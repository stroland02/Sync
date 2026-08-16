# Brief - CI-W167, B111: the suite runs three times on every pull request

You are working in your own Orca workspace. **Start by rebasing:**
`git fetch origin && git checkout -B ci-critical-path origin/console-identity`. The base is
`console-identity`, the integration branch for every workstream right now.

## Stay out of `web/` and out of `src/`

**A second session is rebuilding the entire console presentation layer on `console-identity` in
parallel with you, and a third work item is changing `src/sync/graph/store.py`.** Your territory is
`.github/workflows/`, `scripts/profile_ci.py`, `docs/superpowers/plans/2026-08-06-ci-optimization.md`,
`docs/superpowers/reports/ci-profile-*.md`, and the backlog entry. **Change no test and no source
file.** If closing this needs a source change, that is a finding to report rather than a change to
make.

## What is measured, and it is measured rather than guessed

`B111` in `docs/superpowers/BACKLOG.md` and `reports/ci-profile-2026-08-06.md` carry the numbers,
taken over 25 runs by `scripts/profile_ci.py` (CI-W154). Read both before touching anything.

Jobs run concurrently, so the critical path is the `test` job at a median of **200s**:

| Median | Job | Step |
|---:|---|---|
| 137s | `serial` | Tests, serial scheduler (`-n0`) |
| 80s | `test` | Coverage (recorded, not gated) |
| 60s | `test` | Tests (`-n auto`) |

**Roughly 280s of compute and 140s of the 200s critical path is the same suite, three times.**

**Each of the three has a real reason and none of them is wrong**, which is why this is a scheduling
question rather than a cleanup:

- The `-n auto` run is the gate. It is not moving.
- Coverage is a separate invocation because a dotted `--cov` legitimately changes behaviour in this
  repository - `specs/2026-07-29-psycopg-error-identity.md` - and it is **recorded rather than
  gated**, because `specs/2026-07-27-sync-benchmark-gates.md` forbids inventing a threshold nobody
  has justified.
- The `serial` job exists because `addopts` runs `-n auto` everywhere else and **186 errors appear
  only under `-n0`** - `reports/2026-07-30-n0-is-broken.md`.

## What to decide, and the argument is the deliverable

**What none of those reasons requires is that all three run on every pull request.** That is the
opening this item works in.

The obvious moves and the real cost of each:

- **Coverage to a nightly schedule.** It is recorded, not gated, so no reviewer waits on it. The cost
  is that a coverage regression is noticed the next morning rather than in the pull request. Say
  whether that matters here and why.
- **The serial job conditioned or scheduled.** It catches a class of defect that arrives with a
  `conftest.py`, a fixture, or a plugin change rather than with a screen. A path filter is the cheap
  version and it is also the fragile one: a path filter that is wrong is a gate that silently stops
  running. If you propose one, say exactly which paths and why that set is complete, and prefer
  running it always over running it on a guess.

**Both are decisions with a real risk attached. B111 says that risk is the thing to argue, not to
assume away.** A gate deleted rather than moved does not close this entry, and a plausible-sounding
path filter is a gate deleted with extra steps.

Two more things worth checking while you are in the workflow, because they are cheap and may matter
more than the scheduling:

- **`concurrency: cancel-in-progress` is keyed on `github.ref`.** Confirm what that does to a
  pull-request run when the branch is also pushed - if the two events collide, one is cancelled and
  reports as a failure, which feeds the same misreading B112 documents.
- **Dependency and toolchain caching.** If a meaningful share of those medians is `uv sync` or an
  `npx` fetch rather than the suite itself, that is a larger and far less risky win than moving a
  gate. The profile has the step timings; look before proposing.

## Close it honestly

**Closes when:** the critical path falls, **with the before-and-after medians from two profiles
beside it**, and every check that stopped running per-pull-request is named along with where it runs
instead.

That means running `scripts/profile_ci.py` for the "after" number is part of this item, not a
follow-up - and it means you need enough runs for a median to mean something. **If CI is not
producing runs when you get there, say so and report the change with the before-profile and a stated
expected effect rather than a measured one.** `B112` is open: hosted runners have been intermittently
failing to acquire jobs, and a job that never started reports as `failure` with zero steps. Check
with:

```sh
gh api repos/stroland02/Sync/actions/runs/<id>/jobs --jq '.jobs[] | "\(.name) \(.conclusion) steps=\(.steps|length)"'
```

**Do not report a measured improvement you did not measure.** An unmeasured change with an honest
label is worth more than a number nobody can reproduce.

## Your gate

```sh
cd <your workspace> && uv run pytest tests/ -q -n0
```

Clean - you are changing workflow YAML, so this is a regression check rather than a test of your
work. Baseline at `e57a3e7` is 3407 passed, 4 skipped. Postgres is on **port 5433**;
`docker compose up -d` if it is not running.

**Validate the workflow file itself rather than trusting it.** A YAML change that CI silently ignores
is exactly the failure mode this item is supposed to remove, and B112 means a green run list is not
evidence the file parsed. `gh workflow view` and `actionlint` if available; if neither is, say how
you checked.

**5173 and 8789 belong to the owner - leave both alone.**

Conventional Commits, subject carrying `CI-W167`. Push your branch. **No pull request, nothing on
`main`.** Send `worker_done` when you finish.
