# Why the console came out flat — a root cause analysis

The owner's question, after five sets of reference screenshots: *"is there a harness or a skill
blocking us from doing this kind of UI? Frontier models can do this easily."*

**No harness blocked it and no skill blocked it. This repository's own rules did**, and they did it
by being correct about a different problem. Every agent that produced a flat screen was complying
with a written instruction. That is what makes this worth a report rather than a fix.

## Cause 1 — the originality rule forbids the conventions of the form

`.claude/rules/interface-originality.md` loads **on every turn**. It has no `paths:` frontmatter, so
it sits in the most expensive always-on tier, deliberately. Under *What may not be taken*:

> - A layout, a screen composition, a navigation shape, a visual hierarchy.
> - A colour system, type scale, spacing rhythm, iconography, or motion design.

A sidebar is a navigation shape. A two-column detail is a screen composition. A display step is a
type scale. A 4.7× frame is a spacing rhythm.

**Read literally — and it was read literally, correctly — that rule forbids adopting every one of
the chassis conventions that make a control plane legible.** It was written to stop us cloning a
competitor's identity, and it also banned learning the grammar of the form. Those are different
things and the rule did not distinguish them.

This is the single largest cause. It is not a model limitation: an agent that reads "a navigation
shape may not be taken" and then builds a horizontal strip instead of a rail has obeyed the rule.

## Cause 2 — every visual rule is a prohibition, and none require presence

`.claude/rules/console-surface.md` carries seventeen negations. No score, no dot, no pulse, no
count-up, no third ink, no new token, no motion, no alpha on a ring, no colour alone.

**There is no rule anywhere that requires a screen to have a focal point**, or a level to lead with
something, or a page to compose into regions. A system of prohibitions with no positive requirement
has one stable optimum: add nothing. Zero risk in visual design is inert.

## Cause 3 — all fourteen measured invariants are restraint invariants

The invariants three reference surfaces agreed on — two weights, two ink levels, one keyframe,
nothing decorative at rest, no transition on a primary action, prose that never runs the column —
are every one of them about **restraint**.

**A page can clear all fourteen and still be flat.** Ours nearly does: it clears eight, and the six
it fails are four already-argued deviations plus two real defects. The measurement that was supposed
to drive quality was measuring the wrong axis, and it reported "8 of 14 clear" on a screen the owner
calls unusable. Both numbers are honest. Neither describes presence.

## Cause 4 — the two refusals that matter became permanent by process

`DESIGN.md` refuses a wider type range ("vertical space is rows") and a wider frame ratio ("the nav
rail and header already hold the composition's edge"). Both were recorded as rulings with arguments.

`.claude/rules/autonomous-development.md` instructs agents to treat a recorded ruling as settled and
to keep going rather than re-litigate. That instruction is right — it is what stops a plan stalling.
Its effect here was that **type range 2.0 and frame ratio 3.0 became permanent without anyone
re-deciding them.** Six work items in a row stepped around both.

The frame refusal is also simply false: there is no rail. `site-nav.tsx` renders a horizontal strip.
The premise was never checked because the ruling was recorded.

## Cause 5 — the guards are asymmetric

`tests/test_console_design_tokens.py` is 1,133 lines. Every guard in it fails when a screen **adds**
something: a colour literal, a raw spacing value, a fourth weight, a keyframe, an alpha ring.

**No test fails when a screen is flat.** There is no guard for "this route renders nothing at the
display tier" or "this page places nothing beside anything else". The only automated feedback in the
system pushes in one direction, and it is the direction that was already the problem.

## Cause 6 — the tick's ordering guaranteed the affordance work never came up

`docs/superpowers/loops/console-improvement-tick.md`:

> Every tick, ask the four questions that follow from that, in order. **The first one that answers
> "no" is the tick's work.**

Questions 1 through 3 are correctness — a missing field, a missing rung, a state that does not say
what happened. On a console this dense there was **always** a correctness "no". Tasks 4 and 7 of the
architecture plan — the table layer and progressive disclosure, the two items that would have
produced affordances — sat unstarted for days behind that ordering.

The same file adds:

> **Do not restyle ahead of the data.** Functionality before polish is a plan constraint, not a
> preference.

Correct when written, when the console rendered five screens and none showed the thing the product
is built on. It became a permanent brake after that stopped being true.

## What this is not

It is not the model, and it is not the harness. Every one of these is a written instruction that an
agent followed. The system worked exactly as specified; the specification optimised for a console
that never lies, and said nothing about a console anyone wants to look at.

It is also not an argument to weaken the honesty rules. Not one of the six causes above is about
refusing a health score, and the refusals that protect the product's argument — no scalar, no dot,
absence distinguished from zero — cost nothing visually. **Superlog's screen is beautiful and
carries `Root cause confidence: 9`, which we still refuse.** Those are independent axes, and
conflating them is how "we must not lie" became "we must not compose".

## The corrections

1. **Amend `interface-originality.md`** to distinguish the **conventions of the form** — a sidebar,
   a breadcrumb, a drawer, a page header, a footer bar, a fact tile — from **identity**: colour,
   wordmark, copy, illustration, and the specific arrangement that makes a screen theirs. The first
   is learnable and always was; the second stays refused.
2. **Add presence requirements with measurable bars** beside the restraint invariants: every route
   renders something at the display tier; every level places at least one region beside another; the
   type range clears 3.4:1.
3. **Add a fifth tick question** — *does this screen have a focal point, and does the eye reach the
   right thing first?* — and retire "do not restyle ahead of the data", whose condition was met when
   the ninth level landed.
4. **Reopen the two `DESIGN.md` refusals** with the measurements, which M7 Phase 3 does.
5. **Add the missing guard direction**: a test that fails when a route renders nothing at the
   display tier. The restraint guards stay exactly as they are.
