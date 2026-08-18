"""The beta-gates job has to publish its report, and be able to prove it did.

**`GITHUB_STEP_SUMMARY` is a different file for every step.** GitHub's own documentation says so
in one line -- *this file is unique to the current step and changes for each step in a job* -- and
everything about the variable's name and lifetime suggests otherwise. So a job that writes the
report in one step and checks it in the next is not checking what it wrote; it is checking an
empty file that nothing has touched.

That is exactly what `ci.yml` did. The check was correct, careful, and unsatisfiable: it reported
*the step summary is empty* on every push and failed the job, which is why no run reached a
completed suite verdict and why Gate 4's last clause could not close through CI at all. A guard
that can never pass is the mirror image of one that can never fail, and this repository has now
found both.

The fix is not to weaken the check. Writing, verifying and publishing belong in one step, against
the file the script actually wrote. This pins that arrangement, because the split reads perfectly
natural -- one step measures, the next validates -- and nothing about it looks wrong.
"""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"

# The variable is per-step, so reading it is only meaningful in the step that wrote it.
STEP_SUMMARY = "$GITHUB_STEP_SUMMARY"


def _steps(job: str) -> list[dict]:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return workflow["jobs"][job]["steps"]


def _script(step: dict) -> str:
    return step.get("run") or ""


def test_no_step_reads_a_step_summary_another_step_wrote():
    """The defect itself, stated as a property rather than as a story.

    A step that reads `GITHUB_STEP_SUMMARY` without also writing it is reading its own empty
    file. It cannot pass, and it cannot report anything true about the step that did write.
    """
    offenders = []
    for step in _steps("beta-gates"):
        script = _script(step)
        reads = f'test -s "{STEP_SUMMARY}"' in script or f'cat "{STEP_SUMMARY}"' in script
        writes = STEP_SUMMARY in script and (">>" in script or "--summary" in script)
        if reads and not writes:
            offenders.append(step.get("name", "<unnamed>"))

    assert not offenders, (
        "GITHUB_STEP_SUMMARY is unique to each step, so these steps read a file no step of "
        f"theirs wrote and can only ever find it empty: {offenders}"
    )


def test_the_report_is_verified_before_it_is_published():
    """An empty report published without complaint is the silent nothing this job exists to refuse.

    The check has to survive the fix. Moving the write and the check into one step is only
    correct if the check is still there afterwards -- otherwise the cure is that the job stops
    noticing, which is what it was built to notice.
    """
    writing = [step for step in _steps("beta-gates") if "--summary" in _script(step)]
    assert len(writing) == 1, "exactly one step should produce the gate report"

    script = _script(writing[0])
    assert "beta_gates.py" in script
    # Emptiness, and then each gate by name -- a report that rendered a header and no verdicts
    # is non-empty and says nothing.
    assert "-s " in script, "the step must refuse an empty report"
    for gate in ("Gate 1", "Gate 2", "Gate 3", "Gate 4"):
        assert gate in script, f"the step must confirm {gate} reached the report"


def test_the_report_reaches_the_step_summary():
    """Verifying a file and never publishing it would satisfy the guard and show the reader nothing."""
    writing = next(step for step in _steps("beta-gates") if "--summary" in _script(step))

    assert f'>> "{STEP_SUMMARY}"' in _script(writing), (
        "the verified report has to be appended to the step summary, or the job checks something "
        "nobody will ever see"
    )


def test_the_suite_verdict_comes_from_the_job_that_runs_on_a_push():
    """Gate 4's last clause reads a verdict CI produced, so which job produces it decides everything.

    `coverage` runs on a schedule and on manual dispatch only. If the verdict were read from it,
    Gate 4 could not close on a push at all and every lane would be waiting for a nightly without
    being told. It is read from `serial`, which runs on the push -- so a completed run does close
    the clause, and this pins that so a later edit cannot quietly move the dependency.
    """
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    beta = workflow["jobs"]["beta-gates"]

    assert beta["needs"] == ["serial"]
    script = " ".join(_script(step) for step in beta["steps"])
    assert "needs.serial.result" in script
    assert "needs.coverage" not in script
