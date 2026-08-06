# The console, measured against the bar three unrelated surfaces clear

**Measured 2026-08-06 at `7d8e798`.** Chrome 1440×900, `getComputedStyle` over every visible
element on every route in `web/src/lib/routes.ts`, with a real pointer moved onto a control so
`:hover` genuinely matched. Two extra viewports where a checklist item names one: 1280×800 for the
provenance column, 1920×1080 for prose measure. Fixture: `scripts/seed_console.py` plus
`--scale 10000`, so the tables under measurement held 2,500 rows rather than five.

Two other workstreams are editing `web/` while this was taken, so **every number here is a number
at `7d8e798` and nowhere else.** Two rows changed inside this commit and say so in place.

The bar is the fourteen invariants of
`docs/superpowers/plans/2026-08-05-sync-console-architecture.md`, section 8 — properties three
independently measured surfaces hold, each read the same way. Section 9's divergences are not a bar
and are not measured. Sections 15 and 22 record where a fourth surface, a shipping control plane,
broke four of section 8's fourteen; where our console fails one of those four, this report says so
and names the ruling that overturned the invariant rather than filing a defect against a decision
already argued.

**Two arithmetic notes on the bar itself.** Section 8's table carries fifteen rows while its own
prose, section 11 and this brief all say fourteen; nobody has been counting the same set. And its
`Lines` row is not a threshold — it is a shape ("rules exist and are drawn; the `border` property is
not spent on containers"), so it is reported as a count rather than a pass.

---

## 1. The invariants, per route

Nine routes, in `GRAPH_LEVELS` order. Column keys: **R1** Fleet `/` · **R2** Codebase
`/repositories/seed-console-scale` · **R3** Vendor `/vendors/seed-console-scale-stripe` · **R4**
Signals `/repositories/seed-console-repo-a/observed` · **R5** Binding surface
`/bindings/vendors/seed-console-scale-stripe/operations/PostCharges` · **R6** Detectors `/detectors`
· **R7** Finding `/findings/9f176…4037` · **R8** Solution workflow `…/workflow` · **R9** Pull request
`…/workflow/pull-request`.

Sorted by how far off, worst first.

| # | Invariant | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 3 | Type range ≥ 3.4:1 | 2.67 | 2.67 | 2.00 | 2.67 | 2.00 | 2.67 | 2.00 | 2.00 | 2.00 | **fail, 9/9** — deviation on the record |
| 3b | Display step ≥ 3× body | 2.29 | 2.29 | 1.71 | 2.67 | 1.71 | 2.29 | 2.00 | 2.00 | 2.00 | **fail, 9/9** — same ruling |
| 7 | In-component base 4, one dominant value | 2,4,8,**10**,12,16,20,24,32 | 4,8,**10**,16,20,24,32 | 2,4,8,**10**,12,16,20,24,32 | 2,4,8,**10**,12,16,20,24,32 | 2,4,8,**10**,12,16,20,24,32 | 4,8,**10**,16,20,24,32 | 4,8,16,20,24,32 | 2,4,8,16,20,24,32 | 2,4,8,16,20,24,32 | **fail, 6/9** — B104 |
| 6b | Frame 4.7–7.2× the in-component unit | 3.0 | 3.0 | 3.0 | 3.0 | 3.0 | 3.0 | 3.0 | 3.0 | 3.0 | **fail, 9/9** — reversed on the record |
| 1 | Two font weights, no 600 | 400/500/600 | 400/500/600 | 400/500/600 | 400/500/600 | 400/500/600 | 400/500/600 | 400/600 | 400/600 | 400/600 | **fail, 9/9** — overturned on the record |
| 13 | Primary action on hover: `transition-duration: 0s` | — | — | 0.15s | 0.15s | 0.15s | — | — | — | — | **fail where a control exists** — overturned on the record |
| 2 | Two ink levels plus one accent, never three | 2+accent | 2 | 2 | 2 | 2 | 2+accent | 2 | **3** | **3** | **fail, 2/9** — B107 |
| 5 | Leading loosens as size falls; display ≤ 1.2 | 1.125→1.429, 12px **1.333** | same | same | same | same | same | same | same | same | **partial, 9/9** — declared, see §3 |
| 8 | Prose never runs the column's width | 127ch → **81ch** | 79ch | 75ch | 85ch | 82ch | 80ch | 47ch | 81ch | 79ch | **fixed in this commit** |
| 4 | Display tracking negative, never looser than body | −0.04em | −0.04em | −0.04em | −0.04em | −0.04em | −0.04em | −0.04em | −0.04em | −0.04em | pass, 9/9 |
| 6a | Three spacing levels, each ≥ 2× the one below | 32:16:8:4 | 32:16:8:4 | 32:16:8:4 | 32:16:8:4 | 32:16:8:4 | 32:16:8:4 | 32:16:8:4 | 32:16:8:4 | 32:16:8:4 | pass, 9/9 |
| 10 | At most one authored stylesheet transition | 0/307 | 0/103 | 2/705 | 6/179 | 2/625 | 0/269 | 0/110 | 0/209 | 0/120 | pass — 2 rules, one of them dead |
| 11 | One `@keyframes`, and it is a spinner | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass, 9/9 |
| 12 | Nothing decorative running at rest | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass, 9/9 |
| 14 | One 400ms one-shot scroll fade, nothing else | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass, 9/9 |
| 9 | Primary and secondary differ only in fill | — | — | — | — | — | — | — | — | — | **not measurable** |
| 15 | Rules drawn; `border` not spent on containers | 12 / 0 / 2 | 7 / 0 / 0 | 59 / 0 / 0 | 16 / 0 / 0 | 58 / 0 / 0 | 15 / 0 / 0 | 6 / 0 / 0 | 16 / **7** / 0 | 11 / 0 / 0 | shape held |

Row 15 reads *borders declared / 1–2px filled divs acting as lines / elements carrying a
`box-shadow`*. Row 10 reads *elements with a non-zero rendered `transition-duration` / visible
elements*.

### What the numbers say, invariant by invariant

**Type range (3, 3b).** Nowhere near the bar, and deliberately. `DESIGN.md`'s Type section declares
six steps spanning 12–32px, and section 5 of the architecture plan refused a wider range on the
grounds that vertical space is rows; section 15.1 confirmed it against a control plane whose 14px
headings carry weight rather than size. On six of nine routes the 32px `--text-figure` step never
renders at all — no stat tile is on screen — so the range those routes actually show is 24/12 = 2.0.

**In-component base (7).** The one genuine spacing defect. `table.tsx:103` and `:122` spell
`px-row py-2.5`, so every `th` and `td` renders **10px** of vertical padding — off the 4px base, and
on the table-bearing routes the *second most frequent padding value in the document*: 918
occurrences against 926 of 8px on R5, 714 against 722 on R3. Nine distinct rendered spacing values
where the contract names three plus two exceptions. B104.

**Frame ratio (6b).** 24px frame against an 8px dominant in-component unit is 3.0, against a
4.7–7.2 bar. `DESIGN.md`'s Space section reverses this explicitly: the nav rail and header hold the
composition's edge, so the frame does no hierarchical work and is set to the smallest value that
keeps content off the chrome. The inner ramp — the part that survived section 15.3 — passes cleanly
at 32:16:8:4.

**Font weights (1).** Three weights everywhere: 400, 500 on column headers and navigation, 600 on
the four heading steps. Section 15.1 overturned the two-weight invariant against a control plane
that carries 600 on every heading down to 14px, and `DESIGN.md` already declares 600 on
`--text-emphasis`, `--text-section`, `--text-page` and `--text-figure`. Nothing above 600 renders
anywhere, and a guard now holds that.

**Hover (13).** With a real pointer on the pagination control and `:hover` matching, the fill steps
from `input/30` to `input/50` and nothing else moves: `transform: none`, `scale: none`,
`box-shadow: none`, `opacity: 1`. That is the shape all four references share — instant or eased,
never geometric — at 0.15s rather than 0s. Section 15.2 states plainly that the 0s assertion "is
wrong as written and must not be built as written", and `DESIGN.md`'s Motion section replaced it with
a frequency gate. The row a pointer crosses forty times a second carries no transition at all: a
real pointer on a table row leaves the background transparent and the row's own
`transition-duration` at 0s.

**Ink levels (2).** Two neutral inks on seven routes, plus the brand hue on exactly one element
where a link exists. On R8 and R9 a third appears — `oklch(0.83 0 0)`, `--color-ink-secondary`, from
the wrapper at `run-outcome.tsx:28` — on the two screens carrying the densest evidence. B107.

**Leading (5).** 32px→1.125, 24px→1.25, 18px→1.333, 16px→1.375, 14px→1.429, and then 12px→1.333.
The display end is inside the bar and the direction holds for five steps, then reverses at the
smallest. That reversal is declared, not accidental: `DESIGN.md` gives `--text-meta` a 12/16 line
box, on the 4px grid, and a 12/18 box would put the furniture layer off it.

**Prose measure (8).** Two elements in `features/fleet/` were the console's only prose that ran its
column: `corpus-chart.tsx`'s `figcaption` at **127 characters** in a 1345px column at 1440px, and
**206 characters** in a 1825px column at 1920px, and `screen-limits.tsx`'s four `dd` elements at
**147, 144, 143 and 142** characters at 1920px. Every sibling in the same files already carried
`max-w-prose`; these two did not. Fixed in this commit, one class each, re-measured: **81
characters at 1280, 1440 and 1920.** No route now exceeds 85 characters at any of the three widths.

**Button pairs (9).** Not measurable, and worth stating rather than scoring: the console renders one
button variant. `Previous` and `Next` on the paged tables are the only controls on any of the nine
routes, both `outline`, and no `default`, `secondary` or `destructive` variant appears anywhere. The
invariant needs a pair to compare and there is none.

**Transitions (10).** Two rules in the compiled stylesheet declare a transition: `.transition-colors`,
which the two pagination buttons use, and `.transition`, which **matches zero elements**. The second
is Tailwind lexing `transition={{ … }}` — framer-motion's prop at `error-surface.tsx:102`,
`page-controls.tsx:36` and `node-sequence.tsx:118` — as a class candidate. It is dead CSS carrying
`transform`, `opacity` and `box-shadow`, and the Python guard that bans the bare `transition`
spelling still catches anyone who writes it deliberately. A third rule zeroes every duration
document-wide under `prefers-reduced-motion: reduce`.

**Lines (15).** The shape holds. Rules are drawn as borders on separators and table rules — 5 to 59
per route, scaling with row count, not with container count — and only the node sequence draws
lines as filled divs (7). Two elements on R1 carry a `box-shadow`, which is `--shadow-flat` used
where the contract now says to use it rather than by default.

---

## 2. The seven-item checklist, answered against the running tree

`72450ae`'s note said items 2 through 6 were open. **Four of the five have closed** since; item 5 was
open here and is closed in this commit.

**1. Did a full walk of every route leave the browser console empty? Yes.** Nine routes walked at
1440×900 with console capture enabled from the first navigation: three messages total, all from the
toolchain — two `debug` lines from Vite's HMR client and one `info` notice about React DevTools.
Zero `warn`, zero `error`, no unmounted subtree.

Stated as a limit rather than a pass: the two branches this item exists for are reached by data, not
by clicking. `run-outcome.tsx`'s branch for an outcome the console has never heard of, and
`evidence.tsx`'s `JSON.stringify` of unnamed evidence keys, both need rows the fixture does not
write, and writing them was outside this task's licence. **This walk proves the console does not
throw on the data the fixture holds; it does not prove those two branches render.**

**2. At 1280px, is the provenance column on screen without scrolling a table sideways? Yes, on every
table that carries one.** Measured at 1280×800: no element anywhere in any route has horizontal
overflow except a 1px-wide `sr-only` container. `Rung` sits at column **2 of 7** on the vendor
findings table — the note recorded it sixth, and it has moved — column **1 of 8** and **1 of 6** on
the Signals panels, and column **8 of 9** on the binding surface, whose right edge lands at 1145px
of 1280.

**The structural reason matters more than the measurement, because it is what makes this robust
against a customer's repository rather than lucky with a fixture.** `table.tsx:122` sets
`break-words` on every cell, so the widest cell — `{row.file}:{row.line}`, a path Sync does not
control — wraps instead of widening the table. A 200-character path makes rows taller; it does not
push `Rung` off the viewport. That trade is real and it is the other half of B104: the vendor
findings table renders **80px body rows and a 52.5px header row** against the 36px `row-md` the
contract declares.

**3. Does the heading outline descend without skipping a level? Yes on all nine routes, and the
first heading on every one of them is wrong.** No route skips a level. But `command.tsx:49` puts
`DialogHeader` *outside* `DialogContent`, so the closed command palette's `h2` — "Jump to a
destination" — and its description sit in the document on every route, ahead of the page's `h1`. A
screen reader's heading list opens with the title of a dialog that is not open. B106.

One more thing this item does not ask but the measurement showed: at level 3 the outline and the
visual order disagree. `h3` renders at **12px/400** on R1 and R6 — the `.furniture` treatment,
lighter and smaller than the 14px body beneath it — so the machine-readable claim descends while
the visible one does not. That is the recorded furniture decision doing exactly what it was asked to
do on an element that also happens to be a heading, and it is not filed.

**4. Can you tell a page title, a card title and a row label apart at a glance? Yes.** Four distinct
treatments, measured: `h1` 24px/600/−0.96px, card title 16px/600/−0.32px, `th` 12px/500/normal,
`td` 14px/400/normal. Size, weight and tracking all separate the page title from the card title, and
weight separates the column header from the cell.

**5. At 1920px, does prose in an error, empty or abandoned-run panel wrap at a readable measure? Now
yes; at `7d8e798` no.** The two Fleet elements in §1 were the whole of it — 206, 147, 144, 143 and
142 characters against a rule that fires above roughly 85. Every empty state, every error panel and
every abandoned-run sentence elsewhere already sat at 79–85 characters, because
`components/states.tsx`, `run-outcome.tsx` and every `CardDescription` constrain themselves. Fixed
and re-measured at 81 characters.

**6. Tab to the Next button inside a card. Is its whole focus ring visible? Yes.** A real `Tab`
keypress from the last table link landed on `Next` with `:focus-visible` matching, and the ring
renders as a 3px `box-shadow` in the brand hue at 50%. It is not clipped, and it cannot be:
**`card.tsx` no longer sets `overflow-hidden`** — the structural cause the note recorded is gone —
and a scan of every focusable element on every route for a clipping ancestor with less than 3px of
slack returned **zero on all nine routes**.

Two limits on that answer. The scan ran with the palette closed, and `command.tsx`'s
`DialogContent` does set `overflow-hidden`, so a focus ring on the last item of a scrolled palette
list is unmeasured here. And the ring's rendered contrast is not what the contract publishes — §3.

**7. Is anything on screen rendered below 11px? No.** Minimum rendered font size is **12px** on all
nine routes, and `web/src` contains no `text-[…]` arbitrary size at all. Now held by
`test_nothing_renders_beneath_the_text_size_floor`, which reads the floor out of `DESIGN.md`'s own
Type table rather than restating it.

### The detector, and why none of this came from it

Re-checked in this worktree on 2026-08-06, and the note's finding still stands: `impeccable` is not
in `web/package.json`, and `node -e "require.resolve('puppeteer')"` fails with `MODULE_NOT_FOUND`.
So the precondition the tick demands does not pass and no exit code from a URL scan would have
meant anything. **Nothing was installed.** A dependency added to answer seven questions that a
probe over `getComputedStyle` answers directly, on a console with no test runner and no browser in
CI, would be a dependency whose only consumer is one report — and `CLAUDE.md`'s *build for the case
that exists* governs. Every item above was measured by hand against the running dev server, which is
what the tick already prescribes for this state.

---

## 3. What `DESIGN.md` claims, and what the pixels do

Four divergences. The first three are the contract's own hazard — a pairing computed on declared
tokens, rendered through an alpha — and the fourth is a document describing a pattern the tree has
retired.

**The focus ring: 8.69 claimed, 3.08 rendered.** *Non-text, against the 3:1 floor* says the focus
ring "clears it comfortably: 8.69, against `--color-surface`." The token does — measured 8.70. But
what renders is `focus-visible:ring-ring/50`, the brand hue at half strength, which composites to
`rgb(84, 101, 139)` and measures **3.08:1** against the card and 3.12:1 against the page plane. It
clears the 3:1 floor by 0.08. It is also the only channel: `outline-style` is `none` and the
border stays `--color-input` under focus, so that 3.08 is the whole of what a keyboard user sees.

**The outline button: 12.09 and 8.70 claimed, 10.76 and 8.03 rendered.** *Composed pairings,
rendered* lists `foreground` on `input/30` at 12.09 and on `input/50` at 8.70. Measured over
`--color-surface`, both are lower. The arithmetic, in the gamma-encoded sRGB Chrome actually
composites in: `oklab(0.578 0 0)` resolves to `#7a7a7a`, so `0.3 × 122 + 0.7 × 23 = 53`, and
`#f0f0f0` on `rgb(53,53,53)` is **10.76**; at `/50`, `0.5 × 122 + 0.5 × 23 = 72` gives **8.03**.
Both still clear the 5.05 floor comfortably, so this is a wrong number rather than an unsafe colour.

**Corrected 2026-08-06 while closing B105 (M4-W149).** The sentence that stood here — "No backdrop
in the ramp reproduces 12.09 — over `--color-surface-sunken` the resting fill is 45 and the pairing
is 11.6" — was wrong, and wrong in the direction that makes a real finding look larger than it is.
`#f0f0f0` on `rgb(45,45,45)` is **12.08**, not 11.6, and 12.08 at `/50` becomes `rgb(67,67,67)` at
**8.68**. So the published pair *is* the page-plane pair, read to two decimals; what the rows were
missing was the backdrop they were composed over, which is now a column in `DESIGN.md`. The figure
that matters for this console is the card one, because every outline button here sits inside a
`<Card>`.

**The row height: 36px declared, 40px minimum and 80px rendered.** *Row height* says `row-md` is
"the existing arithmetic made explicit — `TableCell` already renders a 36px row from `text-body` and
`p-row`; it was simply never named." It does not. `TableCell` renders `py-2.5`, which is 10px, so a
single-line row is 40px, and on the vendor findings table, where the call-site path wraps to two
lines, the rendered row is **80px** and the header **52.5px**. At 80px a 900px viewport holds about
ten rows of a ten-thousand-row table. B104 closes both halves — the off-grid value and the claim.

**`TableRow`'s hover fill: documented as current, and gone.** The same section keeps
`ink` on `surface-subtle/50` at 14.80 "as the measurement of what the tree renders today". A real
pointer on a table row now leaves `background-color` at `rgba(0, 0, 0, 0)`, with the row's own
`transition-duration` at 0s — which is section 15.5's ruling, correctly built. The document is
describing a retired pattern in the present tense.

**What holds.** Dark-only holds: no component branches on `prefers-color-scheme`, and
`<html class="dark">` is in the markup. The `@keyframes` baseline of zero holds. Every text-on-solid
pairing in *Contrast, computed* renders exactly as declared, because most of the console composes
solid ink on a solid surface and for those the token table is the whole story — which is the
distinction that section already draws, and it is right.

---

## 4. Which gaps are worth closing

Four, and they share a property: each one either costs an operator rows on a dense screen or puts a
number in the contract that the screen contradicts, which is the failure a measured contract exists
to prevent. **B104** is the one where the contract's own arithmetic does not render — 10px of cell
padding puts a declared 36px row and a declared 40px header in each other's slots, and the same two
lines are what make nine spacing values render where the contract names three. (**Corrected
2026-08-06 by `M4.5-W142`, which closed it.** This paragraph first said B104 "is the only one that
costs rows" and that a ten-thousand-row table "gives up roughly a third of its viewport to padding
nobody chose". Both were wrong. Padding was 20px of an 80px row; the row is set by the Finding
cell, whose 32-character id wraps to three lines at 56px in a 164px column. Fixing the padding
moved a row from 80px to 76px and bought **no extra rows** — 900/80 and 900/76 both floor to 11
above the fold. B104 was right to close on the contract, not on the density; B109 carries where the
rows actually go.) **B105** is three stale numbers and one stale sentence in the one section of
`DESIGN.md` whose entire purpose is to be checkable against pixels; a focus ring published at 8.69
and rendering at 3.08 is exactly the divergence that section warns about, and leaving it makes the
next reader trust the wrong figure. **B106** and **B107** are one line each and both are honesty
defects in the narrow sense this console cares about — a heading list that opens with a closed
dialog's title, and a third neutral ink on the two screens that carry the most evidence, where two
plus an accent is what the ramp promises. Everything else measured above is polish or a decision
already argued, and is not filed: the type range, the three weights, the frame ratio and the 0.15s
hover are all deviations *from* section 8 that sections 15.1, 15.2 and 15.3 and `DESIGN.md` overturned
on this console's own grounds, and refiling them would be relitigating a ruling; the 12px leading
reversal is a declared line box on the 4px grid; the dead `.transition` rule matches zero elements
and the guard that catches its deliberate use still works; `py-0.5`'s 2px duplicates no token, so the
spacing guard is right not to flag it and the disagreement is between `DESIGN.md`'s stricter recorded
decision and the test, which is a document reconciliation rather than a sweep; the `.furniture` `h3`
and the unhighlighted navigable row are both recorded decisions doing what they were asked to.

---

## 5. What is now held by a test, and what cannot be

Two guards landed in `tests/test_console_design_tokens.py`, both in that file's existing shape — a
test against the real tree and a `tmp_path` test carrying a deliberate violation, so the proof that
the scanner detects one is repeated on every run rather than performed once by hand.

- `test_nothing_renders_beneath_the_text_size_floor` — no arbitrary `text-[…]` size beneath the
  floor `DESIGN.md`'s Type table marks, in `px` or `rem`. The rendered census is already at 12px
  everywhere and `web/src` holds no arbitrary size at all; this is the temptation `DESIGN.md` names
  by hand ("No `text-[10px]`, ever, including the next time a table gets crowded").
- `test_no_font_weight_above_the_heaviest_declared_step` — no weight above the heaviest the Type
  table declares, reading 600 from the table rather than restating it, and catching both the
  Tailwind names and the `font-[700]` bracket spelling.

Both were proven red against the real tree, not only against a fixture: `text-[10px]` and
`font-bold` were put into `table.tsx:103` and both real-tree tests failed naming that file and line;
reverted, 26 pass.

**Three of the measured gaps cannot be held this way, and saying so is the point.**

The prose measure cannot. A source guard demanding `max-w-prose` on every `p`, `dd`, `figcaption`
and `CardDescription` under `features/` would be wrong on this tree: a survey of all 95 of them
across `web/src` found 43 without it, 32 of those under `features/`, and the ones checked by hand
were legitimate — a `dd` holding a short mono value, a `p` inside a wrapper that is already
`max-w-prose`, a flex row of label and value. The constraint often sits on an ancestor, and
whether it does is a question about rendered layout. A guard written anyway would either fail on
correct code or be relaxed until it caught nothing.

The row height can, and `M4.5-W142` landed the guard with the fix. **This section first said it
could not** — that "a guard banning fractional spacing utilities would be the right shape and it
fails on the current tree". The shape was wrong, which is why it looked unholdable. A fractional-
spacing ban still fails on the current tree, because `input.tsx`, `input-group.tsx`, `textarea.tsx`
and three badge call sites spell `px-2.5`, `py-1.5` and `py-0.5`, and sweeping the shadcn form
catalog was nobody's task. What the defect needed was not a spelling ban but **the arithmetic
itself**: resolve the classes `table.tsx` sets against `DESIGN.md`'s Type, Space and Row height
tables, and assert they multiply out to the declared height.
`test_a_body_row_measures_the_row_height_design_md_derives_for_it` does that, reddens if either side
moves alone, and was proven red against the real tree at `py-2.5` before it was trusted. **A rule
that resists a string match is often still a rule about a number.**

The rendered-contrast numbers cannot. Compositing an alpha over a surface needs a browser, and
`CLAUDE.md`'s rule that logic with a wrong answer lives in Python does not help here, because the
answer lives in Chrome's compositor. What can be held is the *token* arithmetic, which the existing
guards already do. **The contract's rendered section stays a measurement somebody has to repeat**,
which is what §3 of this report is for and why the method in the header is written out rather than
summarised.

---

## 6. Reproducing this

```sh
docker compose up -d
uv run python scripts/seed_console.py
uv run python scripts/seed_console.py --scale 10000
SYNC_GRAPH_DSN=postgresql://sync:sync@localhost:5433/sync SYNC_API_RELOAD=true uv run python -m sync.api
cd web && npm run dev
```

Then, at 1440×900 in Chrome, read `getComputedStyle` over every visible element and tally: distinct
`font-weight` and `color` among elements holding their own text; `font-size` min, max and mode;
`letter-spacing` divided by `font-size` at the largest and modal step; `line-height` over
`font-size` per step; `row-gap`, `column-gap` and the four paddings; characters per line from a
`Range` over each element's own text nodes divided by a canvas measurement of its font; every
element with a non-zero `transition-duration`; `CSSKeyframesRule` names; `document.getAnimations()`;
inline `opacity: 0`; declared borders against 1–2px filled divs. Then move a real pointer onto a
control and read it again — `element.matches(':hover')` is what tells you the pointer arrived, and
without that check the hover row is an assumption.

**Three notes for whoever repeats it.**

Ports collide. Three Orca workspaces were live, holding 8787, 8788, 5173 and 5174, and the API on
8787 was returning 500. This run used 8789 and 5199 through an untracked `vite.measure.config.ts`
that differed from `vite.config.ts` in the proxy target and nothing else; it is deleted. **Probe the
API before trusting a screen** — a healthy-looking console proxying to somebody else's broken
process is indistinguishable from a broken payload.

The soft-navigation shortcut has a cost. Walking routes with `history.pushState` plus a `popstate`
event is far cheaper than nine full page loads, and on a 2,500-row table three seconds is not always
enough for the fetch to land. Every number in §1 was taken from a direct navigation with the table
present, not from a soft navigation that had not finished.

**Measure the element that holds the prose, not the element that contains it.** The first pass of
this probe read `textContent` on each `p`/`li`/`td`, which on the workflow page concatenated a node
name, a status word and a purpose sentence laid out in one flex row and reported **209 characters**
on a line no reader ever sees. The true figure there is 81. A measurement can be wrong in a way an
impression cannot be corrected from, which is the argument for writing the method down.

---

## 7. Deviations from the brief, recorded

- **The fixture was written to a shared database.** Three workspaces resolve `localhost:5433` to one
  Postgres container, so `--scale 10000` added a synthetic repository other sessions can see. It is
  additive, tagged, and removable with `--scale 10000 --remove`; it was left in place because
  workstream 2's brief needs a long table and removing it mid-run would disturb whoever is looking
  at a screen. Nothing was updated or deleted.
- **Two interface files were edited**, `features/fleet/corpus-chart.tsx` and
  `features/fleet/screen-limits.tsx`, one class each, inside the brief's licence for a correction the
  measurement proves. No test holds them, for the reason §5 gives, so the evidence is the before and
  after in §1.
- **`DESIGN.md` was not edited**, though §3 finds four of its statements wrong. It is the design
  system workstream's file and two agents are in `web/` right now; B105 carries the correction rather
  than this commit.

## 8. Two things the gate showed that are nobody's defect but should be known

**A fresh worktree fails 38 tests until `scripts/bootstrap_tools.sh` runs.** Every one of them
traces to a single `FileNotFoundError: oasdiff not found` across `test_oasdiff.py`,
`test_routing_matrix.py`, `test_generated_adapter.py` and six others. The message names the fix, and
the suite is `3216 passed, 4 skipped` once the pinned binary is in `tools/`. Worth knowing because
the first read of that output looks like a broken branch rather than an unbootstrapped checkout.

**`npm run lint` is at 7 warnings, not zero.** `loops/console-improvement-tick.md` records that it
"reached zero warnings in Task 1 and staying there is a gate". All seven are
`react(only-export-components)` — `status.tsx:60`, `button.tsx:68`, and five in
`cardinality.tsx` — none in a file this commit touches, and `oxlint` exits 0 because they are
warnings. The tick's sentence is no longer true of the tree, and a gate that the tool does not
enforce is a gate somebody has to remember.
