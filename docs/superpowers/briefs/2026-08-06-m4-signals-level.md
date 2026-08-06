# Brief — finish the Signals level, and retire the shim it landed with

You are working in your own Orca workspace on a branch based on `m4-dashboard`. Everything you need
is in the repository; nothing in this brief needs a conversation to interpret.

## Read these first, in this order

1. `CLAUDE.md` at the repository root. Binding. Read *The console renders the product position* and
   *Technical debt is the scaling constraint* carefully — the second one is why this task exists as a
   task rather than as a comment in a file.
2. `.claude/rules/console-hierarchy.md`, `.claude/rules/console-surface.md`,
   `.claude/rules/console-dev-loop.md`, `.claude/rules/interface-originality.md`.
3. `docs/superpowers/specs/2026-07-25-sync-self-maintaining-apis-design.md`, section *M4 — Hosted
   control plane / Information architecture*. **Cite the second fenced block**, the one the document
   labels authoritative. The three signal roles are defined a little below it.
4. `docs/superpowers/BACKLOG.md`, entries **B93** and **B94**.
5. `docs/superpowers/plans/2026-08-06-sync-console-expansion.md`, workstream 3, which is this brief's
   parent.
6. Commit `b39dcde`, which is what landed and what you are continuing.

## Where this stands

The Signals level landed on 2026-08-06 with one panel of one role. `web/src/features/signals/`
carries the page and `not-attached-state.tsx`; `web/src/features/telemetry/observed-telemetry-page.tsx`
is now a one-line re-export shim so the route declaration could move separately from the component.

That shim is deliberate, scoped debt with this brief named as what retires it. Retiring it is the
first thing you do, not the last.

## The work

**Move the route.** `routes.ts` still declares both observed-telemetry routes at level
`Errors & Incidents`. Observed calls, shapes and error windows are what a *signal source produced* —
a reading, not a claim — and declaring a signal at the findings level puts a reading where a claim
belongs. That is the interface undoing the distinction the rung discipline exists to protect. The
route is declared at `Signals`, sits under API Services, and is scoped by repository. Delete the
shim in the same change.

**Make the level honest about its own coverage.** The specification asks for one panel per attached
integration grouped by role — vendor, signal source, human surface. Today the vendor role has the
registry behind it, the signal-source role has the Sentry ingest behind it, and **the human-surface
role has nothing in the tree at all**. So the level's header states which roles have an integration
attached and which do not. One panel of one role must never read as three integrations existing.

This is exactly the distinction `not-attached-state.tsx` was written for, and its docstring carries
the argument: *attached and quiet* is a fact about traffic, *nothing is attached* is a fact about
configuration, and the console does not let one stand in for the other. Use it; do not reach for
`EmptyState`, which documents itself as "the API answered, and the answer was nothing".

**Do not fake the third role.** B94 records that the level is genuinely blocked from being complete
until M5's correlation join, and being blocked is the thing to render, not the thing to paper over.
A panel that says nothing is attached is finished work. A panel invented so the grid looks even is a
false claim.

## Constraints that will not be obvious

- Every value in `GRAPH_LEVELS` cites the specification line that defines it, and
  `tests/test_console_hierarchy.py` holds the vocabulary against the specification's authoritative
  block. Moving a route between levels is fine; inventing a level is not.
- Repository scope matters here and another workstream is building the Codebase level in parallel
  (`briefs/2026-08-06-m4-repository-level.md`). Scope the Signals route by `repoId` as the URL already
  allows, and do not rebuild a repository picker — if the parameter is present, use it; if the fleet
  index does not yet link here, say so in your report rather than building a form.
- Twenty-four sentences on screen carry the honesty distinctions, listed with file and line in
  `docs/superpowers/plans/2026-08-05-sync-console-architecture.md`. Restyling one is allowed;
  deleting, shortening, collapsing behind a disclosure or moving one into a tooltip is not. **Re-read
  your own diff for a deleted qualification before you commit.**
- No composite score, health figure, traffic light, green dot or liveness pulse. A role with an
  attached integration does not get a green dot for having one.
- `DESIGN.md` is the authority for every visual value; three spacing tokens and two named exceptions,
  and `tests/test_console_design_tokens.py` fails on a raw Tailwind spacing utility inside
  `features/`. That test caught `p-4` and `mt-1` in this feature's own first commit. Dark mode only.
- Logic with a wrong answer lives in Python. The console formats and renders.
- `scripts/seed_console.py` and `tests/test_seed_console.py` are owned by another session. Use them;
  do not edit them.

## How to work

Test first: write the failing test, run it, watch it fail for the reason you expect, then implement.

Run the console while you build it, from the repository root:

```sh
SYNC_API_RELOAD=true uv run python -m sync.api
uv run python scripts/seed_console.py
cd web && npm run dev
```

`SYNC_API_RELOAD=true` is not optional. A long-lived API process serves whatever Python it started
with while Vite hot-reloads on top of it, and the mismatch looks entirely plausible — it cost a
verification agent half an hour on 2026-08-05.

## Your gate, before every commit

```sh
uv run pytest tests/ -q
cd web && npm run build && npm run lint
```

All three clean, plus a stated observation of the running screen.

Commit in Conventional Commits form with the body in normal prose explaining why. Push your branch.
**Do not open a pull request and do not push to `main`** — the coordinator merges your branch into
`m4-dashboard`, where the open pull request already runs CI.

Finish everything that is not blocked before reporting, and name what you left and why.
