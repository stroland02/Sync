"""Smoke gate asserting that every selected finding reached a terminal checkpoint.

"A --depth prepare rehearsal against the fixture completes, and every finding it selected
reached a terminal checkpoint." Not a count, not a quality figure. It catches the failure
where a pipeline stops composing or hangs mid-graph.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Sequence

import psycopg
from psycopg.rows import dict_row

_TERMINAL_OUTCOMES = frozenset({"abandoned", "opened", "reported"})


def check_rehearsal_smoke(dsn: str) -> int:
    """Verify that all threads in the checkpointer have reached a terminal outcome.

    Returns:
        0 on success (all threads terminal).
        1 on failure (unterminated threads or no threads found).
    """
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        # Guard: check if checkpoints table exists
        reg = conn.execute("SELECT to_regclass('checkpoints') AS t").fetchone()
        if reg is None or reg["t"] is None:
            print("rehearse smoke: 'checkpoints' table does not exist (skip / unmigrated)", file=sys.stderr)
            return 1

        rows = conn.execute(
            """
            SELECT DISTINCT ON (thread_id)
                   thread_id,
                   checkpoint_id,
                   checkpoint->'channel_values'->>'outcome' AS outcome
              FROM checkpoints
             WHERE checkpoint_ns = ''
             ORDER BY thread_id, checkpoint_id DESC
            """
        ).fetchall()

    if not rows:
        print("rehearse smoke: 0 checkpoint threads found in checkpointer", file=sys.stderr)
        return 1

    unterminated: list[str] = []
    for row in rows:
        outcome = row["outcome"]
        if outcome not in _TERMINAL_OUTCOMES:
            unterminated.append(f"{row['thread_id']} (outcome={outcome!r})")

    if unterminated:
        print(
            f"rehearse smoke: {len(unterminated)} of {len(rows)} thread(s) did not reach a terminal checkpoint:",
            file=sys.stderr,
        )
        for detail in unterminated:
            print(f"  - {detail}", file=sys.stderr)
        return 1

    print(f"rehearse smoke: {len(rows)} thread(s) verified terminal ({', '.join(sorted(_TERMINAL_OUTCOMES))})")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify that all checkpointer rehearsal threads reached a terminal outcome."
    )
    parser.add_argument(
        "--dsn",
        default=os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync"),
        help="PostgreSQL DSN for the checkpointer database",
    )
    args = parser.parse_args(argv)
    return check_rehearsal_smoke(args.dsn)


if __name__ == "__main__":
    sys.exit(main())
