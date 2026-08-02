# The corpus scores one change kind, and adding the second would add rows without adding evidence

**Date:** 2026-07-30
**Task:** M3-W117
**Answer taken:** candidate 2 — `request-parameter-removed` inverts, and inverts to a pair the
corpus already holds. No corpus specification is added; the identity the omission rests on is
pinned by test instead.

## The gap as found

Seventeen frozen specifications sit in `benchmark/corpus/pairs/`, and the filenames all end
`-property-removed`. Read from `change.kind` rather than from the filename, which is the authority:

| kind | specifications |
|---|---:|
| `request-property-removed` | 5 |
| `response-property-removed` | 12 |
| `request-parameter-removed` | 0 |

`src/sync/benchmark/mutate.py:85` declares three:

```python
REQUEST_KINDS = frozenset({"request-property-removed", "request-parameter-removed"})
RESPONSE_KINDS = frozenset({"response-property-removed"})
```

So one declared kind has no specification behind it, and `SUPPORTED_KINDS` is a declaration that
nothing measured.

## Which kinds `generate_pair` can actually invert

Measured, one pair per kind, over one input every kind can mutate — a call passing an object
argument whose result is bound to a plain name. All three invert. None raises, none produces an
empty positive set, none produces a pair the scorer refuses.

| kind | tree changed | target labelled affected | unreachable | `depends_on_change` agrees |
|---|---|---|---|---|
| `request-property-removed` | yes | yes | none | yes |
| `request-parameter-removed` | yes | yes | none | yes |
| `response-property-removed` | yes | yes | none | yes |

`tests/test_mutation_kind_coverage.py::test_every_declared_kind_inverts_into_a_tree_the_audit_half_reads_back`
is that measurement, parametrised over `SUPPORTED_KINDS`, so a kind added to the set without an
inversion branch fails it rather than silently producing a pair with an empty positive set.

The answer to "what does `request-parameter-removed` do when you run it" is therefore not a
refusal. It produces a well-formed pair. It produces the *same* well-formed pair as
`request-property-removed`, which is the finding.

## The generator cannot express a nested change, and the corpus is flat because of that

`changed_path` keeps every segment of the property path; `changed_field` takes the last one, and
the mutation writes that leaf as a **top-level** key. Three changes at three depths therefore
produce one tree, byte for byte:

```
  token          'receipt_email'
  changed_path   ['receipt_email']
  mutated        "const c = await stripe.paymentIntents.create({ receipt_email: 'sync-benchmark', amount: 1, metadata: { note: 'a' } });\n"

  token          'metadata/receipt_email'
  changed_path   ['metadata', 'receipt_email']
  mutated        "const c = await stripe.paymentIntents.create({ receipt_email: 'sync-benchmark', amount: 1, metadata: { note: 'a' } });\n"

  token          'data/items/receipt_email'
  changed_path   ['data', 'items', 'receipt_email']
  mutated        "const c = await stripe.paymentIntents.create({ receipt_email: 'sync-benchmark', amount: 1, metadata: { note: 'a' } });\n"
```

The label still says affected in all three cases and `depends_on_change` still agrees, because both
read the leaf. Only the detector sees the difference: `_leads_into` anchors its match at the
outermost segment, the site passes `receipt_email` and the change is anchored at `metadata`, so it
correctly declines.

Run end to end through the pipeline that ships, against
`turbo-PostRefunds-request-property-removed` with nothing changed but the field:

```
  field='charge'             precision=1.0  n=1   recall=1.0  n=1   findings=1  affected=1
  field='metadata/charge'    precision=None n=0   recall=0.0  n=1   findings=0  affected=1
```

Recall 0.0 is a miss the corpus manufactured, not one the binder made. The tree does not carry the
break in the shape the change describes, because the generator discarded the shape. That is why no
committed specification names a nested field, and why expressing one is a generator change first —
candidate 3, and this is the measurement that says what it would cost.

Scheduler: `-n0` (serial) for the pytest runs above; the pipeline runs are `scripts`-level and
single-process. Score DSN `sync_w117_score`, graph DSN `sync_w117`, both created by this task.
