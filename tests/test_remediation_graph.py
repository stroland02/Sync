from dataclasses import dataclass, field
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver
from pydantic import BaseModel

from sync.core import CallSite, Finding, Patch, RepoRef, VendorChange, VerifyResult
from sync.forge.github import PullRequest
from sync.remediate import nodes
from sync.remediate.graph import build_graph
from sync.route.matrix import NO_PATCH

SITE = CallSite(
    repo_id="r1", path="src/billing.ts", line=6, col=8, vendor_id="stripe",
    operation_id="PostCharges", symbol="stripe.charges.create",
    args_keys=["amount"], response_fields_read=["status"],
    sdk_version="18.0.0", content_hash="h1",
)
CHANGE = VendorChange(
    vendor_id="stripe", from_version="v1", to_version="v2",
    kind="response-property-removed", operation_id="PostCharges", path_ptr="/x/status",
    severity="breaking", source="oasdiff", raw={"field": "status"},
)
FINDING = Finding(
    id="f1", detector="vendor_change", claim="response-field", call_site_id="cs1",
    vendor_change_id="vc1",
    severity="breaking", rationale="status removed",
)
REPO = RepoRef(repo_id="r1", url="https://example.invalid/r", local_path="/tmp/r", head_sha="0" * 40)


def _ok() -> VerifyResult:
    return VerifyResult(ok=True)


def _fail(diagnostics: str = "error TS2339") -> VerifyResult:
    return VerifyResult(ok=False, diagnostics=diagnostics)


class StubStore:
    def __init__(self, change: VendorChange = CHANGE):
        self.change = change
        self.status: str | None = None
        self.status_calls: list[tuple[str, str]] = []
        self.outcomes: list = []

    def get_call_site(self, _id): return SITE
    def get_vendor_change(self, _id): return self.change

    def set_finding_status(self, _id, _status):
        self.status = _status
        self.status_calls.append((_id, _status))

    def record_migration_outcome(self, outcome) -> None:
        """The corpus write, which this stub used to lack.

        `make_recorder` now states that contract at construction, so a store without it fails
        `build_graph` rather than recording nothing. Every test in this file built the real
        graph against a store that could not record and passed regardless -- which is the
        failure the contract exists to make visible, found by making it.
        """
        self.outcomes.append(outcome)


@dataclass
class StubAdapter:
    # A list of full VerifyResult objects, not bools: `ok` and the emptiness of
    # `diagnostics` do not always agree (the real tsc adapter can fail with no
    # diagnostics text at all), so the stub must be able to express that
    # combination rather than deriving diagnostics from ok.
    verdicts: list[VerifyResult] = field(default_factory=lambda: [_ok()])
    calls: int = 0
    prepare_calls: int = 0

    def prepare(self, repo) -> None:
        self.prepare_calls += 1

    def static_verify(self, repo, patch) -> VerifyResult:
        result = self.verdicts[min(self.calls, len(self.verdicts) - 1)]
        self.calls += 1
        return result


@dataclass
class StubRemediator:
    strategy: str = "agent"
    calls: int = 0
    # `AgentRemediator` writes into the clone and then reports what changed. A
    # stub that only returns a diff leaves the tree untouched, which no test
    # against a stubbed adapter can see and which is wrong the moment the real
    # adapter is wired in: it measures the tree, not the diff.
    writes: dict[str, str] = field(default_factory=dict)

    def can_handle(self, finding, change) -> bool: return True

    def propose(self, finding, change, site, repo, diagnostics="") -> Patch:
        self.calls += 1
        for relative, text in self.writes.items():
            (Path(repo.local_path) / relative).write_text(text, encoding="utf-8")
        return Patch(diff="--- a\n+++ b\n", strategy=self.strategy, rationale="fix")


@dataclass
class StubForge:
    ci_results: list[bool] = field(default_factory=lambda: [True])
    polls: int = 0
    pushes: int = 0
    pr_url: str | None = None

    def push_branch(self, repo, patch) -> str:
        self.pushes += 1
        return "sync/fix-1"

    def await_ci(self, repo, branch) -> tuple[bool, str]:
        green = self.ci_results[min(self.polls, len(self.ci_results) - 1)]
        self.polls += 1
        return green, "https://github.com/o/r/actions/runs/1"

    # Returns what the forge created, number and URL, since the merge webhook joins a
    # delivery to a corpus row by number and nothing else durable links the two.
    def open_pull_request(self, repo, branch, evidence) -> PullRequest:
        self.pr_url = "https://github.com/o/r/pull/1"
        return PullRequest(number=1, url=self.pr_url)


def _run(adapter, remediator, forge, store=None, catalogue=None):
    graph = build_graph(
        store=store or StubStore(), adapter=adapter, remediator=remediator,
        forge=forge, checkpointer=InMemorySaver(), catalogue=catalogue,
    )
    return graph.invoke(
        {"finding": FINDING, "repo": REPO},
        config={"configurable": {"thread_id": "t1"}},
    )


def test_a_clean_run_opens_a_pull_request():
    forge = StubForge()
    result = _run(StubAdapter(), StubRemediator(), forge)
    assert result["pr_url"] == "https://github.com/o/r/pull/1"
    assert result["outcome"] == "opened"


def test_a_static_failure_retries_the_patch():
    remediator = StubRemediator()
    result = _run(StubAdapter(verdicts=[_fail(), _ok()]), remediator, StubForge())
    assert remediator.calls == 2
    assert result["outcome"] == "opened"


def test_three_static_failures_abandon_without_pushing():
    forge = StubForge()
    remediator = StubRemediator()
    store = StubStore()
    result = _run(
        StubAdapter(verdicts=[_fail(), _fail(), _fail(), _fail()]), remediator, forge, store=store
    )
    assert result["outcome"] == "abandoned"
    assert forge.pr_url is None
    assert remediator.calls == 3
    assert store.status_calls == [("f1", "abandoned")]


def test_a_red_ci_run_retries_the_patch_once():
    remediator = StubRemediator()
    result = _run(StubAdapter(), remediator, StubForge(ci_results=[False, True]))
    assert remediator.calls == 2
    assert result["outcome"] == "opened"


def test_two_red_ci_runs_abandon_and_record_why():
    forge = StubForge(ci_results=[False, False, False])
    store = StubStore()
    result = _run(StubAdapter(), StubRemediator(), forge, store=store)
    assert result["outcome"] == "abandoned"
    assert forge.pr_url is None
    assert "CI" in result["abandon_reason"]
    assert store.status == "abandoned"


def test_a_red_ci_run_does_not_repatch_once_the_static_budget_is_spent():
    """Two static failures spend two of the three attempts before the third
    verifies clean and pushes; a red CI response must not spend a fourth
    attempt just because ci_attempts is still under its own bound -- the two
    bounds are independent and either one being spent must abandon the run.
    """
    remediator = StubRemediator()
    forge = StubForge(ci_results=[False, True])
    result = _run(StubAdapter(verdicts=[_fail(), _fail(), _ok()]), remediator, forge)
    assert remediator.calls == 3
    assert forge.pushes == 1
    assert result["outcome"] == "abandoned"
    assert forge.pr_url is None
    assert "CI" in result["abandon_reason"]


def test_a_failed_verification_with_empty_diagnostics_never_pushes():
    """The real tsc adapter can return ok=False with diagnostics="" (a silent
    npx failure writes nothing to either stream); routing must trust `ok`,
    not whether the diagnostics string happens to be non-empty.
    """
    forge = StubForge()
    remediator = StubRemediator()
    result = _run(StubAdapter(verdicts=[_fail(diagnostics="")]), remediator, forge)
    assert remediator.calls == 3
    assert forge.pushes == 0
    assert result["outcome"] == "abandoned"
    assert forge.pr_url is None


@dataclass
class Recording(StubRemediator):
    seen: list[str] = field(default_factory=list)

    def propose(self, finding, change, site, repo, diagnostics=""):
        self.seen.append(diagnostics)
        return super().propose(finding, change, site, repo, diagnostics)


def test_diagnostics_from_a_failed_verification_reach_the_next_attempt():
    remediator = Recording()
    _run(StubAdapter(verdicts=[_fail(), _ok()]), remediator, StubForge())
    assert remediator.seen[0] == ""
    assert "TS2339" in remediator.seen[1]


class NotCheckpointed(BaseModel):
    """A model no run ever puts in a checkpoint.

    Module scope rather than inside the test: the ext hook rebuilds a type by
    importing its module and taking the attribute off it, so a class nested in a
    function comes back as a dict regardless of the allowlist.
    """

    value: str


def test_the_graph_registers_syncs_types_on_whatever_checkpointer_it_is_handed():
    """`cli.py` builds the saver, so `build_graph` is the only place every caller
    passes through. A saver that reaches `compile` with langgraph's default
    serializer resumes runs on a permission langgraph says it will withdraw.

    Asserted through a type that is *not* registered, because the default carries
    Sync's models too: only refusing a foreign type distinguishes an explicit
    allowlist from the permissive default.
    """
    saver = InMemorySaver()
    graph = build_graph(
        store=StubStore(), adapter=StubAdapter(), remediator=StubRemediator(),
        forge=StubForge(), checkpointer=saver,
    )
    serde = graph.checkpointer.serde

    assert serde.loads_typed(serde.dumps_typed(FINDING)) == FINDING
    foreign = NotCheckpointed(value="x")
    assert serde.loads_typed(serde.dumps_typed(foreign)) == {"value": "x"}


def test_state_is_checkpointed_at_every_node():
    saver = InMemorySaver()
    graph = build_graph(
        store=StubStore(), adapter=StubAdapter(), remediator=StubRemediator(),
        forge=StubForge(), checkpointer=saver,
    )
    config = {"configurable": {"thread_id": "t2"}}
    graph.invoke({"finding": FINDING, "repo": REPO}, config=config)
    assert graph.get_state(config).values["outcome"] == "opened"


def test_an_agent_run_that_fails_is_abandoned_rather_than_crashing_the_graph():
    @dataclass
    class Failing(StubRemediator):
        def propose(self, finding, change, site, repo, diagnostics=""):
            self.calls += 1
            raise RuntimeError("agent run failed (error_max_turns): []")

    remediator = Failing()
    forge = StubForge()
    store = StubStore()
    result = _run(StubAdapter(), remediator, forge, store=store)
    assert result["outcome"] == "abandoned"
    assert forge.pushes == 0
    assert forge.pr_url is None
    assert remediator.calls == 3
    assert "agent run failed" in result["abandon_reason"]
    assert store.status == "abandoned"


def test_a_patch_that_changes_nothing_is_never_pushed():
    @dataclass
    class NoChange(StubRemediator):
        def propose(self, finding, change, site, repo, diagnostics=""):
            self.calls += 1
            return Patch(diff="", strategy=self.strategy, rationale="nothing to do")

    forge = StubForge()
    store = StubStore()
    result = _run(StubAdapter(), NoChange(), forge, store=store)
    assert result["outcome"] == "abandoned"
    assert forge.pushes == 0
    assert forge.pr_url is None
    assert store.status == "abandoned"


def test_a_bare_exception_still_records_a_useful_abandon_reason():
    """str(KeyError("apiKey")) is "'apiKey'" -- the class name is the only part
    of the message that says what kind of failure this was, and it must not be
    dropped.
    """

    @dataclass
    class Bare(StubRemediator):
        def propose(self, finding, change, site, repo, diagnostics=""):
            self.calls += 1
            raise KeyError("apiKey")

    remediator = Bare()
    result = _run(StubAdapter(), remediator, StubForge())
    assert result["outcome"] == "abandoned"
    assert "KeyError" in result["abandon_reason"]
    assert "apiKey" in result["abandon_reason"]


def test_an_exception_with_no_message_still_produces_a_useful_abandon_reason():
    """str(TimeoutError()) is "" -- an exception raised without arguments must
    not collapse the abandon reason down to the generic 'unknown' fallback.
    """

    @dataclass
    class Bare(StubRemediator):
        def propose(self, finding, change, site, repo, diagnostics=""):
            self.calls += 1
            raise TimeoutError()

    remediator = Bare()
    result = _run(StubAdapter(), remediator, StubForge())
    assert result["outcome"] == "abandoned"
    assert "TimeoutError" in result["abandon_reason"]


def test_prepare_runs_before_the_first_patch_attempt():
    """The patch agent runs with Bash in hand and is told to typecheck as it
    goes; if it meets an empty `node_modules`, the obvious next command it
    reaches for has no `--ignore-scripts` guarantee. `prepare` must install
    before the agent ever starts, not merely before `static_verify`.
    """
    order: list[str] = []

    @dataclass
    class OrderedAdapter(StubAdapter):
        def prepare(self, repo) -> None:
            order.append("prepare")

    @dataclass
    class OrderedRemediator(StubRemediator):
        def propose(self, finding, change, site, repo, diagnostics=""):
            order.append("patch")
            return super().propose(finding, change, site, repo, diagnostics)

    result = _run(OrderedAdapter(), OrderedRemediator(), StubForge())
    assert order == ["prepare", "patch"]
    assert result["outcome"] == "opened"


def test_a_failed_prepare_abandons_without_attempting_a_patch():
    """A prepare failure -- a broken registry, a lockfile out of sync with
    package.json -- is an environment fault no patch can fix. It must abandon
    immediately rather than reaching the patch node at all.
    """

    @dataclass
    class Failing(StubAdapter):
        def prepare(self, repo) -> None:
            raise RuntimeError("npm install failed: ENOENT: registry unreachable")

    remediator = StubRemediator()
    forge = StubForge()
    store = StubStore()
    result = _run(Failing(), remediator, forge, store=store)
    assert result["outcome"] == "abandoned"
    assert remediator.calls == 0
    assert forge.pushes == 0
    assert forge.pr_url is None
    assert "registry unreachable" in result["abandon_reason"]
    assert store.status == "abandoned"


def test_a_fatal_static_verify_abandons_immediately_without_spending_the_retry_budget():
    """An exception out of static_verify -- as opposed to a normal
    VerifyResult(ok=False) -- means verification could not be performed at
    all: a broken registry, a lockfile out of sync with package.json. None of
    those causes is something a different patch could fix, so this must
    abandon on the first occurrence instead of retrying up to
    MAX_STATIC_ATTEMPTS against the same fault.
    """

    @dataclass
    class Fatal(StubAdapter):
        def static_verify(self, repo, patch) -> VerifyResult:
            self.calls += 1
            raise RuntimeError("npm install failed: ENOENT: registry unreachable")

    remediator = StubRemediator()
    forge = StubForge()
    store = StubStore()
    result = _run(Fatal(), remediator, forge, store=store)
    assert result["outcome"] == "abandoned"
    assert remediator.calls == 1
    assert forge.pushes == 0
    assert forge.pr_url is None
    assert "registry unreachable" in result["abandon_reason"]
    assert store.status == "abandoned"


def test_a_vendor_change_that_cannot_be_looked_up_abandons_before_preparing():
    """`Finding.vendor_change_id` is optional: a detector that does not join
    against a vendor change leaves it None, and `get_vendor_change(None)`
    raises. A lookup that cannot be performed is not something a different
    patch fixes, and the exception must not escape `graph.invoke` and leave the
    finding sitting at status 'open'.
    """

    class MissingChange(StubStore):
        def get_vendor_change(self, _id):
            raise KeyError(_id)

    adapter = StubAdapter()
    remediator = StubRemediator()
    forge = StubForge()
    store = MissingChange()
    result = _run(adapter, remediator, forge, store=store)
    assert result["outcome"] == "abandoned"
    assert adapter.prepare_calls == 0
    assert remediator.calls == 0
    assert forge.pushes == 0
    assert forge.pr_url is None
    assert "KeyError" in result["abandon_reason"]
    assert store.status == "abandoned"


def test_a_rejected_push_abandons_without_spending_the_patch_budget():
    """`GitHubForge._run` raises on any non-zero exit -- a protected branch, an
    expired token, a lost network. None of those is something a different patch
    fixes, so this abandons on the first occurrence rather than repatching.
    """

    @dataclass
    class Rejected(StubForge):
        def push_branch(self, repo, patch) -> str:
            self.pushes += 1
            raise RuntimeError("git push failed: protected branch hook declined")

    remediator = StubRemediator()
    forge = Rejected()
    store = StubStore()
    result = _run(StubAdapter(), remediator, forge, store=store)
    assert result["outcome"] == "abandoned"
    assert remediator.calls == 1
    assert forge.polls == 0
    assert forge.pr_url is None
    assert "protected branch" in result["abandon_reason"]
    assert store.status == "abandoned"


def test_a_ci_poll_that_raises_abandons_rather_than_retrying_the_patch():
    """A red CI verdict retries; a poll that produced no verdict at all -- an
    expired gh token, a lost network -- must not, since the patch is not what
    failed.
    """

    @dataclass
    class Unpollable(StubForge):
        def await_ci(self, repo, branch):
            self.polls += 1
            raise RuntimeError("gh run list failed: HTTP 401: Bad credentials")

    remediator = StubRemediator()
    forge = Unpollable()
    store = StubStore()
    result = _run(StubAdapter(), remediator, forge, store=store)
    assert result["outcome"] == "abandoned"
    assert remediator.calls == 1
    assert forge.polls == 1
    assert forge.pr_url is None
    assert "Bad credentials" in result["abandon_reason"]
    assert store.status == "abandoned"


def test_a_pull_request_that_cannot_be_opened_abandons_and_leaves_no_pr_url():
    """The last node in the graph is no more reliable than the rest: `gh pr
    create` fails on a rate limit or a repository that already has an open pull
    request for the branch. `pr_url` must stay unset, exactly as on every other
    abandon route, so nothing downstream reports a pull request that does not
    exist.
    """

    @dataclass
    class Unopenable(StubForge):
        def open_pull_request(self, repo, branch, evidence) -> PullRequest:
            raise RuntimeError("gh pr create failed: GraphQL: was submitted too quickly")

    forge = Unopenable()
    store = StubStore()
    result = _run(StubAdapter(), StubRemediator(), forge, store=store)
    assert result["outcome"] == "abandoned"
    assert result["pr_url"] is None
    assert forge.pushes == 1
    assert "too quickly" in result["abandon_reason"]
    assert store.status == "abandoned"


def test_a_static_retry_names_the_typechecker_as_what_rejected_the_attempt():
    """`diagnostics` reaches the patch agent from two producers with nothing in
    the value itself to tell them apart. Bare tsc output does not say which
    stage produced it.
    """
    remediator = Recording()
    _run(StubAdapter(verdicts=[_fail(), _ok()]), remediator, StubForge())
    feedback = remediator.seen[1]
    assert "tsc" in feedback
    assert "TS2339" in feedback
    assert "CI" not in feedback


def test_a_ci_retry_says_ci_failed_and_hands_over_the_diff_ci_rejected():
    """A CI retry introduced as a typecheck failure is a lie, and a bare run URL
    is unreadable: WebFetch and WebSearch are both in the patch agent's
    DISALLOWED_TOOLS. The retry costs a full agent run plus a second CI wait, so
    it has to carry something the agent can act on without the network.
    """
    remediator = Recording()
    _run(StubAdapter(), remediator, StubForge(ci_results=[False, True]))
    feedback = remediator.seen[1]
    assert "CI" in feedback
    assert "https://github.com/o/r/actions/runs/1" in feedback
    assert "--- a\n+++ b\n" in feedback
    assert "tsc" not in feedback


def test_what_the_patch_agent_is_told_is_not_what_the_operator_is_told():
    """The abandon reason is what `cli.py` prints for a run that produced no
    pull request, and what an operator scans a batch of runs by. Feeding a
    whole rejected diff into it to satisfy the patch agent trades one
    audience's needs for the other's; the two are separate channels.
    """
    remediator = Recording()
    forge = StubForge(ci_results=[False, False, False])
    result = _run(StubAdapter(), remediator, forge, store=StubStore())
    reason = result["abandon_reason"]
    assert result["outcome"] == "abandoned"
    assert "https://github.com/o/r/actions/runs/1" in reason
    assert "--- a\n+++ b\n" not in reason
    assert len(reason.splitlines()) == 1
    # ...while the agent still got the long form on the retry.
    assert "--- a\n+++ b\n" in remediator.seen[1]


def test_a_patch_that_only_typechecks_with_untracked_files_never_reaches_push_branch(
    base_clone, agent_edit
):
    """The real adapter, the real graph, and the M0 acceptance failure's shape.

    The clone's working tree compiles clean; the branch `push_branch` would
    create does not, because the declaration the patched line needs lives in an
    untracked, gitignored file. Before this gate measured the shipped tree the
    run pushed, waited out a CI run, and was rejected there. It now abandons
    carrying the compiler's own complaint.

    The patch node applies the patch rather than the fixture, because `prepare`
    measures its typecheck baseline first and a tree that already carries the
    patch would fold those errors into the baseline they are measured against.
    """
    from sync.index.typescript import TypeScriptAdapter

    repo = RepoRef(
        repo_id="r1", url="https://example.invalid/r",
        local_path=str(base_clone), head_sha="0" * 40,
    )
    forge = StubForge()
    graph = build_graph(
        store=StubStore(), adapter=TypeScriptAdapter(vendor_adapter=None),
        remediator=StubRemediator(writes=agent_edit), forge=forge, checkpointer=InMemorySaver(),
    )
    result = graph.invoke(
        {"finding": FINDING, "repo": repo},
        config={"configurable": {"thread_id": "t-shipped"}},
    )

    assert forge.pushes == 0
    assert result["outcome"] == "abandoned"
    assert "TS2304" in result["abandon_reason"]


class DeletingForge(StubForge):
    """A forge that records what abandonment asked it to clean up."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.deleted: list[str] = []

    def delete_branch(self, repo, branch) -> tuple[bool, str]:
        self.deleted.append(branch)
        return True, f"deleted {branch}"


def test_abandoning_after_a_push_deletes_the_branch_it_left_behind():
    """A finding that abandons after pushing strands a branch with no pull request.

    Nothing ever comes back for it, and it sits on a repository Sync does not own.
    """
    forge = DeletingForge(ci_results=[False, False])
    result = _run(StubAdapter(), StubRemediator(), forge)

    assert result["outcome"] == "abandoned"
    assert forge.deleted == ["sync/fix-1"]


def test_abandoning_before_a_push_deletes_nothing():
    """Most abandonments never reach the forge. Asking it to delete a branch that
    was never pushed would turn every failed patch into a spurious remote call."""
    @dataclass
    class Failing(StubRemediator):
        def propose(self, finding, change, site, repo, diagnostics=""):
            raise RuntimeError("agent run failed (error_max_turns): []")

    forge = DeletingForge()
    result = _run(StubAdapter(), Failing(), forge)

    assert result["outcome"] == "abandoned"
    assert forge.deleted == []


def test_a_failed_cleanup_does_not_replace_the_reason_the_finding_abandoned():
    """The operator's useful signal is why the finding failed, not why the tidying
    afterwards failed. A cleanup that raises must not become the abandon reason."""

    class Unclean(DeletingForge):
        def delete_branch(self, repo, branch):
            raise RuntimeError("the remote hung up")

    forge = Unclean(ci_results=[False, False])
    result = _run(StubAdapter(), StubRemediator(), forge)

    assert result["outcome"] == "abandoned"
    assert "CI" in result["abandon_reason"]
    assert "hung up" not in result["abandon_reason"]


# --- the graph that ships, pinned, and the graph that cannot push -------------------

# Read off the shipped assembly rather than transcribed from `graph.py`, so a router whose
# destination moves moves this pin with it. `__start__` and `__end__` are langgraph's and are
# part of the compiled shape, so they are pinned alongside the ten Sync writes.
SHIPPED_NODES = (
    "__start__", "locate", "prepare", "patch", "static_verify", "replay",
    "push_branch", "await_ci", "open_pr", "report", "abandon", "__end__",
)

# `data` carries the router's decision only where the decision and its destination differ.
# The shipped graph has two such edges and both are load-bearing: `static_verify` decides
# "push_branch" and reaches `replay`, and `open_pr` decides "end" and reaches `__end__`.
SHIPPED_EDGES = frozenset({
    ("__start__", "locate", None, False),
    ("locate", "prepare", None, True),
    ("locate", "abandon", None, True),
    ("prepare", "patch", None, True),
    ("prepare", "report", None, True),
    ("prepare", "abandon", None, True),
    ("patch", "static_verify", None, True),
    ("patch", "patch", None, True),
    ("patch", "abandon", None, True),
    ("static_verify", "patch", None, True),
    ("static_verify", "replay", "push_branch", True),
    ("static_verify", "abandon", None, True),
    ("replay", "patch", None, True),
    ("replay", "push_branch", None, True),
    ("replay", "abandon", None, True),
    ("push_branch", "await_ci", None, True),
    ("push_branch", "abandon", None, True),
    ("await_ci", "patch", None, True),
    ("await_ci", "open_pr", None, True),
    ("await_ci", "abandon", None, True),
    ("open_pr", "__end__", "end", True),
    ("open_pr", "abandon", None, True),
    ("report", "__end__", None, False),
    ("abandon", "__end__", None, False),
})

REMOTE_NODES = frozenset({"push_branch", "await_ci", "open_pr"})


def _topology(graph):
    drawable = graph.get_graph()
    return tuple(drawable.nodes), frozenset(
        (edge.source, edge.target, edge.data, edge.conditional) for edge in drawable.edges
    )


def _build(forge):
    return build_graph(
        store=StubStore(), adapter=StubAdapter(), remediator=StubRemediator(),
        forge=forge, checkpointer=InMemorySaver(),
    )


def test_a_graph_built_with_a_forge_is_the_graph_that_ships():
    """The regression surface, not the change.

    A real run drives this assembly and the acceptance run that would notice a narrowing
    costs a model budget and a pull request. Pinning the whole compiled shape -- every node
    in order, every edge with its condition -- is what makes a node quietly dropped from the
    forge-carrying path a red test here rather than a discovery there.
    """
    nodes, edges = _topology(_build(StubForge()))

    assert nodes == SHIPPED_NODES
    assert edges == SHIPPED_EDGES


def test_a_graph_built_without_a_forge_has_no_node_that_can_push():
    """Absent from the compiled graph, not guarded inside it.

    A guard leaves the node present, and a present node is resumable: an interrupted run
    checkpointed at `push_branch` resumes straight into a push the moment a caller holding a
    forge picks it up. Absence is not resumable, which is the whole of the safety argument.
    """
    nodes, edges = _topology(_build(None))

    assert REMOTE_NODES.isdisjoint(nodes)
    # Nothing else moved: the three named nodes are the only difference.
    assert set(nodes) == set(SHIPPED_NODES) - REMOTE_NODES
    assert not [
        edge for edge in edges if REMOTE_NODES & {edge[0], edge[1]}
    ]
    # The decision keeps its name and only its destination moves. `route_after_static` and
    # `sync.mcp.propose` both read the literal "push_branch" as the verdict "this patch is
    # verified", which is a claim about the patch and not a request for a remote.
    assert ("static_verify", "replay", "push_branch", True) in edges
    assert ("replay", "report", "push_branch", True) in edges


def test_a_forgeless_run_that_would_have_pushed_reports_the_halt():
    forge_less = _run(StubAdapter(), StubRemediator(), None)

    assert forge_less["outcome"] == "reported"
    assert forge_less["pr_url"] is None
    reason = forge_less["report_reason"]
    assert "without a forge" in reason
    # Both halves, because each fails differently. Dropping the cause leaves "was not pushed"
    # alone, which reads as a failure and sends an operator looking for one. Naming a node
    # spends the line on internals that appear on no operator-facing surface, and `cli.py`
    # renders this verbatim.
    assert "cannot reach a remote" in reason
    assert not [node for node in REMOTE_NODES if node in reason]
    # The finding is what an operator is looking at; a reason that names only the harness
    # says nothing about what was left unrepaired.
    assert "response-property-removed" in reason
    assert "PostCharges" in reason
    # And it must not borrow tier -1's sentence. A verified patch that was not pushed is the
    # opposite claim to "no patch was warranted", and the console renders this verbatim.
    assert "no patch is warranted" not in reason


def test_a_forgeless_graph_still_reports_tier_minus_one_in_its_own_words():
    """The halt reason must discriminate rather than decorate.

    `report` is reached from two places in a forge-less graph -- a run that had nothing to
    try, and a run that verified a patch and had nowhere to push it. Both are `reported`, and
    a reason that cannot tell them apart makes the outcome unreadable.
    """

    @dataclass
    class Unverifiable(StubAdapter):
        unverifiable_reason: str = "sync cannot typecheck Python"

    result = _run(Unverifiable(), StubRemediator(), None)

    assert result["outcome"] == "reported"
    assert "sync cannot typecheck Python" in result["report_reason"]
    assert "without a forge" not in result["report_reason"]


# --- the corpus row a halted attempt owes ------------------------------------------

# A real oasdiff record rather than an invented one, so the tier this routes to is the tier
# the shipped table assigns. `kind=lifecycle` is what carries it to -1.
LIFECYCLE_RULE = {
    "id": "api-deprecated-sunset-missing", "level": "error", "direction": "none",
    "area": "paths", "kind": "lifecycle", "action": "change",
    "description": "endpoint deprecated without sunset date",
}
CATALOGUE = {LIFECYCLE_RULE["id"]: LIFECYCLE_RULE}
LIFECYCLE_CHANGE = VendorChange(
    vendor_id="stripe", from_version="v1", to_version="v2",
    kind="api-deprecated-sunset-missing", operation_id="PostCharges",
    path_ptr="/v1/charges", severity="breaking", source="oasdiff",
    raw={"id": "api-deprecated-sunset-missing"},
)


def test_a_forgeless_run_that_verified_a_patch_records_the_attempt():
    """`report` is terminal for an attempt that ran, so it owes the corpus a row.

    Every rehearsal against a fixture ends here. A run that patched, typechecked and had
    nowhere to push still spent an attempt, and the corpus is the table whose grain is one
    attempt -- so without this row `Counts.attempts` counts zero over exactly the runs that
    verified, and `routing_accuracy` learns nothing from them.
    """
    store = StubStore()
    result = _run(StubAdapter(), StubRemediator(), None, store=store)

    assert result["outcome"] == "reported"
    assert result["static_attempts"] == 1
    assert result["attempt_strategy"] == "agent"
    assert result["verify_ok"] is True

    assert len(store.outcomes) == 1
    row = store.outcomes[0]
    assert row.terminal_status == "halted"
    assert row.attempt_index == 1
    assert row.static_verify_passed is True
    # A halt passes neither field that belongs to another terminal: nothing was abandoned,
    # and `pr_number` null is what keeps this row out of every merge rate.
    assert row.abandon_reason is None
    assert row.pr_number is None


def test_a_forgeless_tier_minus_one_run_records_nothing():
    """The other caller of `report`, which must stay silent.

    Tier -1 attempted nothing, and a row at this table's grain would be a fabrication.
    """
    store = StubStore(change=LIFECYCLE_CHANGE)
    result = _run(StubAdapter(), StubRemediator(), None, store=store, catalogue=CATALOGUE)

    assert result["outcome"] == "reported"
    assert result["tier"] == NO_PATCH
    assert result["static_attempts"] == 0
    assert store.outcomes == []


def test_only_the_halt_branch_of_report_reaches_the_recorder():
    """What the graph-level pair above cannot show on its own.

    `corpus._record` already drops any call describing zero attempts, so a `report` that
    recorded on both branches would still write no row for tier -1 and satisfy the negative
    test. The discrimination has to be observed at the call, which is where the branch is.
    """
    calls: list[dict] = []
    report = nodes.make_report("nowhere to push", lambda state, **kw: calls.append(kw))

    report({"change": CHANGE, "verify_ok": True, "static_attempts": 1})
    assert calls == [{"terminal_status": "halted"}]

    calls.clear()
    report({"change": CHANGE, "tier": NO_PATCH, "routing_row": "r1"})
    assert calls == []
