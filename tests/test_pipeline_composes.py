"""The whole pipeline over a committed fixture repository, in the default suite.

`scripts/lint_dead_links.py` catches a component nothing reaches. It cannot catch the size up
from that: components that are each reachable and still do not compose. Nothing in the default
run drove INDEX through SIGNAL, DETECT, LOCATE, PATCH and verification in one pass -- the one
end-to-end test opens a real pull request against a real remote, so it is marked `e2e` and
deselected, correctly.

Where this stops, and why it cannot go further
----------------------------------------------
At the push boundary, by the same structural guarantee `sync.mcp.propose` relies on: this driver
never builds `push_branch`, `await_ci` or `open_pr`, which are the three nodes that hold a
`Forge`. There is nothing here to push with. `abandon` takes a forge parameter and never
dereferences it, because it touches one only to delete a branch a push created -- and no push
happens, which `test_no_run_here_ever_reaches_a_forge` asserts on the state rather than trusting.

A mocked `Forge` was available and is not used. A mock proves the code calls what it was told to
call; the absence of one proves the code cannot.

What is real and what is committed
----------------------------------
Real: the store, the schema, the node factories, the routers, `TieredRemediator`, the codemod,
`git`, and `tsc`. Committed: the vendor change, the call site, and the two project trees under
`tests/fixtures/pipeline/`. No vendor API and no model API is reached, and the agent tier is
armed to fail loudly rather than trusted not to fire.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from sync.benchmark import compute_axes
from sync.benchmark.report import render_report
from sync.cli import build_remediator
from sync.core import CallSite, Finding, RepoRef, VendorChange
from sync.graph.store import GraphStore
from sync.index.typescript import TypeScriptAdapter
from sync.remediate import nodes
from sync.remediate.corpus import make_recorder
from sync.remediate.literal_swap import LiteralSwapRemediator
from sync.remediate.state import MAX_STATIC_ATTEMPTS, RunState
from sync.remediate.tiered import TieredRemediator
from sync.signals.registry import SYMBOL_MAP_FILENAME, VendorContext, load_vendor

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")

FIXTURES = Path(__file__).parent / "fixtures" / "pipeline"

RETIRED = "claude-old-1"
REPLACEMENT = "claude-opus-9"

# What the whole pipeline is driven by: one retired model and one place that names it. Written
# here rather than mined from a vendor page, because what is under test is whether the stages
# compose over a change -- `tests/test_deprecations.py` is what proves the page parses into one.
CHANGE = VendorChange(
    vendor_id="anthropic", from_version="2026-07-01", to_version="2026-07-28",
    kind="deprecation/model-retired", operation_id=RETIRED, path_ptr="",
    severity="breaking", source="vendor-deprecation-table",
    raw={
        "model_id": RETIRED,
        "state": "retired",
        "replacement": REPLACEMENT,
        "retirement_date": "2026-08-05",
    },
)


@pytest.fixture()
def store() -> GraphStore:
    """A store holding only this test's rows.

    Truncated rather than assumed empty: several workers run migrations against their own
    databases in parallel, and a run that read another's rows would fail somewhere unrelated to
    what it was asserting.
    """
    store = GraphStore(DSN)
    store.apply_schema()
    with store.transaction():
        store.truncate_all()
    return store


@pytest.fixture(autouse=True)
def the_agent_never_runs(monkeypatch):
    """Arm the agent tier to fail loudly instead of trusting it not to fire.

    `CLAUDE.md` is unconditional that no test calls a model API. The production cascade holds
    `TerminalTier(AgentRemediator())` and reaches it whenever no codemod claims the change, so a
    fixture that drifted would spend a model call rather than fail -- which is the failure mode
    a rule stated once and never enforced always has.
    """
    def refuse(self, prompt, repo_path, identity):
        raise AssertionError("the pipeline reached the agent tier, which needs a model call")

    monkeypatch.setattr("sync.remediate.agent_patch.AgentRemediator._run_agent", refuse)


def _clone(tmp_path: Path, fixture: str, into: str | None = None) -> RepoRef:
    """A committed project tree, made into the git checkout the pipeline works in.

    Git is not decoration here: `static_verify` reduces the clone to the tree a push would carry
    by asking `git status`, so a directory that is not a repository fails before the compiler
    runs.
    """
    repo = tmp_path / (into or fixture)
    shutil.copytree(FIXTURES / fixture, repo)
    _git(["init", "-q", "-b", "main"], repo)
    _git(["add", "."], repo)
    _git(["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base"], repo)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo,
        capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout.strip()
    return RepoRef(
        repo_id="acme/billing", url="https://example.invalid/acme/billing",
        local_path=str(repo), head_sha=head,
    )


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(
        ["git", *args], cwd=cwd, check=True,
        capture_output=True, text=True, encoding="utf-8",
    )


def _seed(store: GraphStore, repo: RepoRef, path: str) -> Finding:
    """One call site and one vendor change in the graph, and the finding that joins them.

    Inserted through the store's own writers rather than by SQL, so the ids a finding addresses
    are the ids the graph will resolve -- `locate` reads both back, and a hand-written id would
    make this a test of the fixture rather than of the pipeline.
    """
    site = CallSite(
        repo_id=repo.repo_id, path=path, line=7, col=6, vendor_id=CHANGE.vendor_id,
        operation_id=RETIRED, symbol=RETIRED, sdk_version="unknown", content_hash="h1",
    )
    with store.transaction():
        site.id = store.upsert_call_site(site)
        change_id = store.upsert_vendor_change(CHANGE)
        finding = Finding(
            detector="parameter-deprecation", claim=f"parameter:{CHANGE.operation_id}",
            call_site_id=site.id, vendor_change_id=change_id,
            severity="breaking",
            rationale=f"{CHANGE.kind} on {RETIRED}: retired, replaced by {REPLACEMENT}",
            # What `ParameterDeprecationDetector` attributes. This fixture stands in for a real
            # finding travelling the real graph, so it carries the rung the real one would.
            binding_rung="static",
        )
        finding.id = store.insert_finding(finding)
    return finding


def _adapter(tmp_path: Path) -> TypeScriptAdapter:
    """The real index adapter over the real vendor adapter the registry resolves.

    The vendor adapter is unused on this path -- the graph asks the index adapter to prepare and
    to verify, never to index -- and it is built through `load_vendor` anyway rather than stubbed,
    because a stub here would be one more thing that composes in the test and not in a run.
    """
    cache = tmp_path / "cache"
    cache.mkdir(exist_ok=True)
    (cache / SYMBOL_MAP_FILENAME).write_text("{}", encoding="utf-8")
    vendor = load_vendor("stripe", VendorContext(cache_dir=cache, from_version="", to_version=""))
    return TypeScriptAdapter(vendor_adapter=vendor)


def _drive(finding: Finding, repo: RepoRef, store: GraphStore, adapter, remediator) -> RunState:
    """`locate -> prepare -> patch <-> static_verify -> replay`, and stop at the push boundary.

    The shipped node factories and the shipped routers, in the order `build_graph` wires them.
    Nothing here reimplements a stage: a second copy of the routing would drift from the pipeline
    it claims to exercise, and the copy being wrong is worse than not having one. What is left
    out is the three nodes that hold a `Forge`, which is the whole boundary.

    `record` is wired exactly as `build_graph` wires it -- built from the store, handed to
    `patch` and to `abandon` -- so the corpus rows below are written by the real recorder through
    the real writer.
    """
    record = make_recorder(store)
    locate = nodes.make_locate(store)
    prepare = nodes.make_prepare(adapter)
    patch = nodes.make_patch(remediator, record)
    static_verify = nodes.make_static_verify(adapter)
    replay = nodes.make_replay(store)
    # No forge, and none reachable: `abandon` touches one only to delete a branch a push created,
    # and this driver builds no node that can push. `test_no_run_here_ever_reaches_a_forge`
    # asserts that on the state rather than leaving it to this comment.
    abandon = nodes.make_abandon(store, forge=None, record=record)

    state: RunState = {"finding": finding, "repo": repo}

    state.update(locate(state))
    if nodes.route_after_locate(state) == "abandon":
        state.update(abandon(state))
        return state

    state.update(prepare(state))
    destination = nodes.route_after_prepare(state)
    if destination == "abandon":
        state.update(abandon(state))
        return state
    if destination == "report":
        state.update(nodes.make_report()(state))
        return state

    while True:
        state.update(patch(state))
        destination = nodes.route_after_patch(state)
        if destination == "abandon":
            state.update(abandon(state))
            return state
        if destination == "patch":
            continue

        state.update(static_verify(state))
        destination = nodes.route_after_static(state)
        if destination == "abandon":
            state.update(abandon(state))
            return state
        if destination == "patch":
            continue

        state.update(replay(state))
        destination = nodes.route_after_replay(state)
        if destination == "abandon":
            state.update(abandon(state))
            return state
        if destination == "patch":
            continue
        # `push_branch` is the decision, and this driver has nothing to push with.
        state["outcome"] = "verified"
        return state


def _verified_run(tmp_path, store):
    repo = _clone(tmp_path, "verified")
    finding = _seed(store, repo, "src/summarise.ts")
    return _drive(finding, repo, store, _adapter(tmp_path), build_remediator()), repo, finding


def _rejected_run(tmp_path, store):
    """The codemod-only cascade, and the reason it is not the production one.

    `TieredRemediator._eligible` sends a retry to the adaptive tiers, because a codemod re-run
    with feedback re-emits the byte-identical patch that just failed. So the production cascade's
    second attempt is an agent run, which is a model call, which this suite may not make. A
    cascade of one codemod falls back to itself instead, and the retry budget ends the loop --
    which is what makes the corpus's attempt grain observable offline at all.
    """
    repo = _clone(tmp_path, "rejected")
    finding = _seed(store, repo, "src/summarise.ts")
    remediator = TieredRemediator([LiteralSwapRemediator()])
    return _drive(finding, repo, store, _adapter(tmp_path), remediator), repo, finding


# --- a finding travels the whole way ----------------------------------------------


def test_a_finding_reaches_a_verified_patch_through_the_real_graph(tmp_path, store):
    """One pass, real stages. The retired literal is indexed as a call site, joined to a vendor
    change, routed to the tier-0 codemod, edited into the clone, and typechecked by a compiler
    that really ran -- and the assertion is on the file the gate measured, not on the diff the
    remediator rendered, because a patch that renders and does not land is the defect
    `literal_swap` and both parameter tiers each shipped once.
    """
    state, repo, _ = _verified_run(tmp_path, store)

    assert state["outcome"] == "verified"
    assert state["verify_ok"] is True
    source = Path(repo.local_path, "src", "summarise.ts").read_text(encoding="utf-8")
    assert REPLACEMENT in source
    assert RETIRED not in source


def test_no_run_here_ever_reaches_a_forge(tmp_path, store):
    """The boundary, asserted on what the run produced rather than on the driver's shape.

    `branch` is set only by a successful push and `pr_url` only by an opened pull request, so
    both being absent is the observable form of "nothing was pushed". The driver builds no node
    that could set either, which is why `abandon` can be handed no forge at all.
    """
    verified, _, _ = _verified_run(tmp_path, store)
    rejected, _, _ = _rejected_run(tmp_path, store)

    for state in (verified, rejected):
        assert state.get("branch") is None
        assert state.get("pr_url") is None


def test_a_verified_patch_writes_no_corpus_row_without_a_forge(tmp_path, store):
    """A composition finding, pinned here so it stays visible rather than living in a report.

    Only two nodes write a terminal row: `open_pr` and `abandon`. Both take a `Forge`, and only
    the first records a success -- so a run that verifies a patch and stops at the push boundary
    writes nothing at all, and the whole positive class of the corpus is unreachable from any
    test that does not push. `merge_rate` and cost-per-merged-patch follow it: both divide by
    pull requests, and neither can leave null without a network-touching run.

    That is not obviously wrong. A row describes a migration attempt that went somewhere, and
    `sync.mcp.propose` deliberately records nothing for a preview. It is stated because the
    consequence is easy to misread: an empty positive class in the default suite looks exactly
    like a pipeline that never succeeds.
    """
    state, _, finding = _verified_run(tmp_path, store)

    assert state["verify_ok"] is True
    assert [row for row in store.migration_outcomes() if row.finding_id == finding.id] == []


# --- the corpus ------------------------------------------------------------------


def test_the_corpus_grain_is_one_row_per_attempt_not_one_per_finding(tmp_path, store):
    """The mistake the discipline spec names first. One finding here makes three attempts --
    the codemod re-emits the same rejected patch until the budget ends it -- so a reader counting
    findings by counting rows is off by two, and this fails if the grain ever collapses.
    """
    state, _, finding = _rejected_run(tmp_path, store)

    rows = [row for row in store.migration_outcomes() if row.finding_id == finding.id]

    assert state["outcome"] == "abandoned"
    assert len(rows) == MAX_STATIC_ATTEMPTS
    assert {row.attempt_index for row in rows} == set(range(1, MAX_STATIC_ATTEMPTS + 1))
    assert len({row.finding_id for row in rows}) == 1


def test_the_row_records_the_tier_and_strategy_that_actually_fired(tmp_path, store):
    """Not a default. `attempt_strategy` is read off the patch the tier produced, and `tier` is
    derived from it, so a run that recorded a plausible constant instead would be
    indistinguishable in the corpus from one that measured anything.
    """
    _, _, finding = _rejected_run(tmp_path, store)

    rows = sorted(
        (row for row in store.migration_outcomes() if row.finding_id == finding.id),
        key=lambda row: row.attempt_index,
    )

    assert {row.strategy for row in rows} == {"codemod"}
    assert {row.tier for row in rows} == {0}
    assert {row.change_kind for row in rows} == {CHANGE.kind}

    # The compiler really ran, and the row carries what it said. `TS2322` is the assignment the
    # fixture's narrowed `SupportedModel` rejects, so this fails if the gate stopped compiling,
    # if the baseline started absorbing the error, or if the codemod stopped editing the file.
    assert rows[0].static_verify_passed is False
    assert rows[0].static_verify_error_class == "TS2322"

    # The two attempts after it never reached the gate, and the corpus says so by leaving the
    # verdict null rather than false. The codemod had already applied its only edit, so it
    # re-emitted an empty diff -- which `route_after_patch` sends back for another attempt until
    # the budget ends the run. A row reporting `False` here would claim a typecheck that never
    # happened.
    assert [row.static_verify_passed for row in rows[1:]] == [None, None]

    assert [row.terminal_status for row in rows] == ["retried", "retried", "abandoned"]
    assert rows[-1].abandon_reason


def test_the_recorder_writes_through_the_real_store_rather_than_merely_not_raising(tmp_path, store):
    """`corpus._record` reaches the writer through `getattr(store, "record_migration_outcome")`
    and logs a warning when it is absent, so a rename would stop recording silently and every
    axis would keep reporting null with nobody able to tell that from "no runs yet".

    Asserting the row came back out of Postgres is the only thing that separates those two.
    """
    _, _, finding = _rejected_run(tmp_path, store)

    assert any(row.finding_id == finding.id for row in store.migration_outcomes())


def test_re_running_the_same_finding_does_not_duplicate_its_rows(tmp_path, store):
    """Every stage converges on the same rows for the same input; `efcc19d` was this bug. The
    natural key is the finding and the attempt, so a second run over the same clone overwrites
    three rows rather than adding three more.
    """
    _, _, finding = _rejected_run(tmp_path, store)
    first = len(store.migration_outcomes())

    _drive(finding, _clone(tmp_path, "rejected", into="rejected-again"), store,
           _adapter(tmp_path), TieredRemediator([LiteralSwapRemediator()]))

    assert len(store.migration_outcomes()) == first


# --- the benchmark stops being plumbing -------------------------------------------


def test_the_benchmark_computes_a_real_number_over_rows_a_real_run_wrote(tmp_path, store):
    """The moment the reporting surface becomes a measurement. Every axis reported null over
    zero samples because no pipeline run had produced a row; these rows are the first.

    Asserted as a number with its sample size and against no threshold. There is no pass mark
    and inventing one is what the gates spec forbids in terms.
    """
    _rejected_run(tmp_path, store)

    axes = compute_axes(store.migration_outcomes())

    assert axes.routing_accuracy.value is not None
    assert axes.routing_accuracy.n >= 1
    assert axes.counts.attempts == MAX_STATIC_ATTEMPTS
    assert axes.counts.findings == 1
    # One finding, three attempts. An axis dividing by rows where it means findings is the
    # grain mistake again, arriving at the reporting end this time.
    assert axes.counts.attempts != axes.counts.findings


def test_the_rendered_report_carries_that_number_rather_than_unmeasured(tmp_path, store):
    """`sync benchmark` renders what the corpus holds, and until a run wrote a row it could only
    ever print `unmeasured` everywhere. This is the same renderer over real rows.
    """
    _rejected_run(tmp_path, store)

    report = render_report(store.migration_outcomes())

    routing = next(line for line in report.splitlines() if "routing accuracy" in line)
    assert "unmeasured" not in routing
    # One finding was routed to tier 0, which is the denominator -- not the three attempts it
    # made. Routing is a decision per finding, and dividing by attempts would let one stubborn
    # finding outvote three that succeeded first time.
    assert "n=1" in routing
