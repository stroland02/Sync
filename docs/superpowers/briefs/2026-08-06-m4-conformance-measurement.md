# Brief — measure our own console the way the references were measured

You are working in your own Orca workspace on a branch based on `m4-dashboard`. Everything you need
is in the repository; nothing in this brief needs a conversation to interpret.

Your output is a **committed report and the backlog entries it justifies**, not a redesign. You are
the only workstream in this slice that is allowed to change nothing about the interface, and the most
useful thing you can produce is a table of numbers the next three sessions read instead of arguing.

## Read these first, in this order

1. `CLAUDE.md` at the repository root. Binding.
2. `.claude/rules/interface-originality.md` — read it before you open anything under
   `docs/superpowers/references/`. **Nothing under `docs/superpowers/references/screenshots/` is
   opened at any point in this task.**
3. `docs/superpowers/plans/2026-08-05-sync-console-architecture.md`, **section 8, "Where all three
   agree"** — fourteen properties on which three independently measured surfaces agree, with the
   invariant stated for each. Section 9 immediately after it lists the properties on which they
   contradict each other, and those are explicitly *not* a bar; do not measure against them.
4. `docs/superpowers/loops/console-improvement-tick.md`, the seven-item interface-quality checklist.
5. `DESIGN.md`, which is what our console claims about itself.
6. `docs/superpowers/plans/2026-08-06-sync-console-expansion.md`, workstream 4, which is this brief's
   parent.

## Why this is safe under the originality rule, and how to keep it that way

You are not comparing our screens to their screens. You are checking whether ours clears a bar that
three unrelated careful surfaces all clear independently — two type weights and no more, two ink
levels plus one accent, a type range of at least 3.4:1, three spacing levels each at least twice the
one below, one `@keyframes` and it is a spinner, nothing decorative running at rest, primary actions
that do not animate on hover.

Those are invariants about legibility and restraint. They are not a layout, a composition, a palette
or a component. If you find yourself writing "the reference does X, so we should do X", you have
crossed the line; the sentence that stays inside it is "three surfaces independently hold property P,
ours does not, and here is what that costs an operator reading a dense table."

## The method, which is the durable part

Every reference number was read from **Chrome at 1440×900, through `getComputedStyle` over every
element in the document, with a real pointer moved onto a control so `:hover` genuinely matched** —
not from markup, and not from looking at a screenshot. Reproduce that method against our own console.
`superpowers-chrome:browsing` is installed and is the intended tool; invoke it before you start.

A described impression cannot be contradicted by anything. A measurement can, and the reference work
proved that mattered: the fourth surface measured contradicted four of the invariants the first three
had agreed on, and it could only do that because both were measurements.

Run the console first, from the repository root:

```sh
SYNC_API_RELOAD=true uv run python -m sync.api
uv run python scripts/seed_console.py --scale 10000
cd web && npm run dev
```

`--scale 10000` matters for you specifically. Half of what you are measuring — prose measure, column
overflow, whether the provenance column survives at 1280px — only misbehaves on a table that is
actually long, and the base fixture holds five rows. `SYNC_API_RELOAD=true` is not optional; a
long-lived API process serves whatever Python it started with while Vite hot-reloads on top of it.

Measure every route in `web/src/lib/routes.ts`, including the two that landed on 2026-08-06 — the
pull request page and the Signals level. Two other workstreams are changing routes while you work,
so **record the commit SHA your measurement was taken at, in the report, on every table.** A number
without a SHA is worthless within a day.

## What to produce

**One report**, at `docs/superpowers/reports/2026-08-06-console-conformance.md`, containing:

1. A table with one row per invariant and one column per route measured, with the measured value and
   pass or fail. Not prose — a reader must be able to sort it by "how far off".
2. The seven checklist items answered per route, each with the evidence that answers it. Items 2
   through 6 were open as of `72450ae` and several design-system tasks have landed since; **re-check
   them against the running tree rather than trusting that note.**
3. A short section on what `DESIGN.md` claims versus what the rendered pixels do. The two have
   diverged before — a contrast pairing that passes on declared tokens can fail on rendered colour
   once opacity, layering or a chart fill is involved, which is why the design contract insists on
   measuring rendered pixels rather than tokens.
4. Exactly one paragraph naming which gaps are worth closing and which are not, judged by what they
   cost an operator reading a dense table. `CLAUDE.md`'s counterweight applies: a gap that would not
   make a later change slower or a defect quieter is polish, and polish competes with the milestone.

**Backlog entries** in `docs/superpowers/BACKLOG.md` for the gaps worth closing, in the house style —
what was measured, where, what closes it. One entry per gap, each with its number in it. A finding
without a number is an impression and does not get an entry.

**A check that keeps a gap closed**, where one is cheap. Some of these are testable from Python
against the TypeScript source in the way `tests/test_console_design_tokens.py` already is — a second
font weight appearing anywhere, a `@keyframes` block appearing that is not the spinner, a
`text-[10px]`. Where a rule can be held that way, hold it, tests first, and prove it RED by breaking
the thing deliberately before trusting it. Where it genuinely cannot — anything needing a rendered
page — say so in the report rather than writing a test that cannot fail. **A test that cannot fail is
worse than no test**; this repository has shipped three of them.

## The one command that lies

The seven-item checklist offers a detector scan as a shortcut. It exits **0** both when the page is
clean and when the browser engine was never installed, so a missing engine reads as a pass:

```bash
node -e "require.resolve('puppeteer')" || echo "URL SCAN INVALID"
```

As of 2026-08-05 `impeccable` was not a dependency here, not resolvable through `npx --no-install`,
and `puppeteer` was absent. If that is still true, answer the seven items by hand against the running
dev server. If you install the detector, that is a dependency decision — argue it in the report and
run the precondition before trusting any exit code.

## Constraints

- You may change interface code only where a fix is a one-line token or class correction that your
  own measurement proves and a test then holds. Anything larger is a backlog entry for another
  workstream, not your commit. Two other agents are editing `web/` right now.
- Commit path-limited, always. Never a bare `git commit`, and never `git stash pop` blind.
- Do not run `npm run build`, `npm run lint` or `npm run dev` from a second process against a tree
  another agent is building — `tsc -b` writes build state and `vite build` writes `dist/`. You have
  your own worktree, so this is safe here; it stops being safe the moment you reach outside it.
- Do not write to the database while measuring. Reads are fine; the fixture is written once at the
  start.
- Stop the API and dev server when you finish. A process left listening holds 8787 or 5173 for the
  next session.

## Your gate

```sh
uv run pytest tests/ -q
```

Clean. If you touched anything under `web/`, `npm run build` and `npm run lint` clean as well.

Commit in Conventional Commits form, body in normal prose explaining why. Push your branch. **Do not
open a pull request and do not push to `main`.** Report what you measured, not that you looked.
