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

## The pinned repositories already carry what a false positive would need

The score docstring names the partial path match as the only route to a false positive. That needs
an *untargeted* call site on the changed operation whose recorded field list carries an **outer**
segment of a nested change's path. The generator can never create one, so it has to be in the
checkout already — and the question of whether any pinned repository has one is a question about
the five repositories rather than about `mutate.py`.

Asked directly, over all seventeen specifications: for every labelled negative the detector
reaches, whether any top-level property of that operation in the pinned `v2330` document that
itself carries properties is a segment the site's field list leads into.

| specification | negative | what it leads into |
|---|---|---|
| `furever-GetAccountsAccount-response` | `app/api/account_session/route.ts:23` | `capabilities`, `controller` |
| `furever-GetCharges-response` | `app/api/list_charges/route.ts:16` | `data` |
| `furever-PostPaymentIntents-request` | `app/api/setup_accounts/create_charges/route.ts:104` | `mandate_data`, `payment_method_types` |
| `turbo-PostPaymentIntents-request` | `src/routes/arnsPurchaseQuote.ts:223` | `payment_method_types` |
| `virtual-lab-GetProductsId-response` | `scripts/migrate_to_tax_billing.py:264` | `tax_code` |
| `fireship-server-PostPaymentIntents-request` | `src/payments.ts:8` | none |
| `turbo-PostPaymentIntents-response` | `src/routes/arnsPurchaseQuote.ts:223` | none |

**Five of the seven.** The sharpest is `furever`, whose held-back site records
`controller.losses.payments` and `controller.stripe_dashboard.type`: a change removing any leaf
under `controller` that this site does not itself read passes `generate_pair`'s
already-depends refusal — that check is on the leaf — and then `_leads_into` fires on the site
anyway, because it is anchored at the outermost segment and the change's path may skip. A finding
on a site the label calls unaffected is a false positive, and precision would have something to be
wrong about for the first time.

So the answer to "would a partial match arise in a pinned repository" is yes, and no repository has
to be fabricated to get one. The blocker is entirely on the generator side. That is the argument
for candidate 3 and it is why this report names it as the next task rather than as a dead end.

## Every assertion in the pinning test was proved able to fail

`tests/test_mutation_kind_coverage.py` pins behaviour that already worked, so "watch it fail
first" means mutating the code each test covers and watching the test go red. Seven mutants, one
per claim, applied to a copy of the tree and reverted afterwards. The harness distinguishes
*killed* from *survived*, *did-not-compile*, *unreadable* (exit outside `{0,1}`),
*baseline-drifted*, *not-applied* and *anchor-missed*, because each of those has produced a false
verdict on this project before.

| mutant | file | verdict | detail | aimed at |
|---|---|---|---|---|
| `request-branch-declines` | `mutate.py` | killed | 7 failed | every kind inverts / a request kind writes the field |
| `two-request-kinds-diverge` | `mutate.py` | killed | 4 failed | the two request kinds produce the same pair |
| `response-guard-inverted` | `mutate.py` | killed | 1 failed | a response kind reads the field off the result |
| `field-keeps-the-whole-path` | `mutate.py` | killed | 2 failed | a nested change is mutated as its leaf |
| `response-branch-declines` | `mutate.py` | killed | 2 failed | the response kind inverts |
| `rule-drops-the-request-kind` | `build_corpus_specs.py` | killed | 2 failed | the rule omits only duplicates |
| `specification-names-another-kind` | a committed `.yaml` | killed | 1 failed | every specification names a kind the rule proposes |

Baseline `exit=0 passed=12 failed=0` before, and the same after restore. Twelve tests collected,
twelve proved able to fail. No mutant produced any of the false-verdict modes: nothing failed to
compile, nothing exited outside `{0,1}`, no pass count drifted, and no anchor missed — which the
CRLF normalisation in the harness is there to prevent, since this tree is CRLF and an anchor
written with `\n` matches nothing and reads as a survival.

Scheduler: `-n0` (serial) for every pytest run in the harness, which is also what makes the
baseline `12 passed in 3.13s` rather than the 20.41s a `-n auto` run of the same file costs in
worker startup. The pipeline runs are `scripts`-level and single-process. Score DSN
`sync_w117_score`, graph DSN `sync_w117`, both created by this task.
