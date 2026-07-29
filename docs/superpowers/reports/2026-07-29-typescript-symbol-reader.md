# M3-W91: nineteen ways the TypeScript symbol reader gives up

`src/sync/signals/generated/symbols_typescript.py` had 19 uncovered statements and almost every one
was a `continue`, a `return None` or an `except` — the paths where the reader meets an emission it
does not recognise and declines to extract. A reader that declines too much produces a smaller
symbol map, and a smaller symbol map produces fewer findings, which is indistinguishable from a
healthy vendor. This is the record of what each of those paths declines, whether declining is
right, and whether anything downstream learns that it happened.

## Coverage, before and after

Command, both times, from the worktree root:

    uv run pytest -q --cov=sync --cov-report=term-missing

Before, on `24ea4af`:

    src\sync\signals\generated\symbols_typescript.py   251   19   92%
      192-193, 253, 269, 271, 298, 305, 326, 328, 336, 346, 353, 386, 394, 399, 426-428, 511

    2194 passed, 2 skipped

After:

    src\sync\signals\generated\symbols_typescript.py   255    8   97%
      309, 337, 347, 357, 364, 405, 410, 522

The statement count rises from 251 to 255 because the one defect found here cost four statements to
fix. Eleven of the nineteen are now covered; the remaining eight are the same eight statements
throughout, renumbered by that fix, and every one of them is argued unreachable below rather than
reached by calling an internal.

## Every declining branch, what reaches it, and whether declining is right

Line numbers are the pre-change ones, so they match the brief.

| Line | What it declines | What reaches it | Is declining right | Visible downstream |
|---|---|---|---|---|
| 192-193 | An import or re-export whose relative specifier resolves outside the checkout root | `import * as Out from '../../elsewhere/thing'` in a file at the root | Yes. A module outside the checkout is not this SDK; following it reads whatever sits beside the clone | No. The alias is not recorded, the mount holding it is not an edge, and the resource vanishes from the map |
| 253 | A string literal with no fragment — the empty string | `this._client.get('', {})` | Yes. The source states no route. Reading `''` as a route would mount an operation at a path no specification declares | No |
| 269 | A first argument that is a call but not a tagged template | `this._client.get(buildPath(x), {})` | Yes. Reconstructing what the callee returns means evaluating the source, and a guessed route resolves a call site to an operation the customer never calls | No |
| 271 | A tagged template under a tag other than `path` | ``this._client.get(url`/v1/ping`, {})`` | Yes, as the module argues: reading any tag means reading any string built by interpolation, and most are not routes. The cost is that a Stainless flavour renaming that helper reads as a vendor with no operations | No |
| 298 | A `member_expression` callee with no `object` or no `property` field | Nothing. **Unreachable** — see the argument below | n/a | n/a |
| 305 | A client call handed no arguments | `this._client.get()` | Yes, and there is nothing else available — the route is the first argument. Recording the verb alone puts a symbol in the map with no route to match a change against | No |
| 326 | A `member_expression` constructor with no `object` or no `property` field | Nothing. **Unreachable** | n/a | n/a |
| 328 | A `new` expression whose constructor is neither an identifier nor a member expression | `new (pick())(this)` | Yes. Which class that constructs is a runtime fact. An edge invented here files a resource's whole route set under a property no customer reaches by that name | No |
| 336 | A `class_declaration` with no `body` field | Nothing. **Unreachable** | n/a | n/a |
| 346 | A `new_expression` with no `constructor` field | Nothing. **Unreachable** | n/a | n/a |
| 353 | A `method_definition` with no `name` field | Nothing. **Unreachable** | n/a | n/a |
| 386 | An export-clause child that is not an `export_specifier` | `export { /* the resource */ Models } from './models'` — a comment is a named child of the clause, and so is an `ERROR` node from `export { A as }` | Yes, and this one is load-bearing in the other direction: the child names nothing, but skipping the rest of the clause would unroot every mount the client makes through the barrel | Harmless here — the specifier beside it is still read |
| 394 | An `export_specifier` with no `name` field | Nothing. **Unreachable** | n/a | n/a |
| 399 | A `class_declaration` with no `name` field | Nothing. **Unreachable** | n/a | n/a |
| 426-428 | Nothing — this is the `export *` chain being followed, not a decline | `export * from './models'` as the only forwarding of a resource | n/a, and the committed barrel never reaches it because it names every class it forwards | n/a |
| 511 | A queued class key absent from the class table | Nothing. **Unreachable** | n/a | n/a |

Two silent declines that reach no guarded statement at all, found while writing the fixtures and
worth recording because the map is the only place they show:

- **`abstract class Models extends APIResource` is not read.** tree-sitter parses it as
  `abstract_class_declaration`, and `_read_module` matches `class_declaration`. The class is never
  entered into the table, so a mount naming it resolves to nothing and the resource is absent.
- **`export default class extends APIResource` is not read either**, for the same reason: an
  anonymous default export parses as a class *expression*, node type `class`.

Neither is something Stainless emits, so declining is defensible. What is not defensible is that
in an SDK with other readable resources both produce an extraction that parses, roots, reports a
coverage number and is missing a resource. `test_a_resource_this_grammar_does_not_call_a_class_declaration_is_never_reached`
pins that, so the day a generator starts emitting one, a test says so rather than a coverage
number quietly dropping.

## Is a decline visible to anything downstream? No — every one of them is silent

`ExtractionReport` is shared with `symbols.py` and carries four things: `operations`,
`spec_operation_count`, `unknown_to_spec` and `covered_count`. There is no field for a construct
the reader met and declined, and `render()` composes its line from those four numbers only.

The two places a reader could learn something is wrong are both in
`GeneratedSpecAdapter._extracted_symbols`:

- `log.info("%s: %s", vendor_id, report.render())` — the coverage line. A decline lowers
  `extracted_count` and possibly `covered_count`, but nothing states an expected value for either,
  so a smaller number is not distinguishable from a smaller SDK.
- `log.warning(...)` per entry in `report.unknown_to_spec` — this fires only for an operation that
  **was** extracted and whose route the specification does not declare. A declined method never
  becomes an operation, so it never reaches this loop.

Both run only when `sdk_spec_operations` is staged. On the default path the adapter calls
`extract_symbols` and there is no logging at all.

So the whole module has exactly two loud failures, the two `UnrecognisedSdkShape` raises, and both
require the shape to be *totally* absent — nothing extending `APIResource`, or nothing mounting any
of them. Every partial loss is silent.

### What it would cost to make a decline visible

The cheap mechanism already exists in data the pipeline holds and does not use. The Stainless
manifest publishes `configured_endpoints` — 131 for this SDK, parsed into
`manifest.SpecSource.endpoint_count` — and it is the vendor's own count of the operations the SDK
contains. Nothing compares it against the extraction. `grep -rn endpoint_count src/` finds three
hits and none of them is a cross-check; the only consumer is an error message about a manifest that
names no spec to fetch.

Comparing the two would turn every silent decline in this module into one number an operator can
read: extracted 11, manifest says 131. That needs a field on `ExtractionReport` and a line in
`render()`, both in `symbols.py`, which this task is forbidden to touch and which would change what
the Python flavour emits as well. **Reporting it as the next task**, as the brief directs: it is a
contract change across two flavours and wants its own work.

## The unresolvable interpolation: a missing binding, never a wrong one

This is the module's own stated hard case — the route is a tagged template that has to be
reassembled from literal parts — and the question is whether a template the reader cannot fully
read produces a route with a hole in it.

It does not. `_tagged_route` walks the template's children and every `template_substitution`
contributes a segment where it stood, whatever the expression inside it was: the literal parts are
never simply joined. Measured on the shapes a generator could plausibly write:

| Source | Extracted route | Comparable after the parameter reduction | Outcome |
|---|---|---|---|
| ``path`/v1/models/${modelID}`` `` | `/v1/models/{modelID}` | `/v1/models/{}` | Matches `GET /v1/models/{model_id}`. Correct binding |
| ``path`/v1/models/${modelID}/x/${version}`` `` | `/v1/models/{modelID}/x/{version}` | `/v1/models/{}/x/{}` | Both segments present, same count as the source |
| ``path`${this.baseURL}/v1/models`` `` | `{this.baseURL}/v1/models` | `{}/v1/models` | Matches nothing. **Missing binding, and reported** in `unknown_to_spec` |
| ``path`/v1/${f({a: 1})}/ping`` `` | `/v1/{f({a: 1})}/ping` | `/v1/{})}/ping` | The inner brace mangles the reduction. Matches nothing. Missing binding, reported |
| ``path`/v1/ping/${}`` `` | `/v1/ping/{}` | `/v1/ping/{}` | An empty interpolation parses as a MISSING identifier whose text is empty, so the segment is present but empty |

So an interpolation this rule cannot resolve is a **missing** binding that says so: the operation is
in the map, it resolves to no vendor change, and where a specification is staged the cross-check
names it. `test_an_interpolation_this_rule_cannot_resolve_stands_where_it_stood` and
`test_a_route_carrying_an_unresolvable_interpolation_is_unknown_to_the_specification` hold both
halves.

One shape can still produce a wrong binding, and it is a consequence of the parameter reduction
rather than of the template reading: if an SDK interpolates a value that is *not* a path parameter
into a position where the specification writes one, `{}` matches `{}` and the route binds to an
operation the customer does not call. That reduction is deliberate, documented on `_PARAMETER`, and
shared with the Speakeasy flavour, which measured it inert for its own vendor. It is not something
this task should change; it is named here so the next reader knows the one remaining path.

The fourth row is a defect of a smaller kind — `_PARAMETER`'s `\{[^}]*\}` stops at the first
closing brace, so an interpolated expression containing one leaves debris in the comparable. It
cannot produce a wrong match (the debris matches nothing), so it is a missing binding either way,
and fixing it would change `_comparable` in a module the Speakeasy flavour copies. Recorded, not
fixed.

## Branches judged unreachable, with the argument

Eight statements remain uncovered. Seven of them guard a tree-sitter field against being `None`,
and the argument is the same for all seven: **the field is required by the grammar, and
tree-sitter's error recovery inserts a zero-width MISSING node rather than omitting a required
field.** `child_by_field_name` therefore returns a node, not `None`, however damaged the source is.

That is a claim about a parser, so it was measured rather than asserted. All eight committed
TypeScript fixture files were parsed, then 4841 parses in total across three families of damage —
every prefix of each file at 200 truncation points, single-byte deletions at 200 random offsets per
file, and a random one of `{}()` `` ` `` `'.,;<>` injected at 200 random offsets per file — plus 33
hand-written forms aimed straight at each guard (`this._client.;`, `a..b`, `class Foo` with no
body, `new;`, `class A { (){} }`, `export { , } from './x'`, `export { A as } from './x'`, and the
rest). Counts of each guarded field, and how often it was absent:

| Node type | Field | Nodes seen | Field absent |
|---|---|---|---|
| `member_expression` | `object` | 296941 | 0 |
| `member_expression` | `property` | 296941 | 0 |
| `class_declaration` | `name` | 4272 | 0 |
| `class_declaration` | `body` | 4272 | 0 |
| `new_expression` | `constructor` | 21034 | 0 |
| `method_definition` | `name` | 30113 | 0 |
| `export_specifier` | `name` | 541465 | 0 |

The hand-written probes also show *why* each attempt fails to reach the guard, which is the more
useful half:

- `this._client.;` yields `member_expression object: (this) property: (property_identifier)` — the
  property identifier is MISSING and zero-width, but it is a node. **298, 326.**
- `class Foo` with no body, `class {}`, and `export default class extends APIResource {}` do not
  produce a `class_declaration` at all; they produce node type `class`, a class *expression*, which
  `_read_module` never matches. `abstract class` produces `abstract_class_declaration`, likewise
  unmatched. So `_read_class` is only ever handed a `class_declaration`, and that node type
  requires both fields. **336, 399.**
- `class A { x = new; }` does not produce a `new_expression`; the value parses as an identifier.
  **346.**
- `class A { (){} }` yields `method_definition name: (MISSING property_identifier)`. **353.**
- `export { , } from './x'` yields an `export_clause` with no children at all, and
  `export { A as } from './x'` yields one `export_specifier` with a name plus an `ERROR` sibling —
  which is the second input that reaches 386, and it is covered. **394.**

The eighth, line 511, is structural rather than grammatical:

    read = classes.get(key)
    if read is None:
        continue

`classes` is built as every `(module, name)` pair over `modules[module].classes`. Keys enter the
queue from exactly two places: `roots`, which is a filtered subset of `mounts`, itself keyed by
`classes`; and `mounts[key].values()`, which holds only what `_declaring` returned, and `_declaring`
returns `(module, name)` only on the branch where `name in modules[module].classes`. Every key that
can be queued is therefore in `classes` by construction, and the guard cannot fire. Reaching it
would mean calling into the walk with a fabricated queue, which is the manufactured path the brief
says not to build. `symbols.py` carries the identical guard at its line 307, also uncovered, for
the same reason.

## The defect found, and the production diff

**One defect, fixed: a route literal carrying an escape produced a wrong route, silently.**

tree-sitter splits a string literal at every escape, so `'/v1/aAb'` parses as
`string_fragment('/v1/a')`, `escape_sequence('A')`, `string_fragment('b')`. `_plain_route`
returned on the *first* fragment, so the route it read for that source was `/v1/a`.
`_tagged_route` collected only `string_fragment` children, so ``path`/v1/aAb/${x}` `` read as
`/v1/ab/{x}`. Both are routes the source does not state, produced with no signal of any kind.

That is the failure this whole module exists to avoid, and it contradicted `_plain_route`'s own
docstring, which claimed that reading the fragment rather than the quoted text meant "an escape
this does not interpret cannot be mistaken for one". It did the opposite: it truncated silently.

`test_a_route_literal_carrying_an_escape_is_declined_rather_than_truncated` was written first and
failed on both halves before the fix:

    Left contains 2 more items:
    {'models.plain': ('GET', '/v1/a'), 'models.tagged': ('GET', '/v1/ab/{x}')}

The fix declines the literal whole. Declining loses the operation, which is a false negative, but
the brief's ordering is the right one: a wrong route resolves a call site to an operation the
customer never calls, and a missing one does not.

### Hunk by hunk

Four hunks, 13 lines. Each is named against the test that proves it.

| Hunk | Lines | Kept or reverted | The test that proves it |
|---|---|---|---|
| 1a. `_plain_route` docstring, replacing the sentence that described behaviour the function did not have | 4 | **Kept.** Not a refactor — the sentence it replaced was false, and it was the reason the defect went unnoticed | Same test as 1b; the docstring is the claim the code now honours |
| 1b. `_plain_route`: decline a `string` carrying an `escape_sequence` | 2 | **Kept** | `test_a_route_literal_carrying_an_escape_is_declined_rather_than_truncated`, via its `models.plain` assertion. Mutation **M10** removes exactly this hunk and the test dies |
| 2a. `_tagged_route` docstring paragraph: the escape decline, and that a substitution always stands where it stood | 3 | **Kept.** The second sentence is the answer to the brief's stated hard case and is the invariant `test_an_interpolation_this_rule_cannot_resolve_stands_where_it_stood` pins | `test_an_interpolation_this_rule_cannot_resolve_stands_where_it_stood`, mutation **M9** |
| 2b. `_tagged_route`: decline a `template_string` carrying an `escape_sequence` | 2 | **Kept** | Same test, via its `models.tagged` assertion. Mutation **M11** removes exactly this hunk and the test dies |

Nothing was reverted. The two code hunks are proven *independently* rather than jointly: M10 and M11
remove one each, and each one alone turns the test red. Had only their conjunction been detectable,
one of them would have been unproven and would have gone.

### Two clauses that cannot be falsified, and what to do about them

Two mutations survived on the first attempt and in both cases the mutation was at fault, not the
test — the brief's ordering held, and it held twice. Both are worth recording as results rather than
as detours, because they say something about the code.

**`_tagged_route`'s `template.type != "template_string"` clause is redundant for the outcome.**
Removing it, the full suite passes: `2224 passed, 2 skipped`, exit 0. It is *not* subsumed by the
`_PATH_TAG` check that follows — the two overlap partially, and each catches inputs the other does
not:

- `path('/v1/x')`, an ordinary call under the right name, is caught by the type clause alone.
- ``url`/v1/x` ``, a tagged template under the wrong name, is caught by `_PATH_TAG` alone.

What makes removal behaviour-preserving is the trailing `or None`, not the tag check. Measured: a
`call_expression`'s `arguments` field is either an `arguments` node or a `template_string`, and
`string_fragment` and `template_substitution` occur only as direct children of the latter. So an
ordinary call reaching the part loop contributes nothing, the list stays empty, and `or None`
declines it.

**Should it be deleted? No.** It is what makes the loop's assumption — that these children are
template parts — true by construction rather than true by accident, and deleting it would move the
guarantee onto a backstop that happens to hold. It is also a production change no test proves
necessary, which this task is not permitted to make. Kept, and recorded here so the next reader
knows the branch is covered while its effect is not demonstrable.

**`_mount_target`'s final `return None` cannot be falsified by fabricating a class name.** The
first M5 returned the constructor's own text as a class name; `_declaring` refuses a name no module
declares, so the fabricated edge resolved to nothing and the map was unchanged. That is the module's
layered refusal working, and it means the branch is only falsifiable by a mutation that produces a
*resolvable* name. Unwrapping a parenthesized constructor is that mutation, and the test's fixture
now carries `new (API.Models)(this)` so it has something to find.

Both survivals were also test weaknesses, and both tests were strengthened rather than left: the
`buildPath` fixture was handed a variable where it should have been handed a literal, and the mount
fixture had no constructor that named a class. Commits `f90670b` and `1d1d1d3`.

## Mutation table

Harness: `--color=no`, exit code read, mutated text compiled before the run, `ERROR` lines matched
separately from `FAILED` lines, and the restored baseline asserted green afterwards. Every run
reported `restored baseline: exit 0, 0 failed, 0 errors`.

The three known false-survival modes were therefore all distinguishable, and **none of them
occurred**: no mutation produced a `SyntaxError` (so none was reported as `ERROR`/DID-NOT-COMPILE),
every exit code was 0 or 1 (so none was UNREADABLE), and colour was off throughout.

| # | Mutation | Branch it attacks | Verdict | Test killed |
|---|---|---|---|---|
| M1 | Drop `not arguments.named_children`, reading a client call handed no arguments | 305 | killed, exit 1 | `test_a_client_call_handed_no_arguments_yields_no_operation` |
| M2 | Fall back to the quoted text, reading an empty string as the empty route | 253 | killed, exit 1 | `test_an_empty_route_however_written_reads_as_absent_rather_than_as_a_route` |
| M3 (first form) | Drop `template.type != "template_string"` | 269 | **SURVIVED, exit 0** — faulty mutation; see the section above | — |
| M3 | Dig the route out of the first argument's subtree | 269 | killed, exit 1 | `test_a_route_built_by_a_call_this_rule_does_not_read_is_declined` |
| M4 | Read a tagged template under any tag | 271 | killed, exit 1 | `test_a_tagged_template_under_another_tag_is_not_read_as_a_route` |
| M5 (first form) | Return the constructor's own text as a class name | 328 | **SURVIVED, exit 0** — faulty mutation; see the section above | — |
| M5 | Unwrap a parenthesized constructor and mount what it names | 328 | killed, exit 1 | `test_a_mount_whose_constructor_is_not_a_name_is_not_an_edge` |
| M6 | `continue` becomes `break` on a non-specifier export-clause child | 386 | killed, exit 1 | `test_a_comment_inside_an_export_clause_does_not_stop_the_barrel_being_followed` |
| M7 | Do not return what a star re-export resolved | 426-428 | killed, exit 1 | `test_a_class_reached_only_through_a_star_re_export_is_followed` |
| M8 | Remove the `try`/`except ValueError`, letting a specifier outside the root raise | 192-193 | killed, exit 1 | `test_an_import_resolving_above_the_checkout_root_names_nothing_here` |
| M9 | Drop an interpolation instead of standing a segment where it stood | the interpolation invariant | killed, exit 1 | `test_an_interpolation_this_rule_cannot_resolve_stands_where_it_stood` and `test_a_route_carrying_an_unresolvable_interpolation_is_unknown_to_the_specification`, plus 5 pre-existing tests |
| M10 | Remove the escape guard from `_plain_route` (production hunk 1b) | the defect | killed, exit 1 | `test_a_route_literal_carrying_an_escape_is_declined_rather_than_truncated` |
| M11 | Remove the escape guard from `_tagged_route` (production hunk 2b) | the defect | killed, exit 1 | `test_a_route_literal_carrying_an_escape_is_declined_rather_than_truncated` |
| M12 | Match `abstract_class_declaration` as a declaration too | the silent pre-guard decline | killed, exit 1 | `test_a_resource_this_grammar_does_not_call_a_class_declaration_is_never_reached` |
| M13 | Anchor resources on a base this emission does not write | the control | killed, exit 1 | `test_the_hand_built_sdk_is_read_before_anything_is_declined`, plus 26 others |

M9 and M13 killing many tests each is the intended reading rather than noise: the interpolation
reader and the resource anchor are load-bearing for the whole file, and a mutation to either that
killed only the new test would mean the new test was measuring something the module does not
actually depend on.
