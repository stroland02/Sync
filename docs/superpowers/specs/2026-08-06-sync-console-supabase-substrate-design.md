# The console adopts Supabase's component substrate

**Status:** approved by the owner 2026-08-06, spec M7-W165. Amends `2026-08-06-m7-console-as-product.md`
(the M7 plan) rather than replacing it; where the two disagree, this document wins because it is
later and carries the owner's rulings of 2026-08-06.

## 1. Stance — a foundation, not a final identity

The owner's direction, verbatim in intent: Supabase has a fundamentally strong platform layout for
modular systems, and the console adopts it as a foundation. Sync's own visual identity — its own
dashboards, styles and techniques — layers on top of that foundation later, incrementally.

Two consequences bind every task under this spec:

- **The vendored layer stays clean.** A vendored component receives only the edits that make it run
  in our stack (section 2). Restyling happens above it — in composition, in theme variables, in
  wrapper components — never by forking the vendored file. A fork today is a merge conflict with our
  own future identity work.
- **M7 remains the governing milestone.** Same integration branch (`console-identity`), same WORKLOG
  series, same gates. This spec adds phases to M7's plan; it does not open a parallel effort.

Three owner rulings on 2026-08-06 reversed earlier records, and each is now the standing decision:

1. **Vendor wholesale.** Supabase's component code is adopted nearly verbatim, not merely read for
   mechanism. This supersedes the M7 plan's Phase 1 constraint "no component is copied."
2. **Two-tier navigation.** A 40px icon rail plus a contextual sidebar per area — Supabase's
   arrangement. This reverses direction note 6, which chose one sidebar at two widths; the note
   carries an amendment naming the reversal rather than being rewritten.
3. **Phase 4 work already in flight landed first.** M7-W163 and M7-W164 merged before this spec's
   work begins, so the ports start from a stable tree.

## 2. The vendor manifest

One fresh sparse clone of `github.com/supabase/supabase`, pinned at a single commit recorded in
`web/NOTICE`. The clone lives outside the repository and is deleted after extraction, as M7-W159's
clone was.

**Taken nearly verbatim, into `web/src/vendor/supabase/`:**

- `packages/ui` — the component library: button, table, dropdown, sheet, dialog, tabs, badge,
  command menu, the shadcn sidebar primitive, and the rest of the primitives the Studio screens
  compose.
- The theme: their CSS custom properties, color scale, type ramp, spacing and radii, ported into
  `web/src/index.css` under Tailwind 4's `@theme` (their repository configures Tailwind 3; the
  values move, the configuration mechanism is ours).
- `packages/ui-patterns` entries with no Next.js coupling — the empty-state pattern and the layout
  patterns among them.

**Transcribed, never imported:** `apps/studio` code. It is Next.js-coupled (router, data layer,
i18n, feature flags) and cannot run under Vite. Its layout nesting, table arrangements and dashboard
composition are re-written faithfully against our stack, citing the source file the way M7-W159's
note does.

**The only edits a vendored file may receive:** import paths; Next `Link` and router calls swapped
for React Router; i18n and feature-flag calls stripped; TypeScript config accommodations. Each
vendored file keeps its Apache-2.0 header. `web/NOTICE` records the license, the pinned SHA, and the
per-file provenance list.

**Explicitly not taken, whatever the clone contains:** the Supabase wordmark, logo, iconography that
identifies Supabase, marketing copy, and product copy. Identity is not learnable from anyone;
components are, and as of this spec, copyable from this source.

## 3. The theme contract

`DESIGN.md` is rewritten as the Supabase-substrate contract: their color scale, type ramp (including
its display steps — the 2.0:1 type-range defect dies with the old ramp), spacing and radii become
the declared tokens. The rewrite lands in the same commit as the rewrite of
`tests/test_console_design_tokens.py`, so the contract and its guard never disagree.

- **Dark-only stands.** The owner set it 2026-08-05 and has not reversed it. Supabase ships both
  themes; we adopt the dark values and leave the light ones un-imported until the owner asks.
- **Contrast is measured, not assumed.** Every text-bearing token pairing in the adopted palette is
  measured against the 5.05:1 floor after the swap. A pairing below the floor is recorded in
  `DESIGN.md` as a named deviation with its measured ratio — visible, reversible, never silent.
- The token test keeps its direction: it fails when a screen adds a value outside the contract. The
  contract's values change; the discipline does not.

## 4. The chassis, rebuilt two-tier

`layouts/app-frame.tsx` is rebuilt on the vendored sidebar primitive: a 40px icon rail for the
product's areas, plus a contextual sidebar carrying the active area's name as a heading and its
destinations under small-caps letterspaced group labels. The mechanism follows Studio's
(`DefaultLayout` → product layout → `ProjectLayout`, per M7-W159 §1) transcribed onto our route
registry: `lib/routes.ts` gains `area` and `pages` fields; nesting does not replace the registry,
because two Python tests and one vitest file pin the registry's shape and the registry is the right
shape for a nine-level hierarchy.

**Areas are groupings over the specified levels, not new levels.** `GRAPH_LEVELS` does not change;
`tests/test_console_hierarchy.py` continues to hold the vocabulary against the specification's
authoritative block. The rail proposed for review:

| Rail area | Levels and screens inside |
|---|---|
| Fleet (home) | Fleet |
| Codebase | Codebase |
| API Services | API Services |
| Signals | Signals |
| Observe | Binding surface, Errors & Incidents |
| Remediation | Finding, Solution Workflow, Pull Request |
| Settings | pinned last; empty until the write path exists |

Active state follows Studio's `pages`-array mechanism: a menu item that owns several routes says so
in data. The exact grouping above is the owner's to adjust at review; the constraint that areas
group levels without inventing them is not.

## 5. The screen ports

One work item per level, as M7 Phase 4 already runs. Each port recomposes the level onto the
vendored components:

- **Tables:** Studio's anatomy — uppercase letterspaced column headers, the value's type beside the
  column name where one exists, an overflow menu at the row's end, the identifying column as a link,
  and a footer bar owning pagination, page size and the record count.
- **Overview screens:** a fact-tile grid (icon, small-caps label, value) and metric panels with the
  current value at display size above its evidence.
- **Detail:** a right drawer over a dimmed page, addressable by URL, built on the vendored sheet.
- **Empty states:** the vendored pattern — what would fill this space and the way out — wrapping the
  sentences `states.tsx` already owns.
- **Deferred:** the settings-card pattern. It implies a write path; every route is a GET held by
  `test_no_route_reaches_past_the_read_surface`, and mutation belongs to M4's hosted half.

## 6. What does not move

These are claims about data, not looks, and no component swap touches them:

- The twenty-four protected honesty sentences. `tests/test_console_honesty_sentences.py` is the
  merge gate; a port re-places every sentence or fails.
- No composite score, health figure, traffic light, green dot, liveness pulse or count-up. A
  vendored component with a slot for one renders our honest equivalent instead: the rung, a
  closed-vocabulary badge, or the absence sentence.
- Absence is not zero, staleness is not liveness, never-measured is not nothing-here.
- The provenance rung at two levels, monochrome, never a hideable column.
- The API stays read-only.

## 7. The records this spec amends

- `.claude/rules/interface-originality.md` gains an owner-authorized carve-out: Supabase,
  Apache-2.0, code-level adoption permitted per this spec; identity elements remain excluded; the
  rule is unchanged for every other reference.
- `references/direction/NOTES.md` entry 6 gains the reversal amendment (owner, 2026-08-06:
  two-tier navigation is the target).
- `DESIGN.md` per section 3. The M7 plan gains a pointer to this spec at Phases 1–3.

## 8. Execution machinery — unchanged

The workflows that built the console keep running exactly as they run today: a brief per work item;
the next WORKLOG number in every commit subject; workers on branches off `console-identity`; the
coordinator merges, gates, pushes; `main` catches up by fast-forward at least daily. The local gate
remains the authority while B112 keeps CI runners unreliable: `uv run pytest tests/ -q -n0`, then
`npm run build`, `npm run lint`, `npm test` from `web/`. The owner's console serves 5173 from the
coordinator's worktree and restarts after every merge.

Order of work: vendor drop and `NOTICE` (one item) → theme contract swap (one item, `DESIGN.md` and
token test together) → chassis rebuild (one item) → level ports, one item per level, Fleet first.

## 9. Verification

- The honesty-sentence gate green on every merge.
- Vitest stays behavioral — classification, derivation, structural invariants; never class names,
  never snapshots. Every new guard proven RED before it is trusted.
- Per-level Chrome measurement at 1440×900 and 1280×800 through `getComputedStyle`, before and
  after: type range, frame ratio, ink levels, rows above the fold at `--scale 10000`.
- Every `set_viewport` paired with `clear_viewport` (`.claude/rules/console-dev-loop.md`).

## 10. The data seam and the slot mapping

The reason this rebuild is safe to attempt at all: the console's data layer and its presentation
are already separated at a measured seam, and this spec widens nothing across it.

**The seam holds.** The ~2,900 lines of transport, derivation and honesty logic recorded in the M7
plan's ledger — `api/client.ts`, `api/queries.ts`, `api/types.ts`, `lib/format.ts`,
`components/states.tsx`, `components/status.tsx`, `components/provenance.tsx`, the rung and
cardinality derivations — do not move. Every vendored component is fed from these existing view
models. A port that finds itself editing the seam has left its brief.

**A mapping table precedes every port.** Before a level's port begins, its brief carries a table:
every field the current screen renders on the left, the Supabase slot that will carry it on the
right. `references/direction/NOTES.md` already holds these tables for the incident detail, the
activity trail and the project overview; the pattern generalizes. A field with no slot is resolved
in the brief — a new slot, or a recorded ruling that the field moves or retires — never dropped in
passing.

**The completeness check is part of the port's gate.** A port's verification includes walking the
old screen and the new screen against the same seeded database (`scripts/seed_console.py`) and
stating that every fact the old screen asserted is asserted by the new one, with any exception
recorded as a ruling in the plan's ledger. The honesty-sentence test automates the twenty-four
sentences; the walk covers the fields the test does not pin.

**Where our data exceeds the reference, the excess leads.** The slot mappings in
`direction/NOTES.md` found that we hold more than the references render — the rung on every signal,
the abandoned attempts with reasons, the checkpointed node sequence. A port renders the richer
version in the vendored frame; it never trims our data to the reference's silhouette.
