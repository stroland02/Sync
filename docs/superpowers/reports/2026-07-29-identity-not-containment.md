# Identity, not containment — and TypeScript had it too

**Date:** 2026-07-29
**Scope:** B46 — `mutate._result_binding` attached a response guard to a name that never held the
call's result.
**Outcome:** fixed in both languages, four corpus floors unmoved, no pair became unreachable.

## What was wrong

`_result_binding` climbed to an assignment whose value **contained** the call.
`python_lang._result_target` and `typescript._result_target` require the value to **be** the call.
The generator was the permissive one, so it manufactured a labelled positive no correct binder can
find:

```python
customers = list(client.customers.list().auto_paging_iter())
assert customers.has_more is not None      # what the generator wrote
```

`customers` is a list built from the pager. `customers.has_more` is an `AttributeError`, and
removing `has_more` from the response cannot break that code. The binder was right twice — right
to record no response field, right to emit no finding — so the repair belongs in the generator.
Left alone it would have forced `RECALL_FLOOR` from 1.0000 to 0.8889 to accommodate a mislabel,
which is the act `gate_corpus.py` exists to prevent.

## How identity is expressed

The way both binders express it: walk up from the call, and at the first binder require the value
field to be the node walked from. Anything between them that is not a transparent wrapper means
the name holds something computed from the result rather than the result.

```python
if not _same(parent.field(value_field), current):
    return None
```

`_same` compares spans, because ast-grep returns a fresh handle per access.

The wrapper sets are the languages' own — `await` and parentheses for Python; those plus
`non_null_expression`, `as_expression`, `satisfies_expression` and `type_assertion` for
TypeScript. **They are duplicated here rather than imported.** `mutate.py` imports nothing from
`sync.index` and a test over its import closure enforces that, because a generator that consulted
the binder would be scoring the binder against its own opinion. The duplication is the price of
that rule, and it is the cheaper side of the trade.

## TypeScript had the same asymmetry

Checked rather than assumed, and it did — in the same function. The walk climbed to the statement
and took whatever declarator it held without ever asking what that declarator's value was, so

```typescript
const customers = Array.from(stripe.customers.list({ limit: 3 }));
```

bound the guard to the array. Both the declaration form and the assignment form were affected;
both have tests.

**What it means for the twelve existing pairs: nothing, and that was measured.** The corpus was
scored before and after the change:

| | before | after |
|---|---|---|
| pairs scored | 12 | 12 |
| call sites affected | 16 | 16 |
| binding precision | 1.0000 n=16 | 1.0000 n=16 |
| binding recall | 1.0000 n=16 | 1.0000 n=16 |
| falsifiable negatives | 4 | 4 |
| symbol map | `5f71dcd3bec1…` | `5f71dcd3bec1…` |

`Every floor cleared.` **No pair became unreachable.** No repository in the frozen corpus writes
the containment shape — which is the claim that made it safe to fix both languages in one commit,
and it is why it was measured rather than asserted.

## One thing seen and left alone

Partway through, `git status` in this worktree showed `benchmark/corpus/README.md` and
`benchmark/corpus/repositories.yaml` as modified. I did not touch either, and by the next command
they were clean again — the other worker's corpus pin landing through the shared repository. My
commit names its two paths explicitly and contains only `src/sync/benchmark/mutate.py` and
`tests/test_result_binding_identity.py`, verified with `git show --stat` afterwards.

The floors above were re-measured after the tree settled, so the numbers describe the corpus as it
now stands rather than as it was mid-write.
