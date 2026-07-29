"""Choosing the cheapest remediator that can actually do the job.

`make_patch` takes one remediator, so tiering is composition rather than a graph change: this
satisfies the same `Remediator` protocol and delegates. No edit to `graph.py`, `nodes.py`, or
`state.py` is required, and a later tier drops in without touching them either.

The subtle requirement is the retry. `make_patch` feeds `diagnostics` back after a failed
verification, and a deterministic remediator ignores feedback by construction -- it would
re-emit the byte-identical patch that just failed, every round, until the attempt budget is
gone. A codemod gets one attempt; after that the work belongs to something that can read the
error.
"""

from __future__ import annotations

import pytest

from sync.core import CallSite, Finding, Patch, RepoRef, VendorChange
from sync.core.protocols import Remediator
from sync.remediate.tiered import (
    NoPatchWarranted,
    TieredRemediator,
    routing_facts,
)

FINDING = Finding(detector="d", claim="c", call_site_id="cs", severity="breaking",
                  rationale="r")
SITE = CallSite(
    repo_id="r", path="src/a.ts", line=1, col=0, vendor_id="anthropic",
    operation_id="claude-x", symbol="model", sdk_version="1", content_hash="h",
)
REPO = RepoRef(repo_id="r", url="u", local_path="/tmp/x", head_sha="s")
CHANGE = VendorChange(
    vendor_id="anthropic", from_version="a", to_version="b", kind="deprecation/model-retired",
    operation_id="claude-x", path_ptr="", severity="breaking",
    source="vendor-deprecation-table", raw={"model_id": "claude-x", "replacement": "claude-y"},
)


class Stub:
    """A remediator that records whether it was asked to work."""

    def __init__(self, strategy: str, handles: bool = True, diff: str = "d") -> None:
        self.strategy = strategy
        self._handles = handles
        self._diff = diff
        self.proposed = 0

    def can_handle(self, finding, change) -> bool:
        return self._handles

    def propose(self, finding, change, site, repo, diagnostics: str = "") -> Patch:
        self.proposed += 1
        return Patch(diff=self._diff, strategy=self.strategy, rationale=f"{self.strategy} ran")


def _tiered(*stubs: Stub) -> TieredRemediator:
    return TieredRemediator(list(stubs))


# --- delegation ------------------------------------------------------------------


def test_the_first_capable_remediator_wins():
    codemod, agent = Stub("codemod"), Stub("agent")
    patch = _tiered(codemod, agent).propose(FINDING, CHANGE, SITE, REPO)

    assert patch.strategy == "codemod"
    assert codemod.proposed == 1
    assert agent.proposed == 0, "the expensive tier ran even though the cheap one handled it"


def test_it_falls_through_when_the_cheap_tier_declines():
    codemod, agent = Stub("codemod", handles=False), Stub("agent")
    patch = _tiered(codemod, agent).propose(FINDING, CHANGE, SITE, REPO)

    assert patch.strategy == "agent"
    assert codemod.proposed == 0


def test_the_patch_carries_the_strategy_of_whoever_produced_it():
    """`migration_outcome` splits merge rate by strategy. A composite that stamped its own
    label would erase the only distinction that split exists to measure."""
    patch = _tiered(Stub("codemod"), Stub("agent")).propose(FINDING, CHANGE, SITE, REPO)
    assert patch.strategy == "codemod"


def test_an_empty_diff_does_not_fall_through():
    """A remediator that claimed the change owns the outcome.

    Empty means "nothing to do" -- most often the file is already migrated. Falling through
    would spend an agent run proving that, on every already-correct repository.
    """
    codemod, agent = Stub("codemod", diff=""), Stub("agent")
    patch = _tiered(codemod, agent).propose(FINDING, CHANGE, SITE, REPO)

    assert patch.diff == ""
    assert agent.proposed == 0


# --- the retry, which is where a deterministic tier becomes a trap -----------------


def test_a_retry_skips_the_deterministic_tier():
    """`diagnostics` is only non-empty after a verification failure.

    A codemod cannot read feedback, so re-running it re-emits the patch that just failed. The
    graph would loop to the attempt budget and abandon, having spent the whole budget on one
    unchanging answer.
    """
    codemod, agent = Stub("codemod"), Stub("agent")
    patch = _tiered(codemod, agent).propose(FINDING, CHANGE, SITE, REPO, diagnostics="TS2345: nope")

    assert patch.strategy == "agent"
    assert codemod.proposed == 0


def test_the_first_attempt_still_uses_the_cheap_tier():
    codemod, agent = Stub("codemod"), Stub("agent")
    _tiered(codemod, agent).propose(FINDING, CHANGE, SITE, REPO, diagnostics="")

    assert codemod.proposed == 1


def test_a_retry_with_only_a_deterministic_tier_still_produces_something():
    """Degrading to no patch at all would be worse than repeating one. With nothing else
    available the codemod runs, and the graph's own attempt budget ends the loop."""
    codemod = Stub("codemod")
    patch = _tiered(codemod).propose(FINDING, CHANGE, SITE, REPO, diagnostics="boom")

    assert patch.strategy == "codemod"
    assert codemod.proposed == 1


# --- protocol and edges ----------------------------------------------------------


def test_can_handle_is_true_when_any_tier_can():
    assert _tiered(Stub("codemod", handles=False), Stub("agent")).can_handle(FINDING, CHANGE) is True


def test_can_handle_is_false_when_none_can():
    assert _tiered(Stub("codemod", handles=False), Stub("agent", handles=False)).can_handle(FINDING, CHANGE) is False


def test_no_capable_tier_raises_rather_than_returning_a_silent_no_op():
    """`make_patch` catches exceptions and routes to abandon with the message as diagnostics.

    An empty patch here would be indistinguishable from "already migrated" and would abandon
    without saying why.
    """
    with pytest.raises(RuntimeError, match="no remediator"):
        _tiered(Stub("codemod", handles=False)).propose(FINDING, CHANGE, SITE, REPO)


def test_it_requires_at_least_one_tier():
    with pytest.raises(ValueError):
        TieredRemediator([])


def test_it_satisfies_the_remediator_protocol():
    assert isinstance(_tiered(Stub("agent")), Remediator)


def test_a_deterministic_tier_is_identified_by_its_strategy():
    """Which tiers are deterministic is derived from `strategy`, not from a hand-kept list, so
    a new codemod-style remediator is skipped on retry without anyone remembering to add it."""
    from sync.remediate.tiered import is_deterministic

    assert is_deterministic(Stub("codemod")) is True
    assert is_deterministic(Stub("agent")) is False


# --- composed with the real codemod, which is the point ---------------------------


def test_a_deprecation_is_handled_without_the_agent(tmp_path):
    """The economic claim, end to end: a retired model costs no tokens."""
    from sync.remediate.literal_swap import LiteralSwapRemediator

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.ts").write_text('const m = "claude-x";\n', encoding="utf-8")
    repo = RepoRef(repo_id="r", url="u", local_path=str(tmp_path), head_sha="s")

    agent = Stub("agent")
    patch = TieredRemediator([LiteralSwapRemediator(), agent]).propose(FINDING, CHANGE, SITE, repo)

    assert patch.strategy == "codemod"
    assert "claude-y" in patch.diff
    assert agent.proposed == 0


def test_a_spec_change_still_reaches_the_agent(tmp_path):
    """The codemod knows only deprecations. Everything else must pass straight through, or
    adding a tier would have narrowed what the pipeline can repair."""
    from sync.remediate.literal_swap import LiteralSwapRemediator

    repo = RepoRef(repo_id="r", url="u", local_path=str(tmp_path), head_sha="s")
    spec_change = VendorChange(
        vendor_id="stripe", from_version="a", to_version="b",
        kind="response-property-removed", operation_id="PostCharges",
        path_ptr="/v1/charges", severity="breaking", source="oasdiff", raw={},
    )

    agent = Stub("agent")
    patch = TieredRemediator([LiteralSwapRemediator(), agent]).propose(FINDING, spec_change, SITE, repo)

    assert patch.strategy == "agent"
    assert agent.proposed == 1


# --- declining mid-propose, which can_handle cannot express ----------------------
#
# `can_handle` sees the finding and the change, never the call site. A codemod scoped to a
# location cannot know until it reads the file whether the property is there, whether the
# argument is an object literal, or whether a spread makes the property set unknowable.
# Those are declines, and an empty diff cannot carry them: the tier reads empty as
# ownership, so a decline spelled that way would abandon a finding the agent could fix.


class Declining:
    """A tier that accepts the change and then finds it cannot act."""

    def __init__(self, strategy: str = "codemod") -> None:
        self.strategy = strategy
        self.proposed = 0

    def can_handle(self, finding, change) -> bool:
        return True

    def propose(self, finding, change, site, repo, diagnostics: str = "") -> Patch:
        from sync.remediate.tiered import CannotPatch

        self.proposed += 1
        raise CannotPatch("the argument is not an object literal")


def test_a_tier_that_declines_mid_propose_falls_through():
    from sync.remediate.tiered import CannotPatch  # noqa: F401

    codemod, agent = Declining(), Stub("agent")
    patch = _tiered(codemod, agent).propose(FINDING, CHANGE, SITE, REPO)

    assert patch.strategy == "agent"
    assert codemod.proposed == 1, "the declining tier was never given the chance to try"


def test_an_empty_diff_still_does_not_fall_through():
    """The distinction this rests on. Empty means "already correct" and keeps its
    ownership semantics; declining is a separate signal with a separate spelling."""
    codemod, agent = Stub("codemod", diff=""), Stub("agent")
    patch = _tiered(codemod, agent).propose(FINDING, CHANGE, SITE, REPO)

    assert patch.diff == ""
    assert agent.proposed == 0


def test_every_tier_declining_raises_rather_than_returning_nothing():
    from sync.remediate.tiered import CannotPatch

    with pytest.raises((RuntimeError, CannotPatch)):
        _tiered(Declining()).propose(FINDING, CHANGE, SITE, REPO)


# --- the terminal tier ------------------------------------------------------------
#
# `nodes.make_patch` calls propose() directly and never consults can_handle, so today the
# agent handles every finding whatever its severity. Putting a cascade in front of it would
# make AgentRemediator's severity gate live for the first time and narrow what the pipeline
# repairs. Wrapping keeps that gate exactly as unenforced as it is now, without editing a
# contract other tests pin.


def test_a_terminal_tier_is_never_asked_whether_it_can_handle():
    from sync.remediate.tiered import TerminalTier

    refuses = Stub("agent", handles=False)
    patch = _tiered(Stub("codemod", handles=False), TerminalTier(refuses)).propose(
        FINDING, CHANGE, SITE, REPO
    )

    assert patch.strategy == "agent"
    assert refuses.proposed == 1


def test_a_terminal_tier_keeps_the_strategy_of_what_it_wraps():
    """`is_deterministic` reads `strategy`, and a wrapper reporting its own label would
    make a wrapped codemod look adaptive and survive the retry skip."""
    from sync.remediate.tiered import TerminalTier, is_deterministic

    assert TerminalTier(Stub("agent")).strategy == "agent"
    assert is_deterministic(TerminalTier(Stub("codemod"))) is True


def test_a_terminal_tier_does_not_hide_the_patch_its_delegate_produced():
    from sync.remediate.tiered import TerminalTier

    patch = _tiered(TerminalTier(Stub("agent", diff="real"))).propose(FINDING, CHANGE, SITE, REPO)
    assert patch.diff == "real"
    assert patch.strategy == "agent"


def test_the_wired_cascade_sends_an_unroutable_change_to_the_agent():
    """The property this wiring exists to preserve: adding tiers must not narrow what the
    pipeline repairs. A change no codemod claims still reaches the agent, and so does one
    whose severity AgentRemediator.can_handle would refuse."""
    from sync.remediate.literal_swap import LiteralSwapRemediator
    from sync.remediate.property_omit import PropertyOmitRemediator
    from sync.remediate.tiered import TerminalTier

    agent = Stub("agent", handles=False)
    cascade = TieredRemediator(
        [LiteralSwapRemediator(), PropertyOmitRemediator(), TerminalTier(agent)]
    )
    unroutable = VendorChange(
        vendor_id="stripe", from_version="a", to_version="b",
        kind="request-body-media-type-removed", operation_id="PostCharges",
        path_ptr="/v1/charges", severity="info", source="oasdiff", raw={},
    )

    patch = cascade.propose(
        Finding(detector="d", claim="c", call_site_id="cs", severity="info", rationale="r"),
        unroutable, SITE, REPO,
    )
    assert patch.strategy == "agent"
    assert agent.proposed == 1


# --- the decision table selects the tier -----------------------------------------
#
# Until this existed the table in `sync.route.matrix` was decorative: the tier a finding got
# was decided by which remediator happened to be first in a list, and `route()` was never
# consulted. Two things followed. Tier -1 -- the 21 lifecycle rules where no edit in a
# consumer repository resolves anything -- had no effect, so a lifecycle finding still reached
# a remediator that would try to patch it. And the row that decided did not exist to record,
# which is what left "tier 0 was wrong for this change kind" unanswerable.

LIFECYCLE_RULE = {
    "id": "sunset-deleted", "level": "error",
    "kind": "lifecycle", "action": "remove", "direction": "none",
}
RESPONSE_REMOVED_RULE = {
    "id": "response-property-removed", "level": "error",
    "kind": "existence", "action": "remove", "direction": "response",
}
REQUIREDNESS_RULE = {
    "id": "request-property-became-required", "level": "error",
    "kind": "requiredness", "action": "change", "direction": "request",
}
TYPE_RULE = {
    "id": "response-property-type-changed", "level": "error",
    "kind": "type", "action": "change", "direction": "response",
}
ADDED_REQUIRED_RULE = {
    "id": "new-required-request-property", "level": "error",
    "kind": "existence", "action": "add", "direction": "request",
}

CATALOGUE = {
    rule["id"]: rule
    for rule in (LIFECYCLE_RULE, RESPONSE_REMOVED_RULE, REQUIREDNESS_RULE, TYPE_RULE,
                 ADDED_REQUIRED_RULE)
}


def _change(kind: str, **over) -> VendorChange:
    fields = dict(
        vendor_id="stripe", from_version="a", to_version="b", kind=kind,
        operation_id="PostCharges", path_ptr="/v1/charges", severity="breaking",
        source="oasdiff", raw={"text": "removed the `status` property"},
    )
    fields.update(over)
    return VendorChange(**fields)


def _routed(*stubs: Stub, **kwargs) -> TieredRemediator:
    return TieredRemediator(list(stubs), catalogue=CATALOGUE, **kwargs)


def test_a_lifecycle_change_produces_no_patch():
    """Tier -1. `sunset-deleted` is a complaint about how the vendor documented a deprecation;
    no edit in a consumer's repository resolves it. Routing one to an agent produces a
    confident patch against code that was never wrong, which is the most expensive failure
    available -- it spends the reviewer trust the whole precision-over-recall position exists
    to protect.
    """
    agent = Stub("agent")

    with pytest.raises(NoPatchWarranted):
        _routed(Stub("codemod"), agent).propose(FINDING, _change("sunset-deleted"), SITE, REPO)

    assert agent.proposed == 0


def test_a_lifecycle_change_is_not_even_asked_of_a_remediator():
    """Asserted on `can_handle` as well as `propose`. A tier that is consulted and declines is
    a different thing from one that is never reached, and only the second is what tier -1
    means."""
    codemod = Stub("codemod")
    asked: list[str] = []
    codemod.can_handle = lambda finding, change: bool(asked.append("codemod")) or True

    with pytest.raises(NoPatchWarranted):
        _routed(codemod, Stub("agent")).propose(FINDING, _change("sunset-deleted"), SITE, REPO)

    assert asked == []


def test_the_row_that_decided_is_reported():
    """The whole reason `route()` returns a row name alongside the tier. Without it,
    "tier 0 was wrong for this change kind" is an archaeology project rather than a query."""
    seen: list[tuple] = []
    remediator = _routed(
        Stub("agent"), on_route=lambda decision: seen.append((decision.tier, decision.row))
    )

    remediator.propose(FINDING, _change("response-property-type-changed"), SITE, REPO)

    assert seen == [(2, "type-change")]


def test_the_row_reaches_the_message_an_operator_sees():
    """`make_patch` renders the exception into `diagnostics`, which becomes `abandon_reason`.
    A tier -1 abandonment that did not say which row decided would be indistinguishable from
    every other abandonment."""
    with pytest.raises(NoPatchWarranted, match="lifecycle"):
        _routed(Stub("agent")).propose(FINDING, _change("sunset-deleted"), SITE, REPO)


def test_a_change_the_table_sends_to_the_agent_never_asks_the_codemods():
    """The table deciding, rather than the list order deciding. A type change is never
    mechanical, so the codemod is not offered it at all -- previously it was asked and
    declined, which reaches the same patch by a route that cannot be audited."""
    codemod = Stub("codemod")
    agent = Stub("agent")

    patch = _routed(codemod, agent).propose(
        FINDING, _change("response-property-type-changed"), SITE, REPO
    )

    assert patch.strategy == "agent"
    assert codemod.proposed == 0


def test_a_change_already_satisfied_at_the_call_site_produces_no_patch():
    """Row 5, and the reason the graph exists. A request property becoming required needs no
    patch when the call site already passes it; without the index this would be a needless
    pull request against correct code."""
    site = SITE.model_copy(update={"args_keys": ["status", "amount"]})

    with pytest.raises(NoPatchWarranted, match="already-satisfied"):
        _routed(Stub("agent")).propose(
            FINDING, _change("request-property-became-required"), site, REPO
        )


def test_the_same_change_still_routes_when_the_call_site_does_not_pass_it():
    """The other side of row 5. `args_keys` is what this call site passes, so a field absent
    from it is established as not passed rather than unknown -- and the finding must still be
    repaired."""
    site = SITE.model_copy(update={"args_keys": ["amount"]})

    patch = _routed(Stub("agent")).propose(
        FINDING, _change("request-property-became-required"), site, REPO
    )

    assert patch.strategy == "agent"


def test_a_templated_route_falls_to_the_agent():
    """Tier 1 has no remediator: `PatchStrategy` is a two-value Literal and nothing implements
    a constrained single-edit strategy. Falling to the agent is more expensive and correct;
    silently treating it as tier 0 would hand a codemod a change whose value it cannot know."""
    codemod = Stub("codemod")
    agent = Stub("agent")

    patch = _routed(codemod, agent).propose(
        FINDING, _change("new-required-request-property"), SITE, REPO
    )

    assert patch.strategy == "agent"
    assert codemod.proposed == 0


# --- what the facts can and cannot establish -------------------------------------


def test_the_facts_are_populated_from_what_the_call_site_knows():
    """`field_resolved` comes from `changed_field()` over the change's own text."""
    facts = routing_facts(_change("response-property-removed"), SITE)

    assert facts.field_resolved is True


def test_a_change_naming_no_field_is_established_as_unresolved():
    """oasdiff records frequently name no field at all, and that is not a defect. It is
    established knowledge, so it is `False` rather than unknown -- row 2 reads it to keep a
    codemod away from a field nobody can name."""
    facts = routing_facts(_change("response-property-removed", raw={}), SITE)

    assert facts.field_resolved is False


def test_the_facts_this_layer_cannot_establish_stay_unknown():
    """Absent evidence must never read as permission.

    A single call site cannot say how many sites across the graph read a field, so
    `call_sites_reading_field` is unknown however much source is in hand. The literal fact is
    unknown here for a narrower reason -- no clone was passed, so there is no source to read
    it off; `tests/test_tier_zero_reach.py` is where it is established from one. Both make
    the rows needing them decline rather than route work to a codemod on a guess.
    """
    facts = routing_facts(_change("response-property-removed"), SITE)

    assert facts.call_sites_reading_field is None
    assert facts.field_passed_as_literal is None


# --- the table's domain, and what lies outside it --------------------------------


def test_a_kind_the_catalogue_does_not_carry_keeps_the_cascade():
    """A deprecation's `kind` is `deprecation/model-retired`, not an oasdiff rule id, so the
    table has nothing to say about it. Treating an absent record as "no row matched" would
    route every deprecation to the agent and switch off the one signal that costs no tokens.
    """
    codemod = Stub("codemod")

    patch = _routed(codemod, Stub("agent")).propose(FINDING, CHANGE, SITE, REPO)

    assert patch.strategy == "codemod"
    assert codemod.proposed == 1


def test_no_catalogue_keeps_the_cascade_exactly_as_it_was():
    """The table cannot decide without the rule metadata it keys on. A remediator built
    without a catalogue behaves as it did before routing existed, which is what keeps this
    change from silently disabling tier 0 wherever the catalogue is not wired."""
    codemod = Stub("codemod")

    patch = _tiered(codemod, Stub("agent")).propose(
        FINDING, _change("response-property-type-changed"), SITE, REPO
    )

    assert patch.strategy == "codemod"


def test_routing_still_skips_the_deterministic_tier_on_a_retry():
    """The retry rule survives routing. A codemod re-run with feedback re-emits the
    byte-identical patch that just failed, so a retry belongs to something that can read the
    error -- whatever tier the table picked."""
    codemod = Stub("codemod")
    agent = Stub("agent")

    patch = _routed(codemod, agent).propose(
        FINDING, CHANGE, SITE, REPO, diagnostics="TS2304: Cannot find name"
    )

    assert patch.strategy == "agent"
    assert codemod.proposed == 0


def test_a_routed_tier_no_remediator_serves_falls_back_to_the_whole_cascade():
    """A cascade holding only codemods, handed a change the table sends to the agent. Nothing
    serves tier 2, and abandoning there would lose a finding on a composition detail rather
    than on anything about the change. The same reasoning the retry rule already carried:
    repeating a patch beats producing none, and the graph's attempt budget ends the loop
    either way.
    """
    codemod = Stub("codemod")

    patch = _routed(codemod).propose(
        FINDING, _change("response-property-type-changed"), SITE, REPO
    )

    assert patch.strategy == "codemod"


def test_a_caller_holding_the_graph_can_reach_tier_zero():
    """`call_sites_reading_field` is the one fact this layer cannot establish, and it gates the
    response-side mechanical row. That is the defaults working -- absent evidence must not read
    as permission -- and it is not a dead end: a caller that can count the call sites reading a
    field supplies the count and the codemod tier becomes reachable.
    """
    from sync.route.matrix import RoutingFacts

    codemod = Stub("codemod")
    agent = Stub("agent")
    remediator = TieredRemediator(
        [codemod, agent],
        catalogue=CATALOGUE,
        facts_for=lambda change, site, repo: RoutingFacts(
            field_resolved=True, call_sites_reading_field=1
        ),
    )

    patch = remediator.propose(FINDING, _change("response-property-removed"), SITE, REPO)

    assert patch.strategy == "codemod"
    assert agent.proposed == 0


def test_the_default_facts_leave_the_response_side_of_tier_zero_unreachable():
    """Stated as a test so the limitation is visible rather than folklore. The same change as
    above, with the facts this layer can actually establish, routes to the agent because the
    response-side row cannot be satisfied without a call-site count. The request-side row can
    be, and `tests/test_tier_zero_reach.py` drives it.
    """
    codemod = Stub("codemod")

    patch = _routed(codemod, Stub("agent")).propose(
        FINDING, _change("response-property-removed"), SITE, REPO
    )

    assert patch.strategy == "agent"
    assert codemod.proposed == 0
