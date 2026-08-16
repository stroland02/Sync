# A response binding absorbs fields read off a different call with the same name

**Date:** 2026-08-03
**Scope:** M3-W123 — `_response_fields` in `src/sync/index/python_lang.py` and
`src/sync/index/typescript.py`, the read walk M3-W120 reproduced leaking at module scope, at
class-body scope and one level inside a function, in both languages, to the same values.
**Outcome:** fixed in both. The walk no longer descends into a nested scope that gives the bound
name a binding of its own. Twenty-five rebinding forms are named by fixture, with eight control
files beside them; a mutation table of thirty-three is fully killed. Two further defects surfaced while proving the
fix and are fixed here with it, one of them a false binding on a shape M3-W120 recorded as inert.

## 1. Which direction each error runs

A `CallSite.response_fields_read` entry that the call never returned is a **false `static`
binding**. `ObservedDriftDetector` and the vendor-change detectors join findings to call sites
through that column, so a leaked field produces a finding against a site that does not read it —
a false positive, visible to the customer, and attributable to the `static` rung because
`finding.binding_rung` is a column rather than a join.

Dropping a field the call *does* return is the opposite error and it is **silent**: no finding is
raised, nothing appears anywhere, and the break reaches production unreported.

- **Before:** the walk collected every read rooted at the name from the enclosing scope's whole
  subtree. Every error it could make ran in the false-positive direction. It never dropped a
  genuine field, because it never dropped anything.
- **After:** the walk skips a nested scope that declares the name, and only that. The remaining
  errors run in both directions, and each one is bounded by a fixture named below.

**Where the fix is wrong, on what input.** Two call sites in the same scope, binding the same
name one after another:

```python
charge = client.charges.create(...)
print(charge.status)
charge = client.charges.retrieve(...)
print(charge.amount_refunded)
```

Both sites still collect both fields, so both carry one field the other's call returned. No scope
rule reaches this: which read belongs to which call is a question about statement order, not about
scope. It runs in the false-positive direction, which is the direction that at least produces a
finding somebody can read and dispute. `merged`'s function-scope `retrieve` in
`tests/test_module_scope_bindings.py` pins the neighbouring case and is deliberately unchanged.

The second wrong input is a name rebound by an `assignment_expression` in TypeScript —
`charge = other` with no `const`/`let`/`var`. That writes through an existing binding rather than
introducing one, so it is the same order question, and `_holds_binding` there says so in a
docstring rather than guessing.

## 2. The walk stops at a rebinding scope; it does not skip only the rebound reads

Both languages give the same reason, and it is the language's rule rather than a convenience.

Python makes a name local to the *entire* scope that assigns it anywhere, so a read on the line
above the assignment raises `UnboundLocalError`. TypeScript puts the rest of the block in a `let`
or `const`'s temporal dead zone, so the same read throws `ReferenceError`. Neither read reaches
the outer object, so recording its field would be a false field on a read that cannot be of this
call's result.

Skipping only the reads that follow the rebinding would record exactly those. `read_before_rebind`
exists in both languages to state it, and `test_a_read_above_the_rebinding_is_dropped_with_the_rest`
asserts it over both.

The opposite over-reach — skipping every nested scope rather than the rebinding ones — is what
`closure_read` bounds. A nested scope that only *reads* the name reads this call's result through
the closure it is, and the field is genuinely this call's. Dropping it would trade a visible false
finding for a silent missed one. Two mutations, `py-prune-every-scope` and `ts-prune-every-scope`,
make that concrete and both are killed.

## 3. The two languages, and where the fix is not identical

It is not identical, and the asymmetry belongs to the languages.

| | Python | TypeScript |
|---|---|---|
| What opens a scope | function, lambda, comprehension, class body | all of the above **plus every block** — `statement_block`, `for`, `for…of`, `catch`, `switch` body |
| Binding that escapes what it is written in | a walrus escapes a comprehension to the scope around it (PEP 572) | `var` hoists out of its block to the enclosing function |
| Wall on that escape | a `lambda` inside the comprehension | a nested function |

Python has no block scope, so an `if`, `for`, `while`, `with` or `try` body is deliberately not in
`_SCOPE_TYPES` there: a name bound in one belongs to the enclosing function and shadows nothing.
TypeScript needs the wider list because **seven of its thirteen fixtures rebind inside the same
function as the indexed call**, in a block. Nothing in Python can do that, and a rule ported across
unchanged would have left all seven leaking.

The structural symmetry is the last row. Each language has exactly one construct whose binding
does not belong to the construct holding it, each needs a search that passes the scope wall for
that construct alone, and each needs a wall on *that* search or it over-reaches and drops a
genuine field. `_escaping_walrus` and `_hoisted_var` are that pair.

## 4. Which rebinding forms were tested

Thirty-three fixture files — sixteen Python, seventeen TypeScript. Each binds one indexed call to
`charge` and reads `charge.status` off it where the binding is in force. The twenty-five that name
a form read `charge.leaked` from a scope that rebound the name; `leaked` appears in no correct
result at all, which is what `test_no_fixture_here_still_records_the_leaked_field` asserts over
every file in both trees. The eight controls read `charge.total` instead, and require it.

**Python — twelve forms, `tests/fixtures/py/rebinding/src/`:**

| Fixture | What rebinds |
|---|---|
| `parameter` | a function parameter |
| `lambda_parameter` | a lambda parameter |
| `for_target` | a `for` loop target inside a nested function |
| `with_as` | a `with … as` name |
| `except_as` | an `except … as` name |
| `comprehension` | a comprehension's `for` target |
| `destructured` | a nested tuple-unpacking target |
| `augmented` | `charge += 1`, which makes the name local without ever reading an outer one |
| `walrus` | a `:=` inside an `if`, which binds for the whole function because there is no block scope |
| `walrus_in_comprehension` | a `:=` inside a comprehension, which binds *outside* it |
| `nested_def` | `def charge()` — a declaration, not an assignment |
| `class_scope` | a class body attribute |

**TypeScript — thirteen forms, `tests/fixtures/ts/rebinding/src/`:**

| Fixture | What rebinds |
|---|---|
| `parameter`, `optional_parameter`, `arrow_parameter` | the three parameter spellings |
| `for_of` | `for (const charge of …)` |
| `counted_loop` | `for (let charge = …; …)` |
| `catch_parameter` | `catch (charge)` |
| `switch_case` | `const` in an **unbraced** case clause |
| `destructured` | `const { charge }` |
| `array_pattern` | `const [charge]` |
| `bare_block` | `const` in a bare `{ … }` |
| `var_in_function` | `var` in a nested function |
| `var_in_nested_block` | `var` in a block, hoisting to the whole function |
| `nested_function` | `function charge()` — a declaration |

**Controls — eight files under six names, each asserting a field survives**, because every one of
them is a shape where an over-reaching fix would drop a genuine read:

`closure_read` (both languages), `read_before_rebind` (both languages, asserting the opposite),
`let_in_nested_block`, `var_in_deeper_function`, `local_in_deeper_function`,
`walrus_in_comprehension_lambda`.

**Not tested, and therefore not claimed.** A `for (var charge of …)` head — `_hoisted_var` has a
branch for it and no fixture reaches it. A TypeScript `using` declaration. A Python `match` capture
pattern. A rebinding by `global` or `nonlocal` declaration. Each is a real spelling; none is
asserted here, and the enumeration above is the whole of what was measured.

## 5. Two defects found while proving the fix

### 5.1 A walrus inside a comprehension binds outside it

A comprehension is a scope, so the rebinding search stopped at one. PEP 572 binds an assignment
expression in the scope **containing** the comprehension, which makes it the one Python binding
that escapes the construct it is written in. So this leaked:

```python
def report():
    early = charge.leaked                        # recorded against the outer call, wrongly
    picked = [(charge := row) for row in rows]   # binds `charge` in `report`
    return early, picked
```

The interpreter settles it rather than the grammar. Run as a program, that shape raises
`UnboundLocalError` on the first line, so the field cannot be of the call's result — a false
`static` binding of exactly the kind the walk was narrowed to remove.

`_escaping_walrus` enters a comprehension looking for that one construct and nothing else. A
`lambda` written inside the comprehension stops it, and is the only thing that can: a `def` or a
`class` in an expression is a syntax error, so no other scope is spellable there.
`walrus_in_comprehension_lambda` is the control, and the interpreter agrees with it too — that
shape returns the field rather than raising.

### 5.2 The module name was skipped by object identity

M3-W120 reported that `python_lang.py:450` compared tree-sitter nodes with `is`, measured the
branch unreachable, and recorded it as **inert**. It is not inert.

The scan that collects imported names walks an `import_from_statement`'s named children and skips
the module name among them. tree-sitter returns a fresh handle on every access — which is why
`_same` exists in that module, and this was the one place not using it — so the skip never fired
and `stripe` landed in the set of names a constructor may be spelled as. A file that binds
`stripe` to something of its own then has every call on the result attributed to the vendor:

```python
from stripe import StripeClient

def stripe(**kwargs):
    return Ledger(**kwargs)

ledger = stripe(amount=1)
ledger.charges.create(amount=1)     # indexed as stripe.charges.create, before this fix
```

That is a false binding at the *binding* step rather than the field step, which
`_constructs_client`'s own docstring argues is the worse of the two: a wrongly bound call site
produces findings against code that never called the vendor at all. `module_name_shadowed` sits
with the other negative cases in `tests/test_python_client_forms.py`, and it failed before the
one-line change and passes after.

## 6. What M3-W120's pins became

Three assertions in `tests/test_module_scope_bindings.py` changed direction:

| Pin | Was | Is |
|---|---|---|
| `shadowed` | `['status', 'total']` | `['status']` |
| `nested_function` | `['status', 'total']` | `['status']` |
| `merged`, module-scope `create` | `['amount_refunded', 'status']` | `['status']` |

**Why that is not a weakening.** Each of those fixtures also reads a field the call genuinely
returns, and every one of those assertions still requires it — an over-aggressive fix fails them
rather than passing them. `merged`'s function-scope `retrieve` is unchanged, which is what shows
the narrowing hit the one row that was wrong rather than both. `script` and `class_body` did not
move at all. And the mutation that reinstates the defect, `py-walk-restored` / `ts-walk-restored`,
kills the whole table on each side — 20 and 22 failures respectively — so the pins that moved are
proven to detect the old behaviour rather than merely to have been rewritten.

`_enclosing_scope` is untouched in both modules apart from prose it was already owed. M3-W120
established that `return root` is the only answer it can give; `nested_function` is the control
that placed the fault in the walk, and it still places it.

## 7. The mutation table

Thirty-three mutations over the two modules, `tools/mutate_rebind.py`, gitignored like the earlier
harnesses. **All thirty-three killed.** Scheduler `-n0` with `-p no:randomly`, over
`tests/test_rebinding_shadow.py` and `tests/test_module_scope_bindings.py`, baseline 51 passed.

Six outcomes are separated rather than folded into pass/fail, because five of them have produced a
false verdict on this project: `killed`, `survived`, `did-not-compile` (`compile()` before any
run), `unreadable` (pytest exited outside `{0,1}`, or exited 1 with no `FAILED` line),
`baseline-drifted` (the unmutated pass count is not the expected one — a skipped test exits 0 from
the child and is caught only by matching the count), and `not-applied` (the anchor is absent or
ambiguous).

**CRLF.** Both modules are CRLF in the working tree. Anchors are written LF in the harness and
rewritten to the file's own newline before matching; without that step every anchor matches
nothing, which the `not-applied` count reports as a harness fault rather than as a survival. The
harness reads and writes bytes and never lets the platform choose an encoding, and the child gets
`PYTHONIOENCODING=utf-8` with `errors="replace"` harness-side.

**The one that survived, and what it turned out to be.** `py-nested-wall` — deleting
`if node.type in _SCOPE_TYPES: return False` from Python's `_holds_binding` — survived a table of
thirty-one, alone. The rule is to suspect the mutation, then the test, then the code:

1. *The mutation.* Meaningful. A program that distinguishes the two exists and was run: with the
   wall, a nested function that only *contains* a deeper function assigning the name does not count
   as rebinding, and its read of the outer object survives. The interpreter returns that field
   rather than raising, so the wall is right and removing it drops a genuine read — the silent
   direction.
2. *The test.* This is where the fault was. Every Python fixture put its rebinding one scope down,
   where the wall is never consulted. Python's analogue of `var_in_deeper_function` has to be a
   nested *function*, because a nested block is not a scope there at all, and no fixture was
   written that way. `local_in_deeper_function` closes it and the mutation now dies.
3. *The code.* Not at fault for the survival — but the same guard turned out to be over-broad in
   the opposite direction for exactly one construct, which is §5.1.

**The earlier survival, resolved.** A `ts-switch-not-a-scope` mutation survived earlier in this
task. Same rule, same order: the fault was the fixture, whose `case` body was braced, so the
braced body is a `statement_block` and was pruned as one before `switch_body` ever carried the
weight. The fixture is now deliberately unbraced and says so in a comment; the mutation is killed.

This is the fourth and fifth time on this project that a surviving mutation was the harness or the
fixture rather than the production code. The order in the rule has now been right every time.

## 8. Golden output and the benchmark corpus

**No golden file changed** and none was edited. `tests/golden/` holds `tool_schemas.json` only,
which is the MCP tool surface and does not read an index.

**No `benchmark/corpus/` artifact changed** and none was edited. Measured rather than assumed:
`tools/corpus_delta.py` indexed the five frozen checkouts in `.cache/corpus/` on each side of the
fix. 159 call sites both sides, and **one row differs**:

```
- furever  scripts/setup-accounts.py:514  stripe.Account.create  business_profile,business_profile.name,country,id
+ furever  scripts/setup-accounts.py:514  stripe.Account.create  id
```

That is the defect on a real customer repository. `ensure_accounts` binds `account` from
`stripe.Account.create` and reads `account.id` off it; two comprehensions earlier in the same
function rebind `account` and read `account.business_profile.name` and `account.country` off rows
fetched from somewhere else entirely. Three false `static` bindings, removed; the genuine `id`
kept.

**It does not reach the corpus.** `corpus_delta.py` deliberately runs *both* adapters over every
checkout, so it measures a superset of what the benchmark scores. The corpus build uses
`select_language_adapter`, one language per repository, and furever resolves to **typescript** —
it carries both `package.json` and `requirements.txt`, and `language_adapters()` returns
TypeScript first. So `scripts/setup-accounts.py` is not indexed by the corpus build at all, and
nothing the benchmark scores moves.

This matters more than it looks, because `scripts/build_corpus_specs.py` chooses a pair's field as
"the alphabetically first property of that operation that no indexed call site in the repository
already reads". A change to what a site reads could change which field a regeneration picks. It
does not here, for the reason above. Reported rather than acted on: `benchmark/corpus/` is not
mine to edit, and M3-W121 regenerated it one commit before this branch started.

## 9. M3-W120's three other findings

| Finding | Taken? |
|---|---|
| `python_lang.py:450` compares nodes with `is` | **Taken** — §5.2. Not inert, and it produced a false binding. |
| `python_lang.py:700` and `typescript.py:528` are structurally unreachable | **Left.** |
| `_result_target` does not recognise a TypeScript class field | **Left — reported as the next task.** |

**Why the unreachable tails stay.** Both are the `return None` after a `while parent is not None`
loop in `_result_target`. The loop returns first on every input because the root — `module` in
Python, `program` in TypeScript — is not in `_RESULT_WRAPPERS`, so the tail is dead as written.
Deleting it changes no observable behaviour, which means no test can be written that fails before
and passes after; a change with no failing test is not one this repository's discipline supports,
and the statement would be re-derived by the next reader anyway because the annotation promises an
optional return.

**What would make them reachable again:** adding the root node type to `_RESULT_WRAPPERS`, or a
tree-sitter grammar revision in which the outermost node is a wrapper form. Either is a one-line
change somebody could make without noticing that the loop then falls off its end, and the tail is
what keeps that from being an implicit `None` nobody wrote.

**Why the class field is the next task.** `_result_target` in TypeScript recognises a
`variable_declarator` and an `assignment_expression`. A class field — `private charge = await
stripe.charges.create(...)` — is a `public_field_definition`, matches neither, and binds nothing on
the response side. The call *is* indexed and its request side *is* recorded, so this is a missing
binding rather than a false one: a missed finding, silent, and the same direction the fix here was
careful not to move in. It is larger than one node type, because the reads are then rooted at
`this.charge` rather than at a bare identifier and `_response_fields` roots chains at an
identifier — which is the same two-segment problem `self.client` solved on the Python request
side. `tests/test_module_scope_bindings.py::test_a_class_body_call_reaches_the_same_fallback…`
records the Python half of the asymmetry today.

## 10. The four gates

Run on the merged tree, `origin/main` at `26bc526` merged into this branch.

| Gate | Result | Exit |
|---|---|---|
| `uv run pytest -q` | 2823 passed, 4 skipped (208.54s), scheduler `-n auto` from `addopts` | 0 |
| `uv run python scripts/lint_encoding.py src scripts tests` | no output | 0 |
| `PYTHONIOENCODING=utf-8 uv run lint-imports` | `sync.core depends on nothing KEPT`; 1 kept, 0 broken | 0 |
| `uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt` | no output | 0 |

`lint-imports` was run unredirected. Redirected it dies on its own box-drawing output and the
failure reads as a contract break.

**Baselines, so a later harness does not read the difference as drift.** This worktree measured
**2808 passed, 4 skipped** before the merge, at `4aa1dd0`, scheduler `-n auto`. The brief's figure
for `origin/main` was 2778 passed, 1 skipped in a checkout with a populated gitignored
`.cache/specs/`; this worktree's `.cache/` is populated and it still reads 4 skips, so the two
numbers are not comparable and neither is wrong. The scheduler is named on every measurement in
this report for the same reason.
