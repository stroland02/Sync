"""The pull request number reaches the corpus, so a delivery can find the row it belongs to.

`record_merge_outcome` matches a delivery to an attempt by `pr_number`, `MigrationOutcome`
declares that column, and nothing ever wrote it. So every row held `None`, the receiver's match
found nothing, and a delivery that verified correctly updated no row -- a receiver, a command
and a verified signature, and still no numerator for the axis the benchmark spec calls the
direct test of the product claim.

The grain is where this goes quietly wrong, so it is tested first-class rather than assumed. One
row is one attempt and a run can make several; only the attempt that opened the pull request has
a number. A merge outcome written against three rows because they shared a run would inflate the
numerator silently, which is worse than being wrong loudly.

The chain is driven end to end here -- a graph run writes the rows, a signed delivery goes
through `record_merge_outcome`, and the axis is computed off what the store actually holds.
Asserting the column alone would prove the write and leave the join it exists for untested.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from sync.benchmark import compute_axes
from sync.core import CallSite, Evidence, Finding, Patch, RepoRef, VendorChange, VerifyResult
from sync.forge.github import PullRequest
from sync.forge.webhook import record_merge_outcome
from sync.graph.store import GraphStore
from sync.remediate.graph import build_graph

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")
FIXTURES = Path(__file__).parent / "fixtures" / "webhook"

# The number the committed delivery names. Shared with the command's tests deliberately: one
# delivery shape, so a change to the fixture is felt by both.
MERGED_PR = 41

SITE = CallSite(
    id="cs1", repo_id="r1", path="src/billing.ts", line=6, col=8, vendor_id="stripe",
    operation_id="PostCharges", symbol="stripe.charges.create",
    args_keys=["amount"], response_fields_read=["status"],
    sdk_version="18.0.0", content_hash="h1",
)
CHANGE = VendorChange(
    vendor_id="stripe", from_version="v1", to_version="v2",
    kind="request-property-removed", operation_id="PostCharges",
    path_ptr="/v1/charges", severity="breaking", source="oasdiff",
    raw={"id": "request-property-removed", "text": "removed the request property `amount`"},
)
FINDING = Finding(
    id="f1", detector="vendor_change", call_site_id="cs1", vendor_change_id="vc1",
    severity="breaking", rationale="PostCharges no longer accepts amount",
)
REPO = RepoRef(repo_id="r1", url="https://example.invalid/r", local_path="/tmp/r", head_sha="0" * 40)


def _ok() -> VerifyResult:
    return VerifyResult(ok=True)


def _fail() -> VerifyResult:
    return VerifyResult(ok=False, diagnostics="src/billing.ts(6,8): error TS2339: nope")


@dataclass
class _Adapter:
    """A typecheck whose verdicts are a script, so a run can be made to retry."""

    verdicts: list[VerifyResult] = field(default_factory=lambda: [_ok()])
    calls: int = 0

    def prepare(self, repo) -> None:
        return None

    def static_verify(self, repo, patch) -> VerifyResult:
        result = self.verdicts[min(self.calls, len(self.verdicts) - 1)]
        self.calls += 1
        return result

    def discard_contaminated_dependencies(self, repo) -> bool:
        return False


@dataclass
class _Remediator:
    strategy: str = "agent"

    def can_handle(self, finding, change) -> bool:
        return True

    def propose(self, finding, change, site, repo, diagnostics="") -> Patch:
        return Patch(diff="--- a\n+++ b\n", strategy=self.strategy, rationale="fix")


@dataclass
class _Forge:
    """A forge that answers with what it created, number and URL together."""

    number: int = MERGED_PR
    opened: int = 0

    def push_branch(self, repo, patch) -> str:
        return "sync/fix-1"

    def await_ci(self, repo, branch) -> tuple[bool, str]:
        return True, "https://example.invalid/run/1"

    def open_pull_request(self, repo, branch, evidence: Evidence) -> PullRequest:
        self.opened += 1
        return PullRequest(
            number=self.number,
            url=f"https://example.invalid/r/pull/{self.number}",
        )

    def delete_branch(self, repo, branch) -> tuple[bool, str]:
        return True, "deleted"


@pytest.fixture()
def store() -> GraphStore:
    """A store holding only this test's rows, truncated rather than assumed empty."""
    store = GraphStore(DSN)
    store.apply_schema()
    with store.transaction():
        store.truncate_all()
    return store


def _run(store: GraphStore, verdicts: list[VerifyResult] | None = None, number: int = MERGED_PR):
    forge = _Forge(number=number)
    graph = build_graph(
        store=_StoreWithFinding(store), adapter=_Adapter(verdicts=verdicts or [_ok()]),
        remediator=_Remediator(), forge=forge, checkpointer=InMemorySaver(),
    )
    state = graph.invoke(
        {"finding": FINDING, "repo": REPO},
        config={"configurable": {"thread_id": f"t-{number}"}},
    )
    return state, forge


class _StoreWithFinding:
    """The real store, plus the two lookups `locate` makes.

    Wrapped rather than seeded: the finding and the change belong to a graph run and not to the
    corpus, and inserting them would test the store's other tables rather than this column.
    Every corpus write goes through to the real store, which is the whole point -- the axis is
    computed off what Postgres actually holds.
    """

    def __init__(self, store: GraphStore) -> None:
        self._store = store

    def get_call_site(self, _id) -> CallSite:
        return SITE

    def get_vendor_change(self, _id) -> VendorChange:
        return CHANGE

    def set_finding_status(self, finding_id, status) -> None:
        return None

    def record_migration_outcome(self, outcome) -> None:
        self._store.record_migration_outcome(outcome)

    def migration_outcomes(self):
        return self._store.migration_outcomes()

    def observed_shapes(self, vendor_id, operation_id):
        return []


def _rows(store: GraphStore):
    return sorted(store.migration_outcomes(), key=lambda row: row.attempt_index)


def _delivery(fixture: str = "pull_request_merged.json") -> bytes:
    """The delivery's exact bytes. The HMAC covers what was sent, so nothing is re-encoded."""
    return (FIXTURES / fixture).read_bytes()


def _signed(body: bytes, secret: bytes) -> str:
    return "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()


@pytest.fixture()
def secret() -> bytes:
    """Generated here. A shared secret has no value this repository is allowed to commit."""
    return secrets.token_hex(32).encode("ascii")


# --- the write ---------------------------------------------------------------------


def test_a_run_that_opens_a_pull_request_records_its_number(store: GraphStore) -> None:
    """Today the column is null on every row, which is why the receiver matches nothing."""
    _run(store)

    assert [row.pr_number for row in _rows(store)] == [MERGED_PR]


def test_the_number_comes_from_the_forge_rather_than_from_the_url(store: GraphStore) -> None:
    """The forge created the pull request and answers with its number.

    Parsing it back out of the URL would be a second implementation of the forge's own
    knowledge -- correct until the URL shape changes, and then wrong by producing a plausible
    number rather than an error, which attaches a merge outcome to somebody else's attempt.
    """
    _, forge = _run(store, number=907)

    assert forge.opened == 1
    assert [row.pr_number for row in _rows(store)] == [907]


# --- the grain ---------------------------------------------------------------------


def test_a_retried_attempt_keeps_its_number_null(store: GraphStore) -> None:
    """One row is one attempt and only the attempt that opened the pull request has a number.

    A single-attempt test cannot see this, and the failure it guards against is silent: a merge
    written against every row of a run would inflate the numerator of the axis the whole chain
    exists to compute.
    """
    _run(store, verdicts=[_fail(), _ok()])

    rows = _rows(store)
    assert len(rows) == 2
    assert rows[0].pr_number is None
    assert rows[1].pr_number == MERGED_PR


def test_an_abandoned_run_records_no_number(store: GraphStore) -> None:
    """No pull request was opened, so there is no number to attach to anything."""
    _run(store, verdicts=[_fail(), _fail(), _fail()])

    assert [row.pr_number for row in _rows(store)] == [None, None, None]


# --- the join this exists for ------------------------------------------------------


def test_a_verified_delivery_finds_the_row_and_sets_pr_merged(
    store: GraphStore, secret: bytes
) -> None:
    """The whole chain: a run writes the number, a signed delivery matches on it, and the
    column the benchmark divides by stops being null.

    Driven through `record_merge_outcome` rather than through the store, because the write on
    its own was never the missing half -- the join was.
    """
    _run(store)
    body = _delivery()

    assert record_merge_outcome(body, _signed(body, secret), secret, store) is True

    row = next(r for r in _rows(store) if r.pr_number == MERGED_PR)
    assert row.pr_merged is True


def test_only_the_attempt_that_opened_it_is_marked_merged(
    store: GraphStore, secret: bytes
) -> None:
    """The grain again, from the reading end. The retried attempt keeps a null `pr_merged`,
    which is what stops one merge counting as two."""
    _run(store, verdicts=[_fail(), _ok()])
    body = _delivery()
    record_merge_outcome(body, _signed(body, secret), secret, store)

    rows = _rows(store)
    assert rows[0].pr_merged is None
    assert rows[1].pr_merged is True


def test_a_delivery_for_an_unknown_number_changes_nothing(
    store: GraphStore, secret: bytes
) -> None:
    """Not the most recent row, and not an error either: humans and other automation open pull
    requests in the same repository and every one of them delivers here."""
    _run(store, number=5150)
    body = _delivery()

    assert record_merge_outcome(body, _signed(body, secret), secret, store) is False
    assert [row.pr_merged for row in _rows(store)] == [None]


# --- the axis ----------------------------------------------------------------------


def test_merge_rate_reports_a_number_and_its_sample_size(
    store: GraphStore, secret: bytes
) -> None:
    """The point of the chain. Before the delivery the axis is unmeasured over zero samples,
    which is honest and is not a measurement; after it the rate is a number with an `n` beside
    it. No threshold is asserted, deliberately -- the spec forbids inventing one, and a test
    that pinned a floor would be that gate arriving by the back door.
    """
    _run(store)

    before = compute_axes(store.migration_outcomes())
    assert before.merge_rate_by_change_kind == {}

    body = _delivery()
    record_merge_outcome(body, _signed(body, secret), secret, store)

    after = compute_axes(store.migration_outcomes())
    rate = after.merge_rate_by_change_kind["request-property-removed"]

    assert rate.value == 1.0
    assert rate.n == 1
    assert after.counts.pull_requests_opened == 1
    assert after.counts.pull_requests_merged == 1


def test_the_forge_refuses_a_response_carrying_no_number() -> None:
    """The one way asking GitHub could go wrong, and it raises rather than defaulting.

    A zero or a `None` written into the corpus is a row nothing can ever match -- the silent
    half of the failure this whole change replaces -- so an answer without a number is an
    error rather than a value.
    """
    from sync.forge.github import GitHubForge

    forge = GitHubForge()
    forge._run = lambda args, cwd: "{}" if args[1:3] == ["pr", "view"] else "https://x/pull/9"

    with pytest.raises(RuntimeError, match="no number"):
        forge.open_pull_request(REPO, "sync/x", Evidence(
            spec_diff={}, changelog_entry="e", call_sites=[], ci_run_url="",
        ))


def test_a_forged_delivery_still_changes_nothing_now_that_a_row_could_match(
    store: GraphStore, secret: bytes
) -> None:
    """Recording the number makes the receiver able to find a row, which is exactly when the
    signature check starts mattering. Asserted on the row rather than on the raise."""
    _run(store)
    body = _delivery()

    with pytest.raises(Exception):
        record_merge_outcome(body, _signed(body, b"not-the-secret"), secret, store)

    assert [row.pr_merged for row in _rows(store)] == [None]
