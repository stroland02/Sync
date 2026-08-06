# M4.5 — the console is worth looking at

**Status:** scoped 2026-08-06, not started. Its start condition is written below and is checkable.
**Continues:** the five M4 plans, and `2026-08-05-sync-console-design-system.md` in particular, which
built the token contract this milestone measures against.
**Authority for every visual value:** `DESIGN.md`. **Authority for what may be taken from a
reference:** `.claude/rules/interface-originality.md`.

## Why this is its own milestone

M4 is defined at `docs/superpowers/specs/2026-07-25-sync-self-maintaining-apis-design.md:390` as four
deliverables — multi-tenant runtime, dashboard, organization onboarding, per-repository policy. Three
of them have no code. An open-ended quality bar inside a milestone that is three-quarters unbuilt
produces a milestone with no end.

The acceptance test is also a different kind. An M4 task is done when a screen exists and a test holds
it. A quality task is done when a **measurement clears a bar**. Those want different verification
sections, and mixing them is how a bar becomes a matter of opinion.

The third reason is the one that decides it, and it is a fact rather than an argument: **nine
consecutive ticks went to design-system findings while two specified levels of the console did not
exist.** The course correction is in the SDD ledger and the lesson is in `CLAUDE.md`'s debt section. A
separate milestone with a written start condition is the mechanism that stops it recurring, because
"not yet" becomes a fact about sequence instead of a judgement somebody has to keep making.

M6 needs this rather than M4: its preconditions name *"the dashboard of M4 existing to be
photographed"* (`design.md:518-520`), and what gets photographed is this milestone's output.

## Start condition

All three, checkable:

1. Tasks 4, 5, 6 and 7 of `2026-08-05-sync-console-architecture.md` have landed — the table layer,
   the frontend test runner, the transport split, progressive disclosure.
2. The review wave of 2026-08-06 is closed (`briefs/2026-08-06-m4-review-wave.md`).
3. `docs/superpowers/reports/2026-08-06-console-conformance.md` exists.

M4's hosted half — auth, tenancy, onboarding, policy — runs in parallel and does not gate this.

## What the references established, and what they did not

Four surfaces were measured: three landing pages and one shipping control plane. Every number came
from Chrome at 1440×900 reading `getComputedStyle` over every element in the document, with a real
pointer moved onto a control so `:hover` genuinely matched — not from markup and not from looking.

Fourteen properties on which three of them independently agree are recorded at
`2026-08-05-sync-console-architecture.md:2117-2136`. Properties on which they contradict each other
are recorded immediately after, at `:2140-2155`, and are **not a bar** — a property three careful
designers resolve three different ways is taste.

**The method is the durable part, not the numbers.** The fourth surface contradicted four of the
invariants the first three had agreed on, and it could only do that because both were measurements. A
described impression cannot be contradicted by anything.

This is also what keeps the milestone inside the originality rule. We are not asking whether our page
resembles theirs. We are asking whether ours clears a bar that unrelated careful surfaces all clear —
a question about legibility and restraint, not about layout.

## The tasks

### Task 1 — The conformance baseline

Every route measured against the fourteen invariants and the seven interface-quality checklist items
in `docs/superpowers/loops/console-improvement-tick.md`, with the commit SHA on every table, published
as `reports/2026-08-06-console-conformance.md`.

**Closes when** the report exists and every gap it names is either a backlog entry with a number
attached or an argued exception. Without it every task below is an opinion.

### Task 2 — The affordance layer

B90, and Tasks 4 and 7 of the architecture plan. A headless table layer with sorting, filtering and
virtualisation, and progressive disclosure — a dialog for evidence, tabs on the coverage page.
`dialog.tsx`, `command.tsx` and `input.tsx` are vendored already; `radix-ui`, `framer-motion`,
`echarts` and `lucide-react` are installed and barely used. A table library is a real dependency
decision governed by `references/engineering/dependencies-and-packaging.md` and is argued, not assumed.

**A slice, not a sweep**: the two or three screens where the absence costs an operator something.

**Closes when** at `--scale 10000` a named operator question is answered in one interaction that today
needs scrolling, with before-and-after numbers for time to first paint, DOM node count and payload
size — and when a filtered-to-empty view is still distinguishable from a genuinely empty one.

### Task 3 — Type, ink and space, measured against rendered pixels

The agreed invariants: two font weights and no more; two ink levels plus one accent; a type range of
at least 3.4:1 with the display step at least 3× body; three spacing levels each at least twice the
one below; prose that never runs the column's width.

The console lives in 12/12.8/14/16/18px with its `h1` at `text-lg` — measured at 1.5:1 against a 2.0
threshold, which is why a page title, a card title and a row label are hard to tell apart. That one is
a class on four elements and is the cheapest item in the milestone.

**Closes when** each is measured on the running console and either clears the bar or carries an argued
exception in `DESIGN.md`. Declared tokens are not evidence: the 5.05:1 contrast floor is measured
against rendered pixels, because opacity, layering and chart fills all move it.

### Task 4 — Motion, and the discipline of not having any

The most counterintuitive finding, and it survived being checked against open-source source rather
than screenshots: one `@keyframes` per page and it is a spinner; nothing decorative running at rest;
primary actions with `transition-duration: 0s`, `transform: none`, no scale and no fade on hover. One
reference's own rule is that frequent interactions avoid animation altogether.

Motion is not a budget to spend here. **Motion claims a time**, so it is permitted where the data holds
one — a node advancing, a run reaching a terminal state, a value arriving — and nowhere else.

**Closes when** a measurement reports at most one keyframe, zero animations running at rest and no
transition on a primary action, and every remaining animation names the state change it tracks.

### Task 5 — Density that is legible, and the floor that stops it

The standing temptation of a data-dense console is `text-[10px]` the next time a table gets crowded.
The floor is 11px and being on `DESIGN.md`'s ramp does not exempt a value from it. This task is that
regression guard plus the row-height and rhythm decisions that make density readable rather than
merely small.

**Closes when** nothing renders below the floor, the provenance column is on screen at 1280px without
scrolling the table sideways, and the longest prose panel wraps at a readable measure at 1920px. All
three are open checklist items today.

### Task 6 — The one visual that earns itself

Eight screens and one chart, against `echarts` installed and the `dataviz` skill invoked once. Not a
wall of tiles: the single view where the graph's shape is the answer and a table is not. `dataviz` is
invoked before the first line of it.

**Closes when** a reader answers a question from the visual that the table beside it does not answer,
and it survives `--scale 10000`.

## What this milestone must not do

- **No composite score, health figure, traffic light, green dot, liveness pulse or count-up.** Asked
  for and refused four times. The scalar has no referent in the graph, and a design system is exactly
  the moment somebody reaches for a coloured badge.
- **No component added because it is available.** Each earns its place from the operator and the graph.
- **No sentence deleted to make a screen tidier.** Twenty-four sentences carry the honesty
  distinctions, listed with file and line in `2026-08-05-sync-console-architecture.md`. Restyling is
  allowed; deleting, shortening, collapsing behind a disclosure or moving into a tooltip is not.
  Nothing tests prose, so every change re-reads its own diff for a deleted qualification.
- **No restyling ahead of the data.** A beautiful console showing the wrong rung is a failure; a plain
  one showing the right rung is a success. That ordering does not stop applying because the milestone
  is about appearance.
- **Nothing under `docs/superpowers/references/screenshots/` is opened.** The interface is ours.

## Verification

Every task closes on a measurement taken the way the references were measured: Chrome at 1440×900,
`getComputedStyle` over every element, a real pointer for `:hover`, at `--scale 10000`, with the commit
SHA recorded. `superpowers-chrome:browsing` is the tool.

The standing gate still applies to every commit: `uv run pytest tests/ -q` clean, `npm run build` and
`npm run lint` clean, and a stated observation of the running screen — `npm run build` passing proves
the console agrees with its own types, not with the API.
