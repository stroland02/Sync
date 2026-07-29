"""What happens when `apply_schema` meets a database that already exists.

Every other test in this suite starts from a database `conftest` created moments earlier, so
every schema it sees was built in one pass from the current file. That is the case that works,
and it is the reason two columns shipped that a live database never gained: `call_site.loop_depth`
when loop context landed, and `finding.claim` hours ago. `schema.sql` is `CREATE TABLE IF NOT
EXISTS` throughout, so against a database that already has the table the whole statement is
skipped and the new column never appears. Nothing reports a difference. The failure arrives later
as an insert naming a column that is not there, in whatever stage happens to run first, with a
message about a column rather than about a missing migration.

So the fixture here deliberately ages a database rather than asking for a fresh one, and the
assertions are writes rather than catalogue queries -- an insert is the operation that actually
broke.
"""

from __future__ import annotations

import os
from pathlib import Path

import psycopg
import pytest

import sync.graph
from sync.core import CallSite, Finding
from sync.graph.store import (
    GraphStore,
    _column_definitions,
    _statements,
    _table_name,
)

from conftest import ADMIN_DBNAME, dsn_for

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")


@pytest.fixture()
def aged_dsn():
    """A database of this run's own, so aging it cannot disturb the shared one.

    `conftest` gives the run one database and every other test shares it. Dropping columns out
    of that one would leave a broken schema behind for whatever ran next, and the failures would
    land in tests that have nothing to do with this file.
    """
    name = f"{psycopg.conninfo.conninfo_to_dict(DSN)['dbname']}_aged"
    admin = dsn_for(ADMIN_DBNAME, DSN)
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        conn.execute(f'CREATE DATABASE "{name}"')
    try:
        yield dsn_for(name, DSN)
    finally:
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


def _age(dsn: str, *drops: tuple[str, str]) -> None:
    """Put a database back to before those columns existed.

    Dropping a column leaves a table indistinguishable from one created before the column was
    declared, which is what a developer's database actually is. Building an old `schema.sql` by
    hand would test a file nobody has rather than the state everybody has.
    """
    with psycopg.connect(dsn, autocommit=True) as conn:
        for table, column in drops:
            conn.execute(f'ALTER TABLE "{table}" DROP COLUMN "{column}"')


def _columns(dsn: str) -> dict[str, set[str]]:
    with psycopg.connect(dsn, autocommit=True) as conn:
        rows = conn.execute(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = 'public'"
        ).fetchall()
    found: dict[str, set[str]] = {}
    for table, column in rows:
        found.setdefault(table, set()).add(column)
    return found


def test_a_database_that_predates_a_column_gains_it(aged_dsn):
    """The two columns this actually happened to, and the proof is a write.

    `loop_depth` and `claim` are not examples chosen to be convenient -- they are the two that
    shipped into a schema live databases never grew. The assertion is an insert naming both,
    because a catalogue query would pass against a column added with the wrong type and the
    thing that broke was a write.
    """
    GraphStore(aged_dsn).apply_schema()
    _age(aged_dsn, ("call_site", "loop_depth"), ("finding", "claim"))

    store = GraphStore(aged_dsn)
    store.apply_schema()

    site_id = store.upsert_call_site(
        CallSite(
            repo_id="r", path="src/billing.ts", line=12, col=4, vendor_id="stripe",
            operation_id="GetCharges", symbol="stripe.charges.list", args_keys=["limit"],
            response_fields_read=["data"], sdk_version="18.0.0", content_hash="h",
            loop_depth=2,
        )
    )
    store.insert_finding(
        Finding(
            detector="efficiency", claim="loop", call_site_id=site_id,
            severity="info", rationale="called 40 times in one unit of work",
        )
    )

    assert store.get_call_site(site_id).loop_depth == 2
    assert [f.claim for f in store.open_findings()] == ["loop"]


def test_every_column_the_schema_declares_survives_being_missing(aged_dsn):
    """The general form, so a third column cannot ship the way the first two did.

    The test above names two columns and would keep passing while a column added next week did
    not converge. This one drops everything Postgres will let go of -- which is every column
    that could have been added after its table -- and requires the schema back in full.

    A column Postgres refuses to drop is one a key or a foreign key depends on, so it existed
    when the table was created and is not the case this file is about. Those are counted rather
    than passed over in silence: a run that dropped almost nothing would prove almost nothing.
    """
    GraphStore(aged_dsn).apply_schema()
    expected = _columns(aged_dsn)

    dropped = 0
    with psycopg.connect(aged_dsn, autocommit=True) as conn:
        for table, columns in expected.items():
            for column in sorted(columns):
                try:
                    conn.execute(f'ALTER TABLE "{table}" DROP COLUMN "{column}"')
                except psycopg.errors.Error:
                    continue
                dropped += 1

    # 90 columns are declared today and all 90 drop cleanly. The floor is well under that so a
    # schema change does not fail this test for the wrong reason, and well over zero so a run
    # that dropped almost nothing cannot report convergence it never tested.
    assert dropped >= 80, f"only {dropped} columns were droppable; this proves too little"

    GraphStore(aged_dsn).apply_schema()

    assert _columns(aged_dsn) == expected


def test_truncate_all_reaches_every_table_the_schema_declares(aged_dsn):
    """The same blind spot, one method over, and it is a list somebody maintains by hand.

    `truncate_all` names its tables. That list is right today -- checked, all six -- but nothing
    holds it to the schema, so a table added later is missed exactly the way a column added
    later was. The consequence is quieter and worse than a failed insert: rows from one test
    survive into the next and the failure surfaces somewhere unrelated.
    """
    store = GraphStore(aged_dsn)
    store.apply_schema()
    tables = sorted(_columns(aged_dsn))

    with psycopg.connect(aged_dsn, autocommit=True) as conn:
        for table in tables:
            _insert_a_row(conn, table)
        before = {t: _count(conn, t) for t in tables}
        assert before == dict.fromkeys(tables, 1), "every table must hold a row to be emptied of"

        store.truncate_all()

        assert {t: _count(conn, t) for t in tables} == dict.fromkeys(tables, 0)


def test_the_schema_contains_no_semicolon_a_naive_split_would_break_on():
    """`_statements` splits on semicolons, which is right for this file and not for SQL.

    A semicolon inside a string literal or a parenthesised body would cut a statement in half,
    and the resulting syntax error would be blamed on whatever line it landed near. The limit is
    documented on `_statements`; this is what keeps the documentation true.
    """
    ddl = (Path(sync.graph.__file__).parent / "schema.sql").read_text(encoding="utf-8")

    depth = 0
    quoted = False
    for line in ddl.splitlines():
        index = 0
        while index < len(line):
            character = line[index]
            if character == "'":
                quoted = not quoted
            elif not quoted and line[index : index + 2] == "--":
                break
            elif quoted and character == ";":
                raise AssertionError(
                    "a semicolon inside a string literal would split one statement into two"
                )
            elif quoted and line[index : index + 2] == "--":
                raise AssertionError(
                    "a comment marker inside a string literal would truncate the statement"
                )
            elif character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
            elif character == ";":
                assert depth == 0, "a semicolon inside brackets would break the statement split"
            index += 1
    assert not quoted, "an unclosed string literal would make the split unpredictable"


def test_a_column_definition_carrying_brackets_is_not_cut_in_half():
    """The split that a plain `split(",")` gets wrong, pinned against the two shapes here.

    `finding.call_site_id` carries `REFERENCES call_site (id) ON DELETE CASCADE` and
    `call_site.indexed_at` carries `DEFAULT now()`. Both contain brackets, and a naive split
    would emit `REFERENCES call_site (id) ON DELETE CASCADE` as though it were a column named
    `REFERENCES` -- which Postgres would then be asked to add.
    """
    finding = _create_statement("finding")
    definitions = _column_definitions(finding)

    assert [d.split()[0] for d in definitions] == [
        "id", "detector", "claim", "call_site_id", "vendor_change_id",
        "severity", "rationale", "status", "created_at",
    ]
    assert (
        "call_site_id TEXT NOT NULL REFERENCES call_site (id) ON DELETE CASCADE" in definitions
    )


def test_a_table_level_constraint_is_not_mistaken_for_a_column():
    """`migration_outcome` ends with `UNIQUE (finding_id, attempt_index)`.

    Read as a column it becomes `ALTER TABLE migration_outcome ADD COLUMN IF NOT EXISTS UNIQUE
    ...`, which is a syntax error at every startup rather than a silent wrong answer -- but only
    because Postgres happens to reject it. The filter is what makes that not depend on luck.
    """
    definitions = _column_definitions(_create_statement("migration_outcome"))

    assert not any(d.upper().startswith("UNIQUE") for d in definitions)
    assert definitions[-1].split()[0] == "created_at"


def _create_statement(table: str) -> str:
    ddl = (Path(sync.graph.__file__).parent / "schema.sql").read_text(encoding="utf-8")
    for statement in _statements(ddl):
        if statement.upper().startswith("CREATE TABLE") and _table_name(statement) == table:
            return statement
    raise AssertionError(f"no CREATE TABLE for {table}")


def _count(conn, table: str) -> int:
    return conn.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]


# A value Postgres will accept for each type this schema uses, so a row can be put in any table
# without this file restating what every column means.
_FILLER = {
    "text": "'x'",
    "integer": "0",
    "bigint": "0",
    "boolean": "false",
    "jsonb": "'{}'::jsonb",
    "ARRAY": "'{}'",
    "timestamp with time zone": "now()",
}


def _insert_a_row(conn, table: str) -> None:
    """One row in `table`, supplying only what the schema insists on.

    Columns with a default or a nullable declaration are left alone: what this test needs is a
    row, not a meaningful one, and naming fewer columns keeps it working when the schema gains
    another.
    """
    required = conn.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = %s "
        "AND is_nullable = 'NO' AND column_default IS NULL",
        (table,),
    ).fetchall()
    if not required:
        conn.execute(f'INSERT INTO "{table}" DEFAULT VALUES')
        return
    names = ", ".join(f'"{name}"' for name, _ in required)
    values = ", ".join(_FILLER[data_type] for _, data_type in required)
    conn.execute(f'INSERT INTO "{table}" ({names}) VALUES ({values})')
