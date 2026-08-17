# The reference hierarchy, and an eval that stops us replicating by eye

Recreating the drawn console in the built one has been *tediously difficult* — the owner's words, and
the strongest signal in this plan. This document says why it is difficult, ranks the reference
material so nobody has to guess which artifact is authoritative, and specifies an eval that replaces
comparing-by-eye with comparing-by-measurement.

## Why the console is not getting visually better, and it is a coordination failure

The owner says we are not getting the results we want on the UI. That is correct, and the cause is
not the console lane's execution -- it is what the lane was asked for. **Audited against `git log`
rather than from memory: fourteen console units landed on 2026-08-17. Seven of them were signing or
re-signing Gate 3. Zero were visual fidelity.**

The full list is `W340` servable, `W341`/`W342`/`W343`/`W345`/`W347`/`W350`/`W353` Gate 3 paperwork,
`W344` stock-take, `W346` the empty-state fix, `W348`/`W349` the abandoned screen and retry, `W351`
deployment identity, `W352` focus. Every one is *correctness* or *honesty*. Every one was executed
well. **None of them could have made a screen look better, because none of them was about how a
screen looks.**

Four things follow, and the first three are the coordinator's to fix.

**1. I dispatched correctness work and called it console work.** "Does any screen assert a number
nothing computed" is a real question and Gate 3 is worth having signed. It is not the same question
as "is this good", and asking only the first while expecting the second is how a lane produces
fourteen excellent units and a console that looks the same.

**2. This project has already diagnosed this once and it recurred.**
`reports/2026-08-06-why-the-console-came-out-flat.md` measured a type range of 2.0 against a 3.4
bar, seven side-by-side placements in the entire application, and one vertical stack on every
screen. The cause recorded there was `interface-originality.md` read literally -- it appeared to
forbid a sidebar, a breadcrumb, a two-column detail and a display type step, because a competitor
has each. The rule was amended on 2026-08-06 to say the conventions of the form are learnable. **I
have spent today re-stating the strict half of that rule** while routing the console lane at honesty
items, which risks re-creating exactly the chilling effect the amendment exists to prevent.

**3. The bars we measure are proxies, not quality.** Type range, frame ratio, prose-to-data. All
three are necessary, none is sufficient, and a screen can clear all three and still be flat. When
the only things you can count are proxies, the proxies become the target.

**4. The demo has never been queried.** The visual target has existed as ~100KB of renderable source
for weeks and not one computed value has been read from it. That is the single largest available
lever and the rest of this document is about pulling it.

### What changes

- **Visual fidelity gets its own axis, its own evidence and its own sign-off**, separate from Gate 3.
  Honesty being signed must stop being read as the console being finished.
- **The demo is the bar, and copying it exactly is not an originality violation -- it is the point.**
  `interface-originality.md` governs *competitors*. `docs/console-mock/` is ours. A lane hesitating
  to match our own drawing has misread the rule, and that hesitation has a measured history here.
- **The dispatch mix changes.** Alternate fidelity units with correctness units rather than filling
  a queue with one and expecting the other.
- **The question I ask changes.** I have been asking *is it true*. The console also has to be asked
  *is it good*, and the second needs different evidence: the built screen beside the drawn one, both
  measured, not a passing test.

## Why it is difficult, stated before proposing anything

Four causes, each checked against the tree rather than assumed.

**We compare a picture to a running application.** `docs/console-mock/screens/` holds eleven PNGs.
A PNG cannot be queried. Every comparison against it is a person looking at two things and forming
an impression, which is unrepeatable, unassignable, and impossible to put in a gate.

**The dev captures are five weeks stale.** `docs/superpowers/reports/screens/` contains one dated
directory: `2026-08-07`. The console was rebuilt after that — the whole M7 substrate port, the
mock-parity plan, `DetailGrid`, the Fleet grain, Settings as a grid. **There is currently no
current picture of the built console at all**, so "compare dev to the demo" has nothing on one side.

**The most useful artifact is the one nobody uses.** `docs/console-mock/Sync Console.dc.html` and
`Sync Console v2.dc.html` are ~100KB each. They are not screenshots — they are the mock as a
*document a browser renders*. That means every property the built console can be asked for, the mock
can be asked for too: computed colour, font size, spacing, radius, grid template, element count.
Nobody has ever queried them.

**"Similar" is not a criterion.** Two screens can differ in fifty ways. Without naming which
properties matter, a comparison produces a list nobody can act on and an argument nobody can settle.

## The hierarchy

Ranked by authority. When two disagree, the higher one wins, and the ranking exists so that question
never needs asking twice.

### Tier 1 — the demo model, and it is the visual target

`docs/console-mock/`. **This is ours**, drawn for this product, and it is the only tier whose
*appearance* is a target rather than a concept.

| Artifact | What it is | What it is for |
|---|---|---|
| `Sync Console.dc.html`, `Sync Console v2.dc.html` | the mock as rendered source | **the measurable reference** — query it, do not eyeball it |
| `screens/01-fleet.png` … `11-drawer.png` | eleven per-screen captures | the human-readable target; one per route |
| `demo.mp4`, `demo.gif` | the forty-second tour | motion and sequence, which a still cannot carry |
| `index.html`, `README.md` | the tour's own page and provenance | why the mock exists and what it claims |
| `_ds/`, `support.js` | design-system assets the mock loads | where a token's *drawn* value can be read |

**Corrected 2026-08-17, and the correction is the coordinator's.** This plan originally said *v2
supersedes v1 where they differ*. I wrote that from filename order without opening either file, and
the first run of the eval refuted it on three independent measurements:

- **v2 is a light theme** (`rgb(242,242,243)`) against a dark-only ruling the owner recorded on
  2026-08-05.
- **v2 draws no `border-radius` at all**, against `DESIGN.md`'s two declared radius tokens.
- **v2's type range is 1.45**, against a console deliberately rebuilt to clear 3.4.

And decisively for this eval's own purpose: **v2 draws 6 side-by-side regions to v1's 17**, so
following it would have made the console *worse* at precisely the complaint the eval exists to
measure.

**The ruling is therefore: `Sync Console.dc.html` (v1) is the appearance target. v2 supersedes on
vocabulary only** — where it says `Codebases` and v1 still says `Fleet`. Any eval must state which
it measured, and it must measure v1 for appearance.

### Tier 2 — Superlog and the competitor set

`docs/superpowers/references/`. **Concepts only, and this is not a preference.**
`.claude/rules/interface-originality.md` binds it: competitors are studied for ideas about the
problem, never for how a screen should look. A conventional grammar — a rail, a breadcrumb, a
two-column detail, a metric tile — is learnable from anything. A specific arrangement that makes a
screen recognisably theirs is not.

So Tier 2 informs *what a screen must answer*. Tier 1 informs *what it should look like*. An eval
that scored the built console against a competitor's rendering would be measuring the wrong thing
and breaking a standing rule to do it.

### Tier 3 — everything else

Prior captures (`reports/screens/`), the gap reports, `DESIGN.md`'s token contract, and the
specification's hierarchy block. These are history and constraint: useful for *why* something is the
way it is, not authoritative about what it should become.

## The eval

**One command. Both sides measured the same way. Per-page, per-property deltas.**

The insight that makes it possible is that the mock is a document. Open the mock HTML and the built
console in the same browser, ask both the same questions through `getComputedStyle`, and diff the
answers. That converts *"this doesn't look like the demo"* into *"Fleet's card radius is 4px against
the mock's 8px"* — assignable, fixable, and re-runnable.

**What it measures**, chosen because each is objective and each is something a reader notices:

- type ramp — computed `font-size` and `font-weight` per heading level, and the ratio between the
  largest and smallest step
- colour — computed foreground, background and border on the primary surfaces, against `DESIGN.md`'s
  tokens rather than against raw hexes
- spacing and radius — padding, gap and `border-radius` on cards, tables and controls
- composition — how many elements sit side by side, since "one vertical stack where it should be a
  grid" was the owner's original complaint and it is a count
- density — data cells and figures per screen, the ratio the Fleet work already moved from 125.2 to
  25.0

**What it must not do.** It must not score. A single similarity number over these properties would
be exactly the composite figure this console refuses everywhere else, and it would hide which of the
five moved. It reports per-property, per-page, with the mock value and the built value side by side.

**Where a difference is deliberate, it is recorded rather than fixed.** The console has honesty
elements the mock does not: the mock invents fixture numbers on Settings and the built console
refuses to render them. That is the built console being *better than* the demo, which the owner's
instruction explicitly allows — "similar to or better than". Those get an entry in an exceptions
file with the reason, and the eval reads that file so a known-better difference stops being noise.

## What already exists, so we build as little as possible

Researched 2026-08-17. Two categories, and the second is the one that matches this problem.

### Screenshot diffing — mature, and not what we need first

`BackstopJS` (open source, ~40 comparisons a minute), Playwright's built-in visual comparisons, and
`Argos` (surfaces diffs in pull requests) all solve *did this change since last time*. That is
regression, and it is worth having later. **It does not answer our question**, which is *how far is
the built console from a drawing*, because a pixel diff between two different renderings of two
different documents is noise end to end.

### Design-token extraction — this is the one

Several projects do exactly what this plan proposes: drive a headless browser over a page, read
**every computed style off the live DOM**, and emit structured tokens.

- **`d-extract`** — extracts computed styles, layout patterns (grid, flex, containers), responsive
  behaviour across breakpoints and interaction states; emits W3C design tokens and CSS custom
  properties; explicitly supports **comparing multiple sources and syncing a live page to local
  tokens**. Ships as a CLI *and a Claude Code plugin*.
- **`dembrandt`** — Playwright renders, reads computed styles, groups typography, detects spacing
  patterns, returns tokens.
- **`extract-design-system`** — tokens to JSON and CSS custom properties; ships as an **agent skill**
  as well as a CLI.
- **`html-style-extractor`** — formats an extraction into a report deliberately shaped for an LLM,
  i.e. a high-fidelity prompt for reproducing a UI.

**Why this matters for the stated pain.** "Tediously difficult to replicate" is what happens when a
model is handed a PNG and asked to match it. Handed a *token set* — this radius, this ramp, this gap
— it is doing arithmetic instead of interpretation. That is the difference between the two
categories, and it is why the extraction tools are the ones to trial.

**Three cautions before adopting any of them.**

1. **They are built to crawl public sites; our target is a local file.** `Sync Console.dc.html` will
   need serving over `http://` for a headless browser to treat it normally. Verify on the actual
   mock before committing to a tool, rather than trusting the README.
2. **We already own most of the primitives.** `superpowers-chrome` gives Chrome DevTools Protocol
   control, `DESIGN.md` is already a token contract with arithmetic behind every value, and Lane B
   has run `getComputedStyle` walks by hand across ten routes. The missing piece is not a browser or
   a token format — it is that **nobody has ever pointed those at the mock**. A hundred-line script
   using what we have may beat a dependency; trial both and say which, rather than adopting on
   reputation.
3. **A tool that emits a Tailwind or shadcn theme is not thereby authoritative.** `DESIGN.md` is the
   token contract and its values carry contrast arithmetic. An extractor's output is an *observation
   of the mock*, to be compared against that contract — never a replacement for it.

## First run, 2026-08-17: the method works and the news is good

`reports/2026-08-17-visual-eval-first-run.md`, with nine routes captured at 1440x900 in
`reports/screens/2026-08-17/` — the stale-capture cause is closed.

**The central claim held.** The mock renders headless and its computed styles read exactly like the
console's. What had been five weeks of comparing by eye is now about ninety seconds of comparing by
measurement.

**The tool verdict was measured rather than argued, and the in-house script won with zero
dependencies added.** All four candidate extractors are built to crawl public sites and answer a
*superset* question — what tokens does this page use — which still has to be reduced to the twelve
properties before anything can be diffed. That is not a permanent verdict: if the eval grows toward
full token extraction across breakpoints and interaction states, `d-extract` becomes the better
answer.

**The finding on Fleet, and it is a better position than anyone assumed.** Colour and radius match
the mock **exactly** — both OKLCH values, both radii. What differs is composition and prose:

| | built | mock |
|---|---|---|
| side-by-side regions | 4 | 17 |
| prose characters | 915 | 340 |

So the owner's original complaint — *one vertical stack where it should be a grid, and Fleet carries
more prose than data* — is now **countable**, and the gap is structural rather than a palette
problem. Palette problems are a rewrite. Composition problems are a layout pass.

## Sequence

1. **Capture the built console now.** There is no current picture. Every screen, at a fixed viewport,
   into a dated directory beside the 2026-08-07 one.
2. **Extract the mock's measurements** from the `.dc.html` source, per screen.
3. **Diff, and report per property.**
4. **Fix what is worse; record what is deliberately different.**
5. **Make it repeatable** — a command anyone can run, so the next reader does not start where this
   one did.

## What this does not solve

It measures appearance, not behaviour. A screen can match the mock exactly and still assert a number
nothing computed — that is Gate 3's job and Gate 3 is signed. The two are complementary and neither
substitutes for the other.
