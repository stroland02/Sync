# Sync — Pipeline Discipline

**Date:** 2026-07-27
**Status:** Binding on schema and stage design. The short form lives in `CLAUDE.md`; this is
the argument behind it.
**Scope:** The data-engineering practice Sync's pipeline is held to, and — as importantly —
the practice it is deliberately not held to.

## Why this document exists

Sync is a data pipeline that happens to emit pull requests. It reads vendor artifacts,
derives rows, joins them against a static index, and produces an action. Every failure mode
that afflicts a data pipeline is available to it: duplicated rows on a re-run, a table whose
grain nobody declared, history overwritten in place, a dropped record that turns out to have
been the interesting one.

The remedies are old and well understood. They are worth writing down once, in terms of this
codebase, so that no session re-derives them and no session skips them because it did not
think of the pipeline as a pipeline.

Two of the principles below already have a shipped bug attached. That is the argument for
the rest.

## The nine stages

Named here so the rules can bind to something specific.

| | Stage | Produces |
|---|---|---|
| 1 | INDEX | `CallSite` rows, from tree-sitter over customer source |
| 2 | RESOLVE | Raised binding confidence, from the TS compiler and the SDK symbol map |
| 3 | OBSERVE | Raised binding confidence again, from telemetry |
| 4 | SIGNAL | `VendorChange` rows, from `VendorAdapter.fetch_changes()` |
| 5 | DETECT | `Finding` rows, from the join of 1–3 against 4 |
| 6 | LOCATE | The exact lines to edit |
| 7 | PATCH | An edit, from a codemod or an agent |
| 8 | VERIFY | `tsc`, then the customer's own CI |
| 9 | PR | A pull request carrying its evidence |

## The rules that bind

### 1. Declare a table's grain before adding a column

One row of `migration_outcome` is one **attempt**, not one finding — `attempt_index` is in the
schema, so the grain is already per-attempt. Any query that counts findings by counting rows
is wrong, and will be wrong quietly.

One row of `observed_shape` is one `(vendor_id, operation_id, field_path, json_type, source)`
tuple. That is why `sample_count` is a column: a thousand observations of the same shape are
one row with a counter, not a thousand rows.

Write the grain into the schema file as a comment above the table. It costs one line and it
is the cheapest available defence against a table that answers a different question than the
one being asked of it.

*Source: Kimball, "The Data Warehouse Toolkit" — declaring the grain is step two of the
four-step dimensional design process, before dimensions and before facts.*

### 2. Every stage is idempotent

Re-running INDEX, SIGNAL, or DETECT on the same input converges on the same rows. It never
duplicates them.

This is not a hypothetical. `efcc19d fix: include line and col in call_site identity to stop
same-file collisions` is exactly this bug: an identity that was not unique, so re-derivation
collided instead of converging.

**One stage does not satisfy this today, and it is a named exemption rather than an oversight.**
SIGNAL does not converge for oasdiff-derived `vendor_change` rows. `oasdiff breaking` returns a
different answer on every invocation over the same hash-verified bytes — measured on both 1.26.0
and the 1.26.1 CI pins — and the difference reaches the rows rather than stopping at a count,
because `upsert_vendor_change` hashes `raw["text"]` and that is where oasdiff writes the recursive
property path. Two runs of one version shared 23,674 rows out of 58,906 and 193,934.
`2026-07-29-oasdiff-determinism.md` has the evidence.

The exemption covers oasdiff-derived changes and nothing else. **INDEX and DETECT are not
implicated, and neither is the rest of SIGNAL** — the deprecation and MCP sources are ordinary
derivations and the rule binds them exactly as written. A future stage that fails to converge is
still a defect; this one is a documented consequence of a third-party binary we pin.

What retires it: `2026-07-29-oasdiff-convergence.md` measured the curve over 24 runs. Operation-
level coverage converges — 1,174 rows on the first run, unchanged across the 23 that followed,
with the nesting property holding on every one. The natural-key union does not: 2,135,168 rows
after 24 runs and still growing. So a union over repeated runs recovers the *coverage* and cannot
by itself make the *rows* converge, and the fix is that union combined with a natural key that
does not carry the free-text message. Both halves are needed; either alone leaves this rule
violated. Until they land, treat oasdiff-derived `vendor_change` as an at-least-once producer and
do not read a row count from it as a measurement.

Concretely: every table gets a natural key and an explicit conflict clause. The pipeline is a
set of derived views over vendor artifacts and customer source, and a derived view that
cannot be recomputed to the same result is not a view — it is an accumulating log wearing a
table's name.

*Source: Kleppmann, "Designing Data-Intensive Applications", Ch. 11 — deriving state from an
immutable log, and why exactly-once semantics is usually idempotence plus a key.*

### 3. Vendor operations are a slowly changing dimension

The ADG's entire value is answering "what did this look like before the change." That is the
question a Type 2 slowly changing dimension exists to answer: a new row per version, with
validity bounds, so history is addressable.

Overwriting in place — Type 1 — would destroy the only thing that makes the corpus a corpus.
A `migration_outcome` row that points at a spec version which has since been mutated in place
is unlabelled data.

*Source: Kimball, SCD Types 1, 2, and 3.*

### 4. Lineage is a column, not a derivation

The three-rung ladder — `static`, then `resolved`, then `observed` — already is provenance.
Make it explicit and carry it forward: every downstream artifact, `Finding` through `Patch`
through the PR body, records the rung its binding came from.

The payoff is diagnostic. When a false positive surfaces, the question "which rung produced
this?" has an answer in the row rather than in an investigation. Precision is the committed
position, and precision that cannot be attributed cannot be improved.

*Source: Reis & Housley, "Fundamentals of Data Engineering" — data management as an
undercurrent running beneath every lifecycle stage, not a stage of its own.*

### 5. A non-backfillable dataset is written early and widened later

`migration_outcome` and `observed_shape` both record observations that cannot be
reconstructed after the fact. Nobody can go back and see what a vendor sent last month, or
whether a patch attempt that was never recorded would have merged.

The discipline that follows is asymmetric, and worth stating plainly because the instinct
runs the other way: **start writing before the schema is finished.** A nullable column added
in month three costs one migration. A month of unrecorded outcomes costs a month, and no
amount of later engineering recovers it.

### 6. Dead-letter, never drop

The remediation graph's `abandon` node captures `abandon_reason`. That is a dead-letter
queue, and it must be queryable rather than terminal.

Abandoned attempts are the highest-information rows in the corpus: they are where routing
learns which change kinds are not mechanically safe, and they are exactly what an unexamined
pipeline discards as noise. A pipeline that keeps only its successes has thrown away its
training signal.

*Source: Kleppmann — dead-letter queues as the alternative to silent discard.*

### 7. Contract-test the input at the boundary

The public change feed is Ed25519-signed. A signature proves **origin, not correctness**.

A validly signed feed carrying a malformed `VendorChange` must fail at parse, loudly, before
any row is constructed from it. The feed spec already requires signature verification before
`_parse()`; this is the reason it also requires `_parse()` to be strict. Two different failure
modes, two different gates, and neither substitutes for the other.

More generally: validate at system boundaries — vendor responses, subprocess output, feed
payloads, customer source — and trust internal code. That is already the house style; this
names the boundary that is easiest to forget, because a signature feels like it settled the
question.

*Source: the data-contract practice common to Great Expectations, dbt tests, and Soda —
assertions at the ingest boundary, not downstream where the bad row has already spread.*

### 8. Separate extraction from transformation so a re-parse costs nothing

`VendorChange.raw` retains the original oasdiff record. Keep it that way.

The payoff already arrived: `b29795a fix: resolve the patch prompt's affected field from
oasdiff text, not the URL path` replaced a field-extraction rule. Because `raw` was retained,
that fix can be applied to history — the improved extractor re-derives from stored records
rather than re-fetching every spec pair. Had the pipeline stored only its interpretation, the
old rows would be permanently wrong.

### 9. Training-serving skew

The moment routing is learned from `migration_outcome` rather than hand-written, the features
used to route in production must be computed by the **same function** as the features used to
fit. Not an equivalent implementation — the same one.

Two implementations that agree today diverge on the first edge case, and the failure is
silent: the model scores well offline and routes badly online.

*Source: Huyen, "Designing Machine Learning Systems" — training-serving skew.*

## What deliberately does not apply

Naming these prevents a future session from importing machinery the system has no use for.

**Watermarks, windowing, and event-time/processing-time reconciliation.** Streaming Systems'
central apparatus addresses unbounded, out-of-order, high-volume ingest. Sync processes
vendor artifacts in discrete, pinned version pairs — a batch of two documents, on demand.
There is no lateness to reason about.

**Exactly-once stream delivery.** The distributed-transaction machinery is unnecessary when
idempotence plus a natural key gets the same guarantee (rule 2) against a workload measured in
documents per day.

**A feature store.** It solves multi-model feature reuse across teams. There is one model
consumer, one team, and no reuse problem to solve.

**An OTLP ingest endpoint, and the streaming machinery under one.** Competing on ingestion
infrastructure against Datadog was refused on strategic grounds in
`2026-07-25-sync-competitive-position.md`, and joining against the graph was not. What was built
sits on the joining side of that line: `sync.telemetry.otlp` decodes an OTLP/JSON export payload
and `sync.telemetry.ingest` folds the client spans into `observed_call`. Both are library
functions over a decoded payload — no port, no server, no collector protocol — and
`ingest.py` says so in its own docstring. So Sync reads OTLP and still owns no high-volume
ingest path, which is why most of the streaming canon stays out. Note that `observed_call`'s
`spans` map is idempotence by natural key under rule 2, not exactly-once delivery.

## Verification

These are properties a test can hold, not aspirations.

- **Idempotence is asserted per stage**: run INDEX twice against the same fixture repository,
  assert the row count and every row identity are unchanged. Same for SIGNAL against a fixed
  spec pair, and DETECT against a fixed graph.
- **Every table's grain appears as a comment in `schema.sql`.** A grep-level check is enough;
  the point is that the declaration exists before the columns do.
- **`raw` survives a round trip**: store a `VendorChange`, read it back, assert the original
  oasdiff record is byte-identical.
- **A malformed but validly signed feed payload is rejected**, and the rejection happens
  before any `VendorChange` is constructed.
- **`abandon_reason` is never null on an abandoned run.** An abandoned run with no reason is a
  dropped record with extra steps.
