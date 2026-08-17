# Console mock parity and honest motion — design

**Date:** 2026-08-17
**Status:** Approved by the owner in session; supersedes the phasing of
`plans/2026-08-16-sync-m13-dynamic-visuals-and-telemetry.md` (see "Rulings" below).
**Consumes:** `docs/console-mock/` (the owner's ten-screen demo, ground truth for layout),
`plans/2026-08-08-console-mock-to-build.md` (its unfinished tasks),
`plans/2026-08-07-m12-dashboards-that-earn-their-screen.md` (Phase 3 only).

## The problem

The console has a strong token contract (`DESIGN.md`), a strong honesty discipline
(`.claude/rules/console-surface.md`), and a ground-truth mock the owner drew
(`docs/console-mock/`, live at the artifact URL in its README) — and the shipped screens match
none of them well. An audit on 2026-08-17 found:

- `fleet-page.tsx` has drifted off the chassis entirely: its docstring claims `PageHeader` and
  `ControlBar`; the code renders neither. The index route has no display-step focal point, in
  direct violation of `DESIGN.md:513-521`.
- `codebases-panel.tsx` carries nine raw-Tailwind violations, colour-carried judgement badges
  (emerald "Clean" / amber "N Findings" — the traffic light `DESIGN.md:1039` names as
  deliberately absent), and hardcoded fixture fallbacks (`acme/payments-api`, `"Stripe"`) rendered
  as if they were data.
- 37 raw-Tailwind spellings across 14 feature files, against a recorded tokens-only decision.
- Five near-identical two-column grid literals duplicated across five pages with no shared
  component.
- M12's grid-composition phase — the direct answer to the owner's "stop stacking everything
  vertically" — is at 0%, and its own triage calls that gap "correct and unaddressed."
- `plans/2026-08-08-console-mock-to-build.md` Task 1 (measure the mock against what shipped)
  was never run; Tasks 3, 5, 6 (shared drawer, `/settings`, palette test) were never built —
  while `BACKLOG.md` records the plan "Landed (Phases 1-6)."

The last point is why UI changes feel like a struggle: docstrings and ledgers assert layouts the
code does not render, so every session starts from a false map, and no guard fails when a screen
is flat or when a plan half-lands.

## Rulings recorded in this session

Three decisions the owner made explicitly; each reverses or narrows a written plan and is
recorded here so the next session does not re-litigate them.

1. **Scope: the whole console to mock parity**, not the trajectory screen alone. The workflow
   screen is the flagship but arrives in phase order, after the chassis is sound.
2. **The liveness-pulse refusal stands.** M13's "live pulse rings" are not built. The recorded
   refusal (three times, on the grounds that nothing in the data distinguishes a run parked on
   customer CI from one that died) wins over the M13 plan. The DeepSeek-harness feel is achieved
   with honest mechanisms instead: ticking elapsed-since-last-checkpoint, the existing
   change-wash on real state transitions, clickable nodes disclosing stored evidence, and idle
   nodes visually receded so active work stands out.
3. **Remotion is deferred.** No new animation dependency in this effort. Motion stays within the
   sanctioned mechanisms in `web/src/lib/motion.ts` and CSS/SVG. Remotion is evaluated as its own
   milestone once static parity is reached, if at all.

## Authorities

Nothing in this spec overrides them; where a phase below appears to conflict, the authority wins.

1. `docs/superpowers/specs/2026-07-25-sync-self-maintaining-apis-design.md:427-445` — the
   hierarchy. No new levels; `/settings` is a destination, not a level.
2. `DESIGN.md` — every visual value, with its arithmetic. A mock value not in `DESIGN.md` is a
   proposal argued there first.
3. `.claude/rules/console-surface.md` — the honesty channel rules and the twenty-four protected
   sentences. Restyling and re-placing is allowed; deleting, shortening, or hiding one is not.
4. `docs/console-mock/` — ground truth for layout and composition only, and the lowest authority
   in the room. Its fixtures are invented; read a number there as a layout weight, never as data.

## Section 1 — the verification loop

The repository already prescribes the method (`console-surface.md:63-76`: "measure, do not
describe") and the capture conditions (`docs/console-mock/README.md`). This section makes it a
repeatable exit gate rather than a good intention.

**The walk.** Serve the console per `.claude/rules/console-dev-loop.md` — API on 8787, seed
script, `npm run dev` on 5173 from the coordinator's worktree, `--strictPort`. Drive Chrome via
the `superpowers-chrome:browsing` skill at 1440×900, `deviceScaleFactor: 1`, pairing every
`set_viewport` with `clear_viewport`. For each route, read `getComputedStyle` over every element
and record:

- type range on screen (display ÷ smallest rendered step) against the 3.4:1 bar;
- frame-to-gap ratio;
- count of regions placed beside another region (the side-by-side census);
- raw-token census (spellings outside the token vocabulary);
- the honesty checks the improvement tick already carries.

**The report.** The output is the file Task 1 promised and never produced:
`docs/superpowers/reports/YYYY-MM-DD-console-mock-gaps.md` — one row per screen, mock still
beside shipped measurement, verdict per delta: adopt / adapt / refuse-with-reason. The report is
re-run at each phase boundary; a phase exits on its numbers, never on a screenshot.

**Ledger truth.** Before any build work, `BACKLOG.md` rows for
`2026-08-08-console-mock-to-build.md` and `2026-08-08-console-direction-parity.md` are corrected
to say what actually landed, and the stale checkboxes inside the plan files are reconciled with
the tree. A false "Landed" costs every future session a wrong assumption.

**Guards.** `tests/test_console_design_tokens.py` already fails when a route renders nothing at
the display tier. This effort adds one guard: a raw-Tailwind census over `web/src/features/`
that fails on spellings outside the token vocabulary, seeded with the current 37 as a shrinking
allowlist (new violations fail immediately; the list only shrinks).

## Section 2 — Phase 1, chassis conformance

Everything here removes drift or duplication; nothing here restyles.

- **`DetailGrid`.** One shared layout component for the two-column detail shape, replacing the
  five duplicated grid literals in `finding-page.tsx`, `pull-request-page.tsx`,
  `workflow-page.tsx`, `vendor-page.tsx`, `binding-surface-page.tsx`. Rail side and rail width
  are props; the literal lives in exactly one file.
- **Fleet back on the chassis.** `PageHeader` (restoring the display step to the index route),
  `ControlBar` for scope and the one primary action, the existing `FacetChips` replacing the
  hand-rolled filter tabs, the one-off emerald CTA replaced with a tokened primary defined in
  `DESIGN.md` with its contrast arithmetic.
- **`codebases-panel.tsx` rewritten.** Tokens only; badges from the closed vocabulary with a
  glyph and a word, no hue-carried judgement; per-repository counts computed from the payload
  (the current code assigns the fleet-wide total to every card); all fixture fallbacks deleted —
  absence renders as the absence marker, per the protected sentences.
- **Raw-Tailwind sweep.** The 37 spellings in `features/` replaced with tokens; the Section 1
  guard keeps them out.
- **Docstring reconciliation.** Every feature docstring that asserts a composition the code does
  not render is corrected to what ships (or the code is brought up to the docstring where Phase 2
  will need it anyway — decided per file, recorded in the plan ledger).

## Section 3 — Phase 2, composition

M12 Phase 3, verbatim in intent: Fleet and Codebase stop being one vertical stack. Each gets a
fact-tile row across the top, a two-column band beneath it, then the tables — the shape the mock
draws on screens 01 and 02. The side-by-side census from Section 1 is taken before and after;
the phase exits when every level places at least one region beside another and the type range
clears 3.4:1 on every route.

The disposition chart loses categorical hue where length already carries the fact, honouring the
recorded invariant "a chart's colour may not carry a fact its length or position already
carries." The eight-slot series palette remains for axes that are genuinely categorical.

Out of scope here: M12's four new aggregates (stuck-duration, worsening, blind-share, unsafe
change kinds). Those need backend queries and belong to M12 proper. This phase recomposes what
the payload already carries.

## Section 4 — Phase 3, the trajectory flagship

The workflow route (`/findings/:id/workflow`) reaches mock screen 07 plus the honest half of
M13 Phase 1:

- **Two-pane composition per the mock:** the Node-by-node rail (already built, kept) beside an
  **Activity timeline** — assembled at read time from the checkpointer, run outcomes, pull
  request facts, and CI checks; the mock's own caption ("nothing writes a timeline row") is the
  contract. Each entry: timestamp, source, mono event name, one-sentence detail.
- **Clickable nodes disclose stored evidence.** Clicking `static_verify` shows the compiler
  output that node produced; clicking `locate` shows the routing row it matched. The checkpointer
  already holds this; the work is exposing it, not capturing it. This is the competitor note's
  §2.6 finding, adopted at the concept level only.
- **Ticking elapsed.** `lib/elapsed.ts` (already factored) drives a ticking
  elapsed-since-last-checkpoint beside the active node. It is labelled as time since evidence,
  never as "running for" — the data cannot support the stronger sentence.
- **Idle nodes recede.** Nodes at `not_reached_yet` drop to muted ink so reached work carries the
  contrast. No colour is added to reached nodes; the recession is the emphasis.
- **No pulse, no invented per-node durations.** B123 stands: no checkpoint carries a duration,
  so none is drawn. The change-wash (built, tested) remains the only motion on state change.

## Section 5 — Phase 4, remaining parity and the unbuilt tasks

- `Breadcrumbs` on the two routes missing them (vendor, codebase).
- `/settings` built as a destination outside `GRAPH_LEVELS`, per mock screen 10 and
  mock-to-build Task 5.
- The shared `detail-drawer` extracted from `binding-drawer.tsx` (Task 3), consumed by the
  drawer surfaces the mock draws.
- The command-palette test (Task 6): subject-taking routes listed as lookups, never dead links.
- A closing mock walk over all twelve stills; the final gap report is the completion artifact.

## Execution shape

One integration branch, named in the implementation plan. Subagent-driven TDD per the standing
workflow: structural and classification claims tested in vitest (never class names, never
snapshots); rendered-pixel claims measured in Chrome and written into `DESIGN.md`. Local gates
before merge: `uv run pytest tests/ -q`, then `npm run build`, `npm run lint`, `npm test` from
`web/`. Phases land in order; each exits through the Section 1 walk.

## Out of scope

- Remotion and any new animation dependency (owner ruling, this session).
- Liveness pulses and any liveness inference (owner ruling, standing).
- M12's four new aggregates and their backend queries.
- Light theme (`Sync Console v2.dc.html` stays out, per the mock README).
- Any new level in `GRAPH_LEVELS`.

## Success criteria

1. Every route renders a display-step focal point; type range ≥ 3.4:1 on every route (guarded).
2. Every level places at least one region beside another; the side-by-side census shows it.
3. Raw-Tailwind census in `features/` at zero, guard in place.
4. No colour-carried judgement outside the three licensed channels; the traffic-light badges are
   gone.
5. The workflow route matches mock screen 07's composition with the honest-motion mechanisms and
   clickable evidence.
6. `docs/superpowers/reports/` holds the gap report, re-run per phase, final run clean.
7. `BACKLOG.md` and the two 2026-08-08 plan files agree with the tree.
