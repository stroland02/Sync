"""Python repositories are indexed, and their findings are reported rather than attempted.

`PythonAdapter` was 443 lines, tested, and constructed nowhere, so Sync saw TypeScript
repositories and was blind to Python ones -- a coverage limit nobody chose.

Wiring it alone would have been worse than leaving it. Its `static_verify` fails closed on
purpose: Python has no equivalent of `tsc` present in every project, mypy is optional and
routinely failing on code that ships, and passing on a syntax check alone would be a gate's
clothes over no gate, because a renamed field parses perfectly and that is exactly the class of
change this system exists to make. Follow that through the graph and a Python finding reaches
`patch`, spends an agent run, fails verification, retries, spends another, and abandons -- for a
verdict that was knowable before the first token.

So this is the tier -1 mechanism reused rather than reinvented: the decision is made before the
branch out of `prepare`, and the run reaches the report node without entering `patch`. These
tests assert on the executed node sequence for the reason `tests/test_no_patch_route.py` gives --
a patch node that ran and produced nothing would satisfy any weaker assertion -- and they carry a
spy for the agent, because the whole economic claim of deciding early is that no tokens are
spent.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from sync.cli import select_language_adapter
from sync.core import CallSite, Finding, OperationRef, Patch, RepoRef, VendorChange, VerifyResult
from sync.forge.github import PullRequest
from sync.remediate.graph import build_graph
from sync.remediate.tiered import TerminalTier, TieredRemediator

FIXTURES = Path(__file__).parent / "fixtures"

CHANGE = VendorChange(
    vendor_id="stripe", from_version="v1", to_version="v2",
    kind="response-optional-property-removed", operation_id="PostCharges",
    path_ptr="/v1/charges", severity="breaking", source="oasdiff",
    raw={"id": "response-optional-property-removed",
         "text": "removed the optional property `status` from the response"},
)
FINDING = Finding(
    id="f1", detector="vendor_change", claim="response-field", call_site_id="cs1",
    vendor_change_id="vc1",
    severity="breaking", rationale="PostCharges no longer answers with status",
)


class _Vendor:
    """Resolves the one symbol both fixture repositories call, in either language."""

    vendor_id = "stripe"
    # The indexer reads which package to bind from the vendor rather than holding a constant,
    # so a double that declares none is a vendor whose SDK nothing can recognise: it would bind
    # no client, index nothing, and leave every assertion below passing over an empty list.
    sdk_bindings = {
        "typescript": {"package": "stripe"},
        "python": {"distribution": "stripe", "module": "stripe"},
    }

    def operation_for_symbol(self, symbol: str, *, language: str | None = None):
        if symbol.endswith("charges.create"):
            return OperationRef(operation_id="PostCharges", http_method="post", path="/v1/charges")
        return None

    def fetch_changes(self, from_version: str, to_version: str):
        return []


def _repo(tmp_path: Path, fixture: str) -> RepoRef:
    shutil.copytree(FIXTURES / fixture, tmp_path, dirs_exist_ok=True)
    return RepoRef(
        repo_id="r1", url="https://example.invalid/r",
        local_path=str(tmp_path), head_sha="0" * 40,
    )


# --- indexing -------------------------------------------------------------------


def test_a_python_repository_produces_call_sites(tmp_path: Path) -> None:
    """Driven through the selector rather than by constructing `PythonAdapter`, because the
    adapter being correct and the adapter being reachable are the two different things this
    repository keeps shipping apart."""
    repo = _repo(tmp_path, "py/simple")

    adapter = select_language_adapter(repo, _Vendor())
    sites = list(adapter.index(repo))

    assert adapter.language_id == "python"
    assert [(s.path, s.operation_id) for s in sites] == [("src/billing.py", "PostCharges")]


def test_a_python_repository_written_with_aliases_produces_call_sites(tmp_path: Path) -> None:
    """The same reachability question for the forms `tests/test_python_aliases.py` covers at the
    adapter. Aliasing an import is ordinary Python and the branches reading it had never run, so
    until now nothing said whether a repository written that way reaches the indexer at all --
    and since `PythonAdapter` was wired in, a call site that goes unmatched costs a finding
    rather than nothing.

    `client_alias.py` calls `charges.retrieve`, which this vendor stub does not resolve, so two
    of the fixture's three files are expected here rather than all three.
    """
    repo = _repo(tmp_path, "py/aliased")

    adapter = select_language_adapter(repo, _Vendor())
    sites = list(adapter.index(repo))

    assert adapter.language_id == "python"
    assert sorted((s.path, s.operation_id) for s in sites) == [
        ("src/module_alias.py", "PostCharges"),
        ("src/positional_dict.py", "PostCharges"),
    ]


def test_a_typescript_repository_still_produces_call_sites(tmp_path: Path) -> None:
    """The regression that matters. A selector resolving everything to Python passes the test
    above and loses the language Sync already supported."""
    repo = _repo(tmp_path, "ts/simple")

    adapter = select_language_adapter(repo, _Vendor())
    sites = list(adapter.index(repo))

    assert adapter.language_id == "typescript"
    assert [s.operation_id for s in sites] == ["PostCharges"]


def test_a_repository_in_neither_language_is_refused_rather_than_guessed(
    tmp_path: Path,
) -> None:
    """The registry's rule: name what is available and never fall back. A silent default is how
    "we support many languages" becomes "we support one and say nothing"."""
    repo = _repo(tmp_path, "ts/no_stripe")

    with pytest.raises(LookupError) as raised:
        select_language_adapter(repo, _Vendor())

    assert "python" in str(raised.value) and "typescript" in str(raised.value)


# --- the graph ------------------------------------------------------------------


class _SpyAgent:
    """Records whether the expensive tier was asked anything at all."""

    strategy = "agent"

    def __init__(self) -> None:
        self.consulted = 0

    def can_handle(self, finding, change) -> bool:
        self.consulted += 1
        return True

    def propose(self, finding, change, site, repo, diagnostics: str = "") -> Patch:
        self.consulted += 1
        return Patch(diff="--- a\n+++ b\n", strategy="agent", rationale="the agent ran")


class _Store:
    def __init__(self, site: CallSite) -> None:
        self._site = site
        self.statuses: list = []
        self.rows: list = []

    def get_call_site(self, _id):
        return self._site

    def get_vendor_change(self, _id):
        return CHANGE

    def set_finding_status(self, finding_id, status):
        self.statuses.append((finding_id, status))

    def record_migration_outcome(self, outcome):
        self.rows.append(outcome)

    def observed_shapes(self, vendor_id, operation_id):
        return []


@dataclass
class _Forge:
    pushes: int = 0
    pr_url: str | None = None
    deleted: list = field(default_factory=list)

    def push_branch(self, repo, patch) -> str:
        self.pushes += 1
        return "sync/fix-1"

    def await_ci(self, repo, branch) -> tuple[bool, str]:
        return True, "https://example.invalid/run/1"

    # Returns what the forge created, number and URL, since the merge webhook joins a
    # delivery to a corpus row by number and nothing else durable links the two.
    def open_pull_request(self, repo, branch, evidence) -> PullRequest:
        self.pr_url = "https://example.invalid/pull/1"
        return PullRequest(number=1, url=self.pr_url)

    def delete_branch(self, repo, branch) -> tuple[bool, str]:
        self.deleted.append(branch)
        return True, "deleted"


def _site(path: str) -> CallSite:
    return CallSite(
        id="cs1", repo_id="r1", path=path, line=8, col=13, vendor_id="stripe",
        operation_id="PostCharges", symbol="stripe.charges.create",
        args_keys=["amount", "currency"], response_fields_read=["id", "status"],
        sdk_version="12.0.0", content_hash="h",
    )


@dataclass
class _VerifyingAdapter:
    """Any adapter that can verify, which is every one but Python.

    Stands in for `TypeScriptAdapter` in the graph tests and only there. The real one is
    exercised by the selection tests above and by `tests/test_pipeline_composes.py`; driving it
    through a graph would run `prepare`, which installs the customer's dependencies over the
    network, to establish a routing fact that has nothing to do with npm.

    It declares no `unverifiable_reason`, which is the whole of what the router reads.
    """

    language_id: str = "typescript"

    def matches(self, repo) -> bool:
        return True

    def prepare(self, repo) -> None:
        return None

    def static_verify(self, repo, patch) -> VerifyResult:
        return VerifyResult(ok=True)

    def discard_contaminated_dependencies(self, repo) -> bool:
        return False

    def index(self, repo):
        return []


def _drive(tmp_path: Path, fixture: str, source: str, adapter=None):
    """One finding through the shipped graph, returning the executed node sequence."""
    repo = _repo(tmp_path, fixture)
    adapter = adapter or select_language_adapter(repo, _Vendor())
    agent = _SpyAgent()
    store = _Store(_site(source))
    forge = _Forge()

    graph = build_graph(
        store=store, adapter=adapter,
        remediator=TieredRemediator([TerminalTier(agent)]),
        forge=forge, checkpointer=InMemorySaver(),
    )
    config = {"configurable": {"thread_id": "t1"}}

    sequence: list[str] = []
    for update in graph.stream(
        {"finding": FINDING, "repo": repo}, config=config, stream_mode="updates"
    ):
        sequence.extend(update.keys())

    return sequence, graph.get_state(config).values, agent, forge, store


def test_a_python_finding_never_enters_the_patch_node(tmp_path: Path) -> None:
    """The tier -1 assertion, for the other reason a run can know not to try. Against an
    unwired graph this fails because `patch` runs three times against a `static_verify` that
    cannot pass, which is the budget the early decision exists to save."""
    sequence, _, _, forge, _ = _drive(tmp_path, "py/simple", "src/billing.py")

    assert sequence == ["locate", "prepare", "report"]
    assert "patch" not in sequence
    assert forge.pushes == 0


def test_no_agent_is_consulted_for_a_python_finding(tmp_path: Path) -> None:
    """The economic claim. A test that only checked the outcome would pass an implementation
    that reached the agent first and threw its answer away."""
    _, _, agent, _, _ = _drive(tmp_path, "py/simple", "src/billing.py")

    assert agent.consulted == 0


def test_the_outcome_is_reported_and_not_abandoned(tmp_path: Path) -> None:
    """Abandonment means Sync tried and could not finish; this means Sync knew not to try.

    `abandon_reason` is where routing learns which change kinds are not mechanically safe, and
    "this language has no verifier" written there is a fact about Sync's coverage filed as a
    fact about the change -- the same corruption the tier -1 routing messages caused.
    """
    _, state, _, _, store = _drive(tmp_path, "py/simple", "src/billing.py")

    assert state["outcome"] == "reported"
    assert not state.get("abandon_reason")
    assert store.statuses == [], "the finding is real and unremediated, which `open` already says"


def test_the_report_says_why_rather_than_going_quiet(tmp_path: Path) -> None:
    """Not a silent drop either. A Python repository calling a changed operation is a genuine
    break, and Sync knowing and saying nothing is worse than the gap it just closed."""
    _, state, _, _, _ = _drive(tmp_path, "py/simple", "src/billing.py")

    reason = state["report_reason"].lower()
    assert "python" in reason
    assert "verif" in reason
    assert "PostCharges" in state["report_reason"]


def test_a_finding_whose_adapter_can_verify_still_reaches_patch(tmp_path: Path) -> None:
    """So none of the above is satisfied by a graph that reports everything.

    The distinguishing input is the adapter and nothing else: same finding, same change, same
    graph, and an adapter that declares it can verify reaches `patch` where Python reports.
    """
    sequence, state, agent, _, _ = _drive(
        tmp_path, "ts/simple", "src/billing.ts", adapter=_VerifyingAdapter(),
    )

    assert "patch" in sequence
    assert "report" not in sequence
    assert agent.consulted > 0
    assert state["verifiable"] is True


def test_python_static_verify_still_fails_closed(tmp_path: Path) -> None:
    """Pinned here rather than left to the adapter's own suite, because this wiring is the
    thing that would tempt someone to relax it. There is no arrangement of this pipeline in
    which a Python patch is verified, and a `VerifyResult(ok=True)` here would break the
    promise the whole product rests on."""
    repo = _repo(tmp_path, "py/simple")
    adapter = select_language_adapter(repo, _Vendor())

    result = adapter.static_verify(repo, Patch(diff="", strategy="agent", rationale="r"))

    assert isinstance(result, VerifyResult)
    assert result.ok is False
