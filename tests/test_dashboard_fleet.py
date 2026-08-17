"""View-model queries for the fleet screen: every run, the repair record, the repo roll-up.

Follows `tests/test_dashboard_queries.py`'s fixture pattern for the checkpointer side --
`PostgresSaver.put`'s row shape, and the thread-id convention `sync.cli` writes:
`{finding_id}:{run_id or head_sha[:12]}:{generation}`.
"""

import json
import os
import unittest.mock

import psycopg
import pytest

from sync.core import CallSite, Finding, MigrationOutcome, VendorChange
from sync.dashboard.fleet import (
    abandonment_by_change_kind,
    change_units,
    corpus_summary,
    repositories,
    runs,
)
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


def test_runs_recovers_run_id_as_the_second_colon_segment(checkpointer_tables):
    _insert_checkpoint(
        f"{FINDING_ID}:rehearsal-2026-08-05:0",
        "1f069000-0000-6000-8000-000000000001",
        channel_values={"outcome": "reported"},
    )

    page = runs(DSN)

    assert page["items"][0]["run_id"] == "rehearsal-2026-08-05"


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

    assert page == {"items": [], "total": 0, "next_offset": None, "by_disposition": {}}


# --- pagination reaches SQL, not a Python slice -----------------------------


def test_runs_limit_is_sql_not_a_python_slice(checkpointer_tables):
    """`items[offset : offset + limit]` in Python still fetches every row off the wire before
    throwing most of it away -- this is the same "rows read vs rows returned" proof
    `test_graph_store.py` uses, applied to the checkpointer connection `runs` opens directly.
    """
    for i in range(5):
        _insert_checkpoint(
            f"{FINDING_ID}:run{i}:0",
            f"1f069000-0000-6000-8000-00000000000{i}",
            channel_values={"outcome": "opened"},
        )
    counts: list[int] = []
    real_fetchall = psycopg.Cursor.fetchall

    def counting_fetchall(self):
        result = real_fetchall(self)
        counts.append(len(result))
        return result

    with unittest.mock.patch.object(psycopg.Cursor, "fetchall", counting_fetchall):
        page = runs(DSN, limit=2, offset=0)

    assert len(page["items"]) == 2, "rows returned"
    # The item-page query is not the only `fetchall()` in `runs` (the disposition roll-up and
    # the empty-table probe both call it too), so the property under test is that *some* query
    # fetched exactly the page size, not that every recorded count did.
    assert 2 in counts, f"no fetchall() returned exactly the page size; saw {counts}"


# --- the fleet-wide disposition roll-up -------------------------------------


def test_runs_by_disposition_counts_every_run_not_just_the_current_page(checkpointer_tables):
    for i, outcome in enumerate(["opened", "opened", "abandoned"]):
        _insert_checkpoint(
            f"{FINDING_ID}:run{i}:0",
            f"1f069000-0000-6000-8000-00000000000{i}",
            channel_values={"outcome": outcome},
        )

    page = runs(DSN, limit=1, offset=0)

    assert len(page["items"]) == 1  # the page itself is narrow
    assert page["by_disposition"] == {"opened": 2, "abandoned": 1}  # the roll-up is not


def test_runs_by_disposition_buckets_a_live_run_under_null(checkpointer_tables):
    # A run still in flight, or one whose outcome is not in `_FINISHED`, is neither 'opened'
    # nor 'abandoned' -- `_grouped`'s existing null-bucket convention applies here too, the same
    # way it already does for `corpus_summary`'s `by_terminal_status`.
    _insert_checkpoint(
        f"{FINDING_ID}:run0:0",
        "1f069000-0000-6000-8000-000000000000",
        channel_values={"outcome": "running"},
    )
    _insert_checkpoint(
        f"{FINDING_ID}:run1:0",
        "1f069000-0000-6000-8000-000000000001",
        channel_values={"outcome": "opened"},
    )

    page = runs(DSN)

    assert page["by_disposition"] == {"null": 1, "opened": 1}


def test_runs_by_disposition_of_an_empty_fleet_is_empty_not_an_error(checkpointer_tables):
    page = runs(DSN)

    assert page["by_disposition"] == {}


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


# --- abandonment by change kind and tier ------------------------------------
#
# M12-W196: which change kinds are not mechanically safe, and at which tier. Same grain rule
# as `corpus_summary` -- `migration_outcome` is one row per attempt -- applied per (change_kind,
# tier) group instead of over the whole corpus.


def test_abandonment_by_change_kind_separates_attempts_from_distinct_findings(store):
    # One finding, retried three times, two of the attempts abandoned. The grain defect
    # `CLAUDE.md` names would report two abandoned findings; there is one.
    store.record_migration_outcome(_outcome(attempt_index=0, terminal_status="abandoned"))
    store.record_migration_outcome(_outcome(attempt_index=1, terminal_status="abandoned"))
    store.record_migration_outcome(_outcome(attempt_index=2, terminal_status="opened"))

    result = abandonment_by_change_kind(store)

    assert len(result["groups"]) == 1
    group = result["groups"][0]
    assert group["attempt_count"] == 3
    assert group["distinct_finding_count"] == 1
    assert group["abandoned_attempt_count"] == 2
    assert group["abandoned_distinct_finding_count"] == 1


def test_abandonment_by_change_kind_groups_by_change_kind_and_tier(store):
    store.record_migration_outcome(
        _outcome(change_kind="request-parameter-removed", tier=1, terminal_status="abandoned")
    )
    store.record_migration_outcome(
        _outcome(
            finding_id="g" * 32, change_kind="response-property-removed", tier=2,
            terminal_status="opened",
        )
    )

    result = abandonment_by_change_kind(store)

    groups = {(g["change_kind"], g["tier"]): g for g in result["groups"]}
    assert set(groups) == {("request-parameter-removed", 1), ("response-property-removed", 2)}
    assert groups[("request-parameter-removed", 1)]["attempt_count"] == 1
    assert groups[("request-parameter-removed", 1)]["abandoned_attempt_count"] == 1
    assert groups[("response-property-removed", 2)]["attempt_count"] == 1
    assert groups[("response-property-removed", 2)]["abandoned_attempt_count"] == 0


def test_abandonment_by_change_kind_reports_abandon_reason_codes_with_counts(store):
    """B128: the aggregate groups by the coded vocabulary, not by the free-text prose beside
    it -- two rows can carry different `abandon_reason` sentences and still share a code.
    """
    store.record_migration_outcome(
        _outcome(
            attempt_index=0, terminal_status="abandoned",
            abandon_reason="error TS2339 on attempt 3",
            abandon_reason_code="static_verify_exhausted",
        )
    )
    store.record_migration_outcome(
        _outcome(
            finding_id="g" * 32, attempt_index=0,
            terminal_status="abandoned",
            # Different prose, same cause -- this is exactly what grouping on `abandon_reason`
            # could never collapse together.
            abandon_reason="error TS2304 on attempt 3",
            abandon_reason_code="static_verify_exhausted",
        )
    )
    store.record_migration_outcome(
        _outcome(
            finding_id="h" * 32, attempt_index=0,
            terminal_status="abandoned", abandon_reason="CI failed: https://example/run/1",
            abandon_reason_code="ci_attempts_exhausted",
        )
    )

    result = abandonment_by_change_kind(store)

    group = result["groups"][0]
    assert group["abandon_reason_codes"] == {
        "static_verify_exhausted": 2,
        "ci_attempts_exhausted": 1,
    }


def test_abandonment_by_change_kind_a_row_predating_the_code_column_reports_none(store):
    """A row abandoned before `abandon_reason_code` existed carries `abandon_reason` alone.

    That is a gap in the record, not the same fact as `unclassified` -- `unclassified` is a
    real member of the vocabulary a run reaches when `make_abandon` could not classify it, and
    collapsing the two would make a historical gap look like a defect in today's classifier.
    """
    store.record_migration_outcome(
        _outcome(
            attempt_index=0, terminal_status="abandoned", abandon_reason="tsc failed",
            abandon_reason_code=None,
        )
    )

    result = abandonment_by_change_kind(store)

    group = result["groups"][0]
    assert group["abandon_reason_codes"] == {None: 1}


def test_abandonment_by_change_kind_a_group_never_abandoned_has_zero_not_absence(store):
    # Seen and never abandoned is a real zero -- distinct from a (change_kind, tier) never
    # attempted at all, which has no group.
    store.record_migration_outcome(_outcome(terminal_status="opened"))

    result = abandonment_by_change_kind(store)

    group = result["groups"][0]
    assert group["abandoned_attempt_count"] == 0
    assert group["abandoned_distinct_finding_count"] == 0
    assert group["abandon_reason_codes"] == {}


def test_abandonment_by_change_kind_absence_is_not_zero(store):
    # Only "request-parameter-removed" at tier 1 was ever attempted. A change kind never seen
    # must have no row, not a row reading zero -- CLAUDE.md's "absence is not zero" rule.
    store.record_migration_outcome(
        _outcome(change_kind="request-parameter-removed", tier=1, terminal_status="opened")
    )

    result = abandonment_by_change_kind(store)

    seen = {(g["change_kind"], g["tier"]) for g in result["groups"]}
    assert ("response-property-removed", 1) not in seen
    assert ("request-parameter-removed", 2) not in seen


def test_abandonment_by_change_kind_of_an_empty_corpus_is_empty_not_an_error(store):
    result = abandonment_by_change_kind(store)

    assert result["groups"] == []


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


# --- change_units -----------------------------------------------------------


def test_change_units_groups_open_findings_by_vendor_change(store):
    # A single vendor change spanning 3 call sites across 2 repositories is one ChangeUnit.
    change_id = store.upsert_vendor_change(
        VendorChange(
            vendor_id="stripe",
            from_version="2024-04-10",
            to_version="2024-06-20",
            kind="parameter-removed",
            operation_id="PostCharges",
            path_ptr="#/paths/~1v1~1charges/post",
            severity="breaking",
            source="oasdiff",
        )
    )
    site_r1_a = store.upsert_call_site(_site(repo_id="r1", path="src/a.ts", line=10))
    site_r1_b = store.upsert_call_site(_site(repo_id="r1", path="src/b.ts", line=20))
    site_r2 = store.upsert_call_site(_site(repo_id="r2", path="src/c.ts", line=30))

    f1 = store.insert_finding(_finding(site_r1_a, vendor_change_id=change_id, binding_rung="static"))
    f2 = store.insert_finding(_finding(site_r1_b, vendor_change_id=change_id, binding_rung="static"))
    f3 = store.insert_finding(_finding(site_r2, vendor_change_id=change_id, binding_rung="static"))

    result = change_units(store)

    assert result["total"] == 1
    unit = result["items"][0]
    assert unit["vendor_id"] == "stripe"
    assert unit["operation_id"] == "PostCharges"
    assert unit["change_kind"] == "parameter-removed"
    assert unit["from_version"] == "2024-04-10"
    assert unit["to_version"] == "2024-06-20"
    assert unit["severity"] == "breaking"
    assert unit["repository_count"] == 2
    assert unit["call_site_count"] == 3
    assert unit["binding_rung"] == "static"
    assert set(unit["finding_ids"]) == {f1, f2, f3}
    assert unit["repo_ids"] == ["r1", "r2"]


def test_change_units_reports_weakest_rung_when_mixed(store):
    # If call sites within a change unit carry mixed rungs (e.g. static and observed),
    # the change unit reports the weaker rung while preserving finding details.
    site_a = store.upsert_call_site(_site(repo_id="r1", path="src/a.ts", line=10))
    site_b = store.upsert_call_site(_site(repo_id="r1", path="src/b.ts", line=20))
    f1 = store.insert_finding(_finding(site_a, binding_rung="observed"))
    f2 = store.insert_finding(_finding(site_b, binding_rung="static"))

    result = change_units(store)

    assert result["total"] == 1
    unit = result["items"][0]
    assert unit["call_site_count"] == 2
    assert unit["binding_rung"] in ("static", "mixed")


def test_change_units_scoped_to_repo_id(store):
    site_r1 = store.upsert_call_site(_site(repo_id="r1", path="src/a.ts", line=10, operation_id="OpA"))
    site_r2 = store.upsert_call_site(_site(repo_id="r2", path="src/b.ts", line=20, operation_id="OpB"))
    store.insert_finding(_finding(site_r1, claim="c1"))
    store.insert_finding(_finding(site_r2, claim="c2"))

    scoped = change_units(store, repo_id="r1")
    assert scoped["total"] == 1
    assert scoped["items"][0]["repo_ids"] == ["r1"]


def test_change_units_of_an_empty_graph_is_empty_not_an_error(store):
    result = change_units(store)
    assert result == {"items": [], "total": 0, "next_offset": None}
