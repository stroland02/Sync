# The console

Loads when you are editing the console. The root `CLAUDE.md` still applies.

## Before you change a screen, open the reference — and it is not `console-mock`

**`docs/stitch_sync_developer_console/` is the visual authority.** Twenty-four screens, each with a
rendered `screen.png` and the `code.html` behind it. The screen you are about to touch has a still
in there. Open it first.

**`docs/console-mock/` is the retired mock and is no longer the target.** It sits beside the Stitch
set on disk and this paragraph used to point at it, which is how it kept being obeyed after it was
demoted on 2026-08-25. If you are reading a twelve-screen mock, you have the wrong drawing.

**Read `docs/superpowers/plans/2026-08-26-ui-rebuild-master-brief.md` before your first edit.** It
is the entry point: the objective, the authority order, the per-screen rulings, what is already
landed, and what is still owed. The executable half is
`docs/superpowers/specs/2026-08-25-stitch-rebuild-specs.md`, which carries per-file KEEP / REBUILD /
DELETE lists and the build order.

**Most screens are mandated as a rebuild, not a reskin, and the difference is the whole point.**
Measured 2026-08-26: eighteen of twenty-one screens still render `ScreenFrame` at its default
`flow` layout — one long scrolling column — while the brief rules six of them full rebuilds into
locked, multi-pane compositions. A token swap reskins every screen without editing one, which is
exactly how a console can change palette and still be the old console. The owner's words, twice:
*"everything looks exactly the same."* **Structural conformance is not the deliverable.**

Where the reference disagrees with the hierarchy spec, `DESIGN.md` or `console-surface.md`, the
reference loses and the disagreement is recorded. It still outranks your own reading of what a
screen should look like. Enabled tooling and what binds it:
`docs/superpowers/references/notes/2026-08-24-frontend-resources-audit.md`.

## What the console is for

Competitors show a black box and a result and ask a reviewer to trust it. This console shows the
reasoning instead. Three things follow, and only the third is a refusal.

**Show the work.** Provenance, scope, and what was not measured are part of every answer.

**Say which nothing it is.** Absence is not zero. Staleness is not liveness. Never-measured is not
nothing-here. This is the rule that matters most and the one most easily lost in a tidy-up.

**No composite score, health figure, traffic light or liveness pulse.** Rejected three times on the
record: a scalar averaging "we could not check" with "we checked and it passed" collapses the exact
distinction this product exists to make. A **badge** is permitted — a recorded value from a closed
vocabulary, legible without its colour — and run outcome, error state and absence already use one.

## Prose on screen

**Owner ruling, 2026-08-19.** The claim stays visible in the fewest honest words; the argument moves
behind the ⓘ.

A reader who never hovers must still be able to tell what a figure covers and whether it was measured:
*not measured yet* · *all workspaces* · *static evidence* · *no source attached* · *counted before this
filter*. Why the distinction exists belongs in the hover. Rendering one nothing as another is still
refused, and so is a figure whose scope is qualified nowhere.

This replaced a rule protecting twenty-four specific sentences from being shortened or moved. It
blocked ordinary cleanup, and seven of the sentences cited files that no longer existed.

## Charts

**A chart must be able to draw its own data — check the real payload before choosing a form.**
Learned expensively, twice on one panel: provenance shipped as a donut over a set where four of five
members were measured zeros, and a donut cannot draw a zero. It rendered as a closed ring and read as
broken.

- **Bars for rankings and for any set with meaningful zeros.** A bar of length zero still has a row,
  a label and a count.
- **Donuts only where the parts genuinely sum to a whole a reader can name**, and never below two
  members — a ring at 100% is the same picture at any scale.
- **Log scale where the set spans orders of magnitude, and say so on the chart.** A log axis a reader
  takes for linear is worse than no chart. `RankedBars` has `scale="log"`.
- **A count is not a rate.** No percentage without its denominator on screen.

ECharts owns anything with an axis, a legend or a time dimension. `ranked-bars.tsx` is SVG because a
bar row is a labelled rectangle whose width is a ratio.

## Tests

`npm test` is `vitest run` over jsdom. Scope is deliberately narrow: **classification, derivation and
structural invariants. Never class names, never snapshots.** A snapshot in a console being actively
restyled fails on every correct change and gets deleted by whoever it blocks.

Anything about rendered pixels is measured in Chrome and written into `DESIGN.md` — a different
discipline with a different gate.

**A rule the payload can answer belongs in the payload**, so two screens cannot disagree about one
fact. A rule about the rendered view — whether a set is small enough to list, whether a poll should
keep asking — belongs here.

**`npm run build` passing is not evidence.** TypeScript checks the console against the types the
console declares, not against what the API sends. `a6ee379` removed a field from a payload, `types.ts`
still declared it, and a column rendered the absence marker forever while the build stayed green. The
two sides are held together by Python tests that read the TypeScript.

## Authorities

- `DESIGN.md` — the token contract. Every colour, step, space and radius, with the arithmetic proving
  each contrast against a 5.05:1 floor. Dark-only. A new token is argued there, never added here.
- `.claude/rules/console-hierarchy.md` — levels come from the specification, never from a plan.
- `.claude/rules/console-surface.md` — what binds while a screen is open.
- `.claude/rules/interface-originality.md` — the interface is ours. Competitors are studied for
  concepts, never for how a screen should look.
