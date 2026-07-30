# An operation both artifacts declare, that no symbol map can reach

M3-W104. The decline channel M3-W100 built immediately surfaced something no coverage number
would have: the Anthropic SDK sends `GET /v1/messages/batches/{message_batch_id}/results` through
a route it reads out of an earlier response, so neither symbol reader can state the route and
neither produces a symbol for the operation. The specification declares it. **Both flavours lose
it, independently**, which is what makes it a fact about how the vendor builds the SDK rather than
a limit of either reader.

The task was to size the class before choosing a fix. The class has **one operation in it**, and
that answer is what decided the rest.

## The class, measured per artifact and separated by cause

`ExtractionReport` now carries the declines, so this was a query. Every unreached declared
operation across the three pinned artifacts, attributed:

| Artifact | Declared | Unreached declared operations | The omitted tree | The response-URL pattern | Anything else |
|---|---|---|---|---|---|
| `anthropic_python` | 131 | **112** | 110 | 2 | 0 |
| `anthropic_typescript` | 131 | **112** | 110 | 2 | 0 |
| `vercel_typescript` | 359 | **344** | 344 | 0 | 0 |

**The attribution is mechanical rather than judged.** This specification writes 120 of its 131
operations with a `?beta=true` marker, and 110 of those have no unmarked twin -- so an operation
carrying the marker and no twin is reachable only through the `beta/` tree both Anthropic fixtures
leave out, and each of those has a recorded mount decline behind it: one in the Python flavour
(`Anthropic.beta`, whose target file is not staged) and fourteen in the TypeScript flavour, which
does commit `resources/beta/beta.ts` and so declines the fourteen resources *it* mounts.

Strip the omitted tree and **one comparable route is left in each flavour**, in two declared
spellings -- `GET /v1/messages/batches/{message_batch_id}/results` and its `?beta=true` twin. That
is the whole class.

Vercel's 344 are the truncation its README documents, and the reason none of them is this class is
checkable: Speakeasy states the route in the request module a method delegates to, this checkout
stages fifteen of the 349, and **all fifteen yield a symbol.** Nothing is lost there to a route the
rule could not read. Its 48 declines are 38 mounts and 10 delegations, every one of them naming a
file absent from the checkout.

`test_the_fifteen_committed_request_modules_are_all_reached` already asserted the symbol count
against the literal 15. The test added here ties it to the filesystem --
`extracted_count == len(staged) == 15` -- which is the stronger form for this purpose: staging a
sixteenth request module whose route the rule cannot read leaves the extraction at 15, so the
existing assertion still passes and this one goes red. That is the case the class would grow by.

One further measurement, over the committed vendor source rather than over the reports: across both
Anthropic trees the *only* request-helper call whose route argument is not a literal is
`batch.results_url` -- twice in Python (the sync and async forms, the async one already excluded by
the base-class rule) and once in TypeScript. There is no second instance hiding behind the
truncation of what is staged.

**One is a curiosity; a dozen is a category.** This is one, and the population it is drawn from is
two vendors of a class of SDK whose remaining members are not staged here. That is the fact the
choice below rests on.

## The shape is statically recognisable, and recognising it buys a sentence rather than a symbol

Both flavours state it, differently, and both are two lines of work away:

- Python writes `self._get(path_template(batch.results_url, message_batch_id=message_batch_id))`.
  `_path_literal` already inspects `path_template`'s first argument and requires an
  `ast.Constant`; what is there instead is an `ast.Attribute` over a local name.
- TypeScript writes `this._client.get(batch.results_url, {...})`. `_tagged_route` and
  `_plain_route` both decline; the argument node is a bare `member_expression`.

So the reader can distinguish **"the route is a field of an object"** from "the route is absent" or
"the route is built by something I cannot read", without resolving anything.

**What that buys is a better decline message, not a binding.** The reader learns the route arrives
at runtime; it still cannot name which operation. A symbol carrying no route resolves to no
`OperationRef`, which is what `operation_for_symbol` already answers for an unknown symbol -- so
the call site binds to nothing either way and no finding becomes possible that was not possible
before. The sharper message is worth having and is recorded below as the next task rather than
taken here, because it is a change to what the rules read and this task's answer was to measure.

## The choice: option 1, and what is wrong with the other two

### Option 3 was rejected on a measurement, not on principle

The proposal is to bind `messages.batches.results` to the declared path
`/v1/messages/batches/{message_batch_id}/results` on the strength of the name. Two derivations were
built and scored against the only ground truth available -- the routes the three pinned SDKs
literally write down, 38 symbols in total.

**A: the chain composed into a path** (`/v1/` + resource segments + the method as a leaf). It
agrees with the SDK on **0 of 38**. `completions.create` sends `POST /v1/complete`; Vercel serves
routes under `/v1`, `/v2`, `/v3`, `/v4`, `/storage` and `/aliases` and the version prefix is not
derivable at all. This is not a near miss to be tuned.

**B: match the method name against a declared path's trailing segment**, with the verb taken from
the request helper -- which the decline record already knows -- and each chain resource required to
appear as a literal segment in order. On the declined method it produces exactly one comparable
key, and it is the right one. Scored over the 38:

| Artifact | Fires on | Right | Wrong | Ambiguous |
|---|---|---|---|---|
| `anthropic_python` | 2 of 11 | 2 | 0 | 0 |
| `anthropic_typescript` | 2 of 12 | 2 | 0 | 0 |
| `vercel_typescript` | 0 of 15 | 0 | 0 | 0 |

Four firings, four correct, and the four are **two distinct operations** --
`messages.batches.cancel` and `messages.count_tokens` -- each seen once per flavour. Two successes
and no failures bounds the error rate at roughly 0.78 by the rule of three: the evidence permits a
rule that is wrong three times in four. And it fires on none of the fifteen Vercel symbols, so for
the one generator whose vendor names operations by a different convention it has no validation
whatsoever.

The structural objection is worse than the statistical one. **A wrong binding here is
unfalsifiable by anything this module has.** `unknown_to_spec` catches a route the SDK states that
the specification does not declare; a name-derived route came *from* the specification, so that
check can never contradict it. The module's whole argument is that the SDK's source cannot be wrong
about what it sends because it is the thing that sends it -- and this abandons that for the one
binding where nothing can check the result. `symbols.py`'s own docstring names the failure mode: a
guessed convention fails silently, because an unresolvable symbol yields no finding and nobody
learns the guess was wrong. Here it would be worse than silent: it would resolve.

**Rejecting this is agreeing with two existing decisions rather than reversing them, and both are
worth naming.** `intake.py` refuses to join a package to a vendor on a name resemblance -- "the
join is the SDK repository, never the name" -- because `@vercel/sdk` resembles nothing it is
generated from and a package coincidentally sharing a vendor's name has nothing to do with it.
`manifest.py`'s `parse_manifest` refuses the mirror form: the filename selects the convention, so
content resemblance is never enough, because a `.stats.yml` body committed as `README.md` would
otherwise let any file in a repository steer a fetch.

One correction to the brief on that second one, because it matters for what is being agreed with.
The brief describes `manifest.py` as refusing to match on a name; the comment actually there
refuses to match on *content*, and requires the name. The shared principle is the one both state --
an identity has to be stated by an artifact rather than inferred from a resemblance -- and
`manifest.py` is an instance of it in the opposite direction rather than the same one. The
package's own name refusals are elsewhere and are stronger: `_declaring` in the TypeScript flavour
and the mount resolution in the Speakeasy one both leave an unresolved name unresolved rather than
matching it against a class of that name somewhere else, which is precisely the move option 3 asks
for one level up.

Option 3 would have been the first place in this package where a resemblance produced a binding.
**No name match was built, so there is no disagreement to argue and no risk bound to state beyond
the measurement above.**

### Option 2 is blocked by a forbidden file, and its rung question has an answer

A partial binding needs somewhere to live. `CallSite.operation_id` is a required `str`, so an
unresolved call site is not a `CallSite` at all -- both indexers skip a call whose symbol resolves
to nothing. Carrying "this symbol reaches an operation whose route is unresolvable" therefore needs
either a new optional field on `CallSite` or a widened `operation_id`, and both are
`src/sync/core/models.py`, which this task must not touch. **That is the next task, stated below,
rather than something reached for here.**

The rung is worth recording because the brief expected it to be the hard part and it is not.
`models.py` already declares a fourth value: `BindingRung = Literal["static", "resolved",
"observed", "unresolved"]`, where `unresolved` is "the absence of a binding, which is a state worth
naming". That is exactly what this is. It is **not** `observed` -- nothing watched any traffic; what
was read is a static fact about the SDK, namely that the vendor takes the route from a response
field. Calling it `observed` would launder a static reading into the rung an agent weighs a patch
by, which is the fabrication `conformance.py` already warns about in those words. So the honest
rung exists and the field to carry it does not, which is the whole of why option 2 is deferred.

### Option 1, taken

The failure mode is the recoverable one, and that is the deciding criterion. Option 1 leaves the
false negative in place, visible, recorded, and now counted -- nothing wrong is asserted, and a
later task closing it starts from a measurement. Option 2 asserts a binding nothing can consume
yet. Option 3 asserts a binding nothing can check, ever.

What shipped is the measurement and the tests that pin it.

## `ExtractionReport.unreached`, and why it is counted in operations where `covered_count` is not

The report already stated coverage in comparable routes and the API's size in operations. The one
thing it could not state is the gap between them in operations, which is the surface a vendor
change can move without any call site being found. So the field is the declared operations no
extracted symbol reaches, spelled as the specification spells them, and the render line carries the
count:

    stainless-python: 11 symbols extracted, reaching 10 of 121 comparable routes (8.3%);
    the specification declares 131 operations, 10 of them not separately comparable;
    112 declared operations no symbol reaches; 2 constructs this rule could not read

**M3-W100 refused to recount `covered_count` in declared operations and that refusal stands.** Its
reason: a comparable key two declared operations sit behind cannot be attributed, because reaching
it proves one of them is sent and says nothing about the other. Counting both as covered claims
coverage of an operation the SDK may not send; counting neither understates a route it demonstrably
reaches.

**The complement carries no such ambiguity, and that asymmetry is the load-bearing point.** The
reduction only ever merges. So if no symbol reaches the shared key, no symbol sends *any* of the
operations behind it -- the count in operations is exact where the reached one would be a range. For
`anthropic_python` the reached figure is somewhere between 10 and 19 and is not reported; the
unreached figure is 112 and is.

Two consequences the tests pin. `len(unreached)` is at least `comparable_key_count -
covered_count`, larger by however many operations the reduction absorbed -- 112 against 111 keys
here, and the extra one is the `?beta=true` twin of the batch results read, which a key-counting
report would have reported as one loss where the specification declares two. And the entries are
sorted: `spec_operations` is a set, string hashing is randomised per process, and a record left in
iteration order would make two extractions over identical bytes produce different records. Every
stage converges on the same input, and this is a record.

Required at construction rather than defaulted, for the reason `unreadable` is: three construction
sites, all in `src/`, and a default would let a flavour computing nothing pass for one that lost
nothing.

## Both flavours still lose it, and that is asserted rather than assumed

`test_both_flavours_lose_the_batch_results_read_and_agree_that_they_do` asserts, for each Anthropic
flavour, that no symbol named `messages.batches.results` exists, that a route decline naming
`Batches.results` is recorded, and that the set of unreached declared operations outside the omitted
tree is **equal between the two readers** -- `{("GET", "/v1/messages/batches/{message_batch_id}/results")}`.

The comparison is made on the specification's own spelling and that is why the field holds declared
operations rather than reduced keys. The two flavours reduce differently: the Python key is
`/v1/messages/batches/{message_batch_id}/results` and the TypeScript key is
`/v1/messages/batches/{}/results`, because that flavour reduces a parameter segment to a
placeholder. Comparing those would be comparing the readers' internals rather than their verdicts,
and "both readers agree about this loss" would not be a checkable claim at all.

M10 is the mutation that makes this non-vacuous: it lets the TypeScript flavour read the
response-URL argument as a route, closing one flavour and not the other. It kills eleven tests,
this one among them.

## Mutation table

Harness at `%TEMP%\w104_mutate.py`, not committed. It runs

    uv run pytest -q --color=no -p no:randomly -n0 --no-header -p no:cacheprovider

over six test files -- the new one plus the five covering the three changed modules. Each mutation
string must match **exactly once**, the mutated text is `compile()`d before pytest is invoked, and
the verdict is read from the summary *counts* rather than from line prefixes. Baseline asserted
green at the same count before the first mutation and after the last:
`restored baseline: exit 0, counts {'passed': 127, 'skipped': 2}`.

**Twelve real mutations, twelve killed.** One control, not counted among them.

| # | File | Mutation | Verdict | Tests killed |
|---|---|---|---|---|
| M1 | `symbols.py` | the complement is inverted -- the reached operations are reported as unreached | KILLED, 5 failed | `…counted_per_artifact`, `…unreached_key_makes_every_operation_behind_it_unreached`, `…count_travels_in_the_line…`, `…only_operation_outside_the_omitted_tree…`, `…both_flavours…agree_that_they_do` |
| M2 | `symbols.py` | the Python flavour reports nothing unreached | KILLED, 5 failed | the same five |
| M3 | `symbols.py` | the count is computed and never rendered | KILLED, 1 failed | `…count_travels_in_the_line_an_operator_reads` |
| M4 | `symbols.py` | counted in comparable keys rather than declared operations | KILLED, 5 failed | `…counted_per_artifact`, `…every_entry_is_an_operation_the_specification_declares…`, `…count_travels…`, `…only_operation_outside_the_omitted_tree…`, `…both_flavours…` |
| M5 | `symbols.py` | the entries are left in set-iteration order | KILLED, 1 failed -- **SURVIVED first**; the test was at fault, see below | `…every_entry_is_an_operation_the_specification_declares_as_it_declares_it` |
| M6 | `symbols_typescript.py` | the TypeScript flavour reports nothing unreached | KILLED, 4 failed | `…counted_per_artifact`, `…unreached_key_makes…`, `…only_operation_outside…`, `…both_flavours…` |
| M7 | `symbols_typescript.py` | the complement skips the parameter reduction the comparison used | KILLED, 3 failed | `…counted_per_artifact`, `…only_operation_outside…`, `…both_flavours…` |
| M8 | `symbols_speakeasy.py` | the Speakeasy flavour reports nothing unreached | KILLED, 2 failed | `…counted_per_artifact`, `…unreached_key_makes…` |
| M9 | `symbols_speakeasy.py` | the Speakeasy complement is inverted | KILLED, 2 failed | the same two |
| M10 | `symbols_typescript.py` | one flavour reads the response-URL argument as a route and the other does not | KILLED, 11 failed | `…both_flavours…agree_that_they_do`, `…no_symbol_is_bound_to_the_declared_operation_from_its_name`, `…coverage_numbers…did_not_move`, plus 8 existing |
| M11 | `symbols_speakeasy.py` | six staged request modules stop yielding a route | KILLED, 18 failed | `…speakeasy_flavour_loses_no_operation_to_a_route_no_literal_states`, `…counted_per_artifact`, `…coverage_numbers…did_not_move`, plus 15 existing |
| M12 | `symbols.py` | a verb the SDK sends is no longer recognised | KILLED, 12 failed | `…every_symbol_that_bound_before_still_binds_to_the_same_route`, `…coverage_numbers…did_not_move`, `…counted_per_artifact`, `…only_operation_outside…`, `…both_flavours…`, plus 7 existing |
| C1 | `symbols.py` | control: an unbalanced parenthesis | DID-NOT-COMPILE (`'(' was never closed`), pytest never invoked | — |

### The one survival, and where the fault was

**The brief's ordering held: suspect the mutation, then the test, then the code.** The fault was
outside the production code, which is now the ninth task in a row on this project to report that.

M5 replaces `sorted` with `iter` in the complement. The mutation is real -- `spec_operations` is a
set, string hashing is randomised per process, so the field's order varies between runs and two
extractions over identical bytes produce different records. **No test saw it**: the count
assertions use `len`, and the one filtered comparison has a single element, so order was invisible
to every test that touched the field. That is the M16 shape from M3-W100 exactly: a real mutation
with no fixture behind it. The assertion added is that the entries are sorted, argued from the
convergence rule rather than from tidiness, and M5 then kills.

### All four false-verdict modes, reproduced rather than assumed

| Mode | Guard | Reproduced |
|---|---|---|
| A colourised summary defeating a `FAILED ` prefix scan | `--color=no`, and the verdict comes from the summary counts, so a colour code cannot hide a kill even if colour leaks back | the counts path is the only one the verdict reads; `FAILED` lines are parsed for reporting only |
| A non-1 exit with no `FAILED` lines | any exit that is not 0 or 1 is UNREADABLE | `pytest -p no:xdist` against this repo's `-n auto`: `exit 4 counts {} FAILED lines 0`, classified `UNREADABLE (exit 4, counts {})`. A two-outcome harness reads that as a clean run |
| A `SyntaxError` arriving as `ERROR` rather than `FAILED` | every mutation is `compile()`d first | control **C1**, reported `DID-NOT-COMPILE ('(' was never closed)` without pytest being invoked |
| Exit 0 at a passing count other than the baseline | UNREADABLE, not a survival, because the test set moved | `classify(0, {"passed": 41}, 127)` returns `UNREADABLE (exit 0 but 41 passed, baseline 127)` |

**The subprocess mode was guarded and was not what saved this run**, and the distinction is stated
rather than the precaution claimed. `PYTHONIOENCODING=utf-8` in the child environment and
`errors="replace"` on the decode were present throughout. Measured: of the three modules mutated,
`symbols.py` carries exactly one non-ASCII character -- U+2026 on line 22 of its module docstring
-- and the other two plus all six test files are pure ASCII. pytest echoes the failing frame's
source and no frame is ever a line of a module docstring, so the byte never reached the pipe. The
mode was proved live by a direct probe with that same codepoint instead:

| Child env / decode | Result |
|---|---|
| no `PYTHONIOENCODING`, `errors="strict"` | `UnicodeDecodeError: 'utf-8' codec can't decode byte 0x85 in position 0` raised **on the reader thread**, never propagated. `returncode=0`, `stdout is None` |
| `PYTHONIOENCODING=utf-8`, `errors="replace"` | `returncode=0`, stdout decodes, codepoint `0x2026` intact |

The first row is the dangerous one precisely because the exit code is clean: a harness reading
counts out of `None` scores it as whatever its parser does with nothing, and neither answer is
true.

## The frozen inputs did not move

`tests/golden/` and `benchmark/corpus/` are byte-identical to `origin/main` --
`git diff --name-only origin/main -- tests/golden benchmark/corpus` is empty. Nothing here reaches
`severity`, `Finding` or any MCP surface, so no tool schema changed and none was regenerated. The
corpus scores the hand-written Stripe and Twilio maps, which no part of this change touches, and
`test_the_golden_tool_schemas_did_not_move` was green throughout.

## Gates

Branch `stroland02/m1-nodes`, three commits, head `31adc67`:

| SHA | Subject |
|---|---|
| `f64f9f7` | `feat: count the declared operations no extracted symbol reaches` |
| `d4ba718` | `test: pin the ordering a record has to have to converge` |
| `31adc67` | `docs: record why the class is counted rather than closed` |

`git diff --name-only origin/main...HEAD` is five files: three production modules, one new test
file, and this report. Eleven tests added, none deleted, and no existing test file was modified --
the field is new, so nothing existing asserted anything about it.

| Gate | Exit | Result |
|---|---|---|
| `uv run pytest -q` | 0 | 2497 passed, 4 skipped in 128.83s. The brief's baseline of 2486 plus this branch's 11 |
| `uv run python scripts/lint_encoding.py src scripts tests` | 0 | clean |
| `PYTHONIOENCODING=utf-8 uv run lint-imports` | 0 | 95 files, 201 dependencies, 1 contract kept, 0 broken. Run unredirected |
| `uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt` | 0 | clean |

### Why the figures come from a second worktree, and what the shared one said

A concurrent task was working in the assigned worktree throughout. Three things it did, none of
them this task's to undo:

- It held uncommitted edits to `src/sync/graph/schema.sql` and `tests/test_schema_convergence.py`,
  adding a `binding_rung` column to the `finding` table. Against that tree `pytest` exits **1** with
  exactly one failure --
  `tests/test_schema_convergence.py::test_a_column_definition_carrying_brackets_is_not_cut_in_half`,
  `At index 8 diff: 'binding_rung' != 'created_at'`. Neither file is one this branch touches, and
  that test file passes 6 of 6 at this branch's committed content, which is the attribution rather
  than a claim of it.
- It then moved the worktree onto a new branch, `b65-rung-attribution`, which it based on this
  task's second commit -- so `d4ba718` and `f64f9f7` are ancestors of that branch. Nothing was lost:
  `stroland02/m1-nodes` still points at `31adc67` and carries all three. Worth flagging to whoever
  merges, because that branch will appear to contain work that is not its own.
- `origin/main` advanced 15 commits meanwhile. It touches none of the three modules or the test
  file, so the merge is clean by content. The merged-tree gate run that `bb93176` establishes as the
  convention could **not** be done from here, because `origin/main` modifies the very
  `schema.sql` the concurrent session had dirty, and stashing another task's live edit is not this
  task's to do. Whoever merges should re-run the gates on the merged tree.

The four figures above therefore come from a detached worktree at `31adc67`. Two gitignored inputs
had to be supplied to it and neither is code: `tools/oasdiff.exe`, without which 38 tests fail and
9 error with `oasdiff not found; run scripts/bootstrap_tools.sh`. That intermediate run is recorded
rather than dropped, because a clean-checkout suite red for want of a binary is exactly the figure
that gets requoted later as a code failure.

### A fifth false-verdict mode, from the gate run rather than the mutation run

`pytest -q; echo "EXIT=$?"` was reported by the runner as **exit code 0** -- that is the *compound*
command's status, which is `echo`'s, while pytest's own was 1. The `echo` is what caught it. Reading
the wrapper's exit code rather than pytest's would have recorded a green gate over a red suite,
which is the same error as scanning for `FAILED ` prefixes wearing different clothes. The brief's
instruction to run pytest unpiped and read its own exit code is the guard, and it earned its place
on this run.

`SYNC_DSN` was left unset throughout, so `tests/conftest.py` derives a database name from each
run's own pid rather than sharing one with another task, and drops only what it created.

## What this leaves for the next task

1. **The decline could say the route came from a response, and it is two lines per flavour.** Both
   shapes are statically recognisable -- an `ast.Attribute` where Python's `path_template` wants an
   `ast.Constant`, a bare `member_expression` where TypeScript wants a string or a tagged template.
   The record would then distinguish "the route arrives at runtime" from "the route is absent",
   which is a different repair for a reader deciding whether to chase it. It is a change to what
   the rules read rather than to what they report, which is why this task did not take it.
2. **A partial binding needs a field `src/sync/core/models.py` does not have.** `CallSite`
   requires `operation_id`, so a symbol whose operation is known-but-unroutable cannot be recorded
   at all. The rung is settled -- `unresolved`, which already exists and is honest, where
   `observed` would launder a static reading into watched traffic. What is missing is somewhere to
   put it, and that file is a published contract with third-party consumers, so it is its own task
   with its own argument.
3. **`unreached` reaches a log line and stops there, which is the third channel to do so.**
   M3-W100 left that open for `unreadable`; this adds a second per-extraction channel with the
   same property. The question it sharpens: an operator asking "what can break without Sync
   noticing" now has a number, and no query that returns it alongside the other signal sources'
   equivalents.
