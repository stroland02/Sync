# The visual eval, first run — and what it says about Fleet

**2026-08-17.** The plan's central claim is confirmed: **the mock is a document and it can be
queried.** It renders in a headless browser, its computed styles read exactly like the built
console's, and the comparison that has been done by eye for five weeks can be done by measurement in
about ninety seconds.

Two of the plan's four diagnosed causes are confirmed, one is confirmed and now closed, and one of
its hierarchy rulings is **wrong from evidence** — that last one matters most and is first below.

## The hierarchy ruling that must change: v2 does not supersede v1 on appearance

The plan states *"v2 supersedes v1 where they differ."* Measured, at 1440×900:

| | `Sync Console.dc.html` (v1) | `Sync Console v2.dc.html` (v2) |
|---|---|---|
| `body` background | `oklch(0.19 0.0025 159)` — **dark** | `rgb(242, 242, 243)` — **near-white** |
| `body` colour | `oklch(0.95 0.00275 159)` | `rgb(29, 31, 32)` |
| heading | "Fleet" | "Codebases" |

**v2 is a light theme.** `.claude/rules/console-surface.md` records dark-only as of 2026-08-05 on the
owner's explicit instruction, with the theme resolver *deleted* rather than disabled, and
`docs/console-mock/README.md` says v2 was set aside for exactly this reason — it is built on the
light "Industry" design system. Treating v2's appearance as the target would reverse a recorded
owner decision by way of a plan sentence.

**Measured in full, v1 against v2, because the coordinator asked for v2's measurements and they are
the argument.** Both mocks, same probe, 1440×900:

| property | v2 | v1 | what it means |
|---|---|---|---|
| heading | Codebases | Fleet | v2 is newer on vocabulary |
| typeRange | 1.45 | 1.83 | **v2 is the flatter of the two**, and both are under our 3.4 bar |
| radii | *(none)* | 6px, 8px | **v2 draws square corners** — no `border-radius` anywhere |
| body background | `rgb(242, 242, 243)` | `oklch(0.19 0.0025 159)` | v2 light, v1 our exact token |
| side-by-side | 6 | **17** | **v1 is the more composed drawing** |
| prose characters | 81 | 340 | v2 is terser |

**That is three independent contradictions, not one.** Adopting v2's appearance would mean a light
theme against a recorded owner ruling; square corners against `DESIGN.md`'s two declared radius
tokens, which v1 and the build both honour; and a type range of 1.45 against a console rebuilt to
clear 3.4. And it would cost composition: v1 draws seventeen side-by-side regions to v2's six, so v1
is also the better target for the owner's original complaint.

**The refinement, and it keeps what the plan was reaching for.** v2 *is* newer where vocabulary is
concerned — it says "Codebases", which is the terminology `M7-W217` adopted, while v1 still says
"Fleet", which that item eliminated. So:

- **v1 is the appearance target.** Its colours are literally our token contract (see below).
- **v2 supersedes v1 on structure and vocabulary**, where it is simply later.
- **Neither overrides `DESIGN.md`**, which carries the contrast arithmetic.

An eval must say which it measured. This one measured **v1**.

## What was built, and why nothing was installed

`web/scripts/visual-eval.mjs` and `web/scripts/capture-console.mjs`. Both speak Chrome DevTools
Protocol over the `WebSocket` that Node 22+ ships as a global. **Zero dependencies added.**

### The trial the plan asked for, with the measurement

| | in-house script | the extraction tools (`d-extract`, `dembrandt`, `extract-design-system`, `html-style-extractor`) |
|---|---|---|
| Dependencies added | **0** | 1 npm package plus its tree, into a console that currently vendors its component library on purpose |
| Time to first real measurement | **~90 seconds** | not reached |
| Output shape | exactly the twelve properties the plan names | a token set, which then needs mapping onto those properties |
| Works on our target | yes, proven below | unknown — all four are built to crawl public sites |

**The in-house script won, and the deciding evidence is that it already ran.** The plan's second
caution was that we own the primitives and the missing piece was that nobody had pointed them at the
mock; that is precisely what turned out to be true. The extraction tools answer *what tokens does
this page use*, which is a superset of the question and arrives in a shape that still has to be
reduced to the plan's twelve properties before it can be diffed. Adopting one would trade a
hundred-line script we control for a dependency, a mapping layer, and a tool whose stated use case
is a public URL.

**Not a permanent verdict.** If the eval grows toward full token extraction — every colour, every
step, across breakpoints and interaction states — `d-extract` becomes the better answer and this
file should not be read as having settled that.

## First run: Fleet, v1 mock against the built console

1440×900, both sides measured with the identical probe.

| property | mock | built | |
|---|---|---|---|
| heading | Fleet | Repositories | **deliberate** — see below |
| typeMax | 22 | 46 | **deliberate** |
| typeMin | 12 | 12 | same |
| typeRange | 1.83 | 3.83 | **deliberate** |
| weights | 450, 600 | 400, 500, 600 | differs |
| radii | 6px, 8px | 6px, 8px | **same** |
| body background | `oklch(0.19 0.0025 159)` | `oklch(0.19 0.0025 159)` | **same** |
| body colour | `oklch(0.95 0.00275 159)` | `oklch(0.95 0.00275 159)` | **same** |
| frame padding | 0px | 40px | measurement artifact — see below |
| **side-by-side regions** | **17** | **4** | **the finding** |
| cells | 0 | 0 | same |
| **prose characters** | **340** | **915** | **the second finding** |

### What is already right, and it is more than expected

**Colour and radius match exactly.** Both sides report the same OKLCH background, the same
foreground, and the same two radii. That is not a coincidence — `docs/console-mock/README.md`
records that v1 was chosen over v2 precisely because its literal values are the ones
`web/src/index.css` declares. The token contract holds across the drawing and the build, which
means the remaining differences are about *composition*, not about palette.

### The finding as first written — **superseded by the second run below, and left for the record**

> The two sections that follow reported Fleet as far less composed and far wordier than the mock.
> **Both conclusions were wrong**, for two measurement reasons found by extending the eval to every
> page: the console under test had three failed panels, and `sideBySide` was comparing markup
> technique rather than composition. The corrected numbers are at the end of this file. They are
> kept rather than deleted because the wrong version is the intuitive one.

### The finding: Fleet is four side-by-side regions against the mock's seventeen

This is the owner's original complaint — *"the layout is one vertical stack where it should be a
grid"* — measured rather than described, and it is still true on the screen where it was first
raised. Earlier work moved Fleet's `sideBySideRegions` from 15 to 10 to 4 as the chassis changed;
the mock draws 17. **The built Fleet is markedly less composed than the drawing.**

### The second finding: Fleet carries 2.7× the mock's prose

915 characters against 340. `M14-W277` improved the *ratio* of prose to data from 125.2 to 25.0 by
adding real data, which was the right move and did not reduce the prose itself. The mock says the
same screen in a third of the words.

Both findings are Fleet's. Neither is fixed here: this run's job was to make them measurable, and
fixing them is the next unit rather than something to smuggle into an eval.

## Deliberate differences, recorded rather than fixed

The owner's instruction is "similar to or better than", so these are outcomes, not debt.

- **"Repositories" against the mock's "Fleet".** `M7-W217` eliminated "Fleet" as a term. The v1 mock
  predates that and v2 agrees with the build. **The build is correct; the mock is stale.**
- **A type range of 3.83 against the mock's 1.83.** `reports/2026-08-06-why-the-console-came-out-flat.md`
  measured a flat console and set a 3.4:1 bar; the drawing does not clear it. Matching the mock here
  would regress the console below a bar it was rebuilt to pass. **The build is better.**
- **Settings.** The mock invents fixture numbers the console refuses to render — recorded in the
  Gate 3 pass as the sharpest positive evidence in the walk. Unchanged, and it stays a deliberate
  difference.

## Two caveats about the eval itself, stated rather than buried

**Frame padding is a measurement artifact, not a defect.** The probe reads `padding-left` on `main`.
The mock pads an inner container instead, so it reports 0 while plainly having a frame. The number is
honest about what it measured and wrong about what a reader would conclude — it needs a probe that
finds the padded element rather than assuming which one it is. **Do not act on that row until then.**

**The first run of this script produced a false result and it is worth recording why.** It waited for
`main` to exist, measured the mock mid-compile, and reported a heading of `{{ title }}` with every
font size `null`. Had that been pasted into a report it would have read as a broken mock. The probe
now waits for laid-out text and an unrendered-placeholder check, and **throws rather than measuring**
if the page never finishes — a half-rendered measurement is worse than none, which is the same
argument the console makes about absence and zero.

## The stale-capture cause is now closed

`docs/superpowers/reports/screens/` held one directory, `2026-08-07`, from before the M7 port. It now
holds `2026-08-17` with nine routes at 1440×900, captured by `capture-console.mjs`, with subjects
read off the running API rather than hardcoded so a reseed cannot silently fill it with not-found
screens.

## Running it

```
cd docs/console-mock && python -m http.server 8910      # the mock, served so a browser treats it normally
cd web && npm run build && node scripts/serve-console.mjs   # the console, with an API behind it
node web/scripts/visual-eval.mjs                        # the diff
node web/scripts/capture-console.mjs                    # the dated captures
```

Every URL, port and viewport is an environment variable. Chrome needs a debug port; the shared
automation browser already listens on 9222.

## What blocked, and what it did not block

`python -m sync.api` **cannot start on current `main`**: `configured_api_password` is imported inside
`app_factory` at `src/sync/api/__main__.py:209` and called from `main()` at `:243`, so the entrypoint
raises `NameError` (`7d2a38c`, Lane E's B166). Escalated rather than taken — `src/sync/api` is Lane
E's file and this is not a red this lane caused. The suite does not catch it because the tests build
the app through `create_app` rather than executing `main()`.

The eval proceeded by starting the app through `uvicorn sync.api.__main__:app_factory --factory`,
which bypasses the broken function without touching the file.

---

# Second run: page by page, and two corrections that change the conclusion

**Appended 2026-08-17 after extending the eval to walk all seven screens.** The first run compared
one page. The plan asks for page-by-page, and doing it surfaced two measurement defects whose
correction reverses the headline finding. Both are recorded because the wrong version is the
intuitive one and somebody will re-derive it otherwise.

## Correction 1: the console under test was half broken, and the numbers said so

`serve-console.mjs` gates everything including `/api`. Chrome uses credentials embedded in a
navigation URL for the document but **does not attach them to the page's own `fetch` calls**, so
three panels rendered "the request never reached a server" and the eval measured that.

The effect was large and in both directions — error prose counted as console prose, and failed
panels counted as missing composition:

| page | before (unauthenticated) | after |
|---|---|---|
| observe `sideBySide` | 1 | 6 |
| observe `cells` | 0 | 50 |
| remediation `sideBySide` | 4 | **18** |
| settings `cells` | 0 | 41 |

The eval now sends `Authorization` through `Network.setExtraHTTPHeaders` and re-navigates. **This is
the second false result this script produced before being trusted**, after the mid-compile one, and
both were caught by a number looking implausible rather than by the script noticing.

## Correction 2: `sideBySide` compares markup technique, not composition

The mock contains **zero `<table>` elements and 33 `grid-template-columns`** — it draws every table
as CSS-grid rows. The built console uses semantic `<table>`, whose `<tr>` is neither grid nor flex.
So each mock data row counts as a "side-by-side placement" and each of ours counts as nothing.

**Fleet's 17-against-4 was almost entirely that.** Chasing it would mean abandoning table semantics
— worse for assistive technology, on a console that landed focus management this same day — to move
a number nobody reads. That is optimising a proxy, which `M0-W269` warns about in the same document
that commissioned this eval.

`regionsBeside` is the honest form: how many *panels* sit beside another panel, with table-internal
rows excluded by construction. A child counts as a region when it is a landmark, carries its own
heading, or is drawn as a card.

| page | mock | built | |
|---|---|---|---|
| fleet | 0 | **2** | built is more composed |
| codebase | 2 | 0 | **built is behind by 2** |
| api-services | 1 | **4** | built is more composed |
| signals | 1 | 0 | built is behind by 1 |
| observe | 1 | 0 | built is behind by 1 |
| remediation | 1 | 1 | same |
| settings | 1 | 1 | same |

**The premise that the built console is far less composed than the drawing is not supported.** At
panel level the mock places between zero and two regions beside each other; the console places
between zero and four. The real gaps are three pages behind by one or two pairings.

## Fleet: both halves of the assigned fix are already closed, measured

The dispatch asked to close Fleet's composition and prose gaps against v1. Measured, there is
nothing to close:

- **Composition.** Fleet `regionsBeside` is 2 against the mock's 0. The console already exceeds the
  drawing at panel level.
- **Prose.** Fleet renders 915 characters against the mock's 340 — but **580 of those are the
  protected honesty sentences** (the staleness-not-liveness sentence, absence-is-not-zero, the
  three-attempts-one-finding grain, and the composite-health-figure refusal). Non-protected prose is
  **335 characters against the mock's 340.**

So Fleet's *discretionary* prose already matches the drawing to within five characters, and the
entire remaining difference is sentences that may not be shortened. **No change made, and none is
warranted.** Cutting to reach 340 would mean cutting a distinction, which is forbidden as firmly as
deleting one.

## What the eval says to do next, by measured gap

1. **`codebase`** — behind by 2 panel pairings, the largest real composition gap.
2. **`signals`** — behind by 1, and carrying 1663 characters of prose against 308, the largest prose
   gap on any page. Worth checking how much of that is protected before touching it, exactly as
   Fleet turned out to be.
3. **`observe`** — behind by 1.

Type range and heading differences remain deliberate and recorded above: the console clears a 3.4:1
bar the mock does not, and says "Repositories" where the v1 mock still says "Fleet".

---

# Signals: the protected-content pass, and it is at parity

**Audited with `web/scripts/prose-audit.mjs`**, which authenticates the way the eval does and
**refuses to report** if any panel failed — the error-prose trap this lane fell into twice.

Twelve paragraphs, 1571 characters. Classified against the four distinctions `CLAUDE.md` protects
and the twenty-four sentences in *Establish 2*:

| Class | Chars | What it is |
|---|---|---|
| **Protected** | **1083** | three sentences carrying *never-measured apart from nothing-here*, plus one absence statement |
| Transient | 210 | two loading states, caught mid-fetch — not prose anyone can cut |
| **Discretionary** | **278** | the route's own question and three one-line role descriptions |

The protected block is not marginal. One paragraph reads *"a group with no rows in it is a quiet
integration rather than a missing one… A role with nothing attached was never asked, because there is
no adapter, no configuration table and no row here to ask — which is a different fact from an
attached integration that was asked and had nothing to report."* That is the never-measured
distinction stated outright, twice on this screen.

**Discretionary prose is 278 characters against the mock's 308. Signals is already at parity, and
slightly under it.** The 1663-against-308 figure that put this screen first in the queue is
protected honesty prose, exactly as Fleet turned out to be.

**No change made and none is warranted.** Cutting to move the total would mean cutting a
distinction, which is forbidden as firmly as deleting one.

The composition side stands: `regionsBeside` 0 against the mock's 1, behind by one pairing. That is
a real but small gap, and smaller than `codebase`'s.

**A caveat on this run, stated rather than buried.** Two panels were still loading when the audit
fired, contributing 210 characters of "Loading…" text. That inflates the total and does not touch
the discretionary figure, which is what the verdict rests on. A future run should wait for the panels
rather than only for `main`.

---

# The instrument was not reproducible, and every number above it is superseded

**This is the most important finding in this file and it invalidates my own earlier conclusions.**

Running the eval twice in a row returned different answers. `api-services` read 4 regions on one run
and 0 on the next; `remediation` read 1 and then 0. **A measurement that changes between identical
runs cannot order work**, and I had already used it to tell the coordinator that Fleet was at parity
and needed nothing.

## The cause

Panels fetch independently of the document. The probe waited for `main` to have laid-out text, which
happens long before the panels resolve — so it measured whatever had rendered by then, and *which*
panels had rendered varied run to run. A panel still loading has no heading, so it counted as no
region. A panel that failed wrote error prose, which counted as console prose.

Both failure modes return a plausible number rather than an error. That is the third time in this
work that a defect survived because the output looked reasonable, and it is exactly the rule the
coordinator wrote after the second: *a visual metric is checked against a screen whose answer is
already known before it is allowed to order work.*

## The fix, and the proof it worked

Readiness now requires that no panel is still loading, and the probe **refuses outright** — throws,
rather than returning numbers — if any panel is showing a fetch failure. Two consecutive runs are now
byte-identical.

## The stable numbers, which supersede every table above

| page | mock regions | built regions | mock prose | built prose |
|---|---|---|---|---|
| fleet | 0 | **12** | 340 | 1777 |
| codebase | 2 | 1 | 282 | 1015 |
| api-services | 1 | **4** | 291 | 2236 |
| signals | 1 | 0 | 308 | 1663 |
| observe | 1 | 0 | 294 | 3085 |
| remediation | 1 | 1 | 579 | 2945 |
| settings | 1 | 1 | 324 | — |

**Composition:** the console is *ahead* of the drawing on `fleet` (12 against 0) and `api-services`
(4 against 1), level on `remediation` and `settings`, and behind by one pairing on `codebase`,
`signals` and `observe`. The corrected picture is even less alarming than the corrected-but-unstable
one, and the "one vertical stack" complaint is not supported anywhere.

**Prose:** every screen carries substantially more prose than the drawing. That number cannot be
acted on until each screen has a protected-content audit, because the two screens audited so far
both turned out to be dominated by protected sentences.

## What this means for the conclusions already reported

- **"Fleet is at parity on prose" is withdrawn.** It rested on 915 characters measured mid-load; the
  settled figure is 1777. The protected/discretionary split has to be re-taken.
- **"Signals is at parity" is provisional.** Its audit used the same wait-for-`main` readiness, so
  its 1571 total was probably also unsettled, even though its *classification* — 1083 characters
  carrying the never-measured distinction — stands on its own and does not depend on the total.
- **The composition conclusions strengthen rather than weaken.** Fleet needing no layout work was
  right for a better reason than I gave.

**No layout or prose work should be ordered off any number in this file taken before this section.**
The instrument is trustworthy from here; the readings before it are not.

---

# Fleet, re-audited on the fixed instrument — and one cut made

**`prose-audit.mjs` carried the same defect the eval had** and was fixed the same way before this
run: it waited only for `main` to have text, so it could count a skeleton's "Loading…" as console
prose. It now waits for every panel to settle and refuses if any shows a fetch failure.

Fleet, settled: **1777 characters across 16 paragraphs.**

| Class | Chars | What it is |
|---|---|---|
| **Protected** | **1327** | change-unit grain (twice), staleness-not-liveness, absence-is-not-zero, three-attempts-one-finding, the fleet-vs-codebase scope sentence, the standing-limits framing, and the completeness statement |
| **Discretionary** | **450** | the route question, two figure labels, one panel description, and one string repeated once per card |

Against the mock's 340, Fleet's discretionary prose was **450 — over by 110**, which is a real gap
and the first one this work has found that survives a correct measurement.

## The cut, and why it is the only one available

`Git repository · Monitored by Sync` rendered on **every** repository card — 170 of those 450
characters. It carries none of the four distinctions, and both halves are already established by
context: a reader looking at the Sync console's own repository list knows the rows are repositories
and knows Sync is watching them. **Deleting it removes no fact.**

Removed, test-first. Verified by re-running the audit rather than by asserting:

| | before | after |
|---|---|---|
| total | 1777 | **1607** |
| paragraphs | 16 | 11 |
| discretionary | 450 | **280** |

**280 against the mock's 340 — Fleet is now under parity on discretionary prose**, and the four
protected sentences were confirmed still present in the same run rather than assumed.

Nothing else on Fleet is available to cut. The remaining 280 characters are the route's own question,
two figure labels and one panel description, each of which says something the screen does not
otherwise say.

---

# The re-audit, and a fourth instrument defect found by running it

## The auditor was still wrong, and codebase found it

`prose-audit.mjs` refused on *unreachable*-style wordings and did not know about a **not-found**
panel. The codebase screen renders two — `/coverage` and `/observed` both 404 — so the auditor
counted **302 characters of error prose as console prose** and reported a number that looked fine.

That is the fourth defect of this exact shape in this work: markup technique, harness
authentication, half-rendered pages, and now an incomplete refusal list. All four returned a
plausible number rather than an error.

**Fixed structurally rather than by adding another phrase.** Every failed panel renders `ErrorState`,
and every `ErrorState` with a retry renders a `Try again` control, so the *control* is the marker.
The phrase list stays for panels that predate the retry affordance. Both instruments now share it,
and the auditor now refuses codebase outright rather than measuring it.

## What the audit found, per screen

**`fleet` — audited, one cut made, now under parity.** 1777 characters, 1327 protected, 450
discretionary against the drawing's 340. The repeated card description was removed; discretionary is
now 280. Recorded in full in the section above.

**`observe` (`/detectors`) — 3085 characters, and roughly 80% of it is protected.** Eight paragraphs
carry distinctions outright: the rung as a class of evidence rather than a position on a good-to-bad
scale; the refusal to compute a precision figure with no labelled corpus behind it; the fleet-wide
versus repository scope sentence; *"Every bar is the same length because it is a composition, not a
quantity… drawing that as length would render the smaller ones as a sliver indistinguishable from
nothing"*; the once-each counting grain; *"an absence, which is not the same fact as a rung this
console does not have"*; and *"that absence is indistinguishable from a detector that does not
exist"*. **≈2468 protected against ≈617 discretionary**, and the discretionary remainder is the
route's own question plus figure labels that are the counts themselves. **No cut available.**

**`codebase` — cannot be audited, and the reason is a defect worth more than the audit.** Both its
telemetry routes 404 for a repository that `/api/repositories` lists. Filed as **B147**.

**`signals` — classification stands, total to be re-taken.** Its 1083 characters carrying the
never-measured distinction were classified by reading the sentences, which does not depend on the
total; the total itself was measured before the readiness fix and should be re-run.

**`api-services`, `remediation`, `settings` — not yet audited.** Deliberately not guessed at.

## The composition gaps are unchanged and still small

One pairing each on `codebase`, `signals` and `observe`. Not attempted in this unit: `codebase`
cannot currently be measured at all, and changing a layout while its own screen refuses to report is
how a proxy gets optimised.
