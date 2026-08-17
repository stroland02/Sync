repo: stroland02/Sync
branch: main
path: web/src, docs/superpowers, .claude/rules

## Last sync
date: 2026-08-08T20:25:00Z

### Updated in this project
- Built `Sync Console.dc.html` — ten full-page screens on the repo's own token contract (dark-only, Supabase-derived OKLCH resolved in `web/src/index.css`).
- Vocabulary taken verbatim from source: `GRAPH_LEVELS`, `AREAS`, the five binding rungs, the eight workflow nodes, node standings and run outcomes.
- Honesty rules from `.claude/rules/console-surface.md` applied: no composite score, no health figure, no green dot, no liveness pulse; status colour always ships with a glyph and a word.
- Fleet grain is the change unit (findings sharing a vendor change × repository), expandable to call sites — a product decision, not a level.

## Screen map
| Screen | Built from |
| --- | --- |
| Fleet | `web/src/lib/routes.ts` (ROUTES `/`), `src/sync/dashboard/fleet.py` |
| Codebase | `routes.ts` `/repositories/:repoId`, intake/skip reporting in `docs/superpowers/reports/2026-07-29-directory-skips-recorded.md` |
| Vendor | `routes.ts` `/vendors/:vendorId`, `tests/fixtures/deprecations/openai.md` |
| Signals | `routes.ts` `/repositories/:repoId/observed` |
| Binding surface | `web/src/features/bindings/binding-surface-page.tsx`, `web/src/lib/format.ts` (`pathAfter`, `describeRung`) |
| Finding | `web/src/features/findings/finding-page.tsx` (two rungs on one screen) |
| Solution workflow | `src/sync/dashboard/queries.py` (`WORKFLOW_NODES`, `NODE_STANDINGS`, `_EVIDENCE_KEYS`) |
| Pull request | `web/src/features/pullrequests/pull-request-page.tsx` |
| Detectors | `web/src/features/detectors/*` (`rung-series.ts`, `detector-accountability.tsx`) |
| Settings & adapters | `docs/writing-a-vendor-adapter.md`, `docs/superpowers/reports/2026-07-29-adapter-selection-explains-its-refusal.md` |

## Notes
- Design system "Industry" was attached in the brief but is a light blueprint system; `.claude/rules/console-surface.md` records dark-only on the owner's explicit instruction and `DESIGN.md` as the authority for every visual value, so the repo contract was followed.
