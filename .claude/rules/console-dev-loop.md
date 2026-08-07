---
paths:
  - "web/**"
  - "src/sync/api/**"
  - "src/sync/dashboard/**"
  - "scripts/seed_console.py"
---

# Running the console, and what its green checks do not prove

## The loop

Two processes and a fixture, from the repository root:

```sh
SYNC_API_RELOAD=true uv run python -m sync.api   # 8787 — the port web/vite.config.ts proxies /api to
uv run python scripts/seed_console.py            # --scale N adds N synthetic call sites and findings
cd web && npm run dev                            # 5173
```

`SYNC_GRAPH_DSN` names the graph and `SYNC_CHECKPOINTER_DSN` the LangGraph checkpointer, the second
falling back to the first because every local developer runs both on one Postgres. `--remove`
deletes exactly the rows a run wrote; with `--scale` it removes the synthetic repository and leaves
the base fixture. **`scripts/seed_console.py` and `tests/test_seed_console.py` are owned by another
session** — use them, do not edit them.

## The trap this file exists for

**A long-lived API process serves whatever Python it started with, and nothing anywhere signals the
drift.** Vite hot-reloads, so the frontend is always current — which makes the mismatch worse rather
than better: the screen is new, the payload is old, and the pairing looks entirely plausible.

On 2026-08-05 that cost half an hour of a verification agent's walk through the console. The process
had started before two commits it was verifying, so the agent would have certified the exact defect
it had been dispatched to catch, and could reasonably have concluded that a field the code emits
does not exist.

`SYNC_API_RELOAD=true` closes it structurally, which is why it is in the command above rather than
in a footnote. The flag defaults to off — reload costs a file watcher and a subprocess, and a
production process must never acquire either by accident — and an unrecognised value raises rather
than falling back, because a typo falling back either way would be invisible. If you run without it,
either restart the API or confirm its start time postdates the last Python commit before believing
anything on screen.

## One console, one port, one branch — the ordered methodology

**Set by the owner on 2026-08-06, after an afternoon of looking at four different consoles and being
unable to tell which was current.** Five workspaces had dev servers up; Vite picks the next free port
on every restart, so their URLs moved; one was serving a mid-build branch with no API behind it and
rendered ninety-two *"The API is unreachable"* errors. The owner is not required to know which of
those is real. The order below removes the question.

1. **There is exactly one console the owner looks at: `http://localhost:5173`.** It is started from
   the **coordinator's worktree** (`.claude/worktrees/sync-m4-dashboard`) with `--port 5173
   --strictPort`, and it serves the **integration branch** — whatever branch merged work lands on,
   `console-identity` during M7. Nothing else is ever given to the owner as a URL.
2. **A worker never serves the owner.** Work happens on a branch in a workspace, is gated there,
   is pushed, and is **merged by the coordinator**. The owner sees it after the merge, on 5173, and
   never before. A worker's branch is not a preview.
3. **A worker may still run a server to verify its own work** — the rule that a change ships with a
   stated observation of a running screen has not moved. It runs on a free port the worker chooses,
   it is never mentioned to the owner, and **it is stopped before the worker reports.** A server
   left listening is the defect this section exists to stop.
4. **After every merge the coordinator restarts 5173** so the owner's console is the merged tree,
   and says so. Until a merge lands, 5173 serving the previous tree is correct rather than a fault —
   say that plainly instead of implying newer work is visible.
5. **One API, on 8787**, started from the same worktree with `SYNC_GRAPH_DSN` set. A console with no
   API behind it produces a screenful of unreachable errors that look like a defect in the console
   and are not.

The failure this prevents is not wasted ports. It is the owner forming a judgement about the product
from a half-built branch, or from a stale one, with no way to tell which they are looking at.

## The owner should not be looking at the automation browser

`superpowers-chrome` drives **one persistent shared Chrome**, launched with `--no-sandbox` — which is
why that infobar sits at the top of every screenshot taken in it. Any agent that measures a screen
resizes **that window**, and the owner watching it sees the console jump between widths for no reason
they can see. Measured on 2026-08-06: 1920×889, then 929×861 a minute later, mid-worker.

Open the owner's console in an ordinary browser window. The automation browser belongs to the agents
and is expected to change size under them.

## Clear the viewport override, every time, or the owner sees a windowed console

`superpowers-chrome`'s `set_viewport` is a **CDP device-metrics override on a persistent, shared
Chrome instance**. It is the right tool for measuring a screen at 1440×900 or 1280×800, and it does
not end when your task does: it survives navigation, it survives the page being closed, and it
survives the session. Nothing clears it but `clear_viewport`.

**Measured on 2026-08-06, after most of a day of confusion.** An override left applied the previous
day pinned the console to a fraction of the window in every screenshot the owner took, with white
space to the right and below. Two agents measured `main` at full width and the owner's own eyes said
otherwise, repeatedly, and both were correct — they were looking at the same page through different
overrides. With it cleared: `innerWidth` 1920, `main` 1905, no horizontal overflow. The app had
always filled the window.

**The rule:** every `set_viewport` is paired with a `clear_viewport` before the task ends, in the
same way a dev server started is a dev server stopped. If you are unsure whether one is applied,
`get_viewport` costs nothing and a reported size that does not match the window is the answer.

This matters more than it sounds. A viewport override does not look like a bug — it looks like a CSS
defect in the thing you are building, and it will send the next session hunting for a `max-width`
that does not exist.

## `npm run build` passing is not evidence

TypeScript checks the console against the types the console declares, not against what the API
sends. `a6ee379` removed a field from a payload; `types.ts` still declared it, so the build stayed
green while a column rendered the absence marker on every row forever — which reads as "none
retracted" when the truth is "this view cannot see them". The two sides are held together by Python
tests that read the TypeScript, not by the compiler.

## Logic with a wrong answer is tested, and where it lives is now a judgement

**The console has a test runner as of 2026-08-06 (M4-W153).** `npm test` is `vitest run` over
jsdom, and Task 5 of `docs/superpowers/plans/2026-08-05-sync-console-architecture.md` retired the
deferral its own Decision 6 had already ruled retired. `isRunTerminal` and `hasLiveRun`, the two
classifiers this file named as the standing violation, are tested; so are the cardinality
threshold, `describeRung`'s exhaustiveness, `formatElapsed`, an option counted at zero, and every
declared route being reachable from the shell.

So the rule is no longer "TypeScript cannot hold a rule with a wrong answer". It is this:

- **A rule the payload can answer belongs in the payload.** Which node the graph owes a visit, how
  a run is grouped, which run is terminal *as a fact about the run* — Python computes it, one
  answer reaches every screen, and two components cannot disagree about it. That is not a statement
  about where the tests are; it is the reason the Critical of 2026-08-06 was a Critical, and
  `sync.dashboard.queries`'s `standing` field is where it was fixed. **Do not port that back.**
- **A rule about the rendered view stays here, and is tested here.** Whether a set is small enough
  to list, what a disclosure header counts, whether a poll should keep asking — a viewport is not
  in the payload, and the frozen surface serves an agent that has none.

**Scope, so the runner does not become a snapshot habit.** Classification, derivation and
structural invariants. Never class names. Never snapshots — a snapshot in a console being actively
restyled fails on every correct change, and it will be deleted within a week by whoever it blocks.
Anything about rendered pixels is measured in Chrome and written into `DESIGN.md`, which is a
different discipline with a different gate.

**The proven-RED requirement applies here exactly as it does in `tests/`.** Every guard in
`web/src/**/*.test.*` was shown red against a deliberately broken subject before it was trusted.
`CLAUDE.md`'s *Test first, always* is now a TypeScript rule too, and that is a permanent increase
in per-task cost that Decision 6 states rather than hides.

## So verification is, today

`npm run build` clean, `npm run lint` with no new error-level violations, `npm test` green, and a
stated human observation of the running screen. A scale claim ships with three numbers at
`--scale 10000`: time to first paint, DOM node count, payload size — before and after.

## The API stays read-only

No route mutates the graph, triggers a run, or touches a customer repository.
`test_no_route_reaches_past_the_read_surface` (`tests/test_api_routes.py:1101`) holds that
behaviourally and extends to every new route; a route it does not cover is an untested hole in the
guarantee, not an untested route.

`src/sync/mcp/tools.py` is frozen. The console reads aggregate answers through `sync.dashboard`,
per-finding answers through `GraphSurface`, and the transport issues no SQL of its own.
