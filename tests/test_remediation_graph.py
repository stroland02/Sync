from dataclasses import dataclass, field

from langgraph.checkpoint.memory import InMemorySaver

from sync.core import CallSite, Finding, Patch, RepoRef, VendorChange, VerifyResult
from sync.remediate.graph import build_graph

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
    id="f1", detector="vendor_change", call_site_id="cs1", vendor_change_id="vc1",
    severity="breaking", rationale="status removed",
)
REPO = RepoRef(repo_id="r1", url="https://example.invalid/r", local_path="/tmp/r", head_sha="0" * 40)


def _ok() -> VerifyResult:
    return VerifyResult(ok=True)


def _fail(diagnostics: str = "error TS2339") -> VerifyResult:
    return VerifyResult(ok=False, diagnostics=diagnostics)


class StubStore:
    def __init__(self):
        self.status: str | None = None
        self.status_calls: list[tuple[str, str]] = []

    def get_call_site(self, _id): return SITE
    def get_vendor_change(self, _id): return CHANGE

    def set_finding_status(self, _id, _status):
        self.status = _status
        self.status_calls.append((_id, _status))


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

    def can_handle(self, finding, change) -> bool: return True

    def propose(self, finding, change, site, repo, diagnostics="") -> Patch:
        self.calls += 1
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

    def open_pull_request(self, repo, branch, evidence) -> str:
        self.pr_url = "https://github.com/o/r/pull/1"
        return self.pr_url


def _run(adapter, remediator, forge, store=None):
    graph = build_graph(
        store=store or StubStore(), adapter=adapter, remediator=remediator,
        forge=forge, checkpointer=InMemorySaver(),
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
        def open_pull_request(self, repo, branch, evidence) -> str:
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
