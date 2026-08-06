# Brief — M4.5-W143, motion, and the discipline of not having any

You are working in your own Orca workspace. **Start by rebasing:**
`git fetch origin && git checkout -B m45-motion origin/m4-dashboard`. Your workspace is several
slices behind and starting from a stale base has cost two agents an hour each today.

## What this item is, and what it is not

This is not "add animation". Three reference surfaces were measured through `getComputedStyle` at
1440×900 with a real pointer, and they agree on something counterintuitive: **one `@keyframes` per
page and it is a spinner; nothing decorative running at rest; primary actions with
`transition-duration: 0s`, `transform: none`, no scale and no fade on hover.** One of them states
the rule outright — frequent interactions avoid animation altogether. Reading two dense open-source
applications as source overturned the earlier conclusion in the same direction rather than
softening it.

The console already acts on this: `web/src/index.css` zeroes transition duration document-wide, and
`table.tsx` records why the row hover has none — *the gate is frequency, not duration*. So the
global position is taken. **Your job is to check whether the exceptions earn themselves, and to make
the rule hold against the next person rather than against the current tree.**

## Read these first

1. `CLAUDE.md`; `.claude/rules/console-surface.md`; `.claude/rules/interface-originality.md`.
2. `DESIGN.md`, its motion section.
3. `docs/superpowers/plans/2026-08-06-m45-console-quality.md`, **Task 4**.
4. `docs/superpowers/plans/2026-08-05-sync-console-architecture.md`, **section 8** — the fourteen
   invariants, four of which are about motion — and **section 20** onward, where source reading
   confirmed them.
5. `docs/superpowers/reports/2026-08-06-console-conformance.md` — which invariants currently clear.

## The work

**1. Measure what actually moves.** Every route, at rest and under interaction, in Chrome at
1440×900:

- Count `@keyframes` reachable in the document, and say which rule each belongs to.
- Count animations *running at rest*. The target is zero, and "at rest" means after the page has
  settled with no pointer on it.
- Confirm no primary action animates on hover: `transition-duration: 0s`, `transform: none`.
- Note anything that moves on mount and did not need to.

Numbers, not impressions. `superpowers-chrome:browsing` is the tool, and a real pointer has to be
moved onto a control for `:hover` to match.

**2. Audit the three `framer-motion` call sites, and keep only what tracks a real state change.**
`components/error-surface.tsx`, `components/page-controls.tsx`, and
`features/workflows/node-sequence.tsx`.

The test each must pass: **motion claims a time, so it is permitted where the data holds one.** A
node advancing through the remediation graph holds a time. A page control appearing does not — a
paginator is furniture, and it is also one of the most frequent interactions on the console, which
is the case the reference rule names by name. Decide each on its own evidence and record the ruling
in the commit body, including for any you keep.

Deleting a dependency's only remaining callers is a legitimate outcome. If `framer-motion` ends up
unused, say so and let the next person decide whether to remove the package — do not remove it in
this commit, because that is a dependency decision with its own argument.

**3. Make the rule hold structurally.** A guard in `tests/test_console_design_tokens.py` (Python
reading the TypeScript) or in `web/src/**/*.test.*` (`vitest`, landed today as M4-W153) — whichever
can actually see the violation. Candidates: a second `@keyframes` appearing, a `transition-duration`
other than `0s` on an interactive element, an `animate-*` utility outside the spinner.

**Prove it RED against the real tree before trusting it.** Introduce the violation, watch the guard
fail, quote the failure in your report, restore. A test that cannot fail is worse than no test, and
this repository has shipped three.

## Constraints

- **Do not add motion to make the console feel modern.** The measured position of three careful
  surfaces is that a dense operational interface does not move. If you believe a specific animation
  earns its place, the argument is from the operator and the graph — not from it looking better.
- `prefers-reduced-motion` is not a substitute for the rule. It is a second, narrower promise, and
  it does not make an unearned animation earned for everyone else.
- No composite score, health figure, traffic light, green dot, liveness pulse or **count-up**. A
  count-up is animation *and* a false claim about a number arriving over time.
- Twenty-four protected sentences: restyling allowed; deleting, shortening, collapsing behind a
  disclosure or moving into a tooltip is not.
- Nothing under `docs/superpowers/references/screenshots/` is opened.

## How to work

```sh
cd /c/Users/strol/orca/Sync/Sync/.claude/worktrees/sync-m4-dashboard   # your own workspace path
SYNC_GRAPH_DSN=postgresql://sync:sync@localhost:5433/sync SYNC_API_PORT=<free> uv run python -m sync.api
uv run python scripts/seed_console.py
cd web && SYNC_API_ORIGIN=http://127.0.0.1:<free> npm run dev -- --port <free>
```

`SYNC_API_ORIGIN` exists so you never edit `vite.config.ts` to reach a port; a Python guard asserts
that file's fallback matches the API default, and editing it turns that guard red for everyone. Pick
free ports — **5173 is the owner's console and must be left alone** — and stop both servers when you
finish.

## Your gate

```sh
cd /c/Users/strol/orca/Sync/Sync/.claude/worktrees/... && uv run pytest tests/ -q
cd web && npm run build && npm run lint && npm test
```

All four clean, plus the before-and-after counts: keyframes, animations running at rest, and the
hover measurement on a primary action. Quote the guard's red output.

Conventional Commits, subject carrying `M4.5-W143`. Push your branch. **No pull request, nothing on
`main`.**
