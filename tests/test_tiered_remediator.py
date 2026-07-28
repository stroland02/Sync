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
from sync.remediate.tiered import TieredRemediator

FINDING = Finding(detector="d", call_site_id="cs", severity="breaking", rationale="r")
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
        Finding(detector="d", call_site_id="cs", severity="info", rationale="r"),
        unroutable, SITE, REPO,
    )
    assert patch.strategy == "agent"
    assert agent.proposed == 1
