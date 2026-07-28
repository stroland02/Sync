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
from typing import TypedDict

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from sync.cli import _clone, _repo_id, _select, _thread_to_invoke, main, run
from sync.core import CallSite, RepoRef, VendorChange


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
    explode: bool
    outcome: str


def _toy_graph(ran: list[str]):
    """A stand-in for the remediation graph, compiled against the same
    checkpointer contract. The point of testing `_thread_to_invoke` against a
    real compiled graph rather than a fake `get_state` is that the whole
    question is what LangGraph itself does with a finished versus an
    interrupted thread -- a fake would only assert what this file believes.
    """

    def locate(state: _ToyState) -> _ToyState:
        ran.append("locate")
        return {"outcome": "running"}

    def await_ci(state: _ToyState) -> _ToyState:
        ran.append("await_ci")
        if state.get("explode"):
            raise RuntimeError("the worker died waiting on CI")
        return {"outcome": "opened"}

    builder = StateGraph(_ToyState)
    builder.add_node("locate", locate)
    builder.add_node("await_ci", await_ci)
    builder.add_edge(START, "locate")
    builder.add_edge("locate", "await_ci")
    builder.add_edge("await_ci", END)
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


def test_a_run_that_died_mid_flight_resumes_its_own_thread():
    ran: list[str] = []
    graph = _toy_graph(ran)
    with pytest.raises(RuntimeError):
        _invoke(graph, "f1:abc123", {"explode": True})

    assert _thread_to_invoke(graph, "f1:abc123") == ("f1:abc123:0", True)


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
        _invoke(graph, "f1:abc123", {"explode": True})
    assert ran == ["locate", "await_ci"]

    ran.clear()
    graph.update_state({"configurable": {"thread_id": "f1:abc123:0"}}, {"explode": False})
    state = _invoke(graph, "f1:abc123", {"explode": False})

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
    _invoke(graph, "f1:abc123", {"explode": False})
    assert ran == ["locate", "await_ci"]

    ran.clear()
    thread_id, resuming = _thread_to_invoke(graph, "f1:abc123")

    assert (thread_id, resuming) == ("f1:abc123:1", False)
    _invoke(graph, "f1:abc123", {"explode": False})
    assert ran == ["locate", "await_ci"]


def test_a_new_generation_starts_from_an_empty_state():
    """A finished thread is left alone rather than re-entered, so the second
    run cannot inherit the first run's keys. `patch`, `verify_ok` and
    `static_fatal` are all read by routing functions, and every one of them
    would otherwise arrive pre-set from a run that already ended.
    """
    ran: list[str] = []
    graph = _toy_graph(ran)
    _invoke(graph, "f1:abc123", {"explode": False})

    thread_id, _ = _thread_to_invoke(graph, "f1:abc123")
    assert graph.get_state({"configurable": {"thread_id": thread_id}}).values == {}
