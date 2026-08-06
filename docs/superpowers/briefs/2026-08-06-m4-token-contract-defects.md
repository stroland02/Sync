# Brief — the two places the token contract does not render what it declares

You are working in your own Orca workspace on a branch based on `m4-dashboard`. Everything you need
is in the repository.

**Read the tree before the description of it.** Every claim below comes from a measurement committed
at `docs/superpowers/reports/2026-08-06-console-conformance.md`, taken at `7d8e798`. The tree has
moved since. Re-measure before you change anything, and if this brief is wrong, fix the brief in
your commit.

## Read these first

1. `CLAUDE.md`. Binding.
2. `DESIGN.md` — the contract you are enforcing, and in one of these two cases, correcting.
3. `.claude/rules/console-surface.md`, `.claude/rules/console-dev-loop.md`.
4. `docs/superpowers/reports/2026-08-06-console-conformance.md`, the whole thing.
5. `docs/superpowers/BACKLOG.md`, entries **B104** and **B107**.

## The work

### B104 — a row costs twice what the contract says it costs

`table.tsx` spells `py-2.5` on `th` and `td`. **`py-2.5` is 10px**, off the 4px base the system is
built on, and on table-bearing routes it is the second most frequent padding value in the document —
918 occurrences against 926 of 8px on the binding surface.

`DESIGN.md`'s *Row height* section says `row-md` is *"the existing arithmetic made explicit —
`TableCell` already renders a 36px row from `text-body` and `p-row`; it was simply never named."*
**It never rendered 36px.** A single-line row measures 40px, and where `break-words` wraps a
call-site path to two lines it measures 80px. At 80px a 900px viewport holds about ten rows of a
ten-thousand-row table.

Two things have to come out of this and they are different in kind:

- **The pixels or the contract must move.** Either the padding becomes a named token whose value the
  contract states, or the declared 36px becomes what actually renders. Decide which, and say why in
  the commit body — the density argument is real, so do not assume smaller is right.
- **`DESIGN.md`'s sentence is false as written** and stays false until somebody edits it. A contract
  that misdescribes what it produces is worse than one that is silent, because the next reader
  measures nothing and trusts it. This is the same class as B105.

### B107 — a third neutral ink on the two densest screens

Section 8's invariant is two ink levels plus one accent, never three. Seven of nine routes hold it.
On the solution workflow and pull-request screens a third appears — `oklch(0.83 0 0)`,
`--color-ink-secondary`, three elements each — from the wrapper at `run-outcome.tsx` setting
`text-body text-ink-secondary` on a container the abandoned-run prose inherits from.

Those are the two screens carrying the densest evidence, which is where a third level costs most.

`DESIGN.md` names two ink levels for text and a `graphics` allocation rather than a third text step,
so either the wrapper takes `text-ink-muted` or nothing, **or** `ink-secondary` is genuinely the
right step for abandoned-run prose and `DESIGN.md` gains a third text level as an argued decision.
What is not acceptable is a third level arriving from a class nobody decided on.

## Constraints

- **Do not lower contrast to satisfy an invariant.** The floor is 5.05:1 against rendered pixels and
  it outranks the ink-count invariant; if the two collide, the floor wins and the collision is
  recorded.
- Twenty-four protected sentences: restyling is allowed, deleting, shortening, collapsing behind a
  disclosure or moving into a tooltip is not. **B107 touches abandoned-run prose — re-read your diff
  for a deleted qualification.**
- No composite score, health figure, traffic light, green dot or liveness pulse.
- `tests/test_console_design_tokens.py` holds the spacing and type floors and grew two guards
  yesterday. If your change is one a guard could hold, add the guard, and prove it RED against the
  real tree before trusting it.
- Logic with a wrong answer lives in Python. The console formats and renders.

## How to work

Measure, then change, then re-measure. `superpowers-chrome:browsing` at 1440×900 through
`getComputedStyle`, with `--scale 10000` for the row-height half — the cost of a row only shows on a
table that is long.

```sh
SYNC_API_RELOAD=true uv run python -m sync.api
uv run python scripts/seed_console.py --scale 10000
cd web && npm run dev
```

If 8787 or 5173 is held by another workspace, run on another port and revert the proxy edit before
each commit, as the review-wave worker did.

## Your gate

```sh
uv run pytest tests/ -q
cd web && npm run build && npm run lint
```

Clean, plus before-and-after numbers for anything you changed — a row height claim ships with the
measured height, not with the class you set.

Conventional Commits, subject carrying `M4.5-W142`. Push your branch. **No pull request, nothing on
`main`.**
