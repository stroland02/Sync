"""View-model queries for the fleet screen: every run, the repair record, the repo roll-up.

Follows `tests/test_dashboard_queries.py`'s fixture pattern for the checkpointer side --
`PostgresSaver.put`'s row shape, and the thread-id convention `sync.cli` writes:
`{finding_id}:{run_id or head_sha[:12]}:{generation}`.
"""

import json
import os

import psycopg
import pytest

from sync.core import CallSite, Finding, MigrationOutcome
from sync.dashboard.fleet import corpus_summary, repositories, runs
from sync.dashboard.queries import _FINISHED
from sync.graph.store import GraphStore

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")

FINDING_ID = "f" * 32


@pytest.fixture()
def store():
    s = GraphStore(DSN)
    s.apply_schema()
    s.truncate_all()
    return s


def _site(**kw) -> CallSite:
    base = dict(
        repo_id="r1",
        path="src/billing.ts",
        line=42,
        col=8,
        vendor_id="stripe",
        operation_id="PostCharges",
        symbol="stripe.charges.create",
        sdk_version="14.0.0",
        content_hash="hash-42",
    )
    base.update(kw)
    return CallSite(**base)


def _finding(call_site_id: str, **kw) -> Finding:
    base = dict(
        detector="vendor-change",
        claim="request-parameter-removed",
        call_site_id=call_site_id,
        severity="breaking",
        rationale="the call passes a parameter the vendor removed",
        binding_rung="static",
    )
    base.update(kw)
    return Finding(**base)


def _outcome(**kw) -> MigrationOutcome:
    base = dict(
        finding_id=FINDING_ID,
        attempt_index=0,
        vendor_id="stripe",
        from_version="2024-04-10",
        to_version="2024-06-20",
        change_kind="request-parameter-removed",
        change_severity="breaking",
        language="typescript",
        symbol_shape="stripe.charges.create(object)",
        arg_arity=1,
        response_fields_touched_count=1,
        strategy="codemod",
        tier=1,
        routing_row="request-parameter-removed",
        wall_ms=100,
    )
    base.update(kw)
    return MigrationOutcome(**base)


# --- the checkpointer side ---------------------------------------------------


@pytest.fixture()
def checkpointer_tables():
    from langgraph.checkpoint.postgres import PostgresSaver

    with PostgresSaver.from_conn_string(DSN) as saver:
        saver.setup()
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("TRUNCATE checkpoints, checkpoint_blobs, checkpoint_writes")
    yield


def _insert_checkpoint(
    thread_id: str,
    checkpoint_id: str,
    *,
    channel_values: dict,
    checkpoint_ns: str = "",
    ts: str | None = "2026-07-30T12:00:00.000000+00:00",
    step: int = 0,
) -> None:
    checkpoint = {
        "v": 4,
        "id": checkpoint_id,
        "channel_values": channel_values,
        "channel_versions": {},
        "versions_seen": {"__input__": {}},
    }
    if ts is not None:
        checkpoint["ts"] = ts
    metadata = {"source": "loop", "step": step, "parents": {}}
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute(
            """
            INSERT INTO checkpoints (thread_id, checkpoint_ns, checkpoint_id,
                                     parent_checkpoint_id, checkpoint, metadata)
            VALUES (%s, %s, %s, NULL, %s, %s)
            """,
            (thread_id, checkpoint_ns, checkpoint_id, json.dumps(checkpoint), json.dumps(metadata)),
        )


def _version(n: int) -> str:
    return f"{n:032}.0.123456"


def test_runs_returns_one_row_per_thread_not_per_finding(checkpointer_tables):
    # Two generations of the same finding: two threads, so two rows -- the grain rule.
    _insert_checkpoint(
        f"{FINDING_ID}:abc123def456:0",
        "1f069000-0000-6000-8000-000000000001",
        channel_values={"outcome": "abandoned", "abandon_reason": "generation 0 failed"},
    )
    _insert_checkpoint(
        f"{FINDING_ID}:abc123def456:1",
        "1f069000-0000-6000-8000-000000000002",
        channel_values={"outcome": "opened"},
    )

    page = runs(DSN)

    assert page["total"] == 2
    assert len(page["items"]) == 2


def test_runs_returns_the_newest_checkpoint_per_thread_and_no_older_one(checkpointer_tables):
    thread = f"{FINDING_ID}:abc123def456:0"
    _insert_checkpoint(
        thread, "1f069000-0000-6000-8000-000000000001",
        channel_values={"outcome": "abandoned", "abandon_reason": "old checkpoint"},
    )
    _insert_checkpoint(
        thread, "1f069000-0000-6000-8000-000000000002",
        channel_values={"outcome": "opened"},
    )

    page = runs(DSN)

    assert page["total"] == 1
    assert page["items"][0]["outcome"] == "opened"


def test_runs_filters_out_a_subgraph_namespace(checkpointer_tables):
    thread = f"{FINDING_ID}:abc123def456:0"
    _insert_checkpoint(
        thread, "1f069000-0000-6000-8000-000000000001",
        channel_values={"outcome": "opened"},
        checkpoint_ns="",
    )
    _insert_checkpoint(
        thread, "1f069000-0000-6000-8000-000000000009",
        channel_values={"outcome": "abandoned", "abandon_reason": "subgraph noise"},
        checkpoint_ns="patch:subgraph",
    )

    page = runs(DSN)

    assert page["total"] == 1
    assert page["items"][0]["outcome"] == "opened"


@pytest.mark.parametrize("value", sorted(_FINISHED))
def test_runs_reports_outcome_for_a_finished_value(checkpointer_tables, value):
    _insert_checkpoint(
        f"{FINDING_ID}:abc123def456:0",
        "1f069000-0000-6000-8000-000000000001",
        channel_values={"outcome": value},
    )

    page = runs(DSN)

    assert page["items"][0]["outcome"] == value


def test_runs_reports_none_for_a_run_still_in_flight(checkpointer_tables):
    # `locate` writes `outcome: "running"` on the first hop of every run -- a Critical earlier
    # in this milestone treated any non-null outcome as terminal and rendered every live run
    # as finished. `running` must read back as `None`, not as itself.
    _insert_checkpoint(
        f"{FINDING_ID}:abc123def456:0",
        "1f069000-0000-6000-8000-000000000001",
        channel_values={"outcome": "running"},
    )

    page = runs(DSN)

    assert page["items"][0]["outcome"] is None


def test_runs_reports_last_checkpoint_at_from_the_checkpoint_ts(checkpointer_tables):
    _insert_checkpoint(
        f"{FINDING_ID}:abc123def456:0",
        "1f069000-0000-6000-8000-000000000001",
        channel_values={"outcome": "opened"},
        ts="2026-08-01T09:30:00.000000+00:00",
    )

    page = runs(DSN)

    assert page["items"][0]["last_checkpoint_at"] == "2026-08-01T09:30:00.000000+00:00"


def test_runs_reports_none_last_checkpoint_at_when_ts_is_absent(checkpointer_tables):
    _insert_checkpoint(
        f"{FINDING_ID}:abc123def456:0",
        "1f069000-0000-6000-8000-000000000001",
        channel_values={"outcome": "opened"},
        ts=None,
    )

    page = runs(DSN)

    assert page["items"][0]["last_checkpoint_at"] is None


def test_runs_recovers_finding_id_as_the_first_colon_segment(checkpointer_tables):
    # A run-id that itself contains a colon must not fool a naive split(':').
    _insert_checkpoint(
        f"{FINDING_ID}:run:with:colons:0",
        "1f069000-0000-6000-8000-000000000001",
        channel_values={"outcome": "opened"},
    )

    page = runs(DSN)

    assert page["items"][0]["finding_id"] == FINDING_ID


def test_runs_paginates_with_a_null_next_offset_on_the_last_page(checkpointer_tables):
    for i in range(3):
        _insert_checkpoint(
            f"{FINDING_ID}:run{i}:0",
            f"1f069000-0000-6000-8000-00000000000{i}",
            channel_values={"outcome": "opened"},
        )

    first = runs(DSN, limit=2, offset=0)
    assert first["total"] == 3
    assert len(first["items"]) == 2
    assert first["next_offset"] == 2

    second = runs(DSN, limit=2, offset=2)
    assert len(second["items"]) == 1
    assert second["next_offset"] is None


def test_runs_floors_a_limit_below_one(checkpointer_tables):
    for i in range(2):
        _insert_checkpoint(
            f"{FINDING_ID}:run{i}:0",
            f"1f069000-0000-6000-8000-00000000000{i}",
            channel_values={"outcome": "opened"},
        )

    page = runs(DSN, limit=0, offset=0)

    assert len(page["items"]) == 1


def test_runs_is_an_empty_page_when_the_checkpointer_has_no_tables():
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute(
            "DROP TABLE IF EXISTS checkpoints, checkpoint_blobs, "
            "checkpoint_writes, checkpoint_migrations"
        )

    page = runs(DSN)

    assert page == {"items": [], "total": 0, "next_offset": None}


# --- the corpus -----------------------------------------------------------


def test_corpus_summary_separates_attempts_from_distinct_findings(store):
    store.record_migration_outcome(_outcome(attempt_index=0, terminal_status="abandoned"))
    store.record_migration_outcome(_outcome(attempt_index=1, terminal_status="abandoned"))
    store.record_migration_outcome(_outcome(attempt_index=2, terminal_status="opened"))

    summary = corpus_summary(store)

    assert summary["attempts"] == 3
    assert summary["distinct_findings"] == 1


def test_corpus_summary_breaks_down_by_terminal_status_strategy_and_tier(store):
    store.record_migration_outcome(
        _outcome(attempt_index=0, terminal_status="opened", strategy="codemod", tier=1)
    )
    store.record_migration_outcome(
        _outcome(
            finding_id="g" * 32, attempt_index=0,
            terminal_status="abandoned", strategy="agent", tier=2,
        )
    )
    # No terminal_status recorded -- the abandonment classes that never reach `_record`.
    store.record_migration_outcome(
        _outcome(
            finding_id="h" * 32, attempt_index=0,
            terminal_status=None, strategy="codemod", tier=1,
        )
    )

    summary = corpus_summary(store)

    assert summary["by_terminal_status"]["opened"] == 1
    assert summary["by_terminal_status"]["abandoned"] == 1
    assert summary["by_terminal_status"]["null"] == 1
    assert summary["by_strategy"] == {"codemod": 2, "agent": 1}
    assert summary["by_tier"] == {1: 2, 2: 1}


def test_corpus_summary_of_an_empty_corpus_is_empty_not_an_error(store):
    summary = corpus_summary(store)

    assert summary["attempts"] == 0
    assert summary["distinct_findings"] == 0
    assert summary["by_terminal_status"] == {}
    assert summary["by_strategy"] == {}
    assert summary["by_tier"] == {}


# --- repositories -----------------------------------------------------------


def test_repositories_lists_a_repo_with_no_open_finding(store):
    site_id = store.upsert_call_site(_site(repo_id="r-quiet"))
    finding_id = store.insert_finding(_finding(site_id))
    store.set_finding_status(finding_id, "patched")

    result = repositories(store)

    assert "r-quiet" in result["repo_ids"]


def test_repositories_of_an_empty_graph_is_empty_not_an_error(store):
    result = repositories(store)

    assert result["repo_ids"] == []
