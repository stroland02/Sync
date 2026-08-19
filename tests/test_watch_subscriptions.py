"""The watch loop's subscription store: seeded from bindings, overridden by operators only.

The derivation writes with ON CONFLICT DO NOTHING and never deletes, because a re-derivation
that updated would revert every operator edit on every tick -- the failure these tests hold
the door shut on. The cursor tests hold the grain comment in `schema.sql` to its word:
`last_checked_at` moves on every probe, `last_moved_at` only on movement, and a touch never
erases where the cursor sits.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import psycopg

from sync.core import CallSite
from sync.graph.store import GraphStore
from sync.signals.registry import RegisteredAdapter
from sync.watch.subscriptions import DEFAULT_CADENCE_BY_KIND, is_due, seed_subscriptions

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")

ADAPTERS = (
    RegisteredAdapter(vendor_id="stripe", kind="coded", source=None),
    RegisteredAdapter(vendor_id="acmegen", kind="generated", source="acme/acme-sdk"),
)


def _site(repo_id: str, vendor_id: str, line: int = 1) -> CallSite:
    return CallSite(
        repo_id=repo_id,
        path="src/billing.ts",
        line=line,
        col=2,
        vendor_id=vendor_id,
        operation_id="PostCharges",
        symbol=f"{vendor_id}.charges.create",
        sdk_version="17.0.0",
        content_hash="cafe",
    )


def _store() -> GraphStore:
    store = GraphStore(DSN)
    store.apply_schema()
    store.truncate_all()
    return store


def test_seeding_subscribes_every_bound_pair_a_registered_adapter_serves():
    store = _store()
    store.upsert_call_site(_site("github.com/a/app", "stripe"))
    store.upsert_call_site(_site("github.com/a/app", "acmegen", line=9))
    store.upsert_call_site(_site("github.com/b/api", "stripe"))
    store.upsert_call_site(_site("github.com/a/app", "ghost", line=17))

    report = seed_subscriptions(store, adapters=ADAPTERS)

    subs = {
        (row["repo_id"], row["vendor_id"]): row for row in store.watch_subscriptions()
    }
    assert set(subs) == {
        ("github.com/a/app", "stripe"),
        ("github.com/a/app", "acmegen"),
        ("github.com/b/api", "stripe"),
    }, "one subscription per bound pair, and none for a vendor no adapter serves"
    assert subs[("github.com/a/app", "acmegen")]["cadence"] == DEFAULT_CADENCE_BY_KIND["generated"]
    assert subs[("github.com/a/app", "stripe")]["cadence"] == DEFAULT_CADENCE_BY_KIND["coded"]
    assert subs[("github.com/a/app", "stripe")]["policy"] == "auto_pr_breaking"
    assert subs[("github.com/a/app", "stripe")]["paused"] is False

    assert ("github.com/a/app", "ghost") in report.unregistered, (
        "a binding to a vendor no adapter serves is a named absence, never silent scope"
    )
    assert len(report.seeded) == 3


def test_reseeding_converges_and_never_overwrites_an_operator_edit():
    store = _store()
    store.upsert_call_site(_site("github.com/a/app", "stripe"))
    seed_subscriptions(store, adapters=ADAPTERS)

    # The operator's override arrives through whatever authenticates the write; the derivation
    # must survive it. A direct UPDATE is that write in its simplest form.
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute(
            "UPDATE watch_subscription SET paused = true, cadence = 'hourly', "
            "policy = 'notify_only' WHERE repo_id = %s AND vendor_id = %s",
            ["github.com/a/app", "stripe"],
        )

    report = seed_subscriptions(store, adapters=ADAPTERS)

    rows = store.watch_subscriptions()
    assert len(rows) == 1, "re-seeding must converge on the row, not accumulate"
    assert rows[0]["paused"] is True
    assert rows[0]["cadence"] == "hourly"
    assert rows[0]["policy"] == "notify_only"
    assert report.seeded == [], "a pair already subscribed is not re-seeded"


def test_seeding_reads_only_current_bindings():
    store = _store()
    store.upsert_call_site(_site("github.com/a/app", "stripe"))
    # The next pass stops finding the call: the row is retracted, not deleted, and a
    # retracted binding is not a reason to subscribe.
    store.replace_call_sites("github.com/a/app", [])

    report = seed_subscriptions(store, adapters=ADAPTERS)

    assert store.watch_subscriptions() == []
    assert report.seeded == []


def test_first_check_is_always_due_and_cadence_gates_the_second():
    now = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)
    assert is_due("hourly", None, now) is True
    assert is_due("hourly", now - timedelta(minutes=20), now) is False
    assert is_due("hourly", now - timedelta(hours=2), now) is True
    assert is_due("daily", now - timedelta(hours=2), now) is False
    assert is_due("daily", now - timedelta(days=2), now) is True
    # An unknown cadence must not silently skip a vendor forever -- the same direction
    # `SpecSource.changed_from` takes with missing evidence.
    assert is_due("fortnightly", now - timedelta(minutes=1), now) is True


def test_cursor_touch_never_erases_where_the_cursor_sits():
    store = _store()
    t_moved = datetime(2026, 8, 18, 9, 0, tzinfo=timezone.utc)
    t_touch = datetime(2026, 8, 18, 10, 0, tzinfo=timezone.utc)

    store.advance_vendor_cursor(
        "acmegen", last_seen_version="a" * 40, checked_at=t_moved, moved=True
    )
    store.advance_vendor_cursor(
        "acmegen", last_seen_version=None, checked_at=t_touch, moved=False
    )

    cursor = store.vendor_cursor("acmegen")
    assert cursor["last_seen_version"] == "a" * 40, "a touch carries no version and keeps the old one"
    assert cursor["last_checked_at"] == t_touch
    assert cursor["last_moved_at"] == t_moved, "a touch is not movement"


def test_cursor_advance_converges_and_records_movement():
    store = _store()
    t1 = datetime(2026, 8, 18, 9, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 8, 18, 11, 0, tzinfo=timezone.utc)

    assert store.vendor_cursor("acmegen") is None

    store.advance_vendor_cursor("acmegen", last_seen_version="v1", checked_at=t1, moved=True)
    store.advance_vendor_cursor("acmegen", last_seen_version="v2", checked_at=t2, moved=True)

    cursor = store.vendor_cursor("acmegen")
    assert cursor["last_seen_version"] == "v2"
    assert cursor["last_moved_at"] == t2

    with psycopg.connect(DSN, autocommit=True) as conn:
        count = conn.execute(
            "SELECT count(*) FROM vendor_cursor WHERE vendor_id = 'acmegen'"
        ).fetchone()[0]
    assert count == 1, "one row per vendor is the grain; an advance converges on it"
