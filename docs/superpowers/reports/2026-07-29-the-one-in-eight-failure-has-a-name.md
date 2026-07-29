# The one-in-eight failure has a name

**Date:** 2026-07-29
**Scope:** B40 — a full `uv run pytest` returned `1 failed` twice today and the identity was lost
both times.
**Outcome:** captured on run 5 of 14, diagnosed as a race between two pytest *runs* over one
Postgres server, reproduced deterministically in both directions, and fixed in test infrastructure.
`src/` is not involved.

## The name

```
tests/test_leaked_database_sweep.py::test_a_database_that_cannot_be_dropped_does_not_fail_the_run
```

Caught on **run 5 of 14**, worker `gw10`. Runs 1–4 were green. The whole output is at
`.cache/flake/run-05.txt`; the harness that kept it is `scripts/capture_flake.py`.

The failure is not an assertion. It is the test's own setup falling over:

```
held = made(f"sync_test_{dead_pid}_gw2")
free = made(f"sync_test_{dead_pid}_gw3")
with psycopg.connect(dsn_for(held, ADMIN), autocommit=True) as holder:
      ^^^^
psycopg.OperationalError: connection failed: FATAL:  database "sync_test_22000_gw2" does not exist
DETAIL:  It seems to have just been dropped or renamed.
```

The test creates a database and the database is gone by the next statement.

## What removed it

`sweep_leaked_databases` in `tests/conftest.py`, running in some *other* pytest process.

The sweep is deliberately server-wide: it selects every database matching `sync\_test\_%` whose
embedded pid is not running, and drops it, so that a run killed before its finalizer does not leak
a database forever. It runs from `pytest_configure`, in the controller, before any test executes.

Three tests in `test_leaked_database_sweep.py` created real databases **named for a dead pid** —
necessarily, because that is the only thing the sweep will consent to drop, and these tests exist
to watch a real `DROP DATABASE` succeed and a real one be refused.

A database named for a dead pid is exactly the bait every other pytest run is built to eat. All
runs on this machine share one Postgres on 5433. So any second run starting inside the window
between the `CREATE` and the `connect` takes the database out from under the test.

## Reproduced deliberately, in both directions

Not inferred from the traceback. Create the bait, start a second pytest run, look:

```
bait created, exists: True
second pytest run exit: 0
swept line: ['swept 7 leaked test database(s)']
bait still exists: False
```

**`--collect-only` is enough**, which is the sharpest part of the evidence: `pytest_configure`
sweeps before a single test runs, so a second run does not have to execute anything to destroy the
first one's fixture.

And the same experiment against the repaired naming:

```
old naming (dead pid)  survived a concurrent run: False
new naming (live pid)  survived a concurrent run: True
```

## What it is not

**Not connection exhaustion.** The measurement that rejected it stands and this does not overturn
it. The error is `database ... does not exist`, raised by the server after a successful TCP
connect; a connection limit reports `too many clients already`. Nothing here counts connections.

**Not order dependence inside a run.** The sweep runs once, in the controller, before any test
starts, and is gated to `worker is None` so no xdist worker repeats it. Two tests on one worker
cannot produce this in either order. The varying factor is a second *process*, not a second test.

**Not product code.** `sweep_leaked_databases`, the fixtures and the failing test are all under
`tests/`. Nothing under `src/` participates, so the boundary that required stopping was never
reached.

**Not a slow machine on its own** — but load widens the window. The red run took **354.96s**
against 108–122s for the four green ones, which is consistent with a longer gap between the create
and the connect and therefore a larger target.

## Honest attribution of this particular instance

While the harness was running I was separately running a candidate test twenty-five times in a
loop. Each of those is a pytest process, each swept on startup, and that almost certainly fired
this instance. I am not going to present it as a clean catch.

It does not change the diagnosis, because the mechanism does not care where the second process
came from. Two worktrees — `sync-solo-a` and `sync-solo-b` — have been running suites against this
one Postgres all day, which is the same collision with a different second process, and is the
condition under which the coordinator saw it twice. What my loop did was raise the rate, not
invent the failure.

## The repair

The bait now carries **this process's own live pid**, and the sweep under test is handed a probe
that reports it finished:

```python
dropped = sweep_leaked_databases(ADMIN, is_running=_finished)
```

`leaked_database_names` already took `is_running`; only `sweep_leaked_databases` needed it threaded
through, and the production call keeps the default.

What this preserves: the drop is a real `DROP DATABASE`, the refusal on an in-use database is a
real refusal, and the sweep still has to go on and drop the others. What it removes from these
tests — whether the *real* probe can tell a finished process from a running one — is asserted
separately and unchanged by `test_the_probe_tells_a_finished_process_from_a_running_one`, which
spawns a process, waits for it, and asks `pid_is_running` directly.

What it changes for everyone else: a bait named for a live pid is invisible to every other run's
sweep, because their probe is the real one and the pid is running.

Nothing was skipped, quarantined, retried or slept on.

## What is still open

**The window is closed for these three tests, not as a class.** Any future test that names a
database after a pid nobody is running re-opens it. The docstring on `sweep_leaked_databases` now
says so at the point where somebody would write that test.

**Concurrent suites still share one server.** That is by design and already handled for the
databases a run uses for itself — those carry a live pid and the sweep spares them. This was only
ever a problem for databases manufactured to look dead.

## Gates

Run at `ac299c8`.
