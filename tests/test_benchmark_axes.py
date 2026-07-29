"""The quality axes, computed before the rows they will read exist.

`docs/superpowers/specs/2026-07-27-sync-benchmark-gates.md` blocks gate tier B on the corpus
holding rows, and it holds none: no real pipeline run has produced one. That blocks the GATE --
a pass/fail verdict in CI -- and not the COMPUTATION, so this is the computation, tested against
synthetic rows so the measurement works the day real ones arrive. Nothing here is wired into CI
and no threshold is asserted, because the spec is explicit that a gate at an invented number
either fires constantly and gets disabled or never fires and gives false assurance.

Two of the tests below exist because of one sentence in that spec: a merge rate over four pull
requests is not a merge rate, and presenting it as one is how a solo founder talks themselves
into a wrong conclusion with nobody in the room to object.
"""

from __future__ import annotations

import json
import os

import pytest

from sync.benchmark import Axis, compute_axes
from sync.core import MigrationOutcome
from sync.graph.store import GraphStore

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")


def _attempt(**over) -> MigrationOutcome:
    fields = dict(
        finding_id="f-1",
        attempt_index=0,
        vendor_id="stripe",
        from_version="2026-05-01",
        to_version="2026-11-01",
        change_kind="response-property-removed",
        change_severity="breaking",
        operation_id="PostCharges",
        path_ptr="/v1/charges",
        language="typescript",
        sdk_version="18.0.0",
        symbol_shape="<client>.<resource>.<verb>",
        arg_arity=2,
        arg_key_hashes=["aaaa", "bbbb"],
        response_fields_touched_count=2,
        strategy="codemod",
        tier=0,
        routing_row="unrouted",
        wall_ms=1000,
        input_tokens=100,
        output_tokens=50,
        static_verify_passed=True,
        terminal_status="opened",
        pr_number=1,
        pr_merged=True,
    )
    fields.update(over)
    return MigrationOutcome(**fields)


# --- an empty corpus is not a corpus of zeros -------------------------------------


def test_an_empty_corpus_reports_no_samples_rather_than_zero():
    """The normal case today, and so the one most likely to be got wrong. "The merge rate is 0%"
    and "no attempts have been recorded" are different statements, and code returning 0.0 for
    both makes the difference unrecoverable by the time anyone reads it.
    """
    axes = compute_axes([])

    assert axes.routing_accuracy.n == 0
    assert axes.routing_accuracy.value is None
    assert axes.tokens_per_merged_patch.value is None
    assert axes.merge_rate_by_change_kind == {}


def test_an_empty_corpus_still_reports_its_counts_as_zero():
    """Counts are genuinely zero -- nothing was recorded. Only the rates are unmeasurable, and
    conflating the two in the other direction would be the same mistake mirrored."""
    counts = compute_axes([]).counts

    assert (counts.attempts, counts.findings) == (0, 0)
    assert (counts.pull_requests_opened, counts.pull_requests_merged) == (0, 0)


def test_every_axis_carries_its_sample_size():
    """An axis that cannot report n is not finished. Asserted over every axis the module
    produces rather than over a chosen few, so a sixth added later cannot skip it."""
    axes = compute_axes([_attempt()])

    reported = [axes.routing_accuracy, axes.tokens_per_merged_patch, axes.wall_ms_per_merged_patch]
    reported += list(axes.merge_rate_by_change_kind.values())
    reported += list(axes.merge_rate_by_tier.values())

    assert reported
    for axis in reported:
        assert isinstance(axis, Axis)
        assert isinstance(axis.n, int)


def test_the_axes_serialise_to_json():
    """Data a caller can compare across runs and later gate on, not printed text. `null` for an
    unmeasured axis survives the round trip, which is the distinction the whole module rests
    on."""
    payload = json.loads(compute_axes([]).model_dump_json())

    assert payload["routing_accuracy"] == {"value": None, "n": 0}


# --- merge rate: split, because unsplit it says nothing ---------------------------


def test_the_merge_rate_splits_by_change_kind():
    """A high rate driven by one easy kind says nothing about the product claim, which is why
    the spec calls the unsplit number meaningless."""
    rows = [
        _attempt(finding_id="f-1", change_kind="easy", pr_number=1, pr_merged=True),
        _attempt(finding_id="f-2", change_kind="easy", pr_number=2, pr_merged=True),
        _attempt(finding_id="f-3", change_kind="hard", pr_number=3, pr_merged=False),
    ]

    by_kind = compute_axes(rows).merge_rate_by_change_kind

    assert by_kind["easy"] == Axis(value=1.0, n=2)
    assert by_kind["hard"] == Axis(value=0.0, n=1)


def test_the_merge_rate_splits_by_tier():
    rows = [
        _attempt(finding_id="f-1", tier=0, pr_number=1, pr_merged=True),
        _attempt(finding_id="f-2", tier=2, pr_number=2, pr_merged=False),
    ]

    by_tier = compute_axes(rows).merge_rate_by_tier

    assert by_tier[0] == Axis(value=1.0, n=1)
    assert by_tier[2] == Axis(value=0.0, n=1)


def test_an_attempt_that_opened_no_pull_request_is_not_in_the_denominator():
    """The denominator is pull requests opened, not attempts made. An attempt abandoned before
    `push_branch` never reached a reviewer, so counting it as an unmerged pull request would
    report the pipeline's abandonment rate under the name of its merge rate."""
    rows = [
        _attempt(finding_id="f-1", pr_number=1, pr_merged=True),
        _attempt(finding_id="f-2", pr_number=None, pr_merged=None, terminal_status="abandoned"),
    ]

    assert compute_axes(rows).merge_rate_by_change_kind["response-property-removed"] == Axis(value=1.0, n=1)


def test_a_pull_request_awaiting_its_webhook_is_not_counted_as_unmerged():
    """`pr_merged` arrives days later by webhook, so null means "not yet known" and not "not
    merged". Reading it as a failure would make every recent run look worse than it was, and the
    number would improve on its own with no change to the pipeline."""
    rows = [
        _attempt(finding_id="f-1", pr_number=1, pr_merged=True),
        _attempt(finding_id="f-2", pr_number=2, pr_merged=None),
    ]

    assert compute_axes(rows).merge_rate_by_change_kind["response-property-removed"] == Axis(value=1.0, n=1)


# --- the grain is one row per attempt --------------------------------------------


def test_routing_accuracy_counts_findings_rather_than_attempts():
    """A finding retried three times contributes three rows and one routing decision. Dividing
    by rows would let a finding that failed repeatedly outvote three that succeeded first time,
    and the axis would move when the retry budget changed rather than when routing did.
    """
    rows = [
        _attempt(finding_id="f-1", attempt_index=0, tier=0, static_verify_passed=False),
        _attempt(finding_id="f-1", attempt_index=1, tier=0, static_verify_passed=False),
        _attempt(finding_id="f-1", attempt_index=2, tier=2, static_verify_passed=True),
        _attempt(finding_id="f-2", attempt_index=0, tier=0, static_verify_passed=True),
    ]

    assert compute_axes(rows).routing_accuracy == Axis(value=0.5, n=2)


def test_a_tier_zero_route_that_fell_back_is_not_accurate():
    """The economic claim the axis tests: a tier-0 route that fails to codemod is worse than
    never having tried, because it spent a verification and then paid for the agent anyway."""
    rows = [
        _attempt(finding_id="f-1", attempt_index=0, tier=0, static_verify_passed=True),
        _attempt(finding_id="f-1", attempt_index=1, tier=2, static_verify_passed=True),
    ]

    assert compute_axes(rows).routing_accuracy == Axis(value=0.0, n=1)


def test_a_finding_never_routed_to_tier_zero_is_outside_the_axis():
    """The denominator is findings routed to tier 0. One sent straight to the agent says nothing
    about whether tier 0 routes well."""
    rows = [_attempt(finding_id="f-1", tier=2, static_verify_passed=True)]

    assert compute_axes(rows).routing_accuracy == Axis(value=None, n=0)


def test_cost_per_merged_patch_charges_the_failed_attempts_too():
    """A patch that merged on its third try cost all three. Dividing only the winning attempt's
    tokens by the merge count would report a margin the pipeline never achieved, which is the
    number that makes the margin assumed rather than real."""
    rows = [
        _attempt(finding_id="f-1", attempt_index=0, input_tokens=100, output_tokens=0,
                 wall_ms=1000, pr_number=None, pr_merged=None),
        _attempt(finding_id="f-1", attempt_index=1, input_tokens=200, output_tokens=100,
                 wall_ms=2000, pr_number=1, pr_merged=True),
    ]

    axes = compute_axes(rows)

    assert axes.tokens_per_merged_patch == Axis(value=400.0, n=1)
    assert axes.wall_ms_per_merged_patch == Axis(value=3000.0, n=1)


def test_an_unmerged_finding_contributes_no_cost_and_no_denominator():
    """Cost per MERGED patch. Folding unmerged work into the numerator without adding to the
    denominator would make the number grow every time the pipeline failed."""
    rows = [
        _attempt(finding_id="f-1", input_tokens=100, output_tokens=0, wall_ms=1000, pr_merged=True),
        _attempt(finding_id="f-2", input_tokens=900, output_tokens=0, wall_ms=9000,
                 pr_number=2, pr_merged=False),
    ]

    assert compute_axes(rows).tokens_per_merged_patch == Axis(value=100.0, n=1)


def test_attempts_and_findings_are_counted_separately():
    """The grain, stated as a count. A caller reading `attempts` as a finding count is the
    mistake the corpus spec names, and the axes report both so it cannot be made silently."""
    rows = [
        _attempt(finding_id="f-1", attempt_index=0),
        _attempt(finding_id="f-1", attempt_index=1),
        _attempt(finding_id="f-2", attempt_index=0),
    ]

    counts = compute_axes(rows).counts

    assert (counts.attempts, counts.findings) == (3, 2)


# --- what precision will need, and what it may not have --------------------------


def test_the_counts_precision_will_need_are_reported():
    """The spec's first deliverable for ground truth is a count rather than a harness, because
    precision needs a labelled reference that does not exist. These are the denominators it will
    divide into once labels arrive."""
    rows = [
        _attempt(finding_id="f-1", pr_number=1, pr_merged=True),
        _attempt(finding_id="f-2", pr_number=2, pr_merged=False),
        _attempt(finding_id="f-3", pr_number=None, pr_merged=None, terminal_status="abandoned"),
    ]

    counts = compute_axes(rows).counts

    assert counts.findings == 3
    assert counts.pull_requests_opened == 2
    assert counts.pull_requests_merged == 1
    assert counts.findings_abandoned == 1


def test_no_axis_is_computed_from_the_salted_argument_hashes():
    """`arg_key_hashes` is salted per deployment, so grouping on it across customers returns one
    bucket per customer and looks exactly like an answer. Asserted by changing only that column
    and requiring the whole result to be identical -- a grouping that reached for it would split
    these two into separate buckets.
    """
    shared = dict(finding_id="f-1", pr_number=1, pr_merged=True)
    ours = [_attempt(**shared, arg_key_hashes=["aaaa", "bbbb"])]
    theirs = [_attempt(**shared, arg_key_hashes=["cccc", "dddd"])]

    assert compute_axes(ours) == compute_axes(theirs)
    assert "aaaa" not in compute_axes(ours).model_dump_json()


# --- against the real reader ------------------------------------------------------


@pytest.fixture()
def store():
    s = GraphStore(DSN)
    s.apply_schema()
    s.truncate_all()
    return s


def test_the_axes_compute_over_rows_read_back_from_the_corpus(store: GraphStore):
    """The computation is pure and takes rows, but it has to compose with the one reader that
    produces them. A column that round-trips differently -- a null arriving as something else --
    would only show up here."""
    store.record_migration_outcome(_attempt(finding_id="f-1", pr_number=1, pr_merged=True))
    store.record_migration_outcome(
        _attempt(finding_id="f-2", attempt_index=0, pr_number=2, pr_merged=False)
    )

    axes = compute_axes(store.migration_outcomes())

    assert axes.counts.attempts == 2
    assert axes.merge_rate_by_change_kind["response-property-removed"] == Axis(value=0.5, n=2)


def test_an_empty_corpus_read_from_the_store_is_unmeasured(store: GraphStore):
    """The state the table is actually in today."""
    axes = compute_axes(store.migration_outcomes())

    assert axes.counts.attempts == 0
    assert axes.routing_accuracy.value is None
