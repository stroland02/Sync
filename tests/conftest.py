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

import os
import subprocess
import warnings
from pathlib import Path
from typing import Callable

import pytest

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

DEFAULT_DSN = "postgresql://sync:sync@localhost:5433/sync"
ADMIN_DBNAME = "postgres"

_created_dbname: str | None = None
_admin_dsn: str | None = None


def dsn_for(dbname: str, template: str) -> str:
    return make_conninfo(**{**conninfo_to_dict(template), "dbname": dbname})


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
    dbname = database_for(pinned, os.environ.get("PYTEST_XDIST_WORKER"), os.getpid())
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
