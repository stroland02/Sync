"""One tick of the watch loop: probe cheaply, scan what moved, decide, and say everything.

The plan (`docs/superpowers/plans/2026-08-18-continuous-watch-loop.md`) fixes the shape: the
tick is idempotent and clock-agnostic, the cheap-poll cascade is an architectural requirement,
and every subscription prints one account of what was decided -- a silent tick is
indistinguishable from a dead one.

Three honesty rulings are implemented as printed sentences rather than silently worked around,
because each is a gap the tree really has:

- **Spend is capped by count, not dollars.** `migration_outcome` records token counts and no
  price; a dollar ceiling would be enforced against a number nobody stores. The findings-per-
  tick cap (owner decision 3) is real, and the tick says which cap is standing in.
- **Remediation is recorded as a decision, not invoked.** `sync run` composes remediation
  around a fresh clone, a checkpointer and a forge per finding; that composition is not
  cleanly reusable from a tick, so the tick marks what it would remediate and leaves the
  invocation to `sync run` rather than half-reimplementing it.
- **The repo-HEAD poll cannot compare.** INDEX resolves the checkout's head sha and stores it
  nowhere -- `index_run` and `codebase_facts` carry timestamps and counts, no commit -- so the
  poll reports the remote HEAD and the recording gap instead of guessing whether to re-index.

Every boundary is injectable and defaults to the real thing: `resolve_head` to `git
ls-remote`, `spec_source` to the registry's manifest read, `scan_window` to the composition
`sync run` uses, `notify` to the B94 stub, `reconcile` to nothing (the CLI wires the forge,
because this package deliberately never imports `sync.forge`).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

from sync.core import Finding
from sync.graph.store import GraphStore
from sync.route.disposition import disposition
from sync.signals.registry import (
    RegisteredAdapter,
    generated_spec_source,
    registered_adapters,
)
from sync.watch import notify as notify_module
from sync.watch import probe, scan
from sync.watch.subscriptions import is_due, seed_subscriptions

FINDINGS_PER_TICK_VARIABLE = "SYNC_WATCH_FINDINGS_PER_TICK"
DEFAULT_FINDINGS_PER_TICK = 5


def _findings_cap(override: int | None) -> int:
    if override is not None:
        return override
    return int(os.environ.get(FINDINGS_PER_TICK_VARIABLE) or DEFAULT_FINDINGS_PER_TICK)


def tick(
    store: GraphStore,
    *,
    cache_dir: Path,
    now: datetime | None = None,
    repo_id: str | None = None,
    vendor_id: str | None = None,
    dry_run: bool = False,
    from_version: str | None = None,
    to_version: str | None = None,
    findings_per_tick: int | None = None,
    catalogue: dict[str, dict] | None = None,
    adapters: Sequence[RegisteredAdapter] | None = None,
    resolve_head: Callable[[str], str | None] | None = None,
    spec_source: Callable[[str, str], object] | None = None,
    scan_window: Callable[..., dict[str, list[Finding]]] | None = None,
    notify: notify_module.NotifyFindings | None = None,
    reconcile: Callable[[], object] | None = None,
    out: Callable[[str], None] = print,
) -> list[str]:
    """One pass over every due subscription. Returns the lines it printed.

    `from_version`/`to_version` are the operator's explicit window for a vendor whose probe
    is not yet cheap (coded and MCP kinds); they apply only to the vendor `vendor_id` names,
    because one pair cannot describe two vendors' version schemes.
    """
    now = now or datetime.now(timezone.utc)
    resolve_head = resolve_head or probe.remote_head
    spec_source = spec_source or generated_spec_source
    scan_window = scan_window or scan.scan_window
    notify = notify or notify_module.notify_findings
    roster = adapters if adapters is not None else registered_adapters()
    by_vendor = {adapter.vendor_id: adapter for adapter in roster}

    lines: list[str] = []

    def say(text: str) -> None:
        lines.append(text)
        out(text)

    seeded = seed_subscriptions(store, adapters=roster, dry_run=dry_run)
    for pair_repo, pair_vendor, cadence in seeded.seeded:
        verb = "dry run: would subscribe" if dry_run else "subscribed"
        say(f"watch: {verb} {pair_repo} x {pair_vendor} (cadence {cadence}, derived from graph bindings)")
    for pair_repo, pair_vendor in seeded.unregistered:
        say(
            f"watch: {pair_repo} x {pair_vendor}: bound in the graph but no adapter is "
            "registered for this vendor; not watchable"
        )

    subscriptions = store.watch_subscriptions(repo_id=repo_id, vendor_id=vendor_id)
    if not subscriptions:
        say("watch: no subscriptions match; nothing is bound in the graph or the filters exclude everything")

    cap = _findings_cap(findings_per_tick)
    remaining = cap
    say(
        f"watch: remediation entry is capped at {cap} finding(s) per tick "
        f"({FINDINGS_PER_TICK_VARIABLE}); spend is capped by count rather than dollars, "
        "because no cost figure is recorded in the tree -- migration_outcome stores token "
        "counts, not price"
    )

    active = [sub for sub in subscriptions if not sub["paused"]]

    # Owner decision 1's repo-HEAD poll, in its local-honest form: one `ls-remote` per
    # subscribed repository. The comparison it wants does not exist yet -- see the module
    # docstring -- so it reports rather than re-indexes.
    for poll_repo in sorted({sub["repo_id"] for sub in active}):
        remote = store.repo_settings(poll_repo).remote_url
        if remote is None:
            say(f"watch: {poll_repo}: HEAD poll skipped; repo_settings names no remote_url")
            continue
        head = resolve_head(remote)
        if head is None:
            say(f"watch: {poll_repo}: could not resolve HEAD of {remote}; the poll retries next tick")
            continue
        say(
            f"watch: {poll_repo}: remote HEAD is {head[:12]}; INDEX records no commit in the "
            "graph to compare against, so re-indexing is skipped rather than guessed"
        )

    notified: list[notify_module.Notified] = []

    def classify(finding: Finding, policy: str) -> tuple[tuple[int, str] | None, str | None]:
        """A (tier, row) worth a pull request, or the reason this finding is notified instead.

        Two gates in order, and they answer different questions. The subscription's policy is
        the operator's standing instruction for this repository and vendor, so it is asked
        first -- `notify_only` declines a finding the routing table would have taken, and that
        is the operator's call rather than the table's. What is left is the table's own
        question, and `sync.route.disposition` is the one place it is answered: the console
        shows a reader the same verdict this tick acts on, from one derivation rather than two
        that drift.

        The facts are the no-clone facts, which `disposition` documents as naming a tier at
        least as expensive as `propose` settles on -- so a finding marked mechanical here
        cannot become an open-ended agent run, and the error direction is a notification that
        could have been a pull request.
        """
        nonlocal catalogue
        if policy == "notify_only":
            return None, "policy is notify_only"
        if policy not in ("auto_pr_breaking", "auto_pr_safe"):
            return None, f"unknown policy '{policy}' treated as notify_only"
        if policy == "auto_pr_breaking" and finding.severity != "breaking":
            return None, f"severity '{finding.severity}' is not breaking"
        if finding.vendor_change_id is None:
            return None, "no vendor change to route"
        change = store.get_vendor_change(finding.vendor_change_id)
        site = store.get_call_site(finding.call_site_id)
        if catalogue is None:
            from sync.cli import load_catalogue

            catalogue = load_catalogue()
        verdict = disposition(change, site, catalogue, repo=None)
        if verdict.automatic:
            return (verdict.tier, verdict.routing_row), None
        return None, verdict.reason

    def decide(sub: dict, findings: list[Finding]) -> None:
        nonlocal remaining
        label = f"watch: {sub['repo_id']} x {sub['vendor_id']}"
        if not findings:
            say(f"{label}: scan produced no findings")
            return
        for finding in findings:
            decision, reason = classify(finding, sub["policy"])
            if decision is None:
                notified.append(
                    notify_module.Notified(
                        finding=finding, reason=reason or "", repo_id=sub["repo_id"]
                    )
                )
                say(f"{label}: finding {finding.id} notified ({reason})")
            elif remaining > 0:
                remaining -= 1
                tier, row = decision
                say(
                    f"{label}: would remediate finding {finding.id} "
                    f"(severity {finding.severity}, row '{row}', tier {tier}); recorded as a "
                    "decision rather than invoked -- `sync run` owns the remediation composition"
                )
            else:
                say(
                    f"{label}: finding {finding.id} queued to the next tick "
                    f"(findings-per-tick cap {cap} reached)"
                )

    def run_scan(vendor: str, due: list[dict], frm: str, to: str) -> None:
        # The cursor advances in the same transaction as the rows the scan writes, which is
        # what the schema's grain comment promises: an at-least-once tick that dies mid-scan
        # rolls the cursor back with the rows and the next tick rescans the same window onto
        # the same natural keys.
        with store.transaction():
            produced = scan_window(
                store,
                vendor_id=vendor,
                repo_ids=[sub["repo_id"] for sub in due],
                from_version=frm,
                to_version=to,
                cache_dir=cache_dir,
            )
            store.advance_vendor_cursor(vendor, last_seen_version=to, checked_at=now, moved=True)
        for sub in due:
            decide(sub, produced.get(sub["repo_id"], []))

    for vendor in sorted({sub["vendor_id"] for sub in subscriptions}):
        vendor_subs = [sub for sub in subscriptions if sub["vendor_id"] == vendor]
        cursor = store.vendor_cursor(vendor)
        checked_at = cursor["last_checked_at"] if cursor else None

        due: list[dict] = []
        for sub in vendor_subs:
            label = f"watch: {sub['repo_id']} x {vendor}"
            if sub["paused"]:
                say(f"{label}: paused")
            elif not is_due(sub["cadence"], checked_at, now):
                say(f"{label}: not due (cadence {sub['cadence']}; last checked {checked_at.isoformat()})")
            else:
                due.append(sub)
        if not due:
            continue

        adapter = by_vendor.get(vendor)
        if adapter is None:
            for sub in due:
                say(
                    f"watch: {sub['repo_id']} x {vendor}: subscribed but no adapter is "
                    "registered for this vendor any more; skipped"
                )
            continue

        if adapter.kind == "generated":
            _tick_generated(
                store, vendor, adapter, due, cursor,
                now=now, dry_run=dry_run, resolve_head=resolve_head,
                spec_source=spec_source, run_scan=run_scan, say=say,
            )
            continue

        # Coded and MCP vendors: v1 has no cheap probe -- a coded adapter's versions are the
        # vendor's own scheme and an MCP capture is taken by something else -- so the tick
        # proceeds only on an operator's explicit window, and says so instead of faking one.
        if from_version and to_version and vendor_id == vendor:
            if dry_run:
                for sub in due:
                    say(
                        f"watch: {sub['repo_id']} x {vendor}: dry run: would scan "
                        f"{from_version} -> {to_version}"
                    )
                continue
            say(f"watch: {vendor}: scanning the explicit window {from_version} -> {to_version}")
            run_scan(vendor, due, from_version, to_version)
            continue

        for sub in due:
            say(
                f"watch: {sub['repo_id']} x {vendor}: no cheap probe exists yet for a "
                f"{adapter.kind} vendor; pass --vendor {vendor} --from-version/--to-version "
                "to scan a window (recorded as checked)"
            )
        if not dry_run:
            store.advance_vendor_cursor(vendor, checked_at=now, moved=False)

    notify(notified, say)

    if dry_run:
        say("watch: reconcile skipped (dry run)")
    elif reconcile is None:
        say("watch: reconcile skipped; no forge wired into this tick")
    else:
        reconcile()
        say("watch: reconciled pull request outcomes")

    return lines


def _tick_generated(
    store: GraphStore,
    vendor: str,
    adapter: RegisteredAdapter,
    due: list[dict],
    cursor: dict | None,
    *,
    now: datetime,
    dry_run: bool,
    resolve_head: Callable[[str], str | None],
    spec_source: Callable[[str, str], object],
    run_scan: Callable[[str, list[dict], str, str], None],
    say: Callable[[str], None],
) -> None:
    """The cheap-poll cascade for one generated vendor, cheapest question first.

    One `ls-remote` answers "did the SDK repository move at all"; only movement pays for two
    manifest reads; only a moved `openapi_spec_hash` pays for a scan. A probe failure writes
    no cursor, deliberately -- the subscription stays due and the next tick retries, where a
    stamped check would silently push the retry a full cadence away.
    """
    remote = f"https://github.com/{adapter.source}"
    head = resolve_head(remote)
    if head is None:
        for sub in due:
            say(
                f"watch: {sub['repo_id']} x {vendor}: could not resolve HEAD of {remote}; "
                "nothing scanned, the probe retries next tick"
            )
        return

    last = cursor["last_seen_version"] if cursor else None

    if last is None:
        for sub in due:
            prefix = "dry run: would establish" if dry_run else "established"
            say(
                f"watch: {sub['repo_id']} x {vendor}: {prefix} the baseline at {head[:12]}; "
                "a diff needs two ends and the cursor had none, so nothing is scanned"
            )
        if not dry_run:
            store.advance_vendor_cursor(vendor, last_seen_version=head, checked_at=now, moved=False)
        return

    if last == head:
        for sub in due:
            say(f"watch: {sub['repo_id']} x {vendor}: nothing moved (SDK repository still at {head[:12]})")
        if not dry_run:
            store.advance_vendor_cursor(vendor, checked_at=now, moved=False)
        return

    try:
        base_source = spec_source(vendor, last)
        head_source = spec_source(vendor, head)
    except Exception as exc:
        for sub in due:
            say(
                f"watch: {sub['repo_id']} x {vendor}: manifest probe failed "
                f"({type(exc).__name__}: {exc}); nothing scanned, the probe retries next tick"
            )
        return

    if not head_source.changed_from(base_source):
        for sub in due:
            say(
                f"watch: {sub['repo_id']} x {vendor}: SDK repository moved to {head[:12]} but "
                "the specification hash is unchanged; cursor advances without a scan"
            )
        if not dry_run:
            store.advance_vendor_cursor(vendor, last_seen_version=head, checked_at=now, moved=False)
        return

    if dry_run:
        for sub in due:
            say(
                f"watch: {sub['repo_id']} x {vendor}: dry run: would scan {last[:12]} -> {head[:12]}"
            )
        return

    say(f"watch: {vendor}: specification moved {last[:12]} -> {head[:12]}; scanning {len(due)} repository(ies)")
    run_scan(vendor, due, last, head)
