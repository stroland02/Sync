# Eleven declines in the Speakeasy reader, one of which was a wrong binding

M3-W111. `symbols_speakeasy.py` was the fourth and last symbol reader to be read statement by
statement, and the fourth to hold something a coverage number could not have suggested. Eleven
statements were unexecuted by the whole suite. Six are reachable and now covered; five are
unreachable and are argued below with a whole-suite probe rather than with reasoning.

**One defect, and it is the same defect M3-W91 found in the Stainless TypeScript reader.** This
grammar ends a `string_fragment` at every escape sequence, and `_string_literal` returned the first
fragment. So `pathToFunc("/v4/aliases\/{idOrAlias}")` was read as the route `/v4/aliases` — which is
not a truncated version of anything, it is **the route a different method of the same resource
sends**. `aliases.getAlias` and `aliases.listAliases` both bound to `GET /v4/aliases`, and
`unknown_to_spec` could not contradict it because that route is one the specification declares. The
same reduction reads the verb, so `method: "\u0047ET"` was read as `ET`.

The docstring made the claim the code did not implement — "an escape this does not interpret cannot
be mistaken for one" — which is word for word the sentence M3-W91 found false in `_plain_route`. It
is now true here, for the same reason and by the same fix.

## Coverage, before and after

Both figures come from the same command over the whole suite, default scheduler (`-n auto` from
`addopts`, "bringing up nodes" in the output):

    uv run pytest -q --color=no --cov=sync.signals.generated.symbols_speakeasy \
        --cov-report=term-missing

Before, at `6b01f04` (`origin/main`):

    src\sync\signals\generated\symbols_speakeasy.py   243   11   95%
      208, 214-215, 282, 286, 302, 333, 337, 385, 392, 532
    2641 passed, 2 skipped in 139.04s

The brief quoted 2639; `origin/main` had advanced by two tests. The eleven missing statements are
exactly as the brief quoted them.

After:

    src\sync\signals\generated\symbols_speakeasy.py   245    5   98%   309, 344, 392, 399, 539
    2655 passed, 2 skipped in 131.84s

Two statements were added — the escape guard — so the line numbers move by seven from
`_string_literal` onward and not at all before it. The five that remain are the five judged
unreachable: `302→309`, `337→344`, `385→392`, `392→399`, `532→539`.

## The eleven

**Every one of them is in the extraction path.** M3-W96 established that `_comparable` is called
only from `report_extraction` while `operation_for_symbol` builds its `OperationRef` from
`ExtractedOperation.path` verbatim, so a decline in the comparison path costs a measurement and one
in the extraction path costs a binding. `_comparable` here is two statements and both were already
covered: **not one of the eleven costs only a measurement.** Where the cost column says "nothing",
that is because the statement skips a construct rather than an operation.

| # | Statement | Input that reaches it | Is declining right? | What the caller observes | Cost |
|---|---|---|---|---|---|
| 1 | `208` — `_specifier_target`, an `import_statement` stating no `source` | `import aliasesGetAlias = require("../funcs/aliasesGetAlias.js")`. Valid TypeScript, parses with `has_error=False`, and its only named child is an `import_require_clause` | Yes — but **redundant in the forward direction.** The same form states no `import_specifier` either, so `_read_module` binds no local name however the specifier resolves. M5 confirms it: making the specifier resolve changes no symbol | **Nothing.** The delegation resolves to no module and the method contributes no symbol | Binding, in principle. Nothing today: the committed tree contains no `require(` at all |
| 2 | `214` — `except ValueError` | Three expressions inside the block raise it, and they are not one condition. See the section below | Yes for the two boundary cases. It also swallows an internal path fault, and cannot say which arrived | **Nothing.** The import is not recorded | Binding — a mount edge, and every operation under the resource it named |
| 3 | `215` — `return None` | The same inputs; this is the answer the handler gives | Yes — a specifier this rule cannot name is not a module in this checkout. **And it costs the decline as well as the edge**: 503's `elif imported is not None` reports a mount only where the source named a module, so an unresolvable specifier loses six symbols and reports nothing, where an in-tree file that is merely absent reports them | **Nothing at all**, and that is the finding. Six symbols and no record | Binding, plus the record of it |
| 4 | `282→287` — `_string_literal`, the node is not a `string` | `pathToFunc(\`/v4/aliases/${idOrAlias}\`)`, or a `method:` value that is an identifier rather than a literal | Yes. Reading a template's fragments answers `/v4/aliases/` — the parameter segment dropped rather than templated, which is the wrong-route failure `_helper_path`'s docstring refuses | **Nothing.** `aliases.getAlias` is absent from the map | Binding |
| 5 | `286→293` — `_string_literal`, a `string` with no `string_fragment` child | `pathToFunc("")`, or `method: ""` | Yes; the alternative is a symbol bound to the empty path, occupying the key the real operation would take. Forward-redundant against returning `""` — both callers guard on truthiness, which is why M3 survives and only M3′ kills | **Nothing.** The symbol is absent | Binding |
| 6 | `302→309` — `_helper_path`, a `call_expression` stating no `function` or `arguments` | **None.** Both are required fields, and tree-sitter's error recovery inserts a MISSING node for a required field rather than omitting it | Unreachable, so the question does not arise | — | None |
| 7 | `333→340` — `_builder_verb`, an object member that is not a `pair` | A `spread_element`, a `shorthand_property_identifier`, a `comment` or a `method_definition` directly inside `_createRequest`'s object literal. Valid TypeScript. Vercel emits none there — it emits a shorthand `context` in the adjacent `_do` object, which the `_createRequest` check at 333 declines before this loop sees it | Yes, and it is not a decline of the operation: the loop continues and the verb is still read. **Redundant in the forward direction** — deleting it makes 344 the statement that skips those members, measured | **Nothing changes.** The symbol survives with its verb | None |
| 8 | `337→344` — `_builder_verb`, a `pair` stating no `key` or `value` | **None while 340 stands.** A `pair` always states both, even under error recovery. With 340 deleted every non-pair member arrives here — `spread_element`, `shorthand_property_identifier`, `comment` and `method_definition` all answer `None` for `key` — and the statement becomes covered | Unreachable behind 340 | — | None |
| 9 | `385→392` — `_read_class`, a `class_declaration` stating no `body` | **None.** `body` is a required field; `class Foo extends ClientSDK` with no braces produces no `class_declaration` node at all | Unreachable | — | None |
| 10 | `392→399` — `_read_class`, a `method_definition` stating no `name` | **None.** `name` is required; even `class A { () {} }` yields a MISSING `property_identifier` | Unreachable | — | None |
| 11 | `532→539` — the breadth-first walk, a queued key absent from `classes` | **None.** Every queued key comes from `roots ⊆ mounts.keys() ⊆ classes` or from `mounts[key].values() ⊆ candidates ⊆ classes` | Unreachable. M3-W91 reached the same verdict on the identical guard in both Stainless flavours and named `symbols.py:307` | — | None |

## The defect, and what it cost

`test_a_route_literal_carrying_an_escape_is_declined_whole` was written first and failed on the
route it produced rather than on its absence:

    assert 'aliases.getAlias' not in {..., 'aliases.getAlias': ('GET', '/v4/aliases'),
                                           'aliases.listAliases': ('GET', '/v4/aliases'), ...}

Two symbols, one route, and the route is real. That is the difference from M3-W91's case, where the
truncated route `/v1/a` was declared by nothing: here the truncation lands on a route the vendor
publishes, so every check this module has stays silent. `unknown_to_spec` is empty. `covered_count`
does not move — the reduced key was already reached by `listAliases`. `extracted_count` does not
move either, because the symbol is still produced. Nothing in the pipeline distinguishes the two
symbols, and a vendor change to `GET /v4/aliases` would raise a finding against every call site that
calls `getAlias`, which sends `/v4/aliases/{idOrAlias}` and is unaffected.

The verb case is the milder half: `method: "\u0047ET"` read as `ET`, and `(ET, /v4/aliases/{…})` is
a key no specification declares, so the cross-check would have reported it. Both are fixed by the
same two lines.

The fix declines the literal whole, which loses the operation. That is a false negative and the
right trade, for the reason `_route`'s own docstring gives and M3-W91 gave before it: a wrong route
resolves a call site to an operation the customer never calls, and a lost one resolves to nothing.

## It is the same defect, not a similar one, and the history says why the fix did not carry

**Same defect, and the evidence is that it is the same code.** `git show eb50e91` against
`git show 80e2e08^` puts the two helpers side by side, and apart from the function name and the word
`route` where the other says `value` they are byte-identical:

```python
def _plain_route(node: Node, source: bytes) -> str | None:      # symbols_typescript.py, pre-fix
    """A route written as a plain string literal.

    The fragment rather than the quoted text, so an empty string reads as absent rather than as a
    route, and an escape this does not interpret cannot be mistaken for one.
    """
    if node.type != "string":
        return None
    for child in node.children:
        if child.type == "string_fragment":
            return _text(child, source)
    return None
```

`_string_literal` carried that body and **that same false sentence**. So this is not two authors
making the same mistake against the same grammar; it is one function, copied, and the copy kept the
docstring claiming the protection the body does not implement.

**Why the fix did not carry: the copy predates it by nine hours, on another branch.**

| Commit | When | What |
|---|---|---|
| `eb50e91` | 2026-07-29 06:39 | `feat: read the symbol map out of a Speakeasy SDK, the third flavour` — introduces `_string_literal`, copied from `_plain_route` as it then stood |
| `80e2e08` | 2026-07-29 15:54 | M3-W91's fix — adds the escape guard to `_plain_route` and `_tagged_route`, and corrects the docstring |

`git merge-base --is-ancestor 80e2e08 eb50e91` is false: the fix is not in the new reader's history.
Nothing was ignored and nobody skipped a step. The two branches were open at once, the copy was
taken from the version that was current when it was taken, and there is no mechanism in this
repository by which a fix to one reader's literal handling reaches the other's.

**The wrong route was different in each, and this one is the worse of the two.** M3-W91's input was
`'/v1/aAb'`; `_plain_route` read `/v1/a` and `_tagged_route` read `/v1/ab/{x}`. Neither is a
route its specification declares. Here the input is `pathToFunc("/v4/aliases\/{idOrAlias}")`, the
truncation is `/v4/aliases`, and that **is** a route the specification declares — it is the one
`aliases.listAliases` sends. So where W91's wrong route was at least the kind of thing
`unknown_to_spec` exists to report, this one lands inside the set the cross-check compares against
and provably cannot be reported by it.

### This is a finding about the design, not only about the module

The Speakeasy module's docstring argues at length for what is shared and what is not. Shared, by
import: `ExtractedOperation`, `ExtractionReport`, `UnrecognisedSdkShape`, `_route` and
`read_spec_operations`. Deliberately duplicated: the breadth-first walk, `_source_files`, and — named
explicitly — "the tree-sitter plumbing: `_walk`, `_text`, `_module_key` and relative-specifier
resolution". The reason given is that

> what differs underneath them is the whole content of each rule: what a class is, what a mount is,
> how a class is identified, and now whether an operation is even readable from one file. A shared
> walker parameterised over four such differences is a framework for a population of three.

**That argument is right about the walker and does not reach this helper, and the gap is what the
defect grew in.** Reading a string literal is not one of the four differences the docstring
enumerates. It has no generator-specific content at all — `_plain_route` and `_string_literal` were
*the same function*, which is the strongest possible evidence that nothing about Speakeasy versus
Stainless bears on it. It is a fact about tree-sitter's model of a string literal, and it is shared
by exactly the two rules that use tree-sitter.

So the duplication argument priced generator differences and did not price parser facts. The cost it
did not name is this: a parser fact discovered once has to be discovered again per reader, and until
it is, the second reader ships the wrong answer. `_route` is the precedent for the other direction —
it was imported rather than reimplemented because "that decision was made and measured on the Python
flavour", and an escape guard is a decision made and measured on the TypeScript one by exactly the
same test.

**The remedy is not the shared walker the docstring refuses.** It is one function, over one node
type, with no parameters and no rule-specific behaviour, used by the two readers that parse
TypeScript. That is stated as the third next task below rather than taken here, because the module
it would live in is shared by three readers and this task's licence was a defect fix.

### Whether the other three readers have it: no, and for two different reasons

| Reader | Where its route string comes from | Exposed? |
|---|---|---|
| `symbols.py`, `stainless-python` | `ast.Constant.value` | **No.** The value is already decoded, so the flavour reads `/v1/aAb` as `/v1/aAb` and binds it correctly. Established and pinned by M3-W97's `test_a_route_literal_carrying_an_escape_is_read_decoded_rather_than_truncated` |
| `symbols_typescript.py`, `stainless-typescript` | tree-sitter `string_fragment` | Was. Fixed by M3-W91 |
| `symbols_speakeasy.py`, `speakeasy-typescript` | tree-sitter `string_fragment` | Was, from the same source text. Fixed here |
| `sync.signals.twilio.symbols` | `spec: dict[str, Any]`, an OpenAPI document already parsed | **No, structurally.** It parses no source; `grep -n "tree_sitter\|ast\.\|string_fragment"` over both hand-written maps returns nothing. JSON decoding resolves escapes before the map sees a character |
| `sync.signals.stripe.symbols` | the same | **No, structurally** |

The population that can hold this defect is therefore **exactly the readers that parse source with
tree-sitter**, and there are two of them. Both have now had it, and both had it from the same
function. That is a rate of two out of two, which is the reason the third next task is worth doing
rather than a coincidence worth recording.

## Line 214's block: three expressions raise `ValueError`, and one of them is internal

The block is one line long and it is not one condition:

```python
try:
    return _module_key((path.parent / specifier).resolve(), root)
except ValueError:
    return None
```

`_module_key` is `path.relative_to(root).with_suffix("").as_posix()`. Measured, each expression
attempted separately against a real checkout root:

| Expression | Input | Raises | Boundary or internal |
|---|---|---|---|
| `.resolve()` | a specifier carrying a NUL byte, `"./a\x00b.js"` | `ValueError: stat: embedded null character in path` | Boundary — vendor source bytes |
| `relative_to` | `"../../../outside.js"`, resolving above the checkout root | `ValueError: '…\outside.js' is not in the subpath of '…'` | Boundary. This is the case the handler was written for |
| `relative_to` | `"./C:/x.js"`, which `Path` reads as the drive-relative `C:x.js` | the same `ValueError` | Boundary |
| `with_suffix("")` | `sdk/sdk.ts` importing `".."`, which resolves to the checkout root **itself** | `ValueError: WindowsPath('.') has an empty name` | **Internal.** `relative_to` succeeded and answered `.`; the fault is in this rule's own path arithmetic, over a path that is inside the checkout |

**So yes: an internal fault of the same type reaches the caller as an absent answer.** The last row
is not a specifier naming something outside the tree — it names the tree — and the handler answers
`None` for it exactly as it does for the first three. Both are pinned, by
`test_a_mount_imported_from_outside_the_checkout_is_dropped_without_a_record` and
`test_a_specifier_resolving_to_the_checkout_root_declines_the_same_way`, which assert the same
outcome from the two different faults.

**`pydantic_core.ValidationError` cannot arrive here, and that was established rather than assumed.**
It subclasses `ValueError`, so the question is real, and the answer is that no model is constructed
inside the block: the three expressions are `PurePath.__truediv__`, `Path.resolve` and the three
calls in `_module_key`. No pydantic type is reachable from any of them, and nothing else in this
module constructs one at all.

**What it costs is narrowness rather than a wrong answer.** For all four inputs `None` is the
answer a reader would want; the module boundary is real in every case. What the handler cannot do is
say which, and the consequence is the row-3 finding: an unresolvable specifier drops the mount's
decline record too, because 503 needs `imported is not None` to name the missing file.
`symbols_typescript.py` carries the identical `try`/`except` at its lines 198-201, so this is a
package-wide property and not this module's drift.

## Whether the declines reach the channel M3-W100 added: not the ones that matter

`ExtractionReport.unreadable` records two kinds, both stated in `symbols.py`'s own docstring: a
mount whose target this checkout does not carry, and a delegation reaching no request module. Per
statement:

| Statement | Reaches `unreadable`? |
|---|---|
| `208`, `282→287`, `286→293` (a request module is present and its route is unreadable) | **Only as an artifact of the fixture.** See below |
| `214-215` (an unresolvable specifier) | **No, ever.** 503 requires `imported is not None` |
| `333→340`, and the five unreachable statements | Not applicable — nothing is lost |

**The three route declines look visible in the committed tree and are not.** In the twenty staged
files every method delegates to `unwrapAsync`, imported from `../types/fp.js`, which the fixture
does not include. So `absent` is non-empty for every method whatever else is wrong with it, and a
method that loses its route still records

    speakeasy-typescript: sdk/aliases: Aliases.getAlias reaches no request module
      -- 'types/fp' are not in this checkout -- so it contributes no symbol

which names the wrong file. Stage a stub for `types/fp.ts` — a complete checkout, for the purposes
of the delegation walk — and the record disappears entirely:
`test_an_unreadable_route_in_a_staged_request_module_is_recorded_nowhere` asserts that the decline
tuple is *equal* to the one from the unmutated tree. Mutation M7 is what makes that non-vacuous.

The cause is structural and is the generator's, not an oversight. Speakeasy states the route in
another module, so `_Module.route is None` is what "this file builds no request" and "this file
builds a request whose route I could not read" both reduce to — and the first is every other file in
the SDK. The Python and TypeScript flavours separate them, and both record
`… with no route this rule can read`, because there the route is in the file that declares the
method.

**Two numbers do move, and neither names the loss.** `extracted_count` falls by one, and
M3-W100's `unreached` gains the declared operation the lost symbol used to reach —
`test_the_loss_moves_two_numbers_and_names_itself_in_neither` asserts exactly
`{("GET", "/v4/aliases/{idOrAlias}")}` as the difference. But it arrives as one entry among 345,
spelled as the specification spells it and carrying no reason, indistinguishable from the 344 the
fixture's truncation already loses. **And there is no cross-check to catch the total**: a Speakeasy
`workflow.yaml` declares its inputs and not its size, so `endpoint_count` is `None` for every vendor
under this generator — `manifest._parse_speakeasy` never sets it, and
`test_a_generator_publishing_no_endpoint_count_leaves_the_denominator_unchecked` already pins that.
The cross-check the Stainless flavours have does not exist here.

**No second channel was built.** The brief is right that a fourth convention would be worse than any
of the three, and the repair is two lines inside this module rather than a channel: `_helper_path`
and `_builder_verb` already know whether the construct they were reading was present, which is
exactly what `symbols_typescript.py`'s `unread_helper` carries. That is a change to what this module
emits, so it is the next task and is stated as one below.

## Where it agrees with the other three readers, and where it drifted

**One genuine drift, now closed: the escape.** Three readers meet the same input and gave three
answers. `symbols.py` reads `ast.Constant.value`, which is the *decoded* string, so the Python
flavour binds the operation correctly. `symbols_typescript.py` declines the literal whole, since
M3-W91. This module truncated it and produced a wrong binding — the worst of the three, and it was
the only one of the three whose behaviour contradicted its own docstring.

M3-W97 recorded a steer on this that is worth answering rather than ignoring: "anyone later tempted
to align the two should align towards decoding rather than towards declining." **This aligns towards
declining, and the reason is that decoding is not available under this parser.** tree-sitter reports
an `escape_sequence` as a sibling node and gives no decoded value; producing one means implementing
JavaScript string-escape semantics — `\/`, `\n`, `\xNN`, `\uNNNN`, `\u{…}`, line continuations —
inside a symbol reader, and `_text`'s strict decode exists precisely so that this module does not
reinterpret vendor bytes. So the population is now two declines and one decode, the decode is still
the better answer, and it stays available only where the parser already did the work.

**One difference is a generator fact and makes the module weaker: no endpoint count.** Covered
above. It is the reason a silent decline is harder to notice here than in either Stainless flavour,
not easier.

**One difference is a generator fact and is deliberate: the mount resolution refuses a name match.**
`_declaring` in the TypeScript flavour and the mount resolution here both leave an unresolved name
unresolved. M3-W104 named these as the package's two real name refusals and this task did not touch
either. `test_a_speakeasy_getter_constructing_a_class_it_never_imported_is_not_a_mount` already pins
it, and M4′ and M9 both kill it, so it is held rather than merely described.

**One difference is not drift and is worth stating so nobody chases it: the unreachable walk guard.**
`532` here, `307` in `symbols.py`, and its counterpart in `symbols_typescript.py` are the same
statement with the same verdict, reached independently by M3-W91 and by this task. Three modules,
three tasks, one answer, and none of the three was reached by calling into the walk with a
fabricated queue.

## The parameter reduction's pinned inertness still holds

Untouched, and asserted rather than assumed: `test_the_speakeasy_reduction_is_inert_rather_than_unreached`
and `test_the_speakeasy_reduction_changes_no_verdict` both pass on the final tree, in the whole-suite
run and in the mutation harness's baseline of 241. The escape guard is inside `_string_literal`,
which the reduction does not reach, and no fixture route carries an escape, so nothing the reduction
sees changed. M4′ killing both of them is the evidence that they still bear on this module: a
mutation that stops the verb being read stops the reduction having anything to reduce.

## Unreachable and redundant, separated

The brief asked for the distinction and it comes out three ways here.

**Unfalsifiable by any fixture — four statements guarding a required grammar field.** `309`, `344`,
`392` and `399` each test whether `child_by_field_name` answered `None` for a field the TypeScript
grammar declares required. It never does: tree-sitter's error recovery inserts a MISSING node rather
than omitting the field. Measured two ways. Thirty-nine hand-written pathological sources produced
`None` for exactly one field, `import_statement.source`, which is the one that is genuinely
optional — that is statement 1 of the table and it is now covered. And
`test_the_four_guards_against_an_absent_required_field_cannot_fire` sweeps every committed Speakeasy
file truncated at every 64th byte: 1,600-odd parses of real vendor source in every state of
incompleteness, 386 MISSING nodes produced, and not one absent required field. That is held as a
test rather than reported as reasoning because it goes red the day a tree-sitter upgrade changes
error recovery, which is the day those four guards would begin to matter.

**Unreachable by construction — one statement.** `539`. Argued above; no test reaches it and none
should.

**Redundant in the forward direction — three statements, none removed.**

- `340` is subsumed by `344`. Deleting it leaves the suite green and, measured directly, makes `344`
  execute: with the guard deleted the module reports 243 statements missing `156, 309, 363, 390,
  397, 475, 517, 537, 578` — the pair guard, at `342` after the deletion, is no longer among them.
  The two are one guard written twice and only the first can fire.
- `208` is subsumed by `_read_module`'s search for `import_specifier` children. M5 makes the
  specifier resolve and no symbol moves, because the require form binds no local name either way.
- `293` is subsumed by both callers' truthiness guard: returning `""` and returning `None` are the
  same answer to `_helper_path` and to `_builder_verb` alike, which is why M3 survives. It is
  load-bearing against the *other* wrong answer — reading the quoted text, which is truthy — and M3′
  kills that.

None was removed. Each states the loop's assumption at the point the loop makes it, which is the
same reason M3-W91 and M3-W95 kept theirs, and in the `340`/`344` case removing either would leave
the surviving one looking like the discriminating check when it is not.

## Mutation table

Harness at `%TEMP%\w111_mutate.py`, not committed. It runs

    uv run pytest -q --color=no -p no:randomly -n0 --no-header -p no:cacheprovider

over twelve test files — every file in `tests/` that touches this generator — for a baseline of
**241 passed**. Scheduler `-n0` throughout. Each mutation string must match exactly once, the
mutated text is `compile()`d before pytest is invoked, the verdict is read from the summary counts
rather than from line prefixes, and the file is restored from the original *bytes* after every run.
Baseline asserted green at 241 before the first mutation and after the last:
`restored baseline: exit 0, counts {'passed': 241}`.

**Taken before `origin/main` was merged, and still describing the tree that lands.** The merge
(`d0df4d7`) added two test files, `tests/test_core_distribution.py` and
`tests/test_severity_vocabulary.py`, and changed nothing under `src/sync/signals/` —
`git diff --name-only 827eee0 HEAD -- tests/ src/sync/signals/` is exactly those two names. Neither
is in the blast radius, so the baseline of 241 and every verdict below are unchanged by it. The
whole-suite figures elsewhere in this report were re-taken after the merge and are not.

| # | Mutation | Verdict | Tests killed |
|---|---|---|---|
| M1 | the escape guard is removed, so a split literal reads its first fragment again | KILLED, 3 failed | `…route_literal_carrying_an_escape_is_declined_whole`, `…verb_literal_carrying_an_escape…`, `…fourteen_other_symbols_are_the_control…` |
| M2 | the `string` type check accepts a `template_string`, so a template's fragment reads as a route | KILLED, 3 failed | `…route_built_by_interpolation_is_not_read_as_a_route`, `…unreadable_route_in_a_staged_request_module_is_recorded_nowhere`, `…loss_moves_two_numbers…` |
| M3 | an empty route literal is accepted — `if found:` becomes `if found is not None:` | **SURVIVED**; the mutation is inert, see below | — |
| M3′ | the no-fragment case reads the quoted text instead of declining | KILLED, 1 failed | `…empty_route_literal_reads_as_absent_rather_than_as_a_route` |
| M4 | the non-pair guard is deleted | **SURVIVED**; subsumed by `344`, which then executes | — |
| M4′ | the non-pair guard is inverted, so only non-pairs are read | KILLED, 38 failed | 38 across the new file and five existing ones, including `…request_object_carrying_members_that_are_not_pairs_still_yields_its_verb` and both reduction-inertness tests |
| M5 | a source-less import falls back to the first string in the statement | **SURVIVED**; `208` is subsumed, see below | — |
| M6 | the `ValueError` handler answers the raw specifier rather than declining | KILLED, 1 failed | `…mount_imported_from_outside_the_checkout_is_dropped_without_a_record` |
| M7 | a delegation target present in the checkout but stating no route is recorded as absent | KILLED, 2 failed | `…unreadable_route_in_a_staged_request_module_is_recorded_nowhere`, `…loss_moves_two_numbers…` |
| M8 | the Speakeasy flavour reports nothing unreached | KILLED, 3 failed | `…unreached_key_makes_every_operation_behind_it_unreached`, `…declared_operations_no_symbol_reaches_are_counted_per_artifact`, `…loss_moves_two_numbers…` |
| M9 | the mount decline is recorded whether or not the source named a module | KILLED, 3 failed | `…mount_imported_from_outside_the_checkout…`, `…getter_constructing_a_class_it_never_imported_is_not_a_mount`, `…specifier_resolving_to_the_checkout_root…` |
| C1 | control: an unbalanced parenthesis | DID-NOT-COMPILE (`'(' was never closed`), pytest never invoked | — |

**Twelve of the fourteen new tests are killed by at least one production mutation.** The two that
are not read tree-sitter rather than `src/`, so no mutation could kill them, and their non-vacuity
was established the other way — by pinning the wrong answer and watching each report the real one:

| Test | Wrong pin | Reported |
|---|---|---|
| `…four_guards_against_an_absent_required_field_cannot_fire` | `absent_fields == {("pair", "key")}` | `assert set() == {('pair', 'key')}` |
| the same test | `missing == 0` | `assert 386 == 0` |
| `…non_pair_member_has_no_key_which_is_why_the_pair_guard_is_unreachable` | the assertion inverted | `assert (None is not None)` |

### The three survivals, and where the fault was in each

**The brief's ordering held for all three, and in none of them was the production code wrong.** That
is now the eleventh task in a row on this project to report the fault outside it.

**M3: the mutation was at fault.** It relaxes `_helper_path`'s truthiness guard so an empty route
would be accepted — but `_string_literal` answers `None` for an empty literal, not `""`, so the
relaxation has nothing to admit. M3′ is the mutation that reaches the statement, and it kills.

**M4 and M5: the code is genuinely redundant**, in the same sense M3-W95 found for `twilio:142` and
`stripe:143-144`. Both are recorded in the section above with the clause that subsumes each. Neither
is a test weakness and no fixture can make either falsifiable, so nobody should go looking for one.

### False-verdict modes

Guarded by construction, and which of them actually fired:

| Mode | Guard | Fired? |
|---|---|---|
| A colourised summary defeating a `FAILED ` scan | `--color=no`, and the verdict comes from the summary counts | No |
| A non-1 exit with no `FAILED` lines | any exit outside {0, 1} is UNREADABLE | No. Every run exited 0 or 1 |
| A `SyntaxError` arriving as `ERROR` | every mutation is `compile()`d first | Yes — control **C1**, reported without pytest being invoked |
| Exit 0 at a passing count other than the baseline | UNREADABLE, because the test set moved | No |
| Not-applied: an anchor absent or ambiguous | every anchor must match exactly once | NOT_APPLIED_FIRED |
| Anchor-missed: an LF anchor against a CRLF file | `symbols_speakeasy.py` **is** CRLF in the working copy, so every multi-line anchor is translated to `\r\n` before matching | ANCHOR_MISSED_FIRED |
| A decode error on the reader thread | `PYTHONIOENCODING=utf-8` in the child environment, `errors="replace"` harness-side | No. This module and the twelve test files are pure ASCII |
| A skipped test reading as a pass | the pass count is compared to the baseline, not just the exit code | No |
| A second harness instance mutating the same file | none, by construction — see below | **Yes**, on the probe run |
| A mutation captured by a commit taken during the window | none, by construction — see below | **Yes**, in `827eee0` |

ANCHOR_MISSED_PROSE

### Two more false-verdict modes, neither of them in any brief, both hit on this task

Both are about the *harness's* relationship to the working tree rather than about reading pytest's
output, which is why no amount of exit-code discipline catches either.

**A second harness instance, mutating the same file.** A probe run was interrupted mid-flight and a
second was started later against the same module. Both were alive at once. Each restores the file
from its own copy of the original bytes after every probe, which is correct in isolation and
guarantees corruption in pairs: the file was observed carrying **two** markers simultaneously,
`P344` and `P392`, and one harness reported `NOT-APPLIED: anchor occurs 0 times` because the other
had already rewritten the region it was looking for.

The `NOT-APPLIED` guard is what surfaced it. A harness with only KILLED and SURVIVED would have
recorded the interleaved runs as ordinary verdicts. **Every verdict from both runs was discarded**
and the probe table below is a single clean run with nothing else alive — checked by command line,
not by assumption, because `python.exe` on this machine is also every other worktree's test runner.

**A mutation committed by a concurrent snapshot.** While a probe held the module mutated, the work
in progress was committed. `827eee0` therefore carries

```diff
     body = node.child_by_field_name("body")
     if body is None:
-        return read
+        raise AssertionError("P392 reached")
```

in `src/`, and **the whole suite stayed green through it** — 2,671 passed. That is the probe's own
result arriving by accident: nothing reaches that statement, so nothing could notice a raise there.
Reverted in `65229ba`, which restores the module byte-identical to `a3306a4`.

The lesson is specific and worth stating in those terms: **a mutation harness makes the working tree
temporarily untrue, and every green signal over that window is meaningless in both directions.** A
suite that passes proves nothing about the committed content, and a `git add` during the window
commits a lie the suite is structurally unable to report. The guard is to restore before committing
and to diff the mutated file against its last good revision rather than trusting the harness's
`finally` — the `finally` ran, and it ran after the commit.

Each guard's `continue` or `return` replaced by `raise AssertionError`, whole suite, default
scheduler (`-n auto`), on the merged tree. A green run means no test in this repository reaches the
statement; a red one would name what does. Harness at `%TEMP%\w111_probes_full.py`, not committed:
the mutated text is `compile()`d first, each anchor must match exactly once and is translated to
CRLF before matching, the exit code is read directly, and any exit outside {0, 1} — or exit 0 at a
count other than the baseline — is UNREADABLE rather than a verdict.

PROBE_TABLE_PLACEHOLDER

## What changed

`src/sync/signals/generated/symbols_speakeasy.py`: two statements and a docstring paragraph. Nothing
else in `src/` was touched, and none of the forbidden files was opened for writing.
`tests/golden/` and `benchmark/corpus/` are byte-identical to `origin/main` —
`git diff --name-only origin/main -- tests/golden benchmark/corpus` is empty.

**No new fixture file.** Every input is the committed `sdk_sources/vercel_typescript` tree copied to
`tmp_path` with one span of one file substituted, which keeps the other fourteen symbols as the
control for each edit and keeps the claim beside the assertion that rests on it — the same reason
M3-W95 gave for constructing nine of its fourteen inputs inline. `_edit` asserts its target occurs
exactly once, so a substitution that matched nothing cannot leave a test asserting against the
unmodified tree. The copy is `shutil.copytree`, bytes rather than text, because these are vendor
source files and a copy that decoded them would be asserting something about this machine's
codepage.

No test here calls a vendor API or a model API.

## Gates

GATES_PLACEHOLDER

## What this leaves for the next task

1. **This reader can say "a request module states a route I could not read", and it is two lines.**
   `_helper_path` knows it found a `pathToFunc` call whose argument it declined; `_builder_verb`
   knows it found a `_createRequest` call whose `method` it declined. Carrying that out of
   `_read_module` alongside `route` is exactly `symbols_typescript.py`'s `unread_helper`, and it
   would turn the one class of loss this generator hides — a staged request module whose route is
   unreadable — from an unattributed decrement into a named decline. It changes what this module
   emits, so it is a task rather than a drive-by, and it needs no change to `ExtractionReport`:
   `unreadable` is already the right channel and already carries prose.
2. **An unresolvable import specifier loses a mount and its decline together, and that is one
   condition rather than a design.** 503's `elif imported is not None` is written for "the source
   named no module", and `_specifier_target` answering `None` is not the same fact — it answers
   `None` for a specifier that named a module this rule could not turn into a key. Separating the
   two means `_specifier_target` returning why rather than only `None`, which is a signature change
   shared with `symbols_typescript.py`, where the identical handler sits at lines 198-201. Both
   modules, one argument.
3. **One literal reader, shared by the two tree-sitter rules — and it is the one place the
   duplication argument does not reach.** This is the task the provenance section above argues for,
   and it has two halves that should be taken together. The first is to stop the same defect
   arriving a third time: `_plain_route` and `_string_literal` were the same function, so the
   escape guard is a parser fact with no generator content, and today nothing connects them. The
   second is M3-W97's steer — align towards decoding rather than declining — which means
   interpreting `escape_sequence` nodes (`\/`, `\n`, `\xNN`, `\uNNNN`, `\u{…}`, line
   continuations) instead of refusing them, and turns two false negatives into two correct
   bindings. It is the only one of these three that adds a symbol rather than a sentence.

   The scope to hold it to: **one function, over one node type, with no parameters and no
   rule-specific behaviour.** That is deliberately not the shared walker the Speakeasy docstring
   refuses, and the distinction is the docstring's own — a walker has to be parameterised over
   four differences between the rules, and this has none, which is why `_route` was imported and
   this was not. If the change starts growing a `generator` argument, it has stopped being this
   task.
