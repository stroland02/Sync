# Work items

One line per unit of work, in the form `M<milestone>-W<n>`. The number is a single sequence across
the whole project, never restarted per milestone — `M3-W125` and `M4-W126` are consecutive — so a
number identifies a piece of work without needing its milestone to disambiguate it.

The convention is not new. Work items ran from `W67` to `W125` under M3, in commit subjects and
dispatch briefs, and the register lived in an orchestration board that is no longer readable. This
file is that register, in the tree, so the sequence survives a session ending.

**Assigning one.** Take the next number, add the row before you start, and put the identifier in the
commit subject: `feat: M4-W131 ...`. A work item is one reviewable unit — the thing a brief asks for
or a tick takes — not one commit and not one file. Several commits under one number is normal; two
numbers for one change is not.

**A row is a fact, not a plan.** `landed` means the commit is on `m4-dashboard` and gated. Anything
else says what it actually is. A row whose state stops being true is a row to correct, and correcting
it belongs to whoever notices.

M4 continues the sequence at 126. Everything before that is in `git log`.

| Item | Subject | State | Where |
|---|---|---|---|
| M4-W126 | The Pull Request level and its evidence bundle | landed | `c808854`, `d0e316f` |
| M4-W127 | The Signals level: three roles, and the fifth kind of nothing | landed | `3855fd4`, `b39dcde`, `87f0d7f`, merged `e4284ae` |
| M4-W128 | Technical debt named as the scaling constraint in `CLAUDE.md` | landed | `d21ff71` |
| M4-W129 | The npx race that reads as a bad patch, and B99 | landed | `6d1de98` |
| M4-W130 | Repository scope on every level below Codebase — B92 closed | landed | `a628e77`, merged `e79fb5b` |
| M4-W131 | The expansion slice and four cold-start briefs | landed | `7d8e798` |
| M4-W132 | M4.5 split out so M4 can close | landed | `861673b` |
| M4-W133 | The session record a worker can actually open | landed | `0c6eb94` |
| M4-W134 | Reconcile the branch with `main`, and take the by-id read | landed | `99f542b`, `3962fcc` |
| M4-W135 | Filters that compose with repository scope — B90 slice 1 | landed | `f84e334` |
| M4-W136 | The review wave: one Critical, five Important, and an error surface | landed | five commits, merged; `node-standing.ts` and its Python source of truth |
| M4.5-W137 | The conformance measurement against the fourteen invariants | landed | `reports/2026-08-06-console-conformance.md`; gaps filed as B104-B107 |
| M4-W138 | The work-item register back in the tree | landed | this file |
| M4-W139 | The backlog stops describing a console that no longer exists | landed | five entries closed, B90 and B94 corrected, B99 collision resolved |
| M4-W140 | The decode census accounts for the borrowed wrapper's teardown | landed | `tests/test_decode_handlers.py` |
| M4-W146 | The quality milestone's items numbered and reserved | landed | this file |
| M4-W147 | A dispatched worker may never have started — the check that catches it | landed | `reports/2026-08-06-m4-session-record.md` |
| M4-W148 | One milestone table, and M4 says what is now true | landed | `BACKLOG.md` |
| M4-W149 | Two documents that assert what the page does not do — B105, B106 | landed | `cb6b3d6`; B108 filed for the aria-invalid rings |
| M4-W150 | Briefs for the four defects the measurement found | landed | this file |
| M4-W151 | The dev proxy takes a port instead of being edited to reach one | landed | `web/vite.config.ts` |
| CI-W154 | The CI optimization workstream: profiler, plan, daily tick, first profile | landed | `scripts/profile_ci.py`, `plans/2026-08-06-ci-optimization.md`, B111 and B112 |
| M4-W152 | The affordance brief, moved ahead of the architecture plan's remaining tasks | landed | `briefs/2026-08-06-m45-affordance-layer.md` |
| M4-W153 | The frontend test runner and the reachability guard — architecture Task 5 | landed | `briefs/2026-08-06-m4-frontend-test-runner.md` |

## M4.5 — the console is worth looking at

`docs/superpowers/plans/2026-08-06-m45-console-quality.md` carries the argument and the start
condition. **The milestone's first item is already running as M4.5-W137 above**, and it is
deliberately first: it is the measurement every task below closes against, so without it each of
them is an opinion.

The five numbers below are reserved rather than started. A reserved row is a claim about what the
work is, not about when it happens — the start condition is what decides that, and it is checkable:
Tasks 4 through 7 of the architecture plan landed, the review wave closed, the conformance report
published.

| Item | Task | State |
|---|---|---|
| M4.5-W141 | The affordance layer — a severity ordering in SQL and the ordering stated on screen, and the row that cost three wrapped lines to say nothing. B100 and B109 closed, B110 filed | pushed, `m45-affordance`, not merged |
| M4.5-W142 | Type, ink and space measured against rendered pixels — B104 and B107 closed, B108 filed | pushed, `m4-tokens`, not merged |
| M4.5-W143 | Motion audited: one of three framer-motion usages deleted after measuring it had never run, and the registry made a test. B113 and B114 filed | landed | `0de5a44`, `f3b3059` |
| M4.5-W144 | Density: the binding surface's rows 76px to 57px by factoring out the directory 2,500 rows shared. B110 closed, B115 filed | pushed, `m45-density`, not merged |
| M4.5-W145 | Rung composition per detector — length encodes composition, because volume drew three of four as a sliver reading 'found nothing' | landed |

## M7 — the console becomes a product

`docs/superpowers/plans/2026-08-06-m7-console-as-product.md`, on branch `console-identity`. The
milestone exists because the console clears eight of fourteen measured invariants and is still flat;
`reports/2026-08-06-why-the-console-came-out-flat.md` carries the six causes, all of them rules this
repository wrote rather than mistakes anyone made.

| Item | Subject | State | Where |
|---|---|---|---|
| M7-W157 | Why the console came out flat, and the three rules that caused it | landed | `cf3a161` |
| M7-W158 | The honesty sentences guarded before the screens they sit on are rewritten | landed | `7bef206` |
| M7-W159 | Read Supabase as source, for mechanism | landed | `references/notes/supabase-control-plane-mechanism.md` |
| M7-W160 | The chassis: one sidebar at two widths, a page header, and the two DESIGN.md refusals reversed on measurement. B116 filed, B115 re-measured | landed | `briefs/2026-08-06-m7-the-chassis.md` |
| M7-W161 | Landing on `main` is a scheduled fast-forward, not a milestone event | landed | `CLAUDE.md` |
| M7-W162 | The console's API was answered by an eight-hour-old zombie — B117 and B118 | landed | `.claude/rules/console-dev-loop.md` |
| M7-W163 | Phase 4: the Fleet level onto the chassis, and the display step proven on a feature route. Type range 2.67 to 4.00, side-by-side placements 1 to 4. B119, B120, B121 filed | landed | `briefs/2026-08-06-m7-phase4-fleet.md` |
| M7-W164 | Phase 4: the Binding surface and Vendor levels. Type range 2.00 to 4.00, the rung column visible without a sideways scroll in all six configurations, and the `ControlBar` collision closed by deleting one. B119 closed, B115 re-measured — 1280 is one pixel short | landed | `briefs/2026-08-06-m7-phase4-binding-surface.md` |
| M7-W165 | The Supabase-substrate spec: vendor `packages/ui` wholesale (owner ruling), two-tier navigation (owner reversal of direction note 6), theme contract swap, and the data-seam mapping that makes the ports safe | in progress | `specs/2026-08-06-sync-console-supabase-substrate-design.md` |

**M7-W160's navigation was rebuilt once, on the owner's ruling of 2026-08-06.** The first pass built a
56px icon rail of four product areas beside a 240px contextual panel, and collapsing removed the
panel — two components, which is not what a sidebar collapsing to a thin width is. What ships is one
list at two widths: every destination is a row at both, the four areas are group headings rather than
a navigation level, and an icon holds its vertical position when the labels go. Three rulings the
human can reverse, each argued in `web/src/layouts/app-frame.tsx`'s docstring:

- **Group heading rows are reserved when collapsed** — `h-9` kept, text `sr-only` — rather than made
  zero-height in both states. Zero-height would have meant no visible grouping expanded, which is
  what the grouping is for.
- **`area.purpose` and `reachedFrom` moved from rows of prose onto each row's `title` and accessible
  name.** A sentence that renders at one width and not the other changes the height above every icon
  beneath it. Neither is one of the twenty-four protected sentences; both were added by this item's
  own first pass.
- **The sidebar's auto-collapse threshold is 1473px, corrected from 1440.** At exactly 1440 the old
  rule expanded, and B115's re-measurement shows expanding there costs 20px on every row of the
  binding surface.
