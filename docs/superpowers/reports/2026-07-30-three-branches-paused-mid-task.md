# Three branches paused mid-task, and exactly where each stopped

**Date:** 2026-07-30
**Why this exists:** M3-W113, M3-W114 and M3-W115 were all cut off at once by a weekly account
limit that resets **2026-08-04 03:00 ET**. That is five days, which is long enough that nobody —
including the coordinator that dispatched them — will remember the state from context. Each branch
holds unreviewed work with no mutation table and no gate run, and none is merged.

**Do not merge any of these three branches as they stand.** Each preservation commit says so, and
this file says why.

## The three

| Task | Branch | Preservation commit | Diff against `main` | Stopped at |
|---|---|---|---|---|
| M3-W113 | `stroland02/m1-store` | `24e86f1` | 3 files, +140/−17 | proven RED, starting the fix |
| M3-W114 | `stroland02/m1-static-gate` | `ab590f3` | 3 files, +432/−27 | mid-analysis of five call sites |
| M3-W115 | `stroland02/m2-symbols` | `30547bc` | 5 files, +460/−181 | mid-fix, its own test having caught a leak |

Briefs are at `C:\Users\strol\.claude\jobs\51473d2f\tmp\w113.md`, `w114.md`, `w115.md`.

### M3-W113 — the accept predicate and the rule builder read different keys

`LiteralSwapRemediator.can_handle` accepts on `_replacement(change) is not None` alone;
`model_literal_swap` requires `model_id` too, with no fallback, and returns `[]` without it. So a
deprecation carrying only the replacement is accepted, builds zero rules, writes nothing — and the
empty diff reads as *already migrated*. The rationale hides it by falling back to `operation_id`,
so an operator reads a confident sentence naming a model with an empty rule list behind it.

Its last line before the cut was **"GREEN — implement in `literal_swap.py`"**, so the RED existed
and was proven. The diff already touches `literal_swap.py` and two test files.

**Open question it had not answered:** whether to widen `can_handle` or make `propose` refuse.
Those are different contracts — one sends the finding down the cascade, the other abandons with a
reason — and the brief asks what each does to the attempt budget. It also owes the check of whether
the other three codemods share the asymmetry.

### M3-W114 — a computed key reads as absent, and the pipeline calls that agreement

`create({ ['receipt_email']: 'x' })` reads as absent to both position-scoped primitives, so
`PropertyOmitRemediator` reports the customer's code already agrees with the vendor. A wrong answer,
not a missing one.

The constraint it was working under, from M3-W110: `_pair_part` has four call sites, one of which
`rename_parameter` uses to locate the node it rewrites, so a naive strip would make a rename
silently rewrite `['receipt_email']` into `receipt_email` in source the customer wrote. **The reader
and the rewriter want different answers from the same helper**, and finding where that split belongs
is the task. Its last line — "now the five key-comparison call sites and the two declines" — says it
was enumerating exactly that, and had found five rather than the four the brief named.

**Unresolved:** where the split lands. Its diff already changes `templates.py` by 112 lines, so a
position exists in the tree but has not been justified in a report or defended by mutation.

### M3-W115 — the shared grammar, and the leak its own test caught

This one is furthest along and the most interesting. It took **option 1** — extracting the parser
facts into a shared module — and the new file is
`src/sync/signals/generated/typescript_grammar.py`, 99 lines, with a 267-line test beside it.

Its last line is the reason to be glad it committed as it went:

> The test caught a real leak — my own docstring named a generator's helper. Fixing the module, not
> the test.

That is the failure the task existed to prevent, caught by the thing the task built, and it was
correcting the module rather than weakening the assertion. **Whether the leak is fully fixed is
unknown** — that is where the limit landed.

**Unresolved:** the full classification of both readers' helpers into parser facts and generator
facts, which the brief calls the deliverable rather than the refactor; and whether the two pinned
invariants still hold — the Speakeasy parameter reduction's measured inertness, and `_comparable`
never reaching a binding.

## What was checked before committing each

`827eee0` earlier this day captured a probe's `raise AssertionError` into `src/` because the suite
stayed green around an unreachable statement, and it took a later task to notice. All three
preservation commits here were checked for injected probe markers in their `src/` diffs first; none
carried one.

## Resuming

Each agent is resumable by name from its transcript, so the work does not have to be re-derived.
Whoever resumes should tell each one three things:

1. **Re-run anything that was in flight.** All three were mid-measurement, and a result nobody can
   see is one nobody can report.
2. **Merge `origin/main` before gating.** It was `0 0` at 2684 passed when they stopped; five days
   is long enough that this will be stale.
3. **The preservation commit stays in history unamended**, as the record of where the interruption
   fell.

`main` itself is unaffected: `0 0` against origin, 2684 passed, 4 skipped, four gates green.
