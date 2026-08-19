"""One idempotent tick of the watch loop, decided against a real graph.

Every network and subprocess boundary is injected -- `resolve_head`, `spec_source`,
`scan_window`, `notify`, `reconcile` -- which is the registry's own pattern (`fetch_manifest`
is a module attribute for the same reason). What is NOT faked is the store: subscriptions,
cursors, call sites and vendor changes are real rows, because the tick's promises are about
what lands in them and in what transaction.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sync.core import CallSite, Finding, VendorChange
from sync.graph.store import GraphStore
from sync.signals.generated.manifest import SpecSource
from sync.signals.registry import RegisteredAdapter
from sync.watch.subscriptions import seed_subscriptions
from sync.watch.tick import tick

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")

REPO = "github.com/a/app"
SDK_REPO = "acme/acme-sdk"
SHA1 = "1" * 40
SHA2 = "2" * 40

ADAPTERS = (
    RegisteredAdapter(vendor_id="acmegen", kind="generated", source=SDK_REPO),
    RegisteredAdapter(vendor_id="stripe", kind="coded", source=None),
)

# One rule whose row the decision table can settle without a clone: a required request
# property added routes TEMPLATED when the field resolves (row 6), which is the
# below-the-agent tier the policy reads as mechanically safe.
KIND = "request-property-became-required"
CATALOGUE = {
    KIND: {"id": KIND, "kind": "existence", "action": "add", "direction": "request", "level": "error"}
}


def _store() -> GraphStore:
    store = GraphStore(DSN)
    store.apply_schema()
    store.truncate_all()
    return store


def _site(vendor_id: str = "acmegen", repo_id: str = REPO) -> CallSite:
    return CallSite(
        repo_id=repo_id,
        path="src/billing.ts",
        line=3,
        col=2,
        vendor_id=vendor_id,
        operation_id="PostCharges",
        symbol=f"{vendor_id}.charges.create",
        sdk_version="17.0.0",
        content_hash="cafe",
    )


def _change(severity: str = "breaking") -> VendorChange:
    return VendorChange(
        vendor_id="acmegen",
        from_version=SHA1,
        to_version=SHA2,
        kind=KIND,
        operation_id="PostCharges",
        path_ptr="/v1/charges",
        severity=severity,
        source="oasdiff",
        raw={"id": KIND, "text": "added the required request property `customer_name`"},
    )


def _fake_scan(findings_per_repo: int = 1, severity: str = "breaking"):
    """A scan that writes real rows the policy step must read back by id."""

    calls: list[dict] = []

    def scan_window(store, *, vendor_id, repo_ids, from_version, to_version, cache_dir):
        calls.append({
            "vendor_id": vendor_id, "repo_ids": list(repo_ids),
            "from_version": from_version, "to_version": to_version,
        })
        change = _change(severity)
        change.id = store.upsert_vendor_change(change)
        produced: dict[str, list[Finding]] = {}
        for repo_id in repo_ids:
            findings = []
            for n in range(findings_per_repo):
                site = _site(vendor_id, repo_id)
                site.line = 100 + n
                site.id = store.upsert_call_site(site)
                finding = Finding(
                    detector="vendor_change",
                    claim=f"breaks:{n}",
                    call_site_id=site.id,
                    vendor_change_id=change.id,
                    severity=severity,
                    rationale="the operation this call site uses changed",
                    binding_rung="static",
                )
                finding.id = store.insert_finding(finding)
                findings.append(finding)
            produced[repo_id] = findings
        return produced

    scan_window.calls = calls
    return scan_window


def _subscribed_store(vendor_id: str = "acmegen") -> GraphStore:
    store = _store()
    store.upsert_call_site(_site(vendor_id))
    seed_subscriptions(store, adapters=ADAPTERS)
    return store


NOW = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)


def _tick(store, **overrides):
    defaults = dict(
        cache_dir=Path(".cache/specs"),
        now=NOW,
        adapters=ADAPTERS,
        catalogue=CATALOGUE,
        resolve_head=lambda remote: SHA2,
        spec_source=lambda vendor, ref: SpecSource(generator="stainless", spec_hash=ref),
        scan_window=_fake_scan(),
    )
    defaults.update(overrides)
    return tick(store, **defaults)


def _refusing_scan(**_kwargs):
    raise AssertionError("this tick must not scan")


def test_first_tick_establishes_a_baseline_and_scans_nothing():
    store = _subscribed_store()

    lines = _tick(store, scan_window=_refusing_scan)

    assert any("baseline" in line for line in lines), lines
    cursor = store.vendor_cursor("acmegen")
    assert cursor["last_seen_version"] == SHA2
    assert cursor["last_checked_at"] == NOW


def test_unmoved_head_prints_nothing_moved_and_is_not_movement():
    store = _subscribed_store()
    t0 = NOW - timedelta(hours=6)
    store.advance_vendor_cursor("acmegen", last_seen_version=SHA2, checked_at=t0, moved=True)

    lines = _tick(store, scan_window=_refusing_scan)

    assert any("nothing moved" in line for line in lines), lines
    cursor = store.vendor_cursor("acmegen")
    assert cursor["last_checked_at"] == NOW
    assert cursor["last_moved_at"] == t0, "an unmoved probe is a check, not movement"


def test_moved_head_with_unmoved_spec_hash_advances_without_a_scan():
    store = _subscribed_store()
    t0 = NOW - timedelta(hours=6)
    store.advance_vendor_cursor("acmegen", last_seen_version=SHA1, checked_at=t0, moved=True)

    lines = _tick(
        store,
        scan_window=_refusing_scan,
        # The same hash whatever ref is asked about: the SDK repo moved for reasons that
        # were not its specification.
        spec_source=lambda vendor, ref: SpecSource(generator="stainless", spec_hash="same"),
    )

    assert any("unchanged" in line for line in lines), lines
    cursor = store.vendor_cursor("acmegen")
    assert cursor["last_seen_version"] == SHA2, "the cursor still advances past the quiet window"
    assert cursor["last_moved_at"] == t0


def test_moved_hash_scans_the_window_and_advances_the_cursor_in_step():
    store = _subscribed_store()
    store.advance_vendor_cursor(
        "acmegen", last_seen_version=SHA1, checked_at=NOW - timedelta(hours=6), moved=True
    )
    scan = _fake_scan()

    lines = _tick(store, scan_window=scan)

    assert scan.calls == [{
        "vendor_id": "acmegen", "repo_ids": [REPO],
        "from_version": SHA1, "to_version": SHA2,
    }]
    cursor = store.vendor_cursor("acmegen")
    assert cursor["last_seen_version"] == SHA2
    assert cursor["last_moved_at"] == NOW
    assert any("would remediate" in line for line in lines), lines


def test_within_cadence_nothing_is_probed_and_the_line_says_not_due():
    store = _subscribed_store()
    store.advance_vendor_cursor(
        "acmegen", last_seen_version=SHA1, checked_at=NOW - timedelta(minutes=10), moved=False
    )

    lines = _tick(
        store,
        scan_window=_refusing_scan,
        resolve_head=lambda remote: pytest.fail("a not-due subscription must not probe"),
    )

    assert any("not due" in line for line in lines), lines


def test_paused_subscription_is_skipped_loudly():
    store = _subscribed_store()
    import psycopg

    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("UPDATE watch_subscription SET paused = true")

    lines = _tick(
        store,
        scan_window=_refusing_scan,
        resolve_head=lambda remote: pytest.fail("a paused subscription must not probe"),
    )

    assert any("paused" in line for line in lines), lines


def test_findings_cap_queues_overflow_visibly_and_spend_is_capped_by_count():
    store = _subscribed_store()
    store.advance_vendor_cursor(
        "acmegen", last_seen_version=SHA1, checked_at=NOW - timedelta(hours=6), moved=True
    )

    lines = _tick(store, scan_window=_fake_scan(findings_per_repo=7), findings_per_tick=5)

    assert sum("would remediate" in line for line in lines) == 5
    assert sum("queued" in line for line in lines) == 2, (
        "overflow is queued visibly, never silently dropped"
    )
    assert any("dollars" in line for line in lines), (
        "the tick says spend is capped by count rather than dollars, because no cost "
        "figure is recorded anywhere in the tree"
    )


def test_findings_cap_default_reads_the_environment(monkeypatch):
    monkeypatch.setenv("SYNC_WATCH_FINDINGS_PER_TICK", "1")
    store = _subscribed_store()
    store.advance_vendor_cursor(
        "acmegen", last_seen_version=SHA1, checked_at=NOW - timedelta(hours=6), moved=True
    )

    lines = _tick(store, scan_window=_fake_scan(findings_per_repo=3))

    assert sum("would remediate" in line for line in lines) == 1
    assert sum("queued" in line for line in lines) == 2


def test_notify_only_policy_remediates_nothing_and_hands_findings_to_the_seam():
    store = _subscribed_store()
    import psycopg

    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("UPDATE watch_subscription SET policy = 'notify_only'")
    store.advance_vendor_cursor(
        "acmegen", last_seen_version=SHA1, checked_at=NOW - timedelta(hours=6), moved=True
    )
    received: list = []

    lines = _tick(
        store,
        scan_window=_fake_scan(findings_per_repo=2),
        notify=lambda findings, out: received.extend(findings),
    )

    assert not any("would remediate" in line for line in lines), lines
    assert len(received) == 2, "every non-PR finding reaches the notification seam"
    # The seam carries what a notifier needs and the tick already knows: the finding, why it
    # was not remediated, and which repository to notify on. Bare findings forced the forge
    # adapter to re-derive the reason, which is how two surfaces disagree about one decision.
    assert all(item.reason for item in received)
    assert all(item.repo_id == REPO for item in received)
    assert all(item.finding.id for item in received)


def test_non_breaking_findings_are_notified_under_auto_pr_breaking():
    store = _subscribed_store()
    store.advance_vendor_cursor(
        "acmegen", last_seen_version=SHA1, checked_at=NOW - timedelta(hours=6), moved=True
    )
    received: list = []

    lines = _tick(
        store,
        scan_window=_fake_scan(severity="warning"),
        notify=lambda findings, out: received.extend(findings),
    )

    assert not any("would remediate" in line for line in lines), lines
    assert len(received) == 1


def test_default_notification_seam_records_the_pending_b94_destination():
    store = _subscribed_store()
    store.advance_vendor_cursor(
        "acmegen", last_seen_version=SHA1, checked_at=NOW - timedelta(hours=6), moved=True
    )

    lines = _tick(store, scan_window=_fake_scan(severity="warning"))

    assert any("B94" in line for line in lines), (
        "with no notifier configured, the tick says the destination is pending B94 "
        "rather than pretending a notification happened"
    )


def test_coded_vendor_without_an_explicit_pair_says_the_probe_is_not_cheap_yet():
    store = _subscribed_store("stripe")

    lines = _tick(store, scan_window=_refusing_scan)

    assert any("cheap" in line for line in lines), lines
    cursor = store.vendor_cursor("stripe")
    assert cursor is not None and cursor["last_checked_at"] == NOW, (
        "the check happened and is recorded, even though it could not probe"
    )


def test_coded_vendor_with_an_explicit_pair_scans_that_window():
    store = _subscribed_store("stripe")
    scan = _fake_scan()

    _tick(store, vendor_id="stripe", from_version="v2320", to_version="v2330", scan_window=scan)

    assert scan.calls and scan.calls[0]["from_version"] == "v2320"
    assert store.vendor_cursor("stripe")["last_seen_version"] == "v2330"


def test_head_poll_reports_the_index_recording_gap():
    from sync.core.models import RepoSettings

    store = _subscribed_store()
    store.upsert_repo_settings(
        RepoSettings(repo_id=REPO, remote_url="https://github.com/a/app")
    )
    polled: list[str] = []

    def resolve_head(remote: str) -> str:
        polled.append(remote)
        return SHA2

    lines = _tick(store, scan_window=_refusing_scan, resolve_head=resolve_head)

    assert "https://github.com/a/app" in polled
    assert any("no commit" in line for line in lines), (
        "INDEX records no commit in the graph, so the poll must report the gap and skip "
        "re-indexing rather than guess"
    )


def test_head_poll_without_a_remote_is_skipped_and_says_so():
    store = _subscribed_store()

    lines = _tick(store, scan_window=_refusing_scan)

    assert any("remote_url" in line for line in lines), lines


def test_reconcile_runs_at_the_end_of_the_tick():
    store = _subscribed_store()
    ran: list[bool] = []

    _tick(store, scan_window=_refusing_scan, reconcile=lambda: ran.append(True))

    assert ran == [True]


def test_dry_run_probes_but_writes_nothing_and_reconciles_nothing():
    store = _subscribed_store()
    ran: list[bool] = []

    lines = _tick(
        store, dry_run=True, scan_window=_refusing_scan, reconcile=lambda: ran.append(True)
    )

    assert store.vendor_cursor("acmegen") is None, "a dry run advances no cursor"
    assert store.watch_subscriptions() != [], "seeding happened before the dry run began"
    assert ran == [], "a dry run reconciles nothing"
    assert any("dry run" in line for line in lines), lines


def test_dry_run_on_a_moved_hash_says_what_it_would_scan():
    store = _store()
    store.upsert_call_site(_site())
    seed_subscriptions(store, adapters=ADAPTERS)
    store.advance_vendor_cursor(
        "acmegen", last_seen_version=SHA1, checked_at=NOW - timedelta(hours=6), moved=True
    )

    lines = _tick(store, dry_run=True, scan_window=_refusing_scan)

    assert any("would scan" in line for line in lines), lines
    assert store.vendor_cursor("acmegen")["last_seen_version"] == SHA1


def test_every_subscription_prints_a_line():
    """A silent tick is indistinguishable from a dead one."""
    store = _store()
    store.upsert_call_site(_site("acmegen"))
    store.upsert_call_site(_site("stripe"))
    seed_subscriptions(store, adapters=ADAPTERS)

    lines = _tick(store, scan_window=_refusing_scan)

    for vendor in ("acmegen", "stripe"):
        assert any(f"{REPO} x {vendor}:" in line for line in lines), (vendor, lines)


def test_the_cli_offers_watch_once():
    from sync.cli import build_parser

    args = build_parser().parse_args(["watch", "--once"])
    assert args.once is True
    assert args.dry_run is False
    assert args.repo_id is None and args.vendor is None

    with pytest.raises(SystemExit):
        # The tick is the contract and --once is deliberate: `sync watch` without it must
        # refuse rather than quietly run some other mode.
        build_parser().parse_args(["watch"])


def test_the_cli_folds_tick_reasons_onto_the_forge_vocabulary():
    """The forge refuses free text; every reason the tick can produce must land on one of its
    three stories, and the fold lives in the CLI because that is where the two packages meet."""
    from sync.cli import forge_notify_reason
    from sync.forge.notify import NOTIFY_REASONS

    tick_reasons = [
        "policy is notify_only",
        "unknown policy 'x' treated as notify_only",
        "severity 'warning' is not breaking",
        "no vendor change to route",
        "the routing table has no jurisdiction over 'field-removed'",
        "no patch is warranted (row 'r')",
        "not mechanically safe (row 'r' routes to the agent tier)",
        "findings-per-tick cap 5 reached",
    ]
    for reason in tick_reasons:
        assert forge_notify_reason(reason) in NOTIFY_REASONS, reason
