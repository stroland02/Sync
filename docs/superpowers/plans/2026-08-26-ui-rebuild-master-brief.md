# The UI rebuild — master brief

**Read this first in any new session doing console work.** It carries every ruling the owner has
given on how the console should look, what to build it from, and in what order. It exists because
the conversation that produced these rulings is being cleared; nothing here should require the
transcript.

Companions: `2026-08-25-stitch-parity-eval-loop.md` (the loop, the 351 findings, the coverage map),
`docs/superpowers/specs/2026-08-25-stitch-rebuild-specs.md` (the per-screen implementation specs).

## 1. The objective, in the owner's words

The most **sleek, modern, futuristic** UI for self-maintaining API integrations. Attractive enough
to engage a developer on sight; organised enough that it never imposes cognitive overload. Advanced
UI/UX — drawers, popovers, overlays, living motion — used because they reduce load, not because
they impress.

Two failure modes the owner has named explicitly and neither is acceptable:
- **"Everything looks exactly the same."** Structural conformance is not the deliverable.
- **"Too much information."** A sentence that restates what the chrome already says is noise.

## 2. Authority order

1. **The Stitch reference set** — `docs/stitch_sync_developer_console/`, 24 screens with rendered
   `code.html` and `screen.png`, plus the owner's technical specification and CSS token sheet.
   **This is the primary visual authority.** Open the still for the screen you are touching before
   you write a line.
2. **Supabase** — `docs/supabase-reference/` (356 screens, local, gitignored: 126MB, mined not
   read per screen) and the **Mobbin Pro** connector (`search_screens`, `search_sections`,
   `search_flows`). Our primitives are already vendored from Supabase, so its patterns and our
   components are the same material.
3. **`DESIGN.md`** — the token contract. Every value arrives with contrast arithmetic against the
   5.05:1 floor. Dark-only.
4. **`web/CLAUDE.md`** — what a screen may claim.

**Visual reference is unrestricted as of 2026-08-26** (`interface-originality.md`, amended). Any
source may inform how a screen looks. Build the most ambitious version.

## 3. What is still refused, and why it is not a creative limit

The owner asked for every limitation on UI creativity to be removed. These four are not that —
they are the product's argument, and each was reaffirmed rather than relaxed:

| Refusal | Why it is not an aesthetic limit |
|---|---|
| No composite score, health figure, traffic light or liveness pulse | A scalar averaging *we could not check* with *we checked and it passed* collapses the distinction the product exists to make. Rejected three times on the record. **A badge from a closed vocabulary is permitted and looks identical to the reference's chips** — this is the form to reach for. |
| Absence is not zero; staleness is not liveness; never-measured is not nothing-here | Every empty state says *which* nothing it is. This is a sentence, not a constraint on layout. |
| Real data only | A reference figure we do not measure (uptime, MTTR, healed counts) maps to one we do, or goes. Carrying it would put a fiction on screen. |
| Contrast floor 5.05:1 | Accessibility. Text nobody can read is not a design. |

Everything else that previously constrained appearance is retired. Motion's living tier — WebGL
shaders, Three.js graphs, staged entrances, animated throughput — is **authorized** (`DESIGN.md`,
Motion), gated only on: not claiming a time the data lacks, honouring `prefers-reduced-motion`,
and running on the GPU.

## 4. Per-screen layout rulings (owner, 2026-08-25)

| Screens | Ruling |
|---|---|
| Overview | **Full rebuild** → `developer_control_center` bento: viewport-locked grid, panes tiled, per-pane scroll |
| Findings, Runs, Call sites | **Full rebuild** → viewport-locked table filling the screen + **drawer** on selection |
| Finding detail, Workflow | **Full rebuild** → two-column split, evidence left / remediation right, panes scroll independently |
| Solutions | **Rebuild** → `remediation_ci_cd_policy` board *(landed, `CI-W639`)* |
| Graph | Canvas + docked node inspector |
| Vendors, Services, Telemetry | Tables stay, reskinned. **Vendors is cards only** — table view retired |
| Trends, Settings, Detectors, Corpus, Integration changes, File tree | Reskin only |

**Build order:** frame mechanics *(landed)* → shared chrome layer *(landed)* → Findings → Overview
→ Call sites *(landed)* → Runs → Finding detail → Workflow → Solutions *(landed)* → Graph.

## 5. Chassis rulings, all landed

- **Full width, every route.** No max-width cap. Design for 1920×1080.
- **A real height chain** — `html`/`body`/`#root` at 100%. Viewport units broke under display
  scaling; this is why the shell was shorter than the window on another monitor.
- **Two 48px chrome rows** — trail + palette above, a full-width stats bar below. Every page's
  KPI strip portals into it automatically through `KpiStrip`; a page draws no KPI row of its own.
  Cells divide the width evenly, label centred over value.
- **Sidebar** — persistent 240px, collapses to a 48px rail **on its button only**, never on
  hover. Furniture stage labels, no prose. Active row is a filled emerald pill.
- **Detail is a drawer**, never a docked column: a detail must never squeeze the table.
- **Locked layouts** — `ScreenFrame layout="flow"|"fill"|"locked"`. A locked screen owns its
  scrollbars. `Pane`/`PaneScroll` are the mechanic; `PanelPane` adds the banded chrome.
- **Scaling** — the frame gutter steps down at 1000px and 850px of viewport height.

## 6. Cognitive-load rulings, all landed

Removed: the Scope sentence · the not-to-scale paragraph · the API-surface card (deleted) ·
settings-door descriptions (survive as tooltips) · the git login from the top bar · the repo
identity demoted to a small muted value · the sidebar's five stage sentences (survive as tooltips).

**Getting Started leads the Overview** and is a stepper: icon bubble, N-of-M ready with a progress
bar, one chip per prerequisite, the first unmet one expanded with a single CTA.

## 7. Still to build

- **The five remaining screen rebuilds** (Findings, Overview, Runs, Finding detail, Workflow,
  Graph) — specs written, three builders lost to a session limit.
- **Vendor logos** — bundled local SVGs committed to the repo, monogram as fallback. Ruled; not
  started. No CDN fetch: it leaked which integrations each customer watches.
- **All chart surfaces removed and rebuilt** to their Stitch references.
- **The motion tier** — shaders, Three.js dependency graph, log-stream entrances.
- **Track E** — the row health strip, two-tier test signals, the improvement loop
  (`2026-08-23-integration-health-and-the-improvement-loop.md`).

## 8. The dev loop

`npm run no-admin` (Postgres 5433) → `SYNC_API_RELOAD=true uv run python -m sync.api` (8787) →
`cd web && npm run dev -- --port 5173 --strictPort`.

**Gate every change:** `npx tsc -b`, `npx vitest run`, `npm run lint`, `npm run build`, and
`uv run pytest tests/ -q`. Read the FAILED list, never the count — a passing count with a hidden
failure line has cost this project twice.

Verify visually with Playwright against the running console. A change nobody looked at is not done.
