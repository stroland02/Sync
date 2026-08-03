# Sync — Observed Contract Drift

**Date:** 2026-07-26
**Status:** Partly built. The shape store (`observed_shape`, `src/sync/graph/schema.sql:124`),
two `error-payload` readers (`src/sync/signals/sentry/` and `src/sync/signals/datadog/`, which
writes the same `source` value deliberately) and the detector (`src/sync/detect/observed_drift.py`,
wired in `src/sync/cli.py:23`) all exist. Both readers now have a caller: `sync shapes`
(`src/sync/cli.py:974`) folds captured error-tracker exports into the baseline through
`_fold_sentry` (927) and `_fold_datadog` (950), so the store has a writer for the first time —
and it is fed by hand, not by a listener. The replay tier is built (`src/sync/verify/replay.py`
and `src/sync/verify/mock_response.py`, wired as the `replay` node in
`src/sync/remediate/graph.py:37`) and does not feed the shape store — deliberately, which
withdraws this document's claim below that every replay run is also a `source='replay'` writer.
A replay row is the published specification restated through the customer's code, not a response
the customer's code received. Two consumers used to read this table as traffic with no way to say
so, and both conditions that blocked the writer have since been answered:
`GraphStore.observed_shapes` returns traffic alone unless a caller asks for every source, and
`record_observed_shape` no longer accumulates `sample_count` for a synthetic source, so a replay
retried or repeated converges instead of counting one synthesized body once per attempt.
The writer is still not reinstated — that is its own task, and what it now owes is a consumer,
since no caller in `src/` reads a `replay` row.
`docs/superpowers/reports/2026-07-30-replay-shapes-reach-the-store.md` carries the measurements,
`docs/superpowers/reports/2026-07-31-traffic-and-non-traffic-shapes.md` closed the first
condition and `docs/superpowers/reports/2026-08-03-a-retried-replay-converges.md` the second.
The interceptor SDK does not exist — see Sequencing.
**Scope:** Detecting vendor changes no one published, and verifying patches against behavior rather than types
alone. The design transposes Meticulous's record-replay-diff mechanism into the API-consumption domain.

## The borrowed insight

Meticulous records real user sessions, replays them against every pull request with backend responses mocked
from the original recordings, and diffs the outcome. Its central property is not the recording; it is that
**the assertion is never authored — the assertion is the previous behavior.** Nobody writes the expectation.
Coverage is proportional to real usage rather than to developer diligence, and maintenance cost is zero because
the baseline updates itself.

Transposed to Sync's domain:

> The contract for a vendor API is not the vendor's specification. It is the responses the customer's code
> actually received.

A specification says what the vendor promised. Observed traffic says what the vendor did. When those diverge,
something changed that nobody announced — and Sync's entire category of competitor is blind to it, because
specification diffing sees only what vendors publish, and error-triggered tools see only what has already
broken.

## What is genuinely new here, stated honestly

An earlier framing of this idea claimed a cheap version: cross `response_fields_read` with the new vendor
specification. That is not a new detector. It is precisely the join the existing `VendorChangeDetector`
performs, already built at M0. This document does not count it twice.

The new capability is exactly one thing: **an observed baseline of response shapes per operation.** Everything
below — the detector, the replay tier, the coverage reframe — is a consumer of that baseline. Without it, none
of this exists; with it, all three follow cheaply. The baseline can be fed from three sources of ascending
cost and fidelity:

| Source | What it yields | Cost to customer |
|---|---|---|
| Sentry / error-tracker payloads (M2 signal sources) | Shapes at the moment something broke — partial, biased toward failures | None; already planned |
| Replay-tier observations (below) | Shapes exercised during Sync's own verification runs | None; Sync-internal |
| An HTTP-client interceptor shipped by Sync | Complete shapes on live traffic — the full Meticulous transposition | An SDK install. This is the expensive step, and it is deferred and opt-in |

The interceptor is the real product decision. Standard OTel client spans carry method, URL, status, and
duration — **not response bodies**. Full observation means Sync ships a wrapper the customer installs in their
runtime, which changes the install story from "point your telemetry at us" to "add our library." That is
deliberately last in the sequencing, adopted only for customers who want drift detection on unpublished
changes, and never required for the rest of the product to function.

## The shape store

Binding now, because observations cannot be backfilled — every response seen before the store exists is a
baseline sample permanently lost. Same argument, same urgency, as the migration corpus.

**Values are never recorded. Only shape.** The rule that keeps this inside the threat model's "nothing here
worth stealing" posture:

- Record field paths, JSON types, nullability, and presence rate.
- Record an enum value only when that value appears in the vendor's **published specification** — vendor enums
  (`"succeeded"`, `"requires_action"`) are public data. A string absent from the spec is never retained.
- Free-form values — amounts, names, tokens, identifiers — are discarded at the observation boundary and never
  cross a process line.

```sql
observed_shape(
    id               bigserial PRIMARY KEY,
    vendor_id        text NOT NULL,
    operation_id     text NOT NULL,
    field_path       text NOT NULL,      -- '/data/status', a JSON Pointer into the response body
    json_type        text NOT NULL,      -- 'string'|'number'|'boolean'|'object'|'array'|'null'
    nullable_seen    bool NOT NULL,
    spec_enum_values text[],             -- only values present in the published spec
    source           text NOT NULL,      -- 'error-payload'|'replay'|'interceptor'
    sample_count     int  NOT NULL,
    first_seen       timestamptz NOT NULL,
    last_seen        timestamptz NOT NULL,
    UNIQUE (vendor_id, operation_id, field_path, json_type, source)
)
```

### The join, corrected

An earlier version of this document claimed `field_path` "deliberately shares the JSON-pointer form of
`vendor_change.path_ptr`, so ... the join stays one join." **That was wrong, and wrong about shipped code.**
`sync/signals/oasdiff.py` sets `path_ptr` from oasdiff's `path` — the operation's **URL path**, `/v1/charges`.
It is not a pointer into a response body and never was. A join written against that premise matches nothing.

What the two sides actually hold:

| | Operation address | Field address |
|---|---|---|
| `vendor_change` | `operation_id`, plus `path_ptr` as the URL path | a **bare leaf name** — `status` — recovered from `raw` by `changed_field()` |
| `observed_shape` | `operation_id` | `field_path`, a full JSON Pointer — `/data/status` |

So the join is two predicates, not one:

1. `vendor_change.operation_id = observed_shape.operation_id`, which is exact.
2. The leaf segment of `observed_shape.field_path` equals `changed_field(change)`.

The second predicate is **not injective**, and the design says so rather than pretending otherwise: a response
carrying both `/data/status` and `/data/refund/status` matches a change naming `status` twice. When more than
one observed field matches, the detector emits one finding naming every candidate path and marks it ambiguous.
It does not guess. Guessing here produces a confident patch against the wrong field, which is the most
expensive false positive this system can produce.

`changed_field()` returning `None` is common and is not a defect — oasdiff records frequently name no field at
all. A change with no resolvable field still produces a finding at operation granularity and simply does not
participate in predicate 2.

**The cheap improvement, when it is worth doing:** retain oasdiff's full backticked token alongside the reduced
leaf name. That token is itself a schema path, so a later detector could compare more than one segment and cut
the ambiguity above. It is a SIGNAL-stage change, it is not required for the detector to ship, and it is
recorded here so the option is not rediscovered from scratch.

## The fourth detector

`ObservedDriftDetector` compares the shape baseline against two references and emits the same `Finding` type
as every other detector, into the same remediation pipeline. Nothing downstream changes.

Two comparisons, two distinct findings:

- **Observed versus specification** — the vendor's live behavior no longer matches what they publish. A field
  arriving null that the spec marks required; a type that changed; an enum value the spec does not name. This
  is the unpublished-change case, and no shipped competitor detects it before failure.

  **The third of those three cannot be built as this document states it, and is not.** The
  privacy rule above discards any observed value the published specification does not name, so
  `spec_enum_values` can only ever hold published members and an unpublished one leaves no trace
  behind to detect. The two requirements contradict each other; the privacy rule is a
  threat-model commitment and wins. `src/sync/detect/observed_drift.py` therefore detects type
  drift, nullability drift and undeclared fields, and says so in its own module docstring.
  Closing the gap needs a counter of observations whose value was discarded — a count, never a
  value — which is a change to the `observed_shape` schema and is not made.
- **Observed now versus observed before** — the baseline shifted between windows even where the spec is
  silent. Weaker signal, useful as severity enrichment rather than as a lone trigger.

Placement in the causal chain, which is the product argument: the vendor-change detector needs the vendor to
publish. The production-error detector needs a failure to have already happened. This detector needs neither —
it fires on shape divergence alone, before the first exception. It is the most literal expression of "adaptive
where the vendor publishes, reactive where nobody could have known" — it shrinks the second category.

**Safe-miss discipline holds.** A shape seen too few times is not a baseline; below a sample floor the detector
stays silent. False drift findings spend reviewer trust exactly the way false review comments do, and the
precision-over-recall position adopted in `2026-07-26-sync-review-integration.md` applies with full force.

## The replay verification tier

The gap it closes: the design's risk table already concedes that repositories without CI have no verification
path. The quieter problem is that a green CI run proves little when no test exercises the patched call. Most
customers have no test covering their Stripe integration; a passing suite that never runs the patched path is
weak evidence presented as strong.

The tier, transposing Meticulous's mock-first replay:

1. For each patched call site, synthesize a mock response from the **new** specification version — and from
   the observed baseline where one exists, which catches the case where reality and spec disagree.
2. Execute the patched call path against that mock in the credential-free sandbox the threat model already
   mandates. No network, no secrets, no vendor calls, no live side effects — replaying a real charge is not
   legally an option, so mock-first is forced here, not chosen.
3. Assert the patched code consumes the response without error, and that fields the code reads
   (`response_fields_read`) are satisfied by the mocked shape.

This sits between `tsc` and customer CI: stronger than typechecking (it exercises runtime behavior against the
new shape), cheaper and earlier than CI, and it produces evidence for the PR body that a reviewer can read —
"the patched path was executed against the new response shape and consumed it cleanly."

Every replay run produces the shape rows for it (`source = 'replay'`), which is how the baseline begins
accumulating before any customer installs anything. Produces, not yet writes: `replay_shapes` in
`src/sync/verify/replay.py:171` builds them, `make_replay` carries them out on `RunState` as
`replay_shapes`, and nothing calls `record_observed_shape` with them — so the run holds the rows and the
store does not get them.

**Boundary:** the replay tier verifies the *call path*, not the whole application. It executes customer code
only inside the sandbox the threat model requires for `tsc` already — this adds no new execution surface, only
new use of one that must exist anyway.

## Coverage, restated in the honest denominator

The M0 limits section reports mapping 105 of 414 Stripe paths, about 25%. The denominator is wrong for the
product Sync now is. A customer does not call 414 operations; they call perhaps a dozen, and traffic says
which dozen and at what volume.

**Coverage is reported as the share of observed call volume whose operations are bound**, not the share of
specification paths. This is both more honest — it measures what can actually break the customer — and
strictly better-looking, because binding effort concentrates on high-volume operations first. The spec-path
number remains in engineering docs; the volume number is the one a customer sees.

## Sequencing

| When | What | State |
|---|---|---|
| Now | This document. The `observed_shape` schema is binding on anything that later records shapes. | Built — `src/sync/graph/schema.sql:124`, `ObservedShape` in `src/sync/core/models.py` |
| M1 (with the sandbox the threat model gates on) | The replay tier. Feeding the shape store as `source='replay'` was specified here and is withdrawn. | Built as a verification stage, and deliberately not a feeder — `src/sync/verify/replay.py`, between `static_verify` and `push_branch` in `src/sync/remediate/graph.py`. Its `source='replay'` rows reach `RunState` and no further, pinned by `tests/test_replay_shape_writeback.py`. Both conditions the report of 2026-07-30 set are answered: traffic and synthetic rows are kept apart on read (2026-07-31), and a synthetic row's `sample_count` no longer accumulates, so a retried replay converges (2026-08-03). Reinstating the writer is still its own task, and it owes a consumer for these rows — both readers now answer traffic alone |
| M2 (signal sources) | Error-payload shapes from Sentry-class sources, `source='error-payload'`. The detector ships here, running on whatever baseline exists, with the sample floor keeping it silent where data is thin. | Built — `src/sync/signals/sentry/shapes.py`, `src/sync/signals/datadog/shapes.py`, and `src/sync/detect/observed_drift.py`, whose `MIN_SAMPLES` is the sample floor |
| Post-M2, opt-in | The interceptor SDK, only for customers who want unpublished-change detection on live traffic. A separate adoption decision with its own trust conversation. | Not built |

The baseline is empty until somebody feeds it. `record_observed_shape` still has no caller
outside the two readers, and the readers are now constructed — but only by `sync shapes`, which
reads an export an operator hands it. A deployment that never runs that command has an empty
baseline and a detector that correctly finds nothing, which is the sample floor doing its job
rather than a defect. `MIN_SAMPLES` is 30 (`src/sync/detect/observed_drift.py:66`), so one
export is unlikely to lift a shape over the floor on its own.

Both readers write `source='error-payload'`, which merges their rows rather than sitting them
side by side. That is the correct key — both samples are drawn from failures and neither corrects
the other's bias — and it has a consequence worth reading twice: `sample_count` clearing the
floor faster because two sources reported is not corroboration, and once merged a row cannot say
which source contributed.

Nothing here touches M0, the eight-task graph-surface plan, or the frozen tool schemas. The detector emits the
existing `Finding` type; the graph surface exposes its findings through the existing tools with no schema
change.

## Verification

- **Shape extraction is tested against committed fixture payloads** — including one containing PII-shaped
  values — asserting the stored rows contain types and paths only, and that no free-form value survives. The
  privacy rule is a test, not a comment.
- **The detector's true negatives are asserted**: a baseline matching the spec produces no finding; a baseline
  below the sample floor produces no finding regardless of divergence.
- **A synthetic unpublished change** — fixture spec says required string, fixture observations say nullable —
  must produce exactly one finding naming the field path.
- **The replay tier is proven able to fail**: a patch that mishandles the new shape must fail replay before
  the tier is trusted to pass anything.

## The one-line version

Competitors diff specifications or wait for exceptions. Sync additionally holds a baseline of what vendors
actually send, so it catches the change nobody announced — and verifies every patch against that reality, not
just against the types.
