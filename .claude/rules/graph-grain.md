---
paths:
  - "src/sync/graph/**"
  - "**/*.sql"
---

# Graph and schema rules

You are editing the store. These apply on top of the pipeline rules in `CLAUDE.md`.

## Declare the grain first

Every table carries a comment above it stating what one row is. Write it before the columns.

```sql
-- Grain: one row per call site, per indexed revision.
create table call_site (...)
```

A table without a declared grain is a table whose queries will eventually count the wrong
thing. `migration_outcome` is per *attempt* — `attempt_index` is a column, so a finding with
three attempts is three rows. `observed_shape` is per
`(vendor_id, operation_id, field_path, json_type, source)` tuple, which is why `sample_count`
is a counter column rather than a row multiplier.

## Natural key and conflict clause, always

Re-running a stage must converge, not accumulate. Every table needs a unique constraint over
its natural key and every write needs an explicit `on conflict` clause. There is no such thing
here as a table you only ever insert into.

`efcc19d fix: include line and col in call_site identity to stop same-file collisions` is this
rule being learned the expensive way: an identity that was not actually unique, so
re-derivation collided instead of converging.

## A scan clears the tables it names, and a foreign key can widen that behind your back

`GraphStore.truncate_signal_and_detect` empties `vendor_change` and `finding` — the two tables a
scan rebuilds from scratch — and issues no `CASCADE`. So a new table is safe from a scan by
default, and a new foreign key pointing at either of those two makes the scan's `TRUNCATE` fail
loudly rather than quietly widen.

**Adding `CASCADE` to make that error go away re-opens B129**, which emptied the migration corpus,
the repository context and three tables of telemetry on every run. Truncate the new table
alongside them if a scan genuinely rebuilds it, or do not point a foreign key at them.

## Vendor operations are Type 2, not Type 1

A spec version is history. Never update a vendor-derived row in place — write a new row with
validity bounds. The ADG's whole value is answering "what did this look like before the
change," and an in-place update makes every `migration_outcome` row pointing at that version
unlabelled data.

## Lineage travels

If a row's content depends on a binding, the row records which rung produced that binding:
`static`, `resolved`, or `observed`. Not a join away — a column.

`GraphStore.insert_finding` refuses a finding whose rung is `unattributed`, naming the detector
that raised it. The check sits at the write rather than on `Finding` itself, because `Finding` is
exported from `sync.core` and a required field there would break every third-party detector.

`unattributed` exists only for rows written before the column did — a fact about history, which
is why `BindingRung` does not contain it. Nothing new may be written with it.

## Never store what must not be stored

Shapes, not values. Field paths, JSON types, nullability, presence counts. An enum value only
when it appears in the vendor's *published* specification. Free-form values — amounts, names,
tokens, identifiers — are discarded at the observation boundary and never reach a column.
Identifying keys are salted-hashed. This is a threat-model commitment, not a preference.

## Verify

Idempotence is a test, not an intention: run the stage twice against one fixture, assert row
count and every row identity are unchanged.
