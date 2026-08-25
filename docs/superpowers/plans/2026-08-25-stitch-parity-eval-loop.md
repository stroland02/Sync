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
| 1 | 2026-08-25 | all 13 | — | — | — |
