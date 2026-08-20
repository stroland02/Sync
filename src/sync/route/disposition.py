"""What will happen to a finding, decided before anything is run.

The decision table (`matrix.py`) assigns a tier to a change. This is the one step above it:
whether that tier is work Sync takes on by itself, or work that waits for a person. The tick
decided exactly this inline and printed the answer (`sync.watch.tick.classify`); the console
could not see it at all, because nothing persisted or served it. One derivation now answers
both, and `remediation_ticket.routing_row_at_open` records which row decided.

**Every answer here is a pre-clone bound.** `facts.routing_facts` establishes three of the
table's four inputs from graph rows alone; the fourth -- whether an argument is written as a
literal -- is read off a checkout, and only row 4 turns on it. So a disposition computed with
no clone can name a tier at least as expensive as the run settles on, never a cheaper one. The
error direction is a finding that waits for a person and could have been mechanical, which is
the direction the routing spec already chose for the fall-through.

**`no_jurisdiction` is not `no_patch`.** `decide_tier` returns `(None, None)` for both a missing
catalogue and a kind the catalogue does not carry, and this module is what tells them apart for a
screen: a deprecation's kind is `deprecation/model-retired`,
which no oasdiff catalogue carries, and folding that onto "no patch is warranted" would report
the one signal that costs no tokens as a finding nothing can fix.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from sync.core import CallSite, RepoRef, VendorChange
from sync.route.facts import routing_facts
from sync.route.matrix import CODEMOD, NO_PATCH, TEMPLATED, Tier, route

# Why a finding is, or is not, work Sync takes on by itself. Closed, because a screen renders
# it and an aggregate counts it -- free text can do neither. The values are outcomes of the
# routing table, not a second judgement layered over it.
DispositionCode = Literal[
    "mechanical",
    "needs_agent",
    "no_patch",
    "no_jurisdiction",
    "no_catalogue",
    "no_vendor_change",
]

AUTOMATIC_CODES: frozenset[str] = frozenset({"mechanical"})


@dataclass(frozen=True)
class Disposition:
    """One finding's route, and whether it waits for a person.

    `tier` and `routing_row` are `None` together and only together: either the table decided,
    or it had nothing to decide from. `code` says which of the three nothings that is.
    """

    code: DispositionCode
    tier: Tier | None
    routing_row: str | None
    reason: str

    @property
    def automatic(self) -> bool:
        """Whether Sync opens this without being asked."""
        return self.code in AUTOMATIC_CODES


def decide_tier(
    change: VendorChange,
    site: CallSite,
    catalogue: dict[str, Any] | None,
    repo: RepoRef | None = None,
) -> tuple[Tier | None, str | None]:
    """The tier the decision table assigns, and the row that assigned it.

    `(None, None)` means the table had no jurisdiction, which is not tier -1 and must not be
    treated as one -- `disposition` below is what tells the two apart for a caller that has to
    render or count them.
    """
    if not catalogue:
        return None, None
    rule = catalogue.get(change.kind)
    if rule is None:
        return None, None
    return route(rule, routing_facts(change, site, repo))


def disposition(
    change: VendorChange | None,
    site: CallSite | None,
    catalogue: dict[str, Any] | None,
    repo: RepoRef | None = None,
) -> Disposition:
    """What Sync will do about this finding, and why.

    `change`/`site` are optional because a finding need not join to a vendor change at all --
    `Finding.vendor_change_id` is nullable and the observed-drift and status-rate detectors
    raise findings that name none. That is `no_vendor_change`: nothing for the table to route,
    which is a fact about the detector rather than a failure to decide.
    """
    if change is None or site is None:
        return Disposition(
            code="no_vendor_change",
            tier=None,
            routing_row=None,
            reason="this finding names no vendor change, so the routing table has nothing to route",
        )
    if not catalogue:
        return Disposition(
            code="no_catalogue",
            tier=None,
            routing_row=None,
            reason="the routing table was not loaded, so no tier was assigned",
        )

    tier, row = decide_tier(change, site, catalogue, repo)
    if tier is None:
        return Disposition(
            code="no_jurisdiction",
            tier=None,
            routing_row=None,
            reason=f"the routing table has no jurisdiction over '{change.kind}'",
        )
    if tier in (CODEMOD, TEMPLATED):
        return Disposition(
            code="mechanical",
            tier=tier,
            routing_row=row,
            reason=f"row '{row}' routes this to a mechanical edit, which Sync takes on by itself",
        )
    if tier == NO_PATCH:
        return Disposition(
            code="no_patch",
            tier=tier,
            routing_row=row,
            reason=f"row '{row}' finds no patch is warranted in this repository",
        )
    # Everything left is the agent tier, including the fall-through, which `route` reports as
    # the row name rather than as a different tier -- so a reader is told the table did not
    # recognise the change without that becoming a fourth code nobody counts.
    return Disposition(
        code="needs_agent",
        tier=tier,
        routing_row=row,
        reason=f"row '{row}' routes this to the agent tier, which waits for a person to accept it",
    )
