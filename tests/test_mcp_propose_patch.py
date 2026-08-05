"""The fourth tool: run the real pipeline as far as static verification, then stop.

`docs/superpowers/specs/2026-07-25-sync-graph-surface-design.md` says `sync_propose_patch`
returns the diff, the static-verify result, and the evidence -- and that Sync returns patches
as data and never writes to the customer's repository. Stopping is therefore the behaviour
under test, not an implementation detail: the node after static verification is `push_branch`,
and reaching it would be the tool writing.

Nothing here reimplements the pipeline. The driver composes `sync.remediate.nodes`' own node
factories and its own routers, so what these tests exercise is the shipped pipeline truncated,
not a second copy of it that could drift.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from sync.core import CallSite, Finding, Patch, RepoRef, VendorChange, VerifyResult
from sync.mcp.propose import (
    BLOCKED,
    NO_PATCH_WARRANTED,
    PROPOSED,
    UNVERIFIED,
    run_to_static_verify,
)

INDEXED = datetime(2026, 7, 28, 6, 0, tzinfo=timezone.utc)

REPO = RepoRef(repo_id="r", url="https://example.invalid/r", local_path="/tmp/r", head_sha="0" * 40)


def _site() -> CallSite:
    return CallSite(
        id="site-1", repo_id="r", path="src/pay.ts", line=12, col=4, vendor_id="stripe",
        operation_id="PostCharges", symbol="stripe.charges.create",
        args_keys=["amount"], response_fields_read=["status"],
        sdk_version="18.0.0", content_hash="h", indexed_at=INDEXED,
    )


def _change() -> VendorChange:
    return VendorChange(
        id="chg-1", vendor_id="stripe", from_version="v1", to_version="v2",
        kind="response-property-removed", operation_id="PostCharges", path_ptr="/v1/charges",
        severity="breaking", source="oasdiff", raw={"id": "response-property-removed"},
    )


def _finding(rung: str = "static") -> Finding:
    """`binding_rung` is stated rather than defaulted, because the default is a value no row can
    hold: `GraphStore.insert_finding` refuses `unattributed`, so a fixture carrying it stands for
    nothing a detector can write."""
    return Finding(
        id="f-1", detector="vendor_change", claim="response-field", call_site_id="site-1",
        vendor_change_id="chg-1",
        severity="breaking", rationale="response-property-removed on PostCharges",
        binding_rung=rung,
    )


class FakeStore:
    def get_call_site(self, call_site_id: str) -> CallSite:
        return _site()

    def get_vendor_change(self, change_id: str) -> VendorChange:
        if change_id is None:
            raise KeyError("no vendor change")
        return _change()


class FakeAdapter:
    """Records what the pipeline asked of the checkout, so a write would be visible."""

    def __init__(self, verdicts: list[VerifyResult]) -> None:
        self._verdicts = list(verdicts)
        self.calls: list[str] = []

    def prepare(self, repo: RepoRef) -> None:
        self.calls.append("prepare")

    def static_verify(self, repo: RepoRef, patch: Patch) -> VerifyResult:
        self.calls.append("static_verify")
        return self._verdicts.pop(0)


class FakeRemediator:
    def __init__(self, diffs: list[str]) -> None:
        self._diffs = list(diffs)
        self.calls: list[str] = []

    def propose(self, finding, change, site, repo, diagnostics="") -> Patch:
        self.calls.append("propose")
        return Patch(diff=self._diffs.pop(0), strategy="codemod", rationale="swap the literal")


def _run(*, verdicts, diffs, store=None):
    adapter = FakeAdapter(verdicts)
    remediator = FakeRemediator(diffs)
    state = run_to_static_verify(
        _finding(), REPO, store=store or FakeStore(), adapter=adapter, remediator=remediator
    )
    return state, adapter, remediator


def test_a_verified_patch_comes_back_proposed_with_its_diff():
    state, _, _ = _run(verdicts=[VerifyResult(ok=True)], diffs=["--- a/src/pay.ts\n+++ b/src/pay.ts\n"])
    assert state["preview_outcome"] == PROPOSED
    assert state["patch"].diff.startswith("--- a/src/pay.ts")
    assert state["verify_ok"] is True


def test_it_stops_at_static_verification_and_never_reaches_the_write():
    """The spec's hard boundary. `push_branch` is the next node and must not run.

    A pushed branch is the one irreversible thing this tool could do, so the assertion is
    on the executed node sequence rather than on a return value that a later refactor
    could keep true while the behaviour changed.
    """
    state, adapter, _ = _run(verdicts=[VerifyResult(ok=True)], diffs=["diff"])
    assert adapter.calls == ["prepare", "static_verify"]
    assert "branch" not in state
    assert "pr_url" not in state
    assert state.get("ci_url", "") == ""


def test_a_patch_that_fails_typechecking_retries_and_then_reports_unverified():
    """Three static attempts is the pipeline's own budget, honoured rather than restated."""
    state, adapter, remediator = _run(
        verdicts=[VerifyResult(ok=False, diagnostics="TS2339")] * 3,
        diffs=["diff-1", "diff-2", "diff-3"],
    )
    assert state["preview_outcome"] == UNVERIFIED
    assert remediator.calls == ["propose"] * 3
    assert adapter.calls == ["prepare", "static_verify", "static_verify", "static_verify"]
    assert "TS2339" in state["diagnostics"]


def test_a_retry_is_fed_the_diagnostics_from_the_attempt_before_it():
    """Otherwise the second attempt is the first one again, and the budget buys nothing."""
    seen: list[str] = []

    class Recording(FakeRemediator):
        def propose(self, finding, change, site, repo, diagnostics=""):
            seen.append(diagnostics)
            return super().propose(finding, change, site, repo, diagnostics=diagnostics)

    adapter = FakeAdapter([VerifyResult(ok=False, diagnostics="TS2339"), VerifyResult(ok=True)])
    run_to_static_verify(
        _finding(), REPO, store=FakeStore(), adapter=adapter,
        remediator=Recording(["diff-1", "diff-2"]),
    )
    assert seen[0] == ""
    assert "TS2339" in seen[1]


def test_a_finding_whose_change_cannot_be_loaded_is_blocked_rather_than_raising():
    """`locate` failing is an answer an agent can act on; a traceback is not."""

    class Broken(FakeStore):
        def get_vendor_change(self, change_id: str) -> VendorChange:
            raise KeyError("gone")

    state, adapter, remediator = _run(verdicts=[], diffs=[], store=Broken())
    assert state["preview_outcome"] == BLOCKED
    assert remediator.calls == []
    assert adapter.calls == []


def test_a_checkout_that_cannot_be_prepared_is_blocked_before_any_patch_is_attempted():
    """An install failure establishes nothing about the change, so no patch is claimed."""

    class Failing(FakeAdapter):
        def prepare(self, repo: RepoRef) -> None:
            self.calls.append("prepare")
            raise RuntimeError("pnpm not on PATH")

    adapter = Failing([])
    remediator = FakeRemediator([])
    state = run_to_static_verify(
        _finding(), REPO, store=FakeStore(), adapter=adapter, remediator=remediator
    )
    assert state["preview_outcome"] == BLOCKED
    assert remediator.calls == []
    assert "pnpm" in state["diagnostics"]


def test_a_remediator_that_produces_nothing_does_not_reach_verification():
    """An empty diff and a crashed remediator leave the same state, and neither is a patch.

    Producing nothing spends an attempt rather than ending the run: the remediator is asked
    again until the budget is gone. Verification is never reached, because there is nothing
    to verify -- and a no-op diff that reached it would typecheck clean and look like success.
    """
    state, adapter, remediator = _run(verdicts=[], diffs=["", "   ", "\n"])
    assert state["preview_outcome"] == UNVERIFIED
    assert remediator.calls == ["propose"] * 3
    assert adapter.calls == ["prepare"]
    assert state["patch"] is None


def test_verification_that_could_not_run_is_blocked_rather_than_retried():
    """An exception out of static_verify is an environment fault, not a bad patch.

    Spending the remaining attempts against the same broken toolchain buys nothing, and
    the pipeline's own router says so.
    """

    class Exploding(FakeAdapter):
        def static_verify(self, repo: RepoRef, patch: Patch) -> VerifyResult:
            self.calls.append("static_verify")
            raise RuntimeError("tsc not found")

    adapter = Exploding([])
    remediator = FakeRemediator(["diff-1"])
    state = run_to_static_verify(
        _finding(), REPO, store=FakeStore(), adapter=adapter, remediator=remediator
    )
    assert state["preview_outcome"] == BLOCKED
    assert adapter.calls == ["prepare", "static_verify"]
    assert remediator.calls == ["propose"]


def test_the_driver_needs_no_forge_at_all():
    """The strongest available proof that this tool cannot write.

    `push_branch`, `await_ci`, `open_pull_request` and `delete_branch` all live on `Forge`.
    A driver that never takes one cannot call any of them, whatever a later edit does to
    the routing below it.
    """
    import inspect

    assert "forge" not in inspect.signature(run_to_static_verify).parameters


def test_a_change_the_table_says_needs_no_patch_never_reaches_the_patch_node():
    """Tier -1 is an answer, not a failure to produce one.

    The routing matrix routes vendor documentation hygiene to `NO_PATCH`: no edit in a
    consumer repository resolves it. Running the patch node anyway would spend an agent
    call to produce nothing, and would claim an attempt the run never made.
    """
    lifecycle = VendorChange(
        id="chg-2", vendor_id="stripe", from_version="v1", to_version="v2",
        kind="sunset-deleted", operation_id="PostCharges", path_ptr="/v1/charges",
        severity="breaking", source="oasdiff", raw={"id": "sunset-deleted"},
    )

    class LifecycleStore(FakeStore):
        def get_vendor_change(self, change_id: str) -> VendorChange:
            return lifecycle

    adapter = FakeAdapter([])
    remediator = FakeRemediator([])
    state = run_to_static_verify(
        _finding(), REPO, store=LifecycleStore(), adapter=adapter, remediator=remediator,
        catalogue={"sunset-deleted": {"id": "sunset-deleted", "kind": "lifecycle"}},
    )
    assert state["preview_outcome"] == NO_PATCH_WARRANTED
    assert state["tier"] == -1
    assert remediator.calls == []


# -- the tool response, as opposed to the run behind it ------------------------------


class FakeGraph(FakeStore):
    def __init__(self, rung: str = "static") -> None:
        self._rung = rung

    def open_findings(self) -> list[Finding]:
        return [_finding(self._rung)]

    def all_vendor_changes(self, vendor_id: str) -> list[VendorChange]:
        return [_change()] if vendor_id == "stripe" else []


def _surface(*, verdicts, diffs, rung: str = "static", **kwargs):
    from sync.mcp.tools import GraphSurface

    return GraphSurface(
        FakeGraph(rung), repo=REPO, adapter=FakeAdapter(verdicts),
        remediator=FakeRemediator(diffs), **kwargs,
    )


def test_the_response_carries_the_three_fields_the_spec_names():
    surface = _surface(verdicts=[VerifyResult(ok=True, diagnostics="")], diffs=["--- a/x\n+++ b/x\n"])
    response = surface.propose_patch("f-1")
    assert response["diff"] == "--- a/x\n+++ b/x\n"
    assert response["static_verify"] == {"passed": True, "diagnostics": ""}
    assert set(response["evidence"]) == {"spec_diff", "changelog", "call_sites"}
    assert response["evidence"]["call_sites"] == ["src/pay.ts:12"]


def test_the_diff_is_returned_and_the_patched_source_is_not():
    """The one deliberate exception to "never return file contents", and only that far.

    The diff is the answer, so withholding it would make the tool pointless. Returning the
    file it applies to would hand back exactly the tokens the graph exists to save, so the
    response carries no source key beyond the diff itself.
    """
    surface = _surface(verdicts=[VerifyResult(ok=True)], diffs=["--- a/x\n+++ b/x\n+const a = 1;\n"])
    response = surface.propose_patch("f-1")
    assert response["diff"].startswith("--- a/x")
    assert set(response) & {"content", "source", "file_contents", "patched_source"} == set()


def test_the_evidence_claims_no_ci_run_because_none_happened():
    """`sync.core.Evidence` carries `ci_run_url`; an empty one here would report a run."""
    surface = _surface(verdicts=[VerifyResult(ok=True)], diffs=["diff"])
    assert "ci_run_url" not in surface.propose_patch("f-1")["evidence"]


def test_the_response_carries_provenance_and_context_savings_like_every_other_tool():
    surface = _surface(verdicts=[VerifyResult(ok=True)], diffs=["diff"])
    response = surface.propose_patch("f-1")
    assert response["binding_source"] == "static"
    assert response["indexed_at"] == INDEXED.isoformat()
    assert response["context_savings"] > 0


@pytest.mark.parametrize("rung", ["static", "resolved", "observed", "unresolved", "unattributed"])
def test_a_verified_patch_reports_the_rung_the_finding_it_patches_rests_on(rung: str):
    """The wired branch, which is a second `_envelope` call and needs its own cover.

    `propose_patch` returns early with `outcome: unavailable` on a read-only server, and
    `tests/test_mcp_provenance.py` covers that path; this is the one that ran the pipeline. Both
    answer about exactly one finding, so the envelope is the right place for the rung in both --
    and a patch an agent is told rests on a static read when the claim came from watched traffic
    is weighed wrongly in the direction that matters, since `observed` is the rung it trusts most.
    """
    surface = _surface(verdicts=[VerifyResult(ok=True)], diffs=["diff"], rung=rung)
    response = surface.propose_patch("f-1")

    assert response["outcome"] == PROPOSED
    assert response["binding_source"] == rung


def test_a_failed_typecheck_reports_the_verdict_rather_than_omitting_it():
    surface = _surface(verdicts=[VerifyResult(ok=False, diagnostics="TS2339")] * 3,
                       diffs=["d1", "d2", "d3"])
    response = surface.propose_patch("f-1")
    assert response["outcome"] == UNVERIFIED
    assert response["static_verify"]["passed"] is False
    assert "TS2339" in response["static_verify"]["diagnostics"]


def test_a_finding_the_graph_does_not_hold_answers_none():
    surface = _surface(verdicts=[], diffs=[])
    assert surface.propose_patch("f-does-not-exist") is None


def test_a_read_only_server_says_so_instead_of_raising():
    """A deployment with no checkout is a configuration, not a fault.

    The agent still gets the evidence it can have, and an outcome that tells it to stop
    asking rather than a traceback that tells it nothing.
    """
    from sync.mcp.propose import UNAVAILABLE
    from sync.mcp.tools import GraphSurface

    response = GraphSurface(FakeGraph()).propose_patch("f-1")
    assert response["outcome"] == UNAVAILABLE
    assert response["diff"] is None
    assert response["static_verify"] is None
    assert response["evidence"]["call_sites"] == ["src/pay.ts:12"]


def test_verification_that_never_ran_is_null_rather_than_a_failed_verdict():
    """`{"passed": false}` claims a typecheck happened and rejected the patch."""
    surface = _surface(verdicts=[], diffs=["", "", ""])
    response = surface.propose_patch("f-1")
    assert response["outcome"] == UNVERIFIED
    assert response["static_verify"] is None
