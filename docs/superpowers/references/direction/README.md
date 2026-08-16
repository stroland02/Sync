# Direction — the owner's examples of what this should look like

**This directory is different from `../screenshots/`, and the difference is the whole point.**

`../screenshots/` holds twenty-two captures of competitors' shipping interfaces. They are a research
artifact, and `.claude/rules/interface-originality.md` fences them off: concepts and workflows may be
taken from them, appearance never. Nothing in this project opens them.

**This directory is the owner saying "this is the direction."** It is not a competitor's product to
be avoided; it is a target the owner has chosen. That changes what may be taken from it — but not
without limit, and the limits are below.

## Why it exists

As of 2026-08-06 the console clears eight of the fourteen measured invariants and looks, in the
owner's words, bland. Both halves of that are true at once, and the reason is on the record: an
earlier session **refused the two invariants that carry visual impact** — a type range of 4.67:1
(the console runs 2.0–2.67) and a frame ratio of 4.7–7.2× the in-component unit (the console runs
3.0) — on the grounds that vertical space is rows and the nav rail holds the composition's edge.

Both refusals cite Vercel's Geist. So the one reference that resembles a control plane was used to
overrule the three that look striking, and every quality item since has stepped around the result
rather than questioning it. The owner's judgement reopens both.

## What may be taken from a file in here

The rule that governs `../screenshots/` still governs the *outputs*: **the interface is ours.** What
changes is that these files are a legitimate input to the visual argument rather than a hazard.

Take **measurable properties**, and write down the measurement:

- Type range and where the display step sits relative to body.
- Spacing rhythm — the frame, the gap between regions, the in-component unit, and their ratios.
- Ink levels and where weight rather than size is doing the work.
- Composition: what leads a screen, what the eye is meant to reach second.
- Density, and what is allowed to be empty.

Do **not** take a layout wholesale, a component's appearance, a colour system, copy, or an
arrangement reproduced because it looked good in the image. If a change cannot be stated as a
property with a number, it has not been understood yet.

## What does not move, whatever an example shows

- **No composite score, health figure, traffic light, green dot, liveness pulse or count-up.**
  Refused four times, and the argument is in `CLAUDE.md`: the scalar has no referent in the graph.
- **The twenty-four protected sentences.** Restyling is allowed; deleting, shortening, collapsing
  behind a disclosure or moving into a tooltip is not.
- **Absence is not zero, staleness is not liveness, never-measured is not nothing-here.**
- The 5.05:1 contrast floor against rendered pixels, and the 11px size floor.

A reference that is beautiful because it asserts a confidence the data cannot support is a reference
to learn composition from and refuse the claim of.

## How to add one

Drop the image in here with a name that says what it is — `giga-01-landing.png`,
`dovetail-02-dashboard.png` — and, if there is one, a line in `NOTES.md` saying what specifically is
right about it. One sentence is enough: *"the way the page opens with one number and everything else
recedes"* is far more useful than the file alone.
