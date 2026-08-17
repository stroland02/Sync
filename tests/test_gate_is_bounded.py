"""The local gate has to terminate, and it has to say why it declined to run something.

`uv run pytest tests/ -q -n0` is the command `CLAUDE.md` names as the authority over this
repository's health, and on 2026-08-16 it was killed after 70 minutes having printed nothing.
It was not deadlocked. Every admin connection this suite opens against Postgres was unbounded
-- no `connect_timeout`, no `statement_timeout`, no `lock_timeout` -- and `DROP DATABASE`
forces an immediate cluster-wide checkpoint and takes an object lock on the database while it
waits for one. Under several concurrent runs those serialise, and a run that is merely starved
is indistinguishable from a run that is stuck, so an operator kills it. That is the failure
this file exists to make impossible: not "the suite is fast", which no test can promise, but
"no single step of it can wait forever, and a step that gives up says what it was waiting for".

The second half is the same property one level out. Three tests need a container runtime, and
a developer without one got `RuntimeError: docker create failed:` from inside the test body --
a failure that reads as a defect in `sync.remediate.sandbox` rather than as an absent local
toolchain. A precondition the machine cannot satisfy is a skip with a reason, decided once at
collection, the way `conftest.pytest_configure` already decides the Postgres precondition once.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict

import conftest
from conftest import ADMIN_DBNAME, DEFAULT_DSN, dsn_for

REPO_ROOT = Path(__file__).resolve().parents[1]

ADMIN = dsn_for(ADMIN_DBNAME, os.environ.get("SYNC_DSN", DEFAULT_DSN))

OWN_DATABASE = conninfo_to_dict(os.environ.get("SYNC_DSN", DEFAULT_DSN))["dbname"]
"""The database this run is using, which the sweep below must be told to spare.

Under `-n0` the run's own database is `sync_test_<this pid>`, and the sweep below is handed a
liveness answer that calls this process's pid dead -- so without `exclude` the one name it is
most certain to select is the one holding the run. A zero budget means no drop is attempted
today, which is not a reason to leave the guard out: the next person to change what the budget
means should not be able to delete a live suite's database by accident.
"""

UNREACHABLE_DOCKER_HOST = "tcp://127.0.0.1:1"
"""A port nothing listens on, so the Docker CLI fails to reach a daemon immediately.

Reaching for `DOCKER_HOST` rather than stopping Docker Desktop is not a convenience: the
Postgres this suite runs against is a container on the same daemon, and so are three other
worktrees' runs. The code under test resolves its daemon exactly as any other caller does,
so pointing it somewhere dead is the real condition, not a simulation of it.
"""


# --- the watchdog over everything else ----------------------------------------------


def test_the_gate_carries_a_watchdog_that_can_actually_fire(request):
    """A declared bound and an installed plugin, because either alone does nothing.

    `timeout = 900` in `pyproject.toml` with `pytest-timeout` absent is an unknown ini key that
    pytest ignores with a warning, which is the shape `.claude/rules/test-discipline.md` calls a
    test that cannot fail -- it reads as a bound and enforces none. The two are asserted
    together so removing either turns this red.

    The number is not the point and is deliberately not pinned: what has to stay true is that
    some finite bound exists, so a hang arrives as a named test with a stack rather than as a
    terminal an operator eventually kills.
    """
    assert importlib.util.find_spec("pytest_timeout") is not None, (
        "pyproject declares `timeout` but nothing enforces it; pytest ignores an ini key no "
        "plugin claims, so the gate would read as bounded and hang exactly as before"
    )
    assert float(request.config.getini("timeout")) > 0


# --- the database side: no admin statement may wait forever -------------------------


def test_an_admin_connection_carries_a_statement_and_a_lock_timeout():
    """The bound is on the server, not on the client, and that distinction is the point.

    A client-side wait can be abandoned while the backend keeps holding what it acquired.
    `statement_timeout` and `lock_timeout` are the server cancelling its own work, which is
    what makes the next run's sweep able to take the same database.
    """
    with conftest.admin_connection(ADMIN) as conn:
        assert conn.execute("SHOW statement_timeout").fetchone()[0] != "0"
        assert conn.execute("SHOW lock_timeout").fetchone()[0] != "0"


def test_a_blocked_admin_statement_is_cancelled_rather_than_waited_on():
    """Proven against the server rather than by reading back a setting.

    `SHOW statement_timeout` says a GUC was accepted. It does not say the backend honours it
    for the statement this suite actually blocks in, and the whole defect here was a wait
    nobody had measured. `pg_sleep` is the cheapest statement that certainly outlasts the
    bound; the assertion is that control returns, and quickly.
    """
    with conftest.admin_connection(ADMIN, statement_timeout_ms=1_000) as conn:
        started = time.perf_counter()
        with pytest.raises(psycopg.errors.QueryCanceled):
            conn.execute("SELECT pg_sleep(30)")
        assert time.perf_counter() - started < 15


def test_a_drop_that_cannot_finish_names_the_database_it_was_waiting_for():
    """The message is the deliverable, not the exception type.

    An operator meets this at the moment a gate they trusted stops, and `QueryCanceled:
    canceling statement due to statement timeout` names neither the database nor the reason a
    drop waits. `DROP DATABASE` requests an immediate checkpoint and waits for it -- measured
    at 282 ms median on an idle stock server and over 15 s on this machine's shared one under
    four concurrent suites -- so a 1 ms bound cannot be met by any real drop, and the margin is
    16x even against a server with durability turned off.
    """
    # Named for this process's pid so the sweep can take it if the cleanup below cannot: an
    # `IF EXISTS` drop of a name with no pid in it is invisible to `leaked_database_names` and
    # would sit on the server until somebody noticed it by hand.
    name = f"sync_test_{os.getpid()}_b132bound"
    with conftest.admin_connection(ADMIN) as setup:
        conftest.drop_database(setup, name)
        conftest.create_database(setup, name)

    try:
        with conftest.admin_connection(ADMIN, statement_timeout_ms=1) as conn:
            with pytest.raises(TimeoutError) as raised:
                conftest.drop_database(conn, name)
        assert name in str(raised.value)
        assert "checkpoint" in str(raised.value).lower()
    finally:
        conftest.drop_databases_best_effort(ADMIN, name)


def test_the_sweep_stops_at_its_budget_rather_than_working_through_the_list():
    """The budget `pytest_configure` passes, proven to stop real work rather than an empty list.

    A zero budget returning `[]` proves nothing on a server with nothing to sweep, so this puts
    a database in front of it first and requires that the database survive. The control is that
    the same name is one the sweep had *selected* -- asserted against `leaked_database_names`
    rather than by sweeping again for real, because a second sweep's outcome depends on how
    long a drop takes on a contended server and this property does not.

    `is_running` spares every pid but this process's own, which is what makes the test safe to
    run beside three other worktrees' suites: a sweep that judged their databases dead would
    drop the idle ones outright, which `sweep_leaked_databases` documents and this test must
    not cause.
    """
    own = os.getpid()
    only_mine_is_dead = lambda pid: pid != own  # noqa: E731 - one expression, named where used
    name = f"sync_test_{own}_gw0"

    with conftest.admin_connection(ADMIN) as setup:
        conftest.drop_database(setup, name)
        conftest.create_database(setup, name)

    try:
        stopped = conftest.sweep_leaked_databases(
            ADMIN, is_running=only_mine_is_dead, exclude=OWN_DATABASE, budget_seconds=0
        )
        assert stopped == []

        with conftest.admin_connection(ADMIN) as conn:
            assert conn.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (name,)
            ).fetchone(), "a spent budget must leave the database for a later run, not drop it"
            candidates = [
                row[0]
                for row in conn.execute(
                    "SELECT datname FROM pg_database WHERE datname LIKE %s",
                    (conftest.LEAKED_DATABASE_PATTERN,),
                ).fetchall()
            ]

        assert name in conftest.leaked_database_names(
            candidates, is_running=only_mine_is_dead, exclude=OWN_DATABASE
        ), "the budget has to be the only reason this survived, not the selection"
    finally:
        conftest.drop_databases_best_effort(ADMIN, name)


# --- the container side: an absent runtime is a skip, and it says so ----------------


def test_a_reachable_docker_daemon_reports_no_reason_to_skip():
    """The positive control, and without it the test below proves nothing.

    A probe that answered "unavailable" unconditionally would pass the unreachable case and
    silently convert three container tests into permanent skips -- the shape
    `.claude/rules/test-discipline.md` calls a test that cannot fail. This machine runs Docker
    Desktop, so the honest answer here is `None`.
    """
    assert conftest.docker_unavailable_reason() is None


def test_a_docker_endpoint_nothing_answers_reports_a_reason_naming_the_toolchain():
    started = time.perf_counter()
    reason = conftest.docker_unavailable_reason(
        env={**os.environ, "DOCKER_HOST": UNREACHABLE_DOCKER_HOST}
    )
    assert time.perf_counter() - started < 60, "the probe itself has to be bounded"

    assert reason is not None
    assert "docker" in reason.lower()


def test_a_refused_connection_and_an_unanswered_one_are_told_apart():
    """B184: the two ways of not answering are different facts, and only one is absence.

    A machine with no daemon refuses immediately -- the daemon's own words are `error during
    connect` -- and that is genuinely "Docker is not here". A daemon that exists and is buried
    under load answers nothing until the budget expires, which is not the same statement and
    must not be reported as though it were.
    """
    refused = conftest.probe_docker(env={**os.environ, "DOCKER_HOST": UNREACHABLE_DOCKER_HOST})

    assert refused.reason is not None
    assert not refused.timed_out, (
        "a refused connection is an answer -- reporting it as a timeout would send whoever "
        f"reads it looking for a busy daemon instead of an absent one: {refused.reason}"
    )


def test_a_daemon_that_never_answers_stops_the_run_instead_of_skipping_the_boundary_tests(
    monkeypatch,
):
    """B184: an unanswered probe must not be quietly converted into "Docker is absent".

    The collection hook turns an absent runtime into a skip, which is right. The hazard is
    that it did so for *every* unavailability, including a probe that simply ran out of time.
    That probe runs once per xdist worker at collection, so a full `-n auto` run puts sixteen
    `docker version` calls on the daemon in the same instant -- and if that budget ever expired
    the result was a silent mass skip of exactly the tests carrying B97's boundary claim.

    A skip says "this does not apply here". "We could not tell" is a different sentence, and
    collapsing the second onto the first is the failure this whole area exists to refuse.
    """
    monkeypatch.setattr(
        conftest, "probe_docker",
        lambda env=None: conftest.DockerProbe("docker did not answer within 30s", timed_out=True),
    )

    class _FakeItem:
        def __init__(self):
            self.markers = []

        def get_closest_marker(self, name):
            return object() if name == conftest.DOCKER_MARKER else None

        def add_marker(self, marker):
            self.markers.append(marker)

    item = _FakeItem()
    with pytest.raises(Exception) as raised:
        conftest.pytest_collection_modifyitems(config=None, items=[item])

    assert not item.markers, "a probe that timed out must not be reported as a skip"
    assert "did not answer" in str(raised.value), (
        f"the failure has to say the daemon was silent rather than absent: {raised.value}"
    )


def test_the_container_tests_skip_rather_than_error_when_no_daemon_answers():
    """The wiring, driven the way a developer without Docker Desktop meets it.

    A child rather than an in-process assertion, because what is under test is a collection
    hook's effect on a whole run: whether the three marked tests report as skipped with a
    reason, or as errors from inside `sync.remediate.sandbox`. `SYNC_DSN` is passed through
    deliberately -- `conftest.database_for` returns `None` for a pinned serial run, so the
    child creates and drops no database of its own and adds nothing to the churn this file's
    first half is about.
    """
    env = {
        **os.environ,
        "DOCKER_HOST": UNREACHABLE_DOCKER_HOST,
        "PYTHONIOENCODING": "utf-8",
        "SYNC_DSN": os.environ.get("SYNC_DSN", DEFAULT_DSN),
    }
    for inherited in ("PYTEST_XDIST_WORKER", "PYTEST_XDIST_TESTRUNUID", "PYTEST_CURRENT_TEST"):
        env.pop(inherited, None)

    child = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-n0", "-rs", "--color=no",
         "-p", "no:cacheprovider", "-m", "docker", "tests/test_patch_sandbox.py"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )

    assert child.returncode == 0, (
        f"a run with no reachable daemon exited {child.returncode}\n"
        f"--- stdout ---\n{child.stdout}\n--- stderr ---\n{child.stderr}"
    )
    assert "4 skipped" in child.stdout, (
        f"expected all four @pytest.mark.docker tests in test_patch_sandbox.py to skip, got:\n"
        f"{child.stdout}"
    )
    # The counts line rather than the whole output: the skip reason quotes the daemon, and the
    # daemon's own words for an unanswered endpoint are "error during connect". Asserting on
    # the transcript would fail on a message that is exactly what this test wants to see.
    counts = [line for line in child.stdout.splitlines() if line.strip()][-1].lower()
    assert "error" not in counts and "failed" not in counts, (
        f"a skip must not arrive as an error or a failure: {counts}"
    )
    assert "a local Docker daemon is absent" in child.stdout, (
        f"the skip has to name the toolchain that is missing, got:\n{child.stdout}"
    )
