# Interface originality

Read this before designing any screen, and before opening anything under
`docs/superpowers/references/`.

## The rule

**The interface is ours. Every screen, every layout, every component, every word on it.**

Competitor products are studied for concepts, ideas, and efficient workflows and pipelines. They
are never studied for how the screen should look. Those are different activities and this rule
exists so nobody conflates them under deadline.

## Why this is written down rather than assumed

This repository contains twenty-two screenshots of six competitors' shipping interfaces, captured
deliberately and committed on purpose. They are a research artifact. Without a stated rule, an
agent arriving cold — reasonably, helpfully — reads a directory of competitor screenshots as a
design target, because that is what a directory of screenshots usually is.

It is not one here.

## What may be taken

Ideas about the problem, not renderings of the solution:

- **A concept.** That confidence is more honest when defined by the class of evidence behind it
  than by a feeling is an idea about truth-telling. Sync already reaches the same conclusion by its
  own route — the provenance rung — and would keep it if no competitor existed.
- **A vocabulary's shape.** That a reason for giving up should be a closed set of codes rather than
  free text, because free text cannot be aggregated and a promise to learn from failures needs a
  schema that can answer the question. The shape transfers. **The values do not** — they come from
  Sync's own routing predicates, and a vocabulary borrowed wholesale would describe somebody else's
  product.
- **A workflow or pipeline arrangement** that is genuinely more efficient, judged on its merits
  against Sync's own constraints.
- **A negative finding.** Learning that an approach does not work, or costs more than it returns,
  is worth as much as learning that one does.

## The conventions of the form, which are learnable

**Amended 2026-08-06, and the amendment is the important part of this file.** The list below used to
open with "a layout, a screen composition, a navigation shape, a visual hierarchy" and nothing
distinguished those from identity. Read literally — and it was read literally, correctly, by every
agent that met it — that forbade a sidebar, a breadcrumb, a two-column detail and a display type
step, because a competitor has each of them. The console that resulted is measured in
`docs/superpowers/reports/2026-08-06-why-the-console-came-out-flat.md`: a type range of 2.0 against
a 3.4 bar, seven side-by-side placements in the entire application, and one vertical stack on every
screen.

A control plane has a grammar, the same way a form has one. **These are conventions, not
inventions, and learning them from anything is permitted:**

- A persistent navigation rail, and a second contextual level inside it.
- A breadcrumb or scope switcher that says what contains what.
- A page header that names the screen and says what it is for.
- A control bar: scope, search, and one primary action.
- A footer bar owning pagination and the record count.
- A detail that opens in a drawer instead of navigating away.
- A fact rendered as a tile — label register above value register.
- A metric panel whose value sits above its own evidence.
- A type ramp with a display step, and a frame that is larger than the gaps inside it.

Taking these is not copying, any more than using a table is copying. **What makes a screen ours is
what we put in them, what we refuse to put in them, and how the two are arranged.**

## What may not be taken

- A component's appearance, or a component built by looking at a screenshot.
- Copy, labels, microcopy, or a turn of phrase lifted from their interface.
- A colour system, a wordmark, iconography, illustration, or motion design.
- **The specific arrangement that makes a screen recognisably theirs** — which is a judgement, and
  the test is whether somebody who knows the reference would see it rather than see a control plane.
- A feature reproduced because a competitor has it, absent an argument from Sync's own users and
  Sync's own graph.
- **Any claim their screen makes that our data cannot support.** This is the one that matters most
  and the one a beautiful reference makes tempting: Superlog's incident view is the best thing in
  the reference set and it carries `Root cause confidence: 9`. Take its structure, refuse its
  scalar. Composition and honesty are independent axes, and conflating them is how "we must not
  lie" became "we must not compose".

## How to use the reference material

When a note names something worth adopting, it must be restated as a problem before it becomes a
design. "Superlog shows X in a panel" is not adoptable. "A reviewer needs to know why a run gave up
without leaving the run" is, and what Sync builds to answer it is Sync's own.

If a proposed change cannot be justified without pointing at a competitor's screen, it has not been
justified. Delete the pointer and make the argument from the graph, the operator, and the product
position — or drop the change.

## The Supabase carve-out (owner-authorized, 2026-08-06)

`specs/2026-08-06-sync-console-supabase-substrate-design.md` records the owner's ruling: Supabase's
component code (`github.com/supabase/supabase`, Apache-2.0) is adopted at code level as the
console's foundation — vendored nearly verbatim under `web/src/vendor/supabase/`, with attribution
in `web/NOTICE`. For this one source, "a component's appearance" and "a component built by looking
at a screenshot" are no longer refusals; the code itself is taken.

The carve-out does not touch the rest of this rule. Identity elements stay excluded — the Supabase
wordmark, logo, identifying iconography, marketing and product copy. Every other reference is
governed exactly as before. And no vendored component may assert a claim our data cannot support:
a slot for a confidence score renders the rung instead, per the spec's section 6.

## The reason this is not merely legal caution

Sync's position is that competing tools present a black box and a result, and ask a reviewer to
trust the output on faith. The console exists to show the system's reasoning instead. An interface
assembled from screenshots of those same tools would inherit the assumptions that produced the
problem, and would arrive looking like the thing it is supposed to replace.

Copying the surface is how you lose the argument you built the product to make.
