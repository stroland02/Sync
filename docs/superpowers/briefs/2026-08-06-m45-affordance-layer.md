# Brief — M4.5-W141, the affordance layer, and the first change the owner will actually see

You are working in your own Orca workspace on a branch based on `m4-dashboard`. Everything you need
is in the repository.

**Start by rebasing.** `git fetch origin && git checkout -B m45-affordance origin/m4-dashboard`.
Your workspace is behind by at least one slice, and two agents have already lost an hour to
conflicts caused by starting from a stale base.

## Why this one matters more than its position in the plan

The owner looked at the console today and said it looks the same as yesterday. They were partly
looking at a stale dev server, but the substantive half is true: everything that landed today was
correctness, measurement and two new levels. **Nothing changed how the console feels to use.** This
item is the one that does, and it has been moved ahead of the architecture plan's Tasks 5 through 7
for that reason.

So: prefer a change a person notices in the first ten seconds over one that is only defensible in a
diff. That is not a licence to decorate — everything below still binds — it is a statement about
which of several correct options to pick.

## Read these first

1. `CLAUDE.md`. Binding. *The console renders the product position* and *Technical debt is the
   scaling constraint*.
2. `.claude/rules/interface-originality.md` — **read it twice.** The interface is ours. Competitors
   and references are studied for concepts and workflows, never for how a screen should look, and
   nothing under `docs/superpowers/references/screenshots/` is opened at any point.
3. `.claude/rules/console-surface.md`, `.claude/rules/console-dev-loop.md`.
4. `DESIGN.md`, the contract for every visual value.
5. `docs/superpowers/plans/2026-08-06-m45-console-quality.md`, **Task 2**, which is this brief.
6. `docs/superpowers/reports/2026-08-06-console-conformance.md` — the measured baseline. Your work
   must not regress an invariant it records as clearing.
7. `docs/superpowers/BACKLOG.md`, entries **B90**, **B100**, **B109**.

## The work

A headless table layer and progressive disclosure, on **the two or three screens where the absence
costs an operator something** — the vendor findings table and the binding surface are the
candidates, because both are long. **A slice, not a sweep.** Adding a component to every screen is
the failure mode.

What is already there and what is not:

- **Filtering landed today** (M4-W135). Severity and call-site path on vendor findings, repository
  and path on the binding surface, each facet computed without the filter it sets. Build on it;
  do not rebuild it.
- **Sorting is B100 and is the gap.** It needs a server-side `ORDER BY`, because sorting a page is
  sorting the wrong thing — the page is a window on a set the client cannot see. `whats_at_risk` is
  frozen and offers none, but `graph_views.vendor_findings` is ours and already carries the filters.
  The page total must come from the same query as the rows.
- **Virtualisation** is a real question at `--scale 10000` and B109 measured why: a 32-character
  finding id wraps to three lines in a 164px column, so rows are 80px and eleven fit above the fold.
  Whether you virtualise or fix the column is your call — **measure before deciding**, and note that
  `break-words` has to survive whatever you pick.
- **A table library is a dependency decision**, governed by
  `references/engineering/dependencies-and-packaging.md`. The last worker declined TanStack with an
  argument. You may overturn that, but the argument goes in the commit body and the backlog entry,
  not in a `package.json` diff.
- **Progressive disclosure**: `dialog.tsx`, `command.tsx`, `input.tsx` and `input-group.tsx` are
  vendored and mostly unused. Evidence is the obvious candidate — `evidence.tsx` renders a `<pre>`
  block inline where a reader wants to open one thing without losing the run they are reading.

## The rule that keeps this from becoming taste

**A distinction that exists in the data earns a distinction on screen. One that does not, does not
get invented.** That is the same rule that indexed the surface ramp by job rather than depth, and
the same one that refuses a health score — the scalar has no referent in the graph.

Density, emphasis and depth each have to answer to something the graph stores. Motion is the
sharpest case and is **not** yours: three measured reference surfaces declare one `@keyframes` each,
run nothing decorative at rest, and do not animate a primary action on hover. Motion claims a time,
so it is permitted only where the data holds one — and that is `M4.5-W143`, a separate item. Do not
spend it here.

## What you may not do

- **No composite score, health figure, traffic light, green dot, liveness pulse or count-up.** Asked
  for and refused four times, and a component catalogue is exactly the moment somebody reaches for a
  coloured badge.
- **No sentence deleted to make a screen tidier.** Twenty-four sentences carry the honesty
  distinctions and are listed with file and line in
  `docs/superpowers/plans/2026-08-05-sync-console-architecture.md`. Restyling is allowed; deleting,
  shortening, collapsing behind a disclosure or moving into a tooltip is not. **Progressive
  disclosure is precisely the mechanism that would hide one by accident — re-read your own diff for
  a deleted qualification before every commit.**
- **A filtered-to-empty view must stay distinguishable from a genuinely empty one**, and both from a
  view that cannot see. Three states, three sentences; `components/states.tsx` and
  `features/signals/not-attached-state.tsx` carry the existing four.
- **Do not regress a cleared invariant.** Two ink levels plus one accent, two font weights, the
  5.05:1 text floor against rendered pixels, the 11px size floor. The conformance report says which
  currently clear.
- No new token, elevation level, spacing value or type step without an argued change to `DESIGN.md`.

## How to work

Test first where a test is possible. Sorting is classification with a wrong answer, so it lives in
Python with `uv run pytest` holding it — `.claude/rules/console-dev-loop.md` is explicit, and the
console still has no test runner.

```sh
SYNC_GRAPH_DSN=postgresql://sync:sync@localhost:5433/sync SYNC_API_RELOAD=true SYNC_API_PORT=<free> uv run python -m sync.api
uv run python scripts/seed_console.py --scale 10000
cd web && SYNC_API_ORIGIN=http://127.0.0.1:<free> npm run dev
```

`SYNC_API_ORIGIN` exists so you never edit `vite.config.ts` to reach a port. Five workspaces share
this machine and 8787 and 5173 are usually taken, sometimes by dead processes that still hold the
port. Pick free ports, and stop both servers when you finish.

## Your gate

```sh
uv run pytest tests/ -q
cd web && npm run build && npm run lint
```

All clean, **plus three numbers at `--scale 10000` before and after** — time to first paint, DOM
node count, payload size — and a stated observation of each screen you changed. A scale claim
without numbers is an impression.

If the local pytest run fails with hundreds of errors that pass under `-n0`, that is Postgres
contention between agents rather than a defect.

Conventional Commits, subject carrying `M4.5-W141`. Push your branch. **No pull request, nothing on
`main`.**
