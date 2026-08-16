"""Why the replay tier builds `source='replay'` rows, does not write them, and will not.

`docs/superpowers/specs/2026-07-26-sync-observed-contract-drift.md` said "every replay run is
also a shape-store writer (`source = 'replay'`), which is how the baseline begins accumulating
before any customer installs anything". **That claim is retired rather than deferred**, and the
specification now says so in its own words. `replay_shapes` builds the rows and `make_replay`
carries them out on `RunState`; nothing calls `record_observed_shape` with them, and nothing
should.

These tests pin that gap deliberately rather than closing it. The same document's borrowed
insight is that the baseline is "the responses the customer's code actually received" -- and a
replay row is not one. The mock is synthesized from the vendor's published specification
(`synthesize_mock_response`), so a replay row is the specification restated, not traffic.
Writing it into a table two consumers read as traffic had three measured consequences:

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
from sync.verify.mock_response import synthesize_mock_response
from sync.verify.replay import replay_shapes

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

# Every construct the synthesizer treats differently, so "the rows add nothing" is measured
# over the whole vocabulary rather than over two strings: an enum, a nullable object with a
# child under it, an array of objects, and each scalar type.
RICH_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "status": {"type": "string", "enum": ["succeeded", "failed"]},
        "amount": {"type": "integer"},
        "live": {"type": "boolean"},
        "data": {
            "type": "object",
            "nullable": True,
            "properties": {"inner": {"type": "string"}},
        },
        "refunds": {
            "type": "array",
            "items": {"type": "object", "properties": {"rid": {"type": "string"}}},
        },
    },
}

# Every pointer `RICH_SCHEMA` declares a field at, the root excluded because the root is the
# response rather than a field in it. Written out rather than walked out of the schema: a
# derivation would reproduce the walk the test compares against, and agree with it however
# wrong both were.
RICH_DECLARED = frozenset({
    "/id", "/status", "/amount", "/live", "/data", "/data/inner",
    "/refunds", "/refunds/-", "/refunds/-/rid",
})

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


def _rows(carried) -> frozenset:
    """The rows a run offered, in a form two runs can be compared on.

    Every column except the timestamps, which are set when the row is built and so differ
    between two runs that agree about everything a row means.
    """
    return frozenset(
        (row["field_path"], row["json_type"], row["nullable_seen"],
         tuple(row["spec_enum_values"]), row["source"], row["sample_count"])
        for row in carried
    )


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


# --- what a replay row is evidence of, which is what retires the claim ------------
#
# The three tests above say the write is safe now. These say it would still be pointless,
# which is a different claim and the one the specification's withdrawn sentence rested on.
# They are deliberately not read through the store: every one of them has to hold with the
# traffic filter and the sample floor both removed, because a test that let either guard
# supply the answer would pass just as well over rows that carried real evidence.


def test_the_rows_a_replay_builds_do_not_depend_on_the_customer_code_it_ran(store, clone):
    """Three runs, three verdicts, one set of rows.

    `replay_call_path` computes the rows from the mock before the child process starts, so
    nothing the customer's code does can reach them -- not the outcome, not which fields were
    read, not whether the call happened at all. `exits_before_the_call` is the sharp case: it
    ends the process while the module is still loading, so the vendor call is never made, and
    it still offers the same rows as a run that passed.

    This is stronger than the description W116 gave these rows. "The published specification
    restated through the customer's code" grants the customer's code a contribution it does
    not make; the rows are the specification restated, and the run is not one of their inputs.
    A row that is identical across a pass, a throw and a run that never happened cannot be an
    observation of anything that happened.
    """
    runs = {
        fixture: make_replay(store)({
            "site": SITE, "repo": clone(fixture), "replay_plan": PLAN,
        })
        for fixture in ("handles", "mishandles", "exits_before_the_call")
    }

    assert [runs[name]["replay_outcome"] for name in ("handles", "mishandles",
                                                      "exits_before_the_call")] == [
        "passed", "threw", "declined",
    ]
    offered = {name: _rows(run["replay_shapes"]) for name, run in runs.items()}
    assert all(rows for rows in offered.values()), "a run offered no rows to compare"
    assert len(set(offered.values())) == 1, offered


def test_reading_a_replay_runs_own_rows_back_leaves_the_mock_unchanged():
    """The measurement the withdrawn claim needed and does not survive.

    "The baseline begins accumulating" is worth saying only if what accumulates changes an
    answer. Here is the answer it was supposed to change: the mock the *next* replay is
    verified against. Feed a run's own rows back at the sample floor and the mock is
    byte-identical to the one built from the specification alone -- for a two-field schema and
    for one carrying an enum, a nullable object, an array and four scalar types.

    A replay row is therefore evidence of nothing. `synthesize_mock_response` is pure and
    deterministic in the schema and the baseline, `replay_shapes` reduces its output, and a
    reduction of a function's output is not a second input to it.

    **Every guard is removed on purpose and this test must stay that way.** The rows are lifted
    to `MIN_SAMPLES` by hand and handed straight to the synthesizer, so neither the traffic
    filter nor the floor can supply the result. Routed through the store instead, the rows
    would be excluded twice over and the mock would be unchanged for reasons that say nothing
    about what the rows contain -- which is the version of this test that passes over rows
    carrying anything at all.
    """
    for schema in (SCHEMA, RICH_SCHEMA):
        from_specification = synthesize_mock_response(schema, ())
        offered = replay_shapes("stripe", "PostCharges", from_specification)
        at_the_floor = tuple(
            shape.model_copy(update={"sample_count": MIN_SAMPLES}) for shape in offered
        )

        assert at_the_floor, "the schema produced no rows to read back"
        assert synthesize_mock_response(schema, at_the_floor) == from_specification


def test_a_replay_row_carries_no_field_and_no_member_the_specification_did_not():
    """The reduction is lossy in one direction and never additive in the other.

    Every path the rows carry is a path the schema declares, and one the schema declares is
    missing: `/data/inner` sits under a nullable parent, so the mock stops at the null and the
    walk never reaches the child. No enum member survives either -- `replay_shapes` retains
    none, by its own docstring, because retaining one needs the published specification and it
    holds only a body.

    This is what makes the retirement permanent rather than a verdict on today's code. The
    claim becomes worth reopening if these rows ever carry something the specification did not
    already say, and this test is what fails on the day they do.
    """
    offered = replay_shapes(
        "stripe", "PostCharges", synthesize_mock_response(RICH_SCHEMA, ())
    )
    carried = {shape.field_path for shape in offered}

    assert carried < RICH_DECLARED
    assert RICH_DECLARED - carried == {"/data/inner"}
    assert not {member for shape in offered for member in shape.spec_enum_values}
