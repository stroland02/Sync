"""Unit tests for the CLI's testable seams: argument parsing, findings
selection, and the store-truncation-before-scan ordering. `run()` is mostly
wiring against Postgres, the network, and the Agent SDK -- none of which a
unit test may touch -- so the order test below replaces every one of those
collaborators with an in-memory stub that never leaves this process.
"""

import argparse
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
    _clone,
    _repo_id,
    _reset_clone,
    _select,
    _thread_to_invoke,
    main,
    run,
)
from sync.core import CallSite, Finding, Patch, RepoRef, VendorChange, VerifyResult
from sync.forge.github import GitHubForge


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

    def truncate_all(self):
        self.calls.append("truncate_all")

    def upsert_call_site(self, site):
        self.calls.append("upsert_call_site")

    def upsert_vendor_change(self, change):
        self.calls.append("upsert_vendor_change")

    def insert_finding(self, finding):
        self.calls.append("insert_finding")
        return "finding-id"


class _RecordingDetector:
    """Stands in for `VendorChangeDetector`: records that `scan()` ran, on the
    same call list the store records into, so ordering is comparable across both."""

    def __init__(self, store):
        self._store = store

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

    Every collaborator `run()` normally wires up is replaced here: `fetch_spec`
    with a local file write, `StripeAdapter`/`TypeScriptAdapter` with stubs
    that each produce one real call site and vendor change, `_clone` with a
    fake `RepoRef`, `GraphStore` with an in-memory recorder. `VendorChangeDetector`
    is stubbed to report no findings regardless, so `run()` returns before ever
    touching `PostgresSaver` or the remediation graph, and neither needs a stub.
    """
    import sync.cli as cli

    store = _RecordingStore()

    def fake_fetch_spec(tag, dest):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("{}", encoding="utf-8")
        return dest

    def fake_clone(url, dest):
        return RepoRef(repo_id="repo", url=url, local_path=str(dest), head_sha="0" * 40)

    monkeypatch.setattr(cli, "fetch_spec", fake_fetch_spec)
    monkeypatch.setattr(cli, "GraphStore", lambda dsn: store)
    monkeypatch.setattr(cli, "VendorChangeDetector", _RecordingDetector)
    monkeypatch.setattr(cli, "StripeAdapter", _StubVendor)
    monkeypatch.setattr(cli, "TypeScriptAdapter", _StubAdapter)
    monkeypatch.setattr(cli, "_clone", fake_clone)

    args = argparse.Namespace(
        from_version="v2320", to_version="v2330", repo="https://example.invalid/r",
        dsn="postgresql://unused", cache=str(tmp_path / "cache"), limit=1, run_id=None,
    )

    result = run(args)

    assert result == 0
    assert store.calls == [
        "apply_schema", "begin", "truncate_all",
        "upsert_call_site", "upsert_vendor_change", "scan", "commit",
    ]


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

    @contextmanager
    def transaction(self):
        yield

    def apply_schema(self):
        pass

    def truncate_all(self):
        pass

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


class _EditingRemediator:
    """Stands in for the patch agent: edits the call site's file on disk and
    returns the diff, which is what `AgentRemediator` does. No model call."""

    def propose(self, finding, change, site, repo, diagnostics=""):
        target = Path(repo.local_path) / site.path
        target.write_text(f"patched for {site.path}\n", encoding="utf-8")
        return Patch(diff=f"--- a/{site.path}\n+++ b/{site.path}\n", strategy="agent",
                     rationale=f"drop the removed field at {site.path}")


class _PassingAdapter:
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
        def __init__(self, store):
            pass

        def scan(self):
            return [
                Finding(detector="vendor_change", call_site_id=site.id, vendor_change_id="change-1",
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
            return f"https://github.invalid/pull/{branch}"

    monkeypatch.setattr(cli, "fetch_spec", fake_fetch_spec)
    monkeypatch.setattr(cli, "GraphStore", lambda dsn: store)
    monkeypatch.setattr(cli, "VendorChangeDetector", _TwoFindingDetector)
    monkeypatch.setattr(cli, "StripeAdapter", _StubVendor)
    monkeypatch.setattr(cli, "TypeScriptAdapter", _PassingAdapter)
    monkeypatch.setattr(cli, "AgentRemediator", _EditingRemediator)
    monkeypatch.setattr(cli, "GitHubForge", _LocalForge)
    monkeypatch.setattr(cli, "PostgresSaver", _MemoryCheckpointer)

    args = argparse.Namespace(
        from_version="v2320", to_version="v2330", repo=str(origin),
        dsn="postgresql://unused", cache=str(tmp_path / "cache"), limit=0, run_id=None,
    )

    assert run(args) == 0
    assert store.statuses == []

    branches = _git(origin, "for-each-ref", "--format=%(refname:short)", "refs/heads/sync").split()
    assert len(branches) == 2

    commits = [set(_git(origin, "rev-list", f"{base_sha}..{branch}").split()) for branch in branches]
    assert [len(c) for c in commits] == [1, 1]
    assert commits[0].isdisjoint(commits[1])
