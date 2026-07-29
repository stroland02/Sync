# Ten refusals in the MCP-server signal source, and what a caller sees of each

M3-W93. Two small packages — `sync.signals.mcp_server` and `sync.signals.registry_tier` — held ten
unexecuted statements between them, and every one was a refusal to read something. This records
what input reaches each, whether refusing is right, and the question that turned out to matter
most: what the caller observes when it does.

## Coverage, before and after

Both figures come from the same command, run over the whole suite:

    uv run pytest -q -p no:randomly --color=no --cov=sync.signals.mcp_server \
        --cov=sync.signals.registry_tier --cov-report=term-missing

Before, at `88b620e`:

    src\sync\signals\mcp_server\arguments.py         36    4    89%   69, 77, 89, 95
    src\sync\signals\mcp_server\snapshot.py          29    2    93%   53, 73
    src\sync\signals\registry_tier\directory.py      46    4    91%   78, 86, 90, 99
    TOTAL                                           189   10    95%

After:

    src\sync\signals\mcp_server\arguments.py         38    0   100%
    src\sync\signals\mcp_server\snapshot.py          29    0   100%
    src\sync\signals\registry_tier\directory.py      46    0   100%
    TOTAL                                           191    0   100%

`arguments.py` gained two statements because the defect below was fixed in it. That fix also moved
the statements underneath it: the four refusals this task set out to cover were at 69, 77, 89 and 95
and are now at 69, 82, 94 and 100. Everything below refers to them by the line numbers in the
brief, which are the ones in the "before" column.

## The ten, and one more

| # | Statement | Input that reaches it | Is refusing right? | What the caller observes |
|---|---|---|---|---|
| 1 | `arguments.py:69` | `properties` is an array, not an object | Yes. A flat read finds no arguments and would report a tool that takes nothing. | **A row.** `mcp-tool-schema-not-comparable`, `info`, naming the tool. |
| 2 | `arguments.py:77` | one property's subschema is `true` — legal JSON Schema since draft 6, and not a table of arguments | Yes, and refusing the *whole* table rather than the one argument is the load-bearing part: a partial table's missing arguments read downstream as removed. | **A row.** Same kind and severity. |
| 3 | `arguments.py:89` | a property subschema names a `type` *and* composes beside it (`{"type": "string", "anyOf": […]}`) | Yes. `anyOf` intersects with `type`, so reading the `type` on show would be a confident wrong answer. | **Nothing.** `_types_narrowed` skips an argument whose types are unreadable. |
| 4 | `arguments.py:95` | a subschema naming no `type`, or a `type` that is not a string or a list of strings | Yes. There is nothing to compare and guessing would invent a narrowing. | **Nothing.** Same path as 3. |
| 5 | `snapshot.py:53` | a JSON-RPC error response, which has no `result`; also any payload that is not an object | Yes, emphatically. Read as an empty catalogue it withdraws the server's entire tool list. | **A `ValueError`,** uncaught to the top of the process. |
| 6 | `snapshot.py:73` | a capture advertising one tool name twice, with two different definitions | Yes — see the argument below. | **A `ValueError`,** naming the tool. |
| 7 | `directory.py:78` | an api id whose value is a string or an array rather than an object | Yes. `body.get` would raise on it, and there is nothing in it to read. | **Nothing.** The entry is absent from the returned list. |
| 8 | `directory.py:86` | one version whose detail is not an object | Yes, and the skip is correctly scoped to the version — the entry keeps its readable ones. | **Nothing.** The version is absent. |
| 9 | `directory.py:90` | a version with no `swaggerUrl`, or with no string timestamp in `updated` or `added` | Yes, given the data model. Nothing to download, or nothing `versions_after` can compare. | **Nothing.** The version is absent. |
| 10 | `directory.py:99` | an entry whose `versions` map was a non-empty object and every member of which was skipped | Yes, given the data model. | **Nothing.** The entry is absent. |
| — | `arguments.py:76` (new) | `required` is a string rather than an array | Yes, and it did not. **This was a defect; it is fixed.** | **A row** now; a fabricated `breaking` row before. |

### The two packages answer column 3 differently, and so does `arguments.py` internally

`sync.signals.mcp_server` refuses **observably**. Eight of its nine refusals reach a caller as
either a countable row or an exception. `sync.signals.registry_tier` refuses **invisibly**: all
four of its skips are `continue` statements inside `parse_directory`, which returns a list of what
parsed and carries no second channel. A document holding four malformed entries parses to a value
identical to a document that never held them, which is asserted directly rather than described —
`test_a_skipped_entry_leaves_no_trace_the_caller_could_count` compares the two parses for equality.

The split inside `arguments.py` is the sharper finding, because the module's opening docstring
makes a promise that holds for only half of it:

> So this refuses instead, and the caller turns the refusal into a row.

True of `read_arguments` (rows 1 and 2, and the unnumbered row added by the fix). Not true of
`_accepted_types` (rows 3 and 4),
whose `None` becomes an `Argument.types` of `None`, which `_types_narrowed` skips. A tool that
moved an argument's accepted types behind an `anyOf` is reported as unchanged — precisely the
"indistinguishable from a tool that did not change" outcome the paragraph was written to prevent.

**This is not repaired, and the reason is not scope.** `_types_narrowed` cannot emit on an
unreadable type without also emitting on every description edit to an untyped property, because
telling those two apart means deciding whether one JSON Schema accepts less than another. That is
schema subsumption, which the module is right to decline — its own bullet list already says value
narrowings are not read. The defect is that the opening paragraph reads as a blanket promise while
the bullet list scopes it to the top level of the schema. The behaviour is pinned by test so the
limit is at least countable.

### The registry tier is missing a channel that its sibling already has

`sync.signals.intake` has exactly what `parse_directory` lacks. `IntakeReport.unreadable` exists,
and `sync intake` prints it to stderr, on the stated grounds that a manifest which would not parse
is not a repository with no dependencies. The same sentence holds one level up: a directory entry
skipped is a vendor Sync will never offer to watch, and it is reported as a clean scan.

Closing it means changing `parse_directory`'s signature and both of its callers — `sync/cli.py` and
`sync/signals/intake.py` — neither of which this task owns. Reported rather than repaired.

One narrower observation on row 9, pinned by test because the code does not read the way it
behaves. `detail.get("updated") or detail.get("added")` falls back when `updated` is *falsy*, not
when it is *unusable*. A numeric `updated` is truthy, wins the `or`, then fails the string check —
so the version is skipped while a perfectly readable `added` sits beside it unused. Harmless
against the real directory, which writes strings for both.

## Who catches the two `ValueError`s

Nobody. The chain was read end to end rather than assumed:

- `parse_snapshot` raises; `load_snapshot` does not catch.
- `McpServerAdapter.fetch_changes` calls `load_snapshot` with no handler.
- `sync/cli.py:827` iterates `vendor.fetch_changes(...)` with no `try`. The only `except Exception`
  in that function guards `_model_deprecations`, a different adapter.
- `main()` has no handler, and `raise SystemExit(main())` never runs because the exception escapes
  `main()` first. The operator gets a traceback and a non-zero exit.

This is sanctioned rather than accidental. `sync.core.conformance._check_fetch_changes` states that
`fetch_changes` may raise, and records that an earlier version of the kit forbade it and was proved
wrong within a minute: answering an environment failure with an empty iterable reports that the
vendor changed nothing when nothing was looked at.

Two consequences worth having on record.

**The message is the entire user interface for these two failures.** Nothing logs, wraps or
summarises them, so the string is what an operator acts on. Both name their source — the capture's
path, and for row 6 the duplicated tool name. `test_the_refusal_names_the_capture_it_came_from`
pins that, because a refusal that did not name the file would leave an operator with a directory of
captures and no way to tell which is bad. This is *not* the "caught and logged where nobody reads
it" failure the brief warned about; it is the opposite, and it is the right shape.

**The graph survives.** The raise lands inside the `with store.transaction():` block in `sync run`,
after `store.truncate_all()`. `GraphStore.transaction` documents exactly this: an ingest that dies
half-way rolls back to the graph it started from rather than to an empty one. So a bad capture
costs a scan, not the previous scan's results.

## Duplicate tool names: what the specification says, and whether the refusal is proportionate

**The specification says SHOULD, and its schema enforces nothing.** From the draft server/tools
page, under Tool Names: *"Tool names **SHOULD** be unique within a server."* Under Data Types →
Tool: *"`name`: Unique identifier for the tool."* The opening paragraph: *"Each tool is uniquely
identified by a name."* But `schema/draft/schema.json` puts no `uniqueItems` on the `tools` array
and no uniqueness language on `name`, and `mcp.types.ListToolsResult` models `tools` as a plain
`list[Tool]`. So a duplicate is **non-conformant but not unparseable**, which is why it has to be
answered in our code rather than by the parser.

**The specification's own instinct is against whole-document refusal.** For the analogous case of a
tool it must reject, it tells clients to *"exclude the invalid tool from the result of
`tools/list`"* and to log a warning, explicitly so that *"a single malformed tool definition does
not prevent other valid tools from being used."* On its face that makes `snapshot.py:73`
disproportionate.

**It is nevertheless right here, for two reasons that apply to a differ and not to a client.**

1. *Excluding a tool is not free for us.* A client that skips a tool loses one capability. A differ
   that skips a tool has made it **absent**, and absent is exactly how this adapter reads a
   removal — the same trap the `nextCursor` check exists to close. Proportionality would buy a
   false `mcp-tool-removed` at `breaking`.
2. *Keeping one of the two definitions cannot be made idempotent.* Which one is live is unknowable,
   and the reference implementation does not agree with itself: `ToolManager.add_tool` returns the
   **existing** tool on a name collision, while the `ToolManager` constructor's loop overwrites,
   keeping the **last**. Servers are only told they **SHOULD** return tools in a deterministic
   order. So a row derived from a tie-break over an ordering the server need not hold stable is a
   row that does not converge across runs, which is the one thing `CLAUDE.md` does not permit of a
   pipeline stage.

A proportionate design does exist and is worth naming for later: keep the first definition and emit
`mcp-tool-schema-not-comparable` for that tool alone, which is a third state — present but not
comparable — that the adapter already has a kind for. It costs a tie-break, and refusing costs a
scan. Refusing is the safe direction because a refusal is loud and a wrong row is quiet, so it
stands; but it stands on this argument, not on the specification being silent.

## Nothing was judged unreachable

All ten statements were reached with committed fixtures, through the public entry points, without
calling a private function to get at a branch. `_accepted_types` is private and its two refusals
were reached through `read_arguments` and through `McpServerAdapter.fetch_changes`, asserting on the
returned `Argument.types` and on the rows, never on the private call.

Row 3 needed a fixture correction to be honest, and it is the one place this task nearly recorded a
false result. The obvious fixture for "a subschema that composes" is `{"anyOf": [{"type": "string"}]}`
— and deleting the guard at line 89 makes no observable difference to it, because the subschema has
no top-level `type`, so `_accepted_types` falls through to the same `None` at line 95. The mutation
would have survived, and the cause would have been the fixture, not the code. The fixture now
declares a `type` beside the `anyOf`, which is the only shape that makes line 89 distinguishable
from line 95 — and is also what real schemas do.

## Mutation table

Every test here pins existing behaviour, so "fails first" was established by breaking the statement
each covers. Harness at `%TEMP%\w93_mutate.py`, not committed; it runs `pytest -q --color=no
-p no:randomly -n0`, compiles each mutated file before pytest sees it, and classifies four outcomes.
Baseline asserted green before and after, at the same pass count, so a survival is distinguishable
from a blind harness.

| Statement | Mutation | Outcome | Killed by |
|---|---|---|---|
| `arguments.py:69` | `return None` → `properties = {}` (read the top level anyway) | KILLED, 3 failed | `…properties_that_is_not_an_object_is_refused`, `…refused_table_becomes_a_row…`, `…only_the_refused_tables_produce_rows` |
| `arguments.py:77` | `return None` → `continue` (skip the argument, keep the table) | KILLED, 4 failed | `…a_boolean_subschema_is_refused`, `…one_unreadable_subschema_refuses_the_whole_table`, `…refused_table_becomes_a_row…`, `…only_the_refused_tables…` |
| `arguments.py:89` | composition guard deleted (trust the `type` beside the `anyOf`) | KILLED, 3 failed | `…composed_subschema_yields_no_types_even_when_it_names_one`, `…types_became_unreadable_produces_no_row_at_all`, `…only_the_refused_tables…` |
| `arguments.py:95` | `return None` → `return frozenset()` (no type means accepts nothing) | KILLED, 3 failed | `…subschema_naming_no_type_yields_no_types`, `…types_became_unreadable_produces_no_row_at_all`, `…only_the_refused_tables…` |
| `arguments.py:76` (the fix) | reverted to `set(declared) if isinstance(…) else set()` | KILLED, 3 failed | `…required_that_is_not_a_list_is_refused`, `…only_corrected_its_required_spelling_breaks_nobody`, `…only_the_refused_tables…` |
| `snapshot.py:53` | `raise` → `result = {"tools": []}` (an outage is an empty catalogue) | KILLED, 3 failed | `…no_result_object_raises…`, `…payload_that_is_not_an_object_at_all…`, `…refusal_names_the_capture_it_came_from` |
| `snapshot.py:73` | `raise` → `pass` (last duplicate wins) | KILLED, 2 failed | `…duplicated_tool_name_refuses_the_whole_capture`, `…neither_duplicate_definition_is_quietly_chosen` |
| `snapshot.py:40` | `read_text(encoding="utf-8")` → `read_text()` | KILLED, 1 failed | `…row_keeps_the_advertised_description_byte_for_byte` |
| `directory.py:78` | body guard deleted | KILLED, 2 failed | `…entry_whose_body_is_not_an_object_is_skipped`, `…skipped_entry_leaves_no_trace…` |
| `directory.py:86` | detail guard deleted | KILLED, 3 failed | `…version_whose_detail_is_not_an_object…`, `…every_version_was_skipped…`, `…leaves_no_trace…` |
| `directory.py:90` | url/timestamp guard deleted | KILLED, 4 failed | `…no_spec_url_or_no_timestamp_is_skipped`, `…timestamp_that_is_not_a_string…`, `…every_version_was_skipped…`, `…leaves_no_trace…` |
| `directory.py:99` | `continue` → `pass` (keep an entry that lost every version) | KILLED, 2 failed | `…every_version_was_skipped_is_skipped_in_turn`, `…leaves_no_trace…` |

12 of 12 killed. No survivals, and no mutation failed to compile.

### The harness reproduced one of the three false-survival modes on its own first run

Its first baseline run exited **4** with no `FAILED` lines, which is the flag-collision mode the
coordinator warned about. The cause was mine — two test paths passed as a single `argv` item — but
the outcome is the point: a two-outcome harness would have called that a clean baseline and then
scored all twelve mutations as survivals. Classifying every exit code other than 0 and 1 as
UNREADABLE caught it immediately.

The three modes are answered as follows. `--color=no`, plus reading pytest's summary *counts*
rather than line prefixes, so colourised `FAILED` lines cannot hide a kill. `-n0` — which
`pyproject.toml` itself names as the focused-run form, against its default `-n auto` — so no plugin
flag collides; and any exit code that is not 0 or 1 is UNREADABLE rather than a survival. And
`compile()` on the mutated source before pytest is invoked, so a `SyntaxError` mutation is
DID-NOT-COMPILE up front instead of arriving as an `ERROR` with a non-zero exit.

## The defect, and the fix

`read_arguments` refused a `properties` that was not an object and a subschema that was not an
object, and **coerced** a `required` that was not an array to an empty set. That third shape is a
different kind of answer from the other two: an empty set is a claim — this server requires nothing
— about one of the two facts the module says it reads.

The cost is a false positive at `breaking` severity. Measured, not theorised:

    breaking  mcp-tool-required-argument-added  `query` is now a required argument of search

That row is from a pair where the server always required `query` and merely corrected
`"required": "query"` to `"required": ["query"]`. Nothing about what it accepts changed. The row
would drive a remediation pull request telling a customer to start passing an argument they were
already passing.

Fixed by refusing, which is what both neighbouring shapes in the same function already do. The
caller now gets `mcp-tool-schema-not-comparable` at `info`, which is true: the schema did change and
this differ cannot say what the change means. Two statements added to `arguments.py`; no other
production file changed.

## One fixture is deliberately not ASCII

`CLAUDE.md` records that every fixture in this repository is ASCII, and that therefore no test can
catch a missing `encoding="utf-8"` — it fails first against real vendor data. `rename_page`'s
description in the refusal pair now carries an em dash and three accented characters, which makes
`snapshot.py`'s explicit encoding load-bearing.

The failure mode had to be measured before the assertion could be written correctly. On this
machine cp1252 decodes those bytes **without raising** and yields mojibake, so a test asserting that
the read succeeded would pass under the mutation. The assertion is therefore on the string recovered
from the row, and the accents sit on a tool that emits a row rather than on one of the silent
refusals — `read_text()` in place of `read_text(encoding="utf-8")` is killed by it.
