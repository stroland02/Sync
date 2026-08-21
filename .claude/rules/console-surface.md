---
paths:
  - "web/**"
  - "DESIGN.md"
---

# The console's surface

`web/CLAUDE.md` carries what a screen may claim and how prose is placed. This is the visual
contract, and it deliberately restates no token value.

## `DESIGN.md` is a contract, not a palette

Every colour, type step, spacing value, radius, row height and elevation level is declared there
with the arithmetic proving it safe. **A new token, a third elevation, a fourth spacing value or a
seventh type step is a decision argued in that file — never a value added here.** The contrast floor
is 5.05:1, measured against rendered pixels; a pairing below it is a bug in the ramp.

Three shapes of the contract, each a defect first:

- **The surface ramp is indexed by job, not depth.** Four steps carry depth and three carry
  interaction state, and no step does both. **State is a foreground alpha owned by one primitive** —
  `DESIGN.md` reversed this with the substrate, because an opaque state step was invisible on a card
  and correct only on the page. What did not relax is the reason the old rule existed: **no `bg-x/10`
  or `text-y/70` spelled inline in a component**, because an alpha at a call site composites against
  whichever depth sits under it and one declaration would mean several colours.
- **Type is assigned by role, not size.** Weight, line height and tracking travel with the step, so
  `text-page` is the whole decision rather than three of them.
- **Four spacing tokens and exactly one named exception**, the 32px between-panel gap. A raw Tailwind
  spacing utility inside `features/` duplicates one of the four under another name — measured at 19
  token spellings against 128 raw ones, two landing on the same pixel.

Dark-only since 2026-08-05, on the owner's instruction. The theme resolver, its storage key and its
`prefers-color-scheme` listener are deleted rather than disabled, so a component branching on
`prefers-color-scheme` is a regression against a recorded decision.

## What a screen may not assert

`web/CLAUDE.md` holds the refusal; this is where it gets reached for, because a design system is
exactly the moment somebody wants a coloured badge.

**Colour claims a judgement, motion claims a time, depth claims a relationship.** Three channels may
carry a claim because the data holds one: run outcome, error state, absence. **A status colour never
travels alone** — it ships with an icon and a word, because colour is never the only channel.

The provenance rung stays monochrome at both levels and is never a hideable column.

## The protected distinctions

**Amended by the owner, 2026-08-19.** This protected twenty-four specific sentences from being
shortened or moved into a tooltip. It blocked ordinary cleanup, and seven of them cited deleted
files. `web/CLAUDE.md` carries the replacement; the form you need while editing is:

**The distinction is protected. The paragraph explaining it is not.**

- **Visible always, in the fewest honest words:** the claim itself — *not measured yet* · *no source
  attached* · *never indexed* · *all workspaces* · *counted before this filter* · *static evidence*.
- **Behind the ⓘ:** why the distinction exists, and what the payload can and cannot support.

Two refusals were not relaxed: **a figure whose scope or emptiness is qualified nowhere**, and
**rendering one nothing as another**. The ⓘ does not license either.

**Verification is still re-reading your own diff, now asking a different question.** Not *was a
sentence deleted* but *can a reader who does not hover still tell what this figure covers and
whether it was measured*. If not, the claim moved when only the argument should have.

## Measure, do not describe

Four surfaces have been studied for this console. Every number came from Chrome at 1440×900 reading
`getComputedStyle` over every element, with a real pointer moved onto a control so `:hover` genuinely
matched — not from markup, and not from looking.

**The method is the durable part, not the numbers.** The control plane contradicted four of the
fourteen invariants the three landing pages agreed on, and it could only do that because both were
measurements. A described impression cannot be contradicted; it can only be argued with.
