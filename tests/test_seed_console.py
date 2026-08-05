"""`scripts/seed_console.py`: the fixture every console verification round has re-derived by hand.

Not a test of the console -- a test of the properties that make the seed script trustworthy as a
fixture: idempotent, exactly reversible, and honest about what it claims to cover. Assertions run
through the view models (`sync.dashboard.queries`, `sync.dashboard.fleet`) rather than through SQL,
because a fixture that satisfies the SQL but not the view model is not a fixture for the console.

Runs against a throwaway database, never the shared `sync` one another agent may be using:

    docker exec sync-postgres-1 psql -U sync -d postgres -c "CREATE DATABASE sync_seed_check"
"""

from __future__ import annotations

import os

import psycopg
import pytest

from scripts.seed_console import MARKER, SCALE_REPO_ID, remove, remove_scale, seed, seed_scale
from sync.dashboard import fleet, graph_views
from sync.dashboard.queries import workflow_state
from sync.graph.store import GraphStore

DSN = os.environ.get(
    "SYNC_SEED_TEST_DSN", "postgresql://sync:sync@localhost:5433/sync_seed_check"
)

_GRAPH_TABLES = (
    "call_site", "vendor_change", "finding", "migration_outcome",
    "observed_call", "observed_shape", "observed_error_window",
)


@pytest.fixture()
def store():
    s = GraphStore(DSN)
    s.apply_schema()
    yield s
    # Belt and braces: a failed assertion mid-test must not leave rows for the next test.
    remove(DSN, DSN)


def _row_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    with psycopg.connect(DSN, autocommit=True) as conn:
        for table in _GRAPH_TABLES:
            counts[table] = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        has_checkpoints = conn.execute("SELECT to_regclass('checkpoints')").fetchone()[0]
        counts["checkpoints"] = (
            conn.execute("SELECT count(*) FROM checkpoints").fetchone()[0]
            if has_checkpoints
            else 0
        )
    return counts


def test_seed_then_remove_restores_row_counts(store):
    before = _row_counts()

    seed(DSN, DSN)
    remove(DSN, DSN)

    assert _row_counts() == before


def test_seeding_twice_does_not_double_row_counts(store):
    seed(DSN, DSN)
    once = _row_counts()

    seed(DSN, DSN)

    assert _row_counts() == once


def test_seeded_repos_and_vendors_carry_the_marker(store):
    seed(DSN, DSN)

    result = fleet.repositories(store)
    assert result["repo_ids"], "seed wrote no repositories"
    assert all(repo_id.startswith(MARKER) for repo_id in result["repo_ids"])
    assert len(result["repo_ids"]) > 1, "the repositories table needs more than one repo_id"


def test_seeded_findings_span_more_than_one_binding_rung(store):
    summary = seed(DSN, DSN)

    # `sync.dashboard.queries.vendor_detail` used to do this join; read straight off the
    # graph now that nothing else routes through that view model.
    rungs = set()
    for finding in store.open_findings():
        site = store.get_call_site(finding.call_site_id)
        if site.vendor_id in summary.vendor_ids:
            rungs.add(finding.binding_rung)

    assert len(rungs) > 1, f"every seeded finding shares one rung: {rungs}"


def test_seeded_finding_detail_has_args_keys_and_a_known_change(store):
    summary = seed(DSN, DSN)

    # `sync.dashboard.queries.finding_detail` used to fan this out; read straight off the
    # graph now that nothing else routes through that view model.
    finding = next(
        (f for f in store.open_findings() if f.id == summary.detailed_finding_id), None
    )
    assert finding is not None, "the detail-screen finding is not open in the graph"
    assert finding.vendor_change_id is not None, "the detail-screen finding has no known change"
    store.get_vendor_change(finding.vendor_change_id)  # raises KeyError if the change is gone

    site = store.get_call_site(finding.call_site_id)
    assert site.args_keys, "the detail-screen finding's call site has no args_keys"
    assert site.response_fields_read, (
        "the detail-screen finding's call site has no response_fields_read"
    )


def test_seeded_corpus_has_more_attempts_than_distinct_findings(store):
    seed(DSN, DSN)

    summary = fleet.corpus_summary(store)

    assert summary["attempts"] > summary["distinct_findings"] > 0


def test_seeded_fleet_has_a_live_run_and_a_terminal_run(store):
    seed(DSN, DSN)

    page = fleet.runs(DSN)
    assert page["items"], "seed wrote no checkpointer runs"

    live = [row for row in page["items"] if row["current_node"] is not None]
    terminal = [row for row in page["items"] if row["outcome"] is not None]
    assert live, "expected at least one run with a live current_node"
    assert terminal, "expected at least one run with a terminal outcome"


def test_seeded_finding_has_more_than_one_generation(store):
    summary = seed(DSN, DSN)

    state = workflow_state(DSN, summary.retried_finding_id)

    assert state is not None
    assert state["generation_count"] > 1


def test_seeded_binding_surface_has_call_sites_on_a_shared_operation(store):
    summary = seed(DSN, DSN)

    vendor_id, operation_id = summary.shared_operation
    result = graph_views.binding_surface(store, vendor_id, operation_id)

    call_sites = result["call_sites"]["items"]
    assert len(call_sites) > 1, (
        "the binding surface's minimum bar is an operation more than one call site is bound to"
    )
    repo_ids = {row["repo_id"] for row in call_sites}
    assert len(repo_ids) > 1, "the shared operation should span more than one repository"


def test_seeded_observed_telemetry_has_calls_shapes_and_error_windows(store):
    summary = seed(DSN, DSN)

    result = graph_views.observed_telemetry(store, summary.repo_ids[0])

    assert result["calls"], "seed wrote no observed calls for this repository"
    assert result["shapes"], "seed wrote no observed shapes reachable from this repository's calls"
    assert result["error_windows"], "seed wrote no observed error windows for this repository"


def test_seeded_observed_calls_include_an_uncorrelated_one(store):
    # `ObservedCall`'s own contract: an uncorrelated call carries an empty `operation_id` and
    # `binding_rung` 'unresolved'. The seed fixture must carry at least one so the screen has
    # something to render for the case the model documents.
    summary = seed(DSN, DSN)

    calls = []
    for repo_id in summary.repo_ids:
        calls.extend(graph_views.observed_telemetry(store, repo_id)["calls"]["items"])

    unresolved = [row for row in calls if row["binding_rung"] == "unresolved"]
    assert unresolved, "seed wrote no uncorrelated observed call"
    assert all(row["operation_id"] == "" for row in unresolved)


def test_seeded_detector_accountability_spans_more_than_one_detector_and_rung(store):
    seed(DSN, DSN)

    result = graph_views.detector_accountability(store)

    detector_names = {row["detector"] for row in result["detectors"]}
    assert len(detector_names) > 1, f"every seeded finding shares one detector: {detector_names}"

    rungs_seen: set[str] = set()
    for row in result["detectors"]:
        rungs_seen |= row["by_rung"].keys()
    assert len(rungs_seen) > 1, f"every seeded finding shares one rung: {rungs_seen}"


def test_remove_without_a_prior_seed_is_a_no_op(store):
    before = _row_counts()

    remove(DSN, DSN)

    assert _row_counts() == before


# --- scale mode --------------------------------------------------------------
#
# These test the properties `--scale` promises rather than an exact row count: convergence on a
# second run, independence from the base fixture, and silence when nobody asked for it. `store`
# already tears down anything tagged `MARKER` afterwards, and `SCALE_REPO_ID` is `f"{MARKER}-scale"`,
# so that teardown reaches the scale rows too without a second fixture.


def test_scale_seeding_twice_converges_rather_than_doubling(store):
    seed_scale(DSN, 50)
    once_call_sites = graph_views.index_coverage(store, SCALE_REPO_ID)["total_call_sites"]
    once_findings = graph_views.detector_accountability(store)["total_open_findings"]

    seed_scale(DSN, 50)

    assert graph_views.index_coverage(store, SCALE_REPO_ID)["total_call_sites"] == once_call_sites
    assert graph_views.detector_accountability(store)["total_open_findings"] == once_findings


def test_scale_rows_are_removable_without_disturbing_the_base_fixture(store):
    seed(DSN, DSN)
    base_repos_before = fleet.repositories(store)
    base_rungs_before = set()
    for finding in store.open_findings():
        site = store.get_call_site(finding.call_site_id)
        if site.repo_id != SCALE_REPO_ID:
            base_rungs_before.add(finding.binding_rung)

    seed_scale(DSN, 50)
    assert SCALE_REPO_ID in fleet.repositories(store)["repo_ids"], "scale seeding wrote no rows"

    remove_scale(DSN)

    assert fleet.repositories(store) == base_repos_before
    base_rungs_after = set()
    for finding in store.open_findings():
        site = store.get_call_site(finding.call_site_id)
        if site.repo_id != SCALE_REPO_ID:
            base_rungs_after.add(finding.binding_rung)
    assert base_rungs_after == base_rungs_before
    assert len(base_rungs_after) > 1, "the base fixture's own multi-rung assertion should still hold"


def test_scale_flag_absent_leaves_the_default_seed_unchanged(store):
    seed(DSN, DSN)

    result = fleet.repositories(store)

    assert SCALE_REPO_ID not in result["repo_ids"], "seed() without --scale wrote scale rows"
