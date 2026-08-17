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
