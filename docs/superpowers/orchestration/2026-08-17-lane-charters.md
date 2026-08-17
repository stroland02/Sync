# Lane charters, 2026-08-17

Six agents work this repository at once. This file is what each of them reads at the top of every
loop iteration. It exists because the coordination cost of six sessions is not the work; it is the
collisions, and every collision this project has had so far falls into three kinds: two agents
editing one file, two agents claiming one work-item number, and an agent landing on a stale `main`.

Each of the three has a mechanical fix here rather than a convention anybody has to remember.

Read your own lane. Do not read the others' lanes for instruction; read them only to know what you
must not touch.

## The rule that makes the rest work

**A lane owns files, not tasks.** A task name does not collide. A file does. So the lane boundary
below is a path list, and the question "may I do this piece of work" is answered by "are the files
in my lane", never by "does this sound like my area".

If a change you need crosses into another lane, do not make it. Send the coordinator a message
naming the file and what you need, and keep working on something else in your lane while you wait.
A five-minute wait is cheaper than a merge conflict in a file two sessions rewrote.

## The three shared files, and the only safe way to edit them

`docs/superpowers/WORKLOG.md`, `docs/superpowers/BACKLOG.md` and the plan files under
`docs/superpowers/plans/` are touched by every lane. They caused every merge conflict recorded on
2026-08-17.

**When you resolve a conflict in any of these, the resolution is the union of both sides.** Keep
every row from both sides. Never delete another agent's row, never reorder to make a diff smaller,
and never take one side wholesale. If both sides added a row with the same number, keep both rows
and renumber *yours* using your block below, because the other agent may already have pushed.

## Work item and backlog numbers are pre-allocated, so they cannot collide

`M<milestone>-W<n>` is one sequence across the whole project. On 2026-08-17 five collisions
happened in a single afternoon because five sessions each took "the next number" from a register
that was already stale in their working tree.

Take your numbers from your own block. Nobody else will.

| Lane | Work items | Backlog items |
|---|---|---|
| A -- remediation loop | W240-W259 | B140-B144 |
| B -- console | W260-W279 | B145-B149 |
| C -- pipeline health | W280-W299 | B150-B154 |
| D -- signals and adapters | W300-W319 | B155-B159 |
| E -- graph, dashboard, API | W320-W339 | B160-B164 |
| Coordinator | W233-W239 | B137-B139 |

Use them in order. The milestone prefix is whatever the work actually belongs to, so `M10-W241` and
`M11-W242` from one lane is normal and correct.

## Two rules about where you work, learned the hard way on the first afternoon

**Never work in the shared `main` worktree.** Every Orca terminal is bound to
`C:/Users/strol/orca/Sync/Sync`, so `cd`-ing nowhere and just working is the path of least
resistance and it puts six agents in one checkout. Measured 2026-08-17: that worktree was found
holding staged additions plus four unmerged index entries with no merge in progress, and its index
changed between two reads seconds apart because a second agent was resolving conflicts in it at the
same time. Work in your own worktree under `C:/Users/strol/orca/workspaces/Sync/`. If you do not
have one, make one.

**A commit that is not on a branch is not saved.** `be0692d` carried B118's `stop_server.py`, its
author reported it landed, and it is contained in no branch and absent from `origin/main`. It
survived only in the reflog. Land it or branch it; a commit reachable from nothing is a commit
nobody will find.

## The loop

Every iteration, in order. Do not skip step 0, step 1 or step 6.

0. **Read your mail.** `orca orchestration check --json`, process every message, then
   `orca orchestration check --ack <delivery_id>`. The coordinator answers questions and issues
   arbitrations through it, and mail is only read when you ask for it -- a long agent turn can sit
   an hour on an instruction that was already waiting. Reply to a `question` with
   `orca orchestration reply --id <msg_id> --body <answer>`.
1. **Catch up.** `git fetch origin` then `git merge origin/main --no-edit` in your worktree.
   Resolve conflicts by the union rule above. Another session has almost certainly landed since
   your last iteration.
2. **Pick one item** from your lane's queue below. One reviewable unit, not three.
3. **Claim it** by adding its row to `docs/superpowers/WORKLOG.md` with the next number from your
   block, before you write code.
4. **Build it test-first.** Write the failing test, run it, watch it fail for the reason you
   expect, then implement. This is not negotiable and it is not slower; it is the only thing that
   distinguishes a test from a comment.
5. **Gate locally.** The local gate is the authority, not CI -- hosted runners here report a job
   that never started as `failure`. Run every gate your change touches and say which ones ran:
   - Python: `uv run lint-imports`, `uv run python scripts/lint_encoding.py src tests`,
     `uv run pytest tests/ -q -n 4`
   - Console: from `web/`, `npm test`, `npm run build`, `npm run lint`
6. **Land it on `main` by fast-forward, per unit and not per plan.** This is the step the first
   afternoon actually failed at: five lanes produced sixteen commits and landed none of them, while
   one branch sat eleven commits ahead of a `main` that moves hourly. Unlanded work is invisible to
   every other lane and rots against a moving base, which is the exact failure splitting into six
   sessions was supposed to prevent. Land each reviewable unit as it passes its gate. Merge `origin/main` once more, re-run the cheap gates,
   then prove containment before you push:
   ```
   git fetch origin
   git merge-base --is-ancestor origin/main HEAD && git push origin HEAD:refs/heads/main
   ```
   If the ancestor check fails, the branch diverged: merge again and re-check. Never force-push,
   never open a pull request, never push a branch to `main` you have not gated.
7. **Report.** Send `worker_done` naming the commit range that landed, what you gated, and what you
   deliberately did not do. The coordinator re-dispatches you immediately; you do not need to ask
   for more work.

If an iteration produces nothing landable -- the item turned out to be already done, or blocked --
report that as `worker_done` with `--outcome succeeded` and say so plainly. An honest empty
iteration is a result. Do not invent work to fill it.

## Deciding rather than asking

While executing, decide and continue. `.claude/rules/autonomous-development.md` is binding: write
the ruling into the plan's ledger and keep going. Three things only are still the human's -- an
irreversible action outside this repository, a decision that invalidates a plan's architecture, and
anything needing a credential or a spend. Landing on `main` by fast-forward is explicitly
authorized for every lane and is not one of the three.

Escalate to the coordinator, not to the human, when the blocker is another lane.

## Traps that have each cost this project an hour

- **A fresh worktree fails about 50 tests for missing gitignored tooling.** Run
  `bash scripts/bootstrap_tools.sh` and `uv run python scripts/fetch_corpus_repositories.py` once
  per checkout. Do this before you believe any failure.
- **Postgres is shared, on port 5433, and it bounces -- but read the failure text, never the
  count.** This note used to say a run failing in the hundreds is environmental, and that phrasing
  was itself a hazard: on 2026-08-17 `main` was 60 tests red for a real reason while Postgres
  accepted connections throughout, using one connection of three hundred, and the count alone would
  have sent every lane to the wrong conclusion. **Environmental** means the failures carry
  `the database system is starting up`, `is in recovery mode`, or `connection failed`; then wait for
  `docker exec sync-postgres-1 pg_isready -U sync` and re-run. Anything else -- a `KeyError`, a
  `GraphRecursionError`, an `IndexError` -- is a real regression wearing a large number.
  Do not restart the container: five other agents are using it.
- **`python3` does not exist here.** The interpreter is `python`. `uv` only; never Poetry.
- **A crashed xdist worker prints `F` against tests that never ran, at any `-n`.** Measured at
  `-n 4` on 2026-08-17: about thirty phantom failures in a run cut off before its summary, reading
  as a catastrophic regression that did not exist. `-n 4` is the better default but it is not a cure
  for this, so a run without a summary line is not a result -- re-run it before reporting anything.
- **Use `-n auto`. The `-n 4` guidance is retired as of 2026-08-17 and it was costing you 108
  seconds a run.** Measured by Lane C once `CI-W295` made a dead worker visible on a runner at all:
  `-n auto` is 185s on a Linux runner and 125s on this Windows host, both with no worker lost,
  against 233s for `-n 4`. The crash `-n 4` existed to avoid was npx-lock starvation, and Lane D
  fixed that in `2cf2e62`. A workaround that outlives its cause is a tax nobody notices they are
  paying, which is why this is the guidance being retired rather than the configuration being
  changed.
- **Superseded, kept for the record: use `-n 4`, not `-n auto`, for the full suite.** `-n0` is unusable here -- it takes long enough that nobody runs it -- but `-n auto` is not the safe opposite: it has crashed an xdist worker outright on this machine (`INTERNALERROR ... KeyError: <WorkerController gw7>`) and Lane C measured the same thing independently. A crashed worker aborts the run, which reads as a catastrophic failure and is not one. `-n 4` is the working default; a single test file is fine with `-n0`.
- **Never `git stash`.** `refs/stash` is one stack shared by every worktree of this repository, so
  a pop in your tree can take another agent's work.
- **Never `git checkout <file>` on a file with uncommitted work.** It reverts the whole file.
- **Always pass `encoding="utf-8"`** to `read_text`, `write_text`, `open` and
  `subprocess.run(..., text=True)`, and set `PYTHONIOENCODING=utf-8` in a child process's
  environment. Every fixture here is ASCII, so no test will ever catch a missing one.
- **A spec passed through the Orca CLI must be ASCII.** Em dashes arrive as mojibake.

## Confirm your lane before your first landing

**A dispatch delivering a spec is not the same as an agent having read it**, and the gap between
those two is where duplicated work comes from. Measured 2026-08-17: Lane A received its charter,
was mid-task when it arrived, did not act on it, and spent twenty-four minutes building
`sync.dashboard.fleet.change_units`, `by_rung` on `detector_accountability` and `/api/change-units`
-- Lane E's files, which Lane E had already landed as `M12-W320` in `157fff6`. Two lanes, one
aggregate, and neither knew until a coordinator sweep read a terminal.

It also asked, reasonably, whether the coordinator messages were genuine before pushing to
`origin/main` from an index it did not control. That caution was right and cost nothing; the
duplication cost half an hour.

So, once, before your first landing: reply to the coordinator naming your lane, the path list you
believe you own, and your number block. If any of the three is not what the coordinator expects, you
find out before you have written code rather than after.

**And if a coordinator instruction looks unverifiable, verify it rather than stall or comply.** The
charter is on `origin/main` and so is every coordinator commit:
`git show origin/main:docs/superpowers/orchestration/2026-08-17-lane-charters.md` and
`git log --oneline origin/main` settle it in two commands. Pushing to `main` by fast-forward is
authorized for every lane and is explicitly not one of the three things reserved for the human.

## Addressing a worker: resolve the dispatch id immediately before sending

**A dispatch id is not a stable address for a lane.** It changes every time a lane is re-dispatched,
and a coordinator that caches one sends into a dead mailbox with a cheerful `ok=true` and no
delivery. Measured 2026-08-17: a high-priority broadcast about a 60-test regression was addressed to
`ctx_2c000ad0eae9` after the sweep had already replaced it with `ctx_f76066ef0571`, and the lane
reported `count: 0` while the coordinator believed it had been told.

So resolve it fresh, in the same breath as the send:

```
orca orchestration dispatch-show --task <task_id> --json    # read .dispatch.id
orca orchestration send --to dispatch:<that id> ...
```

The terminal handle is the durable identity; the dispatch id is not. When a message genuinely must
arrive -- an arbitration, a stop-work, a regression another lane caused -- prefer
`orca terminal send --terminal <handle> --enter`, which reaches a busy agent as its next input
rather than waiting for it to ask for mail.

## Reading mail: the queue does not advance unless you acknowledge, and there is no `ack` subcommand

**`orca orchestration check` returns the oldest *unacknowledged* batch, and returns it again, and
again.** The acknowledgement is a flag on `check` itself:

```
orca orchestration check --ack <delivery_id> --json
```

There is no `orca orchestration ack`. Calling one fails with `invalid_argument`, which reads as a bad
argument rather than as a missing command, so the natural next move is to fix the arguments instead
of the verb.

Measured 2026-08-17, by the coordinator, on itself: a `worker_done` from Lane B was read, acted on
and answered — and then returned unchanged on the next two sweeps, while a Lane C escalation and a
Lane C `worker_done` sat behind it, unseen. The owner's prompt said *"you have 2 messages"* and then
*"you have 3"* while `check` reported one, which is exactly the signal to look at. **A queue that
only ever shows you the message you have already handled looks identical to a quiet queue.**

Drain it in a loop, acking each batch by the id the previous call returned, until the delivery id
comes back empty. And treat a mismatch between the notification count and what `check` shows as a
defect in your own reading, not as a stale notification.

## When a lane keeps working outside its boundary

Three times on 2026-08-17 one lane built inside another's files: the Fleet change-unit aggregate
that duplicated `M12-W320`, the panel wiring in `1985e3e` that `M14-W277` superseded, and an edit to
`web/src/api/queries.ts` made while the owning lane was editing `web/` in the same minute.

**None of the three was caught by the lane doing it, and none was caught by review.** Each surfaced
because a coordinator read a terminal, and each cost three parties: the lane that wrote it, the lane
that discovered it, and the coordinator that routed it. Duplicated work is the most expensive failure
this workspace has, because it looks like progress from inside.

So the boundary is not a preference and it is not satisfied by good intentions. **Before editing a
file, check it against your own lane's path list.** If it is not there, do not edit it -- message the
coordinator, name the file and what you need, and keep working inside your lane while you wait. The
one exception is the narrow one above: a red you caused, where the failure message names the fix.

A lane that finds itself repeatedly outside its boundary is usually solving the wrong problem. The
work only that lane can do is the work nobody else is able to pick up, and it is almost always the
harder item further down its own queue.

## Fixing a red you caused in another lane's file

The rule is escalate rather than edit outside your lane. **One exception, ratified 2026-08-17:** a
lane may fix a red **it caused** in another lane's file when the failure message names the exact fix
and the edit is unambiguous -- provided it declares the edit in its report and offers the reversal.

The case: Lane B's `M14-W277` landed the Fleet panel, which was the event that expired an entry in
`_NOT_YET_FETCHED_BY_CONSOLE` in `tests/test_api_routes.py` -- a set that documents its own expiry.
The guard went red on `main` at that moment and stayed red. Escalating would have left `main` broken
on Lane B's account while it waited on a coordinator, and a charter that produces that outcome is
wrong at that point.

Two things make it safe rather than a licence: the red must be **yours**, and the fix must be the
one the failure message states. Anything requiring judgement about another lane's design is still an
escalation.

## Standing arbitrations

Recorded here when one is made, so no lane has to ask the same question twice.

**2026-08-17, the blanket exclusion of `test_lint_dead_links` is RESCINDED, and it was a
coordinator error.** The exclusion was granted when the red had three causes none of which any
working lane could fix. All three are now closed. Every violation standing today was introduced
this afternoon by the lane that still owns it -- `reconcile_pull_request_outcomes` and
`GraphStore.intake_attempts` (Lane E), `execute_intake_attempt` (Lane D) -- and the reason it kept
happening is that I told every lane it could skip the one test that would have told them. A rule
nobody's gate enforces is a rule that gets written twice and followed never.

So: **run `tests/test_lint_dead_links.py`. If it reports a symbol you introduced, close it before
you land** -- wire the caller if it can be wired, or add the baseline entry in the same commit,
naming the work item that removes it. A seam-first workflow legitimately produces a producer before
its consumer; that is exactly what the baseline-with-an-expiry is for, and it costs one line.

If it reports a symbol you did not introduce, that is somebody else's and you may still exclude it
-- say whose, and say so when you report.

**2026-08-17, the dead-link red now has three causes and one owner each.** Re-measured against
`main` after the afternoon's landings: `test_lint_dead_links` reports three unreachable symbols, not
one, and every one of them is the same shape -- a primitive landed without the consumer that would
call it.

- `sync/forge/github.py:631`, `GitHubForge.pull_request_outcome`. **The coordinator's, landed as
  `M10-W229`.** Lane E is wiring it to the corpus right now and that landing closes this.
- `sync/forge/webhook.py:263`, `dispatch_webhook_event`. Lane A's, from M10's event ingress. Closes
  when the resume-on-pull-request-event path is wired.
- `src/sync/remediate/sandbox_image.py:113`, `ensure_image_built`. Lane A's, from B97. Still open.

Until all three close, any lane may exclude that one test from its own run **provided it says so
when reporting**. Nobody should re-diagnose it.

**The rule this is teaching, and it is not new -- `CLAUDE.md` already says a workaround ships with
the backlog entry that retires it.** Do not land a producer with no consumer. If a primitive must
land ahead of its caller, baseline it in the same commit and name the work item that removes the
baseline. Three of these accumulated in one afternoon because each author reasonably judged their
own piece complete, and the cost lands on the four lanes that then gate around a red they did not
cause.

**2026-08-17, the original dead-link ruling.** `ensure_image_built` in
`src/sync/remediate/sandbox_image.py` is reached from nowhere and fails
`test_lint_dead_links`. Lane C is right that baselining it would hide another session's in-progress
work, and reached that on its own. **Ruling: leave the red, name `21b99f6` when reporting it, and do
not edit or baseline that file. Lane A wires it as part of its own queue** -- the file is Lane A's,
the function is B97's, and a lane that owns neither should not be the one to decide it is dead. Any
lane may exclude that one test from its own gate run while this stands, and must say so when
reporting.

## The lanes

### Lane A -- the remediation loop, M9 through M11

**Owns:** `src/sync/remediate/**`, `src/sync/runner/**`, `src/sync/core/outcomes.py`,
`src/sync/core/protocols.py`, `src/sync/rehearse/**`, and the tests named for them
(`tests/test_remediate*`, `tests/test_outcome*`, `tests/test_patch_runner_seam.py`,
`tests/test_durable_runs.py`, `tests/test_tiered*`, `tests/test_rehearse*`).

**Authority:** `docs/superpowers/plans/2026-08-06-sync-m8-m11-resolution-loop.md`.

M8's runner seam landed as `M8-W228`. M9's outcome vocabulary is built. What remains is the half
that earns the product's name.

Queue, in order:

1. **M10, durable runs and the human turn.** A run that parks instead of ending:
   `queued -> repo_discovery -> running -> { awaiting_human | awaiting_events | complete | failed }`,
   with `resuming -> running` when a human replies or a pull request event arrives. LangGraph
   checkpoints in Postgres are already a durable session store; what is missing is the parked
   states, the event ingress, and the rule that a parked run is not ticked until something wakes
   it. Closes when a run whose pull request receives a review comment resumes and pushes a
   follow-up commit with no human re-running anything, and when abandoned and parked are
   distinguishable in the corpus.
2. **M11, fan-in.** Findings sharing a `vendor_change_id` against one repository are one unit of
   work. One vendor change across N call sites becomes one pull request with N edits and one
   resolution carrying N dispositions, applied atomically -- if any entry is invalid, nothing
   changes. The corpus records one attempt, not N.

**Do not touch** `src/sync/forge/**` without messaging the coordinator; `pull_request_outcome`
landed there as `M10-W229` and Lane A's event ingress will want it. Reading it is free.

### Lane B -- the console, M7's remainder and M12

**Owns:** `web/**`, `DESIGN.md`, `.claude/rules/console-*.md`, and the console plans under
`docs/superpowers/plans/`.

**Authorities:** `docs/superpowers/plans/2026-08-17-console-mock-parity.md`,
`docs/superpowers/plans/2026-08-08-console-mock-to-build.md`, and the three that bind every screen:
the specification's hierarchy block, `DESIGN.md` as the token contract, and
`.claude/rules/interface-originality.md`.

Queue, in order:

1. **Finish the mock-parity plan** you are already executing, task by task, landing each on `main`
   rather than batching them.
2. **Mock-to-build Task 1**, the measurement pass: put a mock screen and its shipped counterpart
   side by side under `getComputedStyle` and write what differs. Nobody has done this, which is why
   every other task in that plan argues from a drawing.
3. **M12, dashboards that earn their screen.** The two things the owner named and nobody scheduled:
   the layout is one vertical stack where it should be a grid, and Fleet carries more prose than
   data. The useful panels need aggregates `sync.dashboard` does not compute -- those aggregates
   are Lane E's, so message the coordinator with the exact shape you need and build against it when
   it lands.

**The refusals are not style and they are not yours to relax:** no composite score, no health
figure, no traffic light, no green dot, no liveness pulse. Restyling one of the twenty-four honesty
sentences is allowed; deleting, shortening, collapsing behind a disclosure, or moving one into a
tooltip is not.

**Mock-to-build Task 3 is blocked on its own premise** and the plan says so -- the drawer has one
consumer, not five. The work it actually contains is building the second drawer.

### Lane C -- pipeline health, the gate, and CI

**Owns:** `.github/**`, `scripts/**` except `scripts/orchestration/**`, `pyproject.toml`, `docker-compose.yml`, `docker/**`,
`tests/conftest.py`, `tests/test_lint_*`, `tests/test_ci_*`, `tests/test_gate_*`,
`tests/test_leaked_database_sweep.py`, `tests/test_patch_sandbox.py`, `tests/test_sandbox.py`.

Queue, in order:

1. **`main` is red and has been all day.** `tests/test_lint_dead_links.py::test_the_repository_matches_its_baseline`
   fails because `ensure_image_built` in `src/sync/remediate/sandbox_image.py:113` landed with B97
   Decision 2 and is reached from nowhere. Wire it or baseline it -- B111's standard applies, a
   thing held out of the gate must be wired somewhere real rather than dropped. This is the highest
   priority item in any lane, because every other lane is currently gating around it.
   `sandbox_image.py` is Lane A's path: coordinate through the coordinator, or baseline it from
   your side and file the wiring as a backlog item against Lane A.
2. **Postgres bounces under six concurrent sessions** and takes about three minutes of crash
   recovery each time, which reads as a mass test failure and costs whoever hit it a diagnosis.
   Measured twice on 2026-08-17. Find out whether this is Docker Desktop, a resource ceiling, or
   the leaked-database volume, and fix or document it with evidence.
3. **`test_disconnect_network_does_not_stop_an_already_open_socket`** fails under `-n auto` and
   passes alone. A test that fails only under contention is a test nobody can read a verdict from.
4. **Gate wall-clock.** The full suite is eight to fourteen minutes and every lane pays it on every
   iteration. That is the single largest tax on this whole workspace.

### Lane D -- signals, adapters and intake, M5

**Owns:** `src/sync/signals/**`, `src/sync/index/**`, and their tests (`tests/test_*adapter*`,
`tests/test_*signal*`, `tests/test_*vendor*` except `tests/test_adapter_inventory.py`,
`tests/test_intake*`, `tests/test_index*`, `tests/test_oasdiff*`, `tests/test_reachability*`).

M5 is at about 35 percent: Sentry feeds counts in, and nothing correlates anything. That
correlation is this lane's subject.

Queue, in order:

1. **Make the request correlator real.** `RequestCorrelator` is a protocol in `sync.core` with no
   production implementation joining runtime telemetry to a static call site. Until that join
   exists, the `observed` rung is a promise rather than a rung, and two detectors depend on it.
2. **Adapter conformance against a second configured vendor.** The registry serves coded,
   generated-from-manifest and MCP vendors; only the coded pair is exercised end to end.
3. **B136, the intake attempt record**, is filed and is Lane E's schema but this lane's producer.
   Nothing records that an adapter was *asked*, only what it answered, so an adapter whose fetch has
   been failing for a week is indistinguishable from one that found nothing new. Coordinate the
   schema half through the coordinator.

**Vendor-specific knowledge lives in adapters, never in core.** The moment `sync.core` knows a
vendor's name the plugin story is dead, and `tests/test_import_boundary.py` is not advisory.

### Lane E -- the graph, the dashboard view models, and the API

**Owns:** `src/sync/graph/**`, `src/sync/dashboard/**`, `src/sync/api/**`, `src/sync/mcp/**`,
`src/sync/benchmark/**`, and their tests (`tests/test_graph*`, `tests/test_dashboard*`,
`tests/test_api*`, `tests/test_mcp*`, `tests/test_adapter_inventory.py`, `tests/test_severity*`,
`tests/test_pipeline_composes.py`).

Queue, in order:

1. **The aggregates M12 needs.** Lane B cannot build a panel over a number nothing computes. The
   two named in the mock-to-build plan are the Fleet change-unit grain and the cross-detector rung
   tally. Build them as view models with tests, land them, and tell the coordinator the payload
   shape so Lane B can consume it.
2. **B136's schema half**, the intake attempt record. One row per *attempt*, not per adapter,
   carrying the outcome and, on failure, a reason from a closed vocabulary rather than free text --
   B128's argument for `abandon_reason_code` applies unchanged, because a promise to learn from
   failures needs a schema that can be aggregated. Declare the grain as a comment in `schema.sql`
   before you add the first column.
3. **Wire `pull_request_outcome` to something that updates the corpus.** It landed as `M10-W229`
   and nothing calls it, so `pr_merged` is still null on every row and merge rate still has no
   sample. This needs repository resolution per corpus row, and `store.record_merge_outcome`
   currently stamps `pr_merged_at = now()` rather than the instant GitHub holds, which is a
   fidelity gap to close while you are there.

**Every stage is idempotent and every table declares its grain as a comment before it gains a
column.** One `migration_outcome` row is one attempt, not one finding.

## The loop survives the session that started it

Every agent here, the coordinator included, eventually stops mid-loop: a token budget runs out, a
session closes, a runtime drops a connection. The lane then goes quiet and nothing notices, because
the thing that would have noticed is the session that died.

`scripts/orchestration/resume_lanes.py` is what notices. It is idempotent, takes no arguments in its
normal form, and re-attaches any stopped lane to its own terminal. A scheduled task on this machine
runs it every twenty minutes, so a lane that dies while nobody is watching is picked up within
twenty minutes rather than at the next time a human happens to look.

Run `uv run python scripts/orchestration/resume_lanes.py --dry-run` to see every lane's verdict
without changing anything. That is the right first command when you do not know what state the
workspace is in.

**It never invents work.** It re-attaches an existing Task to an existing terminal. Deciding what a
lane does next is a coordinator judgement, and a script that guessed would turn a finished milestone
into busywork.

## The coordinator

Owns `docs/superpowers/WORKLOG.md`, `docs/superpowers/BACKLOG.md`, this file,
`scripts/orchestration/**`, arbitration between lanes, and reconciling a landing that two lanes
raced. Message it with
`orca orchestration ask` when you are blocked on another lane, and with `escalation` when something
is wrong that your lane cannot fix.

It does not review your work before you land it. The gate does that, and you ran it.
