"""Why the replay tier builds `source='replay'` rows and does not write them to the store.

`docs/superpowers/specs/2026-07-26-sync-observed-contract-drift.md` says "every replay run is
also a shape-store writer (`source = 'replay'`), which is how the baseline begins accumulating
before any customer installs anything". `replay_shapes` builds the rows and `make_replay`
carries them out on `RunState`; nothing calls `record_observed_shape` with them.

These tests pin that gap deliberately rather than closing it. The same document's borrowed
insight is that the baseline is "the responses the customer's code actually received" -- and a
replay row is not one. The mock is synthesized from the vendor's published specification
(`synthesize_mock_response`), so a replay row is the specification restated through the
customer's code, not traffic. Writing it into a table two consumers read as traffic had three
measured consequences:

- The mock builder took the store's rows with no `source` filter, and an observation at the
  floor outranks the specification, so replay rows would be fed back into the mock the next
  replay is verified against. **Closed by M3-W119.**
- `ObservedDriftDetector._contradicts_earlier_window` groups siblings by `field_path` across
  sources and applies no sample floor to them, so *one* replay row was enough to turn an
  uncorroborated divergence into a `breaking` finding whose rationale asserts the vendor's
  behaviour changed. **Closed by M3-W119.**
- `record_observed_shape` converged on one row and not on one count, and `route_after_replay`
  sends a failed replay back through `patch`, so a retried run would have counted one
  synthesized body once per attempt. **Closed by M3-W124.**

`GraphStore.observed_shapes` now answers with traffic alone unless a caller asks for every
source, which closed the first two together -- one of the two readers is
`sync.remediate.nodes._observed`, so no argument a caller could have been made to pass would
have reached it. `docs/superpowers/reports/2026-07-31-traffic-and-non-traffic-shapes.md`
carries the argument.

The two tests that recorded those consequences were retired here rather than inverted here.
Each is now asserted as an absence in `tests/test_observed_shape_sources.py`, which is where
the change that closed it lives, and each sits beside the traffic counterpart that keeps the
absence from being vacuous -- `test_the_replay_nodes_own_baseline_reader_receives_no_replay_row`
beside `test_a_traffic_row_at_the_floor_still_reaches_the_mock`, and
`test_one_replay_row_no_longer_escalates_an_uncorroborated_divergence` beside
`test_a_traffic_row_under_the_floor_still_escalates`. Neither property lost an assertion; both
gained one. Leaving inverted copies here as well would have put this file's name over a claim
about the store's reader rather than about the writer this file is named for.

The third was answered at the conflict clause rather than by either shape W116 named. A run key
changes which row the addition lands in and the retry writes the same key twice; a write point
outside the retry loop bounds the retry multiplier and leaves the run multiplier, which is the
one that reaches the sample floor. `sample_count` now adds for traffic sources and holds at the
largest single claim for synthetic ones, so the rows a replay run offers converge however often
they are written. `docs/superpowers/reports/2026-08-03-a-retried-replay-converges.md` carries
the measurements.

**The writer is still not reinstated and these tests still hold it out**, because closing a
condition is not the same as making the write correct. Reinstating it is its own task with its
own before-and-after, and it inherits one question this one does not answer: with both consumers
reading traffic alone, no caller reads a `replay` row, so what the rows are for has to be
established before they are written.
"""

from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sync.core import CallSite, ObservedShape, RepoRef
from sync.detect.observed_drift import MIN_SAMPLES
from sync.graph.store import GraphStore
from sync.remediate.nodes import make_replay
from sync.remediate.state import MAX_STATIC_ATTEMPTS

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")

FIXTURES = Path(__file__).parent / "fixtures" / "replay"
TARGET = "src/billing.ts"

# The new specification marks `status` nullable, so the mock sends the null. `handles` survives
# it and `mishandles` dereferences it, which is what makes one replay pass and the other fail.
SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "status": {"type": "string", "nullable": True},
    },
}

SITE = CallSite(
    repo_id="r1", path=TARGET, line=9, col=23, vendor_id="stripe",
    operation_id="PostCharges", symbol="stripe.charges.create",
    args_keys=["amount", "currency"], response_fields_read=["id", "status"],
    sdk_version="18.0.0", content_hash="h1",
)

PLAN = {
    "schema": SCHEMA,
    "export": "charge",
    "vendor_packages": ["stripe"],
    "arguments": [1000],
}

NOW = datetime(2026, 7, 20, 9, 0, tzinfo=timezone.utc)


@pytest.fixture()
def store() -> GraphStore:
    s = GraphStore(DSN)
    s.apply_schema()
    s.truncate_all()
    return s


@pytest.fixture()
def clone(tmp_path: Path):
    def make(fixture: str) -> RepoRef:
        shutil.copytree(FIXTURES / fixture, tmp_path, dirs_exist_ok=True)
        return RepoRef(
            repo_id="r1", url="https://example.invalid/r",
            local_path=str(tmp_path), head_sha="0" * 40,
        )

    return make


def _shape(**over) -> ObservedShape:
    fields = dict(
        vendor_id="stripe", operation_id="PostCharges", field_path="/status",
        json_type="string", source="replay", sample_count=1,
        first_seen=NOW, last_seen=NOW,
    )
    fields.update(over)
    return ObservedShape(**fields)


# --- what one replay run does to the store ----------------------------------------
#
# All three read with `traffic_only=False`, and that is what keeps them as strong as M3-W116
# wrote them. The rows a reinstated writer would add carry `source='replay'`, so the default
# answer excludes exactly the rows these tests exist to catch and would stay `[]` through the
# writer being switched back on. `_writes_nothing` is the read, so there is one place to be
# right about it.


def _writes_nothing(store) -> bool:
    """No row of any source, which is the only read that can see a replay writer return."""
    return store.observed_shapes("stripe", "PostCharges", traffic_only=False) == []


def test_a_successful_replay_builds_shape_rows_and_writes_none_of_them(store, clone):
    """The rows exist on the state and the store is empty, which is the gap the audit found.

    Asserted as a conjunction rather than as an empty store: a test that only checked the
    store would keep passing if replay stopped building the rows at all.
    """
    result = make_replay(store)({
        "site": SITE, "repo": clone("handles"), "replay_plan": PLAN,
    })

    assert result["replay_outcome"] == "passed"
    assert result["replay_shapes"], "replay built no shape rows to write"
    assert _writes_nothing(store)


def test_a_failed_replay_builds_shape_rows_and_writes_none_of_them(store, clone):
    """The decision, not an accident: a failed replay writes no shapes either.

    A failed replay did observe a body, and the body is a fact about the specification while
    the failure is a fact about the patch -- which is the argument for writing it. It loses to
    the retry loop. `route_after_replay` sends this outcome back to `patch`, and
    `record_observed_shape` adds to `sample_count` on conflict, so writing here would count one
    synthesized body once per attempt. `CLAUDE.md`'s "abandoned runs are data" does not reach
    this: it is about `abandon_reason` staying queryable on the migration corpus, whose grain
    is one row per attempt, and `observed_shape`'s grain is one row per shape with a counter.
    """
    result = make_replay(store)({
        "site": SITE, "repo": clone("mishandles"), "replay_plan": PLAN,
    })

    assert result["replay_outcome"] == "threw"
    assert result["replay_shapes"], "a failed replay still built shape rows"
    assert _writes_nothing(store)


def test_a_declined_replay_builds_no_shape_rows_and_writes_none(store, clone):
    """A run that never happened has no body, so there is nothing to decide and nothing to
    write. Asserted against the store rather than against the empty list on the state."""
    result = make_replay(store)({
        "site": SITE, "repo": clone("handles"), "replay_plan": {},
    })

    assert result["replay_outcome"] == "not-attempted"
    assert result["replay_shapes"] == []
    assert _writes_nothing(store)


# --- the property that made writing them unsafe, now closed -----------------------


def test_a_second_write_of_one_replay_shape_converges_on_a_row_and_on_a_count(store):
    """Measured against the server rather than read off the DDL.

    **This assertion changed direction.** M3-W116 wrote it as `sample_count == 3` and named the
    counter as the half of `CLAUDE.md`'s idempotency rule the table did not satisfy: the row
    converged, the counter did not, and the counter is what `MIN_SAMPLES` reads. The conflict
    clause now adds for traffic sources and holds for synthetic ones, so the counter converges
    too and the old figure is the defect rather than the behaviour.

    Read with `traffic_only=False`, which is the read the subject requires rather than a
    concession to the filter. The rows written here are `replay` rows and the question is what
    the conflict clause did to them; the traffic answer would be empty whether the second write
    had merged, added or been discarded, so it cannot tell those apart.
    """
    for _ in range(3):
        store.record_observed_shape(_shape())

    rows = store.observed_shapes("stripe", "PostCharges", traffic_only=False)
    assert len(rows) == 1
    assert rows[0].sample_count == 1


def test_a_second_write_of_one_traffic_shape_still_counts_twice(store):
    """The counterpart, here rather than only in `tests/test_observed_shape_sources.py`,
    because the test above is where a reader arrives at the inverted assertion and a frozen
    counter would satisfy it just as well as a source-aware one. Two error payloads carrying
    one shape are two samples, and the sample floor the detector depends on is unenforceable
    if this stops being true.
    """
    for _ in range(3):
        store.record_observed_shape(_shape(source="error-payload"))

    rows = store.observed_shapes("stripe", "PostCharges")
    assert len(rows) == 1
    assert rows[0].sample_count == 3


def test_the_rows_a_retried_replay_would_write_converge_over_the_whole_retry_budget(
    store, clone
):
    """Condition (2), asserted over the rows a real replay run built.

    `route_after_replay` sends a failed replay back to `patch`, so `mishandles` is the fixture
    that reaches this: its outcome is the one that re-enters the loop, and `MAX_STATIC_ATTEMPTS`
    bounds how often. Each pass synthesizes the same mock from the same schema against the same
    traffic-only baseline, so each pass offers these same rows -- which is why writing them once
    per attempt is one piece of evidence written three times rather than three observations.

    The rows come out of `make_replay` rather than being hand-built, so this fails if the tier
    ever starts producing rows the store merges some other way.
    """
    result = make_replay(store)({
        "site": SITE, "repo": clone("mishandles"), "replay_plan": PLAN,
    })
    assert result["replay_outcome"] == "threw"
    shapes = [ObservedShape(**row) for row in result["replay_shapes"]]
    assert shapes, "a failed replay still built shape rows"

    for _ in range(MAX_STATIC_ATTEMPTS):
        for shape in shapes:
            store.record_observed_shape(shape)

    rows = store.observed_shapes("stripe", "PostCharges", traffic_only=False)
    assert len(rows) == len(shapes)
    assert {row.sample_count for row in rows} == {1}


def test_no_number_of_replays_lifts_a_synthesized_shape_over_the_sample_floor(store, clone):
    """The harm W116 measured, stated as the property that now forbids it.

    `MIN_SAMPLES` is justified by the rule of three over thirty *independent* samples. Thirty
    replays are one synthesized body observed thirty times, which would satisfy the number with
    none of the statistical content it was chosen for -- reachable in as few as ten findings
    once the retry budget is spent. The floor is not crossed at any repetition count now, so the
    argument does not have to be made again by whoever reinstates the writer.
    """
    result = make_replay(store)({
        "site": SITE, "repo": clone("handles"), "replay_plan": PLAN,
    })
    shapes = [ObservedShape(**row) for row in result["replay_shapes"]]

    for _ in range(MIN_SAMPLES):
        for shape in shapes:
            store.record_observed_shape(shape)

    rows = store.observed_shapes("stripe", "PostCharges", traffic_only=False)
    assert max(row.sample_count for row in rows) < MIN_SAMPLES
