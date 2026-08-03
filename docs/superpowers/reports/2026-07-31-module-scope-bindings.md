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
nothing here has measured, and it belongs to its own task. §10.

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
B33 made, and it is listed in §10 rather than fixed here.

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

## 8. Every test was proven able to fail

All fourteen tests pin behaviour that already existed, so "watch it fail first" can only mean
proving each one fails against a mutation of the code it covers. Ten mutations, run through
`tools/mutate_scope.py`, gitignored. Scheduler `-n0`, baseline 14 passed:

| Mutation | Where | Change | Verdict | Tests killed |
|---|---|---|---|---:|
| `py-fallback` | `python_lang.py:628` | `return root` → `return node` | killed | 6 |
| `ts-fallback` | `typescript.py:495` | `return root` → `return node` | killed | 5 |
| `py-scope-widened` | `python_lang._response_fields` | `_walk(scope)` → `_walk(root)` | killed | 2 |
| `ts-scope-widened` | `typescript._response_fields` | `_walk(scope)` → `_walk(root)` | killed | 2 |
| `py-scope-narrowed` | `python_lang._response_fields` | `_walk(scope)` → `_walk(call_node)` | killed | 6 |
| `ts-scope-narrowed` | `typescript._response_fields` | `_walk(scope)` → `_walk(call_node)` | killed | 5 |
| `py-line` | `python_lang.index` | `start_point[0] + 1` → `+ 2` | killed | 1 |
| `ts-line` | `typescript.index` | `start_point[0] + 1` → `+ 2` | killed | 1 |
| `py-args` | `python_lang._argument_keys` | `return sorted(keys)` → `return []` | killed | 1 |
| `ts-args` | `typescript._argument_keys` | `return sorted(self._object_paths(...))` → `return []` | killed | 1 |

**Every one of the fourteen is killed by at least one mutation**, and the last four rows exist for
that reason alone. The two tests asserting the call site's identity and the two asserting its
argument keys read nothing the scope can reach, so no mutation that moves the scope touches them —
they are exactly the pins that would have kept passing through the defect, and the line and
argument mutations are what shows they are not vacuous.

The two `fallback` rows are the ones that matter for the coverage claim: mutating `return root`
alone changes the module-scope results in both languages and leaves the function-scope results
untouched, which is what makes §4's argument a measurement rather than a reading of the code.

**No false-verdict mode fired.** The harness separates killed, survived, did-not-compile
(`compile()` before the run), unreadable (exit outside `{0, 1}`, or exit 1 with no `FAILED` line),
not-applied (anchor absent or ambiguous) and baseline-drifted (unmutated pass count off 14); all
ten came back killed with the anchor matching exactly once.

**CRLF was live, not theoretical.** Both modules are CRLF in the working tree — measured, not
assumed. Anchors are written LF in the harness and rewritten to the file's own newline before
matching. Without that step all ten would have matched nothing; the anchor-count check reports that
as `not-applied` rather than as a survival, which is the distinction that keeps a harness fault
from reading as a result.

`-p no:xdist` is not usable here: this repository's `addopts` carries `-n auto`, and disabling the
plugin leaves `-n` unrecognised, so pytest exits 4 with no `FAILED` line at all. Every measurement
in this report used `-n0`.

## 9. The remaining statements, one at a time

Thirty-five statements were uncovered across the two modules before this task and thirty-three are
after it — thirty declines and three capability statements. This is the map for them, not a plan to
close them; the brief asked for the pair and the table, not for all thirty-five.

**Three are capability rather than decline**, and the baseline named all three. They are listed
apart because a decline table's question — "is refusing right?" — does not apply to a statement
that produces an answer.

| Statement | What it produces | Why nothing reaches it |
|---|---|---|
| `python_lang.py:319-320` | `decline_reason` rendering "…declare N requirements between them and 'stripe' is not one of them" | Every fixture that declines does so with an empty or unreadable manifest, which returns one line earlier. No fixture declares requirements that do not include the vendor. |
| `python_lang.py:867` | `_configured_typechecker` answering `"mypy"` | A repository configuring mypy through `mypy.ini`, `.mypy.ini` or `setup.cfg` rather than `[tool.mypy]` in `pyproject.toml`. `static_verify` already fails closed either way, so this changes the diagnostic and not the verdict. |

### `python_lang.py` — 21 declines

| # | Statement | Input that reaches it | Is declining right? | What the caller observes |
|---|---|---|---|---|
| 1 | `128` `_same` → `False` | a binding form whose target or value field is absent from the node | Yes. `_same` asks whether the name receives *this* call, and an absent field is not this call. | The result reads as unbound: `response_fields_read` empty. |
| 2 | `340` `_sdk_version` → `"unknown"` | a repository that imports the SDK but declares it in no manifest | Yes. The manifest is the only source, and inventing a version writes a number the project never did. | `sdk_version="unknown"` on every call site from that repository. |
| 3 | `450` `_client_identifiers` → `continue` | intended: the `module_name` child of `from stripe import X`, among the statement's named children. **Nothing reaches it.** | **Unreachable as written** — see below. | Nothing today. The module name lands in `imported` alongside the symbol. |
| 4 | `492` `_constructs_client` → `False` | a `call` node with no `function` field | Yes, and it cannot fire on a well-formed tree. | The name is not bound as a client; its call sites are not indexed. |
| 5 | `498` `_constructs_client` → `False` | a callee that is neither an identifier nor an attribute — `client = make()(...)`, `client = (Stripe)(...)` | Yes. Neither spelling names something imported from the vendor, and following either needs the type inference tree-sitter does not give us. | Not bound; call sites absent. |
| 6 | `516` `_bound_name` → `None` | an assignment target that is neither a name nor an attribute: `a, b = StripeClient(...), 1`, `table["k"] = StripeClient(...)` | Yes. Neither names a root a call chain can be spelled against. | Not bound; call sites absent. |
| 7 | `520` `_bound_name` → `None` | an attribute target whose object is not a plain identifier: `self.a.client = StripeClient(...)` | Yes, for the reason the docstring gives one line down — a deeper root is an object this walk cannot follow to its construction. | Not bound; call sites absent. |
| 8 | `522` `_bound_name` → `None` | an attribute target on anything but `self`: `config.client = StripeClient(...)` | Yes, and this is the case the docstring argues explicitly. Matching any attribute would bind on the attribute name alone and claim every unrelated `client.x.y()` in the repository. | Not bound; call sites absent. |
| 9 | `550` `_attribute_chain` → `None` | an `attribute` node with no `attribute` field | Yes; cannot fire on a well-formed tree. | The call is skipped at `index:752`. |
| 10 | `554` `_attribute_chain` → `None` | an `attribute` node with no `object` field | Yes; same. | Skipped at `index:752`. |
| 11 | `556` `_attribute_chain` → `None` | a chain whose root is not an identifier: `get_client().charges.create(...)`, `clients["a"].charges.create(...)` | Yes. The root is a value this walk cannot resolve to a client, and guessing binds a vendor to code that may not call it. | Skipped at `index:752`; the call is not indexed. |
| 12 | `577` `_dictionary_paths` → `continue` | a dict literal child that is not a `pair`: `{**defaults, "amount": 1}` | Yes. A spread names no key statically. | The spread contributes no `args_keys`; its siblings do. |
| 13 | `580` `_dictionary_paths` → `continue` | a computed key: `{key_name: 1}` | Yes, and the docstring says why — recording the expression would put customer source into a column that holds field names. | That key is absent from `args_keys`. |
| 14 | `598` `_argument_keys` → `[]` | a `call` node with no `arguments` field | Yes; cannot fire on a well-formed tree. | `args_keys` empty. |
| 15 | `605` `_argument_keys` → `continue` | a `keyword_argument` with no `name` field | Yes; same. | That argument contributes no key. |
| 16 | `645` `_read_path` → `None` | an `attribute` node with no `attribute` field | Yes; same. | That read contributes no response field. |
| 17 | `657` `_read_path` → `None` | an attribute or subscript whose object/value field is absent | Yes; same. | That read contributes no response field. |
| 18 | `700` `_result_target` → `None` | **Nothing.** The walk climbs only through `_RESULT_WRAPPERS`, and the `module` node is met before `parent` can become `None` — `module` is not a wrapper, so the check at line 697 returns at 698 first. | **Unreachable, structurally.** | — |
| 19 | `752` `index` → `continue` | a call whose function is an `attribute` that `_attribute_chain` refuses — rows 9, 10 and 11 arriving at the loop | Yes. Scoped to the one call. | The call is not indexed. |
| 20 | `842` `_syntax_errors` `except ValueError` | a source file CPython rejects before the tokenizer: a UTF-16 `.py`, whose null bytes raise `ValueError` rather than `SyntaxError` | Yes, and it is not defensive — the comment records that the uncaught form took `matches` down twice against exactly this file. | — |
| 21 | `848` the same handler's `broken.append` | as row 20 | Yes. The file is reported as unparseable, which is what it is. | `static_verify` returns `ok=False` naming the path. |

### `typescript.py` — 9 declines

| # | Statement | Input that reaches it | Is declining right? | What the caller observes |
|---|---|---|---|---|
| 1 | `96` `_same` → `False` | a binding form whose `name`/`value` or `left`/`right` field is absent | Yes; same argument as `python_lang:128`. | The result reads as unbound. |
| 2 | `235` `_read_manifest` → not-an-object | a `package.json` that is valid JSON but not an object: `[]`, `"text"`, `null` | Yes. `data.get` would raise on all three, and the two-channel return is what keeps "declares nothing" apart from "could not be read". | `decline_reason` says the manifest could not be read, rather than that the vendor is absent from it. |
| 3 | `409` `_member_chain` → `None` | a `member_expression` with no `property` field | Yes; cannot fire on a well-formed tree. | The call is skipped at `index:591`. |
| 4 | `413` `_member_chain` → `None` | a `member_expression` with no `object` field | Yes; same. | Skipped at `index:591`. |
| 5 | `438` `_object_paths` → `continue` | a `pair` with no `key` field | Yes; same. | That key is absent from `args_keys`. |
| 6 | `455` `_argument_keys` → `[]` | a call passing no arguments at all: `stripe.charges.list()` | Yes. There is no request-side field to record. | `args_keys` empty; the call site is still indexed. |
| 7 | `476` `_destructured_fields` → `continue` | a `pair_pattern` with no `key` field | Yes; cannot fire on a well-formed tree. | That field is absent from `response_fields_read`. |
| 8 | `528` `_result_target` → `None` | **Nothing**, for the same structural reason as `python_lang:700`: the `program` node is not a wrapper, so the check at line 525 returns at 526 before `parent` can become `None`. | **Unreachable, structurally.** | — |
| 9 | `558` `_response_fields` → `[]` | a binding target that is neither an object pattern nor an identifier — an array pattern, `const [charge] = await stripe.charges.list(...)` | Yes. An array pattern binds by position and names no vendor field, which is the same argument `python_lang._response_fields` makes about tuple unpacking. | `response_fields_read` empty; the call site is still indexed. |

### The two `_result_target` tails are unreachable, and that is a proof rather than a search

`python_lang.py:700` and `typescript.py:528` are the same statement in the same shape as the pair
this task closed, and they are the one kind of uncovered statement no fixture can reach. The walk
leaves its loop only when `parent` becomes `None`, `parent` is reassigned to `parent.parent`, and
the only node whose parent is `None` is the root — so the root's own type would have to be a result
wrapper for the loop to reach its tail. It is not: measured, the roots are `module` and `program`,
their parents are `None`, and neither type is in either `_RESULT_WRAPPERS`. The loop always returns
at the wrapper check first.

Closing them means deleting them, not writing a fixture. That is worth saying because the previous
decline reports on this project each found one or two statements of this kind, and a task that sets
out to close a coverage number rather than to read it will spend a long time trying to reach these
two.

### Row 3 is the one the coverage number was hiding something behind

`python_lang.py:450` is not uncovered because the input is exotic. It is uncovered because
**the comparison cannot be true**:

```python
module = node.child_by_field_name("module_name")
for child in node.named_children:
    if child is module:
        continue
```

py-tree-sitter hands back a fresh Python object per access, so `child is module` is `False` even
for the node it names. Measured on `from stripe import StripeClient`: the `stripe` child compares
`is` → `False` and `==` → `True`; the `StripeClient` child compares `False` to both. This module
already knows the rule and states it in `_same`'s docstring — *"tree-sitter returns a fresh object
per access, so identity is the span rather than the reference"* — and this is the one place that
does not follow it.

What it costs today is nothing observable. The module name lands in `imported` beside the symbol,
so `from stripe import StripeClient` leaves `imported == {"stripe", "StripeClient"}`, and the only
way to turn that into a wrong binding is `client = stripe(...)` — calling a module, which raises
in any Python that runs. So the guard is inert rather than harmful.

**It is not fixed here, deliberately.** Repairing it to `_same(child, module)` makes line 450
reachable and changes what `imported` holds, which is a behaviour change no test demands; the brief
allows a production edit only where a test proves a defect, and the defect this one would prevent
requires code that cannot execute. It belongs with the other binding-form work in §10, where a
fixture can be written for the change rather than for the guard.

## 10. What the next task is

Four findings this task established and deliberately did not act on.

**The scope walk is not shadow-aware, at any scope.** §3 and §4. `_response_fields` in both
adapters walks a scope's whole subtree, so any nested scope that rebinds the result name donates
its reads to the call — at module scope, at class-body scope, and inside a function with a nested
function. `merged` shows it absorbing another *indexed* call's field, which is a false response
field on a real call site and therefore a false finding with a `static` rung.

It is a bigger change than it looks, and it should not be taken as obviously correct. Skipping
nested function bodies would lose the genuine case — a module-level result read from inside a
function, through the global it is — which turns a false field into a missed break. Neither
direction has been measured on real repositories, and the choice needs that measurement rather than
a preference. Both adapters must move together; the fixtures for it are already committed.

**`_result_target` does not recognise a TypeScript class field.** §6. `static charge =
stripe.charges.create(...)` is indexed and binds nothing on the response side, because
`public_field_definition` is neither of the two forms the walk knows. This is the same shape as
the `assignment_expression` gap B33 closed, one binding form further on, and it is a missed break
rather than a false finding. It belongs to `_result_target` and not to the scope walk.

**`python_lang.py:450` compares tree-sitter nodes with `is`.** §9, row 3. The guard is inert and
the module's own `_same` states the rule it breaks. Harmless today, and the repair changes what
`imported` holds, so it needs a task that can write a fixture for the change rather than for the
guard.

**Both `_enclosing_scope` docstrings understate their input set.** §6. They describe the fallback
as answering for a module-level call; a class body reaches it too, and gets the module rather than
the class. That is a documentation fix, and it should be made by whoever takes the first item,
because the sentence to write depends on what the walk ends up doing.
