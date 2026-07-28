import json
from pathlib import Path

import pytest

from sync.benchmark.binding import (
    BindingLabel,
    EmittedFinding,
    compute_binding_accuracy,
)

FIXTURES = Path(__file__).parent / "fixtures" / "binding_labels"


def _scenario(name: str):
    """A hand-written label set and the findings it scores, as the models.

    The fixtures are on disk and the loading happens here rather than in
    `compute_binding_accuracy`, which reads nothing: labels arrive from outside the
    pipeline entirely, and a scorer that knew where they lived would have to be
    rewritten the day the answer to that changes.
    """
    raw = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    return (
        [EmittedFinding(**finding) for finding in raw["findings"]],
        [BindingLabel(**label) for label in raw["labels"]],
    )


def _finding(call_site: str, rung: str = "static", change: str = "vc1") -> EmittedFinding:
    return EmittedFinding(call_site_id=call_site, vendor_change_id=change, binding_rung=rung)


def _label(call_site: str, affected: bool, rung: str = "static", change: str = "vc1") -> BindingLabel:
    return BindingLabel(
        call_site_id=call_site, vendor_change_id=change, affected=affected, rung=rung
    )


def _run_scoring(static_genuine: int, observed_genuine: int, per_rung: int = 4):
    """A run emitting `per_rung` findings at each of two rungs, of which the stated
    number are genuine. Every finding is labelled, so precision at a rung is exactly
    the genuine count over `per_rung` and the aggregate is their sum over the total.
    """
    findings, labels = [], []
    for rung, genuine in (("static", static_genuine), ("observed", observed_genuine)):
        for index in range(per_rung):
            site = f"{rung}-{index}"
            findings.append(_finding(site, rung))
            labels.append(_label(site, index < genuine, rung))
    return compute_binding_accuracy(findings, labels)


def test_precision_and_recall_are_different_numbers_over_the_same_input():
    """Two findings of the three that carry a label are genuine, and two of the four
    genuinely affected call sites produced a finding. 2/3 and 2/4 are deliberately
    unequal: a fixture where they coincide passes with the two axes swapped, computed
    from each other, or computed from one denominator.
    """
    findings, labels = _scenario("known_answer")

    result = compute_binding_accuracy(findings, labels)

    assert result.precision.value == pytest.approx(2 / 3)
    assert result.recall.value == pytest.approx(2 / 4)


def test_each_axis_reports_the_sample_size_it_divided_by():
    """The spec is emphatic that a rate without its `n` is not a rate. The two
    denominators also differ here -- three labelled findings against four affected
    call sites -- so a single count reported for both is visible rather than
    plausible.
    """
    findings, labels = _scenario("known_answer")

    result = compute_binding_accuracy(findings, labels)

    assert result.precision.n == 3
    assert result.recall.n == 4


def test_a_finding_with_no_label_is_excluded_and_counted_rather_than_dropped():
    """`cs9` in the fixture has no label, so nothing establishes whether it was
    genuine and it cannot be scored. Dropping it silently would turn a biased sample
    into an unqualified number -- the score would read as if it covered every finding
    the run emitted.
    """
    findings, labels = _scenario("known_answer")

    result = compute_binding_accuracy(findings, labels)

    assert result.unlabelled_findings == 1
    # Excluded means excluded from the denominator too. Four findings were emitted
    # and precision divides by the three that could be judged.
    assert result.precision.n == 3
    assert result.precision_by_rung["static"].unlabelled == 1


def test_the_rung_split_separates_a_binder_that_guesses_from_one_that_does_not():
    """The reason the split is the primary output. The static rung emits five findings
    for one genuine dependency and reaches one of the four call sites it should have;
    the observed rung is right about everything it says and misses nothing. Told only
    that precision is 0.5, nobody can act; told which rung is at 0.2, the next change
    is obvious.
    """
    findings, labels = _scenario("rung_split")

    result = compute_binding_accuracy(findings, labels)

    assert result.precision_by_rung["static"].precision.value == pytest.approx(1 / 5)
    assert result.precision_by_rung["observed"].precision.value == pytest.approx(1.0)
    assert result.recall_by_rung["static"].recall.value == pytest.approx(1 / 4)
    assert result.recall_by_rung["observed"].recall.value == pytest.approx(1.0)


def test_the_aggregate_does_not_hide_the_rung_that_scores_badly():
    """The aggregate is a real number and it is the wrong one to act on. It has to sit
    between the rungs rather than resembling either, which is what a caller handed only
    the aggregate would mistake for the pipeline's behaviour.
    """
    findings, labels = _scenario("rung_split")

    result = compute_binding_accuracy(findings, labels)

    assert result.precision.value == pytest.approx(4 / 8)
    assert result.recall.value == pytest.approx(4 / 7)
    worst = result.precision_by_rung["static"].precision.value
    best = result.precision_by_rung["observed"].precision.value
    assert worst < result.precision.value < best


def test_the_aggregate_follows_from_the_split_and_the_split_does_not_follow_from_it():
    """Why the split is stored and the aggregate derived, rather than the reverse.

    Two runs with identical aggregate precision and opposite rung behaviour: one binder
    guessing beside one that is right, against two binders that are mediocre. A caller
    handed only the aggregate cannot tell them apart and would act on neither
    correctly, which is the information the shape of this type exists to keep.
    """
    lopsided = _run_scoring(static_genuine=1, observed_genuine=4)
    even = _run_scoring(static_genuine=2, observed_genuine=3)

    assert lopsided.precision.value == even.precision.value == pytest.approx(5 / 8)
    assert (
        lopsided.precision_by_rung["static"].precision.value
        != even.precision_by_rung["static"].precision.value
    )
    assert (
        lopsided.precision_by_rung["observed"].precision.value
        != even.precision_by_rung["observed"].precision.value
    )


def test_an_empty_input_reports_a_null_rather_than_a_zero():
    """Zero precision means every finding a run emitted was wrong. No samples means
    nothing was measured. The corpus holds no labels today, so unmeasured is the normal
    answer and the type has to say it rather than raise a false alarm.
    """
    result = compute_binding_accuracy([], [])

    assert result.precision.value is None
    assert result.recall.value is None
    assert result.precision.n == 0
    assert result.recall.n == 0
    assert result.precision_by_rung == {}
    assert result.recall_by_rung == {}


def test_a_labelled_call_site_with_no_finding_lowers_recall_and_does_not_raise_precision():
    """The denominator confusion, which is the failure mode this module is most likely
    to ship with. A genuinely affected call site that produced nothing belongs in
    recall's denominator and in neither half of precision. Folded into precision's
    numerator it would report 3/2; treated as unscoreable it would leave recall at 1.0
    on any input at all.
    """
    findings, labels = _scenario("missed_call_sites")

    result = compute_binding_accuracy(findings, labels)

    assert result.recall.value == pytest.approx(1 / 3)
    assert result.precision.value == pytest.approx(1 / 2)


def test_a_missed_call_site_is_a_false_negative_rather_than_an_exclusion():
    """The other half of the same confusion, and the one an assertion on the rates
    alone cannot reach: the two misses have to be counted somewhere, and the somewhere
    is recall's denominator. Nothing about them is unscoreable -- the label is exactly
    what says they should have been found.
    """
    findings, labels = _scenario("missed_call_sites")

    result = compute_binding_accuracy(findings, labels)

    assert result.unlabelled_findings == 0
    assert result.recall_by_rung["static"].false_negatives == 2
    assert result.recall.n == 3


def test_a_call_site_correctly_left_alone_moves_neither_axis():
    """A true negative -- labelled unaffected, and no finding emitted -- is the
    overwhelming majority of any real repository, and neither precision nor recall has
    a term for it. If it reached a denominator, both numbers would fall as the
    customer's codebase grew.
    """
    findings = [_finding("a")]
    scored = compute_binding_accuracy(findings, [_label("a", True)])
    with_true_negatives = compute_binding_accuracy(
        findings, [_label("a", True), _label("b", False), _label("c", False)]
    )

    assert with_true_negatives.precision == scored.precision
    assert with_true_negatives.recall == scored.recall


def test_a_finding_is_scored_against_the_label_for_its_own_vendor_change():
    """A call site can depend on one changed operation and not another, so the label a
    finding is judged by is the one for its own change. Matching on the call site alone
    would score a finding about `vc2` against the answer for `vc1` and be right by
    accident whenever the two agree.
    """
    result = compute_binding_accuracy(
        [_finding("a", change="vc2")],
        [_label("a", True, change="vc1")],
    )

    assert result.unlabelled_findings == 1
    assert result.precision.value is None
    # The `vc1` call site is still genuinely affected and still produced nothing.
    assert result.recall.value == pytest.approx(0.0)
    assert result.recall.n == 1


def test_two_findings_for_one_call_site_cost_precision_twice_and_recall_once():
    """The asymmetry is in the definitions rather than in this implementation.
    Precision is over findings emitted, and a reviewer reads two of them; recall is
    over call sites genuinely affected, and that call site was reached. Counting the
    duplicate once against precision would forgive a binder that emits the same wrong
    finding repeatedly.
    """
    duplicated = compute_binding_accuracy(
        [_finding("a"), _finding("a")],
        [_label("a", True)],
    )

    assert duplicated.precision.n == 2
    assert duplicated.recall.n == 1
    assert duplicated.recall.value == pytest.approx(1.0)


def test_two_labels_for_one_pair_are_refused_rather_than_silently_resolved():
    """Labels are the one input that arrives from outside the pipeline, so they are a
    boundary and get checked like one. A repeated pair inflates recall's denominator by
    the number of times it appears, and a contradictory one makes the score depend on
    which label was read last -- neither of which is visible in the number that comes
    out.
    """
    with pytest.raises(ValueError, match="cs1"):
        compute_binding_accuracy(
            [_finding("cs1")],
            [_label("cs1", True), _label("cs1", False)],
        )
