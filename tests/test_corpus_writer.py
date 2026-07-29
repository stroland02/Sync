"""The corpus writer's contract, and the shape of the hole where a success should be.

Two facts the first whole-pipeline run recorded about the corpus, pinned here so neither can
go quiet.

The writer used to be reached by `getattr(store, "record_migration_outcome", None)` and a
warning when it was absent. That is a soft lookup on the single write the entire benchmark
depends on: rename the method and recording stops, the warning scrolls past in a log nobody
reads, and every axis keeps reporting null with a sample size of zero. Null-because-nothing-ran
and null-because-the-writer-vanished are then indistinguishable, and the measurement that tests
the product claim goes quiet without anything going red.

And the positive class is unreachable without a push: only `open_pr` records a success, and it
takes a forge. The tests at the end of this file document that rather than fix it -- the wiring
belongs to another task -- and they are written to fail when it closes.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from sync.benchmark import compute_axes
from sync.core import CallSite, Finding, MigrationOutcome, Patch, VendorChange
from sync.remediate.corpus import CorpusWriterMissing, make_recorder

NODES = Path(__file__).resolve().parents[1] / "src" / "sync" / "remediate" / "nodes.py"

FINDING = Finding(id="f-1", detector="vendor_change", call_site_id="cs-1",
                  severity="breaking", rationale="status removed")
SITE = CallSite(
    id="cs-1", repo_id="r", path="src/billing.ts", line=12, col=4, vendor_id="stripe",
    operation_id="PostCharges", symbol="stripe.charges.create", args_keys=["amount"],
    response_fields_read=["status"], sdk_version="18.0.0", content_hash="h",
)
CHANGE = VendorChange(
    id="vc-1", vendor_id="stripe", from_version="a", to_version="b",
    kind="response-property-removed", operation_id="PostCharges", path_ptr="/v1/charges",
    severity="breaking", source="oasdiff", raw={"text": "removed the `status` property"},
)


class Store:
    """A store that satisfies the writer contract, and records what it was handed."""

    def __init__(self):
        self.rows: list[MigrationOutcome] = []

    def record_migration_outcome(self, outcome: MigrationOutcome) -> None:
        self.rows.append(outcome)


class Storeless:
    """A store-shaped object that does not satisfy it. The rename this guards against."""

    def record_migration_outcomes(self, outcome) -> None:  # note the plural
        raise AssertionError("the recorder must not find this")


def _state(**over) -> dict:
    state = dict(
        finding=FINDING, site=SITE, change=CHANGE,
        static_attempts=1, attempt_strategy="codemod", attempt_started_at=None,
        attempt_static_passed=True, attempt_ci_result=None, diagnostics="",
    )
    state.update(over)
    return state


# --- part one: the writer's absence is loud ---------------------------------------


def test_a_store_without_the_writer_fails_at_construction():
    """The soft lookup this replaces produced a run that looked successful and recorded
    nothing. Failing here, where `build_graph` calls `make_recorder`, is before any node has
    run and so before there is a run to lose."""
    with pytest.raises(CorpusWriterMissing):
        make_recorder(Storeless())


def test_the_failure_names_the_method_that_is_missing():
    """A reader should not have to diff two versions of the store to work out why recording
    stopped."""
    with pytest.raises(CorpusWriterMissing, match="record_migration_outcome"):
        make_recorder(Storeless())


def test_the_failure_names_the_object_that_lacks_it():
    """Which store was handed in is the other half of the answer -- the pipeline builds one
    from a DSN and tests hand in their own."""
    with pytest.raises(CorpusWriterMissing, match="Storeless"):
        make_recorder(Storeless())


@pytest.mark.parametrize("bound", [None, "record_migration_outcome", 0], ids=["none", "str", "int"])
def test_an_attribute_that_is_not_callable_is_not_a_writer(bound):
    """`hasattr` is satisfied by anything bound to that name -- a column, a `None`, a leftover
    string. The contract is a method, so the check is callability rather than presence.

    Parametrized because `None` alone cannot tell the two apart: a presence check rejects it
    too, so a test using only `None` passes against the weaker implementation and proves
    nothing about which one is there.
    """
    store = Store()
    store.record_migration_outcome = bound

    with pytest.raises(CorpusWriterMissing):
        make_recorder(store)


def test_a_store_with_the_writer_records_the_row():
    """Without this, part one is satisfied by something that rejects every store. The
    contract has to admit the real one."""
    store = Store()

    assert make_recorder(store)(_state(), terminal_status="opened") is True
    assert len(store.rows) == 1
    assert store.rows[0].finding_id == "f-1"


def test_a_write_that_fails_still_never_fails_the_run():
    """The decision the module already carried, kept: losing one row is bad, losing the pull
    request because bookkeeping failed is worse. The contract moved to construction precisely
    so this could stay -- a check on every write would have had to choose between being loud
    and being safe, and at construction there is no run in flight to lose.
    """
    class Failing(Store):
        def record_migration_outcome(self, outcome):
            raise RuntimeError("the database went away")

    assert make_recorder(Failing())(_state(), terminal_status="opened") is False


def test_the_grain_is_one_row_per_attempt():
    """One finding, two attempts, two rows. A rate dividing by rows where it means findings is
    wrong quietly, which is the mistake the discipline spec names first."""
    store = Store()
    record = make_recorder(store)

    record(_state(static_attempts=1), terminal_status="retried")
    record(_state(static_attempts=2), terminal_status="abandoned", abandon_reason="tsc failed")

    assert [row.attempt_index for row in store.rows] == [1, 2]
    assert {row.finding_id for row in store.rows} == {"f-1"}


# --- part two: what recording a success actually requires -------------------------
#
# These document today's behaviour. **Each is written to fail when the gap closes, and that
# failing is the point** -- delete or invert the one that fires, do not adjust it back to
# green.


def _terminal_statuses_recorded_by(path: Path) -> set[str]:
    """Every literal a `record(...)` call in `path` passes as `terminal_status`.

    Read from the syntax rather than by running the graph, because the fact being asserted is
    exactly the one no run can reach: a success needs a forge, so a test that could observe it
    behaviourally would be a test that pushes.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg == "terminal_status" and isinstance(keyword.value, ast.Constant):
                found.add(keyword.value.value)
    return found


def test_open_pr_is_the_only_node_that_records_a_success():
    """Three call sites and one of them is terminal-and-successful. `retried` closes an attempt
    that another is about to supersede, `abandoned` is the negative class, and `opened` is
    written after `forge.open_pull_request` returns a URL -- so the whole positive class of the
    corpus sits behind a push.

    Fails when a fourth status appears, which is what closing this gap looks like.
    """
    assert _terminal_statuses_recorded_by(NODES) == {"retried", "opened", "abandoned"}


def test_the_status_scan_would_notice_a_fourth_call_site(tmp_path):
    """The gap test above is only worth having if it can fail. Proven against a synthetic
    module rather than by editing `nodes.py`, which another task owns -- a mutation there
    would be a collision, and the property under test belongs to the scan either way.
    """
    module = tmp_path / "nodes_with_a_fourth.py"
    module.write_text(
        "def open_pr(state):\n"
        "    record(state, terminal_status='opened')\n"
        "def verified(state):\n"
        "    record(state, terminal_status='verified')\n",
        encoding="utf-8",
    )

    assert _terminal_statuses_recorded_by(module) == {"opened", "verified"}


def test_a_verified_but_unpushed_outcome_is_already_representable():
    """The wall that stopped tier -1 does not stand here, and that is worth knowing before
    anyone proposes a migration. `MigrationOutcome.terminal_status` is `str | None` and the
    column is `TEXT` -- only `strategy` is a two-value Literal, and a verified patch still has
    a strategy that produced it. So recording a success at the verification boundary needs a
    node to call `record`, and no change to the model or the schema.
    """
    store = Store()

    assert make_recorder(store)(_state(), terminal_status="verified") is True
    assert store.rows[0].terminal_status == "verified"
    assert store.rows[0].pr_number is None


def test_a_verified_row_would_unblock_routing_accuracy_and_not_merge_rate():
    """Which of the five axes a verification-boundary row buys, computed rather than argued.

    Routing accuracy divides by findings routed to tier 0 and reads `static_verify_passed`, so
    a verified tier-0 attempt is exactly its numerator -- and today that attempt writes no row
    at all unless it pushes, which is why the axis can only ever see the failures. Merge rate
    and cost per merged patch divide by pull requests and stay null until a real webhook
    populates `pr_merged`; no amount of verification data reaches them.
    """
    verified = MigrationOutcome.from_attempt(
        finding_id="f-1", attempt_index=1, site=SITE, change=CHANGE,
        patch=Patch(diff="", strategy="codemod", rationale=""),
        tier=0, wall_ms=10, salt="s",
        static_verify_passed=True, terminal_status="verified",
    )

    axes = compute_axes([verified])

    assert axes.routing_accuracy.value == 1.0
    assert axes.routing_accuracy.n == 1
    assert axes.merge_rate_by_tier == {}
    assert axes.tokens_per_merged_patch.value is None
