# Brief — the review wave, and the error surface that would have caught it sooner

You are working in your own Orca workspace on a branch based on `m4-dashboard`. Everything you need
is in the repository; nothing in this brief needs a conversation to interpret.

**Read the tree before you read the description of it.** Two briefs in this batch described a state
the repository was not in, because they were written from backlog entries rather than from the code.
Every claim below was checked against `e79fb5b`, but check it again — `git log --oneline -10` and the
files themselves are the authority, and if this brief is wrong about something, fix the brief in your
commit.

## Read these first

1. `CLAUDE.md` at the repository root. Binding. *The console renders the product position* and
   *Technical debt is the scaling constraint* are the two sections this task turns on.
2. `.claude/rules/console-dev-loop.md` — especially *Logic with a wrong answer lives in Python*,
   which is the rule the Critical below violates for the second time.
3. `.claude/rules/console-surface.md`, `.claude/rules/console-hierarchy.md`.
4. `docs/superpowers/plans/2026-08-06-sync-console-expansion.md`.

## The work, in this order

### 1. Critical — two screens give a reviewer contradictory answers about the same payload

`web/src/features/pullrequests/evidence-bundle.tsx` renders node status `current` as **"Running
now."** `web/src/features/workflows/node-sequence.tsx` renders the identical status from the
identical payload as *"due now — the graph owes this node a visit"*.

Reproduced in Chrome at 1440×900 on `/findings/443b1719164579873939aaaecfa2902d/workflow/pull-request`:
that run's newest checkpoint is over 24 hours old and the page says something is running now.
`web/src/api/types.ts` documents `current` as *"the node the graph owes a visit, which is not the same
as 'has never run'"*, and `CLAUDE.md` names this exact case — nothing in our data tells a run parked on
the customer's CI from one that has died.

**The fix is not the sentence.** This is a classification with a wrong answer, and two components
spell it separately. Put the label in one place both screens read. `console-dev-loop.md` rules that
such logic belongs in Python, and names `isRunTerminal` and `hasLiveRun` (`web/src/api/queries.ts`) as
the standing violation of that rule — untested classification in TypeScript. Decide deliberately
between:

- a Python view-model field that both screens render, tested with `uv run pytest`, which is what the
  rule asks for; or
- one shared TypeScript module, if you can argue the payload does not survive the round trip — and
  then say plainly that it is untested, because the console still has no test runner.

Record the ruling in your commit body either way.

### 2. Important — the bundle presupposes a pull request that a `reported` run never opened

`evidence-bundle.tsx`'s stage blurbs are unconditional, so a run whose outcome is `reported` — one
that decided no patch was warranted — gets a page headed *"… pull request"*, a panel reading *"What
Sync actually opened."*, and five *"Never reached"* rows. Verified live on
`/findings/b45fb667d653b9187fe0d05ffe20a7df/workflow/pull-request`, whose `report_reason` is *"no patch
is warranted for field-deprecated on CreateMessage"*.

`web/src/features/workflows/workflow-page.tsx` links here unconditionally with the possessive *"See
the pull request's evidence bundle"*.

Condition the framing on the outcome the payload already carries. For `reported` and `abandoned`, lead
with what the run concluded and put the stages in the conditional, or say at the top that no pull
request exists for this run. Make the link's wording follow the same fact rather than asserting a pull
request in the link text.

### 3. Important — `RunOutcome` describes a layout it is not on

`web/src/features/pullrequests/pull-request-page.tsx` renders `RunOutcome` above a five-node bundle.
`web/src/features/workflows/run-outcome.tsx` was written for the eight-node screen, so it says *"The
attempt is still below in full, with everything each node produced"* — while the bundle deliberately
drops `locate`, `prepare` and `patch`. It also says *"The sequence below is the last state the
checkpointer recorded"* where there is no sequence, and *"The pull request is under `open_pr`"* where
the page labels that node "The pull request".

Either give the Pull Request level its own outcome panel whose sentences describe the five nodes it
actually renders, or parameterise `RunOutcome` with what is below it. One component must not make a
claim about a layout it does not know.

### 4. Important — a CI failure rendered as compiler output

`src/sync/dashboard/queries.py` builds each node's evidence from flat `channel_values`, and
`_EVIDENCE_KEYS` assigns `diagnostics` to `static_verify` alone. `src/sync/remediate/nodes.py` writes
that same channel from `locate`, `prepare`, `patch`, `push_branch`, `await_ci` (literally `"CI failed:
{url}"`) and `open_pr`.

So a run that typechecks, pushes, then fails CI renders `"CI failed: https://…"` inside a panel titled
**"What the compiler said"**, blurbed *"using the clone's own tsc"*.

Fix it at the attribution rather than the label if you can: have `workflow_state` surface `diagnostics`
under `static_verify` only when `verify_ok` is present and false, or have the node write a node-scoped
key. If you relabel instead, the blurb must say that the newest writer of this channel may not be the
compiler. Python change, tests first.

### 5. Important — the absence glyph painted at full ink

`web/src/features/bindings/binding-surface-page.tsx` has a `joinOrAbsent` helper returning the absence
glyph as a bare string, so the Argument keys and Response fields read columns render it at
`--color-ink` where every other absence in the console renders at `--color-ink-muted`. Measured through
`getComputedStyle`.

`web/src/lib/format.ts` documents this exact regression as already closed: the module knows only
`string | null`, and *"there is nothing left for a call site to forget"* — except this call site
forgot. Return `string | null` and render through the existing formatter. `DESIGN.md`: one glyph, one
appearance.

### 6. The error surface — make a thrown error visible instead of silent

This is new work rather than a review finding, and it is the reason the Critical went unnoticed for
half a day.

In React 19 an uncaught exception unmounts the subtree and leaves **nothing** behind — no message, no
box, no clue. On a console whose whole argument is that every state says what happened, a blank region
is the worst possible failure mode: it is indistinguishable from an honest empty state. The
interface-quality checklist's first item exists for this and names the two places a transport change
lands first — `run-outcome.tsx`'s branch for an outcome the console has never heard of, and
`evidence.tsx`'s `JSON.stringify` of unnamed evidence keys. Both are reached by data, not by clicking.

**Corrected against the tree on 2026-08-06, which is what this brief's own opening asks for.** A
boundary already exists: `web/src/components/error-boundary.tsx`, wrapping the `Outlet` in
`layouts/app-shell.tsx`. So this is not new work, and writing it as new work would have produced a
second boundary beside the first. What that boundary actually did wrong is four things, and each is
still worth fixing:

- **It swallowed the throw.** `componentDidCatch` filed the error on the central surface and told
  nobody else, so neither the browser console nor Vite's overlay ever saw it.
- **It named nothing.** The panel rendered `error.message` alone; the component stack went to the
  error surface and nowhere a reader could act on it.
- **There was no way to copy it.**
- **It never reset.** One boundary outside the `Outlet` survives every navigation, so a single crash
  left the crash panel standing over every screen after it until a reload.

Fix those, so a thrown exception becomes a visible, reportable state instead of a hole. The panel is a
state panel like the four in `web/src/components/states.tsx` and it belongs beside them; a fifth
sentence in a family that already distinguishes four kinds of nothing.

Two constraints:

- **It must not swallow the error.** Re-throw to the console, or log it, so Vite's overlay and the
  browser console still see it. The overlay is the fastest debugging surface there is in development
  and this must not replace it — it exists for production and for the case where the overlay is not
  watching.
- **It must not look like an empty state.** A screen that failed is not a screen with no data, and
  this console does not let one stand in for the other.

## Constraints that will not be obvious

- Twenty-four sentences carry the honesty distinctions, listed with file and line in
  `docs/superpowers/plans/2026-08-05-sync-console-architecture.md`. Restyling one is allowed; deleting,
  shortening, collapsing behind a disclosure or moving one into a tooltip is not. **Items 2 and 3 above
  both change sentences on screen — re-read your own diff for a deleted qualification.**
- No composite score, health figure, traffic light, green dot or liveness pulse. Item 1 is a liveness
  claim being removed; do not replace it with a dot.
- `DESIGN.md` is the authority for every visual value; `tests/test_console_design_tokens.py` fails on a
  raw Tailwind spacing utility inside `features/`.
- Logic with a wrong answer lives in Python. The console formats and renders.
- `scripts/seed_console.py` and `tests/test_seed_console.py` are owned by another session.

## How to work

Test first: write the failing test, run it, watch it fail for the reason you expect, then implement.

```sh
SYNC_API_RELOAD=true uv run python -m sync.api
uv run python scripts/seed_console.py
cd web && npm run dev
```

`SYNC_API_RELOAD=true` is not optional. Both findings 1 and 2 above were found by *looking at the
running screen*, not by reading the diff, and both were invisible in the diff.

**Use the running screen and its error surfaces to debug.** Vite's overlay and the browser console are
the fastest path from a symptom to a line; reasoning about what a component will render is the slowest.
`superpowers-chrome:browsing` is installed for exactly this.

## Your gate, before every commit

```sh
uv run pytest tests/ -q
cd web && npm run build && npm run lint
```

All three clean, plus a stated observation of each screen you changed, on a real seeded finding of each
outcome — `opened`, `reported`, `abandoned`, and one still in flight. Findings 2 and 3 only appear on
the outcomes that are not `opened`.

If the local pytest run fails in a way that looks like database contention — hundreds of errors that
pass when re-run with `-n0` — several agents are sharing one Postgres. Re-run serially and say so.

Commit in Conventional Commits form, body in normal prose explaining why. Push your branch. **Do not
open a pull request and do not push to `main`.**
