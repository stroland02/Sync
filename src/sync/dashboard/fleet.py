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
from typing import Any

import psycopg
from psycopg.rows import dict_row

from sync.benchmark.axes import compute_axes
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


def _weaker_rung_summary(rungs: set[str]) -> str:
    """Derive a summary rung from a set of rungs across call sites.

    If all call sites agree on one rung, that rung is returned.
    If multiple distinct rungs are present, 'mixed' or the weakest rung is returned.
    """
    if not rungs:
        return "unattributed"
    if len(rungs) == 1:
        return next(iter(rungs))
    for candidate in ("unattributed", "unresolved", "static", "resolved", "observed"):
        if candidate in rungs:
            return candidate
    return "mixed"


def change_units(
    store: GraphStore,
    checkpointer_dsn: str | None = None,
    *,
    repo_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """The Fleet change-unit roll-up: open findings grouped by vendor change and operation.

    -- Grain: One ChangeUnit is one distinct vendor change (vendor_id, operation_id, from_version, to_version, change_kind)
    -- across open findings in the watched repositories.

    A vendor change affecting multiple repositories and call sites is one ChangeUnit here,
    with distinct counts for repositories (`repository_count`) and call sites (`call_site_count`).

    `binding_rung` is the weakest rung among the constituent findings (or the unified rung if all agree),
    and each unit carries `finding_ids`, `repo_ids`, and `severities`.

    If `checkpointer_dsn` is provided, latest checkpointer checkpoint timestamps and standings
    are joined for the constituent findings.
    """
    limit = max(limit, 1)

    raw_rows = store._connect().execute(
        """
        SELECT finding.id AS finding_id,
               finding.severity AS severity,
               finding.binding_rung AS binding_rung,
               finding.detector AS detector,
               finding.created_at AS created_at,
               call_site.id AS call_site_id,
               call_site.repo_id AS repo_id,
               call_site.path AS path,
               call_site.line AS line,
               call_site.symbol AS symbol,
               call_site.vendor_id AS call_site_vendor_id,
               call_site.operation_id AS call_site_operation_id,
               vendor_change.id AS vendor_change_id,
               vendor_change.vendor_id AS vendor_change_vendor_id,
               vendor_change.operation_id AS vendor_change_operation_id,
               vendor_change.from_version AS from_version,
               vendor_change.to_version AS to_version,
               vendor_change.kind AS change_kind
          FROM finding
          JOIN call_site ON call_site.id = finding.call_site_id
          LEFT JOIN vendor_change ON vendor_change.id = finding.vendor_change_id
         WHERE finding.status = 'open'
           AND call_site.retracted_at IS NULL
         ORDER BY finding.created_at DESC
        """
    ).fetchall()

    if repo_id is not None:
        raw_rows = [r for r in raw_rows if r["repo_id"] == repo_id]

    if not raw_rows:
        return {"items": [], "total": 0, "next_offset": None}

    groups: dict[tuple, list[dict]] = {}
    for row in raw_rows:
        v_id = row["vendor_change_vendor_id"] or row["call_site_vendor_id"] or "unknown"
        op_id = row["vendor_change_operation_id"] or row["call_site_operation_id"]
        c_kind = row["change_kind"] or row["detector"] or "unknown"
        f_ver = row["from_version"]
        t_ver = row["to_version"]
        key = (v_id, op_id, c_kind, f_ver, t_ver)
        groups.setdefault(key, []).append(row)

    units = []
    for (v_id, op_id, c_kind, f_ver, t_ver), group_rows in groups.items():
        finding_ids = [r["finding_id"] for r in group_rows]
        repo_ids = sorted(list({r["repo_id"] for r in group_rows if r["repo_id"]}))
        call_site_ids = {r["call_site_id"] for r in group_rows if r["call_site_id"]}
        severities = [r["severity"] for r in group_rows]
        rungs = {r["binding_rung"] for r in group_rows if r["binding_rung"]}

        sev_priority = {"breaking": 4, "deprecation": 3, "warning": 2, "info": 1}
        dominant_sev = max(severities, key=lambda s: sev_priority.get(s, 0)) if severities else "warning"

        unit = {
            "change_unit_id": f"{v_id}:{op_id or 'all'}:{c_kind}",
            "vendor_id": v_id,
            "operation_id": op_id,
            "change_kind": c_kind,
            "from_version": f_ver,
            "to_version": t_ver,
            "severity": dominant_sev,
            "repository_count": len(repo_ids),
            "call_site_count": len(call_site_ids),
            "binding_rung": _weaker_rung_summary(rungs),
            "finding_ids": finding_ids,
            "repo_ids": repo_ids,
            "standing": None,
            "last_checkpoint_at": None,
        }
        units.append(unit)

    if checkpointer_dsn is not None and units:
        try:
            with psycopg.connect(checkpointer_dsn, row_factory=dict_row) as conn:
                if conn.execute("SELECT to_regclass('checkpoints') AS t").fetchone()["t"] is not None:
                    for u in units:
                        f_ids = u["finding_ids"]
                        placeholders = ", ".join(["%s"] * len(f_ids))
                        cp_rows = conn.execute(
                            f"""
                            SELECT thread_id, checkpoint, ts FROM (
                                SELECT DISTINCT ON (thread_id) thread_id, checkpoint_id, checkpoint, ts
                                  FROM checkpoints
                                 WHERE checkpoint_ns = ''
                                 ORDER BY thread_id, checkpoint_id DESC
                            ) AS newest
                            WHERE split_part(thread_id, ':', 1) IN ({placeholders})
                            ORDER BY ts DESC
                            LIMIT 1
                            """,
                            f_ids,
                        ).fetchall()
                        if cp_rows:
                            latest_cp = cp_rows[0]
                            val = (latest_cp.get("checkpoint") or {}).get("channel_values") or {}
                            outcome = val.get("outcome") if val.get("outcome") in _FINISHED else None
                            u["standing"] = outcome or "in_progress"
                            ts_val = latest_cp.get("ts")
                            u["last_checkpoint_at"] = ts_val.isoformat() if hasattr(ts_val, "isoformat") else str(ts_val) if ts_val else None
        except psycopg.Error:
            pass

    total = len(units)
    paged_items = units[offset : offset + limit] if limit > 0 else units
    consumed = offset + len(paged_items)
    next_offset = consumed if consumed < total else None

    return {
        "items": paged_items,
        "total": total,
        "next_offset": next_offset,
    }


def corpus_health(store: GraphStore) -> dict[str, Any]:
    """The corpus health view model: quality axes status, sample counts, and runs.

    Beta's evidence has to be readable before it is quotable, and this answers which
    quality axes have samples, which have none, and how many runs produced them.
    Absence (status='unmeasured', has_samples=False, value=None) is distinct from
    zero (status='measured', has_samples=True, value=0.0).
    """
    outcomes = store.migration_outcomes()
    axes = compute_axes(outcomes)

    # 1. merge_rate_by_change_kind
    kind_groups = {
        kind: {
            "value": axis.value,
            "n": axis.n,
            "has_samples": axis.n > 0,
            "status": "measured" if axis.n > 0 else "unmeasured",
            "provenance": axis.provenance,
        }
        for kind, axis in axes.merge_rate_by_change_kind.items()
    }
    kind_sample_count = sum(axis.n for axis in axes.merge_rate_by_change_kind.values())
    kind_has_samples = kind_sample_count > 0
    kind_provenance = (
        "unmeasured"
        if not kind_has_samples
        else (
            "mixed"
            if len({v["provenance"] for v in kind_groups.values() if v["has_samples"]}) > 1
            else next(v["provenance"] for v in kind_groups.values() if v["has_samples"])
        )
    )
    kind_axis = {
        "name": "merge_rate_by_change_kind",
        "display_name": "Merge Rate by Change Kind",
        "status": "measured" if kind_has_samples else "unmeasured",
        "has_samples": kind_has_samples,
        "sample_count": kind_sample_count,
        "provenance": kind_provenance,
        "value": {k: v["value"] for k, v in kind_groups.items()} if kind_has_samples else None,
        "groups": kind_groups,
        "unit": "ratio",
        "denominator_description": "pull requests opened with decided outcome, grouped by change kind",
    }

    # 2. merge_rate_by_tier
    tier_groups = {
        tier: {
            "value": axis.value,
            "n": axis.n,
            "has_samples": axis.n > 0,
            "status": "measured" if axis.n > 0 else "unmeasured",
            "provenance": axis.provenance,
        }
        for tier, axis in axes.merge_rate_by_tier.items()
    }
    tier_sample_count = sum(axis.n for axis in axes.merge_rate_by_tier.values())
    tier_has_samples = tier_sample_count > 0
    tier_provenance = (
        "unmeasured"
        if not tier_has_samples
        else (
            "mixed"
            if len({v["provenance"] for v in tier_groups.values() if v["has_samples"]}) > 1
            else next(v["provenance"] for v in tier_groups.values() if v["has_samples"])
        )
    )
    tier_axis = {
        "name": "merge_rate_by_tier",
        "display_name": "Merge Rate by Repair Tier",
        "status": "measured" if tier_has_samples else "unmeasured",
        "has_samples": tier_has_samples,
        "sample_count": tier_sample_count,
        "provenance": tier_provenance,
        "value": {k: v["value"] for k, v in tier_groups.items()} if tier_has_samples else None,
        "groups": tier_groups,
        "unit": "ratio",
        "denominator_description": "pull requests opened with decided outcome, grouped by repair tier",
    }

    # 3. routing_accuracy
    routing_has_samples = axes.routing_accuracy.n > 0
    routing_axis = {
        "name": "routing_accuracy",
        "display_name": "Routing Accuracy",
        "status": "measured" if routing_has_samples else "unmeasured",
        "has_samples": routing_has_samples,
        "sample_count": axes.routing_accuracy.n,
        "provenance": axes.routing_accuracy.provenance,
        "value": axes.routing_accuracy.value if routing_has_samples else None,
        "unit": "ratio",
        "denominator_description": "findings routed to tier 0",
    }

    # 4. tokens_per_merged_patch
    tokens_has_samples = axes.tokens_per_merged_patch.n > 0
    tokens_axis = {
        "name": "tokens_per_merged_patch",
        "display_name": "Tokens per Merged Patch",
        "status": "measured" if tokens_has_samples else "unmeasured",
        "has_samples": tokens_has_samples,
        "sample_count": axes.tokens_per_merged_patch.n,
        "provenance": axes.tokens_per_merged_patch.provenance,
        "value": axes.tokens_per_merged_patch.value if tokens_has_samples else None,
        "unit": "tokens",
        "denominator_description": "merged pull requests",
    }

    # 5. wall_ms_per_merged_patch
    wall_ms_has_samples = axes.wall_ms_per_merged_patch.n > 0
    wall_ms_axis = {
        "name": "wall_ms_per_merged_patch",
        "display_name": "Wall Clock Duration per Merged Patch",
        "status": "measured" if wall_ms_has_samples else "unmeasured",
        "has_samples": wall_ms_has_samples,
        "sample_count": axes.wall_ms_per_merged_patch.n,
        "provenance": axes.wall_ms_per_merged_patch.provenance,
        "value": axes.wall_ms_per_merged_patch.value if wall_ms_has_samples else None,
        "unit": "milliseconds",
        "denominator_description": "merged pull requests",
    }

    axis_list = [kind_axis, tier_axis, routing_axis, tokens_axis, wall_ms_axis]
    measured_count = sum(1 for a in axis_list if a["has_samples"])
    unmeasured_count = len(axis_list) - measured_count

    return {
        "summary": {
            "total_runs": axes.counts.attempts,
            "distinct_findings": axes.counts.findings,
            "pull_requests_opened": axes.counts.pull_requests_opened,
            "pull_requests_merged": axes.counts.pull_requests_merged,
            "findings_abandoned": axes.counts.findings_abandoned,
            "production_attempts": axes.counts.production_attempts,
            "rehearsal_attempts": axes.counts.rehearsal_attempts,
            "axes_measured_count": measured_count,
            "axes_unmeasured_count": unmeasured_count,
            "total_axes": len(axis_list),
            "has_any_samples": measured_count > 0,
        },
        "axes": axis_list,
    }

