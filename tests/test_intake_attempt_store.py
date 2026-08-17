"""The intake attempt record reaches PostgreSQL, and the store implements IntakeAttemptSink.

B136's store half: `IntakeAttempt` records every adapter inquiry -- what was asked, what it
answered, and why it declined or failed. `GraphStore` persists these rows idempotently with
natural key `(vendor_id, attempted_at, from_version, to_version)` and closed reason code vocabulary.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

from sync.graph.store import GraphStore
from sync.signals.intake_attempt import (
    CLOSED_REASON_CODES,
    IntakeAttempt,
    IntakeAttemptSink,
)

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")


@pytest.fixture()
def store() -> GraphStore:
    store = GraphStore(DSN)
    store.apply_schema()
    with store.transaction():
        store.truncate_all()
    return store


def test_graph_store_satisfies_intake_attempt_sink_protocol(store: GraphStore):
    assert hasattr(store, "record_intake_attempt")
    assert callable(store.record_intake_attempt)
    # Also verify type signature compatibility by invoking it
    now = datetime(2026, 8, 17, 10, 0, 0, tzinfo=timezone.utc)
    sink: IntakeAttemptSink = store
    sink.record_intake_attempt(
        IntakeAttempt(vendor_id="stripe", attempted_at=now, outcome="success")
    )


def test_record_and_retrieve_intake_attempt(store: GraphStore):
    now = datetime(2026, 8, 17, 10, 0, 0, tzinfo=timezone.utc)
    attempt = IntakeAttempt(
        vendor_id="stripe",
        attempted_at=now,
        outcome="success",
        reason_code=None,
        detail=None,
        changes_count=12,
        from_version="2024-04-10",
        to_version="2024-06-20",
        source="oasdiff",
        duration_ms=450.5,
    )

    attempt_id = store.record_intake_attempt(attempt)
    assert isinstance(attempt_id, str)
    assert len(attempt_id) == 32

    rows = store.intake_attempts(vendor_id="stripe")
    assert len(rows) == 1
    stored = rows[0]

    assert stored.vendor_id == "stripe"
    assert stored.attempted_at == now
    assert stored.outcome == "success"
    assert stored.reason_code is None
    assert stored.detail is None
    assert stored.changes_count == 12
    assert stored.from_version == "2024-04-10"
    assert stored.to_version == "2024-06-20"
    assert stored.source == "oasdiff"
    assert stored.duration_ms == 450.5


def test_record_intake_attempt_clean_decline(store: GraphStore):
    now = datetime(2026, 8, 17, 11, 0, 0, tzinfo=timezone.utc)
    attempt = IntakeAttempt(
        vendor_id="twilio",
        attempted_at=now,
        outcome="declined",
        reason_code="up_to_date",
        detail="spec hash unchanged",
        changes_count=0,
        from_version="v1",
        to_version="v1",
        source=None,
        duration_ms=1.2,
    )

    store.record_intake_attempt(attempt)
    rows = store.intake_attempts(vendor_id="twilio")
    assert len(rows) == 1
    assert rows[0].outcome == "declined"
    assert rows[0].reason_code == "up_to_date"
    assert rows[0].detail == "spec hash unchanged"


def test_record_intake_attempt_failure(store: GraphStore):
    now = datetime(2026, 8, 17, 12, 0, 0, tzinfo=timezone.utc)
    attempt = IntakeAttempt(
        vendor_id="github",
        attempted_at=now,
        outcome="failed",
        reason_code="http_403_forbidden",
        detail="HTTP 403: API rate limit exceeded",
        changes_count=0,
        from_version="2022-11-28",
        to_version="2026-01-01",
        source="openapi",
        duration_ms=150.0,
    )

    store.record_intake_attempt(attempt)
    rows = store.intake_attempts(vendor_id="github")
    assert len(rows) == 1
    assert rows[0].outcome == "failed"
    assert rows[0].reason_code == "http_403_forbidden"
    assert rows[0].detail == "HTTP 403: API rate limit exceeded"


def test_record_intake_attempt_idempotency_converges(store: GraphStore):
    now = datetime(2026, 8, 17, 13, 0, 0, tzinfo=timezone.utc)
    attempt1 = IntakeAttempt(
        vendor_id="stripe",
        attempted_at=now,
        outcome="failed",
        reason_code="network_error",
        detail="timeout",
        changes_count=0,
        from_version="v1",
        to_version="v2",
        source="oasdiff",
        duration_ms=100.0,
    )
    attempt2 = IntakeAttempt(
        vendor_id="stripe",
        attempted_at=now,
        outcome="success",
        reason_code=None,
        detail=None,
        changes_count=5,
        from_version="v1",
        to_version="v2",
        source="oasdiff",
        duration_ms=300.0,
    )

    id1 = store.record_intake_attempt(attempt1)
    id2 = store.record_intake_attempt(attempt2)
    assert id1 == id2

    rows = store.intake_attempts(vendor_id="stripe")
    assert len(rows) == 1
    assert rows[0].outcome == "success"
    assert rows[0].changes_count == 5
    assert rows[0].reason_code is None


def test_intake_attempts_filtered_by_vendor_and_ordered_by_time_desc(store: GraphStore):
    t1 = datetime(2026, 8, 17, 8, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 8, 17, 9, 0, 0, tzinfo=timezone.utc)
    t3 = datetime(2026, 8, 17, 10, 0, 0, tzinfo=timezone.utc)

    store.record_intake_attempt(
        IntakeAttempt(vendor_id="stripe", attempted_at=t1, outcome="success")
    )
    store.record_intake_attempt(
        IntakeAttempt(vendor_id="stripe", attempted_at=t3, outcome="success")
    )
    store.record_intake_attempt(
        IntakeAttempt(vendor_id="twilio", attempted_at=t2, outcome="declined")
    )

    stripe_rows = store.intake_attempts(vendor_id="stripe")
    assert len(stripe_rows) == 2
    assert stripe_rows[0].attempted_at == t3
    assert stripe_rows[1].attempted_at == t1

    all_rows = store.intake_attempts()
    assert len(all_rows) == 3
    assert [r.attempted_at for r in all_rows] == [t3, t2, t1]
