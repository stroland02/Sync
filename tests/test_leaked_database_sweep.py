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
from psycopg.conninfo import conninfo_to_dict

from conftest import (
    ADMIN_DBNAME,
    admin_connection,
    create_database,
    database_for,
    DEFAULT_DSN,
    LEAKED_DATABASE_PATTERN,
    drop_database,
    drop_databases_best_effort,
    dsn_for,
    leaked_database_names,
    pid_is_running,
    sweep_leaked_databases,
)

ADMIN = dsn_for(ADMIN_DBNAME, os.environ.get("SYNC_DSN") or DEFAULT_DSN)

OWN_DATABASE = conninfo_to_dict(os.environ.get("SYNC_DSN") or DEFAULT_DSN)["dbname"]
"""The database this run is using, which the sweeps below must never take.

Every sweep in this file that lies about liveness has to be told to spare this name, because the
lie is not narrow enough to spare it on its own. `dead_to_the_sweep` says *every pid equal to this
process's is dead*, and under `-n0` the run's own database is `sync_test_<this pid>` -- one pid,
and it is that one. Under `-n auto` the name is `sync_test_<controller>_gw0_p<this pid>`, the
controller's pid reads as alive, and the name is spared by accident. That accident is why a whole
run configuration was broken for an unknown length of time: `addopts` pins `-n auto`, so nobody
reached the case where it does not happen. `docs/superpowers/reports/2026-07-30-n0-is-broken.md`.
"""


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
    """Databases this test created, dropped afterwards whatever the test did to them.

    Both halves go through `conftest.admin_connection`, so neither can wait forever on the
    checkpoint every `DROP DATABASE` requests -- this teardown is one of the two places B132
    caught a serial run blocked. The teardown is best-effort on top of that: a name it could
    not drop is one the next run's sweep takes, and this file is where that sweep is tested.
    """
    created: list[str] = []

    def make(name: str) -> str:
        with admin_connection(ADMIN) as conn:
            drop_database(conn, name)
            create_database(conn, name)
        created.append(name)
        return name

    yield make

    drop_databases_best_effort(ADMIN, *created)


def _exists(name: str) -> bool:
    with admin_connection(ADMIN) as conn:
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
    with admin_connection(ADMIN) as conn:
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
    # Named for this live process and told to the sweep as dead, rather than named for a dead
    # pid: a genuinely dead-named database is correctly dropped by any suite sweeping the same
    # server in the window before the connect below, and this test then fails on the connect
    # itself. Reproduced twice while writing this, with the error the investigation began from.
    name = made(f"sync_test_{os.getpid()}_gw1")
    dead_to_the_sweep = lambda pid: pid != os.getpid()  # noqa: E731

    with psycopg.connect(dsn_for(name, ADMIN), autocommit=True) as holder:
        holder.execute("SELECT 1")
        dropped = sweep_leaked_databases(ADMIN, is_running=dead_to_the_sweep, exclude=OWN_DATABASE)

    assert name not in dropped
    assert _exists(name)


def test_a_database_that_cannot_be_dropped_does_not_fail_the_run(dead_pid, made):
    """Cleanup that breaks a suite is worse than the leak it fixes.

    The refusal above must be skipped rather than raised, and the sweep must go on to drop the
    other leaked databases rather than stopping at the first one it cannot have.
    """
    # Named for this process, which is alive, so a suite sweeping the same server concurrently
    # spares them; the sweep under test is told they are dead instead. Named for a genuinely dead
    # pid these are correctly dropped by that other sweep in the window before the connect below,
    # and the test then fails with `database ... does not exist` -- which is the failure this
    # investigation started from, reproduced twice while writing this.
    held = made(f"sync_test_{os.getpid()}_gw2")
    free = made(f"sync_test_{os.getpid()}_gw3")
    # Dead for exactly this process and alive for every other, so the sweep under test drops
    # these two and leaves another suite's databases alone. A blanket `False` would have this
    # test drop every leaked-looking database on a shared server, including live ones.
    dead_to_the_sweep = lambda pid: pid != os.getpid()  # noqa: E731

    with psycopg.connect(dsn_for(held, ADMIN), autocommit=True) as holder:
        holder.execute("SELECT 1")
        dropped = sweep_leaked_databases(ADMIN, is_running=dead_to_the_sweep, exclude=OWN_DATABASE)

    assert free in dropped and not _exists(free)
    assert held not in dropped and _exists(held)


def test_a_server_that_cannot_be_reached_is_not_an_error():
    """`pytest_configure` already warns and carries on when Postgres is absent; so does this."""
    assert sweep_leaked_databases("postgresql://sync:sync@localhost:1/postgres") == []


# --- what the name's pid actually identifies -------------------------------------------


def test_a_worker_database_is_named_for_the_process_that_will_not_use_it():
    """The hole, stated as the fact it rests on.

    `pytest_configure` exports `SYNC_DSN` before xdist spawns any worker, so every worker reads
    the controller's database as its pin and subdivides it. The pid in `sync_test_28096_gw2` is
    therefore the **controller's**, and the worker's own pid appears nowhere -- measured by
    running a two-worker suite, whose workers had pids 15944 and 34508 and whose databases were
    `sync_test_30080_gw0` and `sync_test_30080_gw1`.

    So the sweep's liveness test asks about a process that is not the one using the database. It
    is right whenever the controller outlives its workers, which is every ordinary run, and wrong
    exactly when it does not.
    """
    controller_pin = dsn_for("sync_test_28096", DEFAULT_DSN)

    name = database_for(controller_pin, "gw2", 51234)

    assert name.startswith("sync_test_28096_gw2")
    assert "28096" in name, "the controller's pid is what the name has always carried"


def test_a_worker_database_carries_the_worker_that_uses_it():
    """The guard. The name keeps the controller's pid, because an operator reads it to find the
    run, and gains the pid of the process the database actually belongs to."""
    controller_pin = dsn_for("sync_test_28096", DEFAULT_DSN)

    assert database_for(controller_pin, "gw2", 51234) == "sync_test_28096_gw2_p51234"


def test_a_pinned_database_a_person_chose_gains_no_pid(made):
    """`sync_b5_gw0` is what an operator asked for and is outside the swept pattern entirely.
    Appending a pid there would be noise in a name nobody sweeps."""
    assert database_for(dsn_for("sync_b5", DEFAULT_DSN), "gw0", 51234) == "sync_b5_gw0"


# --- the three interleavings ------------------------------------------------------------


def test_a_name_whose_pid_is_alive_survives():
    """Interleaving one: the ordinary case, and the one the current implementation already gets
    right."""
    assert leaked_database_names(["sync_test_777_gw1"], is_running=lambda pid: pid == 777) == []


def test_a_name_whose_only_pid_died_is_swept():
    """Interleaving two: the case the sweep exists for."""
    assert leaked_database_names(["sync_test_777_gw1"], is_running=lambda pid: False) == [
        "sync_test_777_gw1"
    ]


def test_a_database_whose_controller_died_while_its_worker_lives_is_spared():
    """Interleaving three, and the one the sweep failed.

    A controller killed before its workers leaves them running against databases named for a pid
    that is now dead. The sweep judged the name dead, and a plain `DROP DATABASE` does not refuse
    an idle database -- measured directly: dropping a database nobody is connected to succeeds,
    and only an open connection makes the server refuse. So a worker between two queries loses
    the database out from under it and fails on its next connect with exactly the error this
    investigation started from.

    Sparing it needs the worker's own pid in the name and a rule that reads every pid there.
    """
    name = "sync_test_28096_gw2_p51234"
    controller_dead_worker_alive = lambda pid: pid == 51234  # noqa: E731

    assert leaked_database_names([name], is_running=controller_dead_worker_alive) == []


def test_a_database_is_swept_only_when_every_pid_in_its_name_is_dead():
    """The rule stated in both directions. Either pid alive spares it; both dead sweeps it.

    Tightening rather than widening: a name this rule spares is a name the old rule would have
    dropped, never the reverse, so it cannot make the sweep reach further than it did.
    """
    name = "sync_test_28096_gw2_p51234"

    assert leaked_database_names([name], is_running=lambda pid: pid == 28096) == []
    assert leaked_database_names([name], is_running=lambda pid: pid == 51234) == []
    assert leaked_database_names([name], is_running=lambda pid: False) == [name]


def test_a_recycled_pid_anywhere_in_the_name_spares_the_database():
    """Pid reuse, which the file's own comment argued could not disturb a live run. It cannot
    cause a wrong drop, and this pins the direction it does err in: a name holding a recycled pid
    is spared and leaks until a later run, which costs one database rather than a live one."""
    assert leaked_database_names(
        ["sync_test_28096_gw2_p51234"], is_running=lambda pid: pid == 28096
    ) == []


# --- the canary ---------------------------------------------------------------------------


def test_the_run_s_own_database_survives_every_sweep_in_this_file():
    """Last in the file, and it is meant to be: it reports on what ran before it.

    Two tests above hand the sweep a predicate that calls this process dead so their own fixture
    databases are eligible. Under `-n0` that predicate also reaches the database
    `pytest_configure` created for this run, and a plain `DROP DATABASE` does not refuse an idle
    one -- so the run loses its own database partway through this file and every later test
    needing Postgres errors in setup. 186 of them in a full suite.

    This cannot fail under `-n auto`, where the name carries a second pid that reads as alive.
    `test_serial_run_isolation.py` is what runs it serially, because `addopts` pins `-n auto` and
    nothing in an ordinary suite run would ever reach the broken case.
    """
    assert _exists(OWN_DATABASE), (
        f"{OWN_DATABASE} is the database this run is using and a sweep in this file took it"
    )
