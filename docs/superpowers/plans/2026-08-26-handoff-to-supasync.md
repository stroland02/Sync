# Handoff: what changed here since the 2026-08-25 clone

Written 2026-08-26 for the **supasync** repository, which was cloned from this one on 2026-08-25 and
has since diverged. Nothing here is a request to sync code. It is the set of **decisions, measured
findings and refusals** that the clone does not have, so the same ground is not re-walked or
re-litigated there.

Read `docs/superpowers/plans/2026-08-26-ui-rebuild-master-brief.md` first if you take only one file.
This document is the delta on top of it.

---

## 1. The authority order changed, and this is the highest-value item here

**`web/CLAUDE.md` was routing every console edit to a retired mock.** It opened with *"Before you
change a screen, open the mock — `docs/console-mock/`"*. That mock was demoted on 2026-08-25, but
both directories sit side by side on disk, so every agent kept conforming to the old UI while
believing it was following the current one. This is why the console kept coming out looking the
same. Fixed in `CI-W642`.

The order now is:

1. **`docs/stitch_sync_developer_console/`** — 24 screens, each a `screen.png` plus the `code.html`
   behind it. This is the visual authority.
2. **`docs/console-mock/`** — **RETIRED.** If you are reading a twelve-screen mock, you have the
   wrong drawing.
3. Where the reference disagrees with `DESIGN.md` or `console-surface.md`, **the reference loses**
   and the disagreement is recorded.

Two traps found in the reference set itself:

- **`high_density_technical_console` is not a screen.** The directory holds only a `DESIGN.md` token
  sheet — no `screen.png`, no `code.html`. It cannot supply a composition. Read it for row-height
  and border-over-shadow rules only.
- **`advanced_telemetry_trace_explorer` carries a pulsing "Tailing…" dot.** That is a liveness
  pulse, refused outright (see §5). A lane correctly declined it rather than shipping it.

`.claude/rules/interface-originality.md` was amended by the owner on 2026-08-26: **visual reference
is now unrestricted.** The old rule — competitors studied for concepts but never for how a screen
should look — is retired. It produced the flatness measured in
`reports/2026-08-06-why-the-console-came-out-flat.md` (type range 2.0 against a 3.4 bar; seven
side-by-side placements in the whole application). Four things still do not transfer: identity,
copy, a claim the data cannot support, and anything unlicensed.

---

## 2. What actually shipped — 30 commits, `CI-W622` … `CI-W653`

**Nine screens moved from one unbounded scrolling column to bounded multi-pane compositions.** At
the clone point that count was three. The test suite went from ~1,079 to **1,266**.

| Screen | What it became |
|---|---|
| Findings | locked table + drawer that never squeezes it |
| Overview | bento; Getting Started + both maps above the fold, stage doors below |
| Runs | locked filling stream, five fixed columns, one line per row |
| Finding detail | **evidence / remediation split** — true 50/50, each pane scrolls its own body |
| Workflow | same split; Evidence (4 sections) beside Remediation (5) |
| Graph | canvas + inspector; 118-node map at 69% of content width |
| Vendors | **zero tables**, 30 cards, each with its mark; docked drawer |
| Solutions | **board** of five columns from the closed disposition vocabulary |
| Binding surface | four panes; 9 columns → 5, 346 words → 190 |

Trends and Corpus were rebuilt as locked bentos. Call sites was locked earlier (`CI-W635`) but is
**still thin** — see §4.

### Owner instructions carried out and independently verified

Scope sentence removed · not-to-scale paragraph removed · API Surface card removed · git name out of
the top bar · KPI/workflow bars moved **into** the top bar as a second 48px row, full width, centred
· sidebar minimize rail · simpler breadcrumb trail · call site as a drawer that does not compact the
screen · Vendors fully cards · full-screen 1920×1080.

---

## 3. Measured findings worth carrying over — these cost real time to find

These are the durable part. Each was a defect that looked like something else.

**Cascade layers beat specificity, and it silently broke three viewport rules.** `index.css` put
three `max-height` rules in `@layer components`, where they lose to `p-frame`, `py-section` and
`gap-8` — Tailwind's `utilities` layer outranks `components` **regardless of selector specificity**.
Every viewport step had been inert since it was written. Measured at 1366×768: the gutter rendered
**40px where the rule says 8px**, the gap **32px where it says 16px**. Un-layering returned ~64px of
vertical space at laptop heights. (`CI-W647`)

**Tailwind v4 namespace trap.** `h-*` derives from `--spacing-*`, so `h-row-lg` generates **nothing**
and the class is inert. Must be `h-[var(--row-lg)]`. This rendered a pane header at 29px and a
footer at 17px — both content height — with no error anywhere.

**An implicit grid row is sized by its content *before* the `fr` rows divide what is left.** Adding a
row to a two-track `.bento-lock` collapsed the two chart rows to **131px and 87px** while the new row
took 399px, and two panes clipped inside their own boxes. Declare the track. (`CI-W649`)

**`auto` sizes a row to what a pane will *accept*, not what it *needs*.** With `min-height: 0` on the
children, a bare `auto` row measured 72px with the body crushed to 32px. Floors must come from
measurement. (`CI-W651`)

**A sticky `thead` needs the scroll on the vendored `data-slot=table-container`.** Wrapping it in a
second scroller leaves the head sticking to a box that never scrolls, so it rides away with the rows.
`PanelPane` has `scroll={false}` for exactly this.

**`100svh` masked a missing height chain** and broke under display scaling. `html, body, #root {
height: 100% }` plus `body { overflow: hidden }` is the real fix. (`CI-W638`)

**The colour-literal guard reads a `#`-prefixed hex run as a colour.** Valid hex lengths are 3, 4, 6
and 8, and every decimal digit is a hex digit — so a PR number `#101` trips it as `#RGB` and `#1017`
trips it as `#RGBA`. Five digits is the shortest safe length in a fixture.

**Two agents will factor the same code into rival modules.** Two lanes each extracted the diff
renderer out of `patch-panel.tsx` at once, into `patch-diff.tsx` and `patch-parts.tsx`. The
coordinator kept one — and **the one behavioural addition the spec attached to that move went with
the copy that was dropped**, so `pr_url` rendered nowhere for several commits. If a lane factors code
out of a file outside its own directory, it must say so first and loudest.

**Isolate every parallel lane in a worktree.** Two rebuild scripts were dispatched without
`isolation: 'worktree'` and wrote into the main tree concurrently, both touching
`features/bindings/`. It ended well by luck, not design.

---

## 4. Still owed

**Four screens still render the default `flow` layout and genuinely owe a rebuild:** Detectors,
Pull request, Vendor detail, Integration changes. Three more are flow **by owner ruling** and are
correct as they are: Settings, Telemetry, Services (tables stay, reskinned) — though the audit found
the Telemetry and Services *reskins* were never actually performed either.

**Call sites is thin.** Owner: *"there's not a lot of information and quality and design going on."*
Measured: one pane, one 6-column table, 50 rows, **zero charts, zero KPI tiles**, 718 words — and
`"Narrow the call sites"` renders **twice**, which is a live defect. The owner named
`repository_index_explorer` as the reference. Note its neighbour `binding-surface-page.tsx` was
rebuilt against that same reference and shares `call-site-columns.ts` and `filter-rail.tsx` with it.

**Integration changes has dead markup** — an empty `<div className="grid auto-rows-fr gap-8
xl:grid-cols-2">` left behind by a removed chart row.

**Solutions built a differently-shaped board than its spec**, leaving three residues uncleaned.

**Runs' spec DELETE list is half carried out** — the spec names two deletions and one was executed.

---

## 5. Ideas raised and NOT taken — with the reason, so they are not re-proposed

### Refused on principle, repeatedly, and these are load-bearing

- **A composite score, health figure, traffic light or liveness pulse.** Rejected three times on the
  record. A scalar that averages *"we could not check"* with *"we checked and it passed"* collapses
  the exact distinction the product exists to make. A **badge** is permitted — a recorded value from
  a closed vocabulary, legible without its colour.
- **`Root cause confidence: 9`.** The best incident view in the reference set carries it. Take the
  structure, refuse the scalar. **Composition and honesty are independent axes.**
- **A confidence bar, a spinning chip, and three write actions** in the remediation pane — all
  present in the Stitch reference, all declined, each refusal recorded in the component docstring.
- **A pulsing "Tailing…" dot** from `advanced_telemetry_trace_explorer`.
- **Any percentage without its denominator on screen**, and any figure whose scope is qualified
  nowhere.
- **Hiding a protected distinction behind a disclosure.** An early scaling fix used `display: none`
  on the chassis qualifications at short viewports — one of which is the multi-tenancy claim.
  Reverted. **Only spacing scales.**

### Authorized but deliberately not started, and each is blocked on something specific

- **The motion tier** — shaders, Three.js dependency graph, log-stream entrances. The brief
  authorises it. `web/src/lib/motion.ts` holds `MOTION_USAGES` (1 entry) and `KEYFRAMES` (**empty**)
  as closed registries that `tests/test_console_design_tokens.py` asserts **in both directions**
  against the tree and against `index.css`. Any Tailwind animation utility or staged entrance fails
  the Python gate until it has an argued registry entry. A lane hit this and correctly declined
  rather than working around it. **This is a decision for the brief, not for a screen.**
- **Vendor logos.** Ruled: bundled local SVGs committed to the repo, monogram as fallback, **no CDN
  fetch** — the previous `logo.clearbit.com` call leaked which integrations each customer watches
  and made the console's appearance depend on a network nobody controls. The mechanism ships and
  reaches nothing at render; `web/src/assets/vendors/` contains **only a README**. What is missing is
  the per-vendor licensing call, which is the owner's.
- **Track E** — the row health strip, two-tier test signals, the improvement loop
  (`2026-08-23-integration-health-and-the-improvement-loop.md`). No `HealthStrip` component exists.
- **"All popular developer vendors"** in the Add-vendor drawer. What shipped is **10 Stainless
  fintech/AI SDKs**. Absent entirely: GitHub, Slack, SendGrid, Shopify, AWS, Google Cloud, Firebase.
- **All chart surfaces rebuilt.** Trends and Corpus were done; Telemetry's three charts were not.

### Structural constraints that shaped what was built

- **The API stays read-only.** No route mutates the graph, triggers a run, or touches a customer
  repository. One exception, owner-ruled: `POST /api/findings/{id}/dismissal` exists and **the
  console does not call it** — dismissing is a command-line action.
- **We never hold customer secrets.** Unqualified.
- **`sync.core` imports nothing from a sibling package**, and vendor-specific knowledge lives in
  adapters, never core.

---

## 6. The corpus, if you are running screens against data

**`synthetic/every-state`** is the one to use: 105 of 110 findings, 56 call sites, **30 vendors, 12
protocol kinds**, 210 vendor changes across 5 severities, all four binding rungs, 12 detectors, 3
error windows, telemetry attached. Built by `scripts/seed_synthetic.py`.

The other four are deliberate edge cases: `synthetic/never-indexed` (empty-state fixture, 0
findings), `seed-console-repo-a`/`-b` (small legacy fixtures), and `github.com/stroland02/Sync` —
Sync indexing itself, **1,195 real call sites but 0 findings**, because no detector has run on it.

**One seeder trap worth knowing.** Writing observed calls straight to the store produces a state the
product cannot otherwise reach: real telemetry arrives through `sync.telemetry.ingest`, which marks
attachment itself (`ingest.py:117`). Skipping that left sixty observed calls under a repository the
graph said was never watched, and the Telemetry screen correctly refused the whole page — printing
*"nothing has watched this repository's traffic"* over calls it was holding. (`CI-W652`)

---

## 7. Verification discipline, which is the part most worth copying

- **Test first, and watch it fail for the reason you expect.** Every console guard is shown red
  against a deliberately broken subject before it is trusted. A test that has never failed has never
  been shown to test anything.
- **Read the FAILED list, never the count.** A passing count with a hidden failure line has cost this
  project twice. Piping through `head` also swallows the exit code — that produced one false "green"
  in this session.
- **`npm run build` passing is not evidence.** TypeScript checks the console against the types the
  console *declares*, not what the API *sends*. Python tests that read the TypeScript hold the two
  sides together.
- **Measure the DOM, do not describe it.** Screenshots were unavailable for this whole session, and
  DOM measurement turned out to be **stronger** evidence for layout claims than a still would be —
  computed overflow, scrollHeight vs clientHeight, pane geometry, how many regions actually scroll.
  It is also how a stale stylesheet was caught: a dead Vite process served old CSS while the source
  was correct, and only the measurement disagreed.
- **Adversarially verify anything reported as done.** A four-lane audit of 41 items overturned
  **7 of 24 "DONE" claims** — including two owner instructions that had been reported complete and
  never executed, and one where a plan had quietly reinterpreted the instruction into a narrower one
  it could satisfy.
