"""Thin subprocess wrapper around the oasdiff binary."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from sync.core import VendorChange

_BACKTICKED = re.compile(r"`([^`]+)`")
_COMPOSITION_SEGMENT = re.compile(r"\A(?:any|one|all)Of\[.*\]\Z")
# `\Z`, never `$`: `$` also matches before a trailing newline, so a segment ending in one
# would be accepted and handed back with the newline still attached.
_SINGLE_LINE_NAME = re.compile(r"[^\n]+\Z")


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
    parsed = _parse_json(result.stdout, "oasdiff breaking")
    return parsed if isinstance(parsed, list) else []


def run_oasdiff_checks() -> list[dict[str, Any]]:
    """The binary's own catalogue of checker rules, one record per rule.

    Each record carries `id` -- which is what `VendorChange.kind` holds -- alongside the
    `level`, `direction`, `kind`, and `action` axes the routing matrix keys on. Reading the
    catalogue from the binary rather than maintaining a copy is what keeps routing honest
    across an oasdiff upgrade: the rule set grows, and a stale local list would route new
    kinds silently.

    Note the two surfaces disagree on how `level` is encoded -- a string here, an integer in
    `breaking` output -- so map between them explicitly rather than comparing directly.
    """
    result = subprocess.run(
        [_binary(), "checks", "--format", "json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(f"oasdiff checks failed ({result.returncode}): {result.stderr.strip()}")
    parsed = _parse_json(result.stdout, "oasdiff checks")
    return parsed if isinstance(parsed, list) else []


def _parse_json(stdout: str, surface: str) -> Any:
    """Parse one oasdiff invocation's stdout, failing as this module documents.

    Subprocess output is a system boundary, and a truncated or malformed payload here
    raises `JSONDecodeError` -- an exception no caller of this module is written against,
    since `RuntimeError` is the failure it declares. It must still raise: a differ whose
    output could not be parsed is not a vendor that changed nothing.
    """
    try:
        return json.loads(stdout.strip())
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{surface} output was not JSON ({exc}): {stdout[:200]!r}") from exc


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


def changed_field(change: VendorChange) -> str | None:
    """The field name a change refers to, when it can be determined.

    Real oasdiff records never carry a `field`, `property`, `parameter`, or
    `name` key -- the lookups below cost nothing today and stand ready in
    case a future oasdiff version adds a structured one. The field name lives
    in the free-text `text` message instead, as the first backticked token
    (oasdiff backticks the field it names before any incidental value, such
    as a status code). There is deliberately no path-derived fallback for
    `path_ptr`, the URL path: a URL segment is never a field name, and
    returning one would be confident nonsense -- worse than admitting the
    field couldn't be determined. The backticked token is different: for a
    nested property it is itself a schema path, and unlike a URL path its
    segments genuinely are property names, so it is reduced to its leaf
    rather than returned whole.
    """
    for key in ("field", "property", "parameter", "name"):
        value = change.raw.get(key)
        if isinstance(value, str) and value:
            return value
    text = change.raw.get("text")
    if isinstance(text, str):
        match = _BACKTICKED.search(text)
        if match:
            return _leaf_of(match.group(1))
    return None


def _leaf_of(token: str) -> str | None:
    """The property name at the end of an oasdiff property path.

    oasdiff names a nested property by its full schema path, interposing a
    segment for every composition it walks through -- `anyOf[subschema #1:
    Name]` and its `oneOf`/`allOf` siblings. Those segments name a schema, not
    a property, so the rightmost segment is not always the field.

    The indexer records the bare names a call site reads, so a path matches
    only once reduced to one. The deepest real name is the property the vendor
    changed, which is what makes the reduction sound.

    Composition is the only reason a segment defers to the one above it.
    Skipping a segment for any other reason answers with the parent's name --
    a field the vendor did not change, which filters the finding out of
    existence. `None` is the safe miss: the finding still matches on its
    operation.
    """
    for segment in reversed(token.split("/")):
        if _COMPOSITION_SEGMENT.match(segment):
            continue
        return segment if _SINGLE_LINE_NAME.match(segment) else None
    return None
