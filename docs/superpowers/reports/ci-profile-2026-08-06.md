# CI profile — 2026-08-06 18:12 UTC

Measured over the last 25 workflow runs, of which **20** contributed at least one successful job. **14 jobs ran zero steps** — a job that records a start and an end without running a step was never acquired by a runner, and its elapsed time is not a duration.

**Critical path, median: 186s.** Jobs run concurrently, so a run costs its slowest job rather than the sum of them; shortening anything else buys nothing.

## Jobs

| Job | n | median | min | max |
|---|---:|---:|---:|---:|
| `test` | 14 | 200s | 173s | 472s |
| `serial` | 16 | 160s | 135s | 484s |
| `web` | 13 | 24s | 20s | 29s |

## Steps above 3s

| Median | n | Job | Step |
|---:|---:|---|---|
| 137s | 16 | `serial` | Tests, serial scheduler |
| 80s | 14 | `test` | Coverage (recorded, not gated) |
| 60s | 14 | `test` | Tests |
| 21s | 14 | `test` | Score the frozen corpus |
| 12s | 14 | `test` | Initialize containers |
| 11s | 16 | `serial` | Initialize containers |
| 6s | 13 | `web` | Install Node |
| 6s | 13 | `web` | Install dependencies |
| 5s | 13 | `web` | Build |
| 4s | 14 | `test` | Stage the pinned Stripe specifications |
| 3s | 9 | `test` | Warm the TypeScript npx cache |
| 3s | 14 | `test` | Fetch the frozen corpus |
| 3s | 16 | `serial` | Install uv |

## Reading this

A step is worth attacking only if it sits on the critical path — inside whichever job the
table above shows slowest. A saving inside a faster job is real compute and zero
wall-clock, and the two are different currencies: compute is billed, wall-clock is what a
reviewer waits for. Say which one a change buys.
