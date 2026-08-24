# What is enabled for building the console, audited 2026-08-24

Written because the owner asked twice why the console looked unchanged, and part of the answer was
that resources they had provided were never opened. This is the list, with what each is actually
for and which are binding rather than advisory.

## Binding — these overrule any reference or plugin

Read before writing a screen. A plugin's suggestion that conflicts with one of these loses.

| Source | What it binds |
|---|---|
| `web/CLAUDE.md` | What a screen may claim. Absence is not zero, staleness is not liveness, never-measured is not nothing-here. **No composite score, health figure, traffic light or liveness pulse** — rejected three times on the record. A badge from a closed vocabulary is permitted. |
| `DESIGN.md` (74KB) | Every visual value. A colour, size or spacing step not in it is a proposal, not a measurement — it arrives with its contrast arithmetic against the 5.05:1 floor in the same commit that first uses it. |
| `.claude/rules/console-surface.md` | What may be said on screen. Dark-only, on the owner's explicit instruction. |
| `.claude/rules/console-hierarchy.md` | The nine levels come from the design spec, not from the console. Adding or moving a destination cites `specs/2026-07-25-...-design.md:429-443`, the amended block. |
| `.claude/rules/interface-originality.md` | The interface is ours. Competitors transfer **concepts, workflows and negative findings** — never how a screen looks. `scripts/hook_guard_reads.py` blocks the 50 competitor screenshots deterministically. |
| `.claude/rules/console-dev-loop.md` | One console on 5173, served from the coordinator's tree. A worker verifies on a free port and stops it before reporting. Rendered-pixel claims are measured, not screenshotted. |

## The target

`docs/console-mock/` — the owner's own mock, 2026-08-08. Twelve stills, a demo video, the design
canvas, and `README.md` explaining which of its facts are fixtures. **The mock is the lowest
authority in the room**: where it disagrees with the hierarchy spec, `DESIGN.md` or
`console-surface.md`, the mock loses and the disagreement is recorded rather than resolved silently.

Its colours are already our token contract — background `oklch(0.19 0.0025 159)`, card `0.215`,
popover `0.2275`, foreground `oklch(0.95 0.00275 159)` — so porting a screen is composition work,
and any colour that is *new* is conspicuous.

`docs/superpowers/plans/2026-08-17-console-mock-parity.md` is the route. **Its checkboxes are
false** — see the reconciliation header and `CI-W607`.

## Enabled and proven

| Plugin / tool | Proven | For |
|---|---|---|
| `playwright` | Yes — live screenshot of 5173 against real data | Navigate, screenshot, accessibility tree, console errors, network, resize, click and type |
| `frontend-design` | Enabled | Visual direction when building new UI |
| `superdesign` | Enabled | Multi-artboard canvas for comparing variants before building |
| `ui-theme-designer` | **Enabled 2026-08-24** | Named by the owner in this session's first message and off until now |
| `typescript-lsp` / `pyright-lsp` | Enabled | Real diagnostics rather than grep |
| `code-review`, `code-simplifier`, `feature-dev` | Enabled | Review and refactor loops |
| `chrome-devtools-mcp` | Enabled, **server disconnected** | Lighthouse, performance traces, heap. Needs `/mcp` in an interactive session. Playwright covers the frontend loop meanwhile. |

## Not useful here, recorded so it is not re-litigated

- **`sync-external-resources`** (repo skill) — nine nominated repositories. Its own verdicts say
  none serve frontend work; `pbakaus/impeccable` is explicitly *"do not read it for design advice"*
  on the grounds that **"Sync has no frontend"**, which was true when written and is not now. The
  entry is stale rather than wrong: what it recommends taking is the architecture, not the design.
- **`roadmap.sh` frontend track** (`references/notes/roadmap-frontend-skills.md`) — audited
  2026-08-04 and closed: *"worth zero minutes"*. Roughly ninety percent of the track is out of
  scope before you start reading.
- **`references/screenshots/`** — 50 competitor screens, deliberately unreadable by hook. The notes
  beside them are the adoptable half.

## The loop this establishes

1. Open the mock still for the screen being built.
2. Build against it, in `DESIGN.md`'s tokens.
3. Screenshot the running console with Playwright and compare to the still.
4. Gate: `npm run build`, `npm run lint`, `npm test`, and `uv run pytest tests/ -q` when Python moved.

Step 1 is the one that was skipped, and skipping it is what produced a day of work the owner could
not see.
