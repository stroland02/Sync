"""Tier -1 reaches END without entering the patch node.

`sync.route.matrix` routes the 21 `kind=lifecycle` breaking rules to tier -1: they describe
how a vendor documented a deprecation, and no edit in a consumer's repository resolves one.
`TieredRemediator` honours that by raising `NoPatchWarranted` -- but it raises from inside
`propose`, which runs inside the `patch` node, and nothing in the graph catches it.

The routing-matrix spec's Verification section is explicit about how to test the fix:

    **Tier -1 emits no patch.** A `lifecycle` finding must produce a report and reach `END`
    without entering `patch`. Assert on the node sequence, not on the absence of a diff -- a
    patch node that ran and produced nothing is a different bug wearing the same result.

So these assert on the executed node sequence. A test that only checked `pr_url is None`
would pass against the broken code, which reaches `patch`, raises, and abandons.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from sync.core import CallSite, Finding, Patch, RepoRef, VendorChange, VerifyResult
from sync.forge.github import PullRequest
from sync.remediate.graph import build_graph
from sync.remediate.tiered import TerminalTier, TieredRemediator
from sync.route.matrix import NO_PATCH

# Real catalogue records, read from the pinned oasdiff binary rather than invented -- a
# fixture that disagreed with the binary would test a table nobody routes on.
LIFECYCLE_RULE = {
    "id": "api-deprecated-sunset-missing", "level": "error", "direction": "none",
    "area": "paths", "kind": "lifecycle", "action": "change",
    "description": "endpoint deprecated without sunset date",
}
PATCHABLE_RULE = {
    "id": "request-property-removed", "level": "warning", "direction": "request",
    "area": "schema", "kind": "existence", "action": "remove",
    "description": "request property removed",
}
CATALOGUE = {LIFECYCLE_RULE["id"]: LIFECYCLE_RULE, PATCHABLE_RULE["id"]: PATCHABLE_RULE}

SITE = CallSite(
    repo_id="r1", path="src/billing.ts", line=6, col=8, vendor_id="stripe",
    operation_id="PostCharges", symbol="stripe.charges.create",
    args_keys=["amount"], response_fields_read=["status"],
    sdk_version="18.0.0", content_hash="h1",
)
LIFECYCLE_CHANGE = VendorChange(
    vendor_id="stripe", from_version="v1", to_version="v2",
    kind="api-deprecated-sunset-missing", operation_id="PostCharges",
    path_ptr="/v1/charges", severity="breaking", source="oasdiff",
    raw={"id": "api-deprecated-sunset-missing",
         "text": "endpoint deprecated without sunset date"},
)
PATCHABLE_CHANGE = VendorChange(
    vendor_id="stripe", from_version="v1", to_version="v2",
    kind="request-property-removed", operation_id="PostCharges",
    path_ptr="/v1/charges", severity="breaking", source="oasdiff",
    raw={"id": "request-property-removed",
         "text": "removed the request property `amount`"},
)
FINDING = Finding(
    id="f1", detector="vendor_change", claim="operation-only", call_site_id="cs1",
    vendor_change_id="vc1",
    severity="breaking", rationale="endpoint deprecated without a sunset date",
)
REPO = RepoRef(repo_id="r1", url="https://example.invalid/r", local_path="/tmp/r", head_sha="0" * 40)


class StubStore:
    def __init__(self, change: VendorChange) -> None:
        self._change = change
        self.statuses: list[tuple[str, str]] = []
        self.rows: list = []

    def get_call_site(self, _id):
        return SITE

    def get_vendor_change(self, _id):
        return self._change

    def set_finding_status(self, finding_id, status):
        self.statuses.append((finding_id, status))

    def record_migration_outcome(self, outcome):
        self.rows.append(outcome)


@dataclass
class StubAdapter:
    prepare_calls: int = 0

    def prepare(self, repo) -> None:
        self.prepare_calls += 1

    def static_verify(self, repo, patch) -> VerifyResult:
        return VerifyResult(ok=True)


@dataclass
class StubRemediator:
    strategy: str = "agent"
    calls: int = 0

    def can_handle(self, finding, change) -> bool:
        return True

    def propose(self, finding, change, site, repo, diagnostics="") -> Patch:
        self.calls += 1
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


def _drive(change: VendorChange, catalogue=CATALOGUE):
    """Run one finding and return the executed node sequence alongside the final state.

    `stream_mode="updates"` yields one mapping per node that ran, keyed by node name, which
    is the sequence itself rather than a proxy for it.
    """
    store = StubStore(change)
    remediator = StubRemediator()
    forge = StubForge()
    adapter = StubAdapter()
    graph = build_graph(
        store=store, adapter=adapter,
        remediator=TieredRemediator([TerminalTier(remediator)], catalogue=catalogue),
        forge=forge, checkpointer=InMemorySaver(), catalogue=catalogue,
    )
    config = {"configurable": {"thread_id": "t1"}}
    payload = {"finding": FINDING, "repo": REPO}

    sequence: list[str] = []
    for update in graph.stream(payload, config=config, stream_mode="updates"):
        sequence.extend(update.keys())

    return sequence, graph.get_state(config).values, store, remediator, forge


# --- the assertion the spec asks for ----------------------------------------------


def test_a_lifecycle_finding_never_enters_the_patch_node():
    """The spec's own words: assert on the node sequence, not on the absence of a diff.

    Against the broken code this fails because `patch` runs, the cascade raises
    `NoPatchWarranted` from inside it, and the run abandons -- which leaves `pr_url` unset
    and would satisfy any weaker assertion.
    """
    sequence, _, _, remediator, forge = _drive(LIFECYCLE_CHANGE)

    assert "patch" not in sequence
    assert remediator.calls == 0
    assert forge.pushes == 0


def test_a_lifecycle_finding_reaches_the_report_node_and_stops():
    sequence, state, _, _, _ = _drive(LIFECYCLE_CHANGE)

    assert sequence[-1] == "report"
    assert state["outcome"] == "reported"
    assert state.get("pr_url") is None


# --- the test that makes the first one mean something ------------------------------


def test_a_patchable_finding_still_reaches_the_patch_node():
    """Without this, an implementation that routes everything away from `patch` passes the
    first test. `request-property-removed` is `kind=existence`, which no tier -1 row
    matches."""
    sequence, state, _, remediator, _ = _drive(PATCHABLE_CHANGE)

    assert "patch" in sequence
    assert "report" not in sequence
    assert remediator.calls == 1
    assert state["outcome"] == "opened"


def test_a_change_the_catalogue_does_not_carry_still_reaches_patch():
    """A deprecation's kind is `deprecation/model-retired`, which no oasdiff catalogue
    holds. Outside the table's jurisdiction is not tier -1, and treating it as one would
    switch off the signal that costs no tokens."""
    outside = LIFECYCLE_CHANGE.model_copy(update={"kind": "deprecation/model-retired"})
    sequence, _, _, remediator, _ = _drive(outside)

    assert "patch" in sequence
    assert remediator.calls == 1


def test_no_catalogue_at_all_leaves_every_finding_on_the_patch_path():
    """The table needs jurisdiction to have an opinion. A graph built without one behaves
    exactly as it did before routing existed."""
    sequence, _, _, remediator, _ = _drive(LIFECYCLE_CHANGE, catalogue=None)

    assert "patch" in sequence
    assert remediator.calls == 1


# --- report-only is not abandonment ------------------------------------------------


def test_a_report_is_not_recorded_as_an_abandonment():
    """`abandon_reason` is where routing learns which change kinds are not mechanically
    safe. "This kind never needed a patch" is not that, and writing it there corrupts the
    signal the pipeline-discipline spec says that field exists to carry.
    """
    _, state, store, _, _ = _drive(LIFECYCLE_CHANGE)

    assert state["outcome"] != "abandoned"
    assert not state.get("abandon_reason")
    assert ("f1", "abandoned") not in store.statuses


def test_a_report_writes_no_attempt_row_to_the_corpus():
    """One `migration_outcome` row is one repair *attempt*. Tier -1 attempted nothing, so
    a row at that grain would be a fabrication -- the same rule that already gives a run
    abandoned before any attempt no row at all.
    """
    _, _, store, _, _ = _drive(LIFECYCLE_CHANGE)

    assert store.rows == []


# --- the tier is decided once, and the branch acts on what was stored ---------------


def test_the_branch_acts_on_the_tier_that_was_stored_rather_than_recomputing_it():
    """`route_after_static` models the discipline: branch on a value a node set on purpose.
    The predicate must read the stored tier, so overwriting it changes where the run goes.
    """
    from sync.remediate import nodes

    assert nodes.route_after_prepare({"prepare_ok": True, "tier": NO_PATCH}) == "report"
    assert nodes.route_after_prepare({"prepare_ok": True, "tier": 2}) == "patch"
    assert nodes.route_after_prepare({"prepare_ok": True}) == "patch"
    # A failed prepare still outranks it: an environment fault is not a routing decision.
    assert nodes.route_after_prepare({"prepare_ok": False, "tier": NO_PATCH}) == "abandon"


def test_the_stored_tier_and_row_survive_to_the_end_of_the_run():
    """The decision has to be readable after the fact, or the corpus follow-up has nothing
    to read. `tier` and the deciding row are both on `RunState`."""
    _, state, _, _, _ = _drive(LIFECYCLE_CHANGE)

    assert state["tier"] == NO_PATCH
    assert state["routing_row"] == "lifecycle"


def test_a_patchable_finding_stores_the_tier_the_table_gave_it():
    _, state, _, _, _ = _drive(PATCHABLE_CHANGE)

    assert state["tier"] != NO_PATCH
    assert state["routing_row"]


def test_the_tier_is_decided_before_the_branch_not_inside_the_patch_node():
    """One place determines the tier and one place stores it. If the decision were made
    inside `patch`, a run that never enters `patch` would carry no tier at all."""
    sequence, state, _, _, _ = _drive(LIFECYCLE_CHANGE)

    assert "patch" not in sequence
    assert state["tier"] == NO_PATCH


# --- the wiring, so the table has jurisdiction in production -----------------------


def test_the_cli_builds_a_remediator_the_table_has_jurisdiction_over():
    """Until this, `build_remediator()` passed no catalogue, so `_tier_for` returned `None`
    for every change and tier -1 could not fire outside a test. A complete, tested
    component with no caller is the failure this repository has already shipped three times.
    """
    from sync.cli import build_remediator
    from sync.remediate.tiered import NoPatchWarranted

    remediator = build_remediator(CATALOGUE)

    with pytest.raises(NoPatchWarranted):
        remediator.propose(FINDING, LIFECYCLE_CHANGE, SITE, REPO)


def test_the_cli_loads_the_catalogue_from_the_pinned_binary():
    """The catalogue is the binary's own checker list, not a hand-kept copy that rots on
    the next oasdiff upgrade."""
    from sync.cli import load_catalogue

    catalogue = load_catalogue()

    assert catalogue["api-deprecated-sunset-missing"]["kind"] == "lifecycle"
    assert "request-property-removed" in catalogue
