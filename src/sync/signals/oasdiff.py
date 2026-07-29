"""Thin subprocess wrapper around the oasdiff binary."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from sync.core import Severity, VendorChange

_BACKTICKED = re.compile(r"`([^`]+)`")
_COMPOSITION_SEGMENT = re.compile(r"\A(?:any|one|all)Of\[.*\]\Z")
# `\Z`, never `$`: `$` also matches before a trailing newline, so a segment ending in one
# would be accepted and handed back with the newline still attached.
_SINGLE_LINE_NAME = re.compile(r"[^\n]+\Z")

# oasdiff's own grading, as the two surfaces encode it. A `breaking` record carries `level` as an
# **integer**; `oasdiff checks` carries it as a **string**. Nothing but the rule id is common to
# both, so every pair below was established by joining a record to the catalogue on that id
# against the pinned binary rather than inferred from the names --
# `test_the_two_surfaces_encode_level_differently_and_the_integers_cross_reference` is that join,
# and it runs the binary rather than asserting a table against itself.
#
# `1` is reachable only through `changelog`; `breaking` emits `2` and `3`. It is mapped anyway,
# because a level this module knows about and declines to map is the same silent default the
# mapping exists to remove.
LEVEL_SEVERITY: dict[int, Severity] = {3: "breaking", 2: "warning", 1: "info"}


class UnknownOasdiffLevel(ValueError):
    """A record graded at a level this mapping does not know.

    An oasdiff release adding a level, renaming the field, or moving the record surface to the
    catalogue's string encoding all arrive here. Every one of them is a finding about the tool
    and none is a record to guess at: defaulting an unknown grading to `breaking` is precisely
    the behaviour this mapping replaced, one release later and harder to see, because it would
    once again be a constant that reads as evidence.
    """


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


def severity_for(record: dict[str, Any]) -> Severity:
    """What oasdiff graded this record, in this repository's vocabulary.

    Raises rather than defaulting. `level` is read exactly as it arrives -- an integer key, no
    coercion -- because a string here would mean the record surface had moved to the catalogue's
    encoding, and coercing it would hide the one change worth being told about.
    """
    level = record.get("level")
    if not isinstance(level, int) or isinstance(level, bool) or level not in LEVEL_SEVERITY:
        raise UnknownOasdiffLevel(
            f"oasdiff graded a {record.get('id', 'unknown')!r} record at level {level!r}, which "
            f"this mapping does not know; known levels are "
            f"{sorted(LEVEL_SEVERITY)} (see `oasdiff checks`)"
        )
    return LEVEL_SEVERITY[level]


def to_vendor_changes(
    records: list[dict[str, Any]], vendor_id: str, from_version: str, to_version: str
) -> list[VendorChange]:
    """Map oasdiff records onto VendorChange rows.

    oasdiff reports `operationId` when the spec declares one, and always reports
    `operation` (the HTTP method) plus `path`. We prefer operationId and fall back
    to `METHOD path` so a spec without operation IDs still produces usable changes.

    Severity is what oasdiff said about this record and not a constant. It used to be
    `"breaking"` unconditionally, which `2026-07-29-oasdiff-determinism.md` measured as a field
    carrying no information at all -- every one of 792,552 records was warning-level -- and which
    `2026-07-27-sync-routing-matrix.md` had already named as the reason an endpoint deleted
    without deprecation and an optional response property removed arrived downstream
    indistinguishable.
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
                severity=severity_for(record),
                source="oasdiff",
                raw=record,
            )
        )
    return changes


def changed_path(change: VendorChange) -> list[str] | None:
    """The property path a change refers to, outermost segment first.

    Real oasdiff records never carry a `field`, `property`, `parameter`, or
    `name` key -- the lookups below cost nothing today and stand ready in
    case a future oasdiff version adds a structured one. A structured key
    names a field and not a path, so it answers as a single segment. The path
    otherwise lives in the free-text `text` message, as the first backticked
    token (oasdiff backticks the field it names before any incidental value,
    such as a status code). There is deliberately no fallback to `path_ptr`,
    the URL path: a URL segment is never a property name, and returning one
    would be confident nonsense -- worse than admitting the path couldn't be
    determined.

    `None`, never `[]`, when nothing resolves: an empty path reads as a real
    answer to a caller that only checks for `None`, and the safe miss is the
    finding matching on its operation alone.
    """
    for key in ("field", "property", "parameter", "name"):
        value = change.raw.get(key)
        if isinstance(value, str) and value:
            return [value]
    text = change.raw.get("text")
    if isinstance(text, str):
        match = _BACKTICKED.search(text)
        if match:
            return _real_segments(match.group(1))
    return None


def changed_field(change: VendorChange) -> str | None:
    """The name of the property a change refers to, when it can be determined.

    The deepest real segment of the path is the property the vendor changed.
    Callers that need to know which call sites are affected want the whole
    path instead -- a name alone cannot say where in a response it sits.
    """
    path = changed_path(change)
    return path[-1] if path else None


def _real_segments(token: str) -> list[str] | None:
    """An oasdiff property path with its structural segments removed.

    oasdiff names a nested property by its full schema path, interposing a
    segment for every composition it walks through -- `anyOf[subschema #1:
    Name]` and its `oneOf`/`allOf` siblings. Those segments name a schema, not
    a property, so they are not part of the path a caller can match against.

    Composition is the only reason a segment is dropped. Dropping the deepest
    segment for any other reason would leave the parent's name standing as the
    leaf -- a field the vendor did not change, which filters the finding out of
    existence rather than merely weakening it. A deepest segment that could
    never name a property answers `None` instead.
    """
    segments = [s for s in token.split("/") if not _COMPOSITION_SEGMENT.match(s)]
    if not segments or not _SINGLE_LINE_NAME.match(segments[-1]):
        return None
    return segments
