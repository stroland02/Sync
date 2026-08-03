# A retried replay converges

**Date:** 2026-08-03
**Task:** M3-W124
**Answer taken:** neither shape the predecessor named — the conflict clause stops accumulating
for synthetic sources, so re-execution converges wherever the write happens and however often.

This closes the second of the two conditions M3-W116 set before the replay tier can write
`source='replay'` rows.
`docs/superpowers/reports/2026-07-30-replay-shapes-reach-the-store.md` carries the argument and
the measurements this one builds on;
`docs/superpowers/reports/2026-07-31-traffic-and-non-traffic-shapes.md` closed the first
condition. Neither is restated here.

## The condition, read off the code rather than taken from the brief

Three facts, each verified against the source before anything was changed.

`GraphStore.record_observed_shape` merged `sample_count` as `observed_shape.sample_count +
EXCLUDED.sample_count`. `route_after_replay` (`src/sync/remediate/nodes.py:485`) returns `patch`
for any outcome in `_REPLAY_FAILURES`, and `MAX_STATIC_ATTEMPTS` is 3
(`src/sync/remediate/state.py:16`). The multiplier is not inferred from those three: it is
already asserted through the real graph by
`tests/test_replay_stage.py::test_a_replay_failure_is_retried_rather_than_abandoned_on_the_first_round`,
which drives `mishandles` to abandonment and asserts `sequence.count("replay") ==
MAX_STATIC_ATTEMPTS`.

So a writer in the replay node would have written the same rows three times for one finding. And
the same rows, not merely rows of the same kind: each pass synthesizes the mock from the same
`plan["schema"]` against the same baseline, and condition (1) means that baseline no longer moves
when replay writes. One body, three writes.

## What convergence has to mean here

`CLAUDE.md`: "Every stage is idempotent. Re-running INDEX, SIGNAL, or DETECT on the same input
converges on the same rows."

W116 recorded that this table satisfied that in rows and broke it in meaning — the row converges
and the counter does not. That is the whole of the defect, and it locates it precisely:
`sample_count` is the only column in the conflict clause whose merge is not idempotent.
`nullable_seen` is `OR`, `spec_enum_values` is a set union, `first_seen` is `LEAST` and
`last_seen` is `GREATEST`. Every one of those is idempotent, commutative and order-independent,
which is why the clause already survives an error-payload batch arriving hours after a replay
observed the same shape. Addition is none of the three.

That framing is what decides between the candidates, because **convergence under re-execution is
a property of the merge, not of the key and not of the write site.**

## The two shapes W116 named, weighed and measured

Both measurements were taken against a real Postgres 16 on port 5433 (`sync_w124`), not read off
the DDL.

### A run key on the row, so a retry updates rather than adds

The shape: add a `run_key` column, put it in the natural key, and let a retried attempt land on
the row its first attempt created.

**It does not converge, and the reason is not incidental.** A run key changes *which* row the
addition lands in. It does not stop the addition, and the retry is precisely the event that
writes the same key a second time. Measured over a table with `run_key` in the unique constraint
and the existing additive clause, three retries of one finding:

| run key | rows | `sample_count` on the row |
|---|---|---|
| `finding-1` (stable across the retry loop) | 1 | **3** |
| `finding-1/attempt-N` (one per attempt) | 3 | 1 each |

The first is the shape as described and it reproduces the defect exactly. The second converges
only because no key is ever written twice — and a run resumed from a checkpoint re-runs an
attempt, which writes one twice again. Either way the additive merge has to change, so this
candidate does not stand on its own: it is the answer taken, plus a column.

What the column would then cost is not small. It changes the grain of the table for every source,
including the two that write traffic today. It needs a value for every row written before it
existed, on the `unattributed` precedent `CLAUDE.md` records. It grows the table once per run
without bound, in Sync's own runs rather than in customer traffic. And it would need threading
through `RunState`, which carries no run identifier today — so it also reaches
`src/sync/remediate/`, where W116 was careful to keep this decision out of.

Rejected. It buys an audit trail nobody has asked for, and `migration_outcome` already records
which runs happened.

### A write point the retry loop cannot re-enter

The shape: leave the clause alone and write once per run, somewhere the loop cannot reach twice.

**There is no such point, and even at the terminal nodes the shape solves the wrong multiplier.**

Read off `src/sync/remediate/graph.py`: `patch`, `static_verify` and `replay` are in the loop by
`route_after_replay`; `push_branch` and `await_ci` are in it too, because `route_after_ci`
returns `patch` on a red CI run. What remains is `open_pr`, `report` and `abandon` — the three
terminals — and a write there makes the store's contents a function of how a run *ended*. W116
rejected its own candidate 2 for exactly that, calling it the same silent-loss shape as an
undeclared reducer, and a run interrupted mid-flight would write nothing at all.

The larger objection is that this bounds the wrong number. Writing once per run removes the ×3
and leaves the ×N over runs, and N is the one that reaches the floor. Measured, one write per
run against the store as it stood:

| runs over one operation | rows | `sample_count` | `MIN_SAMPLES` |
|---|---|---|---|
| 30 | 1 | **30** | 30 |

That is W116's central complaint arriving anyway, one release later: thirty replays are one
synthesized body observed thirty times, satisfying a number chosen for thirty *independent*
samples. `tests/test_replay_shape_writeback.py::test_no_number_of_replays_lifts_a_synthesized_shape_over_the_sample_floor`
is that measurement kept as an assertion, and it fails against this candidate.

Rejected.

### The third answer, that convergence cannot be had

Available, and its premise is false. Convergence can be had, more cheaply than either shape, so
the tier staying unwritten permanently is not what the evidence supports. There is a separate
question about whether the writer should ever be reinstated — see below — but it is a question
about what reads the rows, not about whether they converge, and answering condition (2) with it
would have been answering a different question.

## What was taken

`sample_count` adds only for a source in `TRAFFIC_SOURCES`. For a source in `SYNTHETIC_SOURCES`
it is held at the largest single claim made about the row:

```sql
sample_count = CASE
    WHEN observed_shape.source = ANY(%s)
    THEN observed_shape.sample_count + EXCLUDED.sample_count
    ELSE GREATEST(observed_shape.sample_count, EXCLUDED.sample_count)
END,
```

No column, no migration, no backfill, and nothing to thread through the graph. A synthetic row
converges after the first write and stays converged at any repetition count, from any write site,
in any order, across runs as well as within one.

The classification is read from `sync.graph.sources` rather than asserted by the caller. A row's
merge and a row's audience are the same question about the mechanism that produced it, and
answering them from two lists would let them disagree. That module now says so.

**A maximum rather than the three cheaper ways to converge**, and each rejection is a test:

- `DO NOTHING` for synthetic rows converges and throws away the rest of the merge — the null a
  later body proved, the published member an earlier specification named, the window the row
  covers. Only the counter should be held.
  `test_a_synthetic_row_written_again_still_gains_evidence_and_widens_its_window`.
- Taking `EXCLUDED.sample_count` rewrites history. Rows already in a database were written under
  the additive clause and some hold counts above one; the next write would silently reset them to
  1, which is a migration performed by a merge.
  `test_a_synthetic_count_written_before_this_clause_is_not_rewritten`.
- Keeping whatever the row already held makes the counter the one column in this clause that
  depends on arrival order, in a clause built around sources not arriving in order.
  `test_a_synthetic_rows_count_does_not_depend_on_arrival_order`.

## The grain, which is what changed about the table

No column was added, so `CLAUDE.md`'s rule does not bind by its letter. It binds by its subject:
the grain comment made a claim about `sample_count` that this change makes source-dependent, and
a claim like that going quietly stale is the failure the rule exists to prevent. The comment was
written before the clause.

The grain itself is unchanged — one row per `(vendor_id, operation_id, field_path, json_type,
source)`. What the comment now adds is what the counter on that row means:

> **`sample_count` means one thing per source class and merges accordingly**, and it is the
> sentence above that forces the split rather than an exception to it. For a traffic source the
> write is a response somebody received, so a second write is a second sample and the counter
> adds. For a synthetic source [...] a second write is the ingest running again over the same
> constructed body, so the counter holds: it is the largest single claim made about the row
> rather than the sum of the claims. One row still means one shape; for a synthetic source it
> also means one sample, at any repetition count.

It names the replay tier as the case that forces it, and it records that a run key does not fix
it, so the candidate rejected above is not rediscovered from scratch.

**One duplicate of that statement could not be updated.** `ObservedShape`'s docstring in
`src/sync/core/models.py` carries the same grain paragraph, and `sync.core` is a published
contract this task must not edit. Its mechanism sentence — "observing a shape a second time
increments it" — is now true for traffic and over-stated for synthetic sources. Its *reason* is
this change's reason verbatim: "a table that appended instead would make every presence rate a
function of how often the ingest ran rather than of what the vendor sent." Whoever next owns
`sync.core` should qualify the sentence; nothing depends on it in code.

## The rung rule, and what it did and did not decide

`CLAUDE.md`: every binding carries the rung it came from, and so does every artifact derived from
it. W116 established that `source` is not a rung — `ObservedShape` is evidence, not a binding, and
the ladder attributes bindings. That reading is unchanged and this task did not touch
`binding_rung` anywhere.

What the rule does contribute is the direction of the fix. A replay row is evidence about a
specification, not about a vendor, and the harm W116 measured was that nothing in the row let a
reviewer discount it. Condition (1) keeps such a row out of every answer read as traffic.
Condition (2) adds that its count cannot grow into something that *looks* like accumulated vendor
evidence — a `sample_count` of 30 on a synthesized row is exactly the artifact a reviewer cannot
attribute, and it is now unreachable rather than merely filtered.

## The pin that changed direction

`test_a_second_write_of_one_shape_converges_on_a_row_and_not_on_a_count` asserted `sample_count
== 3` and now asserts 1, as
`test_a_second_write_of_one_replay_shape_converges_on_a_row_and_on_a_count`. The name gained
`replay` as well as losing `not`, because a traffic counterpart now sits beside it and the two
would otherwise differ only in a negation.

It was not retired and it did not become awkward. W116 wrote that figure deliberately, to record
the half of the idempotency rule the table did not satisfy, and it is the defect that went away.
The mutation reinstating the old behaviour — the clause reverted to unconditional addition — is
`M1` below, and it kills the inverted assertion. That is the check the brief asks for: an
assertion that changed direction has to be shown to fail against the behaviour it used to pin.

**A frozen counter would satisfy the inverted assertion just as well**, and that is the way this
change could have converged everything by destroying the sample floor. So
`test_a_second_write_of_one_traffic_shape_still_counts_twice` sits beside it in the same file
rather than only in `tests/test_observed_shape_sources.py`, on W119's precedent that an absence
asserted without its counterpart is vacuous. `M2` — the clause holding the counter for every
source — is the mutation that reaches it.

The write-side pair in `tests/test_observed_shape_sources.py` is parametrised over
`TRAFFIC_SOURCES` and `SYNTHETIC_SOURCES` rather than over the values written there, so a fourth
source added to `sync.graph.sources` arrives with a merge assertion instead of taking whichever
branch it happens to fall into. That is the same discipline
`test_every_declared_observation_source_is_classified` already applies to the read side.

The three tests holding the tier to writing nothing are unchanged and still read every source
through `_writes_nothing`.

## Is condition (2) closed, and what does reinstatement own

**Condition (2) is closed.** A retried replay converges, and so does a repeated one: the rows a
real `make_replay` builds, written once per attempt across the whole retry budget, produce one row
per shape at `sample_count` 1, and thirty repetitions do not reach `MIN_SAMPLES`. Both are
asserted against a real database over rows the tier actually produced rather than hand-built ones.

**The writer is not reinstated here and this task was not authorised to reinstate it.** Both
conditions being satisfied makes the write safe; it does not make it right, and those are
different claims.

What the reinstatement task owns:

1. **The write itself**, in the replay node. W116 established the node over the caller and nothing
   here disturbs that: `make_replay` already holds the store and already reads it in `_observed`,
   while a caller draining `state["replay_shapes"]` would make the store's contents a function of
   how a run ended. It needs no schema change and no run key.
2. **A before-and-after over the two consumers**, since it is switching on a writer whose rows two
   readers used to see. The measurement to repeat is W116's: severity of a real divergence, and
   the mock built for the next replay, with and without the writer.
3. **The question neither condition asked: what reads a `replay` row.** With condition (1) landed,
   `ObservedDriftDetector` and the mock builder both answer traffic-only, so no caller in `src/`
   receives one. The specification's stated purpose for these rows — "the baseline begins
   accumulating before any customer installs anything" — is the reading condition (1) correctly
   forbids, so it cannot be the justification. A writer whose rows nothing reads is cost without a
   consumer, and that has to be answered before the write rather than after. This is a finding of
   this task, not a condition it sets, and it is why the specification's Sequencing row still says
   the tier is deliberately not a feeder.
**The fourth item this section carried is closed, and reinstatement does not own it.** W119's
second finding — a single `sample_count=1` row of *any* source escalating a divergence to
`breaking` — was still open when this task was interrupted, and M3-W122 answered it in the
meantime: `MIN_SAMPLES` now reaches the sibling window, and a thin earlier observation grades
`info` with a rationale naming its count and the floor. It is merged into this branch, and
`test_a_traffic_row_under_the_floor_still_escalates` is the pin it inverted in place, now
`..._no_longer_escalates`. `docs/superpowers/reports/2026-07-31-the-sibling-window.md` carries it.

That change and this one land on the same row from opposite sides, and neither depends on the
other. A synthetic row held at `sample_count=1` also cannot corroborate anything now, because the
floor excludes it — but condition (1) already keeps every `replay` row out of the detector's read,
so the floor is a second barrier behind a filter that was never going to let the row through.
Recorded because a reader comparing the two reports will notice the overlap, not because either
result rests on it.

## Verification

All measurements against a real Postgres 16 on port 5433. `sync_w124` for the suite and the
gates, `sync_w124_mut` for the mutation harness, both created by this task; no database created
by another task was dropped. `tests/conftest.py` subdivides a pinned `SYNC_DSN` per xdist worker,
so an `-n auto` run uses `sync_w124_gw0…gwN`, and its leaked-database sweep is confined to the
generated `sync_test_<pid>` pattern — a pinned name is outside it, which is why running here
cannot reach another task's database.

**Which scheduler produced which number.** The mutation harness and its baseline are `-n0` over
twelve files, because a survival has to be attributable to a test rather than to a worker that
died. The gates run on both schedulers, `-n auto` being the `addopts` default a developer gets
and `-n0` being CI's. The two candidate measurements above — the run-key table and the thirty-run
table — are direct writes against the server through `GraphStore`, with no pytest involved and so
no scheduler.

**No figure here was transcribed from a remembered number**, and that is the whole reason this
report took three attempts. Two session limits ended between measuring and writing, and a
measurement that exists only in an agent's context is a measurement nobody has. The mutation
results were re-measured on the merged tree at 07:45, after `af0365e` landed at 07:30, and are on
disk in the harness's own run log; the baseline moved from 231 to 235 across that merge, which is
what a stale figure would have hidden. The gate figures below are this attempt's, on `7ec8be1`.

Suite baseline for **this worktree**, measured at `da6a820` before the branch was merged onto it:
**2778 passed, 1 skipped**, exit 0, `-n auto`, 140s. That matches the figure `main` reports, so
this worktree's gitignored `.cache/specs/` is populated and no extra environmental skip is in play.
Recorded first so a mutation harness does not read a checkout difference as drift.

### The retried run, asserted against the server

The failing test this change was written against is
`test_the_rows_a_retried_replay_would_write_converge_over_the_whole_retry_budget`. It is not a
hand-built row: it drives `make_replay` over the `mishandles` fixture, which is the outcome
`route_after_replay` returns to `patch`, takes the `ObservedShape` rows that run actually built,
writes them once per attempt across `MAX_STATIC_ATTEMPTS`, and then reads back **through the
store** with `observed_shapes(..., traffic_only=False)`. It asserts one row per shape and
`{row.sample_count for row in rows} == {1}`.

Against the additive clause it read 3 and failed for that reason. That is the direction the brief
asked to see, and it is the same figure W116 recorded as the defect.

`traffic_only=False` is the read the subject requires rather than a concession to condition (1)'s
filter: the rows are `replay` rows, and a traffic-only read returns empty whether the second write
merged, added, or was discarded, so it cannot tell those apart. A test written that way would
have passed against the defect.

### The schema, applied twice to a database that already holds rows

`CLAUDE.md` requires the grain declared before a column is added, and idempotence of every stage.
No column was added, so the risk is not a backfill — it is that re-applying the schema over a
populated database disturbs rows written under the old clause. Both are asserted against a
database holding rows rather than inferred from the DDL:

| Test | Set up | After two `apply_schema()` calls |
|---|---|---|
| `test_rows_written_before_the_filter_existed_survive_a_second_apply_schema` | `error-payload` at 7, `replay` at 5 | both intact — `{"error-payload": 7, "replay": 5}`, and the traffic read still returns `error-payload` alone |
| `test_a_held_synthetic_count_survives_a_second_apply_schema_and_a_further_write` | `replay` at 5 | still `[5]` after a *further* write — neither reset to 1 nor advanced to 6 |

The second is the one that binds the clause rather than the column list. A `replay` row at 5 could
only have been written under the additive clause, so it is exactly the history this change could
have rewritten: taking `EXCLUDED.sample_count` would reset it to 1, and continuing to add would
carry it to 6. `GREATEST` holds it at 5. Mutations `M3` and `M5` are those two wrong answers, and
both are killed by this test among others.

### Mutation

Baseline for the harness: **235 passed, exit 0, `-n0`**, over the twelve test files that can
reach this change. The four tests between this and the earlier attempt's 231 are M3-W122's, in
`test_observed_drift.py` and `test_detector_declines.py`, which the harness covers because the
detector is a reader of the rows this change writes.

| Mutation | Verdict | Killed |
|---|---|---|
| M1 the clause reverts to unconditional addition (the change reverted) | killed | 8, including `test_a_second_write_of_one_replay_shape_converges_on_a_row_and_on_a_count` and `test_a_synthetic_row_written_again_does_not_count_again[replay]` |
| M2 the clause holds the counter for every source | killed | 8, including `test_a_second_write_of_one_traffic_shape_still_counts_twice`, `test_a_traffic_row_written_again_counts_again[error-payload]`, `[interceptor]`, `test_recording_the_same_shape_twice_counts_it_twice_in_one_row`, `test_a_batch_adds_its_whole_count` |
| M3 the synthetic branch takes the incoming count | killed | 3, including `test_a_synthetic_count_written_before_this_clause_is_not_rewritten` |
| M4 the synthetic branch keeps whatever arrived first | killed | 1: `test_a_synthetic_rows_count_does_not_depend_on_arrival_order` |
| M5 the synthetic branch pins the count at one | killed | 3, including `test_a_held_synthetic_count_survives_a_second_apply_schema_and_a_further_write` |
| M6 the clause is matched against `SYNTHETIC_SOURCES` (the partition inverted on write) | killed | 16 |
| M7 `replay` classified as traffic (the partition broken) | killed | 14, including `test_a_reader_asking_for_traffic_does_not_receive_a_replay_row` |
| M8 the replay writer reinstated (W116's candidate 1) | killed | 3: `test_a_successful_replay_builds_shape_rows_and_writes_none_of_them`, `test_a_failed_replay_builds_shape_rows_and_writes_none_of_them`, `test_the_offered_shapes_are_carried_and_not_written` |

No mutation survived and no false-verdict mode fired.

**`M1` and `M4` are the two worth naming.** `M1` is the behaviour the inverted pin used to
assert, so its kill is the failing-first evidence for an assertion that changed direction rather
than for one that was written new. `M4` is killed by exactly one test — keeping the value already
on the row converges, holds history, and passes everything else — which makes
`test_a_synthetic_rows_count_does_not_depend_on_arrival_order` load-bearing on its own, and is
the reason the maximum was argued rather than assumed.

`M8` is the check that this change did not quietly make W116's central pin vacuous. It kills the
same three tests it killed against the previous tree, so switching the writer on is still visible
to the suite.

The harness separates killed, survived, did-not-compile (`compile()` before the write),
unreadable (exit ∉ {0,1}, and exit 1 with no `FAILED` line), baseline-drifted (pass count off
baseline), not-applied (anchor absent) and anchor-ambiguous (more than one hit) — reported
separately so a silent zero-hit replace cannot be scored as a survival.

**CRLF anchors.** All three mutated files are CRLF in the working tree. Anchors are written LF in
the harness and rewritten to the file's own newline before matching; without that step every
mutation reports not-applied.

`M8` edits `src/sync/remediate/nodes.py`, which this task must not change. It is restored
byte-for-byte from bytes read before the edit, in a `finally`, and `git diff --exit-code` over the
tracked tree returned 0 after the run. `M6` and `M7` edit `src/sync/graph/`, which this task owns,
under the same restore.

### The four gates

Run on `stroland02/m2-converge` at `7ec8be1` — the merged tree, with `af0365e` in it. The earlier
attempt's gate figures were taken on top of `d24f61f`, before the merge, and are not carried
forward.

| Gate | Result | Exit |
|---|---|---|
| `pytest -q` (`-n auto`, the `addopts` default) | *in flight* | |
| `pytest -q -n0` (the CI scheduler) | *in flight* | |
| `lint_encoding.py src scripts tests` | no output | 0 |
| `lint-imports` (unredirected, `PYTHONIOENCODING=utf-8`) | `Contracts: 1 kept, 0 broken`, 98 files, 203 dependencies | 0 |
| `lint_dead_links.py src --baseline scripts/dead_links_baseline.txt` | no output | 0 |
