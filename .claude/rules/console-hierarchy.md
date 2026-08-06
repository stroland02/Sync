---
paths:
  - "web/src/lib/routes.ts"
  - "web/src/App.tsx"
  - "web/src/layouts/**"
  - "docs/superpowers/plans/**"
---

# The console's levels come from the specification

You are adding or moving a destination in the operator console, or writing a plan that does. One
document defines the interface hierarchy, and it is not this one.

`docs/superpowers/specs/2026-07-25-sync-self-maintaining-apis-design.md:392-411`, section *M4 —
Hosted control plane / Information architecture*.

## The rule

**Every value in `GRAPH_LEVELS` cites the specification line that defines it.** A level with no such
line does not go in the array. It goes in the specification first — as a dated amendment inside that
section, carrying the argument for why the graph gained an entity the document did not have — and
only then into the console.

That ordering is the whole rule. A level added to the console and argued in a plan is drift no
matter how good the argument is, because the plan is not what the next screen will be checked
against.

Two consequences worth stating, because both were violated:

- **A screen may exist without being a level.** An aggregate over a level is not a new level.
  `/codebase` aggregates over API Services; detector attribution aggregates over Errors &
  Incidents. Neither is a rung on the ladder, and adding one to `GRAPH_LEVELS` claims it is.
- **A stated exception is a licence with a scope, and the scope decays.** Write down which route it
  covers and for how long, or it will be spent on something else within the day.

## The failure this exists to prevent

Three plans — `2026-07-30-sync-m4-dashboard.md`, `2026-08-04-sync-m4-slice-2.md`,
`2026-08-05-sync-console-architecture.md` — built a route table, a route registry, a persistent
navigation and a command palette on a six-level hierarchy. None of them opened the specification.
Reconciled on 2026-08-05: three of eleven routes matched, four levels were invented, two were
reparented, and three specified levels had never been built. The console's index route was a level
whose name appears zero times in the design document.

Every one of those decisions was argued, in writing, in the right file, by someone being careful.
The argument was just never made against the authority. That is the defect this rule catches, and
it is a cheap one to catch: it costs one file open.

## What holds it when nobody reads this

`tests/test_console_hierarchy.py` (Task 10 of `2026-08-05-sync-console-architecture.md`) parses the
specification's fenced hierarchy block and `GRAPH_LEVELS`, and asserts the two name the same levels
in the same order. It deliberately does not assert which route sits at which level — that is a
judgement with a wrong answer, and it belongs to a reviewer. The test holds the vocabulary, which is
the thing that drifted silently.

A rule alone was not enough here before, and saying so is the point: the fleet exception was written
down honestly and read by nobody for the twenty-four hours it took three more levels to appear
beside it.
