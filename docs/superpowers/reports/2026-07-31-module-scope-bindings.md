# A call bound at module scope, in both indexers

**Date:** 2026-07-31
**Scope:** M3-W120 — `python_lang.py:628` and `typescript.py:495`, the two `_enclosing_scope`
fallbacks that `docs/superpowers/specs/2026-07-30-sync-coverage-baseline-3.md` ranks highest by
cost, plus the decline table for the remaining statements in both modules.
**Outcome:** both adapters handle a module-scope call correctly and identically. **No production
code changed.** The statements were unexercised, not wrong. What the fixture did find is a
precision leak that the fallback is not the cause of, recorded below as the next task.

## 1. What each adapter does with a module-scope call

Five fixture files per language under `tests/fixtures/py/module_scope` and
`tests/fixtures/ts/module_scope`, written to the same shape so the two can be compared on the
same program. Indexed with the Stripe adapter over a two-operation symbol map; the figures are
the `CallSite` rows themselves.

| Fixture | Python `response_fields_read` | TypeScript `response_fields_read` |
|---|---|---|
| `script` — module-scope call, module-scope reads | `['id', 'status']` | `['id', 'status']` |
| `shadowed` — plus a function rebinding the name | `['status', 'total']` | `['status', 'total']` |
| `merged` — plus a second indexed call in a function, same name | create: `['amount_refunded', 'status']`<br>retrieve: `['amount_refunded']` | create: `['amount_refunded', 'status']`<br>retrieve: `['amount_refunded']` |
| `nested_function` — the rebinding one level *inside* a function | `['status', 'total']` | `['status', 'total']` |
| `class_body` — a call in a class body | `['status']` | no matched source; see §6 |

Of the three outcomes the brief separated, it is the good one: **the binding is produced, and
produced correctly.** `script` is the ordinary customer script the baseline described — a call at
the top of a file and a field read off the result — and both adapters index it, resolve
`stripe.charges.create` to `PostCharges`, record `['amount', 'currency']` on the request side and
`['id', 'status']` on the response side. Neither produces no binding, and neither produces one
whose scope is wrong in a way that changes the fields.

## 2. The two languages agree

Compared on `(fixture, symbol, response_fields_read)` across the four matched fixtures, Python and
TypeScript are identical — `test_the_two_languages_agree_on_every_module_scope_call`. The
agreement extends further than the assertion: `content_hash` matches across languages for
`script`, `shadowed` and `merged`'s module-scope call, because that hash is
`symbol|args|response_fields` and all three agree.

Two differences are not disagreements and are deliberately outside the assertion. `col` is a byte
offset into differently-indented source. And `merged`'s TypeScript `retrieve` records no argument
keys where Python records `['id']`, because the TypeScript request side reads an object literal
and the fixture passes a positional string — the documented rule in `_argument_keys`, not a scope
matter.

This is the finding the baseline said comparing adapters could not produce, and it is worth
stating that the comparison came out clean. A symmetric defect would have been invisible to
anyone diffing the two fixture directories; there was no defect, and only running the fixture
could have established that either.

## 3. What `root` as the scope costs

`_response_fields` walks the whole subtree of the scope it is handed. At module scope that subtree
contains every function in the file, so a function that rebinds the same name donates its reads to
the module-scope call.

`shadowed` shows the cheap version: `total` is read off a function-local `charge` holding no
vendor response at all, and it is credited to the Stripe call. `merged` shows the expensive one —
the module-scope `create` absorbs `amount_refunded`, which is read off *another indexed call's*
result. That is the merge both docstrings say must not happen:

> two unrelated calls sharing a generic result name in different functions must not merge into one
> dependency set

and it runs one way only. The function-scope `retrieve` collects nothing of the module's, because
the module is not inside the function. A detector reading the first row would report it against a
change to a field that call site never touches — a false finding, which
`2026-07-26-sync-review-integration.md` costs above a missed one.

## 4. The fallback is not the cause

`nested_function` is the control, and it is why nothing in `src/` changed.

It moves the rebinding one level down: the indexed call sits inside `outer`, so `_enclosing_scope`
finds `outer` in `_FUNCTION_TYPES` and returns it on line 626/493. **The fallback never runs**, and
the fields recorded are `['status', 'total']` — the same leak, in both languages, to the same
values as the module-scope case.

That places the fault in `_response_fields`, which walks a scope's subtree without asking which
nested scope rebinds the name. It is not in `_enclosing_scope`. Module scope is only the widest
instance of a leak that exists at every scope that can contain another.

And `return root` is the only answer available to the question `_enclosing_scope` is asked. The
enclosing scope of a module-level statement *is* the module; there is no smaller node, and §1
proves the answer is usable. The brief's instruction — "if the fallback is wrong, say what it
should return" — has no answer, because the fallback is not wrong.

Fixing the leak means teaching `_response_fields` which reads a nested rebinding shadows. That is a
different change to a different method, it trades a false field for a missed one in a direction
nothing here has measured, and it belongs to its own task. §8.

## 5. The rung survives, and does so without depending on the scope

`CallSite` carries no rung field. The rung is stamped by the detectors that read the static index
— `detect/vendor_change.py:162`, `detect/parameter_deprecation.py:108`,
`detect/observed_drift.py:234` and `:277` all write `binding_rung="static"` — and the comment at
the first of them says why it is keyed on the source rather than on the row:

> The rung names the binding whose wrongness would make this finding wrong. This detector reads
> only the static index, so a wrong static binding is the only thing that could make the claim
> wrong.

A module-scope binding is a static binding, so it carries `static` exactly as a function-scope one
does, and `GraphStore.insert_finding`'s refusal of `unattributed` is never in question. Nothing on
the scope path can reach the rung. That is the right answer for the leak in §3 too: a false field
on a module-scope call produces a finding attributed to `static`, which is where a reviewer should
look for it.

## 6. The fallback answers for more inputs than its docstrings name

A class body is not a function, so a call in one has no ancestor in `_FUNCTION_TYPES` either and
reaches the same statement. `class_body.py` measures it: the call is indexed and its scope is the
**module**, not the class. In a file holding several classes that is the widest read this walk
performs, and neither docstring mentions it — the TypeScript one says "for a module-level call",
which understates the input set.

There is no TypeScript counterpart fixture, and the reason is the languages rather than the
adapters. Python reads a class attribute inside the class body by its bare name; TypeScript reads
a class field through `this.` or through the class name, neither of which `_member_chain` can root
a chain at. Measured, a TypeScript class-field call is indexed and records **no** response fields —
but it is declined one step earlier, at `_result_target`, which does not recognise a
`public_field_definition` and returns `None` before the scope walk is reached. That is a real gap
and a separate one; it belongs to `_result_target`, alongside the `assignment_expression` widening
B33 made, and it is listed in §8 rather than fixed here.

## 7. The response-side path is reachable at module scope

Yes, by both routes.

The plain-identifier route is §1's measurement. The TypeScript destructuring route does not depend
on the scope at all: `_response_fields` returns `sorted(self._destructured_fields(name_node,
source))` before `_enclosing_scope` is ever called, so `const { id, status } = await
stripe.charges.create(...)` at module scope takes a scope-free path and records what the pattern
names. Both committed destructuring fixtures (`ts/destructured`, `ts/nested_destructured`) wrap
their call in a function, so that spelling at module scope is also unexercised — but it is
unexercised in a way that cannot differ, because the statement it would run is the same one and it
reads no scope. Python has no analogue; `_response_fields`' docstring says why (tuple unpacking is
positional and names no vendor field).

No fixture in this task produced a request-side binding without a response-side one.
