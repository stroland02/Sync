"""Three properties of `ci.yml` that decide whether a green run means anything.

`tests/test_ci_runs_the_serial_scheduler.py` and `tests/test_ci_stages_the_corpus_inputs.py`
already pin *which* steps exist and in what order. What none of them asked is whether the suite
those steps run can reach its inputs, and whether anybody looks at the answer. Measured on run
`32024607194`: eleven of the twenty-three failures were a resource the runner never had, and the
nightly -- the only run on a schedule -- discarded a failing suite's exit code and reported
success for a hundred commits.

**A pytest step needs the frozen corpus.** `sync.rehearse.fixture` refuses without it, by name,
and `sync rehearse` is the only end-to-end exercise of the pipeline that opens no pull request.
The `test` job did fetch it -- after the suite had already run, which is the same as not fetching
it at all and looks like a step that is present.

**A pytest step's exit code is the whole of what it reports.** Exit 1 is a failing test. A step
that captures the status and re-raises only above 1 passes a failing suite straight through; that
is what the nightly did. Coverage still gates nothing, and nothing here asks it to: no
`--cov-fail-under` is passed anywhere, so a number cannot fail a build. What may not be discarded
is pytest's own verdict.

**A run that died is not a result.** A crashed xdist worker prints `F` against every test it
never got to, so a job can report a tally that counts absences as failures. B152 measured three
runs of one tree reporting thirty, sixty and one failure; two had a dead worker in them. CI has
the same blind spot the local gate had, and the answer is the same one: capture the output and
ask `scripts/gate_verdict.py` whether the verdict can be believed, separately from whether the
suite passed.

**The nightly has to gate something.** A schedule whose every job is either excluded by an `if`
or unable to fail is a green tick that asserts nothing, which is strictly worse than a red one --
a red build is information.

The `if` reading below is a substring match over the three shapes this workflow uses rather than
a GitHub expression evaluator. A fourth shape would need it widened, and that is the honest limit
of what this file checks.
"""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"

CORPUS_FETCH = "scripts/fetch_corpus_repositories.py"


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _script(step: dict) -> str:
    return step.get("run") or ""


def _pytest_steps(job: dict) -> list[tuple[int, dict]]:
    """Every (index, step) in `job` that runs the Python suite.

    `uv run sync rehearse` and `scripts/rehearse_smoke.py` are not pytest and are not this
    file's business; the match is on the runner, not on the word "test".
    """
    return [
        (position, step)
        for position, step in enumerate(job.get("steps", []))
        if "pytest" in _script(step)
    ]


def _jobs_running_pytest() -> list[tuple[str, dict]]:
    return [(name, job) for name, job in _workflow()["jobs"].items() if _pytest_steps(job)]


def _runs_on_schedule(job: dict) -> bool:
    condition = job.get("if")
    if condition is None:
        return True
    if "!= 'schedule'" in condition:
        return False
    return "'schedule'" in condition


def test_some_job_in_ci_runs_pytest():
    assert _jobs_running_pytest(), (
        "no job in ci.yml runs pytest, so nothing below is checking anything"
    )


def test_every_job_that_runs_pytest_fetches_the_corpus_first():
    """The corpus is a resource, not a fixture, and a suite without it fails by name.

    Position rather than presence: the `test` job ran the fetch four steps *after* the suite,
    which is a step a reader sees and a resource the suite never had.
    """
    for name, job in _jobs_running_pytest():
        steps = job.get("steps", [])
        fetches_at = [i for i, step in enumerate(steps) if CORPUS_FETCH in _script(step)]
        assert fetches_at, (
            f"job {name!r} runs pytest and never runs {CORPUS_FETCH}. "
            "`sync.rehearse.fixture` refuses without .cache/corpus and names the script that "
            "fills it, so those tests fail on the runner for a reason that is not a defect"
        )
        first_pytest = _pytest_steps(job)[0][0]
        assert min(fetches_at) < first_pytest, (
            f"job {name!r} fetches the corpus at step {min(fetches_at)} and runs pytest at step "
            f"{first_pytest}, so the suite reads whatever was there before it -- on a fresh "
            "checkout, nothing"
        )


def test_no_pytest_step_discards_its_exit_code():
    """Exit 1 is a failing test, and a step that swallows it reports a suite nobody ran.

    Both spellings are refused because both were reached for here: `|| true` outright, and the
    subtler `status=$?` compared against a floor, which passes exactly the exit code that means
    a test failed.
    """
    for name, job in _jobs_running_pytest():
        for _, step in _pytest_steps(job):
            script = _script(step)
            label = f"step {step.get('name')!r} of job {name!r}"
            assert "||" not in script, (
                f"{label} runs pytest behind `||`, which turns a failing suite into a passing "
                "step. Coverage is still not gated -- no --cov-fail-under is passed anywhere -- "
                "but pytest's own verdict is not a number and may not be discarded"
            )
            assert "-gt" not in script, (
                f"{label} compares pytest's exit code against a floor. Exit 1 is a failing test "
                "and every floor above 0 lets it through; this is the shape that made a hundred "
                "nightlies green over a red suite"
            )
            # An adversarial review of the commit that wrote the three assertions above mutated
            # this workflow three ways and watched all four tests in this file stay green:
            # `continue-on-error` on the step, `continue-on-error` on the job, and a script ending
            # `exit 0`. Each reproduces the nightly defect exactly, and the first is the likely
            # one -- it is GitHub's own idiom for "record but do not gate", which is what the old
            # step's name claimed to be doing while it swallowed pytest's verdict too.
            assert step.get("continue-on-error") is not True, (
                f"{label} carries `continue-on-error`, so the job stays green over a failing "
                "suite. Coverage not gating is a claim about a number; this discards the verdict"
            )
            assert not script.rstrip().endswith("exit 0"), (
                f"{label} ends `exit 0`, which discards whatever pytest reported. `set +e` and an "
                "unconditional success are the same defect as `|| true` written across two lines"
            )
        assert job.get("continue-on-error") is not True, (
            f"job {name!r} runs pytest under `continue-on-error`, so no step in it can fail the "
            "workflow. A job that cannot go red is not a gate, whatever its steps assert"
        )


def test_the_nightly_gates_the_suite():
    """A schedule that can only report success is not a check.

    `test`, `web` and `serial` all exclude the nightly deliberately and this does not argue with
    that -- it asks only that whatever the nightly *does* run can fail.
    """
    nightly = [name for name, job in _jobs_running_pytest() if _runs_on_schedule(job)]

    assert nightly, (
        "every job that runs pytest excludes `schedule`, so the nightly run reports success "
        "without executing the suite. A green tick that asserts nothing is worse than a red "
        "build, because a red build is information"
    )


VERDICT_CHECK = "scripts/gate_verdict.py"


def _verdict_steps(job: dict) -> list[tuple[int, dict]]:
    return [
        (position, step)
        for position, step in enumerate(job.get("steps", []))
        if VERDICT_CHECK in _script(step)
    ]


def test_every_pytest_step_captures_its_output():
    """A verdict cannot be read from output nobody kept.

    `tee` rather than a plain redirect, because the run's own log is what a person reads while it
    is happening, and a redirect makes a job that takes twenty minutes look hung.
    """
    for name, job in _jobs_running_pytest():
        for _, step in _pytest_steps(job):
            script = _script(step)
            assert "tee" in script, (
                f"step {step.get('name')!r} of job {name!r} runs pytest without capturing its "
                "output, so no crashed-worker check can read it"
            )


def test_capturing_output_does_not_swallow_the_exit_code():
    """`cmd | tee file` reports tee's status, not pytest's, unless pipefail is set.

    This is the same defect as the nightly's discarded exit code, arriving by a different route:
    the step would report success over a failing suite because the last process in the pipe
    succeeded. Adding the capture without this line would have reintroduced exactly what
    `test_no_pytest_step_discards_its_exit_code` exists to prevent.
    """
    for name, job in _jobs_running_pytest():
        for _, step in _pytest_steps(job):
            script = _script(step)
            if "tee" not in script:
                continue
            assert "pipefail" in script, (
                f"step {step.get('name')!r} of job {name!r} pipes pytest into tee without "
                "`set -o pipefail`, so a failing suite reports as a passing step"
            )


def test_every_job_that_runs_pytest_checks_the_run_is_trustworthy():
    for name, job in _jobs_running_pytest():
        assert _verdict_steps(job), (
            f"job {name!r} runs pytest but never runs {VERDICT_CHECK}, so a crashed worker's "
            "phantom failures are indistinguishable from real ones"
        )


def test_the_trustworthiness_check_runs_after_the_suite_it_judges():
    for name, job in _jobs_running_pytest():
        last_pytest = max(position for position, _ in _pytest_steps(job))
        assert any(position > last_pytest for position, _ in _verdict_steps(job)), (
            f"job {name!r} runs {VERDICT_CHECK} before the suite it is supposed to judge"
        )


def test_the_trustworthiness_check_runs_even_when_the_suite_fails():
    """The case it exists for. A failing suite is exactly when a reader needs to know whether the
    tally can be believed, and a step with no condition is skipped once an earlier step fails."""
    for name, job in _jobs_running_pytest():
        for _, step in _verdict_steps(job):
            assert "always()" in str(step.get("if", "")), (
                f"step {step.get('name')!r} of job {name!r} runs {VERDICT_CHECK} without "
                "`if: always()`, so it is skipped in the one case it exists for"
            )


def test_no_step_carries_a_literal_backslash_n_in_its_script():
    """A two-character `\n` where a line continuation was meant.

    YAML parses it happily — it is an ordinary character in a block scalar — and every
    substring assertion in this file passed over it, because the words they look for were all
    still present. `bash` would have met `\n` as a command and the step would have failed on
    the runner for a reason with nothing to do with the suite.

    Caught by hand in `cat -A` output while wiring the verdict check, which is not a method that
    scales. Written down as a check so the next one is caught by the gate instead.
    """
    literal = chr(92) + "n"
    offenders = [
        f"{name}: {step.get('name')!r}"
        for name, job in _workflow()["jobs"].items()
        for step in job.get("steps", [])
        if literal in _script(step)
    ]

    assert not offenders, "steps whose script carries a literal backslash-n: " + ", ".join(offenders)
