# Brief - M7-W163, the Fleet level onto the chassis

You are working in your own Orca workspace. **Start by rebasing:**
`git fetch origin && git checkout -B m7-fleet origin/console-identity`. The base is
`console-identity`, not `main` and not `m4-dashboard`.

M7's Phase 4 recomposes the nine specification levels onto the chassis that landed as M7-W160. This
is the first of them, and it is deliberately first: Fleet is the screen an operator lands on, and it
is the screen the owner looks at when judging whether the console is any good.

## Read these first, and the first two are not optional

1. **`docs/superpowers/reports/2026-08-06-why-the-console-came-out-flat.md`.** Six causes, all of
   them written rules rather than mistakes. Without it you will rebuild a flat screen out of better
   parts.
2. **`.claude/rules/interface-originality.md`**, as amended on 2026-08-06. It separates the
   conventions of the form - a page header, a control bar, a fact tile, a footer bar - which are
   learnable from anything, from identity, which is not.
3. `CLAUDE.md`; `.claude/rules/console-surface.md`; `.claude/rules/console-hierarchy.md`;
   `.claude/rules/console-dev-loop.md`.
4. `docs/superpowers/references/direction/NOTES.md` - the owner's six worked examples.
5. `DESIGN.md`, and `web/src/layouts/app-frame.tsx`'s docstring, which carries the three rulings the
   chassis made.

## What exists now that did not before

M7-W160 landed the chassis and **nothing under `features/` moved into it**. That was the point: the
frame became reviewable apart from the pages. Your item is the other half for one level.

The primitives waiting for a caller:

- **`layouts/page-header.tsx`** - a display-size title and one sentence saying what the page is for.
  **That sentence already exists**: `RouteEntry.question` in `lib/routes.ts`, one per route, written
  for exactly this and rendered on no feature screen today.
- **`layouts/control-bar.tsx`** - scope selectors and search on the left, at most one primary action
  on the right.
- **`layouts/footer-bar.tsx`** - pagination, page size, record count. It wraps
  `components/page-controls.tsx`; do not reimplement offset paging, and keep reading `next_offset`
  rather than doing arithmetic on a total that may be bounded.
- **`components/fact-tile.tsx`** and **`components/fact-list.tsx`** - the label register above the
  value register, using `.furniture` from `index.css`.
- **`components/skeleton.tsx`** - a bar the width of the value it will become. **It does not replace
  anything in `states.tsx`.** Those five sentences answer *a query*; a skeleton is for a value in
  flight and says nothing.

## What you are building

Recompose `web/src/features/fleet/` onto those primitives. The screen today is
`<section className="flex flex-col gap-8">` with six cards stacked beneath a `text-page` `h1` and a
paragraph rendering at about 491px with roughly 1330px of nothing to its right. Every panel has the
same anatomy and nothing is ever placed beside anything else.

What it should become:

- **A page header** carrying the display step. `fleet-page.tsx` currently opens with
  `<h1 className="text-page">Fleet</h1>` and a paragraph; that becomes `PageHeader` with the route's
  own `question`. **This is the item that first proves the display step on a feature route** - the
  chassis declared a 48px display tier and only `unknown-route.tsx` renders it, which is why the
  measured type range is still 2.00-2.67 on all nine feature screens.
- **A fact rail** replacing the prose intro's role as the first thing on the page. The counts an
  operator acts on - open findings, runs, repositories, detectors - become fact tiles with the label
  register above the value, placed beside one another rather than stacked.
- **Panels placed beside panels** where the data is low-cardinality enough to allow it. The existing
  `lg:grid-cols-2` pairing of repositories and detectors is the only side-by-side placement on the
  screen; it should not be the only one.
- **A footer bar** on any panel that pages, replacing in-card pagination.

**Do not change what the screen says.** The panel order in `fleet-page.tsx`'s docstring is the
operator's ranking and it was argued for; if you change it, say why in the commit body. The routes,
the payloads and the view models do not change at all - this is presentation.

## What must not break, and the first one has no second chance

- **`tests/test_console_honesty_sentences.py`** guards seventeen fragments of the protected
  sentences and is deliberately not file-pinned, so moving a sentence into a new composition is fine
  and deleting or shortening one fails the build. **`fleet-page.tsx` carries one of them** - the "no
  composite health figure" paragraph, which holds `we could not check`. It must still be on screen
  when you are done. It may move; it may be restyled; it may not become a tooltip, a disclosure, or
  a shorter sentence. Run this test after every change.
- **No composite score, health figure, traffic light, green dot, liveness pulse or count-up.** The
  fleet screen is where the temptation is strongest because it is a summary screen. The refusal is
  in `CLAUDE.md` and it is not reopened by a reference showing one.
- **`tests/test_console_design_tokens.py`**, now 1,133 lines plus the chassis's additions: no colour
  literal outside `index.css`, no raw spacing value duplicating a token inside `features/`, nothing
  below the 12px floor, no fourth font weight, no alpha on a focus ring, no `text-ink-secondary` on
  DOM text, no keyframes outside the component catalogue, no transition on geometry, and a raw-source
  scan that sees keyframe names even inside comments.
- **`lib/motion.ts`** carries a registry a Python guard binds to the tree in both directions, so an
  unlisted importer fails the build. There is no motion on this screen.
- `components/states.tsx`, `status.tsx`, `provenance.tsx`, `lib/format.ts`, `cardinality.tsx` -
  product logic. Their call sites may move; their sentences and their `string | null` discipline may
  not. `cardinality.tsx` is the bounded-count discipline: a bounded figure is a floor and is never
  rendered as if it were exact.
- **`web/src/lib/routes.test.tsx`** is the reachability guard. Every route needing no subject must
  remain linked from a destination.

## One piece of debt you will meet, and it is yours to resolve

**There are two components named `ControlBar`.** `components/filters.tsx` has exported one for some
time and `features/bindings/binding-surface-page.tsx` and `features/vendors/vendor-findings-table.tsx`
import it. The chassis added `layouts/control-bar.tsx`. Neither of those two files is yours, so **do
not rename theirs** - a second worker is on the bindings level in parallel and would conflict with
you. What is yours: **use the layout one on the fleet screen, import it under a name that cannot be
confused with the other at a glance, and file a backlog entry naming the collision and which of the
two should survive.** Take the next free `B` number from `docs/superpowers/BACKLOG.md`; `B118` is
taken.

`CLAUDE.md`'s debt section is the reason this is in the brief rather than left for later: two things
with one name is a fact written twice, and it will disagree with itself.

## How to work

```sh
SYNC_GRAPH_DSN=postgresql://sync:sync@localhost:5433/sync SYNC_API_PORT=<free> uv run python -m sync.api
uv run python scripts/seed_console.py --scale 10000
cd web && SYNC_API_ORIGIN=http://127.0.0.1:<free> npm run dev -- --port <free>
```

**5173 is the owner's console and 8789 is the API behind it - leave both alone.** Never edit
`vite.config.ts` to reach a port; `SYNC_API_ORIGIN` is what M4-W151 built for that. Stop every server
you start before you report, **and kill its shell wrapper too** - B118 records an afternoon lost to a
listening socket held by a dead PID because only the child was killed.

If you use Chrome to measure, **pair every `set_viewport` with a `clear_viewport`**. It is a device
metrics override on a shared persistent browser; it survives your task and the owner sees a windowed
console for a day.

## Your gate

```sh
cd <your workspace> && uv run pytest tests/ -q -n0
cd web && npm run build && npm run lint && npm test
```

All four clean, **plus the measurement that is the point of this item**, at 1440x900 and 1280x800,
before and after:

- **Type range on this route.** It is 2.00-2.67 today. The bar is **3.4:1**, and the display step is
  declared already, so this is a matter of rendering it. Say what it measures after.
- **How many regions are placed beside another** on this screen. It is one today.
- Row heights and rows above the fold at `--scale 10000`, if you touch a table.

A number you did not measure is not a number. If something does not reach its bar, say so plainly and
file what closes it - the chassis item did exactly that with B116 and that was the right call.

Conventional Commits, subject carrying `M7-W163`. Push your branch. **No pull request, nothing on
`main`.** When you finish, send `worker_done` - the last item finished without sending one and its
coordinator waited on a message that never came.
