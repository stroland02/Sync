---
paths:
  - "web/**"
  - "DESIGN.md"
  - "docs/superpowers/references/**"
---

# The interface is ours

**Amended 2026-08-26 by the owner, and this amendment is the first thing to read.** The rule that
opened this file — *competitors are studied for concepts, workflows and negative findings, never
for how a screen should look* — is **retired**. It was written to stop the console arriving as a
clone. What it actually produced is the failure `reports/2026-08-06-why-the-console-came-out-flat.md`
measures: a type range of 2.0 against a 3.4 bar, seven side-by-side placements in the whole
application, one vertical stack on every screen. Two carve-outs had already eaten it from the edges
— Supabase at code level, Mobbin as visual reference — and the owner's ruling completes that.

**Visual reference is unrestricted.** Any source may inform how a screen looks: composition,
density, motion, depth, elevation, the shape of a pane, how a mature product arranges a working
surface. Build the most ambitious version, not the safest one.

Four things still do not transfer, and none of them is about taste:

- **Identity.** A wordmark, logo, or identifying iconography belongs to whoever owns it.
- **Copy.** Their labels, their microcopy, their turns of phrase.
- **A claim our data cannot support.** The one that matters, and the one a beautiful reference
  makes tempting: the best incident view in the reference set carries `Root cause confidence: 9`.
  Take its structure, refuse its scalar. **Composition and honesty are independent axes** —
  building beautifully has never required claiming more than was measured.
- **Anything unlicensed.** Code is adopted under its licence, with attribution.

What follows is kept because the arguments are worth reading, but where any of it contradicts the
four lines above, the four lines win.

---

Every screen, layout, component and word on it is ours to make. Competitors are studied for
concepts, workflows, negative findings **and, since 2026-08-26, appearance.**

**Scoped as of 2026-08-19.** This loaded on every turn because the 50 competitor screenshots under
`references/screenshots/` can be opened from anywhere, and no path pattern could fence that.
`scripts/hook_guard_reads.py` blocks reading them deterministically, so the rule now costs a Python
session nothing. The notes beside them stay readable — they are the adoptable half.

## What transfers

- **A concept.** That confidence is more honest when defined by the class of evidence behind it
  than by a feeling. Sync reaches that by its own route — the provenance rung — and would keep it
  if no competitor existed.
- **A vocabulary's *shape*.** That a reason for giving up should be a closed set of codes rather
  than free text, because free text cannot be aggregated. The shape transfers; **the values do
  not** — ours come from Sync's own routing predicates.
- **A workflow arrangement** that is genuinely more efficient, judged against Sync's constraints.
- **A negative finding.** That an approach does not work is worth as much as that one does.

## The conventions of the form, which are learnable

**Amended 2026-08-06, and this is the important half of the file.** The forbidden list used to open
with "a layout, a screen composition, a navigation shape, a visual hierarchy", and every agent read
it literally and correctly — which forbade a sidebar, a breadcrumb, a two-column detail and a
display type step, because a competitor has each. The result is measured in
`reports/2026-08-06-why-the-console-came-out-flat.md`: a type range of 2.0 against a 3.4 bar, seven
side-by-side placements in the whole application, one vertical stack on every screen.

A control plane has a grammar, the way a form does. **These are conventions, not inventions, and
learning them from anything is permitted:** a persistent navigation rail and a contextual second
level · a breadcrumb or scope switcher · a page header naming the screen · a control bar with
scope, search and one primary action · a footer owning pagination and the record count · a detail
in a drawer · a fact as a tile, label register above value register · a metric panel with its value
above its evidence · a type ramp with a display step.

Taking these is not copying, any more than using a table is. **What makes a screen ours is what we
put in them, what we refuse to put in them, and how the two are arranged.**

## What does not transfer

- A component's appearance, or a component built by looking at a screenshot.
- Copy, labels, microcopy, or a turn of phrase from their interface.
- A colour system, wordmark, iconography, illustration or motion design.
- **The specific arrangement that makes a screen recognisably theirs** — a judgement, and the test
  is whether somebody who knows the reference would see it rather than see a control plane.
- A feature reproduced because a competitor has it, absent an argument from Sync's own graph.
- **Any claim their screen makes that our data cannot support.** This is the one that matters most
  and that a beautiful reference makes tempting: the best incident view in the reference set
  carries `Root cause confidence: 9`. Take its structure, refuse its scalar. **Composition and
  honesty are independent axes**, and conflating them is how "we must not lie" became "we must not
  compose".

## Using the material

A note naming something worth adopting must be **restated as a problem before it becomes a design**.
"Superlog shows X in a panel" is not adoptable. "A reviewer needs to know why a run gave up without
leaving the run" is, and what Sync builds to answer it is Sync's own.

**If a proposed change cannot be justified without pointing at a competitor's screen, it has not
been justified.**

## The Supabase carve-out (owner-authorized, 2026-08-06)

`specs/2026-08-06-sync-console-supabase-substrate-design.md` records it: Supabase's component code
(Apache-2.0) is adopted at code level, vendored under `web/src/vendor/supabase/` with attribution in
`web/NOTICE`. For that one source, "a component's appearance" is no longer a refusal.

Identity elements stay excluded — wordmark, logo, identifying iconography, marketing copy. Every
other reference is governed exactly as above. And **no vendored component may assert a claim our
data cannot support**: a slot for a confidence score renders the rung instead.

## The Mobbin carve-out (owner-authorized, 2026-08-25)

The owner holds a Mobbin Pro subscription and ruled that its library may inform **how our screens
look**, not only how they work. That is an explicit amendment to "What does not transfer" above,
and it is recorded here rather than in a chat message because the paragraph it modifies is the one
every agent reads.

**What the ruling changes.** Mobbin screens, sections and flows may be used as visual reference —
composition, density, the shape of a pane, how a mature product arranges a working surface.

**What it does not change**, because none of it was about references:

- **The Stitch set remains the primary visual authority.** Where Mobbin and Stitch disagree about
  our console, Stitch wins; Mobbin fills gaps Stitch does not draw.
- **Identity elements stay excluded.** Wordmark, logo, iconography, illustration, marketing copy.
- **No screen may assert a claim our data cannot support.** This is the refusal that matters most
  and the one a beautiful reference makes tempting: take a structure, refuse its scalar. The best
  incident view in the reference set carries `Root cause confidence: 9`, and we still will not.
- **A change still has to be justifiable without pointing at the reference.** "Mobbin shows X"
  remains not an argument; the problem it solves for an operator here is.

The competitor screenshots under `references/screenshots/` stay hook-blocked. That guard was about
one specific corpus and the reasoning that put it there is untouched by this ruling.

## Why this is not merely legal caution

Sync's position is that competing tools present a black box and ask for trust. An interface
assembled from screenshots of those tools would inherit the assumptions that produced the problem,
and arrive looking like the thing it replaces. **Copying the surface is how you lose the argument
you built the product to make.**
