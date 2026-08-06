# The Sync operator console

A read-only React front end over Sync's API Dependency Graph. Every screen is one level of the
graph's hierarchy; the hierarchy itself is not this file's to state, because it already has an
authority — see *The hierarchy* below.

Nothing here writes. Every screen is a GET, and no route in the transport behind it mutates the
graph, starts a remediation run, or touches a customer repository
(`.claude/rules/console-dev-loop.md`, *The API stays read-only*).

## Running it

Two processes and a fixture, from the repository root — the full loop, including the environment
variables that name the graph and the checkpointer, and the trap around a stale reloaded process,
is `.claude/rules/console-dev-loop.md`:

```sh
SYNC_API_RELOAD=true uv run python -m sync.api   # 8787 — vite.config.ts proxies /api here
uv run python scripts/seed_console.py            # fixture data
```

Then, from this directory:

```sh
npm install
npm run dev                                       # 5173
```

`npm run build` runs `tsc -b` then Vite's build; `npm run lint` runs `oxlint`. Both are expected
to be silent — `web/` has no CI gate of its own, and a warning here is a defect. **There is no
`npm test`.** That is deliberate, not unfinished: `.claude/rules/console-dev-loop.md` says which
logic belongs in Python instead, and why.

## The hierarchy

Every destination the console declares — the router, the persistent navigation, and the
Cmd/Ctrl-K command palette — reads one array: `GRAPH_LEVELS` and `ROUTES` in
`web/src/lib/routes.ts`. That file is not where the hierarchy comes from; it is where the
hierarchy is checked. The source is
`docs/superpowers/specs/2026-07-25-sync-self-maintaining-apis-design.md`, *M4 — Hosted control
plane / Information architecture*, and `.claude/rules/console-hierarchy.md` states which of that
section's two fenced blocks is the authoritative one and why a level with no line there does not
belong in `GRAPH_LEVELS`. `tests/test_console_hierarchy.py` parses both sides and fails the build
if they disagree.

Read `routes.ts`'s own docstring for the current levels, the current routes, and the two
placement decisions that are not obvious from a route's own file. Do not expect this README to
repeat them — a route list here is a second copy for the two to disagree about, and the reconciled
hierarchy is exactly what drifted silently once already
(`.claude/rules/console-hierarchy.md`, *The failure this exists to prevent*).

## Design

Dark-only. `DESIGN.md` at the repository root is the token contract — every colour, size, space
and elevation value, with the arithmetic that proves each pairing clears the contrast floor.
`.claude/rules/console-surface.md` carries what binds while a screen is open, including the
sentences a screen may not delete, shorten, or hide behind a disclosure.

## Where things are

| | |
|---|---|
| Route registry, the hierarchy checked against the graph levels | `src/lib/routes.ts` |
| Router, built from the registry | `src/App.tsx` |
| Shell, persistent navigation, command palette | `src/layouts/` |
| One directory per screen | `src/features/` |
| Response types, fetching, errors | `src/api/` |
| Route handlers and payloads | `src/sync/api/app.py` |
| The workflow view's data | `src/sync/dashboard/` |

Constants that exist in both languages — the default page size, the remediation graph's node
order, the evidence keys each node produces — are restated in TypeScript because it cannot import
Python, and Python tests (`tests/test_api_routes.py`, `tests/test_dashboard_queries.py`) fail the
two sides apart when they drift.
