"""Which `Error` class is in the raised exception's MRO? Scratch."""

from __future__ import annotations

import sys

import psycopg
import psycopg.errors

DSN = "postgresql://sync:sync@localhost:1/postgres"


def test_identity():
    try:
        with psycopg.connect(DSN, autocommit=True, connect_timeout=10):
            pass
    except BaseException as exc:
        mro_error = next(c for c in type(exc).__mro__ if c.__qualname__ == "Error")
        print(
            f"raised={type(exc).__module__}.{type(exc).__qualname__}@{id(type(exc))}"
            f" attr=psycopg.errors.ConnectionTimeout@{id(psycopg.errors.ConnectionTimeout)}"
            f" same_class={type(exc) is psycopg.errors.ConnectionTimeout}"
            f" mro_Error@{id(mro_error)} from {mro_error.__module__}"
            f" psycopg.Error@{id(psycopg.Error)}"
            f" is_same_Error={mro_error is psycopg.Error}"
            f" isinstance={isinstance(exc, psycopg.Error)}"
            f" modules={sorted(m for m in sys.modules if 'psycopg' in m)}"
        )
    else:
        raise AssertionError("connected, unexpected")
