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

    oasdiff exits 0 when there are no breaking changes and 1 when there are,
    but only once `--fail-on WARN` is passed — without it, oasdiff 1.26.0 always
    exits 0 and leaves exit-code signalling to the caller. WARN is the lower of
    oasdiff's two failure levels, so `--fail-on WARN` covers both WARN and ERR
    findings; everything it reports lands in our own `severity="breaking"`.
    Exit code 1 is a successful run with findings — only codes above 1 are errors.
    """
    result = subprocess.run(
        [_binary(), "breaking", str(base_path), str(revision_path), "--format", "json", "--fail-on", "WARN"],
        capture_output=True,
        text=True,
    )
    if result.returncode > 1:
        raise RuntimeError(f"oasdiff failed ({result.returncode}): {result.stderr.strip()}")
    payload = result.stdout.strip()
    if not payload:
        return []
    parsed = json.loads(payload)
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
