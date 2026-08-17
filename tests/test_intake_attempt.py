"""Tests for the B136 intake attempt record producer half and closed vocabulary."""

from __future__ import annotations

import json
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pytest

from sync.core import VendorChange
from sync.signals.generated.adapter import GeneratedSpecAdapter, NO_MANIFEST, NO_SPECIFICATION, ONE_DOCUMENT, Observability
from sync.signals.generated.manifest import SpecSource
from sync.signals.intake_attempt import (
    CLOSED_REASON_CODES,
    IntakeAttempt,
    IntakeAttemptSink,
    IntakeOutcome,
    IntakeReasonCode,
    classify_intake_exception,
    execute_intake_attempt,
)


class MemoryIntakeAttemptSink:
    """Test fake implementing IntakeAttemptSink protocol."""

    def __init__(self) -> None:
        self.attempts: list[IntakeAttempt] = []

    def record_intake_attempt(self, attempt: IntakeAttempt) -> None:
        self.attempts.append(attempt)


class StubAdapter:
    """Configurable stub adapter for testing intake attempts."""

    def __init__(
        self,
        vendor_id: str,
        changes: Iterable[VendorChange] = (),
        error: Exception | None = None,
        observability_verdict: Observability | None = None,
    ) -> None:
        self.vendor_id = vendor_id
        self._changes = list(changes)
        self._error = error
        self._observability_verdict = observability_verdict

    def observability(self, from_version: str, to_version: str) -> Observability:
        if self._observability_verdict is not None:
            return self._observability_verdict
        return Observability(True, "observable", "observable")

    def fetch_changes(self, from_version: str, to_version: str) -> Iterable[VendorChange]:
        if self._error is not None:
            raise self._error
        return self._changes


def _change(**kw) -> VendorChange:
    base = dict(
        vendor_id="stripe",
        from_version="v1",
        to_version="v2",
        kind="request-parameter-removed",
        operation_id="PostCharges",
        path_ptr="/paths/~1charges/post",
        severity="breaking",
        source="oasdiff",
    )
    base.update(kw)
    return VendorChange(**base)


# --- Closed Vocabulary Invariants ---


def test_closed_reason_codes_is_frozen_and_non_empty():
    assert len(CLOSED_REASON_CODES) >= 15
    assert "http_403_forbidden" in CLOSED_REASON_CODES
    assert "up_to_date" in CLOSED_REASON_CODES
    assert "spec_url_unconfigured" in CLOSED_REASON_CODES
    assert "manifest_missing" in CLOSED_REASON_CODES
    assert "spec_unparseable" in CLOSED_REASON_CODES
    assert "oasdiff_error" in CLOSED_REASON_CODES


# --- Success Path ---


def test_successful_fetch_records_attempt_with_changes_count():
    sink = MemoryIntakeAttemptSink()
    change = _change(vendor_id="stripe")
    adapter = StubAdapter(vendor_id="stripe", changes=[change])

    now = datetime(2026, 8, 17, 12, 0, 0, tzinfo=timezone.utc)
    changes, attempt = execute_intake_attempt(
        adapter, "v1", "v2", sink=sink, now=now
    )

    assert len(changes) == 1
    assert attempt.vendor_id == "stripe"
    assert attempt.attempted_at == now
    assert attempt.outcome == "success"
    assert attempt.reason_code is None
    assert attempt.detail is None
    assert attempt.changes_count == 1
    assert attempt.from_version == "v1"
    assert attempt.to_version == "v2"
    assert attempt.source == "oasdiff"
    assert attempt.duration_ms is not None
    assert attempt.duration_ms >= 0.0

    assert sink.attempts == [attempt]


def test_successful_fetch_with_zero_changes_records_success():
    sink = MemoryIntakeAttemptSink()
    adapter = StubAdapter(vendor_id="stripe", changes=[])

    changes, attempt = execute_intake_attempt(
        adapter, "v1", "v2", sink=sink
    )

    assert len(changes) == 0
    assert attempt.outcome == "success"
    assert attempt.reason_code is None
    assert attempt.changes_count == 0


# --- Pre-execution & Decline Paths ---


def test_identical_versions_records_declined_up_to_date():
    sink = MemoryIntakeAttemptSink()
    adapter = StubAdapter(vendor_id="stripe", changes=[_change()])

    changes, attempt = execute_intake_attempt(
        adapter, "v1", "v1", sink=sink
    )

    assert len(changes) == 0
    assert attempt.outcome == "declined"
    assert attempt.reason_code == "up_to_date"
    assert attempt.changes_count == 0
    assert attempt.reason_code in CLOSED_REASON_CODES
    assert sink.attempts == [attempt]


def test_unconfigured_spec_url_records_declined_spec_url_unconfigured():
    sink = MemoryIntakeAttemptSink()
    obs = Observability(False, NO_SPECIFICATION, "manifest names no spec to fetch")
    adapter = StubAdapter(vendor_id="cloudflare", observability_verdict=obs)

    changes, attempt = execute_intake_attempt(
        adapter, "v1", "v2", sink=sink
    )

    assert len(changes) == 0
    assert attempt.outcome == "declined"
    assert attempt.reason_code == "spec_url_unconfigured"
    assert attempt.reason_code in CLOSED_REASON_CODES
    assert "manifest names no spec" in (attempt.detail or "")
    assert sink.attempts == [attempt]


def test_missing_manifest_records_declined_manifest_missing():
    sink = MemoryIntakeAttemptSink()
    obs = Observability(False, NO_MANIFEST, "no manifest parsed for v1")
    adapter = StubAdapter(vendor_id="anthropic", observability_verdict=obs)

    changes, attempt = execute_intake_attempt(
        adapter, "v1", "v2", sink=sink
    )

    assert len(changes) == 0
    assert attempt.outcome == "declined"
    assert attempt.reason_code == "manifest_missing"
    assert attempt.reason_code in CLOSED_REASON_CODES
    assert sink.attempts == [attempt]


def test_same_document_records_declined_same_document():
    sink = MemoryIntakeAttemptSink()
    obs = Observability(False, ONE_DOCUMENT, "both versions resolve to same unversioned URL")
    adapter = StubAdapter(vendor_id="vercel", observability_verdict=obs)

    changes, attempt = execute_intake_attempt(
        adapter, "v1", "v2", sink=sink
    )

    assert len(changes) == 0
    assert attempt.outcome == "declined"
    assert attempt.reason_code == "same_document"
    assert attempt.reason_code in CLOSED_REASON_CODES
    assert sink.attempts == [attempt]


# --- Failure Paths & Exception Classification ---


@pytest.mark.parametrize(
    ("http_code", "expected_reason"),
    [
        (403, "http_403_forbidden"),
        (404, "http_404_not_found"),
        (429, "http_429_rate_limited"),
        (500, "http_5xx_server_error"),
        (502, "http_5xx_server_error"),
        (503, "http_5xx_server_error"),
        (418, "http_error_other"),
    ],
)
def test_http_status_errors_classified_into_closed_reasons(http_code: int, expected_reason: IntakeReasonCode):
    sink = MemoryIntakeAttemptSink()
    err = urllib.error.HTTPError(
        url="https://api.vendor.com/spec.json",
        code=http_code,
        msg=f"HTTP {http_code}",
        hdrs={},  # type: ignore[arg-type]
        fp=None,
    )
    adapter = StubAdapter(vendor_id="vendor-x", error=err)

    changes, attempt = execute_intake_attempt(adapter, "v1", "v2", sink=sink)

    assert len(changes) == 0
    assert attempt.outcome == "failed"
    assert attempt.reason_code == expected_reason
    assert attempt.reason_code in CLOSED_REASON_CODES
    assert attempt.changes_count == 0
    assert sink.attempts == [attempt]


def test_network_connection_error_records_failed_network_error():
    sink = MemoryIntakeAttemptSink()
    err = urllib.error.URLError(ConnectionRefusedError("Connection refused by peer"))
    adapter = StubAdapter(vendor_id="vendor-x", error=err)

    changes, attempt = execute_intake_attempt(adapter, "v1", "v2", sink=sink)

    assert attempt.outcome == "failed"
    assert attempt.reason_code == "network_error"
    assert attempt.reason_code in CLOSED_REASON_CODES
    assert "Connection refused" in (attempt.detail or "")


def test_timeout_error_records_failed_network_error():
    sink = MemoryIntakeAttemptSink()
    err = TimeoutError("Request timed out after 60s")
    adapter = StubAdapter(vendor_id="vendor-x", error=err)

    changes, attempt = execute_intake_attempt(adapter, "v1", "v2", sink=sink)

    assert attempt.outcome == "failed"
    assert attempt.reason_code == "network_error"
    assert attempt.reason_code in CLOSED_REASON_CODES


def test_spec_unparseable_records_failed_spec_unparseable():
    sink = MemoryIntakeAttemptSink()
    err = json.JSONDecodeError("Expecting value", "<html>404 Not Found</html>", 0)
    adapter = StubAdapter(vendor_id="vendor-x", error=err)

    changes, attempt = execute_intake_attempt(adapter, "v1", "v2", sink=sink)

    assert attempt.outcome == "failed"
    assert attempt.reason_code == "spec_unparseable"
    assert attempt.reason_code in CLOSED_REASON_CODES


def test_oasdiff_error_records_failed_oasdiff_error():
    sink = MemoryIntakeAttemptSink()
    err = FileNotFoundError("[Errno 2] No such file or directory: 'oasdiff'")
    adapter = StubAdapter(vendor_id="vendor-x", error=err)

    changes, attempt = execute_intake_attempt(adapter, "v1", "v2", sink=sink)

    assert attempt.outcome == "failed"
    assert attempt.reason_code == "oasdiff_error"
    assert attempt.reason_code in CLOSED_REASON_CODES


def test_runtime_error_with_403_message_classified_as_403():
    sink = MemoryIntakeAttemptSink()
    err = RuntimeError("gh api error: 403 Forbidden rate limit exceeded")
    adapter = StubAdapter(vendor_id="stripe", error=err)

    changes, attempt = execute_intake_attempt(adapter, "v1", "v2", sink=sink)

    assert attempt.outcome == "failed"
    assert attempt.reason_code == "http_403_forbidden"
    assert attempt.reason_code in CLOSED_REASON_CODES


# --- Real GeneratedSpecAdapter Integration with intake attempt ---


def test_real_generated_spec_adapter_declined_intake_attempt(tmp_path: Path):
    cache = tmp_path / "cache"
    cache.mkdir()
    adapter = GeneratedSpecAdapter(
        vendor_id="cloudflare",
        sources={
            "v1": SpecSource(generator="stainless", endpoint_count=42),
            "v2": SpecSource(generator="stainless", endpoint_count=45),
        },
        fetch=lambda url: "{}",
        cache_dir=cache,
    )
    sink = MemoryIntakeAttemptSink()

    changes, attempt = execute_intake_attempt(adapter, "v1", "v2", sink=sink)

    assert len(changes) == 0
    assert attempt.vendor_id == "cloudflare"
    assert attempt.outcome == "declined"
    assert attempt.reason_code == "spec_url_unconfigured"
    assert attempt.reason_code in CLOSED_REASON_CODES
    assert sink.attempts == [attempt]


# --- B168: Detail Sanitization and Validation Tests ---


def test_sanitize_intake_detail_truncates_oversize_detail():
    long_text = "A" * 1000
    attempt = IntakeAttempt(
        vendor_id="stripe",
        attempted_at=datetime.now(timezone.utc),
        outcome="failed",
        reason_code="unknown_error",
        detail=long_text,
    )
    assert attempt.detail is not None
    assert len(attempt.detail) <= 500
    assert attempt.detail.endswith("...[truncated]")


def test_sanitize_intake_detail_scrubs_absolute_paths():
    win_path = r"C:\Users\strol\orca\Sync\Sync\spec.yaml failed to parse at line 10"
    posix_path = "/home/runner/work/Sync/Sync/openapi.json not found"

    attempt_win = IntakeAttempt(
        vendor_id="stripe",
        attempted_at=datetime.now(timezone.utc),
        outcome="failed",
        reason_code="spec_unparseable",
        detail=win_path,
    )
    assert "[path]" in (attempt_win.detail or "")
    assert "Users" not in (attempt_win.detail or "")
    assert "strol" not in (attempt_win.detail or "")

    attempt_posix = IntakeAttempt(
        vendor_id="stripe",
        attempted_at=datetime.now(timezone.utc),
        outcome="failed",
        reason_code="spec_missing",
        detail=posix_path,
    )
    assert "[path]" in (attempt_posix.detail or "")
    assert "home" not in (attempt_posix.detail or "")
    assert "runner" not in (attempt_posix.detail or "")


def test_intake_attempt_validates_closed_vocabulary():
    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError, match="invalid intake outcome"):
        IntakeAttempt(vendor_id="stripe", attempted_at=now, outcome="pending")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="invalid intake reason_code"):
        IntakeAttempt(vendor_id="stripe", attempted_at=now, outcome="failed", reason_code="invented_reason")  # type: ignore[arg-type]

