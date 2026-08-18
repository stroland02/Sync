"""Schema convergence for an adopted database, held apart from seeding on purpose.

The embedded cluster outlives any checkout: `~/.sync-postgres` is installed once per machine
and every clone adopts it. Adoption keeps the rows -- a stopped database is somebody's data --
but the schema ships with the code, and a checkout that just pulled today's `main` can meet a
database created before today's tables existed. The first fresh clone after `run_heartbeat`
landed hit exactly that: every precondition green except `schema: 1 table(s) absent`, and the
named fix was `seed_console.py`, which would also write fixture rows into an adopted database
whose rows the doorbell had just promised to keep.

`scripts/apply_schema.py` is the schema-only half: `GraphStore.apply_schema` converges tables
and constraints and touches no rows, so the doorbell can run it on every adoption.
"""

from __future__ import annotations

import os

import psycopg

from sync.graph.store import GraphStore

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")


def test_apply_schema_converges_a_lagging_database_and_says_what_it_added():
    from scripts.apply_schema import converge

    store = GraphStore(DSN)
    store.apply_schema()
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS run_heartbeat CASCADE")
    missing = store.missing_tables()
    assert missing, "the drop did not create the drift this test exists to converge"

    outcome = converge(DSN)

    assert store.missing_tables() == [], "convergence left the schema lagging"
    assert "run_heartbeat" in outcome, (
        "the message must name what was added; a silent migration is how the next drift "
        "gets misread as data loss"
    )


def test_apply_schema_runs_standalone_the_way_the_doorbell_calls_it():
    """`uv run python scripts/apply_schema.py`, not an import: pytest puts the repo root on
    `sys.path` and the doorbell does not, and the first live run died on exactly that
    difference (`ModuleNotFoundError: scripts.seed_console`)."""
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "scripts/apply_schema.py"],
        cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=120, env={**os.environ, "SYNC_GRAPH_DSN": DSN, "PYTHONIOENCODING": "utf-8"},
    )
    assert result.returncode == 0, f"the standalone run failed: {result.stderr}"
    assert result.stdout.strip(), "the run must say what it decided"


def test_apply_schema_on_a_current_database_changes_nothing_and_says_so():
    from scripts.apply_schema import converge

    GraphStore(DSN).apply_schema()

    outcome = converge(DSN)

    assert "Nothing was changed" in outcome, (
        "a no-op that does not say so reads as a hang in the middle of a bring-up"
    )
