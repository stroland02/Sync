"""Unit tests for the CLI's testable seams: argument parsing, findings
selection, and the store-truncation-before-scan ordering. `run()` is mostly
wiring against Postgres, the network, and the Agent SDK -- none of which a
unit test may touch -- so the order test below replaces every one of those
collaborators with an in-memory stub that never leaves this process.
"""

import argparse
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import TypedDict

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from sync.cli import (
    _checkout_branch,
    _declared_response_fields,
    _detector_suite,
    _parameter_deprecations,
    _scan,
    _clone,
    _repo_id,
    _reset_clone,
    _select,
    _thread_to_invoke,
    main,
    run,
)
from sync.core import CallSite, Finding, Patch, RepoRef, VendorChange, VerifyResult
from sync.forge.github import PullRequest
from sync.core.protocols import Detector
from sync.forge.github import GitHubForge
from sync.graph.store import GraphStore
from sync.signals import registry

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")


def test_no_arguments_exits_nonzero_instead_of_crashing(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["sync"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code != 0


REQUIRED_RUN_FLAGS = {
    "--from-version": "v2320",
    "--to-version": "v2330",
    "--repo": "https://example.invalid/r",
}


@pytest.mark.parametrize("omitted_flag", sorted(REQUIRED_RUN_FLAGS))
def test_run_missing_any_single_required_argument_exits_nonzero(monkeypatch, omitted_flag):
    """Each of the three flags is independently `required=True`. A test that
    omits all three at once cannot tell that apart from omitting just one --
    it would stay green even if only one flag's `required=True` were dropped,
    since the other two still trigger the same argparse error. Parametrizing
    over one omission at a time pins each flag on its own.

    `cli.run` is stubbed before `main()` runs. If a future edit drops
    `required=True` from the omitted flag, argparse would otherwise dispatch
    to the real `run()`, whose second line fetches a Stripe spec over the
    network -- exactly the live call CLAUDE.md forbids a unit test from
    making. The stub makes that path inert regardless of what regresses:
    argparse still raises `SystemExit` before `func` is ever consulted when
    the flags are actually required, so the stub changes nothing about what
    a correctly-required parser does.
    """
    import sync.cli as cli

    monkeypatch.setattr(cli, "run", lambda args: 0)

    argv = ["sync", "run"]
    for flag, value in REQUIRED_RUN_FLAGS.items():
        if flag != omitted_flag:
            argv += [flag, value]
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code != 0


def test_limit_zero_selects_every_finding():
    findings = ["a", "b", "c"]
    assert _select(findings, 0) == findings


def test_limit_one_selects_only_the_first_finding():
    findings = ["a", "b", "c"]
    assert _select(findings, 1) == ["a"]


def test_limit_larger_than_the_findings_selects_all_of_them():
    findings = ["a", "b"]
    assert _select(findings, 5) == ["a", "b"]


class _RecordingStore:
    """Stands in for `GraphStore`: records the order its methods are called in,
    nothing else. No connection, no schema, no network."""

    def __init__(self):
        self.calls: list[str] = []

    @contextmanager
    def transaction(self):
        self.calls.append("begin")
        yield
        self.calls.append("commit")

    def apply_schema(self):
        self.calls.append("apply_schema")

    def truncate_signal_and_detect(self):
        self.calls.append("truncate_signal_and_detect")

    def truncate_all(self):
        # Recorded rather than absent, so a scan that went back to emptying the whole database
        # fails on the assertion that names the property instead of on a missing attribute.
        self.calls.append("truncate_all")

    def replace_call_sites(self, repo_id, sites):
        self.calls.append("replace_call_sites")
        return [f"cs-{index}" for index, _ in enumerate(sites)]


    # The scan opens and closes an `index_run` row around the pass; a double that
    # indexes has to accept both, or the store surface it stands in for is a
    # narrower thing than the one the CLI actually calls.
    def start_index_run(self, repo_id, *, started_at):
        return None

    def finish_index_run(self, repo_id, *, started_at, finished_at, call_sites):
        return None
    def upsert_call_site(self, site):
        self.calls.append("upsert_call_site")

    def upsert_vendor_change(self, change):
        self.calls.append("upsert_vendor_change")

    def insert_finding(self, finding):
        self.calls.append("insert_finding")
        return "finding-id"


class _RecordingDetector:
    """Stands in for `VendorChangeDetector`: records that `scan()` ran, on the
    same call list the store records into, so ordering is comparable across both.

    `vendor_id` is accepted because the real detector has always taken it and the suite now
    builds one per deprecation vendor as well as one for Stripe. A stub narrower than the thing
    it stands for fails on a correct call, which is what this one did. `repo_id` is accepted for
    the same reason: a scan names the repository it is about, or it finds every customer's rows."""

    def __init__(self, store, vendor_id: str = "stripe", repo_id: str | None = None):
        self._store = store
        self._vendor_id = vendor_id
        self._repo_id = repo_id

    def scan(self):
        self._store.calls.append("scan")
        return []


_STUB_VENDOR_CHANGE = VendorChange(
    vendor_id="stripe", from_version="v1", to_version="v2",
    kind="response-property-removed", operation_id="PostCharges",
    path_ptr="/x/status", severity="breaking", source="oasdiff",
)

_STUB_CALL_SITE = CallSite(
    repo_id="repo", path="src/billing.ts", line=1, col=0, vendor_id="stripe",
    operation_id="PostCharges", symbol="stripe.charges.create",
    sdk_version="1.0.0", content_hash="hash",
)


class _StubVendor:
    vendor_id = "stripe"

    def __init__(self, spec_dir, symbol_map_path):
        pass

    def fetch_changes(self, from_version, to_version):
        return [_STUB_VENDOR_CHANGE]


class _StubAdapter:
    def discard_contaminated_dependencies(self, repo):
        return False

    def __init__(self, vendor_adapter):
        pass

    def matches(self, repo):
        return True

    def index(self, repo):
        return [_STUB_CALL_SITE]


def test_the_graph_is_truncated_after_apply_schema_and_before_the_scan(monkeypatch, tmp_path):
    """A previous invocation of `sync run` leaves rows behind -- the graph
    tables have no incremental story yet at M0 -- and a stale row is
    indistinguishable from a real finding to `VendorChangeDetector.scan()`.
    `run()` must wipe the graph tables after `apply_schema()` (schema must
    exist first) and *before the indexer writes into it* -- not merely
    "somewhere before scan()". `_StubAdapter.index` and `_StubVendor.fetch_changes`
    each yield one real `CallSite`/`VendorChange`, so an upsert actually happens
    between truncation and the scan; with both stubs returning nothing (as an
    earlier version of this test had them), truncating right before the
    findings loop -- after production's real upserts at `cli.py:80-83` have
    already written rows the detector would read -- passes the assertion just
    as well as the correct placement does, because no upsert call exists in
    the recorded order to catch the difference. That placement wipes every
    call site and vendor change before the detector reads them: every
    invocation reports "0 finding(s)" and exits 0 as if nothing had changed.

    Every collaborator `run()` normally wires up is replaced here: vendor
    selection with a stub adapter, `TypeScriptAdapter` with another, between
    them producing one real call site and vendor change, `_clone` with a
    fake `RepoRef`, `GraphStore` with an in-memory recorder. `VendorChangeDetector`
    is stubbed to report no findings regardless, so `run()` returns before ever
    touching `PostgresSaver` or the remediation graph, and neither needs a stub.
    """
    import sync.cli as cli

    store = _RecordingStore()

    def fake_clone(url, dest):
        return RepoRef(repo_id="repo", url=url, local_path=str(dest), head_sha="0" * 40)

    _stub_vendor_selection(monkeypatch, cli)
    monkeypatch.setattr(cli, "GraphStore", lambda dsn: store)
    monkeypatch.setattr(cli, "VendorChangeDetector", _RecordingDetector)
    monkeypatch.setattr(cli, "TypeScriptAdapter", _StubAdapter)
    monkeypatch.setattr(cli, "_clone", fake_clone)

    args = argparse.Namespace(
        vendor="stripe", from_version="v2320", to_version="v2330",
        repo="https://example.invalid/r", dsn="postgresql://unused",
        cache=str(tmp_path / "cache"), limit=1, run_id=None,
    )

    result = run(args)

    assert result == 0
    # The ordering, not the census. This pinned one `scan` entry and so counted detectors as a
    # side effect of asserting when the truncate happens; the suite now builds a
    # `VendorChangeDetector` per deprecation vendor as well, and how many there are is a
    # different test's business. The property in the name is preserved literally.
    assert store.calls[:3] == ["apply_schema", "begin", "truncate_signal_and_detect"]
    assert store.calls[-1] == "commit"
    assert store.calls.index("truncate_signal_and_detect") < store.calls.index("scan")
    assert store.calls.index("replace_call_sites") < store.calls.index("scan")
    assert store.calls.index("upsert_vendor_change") < store.calls.index("scan")
    # And the clear names what it empties rather than what it spares. A scan reaching
    # `truncate_all` empties the migration corpus and the repository context along with
    # everything else, which is what B129 measured; the ordering above holds either way.
    assert "truncate_all" not in store.calls


EQUIVALENT_URLS = [
    "https://github.com/acme/billing.git",
    "https://github.com/acme/billing",
    "https://github.com/acme/billing/",
    "http://GitHub.com/acme/billing.git",
    "git@github.com:acme/billing.git",
    "ssh://git@github.com/acme/billing.git",
    "ssh://git@github.com:2222/acme/billing.git",
    "https://x-access-token:ghs_secret@github.com/acme/billing.git",
]


@pytest.mark.parametrize("url", EQUIVALENT_URLS)
def test_every_spelling_of_one_remote_gets_one_repo_id(url):
    assert _repo_id(url) == "github.com/acme/billing"


def test_a_credential_in_the_url_never_reaches_the_repo_id():
    """`repo_id` is written to every `call_site` row and hashed into the branch
    name `GitHubForge` pushes. A token embedded in a clone URL must not travel
    with it."""
    assert "ghs_secret" not in _repo_id("https://x-access-token:ghs_secret@github.com/acme/billing.git")


@pytest.mark.parametrize(
    "left, right",
    [
        ("https://github.com/acme/billing", "https://github.com/other/billing"),
        ("https://github.com/acme/billing", "https://gitlab.com/acme/billing"),
        ("https://github.com/acme/billing", "https://github.com/acme/billing-web"),
    ],
)
def test_distinct_repositories_get_distinct_repo_ids(left, right):
    assert _repo_id(left) != _repo_id(right)


def test_clone_takes_repo_id_from_the_url_not_the_destination_directory(tmp_path):
    """Every clone lands in a directory named `repo`, so `dest.name` made
    `repo_id` the constant "repo" for every customer. Call site ids hash
    `repo_id`, which meant two repositories with a file at the same path
    calling the same symbol collapsed onto one row.

    Cloning a local repository keeps this off the network; `git` is local
    toolchain, which CLAUDE.md allows a test to use.
    """
    origin = tmp_path / "origin"
    origin.mkdir()
    git = ["git", "-c", "user.email=t@example.invalid", "-c", "user.name=t"]
    subprocess.run(["git", "init", "-q", str(origin)], check=True)
    subprocess.run(git + ["commit", "-q", "--allow-empty", "-m", "root"], cwd=origin, check=True)

    ref = _clone(str(origin), tmp_path / "workdir" / "repo")

    assert ref.repo_id != "repo"
    assert ref.repo_id == _repo_id(str(origin))
    assert len(ref.head_sha) == 40


class _ToyState(TypedDict, total=False):
    explode_at: str
    outcome: str


TOY_NODES = ("locate", "static_verify", "await_ci")


def _toy_graph(ran: list[str]):
    """A stand-in for the remediation graph, compiled against the same
    checkpointer contract, and carrying the real node names either side of the
    push. The point of testing `_thread_to_invoke` against a real compiled graph
    rather than a fake `get_state` is that the whole question is what LangGraph
    itself does with a finished versus an interrupted thread -- a fake would
    only assert what this file believes.
    """

    def make(name: str):
        def node(state: _ToyState) -> _ToyState:
            ran.append(name)
            if state.get("explode_at") == name:
                raise RuntimeError(f"the worker died in {name}")
            return {"outcome": "opened" if name == "await_ci" else "running"}

        return node

    builder = StateGraph(_ToyState)
    for name in TOY_NODES:
        builder.add_node(name, make(name))
    builder.add_edge(START, TOY_NODES[0])
    for earlier, later in zip(TOY_NODES, TOY_NODES[1:]):
        builder.add_edge(earlier, later)
    builder.add_edge(TOY_NODES[-1], END)
    return builder.compile(checkpointer=InMemorySaver())


def _invoke(graph, base, payload):
    thread_id, resuming = _thread_to_invoke(graph, base)
    return graph.invoke(
        None if resuming else payload,
        config={"configurable": {"thread_id": thread_id}},
    )


def test_a_finding_never_remediated_starts_a_fresh_first_generation():
    graph = _toy_graph([])
    assert _thread_to_invoke(graph, "f1:abc123") == ("f1:abc123:0", False)


def test_a_run_that_died_waiting_on_ci_resumes_its_own_thread():
    ran: list[str] = []
    graph = _toy_graph(ran)
    with pytest.raises(RuntimeError):
        _invoke(graph, "f1:abc123", {"explode_at": "await_ci"})

    assert _thread_to_invoke(graph, "f1:abc123") == ("f1:abc123:0", True)


def test_a_run_that_died_before_the_push_starts_over_instead_of_resuming():
    """Everything `await_ci` and `open_pr` need is in the branch a previous
    process pushed, so those resume. A run interrupted earlier left its patch in
    a temporary directory that died with it: resuming would typecheck a tree
    with none of the work in it, and commit an empty index. Redoing the run is
    the honest option, so the thread advances a generation instead.
    """
    ran: list[str] = []
    graph = _toy_graph(ran)
    with pytest.raises(RuntimeError):
        _invoke(graph, "f1:abc123", {"explode_at": "static_verify"})

    assert _thread_to_invoke(graph, "f1:abc123") == ("f1:abc123:1", False)


def test_resuming_replays_only_the_node_that_did_not_finish():
    """The durability the checkpointer exists for. `graph.invoke(payload, ...)`
    on an interrupted thread re-enters at START and redoes every node -- for
    the real graph that is a second agent run and a second pushed branch.
    Only `invoke(None, ...)` resumes the pending node, so the resume decision
    has to reach the invocation, not just the thread id.
    """
    ran: list[str] = []
    graph = _toy_graph(ran)
    with pytest.raises(RuntimeError):
        _invoke(graph, "f1:abc123", {"explode_at": "await_ci"})
    assert ran == ["locate", "static_verify", "await_ci"]

    ran.clear()
    graph.update_state({"configurable": {"thread_id": "f1:abc123:0"}}, {"explode_at": ""})
    state = _invoke(graph, "f1:abc123", {})

    assert ran == ["await_ci"]
    assert state["outcome"] == "opened"


def test_a_re_run_after_a_finished_run_does_the_work_again():
    """Finding ids are stable hashes and `head_sha` is unchanged on a re-run
    against the same customer commit, so the operator who fixes a broken
    environment and re-runs presents byte-identical coordinates. That must
    execute the graph, not replay the old verdict.
    """
    ran: list[str] = []
    graph = _toy_graph(ran)
    _invoke(graph, "f1:abc123", {})
    assert ran == list(TOY_NODES)

    ran.clear()
    thread_id, resuming = _thread_to_invoke(graph, "f1:abc123")

    assert (thread_id, resuming) == ("f1:abc123:1", False)
    _invoke(graph, "f1:abc123", {})
    assert ran == list(TOY_NODES)


def test_a_new_generation_starts_from_an_empty_state():
    """A finished thread is left alone rather than re-entered, so the second
    run cannot inherit the first run's keys. `patch`, `verify_ok` and
    `static_fatal` are all read by routing functions, and every one of them
    would otherwise arrive pre-set from a run that already ended.
    """
    ran: list[str] = []
    graph = _toy_graph(ran)
    _invoke(graph, "f1:abc123", {})

    thread_id, _ = _thread_to_invoke(graph, "f1:abc123")
    assert graph.get_state({"configurable": {"thread_id": thread_id}}).values == {}


GIT_IDENTITY = ["-c", "user.email=t@example.invalid", "-c", "user.name=t"]


def _git(cwd, *args: str) -> str:
    return subprocess.run(
        ["git", *GIT_IDENTITY, *args], cwd=cwd, check=True,
        capture_output=True, text=True, encoding="utf-8",
    ).stdout.strip()


def _origin_repo(tmp_path):
    origin = tmp_path / "origin"
    origin.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(origin)], check=True)
    (origin / "billing.ts").write_text("original\n", encoding="utf-8")
    (origin / "refunds.ts").write_text("original\n", encoding="utf-8")
    (origin / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
    _git(origin, "add", "-A")
    _git(origin, "commit", "-q", "-m", "root")
    return origin


def _finish_a_finding(work, branch: str, content: str) -> None:
    """What `GitHubForge.push_branch` leaves in the clone, minus the push:
    HEAD on the branch it created, with the patch committed on top."""
    (work / "billing.ts").write_text(content, encoding="utf-8")
    _git(work, "checkout", "-q", "-B", branch)
    _git(work, "add", "-u")
    _git(work, "commit", "-q", "-m", "fix: finding 1")


def test_the_next_finding_starts_from_the_commit_that_was_cloned(tmp_path):
    """`push_branch` runs `git checkout -B`, so it leaves HEAD on the branch it
    pushed with the patch committed. One clone is reused for every finding, so
    without a reset finding 2's agent starts from finding 1's tip: its branch
    carries finding 1's commit as a parent, its pull request shows both diffs,
    and its CI verifies a combination neither finding proposed.
    """
    origin = _origin_repo(tmp_path)
    repo = _clone(str(origin), tmp_path / "work" / "repo")
    work = Path(repo.local_path)
    _finish_a_finding(work, "sync/api-drift-aaaa", "patched by finding 1\n")

    _reset_clone(repo)

    assert _git(work, "rev-parse", "HEAD") == repo.head_sha
    assert (work / "billing.ts").read_text(encoding="utf-8") == "original\n"


def test_an_abandoned_finding_leaves_nothing_for_the_next_one_to_commit(tmp_path):
    """The sharper half. An abandoned finding never reaches `push_branch`, so
    its edits stay in the tree uncommitted -- and `push_branch` stages with
    `git add -u`, which would sweep them into the next finding's commit. That
    puts work no gate ever passed into a pull request describing something else.
    """
    origin = _origin_repo(tmp_path)
    repo = _clone(str(origin), tmp_path / "work" / "repo")
    work = Path(repo.local_path)
    (work / "billing.ts").write_text("half-finished patch that failed tsc\n", encoding="utf-8")

    _reset_clone(repo)

    assert (work / "billing.ts").read_text(encoding="utf-8") == "original\n"
    assert _git(work, "status", "--porcelain") == ""


def test_the_reset_removes_untracked_files_the_agent_left_behind(tmp_path):
    origin = _origin_repo(tmp_path)
    repo = _clone(str(origin), tmp_path / "work" / "repo")
    work = Path(repo.local_path)
    (work / "scratch.ts").write_text("export const x = 1\n", encoding="utf-8")

    _reset_clone(repo)

    assert not (work / "scratch.ts").exists()


def test_the_reset_keeps_the_dependency_install_the_previous_finding_paid_for(tmp_path):
    """`git clean` without `-x`, so ignored files survive. `prepare` installs
    the customer's dependencies with their own package manager, which is tens of
    seconds; deleting `node_modules` between findings would make the reset cost
    more than the clone it is protecting."""
    origin = _origin_repo(tmp_path)
    repo = _clone(str(origin), tmp_path / "work" / "repo")
    work = Path(repo.local_path)
    (work / "node_modules").mkdir()
    (work / "node_modules" / "stripe.js").write_text("module.exports = {}\n", encoding="utf-8")

    _reset_clone(repo)

    assert (work / "node_modules" / "stripe.js").exists()


def test_a_resumed_run_finds_the_clone_on_the_branch_the_dead_process_pushed(tmp_path):
    """A resumed run's checkpoint names a working copy that died with its
    temporary directory; the branch it pushed is the durable part. `await_ci`
    reads HEAD out of the clone to match CI runs against the commit it pushed,
    so a fresh clone sitting on the default branch would poll for the wrong sha
    and time out after half an hour.
    """
    origin = _origin_repo(tmp_path)
    first = _clone(str(origin), tmp_path / "first" / "repo")
    _finish_a_finding(Path(first.local_path), "sync/api-drift-bbbb", "patched\n")
    _git(Path(first.local_path), "push", "-q", "origin", "sync/api-drift-bbbb")
    pushed_sha = _git(Path(first.local_path), "rev-parse", "HEAD")

    restarted = _clone(str(origin), tmp_path / "second" / "repo")
    _checkout_branch(restarted, "sync/api-drift-bbbb")

    assert _git(Path(restarted.local_path), "rev-parse", "HEAD") == pushed_sha


class _TwoFindingStore:
    """`GraphStore` for a run with two findings. The remediation graph reads
    sites and changes back out of the store by id, so recording calls is not
    enough here -- the stub has to answer them."""

    def __init__(self, sites, change):
        self._sites = {site.id: site for site in sites}
        self._change = change
        self.statuses: list[tuple[str, str]] = []
        self.outcomes: list = []

    def record_migration_outcome(self, outcome) -> None:
        """`make_recorder` states this contract at construction, so a store without it fails
        `build_graph`. This stub drives the real graph and so owes the real write."""
        self.outcomes.append(outcome)

    @contextmanager
    def transaction(self):
        yield

    def apply_schema(self):
        pass

    def truncate_signal_and_detect(self):
        pass

    def replace_call_sites(self, repo_id, sites):
        return [site.id for site in sites]

    # The scan opens and closes an `index_run` row around the pass; a double that indexes has to
    # accept both, or the store surface it stands in for is narrower than the one the CLI calls.
    def start_index_run(self, repo_id, *, started_at):
        return None

    def finish_index_run(self, repo_id, *, started_at, finished_at, call_sites):
        return None

    def upsert_call_site(self, site):
        return site.id

    def upsert_vendor_change(self, change):
        return change.id

    def insert_finding(self, finding):
        return f"finding-{finding.call_site_id}"

    def get_call_site(self, call_site_id):
        return self._sites[call_site_id]

    def get_vendor_change(self, change_id):
        return self._change

    def set_finding_status(self, finding_id, status):
        self.statuses.append((finding_id, status))

    def repo_context(self, repo_id):
        # `run()` reads this once per run since the context-seeding task landed. No fixture
        # here carries a `.sync/context.md`, so a real store would also answer None.
        return None

    def upsert_repo_context(self, context) -> None:
        pass


class _EditingRemediator:
    """Stands in for the patch agent: edits the call site's file on disk and
    returns the diff, which is what `AgentRemediator` does. No model call."""

    def __init__(self, repo_context: str = "") -> None:
        # `build_remediator` now constructs the real `AgentRemediator` with this kwarg, and
        # this class replaces that constructor via `monkeypatch.setattr`, so it takes the same
        # argument -- unused, since this stand-in never builds a prompt.
        pass

    def propose(self, finding, change, site, repo, diagnostics=""):
        target = Path(repo.local_path) / site.path
        target.write_text(f"patched for {site.path}\n", encoding="utf-8")
        return Patch(diff=f"--- a/{site.path}\n+++ b/{site.path}\n", strategy="agent",
                     rationale=f"drop the removed field at {site.path}")


class _PassingAdapter:
    def discard_contaminated_dependencies(self, repo):
        return False

    def __init__(self, vendor_adapter=None):
        pass

    def matches(self, repo):
        return True

    def index(self, repo):
        return []

    def prepare(self, repo):
        return None

    def static_verify(self, repo, patch):
        return VerifyResult(ok=True)


class _MemoryCheckpointer(InMemorySaver):
    def setup(self):
        pass

    @classmethod
    @contextmanager
    def from_conn_string(cls, dsn):
        yield cls()


def test_two_findings_in_one_run_produce_branches_that_share_no_commits(tmp_path, monkeypatch):
    """The whole loop, with the real `push_branch` pushing to a local origin.

    One clone serves every finding. `push_branch` leaves HEAD on the branch it
    just pushed, so without a reset between findings the second branch is cut
    from the first one's tip: its pull request carries a commit from a finding
    nobody reviewing it asked about, and its CI verifies both patches together.
    Two branches that share a commit is the observable form of that, and it is
    what this asserts.
    """
    import sync.cli as cli

    origin = _origin_repo(tmp_path)
    base_sha = _git(origin, "rev-parse", "HEAD")

    sites = [
        CallSite(id=f"site-{name}", repo_id="r", path=f"{name}.ts", line=1, col=0,
                 vendor_id="stripe", operation_id="PostCharges", symbol="stripe.charges.create",
                 sdk_version="1.0.0", content_hash=name)
        for name in ("billing", "refunds")
    ]
    store = _TwoFindingStore(sites, _STUB_VENDOR_CHANGE)

    class _TwoFindingDetector:
        def __init__(self, store, vendor_id: str = "stripe", repo_id: str | None = None):
            # Scoped like the real detector. The suite builds one of these per deprecation
            # vendor too, and a stub that ignored `vendor_id` would answer the same two Stripe
            # findings three times over -- six findings in a test about two.
            self._vendor_id = vendor_id
            self._repo_id = repo_id

        def scan(self):
            if self._vendor_id != "stripe":
                return []
            return [
                Finding(detector="vendor_change", claim="response-field",
                        call_site_id=site.id, vendor_change_id="change-1",
                        severity="breaking", rationale=f"status removed at {site.path}")
                for site in sites
            ]

    def fake_fetch_spec(tag, dest):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("{}", encoding="utf-8")
        return dest

    class _LocalForge(GitHubForge):
        """The real `push_branch` -- the code under test here is what it leaves
        in the clone. Only the two steps that need GitHub are replaced."""

        def await_ci(self, repo, branch):
            return True, "https://ci.invalid/run/1"

        def open_pull_request(self, repo, branch, evidence):
            # Number and URL together: the corpus is joined to a merge delivery by number.
            return PullRequest(number=1, url=f"https://github.invalid/pull/{branch}")

    _stub_vendor_selection(monkeypatch, cli)
    monkeypatch.setattr(cli, "GraphStore", lambda dsn: store)
    monkeypatch.setattr(cli, "VendorChangeDetector", _TwoFindingDetector)
    monkeypatch.setattr(cli, "TypeScriptAdapter", _PassingAdapter)
    monkeypatch.setattr(cli, "AgentRemediator", _EditingRemediator)
    monkeypatch.setattr(cli, "GitHubForge", _LocalForge)
    monkeypatch.setattr(cli, "PostgresSaver", _MemoryCheckpointer)

    args = argparse.Namespace(
        vendor="stripe", from_version="v2320", to_version="v2330", repo=str(origin),
        dsn="postgresql://unused", cache=str(tmp_path / "cache"), limit=0, run_id=None,
    )

    assert run(args) == 0
    assert store.statuses == []

    branches = _git(origin, "for-each-ref", "--format=%(refname:short)", "refs/heads/sync").split()
    assert len(branches) == 2

    commits = [set(_git(origin, "rev-list", f"{base_sha}..{branch}").split()) for branch in branches]
    assert [len(c) for c in commits] == [1, 1]
    assert commits[0].isdisjoint(commits[1])


# --- the tier cascade the CLI hands to the graph ----------------------------------
#
# `build_graph` took `AgentRemediator()` directly, so nothing in `src/` ever constructed
# a `TieredRemediator`: the routing table routed, the cascade composed, and neither ran.
# The construction is pulled out of `run()` for the same reason `_select` is -- so the
# ordering is reachable without Postgres, the network, or the Agent SDK.


def test_the_cascade_puts_every_codemod_ahead_of_the_agent():
    """Cheapest first is the whole economic claim. An agent tier reached before a codemod
    that could have handled the finding spends ten minutes proving the codemod right."""
    from sync.cli import build_remediator
    from sync.remediate.tiered import TerminalTier

    tiers = build_remediator()._remediators
    terminal = [i for i, t in enumerate(tiers) if isinstance(t, TerminalTier)]

    assert terminal == [len(tiers) - 1], "the agent is not the last tier"
    assert all(t.strategy == "codemod" for t in tiers[:-1])


def test_the_agent_tier_is_terminal_so_nothing_narrows_what_reaches_it():
    """`nodes.make_patch` never consults `can_handle`, so today the agent handles every
    finding whatever its severity. A cascade that gated it would narrow the pipeline as a
    side effect of a change made for another reason."""
    from sync.cli import build_remediator

    agent_tier = build_remediator()._remediators[-1]
    unhandleable = Finding(detector="d", claim="c", call_site_id="cs", severity="info",
                           rationale="r")
    change = VendorChange(
        vendor_id="stripe", from_version="a", to_version="b", kind="whatever-this-is",
        operation_id="Op", path_ptr="/v1/x", severity="info", source="oasdiff", raw={},
    )

    assert agent_tier.can_handle(unhandleable, change) is True
    assert agent_tier.strategy == "agent"


def test_the_acceptance_finding_is_patched_without_reaching_the_agent(tmp_path):
    """The claim this task exists to make good on, through the wiring the CLI builds.

    The M0 acceptance run spent roughly ten minutes of `xhigh` model time on this exact
    finding. Nothing here constructs an Agent SDK client, so a cascade that fell through
    would fail rather than quietly cost money.
    """
    import shutil

    from sync.cli import build_remediator

    fixture = Path(__file__).parent / "fixtures" / "ts" / "two_payment_intents"
    clone = tmp_path / "clone"
    shutil.copytree(fixture, clone)

    change = VendorChange(
        vendor_id="stripe", from_version="v2300", to_version="v2345",
        kind="request-property-removed", operation_id="PostPaymentIntents",
        path_ptr="/v1/payment_intents", severity="breaking", source="oasdiff",
        raw={"id": "request-property-removed",
             "text": "removed the request property `receipt_email`"},
    )
    site = CallSite(
        repo_id="r", path="app/api/setup_accounts/route.ts", line=11, col=23,
        vendor_id="stripe", operation_id="PostPaymentIntents",
        symbol="stripe.paymentIntents.create",
        args_keys=["amount", "currency", "customer", "receipt_email"],
        response_fields_read=["id"], sdk_version="22.4.0-beta.1", content_hash="h",
    )
    repo = RepoRef(repo_id="r", url="u", local_path=str(clone), head_sha="s")

    patch = build_remediator().propose(
        Finding(detector="vendor_change", claim="request-field", call_site_id="cs",
                vendor_change_id="vc",
                severity="breaking", rationale="receipt_email removed"),
        change, site, repo,
    )

    assert patch.strategy == "codemod"
    assert "onboarding@example.com" in patch.diff
    assert "topup@example.com" not in patch.diff


def test_run_hands_the_graph_the_cascade_and_not_a_bare_agent(monkeypatch):
    """The wiring itself. `build_remediator` being correct is worth nothing if `run()`
    still constructs `AgentRemediator()` on its own."""
    import inspect

    import sync.cli as cli

    source = inspect.getsource(cli.run)
    # `build_remediator(` and not `build_remediator()`: the property is that `run()` does
    # not construct a remediator itself, and pinning the empty parentheses failed every
    # correct call that later needed an argument. A bare `AgentRemediator()` still fails.
    assert "build_remediator(" in source
    assert "AgentRemediator()" not in source


# --- the sdk document the symbol map's verbs come from ----------------------------
#
# `build_symbol_map` takes it as a second argument, so a `run()` that keeps calling
# with one argument leaves the whole derivation unreached while every unit test
# around it stays green -- the shape of the bug the cascade comment above records.

_SUBSCRIPTION_SPEC = {
    "paths": {"/v1/subscriptions/{subscription_exposed_id}": {"delete": {"operationId": "DeleteSubscription"}}}
}
_SUBSCRIPTION_SDK = {
    "paths": {"/v1/subscriptions/{subscription_exposed_id}": {"delete": {"x-stableId": "cancel_billing_subscription"}}}
}


def _stub_run_collaborators(monkeypatch, cli, store):
    """Everything a run touches except the vendor, which is now selected rather than named.

    The vendor moved out of here because `cli.py` no longer holds an adapter class to replace.
    A test that wants a stubbed vendor calls `_stub_vendor_selection` as well; the two below
    that assert what the staging derives deliberately do not, because the staging is the thing
    they are about.
    """
    monkeypatch.setattr(cli, "GraphStore", lambda dsn: store)
    monkeypatch.setattr(cli, "VendorChangeDetector", _RecordingDetector)
    monkeypatch.setattr(cli, "TypeScriptAdapter", _StubAdapter)
    monkeypatch.setattr(cli, "http_fetch", lambda url, **kw: "")
    monkeypatch.setattr(
        cli, "_clone",
        lambda url, dest: RepoRef(repo_id="repo", url=url, local_path=str(dest), head_sha="0" * 40),
    )


def _stub_vendor_selection(monkeypatch, cli):
    """Stand in for whichever adapter `--vendor` resolves to.

    Patched at the selection call rather than at an adapter class, because naming a class here
    is the defect `tests/test_vendor_registry.py` exists to hold shut -- and a stub that named
    one would keep passing after `cli.py` started importing it again. Which adapter a run
    selects is asserted there; these tests treat the vendor as a stubbed collaborator, the same
    way they treat the store.
    """
    from sync.signals.registry import PreparedVendor

    monkeypatch.setattr(
        cli, "prepare_vendor",
        lambda vendor_id, context: PreparedVendor(
            adapter=_StubVendor(spec_dir=context.cache_dir, symbol_map_path=None), documents=(),
        ),
    )


def _run_args(tmp_path):
    """The namespace argparse actually builds, `--vendor` default included. A helper that
    omitted a flag the parser always sets would let `run()` read one that is never absent in a
    real invocation and fail only here."""
    return argparse.Namespace(
        vendor="stripe", from_version="v2320", to_version="v2330",
        repo="https://example.invalid/r", dsn="postgresql://unused",
        cache=str(tmp_path / "cache"), limit=1, run_id=None,
    )


def test_the_run_builds_its_symbol_map_from_the_sdk_document(monkeypatch, tmp_path):
    """Asserted on the written map, not on whether `fetch_sdk_spec` was called.

    A run that fetched the document and then dropped it would record the call
    just as a correct one does. `DELETE /v1/subscriptions/{id}` is the operation
    the two derivations disagree about, so the map itself says which one ran.
    """
    import sync.cli as cli

    store = _RecordingStore()

    def fake_fetch_spec(tag, dest):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(_SUBSCRIPTION_SPEC), encoding="utf-8")
        return dest

    def fake_fetch_sdk_spec(tag, dest):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(_SUBSCRIPTION_SDK), encoding="utf-8")
        return dest

    monkeypatch.setattr(registry, "fetch_spec", fake_fetch_spec)
    monkeypatch.setattr(registry, "fetch_sdk_spec", fake_fetch_sdk_spec)
    _stub_run_collaborators(monkeypatch, cli, store)

    assert run(_run_args(tmp_path)) == 0

    symbols = json.loads((tmp_path / "cache" / "symbols.json").read_text(encoding="utf-8"))
    assert "stripe.subscriptions.cancel" in symbols
    assert "stripe.subscriptions.del" not in symbols


def test_the_run_completes_on_a_version_that_publishes_no_sdk_document(monkeypatch, tmp_path):
    """The path a stub will not exercise by accident.

    Stripe published `spec3.sdk.json` without a single `x-stableId` as recently
    as v1900, and `fetch_sdk_spec` answers None for a tag that has no document at
    all. Either way the run has to finish on the HTTP-verb derivation rather than
    abandon, so this asserts both that it returned and what it wrote -- a run
    that completed while silently writing an empty map would pass on the exit
    code alone.
    """
    import sync.cli as cli

    store = _RecordingStore()

    def fake_fetch_spec(tag, dest):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(_SUBSCRIPTION_SPEC), encoding="utf-8")
        return dest

    monkeypatch.setattr(registry, "fetch_spec", fake_fetch_spec)
    monkeypatch.setattr(registry, "fetch_sdk_spec", lambda tag, dest: None)
    _stub_run_collaborators(monkeypatch, cli, store)

    assert run(_run_args(tmp_path)) == 0

    symbols = json.loads((tmp_path / "cache" / "symbols.json").read_text(encoding="utf-8"))
    assert "stripe.subscriptions.del" in symbols
    assert "stripe.subscriptions.cancel" not in symbols


# --- every detector runs, and says how much it found ------------------------------


class _Silent:
    detector_id = "silent"

    def scan(self):
        return []


class _Broken:
    detector_id = "broken"

    def scan(self):
        raise RuntimeError("the vendor page could not be fetched")


class _Yields:
    def __init__(self, count: int, detector: str = "yields"):
        self._count = count
        self.detector_id = detector

    def scan(self):
        return [
            Finding(detector=self.detector_id, claim="response-field",
                    call_site_id=f"cs-{i}", severity="breaking",
                    rationale=f"finding {i}")
            for i in range(self._count)
        ]


class _InsertCountingStore:
    def __init__(self):
        self.inserted: list[Finding] = []

    def insert_finding(self, finding):
        self.inserted.append(finding)
        return f"id-{len(self.inserted)}"


def test_every_detector_reports_its_own_count(capsys):
    """A detector that silently produces nothing forever is indistinguishable from one that is
    broken, and that is the failure this wiring exists to end. The count is per detector, and a
    zero is printed rather than omitted -- an operator has to be able to see which one is quiet.
    """
    _scan([("vendor_change", _Yields(2)), ("parameter-deprecation", _Silent())], _InsertCountingStore())

    printed = capsys.readouterr().out
    assert "vendor_change: 2 finding(s)" in printed
    assert "parameter-deprecation: 0 finding(s)" in printed


def test_a_detector_that_raises_does_not_stop_the_others(capsys):
    """Losing one detector's findings is bad; losing the whole run because one input was missing
    is worse. A vendor page that cannot be fetched must cost its own findings and nothing else.
    """
    store = _InsertCountingStore()

    findings = _scan(
        [("broken", _Broken()), ("vendor_change", _Yields(3))], store
    )

    assert len(findings) == 3
    assert len(store.inserted) == 3
    assert "broken" in capsys.readouterr().err


def test_a_failed_detector_is_reported_rather_than_passed_over(capsys):
    """Swallowing the failure would make a broken detector look like a quiet one, which is the
    same confusion from the other direction."""
    _scan([("broken", _Broken())], _InsertCountingStore())

    assert "unavailable" in capsys.readouterr().err


def test_every_finding_reaches_the_store_through_one_path():
    """One `Finding` type, one insert, one remediation pipeline. A second write path is how two
    detectors end up with two different notions of what a finding is."""
    store = _InsertCountingStore()

    findings = _scan([("a", _Yields(2, "a")), ("b", _Yields(3, "b"))], store)

    assert len(store.inserted) == 5
    assert [f.id for f in findings] == ["id-1", "id-2", "id-3", "id-4", "id-5"]
    assert {f.detector for f in store.inserted} == {"a", "b"}


def test_the_suite_runs_every_detector(tmp_path):
    """The whole point. Three detectors exist, all satisfying the protocol, and exactly one was
    ever called -- the other two were finished work that could not produce a single finding."""
    store = GraphStore(DSN)
    store.apply_schema()

    suite = _detector_suite(
        store, spec_documents=(), call_sites=[], deprecations=[], vendor_id="stripe", repo_id="r",
    )

    assert [name for name, _ in suite] == [
        "vendor_change", "parameter-deprecation", "observed-drift", "status-rate", "efficiency",
    ]
    assert all(isinstance(detector, Detector) for _, detector in suite)


def test_an_empty_drift_baseline_produces_no_findings_and_does_not_error(tmp_path):
    """The normal case today: nothing has fed Sentry payloads in, so `observed_shape` is empty.
    That is not a fault, and a detector that raised on it would take the whole scan with it."""
    store = GraphStore(DSN)
    store.apply_schema()
    store.truncate_all()

    suite = _detector_suite(
        store, spec_documents=[_DRIFT_SPEC], call_sites=[], deprecations=[], vendor_id="stripe",
        repo_id="r",
    )
    drift = dict(suite)["observed-drift"]

    assert list(drift.scan()) == []


# --- what each detector needed that the CLI did not already have ------------------


_DRIFT_SPEC = {
    "paths": {
        "/v1/charges": {
            "post": {
                "operationId": "PostCharges",
                "responses": {
                    "200": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["status"],
                                    "properties": {
                                        "status": {"type": "string"},
                                        "amount": {"type": "integer", "nullable": True},
                                        "card": {
                                            "type": "object",
                                            "properties": {"brand": {"type": "string"}},
                                        },
                                    },
                                }
                            }
                        }
                    }
                },
            }
        }
    }
}


def test_declared_fields_are_derived_from_the_published_specification():
    """`ObservedDriftDetector` compares the baseline against what the vendor declares, and
    nothing in the repository turned a specification into declared fields -- the detector shipped
    with no way to be given its own input."""
    declared = _declared_response_fields(_DRIFT_SPEC)

    by_path = {field.field_path: field for field in declared["PostCharges"]}
    assert by_path["/status"].json_types == frozenset({"string"})
    assert by_path["/status"].required is True
    assert by_path["/amount"].nullable is True


def test_declared_fields_reach_into_nested_objects():
    """A vendor change is overwhelmingly nested, so a walker that stopped at the top level could
    only ever describe the shallowest fields the baseline records."""
    paths = {field.field_path for field in _declared_response_fields(_DRIFT_SPEC)["PostCharges"]}

    assert "/card/brand" in paths


def test_a_recursive_schema_terminates():
    """Stripe's specification refers to itself -- a charge carries a refund carrying a charge.
    An unbounded walk does not return, and a run that hangs before the detector even starts is
    worse than one that describes fields shallowly."""
    document = {
        "paths": {
            "/v1/self": {
                "get": {
                    "operationId": "GetSelf",
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/Node"}}
                            }
                        }
                    },
                }
            }
        },
        "components": {
            "schemas": {
                "Node": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "child": {"$ref": "#/components/schemas/Node"},
                    },
                }
            }
        },
    }

    paths = {field.field_path for field in _declared_response_fields(document)["GetSelf"]}

    assert "/name" in paths
    # Descended through the cycle rather than refusing it. `MAX_SCHEMA_DEPTH` is what makes the
    # walk terminate, and a `seen` set would terminate too while pruning this -- a field the
    # vendor really does return.
    assert "/child/name" in paths


def test_an_operation_with_no_response_schema_is_skipped():
    """A specification that describes no response body says nothing the baseline can be compared
    against, and inventing an empty declaration would report every observed field as undeclared.
    """
    document = {"paths": {"/v1/ping": {"get": {"operationId": "Ping", "responses": {"204": {}}}}}}

    assert _declared_response_fields(document) == {}


class _CountingFetch:
    def __init__(self, page: str = "", failing: bool = False):
        self.page = page
        self.failing = failing
        self.calls: list[str] = []

    def __call__(self, url: str) -> str:
        self.calls.append(url)
        if self.failing:
            raise RuntimeError("the vendor page is unreachable")
        return self.page


_PARAMETER_PAGE = """
| Parameter | Status | Replacement |
| --- | --- | --- |
| `max_tokens` | Deprecated (Claude Opus 4.7 and later) | `max_completion_tokens` |
"""


def test_parameter_deprecations_are_parsed_from_an_injected_fetch(tmp_path):
    """The adapter takes an injected fetch precisely so tests need no network. Nothing in this
    suite may reach a vendor's page."""
    fetch = _CountingFetch(page=_PARAMETER_PAGE)

    deprecations = _parameter_deprecations(tmp_path / "cache", fetch=fetch)

    assert fetch.calls
    assert any(item.parameter == "max_tokens" for item in deprecations)


def test_a_vendor_page_that_cannot_be_fetched_yields_no_deprecations_rather_than_raising(tmp_path, capsys):
    """The deprecation adapter raises on an unreachable page, because for that signal an empty
    answer is indistinguishable from a healthy vendor. Here the caller is a scan that also runs
    two other detectors, so the failure costs this detector's findings and nothing else -- and it
    is printed, because a silent zero is the confusion this task exists to end.
    """
    deprecations = _parameter_deprecations(tmp_path / "cache", fetch=_CountingFetch(failing=True))

    assert deprecations == []
    assert capsys.readouterr().err != ""


def test_a_cached_page_is_reused_rather_than_refetched(tmp_path):
    """A scan is not the only thing running against these pages, and a run that refetched two
    vendor pages every time would be rate-limited into the failure path above."""
    cache = tmp_path / "cache"
    _parameter_deprecations(cache, fetch=_CountingFetch(page=_PARAMETER_PAGE))

    second = _CountingFetch(page=_PARAMETER_PAGE)
    _parameter_deprecations(cache, fetch=second)

    assert second.calls == []
