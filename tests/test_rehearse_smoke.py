"""Tests for rehearsal smoke assertion on checkpointer terminal outcomes."""

import os
from pathlib import Path
import psycopg
import pytest

from scripts.rehearse_smoke import check_rehearsal_smoke

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")


@pytest.fixture()
def checkpointer_tables():
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS checkpoint_blobs CASCADE")
        conn.execute("DROP TABLE IF EXISTS checkpoint_writes CASCADE")
        conn.execute("DROP TABLE IF EXISTS checkpoints CASCADE")
        conn.execute("""
            CREATE TABLE checkpoints (
                thread_id TEXT NOT NULL,
                checkpoint_ns TEXT NOT NULL DEFAULT '',
                checkpoint_id TEXT NOT NULL,
                parent_checkpoint_id TEXT,
                type TEXT,
                checkpoint JSONB NOT NULL,
                metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
            )
        """)
    yield
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS checkpoint_blobs CASCADE")
        conn.execute("DROP TABLE IF EXISTS checkpoint_writes CASCADE")
        conn.execute("DROP TABLE IF EXISTS checkpoints CASCADE")


def _insert_checkpoint(thread_id: str, checkpoint_id: str, channel_values: dict):
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute(
            """
            INSERT INTO checkpoints (thread_id, checkpoint_ns, checkpoint_id, checkpoint)
            VALUES (%s, '', %s, %s::jsonb)
            """,
            (thread_id, checkpoint_id, psycopg.types.json.Jsonb({"channel_values": channel_values})),
        )


def test_rehearsal_smoke_passes_when_all_threads_reach_terminal_outcome(checkpointer_tables):
    _insert_checkpoint("finding-1:rehearsal-2026-08-05:0", "chk-1", {"outcome": "reported"})
    _insert_checkpoint("finding-2:rehearsal-2026-08-05:0", "chk-2", {"outcome": "abandoned"})

    exit_code = check_rehearsal_smoke(DSN)
    assert exit_code == 0


def test_rehearsal_smoke_fails_when_a_thread_is_unterminated(checkpointer_tables):
    _insert_checkpoint("finding-1:rehearsal-2026-08-05:0", "chk-1", {"outcome": "reported"})
    # Thread 2 is pending at a node without a terminal outcome
    _insert_checkpoint("finding-2:rehearsal-2026-08-05:0", "chk-2", {"outcome": "running"})

    exit_code = check_rehearsal_smoke(DSN)
    assert exit_code == 1


def test_rehearsal_smoke_fails_when_zero_threads_present(checkpointer_tables):
    exit_code = check_rehearsal_smoke(DSN)
    assert exit_code == 1


def test_ci_runs_rehearsal_smoke_gate():
    ci_path = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"
    content = ci_path.read_text(encoding="utf-8")
    assert "scripts/rehearse_smoke.py" in content, (
        "ci.yml must wire scripts/rehearse_smoke.py as a gated step"
    )

