"""The beta gates, measured rather than asserted — and the cases where they cannot be.

Sync's whole argument is that a competing tool shows a reviewer a result and asks them to trust
it. Until now the four beta gates were measured by a coordinator writing prose in chat, which is
that same black box pointed at our own readiness.

**`CANNOT_TELL` is the load-bearing verdict here and most of this file is about it.** A gate script
that reports `MET` because it found no rows would be the worst available instance of the defect
this console exists to remove: absence read as zero. So the rule these tests pin is that an
unreachable source, a missing report and an empty table each produce `CANNOT_TELL`, and only a
source that answered produces `MET` or `NOT_MET`.

The empty-corpus case is the subtle one and it is not theoretical. `B129` found that every scan
truncated `migration_outcome`, so an empty corpus in this repository genuinely cannot distinguish
"no run ever opened a pull request" from "the rows were deleted by a bug that shipped for weeks".
Reporting `NOT_MET` there would be a claim the data does not support.
"""

from __future__ import annotations

from scripts.beta_gates import (
    CANNOT_TELL,
    MET,
    NOT_MET,
    Verdict,
    gate_one_loop_closes,
    gate_two_evidence_exists,
    gate_four_containment_true,
    render,
    render_markdown,
)


class _Unreachable:
    """A store whose every call raises, standing in for Postgres being down."""

    def __init__(self, error: Exception | None = None) -> None:
        self._error = error or ConnectionError("could not connect to localhost:5433")

    def migration_outcomes(self):
        raise self._error


class _Store:
    def __init__(self, outcomes: list[dict]) -> None:
        self._outcomes = outcomes

    def migration_outcomes(self):
        return self._outcomes


def _outcome(**overrides) -> dict:
    row = {
        "finding_id": "f1",
        "attempt_index": 1,
        "is_rehearsal": False,
        "pr_number": None,
        "ci_result": None,
        "pr_merged": None,
    }
    row.update(overrides)
    return row


# --- the verdict vocabulary itself -------------------------------------------------


def test_the_three_verdicts_are_distinct_values() -> None:
    """Three, not two. A boolean gate cannot say "I could not look"."""
    assert len({MET, NOT_MET, CANNOT_TELL}) == 3


def test_a_verdict_carries_its_evidence() -> None:
    """A verdict with no evidence is the prose it replaces, in a fixed-width font."""
    verdict = Verdict(gate="1", name="the loop closes", status=CANNOT_TELL, evidence=["a reason"])

    assert verdict.evidence


def test_a_verdict_refuses_to_be_built_without_evidence() -> None:
    """The one rule that keeps this from decaying into an opinion."""
    try:
        Verdict(gate="1", name="x", status=MET, evidence=[])
    except ValueError:
        return
    raise AssertionError("a Verdict with no evidence was accepted")


# --- an unreachable source is never a failed gate ----------------------------------


def test_an_unreachable_database_cannot_tell_rather_than_failing_gate_one() -> None:
    """The distinction the whole script turns on.

    A database that did not answer says nothing about whether a run ever produced a green pull
    request. Reporting `NOT_MET` would be inventing a measurement from an outage.
    """
    verdict = gate_one_loop_closes(_Unreachable(), resume_built=True)

    assert verdict.status is CANNOT_TELL
    assert any("could not connect" in line for line in verdict.evidence)


def test_an_unreachable_database_cannot_tell_rather_than_failing_gate_two() -> None:
    verdict = gate_two_evidence_exists(_Unreachable(), health_reader=_raising_health)

    assert verdict.status is CANNOT_TELL


def _raising_health(store):
    raise ConnectionError("could not connect to localhost:5433")


# --- an empty corpus is absence, not zero ------------------------------------------


def test_an_empty_corpus_cannot_tell_because_b129_deleted_rows_for_weeks() -> None:
    """No rows is not the same fact as no successes.

    `B129`: every scan truncated `migration_outcome` until it was fixed, so an empty corpus here
    cannot distinguish a loop that never closed from rows a bug removed. This is the exact case
    where a lazier script would print `NOT MET` and be believed.
    """
    verdict = gate_one_loop_closes(_Store([]), resume_built=True)

    assert verdict.status is CANNOT_TELL
    assert any("B129" in line for line in verdict.evidence)


def test_rows_that_exist_and_none_green_is_a_real_not_met() -> None:
    """Once the corpus has answered, zero is a measurement and the gate may fail on it."""
    verdict = gate_one_loop_closes(
        _Store([_outcome(pr_number=None), _outcome(pr_number=None)]), resume_built=True
    )

    assert verdict.status is NOT_MET


def test_a_green_pull_request_meets_the_first_half_but_not_the_gate_without_resume() -> None:
    """Gate 1 is two claims and both have to hold. B7 alone is not the gate."""
    verdict = gate_one_loop_closes(
        _Store([_outcome(pr_number=41, ci_result="passed")]), resume_built=False
    )

    assert verdict.status is NOT_MET
    assert any("resume" in line.lower() for line in verdict.evidence)


def test_a_green_pull_request_and_a_resume_path_meets_gate_one() -> None:
    verdict = gate_one_loop_closes(
        _Store([_outcome(pr_number=41, ci_result="passed")]), resume_built=True
    )

    assert verdict.status is MET


def test_a_rehearsal_row_does_not_count_as_a_real_run() -> None:
    """`sync rehearse` opens no pull request and its rows are marked. Counting one here would be
    the same lie as a fixture standing in for evidence, which is what Gate 2 exists to refuse."""
    verdict = gate_one_loop_closes(
        _Store([_outcome(pr_number=41, ci_result="passed", is_rehearsal=True)]),
        resume_built=True,
    )

    assert verdict.status is not MET


# --- gate two reads what Lane E computed rather than recomputing it ------------------


def test_gate_two_reports_unmeasured_axes_as_absence() -> None:
    health = {
        "summary": {
            "pull_requests_opened": 0,
            "pull_requests_merged": 0,
            "axes_measured_count": 0,
            "total_axes": 5,
            "has_any_samples": False,
        },
        "axes": [{"name": "merge_rate", "status": "unmeasured", "has_samples": False}],
    }

    verdict = gate_two_evidence_exists(_Store([]), health_reader=lambda store: health)

    assert verdict.status is CANNOT_TELL
    assert any("unmeasured" in line or "no samples" in line for line in verdict.evidence)


def test_gate_two_needs_three_of_five_axes_and_says_how_many_it_found() -> None:
    health = {
        "summary": {
            "pull_requests_opened": 9,
            "pull_requests_merged": 4,
            "axes_measured_count": 2,
            "total_axes": 5,
            "has_any_samples": True,
        },
        "axes": [],
    }

    verdict = gate_two_evidence_exists(_Store([_outcome()]), health_reader=lambda s: health)

    assert verdict.status is NOT_MET
    assert any("2" in line and "5" in line for line in verdict.evidence)


def test_gate_two_is_met_with_merge_rate_and_three_axes() -> None:
    health = {
        "summary": {
            "pull_requests_opened": 12,
            "pull_requests_merged": 5,
            "axes_measured_count": 3,
            "total_axes": 5,
            "has_any_samples": True,
        },
        "axes": [],
    }

    verdict = gate_two_evidence_exists(_Store([_outcome()]), health_reader=lambda s: health)

    assert verdict.status is MET


# --- rendering ----------------------------------------------------------------------


def test_render_names_the_verdict_before_the_evidence() -> None:
    """A reader skimming sees the answer; a reader who doubts it reads on."""
    text = render([Verdict(gate="1", name="the loop closes", status=CANNOT_TELL, evidence=["x"])])

    assert "CANNOT TELL" in text
    assert text.index("CANNOT TELL") < text.index("x")


def test_render_spells_cannot_tell_with_a_space_rather_than_an_underscore() -> None:
    """It is read by a person, not parsed by a machine."""
    assert "CANNOT_TELL" not in render(
        [Verdict(gate="1", name="n", status=CANNOT_TELL, evidence=["x"])]
    )


# --- publishing: the meter has to be readable without a clone ------------------------


def _one_of_each() -> list[Verdict]:
    return [
        Verdict(gate="1", name="the loop closes", status=NOT_MET, evidence=["0 green pull requests"]),
        Verdict(gate="2", name="the evidence exists", status=CANNOT_TELL, evidence=["no database here"]),
        Verdict(gate="3", name="the console tells the truth", status=MET, evidence=["signed"]),
    ]


def test_markdown_keeps_cannot_tell_visibly_apart_from_not_met() -> None:
    """The rule the whole meter exists to honour, applied to its own output.

    A reader skimming a summary sees glyphs and bold text before words. If `CANNOT TELL` and
    `NOT MET` render the same, the publication re-introduces exactly the absence-versus-zero
    collapse the script refuses internally, and it does it at the only place anybody looks.
    """
    text = render_markdown(_one_of_each())

    not_met_line = next(line for line in text.splitlines() if "Gate 1" in line)
    cannot_tell_line = next(line for line in text.splitlines() if "Gate 2" in line)

    assert "NOT MET" in not_met_line
    assert "CANNOT TELL" in cannot_tell_line
    marks = {line.split()[0] for line in (not_met_line, cannot_tell_line)}
    assert len(marks) == 2, f"both verdicts render with the same leading mark: {marks}"


def test_markdown_states_the_count_of_each_verdict() -> None:
    """So a reader who reads one line reads the right one."""
    text = render_markdown(_one_of_each())

    assert "1 of 3" in text
    assert "cannot be told" in text.lower()


def test_markdown_never_reports_a_gate_it_did_not_measure_as_met() -> None:
    text = render_markdown([Verdict(gate="4", name="x", status=CANNOT_TELL, evidence=["y"])])

    assert "0 of 1" in text


def test_markdown_carries_the_evidence_under_each_gate() -> None:
    """A verdict without its evidence is the prose this replaced."""
    assert "no database here" in render_markdown(_one_of_each())


# --- gate four reads the suite CI already ran, rather than running it again ----------


def test_a_reported_suite_success_is_used_rather_than_re_run() -> None:
    """The nightly already runs the whole suite and gates on it.

    Running it a second time inside this script would buy a duplicate answer for four minutes,
    which is the waste B111 closed when it stopped one pull request running the suite three
    times. Worse, two runs can disagree, and then the report carries two verdicts about one tree
    with nothing to choose between them. GitHub already knows the answer; this asks it.
    """
    verdict = gate_four_containment_true(run_suite=False, suite_result="success")

    assert any("suite" in line.lower() and "success" in line.lower() for line in verdict.evidence)
    assert not any("not measured" in line for line in verdict.evidence)


def test_a_reported_suite_failure_is_a_real_not_met() -> None:
    """Asserted on the suite line rather than on the gate.

    Gate 4 is already NOT MET for an unrelated reason -- the sandbox is built and unwired -- so
    reading the overall verdict here would pass whatever the suite reported, which is a test that
    cannot fail. What this pins is that a reported failure becomes a failure and says so.
    """
    verdict = gate_four_containment_true(run_suite=False, suite_result="failure")

    assert any("reported failure" in line for line in verdict.evidence)


def test_a_skipped_suite_cannot_tell_rather_than_passing() -> None:
    """`skipped` and `cancelled` are not results. A job that did not run says nothing about the
    tree, and reading either as success is the same fabrication as an empty table read as zero."""
    for reported in ("skipped", "cancelled"):
        verdict = gate_four_containment_true(run_suite=False, suite_result=reported)

        assert any("not a result about the tree" in line for line in verdict.evidence), reported
        assert not any("success" in line.lower() for line in verdict.evidence), reported


def test_no_suite_result_at_all_still_says_it_was_not_measured() -> None:
    verdict = gate_four_containment_true(run_suite=False, suite_result=None)

    assert any("not measured" in line for line in verdict.evidence)
