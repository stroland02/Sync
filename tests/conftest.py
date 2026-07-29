"""Give each test run its own Postgres database.

Every fixture that touches Postgres truncates the graph tables, so two runs
against one database delete each other's rows. The failures land wherever one
run happens to read between another run's TRUNCATE and its INSERT, which makes
them look like flakes in whatever code that test covers rather than what they
are. Reproduced deliberately: this suite and `test_vendor_change_detector.py`
run concurrently against one database fail 5 and 3 tests respectively, in
tests that predate the change being blamed.

`SYNC_DSN` set explicitly wins for a serial run. CI pins a database, and an
operator debugging a specific one needs the same escape hatch; only an unset
variable gets a per-run database. The name carries the pid, which is unique
among the processes that could collide, and is dropped WITH (FORCE) because
`GraphStore` holds its connection open for the life of the store.

Under `pytest-xdist` a pin cannot be honoured as given: every worker is a
separate process, they would all resolve it to the same database, and the
TRUNCATE two of them issue at once deadlocks. So a worker subdivides whatever
it was pinned to rather than ignoring it -- `sync_b5` becomes `sync_b5_gw0`,
and an operator still knows which server and which run to look at.

`pytest_configure` rather than a fixture: test modules resolve `SYNC_DSN` at
import time, and collection imports them after this hook runs -- in the worker
process, under xdist, which is why the per-worker name has to be decided here
too. A session-scoped fixture would be too late, and none of those modules has
to change.
"""

from __future__ import annotations

import ctypes
import os
import re
import subprocess
import warnings
from pathlib import Path
from typing import Callable, Iterable

import pytest

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

DEFAULT_DSN = "postgresql://sync:sync@localhost:5433/sync"
ADMIN_DBNAME = "postgres"

LEAKED_DATABASE_PATTERN = r"sync\_test\_%"
"""The SQL `LIKE` pattern for databases this file creates, and nothing else.

The underscores are escaped because `_` is a single-character wildcard in `LIKE`; unescaped, the
pattern would also match `syncXtestY...`. That is cosmetic here and the substantive point is the
prefix.

**It must never be `sync%`.** That matches the primary `sync` database, which `POSTGRES_DB`
creates and `DEFAULT_DSN` points at, and it matches every pinned development database on the
server -- `sync_b14` and `sync_w50` are deliberate pins somebody is working in. Sweeping by that
pattern took Postgres down for fourteen seconds and killed a run that was gating a merge.
`sync\\_test\\_%` reaches `sync_test_<pid>`, `sync_test_<pid>_<worker>` and the suffixed variants
fixtures derive from those, which is exactly the set this file is responsible for.
"""

_LEAKED_NAME = re.compile(r"^sync_test_(\d+)(?:_.+)?$")
"""The same set as a regex, for reading the pid back out of a name.

Two spellings of one rule is a duplication worth naming: the `LIKE` form is what the server can
filter on, and only Python can parse the pid. `test_the_primary_database_is_never_matched_by_the
_pattern` holds the SQL half and `test_a_pinned_development_database_is_not_matched` holds this
one, so neither drifts on its own.
"""

_created_dbname: str | None = None
_admin_dsn: str | None = None


def dsn_for(dbname: str, template: str) -> str:
    return make_conninfo(**{**conninfo_to_dict(template), "dbname": dbname})


def pid_is_running(pid: int) -> bool:
    """Whether a process with this pid exists.

    The liveness test the sweep rests on, and it is the pid already in the database's name rather
    than a connection check -- a leaked database has no connections either way, so counting them
    cannot tell a dead run's database from a live run's idle one.

    **`os.kill(pid, 0)` is the portable idiom and it does not answer this question on Windows.**
    Measured on Python 3.12 here: against the pid of a process that has already exited it returns
    without raising, because a handle to the finished process keeps the process object alive, and
    it raises `OSError` only for a pid outside the valid range. So it reports "plausible pid"
    where the sweep needs "something is running", and a sweep built on it would spare nothing.
    `GetExitCodeProcess` is the answer that distinguishes them.

    Unsure resolves to alive, everywhere. A wrong `True` costs one leaked database surviving until
    the next run; a wrong `False` drops a database out from under a suite that is using it.
    """
    if pid <= 0:
        return True
    if os.name == "nt":
        return _windows_pid_is_running(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        # Permission denied, or anything else this cannot interpret. The process exists as far as
        # the sweep is concerned.
        return True
    return True


_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_STILL_ACTIVE = 259
_ERROR_INVALID_PARAMETER = 87


def _windows_pid_is_running(pid: int) -> bool:
    """`OpenProcess` and then the exit code, because the handle alone is not the answer.

    A process that has exited while somebody still holds a handle to it keeps its process object,
    so `OpenProcess` succeeds for it. Only `GetExitCodeProcess` separates that from a running one.
    `STILL_ACTIVE` is also a legal exit code, so a process that exited with 259 reads as alive --
    which is the direction this errs in anyway.
    """
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ctypes.get_last_error() != _ERROR_INVALID_PARAMETER
    try:
        code = ctypes.c_ulong()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return True
        return code.value == _STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def leaked_database_names(
    candidates: Iterable[str],
    *,
    is_running: Callable[[int], bool] = pid_is_running,
    exclude: str | None = None,
) -> list[str]:
    """Which of `candidates` belong to a run that is no longer alive.

    `exclude` is the name the caller is about to create. Inside `pytest_configure` the risk of
    sweeping it is small -- this process picks its name from its own live pid -- but the guard is
    here rather than in the caller so anything reusing this function inherits it.
    """
    dead = []
    for name in candidates:
        if name == exclude:
            continue
        match = _LEAKED_NAME.match(name)
        if match is None:
            continue
        if is_running(int(match.group(1))):
            continue
        dead.append(name)
    return sorted(dead)


def sweep_leaked_databases(admin_dsn: str, *, exclude: str | None = None) -> list[str]:
    """Drop the databases killed runs left behind, and return what was dropped.

    A killed run cannot run its own finalizer, so the next run cleans up after it. This is called
    from `pytest_configure`, which is where a database is created anyway and therefore exactly
    when a leak is in the way -- no scheduler, no cron, and no separate script to remember.

    Plain `DROP DATABASE`, never `WITH (FORCE)`. Plain refuses a database that is in use and
    `FORCE` kills the connections of whatever is using it. Letting the server enforce that is
    stronger than checking first, because a snapshot of live connections is stale the moment
    another suite starts.

    **Nothing here may fail the run.** Cleanup that breaks a suite is worse than the leak it
    fixes, so every drop is attempted on its own and a refusal is skipped rather than raised. An
    unreachable server returns an empty list for the same reason `pytest_configure` warns and
    carries on when Postgres is absent.
    """
    try:
        with psycopg.connect(admin_dsn, autocommit=True, connect_timeout=10) as conn:
            candidates = [
                row[0]
                for row in conn.execute(
                    "SELECT datname FROM pg_database WHERE datname LIKE %s",
                    (LEAKED_DATABASE_PATTERN,),
                ).fetchall()
            ]
            dropped = []
            for name in leaked_database_names(candidates, exclude=exclude):
                try:
                    conn.execute(
                        sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(name))
                    )
                except psycopg.Error:
                    # In use, or dropped by another run's sweep between the query and here.
                    continue
                dropped.append(name)
            return dropped
    except psycopg.Error:
        return []


def database_for(pinned_dsn: str | None, worker: str | None, pid: int) -> str | None:
    """The database this process has to create for itself, or None to use what
    it was handed.

    `worker` is xdist's `PYTEST_XDIST_WORKER`, absent in a serial run and in the
    controller process.
    """
    own = f"sync_test_{pid}"
    if worker is None:
        return None if pinned_dsn else own
    # Not `pinned_dsn or DEFAULT_DSN`: an unpinned worker has to stay distinct
    # from the same worker id in a suite someone else launched at the same time,
    # and its own pid is the only thing here that separates them.
    return f"{conninfo_to_dict(pinned_dsn)['dbname'] if pinned_dsn else own}_{worker}"


def pytest_configure(config) -> None:
    global _created_dbname, _admin_dsn

    pinned = os.environ.get("SYNC_DSN")
    worker = os.environ.get("PYTEST_XDIST_WORKER")
    dbname = database_for(pinned, worker, os.getpid())
    if dbname is None:
        return

    template = pinned or DEFAULT_DSN
    admin_dsn = dsn_for(ADMIN_DBNAME, template)
    try:
        conn = psycopg.connect(admin_dsn, autocommit=True)
    except psycopg.OperationalError as exc:
        # No server: the tests that need one were going to fail anyway, and the
        # ones that do not still run. Leaving SYNC_DSN unset keeps that exactly
        # as it was before this file existed.
        warnings.warn(f"no Postgres at {template}, tests run unisolated: {exc}", stacklevel=1)
        return

    with conn:
        # A run killed hard enough to skip the finalizer leaves its database
        # behind, and pids are reused. Dropping first cannot disturb a live run,
        # since no two live processes share a pid -- nor a pid and a worker id.
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(dbname)))
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))

    # The same argument one line further: this run cleans up after the runs that were killed
    # before they could. Only in the controller, because a worker would repeat the whole sweep
    # once per process for nothing, and only after this process has created its own database, so
    # the name it is using exists and cannot be a candidate.
    if worker is None:
        swept = sweep_leaked_databases(admin_dsn, exclude=dbname)
        if swept:
            print(f"swept {len(swept)} leaked test database(s)")

    _created_dbname, _admin_dsn = dbname, admin_dsn
    os.environ["SYNC_DSN"] = dsn_for(dbname, template)


def pytest_unconfigure(config) -> None:
    global _created_dbname

    if _created_dbname is None:
        return

    with psycopg.connect(_admin_dsn, autocommit=True) as conn:
        conn.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(_created_dbname))
        )
    _created_dbname = None


GitRunner = Callable[[list[str], Path], None]


@pytest.fixture()
def git() -> GitRunner:
    def run(args: list[str], cwd: Path) -> None:
        subprocess.run(
            ["git", *args], cwd=cwd, check=True, capture_output=True, text=True, encoding="utf-8"
        )

    return run


@pytest.fixture()
def base_clone(tmp_path: Path, git: GitRunner) -> Path:
    """A committed project, before any patch.

    This is the shape of the M0 acceptance failure, minus the patch. Next.js
    writes `next-env.d.ts` during a build, `tsconfig.json` lists it in
    `include`, and `.gitignore` keeps it out of the repository -- so what that
    file declares exists in the tree the patch agent works in and in no checkout
    of the branch that gets pushed.

    A test that drives the graph starts here and lets the patch node apply the
    patch, because `prepare` measures its typecheck baseline against exactly
    this tree: a baseline taken from a tree that already carries the patch
    absorbs the errors the gate exists to catch.
    """
    repo = tmp_path / "clone"
    (repo / "src").mkdir(parents=True)
    (repo / ".gitignore").write_text("generated.d.ts\nnode_modules\n", encoding="utf-8")
    (repo / "tsconfig.json").write_text(
        '{"compilerOptions": {"strict": true, "noEmit": true, "target": "ES2022", "module": "ESNext",'
        ' "moduleResolution": "bundler", "skipLibCheck": true}, "include": ["src", "generated.d.ts"]}',
        encoding="utf-8",
    )
    (repo / "src" / "a.ts").write_text("export const n: number = 1;\n", encoding="utf-8")

    git(["init", "-q", "-b", "main"], repo)
    git(["add", "."], repo)
    git(["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base"], repo)
    return repo


@pytest.fixture()
def agent_edit() -> dict[str, str]:
    """What the patch agent leaves in `base_clone`: a tracked modification that
    typechecks only because of a gitignored file it also wrote.

    `push_branch` stages with `git add -u`, so `src/a.ts` reaches the branch and
    `generated.d.ts` does not. Held in one place because two fixtures apply it
    from opposite directions -- one before the test runs, one from inside the
    graph's own patch node.
    """
    return {
        "src/a.ts": "export const g: Generated = { id: 'x' };\n",
        "generated.d.ts": "declare type Generated = { id: string };\n",
    }


@pytest.fixture()
def patched_clone(base_clone: Path, agent_edit: dict[str, str]) -> Path:
    """`base_clone` with the patch already applied.

    For tests that call `static_verify` directly, which is how the graph calls
    it: after the patch node has written to the clone.
    """
    for relative, text in agent_edit.items():
        (base_clone / relative).write_text(text, encoding="utf-8")
    return base_clone
