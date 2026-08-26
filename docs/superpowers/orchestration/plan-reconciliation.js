export const meta = {
  name: 'plan-reconciliation',
  description: 'Read every plan and spec, and reconcile what they mandate against what the console actually is',
  phases: [
    { title: 'Read', detail: 'four readers across the corpus' },
    { title: 'Reconcile', detail: 'what is mandated vs what exists' },
  ],
}

const ROOT = 'C:/Users/sebastianr/Desktop/Terminal/Claude/Sync'
const PLANS = ROOT + '/docs/superpowers/plans'
const SPECS = ROOT + '/docs/superpowers/specs'

const BRIEF = `You are auditing the planning corpus of the Sync operator console for an owner who says: "there is a lot more up-to-date information in the plans and specs than the one I have been working from, and those plans describe a FULL REBUILD of the UI, brand new — but the work being done is building off the OLD UI."

Your job is to find out whether that is true, and precisely what the plans mandate.

For every document in your assigned set, extract:
1. **What it mandates for the console's UI** — layout, composition, components, screens, visual direction. Quote the operative sentences.
2. **Whether it calls for a rebuild or an amendment.** A plan that says "recompose", "replace", "delete and rebuild", "from scratch" is different from one that says "reskin", "conform", "bring to parity". Say which, with the words it uses.
3. **Its status** — landed, superseded, abandoned, or open. Look for a status header, checkbox state, or a note naming the commit that closed it. WARNING: checkboxes in this repository are known to be false (CI-W607 records a plan reading 0/74 done while 89 of its items had shipped). Prefer commit references and status headers over checkboxes, and say when you cannot tell.
4. **What it supersedes or is superseded by**, if it says.

Be exact. Quote rather than paraphrase where the wording decides the meaning. If a document is not about the console UI, say so in one line and move on — do not pad.`

const EXTRACT = {
  type: 'object',
  required: ['documents'],
  properties: {
    documents: {
      type: 'array',
      items: {
        type: 'object',
        required: ['file', 'aboutUI', 'summary'],
        properties: {
          file: { type: 'string' },
          aboutUI: { type: 'boolean' },
          mandate: { type: 'string', description: 'what it requires of the UI, quoting operative sentences' },
          kind: { type: 'string', enum: ['rebuild', 'amendment', 'both', 'neither'] },
          status: { type: 'string', enum: ['landed', 'superseded', 'abandoned', 'open', 'unclear'] },
          statusEvidence: { type: 'string' },
          supersedes: { type: 'string' },
          summary: { type: 'string' },
        },
      },
    },
  },
}

phase('Read')
const BATCHES = [
  { label: 'plans-newest', glob: `${PLANS}, the twelve files whose names sort newest (2026-08-23 through 2026-08-26)` },
  { label: 'plans-mid',    glob: `${PLANS}, the files dated 2026-08-17 through 2026-08-19` },
  { label: 'plans-early',  glob: `${PLANS}, every file dated 2026-08-16 or earlier` },
  { label: 'specs',        glob: `${SPECS}, every file — plus ${ROOT}/DESIGN.md and ${ROOT}/web/CLAUDE.md` },
]

const read = await parallel(BATCHES.map((b) => () =>
  agent(
    BRIEF + `\n\nYOUR SET: ${b.glob}\n\nList the directory first, then read every file in your set. Do not skip one because its name looks irrelevant — the owner's point is that something was missed.`,
    { label: `read:${b.label}`, phase: 'Read', schema: EXTRACT },
  ).then((r) => ({ batch: b.label, documents: r?.documents ?? [] }))
))

const all = read.filter(Boolean)
const flat = all.flatMap((b) => b.documents)
log(`${flat.length} documents read; ${flat.filter((d) => d.aboutUI).length} concern the UI`)

phase('Reconcile')
const verdict = await agent(
  `You are reconciling what the Sync console's plans mandate against what the console actually is.\n\n` +
  `THE OWNER'S CLAIM: the newest plans describe a full rebuild of the UI, brand new, and the work being done instead reskins the old UI. Determine whether that is correct.\n\n` +
  `WHAT HAS ACTUALLY BEEN BUILT in the last two days (from the register): a viewport-locked chassis; a shared chrome layer (Pane/PaneScroll/PanelPane, docked DetailLayout now a drawer, sticky table headers); the Stitch token layer applied by changing token VALUES so 245 files reskinned without being edited; a persistent 240px sidebar with an emerald active pill; a two-row top bar whose second row is a full-width stats instrument; page headings; cognitive-load removals; Call sites recomposed as a locked three-pane explorer; Solutions recomposed as a board. Five screens (Findings, Overview, Runs, Finding detail, Workflow, Graph) have written specs but are NOT rebuilt.\n\n` +
  `Produce:\n` +
  `1. **VERDICT** — is the owner right? Answer plainly, with the evidence.\n` +
  `2. **THE OPERATIVE PLAN SET** — which documents actually govern the UI now, in authority order, with anything superseded named as such. The owner needs to know what to read.\n` +
  `3. **MANDATED BUT NOT BUILT** — every UI requirement across the corpus that is still open, deduplicated, ranked by how much of the console it changes. This is the work list.\n` +
  `4. **BUILT BUT NOT MANDATED, OR CONTRADICTED** — anything built that the plans do not call for, or that a plan contradicts. Be specific; this is where the reskin-versus-rebuild question gets decided.\n\n` +
  `Do not invent requirements. Quote the plans.\n\nDOCUMENTS:\n${JSON.stringify(flat)}`,
  {
    label: 'reconcile',
    phase: 'Reconcile',
    schema: {
      type: 'object',
      required: ['verdict', 'operativePlans', 'mandatedNotBuilt'],
      properties: {
        verdict: { type: 'string' },
        operativePlans: { type: 'array', items: { type: 'object', properties: {
          file: { type: 'string' }, role: { type: 'string' }, status: { type: 'string' } } } },
        mandatedNotBuilt: { type: 'array', items: { type: 'object', properties: {
          requirement: { type: 'string' }, source: { type: 'string' }, scope: { type: 'string' }, rank: { type: 'integer' } } } },
        contradicted: { type: 'array', items: { type: 'object', properties: {
          built: { type: 'string' }, plan: { type: 'string' }, conflict: { type: 'string' } } } },
      },
    },
  },
)

return { read: flat.length, aboutUI: flat.filter((d) => d.aboutUI).length, verdict }