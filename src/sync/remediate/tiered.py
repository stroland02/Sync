"""Delegating a finding to the cheapest remediator that can actually do the job.

`make_patch` takes one remediator, so tiering is composition rather than a graph change. This
satisfies the same `Remediator` protocol and delegates to an ordered list, cheapest first, so
`graph.py`, `nodes.py`, and `state.py` need no edit -- and a later tier drops in without
touching them either.

Two decisions carry the design.

**An empty diff does not fall through.** A remediator that claimed the change owns the outcome.
Empty almost always means the file is already migrated, and falling through would spend an
agent run proving that on every already-correct repository.

**A retry skips the deterministic tiers.** `make_patch` feeds `diagnostics` back after a failed
verification, and a codemod ignores feedback by construction: re-running it re-emits the
byte-identical patch that just failed. The graph would loop to its attempt budget and abandon,
having spent the entire budget on one unchanging answer. A codemod gets one attempt; after that
the work belongs to something that can read the error.
"""

from __future__ import annotations

from typing import Sequence

from sync.core import CallSite, Finding, Patch, RepoRef, VendorChange

# Strategies whose output is a pure function of their input, so feedback cannot change it.
# Derived from `strategy` rather than a hand-kept registry, so a new codemod-style remediator
# is skipped on retry without anyone remembering to list it.
_DETERMINISTIC = frozenset({"codemod"})


def is_deterministic(remediator) -> bool:
    """Whether re-running this remediator with feedback could produce a different patch."""
    return getattr(remediator, "strategy", "") in _DETERMINISTIC


class TieredRemediator:
    """Tries each remediator in order and returns the first patch produced.

    `strategy` here is a label for the composite. The `Patch` carries the strategy of whichever
    delegate produced it, which is what `migration_outcome` splits merge rate by -- stamping the
    composite's own label would erase the distinction that split exists to measure.
    """

    strategy = "tiered"

    def __init__(self, remediators: Sequence) -> None:
        if not remediators:
            raise ValueError("TieredRemediator needs at least one remediator")
        self._remediators = list(remediators)

    def can_handle(self, finding: Finding, change: VendorChange) -> bool:
        return any(r.can_handle(finding, change) for r in self._remediators)

    def propose(
        self,
        finding: Finding,
        change: VendorChange,
        site: CallSite,
        repo: RepoRef,
        diagnostics: str = "",
    ) -> Patch:
        for remediator in self._eligible(diagnostics):
            if remediator.can_handle(finding, change):
                return remediator.propose(finding, change, site, repo, diagnostics=diagnostics)

        # Raising rather than returning an empty patch: `make_patch` catches exceptions and
        # routes to abandon carrying the message, whereas an empty diff is indistinguishable
        # from "already migrated" and would abandon without saying why.
        raise RuntimeError(f"no remediator can handle {change.kind} for {change.operation_id}")

    def _eligible(self, diagnostics: str) -> list:
        """The remediators worth trying for this attempt.

        On a retry the deterministic ones are dropped -- unless dropping them would leave
        nothing, since repeating a patch is still better than producing none and the graph's
        own attempt budget ends the loop either way.
        """
        if not diagnostics.strip():
            return self._remediators

        adaptive = [r for r in self._remediators if not is_deterministic(r)]
        return adaptive or self._remediators
