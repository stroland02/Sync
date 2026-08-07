# CI profile — 2026-08-07 13:55 UTC

Measured over the last 6 workflow runs, of which **6** contributed at least one successful job. **0 jobs ran zero steps** — a job that records a start and an end without running a step was never acquired by a runner, and its elapsed time is not a duration.

**Critical path, median: 170s.** Jobs run concurrently, so a run costs its slowest job rather than the sum of them; shortening anything else buys nothing.

## Jobs

| Job | n | median | min | max |
|---|---:|---:|---:|---:|
| `serial` | 6 | 170s | 165s | 177s |
| `coverage` | 6 | 130s | 123s | 137s |
| `test` | 6 | 123s | 119s | 126s |
| `web` | 6 | 42s | 36s | 46s |

## Steps above 3s

| Median | n | Job | Step |
|---:|---:|---|---|
| 148s | 6 | `serial` | Tests, serial scheduler |
| 102s | 6 | `coverage` | Coverage (recorded, not gated) |
| 65s | 6 | `test` | Tests |
| 20s | 6 | `test` | Score the frozen corpus |
| 14s | 6 | `web` | Test |
| 12s | 6 | `serial` | Initialize containers |
| 11s | 6 | `test` | Initialize containers |
| 10s | 6 | `coverage` | Initialize containers |
| 8s | 6 | `web` | Install Node |
| 7s | 6 | `web` | Install dependencies |
| 7s | 6 | `web` | Build |
| 5s | 6 | `coverage` | Warm the TypeScript npx cache |
| 4s | 6 | `test` | Stage the pinned Stripe specifications |
| 4s | 6 | `test` | Fetch the frozen corpus |
| 3s | 6 | `test` | Warm the TypeScript npx cache |

## Reading this

A step is worth attacking only if it sits on the critical path — inside whichever job the
table above shows slowest. A saving inside a faster job is real compute and zero
wall-clock, and the two are different currencies: compute is billed, wall-clock is what a
reviewer waits for. Say which one a change buys.
