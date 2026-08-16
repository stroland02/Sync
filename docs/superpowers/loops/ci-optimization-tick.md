# CI optimization tick

A daily prompt. It assumes nothing except this repository and a working `gh`.

`docs/superpowers/plans/2026-08-06-ci-optimization.md` carries the argument and the rules. This is
the loop that executes it.

---

## The tick

**1. Profile, before deciding anything.**

```sh
cd /c/Users/strol/orca/Sync/Sync/.claude/worktrees/sync-m4-dashboard
PYTHONIOENCODING=utf-8 uv run python scripts/profile_ci.py --runs 30
```

It writes `docs/superpowers/reports/ci-profile-<date>.md`. Read the previous day's file beside it —
**the series is the point.** One profile is a snapshot; two are a direction.

**2. Check the profile is measuring runs rather than absences.**

The report prints `zero_step_jobs`. A job that records a start and an end while running zero steps
was never acquired by a runner, and its elapsed time is not a duration. If that count is climbing,
CI is not slow — it is not running, and **its verdict means nothing until it is**. That is B112, and
it outranks every optimisation, because an optimisation measured against a broken pipeline is
measured against noise.

Confirm before believing a red build:

```sh
gh api repos/stroland02/Sync/actions/runs/<id>/jobs --jq '.jobs[] | "\(.name) \(.conclusion) steps=\(.steps|length)"'
```

Zero steps plus the annotation *"was not acquired by Runner of type hosted"* is GitHub, not us.

**3. Take exactly one item.**

Highest median on the **critical path** — the slowest job, since jobs run concurrently. A saving
inside a faster job is compute rather than wall-clock, and the two are different currencies. Say
which one the change buys.

Prefer, in order:

1. A step that can stop running on every pull request without weakening a gate — moved to a
   schedule, or folded into an invocation that already happens.
2. A step whose cost is setup rather than work: an install that could be cached, a container that
   could be shared.
3. A genuinely faster way to do the same work.

**4. Land it against a measurement, or do not land it.**

Before and after medians from the profile, in the commit body. An expectation is not a result. If
the next profile cannot see the change, it did not happen and the entry says so.

**5. Record the losses too.**

A tried-and-rejected optimisation goes in the backlog with the number that killed it. Without that,
the next session tries it again — this repository has re-derived the same rejected idea more than
once.

---

## What a tick must not do

- **Never weaken a gate to make it faster.** A deleted check is a smaller promise wearing the same
  name. If a check is not worth its time, argue that explicitly and separately.
- **Never make a red build easier to ignore.** The expensive failure here has always been a real
  defect hiding inside an expected one.
- **Never optimise against a synthetic run.** The numbers come from this repository's own history.
- **Do not touch the workflow and the suite in one commit.** When the next profile moves, you want
  to know which of the two moved it.
