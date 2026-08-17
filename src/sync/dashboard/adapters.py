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

    There is deliberately no `decline_reason`. Nothing in this repository records why an adapter
    declined, and a column that is null on every row reads as "no adapter has ever declined" --
    a claim nothing measured, on the screen whose argument is that it does not make those. B136
    is the intake attempt record that closes both this and the `last_change_at` limit above.
    """
    registered = list(registered_adapters() if adapters is None else adapters)
    delivered = store.vendor_intake_rollup()

    rows = [
        {
            "vendor_id": entry.vendor_id,
            "kind": entry.kind,
            "source": entry.source,
            **delivered.get(entry.vendor_id, NEVER_DELIVERED),
        }
        for entry in registered
    ]
    known = {entry.vendor_id for entry in registered}
    rows += [
        {"vendor_id": vendor_id, "kind": "unregistered", "source": None, **rollup}
        for vendor_id, rollup in delivered.items()
        if vendor_id not in known
    ]
    return {"adapters": sorted(rows, key=lambda row: row["vendor_id"])}
