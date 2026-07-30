# Eleven declines in the two hand-written symbol maps, and what a caller sees of each

M3-W95. `sync.signals.twilio.symbols` and `sync.signals.stripe.symbols` are the two maps written
by rule rather than read out of a generator, and between them they held eleven unexecuted
statements. Every one is a decline: an input that yields no symbol.

The brief's title says fifteen and its body says eleven. **Eleven is what the coverage output
supports**, re-measured before any edit: six in Twilio, five in Stripe, and nothing else uncovered
in either module. No reconciliation to fifteen was attempted and none is available.

## Coverage, before and after

Both figures come from the same command, run over the whole suite:

    uv run pytest -q -p no:randomly --color=no --cov=sync.signals.twilio.symbols \
        --cov=sync.signals.stripe.symbols --cov-report=term-missing

Before, at `3cd71eb` (`origin/main`):

    src\sync\signals\stripe\symbols.py      69      5    93%   143-144, 184, 190, 193
    src\sync\signals\twilio\symbols.py      59      6    90%   110, 114, 142, 145, 149, 156
    TOTAL                                  128     11    91%
    2285 passed, 2 skipped in 199.38s

After:

    src\sync\signals\stripe\symbols.py      69      0   100%
    src\sync\signals\twilio\symbols.py      59      0   100%
    TOTAL                                  128      0   100%
    2299 passed, 2 skipped in 137.36s

No statement was added or removed from either module, so the line numbers below are the same in
both columns. Fourteen tests were added, all in one new file.

## The eleven

| # | Statement | Input that reaches it | Is declining right? | What the caller observes |
|---|---|---|---|---|
| 1 | `twilio:110` — `not isinstance(body, dict)` | an `x-twilio.parent` naming a path the document does not contain | Yes, and refusing the *whole chain* is the load-bearing part. Keeping the resolved tail would mount the child at the top level under a name no library exposes. | **Nothing.** The symbol is absent from the returned map. |
| 2 | `twilio:110` — `path in seen` | a parent cycle: a path naming itself, or a two-path ring | Yes. Without it a cycle is a `RecursionError` from inside a map build, which is a crash rather than a diagnosis. No published document contains one. | **Nothing.** Absent. |
| 3 | `twilio:114` | `_mount` answers `None` — a path with no `mountName` and no literal segment after the version, e.g. `/v1/{Sid}` | Yes. The alternative `""` mounts the operation at `twilio.insights.v1..fetch`, a key no library produces and no call site can spell, which sits in the map resolving nothing forever. | **Nothing.** Absent. |
| 4 | `twilio:142` | a `paths` entry whose value is not an object | Yes, but **the statement is redundant** — `_chain` re-reads `paths[path]` and refuses a non-object itself. See below. | **Nothing.** The path is skipped; its siblings resolve. |
| 5 | `twilio:145` | any path whose chain was refused — rows 1, 2 and 3 arriving at the loop | Yes. Scoped to the one path rather than the document. | **Nothing.** Absent. |
| 6 | `twilio:149` | a path-item key whose value is not an operation object. **Twilio writes two on every path of this product**: `servers` (a list) and `description` (a string). | Yes, and it is not a defensive guard — it is what makes the rest of the suite's fixture reduction safe. | **Nothing.** The key contributes no symbol. |
| 7 | `twilio:156` | an `operationId` whose leading word is absent from `_SDK_VERBS` (`PurchaseThing`), or that does not match the leading-word pattern at all (`fetchThing`) | Yes. Twilio states the verb in `operationId` and nowhere else, so there is nothing to fall back to; accepting the word would mint `things.purchase`, which `twilio-python` does not expose. | **Nothing.** Absent. |
| 8 | `stripe:143-144` — `case _` | four kinds: a verb Stripe does not use on a v1 resource (`PUT`, `PATCH`); a `DELETE` on a path this map reads as a collection; an object-valued path-item key that is not a method (an `x-` extension); and any of those with an `x-stableId` naming no verb | Yes. Naming the method after the verb is the plausible wrong answer and it is the invented method name `_SDK_VERBS`' own comment refuses. **But the statement is removable** — see below. | **Nothing.** Absent. |
| 9 | `stripe:184` | a path-item key whose value is not an object: `parameters`, `servers`, `description`, `summary` | Yes — but for those four inputs it is **redundant** with row 8, which refuses them one line later. It is load-bearing only for a *method* key holding a non-object, which no valid document contains. | **Nothing.** The key contributes no symbol. |
| 10 | `stripe:190` | any operation where both verb sources declined — row 8's inputs | Yes. | **Nothing.** Absent. |
| 11 | `stripe:193` | an operation object carrying no `operationId` | Yes. `operation_id` is what the graph joins a vendor change against, so an entry carrying `None` there is a call site bound to nothing, occupying the key the real operation would take. | **Nothing.** Absent. |

Eleven declines, eleven times **Nothing**. Neither module raises on any of them and neither
returns anything but the mapping.

## Row 6 is the one the coverage number was hiding something behind

`twilio:149` was not uncovered because the input is exotic. It is uncovered because
`scripts/build_twilio_fixtures.py:shape_only` deletes the input:

```python
for key, value in body.items():
    if key == "x-twilio":
        kept[key] = value
    elif isinstance(value, dict) and value.get("operationId"):
        kept[key] = {"operationId": value["operationId"]}
```

`servers` and `description` are legal Path Item fields and the vendor writes both on every path of
this product — measured on the committed real bytes at `tests/fixtures/twilio/2.3.0/insights_v1.json`,
where all four path items carry `description` (string), `servers` (list), `x-twilio` (object) and
`get` (object). The reduction's stated reason is correct about what the map *reads*; the guard at
149 is what makes that reduction safe, and no fixture exercised it.

`test_the_real_vendor_document_carries_path_item_keys_that_are_not_operations` builds the map from
that real document instead of the shape fixture. It is the only test in the suite that does, and
deleting the guard fails it and nothing else.

The same asymmetry explains why `twilio:152` (`if not operation_id: continue`) was already covered
while its Stripe counterpart at 193 was not: `x-twilio` survives the reduction, it is an object,
and it carries no `operationId`, so it lands on 152. Stripe's fixture has no path-item extension
and Stripe checks the verb *before* the id, so nothing reached 193.

## Whether a decline is visible downstream, per module

**Neither module. Identically, and completely.** Both `build_symbol_map` functions return a
`dict[str, dict[str, str]]` and nothing else. No count, no list of what was refused, no log line,
no exception. `test_a_declined_operation_leaves_no_trace_either_map_s_caller_could_count` asserts
this directly rather than describing it: a document holding declined operations builds a map equal
to a document that never held them, for both vendors.

The two production callers do not close the gap:

- `registry._prepare_stripe` writes `json.dumps(build_stripe_symbols(head, sdk_spec))` to
  `symbols.json`. No count is read, compared or recorded.
- `registry._prepare_twilio` calls `symbols.update(...)` once per product document and writes one
  file. Nothing counts, and see the next section for a second problem with that `update`.

**One thing downstream does notice a map that shrank, and it is worth being precise about what it
notices.** `scripts/symbol_map_pin.py` pins the staged map by digest *and* by symbol count, and
`verify_staged_map` raises `SymbolMapMismatch` naming both sides. So a decline that changes the map
from the one the corpus recorded is loud — but only on the corpus-scoring path
(`scripts/score_corpus.py`), not on `sync run`, and it says only that the map differs. It cannot
tell a decline from Stripe removing an operation, which is exactly the attribution a false negative
needs.

**What it would cost to make declines countable, not built here.** A live task is building a
reporting channel for a different package and a second convention is worse than none, so this is
priced rather than implemented:

- Two production call sites (`registry.py:440`, `registry.py:467`) and 56 call sites across
  `tests/` and `scripts/` pass the current single-return signature. A second return value or a
  report object touches all of them.
- There is a coupling that is easy to miss. The written artifact **is** the mapping, and
  `symbol_map_digest` digests every key of it. Adding a `declines` key to `symbols.json` adds an
  entry the pin reads as a symbol, moving both `digest` and `symbols` and breaking
  `benchmark/corpus/symbol_map.yaml`. A decline count has to travel beside the artifact, not
  inside it.
- `registry.py` is not this task's to modify, so the cheapest honest version is: `build_symbol_map`
  returns `(mapping, declines)`, `registry` writes the count to a sidecar, and `sync run` prints it
  the way `sync intake` prints `IntakeReport.unreadable`. That is the shape
  `2026-07-29-mcp-signal-refusals.md` recommends one level down, and the argument transfers without
  change.

## Whether the two maps decline on the same inputs

They are independent hand-written maps and `CLAUDE.md` requires vendor knowledge to stay in
adapters, so they are supposed to differ. Three differences are vendor facts, two look like drift.

### Vendor facts

**An unrecognised verb ends the Twilio derivation and costs Stripe nothing.** This is the largest
difference and it follows from the documents. Twilio writes the verb into `operationId` and states
it nowhere else, so `twilio:156` has nothing to fall back to. Stripe has two independent sources —
`x-stableId` in the generator input, and the HTTP method with the path shape — and the second is
already the answer for every operation the first does not cover, so an unrecognised token there
changes nothing. `test_only_twilio_declines_an_unrecognised_verb_and_only_stripe_has_a_fallback`
asserts the asymmetry on the same logical input to both, so it is a measurement rather than a
reading of two docstrings.

**Twilio needs a cycle guard and Stripe has no chain to cycle.** `x-twilio.parent` is a link;
Stripe's resource name falls out of one regular expression over the path.

**Placeholder-only paths are refused by different mechanisms.** Twilio's `_mount` answers `None`;
Stripe's `^/v1/([a-z_]+)(/\{[^}]+\})?/?$` simply does not match, and the skip lands on the
already-covered `continue` at 177. Same protection, and the difference is that the vendors' URL
conventions differ — which is the reason the pattern is in an adapter.

### Drift

**A malformed path item: Twilio skips it, Stripe raises `AttributeError: 'list' object has no
attribute 'get'`.** Same layer, same input, two answers. Neither vendor publishes such a document,
so this is not a live defect for either — but the two adapters disagree about whether a vendor
document is a system boundary, and `CLAUDE.md` says it is one ("Validate at system boundaries —
user input, vendor responses, subprocess output"). The raise is also the less useful answer: a
skipped path could name which document is bad and a type name cannot.

Resolving it means adding Twilio's guard to Stripe, which is a production change with no test able
to demonstrate a defect against real vendor data, so it is reported rather than made.
`test_the_two_maps_answer_a_malformed_path_item_differently` pins both answers so the drift is
visible in the suite rather than only here — the same device
`test_the_enum_noise_filter_is_applied_to_twilio_too` uses for duplicated vendor knowledge.

**The `operationId` check and the verb check are in opposite orders.** Twilio checks `operationId`
first (152, then 156); Stripe checks the verb first (190, then 193). No input is answered
differently — both orders skip — so this is drift without a cost, and it is recorded because it is
the whole reason two of the eleven were uncovered on one side and covered on the other. Anyone
reading the two functions side by side should know the difference is arbitrary.

### One asymmetry that is out of scope and should not be lost

Stripe records both SDK spellings in the map at build time (`_spellings` emits a `python` and a
`typescript` key with a `languages` list); Twilio emits one snake_case key and its adapter
camelises at lookup. Stripe's own docstring argues that direction matters because `_camel` is not
injective — and both modules in fact derive camel from snake, so neither is doing the unsafe
inversion. The difference is *where* the derivation happens, and it belongs to the adapters, which
this task does not own.

## Stripe's `case _:` specifically

**What reaches it** — enumerated by exhausting `_method_name`'s input space rather than guessed:

| `(http_method, is_instance)` | Real today? |
|---|---|
| `("delete", False)` | No. Of v2330's 414 paths, 105 match the resource pattern and **none** is a collection path carrying a `DELETE`. Measured against `tests/fixtures/specs/stripe_v2330_shape.json`, whose path keys are the real set. |
| `("put", …)`, `("patch", …)` | No. Stripe uses `POST` for updates on v1. |
| any object-valued non-method path-item key, e.g. `x-stripe` | Not established for Stripe; **yes for a vendor** — Twilio's `x-twilio` is exactly this shape. |

**Would a new shape arriving there be noticed?** No. It produces a smaller symbol map and nothing
else. `case _` returns `None`, `build_symbol_map` skips at 190, the operation is absent from
`symbols.json`, every call site on it fails to resolve, no finding can be raised against it however
breaking the change is, and the scan reports clean. The only thing anywhere that would react is
`verify_staged_map` refusing a digest mismatch on the corpus path — which fires on any change to
the map and attributes nothing.

Two qualifications, both honest limits rather than reassurance:

- `("delete", False)` does not need Stripe to add a collection `DELETE` to arrive. It also arrives
  when `_addresses_one_resource` reads a singleton wrongly — a path with a `DELETE` and no `GET`,
  or a `GET` whose 200 is not `application/json`. That function's own docstring already argues for
  reading only a positive `$ref`, and this is the cost of that direction: a silent skip rather than
  a collided `retrieve`.
- **Whether real Stripe path items carry non-method keys is not established by any committed
  artifact.** `stripe_v2330_shape.json` holds only `get`, `post` and `delete` across all 414 paths,
  and there is no reduction script for it to say what was dropped — unlike Twilio, where
  `build_twilio_fixtures.py` proves the reduction and the real bytes prove the vendor. Establishing
  it costs one `gh api repos/stripe/openapi/contents/openapi/spec3.json?ref=v2330` and a key
  census. It does not change any assertion here, because the guard is required by the OpenAPI Path
  Item Object regardless of what Stripe currently emits.

## Nothing was judged unreachable, and two statements are redundant

All eleven were reached through `build_symbol_map`, the public entry point of each module, with no
private function called to get at a branch. Four are reachable only from inputs no vendor publishes
— `twilio:110`'s cycle half, `twilio:114`, `twilio:142`, and `stripe:184`'s discriminating half —
and each is recorded as such in the table rather than dressed up as a live case.

Two statements are **redundant in the forward direction** — deleting them changes no observable
answer, verified against the whole suite:

**`twilio:141-142`.** `build_symbol_map` guards `isinstance(body, dict)` and then calls
`_chain(path, paths)`, which re-reads `paths.get(path)` and applies the same check at 110. With
141-142 deleted the full suite is **2299 passed, 2 skipped, exit 0**. The clause that subsumes it
is `_chain`'s `not isinstance(body, dict)`.

**`stripe:143-144`.** `case _: return None` is the last arm of a `match`; Python falls through an
unmatched `match` and `_method_name` returns `None` implicitly. With the arm deleted the full suite
is **2299 passed, 2 skipped, exit 0**. The statement is explicitness, not logic — which is a good
reason to keep it and the reason no mutation that *deletes* it can ever be informative.

Neither was removed. Removing them is a refactor with no defect behind it, and in the Twilio case
it would make the loop's contract implicit at the exact place the two vendors already disagree.

`2026-07-29-typescript-symbol-reader.md` (M3-W91) reached the same verdict on two clauses of the
generated TypeScript reader, independently and on the same day: recorded, not deleted, because it is
a production change no test proves necessary and because the clause makes the code's assumption true
by construction rather than by accident. Three modules, three tasks, one answer.

**One difference from theirs is worth keeping straight, because it changes what a later reader
should try.** Both of M3-W91's survivals were also test weaknesses — a better fixture made both
falsifiable, and both tests were strengthened. Neither of the two here can be made falsifiable by
any fixture. For `twilio:142`, reaching `body.items()` with a non-object body requires getting past
145, which the same input has already stopped; for `stripe:143-144`, Python's implicit `None` is
indistinguishable from the explicit one for every input there is. So nobody should go looking for
the fixture that kills these two. There isn't one.

One statement outside the eleven carries a dead sub-condition, noted because it is the same
species: `_version_prefix` returns `f"/{segments[0]}" if segments and segments[0] else ""`, and
`str.split("/")` never returns an empty list — `"".split("/")` is `[""]` — so `segments and` can
never be false. Line 76 is covered, so it is not this task's to fix.

## Mutation table

Every test here pins existing behaviour, so "fails first" was established by breaking the statement
each covers. Harness at `%TEMP%\w95_mutate.py`, not committed. It runs
`pytest -q --color=no -p no:randomly -n0` over
`tests/test_symbol_map_declines.py tests/test_twilio_adapter.py tests/test_stripe_adapter.py`,
asserts each mutation string matches exactly once, `compile()`s the mutated source before pytest
sees it, and classifies from the summary *counts* rather than from line prefixes. Baseline asserted
green at 72 passed before the run and 72 passed after it, so a survival is distinguishable from a
blind harness.

| # | Statement | Mutation | Outcome | Killed by |
|---|---|---|---|---|
| T-110a | `twilio:110` | body guard dropped — an absent parent reaches `_mount` as `None` | KILLED, 2 failed | `…parent_the_document_does_not_name_drops_the_child…`, `…unresolvable_chain_costs_its_own_path…` |
| T-110a' | `twilio:110` | absent parent coerced to `{}` rather than refused | KILLED, 2 failed | same two |
| T-110b | `twilio:110` | `or path in seen` dropped (cycle guard) | KILLED, 1 failed | `…parent_cycle_yields_no_symbol_instead_of_recursing…` |
| T-114 | `twilio:114` | `_mount` answers `""` rather than `None` | KILLED, 2 failed | `…path_built_only_of_placeholders…`, `…declined_operation_leaves_no_trace…` |
| T-114' | `twilio:114` | statement deleted; the `None` mount is carried into the chain | KILLED, 2 failed | same two |
| T-142 | `twilio:142` | guard deleted | **SURVIVED** | — (also survives the full suite; the clause is redundant) |
| T-142' | `twilio:142` | guard inverted | KILLED, 16 failed | 16 across the new file and `test_twilio_adapter.py` |
| T-145 | `twilio:145` | `continue` → `chain = []`, mounting an unresolvable chain at the top level | KILLED, 5 failed | all four Twilio decline tests plus `…leaves_no_trace…` |
| T-149 | `twilio:149` | guard deleted | KILLED, 1 failed | `…real_vendor_document_carries_path_item_keys_that_are_not_operations` |
| T-156a | `twilio:156` | unverified leading word accepted as its own method name | KILLED, 3 failed | `…naming_no_known_verb…`, `…only_twilio_declines_an_unrecognised_verb…`, `…leaves_no_trace…` |
| T-156b | `twilio:156` | an `operationId` matching no leading word defaults to a verb | KILLED, 1 failed | `…naming_no_known_verb…` |
| S-143 | `stripe:143-144` | `case _` arm deleted | **SURVIVED** | — (Python's implicit `None`; also survives the full suite) |
| S-143' | `stripe:143-144` | unhandled pair named after the HTTP verb | KILLED, 3 failed | `…http_method_stripe_does_not_use…`, `…stable_id_naming_no_verb…`, `…leaves_no_trace…` |
| S-184 | `stripe:184` | guard deleted | KILLED, 1 failed | `…path_item_key_whose_value_is_not_an_object_is_skipped` |
| S-190 | `stripe:190` | `continue` → `pass` | KILLED, 3 failed | `…http_method_stripe_does_not_use…`, `…stable_id_naming_no_verb…`, `…leaves_no_trace…` |
| S-193 | `stripe:193` | `continue` → `pass` | KILLED, 2 failed | `…operation_with_no_operation_id…`, `…leaves_no_trace…` |

14 of 16 killed. Both survivals are the "a later clause subsumes the one being broken" case the
brief predicted, and in both the fault is neither the test nor the code: the statement is genuinely
removable. Naming which clause subsumes it is the result; no test was written to reach either one
artificially.

Nothing failed to compile.

### A fourth false-survival mode, not among the three the brief named

The brief named three: colourised summaries defeating a `FAILED ` prefix scan, a plugin flag
colliding with `-n auto` giving exit 4, and a `SyntaxError` arriving as `ERROR`. The harness
answered all three by construction and then hit a fourth on its first real run.

`S-184` and `S-190` came back **UNREADABLE (exit 1, counts={})** — exit 1 with no output at all.
The cause was in the harness, and it is precisely the defect `CLAUDE.md` warns about:

```
UnicodeDecodeError: 'utf-8' codec can't decode byte 0x97 in position 3014
Exception in thread Thread-1 (_readerthread)
returncode 1  stdout len 0  stderr len 0
```

`subprocess.run(..., text=True, encoding="utf-8")` was passed, which is what `CLAUDE.md` asks for —
and it is the wrong answer when the *child* chooses the encoding. Both modules' docstrings carry em
dashes, pytest renders the failing frame's source, and the child encoded its stdout as cp1252, so
`0x97` arrived where the decoder wanted UTF-8. The exception was raised on the reader thread, never
propagated, and `run` returned with empty output.

**A two-outcome harness scores this as a survival.** Reading only the exit code scores it as a kill
by luck. Both mutations do in fact kill. The fix was to tell the child what to emit
(`PYTHONIOENCODING=utf-8` in its environment) and to keep the decode tolerant
(`errors="replace"`), and the general rule this adds: when reading a subprocess you do not control,
`encoding="utf-8"` is a claim about the child, not a safety measure.

Worth recording beside the other three because the guidance that produced it is guidance this
repository gives on purpose.

## No production code changed, and no defect was found in it

Eleven statements covered, each decline correct for the input that reaches it, and no production
change. Two redundant statements were found and deliberately left. The `AttributeError` asymmetry
and the `registry._prepare_twilio` observation below are reported rather than repaired because both
land outside this task's files.

## Two things for the next task, both outside these files

**`registry._prepare_twilio` merges products with `dict.update`, which silently overwrites.**
Inside one document a symbol claimed twice raises `SymbolCollision`, on the stated ground that an
overwritten operation is unreachable from every call site and nothing reports the loss. Across
documents the same collision is a silent overwrite. `registry.py:467` is
`symbols.update(build_twilio_symbols(head, document.domain, document.version))`. The symbol carries
`domain` and `version`, so two distinct products cannot collide — but the protection is a property
of the configured `ProductDocument` list rather than of the code, and `test_twilio_adapter.py`
already constructs a duplicate registration deliberately for a different purpose. The guard that
exists inside a document does not exist between them.

**`_mount` snake-cases the last literal path segment verbatim, and Twilio's oldest product ends its
segments in `.json`.** `twilio_api_v2010.json` serves paths such as `/2010-04-01/Accounts/{Sid}.json`,
and `_snake("Accounts.json")` is `accounts.json`, which is not what the library exposes.
`x-twilio.mountName` may well cover every affected path — that is exactly what `mountName` is for —
so this is a hypothesis, not a finding: no api_v2010 fixture is committed and nothing here measured
it. It concerns a covered line, so it belongs to a task that owns the fixture set.

## Fixtures and provenance

No new fixture file was created. One committed fixture is read that no other test reads —
`tests/fixtures/twilio/2.3.0/insights_v1.json`, real bytes from `twilio/twilio-oai` at tag `2.3.0`,
fetched by `scripts/build_twilio_fixtures.py` — because it is the only artifact in the repository
carrying the path-item shape row 6 needs, and constructing that shape by hand would have proved
only that the constructor knew what to write.

Everything else is an inline dict at the assertion, matching how both existing vendor test files
state a constructed shape. Nine of the fourteen inputs are malformed or unpublished documents, and
for those the fixture *is* the claim being made; putting them in a file one directory away would
separate the claim from the assertion that rests on it.

No test here calls a vendor API or a model API.
