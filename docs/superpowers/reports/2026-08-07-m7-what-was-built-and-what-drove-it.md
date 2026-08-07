# M7 so far — what was built, what drove it, and what it measured

Written 2026-08-07, covering `M7-W157` through `M7-W180` plus the backend and CI work that ran
beside them. It exists because the reference screenshots this milestone was built against were
sitting untracked on one machine while the documents that cite them were committed, and because two
sessions worked the same milestone from different directions and neither transcript is durable.

**This is a record, not an authority.** `specs/2026-08-06-sync-console-supabase-substrate-design.md`
is the standing design; `plans/2026-08-06-m7-console-as-product.md` is the plan it amends;
`references/direction/NOTES.md` is the owner's direction. Where this file and one of those disagree,
they are right.

## The reference material, now in the tree

`references/direction/` holds **28 screenshots the owner captured and supplied**, committed by this
work item. They were untracked until now — not ignored, simply never added — which meant `NOTES.md`
was a committed document pointing at files no clone had.

They are **not** the same material as `references/screenshots/`, and the distinction is load-bearing.
`.claude/rules/interface-originality.md` fences off that directory's 22 competitor captures from
being opened as a design target. `direction/` is the owner's own material, deliberately separate and
open, which is why briefs are allowed to point at it.

| Files | What they are | What they drove |
|---|---|---|
| `supabase-01`–`supabase-24` | Supabase Studio: project overview empty and populated, table and SQL editors, schema visualizer, database functions, extensions, an indexes drawer, settings, auth users and OAuth apps empty, edge functions and secrets, security advisor, observability, five report screens, query performance and its drawer, the logs explorer, integrations | The substrate rebuild, `M7-W165`–`M7-W180`. The empty screens mattered as much as the populated ones: an empty state that says what would fill it is a component contract, not a decoration |
| `superlog-01`, `superlog-02` | An incident detail and its findings tab | The workflow-as-narrative screen (`M7-W179`), and the source study merged as PR #2 |
| `superlog-03`, `superlog-04` | A sidebar expanded and collapsed | Direction note 6 — the sidebar correction — and then its reversal |

## What the console actually looks like

[`screens/2026-08-07/`](screens/2026-08-07/) holds seven of the nine levels captured from the
running console at this commit, at 1920 with no viewport override, so the substrate rebuild can be
compared against the reference material rather than argued about from memory. Its README carries the
capture conditions and two composition gaps the full-page views make visible.

## Two passes at the same milestone, and why there were two

M7 exists because the console cleared eight of fourteen measured invariants and was still flat.
`reports/2026-08-06-why-the-console-came-out-flat.md` traces six causes, **all of them rules this
repository wrote** rather than mistakes anyone made. The largest was `interface-originality.md`
listing "a layout, a screen composition, a navigation shape, a visual hierarchy" among things that
may not be taken — read literally, as every agent correctly read it, that forbade a sidebar because a
competitor has one.

**The first pass (`W157`–`W164`) built a chassis from scratch.** The rule was amended to separate the
conventions of the form from identity; a guard was put on the twenty-four honesty sentences before
7,900 lines of presentation were rewritten; a chassis replaced `layouts/`; and three levels were
recomposed onto it.

**The second pass (`W165`–`W180`) replaced that chassis with vendored Supabase components**, on the
owner's ruling of 2026-08-06 recorded in the substrate spec. Three earlier decisions were reversed:
`packages/ui` is adopted at code level under `web/src/vendor/supabase/` with attribution in
`web/NOTICE`; navigation went two-tier; and the token contract became Supabase's dark palette, type
ramp and radii.

The first pass is not wasted and is worth saying plainly rather than quietly retiring. It produced
the honesty-sentence gate that the substrate ports are still merged against, the measurements the
substrate work is judged by, and the finding that the console's flatness was caused by our own rules
— which is what made the carve-out arguable at all.

## What the numbers did

Measured in Chrome through `getComputedStyle` at 1440×900 and 1280×800, before and after, on every
item that claimed one.

| | Before M7 | After the first pass | Bar |
|---|---|---|---|
| Type range | 2.00–2.67:1 | 4.00:1 on Fleet, Binding surface, Vendor | **3.4:1** |
| Frame ratio | 3.0 | 5.0 on ten of ten routes | **4.7–7.2** |
| Regions placed beside another | 7 in the whole application | 4 on Fleet alone; 2 on the binding surface | — |

Three things were recorded as **not** met rather than smoothed over, and each is the reason to trust
the numbers that were:

- **The display step did not reach six of nine feature routes** in the first pass, because nothing
  under `features/` changed in the chassis item. `B116` filed the migration rather than the branch
  claiming a range it had not earned.
- **The binding surface at 1280 did not improve.** Its rows drop from 77px to 57px at 1170px of
  content width and nowhere else; 1280-collapsed grants 1137px. After the Card was dropped the
  threshold restated as 1138px of table width against 1137px granted — **one pixel short instead of
  33**, and `B115` was deliberately left open because "a one-pixel margin on one fixture is a
  coincidence rather than a fix."
- **The fact rail costs six table rows above the fold** at 1440, five at 1280 (`B121`).

## The sidebar, built three times

Worth recording because the cost was real and the reversal was deliberate.

1. The brief specified Supabase's arrangement — a 40px icon rail plus a separate contextual panel.
2. The owner corrected it to **one sidebar at two widths**, recorded as direction note 6: the same
   destinations at all times, ~215px expanded with icon and label, ~48px collapsed with the icons in
   identical vertical positions. `M7-W160` was reworked to satisfy it, and proved it by measurement
   rather than assertion — icon tops at 1440 were `104, 176, 212, 248, 284, 356, 392, 464, 500` in
   both states.
3. `M7-W171` reversed it back to two-tier on the vendored sidebar primitive, per the substrate
   ruling. Note 6 carries the reversal as an amendment rather than being rewritten.

The middle step also produced a test worth keeping: `web/src/layouts/app-frame.test.tsx` states
plainly that **jsdom has no layout** — `getBoundingClientRect` returns zeroes — and asserts the
structural cause instead. Its own first draft called `element.click()` outside `act`, so React never
flushed and every assertion compared the expanded tree against itself and passed. That draft was a
test that could not fail, caught before it shipped.

## What did not move, through both passes

- **The twenty-four protected honesty sentences.** `tests/test_console_honesty_sentences.py` guards
  seventeen distinguishing fragments and is deliberately not file-pinned, so a sentence may move into
  a new composition and only deletion or shortening fails. It landed before the rewrite began.
- **No composite score, health figure, traffic light, green dot, liveness pulse or count-up.** A
  vendored component with a slot for one renders the honest equivalent instead.
- **Absence apart from zero, staleness apart from liveness, never-measured apart from nothing-here.**
- **The provenance rung at two levels, monochrome, never behind a sideways scroll.**
- **The API stays read-only**, held behaviourally by `test_no_route_reaches_past_the_read_surface`.

## The backend and CI work that ran beside it

Not console work, and deliberately scoped away from it so two sessions could run in parallel.

- **`B117`, closed by `M4-W166`.** `GraphStore._connect` reconnected only when the cached connection
  was `None`, so a *closed* one was handed back forever and every route raised
  `OperationalError` until the process restarted. This took the owner's console down on 2026-08-06
  while Postgres was healthy and idle at 11 of 300 connections. The transactional ruling is the part
  worth reading: reconnecting under an open `transaction()` block would put later writes on a fresh
  autocommit connection while the block rolls back, so a depth counter blocks reconnect inside a
  block while a block that *starts* dead still gets a live connection.
- **`B118`, recorded not closed.** Killing a server's child leaves the shell wrapper holding the
  inherited listening socket, so a port reports `LISTENING` under a PID that no longer exists. Two
  consequences: kill the wrapper chain, not the child; and **a process that cannot bind logs
  `Application startup complete` before the bind error**, so a log tail that stops there looks like a
  healthy server and is not.
- **`B111`, open.** Roughly 280s of compute and 140s of the 200s critical path is the same suite three
  times per pull request. Each run has a real reason; what none of them requires is running on every
  pull request.
- **`B120`, open and worth doing before more ports.** A feature page cannot import `ROUTES`, because
  `routes.ts` imports every page and the cycle leaves `ROUTES` undefined at module-init. **`npm run
  build` does not catch it** — it is legal ESM and typechecks clean; only vitest saw it. Two workers
  independently invented a workaround. The fix belongs in `App.tsx`, which already maps over `ROUTES`.

## One trap that cost an hour, for the next session

**A fresh worktree cannot pass the suite.** `tools/` is gitignored, so a new checkout has no
`oasdiff` and 38 tests fail with 9 errors — identically under `-n auto` and `-n0`, which rules out the
usual Postgres-contention explanation. The only signal is a `FileNotFoundError` buried in the
failures. `bash scripts/bootstrap_tools.sh` fixes it, and the suite then returns the exact baseline.
