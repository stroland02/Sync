# The Python binder stops crediting a call with somebody else's fields

**Date:** 2026-07-29
**Scope:** B34 — `python_lang._response_fields` walked to the nearest assignment without checking
the SDK call is what the name receives.
**Outcome:** two false attributions removed, six correct cases unchanged, nothing anywhere records
more than it did.

## The one line that was wrong, before and after

The reproduction the brief was written from, re-run against the fix:

```
charge = client.charges.create(amount=n)          ->  ['id', 'status']    unchanged, correct
charge = dict(client.charges.create(amount=n))    ->  []                  was ['id', 'status']
return client.charges.create(amount=n)            ->  []                  unchanged, correct
```

`dict(...)`'s return value is what `charge` receives, so the fields read off it were a claim that
the Stripe call's response carries `id` and `status` — a dependency the vendor need not have. A
false attribution turns a call site into a finding for a change it does not depend on, and
`2026-07-26-sync-review-integration.md` puts that above a missed finding in cost: a missed one
costs an incident, a false one costs the reviewer's willingness to read the next.

## Python's transparent wrappers, and what was rejected

**`await` and `parenthesized_expression`. Those two, and no others.**

Derived from the grammar rather than translated from TypeScript's. The node kinds below were read
off `tree_sitter_python` by parsing each form and walking from the call to its statement, because
the worker who found this defect verified Python's behaviour and said explicitly that it had not
verified the node names.

| form | path from the call | wrapper? |
|---|---|---|
| `charge = create(...)` | `call <- assignment` | — binds directly |
| `charge: C = create(...)` | `call <- assignment` | — **same node**, annotation is a field |
| `charge = await create(...)` | `call <- await <- assignment` | **yes** |
| `charge = (create(...))` | `call <- parenthesized_expression <- assignment` | **yes** |
| `charge = dict(create(...))` | `call <- argument_list <- call <- assignment` | no |
| `charge = create(...) or {}` | `call <- boolean_operator <- assignment` | no |
| `charge = create(...) if f else o` | `call <- conditional_expression <- assignment` | no |
| `charge = [create(...)]` | `call <- list <- assignment` | no |
| `charge += create(...)` | `call <- augmented_assignment` | no — different node kind |
| `return create(...)` | `call <- return_statement` | no |
| `(charge := create(...))` | `call <- named_expression <- …` | **rejected deliberately** |

Considered and rejected, each for its own reason rather than by omission:

- **`boolean_operator` and `conditional_expression`** each choose between two values and only one
  of them is the call's. `create(...) or {}` may bind the empty dict, and nothing static says
  which.
- **Collection literals** bind a container. `charge[0].id` reads a field of an element, and the
  path recorded would be the container's.
- **`argument_list`** means another call received the result; its return value is what the name
  gets. This is the defect itself.
- **`named_expression`** — the walrus — genuinely does bind the call's result, and is still left
  out. Recording it would make this walk report *more* than it did, and this is a precision task.
  It is a recall improvement with its own evidence to gather, not a side effect to take here.

**TypeScript's `as`, `satisfies`, non-null assertion and type assertion have no Python
equivalent**, which is why the set is smaller rather than differently chosen.

## Annotated and augmented, the two the brief singled out

Both were checked against the grammar first, and the answer to each was the opposite of what a
port from TypeScript would have produced.

**Annotated assignment needed nothing.** `charge: Charge = client.charges.create(...)` is an
`assignment` node with the annotation as a `type` field — not a separate kind. A walk keyed on a
narrower node would have lost it, which would have been a missed break introduced by a precision
fix. It worked before and works now, and there is a test so the next change cannot quietly drop
it.

**Augmented assignment needed no rule of its own.** `charge += ...` is an `augmented_assignment`,
a different kind, so it falls off the wrapper set and answers nothing — the same nothing it
answered before. Writing an explicit exclusion for it would have implied the walk could otherwise
reach it.

## Every form, before and after

| form | before | after |
|---|---|---|
| bare `charge = create(...)` | `['id', 'status']` | `['id', 'status']` |
| annotated `charge: dict = create(...)` | `['id', 'status']` | `['id', 'status']` |
| awaited `charge = await create(...)` | `['id', 'status']` | `['id', 'status']` |
| parenthesised `charge = (create(...))` | `['id', 'status']` | `['id', 'status']` |
| augmented `charge += create(...)` | `[]` | `[]` |
| returned `return create(...)` | `[]` | `[]` |
| **wrapped** `charge = dict(create(...))` | `['id', 'status']` | **`[]`** |
| **defaulted** `charge = create(...) or {}` | `['id', 'status']` | **`[]`** |

**No correct case records more than it did.** Six are byte-identical, two record strictly fewer,
and none records a field it did not before. The "before" column is not asserted from memory: the
eight tests were written first and run against the unmodified module, where exactly the two
false-attribution cases failed with the extra items in the diff and the other six passed.

The `or {}` case was not in the brief. It is the same defect through a different node and was
found by asking what else sits between a call and an assignment.

## No corpus number moved, and none could

All four repositories in the frozen corpus are TypeScript, so binding precision and recall cannot
see this defect and read identically either side of the change. Nothing under
`benchmark/corpus/` or `src/sync/benchmark/` was touched, and `git status` over both is clean.
The closing evidence is the fixture and the eight assertions, which is what the brief said it
would be.

## Boundaries

`src/sync/index/typescript.py`, `src/sync/benchmark/`, `benchmark/corpus/`, `src/sync/cli.py`,
`src/sync/graph/` and `src/sync/remediate/` are unmodified.
