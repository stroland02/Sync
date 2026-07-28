"""The naming rule that keeps parallel workers off each other's rows.

`GraphStore.ingest` TRUNCATEs the graph tables, so two pytest processes sharing
one database delete each other's fixtures mid-test. Under `-n auto` that is not
a rare race: an unfixed run produced 59 `DeadlockDetected` errors, every one of
them two workers waiting for AccessExclusiveLock on the same relation.

These assert the naming decision only. That distinct names actually isolate the
runs is a claim about Postgres, and the evidence for it is the suite passing
repeatedly under `-n auto`, not an assertion here.
"""

from __future__ import annotations

from conftest import DEFAULT_DSN, database_for, dsn_for
from psycopg.conninfo import conninfo_to_dict


def test_two_workers_of_one_run_get_two_databases() -> None:
    assert database_for(DEFAULT_DSN, "gw0", 4242) != database_for(DEFAULT_DSN, "gw1", 4242)


def test_a_pinned_dsn_is_left_alone_when_nothing_is_parallel() -> None:
    assert database_for("postgresql://sync:sync@localhost:5433/sync_b5", None, 4242) is None


def test_an_unpinned_serial_run_gets_a_database_of_its_own() -> None:
    assert database_for(None, None, 4242) == "sync_test_4242"


def test_a_worker_subdivides_the_database_it_was_pinned_to() -> None:
    """CI pins `SYNC_DSN`, and so does every worktree on this machine. A worker
    that ignored the pin and derived from the default would connect to whatever
    `localhost:5433` happens to be, which on CI is nothing."""
    assert database_for("postgresql://sync:sync@db:6000/ci_run", "gw3", 4242) == "ci_run_gw3"


def test_two_concurrent_unpinned_runs_do_not_share_a_worker_database() -> None:
    """The pid is what separates two suites launched at once, so it has to
    survive into the per-worker name rather than being replaced by it."""
    assert database_for(None, "gw0", 4242) != database_for(None, "gw0", 9999)


def test_the_admin_connection_keeps_the_host_it_was_given() -> None:
    """`CREATE DATABASE` runs against `postgres` on the same server as the
    target, not against the one the default DSN names."""
    admin = conninfo_to_dict(dsn_for("postgres", "postgresql://sync:sync@db:6000/ci_run"))
    assert (admin["host"], admin["port"], admin["dbname"]) == ("db", "6000", "postgres")
