# CI optimization — a standing workstream, driven by measurement

**Status:** open, continuous. Not a milestone; it does not finish.
**Profiler:** `scripts/profile_ci.py`. **Reports:** `docs/superpowers/reports/ci-profile-<date>.md`.
**Tick:** `docs/superpowers/loops/ci-optimization-tick.md`, daily.

## Why this is its own workstream

CI time is paid by every task, every worker and every session, every day. It is also the one cost in
this project that nobody owns — each session waits for it and moves on, so it drifts upward and
nothing notices. The other workstreams optimise what Sync does; this one optimises what checking
Sync costs.

**It is measured, never estimated.** GitHub records the start and end of every job and every step,
so where the minutes go is a fact we can read rather than a thing to reason about. A CI change
argued from a guess is worth nothing — this repository has already spent most of a day treating a
runner-allocation failure as a red build, and the distinction was sitting in the job record the
whole time.

## The first profile, 2026-08-06, over 25 runs

| Job | median | min | max |
|---|---:|---:|---:|
| `test` | 200s | 173s | 472s |
| `serial` | 160s | 135s | 484s |
| `web` | 24s | 20s | 29s |

Jobs run concurrently, so **the critical path is `test` at 200s** and a saving anywhere else is
compute rather than wall-clock. Those are different currencies and a change should say which one it
buys.

The steps that cost, all of them inside the two Python jobs:

| Median | Job | Step |
|---:|---|---|
| 137s | `serial` | Tests, serial scheduler |
| 80s | `test` | Coverage (recorded, not gated) |
| 60s | `test` | Tests |
| 21s | `test` | Score the frozen corpus |
| 12s | `test` | Initialize containers |

**The finding that dominates everything else: the suite runs three times per CI run.** Once under
`-n auto` as the gate (60s), once more under `--cov` for a number that is deliberately not gated
(80s), and once under `-n0` in a second job (137s). Roughly 280s of compute and 140s of the
200s critical path is the same tests, three times.

Each of the three has a real reason. The gate is the gate. Coverage is recorded because
`2026-07-27-sync-benchmark-gates.md` forbids inventing a threshold, and it is a separate invocation
because a dotted `--cov` legitimately changes behaviour here
(`2026-07-29-psycopg-error-identity.md`). The serial job exists because `addopts` runs `-n auto`
everywhere else and 186 errors only appear under `-n0`
(`2026-07-30-n0-is-broken.md`). **None of those reasons requires all three to run on every pull
request**, and that is the opening this workstream starts from — B111.

## How the workstream runs

1. **Profile daily.** `uv run python scripts/profile_ci.py --runs 30` writes a dated report. The
   series is the point: one profile is a snapshot, a week of them shows drift, and drift is what
   nobody currently notices.
2. **Take one item.** Highest median on the critical path first, unless a cheaper item removes a
   whole step.
3. **Land it against a measurement.** Every change ships with the before and after medians from the
   profile, not with an expectation. A change whose effect cannot be seen in the next profile did
   not happen.
4. **Record it**, including the ones that lose. A tried-and-rejected optimisation is worth as much
   as a landed one, because the next session will otherwise try it again.

## What this workstream may not do

- **Never weaken a gate to make it faster.** Deleting a check is not an optimisation; it is a
  smaller promise wearing the same name. If a check is not worth its time, that is an argument to
  make explicitly and record — not a speedup.
- **Never make a red build likelier to be ignored.** Anything that adds a "usually fine" failure
  mode costs more than it saves, because the expensive failure in this project has always been a
  real defect hiding inside an expected one.
- **Do not chase compute that is not on the critical path** without saying so. The `web` job at 24s
  is not where the time is.
- **Do not optimise against a synthetic run.** The numbers come from the repository's own history.

## Landed

- **B111** (CI-W167, 2026-08-07) — coverage to a nightly job of its own, the serial job off
  `pull_request` and onto every push to `main`. Pull-request critical path 200s → 123s, push
  critical path 200s → 170s, measured over six `workflow_dispatch` runs of the new shape
  (`reports/ci-profile-2026-08-07.md`); the closure in `BACKLOG.md` carries the argument and the
  risk accepted. Same pass: `github.event_name` added to the concurrency group so the nightly and
  a push to `main` stop sharing `refs/heads/main`, and a finding that dependency caching was
  already effective — `uv sync` and the oasdiff install are under 3s in every job, so there was no
  cache win to prefer.

  **A caveat the series has to carry:** coverage left the `test` job on 2026-08-07, so `test`
  medians before and after measure different step sets. Compare step medians across that date, not
  the job median.

## Open items

- **B112** — jobs are not being acquired by hosted runners, so CI's verdict currently means
  nothing. Not observed today: the six CI-W167 measurement runs all acquired runners and ran
  steps, but the entry stays open because the cause was never recorded.
