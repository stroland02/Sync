# Brief — two documents that assert what the page does not do

You are working in your own Orca workspace on a branch based on `m4-dashboard`. Everything you need
is in the repository.

Both items below were found by measurement, not by reading, and both are the same shape: something
declares a fact and the rendered page contradicts it. `docs/superpowers/reports/2026-08-06-console-conformance.md`
carries the numbers, taken at `7d8e798`. **Re-measure before changing anything** — the tree has moved
— and if this brief is wrong, fix the brief in your commit.

## Read these first

1. `CLAUDE.md`. Binding.
2. `DESIGN.md`, especially its rendered-pixel section, which is the subject of the first item.
3. `.claude/rules/console-surface.md`, `.claude/rules/console-dev-loop.md`.
4. `docs/superpowers/reports/2026-08-06-console-conformance.md`.
5. `docs/superpowers/BACKLOG.md`, entries **B105** and **B106**.

## B105 — the contract's checkable section does not survive being checked

Four claims in the one section of `DESIGN.md` whose whole purpose is to be verifiable against a
screen are contradicted by that screen. The worst:

**The focus ring is published at 8.69:1 and renders at 3.08:1.** The *token* is 8.70. What renders is
`focus-visible:ring-ring/50` — the brand hue at half strength, compositing to `rgb(84, 101, 139)` —
which measures 3.08 against the card and 3.12 against the page plane. It clears the non-text floor by
0.08, and it is the **only** channel: `outline-style` is `none` and the border does not change under
focus. So 3.08 is the entire visual signal a keyboard user gets.

The outline button's two figures are wrong the same way, and one of them (12.09) is reproducible
against no backdrop in the ramp at all.

**The correction has two halves and both are required.** Fix the numbers so the document states what
renders — and decide whether 3.08 with no second channel is acceptable for the only focus signal in
the console. If it is not, that is a token or a class change, and the argument goes in `DESIGN.md`
rather than in a component. If it is, say so explicitly, because a figure that clears a floor by 0.08
with nothing beside it is a decision somebody should have made on purpose.

**Why the numbers went wrong is worth reading before you rewrite them.** The published figures were
computed from declared tokens; what renders is those tokens composited — alpha over a plane, in the
gamma-encoded sRGB Chrome actually blends in. A contrast figure derived from a token is not a
measurement of what a reader sees. Whatever you write, write how it was obtained.

## B106 — every heading list opens with a dialog that is closed

On all nine routes the first heading in the document is `h2 "Jump to a destination"` — the command
palette's title — ahead of the page's own `h1`.

`command.tsx` puts `DialogHeader` **outside** `DialogContent`. Radix unmounts the content when the
dialog is closed; the header is not inside it, so the title and its description sit in the document
permanently. A screen reader's heading list begins with a closed dialog, and the description is a
permanent 37-character paragraph in a 1px container that every prose measurement has to filter out.

This matters beyond accessibility hygiene, and the reason is in the tick's own checklist: **the
console's navigation hierarchy is the dependency graph, and the heading tree is the only
machine-readable assertion of which level you are looking at.** A tree that opens with a closed
dialog asserts the wrong root on every screen.

Move the header inside the content, and check what that does to the dialog's accessible name — Radix
wants a title associated with the content for exactly this reason, so verify rather than assume the
label survives.

## Constraints

- **The contrast floor is 5.05:1 for text against rendered pixels**, and it outranks any invariant it
  collides with. Never lower a contrast to satisfy something else.
- Twenty-four protected sentences: restyling allowed; deleting, shortening, collapsing behind a
  disclosure or moving into a tooltip is not.
- No composite score, health figure, traffic light, green dot or liveness pulse.
- If a rule here can be held by a test, hold it — `tests/test_console_design_tokens.py` reads the
  TypeScript from Python and is where a heading-structure or class guard belongs. Prove any new guard
  RED against the real tree first. **A test that cannot fail is worse than no test.**
- Logic with a wrong answer lives in Python. The console formats and renders.

## How to work

```sh
SYNC_API_RELOAD=true uv run python -m sync.api
uv run python scripts/seed_console.py
cd web && npm run dev
```

`superpowers-chrome:browsing` at 1440×900, `getComputedStyle`, real pointer for `:hover` and real
keyboard focus for the ring — a focus ring cannot be measured without focusing something. If 8787 or
5173 is held by another workspace, use another port and revert the proxy edit before each commit.

## Your gate

```sh
uv run pytest tests/ -q
cd web && npm run build && npm run lint
```

Clean, plus the measured figures for every number you write into `DESIGN.md`, and how each was
obtained.

Conventional Commits, subject carrying `M4-W149`. Push your branch. **No pull request, nothing on
`main`.**
