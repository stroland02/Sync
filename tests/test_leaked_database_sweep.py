"""The sweep that removes databases a killed run left behind.

A run that is killed never reaches `pytest_unconfigure`, so the database `pytest_configure`
created for it survives. Fifty were on the shared server when this was written and roughly three
hundred had accumulated before a manual sweep earlier the same day.

**This is housekeeping and not correctness.** The intermittent `psycopg.OperationalError` failures
that ran alongside this problem were `max_connections = 100` against a measured peak of 105; the
ceiling is 300 now and the flakiness is gone. A leaked database holds no connections and was never
the cause of anything. Nothing here should be expected to change test reliability, and a future
reader explaining a flake with it has the wrong model.

The next run cleans up after the killed one, inside `pytest_configure`, because that is already
where a database is created and it is exactly when a leak is in the way. No scheduler, no cron, no
separate script anybody has to remember to run.

Three rules make it safe, and each has a test here because each has already gone wrong somewhere:
the pattern must not match the primary `sync` database, the drop must be plain rather than
`WITH (FORCE)` so Postgres refuses a database in use instead of killing its connections, and a
failure to drop must be skipped rather than raised -- cleanup that breaks a suite is worse than the
leak it fixes.
"""

from __future__ import annotations

import os
import subprocess
import sys

import psycopg
import pytest
from psycopg import sql

from conftest import (
    ADMIN_DBNAME,
    DEFAULT_DSN,
    LEAKED_DATABASE_PATTERN,
    dsn_for,
    leaked_database_names,
    pid_is_running,
    sweep_leaked_databases,
)

ADMIN = dsn_for(ADMIN_DBNAME, os.environ.get("SYNC_DSN") or DEFAULT_DSN)


@pytest.fixture()
def dead_pid() -> int:
    """A pid belonging to a process that has certainly finished.

    Spawned and waited on rather than invented, because a number nobody ran is a weaker case: it
    proves the probe rejects nonsense, not that it can tell a finished run from a live one.
    """
    process = subprocess.Popen([sys.executable, "-c", "pass"])
    process.wait()
    return process.pid


@pytest.fixture()
def made():
    """Databases this test created, dropped afterwards whatever the test did to them."""
    created: list[str] = []

    def make(name: str) -> str:
        with psycopg.connect(ADMIN, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        created.append(name)
        return name

    yield make

    with psycopg.connect(ADMIN, autocommit=True) as conn:
        for name in created:
            conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))


def _exists(name: str) -> bool:
    with psycopg.connect(ADMIN, autocommit=True) as conn:
        return conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone() is not None


# --- the liveness test -------------------------------------------------------------


def test_the_probe_tells_a_finished_process_from_a_running_one(dead_pid):
    """The whole sweep rests on this one answer, so it is tested on its own.

    `os.kill(pid, 0)` is the portable idiom and it does not work here. Measured on this machine,
    Python 3.12 on Windows: against the pid of a process that has already exited it returns
    without raising, because a handle to the finished process is still open and the process object
    therefore still exists. It answers "is this a plausible pid" rather than "is anything running",
    which is the question the sweep has to ask.
    """
    assert pid_is_running(os.getpid()) is True
    assert pid_is_running(dead_pid) is False


def test_the_probe_treats_an_unanswerable_pid_as_alive():
    """Unsure means alive, in every direction.

    A wrong True costs one leaked database surviving until the next run. A wrong False drops a
    database out from under a suite that is using it. The two are not comparable, so every
    uncertain answer resolves the same way.
    """
    assert pid_is_running(0) is True
    assert pid_is_running(-1) is True


# --- what the sweep selects --------------------------------------------------------


def test_a_database_named_for_a_dead_pid_is_swept(dead_pid, made):
    name = made(f"sync_test_{dead_pid}_gw0")
    assert _exists(name)

    dropped = sweep_leaked_databases(ADMIN)

    assert name in dropped
    assert not _exists(name)


def test_a_database_named_for_a_live_pid_survives(made):
    """The test that stops the sweep eating a running suite.

    This process is the live one, and its own pid is in the name -- exactly the shape
    `pytest_configure` gives the database a concurrent run is using right now.
    """
    name = made(f"sync_test_{os.getpid()}_gw9")

    dropped = sweep_leaked_databases(ADMIN)

    assert name not in dropped
    assert _exists(name)


def test_the_primary_database_is_never_matched_by_the_pattern():
    """The mistake that took the server down, asserted against the real catalogue.

    `LIKE 'sync%'` matches the primary `sync` database, which `POSTGRES_DB` creates and
    `DEFAULT_DSN` points at. The pattern has to match only what `conftest` itself creates.

    Non-vacuous by construction: the primary database is asserted to exist, so the pattern is
    being asked about a name that is really there. Widening `LEAKED_DATABASE_PATTERN` to `sync%`
    turns this red.
    """
    with psycopg.connect(ADMIN, autocommit=True) as conn:
        assert conn.execute("SELECT 1 FROM pg_database WHERE datname = 'sync'").fetchone(), (
            "the primary database must exist or this proves nothing"
        )
        matched = {
            row[0]
            for row in conn.execute(
                "SELECT datname FROM pg_database WHERE datname LIKE %s", (LEAKED_DATABASE_PATTERN,)
            ).fetchall()
        }

    assert "sync" not in matched
    assert all(name.startswith("sync_test_") for name in matched)


def test_a_pinned_development_database_is_not_matched():
    """`sync_b14` and `sync_w50` are on that server and look like deliberate pins."""
    candidates = [
        "sync",
        "sync_b14",
        "sync_w50",
        "sync_w69_gw0_score",
        "sync_docs",
        "postgres",
        "sync_test_1_gw0",
    ]

    assert leaked_database_names(candidates, is_running=lambda pid: False) == ["sync_test_1_gw0"]


def test_every_name_conftest_creates_is_swept_when_its_run_is_gone():
    """The three shapes `database_for` produces, plus the suffixed ones fixtures derive from it.

    `sync_test_<pid>` is a serial or controller run, `sync_test_<pid>_gw5` a worker, and
    `sync_test_<pid>_gw6_score` a fixture that subdivided the worker's name again. All three leak
    the same way and the pattern has to reach all three.
    """
    candidates = ["sync_test_4242", "sync_test_4242_gw5", "sync_test_4242_gw6_score"]

    assert leaked_database_names(candidates, is_running=lambda pid: False) == sorted(candidates)


def test_the_name_this_process_is_about_to_create_is_never_swept():
    """Low risk inside `pytest_configure` and a real one for anything standalone."""
    name = "sync_test_4242_gw5"

    assert leaked_database_names([name], is_running=lambda pid: False) == [name]
    assert leaked_database_names([name], is_running=lambda pid: False, exclude=name) == []


# --- how the sweep drops -----------------------------------------------------------


def test_a_database_in_use_is_refused_rather_than_force_dropped(dead_pid, made):
    """Plain `DROP DATABASE` over `WITH (FORCE)`.

    A snapshot of live connections taken at sweep start is stale the moment another suite begins,
    so letting Postgres refuse is stronger than racing it. The database here is named for a dead
    pid, so the sweep genuinely tries to drop it and is genuinely refused -- if the name were live
    the liveness test would have skipped it and this would prove nothing.
    """
    name = made(f"sync_test_{dead_pid}_gw1")

    with psycopg.connect(dsn_for(name, ADMIN), autocommit=True) as holder:
        holder.execute("SELECT 1")
        dropped = sweep_leaked_databases(ADMIN)

    assert name not in dropped
    assert _exists(name)


def test_a_database_that_cannot_be_dropped_does_not_fail_the_run(dead_pid, made):
    """Cleanup that breaks a suite is worse than the leak it fixes.

    The refusal above must be skipped rather than raised, and the sweep must go on to drop the
    other leaked databases rather than stopping at the first one it cannot have.
    """
    held = made(f"sync_test_{dead_pid}_gw2")
    free = made(f"sync_test_{dead_pid}_gw3")

    with psycopg.connect(dsn_for(held, ADMIN), autocommit=True) as holder:
        holder.execute("SELECT 1")
        dropped = sweep_leaked_databases(ADMIN)

    assert free in dropped and not _exists(free)
    assert held not in dropped and _exists(held)


def test_a_server_that_cannot_be_reached_is_not_an_error():
    """`pytest_configure` already warns and carries on when Postgres is absent; so does this."""
    assert sweep_leaked_databases("postgresql://sync:sync@localhost:1/postgres") == []
