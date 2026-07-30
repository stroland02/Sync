"""CI has to run the scheduler `addopts` never selects, in the configuration where it can fail.

`-n0` was broken on `main` for an unknown length of time -- 186 errors from one cause -- and what
made it last is that nothing ran it. `addopts` pins `-n auto`, so no developer reached the case by
accident, and no step in `.github/workflows/ci.yml` passed `-n0` at all.
`docs/superpowers/reports/2026-07-30-ci-does-not-run-serial.md` carries the decision this file
pins and `2026-07-30-n0-is-broken.md` carries the defect.

Three properties of that job, and the second is the one worth a test on its own.

**It runs `-n0`.** Lose that and the job is a second copy of the parallel suite, green for exactly
the reasons the parallel suite is green.

**Nothing hands it a pinned `SYNC_DSN`.** This is the silent one, and it is silent in the
direction that manufactures confidence. `conftest.database_for` returns `None` for a serial run
that was handed a pin, so `pytest_configure` creates no database of its own, and the sweep this
job exists to watch has nothing of the run's to take. Measured: the two-file recipe that
reproduces the defect in 33 s unpinned is **green** under a pin, on the same broken tree. A serial
job carrying the `test` job's `SYNC_DSN` would have stayed green through all 186 errors.

**It runs the whole suite.** The alternative considered was a serial run over the database-touching
subset, and it was rejected because the defect class is one test breaking a later test in the same
process: any rule that picks the subset picks victims, and the breaker is what a new test brings.
Narrowing this job back to a list of paths is that rejected design arriving as a config tweak, so
it fails here instead and has to be argued for.

The workflow is parsed rather than grepped, because `SYNC_DSN` can reach a step from three scopes
and only a parse tells a workflow-level `env` from another job's. What a parse cannot see is a
variable written to `$GITHUB_ENV` by an earlier step; nothing in this workflow does that, and a
job that started to would need this file widened.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"

SERIAL_SCHEDULER = re.compile(r"-n\s*0(?![.\d])")
"""`-n0` and `-n 0`, which xdist treats identically, and neither of which a comment reformat moves.

Deliberately not `-p no:xdist`: against this repository's `addopts` that exits 4 on an
unrecognised `-n auto` rather than running the suite, measured in `2026-07-30-n0-is-broken.md`.
"""


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _serial_steps(workflow: dict) -> list[tuple[str, dict, dict]]:
    """Every (job name, job, step) whose script runs pytest under the serial scheduler."""
    return [
        (name, job, step)
        for name, job in workflow["jobs"].items()
        for step in job.get("steps", [])
        if "pytest" in (step.get("run") or "") and SERIAL_SCHEDULER.search(step["run"])
    ]


def test_ci_runs_the_suite_under_the_serial_scheduler():
    assert _serial_steps(_workflow()), (
        "no step in ci.yml runs pytest with -n0. `addopts` pins `-n auto`, so with this step "
        "gone nothing anywhere runs the serial configuration -- which is the state that let "
        "186 errors sit on main"
    )


def test_no_pinned_database_reaches_the_serial_run():
    workflow = _workflow()
    steps = _serial_steps(workflow)
    assert steps, "no serial step to check; test_ci_runs_the_suite_under_the_serial_scheduler says why"

    for job_name, job, step in steps:
        scopes = {
            "the workflow": workflow.get("env") or {},
            f"job {job_name!r}": job.get("env") or {},
            f"step {step.get('name')!r}": step.get("env") or {},
        }
        for scope, env in scopes.items():
            assert "SYNC_DSN" not in env, (
                f"{scope} sets SYNC_DSN, which reaches the serial run in {job_name!r}. A serial "
                "run handed a pin creates no database of its own -- database_for returns None -- "
                "so the sweep this job watches has nothing of the run's to take and the job is "
                "green through the defect it exists to catch"
            )


def test_the_serial_run_is_the_whole_suite():
    steps = _serial_steps(_workflow())
    assert steps, "no serial step to check; a vacuous pass here is what this line refuses"

    for job_name, _job, step in steps:
        assert "tests/" not in step["run"], (
            f"the serial step in {job_name!r} names test paths, which makes it a run over a "
            "hand-picked subset. One test breaking a later test in the same process is the "
            "defect class here, and a subset chosen by hand holds the victims rather than the "
            "breakers"
        )
