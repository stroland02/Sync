# M4 expansion — from a correct console to an operable one

**Status:** in execution, four parallel workspaces.
**Continues:** `2026-07-30-sync-m4-dashboard.md` (the spine), `2026-08-04-sync-m4-slice-2.md`,
`2026-08-05-sync-console-architecture.md` (the hierarchy reconciliation and the reference
measurements), `2026-08-05-sync-console-design-system.md` (the token contract).
**Authority above all of these:** `docs/superpowers/specs/2026-07-25-sync-self-maintaining-apis-design.md`,
section *M4 — Hosted control plane / Information architecture*, second fenced block.

This plan does not start a new workflow. It is the next slice of the one those four plans have been
executing, and it inherits every rule they established. Where it disagrees with one of them, that is
a defect in this document.

## Why there is an expansion at all

The first three slices were about being *right*: does the console show what the graph actually holds,
does it distinguish absence from zero and staleness from liveness, does every level of the interface
correspond to an entity the system stores. That work is largely done and it was the correct order —
a beautiful console showing the wrong rung is a failure, a plain one showing the right rung is a
success.

What it produced is a read-only table renderer. Measured on 2026-08-05: 21 `<Card>`, 17 `<Table>`,
one chart, and across the whole frontend 7 `onChange`, 3 `<Button>`, 2 `onClick`, 1 `<input>`. On a
console whose tables will hold thousands of call sites from a customer repository where the fixture
holds five.

So the expansion has two halves and they are not in tension:

1. **Finish the specified hierarchy.** Three levels the design document names were never built. Two
   landed on 2026-08-06 — Pull Request with its evidence bundle (`c808854`) and Signals (`b39dcde`).
   Codebase is the one still missing, and it is the one everything below inherits scope from.
2. **Make the console operable, and let the aesthetic follow from the engine.** Affordances the data
   demands, argued from the operator rather than from the component catalogue.

## The rule that keeps the second half from becoming taste

**A distinction that exists in the data earns a distinction on screen. One that does not, does not
get invented.**

That is the same rule that produced the surface ramp indexed by job rather than depth, and the same
one that refuses a composite health score — the scalar has no referent in the graph. Applied to the
expansion it says: density, motion, depth and emphasis each have to answer to something the graph
stores. Motion that tracks a real state change is information. Motion on a frequent interaction is a
delay the operator pays every time with nothing behind it.

`.claude/rules/interface-originality.md` binds the whole slice. Concepts and workflows may be taken
from anywhere; layouts, compositions and component appearances may not. Nothing under
`docs/superpowers/references/screenshots/` is opened.

## The comparison this slice can actually run

`2026-08-05-sync-console-architecture.md:2117-2136` records fourteen properties on which three
independently measured reference surfaces agree, each read from Chrome at 1440×900 through
`getComputedStyle` over every element, with a real pointer moved onto a control so `:hover` genuinely
matched. Two weights and no more. Two ink levels plus one accent. Type range at least 3.4:1. Three
spacing levels, each at least twice the one below. One `@keyframes`, and it is a spinner. Nothing
decorative running at rest. Primary actions that do not animate on hover.

**Those are invariants, not a design.** They can be measured on our console the same way and the
answer is a number, not an opinion — which is precisely what makes the comparison safe under the
originality rule. We are not asking whether our page resembles theirs. We are asking whether ours
clears a bar that three unrelated careful surfaces all clear.

The seven-item interface-quality checklist in
`docs/superpowers/loops/console-improvement-tick.md:47-114` is the second half of the same
measurement, and it asks whether what is rendered can be read at all. Items 2 through 6 were open as
of `72450ae` and have not been re-checked against the running tree since the design-system tasks
landed.

## The four workstreams

Each runs in its own Orca workspace on a branch based on `m4-dashboard`, with a brief under
`docs/superpowers/briefs/`. They were chosen to touch different files; where two must touch
`routes.ts`, the coordinator resolves it at merge.

**1. The Codebase level, and the two routes that exist because it does not.** B92, and Task 9 of
`2026-08-05-sync-console-architecture.md`. `/repositories/:repoId` becomes the Codebase level,
reachable by clicking a repository row rather than by typing an identifier into a form; `/bindings`
and `/observed-telemetry` leave `routes.ts` entirely. The hard half is scope: `/api/overview`,
`/api/detectors` and `/api/corpus` are fleet-wide and take no `repo_id`, and a fleet-wide number
rendered under a repository heading is a false claim about that repository. Every figure below
Codebase is either scoped or says in words that it is not.
Brief: `briefs/2026-08-06-m4-repository-level.md`.

**2. The interface idiom.** B90. A slice, not a sweep — the two or three screens where the absence
of filtering, sorting or search actually costs an operator something, given tables that will be long.
Zero new dependencies are needed for dialog, tabs, command, tooltip, badge, skeleton, separator,
scroll-area or dropdown-menu; a headless table library is a real dependency decision that gets argued
in the commit body and the backlog or does not happen. Any affordance added must keep filtered-to-empty
distinguishable from genuinely-empty.
Brief: `briefs/2026-08-06-m4-interface-idiom.md`.

**3. Signals, finished.** B93 and the buildable part of B94. The level landed with one panel of one
role and a re-export shim standing where the reparented route will go. This retires the shim, moves
the route declaration to `Signals` under API Services, scopes it by repository, and makes the level's
header state which of the three roles have integrations attached and which do not — because one panel
of one role must never imply three.
Brief: `briefs/2026-08-06-m4-signals-level.md`.

**4. The conformance measurement.** New, and it is what makes the other three checkable. Measure the
running console the way the references were measured, produce a per-route table against the fourteen
invariants and the seven checklist items, and commit it as a report that the next tick reads instead
of re-deriving. A gap is a backlog entry with a number attached, not an impression.
Brief: `briefs/2026-08-06-m4-conformance-measurement.md`.

## Verification, unchanged from the slices before it

`uv run pytest tests/ -q` clean, `npm run build` and `npm run lint` clean from `web/`, and a stated
human observation of the running screen. `npm run build` passing proves the console agrees with its
own types, not that it agrees with the API — `a6ee379` is the commit that proved this the expensive
way.

Logic with a wrong answer lives in Python, because the console has no test runner. The console
formats and renders.

Twenty-four sentences carry the honesty distinctions and are listed with file and line in
`2026-08-05-sync-console-architecture.md`. Restyling one is allowed; deleting, shortening, collapsing
behind a disclosure or moving one into a tooltip is not. Every workstream re-reads its own diff for a
deleted qualification before committing, because nothing tests prose.

## What this slice must not do

- Add a route the graph cannot answer. That is a question about the graph and it belongs in a plan.
- Add a level `GRAPH_LEVELS` does not have. The specification is amended first, as a dated amendment,
  and `tests/test_console_hierarchy.py` fails otherwise.
- Ship a composite score, health figure, traffic light, green dot, liveness pulse or count-up. Asked
  for and refused four times; the argument is in `CLAUDE.md`.
- Leave a shim, a workaround or a dead route behind without a backlog entry naming what retires it.
  `CLAUDE.md`'s *Technical debt is the scaling constraint* governs, and this slice is the first one
  written under it.
