"""Persistence and queries for the API Dependency Graph."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Collection, Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime
from importlib import resources

import psycopg
from psycopg.rows import dict_row

from sync.core import CallSite, Finding, FindingStatus, MigrationOutcome, RepoContext, VendorChange
from sync.core.models import (
    SEVERITY_ORDER,
    UNATTRIBUTED,
    ObservedCall,
    ObservedErrorWindow,
    ObservedShape,
)
from sync.graph.sources import TRAFFIC_SOURCES


def _stable_id(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:32]


# Entries in a CREATE TABLE body that declare a constraint rather than a column. Everything
# else is a column, which is what makes this list the whole of the grammar this needs to know.
_TABLE_CONSTRAINTS = frozenset(
    {"UNIQUE", "PRIMARY", "FOREIGN", "CHECK", "CONSTRAINT", "EXCLUDE", "LIKE"}
)


def _statements(ddl: str) -> list[str]:
    """`schema.sql` as separate statements, comments removed.

    Split on semicolons, and strip everything after a `--` to end of line. Both are correct for
    this file and neither is correct for SQL in general: a semicolon inside a string literal, an
    identifier or a function body would cut a statement in half, and a `--` inside a literal
    would truncate one. That is a real limit rather than an oversight, and the convergence tests
    fail if either ever appears in `schema.sql`.
    """
    without_comments = "\n".join(line.split("--", 1)[0] for line in ddl.splitlines())
    return [statement.strip() for statement in without_comments.split(";") if statement.strip()]


# The order a page of open findings arrives in. Named orderings, not column names -- see
# `open_findings_at_risk`'s docstring for why a column name must never reach this from a URL.
#
# `first-seen` is what this shipped with and is unchanged: `created_at` ascending, the order Sync
# raised the findings in. It keeps the name it earned rather than being called "default", because a
# reader has to be told which ordering they are looking at when they have chosen nothing, and
# "default" tells them nothing.
DEFAULT_FINDING_ORDER = "first-seen"
FINDING_ORDERS = (DEFAULT_FINDING_ORDER, "severity")

# `finding.created_at, finding.id` is the tiebreak on every ordering, not only the default: two
# findings of one severity need a total order or `LIMIT`/`OFFSET` pages overlap and skip rows, and
# the reader never sees the row that fell between two pages.
_TIEBREAK = "finding.created_at, finding.id"

# `array_position` over the rank rather than a `CASE` expression, so the ordering has exactly one
# copy and it is the tuple in `sync.core.models`. A severity the rank does not name yields NULL,
# which Postgres sorts last under `ASC` -- the behaviour to want: an unrankable finding at the top
# of a page opened to see the worst first is a false claim about which finding matters most.
_FINDING_ORDER_CLAUSES = {
    DEFAULT_FINDING_ORDER: (_TIEBREAK, []),
    "severity": (
        f"array_position(%s::text[], finding.severity), {_TIEBREAK}",
        [list(SEVERITY_ORDER)],
    ),
}


def _finding_order_clause(order: str) -> tuple[str, list[object]]:
    if order not in _FINDING_ORDER_CLAUSES:
        raise ValueError(
            f"unknown ordering {order!r}; must be one of {sorted(_FINDING_ORDER_CLAUSES)}"
        )
    clause, parameters = _FINDING_ORDER_CLAUSES[order]
    return clause, list(parameters)


def _common_directory(lo: str | None, hi: str | None) -> str:
    """The deepest directory two paths share, ending in `/`, or `""`.

    `lo` and `hi` are the lexicographic extremes of a set, which is enough to characterise the whole
    set's common prefix -- see `call_sites_common_directory` for why. `None` means the set was empty.

    The truncation is the load-bearing part. A common *character* prefix can stop in the middle of a
    filename, and a prefix that does is not a directory: it names nothing on disk and the remainder
    it leaves behind cannot be rejoined by a reader who wants to open the file.
    """
    if lo is None or hi is None:
        return ""
    shared = 0
    for a, b in zip(lo, hi):
        if a != b:
            break
        shared += 1
    cut = lo.rfind("/", 0, shared)
    return lo[: cut + 1] if cut >= 0 else ""


def _open_findings_predicate(
    *,
    repo_id: str | None = None,
    vendor_id: str | None = None,
    severity: str | None = None,
    path_prefix: str | None = None,
) -> tuple[str, list[object]]:
    """The `WHERE` clause every open-findings read shares, and its parameters.

    Seven reads answer questions about the same set -- open status, and a call site the code
    still has -- and each of them can now be narrowed to one repository, because repository
    scope is what every console level below Codebase inherits. One builder rather than seven
    copies of the clause: a filter added to six of them and forgotten in the seventh is a screen
    that renders a fleet-wide figure under a repository heading, which is precisely the false
    claim this scoping exists to remove.

    Every filter is a placeholder rather than interpolated text. The clause itself carries no
    caller-supplied string, so the `f`-strings that embed it are composing SQL this module wrote.
    """
    clauses = ["finding.status = 'open'", "call_site.retracted_at IS NULL"]
    parameters: list[object] = []
    if repo_id is not None:
        clauses.append("call_site.repo_id = %s")
        parameters.append(repo_id)
    if vendor_id is not None:
        clauses.append("call_site.vendor_id = %s")
        parameters.append(vendor_id)
    if severity is not None:
        clauses.append("finding.severity = %s")
        parameters.append(severity)
    if path_prefix is not None:
        # `starts_with` rather than `LIKE prefix || '%'`: the caller's string is a path, and a
        # path holding `%` or `_` is a wildcard under `LIKE` and a literal under this.
        clauses.append("starts_with(call_site.path, %s)")
        parameters.append(path_prefix)
    return " AND ".join(clauses), parameters


def _call_site_predicate(
    vendor_id: str,
    operation_id: str,
    *,
    repo_id: str | None = None,
    path_prefix: str | None = None,
) -> tuple[str, list[object]]:
    """The `WHERE` every live-call-site read on one operation shares, and its parameters.

    A sibling of `_open_findings_predicate` rather than the same builder, because the two answer
    over different relations: that one always joins `finding` and always asks for open status,
    and this one reads `call_site` alone, where a call site exists whether or not any detector
    has raised anything against it. Sharing a builder would mean either an open-findings join a
    binding surface does not want or a status clause that quietly drops every unflagged site.

    What they do share is the reason for `starts_with` over `LIKE`, and that argument is written
    once, above, rather than restated here: a path holding `_` or `%` is a wildcard under `LIKE`
    and a literal under this.

    One builder for the page, its denominator and the repository facet, for the reason
    `_open_findings_predicate` gives for its own seven readers: a filter added to two of three
    and forgotten in the third is a page and a total that disagree about which rows exist.
    """
    clauses = ["vendor_id = %s", "operation_id = %s", "retracted_at IS NULL"]
    parameters: list[object] = [vendor_id, operation_id]
    if repo_id is not None:
        clauses.append("repo_id = %s")
        parameters.append(repo_id)
    if path_prefix is not None:
        clauses.append("starts_with(path, %s)")
        parameters.append(path_prefix)
    return " AND ".join(clauses), parameters


def _table_name(create: str) -> str:
    return create[: create.index("(")].split()[-1]


def _column_definitions(create: str) -> list[str]:
    """The column declarations in one CREATE TABLE, verbatim and in order.

    Split at commas outside parentheses, because `REFERENCES call_site (id)` and
    `NOT NULL DEFAULT now()` both put commas' worth of structure inside brackets that a plain
    split would cut through.
    """
    body = create[create.index("(") + 1 : create.rindex(")")]
    entries, depth, start = [], 0, 0
    for index, character in enumerate(body):
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
        elif character == "," and depth == 0:
            entries.append(body[start:index])
            start = index + 1
    entries.append(body[start:])

    definitions = []
    for entry in entries:
        collapsed = " ".join(entry.split())
        if not collapsed or collapsed.split()[0].upper() in _TABLE_CONSTRAINTS:
            continue
        definitions.append(collapsed)
    return definitions


def _add_missing_columns(creates: list[str]) -> list[str]:
    """One `ADD COLUMN IF NOT EXISTS` per declared column, derived rather than written twice.

    This is what makes `apply_schema` converge a database that already exists. It is derived
    from the CREATE TABLE bodies on purpose: the alternative is a parallel list of ALTERs that
    somebody has to remember to extend, and forgetting is the entire defect being fixed here --
    a mechanism that needs the same discipline the bug needed is not a fix.

    The column definition is reused verbatim, so an added column arrives with the type, default
    and nullability the schema declares rather than a second opinion about them.
    """
    return [
        f"ALTER TABLE {_table_name(create)} ADD COLUMN IF NOT EXISTS {definition}"
        for create in creates
        for definition in _column_definitions(create)
    ]


def _table_unique_constraints(create: str) -> list[tuple[str, ...]]:
    """The column tuples of table-level UNIQUE constraints declared in a CREATE TABLE.

    Derived from the CREATE TABLE body so `apply_schema` can reconcile constraints on
    an existing database when a natural key is widened (such as B79 adding `is_rehearsal`
    to `migration_outcome`'s natural key, which B129 caught).
    """
    body = create[create.index("(") + 1 : create.rindex(")")]
    entries, depth, start = [], 0, 0
    for index, character in enumerate(body):
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
        elif character == "," and depth == 0:
            entries.append(body[start:index])
            start = index + 1
    entries.append(body[start:])

    uniques = []
    for entry in entries:
        collapsed = " ".join(entry.split())
        if collapsed.upper().startswith("UNIQUE"):
            inside = collapsed[collapsed.index("(") + 1 : collapsed.rindex(")")]
            cols = tuple(c.strip() for c in inside.split(",") if c.strip())
            if cols:
                uniques.append(cols)
    return uniques


def _reconcile_unique_constraints(connection: psycopg.Connection, creates: list[str]) -> None:
    """Reconcile table-level UNIQUE constraints on a database that already exists.

    `CREATE TABLE IF NOT EXISTS` leaves an existing table's constraints untouched, so a
    natural key widened in `schema.sql` (e.g. B79 adding `is_rehearsal` to `migration_outcome`)
    is never created on a database from before the change, causing ON CONFLICT upserts to fail.

    This queries `pg_constraint` for existing unique constraints on each table and compares
    them against the declarations in `creates`. If a declared UNIQUE constraint is missing,
    any superseded constraint covering a subset of those columns is dropped, and the declared
    constraint is added.
    """
    declared_by_table: dict[str, list[tuple[str, ...]]] = {}
    for create in creates:
        table = _table_name(create)
        uniques = _table_unique_constraints(create)
        if uniques:
            declared_by_table[table] = uniques

    if not declared_by_table:
        return

    rows = connection.execute(
        """
        SELECT c.relname AS table_name,
               con.conname AS constraint_name,
               ARRAY(
                   SELECT a.attname
                   FROM pg_attribute a
                   WHERE a.attrelid = con.conrelid
                     AND a.attnum = ANY(con.conkey)
                   ORDER BY array_position(con.conkey, a.attnum)
               ) AS columns
        FROM pg_constraint con
        JOIN pg_class c ON c.oid = con.conrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND con.contype = 'u'
        """
    ).fetchall()

    existing_by_table: dict[str, dict[str, tuple[str, ...]]] = {}
    for row in rows:
        existing_by_table.setdefault(row["table_name"], {})[row["constraint_name"]] = tuple(
            row["columns"]
        )

    for table, declared_uniques in declared_by_table.items():
        existing_constraints = existing_by_table.get(table, {})
        existing_tuples = set(existing_constraints.values())

        for required_cols in declared_uniques:
            if required_cols in existing_tuples:
                continue

            req_set = set(required_cols)
            for conname, existing_cols in existing_constraints.items():
                if set(existing_cols).issubset(req_set) and len(existing_cols) < len(required_cols):
                    connection.execute(f"ALTER TABLE {table} DROP CONSTRAINT {conname}")

            cols_sql = ", ".join(required_cols)
            connection.execute(f"ALTER TABLE {table} ADD UNIQUE ({cols_sql})")



class GraphStore:
    """One store instance owns one connection, opened on first use.

    A per-call connection costs a TCP handshake, an authentication round trip
    and a teardown for every row: an ingest of a few thousand vendor changes
    spends most of its time connecting. A connection that has died is replaced
    on the next call -- the database is outside this process and a connection
    dying is a condition that occurs, and the API holds one store for the
    process lifetime, so handing the dead one back forever turned one dropped
    connection into every console route failing until a restart (B117). The
    one place that must not reconnect is under an open `transaction()` block,
    and `_connect` carries why.

    A store is meant for one caller at a time. psycopg serialises statements on
    a shared connection, so concurrent callers corrupt nothing -- but they share
    a transaction as well as a connection, which is a sharper edge than it
    sounds and is spelled out on `transaction()`. Give each concurrent unit of
    work its own store.
    """

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._conn: psycopg.Connection | None = None
        self._transaction_depth = 0

    def _connect(self) -> psycopg.Connection:
        # Never reconnect under an open `transaction()` block: the block's transaction lives
        # on the dead connection, so a fresh autocommit connection here would commit each
        # later write on its own while the block rolls back -- a failed write turned into a
        # silently partial one, which is worse than the outage. Inside a block the dead
        # connection is handed back and the next statement raises OperationalError instead.
        # `closed` covers a broken connection too: psycopg marks a broken connection closed.
        if self._conn is None or (self._conn.closed and self._transaction_depth == 0):
            self._conn = psycopg.connect(self._dsn, row_factory=dict_row, autocommit=True)
        return self._conn

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Group writes so a failure part-way through leaves no partial graph.

        Outside a block every write commits on its own, which is what the
        detector and the remediation nodes want. Inside one, nothing another
        connection reads reflects the block until it returns -- including the
        TRUNCATE, so an ingest that dies half-way rolls back to the graph it
        started from rather than to an empty one.

        That guarantee is single-threaded, and the two ways it does not
        generalise are both measured rather than reasoned about:

        The block belongs to this store's connection, not to the caller that
        opened it. A write issued through the same store from another thread
        joins the block whether it means to or not, and is rolled back with it
        without raising anything. Concurrency here needs a store per unit of
        work; M1's fan-out across findings is the case that will meet this.

        A reader on another connection does not see the previous graph while an
        ingest runs. TRUNCATE takes ACCESS EXCLUSIVE, which conflicts with the
        ACCESS SHARE an ordinary SELECT takes, so the reader blocks for the
        duration of the block and then reads whatever it committed.
        """
        # Resolve the connection before raising the depth, so a block starting on a dead
        # connection gets a live one -- only calls inside the block are pinned to it.
        connection = self._connect()
        self._transaction_depth += 1
        try:
            with connection.transaction():
                yield
        finally:
            self._transaction_depth -= 1

    def apply_schema(self) -> None:
        """Bring a database to the current schema, whether or not it already has one.

        `schema.sql` is `CREATE TABLE IF NOT EXISTS` throughout, so against a database that
        already has the tables it used to be a no-op: the guard skipped the whole statement and
        a column added to the file afterwards never appeared. Two shipped that way --
        `call_site.loop_depth` and `finding.claim` -- and neither was noticed here, because
        `conftest` builds a fresh database per run and a schema built in one pass is exactly the
        case that works. The failure landed later, as an insert naming a column that was not
        there, in whichever stage happened to run first.

        So every declared column is also issued as `ADD COLUMN IF NOT EXISTS`, derived from the
        CREATE TABLE bodies rather than maintained beside them. Ordering is the reason this runs
        in three passes rather than one: tables first, then the columns, then the indexes --
        because an index over a column added later cannot be created until the column is.

        **What this does not express.** Added columns and widened unique constraints are
        reconciled forward. It cannot rename a column, change a type, or backfill a value.
        Adding a `NOT NULL` column to a table that already has rows fails, correctly -- there is
        no value to give them, and inventing one is a backfill decision rather than a schema
        application. Any of those needs a real migration: a version table, an ordered history
        and a workflow. Not built, because this is a single-tenant local pipeline whose only
        databases are a developer's and a test run's, and the hosted control plane that makes
        migration history load-bearing is M4 and unbuilt. A framework bought now is carried for a
        year before it is needed. When the first rename or backfill arrives, this is the thing to
        replace rather than the thing to extend -- it converges forward and keeps no history to
        reconcile, so replacing it costs nothing that has to be unwound.
        """
        ddl = resources.files("sync.graph").joinpath("schema.sql").read_text(encoding="utf-8")
        statements = _statements(ddl)
        creates = [s for s in statements if s.upper().startswith("CREATE TABLE")]
        rest = [s for s in statements if s not in creates]

        connection = self._connect()
        # Nothing to converge when the database is empty: the creates below build every column.
        # Worth a query because `apply_schema` runs in every test's fixture and the column pass
        # is about eighty statements -- unconditional, it cost the suite 83s against 74s.
        existing = connection.execute(
            "SELECT count(*) AS tables FROM information_schema.tables WHERE table_schema = 'public'"
        ).fetchone()["tables"]

        # One round trip per pass rather than one per statement. Issuing them separately cost
        # the better part of a minute across the suite for nothing -- measured at 128s.
        if existing:
            for statements_in_pass in [creates, _add_missing_columns(creates)]:
                connection.execute(";\n".join(statements_in_pass))
            _reconcile_unique_constraints(connection, creates)
            connection.execute(";\n".join(rest))
        else:
            for statements_in_pass in [creates, rest]:
                connection.execute(";\n".join(statements_in_pass))

    def _schema_tables(self) -> list[str]:
        ddl = resources.files("sync.graph").joinpath("schema.sql").read_text(encoding="utf-8")
        return [
            _table_name(statement)
            for statement in _statements(ddl)
            if statement.upper().startswith("CREATE TABLE")
        ]

    def truncate_all(self, keep: Sequence[str] = ()) -> None:
        """Empty every table the schema declares, except the ones named.

        The list used to be written out here, and it was right -- but it was right the way
        `schema.sql` was complete: by somebody remembering. A table added later would have been
        missed by it exactly as a column added later was missed by `apply_schema`, and the
        consequence is quieter than a failed insert. Rows from one run survive into the next and
        the failure surfaces somewhere with no obvious connection to this method.

        `keep` exists because a scan cannot use this method as written. It empties the whole
        database, so a scan of one repository erases every other repository's rows -- `cli.run`
        says a hosted control plane must never do it, and until `replace_call_sites` existed there
        was nothing else that made a re-index converge. A scan now keeps `call_site` and converges
        it per repository instead.

        Keeping a parent while truncating its children is what the foreign keys already allow:
        `finding` references `call_site`, and truncating the referencing table needs nothing from
        the referenced one. Keeping a child while truncating its parent would need `CASCADE` to
        reach back, which it does, so a caller cannot use this to leave a dangling row.
        """
        tables = [table for table in self._schema_tables() if table not in set(keep)]
        self._connect().execute(f"TRUNCATE {', '.join(tables)} CASCADE")

    def upsert_call_site(self, site: CallSite) -> str:
        # line and col are part of identity, not just data: two distinct call sites
        # in the same file can share a symbol (the same SDK method called twice), and
        # without a position component they'd hash to one id and silently collapse.
        # This means a call site that merely shifts down the file (no other content
        # change) becomes a new row rather than an update to the old one, which is
        # why an upsert on its own never converges a repository that changed:
        # `replace_call_sites` retracts what this pass did not find, and a caller
        # looping over this method instead leaves every old position asserted.
        #
        # `retracted_at = NULL` on conflict because a call that comes back to a
        # position it once occupied -- the comment above it deleted again -- is
        # current, not a resurrected ghost. The row is the same row; what changed is
        # whether the repository has it.
        site_id = _stable_id(site.repo_id, site.path, site.symbol, str(site.line), str(site.col))
        self._connect().execute(
            """
            INSERT INTO call_site (id, repo_id, path, line, col, vendor_id, operation_id,
                                   symbol, args_keys, response_fields_read, sdk_version, content_hash,
                                   loop_depth)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                line = EXCLUDED.line,
                col = EXCLUDED.col,
                operation_id = EXCLUDED.operation_id,
                args_keys = EXCLUDED.args_keys,
                response_fields_read = EXCLUDED.response_fields_read,
                sdk_version = EXCLUDED.sdk_version,
                content_hash = EXCLUDED.content_hash,
                loop_depth = EXCLUDED.loop_depth,
                indexed_at = now(),
                retracted_at = NULL
            """,
            (
                site_id, site.repo_id, site.path, site.line, site.col, site.vendor_id,
                site.operation_id, site.symbol, site.args_keys, site.response_fields_read,
                site.sdk_version, site.content_hash, site.loop_depth,
            ),
        )
        return site_id

    def replace_call_sites(self, repo_id: str, sites: Sequence[CallSite]) -> list[str]:
        """One repository's call sites, converged on the revision just indexed. Ids, in order.

        `upsert_call_site` alone cannot do this and says so: position is part of identity, so a
        call that merely shifted down the file becomes a new row and the old one survives. One
        blank line inserted above a call turned one row into two, and the stale row kept the
        finding raised against it -- a finding naming a position the code no longer has, which
        reads as live and sends `make_locate` to a line that moved.

        The only thing that had ever cleared those was `truncate_all`, which is per *database*.
        This is per repository, which is the grain a re-index actually has: one customer's scan
        must not be able to erase another's rows, and a graph holding two repositories is the
        state a hosted control plane is entirely made of.

        **Retracted, not deleted, and the foreign key is why.** `finding.call_site_id` cascades on
        delete, so removing the stale row removes what a run concluded about it -- with no error
        and nothing left to notice. Measured on the first attempt at this: the ghost row went and
        the finding went with it, one row to zero. So the row stays, `retracted_at` is stamped, and
        every query that speaks for the current revision excludes it. The record survives; nothing
        acts on it. `open_findings` is where the second half of that lives.

        Stamped inside one transaction with the upserts, and only over rows still current, so a
        reader either sees the revision before this pass or the revision after it, and a row that
        went absent two passes ago keeps the timestamp of the pass that lost it.

        The empty sequence is a real answer rather than a guard: a customer who removed their last
        call to a vendor has zero call sites, and declining to write that would leave the graph
        claiming an integration that is gone. `id <> ALL('{}')` is true of every row, so that case
        needs no branch here.

        What this does not do is match an old row to a new one and move the finding across. A call
        at line 13 where there used to be one at line 12 may be the same call shifted or a
        different call written where the old one was deleted, and nothing at this layer can tell
        those apart. A wrong guess reattributes a conclusion to a call nobody drew it about, which
        is a quieter defect than the two this method exists to avoid.
        """
        with self.transaction():
            ids = [self.upsert_call_site(site) for site in sites]
            self._connect().execute(
                """
                UPDATE call_site
                   SET retracted_at = now()
                 WHERE repo_id = %s AND retracted_at IS NULL AND id <> ALL(%s::text[])
                """,
                (repo_id, ids),
            )
        return ids

    def upsert_vendor_change(self, change: VendorChange) -> str:
        change_id = _stable_id(
            change.vendor_id, change.from_version, change.to_version, change.kind,
            change.path_ptr, change.operation_id, change.raw.get("text", ""),
        )
        self._connect().execute(
            """
            INSERT INTO vendor_change (id, vendor_id, from_version, to_version, kind,
                                       operation_id, path_ptr, severity, source, raw)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET raw = EXCLUDED.raw, detected_at = now()
            """,
            (
                change_id, change.vendor_id, change.from_version, change.to_version, change.kind,
                change.operation_id, change.path_ptr, change.severity, change.source,
                json.dumps(change.raw),
            ),
        )
        return change_id

    def insert_finding(self, finding: Finding) -> str:
        """One finding, refused if it names no rung.

        The refusal is here and not on the model. `Finding` is exported from `sync.core`, which
        `CLAUDE.md` calls the published plugin SDK -- a required field there breaks every detector
        a third party has written, and inside this repository alone it cost 153 failures and 120
        errors across 32 files. `sync.graph` is internal, so nothing published is at stake, and
        `CLAUDE.md` puts validation at boundaries: a write to Postgres is one, a Pydantic
        constructor inside our own detector is not.

        `unattributed` is what the column defaults to, so a row written without a rung is
        indistinguishable from every row that predates the column -- there is no later query that
        can separate a detector which forgot from history that could not know. That is what makes
        this a refusal rather than a warning: the evidence a warning would tell you to go and check
        does not survive the write.

        Raised rather than corrected. There is no rung this could substitute that would not be a
        binding claim nobody made, and `sync.benchmark.binding` scores precision per rung off this
        column -- a guessed value there is a measurement about a binder that did not run.
        """
        if finding.binding_rung == UNATTRIBUTED:
            raise ValueError(
                f"{finding.detector} produced a finding naming no binding rung, and "
                f"'{UNATTRIBUTED}' is reserved for rows written before the column existed. "
                f"The rung names the binding whose wrongness would make the finding wrong: "
                f"'static' for a claim resting on a static binding, the correlator's own rung "
                f"carried through where a span-to-operation correlation is load-bearing."
            )

        # `claim` is in the identity, not just data. Without it the key was
        # (detector, call_site, vendor_change), which is one row per call site for any detector
        # that does not join against a vendor change -- and three of them do not. Two claims
        # about one site then derived one id, and DO NOTHING dropped the second with no error
        # and no warning. `schema.sql` states the grain this restores.
        #
        # Neither the rationale nor anything derived from it may join this key: efficiency
        # rationales carry live call counts, so an id computed from one would change between
        # runs and accumulate a row per scan rather than converging on the row it already wrote.
        finding_id = _stable_id(
            finding.detector, finding.call_site_id, finding.vendor_change_id or "", finding.claim
        )
        self._connect().execute(
            """
            INSERT INTO finding (id, detector, claim, call_site_id, vendor_change_id, severity,
                                 rationale, status, binding_rung)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                finding_id, finding.detector, finding.claim, finding.call_site_id,
                finding.vendor_change_id, finding.severity, finding.rationale, finding.status,
                # Written, and deliberately absent from `_stable_id` above. The rung describes
                # the binding a claim rested on rather than which claim it is, so a correlator
                # improving from `unresolved` to `observed` converges on the row it already
                # wrote -- in the key it would add a second row for the same claim and every
                # rate over this table would double-count the findings whose attribution
                # got better.
                finding.binding_rung,
            ),
        )
        return finding_id

    def call_sites_for_operation(
        self,
        vendor_id: str,
        operation_id: str,
        *,
        repo_id: str | None = None,
        path_prefix: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[CallSite]:
        """Call sites the code currently has on one vendor operation, in one repository or in all.

        Retracted rows are excluded and there is no parameter to include them. A detector asking
        this question is asking what to raise a finding against, and a position the code no longer
        occupies is not one -- that is the whole point of retracting instead of deleting, and an
        opt-in flag here would be an invitation to hand a detector the history. Reading a retracted
        site is `get_call_site`, by the id a finding already holds.

        `repo_id` is optional and its absence means every repository, which is a real query for an
        aggregate across customers. It is not a sensible default for a detector: a scan runs against
        one repository, and unscoped this returned another's rows, so `VendorChangeDetector` emitted
        a finding for each -- a patch proposed to one customer for a line in somebody else's
        codebase. `truncate_all` was what hid that, by making a second repository impossible to
        hold.

        `tests/test_reindex_convergence.py` reads the detector sources and fails on a call here that
        omits it, because the parameter staying optional is what lets a fifth detector reacquire the
        defect silently.

        `limit` is a real SQL `LIMIT`, not a slice applied to a fetch that already happened --
        `limit=None`, the default, carries no bound at all, which is what every existing caller
        (three detectors, `binding_surface`) needs: each of them ranks or counts over the whole
        set, and a page of it would rank the wrong thing. `call_sites_for_operation_count` is the
        matching denominator, read without fetching a single row's columns.

        `path_prefix` narrows to a directory or a file prefix and is a real SQL predicate, for
        the same reason `limit` is: a prefix applied after the fetch reads every row off the
        wire before discarding most of them, which is the whole cost the filter exists to avoid
        against a customer repository holding thousands of sites.
        """
        clause, parameters = _call_site_predicate(
            vendor_id, operation_id, repo_id=repo_id, path_prefix=path_prefix
        )
        limit_clause = ""
        if limit is not None:
            limit_clause = " LIMIT %s OFFSET %s"
            parameters += [limit, offset]
        rows = self._connect().execute(
            f"SELECT * FROM call_site WHERE {clause} ORDER BY path, line{limit_clause}",
            parameters,
        ).fetchall()
        return [CallSite(**row) for row in rows]

    def call_sites_for_operation_count(
        self,
        vendor_id: str,
        operation_id: str,
        *,
        repo_id: str | None = None,
        path_prefix: str | None = None,
    ) -> int:
        """How many rows `call_sites_for_operation` would return unbounded -- the denominator a
        page of it is drawn from, read without a single column of any row.

        Every narrowing parameter the page takes is taken here too. A denominator drawn from a
        wider set than the page it sits beside tells a reader the page is a window on something
        it is not, which is the failure the console keeps having to close by hand.
        """
        clause, parameters = _call_site_predicate(
            vendor_id, operation_id, repo_id=repo_id, path_prefix=path_prefix
        )
        row = self._connect().execute(
            f"SELECT count(*) AS n FROM call_site WHERE {clause}", parameters
        ).fetchone()
        return row["n"]

    def call_sites_common_directory(
        self,
        vendor_id: str,
        operation_id: str,
        *,
        repo_id: str | None = None,
        path_prefix: str | None = None,
    ) -> str:
        """The deepest directory every live call site on this operation shares, or `""`.

        The binding surface's path column is the widest thing on that screen, and on a real
        repository most of its width is a prefix that is identical on every row. This is that
        prefix, so the screen can state it once and give each row the part that distinguishes it.
        Nothing is hidden by that: the prefix is on screen in words, above the column it came out of.

        **A property of the filtered set, not of a page.** Computed under the same predicate the
        page is drawn from, so it narrows when the filter does. Computing it over the fifty rows in
        one window would make the same call site render differently on page one and page two, which
        is a column whose meaning depends on where you are standing.

        `min` and `max` are the whole scan, and that is not a trick worth hiding: for any set of
        strings the longest common prefix of the set is the longest common prefix of its
        lexicographic extremes, because a character position where the extremes agree is one where
        everything between them agrees too. Two aggregates over an indexed column rather than
        reading every path off the wire to fold in Python.

        **Truncated at the last `/`, and that is the correctness condition rather than a nicety.**
        `create-a.ts` and `create-b.ts` share the characters `create-`; stopping there would name a
        directory that does not exist and leave each row holding a remainder no reader could rejoin
        to anything. A shared prefix is only sayable at a segment boundary.
        """
        clause, parameters = _call_site_predicate(
            vendor_id, operation_id, repo_id=repo_id, path_prefix=path_prefix
        )
        row = self._connect().execute(
            f"SELECT min(path) AS lo, max(path) AS hi FROM call_site WHERE {clause}", parameters
        ).fetchone()
        return _common_directory(row["lo"], row["hi"])

    def call_site_repositories_for_operation(
        self, vendor_id: str, operation_id: str
    ) -> dict[str, int]:
        """Which repositories hold a live call site on one vendor operation, and how many each
        holds -- one `GROUP BY`, never a query per repository.

        Deliberately unscoped by `repo_id` and by `path_prefix`: this is the option list a
        repository filter is built from, and an option list narrowed by the filter it sets
        collapses to whatever is already selected, leaving no way back. The counts it carries
        are therefore counts over the whole operation, which is a different number from the
        page beside it whenever a path filter is active -- the caller renders which one it is
        showing rather than letting a reader assume.

        **A repository whose call sites have all been retracted is absent, not present with a
        zero**, matching `call_sites_for_operation`'s own exclusion. Offering a repository that
        can only ever answer with an empty page would invent a choice the graph does not hold.
        """
        clause, parameters = _call_site_predicate(vendor_id, operation_id)
        rows = self._connect().execute(
            f"""
            SELECT repo_id, count(*) AS n
              FROM call_site
             WHERE {clause}
             GROUP BY repo_id
             ORDER BY repo_id
            """,
            parameters,
        ).fetchall()
        return {row["repo_id"]: row["n"] for row in rows}

    def call_site_counts(self, repo_id: str) -> dict[str, int]:
        """How many indexed call sites reach each vendor, for one repository.

        **One row is one call site, not one dependency.** The count answers how many *places in
        the code* call a vendor, which differs from how many dependencies a manifest declares
        whenever one vendor is called from several files -- the normal case, and exactly the case
        ranking is about.

        **A vendor with no call sites is absent from the result, not present with a zero.** That
        absence has two causes this query cannot separate: the indexer looked and found nothing,
        or it never looked because nothing declares which package to look for. A zero would
        assert the first. Only the intake category tells them apart, the caller holds it and this
        does not, so the contract stops at absence deliberately rather than resolving it wrongly
        here. `sync.signals.reachability` is where that resolution happens.

        Scoped to a repository for the reason `observed_calls` is: it is the unit a finding is
        raised against, and a count that leaked another customer's call sites in would rank the
        wrong code.

        Retracted rows are excluded for the same reason and it matters more here than it looks: a
        count over the whole table grows every time a file is edited above a call, so ranking would
        promote whichever repository had been re-indexed most rather than whichever calls the vendor
        most.
        """
        rows = self._connect().execute(
            """
            SELECT vendor_id, count(*) AS sites
              FROM call_site
             WHERE repo_id = %s AND retracted_at IS NULL
             GROUP BY vendor_id
            """,
            (repo_id,),
        ).fetchall()
        return {row["vendor_id"]: row["sites"] for row in rows}

    def call_site_coverage(self, repo_id: str) -> dict[str, tuple[int, datetime]]:
        """How many current call sites reach each vendor, and when the newest of them was
        indexed, for one repository -- both facts read off the same rows in one round trip.

        This used to be two separate reads, `call_site_counts` plus a `call_site_last_indexed`
        that no longer exists, composed by a caller keying one by the other's result. Both
        queries shared the same `WHERE repo_id = %s AND retracted_at IS NULL GROUP BY vendor_id`,
        so their key sets agreed only if nothing wrote to `call_site` between the two round
        trips -- and Postgres's default READ COMMITTED gives every statement its own snapshot,
        so even wrapping both in one transaction would not have closed the gap. A call site
        indexed for a vendor between the two reads landed in one result and not the other, and
        the caller's `{v: last_indexed[v] for v in counts}` raised `KeyError`. One query has one
        snapshot, so the two facts cannot disagree and there is no key to be missing.

        **A vendor with no call sites is absent from the result, not present with a zero or a
        `None`.** `call_site_counts`'s own contract is why: that absence has two causes a query
        cannot separate -- the indexer looked and found nothing, or it never looked because
        nothing declares which package to look for -- and either a zero count or a null
        timestamp would assert the first.

        Retracted rows are excluded for the same reason `call_site_counts` excludes them: a
        call site the last pass stopped finding is not part of what the repository currently
        has, so it must contribute neither to the count nor to the timestamp -- a retracted
        row's `indexed_at` must not win against a surviving row merely for being newer.
        """
        rows = self._connect().execute(
            """
            SELECT vendor_id, count(*) AS sites, max(indexed_at) AS last_indexed
              FROM call_site
             WHERE repo_id = %s AND retracted_at IS NULL
             GROUP BY vendor_id
            """,
            (repo_id,),
        ).fetchall()
        return {row["vendor_id"]: (row["sites"], row["last_indexed"]) for row in rows}

    def get_call_site(self, call_site_id: str) -> CallSite:
        """One call site by id, retracted or not.

        Unfiltered on purpose. A finding holds a call site id and stays queryable after the call
        moved, so this is what makes an old conclusion explainable -- `retracted_at` on the returned
        model is how a caller asks whether the code still has it. `open_findings` is what keeps a
        retracted site out of the remediation path; this is not that gate.
        """
        row = self._connect().execute(
            "SELECT * FROM call_site WHERE id = %s", (call_site_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"no call site {call_site_id}")
        return CallSite(**row)

    def get_vendor_change(self, change_id: str) -> VendorChange:
        row = self._connect().execute(
            "SELECT * FROM vendor_change WHERE id = %s", (change_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"no vendor change {change_id}")
        return VendorChange(**row)

    def all_vendor_changes(self, vendor_id: str) -> list[VendorChange]:
        rows = self._connect().execute(
            "SELECT * FROM vendor_change WHERE vendor_id = %s ORDER BY detected_at", (vendor_id,)
        ).fetchall()
        return [VendorChange(**row) for row in rows]

    def vendor_changes_for_operation(
        self, vendor_id: str, operation_id: str, *, limit: int | None = None, offset: int = 0
    ) -> list[VendorChange]:
        """One vendor's changes naming one operation -- what `binding_surface` actually shows,
        as its own query rather than a Python filter over `all_vendor_changes`'s wide answer.

        A sibling method rather than a parameter on `all_vendor_changes`, because
        `all_vendor_changes(self, vendor_id: str)` is pinned exactly by
        `sync.mcp.tools.GraphReader`, the frozen surface's structural protocol --
        `tests/test_mcp_tools.py::test_the_real_graph_store_satisfies_the_reader_protocol` fails
        the moment that signature grows a parameter the protocol does not declare. `cli.py`'s feed
        render and `VendorChangeDetector` keep calling the wide method unchanged.

        `limit=None` is unbounded. `vendor_changes_for_operation_count` is the matching
        denominator.
        """
        parameters: list[object] = [vendor_id, operation_id]
        limit_clause = ""
        if limit is not None:
            limit_clause = " LIMIT %s OFFSET %s"
            parameters += [limit, offset]
        rows = self._connect().execute(
            f"SELECT * FROM vendor_change WHERE vendor_id = %s AND operation_id = %s "
            f"ORDER BY detected_at{limit_clause}",
            parameters,
        ).fetchall()
        return [VendorChange(**row) for row in rows]

    def vendor_changes_for_operation_count(self, vendor_id: str, operation_id: str) -> int:
        row = self._connect().execute(
            "SELECT count(*) AS n FROM vendor_change WHERE vendor_id = %s AND operation_id = %s",
            (vendor_id, operation_id),
        ).fetchone()
        return row["n"]

    def open_findings(self) -> list[Finding]:
        """Findings still to act on: open status, and a call site the code still has.

        The join is the other half of retraction. A finding whose call site was retracted names a
        position the code no longer occupies, so `make_locate` would send an agent to a line that
        moved -- and that hazard is what made deleting the stale row tempting, at the cost of
        deleting the finding with it. Filtering here instead keeps the row queryable and stops
        anything from working on it.

        `status` is not touched, and that is deliberate. It tracks what remediation did --
        'open', 'patched', 'abandoned' -- and rewriting it here would say a run reached a conclusion
        it never reached. Whether the code still has the call site is a fact about the graph, so it
        is read from the graph.
        """
        rows = self._connect().execute(
            """
            SELECT finding.* FROM finding
              JOIN call_site ON call_site.id = finding.call_site_id
             WHERE finding.status = 'open' AND call_site.retracted_at IS NULL
             ORDER BY finding.created_at
            """
        ).fetchall()
        return [Finding(**row) for row in rows]

    def open_findings_page(
        self, *, limit: int | None = None, offset: int = 0, repo_id: str | None = None
    ) -> list[Finding]:
        """`open_findings`, windowed by a real SQL `LIMIT` -- a sibling rather than a parameter
        on `open_findings` itself, because `open_findings(self)` is pinned exactly by
        `sync.mcp.tools.GraphReader`'s structural protocol and gaining a parameter there fails
        `tests/test_mcp_tools.py::test_the_real_graph_store_satisfies_the_reader_protocol`.

        `limit=None` is unbounded, matching `open_findings`. `open_findings_count` is the
        matching denominator. `repo_id` narrows to one repository and is why
        `detector_accountability` reads this method rather than the unpaginated one: an
        aggregate scoped to a codebase and the same aggregate across the fleet are the same
        query with one predicate, not two reads.
        """
        predicate, parameters = _open_findings_predicate(repo_id=repo_id)
        limit_clause = ""
        if limit is not None:
            limit_clause = " LIMIT %s OFFSET %s"
            parameters = parameters + [limit, offset]
        rows = self._connect().execute(
            f"""
            SELECT finding.* FROM finding
              JOIN call_site ON call_site.id = finding.call_site_id
             WHERE {predicate}
             ORDER BY finding.created_at{limit_clause}
            """,
            parameters,
        ).fetchall()
        return [Finding(**row) for row in rows]

    def open_findings_count(
        self, *, repo_id: str | None = None, vendor_id: str | None = None
    ) -> int:
        """How many rows `open_findings`/`open_findings_page` return unbounded, through the same
        join -- a retracted call site's finding is invisible to both or neither.

        `vendor_id` sits beside `repo_id` so `severity_rollup` can compute its total under the
        same scope as its breakdown, through a second real aggregate rather than by summing the
        first. Two numbers that cannot contradict each other are two numbers that can never
        reveal one of them is wrong.
        """
        predicate, parameters = _open_findings_predicate(repo_id=repo_id, vendor_id=vendor_id)
        row = self._connect().execute(
            f"""
            SELECT count(*) AS n FROM finding
              JOIN call_site ON call_site.id = finding.call_site_id
             WHERE {predicate}
            """,
            parameters,
        ).fetchone()
        return row["n"]

    def open_findings_count_bounded(
        self, bound: int, *, repo_id: str | None = None
    ) -> tuple[int, bool]:
        """How many open findings there are, up to `bound` -- and whether the true count reaches
        it.

        `open_findings_count` is already a single aggregate and materialises nothing, but it
        still walks the whole join to produce an exact answer, and the fleet screen does not
        need an exact answer to render -- it needs one fast enough to load in the time an
        operator will wait. This is Sentry's `count_hits` pattern (`paginator.py:30-48`): the
        join is truncated with a real SQL `LIMIT` before it is counted, so Postgres stops
        scanning at `bound` rows however many actually match, and the count costs the same at
        ten thousand matching rows as it does at one thousand.

        The second element is the fact the count alone cannot carry: whether the scan stopped
        because it ran out of rows or because it hit `bound`. `n == bound` is the only way to
        tell -- the `LIMIT` makes `n` never exceed it, so equality means the bound was reached
        rather than merely approached. A caller that wants a bound-free answer already has
        `open_findings_count`; this is a different question, not a faster version of that one.
        """
        predicate, parameters = _open_findings_predicate(repo_id=repo_id)
        row = self._connect().execute(
            f"""
            SELECT count(*) AS n FROM (
                SELECT finding.id FROM finding
                  JOIN call_site ON call_site.id = finding.call_site_id
                 WHERE {predicate}
                 LIMIT %s
            ) AS bounded
            """,
            parameters + [bound],
        ).fetchone()
        n = row["n"]
        return n, n >= bound

    def open_findings_vendor_counts(self, *, repo_id: str | None = None) -> dict[str, int]:
        """Every open finding, tallied by vendor -- one `GROUP BY`, never a loop over findings.

        The vendor cardinality a customer integrates against does not grow with how many
        findings are open against it, so this is cheap at any scale `open_findings_count_bounded`
        is not: a customer with ten thousand open findings across six vendors still returns six
        rows here. That is what makes it safe to leave this distribution unbounded while the
        total beside it is truncated -- a `GROUP BY` over the whole table is not the defect a
        full materialisation of every row into Python is, which is what this replaces: the old
        `/api/overview` read every open finding, looked up its call site one row at a time, and
        tallied vendors in a Python loop.
        """
        predicate, parameters = _open_findings_predicate(repo_id=repo_id)
        rows = self._connect().execute(
            f"""
            SELECT call_site.vendor_id AS vendor_id, count(*) AS n
              FROM finding
              JOIN call_site ON call_site.id = finding.call_site_id
             WHERE {predicate}
             GROUP BY call_site.vendor_id
             ORDER BY call_site.vendor_id
            """,
            parameters,
        ).fetchall()
        return {row["vendor_id"]: row["n"] for row in rows}

    def open_findings_severity_counts(
        self, *, repo_id: str | None = None, vendor_id: str | None = None
    ) -> dict[str, int]:
        """Every open finding, tallied by severity -- the same reasoning
        `open_findings_vendor_counts` carries, over `finding.severity` instead of
        `call_site.vendor_id`.

        `repo_id` and `vendor_id` narrow together or separately, through the same shared
        predicate every other open-findings read uses. A vendor screen's severity filter is built
        from both at once: the breakdown beside one vendor's findings inside a selected repository
        has to be that vendor in that repository, or it is the same false claim one axis at a
        time.

        A distribution derived from a bounded page understates whichever severities the ordering
        happened not to reach before the bound -- exactly the failure `open_findings_count_bounded`
        is not asked to avoid, because a total is a single honest number at whatever ceiling it
        stopped at and a breakdown is not: a bounded breakdown presented as the breakdown is a
        falsehood the truncation introduced, not a smaller version of the truth. So this reads
        every row's severity, aggregated in SQL, rather than counting a `Counter` in Python over
        a full fetch of every `Finding`.
        """
        predicate, parameters = _open_findings_predicate(repo_id=repo_id, vendor_id=vendor_id)
        rows = self._connect().execute(
            f"""
            SELECT finding.severity AS severity, count(*) AS n
              FROM finding
              JOIN call_site ON call_site.id = finding.call_site_id
             WHERE {predicate}
             GROUP BY finding.severity
             ORDER BY finding.severity
            """,
            parameters,
        ).fetchall()
        return {row["severity"]: row["n"] for row in rows}

    def open_findings_summary(
        self,
        *,
        repo_id: str | None = None,
        vendor_id: str | None = None,
        severity: str | None = None,
        path_prefix: str | None = None,
    ) -> dict:
        """The newest `indexed_at` among every open finding's call site, and the rung they all
        share -- `None` when there are none or when they disagree -- read together in one round
        trip.

        `call_site_coverage`'s docstring carries why this is one query rather than two: two
        separate aggregate reads of the same join have no shared snapshot under READ COMMITTED,
        so a write landing between them could pair one fact with a revision the other fact does
        not describe -- here that would mean an `indexed_at` newer than the finding set
        `binding_rung` was computed over. One query has one snapshot, so the two cannot disagree.

        The three filters take the same values `open_findings_at_risk` takes, because that page
        and this envelope describe one answer: a rung that summarised the fleet while the rows
        beneath it were narrowed to one repository would be provenance for a set the reader
        cannot see.
        """
        predicate, parameters = _open_findings_predicate(
            repo_id=repo_id, vendor_id=vendor_id, severity=severity, path_prefix=path_prefix
        )
        row = self._connect().execute(
            f"""
            SELECT max(call_site.indexed_at) AS indexed_at,
                   CASE WHEN count(DISTINCT finding.binding_rung) = 1
                        THEN max(finding.binding_rung) END AS binding_rung
              FROM finding
              JOIN call_site ON call_site.id = finding.call_site_id
             WHERE {predicate}
            """,
            parameters,
        ).fetchone()
        return {"indexed_at": row["indexed_at"], "binding_rung": row["binding_rung"]}

    def open_findings_at_risk(
        self,
        *,
        repo_id: str | None = None,
        vendor_id: str | None = None,
        severity: str | None = None,
        path_prefix: str | None = None,
        order: str = DEFAULT_FINDING_ORDER,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict]:
        """One row per open finding, joined to the call site it names and the vendor change it
        rests on -- the binding an operator reads, rather than the `Finding` model.

        This is what `GraphSurface.whats_at_risk` answers for an agent, and it exists separately
        because that method cannot answer it for a repository: `sync/mcp/tools.py` is frozen, its
        rows carry no `repo_id`, and it walks every open finding doing one `get_call_site` round
        trip per row before slicing the result in Python. Repository scope is what every console
        level below Codebase inherits, so the filter has to reach the database.

        `LEFT JOIN vendor_change`, not an inner one: a finding raised from watched traffic names
        no change, and dropping it would silently shorten the page for exactly the detectors
        whose claims rest on the observed rung.

        `binding_rung` is `finding.binding_rung` -- the rung of that row's own claim, per finding
        because a page can hold findings from several binders and no one value is true of all of
        them. `open_findings_summary` carries the page-level rung, null when they disagree.

        `order` names an ordering rather than a column, and `FINDING_ORDERS` is the whole of what
        it may be. A column name reaching this from a query string would let a reader order by
        whatever a header happened to hold -- a rank over `binding_rung`, which is an evidence
        class and not a good-to-bad scale, or over a path, which sorts a codebase alphabetically
        and calls it a priority.
        """
        predicate, parameters = _open_findings_predicate(
            repo_id=repo_id, vendor_id=vendor_id, severity=severity, path_prefix=path_prefix
        )
        order_clause, order_parameters = _finding_order_clause(order)
        parameters = parameters + order_parameters
        limit_clause = ""
        if limit is not None:
            limit_clause = " LIMIT %s OFFSET %s"
            parameters = parameters + [limit, offset]
        return self._connect().execute(
            f"""
            SELECT finding.id AS finding_id,
                   finding.severity AS severity,
                   finding.binding_rung AS binding_rung,
                   finding.detector AS detector,
                   call_site.repo_id AS repo_id,
                   call_site.path AS path,
                   call_site.line AS line,
                   call_site.symbol AS symbol,
                   call_site.vendor_id AS vendor_id,
                   call_site.operation_id AS operation_id,
                   call_site.indexed_at AS indexed_at,
                   vendor_change.kind AS change_kind
              FROM finding
              JOIN call_site ON call_site.id = finding.call_site_id
              LEFT JOIN vendor_change ON vendor_change.id = finding.vendor_change_id
             WHERE {predicate}
             ORDER BY {order_clause}{limit_clause}
            """,
            parameters,
        ).fetchall()

    def open_findings_at_risk_count(
        self,
        *,
        repo_id: str | None = None,
        vendor_id: str | None = None,
        severity: str | None = None,
        path_prefix: str | None = None,
    ) -> int:
        """The true total `open_findings_at_risk` pages over, under the same filters.

        Separate from the page rather than derived from it: a total counted off a page is the
        page's own length wearing a bigger number's name, which is the defect this milestone
        keeps closing.
        """
        predicate, parameters = _open_findings_predicate(
            repo_id=repo_id, vendor_id=vendor_id, severity=severity, path_prefix=path_prefix
        )
        row = self._connect().execute(
            f"""
            SELECT count(*) AS n FROM finding
              JOIN call_site ON call_site.id = finding.call_site_id
             WHERE {predicate}
            """,
            parameters,
        ).fetchone()
        return row["n"]

    def set_finding_status(self, finding_id: str, status: FindingStatus) -> None:
        self._connect().execute("UPDATE finding SET status = %s WHERE id = %s", (status, finding_id))

    _OUTCOME_COLUMNS = (
        "finding_id", "attempt_index", "is_rehearsal", "vendor_id", "from_version", "to_version",
        "change_kind", "change_severity", "operation_id", "path_ptr", "language",
        "sdk_version", "symbol_shape", "arg_arity", "arg_key_hashes",
        "response_fields_touched_count", "strategy", "tier", "routing_row", "input_tokens",
        "output_tokens", "cache_read_input_tokens", "wall_ms", "static_verify_passed",
        "static_verify_error_class", "ci_result", "terminal_status", "abandon_reason",
        "pr_number", "pr_merged", "pr_merged_at", "human_edits_before_merge",
    )

    def record_migration_outcome(self, outcome: MigrationOutcome) -> None:
        """Append one attempt to the corpus.

        `ON CONFLICT DO NOTHING` on `(finding_id, attempt_index, is_rehearsal)` because the
        remediation graph retries and a restarted run must converge rather than inflate the
        corpus. An inflated corpus silently overstates every rate computed from it, which is
        worse than a missing row because nothing looks wrong.
        """
        values = [getattr(outcome, name) for name in self._OUTCOME_COLUMNS]
        placeholders = ", ".join(["%s"] * len(self._OUTCOME_COLUMNS))
        self._connect().execute(
            f"""
            INSERT INTO migration_outcome ({", ".join(self._OUTCOME_COLUMNS)})
            VALUES ({placeholders})
            ON CONFLICT (finding_id, attempt_index, is_rehearsal) DO NOTHING
            """,
            values,
        )

    def migration_outcomes(self) -> list[MigrationOutcome]:
        """Every production attempt, in corpus order.

        Filters `is_rehearsal` out rather than handing the dimension to every caller: a rehearsal
        row belongs in the table -- it still cost a repair attempt worth recording -- but nowhere
        a corpus-wide rate (`merge_rate`, `counts.pull_requests_opened`, ...) is computed. See the
        table's grain comment.
        """
        rows = self._connect().execute(
            "SELECT * FROM migration_outcome WHERE NOT is_rehearsal ORDER BY finding_id, attempt_index"
        ).fetchall()
        return [MigrationOutcome(**row) for row in rows]

    def migration_outcome_rollup_by_kind(self) -> list[dict]:
        """One row per (`change_kind`, `tier`) actually attempted -- a real SQL `GROUP BY` over
        `migration_outcome_kind_idx`, not a Python `Counter` over every row.

        **A (`change_kind`, `tier`) pair with no attempt has no row here.** That is what makes
        this the answer to "which change kinds are not mechanically safe": absence and a
        zero-abandonment group are two different facts, and only the group's presence tells
        them apart. `sync.dashboard.fleet.abandonment_by_change_kind` is what a caller reads.

        `attempt_count` and `distinct_finding_count` are the corpus grain rule
        (`migration_outcome` is one row per attempt) applied per group, same as
        `corpus_summary`'s fleet-wide `attempts`/`distinct_findings`. The `abandoned_*` pair is
        the same distinction scoped to `terminal_status = 'abandoned'`.
        """
        rows = self._connect().execute(
            """
            SELECT change_kind, tier,
                   count(*) AS attempt_count,
                   count(DISTINCT finding_id) AS distinct_finding_count,
                   count(*) FILTER (WHERE terminal_status = 'abandoned')
                       AS abandoned_attempt_count,
                   count(DISTINCT finding_id) FILTER (WHERE terminal_status = 'abandoned')
                       AS abandoned_distinct_finding_count
              FROM migration_outcome
             WHERE NOT is_rehearsal
             GROUP BY change_kind, tier
             ORDER BY change_kind, tier
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def migration_outcome_abandon_reasons_by_kind(self) -> list[dict]:
        """`abandon_reason`, tallied per (`change_kind`, `tier`), over abandoned attempts only.

        `abandon_reason` is free text written by the abandoning node (`state.get("diagnostics")`
        or exception text) rather than a coded vocabulary, so this reports whatever distinct
        strings actually occurred -- a closed set *of what was observed*, not a promise the
        column itself is bounded. `remediate-stage.md` requires `abandon_reason` non-null on an
        abandoned run; a null here is a defect in the writer, not an expected case, and is
        reported as `None` rather than silently folded into another bucket.
        """
        rows = self._connect().execute(
            """
            SELECT change_kind, tier, abandon_reason, count(*) AS n
              FROM migration_outcome
             WHERE NOT is_rehearsal AND terminal_status = 'abandoned'
             GROUP BY change_kind, tier, abandon_reason
             ORDER BY change_kind, tier
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def set_merge_outcome(
        self,
        finding_id: str,
        attempt_index: int,
        pr_number: int | None = None,
        pr_merged: bool | None = None,
        human_edits_before_merge: int | None = None,
    ) -> None:
        """Fill in what only arrives days later, by webhook.

        Merge outcome is the one measurement that tests the product claim, and a column that
        silently stays null destroys it. The update path exists from the first row rather than
        being added once someone notices the column is empty.

        `AND NOT is_rehearsal`: a real GitHub delivery describes a real pull request, which only
        a production run can have opened. Without the filter this would also match a rehearsal
        row sharing the same finding and attempt index, crediting a merge to an attempt that
        never reached a forge.
        """
        self._connect().execute(
            """
            UPDATE migration_outcome
               SET pr_number = COALESCE(%s, pr_number),
                   pr_merged = COALESCE(%s, pr_merged),
                   pr_merged_at = CASE WHEN %s THEN now() ELSE pr_merged_at END,
                   human_edits_before_merge = COALESCE(%s, human_edits_before_merge)
             WHERE finding_id = %s AND attempt_index = %s AND NOT is_rehearsal
            """,
            (pr_number, pr_merged, bool(pr_merged), human_edits_before_merge,
             finding_id, attempt_index),
        )

    _SHAPE_COLUMNS = (
        "vendor_id", "operation_id", "field_path", "json_type", "nullable_seen",
        "spec_enum_values", "source", "sample_count", "first_seen", "last_seen",
    )

    def record_observed_shape(self, shape: ObservedShape) -> None:
        """Fold one observation into the baseline.

        The conflict clause is an update rather than `DO NOTHING`, which is the difference
        between this table and the migration corpus: the grain is one row per
        (vendor, operation, field_path, json_type, source) tuple and `sample_count` is a counter
        on it, so a shape seen again is a count, not a row. `DO NOTHING` here would freeze every
        count at one and make the sample floor the detector depends on unenforceable.

        Each merged column merges the way its meaning requires. `nullable_seen` is OR because it
        is evidence and evidence does not expire. `spec_enum_values` is a union because traffic
        exercises one member at a time, and because this table has no spec-version column --
        last-write-wins would silently erase what an earlier specification named. The window
        widens at both ends rather than taking the last write, since sources do not arrive in
        order: an error-payload batch can be forwarded hours after a replay run observed the
        same shape.

        `sample_count` is the one of them whose merge is not idempotent, and it adds only for a
        source in `TRAFFIC_SOURCES`. A synthetic row is a body Sync constructed from a published
        specification, so writing it again is this ingest running again rather than the shape
        being seen again, and a counter that added would measure how often Sync ran against the
        floor the detector reads. Held as a maximum rather than by holding the row still: taking
        whichever value arrived first would make the counter the only column in this clause that
        depends on arrival order, and taking the incoming one would rewrite counts written before
        the clause was split.

        The classification is read here rather than asserted by the caller. A row's merge is a
        property of the mechanism that produced it, and `sync.graph.sources` is where that is
        decided for the reader too.
        """
        placeholders = ", ".join(["%s"] * len(self._SHAPE_COLUMNS))
        self._connect().execute(
            f"""
            INSERT INTO observed_shape ({", ".join(self._SHAPE_COLUMNS)})
            VALUES ({placeholders})
            ON CONFLICT (vendor_id, operation_id, field_path, json_type, source) DO UPDATE SET
                sample_count = CASE
                    WHEN observed_shape.source = ANY(%s)
                    THEN observed_shape.sample_count + EXCLUDED.sample_count
                    ELSE GREATEST(observed_shape.sample_count, EXCLUDED.sample_count)
                END,
                nullable_seen = observed_shape.nullable_seen OR EXCLUDED.nullable_seen,
                spec_enum_values = ARRAY(
                    SELECT DISTINCT unnest(observed_shape.spec_enum_values || EXCLUDED.spec_enum_values)
                    ORDER BY 1
                ),
                first_seen = LEAST(observed_shape.first_seen, EXCLUDED.first_seen),
                last_seen = GREATEST(observed_shape.last_seen, EXCLUDED.last_seen)
            """,
            [
                *(getattr(shape, name) for name in self._SHAPE_COLUMNS),
                sorted(TRAFFIC_SOURCES),
            ],
        )

    def record_observed_call(self, call: ObservedCall) -> None:
        """Fold one unit of work's calls against one operation into the graph.

        The conflict clause merges the span map with `||`, which is last-write-wins per key.
        That is what makes this idempotent under at-least-once delivery: a span already in the
        map re-folds to the same entry, so re-ingesting a batch -- or the overlapping subset a
        collector actually re-sends -- converges instead of inflating. There is no counter to
        double, because every count this table answers is derived from the map rather than
        stored beside it.

        The window widens at both ends rather than taking the last write. A collector flushes
        its buffered backlog after the live stream has resumed, so batches do not arrive in
        order, and a `first_seen` that took the last write would walk forward every time an old
        batch landed.

        `url_template` uses COALESCE-by-emptiness rather than EXCLUDED outright: an uncorrelated
        span writes an empty template, and a later correlated one must be able to fill it in
        without an earlier blank erasing what is already known.
        """
        self._connect().execute(
            """
            INSERT INTO observed_call (repo_id, vendor_id, operation_id, binding_rung,
                                       server_address, http_method, trace_id, url_template,
                                       spans, first_seen, last_seen)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (repo_id, vendor_id, operation_id, server_address, http_method, trace_id)
            DO UPDATE SET
                spans = observed_call.spans || EXCLUDED.spans,
                url_template = CASE
                    WHEN EXCLUDED.url_template <> '' THEN EXCLUDED.url_template
                    ELSE observed_call.url_template
                END,
                first_seen = LEAST(observed_call.first_seen, EXCLUDED.first_seen),
                last_seen = GREATEST(observed_call.last_seen, EXCLUDED.last_seen)
            """,
            (
                call.repo_id, call.vendor_id, call.operation_id, call.binding_rung,
                call.server_address, call.http_method, call.trace_id, call.url_template,
                json.dumps(call.spans), call.first_seen, call.last_seen,
            ),
        )

    def observed_calls(
        self, repo_id: str, *, limit: int | None = None, offset: int = 0
    ) -> list[ObservedCall]:
        """Every observed call for one repository.

        Scoped to a repository because that is the unit a finding is raised against, and a query
        that leaked another customer's traffic in would produce findings naming the wrong code.

        `limit=None` is unbounded, matching the efficiency and status-rate detectors, which both
        need every call to compute a per-trace count and would undercount from a page of them.
        `observed_calls_count` is the matching denominator.
        """
        parameters: list[object] = [repo_id]
        limit_clause = ""
        if limit is not None:
            limit_clause = " LIMIT %s OFFSET %s"
            parameters += [limit, offset]
        rows = self._connect().execute(
            f"""
            SELECT * FROM observed_call
             WHERE repo_id = %s
             ORDER BY trace_id, operation_id, http_method{limit_clause}
            """,
            parameters,
        ).fetchall()
        return [ObservedCall(**row) for row in rows]

    def observed_calls_count(self, repo_id: str) -> int:
        row = self._connect().execute(
            "SELECT count(*) AS n FROM observed_call WHERE repo_id = %s", (repo_id,)
        ).fetchone()
        return row["n"]

    def observed_operation_pairs(self, repo_id: str) -> list[tuple[str, str]]:
        """Every `(vendor_id, operation_id)` this repository's observed traffic actually names.

        Bounded by how many operations a repository calls, not by how many times it called
        them -- the cardinality `observed_shapes_for_operations` needs in order to join the
        baseline in with one query instead of one per pair. An uncorrelated span writes an empty
        `operation_id`, and that is excluded here rather than left for the caller to filter: it
        names no operation, so it must not manufacture a pair nothing can join against.
        """
        rows = self._connect().execute(
            """
            SELECT DISTINCT vendor_id, operation_id FROM observed_call
             WHERE repo_id = %s AND operation_id <> ''
             ORDER BY vendor_id, operation_id
            """,
            (repo_id,),
        ).fetchall()
        return [(row["vendor_id"], row["operation_id"]) for row in rows]

    def record_observed_error_window(self, window: ObservedErrorWindow) -> None:
        """Record one operation's failure count over one window.

        The conflict clause replaces rather than adds, which is where this parts company with
        `record_observed_shape`. A shape observation is an increment -- each one is fresh
        evidence that a shape recurs -- but a count over a bounded window is a level, and adding
        would double it every time the same export was fed twice. That is the idempotency rule
        with a number attached: the second ingest of one export has to converge, and a detector
        reading a doubled count would see a spike that is an artifact of how often the ingest ran.

        Replacement rather than a maximum, in the other direction. A window re-queried after a
        group was merged or deleted holds fewer errors, and a clause that could only ever
        increase would leave the graph asserting a level the tracker no longer reports, with
        nothing able to bring it down.

        `binding_rung` follows the count because it is outside the natural key: a correlator that
        improves must converge on the row it already wrote, and the row's rung has to describe
        the binding that produced the count now stored in it.
        """
        self._connect().execute(
            """
            INSERT INTO observed_error_window (repo_id, vendor_id, operation_id, binding_rung,
                                               source, status_class, window_start, window_end,
                                               error_count, issue_count)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (repo_id, vendor_id, operation_id, source, status_class,
                         window_start, window_end)
            DO UPDATE SET
                error_count = EXCLUDED.error_count,
                issue_count = EXCLUDED.issue_count,
                binding_rung = EXCLUDED.binding_rung,
                recorded_at = now()
            """,
            (
                window.repo_id, window.vendor_id, window.operation_id, window.binding_rung,
                window.source, window.status_class, window.window_start, window.window_end,
                window.error_count, window.issue_count,
            ),
        )

    def remove_observed_error_windows_outside(
        self,
        repo_id: str,
        vendor_id: str,
        source: str,
        window_start: datetime,
        window_end: datetime,
        keys: Collection[tuple[str, str]],
    ) -> int:
        """Drop this window's rows for this source that `keys` no longer names, and say how many.

        The count has a caller rather than being returned for symmetry: an ingest that wrote
        nothing and deleted three rows is indistinguishable from one that held nothing for this
        vendor, and rows leaving the graph unremarked is the worse half of that pair to get wrong.

        The other half of what makes an ingest a replacement. `record_observed_error_window`
        replaces a key whose count changed and cannot touch a key that stopped being reported at
        all -- a group merged into another or deleted outright leaves a row asserting a level the
        tracker no longer holds, and a consumer summing the window counts those errors a second
        time under the operation they were merged into.

        `source` bounds the delete because two sources are two samples of the same failures, which
        is why it is in the natural key; one ingest must not clear a window another source wrote.
        The bounds are the ones the caller wrote, never every window for the repository: an
        earlier period is a separate observation and is not contradicted by this one.

        An empty `keys` is a replacement like any other, not a no-op. A window the tracker now
        reports as clean has to bring yesterday's counts down, and a guard against the empty case
        would leave exactly the rows that can never be corrected.
        """
        operations = [operation for operation, _ in keys]
        classes = [status_class for _, status_class in keys]
        return self._connect().execute(
            """
            DELETE FROM observed_error_window
             WHERE repo_id = %s AND vendor_id = %s AND source = %s
               AND window_start = %s AND window_end = %s
               AND (operation_id, status_class)
                   NOT IN (SELECT * FROM unnest(%s::text[], %s::text[]))
            """,
            (repo_id, vendor_id, source, window_start, window_end, operations, classes),
        ).rowcount

    def observed_error_windows(
        self, repo_id: str, *, limit: int | None = None, offset: int = 0
    ) -> list[ObservedErrorWindow]:
        """Every failure count recorded for one repository.

        Scoped to a repository for the reason `observed_calls` is: it is the unit a finding is
        raised against, and a query leaking another customer's error volume in would produce
        findings naming the wrong code.

        `limit=None` is unbounded, the only shape any caller before this needed.
        `observed_error_windows_count` is the matching denominator.
        """
        parameters: list[object] = [repo_id]
        limit_clause = ""
        if limit is not None:
            limit_clause = " LIMIT %s OFFSET %s"
            parameters += [limit, offset]
        rows = self._connect().execute(
            f"""
            SELECT * FROM observed_error_window
             WHERE repo_id = %s
             ORDER BY window_start, window_end, operation_id, status_class, source{limit_clause}
            """,
            parameters,
        ).fetchall()
        return [ObservedErrorWindow(**row) for row in rows]

    def observed_error_windows_count(self, repo_id: str) -> int:
        row = self._connect().execute(
            "SELECT count(*) AS n FROM observed_error_window WHERE repo_id = %s", (repo_id,)
        ).fetchone()
        return row["n"]

    def repo_ids(self) -> list[str]:
        """Every repository the index has seen, sorted.

        `DISTINCT repo_id` over `call_site`, retracted rows included. That is what lets a
        repository whose every finding has closed still appear -- `open_findings` cannot, since
        it filters on finding status rather than on the repository. **What this cannot see:** a
        repository that was configured but never indexed has no call site row at all, so it is
        absent here exactly as it is absent from the graph -- indistinguishable from a
        repository that was never configured in the first place.
        """
        rows = self._connect().execute(
            "SELECT DISTINCT repo_id FROM call_site ORDER BY repo_id"
        ).fetchall()
        return [row["repo_id"] for row in rows]

    def observed_shapes(
        self, vendor_id: str, operation_id: str, *, traffic_only: bool = True
    ) -> list[ObservedShape]:
        """The baseline for one operation: what the vendor sent, unless everything is asked for.

        Scoped to one operation because that is what the detector asks about; a baseline that
        leaked another operation's fields into the answer would produce findings against paths
        the operation never returns.

        Scoped to traffic by default, which is the opposite of how `call_sites_for_operation`
        treats `repo_id` and for the opposite reason. There the wide answer is the dangerous one,
        so a detector has to ask for the narrow one and a test reads the sources to check it did.
        Here the narrow answer is the safe one and the two readers that matter both want it --
        `ObservedDriftDetector`, and the baseline `sync.remediate.nodes._observed` hands the mock
        builder. Making each ask would be two call sites that must not disagree.

        A `source` outside `TRAFFIC_SOURCES` is a row Sync built rather than one a vendor sent.
        `sync.verify.replay` constructs its bodies from the published specification, so a
        `replay` row is that specification restated through the customer's code; read as traffic
        it escalates a divergence to `breaking` on a rationale asserting the opposite of its own
        provenance, and at the sample floor it outranks the specification in the mock the next
        replay is verified against. Both are measured in
        `docs/superpowers/reports/2026-07-30-replay-shapes-reach-the-store.md`.

        `traffic_only=False` answers a different question -- what the table holds, which is what
        an audit of the ingest asks and what a test of the conflict clause has to read. It is not
        an escape hatch for a consumer that found the filter inconvenient.
        """
        clause = " AND source = ANY(%s)" if traffic_only else ""
        parameters = (
            (vendor_id, operation_id, sorted(TRAFFIC_SOURCES))
            if traffic_only
            else (vendor_id, operation_id)
        )
        rows = self._connect().execute(
            f"SELECT * FROM observed_shape "
            f"WHERE vendor_id = %s AND operation_id = %s{clause} "
            f"ORDER BY field_path, json_type, source",
            parameters,
        ).fetchall()
        return [ObservedShape(**row) for row in rows]

    def _shapes_for_operations_clause(
        self, pairs: Sequence[tuple[str, str]], *, traffic_only: bool
    ) -> tuple[str, list[object]]:
        vendor_ids = [vendor_id for vendor_id, _ in pairs]
        operation_ids = [operation_id for _, operation_id in pairs]
        where = " AND source = ANY(%s)" if traffic_only else ""
        parameters: list[object] = [vendor_ids, operation_ids]
        if traffic_only:
            parameters.append(sorted(TRAFFIC_SOURCES))
        return where, parameters

    def observed_shapes_for_operations(
        self,
        pairs: Sequence[tuple[str, str]],
        *,
        traffic_only: bool = True,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[ObservedShape]:
        """The baseline across every `(vendor_id, operation_id)` pair named, in one query.

        This is what `observed_telemetry` reads instead of calling `observed_shapes` once per
        pair -- a repository touching two hundred operations used to cost two hundred and one
        round trips for one page load. `(vendor_id, operation_id) IN (SELECT * FROM
        unnest(%s::text[], %s::text[]))` is the same tupled-unnest join
        `remove_observed_error_windows_outside` already uses for exclusion; here it is inclusion,
        one query regardless of how many pairs are named.

        An empty `pairs` makes no query at all and returns empty -- the property
        `observed_telemetry` depends on for a repository whose observed traffic is entirely
        uncorrelated: nothing here mints a pair to join against.

        `limit=None` is unbounded, matching `observed_shapes`'s own default.
        `observed_shapes_for_operations_count` is the matching denominator.
        """
        if not pairs:
            return []
        where, parameters = self._shapes_for_operations_clause(pairs, traffic_only=traffic_only)
        limit_clause = ""
        if limit is not None:
            limit_clause = " LIMIT %s OFFSET %s"
            parameters += [limit, offset]
        rows = self._connect().execute(
            f"""
            SELECT * FROM observed_shape
             WHERE (vendor_id, operation_id) IN (SELECT * FROM unnest(%s::text[], %s::text[])){where}
             ORDER BY vendor_id, operation_id, field_path, json_type, source{limit_clause}
            """,
            parameters,
        ).fetchall()
        return [ObservedShape(**row) for row in rows]

    def observed_shapes_for_operations_count(
        self, pairs: Sequence[tuple[str, str]], *, traffic_only: bool = True
    ) -> int:
        if not pairs:
            return 0
        where, parameters = self._shapes_for_operations_clause(pairs, traffic_only=traffic_only)
        row = self._connect().execute(
            f"""
            SELECT count(*) AS n FROM observed_shape
             WHERE (vendor_id, operation_id) IN (SELECT * FROM unnest(%s::text[], %s::text[])){where}
            """,
            parameters,
        ).fetchone()
        return row["n"]

    def upsert_repo_context(self, context: RepoContext) -> None:
        """Write one repository's context, replacing whatever it held.

        Last write wins, and there is no counter to lose. The natural key is `repo_id` and the
        table holds one row per repository, so re-running a seed converges on the row it already
        has -- which is what `2026-07-27-sync-pipeline-discipline.md` asks of every stage.

        `updated_at` is taken from the database rather than from the caller. Two writers on two
        machines disagreeing about the clock would otherwise make "which of these is later" a
        question about their clocks instead of about the writes.
        """
        self._connect().execute(
            """
            INSERT INTO repo_context (repo_id, body, source)
            VALUES (%s, %s, %s)
            ON CONFLICT (repo_id) DO UPDATE SET
                body = EXCLUDED.body,
                source = EXCLUDED.source,
                updated_at = now()
            """,
            [context.repo_id, context.body, context.source],
        )

    def repo_context(self, repo_id: str) -> RepoContext | None:
        """One repository's context, or None when it has none.

        None rather than an empty `RepoContext`, because absence and emptiness must not reach a
        prompt as two states. A caller that renders a section for an empty body would put an
        empty heading in front of an agent, which reads as a statement that there is nothing
        worth knowing rather than as nothing at all.
        """
        row = self._connect().execute(
            "SELECT * FROM repo_context WHERE repo_id = %s",
            [repo_id],
        ).fetchone()
        return RepoContext(**row) if row is not None else None
