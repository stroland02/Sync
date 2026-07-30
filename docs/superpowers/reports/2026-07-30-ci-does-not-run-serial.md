# CI could not have caught the serial defect, and not only because it never ran `-n0`

**Date:** 2026-07-30
**Scope:** M3-W108 — decide what CI should do about the scheduler `addopts` never selects, after
`2026-07-30-n0-is-broken.md` fixed a defect that had been sitting in it.
**Outcome:** a `serial` job running the whole suite under `-n0` with **no `SYNC_DSN`**, and the
coverage step's `|| true` replaced by something that keeps the non-gating and stops swallowing an
incomplete run. The pin is the load-bearing half: a `-n0` step added to the existing job would
have been green through all 186 errors, which is measured below rather than argued.

## 1. What was missing, and what "missing" turned out to mean

W105's closing note names two gaps, and the one that matters here is that nothing in CI passes
`-n0`. That is true and it is not the whole of it. `.github/workflows/ci.yml` pins `SYNC_DSN` at
the job level, and a pin decides which
database the run owns before any scheduler is chosen. Computed from the real
`conftest.database_for` and the real `conftest.pids_in_name`, with `LEAKED_DATABASE_PATTERN` as
`sync\_test\_%`:

| configuration | scheduler | database the run owns | pids the sweep reads |
|---|---|---|---|
| `SYNC_DSN` pinned, as `test` sets it | `-n0` | **none** — `database_for` returns `None` | — |
| `SYNC_DSN` pinned, as `test` sets it | `-n auto` | `sync_gw0` | none; outside the swept pattern |
| unpinned | `-n0` | `sync_test_4242` | `[4242]` |
| unpinned | `-n auto` | `sync_test_4242_gw0_p4242` | `[4242, 4242]` |

Under the pin, no database this job creates is a sweep candidate at all, under either scheduler.
So the gap was not that CI ran the wrong scheduler. It is that **CI's database configuration puts
the defect out of reach**, and a `-n0` step inheriting it would have been a step that cannot fail.
That is the trap this task was most likely to fall into, and it is the reason the serial run is a
job of its own rather than a step appended to `test`.

## 2. What a serial job costs, re-measured

Taken on the merged tree at `c0a0e9d`, 12 cores, against the shared Postgres on 5433. Three runs
back to back in one quiet window, so the three are comparable to each other rather than each being
somebody's best case:

| scheduler | result | pytest's own wall clock | against `-n auto` |
|---|---|---|---|
| `-n auto` — 12 workers, what `addopts` pins | 2608 passed, 2 skipped, exit 0 | **117.49 s** | 1.00× |
| `-n4` | 2608 passed, 2 skipped, exit 0 | **167.40 s** | 1.42× |
| `-n0` | 2608 passed, 2 skipped, 1 deselected, exit 0 | **371.23 s** | **3.16×** |

W105 measured 3.46× and this is 3.16×, so that figure is confirmed rather than replaced. **But
3.16× is the wrong number to argue the CI decision from, and the `-n4` row is why.** The ratio is a
property of the core count, not of the suite: the serial figure barely moves as workers are taken
away and the parallel figure is the one that does. Against four workers, `-n0` is **2.22×**. A
GitHub-hosted `ubuntu-latest` runner has nowhere near twelve cores, and four workers on twelve cores
still leaves the `git`, `tsc` and `oasdiff` subprocesses more room than four cores would — so 2.22×
over-estimates the parallel side, and the real cost in CI is nearer double the parallel suite than
triple.

Two earlier figures are kept here because they say what this machine is worth rather than what the
suite is: an `-n0` run at 676 s with a mutation harness beside it, and an `-n auto` run at 190 s
with roughly fifty foreign python processes beside it. The machine is shared with other agents'
suites, contention inflates and never deflates, and that is why the table above is one window
instead of a best-of across five runs.

## 3. The three options, and the two not chosen

**A serial job over a subset was the tempting one, and the measurement killed it.** A subset needs
a membership rule read out of the source rather than a hand-maintained list —
`tests/test_decode_handlers.py` records what a positional hand-maintained list costs here, and its
answer was to read the inventory out of `src/`. The natural computable rule is *every test module
that transitively imports psycopg*, since losing a database is what the known defect does. Over
this tree that rule selects 67 of 146 test modules, 46%, and here is what it leaves out:

- **`tests/test_serial_run_isolation.py`** — the one file in the suite whose entire purpose is the
  serial configuration. It imports `os`, `subprocess`, `sys` and `pathlib`, so a psycopg-reaching
  rule excludes it from the serial job.
- **`tests/test_psycopg_error_identity.py`** — a test about psycopg class identity being split by a
  dotted `--cov`, which reaches psycopg only inside a string it hands to a subprocess.

That is not a rule with a rough edge; it is a rule pointed at the wrong half of the problem. The
defect class is **one test breaking a later test in the same process**, and a static rule can
guess which tests are *victims* while the *breaker* is whatever a new test brings. `-n0` puts the
whole suite in one process, so the interference mechanisms are not confined to code that touches
Postgres: a monkeypatched module global, a mutated `os.environ`, a `sys.modules` eviction and a
changed working directory all reach across files under `-n0` and across nothing under `-n auto`. A
subset chosen by database contact addresses exactly the one mechanism already known about, at 46%
of the modules, and does not shrink the wall clock by anything like 54% because the heavy files are
in both halves.

**Nothing in CI, written down, is defensible and was rejected on one fact.** The reason the defect
lasted is that nobody could see the gap. A comment saying "we do not run this, here is why" makes
the gap visible, which is most of the value — but `tests/test_serial_run_isolation.py` covers three
tests' worth of the serial configuration from inside the parallel suite, and three tests is not a
floor under the whole-suite interference class above. The honest form of option 3 is "the driver is
enough", and §5's demonstration is what refuses it: the driver *did* catch this defect, and so did
the canary, and the full serial run additionally reproduced **186 errors** that neither of them can
see. A gate that reports 2 failures where the configuration produces 188 is a gate that has stopped
measuring the configuration.

**So: the whole suite, serially, in a job of its own.** It cannot rot, because there is no
membership question to rot. Its cost is a full suite run at serial speed, and a separate job pays
that in runner minutes rather than adding it to the `test` job's wall clock.

The workflow's own wall clock is likely to move less than the price tag suggests, and the arithmetic
is worth writing down because it is the one place option 1 gets cheap. `test` already runs the suite
**twice** — once as `Tests` and once as `Coverage`, both parallel, the second with instrumentation —
and then fetches, scores and gates the corpus. Calling the parallel suite P, that job is upwards of
2.2 P. From §2, `-n0` against four workers is 2.22 P, so the `serial` job is about that plus its own
checkout and `uv sync`. The two jobs are therefore comparable in length, and the workflow ends when
the longer finishes rather than after their sum. What this buys with is runner minutes and a second
Postgres container, not the minutes-per-push the option is usually charged for. It is stated as a
prediction, not a measurement — no run has happened yet, and §7 says so.

## 4. The `|| true`, and a correction to W105

Its comment argues for the non-gating and is right: *"a coverage run that errors must not turn a
green suite red either."* The non-gating stays. What `|| true` cannot distinguish is **a number
that moved from a run that never produced one**, and the exit code it discards is the only place
that distinction lives.

The reason the distinction belongs in this step rather than a separate one is narrow and
checkable: **no `--cov-fail-under` is passed here, so coverage cannot produce an exit code at
all.** Measured — `pytest -q -n0 --cov=sync --cov-report=term-missing:skip-covered
tests/test_oasdiff_pin.py` (plus `--color=no -p no:cacheprovider`), a slice that leaves almost all
of `sync` uncovered, exits **0** with 17 tests passed. Every
non-zero value from that step is therefore pytest's, and pytest's are already sorted: 0 clean, 1 a
failing test, and 2 through 5 all mean no number was measured. Also measured, with `--cov` in play:
`-k` matching nothing exits **5**, and an unrecognised flag exits **4**.

So the step keeps 0 and 1 — `Tests` above is the gate on the suite, and a dotted `--cov`
legitimately changes behaviour in this repository (`2026-07-29-psycopg-error-identity.md`) — and
fails on the rest. The two forms, with pytest stubbed to each exit code and the script run under
`bash -e` as Actions runs it:

| pytest exits | `\|\| true` | the step now |
|---|---|---|
| 0 | 0 | 0 |
| 1 | 0 | 0 |
| 2 interrupted | **0** | 2 |
| 3 internal error | **0** | 3 |
| 4 usage error | **0** | 4 |
| 5 nothing collected | **0** | 5 |

**One correction.** W105's §9 says the `|| true` "is one of the two things that hid this", and that
is not right. `addopts` applies to the coverage step too, so it has always run `-n auto` and never
the serial configuration those 186 errors need; §1's table adds that the pin puts the defect out of
reach under `-n auto` as well. Nothing in CI hid that defect, because nothing in CI could reach it.
The `|| true` was hiding a different class — a coverage run that collapses — and that is what
changed here.

## 5. Validating the step by hand, against both trees

GitHub Actions cannot be run locally, so what is validated is the command the step runs, in the
environment the job gives it: **`uv run pytest -q -n0` with `SYNC_DSN` unset**. The broken tree is
W105's defect exactly — both `exclude=OWN_DATABASE` arguments removed from
`tests/test_leaked_database_sweep.py`, nothing else touched, restored afterwards from the original
bytes because these files are CRLF.

| tree | command | environment | result |
|---|---|---|---|
| fixed | `uv run pytest -q -n0` | `SYNC_DSN` unset | 2556 passed, 2 skipped, 1 deselected, **exit 0**, 422.18 s |
| **broken** | `uv run pytest -q -n0` | `SYNC_DSN` unset | **2 failed, 2368 passed, 2 skipped, 1 deselected, 186 errors, exit 1**, 371.68 s |

The broken run's 186 errors are one string, and the database named is the run's own:

    E  psycopg.OperationalError: connection failed: ... FATAL:  database "sync_test_10764" does not exist

**186, not "the same cause would produce 186".** W105 declined to re-take W102's count and said so
in its §7; this run reproduces it independently, fifteen commits on from the `8187a9b` W102's
recipe was pinned against, with no `--cov` anywhere. The two failures are the canary and W105's
driver:

    FAILED tests/test_leaked_database_sweep.py::test_the_run_s_own_database_survives_every_sweep_in_this_file
    FAILED tests/test_serial_run_isolation.py::test_a_serial_run_does_not_sweep_away_its_own_database

### The counterfactual, which is the point of the job being separate

Same broken tree, same command, W105's two-file recipe, one variable changed — the pin:

| environment | result |
|---|---|
| `SYNC_DSN` unset | 1 failed, 32 passed, **4 errors**, **exit 1**, 109.49 s |
| `SYNC_DSN` pinned, as `test` pins it | **37 passed, exit 0**, 33.45 s |

The pin is a database created for this measurement and dropped after it — `sync_w108_pin`, not the
shared `sync` the workflow names, because six other worktrees share that server. The mechanism is
the pin's existence rather than its name: `database_for` returns `None` for any pinned serial run,
and the fixture databases the sweep does reach are named `sync_test_<pid>_gw…` either way.

A `-n0` step added to the existing `test` job is the second row. It runs the serial scheduler, it
runs the whole suite, it is gated, and it is green on a tree carrying the defect. That is the step
this task existed to avoid writing, and the pin is the whole of the difference.

## 6. The test, and its mutants

`tests/test_ci_runs_the_serial_scheduler.py` parses `ci.yml` and pins three properties. Two of the
three are silent when lost, which is why they are a test rather than a comment: a serial job
carrying a pin is green, and a serial job that lost `-n0` is a second copy of the parallel suite.
The third refuses the subset design arriving later as a config tweak.

Harness at `.cache/w108/mutate.py`, gitignored. It parses every mutant with `yaml.safe_load` before
writing, reports an anchor that matched nothing as `ANCHOR-MISSED` rather than as a survivor,
restores from the **original bytes**, and reads pytest's own exit code together with the count in
its output. `KILLED` needs exit 1 *and* a `failed` count; `SURVIVED` needs exit 0 *and* `3 passed`
and no `failed`; anything else is `UNREADABLE` with the exit code printed. Baseline `3 passed`
before and after, so nothing drifted, and `git diff` on `ci.yml` is empty afterwards.

| mutation | verdict | note |
|---|---|---|
| `M-no-serial-job` — the whole `serial` job deleted | **KILLED**, `3 failed` | the state this task started in |
| `M-parallel-scheduler` — `-n0` dropped from the step | **KILLED**, `3 failed` | a second copy of the parallel suite |
| `M-pinned-dsn` — `SYNC_DSN` added to the serial job | **KILLED**, `1 failed, 2 passed` | §5's second row, refused |
| `M-subset-paths` — the step narrowed to one test file | **KILLED**, `1 failed, 2 passed` | §3's rejected design, refused |
| `M-flag-with-a-space` — `-n0` written `-n 0` | **SURVIVED**, `3 passed` | behaviour-neutral, and must not fire |
| `M-reworded-comment` — the comment above the job rewritten | **SURVIVED**, `3 passed` | ditto; a check that fires on a reformat gets silenced |

The last two are the honesty check. `ANCHOR-MISSED` earned its place on the first run:
`M-pinned-dsn`'s anchor spelled a line break `\n` against a CRLF file and matched nothing, which a
two-outcome harness would have printed as a surviving mutant and a hole in the test.

## 7. What this evidence does not cover

- **No GitHub Actions run happened.** What is validated is the command each step runs, executed by
  hand, in the environment the job declares. Nothing here establishes that the `serial` job's
  service container comes up, that `5433:5432` is accepted as written, or that `ubuntu-latest`
  installs a Linux oasdiff from the pinned tag. The first push is what establishes those.
- **The `-n4` row is a stand-in and not a runner measurement.** Twelve cores running four workers
  is not four cores running four workers. It bounds the ratio in the honest direction and no more.
- **The 186 is reproduced under one configuration only** — no `--cov`, this tree, this machine.
  W102's number was taken under a dotted `--cov=sync.benchmark.mutate`, which changes program
  behaviour here, and the two are not compared.
- **The subset rule was measured, not the subset's wall clock.** 46% of modules is a count of
  modules, not of tests and not of seconds. The argument against the subset does not rest on the
  saving being small; it rests on the rule selecting victims rather than breakers.
- **Nothing here says `-n0` has only this one defect.** The `serial` job is what would say so, run
  after run, and it speaks only for the tests that exist on the day it runs.
- **The workflow test cannot see a variable written to `$GITHUB_ENV`.** It reads the three
  declarative scopes a `SYNC_DSN` could arrive from. No step in this workflow writes to
  `$GITHUB_ENV`, and one that started to would need that file widened.
- **`test_the_serial_run_is_the_whole_suite` asserts on a substring, `tests/`.** A future serial
  step that narrowed the run some other way — a `--deselect`, a `-k`, a marker — would pass it. It
  refuses the shape that was actually considered and rejected, not every possible narrowing.

## 8. Gates

Taken on the merged tree at `c0a0e9d`, after `origin/main` moved twenty commits ahead mid-task. It
was merged in rather than left for the coordinator for one reason: this branch makes `-n0` a gate,
so whether the tree that lands is green under `-n0` is this task's question and not the next one's.
Every exit code is the command's own, read from a redirect rather than a pipeline — `pytest -q;
echo $?` reports `echo`'s status and that has produced a false verdict here.

| gate | result |
|---|---|
| `uv run pytest -q` (`-n auto` via `addopts`) | **2608 passed, 2 skipped, exit 0**, 117.49 s |
| `uv run pytest -q -n0` | **2608 passed, 2 skipped, 1 deselected, exit 0**, 371.23 s |
| `uv run pytest -q -n4` | **2608 passed, 2 skipped, exit 0**, 167.40 s |
| `uv run python scripts/lint_encoding.py src scripts tests` | exit 0 |
| `PYTHONIOENCODING=utf-8 uv run lint-imports` | `1 kept, 0 broken`, exit 0 |
| `uv run python scripts/lint_dead_links.py src --baseline …` | exit 0 |

The second row is what the `serial` job will run. It is green here and it is red on the tree in §5.

2608 passed, against 2553 when this branch started: three are
`tests/test_ci_runs_the_serial_scheduler.py` and the rest arrived with the merge. The measurements
in §5 were taken before it, on 2556, and are not re-taken — the merge touched no file this branch
touches and none of `pyproject.toml`, `tests/conftest.py` or
`tests/test_leaked_database_sweep.py`, so the defect §5 reinstates is reachable identically on
either side of it.
