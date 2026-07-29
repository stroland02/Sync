# Sync — The Coverage Baseline

**Date:** 2026-07-29
**Status:** Measurement. Recorded, reviewed by a human, gated by nothing — the treatment
`2026-07-27-sync-benchmark-gates.md` gives every tier B axis, for the reason it gives.
**Scope:** How much of `src/sync` the default suite executes, which modules are least covered,
and which of those are thin for a reason.

## Why this was measured before anything was hardened

"Harden any module whose tests are thin" sat on the remaining-work list for most of this build
and was never acted on, because nobody had measured which modules were thin. Two attempts used a
proxy — counting how often a module's name appears in the test tree — and the proxy was wrong.
`src/sync/index/dependency_edits.py` reads as 187 lines with a single mention and has eleven
tests, because its test file imports the symbols directly and never names the module.

That proxy failed in the direction that matters. It would have sent someone to harden a
well-tested module while a genuinely thin one went unnoticed, which is the same failure the
benchmark spec's rule exists to prevent: *"The first deliverable is measurement, not
construction."*

## The figure, and how to reproduce it

```
uv add --dev "pytest-cov>=7.0"
uv run pytest -q --cov=sync --cov-report=term-missing:skip-covered
```

**95.71% of 4,916 statements, 211 missed, across 84 files.** Measured at commit `58257f6`,
against a suite of 1,468 passing tests.

Two qualifications travel with that number.

**The end-to-end test is deselected, as it always is.** `addopts` carries `-m 'not e2e'`, so
this figure describes what CI actually runs. Including a test nobody runs by default would
measure a suite that does not exist.

**The denominator is statements, not branches.** A line that executes once with one input counts
as covered whether or not its other outcome was ever taken. Every figure below is therefore an
upper bound on how well the module is exercised.

## The least-covered modules

Ranked by percentage, with statement counts beside them — a 90% figure over 30 statements and
over 300 are different problems, and the percentage alone hides which.

| Module | Covered | Statements | Missed |
|---|---:|---:|---:|
| `telemetry/otlp.py` | 82.9% | 70 | 12 |
| `mcp/server.py` | 85.9% | 92 | 13 |
| `index/python_lang.py` | 88.1% | 278 | 33 |
| `signals/mcp_server/arguments.py` | 88.9% | 36 | 4 |
| `verify/mock_response.py` | 89.2% | 74 | 8 |
| `signals/twilio/symbols.py` | 89.8% | 59 | 6 |
| `verify/replay.py` | 90.0% | 100 | 10 |
| `signals/oasdiff.py` | 91.9% | 62 | 5 |
| `signals/stripe/symbols.py` | 92.1% | 63 | 5 |
| `index/literals.py` | 92.3% | 52 | 4 |
| `signals/mcp_server/snapshot.py` | 93.1% | 29 | 2 |
| `index/typescript.py` | 93.8% | 258 | 16 |

Ranked by absolute gap instead, the order changes and the change is the point:

| Module | Missed | Covered |
|---|---:|---:|
| `index/python_lang.py` | 33 | 88.1% |
| `cli.py` | 18 | 95.0% |
| `index/typescript.py` | 16 | 93.8% |
| `mcp/server.py` | 13 | 85.9% |
| `route/templates.py` | 12 | 94.8% |
| `telemetry/otlp.py` | 12 | 82.9% |
| `verify/replay.py` | 10 | 90.0% |

`cli.py` at 95% hides eighteen unexecuted statements — more than nine of the twelve modules in
the first table have in total. Percentage alone would never have surfaced it.

## Thin for a reason, and thin and not

The line separating these is what a test in this repository is *allowed* to do.
`.claude/rules/test-discipline.md` forbids a vendor API call and a model API call; `CLAUDE.md`
forbids guarding against conditions that cannot occur. So:

- **Correctly thin** means no test this repository permits itself to write could reach the code
  — a process entry point, a running server, a binary that is present on every machine that runs
  the suite.
- **Thin and should not be** means a committed fixture could reach it today, and none does.

Three of the twelve are correctly thin.

**`mcp/server.py`** — eleven of its thirteen missed statements are `main()`: read `SYNC_DSN`,
construct a real `GraphStore`, call `serve`, `raise SystemExit`. Reaching them needs a process
and a database, which is the shape this repository declines to test. The other two are not: the
`except Exception` that keeps a tool fault from taking the session down is reachable with a tool
that raises, and nothing has ever made one.

**`signals/oasdiff.py`** — the five missed statements are the `oasdiff` binary not being found
and a non-zero exit from it. The binary is pinned and present wherever the suite runs, so the
not-found branch cannot fire; forcing it would mean hiding the tool from the process, which
tests the test rather than the code.

**`verify/replay.py`** — `node` absent from `PATH`, and the sixty-second timeout. Both are
environment faults, and the timeout is coverable only by spending a minute of suite time to
watch a clock.

The other nine are thin and should not be, and they share a shape: they are the branches that
answer *cannot establish*. `arguments.py` is four bare `return None`s; `literals.py` four;
`stripe/symbols.py` and `twilio/symbols.py` between them eleven `continue`s over malformed
vendor rows. This repository treats "not established" as load-bearing everywhere — absent
evidence must never read as permission — and a `return None` that has never fired in a test is a
branch nobody has shown behaves.

**`telemetry/otlp.py` is the sharpest case of it.** Every one of its twelve missed statements is
a rejection path in a decoder over untrusted third-party telemetry, and its own docstring names
the two traps: a 64-bit field arrives as a JSON *string*, and a span kind arrives as `3` or as
`"SPAN_KIND_CLIENT"` depending on the exporter, so "a reader that handles one silently discards
most of a real batch". The accepting paths are covered. The discarding ones are not, which means
nothing proves the module rejects what it says it rejects.

## What to harden first

**`src/sync/index/python_lang.py`.**

One module rather than a list, because a list is a way of not choosing.

It is the largest absolute gap — thirty-three statements, half again the next module's — and
unlike every other entry in the first table, what is uncovered there is *capability* rather than
guards. Lines 206-210 and 220-223 are aliased imports: `from stripe import X as Y` and
`import stripe as s`. Lines 308-309 walk a nested dictionary argument. None of that is a
defensive branch; it is indexing, and it has never run.

The asymmetry that made it concrete has since been closed. `tests/fixtures/py/aliased` now
exists alongside `tests/fixtures/ts/aliased`, and `tests/test_python_aliases.py` reads it, so
the Python adapter's alias handling is exercised against a fixture the way the TypeScript
adapter's is. The repair was a fixture rather than a redesign, as this said it would be, and the
figures in the tables above predate it.

And the exposure is new. `PythonAdapter` was wired into the pipeline days ago and was
constructed nowhere before that, so until this week an unmatched Python call site cost nothing.
It now costs a finding: a customer's aliased `import stripe as s` produces no call site, no
finding is raised, and the miss is silent — which the design document's own rule calls the
recoverable half of a mapping failure only because *resolving incorrectly* is worse, not because
missing is free.

Two runners-up, named so the choice is visible rather than implied: `telemetry/otlp.py`, whose
rejection paths are its whole job, and the tool-fault branch in `mcp/server.py`, which is two
statements and an afternoon.

## What coverage does not tell you

This repository has shipped at least seven components that were fully covered by their own tests
and reachable from nothing in `src/`: `GraphStore.set_merge_outcome`, `sync.route.matrix.route()`,
`DeprecationAdapter`, `ingest_payload`, `synthesize_mock_response`, `record_merge_outcome`, and
`PythonAdapter`. Every one had passing tests the whole time it was dead.

**Line coverage would have called all seven healthy**, because a test importing a symbol and
exercising it is exactly what coverage measures. The property it cannot see is whether anything
in production reaches the code at all, and that property is the one that kept failing here.
`scripts/lint_dead_links.py` exists because of it, and it is the gate that catches this class —
not the number above.

So the number is worth what it is worth. It says the suite executes most lines of most modules.
It does not say the assertions are good, that the branches not taken behave, or that a single
line of it is reachable from the entry point. A coverage figure arriving without that sentence
will be trusted more than it deserves.

## Why no threshold

The benchmark spec's rule is general and binds here: *"do not invent a threshold. A gate at an
invented number either fires constantly and gets disabled, or never fires and provides false
assurance."*

CI records the figure and does not gate on it. A percentage that fails a build is a percentage
people write tests to satisfy rather than to test something, and this repository has a rule
about that too: a test that cannot fail is worse than no test. The same is true of a test
written to move a number.

The one gate that would be safe here is the one tier C already names as safe elsewhere: a
directional floor on a deterministic measurement, once there is enough history to say which
movement is a regression and which is noise. There is one measurement. That is not history.
