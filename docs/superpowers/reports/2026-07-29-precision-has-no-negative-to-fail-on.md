# Precision has no negative to fail on, and the reason is one line in the harness

**Date:** 2026-07-29
**Scope:** B31 — give the frozen corpus a negative the binder could plausibly get wrong, so
binding precision stops being a constant.
**Outcome:** the diagnosis is confirmed and corrected; the negative could not be built inside
this task's boundary, and the reason is stated rather than worked around.

## The short version

Binding precision over the frozen corpus is 1.0000 at n=12 and it cannot be anything else. That
was suspected in `2026-07-29-frozen-corpus-first-binding-numbers.md` and is now measured: the
corpus holds **zero** labelled negatives the detector could have fired on, in every one of the ten
scored pairs.

The cause named in the brief — `generate_pair` refusing a tree where an untargeted call site
carries the changed dependency — is real code and is **not** what causes this. Neither is the
choice of repositories. The cause is `cli._score_corpus`, which targets every indexed call site on
the changed operation, and it cannot be repaired from `src/sync/benchmark/` or `benchmark/corpus/`.

## Which of the three explanations was true

The third: something else entirely. Two separate corrections, and the first invalidates the
evidence the task was dispatched on.

### The rung on a negative is not evidence about the indexer

The brief counts `rung` over the label set and reads `{'unresolved': 94}` as *the indexer bound
none of them*. The rung does not carry that.

`mutate.py:190` writes it as a literal:

```python
rung="static" if site.id in broken else "unresolved",
```

Every site the generator did not break gets the string `unresolved` regardless of what the
indexer did, and `BindingLabel.rung` defaults to the same value. `binding.py:222-225` then reads a
label's rung **only when the label is affected** — precision splits on the rung the *finding*
carries, never on the label's. So the negative set's rung column is a constant the scorer never
consults, and counting it establishes nothing in either direction.

What is true is the opposite of the reading. Every labelled site — negative included — is a call
site the indexer bound to an operation at `static`, because the sites reaching `generate_pair` come
from `adapter.index(repo)`, and `TypeScriptAdapter.index` yields no `CallSite` at all unless
`operation_for_symbol` resolved. A site the binder could not bind is not an unresolved negative in
this corpus; it is absent from it.

### The refusal exists, is narrower than described, and never fires here

`mutate.py:154-162` raises when any site in the tree already carries the changed *field*. It is
about the field, not the operation, so it does not exclude a same-operation site that does not
touch the field — the very case the task wants. And it never fires over this corpus, because
`build_corpus_specs.py` pre-empts it: the field it writes into a specification is *the
alphabetically first property of that operation that no call site in the repository already uses*.

So the refusal is not in the way. Removing it would change nothing.

### The cause is the targeting rule

`cli.py:1473`:

```python
targets = [site.id for site in sites if site.operation_id == change.operation_id]
```

Every indexed site on the changed operation is targeted. A same-operation site is therefore either
broken — and labelled affected — or a target the mutation could not attach to. There is no third
class, and that is exactly what the recorded run shows: for all ten scored pairs,

```
affected + unreachable == the number of indexed call sites on the changed operation
```

verified against the count each specification records in its own header comment. The two rows
where it does not hold are the two `displaced-label` exclusions, which scored nothing at all.

## Why the residue cannot serve either, and why this is not a corpus problem

Eleven of the ninety-four negatives are same-operation — the unreachable targets. They look like
candidates and are not, for a reason that is structural rather than incidental:

- a **request** mutation attaches where the call passes an object argument, which is exactly where
  the indexer records `args_keys`;
- a **response** mutation attaches where the result is bound in a `const`/`let` declarator, which
  is exactly where the indexer records `response_fields_read`.

The mutation attaches precisely where the indexer reads. **So a site the mutation cannot reach is a
site whose field list is empty, and `_deepest_match` over an empty list returns `None` for every
change there has ever been.** Those eleven decline before any property of the binder is consulted.

The consequence worth carrying: **adding repositories cannot fix this.** More repositories raise
the negative count and add no candidates, because every negative they contribute is either on
another operation — which `call_sites_for_operation` never returns — or an unreachable target with
nothing to match. This is a property of the harness, not of the sample.

## The numbers, recomputed

`benchmark/corpus/recorded/2026-07-29-falsifiable-negatives.{txt,json}`, byte-identical across two
runs from two freshly created databases:

```
sha256  c78177750c51a04f8171cd4f3b4860991f54e6c2a98056c0f3d57bb608aa3175
```

```
  pairs specified       12
  pairs scored          10
  binding precision     1.0000       n=12
  binding recall        1.0000       n=12
  call sites affected   12
  call sites unaffected 94
  unlabelled findings   0
  falsifiable negatives  0
```

Precision and recall are unchanged, which is the point: nothing about the corpus moved, and the
new column is the one that says the first of those two numbers could never have been anything
else.

The negative set, split the two ways that matter:

| | count | can it produce a false positive |
|---|---:|---|
| labelled negatives | 94 | |
| — on another operation | 83 | No. `call_sites_for_operation` never returns them, so no detector examines them. |
| — same operation, unreachable target | 11 | No. Field list empty, so the match declines for every change. |
| **falsifiable negatives** | **0** | — |

And the rung distribution the brief asked for, with the caveat that makes it readable:

```
affected   (n=12): {'static': 12}
unaffected (n=94): {'unresolved': 94}
```

Unchanged, and it means nothing. Every one of those 94 sites is a `static` binding the indexer
produced; `unresolved` is the literal `generate_pair` writes on a site it did not break, and the
scorer never reads it.

## What was built

**`falsifiable_negatives`** in `src/sync/benchmark/score.py` — the labelled negatives this change
gave the detector any chance of firing on. Two filters, each mirroring a place
`VendorChangeDetector.scan` declines before the binder is consulted: the site must be on the
changed operation, and it must carry a non-empty field list on the side the change is on. A kind
whose field cannot be placed degrades to an operation-match-only finding that fires on every
same-operation site, so there the field list is correctly not consulted.

It is carried on `ScoredPair`, pooled across the set by the corpus runner, and printed beside
precision. When it is zero the rendered report replaces the reader's inference with a statement:
the rate above is not a measurement, and a directional floor over it would gate a constant. When
it is non-zero that paragraph disappears — a caveat that prints unconditionally is a banner, and
the next reader learns to skip it.

Eight tests over the pure function and three over the aggregation and the rendering. All are pure:
labels, call sites and a change in, identities out. No database, no network.

## What was not built, and why

**The negative itself.** It requires holding a same-operation call site back from `targets`, and
`targets` is computed in `cli._score_corpus`, which this task was told not to edit.

`generate_pair` already supports it — the caller names its targets and the module deliberately
refuses to choose them. So the change is small and it is entirely in `cli.py`: derive the target
list from something the specification declares rather than from "every site on the operation", and
let the held-back sites fall through to the negative set as ordinary unaffected labels.

Two things the coordinator has to decide before that lands, neither of which was mine to settle:

- **It moves recall's denominator.** A site held back as a witness is a site not broken, so the
  twelve labelled affected call sites become fewer. Recall 1.0 at n=12 is currently the one real
  measurement on this benchmark, and trading part of it for a precision that can fail is a
  judgement about what the corpus is for.
- **It is a distribution choice, and `_score_corpus`'s docstring argues against making one
  silently** — "a harness that picked a subset would be choosing a distribution without saying
  so". Whatever rule holds sites back has to be declared in the specification file, the way the
  field choice already is, so the corpus keeps saying what it is a corpus of.

Building that selector here would have meant encoding a distribution decision I could not land or
exercise end to end. The measurement above is what makes the absence visible in the meantime, and
it is what a precision floor should itself be gated on: no floor while `falsifiable negatives` is
zero.

## Boundaries

`_result_binding` was **not** touched — the response-side gap is B29. It is named twice above
because the coupling between where the mutation attaches and where the indexer reads is the reason
the unreachable targets cannot serve as negatives, which is a fact about B31 and not a change to
B29's function.

Nothing under `src/sync/graph/`, `src/sync/remediate/` or `src/sync/cli.py` was modified.
