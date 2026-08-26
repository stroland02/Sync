export const meta = {
  name: 'screen-rebuilds-wave-3',
  description: 'Vendors to cards, Solutions to a board, and the chart surfaces rebuilt',
  phases: [{ title: 'Rebuild', detail: 'three screens, isolated worktrees' }],
}

const ROOT = 'C:/Users/sebastianr/Desktop/Terminal/Claude/Sync'
const REFS = ROOT + '/docs/stitch_sync_developer_console/stitch_sync_developer_console'

const CONTRACT = `You are REBUILDING one screen of the Sync operator console. Not reskinning it. The distinction is the entire point of this task and the owner has rejected the reskin twice.

WHY THIS MATTERS, in one measurement: eighteen of twenty-one screens still render \`ScreenFrame\` at its default \`flow\` layout — one long scrolling column — while the plans mandate locked, multi-pane compositions. A token swap already reskinned every screen without editing one, which is exactly how a console changes palette and stays the old console. If your screen still renders one scrolling column when you are done, you have not done the task.

READ FIRST, in this order:
1. ${ROOT}/docs/superpowers/plans/2026-08-26-ui-rebuild-master-brief.md — objective, authority order, per-screen rulings.
2. ${ROOT}/docs/superpowers/specs/2026-08-25-stitch-rebuild-specs.md — find YOUR screen's section. It carries the target composition, per-file KEEP / REBUILD / DELETE lists, what each pane binds, and the tests to change. It was written by an agent that read your source and your reference.
3. Your Stitch reference PNG and its code.html (paths below). The reference is the target.
4. ${ROOT}/web/CLAUDE.md.

**\`docs/console-mock/\` is the RETIRED mock. Do not open it.** The Stitch set is the authority.

THE CHASSIS YOU BUILD ON — already landed, use it rather than reinventing:
- \`ScreenFrame\` takes \`layout="flow" | "fill" | "locked"\`. A locked screen stamps \`data-screen="locked"\`, which flips \`main\` to \`overflow-hidden\` — the screen then owns every scrollbar on the page. **Your screen almost certainly wants \`locked\`.**
- \`layouts/pane.tsx\` — \`Pane\` (min-h-0 min-w-0 flex-1 flex-col overflow-hidden) and \`PaneScroll\` (min-h-0 flex-1 overflow-auto). Exactly one PaneScroll per Pane. This chain is load-bearing; omitting \`min-h-0\` silently gives the page a second scrollbar.
- \`components/pane.tsx\` — \`PanelPane({label, icon, actions, footer})\`, a bordered pane with a 40px banded header and a footer pinned outside the scroll.
- \`components/detail-layout.tsx\` — \`DetailLayout\` with \`docked\` renders the detail as a RIGHT-HAND DRAWER over the page (Sheet). Owner ruling: **a detail must never squeeze the table.**
- \`components/data-table.tsx\` — \`TableHeader sticky\` and \`TableFrame fill\`.
- Every page's KPI strip portals into the top bar automatically through \`KpiStrip\`. **Do not draw a KPI row in the page.**
- Title and subtitle come from \`ScreenFrame\` (title from the route registry, \`subtitle\` prop). Do not draw your own h1.
- The console is full width on every route. Design for 1920x1080; it must also hold at 1366x768.

BINDING, and a change violating any of these is wrong even if the reference shows it:
- No composite score, health figure, traffic light or liveness pulse. A badge from a closed vocabulary IS permitted and looks identical to the reference's chips — reach for that.
- Absence is not zero; staleness is not liveness; never-measured is not nothing-here. Every empty state says WHICH nothing it is.
- Real data only. A reference figure we do not measure (uptime, MTTR, healed counts) maps to one we do, or goes. Read the API payload; do not guess field names.
- No new colour/size/space token without a DESIGN.md row carrying contrast arithmetic against 5.05:1. Prefer existing tokens.
- Vendored primitives under web/src/vendor/ and web/src/components/ui/ are not yours to re-author.

VISUAL FREEDOM: as of 2026-08-26 no rule limits how a screen may look. Ambient motion is authorized. Build the most ambitious version that stays honest.

DATA: the console has a synthetic corpus covering every state — \`synthetic/every-state\` (60 call sites, 30 vendors, 12 protocol kinds, all rungs, all severities, all statuses) and \`github.com/stroland02/Sync\` (1195 real call sites). Both are in the graph on port 5433.

HOW TO WORK:
- Delete what the spec says DELETE. A rebuild that leaves the old composition beside the new one is not a rebuild.
- Run \`cd web && npx tsc -b --pretty false\` and \`npx vitest run --maxWorkers=4\` until clean. Default parallelism has produced spurious worker-start timeouts in this repo.
- Update tests that assert the old composition. Retitle them to the new behaviour rather than deleting the coverage they carried, and say in the test why it changed.
- Do NOT run pytest, lint or build; the coordinator gates those. Do NOT commit; leave the worktree dirty.
- If the spec conflicts with a binding rule, follow the rule and report the conflict.
- **If you factor shared code out of a file OUTSIDE your screen's own directory, say so first and loudest in \`forCoordinator\`.** Two lanes last wave each extracted the same renderer out of \`patch-panel.tsx\` into differently-named modules, and the coordinator had to drop one at the merge. Name the file you took code out of and the module you put it in.`

const REPORT = {
  type: 'object',
  required: ['screen', 'done', 'files', 'isLocked'],
  properties: {
    screen: { type: 'string' },
    done: { type: 'string', description: 'what the screen now IS, concretely — panes, what scrolls' },
    isLocked: { type: 'boolean', description: 'does it render ScreenFrame layout="locked" or "fill"' },
    deleted: { type: 'array', items: { type: 'string' }, description: 'files and components removed' },
    files: { type: 'array', items: { type: 'string' } },
    testsChanged: { type: 'array', items: { type: 'string' } },
    tscClean: { type: 'boolean' },
    vitestClean: { type: 'boolean' },
    blocked: { type: 'array', items: { type: 'string' } },
    forCoordinator: { type: 'string' },
  },
}

const SCREENS = [
  { slug: 'vendors', ref: 'integration_fleet_overview', src: 'features/vendors/repository-vendors-page.tsx',
    ruling: 'OWNER RULING, VERBATIM: "Vendors should fully switch to cards." Measured 2026-08-26 this screen is a HYBRID -- it already has a `VendorCard` and three `grid-cols`, but still carries EIGHTEEN table references. Fully means the tables go. Every connected integration becomes a card carrying its own mark (`VendorMark` already resolves a bundled SVG and falls back to a monogram), its binding rung, and what is actually recorded about it. A vendor with nothing measured gets a card that says which nothing it is, never a card that looks like a measured zero. Keep the existing `AddVendorDrawer` affordance working -- the owner asked for it by name.' },
  { slug: 'solutions', ref: 'remediation_ci_cd_policy', src: 'features/workflows/solutions-page.tsx',
    ruling: 'OWNER RULING: Solutions becomes a BOARD. Measured 2026-08-26 it is still a table -- fourteen table references and no columns. A board means solutions grouped into columns by the stage they have actually reached, each column headed by its own count, each card openable. The column vocabulary must come from a CLOSED SET the payload already carries (a run disposition, a status) -- never a stage somebody invented for the board. A column with no members still renders with its heading and a zero, because an absent column would claim the stage does not exist.' },
  { slug: 'charts', ref: 'advanced_telemetry_trace_explorer', src: 'features/dashboards/metrics-page.tsx',
    ruling: 'REBUILD THE CHART SURFACES against the reference. Your lane is `features/dashboards/metrics-page.tsx` and `features/dashboards/precedent-page.tsx`. `web/CLAUDE.md` carries the chart law and it OUTRANKS the reference: bars for rankings and for any set with meaningful zeros; donuts ONLY where the parts sum to a whole a reader can name and never below two members; log scale where the set spans orders of magnitude and SAY SO on the chart; a count is not a rate and no percentage ships without its denominator on screen. **Check the real payload before choosing a form** -- provenance once shipped as a donut over a set where four of five members were measured zeros and it rendered as a closed ring that read as broken. ECharts owns anything with an axis, a legend or a time dimension.' },
]

phase('Rebuild')
const built = await parallel(SCREENS.map((s) => () =>
  agent(
    CONTRACT +
      `\n\nYOUR SCREEN: ${s.slug}` +
      `\nOWNER RULING: ${s.ruling}` +
      `\nSpec section: search ${ROOT}/docs/superpowers/specs/2026-08-25-stitch-rebuild-specs.md for the heading naming your screen` +
      `\nReference image (the target): ${REFS}/${s.ref}/screen.png` +
      `\nReference markup, for exact values: ${REFS}/${s.ref}/code.html` +
      `\nYour source: web/src/${s.src}`,
    { label: `rebuild:${s.slug}`, phase: 'Rebuild', schema: REPORT, isolation: 'worktree' },
  )
))

const ok = built.filter(Boolean)
log(`${ok.length} of ${SCREENS.length} rebuilt; locked: ${ok.filter((r) => r.isLocked).length}`)
return { built: ok }