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

## Vendor operations are Type 2, not Type 1

A spec version is history. Never update a vendor-derived row in place — write a new row with
validity bounds. The ADG's whole value is answering "what did this look like before the
change," and an in-place update makes every `migration_outcome` row pointing at that version
unlabelled data.

## Lineage travels

If a row's content depends on a binding, the row records which rung produced that binding:
`static`, `resolved`, or `observed`. Not a join away — a column.

## Never store what must not be stored

Shapes, not values. Field paths, JSON types, nullability, presence counts. An enum value only
when it appears in the vendor's *published* specification. Free-form values — amounts, names,
tokens, identifiers — are discarded at the observation boundary and never reach a column.
Identifying keys are salted-hashed. This is a threat-model commitment, not a preference.

## Verify

Idempotence is a test, not an intention: run the stage twice against one fixture, assert row
count and every row identity are unchanged.
