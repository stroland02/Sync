"""Replay between the typechecker and CI, where the spec puts it.

`docs/superpowers/specs/2026-07-26-sync-observed-contract-drift.md`:

    This sits between `tsc` and customer CI: stronger than typechecking (it exercises runtime
    behavior against the new shape), cheaper and earlier than CI.

The tier itself was built and tested in `tests/test_replay.py`; what is under test here is the
graph. So these drive whole runs and assert on the executed node sequence, which is the
assertion `tests/test_no_patch_route.py` argues for: a stage that ran and did nothing would
satisfy any test that only checked whether a pull request appeared.

Replay is real in every test below -- a Node process, the sandbox, the fixtures from
`tests/fixtures/replay/`. Stubbing it would leave the one thing this task adds untested, and
the two fixtures differ by a single line, so a stage wired to the wrong verdict cannot pass
both.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from sync.core import CallSite, Finding, Patch, RepoRef, VendorChange, VerifyResult
from sync.forge.github import PullRequest
from sync.remediate.graph import build_graph
from sync.remediate.state import MAX_STATIC_ATTEMPTS

FIXTURES = Path(__file__).parent / "fixtures" / "replay"
TARGET = "src/billing.ts"

# The new specification marks `status` nullable, so the synthesized mock sends the null. That
# is the case the tier exists to catch, and the two fixtures differ only in whether they
# survive it.
SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "status": {"type": "string", "nullable": True},
    },
}

SITE = CallSite(
    repo_id="r1", path=TARGET, line=9, col=23, vendor_id="stripe",
    operation_id="PostCharges", symbol="stripe.charges.create",
    args_keys=["amount", "currency"], response_fields_read=["id", "status"],
    sdk_version="18.0.0", content_hash="h1",
)
CHANGE = VendorChange(
    vendor_id="stripe", from_version="v1", to_version="v2",
    kind="response-optional-property-removed", operation_id="PostCharges",
    path_ptr="/v1/charges", severity="breaking", source="oasdiff",
    raw={"id": "response-optional-property-removed",
         "text": "removed the optional property `status` from the response"},
)
FINDING = Finding(
    id="f1", detector="vendor_change", call_site_id="cs1", vendor_change_id="vc1",
    severity="breaking", rationale="PostCharges may now answer with a null status",
)

PLAN = {
    "schema": SCHEMA,
    "export": "charge",
    "vendor_packages": ["stripe"],
    "arguments": [1000],
}


class StubStore:
    """Records every write so a test can assert one did not happen."""

    def __init__(self) -> None:
        self.statuses: list[tuple[str, str]] = []
        self.rows: list = []
        self.shapes_written: list = []

    def get_call_site(self, _id):
        return SITE

    def get_vendor_change(self, _id):
        return CHANGE

    def set_finding_status(self, finding_id, status):
        self.statuses.append((finding_id, status))

    def record_migration_outcome(self, outcome):
        self.rows.append(outcome)

    def observed_shapes(self, vendor_id, operation_id):
        return []

    def record_observed_shape(self, shape):
        self.shapes_written.append(shape)


@dataclass
class StubAdapter:
    """`static_verify` is a dial, because the ordering assertion needs it to fail."""

    ok: bool = True

    def prepare(self, repo) -> None:
        return None

    def static_verify(self, repo, patch) -> VerifyResult:
        if self.ok:
            return VerifyResult(ok=True)
        return VerifyResult(ok=False, diagnostics="src/billing.ts(9,3): error TS2339: nope")


@dataclass
class WritingRemediator:
    """Writes the fixture's source into the clone, which is what the patch node's real
    remediators do -- `property_omit` edits the file and returns the diff describing it.

    Without the write there is nothing for replay to execute, and a stage tested against a
    diff nobody applied would prove only that the node ran.
    """

    body: str
    strategy: str = "agent"
    calls: int = 0

    def can_handle(self, finding, change) -> bool:
        return True

    def propose(self, finding, change, site, repo, diagnostics="") -> Patch:
        self.calls += 1
        (Path(repo.local_path) / TARGET).write_text(self.body, encoding="utf-8")
        return Patch(diff="--- a\n+++ b\n", strategy=self.strategy, rationale="fix")


@dataclass
class StubForge:
    pushes: int = 0
    pr_url: str | None = None
    deleted: list = field(default_factory=list)

    def push_branch(self, repo, patch) -> str:
        self.pushes += 1
        return "sync/fix-1"

    def await_ci(self, repo, branch) -> tuple[bool, str]:
        return True, "https://github.com/o/r/actions/runs/1"

    # Returns what the forge created, number and URL, since the merge webhook joins a
    # delivery to a corpus row by number and nothing else durable links the two.
    def open_pull_request(self, repo, branch, evidence) -> PullRequest:
        self.pr_url = "https://github.com/o/r/pull/1"
        return PullRequest(number=1, url=self.pr_url)

    def delete_branch(self, repo, branch) -> tuple[bool, str]:
        self.deleted.append(branch)
        return True, "deleted"


def _body(fixture: str) -> str:
    return (FIXTURES / fixture / TARGET).read_text(encoding="utf-8")


@pytest.fixture()
def clone(tmp_path: Path) -> RepoRef:
    """A clone holding the unpatched source. The remediator overwrites it, as a real one does."""
    shutil.copytree(FIXTURES / "handles", tmp_path, dirs_exist_ok=True)
    return RepoRef(
        repo_id="r1", url="https://example.invalid/r",
        local_path=str(tmp_path), head_sha="0" * 40,
    )


def _drive(repo: RepoRef, fixture: str, *, plan=PLAN, static_ok: bool = True):
    """Run one finding and return the executed node sequence beside the final state.

    `stream_mode="updates"` yields one mapping per node that ran, keyed by node name, so the
    sequence is the thing itself rather than a proxy for it.
    """
    store = StubStore()
    remediator = WritingRemediator(body=_body(fixture))
    forge = StubForge()
    graph = build_graph(
        store=store, adapter=StubAdapter(ok=static_ok), remediator=remediator,
        forge=forge, checkpointer=InMemorySaver(),
    )
    config = {"configurable": {"thread_id": "t1"}}
    payload = {"finding": FINDING, "repo": repo}
    if plan is not None:
        payload["replay_plan"] = plan

    sequence: list[str] = []
    for update in graph.stream(payload, config=config, stream_mode="updates"):
        sequence.extend(update.keys())

    return sequence, graph.get_state(config).values, store, forge


# --- the gate, in both directions -------------------------------------------------


def test_a_patch_that_mishandles_the_new_shape_does_not_reach_ci(clone: RepoRef) -> None:
    """The assertion the spec asks for, on the node sequence rather than on the absence of a
    pull request. `tsc` passes this patch -- the SDK type still carries `status` -- so without
    replay in the graph it reaches CI, and a suite with no test over the call lets it merge."""
    sequence, state, _, forge = _drive(clone, "mishandles")

    assert "replay" in sequence
    assert "push_branch" not in sequence
    assert "await_ci" not in sequence
    assert forge.pr_url is None
    assert state["replay_outcome"] == "threw"


def test_a_patch_that_handles_the_new_shape_reaches_ci(clone: RepoRef) -> None:
    """Second, so a stage that blocked everything could not satisfy the test above."""
    sequence, state, _, forge = _drive(clone, "handles")

    assert sequence[:6] == [
        "locate", "prepare", "patch", "static_verify", "replay", "push_branch",
    ]
    assert forge.pr_url is not None
    assert state["replay_outcome"] == "passed"
    assert state["replay_ok"] is True


def test_a_replay_failure_is_retried_rather_than_abandoned_on_the_first_round(
    clone: RepoRef,
) -> None:
    """A replay failure means this patch is wrong, which is what the retry loop is for -- the
    same distinction `route_after_static` draws between a failed typecheck and an environment
    fault. It spends the static-attempt budget and only then abandons."""
    sequence, state, store, _ = _drive(clone, "mishandles")

    assert sequence.count("replay") == MAX_STATIC_ATTEMPTS
    assert sequence.count("patch") == MAX_STATIC_ATTEMPTS
    assert sequence[-1] == "abandon"
    assert state["outcome"] == "abandoned"
    assert "replay" in state["abandon_reason"].lower()


# --- ordering: replay costs a sandboxed execution, so it runs on nothing tsc rejected ---


def test_a_patch_that_fails_the_typecheck_never_reaches_replay(clone: RepoRef) -> None:
    """Running the sandbox on a patch the compiler already rejected spends a process to
    discover something `tsc` said for free."""
    sequence, _, _, forge = _drive(clone, "handles", static_ok=False)

    assert "static_verify" in sequence
    assert "replay" not in sequence
    assert forge.pushes == 0


# --- not running is not passing ---------------------------------------------------


def test_replay_declining_is_distinguishable_from_replay_passing(clone: RepoRef) -> None:
    """The test that stops the gate from silently opening.

    A run with no plan cannot execute the call path, and that must be recorded as *not
    verified by replay* rather than as verified. It still reaches CI -- replay is an
    additional tier, not a precondition -- but nothing may later read the run as though the
    patched path had been exercised.
    """
    sequence, state, _, forge = _drive(clone, "handles", plan=None)

    assert "replay" in sequence
    assert "push_branch" in sequence
    assert forge.pr_url is not None
    assert state["replay_outcome"] == "not-attempted"
    assert state["replay_ok"] is False


def test_an_unresolvable_export_declines_rather_than_failing_the_patch(clone: RepoRef) -> None:
    """Nothing ran, so this is not a verdict on the patch and must not spend a retry."""
    plan = {**PLAN, "export": "noSuchExport"}
    sequence, state, _, forge = _drive(clone, "handles", plan=plan)

    assert sequence.count("patch") == 1
    assert state["replay_outcome"] == "declined"
    assert state["replay_ok"] is False
    assert forge.pr_url is not None


def test_the_evidence_line_says_what_replay_established_and_no_more(clone: RepoRef) -> None:
    """The spec promises a reviewer a sentence they can read. It must not overclaim: replay
    proves the patched path consumed the mocked shape, not that the application works."""
    _, passed, _, _ = _drive(clone, "handles")
    _, declined, _, _ = _drive(clone, "handles", plan=None)

    assert "mock" in passed["replay_evidence"].lower()
    assert "not" in declined["replay_evidence"].lower()
    assert declined["replay_evidence"] != passed["replay_evidence"]


# --- the shapes are carried, never written ----------------------------------------


def test_the_offered_shapes_are_carried_and_not_written(clone: RepoRef) -> None:
    """They describe the mock the code was exercised against, not traffic a vendor sent. In
    the store beside real observations they would have the drift detector comparing reality
    against a mock Sync itself built, which is worse than an empty baseline."""
    _, state, store, _ = _drive(clone, "handles")

    assert store.shapes_written == []
    carried = {shape["field_path"]: shape for shape in state["replay_shapes"]}
    assert carried["/id"]["source"] == "replay"
    assert carried["/status"]["nullable_seen"] is True
