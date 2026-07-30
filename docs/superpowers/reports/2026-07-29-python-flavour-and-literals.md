# Thirteen declines in the Python symbol reader and the literal indexer

M3-W97. `sync.signals.generated.symbols` is the original of the generated-SDK symbol readers and
the module the other two flavours import `ExtractedOperation`, `ExtractionReport`,
`UnrecognisedSdkShape` and `_route` from. `sync.index.literals` is the indexer that turns a
deprecated model id into a call site. Between them they held thirteen unexecuted statements.

Eleven are now covered. **Two are argued unreachable and were not reached**, and both are
unreachable in the same way — a guard against a `None` that the construction above it makes
impossible — which turns out to be the finding that carries furthest across the four readers.

No production code changed. No defect was found in either module's behaviour; one comment states a
reason that is not the reason, and that is reported below rather than repaired.

## Coverage, before and after

Same command both times, over the whole suite, from the worktree root:

    uv run pytest -q -p no:randomly --color=no \
        --cov=sync.signals.generated.symbols --cov=sync.index.literals --cov-report=term-missing

Before, at `2b2c29b`, which was `origin/main` when this branch was cut:

    src\sync\index\literals.py                 52      4    92%   59, 79, 111-114
    src\sync\signals\generated\symbols.py     146      9    94%   136, 162, 171-172, 179-181, 221, 307
    TOTAL                                     198     13    93%
    2343 passed, 2 skipped in 267.75s

After:

    src\sync\index\literals.py                 52      1    98%   79
    src\sync\signals\generated\symbols.py     146      1    99%   307
    TOTAL                                     198      2    99%
    2358 passed, 2 skipped in 310.31s

No statement was added or removed from either module, so the line numbers are the same in both
columns. Fifteen tests were added, all in one new file,
`tests/test_python_flavour_and_literal_declines.py`, and the suite moves from 2343 to 2358 by
exactly those fifteen.

The two statements still missing are `literals:79` and `symbols:307` — the two argued unreachable.

## The thirteen

| # | Statement | Input that reaches it | Is declining right? | What the caller observes |
|---|---|---|---|---|
| 1 | `symbols:136` — `return 0.0` | `report_extraction(root, set())` — a staged specification declaring nothing | Yes, and the alternative is worse: dividing would raise `ZeroDivisionError` from inside a log line. It is a sentinel rather than a measurement, and see the section below on whether that is legible | **The rendered line, and only there.** `0.0` as a float is *equal* to the ratio a fully missed specification gives. `render()` writes `0 of 0` beside it, so the denominator is what distinguishes them |
| 2 | `symbols:162` — `return True` | a mount decorated `@functools.cached_property` rather than the bare name | n/a — this **accepts**, it does not decline. Uncovered because the committed vendor source only ever writes the bare form | The mount is read, so a whole resource subtree is present that would otherwise be absent |
| 3 | `symbols:171-172` | `class Models(resources.SyncAPIResource)` — a base class named through a module | n/a — **accepts**. The base-class rule is the whole of how a resource is told from `AsyncModels` and the `*WithRawResponse` wrappers | The class is a resource. Without it the SDK appears to have none, which raises `UnrecognisedSdkShape` |
| 4 | `symbols:179-180` | `def messages(self) -> resources.Messages` — a dotted return annotation | n/a — **accepts**. Also reached from `_path_literal`, where a `path_template` called through a module still yields its route | The mount resolves. Without it the subtree is unrooted and silently absent |
| 5 | `symbols:181` — `return None` | two inputs: a `cached_property` with no return annotation, and one annotated with a subscript (`-> Optional[Messages]`) | Yes. The annotation is the only statement of what a mount mounts — the directory is deliberately not consulted — and guessing a subscript's base would mount a resource under a chain the customer may not be able to write | **Nothing.** The mount is absent from the map; every operation under it is unreachable |
| 6 | `symbols:221` — `continue` | `self._post(**kwargs)` — the verb stated, the route not | Yes. The route is the first positional argument and there is no second source. Recording the verb alone puts a symbol in the map with no route to match a vendor change against, while still counting towards the coverage figure | **Nothing.** That method contributes no symbol; others in the same class still do, because the decline is scoped to the call rather than the method |
| 7 | `symbols:307` — `continue` | Nothing. **Unreachable by construction** — see below | n/a | n/a |
| 8 | `literals:59` — `return []` | a quoted key in an `interface` or type literal: `interface ModelLimits { "claude-opus-4-8": number }`. The parent is a `property_signature` and its container an `interface_body`, not an `object` | Yes. The members of an interface are not the arguments of a call, and claiming them would make a parameter finding describe a call that was never made — the same failure the nested-object rule refuses | **Partial.** The site is still recorded, with the right `operation_id` and line; only `args_keys` is empty |
| 9 | `literals:79` — `return None` | Nothing. **Unreachable by construction** — see below | n/a | n/a |
| 10 | `literals:111` — `except Exception:` | a `str` carrying a lone surrogate, which `ast-grep` cannot encode to UTF-8 for the parser. **Not** a file that does not parse, and **not** a `UnicodeDecodeError` | Scope is wrong in both directions — see the section below | **Nothing.** An empty list, indistinguishable from a file that names no model |
| 11 | `literals:114` — `return []` | the same input | as above | **Nothing** |

Counted by statement rather than by row: **thirteen statements, of which five are accepts (rows 2,
3, 4) and eight are declines.** Two of the eight are unreachable (rows 7, 9). Of the six reachable
declines, **four are observed as `Nothing`** (rows 5, 6, 10, 11); row 8 is the only *partial*
decline in either module, where the call site survives and one field of it is empty; and row 1 is
the only one legible to a caller at all, and only through the rendered line rather than the value.

Rows 2, 3 and 4 are not declines at all. They are alternative spellings the rule already accepts,
uncovered only because the committed vendor source writes one spelling of each. That is worth
separating from the declines, because the risk they carry is the opposite one: a reader that
stopped accepting them would lose whole subtrees, and nothing would say so.

## The `except Exception`, and what actually reaches it

The comment says:

> Customer repositories contain files that do not parse: generated output, partial checkouts,
> syntax a newer compiler accepts. One bad file must not abort the index.

**That condition never raises.** tree-sitter error-recovers rather than refusing: `SgRoot("const =
= = {{{", "typescript").root()` returns a `program` node. The existing
`test_malformed_source_does_not_raise` is green because of the parser, not because of the handler
— which is exactly why the handler was unexecuted while that test passed. The intent the comment
states is real and is satisfied; the mechanism it credits is not the one providing it.

Measured, by exhausting what `SgRoot(source, language)` can raise:

| Input | Raised | Caught by `except Exception`? |
|---|---|---|
| source that does not parse | nothing at all — a `program` node with error recovery | n/a, the `try` completes |
| a `str` holding a lone surrogate | `UnicodeEncodeError` | **Yes**, and swallowed |
| an unsupported `language` | `pyo3_runtime.PanicException` | **No** — it derives `BaseException` directly |

So the handler's live scope is one exception type, `UnicodeEncodeError`, and it is the **encode**
direction.

### No `UnicodeDecodeError` reaches it, and that is structural

`index_operation_literals(source: str, ...)` takes text, not bytes. The decode already happened in
the caller, and `sync/cli.py:690-699` does it strictly and reports the failure by name:

```python
try:
    source = file_path.read_text(encoding="utf-8")
except UnicodeDecodeError as exc:
    print(f"model-deprecation: {relative} is not UTF-8 and was not indexed ({exc})", file=sys.stderr)
    continue
```

A `str` cannot carry undecodable bytes, so there is no decode left to fail at this boundary. The
mirror image is available — a `str` *can* carry a lone surrogate, and encoding one raises — and
that is the only thing the handler catches in practice. It is also unreachable from the production
caller, because that strict `read_text` is what produces the string and strict decoding never
emits a surrogate. Reaching it requires a library caller that decoded with `errors="surrogateescape"`.

Swallowing a `UnicodeEncodeError` there is therefore **not a behaviour anyone chose**. It is what a
bare `except Exception` happens to include. It costs nothing today because nothing can deliver the
input.

### Whether this handler belongs in the decode-handler inventory: no

`tests/test_decode_handlers.py` inventories a `try` by AST **only if a clause names
`UnicodeDecodeError`** — `decode_handlers()` keeps a handler when
`"UnicodeDecodeError" in _caught_names(handler.type)`. `except Exception:` names `Exception`, so
this handler is not in the inventory and no key needs re-anchoring.

Confirmed by running the inventory rather than by reading it: `decode_handlers()` returns **15
handlers and none of them is in `literals.py`**, and `tests/test_decode_handlers.py` is green at 19
passed on this branch. The positional-key hazard that file warns about did not arise, because no
file in `src/` was edited.

It should not be added, for a reason stronger than the matching rule: **the inventory's question
cannot be asked of this handler.** Its drivers construct undecodable *bytes* and assert the
handler answers correctly; there are no bytes here to construct, because the parameter is already
`str`. Widening `decode_handlers()` to match `Exception` would also pull in every broad handler in
`src/` and demand a driver for each, which is the eight-site edit that file's own docstring
records rejecting. `tests/test_decode_handlers.py` was not modified.

The handler that *does* protect this stage against undecodable bytes is already in the inventory
and already driven: `sync/cli.py:692`, registered as `_drive_literal_call_sites`.

### Whether a swallowed file is countable: no, and the channel already exists

`index_operation_literals` returns `list[CallSite]` and nothing else. A swallowed file returns `[]`,
which is identical to a file that legitimately names no model. `sync/cli.py:_literal_call_sites`
does `sites.extend(...)` per file per vendor and counts nothing, so the loss reaches nobody.

**No channel was built.** M3-W94 has just built one for `sync.signals.registry_tier` and a second
convention is worse than none. What exists is consistent across three modules already and is what
this would reuse rather than invent:

- `read_checkout` returns `(sources, skipped)` — the skipped paths, not a count.
- `read_declared_dependencies` returns `(declared, unreadable)`, surfaced as `IntakeReport.unreadable`.
- `parse_directory` now returns `(entries, faults)`, M3-W94's work.

Priced, not implemented: `index_operation_literals` would return `(sites, faults)`. The signature
change is unusually cheap — **one production call site, `sync/cli.py:702`, and three in `tests/`**
(`test_literal_index.py`, `test_deprecation_end_to_end.py`, `test_deprecations_third_vendor.py`).
That is far less than the 56 call sites W95 had to price for the hand-written maps. `sync/cli.py`
is forbidden to this task, but cost is not what argues against it.

**But the case here is weaker than in W94's module, and that is the more useful conclusion.** The
only refusal that can actually fire from the production path is the decode, and the caller
*already* names it on stderr three lines above the call. The parse guard cannot fire from
production at all. So a second channel would, today, report zero events forever. What would make
it worth building is a real input that reaches the guard — and this task establishes there is
none.

## Line 136's `0.0`: what consumes it, and whether it is a distinguishable zero

`coverage_ratio` has exactly one production consumer: `render()` at `symbols.py:150`, which
interpolates it as `{...:.1%}`. `render()` has exactly one production consumer:
`GeneratedSpecAdapter._extracted_symbols` at `adapter.py:332`, a `log.info`. Nothing else in
`src/` reads either. `grep -rn coverage_ratio src/` finds the definition and that one use.

**As a value the zero is not distinguishable.** An empty specification and a specification none of
whose operations were reached both answer exactly `0.0`, and the new test asserts that equality
rather than implying otherwise. Any consumer reading only the property could not tell a sentinel
from a measurement.

**In the only artifact that exposes it, it is** — because of the module's own rule that coverage
travels with its denominator. `render()` writes `0 of 0 specification operations (0.0%)` against
`0 of 1 specification operations (0.0%)`. That is the docstring's closing claim ("Coverage travels
with its denominator") doing real work: it is what keeps a sentinel legible without a second
field.

The zero-denominator input is also loud for an independent reason. Every extracted operation then
fails the cross-check, so the same line ends `; 11 extracted operations the specification does not
declare`. A staged specification that declares nothing produces a log line naming eleven
anomalies, not a quiet `0.0%`.

Reaching `spec_operation_count == 0` in production needs a staged `sdk_spec_operations` file whose
JSON array is empty. That is a plausible artifact — a fetch or reduction that produced nothing —
and it is a configuration fault rather than a vendor fault.

## The two unreachable statements, and which kind of unreachable

Both are `None` guards made impossible by the construction above them, and both are **redundant in
the forward direction *and* unfalsifiable by any fixture** — W95's distinction, and here the two
coincide rather than splitting.

**`symbols:305-307`.**

```python
resource = read.get(class_name)
if resource is None:
    continue
```

`read` is `{name: _read_class(...) for name, node in classes.items()}`, so its keys are exactly
`classes`'. Names enter the queue from two places only. The seed is `client_name`, written into
`classes` at line 281-282 on the same branch that sets it. Every later append is
`resource.mounts` values, and `_read_class` records a mount only `if mounted in resource_classes`
— and every member of `resource_classes` is written into `classes` on the same two lines
(278-279). So every name that can be queued is a key of `read`, and the guard cannot fire.

**`literals:78-79`.**

```python
parent = node.parent()
if parent is None:
    return None
```

The only node whose parent is `None` is the root; the root of every JS/TS parse is a `program`;
and the nodes handed to `_enclosing_key` come from `root.find_all(kind="string")`, which returns
descendants. Asserted over four sources including one that does not parse:
`test_a_string_literal_is_never_the_root_so_the_parent_guard_cannot_fire`. Note that the sibling
function's identical `pair is None` check at line 54 *is* covered — not because it fires, but
because it shares a line with the `kind()` test beside it, which is the same
co-located-clause blindness `tests/test_decode_handlers.py` exists to work around.

Neither was removed, and neither was reached by calling the private function with a fabricated
node. Both guards make their loop's assumption true by construction rather than by accident, which
is the reason M3-W91 gave for keeping the identical statement in the TypeScript flavour and M3-W95
gave for keeping `twilio:141-142`. Removing them is a production change with no defect behind it.

**The two mutations that break them establish more than redundancy, and this is a stronger result
than a deletion test gives.** Both were replaced by a form that *crashes* if the guarded condition
ever holds — `read.get(class_name)` became `read[class_name]`, which raises `KeyError`, and
`literals`' guard was deleted so that `parent.kind()` runs on `None` and raises `AttributeError`.
Both survived 112 tests. So the evidence is not merely "deleting the guard changes no assertion";
it is "across every input the suite has, the guarded condition never once held". A test asserting
the guard is redundant could pass while the condition occasionally fired and was silently absorbed;
these two cannot.

**The same dead guard exists in all three generated flavours**: `symbols.py:307`,
`symbols_typescript.py:520-521`, `symbols_speakeasy.py:500-501`. Three copies, three tasks, one
answer, and it is not drift — it is a shared idiom that is dead by construction in every copy.
M3-W91 reached this verdict for the TypeScript copy independently.

## How the Python flavour's declines differ from the other three readers'

Four readers now have a per-decline record: this one, the TypeScript flavour (M3-W91), and the two
hand-written maps for Twilio and Stripe (M3-W95). The comparison splits cleanly.

### The rule every one of the four applies

**Refuse to invent a name.** `symbols:181` declines a subscripted annotation rather than mounting
its base; `twilio:156` declines an unrecognised verb rather than minting `things.purchase`;
`stripe:143-144` declines rather than naming a method after its HTTP verb; the TypeScript flavour
declines a constructor it cannot read rather than guessing the class. Four independent modules,
one principle, and it is the principle `operation_for_symbol`'s docstring states.

**And all four are silent about it.** Four of my six reachable declines are observed as `Nothing`,
a fifth costs one field of a surviving call site, and the sixth is legible only because its
denominator travels beside it; W95 found eleven of eleven silent; W91 found every decline silent.
Four-for-four, and it is the strongest shared result across the set — with the qualification that
this module is the only one of the four with *any* decline a caller can see, and it got that for
free from a docstring rule about denominators rather than from a reporting channel.

### Generator and language facts

**Where the mount is stated differs, so the decline sets do not correspond.** Stainless-Python
mounts a resource with an annotated `cached_property`; Stainless-TypeScript mounts it with a `new`
expression in a field initialiser. So `symbols:181` (annotation names no class) has **no
TypeScript counterpart at all**, and `symbols_typescript:328` (constructor is neither an
identifier nor a member expression) has no Python counterpart. Neither is a missing rule; they are
two generators stating the same fact in different syntax.

**The dotted spellings — rows 2, 3 and 4 — are a Python-language fact.** A decorator, a base class
and an annotation can each be written through a module in Python. The TypeScript reader's analogue
is its `member_expression` handling in `_extends` and `_mount_target`, which is covered.

**One rule is identical in both generated flavours, on the same logical input**:
`symbols:220-221` and `symbols_typescript:315-316` both decline a request helper handed no
arguments, for the same stated reason. Agreement rather than drift, and it is worth recording as
such — it is the only decline of mine with an exact counterpart.

**The hand-written maps decline on document shape, the generated readers on source shape**, so
most of the eleven in W95's table have no analogue here at all. One structural difference does
matter: the generated readers **raise** `UnrecognisedSdkShape` when the shape is totally absent,
where the hand-written maps return a smaller dictionary. The generated flavours refuse a partial
map; the hand-written maps do not have that protection.

### The one difference in outcome on the same input, and it favours this flavour

**A route literal carrying an escape.** M3-W91 found and fixed a real defect in the TypeScript
reader: tree-sitter splits a string literal at every escape, `_plain_route` returned the first
fragment, and `'/v1/aAb'` was read as the route `/v1/a` — silently wrong. The fix was to
decline such a literal whole.

**That defect cannot exist here, and the fix is not needed here.** `ast.Constant.value` is the
*decoded* string, so this flavour reads `/v1/models` from `"/v1/models"` — the route the SDK
actually sends. Pinned by
`test_a_route_literal_carrying_an_escape_is_read_decoded_rather_than_truncated`, with the escape
written into the fixture as six characters so the decoding under test is the parser's.

So on one input both generators can emit, the two flavours answer differently: **Python binds the
operation correctly; TypeScript now loses it.** This is a parser fact in origin — `ast` interprets
escapes, tree-sitter reports them as siblings — and neither answer is wrong, because W91's decline
is a false negative rather than a false binding. It is recorded because the asymmetry is invisible
from inside either module: W91 chose declining as the safe answer without the other flavour's
option being available, and anyone later tempted to "align" the two should align towards decoding
rather than towards declining.

**Nothing here looks like drift.** Every difference traces to a generator's syntax or a parser's
model of a string literal. That is a different result from W95, which found one genuine drift
between the two hand-written maps — and the reason is structural: those two are independent
hand-written rules over the same kind of document, where these two are one rule expressed against
two languages.

## Mutation table

Every test here pins existing behaviour, so "fails first" was established by breaking the statement
each covers. Harness at `%TEMP%\w97_mutate.py`, not committed. It runs

    uv run pytest -q --color=no -p no:randomly -n0 --no-header -p no:cacheprovider

over `test_python_flavour_and_literal_declines.py`, `test_literal_index.py`,
`test_extracted_symbols.py`, `test_extracted_symbols_typescript.py` and
`test_extracted_symbols_speakeasy.py` — the last two because `ExtractionReport` and `_route` are
shared, so a mutation to them must be shown to reach the other flavours' tests or not.

It asserts each mutation string matches **exactly once**, `compile()`s the mutated source before
pytest sees it, and classifies from the summary *counts* rather than from line prefixes. Baseline
asserted green at **112 passed** before the run and **112 passed** after it, so a survival is
distinguishable from a blind harness.

| # | Statement | Mutation | Outcome | Killed by |
|---|---|---|---|---|
| P-136a | `symbols:136` | the sentinel answers `1.0` | KILLED, 1 failed | `…empty_specification_yields_a_zero_ratio_and_says_so_in_the_line` |
| P-136b | `symbols:135-136` | guard deleted; an empty specification divides by zero | KILLED, 2 failed | same, plus `…reports_every_extracted_operation_as_unknown` |
| P-162 | `symbols:161-162` | a decorator reached through a module is not read as one | KILLED, 1 failed | `…mount_decorated_through_a_module_is_still_a_mount` |
| P-171 | `symbols:171-172` | a dotted base class contributes no name | KILLED, 1 failed | `…resource_deriving_a_dotted_base_is_recognised` |
| P-179 | `symbols:179-180` | a dotted return annotation names nothing | KILLED, 1 failed | `…mount_annotated_through_a_module_names_its_resource` |
| P-181 | `symbols:181` | a subscripted annotation resolves to its base instead of declining | KILLED, 1 failed | `…annotation_names_no_resource_class_mounts_nothing` |
| P-192 | `symbols:192` | a route literal is truncated — the shape of the defect W91 fixed in the TS flavour | KILLED, 17 failed | `…escape_is_read_decoded_rather_than_truncated`, plus 16 pre-existing |
| P-221 | `symbols:220-221` | a helper handed no route records the verb with an empty path | KILLED, 2 failed | `…request_helper_handed_no_route_yields_no_operation`, `…does_not_stop_the_one_beside_it` |
| P-307 | `symbols:305-307` | class-table guard replaced by a direct subscript | **SURVIVED**, 112 passed | — (unreachable by construction; see above) |
| P-CTRL | `symbols:72` | control: anchor resources on a base Stainless does not write | KILLED, 25 failed | 25 across three flavours' test files |
| L-59 | `literals:58-59` | container guard deleted; interface members read as call arguments | KILLED, 1 failed | `…model_id_used_as_a_type_key_records_no_argument_keys` |
| L-59b | `literals:58` | an `interface_body` accepted as an argument object | KILLED, 1 failed | same |
| L-79 | `literals:78-79` | root-parent guard deleted | **SURVIVED**, 112 passed | — (unreachable by construction; see above) |
| L-111 | `literals:111` | `except Exception` narrowed to `except SyntaxError` | KILLED, 1 failed | `…parse_guard_swallows_an_encode_error_and_no_decode_can_reach_it` |
| L-114 | `literals:114` | the guard re-raises instead of swallowing | KILLED, 1 failed | same |
| L-CTRL | `literals:30` | control: look for a node kind the grammar does not have | KILLED, 22 failed | 22 across both literal test files |

**14 of 16 killed.** Both survivals are the two statements argued unreachable above, and in neither
is the fault the test or the mutation: the statement is dead by construction. No test was written to
reach either one artificially.

Nothing failed to compile, no mutation string matched more or fewer than once, and no run was
UNREADABLE or BASELINE-DRIFTED.

### The newest false-verdict mode: prevented, and measured separately rather than assumed

The brief predicted this harness would hit `subprocess.run(..., text=True, encoding="utf-8")`
returning exit 1 with no output, on the ground that both modules carry non-ASCII prose. **It did
not, and the reason is worth recording, because "I took the precaution" is not evidence the
precaution was needed.**

Measured on the two modules: `literals.py` is **pure ASCII**, and `symbols.py` carries exactly one
non-ASCII character, U+2026, on line 22 of its module docstring (`_makeRequest('GET', …)`). pytest
echoes the failing frame's source, and no frame is ever a line of a module docstring, so the byte
never reaches the pipe. Re-running
P-192 — the mutation that fails 17 tests and echoes the most source — with the guard **off** still
produced `KILLED (17 failed)`.

So the mode was proved live by a direct probe instead, using the exact character `symbols.py`
carries:

| Child env / decode | Result |
|---|---|
| no `PYTHONIOENCODING`, `errors="strict"` | `UnicodeDecodeError: 'utf-8' codec can't decode byte 0x85 in position 6` raised **on the reader thread**, never propagated. `returncode=1`, `stdout is None`, no counts — the harness's UNREADABLE verdict |
| `PYTHONIOENCODING=utf-8`, `errors="replace"` | `returncode=1`, stdout decodes, codepoint `0x2026` intact and classifiable |

The child encodes U+2026 as cp1252 `0x85`; `PYTHONIOENCODING=utf-8` is what changes what it emits
(measured: `sys.stdout.encoding` goes from `cp1252` to `utf-8`, including through `uv run python`),
and `errors="replace"` is the backstop for anything it does not cover. So `CLAUDE.md`'s guidance is
correct and load-bearing on this machine — it simply was not what saved *this* run, and a report
claiming otherwise would be inventing evidence.

One footnote, because it is the same class of error one layer out: an intermediate version of this
probe printed `�` where `0x2026` belonged and briefly looked like the child had misencoded.
That replacement character was produced by the display pipeline reading this agent's own stdout, not
by the child. Reading a codepoint list rather than a repr is what settled it.

## Gates

Run on the final tree, branch `stroland02/m1-nodes`, based on `2b2c29b`.

| Gate | Exit | Result |
|---|---|---|
| `uv run pytest -q` | PYTEST-EXIT | PYTEST-RESULT |
| `uv run python scripts/lint_encoding.py src scripts tests` | 0 | clean |
| `PYTHONIOENCODING=utf-8 uv run lint-imports` | 0 | 95 files, 201 dependencies, 1 contract kept, 0 broken |
| `uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt` | 0 | clean |

`pytest` was run unpiped with its exit code read directly, so the status is pytest's own and not a
pipe's.

## What this leaves for the next task

1. **The `except Exception` in `literals.py:111` should probably be narrowed, and no test here can
   prove it.** Its live scope is one exception type nothing can currently deliver, its stated
   reason names a condition that does not raise, and the one thing `SgRoot` reliably raises escapes
   it. Narrowing it to `UnicodeEncodeError` — or deleting it and letting the caller's decode remain
   the only guard — is a production change with no failing test behind it, so it is reported.
   The comment is the part that actively misleads: a reader who trusts it believes malformed input
   is handled here, when the parser handles it and this handler never runs.
2. **`ExtractionReport` still has no field for a decline**, which M3-W91 left for a later task and
   this task confirms from the Python side. All three flavours share the dataclass, so it remains a
   contract change across three modules. The manifest's `configured_endpoints` is still the
   published number that would make the comparison possible.
3. **Three copies of a dead class-table guard** now have three independent unreachability
   arguments. If anyone consolidates the generated flavours, that guard is the marker for where the
   three walks are the same walk.
