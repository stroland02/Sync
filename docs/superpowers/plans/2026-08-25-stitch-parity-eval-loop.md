# The Stitch parity eval loop

**Owner ruling, 2026-08-25: the Stitch screens are the primary visual authority for how the
console should look.** The loop below exists to close the distance between the running console
and those references, continuously, until an operator putting the two side by side cannot say
which one was the drawing.

The loop is: **capture → compare → rank → fix → gate → repeat.** Every iteration produces either
a landed commit or a recorded finding that needs a ruling. Nothing is adjusted by taste; every
change traces to a named difference against a named reference.

## Authority order, unchanged

The Stitch references decide *how things look*. They do not overrule:

1. `web/CLAUDE.md` — what a screen may claim. No composite score, health figure, traffic light or
   liveness pulse. A badge from a closed vocabulary is the permitted form, and it is visually
   identical to the mock's chips.
2. **Real data only.** A mock figure we do not measure is replaced by one we do, never carried.
3. `DESIGN.md` — every visual value lands there with its contrast arithmetic (5.05:1) before it
   is used. The Stitch token sheet is already absorbed (`CI-W614`); a new value found in a
   reference goes through the same door.
4. `.claude/rules/console-hierarchy.md` — nine levels, spec-pinned. The four Stitch screens with
   no level (API Keys, Team Management, Database Explorer, API Docs) stay set aside per the
   owner's ruling of 2026-08-24.

Where a reference conflicts with these, the difference is recorded as `BLOCKED(rule)` in the
iteration log rather than silently skipped — the owner may rule to change the rule.

## The screen map

Primary reference first; secondary in parentheses where two Stitch screens cover one route.

| Console route | Stitch reference |
|---|---|
| `/repositories/:id` (Overview) | `developer_control_center` (`futuristic_developer_control_center`) |
| `/repositories/:id/call-sites` | `repository_index_explorer` |
| `/repositories/:id/vendors` | `code_graph_service_map_supabase_style` (`code_graph_service_map`) |
| `/repositories/:id/services` | `integration_performance_explorer` |
| `/repositories/:id/observed` (Telemetry) | `live_telemetry_agent_hub` (`animated_live_telemetry_hub`, `advanced_telemetry_trace_explorer`) |
| `/repositories/:id/findings` | `self_healing_queue` |
| `/repositories/:id/findings/:f` | `self_healing_incident_inspector` |
| `/repositories/:id/findings/:f/workflow` | `ai_driven_incident_resolution_workflow` |
| `/repositories/:id/solutions` | `remediation_ci_cd_policy` |
| `/repositories/:id/runs` | `infrastructure_logs` (`live_trace_log_stream`) |
| `/repositories/:id/graph` | `code_graph_dependency_explorer` (`3d_dependency_graph_explorer`) |
| `/repositories/:id/metrics` (Trends) | `integration_performance_explorer` |
| `/settings` | `platform_settings` |

Non-screen resources: `high_density_technical_console/DESIGN.md` and `sync_console/DESIGN.md`
(the token sheets, absorbed), `shader/` and `three.js/` (working sample code for the motion
tier), `Stitch UI.txt` (the raw export).

## The comparison rubric — the prompt each evaluator runs

> You are comparing a screenshot of the running Sync console against a Stitch design reference
> for the same screen. The reference is the target. Enumerate every visible difference, one
> finding per difference, classified on these axes in this order:
>
> 1. **Structure** — panes, columns, split views, sidebars, toolbars the reference has and ours
>    lacks (or the reverse). The biggest class of visible distance.
> 2. **Density** — row heights, padding, how many facts fit before the fold, table vs card.
> 3. **Hierarchy** — what leads the page, title/section scale, what is above the fold.
> 4. **Componentry** — KPI tiles, badges, filter fields, tabs, code panes, timelines the
>    reference draws and we render differently or not at all.
> 5. **Colour and token fidelity** — a colour, border or fill that differs from the token sheet.
> 6. **Typography** — face, size, weight, mono-vs-sans assignment.
> 7. **Motion and living-UI** — pulses, flows, entrances the reference implies (static PNG:
>    infer only from visible affordances like glows or trails; mark these `inferred`).
>
> For each finding give: the axis, one sentence naming the difference, where it is on each image
> (region words, not pixels), an impact score 1–5 (5 = an operator notices at a glance), an
> effort guess S/M/L, and — only when confident — the likely file in `web/src` responsible.
> **Never propose carrying a metric we do not measure** (uptime, MTTR, healed counts): where the
> reference's content is fictional, map it to the nearest real fact or mark it
> `DATA-SUBSTITUTION`. Do not report the absence of the four set-aside screens' features.
> Report nothing that is identical. Exhaustiveness beats brevity.

## The builder prompt — the standard every fix is held to

Supplied by the owner, 2026-08-25, placeholders resolved against this repository. The evaluator
rubric above finds the differences; every fix that closes one is executed under this contract.

> You are a Senior Frontend Architect rebuilding the production frontend to pixel-perfect
> fidelity with the Stitch references, under production-grade engineering practice.
>
> **Inputs.** Visual references: `docs/stitch_sync_developer_console/.../<screen>/screen.png`,
> with the prototype markup beside each as `code.html` — read the prototype for exact values,
> never port its markup wholesale (it is CDN-Tailwind demo code; ours is a token system).
> Stack: React 19 + Vite + TypeScript strict, Tailwind v4 with CSS-first tokens in
> `web/src/index.css`, vendored Supabase/shadcn primitives over Radix in `web/src/vendor/` and
> `web/src/components/ui/` (not ours to re-author). Server state: TanStack Query; view state:
> URL params. Dark-only.
>
> **Decomposition.** Tokens → primitives (vendored) → our components (`web/src/components/`) →
> layouts (`web/src/layouts/`) → feature screens (`web/src/features/`). New visual values enter
> as tokens with contrast arithmetic in `DESIGN.md`; no magic numbers, no inline hex.
> One responsibility per component; typed props; no `any`.
>
> **Quality.** Semantic HTML5 landmarks; WCAG 2.1 AA — colour never the sole channel, focus
> visible, accessible names carrying the real figures. Micro-states on every interactive
> element: hover, active, focus-visible, disabled, loading. Skeleton, empty and error states on
> every data surface — and the empty state must say *which* nothing it is (absence ≠ zero ≠
> never-measured). Desktop-first (operator console); wide content scrolls in its own container.
>
> **Two deviations from the generic playbook, deliberate.** No mock data schemas — every
> surface binds real graph data, and a reference figure we do not measure maps to one we do.
> And no new shell wrappers — screens compose through `ScreenFrame`'s four bands.

## The loop protocol

One iteration:

1. **Capture** every mapped route at 1600×900 with Playwright against real data on 5173, into
   `.playwright-mcp/eval/<route-slug>.png` (gitignored).
2. **Compare** — one evaluator per pair runs the rubric; findings return structured.
3. **Rank** — merge all screens' findings; systemic differences (same finding on 3+ screens)
   outrank per-screen ones at equal impact; sort by impact desc, effort asc.
4. **Fix** the top slice inline on `main` (owner ruling 2026-08-24: build on main, 5173 live).
5. **Gate** — `tsc`, vitest, lint, build, `uv run pytest tests/ -q`. All of them, every
   iteration: `CI-W621` records what skipping the Python gate cost.
6. **Commit** with the next `CI-W` number; log the iteration below.
7. **Re-capture the fixed screens** — a fix is not done until the delta is visibly smaller.

Stopping: an iteration whose top remaining finding scores impact ≤ 2 ends the density/structure
phase and hands over to the **motion tier** (three.js graph, shader backgrounds, log-stream
entrances — the `shader/` and `three.js/` samples are the starting code, applied only where the
reference shows them and never as decoration on data-bearing surfaces).

## Iteration log

| # | Date | Screens | Findings | Fixed | Landed |
|---|---|---|---|---|---|
| 1 | 2026-08-25 | all 13 | 351 raw, 12 systemic | #7 sidebar prose, #12 topbar identity | `CI-W624` |

### Iteration 1 — the twelve systemic findings, ranked

Fourteen agents, 351 raw findings, synthesized. Impact 5 = an operator notices at a glance.
Effort S/M/L. The two shell items were fixed the same day (`CI-W624`); the captures predate that
fix, so re-capture retires them formally next iteration.

| # | Impact | Effort | Difference | Screens |
|---|---|---|---|---|
| 1 | 5 | L | **Viewport-locked multi-pane composition** — the references keep every fact on screen (bento grids, splits, canvas+inspector) with per-pane scroll; we render one long scrolling column | 9 |
| 2 | 5 | L | **Persistent selection-driven inspector pane** — selecting a row or node should surface detail in place; ours shows nothing or navigates away | call-sites, vendors, runs, graph |
| 3 | 4 | S | **Tinted-fill icon+word status badges** — closed-vocabulary values render as plain text or gray outline chips; the tinted form is explicitly permitted and dropped everywhere | 8 |
| 4 | 4 | S | **Active nav item as a filled primary-container pill** with on-primary ink, not a faint tint with an edge bar | all |
| 5 | 4 | M | **No filled-primary element anywhere in the chrome** — logo, CTAs and accents all neutral; the references carry the emerald family through | 8 |
| 6 | 4 | M | **Prose before data** — caption paragraphs and checklists spend the fold; the references lead with data and one subtitle line | 10 |
| 7 | 3 | S | Sidebar stage descriptor sentences — **fixed, `CI-W624`** | 10 |
| 8 | 3 | M | **Persistent bordered search input at top-bar left** opening the palette, not a pill at the far right | 8 |
| 9 | 3 | M | **Banded pane headers** — tinted furniture strip (container fill, hairline, uppercase label with icon) on cards and panels | 7 |
| 10 | 2 | S | **Chrome on raised surfaces** — sidebar `#1b1c1b`, topbar `#1f201f` over the `#131413` page, not border-only separation | 10 |
| 11 | 2 | S | **Face split** — Manrope reserved for display/headers, body and meta in Inter 13px | 7 |
| 12 | 2 | S | Topbar repo identity as large mono — **partially fixed, `CI-W624`** (chip landed; mono size next capture) | 5 |

**Execution order:** 3 → 4 → 10 → 11 (small, high visibility) → 5 → 6 → 8 → 9 (medium) → 1 → 2
(the structural sequence, planned as its own slice). Raw per-screen findings: the workflow
journal for run `wf_3d57190e-249`.

## Layout rulings — owner, 2026-08-25

Asked screen by screen; these govern the structural slice.

| Screens | Ruling |
|---|---|
| Overview | **Full rebuild** to the `developer_control_center` bento: viewport-locked grid, KPI row, per-pane scroll |
| Findings, Runs, Call sites | **Full rebuild**: viewport-locked table filling the screen, compressed KPI strip, docked right inspector fed by selection |
| Finding detail, Workflow | **Full rebuild** to the two-column split: evidence timeline left, remediation/code right, per-pane scroll |
| Solutions | **Rebuild** to the `remediation_ci_cd_policy` board |
| Graph | Canvas + docked node inspector; **Vendors, Services, Telemetry keep their table layouts** (their data is tabular; the service-map look arrives with the motion tier) |
| Trends, Settings, Detectors, Corpus, Integration changes, File tree | **Reskin only** — systemic chrome, badges, banded headers, density |

**Build order:** the viewport-locked frame mechanics land once in `ScreenFrame` (everything sits
on it), then Findings → Overview → Call sites → Runs → Finding detail → Workflow → Solutions →
Graph. Each lands gated with a re-capture before the next starts.

## Supabase reference, via Mobbin (2026-08-25)

The owner enabled Mobbin Pro and pointed at Supabase specifically. It is the right reference for
this console: our primitives are already vendored from Supabase under the 2026-08-06 carve-out, so
its patterns and our components are the same material. Read as composition, per `CI-W630`.

What its dashboard does that ours does not, each restated as a problem rather than a picture:

| Pattern | The problem it solves here |
|---|---|
| **Table toolbar directly above the rows** — filter field, then actions, then one primary button at the right edge | Our filters live in a rail or a controls band away from the table; a reader narrowing a table looks at the table. The eval's finding #8 is the same gap seen from the Stitch side. |
| **Column type annotations** — `id int8`, `created_at timestamptz` in muted mono beside the header | Our columns say what they are named, never what they hold. Sync's equivalent is the unit or grain a column counts, which several screens currently explain in prose beneath. |
| **Bottom bar owning pagination and the record count** — `Page 1 of 1 · 100 rows · 18 records` | We already have a status band; this is the same instrument and confirms the placement. |
| **Grouped section nav** — MANAGE / NOTIFICATIONS / CONFIGURATION as furniture headings over items | Exactly the stage grouping the sidebar landed in `CI-W624`. Independent confirmation, not a change. |
| **Two-tier navigation** — a 48px icon rail *plus* a labelled section nav, on screens with sub-sections | Ours collapses to one tier. Settings and the graph screens are where a second tier would earn itself. **Not adopted yet**: it is a real change to the chassis and belongs to a ruling, not to a rebuild. |
| **Environment chip in the trail** — `main [PRODUCTION]` beside the project | We put `LOCAL DEV` in the top bar in `CI-W624`; Supabase puts it in the trail beside the branch. Worth revisiting when the trail work settles. |

**What is deliberately not taken:** the primary green is already ours from the token sheet, and the
identity elements stay excluded. Nothing here overrides a Stitch screen where the two disagree.

## Coverage map — what a screenshot cannot see

The 13 captures cover the default state of every routed screen. "Every pixel" also includes the
surfaces below; each gets its own capture-and-compare pass once the systemic fixes land, because
comparing them before the base changes would find differences already scheduled to move.

| Surface | How it is evaluated | Reference |
|---|---|---|
| Hover, active, focus-visible on every interactive element | Playwright `:hover`/focus scripting per component, compared against the prototypes' state classes in each `code.html` | all `code.html` files |
| Loading, empty, error states per data surface | API stubbed per state; capture each; the empty state must say *which* nothing it is | builder prompt, quality section |
| Drawers, dialogs, dropdowns, command palette | Opened via Playwright, captured over each base screen | `self_healing_queue` (drawer), `platform_settings` (dialogs) |
| Sidebar collapsed rail (48px) | Captured in both pin states | `integration_fleet_overview` |
| Table sort, filter, pagination affordances | Captured engaged | `repository_index_explorer`, `infrastructure_logs` |
| Scrollbars, selection colour, focus rings | Spot-checked via computed styles — thin dark scrollbars, `selection:bg-primary-container`, emerald rings | prototypes' base CSS |
| Motion tier — pulses, flows, entrances, 3D graph | Deferred to the motion phase by design; static parity first | `shader/`, `three.js/`, `animated_live_telemetry_hub` |
| The four set-aside screens | Not evaluated, owner ruling 2026-08-24 | — |

## Appendix — iteration 1, every finding, per screen

Complete extraction from run `wf_3d57190e-249` (14 agents, 351 findings). This is the
every-pixel inventory: a difference absent here was either already identical to the reference
or is one of the twelve systemic entries above. Re-capture after each fix retires rows; the
workflow journal keeps the original record.

### `overview` vs `developer_control_center` — 27 findings

| Imp | Eff | Axis | Difference | File |
|---|---|---|---|---|
| 5 | S | hierarchy | The reference leads with a 46px Manrope display title plus a one-line subtitle under it and a bottom rule; ours opens with a 24px 'Overview' heading and no subtitle, so nothing on our page reads as the page's headline at a glance. | `layouts/screen-frame.tsx` |
| 5 | L | structure | The reference composes the canvas as a bento grid — an 8-column hero card beside a 4-column actions card, then a full-width tile band, then a three-up card band — while ours is a single-column stack of full-width bands (scope prose, pipeline strip, getting-started, then two map cards). | `features/repositories/codebase-page.tsx` |
| 4 | S | colour | The reference's active nav item is a filled primary pill (#45cd8e-family background, dark ink, rounded); ours is a barely-visible dark-green tint (rgb 24,39,31) with a thin right-edge accent bar. | `layouts/app-frame.tsx` |
| 4 | S | colour | The reference carries one filled-primary CTA ('Deploy Agent', green fill with dark ink) in the top bar; our entire screen has no filled-primary element — every button is a neutral gray outline chip, so no action carries brand weight. | `layouts/app-frame.tsx` |
| 4 | M | componentry | **[DATA-SUBSTITUTION]** The reference presents its three headline figures inside bordered surface-dim sub-tiles (label above, 28px figure below, one accented green); our pipeline numerals sit directly on the strip background with no tile containment — the reference's fictional metrics (14.2M events, 843 healing actions, 12ms p99) map to our real pipeline counts (calls observed, open findings, call sites indexed). | `features/repositories/pipeline-strip.tsx` |
| 4 | M | componentry | **[DATA-SUBSTITUTION]** The reference has a 'Command Center' card of three large icon+label+arrow action buttons (one amber-accented destructive); ours has no quick-actions card anywhere — nearest real actions are run an index pass, fetch vendor signals, and flush the local demo workspace. | `features/repositories/codebase-page.tsx` |
| 4 | M | componentry | The reference's top bar leads with a persistent bordered search input ('Search commands, logs...') at the left; ours offers only a 'Jump to a destination Ctrl K' pill at the far right that opens a palette, with no visible input field. | `layouts/command-palette.tsx` |
| 4 | L | density | The reference lands six data-bearing widgets inside one viewport (hero figures, quick actions, four integration tiles, audit log, PR feed, meters); our first viewport spends its height on prose sentences and a readiness checklist, pushing both graph cards below the fold behind a scrollbar. | `features/repositories/codebase-page.tsx` |
| 4 | L | componentry | **[BLOCKED]** The reference's hero is a 'Global Sync Status' card with an ACTIVE pill and 'real-time agent telemetry stream active' copy — a composite liveness signal our console is forbidden to carry; ours correctly has no equivalent, so this cannot be closed as drawn. |  |
| 4 | L | componentry | **[DATA-SUBSTITUTION]** The reference's full-width integration band is a grid of per-vendor tiles — brand-coloured icon chip, vendor name, mono file path, status badge — while ours renders an integration map graph; the tiles' fictional vendors map to our real vendors/bindings with their call-site paths, and HOOKED/PENDING maps to our adapter status vocabulary. | `features/repositories/api-surface-panel.tsx` |
| 3 | S | colour | Our READY/MISSING chips are neutral gray-on-gray; the reference colour-codes its closed-vocabulary badges (green status-good bg/ink for HOOKED, amber status-warning for PENDING) — closed-vocabulary badge colouring is permitted and ours drops it. | `components/status.tsx` |
| 3 | S | motion | **[BLOCKED]** The reference shows a visible glow halo (box-shadow pulse in the markup) on the hero's tower icon and ACTIVE pill — a liveness pulse, which our console is forbidden to carry. |  |
| 3 | M | componentry | The reference's hero card has a glass treatment — holographic gradient border, backdrop blur, diagonal green gradient wash — while all our cards are flat matte panels with uniform borders. |  |
| 3 | M | componentry | **[DATA-SUBSTITUTION]** The reference has a 'System Audit Log' card: a dense mono event table with 10px timestamps and coloured category chips (AUTH/ERR/HEAL/SYS) under a darker header strip; ours has no recent-events feed — nearest real facts are recent index passes, signal fetches and run events. |  |
| 3 | M | componentry | **[DATA-SUBSTITUTION]** The reference has a 'Remediation PRs' feed (status icon, PR title, '#id • author', relative time per row); ours exposes remediation only as a 'Runs →' text link in the pipeline strip — nearest real facts are recent remediation runs and their opened pull requests. |  |
| 3 | M | componentry | **[DATA-SUBSTITUTION]** The reference has a 'Resource Telemetry' card of three thin labelled progress meters with right-aligned mono values (CPU/Memory/Network are metrics we do not measure); the meter treatment maps to real per-integration observed call volume or index-pass durations. |  |
| 3 | M | density | Our sidebar interleaves full-sentence stage descriptors ('downloads vendor specs and diffs them') between nav items, roughly doubling nav height; the reference nav is single-line icon+label rows with no prose. | `layouts/app-frame.tsx` |
| 3 | M | structure | Ours devotes a full-width band to a 'Getting started' readiness checklist (six labelled checks plus three buttons) that the reference does not have at all; in the reference layout that slot is data, not setup. | `features/repositories/getting-started-card.tsx` |
| 3 | M | componentry | **[DATA-SUBSTITUTION]** The reference's top bar carries Production/Staging environment tabs with a green active underline; ours has breadcrumb scope dropdowns instead — we have no environments, so the nearest real fact is the workspace/repository scope already in our breadcrumbs. |  |
| 2 | S | density | Ours carries explanatory caveat sentences on the canvas (the SCOPE sentence, 'Every figure is this workspace's alone...') that the reference never spends canvas rows on. | `features/repositories/codebase-page.tsx` |
| 2 | S | colour | The reference elevates its top bar (#1f201f) and sidebar (#1b1c1b) above the #131413 canvas with border separators; our top bar and sidebar sample as the same canvas black, flattening the chrome. | `index.css` |
| 2 | S | typography | Ours renders the workspace identity as large prominent mono text in the top bar ('github.com/stroland02/demo-v1 · local dev · git: stroland02'); the reference keeps the top bar entirely sans and restricts mono to data values (paths, timestamps, badges). | `layouts/app-frame.tsx` |
| 2 | S | componentry | The reference sidebar header is a brand block — filled circular green logo, 'Sync' wordmark, 'API Automation' subtitle, under-rule; ours is a bare glyph plus wordmark with no subtitle or separator. | `layouts/app-frame.tsx` |
| 2 | S | componentry | **[inferred]** The reference includes a dashed-border 'Manually Add Integration' tile as the fourth grid cell; ours has no manual-add affordance, and since our integrations come from static indexing the action behind it may not exist. |  |
| 2 | S | structure | The reference constrains content to a centered max-width column with page-frame padding; our canvas runs full-bleed from the sidebar to the window edge. | `layouts/screen-frame.tsx` |
| 2 | M | componentry | **[inferred]** The reference top bar's right cluster has a notification bell, help icon and avatar image; ours has none of these (identity lives in the sidebar footer) — a notification feed may not exist in our data model. |  |
| 2 | M | componentry | Ours shows a breadcrumb trail with two inline scope-switcher dropdowns in the top bar; the reference top bar has no breadcrumbs at all — its top bar is search, environment tabs and actions only. | `layouts/breadcrumbs.tsx` |

### `call-sites` vs `repository_index_explorer` — 27 findings

| Imp | Eff | Axis | Difference | File |
|---|---|---|---|---|
| 5 | L | structure | The reference keeps a persistent code-preview pane (PREVIEW (LINE 42)) with the call's source and a primary-highlighted line always on screen; ours shows no code at all until a row click opens the drawer. | `features/bindings/call-site-drawer.tsx` |
| 4 | S | componentry | Our binding-status pills (CLEAN / AT RISK) render under the Loops header and the numeric loop depth under Status — the cells emit status before loops while the headers declare Loops before Status, a visible column swap the reference does not have (its badge sits under its Status header). | `features/bindings/call-sites-page.tsx` |
| 4 | L | structure | The reference's left pane is a PROJECT STRUCTURE file tree that scopes the table to one selected file; ours is a NARROW THE CALL SITES facet rail with no file-tree navigation (only a path-prefix facet). | `features/bindings/call-sites-page.tsx` |
| 3 | S | hierarchy | The reference leads with an 18px icon-plus-title header followed by a one-line grey purpose sentence; ours leads with a ~28px bare 'Call sites' H1 with no icon and no description line (our CI-W622 convention deliberately sizes the screen name above its sections, so adopting the reference's scale reverses a recorded ruling). | `layouts/screen-frame.tsx` |
| 3 | S | componentry | **[BLOCKED]** The reference shows a System Healthy pill with a pulsing dot; this is a composite health indicator with a liveness pulse and is refused outright by the console's rules — not to be carried in any form. | `layouts/app-frame.tsx` |
| 3 | M | structure | The reference is a fixed-viewport app frame (h-screen, overflow-hidden) where each pane scrolls internally and everything sits above the fold; our page scrolls as one document, with a visible right-edge scrollbar and content continuing below the fold. | `layouts/app-frame.tsx` |
| 3 | M | density | Reference rows are single-line ~33px compact mono rows; ours run ~48px because the FILE column wraps paths onto two lines, so roughly a third fewer rows fit before the fold. | `features/bindings/call-sites-page.tsx` |
| 3 | L | structure | **[DATA-SUBSTITUTION]** The reference attaches a CALL SITE TELEMETRY footer (P95 LATENCY, ERROR RATE (1H), LAST OBSERVED) to the selected call site; ours surfaces no runtime facts beside a call site — P95 latency and error rate are not measured here, so the mappable facts are telemetry's last_seen and observed request volume only. | `features/bindings/call-site-drawer.tsx` |
| 3 | L | structure | **[DATA-SUBSTITUTION]** The reference's nav is a flat six-item MENU (Dashboard, Integrations, Self-Healing Queue, Telemetry/Traces, API Keys, Settings) with a Docs/Support footer; ours is a pipeline-grouped rail (Index / Signal / Observe / Detect / Remediate) with prose stage captions — the reference's menu names screens this product does not have, so our real IA is the nearest mappable structure. | `layouts/app-frame.tsx` |
| 2 | S | componentry | Every reference pane opens with a 32px uppercase furniture strip on the surface-container step (PROJECT STRUCTURE, WATCHED CALL SITES..., PREVIEW...); our cards have no header strips — the rail title floats unboxed and the table card opens with a metric block. | `features/bindings/call-sites-page.tsx` |
| 2 | S | componentry | **[DATA-SUBSTITUTION]** The reference carries a Sensitivity column (icon + High/Low/Critical in warning/critical inks); sensitivity is not a fact we measure — the nearest real fact, binding status, is already on the row as a pill, so the only adoptable part is the inline icon-plus-word rendering rather than a new column. | `features/bindings/call-sites-page.tsx` |
| 2 | S | colour | The reference's sidebar sits on the raised surface-container-low step (#1b1c1b) with a right border; ours shares the page background (#131413), so the rail-to-page split reads flatter than the target. | `layouts/app-frame.tsx` |
| 2 | S | colour | The reference renders the active nav item in primary green text with a 2px #65eaa8 (primary) edge bar; ours keeps the label in white ink on a dark green tint with a #45cd8e (primary-container) bar — the accent is one token step darker and the label does not take the accent colour. | `layouts/app-frame.tsx` |
| 2 | S | typography | The reference sets body text in Inter 13px and reserves Manrope for display/headers; ours sets Manrope for every sans run (index.css --font-sans), so body and headers share one face where the target contrasts two. | `index.css` |
| 2 | S | density | Ours spends roughly 230px on the title, the Columns button and surrounding whitespace before any data; the reference reaches its first data row about 90px below its title via tight 8px pane gaps. | `layouts/screen-frame.tsx` |
| 2 | M | hierarchy | The reference states the record count as a small '4 SITES' chip inside the pane's header strip; ours leads the card with a metric-panel figure ('40' at display scale) above the table, giving the count more visual weight than any row. | `features/bindings/call-sites-page.tsx` |
| 2 | M | componentry | The reference's top bar opens with a bordered 'Search resources...' input field on the left; ours offers search only as a 'Jump to a destination Ctrl K' button pushed to the far right. | `layouts/app-frame.tsx` |
| 2 | M | structure | Ours carries a breadcrumb/scope-switcher path (Repositories / repo / Vendor / Call sites) where the reference has none — a reverse difference; the breadcrumb is our real scoping model and the reference offers nothing to replace it. | `layouts/breadcrumbs.tsx` |
| 2 | M | componentry | The reference ends the top bar with notification and terminal icon buttons plus an avatar photo; ours shows the repo identity string and the Ctrl K button, with the account chip relocated to the sidebar footer and no icon buttons. | `layouts/app-frame.tsx` |
| 2 | L | componentry | **[DATA-SUBSTITUTION]** The reference's Status column carries a live verification state per call site ('Verifying' with a spinner, 'Verified' with a check); we hold no per-call-site verification state — verification is a property of a remediation run, so the nearest real fact is binding status or a link to the run, not a carried state word. | `features/bindings/call-sites-page.tsx` |
| 1 | S | colour | The reference wordmark 'Sync' is primary green inside a primary-tinted rounded icon tile; ours renders the wordmark in white ink with a plain glyph and no tile. | `layouts/app-frame.tsx` |
| 1 | S | typography | The reference's column headers are Title Case furniture (Line, Integration); ours are uppercase letterspaced (FILE, SYMBOL). | `features/bindings/call-sites-page.tsx` |
| 1 | S | typography | The reference's data mono is the system ui-monospace stack (Menlo/Consolas); ours renders JetBrains Mono — a deliberate token choice in DESIGN.md, but a visible face difference against the target. | `index.css` |
| 1 | S | componentry | Our operation values render as underlined links; the reference's method values are plain mono text with no underline. | `features/bindings/call-sites-page.tsx` |
| 1 | S | componentry | Ours shows a 'Columns' visibility control the reference lacks — a reverse difference tied to our wider column set. | `components/column-visibility.tsx` |
| 1 | S | motion | **[inferred]** The reference declares an active:translate-y-px press nudge on nav links and buttons (its colour transitions are duration-0, i.e. instant); ours shows no visible press affordance. | `layouts/app-frame.tsx` |
| 1 | M | motion | **[inferred]** The reference's markup spins the 'Verifying' status icon (animate-spin) on the in-flight row (the column is clipped in the still); ours shows no in-progress affordance — and since per-call-site verification is not a state we hold, the only honest home for such motion would be a live run elsewhere. | `features/bindings/call-sites-page.tsx` |

### `vendors` vs `code_graph_service_map_supabase_style` — 32 findings

| Imp | Eff | Axis | Difference | File |
|---|---|---|---|---|
| 5 | L | structure | The reference devotes the whole viewport to a two-region working surface — a full-bleed graph canvas plus a fixed ~420px right inspector panel — while ours is a single scrolling column of title, tabs, tiles and table with no detail pane. | `features/vendors/repository-vendors-page.tsx` |
| 5 | L | componentry | The reference draws the vendor topology as a node graph — a central hub node with vendor nodes joined by edges and a selection ring on the active node — where ours renders the same three vendors as table rows; our real graph facts (vendors, services called, call sites) could populate the nodes and edges. | `features/vendors/repository-vendors-page.tsx` |
| 4 | M | componentry | **[DATA-SUBSTITUTION]** The reference inspector carries a Source Definition code pane — file-path header bar, syntax-highlighted source, uppercase VIEW ON GITHUB link — with no counterpart anywhere on our screen; its Python is fictional, so populate it from a real indexed call-site excerpt. |  |
| 4 | M | componentry | **[DATA-SUBSTITUTION]** The reference tints a troubled node amber end-to-end — node border, warning chip (High Latency), its edge, and a DEGRADED badge in the inspector — while ours shows no per-vendor state at all; the nearest real fact is open-finding severity per vendor rendered as a closed-vocabulary badge, not a live health readout. |  |
| 4 | L | componentry | The reference supports click-to-inspect: selecting a node opens an in-place inspector (status badge, mono node_id, 24px title, subtitle, close button) without leaving the screen, while ours only offers navigation away via the vendor-name link. |  |
| 3 | S | componentry | **[BLOCKED]** The reference topbar shows a SYSTEM HEALTHY pill (green tinted, check icon) — a composite health traffic light our console explicitly does not carry. |  |
| 3 | S | motion | **[BLOCKED]** Reference nodes pulse continuously (pulse-emerald/pulse-amber box-shadow keyframes in code.html, 2-3s infinite) — a liveness pulse, which our binding forbids. |  |
| 3 | S | typography | The reference sets every micro-label — stat-tile captions, badges, the topbar context label — in JetBrains Mono 11px uppercase with 0.05em tracking, while our stat-tile captions (WATCHED HERE, STAGED) and table headers are uppercase sans. |  |
| 3 | S | hierarchy | The reference has no page heading at all — the working canvas leads and context lives in a quiet topbar micro-label — while ours spends the first ~120px on the Vendors H1 and tab row before any fact appears (note: our CI-W622 convention requires the screen to name itself, so this difference is a deliberate divergence to reconcile, not an automatic fix). | `features/vendors/repository-vendors-page.tsx` |
| 3 | M | componentry | **[DATA-SUBSTITUTION]** The reference inspector opens with two per-vendor metric tiles (Latency 99p 1,402ms with a +45% trend delta, Error Rate 0.12% Steady) that ours lacks; the figures are fictional and latency percentiles are not something we surface here, so map to per-vendor facts we do hold — call sites, services called, changes recorded. |  |
| 3 | M | density | Ours leaves roughly the lower 40% of the viewport empty below the three-row table, while the reference fills the full height with canvas and inspector. | `features/vendors/repository-vendors-page.tsx` |
| 3 | M | componentry | Our four page-level stat tiles (Watched here, Staged, Available, Changes recorded) have no counterpart in the reference, whose only stat tiles are per-node inside the inspector. | `features/vendors/repository-vendors-page.tsx` |
| 2 | S | componentry | **[DATA-SUBSTITUTION]** Reference node sublabels carry metrics we do not measure — 100% Uptime, 34ms avg, 85ms avg — the nearest real per-vendor facts are call-site and recorded-change counts. |  |
| 2 | S | motion | **[inferred]** Reference edges are grey-to-green (grey-to-amber on the warning path) gradients implying directional flow along the connection — a trail affordance ours has no equivalent of. |  |
| 2 | S | componentry | The reference canvas has zoom in / zoom out / fit-to-view controls bottom-left; ours has no canvas and no such controls. |  |
| 2 | S | structure | The reference topbar leads with an always-visible bordered search input (Search services...) at left; ours exposes search only as the Ctrl-K Jump-to-a-destination pill at the far right. |  |
| 2 | S | componentry | **[DATA-SUBSTITUTION]** The reference topbar right holds a notifications bell, a terminal icon button, and a circular avatar; ours has none of these in the topbar — no notification center exists, and our account identity already lives in the sidebar footer. |  |
| 2 | S | typography | Reference headlines are Manrope 600 with negative letterspacing (24px inspector title, 18px brand); our Vendors heading and tile numerals render in the console's single sans face. |  |
| 2 | S | hierarchy | Context placement inverts: the reference states scope as a small uppercase mono label at topbar left (SERVICE MAP : US-EAST-1) while ours puts the repo path center-stage in the topbar as large mono text that visually outweighs the nav. |  |
| 2 | S | density | Our screen closes with a three-paragraph explanatory prose block (Vendors 3 of 3 attached... / Nine graph levels...) that the reference has no counterpart for. | `features/vendors/repository-vendors-page.tsx` |
| 2 | S | density | Our sidebar interleaves prose stage descriptions (reads the code, downloads vendor specs and diffs them, ...) between nav items, while the reference nav is bare labels with icons only. | `layouts/app-frame.tsx` |
| 2 | S | structure | Ours carries list controls the reference lacks — the All/Generated filter tabs and the Table/Cards view toggle. | `features/vendors/repository-vendors-page.tsx` |
| 2 | S | colour | The reference canvas backdrop is a 24px dotted grid of primary green at 5% opacity (radial-gradient #60eca8); our content area is a flat dark surface. |  |
| 2 | S | colour | The reference primary accent is #60eca8 with #3ecf8e as container, while our --color-primary is #45cd8e — visibly duller on the active nav item and links. | `index.css` |
| 2 | S | colour | Reference healthy nodes carry a static emerald glow (box-shadow 0 0 20px rgba(96,236,168,0.15)); nothing on our screen glows. |  |
| 2 | S | componentry | The reference inspector is glassmorphic — rgba(23,23,23,0.7) with 16px backdrop blur over the canvas — while all our surfaces are opaque. |  |
| 2 | S | componentry | Badge treatment differs: reference badges are tinted-fill (10% colour background, 20% colour border, coloured text, often with an icon) while our GENERATED pills are outline-only mono with no fill. |  |
| 2 | M | componentry | **[DATA-SUBSTITUTION]** The reference sidebar ends in a full-width primary CTA button (Deploy Integration) above Docs/Support; ours has no primary action in the sidebar — the action itself is fictional, and the nearest real one would be attaching/watching a repository. |  |
| 1 | S | motion | **[inferred]** Reference interactive elements carry press micro-motion (active:translate-y-px) and instant hover fills per code.html; not observable in our static capture. |  |
| 1 | S | componentry | Active nav treatment differs: the reference marks the active item with a right-edge 2px green border, 10% green fill and green text, while ours uses a left green bar on a neutral fill. |  |
| 1 | S | typography | **[DATA-SUBSTITUTION]** The reference brand block carries an uppercase mono tagline (AI API ORCHESTRATOR) under the wordmark; ours shows the logo and name only — the reference copy is fictional positioning, so any tagline would need our real one. |  |
| 1 | S | structure | Sidebar footers differ: the reference ends with Docs and Support links, ours with the account chip and Settings. | `layouts/app-frame.tsx` |

### `services` vs `integration_performance_explorer` — 24 findings

| Imp | Eff | Axis | Difference | File |
|---|---|---|---|---|
| 5 | L | structure | **[DATA-SUBSTITUTION]** The reference leads with a concrete service drill-down (identity header, KPIs, drift timeline, endpoint panel for one integration); ours spends the entire fold on definitional taxonomy cards, with the actual services table pushed below the fold. | `features/vendors/repository-services-page.tsx` |
| 5 | L | density | **[DATA-SUBSTITUTION]** The reference fold carries roughly a dozen measured values (4 KPI figures with deltas, 3 endpoint latencies, event timestamps); our fold carries zero measured facts, only prose definitions. | `features/vendors/repository-services-page.tsx` |
| 5 | L | componentry | **[DATA-SUBSTITUTION]** The reference has a four-across KPI tile row (28px figure, unit suffix, corner icon, trend-arrow delta line); ours has no figure tiles anywhere on the screen — throughput/latency/success-rate would map to observed telemetry we do capture. | `features/vendors/repository-services-page.tsx` |
| 5 | L | componentry | **[DATA-SUBSTITUTION]** The reference draws a schema-drift provenance timeline — circular icon nodes on a vertical connector, per-event cards with mono timestamps, inline code chips, and an embedded red-strikethrough/green-added diff pane — absent from ours; real vendor spec-diff events and findings are the mappable facts. | `features/vendors/repository-services-page.tsx` |
| 4 | M | hierarchy | **[DATA-SUBSTITUTION]** The reference page header is an entity identity block — 48px rounded icon tile, 22px title, and a meta line (version, base URL, auth method); ours is a bare text title with no icon, badge, or meta facts (spec version and base URL are real facts we hold). | `layouts/screen-frame.tsx` |
| 4 | M | componentry | **[DATA-SUBSTITUTION]** The reference places a section tab bar under the header (Overview, Performance, Schema, Logs with a count pill, Remediation Settings); our screen shows no tabs — real sections would be call sites, spec diffs, observed traffic, findings. | `layouts/screen-tabs.tsx` |
| 4 | M | componentry | **[DATA-SUBSTITUTION]** The reference has an Endpoint Health side panel listing method chip + mono path + latency per row; ours has no per-operation list on this screen — observed operations with latency are measurable and mappable. | `features/vendors/repository-services-page.tsx` |
| 3 | S | colour | Active nav in the reference is a filled primary-container pill (#45cd8e) with dark-green ink (#005333) and a filled icon; ours is a faint #18271f tint with white text and a thin green bar on the right edge. | `layouts/app-frame.tsx` |
| 3 | S | componentry | **[BLOCKED]** The reference's 'Healthy' badge beside the title is a composite health traffic light, which our console forbids (closed-vocabulary state badges remain the permitted form). |  |
| 3 | M | componentry | **[DATA-SUBSTITUTION]** The reference ends with a Live Traffic Telemetry table (colored status-code chips, warning/critical row tints, mono columns, trace-ID filter input) which is not visible anywhere in our viewport. | `features/telemetry/observed-calls-table.tsx` |
| 3 | M | structure | The reference main canvas is an asymmetric bento (two-thirds timeline + one-third side panel over a full-width table); ours is a uniform three-column card grid. | `features/vendors/repository-services-page.tsx` |
| 3 | M | componentry | **[DATA-SUBSTITUTION]** The reference header carries page-level actions (neutral Pause Sync plus filled-green Force Sync); ours offers no actions on the screen — the nearest real actions are re-index or poll vendor specs. | `layouts/screen-frame.tsx` |
| 3 | M | structure | **[DATA-SUBSTITUTION]** The reference top bar has environment tabs (Production/Staging) at left and a global cluster (Deploy Agent CTA, bell, help, avatar) at right; ours carries a scope breadcrumb, repo identity, and a command-palette hint instead — environments would map to our real scopes (local dev, git remote). | `layouts/app-frame.tsx` |
| 3 | M | colour | The reference uses the filled-primary control style (dark ink on #45cd8e) for its main CTAs; no filled-green control appears anywhere in ours — accent green exists only as outline badges and text. | `components/ui/button.tsx` |
| 3 | M | density | Reference sidebar items are single-line labels; ours interleaves group headings with full-sentence descriptions ('reads the code', 'downloads vendor specs and diffs them'), roughly doubling nav height per item. | `layouts/app-frame.tsx` |
| 3 | M | typography | **[inferred]** Reference headings are Manrope at a distinct display scale (22px page header, 18px section header, tight -0.02 to -0.04em tracking); our titles render in the same sans face as body copy with no second display face. | `layouts/screen-frame.tsx` |
| 3 | L | componentry | **[BLOCKED]** The reference's 'Cost Saved via Auto-Fix' KPI tile ($1,240/mo, 421 errors mitigated automatically) is a healed-count and savings metric Sync does not measure. |  |
| 2 | S | componentry | **[BLOCKED]** The per-row green/amber liveness dots in the reference's Endpoint Health panel are traffic-light indicators our console forbids. |  |
| 2 | S | colour | Reference chrome sits on layered surfaces (top bar #1f201f, sidebar #1b1c1b) distinct from the #131413 canvas; ours renders both chrome regions in the same #131413 as the canvas, separated by borders only. | `layouts/app-frame.tsx` |
| 2 | S | componentry | **[DATA-SUBSTITUTION]** The reference sidebar footer is a workspace identity block (icon tile, org name, 'Pro Plan • us-east-1' second line); ours is a plain user row plus Settings link — plan/region are fictional, git identity and repo scope are the real facts. | `layouts/app-frame.tsx` |
| 2 | S | hierarchy | The reference repeats the breadcrumb inside the content header directly above the title, with chevron icon separators and an emphasized current-page token; ours confines a slash-separated breadcrumb to the top app bar. | `layouts/breadcrumbs.tsx` |
| 2 | S | typography | **[inferred]** Reference body and meta copy sit at 13px/20 and 12px/16 tokens; our card prose reads a step larger (~14-15px) with looser leading, costing rows per fold. | `features/vendors/repository-services-page.tsx` |
| 2 | M | componentry | The reference top bar includes a notification bell, help button, and avatar cluster; ours has none of the three. | `layouts/app-frame.tsx` |
| 1 | S | motion | **[inferred]** The reference markup carries hover affordances — an accent glow fading in on the savings tile, border-colour shifts on timeline cards, and a 1px press translation on buttons — none of which our screen shows evidence of. |  |

### `observed` vs `live_telemetry_agent_hub` — 28 findings

| Imp | Eff | Axis | Difference | File |
|---|---|---|---|---|
| 5 | L | structure | The reference composes the whole screen as a three-pane bento grid (operations log 4/12, live call table 5/12, health rail 3/12) locked to one viewport with each panel scrolling internally; ours is a one-column stack (KPI strip, chart, rollup table) that scrolls the page. | `features/signals/signals-page.tsx` |
| 4 | S | hierarchy | **[BLOCKED]** Directly under the page title the reference leads with a system status line ('System nominal. Agents active.') fronted by a pulsing green dot — a composite health claim plus a liveness pulse, both refused; our compliant equivalent is the existing textual 'As of 1s ago. Refreshing in the background.' line. |  |
| 4 | M | structure | **[DATA-SUBSTITUTION]** The reference's right rail is 'Node Health' cards with per-agent CPU/MEM progress meters, metrics we do not measure — the nearest real facts are per-signal-source status (attached-at, last span seen, spans recorded) already carried by the signal-source panel; the meters themselves cannot be carried. | `features/telemetry/signal-source-panel.tsx` |
| 4 | M | density | The reference puts every fact above the fold with 12px mono rows and 12px panel padding; ours spends roughly 530px on the KPI band plus chart before the first table row, pushing the operation rollup below the fold at 900px tall. | `features/signals/signals-page.tsx` |
| 4 | L | structure | **[DATA-SUBSTITUTION]** The reference's left pane is a timestamped agent-operations event log; our screen has no activity pane at all — the fictional 'Analyzing Trace / Synthesizing Fix' steps map to our real remediation run and workflow activity events, not to anything invented. | `features/signals/signals-page.tsx` |
| 3 | S | hierarchy | **[DATA-SUBSTITUTION]** The reference right-aligns two bordered stat chips (Avg Latency 12ms, 99.99% Uptime) on the page-header line; uptime is a metric we do not measure, so the chip pattern maps to measured KPI figures (calls observed, error windows) if adopted at header level. | `features/signals/signals-kpis.tsx` |
| 3 | S | componentry | **[BLOCKED]** The reference carries a bright 'Deploy Agent' primary CTA (with hover shimmer) in the topbar; our console is read-only by owner ruling and holds no real deploy action to bind it to. |  |
| 3 | S | density | The reference's table rows are ~28px tall (py-1.5 on 12px mono); ours run ~38px with roomier cell padding, costing roughly a third of the rows per fold. | `features/telemetry/traffic-rollup-table.tsx` |
| 3 | S | colour | The reference fills the active nav item as a bright primary-container pill (#45cd8e) with dark on-primary ink; ours marks it with a faint dark-green tint (#182720) and a left accent bar. | `layouts/app-frame.tsx` |
| 3 | S | motion | **[BLOCKED]** The reference animates liveness everywhere — pulsing header dot, pulsing ACTIVE badge, animate-ping stream indicator, pulsing 429 badge and pulsing 88% CPU bar — all liveness pulses our surface refuses; ours states recency in text instead. |  |
| 3 | M | componentry | The reference exposes a persistent mono-face search input ('Search traces...') in the topbar; ours offers search only behind the 'Jump to a destination Ctrl K' button. | `layouts/command-palette.tsx` |
| 3 | M | componentry | The reference gives every panel a tinted header strip (one surface step up, bottom border) with a leading icon glyph and a right-side status affordance; our card headers sit flat on the card with only a trailing info glyph. | `components/ui/card.tsx` |
| 3 | M | componentry | The reference's call table renders status codes as tinted closed-vocabulary badges (200 good, 429 warning) and colours the method verb (GET vs POST); our rollup shows method-and-host as undifferentiated mono white and errors as plain prose ratios. | `features/telemetry/traffic-rollup-table.tsx` |
| 3 | L | structure | The reference has a fixed utility topbar (search field, environment tabs, bell, help, primary CTA, avatar) on a tinted strip; our top row is breadcrumbs plus repo identity plus a command-palette trigger, with no utility cluster. | `layouts/app-frame.tsx` |
| 2 | S | colour | The reference lifts chrome one surface step above the page (sidebar #1b1c1b, topbar #1f201f, table well dropped to #0d0e0d); our sidebar and topbar sit on the page background (#131413) separated by borders alone. | `layouts/app-frame.tsx` |
| 2 | S | typography | The reference splits faces by role — Manrope for display/page/section headers, Inter 13px/450 for body and meta; ours runs one sans stack (Manrope-first) for headers and body alike. | `index.css` |
| 2 | S | typography | The reference sets every data value — timestamps, chip figures, log labels, table cells — in 12px mono; our KPI values, chart axis labels and the freshness line render in sans. | `features/signals/signals-kpis.tsx` |
| 2 | S | structure | The reference places the account avatar in the topbar's right cluster; ours anchors the account row (stroland02) at the sidebar's bottom. |  |
| 2 | S | structure | Ours opens with a four-tile KPI strip (telemetry attached, calls observed, shapes recorded, error windows) that has no counterpart on the reference screen. | `features/signals/signals-kpis.tsx` |
| 2 | S | structure | Ours carries a full-width stacked-bar traffic-over-time chart with legend; the reference screen has no chart pane at all. | `features/telemetry/traffic-over-time-card.tsx` |
| 2 | M | componentry | **[DATA-SUBSTITUTION]** The reference's topbar has Production/Staging environment tabs; we have no environment dimension — the nearest real scope facts are the repository and vendor switchers already in our breadcrumb. |  |
| 2 | M | componentry | **[DATA-SUBSTITUTION]** The reference's topbar carries a notification bell and help icon button; ours has neither, and a bell presumes an unread-alerts store we do not hold — the nearest real fact is the recorded findings/error-window counts. |  |
| 2 | M | componentry | **[inferred]** The reference's log entries and table rows are click-to-expand with inline detail payloads (decision context, req_id) sliding open beneath the row; ours navigates via underlined operation links to detail pages instead. |  |
| 2 | M | density | The reference's sidebar is six flat icon-led items at compact row height; ours interleaves stage group headers with prose explainer lines ('reads the code', 'downloads vendor specs and diffs them'), roughly doubling the nav's vertical spend. | `layouts/app-frame.tsx` |
| 1 | S | componentry | The reference's sidebar identity block is a filled green logo tile plus wordmark plus 'Self-maintaining API' subtitle; ours is a small glyph and wordmark only. | `layouts/app-frame.tsx` |
| 1 | S | structure | Ours renders a breadcrumb trail with scope switchers plus a repo identity string in the top row; the reference topbar carries no breadcrumb or repo identity. | `layouts/breadcrumbs.tsx` |
| 1 | S | colour | **[inferred]** The reference lays a barely-visible binary-digit texture over the page background at ~3-5% green alpha; our background is flat. |  |
| 1 | S | componentry | The reference styles scrollbars to a 6px thumb on transparent track; ours shows the default full-width scrollbar at the right edge of the viewport. | `index.css` |

### `findings` vs `self_healing_queue` — 30 findings

| Imp | Eff | Axis | Difference | File |
|---|---|---|---|---|
| 5 | L | structure | The reference leads with the queue table immediately under the title row (~15% down the viewport); ours pushes the table below a tab row, a KPI band, a Dismissed prose section, a kind-filter row and a section header, so the first data row lands at ~85% of the fold. | `features/findings/findings-page.tsx` |
| 4 | M | density | The reference carries exactly one prose line (the subtitle) on the entire screen; ours spends the fold on five-plus prose blocks (tab caption, two Dismissed paragraphs, the '9 changes to deal with…' explainer) before any table row. | `features/findings/findings-page.tsx` |
| 4 | L | componentry | **[DATA-SUBSTITUTION]** The reference shows a per-row remediation-state chip with icon ('Proposing Fix', 'Testing Sandbox', 'Analyzing Traces', 'Deployed Fix'); ours has no per-row pipeline state — map to the finding's real remediation run/solution state from the Runs pipeline, not a fictional agent status. | `features/findings/findings-table.tsx` |
| 3 | S | hierarchy | The reference subtitle sits directly under the page title as one unit; ours separates the title from its descriptive line with the tab row, so the page reads title, then controls, then caption. | `features/findings/findings-page.tsx` |
| 3 | S | componentry | **[DATA-SUBSTITUTION]** The reference stat pair is CRITICAL 14 / HEALING 08 — 'healing' is a healed-count metric we do not measure; the nearest real facts are the breaking-findings count (we show 4) and remediation runs in flight. | `features/findings/findings-kpis.tsx` |
| 3 | S | componentry | The reference active nav item is a solid green pill with dark text; ours is a faint dark fill with a thin green left edge and green label — far quieter than the target. | `layouts/app-frame.tsx` |
| 3 | M | structure | The reference pairs the page title with two compact stat tiles on the same row (title left, tiles right); ours renders a full-width four-tile KPI band as a separate block below the tabs. | `features/findings/findings-kpis.tsx` |
| 3 | M | structure | The reference top bar is an always-visible inline search field on the left with env links, bell/help icons and a primary CTA on the right; ours is breadcrumb + screen tabs + repo identity with only a 'Jump to a destination Ctrl K' button. | `layouts/control-bar.tsx` |
| 3 | M | structure | The reference table card ends in a pagination footer ('Showing 4 of 24 active remediation jobs', '1 / 6' with chevrons) capping visible rows; ours lists every group in one scroll with no in-card footer or row cap. | `features/findings/findings-table.tsx` |
| 3 | M | density | **[DATA-SUBSTITUTION]** Ours devotes a titled section and two full paragraphs to a zero-valued dismissal measurement; the reference handles the resolved state inline as a dimmed, struck-through table row — dismissed findings are our real analogue of its fictional 'Resolved' row. | `features/findings/dismissed-tally.tsx` |
| 3 | M | componentry | The reference gives every row an explicit right-aligned action ('Inspect' outlined button; 'View Log' ghost on resolved rows); our rows expose only a left chevron expander and no visible action control. | `features/findings/findings-table.tsx` |
| 3 | M | componentry | **[DATA-SUBSTITUTION]** The reference leads each row with a stable human-readable ID (INC-9942) in mono; ours leads with a count label ('1 finding') — the real substitute is the finding/change identifier the graph already holds, not an invented incident number. | `features/findings/findings-table.tsx` |
| 3 | M | colour | The reference uses its green primary (#65eaa8 / #45cd8e) as a strong presence — logo tile, active-nav fill, CTA button; on ours green appears only as thin accents, so the screen reads accent-less at a glance. |  |
| 2 | S | structure | The reference sidebar is a flat six-item icon nav; ours interleaves group labels with prose taglines ('reads the code', 'downloads vendor specs and diffs them') between the items. | `layouts/app-frame.tsx` |
| 2 | S | density | Reference stat tiles are compact two-line tiles (10px uppercase label over a 28px figure, min-width 120px); ours add a third caption line under every figure and stretch to a quarter of the content width each, roughly doubling tile height. | `features/findings/findings-kpis.tsx` |
| 2 | S | hierarchy | The reference table needs no section chrome; ours introduces it with a second-level heading ('Errors and incidents'), a repeated headline count (46 appears twice on screen) and an explainer paragraph, diluting which number leads. | `features/findings/findings-page.tsx` |
| 2 | S | componentry | **[DATA-SUBSTITUTION]** The reference shows a Production / Staging environment switcher; ours shows a static 'local dev' label — real deployments known to the workspace are the fact to surface, not fictional env names. | `layouts/control-bar.tsx` |
| 2 | S | componentry | The reference wraps the table in a rounded bordered card (surface-card with a hairline ring) with a distinct header band; ours renders the table full-bleed inside the section with row rules only, no enclosing card. | `features/findings/findings-table.tsx` |
| 2 | S | componentry | Reference severity badges are fully-rounded pills with a leading icon on a warm tinted fill; our BREAKING badge is a squarer chip — same closed-vocabulary badge idea, different shape and fill treatment. | `features/findings/findings-table.tsx` |
| 2 | S | componentry | The reference dims resolved rows to 75% opacity and strikes through the integration name inline; ours never shows a resolved/dismissed row in the table at all. | `features/findings/findings-table.tsx` |
| 2 | S | colour | The reference token sheet's critical pair is soft salmon ink #fa8880 on #541c15; our BREAKING badge red is brighter and purer than that pair. | `features/findings/findings-table.tsx` |
| 2 | S | typography | The reference sets page/section headers in a distinct display face (Manrope per the token sheet, tight -0.04em tracking); ours sets every heading in the same body sans. | `features/findings/findings-page.tsx` |
| 2 | S | typography | The reference sets integration names in the sans furniture style with mono reserved for IDs and version chips; ours sets vendor/operation, change kind, versions and rung all in mono, so rows read as raw code rather than mixed prose-plus-data. | `features/findings/findings-table.tsx` |
| 2 | S | motion | **[BLOCKED]** The reference animates status icons (animate-spin on 'Proposing Fix', animate-pulse on 'Testing Sandbox' in the markup) — a liveness pulse, which our binding forbids; static icons from a closed vocabulary are the permitted form. |  |
| 2 | M | structure | The reference has no tab rows at all; ours inserts two ('By change / Every finding' view-mode tabs and the 'every kind / breaking / warning / deprecation / addition / info' filter row) between the title and the table. | `features/findings/findings-page.tsx` |
| 2 | M | componentry | **[DATA-SUBSTITUTION]** The reference carries a filled green primary CTA ('Deploy Agent') plus notification-bell and help icons; ours has none of the three — 'Deploy Agent' is fictional, the nearest real action is opening the command palette or a remediation run. | `layouts/control-bar.tsx` |
| 1 | S | componentry | The reference renders the version as a small bordered chip beside the integration name (v2023-10-16); ours puts versions in a separate mono column as plain 'v2320 → v2330' text with no chip treatment. | `features/findings/findings-table.tsx` |
| 1 | S | componentry | The reference brand block is a bordered green logo tile with a green wordmark and an 'API Automation' subtitle; ours is a plain icon with a white wordmark and no subtitle. | `layouts/app-frame.tsx` |
| 1 | S | colour | **[inferred]** Reference surfaces sit on a warm green-tinted near-black ramp (#131413 background, #181a19 card); ours reads as a neutral-to-cool dark that is not on that token ramp. |  |
| 1 | S | motion | **[inferred]** The reference markup gives buttons a 1px press-down (active:translate-y) and zero-duration hover transitions plus row hover fills; no equivalent press affordance is visible in our screenshot. |  |

### `finding-detail` vs `self_healing_incident_inspector` — 25 findings

| Imp | Eff | Axis | Difference | File |
|---|---|---|---|---|
| 5 | M | hierarchy | **[DATA-SUBSTITUTION]** The reference leads with judgement and identity — a critical badge ('Breaking Change Detected') beside a specific subject ('Incident #7742') in one compact header — while ours leads with the bare word 'Finding' and buries severity mid-rail as plain text; the incident number is fictional and maps to our finding identifier or a vendor+operation title. | `features/findings/finding-page.tsx` |
| 5 | L | structure | The reference presents the finding as a slide-over sheet (max-w-5xl, close X, shadow-float) over a dimmed blurred backdrop of the console; ours is a full-page route with the persistent nav rail and topbar always visible. | `features/findings/finding-page.tsx` |
| 5 | L | structure | The reference splits the body into two equal side-by-side panes — Evidence left, Remediation right — each with its own banded header and independent scroll; ours is one content column with a 360px facts rail on the right. | `features/findings/finding-page.tsx` |
| 5 | L | componentry | **[DATA-SUBSTITUTION]** The reference's evidence pane leads with an OpenTelemetry trace waterfall — indented spans, per-span latencies, an error row with inline error text — and ours shows no runtime-telemetry evidence anywhere; the specific trace is fictional, the nearest real fact is the observed telemetry that put this finding on the OBSERVED rung. | `features/findings/finding-page.tsx` |
| 4 | S | componentry | The reference wears severity as a tinted chip with icon plus words (error glyph + 'Breaking Change Detected' on a critical background); our rail prints severity as bare mono text 'info' with no chip, though a closed-vocabulary SeverityTag already exists in the codebase and is used elsewhere on this page's known-changes table. | `features/findings/finding-page.tsx` |
| 4 | M | structure | The reference anchors a fixed footer action bar (Dismiss left; Escalate and Apply right); ours has no footer — the single navigation action sits inline mid-rail as 'Open the solution workflow'. | `features/findings/finding-page.tsx` |
| 4 | M | density | The reference packs trace and diff fully above the fold in 12px/16px mono panes with 4–8px padding; ours spends the fold on prose captions and 32px section gaps so roughly two sections fit before scrolling. | `features/findings/finding-page.tsx` |
| 4 | M | componentry | **[DATA-SUBSTITUTION]** The reference renders the change as a unified code diff pane — file chip 'models/user.ts', -1/+1 counts, line numbers, red removed and green added rows — where our 'Known changes' renders an empty-state prose card or a three-column id/kind/severity table, never a diff; the fictional schema diff maps to our vendor spec-diff record when one names the call site. | `features/findings/finding-page.tsx` |
| 4 | M | colour | The reference commits its accent family to green (#65eaa8 primary / #5feba7 tertiary) — the GET verb, the Proposed Fix icon, added diff rows, pass ticks, and a filled glowing primary CTA — while our screen is entirely monochrome greys and white with no accent hue visible. |  |
| 4 | L | componentry | **[DATA-SUBSTITUTION]** The reference's right pane shows the proposed patch as a syntax-highlighted code pane with the inserted block tinted green behind a left accent border plus a one-paragraph rationale; ours reduces remediation to one prose rail row and a link out — the nearest real fact is the run's actual patch, currently shown only on the solution-workflow screen. | `features/findings/finding-page.tsx` |
| 4 | L | componentry | **[BLOCKED]** The reference's three footer CTAs are mutations — 'Apply Fix & Deploy', 'Dismiss', 'Escalate to On-Call' — and the console API is read-only by test: dismissal is a CLI action the console only reads, no on-call integration exists, and nothing may reach a PR or deploy from a click here. |  |
| 3 | S | componentry | **[BLOCKED]** The reference's 'Overall Confidence — 4/4 Passing' green summary bar is a composite confidence scalar averaging distinct checks into one figure, which the console refuses; individual gate results are the permitted form. |  |
| 3 | S | colour | The reference tints status surfaces — critical rows on #541c15 with #fa8880 ink, the warning badge on #4a2900 with #f2af48, added rows on status-good-bg — and ours paints no tinted status surface anywhere on the screen. |  |
| 3 | M | hierarchy | Reference pane headers are 12px uppercase furniture labels on tinted strips (EVIDENCE, AI REMEDIATION) that recede beneath the content; ours are 18px+ sentence-case section titles each trailing a one-to-two-sentence caption, so the furniture outweighs the evidence. | `components/metric-panel.tsx` |
| 3 | M | density | The reference compresses subject facts (badge, id, endpoint, time) into an ~80px header row; our rail gives each fact its own row and several rows a full sentence ('Open — nobody has dismissed this', 'the checkpointer holds no run for this finding'), roughly 550px tall. | `features/findings/finding-page.tsx` |
| 3 | M | componentry | **[DATA-SUBSTITUTION]** The reference shows verification as paired result tiles (Unit Tests — Pass, Type Check — Pass, each with a check icon); ours surfaces no verification results on this screen — the real analogues are the pipeline's own recorded gates, tsc and the customer's CI, on the remediation run. | `features/findings/finding-page.tsx` |
| 2 | S | structure | Our 'What the call site touches' (argument-key chips, response fields) and 'Provenance' sections exist only on our side — the reference has no surface for the binding's touched surface or for provenance at all. | `features/findings/finding-page.tsx` |
| 2 | S | componentry | **[DATA-SUBSTITUTION]** The reference's remediation pane header carries an 'Analyzing' state badge (warning tint, icon); ours states run standing as a prose sentence in the rail — the real analogue is the run-standing closed vocabulary (in-flight, opened, abandoned, reported) rendered as a badge. | `features/findings/finding-page.tsx` |
| 2 | S | componentry | **[DATA-SUBSTITUTION]** The reference's header meta row shows endpoint and a '2 mins ago' relative time with icons; ours shows no timestamp anywhere on the screen — the payload holds only indexed_at, which B122 refused as a stand-in for detection time, so the honest mapping is an 'indexed at' fact labelled as such, never recency. | `features/findings/finding-page.tsx` |
| 2 | S | motion | **[BLOCKED]** The reference's Analyzing badge spins its icon perpetually (animate-spin) — a liveness pulse the console refuses; the standing word from the run record is the permitted form. |  |
| 2 | M | structure | Ours carries an 11-row label/value facts rail (identifier, severity, repository, call site, vendor, operation, symbol, SDK version, rung, remediation, standing) that has no counterpart in the reference, which folds identity facts into an ~80px header and shows nothing else. | `components/fact-list.tsx` |
| 2 | M | colour | The reference layers surfaces — tinted header strips (surface-container-low #1b1c1b) banding each pane on a sheet (#1b1d1c), with code panes dropped to the darker background (#131413) — where ours draws flat single-level cards on a near-black page with no banded headers. |  |
| 1 | S | typography | **[inferred]** The reference PNG's trace, diff and code panes render in a serif because its mono stack is a quoted single string ('"ui-monospace, monospace"') that falls back to the default serif — ours renders true monospace, so ours already matches the evident intent, not the pixels. |  |
| 1 | S | motion | **[inferred]** The reference sheet declares a 300ms translate-x entrance over a blurred backdrop, implying an animated slide-in; our page navigation cuts statically. |  |
| 1 | S | motion | **[inferred]** Reference buttons carry a 1px active press displacement and hover surface shifts, and the primary CTA a static green glow suggesting an emphasized affordance; our rail button shows a plain outline with no visible hover/press affordances in the still. |  |

### `workflow` vs `ai_driven_incident_resolution_workflow` — 26 findings

| Imp | Eff | Axis | Difference | File |
|---|---|---|---|---|
| 5 | M | hierarchy | **[DATA-SUBSTITUTION]** Reference leads with the object under remediation — a red 'Breaking Change Detected' badge (icon + word, closed-vocabulary shape we permit) beside 'Incident #7742' — while ours leads with the generic screen name 'Solution workflow' and buries the finding hash in a small rail row; map the fictional incident number and severity to the real finding id plus its detector/run-outcome badge. | `features/workflows/workflow-page.tsx` |
| 5 | L | structure | Reference presents the workflow as a slide-over sheet (max-width 1200px) floating over a dimmed, blurred backdrop of the console; ours renders it as a full console route with persistent sidebar nav, breadcrumb topbar, and no close affordance. | `features/workflows/workflow-page.tsx` |
| 5 | L | structure | Reference splits the body into two fixed panes — evidence timeline left (~5/12) and remediation feed right (~7/12), separated by a vertical border, each with its own header strip; ours is a narrow left fact rail plus one content column with no evidence-vs-remediation split. | `features/workflows/workflow-page.tsx` |
| 5 | L | componentry | **[inferred]** Reference draws the run as a vertical timeline — circular icon nodes on a 2px connecting spine, timestamped stage titles, terminal stage ringed and titled in green — while our capture shows no timeline at all and our populated node sequence is prose entries without an icon-node spine (populated form read from code, not pixels). | `features/workflows/node-sequence.tsx` |
| 4 | M | structure | **[BLOCKED]** Reference pins a footer action bar (Dismiss left; Escalate to On-Call and a solid-green glowing Apply Fix & Deploy right); ours has none because Sync's API is read-only and the console does not mutate runs — our ACTIONS prose block explaining that refusal is the deliberate replacement. |  |
| 4 | M | density | Reference puts concrete evidence before the fold — trace spans with latencies, a schema diff, a root-cause card, fix code, and verification tiles — where ours spends the fold on ten label rows of absence plus a ~180-word prose paragraph, and even our populated view opens with a narrative prose entry ('What arrived') rather than evidence cards. | `features/workflows/workflow-page.tsx` |
| 4 | M | componentry | **[DATA-SUBSTITUTION]** Reference's first evidence card is a trace waterfall — span rows with per-span millisecond durations and the failing span tinted critical with an inline error line — which ours lacks entirely; per-node elapsed time is not on the checkpoint payload (B123), so map to the telemetry evidence a node actually recorded and drop the invented millisecond figures. |  |
| 4 | M | componentry | **[DATA-SUBSTITUTION]** Reference renders a line-numbered diff card — file path in the header bar, removed row tinted critical, added row tinted good — and ours draws no diff componentry; the models/user.ts content is fictional but Sync holds real vendor spec diffs and generated patches to fill it. |  |
| 4 | M | componentry | **[DATA-SUBSTITUTION]** Reference's Proposed Fix card wraps a syntax-highlighted code pane in a filename title bar with a copy button, inserted lines carrying a green left border and tinted background; nothing comparable is visible on ours — map the fictional Zod fix to the run's real generated patch. | `features/workflows/code-block.tsx` |
| 4 | M | componentry | **[DATA-SUBSTITUTION]** Reference shows a two-up grid of verification tiles ('Unit Tests — Passed — 142/142', 'Type Check — Passed — tsc --noEmit') with check icons; ours shows no verification tiles — Sync genuinely runs tsc and the customer's CI, so the tiles can carry the real verification chain, but the 142/142 count is fictional. |  |
| 4 | M | colour | Reference is green-accented throughout — primary #65eaa8 family on icons, the terminal timeline node, added diff lines, and status triads (critical #fa8880/#541c15, warning #f2af48/#4a2900, good #85e0ba/#00311d) — while our visible screen is entirely neutral monochrome with no accent or status colour anywhere; badge-scoped status colour with icon and word is permitted, wholesale accent adoption is a DESIGN.md decision. |  |
| 3 | S | structure | Reference's header is a two-line identity block — badge + title row, then an icon meta row — inside a bordered header strip with a close button; ours is a bare h1 sitting in the page flow with nothing beneath it. | `features/workflows/workflow-page.tsx` |
| 3 | S | hierarchy | Reference gives each pane an uppercase letter-spaced 12px section header with a leading icon ('EVIDENCE TIMELINE', 'AI REMEDIATION FEED') that outranks card titles; our visible region has no pane-level headers — sections start directly at card or fact-label register. |  |
| 3 | S | componentry | **[BLOCKED]** Reference's 'Overall Agent Confidence' row with a green progress bar at 98% is a composite scored judgement — the exact scalar this console has refused three times on the record; it does not map to any real fact and must not be built. |  |
| 3 | S | componentry | Reference's header carries an amber 'Agent Active' pill with a dot; as a static badge the shape maps to our run-standing vocabulary and ours shows no standing badge in the header at all — but the pill as drawn (breathing pulse) is covered by the blocked motion finding. |  |
| 3 | S | componentry | **[BLOCKED]** Reference's dashed-border 'Implementation Status' card with a spinning icon and 'Awaiting user approval to apply fix and generate PR...' implies an approval flow the read-only console cannot host; the waiting-on fact itself is real and ours states it in prose via the reply box instead of a card. | `features/workflows/reply-box.tsx` |
| 3 | S | componentry | **[DATA-SUBSTITUTION]** Reference's header meta row sets 'Endpoint: /v1/users/profile' and '2 mins ago' as icon-led mono chips under the title; ours has no meta row — map the fictional endpoint to the finding's real call site/operation and the age to checkpoint timestamps. | `features/workflows/run-fact-rail.tsx` |
| 3 | S | motion | **[BLOCKED]** The Agent Active pill's visible glow rings come from a pulse-breathing box-shadow keyframe — a liveness pulse claiming the agent is working right now, which the checkpointer cannot attest and the console bans. |  |
| 3 | M | typography | Reference sets every machine fact — timestamps, span durations, file paths, diff lines, endpoint — in a 10-12px data-mono register (the prototype's mono stack is broken, quoting 'ui-monospace, monospace' as one family so the PNG falls back to serif, but mono is the stated intent), while ours uses mono only for the finding hash and repo identity and sets values like 'no run for this finding' in body sans. | `features/workflows/run-fact-rail.tsx` |
| 2 | S | density | Reference evidence rows are compact 24px mono rows packed inside bordered cards; our fact-rail rows run roughly 36px with looser padding and a rule between each, so fewer facts fit per screen-height. | `features/workflows/run-fact-rail.tsx` |
| 2 | S | colour | Reference surfaces carry a green-tinted cast — outline-variant #3d4a41 borders on #1f201f cards over #131413 — where ours uses cooler neutral borders over a near-black page, so the two token sheets disagree on surface and border hue. |  |
| 2 | S | typography | Reference titles the sheet at 18px Manrope section-header with 12px/500 uppercase furniture around it, while our h1 'Solution workflow' renders near 28px — larger than anything in the reference frame (deliberate per CI-W622, but visibly a different scale relationship). |  |
| 2 | S | motion | **[BLOCKED]** The Implementation Status card's sync icon carries animate-spin — motion claiming execution-in-progress, which our node-standing rule ('nothing here says a node is executing') refuses. |  |
| 2 | S | motion | **[inferred]** The sheet markup declares a translate-x slide-in transition and hover/active transitions on buttons, implying an animated drawer entrance our static page lacks; entrance motion claims no data and is not blocked, only unbuilt. |  |
| 1 | S | structure | Ours carries a status band at the bottom of the frame stating which nothing it is ('the checkpointer holds no run for this finding'); the reference has no status band anywhere — a reverse difference we keep by design. | `layouts/status-band.tsx` |
| 1 | S | componentry | Reference decorates the Proposed Fix card with a blurred green glow orb in the corner (bg-primary/5 blur-3xl); ours has no decorative surface treatment, and adopting it would require a DESIGN.md ruling since inline alpha composites are banned at call sites. |  |

### `solutions` vs `remediation_ci_cd_policy` — 25 findings

| Imp | Eff | Axis | Difference | File |
|---|---|---|---|---|
| 5 | L | structure | **[DATA-SUBSTITUTION]** The reference's entire canvas is a remediation-policy configuration surface (Detection Thresholds card, Approval Workflows table, action rail) while ours is outcome analytics (KPI strip, Sankey, chart panels) — the page's content model differs wholesale, and the reference's policy values (2% drift, toggle states, workflow rows) are fictional whose nearest real facts are the attempt/outcome counts ours already renders. | `features/workflows/solutions-page.tsx` |
| 5 | L | componentry | The full-width 'Where remediation work stops' Sankey (~600px tall, six outcome branches) that dominates our canvas has no counterpart anywhere in the reference, whose mid-canvas is empty below the cards. | `features/workflows/solutions-page.tsx` |
| 4 | M | structure | **[DATA-SUBSTITUTION]** The reference top bar is a settings-section tab nav (General, Team, Billing, Remediation active with 2px primary underline, Webhooks) while ours carries breadcrumbs, a Solutions/Corpus segmented control, mono repo identity, and a Ctrl-K jump hint — General/Team/Billing are sections our console does not have, so the nearest real sectioning is the existing screen tabs. | `layouts/app-frame.tsx` |
| 4 | M | structure | Ours opens with a four-tile KPI fact strip (pull requests opened, distinct findings, share of runs, newest) that the reference lacks entirely. | `components/kpi-strip.tsx` |
| 4 | M | componentry | Reference cards open with a tinted header strip (surface-container-low fill, bottom hairline, 16px leading icon plus 12px furniture label); our panels use a large bold inline title with info glyphs and body prose, with no header strip and no icon. | `components/metric-panel.tsx` |
| 4 | L | structure | The reference constrains content to a centered max-w-4xl two-column grid (2/3 settings column plus 1/3 right action rail); ours runs a single full-bleed column with no right rail. | `features/workflows/solutions-page.tsx` |
| 3 | S | hierarchy | The reference pairs its page title with a one-line ink-secondary subtitle ('Configure automated response behaviors and state machine guardrails.'); our 'Solutions' title stands alone with no descriptor line. | `features/workflows/solutions-page.tsx` |
| 3 | S | colour | Active nav treatment: the reference fills the active row with primary-container #45cd8e and on-primary-container #005333 ink, while ours tints the row #18271f with a #45cd8e edge bar and light green text. | `layouts/app-frame.tsx` |
| 3 | S | colour | Our Sankey greens sit off the token sheet: link fills sample at #1d5841/#1d5640 and the node bar at #199e70, matching no sheet value (nearest tokens: status-good-bg #00311d, on-primary-container #005333, tertiary-container #3dce8d, primary-container #45cd8e). | `features/workflows/solutions-page.tsx` |
| 3 | M | structure | **[DATA-SUBSTITUTION]** Sidebar IA differs: the reference has six flat icon+label items (Dashboard, Integrations, Self-Healing Queue, Telemetry/Traces, API Keys, Settings) while ours has nine items grouped under prose stage headers (Index/Signal/Observe/Detect/Remediate) with description sentences and a footer account row — 'Self-Healing Queue' implies healed-count framing we do not measure (maps to Remediate: Runs/Solutions) and 'API Keys' implies held credentials we never store. | `layouts/app-frame.tsx` |
| 3 | M | componentry | **[BLOCKED]** The Drift Tolerance Trigger range slider with mono '> 2%' value chip configures a configuration-drift percentage Sync does not measure, so carrying it would fabricate a metric. |  |
| 3 | M | componentry | **[DATA-SUBSTITUTION]** The CI/CD Binding card (boxed repo tile, 'GitHub Actions / Connected to sync-ops/core-infra', outlined Manage Connection button) is absent in ours; the fictional repo maps to the real bound repository github.com/stroland02/demo-v1 and the customer-CI verification chain we already record. |  |
| 3 | M | componentry | **[DATA-SUBSTITUTION]** The Save Configuration card with a full-width filled-primary CTA ('Apply Policy Changes', #65eaa8 fill, dark on-primary ink) is absent in ours, and its copy about taking effect 'across all connected agents' describes a fleet-push behavior we do not have. |  |
| 3 | L | componentry | **[BLOCKED]** The reference's Approval Workflows table (severity rows with per-row action dropdowns) is absent in ours, and its 'Auto-Apply (Zero Touch)' options would let a fix land without the verified-PR pipeline, which the product forbids — the control set cannot be carried as designed. |  |
| 2 | S | componentry | Severity badge pills (rounded-full, status-critical/warning/good background plus matching ink and a 14px leading icon) appear nowhere on our screen even though severity is a real closed vocabulary in api/types.ts; our only visible chip (ALL WORKSPACES) is plain outlined text. |  |
| 2 | S | componentry | **[DATA-SUBSTITUTION]** The reference top bar's right cluster (help icon button and 32px circular photo avatar) is missing in ours, whose identity lives in the sidebar footer as 'stroland02' — the stock avatar photo would map to the real git identity, not an image. | `layouts/app-frame.tsx` |
| 2 | S | hierarchy | Title scale differs: the reference page header renders at the quiet 18px Manrope section scale while our 'Solutions' renders visibly larger (~24px+), out-scaling the reference's lead (a deliberate CI-W622 choice, but still a divergence from the target). | `features/workflows/solutions-page.tsx` |
| 2 | S | componentry | The brand lockup differs: the reference sets 'Sync' in primary green with an 'API Automation' subtitle and a bordered 32px icon tile, while ours is a white wordmark with a bare glyph and no subtitle. | `layouts/app-frame.tsx` |
| 2 | S | colour | Our chart-legend swatches drift from the status tokens: amber samples #e8c15a vs status-warning-ink #f2af48, orange #f78a4e vs status-serious-ink #fd9565, and cyan #5bd6e0 has no sheet counterpart at all (red #fa8880 and green #3ecf8e do match). |  |
| 2 | S | colour | Chrome surfaces: the reference sets the top bar on surface-container #1f201f and the sidebar on surface-container-low #1b1c1b, both separated by outline-variant #3d4a41 borders, while ours renders both chrome bars on the base background #131413 with no tonal step from the canvas. | `layouts/app-frame.tsx` |
| 2 | S | typography | Furniture labels differ in case and weight: ours renders tile and scope labels uppercase at weight 600 ('PULL REQUESTS OPENED', 'ALL WORKSPACES') while the reference furniture style is mixed-case 12px weight 500 with 0.025em tracking throughout. | `index.css` |
| 2 | M | componentry | **[BLOCKED]** The 'Aggressive Polling — increase check frequency during active incidents' toggle presumes an incident/liveness state our console deliberately does not model and has no real backing. |  |
| 2 | M | density | The reference completes within one viewport with generous empty canvas below its cards, while ours continues past the fold into two further chart panels whose legends are cut at the viewport edge. |  |
| 1 | S | typography | Face split differs: the reference reserves Manrope for headers and sets body/meta text in Inter 13px weight 450, while our stack lists Manrope first for all text so body copy renders in the display face with no header/body contrast. | `index.css` |
| 1 | S | motion | **[inferred]** The reference markup carries press micro-interactions (active:translate-y-[1px] on nav items and buttons) and an animated toggle transition, and nothing on our screen suggests any press displacement or control animation. |  |

### `runs` vs `infrastructure_logs` — 30 findings

| Imp | Eff | Axis | Difference | File |
|---|---|---|---|---|
| 5 | M | density | Reference log rows are single-line, ~36px tall in 13px mono showing 8+ events; our run rows are ~110px tall because the FINDING column is so narrow that finding names and checkpoint hashes wrap onto five lines, leaving 3.5 rows visible. | `features/fleet/runs-table.tsx` |
| 5 | L | structure | Reference splits the screen master-detail with a 400px right-hand 'Log Event Detail' pane (summary card plus raw payload) opened from the selected row; our runs screen is a single full-width table with no in-place detail pane. |  |
| 4 | S | componentry | Reference renders the categorical state as tinted uppercase chips (INFO/WARN/ERROR on 20%-alpha colour fields); our OUTCOME column is plain unstyled sans text ('opened', 'in flight') — a closed-vocabulary badge here is explicitly permitted. | `features/workflows/run-outcome.tsx` |
| 4 | M | componentry | **[DATA-SUBSTITUTION]** Reference tops the stream with a histogram strip of event volume over time, bars coloured by severity with a total-events count; ours has no time-distribution visual — the nearest real fact is checkpoint activity over time bucketed by outcome, since '124k Events' is fictional. |  |
| 4 | M | density | Reference puts the first data row ~230px from the top under compact chrome; ours spends ~460px on page title, explainer sentence, four stat tiles, and two caption paragraphs before the first run row. | `features/runs/runs-page.tsx` |
| 4 | L | componentry | Reference narrows via a wide SQL-like query input in JetBrains Mono with a terminal icon plus a Filters button; our only narrowing control is a fixed list of five preset disposition buttons. | `components/filter-rail.tsx` |
| 4 | L | structure | Ours dedicates a ~270px left facet panel ('NARROW THE RUNS') with its own explanatory paragraph inside the content area; the reference has no in-content filter column and gives that width to data. | `components/filter-rail.tsx` |
| 3 | S | colour | Reference rank-colours severity throughout the table — error row message in #FA4B4B, badges in #2081E2/#F5A623/#FA4B4B; our visible rows are entirely monochrome with no colour separating opened, in-flight, and abandoned outcomes. | `features/fleet/runs-table.tsx` |
| 3 | S | density | Our OUTCOME column stretches across ~500px of dead space between 'opened' and LAST CHECKPOINT; the reference gives its flex width to the data-bearing message column so no column carries empty span. | `features/fleet/runs-table.tsx` |
| 3 | S | density | Reference opens every row with an absolute millisecond-precision timestamp in secondary mono; ours shows only a relative '118h ago', hiding the real checkpoint times we do record. | `features/fleet/runs-table.tsx` |
| 3 | S | density | Our sidebar interleaves prose stage descriptions ('downloads vendor specs and diffs them') between nav groups; the reference nav is a compact icon-plus-label list with no prose. | `layouts/app-frame.tsx` |
| 3 | S | typography | Reference table cells are uniformly 13px JetBrains Mono including the message; our rows mix mono identifiers with larger sans cells ('opened', '—'), so the stream does not read as one code surface. | `features/fleet/runs-table.tsx` |
| 3 | M | structure | Ours leads the content with a four-tile stat row (RUNS RECORDED / OPENED A PULL REQUEST / ABANDONED / NO OUTCOME RECORDED); the reference reserves that band for the filter toolbar and histogram and has no KPI tiles. | `features/runs/runs-kpis.tsx` |
| 3 | M | hierarchy | Reference has no page title at all — the filter toolbar and data lead the screen; ours leads with a large 'Runs' headline plus a full-sentence subtitle (deliberate under our CI-W622 screen-names-itself convention, so reversing it conflicts with a landed rule). | `features/runs/runs-page.tsx` |
| 3 | M | componentry | Reference includes a time-range picker button ('Last 1h' with calendar icon and dropdown) beside the query input; ours has no time scoping at all. |  |
| 3 | M | structure | Reference runs the table edge-to-edge under the toolbar with the chrome as full-bleed bands; our content sits as inset boxed cards with wide gutters either side. | `layouts/screen-frame.tsx` |
| 3 | L | componentry | Reference's detail pane carries a raw payload viewer with four-colour JSON syntax highlighting (keys #ffa072, strings #51df9c, numbers #2081E2, booleans #F5A623) and a Copy control; ours exposes no raw-record view for a run checkpoint. |  |
| 2 | S | typography | Reference column headers are 11px JetBrains Mono uppercase with 0.05em tracking on a card surface; ours are larger sans-serif uppercase, and one wraps to two lines ('NODE THE GRAPH OWES'). | `features/fleet/runs-table.tsx` |
| 2 | S | colour | Reference sidebar sits on its own surface (#1C1C1C, surface-main) separated from the #131313 canvas by a #232323 border; our sidebar is the same colour as the canvas (sampled 19,20,19) so the two planes do not separate. | `layouts/app-frame.tsx` |
| 2 | S | colour | Reference marks the active nav item with a 2px primary-green LEFT border, #353535 fill, and green label text; ours uses a green bar on the RIGHT edge, a green-tinted fill, and white label text. | `layouts/app-frame.tsx` |
| 2 | S | componentry | Reference has a persistent search input field with an inset 'Cmd+K' keycap chip and 2px corner radius; ours is a fully-rounded pill button reading 'Jump to a destination Ctrl K'. | `layouts/command-palette.tsx` |
| 2 | S | structure | **[DATA-SUBSTITUTION]** Reference's global header carries product-level nav links (Environments, API Docs, Team) plus bell/gear/avatar; ours carries breadcrumbs — the reference sections are fictional and their nearest real equivalents are the repository/vendor scopes our breadcrumb already names. |  |
| 2 | S | structure | Ours repeats the repository identity ('github.com/stroland02/demo-v1 · local dev · git: stroland02') as large mono text in the header centre; the reference header has no such duplicate identity block. | `layouts/breadcrumbs.tsx` |
| 2 | M | componentry | **[DATA-SUBSTITUTION]** Reference offers a pause control on the stream (live-tail affordance); ours has none — the nearest real behaviour would be pausing checkpoint auto-refresh, since we have no streaming log tail. |  |
| 2 | M | componentry | Reference offers a download/export control on the table; ours has no export affordance. |  |
| 2 | M | motion | **[inferred]** Reference code declares row hover surface shifts, a highlighted selected-row state feeding the pane, a 300ms slide-out transform on the detail pane, and active:scale-95 button presses; our static shot shows no hover/selection affordances on rows. |  |
| 1 | S | colour | **[inferred]** Reference fades its three oldest rows to 70% opacity as a recency gradient; our rows are uniform brightness regardless of checkpoint age. |  |
| 1 | S | componentry | **[DATA-SUBSTITUTION]** Reference has a green 'Deploy' primary CTA in the header; ours has none, and the action is fictional for Sync with no real analogue to map to. |  |
| 1 | S | componentry | **[DATA-SUBSTITUTION]** Reference shows a photographic user avatar in the header; ours shows the real account name 'stroland02' in the sidebar footer — the avatar portrait is fictional persona content. |  |
| 1 | S | typography | **[DATA-SUBSTITUTION]** Reference wordmark pairs green 'Sync' in Manrope with an 'API AUTOMATION' mono sub-label; ours is the logo mark plus 'Sync' in white with no sub-label — the tagline is fictional branding. |  |

### `graph` vs `code_graph_dependency_explorer` — 24 findings

| Imp | Eff | Axis | Difference | File |
|---|---|---|---|---|
| 5 | L | structure | **[DATA-SUBSTITUTION]** Reference docks a 400px Call Site Inspector on the right (status badge, call-site title, last-indexed provenance, LOCATION card, syntax-highlighted code pane with the drifted lines outlined, and a remediation CTA); our graph screen has no detail panel at all — selecting a node surfaces nothing visible. | `features/index-graph/index-graph-page.tsx` |
| 5 | L | componentry | Reference draws every node as a readable card — brand-color icon square, name in UI type, and a mono operation/path line (POST /v1/charges, src/payments/main.py) inside a bordered rounded tile; ours renders abstract dots, rings, and squares with tiny detached labels that identify almost nothing at a glance. | `features/index-graph/force-map.tsx` |
| 4 | M | colour | Reference is keyed to the green primary #65eaa8 (logo, active nav pill, active tab underline, CTA fill, service-node border, inspector file path) over green-tinted surfaces and #3d4a41 borders; ours has no green anywhere — the chrome is white-on-near-black with neutral borders, and the only saturated hue is vendor blue, so the screen reads as a different product. |  |
| 4 | M | componentry | **[DATA-SUBSTITUTION]** Reference vendor cards carry a per-node status badge from a closed vocabulary (green check = conforming, orange healing = drifting, with the drifting card's whole surface tinted warning); our nodes carry no state marker of any kind — a drifting binding looks identical to a healthy one. | `features/index-graph/force-map.tsx` |
| 4 | M | structure | Reference fits the whole screen in the viewport — the canvas is a bounded, bordered, rounded panel that flexes to fill remaining height; ours is a page-scrolling layout where the anthropic and openai clusters fall below the fold and a scrollbar appears. | `features/index-graph/index-graph-page.tsx` |
| 3 | S | componentry | Reference places Filter and Re-index buttons right-aligned on the page-header line; ours has neither a graph filter nor a re-index affordance on this screen. | `features/index-graph/index-graph-page.tsx` |
| 3 | S | componentry | Reference marks the current nav section with a filled primary-container pill (dark text on green); our sidebar shows no visible active state for the screen being viewed. | `layouts/app-frame.tsx` |
| 3 | S | componentry | Reference canvas sits on a 60px grid backdrop inside a bordered rounded frame, giving it a workbench feel; ours floats nodes in an unframed flat void with no grid. | `features/index-graph/force-map.tsx` |
| 3 | M | hierarchy | **[DATA-SUBSTITUTION]** Ours spends the top ~180px on a four-tile KPI band before the graph appears; reference compresses those facts into one meta line under the title ('Found 43 call sites watching 12 external APIs via uv run sync index' — map to our real 40 call sites / 3 integrations and the real index command) and gives the reclaimed vertical to the canvas. | `features/repositories/topology-kpis.tsx` |
| 3 | M | componentry | Operation labels in ours are clipped behind neighboring node circles ('P…aymentIntents', 'G…ccountsAccount' half-hidden) and most file dots are unlabeled; every node label in the reference is fully legible. | `features/index-graph/force-map.tsx` |
| 3 | M | colour | **[DATA-SUBSTITUTION]** Reference edges are 2px and coloured by state (primary green for conforming paths, warning orange for the drifting one); ours draws all 40+ edges as identical hairline light gray. | `features/index-graph/force-map.tsx` |
| 2 | S | componentry | Reference has an always-visible inline search input with magnifier icon and 'Search call sites...' placeholder in the top bar; ours offers only a 'Jump to a destination Ctrl K' button that opens a palette. | `layouts/command-palette.tsx` |
| 2 | S | componentry | Reference floats a compact vertical +/- zoom stack inside the canvas bottom-right corner; ours puts labeled text buttons (Zoom in / Zoom out / Fit) plus a '44 nodes · 87% · scroll to zoom, drag to pan' status line in a toolbar row above the canvas. | `features/index-graph/force-map.tsx` |
| 2 | S | componentry | **[DATA-SUBSTITUTION]** Reference top bar carries a filled-primary 'Deploy Agent' CTA (fictional — nearest real action is triggering a re-index or opening the remediation queue); our chrome has no primary CTA anywhere. |  |
| 2 | S | typography | Reference sets headers in Manrope with tight negative tracking (page title at the 18px section-header size); ours uses one geometric sans throughout with a larger ~24px page title and no face change between title and body. |  |
| 2 | S | typography | Reference renders all data values — node paths, endpoint lines, inspector location — in ui-monospace; our canvas labels (route.ts, stripe, operation names) are sans, with mono reserved only for the repo string in the top bar. | `features/index-graph/force-map.tsx` |
| 2 | S | density | Our sidebar interleaves full prose descriptor sentences under every stage label ('downloads vendor specs and diffs them'), roughly doubling nav height; reference nav is a terse icon+label list under a single uppercase group header. | `layouts/app-frame.tsx` |
| 2 | S | colour | Reference layers its dark surfaces — sidebar #1b1c1b and topbar #1f201f raised above the #131413 background with visible tinted borders; ours reads as one flat near-black plane with barely differentiated chrome. |  |
| 2 | S | motion | **[BLOCKED]** Reference's service node pulses (node-pulse keyframes, 2s opacity cycle with a green glow) to signal liveness; ours is static — and a liveness pulse is barred by our binding, so this stays un-adopted. |  |
| 2 | S | motion | **[BLOCKED]** Reference animates marching dashed strokes along the active edges (data-flow keyframes) implying live traffic streaming over the bindings; ours draws static edges — the animation reads as a liveness pulse and is barred, though the static dash/colour styling itself is not. |  |
| 2 | M | structure | **[DATA-SUBSTITUTION]** Reference top bar leads with Production/Staging environment tabs (fictional for us — our nearest real facts, repo, 'local dev' and git branch, are already shown in our top bar); ours leads with a breadcrumb trail plus scope switchers the reference lacks. | `layouts/app-frame.tsx` |
| 1 | S | componentry | **[DATA-SUBSTITUTION]** Reference top-right utility cluster has notification bell, help, and an avatar (notifications are fictional — nearest real fact is pending findings count); ours has no utility cluster, keeping account identity and Settings in the sidebar footer. |  |
| 1 | S | colour | Reference uses Stripe's brand indigo #635BFF for the vendor icon square; our stripe node square is a lighter generic blue. | `features/index-graph/force-map.tsx` |
| 1 | S | motion | **[BLOCKED]** Reference sweeps a green radar-style scanline down the canvas on a 4s loop (visible as a horizontal glow band); ours has none — pure liveness theater, barred by our binding. |  |

### `metrics` vs `integration_performance_explorer` — 32 findings

| Imp | Eff | Axis | Difference | File |
|---|---|---|---|---|
| 5 | S | colour | Our findings chart paints 'breaking' bands in green #199e70 (the token sheet's status-good family) and 'info' in orange #d95926 (the status-serious family), so severity reads inverted at a glance; the recorded Decision 5 forbids a danger ramp, so the fix is categorical hues that do not collide with status inks, not a red-for-breaking ramp. | `features/dashboards/findings-over-time-option.ts` |
| 4 | S | density | Each chart card carries five-plus sentences of explanatory prose above and below the plot, reading as documentation and pushing facts below the fold; reference cards are a one-line header plus content only. | `features/dashboards/findings-over-time-card.tsx` |
| 4 | M | hierarchy | Our page leads with the bare word 'Trends'; the reference leads with a full context header — icon tile, title, meta line beneath it, and right-aligned actions — before any content. | `features/dashboards/metrics-page.tsx` |
| 4 | M | colour | Our chrome is entirely neutral (logo glyph grey, nav plain, tabs white-outlined); the reference paints the logo, active nav pill, active tab underline and primary buttons in the primary green family (#65eaa8/#45cd8e) that our token sheet already defines but the screen never uses. | `layouts/app-frame.tsx` |
| 4 | L | componentry | **[DATA-SUBSTITUTION]** The reference's dominant pane is a vertical provenance timeline — icon nodes on a connector line, uppercase rung labels, right-aligned mono timestamps, one card per event — which our screen lacks entirely; its drift/auto-remediation narrative is fictional, so map rungs to real Finding, Solution and PR events from the pipeline. |  |
| 3 | S | density | Our sidebar interleaves prose descriptions under each stage heading ('reads the code', 'downloads vendor specs and diffs them'); reference rows are icon plus label only. | `lib/stage-pages.ts` |
| 3 | S | componentry | Our KPI row is one flush strip with hairline dividers and square corners; the reference renders four separated rounded-corner cards with visible borders, 16px gutters of page background between them, and a subtle shadow. | `components/kpi-strip.tsx` |
| 3 | S | hierarchy | **[DATA-SUBSTITUTION]** The reference accents its fourth KPI tile in primary green (label, figure, icon) to lead the row; our four tiles are uniformly neutral — the reference's cost-saved/errors-mitigated content is a healed-count metric we do not measure, so accent the nearest real fact such as changes published. | `features/dashboards/trends-kpis.tsx` |
| 3 | S | colour | The integration-changes chart assigns two near-identical greens to anthropic (#199e70) and stripe (#008300), and #008300 appears nowhere on the token sheet, so the dominant stacked area is unattributable at a glance. | `features/dashboards/changes-over-time-card.tsx` |
| 3 | M | componentry | **[DATA-SUBSTITUTION]** The reference embeds an inline mono diff pane (struck-through red removal, green addition) inside a timeline card; nothing on our screen renders a diff even though real oasdiff spec hunks exist to draw. |  |
| 3 | M | structure | Our sidebar is nine items grouped under five pipeline-stage headings; the reference is a flat six-item icon nav with no grouping. | `layouts/app-frame.tsx` |
| 3 | M | structure | The current screen has no sidebar anchor — Trends is reachable only through the top-bar pills and no sidebar item shows an active state; the reference always marks the live section with a filled primary pill in the sidebar. |  |
| 3 | M | componentry | Section tabs sit in our top bar as two boxed pills (Findings / Trends); the reference draws an underline tab row of five sections inside the content header below the title. | `layouts/screen-tabs.tsx` |
| 3 | M | componentry | **[DATA-SUBSTITUTION]** Reference tiles close with a colour-coded trend line (+12% green, +8ms amber, Stable neutral with trend glyphs); our tiles have no delta affordance — a vs-prior-day delta is computable from the real recorded series rather than the reference's fictional vs-last-hour figures. | `features/dashboards/trends-kpis.tsx` |
| 3 | M | componentry | **[BLOCKED]** The reference pins a green 'Healthy' composite status badge beside the page title; a composite health verdict is barred for our console — closed-vocabulary badges (severity, provenance) are the permitted form. |  |
| 3 | M | structure | **[DATA-SUBSTITUTION]** The reference top bar carries a Production/Staging environment switcher next to the logo; ours has none — we run one local-dev context, so the nearest real control is the workspace/branch context currently shown only as inline text. | `layouts/app-frame.tsx` |
| 3 | L | structure | **[DATA-SUBSTITUTION]** The reference top bar's right cluster is a primary action button plus bell, help and avatar; ours is a mono repo-identity string and a 'Jump to a destination' button — Deploy Agent and a notification feed have no real counterpart here, so map to the command palette and settings entry points we do have. | `layouts/app-frame.tsx` |
| 3 | L | componentry | **[DATA-SUBSTITUTION]** The reference right rail lists endpoints as METHOD badge + mono path + per-row figure, a panel our screen lacks; per-endpoint latency is not measured, so the nearest real fact is observed call counts per call site from telemetry. |  |
| 2 | S | componentry | **[BLOCKED]** The reference's Endpoint Health rows end in green/amber liveness dots — a per-row traffic light our console is barred from drawing. |  |
| 2 | S | typography | Our KPI labels are uppercase letter-spaced ('FINDINGS RECORDED'); reference furniture labels are mixed-case 12px medium ('Throughput'). | `components/kpi-strip.tsx` |
| 2 | S | typography | Reference figures carry their unit inline in smaller muted type ('4,281 req/min', '142 ms'); our figures are bare integers with all context exiled to the caption line below. | `features/dashboards/trends-kpis.tsx` |
| 2 | S | typography | Our --font-sans leads with Manrope for everything including body prose; the reference reserves Manrope for display/section/page headers and sets body, meta and furniture text in Inter. | `index.css` |
| 2 | M | structure | The reference's content grid is asymmetric (two-thirds main pane, one-third rail); ours is two equal-width chart columns. | `features/dashboards/metrics-page.tsx` |
| 2 | M | structure | Our breadcrumbs live in the top bar as slash-separated scope dropdowns with carets; the reference places plain chevron breadcrumbs inside the content header directly above the title. | `layouts/breadcrumbs.tsx` |
| 2 | L | componentry | **[DATA-SUBSTITUTION]** The reference header offers right-aligned actions (neutral Pause Sync, primary Force Sync); our screen offers no action anywhere — pause/force-sync semantics do not exist in our pipeline, whose nearest real action is run- or fetch-related. |  |
| 1 | S | colour | Our sidebar and top bar share the page background (#131413); the reference lifts chrome onto lighter surfaces — sidebar #1b1c1b (surface-container-low) and top bar #1f201f (surface-container) — each with a hairline border against the page. | `layouts/app-frame.tsx` |
| 1 | S | componentry | **[DATA-SUBSTITUTION]** The reference's Logs tab carries a rounded count pill ('12k'); our top-bar tabs carry no counts — the real findings count could ride the Findings pill. |  |
| 1 | S | componentry | Reference KPI label rows end in a small trailing metric glyph (speed, timer, check); our tile label rows have no icon. | `features/dashboards/trends-kpis.tsx` |
| 1 | S | componentry | **[DATA-SUBSTITUTION]** The reference sidebar footer is an org card — icon tile, org name, and a plan/region meta line; ours is a plain username row plus a Settings item — plan and region are fictional for us, so the meta line maps to the git identity and workspace we already display in the top bar. |  |
| 1 | S | componentry | Ours adds an info-hint glyph beside the 'Integration changes over time' heading; reference section headers carry no hint affordance. | `components/info-hint.tsx` |
| 1 | S | componentry | Our content edge shows the default light scrollbar; the reference styles slim 8px dark scrollbars (#343534 thumb on #131413 track). | `index.css` |
| 1 | S | motion | **[inferred]** Reference markup gives buttons and nav a 1px press translate and gives cards hover tints — including a primary glow overlay on the accent KPI tile — with no equivalent affordance evident on our screen. |  |

### `settings` vs `platform_settings` — 21 findings

| Imp | Eff | Axis | Difference | File |
|---|---|---|---|---|
| 5 | M | colour | The reference carries its green primary family (#65eaa8 accent, #45cd8e active-nav container, primary-tinted links and CTA) across logo tile, active nav, Staging underline, and 'Add Variable' link; our visible screen is entirely achromatic gray-on-black with no accent anywhere. |  |
| 4 | L | structure | The reference organizes settings as a left vertical rail (narrow tab column with an active row carrying a primary-coloured chevron_right drill-in affordance) beside a wide content column; ours runs a single horizontal tab strip (Setup…About) above full-width content. | `features/settings/settings-page.tsx` |
| 3 | S | colour | Reference active sidebar item is a filled primary-container pill (#45cd8e) with dark on-primary-container text and a filled icon; our active 'Settings' row is a neutral gray highlight with white text. | `layouts/app-frame.tsx` |
| 3 | M | componentry | Reference sections are framed cards with a tinted header band (section title + one-line muted subtitle on surface-container-lowest/50) and, for editable sections, a tinted footer band with a right-aligned action button; our 'Codebase & Context Settings' and 'Monitored Codebases' are bare headings sitting directly on the page background with no card chrome or footer band. | `features/settings/codebases-settings-panel.tsx` |
| 3 | M | density | The reference fills the fold with compact controls (32px inputs, ~40px table rows, one-line helper texts); ours spends the equivalent area on multi-paragraph explanatory prose inside the Project Context card, so fewer distinct facts and zero controls land before the fold. | `features/settings/codebases-settings-panel.tsx` |
| 3 | M | componentry | **[DATA-SUBSTITUTION]** Reference chrome shows an environment switcher as two top-bar tabs (Production / Staging, active tab green-underlined); our real environment fact is the plain '· local dev ·' text fragment in the top bar — the reference's two-environment tab set is fictional and maps to our single measured environment indicator. | `layouts/app-frame.tsx` |
| 3 | L | componentry | **[DATA-SUBSTITUTION]** Reference's General tab is editable — text input, prefixed slug input, select, and a Save Changes flow — while our visible tab is entirely read-only; the reference's Organization Name / Platform Slug fields are fictional and map to our real workspace identity (stroland02, repo URL) and to the genuinely editable settings that live on our Model/Setup tabs. | `features/settings/codebases-settings-panel.tsx` |
| 2 | S | componentry | Reference status chips are tinted fills with an icon and status ink ('Global Sync Active': status-good-bg #00311d, check_circle icon, #85e0ba ink); our equivalents (ACTIVE, READ-ONLY: TRACKED IN GIT, 46 OPEN FINDINGS) are outline-only pills with no fill and no icon. | `features/settings/setting-card.tsx` |
| 2 | S | componentry | **[DATA-SUBSTITUTION]** The reference asserts a global liveness chip ('Global Sync Active'); the nearest real fact we measure is the GitHub connection state on our Connection tab, which can carry a closed-vocabulary status badge — a pulsing/composite liveness indicator itself would be blocked, but a state badge is the legitimate mapping. |  |
| 2 | S | componentry | Reference contains its table inside a bordered rounded container within the card, with a tinted sentence-case header row; our Monitored Codebases table sits directly on the page with an uppercase letterspaced header band and no containing border. | `features/settings/codebases-settings-panel.tsx` |
| 2 | S | hierarchy | Reference pairs the page title with a one-line muted description directly beneath it; our 'Settings' title stands alone with no descriptive subline. | `features/settings/settings-page.tsx` |
| 2 | S | typography | Reference labels, table headers, and badges are 12px sentence-case (meta/furniture scale, no uppercase transform); ours renders table headers and badge text as uppercase letterspaced micro-caps (REPOSITORY, ATTACHED VENDORS, SOURCE OF TRUTH…). |  |
| 2 | S | structure | Reference centers its content at max-width 1200px with symmetric margins; our content column is left-anchored and stretches noticeably wider. | `features/settings/settings-page.tsx` |
| 2 | S | componentry | **[DATA-SUBSTITUTION]** Reference places a filled-primary 'Deploy Agent' CTA in the top bar; ours has no primary CTA in the chrome — the action is fictional (Sync has no deployable agent) with no real global action to map, so only the absence of any primary-emphasis element in the chrome is actionable. |  |
| 2 | M | componentry | **[DATA-SUBSTITUTION]** Reference has a contained key/value data table (Key / Value / Actions with '+ Add Variable' inline add); the SYNC_RETRY_LIMIT/SYNC_TIMEOUT_MS env-var store is fictional — the console intentionally never writes config (our own card says context is Git-only) — so this maps to displaying real key/value facts we already hold, such as analysis scope and lockfile resolution, in the same contained-table grammar. |  |
| 2 | M | typography | Reference reserves monospace for values only (slug, env-var keys/values at 12px) with headers in Manrope over an Inter body; ours runs monospace prominently and at larger sizes — the top-bar repo identity, table repo links, vendor chips, and badge text — and appears to use a single sans family for all headers. |  |
| 2 | M | structure | Ours inserts a 'Target codebase' dropdown row and a three-pill repository filter row (All repositories / With active remediations / Clean repositories) between title and content; the reference page has no scoping or filter controls at all — scope lives in its chrome. | `features/settings/settings-page.tsx` |
| 2 | M | structure | **[DATA-SUBSTITUTION]** Reference sidebar is a flat six-item icon+label list with the product subtitle 'API Automation' under the logo and Settings inside the main nav; ours interleaves lowercase stage-description prose lines between grouped nav items and relocates Settings and the account chip to a sidebar footer — reference nav labels (Dashboard, Self-Healing Queue) are fictional and map to our real pipeline IA. | `layouts/app-frame.tsx` |
| 2 | M | componentry | **[DATA-SUBSTITUTION]** Reference top bar carries a persistent visible search input ('Search resources…') plus a bell/help/avatar cluster on the right; ours exposes search only as the 'Jump to a destination Ctrl K' pill and has no icon cluster — the notification bell is fictional (no notifications feature) while the avatar maps to our real stroland02 account chip. | `layouts/app-frame.tsx` |
| 1 | S | componentry | **[DATA-SUBSTITUTION]** Reference nav tabs carry inline count badges ('2 Active' on Webhooks); our settings tab strip shows no counts — real per-tab counts exist (e.g. adapters, monitored codebases) and could substitute for the fictional webhook count. | `features/settings/settings-page.tsx` |
| 1 | S | motion | **[inferred]** Reference markup reveals table row actions only on hover (opacity-0 to group-hover:opacity-100 edit buttons) and gives buttons a 1px active press translate; our visible tables and buttons show no hover-revealed actions or press affordance. |  |

