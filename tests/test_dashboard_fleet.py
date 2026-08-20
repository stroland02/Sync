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
    NESTED_FINDINGS_PER_UNIT,
    IN_FLIGHT,
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


def test_runs_scoped_to_repository(checkpointer_tables, store):
    s1 = store.upsert_call_site(_site(repo_id="r1", path="src/a.ts"))
    f1 = store.insert_finding(_finding(s1))
    s2 = store.upsert_call_site(_site(repo_id="r2", path="src/b.ts"))
    f2 = store.insert_finding(_finding(s2))

    _insert_checkpoint(
        f"{f1}:run1:0",
        "1f069000-0000-6000-8000-000000000001",
        channel_values={"outcome": "opened"},
    )
    _insert_checkpoint(
        f"{f2}:run2:0",
        "1f069000-0000-6000-8000-000000000002",
        channel_values={"outcome": "abandoned"},
    )

    scoped = runs(DSN, repo_id="r1", store=store)
    assert scoped["total"] == 1
    assert len(scoped["items"]) == 1
    assert scoped["items"][0]["finding_id"] == f1
    assert scoped["items"][0]["repo_id"] == "r1"

    fleet_runs = runs(DSN, store=store)
    assert fleet_runs["total"] == 2
    r_map = {item["finding_id"]: item["repo_id"] for item in fleet_runs["items"]}
    assert r_map[f1] == "r1"
    assert r_map[f2] == "r2"


def test_a_run_carries_its_findings_sayable_name(checkpointer_tables, store):
    """A run row is addressed by a 32-character hex id and read by a person.

    `finding_name` is derived in the payload rather than in the console, because the CLI and a
    pull-request body name the same finding too -- a third derivation is where the three begin
    to differ. The id stays the addressable thing; this is what makes the row speakable.
    """
    site = store.upsert_call_site(_site(vendor_id="stripe", operation_id="PostCharges"))
    finding = store.insert_finding(_finding(site))
    _insert_checkpoint(
        f"{finding}:run1:0",
        "1f069000-0000-6000-8000-000000000001",
        channel_values={"outcome": "opened"},
    )

    row = runs(DSN, store=store)["items"][0]

    assert row["finding_name"].startswith("stripe-postcharges-")
    # The id is unchanged and still what every link is built from.
    assert row["finding_id"] == finding


def test_a_run_whose_finding_is_gone_is_named_by_nothing_rather_than_by_a_guess(
    checkpointer_tables, store
):
    """The checkpointer outlives `finding`, which every scan truncates and rebuilds.

    A thread whose finding has been patched or retracted has no call site to take a vendor and
    an operation from. A name invented for it would assert an integration nothing recorded, so
    the row says it has none -- the run itself is still listed, because it happened.
    """
    _insert_checkpoint(
        f"{FINDING_ID}:run1:0",
        "1f069000-0000-6000-8000-000000000001",
        channel_values={"outcome": "abandoned"},
    )

    row = runs(DSN, store=store)["items"][0]

    assert row["finding_name"] is None
    assert row["finding_id"] == FINDING_ID


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

    # `unfiltered_total` is part of this envelope too: the rail counts every run the deployment
    # holds, and a database with no checkpoint table holds none. Omitting it here let the
    # payload gain a key this assertion never checked.
    assert page == {
        "items": [], "total": 0, "next_offset": None,
        "by_disposition": {}, "unfiltered_total": 0,
    }


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


def test_corpus_summary_scoped_to_repository(store):
    s1 = store.upsert_call_site(_site(repo_id="r1", path="src/a.ts"))
    f1 = store.insert_finding(_finding(s1))
    s2 = store.upsert_call_site(_site(repo_id="r2", path="src/b.ts"))
    f2 = store.insert_finding(_finding(s2))

    store.record_migration_outcome(
        _outcome(finding_id=f1, attempt_index=0, terminal_status="opened")
    )
    store.record_migration_outcome(
        _outcome(finding_id=f2, attempt_index=0, terminal_status="abandoned")
    )

    scoped_r1 = corpus_summary(store, repo_id="r1")
    assert scoped_r1["repo_id"] == "r1"
    assert scoped_r1["attempts"] == 1
    assert scoped_r1["distinct_findings"] == 1
    assert scoped_r1["by_terminal_status"] == {"opened": 1}

    scoped_r2 = corpus_summary(store, repo_id="r2")
    assert scoped_r2["repo_id"] == "r2"
    assert scoped_r2["attempts"] == 1
    assert scoped_r2["distinct_findings"] == 1
    assert scoped_r2["by_terminal_status"] == {"abandoned": 1}

    fleet_summary = corpus_summary(store)
    assert fleet_summary["repo_id"] is None
    assert fleet_summary["attempts"] == 2
    assert fleet_summary["distinct_findings"] == 2


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


def test_a_unit_carries_its_own_findings_and_they_reconcile(store):
    """M15 Task 7's verification: a unit's finding count sums to the flat total.

    Twenty-four findings are really thirteen change units, and a console listing them flat shows
    a reader twenty-four problems where there are thirteen. Making the unit primary is only
    honest if the two views describe the same set -- a grouped total that disagreed with the flat
    one would be the console asserting two different sizes for one workspace, which is the exact
    failure the absence-versus-zero discipline exists to prevent, arriving as arithmetic.

    The nested rows cost no extra query: `change_units` already fetches each finding's call site
    to group it, so the rows are in hand when the unit is built.
    """
    site_a = store.upsert_call_site(_site(path="src/a.ts", line=1))
    site_b = store.upsert_call_site(_site(path="src/b.ts", line=2))
    site_c = store.upsert_call_site(_site(path="src/c.ts", line=3, operation_id="GetBalance"))
    for site in (site_a, site_b, site_c):
        store.insert_finding(_finding(site, claim=f"claim-{site}"))

    result = change_units(store, repo_id="r1")

    # Two operations, so two units; three findings across them.
    assert result["total"] == 2
    assert sum(unit["finding_count"] for unit in result["items"]) == 3
    assert sum(len(unit["findings"]) for unit in result["items"]) == 3


def test_a_nested_finding_carries_what_the_flat_table_shows(store):
    """The nested row is the same object the flat table renders, name included.

    A second, thinner shape here would mean the grouped view and the flat view describe one
    finding two ways -- and the one that got a field added later would be the only one that had it.
    """
    site = store.upsert_call_site(_site(path="src/a.ts", line=7))
    store.insert_finding(_finding(site))

    row = change_units(store, repo_id="r1")["items"][0]["findings"][0]

    assert row["file"] == "src/a.ts"
    assert row["line"] == 7
    assert row["severity"] == "breaking"
    assert row["binding_source"] == "static"
    assert row["name"].startswith("stripe-postcharges-")


def test_a_unit_counts_its_findings_rather_than_its_call_sites(store):
    """Two findings on one call site is two findings and one call site.

    `graph-grain.md` is explicit that one row is one claim, and a unit that reported its call-site
    count as its finding count would under-report exactly where a single call is broken in more
    than one way -- which is the case a reviewer most needs to see.
    """
    site = store.upsert_call_site(_site(path="src/a.ts"))
    store.insert_finding(_finding(site, claim="request-parameter-removed"))
    store.insert_finding(_finding(site, claim="response-field-type-changed"))

    unit = change_units(store, repo_id="r1")["items"][0]

    assert unit["finding_count"] == 2
    assert unit["call_site_count"] == 1


def test_narrowing_to_a_severity_narrows_the_units_and_still_reconciles(store):
    """The severity tabs must reach the grouped view, or they would silently stop applying.

    A tab pressed over a grouped table that ignored it is the worst shape a filter can take: the
    control looks active, the numbers are true of *something*, and nothing on screen is visibly
    broken. So severity narrows the findings before they are grouped -- a unit then reports the
    findings of that severity it holds, and the sum still equals the flat total for that tab.

    A unit with no finding at the chosen severity is absent rather than present at nought: the
    grouping returns groups that exist, which is the same rule `by_vendor_severity` follows.
    """
    site_a = store.upsert_call_site(_site(path="src/a.ts"))
    site_b = store.upsert_call_site(_site(path="src/b.ts", operation_id="GetBalance"))
    store.insert_finding(_finding(site_a, claim="c1", severity="breaking"))
    store.insert_finding(_finding(site_a, claim="c2", severity="warning"))
    store.insert_finding(_finding(site_b, claim="c3", severity="warning"))

    breaking = change_units(store, repo_id="r1", severity="breaking")

    assert breaking["total"] == 1
    assert sum(unit["finding_count"] for unit in breaking["items"]) == 1
    assert breaking["items"][0]["operation_id"] == "PostCharges"


def test_an_unnarrowed_grouping_still_holds_every_finding(store):
    site = store.upsert_call_site(_site(path="src/a.ts"))
    store.insert_finding(_finding(site, claim="c1", severity="breaking"))
    store.insert_finding(_finding(site, claim="c2", severity="warning"))

    assert sum(u["finding_count"] for u in change_units(store, repo_id="r1")["items"]) == 2


def test_a_parked_run_reports_parked_rather_than_reading_as_in_flight(checkpointer_tables):
    """M15 Task 8: *a run needing review is indistinguishable from one in flight.*

    The vocabulary already held the state -- `make_park` writes `outcome: "parked"` with
    `parked_reason: "awaiting_review"`, and `Outcome` has carried it all along. What it never
    reached was `_FINISHED`, and every display site asks `outcome in _FINISHED else None`, so a
    run waiting on a human came back as `None` and the console renders `None` as *in flight*.

    That is the worst shape this distinction can take: the run is not running, nobody is coming
    back to it on their own, and the one screen that would say so reports it as busy.
    """
    _insert_checkpoint(
        f"{FINDING_ID}:abc123def456:0",
        "1f069000-0000-6000-8000-000000000001",
        channel_values={"outcome": "parked", "parked_reason": "awaiting_review"},
    )

    page = runs(DSN)

    assert page["items"][0]["outcome"] == "parked"


def test_parked_is_a_disposition_without_being_an_ending():
    """Why `parked` was not simply added to `_FINISHED`.

    A parked run has stopped and has something to report, which is what every display site is
    actually asking. It has *not* finished: nothing was opened, abandoned or reported, and a
    tuple named `_FINISHED` holding a state that did not finish is a name that misleads the next
    reader into counting it as an ending.
    """
    from sync.dashboard.queries import DISPOSITIONS, _FINISHED

    assert "parked" in DISPOSITIONS
    assert "parked" not in _FINISHED
    assert set(_FINISHED).issubset(set(DISPOSITIONS))


def test_a_parked_run_is_not_counted_among_the_runs_in_flight(checkpointer_tables):
    """The filter moves with the classification, or the rail lies in the other direction.

    `IN_FLIGHT` selects runs with no disposition yet. A parked run has one, so pressing *in
    flight* must not return it -- otherwise the count beside the option promises runs that are
    live and delivers runs that are waiting.
    """
    _insert_checkpoint(
        f"{FINDING_ID}:abc123def456:0",
        "1f069000-0000-6000-8000-000000000001",
        channel_values={"outcome": "parked", "parked_reason": "awaiting_review"},
    )

    assert runs(DSN, outcome=IN_FLIGHT)["items"] == []


def test_change_units_joins_the_newest_checkpoint_for_each_unit(store, checkpointer_tables):
    """The standing a unit reports comes from the newest checkpoint among its own findings.

    Untested until 2026-08-19, when the per-unit checkpointer query became one query for the
    page: fifty units cost fifty round trips against a second database, on the route the
    console's Integrations screen reads. The rewrite keys one answer in Python, and this is
    what holds the two readings equal -- newest wins, and a unit whose findings have no
    checkpoint keeps the nulls rather than borrowing another unit's standing.
    """
    site_a = store.upsert_call_site(_site(repo_id="r1", path="src/a.ts", line=10))
    site_b = store.upsert_call_site(_site(repo_id="r1", path="src/b.ts", line=20, operation_id="GetBalance"))
    patched = store.insert_finding(_finding(site_a, claim="c1"))
    store.insert_finding(_finding(site_b, claim="c2"))

    # Two checkpoints on one finding's thread; the newer one carries the outcome that must win.
    _insert_checkpoint(f"{patched}:run-1", _version(1),
                       channel_values={"outcome": "abandoned"},
                       ts="2026-07-30T12:00:00.000000+00:00")
    _insert_checkpoint(f"{patched}:run-1", _version(2),
                       channel_values={"outcome": "opened"},
                       ts="2026-08-01T12:00:00.000000+00:00")

    units = change_units(store, checkpointer_dsn=DSN, repo_id="r1")["items"]
    by_op = {u["operation_id"]: u for u in units}

    assert by_op["PostCharges"]["standing"] == "opened"
    assert by_op["PostCharges"]["last_checkpoint_at"].startswith("2026-08-01")
    # The other unit's findings have no checkpoint at all, and it must not inherit one.
    assert by_op["GetBalance"]["standing"] is None
    assert by_op["GetBalance"]["last_checkpoint_at"] is None


def test_a_units_nested_findings_are_bounded_while_its_count_is_not(store):
    """`limit` bounds units; nothing bounded the findings nested inside them.

    Measured at 10,000 findings: eight units carried **10,000 nested rows** and the response was
    **4.3 MB** for one page of fifty. The page was unbounded in the dimension that decides its
    size, on the route the Integrations screen reads.

    `finding_count` is why the cap is safe rather than a loss: it is stated by the payload
    precisely so a reader never counts the array, and its own comment says the array "would
    report the page". This makes that true instead of aspirational -- the count stays the
    workspace's, the array becomes a bounded sample, and the screen says which it is showing.
    """
    site = store.upsert_call_site(_site(repo_id="r1", path="src/a.ts", line=1))
    for n in range(NESTED_FINDINGS_PER_UNIT + 5):
        store.insert_finding(_finding(site, claim=f"claim-{n}"))

    unit = change_units(store, repo_id="r1")["items"][0]

    # The truth is unbounded; the sample is bounded; the two are different fields on purpose.
    assert unit["finding_count"] == NESTED_FINDINGS_PER_UNIT + 5
    assert len(unit["findings"]) == NESTED_FINDINGS_PER_UNIT
    # The ids are bounded the same way, and for the same reason: one unit''s `finding_ids` was
    # 92,500 bytes against 8,194 for the rows they identify, and no screen reads the field. The
    # checkpointer join upstream still sees every id, so a unit''s standing is the whole unit''s.
    assert len(unit["finding_ids"]) == NESTED_FINDINGS_PER_UNIT
