# Brief — the console is one idiom repeated eight times

You are working in your own Orca workspace on a branch based on `m4-dashboard`. Everything you need
is in the repository; nothing in this brief needs a conversation to interpret.

## Read these first, in this order

1. `CLAUDE.md` at the repository root. Binding. The sections that matter most to you are *The console
   renders the product position*, *Technical debt is the scaling constraint*, and *How we work*.
2. `.claude/rules/interface-originality.md` — read this one twice, it governs the whole task.
3. `.claude/rules/console-surface.md`, `.claude/rules/console-dev-loop.md`,
   `.claude/rules/console-hierarchy.md`.
4. `DESIGN.md`, which is the contract for every visual value.
5. `docs/superpowers/BACKLOG.md`, entry **B90**, which is the work.

## The measurement this starts from

Measured on 2026-08-05 across `web/src`: **21 `<Card>`, 17 `<Table>`, 1 chart, 5,781 lines.** The
whole frontend contains 7 `onChange`, 3 `<Button>`, 2 `onClick` and 1 `<input>`.

So the console is a read-only table renderer. That was the right first version — it produced eight
screens, provenance rendered at two levels, and six false-claim defects found and closed. What is
missing is not structure. It is interface: there is no filtering, sorting, search, drill-down, tab,
dialog, skeleton or tooltip anywhere, on a console whose tables will hold thousands of call sites
from a real customer repository where the fixture holds five.

The leverage is that almost nothing needs installing. `shadcn` is in `devDependencies` and vendors
component source rather than adding a package; `radix-ui` is already a dependency. Dialog, tabs,
command, tooltip, badge, skeleton, separator, scroll-area and dropdown-menu cost **zero new
dependencies**. `lucide-react`, `framer-motion` and `echarts` are installed and barely used.

## What closes this

**A slice, not a sweep.** Pick the two or three screens where the absence actually costs an operator
something — the vendor findings table and the binding surface are the candidates, because both will
be long — and give them the affordances the data demands. Every addition is argued from the operator
and the graph, never from the component catalogue and never from a competitor's screen.

A sweep that adds a component to every screen is the failure mode, not the goal. So is a tour of the
shadcn catalogue.

Seventeen tables with no sorting or filtering is the strongest argument for a headless table library,
and TanStack Table is a **real dependency decision that must be argued rather than assumed**.
`docs/superpowers/references/engineering/dependencies-and-packaging.md` governs it. You may take that
decision — record the argument in the backlog entry and in your commit body — but a dependency added
without the argument written down is the thing that rule exists to stop.

## The aesthetic the owner asked for, stated as a build rule

The operator should feel they are flying something precise — a cockpit, not a report. That is a real
requirement and it has a concrete test attached, so it does not become taste:

**A distinction that exists in the data earns a distinction on screen. One that does not, does not get
invented.** Density, motion, depth and emphasis all have to answer to something the graph stores.
That is already why the surface ramp is indexed by job rather than by depth, and why the console
refuses a health score: the scalar has no referent.

So: motion that tracks a real state change, yes. Motion as decoration on a frequent interaction, no —
frequent interactions avoid animation altogether, because a delay the operator pays on every click is
a cost with no information behind it.

## Constraints that will not be obvious

- **No composite score, health figure, traffic light, green dot, liveness pulse or count-up.** This
  has been asked for and refused four times. Colour claims a judgement, motion claims a time, depth
  claims a relationship; three channels may carry a claim because the data holds one — run outcome,
  error state, and absence. A status colour never travels alone: it ships with an icon and a word.
- Twenty-four sentences on screen carry the honesty distinctions, listed with file and line in
  `docs/superpowers/plans/2026-08-05-sync-console-architecture.md`. Restyling one is allowed.
  Deleting, shortening, collapsing behind a disclosure, or moving one into a tooltip is not. A screen
  gets shorter every time somebody tidies it, so **re-read your own diff for a deleted
  qualification** before committing.
- Absence is distinguished from zero, staleness from liveness, never-measured from nothing-here. Any
  affordance you add — a filter, a sort, a search — must not make a filtered-to-empty view look like
  a genuinely empty dataset.
- `DESIGN.md` is the authority for every visual value. A new token, a third elevation level, a fourth
  spacing value or a seventh type step is a decision argued in that file, never a value added in a
  component. The contrast floor is 5.05:1 and `tests/test_console_design_tokens.py` holds the spacing
  half of it.
- Dark mode only, on the owner's explicit instruction. The theme resolver and its
  `prefers-color-scheme` listener are deleted rather than disabled.
- Logic with a wrong answer — which row is current, how rows group, what a filter means — lives in
  Python, because the console has no test runner. The console formats and renders.
- Nothing under `docs/superpowers/references/screenshots/` is opened. The interface is ours.

## How to work

Test first. Write the failing test, run it, watch it fail for the reason you expect, then implement.

Run the console while you build it, from the repository root:

```sh
SYNC_API_RELOAD=true uv run python -m sync.api
uv run python scripts/seed_console.py --scale 10000
cd web && npm run dev
```

`--scale 10000` is the point for you specifically: the affordances you are adding only justify
themselves against a table that is actually long. A scale claim ships with three numbers — time to
first paint, DOM node count, payload size — before and after.

`SYNC_API_RELOAD=true` is not optional; a long-lived API process serves whatever Python it started
with while Vite hot-reloads on top of it, and the mismatch looks plausible.

## Your gate, before every commit

```sh
uv run pytest tests/ -q
cd web && npm run build && npm run lint
```

All three clean, plus a stated human observation of the running screen — `npm run build` passing
proves the console agrees with its own types, not that it agrees with the API.

Commit in Conventional Commits form, body in normal prose explaining why. Push your branch. **Do not
open a pull request and do not push to `main`** — the coordinator merges into `m4-dashboard`, where
the open pull request already runs CI.

Finish everything that is not blocked before reporting. Do not stop and wait on a question.
