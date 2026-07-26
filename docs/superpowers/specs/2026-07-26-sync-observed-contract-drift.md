# Sync — Observed Contract Drift

**Date:** 2026-07-26
**Status:** Specified. The shape store's format is binding now; the detector and replay tier land per Sequencing.
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
    field_path       text NOT NULL,      -- '/data/status', JSON-pointer form, matching path_ptr
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

`field_path` deliberately shares the JSON-pointer form of `vendor_change.path_ptr`, so an observed divergence
and a published change address the same field the same way — the join stays one join.

## The fourth detector

`ObservedDriftDetector` compares the shape baseline against two references and emits the same `Finding` type
as every other detector, into the same remediation pipeline. Nothing downstream changes.

Two comparisons, two distinct findings:

- **Observed versus specification** — the vendor's live behavior no longer matches what they publish. A field
  arriving null that the spec marks required; a type that changed; an enum value the spec does not name. This
  is the unpublished-change case, and no shipped competitor detects it before failure.
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

Every replay run is also a shape-store writer (`source = 'replay'`), which is how the baseline begins
accumulating before any customer installs anything.

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

| When | What |
|---|---|
| Now | This document. The `observed_shape` schema is binding on anything that later records shapes. |
| M1 (with the sandbox the threat model gates on) | The replay tier, feeding the shape store as `source='replay'`. |
| M2 (signal sources) | Error-payload shapes from Sentry-class sources, `source='error-payload'`. The detector ships here, running on whatever baseline exists, with the sample floor keeping it silent where data is thin. |
| Post-M2, opt-in | The interceptor SDK, only for customers who want unpublished-change detection on live traffic. A separate adoption decision with its own trust conversation. |

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
