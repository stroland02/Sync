"""The patch a run produced, served with the place it was pushed.

**A diff is Sync's own artifact.** It is a thing this system wrote and already holds in the run's
checkpoint, so serving it is not blocked on anything -- which is the distinction decisions 21, 26
and 47 each ran into without naming. Customer *source* is different and stays blocked on the
threat-model question of whether a clone outlives its run.

**Owner ruling: the diff and its target travel together.** A diff on its own is the shape a reader
mistakes for a change that has already landed somewhere. Every payload here names the repository
and the branch, so seeing the change and seeing where it went cannot come apart.

The absences are kept separate, because three different things produce no diff and only one of
them is a fault: a run that decided no patch was warranted, a run that gave up before writing one,
and a run still working. Each says which.
"""

from __future__ import annotations

from typing import Any

import psycopg
from psycopg.rows import dict_row

from sync.dashboard.queries import _like_prefix


def diff_stat(diff: str) -> dict[str, int]:
    """How many files a diff touches and how many lines it adds and removes.

    Counted here rather than stored, because the diff is the fact and a stored count beside it is
    a second copy that can disagree. `+++` and `---` are file headers rather than content, and a
    reader who saw them counted would be told a one-line change touched three.
    """
    files = added = removed = 0
    for line in diff.splitlines():
        if line.startswith("+++"):
            files += 1
            continue
        if line.startswith("---"):
            continue
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1
    return {"files_changed": files, "lines_added": added, "lines_removed": removed}


def patch_payload(values: dict[str, Any]) -> dict[str, Any]:
    """Shape one run's state into the patch answer, or into the reason there is not one.

    Pure, and separate from the read, so every branch below is reachable in a test without a
    database. The branches are the substance: this route must never render "no patch" the same
    way for a run that decided against one and a run that has not got there yet.
    """
    patch = values.get("patch")
    target = {
        "repo_id": values.get("repo_id"),
        # `branch` is written by `push_branch`. Absent means the patch was never pushed, which is
        # a different fact from a patch that does not exist, and both can be true at once.
        "branch": values.get("branch"),
        "pr_url": values.get("pr_url"),
        "pr_number": values.get("pr_number"),
    }

    if patch is None:
        return {
            "diff": None,
            "strategy": None,
            "rationale": None,
            "stat": None,
            "target": target,
            "absent_because": _why_no_patch(values.get("outcome")),
        }

    diff = patch["diff"] if isinstance(patch, dict) else patch.diff
    strategy = patch["strategy"] if isinstance(patch, dict) else patch.strategy
    rationale = patch["rationale"] if isinstance(patch, dict) else patch.rationale
    return {
        "diff": diff,
        "strategy": strategy,
        "rationale": rationale,
        "stat": diff_stat(diff),
        "target": target,
        "absent_because": None,
    }


def _why_no_patch(outcome: str | None) -> str:
    """Which kind of nothing this is.

    Three runs produce no diff for three different reasons, and a reader must not be shown one
    sentence for all of them: deciding against a patch is a judgement, giving up is a failure,
    and still running is neither.
    """
    if outcome == "reported":
        return (
            "This run reported rather than patched: routing decided no patch was warranted, so "
            "none was written."
        )
    if outcome == "abandoned":
        return "This run was abandoned before a patch was written."
    if outcome == "opened":
        return (
            "This run opened a pull request but its checkpoint no longer carries the patch -- the "
            "diff is on the branch named beside this, not here."
        )
    return "This run has not produced a patch yet."


def patch_for_finding(checkpointer_dsn: str, finding_id: str) -> dict[str, Any] | None:
    """The newest generation's patch for one finding, or `None` when no run exists.

    A deliberately simpler read than `workflow_state`'s, and **not a candidate for sharing one
    query with it**: that one computes a generation count and per-thread rows in a single
    statement precisely so the count cannot straddle a write, and folding this into it would
    spend that property to save a round trip nobody is waiting on.
    """
    with psycopg.connect(checkpointer_dsn, row_factory=dict_row) as conn:
        # A database no run has ever checkpointed into has no tables at all; that is the same
        # answer as a finding with no run, not an error.
        if conn.execute("SELECT to_regclass('checkpoints') AS t").fetchone()["t"] is None:
            return None
        prefix = _like_prefix(finding_id)
        row = conn.execute(
            """
            SELECT checkpoint FROM checkpoints
             WHERE thread_id LIKE %s AND checkpoint_ns = ''
             ORDER BY checkpoint_id DESC LIMIT 1
            """,
            (prefix,),
        ).fetchone()
    if row is None:
        return None
    values = (row["checkpoint"] or {}).get("channel_values") or {}
    return patch_payload(values)
