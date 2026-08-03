# Where this session stopped

**Date:** 2026-08-03. Written so a session starting cold can resume without reconstructing
anything from a transcript.

## State of the tree

`main` at `a1075c2`, pushed, working tree clean. CI run `30810733369` is **green** — the first
one this project has had. `2026-08-03-ci-first-green-and-the-gate-that-never-ran.md` carries what
was wrong and what fixed it.

## Done in this session

- `scripts/stage_symbol_map.py` and `tests/test_stage_symbol_map.py` — the symbol map the corpus
  is scored against, rebuilt by a command instead of by prose.
- `tests/test_ci_stages_the_corpus_inputs.py` — asserts every input the scorer reads is staged
  before it runs, by position within the scoring job.
- `.github/workflows/ci.yml` — two staging steps added, and `GH_TOKEN` scoped to the one step
  that shells out to `gh`.
- `tests/test_pipeline_composes.py` — `_why(state)` on the outcome assertions, so a Linux-only
  abandon reports its reason instead of only its symptom.
- `.gitignore` — `corpus-score.json`, which is a measurement of the tree it was taken on.

## Open, in the order it should be picked up

**1. Two red runs that predate the token fix.** The merges `M3-W121` and `M3-W122` failed before
`a1075c2` landed. They may be nothing more than the same `GH_TOKEN` failure, now fixed — re-run
one to find out. They belong to whichever session owns those merges; do not assume.

**2. M4, on the task board.** Four tasks, dependencies already set:

| # | Task | State |
|---|---|---|
| 10 | M4-S — scaffold `web/` (Vite, React 19, Tailwind v4) | ready |
| 11 | M4-T — HTTP transport, `src/sync/api/` | ready |
| 12 | M4-U — the console's three graph levels | blocked by 10 and 11 |
| 13 | M4-V — the Solution Workflow view | blocked by 12 |

`docs/superpowers/plans/2026-07-30-sync-m4-dashboard.md` is the plan; each task's description
is a summary of one of its tasks and the plan is the authority where they differ.

**#10 is the clean hand-off for a second session.** It touches `web/` and `.gitignore` only, so
it cannot collide with any Python work.

## Two things a cold session will otherwise get wrong

**`main` moves under you.** Several sessions push to it. `git log --oneline -3` before
committing; `da6a820` landed between two of this session's pushes.

**A failing corpus score is more often a staging problem than a score.** Check what
`.cache/specs/` holds before reading a refusal as a regression. Re-pinning the symbol map is a
deliberate act with a measurement attached, and `benchmark/corpus/symbol_map.yaml` carries the
rule for it.
