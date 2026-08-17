"""View models for the fleet screen: aggregate answers no per-finding tool holds.

`sync.dashboard.queries` answers questions about one finding or one vendor; nothing there has
a grain of "every run" or "every attempt". This module does, and it is deliberately not folded
into `queries.py` -- CLAUDE.md prefers small focused modules, and that one already carries a
stated constraint of its own.

Every function returns primitives, matching `queries.py`'s convention: a page that received a
live model could lazily re-query or mutate it, and this surface is read-only by design.

The checkpointer side reuses `queries.py`'s `_FINISHED` tuple and `_pending_node` rather than
restating either. A run's terminal signal and its pending node are one piece of reasoning about
one JSONB shape; a second copy is a second place for the two to drift, which is exactly the
defect class the run-state Critical was.
"""

from __future__ import annotations

from collections import Counter

import psycopg
from psycopg.rows import dict_row

from sync.dashboard.queries import _FINISHED, _pending_node
from sync.graph.store import GraphStore


def _run_row(thread_id: str, checkpoint: dict) -> dict:
    values = checkpoint.get("channel_values") or {}
    versions = checkpoint.get("channel_versions") or {}
    seen = checkpoint.get("versions_seen") or {}

    outcome = values.get("outcome") if values.get("outcome") in _FINISHED else None
    parts = thread_id.split(":")
    finding_id = parts[0]
    run_id = parts[1] if len(parts) > 1 else None
    return {
        "thread_id": thread_id,
        "finding_id": finding_id,
        "run_id": run_id,
        "current_node": None if outcome is not None else _pending_node(versions, seen),
        "outcome": outcome,
        "abandon_reason": values.get("abandon_reason"),
        "last_checkpoint_at": checkpoint.get("ts"),
    }


def runs(checkpointer_dsn: str, *, limit: int = 50, offset: int = 0) -> dict:
    """Every run the checkpointer holds, one row per thread, newest first -- paginated by a real
    SQL `LIMIT`, plus a disposition roll-up computed across every run rather than the page.

    A finding retried across generations has one thread per generation, and this does not
    collapse them the way `workflow_state` does -- that answers a per-finding question and this
    answers a per-run one, so a retried finding is two rows here and one there.

    Three round trips rather than one, on purpose: `total` is a `count(DISTINCT thread_id)` that
    never fetches a checkpoint body, the page is a `LIMIT`/`OFFSET` over the same newest-per-
    thread subquery the old single-query form used, and `by_disposition` reads only the one JSON
    field it needs (`channel_values->>'outcome'`) across every thread rather than every column of
    every checkpoint. The old form fetched every row's full JSONB into Python and sliced the
    result -- `rows[offset : offset + limit]`, in a variable literally named after the mistake --
    so a fleet of ten thousand runs read ten thousand rows to return fifty; this reads ten
    thousand only for the roll-up, and only the one string column that roll-up needs.

    `by_disposition` is `_grouped` over `outcome`, the same field `_run_row` derives per item,
    computed independently across every thread rather than by tallying the current page -- the
    same reasoning `app.py`'s `overview` route already applies to `total_findings`: a count over
    a page and reported as a fleet-wide fact is the defect this milestone keeps closing.
    """
    limit = max(limit, 1)

    with psycopg.connect(checkpointer_dsn, row_factory=dict_row) as conn:
        # A database no run has ever checkpointed into has no tables at all; that is the same
        # answer as an empty fleet, not an error -- `queries.workflow_state`'s guard applies
        # here identically.
        if conn.execute("SELECT to_regclass('checkpoints') AS t").fetchone()["t"] is None:
            return {"items": [], "total": 0, "next_offset": None, "by_disposition": {}}

        total = conn.execute(
            "SELECT count(DISTINCT thread_id) AS n FROM checkpoints WHERE checkpoint_ns = ''"
        ).fetchone()["n"]

        rows = conn.execute(
            """
            SELECT thread_id, checkpoint FROM (
                SELECT DISTINCT ON (thread_id) thread_id, checkpoint_id, checkpoint
                  FROM checkpoints
                 WHERE checkpoint_ns = ''
                 ORDER BY thread_id, checkpoint_id DESC
            ) AS newest_per_thread
            ORDER BY checkpoint_id DESC
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        ).fetchall()

        outcome_rows = conn.execute(
            """
            SELECT DISTINCT ON (thread_id)
                   checkpoint->'channel_values'->>'outcome' AS outcome
              FROM checkpoints
             WHERE checkpoint_ns = ''
             ORDER BY thread_id, checkpoint_id DESC
            """
        ).fetchall()

    items = [_run_row(row["thread_id"], row["checkpoint"]) for row in rows]
    consumed = offset + len(items)
    by_disposition = _grouped(
        [row["outcome"] if row["outcome"] in _FINISHED else None for row in outcome_rows]
    )
    return {
        "items": items,
        "total": total,
        "next_offset": consumed if consumed < total else None,
        "by_disposition": by_disposition,
    }


def _grouped(values: list) -> dict:
    """One count per distinct value, with `None` reported as the named bucket `"null"`.

    Dropping the null rows would understate the denominator by exactly the attempts a nullable
    column was never written for -- the three abandonment classes `corpus._record` returns
    before, for `terminal_status` specifically.
    """
    counts: Counter = Counter("null" if value is None else value for value in values)
    return dict(counts)


def corpus_summary(store: GraphStore) -> dict:
    """The repair record, aggregated. `attempts` and `distinct_findings` are separate keys.

    One finding retried three times is three rows in `migration_outcome` and one finding here
    too -- `attempts == 3`, `distinct_findings == 1`. Counting findings by counting rows is the
    grain defect `CLAUDE.md` names for this table.
    """
    outcomes = store.migration_outcomes()
    return {
        "attempts": len(outcomes),
        "distinct_findings": len({outcome.finding_id for outcome in outcomes}),
        "by_terminal_status": _grouped([outcome.terminal_status for outcome in outcomes]),
        "by_strategy": _grouped([outcome.strategy for outcome in outcomes]),
        "by_tier": _grouped([outcome.tier for outcome in outcomes]),
    }


def abandonment_by_change_kind(store: GraphStore) -> dict:
    """Which change kinds are not mechanically safe, and at which tier -- M12's first aggregate.

    `docs/superpowers/specs/2026-07-27-sync-pipeline-discipline.md` argues abandoned attempts are
    where routing learns this; nothing read them back before this. The decision it changes is
    concrete: a `(change_kind, tier)` that abandons repeatedly is a routing-table row to correct
    or a codemod to write.

    One entry per `(change_kind, tier)` **actually attempted** --
    `store.migration_outcome_rollup_by_kind`'s own contract: a pair with no attempt has no entry.
    Reading `groups` for a pair therefore answers "never seen"; reading a present entry with
    `abandoned_attempt_count == 0` answers "seen, never abandoned". Collapsing the two into a
    zero would be the exact defect `CLAUDE.md` forbids under "absence is not zero".

    Each entry states two grains side by side, same rule `corpus_summary` already carries: a
    finding retried three times is three rows and one finding, so `attempt_count` and
    `distinct_finding_count` are separate keys, never a bare `count` -- and the same split holds
    for the abandoned subset (`abandoned_attempt_count`, `abandoned_distinct_finding_count`).

    No ratio is computed here. A change kind abandoning 3 of 4 attempts is reported as
    `attempt_count: 4, abandoned_attempt_count: 3` -- the reader can divide; this function does
    not hand back a percentage that reads as a health score, which `CLAUDE.md` and this
    milestone's plan both refuse outright.

    `abandon_reason_codes` is `abandon_reason_code` tallied within the group, over abandoned
    attempts only (B128) -- the closed vocabulary `sync.remediate.state.AbandonReasonCode`
    declares, not the free-text `abandon_reason` prose beside it: two abandonments that read
    differently but share a cause now group together, which is what makes "which change kinds
    are not mechanically safe, and why" a query rather than an argument. A group with no
    abandonment has `{}`.
    """
    reasons: dict[tuple[str, int], dict] = {}
    for row in store.migration_outcome_abandon_reasons_by_kind():
        key = (row["change_kind"], row["tier"])
        reasons.setdefault(key, {})[row["abandon_reason_code"]] = row["n"]

    groups = []
    for row in store.migration_outcome_rollup_by_kind():
        key = (row["change_kind"], row["tier"])
        groups.append(
            {
                "change_kind": row["change_kind"],
                "tier": row["tier"],
                "attempt_count": row["attempt_count"],
                "distinct_finding_count": row["distinct_finding_count"],
                "abandoned_attempt_count": row["abandoned_attempt_count"],
                "abandoned_distinct_finding_count": row["abandoned_distinct_finding_count"],
                "abandon_reason_codes": reasons.get(key, {}),
            }
        )
    return {"groups": groups}


def repositories(store: GraphStore) -> dict:
    """The repo_id roll-up from the index. `store.repo_ids`'s docstring carries the limit:
    a repository configured but never indexed has no row here.
    """
    return {"repo_ids": store.repo_ids()}
