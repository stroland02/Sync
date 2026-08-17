"""Tests for rehearsal smoke assertion on checkpointer terminal outcomes.

This module stands its own `checkpoints` table up by hand rather than through `PostgresSaver`,
because what it tests reads that one table and nothing else. The cost of doing so is that it
also has to put the database back the way `PostgresSaver.setup()` expects to find it, and for
most of its life it did not -- see `_drop_checkpointer_tables`.
"""

import os
from pathlib import Path
import psycopg
import pytest

from scripts.rehearse_smoke import check_rehearsal_smoke

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")

# `checkpoint_migrations` is the fourth one and leaving it out is not a tidiness question.
# `PostgresSaver.setup()` reads the highest version recorded there and applies only the
# migrations above it, so a ledger left behind with its tables gone makes every later `setup()`
# a silent no-op: the caller is told the schema is current and the first INSERT gets `relation
# "checkpoints" does not exist`. That is what happened to eleven of `tests/test_seed_console.py`
# on every serial CI run, because this module sorts before it and shares its database. It cannot
# happen under `-n auto` unless the scheduler puts both files in one worker, which is why the
# serial job is the one that saw it.
_CHECKPOINTER_TABLES = (
    "checkpoint_blobs", "checkpoint_writes", "checkpoints", "checkpoint_migrations",
)


def _drop_checkpointer_tables() -> None:
    with psycopg.connect(DSN, autocommit=True) as conn:
        for table in _CHECKPOINTER_TABLES:
            conn.execute(f"DROP TABLE IF EXISTS {table} CASCADE")


@pytest.fixture()
def checkpointer_tables():
    _drop_checkpointer_tables()
    with psycopg.connect(DSN, autocommit=True) as conn:
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
    _drop_checkpointer_tables()


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


def test_what_this_module_drops_a_later_setup_can_rebuild():
    """The cleanup contract, asserted rather than assumed.

    Nothing in this file uses `PostgresSaver`, so nothing in it would ever notice that its
    teardown had made `PostgresSaver.setup()` unable to do its job -- the damage lands in
    whichever module runs next against the same database, wearing a traceback that names that
    module's code and none of this one's.

    Written against `_drop_checkpointer_tables` rather than against the fixture because the
    helper is what the fixture and any future caller share: a table added to the drop list
    without its ledger companion fails here, not three files later.
    """
    from langgraph.checkpoint.postgres import PostgresSaver

    with PostgresSaver.from_conn_string(DSN) as saver:
        saver.setup()

    _drop_checkpointer_tables()

    with PostgresSaver.from_conn_string(DSN) as saver:
        saver.setup()

    try:
        with psycopg.connect(DSN, autocommit=True) as conn:
            present = conn.execute("SELECT to_regclass('checkpoints')").fetchone()[0]
        assert present is not None, (
            "PostgresSaver.setup() left no `checkpoints` table, so this module's teardown "
            "stranded `checkpoint_migrations` at a version whose tables are gone and every "
            "later setup() on this database is a no-op that reports success"
        )
    finally:
        _drop_checkpointer_tables()


def test_ci_runs_rehearsal_smoke_gate():
    ci_path = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"
    content = ci_path.read_text(encoding="utf-8")
    assert "scripts/rehearse_smoke.py" in content, (
        "ci.yml must wire scripts/rehearse_smoke.py as a gated step"
    )

