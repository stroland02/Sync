"""Traffic and non-traffic rows are kept apart on read.

`observed_shape.source` says which mechanism produced a row. Two consumers read the table as
traffic -- `ObservedDriftDetector` and the baseline the mock builder is handed -- and until this
change neither could say so: `GraphStore.observed_shapes` selected on `(vendor_id,
operation_id)` and returned every source the table held.

That was harmless only because both writers emit `error-payload`.
`docs/superpowers/reports/2026-07-30-replay-shapes-reach-the-store.md` measured what the first
non-traffic writer would cost, against a real server: one `source='replay'` row at
`sample_count=1` turns an uncorroborated divergence into a `breaking` finding whose rationale
asserts the vendor's behaviour changed, and a `replay` row at the sample floor outranks the
specification in the mock the next replay is verified against.

Both of those are asserted here as absences now rather than as the presences W116 recorded. The
tests that still pin the writer's absence live in `tests/test_replay_shape_writeback.py`, which
holds the second condition -- a retried replay counting one synthesized body once per attempt --
that this change does not address.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import get_args

import pytest

from sync.core import CallSite, ObservedShape
from sync.core.models import ObservationSource
from sync.detect.observed_drift import MIN_SAMPLES, DeclaredField, ObservedDriftDetector
from sync.graph.sources import SYNTHETIC_SOURCES, TRAFFIC_SOURCES
from sync.graph.store import GraphStore
from sync.remediate.nodes import _observed
from sync.verify.mock_response import synthesize_mock_response

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")

NOW = datetime(2026, 7, 20, 9, 0, tzinfo=timezone.utc)
EARLIER = NOW - timedelta(days=30)

SITE = CallSite(
    repo_id="r1", path="src/billing.ts", line=9, col=23, vendor_id="stripe",
    operation_id="PostCharges", symbol="stripe.charges.create",
    args_keys=["amount"], response_fields_read=["id", "status"],
    sdk_version="18.0.0", content_hash="h1",
)

STATUS_DECLARED_STRING = DeclaredField(
    field_path="/status", json_types=frozenset({"string"}), required=True, nullable=False,
)


@pytest.fixture()
def store() -> GraphStore:
    s = GraphStore(DSN)
    s.apply_schema()
    s.truncate_all()
    return s


def _shape(**over) -> ObservedShape:
    fields = dict(
        vendor_id="stripe", operation_id="PostCharges", field_path="/status",
        json_type="string", source="error-payload", sample_count=1,
        first_seen=NOW, last_seen=NOW,
    )
    fields.update(over)
    return ObservedShape(**fields)


# --- what the store answers ---------------------------------------------------------


def test_a_reader_asking_for_traffic_does_not_receive_a_replay_row(store: GraphStore):
    """The read the two consumers make. A `replay` row is the published specification restated
    through the customer's code, so it is not a response the vendor sent and does not belong in
    an answer either consumer treats as one.
    """
    store.record_observed_shape(_shape(source="error-payload"))
    store.record_observed_shape(_shape(source="replay"))

    rows = store.observed_shapes("stripe", "PostCharges")

    assert [row.source for row in rows] == ["error-payload"]


def test_a_reader_asking_for_every_source_still_receives_every_source(store: GraphStore):
    """The filter is a choice and not a silent narrowing. What the table holds is a real
    question -- an audit of the ingest asks it, and so does any test whose subject is the
    conflict clause rather than the reader.
    """
    store.record_observed_shape(_shape(source="error-payload"))
    store.record_observed_shape(_shape(source="replay"))

    rows = store.observed_shapes("stripe", "PostCharges", traffic_only=False)

    assert sorted(row.source for row in rows) == ["error-payload", "replay"]


def test_an_interceptor_row_is_traffic(store: GraphStore):
    """The classification is not "error-payload and nothing else". The interceptor SDK is
    unbuilt, and its rows are responses the customer's code actually received when it exists --
    so a filter that named only today's single written value would drop the one source the
    specification is most explicit about.
    """
    store.record_observed_shape(_shape(source="interceptor"))

    assert [row.source for row in store.observed_shapes("stripe", "PostCharges")] == [
        "interceptor"
    ]


# --- the classification, and what happens when a fourth source is added -------------


def test_every_declared_observation_source_is_classified():
    """`ObservationSource` is a closed `Literal` in `sync.core`, so a fourth source cannot
    appear without a deliberate edit there. This is what makes the edit reach here too: the
    filter matches positively, so an unclassified source is absent from every baseline rather
    than silently entering one, and absence without a failing test is a detector that quietly
    stops seeing a source somebody built.
    """
    declared = set(get_args(ObservationSource))

    assert TRAFFIC_SOURCES | SYNTHETIC_SOURCES == declared


def test_no_source_is_both_traffic_and_synthetic():
    """A partition rather than two overlapping lists. A source in both would make the filter's
    answer depend on which set the query happened to read."""
    assert TRAFFIC_SOURCES & SYNTHETIC_SOURCES == frozenset()


# --- the two consumers, end to end --------------------------------------------------


def test_one_replay_row_no_longer_escalates_an_uncorroborated_divergence(store: GraphStore):
    """The escalation W116 measured, asserted through the detector rather than by unit.

    `_contradicts_earlier_window` groups siblings by `field_path` and applies no sample floor to
    them, so before this change a single `sample_count=1` replay row with an earlier
    `first_seen` flipped `info` to `breaking` -- on a rationale telling the reviewer the claim
    rested on observed traffic, of a row Sync synthesized from what the vendor published.

    The sibling window is unchanged and is still wrong for traffic; see
    `test_a_traffic_row_under_the_floor_still_escalates`. What changed is that a replay row
    cannot reach it.
    """
    store.upsert_call_site(SITE)
    store.record_observed_shape(
        _shape(json_type="number", source="error-payload", sample_count=MIN_SAMPLES)
    )
    spec = {"PostCharges": [STATUS_DECLARED_STRING]}

    assert [f.severity for f in ObservedDriftDetector(store, spec).scan()] == ["info"]

    store.record_observed_shape(_shape(source="replay", first_seen=EARLIER, last_seen=EARLIER))

    findings = list(ObservedDriftDetector(store, spec).scan())
    assert [f.severity for f in findings] == ["info"]
    assert "the vendor's behaviour changed" not in findings[0].rationale


def test_the_replay_nodes_own_baseline_reader_receives_no_replay_row(store: GraphStore):
    """The feedback loop, closed at the store because it cannot be closed at the caller.

    `_observed` is the reader `make_replay` hands to `synthesize_mock_response`, and it lives in
    `sync.remediate.nodes`. It is imported here rather than reconstructed so this fails if that
    node ever starts reading the table some other way.
    """
    store.record_observed_shape(
        _shape(json_type="number", source="replay", sample_count=MIN_SAMPLES)
    )

    baseline = _observed(store, SITE)
    assert list(baseline) == []

    declared = {"type": "object", "properties": {"status": {"type": "string"}}}
    assert synthesize_mock_response(declared, baseline)["status"].startswith("<sync-mock")


def test_a_traffic_row_at_the_floor_still_reaches_the_mock(store: GraphStore):
    """The filter narrows by source and by nothing else. Observation outranking the
    specification is the point of the mock builder, so a change that quietly cost it every
    observation would have fixed the feedback loop by emptying the baseline.
    """
    store.record_observed_shape(
        _shape(json_type="number", source="error-payload", sample_count=MIN_SAMPLES)
    )

    baseline = _observed(store, SITE)
    assert [row.source for row in baseline] == ["error-payload"]

    declared = {"type": "object", "properties": {"status": {"type": "string"}}}
    assert synthesize_mock_response(declared, baseline)["status"] == 0


# --- rows that were already there ---------------------------------------------------


def test_rows_written_before_the_filter_existed_survive_a_second_apply_schema(store: GraphStore):
    """`apply_schema` is idempotent and runs against databases that already hold rows.

    Asserted against a database holding some rather than inferred from the DDL, because the
    answer this task took adds no column: every row keeps the `source` it was written with, and
    there is no value for a pre-existing row to be given. An answer that had added a
    classification column would have had to prove this and could not have proved it here.
    """
    store.record_observed_shape(_shape(source="error-payload", sample_count=7))
    store.record_observed_shape(_shape(source="replay", sample_count=5))

    store.apply_schema()
    store.apply_schema()

    everything = store.observed_shapes("stripe", "PostCharges", traffic_only=False)
    assert {row.source: row.sample_count for row in everything} == {
        "error-payload": 7, "replay": 5,
    }
    assert [row.source for row in store.observed_shapes("stripe", "PostCharges")] == [
        "error-payload"
    ]


# --- the defect this task did not fix -----------------------------------------------


def test_a_traffic_row_under_the_floor_still_escalates(store: GraphStore):
    """**This pins a defect.** It is the second finding of M3-W119 and is not fixed here.

    `MIN_SAMPLES` gates the row being reported and not the siblings it is compared against, so a
    single `error-payload` row -- one upstream incident, one misbehaving account, which is the
    module docstring's own justification for the floor -- is enough to escalate a divergence to
    `breaking` on the claim that the vendor's behaviour changed. The module says a shape seen
    fewer than `MIN_SAMPLES` times "is not a baseline", and `_contradicts_earlier_window` then
    reads exactly such a row as "the baseline's own history".

    Filtering by source does not touch this and was never going to: the escalation needs one
    row of any source. Fixing it changes the severity of findings against live `error-payload`
    baselines, which needs its own measurement.
    """
    store.upsert_call_site(SITE)
    store.record_observed_shape(
        _shape(json_type="number", source="error-payload", sample_count=MIN_SAMPLES)
    )
    spec = {"PostCharges": [STATUS_DECLARED_STRING]}

    assert [f.severity for f in ObservedDriftDetector(store, spec).scan()] == ["info"]

    store.record_observed_shape(
        _shape(
            json_type="string", source="interceptor", sample_count=1,
            first_seen=EARLIER, last_seen=EARLIER,
        )
    )

    findings = list(ObservedDriftDetector(store, spec).scan())
    assert [f.severity for f in findings] == ["breaking"]
    assert "the vendor's behaviour changed" in findings[0].rationale
