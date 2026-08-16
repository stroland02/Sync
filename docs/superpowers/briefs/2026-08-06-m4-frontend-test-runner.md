# Brief — M4-W153, the frontend test runner, and the guard that would have caught today's Critical

You are working in your own Orca workspace on a branch based on `m4-dashboard`.

**Start by rebasing.** `git fetch origin && git checkout -B m4-vitest origin/m4-dashboard`. Your
workspace is several slices behind, and starting from a stale base is what produced an eleven-file
conflict earlier today.

## Why this exists

`.claude/rules/console-dev-loop.md` states the rule and names the standing violation in the same
breath: *logic with a wrong answer lives in Python, because the console has no test runner* — and
`isRunTerminal` and `hasLiveRun` in `web/src/api/queries.ts` are classification in TypeScript with
nothing testing them. Their own docstrings say what a wrong answer costs: reading a live run as
terminal "stops the poll on a live run, which freezes the screen on a stale answer."

This morning's Critical was exactly that shape — two components classifying node status separately
and disagreeing about the same payload. It was fixed by moving the classification into Python. That
was the right call under the current rule, and it is not a general answer: some classification is
genuinely about rendering and belongs here.

Task 5 of `docs/superpowers/plans/2026-08-05-sync-console-architecture.md` is this work, and it has
never been started. **Decision 6 of that plan already ruled the deferral retired**, so you are
executing a decision, not making one.

## Read these first

1. `CLAUDE.md`, and `.claude/rules/test-discipline.md`.
2. `.claude/rules/console-dev-loop.md`, especially *Logic with a wrong answer lives in Python*.
3. `docs/superpowers/plans/2026-08-05-sync-console-architecture.md`, **Task 5** and **Decision 6**.
4. `docs/superpowers/references/engineering/testing-strategy.md`.

## The work, as the plan already specifies it

Install `vitest`, `@testing-library/react` and `jsdom`; add `"test": "vitest run"`; create
`web/vitest.config.ts`.

Then write the tests **failing first**, against behaviour that already exists, and watch each fail
for the reason you expect. The plan names the set:

- `isRunTerminal` over every outcome value, including `running` and `null`.
- `hasLiveRun` over an empty page, a page of terminal runs, and a mixed page.
- The cardinality threshold: at, below, above.
- The disclosure-header count including zero — **a section labelled "(0)" is a fact and must render
  rather than be suppressed.**
- `describeRung` over every member of the rung union plus an unknown value, which must produce the
  "vocabulary has changed" sentence rather than a blank.
- `formatElapsed` over null, zero, and a value spanning units.
- **Every route in `lib/routes.ts` is reachable from the shell**, and every route `App.tsx` declares
  is in the registry.

**Then prove the reachability guard can fail**: remove one entry from the registry's navigation
grouping, watch it go red, restore it. A guard that has never rejected anything has not been shown
to guard, and this repository has shipped three guards that could not fail.

Wire `npm test` into the existing `web` job in `.github/workflows/ci.yml`.

Finally, record in `CLAUDE.md`'s test-discipline section that TypeScript is now test-first too, with
Decision 6's scope: **classification and structural invariants, never class names, never
snapshots.** A snapshot test in a console being actively restyled is a test that fails on every
correct change, and it will be deleted within a week by whoever it blocks.

## Constraints

- The Python guards that read TypeScript stay. `tests/test_console_design_tokens.py` and
  `tests/test_console_hierarchy.py` assert over the *source text* against a specification, which is
  a different question from behaviour and does not move.
- Do not port the node-standing classification back into TypeScript. It landed in Python this
  morning with tests; this task gives the console a runner, it does not reopen that ruling.
- Adding three dev dependencies is the point of the task, so no dependency argument is needed — but
  keep it to those three. `@testing-library/user-event` and friends are a separate decision.
- If a test you write cannot fail, delete it. That is worse than not writing it.

## How to work

```sh
cd web && npm test
```

The API is not needed for any of this. If you want the console running to check something, pick free
ports and pass `SYNC_API_ORIGIN` — five workspaces share this machine and 8787 and 5173 are usually
taken.

## Your gate

```sh
uv run pytest tests/ -q
cd web && npm run build && npm run lint && npm test
```

All four clean, plus the recorded evidence that the reachability guard went red when you broke it
and green when you restored it. Quote the failure.

Conventional Commits, subject carrying `M4-W153`. Push your branch. **No pull request, nothing on
`main`.**
