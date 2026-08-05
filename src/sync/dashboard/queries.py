"""View models for the dashboard: plain dicts out of the checkpointer.

Every function returns primitives -- dicts, lists, strings, numbers, None --
never live models. A page that received a model could lazily re-query or
mutate it, and the dashboard is read-only by design.

This module reads langgraph-checkpoint-postgres rows directly.
`PostgresSaver.put` inlines primitive channel values in the `checkpoint`
JSONB and splits models out to `checkpoint_blobs`, so everything a page
renders -- diagnostics, outcome, abandon reason, attempt counts -- is
readable without the serialiser, and the models stay where they are.

The thread-id convention is `sync.cli`'s: `{finding_id}:{run_id or
head_sha[:12]}:{generation}`, one generation per finished run. The queries
therefore match threads by finding-id prefix and read the newest checkpoint
across them, which is the run the operator is watching.
"""

from __future__ import annotations

import psycopg
from psycopg.rows import dict_row

# The remediation graph's node order, as `sync.remediate.graph` wires it.
# Mirrored rather than imported: the constraint on this package is that it
# reads checkpoint rows, never graph code, and a row cannot say the order.
WORKFLOW_NODES = (
    "locate", "prepare", "patch", "static_verify",
    "replay", "push_branch", "await_ci", "open_pr",
)

# `report` and `abandon` end a run rather than advance it; they can be the
# pending node mid-hop but are rendered through `outcome`, not as steps.
_TERMINAL_NODES = ("report", "abandon")

# Which RunState keys are one node's evidence. All primitives, so all inline.
_EVIDENCE_KEYS = {
    "locate": ("tier", "routing_row"),
    "prepare": ("prepare_ok", "verifiable", "verify_gap"),
    "patch": ("static_attempts", "attempt_strategy"),
    "static_verify": ("verify_ok", "diagnostics"),
    "replay": ("replay_outcome", "replay_reason", "replay_evidence"),
    "push_branch": ("branch",),
    "await_ci": ("ci_url", "ci_attempts", "attempt_ci_result"),
    "open_pr": ("pr_url", "pr_number"),
}

_FINISHED = ("opened", "abandoned", "reported")


def _like_prefix(finding_id: str) -> str:
    escaped = (
        finding_id.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    )
    return f"{escaped}:%"


def workflow_state(checkpointer_dsn: str, finding_id: str) -> dict | None:
    """The newest generation's workflow state, naming which generation it is.

    A finding retried across generations has one checkpointer thread per
    generation (module docstring above). `sync.dashboard.fleet.runs` lists
    every generation as its own row, so a reader landing here from that list
    needs to know whether this payload is the row they clicked or a newer
    one that superseded it -- `thread_id` and `generation_count` answer
    that; neither is inferable from `outcome` alone.
    """
    with psycopg.connect(checkpointer_dsn, row_factory=dict_row) as conn:
        # A database no run has ever checkpointed into has no tables at all;
        # that is the same answer as a finding with no run, not an error.
        if conn.execute("SELECT to_regclass('checkpoints') AS t").fetchone()["t"] is None:
            return None
        # The newest checkpoint across every thread of this finding, plus how many
        # threads (generations) it has -- one query, one snapshot, so the count
        # can't straddle a write and land inconsistent with the selected row.
        # `checkpoint_id` is a UUIDv6, so text order is creation order, within
        # a thread and across the generations `sync.cli` steps through.
        # Postgres 16 rejects `COUNT(DISTINCT ...) OVER ()`; a scalar subquery
        # in the select list gets the same one-round-trip, one-snapshot result.
        prefix = _like_prefix(finding_id)
        row = conn.execute(
            """
            SELECT thread_id, checkpoint,
                   (SELECT COUNT(DISTINCT thread_id) FROM checkpoints
                     WHERE thread_id LIKE %s AND checkpoint_ns = '') AS generation_count
              FROM checkpoints
             WHERE thread_id LIKE %s AND checkpoint_ns = ''
             ORDER BY checkpoint_id DESC LIMIT 1
            """,
            (prefix, prefix),
        ).fetchone()
    if row is None:
        return None

    checkpoint = row["checkpoint"]
    values = checkpoint.get("channel_values") or {}
    versions = checkpoint.get("channel_versions") or {}
    seen = checkpoint.get("versions_seen") or {}

    # `sync.remediate.state.Outcome` also holds `running`, which `locate` writes on the
    # first hop of every run. Only a finished value is reported: `outcome` is the console's
    # terminal signal, and a live run reaching it stops the poll on a run still in flight.
    outcome = values.get("outcome") if values.get("outcome") in _FINISHED else None
    current = None if outcome is not None else _pending_node(versions, seen)

    nodes = []
    for name in WORKFLOW_NODES:
        if name == current:
            status = "current"
        elif name in seen:
            status = "done"
        else:
            status = "pending"
        evidence = {key: values[key] for key in _EVIDENCE_KEYS[name] if key in values}
        nodes.append({"name": name, "status": status, "evidence": evidence})

    return {
        "nodes": nodes,
        "outcome": outcome,
        "abandon_reason": values.get("abandon_reason"),
        "report_reason": values.get("report_reason"),
        "thread_id": row["thread_id"],
        "generation_count": row["generation_count"],
    }


def _pending_node(versions: dict, seen: dict) -> str | None:
    """The node the graph owes a visit: its trigger updated past what it saw.

    `branch:to:<node>` is the trigger channel langgraph writes for every edge,
    and `versions_seen[node]` records the trigger version the node consumed
    when it last ran -- a newer version still in `channel_versions` means the
    node is due. That is the checkpointer-row shadow of Pregel's own
    next-task rule, and it is what makes a retry loop render honestly: a
    `patch` that already ran once reads as current again, not done.
    """
    for name in (*WORKFLOW_NODES, *_TERMINAL_NODES):
        trigger = f"branch:to:{name}"
        if trigger in versions and seen.get(name, {}).get(trigger) != versions[trigger]:
            return name
    return None
