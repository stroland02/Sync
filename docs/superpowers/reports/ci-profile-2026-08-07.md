# CI profile — 2026-08-07 13:55 UTC

Measured over the last 30 workflow runs, of which **25** contributed at least one successful job. **14 jobs ran zero steps** — a job that records a start and an end without running a step was never acquired by a runner, and its elapsed time is not a duration.

**Critical path, median: 198s.** Jobs run concurrently, so a run costs its slowest job rather than the sum of them; shortening anything else buys nothing.

## Jobs

| Job | n | median | min | max |
|---|---:|---:|---:|---:|
| `test` | 22 | 200s | 119s | 472s |
| `serial` | 21 | 169s | 155s | 484s |
| `coverage` | 6 | 130s | 123s | 137s |
| `web` | 22 | 32s | 20s | 46s |

## Steps above 3s

| Median | n | Job | Step |
|---:|---:|---|---|
| 146s | 21 | `serial` | Tests, serial scheduler |
| 102s | 6 | `coverage` | Coverage (recorded, not gated) |
| 84s | 16 | `test` | Coverage (recorded, not gated) |
| 64s | 22 | `test` | Tests |
| 20s | 22 | `test` | Score the frozen corpus |
| 11s | 22 | `test` | Initialize containers |
| 10s | 21 | `serial` | Initialize containers |
| 10s | 16 | `web` | Test |
| 10s | 6 | `coverage` | Initialize containers |
| 7s | 22 | `web` | Install Node |
| 6s | 22 | `web` | Install dependencies |
| 6s | 22 | `web` | Build |
| 5s | 6 | `coverage` | Warm the TypeScript npx cache |
| 4s | 22 | `test` | Stage the pinned Stripe specifications |
| 3s | 21 | `test` | Warm the TypeScript npx cache |
| 3s | 22 | `test` | Fetch the frozen corpus |
| 3s | 21 | `serial` | Install uv |

## Reading this

A step is worth attacking only if it sits on the critical path — inside whichever job the
table above shows slowest. A saving inside a faster job is real compute and zero
wall-clock, and the two are different currencies: compute is billed, wall-clock is what a
reviewer waits for. Say which one a change buys.


---

## The series, which is the point

| | 2026-08-06 | 2026-08-07 |
|---|---:|---:|
| Runs read | 25 | 30 |
| Contributed a successful job | 20 | 25 |
| **Zero-step jobs** | **14** | **14** |
| **Critical path, median** | **186s** | **198s** |
| `test` | 200s | 200s |
| `serial` | 160s | 169s |
| `web` | 24s | 32s |
| `coverage` | — | 130s (n=6) |

**The critical path did not get worse.** It reads +12s, and both numbers are medians over
overlapping windows of runs that did not all execute the same workflow. Treating 186 → 198 as a
regression would be reading noise as signal.

## B112 has recovered, and the flat 14 is why that is not obvious

`zero_step_jobs` is unchanged at 14, which read at first as the failure persisting. It is not.
**Every one of the last twelve runs ran zero zero-step jobs**, checked run by run:

```
2026-08-07T13:51  0 / 4      2026-08-07T12:58  0 / 3
2026-08-07T13:48  0 / 4      2026-08-07T12:35  0 / 3
2026-08-07T13:45  0 / 4      2026-08-07T06:24  0 / 3
2026-08-07T13:42  0 / 4      2026-08-07T04:06  0 / 3
2026-08-07T13:39  0 / 4      2026-08-07T03:18  0 / 3
2026-08-07T13:36  0 / 4      2026-08-07T02:27  0 / 3
```

All 14 are historical — the 2026-08-06 incident, still inside a 30-run window. **A cumulative count
over a sliding window cannot distinguish a failure that is continuing from one that has stopped**,
and that is a defect in how this metric is read rather than in the pipeline. The distinguishing
check is per-run and cheap; the count alone is not sufficient evidence to stop a tick on, and this
tick nearly stopped on it.

## No item was taken this tick, and the number that decided it

B111 — the headline this tick was written around — **was closed by `CI-W167` twenty minutes before
this profile ran**: coverage moved to a nightly, the serial job came off the pull-request path, and
the concurrency group gained `event_name`. That change is merged to `console-identity` and **has not
reached `main`**, so no pull-request or push run has executed it.

The six `coverage` samples above are `workflow_dispatch` runs on the branch, which is the on-demand
path the change added. So this profile is a **mixed population**: 16 `test` jobs still carrying the
84s coverage step under the old shape, and 6 under the new one.

That makes this report `CI-W167`'s **before**, and taking a second timing item now would make both
unattributable — the same reason the tick forbids touching the workflow and the suite in one commit.
The next profile, taken after `CI-W167` reaches `main`, is the one that says whether it worked.

**What it should show if it worked:** `test` loses its 84s coverage step and lands near 116s,
`serial` at 169s becomes the critical path, and the next item is `serial`'s own 146s
`Tests, serial scheduler`. **Recorded as a prediction, not a result** — if the next profile
disagrees, the prediction is what was wrong.


---

## CI-W167 measured, against the prediction above

The change reached `main` at `3f12149` and ran for the first time as a `push` event. Both runs are
on `main`, same workflow file except for this change, so the pair is comparable:

| Job | Before (`25a4a10`, run 31180520625) | After (`3f12149`, run 31185321603) |
|---|---:|---:|
| `test` | **211s** | **114s** |
| `serial` | 158s | 156s |
| `web` | 39s | 41s |
| `coverage` | — | *skipped*, 0 steps |
| **Critical path** | **211s** | **156s** |

**−55s, a 26% reduction**, and `serial` is now the critical path exactly as predicted. The
prediction said `test` would land "near 116s"; it landed at 114s. Recorded because the prediction
was written down before the measurement, which is the only thing that makes it worth anything.

**The next item is `serial`'s own 146s `Tests, serial scheduler`.** It is not taken here — see below.

## What CI-W167 broke, and it is this report's own alarm

`coverage` is now `skipped` on every push and pull request, which is correct. **A skipped job also
reports zero steps**, and `zero_step_jobs` counted any stepless job. So the B112 alarm would have
gained one per run forever while the pipeline stayed healthy.

That is worse than a wrong number. The tick above is instructed to **stop** if the count has risen,
so a count that always rises stops every tick for a reason that is not real — the same failure shape
as a gate at an invented threshold, which either fires constantly and gets disabled or never fires.

Fixed in `CI-W190`: `never_acquired()` separates the two, proven RED first, and the report now states
both numbers. Against the same 30-run window it reads **14 never acquired, 1 skipped** — the 1 being
the landing run above, which the old code would have counted as a fifteenth B112 job.

**This is why a timing item was not taken this tick.** Two changes to the same workflow between two
profiles cannot be attributed, and the metric that would attribute them was itself broken until now.
