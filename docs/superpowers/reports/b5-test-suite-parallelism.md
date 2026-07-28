# B5 — parallelism is worth it, and one fixture had to change first

Commit `ba6d2b8` on `stroland02/m1-forge`, rebased onto `origin/main` at `07390fa`.

Files changed: `pyproject.toml`, `uv.lock`, `tests/conftest.py`, and one new file
`tests/test_parallel_isolation.py`. Nothing under `src/` was touched, and no source change
turned out to be required.

**Recommendation: adopt `-n auto`.** The suite goes from 133 seconds to 46, twelve
consecutive parallel runs passed with no failures, and the one fixture that was not
parallel-safe was fixable in `tests/` without weakening a single assertion.

## The numbers

All timings are the full suite, 867 tests, `SYNC_DSN` pinned to `sync_b5`. The machine has
12 logical cores and was running roughly six other agent worktrees throughout, so every
figure here is depressed by the same background load; the ratios are the part worth reading.

| Workers | Wall clock | Speedup |
|---|---|---|
| serial | 133.6s | — |
| `-n 2` | 90.5s | 1.5× |
| `-n 4` | 56.1s | 2.4× |
| `-n 6` | 62.7s | 2.1× |
| `-n 8` | 52.0s | 2.6× |
| `-n 12` | 45.8s | 2.9× |
| `-n auto` (= 12 here) | 44.3s | 3.0× |

The `-n 6` reading is out of order against `-n 4`, which is what background load on a shared
machine looks like; it is not a real inflection.

Returns flatten hard after four workers — from 2.4× to 3.0× costs another eight processes.
That is the signature of a suite whose critical path is a handful of long serial subprocess
chains rather than a broad pile of short ones, which is exactly what the brief measured.

### Distribution mode matters more than the last four workers

| `--dist` at `-n auto` | Wall clock |
|---|---|
| `load` (default) | 47.7s |
| `loadfile` | 77.6s |
| `worksteal` | 41.7s |

`loadfile` is the trap. Pinning a whole file to one worker puts all of `test_github_forge.py`
on a single process, and since three files carry 79% of the wall clock, one of them becomes
the critical path and the other eleven workers idle. The default `load` is correct here for
precisely the reason the suite is slow.

`worksteal` measured 12% faster than `load`. **It was not soaked and I am not recommending it
on one sample.** If someone wants it, it needs its own ten runs first.

## Amdahl, briefly

The brief's own measurement said three files hold 95.5s of the 121s. Twelve workers cannot
beat the longest single test chain in those files, and 44s against a 133s serial run is close
to what that predicts. Adding cores past twelve would not help; the remaining time is one
worker waiting on `tsc` and `git`.

## What was not parallel-safe

One thing, and it broke loudly rather than subtly — which was lucky.

### `tests/conftest.py`, the per-process database — NOT safe. Fixed.

`pytest_configure` returned early whenever `SYNC_DSN` was set. Under xdist every worker is a
separate process resolving the same pin, so all twelve connected to one database. `GraphStore.ingest`
TRUNCATEs the graph tables (`src/sync/graph/store.py:81`), and a TRUNCATE takes ACCESS EXCLUSIVE.

Evidence, from an unmodified `-n auto` run:

```
5 failed, 788 passed, 68 errors in 46.54s
```

with 59 of those errors being `psycopg.errors.DeadlockDetected: deadlock detected`, and every
detail line the same shape:

```
Process 25606 waits for AccessExclusiveLock on relation 197735 of database 197309; blocked by process 25614.
```

The surviving five failures were the quieter half of the same cause — one worker's TRUNCATE
landing between another's INSERT and its SELECT, producing `assert 0 == 1` and
`KeyError: 'no vendor change 94541e28...'`. That is the failure mode the conftest docstring
already described for two concurrent suites; xdist just makes it twelve.

**The fix**: a worker subdivides the pin rather than ignoring it. `sync_b5` becomes
`sync_b5_gw0` through `sync_b5_gw11`. The escape hatch survives in the form that matters — an
operator who pins a DSN still gets that server and a name that says which run it belongs to.

This is not the same as making `SYNC_DSN` lose. A pin could never have been honoured literally
under xdist; twelve processes cannot share one database that each of them truncates. The
choice was between subdividing the pin and deadlocking on it.

Naming is covered by `tests/test_parallel_isolation.py`, six assertions on a pure function.
They caught a real hole during development: the first implementation derived an unpinned
worker's name from `DEFAULT_DSN`, which made two *concurrently launched* unpinned suites
collide on `sync_gw0`. The test failed, the fix threads the pid through, and the comment in
`database_for` says why `pinned_dsn or DEFAULT_DSN` is wrong there.

Those tests assert the naming rule only. That distinct names actually isolate the runs is a
claim about Postgres, and its evidence is the soak below, not an assertion.

### Everything else — safe, with the evidence rather than the reasoning

**`git`, `base_clone`, `patched_clone`** — safe. They build under `tmp_path`, and xdist gives
each worker its own `tmp_path` base. The thing that would have broken this is a test writing
global git state; `grep` for `--global`, `--system`, `HOME`, `Path.home`, `expanduser` and
`tempfile.` across `tests/` returns nothing outside `tmp_path`.

**`test_github_forge.py`'s bare remotes** — safe, same reason. Each remote is a directory
under the test's own `tmp_path`; there is no shared remote and no shared clone.

**`test_tsc_verify.py`'s "real dependency installs"** — safe, and less real than the brief
assumed. Every package-manager call in that file and in `test_deps.py` is monkeypatched
(`sync.index.deps.install_dependencies`, and `deps.subprocess.run` in `test_deps.py`). The
`vendored_clone` fixture hand-builds `node_modules` specifically so the test costs no registry
round trip. No test in this suite runs a real `npm`, `pnpm` or `yarn`.

**The `npx` cache is the one genuinely shared resource**, because `run_tsc` falls back to a
pinned `npx` download when a clone has no local compiler, and `_npx` lives in the user-global
npm cache. A warm machine hides any race there, so I forced a cold one: `npm_config_cache`
pointed at an empty scratch directory, then `-n auto` over the four files that reach `run_tsc`.
75 tests passed in 27.8s, and the scratch cache came out holding 64MB — so the download really
did happen, twelve workers deep, and npm's `cacache` handled the concurrent write.

**`test_routing_matrix.py`'s module-scoped `catalogue`** — safe, at a small cost. Under
`--dist load` a module's tests can split across workers, so `run_oasdiff_checks()` runs once per
worker holding one of them instead of once. It is a read-only subprocess against a pinned
binary, so this is wasted work and not a hazard.

**Database lifecycle** — the per-worker databases are dropped. `pytest_unconfigure` runs in each
worker process, and the database list before and after a run is identical. One `sync_test_*`
database on the server outlived my runs; `pg_stat_activity` shows it holding live connections
from another worktree's suite, so it is someone else's in-flight run rather than a leak of mine.

## The soak

Twelve consecutive full-suite runs at the recommended setting.

```
run1  867 passed in 46.37s      run7   867 passed in 51.83s
run2  867 passed in 45.09s      run8   867 passed in 48.54s
run3  867 passed in 51.55s      run9   867 passed in 50.08s
run4  867 passed in 52.53s      run10  867 passed in 48.89s
run5  867 passed in 57.07s      run11  867 passed in 48.87s
run6  867 passed in 47.54s      run12  867 passed in 58.68s
```

**Failure count: 0 of 12.** Exit status 0 every time.

Counting every parallel full-suite run made after the fix — the soak, the worker sweep, the
three distribution modes, the `addopts` verification and two runs with `SYNC_DSN` unset — that
is 24 parallel runs and no failure. Zero out of twelve does not prove the flake rate is zero;
it bounds it at roughly one run in twelve at 95% confidence, which is worse than it sounds.
The reason to trust it beyond that number is that the one unsafe fixture failed 73 tests rather
than one, and the remaining shared resource was tested cold on purpose.

## Where `-n auto` is configured, and the cost of that choice

It is in `addopts` in `pyproject.toml`, not in `.github/workflows/ci.yml`. **The CI workflow
needs no change** — its `uv run pytest` step now picks up parallelism, which is the strongest
form of "CI runs the same command as a developer does": literally the same command.

The alternative was `-n auto` in the workflow only, and it is worse for a specific reason. It
would leave developers serial and CI parallel, so a parallel-unsafe test would fail only in CI,
where it looks like infrastructure flakiness and gets rerun. Configuring it once means both
places schedule identically and a real concurrency bug fails on the machine of whoever wrote it.

**The cost, stated plainly, because it lands on the loop CLAUDE.md prescribes.** Worker startup
is a flat ~4 seconds, and it dominates a focused run:

| `pytest tests/test_core_contracts.py` | Reported |
|---|---|
| serial | 0.04s |
| `-n auto` | 4.81s |
| `-n0` | 0.04s |

That is a 100× penalty on the fastest inner-loop command. `-n0` removes it completely and the
comment in `pyproject.toml` says so at the point of configuration.

The overhead is process spawn, not the extra databases: creating twelve databases in parallel
measured 0.53s and dropping them 0.22s, against ~3.7s of fixed cost already present at `-n 2`.
It is Python interpreter startup plus `psycopg`/`langgraph`/`pydantic` imports, twelve times,
on Windows. Nothing in `tests/` can shrink it.

## Two caveats worth acting on

**The e2e run inherits this.** `addopts` applies to `-m e2e` as well, so the coordinator's e2e
invocation will spin up twelve workers for one test and buffer its output until it finishes.
For a long model-driven test that loses live feedback for no gain. **Run it as
`uv run pytest -n0 -m e2e ...`.**

**CI will see about 2.4×, not 3.0×.** GitHub's `ubuntu-latest` runner is 4 vCPU, so `auto`
resolves to 4 there. By the sweep above that is 56s from 133s — still worth having, but the
three-times figure is a 12-core number and should not be quoted for CI.

## Reproducing any of this

```sh
export SYNC_DSN=postgresql://sync:sync@localhost:5433/sync_b5
uv run pytest              # -n auto via addopts
uv run pytest -n0          # serial, for comparison or for a focused run
uv run pytest -n auto --dist worksteal   # the 12% that was not soaked
```
