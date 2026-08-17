# What the Postgres bounce actually is

**2026-08-17, Lane C, `CI-W362`.** The charter's queue item 2 asks whether the bounce is Docker
Desktop, a resource ceiling, or the leaked-database volume, and says it costs "about three minutes
of crash recovery each time". Measured against the running container: **it is none of the three, and
the recovery is 2.74 seconds.**

Both corrections matter, because the three-minute figure is what makes the bounce look like the
expensive problem, and the expensive problem is somewhere else.

## What the container says

| | |
|---|---|
| `RestartCount` | 0 |
| `OOMKilled` | false |
| Memory limit | 0 (unlimited) |
| Restart policy | `no` |
| Created | 2026-08-17 11:00:55 UTC |
| Started | 2026-08-17 11:01:11 UTC |

Created sixteen seconds before it started, which means this container was **new** at 11:00:55 — the
previous one was removed, not restarted. Docker did not do it: the restart policy is `no` and the
restart count is zero.

## What the log says

```
LOG:  database system was interrupted; last known up at 2026-08-17 10:59:40 UTC
LOG:  database system was not properly shut down; automatic recovery in progress
LOG:  redo starts at 0/191F190
LOG:  redo done at 0/D26E198 system usage: CPU: user: 0.93 s, system: 1.43 s, elapsed: 2.37 s
LOG:  database system is ready to accept connections
```

From process start (11:01:12.756) to accepting connections (11:01:15.499) is **2.74 seconds**, of
which Postgres attributes 2.37s to redo. **25 connections were refused while it ran.**

## Each candidate, and how it was eliminated

- **A resource ceiling — no.** `OOMKilled` is false, there is no memory limit set, and nothing was
  restarted by the daemon.
- **Docker Desktop going down — no.** The leaked `sync-patch-sandbox` container has `StartedAt`
  06:57:53 UTC and was still running hours after this event. A backend restart would have stopped
  it. The virtual machine never went down; only Postgres did.
- **The leaked-database volume — no.** `tests/test_leaked_database_sweep.py` already records that a
  leaked database holds no connections and was never the cause of anything. The volume survived and
  recovery replayed from it successfully.
- **The stop grace period expiring — no, and this one had to be measured rather than argued.**
  A scratch `postgres:16` with this compose file's exact flags, carrying **86 connections** under
  sustained `pgbench` write load, was stopped with a default `docker stop`: it completed in
  **2427ms** and logged `database system is shut down`. The 10-second default is four times what a
  clean shutdown needs here, so the termination was not a grace-period overrun.

**What is left is that something removed the container without letting Postgres shut down.** Nothing
in this repository instructs it — there is no `docker compose down`, `stop`, `restart` or `kill` in
any script, workflow, or document. So it is ad hoc, typed by hand, and the honest limit of this
finding is that the log cannot name which command it was. What can be said is that it was not any of
the automatic causes, and not the one plausible mechanical cause either.

## The cost is not the recovery, and this is the part worth fixing

2.74 seconds of recovery is cheap. What was expensive is what the suite did during it.

`tests/conftest.py`'s `pytest_configure` caught `psycopg.OperationalError`, warned "no Postgres",
and let the run continue **unisolated** — meaning `SYNC_DSN` stayed unset and every
database-touching test ran without its own database. `psycopg.errors.CannotConnectNow` is SQLSTATE
`57P03`, "the database system is starting up", and it is an `OperationalError` **subclass**. So a
run that reached collection inside that 2.74-second window was told the server did not exist.

That is a mass red with a diagnosis cost, from a condition that resolves itself in under three
seconds.

**Postgres distinguishes the two states and the code did not.** A server that is absent refuses the
socket and raises a plain `OperationalError` with no SQLSTATE — there is nothing to wait for. A
server that is recovering answers, and says so with a code. `admin_connection_once_ready` now waits
out the second and still fails immediately on the first, bounded at 60 seconds against a measured
2.74.

This is the third instance of one shape found in this lane today, after `B183` and `B184`:
**"we could not check yet" collapsed onto "there is nothing here."** It is worth naming as a class
rather than fixing three times and moving on.

## What was deliberately not done

- **`stop_grace_period` was not added to `docker-compose.yml`.** It was the obvious fix and the
  measurement above says it would be decoration: a clean shutdown under load takes 2427ms against a
  10s default. Adding it would have looked like a fix and closed nothing.
- **The shared container was not restarted, stopped, or recreated.** Five other sessions are on it.
  Every measurement here comes either from reading its logs and metadata, or from a scratch
  container that was removed afterwards.
- **The charter was not edited.** `docs/superpowers/orchestration/` is the coordinator's. The two
  corrections — the cause, and 2.74s rather than three minutes — are reported instead.
