# Replay shapes do not reach the store, and should not yet

**Date:** 2026-07-30
**Task:** M3-W116
**Answer taken:** candidate 3 — neither write site, and the specification is corrected instead.

## The gap as found

`docs/superpowers/specs/2026-07-26-sync-observed-contract-drift.md` says of the replay tier:

> every replay run is also a shape-store writer (`source = 'replay'`), which is how the baseline
> begins accumulating before any customer installs anything

Half of that is built. `replay_shapes` (`src/sync/verify/replay.py:172`) builds the rows,
`make_replay` serialises them onto `RunState` (`src/sync/remediate/nodes.py:432`), and nothing in
`src/` calls `GraphStore.record_observed_shape` with them. The only two callers are the Sentry and
Datadog readers, both of which fold an export an operator hands in.

`make_replay(store)` already holds the store, so the writer is one call away. That is why this task
was about the decision and not about the call: the call is easy and it is wrong today.

## Why it is wrong, measured rather than argued

Every figure below was taken against a real Postgres 16 (`sync_w116` on port 5433), not read off
the DDL. `tests/test_replay_shape_writeback.py` holds each as an assertion.

### A replay row is not an observation

The document's own borrowed insight is that the baseline is "the responses the customer's code
actually received". A replay row is not one. Step 1 of the tier synthesizes the mock from the
**new specification** (`synthesize_mock_response`), so the body replay observes is one Sync
constructed. The row that comes out is the published specification restated through the customer's
code — filtered by what that code touched, but originating in the vendor's document rather than in
anything the vendor sent.

This is the same category error `src/sync/verify/replay.py` already refuses one level down. Its
`replay_shapes` docstring declines to retain enum members because "that argument needs the
published specification, this has only the body, and inventing provenance is what the column's own
comment forbids". Writing the row itself into a table two consumers read as traffic invents
provenance at the row level, having refused to invent it at the column level.

The transposition from Meticulous breaks precisely here. Meticulous's mocks come from recorded real
sessions; the recording is traffic. Sync's mock is a synthesis. The mechanism transposes, the
provenance does not.

### One replay row escalates a real finding to `breaking`

This is the decisive one, and it is not a matter of degree.

`ObservedDriftDetector` groups sibling shapes by `field_path` **across sources**
(`observed_drift.py:160`), and `_contradicts_earlier_window` (`:291`) applies **no sample floor** to
the siblings — the floor at `:170` gates the shape being reported, not the rows it is compared
against. So a single `sample_count=1` replay row with an earlier `first_seen` and a different
`json_type` flips a genuine divergence from `info` to `breaking`.

Measured, with a real `error-payload` row at the floor disagreeing with the specification:

| store contents | severity |
|---|---|
| traffic alone | `info` |
| traffic + one `sample_count=1` replay row | `breaking` |

The rationale the second produces reads:

> The same field was seen arriving differently before this shape appeared, so the vendor's
> behaviour changed rather than the specification having always been wrong. This rests on observed
> traffic, not on anything the vendor published.

Both sentences are false in that state. The earlier row was synthesized from what the vendor
published. The finding asserts the exact opposite of its own provenance, at the severity that
reaches a reviewer first, in the detector the specification itself calls the one most able to
violate precision-over-recall.

**This is why no narrower version of candidate 1 exists.** Writing only on `passed`, or only above
some count, does not help: the harm needs exactly one row and the floor does not gate siblings.

### A replay row at the floor outranks the specification in the next mock

`_observed` (`nodes.py:461`) reads the baseline with `observed_shapes`, which has no `source`
filter — confirmed against the server: writing one `replay` row and one `error-payload` row for the
same field returns both. `_decide` in `mock_response.py` then prefers any observation at or above
`MIN_SAMPLES` over the specification, and picks the dominant row by `sample_count`.

Measured: against a schema declaring `status` a string, the mock is `<sync-mock /status>` from the
specification alone, and `0` once a `source='replay'` row at `sample_count=30` claiming `number` is
in the store.

So replay rows would be fed back into the mock that the next replay is verified against. Worse,
`dominant = max(..., key=sample_count)`: a replay row's count grows once per run without bound,
while an `error-payload` row's grows only as fast as the vendor actually errors. Sync's synthesis
would eventually outrank real traffic.

### The counter is not idempotent under the retry loop

`record_observed_shape`'s conflict clause is `sample_count = observed_shape.sample_count +
EXCLUDED.sample_count`. Measured over three identical writes: **1 row, `sample_count` 1 → 2 → 3.**
The row converges; the counter does not.

That is deliberate and correct for traffic — the docstring is right that `DO NOTHING` would freeze
every count at one. It is wrong for replay, because `route_after_replay` sends a failed replay back
to `patch` and `MAX_STATIC_ATTEMPTS = 3`. One finding retried to exhaustion would count one
synthesized body three times, from one underlying fact.

`CLAUDE.md`'s "every stage is idempotent" is satisfied in rows and broken in meaning. The named
exemption is oasdiff-derived `vendor_change`, and it does not extend here.

## The questions the brief posed, answered

**Does a failed replay write?** No, and this is a decision rather than a fallout of the others. The
case for writing is real: a failed replay did consume a body, and the body is a fact about the
specification while the failure is a fact about the patch. It loses to the retry loop above — a
failed replay is exactly the outcome that re-enters `patch`, so it is the one outcome where writing
multiplies. Both the success and failure cases are pinned, and the failure test is named so a reader
sees it was decided.

**Does `CLAUDE.md`'s "abandoned runs are data" argue for writing on failure?** No, and it should not
be cited as cover. That rule is about `abandon_reason` staying queryable so routing can learn which
change kinds are not mechanically safe. Its subject is the migration corpus, whose grain is one row
per *attempt* — which is why counting attempts there is correct. `observed_shape`'s grain is one row
per shape with a counter, and a counter over attempts measures how often Sync ran, not what the
vendor sent. The rule argues for keeping the replay outcome queryable, which `replay_outcome`,
`replay_reason` and `diagnostics` already do. It does not argue for putting synthesized rows in a
traffic table.

**Node or caller?** Neither, so the question is moot for this change — but the answer that would
have been taken is the node. `make_replay` already holds the store and already reads it in the same
node (`_observed`), so the node is not store-free today and a write would add no new dependency. A
caller draining `state["replay_shapes"]` costs more than it looks: it is a second place that has to
remember, `build_graph` has several terminal paths, and an abandoned run may never reach the drain —
which would make the store's contents a function of how a run ended rather than of what was
observed. That is the same silent-loss shape as an undeclared reducer.

**How many runs cross `MIN_SAMPLES`, and is that the intended reading?** One replay run of one
operation builds one row per distinct `(field_path, json_type)`, each at `sample_count=1` — measured
at 2 rows for the test fixture's response. Each run adds exactly 1. So **30 replay runs of the same
operation** cross the floor for a given field path, or as few as **10 findings** once
`MAX_STATIC_ATTEMPTS = 3` is spent.

That is not the intended reading. `MIN_SAMPLES` is justified by the rule of three over *30
independent samples*: "an outcome not seen in 30 independent samples has a 95% upper bound of about
3/30". Thirty replays are one synthesized body observed thirty times — one sample, repeated. The
number would be satisfied with none of the statistical content it was chosen for.

And the contrast the brief asked for is sharp: a hand-fed Sentry export of 30 error payloads really
is 30 distinct captured responses. **Replay rows would cross the floor in a way a hand-fed export
would not** — mechanically, cheaply, and without the vendor's involvement. That changes what the
detector fires on, from shapes traffic established to shapes Sync synthesized.

**What does `source='replay'` mean against the three-rung ladder?** It is not a rung and it is not
`observed`. The ladder — `static`, `resolved`, `observed` — attributes a *binding*: how a call site
was tied to an operation. `ObservedShape` carries no `binding_rung` and is not a binding; it is
evidence. `source` says which mechanism produced the evidence, which is a different axis. The
detector keeps these apart correctly, emitting `binding_rung="static"` with the comment "the binding
is static and the evidence is observed".

The trap is that the table is named `observed_shape` and its two existing sources are both real
traffic, so `source` has so far been a distinction *within* observation. `replay` is not: its
mechanism is synthesis from the specification. Filed beside `error-payload` and `interceptor` under
a reader with no `source` filter, it reads as observation to every consumer, and the ladder's own
rule — that a false positive which cannot be attributed to a rung cannot be fixed — is what the
`breaking` escalation above violates. Nothing in the row lets a reviewer discount it.

## What was rejected

**Candidate 1, write inside the replay node.** Smallest diff, and the write site would have been
right. Rejected because one row is enough to produce a false `breaking` finding, and no outcome
filter or count threshold available inside `nodes.py` prevents it. This is not hypothetical: the
mutation that implements candidate 1 is `M1` below, and it turns both pinning tests red.

**Candidate 2, drain `state["replay_shapes"]` in the caller.** Rejected for everything in candidate
1 — the rows are equally dangerous wherever they are written from — plus a second failure mode of
its own: a run that abandons may never reach the drain, so the store would record what finished
rather than what was observed.

**Candidate 3 was not taken because it is smaller.** It is taken because candidates 1 and 2 both
require a change in `src/sync/detect/` or `src/sync/graph/` to be safe, and both are forbidden to
this task. `CLAUDE.md`'s brief is explicit that discovering this is the result, not an obstacle to
work around.

## What has to change before replay can write

Neither is in this task's files. Both are stated here as the argument for the next one.

1. **`observed_shape` needs traffic and non-traffic sources kept apart on read.** The cheapest
   correct form is a `source` filter on `GraphStore.observed_shapes`, so a caller says which sources
   it wants: `ObservedDriftDetector` wants traffic only, and `mock_response` wants traffic only, and
   both currently take everything. A detector-side filter would fix the escalation but leave the
   mock feedback loop; a store-side filter fixes both. This is a decision about what the table means
   and belongs with its owner. `src/sync/graph/store.py`, and `src/sync/detect/observed_drift.py` if
   the sibling window is fixed there instead.
2. **A retried replay must converge.** With (1) in place the escalation is gone, but three attempts
   still write three counts from one body. Either replay rows carry a run key so a retry updates
   rather than adds, or the tier writes once per run at a point the retry loop cannot re-enter.
   The first is a schema change to `observed_shape`.

Until (1) lands, the tier not writing is correct rather than incomplete, and
`tests/test_replay_shape_writeback.py` holds it there.

## Verification

Six tests, all against a real database, all `-n0`. Characterization tests are green by
construction, so non-vacuity is shown by mutation rather than by a red-then-green cycle — and `M1`
is candidate 1 itself, which makes it the genuine failing-first evidence for the central pin.

| Mutation | Verdict | Killed |
|---|---|---|
| M1 write the shapes in the replay node (candidate 1) | killed | `test_a_successful_replay_...`, `test_a_failed_replay_...` |
| M2 conflict clause stops counting | killed | `test_a_second_write_of_one_shape_converges_...` |
| M3 the node's baseline reader drops replay rows | killed | `test_a_replay_row_at_the_floor_outranks_...` |
| M4 the sibling window becomes source-aware | killed | `test_one_replay_row_under_the_floor_turns_..._breaking` |
| M5 the missing-plan guard stops firing | killed | `test_a_declined_replay_builds_no_shape_rows_...` |

No mutation survived and no false-verdict mode fired. The harness distinguishes killed,
did-not-compile (`compile()` before running), unreadable (exit ∉ {0,1}), baseline-drifted (pass
count off baseline), not-applied (anchor absent or ambiguous) and anchor-missed separately. The last
was a live risk rather than a theoretical one: all three mutation targets are CRLF in the working
tree, so the LF-written anchors are rewritten to the file's own newline before matching, and a
harness that skipped that step would have reported five not-applied mutations as survivals.

M2 and M4 edit files this task must not change. They are applied and restored byte-for-byte in a
`finally`, and `git diff --exit-code` over the tracked tree confirmed the restore.
