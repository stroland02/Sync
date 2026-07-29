# The corpus gains a Python repository and refuses to certify a single pair over it

**Date:** 2026-07-29
**Scope:** B44 — pin `openbraininstitute/virtual-lab-api` and give Python its first binding
measurement.
**Outcome:** the repository is pinned and indexed; both pairs the selection rule produces label a
dependency the repository does not have, so neither was written. Python binding precision and
recall remain **null over n=0**. All four floors are unmoved, and the corpus score is byte-identical
to the last recording.

## What was confirmed before anything was added

B42 found the repository and measured it against the binder as it stood that morning. The binder
has changed since — B34, B35, B38 and B39 all landed — so the bar was re-checked rather than
assumed.

| | B42 | now |
|---|---|---|
| licence | Apache-2.0 | Apache-2.0 |
| `matches` | yes | yes |
| indexed call sites | 21 | 21 |
| operations | 12 | 12 |

Three operations carry three call sites each — `GetCustomers`, `GetProductsId`,
`GetSubscriptions` — which is what B42 read as enough for the hold-back rule to fire. It is not,
and the reason is the first thing this task learned.

## The selection rule reaches past everything Python could have measured

The rule takes the two operations with the most indexed call sites **where at least one call
passes an object argument**. Applied here:

| operation | sites | passes an object argument | reads a response field |
|---|---:|---|---|
| `GetCustomers` | 3 | yes (`params={…}`) | no |
| `GetSubscriptions` | 3 | yes (`params={…}`) | no |
| `GetProductsId` | 3 | **no** — `products.retrieve(product_id)` | **yes** (`id`, `name`, `tax_code`) |
| `PostCustomers` | 1 | yes (`email`, `metadata`, `name`) | no |
| `PostProductsId` | 2 | yes | no |

`GetProductsId` is the only operation in the repository whose call sites read response fields, and
the object-argument clause excludes it. `PostCustomers` is the only site passing request fields the
way a POST body is written, and the two-per-repository cap excludes it. What survives is
`GetCustomers` and `GetSubscriptions`: two GETs, so `request-property-removed` has no property to
name and is skipped exactly as `furever/GetCharges` already is, leaving two response-side
specifications and nothing else.

That is worth stating plainly because it is not a Python fact. The rule was written against
repositories that pass an options object and read fields off the returned intent, and it selects
for that shape wherever it looks.

## Both surviving pairs label a dependency the repository does not have

Every one of the six call sites on those two operations is written the same way:

```python
customers = list(self.client.customers.list(params={"limit": 100}).auto_paging_iter())
```

The response mutation appends its guard to the statement binding the result, and produces:

```python
customers = list(self.client.customers.list(params={"limit": 100}).auto_paging_iter()); assert customers.has_more is not None
```

`customers` is a Python list built from the pager. `customers.has_more` is an `AttributeError`.
Removing `has_more` from the `GetCustomers` response cannot break that code, so the label
`affected=True` describes a dependency that is not there.

The generator and the indexer disagree, and the disagreement is one word:

```
mutate._result_binding      climbs to an assignment whose value CONTAINS the call
python_lang._result_target  requires the value to BE the call
```

Containment against identity. The generator is the more permissive of the two, so it writes a
dependency the binder is right to refuse to record — and right, in turn, to emit no finding
against. **The binder is right twice**, and the pair punishes it both times.

`_result_target` reaches a name through `await` and a parenthesised expression and stops at
anything else, because `charge = dict(client.charges.create(...))` binds `dict`'s return value and
not the response. That rule is correct and predates this task. `_result_binding` has no equivalent
of it.

## What the number would have been, and why it is not a measurement

Scored with both Python pairs present, fourteen specifications, deterministic:

```
  pairs scored          14          was 12
  binding precision     1.0000  n=16    unchanged
  binding recall        0.8889  n=18    was 1.0000  n=16
  call sites affected   18          was 16
```

Split by language, which is the split the pooled figure hides:

| | pairs | affected | findings | precision | recall |
|---|---:|---:|---:|---|---|
| TypeScript | 12 | 16 | 16 | 1.0000 n=16 | **1.0000 n=16** |
| Python | 2 | 2 | 0 | unmeasured n=0 | 0.0000 n=2 |

**TypeScript did not move.** Nothing regressed. The whole of the pooled fall is the two Python
positives, and both of them are mislabels — so 0.8889 is the number the corpus would have recorded
had the mislabel gone unnoticed, and not a measurement of anything.

Landing those pairs meant lowering `RECALL_FLOOR` from 1.0000 to 0.8889 to accommodate ground truth
that had been proved wrong. That is the precise act `gate_corpus.py` exists to make impossible, and
a floor lowered to fit a bad label is worse than no floor: every later score would be compared
against a number that certified a mislabel.

The pairs were dropped. They are not pairs dropped for convenience — they never described a
dependency, and a corpus scoring them would be measuring the generator's permissiveness rather than
the binder's accuracy.

## Python binding precision and recall

**Null over n=0, and null rather than zero.** `axes.py` reports a null for an axis with no samples
for exactly this reason, and unmeasured is the honest word: there is a Python repository in the
corpus, indexed, and no honest Python pair over it yet.

Reporting Python recall as 0.0000 would be worse than reporting nothing. It would read as a binder
that finds no Python break, when what happened is that the binder declined two invitations it was
right to decline.

## What landed, and the two floors that did not move

Pinned in `repositories.yaml` by commit, subpath and `tree_digest`:

```
virtual-lab      a2577bb15dd0  563 files  7426825dba1243e737187237782d32bb5ff419a4b30dcf6fceeb0a385056921f  ok
```

The four floors, measured over the twelve frozen specifications after the pin:

```
  binding precision             1.0000    1.0000   n=16
  binding recall                1.0000    1.0000   n=16
  falsifiable negatives              4         4
  pairs scored                      12        12
  symbol map              5f71dcd3bec15f71dcd3bec1

Every floor cleared.
```

**No floor was restated, because no denominator moved.** The brief expected `gate_corpus.py` to
fail and it did not, for the same reason B42's did not: a repository was added and no pair was.

The symbol map pin held, as it had to — a Python repository does not change what the map resolves.
It digests to `5f71dcd3bec1302cf70cba56bc9ebf043b38a1727acb43cee9e20fa08ead6be7` over 272 symbols,
the pinned value.

The strongest single piece of evidence that the pin changed nothing: the score JSON taken after it
is **byte-identical** to `benchmark/corpus/recorded/2026-07-29-symbol-map-pinned.json`, digest
`e48ee05da861900f07c807c99f34d03c6d5bac821f5facf3e76d452348855d60`. No new recording was written
because there is no new number.

## Determinism

Scored twice from two freshly created databases, byte-identical in both the rendered text and the
JSON:

```
2e1b94d12e95662d36be53538d8f32bde74c7512ffe9cb8d25603906257662ea  .txt
e48ee05da861900f07c807c99f34d03c6d5bac821f5facf3e76d452348855d60  .json
```

The fourteen-pair run was checked the same way before the pairs were dropped, and was also
byte-identical across two databases. Python introduced no non-determinism, which is what the
precision floor's safety rests on.

## One change to the rule, and the frozen twelve prove it inert

`_read_fields` — the coarse scan that keeps the chosen field off a property the repository already
mentions — globbed `*.ts` only. Over a Python repository that reads nothing at all, which is an
absent guard rather than a loose one: it chose `data` for both specifications, a name
`virtual-lab` uses throughout, where the rule intends the first property the repository does *not*
use.

The scan now reads the repository's own language, from the adapter the indexer selected. Reading
both suffixes everywhere was the obvious alternative and is wrong: `furever` carries one `.py`
script mentioning `amount` fifteen times, and its frozen response specification is pinned on
`amount`. A Python repository added elsewhere in the manifest would have moved a TypeScript pair.

Regenerated with the change, the twelve committed specifications come back byte-identical except
for the drift below, and the Python field moves from `data` to `has_more`.

## Found on the way: the frozen twelve no longer match the generator

Re-running `build_corpus_specs.py` over the same pinned trees now writes a `hold_back` entry into
`furever-PostPaymentIntents-response-property-removed` and
`turbo-PostPaymentIntents-response-property-removed` that the committed files do not carry — six of
twelve rather than four.

No checkout moved. The binder did: B34 taught it to record fields off a result the call reaches
through a wrapper, so the first site on each of those operations now carries a non-empty
`response_fields_read` where it carried none, and the hold-back rule's third clause fires.

The twelve were left frozen. Regenerating them would move TypeScript's numbers in the same commit
that was measuring Python, and afterwards neither movement would be attributable — which is the
same reason this task did not touch the binder or the generator. It is a task of its own with its
own measurement, and it will move `falsifiable negatives` upward and `recall` downward by trading
positives for negatives, exactly as the last hold-back change did.

Until then, this directory's claim that the same specifications come out of the same pinned inputs
holds only against the same binder. The inputs the corpus pins are the checkouts and the symbol
map; the binder is not pinned and cannot be.

## What would unblock Python's first honest number, in the order it would pay

1. **`_result_binding` must require identity rather than containment**, matching `_result_target`.
   Then these two targets are recorded `unreachable` — correctly, as targets the mutation cannot
   honestly attach to — and the two pairs can be generated. They would contribute zero affected
   sites and no positives, so this alone gives Python a pair and still no measurement.
2. **A rule that can reach `GetProductsId`.** It is the only operation in this repository whose
   call sites read a response field, and the object-argument clause excludes it. That clause exists
   because neither mutation can attach to a call with no object argument — which was true when both
   mutations needed a literal, and is no longer true of the response mutation, which needs a bound
   result and not an argument. Relaxing it for the response kind is a change to the selection rule
   and belongs in a commit that re-derives every specification and states what moved.
3. **A second Python repository**, if one exists whose calls both pass request fields and read
   response fields. None of the eight B42 re-searched does; `virtual-lab` was the only one that
   indexed at all.

Nothing here is a Python-specific defect. Both the containment-against-identity gap and the
object-argument clause are in language-agnostic code, and Python is where they became visible —
which is the argument for a second language in the corpus, made by the corpus, on its first day of
holding one.
