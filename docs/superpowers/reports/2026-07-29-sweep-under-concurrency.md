# The vanished database was the sweep's own test, not a live run's

A full suite failed with `FATAL: database "sync_test_28096_gw2" does not exist` and the immediate
re-run passed. Three explanations were on the table. **The evidence supports the third**, and the
name that looked most incriminating is a coincidence: `gw2` in that string is a literal in a test,
not the worker that failed.

It reproduced. Twice, while writing this, with the same error shape:

```
FATAL:  database "sync_test_27888_gw2" does not exist
FATAL:  database "sync_test_15800_gw2" does not exist
```

Both in `test_a_database_that_cannot_be_dropped_does_not_fail_the_run`, on a server another
suite was sweeping.

## What that test does, and why it could not survive a shared server

```python
held = made(f"sync_test_{dead_pid}_gw2")     # created, and nobody is connected to it
free = made(f"sync_test_{dead_pid}_gw3")
with psycopg.connect(dsn_for(held, ADMIN)) as holder:   # <- fails here
```

The fixture deliberately names the database for a **genuinely dead pid**, because the sweep under
test has to find it sweepable. Between the `CREATE` and the `connect` the database is idle and
named for a dead process, which is exactly the definition of a leak. Any other suite sweeping the
same server in that window drops it — **correctly** — and the test then fails on its own next
connection.

The `_gw2` and `_gw3` suffixes are hard-coded in that test. The reported failure named `_gw2`.

## Two measurements the diagnosis rests on

**A worker's database is named for the controller, not for the worker.** `pytest_configure`
exports `SYNC_DSN` before xdist spawns anything, so every worker subdivides the controller's name.
Measured on a two-worker run:

| worker | its own pid | database it was given |
|---|---:|---|
| `gw0` | 15944 | `sync_test_30080_gw0` |
| `gw1` | 34508 | `sync_test_30080_gw1` |

30080 is the controller. Neither worker's pid appears anywhere.

**Plain `DROP DATABASE` protects a connected database and not an idle one.** Measured directly
against the server:

```
idle database, plain DROP        : SUCCEEDED -- 'in use' did not protect it
connected database, plain DROP   : refused -- database "sync_w80_probe" is being accessed by other users
```

The design argument for plain-over-`FORCE` holds, and its reach is narrower than it read: it
protects a database somebody is *connected to*, not one somebody is *about to use*.

## The three interleavings, and which the implementation survives

| interleaving | before | after |
|---|---|---|
| the name's pid is alive | **survives** — skipped | survives |
| the name's only pid is dead | **survives** — swept, which is the point | survives |
| the name's pid is dead and a live process is using the database | **fails** — swept out from under it | survives |

The third is reachable in production without any liveness bug: a controller killed before its
workers leaves them running against databases named for a pid that is now dead. It is also what
the test above walked into on every run, deliberately, because it had no other way to make the
database sweepable.

## Explanations 1 and 2, and why neither is it

**The liveness test is sound.** Measured: own pid `True`, a live child `True`, the same child
after `kill()` `False`, pid 0 `True`, an unallocated pid `False`. `os.kill(pid, 0)` really does
not answer this on Windows and `GetExitCodeProcess` really does.

**One latent defect found in it, erring safe.** `kernel32.OpenProcess` is called with no
`restype`, so ctypes returns `c_long` — 4 bytes — where a Windows `HANDLE` is 8. Handles observed
here are 372 and 396, so nothing truncates today. A handle whose low 32 bits were zero would read
as failure and fall to the error branch, which returns "alive" unless the *stale* last error is
`ERROR_INVALID_PARAMETER`. That is a plausible check that is not checking what it says, of the
same family as the `st_mtime_ns` rule, and it is recorded here rather than fixed because it did
not cause this and a change to the liveness path wants its own evidence.

**Pid reuse cannot cause a wrong drop.** It causes a wrong *skip*: a name holding a recycled pid
is spared and leaks until a later run. That is one database, against a live one.

## What changed

**Every pid in a name has to be dead before it is swept**, not only the leading one, and a
worker's database now carries the pid of the process that uses it: `sync_test_30080_gw0_p15944`.
The controller's pid stays, because an operator reads it to find the run.

This is a tightening. A name the new rule spares is one the old rule would have dropped, and no
name becomes newly eligible, so the sweep cannot reach further than it did. The cost is in the
direction this file already chose: a recycled pid anywhere in a name leaves one database behind.

`sweep_leaked_databases` takes `is_running` as an argument, so a test can name its fixtures for
its own **live** pid and still have the sweep under test treat them as dead. That is what removes
the race from the two tests that create a database and then connect to it, and it is scoped —
`pid != os.getpid()` rather than a blanket `False`, because a blanket answer would have the test
drop every leaked-looking database on a shared server, including live ones. That was tried and it
did exactly that.

## Mutations

| mutation | caught by |
|---|---|
| back to the leading pid only | 2 interleaving tests, including the controller-died case |
| the worker's pid is not put in the name | `..._carries_the_worker_that_uses_it` |
| a pinned database gains a pid it should not | `..._a_person_chose_gains_no_pid` |
| only the trailing pid is read, not the leading one | 2 tests, including recycled-pid sparing |

## What was not done

The sweep was not disabled, no retry was added, and the pattern was not widened. The advisory
lock was considered and rejected: serialising two sweeps does not help, because a single sweep
acting alone is what drops a live-but-idle database. The `restype` defect is reported and left.
