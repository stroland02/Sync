# M12 — dashboards that earn their screen

**Proposed 2026-08-07, not scheduled.** Numbered M12 because M8–M11 are the resolution loop and M7 is
the console. Full-stack by necessity: the useful dashboards need aggregations `sync.dashboard` does
not compute today, so this is not a restyle and must not be planned as one.

## Where this came from

The owner reviewed `reports/screens/2026-08-07/` against `references/direction/` and named four gaps.
Checked against the tree before planning, because two of the four were already answered:

| Owner's finding | State on 2026-08-07 |
|---|---|
| "Change the base background from pure black" | **Already done.** `--color-background` is `oklch(0.19 0.0025 159)`, Supabase's own value, since `M7-W170`. It photographs as black and is not |
| "Make numbers large, labels small and muted" | **The scale exists; the assignment is wrong.** `--text-2xl` 22px, `--text-3xl` 28px and a 48px display step are declared, while panel headings render at 12px furniture. `M7-W182` Task 2 is fixing exactly that |
| "Use cards; never let raw data float" | Partly true. Fact tiles and panels are contained; the tallies beneath the disposition bar are not |
| **"Stop stacking everything vertically"** | **Correct and unaddressed.** Nothing in the fidelity pass touches grid composition. This is the milestone's centre |

Two of the prescriptions are refused, and the refusals are the owner's to reverse rather than mine:

- **"Remove almost all the paragraph text"** is not available as written. Those paragraphs are the
  twenty-four protected sentences and `tests/test_console_honesty_sentences.py` fails on deletion.
  **What is available, and is what this milestone does:** the guard is deliberately not file-pinned,
  so a sentence may be **re-placed** — into disclosure, an empty state, or an inspector — where it is
  on screen when it is load-bearing and not competing with the figure beside it. The owner's
  strongest line, *"if a metric needs a paragraph to explain it, the metric is wrong"*, mostly does
  not apply here: these sentences do not explain the metric, they state what it cannot tell you.
- **"A green dot for a healthy status"** is the refusal `CLAUDE.md` records three times. Nothing in
  our data separates a run parked on a customer's CI from one that has died, so a green dot is a
  confident wrong verdict. A muted semantic colour on an **error** state is already permitted — a
  recorded value from a closed vocabulary, legible without its colour — so most of what the review
  asks for is available and only "healthy" is not.

One finding of the owner's is accepted outright and has no entry yet: **the disposition bar spends
four hues on a categorical axis where length already carries the fact.** `M4.5-W145` made exactly
this argument for the rung composition chart and it was not carried across.

## What a dashboard has to earn

The failure this milestone must avoid is the one every observability product ships: a screen of
charts nobody reads because none of them changes a decision. So the ordering rule is **the question
first, the panel second**, and a panel that cannot name the decision it changes does not get built.

Four questions an operator actually has, each already answerable from the graph:

1. **Is anything stuck right now, and for how long?** Runs by node with time-at-node. The data exists
   in the checkpointer; nothing aggregates it.
2. **What is getting worse?** Findings opened per day per vendor, against the same window closed.
   `vendor_change` and `finding` carry the timestamps; there is no time-bucketed query.
3. **Where is the graph blind?** Call sites at the `static` rung as a share of the total, per
   repository — the honest form of "coverage", and it is a ratio we can actually support because both
   terms are counts of the same thing.
4. **Which change kinds are not mechanically safe?** `abandon_reason` by change kind. The pipeline
   discipline says abandoned runs are where routing learns; nothing reads them back.

Each is a **new aggregate in `sync.dashboard`**, a new read-only route, and a panel. That is the
full-stack part, and it is why this cannot be done inside the console session's brief.

## Shape of the work

- **Phase 1 — the four aggregates.** One work item each: grain declared as a comment in
  `schema.sql` terms, the query, the view model, the route, the behavioural test that the route
  reaches nothing past the read surface. No presentation.
- **Phase 2 — the panels.** Value at display size above its own evidence, per
  `interface-originality.md`'s metric-panel convention. One item per question.
- **Phase 3 — grid composition.** The owner's fourth point. Fleet and Codebase stop being one
  vertical stack: a fact row across the top, then a two-column band, then the tables. Measured, with
  regions-placed-beside-another before and after.
- **Phase 4 — the honesty sentences re-placed, not removed.** Each of the twenty-four gets a decided
  home: beside its figure, behind a disclosure, in an empty state, or in an inspector. The guard
  stays green throughout by construction, and every move is recorded.

## What must not move

Everything `M7`'s spec section 6 protects: the twenty-four sentences, no composite score or health
figure or traffic light or green dot, absence apart from zero, staleness apart from liveness, the
provenance rung at two levels and monochrome, and the API read-only.

**And one this milestone adds:** a chart's colour may not carry a fact its length or position already
carries. That is the disposition-bar finding generalised, and it is the rule that keeps "use colour
purposefully" from becoming "use colour".

## Verification

Per panel: the decision it changes, named in the brief before it is built. Per screen: Chrome at
1440×900 and 1280×800, before and after — type range, regions placed beside another, rows above the
fold at `--scale 10000`. Per aggregate: the grain, and a test that a count of rows is not read as a
count of findings.
