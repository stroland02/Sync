# Brief — the Codebase level, and the two routes that exist because it does not

You are working in your own Orca workspace on a branch based on `m4-dashboard`. Everything you need
is in the repository; nothing in this brief needs a conversation to interpret.

## Read these first, in this order

1. `CLAUDE.md` at the repository root. It is binding. The sections that matter most to you are *The
   console renders the product position*, *Technical debt is the scaling constraint*, and *How we
   work*.
2. `.claude/rules/console-hierarchy.md`, `.claude/rules/console-surface.md`,
   `.claude/rules/console-dev-loop.md`, `.claude/rules/interface-originality.md`.
3. `docs/superpowers/specs/2026-07-25-sync-self-maintaining-apis-design.md`, section *M4 — Hosted
   control plane / Information architecture*. **Cite the second fenced block**, the one the document
   labels authoritative — the first is kept deliberately superseded and citing it is the exact
   failure `console-hierarchy.md` exists to prevent.
4. `docs/superpowers/BACKLOG.md`, entry **B92**, which is the work.
5. `docs/superpowers/plans/2026-08-05-sync-console-architecture.md`, Task 9, which carries it.

## The work

The design document's hierarchy starts at `Codebase (the selected repository)` and says why: *a user
starts from a repository, not from a vendor list, because the question they actually have is "what is
wrong with my code"*. Nothing in the console selects a repository.

The screen already exists. `/bindings/repositories/:repoId` takes exactly that parameter and reports
what the index sees in one repository — but it is labelled *Repository coverage*, addressed as a
child of `/bindings`, and reachable only from a lookup form. Two routes exist purely to reach it:
`/bindings` is three text fields that navigate to a URL, and `/observed-telemetry` is a repository
picker wrapped around one panel. Both are repository selectors that do not know they are one.

Build the level, and delete what existed to work around its absence:

- `/repositories/:repoId` is the Codebase level, reachable by clicking a repository row on the fleet
  index rather than by typing an identifier into a form.
- `/bindings` and `/observed-telemetry` leave `routes.ts`. Deleting them is part of the task, not a
  follow-up — a dead route that still typechecks is the debt this repository has paid for twice.
- Every figure on every screen below Codebase changes when a different repository is picked.

That last point is the hard half, and it is where the honesty rules bite. `/api/overview`,
`/api/detectors` and `/api/corpus` are fleet-wide today and take no `repo_id`. **An unscoped answer
rendered underneath a selected repository is a false claim about that repository** — the same class
of defect this milestone has already closed six times.

You have two honest ways to resolve that, and you must pick one per figure and record which:

1. Scope the query. The API is read-only and `tests/test_api_routes.py` holds that behaviourally;
   adding a `repo_id` filter to a read route is in scope for you, tests first.
2. Say so on screen. A figure that genuinely cannot be scoped stays, and states in words that it is
   fleet-wide. It never sits silently under a repository heading.

What you may not do is render a fleet-wide number under a repository name and leave the reader to
find out.

## Constraints that will not be obvious

- Every value in `GRAPH_LEVELS` cites the specification line that defines it. If your work needs a
  level the specification does not have, the specification is amended first, as a dated amendment
  inside that section, and only then the console. `tests/test_console_hierarchy.py` fails otherwise,
  and it is meant to.
- Twenty-four sentences on screen carry the honesty distinctions, listed with file and line in
  `docs/superpowers/plans/2026-08-05-sync-console-architecture.md`. Restyling one is fine. Deleting,
  shortening, collapsing behind a disclosure, or moving one into a tooltip is not. **Re-read your own
  diff for a deleted qualification before you commit** — nothing tests prose.
- No composite score, health figure, traffic light, green dot or liveness pulse. Ever. The console
  refuses a scalar because the scalar has no referent in the graph.
- `DESIGN.md` is the authority for every visual value. Three spacing tokens and two named exceptions;
  a raw Tailwind spacing utility inside `features/` fails
  `tests/test_console_design_tokens.py`. Dark mode only — the theme resolver is deleted, and a
  component that branches on `prefers-color-scheme` is a regression against a recorded decision.
- Logic with a wrong answer lives in Python, because the console has no test runner. Formatting and
  rendering live in TypeScript.
- `scripts/seed_console.py` and `tests/test_seed_console.py` are owned by another session. Use them;
  do not edit them.

## How to work

Test first, always: write the failing test, run it, watch it fail for the reason you expect, then
implement. A test that has never failed has never been shown to test anything.

Run the console while you build it, from the repository root:

```sh
SYNC_API_RELOAD=true uv run python -m sync.api
uv run python scripts/seed_console.py
cd web && npm run dev
```

`SYNC_API_RELOAD=true` is not optional. A long-lived API process serves whatever Python it started
with, Vite hot-reloads on top of it, and the pairing looks entirely plausible while being wrong.

## Your gate, before every commit

```sh
uv run pytest tests/ -q
cd web && npm run build && npm run lint
```

All three clean. `npm run build` passing is not evidence that the screen is right — TypeScript checks
the console against the types the console declares, not against what the API sends — so state a human
observation of the running screen alongside it.

Commit in Conventional Commits form with the body in normal prose explaining why. Push your branch.
**Do not open a pull request and do not push to `main`** — the coordinator merges your branch into
`m4-dashboard`, which is where the open pull request already runs CI.

If you find something genuinely blocked, finish everything that is not blocked, then report what you
left and why. Do not stop and wait.
