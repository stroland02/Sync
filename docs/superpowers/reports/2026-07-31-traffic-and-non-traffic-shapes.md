# Traffic and non-traffic shapes are kept apart on read

**Date:** 2026-07-31
**Task:** M3-W119
**Answer taken:** candidate 1 — a `traffic_only` parameter on `GraphStore.observed_shapes`, defaulting to traffic.

M3-W116 established that the replay tier writing `source='replay'` rows into `observed_shape`
would be wrong rather than merely late, and closed with the two changes that have to land first.
This is the first of them. `docs/superpowers/reports/2026-07-30-replay-shapes-reach-the-store.md`
carries the measurements this one builds on and does not restate them.

## What `source` means on this table

`source` names the mechanism that produced a row, not the vendor it came from: Sentry and Datadog
both write `error-payload`, and `sync.signals.sentry.shapes` and `sync.signals.datadog.shapes`
are two adapters over one value. That is the property that keeps a classification of sources out
of the reach of `CLAUDE.md`'s rule that vendor knowledge lives in adapters — no adapter's name
appears in it, and none may.

The distinction the table has never had to make is a different one. Every source it holds today
is a response a vendor actually sent, so "what the table holds" and "what the vendor sent" have
been the same set, and the two consumers that read it as traffic were right by accident.
`ObservationSource` also declares `replay`, whose rows are the published specification restated
through the customer's code. Those are evidence about a specification, not about a vendor.

So traffic is a property a caller can ask for, and it is a property *of the mechanism* rather
than of the row's contents — which is what makes it answerable at all. `src/sync/graph/sources.py`
holds the partition as two sets, `TRAFFIC_SOURCES` and `SYNTHETIC_SOURCES`, written out rather
than derived from one another so that `test_every_declared_observation_source_is_classified` has
something to check. Membership is positive: a source added to `ObservationSource` and forgotten
there is then absent from every baseline rather than silently entering one. That failure costs
recall, and the alternative costs precision in the detector `src/sync/detect/observed_drift.py`
calls the one most able to violate precision-over-recall.

## The three candidates

**Taken: a filter parameter on the store, defaulting to traffic.** `observed_shapes` grows
`traffic_only: bool = True`. Neither consumer names a source; both get traffic because that is
what the reader answers by default, and an audit of the ingest asks for everything explicitly.

The default is the whole of the argument, and it is not a convenience. The brief's framing of
this candidate — "with both callers passing what they want" — is the version that does not work,
and the reason is `sync.remediate.nodes._observed`. That is the reader the mock builder is handed,
it lives in a package this task must not edit, and it calls `observed_shapes(vendor_id,
operation_id)` positionally with no keyword. **No argument a caller could have been made to pass
would have reached it**, because there was no edit available to make the caller pass one. A
default of `False` fixes the detector and leaves the mock feedback loop open, which is precisely
the half W116 said a detector-side filter would fix. Mutation `M3` below is that default flipped,
and it is killed by the test that reads through `_observed`.

The cost the brief named is real and is paid: the knowledge of which sources are traffic now sits
in `sync.graph.sources`, and the knowledge that traffic is the right answer sits in one default
rather than at two call sites that must not disagree. That is one place, not two.

**Rejected: a traffic classification on the row.** A column saying of a row whether it came from
traffic is the most expensive answer and would have been the most correct one if `source` were
open-ended. It is not: `ObservationSource` is a closed `Literal` in `sync.core`, so a fourth source
cannot appear without a deliberate edit to a published contract, and that edit is exactly the
moment a classification should be made. A column would record the same judgement per row, ten
million times, and would then need a migration, a grain comment, and a value for every row written
before it existed — `unattributed`, on the precedent `CLAUDE.md` records. It would also put the
classification on data rather than on the vocabulary, so two rows of one source could disagree,
which is a state nothing should be able to reach. The derived-property variant of this candidate
is what was built: `sources.py` *is* the classification, evaluated once per query rather than
stored per row.

**Rejected: neither, and the sibling window is the real defect.** The sibling window is *also* a
defect — see below, it is this task's second finding — but taking this candidate would have
required establishing that source mixing costs nothing once the floor is applied consistently,
and that is false. The mock feedback loop is independent of the floor:
`test_a_traffic_row_at_the_floor_still_reaches_the_mock` shows an observation at the floor
outranking the specification, which is the mock builder working as designed, and a `replay` row at
the floor would do the same thing while being Sync's own synthesis. No amount of fixing the floor
closes that, because the row clears the floor honestly. The candidate also leaves `mock_response`
unanswered, which the brief required be said rather than dropped.

## Whether the filter reaches the mock builder

**It does, and it is now established at the mock builder itself rather than inferred.**

`src/sync/verify/mock_response.py` is pure — it takes `observed` as an argument and opens no
connection — so it is not the reader. The reader is `_observed` at `src/sync/remediate/nodes.py:461`,
and it calls `observed_shapes(site.vendor_id, site.operation_id)` positionally with no keyword, so
it takes the default. The chain is `make_replay` → `_observed` (`nodes.py:412`) →
`replay_from_specification` → `synthesize_mock_response` (`replay.py:278`).

The first form of this answer was an inference: W116's
`test_a_replay_row_at_the_floor_outranks_the_specification_in_the_next_mock` asserted that a
`replay` row reaches that reader, and against this change it failed with `assert [] == ['replay']`.
A test failing is evidence that something changed; it is not by itself evidence about which
production call path changed, and the three links above were read off the source.

The direct form is `test_the_baseline_a_replay_run_hands_the_mock_builder_carries_traffic_alone`.
It puts one `error-payload` row and one `replay` row in the table, both at the sample floor, runs a
real `make_replay` against the `handles` fixture, and **records what `synthesize_mock_response`
actually receives** through a spy bound on the module `replay.py` imports it from. The recorded
baseline is `('error-payload',)`. With the default flipped to `traffic_only=False` — mutation `M3`
— the same recording is `('replay', 'error-payload')`, which is W116's defect reproduced at the
mock builder rather than at a reader standing in for it. That is the measurement, in both
directions, in the production call path.

It names the traffic row as well as the absent replay row for the reason the two tests beside it
do: an assertion on the absence alone would also have held if the baseline arrived empty, which is
how this change could have closed the feedback loop by breaking the mock.

Two narrower tests remain either side of it — a `replay` row at the floor yields an empty baseline
from `_observed` and a mock built from the specification, an `error-payload` row at the floor
yields a baseline of one and a mock built from observation. They import `_observed` rather than
reconstruct it, so they fail if that node starts reading the table some other way; the new test is
what fails if `make_replay` stops using that node at all. `mock_response.py` was not edited, and
did not need to be.

## Whether the sibling window is also wrong for traffic sources — the second finding

**It is, and it is a separate and larger defect than the one this task fixed.** Reported here
rather than folded in, and not fixed.

Measured rather than argued: `test_a_traffic_row_under_the_floor_still_escalates` writes an
`error-payload` row at the floor and an `interceptor` row at `sample_count=1`, with no synthetic
row anywhere in the database, and the divergence is still graded `breaking` with "the vendor's
behaviour changed" in its rationale. The traffic filter is in place while that runs. So the
escalation is not a consequence of source mixing and this task's change does not touch it.

`MIN_SAMPLES` gates the row a finding is *raised* on. It does not gate the sibling rows that
decide that finding's *severity*: `_contradicts_earlier_window` reads every sibling whatever its
count. So a single `sample_count=1` row of any source — one upstream incident, one misbehaving
account, which is the module docstring's own justification for the floor existing — is enough to
promote a divergence from `info` to `breaking`, on a rationale telling the reviewer the vendor's
behaviour changed. The module says a shape seen fewer than `MIN_SAMPLES` times "is not a
baseline", and then reads exactly such a row as "the baseline's own history".

Filtering by source does not touch this and was never going to. The escalation needs one row, and
one `interceptor` row is as good as one `replay` row.
`test_a_traffic_row_under_the_floor_still_escalates` pins it with two traffic sources and no
synthetic row anywhere in the database.

Three things make it bigger than a one-line fix:

- The behaviour is already pinned deliberately, in a test written by an earlier task:
  `test_a_single_earlier_observation_is_enough_to_grade_a_divergence_breaking` at
  `tests/test_detector_declines.py:359`, whose docstring says the asymmetry is visible in the suite
  rather than only in a report. Mutation `M7` — the sibling window given the floor — kills that
  test. Fixing the defect therefore requires retiring a pin somebody wrote on purpose, with the
  argument.
- It changes the severity of findings against live `error-payload` baselines, which is a change to
  what reaches a reviewer first, in the detector least able to afford a precision loss. That needs
  its own measurement against a real baseline, not a unit test.
- The right fix is not obviously "apply `MIN_SAMPLES` to siblings". A sibling's job is to establish
  that the field *used to* behave differently, and the sample size that makes that credible is not
  necessarily the sample size that makes a divergence worth reporting. `M7` is the cheapest fix,
  not the argued one.

## What happens to rows already in the table

Nothing, and that is a property of the answer taken rather than a claim about a migration. No
column was added and no DDL changed except a comment, so `apply_schema` has nothing to backfill
and no pre-existing row needs a value. `CLAUDE.md`'s `unattributed` precedent does not come into
play, because there is no column for history to be absent from.

Asserted against a database that holds rows rather than inferred from the DDL:
`test_rows_written_before_the_filter_existed_survive_a_second_apply_schema` writes an
`error-payload` row at `sample_count=7` and a `replay` row at `sample_count=5`, applies the schema
twice, and reads both back with their counts intact — then reads again with the default and gets
the `error-payload` row alone. The second `apply_schema` is what makes it an idempotency assertion
rather than a survival assertion.

The one change to `schema.sql` is the `source` column's comment, which now says what the values
mean and names `sync.graph.sources` as the list that must be extended alongside it.

## Whether W116's condition (1) is satisfied, and which of its pins are stale

**Condition (1) is satisfied.** Traffic and non-traffic sources are kept apart on read, at the
store, reaching both consumers. Condition (2) — a retried replay must converge — is untouched and
is now the whole of what stands between this project and reinstating the writer.

**The writer is not reinstated here, and reinstating it is the next task.** It needs (2) answered
first: `record_observed_shape` adds to `sample_count` on conflict, `route_after_replay` sends a
failed replay back to `patch`, and `MAX_STATIC_ATTEMPTS = 3`, so three attempts still write three
counts from one synthesized body. Either the row carries a run key so a retry updates rather than
adds, or the tier writes at a point the retry loop cannot re-enter. The first is a schema change to
`observed_shape` and needs a grain comment before it.

W116's six pins resolved three different ways, and the three ways are the finding:

| Pin | Resolution |
|---|---|
| `test_a_successful_replay_builds_shape_rows_and_writes_none_of_them` | kept, **read corrected** |
| `test_a_failed_replay_builds_shape_rows_and_writes_none_of_them` | kept, **read corrected** |
| `test_a_declined_replay_builds_no_shape_rows_and_writes_none` | kept, **read corrected** |
| `test_a_second_write_of_one_shape_converges_on_a_row_and_not_on_a_count` | kept, read corrected |
| `test_a_replay_row_at_the_floor_outranks_the_specification_in_the_next_mock` | **retired**, asserted as an absence |
| `test_one_replay_row_under_the_floor_turns_an_uncorroborated_divergence_breaking` | **retired**, asserted as an absence |

**The three that kept passing are the ones worth naming, because they are the ones that nearly
broke.** They assert the writer writes nothing, and they read the store to do it. With a
traffic-only default they would have kept passing through the writer being switched back on, since
every row it adds carries `source='replay'` — the default answer excludes exactly the rows those
tests exist to catch. That is W116's central pin going vacuous as a silent side effect of this
change, which is the failure the brief for this task warned about, arriving from the direction
nobody was watching: not from a pin that failed, but from three that did not.

Measured rather than reasoned. With the replay writer reinstated in `nodes.py`:

| read | result |
|---|---|
| `traffic_only=False` (as committed) | 2 failed, 1 passed |
| traffic-only (the default) | **3 passed** |

All three now read every source, through one `_writes_nothing` helper so there is a single place
to be right about it. Mutation `M1` — W116's candidate 1, the writer reinstated — is still killed.

`test_a_second_write_of_one_shape_converges_on_a_row_and_not_on_a_count` failed against this
change for an unrelated reason and was resolved unrelatedly. Its subject is the conflict clause,
which this change does not touch, and the rows it writes are `replay` rows; the traffic answer is
empty whether the second write merged, added, or was discarded, so it cannot tell those apart. It
was asking the store the wrong question, and now asks with `traffic_only=False`.

**The two retired pins described defects that no longer exist.** Neither was retired because it
became awkward, and neither property lost an assertion — both gained one. Each is now asserted as
an absence in `tests/test_observed_shape_sources.py`, beside a traffic counterpart that keeps the
absence from being vacuous: a `replay` row at the floor no longer reaches `_observed`, *and* an
`error-payload` row at the floor still does; a `replay` row under the floor no longer escalates,
*and* a traffic row under the floor still does. An absence asserted without its counterpart would
have passed just as well if the filter had emptied the baseline entirely, which is the way this
change could have "fixed" both defects while breaking the mock builder.

They were retired rather than inverted in place because `tests/test_replay_shape_writeback.py` is
named for the writer. An inverted copy there would put that name over a claim about the store's
reader, and would separate each absence from the counterpart that gives it meaning.

## Verification

All measurements against a real Postgres 16 on port 5433, `sync_w119` and `sync_w119_mut`, both
created by this task. Every mutation run used `-n0`. The full suite was run on both schedulers.

Mutation baseline: 86 passed, exit 0, `-n0`, over the six test files that can reach this change.

| Mutation | Verdict | Killed |
|---|---|---|
| M1 the replay writer reinstated (W116's candidate 1) | killed | `test_a_successful_replay_...`, `test_a_failed_replay_...`, `test_the_offered_shapes_are_carried_and_not_written` |
| M2 `observed_shapes` ignores `traffic_only` (the change reverted) | killed | 42 tests, including `test_a_reader_asking_for_traffic_does_not_receive_a_replay_row` |
| M3 the default flips to `traffic_only=False` | killed | `test_the_replay_nodes_own_baseline_reader_receives_no_replay_row`, `test_the_baseline_a_replay_run_hands_the_mock_builder_carries_traffic_alone`, `test_a_reader_asking_for_traffic_...`, `test_one_replay_row_no_longer_escalates_...`, `test_rows_written_before_the_filter_existed_...` |
| M4 the filter matches `SYNTHETIC_SOURCES` instead of `TRAFFIC_SOURCES` | killed | 34 tests, including `test_a_traffic_row_at_the_floor_still_reaches_the_mock` |
| M5 `TRAFFIC_SOURCES` loses `interceptor` | killed | `test_an_interceptor_row_is_traffic`, `test_every_declared_observation_source_is_classified`, `test_a_traffic_row_under_the_floor_still_escalates` |
| M6 `replay` classified as traffic (the partition broken) | killed | `test_no_source_is_both_traffic_and_synthetic`, `test_a_reader_asking_for_traffic_...`, `test_the_replay_nodes_own_baseline_reader_...`, and two more |
| M7 the sibling window applies the sample floor (the second finding, fixed) | killed | `test_a_traffic_row_under_the_floor_still_escalates`, `test_a_single_earlier_observation_is_enough_to_grade_a_divergence_breaking` |

No mutation survived and no false-verdict mode fired. The harness separates killed, survived,
did-not-compile (`compile()` before running), unreadable (exit ∉ {0,1}, and exit 1 with no
`FAILED` line), baseline-drifted (pass count off baseline), not-applied (anchor absent, and
ambiguous reported separately) and anchor-missed.

`M3` is the mutation that matters most and it is the one an inattentive harness would have
misread. It is a one-character change to a default, it compiles, and it leaves every store-side
test that passes `traffic_only` explicitly green. Only the tests that read through `_observed`
catch it — which is the same asymmetry that made the default the right answer.

**CRLF anchors.** All four mutated files are CRLF in the working tree. Every anchor is written LF
in the harness and rewritten to the file's own newline before matching, and a mismatch between the
two forms is reported as `anchor-missed` separately from `not-applied`, so a silent zero-hit
replace cannot be read as a survival. Without that step all seven mutations would have reported as
not-applied, and a harness that scored not-applied as survived would have reported seven survivals
over correct code.

`M1` edits `src/sync/remediate/nodes.py`, which this task must not change. `M7` edits
`src/sync/detect/observed_drift.py`, which this task may change and deliberately did not. Both
are restored byte-for-byte from bytes read before the edit, in a `finally`, and `git diff
--exit-code` over the tracked tree returned 0 after the run. The vacuity measurement above edits
`nodes.py` too, under the same restore, and also returned 0.

### The four gates

Run on the merged tree, `stroland02/m1-observed` on top of `9bc6fa5`.

| Gate | Result | Exit |
|---|---|---|
| `pytest -q` (`-n auto`, the `addopts` default) | 2753 passed, 2 skipped | 0 |
| `pytest -q -n0` | 2753 passed, 2 skipped, 1 deselected | 0 |
| `lint_encoding.py src scripts tests` | no output | 0 |
| `lint-imports` (unredirected, `PYTHONIOENCODING=utf-8`) | `Contracts: 1 kept, 0 broken` | 0 |
| `lint_dead_links.py src --baseline scripts/dead_links_baseline.txt` | no output | 0 |

`-n0` is the one that had not been run when the previous session ended, and it is a CI gate. It
takes 7 minutes against this suite where `-n auto` takes 2, which is the whole reason it is the
measurement that gets skipped.

Both skips are environmental and neither is this change: `test_oasdiff_determinism.py:159` wants
`SYNC_OASDIFF_DETERMINISM=1`, and `test_symbol_map_pin.py:128` wants a staged symbol map at
`.cache/specs/symbols.json`, which is gitignored and absent from this worktree. A tree that has
fetched one reads 2754 passed, 1 skipped, which is the same suite.
