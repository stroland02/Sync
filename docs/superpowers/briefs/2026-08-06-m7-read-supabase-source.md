# Brief — M7-W159, read Supabase as source

You are working in your own Orca workspace. **Start by rebasing:**
`git fetch origin && git checkout -B m7-supabase-source origin/console-identity`. Note the base is
`console-identity`, not `m4-dashboard`.

## Why this is permitted, and what changed today

`.claude/rules/interface-originality.md` was amended on 2026-08-06 and **you must read the amendment
before anything else.** It previously listed "a layout, a screen composition, a navigation shape, a
visual hierarchy" among things that may not be taken, which — read literally, as it was — forbade
adopting a sidebar, a breadcrumb or a display type step because a competitor has one. The console
that resulted is measured in `docs/superpowers/reports/2026-08-06-why-the-console-came-out-flat.md`.

The rule now separates **the conventions of the form**, which are learnable from anything, from
**identity**, which is not. You are reading source for mechanism and stated reasoning. You are not
reading it for appearance, and you copy no component.

Supabase is open source: `github.com/supabase/supabase`. This is the same method already used on
`getsentry/sentry` and `grafana/grafana` — see section 20 of
`docs/superpowers/plans/2026-08-05-sync-console-architecture.md` for the shape of a good outcome and
the standard of citation it sets.

## Read these first

1. `CLAUDE.md`; `.claude/rules/interface-originality.md` (amended today);
   `.claude/rules/console-surface.md`.
2. `docs/superpowers/references/direction/NOTES.md` — five entries recording what the owner asked
   for, each with a mapping onto data we already hold. Your job is the mechanism behind those
   screens.
3. `docs/superpowers/reports/2026-08-06-why-the-console-came-out-flat.md`.
4. The M7 plan section of `docs/superpowers/plans/` (see `2026-08-06-m7-console-as-product.md` if it
   has landed; otherwise the brief set is the plan).

## What to read, and what to bring back

Clone shallow. Read **source**, not their docs site. For each item below produce a section in one
note, `docs/superpowers/references/notes/supabase-control-plane-mechanism.md`:

1. **The shell.** How the icon rail and the contextual sidebar compose; how a route declares which
   sidebar it belongs to; where the active state lives; how the sidebar collapses and what reflows.
2. **Layout primitives.** Their page header, control bar, footer bar — the props each takes, what is
   required versus optional, and what a page must supply.
3. **The empty state.** The component and its API. Ours are sentences; theirs say what would fill
   the space and how. What does the component require a caller to provide?
4. **The drawer/sheet.** How focus, history and dismissal are handled, and whether the URL carries
   it.
5. **The settings card** — title, explanation, control, its own Save. How is dirty state tracked and
   where does the cancel boundary sit?
6. **The metric panel** — value above evidence, and how the expandable rows beneath a chart are
   fetched and keyed.

For each: **file and line citations into the cloned tree**, the mechanism in your own words, and a
closing line — *what we would put in that slot, from data we already hold*. `direction/NOTES.md`
already maps most slots; use it rather than re-deriving.

## What makes this note good, and the one failure mode

The Sentry and Grafana notes are the standard. The failure mode they avoided and you must too:
**a note that describes what a component looks like is worthless.** What transfers is how it is
composed, what it requires of a caller, and what its authors wrote down about why.

Where their mechanism rests on something we do not have — a user model, live infrastructure metrics,
a write path — say so and stop. Do not design around it; that is Phase 6 and it belongs to M4's
hosted half.

**Record what you decline.** A mechanism you read and rejected is worth as much as one you adopt,
and this repository has re-derived rejected ideas more than once.

## Constraints

- **Copy no component and no class string.** If your note contains a JSX snippet from their tree
  longer than an identifier, it is the wrong note.
- No claim their screen makes that our data cannot support. Their confidence scores are refused
  however good the screen carrying them is.
- Nothing under `docs/superpowers/references/screenshots/` is opened. `references/direction/` is
  open to you — that is the owner's own material.
- Clone under your workspace's ignored scratch space, never into the repository.

## Your gate

```sh
cd <your workspace> && uv run pytest tests/ -q -n0
```

Clean — you are adding a document, so this is a regression check rather than a test of your work.
The note itself is the deliverable and its quality is the citations.

Conventional Commits, subject carrying `M7-W159`. Push your branch. **No pull request, nothing on
`main`.**
