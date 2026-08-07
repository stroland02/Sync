"""A job that ran no steps is two different facts, and the profiler counted them as one.

`zero_step_jobs` exists to watch B112: a job never acquired by a hosted runner records a start and
an end without running a step, and its elapsed time is not a duration. A rising count is the alarm.

`CI-W167` broke that by being correct. It moved coverage behind `if: github.event_name ==
'schedule'`, so on every push and every pull request the `coverage` job is **skipped** — and a
skipped job also reports zero steps. Measured on run `31185321603`, the first real execution of the
new workflow: `coverage skipped steps=0`. Without the distinction below, every future run adds one
to an alarm that is supposed to mean "a runner failed to pick this up", and the number climbs
forever while the pipeline is healthy.

That matters more than a wrong number. The 2026-08-07 tick was instructed to stop if the count had
risen, and a metric that always rises is a metric that stops every tick for a reason that is not
real — the same class of defect as a gate at an invented threshold, which either fires constantly
and gets disabled or never fires at all.
"""

from __future__ import annotations

from scripts.profile_ci import never_acquired


def test_a_skipped_job_is_not_a_job_a_runner_failed_to_acquire():
    """`conclusion: skipped` with no steps is a deliberate outcome, not an allocation failure."""
    assert never_acquired({"name": "coverage", "conclusion": "skipped", "steps": []}) is False


def test_a_zero_step_failure_is_a_job_a_runner_never_acquired():
    """The B112 signature: a start, an end, no steps, and a conclusion that reads as a red build."""
    assert never_acquired({"name": "test", "conclusion": "failure", "steps": []}) is True


def test_a_zero_step_cancellation_is_also_never_acquired():
    """The same failure reported the other way; run 31124124263 recorded all three jobs like this."""
    assert never_acquired({"name": "serial", "conclusion": "cancelled", "steps": []}) is True


def test_a_job_that_ran_steps_is_never_counted_however_it_concluded():
    """A job that ran and failed is a real failure, and belongs to whoever reads the build."""
    assert never_acquired({"name": "test", "conclusion": "failure", "steps": [{"name": "Tests"}]}) is False
    assert never_acquired({"name": "test", "conclusion": "success", "steps": [{"name": "Tests"}]}) is False


def test_a_missing_steps_key_is_treated_as_no_steps():
    """GitHub omits `steps` rather than sending an empty list when a job never started."""
    assert never_acquired({"name": "web", "conclusion": "cancelled"}) is True
