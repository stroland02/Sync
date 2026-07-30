# The extraction report's numbers now say what they count, and a decline reaches somebody

M3-W100. `ExtractionReport` is shared by all three generated-SDK symbol readers, and three tasks in
a row queued a change to it rather than making one, because none of them owned the file. Two
findings were waiting there and they are one change:

**The denominator was counted in comparable keys and called specification operations.** M3-W96
constructed the cost. A vendor publishing three operations, two of which reduce to one comparable
key, got a denominator of two, and an SDK reaching both keys reported `2 of 2 specification
operations (100.0%)` for an API it reaches two thirds of. Every number in that line was internally
consistent with every other, which is what made it unreadable as a warning.

**Every decline in these readers was silent.** M3-W91 established it across nineteen branches of
the TypeScript flavour, M3-W95 across eleven in the two hand-written maps, M3-W97 across thirteen
in the Python flavour and the literal indexer. Four readers, and the same shape in each: the two
loud paths are a coverage line nobody compares to an expectation and a warning that fires only for
operations that *were* extracted, so a partial loss produced a smaller map and nothing else.

Both are closed. The contract change touched three flavours, the adapter and six test files, and
found two real losses in the committed Anthropic SDK on the way.

## The two reds

### The denominator, on W96's own constructed input

`tests/test_extraction_report_contract.py::test_two_specification_operations_behind_one_key_no_longer_deflate_the_denominator`,
against the SDK and specification W96 built:

    >       assert report.declared_operation_count == 3
    E       AttributeError: 'TypeScriptExtractionReport' object has no attribute
            'declared_operation_count'. Did you mean: 'spec_operation_count'?

and, from the test that pins the retirement rather than the correction:

    >       assert not hasattr(report, "spec_operation_count")
    E       AssertionError: assert not True
    E        +  where True = hasattr(ExtractionReport(..., spec_operation_count=121,
             unknown_to_spec=(), covered_count=10), 'spec_operation_count')

Eight of the nine tests in that first file were red, the ninth being the golden-schema control,
which was green from the first run and stayed green.

### A decline reaching the report

The second increment's red, from the same file:

    >       operations, unreadable = symbols.extract_symbols(root)
    E       ValueError: not enough values to unpack (expected 2, got 1)

    >       assert len(report.unreadable) == 1
    E       AttributeError: 'TypeScriptExtractionReport' object has no attribute 'unreadable'

Fifteen tests red, nine green — the nine being increment one's, which is the control that says the
second change did not reach the first.

## One count became two, and the old name was retired rather than corrected

`spec_operation_count` answered "how many distinct comparable keys did the specification yield"
under a name claiming to answer "how many operations does the specification declare". Those differ
by whatever the comparison's reduction absorbed: 121 against 131 for the vendor this repository
pins, 2 against 3 on W96's input.

**Two fields, because both facts are wanted and neither substitutes.**

- `declared_operation_count` — operations the specification declares, counted before any
  reduction. The API's size, and the only one of the counts a vendor publishes independently.
- `comparable_key_count` — distinct keys those reduce to. What the cross-check can be made
  against, and the denominator of `coverage_ratio`.
- `indistinct_operation_count`, a property, is the difference: declared operations this comparison
  cannot tell apart from another. Zero is the ordinary answer and is a claim rather than a default.

**The name was not reused for the corrected quantity, and that is the load-bearing decision.** The
brief allowed either changing the name or making the render line say which is which; this does
both, and retiring the name outright is the stronger half. A field whose meaning changed under an
unchanged name hands every existing reader a different number with no error. A name that is gone
raises `AttributeError` at the first stale read.
`test_the_retired_name_is_gone_rather_than_carrying_a_new_meaning` asserts the absence, so nobody
re-adds it with the old meaning either.

The rendered line changed wording for the same reason, so an operator comparing last week's line
against today's is looking at two different sentences rather than one sentence with two meanings:

    stainless-python: 11 symbols extracted, reaching 10 of 121 comparable routes (8.3%);
    the specification declares 131 operations, 10 of them not separately comparable;
    2 constructs this rule could not read

### The ratio stays in comparable routes, and that is not a compromise

The tempting alternative is `covered_count / declared_operation_count`, because 10 of 131 reads
like coverage of the vendor's API and 10 of 121 reads like coverage of an internal reduction.
**It would be a ratio of routes to operations.** `covered_count` counts comparable routes reached;
dividing by a count of operations produces a figure that moves when a reduction changes and means
nothing either way. That is the units mismatch the brief warned about for `configured_endpoints`,
arriving from inside the module instead.

Nor can `covered_count` be recounted in operations without inventing an answer. On W96's input the
SDK reaches `(GET, /v1/{}/members)`, which two declared operations sit behind; counting both as
covered claims coverage of an operation the SDK may not send, and counting neither understates a
route it demonstrably reaches. The truth is unknowable from these two artifacts, which is exactly
why the number is reported as a gap rather than folded into a ratio.
`test_the_ratio_is_taken_against_the_keys_it_is_counted_in` pins the division and asserts the other
one is different, so a later "improvement" to the honest-looking denominator goes red.

**The gap is not the same thing as a collision, and the wording matters.** Anthropic's ten
indistinct operations are `?beta=true` twins of routes already listed — a reduction this project
applies to both sides on purpose, where reaching the shared key really does cover both operations.
W96's one is a parameter collision, where it covers one and says nothing about the other. The
report cannot tell those apart, which is the reason it states the number and calls them *not
separately comparable* rather than uncovered.

### `read_spec_operations` stopped reducing what it reads

It returned `{_route(method, path)}`, so the query marker was dropped at the read and the published
operation count was gone before any report could carry it: 131 entries arrived as 121 members. It
now returns the operations as the specification states them, verb case normalised and nothing else,
and each flavour reduces both sides itself — which is where the reduction already lived, since the
two TypeScript flavours add one this file knows nothing about and were reducing an
already-reduced set.

One test moved with it. `test_a_beta_query_marker_is_not_mistaken_for_a_different_route` asserted
that the reader stripped the marker; it now asserts that the marker survives the read, that both
spellings of `GET /v1/models` are present, that they reduce to one of 121 routes, and that the
cross-check still reports nothing. That is a stronger statement than the one it replaced, because
it pins the layer the reduction happens at as well as the outcome.

## What `configured_endpoints` is, per generator, and why no runtime comparison was built

The brief asked this to be established before anything was compared. It was, per configured vendor,
against the committed manifests.

| Vendor | Generator | `configured_endpoints` | Parsed into | Spec staged here |
|---|---|---|---|---|
| anthropic | Stainless (python and typescript) | **131**, in both SDKs' manifests | `SpecSource.endpoint_count` | 131 operations |
| openai | Stainless | 278 | same | none |
| cloudflare | Stainless | 2521, and no spec URL at all | same | none |
| orb | Stainless (fixture) | 139, and no spec URL | same | none |
| vercel | **Speakeasy** | **absent** — a `workflow.yaml` declares its inputs, not its size | always `None` | 359 operations |

**It counts operations, not endpoints, despite the name.** The Anthropic specification's operation
set holds 131 entries across **89 distinct paths**; `configured_endpoints` is 131, not 89. So the
field's unit is (method, path), which is the unit `declared_operation_count` now counts in. Two
independently published artifacts agreeing on a denominator, which is what the old field could not
be checked against at all.

**Comparing it to an extraction is not apples to apples, and no such check was built.** Three
reasons, and any one is sufficient:

- **Symbols are not operations.** `extracted_count` counts chains a customer writes, and two of
  them can send one request — `messages.create` and `messages.parse` are both `POST /v1/messages`.
  Eleven symbols reach ten routes on the committed fixture. A check comparing 131 against a symbol
  count fires on a difference that is not an error.
- **`covered_count` is in comparable routes.** 131 against 121 differs by the query marker, which
  is deliberate on both sides. That check would fire on every run for this vendor.
- **The adapter has no version to select a manifest from.** `_sources` is keyed by version;
  `sdk_source` and `sdk_spec_operations` are not, and nothing maps a staged checkout to a manifest
  version. Choosing one arbitrarily would compare an extraction against a different tag's count.

**The one comparison that *is* apples to apples is between the two published artifacts**, and it is
now a test rather than prose. `test_the_operation_count_is_the_number_this_sdks_own_manifest_publishes`
reads `configured_endpoints` out of both Anthropic manifests through `parse_manifest` and asserts
`declared_operation_count == 131 == 131`. That protects the denominator's provenance, which is what
the whole coverage number rests on, and it is the check M3-W91 identified as existing and unused.
It could not have been written against the old field, which answered 121.

`test_a_generator_publishing_no_endpoint_count_leaves_the_denominator_unchecked` asserts the other
half: `configured_endpoints` is absent from `vercel/sdk`'s manifest, so for every Speakeasy vendor
there is no second artifact and nothing pretends otherwise.

## Which declines are carried, and why not fewer or more

Two kinds, distinguished by what the map loses, with a distinct message per cause inside each.

- **Kind A — a mount whose target this rule cannot reach.** Costs a resource and every operation
  under it.
- **Kind B — a request whose route this rule cannot read.** Costs one symbol.

The three decline tables are what makes the count two rather than nineteen. They establish that a
declining branch is one of three things, and only one of them belongs in a channel an operator
reads:

- **Correct and expected on every run.** A method that sends no request, a class that is not a
  resource, a path-item key that is not an operation, a comment inside an export clause. Recording
  these means hundreds of entries per extraction and a channel nobody reads.
- **Unfalsifiable or unreachable by construction.** The dead class-table guard all three flavours
  carry, `literals:79`, the seven tree-sitter field guards W91 measured across 4841 parses. A
  record on those is a line no run can produce.
- **A real partial loss.** The rule met a construct the source states and could not use it.

Only the third is recorded. The discriminator is not a judgement about the branch; it is a question
asked of the source at the branch, and it differs per flavour because the languages state different
amounts.

**Python has only a class name.** A `cached_property` annotation is the whole of what states a
mount, so the question is whether *any* class of that name is declared in the checkout. Measured on
the committed tree: eleven mounts resolve to a class that is declared here and is not a resource —
every `*WithRawResponse` and `*WithStreamingResponse` — and exactly one resolves to a name nothing
here declares. The first eleven are the module docstring's own deliberate exclusion and are not
recorded. The twelfth is `Anthropic.beta`, and it is a real loss.

**Both TypeScript flavours have the module too, so they ask the sharper question.** A mount across
files is written `new ModelsAPI.Models(this)` against an `import * as ModelsAPI from './models'`,
so the source names the file the class should be in. A record is written only where the source
named a module. That is what excludes `client.ts`'s real
`#requestAuthFlags = new WeakMap<...>()` — a field initialised with `new`, reaching the mount code
path, resolving to nothing — without naming `WeakMap` or any wrapper suffix anywhere in the rule.
`test_a_field_holding_something_this_sdk_does_not_declare_is_not_a_mount` holds it.

**Speakeasy's third refusal was left alone.** A checkout carrying resource classes without their
request modules already raises `UnrecognisedSdkShape`, and that is right: the channel is for a
partial loss, and a total one is not something to report a count for. The same reasoning keeps both
Stainless flavours' raise sites untouched.

**Two causes were deliberately not recorded**, both because no emission reaches them. A TypeScript
mount whose constructor is neither an identifier nor a member expression is unreachable — W91
established that prettier strips the redundant parentheses before Stainless writes the file — and
the Speakeasy equivalent is the same shape. A record there would be a line no run can produce,
which is the second category above.

### The two real losses the channel found

Both were already there, in committed vendor source, and neither was visible.

**`Anthropic.beta` mounts a tree the fixture omits.** The Python flavour records it once; the
TypeScript flavour commits `resources/beta/beta.ts` and so records the fourteen resources *it*
mounts instead. The README states this in prose — "coverage measured against this fixture is a
floor rather than the SDK's real figure" — and now the extraction says it in numbers.

**`messages.batches.results` sends a route no literal states.** The vendor writes
`self._get(path_template(batch.results_url, message_batch_id=...))`, so the route comes from a
field of an earlier response. Declining is right and there is no second source for it. But the
specification *does* declare `GET /v1/messages/batches/{message_batch_id}/results`, so the map is
missing a symbol for an operation both artifacts agree exists, and the coverage line read as a
slightly smaller SDK. **Both flavours lose it, independently.** Two rules over two languages
agreeing about a loss is what makes it a fact about the vendor's SDK rather than about either
reader.

| Artifact | Operations read | Kind A | Kind B | Total |
|---|---|---|---|---|
| `anthropic_python` | 11 | 1 (`Anthropic.beta`) | 1 (`Batches.results`) | 2 |
| `anthropic_typescript` | 12 | 14 (`Beta.*`) | 1 (`Batches.results`) | 15 |
| `vercel_typescript` | 15 | 38 mounts | 10 delegations | 48 |

Every one of the 48 in the Vercel column is the truncation its README documents: `sdk/sdk.ts` is
committed whole with all 41 of its mounts and eleven of its own delegations, while three resource
classes and one request module are.

## W94's shape, followed, with one narrowing

`2026-07-29-directory-skips-recorded.md` argued the convention rather than inventing one, and all
three of its specifics are copied:

- **A tuple of prose strings, not a structured record.** Each names its generator, its file, the
  class and member, and the cause. A reader filtering by cause matches on text, which is the
  existing rule for `IntakeReport.unreadable` and was kept deliberately.
- **Present and empty, never absent.** A clean read is `()`, and the render line's clause appears
  only when there is something to say, so silence is a claim.
- **Second in the returned pair.** `extract_symbols` returns
  `tuple[tuple[ExtractedOperation, ...], tuple[str, ...]]`, the shape
  `read_declared_dependencies` and `parse_directory` already return.

The field is named `unreadable`, the same key `IntakeReport`, `ReachabilityRanking` and
`parse_directory` use, for the reason M3-W90 recorded: a reader parsing several artifacts needs one
rule, not one per artifact. W96 had guessed the name would be `declined`, and
`test_a_collision_is_reported_nowhere` asserted `not hasattr(report, "declined")` — which would
have passed vacuously against a field called `unreadable`. That test was rewritten rather than left
to pass for the wrong reason.

**One narrowing, argued.** `unreadable` is **required at construction** rather than defaulted to
`()`. W94 defaulted its `registry_unreadable` parameter and gave the reason — a deployment that
passed no directory has no directory faults, so empty is the truth there. Here the opposite holds:
every construction site is an extraction that either found something or did not, and a default
would let a flavour that records nothing construct a report indistinguishable from one that found
nothing. That is the exact failure `ReachabilityRanking.unreadable` argues against, arriving in
constructor form. Three construction sites exist, all in `src/`, so requiring it costs nothing.

**Two things this did *not* do**, both because the convention is about a fault channel and neither
of these is one. A collision is not put in `unreadable`: both operations were read and the
reduction that merged them is deliberate, so recording it would report our own reduction as an
unreadable construct — the failure `_route`'s docstring names. And no `unreadable` entry is written
for the `UnrecognisedSdkShape` raises, which are total losses and already loud.

## The adapter's log level: the count at warning, the records at info

**`log.warning` once, naming the count and the generator. `log.info` per record.**

A decline means the map is smaller than the SDK, and a smaller map produces fewer findings, which
is indistinguishable from a healthy vendor. That is the false negative this whole module exists to
avoid, so silence is wrong and `debug` is silence in practice.

Warning *per record* is also wrong, and the measurement is the argument: the committed `vercel/sdk`
tree produces **48 records on every extraction**, because it is a deliberately partial checkout. A
vendor emitting 48 warnings per scan is how a reader learns to filter this logger out, and then the
one warning that mattered goes with it.

That is deliberately the opposite balance from `unknown_to_spec`, which warns per entry, and the
difference is what each channel reports. `unknown_to_spec` is two independently derived artifacts
disagreeing — evidence one of them is wrong, and each entry is its own reconciliation. This channel
is a limit of our own rule against a checkout, where the count is the finding and the records are
the detail.

Both adapter paths carry it, which closes the half M3-W91 measured as logging nothing at all: with
no specification staged there is no coverage line, so before this a decline had nowhere to appear
even in principle. `test_the_adapter_surfaces_a_decline_on_the_path_that_stages_no_specification`
and `test_the_adapter_states_the_count_once_rather_than_warning_per_decline` hold both, the second
asserting exactly one warning and 49 info records against the Vercel tree.

## The golden tool schemas did not move

`test_the_golden_tool_schemas_did_not_move` asserts `schemas_as_data() == tests/golden/tool_schemas.json`
and was **green on its first run, before any production change**, which is what makes it a control
rather than a regenerated file. Nothing here touches `severity`, `Finding`, or any MCP surface;
`git status` shows `tests/golden/` unmodified throughout, and `benchmark/corpus/` likewise — the
corpus scores the hand-written Stripe and Twilio maps, which no part of this change reaches.

## Mutation table

Harness at `%TEMP%\w100_mutate.py`, not committed. It runs

    uv run pytest -q --color=no -p no:randomly -n0 --no-header -p no:cacheprovider

over the six affected test files, 130 tests. Each mutation string must match **exactly once**, the
mutated text is `compile()`d before pytest is invoked, the verdict is read from the summary
*counts* rather than from line prefixes, and the baseline is asserted green at the same count
before the first mutation and after the last:
`restored baseline: exit 0, counts {'passed': 130, 'skipped': 2}`.

MUTATION_TABLE_PLACEHOLDER

## All four false-verdict modes, and which were live

The brief named four. Each is answered by construction, and each answer was **checked rather than
assumed** — the distinction M3-W97 insisted on, because "I took the precaution" is not evidence the
precaution was needed.

**Colourised summaries defeating a `FAILED ` prefix scan.** `--color=no`, and the verdict comes
from the summary counts, so a colour code cannot hide a kill even if colour leaked back in.

**A non-1 exit with no `FAILED` lines.** Any exit code that is not 0 or 1 is UNREADABLE.
Reproduced deliberately: `pytest -p no:xdist` against this repo's `-n auto` gives
`exit 4 counts {}`, classified `UNREADABLE (exit 4, counts {})`. A two-outcome harness reads that
as nine clean runs.

**A `SyntaxError` arriving as `ERROR` rather than `FAILED`.** Every mutation is compiled first.
Reproduced deliberately by control **C1**, an unclosed parenthesis, reported
`DID-NOT-COMPILE ('(' was never closed)` without pytest ever being invoked.

**A fourth guard, W94's:** exit 0 with a passing count other than the baseline is UNREADABLE, not a
survival, because the test set moved. `classify(0, {"passed": 41}, 130)` returns
`UNREADABLE (exit 0 but 41 passed, baseline 130)`.

**The subprocess mode was guarded and was not what saved this run.** `PYTHONIOENCODING=utf-8` in
the child's environment and `errors="replace"` on the decode, both present throughout. Measured:
of the four modules mutated, `symbols.py` carries exactly one non-ASCII character — U+2026 on line
22 of its module docstring — and the other three are pure ASCII. pytest echoes the failing frame's
source and no frame is ever a line of a module docstring, so the byte never reached the pipe. The
mode was therefore proved live by a direct probe using that same character rather than claimed from
the precaution:

| Child env / decode | Result |
|---|---|
| no `PYTHONIOENCODING`, `errors="strict"` | `UnicodeDecodeError: 'utf-8' codec can't decode byte 0x85 in position 0` raised **on the reader thread**, never propagated. `returncode=1`, `stdout is None` |
| `PYTHONIOENCODING=utf-8`, `errors="replace"` | `returncode=1`, stdout decodes, codepoint `0x2026` intact |

A two-outcome harness scores the first row as a survival or a kill depending only on how it counts,
and neither is true.

## Gates

GATES_PLACEHOLDER

## What this leaves for the next task

1. **The Python flavour's mount discriminator is the weaker of the two, and one input would fool
   it.** A `cached_property` annotated with a type this checkout does not declare — `-> str`, say —
   would be recorded as a missing resource. Zero such mounts exist across the committed tree's five
   files, and the cost is one extra line in a diagnostic channel rather than a wrong binding, so it
   is recorded rather than repaired. The sharper evidence is available and unread: the real source
   writes `from .resources.beta import Beta` inside the mount's own body, which names the module the
   way TypeScript's alias does. Reading it is a new capability for the rule, not instrumentation,
   which is why this task did not.
2. **`messages.batches.results` is a false negative with a name now, and repairing it is a
   different task.** The route is a field of an earlier response, so no static rule can read it;
   what could close it is the specification side — the operation is declared, and a symbol could be
   bound to it from the method name plus the resource chain. That is inventing a convention, which
   is what `operation_for_symbol` refuses, so it wants its own argument rather than a drive-by.
3. **`unreadable` is on the report and reaches no artifact.** `IntakeReport.to_json()` carries its
   own; this one reaches a log line and stops there. The question M3-W94 left open — whether one
   query should answer "what did this run not cover" across every signal source — now has a third
   channel to include, and this one is per-extraction rather than per-run.
