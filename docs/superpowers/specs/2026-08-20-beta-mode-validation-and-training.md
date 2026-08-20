# Beta mode: validation, retrieval, and the overnight loop

Owner directive, 2026-08-19 (evening): enter full testing-and-running mode. Run real scenarios
against demo-v1, compare each resolution against what a correct fix looks like, keep training the
solution workflow, and keep the results visible in the console until the demo. Autonomy granted:
land to main, spend model tokens on test runs, open pull requests on `stroland02/demo-v1`.

## What beta mode is

Four capabilities, in dependency order:

1. **The executor** (`sync tickets`, this session): the console's request button becomes a run.
   Landed with the store loaders (`get_finding`, `stamp_ticket_thread`) and wiring tests.
2. **The validation harness**: a scenario is a deliberately broken state of demo-v1 plus a
   statement of what a correct resolution changes. A run is scored by comparing the PR's diff
   against that statement — did it touch the right call sites, did it verify, did it avoid
   collateral edits. Scores are rows, not prose: `migration_outcome` already has the grain
   (one row per attempt), so validation writes there and the console reads what it already reads.
3. **Retrieval into the remediator** (owner ruling: corpus + vendor docs). `build_remediator`
   already takes `repo_context`; the retrieval layer widens what flows into that context:
   the migration corpus rows nearest the finding's change kind, and the vendor's own migration
   notes for the from→to version pair. Nearest-by-change-kind first; embeddings only if the
   corpus outgrows exact-match joins. Build for the case that exists.
4. **The overnight loop**: a self-resuming cycle (ScheduleWakeup) that seeds a scenario, requests
   a ticket, executes it, scores the result, syncs `main` ↔ the dev tree, and updates the beta
   report. It survives the operator's usage-window resets because each wakeup re-enters with
   the ledger on disk, not the transcript.

## Scenario shapes (first set)

- **S1 removed-field**: demo-v1 reads a response field the vendor change removed. Correct
  resolution stops reading it or migrates to the replacement field.
- **S2 retired-model**: a literal model name past retirement. Correct resolution is the
  tier-0 literal swap to the announced replacement.
- **S3 renamed-operation**: a call against an operation the new version renames. Correct
  resolution renames the call and carries argument changes.
- **S4 no-op control**: no injected defect. Correct resolution is *no ticket at all* — the
  detector suite staying quiet is a measurement, and a harness that only scores fixes trains
  a workflow to hallucinate them.

Each scenario is a branch of demo-v1 (`scenario/s1-removed-field`, …) so runs are repeatable
and the baseline never drifts.

## Scoring

Per attempt: `verified` (tsc + CI green), `targeted` (every edited file holds a call site the
finding named), `minimal` (no edits outside those files), `outcome` (the graph's own terminal
state). A resolution passes when all four hold. Failures stay queryable — abandoned runs are
data, and so are wrong fixes.

## First live pass, 2026-08-20 03:48

The loop closed: ticket 11 (operator lane, finding `fe184caf`, retired `claude-3-opus-20240229`
at `lib/assistant.ts:13`) → `sync tickets` → tier-0 literal swap → tsc → push → demo-v1's own
CI green → **https://github.com/stroland02/demo-v1/pull/1**, ticket closed `opened` with the PR
URL as its detail. Scored by hand against the S2 statement: verified (tsc + real CI), targeted
(the one file the finding named), minimal (one line), outcome `opened`.

Seven runs of failure bought the pass, each one a real defect the pipeline surfaced honestly:
a drifted lockfile, an engine pin the machine could not satisfy, missing image type
declarations, one mis-shaped Stripe call, a credential-less clone, a CI workflow listening on a
branch the repository does not have, and a prettier gate the baseline itself failed. Every
abandonment named its reason; nothing was retried blind.

One pipeline defect found and still open: the agent lane reached for the `Skill` tool, the
patch gate refused it (twice, in runs 5 and 7), and the attempt ended as "the remediator
produced no change". The gate is right to refuse what `PERMITTED_TOOLS` does not name; the
waste is that the model can see a tool it may never use. Fix on the list: name `Skill` in the
SDK options' `disallowed_tools` (a real block, per `src/sync/CLAUDE.md`) so the model never
attempts it -- and the owner's ask for a software-engineering skill *inside* the solutions
workflow becomes its own designed change, not a gate loosened in passing.

## Ledger

| When | Ruling | Against | Why |
|---|---|---|---|
| 2026-08-20 | Executor claims with a provisional thread id, corrects after loading the finding | widening `claim_next_ticket` to take a thread factory | the claim must stay one atomic statement; a factory inside it would hold the row lock across a graph probe |
| 2026-08-20 | Retracted-finding tickets close as `reported` | leaving them `picked_up` | a row parked at picked_up reads as a dead runner, and the console must never show a zombie |
| 2026-08-20 | Validation writes into `migration_outcome` rather than a new table | a `beta_score` table | the grain already fits (one row per attempt) and the console already reads it; a second table is a copy that will disagree |
| 2026-08-20 | Scenarios live as branches of demo-v1 | committing broken states to demo-v1 `main` | the demo repo's main is what the demo shows; scenario branches keep the baseline clean and every run repeatable |
