"""Why the replay tier builds `source='replay'` rows and does not write them to the store.

`docs/superpowers/specs/2026-07-26-sync-observed-contract-drift.md` says "every replay run is
also a shape-store writer (`source = 'replay'`), which is how the baseline begins accumulating
before any customer installs anything". `replay_shapes` builds the rows and `make_replay`
carries them out on `RunState`; nothing calls `record_observed_shape` with them.

These tests pin that gap deliberately rather than closing it, and the last three are why. The
same document's borrowed insight is that the baseline is "the responses the customer's code
actually received" -- and a replay row is not one. The mock is synthesized from the vendor's
published specification (`synthesize_mock_response`), so a replay row is the specification
restated through the customer's code, not traffic. Writing it into a table two consumers read
as traffic has three measured consequences, each asserted below against a real server:

- The mock builder takes the store's rows with no `source` filter, and an observation at the
  floor outranks the specification. Replay rows would therefore be fed back into the mock that
  the next replay is verified against.
- `ObservedDriftDetector._contradicts_earlier_window` groups siblings by `field_path` across
  sources and applies no sample floor to them, so *one* replay row is enough to turn an
  uncorroborated divergence into a `breaking` finding whose rationale asserts the vendor's
  behaviour changed.
- `record_observed_shape` converges on one row and not on one count, and `route_after_replay`
  sends a failed replay back through `patch`, so a retried run would count one synthesized
  body once per attempt.

The fixes for the second and third live in `src/sync/detect/` and `src/sync/graph/`. Until
they are made, the tier not writing is the correct behaviour and these tests hold it there.
"""

from __future__ import annotations

import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sync.core import CallSite, ObservedShape, RepoRef
from sync.detect.observed_drift import MIN_SAMPLES, DeclaredField, ObservedDriftDetector
from sync.graph.store import GraphStore
from sync.remediate.nodes import _observed, make_replay
from sync.verify.mock_response import synthesize_mock_response

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
EARLIER = NOW - timedelta(days=30)

STATUS_DECLARED_STRING = DeclaredField(
    field_path="/status", json_types=frozenset({"string"}), required=True, nullable=False,
)


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
    assert store.observed_shapes("stripe", "PostCharges") == []


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
    assert store.observed_shapes("stripe", "PostCharges") == []


def test_a_declined_replay_builds_no_shape_rows_and_writes_none(store, clone):
    """A run that never happened has no body, so there is nothing to decide and nothing to
    write. Asserted against the store rather than against the empty list on the state."""
    result = make_replay(store)({
        "site": SITE, "repo": clone("handles"), "replay_plan": {},
    })

    assert result["replay_outcome"] == "not-attempted"
    assert result["replay_shapes"] == []
    assert store.observed_shapes("stripe", "PostCharges") == []


# --- the three properties that make writing them unsafe today ---------------------


def test_a_second_write_of_one_shape_converges_on_a_row_and_not_on_a_count(store):
    """Measured against the server rather than read off the DDL.

    The row converges, which is the half `CLAUDE.md`'s idempotency rule is usually about. The
    counter does not, and it is the counter `MIN_SAMPLES` reads. So a stage that wrote here
    would be idempotent in rows and not in meaning.
    """
    for _ in range(3):
        store.record_observed_shape(_shape())

    rows = store.observed_shapes("stripe", "PostCharges")
    assert len(rows) == 1
    assert rows[0].sample_count == 3


def test_a_replay_row_at_the_floor_outranks_the_specification_in_the_next_mock(store):
    """The feedback loop. `_observed` reads every row for the operation with no `source`
    filter, and `_decide` prefers an observation at the floor over the specification, so
    replay rows written here would build the mock the next replay is verified against.

    `_observed` is the node's own reader rather than a reconstruction of it, so this fails if
    the node ever starts filtering.
    """
    store.record_observed_shape(
        _shape(json_type="number", sample_count=MIN_SAMPLES)
    )

    baseline = _observed(store, SITE)
    assert [row.source for row in baseline] == ["replay"]

    # Declared a plain string here, so the two answers differ by type rather than by the null
    # `SCHEMA`'s nullable field would produce from the specification alone.
    declared = {"type": "object", "properties": {"status": {"type": "string"}}}
    assert synthesize_mock_response(declared, ())["status"].startswith("<sync-mock")
    assert synthesize_mock_response(declared, baseline)["status"] == 0


def test_one_replay_row_under_the_floor_turns_an_uncorroborated_divergence_breaking(store):
    """The blocker, and the reason no narrower write is available.

    `_contradicts_earlier_window` compares siblings grouped by `field_path` across sources and
    applies no sample floor to them, so a single `sample_count=1` replay row with an earlier
    `first_seen` is enough to escalate. The rationale then tells a reviewer the vendor's
    behaviour changed and that the claim rests on observed traffic -- of a row Sync synthesized
    from what the vendor published.
    """
    store.upsert_call_site(SITE)
    traffic = _shape(
        json_type="number", source="error-payload", sample_count=MIN_SAMPLES,
    )
    store.record_observed_shape(traffic)
    spec = {"PostCharges": [STATUS_DECLARED_STRING]}

    uncorroborated = list(ObservedDriftDetector(store, spec).scan())
    assert [finding.severity for finding in uncorroborated] == ["info"]

    store.record_observed_shape(_shape(first_seen=EARLIER, last_seen=EARLIER))

    corroborated = list(ObservedDriftDetector(store, spec).scan())
    assert [finding.severity for finding in corroborated] == ["breaking"]
    assert "the vendor's behaviour changed" in corroborated[0].rationale
