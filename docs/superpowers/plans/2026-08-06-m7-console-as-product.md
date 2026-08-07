# M7 — the console becomes a product

**Status:** approved 2026-08-06, in execution on branch `console-identity`.

**Amended 2026-08-06 by `specs/2026-08-06-sync-console-supabase-substrate-design.md` (M7-W165):**
Phase 1's "no component is copied" is superseded — Supabase's components are vendored wholesale
under an owner-authorized carve-out. Phase 2's chassis is rebuilt two-tier. Phases 4–5 continue on
the vendored substrate; each remaining level port follows the spec's §10 mapping-table gate.

**Root cause this milestone answers:** `reports/2026-08-06-why-the-console-came-out-flat.md`.
**The owner's direction:** `references/direction/NOTES.md`, five examples with mappings.

## Context

The owner's verdict, after five sets of reference screenshots: the platform underneath is strong and
the interface is not close to standard. That judgement is correct and it is measurable rather than a
matter of taste.

Measured on the running tree at 1890px:

- **Type range 2.0–2.67:1** against the 3.4:1 bar the reference surfaces clear. A 32px display step
  is declared and **never renders on six of nine routes**. Nothing on screen has presence.
- **Frame ratio 3.0** against 4.7–7.2. `DESIGN.md` refuses a wider frame because *"the nav rail and
  header already hold the composition's edge"* — **there is no rail.** `site-nav.tsx` is a horizontal
  strip. The refusal rests on a component that does not exist.
- **Every page is one vertical stack.** `<section className="flex flex-col gap-8">` with N cards
  beneath it. Across the whole console there are **7 side-by-side placements, 5 of which are
  definition lists inside a card**. Nothing is ever placed beside anything else.
- **Paragraphs render at 491px** with ~1330px of nothing to their right, while the table beneath
  spends a 1290px column on a vendor name. The app is full-width; the composition is not.
- **22 cards, one anatomy, no exceptions.** Header, title, description, content — 22 times.

Against that, the references share a chassis we have none of: a two-tier navigation, a two-line page
header, a control bar with exactly one primary action, a fact-tile grid, a right drawer for detail,
an empty state that says what would fill it, a footer bar owning pagination, and a label register
distinct from the value register.

**This is a rebuild of the presentation layer, not of the console.** The seam is clean and already
measured: ~2,900 lines of transport, derivation and honesty logic have no presentation in them and
stay untouched. ~7,900 lines of shell, primitives and page composition get replaced.

## What must survive, and the one thing that will otherwise be lost

The product's argument lives in the presentation layer, which is what makes this risky:

- **`components/states.tsx`** — five distinguishable kinds of nothing, and `explain()` mapping each
  error class to a headline and a remedy.
- **`components/status.tsx`** — the single place a `null` becomes ink; colour never without an icon
  and a word.
- **`components/provenance.tsx`** — the rung at two levels, deliberately not merged.
- **`lib/format.ts`, `cardinality.tsx`, `rung-series.ts`** — absence is not zero, a bounded count is
  a floor, a rung nothing carries is still a series.

**The twenty-four protected honesty sentences have no automated guard at all**, and their catalogue
in `2026-08-05-sync-console-architecture.md:102-207` cites four files that no longer exist. The rule
protecting them says plainly: *"Nothing tests prose."* A rebuild that rewrites 7,900 lines of
presentation with no guard on those sentences will delete the product's argument silently and
nobody will notice for weeks. **Phase 0 exists for exactly this and nothing else starts before it.**

---

## Phase 0 — Make the rebuild survivable (blocks everything)

1. **Re-catalogue the twenty-four sentences against the current tree.** Four cited files are gone;
   the sentences moved. Produce a machine-readable list: each sentence, its distinguishing
   substring, its current file.
2. **Add `tests/test_console_honesty_sentences.py`** — for each entry, assert the substring still
   appears somewhere under `web/src`. Not file-pinned, so a sentence may move; deletion fails the
   build. Proven RED by deleting one.
3. **Record the seam** — the ~2,900 lines that do not move — in the plan's own ledger, so a worker
   rewriting a page knows what it may not touch.

## Phase 1 — Read Supabase as source, not as screenshots

Supabase is open source (`github.com/supabase/supabase`), and the owner has asked us to use that.
`.claude/rules/interface-originality.md` permits exactly this and it is what was already done with
Sentry and Grafana: **mechanism and stated reasoning, never markup and never appearance.**

Clone and read, recording each as a mechanism note under `docs/superpowers/references/notes/`:

- The **shell**: how the icon rail and contextual sidebar compose, and how a page declares which
  sidebar it wants.
- The **layout primitives**: their page header, control bar, footer bar, and the props each takes.
- The **empty state** component and its API — the thing that turns "no rows" into "here is what
  would fill this and how".
- The **drawer/sheet** pattern and how focus and history are handled.
- The **settings card** — title, explanation, control, its own Save.

Deliverable: one note per mechanism, each ending in *what we would put in that slot*, and each
naming what we will do differently. **No component is copied.**

## Phase 2 — The chassis

Replace `layouts/` (369 lines) and add the primitives every page will use. This is the single
highest-leverage change in the plan: it is what makes a display-size title, a fact rail and a
drawer possible at all.

- **`layouts/app-frame.tsx`** — icon rail (fixed, product areas) + contextual sidebar (the level you
  are inside, with its name as a heading and small-caps group labels) + content region.
- **`layouts/page-header.tsx`** — display title plus one sentence saying what the page is for. Every
  route already carries that sentence: `RouteEntry.question` in `lib/routes.ts`.
- **`layouts/control-bar.tsx`** — scope selectors and search left, one primary action right.
- **`layouts/footer-bar.tsx`** — pagination, page size, record count. `page-controls.tsx` moves into
  it rather than being reimplemented.
- **`components/detail-drawer.tsx`** — right drawer over a dimmed page, built on the vendored
  `dialog.tsx`, addressable so a URL still opens it.
- **`components/fact-tile.tsx`** and **`components/fact-list.tsx`** — the label/value register.
- **`components/skeleton.tsx`** — a bar the width of the value it will become. `states.tsx` keeps
  every sentence it already owns; the skeleton is for a value in flight, not for an answer.
- **`components/metric-panel.tsx`** — the pattern under every observability screen in the
  references: title, **the current value at display size directly beneath it**, then the evidence,
  then a legend pairing a dot with a word. Value first, chart second — the number is the answer and
  the chart is why. Our charts today have no headline value at all, and `echart.tsx` already
  resolves every colour from the token block, so this is composition rather than new plumbing.

Constraint: `lib/routes.ts`'s shape is pinned by two Python tests and one vitest file. The registry
gains fields (icon, sidebar group); it does not change shape.

## Phase 3 — Reopen the two refusals, with measurements

- **Type.** Add a display tier so the range clears 3.4:1 and the display step is at least 3× body.
  `DESIGN.md`'s Type section is amended with the measurement, not silently overridden — the previous
  argument ("vertical space is rows") was sound for a page with no rail and is not once a rail
  holds the edge.
- **Space.** The frame grows to clear the 4.7–7.2 ratio, because the premise it was refused on
  becomes true in Phase 2.
- **The label register.** `.furniture` (uppercase, `0.025em`) already exists in `index.css` and is
  used almost nowhere. Small-caps letterspaced muted labels become the standard for every field
  label, which is most of what separates their screens from ours.

Every one of these changes lands with a before-and-after measurement from Chrome, and
`tests/test_console_design_tokens.py` is updated in the same commit — it reads its thresholds out of
`DESIGN.md`, so the contract and the guard move together.

### Four patterns from the observability and catalogue screens

The later examples add shapes that map onto levels we already have, and each is composition over
data we already store rather than new plumbing:

- **A metric panel carries its own evidence.** Their Data API panel is title → value → sparkline →
  **the rows behind the number**, each expandable in place (`HEAD 521 /rest-admin/v1/ready · 9`,
  opening to "No query parameters in this request"). The number and its evidence never separate.
  Ours: every count on the fleet and detector screens currently has its evidence on another screen.
- **An empty chart is a dashed region that says why and when.** *"No data to show — it may take up
  to 24 hours for data to refresh."* Our five kinds of nothing are sentences in panels; a chart with
  no series currently renders nothing at all. This extends `states.tsx` rather than replacing it.
- **A faceted explorer.** Their Logs screen is a facet sidebar with counts per value —
  `Edge Function 0` rendered, not suppressed — a volume histogram aligned over the result set, and a
  dense monospace table beneath. This is what **Errors & Incidents** and **Signals** should be, and
  `components/filters.tsx` already renders a zero-count facet and already sends narrowing to the API
  rather than to rows on screen.
- **A catalogue with provenance chips.** Their Integrations grid — icon, name, description,
  `OFFICIAL` / `COMMUNITY` / `BETA` / `INSTALLED`, "Built by X" — is a better rendering of the
  **Signals** level than three stacked panels: one card per integration, grouped by the three M5
  roles, with the roles that have nothing attached saying so in the same grid.

## Phase 4 — Recompose the nine levels, one per work item

Each level moves onto the chassis on its own, gated and measured, so the console is never broken:
Fleet, Codebase, API Services, Signals, Binding surface, Errors & Incidents, Finding, Solution
Workflow, Pull Request.

Per level: a fact rail replacing the prose intro, a fact-tile grid replacing the definition lists, a
control bar replacing ad-hoc filter placement, a footer bar replacing in-card pagination, and the
protected sentences re-placed rather than dropped (Phase 0's guard enforces it).

## Phase 5 — The two moments that make it feel engineered

- **The workflow as a narrative.** Superlog's reading order — signals arrive, state changes, the
  agent narrates, then a named structured block carries the conclusion with its evidence, then a
  resolution block closes each item with a reason. **We hold every slot they render and two they do
  not**: the provenance rung on each signal, and the attempts that were abandoned with the reason.
  We render it as a plain list. This is the single screen where our data is richer than the
  reference's, and it is the screen the product's argument lives on.
- **One binding, drawn.** A node card — call site, operation, vendor change, the rungs between them
  — for a *single* binding. Task 11's refusal of a fleet-wide bipartite diagram stands on
  cardinality and is not reopened by this.

**Refused, whatever a reference shows:** a confidence score. Superlog renders `Root cause confidence:
9`. That is the composite score this project has refused four times, and the rung is the honest
version of that field — it says which class of evidence a claim rests on and is attributable, where
a 9 is neither.

## Phase 6 — The write path, deliberately last

The reply composer and the settings cards both imply mutation. Every route is a GET held by a
behavioural test, and there is no user model. This belongs to M4's hosted half — auth, tenancy,
audit — and is planned there, not smuggled in as a text box.

---

## Research strand, running alongside

The owner asked for the psychology of the interface, and the honest gap is nameable: the fourteen
invariants this console has been built to are about **restraint** — two ink levels, two weights, no
motion, nothing decorative at rest. Clearing them makes a page *not bad*. **None of them produce
presence**, and presence is what the references have. Restraint without hierarchy reads as bland,
which is exactly the complaint.

One note, `references/notes/interface-presence.md`: focal hierarchy and where the eye lands first;
scale contrast as the primary signal; spatial rhythm and uneven breathing; the craft details
(optical alignment, edge treatment, how a surface meets a surface). Each claim measurable against
the four surfaces already measured.

## Verification

- **Phase 0's guard is the gate.** Every subsequent commit runs it.
- Per level: Chrome at 1440×900 and 1280×800 through `getComputedStyle`, before and after — type
  range, frame ratio, ink levels, row heights, rows above the fold at `--scale 10000`.
- The existing suites must stay green: `uv run pytest tests/ -q -n0`, and from `web/`
  `npm run build`, `npm run lint`, `npm test`. The 8 vitest files assert behaviour rather than class
  names, so a visual rebuild breaks none of them by construction — if one goes red, behaviour was
  lost, not styling.
- `tests/test_console_hierarchy.py` and `test_console_signals_roles.py` continue to pin the route
  registry and the signal roles to the specification.
