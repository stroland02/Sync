"""Give each test run its own Postgres database.

Every fixture that touches Postgres truncates the graph tables, so two runs
against one database delete each other's rows. The failures land wherever one
run happens to read between another run's TRUNCATE and its INSERT, which makes
them look like flakes in whatever code that test covers rather than what they
are. Reproduced deliberately: this suite and `test_vendor_change_detector.py`
run concurrently against one database fail 5 and 3 tests respectively, in
tests that predate the change being blamed.

`SYNC_DSN` set explicitly always wins. CI pins a database, and an operator
debugging a specific one needs the same escape hatch; only an unset variable
gets a per-run database. The name carries the pid, which is unique among the
processes that could collide, and is dropped WITH (FORCE) because `GraphStore`
holds its connection open for the life of the store.

`pytest_configure` rather than a fixture: test modules resolve `SYNC_DSN` at
import time, and collection imports them after this hook runs. A
session-scoped fixture would be too late, and none of those modules has to
change.
"""

from __future__ import annotations

import os
import warnings

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

DEFAULT_DSN = "postgresql://sync:sync@localhost:5433/sync"
ADMIN_DBNAME = "postgres"

_created_dbname: str | None = None
_admin_dsn: str | None = None


def _dsn_for(dbname: str) -> str:
    return make_conninfo(**{**conninfo_to_dict(DEFAULT_DSN), "dbname": dbname})


def pytest_configure(config) -> None:
    global _created_dbname, _admin_dsn

    if os.environ.get("SYNC_DSN"):
        return

    dbname = f"sync_test_{os.getpid()}"
    admin_dsn = _dsn_for(ADMIN_DBNAME)
    try:
        conn = psycopg.connect(admin_dsn, autocommit=True)
    except psycopg.OperationalError as exc:
        # No server: the tests that need one were going to fail anyway, and the
        # ones that do not still run. Leaving SYNC_DSN unset keeps that exactly
        # as it was before this file existed.
        warnings.warn(f"no Postgres at {DEFAULT_DSN}, tests run unisolated: {exc}", stacklevel=1)
        return

    with conn:
        # A run killed hard enough to skip the finalizer leaves its database
        # behind, and pids are reused. Dropping first cannot disturb a live run,
        # since no two live processes share a pid.
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(dbname)))
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))

    _created_dbname, _admin_dsn = dbname, admin_dsn
    os.environ["SYNC_DSN"] = _dsn_for(dbname)


def pytest_unconfigure(config) -> None:
    global _created_dbname

    if _created_dbname is None:
        return

    with psycopg.connect(_admin_dsn, autocommit=True) as conn:
        conn.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(_created_dbname))
        )
    _created_dbname = None
