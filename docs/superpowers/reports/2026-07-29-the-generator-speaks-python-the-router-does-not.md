# The generator speaks Python; the router still does not

**Date:** 2026-07-29
**Scope:** B43 — `sync.benchmark.mutate` could not build a labelled pair from a Python call site.
**Outcome:** both change kinds attach, `sync/route/templates.py` is untouched, and the four corpus
floors are unmoved.

## How the router's question was separated from the generator's

**The generator owns its own table. `sync.route.templates` was not edited at all.**

`language_for` answers *can a codemod patch this file*. Its other two callers are
`remediate.tiered`, choosing whether a finding routes to a codemod tier, and
`remediate.property_omit`, which does the patching — and both of those match TypeScript's `object`
literal, where Python has `dictionary`. Adding `.py` there would have admitted a Python finding to
a tier that produces an empty diff and abandons as *the remediator produced no change*, which is
exactly the failure that function's docstring exists to prevent.

`mutate.py` asks a different question: *can I parse and edit this file to build a labelled pair*.
It now answers it from `_MUTABLE_LANGUAGES`, its own mapping, and no longer imports from
`sync.route.templates`.

**Why a table rather than a parameter.** A `language_for(path, *, for_codemod=True)` is the same
coupling spelled with an argument: one function still answers both questions, and a caller who
omits the flag gets the wrong answer with nothing to say so. The failure mode that produced this
task was silence, and a default-valued parameter preserves it.

**Why a copy rather than a subset.** The TypeScript half of `_MUTABLE_LANGUAGES` is the router's
table verbatim, plus `.py`. Nothing that was mutable before is mutable differently now, which is
what keeps this change off the corpus numbers. The two tables are free to diverge from here, and
that is the point — the generator's capability and the codemod tier's are different facts and
should be allowed to move apart.

Dropping the import also removes a dependency the module's own docstring argues against in spirit:
`mutate.py` deliberately imports nothing from `sync.index`, `sync.detect` or `sync.graph` so the
label cannot be derived from the thing being scored. A benchmark generator taking its capability
table from the router is a smaller version of the same coupling.

## Which primitives learned Python

| | TypeScript | Python |
|---|---|---|
| call node | `call_expression` | `call` |
| request literal | `object` | `dictionary`, and usually absent |
| request field | entry in the literal | **keyword argument** |
| result binder | `variable_declarator`, `assignment_expression` | `assignment`, `named_expression` |
| field read | `member_expression` (`property`) | `attribute` (`attribute`) |

Three of those are worth a sentence each.

**Keyword arguments are the request half, not the literal.** Most Python call sites pass no
mapping at all, so `_object_argument` returning `None` cannot mean "cannot mutate". A break is
written as a keyword argument because that is what `sync.index.python_lang` records — a mutation
into a dict literal would produce a dependency the indexer reads and the SDK does not accept.

**The walrus is a binder here too.** B35 taught the indexer to record reads through
`named_expression`; a shape the binder can find and the generator cannot break would be a labelled
negative that is really a gap. The walk climbs to the binder and then on to the statement, because
the guard is appended to the statement — `charge := create(...)` sits inside a condition, and
splicing after the expression would land inside it.

**The read search cannot be one search over both grammars.** ast-grep refuses a kind the grammar
does not have rather than matching nothing, so `find_all(kind="member_expression")` raises against
Python source. That was found by running it, not by reading the docs.

## Both change kinds attach

Request-side, into a keyword-argument call and into a positional dict literal. Response-side, as
`; assert name.field is not None` appended to the binding statement.

**The guard occupies no new line, and Python is where that matters most.** `upsert_call_site` keys
identity on line and column, so a guard on a line of its own renames every call below it in the
file and its label addresses a row the mutated tree no longer holds. A semicolon joins two simple
statements on one line and `assert` is a simple statement — which sidesteps indentation entirely.
A Python guard written as an `if` would have to be indented to match whatever block it landed in,
and getting that wrong is a syntax error rather than a larger diff. `test_the_mutated_python_still_parses`
runs `ast.parse` over the result for that reason.

A result nobody binds stays `unreachable` and is labelled unaffected, unchanged from TypeScript and
for the same reason: a call that reads no response field is not broken by a response property being
removed.

## The router still declines Python, and there is a test for it

This is the regression the change was most likely to introduce and it would have been completely
silent — nothing in the corpus numbers would have moved.

```python
assert language_for("src/app.py") is None
assert language_for("src/app.ts") == "typescript"
```

and the consequence, asserted where it costs something:

```python
with pytest.raises(CannotPatch, match="not a language this codemod parses"):
    PropertyOmitRemediator().propose(finding=None, change=..., site=<a .py site>, repo=...)
```

`CannotPatch` is the tier falling through to the agent rather than abandoning the finding, which
is the behaviour that was already correct and had to stay so.

## The four floors are unmoved

```
  binding precision             1.0000    1.0000   n=16
  binding recall                1.0000    1.0000   n=16
  falsifiable negatives              4         4
  pairs scored                      12        12
  symbol map              5f71dcd3bec15f71dcd3bec1

Every floor cleared.
```

Nothing was pinned and no corpus file was touched. `benchmark/corpus/`, `scripts/gate_corpus.py`,
`src/sync/index/`, `src/sync/signals/` and `src/sync/route/` are all unmodified.

## Found and deliberately left

**No repair primitive inverts the Python break.** `omit_argument_at` is the codemod that undoes a
request insertion in TypeScript, and the comment in `_insert_property` explains that a leading
insertion is the one it removes exactly. There is no Python equivalent, so
`test_a_request_mutation_is_undone_exactly_by_the_repair_primitive` has no Python counterpart.
That is honest rather than missing: this task builds the *break*, and the repair half is the
codemod tier that deliberately still declines Python. A Python finding is expected to reach the
agent tier, not a codemod.

**The generator can now break more Python than the corpus can use.** Nothing is pinned yet, so
none of this is exercised end to end against a real repository. That is B44 and it is deliberately
separate.

## One defect found while writing this report, and fixed rather than noted

The keyword insertion originally placed the field **first**, mirroring the literal insertion above
— which is correct in TypeScript and a `SyntaxError` in Python, because a positional argument may
not follow a keyword one. `create(customer_id)` is an ordinary shape and one the qualifying
repository writes, and the mutation turned it into:

```
result = client.customers.create(description='sync-benchmark', customer_id)
                                                                          ^
SyntaxError: positional argument follows keyword argument
```

That is worse than a failed mutation. tree-sitter recovers from a syntax error and returns a tree,
so `depends_on_change` would have read the field back out and the pair would have been labelled
affected — a corrupt pair rather than a refused one, over a tree that is not Python.

The insertion is now written last, which pays the trailing-comma reasoning the leading form was
chosen to avoid, and `ast.parse` runs over the mutated source in the tests rather than the two
strings merely being compared. I nearly shipped this as a stated limitation; writing the sentence
is what showed it was a bug.
