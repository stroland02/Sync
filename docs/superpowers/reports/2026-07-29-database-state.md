# What the running Postgres actually holds

**Date:** 2026-07-29
**Server:** PostgreSQL 16.14 in Docker, `localhost:5433`, `max_connections = 100`
**Answers:** `2026-07-29-sync-spec-audit-log-2.md`, "What could not be verified" — *"It is a
database fact. That `migration_outcome` and `observed_shape` hold no rows is asserted by five
documents and was not confirmed against a running Postgres."*

## The short answer

**The claim is confirmed in the state the five documents describe, and false in a state they do
not mention.** No real pipeline run has produced a corpus row anywhere on this server. But the
test suite writes real rows through the real writers, and a database it has been pointed at is
not empty — which matters because that is a developer's own database, not a hypothetical.

The developer default was measured twice, either side of a crash and a repair that happened
mid-task: stale-but-populated schema with both tables at zero beforehand, and a bare database
with no tables at all afterwards. Both confirm the claim. §1 keeps them apart rather than
letting the survivor stand in for the other.

One spec sentence was corrected. Four documents needed no edit. §6 says which and why.

## 1. The two states measured

### The developer default, `sync`

`DEFAULT_DSN` in `tests/conftest.py` is `postgresql://sync:sync@localhost:5433/sync`, and that is
what a developer gets with `SYNC_DSN` unset. Measured at 10:5x on 2026-07-29:

| table | rows |
|---|---|
| `call_site` | 1 |
| `vendor_change` | 1 |
| `finding` | 0 |
| `observed_call` | **table absent** |
| `migration_outcome` | **0** |
| `observed_shape` | **0** |

**Both tables of interest are empty. The claim holds here.**

Two things fell out that nobody asked about. `observed_call` does not exist in that database at
all, and `call_site` has no `loop_depth` column and `finding` no `claim` column — so it predates
three separate schema additions and `apply_schema` has not been run against it since before
`observed_call` landed. It is a stale database that would fail on the first insert naming any of
the three, which is the defect `2026-07-29` schema-convergence work fixed for columns going
forward.

**Those counts are of a state that no longer exists, and this report keeps the two apart.**
Shortly after they were taken the shared server crashed and recovered (§5), and `sync` was
afterwards found invalid — `datconnlimit = -2`, connections refused. A coordinator then dropped
and recreated it, because three tasks' suites were failing against it. So:

| | pre-repair, measured 2026-07-29 before the crash | post-repair, measured after |
|---|---|---|
| schema | present but stale — no `observed_call`, no `loop_depth`, no `claim` | **no tables at all** |
| `migration_outcome` | **0** | no such table |
| `observed_shape` | **0** | no such table |

The pre-repair figures are the historically interesting ones and they are recoverable only
because they happened to be taken before the crash; the post-repair database is a bare
`CREATE DATABASE` against which `apply_schema` has not been run, so it answers the fresh-checkout
question and nothing about history. **Both confirm the claim, by different routes.** Neither is
presented as the other.

**On the cause, deliberately less than the evidence seems to offer.** `datconnlimit = -2` is the
marker Postgres leaves for a `DROP DATABASE` that did not finish, and it is tempting to read it
as somebody having dropped the shared database instead of using their own `SYNC_DSN`. That
reading fits, and it is not the only thing that fits: a crash mid-recovery leaves the same marker
with nobody having issued a drop at all, and the crash is independently reported by two sides. So
what this report records is that **the database was found invalid after a crash and recovery of
the shared server**, and no more than that.

One observation worth keeping as a fact, and worth not over-reading: every per-worker database
checked at the same moment was healthy at `datconnlimit = -1` — `sync_w1`, `sync_w2`, `sync_w31`,
`sync_w35`, `sync_w41`, `sync_w69` and others — while only the shared default was invalid. That
is consistent with the shared one simply being the database under constant load from every suite
run, and a crash sparing databases nothing was touching. It is not evidence of anyone's
misbehaviour and is not offered as any.

I did not drop or truncate `sync`. The only databases I created or dropped are the three named
`sync_w73*`, and they are dropped.

### Whatever the suite leaves behind

Two measurements on databases created for this purpose, each with a **pinned** `SYNC_DSN`, which
`conftest` deliberately does not drop or truncate — the per-run database and its teardown apply
only when `SYNC_DSN` is unset.

`tests/test_pipeline_composes.py`, the run that drives the real remediation graph:

| table | rows |
|---|---|
| `call_site` | 1 |
| `vendor_change` | 1 |
| `finding` | 1 |
| `observed_call` | 0 |
| `migration_outcome` | **3** |
| `observed_shape` | 0 |

`tests/test_shape_ingest_command.py` and `tests/test_observed_shape.py`:

| table | rows |
|---|---|
| every other table | 0 |
| `observed_shape` | **1** |

**So the suite leaves rows in both tables, through the real writers, whenever the database is
pinned.** These are not synthetic inserts: `record_migration_outcome` and `record_observed_shape`
are the same calls a deployment would make.

A *completed* unpinned run leaves nothing — `pytest_unconfigure` drops the database it created. A
*killed* run leaves the whole database behind, which is why §5 found 314 of them.

## 2. The grain, checked rather than assumed

`schema.sql` declares one `migration_outcome` row to be one **attempt**, not one finding. The
measurement is the case that punishes conflating them:

```
GRAIN: 3 attempts across 1 distinct finding(s)
 ('60e7305cdf6153535242c52a30ed05c6', 1, 'codemod', 0, 'retried',   None)
 ('60e7305cdf6153535242c52a30ed05c6', 2, 'codemod', 0, 'retried',   None)
 ('60e7305cdf6153535242c52a30ed05c6', 3, 'codemod', 0, 'abandoned', 'the remediator produced no change')
```

Three rows, one finding, three tiers of the same repair attempted and abandoned. A query counting
findings by counting rows reports three times the truth here, which is the first mistake
`2026-07-27-sync-pipeline-discipline.md` names.

`observed_shape` has the mirror property: its grain is one row per
`(vendor_id, operation_id, field_path, json_type, source)` and `sample_count` is a counter on the
row. The single row measured carries `sample_count = 1`, so one row and one observation happen to
coincide — which is exactly the case that would let a reader assume they always do.

## 3. Is it a real pipeline run, or the suite?

**The suite.** One database on the server other than mine held `migration_outcome` rows —
`sync_w46`, another task's pinned database, with three:

```
('d025f570e114860941628aaff1d35aaa', 1, 'codemod', 0, 'retried',   None, 'anthropic', 'typescript')
('d025f570e114860941628aaff1d35aaa', 2, 'codemod', 0, 'retried',   None, 'anthropic', 'typescript')
('d025f570e114860941628aaff1d35aaa', 3, 'codemod', 0, 'abandoned', 'the remediator produced no change', ...)
```

Same shape as my own reproduction in §2, down to the abandon reason and the tier: three attempts,
one finding, `test_pipeline_composes`. **No corpus row on this server came from a real pipeline
run.** The five documents' causal claim — *"no real pipeline run has yet produced one"* — is
confirmed.

## 4. Does anything write either table unattended?

**No. Confirmed from the code rather than inherited from the audit.**

| table | every writer | reached from |
|---|---|---|
| `observed_shape` | `SentryShapeReader.ingest` (`signals/sentry/shapes.py:145`), `DatadogShapeReader.ingest` (`signals/datadog/shapes.py:171`) | constructed only in `cli.py:951` and `cli.py:962`, under `sync shapes` |
| `migration_outcome` | `GraphStore.record_migration_outcome` (`graph/store.py:384`) via `remediate/corpus.py:286`, and `GraphStore.set_merge_outcome` via `forge/webhook.py:178` | `remediate/graph.py` under `sync run`; `sync merge-outcome` |

The CLI defines eight subcommands — `run`, `ingest`, `shapes`, `merge-outcome`, `publish`,
`public-key`, `intake`, `benchmark` — and every path above sits under one of them. A search for
`cron`, `schedule`, `apscheduler`, `celery`, `threading.Timer`, `asyncio.create_task` and
`while True` across `src/` returns no scheduler, no daemon and no background task; the `while
True` hits are parsing loops and one thread-id search in `cli.py:330`, none of which writes.

Commands re-runnable:

```bash
grep -rn "record_observed_shape" --include=*.py src/
grep -rn "record_migration_outcome|set_merge_outcome" -E --include=*.py src/
grep -rniE "\bcron\b|schedule|apscheduler|celery|threading\.Timer|asyncio\.create_task" --include=*.py src/
```

## 5. The environment, which is worse than the question asked

A sweep of every database on the server found **314 databases, 178 of them invalid** — that is,
`datconnlimit = -2`, unusable, removable only by an explicit `DROP DATABASE`. `conftest` drops its
per-run database at `pytest_unconfigure`, so each one is a run killed before it finished. Nobody
is cleaning them up.

While that sweep ran — one connection per database — alongside two concurrent twelve-worker xdist
suites, **the server exhausted `max_connections = 100` and crashed into recovery mode** for about
forty seconds. My sweep is a contributing cause and is the reason this report's measurements are
scoped to named databases rather than a scan. Symptoms other work may have seen and should not
chase: `FATAL: sorry, too many clients already`, `INTERNALERROR> KeyError: <WorkerController gwN>`,
and isolated detector failures that pass on re-run — `test_status_rate_detector.py` failed in a
full run and all 27 tests passed serially a minute later.

The `sync` database was found invalid after that window (§1). What produced the marker is not
established and this report does not claim it.

The count has since fallen sharply — **137 databases, 2 invalid** when this report was finished,
against 314 and 178 during the incident. Somebody cleaned up. The underlying condition has not
changed: `pytest_unconfigure` drops a per-run database only when the run reaches it, so every
killed run still leaves one behind, and nothing sweeps them on a schedule.

**The totals from the sweep are a lower bound, not a measurement**, because 182 of the 293
databases enumerated at the time were unreachable. They are recorded here only as context:
`call_site` 95, `vendor_change` 62, `finding` 7, `observed_call` 9, `migration_outcome` 3,
`observed_shape` 56, the last spread across six databases (1, 1, 11, 1, 11, 31).

## 6. What was corrected, and what was confirmed

**Corrected — one sentence, in `2026-07-27-sync-benchmark-gates.md`.** It read:

> The corpus holds no rows, because no real pipeline run has yet produced one, so every axis
> currently reports zero samples.

The causal half is right and is confirmed in §3. The flat present-tense half is not: a database
the suite has been pointed at holds three attempts, so `sync benchmark` aimed at a developer's own
database reports three samples of a fixture rather than the null the section goes on to reason
about. That sentence is the premise of the whole tier-B argument — the argument that axes report
null *because* the corpus is empty — so an over-broad version of it is load-bearing in the
direction that matters. The edit qualifies it and changes no part of the argument.

**Confirmed, unedited:**

- `2026-07-25-sync-migration-corpus.md` — *"no real pipeline run has produced a row yet."*
  Confirmed exactly, §3.
- `2026-07-26-sync-observed-contract-drift.md` — *"The baseline is empty until somebody feeds
  it… A deployment that never runs that command has an empty baseline and a detector that
  correctly finds nothing."* Conditional and correct: the only writers are the two shape readers
  under `sync shapes` (§4), and a deployment that never runs it has nothing.
- `2026-07-27-sync-pipeline-discipline.md` — its attempt-versus-finding grain claim is not just
  confirmed but demonstrated, §2.
- `2026-07-29-sync-spec-audit-log-2.md` — its own statement that the fact was unverified was
  true when written. This report is the verification; the audit entry needs no edit to have been
  right.

## 7. Commands, so a reader can re-run this

```bash
# The developer default. Since the repair in §1 this database carries no tables at all, so the
# query below errors rather than returning zeros -- which is itself the fresh-checkout answer.
# Run `sync run` or GraphStore.apply_schema() against it first if you want the tables.
psql postgresql://sync:sync@localhost:5433/sync -c "
  SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"
psql postgresql://sync:sync@localhost:5433/sync -c "
  SELECT 'migration_outcome' t, count(*) FROM migration_outcome
  UNION ALL SELECT 'observed_shape', count(*) FROM observed_shape;"

# What the suite leaves in a pinned database. Use a database of your own.
createdb -h localhost -p 5433 -U sync sync_scratch
SYNC_DSN=postgresql://sync:sync@localhost:5433/sync_scratch \
  uv run pytest tests/test_pipeline_composes.py -q -n0
psql postgresql://sync:sync@localhost:5433/sync_scratch -c "
  SELECT count(*) attempts, count(DISTINCT finding_id) findings FROM migration_outcome;"

# The shape half.
SYNC_DSN=postgresql://sync:sync@localhost:5433/sync_scratch2 \
  uv run pytest tests/test_shape_ingest_command.py tests/test_observed_shape.py -q -n0

# How many databases, and how many are unusable.
psql postgresql://sync:sync@localhost:5433/postgres -c "
  SELECT count(*) total, count(*) FILTER (WHERE datconnlimit = -2) invalid
  FROM pg_database WHERE NOT datistemplate;"
```

`-n0` matters: under xdist a pinned DSN is subdivided per worker and those databases are dropped,
so a parallel run measures nothing. Do not point these at a database you did not create — several
on this server belong to other work.
