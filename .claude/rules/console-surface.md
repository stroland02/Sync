---
paths:
  - "web/**"
  - "DESIGN.md"
---

# The console's surface

You are editing a screen. `DESIGN.md` is the authority for every visual value; this file is what
binds while you work, and it deliberately does not restate a single token.

## `DESIGN.md` is a contract, not a palette

Every colour, type step, spacing value, radius, row height and elevation level is declared there
with the arithmetic that proves it safe. **A new token, a third elevation level, a fourth spacing
value or a seventh type step is a decision argued in that file — never a value added here.** The
contrast floor is 5.05:1, measured across declared tokens and against rendered pixels; a pairing
that regresses below it is a bug in the ramp, not an acceptable trade.

Three shapes of that contract are worth knowing before you reach for a class, because each was a
defect first:

- **The surface ramp is indexed by job, not by depth.** Two steps carry depth and two carry
  interaction state, and no step does both. State is always a named step, never an alpha overlay —
  an alpha composites differently against whichever depth step sits under it, so one declaration
  would mean several different colours depending on where it landed.
- **Type is assigned by role, not by size.** Weight, line height and tracking travel with the step,
  so `text-page` is the whole decision rather than three of them. Tracking belongs to the heading
  role; a step reached for as in-row emphasis takes `tracking-normal` alongside it.
- **Three spacing tokens, and exactly two named exceptions**, both page-layout numbers used once
  per view. A raw Tailwind spacing utility inside `features/` duplicates one of the three under a
  different name — measured at 19 token spellings against 128 raw ones, two of them landing on the
  same pixel value.

Dark-only as of 2026-08-05, on the owner's explicit instruction. The theme resolver, its storage
key and its `prefers-color-scheme` listener are deleted rather than disabled, so a component that
branches on `prefers-color-scheme` again is a regression against a recorded decision, not a
feature.

## What a screen may not assert

**No composite score, health figure, traffic light, green dot, liveness pulse or count-up.**
`CLAUDE.md` carries the argument; this is where it gets reached for, because a design system is
precisely the moment somebody wants a coloured badge. The provenance rung stays monochrome at both
levels and is never a hideable column.

Colour claims a judgement, motion claims a time, depth claims a relationship. Three channels may
carry a claim, because the data holds one: the run outcome, the error state, and absence. A status
colour never travels alone — it ships with an icon and a word, because colour is never the only
channel, whatever it measures.

## The protected distinctions

**Amended by the owner, 2026-08-19.** This section used to protect twenty-four specific sentences,
reproduced with file and line in
`docs/superpowers/plans/2026-08-05-sync-console-architecture.md:102-207` (*Establish 2*): restyling
allowed, deleting, shortening, collapsing behind a disclosure or moving into a tooltip refused. The
owner's instruction is that a screen carrying its full explanation as body prose is cluttered, and
`CLAUDE.md` carries the resolution. It is repeated here in the form you need while editing a screen.

**The distinction is protected. The paragraph explaining it is not.**

- **Visible, always, in the fewest words that are still honest**: the claim itself. *not measured
  yet* · *no source attached* · *never indexed* · *all workspaces* · *counted before this filter* ·
  *static evidence*. A reader who never hovers must not be misled about what a figure covers or
  whether it was measured at all.
- **Behind the ⓘ**: why that distinction exists, what the alternative reading would have been, and
  what the payload can and cannot support. This is the material that used to sit in a paragraph.

Two things are still refused outright, and neither was relaxed:

- **A figure with no indication that its scope or its emptiness is qualified.** A fleet-wide number
  under a workspace heading with nothing saying so is the same defect it always was, whether the
  qualification was deleted or merely never written.
- **Rendering one nothing as another.** A measured zero drawn as an absence, or an absence drawn as
  a zero, is the failure this console exists to replace. The `ⓘ` does not license it; a short label
  that says which nothing it is, is what does.

**Verification for any change to a screen is still re-reading its own diff — now asking a different
question.** Not *was a sentence deleted* but *can a reader who does not hover still tell what this
figure covers and whether it was measured*. If the answer is no, the claim was moved when only the
argument should have been.

## Measure, do not describe

Four surfaces have been studied for this console: three landing pages and one published control
plane. Every number came from Chrome at 1440×900 reading `getComputedStyle` over every element in
the document, with a real pointer moved onto a control so `:hover` genuinely matched — not from
markup, and not from looking.

**The method is the durable part, not the numbers.** The control plane contradicted four of the
fourteen invariants the three landing pages had agreed on, and it could only do that because both
were measurements. A described impression cannot be contradicted by anything; it can only be
argued with.

`.claude/rules/interface-originality.md` binds the whole exercise and loads on every turn. Nothing
under `docs/superpowers/references/screenshots/` is opened.
