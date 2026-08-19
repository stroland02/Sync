"""Persistence and queries for the API Dependency Graph."""

from __future__ import annotations

import hashlib
import json
import time
from collections import deque
from collections.abc import Collection, Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime, timezone
from importlib import resources

import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row

from sync.core import (
    CallSite,
    Finding,
    FindingStatus,
    MigrationOutcome,
    RepoContext,
    RepoSettings,
    VendorChange,
    ALLOWED_MERGE_POLICIES,
    ALLOWED_MERGE_METHODS,
    REFUSED_MERGE_POLICIES,
)
from sync.core.models import (
    INDEX_RUN_OUTCOMES,
    SEVERITY_ORDER,
    UNATTRIBUTED,
    ObservedCall,
    ObservedErrorWindow,
    ObservedShape,
)
from sync.graph.sources import TRAFFIC_SOURCES
from sync.signals.intake_attempt import IntakeAttempt


DEFAULT_DSN = "postgresql://sync:sync@localhost:5433/sync"
"""The graph `docker compose up -d` brings up, and the default of every entry point.

Here rather than in `sync.cli` because two entry points resolve it and neither owns the other:
the CLI defaults `--dsn` to it and `python -m sync.api` falls back to it when `SYNC_GRAPH_DSN`
is unset. Written twice they disagreed -- the API had no default at all and died on a bare
`KeyError`, so the console and the pipeline documented on one page pointed at different
databases, one of which did not exist.
"""


def describe_dsn(dsn: str) -> str:
    """A DSN as `host:port/dbname` -- enough to say which database, never the password."""
    info = conninfo_to_dict(dsn)
    host = info.get("host") or "localhost"
    port = info.get("port") or "5432"
    dbname = info.get("dbname") or info.get("user") or "?"
    return f"{host}:{port}/{dbname}"


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



# Owner decision 45's vocabulary, as codes. Deliberately here rather than in `sync.core`: that
# package is the published plugin SDK and a vendor adapter has no use for a reviewer's reason for
# dismissing a finding, so putting it there would widen the SDK for nobody.
#
# Closed for the same reason `AbandonReasonCode` is closed -- a promise to learn from dismissals
# needs a schema that can answer the question, and free text cannot be aggregated. The values are
# Sync's own reviewers'; `interface-originality.md` takes a vocabulary's shape and never its
# values.
#
# `false_positive` is load-bearing beyond the others: it is the only honest source of detector
# accuracy, which is exactly the number Gate 2's quality axes have no samples for today.
# The one channel every repository's events travel on.
#
# A Postgres channel name is an identifier, and a `repo_id` is `org/name` -- not one. So the scope
# rides in the payload and the subscriber filters, while the API keeps `repo_id` in the route path
# where owner decision 49 puts it. The channel being shared is an implementation detail; a client
# never sees another repository's events.
class _EventStream:
    """One repository's slice of the shared channel.

    Filtering happens here rather than in the publisher because Postgres channel names are
    identifiers and a `repo_id` is not one. A subscriber therefore sees every repository's
    notification on the wire and forwards only its own.

    **Notifications land in a deque via a handler rather than being read from a generator, and
    that is the third shape this took.** A single long-lived `notifies()` generator opened with no
    timeout blocked forever on a quiet channel, so the heartbeat could never fire -- the transport
    looked dead exactly when the system was idle. A fresh generator per call with `stop_after=1`
    fixed the blocking and lost every notification after the first, because closing the generator
    discards what it had buffered -- and an index run is precisely a burst. A handler owns neither
    problem: it appends as notifications arrive, and reading is just draining a deque.
    """

    def __init__(self, connection, repo_id: str) -> None:
        self._connection = connection
        self._repo_id = repo_id
        self._pending: deque[dict] = deque()
        connection.add_notify_handler(self._receive)

    def _receive(self, notice) -> None:
        self._pending.append(json.loads(notice.payload))

    def next(self, timeout: float) -> dict | None:
        """The next event for this repository, or `None` when the timeout passes with none.

        `None` is a real answer rather than an error: a quiet index is quiet, and the caller needs
        to tell that apart from a broken stream so it can send a heartbeat instead of reporting a
        drop.

        The `SELECT 1` is what makes the handler run. psycopg reads pending notifications while
        processing a result, so a connection issuing no queries never notices what arrived -- the
        poll is the price of not holding a blocking generator open.
        """
        deadline = time.monotonic() + timeout
        while True:
            while self._pending:
                event = self._pending.popleft()
                if event.get("repo_id") == self._repo_id:
                    return event
            if time.monotonic() >= deadline:
                return None
            self._connection.execute("SELECT 1")
            time.sleep(_POLL_SECONDS)


# Short enough that an event feels immediate, long enough that a quiet stream is not a busy loop.
_POLL_SECONDS = 0.05


EVENT_CHANNEL = "sync_events"

# `NOTIFY` refuses a payload over 8000 bytes and raises, which would take the write down with it.
# The margin covers the JSON envelope around the longest field.
_NOTIFY_PAYLOAD_LIMIT = 7900


DISMISSAL_REASONS: frozenset[str] = frozenset(
    {"not_used_here", "intentional", "false_positive", "wont_fix"}
)


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

    def missing_tables(self) -> list[str]:
        """Which tables `schema.sql` declares that this database does not have.

        For a reader that must not create them. `apply_schema` is the only writer of DDL here
        and every caller of it is a command a person ran deliberately; the console API is
        read-only, so it asks this instead and refuses with the answer rather than serving a
        500 from every route.

        Tables, not columns. A database whose schema is behind by a column is a different
        condition with a different remedy -- `apply_schema` converges it -- and reporting it
        here would send a reader to the wrong command.
        """
        declared = self._schema_tables()
        rows = self._connect().execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        ).fetchall()
        present = {row["table_name"] for row in rows}
        return [table for table in declared if table not in present]

    def truncate_all(self) -> None:
        """Empty every table the schema declares.

        The list used to be written out here, and it was right -- but it was right the way
        `schema.sql` was complete: by somebody remembering. A table added later would have been
        missed by it exactly as a column added later was missed by `apply_schema`, and the
        consequence is quieter than a failed insert. Rows from one run survive into the next and
        the failure surfaces somewhere with no obvious connection to this method.

        A whole-database wipe, and it means it. Its callers are a test fixture starting from
        nothing and the benchmark harness, which scores into a scratch database `cli.score`
        refuses to let anyone point at the corpus. A scan is not one of them: it calls
        `truncate_signal_and_detect`, and B129 records what it cost while it called this with an
        allow-list instead.
        """
        self._connect().execute(f"TRUNCATE {', '.join(self._schema_tables())} CASCADE")

    def truncate_signal_and_detect(self) -> None:
        """Empty what a scan rebuilds from scratch: SIGNAL's rows, then DETECT's.

        A scan names what it clears rather than what it spares, and the inversion is the whole
        fix. The allow-list this replaced held one table against the seven it did not name, so a
        scan emptied the migration corpus, the repository context it had seeded eight lines
        earlier, and three tables of telemetry it did not produce and cannot re-produce -- and a
        table added to `schema.sql` afterwards would have joined the wiped set by saying nothing.
        Naming the cleared set means a table nobody thought about survives, which is the
        direction a mistake here should point.

        `call_site` is rebuilt by a scan too and is deliberately absent: INDEX converges it per
        repository through `replace_call_sites`, which retracts what a pass stopped finding
        rather than deleting it. These two are not converged that way yet, so a scan of one
        repository still clears every repository's findings and every vendor's changes. That is
        a per-table grain argument rather than a line to change here, and B129 carries it.

        Never `CASCADE`. `finding` holds the only foreign keys in the schema and both ends are
        accounted for -- `vendor_change` is truncated with it and `call_site` is only referenced
        -- so the constraint is satisfied without one. A `CASCADE` would instead reach silently
        into whatever table references these next, which is the shape of the defect this method
        exists to close.
        """
        self._connect().execute("TRUNCATE vendor_change, finding")

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
        # One event per call site, owner-selected: the finest grain, so the canvas can draw an
        # edge the instant the index finds it. The cost -- thousands of notifications on a large
        # repository -- was stated when the choice was made and taken deliberately.
        #
        # The payload carries the node rather than signalling a re-read, which is the other half
        # of that selection: the canvas draws from the stream without a round trip. The rung is
        # `static` because that is what a call site is, and it travels on the wire for the same
        # reason it travels on the screen -- an edge whose rung cannot be named is unattributable.
        self._publish(
            {
                "kind": "call_site.indexed",
                "repo_id": site.repo_id,
                "path": site.path,
                "vendor_id": site.vendor_id,
                "operation_id": site.operation_id,
                "binding_rung": "static",
            }
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
        site = self._connect().execute(
            "SELECT repo_id, vendor_id FROM call_site WHERE id = %s", (finding.call_site_id,)
        ).fetchone()
        repo_id = site["repo_id"] if site is not None else None
        vendor_id = site["vendor_id"] if site is not None else None

        cursor = self._connect().execute(
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
        # Decision 76's second publisher, and what decision 87's new-findings banner needs to
        # exist at all.
        #
        # `cursor.rowcount` rather than an unconditional publish: `insert_finding` is
        # `ON CONFLICT DO NOTHING`, so a converging DETECT re-run writes nothing, and an event
        # tied to the call rather than the write would announce findings nobody opened on every
        # scheduled pass. A banner that cries wolf once is a banner people turn off.
        #
        # The severity travels because 87's banner is a triage prompt: a reader deciding whether
        # to interrupt themselves needs to know whether the arrival was breaking or an addition,
        # and a banner that made them open the table to find out would be the worse interruption.
        # The rung travels for the reason every artifact derived from a binding carries one.
        if cursor.rowcount:
            self._publish(
                {
                    "kind": "finding.opened",
                    "repo_id": repo_id,
                    "finding_id": finding_id,
                    "vendor_id": vendor_id,
                    "severity": finding.severity,
                    "binding_rung": finding.binding_rung,
                }
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

    def start_index_run(self, repo_id: str, *, started_at: datetime) -> None:
        """Record that an index pass began, before it is known whether it will finish.

        Written at the start rather than the end on purpose: a pass that dies leaves a row saying
        it started and never finished, which is the fact a reader needs before trusting the call
        sites it left behind. A table written only on success could not say anything had been
        attempted at all.
        """
        self._connect().execute(
            """
            INSERT INTO index_run (repo_id, started_at) VALUES (%s, %s)
            ON CONFLICT (repo_id, started_at) DO NOTHING
            """,
            [repo_id, started_at],
        )

    def finish_index_run(
        self, repo_id: str, *, started_at: datetime, finished_at: datetime, call_sites: int
    ) -> None:
        """Close the pass `started_at` opened, with what it actually wrote.

        `DO UPDATE` rather than a plain insert so a replayed finish converges: re-running INDEX
        over the same input must reach the same rows, which is what `CLAUDE.md` binds every stage
        to.
        """
        self._connect().execute(
            """
            INSERT INTO index_run (repo_id, started_at, finished_at, call_sites, outcome)
                 VALUES (%s, %s, %s, %s, 'completed')
            ON CONFLICT (repo_id, started_at)
              DO UPDATE SET finished_at = EXCLUDED.finished_at,
                            call_sites = EXCLUDED.call_sites,
                            outcome = EXCLUDED.outcome
            """,
            [repo_id, started_at, finished_at, call_sites],
        )

    def fail_index_run(
        self, repo_id: str, *, started_at: datetime, at: datetime, outcome: str
    ) -> None:
        """Close the pass `started_at` opened without a trustworthy count.

        `call_sites` is deliberately left NULL rather than written with whatever the pass had
        managed: a partial count is not a smaller count, it is not a count, and a number here
        would be read as the size of the codebase.

        The outcome is refused unless it is in the closed set, at this boundary rather than as a
        CHECK, for the same reason `record_dismissal` refuses a reason here.
        """
        if outcome not in INDEX_RUN_OUTCOMES:
            raise ValueError(
                f"{outcome!r} is not an index-run outcome; the closed set is "
                f"{', '.join(INDEX_RUN_OUTCOMES)}"
            )
        self._connect().execute(
            """
            INSERT INTO index_run (repo_id, started_at, finished_at, outcome)
                 VALUES (%s, %s, %s, %s)
            ON CONFLICT (repo_id, started_at)
              DO UPDATE SET finished_at = EXCLUDED.finished_at, outcome = EXCLUDED.outcome
            """,
            [repo_id, started_at, at, outcome],
        )

    def latest_index_run(self, repo_id: str) -> dict | None:
        """The newest pass this repository has, finished or not, or `None` if it has never been
        indexed.

        `None` is never-indexed, and it is a different fact from a pass that ran and found
        nothing -- which is a row with `call_sites = 0`. Collapsing those two is the conflation
        this console exists to refuse, and here it would tell an operator their codebase calls no
        vendor when nothing had ever looked.
        """
        row = self._connect().execute(
            """
            SELECT repo_id, started_at, finished_at, call_sites, outcome
              FROM index_run
             WHERE repo_id = %s
             ORDER BY started_at DESC
             LIMIT 1
            """,
            [repo_id],
        ).fetchone()
        return dict(row) if row is not None else None

    def index_run_count(self, repo_id: str) -> int:
        """How many passes this repository has had. One row is one pass, never one repository."""
        row = self._connect().execute(
            "SELECT count(*) AS n FROM index_run WHERE repo_id = %s", [repo_id]
        ).fetchone()
        return int(row["n"])

    def call_sites_for_repository(
        self, repo_id: str, *, limit: int | None = None
    ) -> list[CallSite]:
        """Every place one repository currently calls any vendor, ordered by position.

        The dependency graph the Overview draws needs the whole picture for one repository in one
        read. Composing it from `call_sites_for_operation` would mean a query per vendor per
        operation -- one round trip per node to draw a single picture -- and the console cannot
        know the operation list before it has the graph that names it.

        Retracted rows are excluded and there is no parameter to include them, for the same
        reason `call_sites_for_operation` has none: an edge the last index pass stopped finding
        is not a place this codebase calls the vendor, and drawing it would show exposure a
        reader cannot act on. `call_sites_for_repository_count` is the matching denominator, so
        a bounded read can say the picture is partial rather than quietly drawing a smaller
        codebase than the one that exists.
        """
        parameters: list[object] = [repo_id]
        limit_clause = ""
        if limit is not None:
            limit_clause = " LIMIT %s"
            parameters.append(limit)
        rows = self._connect().execute(
            "SELECT * FROM call_site WHERE repo_id = %s AND retracted_at IS NULL"
            f" ORDER BY vendor_id, path, line{limit_clause}",
            parameters,
        ).fetchall()
        return [CallSite(**row) for row in rows]

    def call_sites_page(
        self,
        repo_id: str,
        *,
        vendor_id: str | None = None,
        path_prefix: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """One page of a repository's current call sites, with the facets a browser needs.

        The whole-repository read above serves the dependency graph, which needs every row at
        once and no narrowing; this serves a table a person walks, which needs the opposite --
        a bounded page and the option lists to narrow it by.

        **The facet counts are computed without the facet's own filter applied**, the same rule
        the filter rail states on screen: an option list narrowed by the filter it sets
        collapses to whatever is already selected and leaves no way back to the rest. So the
        vendor counts honour a path prefix and ignore the vendor selection, and nothing here
        sums them into a total the caller did not ask for.

        Retracted rows are excluded, as everywhere: a site the last pass stopped finding is not
        a place this codebase calls the vendor, and `total` counts what the filters admit so
        the pager walks exactly the set on screen.
        """
        limit = max(limit, 1)
        where = ["repo_id = %s", "retracted_at IS NULL"]
        params: list[object] = [repo_id]
        if vendor_id is not None:
            where.append("vendor_id = %s")
            params.append(vendor_id)
        if path_prefix:
            where.append("path LIKE %s")
            params.append(f"{path_prefix}%")
        clause = " AND ".join(where)

        total = int(
            self._connect().execute(
                f"SELECT count(*) AS n FROM call_site WHERE {clause}", params
            ).fetchone()["n"]
        )
        rows = self._connect().execute(
            f"SELECT * FROM call_site WHERE {clause} ORDER BY path, line, col LIMIT %s OFFSET %s",
            [*params, limit, offset],
        ).fetchall()

        # The vendor facet, counted over everything the OTHER filters admit.
        facet_where = ["repo_id = %s", "retracted_at IS NULL"]
        facet_params: list[object] = [repo_id]
        if path_prefix:
            facet_where.append("path LIKE %s")
            facet_params.append(f"{path_prefix}%")
        vendor_rows = self._connect().execute(
            f"""
            SELECT vendor_id, count(*) AS n
              FROM call_site
             WHERE {" AND ".join(facet_where)}
             GROUP BY vendor_id
             ORDER BY vendor_id
            """,
            facet_params,
        ).fetchall()

        def rendered(row) -> dict:
            # `indexed_at` arrives as a datetime and the transport is JSON, so it is rendered
            # here rather than at the route: one place turns a stored instant into a string,
            # and every reader of this page gets the same spelling.
            item = dict(row)
            for key in ("indexed_at", "retracted_at"):
                value = item.get(key)
                if hasattr(value, "isoformat"):
                    item[key] = value.isoformat()
            return item

        consumed = offset + len(rows)
        return {
            "repo_id": repo_id,
            "items": [rendered(row) for row in rows],
            "total": total,
            "next_offset": consumed if consumed < total else None,
            "by_vendor": {row["vendor_id"]: int(row["n"]) for row in vendor_rows},
            "unfiltered_total": sum(int(row["n"]) for row in vendor_rows),
            "vendor_id": vendor_id,
            "path_prefix": path_prefix,
        }

    def api_topology(self, repo_id: str) -> dict:
        """The shape of one repository's API surface, measured from the call sites themselves.

        Everything here is a `GROUP BY` over `call_site` — no new parse, no new tool, and no
        figure that is not a count of rows the index wrote. What the numbers describe is the
        *topology*: how many operations a codebase reaches, how concentrated its calls are on
        a few of them, how many files touch more than one integration, and how many calls sit
        inside loops.

        **Loop depth is static evidence and the payload keeps it labelled as such**: a loop that
        never runs still counts, which is exactly why `call_site.loop_depth` exists as a depth
        rather than a flag. It says what the code says, never what ran.
        """
        connection = self._connect()
        base = "FROM call_site WHERE repo_id = %s AND retracted_at IS NULL"

        per_vendor = connection.execute(
            f"""
            SELECT vendor_id,
                   count(*)                     AS call_sites,
                   count(DISTINCT operation_id) AS operations,
                   count(DISTINCT path)         AS files
              {base}
             GROUP BY vendor_id
             ORDER BY count(*) DESC, vendor_id
            """,
            [repo_id],
        ).fetchall()

        busiest = connection.execute(
            f"""
            SELECT vendor_id, operation_id, count(*) AS call_sites, count(DISTINCT path) AS files
              {base}
             GROUP BY vendor_id, operation_id
             ORDER BY count(*) DESC, vendor_id, operation_id
             LIMIT 8
            """,
            [repo_id],
        ).fetchall()

        # A file reaching several integrations is where a vendor change costs the most to fix,
        # which is the one thing this table can say about coupling that a count of files cannot.
        multi_vendor = connection.execute(
            f"""
            SELECT path, count(DISTINCT vendor_id) AS vendors, count(*) AS call_sites
              {base}
             GROUP BY path
            HAVING count(DISTINCT vendor_id) > 1
             ORDER BY count(DISTINCT vendor_id) DESC, count(*) DESC, path
             LIMIT 8
            """,
            [repo_id],
        ).fetchall()

        loops = connection.execute(
            f"SELECT loop_depth, count(*) AS n {base} GROUP BY loop_depth ORDER BY loop_depth",
            [repo_id],
        ).fetchall()

        totals = connection.execute(
            f"""
            SELECT count(*)                                        AS call_sites,
                   count(DISTINCT vendor_id)                       AS vendors,
                   count(DISTINCT (vendor_id || ':' || operation_id)) AS operations,
                   count(DISTINCT path)                            AS files
              {base}
            """,
            [repo_id],
        ).fetchone()

        return {
            "repo_id": repo_id,
            "totals": dict(totals),
            "by_vendor": [dict(row) for row in per_vendor],
            "busiest_operations": [dict(row) for row in busiest],
            "multi_vendor_files": [dict(row) for row in multi_vendor],
            "by_loop_depth": {str(row["loop_depth"]): int(row["n"]) for row in loops},
        }

    def call_sites_for_repository_count(self, repo_id: str) -> int:
        """How many current call sites one repository holds, read without fetching their columns."""
        row = self._connect().execute(
            "SELECT count(*) AS n FROM call_site WHERE repo_id = %s AND retracted_at IS NULL",
            [repo_id],
        ).fetchone()
        return int(row["n"])

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

    def vendor_changes_page(
        self,
        *,
        vendor_id: str | None = None,
        severity: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """One page of every integration change the graph holds, newest first.

        **Deliberately not scoped to a repository, and the payload says so rather than
        implying otherwise.** What a vendor published is a fact about the vendor; it becomes a
        fact about a codebase only where a call site binds to it, which is what a finding is.
        A feed narrowed to one repository would be a different question with the same rows.

        Facets are counted without their own filter applied -- the rail's rule -- and one
        source is worth naming here rather than in the console: `oasdiff` rows do not converge
        across runs (`CLAUDE.md`'s named idempotency exemption), so a count over them is
        at-least-once rather than a measurement, and the caller is handed the source column to
        say so on screen.
        """
        limit = max(limit, 1)
        where: list[str] = []
        params: list[object] = []
        if vendor_id is not None:
            where.append("vendor_id = %s")
            params.append(vendor_id)
        if severity is not None:
            where.append("severity = %s")
            params.append(severity)
        clause = f"WHERE {' AND '.join(where)}" if where else ""

        total = int(
            self._connect().execute(
                f"SELECT count(*) AS n FROM vendor_change {clause}", params
            ).fetchone()["n"]
        )
        rows = self._connect().execute(
            f"""
            SELECT id, vendor_id, from_version, to_version, kind, operation_id,
                   path_ptr, severity, source, detected_at
              FROM vendor_change {clause}
             ORDER BY detected_at DESC, id
             LIMIT %s OFFSET %s
            """,
            [*params, limit, offset],
        ).fetchall()

        def facet(column: str, ignoring: str) -> dict[str, int]:
            facet_where: list[str] = []
            facet_params: list[object] = []
            if vendor_id is not None and ignoring != "vendor_id":
                facet_where.append("vendor_id = %s")
                facet_params.append(vendor_id)
            if severity is not None and ignoring != "severity":
                facet_where.append("severity = %s")
                facet_params.append(severity)
            facet_clause = f"WHERE {' AND '.join(facet_where)}" if facet_where else ""
            found = self._connect().execute(
                f"SELECT {column} AS key, count(*) AS n FROM vendor_change {facet_clause}"
                f" GROUP BY {column} ORDER BY {column}",
                facet_params,
            ).fetchall()
            return {row["key"]: int(row["n"]) for row in found}

        by_vendor = facet("vendor_id", ignoring="vendor_id")
        by_severity = facet("severity", ignoring="severity")

        # Dashboard G3's source: severity per vendor, which neither single-column facet can
        # answer. A reader wanting "which integration publishes the breaking changes" could
        # otherwise only filter to one vendor and read the severity facet, once per vendor.
        #
        # Both filters ignored, for the same reason each facet ignores its own: a cross-facet
        # narrowed to the reader's current selection would show them the slice they already
        # chose. Bounded by vendors x the five-member severity vocabulary rather than by row
        # count, so it is cheap at any scale -- the argument `open_findings_vendor_counts`
        # carries for staying unbounded.
        crossed = self._connect().execute(
            """
            SELECT vendor_id, severity, count(*) AS n
              FROM vendor_change
             GROUP BY vendor_id, severity
             ORDER BY vendor_id, severity
            """
        ).fetchall()
        by_vendor_severity: dict[str, dict[str, int]] = {}
        for row in crossed:
            by_vendor_severity.setdefault(row["vendor_id"], {})[row["severity"]] = int(row["n"])
        consumed = offset + len(rows)
        return {
            "items": [
                {
                    **dict(row),
                    "detected_at": row["detected_at"].isoformat()
                    if hasattr(row["detected_at"], "isoformat")
                    else row["detected_at"],
                }
                for row in rows
            ],
            "total": total,
            "next_offset": consumed if consumed < total else None,
            "by_vendor": by_vendor,
            "by_severity": by_severity,
            # A pairing absent here was never published, never measured at nought: the grouping
            # returns groups that exist, and a render site must not fill a missing key with a zero.
            "by_vendor_severity": by_vendor_severity,
            "unfiltered_total": sum(by_vendor.values()),
            "vendor_id": vendor_id,
            "severity": severity,
        }

    def vendor_intake_rollup(self) -> dict[str, dict]:
        """Per vendor id, what the graph has ever received: rows, distinct operations, the newest
        `detected_at`, and the `source` values those rows carry.

        Keyed by vendor id and grouped in SQL rather than returned as rows for a caller to fold,
        because the caller is a screen listing one line per adapter and a fold in Python would be
        the same GROUP BY written twice.

        **A vendor absent from this mapping has never delivered, which is not the same as having
        delivered nothing.** Nothing is invented for it here -- it simply is not a key, and
        `sync.dashboard.adapters` is where that absence becomes the null the console renders as
        never-measured.
        """
        rows = self._connect().execute(
            """
            SELECT vendor_id,
                   count(*)                        AS changes,
                   count(DISTINCT operation_id)    AS operations,
                   max(detected_at)                AS last_change_at,
                   array_agg(DISTINCT source)      AS sources
            FROM vendor_change
            GROUP BY vendor_id
            """
        ).fetchall()
        return {
            row["vendor_id"]: {
                "changes": row["changes"],
                "operations": row["operations"],
                "last_change_at": row["last_change_at"].isoformat(),
                "sources": sorted(row["sources"]),
            }
            for row in rows
        }

    def call_sites_by_operation(
        self, vendor_id: str, *, repo_id: str | None = None
    ) -> list[dict]:
        """Per operation of one vendor, how many current call sites name it and how many
        repositories hold them.

        Grouped in SQL rather than folded in Python for the same reason `vendor_intake_rollup`
        is: the caller is a screen rendering one line per operation, and a fold here would be
        the same GROUP BY written twice.

        `retracted_at IS NULL` is the whole difference between exposure and history. A call the
        last index pass stopped finding is not a place this codebase calls the vendor any more,
        and counting it would report exposure a reader cannot act on.

        Ordered by count descending then by id, so the order is total. Ordering on the count
        alone leaves ties to the planner, and a screen whose rows reshuffle between reads for no
        reason a reader can see reads as a bug in the data.
        """
        clauses = ["vendor_id = %s", "retracted_at IS NULL"]
        parameters: list[object] = [vendor_id]
        if repo_id is not None:
            clauses.append("repo_id = %s")
            parameters.append(repo_id)

        rows = self._connect().execute(
            f"""
            SELECT operation_id,
                   count(*)                  AS call_site_count,
                   count(DISTINCT repo_id)   AS repository_count
              FROM call_site
             WHERE {" AND ".join(clauses)}
             GROUP BY operation_id
             ORDER BY count(*) DESC, operation_id
            """,
            parameters,
        ).fetchall()
        return [dict(row) for row in rows]

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

    def open_findings_rung_counts(self, *, repo_id: str | None = None) -> dict[str, int]:
        """Every open finding, tallied by the rung its binding was established at -- one
        `GROUP BY`, never a loop over findings.

        Deliberately unbounded, for the reason `open_findings_vendor_counts` is: a distribution
        derived from a bounded page is the distribution of whichever rows the ordering reached,
        not of the population, and a bounded total is honest where a bounded breakdown presented
        as the breakdown is not. The rung vocabulary is closed and tiny, so this returns at most
        five rows at any scale the bounded total is protecting against.

        Only rungs that occur are returned. The caller fills the rest of the vocabulary in at
        nought, because a rung absent from a dict and a rung at nought are different claims and
        this query cannot make the second one.
        """
        predicate, parameters = _open_findings_predicate(repo_id=repo_id)
        rows = self._connect().execute(
            f"""
            SELECT finding.binding_rung AS rung, count(*) AS n
              FROM finding
              JOIN call_site ON call_site.id = finding.call_site_id
             WHERE {predicate}
             GROUP BY finding.binding_rung
             ORDER BY finding.binding_rung
            """,
            parameters,
        ).fetchall()
        return {row["rung"]: int(row["n"]) for row in rows}

    def _publish(self, event: dict) -> None:
        """Send one event on the shared channel, degrading rather than failing.

        **The write must never fail because the notification did.** `NOTIFY` raises on a payload
        over 8000 bytes, and a repository with deeply nested paths can produce one -- so an event
        that will not fit is replaced by a thin one naming only its kind and scope, and the
        console re-reads. Losing the fat payload costs a round trip; losing the write would cost
        the index run.

        `NOTIFY` is transactional: it fires on commit and not before, so a subscriber never hears
        about a row that was rolled back. That is why this sits inside the writing statement's
        transaction rather than after it.
        """
        payload = json.dumps(event, separators=(",", ":"))
        if len(payload.encode("utf-8")) > _NOTIFY_PAYLOAD_LIMIT:
            payload = json.dumps(
                {"kind": f"{event['kind']}.unsent", "repo_id": event["repo_id"]},
                separators=(",", ":"),
            )
        self._connect().execute("SELECT pg_notify(%s, %s)", (EVENT_CHANNEL, payload))

    @contextmanager
    def subscribe_events(self, repo_id: str) -> Iterator[_EventStream]:
        """Listen for one repository's events on a connection of its own.

        A dedicated connection because `LISTEN` occupies one: a session waiting on notifications
        cannot also serve reads, and sharing the store's connection would block every query behind
        the stream.
        """
        connection = psycopg.connect(self._dsn, autocommit=True, row_factory=dict_row)
        try:
            connection.execute(f"LISTEN {EVENT_CHANNEL}")
            yield _EventStream(connection, repo_id)
        finally:
            connection.close()

    def record_dismissal(
        self, finding_id: str, *, reason: str | None, actor: str, at: datetime | None = None
    ) -> None:
        """Dismiss a finding with a reason, or restore it by passing `reason=None`.

        **This writes a row, never a column**, which is owner decision 45's actual requirement:
        a finding dismissed and later restored has two rows and the current state is the latest.
        A column would overwrite, and the console could then never show that somebody changed
        their mind -- which is the one thing keeping this history buys.

        The reason is refused unless it is in the closed vocabulary. Free text cannot be
        aggregated, and `false_positive` in particular is the only honest source of detector
        accuracy, so a reason spelled three ways is a number nobody can compute. Validation lives
        here rather than in the database because a `CHECK` constraint cannot be added to a
        populated table without a migration this project has no path for yet, and the refusal
        needs to exist now.
        """
        if reason is not None and reason not in DISMISSAL_REASONS:
            raise ValueError(
                f"{reason!r} is not a dismissal reason. The vocabulary is closed -- "
                f"{', '.join(sorted(DISMISSAL_REASONS))} -- because a promise to learn from "
                "dismissals needs a schema that can answer the question, and free text cannot "
                "be aggregated."
            )
        # `at` is the instant the decision was taken, and it is the third member of the natural
        # key. A caller that supplies it gets idempotency: replaying the same write converges
        # rather than recording the decision twice. Omitted, it is now(), so two genuine clicks
        # stay two rows -- the key must not collapse a real change of mind.
        self._connect().execute(
            """
            INSERT INTO finding_dismissal (finding_id, reason, actor, created_at)
                 VALUES (%s, %s, %s, COALESCE(%s, now()))
            ON CONFLICT (finding_id, actor, created_at) DO UPDATE SET reason = EXCLUDED.reason
            """,
            (finding_id, reason, actor, at),
        )

        # Emitted now rather than when a write path lands, because the write path is in flight
        # rather than anticipated -- this is not the dead usage `lib/motion.ts` recorded.
        #
        # A restore is its own kind rather than a dismissal carrying a null reason. They are
        # opposite decisions, and a console told only that *something changed* would have to
        # re-read to learn which. The reason travels on a dismissal because it is the one signal
        # feeding detector accuracy, and a toast that could not say why a row left the list would
        # be reporting a disappearance rather than a decision.
        site = self._connect().execute(
            """
            SELECT call_site.repo_id AS repo_id
              FROM finding
              JOIN call_site ON call_site.id = finding.call_site_id
             WHERE finding.id = %s
            """,
            (finding_id,),
        ).fetchone()
        if site is not None:
            event = {
                "kind": "finding.dismissed" if reason is not None else "finding.restored",
                "repo_id": site["repo_id"],
                "finding_id": finding_id,
                "actor": actor,
            }
            if reason is not None:
                event["reason"] = reason
            self._publish(event)

    def dismissal_state(self, finding_id: str) -> dict:
        """Whether this finding stands dismissed right now, and on whose word.

        The latest row wins. `dismissed` is `False` with a `None` reason for a finding nobody has
        ever touched *and* for one that was dismissed and then restored -- those are the same
        current state, and the difference between them lives in the history rather than here.
        """
        row = self._connect().execute(
            """
            SELECT reason, actor FROM finding_dismissal
             WHERE finding_id = %s
             ORDER BY created_at DESC, id DESC
             LIMIT 1
            """,
            (finding_id,),
        ).fetchone()
        if row is None or row["reason"] is None:
            return {"dismissed": False, "reason": None, "actor": None}
        return {"dismissed": True, "reason": row["reason"], "actor": row["actor"]}

    def dismissal_history_count(self, finding_id: str) -> int:
        """How many times this finding has been dismissed or restored.

        Exposed because the grain is the decision: a caller that wants to know whether anybody
        changed their mind asks this, and a caller that wants the current state asks
        `dismissal_state`. Neither answers the other's question.
        """
        row = self._connect().execute(
            "SELECT count(*) AS n FROM finding_dismissal WHERE finding_id = %s",
            (finding_id,),
        ).fetchone()
        return int(row["n"])

    def dismissal_reason_counts(self) -> dict[str, int]:
        """Currently-dismissed findings, tallied by the reason standing against each.

        Counted over the latest row per finding rather than over every row, because a finding
        dismissed, restored and dismissed again is one dismissal now and not three. Only reasons
        that occur are returned -- a reason absent here and a reason at nought are different
        claims and this query cannot make the second.
        """
        rows = self._connect().execute(
            """
            SELECT latest.reason AS reason, count(*) AS n
              FROM (
                SELECT DISTINCT ON (finding_id) finding_id, reason
                  FROM finding_dismissal
                 ORDER BY finding_id, created_at DESC, id DESC
              ) AS latest
             WHERE latest.reason IS NOT NULL
             GROUP BY latest.reason
             ORDER BY latest.reason
            """
        ).fetchall()
        return {row["reason"]: int(row["n"]) for row in rows}

    def observed_edges_for_repository(self, repo_id: str) -> list[dict]:
        """One row per (vendor, operation, rung) this repository's traffic actually named.

        The telemetry rung as *edges* rather than as rows: the canvas draws one line per operation
        the traffic reached, and `observed_call`'s grain is one row per unit of work, so drawing
        it unaggregated would put a thousand identical lines between two nodes.

        **An uncorrelated span is excluded here and counted by `off_path_counts` instead.** It
        names no operation, so there is no node to draw an edge to; folding it into `observed`
        would claim a correlation nothing made, and dropping it entirely would understate what
        reached the vendor. It is off the path rather than absent, and off-path is a place on this
        screen.
        """
        rows = self._connect().execute(
            """
            SELECT vendor_id,
                   operation_id,
                   binding_rung,
                   count(*)            AS calls
              FROM observed_call
             WHERE repo_id = %s AND operation_id <> ''
             GROUP BY vendor_id, operation_id, binding_rung
             ORDER BY vendor_id, operation_id, binding_rung
            """,
            (repo_id,),
        ).fetchall()
        return [
            {
                "vendor_id": row["vendor_id"],
                "operation_id": row["operation_id"],
                "binding_rung": row["binding_rung"],
                "calls": int(row["calls"]),
            }
            for row in rows
        ]

    def off_path_counts(self, repo_id: str) -> dict[str, int]:
        """What this repository holds that no edge on the canvas can carry.

        `unresolved` is a span that correlated to no operation. `unattributed` is a finding whose
        rung predates the column that would have recorded one -- a value no binder emits and which
        `BindingRung` deliberately excludes, so it cannot be drawn as a rung.

        Both are returned as numbers rather than omitted when nought, because the tables were read
        and held none, and that is a measurement. The never-indexed case is the one that answers
        `None`, and it answers from `repository_indexed_at`.
        """
        unresolved = self._connect().execute(
            """
            SELECT count(*) AS n FROM observed_call
             WHERE repo_id = %s AND (operation_id = '' OR binding_rung = 'unresolved')
            """,
            (repo_id,),
        ).fetchone()
        unattributed = self._connect().execute(
            """
            SELECT count(*) AS n
              FROM finding
              JOIN call_site ON call_site.id = finding.call_site_id
             WHERE call_site.repo_id = %s AND finding.binding_rung = 'unattributed'
            """,
            (repo_id,),
        ).fetchone()
        return {"unresolved": int(unresolved["n"]), "unattributed": int(unattributed["n"])}

    def repository_indexed_at(self, repo_id: str) -> datetime | None:
        """When the index last wrote a call site for this repository, or `None` if it never has.

        **Retracted rows count.** A repository whose calls have all since gone was still indexed,
        and answering `None` there would say the index never ran -- a different and false claim.

        `None` is honestly ambiguous and the screen must say so rather than resolve it: no call
        site row has ever existed here, which is either an index that never ran or one that ran
        and found no vendor call. Nothing records an index attempt, only its result, so this
        cannot tell them apart -- the same limit `AdapterRow.last_change_at` carries for intake.
        """
        row = self._connect().execute(
            "SELECT max(indexed_at) AS at FROM call_site WHERE repo_id = %s",
            (repo_id,),
        ).fetchone()
        return row["at"]

    def findings_recorded_by_day_and_severity(
        self, *, repo_id: str | None = None
    ) -> list[dict]:
        """Every finding the graph holds, tallied by the day it was recorded and its severity.

        **Not filtered to open.** A time series of only still-open findings rewrites its own
        history as work gets done -- yesterday's bar shrinks every time somebody merges a patch --
        so this counts what DETECT produced and `findings_still_open_count` reports separately how
        much of it remains. Nor is a retracted call site excluded: the finding was genuinely
        produced when it was produced, and dropping it would edit the past to match the present.

        `created_at` is stable across re-runs because `upsert_finding` is `ON CONFLICT DO
        NOTHING`, which is what makes a date on this table mean anything at all. It is the day
        Sync first recorded the claim, never the day the vendor published the change behind it.

        Grouped in SQL. The join to `call_site` exists only for the repository scope and is
        omitted from neither branch, because a fleet-wide series under a repository's heading is
        the false claim the scoping exists to remove.
        """
        clauses: list[str] = []
        parameters: list[object] = []
        if repo_id is not None:
            clauses.append("call_site.repo_id = %s")
            parameters.append(repo_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        rows = self._connect().execute(
            f"""
            SELECT (finding.created_at AT TIME ZONE 'UTC')::date AS day,
                   finding.severity                              AS severity,
                   count(*)                                      AS n
              FROM finding
              JOIN call_site ON call_site.id = finding.call_site_id
             {where}
             GROUP BY 1, 2
             ORDER BY 1, 2
            """,
            parameters,
        ).fetchall()
        return [
            {"day": row["day"].isoformat(), "severity": row["severity"], "n": int(row["n"])}
            for row in rows
        ]

    def findings_rung_counts(self, *, repo_id: str | None = None) -> dict[str, int]:
        """Every finding the graph holds, tallied by the rung it rests on.

        The counterpart to `open_findings_rung_counts` over the same unfiltered set the day-and-
        severity tally uses, so the rung composition beside a time series describes the findings
        that series drew and not a different population.

        Only rungs that occur are returned; a rung absent here and a rung at nought are different
        claims and this query cannot make the second.
        """
        clauses: list[str] = []
        parameters: list[object] = []
        if repo_id is not None:
            clauses.append("call_site.repo_id = %s")
            parameters.append(repo_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        rows = self._connect().execute(
            f"""
            SELECT finding.binding_rung AS rung, count(*) AS n
              FROM finding
              JOIN call_site ON call_site.id = finding.call_site_id
             {where}
             GROUP BY finding.binding_rung
             ORDER BY finding.binding_rung
            """,
            parameters,
        ).fetchall()
        return {row["rung"]: int(row["n"]) for row in rows}

    def findings_still_open_count(self, *, repo_id: str | None = None) -> int:
        """How many of the findings the graph holds are still open.

        Reported beside the series rather than folded into it: the series says what Sync produced,
        this says how much of it is outstanding, and a reader needs both to avoid reading either
        as the other.
        """
        clauses: list[str] = ["finding.status = 'open'"]
        parameters: list[object] = []
        if repo_id is not None:
            clauses.append("call_site.repo_id = %s")
            parameters.append(repo_id)

        row = self._connect().execute(
            f"""
            SELECT count(*) AS n
              FROM finding
              JOIN call_site ON call_site.id = finding.call_site_id
             WHERE {' AND '.join(clauses)}
            """,
            parameters,
        ).fetchone()
        return int(row["n"])

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

    def open_findings_repository_summaries(self) -> list[dict]:
        """Every open finding and its attached vendors, grouped by repository across the fleet.

        Answers in a single query what the fleet screen previously issued N+1 scoped queries for
        (B148): for each repository known to the index, returns its total open findings count and
        the list of distinct vendor IDs attached to those open findings.
        """
        rows = self._connect().execute(
            """
            SELECT call_site.repo_id AS repo_id,
                   call_site.vendor_id AS vendor_id,
                   count(finding.id) AS n
              FROM call_site
              LEFT JOIN finding ON finding.call_site_id = call_site.id AND finding.status = 'open'
             WHERE call_site.retracted_at IS NULL
             GROUP BY call_site.repo_id, call_site.vendor_id
             ORDER BY call_site.repo_id, call_site.vendor_id
            """
        ).fetchall()

        by_repo: dict[str, dict] = {}
        for row in rows:
            repo_id = row["repo_id"]
            if repo_id not in by_repo:
                by_repo[repo_id] = {"repo_id": repo_id, "open_finding_count": 0, "vendors": []}
            n = row["n"]
            if n > 0:
                by_repo[repo_id]["open_finding_count"] += n
                if row["vendor_id"] not in by_repo[repo_id]["vendors"]:
                    by_repo[repo_id]["vendors"].append(row["vendor_id"])

        return sorted(by_repo.values(), key=lambda r: r["repo_id"])

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
        "abandon_reason_code",
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

    def migration_outcomes(self, *, repo_id: str | None = None) -> list[MigrationOutcome]:
        """Every production attempt, in corpus order.

        Filters `is_rehearsal` out rather than handing the dimension to every caller: a rehearsal
        row belongs in the table -- it still cost a repair attempt worth recording -- but nowhere
        a corpus-wide rate (`merge_rate`, `counts.pull_requests_opened`, ...) is computed. See the
        table's grain comment.

        `repo_id` narrows to one repository's findings (B149).
        """
        if repo_id is None:
            rows = self._connect().execute(
                "SELECT * FROM migration_outcome WHERE NOT is_rehearsal ORDER BY finding_id, attempt_index"
            ).fetchall()
        else:
            rows = self._connect().execute(
                """
                SELECT migration_outcome.*
                  FROM migration_outcome
                  JOIN finding ON finding.id = migration_outcome.finding_id
                  JOIN call_site ON call_site.id = finding.call_site_id
                 WHERE NOT migration_outcome.is_rehearsal AND call_site.repo_id = %s
                 ORDER BY migration_outcome.finding_id, migration_outcome.attempt_index
                """,
                [repo_id],
            ).fetchall()
        return [MigrationOutcome(**row) for row in rows]

    def finding_repo_ids(self) -> dict[str, str]:
        """Map every finding_id to its call_site.repo_id (B149)."""
        rows = self._connect().execute(
            """
            SELECT finding.id AS finding_id, call_site.repo_id AS repo_id
              FROM finding
              JOIN call_site ON call_site.id = finding.call_site_id
            """
        ).fetchall()
        return {row["finding_id"]: row["repo_id"] for row in rows}

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
        """`abandon_reason_code`, tallied per (`change_kind`, `tier`), over abandoned attempts
        only.

        Groups on the closed vocabulary `sync.remediate.state.AbandonReasonCode` declares, not
        on `abandon_reason`'s free text (B128): two runs that abandoned for the same reason
        group together here even when their prose reads differently, which grouping on the
        prose could never do -- "how often did tier 2 abandon because the compiler never
        recovered" becomes `abandon_reason_code = 'static_verify_exhausted'` rather than a
        substring match. `abandon_reason` stays free text and stays on the row
        (`GraphStore.migration_outcomes`); this aggregate is not where it is deleted.

        `remediate-stage.md` requires `abandon_reason` non-null on an abandoned run, and
        `make_abandon` writes `abandon_reason_code` beside it on every abandonment (falling
        back to `'unclassified'` rather than guessing), so a null code here is a row recorded
        before this column existed, not an expected case -- reported as `None` rather than
        folded into `'unclassified'`, which is a real member of the vocabulary and a different
        fact.
        """
        rows = self._connect().execute(
            """
            SELECT change_kind, tier, abandon_reason_code, count(*) AS n
              FROM migration_outcome
             WHERE NOT is_rehearsal AND terminal_status = 'abandoned'
             GROUP BY change_kind, tier, abandon_reason_code
             ORDER BY change_kind, tier
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def corpus_health_aggregates(self):
        """Compute the benchmark quality axes directly in Postgres via SQL aggregation.

        Avoids O(n) table scans in Python over the append-only `migration_outcome` table (B167).
        """
        from sync.benchmark.axes import Axis, BenchmarkAxes, Counts

        counts_row = self._connect().execute(
            """
            SELECT
                count(*) AS attempts,
                count(DISTINCT finding_id) AS findings,
                count(*) FILTER (WHERE NOT is_rehearsal AND pr_number IS NOT NULL) AS pull_requests_opened,
                count(DISTINCT finding_id) FILTER (WHERE NOT is_rehearsal AND pr_number IS NOT NULL AND pr_merged = true) AS pull_requests_merged,
                count(DISTINCT finding_id) FILTER (WHERE NOT is_rehearsal AND terminal_status = 'abandoned') AS findings_abandoned,
                count(*) FILTER (WHERE NOT is_rehearsal) AS production_attempts,
                count(*) FILTER (WHERE is_rehearsal) AS rehearsal_attempts
            FROM migration_outcome
            """
        ).fetchone()

        counts = Counts(
            attempts=(counts_row["attempts"] if counts_row else 0) or 0,
            findings=(counts_row["findings"] if counts_row else 0) or 0,
            pull_requests_opened=(counts_row["pull_requests_opened"] if counts_row else 0) or 0,
            pull_requests_merged=(counts_row["pull_requests_merged"] if counts_row else 0) or 0,
            findings_abandoned=(counts_row["findings_abandoned"] if counts_row else 0) or 0,
            production_attempts=(counts_row["production_attempts"] if counts_row else 0) or 0,
            rehearsal_attempts=(counts_row["rehearsal_attempts"] if counts_row else 0) or 0,
        )

        kind_rows = self._connect().execute(
            """
            SELECT
                change_kind,
                count(*) AS total,
                count(*) FILTER (WHERE pr_merged = true) AS merged,
                bool_or(is_rehearsal) AS has_rehearsal,
                bool_or(NOT is_rehearsal) AS has_prod
            FROM migration_outcome
            WHERE NOT is_rehearsal AND pr_number IS NOT NULL AND pr_merged IS NOT NULL
            GROUP BY change_kind
            """
        ).fetchall()
        kind_rates = {}
        for r in kind_rows:
            prov = "rehearsal" if r["has_rehearsal"] and not r["has_prod"] else ("mixed" if r["has_rehearsal"] and r["has_prod"] else "production")
            kind_rates[r["change_kind"]] = Axis.over(r["merged"], r["total"], provenance=prov)

        tier_rows = self._connect().execute(
            """
            SELECT
                tier,
                count(*) AS total,
                count(*) FILTER (WHERE pr_merged = true) AS merged,
                bool_or(is_rehearsal) AS has_rehearsal,
                bool_or(NOT is_rehearsal) AS has_prod
            FROM migration_outcome
            WHERE NOT is_rehearsal AND pr_number IS NOT NULL AND pr_merged IS NOT NULL
            GROUP BY tier
            """
        ).fetchall()
        tier_rates = {}
        for r in tier_rows:
            prov = "rehearsal" if r["has_rehearsal"] and not r["has_prod"] else ("mixed" if r["has_rehearsal"] and r["has_prod"] else "production")
            tier_rates[r["tier"]] = Axis.over(r["merged"], r["total"], provenance=prov)

        t0_row = self._connect().execute(
            """
            WITH tier_zero_findings AS (
                SELECT
                    finding_id,
                    bool_or(tier > 0) AS any_fallback,
                    bool_or(tier = 0 AND static_verify_passed = true) AS any_t0_passed,
                    bool_or(is_rehearsal) AS has_rehearsal,
                    bool_or(NOT is_rehearsal) AS has_prod
                FROM migration_outcome
                WHERE NOT is_rehearsal
                GROUP BY finding_id
                HAVING bool_or(tier = 0)
            )
            SELECT
                count(*) AS denominator,
                count(*) FILTER (WHERE NOT any_fallback AND any_t0_passed) AS numerator,
                bool_or(has_rehearsal) AS has_rehearsal,
                bool_or(has_prod) AS has_prod
            FROM tier_zero_findings
            """
        ).fetchone()
        if t0_row and t0_row["denominator"] and t0_row["denominator"] > 0:
            prov = "rehearsal" if t0_row["has_rehearsal"] and not t0_row["has_prod"] else ("mixed" if t0_row["has_rehearsal"] and t0_row["has_prod"] else "production")
            routing_acc = Axis.over(t0_row["numerator"], t0_row["denominator"], provenance=prov)
        else:
            routing_acc = Axis.over(0, 0, provenance="unmeasured")

        merged_row = self._connect().execute(
            """
            WITH merged_findings AS (
                SELECT DISTINCT finding_id
                FROM migration_outcome
                WHERE NOT is_rehearsal AND pr_number IS NOT NULL AND pr_merged = true
            )
            SELECT
                count(DISTINCT m.finding_id) AS denominator,
                coalesce(sum(coalesce(m.input_tokens, 0) + coalesce(m.output_tokens, 0)), 0) AS total_tokens,
                coalesce(sum(m.wall_ms), 0) AS total_wall_ms,
                bool_or(m.is_rehearsal) AS has_rehearsal,
                bool_or(NOT m.is_rehearsal) AS has_prod
            FROM migration_outcome m
            JOIN merged_findings f ON m.finding_id = f.finding_id
            WHERE NOT m.is_rehearsal
            """
        ).fetchone()

        if merged_row and merged_row["denominator"] and merged_row["denominator"] > 0:
            prov = "rehearsal" if merged_row["has_rehearsal"] and not merged_row["has_prod"] else ("mixed" if merged_row["has_rehearsal"] and merged_row["has_prod"] else "production")
            tokens_axis = Axis.over(int(merged_row["total_tokens"]), merged_row["denominator"], provenance=prov)
            wall_ms_axis = Axis.over(int(merged_row["total_wall_ms"]), merged_row["denominator"], provenance=prov)
        else:
            tokens_axis = Axis.over(0, 0, provenance="unmeasured")
            wall_ms_axis = Axis.over(0, 0, provenance="unmeasured")

        return BenchmarkAxes(
            merge_rate_by_change_kind=kind_rates,
            merge_rate_by_tier=tier_rates,
            routing_accuracy=routing_acc,
            tokens_per_merged_patch=tokens_axis,
            wall_ms_per_merged_patch=wall_ms_axis,
            counts=counts,
        )

    def repo_id_for_finding(self, finding_id: str) -> str | None:
        """The repository ID of the call site a finding was raised against, or None."""
        row = self._connect().execute(
            """
            SELECT cs.repo_id
              FROM finding f
              JOIN call_site cs ON f.call_site_id = cs.id
             WHERE f.id = %s
            """,
            (finding_id,),
        ).fetchone()
        return row["repo_id"] if row else None

    def repo_ids_for_findings(self, finding_ids: Sequence[str]) -> dict[str, str]:
        """Map each finding_id to its call site's repo_id."""
        if not finding_ids:
            return {}
        rows = self._connect().execute(
            """
            SELECT f.id AS finding_id, cs.repo_id
              FROM finding f
              JOIN call_site cs ON f.call_site_id = cs.id
             WHERE f.id = ANY(%s)
            """,
            (list(finding_ids),),
        ).fetchall()
        return {row["finding_id"]: row["repo_id"] for row in rows}

    def pending_merge_outcomes(self) -> list[MigrationOutcome]:
        """Every production attempt with an open pull request awaiting merge decision."""
        rows = self._connect().execute(
            """
            SELECT *
              FROM migration_outcome
             WHERE NOT is_rehearsal
               AND pr_number IS NOT NULL
               AND pr_merged IS NULL
             ORDER BY finding_id, attempt_index
            """
        ).fetchall()
        return [MigrationOutcome(**row) for row in rows]

    def set_merge_outcome(
        self,
        finding_id: str,
        attempt_index: int,
        pr_number: int | None = None,
        pr_merged: bool | None = None,
        human_edits_before_merge: int | None = None,
        pr_merged_at: datetime | str | None = None,
    ) -> None:
        """Fill in what only arrives days later, by webhook or polling.

        Merge outcome is the one measurement that tests the product claim, and a column that
        silently stays null destroys it. The update path exists from the first row rather than
        being added once someone notices the column is empty.

        `AND NOT is_rehearsal`: a real GitHub delivery describes a real pull request, which only
        a production run can have opened. Without the filter this would also match a rehearsal
        row sharing the same finding and attempt index, crediting a merge to an attempt that
        never reached a forge.
        """
        merged_at_dt: datetime | None = None
        if isinstance(pr_merged_at, str):
            try:
                merged_at_dt = datetime.fromisoformat(pr_merged_at.replace("Z", "+00:00"))
            except ValueError:
                merged_at_dt = None
        elif isinstance(pr_merged_at, datetime):
            merged_at_dt = pr_merged_at

        self._connect().execute(
            """
            UPDATE migration_outcome
               SET pr_number = COALESCE(%s, pr_number),
                   pr_merged = COALESCE(%s, pr_merged),
                   pr_merged_at = CASE
                       WHEN %s IS FALSE THEN NULL
                       WHEN %s::timestamptz IS NOT NULL THEN %s::timestamptz
                       WHEN %s IS TRUE THEN now()
                       ELSE pr_merged_at
                   END,
                   human_edits_before_merge = COALESCE(%s, human_edits_before_merge)
             WHERE finding_id = %s AND attempt_index = %s AND NOT is_rehearsal
            """,
            (
                pr_number,
                pr_merged,
                pr_merged,
                merged_at_dt,
                merged_at_dt,
                pr_merged,
                human_edits_before_merge,
                finding_id,
                attempt_index,
            ),
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
            INSERT INTO repo_context (repo_id, body, source, telemetry_attached_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (repo_id) DO UPDATE SET
                body = EXCLUDED.body,
                source = EXCLUDED.source,
                updated_at = now(),
                telemetry_attached_at = COALESCE(EXCLUDED.telemetry_attached_at, repo_context.telemetry_attached_at)
            """,
            [context.repo_id, context.body, context.source, context.telemetry_attached_at],
        )

    def mark_telemetry_attached(self, repo_id: str, attached_at: datetime | None = None) -> None:
        """Record that telemetry has been attached for a repository (B157)."""
        ts = attached_at or datetime.now(timezone.utc)
        self._connect().execute(
            """
            INSERT INTO repo_context (repo_id, body, source, telemetry_attached_at)
            VALUES (%s, '', 'telemetry', %s)
            ON CONFLICT (repo_id) DO UPDATE SET
                telemetry_attached_at = EXCLUDED.telemetry_attached_at,
                updated_at = now()
            """,
            [repo_id, ts],
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

    def repo_settings(self, repo_id: str) -> RepoSettings:
        """One repository's automation and merge settings, or default settings if none recorded.

        Default settings:
        `merge_policy`: 'when_checks_pass'
        `merge_method`: 'squash'
        `base_branch`: 'main'
        """
        row = self._connect().execute(
            "SELECT * FROM repo_settings WHERE repo_id = %s",
            [repo_id],
        ).fetchone()
        if row is None:
            return RepoSettings(repo_id=repo_id)
        d = dict(row)
        if isinstance(d.get("merge_policy_refusals"), str):
            d["merge_policy_refusals"] = json.loads(d["merge_policy_refusals"])
        return RepoSettings(**d)

    def upsert_repo_settings(self, settings: RepoSettings) -> None:
        """Persist automation and merge settings for one repository.

        Enforces system invariants: immediate merge without verification is refused.
        """
        if settings.merge_policy not in ALLOWED_MERGE_POLICIES:
            refusal = settings.merge_policy_refusals.get(
                settings.merge_policy,
                "Refused: violates invariant 'nothing reaches a pull request unverified'",
            )
            raise ValueError(
                f"Invalid or refused merge_policy '{settings.merge_policy}': {refusal}. "
                f"Permitted policies: {ALLOWED_MERGE_POLICIES}"
            )
        if settings.merge_method not in ALLOWED_MERGE_METHODS:
            raise ValueError(
                f"Invalid merge_method '{settings.merge_method}'. Permitted methods: {ALLOWED_MERGE_METHODS}"
            )
        refusals_json = json.dumps(settings.merge_policy_refusals)
        self._connect().execute(
            """
            INSERT INTO repo_settings (repo_id, merge_policy, merge_method, base_branch, remote_url, merge_policy_refusals, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, now())
            ON CONFLICT (repo_id) DO UPDATE SET
               merge_policy = EXCLUDED.merge_policy,
               merge_method = EXCLUDED.merge_method,
               base_branch = EXCLUDED.base_branch,
               remote_url = EXCLUDED.remote_url,
               merge_policy_refusals = EXCLUDED.merge_policy_refusals,
               updated_at = now()
            """,
            [
                settings.repo_id,
                settings.merge_policy,
                settings.merge_method,
                settings.base_branch,
                settings.remote_url,
                refusals_json,
            ],
        )

    def upsert_codebase_facts(self, repo_id: str, facts: dict) -> None:
        """Replace one repository's technical census with the pass that just ran."""
        self._connect().execute(
            """
            INSERT INTO codebase_facts (repo_id, facts, computed_at)
            VALUES (%s, %s, now())
            ON CONFLICT (repo_id) DO UPDATE SET
               facts = EXCLUDED.facts,
               computed_at = now()
            """,
            [repo_id, json.dumps(facts)],
        )

    def codebase_facts(self, repo_id: str) -> dict | None:
        """The newest census for one repository, or None when no index pass has written one."""
        row = self._connect().execute(
            "SELECT facts, computed_at FROM codebase_facts WHERE repo_id = %s",
            [repo_id],
        ).fetchone()
        if row is None:
            return None
        facts = row["facts"] if isinstance(row["facts"], dict) else json.loads(row["facts"])
        return {**facts, "computed_at": row["computed_at"].isoformat()}

    def begin_run_heartbeat(self, thread_id: str, *, expire_after_secs: int = 90) -> None:
        """Open (or re-open, on resume) the heartbeat row for one run.

        A resumed thread reuses its row: the previous generation's `stopped_at` or
        `expired_at` describes a process that is over, and carrying either into a run that is
        executing right now would report the new process through the old one's death.
        """
        self._connect().execute(
            """
            INSERT INTO run_heartbeat (thread_id, expire_after_secs)
            VALUES (%s, %s)
            ON CONFLICT (thread_id) DO UPDATE SET
               started_at = now(),
               last_heartbeat_at = now(),
               expire_after_secs = EXCLUDED.expire_after_secs,
               stopped_at = NULL,
               expired_at = NULL
            """,
            [thread_id, expire_after_secs],
        )

    def heartbeat_run(self, thread_id: str) -> None:
        """The tick. Idempotent and tiny on purpose: it runs on a timer from a worker thread."""
        self._connect().execute(
            "UPDATE run_heartbeat SET last_heartbeat_at = now() WHERE thread_id = %s",
            [thread_id],
        )

    def stop_run_heartbeat(self, thread_id: str) -> None:
        """The clean exit, whatever the outcome -- an abandoned run still exited cleanly."""
        self._connect().execute(
            "UPDATE run_heartbeat SET stopped_at = now() WHERE thread_id = %s",
            [thread_id],
        )

    def expire_stale_heartbeats(self) -> list[str]:
        """Record EXPIRED for every run whose heartbeats stopped with no clean exit.

        Read-triggered rather than a daemon: this deployment is local-first and owns no
        supervisor, so the sweep runs when runs are read -- which is exactly when the answer
        is about to be shown to somebody. The transition is recorded, not computed per read:
        `expired_at` is written once and the moment it happened survives.
        """
        rows = self._connect().execute(
            """
            UPDATE run_heartbeat
               SET expired_at = now()
             WHERE stopped_at IS NULL
               AND expired_at IS NULL
               AND last_heartbeat_at < now() - make_interval(secs => expire_after_secs)
            RETURNING thread_id
            """
        ).fetchall()
        return [row["thread_id"] for row in rows]

    def run_heartbeats(self, thread_ids: list[str]) -> dict[str, dict]:
        """The heartbeat rows for these threads, keyed by thread id. Absent is a fact."""
        if not thread_ids:
            return {}
        rows = self._connect().execute(
            """
            SELECT thread_id, started_at, last_heartbeat_at, stopped_at, expired_at
              FROM run_heartbeat
             WHERE thread_id = ANY(%s)
            """,
            [thread_ids],
        ).fetchall()
        return {row["thread_id"]: dict(row) for row in rows}

    def record_intake_attempt(self, attempt: IntakeAttempt) -> str:
        """Persist one intake attempt record.

        Idempotent: updates existing attempt if the natural key matches.
        """
        attempt_id = _stable_id(
            attempt.vendor_id,
            attempt.attempted_at.isoformat(),
            attempt.from_version or "",
            attempt.to_version or "",
        )
        self._connect().execute(
            """
            INSERT INTO intake_attempt (
                id, vendor_id, attempted_at, outcome, reason_code, detail,
                changes_count, from_version, to_version, source, duration_ms
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE
               SET outcome = EXCLUDED.outcome,
                   reason_code = EXCLUDED.reason_code,
                   detail = EXCLUDED.detail,
                   changes_count = EXCLUDED.changes_count,
                   source = EXCLUDED.source,
                   duration_ms = EXCLUDED.duration_ms
            """,
            (
                attempt_id,
                attempt.vendor_id,
                attempt.attempted_at,
                attempt.outcome,
                attempt.reason_code,
                attempt.detail,
                attempt.changes_count,
                attempt.from_version,
                attempt.to_version,
                attempt.source,
                attempt.duration_ms,
            ),
        )
        return attempt_id

    def intake_attempts(
        self, vendor_id: str | None = None, limit: int = 100
    ) -> list[IntakeAttempt]:
        """Query recent intake attempts, optionally filtered by vendor_id."""
        if vendor_id is not None:
            rows = self._connect().execute(
                """
                SELECT vendor_id, attempted_at, outcome, reason_code, detail,
                       changes_count, from_version, to_version, source, duration_ms
                  FROM intake_attempt
                 WHERE vendor_id = %s
                 ORDER BY attempted_at DESC
                 LIMIT %s
                """,
                (vendor_id, limit),
            ).fetchall()
        else:
            rows = self._connect().execute(
                """
                SELECT vendor_id, attempted_at, outcome, reason_code, detail,
                       changes_count, from_version, to_version, source, duration_ms
                  FROM intake_attempt
                 ORDER BY attempted_at DESC
                 LIMIT %s
                """,
                (limit,),
            ).fetchall()
        return [IntakeAttempt(**dict(row)) for row in rows]

    def bound_repo_vendor_pairs(self) -> list[tuple[str, str]]:
        """Every (repo_id, vendor_id) pair the graph currently binds, sorted.

        Current only -- `retracted_at IS NULL` -- because this is what seeds
        `watch_subscription`, and a binding a pass stopped finding is not a reason to
        subscribe. Existing subscriptions are unaffected either way: the seed never deletes.
        """
        rows = self._connect().execute(
            """
            SELECT DISTINCT repo_id, vendor_id
              FROM call_site
             WHERE retracted_at IS NULL
             ORDER BY repo_id, vendor_id
            """
        ).fetchall()
        return [(row["repo_id"], row["vendor_id"]) for row in rows]

    def seed_watch_subscription(self, repo_id: str, vendor_id: str, *, cadence: str) -> bool:
        """Subscribe one bound pair, touching nothing an operator may have edited.

        DO NOTHING rather than DO UPDATE, and that is the contract rather than a shortcut:
        `paused`, `cadence` and `policy` are the operator's overrides, and a derivation that
        updated them would revert every override on every tick. Returns whether a row was
        created, which is what the tick prints.
        """
        cursor = self._connect().execute(
            """
            INSERT INTO watch_subscription (repo_id, vendor_id, cadence)
            VALUES (%s, %s, %s)
            ON CONFLICT (repo_id, vendor_id) DO NOTHING
            """,
            [repo_id, vendor_id, cadence],
        )
        return cursor.rowcount == 1

    def watch_subscriptions(
        self, *, repo_id: str | None = None, vendor_id: str | None = None
    ) -> list[dict]:
        """The subscriptions, optionally scoped, sorted so a tick's output is stable."""
        clauses, params = [], []
        if repo_id is not None:
            clauses.append("repo_id = %s")
            params.append(repo_id)
        if vendor_id is not None:
            clauses.append("vendor_id = %s")
            params.append(vendor_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._connect().execute(
            f"SELECT * FROM watch_subscription {where} ORDER BY repo_id, vendor_id",
            params,
        ).fetchall()
        return [dict(row) for row in rows]

    def vendor_cursor(self, vendor_id: str) -> dict | None:
        """Where the watch loop's cursor sits for one vendor, or None before the first probe."""
        row = self._connect().execute(
            "SELECT * FROM vendor_cursor WHERE vendor_id = %s", [vendor_id]
        ).fetchone()
        return dict(row) if row is not None else None

    def advance_vendor_cursor(
        self,
        vendor_id: str,
        *,
        checked_at: datetime,
        last_seen_version: str | None = None,
        moved: bool = False,
    ) -> None:
        """Record one probe: always the check, the version and movement only when carried.

        Both COALESCEs run in the same direction -- toward keeping what is known. A touch
        passes no version and must not erase where the cursor sits, and a probe that found
        nothing must not un-record the last movement. Callers that just wrote scan rows call
        this inside the same `transaction()` block, which is what the schema's grain comment
        promises.
        """
        self._connect().execute(
            """
            INSERT INTO vendor_cursor (vendor_id, last_seen_version, last_checked_at, last_moved_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (vendor_id) DO UPDATE SET
                last_seen_version = COALESCE(EXCLUDED.last_seen_version, vendor_cursor.last_seen_version),
                last_checked_at = EXCLUDED.last_checked_at,
                last_moved_at = COALESCE(EXCLUDED.last_moved_at, vendor_cursor.last_moved_at)
            """,
            [vendor_id, last_seen_version, checked_at, checked_at if moved else None],
        )

