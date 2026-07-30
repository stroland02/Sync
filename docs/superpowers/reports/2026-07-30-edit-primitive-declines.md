# Twelve statements in the edit primitives, six of which no fixture can reach

M3-W110. `sync.route.templates` holds the tier-0 rewrites Sync applies with no model. It is the
module where `CLAUDE.md`'s codemod rule bites: a wrong edit produces source that parses cleanly
and means something else, because tree-sitter reports `{ model: "x", , max_tokens: 16 }` with
zero `ERROR` nodes, zero `MISSING` nodes and `root_node.has_error` false -- the same verdict it
gives correct source. Correctness here is established by construction, so this is a testing task
and it made no production change.

Twelve statements were unexecuted. **Six are reachable and now have tests. Six are not reachable
by any fixture.** Three are *redundant in the forward direction* as well -- a statement whose
answer equals what the code below it would have produced anyway: `402` among the unreachable
six, `196` and `633` among the reachable ones. The distinction matters because they are
deletable and the other nine are not, and because a mutation that removes a redundant statement
survives every test by construction. Both survivals in the table below are exactly that, and
were predicted before the harness ran.

## Coverage, before and after

Both figures come from the same command over the whole suite, scheduler `-n auto` (the repo's
`addopts` default, 12 workers):

    uv run pytest -q -p no:randomly --cov=sync.route.templates --cov-report=term-missing

Before, at `6b01f04` (`origin/main`):

    src\sync\route\templates.py   229   12   95%   196, 213, 215, 222, 308, 364, 402, 507, 600, 611, 617, 633
    2639 passed, 4 skipped in 206.47s

After:

    src\sync\route\templates.py   229    6   97%   222, 308, 364, 402, 507, 611
    2651 passed, 4 skipped in 189.55s, exit 0

No statement was added to or removed from `templates.py`, so the line numbers are the same in
both columns. Twelve tests were added, all in one new file, and no production file changed.
The six that remain are the six the next section judges unreachable.

## The twelve

`omit_property_at` is the one public function in this module that nothing in `src/` calls --
`scripts/dead_links_baseline.txt` records it, with three reasons. Rows 1, 2, 3 and 5 below are
reachable **only** through it: `_to_character_column`, `_contains` and `_call_at` each have
exactly one caller in the module and it is `omit_property_at`. That is why their "what the
pipeline does" column says nothing happens rather than naming a cost.

| # | Statement | Input that reaches it | Is the answer right? | What the pipeline does with it |
|---|---|---|---|---|
| 1 | `196` `_to_character_column` -> `len(lines[line - 1])` | a byte column at or past the end of its line. `CallSite.col` is measured in bytes against the file as it was indexed, so a line that has since lost characters yields one; any column on an empty line yields one too (`0 >= 0`) | Yes, and **redundant in the forward direction** -- the fall-through at `199` computes the same number. `encoded[:byte_col]` with `byte_col >= len(encoded)` is `encoded`, and decoding valid UTF-8 back gives the line, so both branches return the line's character length | **Nothing.** `_call_at` only, and `omit_property_at` is unwired. Inside the primitive: clamping to the end of the line keeps the position inside a call that continues onto later lines, and outside every call that ends on this one |
| 2 | `213` `_contains` -> `False` (column left of the node on its start line) | column 0 of an indented statement whose call starts further right | Yes. A line is not an identity: two calls can share one, and accepting on a line match would edit whichever the formatter put first | **Nothing** today. Within the primitive it produces `omit_property_at`'s `return source` at `304` -- the same value that function returns for "already correct", which is one of the three reasons the baseline entry gives for not wiring it |
| 3 | `215` `_contains` -> `False` (column at or past the node's end on its end line) | the column where the next statement on that line begins | Yes. Ranges are half-open at the end, so a column equal to `end.column` is one past the node | **Nothing** today; as row 2 |
| 4 | `222` `_has_object_argument` -> `False` when `field("arguments")` is `None` | **none.** `arguments` is a required field of `call_expression` in all three grammars, and recovery on a truncated call yields an `ERROR` node rather than a fieldless `call_expression`. A tagged template's `arguments` field is the `template_string`, not `None` | Unfalsifiable. A call with no argument list has no property to remove, so `False` is the only defensible answer | Feeds `_preferred`'s sort key, from both `_call_at` and `_object_argument_at`. A wrong `True` would let a call carrying no object win the tie, and the edit would find nothing and return the source |
| 5 | `308` `omit_property_at` -> `return source` when `field("arguments")` is `None` | **none**, same reason as row 4 | Unfalsifiable | **Nothing.** No caller in `src/` |
| 6 | `364` `_declared_keys` -> `continue` when the key node is `None` | **none.** Every `pair` carries a key node: `{ : 1 }` yields an *empty* `property_identifier`, not a missing field, and `pair.child(0)` is non-`None` for any pair | Unfalsifiable, and skipping is the direction the guard's own docstring calls safe: an unknown key is not collected | `rename_parameter`'s duplicate-key guard. Collecting a phantom key would decline a safe rename; missing a real one produces the silent last-wins duplicate the guard exists to prevent |
| 7 | `402` `rename_parameter` -> `continue` when the key node is `None` | **none**, and **redundant in the forward direction**: line `398` already evaluated `_pair_part(pair, "key", 0)`, which computes `pair.field("key") or pair.child(0)` -- the identical expression -- and returns `None` when it is `None`, so `None != old` has already `continue`d one line earlier | Unfalsifiable | As row 6 |
| 8 | `507` `_object_argument_at` -> `None` when `field("arguments")` is `None` | **none**, same reason as row 4 | Unfalsifiable | Two live callers. `omit_argument_at` -> `PropertyOmitRemediator` raises `CannotPatch` -> the cascade falls through to the agent inside the same attempt. `argument_is_literal_at` -> `field_passed_as_literal=None` -> row 4 declines -> `AGENT` |
| 9 | `600` `argument_is_literal_at` -> `None` when no object argument was located | a line/col naming no call: a `CallSite` the index has outlived, or a slip in the 1-based-to-0-based conversion `tiered._passed_as_literal` performs | Yes, and the `None`/`False` split is load-bearing. `False` means located and not a literal, which row 4 can explain; `None` means the router never saw the call | `RoutingFacts.field_passed_as_literal = None`. Row 4 tests `is True`, so the request-side mechanical row declines and the change reaches the `fall-through` row and the agent. Costs an agent run; never a wrong edit |
| 10 | `611` `argument_is_literal_at` -> `False` when the pair has no value | **none.** `create({ a: })` yields a pair whose `value` field is a MISSING `identifier` of empty text, not a missing field | Unfalsifiable, and the nearest reachable input answers identically: an empty `identifier` is not in `_LITERAL_KINDS`, so `620` returns `False` as well | As row 9, but `False` rather than `None`. Row 4 declines either way; only what the router could say about why differs |
| 11 | `617` `argument_is_literal_at` -> `not any(template_substitution)` | a value written as a backtick string. `True` for `` `x@example.com` ``, `False` for `` `${user}@example.com` `` | Yes. A template with no substitution is a literal spelled differently; one substitution reaches a variable | **The only one of the twelve whose wrong answer produces a wrong edit rather than a missed one.** See below |
| 12 | `633` `apply_rules` -> `return source` when there are no rules | `model_literal_swap` returning `[]` for a change `LiteralSwapRemediator.can_handle` accepted: a `deprecation/model-*` change carrying a `replacement` and no `model_id` | The value is right and the statement is **redundant in the forward direction** -- with `rules == []` the loop runs zero times and `645` returns the same `source` | `propose` sees `updated == original` and returns an empty diff. `make_patch` sets `patch=None`, records `attempt_strategy="codemod"` and `diagnostics="the remediator produced no change"`; `route_after_patch` sends it back to `patch`, never to `static_verify`, up to `MAX_STATIC_ATTEMPTS=3`, and the second attempt narrows to the adaptive tier. Costs one attempt, one `retried` row attributed to a codemod, and a diagnostic that says "no change" where the truth is "no rule could be built" |

Eleven of the twelve cost at most an agent run. One -- row 11 -- gates a deletion.

## Can any of the twelve make a remediator claim success having written nothing?

**No, and for two independent reasons.**

**None of them can produce a non-empty diff.** All three codemod remediators derive the diff from
`updated != original` and write the file in the same branch that renders it, so the failure the
kit's first rule names -- a diff describing an edit that is not on disk -- is not reachable from
any of the twelve. Each of them either declines or returns the input unchanged.

**The empty diff they can produce is not read as success anywhere.** `make_patch` turns it into
`patch=None`; `route_after_patch` then routes to `patch` or to `abandon` and never to
`static_verify`, so `push_branch` is not reached and no pull request is opened.

The brief's premise -- that `check_remediator` reads an empty diff as a decline, so a remediator
claiming everything and writing nothing satisfies the kit -- **describes the state before the
kit's third check existed.** `_check_propose_touches_the_clone` now fails on an empty diff
against the *case*: "the case handed to the kit must be one this remediator patches." Its own
docstring records that this used to be reported as conforming and that
`ParameterRenameRemediator` passed the kit on a patch it never produced.
`test_the_conformance_kit_refuses_that_case_rather_than_passing_it` asserts the current behaviour
against the row-12 input rather than restating the docstring.

What the twelve *can* do is make a decline indistinguishable from "already migrated". That is
row 12's real cost, and it is paid in an attempt rather than in a wrong patch.

## What the two `return source` paths cost a caller that cannot distinguish decline from no-op

The two uncovered ones are `308` and `633`. They are opposite cases.

**`308` costs nothing, because the cost was already priced and refused.** `omit_property_at`
answers two ways -- the edited source, or the input -- and both `304` (no call at that position)
and `308` (no object argument) return the input, exactly as `319` does when the property is
simply absent. So "cannot establish" and "already correct" are the same value. The baseline entry
names that as one of three reasons the symbol is not wired, and the remediator that needs this
operation calls `omit_argument_at` instead, which answers `None` for the first two and `source`
for the third. `PropertyOmitRemediator` turns the `None` into `CannotPatch` and the `source` into
an empty diff, and its module docstring is explicit that collapsing them would either abandon
findings the agent could fix or spend an agent run on every already-correct repository.

**`633` pays it.** `LiteralSwapRemediator` cannot tell "no rule could be built" from "the rules
matched nothing in this file", because both arrive as `updated == original`. The second is the
honest already-migrated case the module docstring describes. The first is a decline, and it
carries a diagnostic that misdescribes it. The gap is one line wide:
`can_handle` tests `_replacement(change)` and never `raw["model_id"]`, while `model_literal_swap`
requires both. The in-repo catalogue always writes `model_id`, so this input arrives from the two
sources that do not go through it: the feed consumer, which builds `VendorChange(**entry)` with
no check on the contents of `raw`, and a third-party adapter, which is unconstrained by
construction. **Not fixed here** -- `src/sync/remediate/` is outside this brief, and the fix is a
`can_handle` that tests both fields or a `CannotPatch` in `propose`, which is a decision about
that module's decline contract rather than about the primitive.

## Line 617: what it guards, and the cost in each direction

It is the last statement in the chain `routing_facts` -> `_passed_as_literal` ->
`argument_is_literal_at`, and its answer is `RoutingFacts.field_passed_as_literal`. Row 4 of the
decision table reads it:

```python
_Row("request-field-removed-literal", CODEMOD, lambda r, f: (
    _is(r, kind="existence", action="remove", direction="request")
    and f.field_resolved is True
    and f.field_passed_as_literal is True
))
```

So `True` is what sends a request-property removal to tier 0, where `PropertyOmitRemediator`
deletes the pair. The two directions are not symmetric.

**A wrong `True` deletes a variable's last reference.** Where the value is a template
interpolating `user`, the pair is the only use of it. Deleting it produces source that still compiles wherever
`user` is used elsewhere, and where it is not, `tsc` reports it only under `noUnusedLocals` --
which is off by default, and this project's gate runs the customer's own configuration. So the
wrong `True` is precisely the failure class `CLAUDE.md` calls most expensive: a patch that
compiles, type-checks, and drops what the call was sending. The pull request would claim it
removed a property the vendor retired, and would also have removed the interpolation that built
its value.

**A wrong `False` costs an agent run.** Row 4 declines, the change falls through to `AGENT`, and
the agent reads the template and does the same edit for the price of a model call.

The code takes the safe direction wherever it is uncertain: any substitution answers `False`, and
a tagged template (`` tag`x` ``) never reaches `617` at all -- it parses as a `call_expression`,
so `620` answers from `_LITERAL_KINDS` and returns `False`. All three shapes are now pinned.

## What was judged unreachable, and the probe

Six statements: `222`, `308`, `364`, `402`, `507`, `611`. Each was replaced with
`raise AssertionError` and the **whole suite** run. A green suite at the baseline pass count
means the condition never held across every test in the repository, which is stronger evidence
than "no assertion changed" -- the latter only says no assertion noticed.

All six went in together, because a green suite answers for all six at once and a red one would
have been bisected. Scheduler `-n auto`. Harness at `tools/probe/unreachable.py`, gitignored.

    anchor x1  222 _has_object_argument: arguments is None
    anchor x1  308 omit_property_at: arguments is None
    anchor x1  364 _declared_keys: key node is None
    anchor x1  402 rename_parameter: key node is None
    anchor x1  507 _object_argument_at: arguments is None
    anchor x1  611 argument_is_literal_at: value is None
    PROBED   scheduler=-n auto exit=0 {'passed': 2651, 'skipped': 4}
    NEVER-HELD: none of the six conditions held in any test
    RESTORED scheduler=-n auto exit=0 {'passed': 2651, 'skipped': 4}
    baseline reproduced: True

Every anchor matched exactly once, the mutated source compiled, and the restored tree
reproduced the pass count -- so the verdict is not NOT-APPLIED, DID-NOT-COMPILE or
BASELINE-DRIFTED wearing a green suit.

Two supporting measurements, because a green suite proves only that the suite does not reach a
statement:

**The grammar makes all six structural.** Three required fields cover them: `arguments` on
`call_expression` (`222`, `308`, `507`), `key` on `pair` (`364`, `402`) and `value` on `pair`
(`611`). A truncated call (`create(`) is recovered as an
`ERROR` node containing an `identifier` and a `(`, not as a `call_expression` missing its
arguments; `{ a: }` yields a pair whose `value` is a MISSING `identifier` with empty text, and
`{ : 1 }` a pair whose `key` is an empty `property_identifier`. In every case the field is
present and the guard's condition is false.

**A million constructed sources did not produce one.** Two probes, because the first was thin
where it mattered:

- *Random fragments.* Strings of 2-11 tokens drawn from a 29-token alphabet of TypeScript
  punctuation and identifiers, 200,000 per grammar over `typescript`, `tsx` and `javascript`.
  It produced 6,702 `call_expression` nodes and 5,293 `object` nodes -- but only **65** `pair`
  nodes, which is thin evidence about a guard on a pair's fields.
- *Constructed objects.* Every combination of up to three entries drawn from 29 entry forms --
  well-formed pairs, `a:` with no value, `:` with no key, shorthand, quoted and computed keys, a
  spread, a getter, a method, `a::1`, `a b` -- inside 14 wrappers including four truncated ones,
  each also re-run with newlines after the separators, over all three grammars. **1,060,878
  sources, 1,376,836 `call_expression` nodes, 1,979,268 `object` nodes, 3,869,338 `pair`
  nodes.**

Across both: **zero** missing `arguments`, `key` or `value` fields, and zero `arguments` fields
of empty text.

**One of the six is redundant as well as unreachable, and it can be shown without a probe.**
`402` is guarded by the identical expression one line above it: `_pair_part(pair, "key", 0)` *is*
`_key_node(pair)` followed by `.text()`, and it returns `None` exactly when the node is `None`, so
`None != old` has already `continue`d. `611` is a weaker case and is not counted as redundant: it
is unreachable, and the *nearest* reachable input -- a pair whose value is a MISSING `identifier`
-- happens to answer `False` at `620` as the guard would have. That is a coincidence of the
literal-kind set rather than a property of the code below it.

**Two of the reachable six are redundant too, and the mutation table below shows it.** `196`
returns the line's character length, which is what the fall-through at `199` computes for every
input that reaches it -- checked over 400 `(line, byte_col)` pairs spanning empty lines,
accented text, CJK, an astral-plane emoji and a 300-character line, where
`len(line) == len(line.encode()[:byte_col].decode("utf-8", errors="ignore"))` held every time,
because slicing at or past the end of the encoding yields the whole encoding and it is valid
UTF-8. `633` returns `source`, which is what `645` returns when the loop body runs zero times.

Both are stated rather than removed. This brief forbids a production change without a test
proving the current behaviour wrong, and neither is wrong -- and `196` in particular is the kind
of statement whose deletion looks like a tidy-up and is unverifiable, which is the same trade the
comma-span decision already refuses. It is worth being precise about what "redundant" means here:
`196` is not *unobservable* for every mutation. `return 0` changes the answer and a test catches
it. What no test can catch is the *removal* of the guard, because the fall-through answers
identically.

## Mutation table

Harness at `tools/probe/mutate.py`, gitignored. Scheduler `-n0`, over eight files: the new one,
the four existing test files for this module, `tests/test_migration_rules.py`,
`tests/test_tier_zero_reach.py` and `tests/test_shipped_conformance.py`. **Baseline 139 passed,
exit 0, before and after.** Nothing came back NOT-APPLIED, DID-NOT-COMPILE, UNREADABLE or
BASELINE-DRIFTED. Every test in the new file pins existing behaviour, so "fails first" is
established by these mutations rather than by writing against absent code.

Eleven mutations sit in `templates.py`; M12 and M13 sit in `sync/route/matrix.py`, because
`test_an_unestablished_literal_fact_keeps_row_four_from_firing` makes a claim about the row that
reads the primitive's answer, and a claim about a row is only falsifiable by mutating the row.

| # | Statement | Mutation | Outcome | Killed by |
|---|---|---|---|---|
| M1 | `templates:196` | the clamp returns `0` | KILLED, 1 failed | `…byte_column_past_the_end_of_its_line_still_resolves_the_call` |
| M2 | `templates:196` | the clamp returns `byte_col` -- the guard removed in effect | **SURVIVED** | -- see below |
| M3 | `templates:213` | a column left of the node reads as contained | KILLED, 1 failed | `…column_before_the_call_on_its_own_start_line_declines` |
| M4 | `templates:215` | a column past the node reads as contained | KILLED, 1 failed | `…column_past_the_call_on_its_end_line_declines` |
| M5 | `templates:600` | cannot-establish answers `False` instead of `None` | KILLED, 1 failed | `…position_naming_no_call_cannot_establish_the_literal_fact` |
| M6 | `templates:617` | the substitution scan loses its `not` | KILLED, 2 failed | both template tests -- it flips each one the other way |
| M7 | `templates:617` | the substitution kind never matches | KILLED, 1 failed | `…template_carrying_a_substitution_is_not_a_literal` |
| M8 | `templates:633` | no rules returns `""` rather than the source | KILLED, 4 failed | all four `apply_rules` tests, including the conformance one |
| M9 | `templates:631` | `if not rules:` becomes `if False:` -- the early return never taken | **SURVIVED** | -- see below |
| M10 | `templates:620` | the literal-kind test answers `None` | KILLED, 5 failed | `…tagged_template_is_not_a_literal`, `…keeps_row_four_from_firing`, and three in `test_tier_zero_reach.py` |
| M11 | `templates:50` | `_LITERAL_KINDS` admits `call_expression` | KILLED, 1 failed | `…tagged_template_is_not_a_literal` |
| M12 | `matrix:100` | row 4 accepts a located non-literal (`is not None`) | KILLED, 1 failed | `test_a_variable_argument_still_declines_to_the_agent` |
| M13 | `matrix:100` | row 4 accepts an unestablished fact (`is not False`) | KILLED, 2 failed | `…keeps_row_four_from_firing`, `test_a_spread_cannot_establish_the_fact_and_declines` |

Thirteen mutations, eleven killed. **Every one of the twelve new tests is killed by at least one
mutation.**

### The two survivals are the finding, not a gap

M2 and M9 are the redundancy claims, run as mutations so the claim is measured rather than
argued. Each removes a statement's effect entirely and the suite does not notice, because the
fall-through computes the same answer:

- **M2.** `_to_character_column`'s clamp returns the line's character length; without it,
  `encoded[:byte_col]` is the whole encoding, decoding is lossless, and `len` is the same number.
  M1 is the control: mutate the *value* rather than remove the guard and a test catches it
  immediately. So `196` is reachable and pinned, and simultaneously deletable.
- **M9.** `apply_rules`'s early return hands back `source`; without it, `result = source`, the
  loop body runs zero times, and `645` returns the same object. M8 is the control.

Neither is removed. This brief forbids a production change without a test proving the current
behaviour wrong, and a statement whose answer is right is not wrong for being redundant --
`omit_parameter`'s own `end <= start` guard is kept on exactly that reasoning, with a comment
saying so.

**Suspecting the mutation, then the test, then the code** was applied to both and stopped at the
first step: the mutations are sound, and what they prove is a property of the code. That keeps
the project's run intact -- the fault behind a survival has been outside the production code
every time.

### The false-verdict modes, and which one bit

All seven were answered by construction, and one of them was exercised rather than merely
provided for.

- **Colourised summary.** `--color=no`, and every verdict is read from the summary *counts*. The
  `FAILED ` prefix is parsed only for the names in the last column, so a colourised run would
  have emptied that column rather than turning a kill into a survival.
- **Unreadable exit code.** `-n0` rather than `-p no:xdist`, which exits 4 against this repo's
  `addopts`. Any exit outside `{0, 1}`, or any run yielding no parseable counts, is UNREADABLE
  and never a survival. The exit code is read off the `CompletedProcess`, never from a shell
  after a pipe, so `pytest -q; echo $?` cannot report `echo`'s status in its place.
- **Did-not-compile.** `compile()` on the mutated source before pytest is invoked, so a
  `SyntaxError` is reported as itself instead of arriving as a collection `ERROR`.
- **Not-applied.** Each anchor must match exactly once; 0 or 2 is NOT-APPLIED and the mutation is
  skipped rather than guessed at. All thirteen matched once.
- **Anchor-missed.** The target is read with `read_text`, whose universal-newline translation
  gives LF in memory whatever the working tree holds, so a `\n` anchor matches against this
  repo's CRLF checkout. It is written back with `newline=""` and restored from the same string.
  **This left a trace worth naming:** the restored files are byte-identical in content and LF on
  disk, so `git status` reported both as modified with an empty `git diff --stat`. They were
  restored with `git checkout --`, and the tree is byte-identical to `HEAD` for everything this
  task did not intend to change.
- **Baseline-drifted.** The restored tree is re-run and its pass count compared with the
  baseline. `RESTORED exit=0 {'passed': 139} drifted=False`.
- **Encoding.** `PYTHONIOENCODING=utf-8` in the child env, output captured as **bytes** and
  decoded here with `errors="replace"`. This is the one that could have bitten, and the position
  is measured rather than assumed. Census over the nine files the harness reads or mutates:

      src\sync\route\templates.py              none
      src\sync\route\matrix.py                 none
      tests\test_edit_primitive_declines.py    none
      tests\test_property_at.py                none
      tests\test_parameter_omit.py             none
      tests\test_parameter_rename.py           none
      tests\test_route_defects.py              [31, 63, 69, 72]
      tests\test_migration_rules.py            none
      tests\test_tier_zero_reach.py            none
      tests\test_shipped_conformance.py        none

  `tests/test_route_defects.py` carries `é` and `café` **on purpose** -- it is the file that
  pins the byte-column defect, and `CLAUDE.md` records that every other fixture here is ASCII,
  which is why that defect survived a green suite. Its lines 31, 63, 69 and 72 are inside the
  three tests M3 and M4 were most likely to break, so a run that killed those mutations by
  breaking those tests would have had pytest render accented source back through the pipe. It
  did not happen -- M3 and M4 each killed exactly one test, in the ASCII file -- but it was one
  assertion away, and the harness would have returned exit 1 with no output at all rather than a
  verdict.

## Next tasks this produced

Two, both outside this brief's file list.

1. **`LiteralSwapRemediator.can_handle` should test `raw["model_id"]` as well as
   `raw["replacement"]`, or `propose` should raise `CannotPatch` when `model_literal_swap`
   returns no rule.** That is row 12: the gate accepts a change the rule builder cannot serve,
   and the result is an empty diff that means "already migrated". `src/sync/remediate/` is
   outside this brief. The choice between the two fixes is a decision about that module's
   decline contract: `can_handle` returning `False` lets the cascade try the next tier in the
   same attempt, while `CannotPatch` records the reason. `PropertyOmitRemediator`'s module
   docstring argues for the second and its argument transfers.

2. **A computed literal key reads as absent to both position-scoped primitives, and nothing says
   so.** `create({ ['receipt_email']: 'x' })` gives `argument_is_literal_at` -> `False` and
   `omit_argument_at` -> the source unchanged, which `PropertyOmitRemediator` reports as "the
   code already agrees with the vendor". It does not. The cause is `_pair_part`, which compares
   `node.text().strip("\"'")` against the key name, and a `computed_property_name`'s text is
   `['receipt_email']` -- brackets survive the strip. `_declared_keys` handles exactly this shape
   and its docstring records that missing it produced the silent last-wins duplicate the guard
   exists to prevent, so the asymmetry is between two functions in this file rather than a gap
   nobody has met.

   **Not fixed here, deliberately.** The obvious repair is to unwrap computed names in
   `_pair_part`, and `_pair_part` has four call sites: two key comparisons, one *value*
   comparison in `_objects_naming`, and the key comparison `rename_parameter` uses to find the
   node it rewrites. That last one is the problem. `rename_parameter` replaces the node
   `_key_node` returns, which for a computed key is the whole `['budget_tokens']`, and its
   quote-preservation rule reads `text[0]` -- which is `[`, so the replacement would be written
   bare and `{ ['budget_tokens']: 8 }` would become `{ max_tokens: 8 }`. That is a form change
   inside a diff whose only claimed purpose is a rename, which this module declines twice
   already. Making the key comparison see computed names without making the rename rewrite them
   is a real design decision in the module whose correctness is established by construction, and
   this brief says not to make one without a test proving the current behaviour wrong. The test
   would be easy; the fix is not, and the current behaviour costs an attempt rather than a
   patch.

## Fixtures

None added. Every input in `tests/test_edit_primitive_declines.py` is an inline source string, as
in the four existing test files for this module, and the one clone the remediator tests need is
built in `tmp_path`. It is written with `write_bytes` rather than `write_text`: the first run of
`test_a_deprecation_with_no_model_id_is_accepted_and_then_produces_nothing` failed because
`write_text` expands `\n` to `os.linesep`, so the file the remediator read with `read_bytes`
carried CRLF and the byte-for-byte assertion caught it. That is the round trip
`literal_swap.propose` avoids for exactly this reason, reproduced in a test fixture within an hour
of reading the comment that explains it.

## The dead-links baseline entry still describes a violation

`src/sync/route/templates.py:omit_property_at` stays. Nothing in `src/` calls it, and this task
added tests rather than wiring. All three reasons the entry gives are unchanged, and this task
measured the first two rather than inheriting them:

- **It counts lines from one where `omit_argument_at` counts from zero.** Both tested here:
  `omit_property_at(..., line=1, ...)` addresses the first line, `argument_is_literal_at(...,
  line=0, ...)` addresses the same one.
- **It answers two ways where the remediator needs three.** Rows 2, 3 and 5 above are the
  measurement: two distinct "cannot establish" conditions and one "already correct" all return
  the input.
- **It has no spread guard.** `omit_argument_at` and `argument_is_literal_at` both refuse a
  container holding a `spread_element`; `omit_property_at` has no such check, and
  `tests/test_property_at.py::test_a_spread_is_not_mistaken_for_the_property` pins that it
  declines only because a spread carries no key -- not because it noticed one.

## Which scheduler each measurement used

| Measurement | Scheduler | Result |
|---|---|---|
| Coverage before, at `6b01f04` | `-n auto` (12 workers, the `addopts` default) | 12 missing, 95%, 2639 passed / 4 skipped |
| Coverage after | `-n auto` | 6 missing, 97%, 2651 passed / 4 skipped, exit 0 |
| Unreachability probe, both runs | `-n auto` | 2651 passed / 4 skipped, exit 0, NEVER-HELD |
| Mutation harness, all 15 runs | `-n0` | baseline and restored 139 passed, exit 0 |
| Gate 1 | `-n auto` | see below |

`-n0` for the harness because a mutation run wants determinism and a 139-test subset takes 10.7 s
serially; `-n auto` for anything measured over the whole suite, because that is what `addopts`
gives and what the before-figure in the brief was taken with. `-p no:xdist` was not used anywhere:
it exits 4 against this repo's `addopts` and would have been read as UNREADABLE, which is the
verdict the harness reserves for exactly that.

## Gates

All four run unpiped, exit codes read from the process rather than from a shell after a pipe.

| Gate | Result | Exit |
|---|---|---|
| `uv run pytest -q` | 2651 passed, 4 skipped in 261.51s (`-n auto`) | **0** |
| `uv run python scripts/lint_encoding.py src scripts tests` | no output | **0** |
| `PYTHONIOENCODING=utf-8 uv run lint-imports` | `sync.core depends on nothing KEPT` -- 95 files, 201 dependencies, 1 kept, 0 broken | **0** |
| `uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt` | no output | **0** |

The fourth is the one that matters here: it fails on a baseline entry that no longer describes a
violation, and it passed with `src/sync/route/templates.py:omit_property_at` still in the file.
