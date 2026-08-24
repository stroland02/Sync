"""What adapters this deployment has registered, and what each has ever delivered.

The console's Settings screen is drawn and has no route, and the reason it is worth building is
narrow: an operator can read a vendor's findings but cannot read whether the adapter behind that
vendor has ever run. A vendor with no findings and a vendor whose adapter has never been reached
look identical on every screen that exists today.

**The distinction this module carries is never-measured against nothing-here.** A registered
adapter the graph holds no `vendor_change` row for answers `None` for its counts, not `0`. Zero
says Sync asked the vendor and the vendor had changed nothing; `None` says Sync has never
received anything from that adapter at all. Both are legitimate states and only one of them is a
problem, so collapsing them onto `0` hides exactly the case the screen exists to show.

Nothing here reaches a vendor. `registered_adapters` reads configuration and `adapter_inventory`
reads the graph; neither fetches, and a "last intake" is the newest row the graph holds rather
than the last time an adapter was asked. Those are different facts and the second one is not
recorded anywhere yet -- stated in `adapter_inventory`'s docstring rather than approximated here.
"""

from __future__ import annotations

import os
import textwrap
from pathlib import Path

import pytest

from sync.core import VendorChange
from sync.dashboard.adapters import adapter_inventory
from sync.graph.store import GraphStore
from sync.signals.registry import (
    GENERATED_VENDORS_VARIABLE,
    MCP_SERVERS_VARIABLE,
    RegisteredAdapter,
    registered_adapters,
)

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")


@pytest.fixture()
def store():
    s = GraphStore(DSN)
    s.apply_schema()
    s.truncate_all()
    return s


def _change(**kw) -> VendorChange:
    base = dict(
        vendor_id="stripe",
        from_version="v1",
        to_version="v2",
        kind="request-parameter-removed",
        operation_id="PostCharges",
        path_ptr="/paths/~1charges/post",
        severity="breaking",
        source="oasdiff",
    )
    base.update(kw)
    return VendorChange(**base)


# --- the registry side: what is configured, without touching a vendor --------


def test_the_remaining_hand_written_adapter_is_reported_as_coded():
    coded = {entry.vendor_id: entry for entry in registered_adapters() if entry.kind == "coded"}

    # One, since `CI-W586` made stripe a configuration row. `A13` retires the last of them, at
    # which point this set is empty and the `coded` kind goes with it.
    assert set(coded) == {"twilio"}
    assert coded["twilio"].source is None


def test_a_configured_generated_vendor_reports_the_repository_it_reads(tmp_path, monkeypatch):
    manifest = tmp_path / "vendors.yaml"
    manifest.write_text(
        textwrap.dedent(
            """\
            - vendor_id: acme
              repo: acme/acme-node
              manifest: .stats.yml
            """
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(GENERATED_VENDORS_VARIABLE, str(manifest))
    monkeypatch.setenv(MCP_SERVERS_VARIABLE, str(tmp_path / "absent.yaml"))

    entry = next(e for e in registered_adapters() if e.vendor_id == "acme")

    assert entry.kind == "generated"
    assert entry.source == "acme/acme-node"


def test_a_watched_mcp_server_is_reported_under_the_id_a_row_is_keyed_by(tmp_path, monkeypatch):
    servers = tmp_path / "servers.yaml"
    servers.write_text("- server_id: paperless\n", encoding="utf-8")
    monkeypatch.setenv(MCP_SERVERS_VARIABLE, str(servers))
    monkeypatch.setenv(GENERATED_VENDORS_VARIABLE, str(tmp_path / "absent.yaml"))

    ids = {entry.vendor_id: entry.kind for entry in registered_adapters()}

    assert ids["mcp:paperless"] == "mcp"


def test_every_registered_id_is_one_the_command_line_would_accept(tmp_path, monkeypatch):
    """`available_vendors` is what `--vendor` validates against. Two lists of registered vendors
    that can disagree is the defect the registry docstring already names for `_CODED_ADAPTERS`,
    and this one would show up as a Settings row for an adapter no run can select.
    """
    from sync.signals.registry import available_vendors

    monkeypatch.setenv(GENERATED_VENDORS_VARIABLE, str(tmp_path / "absent.yaml"))
    monkeypatch.setenv(MCP_SERVERS_VARIABLE, str(tmp_path / "absent.yaml"))

    assert {entry.vendor_id for entry in registered_adapters()} == set(available_vendors())


def test_the_entries_are_sorted_so_the_screen_has_a_stable_order():
    ids = [entry.vendor_id for entry in registered_adapters()]

    assert ids == sorted(ids)


# --- the graph side: what each adapter has actually delivered ----------------


def _rows(inventory: dict) -> dict[str, dict]:
    return {row["vendor_id"]: row for row in inventory["adapters"]}


def test_an_adapter_that_has_never_delivered_answers_never_measured_rather_than_zero(store):
    """The distinction the screen exists for.

    `0 operations` is a measurement: Sync read the vendor's specification and found nothing to
    say. `None` is the absence of one. An operator looking for the adapter that silently stopped
    working needs to tell those apart, and a table that prints `0` for both hides it in the row
    that looks most reassuring.
    """
    registry = (RegisteredAdapter(vendor_id="stripe", kind="coded", source=None),)

    row = _rows(adapter_inventory(store, adapters=registry))["stripe"]

    assert row["changes"] is None
    assert row["operations"] is None
    assert row["last_change_at"] is None


def test_an_adapter_that_has_delivered_reports_its_counts(store):
    store.upsert_vendor_change(_change(operation_id="PostCharges"))
    store.upsert_vendor_change(_change(operation_id="PostCharges", kind="parameter-deprecated"))
    store.upsert_vendor_change(_change(operation_id="GetCharges"))
    registry = (RegisteredAdapter(vendor_id="stripe", kind="coded", source=None),)

    row = _rows(adapter_inventory(store, adapters=registry))["stripe"]

    assert row["changes"] == 3
    assert row["operations"] == 2
    assert row["last_change_at"] is not None


def test_one_adapters_rows_are_not_counted_against_another(store):
    store.upsert_vendor_change(_change(vendor_id="stripe"))
    store.upsert_vendor_change(_change(vendor_id="twilio", operation_id="CreateMessage"))
    registry = (
        RegisteredAdapter(vendor_id="stripe", kind="coded", source=None),
        RegisteredAdapter(vendor_id="twilio", kind="coded", source=None),
    )

    rows = _rows(adapter_inventory(store, adapters=registry))

    assert rows["stripe"]["changes"] == 1
    assert rows["twilio"]["changes"] == 1


def test_the_intake_sources_a_vendors_rows_carry_are_named(store):
    """`vendor_change.source` records which route produced a row. An adapter delivering through
    two of them is a fact about the deployment an operator cannot read anywhere else.
    """
    store.upsert_vendor_change(_change(source="oasdiff"))
    store.upsert_vendor_change(_change(operation_id="GetCharges", source="changelog"))
    registry = (RegisteredAdapter(vendor_id="stripe", kind="coded", source=None),)

    row = _rows(adapter_inventory(store, adapters=registry))["stripe"]

    assert row["sources"] == ["changelog", "oasdiff"]


def test_a_vendor_the_graph_holds_rows_for_but_nobody_registered_is_reported_as_unregistered(store):
    """A row keyed by a vendor id no adapter serves any more.

    Dropping it would make the table say the graph holds nothing from that vendor, which is
    false and is the direction that loses data. It is listed with `kind` naming what it is:
    history from an adapter this deployment no longer registers.
    """
    store.upsert_vendor_change(_change(vendor_id="retired-vendor"))
    registry = (RegisteredAdapter(vendor_id="stripe", kind="coded", source=None),)

    rows = _rows(adapter_inventory(store, adapters=registry))

    assert rows["retired-vendor"]["kind"] == "unregistered"
    assert rows["retired-vendor"]["changes"] == 1


def test_the_table_is_ordered_by_vendor_id(store):
    store.upsert_vendor_change(_change(vendor_id="twilio"))
    registry = (
        RegisteredAdapter(vendor_id="stripe", kind="coded", source=None),
        RegisteredAdapter(vendor_id="acme", kind="generated", source="acme/acme-node"),
    )

    listed = [row["vendor_id"] for row in adapter_inventory(store, adapters=registry)["adapters"]]

    assert listed == sorted(listed)


def test_nothing_here_records_why_an_adapter_declined(store):
    """The screen's drawn Cloudflare row -- a catalogue that served an HTML error page -- has no
    field behind it, and inventing one that is always null would be worse than its absence: a
    column of blanks reads as "no adapter has ever declined", which nothing here measured.

    This asserts the gap rather than papering over it. B136 is the row that closes it -- an
    intake attempt record, one row per attempt; when it lands this test is the one to change.
    """
    registry = (RegisteredAdapter(vendor_id="stripe", kind="coded", source=None),)

    row = _rows(adapter_inventory(store, adapters=registry))["stripe"]

    assert "decline_reason" not in row


def test_inventory_carries_the_last_attempt_not_only_the_last_delivery(store):
    """B136's console half: an adapter that ran and found nothing is not an adapter that never ran.

    `last_change_at` is the newest `vendor_change` row, so an adapter polled hourly that has found
    nothing new for a week reports last week. That limit is stated in `adapter_inventory`'s own
    docstring and it is what `intake_attempt` exists to close: the attempt record says when the
    adapter was last *asked*, which is the question an operator reading this screen actually has.
    """
    from datetime import datetime, timezone

    from sync.signals.intake_attempt import IntakeAttempt

    store.record_intake_attempt(
        IntakeAttempt(
            vendor_id="stripe",
            attempted_at=datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc),
            outcome="success",
            changes_count=3,
        )
    )
    store.record_intake_attempt(
        IntakeAttempt(
            vendor_id="stripe",
            attempted_at=datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc),
            outcome="declined",
            reason_code="up_to_date",
        )
    )

    rows = {row["vendor_id"]: row for row in adapter_inventory(store)["adapters"]}

    assert rows["stripe"]["last_attempt_at"] == "2026-08-19T12:00:00+00:00"
    assert rows["stripe"]["last_attempt_outcome"] == "declined"
    # The reason vocabulary is closed, which is what makes an aggregate over it possible at all --
    # the docstring's "there is deliberately no decline_reason" limit closes here.
    assert rows["stripe"]["last_attempt_reason"] == "up_to_date"
    assert rows["stripe"]["attempts"] == {"success": 1, "declined": 1}


def test_an_adapter_with_no_attempt_recorded_reports_none_rather_than_never_asked(store):
    """Absence, not a claim. A vendor with no attempt row has no attempt *record* -- which is not
    the same as an adapter that was never asked, because the record only began being written when
    `intake_attempt` landed. Nulls say "this screen cannot tell you", never "it never ran".
    """
    rows = {row["vendor_id"]: row for row in adapter_inventory(store)["adapters"]}
    some_adapter = next(iter(rows.values()))

    assert some_adapter["last_attempt_at"] is None
    assert some_adapter["last_attempt_outcome"] is None
    assert some_adapter["attempts"] == {}
