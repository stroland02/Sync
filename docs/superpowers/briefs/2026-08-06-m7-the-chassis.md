# Brief — M7-W160, the chassis

You are working in your own Orca workspace. **Start by rebasing:**
`git fetch origin && git checkout -B m7-chassis origin/console-identity`. The base is
`console-identity`, not `m4-dashboard`.

This is the highest-leverage item in M7. Everything else — a display-size title, a fact rail, a
drawer — is impossible until it exists.

## Read these first, and the first two are not optional

1. **`docs/superpowers/reports/2026-08-06-why-the-console-came-out-flat.md`.** Six causes, all of
   them written rules rather than mistakes. If you do not read this you will rebuild the same flat
   console with better components.
2. **`.claude/rules/interface-originality.md`, amended 2026-08-06.** It now separates the
   conventions of the form — a rail, a breadcrumb, a page header, a drawer, a fact tile — which are
   learnable, from identity, which is not.
3. `CLAUDE.md`; `.claude/rules/console-surface.md`; `.claude/rules/console-hierarchy.md`.
4. `docs/superpowers/references/direction/NOTES.md` — the owner's five examples, each already
   mapped onto data we hold.
5. `DESIGN.md`.

## What you are building

Replace `web/src/layouts/` (369 lines) and add the primitives every page will use. **Nothing in
`features/` changes in this work item** — the pages keep rendering exactly what they render today,
inside a new frame. That constraint is what makes this reviewable.

- **`layouts/app-frame.tsx`** — **one sidebar with two widths, not two components.** Corrected
  2026-08-06 by the owner, and the correction matters because the wrong reading is the more common
  pattern and this brief originally specified it.

  **Wrong:** a fixed 40px icon rail *plus* a separate contextual panel that slides out beside it, so
  expanding produces two columns of chrome. That is Supabase's arrangement and it is not what we
  want.

  **Right:** a single sidebar carrying the same destinations at all times, in the same vertical
  order. Expanded (~215px) each row is an icon **and** its label, with small-caps letterspaced group
  headings above each cluster. Collapsed (~48px) the labels and the group headings go, the icons
  stay **in the identical vertical positions**, and nothing else about the list changes. One toggle
  at the top switches between them. The content region reflows into the reclaimed width.

  The test that you have built the right thing: **an icon must not move vertically when the sidebar
  collapses.** If it does, you have two components rather than one at two widths. A collapsed row
  keeps its label as an accessible name and as a tooltip — the text disappears visually, never
  semantically.
- **`layouts/page-header.tsx`** — a display-size title and one sentence saying what the page is for.
  **That sentence already exists**: `RouteEntry.question` in `lib/routes.ts`, one per route, written
  for exactly this.
- **`layouts/control-bar.tsx`** — scope selectors and search on the left, at most one primary action
  on the right. Never two.
- **`layouts/footer-bar.tsx`** — pagination, page size, record count. `components/page-controls.tsx`
  moves into it; do not reimplement offset paging, and keep reading `next_offset` rather than doing
  arithmetic on a total that may be bounded.
- **`components/fact-tile.tsx`** and **`components/fact-list.tsx`** — the label register above the
  value register. `.furniture` already exists in `index.css` (uppercase, `0.025em`) and is used
  almost nowhere; this is its purpose.
- **`components/skeleton.tsx`** — a bar the width of the value it will become. **This does not
  replace anything in `states.tsx`.** Those five sentences answer *a query*; a skeleton is for a
  value in flight and says nothing.

## What must not break, and one of them has no second chance

- **`tests/test_console_honesty_sentences.py` landed today** and guards seventeen fragments of the
  protected sentences. It is not file-pinned, so moving a sentence into your new frame is fine and
  deleting one fails the build. Run it after every change.
- **`lib/routes.ts` is pinned by two Python tests and one vitest file.** The registry may gain
  fields — an icon, a sidebar group — and may not change shape. `GRAPH_LEVELS` and every route's
  `level` stay exactly as they are; `test_console_hierarchy.py` asserts them against the
  specification.
- **`web/src/lib/routes.test.tsx` is the reachability guard.** Every route needing no subject must
  remain linked from a destination. Seven of eleven routes were once unreachable and this is what
  caught it.
- `components/states.tsx`, `status.tsx`, `provenance.tsx`, `lib/format.ts` — product logic. Their
  call sites may move; their sentences and their `string | null` discipline may not.
- `tests/test_console_design_tokens.py`, 1,133 lines: no colour literal outside `index.css`, no raw
  spacing value duplicating a token inside `features/`, nothing below the 12px floor, no fourth font
  weight, no alpha on a focus ring, no `text-ink-secondary` on DOM text, no keyframes outside the
  component catalogue, no transition on geometry, and a `DialogTitle` must sit inside its
  `DialogContent`.

## The type and space change belongs here, not later

The two `DESIGN.md` refusals are reopened by the owner's judgement and the frame one rests on a
false premise: it refuses a wider frame because *"the nav rail and header already hold the
composition's edge"* — **there is no rail**, `site-nav.tsx` is a horizontal strip. Your work makes
that premise true, so make the change in the same item:

- **Add a display step** so the type range clears **3.4:1** and the display step is at least **3×
  body**. The console currently measures 2.0–2.67:1 and a 32px `--text-figure` never renders on six
  of nine routes.
- **Grow the frame** to clear a **4.7–7.2×** ratio against the in-component unit. It is 3.0 today.
- **Amend `DESIGN.md` in the same commit**, with the measurement and the reason the earlier argument
  expired. `test_console_design_tokens.py` reads its thresholds out of `DESIGN.md`, so the contract
  and the guard move together — do not edit one without the other.

## What does not change, whatever it looks like

No composite score, health figure, traffic light, green dot, liveness pulse or count-up. No motion:
`lib/motion.ts` carries a registry a Python guard binds to the tree in both directions, so an
unlisted importer fails the build. Two ink levels plus one accent on text. The 5.05:1 contrast floor
against rendered pixels, and the 11px size floor.

## How to work

```sh
SYNC_GRAPH_DSN=postgresql://sync:sync@localhost:5433/sync SYNC_API_PORT=<free> uv run python -m sync.api
uv run python scripts/seed_console.py --scale 10000
cd web && SYNC_API_ORIGIN=http://127.0.0.1:<free> npm run dev -- --port <free>
```

**5173 is the owner's console — leave it alone.** Never edit `vite.config.ts` to reach a port.

## Your gate

```sh
cd <your workspace> && uv run pytest tests/ -q -n0
cd web && npm run build && npm run lint && npm test
```

All four clean, **plus the measurement that is the point of this item**: at 1440×900 and 1280×800,
before and after — type range, frame ratio, and how many regions are placed beside another. Today
those are 2.0:1, 3.0, and seven in the entire application.

Conventional Commits, subject carrying `M7-W160`. Push your branch. **No pull request, nothing on
`main`.**
