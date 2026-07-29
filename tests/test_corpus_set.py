"""Aggregating a set of scored pairs into one binding number, driven from constructed results.

The split is the one `tests/test_mine_stripe_migrations.py` already uses: running the pipeline
over a checkout is impure and untested here, and everything that turns per-pair results into a
corpus-level number is pure and is all that is asserted on. Nothing here opens a database, reads
a checkout or reaches a network.

The three properties `2026-07-27-sync-benchmark-gates.md` makes non-optional are the three this
file exists to hold: every axis reports its sample size, an axis with no samples reports a null
rather than a zero, and an excluded pair is counted and named rather than swallowed.
"""

from __future__ import annotations

import pytest

from scripts.score_corpus import (
    PairResult,
    aggregate,
    reason_for,
    render,
)
from sync.benchmark.binding import BindingLabel, EmittedFinding
from sync.benchmark.mutate import UnsupportedChangeKind
from sync.benchmark.score import DisplacedLabel, SYNTHETIC_REFERENCE, UnbrokenLabel


def _finding(site: str, change: str = "chg") -> EmittedFinding:
    return EmittedFinding(call_site_id=site, vendor_change_id=change, binding_rung="static")


def _label(site: str, affected: bool, change: str = "chg") -> BindingLabel:
    return BindingLabel(
        call_site_id=site, vendor_change_id=change, affected=affected,
        rung="static" if affected else "unresolved",
    )


def _scored(name: str, findings, labels, unreachable=(), falsifiable=()) -> PairResult:
    affected = sum(1 for label in labels if label.affected)
    return PairResult(
        name=name, scored=True, findings=findings, labels=labels,
        affected_sites=affected, unaffected_sites=len(labels) - affected,
        unreachable_targets=tuple(unreachable),
        falsifiable_negatives=tuple(falsifiable),
    )


# --- pooling, and the sample size that has to travel with it -----------------------


def test_two_pairs_pool_into_one_number_over_both_sample_sizes():
    """A corpus number is over the whole set or it is a per-pair number wearing a corpus label.
    Findings and labels meet on (call site, change), and the call site ids are per repository, so
    pooling is the union rather than a mean of means -- averaging two pairs' precisions would
    weight a one-site pair equally with a six-site one."""
    first = _scored("a", [_finding("a1")], [_label("a1", True), _label("a2", False)])
    second = _scored("b", [_finding("b1")], [_label("b1", True)])

    score = aggregate([first, second])

    assert score.pairs_scored == 2
    assert score.precision.value == 1.0
    assert score.precision.n == 2
    assert score.recall.value == 1.0
    assert score.recall.n == 2
    assert score.affected_sites == 2
    assert score.unaffected_sites == 1


def test_a_miss_and_a_false_positive_move_the_two_axes_apart():
    """The direction that proves the aggregate is arithmetic rather than a constant. One finding
    on an unaffected site costs precision; one affected site with no finding costs recall."""
    pair = _scored(
        "a",
        [_finding("a1"), _finding("a2")],
        [_label("a1", True), _label("a2", False), _label("a3", True)],
    )

    score = aggregate([pair])

    assert score.precision.value == 0.5
    assert score.precision.n == 2
    assert score.recall.value == 0.5
    assert score.recall.n == 2


# --- an axis with no samples is a null and never a zero ----------------------------


def test_a_corpus_that_scored_nothing_reports_nulls_rather_than_zeroes():
    """`axes.py` already refuses to call an unmeasured rate zero, and a thin corpus is exactly
    when that refusal becomes inconvenient to look at. "Precision is 0%" and "nothing was scored"
    are different statements and a report that cannot tell them apart is worse than none."""
    score = aggregate([
        PairResult(name="a", scored=False, reason="displaced-label", detail="2 labels displaced"),
    ])

    assert score.pairs_scored == 0
    assert score.precision.value is None
    assert score.precision.n == 0
    assert score.recall.value is None
    assert score.recall.n == 0


def test_a_scored_pair_that_emitted_nothing_reports_a_null_precision_and_a_zero_recall():
    """The two axes answer different questions and an empty run separates them. Precision has no
    findings to judge, so it is unmeasured; recall has an affected site that produced nothing, so
    it is genuinely zero. Collapsing either into the other hides a real result."""
    score = aggregate([_scored("a", [], [_label("a1", True)])])

    assert score.precision.value is None
    assert score.precision.n == 0
    assert score.recall.value == 0.0
    assert score.recall.n == 1


# --- exclusions are counted and named ----------------------------------------------


def test_every_excluded_pair_is_counted_under_the_reason_it_was_excluded_for():
    """Silent exclusion turns a biased sample into an unqualified number. `score.py` raises
    `DisplacedLabel` and `UnbrokenLabel` precisely so a pair it cannot score is refused rather
    than scored wrongly, and a runner that swallowed either would undo that."""
    score = aggregate([
        _scored("a", [_finding("a1")], [_label("a1", True)]),
        PairResult(name="b", scored=False, reason="displaced-label", detail="3 displaced"),
        PairResult(name="c", scored=False, reason="displaced-label", detail="1 displaced"),
        PairResult(name="d", scored=False, reason="unbroken-label", detail="1 unbroken"),
    ])

    assert score.pairs_total == 4
    assert score.pairs_scored == 1
    assert score.excluded_by_reason == {"displaced-label": 2, "unbroken-label": 1}
    assert [(p.name, p.reason) for p in score.excluded_pairs] == [
        ("b", "displaced-label"), ("c", "displaced-label"), ("d", "unbroken-label"),
    ]


@pytest.mark.parametrize(
    "error,expected",
    [
        (DisplacedLabel("x"), "displaced-label"),
        (UnbrokenLabel("x"), "unbroken-label"),
        (UnsupportedChangeKind("x"), "unsupported-change-kind"),
        (LookupError("x"), "no-call-site-on-the-changed-operation"),
        (KeyError("x"), "malformed-specification"),
        (ValueError("x"), "generator-refused"),
    ],
)
def test_each_refusal_the_harness_can_raise_maps_to_a_named_reason(error, expected):
    """Named rather than counted as one bucket. `UnbrokenLabel` is a defect in the generator and
    `DisplacedLabel` is a property of where the mutation landed; a single "excluded" count would
    make a corpus that cannot be scored look like a corpus that is merely awkward."""
    assert reason_for(error) == expected


def test_an_unrecognised_failure_is_not_quietly_folded_into_a_known_reason():
    """The direction that keeps the mapping honest. A reason nobody wrote down must not be
    reported under one somebody did."""
    assert reason_for(RuntimeError("something else entirely")) is None


# --- unreachable targets are part of the corpus's shape ----------------------------


def test_targets_the_mutation_could_not_attach_to_are_reported_rather_than_dropped():
    """`generate_pair` labels an unreachable target unaffected, which is honest and invisible: it
    silently shrinks the affected population the recall denominator is taken over."""
    score = aggregate([
        _scored("a", [_finding("a1")], [_label("a1", True), _label("a2", False)],
                unreachable=("a2",)),
    ])

    assert score.unreachable_targets == ["a::a2"]


# --- whether precision could have failed at all ------------------------------------


def test_the_negatives_the_detector_could_have_fired_on_pool_across_pairs():
    """Qualified by the pair for the reason the unreachable targets are: a call site id is unique
    within a repository and the corpus pools four of them."""
    score = aggregate([
        _scored("a", [_finding("a1")], [_label("a1", True), _label("a2", False)],
                falsifiable=("a2",)),
        _scored("b", [], [_label("b1", False)], falsifiable=("b1",)),
    ])

    assert score.falsifiable_negatives == ["a::a2", "b::b1"]


def test_a_corpus_with_no_falsifiable_negative_says_the_precision_beside_it_is_a_constant():
    """The frozen corpus is this. Every negative is on another operation or carries no field list,
    so precision 1.0 is what the construction guarantees -- and a directional floor over it would
    be gating a constant, which `2026-07-27-sync-benchmark-gates.md` calls worse than no gate."""
    score = aggregate([_scored("a", [_finding("a1")], [_label("a1", True), _label("a2", False)])])

    rendered = render(score, reference=SYNTHETIC_REFERENCE)

    assert score.falsifiable_negatives == []
    assert "no negative the detector could have fired on" in rendered
    assert "gate a constant" in rendered


def test_a_corpus_holding_one_does_not_carry_that_warning():
    """The warning has to disappear when it stops being true, or it is a banner rather than a
    measurement and the next reader learns to skip it."""
    score = aggregate([
        _scored("a", [_finding("a1")], [_label("a1", True), _label("a2", False)],
                falsifiable=("a2",)),
    ])

    rendered = render(score, reference=SYNTHETIC_REFERENCE)

    assert "gate a constant" not in rendered
    assert "falsifiable negatives  1" in rendered


# --- the reference travels with the number -----------------------------------------


def test_rendering_refuses_to_state_a_score_without_the_reference_it_was_taken_over():
    """`report.py` makes the same refusal and for the same reason: a precision without what the
    labels were derived from is a number claiming to describe the binder when it partly describes
    the corpus."""
    score = aggregate([_scored("a", [_finding("a1")], [_label("a1", True)])])

    with pytest.raises(ValueError, match="reference"):
        render(score, reference=None)


def test_the_rendered_report_carries_the_sentence_the_number_must_not_outlive():
    """`SYNTHETIC_REFERENCE` ends by saying a binder scoring well here has been shown to handle
    the mechanical case and nothing more. That sentence is the one most likely to be dropped when
    the number looks good, so it is asserted rather than trusted."""
    score = aggregate([_scored("a", [_finding("a1")], [_label("a1", True)])])

    rendered = render(score, reference=SYNTHETIC_REFERENCE)

    assert "has been shown to handle the mechanical case, and nothing more" in rendered
    assert "n=1" in rendered


def test_a_pair_that_contributed_no_positives_is_visible_beside_the_ones_that_did():
    """The exclusion the exclusion count cannot catch. A pair whose every target was unreachable
    is scored, counted in the pair total, and carries no information about the binder -- so a
    corpus total that only reported ten scored pairs would overstate its own sample."""
    score = aggregate([
        _scored("rich", [_finding("r1")], [_label("r1", True), _label("r2", False)]),
        _scored("empty", [], [_label("e1", False)], unreachable=("e1",)),
    ])

    rendered = render(score, reference=SYNTHETIC_REFERENCE)
    empty = [line for line in rendered.splitlines() if line.split()[:1] == ["empty"]]

    assert score.pairs_scored == 2
    assert len(empty) == 1
    assert empty[0].split()[1:] == ["0", "1", "0", "1"]


def test_the_rendered_report_names_every_exclusion_beside_the_score():
    """Beside it rather than below a fold. An exclusion count in a JSON file nobody opens is a
    silent exclusion with extra steps."""
    score = aggregate([
        _scored("a", [_finding("a1")], [_label("a1", True)]),
        PairResult(name="b", scored=False, reason="displaced-label", detail="3 displaced"),
    ])

    rendered = render(score, reference=SYNTHETIC_REFERENCE)

    assert "displaced-label" in rendered
    assert "b" in rendered
