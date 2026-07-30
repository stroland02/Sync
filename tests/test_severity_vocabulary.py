"""What Postgres accepts in a severity column, what the model refuses, and where the gap is closed.

`docs/superpowers/reports/2026-07-30-mcp-tool-surface-declines.md` recorded the gap: *a row
Postgres stores is one the model refuses.* `Severity` is a five-member `Literal`; `severity` is
`TEXT NOT NULL` at two places in `schema.sql` and `change_severity` at a third, none of them with
a CHECK. So the database will hold a value no build of this code can read back.

This file pins that against a real server rather than against the `Literal`, because a test
asserting on a Python type has proved nothing about what Postgres accepts. It also pins the two
facts that decide what the fix is and where it goes:

**The store already tells the two cases apart.** `get_vendor_change` raises `KeyError` for a row
that is absent and `pydantic_core.ValidationError` for a row that exists and does not validate.
Neither is a subclass of the other -- `KeyError` is a `LookupError` and not a `ValueError`,
`ValidationError` is a `ValueError` and not a `LookupError`. The place the two become one answer
is `sync.mcp.tools`, whose `_change_for` catches `(KeyError, LookupError, ValueError)`; nothing in
`sync.graph` has to move for that catch to be narrowed.

**No CHECK is declared, and that is the schema's convention rather than an omission.** Ten model
fields are closed `Literal`s and nine of them are columns; not one is constrained in DDL, and four
of the nine name their vocabulary in a comment instead. `schema.sql` carries the argument on
`vendor_change`. What this file adds is the measurement behind it: a CHECK written into a column
definition never reaches a database that already has the column, so the constraint would be
present exactly where every write is already validated and absent exactly where a hand-written row
could appear.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import get_args

import psycopg
import pytest

from sync.core import CallSite, Finding, MigrationOutcome, VendorChange
from sync.core.models import Severity
from sync.graph.store import GraphStore

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")

ROWS = json.loads(
    (Path(__file__).parent / "fixtures" / "graph" / "vendor_change_rows.json").read_text(
        encoding="utf-8"
    )
)
"""The same fixture `test_mcp_tool_declines.py` reads, which is the point.

That file drives the rows through a fake reader with no database. This one writes them to Postgres
with raw SQL. One fixture behind both keeps `off-literal-severity` a single value: if `Severity`
ever gains `catastrophic`, both files stop testing what they claim on the same commit rather than
one of them retiring its coverage quietly.
"""

OFF_LITERAL = ROWS["off-literal-severity"]["severity"]

# The three columns, and the model field each is read back through. Written out because the
# schema-to-model mapping is not derivable from either side, and a fourth severity column added
# later should be added here by whoever adds it.
SEVERITY_COLUMNS = (
    ("vendor_change", "severity", VendorChange, "severity"),
    ("finding", "severity", Finding, "severity"),
    ("migration_outcome", "change_severity", MigrationOutcome, "change_severity"),
)


@pytest.fixture()
def store():
    """Truncated before *and* after, because this file writes rows nothing can read.

    Every other fixture in the suite truncates on the way in. That is enough for a valid row and
    not enough for these: a row with an off-vocabulary severity left behind makes
    `all_vendor_changes` and `open_findings` raise for whatever runs next in this worker, and the
    failure lands in a test that has nothing to do with this file.
    """
    s = GraphStore(DSN)
    s.apply_schema()
    s.truncate_all()
    yield s
    s.truncate_all()


def _site(store: GraphStore) -> str:
    return store.upsert_call_site(
        CallSite(
            repo_id="r", path="src/billing.ts", line=12, col=4, vendor_id="stripe",
            operation_id="PostCharges", symbol="stripe.charges.create",
            args_keys=["amount"], response_fields_read=["status"],
            sdk_version="18.0.0", content_hash="h",
        )
    )


def _write_off_literal_change(store: GraphStore, change_id: str = "vc-off-literal") -> str:
    """The fixture row, written the only way it can be written: raw SQL.

    `upsert_vendor_change` takes a `VendorChange`, so it cannot produce this row -- which is the
    finding, not a limitation of the test. This is a restore from a dump or a hand-applied repair,
    standing in for the routes enumerated in
    `docs/superpowers/reports/2026-07-30-a-row-the-model-refuses.md`.
    """
    row = ROWS["off-literal-severity"]
    store._connect().execute(
        """
        INSERT INTO vendor_change (id, vendor_id, from_version, to_version, kind,
                                   operation_id, path_ptr, severity, source, raw)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            change_id, row["vendor_id"], row["from_version"], row["to_version"], row["kind"],
            row["operation_id"], row["path_ptr"], row["severity"], row["source"],
            json.dumps(row["raw"]),
        ),
    )
    return change_id


def _write_off_literal_finding(store: GraphStore, site_id: str) -> None:
    store._connect().execute(
        """
        INSERT INTO finding (id, detector, claim, call_site_id, severity, rationale, status,
                             binding_rung)
        VALUES ('f-off-literal', 'vendor_change', 'response-field', %s, %s, 'r', 'open', 'static')
        """,
        (site_id, OFF_LITERAL),
    )


def _write_off_literal_outcome(store: GraphStore) -> None:
    store._connect().execute(
        """
        INSERT INTO migration_outcome (finding_id, attempt_index, vendor_id, from_version,
                                       to_version, change_kind, change_severity, language,
                                       symbol_shape, arg_arity, response_fields_touched_count,
                                       strategy, tier, wall_ms)
        VALUES ('f-off-literal', 0, 'stripe', 'v1', 'v2', 'response-property-removed', %s,
                'typescript', 'client.resource.method', 1, 1, 'agent', 0, 1)
        """,
        (OFF_LITERAL,),
    )


# --- what the database accepts -------------------------------------------------------


def test_postgres_stores_a_severity_the_model_refuses_in_all_three_columns(store):
    """The gap, measured against the server rather than read off the DDL.

    All three columns, because a CHECK on one of them would leave the other two exactly as they
    are and the failure they produce is identical.
    """
    site_id = _site(store)
    _write_off_literal_change(store)
    _write_off_literal_finding(store, site_id)
    _write_off_literal_outcome(store)

    stored = {
        table: store._connect().execute(
            f'SELECT "{column}" AS value FROM "{table}" LIMIT 1'
        ).fetchone()["value"]
        for table, column, _, _ in SEVERITY_COLUMNS
    }

    assert stored == dict.fromkeys(("vendor_change", "finding", "migration_outcome"), OFF_LITERAL)
    assert OFF_LITERAL not in get_args(Severity), (
        f"{OFF_LITERAL!r} has to be a value the model refuses for this test to mean anything"
    )


# A complete, valid set of arguments for each model, so the severity is the only thing under test.
# Without the valid construction beside the invalid one the refusal below would also be produced by
# a missing required field, and the test could not fail.
_VALID_ARGUMENTS = {
    VendorChange: dict(
        vendor_id="stripe", from_version="v1", to_version="v2",
        kind="response-property-removed", operation_id="PostCharges", path_ptr="/v1/charges",
        source="oasdiff",
    ),
    Finding: dict(
        detector="vendor_change", claim="response-field", call_site_id="cs1", rationale="r",
        binding_rung="static",
    ),
    MigrationOutcome: dict(
        finding_id="f", attempt_index=0, vendor_id="stripe", from_version="v1", to_version="v2",
        change_kind="response-property-removed", language="typescript",
        symbol_shape="client.resource.method", arg_arity=1, response_fields_touched_count=1,
        strategy="agent", tier=0, routing_row="row-1", wall_ms=1,
    ),
}


def test_the_model_refuses_the_value_the_database_accepted():
    """The other half of the same sentence, at the write.

    All three store methods take one of these models, so the production write path cannot produce
    the row the test above wrote. That is what makes the enumeration of write routes a short list.

    The valid construction is asserted first and it is not decoration: every one of these models has
    required fields, so an invalid-severity refusal on its own would also be produced by a keyword
    that was left out, and the test would pass however wide the field's type became.
    """
    for cls, field in ((VendorChange, "severity"), (Finding, "severity"),
                       (MigrationOutcome, "change_severity")):
        arguments = _VALID_ARGUMENTS[cls]

        accepted = cls(**arguments, **{field: "breaking"})
        with pytest.raises(ValueError, match=field):
            cls(**arguments, **{field: OFF_LITERAL})

        assert getattr(accepted, field) == "breaking"


# --- what the read does with it -------------------------------------------------------


def test_no_read_answers_for_a_row_it_cannot_parse(store):
    """Every read raises. None of them returns a partial answer or a null-filled one.

    Worth pinning because the report this file follows describes the failure as silent, and the
    silence is not here: `sync.graph` raises on all four paths, and `sync.mcp.tools` is what turns
    one of them into an empty answer. A future change that made a read here return a
    partially-populated model would make the tool's decline correct and unfixable.
    """
    site_id = _site(store)
    change_id = _write_off_literal_change(store)
    _write_off_literal_finding(store, site_id)
    _write_off_literal_outcome(store)

    reads = {
        "get_vendor_change": lambda: store.get_vendor_change(change_id),
        "all_vendor_changes": lambda: store.all_vendor_changes("stripe"),
        "open_findings": store.open_findings,
        "migration_outcomes": store.migration_outcomes,
    }

    answered = []
    for label, read in reads.items():
        try:
            read()
        except ValueError:
            continue
        answered.append(label)

    assert answered == []


def test_the_store_already_tells_an_absent_row_from_one_it_cannot_read(store):
    """The two cases are separate exception types, and the types are disjoint.

    This is why option 2 needs nothing from `sync.graph`. `sync.mcp.tools._change_for` catches
    `(KeyError, LookupError, ValueError)`, which spans both, and narrowing it to `LookupError`
    keeps the dangling-reference decline its own docstring argues for while letting a genuine
    fault escape to `_call`, which reports `isError` with the exception type. No new response
    field, no movement in `tests/golden/tool_schemas.json`.
    """
    change_id = _write_off_literal_change(store)

    with pytest.raises(KeyError) as absent:
        store.get_vendor_change("no-such-change")
    with pytest.raises(ValueError) as unreadable:
        store.get_vendor_change(change_id)

    assert isinstance(absent.value, LookupError)
    assert not isinstance(absent.value, ValueError)
    assert isinstance(unreadable.value, ValueError)
    assert not isinstance(unreadable.value, LookupError)


# --- what the vocabulary is, and that it is one vocabulary ---------------------------


def test_the_three_columns_are_typed_by_one_alias(store):
    """Established from the model rather than by reading the five values off three declarations.

    A CHECK on a column whose domain was guessed is worse than none, so the question "do all three
    hold the same vocabulary" is answered by identity: the annotation on each field *is* `Severity`,
    not merely equal to it. Retyping one of them -- widening `change_severity` for a corpus that
    grades differently, say -- fails here rather than being discovered by a rejected row.
    """
    annotations = {
        f"{table}.{column}": cls.model_fields[field].annotation
        for table, column, cls, field in SEVERITY_COLUMNS
    }

    assert set(annotations) == {
        "vendor_change.severity", "finding.severity", "migration_outcome.change_severity"
    }
    for name, annotation in annotations.items():
        assert annotation is Severity, f"{name} is not typed by the shared alias"


def test_the_vocabulary_is_exactly_these_five_members():
    """Pinned literally, so a change in either direction turns a test red beside its consequence.

    Widening is cheap today and the comment on `Severity` says why: nothing enumerates it on a
    frozen surface. Narrowing is not cheap and nothing else would notice -- retiring `warning`
    makes every stored `warning` row unreadable, and there is no such row in any database on this
    container to fail on. `sync.core` is a published contract, so this pin lives beside the
    persistence consequence rather than on the model.
    """
    assert get_args(Severity) == ("breaking", "warning", "deprecation", "addition", "info")


@pytest.mark.parametrize("member", get_args(Severity))
def test_every_member_of_the_vocabulary_survives_a_round_trip_through_all_three_columns(
    store, member
):
    """Without this, a CHECK that rejected everything would pass the test above it.

    Each write varies the field its natural key is built from -- `kind` for a change, `claim` for a
    finding, `attempt_index` for an attempt -- because severity is in none of the three keys, and
    five members sharing one key would converge on one row whose severity was whichever arrived
    first.
    """
    site_id = _site(store)
    change_id = store.upsert_vendor_change(
        VendorChange(
            vendor_id="stripe", from_version="v1", to_version="v2", kind=f"kind-{member}",
            operation_id="PostCharges", path_ptr="/v1/charges", severity=member,
            source="oasdiff", raw={"text": f"a {member} change"},
        )
    )
    store.insert_finding(
        Finding(
            detector="vendor_change", claim=f"claim-{member}", call_site_id=site_id,
            vendor_change_id=change_id, severity=member, rationale="r", binding_rung="static",
        )
    )
    store.record_migration_outcome(
        MigrationOutcome(
            finding_id="f", attempt_index=get_args(Severity).index(member),
            vendor_id="stripe", from_version="v1", to_version="v2",
            change_kind="response-property-removed", change_severity=member,
            language="typescript", symbol_shape="client.resource.method", arg_arity=1,
            response_fields_touched_count=1, strategy="agent", tier=0, routing_row="row-1",
            wall_ms=1,
        )
    )

    assert store.get_vendor_change(change_id).severity == member
    assert [f.severity for f in store.open_findings()] == [member]
    assert [o.change_severity for o in store.migration_outcomes()] == [member]


# --- why there is no CHECK ------------------------------------------------------------


def test_no_check_constraint_stands_over_a_severity_column(store):
    """The decision this task took, pinned where the next person will trip on it.

    Not caution: a CHECK here would be the first DDL enumeration of a model vocabulary in this
    schema, and the schema's convention across nine closed-vocabulary columns is a comment. The
    argument is in `schema.sql` above `vendor_change` and in
    `docs/superpowers/reports/2026-07-30-a-row-the-model-refuses.md`. Read it before deleting this
    test; adding the constraint is a decision about coupling `schema.sql` to `sync.core`, not a
    hardening with no cost.

    Scoped to the severity columns rather than to the whole schema, because a CHECK added for an
    unrelated reason -- a non-negative `arg_arity` -- is not this decision being reversed.
    """
    rows = store._connect().execute(
        """
        SELECT c.conrelid::regclass::text AS relation,
               pg_get_constraintdef(c.oid)  AS definition,
               a.attname                    AS column_name
          FROM pg_constraint c
          JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
         WHERE c.contype = 'c' AND c.connamespace = 'public'::regnamespace
        """
    ).fetchall()

    over_severity = [
        (row["relation"], row["column_name"], row["definition"])
        for row in rows
        if (row["relation"], row["column_name"])
        in {(table, column) for table, column, _, _ in SEVERITY_COLUMNS}
    ]

    assert over_severity == []


def test_a_check_in_a_column_definition_never_reaches_a_database_that_has_the_column(store):
    """The measurement that decided it, run against the server rather than reasoned about.

    `apply_schema` converges an existing database by re-issuing every column definition as
    `ADD COLUMN IF NOT EXISTS`, and its own docstring says it "cannot rename a column, change a
    type, add or drop a constraint". This is what that costs a CHECK specifically: on a table that
    already has the column, the whole `ADD COLUMN` item is skipped and any constraint riding on the
    definition is skipped with it. So a CHECK written into `schema.sql` would be present on every
    database created afterwards -- where every write already goes through the model -- and absent
    from every database that predates it, which is where a hand-written row could be.

    Absent *and believed present* is the part that makes it worse than nothing.
    """
    connection = store._connect()
    connection.execute("DROP TABLE IF EXISTS severity_check_probe")
    connection.execute("CREATE TABLE severity_check_probe (severity TEXT NOT NULL)")
    try:
        connection.execute(
            "ALTER TABLE severity_check_probe ADD COLUMN IF NOT EXISTS severity TEXT NOT NULL "
            f"CHECK (severity IN ({', '.join(repr(m) for m in get_args(Severity))}))"
        )

        checks = connection.execute(
            "SELECT count(*) AS n FROM pg_constraint "
            "WHERE conrelid = 'severity_check_probe'::regclass AND contype = 'c'"
        ).fetchone()["n"]
        connection.execute(
            "INSERT INTO severity_check_probe (severity) VALUES (%s)", (OFF_LITERAL,)
        )

        assert checks == 0
        assert connection.execute(
            "SELECT severity FROM severity_check_probe"
        ).fetchone()["severity"] == OFF_LITERAL
    finally:
        connection.execute("DROP TABLE IF EXISTS severity_check_probe")


def test_apply_schema_converges_over_a_database_holding_a_row_the_model_refuses(store):
    """Idempotence, asserted where the brief asks: against rows that are already there.

    `apply_schema` runs against long-lived databases -- 216 on this container -- so a schema change
    that fails against a violating row fails at startup for whoever holds one. It does not, today,
    and this is what would have to keep being true of any constraint added later: adding a CHECK by
    plain `ALTER TABLE` to a table holding such a row is refused with SQLSTATE 23514, which is why
    the pattern would have to be `NOT VALID` -- the same shape as `binding_rung`'s `unattributed`
    default, tolerating history rather than backfilling it.
    """
    site_id = _site(store)
    change_id = _write_off_literal_change(store)
    _write_off_literal_finding(store, site_id)
    _write_off_literal_outcome(store)

    columns_before = _columns(store)
    store.apply_schema()
    store.apply_schema()

    assert _columns(store) == columns_before
    assert store._connect().execute(
        "SELECT severity FROM vendor_change WHERE id = %s", (change_id,)
    ).fetchone()["severity"] == OFF_LITERAL
    assert [
        store._connect().execute(f'SELECT count(*) AS n FROM "{table}"').fetchone()["n"]
        for table, _, _, _ in SEVERITY_COLUMNS
    ] == [1, 1, 1]


def _columns(store: GraphStore) -> set[tuple[str, str]]:
    return {
        (row["table_name"], row["column_name"])
        for row in store._connect().execute(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = 'public'"
        ).fetchall()
    }


# --- why the write routes are a short list -------------------------------------------


_SQL_WRITE = re.compile(
    r"\b(?:INSERT\s+INTO|UPDATE)\s+(vendor_change|finding|migration_outcome)\b", re.IGNORECASE
)


def test_the_store_is_the_only_module_that_writes_a_severity_column():
    """The enumeration of write routes, made executable.

    "Every production write goes through a validated model" rests on there being one module that
    issues SQL against these tables, and on each of its three inserts taking a model. The first
    half is checkable and this checks it; the second is what `test_the_model_refuses_the_value_the
    _database_accepted` covers. A sixth detector or a second ingest that reached for raw SQL would
    reopen the route without anybody noticing, which is how `insert_finding`'s rung check came to
    be needed.
    """
    root = Path(__file__).resolve().parents[1] / "src"
    writers = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*.py")
        if _SQL_WRITE.search(path.read_text(encoding="utf-8"))
    }

    assert writers == {"sync/graph/store.py"}
