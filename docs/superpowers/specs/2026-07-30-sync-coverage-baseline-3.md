# Sync — The Coverage Baseline, Third Measurement

**Date:** 2026-07-30
**Status:** Measurement. Recorded, reviewed by a human, gated by nothing — the same treatment
`2026-07-27-sync-benchmark-gates.md` gives every tier B axis, for the reason it gives.
**Scope:** How much of `src/sync` the default suite executes at `d615b75`; which modules are worth
hardening *next*, ranked by what a wrong answer in each one costs rather than by percentage; which
of the two earlier baselines' line citations still resolve; and what became of every module either
of them named.
**Supersedes:** `2026-07-29-sync-coverage-baseline.md` (`58257f6`) and
`2026-07-29-sync-coverage-baseline-2.md` (`5c546fa`). Both remain correct records of the trees they
measured and neither is renumbered here, for the reason
`2026-07-29-sync-spec-audit-log-2.md` gives: a measurement half from one tree and half from another
is worse than a dated one.
**No production code changed.** This document is a measurement and a ranked list. It names modules
as thin; hardening them is the work it exists to direct, not work it did.

## The figure, and how to reproduce it

```
uv run pytest -q --cov=sync --cov-report=term-missing --cov-report=json:coverage.json
```

**97.71% of 7,234 statements, 166 missed, across 97 files.** Measured at commit `d615b75`, over a
suite reporting **2,699 passed and 4 skipped in 147.39s, exit 0**, under the `-n auto` scheduler
`pyproject.toml`'s `addopts` selects — twelve workers on this machine. `SYNC_DSN` pointed at
`sync_w118`, a database created for this measurement and used by nothing else.

`--cov-report=json` is the only addition to the command the previous baseline published, and it
changes no figure: it writes the same run in the form `scripts/rank_coverage.py` reads, so the
ranking below is computed from the measurement rather than transcribed from it.

Four qualifications travel with the number, and the fourth is new.

**The end-to-end test is deselected, as it always is.** `addopts` carries `-m 'not e2e'`, so the
figure describes what CI runs.

**The denominator is statements, not branches.** A line that executes once with one input counts as
covered whether or not its other outcome was ever taken, so every figure below is an upper bound on
how well a module is exercised. Sixty-five further statements are excluded outright and appear in
no denominator here.

**Code executed in a subprocess is still invisible to it.** Baseline-2 raised this against
`mcp/server.py`, whose `main()` is driven by `tests/test_mcp_entry_point.py` through a real pipe and
was scored as untested. That module now reads 100% for an unrelated reason — M3-W107 covered the
rest of it — so the caveat no longer distorts this table, but the property has not changed and the
next module tested through a subprocess will read as thin again.

**The suite reports two fewer passes under `--cov` than without it.** The plain gate run at this
commit is 2,701 passed and 2 skipped; the coverage run is 2,699 passed and 4 skipped. Two tests skip
when coverage is on and pass when it is off — the totals agree at 2,703, so nothing is lost, and the
figure above is therefore taken over a suite two tests smaller than the one the gate runs. That is a
small discrepancy and it is stated because a coverage figure quoted beside a test count invites the
reader to assume the two describe the same run.

## What moved, and what a threshold would have made of it

| | statements | missed | covered | files | tests |
|---|---:|---:|---:|---:|---:|
| `58257f6` — baseline 1 | 4,916 | 211 | 95.71% | 84 | 1,468 |
| `5c546fa` — baseline 2 | 5,278 | 235 | 95.55% | 87 | 1,569 |
| `d615b75` — here | 7,234 | 166 | 97.71% | 97 | 2,699 |

Between the second measurement and this one the tree grew by 1,956 statements — 37% — and the
number of statements nothing executes *fell* by 69. That is the first movement in this series large
enough to mean something, and it is not the percentage: the percentage moved 2.16 points, which is
the least interesting number in the table and exactly the one a gate would have been built on.

What produced it is legible in the commit history and is named module by module further down: ten
tasks between `5c546fa` and here read a single module statement by statement, wrote a decline table
for it, and covered what a fixture could reach. Nine of the sixteen modules the two earlier
baselines named are now at 100% or one statement short of it.

## The ranking, and the weighting it rests on

A percentage ranking answers the wrong question, and both earlier baselines said so in prose beside
a table sorted by percentage. This one is sorted by **exposure — missed statements times what being
wrong in that package costs** — computed by `scripts/rank_coverage.py`, which carries the weights
and the argument for each so a reader can disagree with a number rather than with a paragraph.

| Tier | Weight | Packages | Why a wrong answer costs this much |
|---|---:|---|---|
| patch | 4 | `sync/remediate/`, `sync/route/`, `sync/verify/` | These choose, write and gate an edit to a customer's source. The worst case this project has is the one `CLAUDE.md` names — a patch that parses cleanly and means something else — and it is produced here or caught here. `verify/` is weighted with them rather than below them because it is the only thing between a wrong edit and a pull request. |
| signal | 3 | `sync/index/`, `sync/signals/`, `sync/detect/`, `sync/telemetry/` | A silent decline here costs a binding, and a run missing a binding reports clean: the vendor broke, the call site was never found, and nothing distinguishes that from a healthy repository. A decline that resolves *wrongly* is worse and rarer. |
| record | 2 | `sync/core/`, `sync/graph/`, `sync/forge/`, `sync/benchmark/` | These carry what the earlier stages established and publish it. A defect corrupts the record rather than the customer's source — recoverable, but not free: `benchmark/` produces the labels precision and recall are gated on. |
| report | 1 | `sync/cli.py`, `sync/dashboard/`, `sync/mcp/` | A defect costs a number on a screen or a malformed tool response, with an operator reading it. |

Three things about this weighting are worth attacking, and are stated so somebody can.

**It is per package, not per statement.** A package is the coarsest granularity at which the cost
argument is actually true, and the alternative — a weight per module — goes stale the day somebody
splits a file. The cost of the coarseness is visible in exactly one row: two of `cli.py`'s
uncovered statements (1062–1063) check out a branch and write graph state, which is pipeline
wiring and not a number on a screen. Weighted at 1 with the rest of the entry point, they are
under-counted.

**`sync/cli.py` is deliberately the low weight even though it is where the pipeline is wired.** The
wiring failure this project actually keeps having — a component finished, tested, and reachable
from nothing — is invisible to line coverage in *both* directions, and `scripts/lint_dead_links.py`
is the gate for it. Weighting `cli.py` up would be using this instrument to chase a defect it
cannot see.

**`sync/mcp/` at 1 is arguable.** It is the product surface a customer's agent talks to, so a wrong
answer there is a wrong answer delivered to a model rather than to a person. It sits at 1 because a
malformed tool response is observed by the agent that receives it, and `2026-07-30-provenance-on-the-tool-surface.md`
is the case for reading that as recoverable. Anyone who disagrees should raise it to 2 and re-run;
at one missed statement in the whole package it changes no ordering today.

### Every module with something uncovered, ranked

Generated by `uv run python scripts/rank_coverage.py coverage.json`. The last column is added by
hand and is the one that matters most: **examined** means a committed report has already read those
statements one at a time and classified each.

| Module | Tier | Missed | Statements | Covered | Exposure | Already examined? |
|---|---|---:|---:|---:|---:|---|
| `sync/index/python_lang.py` | signal | 25 | 373 | 93% | 75 | **No** |
| `sync/cli.py` | report | 31 | 573 | 95% | 31 | **No** |
| `sync/index/typescript.py` | signal | 10 | 307 | 97% | 30 | **No** |
| `sync/remediate/nodes.py` | patch | 7 | 213 | 97% | 28 | **No** |
| `sync/route/templates.py` | patch | 6 | 229 | 97% | 24 | Yes — `2026-07-30-edit-primitive-declines.md`, all six |
| `sync/signals/generated/symbols_typescript.py` | signal | 8 | 274 | 97% | 24 | Yes — `2026-07-29-typescript-symbol-reader.md`, all eight |
| `sync/signals/registry.py` | signal | 7 | 157 | 96% | 21 | **No** |
| `sync/core/conformance.py` | record | 9 | 287 | 97% | 18 | **No** |
| `sync/benchmark/mutate.py` | record | 8 | 213 | 96% | 16 | Yes — `2026-07-29-mutation-engine-declines.md`, all eight proven unreachable |
| `sync/signals/generated/symbols_speakeasy.py` | signal | 5 | 245 | 98% | 15 | Yes — `2026-07-30-speakeasy-reader-declines.md`, the same five lines |
| `sync/signals/oasdiff.py` | signal | 5 | 69 | 93% | 15 | Partly — four are the correctly-thin binary lookup both earlier baselines named |
| `sync/remediate/parameters.py` | patch | 3 | 58 | 95% | 12 | **No** |
| `sync/signals/generated/adapter.py` | signal | 4 | 142 | 97% | 12 | **No** |
| `sync/signals/sentry/shapes.py` | signal | 4 | 83 | 95% | 12 | **No** |
| `sync/detect/status_rate.py` | signal | 3 | 119 | 97% | 9 | Yes — `2026-07-29-detector-declines.md`, `2026-07-30-declines-that-cost-findings.md` |
| `sync/signals/datadog/shapes.py` | signal | 3 | 87 | 97% | 9 | **No** |
| `sync/signals/deprecations/adapter.py` | signal | 3 | 74 | 96% | 9 | **No** |
| `sync/signals/deprecations/catalogue.py` | signal | 3 | 172 | 98% | 9 | **No** |
| `sync/detect/observed_drift.py` | signal | 2 | 89 | 98% | 6 | Yes — `2026-07-29-detector-declines.md` |
| `sync/index/dependency_edits.py` | signal | 2 | 72 | 97% | 6 | **No** |
| `sync/index/tsc.py` | signal | 2 | 59 | 97% | 6 | **No** |
| `sync/forge/github.py` | record | 2 | 160 | 99% | 4 | **No** |
| `sync/remediate/agent_patch.py` | patch | 1 | 69 | 99% | 4 | **No** |
| `sync/remediate/corpus.py` | patch | 1 | 82 | 99% | 4 | **No** |
| `sync/remediate/tiered.py` | patch | 1 | 98 | 99% | 4 | **No** |
| `sync/verify/mock_response.py` | patch | 1 | 74 | 99% | 4 | **No** |
| `sync/verify/replay.py` | patch | 1 | 104 | 99% | 4 | Partly — the timeout, named correctly thin twice |
| `sync/index/literals.py` | signal | 1 | 52 | 98% | 3 | Yes — `2026-07-29-python-flavour-and-literals.md` |
| `sync/index/shipped_tree.py` | signal | 1 | 55 | 98% | 3 | **No** |
| `sync/signals/generated/manifest.py` | signal | 1 | 71 | 99% | 3 | **No** |
| `sync/signals/generated/symbols.py` | signal | 1 | 176 | 99% | 3 | Yes — `2026-07-29-python-flavour-and-literals.md` |
| `sync/benchmark/score.py` | record | 1 | 80 | 99% | 2 | **No** |
| `sync/core/models.py` | record | 1 | 196 | 99% | 2 | **No** |
| `sync/forge/webhook.py` | record | 1 | 54 | 98% | 2 | **No** |
| `sync/dashboard/queries.py` | report | 1 | 78 | 99% | 1 | **No** |
| `sync/mcp/tools.py` | report | 1 | 93 | 99% | 1 | Yes — `2026-07-30-mcp-tool-surface-declines.md` |

Sixty-one further modules are at 100% and are not ranked, because a ranking of what to harden has
nothing to say about a module with nothing uncovered.

The ordering is stable against the one filter that could have changed it: the top four rows are the
same whether or not the already-examined modules are removed first. `route/templates.py` and
`symbols_typescript.py` would otherwise sit fifth and sixth, and both have been read statement by
statement already.

## What to harden next: three modules, and the reason each

**`src/sync/index/python_lang.py` — 25 missed, exposure 75, the largest by a factor of two.**

It has held that position in all three measurements, and it is the only module that has. Baseline-1
named it and one repair was made — `tests/fixtures/py/aliased` and `tests/test_python_aliases.py`,
recorded in the audit log — which closed the specific asymmetry that document argued from and left
the module thin. Its statement count has grown from 278 to 373 since then and its uncovered count
from 23 to 25.

Eighteen of the twenty-five are literal declines: `return None`, `return False`, `continue`. That
is the shape every decline report on this project has found, and the same instrument applies. The
other seven are not, and two of them are capability rather than guard — line 319–320 renders the
count of declared requirements, and line 867 answers `"mypy"` for a repository that configures it
through a file rather than through `pyproject.toml`.

**`src/sync/index/typescript.py` — 10 missed, exposure 30 — and it should be hardened in the same
task, because one fixture closes a statement in both.**

`python_lang.py:628` and `typescript.py:495` are the same statement in the two indexers:
`_enclosing_scope` walking to the root and returning it. Both docstrings say what reaches it — the
TypeScript one in as many words, *"falls back to `root` for a module-level call, which has no such
ancestor"* — and neither is covered, which means **no fixture in this repository binds a call
result at module scope in either language.** Every response-side fixture wraps its call in a
function. A customer's script that calls `stripe.charges.create` at the top of a file and reads a
field off the result is ordinary, and nothing has ever shown either adapter handles it.

That is the same species of finding as the alias asymmetry baseline-1 opened with, and it is worth
saying that it is *worse*: that one was an asymmetry between the two adapters, visible to anyone
comparing the two fixture directories. This one is symmetric, so comparing the adapters finds
nothing, and only the coverage number points at it.

**`src/sync/remediate/nodes.py` — 7 missed, exposure 28, and the highest cost per statement in the
table.**

Named third rather than `cli.py`, and the ranking is why: `cli.py` outranks it on volume alone at
the lowest weight, while these seven sit on the patch path at the highest. Five of the seven are
two `except Exception` handlers — the ones that turn a fault inside the patch cascade into a
recorded decline instead of an abandoned run — and neither has ever caught anything in a test.
`CLAUDE.md`'s rule about abandoned runs being data rests on exactly those two handlers writing an
`abandon_reason` a router can learn from, and nothing has shown either one writes it.

The remaining two (342, 347) are the message rendered when a patched call path fails replay, which
is the sentence a human reads on a declined finding.

**`sync/cli.py` is second by exposure and is deliberately not named here.** Thirty-one statements is
the largest raw gap in the tree and has been in all three measurements, but the module is the
command line: much of the gap is argument handling, `json.load(sys.stdin)`, and one whole
key-printing subcommand at 1503–1512. It is worth a task; it is not worth the *next* task, and this
is the disagreement the weighting exists to make explicit rather than to hide.

## Where coverage has nothing left to tell you, and what would

**Forty-eight per cent of the missed statements in this tree are literal declines** — 79 of 166 are
a bare `continue`, `pass`, `return None`, `return False`, `return []`, `return {}` or `return ()`.
In the two indexers at the top of the ranking the proportion is higher: 18 of 25 and 8 of 10.

For a module in that shape, the coverage number has already told you everything it can. It says a
`return None` never ran. It cannot say whether the `return None` is right, what input reaches it,
or what the caller sees when it fires — and this project has now measured, ten times, that the
answer to the last question is usually **nothing at all**. `2026-07-29-hand-written-symbol-maps.md`
found eleven declines and eleven times "the caller observes nothing";
`2026-07-30-declines-that-cost-findings.md` found eight that cost a finding and one that costs
nothing, which is the first time the answer differed.

Worse, a covered decline is not a tested one. A `continue` that some distant test perturbs for an
unrelated reason reads as covered and is checked by nothing, and the ten reports above found this
repeatedly — `2026-07-29-hand-written-symbol-maps.md`'s row 6 is a guard that was uncovered only
because a *fixture reduction script* deleted its input, and the same file names a covered line
carrying a sub-condition that can never be false.

So for these modules the instrument to reach for is not more coverage. It is the one this project
has converged on independently in ten tasks and which
`docs/superpowers/reports/2026-07-29-hand-written-symbol-maps.md` gives the canonical shape of:

- **A decline table.** One row per uncovered statement: the statement, the input that reaches it,
  whether declining is the right answer for that input, and what the caller observes. The fourth
  column is the one that produces findings; three separate reports found a decline no downstream
  artifact could count.
- **A mutation pass over the statements the table covers**, to establish that the tests added are
  not vacuous. Every one of these reports pins existing behaviour, so no test in them was red
  before the code existed, and mutation is what stands in for that.
- **A named fixture for the input**, where one exists. `python_lang.py:628` and
  `typescript.py:495` need a module-scope call site, and that is a fixture, not a redesign — the
  same answer baseline-1 reached about the alias gap.

`sync/benchmark/mutate.py` is the clearest case of coverage having stopped being informative.
It sits ninth in the ranking at eight missed statements, and all eight were proven unreachable by
three independent kinds of evidence — structural, empirical over 372 committed source files, and a
whole-suite run with all eight replaced by `raise AssertionError`. Nothing will ever cover them and
nobody should try. The ranking cannot know that, which is why the last column of the table exists.

## The previous baselines' line citations, and which still resolve

The spec audit named one broken citation and declined to renumber it. There are nine in the two
documents. **Eight no longer resolve; one does.**

| Citation | Document | What it described | What sits there at `d615b75` | Where the construct lives now |
|---|---|---|---|---|
| `index/python_lang.py:206-210` | baseline 1 | `from stripe import X as Y` | the vendor-binding constructor reading `distribution` | 437–443 |
| `index/python_lang.py:220-223` | baseline 1 | `import stripe as s` | a comment and `self._symbol_root` | 453–456 |
| `index/python_lang.py:308-309` | baseline 1 | walking a nested dictionary argument | an error-message f-string | `_dictionary_paths`, 562–585, called from 609–612 |
| `mcp/server.py:88` | baseline 2 | the `continue` on a blank line in the stream | `for line in source:` | 90 |
| `mcp/server.py:200-201` | baseline 2 | the `except Exception` tool-fault guard | `return _result(` | 225 |
| `signals/oasdiff.py:26-29` | baseline 2 | the binary not being found | a comment on exit levels | 49–52 |
| `signals/oasdiff.py:72` | baseline 2 | a non-zero exit from the binary | `_parse_json(result.stdout, ...)` | 70–71 |
| `verify/replay.py:221` | baseline 2 | `node` absent from `PATH` | **`if node is None:`** | **221 — resolves** |
| `verify/replay.py:344-345` | baseline 2 | the sixty-second timeout | `env=_environment(...)` | 350–351 |

One correction to the audit log, which is a fact about how fast this drifts rather than a fault in
the audit. Its replacement reading — that `python_lang.py:206-210` *"is now a set comprehension
inside `_bindings_for`"* — was true at `0613da2` and is not true here: `_bindings_for` no longer
exists anywhere in the file. A citation and its correction both went stale inside one day.

**This is the argument for a successor rather than an edit, and it is stronger than the audit could
state it.** Eight of nine citations moved in 411 commits. Renumbering them would have produced a
document whose tables were measured at one commit and whose line ranges pointed at another, which
is the failure mode the audit refused and was right to refuse.

## Every module the two earlier baselines named, and what happened to it

Sixteen modules were named across the two documents. **None is gone; every file still exists.**
Nine are at 100% or one statement short of it, two have had every remaining statement classified by
a committed report, and five still carry uncovered statements nobody has read.

| Module | `58257f6` | `5c546fa` | `d615b75` | Fate |
|---|---|---|---|---|
| `telemetry/otlp.py` | 83%, 12 missed | 83%, 12 missed | **100%**, 0 | Repaired by baseline-2's own task, thirteen tests, each proven non-vacuous by mutation |
| `mcp/server.py` | 86%, 13 | 82%, 17 | **100%**, 0 | Repaired — `2026-07-30-mcp-tool-surface-declines.md` (M3-W107) |
| `signals/mcp_server/arguments.py` | 89%, 4 | 89%, 4 | **100%**, 0 | Repaired — `2026-07-29-mcp-signal-refusals.md` |
| `signals/mcp_server/snapshot.py` | 93%, 2 | — | **100%**, 0 | Repaired — same report |
| `signals/twilio/symbols.py` | 90%, 6 | 90%, 6 | **100%**, 0 | Repaired — `2026-07-29-hand-written-symbol-maps.md` (M3-W95) |
| `signals/stripe/symbols.py` | 92%, 5 | 92%, 5 | **100%**, 0 | Repaired — same report |
| `verify/mock_response.py` | 89%, 8 | 89%, 8 | 99%, 1 | Repaired but for one statement |
| `verify/replay.py` | 90%, 10 | 90%, 10 | 99%, 1 | Repaired but for the sixty-second timeout, which both earlier documents called correctly thin |
| `index/literals.py` | 92%, 4 | 92%, 4 | 98%, 1 | Repaired — `2026-07-29-python-flavour-and-literals.md`; the remaining statement is that report's |
| `benchmark/mutate.py` | — | 92%, 12 | 96%, 8 | **Closed.** All eight remaining proven unreachable — `2026-07-29-mutation-engine-declines.md` |
| `route/templates.py` | 95%, 12 | 95%, 12 | 97%, 6 | **Closed.** All six examined and classified — `2026-07-30-edit-primitive-declines.md` |
| `index/typescript.py` | 94%, 16 | 93%, 18 | 97%, 10 | Improved; still thin, third in the ranking, and shares a statement with the module below |
| `index/python_lang.py` | 88%, 33 | 92%, 23 | 93%, 25 | **Still thin, and first in the ranking for the third time.** One repair made (the alias fixture); the rest never taken up |
| `core/conformance.py` | — | 88%, 5 | 97%, 9 | Grew from 43 to 287 statements and stayed roughly as thin proportionally. Still unexamined |
| `signals/oasdiff.py` | 92%, 5 | 92%, 5 | 93%, 5 | Unchanged in three measurements. Four of the five are the binary lookup both baselines called correctly thin; the fifth is a non-zero exit from `oasdiff checks`, which a fixture reaches |
| `cli.py` | 95%, 18 | 94%, 27 | 95%, 31 | Grew with the tree. Largest raw gap in all three measurements and never acted on |

**So the recommendations were tracked, and this is the first of the three baselines that can say
so.** Baseline-1 named one module to harden and its repair is recorded in the audit log. Baseline-2
named one and hardened it in the same task. The eleven repairs above were mostly not made *because*
a baseline asked for them — they were made by tasks reading one module at a time — but the
overlap is near total, and the two modules the baselines named that nobody took up are exactly the
two still at the top of this ranking.

That is the honest reading, and it has one uncomfortable half. `index/python_lang.py` has been
named first in three consecutive measurements over 435 commits and has been hardened once, in a way
that closed the specific example the document argued from rather than the module. A baseline whose
top recommendation survives three of its own successors is a document being read and not acted on.

## The `--cov` trap, and whether this measurement hit it

**No measurement in this document used a dotted `--cov` argument.** Every figure comes from
`--cov=sync`, and there are no per-module runs.

That matters because a per-module coverage run on this project can fail for a reason that has
nothing to do with the module. `2026-07-29-psycopg-error-identity.md` established the mechanism, and
it survived one retraction that was itself wrong, so it was re-verified here at `d615b75` against
the installed `coverage 7.15.2` rather than cited:

```
--cov=sync                   : 0 psycopg modules imported inside sys_modules_saved(), 0 evicted
--cov=sync.benchmark.mutate  : 77 imported, 77 evicted on restore
                               psycopg.Error is the same class          = False
                               isinstance(first-set exc, psycopg.Error) = False
                               isinstance(first-set exc, first Error)   = True
```

0.85 s, no pytest involved. `coverage.inorout` resolves a dotted source argument by importing it
inside `coverage.misc.sys_modules_saved()`, whose `restore()` deletes every module the import added;
`psycopg/errors.py` is pure Python and re-executes into a second set of exception classes, while
the `psycopg_binary._psycopg` extension is cached below `sys.modules`, is not re-executed, and goes
on raising the first set. `--cov=sync` names a package that imports no psycopg, so nothing is
evicted and nothing splits.

**Anyone taking a per-module figure to check one of the modules named above should expect this and
say whether their run was clean.** A dotted `--cov` is exactly the natural way to measure a single
module, which is what makes the trap expensive: it fires on the measurement, not on the code, and
the resulting red test is attributed to whatever was being measured.

## What this number still cannot see

Unchanged from both earlier baselines, and restated because it has not stopped being true.

Line coverage cannot see whether anything in production reaches the code at all. Seven components
shipped here fully covered and reachable from nothing, and a line count called every one of them
healthy; an eighth arrived in the commit that added it. `scripts/lint_dead_links.py` is the gate
that catches that class, and the number above is not.

Nor can it see whether an assertion is any good. Ten decline reports on this project reached the
same conclusion from ten different modules: the statements a coverage number points at are the
cheap half of the question, and the expensive half — what the caller observes when the decline
fires — is invisible to it in both directions.

So the figure is worth what it is worth. It says the suite executes most lines of most modules. It
does not say the assertions are good, that the branches not taken behave, or that a line of it is
reachable from an entry point. A 97%-plus figure arriving without that sentence will be trusted
further than it deserves.

## Why no threshold, a third time

`2026-07-27-sync-benchmark-gates.md` binds: *"do not invent a threshold. A gate at an invented
number either fires constantly and gets disabled, or never fires and provides false assurance."* CI
records the figure with `|| true` and gates on nothing, which is correct and was left alone.

There are now three measurements, at `58257f6`, `5c546fa` and `d615b75`. Three points are the
beginning of a history rather than a history, and this measurement finally moved by more than the
noise the second one had to account for — 2.16 points, against a run-to-run variation baseline-2
measured at three statements. So the objection is no longer that the signal is smaller than the
noise.

It is now the other objection, and it is the stronger one. **The exposure column in this document is
a ranking key, and turning a ranking key into a floor is how it stops measuring.** A percentage that
fails a build is a percentage people write tests to satisfy, and this repository's rule about a test
that cannot fail applies exactly as well to a test written to move a number. The gate tier C
describes as safe — a directional floor on a deterministic measurement — is still the only one that
would be safe here, and what it would floor is the count of *unexamined* uncovered statements, not
the percentage. That is a number a decline table moves and a vacuous test does not, and it is worth
building only once somebody has written the fourth of these documents and can say whether the
column above went up or down.
