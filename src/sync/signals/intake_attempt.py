"""The intake attempt record, recording when an adapter was asked and what it answered.

`docs/superpowers/specs/2026-07-27-sync-pipeline-discipline.md` and B136.

The distinction this exists to make is *never-asked* apart from *nothing-new*, and *clean-decline*
apart from *fetch-failure*. `vendor_change` records only results, so an adapter polled hourly that
found nothing new for a week is indistinguishable from one whose fetch has been 403ing for a
week. Both render as an old `last_change_at`.

Grain: one row per attempt (not per adapter).

Closed vocabulary for failure and decline reasons
-------------------------------------------------
Like B128's `abandon_reason_code`, a promise to learn from failures and aggregate statistics across
adapters requires a closed vocabulary rather than free text. Free text is retained only as diagnostic
detail.

The reasons are derived from the real failure and decline paths in our adapters:
- Clean declines (configuration or version conditions):
    - `up_to_date`: Specification hash or versions did not move; no diff needed.
    - `spec_url_unconfigured`: Manifest declares no fetchable spec URL (e.g. Cloudflare configured_endpoints).
    - `manifest_missing`: SDK generator manifest (.stats.yml, workflow.yaml) is not present.
    - `unsupported_version`: Version string or version range format unsupported.
    - `mcp_snapshot_missing`: MCP capture directory not configured or missing.
    - `same_document`: Both versions resolve to identical spec URLs (unversioned live endpoint).
- Failures (network, HTTP, tool, parsing):
    - `http_403_forbidden`: 403 Forbidden / authentication / rate limit on GitHub API / mirror.
    - `http_404_not_found`: 404 Not Found at spec URL or tag.
    - `http_429_rate_limited`: 429 Too Many Requests.
    - `http_5xx_server_error`: 500/502/503/504 server error.
    - `http_error_other`: Other HTTP non-2xx status (e.g. HTML error page returned).
    - `network_error`: Connection refused, timeout, DNS resolution failure.
    - `spec_missing`: Local spec file or directory not found.
    - `spec_unparseable`: OpenAPI JSON/YAML decode error or invalid schema.
    - `manifest_unparseable`: Manifest YAML decode error.
    - `oasdiff_error`: oasdiff tool missing or exited with error.
    - `unknown_error`: Uncaught runtime exception.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Literal, Protocol, Sequence
import urllib.error

import yaml

from sync.core import VendorChange
from sync.core.protocols import VendorAdapter

IntakeOutcome = Literal["success", "declined", "failed"]

IntakeReasonCode = Literal[
    # Clean declines / known configuration conditions
    "up_to_date",
    "spec_url_unconfigured",
    "manifest_missing",
    "unsupported_version",
    "mcp_snapshot_missing",
    "same_document",
    # Network / HTTP failures
    "http_403_forbidden",
    "http_404_not_found",
    "http_429_rate_limited",
    "http_5xx_server_error",
    "http_error_other",
    "network_error",
    # File / Spec / Tooling failures
    "spec_missing",
    "spec_unparseable",
    "manifest_unparseable",
    "oasdiff_error",
    "unknown_error",
]

CLOSED_REASON_CODES: frozenset[IntakeReasonCode] = frozenset({
    "up_to_date",
    "spec_url_unconfigured",
    "manifest_missing",
    "unsupported_version",
    "mcp_snapshot_missing",
    "same_document",
    "http_403_forbidden",
    "http_404_not_found",
    "http_429_rate_limited",
    "http_5xx_server_error",
    "http_error_other",
    "network_error",
    "spec_missing",
    "spec_unparseable",
    "manifest_unparseable",
    "oasdiff_error",
    "unknown_error",
})


@dataclass(frozen=True)
class IntakeAttempt:
    """One recorded attempt to query an adapter for vendor changes.

    Declared in `sync.signals` as the producer contract for B136.
    Lane E implements the matching consumer/store in `sync.graph`.
    """

    vendor_id: str
    attempted_at: datetime
    outcome: IntakeOutcome
    reason_code: IntakeReasonCode | None = None
    detail: str | None = None
    changes_count: int = 0
    from_version: str | None = None
    to_version: str | None = None
    source: str | None = None
    duration_ms: float | None = None


class IntakeAttemptSink(Protocol):
    """Narrow port for persisting or collecting intake attempts.

    Decoupled from GraphStore so `sync.signals` depends on no graph or storage implementation.
    """

    def record_intake_attempt(self, attempt: IntakeAttempt) -> None:
        """Persist or collect one intake attempt record."""
        ...


def classify_intake_exception(exc: Exception) -> tuple[IntakeReasonCode, str]:
    """Classify a Python exception raised during adapter fetch into a closed reason code and detail."""
    detail = str(exc) or repr(exc)
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code == 403:
            return "http_403_forbidden", detail
        if exc.code == 404:
            return "http_404_not_found", detail
        if exc.code == 429:
            return "http_429_rate_limited", detail
        if exc.code >= 500:
            return "http_5xx_server_error", detail
        return "http_error_other", detail

    if isinstance(exc, (urllib.error.URLError, TimeoutError, ConnectionError)):
        return "network_error", detail

    if isinstance(exc, (json.JSONDecodeError, yaml.YAMLError, UnicodeDecodeError)):
        return "spec_unparseable", detail

    if isinstance(exc, FileNotFoundError):
        if "oasdiff" in detail.lower():
            return "oasdiff_error", detail
        return "spec_missing", detail

    lower = detail.lower()
    if "oasdiff" in lower:
        return "oasdiff_error", detail
    if "403" in lower or "forbidden" in lower:
        return "http_403_forbidden", detail
    if "404" in lower or "not found" in lower:
        return "http_404_not_found", detail
    if "429" in lower or "rate limit" in lower:
        return "http_429_rate_limited", detail

    return "unknown_error", detail


def execute_intake_attempt(
    adapter: VendorAdapter,
    from_version: str,
    to_version: str,
    *,
    vendor_id: str | None = None,
    sink: IntakeAttemptSink | None = None,
    now: datetime | None = None,
) -> tuple[tuple[VendorChange, ...], IntakeAttempt]:
    """Execute `adapter.fetch_changes` and record the intake attempt.

    Categorizes the execution into `success`, `declined`, or `failed`, classifying
    any failure or decline reason against the closed vocabulary `IntakeReasonCode`.
    If `sink` is provided, dispatches `sink.record_intake_attempt(attempt)`.

    Returns both the fetched changes (if any) and the structured `IntakeAttempt`.
    """
    resolved_vendor_id = (
        vendor_id
        or getattr(adapter, "vendor_id", None)
        or getattr(adapter, "_vendor_id", None)
        or "unknown"
    )
    attempted_at = now or datetime.now(timezone.utc)
    start_time = time.monotonic()

    # Pre-execution check: identical versions
    if from_version == to_version:
        duration_ms = (time.monotonic() - start_time) * 1000.0
        attempt = IntakeAttempt(
            vendor_id=resolved_vendor_id,
            attempted_at=attempted_at,
            outcome="declined",
            reason_code="up_to_date",
            detail="from_version and to_version are identical",
            changes_count=0,
            from_version=from_version,
            to_version=to_version,
            duration_ms=duration_ms,
        )
        if sink is not None:
            sink.record_intake_attempt(attempt)
        return (), attempt

    # Pre-execution check: adapter observability / decline declarations
    if hasattr(adapter, "observability") and callable(adapter.observability):
        obs = adapter.observability(from_version, to_version)
        if not getattr(obs, "observable", True):
            reason_name = getattr(obs, "reason", "")
            detail = getattr(obs, "detail", "")
            duration_ms = (time.monotonic() - start_time) * 1000.0
            reason_code: IntakeReasonCode = "spec_url_unconfigured"
            if reason_name in ("no_manifest", "no-manifest"):
                reason_code = "manifest_missing"
            elif reason_name in ("one_document", "one-document"):
                reason_code = "same_document"
            elif reason_name in ("no_specification", "no-specification"):
                reason_code = "spec_url_unconfigured"

            attempt = IntakeAttempt(
                vendor_id=resolved_vendor_id,
                attempted_at=attempted_at,
                outcome="declined",
                reason_code=reason_code,
                detail=detail,
                changes_count=0,
                from_version=from_version,
                to_version=to_version,
                duration_ms=duration_ms,
            )
            if sink is not None:
                sink.record_intake_attempt(attempt)
            return (), attempt

    try:
        changes = tuple(adapter.fetch_changes(from_version, to_version))
        duration_ms = (time.monotonic() - start_time) * 1000.0
        source = changes[0].source if changes else None

        attempt = IntakeAttempt(
            vendor_id=resolved_vendor_id,
            attempted_at=attempted_at,
            outcome="success",
            reason_code=None,
            detail=None,
            changes_count=len(changes),
            from_version=from_version,
            to_version=to_version,
            source=source,
            duration_ms=duration_ms,
        )
    except Exception as exc:
        duration_ms = (time.monotonic() - start_time) * 1000.0
        reason_code, detail = classify_intake_exception(exc)
        attempt = IntakeAttempt(
            vendor_id=resolved_vendor_id,
            attempted_at=attempted_at,
            outcome="failed",
            reason_code=reason_code,
            detail=detail,
            changes_count=0,
            from_version=from_version,
            to_version=to_version,
            duration_ms=duration_ms,
        )
        if sink is not None:
            sink.record_intake_attempt(attempt)
        return (), attempt

    if sink is not None:
        sink.record_intake_attempt(attempt)
    return changes, attempt
