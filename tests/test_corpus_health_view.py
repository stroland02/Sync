"""The corpus health view model, distinguishing measured quality axes from unmeasured ones.

Beta's evidence has to be readable before it is quotable, and this view model answers which
quality axes have samples, which have none, and how many runs produced them.
Absence and zero are different answers:
- When n == 0: status is 'unmeasured', has_samples is False, and value is None.
- When n > 0 and value == 0.0: status is 'measured', has_samples is True, and value is 0.0.
"""

from __future__ import annotations

import os
from typing import Any

import pytest
from starlette.testclient import TestClient

from sync.api.app import create_app
from sync.benchmark.axes import Axis, BenchmarkAxes, Counts
from sync.core import MigrationOutcome
from sync.dashboard.fleet import corpus_health
from sync.graph.store import GraphStore

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")


@pytest.fixture()
def store() -> GraphStore:
    store = GraphStore(DSN)
    store.apply_schema()
    with store.transaction():
        store.truncate_all()
    return store


def _outcome(**overrides: Any) -> MigrationOutcome:
    fields: dict[str, Any] = dict(
        finding_id="f-1",
        attempt_index=0,
        vendor_id="stripe",
        from_version="2024-04-10",
        to_version="2024-06-20",
        change_kind="request-property-removed",
        change_severity="breaking",
        language="typescript",
        symbol_shape="stripe.charges.create",
        arg_arity=2,
        response_fields_touched_count=1,
        strategy="codemod",
        tier=0,
        routing_row="unrouted",
        wall_ms=1200,
        input_tokens=500,
        output_tokens=150,
        static_verify_passed=True,
        terminal_status="pr_opened",
        pr_number=41,
        pr_merged=None,
    )
    fields.update(overrides)
    return MigrationOutcome(**fields)


def test_corpus_health_empty_corpus_all_axes_unmeasured(store: GraphStore):
    health = corpus_health(store)

    assert health["summary"]["total_runs"] == 0
    assert health["summary"]["distinct_findings"] == 0
    assert health["summary"]["axes_measured_count"] == 0
    assert health["summary"]["axes_unmeasured_count"] == 5
    assert health["summary"]["has_any_samples"] is False

    axes = {a["name"]: a for a in health["axes"]}
    assert len(axes) == 5

    # Every axis has status='unmeasured', has_samples=False, value=None
    for name in [
        "merge_rate_by_change_kind",
        "merge_rate_by_tier",
        "routing_accuracy",
        "tokens_per_merged_patch",
        "wall_ms_per_merged_patch",
    ]:
        axis = axes[name]
        assert axis["status"] == "unmeasured"
        assert axis["has_samples"] is False
        assert axis["value"] is None
        assert axis["sample_count"] == 0


def test_corpus_health_distinguishes_zero_from_absence(store: GraphStore):
    # Record 1 finding routed to tier 0 that failed verification and escalated to tier 1
    # Routing accuracy denominator n = 1 (routed to tier 0), held at tier 0 = 0 -> value = 0.0 (measured zero!)
    attempt1 = _outcome(
        finding_id="f-1",
        attempt_index=0,
        tier=0,
        static_verify_passed=False,
        terminal_status="escalated",
        pr_number=None,
    )
    attempt2 = _outcome(
        finding_id="f-1",
        attempt_index=1,
        tier=1,
        strategy="agent",
        static_verify_passed=True,
        terminal_status="pr_opened",
        pr_number=42,
        pr_merged=False,  # closed without merge -> merge rate is 0.0 (measured zero!)
    )
    store.record_migration_outcome(attempt1)
    store.record_migration_outcome(attempt2)

    health = corpus_health(store)

    assert health["summary"]["total_runs"] == 2
    assert health["summary"]["distinct_findings"] == 1

    axes = {a["name"]: a for a in health["axes"]}

    # Routing accuracy: n = 1, value = 0.0 -> measured!
    routing = axes["routing_accuracy"]
    assert routing["status"] == "measured"
    assert routing["has_samples"] is True
    assert routing["sample_count"] == 1
    assert routing["value"] == 0.0
    assert routing["provenance"] == "production"

    # Merge rate by change kind: n = 1, value = 0.0 -> measured!
    mr_kind = axes["merge_rate_by_change_kind"]
    assert mr_kind["status"] == "measured"
    assert mr_kind["has_samples"] is True
    assert mr_kind["sample_count"] == 1
    assert mr_kind["provenance"] == "production"
    assert mr_kind["groups"]["request-property-removed"]["value"] == 0.0
    assert mr_kind["groups"]["request-property-removed"]["provenance"] == "production"

    # Tokens per merged patch: 0 merged PRs -> n = 0, value = None -> unmeasured!
    tokens = axes["tokens_per_merged_patch"]
    assert tokens["status"] == "unmeasured"
    assert tokens["has_samples"] is False
    assert tokens["sample_count"] == 0
    assert tokens["value"] is None
    assert tokens["provenance"] == "unmeasured"

    # Wall ms per merged patch: 0 merged PRs -> n = 0, value = None -> unmeasured!
    wall_ms = axes["wall_ms_per_merged_patch"]
    assert wall_ms["status"] == "unmeasured"
    assert wall_ms["has_samples"] is False
    assert wall_ms["sample_count"] == 0
    assert wall_ms["value"] is None
    assert wall_ms["provenance"] == "unmeasured"

    assert health["summary"]["axes_measured_count"] == 3  # merge_rate_by_change_kind, merge_rate_by_tier, routing_accuracy
    assert health["summary"]["axes_unmeasured_count"] == 2  # tokens, wall_ms
    assert health["summary"]["production_attempts"] == 2
    assert health["summary"]["rehearsal_attempts"] == 0


def test_corpus_health_api_route(store: GraphStore):
    attempt = _outcome(
        finding_id="f-1",
        attempt_index=0,
        tier=0,
        static_verify_passed=True,
        terminal_status="pr_opened",
        pr_number=10,
        pr_merged=True,
        input_tokens=1000,
        output_tokens=200,
        wall_ms=5000,
    )
    store.record_migration_outcome(attempt)

    from tests.test_api_routes import _build_app
    from sync.mcp.tools import GraphSurface

    app = _build_app(
        surface=GraphSurface(store),
        corpus_health_reader=lambda: corpus_health(store),
    )
    client = TestClient(app)

    response = client.get("/api/corpus/health")
    assert response.status_code == 200
    data = response.json()

    assert data["summary"]["total_runs"] == 1
    assert data["summary"]["axes_measured_count"] == 5
    assert data["summary"]["axes_unmeasured_count"] == 0
    assert len(data["axes"]) == 5
    for a in data["axes"]:
        assert "provenance" in a
        assert a["provenance"] == "production"


def test_corpus_health_sql_aggregates_match_python_computation(store: GraphStore):
    from sync.benchmark.axes import compute_axes

    # Populate a rich set of attempts: rehearsals, prod runs, mixed outcomes, token counts
    attempt1 = _outcome(
        finding_id="f-1",
        attempt_index=1,
        tier=0,
        static_verify_passed=True,
        terminal_status="pr_opened",
        pr_number=101,
        pr_merged=True,
        input_tokens=800,
        output_tokens=200,
        wall_ms=4500,
    )
    attempt2 = _outcome(
        finding_id="f-2",
        attempt_index=1,
        tier=0,
        static_verify_passed=False,
        terminal_status="retried",
        pr_number=None,
    )
    attempt3 = _outcome(
        finding_id="f-2",
        attempt_index=2,
        tier=2,
        static_verify_passed=True,
        terminal_status="pr_opened",
        pr_number=102,
        pr_merged=False,
        wall_ms=6000,
    )
    attempt_rehearsal = _outcome(
        finding_id="f-3",
        attempt_index=1,
        tier=0,
        static_verify_passed=True,
        terminal_status="pr_opened",
        pr_number=103,
        pr_merged=True,
        is_rehearsal=True,
    )
    for a in [attempt1, attempt2, attempt3, attempt_rehearsal]:
        store.record_migration_outcome(a)

    sql_axes = store.corpus_health_aggregates()
    py_axes = compute_axes(store.migration_outcomes())

    assert sql_axes.counts.attempts == 4
    assert sql_axes.counts.findings == 3
    assert sql_axes.counts.pull_requests_opened == py_axes.counts.pull_requests_opened
    assert sql_axes.counts.pull_requests_merged == py_axes.counts.pull_requests_merged
    assert sql_axes.counts.production_attempts == 3
    assert sql_axes.counts.rehearsal_attempts == 1

    assert sql_axes.routing_accuracy.value == py_axes.routing_accuracy.value
    assert sql_axes.routing_accuracy.n == py_axes.routing_accuracy.n

    assert sql_axes.tokens_per_merged_patch.value == py_axes.tokens_per_merged_patch.value
    assert sql_axes.tokens_per_merged_patch.n == py_axes.tokens_per_merged_patch.n

    assert sql_axes.wall_ms_per_merged_patch.value == py_axes.wall_ms_per_merged_patch.value
    assert sql_axes.wall_ms_per_merged_patch.n == py_axes.wall_ms_per_merged_patch.n




def test_outcomes_by_day_buckets_attempts_on_the_day_they_were_recorded(store: GraphStore):
    """L2 and T4's source: repair attempts tallied by day and terminal status.

    Bucketed in SQL for the reason every other series on this console is: the runs feed pages
    newest-first, so a fold over one page would draw the most recent page and label it the
    history.

    `created_at` rather than `pr_merged_at`: this counts attempts as they happened, and a series
    keyed on the merge date would silently exclude every attempt that never opened a pull
    request -- which is most of them, and the half a reader most needs to see.
    """
    store.record_migration_outcome(_outcome(finding_id="f-1", terminal_status="pr_opened"))
    store.record_migration_outcome(
        _outcome(finding_id="f-2", attempt_index=0, terminal_status="abandoned")
    )

    series = store.outcomes_by_day()

    assert len(series) == 1, "both attempts landed on one day"
    assert series[0]["counts"] == {"pr_opened": 1, "abandoned": 1}


def test_outcomes_by_day_excludes_a_rehearsal(store: GraphStore):
    """A rehearsal is halted before the remote and never counts toward a rate.

    `migration_outcomes` filters them out rather than handing the dimension to every caller, and
    a time series is exactly a place where including them would overstate activity.
    """
    store.record_migration_outcome(_outcome(finding_id="f-1", terminal_status="pr_opened"))
    store.record_migration_outcome(
        _outcome(finding_id="f-2", terminal_status="pr_opened", is_rehearsal=True)
    )

    series = store.outcomes_by_day()

    assert series[0]["counts"] == {"pr_opened": 1}


def test_attempts_by_tier_counts_each_tier_that_occurs(store: GraphStore):
    """L3's source: which repair tier produced each outcome.

    A tier absent from this tally never ran, and is not a tier measured at nought -- the grouping
    returns groups that exist, and a view must not fill a missing tier with a zero.
    """
    store.record_migration_outcome(_outcome(finding_id="f-1", tier=0, terminal_status="pr_opened"))
    store.record_migration_outcome(_outcome(finding_id="f-2", tier=0, terminal_status="abandoned"))
    store.record_migration_outcome(_outcome(finding_id="f-3", tier=2, terminal_status="pr_opened"))

    tally = store.attempts_by_tier()

    assert tally == {0: {"pr_opened": 1, "abandoned": 1}, 2: {"pr_opened": 1}}
    assert 1 not in tally
