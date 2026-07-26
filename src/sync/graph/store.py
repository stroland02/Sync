"""Persistence and queries for the API Dependency Graph."""

from __future__ import annotations

import hashlib
import json
from importlib import resources

import psycopg
from psycopg.rows import dict_row

from sync.core import CallSite, Finding, FindingStatus, VendorChange


def _stable_id(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:32]


class GraphStore:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self._dsn, row_factory=dict_row, autocommit=True)

    def apply_schema(self) -> None:
        ddl = resources.files("sync.graph").joinpath("schema.sql").read_text(encoding="utf-8")
        with self._connect() as conn:
            conn.execute(ddl)

    def truncate_all(self) -> None:
        with self._connect() as conn:
            conn.execute("TRUNCATE finding, call_site, vendor_change CASCADE")

    def upsert_call_site(self, site: CallSite) -> str:
        site_id = _stable_id(site.repo_id, site.path, site.symbol)
        with self._connect() as conn:
            conn.execute(
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
        with self._connect() as conn:
            conn.execute(
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
        with self._connect() as conn:
            conn.execute(
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
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM call_site WHERE vendor_id = %s AND operation_id = %s ORDER BY path, line",
                (vendor_id, operation_id),
            ).fetchall()
        return [CallSite(**row) for row in rows]

    def get_call_site(self, call_site_id: str) -> CallSite:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM call_site WHERE id = %s", (call_site_id,)).fetchone()
        if row is None:
            raise KeyError(f"no call site {call_site_id}")
        return CallSite(**row)

    def get_vendor_change(self, change_id: str) -> VendorChange:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM vendor_change WHERE id = %s", (change_id,)).fetchone()
        if row is None:
            raise KeyError(f"no vendor change {change_id}")
        return VendorChange(**row)

    def all_vendor_changes(self, vendor_id: str) -> list[VendorChange]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM vendor_change WHERE vendor_id = %s ORDER BY detected_at", (vendor_id,)
            ).fetchall()
        return [VendorChange(**row) for row in rows]

    def open_findings(self) -> list[Finding]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM finding WHERE status = 'open' ORDER BY created_at").fetchall()
        return [Finding(**row) for row in rows]

    def set_finding_status(self, finding_id: str, status: FindingStatus) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE finding SET status = %s WHERE id = %s", (status, finding_id))
