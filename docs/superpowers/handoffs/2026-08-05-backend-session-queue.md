# Backend session: the queue, and the loop that works it

Written 2026-08-05 by the console session, for the session that owns `src/sync/remediate/`,
`src/sync/signals/` and the backlog. It exists because that session finished dogfooding Task 2 and
then sat idle at a prompt, and idle is the most expensive state a session has.

Everything below is ordered. Take the top item that is not blocked, and do not stop to ask which —
`.claude/rules/autonomous-development.md` names the only three things that still go to the human,
and none of the work here is one of them.

## The loop

Paste this as a repeating prompt, or hand it to a fresh session. It is modelled on the console
session's tick, which has now driven twenty commits without a blocking question.

> **Sync backend tick.** Work the loop without asking; never end a tick by asking whether to
> continue.
>
> **Budget:** at most two subagents per tick, dispatched synchronously — this session restarts and
> background agents do not survive it. Prefer sonnet. Opus only for a whole-branch review or an
> architecture decision.
>
> **Step 1, cheap checks, no subagent.** In your worktree run `git log --oneline -3` and
> `git status --porcelain`. If the tree is dirty, compare file mtimes against the clock. Still
> moving means another agent is live — work a different file set or stop. Idle for several minutes
> means the work is orphaned by a restart: verify it against the gates and commit it, which is the
> controller's job. Then `git log --oneline -10` on `main`, because two sessions push there and the
> thing you are about to build may already exist.
>
> **Step 2.** Take exactly one item from the queue in
> `docs/superpowers/handoffs/2026-08-05-backend-session-queue.md`, highest value over cost first.
> One item per tick. A tick that lands one reviewed change beats a tick that starts four.
>
> **Stay in your lane.** You own `src/sync/remediate/`, `src/sync/signals/`, `src/sync/cli.py` and
> `docs/superpowers/BACKLOG.md`. The console session owns `web/`, `src/sync/api/`,
> `src/sync/dashboard/` and the rest of `docs/`. If a defect belongs to their paths, describe it and
> hand it over rather than fixing it.
>
> **Gates before any commit:** `uv run pytest` on the touched test files, `uv run lint-imports`,
> `uv run python scripts/lint_encoding.py src scripts tests`, and
> `uv run python scripts/lint_test_skips.py tests`. Do not run the full suite as a gate unless
> `scripts/bootstrap_tools.sh` has run in your worktree — without `oasdiff` about 38 failures and 9
> errors are environmental, not regressions. CI installs it and is green.
>
> **Test-first, always.** Write the failing test, run it, watch it fail for the reason you expect,
> then implement. A test that has never failed has not been shown to test anything, and this
> repository has shipped that mistake twice.
>
> **Step 3.** Append to your plan's SDD ledger what shipped, its commit range, and what the next
> tick should look at first. Then stop.

## The queue

### 1. Prompt-injection defence for the patch agent

**This is the highest-value unstarted item in the whole repository**, and it has been open since the
reference research closed. `docs/superpowers/reports/2026-08-04-what-the-research-changed.md` calls
it the programme's best single output — a security finding nobody was looking for — and the owner's
own recommendation was "yes, and first".

The exposure, stated plainly: Sync's patch agent reads **vendor changelog text and customer
repository contents**, then edits code, with a pull request at the end of the pipeline. That is
third-party text nobody at Sync controls reaching a model with write access to a customer's
repository. There is no defence today.

The mitigations that exist are real but partial, and the report is careful about the distinction:
every patch passes `tsc` and then the customer's own CI, and `sync.index.shipped_tree` holds
untracked and ignored paths out of the compiled tree. Those constrain what a compromised patch can
*ship*. They do not constrain what a poisoned changelog can persuade the agent to *attempt*, and
they do not cover an instruction that produces code which compiles and passes tests.

**Write a threat model before any code.** Which inputs are untrusted, where the boundary sits, and
what a refusal looks like. `docs/superpowers/specs/2026-07-25-sync-threat-model.md` exists on `main`
from before the research and names the verification gate and the evidence bundle as partial
containment — extend it rather than starting a second document.

`docs/superpowers/references/engineering/llm-engineering-practice.md` records PageIndex's
three-layer defence: an injection-pattern list, delimiter framing with the smuggling bypass closed,
and system-prompt hardening. That is a shape to consider, not a design to copy — Sync's inputs and
boundary are its own.

Days rather than hours. Start with the threat model and let it size the rest.

### 2. The two run-state contradictions

Both found by the run-state specification, both in your paths, both hours rather than days.

- `state.py` and `tiered.py` cite the same rule and disagree about whether `NoPatchWarranted` should
  reach `abandon_reason`.
- `sync.mcp.propose` writes five values into `RunState["outcome"]` that are not in the `Outcome`
  literal. The console now filters anything outside `("opened", "abandoned", "reported")` to null,
  so **such a run reads as permanently in flight** — a live-looking run that will never move.

The second is the more urgent: it is the same class as the Critical the console shipped and fixed in
`259906b`, where three modules held three partial opinions about what states a run could be in.

### 3. The abandonment vocabulary — unblocked, and it was blocking you

`docs/superpowers/specs/2026-08-04-sync-run-state-and-abandonment-vocabulary.md` was **accepted** by
a controller ruling on 2026-08-05, recorded in `ff41faa`: the `Disposition` move into
`sync.core.models`, `running` deleted from it, the sixteen abandonment codes, and existing free-text
rows left NULL rather than backfilled. Backfilling is what two specifications and a model comment
already argue against — a guessed value and a measured one in the same column cannot be told apart
afterwards.

So this is yours to build now. `AbandonCode` and `classify` land in `sync.remediate`. **The console
half is deferred behind exactly that condition**, so the moment those exist, tell the console session
and it will render them.

The values matter and they are not borrowed: they come from Sync's own routing predicates, which is
the whole argument in `.claude/rules/interface-originality.md` about a shape transferring where the
values do not.

### 4. Dogfooding Tasks 3 through 7

`docs/superpowers/plans/2026-08-05-sync-dogfooding-and-loop-testing.md`. Task 2 — the forge-free
pipeline runner — was blocking four of the seven, and you have just landed it. Confirm it against
the gates, then take the unblocked tasks in the plan's own order.

The safety boundary in that plan is an **absent object** rather than a flag:
`build_graph(forge=None)` omits `push_branch`, `await_ci` and `open_pr` entirely. A graph that
cannot reach those nodes cannot open a pull request by accident, which is a stronger guarantee than
a conditional. Keep it that way.

### 5. Logging, the half the console session deliberately did not cross into

`docs/superpowers/references/engineering/observability.md` §3.1. No `basicConfig` or `dictConfig`
exists anywhere outside `.venv`, so **every `log.info` and `log.debug` in the codebase is discarded
unconditionally** — including `src/sync/remediate/corpus.py:266`, which distinguishes a run that
never attempted a repair from one that attempted and found no tier, a distinction its own comment
says an operator reading logs needs, and which has never reached one.

**Half of this is already done and is on the console branch.** `src/sync/obs/log.py` exists with
`configure(level, fmt)`, a JSON formatter, idempotence, and non-ASCII handling, wired into
`python -m sync.api` behind `SYNC_LOG_LEVEL` and `SYNC_LOG_FORMAT`. It landed in `bad76ef`.

What remains is the call from `main()` in `src/sync/cli.py`, which is your file. The console session
declined to cross the boundary for it — an edit there from a feature branch buys a merge conflict
for nothing. Take it after `m4-dashboard` merges, or take it now against `main` if you are working
there.

Do not convert any `print()` call. The CLI's `print()` output is deliberate human output; the point
is that a log stream starts existing, not that the CLI stops talking.

### 6. The engineering audit's two missing pieces

`docs/superpowers/references/engineering/` holds all eleven dimension files. **The synthesis and the
completeness critic were never written** — the workflow that would have produced them stopped on a
session limit. Both reports now say so plainly rather than describing the whole audit as unfinished.

Low priority and genuinely optional. Named here so it stops being invisible.

## What the console session is doing, so you do not collide

`m4-dashboard` is at `a2153bd`, roughly sixty commits ahead of `main`, gate green. Slice 2 is
complete, the design system shipped, and a seven-agent fan-out (`wf_e361a5ce-0d1`) is currently
building three new surfaces: the API Dependency Graph made visible, the observed rung, and detector
accountability. All of it lives in `web/`, `src/sync/api/` and `src/sync/dashboard/`.

Two live servers are running against the shared Postgres on port 5433 — the API on 8787 and a Vite
dev server on 5173 — because the owner is watching the console while it is built. **Do not stop
them, and do not truncate or reseed the `sync` database.** If you need a database for a test, create
your own and drop it afterwards; `scripts/seed_console.py` shows the pattern and refuses any DSN
whose host is not local.

## Two facts that will otherwise cost you an afternoon

**The 38 local test failures are not a regression and not `yarn`.** `oasdiff` is not installed in
every worktree — `tools/` is gitignored and `scripts/bootstrap_tools.sh` has not been run there — so
`sync.signals.oasdiff._binary()` raises `FileNotFoundError`. Every one of the 38 failures and 9
errors traces to that single missing binary. Run the bootstrap before reading a red suite as
breakage.

**`tests/test_seed_console.py` races under the default `-n auto` scheduler**, because its fixture
seeds and removes against one shared database with no per-worker isolation. Run it with `-n0`. That
is a known pre-existing flake and it is worth a tick of somebody's time.
