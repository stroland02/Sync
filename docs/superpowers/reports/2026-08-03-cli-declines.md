# Thirty-one statements on the operator's interface, and the five that report as success

M3-W125. `src/sync/cli.py` was second by exposure in
`docs/superpowers/specs/2026-07-30-sync-coverage-baseline-3.md` and deliberately not named as a
module to harden. This is that task taken up anyway, on the ground the baseline itself gives for
why the instrument has stopped being useful on modules in this shape: the number can say a
statement never ran, and it cannot say what the operator sees when it does.

**No production code changed.** Twenty-eight of the thirty-one statements are now executed by
tests, two are unreachable through any input, and one is invisible to the instrument that
counted it. The one production edit this task's interrupted predecessor left behind was a
mutation probe and was removed rather than kept; `2a15e65` carries why.

## The figure, and how to reproduce it

```
SYNC_DSN=postgresql://sync:sync@localhost:5433/sync_w125 PYTHONIOENCODING=utf-8 \
  uv run pytest -q --cov=sync --cov-report=term-missing --cov-report=json:coverage.json -rs
```

Under `-n auto`, the scheduler `pyproject.toml`'s `addopts` selects, twelve workers on this
machine. `SYNC_DSN` names `sync_w125`, used by nothing else; each worker subdivides it into
`sync_w125_gw<n>` and creates and drops its own, so the pinned name is itself never created and
never dropped.

| | statements | missed | missing lines |
|---|---:|---:|---|
| before | 573 | **31** | 385, 410, 425, 452, 455, 458, 611, 616, 733, 1062, 1063, 1069, 1205, 1210, 1214, 1289, 1380, 1381, 1382, 1503, 1504, 1505, 1509, 1511, 1512, 1557, 1558, 1559, 1657, 1662, 1923 |
| after | 573 | **3** | 611, 616, 1923 |

`src/sync/cli.py` is byte-identical to the baseline's tree at `048e28a`, so the 31 above is the
baseline's own figure re-measured rather than a second number about a different file. The before
row was taken on this branch with `tests/test_cli_declines.py` moved aside and nothing else
changed, which is the only difference between the two runs.

**Note the suite counts, so a later mutation harness does not read the difference as drift.**
This worktree has no `.cache/specs/`, so it reads four skips where the coordinator's populated
checkout reads one. At `da6a820` here: **2,775 passed, 4 skipped**. The coordinator's checkout
reports 2,778 passed and 1 skipped at the same commit, and the two reconcile exactly —
2,775 + 4 = 2,778 + 1 = 2,779. Baseline-3's fourth qualification is the explanation and it has
not changed. On this branch: **2,810 passed, 4 skipped.**

## Every statement, and what the operator sees

The last column is the one this report exists for. The other decline reports on this project ask
what a *caller* observes; this module is the command line, so the question is what a person
receives, and "nothing" is a different kind of answer here than it is inside a detector.

**Distinguishable** means an operator running the command could tell this statement fired from a
run in which nothing was wrong, using only stdout, stderr and the exit code.

| Line | Statement | What reaches it | Right answer? | What the operator sees | Distinguishable |
|---|---|---|---|---|---|
| 385 | `return None` in `_resolve` | a `$ref` naming a schema `components` does not define | yes — the alternative is a declared field with no type | nothing | **no** |
| 410 | `return True` in `_nullable` | the OpenAPI 3.1 spelling, `"type": [..., "null"]` | capability, not decline | nothing | n/a |
| 425 | `continue` in `_walk_schema` | a property whose `$ref` 385 dropped | yes | nothing | **no** |
| 452 | `continue` in `_declared_response_fields` | a `paths` entry that is not an object | yes | nothing | **no** |
| 455 | `continue` | a path-item key that is not an operation (`parameters`, `summary`) | yes | nothing | **no** |
| 458 | `continue` | an operation carrying no `operationId` | yes — nothing downstream can address it | nothing | **no** |
| 611 | the drop message in `_parameter_changes` | nothing; see "unreachable" below | n/a | one stderr line per dropped row, exit code unchanged | partly |
| 616 | `continue` | as 611 | n/a | as 611 | partly |
| 733 | `continue` in the literal pass | `node_modules/` and `*.d.ts` | yes — a deliberate skip | nothing, and correctly not counted as unreadable | n/a |
| 1062 | `_checkout_branch(...)` | a resumed thread whose predecessor died | capability, not decline | the CI verdict describes the right commit | n/a |
| 1063 | `graph.update_state(...)` | as 1062 | capability | as 1062 | n/a |
| 1069 | the discard notice | a dependency tree the previous finding doctored | capability | `discarded the previous finding's dependency tree` on stdout | yes |
| 1205 | the refusal message in `shapes` | `--vendor anthropic` and three others: `GeneratedSpecAdapter` is no `RequestCorrelator` | yes | the reason, on stderr | yes |
| 1210 | `return 2` | as 1205 | yes | exit 2 | yes |
| 1214 | `payload = json.load(sys.stdin)` | `shapes --payload -` | capability | the folded shapes | n/a |
| 1289 | `payload = json.load(sys.stdin)` | `ingest --payload -` | capability | the ingested rows | n/a |
| 1380 | `except WebhookFormatError` | a vouched-for delivery that is not a pull-request event | yes | — | — |
| 1381 | the message | as 1380 | yes — it describes the payload, which the operator must fix | `delivery rejected: <what>` on stderr | yes |
| 1382 | `return 1` | as 1380 | yes | exit 1 | yes |
| 1503 | `key = _signing_key(args.key_file)` | `feed-public-key --key-file` | capability | the key file is honoured | n/a |
| 1504 | `if key is None:` | no key in the environment and no `--key-file` | yes | — | — |
| 1505 | the refusal message | as 1504 | yes | names the environment variable and the flag | yes |
| 1509 | `return 2` | as 1504 | yes | exit 2 | yes |
| 1511 | `print(public_key_bytes(key).hex())` | a usable key | capability | the hex that goes in the diff | n/a |
| 1512 | `return 0` | as 1511 | yes | exit 0 | yes |
| 1557 | `except (KeyError, LookupError, ValueError)` | an incomplete `--score-pair` specification | yes | — | — |
| 1558 | the message | as 1557 | yes | `pair specification: <file> names no <keys>` on stderr | yes |
| 1559 | `return 2` | as 1557 | yes | exit 2, and no report on stdout | yes |
| 1657 | `raise KeyError` | a specification missing `repo`, `vendor`, `cache`, a version or `change` | yes | reaches the operator through 1558 | yes |
| 1662 | `raise KeyError` | a `change` missing `kind`, `operation` or `field` | yes | as 1657 | yes |
| 1923 | `raise SystemExit(main())` | `python -m sync.cli` | capability | every exit code the module produces | yes |

## Yes — five declines report as success, and they are the same five

**Lines 385, 425, 452, 455 and 458 are indistinguishable from a run in which nothing was wrong.**

This is the fourth surface on which this project has found that shape and the first time it has
been checked on the operator's interface. It is not an inference from reading the source. All
five narrow the declared map `ObservedDriftDetector` compares traffic against; an operation any
of them drops never enters `self._spec`, so no shape is queried, no divergence is computed, and
the line `_scan` prints is

```
observed-drift: 0 finding(s), 0 declined
```

`test_an_operation_the_walk_dropped_reports_exactly_what_a_clean_repository_reports` asserts that
string, then scans a vendor with an empty `paths` and asserts the two lines are **equal** rather
than describing the resemblance — so a channel that later distinguished them fails here and is
noticed rather than silently making this report stale.

**The `declined` channel does not close it.** That channel exists precisely to make a silent
decline countable, and it counts divergences a detector saw and did not report. An operation that
never entered the map was never seen, so the channel reads zero for the same reason the finding
count does. This is worth stating plainly because `2026-07-30-declines-that-cost-findings.md`
built that channel to solve this exact problem one layer down, and it does not reach up here.

The contrast is kept in the same file rather than argued:
`test_the_collision_drop_is_printed_where_the_walk_declines_are_not` pins the one decline in this
neighbourhood an operator *can* see — `_declared_fields` prints to stderr when two documents
declare one operation. Same map, same narrowing, opposite visibility.

I am not proposing the fix here. Naming the right channel is a design decision about operator
output with a real noise cost — a specification with fifty non-operation path-item keys would
print fifty lines — and the honest options are a count rather than a line per drop, or reusing
`declined` with its meaning widened. Both are a task, and this one was measurement.

## Two statements unreachable, established by probe rather than by reasoning

`_parameter_changes` (611, 616) names a `ParameterDeprecation` on stderr and drops it when
converting that one row produced anything other than one `VendorChange`. Three kinds of evidence,
matching what `2026-07-29-mutation-engine-declines.md` established for `benchmark/mutate.py`:

- **Structural.** `parameters_to_vendor_changes` is an unfiltered list comprehension over its
  argument — no filter clause, no branch, no early return — and this call site hands it a
  one-element list. The length is one by construction.
- **Empirical.** The three parameter deprecations the committed Anthropic page carries, each
  converted alone the way the call site converts it: three conversions, all length one. That page
  is the whole sample because it is the only shipped source publishing a parameter table, which
  `test_deprecation_wiring.py` measures rather than assumes.
- **Whole suite.** The drop replaced by `raise AssertionError`, full suite run: **2,809 passed,
  4 skipped, exit 0.** Nothing in the suite reaches it.

**What the operator would see if it went live was measured, not read off the source.** With a
converter emitting two rows per input, `_parameter_changes` over the committed page produced:

```
parameter-deprecation: anthropic `temperature` produced 2 vendor change(s); dropped rather than joined to a guess
parameter-deprecation: anthropic `top_p` produced 2 vendor change(s); dropped rather than joined to a guess
parameter-deprecation: anthropic `top_k` produced 2 vendor change(s); dropped rather than joined to a guess
```

Three rows in, zero pairs out, every one named on stderr — and the exit code unchanged, because
`_parameter_changes` returns a list and raises nothing. So it is legible to an operator reading
stderr and invisible to one reading `$?`, which is why the table says *partly*.

**A test was added for this, and it asserts on the converter rather than on the guard.** The
unreachability is a fact about a different module, so it decays the day somebody makes that
converter emit two rows for one deprecation — and nothing here would have noticed; the drop would
simply go live and start discarding rows. `ad97347` is that test, watched red against exactly
that change: `[2, 2, 2] == [1, 1, 1]`.

**Nothing is judged redundant.** Every other statement in the table has an input that reaches it.

## Line 1923, and the instrument that cannot see it

`raise SystemExit(main())` runs only when the module is `__main__`, which no in-process test can
arrange, and a child process's lines are invisible to a coverage run that did not start it under
coverage. It stays in the missing list however hard a test presses on it. That is a property of
the instrument, and it is the caveat baseline-3 records for `mcp/server.py`.

Three tests drive it through a real `python -m sync.cli`. What they establish is what the number
cannot: the guard exists and carries the exit code out. Without it the process runs `main()`
never, exits 0 always, and prints nothing — every refusal reported to a wrapper reading `$?` as
success. That is the most complete instance of this report's own finding, sitting in the two
lines a coverage figure will always call untested.

## The mutation table

Every test here pins existing behaviour, so none was red before the code existed and mutation is
what stands in for that. One mutant at a time, restored after each, each naming the exact text
expected at its line so a mutant that no longer applies raises rather than mutating nothing and
reporting a kill. `PYTHONIOENCODING=utf-8` in the child's environment and `errors="replace"` on
the call, for the reason `CLAUDE.md` gives: this file's docstrings carry em dashes, and a run that
returns exit 1 with no output is read as either a survival or a kill and is neither.

**28 of 28 killed. 3 of 3 controls survived.**

| Line | Mutant | Result | Killed by |
|---|---|---|---|
| 385 | `return None` → `return schema` | killed | `test_a_property_whose_reference_dangles_is_dropped_and_its_siblings_are_kept` |
| 410 | `return True` → `return False` | killed | `test_a_field_nullable_in_the_openapi_31_spelling_is_recorded_as_nullable` |
| 425 | `continue` → `resolved = {}` | killed | `test_a_property_whose_reference_dangles_is_dropped_and_its_siblings_are_kept` |
| 452 | `continue` → `pass` | killed | `test_a_path_whose_value_is_not_an_object_is_skipped_and_its_siblings_resolve` |
| 455 | `continue` → `pass` | killed | `test_a_path_item_key_that_is_not_an_operation_contributes_nothing` |
| 458 | `continue` → `pass` | killed | `test_an_operation_carrying_no_operation_id_declares_nothing` |
| 733 | `continue` → `pass` | killed | `test_the_literal_pass_reads_neither_an_installed_dependency_nor_a_declaration_file` |
| 1062 | `_checkout_branch(...)` deleted | killed | `test_a_resumed_run_polls_the_commit_its_dead_predecessor_pushed` |
| 1063 | `graph.update_state(...)` deleted | killed | `test_a_resumed_run_polls_the_commit_its_dead_predecessor_pushed` |
| 1069 | discard notice deleted | killed | `test_a_discarded_dependency_tree_is_announced_rather_than_done_quietly` |
| 1205 | refusal message → `pass` | killed | `test_shapes_refuses_a_vendor_whose_adapter_cannot_correlate_a_request` |
| 1210 | `return 2` → `return 0` | killed | `test_shapes_refuses_a_vendor_whose_adapter_cannot_correlate_a_request` |
| 1214 | stdin read → `payload = {}` | killed | `test_shapes_reads_a_payload_from_stdin` |
| 1289 | stdin read → `payload = {}` | killed | `test_ingest_reads_a_payload_from_stdin` |
| 1380 | `WebhookFormatError` → `WebhookSignatureError` | killed | `test_a_verified_delivery_that_is_not_a_pull_request_event_is_rejected_by_name` |
| 1381 | message → `pass` | killed | same |
| 1382 | `return 1` → `return 0` | killed | same |
| 1503 | `args.key_file` → `None` | killed | `test_feed_public_key_reads_a_key_file_as_well_as_the_environment` |
| 1504 | `if key is None:` → `if False:` | killed | `test_feed_public_key_refuses_when_there_is_no_usable_key` |
| 1505 | refusal message → `pass` | killed | same |
| 1509 | `return 2` → `return 0` | killed | same |
| 1511 | hex printed truncated | killed | `test_feed_public_key_prints_the_hex_sync_core_keys_holds` |
| 1512 | `return 0` → `return 2` | killed | same |
| 1557 | except clause → `SystemExit` | killed | `test_a_pair_specification_missing_a_top_level_key_is_refused_naming_the_file` |
| 1558 | message → `pass` | killed | same |
| 1559 | `return 2` → `return 0` | killed | same |
| 1657 | `raise KeyError` → `pass` | killed | same |
| 1662 | `raise KeyError` → `pass` | killed | `test_a_pair_specification_whose_change_is_incomplete_is_refused_the_same_way` |

**The controls, and why they are here.** A harness that has never reported a survivor has not
been shown to be able to report one, which is this repository's rule about a test that cannot
fail applied to the instrument rather than to the test.

| Control | Result | Why it must survive |
|---|---|---|
| 611 drop message rewritten | survived | the guard is unreachable; a kill would refute this report |
| 616 `continue` → `pass` | survived | same |
| comment-only edit at 608 | survived | no test can observe a comment, so a kill would mean the harness reports kills it did not measure |

**One mutant was discarded as degenerate and is recorded rather than dropped.** The first form of
the 1205 mutant replaced `print(` with `_ = (`, which makes `file=sys.stderr` a syntax error
inside a tuple. It "died" at import, so the kill was the parser and not a test. It was replaced
with statement deletion — the whole `print(...)` call to `pass` — which is valid Python and dies
against the assertion on stderr. A mutation table reporting the first form would have counted a
test it never ran.

## Does baseline-3's ranking of this module still hold?

**The key held. The prose beside it did not.**

The ranking put `sync/cli.py` second at exposure 31 — 31 missed statements at the `report` weight
of 1 — and then declined to name it, on this reasoning:

> much of the gap is argument handling, `json.load(sys.stdin)`, and one whole key-printing
> subcommand at 1503–1512.

Measured against the statements themselves, that describes **eight of the thirty-one**: the six
of the key-printing subcommand (1503, 1504, 1505, 1509, 1511, 1512) and the two
`json.load(sys.stdin)` reads. The third category, argument handling, adds nothing to the count —
its only uncovered statement is 1503, already inside the subcommand. So the three named
categories cover a quarter of the gap, and "much of the gap" errs in the direction that made the
module easy to skip.

The remaining twenty-one are not report-tier work. They are other packages' work, wired here:

| What the statement actually serves | Lines | Count | Tier the baseline weights that package at |
|---|---|---:|---|
| the declared map `ObservedDriftDetector` reads | 385, 410, 425, 452, 455, 458 | 6 | signal, 3 |
| the literal call-site index | 733 | 1 | signal, 3 |
| folding captured telemetry | 1205, 1210, 1214, 1289 | 4 | signal, 3 |
| the resumed remediation loop | 1062, 1063 | 2 | patch, 4 |
| the merge-outcome webhook | 1380, 1381, 1382 | 3 | record, 2 |
| the benchmark corpus scorer | 1557, 1558, 1559, 1657, 1662 | 5 | record, 2 |
| genuinely a number on a screen | 1069, 1503, 1504, 1505, 1509, 1511, 1512, 611, 616, 1923 | 10 | report, 1 |

Weighting each statement by the package it serves rather than by the file it sits in puts this
module at **exposure 67**, against 31. The result is robust to the assignments worth arguing
about: moving both `json.load(sys.stdin)` reads down to report gives 63, and moving the discard
notice up to patch gives 70. Every version lands the module between `remediate/nodes.py` at 28
and `index/python_lang.py` at 75 — that is, **still second, but more than twice the third-placed
module rather than one point above the fourth.**

So the ordering the baseline published was right and its argument for departing from it was not.
That is a finding about the weighting, and it is the one the baseline invited: it named the
per-package coarseness as the first of three things worth attacking, and said *"the cost of the
coarseness is visible in exactly one row: two of `cli.py`'s uncovered statements (1062–1063)."*
The cost was visible in twenty-one of them, in that one row.

**None of which changes what to do next.** `sync/cli.py` now sits at 3 missed and exposure 3, and
two of those three are unreachable and the third is invisible to the instrument. The module is
closed. `index/python_lang.py` remains first at exposure 75, named first in three consecutive
measurements and hardened once; `index/typescript.py` and `remediate/nodes.py` follow. Baseline-3
named those three and this report does not displace them.

What it does add is a caution for the fourth baseline: **an entry-point module's exposure is not
its package's weight.** `cli.py` is the one file in this tree whose statements mostly do other
packages' work, so it is the one file where per-package weighting is guaranteed to understate.
Either weight it by what its statements serve, or say in the document that its number is a floor.

## What this leaves open

- **The five silent declines have no channel.** Named above, deliberately not built here.
- **`_declared_response_fields` is signal work in the entry point.** Six statements building the
  detector's input live in `cli.py`, which is why they were weighted at 1 and why nobody looked
  at them for three measurements. Whether that walk belongs in `sync/index/` or `sync/detect/` is
  a question this task is not the place to answer, but it is the reason the statements were cheap
  to overlook.
- **The two `--payload -` reads are the operator's route for customer data** and had never been
  driven before this task. They are covered now; nothing asserts what happens when the pipe
  carries something that is not JSON.
