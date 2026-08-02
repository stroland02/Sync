# Sync — The Coverage Baseline, Re-measured

> **Superseded 2026-08-02 by `2026-07-30-sync-coverage-baseline-3.md`**, which re-measures the
> tree at `048e28a`. Nothing below is renumbered, for the reason this document itself gives about
> its predecessor. Read the figures and the line citations here as pinned to `5c546fa`. Five of
> this document's six per-module line citations have since moved; `verify/replay.py:221` is the
> one that still resolves. The successor tabulates all nine across both documents.

**Date:** 2026-07-29
**Status:** Measurement. Recorded, reviewed by a human, gated by nothing — the same treatment
`2026-07-27-sync-benchmark-gates.md` gives every tier B axis, for the reason it gives.
**Scope:** How much of `src/sync` the default suite executes at `5c546fa`, which modules are
least covered, which of those are thin for a reason, and the one that was hardened.
**Supersedes:** `2026-07-29-sync-coverage-baseline.md`, which remains a correct record of what
was true at `58257f6` and is not edited. Its per-module line citations have moved with the code
— `index/python_lang.py:206-210` is a set comprehension inside `_bindings_for` now, not the
aliased-import handling described there — and the spec audit declined to renumber them without
re-running the measurement, because half a figure from one tree and half from another is worse
than a dated one.

## The figure, and how to reproduce it

```
uv run pytest -q --cov=sync --cov-report=term-missing
```

**95.55% of 5,278 statements, 235 missed, across 87 files.** Measured at commit `5c546fa`, with
`SYNC_DSN` pointed at a database no other task was using. That is the measurement this document
records and the one the tables below describe: the tree before this task touched it.

After the hardening described further down, the same command over the same tree plus thirteen
tests reports **95.76%, 224 missed, over 1,569 passing tests.** Eleven statements, all of them
in the one module named below. The two figures are kept apart deliberately: a measurement that
silently includes the repair it motivated cannot be compared with the one before it.

The previous baseline recorded 95.71% of 4,916 statements at `58257f6` over 1,468 tests. So 362
statements of new code arrived and the percentage moved by sixteen hundredths of a point,
downward — which is the least interesting fact here and exactly the one a threshold would have
been built on.

Three qualifications travel with the number, one of them new.

**The end-to-end test is deselected, as it always is.** `addopts` carries `-m 'not e2e'`, so the
figure describes what CI runs.

**The denominator is statements, not branches.** A line that executes once with one input counts
as covered whether or not its other outcome was ever taken. Every figure below is an upper
bound on how well the module is exercised.

**Code executed in a subprocess is invisible to it.** This is new, and it changes one of the
previous baseline's verdicts. `mcp/server.py:main()` was called correctly thin because reaching
it needs a process and a database — but `tests/test_mcp_entry_point.py` now starts `sync-mcp`
as a subprocess and drives the real `main()` through the real transport, and coverage sees none
of it, because it measures the process it runs in. The module reads as the least-covered file
in the tree and is one of the better-tested ones. A figure that cannot tell an untested function
from one tested through a pipe is not measuring what its readers assume.

**The measurement is noisy against a shared database.** The first run of this command reported
238 missed with fourteen errors in tests that write to Postgres — a freshly created database,
several xdist workers, and other tasks on the same server. The second reported 235 with two such
errors, and the post-hardening run had none. A single unrelated test also failed once under
parallel load and passed both in isolation and on the next full run. So the 235 above is the
better of two imperfect runs, three statements of it are attributable to tests that errored
rather than to code nobody exercises, and a coverage number taken from a run that did not finish
is a number over a suite that does not exist. Saying so is the difference between a measurement
and a decoration.

## The least-covered modules

Ranked by percentage, with statement counts beside them, because 88% over 43 statements and over
430 are different problems. Both tables describe the tree at `5c546fa`, before the hardening
below — `telemetry/otlp.py` reads 83% here and 100% after it.

| Module | Covered | Statements | Missed |
|---|---:|---:|---:|
| `mcp/server.py` | 82% | 96 | 17 |
| `telemetry/otlp.py` | 83% | 70 | 12 |
| `core/conformance.py` | 88% | 43 | 5 |
| `signals/mcp_server/arguments.py` | 89% | 36 | 4 |
| `verify/mock_response.py` | 89% | 74 | 8 |
| `signals/twilio/symbols.py` | 90% | 59 | 6 |
| `verify/replay.py` | 90% | 100 | 10 |
| `benchmark/mutate.py` | 92% | 144 | 12 |
| `index/literals.py` | 92% | 52 | 4 |
| `index/python_lang.py` | 92% | 300 | 23 |
| `signals/oasdiff.py` | 92% | 62 | 5 |
| `signals/stripe/symbols.py` | 92% | 63 | 5 |

Ranked by absolute gap the order changes, and the change is again the point:

| Module | Missed | Covered |
|---|---:|---:|
| `cli.py` | 27 | 94% |
| `index/python_lang.py` | 23 | 92% |
| `index/typescript.py` | 18 | 93% |
| `mcp/server.py` | 17 | 82% |
| `telemetry/otlp.py` | 12 | 83% |
| `benchmark/mutate.py` | 12 | 92% |
| `route/templates.py` | 12 | 95% |
| `verify/replay.py` | 10 | 90% |

`cli.py` at 94% carries twenty-seven unexecuted statements, more than any module in the first
table has in total, and it is forbidden to this task — the same shape the previous baseline
found, one commit range later.

## Thin for a reason, and thin and not

The line separating them is what a test in this repository is *allowed* to do.
`.claude/rules/test-discipline.md` forbids a vendor API call and a model API call; `CLAUDE.md`
forbids guarding against conditions that cannot occur. **Correctly thin** means no permitted
test could reach the code. **Thin and should not be** means a committed fixture could reach it
today and none does.

The verdicts were re-derived against this tree rather than inherited. **No module in the table
is correctly thin in its entirety. Three carry correctly-thin regions**, and they are the same
three the previous baseline named — which is itself a finding: 105 commits of new code added no
new category of untestable branch, and everything else in the table is a branch a fixture could
reach.

**`mcp/server.py`** — eleven of seventeen are `main()`: read `SYNC_DSN`, build a `GraphStore`,
serve, `raise SystemExit`. Correctly thin *as measured*, and see the subprocess caveat above:
they are executed on every run, in a child process. The other six are not thin for any reason.
Line 88 is the `continue` on a blank line in the stream, and lines 200-201 are the
`except Exception` that keeps a tool fault from taking the session down — reachable with a tool
that raises, and nothing has ever made one.

**`signals/oasdiff.py`** — lines 26-29 are the `oasdiff` binary not being found. It is pinned
and present wherever the suite runs, so the branch cannot fire; forcing it means hiding a tool
from the process, which tests the test. Line 72, a non-zero exit from the binary, is *not* in
that category: a committed malformed spec pair reaches it without calling any vendor.

**`verify/replay.py`** — `node` absent from `PATH` (221) and the sixty-second timeout (344-345)
are environment faults, and the second is coverable only by spending a minute of suite time
watching a clock. The other six are a shape-merge branch and two JSON-decode failures, all
reachable from a fixture.

The remaining nine share the shape the previous baseline named, and it has not changed:
they are the branches that answer *cannot establish*. `arguments.py` is four bare `return None`.
`stripe/symbols.py` and `twilio/symbols.py` are between them nine `continue`s over malformed
vendor rows and a `case _`. `index/literals.py` is an `except Exception` over a file that does
not parse — which its own comment says is ordinary in a customer repository. This project treats
"not established" as load-bearing everywhere, because absent evidence must never read as
permission, and a `return None` that has never fired in a test is a branch nobody has shown
behaves.

`benchmark/mutate.py` is new this week and enters the table at 92%: its twelve are the
`return None`s that decline a call site the mutation cannot attach to. It is also the module the
dead-link lint currently names, which is the more useful fact about it.

## What was hardened: `src/sync/telemetry/otlp.py`

One module rather than a list, because a list is a way of not choosing.

It is the lowest-covered module in the tree whose gap is not an entry point — `mcp/server.py`
sits below it only because coverage cannot see a subprocess. And what is uncovered there is not
incidental: **every one of its twelve missed statements is a rejection or a fallback in a
decoder over telemetry a customer's collector sends.** The accepting paths were covered; nothing
proved the module rejects what its docstring says it rejects.

That docstring names the two traps itself — a 64-bit field arrives as a JSON *string*, and a
span kind arrives as `3` or as `"SPAN_KIND_CLIENT"` depending on the exporter, so "a reader that
handles one silently discards most of a real batch". One of the uncovered lines was the *other*
half of the first trap: the branch accepting the JSON-number form of a 64-bit field, which the
docstring promises and which had never run. The rest were the malformed-input paths, and the
consequence of any of them being wrong is a fabricated row: a status code invented from a
malformed attribute feeds the status-rate detector, which decides whether a vendor is failing.

Thirteen tests were added to `tests/test_otlp_spans.py`, taking the module from **83% to 100%**.
They assert what the decoder yields, never that a line ran.

Two honest notes about them. They are characterization tests over behaviour that already
existed, so none was red before the code was written — the code was already right. Each was
proven non-vacuous by mutation instead: the guard broken, the test watched to fail, the guard
restored, the file confirmed byte-identical afterwards.

| Mutation | Test that caught it |
|---|---|
| The JSON-number form of a 64-bit field is rejected | `..._status_code_written_as_a_json_number_is_read` |
| A non-numeric string becomes a status code of `0` | `..._not_a_number_reads_as_absent...` |
| A bare scalar is read where an AnyValue belongs | `..._not_an_any_value_is_treated_as_absent` |
| An `arrayValue` is stringified rather than declined | `..._array_valued_attribute_is_treated_as_absent...` |
| A span with no start time is dated to the epoch | `..._no_start_time_is_skipped`, `..._start_time_that_is_not_a_number...` |
| A span with an empty trace or span id is accepted | `..._span_with_no_identity_is_skipped` |
| A malformed resource entry discards the batch around it | `..._resource_entry_that_is_not_an_object...` |
| A malformed scope entry discards the spans beside it | `..._scope_entry_that_is_not_an_object...` |
| An absent `server.address` is left empty rather than recovered | `..._falls_back_to_the_host_in_the_url` |
| A `doubleValue` status code is truncated to an integer | `..._floating_point_value_reads_as_absent` |

Ten mutations, ten caught, and the source restored unchanged after each.

## What this number cannot see

The same caveat the previous baseline ended on, restated for this tree because it has not
stopped being true.

Line coverage cannot see whether anything in production reaches the code at all. Seven
components shipped here fully covered and reachable from nothing, and a line count called every
one of them healthy. `scripts/lint_dead_links.py` is the gate that catches that class, and at
this commit it names one thing: `benchmark/mutate.py`'s two public functions, which are finished,
tested, and waiting on the scorer that will consume them. That is now recorded on the definitions
themselves with the reason, so it disappears in the commit that wires them.

So the figure is worth what it is worth. It says the suite executes most lines of most modules.
It does not say the assertions are good, that the branches not taken behave, or that a line of
it is reachable from an entry point. A 95%-plus figure arriving without that sentence will be
trusted further than it deserves.

## Why no threshold, again

`2026-07-27-sync-benchmark-gates.md` binds: *"do not invent a threshold. A gate at an invented
number either fires constantly and gets disabled, or never fires and provides false
assurance."* CI records the figure with `|| true` and gates on nothing, which is correct and
was left alone.

There are now two measurements, at `58257f6` and `5c546fa`. Two points are not a history, and
the movement between them — 95.71% to 95.76% — is smaller than the noise this document had to
account for to produce the second one. The gate tier C describes as safe, a directional floor on
a deterministic measurement, needs a measurement that is deterministic. This one is not yet:
until the database contention above is separated from the signal, a floor would fire on which
other task happened to be running.
