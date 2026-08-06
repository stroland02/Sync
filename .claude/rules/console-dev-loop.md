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

## `npm run build` passing is not evidence

TypeScript checks the console against the types the console declares, not against what the API
sends. `a6ee379` removed a field from a payload; `types.ts` still declared it, so the build stayed
green while a column rendered the absence marker on every row forever — which reads as "none
retracted" when the truth is "this view cannot see them". The two sides are held together by Python
tests that read the TypeScript, not by the compiler.

## Logic with a wrong answer lives in Python

**The console has no test runner.** `web/package.json` declares `dev`, `build`, `lint` and
`preview`, and no `test`. So any rule with a wrong answer — which node is current, which run is
terminal, how a run is grouped — belongs in Python, where `uv run pytest` can hold it and
`CLAUDE.md`'s test-first rule applies. The console formats and renders.

**That has been violated once, and the violation is still in the tree.** `isRunTerminal`
(`web/src/api/queries.ts:82`) and `hasLiveRun` (`:116`) are classification. Their own docstrings
state what a wrong answer costs — reading a live run as terminal "stops the poll on a live run,
which freezes the screen on a stale answer" — and nothing tests either of them.

Decision 6 of `docs/superpowers/plans/2026-08-05-sync-console-architecture.md` rules that the
deferral retires and Task 5 adds Vitest, `@testing-library/react` and `jsdom`. **Task 5 has not
landed**, so the rule above still binds. When it does, the scope is classification and structural
invariants — never class names, never snapshots — and the repository gains a second test discipline
with the same proven-RED requirement.

## So verification is, today

`npm run build` clean, `npm run lint` with no new error-level violations, and a stated human
observation of the running screen. A scale claim ships with three numbers at `--scale 10000`: time
to first paint, DOM node count, payload size — before and after.

## The API stays read-only

No route mutates the graph, triggers a run, or touches a customer repository.
`test_no_route_reaches_past_the_read_surface` (`tests/test_api_routes.py:1101`) holds that
behaviourally and extends to every new route; a route it does not cover is an untested hole in the
guarantee, not an untested route.

`src/sync/mcp/tools.py` is frozen. The console reads aggregate answers through `sync.dashboard`,
per-finding answers through `GraphSurface`, and the transport issues no SQL of its own.
