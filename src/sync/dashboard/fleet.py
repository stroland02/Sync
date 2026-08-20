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
from sync.core.naming import finding_name
from sync.dashboard.queries import DISPOSITIONS, _FINISHED, _pending_node
from sync.graph.store import GraphStore


NESTED_FINDINGS_PER_UNIT = 20
"""How many of a change unit's findings travel inside the unit itself.

A sample, never the population -- `finding_count` on the same row is the population and is
computed independently, which is the whole reason it is stated rather than derived from this
array. Twenty because the console renders these in a disclosure a reader opens on one unit at a
time: enough that opening one is useful, few enough that fifty units cannot build a payload out
of them. The exact number is not load-bearing; that the array is bounded at all is.
"""


def _run_row(thread_id: str, checkpoint: dict, identity: dict | None = None) -> dict:
    values = checkpoint.get("channel_values") or {}
    versions = checkpoint.get("channel_versions") or {}
    seen = checkpoint.get("versions_seen") or {}
    known = identity or {}

    outcome = values.get("outcome") if values.get("outcome") in DISPOSITIONS else None
    parts = thread_id.split(":")
    finding_id = parts[0]
    run_id = parts[1] if len(parts) > 1 else None
    return {
        "thread_id": thread_id,
        "finding_id": finding_id,
        # The sayable name, derived here rather than in the console for the reason `naming.py`
        # states: the same finding is named by the CLI and by a pull-request body too, and a
        # third derivation is where the three start to differ.
        #
        # `None` when the graph no longer holds the finding this thread names. The checkpointer
        # outlives `finding`, which a scan truncates and rebuilds, so a run whose finding has
        # been patched or retracted has a thread and no call site to name it from -- and a name
        # invented for it would claim a vendor and an operation nothing recorded.
        "finding_name": _run_name(finding_id, known),
        "repo_id": known.get("repo_id") or values.get("repo_id"),
        "run_id": run_id,
        "current_node": None if outcome is not None else _pending_node(versions, seen),
        "outcome": outcome,
        "abandon_reason": values.get("abandon_reason"),
        "last_checkpoint_at": checkpoint.get("ts"),
    }


def _run_name(finding_id: str, identity: dict) -> str | None:
    """This run's finding as something a reviewer can say, or `None` when it cannot be derived.

    An operation is nullable on `call_site` -- not every binding resolves one -- and
    `finding_name` builds its name from the parts that are present, so a finding with no
    operation is named for its vendor alone. What it cannot do without is the id, which is
    where the discriminator comes from.
    """
    if not identity.get("vendor_id"):
        return None
    return finding_name(identity["vendor_id"], identity.get("operation_id") or "", finding_id)


IN_FLIGHT = "in-flight"
"""The filter value that selects runs with no disposition yet.

Not a member of `_FINISHED` and never stored anywhere: a run is in flight exactly while its
newest checkpoint carries no finished outcome, so the transport needs a word for that state
that cannot collide with a real outcome value.
"""


def runs(
    checkpointer_dsn: str,
    *,
    repo_id: str | None = None,
    store: GraphStore | None = None,
    limit: int = 50,
    offset: int = 0,
    outcome: str | None = None,
) -> dict:
    """Every run the checkpointer holds, one row per thread, newest first -- paginated by a real
    SQL `LIMIT`, plus a disposition roll-up computed across every run rather than the page.

    A finding retried across generations has one thread per generation, and this does not
    collapse them the way `workflow_state` does -- that answers a per-finding question and this
    answers a per-run one, so a retried finding is two rows here and one there.

    `repo_id` narrows to runs belonging to that repository (B149). `outcome` narrows to runs
    whose newest checkpoint reached that disposition, with `IN_FLIGHT` selecting the ones that
    have none yet; a value outside the vocabulary matches nothing, which is an empty page rather
    than an error, because the console renders an out-of-vocabulary selection as its own state.

    `by_disposition` and `unfiltered_total` are deliberately computed before the `outcome`
    filter is applied: they exist so a filter rail can say what each selection *would* return,
    and counts narrowed by the filter they set collapse to whatever is already selected.
    `total` describes the filtered set, because pagination walks that set and no other.
    """
    limit = max(limit, 1)
    # One map, carrying the repository this narrows on and the vendor and operation each row is
    # named from. Two queries over the same join would be a second thing to keep in agreement.
    identities = store.finding_identities() if store is not None else {}

    if repo_id is not None:
        matching_fids = [
            fid for fid, known in identities.items() if known.get("repo_id") == repo_id
        ]
        if not matching_fids:
            return {
                "items": [], "total": 0, "next_offset": None,
                "by_disposition": {}, "unfiltered_total": 0,
            }
        predicate = "checkpoint_ns = '' AND split_part(thread_id, ':', 1) = ANY(%s)"
        params: list[Any] = [matching_fids]
    else:
        predicate = "checkpoint_ns = ''"
        params = []

    newest = f"""
        SELECT DISTINCT ON (thread_id)
               thread_id, checkpoint_id, checkpoint,
               checkpoint->'channel_values'->>'outcome' AS outcome
          FROM checkpoints
         WHERE {predicate}
         ORDER BY thread_id, checkpoint_id DESC
    """

    if outcome is None:
        narrowed = "TRUE"
        narrowed_params: list[Any] = []
    elif outcome == IN_FLIGHT:
        narrowed = "(outcome IS NULL OR outcome <> ALL(%s))"
        narrowed_params = [list(DISPOSITIONS)]
    else:
        narrowed = "outcome = %s"
        narrowed_params = [outcome]

    with psycopg.connect(checkpointer_dsn, row_factory=dict_row) as conn:
        # A database no run has ever checkpointed into has no tables at all; that is the same
        # answer as an empty fleet, not an error -- `queries.workflow_state`'s guard applies
        # here identically.
        if conn.execute("SELECT to_regclass('checkpoints') AS t").fetchone()["t"] is None:
            return {
                "items": [], "total": 0, "next_offset": None,
                "by_disposition": {}, "unfiltered_total": 0,
            }

        total = conn.execute(
            f"SELECT count(*) AS n FROM ({newest}) AS newest WHERE {narrowed}",
            params + narrowed_params,
        ).fetchone()["n"]

        rows = conn.execute(
            f"""
            SELECT thread_id, checkpoint FROM ({newest}) AS newest
             WHERE {narrowed}
             ORDER BY checkpoint_id DESC
             LIMIT %s OFFSET %s
            """,
            params + narrowed_params + [limit, offset],
        ).fetchall()

        outcome_rows = conn.execute(
            f"SELECT outcome FROM ({newest}) AS newest", params
        ).fetchall()

    items = [
        _run_row(
            row["thread_id"],
            row["checkpoint"],
            identity=identities.get(row["thread_id"].split(":", 1)[0]),
        )
        for row in rows
    ]
    _annotate_liveness(items, store)
    consumed = offset + len(items)
    by_disposition = _grouped(
        [row["outcome"] if row["outcome"] in DISPOSITIONS else None for row in outcome_rows]
    )
    return {
        "items": items,
        "total": total,
        "next_offset": consumed if consumed < total else None,
        "by_disposition": by_disposition,
        "unfiltered_total": len(outcome_rows),
    }


def _annotate_liveness(items: list[dict], store: GraphStore | None) -> None:
    """Attach what the heartbeat table knows about each in-flight run (B194).

    The sweep runs first, so EXPIRED is a recorded transition read back rather than a verdict
    computed per request -- `expired_at` is written once and the moment survives.

    Four answers, and none is guessed: `alive` (a heartbeat inside the window), `expired` (the
    sweep recorded that heartbeats stopped with no clean exit -- for an in-flight run, a process
    that exited without finishing earns the same word, because from outside the two read
    identically and both mean nobody is working on this run), `unmonitored` (no row: the run
    predates the table), and `null` on a terminal run, where liveness is not a question.
    """
    if store is None:
        for item in items:
            item["liveness"] = None if item["outcome"] is not None else "unmonitored"
            item["last_heartbeat_at"] = None
        return

    store.expire_stale_heartbeats()
    beats = store.run_heartbeats([item["thread_id"] for item in items])
    for item in items:
        beat = beats.get(item["thread_id"])
        item["last_heartbeat_at"] = (
            beat["last_heartbeat_at"].isoformat() if beat is not None else None
        )
        if item["outcome"] is not None:
            item["liveness"] = None
        elif beat is None:
            item["liveness"] = "unmonitored"
        elif beat["expired_at"] is not None or beat["stopped_at"] is not None:
            item["liveness"] = "expired"
        else:
            item["liveness"] = "alive"


def _grouped(values: list) -> dict:
    """One count per distinct value, with `None` reported as the named bucket `"null"`.

    Dropping the null rows would understate the denominator by exactly the attempts a nullable
    column was never written for -- the three abandonment classes `corpus._record` returns
    before, for `terminal_status` specifically.
    """
    counts: Counter = Counter("null" if value is None else value for value in values)
    return dict(counts)


def corpus_summary(store: GraphStore, *, repo_id: str | None = None) -> dict:
    """The repair record, aggregated. `attempts` and `distinct_findings` are separate keys.

    One finding retried three times is three rows in `migration_outcome` and one finding here
    too -- `attempts == 3`, `distinct_findings == 1`. Counting findings by counting rows is the
    grain defect `CLAUDE.md` names for this table.

    `repo_id` narrows to one repository's findings (B149).
    """
    outcomes = store.migration_outcomes(repo_id=repo_id)
    return {
        "repo_id": repo_id,
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
    severity: str | None = None,
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

    # Both narrowings are SQL predicates, and that is a latency fix rather than a tidy-up.
    # They were Python list comprehensions over the whole fleet's open findings, so a
    # repository-scoped request fetched every repository's rows and then discarded them --
    # measured at 10,000 findings, the scoped call was *slower than the fleet-wide one*
    # (310 ms against 199 ms), which is the signature of doing the same work plus the filtering.
    # The predicates say the same thing; the difference is where the rows stop.
    narrowing = ""
    params: list[Any] = []
    if repo_id is not None:
        narrowing += " AND call_site.repo_id = %s"
        params.append(repo_id)
    # Narrowed before grouping, so a unit reports the findings of the chosen severity it holds
    # and the sum still equals the flat total for that tab. Filtering the units afterwards would
    # leave each one counting findings the reader is not being shown, which is a grouped table
    # whose parts do not add to the figure above it.
    #
    # A unit with no finding at this severity is absent rather than present at nought -- the
    # grouping returns groups that exist, the rule `by_vendor_severity` already follows.
    if severity is not None:
        narrowing += " AND finding.severity = %s"
        params.append(severity)

    raw_rows = store._connect().execute(
        f"""
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
           {narrowing}
         ORDER BY finding.created_at DESC
        """,
        params,
    ).fetchall()

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
            # The count is stated rather than left to be derived from the array beside it: a
            # console that counted `findings` would report the page it holds, and these rows are
            # not paginated. Findings rather than call sites -- one call broken in two ways is
            # two findings and one site, and that is the case a reviewer most needs to see.
            "finding_count": len(finding_ids),
            "finding_ids": finding_ids,
            # The constituent findings, in the shape the flat table already renders. No extra
            # query: the grouping above has already fetched each finding's call site. One shape
            # rather than a thinner second one, because the copy that did not get a field added
            # later would be the only one missing it.
            #
            # **Bounded, and `finding_count` above is what makes that safe.** `limit` bounds
            # units and nothing bounded this, so the page was unbounded in the dimension that
            # decides its size: measured at 10,000 findings, eight units carried 10,000 nested
            # rows and the response was 4.3 MB. The count beside it is the workspace's and stays
            # exact; this is a sample and the screen says so.
            "findings": [
                {
                    "name": finding_name(
                        row["call_site_vendor_id"],
                        row["call_site_operation_id"],
                        row["finding_id"],
                    ),
                    "file": row["path"],
                    "line": row["line"],
                    "symbol": row["symbol"],
                    "operation": row["call_site_operation_id"],
                    "vendor": row["call_site_vendor_id"],
                    "change_kind": row["change_kind"],
                    "severity": row["severity"],
                    "finding_id": row["finding_id"],
                    "binding_source": row["binding_rung"],
                }
                for row in group_rows[:NESTED_FINDINGS_PER_UNIT]
            ],
            "repo_ids": repo_ids,
            "standing": None,
            "last_checkpoint_at": None,
        }
        units.append(unit)

    if checkpointer_dsn is not None and units:
        # One query for every unit on the page, not one per unit. This was a round trip inside
        # `for u in units`, so a page of fifty units cost fifty queries against a second database
        # -- an N+1 on the route the console's Integrations screen reads. The checkpointer holds
        # one newest checkpoint per thread whichever way it is asked; asking once and keying the
        # answer in Python is the same answer at one round trip.
        by_finding: dict[str, tuple[str | None, object]] = {}
        try:
            with psycopg.connect(checkpointer_dsn, row_factory=dict_row) as conn:
                if conn.execute("SELECT to_regclass('checkpoints') AS t").fetchone()["t"] is not None:
                    wanted = sorted({f_id for u in units for f_id in u["finding_ids"]})
                    if wanted:
                        placeholders = ", ".join(["%s"] * len(wanted))
                        # **The timestamp is a key inside the checkpoint, not a column.**
                        # `checkpoints` holds (thread_id, checkpoint_ns, checkpoint_id,
                        # parent_checkpoint_id, type, checkpoint, metadata) and nothing else, so
                        # the `ts` this query used to select did not exist -- every execution
                        # raised `UndefinedColumn`, the bare `except psycopg.Error` below caught
                        # it, and every unit reported `standing: null` forever. `_run_row` reads
                        # `checkpoint.get("ts")` and is the correct reading; this now matches it.
                        cp_rows = conn.execute(
                            f"""
                            SELECT split_part(thread_id, ':', 1) AS finding_id,
                                   checkpoint,
                                   checkpoint ->> 'ts' AS checkpoint_ts
                              FROM (
                                SELECT DISTINCT ON (thread_id) thread_id, checkpoint_id, checkpoint
                                  FROM checkpoints
                                 WHERE checkpoint_ns = ''
                                 ORDER BY thread_id, checkpoint_id DESC
                              ) AS newest
                             WHERE split_part(thread_id, ':', 1) IN ({placeholders})
                             ORDER BY checkpoint ->> 'ts' DESC NULLS LAST
                            """,
                            wanted,
                        ).fetchall()
                        # Newest first, so the first row seen for a finding is the one that wins --
                        # the same row the per-unit `ORDER BY ... LIMIT 1` meant to return.
                        for row in cp_rows:
                            by_finding.setdefault(
                                row["finding_id"], (row.get("checkpoint"), row.get("checkpoint_ts"))
                            )
                    for u in units:
                        found = [by_finding[f] for f in u["finding_ids"] if f in by_finding]
                        if not found:
                            continue
                        checkpoint, ts_val = max(
                            found, key=lambda pair: (pair[1] is not None, pair[1] or "")
                        )
                        val = (checkpoint or {}).get("channel_values") or {}
                        outcome = val.get("outcome") if val.get("outcome") in DISPOSITIONS else None
                        u["standing"] = outcome or "in_progress"
                        u["last_checkpoint_at"] = (
                            ts_val.isoformat() if hasattr(ts_val, "isoformat")
                            else str(ts_val) if ts_val else None
                        )
        except psycopg.Error:
            pass

    # The ids travel bounded, and this happens *after* the checkpointer join above deliberately:
    # that join reads every finding of a unit to find the newest checkpoint among them, so the
    # standing it reports is the whole unit's and not the sample's. Only the wire is trimmed.
    #
    # Measured: one unit's `finding_ids` was **92,500 bytes** against 8,194 for the `findings`
    # array beside it -- eleven times the rows it identifies, for a field no screen reads. The
    # sample's own ids are on `findings[].finding_id`; `finding_count` remains the population.
    for unit in units:
        unit["finding_ids"] = unit["finding_ids"][:NESTED_FINDINGS_PER_UNIT]

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

    Uses SQL aggregation on GraphStore (B167) or falls back to compute_axes(store.migration_outcomes()).
    """
    if hasattr(store, "corpus_health_aggregates"):
        axes = store.corpus_health_aggregates()
    else:
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



def remediation_activity(store: GraphStore) -> dict:
    """Dashboards L2, L3 and T4: what the repair pipeline attempted, over time and by tier.

    One view rather than three routes, because all three are groupings of one table read at one
    grain and splitting them would be three round trips for one answer. The console renders them
    as separate panels; that is a layout decision and not a reason for three endpoints.

    **One row is one attempt.** `migration_outcome`'s grain, restated here because every figure
    below inherits it: a finding retried three times contributes three attempts, so a total here
    is larger than the finding count on every other screen and neither is wrong.

    **Fleet-wide, and it cannot be otherwise.** `migration_outcome` stores no `repo_id` -- the
    schema decision that makes the table safe to aggregate across customers -- so there is no
    narrower answer being withheld. The console says so on screen rather than implying a scope.
    """
    return {
        "days": store.outcomes_by_day(),
        "by_tier": {str(tier): counts for tier, counts in store.attempts_by_tier().items()},
    }
