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


class CannotPatch(Exception):
    """Raised by a tier that accepted the change and then found it could not act.

    `can_handle` sees the finding and the change and never the call site, so a codemod
    scoped to a location cannot answer there. Whether the property is at that position,
    whether the argument is an object literal, whether a spread makes the property set
    unknowable -- all of it is only knowable once the file is read.

    An empty diff cannot carry that answer, because this module gives empty the opposite
    meaning: a remediator that claimed the change owns the outcome, so empty abandons the
    run rather than falling through. Spelling a decline that way would abandon findings
    the agent could repair. So a decline is an exception, the cascade catches it, and the
    next tier gets the work.
    """


class NoTierApplies(RuntimeError):
    """No tier accepted the finding, so none ran and none has a strategy to record.

    Distinct from `TierFailed`, and the corpus needs them apart: "nothing was attempted"
    and "the agent tier ran and failed" are different facts, and squashing them loses
    exactly the signal `migration_outcome` exists to capture.
    """


class TierFailed(RuntimeError):
    """A tier accepted the finding, ran, and raised.

    Carries the strategy of the tier that failed. That attempt is a negative example, and
    the corpus splits merge rate by strategy -- the information exists here, so discarding
    it would be a choice rather than a limitation.

    The message keeps the original exception's class and text because `make_patch` renders
    it into `diagnostics`, and that string is the whole of what an operator sees on an
    abandoned run.
    """

    def __init__(self, strategy: str, cause: BaseException) -> None:
        super().__init__(f"{type(cause).__name__}: {cause}")
        self.tier_strategy = strategy


class TerminalTier:
    """The last tier in a cascade, which is never asked whether it can handle a finding.

    `nodes.make_patch` calls `propose()` directly and has never consulted `can_handle`, so
    the agent handles every finding today whatever its severity -- `AgentRemediator`'s own
    severity gate has no caller. Putting a cascade in front of it would make that gate live
    for the first time, narrowing what the pipeline repairs as a side effect of a change
    nobody made for that reason.

    Wrapping keeps the gate exactly as unenforced as it already is, and does it without
    editing a contract other tests pin. Only the terminal position is exempted, so a
    cascade of nothing but codemods still declines rather than forcing its last tier to
    guess.
    """

    def __init__(self, remediator) -> None:
        self._remediator = remediator

    @property
    def strategy(self) -> str:
        """The delegate's own label. `is_deterministic` reads this, and a wrapper
        reporting its own would make a wrapped codemod look adaptive and survive the
        retry skip that exists to stop it re-emitting a failed patch."""
        return getattr(self._remediator, "strategy", "")

    def can_handle(self, finding: Finding, change: VendorChange) -> bool:
        return True

    def propose(
        self,
        finding: Finding,
        change: VendorChange,
        site: CallSite,
        repo: RepoRef,
        diagnostics: str = "",
    ) -> Patch:
        return self._remediator.propose(finding, change, site, repo, diagnostics=diagnostics)


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
        declined: list[str] = []
        for remediator in self._eligible(diagnostics):
            if not remediator.can_handle(finding, change):
                continue
            try:
                return remediator.propose(finding, change, site, repo, diagnostics=diagnostics)
            except CannotPatch as exc:
                # Accepted the change, then read the call site and found it not mechanical.
                # The next tier gets the work; only the reason is carried forward, so a
                # cascade that declines all the way down still says why.
                declined.append(f"{getattr(remediator, 'strategy', '?')}: {exc}")
            except Exception as exc:
                # A tier that ran and failed. Re-raised carrying its strategy so the corpus
                # can record the attempt against the tier that made it rather than losing
                # the negative example.
                raise TierFailed(getattr(remediator, "strategy", ""), exc) from exc

        # Raising rather than returning an empty patch: `make_patch` catches exceptions and
        # routes to abandon carrying the message, whereas an empty diff is indistinguishable
        # from "already migrated" and would abandon without saying why.
        detail = f" ({'; '.join(declined)})" if declined else ""
        raise NoTierApplies(
            f"no remediator can handle {change.kind} for {change.operation_id}{detail}"
        )

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
