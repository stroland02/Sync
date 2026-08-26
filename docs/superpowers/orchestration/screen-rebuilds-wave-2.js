export const meta = {
  name: 'screen-rebuilds-wave-2',
  description: 'Rebuild Finding detail, Workflow and Graph into locked multi-pane compositions',
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
- If the spec conflicts with a binding rule, follow the rule and report the conflict.`

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
  { slug: 'finding-detail', ref: 'self_healing_incident_inspector', src: 'features/findings/finding-page.tsx',
    ruling: 'FULL REBUILD to the evidence/remediation split (owner ruling): viewport-locked, evidence on one side and the proposed remediation on the other, each scrolling independently. The reference inspector carries `Root cause confidence: 9` -- REFUSE the scalar, take the structure. The provenance rung is the honest analogue and it stays monochrome and never hideable.' },
  { slug: 'workflow', ref: 'ai_driven_incident_resolution_workflow', src: 'features/workflows/workflow-page.tsx',
    ruling: 'FULL REBUILD to the evidence/remediation split (same ruling as finding detail): locked, the run stages on one side and what each stage produced on the other. A stage that never ran is not a stage that passed -- every stage says which nothing it is.' },
  { slug: 'graph', ref: 'code_graph_dependency_explorer', src: 'features/index-graph/index-graph-page.tsx',
    ruling: 'FULL REBUILD to canvas + inspector (owner ruling): the map fills the viewport and a selection opens an inspector beside it. The canvas owns its own scroll/zoom -- the page must not scroll. Existing canvases (force-map.tsx, file-tree-canvas.tsx, coupling-chord.tsx, map-previews.tsx) are the material; compose them, do not rewrite them from nothing.' },
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