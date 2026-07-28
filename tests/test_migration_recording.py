"""Wiring the corpus into the remediation graph, so `migration_outcome` actually fills.

`bf675b6` built the table, the model and the store methods, and nothing in `src/` called
them. A table that exists and stays empty is the same failure as not having built it: the
corpus cannot be backfilled, so every run that finishes without writing is a row that can
never be recovered.

The grain under test is one row per *attempt*. A finding retried three times writes three
rows and `attempt_index` says which is which, so a query counting findings by counting
rows is wrong. `static_attempts` is the counter that carries it: it increments once per
`make_patch` call, and `route_after_ci` already treats it as the bound on total patch
attempts for the whole run. `ci_attempts` counts CI polls, and a run can spend its whole
budget without ever reaching CI.

Abandoned attempts are the negative class. A corpus of successes alone can compute no
precision and evaluate no future router, so an abandoned run writes its row and carries
`abandon_reason` on it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from sync.core import CallSite, Finding, MigrationOutcome, Patch, RepoRef, VendorChange, VerifyResult
from sync.remediate.graph import build_graph
from sync.remediate.tiered import CannotPatch, TerminalTier, TieredRemediator

SALT = "corpus-salt-for-tests"

SITE = CallSite(
    repo_id="r1", path="src/billing.ts", line=6, col=8, vendor_id="stripe",
    operation_id="PostCharges", symbol="stripe.charges.create",
    args_keys=["amount", "currency"], response_fields_read=["status"],
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


class RecordingStore:
    """A store that keeps the corpus in memory, so the grain is assertable without Postgres."""

    def __init__(self, locate_error: Exception | None = None) -> None:
        self.rows: list[MigrationOutcome] = []
        self.status: str | None = None
        self._locate_error = locate_error

    def get_call_site(self, _id):
        if self._locate_error is not None:
            raise self._locate_error
        return SITE

    def get_vendor_change(self, _id):
        return CHANGE

    def set_finding_status(self, _id, status):
        self.status = status

    def record_migration_outcome(self, outcome: MigrationOutcome) -> None:
        self.rows.append(outcome)


class ExplodingStore(RecordingStore):
    """A corpus write that fails. Losing one row is bad; losing the pull request because
    bookkeeping failed is worse."""

    def record_migration_outcome(self, outcome: MigrationOutcome) -> None:
        raise RuntimeError("relation \"migration_outcome\" does not exist")


@dataclass
class StubAdapter:
    verdicts: list[VerifyResult] = field(default_factory=lambda: [_ok()])
    calls: int = 0

    def prepare(self, repo) -> None:
        pass

    def static_verify(self, repo, patch) -> VerifyResult:
        result = self.verdicts[min(self.calls, len(self.verdicts) - 1)]
        self.calls += 1
        return result


@dataclass
class StubRemediator:
    strategy: str = "agent"
    calls: int = 0
    diff: str = "--- a\n+++ b\n"

    def can_handle(self, finding, change) -> bool:
        return True

    def propose(self, finding, change, site, repo, diagnostics="") -> Patch:
        self.calls += 1
        return Patch(diff=self.diff, strategy=self.strategy, rationale="fix")


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

    def delete_branch(self, repo, branch) -> tuple[bool, str]:
        return True, "deleted"


@pytest.fixture(autouse=True)
def _salt(monkeypatch):
    monkeypatch.setenv("SYNC_CORPUS_SALT", SALT)


def _run(adapter=None, remediator=None, forge=None, store=None):
    store = store if store is not None else RecordingStore()
    graph = build_graph(
        store=store, adapter=adapter or StubAdapter(),
        remediator=remediator or StubRemediator(), forge=forge or StubForge(),
        checkpointer=InMemorySaver(),
    )
    state = graph.invoke(
        {"finding": FINDING, "repo": REPO},
        config={"configurable": {"thread_id": "t1"}},
    )
    return state, store


# --- the grain --------------------------------------------------------------------


def test_a_clean_run_writes_exactly_one_row():
    state, store = _run()

    assert state["outcome"] == "opened"
    assert len(store.rows) == 1
    assert store.rows[0].attempt_index == 1
    assert store.rows[0].finding_id == "f1"


def test_a_finding_that_took_three_tries_writes_three_rows():
    """The grain the corpus spec insists on. One row per attempt, not per finding --
    a query counting findings by counting rows is wrong, and it is wrong quietly."""
    _, store = _run(adapter=StubAdapter(verdicts=[_fail(), _fail(), _ok()]))

    assert [row.attempt_index for row in store.rows] == [1, 2, 3]


def test_the_attempts_before_the_last_are_marked_as_retried():
    _, store = _run(adapter=StubAdapter(verdicts=[_fail(), _ok()]))

    assert [row.terminal_status for row in store.rows] == ["retried", "opened"]


def test_a_run_abandoned_before_any_attempt_writes_no_row():
    """Zero attempts is zero rows. Conflating "abandoned before attempting" with
    "attempted and failed" would make every rate computed off this table wrong; the
    finding's status and `abandon_reason` already record that it was abandoned."""
    store = RecordingStore(locate_error=KeyError("vc1"))
    state, store = _run(store=store)

    assert state["outcome"] == "abandoned"
    assert store.rows == []


# --- the negative class -----------------------------------------------------------


def test_an_abandoned_run_writes_a_row_carrying_its_reason():
    """A corpus of successes alone can compute no precision and evaluate no router."""
    _, store = _run(adapter=StubAdapter(verdicts=[_fail("error TS2339: no such field")]))

    last = store.rows[-1]
    assert last.terminal_status == "abandoned"
    assert last.abandon_reason
    assert "TS2339" in last.abandon_reason


def test_an_abandoned_run_records_every_attempt_it_spent():
    _, store = _run(adapter=StubAdapter(verdicts=[_fail()]))

    assert [row.attempt_index for row in store.rows] == [1, 2, 3]
    assert [row.terminal_status for row in store.rows] == ["retried", "retried", "abandoned"]


def test_a_failed_static_verification_is_recorded_as_such():
    _, store = _run(adapter=StubAdapter(verdicts=[_fail(), _ok()]))

    assert store.rows[0].static_verify_passed is False
    assert store.rows[1].static_verify_passed is True


def test_a_red_ci_run_is_recorded_on_the_attempt_that_produced_it():
    _, store = _run(forge=StubForge(ci_results=[False, True]))

    assert store.rows[0].ci_result == "failed"
    assert store.rows[1].ci_result == "passed"


def test_an_attempt_that_never_reached_ci_records_no_ci_result():
    """None means "did not run", which is a different fact from "ran and failed". A
    column that flattens them cannot be used to compute anything about CI."""
    _, store = _run(adapter=StubAdapter(verdicts=[_fail(), _ok()]))

    assert store.rows[0].ci_result is None


# --- strategy and tier, which are the whole point of splitting merge rate ----------


def test_an_agent_patch_records_the_agent_strategy_and_tier():
    _, store = _run(remediator=StubRemediator(strategy="agent"))

    assert store.rows[0].strategy == "agent"
    assert store.rows[0].tier == 2


def test_a_codemod_patch_records_the_codemod_strategy_and_tier():
    """The claim this table exists to check is that mechanical changes land more often
    than agent-written ones. A defaulted column makes that unanswerable."""
    _, store = _run(remediator=StubRemediator(strategy="codemod"))

    assert store.rows[0].strategy == "codemod"
    assert store.rows[0].tier == 0


def test_the_strategy_recorded_is_the_tier_that_ran_not_the_cascade_label():
    """`TieredRemediator.strategy` is "tiered", which is composition rather than a
    strategy anyone chose. Stamping it would erase the distinction the split measures."""
    cascade = TieredRemediator([StubRemediator(strategy="codemod")])
    _, store = _run(remediator=cascade)

    assert store.rows[0].strategy == "codemod"


def test_a_tier_that_ran_and_raised_is_recorded_against_that_tier():
    """The information exists at the raise site, so discarding it is a choice rather
    than a limitation."""

    @dataclass
    class Exploding(StubRemediator):
        def propose(self, finding, change, site, repo, diagnostics=""):
            self.calls += 1
            raise RuntimeError("agent run failed (error_max_turns)")

    cascade = TieredRemediator([Exploding(strategy="agent")])
    _, store = _run(remediator=cascade)

    assert store.rows[-1].strategy == "agent"
    assert store.rows[-1].tier == 2
    assert "error_max_turns" in store.rows[-1].abandon_reason


def test_no_tier_applying_at_all_writes_no_row():
    """Distinct from a tier that ran and failed. Nothing was attempted, so there is no
    strategy to name and no attempt to describe -- squashing the two would put a made-up
    strategy in the column the corpus splits on."""

    @dataclass
    class Declines(StubRemediator):
        def can_handle(self, finding, change) -> bool:
            return False

    cascade = TieredRemediator([Declines(strategy="codemod")])
    state, store = _run(remediator=cascade)

    assert state["outcome"] == "abandoned"
    assert store.rows == []


# --- wall_ms, measured rather than defaulted --------------------------------------


def test_wall_ms_is_measured_rather_than_defaulted(monkeypatch):
    """A defaulted duration is worse than a missing one: it looks like a measurement."""

    ticks = iter([1000.0, 1000.25, 1000.5, 1000.75, 1001.0, 1001.5, 1002.0, 1002.5])
    monkeypatch.setattr(
        "sync.remediate.corpus.now", lambda: next(ticks, 1003.0)
    )

    _, store = _run()
    assert store.rows[0].wall_ms == 250


# --- a recording failure must never fail a run -------------------------------------


def test_a_corpus_write_that_raises_does_not_fail_the_run(caplog):
    """Losing one row is bad. Losing the pull request because bookkeeping failed is worse."""
    state, _ = _run(store=ExplodingStore())

    assert state["outcome"] == "opened"
    assert state["pr_url"] == "https://github.com/o/r/pull/1"


def test_a_corpus_write_that_raises_is_visible_in_the_logs(caplog):
    """Silent loss is the failure mode that makes a corpus untrustworthy: nothing looks
    wrong and every rate computed from it is quietly short."""
    import logging

    with caplog.at_level(logging.WARNING, logger="sync.remediate.corpus"):
        _run(store=ExplodingStore())

    assert any("migration_outcome" in record.getMessage() for record in caplog.records)


def test_a_store_with_no_corpus_method_does_not_fail_the_run():
    """The store is a protocol boundary, and an older one is a missing row rather than a
    crashed pipeline."""

    class OldStore:
        def get_call_site(self, _id): return SITE
        def get_vendor_change(self, _id): return CHANGE
        def set_finding_status(self, _id, status): pass

    state, _ = _run(store=OldStore())
    assert state["outcome"] == "opened"


# --- the salt, which must never be a published constant ---------------------------


def test_no_salt_configured_writes_no_row_and_says_so(monkeypatch, caplog):
    """This project is open core. A constant fallback in the source is a published
    constant, and a hash salted with a published constant is reversible by anyone who can
    read the repository -- so an unconfigured salt omits the row rather than weakening it.
    """
    import logging

    monkeypatch.delenv("SYNC_CORPUS_SALT", raising=False)

    with caplog.at_level(logging.WARNING, logger="sync.remediate.corpus"):
        state, store = _run()

    assert state["outcome"] == "opened"
    assert store.rows == []
    assert any("SYNC_CORPUS_SALT" in record.getMessage() for record in caplog.records)


def test_the_salt_reaches_the_hashes_rather_than_being_ignored():
    """A salt that is read and then not used is the same hole as no salt at all."""
    from sync.core.corpus import hash_arg_keys

    _, store = _run()
    assert store.rows[0].arg_key_hashes == hash_arg_keys(["amount", "currency"], salt=SALT)


# --- nothing customer-identifying reaches the row ----------------------------------


def test_the_row_carries_no_diff_and_no_file_path():
    """The reduction lives in `from_attempt`, and this asserts the graph actually goes
    through it rather than assembling a row of its own."""
    _, store = _run()
    row = store.rows[0]

    serialised = row.model_dump_json()
    assert "billing.ts" not in serialised
    assert "--- a" not in serialised
    assert row.symbol_shape == "<client>.<resource>.<verb>"
    assert row.arg_arity == 2


def test_a_run_abandoned_at_prepare_writes_no_row(caplog):
    """The other zero-attempt path, and the one that reaches further in.

    `locate` succeeded, so the site and change are on the state and a row could be built
    from them -- only `static_attempts` says no attempt was made. A guard that stops at
    "is the site present" would let this one through.
    """

    @dataclass
    class FailingAdapter(StubAdapter):
        def prepare(self, repo) -> None:
            raise RuntimeError("npm install failed: ENOENT: registry unreachable")

    import logging

    with caplog.at_level(logging.DEBUG, logger="sync.remediate.corpus"):
        state, store = _run(adapter=FailingAdapter())

    assert state["outcome"] == "abandoned"
    assert store.rows == []
    # Said as "never attempted", not as "no tier applied". They are different facts and an
    # operator reading logs has only the message to tell them apart.
    assert any("before any attempt" in r.getMessage() for r in caplog.records)


def test_a_ci_verdict_does_not_leak_into_the_attempt_after_it():
    """Attempt 1 goes red at CI and retries; attempt 2 fails typechecking and never
    reaches CI. If the verdict were not cleared when an attempt starts, attempt 2 would
    carry attempt 1's "failed" and the corpus would report a CI result for a patch CI
    never saw.
    """
    _, store = _run(
        adapter=StubAdapter(verdicts=[_ok(), _fail(), _fail()]),
        forge=StubForge(ci_results=[False]),
    )

    assert store.rows[0].ci_result == "failed"
    assert [row.ci_result for row in store.rows[1:]] == [None] * (len(store.rows) - 1)
