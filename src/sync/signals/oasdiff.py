"""Thin subprocess wrapper around the oasdiff binary."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from sync.core import VendorChange


def _binary() -> str:
    root = Path(__file__).resolve().parents[3]
    for candidate in (root / "tools" / "oasdiff.exe", root / "tools" / "oasdiff"):
        if candidate.exists():
            return str(candidate)
    found = shutil.which("oasdiff")
    if found:
        return found
    raise FileNotFoundError("oasdiff not found; run scripts/bootstrap_tools.sh")


def run_oasdiff_breaking(base_path: Path, revision_path: Path) -> list[dict[str, Any]]:
    """Return oasdiff's breaking-change records.

    We don't pass `--fail-on`, so 1.26.0 exits 0 for this invocation whether or
    not it finds breaking changes; "no findings" is reported as the JSON literal
    `[]`, never as empty output. Any non-zero exit is therefore a real failure
    (bad args, a crashed or killed process) and must raise rather than be read
    as a clean report.
    """
    result = subprocess.run(
        [_binary(), "breaking", str(base_path), str(revision_path), "--format", "json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(f"oasdiff failed ({result.returncode}): {result.stderr.strip()}")
    parsed = json.loads(result.stdout.strip())
    return parsed if isinstance(parsed, list) else []


def to_vendor_changes(
    records: list[dict[str, Any]], vendor_id: str, from_version: str, to_version: str
) -> list[VendorChange]:
    """Map oasdiff records onto VendorChange rows.

    oasdiff reports `operationId` when the spec declares one, and always reports
    `operation` (the HTTP method) plus `path`. We prefer operationId and fall back
    to `METHOD path` so a spec without operation IDs still produces usable changes.
    """
    changes: list[VendorChange] = []
    for record in records:
        operation_id = record.get("operationId") or f"{record.get('operation', '')} {record.get('path', '')}".strip()
        changes.append(
            VendorChange(
                vendor_id=vendor_id,
                from_version=from_version,
                to_version=to_version,
                kind=record.get("id", "unknown"),
                operation_id=operation_id,
                path_ptr=record.get("path", ""),
                severity="breaking",
                source="oasdiff",
                raw=record,
            )
        )
    return changes
