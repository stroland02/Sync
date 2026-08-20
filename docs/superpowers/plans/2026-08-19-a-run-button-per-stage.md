# A run button per stage — the pipeline becomes operable from the console

**Owner direction, 2026-08-19.** *"we need to plan out how we can run these services that are built
into the product… we want it to have a run button for each one of these pages so that a user can
manually update the data for all 5 of the different processes."*

`PipelineStrip` draws Index → Signal → Observe → Detect → Remediate and `WorkflowGrid` gives every
stage its doors, so a reader can now see the whole loop and what each stage holds. **Every stage is
read-only from the console.** Refreshing any of the five means leaving for a terminal, and the
console cannot say when a stage last ran or that one is running now.

This plan is the companion to `2026-08-19-findings-become-work.md` and is deliberately built on that
plan's ruling rather than beside it. That plan opens the fifth stage; this one opens the other four
and gives all five one shape.

---

## 1. The ruling this plan inherits

`2026-08-19-findings-become-work.md` §2 already settled the architecture, and nothing here reopens
it:

> The API writes one row and answers with what it wrote… **`GraphSurface` gains no write method**, so
> `test_no_route_reaches_past_the_read_surface` stays green on its own terms rather than being
> relaxed.

```
console  ──POST /api/repositories/{id}/runs──▶  run_request row   (one row, nothing executed)
                                                      │
worker   ──sync work ─────────────────────────────────┘  claims requests, runs the stage,
                                                         writes the stage's own run record
```

**One worker, not two.** `sync work` is already this plan's sibling's command for claiming
remediation tickets. A run request is the same shape one table over, so it claims both rather than
growing a second daemon with a second set of failure modes.

**The button never runs anything.** It records that a human asked, and the request row is the thing
the screen watches. That is what keeps `.claude/rules/console-dev-loop.md`'s rule intact in
substance — no route mutates the graph, and no route touches a customer repository — while widening
its letter by exactly one more writer, on the same terms the dismissal and context writers already
have.

---

## 2. The five stages are not equally safe, and the plan does not pretend they are

Researched against the tree rather than assumed. **Four of the five already record their runs** —
the "what happened" half exists and is unrendered:

| Stage | What running it means | Existing run record | Network | Customer repo | Spend |
|---|---|---|---|---|---|
| **Index** | `sync index --repo <path>` over a checkout | `index_run` (start/finish/fail) | no | reads a checkout | no |
| **Signal** | fetch two spec versions, diff with `oasdiff` | `intake_attempt` (outcome + reason code) | **yes** | no | no |
| **Observe** | fold a captured OTLP payload | `observed_call`, `telemetry_attached_at` | no | no | no |
| **Detect** | run detectors over the graph | `finding.created_at` only | no | no | no |
| **Remediate** | clone, patch, verify, push, open PR | checkpointer + `migration_outcome` + `run_heartbeat` | yes | **writes** | **yes** |

Two consequences the buttons must respect:

**Observe has nothing to run without a file.** `sync ingest` folds a capture in; there is no fetch
behind it. Its button is an upload, not a refresh, and the empty state — which is the state most
deployments are in — is exactly where it belongs.

**Remediate keeps its own door.** It is the one stage that spends and reaches a customer repository,
and its entry point is the ticket the sibling plan builds. This plan gives it **no** run button; the
Remediate page's control stays *open a ticket*, and `sync work` does the rest. Consistency across
five buttons is not worth putting a clone and a model run behind a web click.

So: **four run buttons and one upload, plus the sibling plan's ticket.**

---

## 3. What the button must say, which is most of the work

A control that fires and says nothing is the failure this console exists to refuse. Each stage's
button resolves to one of four states, and they are four different facts:

| State | Screen | Source |
|---|---|---|
| never run here | *never indexed* · *never attached* | no run record |
| running now | *asked 3 minutes ago, still going* | request `claimed_at`, no terminal row |
| finished, with a result | *1,204 call sites, 3 minutes ago* | the stage's own run record |
| failed, with a reason | the reason code, from the closed vocabulary | `index_run.outcome`, `intake_attempt.reason` |

**A request is not a run.** A row that was asked for and never claimed means no worker is running —
which is a fact about the deployment, not about the stage, and the screen says which. This is the
distinction `run_heartbeat` already exists to draw for remediation runs, applied one level up.

**No progress bar and no percentage.** Nothing reports fractional progress, and a bar that advanced
on a timer would be the fabricated liveness `web/CLAUDE.md` refuses. Elapsed time since the request
is real; a completion estimate is not.

---

## 4. Tasks

### Task 1 — `run_request`, the table

One row per human ask: `id`, `repo_id`, `stage`, `requested_at`, `requested_by`, `claimed_at`,
`finished_at`, `outcome`, `detail`. Grain declared in `schema.sql` before the columns, per
`graph-grain.md`. Natural key and conflict clause so a double-press converges: an unclaimed request
for the same `(repo_id, stage)` is the same row.

`stage` is the `WORKFLOW_STAGES` vocabulary the console already renders — closed, so it can be
counted, and asserted against the console's list the way the rung vocabulary already is.

### Task 2 — The store writer and reader

`request_run`, `claim_run_request`, `finish_run_request`, and `latest_run_request(repo_id, stage)`.
Writers only — `GraphSurface` gains nothing, which is what keeps the invariant test green on its own
terms.

### Task 3 — The route

`POST /api/repositories/{repo_id}/runs` taking `{stage}`, and the request state on the existing
coverage payload so a screen that already reads one route does not gain a second round trip.
Injected writer beside `dismissal_writer`. Gated by `SYNC_ENABLE_RUNS`, defaulting the way
`SYNC_SERVE_SOURCE` does, so a hosted deployment can refuse the whole capability in one variable.

### Task 4 — `sync work` claims run requests

The sibling plan's worker gains the four stages. Each claims, runs the existing code path
(`index_codebase`, the intake attempt, `sync ingest`'s fold, the detector sweep), and writes both
the request's outcome and the stage's own run record. Idempotent per `CLAUDE.md`: re-running a stage
converges.

### Task 5 — The control, once

One `StageRunControl` component: the button, the four states of §3, and the reason on failure. It
renders on Index, Signal, Detect from one implementation; Observe passes an upload handler instead
of a trigger. Written once because five copies of a control that must never claim liveness is five
places to get it wrong.

### Task 6 — The demo

Seed through `scripts/seed_console.py`'s own writers: a stage never run, one finished with a result,
one failed with a reason, and one requested with no worker — so the console shows all four states
without anybody having to break a deployment to see them.

---

## 5. What this plan refuses

- **A run triggered inside the API process.** A long index would tie up the read server and a crash
  would take the console with it. The row is the handoff.
- **A run button on Remediate.** §2. Its door is the ticket.
- **A progress bar.** §3. Nothing measures fractional progress.
- **A "last run" derived from data timestamps.** The newest `call_site.indexed_at` answers when a row
  was written, not whether a pass ran and found nothing — `index_run` exists precisely because those
  are different, and the second is the one a run button must report.
- **A refresh-all button.** The stages have different costs and different failure modes; one control
  that fires five would report a single outcome for five answers.

---

## 6. Ledger

| # | Decision | Against | Why |
|---|---|---|---|
| 1 | Reuse the sibling plan's row-then-worker shape | A second trigger mechanism | Two ways to start work is two sets of failure modes, and the ruling is already recorded |
| 2 | Four buttons, not five | Consistency across the strip | Remediate spends and writes to a customer repository; the other four do neither, and uniformity is not worth putting that behind a click |
| 3 | Observe's control is an upload | A refresh button | `ingest` folds a file; there is no fetch behind it, and a button that refreshed nothing would be a control that lies |
| 4 | `run_request` is its own table | Reusing `index_run` | `index_run` is Index's own record and three stages have no equivalent; one table for the ask, each stage keeps its own record of what happened |
| 5 | The capability is env-gated | Shipping it always on | `SYNC_SERVE_SOURCE` is the recorded precedent for a deployment-level refusal, and a hosted control plane will want this off |
| 6 | Elapsed time, never an estimate | A progress indicator | Nothing reports fractional progress; a bar advancing on a timer is fabricated liveness |
| 7 | A request nobody claimed says so | Rendering it as running | An unclaimed row means no worker, which is a fact about the deployment rather than about the stage |
