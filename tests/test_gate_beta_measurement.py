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
    CONSOLE_CLAIM_PATHS,
    gate_four_containment_true,
    read_suite_record,
    record_suite_verdict,
    suite_from_record,
    gate_three_console_truth,
    signature_date,
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


def test_a_resume_path_that_could_not_be_read_is_not_a_resume_path_that_is_absent() -> None:
    """`CI-W365`: the fourth instance of the class `B183`, `B184` and `B185` each turned out to be.

    `_resume_path_exists` read two source files and returned `False` on `OSError`, so a file it
    could not open reported the resume path as **missing**. Gate 1 then failed with the evidence
    line "no resume path, so a review comment leaves the run parked forever" -- a specific claim
    about the code, made on the strength of not having read it.

    This script already argues the opposite of itself six hundred lines earlier, for the database:
    "an unreachable database says nothing about whether a run ever closed the loop." The same
    sentence is true of an unreadable file.
    """
    verdict = gate_one_loop_closes(
        _Store([_outcome(pr_number=41, ci_result="passed")]), resume_built=None
    )

    assert verdict.status is CANNOT_TELL
    assert any("could not" in line.lower() for line in verdict.evidence), (
        f"the verdict has to say it failed to look, not that it looked and found nothing: "
        f"{verdict.evidence}"
    )


def test_an_unreadable_source_file_reports_unknown_rather_than_absent(tmp_path, monkeypatch) -> None:
    """The probe itself, asked about a tree whose files it cannot read.

    Pointed at a directory where neither file exists, which is the `OSError` the handler was
    written for. `None` is the honest answer; `False` is a statement about the code.
    """
    import scripts.beta_gates as beta_gates

    monkeypatch.setattr(beta_gates, "REPO_ROOT", tmp_path)

    assert beta_gates._resume_path_exists() is None


def test_a_source_file_that_is_read_and_lacks_the_path_still_reports_absent(
    tmp_path, monkeypatch
) -> None:
    """The guard, so the fix above cannot become "never say no".

    A tree whose files exist and genuinely do not carry the resume path must still report
    `False` -- otherwise the gate could never fail on this half and the change would have
    replaced a wrong answer with no answer.
    """
    import scripts.beta_gates as beta_gates

    (tmp_path / "src" / "sync" / "remediate").mkdir(parents=True)
    (tmp_path / "src" / "sync" / "forge").mkdir(parents=True)
    (tmp_path / "src" / "sync" / "remediate" / "durable.py").write_text("", encoding="utf-8")
    (tmp_path / "src" / "sync" / "forge" / "webhook.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(beta_gates, "REPO_ROOT", tmp_path)

    assert beta_gates._resume_path_exists() is False


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


def test_with_no_flag_and_no_record_it_says_it_was_not_measured(tmp_path, monkeypatch) -> None:
    """Rewritten by `CI-W306`, and the rewrite is the point rather than a fixup.

    This asserted that no flag means "not measured", which was true when the only sources were two
    flags. It is now false by design: with no flag the gate reads a durable record, which is the
    whole of what that unit fixed. Left alone the test would have pinned the behaviour it was
    landed to remove.

    So it pins the surviving claim — with no flag *and* no record there is nothing to report — and
    points at a record that genuinely does not exist, rather than at the repository's own, which is
    what made the original fail.
    """
    import scripts.beta_gates as beta_gates

    monkeypatch.setattr(beta_gates, "SUITE_RECORD", tmp_path / "absent.json")
    verdict = gate_four_containment_true(run_suite=False, suite_result=None)

    assert any("not measured" in line for line in verdict.evidence)


# --- gate three: what counts as a re-sign, and what counts as a console change -------


def _reports(tmp_path, **docs):
    directory = tmp_path / "reports"
    directory.mkdir()
    for name, body in docs.items():
        (directory / f"{name}.md").write_text(body, encoding="utf-8")
    return directory


def test_a_resign_that_arrives_as_a_new_document_is_seen(tmp_path) -> None:
    """The defect that made this unit necessary, stated as a test.

    The meter had one report path hardcoded, so when Lane B re-signed by landing
    `2026-08-17-gate-3-resign.md` beside the original the meter went on reading the original and
    reported the same stale timestamp as before. A lane that does the work and watches the gate
    ignore it learns that clearing the gate is ceremony, which is how a gate stops being read.
    """
    directory = _reports(
        tmp_path,
        **{
            "2026-08-17-gate-3-screen-pass": "Signed: 2026-08-17T11:10:00-04:00\n",
            "2026-08-17-gate-3-resign": "Signed: 2026-08-17T12:20:00-04:00\n",
        },
    )

    verdict = gate_three_console_truth(directory, console_changed_at="2026-08-17T11:54:54-04:00")

    assert verdict.status is MET
    assert any("resign" in line for line in verdict.evidence)


def test_a_recorded_signature_older_than_the_console_says_so_in_those_words(tmp_path) -> None:
    """The legibility half. A lane whose re-sign did not register must be told why, not left to
    guess -- the answer is almost always that it updated the prose and not the signature line."""
    directory = _reports(
        tmp_path, **{"2026-08-17-gate-3-resign": "Signed: 2026-08-17T09:00:00-04:00\n"}
    )

    verdict = gate_three_console_truth(directory, console_changed_at="2026-08-17T11:54:54-04:00")

    assert verdict.status is CANNOT_TELL
    joined = " ".join(verdict.evidence)
    assert "recorded signature date is older than the console change" in joined
    assert "Signed:" in joined


def test_a_report_with_no_signature_line_names_the_line_to_add(tmp_path) -> None:
    directory = _reports(tmp_path, **{"2026-08-17-gate-3-resign": "# a pass with no marker\n"})

    verdict = gate_three_console_truth(directory, console_changed_at="2026-08-17T11:54:54-04:00")

    assert verdict.status is CANNOT_TELL
    assert any("Signed:" in line for line in verdict.evidence)


def test_no_report_at_all_cannot_tell(tmp_path) -> None:
    directory = tmp_path / "reports"
    directory.mkdir()

    verdict = gate_three_console_truth(directory, console_changed_at="2026-08-17T11:54:54-04:00")

    assert verdict.status is CANNOT_TELL


def test_an_unreadable_console_history_cannot_tell(tmp_path) -> None:
    directory = _reports(
        tmp_path, **{"2026-08-17-gate-3-resign": "Signed: 2026-08-17T12:20:00-04:00\n"}
    )

    verdict = gate_three_console_truth(directory, console_changed_at=None)

    assert verdict.status is CANNOT_TELL


def test_signature_date_reads_the_recorded_line_rather_than_the_prose() -> None:
    assert signature_date("intro\nSigned: 2026-08-17T12:20:00-04:00\nmore") == (
"2026-08-17T12:20:00-04:00"
    )
    assert signature_date("# Gate 3, re-signed - 2026-08-17\nno marker here") is None


# --- the watched set ----------------------------------------------------------------


def test_the_watched_set_names_what_it_excludes_rather_than_what_it_includes() -> None:
    """The abstraction, not the list. An include-list of directory names is invisible-by-default.

    Three names were adopted as a proxy for "the claim surface" and the proxy was wrong: `layouts/`
    renders on every screen -- the deployment-identity sentence sits in the sidebar footer -- and
    was not among them, so Gate 3 read MET across a change it could not see. `lib/`, `vendor/`,
    `App.tsx` and `main.tsx` were missing for the same reason.

    The fix is the same inversion `B129` made when a scan named the one table it spared instead of
    the two it cleared: name the exclusions, so a directory nobody thought about is watched rather
    than invisible. A miss here costs a false MET on a gate about whether screens tell the truth;
    a false positive costs a re-walk.
    """
    assert "web/src" in CONSOLE_CLAIM_PATHS
    excluded = [p for p in CONSOLE_CLAIM_PATHS if p.startswith(":(exclude)")]
    assert excluded, "the watched set is an include-list again, so a new directory is invisible"
    assert not any(
        p.startswith("web/src/") for p in CONSOLE_CLAIM_PATHS
    ), "naming subdirectories reintroduces invisible-by-default"


def test_everything_that_can_render_is_watched() -> None:
    """`layouts/` is the one that was missed; the others were missed for the same reason."""
    for renders in ("web/src/layouts", "web/src/lib", "web/src/vendor", "web/src/App.tsx"):
        assert any(
            renders.startswith(path) or path == "web/src" for path in CONSOLE_CLAIM_PATHS
        ), f"{renders} can put a sentence in front of a reader and is not watched"


def test_a_stylesheet_or_a_test_still_does_not_reopen_the_gate() -> None:
    """Lane B's original complaint, which the widening must not undo.

    A gate that fires on a CSS tweak teaches the lane that clearing it is ceremony. Appearance is
    measured in `DESIGN.md` against rendered pixels, which is a different discipline with a
    different gate.
    """
    joined = " ".join(CONSOLE_CLAIM_PATHS)
    for noisy in (".test.", ".css", ".md"):
        assert noisy in joined, f"{noisy} is no longer excluded, so the gate fires on it"


def test_the_watched_set_is_only_what_can_change_a_claim_about_data() -> None:
    """Watching all of `web/` meant a token, a build config or a script re-opened the gate.

    None of those can change what a screen claims about data, and a gate that fires on a CSS tweak
    teaches the lane that clearing it is ceremony. Narrow, and deliberately conservative: this gate
    can only ever say MET or CANNOT TELL, never NOT MET, so a miss costs a re-walk rather than a
    false pass.
    """
    assert not any(path == "web" for path in CONSOLE_CLAIM_PATHS), (
        "watching all of web/ pulls in build config and tokens, which cannot change a claim"
    )


def test_tests_are_excluded_from_the_watched_set() -> None:
    """A vitest file changing cannot change what a screen asserts to a reader."""
    assert any("exclude" in path and "test" in path for path in CONSOLE_CLAIM_PATHS)


def test_a_structural_cannot_tell_says_it_will_not_change_by_itself() -> None:
    """B171, and it was smaller than filed: the footer already said absence is not zero.

    What was missing is that a reader cannot tell a `CANNOT TELL` that might resolve next run from
    one that is structural to the environment. In CI, gates 1 and 2 will read `CANNOT TELL` on
    every push forever, because CI has no corpus and deliberately gets no database. Left
    unqualified that is indistinguishable from a fresh unknown, and a reader eventually stops
    looking at it -- the same way a gate that fires on a CSS tweak teaches a lane to stop clearing
    it.
    """
    verdicts = [
        Verdict(gate="1", name="the loop closes", status=CANNOT_TELL, evidence=["no corpus"]),
        Verdict(gate="4", name="containment", status=NOT_MET, evidence=["unwired"]),
    ]

    text = render_markdown(verdicts)

    assert "structural" in text
    assert "scripts/beta_gates.py" in text


def test_a_measured_run_does_not_carry_the_structural_note() -> None:
    """Silence is the ordinary case. A run that answered has nothing to explain."""
    text = render_markdown(
        [Verdict(gate="1", name="the loop closes", status=NOT_MET, evidence=["0 green"])]
    )

    assert "structural" not in text


# --- a durable suite verdict, and the staleness it must not paper over ---------------


def test_a_record_for_the_current_commit_answers_the_question(tmp_path) -> None:
    """The lie of omission this closes.

    `main-is-green not measured: pass --run-suite` was printed on every invocation anybody ran,
    while `main` was in fact green. A gate that declines to answer a question it is built to
    answer teaches its reader to skip that line.
    """
    record = tmp_path / "suite.json"
    record_suite_verdict(record, commit="abc123", trustworthy=True, passed=True, summary="3962 passed")

    ok, detail = suite_from_record(record, head="abc123")

    assert ok is True
    assert "3962 passed" in detail


def test_a_record_from_another_commit_cannot_tell_rather_than_reporting_green(tmp_path) -> None:
    """The constraint that matters: a green from forty commits ago is not a statement about now.

    Rebuilding Gate 3's staleness failure inside Gate 4 would be careless, so a record that does
    not describe `HEAD` is absence rather than evidence — and it says which commit it does
    describe, so the reader can decide whether to re-run rather than guess.
    """
    record = tmp_path / "suite.json"
    record_suite_verdict(record, commit="old111", trustworthy=True, passed=True, summary="3962 passed")

    ok, detail = suite_from_record(record, head="new222")

    assert ok is None, "a stale green was reported as a measurement of HEAD"
    assert "old111" in detail and "new222" in detail


def test_a_recorded_failure_is_a_real_not_met(tmp_path) -> None:
    record = tmp_path / "suite.json"
    record_suite_verdict(record, commit="abc123", trustworthy=True, passed=False, summary="3 failed")

    ok, _ = suite_from_record(record, head="abc123")

    assert ok is False


def test_a_recorded_run_that_was_untrustworthy_cannot_tell(tmp_path) -> None:
    """A dead worker's tally is not a verdict, and storing it does not make it one."""
    record = tmp_path / "suite.json"
    record_suite_verdict(
        record, commit="abc123", trustworthy=False, passed=False, summary="60 failed"
    )

    ok, detail = suite_from_record(record, head="abc123")

    assert ok is None
    assert "trust" in detail.lower()


def test_no_record_says_how_to_produce_one(tmp_path) -> None:
    ok, detail = suite_from_record(tmp_path / "absent.json", head="abc123")

    assert ok is None
    assert "--run-suite" in detail


def test_a_record_carries_when_and_against_what(tmp_path) -> None:
    """Both, because either alone is unreadable: a time with no commit cannot be checked against
    the tree, and a commit with no time cannot be aged."""
    record = tmp_path / "suite.json"
    record_suite_verdict(record, commit="abc123", trustworthy=True, passed=True, summary="ok")

    stored = read_suite_record(record)

    assert stored["commit"] == "abc123"
    assert stored["measured_at"], "a record with no timestamp cannot be aged"


def test_run_suite_is_reachable_when_invoked_as_a_script() -> None:
    """The flag the gate's own message told every reader to pass, and it crashed.

    Run as a script, `scripts/` is on `sys.path` and the repository root is not, so
    `import scripts.gate_verdict` inside `_suite_green` raised `ModuleNotFoundError`. Under pytest
    it imports fine, because `pythonpath = ["."]` puts the root on the path — so a green suite hid
    a crash on the one path no test executed.

    Executed in a subprocess rather than imported, because importing it here would use the very
    path setup that hid the defect.
    """
    import subprocess
    import sys as _sys
    from pathlib import Path as _Path

    root = _Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            _sys.executable,
            "-c",
            "import runpy, sys; sys.argv=['beta_gates.py']; "
            "m = runpy.run_path(r'%s', run_name='not_main'); "
            "m['_suite_green']; import scripts.gate_verdict; print('importable')"
            % (root / "scripts" / "beta_gates.py"),
        ],
        cwd=root / "scripts",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )

    assert "importable" in result.stdout, result.stdout + result.stderr
