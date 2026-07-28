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
from sync.core.models import ObservedShape


def _stable_id(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:32]


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
        ddl = resources.files("sync.graph").joinpath("schema.sql").read_text(encoding="utf-8")
        self._connect().execute(ddl)

    def truncate_all(self) -> None:
        self._connect().execute(
            "TRUNCATE finding, call_site, vendor_change, migration_outcome, observed_shape CASCADE"
        )

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
                                   symbol, args_keys, response_fields_read, sdk_version, content_hash)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                line = EXCLUDED.line,
                col = EXCLUDED.col,
                operation_id = EXCLUDED.operation_id,
                args_keys = EXCLUDED.args_keys,
                response_fields_read = EXCLUDED.response_fields_read,
                sdk_version = EXCLUDED.sdk_version,
                content_hash = EXCLUDED.content_hash,
                indexed_at = now()
            """,
            (
                site_id, site.repo_id, site.path, site.line, site.col, site.vendor_id,
                site.operation_id, site.symbol, site.args_keys, site.response_fields_read,
                site.sdk_version, site.content_hash,
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
        finding_id = _stable_id(finding.detector, finding.call_site_id, finding.vendor_change_id or "")
        self._connect().execute(
            """
            INSERT INTO finding (id, detector, call_site_id, vendor_change_id, severity, rationale, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                finding_id, finding.detector, finding.call_site_id, finding.vendor_change_id,
                finding.severity, finding.rationale, finding.status,
            ),
        )
        return finding_id

    def call_sites_for_operation(self, vendor_id: str, operation_id: str) -> list[CallSite]:
        rows = self._connect().execute(
            "SELECT * FROM call_site WHERE vendor_id = %s AND operation_id = %s ORDER BY path, line",
            (vendor_id, operation_id),
        ).fetchall()
        return [CallSite(**row) for row in rows]

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
        "response_fields_touched_count", "strategy", "tier", "input_tokens",
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
