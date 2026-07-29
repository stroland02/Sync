"""The first quality gate, and the properties that decide whether it is worth having.

`2026-07-27-sync-benchmark-gates.md` allows exactly one gate today -- a directional floor on a
deterministic axis -- and is unambiguous about the two ways one fails: firing constantly until
somebody disables it, or never firing and providing false assurance. What is asserted here is
the second, mostly. A floor that cannot go red is the failure this repository has shipped before,
and the lint that exists because of it is one of the four this change runs.

The score these tests judge is built inline rather than read from `benchmark/corpus/recorded/`.
The recording is the corpus's answer and this file is about the comparison: a test reading the
recording would go green on a gate that compared nothing, because the recording clears every
floor by construction.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.gate_corpus import (
    FALSIFIABLE_NEGATIVES_FLOOR,
    PAIRS_SCORED_FLOOR,
    PRECISION_FLOOR,
    RECALL_FLOOR,
    check,
    main,
    render,
)

RECORDED = Path(__file__).parents[1] / "benchmark" / "corpus" / "recorded"


def _pinned_digest() -> str:
    from scripts.symbol_map_pin import PIN, read_pin

    return read_pin(PIN)["digest"]


def _score(
    true_positives: int = 26,
    false_positives: int = 0,
    false_negatives: int = 0,
    negatives: int = FALSIFIABLE_NEGATIVES_FLOOR,
    pairs_scored: int = PAIRS_SCORED_FLOOR,
) -> dict:
    """A score in the shape `score_corpus.py --json` writes, defaulting to what it recorded."""
    return {
        "pairs_total": 17,
        "pairs_scored": pairs_scored,
        "falsifiable_negatives": [f"pair::site{index}" for index in range(negatives)],
        "symbol_map_digest": _pinned_digest(),
        "accuracy": {
            "precision_by_rung": {
                "static": {
                    "true_positives": true_positives,
                    "false_positives": false_positives,
                    "unlabelled": 0,
                }
            },
            "recall_by_rung": {
                "static": {
                    "true_positives": true_positives,
                    "false_negatives": false_negatives,
                }
            },
        },
    }


# --- the floors are the recorded figures, not numbers near them ---------------------------


def test_every_floor_is_the_figure_the_corpus_recorded():
    """The distinction the whole task turns on. A floor derived from measurement is defensible
    and a floor at a round number is invented, and the specification forbids the second.

    Asserted against the recording rather than against a literal, so a floor moved without the
    corpus moving fails here -- which is the direction that would quietly weaken the gate.
    """
    recorded = json.loads((RECORDED / "2026-07-29-the-hold-back-the-binder-earns.json").read_text(encoding="utf-8"))

    assert PRECISION_FLOOR == recorded["accuracy"]["precision_by_rung"]["static"]["precision"]["value"]
    assert RECALL_FLOOR == recorded["accuracy"]["recall_by_rung"]["static"]["recall"]["value"]
    assert FALSIFIABLE_NEGATIVES_FLOOR == len(recorded["falsifiable_negatives"])
    assert PAIRS_SCORED_FLOOR == recorded["pairs"].__len__()


def test_no_floor_carries_a_tolerance():
    """A tolerance is an invented threshold wearing a safety margin's clothes. The axes are
    deterministic -- byte-identical output across independent runs from clean databases -- so a
    drop is real and there is nothing for slack to absorb.

    The smallest movement the corpus can express is one sample in twenty-six, so a floor with
    any slack at all would pass a score that lost one.
    """
    assert check(_score(true_positives=15, false_positives=1))
    assert check(_score(true_positives=15, false_negatives=1))


# --- what passes -------------------------------------------------------------------------


def test_the_recorded_score_clears_every_floor():
    assert check(_score()) == []


def test_a_score_above_every_floor_clears_them():
    """A gate that only ever passes at exactly the floor would fail the day the pipeline
    improved, which is the "fires constantly" half of the failure."""
    assert check(_score(negatives=9, pairs_scored=20)) == []


# --- what fails, one axis at a time ---------------------------------------------------------


def test_one_false_positive_fails_the_precision_floor():
    """The regression the gate exists for. Before `hold_back` there was no negative the detector
    could fire on, so this could not have happened and the floor would have gated a constant."""
    failures = check(_score(true_positives=15, false_positives=1))

    assert [f.axis for f in failures] == ["binding precision"]
    assert "0.9375" in failures[0].detail
    assert "1.0000" in failures[0].detail


def test_one_missed_break_fails_the_recall_floor():
    """A missed break is the failure the product exists to prevent, which is the argument for
    floors on both axes rather than on precision alone."""
    failures = check(_score(true_positives=15, false_negatives=1))

    assert [f.axis for f in failures] == ["binding recall"]
    assert "0.9375" in failures[0].detail


def test_losing_a_falsifiable_negative_fails_its_own_floor():
    """This floor guards a gate rather than the binder. With no negative the detector could have
    fired on, precision is fixed by how the corpus was built and reads 1.0 through any regression
    that only affects same-operation discrimination -- so the precision floor above would stay
    green while gating nothing."""
    failures = check(_score(negatives=3))

    assert [f.axis for f in failures] == ["falsifiable negatives"]
    assert "gates a constant" in failures[0].detail


def test_an_excluded_pair_fails_the_pairs_floor_even_though_both_rates_hold():
    """The failure one step further up. An exclusion shrinks both denominators and leaves both
    rates at 1.0000, so a corpus that quietly stopped covering a third of itself would clear
    every rate floor."""
    failures = check(_score(true_positives=12, negatives=7, pairs_scored=10))

    assert [f.axis for f in failures] == ["pairs scored"]
    assert check(_score(true_positives=12, negatives=7, pairs_scored=10))[0].detail.startswith("10 of 17")


def test_every_failing_axis_is_reported_rather_than_the_first():
    """A run that stopped at one regression would hide the rest, and a reader deciding whether a
    change is worth its cost needs the whole movement."""
    failures = check(
        _score(true_positives=8, false_positives=4, false_negatives=4, negatives=0, pairs_scored=6)
    )

    assert [f.axis for f in failures] == [
        "binding precision", "binding recall", "falsifiable negatives", "pairs scored",
    ]


# --- a null is not a pass ------------------------------------------------------------------


def test_an_unmeasured_axis_fails_rather_than_passing_silently():
    """`axes.py` reports a null rather than a zero for an axis with no samples, deliberately, and
    a comparison against a null must never silently succeed. The corpus is committed and frozen,
    so an axis with no samples means the scoring stopped covering it."""
    empty = _score()
    empty["accuracy"] = {"precision_by_rung": {}, "recall_by_rung": {}}

    failures = check(empty)

    # The pair count is untouched, so only the two rates fail: an unmeasured axis is a failure
    # of that axis and not a reason to report others that were fine.
    assert [f.axis for f in failures] == ["binding precision", "binding recall"]
    assert all("null" in f.detail for f in failures)


def test_a_missing_score_file_is_not_a_passing_gate(tmp_path, capsys):
    """A gate that treats an absent input as a pass is a gate that turns itself off the first
    time the step before it fails."""
    assert main.__module__

    import sys

    argv = sys.argv
    sys.argv = ["gate_corpus.py", "--score", str(tmp_path / "nothing.json")]
    try:
        assert main() == 2
    finally:
        sys.argv = argv

    assert "not a passing gate" in capsys.readouterr().err


# --- what a reader sees ---------------------------------------------------------------------


def test_the_gate_prints_what_it_compared_even_when_it_passes():
    """A gate that is silent when green cannot be told apart from one that did not run."""
    page = render(_score(), [])

    assert "binding precision" in page
    assert "1.0000" in page
    assert "Every floor cleared." in page


def test_the_gate_names_the_measured_value_beside_the_floor_when_it_fails():
    score = _score(true_positives=15, false_positives=1)
    page = render(score, check(score))

    assert "0.9375" in page
    assert "1 floor(s) not cleared" in page
    assert "never to make a red build green" in page


def test_the_exit_code_is_the_verdict(tmp_path, capsys):
    """CI reads the exit code and nothing else, so the exit code is the gate."""
    import sys

    passing = tmp_path / "pass.json"
    passing.write_text(json.dumps(_score()), encoding="utf-8")
    failing = tmp_path / "fail.json"
    failing.write_text(json.dumps(_score(true_positives=15, false_positives=1)), encoding="utf-8")

    argv = sys.argv
    try:
        sys.argv = ["gate_corpus.py", "--score", str(passing)]
        assert main() == 0
        sys.argv = ["gate_corpus.py", "--score", str(failing)]
        assert main() == 1
    finally:
        sys.argv = argv

    assert "Every floor cleared." in capsys.readouterr().out


def test_the_gate_clears_the_score_the_scorer_actually_records():
    """End to end against the committed recording, which is the artifact CI will judge. The tests
    above use built scores so they can fail; this one is the check that the floors and the
    recording have not drifted apart."""
    recorded = json.loads((RECORDED / "2026-07-29-the-hold-back-the-binder-earns.json").read_text(encoding="utf-8"))
    recorded["pairs_scored"] = len(recorded["pairs"])

    assert check(recorded) == []


def test_a_score_that_does_not_name_its_symbol_map_is_refused():
    """The corpus's second frozen input. Every floor above was measured against one resolution,
    so judging a score taken against another compares two different corpora -- and a score JSON
    is a file, which can arrive from a scorer predating the pin or from a hand edit."""
    score = _score()
    score.pop("symbol_map_digest", None)

    failures = check(score)

    assert "symbol map" in [f.axis for f in failures]
    assert "no symbol map" in next(f for f in failures if f.axis == "symbol map").detail


def test_a_score_naming_a_different_symbol_map_is_refused():
    from scripts.symbol_map_pin import PIN, read_pin

    score = {**_score(), "symbol_map_digest": "0" * 64}

    failures = check(score)

    assert [f.axis for f in failures] == ["symbol map"]
    assert read_pin(PIN)["digest"][:16] in failures[0].detail


def test_a_score_naming_the_pinned_symbol_map_clears_every_floor():
    from scripts.symbol_map_pin import PIN, read_pin

    assert check({**_score(), "symbol_map_digest": read_pin(PIN)["digest"]}) == []
