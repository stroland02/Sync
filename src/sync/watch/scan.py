"""The tick's scan: the same signal and detect composition `sync run` drives, minus two things.

Minus the clone, because the tick detects against call sites INDEX already wrote -- re-indexing
is the repo-HEAD poll's job, not the vendor scan's. And minus `truncate_signal_and_detect`,
deliberately: `run` rebuilds one vendor's window from scratch, while the tick converges
incrementally on whatever the graph holds -- a truncate here would clear every repository's
findings and every vendor's changes on every tick, which is B129's shape arriving on a timer.
Convergence is carried by the natural keys instead: `upsert_vendor_change` and `insert_finding`
land on the rows they already wrote (the oasdiff exemption in `CLAUDE.md` stands -- those
`vendor_change` rows are at-least-once, and no count of them is a measurement).

The stage functions are `cli`'s own -- `prepare_vendor`, `execute_intake_attempt`,
`_detector_suite`, `_scan` -- imported at call time so `sync.watch` stays importable without
dragging in the CLI's LangGraph surface, and so the composition cannot drift from the one
`sync run` uses.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from sync.core import Finding
from sync.graph.store import GraphStore
from sync.signals.intake_attempt import execute_intake_attempt
from sync.signals.registry import VendorContext, prepare_vendor


def scan_window(
    store: GraphStore,
    *,
    vendor_id: str,
    repo_ids: Sequence[str],
    from_version: str,
    to_version: str,
    cache_dir: Path,
) -> dict[str, list[Finding]]:
    """Scan one vendor's version window and detect against every subscribed repository.

    One staging and one intake per vendor, one detector pass per repository: the changes are
    a fact about the vendor, the findings are facts about each repository's call sites.
    """
    from sync.cli import _detector_suite, _scan

    cache = cache_dir / vendor_id
    cache.mkdir(parents=True, exist_ok=True)
    prepared = prepare_vendor(vendor_id, VendorContext(
        cache_dir=cache, from_version=from_version, to_version=to_version,
    ))

    changes, _attempt = execute_intake_attempt(
        prepared.adapter,
        from_version,
        to_version,
        sink=store if hasattr(store, "record_intake_attempt") else None,
    )
    for change in changes:
        store.upsert_vendor_change(change)

    produced: dict[str, list[Finding]] = {}
    for repo_id in repo_ids:
        produced[repo_id] = _scan(
            _detector_suite(
                store,
                spec_documents=prepared.documents,
                # The deprecation signal stages its own artifacts on `run`'s path; the tick
                # scans a vendor window, so that detector correctly has nothing here.
                call_sites=[],
                deprecations=[],
                vendor_id=vendor_id,
                repo_id=repo_id,
            ),
            store,
        )
    return produced
