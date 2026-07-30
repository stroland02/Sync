"""Does the handler in `sweep_leaked_databases` catch it under pytest-cov? Scratch."""

from __future__ import annotations

import psycopg
from conftest import sweep_leaked_databases

DSN = "postgresql://sync:sync@localhost:1/postgres"


def test_what_the_handler_does():
    try:
        result = sweep_leaked_databases(DSN)
    except BaseException as exc:
        import tests.conftest as conftest

        print(
            f"ESCAPED {type(exc).__module__}.{type(exc).__qualname__}"
            f" isinstance(psycopg.Error)={isinstance(exc, psycopg.Error)}"
            f" same-psycopg={conftest.psycopg is psycopg}"
            f" Error-is={conftest.psycopg.Error is psycopg.Error}"
            f" mro={[c.__qualname__ for c in type(exc).__mro__]}"
        )
        raise
    else:
        print(f"CAUGHT, returned {result}")
