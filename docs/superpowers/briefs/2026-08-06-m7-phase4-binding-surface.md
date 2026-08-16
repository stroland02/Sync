# Brief - M7-W164, the Binding surface level onto the chassis

You are working in your own Orca workspace. **Start by rebasing:**
`git fetch origin && git checkout -B m7-bindings origin/console-identity`. The base is
`console-identity`, not `main` and not `m4-dashboard`.

M7's Phase 4 recomposes the nine specification levels onto the chassis that landed as M7-W160. This
is the second, running in parallel with M7-W163 on the Fleet level. **You own
`web/src/features/bindings/` and `web/src/features/vendors/`. The other worker owns
`web/src/features/fleet/`.** Do not edit outside your two directories without saying so.

## Read these first, and the first two are not optional

1. **`docs/superpowers/reports/2026-08-06-why-the-console-came-out-flat.md`.** Six causes, all of
   them written rules rather than mistakes.
2. **`.claude/rules/interface-originality.md`**, as amended on 2026-08-06. It separates the
   conventions of the form from identity.
3. `CLAUDE.md`; `.claude/rules/console-surface.md`; `.claude/rules/console-hierarchy.md`;
   `.claude/rules/console-dev-loop.md`.
4. `docs/superpowers/references/direction/NOTES.md` - the owner's six worked examples.
5. `DESIGN.md`, `web/src/layouts/app-frame.tsx`'s docstring, and **`B115` in
   `docs/superpowers/BACKLOG.md`**, which was re-measured by the chassis item and is about this exact
   screen.

## Why this screen and not another

`features/bindings/binding-surface-page.tsx` is 429 lines, the largest feature file in the console
and its densest screen: nine columns of evidence. It is also the screen every width decision has been
measured against. B115 records the current state precisely, and the numbers matter to you:

- The row height drops from **77px to 57px at 1170px of content width** and nowhere else. That
  threshold was found by stepping the surface's width in 2px increments.
- At 1440 with the sidebar collapsed the content box is 1297px, which clears it by 127px, and the row
  is 57px.
- At 1280 the content box is 1137px collapsed, **33px short**, and the row is 77px in every
  configuration. **The chassis does not fix 1280 and nobody should pretend otherwise.** B115 names
  1617px of content as the width at which the row reaches 37px.

So this screen has a real, measured, unsolved density problem, and your item is not required to solve
it. What your item must not do is make it worse, or hide it.

## What you are building

Recompose the binding surface and the vendor level onto the chassis primitives:

- **`layouts/page-header.tsx`** - the display step and `RouteEntry.question` from `lib/routes.ts`,
  which exists for every route and renders on none of them today.
- **`layouts/control-bar.tsx`** - the scope selectors and search on the left, at most one primary
  action on the right, never two.
- **`layouts/footer-bar.tsx`** - pagination, page size and record count, wrapping
  `components/page-controls.tsx`. **Keep reading `next_offset`**; do not compute a page count from a
  total that may be bounded.
- **`components/fact-tile.tsx`** / **`fact-list.tsx`** - the label register above the value register.
  The binding surface's definition lists are the clearest case for these in the whole console.
- **`components/skeleton.tsx`** for values in flight. It replaces nothing in `states.tsx`.

## The debt you are here to resolve

**There are two components named `ControlBar`.** `components/filters.tsx` exports one, and
`binding-surface-page.tsx` and `vendor-findings-table.tsx` - both yours - import it. The chassis
added `layouts/control-bar.tsx`, which is the one every screen is meant to use.

Resolve it, because both callers are in your two directories:

- Decide which one survives. The layout one is the chassis primitive and is the likely answer, but
  read both before deciding - the filters one may carry facet behaviour the layout one does not, in
  which case the honest outcome is that the filters component keeps its behaviour under a name that
  says what it is (it is a facet control, not a control bar) and renders *inside* the layout one.
- **Make the change in one commit with the rename**, and say in the body which you kept and why. A
  deprecated second copy left behind is the exact debt `CLAUDE.md` names: a dead path that still
  typechecks and still gets maintained by someone who cannot tell it is dead.
- The other worker has been told not to touch either file and to file a backlog entry instead. If
  they filed one, close it in your commit and reference the number.

## What must not break, and the first one has no second chance

- **`tests/test_console_honesty_sentences.py`** guards seventeen fragments and is not file-pinned, so
  a sentence may move and only deletion or shortening fails. **Your directories carry several of
  them**, including `sideways scroll` - which is about this screen specifically: provenance rendered
  is not provenance visible, and the rung column's position is a layout constraint rather than a
  preference. If your recomposition pushes the rung column behind a horizontal scroll, you have
  broken the thing that sentence exists to prevent, and the sentence will still be on screen saying
  so. Also `deliberately not merged`, `has no denominator`, `cannot tell the two apart`,
  `no finding here to attribute`, `do not all rest on one rung`. Run the test after every change.
- **No composite score, health figure, traffic light, green dot, liveness pulse or count-up.** The
  rung is never coloured - `never its hue` is a protected sentence and it means it.
- **`tests/test_console_design_tokens.py`** plus the chassis's additions, including a raw-source scan
  that sees keyframe names inside comments.
- **`lib/motion.ts`**'s registry is bound to the tree in both directions by a Python guard.
- `components/states.tsx`, `status.tsx`, `provenance.tsx`, `lib/format.ts` - product logic. Call sites
  may move; sentences and the `string | null` discipline may not.
- **`web/src/lib/routes.test.tsx`** is the reachability guard.

## How to work

```sh
SYNC_GRAPH_DSN=postgresql://sync:sync@localhost:5433/sync SYNC_API_PORT=<free> uv run python -m sync.api
uv run python scripts/seed_console.py --scale 10000
cd web && SYNC_API_ORIGIN=http://127.0.0.1:<free> npm run dev -- --port <free>
```

**5173 is the owner's console and 8789 is the API behind it - leave both alone.** Never edit
`vite.config.ts` to reach a port. Stop every server you start before you report, **and kill its shell
wrapper too** - B118 records a listening socket held by a dead PID because only the child was killed,
and it cost an hour of debugging the wrong process.

If you use Chrome to measure, **pair every `set_viewport` with a `clear_viewport`.**

## Your gate

```sh
cd <your workspace> && uv run pytest tests/ -q -n0
cd web && npm run build && npm run lint && npm test
```

All four clean, **plus the measurement, at 1440x900 and 1280x800, before and after**:

- **Type range on these routes.** 2.00-2.67 today, against a **3.4:1** bar. The display step is
  already declared; this is a matter of rendering it.
- **Content width and row height at `--scale 10000`**, with the sidebar collapsed and expanded, in
  the same shape as B115's table so the two can be compared directly. **If 1280 is still 77px, say
  so.** It almost certainly will be, and B115 already explains why.
- **Whether the rung column is visible without a sideways scroll** at both widths. This is the one
  measurement that is a pass/fail rather than a number.
- **How many regions are placed beside another.**

A number you did not measure is not a number. If something does not reach its bar, say so and file
what closes it.

Conventional Commits, subject carrying `M7-W164`. Push your branch. **No pull request, nothing on
`main`.** When you finish, send `worker_done` - the last item finished without sending one and its
coordinator waited on a message that never came.
