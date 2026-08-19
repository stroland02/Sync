"""The Settings screen's adapter table: what is registered, and what each has ever delivered.

Every other console screen answers a question about a vendor. None of them answers a question
about the adapter behind it, so a vendor with nothing to report and a vendor whose adapter has
never been reached render identically -- as an empty row on the screen that looks most reassuring.

Two sources, joined here and nowhere else. `sync.signals.registry` says what this deployment
registered, reading configuration and constructing nothing. `GraphStore.vendor_intake_rollup` says
what the graph holds. Neither reaches a vendor, and the join is a full outer one because both
sides carry entries the other does not: a registered adapter that has never delivered, and history
keyed by a vendor id nobody registers any more.
"""

from __future__ import annotations

from typing import Iterable

from sync.graph.store import GraphStore
from sync.signals.registry import RegisteredAdapter, registered_adapters

NEVER_DELIVERED: dict[str, None] = {
    "changes": None,
    "operations": None,
    "last_change_at": None,
    "sources": None,
}

# No attempt row for this vendor. Every field is null and `attempts` is empty rather than zeroed,
# for the reason the delivery mapping above uses nulls: the attempt record began when the table
# did, so "no row" means this screen cannot tell you whether the adapter ran -- never that it
# did not. A zero here would be a measurement nobody took.
NO_ATTEMPT_RECORDED: dict = {
    "last_attempt_at": None,
    "last_attempt_outcome": None,
    "last_attempt_reason": None,
    "last_attempt_changes": None,
    "attempts": {},
}
"""What a registered adapter the graph holds no row for answers.

`None` and not `0`. Zero is a measurement -- Sync read the vendor's specification and found
nothing to say -- and the absence of one is the state an operator is looking for when an adapter
has silently stopped working. `.claude/rules/console-surface.md` binds the console to rendering
absence apart from zero, and a view model that collapses them here leaves the screen nothing to
render the distinction from.
"""


def adapter_inventory(
    store: GraphStore, *, adapters: Iterable[RegisteredAdapter] | None = None
) -> dict:
    """One row per adapter, registered or historical, ordered by vendor id.

    `adapters` is injectable so a test can name its own registry rather than the deployment's;
    the default is what this deployment actually registers.

    **`last_change_at` is the newest row the graph holds, which is not the last time an adapter
    was asked.** An adapter polled hourly that has found nothing new for a week reports last
    week's date, and there is no field here that would say otherwise: nothing records an intake
    attempt, only its result. Naming it `last_change_at` rather than `last_intake` is the whole
    of the fix available without that record, and the screen must not relabel it.

    **Both limits above are closed as of `CI-W501`, and the wording is kept because the reason
    still holds for the `last_change_at` column itself.** `intake_attempt` now records the
    attempt, so `last_attempt_at` sits beside `last_change_at` and the two say different things:
    when the adapter was last *asked*, and when it last had something to say. An adapter that is
    healthy and quiet has a recent first and an old second -- previously indistinguishable from
    one nobody had run. `last_attempt_reason` is the decline reason, drawn from the closed
    vocabulary `sync.signals.intake_attempt` owns, which is what makes it aggregatable rather
    than free text.

    **A null in either group is still not a zero**, and the two nulls mean different things: no
    delivery means the graph holds no change from this adapter, no attempt means the graph holds
    no record of it being asked -- and since that record only began when the table did, it never
    means the adapter was not asked.
    """
    registered = list(registered_adapters() if adapters is None else adapters)
    delivered = store.vendor_intake_rollup()
    attempted = store.intake_attempt_rollup()

    rows = [
        {
            "vendor_id": entry.vendor_id,
            "kind": entry.kind,
            "source": entry.source,
            **delivered.get(entry.vendor_id, NEVER_DELIVERED),
            **attempted.get(entry.vendor_id, NO_ATTEMPT_RECORDED),
        }
        for entry in registered
    ]
    known = {entry.vendor_id for entry in registered}
    rows += [
        {
            "vendor_id": vendor_id,
            "kind": "unregistered",
            "source": None,
            **rollup,
            **attempted.get(vendor_id, NO_ATTEMPT_RECORDED),
        }
        for vendor_id, rollup in delivered.items()
        if vendor_id not in known
    ]
    return {"adapters": sorted(rows, key=lambda row: row["vendor_id"])}
