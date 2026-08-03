"""Traffic and non-traffic rows are kept apart on read, and merged differently on write.

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
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import get_args

import pytest

from sync.core import CallSite, ObservedShape, RepoRef
from sync.core.models import ObservationSource
from sync.detect.observed_drift import MIN_SAMPLES, DeclaredField, ObservedDriftDetector
from sync.graph.sources import SYNTHETIC_SOURCES, TRAFFIC_SOURCES
from sync.graph.store import GraphStore
from sync.remediate.nodes import _observed, make_replay
from sync.verify.mock_response import synthesize_mock_response

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")

FIXTURES = Path(__file__).parent / "fixtures" / "replay"

NOW = datetime(2026, 7, 20, 9, 0, tzinfo=timezone.utc)
EARLIER = NOW - timedelta(days=30)

SITE = CallSite(
    repo_id="r1", path="src/billing.ts", line=9, col=23, vendor_id="stripe",
    operation_id="PostCharges", symbol="stripe.charges.create",
    args_keys=["amount", "currency"], response_fields_read=["id", "status"],
    sdk_version="18.0.0", content_hash="h1",
)

REPLAY_PLAN = {
    "schema": {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "status": {"type": "string", "nullable": True},
        },
    },
    "export": "charge",
    "vendor_packages": ["stripe"],
    "arguments": [1000],
}

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


# --- what the store does with a row it already holds ---------------------------------
#
# The same partition, applied to the conflict clause. `sample_count` is the one column in that
# clause whose merge is not idempotent, and idempotence is what `CLAUDE.md` requires of a stage
# re-run on the same input. For traffic the addition is right and is the reason the column
# exists: two error payloads carrying one shape are two samples. For a synthetic source the
# second write is the same constructed body again, so adding would count how often Sync ran.
#
# Both directions are parametrised over the sets rather than over the values written here, so a
# fourth source added to `sync.graph.sources` arrives with a merge assertion instead of taking
# whichever branch it happens to fall into.


@pytest.mark.parametrize("source", sorted(TRAFFIC_SOURCES))
def test_a_traffic_row_written_again_counts_again(store: GraphStore, source: str):
    """The counterpart that keeps the synthetic assertion below from reading as a frozen
    counter. A clause that stopped counting for every source would satisfy that test and
    destroy the sample floor, which is the failure mode this pair exists to separate.
    """
    for _ in range(3):
        store.record_observed_shape(_shape(source=source))

    rows = store.observed_shapes("stripe", "PostCharges", traffic_only=False)
    assert [row.sample_count for row in rows] == [3]


@pytest.mark.parametrize("source", sorted(SYNTHETIC_SOURCES))
def test_a_synthetic_row_written_again_does_not_count_again(store: GraphStore, source: str):
    """A synthetic row is a body Sync constructed, so writing it a second time is the ingest
    running a second time and not the shape being seen a second time. The count is one sample
    however many times the write happens.
    """
    for _ in range(3):
        store.record_observed_shape(_shape(source=source))

    rows = store.observed_shapes("stripe", "PostCharges", traffic_only=False)
    assert [row.sample_count for row in rows] == [1]


def test_a_synthetic_count_written_before_this_clause_is_not_rewritten(store: GraphStore):
    """Rows already in a database were written under a clause that added, so some hold counts
    above one. Taking the incoming value would rewrite that history on the next write, which is
    a migration performed silently by a merge rather than a merge holding a counter still.
    """
    store.record_observed_shape(_shape(source="replay", sample_count=5))
    store.record_observed_shape(_shape(source="replay", sample_count=1))

    rows = store.observed_shapes("stripe", "PostCharges", traffic_only=False)
    assert [row.sample_count for row in rows] == [5]


def test_a_synthetic_rows_count_does_not_depend_on_arrival_order(store: GraphStore):
    """Every other column in this clause merges the same way whichever write lands first --
    `LEAST`, `GREATEST`, `OR`, a union -- because sources do not arrive in order. Keeping
    whatever the row already held would make the counter the one column that reads the
    sequence, which is the property `test_an_observation_arriving_out_of_order_does_not_rewind
    _the_window` already refuses for the timestamps.
    """
    store.record_observed_shape(_shape(source="replay", field_path="/a", sample_count=5))
    store.record_observed_shape(_shape(source="replay", field_path="/a", sample_count=1))
    store.record_observed_shape(_shape(source="replay", field_path="/b", sample_count=1))
    store.record_observed_shape(_shape(source="replay", field_path="/b", sample_count=5))

    rows = store.observed_shapes("stripe", "PostCharges", traffic_only=False)
    assert {row.field_path: row.sample_count for row in rows} == {"/a": 5, "/b": 5}


def test_a_synthetic_row_written_again_still_gains_evidence_and_widens_its_window(
    store: GraphStore,
):
    """Only the counter is held. `DO NOTHING` for synthetic sources would converge too, and
    would throw away the rest of the merge: a later write proving the field can be null, or an
    enum member an earlier specification did not name, or the window this row covers. The row
    still records that the shape was seen and when -- it stops recording how many times the
    write happened.
    """
    later = NOW + timedelta(days=1)
    store.record_observed_shape(_shape(source="replay", nullable_seen=False))
    store.record_observed_shape(
        _shape(
            source="replay", nullable_seen=True, spec_enum_values=["succeeded"],
            first_seen=EARLIER, last_seen=later,
        )
    )

    row = store.observed_shapes("stripe", "PostCharges", traffic_only=False)[0]
    assert row.sample_count == 1
    assert row.nullable_seen is True
    assert row.spec_enum_values == ["succeeded"]
    assert (row.first_seen, row.last_seen) == (EARLIER, later)


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


def test_the_baseline_a_replay_run_hands_the_mock_builder_carries_traffic_alone(
    store: GraphStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """The one link the two tests above leave to be read off the source rather than measured.

    They establish that `_observed` answers with traffic and that the mock builder honours what
    it is handed. That `_observed` is what a replay run actually uses is a single argument at
    one line of `sync.remediate.nodes`, and a change there that built the baseline some other
    way would leave both of them passing. So this records what reaches
    `synthesize_mock_response` during a real `make_replay`, with one row of each kind in the
    table -- naming the traffic row as well as the absent replay row, because an assertion on
    the absence alone would also hold if the baseline arrived empty.
    """
    store.record_observed_shape(
        _shape(json_type="number", source="error-payload", sample_count=MIN_SAMPLES)
    )
    store.record_observed_shape(
        _shape(json_type="boolean", source="replay", sample_count=MIN_SAMPLES)
    )

    handed: list[tuple[str, ...]] = []
    build = synthesize_mock_response

    def spy(schema, observed=(), **kwargs):
        observed = tuple(observed)
        handed.append(tuple(row.source for row in observed))
        return build(schema, observed, **kwargs)

    monkeypatch.setattr("sync.verify.mock_response.synthesize_mock_response", spy)

    shutil.copytree(FIXTURES / "handles", tmp_path, dirs_exist_ok=True)
    repo = RepoRef(
        repo_id="r1", url="https://example.invalid/r",
        local_path=str(tmp_path), head_sha="0" * 40,
    )

    make_replay(store)({"site": SITE, "repo": repo, "replay_plan": REPLAY_PLAN})

    assert handed == [("error-payload",)]


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


def test_a_held_synthetic_count_survives_a_second_apply_schema_and_a_further_write(
    store: GraphStore,
):
    """The same assertion for the clause rather than for the column list, because the clause is
    what this task changed. A `replay` row at 5 was written under a clause that added, and it
    has to come through both a re-applied schema and a further write intact -- neither reset to
    1 nor advanced to 6.
    """
    store.record_observed_shape(_shape(source="replay", sample_count=5))

    store.apply_schema()
    store.apply_schema()
    store.record_observed_shape(_shape(source="replay"))

    rows = store.observed_shapes("stripe", "PostCharges", traffic_only=False)
    assert [row.sample_count for row in rows] == [5]


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
