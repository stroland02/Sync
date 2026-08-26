export const meta = {
  name: 'ui-status-audit',
  description: 'Audit every console screen and every owner instruction against what is actually built',
  phases: [
    { title: 'Audit' },
    { title: 'Verify' },
  ],
}

const SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['lane', 'items'],
  properties: {
    lane: { type: 'string' },
    items: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['what', 'status', 'evidence'],
        properties: {
          what: { type: 'string', description: 'The screen or the instruction, named exactly' },
          status: { enum: ['DONE', 'PARTIAL', 'NOT_STARTED', 'CANNOT_TELL'] },
          evidence: { type: 'string', description: 'file:line or a measured fact, never an impression' },
          gap: { type: 'string', description: 'If not DONE: precisely what is missing' },
          effort: { enum: ['S', 'M', 'L'] },
        },
      },
    },
  },
}

const CONTRACT = [
  'You are auditing the Sync operator console in C:/Users/sebastianr/Desktop/Terminal/Claude/Sync.',
  '',
  'READ FIRST: docs/superpowers/plans/2026-08-26-ui-rebuild-master-brief.md, web/CLAUDE.md, and',
  'docs/superpowers/specs/2026-08-25-stitch-rebuild-specs.md. The visual authority is',
  'docs/stitch_sync_developer_console/stitch_sync_developer_console/ -- 24 screens, each a screen.png',
  'with the code.html behind it. docs/console-mock/ is RETIRED; ignore it.',
  '',
  'RULES OF THIS AUDIT:',
  '- **Evidence or CANNOT_TELL.** Every status cites a file:line or a measured fact. An impression is',
  '  not evidence. If you cannot establish it from the tree, say CANNOT_TELL rather than guessing.',
  '- **Structural conformance is not the deliverable.** A screen rendering ScreenFrame at its default',
  '  "flow" layout -- one long scrolling column -- is NOT rebuilt however good its tokens look. Check',
  '  the layout prop, the pane composition, and whether the spec DELETE list was actually carried out.',
  '- **Be adversarial about DONE.** The owner has twice said "everything looks exactly the same" about',
  '  work reported finished. Prefer PARTIAL over DONE when unsure.',
  '- The console runs at http://localhost:5173 against a real API on 8787, with a synthetic corpus',
  '  under repo id "synthetic/every-state". Read files freely; edit nothing.',
  '- Report every item in your lane, including the ones that are DONE.',
].join('\n')

phase('Audit')

const LANES = [
  {
    key: 'screens-detect',
    task: [
      'YOUR LANE: the DETECT and REMEDIATE screens. Report one item per screen:',
      'findings-page, finding-page, detectors-page, fleet-page (Runs), solutions-page, workflow-page,',
      'pull-request-page, binding-surface-page.',
      '',
      'For each: which layout= its ScreenFrame uses; whether it is a real multi-pane composition or one',
      'scrolling column; whether its spec DELETE list was carried out; and whether it reflects its',
      'Stitch reference composition. Name the reference you compared against.',
    ].join('\n'),
  },
  {
    key: 'screens-index',
    task: [
      'YOUR LANE: the INDEX, SIGNAL and OBSERVE screens plus the tail. Report one item per screen:',
      'codebase-page (Overview), call-sites-page, file-tree-page, index-graph-page,',
      'repository-vendors-page, vendor-page, repository-services-page, integration-changes-page,',
      'signals-page (Telemetry), metrics-page (Trends), precedent-page (Corpus), settings-page.',
      '',
      'For each: which layout= its ScreenFrame uses; real composition or one scrolling column; whether',
      'its Stitch reference composition is reflected. Name the reference you compared against.',
    ].join('\n'),
  },
  {
    key: 'owner-instructions',
    task: [
      "YOUR LANE: the owner's OWN instructions from the working session. Audit each SEPARATELY and",
      'report one item per instruction, each with evidence:',
      '',
      '1. Remove the Scope sentence from the Overview screen.',
      '2. Remove the not-to-scale paragraph.',
      '3. Remove the API Surface card on the Overview page.',
      '4. Remove the Settings screen descriptions.',
      '5. Remove the git name from the top bar.',
      '6. Swap Getting Started with Pipeline, so Getting Started sits ABOVE Pipeline on Overview.',
      '7. Getting Started must be icon-driven and interactive, not a wall of sentences.',
      "8. Each page's KPI/workflow bar moved INTO the top bar as a SECOND ROW at the same 48px height,",
      '   full width, text centred. Look for a topbar stats portal and check the row height token.',
      '9. Add a sidebar minimize view -- a collapsed rail state.',
      '10. The top-bar file directory trail should be much simpler and cleaner.',
      '11. Every connected vendor should have its logo on its card.',
      '12. The call site should be a DRAWER and must not compact the screen.',
      '13. The UI should be full screen at 1920x1080.',
      '14. Vendors fully switched to cards.',
      '15. An add-vendor option on the Vendors page, plus all popular developer vendors available.',
      '',
      'For each, cite the file:line proving it, or say NOT_STARTED naming what is missing.',
    ].join('\n'),
  },
  {
    key: 'design-system',
    task: [
      'YOUR LANE: the design system and cross-cutting surface. Report one item per numbered point:',
      '',
      '1. **Chart surfaces.** Are they all rebuilt against their Stitch references? Which chart',
      '   components exist, where is each mounted, and does each obey the chart law in web/CLAUDE.md:',
      '   bars for rankings and any set with meaningful zeros; donuts only where parts sum to a whole a',
      '   reader can name and never below two members; log scale declared on the chart itself; no',
      '   percentage without its denominator on screen.',
      '2. **The motion tier** -- shaders, Three.js, log-stream entrances. Read web/src/lib/motion.ts,',
      '   its MOTION_USAGES and KEYFRAMES, and what tests/test_console_design_tokens.py asserts about',
      '   them. Report exactly what is registered and what the brief still owes.',
      '3. **Typography and density.** reports/2026-08-06-why-the-console-came-out-flat.md measured a',
      '   type range of 2.0 against a 3.4 bar. What is the range NOW? Count distinct type steps used',
      '   across features/, and count side-by-side placements against vertical stacks.',
      '4. **Vendor marks.** Is web/src/assets/vendors/ populated or empty, and what does the console',
      '   draw when it is empty?',
      '5. Any screen still importing from a deleted or retired module.',
    ].join('\n'),
  },
]

const audits = await parallel(LANES.map(lane => () =>
  agent(CONTRACT + '\n\n' + lane.task, { label: 'audit:' + lane.key, phase: 'Audit', schema: SCHEMA })
))

const all = audits.filter(Boolean).flatMap(a => (a.items || []).map(i => Object.assign({}, i, { lane: a.lane })))
log(all.length + ' items audited: ' + all.filter(i => i.status === 'DONE').length + ' DONE, '
  + all.filter(i => i.status === 'PARTIAL').length + ' PARTIAL, '
  + all.filter(i => i.status === 'NOT_STARTED').length + ' NOT_STARTED')

phase('Verify')

const doneClaims = all.filter(i => i.status === 'DONE')
const verdicts = await parallel(doneClaims.map(claim => () =>
  agent([
    CONTRACT,
    '',
    'An auditor claims this is DONE. Try to REFUTE it. Default to refuted=true if you cannot confirm.',
    '',
    'CLAIM: ' + claim.what,
    'THEIR EVIDENCE: ' + claim.evidence,
    '',
    'Open the file. Check the claim holds for the CURRENT tree, not for an intention. If it is a',
    'screen, check the layout prop and the actual pane composition rather than the tokens. If it is',
    'an owner instruction, check the thing asked for is actually GONE, or actually PRESENT as asked.',
  ].join('\n'), {
    label: 'refute:' + claim.what.slice(0, 26),
    phase: 'Verify',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['refuted', 'why'],
      properties: { refuted: { type: 'boolean' }, why: { type: 'string' } },
    },
  }).then(v => ({ claim, verdict: v }))
))

const overturned = verdicts.filter(Boolean).filter(v => v.verdict && v.verdict.refuted)

return {
  totals: {
    audited: all.length,
    done: all.filter(i => i.status === 'DONE').length,
    partial: all.filter(i => i.status === 'PARTIAL').length,
    notStarted: all.filter(i => i.status === 'NOT_STARTED').length,
    cannotTell: all.filter(i => i.status === 'CANNOT_TELL').length,
    doneOverturned: overturned.length,
  },
  overturned: overturned.map(v => ({ what: v.claim.what, why: v.verdict.why })),
  notDone: all.filter(i => i.status !== 'DONE').map(i => ({
    lane: i.lane, what: i.what, status: i.status, gap: i.gap, effort: i.effort, evidence: i.evidence,
  })),
  doneAndSurvived: doneClaims
    .filter(c => !overturned.some(o => o.claim.what === c.what))
    .map(c => c.what),
}
