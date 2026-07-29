"""Persistence and queries for the API Dependency Graph."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from importlib import resources

import psycopg
from psycopg.rows import dict_row

from sync.core import CallSite, Finding, FindingStatus, MigrationOutcome, VendorChange
from sync.core.models import ObservedCall, ObservedShape


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


class GraphStore:
    """One store instance owns one connection, opened on first use.

    A per-call connection costs a TCP handshake, an authentication round trip
    and a teardown for every row: an ingest of a few thousand vendor changes
    spends most of its time connecting. The connection is never reopened once
    it breaks -- a run whose database went away has no correct way to continue,
    and reconnecting inside `transaction()` would silently turn one atomic
    ingest into a partially committed one.

    A store is meant for one caller at a time. psycopg serialises statements on
    a shared connection, so concurrent callers corrupt nothing -- but they share
    a transaction as well as a connection, which is a sharper edge than it
    sounds and is spelled out on `transaction()`. Give each concurrent unit of
    work its own store.
    """

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._conn: psycopg.Connection | None = None

    def _connect(self) -> psycopg.Connection:
        if self._conn is None:
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
        with self._connect().transaction():
            yield

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

        **What this does not express.** Added columns, and nothing else. It cannot rename a
        column, change a type, add or drop a constraint, or backfill a value, and it does not
        restore a table-level `UNIQUE` that a dropped column took with it. Adding a `NOT NULL`
        column to a table that already has rows fails, correctly -- there is no value to give
        them, and inventing one is a backfill decision rather than a schema application. Any of
        those needs a real migration: a version table, an ordered history and a workflow. Not
        built, because this is a single-tenant local pipeline whose only databases are a
        developer's and a test run's, and the hosted control plane that makes migration history
        load-bearing is M4 and unbuilt. A framework bought now is carried for a year before it
        is needed. When the first rename or backfill arrives, this is the thing to replace
        rather than the thing to extend -- it converges forward and keeps no history to
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
        passes = [creates, _add_missing_columns(creates), rest] if existing else [creates, rest]
        for statements_in_pass in passes:
            connection.execute(";\n".join(statements_in_pass))

    def _schema_tables(self) -> list[str]:
        ddl = resources.files("sync.graph").joinpath("schema.sql").read_text(encoding="utf-8")
        return [
            _table_name(statement)
            for statement in _statements(ddl)
            if statement.upper().startswith("CREATE TABLE")
        ]

    def truncate_all(self) -> None:
        """Empty every table the schema declares.

        The list used to be written out here, and it was right -- but it was right the way
        `schema.sql` was complete: by somebody remembering. A table added later would have been
        missed by it exactly as a column added later was missed by `apply_schema`, and the
        consequence is quieter than a failed insert. Rows from one run survive into the next and
        the failure surfaces somewhere with no obvious connection to this method.
        """
        self._connect().execute(f"TRUNCATE {', '.join(self._schema_tables())} CASCADE")

    def upsert_call_site(self, site: CallSite) -> str:
        # line and col are part of identity, not just data: two distinct call sites
        # in the same file can share a symbol (the same SDK method called twice), and
        # without a position component they'd hash to one id and silently collapse.
        # This means a call site that merely shifts down the file (no other content
        # change) becomes a new row rather than an update to the old one. That is
        # safe at M0 only because cli.py truncates the whole graph at the start of
        # every run, so no stale row ever survives to be orphaned; M2's incremental
        # indexing will need a different identity scheme that tolerates line drift.
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
                indexed_at = now()
            """,
            (
                site_id, site.repo_id, site.path, site.line, site.col, site.vendor_id,
                site.operation_id, site.symbol, site.args_keys, site.response_fields_read,
                site.sdk_version, site.content_hash, site.loop_depth,
            ),
        )
        return site_id

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
                                 rationale, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                finding_id, finding.detector, finding.claim, finding.call_site_id,
                finding.vendor_change_id, finding.severity, finding.rationale, finding.status,
            ),
        )
        return finding_id

    def call_sites_for_operation(self, vendor_id: str, operation_id: str) -> list[CallSite]:
        rows = self._connect().execute(
            "SELECT * FROM call_site WHERE vendor_id = %s AND operation_id = %s ORDER BY path, line",
            (vendor_id, operation_id),
        ).fetchall()
        return [CallSite(**row) for row in rows]

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
        """
        rows = self._connect().execute(
            """
            SELECT vendor_id, count(*) AS sites
              FROM call_site
             WHERE repo_id = %s
             GROUP BY vendor_id
            """,
            (repo_id,),
        ).fetchall()
        return {row["vendor_id"]: row["sites"] for row in rows}

    def get_call_site(self, call_site_id: str) -> CallSite:
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

    def open_findings(self) -> list[Finding]:
        rows = self._connect().execute(
            "SELECT * FROM finding WHERE status = 'open' ORDER BY created_at"
        ).fetchall()
        return [Finding(**row) for row in rows]

    def set_finding_status(self, finding_id: str, status: FindingStatus) -> None:
        self._connect().execute("UPDATE finding SET status = %s WHERE id = %s", (status, finding_id))

    _OUTCOME_COLUMNS = (
        "finding_id", "attempt_index", "vendor_id", "from_version", "to_version",
        "change_kind", "change_severity", "operation_id", "path_ptr", "language",
        "sdk_version", "symbol_shape", "arg_arity", "arg_key_hashes",
        "response_fields_touched_count", "strategy", "tier", "routing_row", "input_tokens",
        "output_tokens", "cache_read_input_tokens", "wall_ms", "static_verify_passed",
        "static_verify_error_class", "ci_result", "terminal_status", "abandon_reason",
        "pr_number", "pr_merged", "pr_merged_at", "human_edits_before_merge",
    )

    def record_migration_outcome(self, outcome: MigrationOutcome) -> None:
        """Append one attempt to the corpus.

        `ON CONFLICT DO NOTHING` on `(finding_id, attempt_index)` because the remediation graph
        retries and a restarted run must converge rather than inflate the corpus. An inflated
        corpus silently overstates every rate computed from it, which is worse than a missing
        row because nothing looks wrong.
        """
        values = [getattr(outcome, name) for name in self._OUTCOME_COLUMNS]
        placeholders = ", ".join(["%s"] * len(self._OUTCOME_COLUMNS))
        self._connect().execute(
            f"""
            INSERT INTO migration_outcome ({", ".join(self._OUTCOME_COLUMNS)})
            VALUES ({placeholders})
            ON CONFLICT (finding_id, attempt_index) DO NOTHING
            """,
            values,
        )

    def migration_outcomes(self) -> list[MigrationOutcome]:
        rows = self._connect().execute(
            "SELECT * FROM migration_outcome ORDER BY finding_id, attempt_index"
        ).fetchall()
        return [MigrationOutcome(**row) for row in rows]

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
        """
        self._connect().execute(
            """
            UPDATE migration_outcome
               SET pr_number = COALESCE(%s, pr_number),
                   pr_merged = COALESCE(%s, pr_merged),
                   pr_merged_at = CASE WHEN %s THEN now() ELSE pr_merged_at END,
                   human_edits_before_merge = COALESCE(%s, human_edits_before_merge)
             WHERE finding_id = %s AND attempt_index = %s
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
        """
        placeholders = ", ".join(["%s"] * len(self._SHAPE_COLUMNS))
        self._connect().execute(
            f"""
            INSERT INTO observed_shape ({", ".join(self._SHAPE_COLUMNS)})
            VALUES ({placeholders})
            ON CONFLICT (vendor_id, operation_id, field_path, json_type, source) DO UPDATE SET
                sample_count = observed_shape.sample_count + EXCLUDED.sample_count,
                nullable_seen = observed_shape.nullable_seen OR EXCLUDED.nullable_seen,
                spec_enum_values = ARRAY(
                    SELECT DISTINCT unnest(observed_shape.spec_enum_values || EXCLUDED.spec_enum_values)
                    ORDER BY 1
                ),
                first_seen = LEAST(observed_shape.first_seen, EXCLUDED.first_seen),
                last_seen = GREATEST(observed_shape.last_seen, EXCLUDED.last_seen)
            """,
            [getattr(shape, name) for name in self._SHAPE_COLUMNS],
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

    def observed_calls(self, repo_id: str) -> list[ObservedCall]:
        """Every observed call for one repository.

        Scoped to a repository because that is the unit a finding is raised against, and a query
        that leaked another customer's traffic in would produce findings naming the wrong code.
        """
        rows = self._connect().execute(
            """
            SELECT * FROM observed_call
             WHERE repo_id = %s
             ORDER BY trace_id, operation_id, http_method
            """,
            (repo_id,),
        ).fetchall()
        return [ObservedCall(**row) for row in rows]

    def observed_shapes(self, vendor_id: str, operation_id: str) -> list[ObservedShape]:
        """The baseline for one operation.

        Scoped to one operation because that is what the detector asks about; a baseline that
        leaked another operation's fields into the answer would produce findings against paths
        the operation never returns.
        """
        rows = self._connect().execute(
            """
            SELECT * FROM observed_shape
             WHERE vendor_id = %s AND operation_id = %s
             ORDER BY field_path, json_type, source
            """,
            (vendor_id, operation_id),
        ).fetchall()
        return [ObservedShape(**row) for row in rows]
