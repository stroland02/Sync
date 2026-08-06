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

`docs/superpowers/specs/2026-07-25-sync-self-maintaining-apis-design.md:427-445`, section *M4 —
Hosted control plane / Information architecture*.

**Cite the second block, not the first.** That section carries two fenced hierarchies. The one at
`:396-405` is the original and is kept deliberately unamended so its argument stays readable; the
one at `:429-443` is the amended block the document itself labels authoritative, and it is the only
one that holds `Fleet` and `Binding surface`. A citation against the first block is a citation
against a superseded diagram, which is the same failure as citing no document at all.

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

## What is supposed to hold it when nobody reads this, and does not yet

`tests/test_console_hierarchy.py` (Task 10 of `2026-08-05-sync-console-architecture.md`) is to parse
the specification's authoritative fenced block and `GRAPH_LEVELS`, and assert the two name the same
levels in the same order. It deliberately would not assert which route sits at which level — that is
a judgement with a wrong answer, and it belongs to a reviewer. The test holds the vocabulary, which
is the thing that drifted silently.

**That file does not exist yet, on this branch or on `main`.** The specification at `:447` and an
earlier draft of this rule both describe it in the present tense; they are describing Task 10, not
the tree. Until it lands, the only thing standing between `GRAPH_LEVELS` and a fourth invented level
is a reviewer opening the specification — which is exactly the check that failed three times. Write
the test before trusting the guard, and do not read either sentence as evidence one is running.

A rule alone was not enough here before, and saying so is the point: the fleet exception was written
down honestly and read by nobody for the twenty-four hours it took three more levels to appear
beside it.
