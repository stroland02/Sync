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

