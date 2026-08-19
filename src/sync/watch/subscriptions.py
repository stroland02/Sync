"""Deriving watch subscriptions from what the graph already binds.

A repository is watched against every vendor its indexed call sites bind to -- connecting an
integration *is* indexing it, so nobody configures a subscription by hand. The operator's part
is overrides only, which is why the seed goes through `seed_watch_subscription`'s
ON CONFLICT DO NOTHING and never deletes: a derivation that updated would revert every operator
edit on every tick, and one that deleted would unsubscribe a repository because one pass failed
to bind it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Sequence

from sync.graph.store import GraphStore
from sync.signals.registry import RegisteredAdapter, registered_adapters

# Defaulted by what a check costs, per the plan: a generated vendor's probe is one `ls-remote`
# and at most two small manifest fetches; coded staging downloads specifications and MCP needs
# a capture. Operators override per subscription.
DEFAULT_CADENCE_BY_KIND = {"generated": "hourly", "coded": "daily", "mcp": "daily"}

CADENCE_INTERVALS = {"hourly": timedelta(hours=1), "daily": timedelta(days=1)}


def is_due(cadence: str, last_checked_at: datetime | None, now: datetime) -> bool:
    """Whether a subscription's next check has arrived. The first check is always due.

    An unknown cadence answers due rather than never -- the direction `SpecSource.changed_from`
    takes with missing evidence, and for the same reason: a subscription silently skipped
    forever is the expensive failure precisely because it is invisible.
    """
    if last_checked_at is None:
        return True
    interval = CADENCE_INTERVALS.get(cadence)
    if interval is None:
        return True
    return now - last_checked_at >= interval


@dataclass(frozen=True)
class SeedReport:
    """What one derivation pass did, so the tick can say it."""

    seeded: list[tuple[str, str, str]]
    """(repo_id, vendor_id, cadence) for each pair newly subscribed."""

    unregistered: list[tuple[str, str]]
    """(repo_id, vendor_id) pairs bound in the graph that no registered adapter serves.

    Named absence, never silent scope: the catalog's recognized-but-unwatched vendors surface
    here rather than quietly falling outside the loop.
    """


def seed_subscriptions(
    store: GraphStore,
    *,
    adapters: Sequence[RegisteredAdapter] | None = None,
    dry_run: bool = False,
) -> SeedReport:
    """Subscribe every current (repo, vendor) binding a registered adapter serves.

    `adapters` is injectable because `registered_adapters()` reads deployment configuration
    files; a test declares its own roster instead of writing them.
    """
    roster = adapters if adapters is not None else registered_adapters()
    kinds = {adapter.vendor_id: adapter.kind for adapter in roster}

    existing = {
        (row["repo_id"], row["vendor_id"]) for row in store.watch_subscriptions()
    }
    seeded: list[tuple[str, str, str]] = []
    unregistered: list[tuple[str, str]] = []

    for repo_id, vendor_id in store.bound_repo_vendor_pairs():
        kind = kinds.get(vendor_id)
        if kind is None:
            unregistered.append((repo_id, vendor_id))
            continue
        cadence = DEFAULT_CADENCE_BY_KIND.get(kind, "daily")
        if dry_run:
            if (repo_id, vendor_id) not in existing:
                seeded.append((repo_id, vendor_id, cadence))
        elif store.seed_watch_subscription(repo_id, vendor_id, cadence=cadence):
            seeded.append((repo_id, vendor_id, cadence))

    return SeedReport(seeded=seeded, unregistered=unregistered)
