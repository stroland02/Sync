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

**The decision table selects the tier, where it has jurisdiction.** `sync.route.matrix.route()`
assigns a tier to an oasdiff rule from the rule's own metadata, and until it was consulted here
the tier a finding got was decided by which remediator happened to be first in a list. Two
things followed from that: tier -1 had no effect, so a lifecycle finding still reached a
remediator that would try to patch it; and the row that decided did not exist to record, which
is what left "tier 0 was wrong for this change kind" unanswerable.

Jurisdiction is the qualification. `route()` keys on a catalogue record from
`run_oasdiff_checks()`, and `VendorChange.kind` holds that record's id only for oasdiff-sourced
changes. A deprecation's kind is `deprecation/model-retired`, which no catalogue carries.
Treating an absent record as "no row matched" would route every deprecation to the fall-through
agent and switch off the one signal that costs no tokens, so a kind the catalogue does not carry
is outside the table's domain and keeps the `can_handle` cascade. So does a remediator built
with no catalogue at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from sync.core import CallSite, Finding, Patch, RepoRef, VendorChange
from sync.route.matrix import CODEMOD, NO_PATCH, RoutingFacts, Tier, route
from sync.route.templates import argument_is_literal_at, language_for
from sync.signals.oasdiff import changed_field

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


class NoPatchWarranted(RuntimeError):
    """The table routed this finding to tier -1: no patch is justified.

    Distinct from `NoTierApplies`, which means every tier was offered the work and none took
    it. This one means the work was never offered, because no edit in a consumer's repository
    resolves the change. `kind=lifecycle` covers 21 of oasdiff's 212 breaking rules and every
    one of them is a complaint about how the vendor documented a deprecation --
    `sunset-deleted` describes a defect in the vendor's specification, and there is nothing in
    the customer's code to fix.

    Raised rather than returned as an empty patch, for the reason this module already gives
    empty diffs the opposite meaning. It answers a caller holding a `TieredRemediator`
    directly, which is where nothing has established a tier ahead of it. Inside the graph
    nothing catches it and nothing needs to: `locate` stores the tier and `route_after_prepare`
    sends tier -1 to `report` before `patch` runs, so the row that decided travels on
    `RunState["routing_row"]` and `make_report` renders it.

    This message must never reach `abandon_reason`. Abandonment means Sync tried and could not
    finish, and that field is where routing learns which change kinds are not mechanically
    safe; "this kind never needed a patch" written there corrupts exactly that signal.
    """

    def __init__(self, row: str, change: VendorChange) -> None:
        super().__init__(
            f"no patch is warranted for {change.kind} on {change.operation_id}: "
            f"routed to tier {NO_PATCH} by row '{row}'"
        )
        self.row = row


@dataclass(frozen=True)
class RoutingDecision:
    """What the table decided, and which row decided it.

    Reported through `on_route` because the row has nowhere else to go: `Patch` carries a
    strategy and no room for the row, and the state key the corpus reads is written by
    `nodes.make_patch`. Recording it into `migration_outcome` is one line in that node, which
    this module cannot write for itself.
    """

    tier: Tier
    row: str
    change_kind: str


def routing_facts(
    change: VendorChange, site: CallSite, repo: RepoRef | None = None
) -> RoutingFacts:
    """What this layer can establish about the change and the one call site it was given.

    `RoutingFacts` defaults every field to "not established" precisely so a row needing a fact
    declines when the fact is unknown, which is what stops an unpopulated graph routing work to
    a codemod. Three of the four are established here; the fourth is the open one.

    - `field_resolved` comes from the change's own text. A record naming no field is a real
      answer -- `False`, not unknown -- which is what row 2 reads to keep a codemod away from
      a field nobody can name.
    - `value_already_passed` comes from `args_keys`, which is what this call site passes.
    - `field_passed_as_literal` comes from the clone, when there is one. The index records
      which keys a call site passes and never how each was written, so this reads the call
      itself -- see `sync.route.templates.argument_is_literal_at`, which answers `None` for
      anything it cannot establish. Reading the source is not a second index: it is the same
      file the codemod is about to edit, parsed by the same scoping, so router and codemod
      cannot disagree about which call they mean.
    - `call_sites_reading_field` cannot be established here at all. It is a count across the
      whole graph -- how many *indexed* sites read the field -- and `propose` is handed one
      site with no reader for the rest. Row 3, the response-side mechanical row, therefore
      still declines, and a response-property removal still costs an agent run.

    `repo` is optional because `nodes.py` previews the route at `locate`, before a clone is
    necessarily in hand. Without it the literal fact stays unknown, so that preview can only
    ever name a tier at least as expensive as the one `propose` settles on -- a refinement,
    never a contradiction.
    """
    field = changed_field(change)
    return RoutingFacts(
        field_resolved=field is not None,
        value_already_passed=(field in set(site.args_keys)) if field is not None else None,
        field_passed_as_literal=_passed_as_literal(field, site, repo),
    )


def _passed_as_literal(field: str | None, site: CallSite, repo: RepoRef | None) -> bool | None:
    """The literal fact, or `None` wherever the source cannot settle it.

    Every failure here is `None` rather than `False`. A missing clone, a path the index has
    outlived, bytes that are not UTF-8, a suffix no grammar covers -- none of them is evidence
    about how the argument was written, and absent evidence must never read as permission.
    """
    if field is None or repo is None:
        return None

    language = language_for(site.path)
    if language is None:
        return None

    try:
        source = (Path(repo.local_path) / site.path).read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    # `CallSite.line` is 1-based off tree-sitter's `start_point` and ast-grep counts from
    # zero, the same conversion `property_omit` makes before the edit.
    return argument_is_literal_at(
        source, field, language=language, line=site.line - 1, col=site.col,
    )


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

    def __init__(
        self,
        remediators: Sequence,
        catalogue: Mapping[str, dict[str, Any]] | None = None,
        on_route: Callable[[RoutingDecision], None] | None = None,
        facts_for: Callable[[VendorChange, CallSite, RepoRef], RoutingFacts] | None = None,
    ) -> None:
        if not remediators:
            raise ValueError("TieredRemediator needs at least one remediator")
        self._remediators = list(remediators)
        self._catalogue = catalogue or {}
        self._on_route = on_route
        # A caller holding the graph can establish the one fact this layer cannot -- see
        # `routing_facts`, whose docstring says which and why. Row 3 cannot fire without it,
        # so the response side of tier 0 is unreachable through the default.
        self._facts_for = facts_for or routing_facts

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
        tier = self._tier_for(change, site, repo)
        for remediator in self._eligible(finding, change, diagnostics, tier):
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

    def _tier_for(self, change: VendorChange, site: CallSite, repo: RepoRef) -> Tier | None:
        """The tier the table assigns, or `None` where the table has no jurisdiction.

        `None` is not a tier and does not mean the fall-through. It means the change is
        outside the table's domain -- no catalogue was supplied, or the change's kind is not an
        oasdiff rule id -- and the cascade decides as it did before routing existed.

        Tier -1 raises here rather than returning, so no remediator is consulted at all. A tier
        that is asked and declines is a different thing from one that is never reached, and
        only the second is what tier -1 means.
        """
        rule = self._catalogue.get(change.kind)
        if rule is None:
            return None

        tier, row = route(rule, self._facts_for(change, site, repo))
        if self._on_route is not None:
            self._on_route(RoutingDecision(tier=tier, row=row, change_kind=change.kind))
        if tier == NO_PATCH:
            raise NoPatchWarranted(row, change)
        return tier

    def _serves(self, remediator, tier: Tier) -> bool:
        """Whether a remediator serves the tier the table picked.

        Tier is read off `strategy`, which is the same derivation `remediate.corpus` makes in
        the other direction -- which tier ran *is* which remediator produced the patch. Tier 1
        has no remediator: `PatchStrategy` is a two-value Literal and nothing implements a
        constrained single-edit strategy, so a templated route is served by the adaptive tier.
        That is more expensive and correct; treating it as tier 0 would hand a codemod a change
        whose value it cannot know.
        """
        if tier == CODEMOD:
            return is_deterministic(remediator)
        return not is_deterministic(remediator)

    def _eligible(
        self,
        finding: Finding,
        change: VendorChange,
        diagnostics: str,
        tier: Tier | None,
    ) -> list:
        """The remediators worth trying for this attempt.

        Routing narrows first, then the retry rule narrows again. Both survive: a codemod
        re-run with feedback re-emits the byte-identical patch that just failed, whatever tier
        the table picked for it.

        Neither filter is allowed to empty the list. A routed tier with no remediator serving
        it falls back to the whole cascade rather than abandoning a repairable finding on a
        composition detail -- the same reasoning the retry rule already carried, where
        repeating a patch beats producing none and the graph's attempt budget ends the loop
        either way.

        `can_handle` is part of the routing filter and not only of the loop below, which is
        the correction that came with row 4 becoming reachable. A tier-0 route narrows to the
        codemods, and when every one of them declines the change the narrowed list is not
        empty -- it is full of remediators that will each decline in turn, leaving the loop
        to raise `NoTierApplies` with the agent never asked. A routing decision would then
        have destroyed a repair rather than made one cheaper. Emptiness has to be measured
        over remediators that would actually take the work.
        """
        candidates = self._remediators
        if tier is not None:
            serving = [
                r for r in candidates
                if self._serves(r, tier) and r.can_handle(finding, change)
            ]
            candidates = serving or candidates

        if not diagnostics.strip():
            return candidates

        adaptive = [r for r in candidates if not is_deterministic(r)]
        return adaptive or candidates
