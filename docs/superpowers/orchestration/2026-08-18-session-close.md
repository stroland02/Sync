# Session close, 2026-08-18: what landed, what did not, and where it stands

**Written at close-out so the next session starts from a record rather than from inference.**
Every claim here was measured at the time of writing, not asserted.

## The tree

**Every worktree is clean and nothing is ahead of `main`.** Lanes A, C, H, I and the coordinator
all report `dirty=0`, `untracked=0`, `ahead_of_main=0`. The only untracked paths anywhere are
`.agents/` and `AGENTS.md` in the primary checkout, which predate this session.

**Nothing is stranded on a branch.** All four lane branches — `lane-c-pipeline`, `lane-f`,
`lane-e-graph`, `console-motion` — are ancestors of `main`.

## The gates

`uv run python scripts/beta_gates.py --run-suite`, measured at close:

| Gate | Verdict | Waiting on |
|---|---|---|
| 1 — the loop closes | **NOT MET** | 3 real attempts, **0 with a pull request that went green**. `B7` has run and abandoned. |
| 2 — the evidence exists | **CANNOT TELL** | 0 of 5 quality axes have samples. Follows from Gate 1. |
| 3 — the console tells the truth | **CANNOT TELL** | The last signature predates the console. **Deliberately not walked** — see below. |
| 4 — the containment story | **NOT MET** | **1 suite failure**, down from 13 during this session. |

**The suite went 13 → 4 → 2 → 1 failure across the session.** The survivor is
`tests/test_api_routes.py::test_the_consoles_fetched_paths_match_the_apps_declared_routes` — the
console/API drift guard, which is the check that catches payload-and-type disagreements `tsc`
cannot see.

## Gate 3 was not walked, and that is the answer rather than a gap

`CI-W450` records it. Four console changes landed in eighty-two minutes; the longest gap was
twenty-three. The bar was twenty-five minutes of quiet, **chosen before the measurement rather than
after it**. The console never cleared it, so there was no window in which a walk could start and
finish against one tree.

**The report is marked `Historical` and carries no `Signed:` line, so it cannot be misread as a
signature.** The gate reads it correctly: *"carries no signature by design, so not read and not
missing one."*

## What this session built

- **The zero-prerequisite install**, on owner decisions 97–99: `bin/embedded-postgres.mjs`,
  `bin/python-bootstrap.mjs`, the `uv` bootstrap. Docker becomes optional rather than required.
- **`sync index --repo`** (`M14-W443`) — the command that did not exist and without which a
  stranger's container came up to an empty console.
- **`GET /api/events`** and the console consuming it — the SSE bus behind the motion system.
- **The Findings destination** (`M14-W432`), the Runs page, dashboards 1, 5, 6, 7 and 9.
- **A competitor's npm scope removed from the front door** (`CI-W441`): the README told visitors to
  run `npx @superloglabs/sync`. **`package.json` still carries that name** — the replacement is the
  owner's decision and nothing publishes until it is made. `"private": true` prevents an accident.
- **`npx` measured, not assumed** (`CI-W440`): the registry 404s and `npm publish` refuses.
- **67 owner UI decisions recorded** (33–99) in `2026-08-18-owner-ui-decisions.md`, each with what
  it was decided against.

## The three defects worth carrying forward

- **`dev_up` walked you into the sentence it exists to prevent** (`CI-W447`). It probed readiness at
  a hardcoded port while starting the API on a configured one, so its own documented workaround made
  the probe answer from **another lane's server**.
- **A fabricating fallback answered questions it was never qualified to answer** (`M14-W433`).
  `_FallbackIndexingAdapter` derived operation ids from symbol words, returning `CreateCharges` where
  the spec says `PostCharges`. Deleted rather than corrected: **answering nothing beats answering
  wrongly**, because a finding built on it names an operation no vendor has.
- **The work register became 32 nested copies of itself** (`M0-W346`), 10.7MB, because a whole-file
  conflict was resolved by keeping both sides. Rebuilt losslessly; `scripts/check_worklog.py` now
  fails the gate on a second heading or a repeated id.

## What the next session should pick up first

1. **`B7` produces no pull request.** All 24 findings are one structural class — a response field
   seven to nine levels deep inside `anyOf` branches, matched at *operation only* because the call
   site's `response_fields_read` never names it precisely enough. **That is indexing precision, not
   agent behaviour**, and it is what Gates 1 and 2 wait on.
2. **The package name.** Owner decision, blocking publication.
3. **The last suite failure**, which is the drift guard.
4. **The UI features not yet built**: dismissal with reason codes (decision 45), global search in
   the rail (70), and editable Settings (74).
