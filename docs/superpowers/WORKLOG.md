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

**A row is a fact, not a plan.** `landed` means the commit is on the integration branch and gated —
`console-identity` since M7 opened, `m4-dashboard` before it, and `main` tracks the integration
branch by fast-forward at least daily. Anything
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

**All five landed and are merged to `main` as of 2026-08-07**, verified by
`git merge-base --is-ancestor` rather than from memory — three of these rows read "pushed, not
merged" for a day after they were not. What remains of "worth looking at" moved into M7, which
rebuilt the presentation layer the measurements below were taken against; the measurements still
stand as the before-figures M7 is judged on.

| Item | Task | State |
|---|---|---|
| M4.5-W141 | The affordance layer — a severity ordering in SQL and the ordering stated on screen, and the row that cost three wrapped lines to say nothing. B100 and B109 closed, B110 filed | landed |
| M4.5-W142 | Type, ink and space measured against rendered pixels — B104 and B107 closed, B108 filed | landed |
| M4.5-W143 | Motion audited: one of three framer-motion usages deleted after measuring it had never run, and the registry made a test. B113 and B114 filed | landed | `0de5a44`, `f3b3059` |
| M4.5-W144 | Density: the binding surface's rows 76px to 57px by factoring out the directory 2,500 rows shared. B110 closed, B115 filed | landed |
| M4.5-W145 | Rung composition per detector — length encodes composition, because volume drew three of four as a sliver reading 'found nothing' | landed |

## M7 — the console becomes a product

`docs/superpowers/plans/2026-08-06-m7-console-as-product.md`, on branch `console-identity`. The
milestone exists because the console cleared eight of fourteen measured invariants and was still
flat; `reports/2026-08-06-why-the-console-came-out-flat.md` carries the six causes, all of them
rules this repository wrote rather than mistakes anyone made.

**The plan was amended mid-milestone and the register reads oddly without knowing that.**
`specs/2026-08-06-sync-console-supabase-substrate-design.md` is the standing design from `M7-W165`
onward: on the owner's ruling, Supabase's `packages/ui` is vendored at code level, navigation went
two-tier, and the token contract became Supabase's. So `W157`–`W164` built a chassis from scratch
and `W165`–`W180` replaced it. The first pass is not dead work — it produced the honesty-sentence
gate every later port is merged against, the before-measurements the substrate is judged by, and the
finding that the console's flatness was caused by our own rules, which is what made the carve-out
arguable at all. `reports/2026-08-07-m7-what-was-built-and-what-drove-it.md` carries the whole
account, and `reports/screens/2026-08-07/` shows what it produced.

**Where M7 stands on 2026-08-07.** All nine levels are on the substrate. `M7-W182`, the fidelity
pass, is in flight. Phase 5 — the workflow as a narrative, and one binding drawn — and Phase 6, the
write path, are unbuilt; Phase 6 needs auth and tenancy and belongs to M4's hosted half.

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
| M7-W168 | Task 1 of the substrate plan: the interface-originality carve-out, direction note 6's reversal amendment, and the M7 plan pointer | landed | plans/2026-08-06-console-supabase-substrate.md |
| M7-W169 | Task 2 of the substrate plan: `packages/ui` vendored at 6ac0316 under `web/src/vendor/supabase/`, theme.css captured, NOTICE guard proven RED then green | landed | `web/NOTICE` |
| M7-W170 | Task 3 of the substrate plan: Supabase's dark palette, type ramp and radii become the declared token contract; DESIGN.md and its guard rewritten in one commit; contrast measured, deviations named | landed | `DESIGN.md` |
| M7-W171 | Task 4 of the substrate plan: the 40px icon rail and the contextual sidebar replace the single sidebar; routes gain area and pages; every level reachable from the rail | landed | `web/src/layouts/app-frame.tsx` |
| M7-W172 | Task 5 of the substrate plan: Fleet is the first level on the vendored components — mapping table first, fact tiles and metric panels, Studio table anatomy, completeness walk against the same seed | landed | `docs/superpowers/briefs/2026-08-07-substrate-fleet.md` |
| M7-W173 | Task 6: the Codebase level on the substrate — coverage and findings as metric panels, watched vendors in Studio table anatomy, mapping table first | landed | `docs/superpowers/briefs/2026-08-07-substrate-codebase.md` |
| M7-W174 | Task 6: the API Services level on the substrate — vendor changes and findings in Studio table anatomy, the at-least-once sentence kept, mapping table first | landed | `docs/superpowers/briefs/2026-08-07-substrate-api-services.md` |
| M7-W175 | Task 6: the Signals level on the substrate — sources as a role-grouped catalogue, telemetry tables onto the Studio anatomy, the not-attached sentences kept in the grid | landed | `docs/superpowers/briefs/2026-08-07-substrate-signals.md` |
| M7-W176 | Task 6: the Binding surface on the substrate — the join in Studio anatomy, a binding's detail in a URL-addressable drawer, one binding drawn as cards with its rungs | landed | `docs/superpowers/briefs/2026-08-07-substrate-binding-surface.md` |
| M7-W177 | Task 6: Errors & Incidents on the substrate — the faceted explorer keeps its zero counts, accountability keeps its abandoned attempts, the rung chart becomes a panel's evidence | landed | `docs/superpowers/briefs/2026-08-07-substrate-errors-incidents.md` |
| M7-W178 | Task 6: the Finding on the substrate — a fact rail beside the content column, the first detail-shaped level, the rung where a reference would put a score | landed | `docs/superpowers/briefs/2026-08-07-substrate-finding.md` |
| M7-W179 | Task 6: the Solution Workflow on the substrate — the node sequence as a narrative with evidence in place, the run's outcome stated where the run stopped rather than in a banner, the evidence blocks where a reference puts a 9 (a superseded generation is not on this payload: B124) | landed | `docs/superpowers/briefs/2026-08-07-substrate-workflow.md` |
| M7-W180 | Task 6: the Pull Request on the substrate — the evidence bundle as titled blocks at one depth, the fact rail left, the ninth level closes | landed | `docs/superpowers/briefs/2026-08-07-substrate-pull-request.md` |
| M7-W181 | The fidelity scout: 28 owner screenshots filed under `references/direction/`, and the gap analysis joining them against Studio's source at 6ac0316 and the console measured in Chrome | landed | `reports/2026-08-07-console-fidelity-gaps.md` |
| M7-W182 | The fidelity pass planned: six tasks from the gap report's five largest findings, before the final review | landed | `plans/2026-08-07-console-fidelity-pass.md` |
| M7-W183 | Fidelity Task 1: a 48px banner above the chassis — home, fleet/repository/vendor switchers with command-menu popovers, the palette trigger, and errors displacing rather than floating | landed | `web/src/layouts/scope-switchers.tsx` |
| M7-W184 | The two registers say what is true: M7 added to the milestone table, M4.5's five items corrected to landed, and In flight rewritten against measurement. **Its commit `bf19a2b` carries `M7-W183` in the subject** — the number was taken concurrently by the console session and the row above merged first, so this row holds the correction rather than the history being rewritten | landed | `bf19a2b` |
| M7-W185 | The 28 direction screenshots committed, one record of what M7 built and what drove it, and seven of our own screens beside them. **Its commits `25a4a10` and `d67c5c5` carry `M7-W181` in their subjects** — `7d8901b` had already taken that number and merged first, so it keeps it and this row holds the correction | landed | `reports/2026-08-07-m7-what-was-built-and-what-drove-it.md`, `reports/screens/2026-08-07/` |
| M12-W186 | M12 proposed: the four questions a panel must answer, the two prescriptions refused with their reasons, and the colour rule the disposition bar earned | landed | `plans/2026-08-07-m12-dashboards-that-earn-their-screen.md` |
| M7-W187 | The repository landing page: the console shown rather than described, a competitor table, the architecture drawn, and the honesty discipline stated as the differentiator | landed | `README.md` |
| CI-W189 | The 2026-08-07 profile and the series: B112 closed by per-run evidence, and no timing item taken because CI-W167 is landed but unmeasured | landed | `reports/ci-profile-2026-08-07.md` |
| CI-W190 | CI-W167 measured — critical path 211s to 156s — and the alarm it broke: a skipped job reports zero steps, so `never_acquired()` now separates it from a job no runner picked up | landed | `scripts/profile_ci.py`, `tests/test_profile_ci.py` |
| M7-W191 | `ARCHITECTURE.md`: the remediation state machine node by node, the tier cascade, provenance rungs, durable execution, and the three mechanisms that contain the agent | landed | `ARCHITECTURE.md` |
| M7-W192 | The systems move onto the front page itself — rungs, the state machine, the tier cascade, containment and the vocabulary are read on `README.md` rather than behind a link | landed | `README.md` |
| M7-W188 | Fidelity Task 2: the type ramp's middle is populated — section headings take `--text-section`, labels stay furniture, the display step stays `PageHeader`'s alone. **Dispatched as `M7-W186`** — `M12-W186` and `M7-W187` had both landed on the integration branch before this reached a commit, so it takes the next free number rather than a third duplicate | landed | `DESIGN.md` |
| M4-W166 | B117: `GraphStore` reconnects a closed connection, instead of handing the dead one back forever | dispatched | `briefs/2026-08-07-b117-graphstore-reconnect.md` |
| CI-W167 | B111 closed: coverage into its own nightly job, the serial job off `pull_request` and onto every push to `main`, and `event_name` in the concurrency group so a schedule and a push stop cancelling each other. PR critical path 200s to 123s | landed | `.github/workflows/ci.yml`, `reports/ci-profile-2026-08-07.md` |
| M7-W193 | Fidelity Task 3: the three detail headers span both columns and carry derived names; the hex id becomes a monospace rail fact. **Dispatched as `M7-W190`** — `CI-W190` landed on the integration branch while this was paused, so it takes the next free number rather than a duplicate, following `M7-W188`'s precedent | landed | `web/src/lib/detail-title.tsx` |
| M7-W194 | The milestone table and a dated progress summary say what is true: M7 at 88 percent, M0 stale by 1,073 commits rather than 200, M6 unblocked by M7 rather than M4.5 | landed | `BACKLOG.md` |
| M12-W196 | M12 Phase 1, first aggregate: abandonment by change kind and tier, so routing can learn what is not mechanically safe | dispatched | `briefs/2026-08-07-m12-abandonment-by-change-kind.md` |
| M12-W197 | The route exemption cannot outlive its panel, and B128 files the free-text `abandon_reason` the first read-back exposed (renumbered from B126 on landing, which collided with the repo-context item) | landed | `tests/test_api_routes.py`, `BACKLOG.md` |
| M7-W195 | Fidelity Task 4: the control and footer bars are fed — the vendor page's three narrowings leave a card body, `/detectors` gains the widen control the top bar cannot reach, record counts leave two `h2` headings for the footer under the rows they count, and the five list breadcrumbs stop repeating the top bar's scope trail | landed | `web/src/layouts/footer-bar.tsx`, `briefs/2026-08-07-substrate-fidelity-task-4.md` |
| M7-W198 | M7-W195's review: the untrimmed `Fleet` crumbs are four named routes rather than one, and the binding surface's kept crumb is redundant like `/detectors`' rather than informative like Signals' — a correction to the brief, no code | landed | `briefs/2026-08-07-substrate-fidelity-task-4.md` |
| M7-W199 | Fidelity Task 5: the rail expands on hover from 48px to 208px over the vendored primitive's own state machine, the two tiers stop sharing one active fill, and a second-tier row becomes a link wherever the address supplies its subject | dispatched | `briefs/2026-08-07-substrate-fidelity-task-5.md` |
| M4-W200 | B78 Tasks 1 & 3: Local zero-remote rehearsal fixture and 'sync rehearse' driver with verified digest and depth control | landed | `src/sync/rehearse/fixture.py`, `src/sync/rehearse/driver.py`, `src/sync/cli.py`, `tests/test_rehearse_fixture.py`, `tests/test_rehearse_driver.py` |
| M4-W201 | B78 Task 4: Rehearsal boundary across 4 independent layers (importlinter contract, graph node inspection, signature guard, zero remotes) | landed | `pyproject.toml`, `tests/test_rehearse_boundary.py`, `.claude/rules/remediate-stage.md` |
| M4-W202 | B78 Task 5: Rehearsals labelled in fleet runs table, outcome phrasing for local halts, tick verification updated to sync rehearse | landed | `web/src/features/fleet/runs-table.tsx`, `web/src/features/workflows/run-outcome.tsx`, `src/sync/dashboard/fleet.py`, `docs/superpowers/loops/console-improvement-tick.md` |
| M4-W203 | B78 Task 6: Rehearsal smoke gate asserting checkpointer terminal outcomes wired into CI | landed | `scripts/rehearse_smoke.py`, `tests/test_rehearse_smoke.py`, `.github/workflows/ci.yml`, `BACKLOG.md` |
| M4-W204 | B79: `is_rehearsal` joins `migration_outcome`'s natural key so a rehearsal row can no longer swallow a colliding production row | landed | `src/sync/graph/schema.sql`, `src/sync/graph/store.py`, `src/sync/core/models.py`, `src/sync/remediate/corpus.py`, `src/sync/remediate/graph.py`, `src/sync/rehearse/driver.py`, `tests/test_migration_corpus.py` |
| M7-W205 | B120: Routes cycle eliminated — App.tsx passes question prop down to screens, zero features import routes registry, guard added (renumbered from M7-W204 on landing) | landed | `web/src/App.tsx`, `web/src/features/**`, `tests/test_console_design_tokens.py`, `BACKLOG.md` |
| M7-W206 | B125: Workflow state forwards repo_id to Pull Request screen fact rail with Codebase link, consolidated asHttpUrl boundary helper in lib/url.ts | landed | `src/sync/dashboard/queries.py`, `web/src/lib/url.ts`, `web/src/features/pullrequests/**`, `web/src/features/workflows/evidence.tsx`, `web/src/api/types.ts`, `tests/test_dashboard_queries.py`, `BACKLOG.md` |
| M7-W207 | B127: Finding route forwards severity, call site, and repository; Finding level renders them on fact rail | landed | `src/sync/api/app.py`, `src/sync/mcp/tools.py`, `web/src/features/findings/**`, `web/src/api/types.ts`, `tests/test_api_routes.py`, `docs/superpowers/briefs/2026-08-07-substrate-finding.md`, `BACKLOG.md` |
| M7-W208 | B124: Solution workflow returns generations list across threads and renders superseded attempts | landed | `src/sync/dashboard/queries.py`, `web/src/features/workflows/**`, `web/src/api/types.ts`, `tests/test_dashboard_queries.py`, `docs/superpowers/briefs/2026-08-07-substrate-workflow.md`, `BACKLOG.md` |
| M7-W209 | Fidelity Task 6: table anatomy (subtle header strip, font-medium, column type/rung suffixes, distinct row hover vs selected state, table empty rows), empty state cards 8px radius; mock-to-build plan created | landed | `web/src/components/data-table.tsx`, `web/src/components/states.tsx`, `web/src/features/bindings/binding-surface-page.tsx`, `docs/superpowers/plans/2026-08-08-console-direction-parity.md` |
| M7-W210 | B123: Solution workflow extracts checkpointer timestamps per node and renders node clock window; no-clock sentence removed; implementation plans ledger indexed in BACKLOG.md | landed | `src/sync/dashboard/queries.py`, `web/src/features/workflows/**`, `web/src/api/types.ts`, `tests/test_dashboard_queries.py`, `BACKLOG.md` |
| M7-W211 | Code block language header strips and syntax containers across Solution Workflow and Pull Request evidence bundles; console mock-to-build tasks closed | landed | `web/src/features/workflows/evidence.tsx`, `docs/superpowers/plans/2026-08-08-console-direction-parity.md` |
| M7-W212 | B97: the container network-cutoff primitive, proven against a real Docker Desktop, and the patch-sandbox image it will run in (renumbered from M7-W207 on landing, which collided with B127) | landed | `src/sync/remediate/sandbox.py`, `docker/patch-sandbox/Dockerfile`, `tests/test_sandbox.py`, `tests/test_patch_sandbox.py`, `pyproject.toml`, `BACKLOG.md` |
| M7-W213 | B97: `disconnect_network`'s cutover race closed structurally — a risky-phase container's output is copied out and the container destroyed outright, rather than disconnected while its process keeps running; `ss -K` and `conntrack -F` were tried against this host's real Docker Desktop/WSL2 kernel first and both measured as ineffective; `probe_connect`'s dead substring check also tightened (renumbered from M7-W208, which collided with B124) | landed | `src/sync/remediate/sandbox.py`, `tests/test_patch_sandbox.py`, `tests/test_sandbox.py`, `scripts/dead_links_baseline.txt`, `BACKLOG.md` |
| M7-W214 | Claude Design ground-truth UI mockups imported into `docs/console-mock/`; console upgraded to match demo layout with ChangeUnitsTable, Scope filter tabs, Review CTA button, and single Area navigation cards; `migration_outcome` schema applied to resolve 500 error | landed | `docs/console-mock/*`, `web/src/features/fleet/change-units-table.tsx`, `web/src/features/fleet/fleet-page.tsx`, `src/sync/graph/store.py`, `docs/superpowers/WORKLOG.md` |
| M7-W215 | De-congest Fleet overview (eliminate stacked duplicate cards) and connect `ChangeUnitsTable` to 100% live backend API `useRuns` & `useOverview` data with zero fake items; Phase 5 Screen De-congestion added to `2026-08-08-console-mock-to-build.md` | landed | `web/src/features/fleet/change-units-table.tsx`, `web/src/features/fleet/fleet-page.tsx`, `docs/superpowers/plans/2026-08-08-console-mock-to-build.md`, `docs/superpowers/WORKLOG.md` |
| M7-W216 | Sidebar naming and organization aligned with demo ground truth (`docs/console-mock/Sync Console.dc.html`); `sync.console` top branding, Area purposes, and hierarchy footer notes added to `ContextualSidebar`; workflow systematic structure reviewed | landed | `web/src/layouts/app-frame.tsx`, `docs/superpowers/plans/2026-08-08-console-mock-to-build.md`, `docs/superpowers/WORKLOG.md` |
| M7-W217 | Eliminated "Fleet" terminology across console navigation, breadcrumbs, and headers; introduced Codebases-First hierarchy with front-page `CodebasesPanel` displaying watched repositories with vendor/finding rollups; nested `ChangeUnitsTable` in Codebase level | landed | `web/src/features/fleet/codebases-panel.tsx`, `web/src/features/fleet/fleet-page.tsx`, `web/src/features/repositories/codebase-page.tsx`, `web/src/lib/routes.ts`, `web/src/layouts/scope-switchers.tsx` |
| M7-W218 | Loading stops being static, without claiming a shape: `LoadingState` gains an indeterminate sweep and, past two seconds, the elapsed wait in whole seconds. One component, 52 call sites. The sweep is registered in `MOTION_USAGES` under the bar that file sets -- a request in flight holds a real duration -- and is deliberately not a skeleton, which would assert rows the answer may not have. Reduced motion stops the sweep and keeps the count, because that is information rather than movement | landed | `web/src/components/states.tsx`, `web/src/lib/motion.ts` |
| M7-W219 | Human-friendly finding badges (`f-2f725b`) and thread badges implemented in `web/src/lib/format.ts` and wired into detail breadcrumbs; Milestone `M13` registered in `BACKLOG.md` and planned in `2026-08-16-sync-m13-dynamic-visuals-and-telemetry.md` referencing DeepSeek Harness | landed | `web/src/lib/format.ts`, `web/src/features/findings/finding-page.tsx`, `web/src/features/workflows/workflow-page.tsx`, `web/src/features/pullrequests/pull-request-page.tsx`, `docs/superpowers/plans/2026-08-16-sync-m13-dynamic-visuals-and-telemetry.md`, `docs/superpowers/BACKLOG.md`, `docs/superpowers/WORKLOG.md` |
| M7-W220 | Live database seeding and continuous test-driven validation loop enabled; verified real DB checkpointer checkpoints, call sites, and findings via `scripts/seed_console.py` | landed | `scripts/seed_console.py`, `docs/superpowers/WORKLOG.md` |
| M7-W221 | The ten-screen console mock lands as a dated artifact with its provenance, its tour and twelve stills; the landing page shows it as unbuilt rather than as product, and `plans/2026-08-08-console-mock-to-build.md` splits it into six tasks across M7, M12 and M4 (renumbered from M7-W199 on reconciliation, which collided with Fidelity Task 5 on the other side of the divergence) | landed | `docs/console-mock/`, `plans/2026-08-08-console-mock-to-build.md`, `README.md` |
| M7-W222 | The console tour becomes the landing page's lede and the mock precedes the shipped captures, on the owner's instruction; the two sets are separated into *Where it is going* and *What is running today* so the reordering cannot read as a claim that the mock ships (renumbered from M7-W200 on reconciliation) | landed | `README.md` |
| M4-W223 | B128 lands: `abandon_reason_code`, a twelve-member closed vocabulary derived from the real routing paths in `sync.remediate.nodes`, travels beside `abandon_reason`'s free-text prose rather than replacing it; `migration_outcome_abandon_reasons_by_kind` groups on the code | landed | `src/sync/remediate/nodes.py`, `src/sync/remediate/state.py`, `src/sync/remediate/corpus.py`, `src/sync/graph/schema.sql`, `src/sync/graph/store.py`, `src/sync/dashboard/fleet.py`, `BACKLOG.md` |

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

**M7-W171 reversed that arrangement on the owner's later ruling, and the three items above are
history rather than current behaviour.** The chassis is two tiers again — a 40px rail of six areas
with Settings pinned last, and a 208px contextual sidebar on the vendored `sidebar` primitive — and
the collapse machinery is deleted rather than disabled. The defect that sank the first two-tier
attempt was reachability, not the arrangement: this one renders every one of the nine levels in the
sidebar of the area that owns it, and the walk in `.superpowers/sdd/2026-08-06-console-supabase-substrate/task-4-report.md`
records all nine reached with the heading, the group labels and the active row correct on each.
