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















## 2026-08-17: five parallel lanes, 72 work items















**This file is a register, not a report.** It records what landed, in order, so a number identifies







work without anyone having to remember it. For *status* -- what is done, what is being worked now,







and what to do next -- read `BACKLOG.md`'s "Where development stands, 2026-08-17 evening", which is







written against `git log` and a measurement rather than against memory.















Today's rows come from five lanes working concurrently under







`orchestration/2026-08-17-lane-charters.md`. Reading them in file order is misleading, because five







lanes interleave; read them by prefix instead:















| Prefix | Lane | What it covers |







|---|---|---|







| `M0-W233`..`W255` | coordinator | Orchestration itself: charters, the resume sweep, arbitrations, and the beta scope. Every one of these exists because something went wrong in coordination and was fixed |







| `M5-W300`..`W308` | D | Signals, adapters, intake, and the two `B7` verification passes |







| `M10`, `M8`, `M9` | A | The resolution loop: the runner seam, the outcome vocabulary, durable runs, and B151 |







| `M12-W320`..`W324` | E | Graph, dashboard, API: the aggregates, the intake table, corpus health, merge-rate wiring |







| `M14-W228`..`W341` | B | The console: mock-parity, Gate 3's screen pass, and the production-servable artefact |







| `CI-W233`..`W289` | C | CI, gates, and `beta_gates.py` |















**Numbers are allocated per lane in blocks** so two sessions cannot claim one number -- that







happened five times in one afternoon before the blocks existed. The blocks are in the charter. A







commit subject may carry a pre-renumber number where a collision was found on landing; the row is







the authority, and it says so where that happened.















Three rows are worth reading even if you read nothing else, because each is a defect the workspace







found in itself rather than in the product: `M0-W244`, a safety net that reported success while







doing nothing; `M0-W250`, an arbitration that was unenforceable because the coordinator had told







every lane to skip the test that enforced it; and `M0-W253`, the gate meter contradicting the







coordinator within minutes of landing.















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







| M7-W224 | Staleness apart from liveness, on every polled surface rather than one: `FetchedAt` renders `dataUpdatedAt` as a ticking age and says whether a poll is still scheduled or has stopped, with the caller naming why it stopped. No dot and no pulse -- `CLAUDE.md` refuses a liveness pulse, and nothing in the data distinguishes a working poll from one whose last three attempts failed. The ticking clock is factored into `lib/elapsed.ts` at its second use | landed | `web/src/components/fetched-at.tsx`, `web/src/lib/elapsed.ts`, `web/src/features/fleet/runs-table.tsx`, `web/src/features/workflows/workflow-page.tsx` |







| M0-W225 | B129: a scan emptied the migration corpus, the repository context it had seeded moments earlier, and three tables of telemetry it does not produce — the allow-list `truncate_all(keep=("call_site",))` held one name against seven tables. A scan now names what it clears, `truncate_signal_and_detect()`, and `keep` is deleted | landed | `src/sync/graph/store.py`, `src/sync/cli.py`, `src/sync/benchmark/score.py`, `tests/test_scan_preserves_durable_rows.py`, `tests/test_cli.py`, `tests/test_cli_declines.py`, `tests/test_cli_wiring.py`, `tests/test_deprecation_urgency.py`, `tests/test_deprecation_wiring.py`, `.claude/rules/graph-grain.md`, `BACKLOG.md` |







| M7-W226 | Vitest coverage for `NodeEvidence` component across scalars, flags, language-tagged blocks, and unnamed properties; dev server verified live on port 5173 with proxy to 8787 | landed | `web/src/features/workflows/evidence.test.tsx`, `docs/superpowers/WORKLOG.md` |







| M13-W227 | M13 Phase 1: Reasoning & Strategy disclosures in Solution Workflow `NodeEvidence` component, providing structured deductions across AST transforms, compiler checks, sandbox safety, and CI polling inspired by DeepSeek Harness | landed | `web/src/features/workflows/evidence.tsx`, `web/src/features/workflows/evidence.test.tsx`, `docs/superpowers/WORKLOG.md` |







| M8-W228 | M8's runner seam: `PatchRunner` in `sync.core.protocols`, `sync.runner` owning every line that knows a model SDK exists, and an import-linter contract proving `sync.remediate` reaches none of it. `StaticRunner` replaces `monkeypatch.setattr(agent_patch, "query", ...)` across six test files, so the remediation suite needs no key. A full-depth rehearsal run then paid for itself three times: it found the refusal the runner was throwing away — `continue_: False` makes the CLI exit non-zero, so `query()` raised and the reason read after the loop never survived, leaving `Claude Code returned an error result: success` in `abandon_reason` — it found B135 — the clone's own `.claude/settings.json` was configuration Sync obeyed, so a `SessionStart` hook in a customer's repository ran arbitrary shell before `tool_gate`, a `PreToolUse` hook, was on the path at all, closed here with `setting_sources=[]` — and it filed B133 and B134, every `migration_outcome` write failing on any database created before B79 | landed | `src/sync/core/protocols.py`, `src/sync/runner/**`, `src/sync/remediate/agent_patch.py`, `src/sync/remediate/tool_gate.py`, `src/sync/remediate/tool_output.py`, `pyproject.toml`, `tests/test_patch_runner_seam.py`, `BACKLOG.md` |







| M0-W230 | B130: the documented first run is executable and stays that way (renumbered from M0-W228 on landing, which collided with M8's runner seam) — the oasdiff asset is chosen per platform, one `DEFAULT_DSN` serves the API and the CLI, the read-only API refuses an empty database by name instead of 500ing every route, and `--repo`'s argparse type refuses a path the forge cannot address while argv is being read | landed | `scripts/oasdiff_asset.sh`, `scripts/bootstrap_tools.sh`, `src/sync/graph/store.py`, `src/sync/api/__main__.py`, `src/sync/cli.py`, `tests/test_day_one_path.py`, `tests/test_bootstrap_tools.py`, `README.md`, `CONTRIBUTING.md`, `BACKLOG.md` |







| M3-W229 | B131: the four generated-SDK vendors bind no call site and a run reported that as a clean scan; adapters now declare `unbindable_reason` and `cli.run` prints it before the finding count, so "we found no call sites" and "nothing here could be looked at" are no longer one output | on branch `b131-generated-vendors` | `src/sync/signals/generated/adapter.py`, `src/sync/signals/mcp_server/adapter.py`, `src/sync/cli.py`, `tests/test_unbindable_vendor_report.py`, `tests/test_shipped_conformance.py`, `BACKLOG.md` |







| M0-W231 | B132: the local gate could not finish — `-n0` killed after 70 minutes with no output, diagnosed to unbounded `DROP DATABASE` queueing on the immediate checkpoint each one forces, not to the `docker`-marked tests as suspected; every admin statement now bounded server-side and named on timeout, the pre-header sweep budgeted, `pytest-timeout` added as a 900s watchdog, the test server's durability traded for an 18x cheaper drop, and an absent Docker daemon turned into a skip that says so | landed | `tests/conftest.py`, `tests/test_gate_is_bounded.py`, `tests/test_leaked_database_sweep.py`, `tests/test_schema_convergence.py`, `docker-compose.yml`, `pyproject.toml`, `BACKLOG.md` |







| M10-W229 | Sync asks GitHub what became of a pull request it opened. `open_pull_request` returned a number and the run ended, so `pr_merged` was null on every corpus row and merge rate -- the direct test of the product claim -- had no numerator. `pull_request_outcome` reads `state`, `mergedAt` and the commit authors in one `gh pr view`, and answers with `PullRequestOutcome`. Three distinctions the corpus turns on are in the type rather than in a caller: an open pull request is `None` rather than `False`, because a reviewer who has not decided is not a reviewer who said no; a merge is read from `mergedAt` rather than from "not OPEN", because a merge is also a close; and a commit GitHub cannot attribute counts as somebody else's, so the untouched-patch figure is never flattered by missing data | landed | `src/sync/forge/github.py`, `tests/test_pull_request_outcome.py` |







| M7-W230 | Mock-to-build Task 6 (renumbered from M7-W227 on landing, which collided with M13-W227): the palette lists nine destinations instead of two. It filtered `ROUTES` down to the routes it could link to, which reads as honesty and is not -- an operator who opens the console's own list of destinations and finds Codebases and Detectors learns the console has two screens. A route needing a subject is now listed as a place to look one up, carrying the registry's `reachedFrom` and its route pattern, and cannot be followed; dropping it hides a screen and linking it renders `/findings//workflow`, and the row that names where to pick a subject is the only answer that is neither. `paletteGroups` is pure over the registry so the rule is tested as a derivation | landed | `web/src/layouts/command-palette.tsx`, `web/src/layouts/command-palette.test.tsx`, `docs/superpowers/plans/2026-08-08-console-mock-to-build.md` |







| M4-W231 | Mock-to-build Task 5: Settings exists, read-only, and is a destination rather than a tenth level. Full-stack, because the adapter table needed a read surface nothing had built: `registered_adapters` reads what the deployment configured without constructing an adapter, `GraphStore.vendor_intake_rollup` says what each has delivered, and `adapter_inventory` joins them. **An adapter the graph holds no row for answers `null`, never `0`** -- zero is a measurement and its absence is the state an operator looking for a silently-stopped adapter needs, and every step from that null to the cell has a `?? 0` in it. Two of the task's three interfaces are built as written; the merge policy panel is refused, because no merge policy exists in `sync.forge` and a panel naming one would assert a configured fact the system does not hold. A `decline_reason` is refused for the narrower reason that nothing records an intake **attempt**, only its result -- filed as B136 and held by a test asserting the field's absence | landed | `src/sync/signals/registry.py`, `src/sync/graph/store.py`, `src/sync/dashboard/adapters.py`, `src/sync/api/app.py`, `web/src/features/settings/**`, `web/src/lib/routes.ts`, `tests/test_adapter_inventory.py` |







| M0-W233 | Six sessions get lane charters: a lane owns files rather than tasks, work-item and backlog numbers are pre-allocated per lane so the five collisions of one afternoon cannot recur, and the shared registers are resolved by union rather than by one side winning. Carries the loop every worker runs -- catch up, claim, test-first, gate locally, land on `main` by fast-forward, report -- and the traps that have each cost an hour | landed | `docs/superpowers/orchestration/2026-08-17-lane-charters.md` |







| M0-W234 | The development loop survives the session that started it: `scripts/orchestration/resume_lanes.py` re-attaches any lane whose worker stopped, and a scheduled task runs it every twenty minutes. Three stall shapes are distinguished because they look identical from the task list -- a dispatch that failed, one that reads `dispatched` but never attached to a terminal (`worker-start` gives up after a minute against a busy TUI, which is the common case), and one whose terminal has gone silent past the threshold. It re-attaches and never invents work, because choosing a lane's next item is a coordinator judgement | landed | `scripts/orchestration/resume_lanes.py`, `docs/superpowers/orchestration/2026-08-17-lane-charters.md` |







| M0-W235 | The whole remaining scope to beta, as six rulings rather than a survey. Beta is a design-partner beta and not a self-serve hosted product, which shrinks M4's obligation to *reachable and showing real data* and puts tenancy and the write path out. The gate is evidence rather than features: four gates, and the sharpest is that merge rate has never had a sample while the acceptance run is over a thousand commits stale. M10 in and M11 out; M5's correlator in, because the console renders the `observed` rung today and a rung nothing produces is a promise; M6, M13 and most of M12 out. Each lane's queue is ordered against those gates and marked for which gate it serves | landed | `docs/superpowers/plans/2026-08-17-sync-to-beta-scope.md` |







| M0-W236 | The resume sweep can place a lane whose dispatch never recorded a terminal, which is the case it most needs to handle: a dispatch stores its assignee only once `worker-start` succeeds, and the common stall is that it never did against a busy agent's TUI -- so exactly the lanes needing resumption were the ones with no handle to resume onto. A coordinator-written map beside the script supplies the fallback, and an absent or unreadable map degrades to no fallback rather than stopping the sweep | landed | `scripts/orchestration/resume_lanes.py`, `scripts/orchestration/lane_terminals.json` |







| M0-W237 | Two coordinator corrections from what workers measured rather than from what the charter assumed. `-n auto` is not the safe opposite of `-n0`: it has crashed an xdist worker outright here and Lane C measured the same independently, so the full-suite default becomes `-n 4` -- a crashed worker aborts the run and reads as a catastrophe that is not one. And the dead-link red on `main` gets a standing arbitration rather than five separate diagnoses: leave it, name `21b99f6`, Lane A wires it because the file is Lane A's, and any lane may exclude that one test meanwhile if it says so | landed | `docs/superpowers/orchestration/2026-08-17-lane-charters.md` |







| M0-W238 | The resume sweep stops reporting a dropped response as a failed restart. Orca returns `runtime_unavailable` when it closes the connection before answering, and twice here the mutation had landed anyway -- the retry dispatch existed while the sweep printed FAILED. A safety net that misreports is worse than none, because the misreport is trusted precisely when nobody is watching. It now re-queries the dispatch after an error and distinguishes queued from failed | landed | `scripts/orchestration/resume_lanes.py` |







| M0-W239 | Three charter gaps the first afternoon of six-agent work exposed, each measured rather than anticipated. Mail is only read when asked for, so an arbitration can sit unread through an hour-long turn -- reading it becomes step 0 of every iteration. Every Orca terminal is bound to the shared `main` worktree, so working nowhere in particular puts six agents in one checkout; that worktree was found mid-merge with four unmerged entries and an index changing between reads seconds apart. And landing is per unit, not per plan: five lanes produced sixteen commits and landed none, one branch eleven ahead of an hourly-moving `main` | landed | `docs/superpowers/orchestration/2026-08-17-lane-charters.md` |







| CI-W280 | B150: CI was red on `main` and its one scheduled run reported success over a failing suite. Five causes, each verified against the code before it was touched: a `gh` stub that ignored `--pattern` and so tested the platform its fixture was named for rather than the mapping B130 built; a corpus fetched four steps *after* the suite that refuses without it, and absent from `serial` and `coverage` entirely; a checkpointer migration ledger left behind by a module that never uses the checkpointer, which made every later `PostgresSaver.setup()` a silent no-op and cost fourteen `test_seed_console` tests under `-n0`; both B97 container positive controls disarmed on Linux because `host.docker.internal` is a Docker Desktop name, so the only evidence the network boundary holds was measuring nothing; and a nightly whose sole job re-raised pytest's exit code only above 1, recorded `success` over `5 failed, 3632 passed`. Fixed in the tests and the workflow, never in `sandbox.py` -- widening the thing under measurement to make the measurement work is the wrong direction on a security boundary. Two dead-link violations are left red on purpose and named, because they belong to a session mid-way through wiring them | landed | `.github/workflows/ci.yml`, `tests/test_ci_gates_what_it_runs.py`, `tests/test_oasdiff_pin.py`, `tests/test_rehearse_smoke.py`, `tests/test_patch_sandbox.py`, `BACKLOG.md` |







| M8-W218 | B129: Reconcile table unique constraints on existing database in `GraphStore.apply_schema`; B130: `CorpusRecorder` tracks attempt, failure, and error stats | landed | `src/sync/graph/store.py`, `src/sync/remediate/corpus.py`, `tests/test_migration_corpus.py`, `tests/test_migration_recording.py`, `tests/test_decode_handlers.py`, `BACKLOG.md` |







| M9-W219 | M9's outcome vocabulary: five outcome tools (`report_findings`, `propose_patch`, `report_external_cause`, `ask_human`, `abandon`) with flat top-level schemas, 1..10 confidence calibration rubric, strict citation parsing with path:line and fenced quotes, model-directed validator with actionable feedback, retired redirects, and `external_cause` node distinct from abandonment | landed | `src/sync/core/outcomes.py`, `src/sync/runner/outcome_tools.py`, `src/sync/remediate/nodes.py`, `src/sync/remediate/graph.py`, `src/sync/remediate/state.py`, `tests/test_outcome_vocabulary.py`, `BACKLOG.md` |







| M10-W220 | M10's durable runs and the human turn: durable execution loop with `park` node, `parked` state vocabulary, GitHub webhook parsers for `pull_request_review`, `pull_request_review_comment`, and `check_run` events, review feedback formatting with diff context, `resume_durable_run` checkpointer wake-up with turn progression and follow-up commits | landed | `src/sync/remediate/durable.py`, `src/sync/forge/webhook.py`, `src/sync/remediate/graph.py`, `src/sync/remediate/nodes.py`, `src/sync/remediate/state.py`, `tests/test_durable_runs.py`, `tests/test_decode_handlers.py`, `WORKLOG.md` |







| M5-W300 | Twilio RequestCorrelator: route building from symbol map, instance & collection path resolution through URL templates with privacy boundary, case-insensitive method matching, and conformance kit verification | landed | `src/sync/signals/twilio/adapter.py`, `tests/test_twilio_adapter.py`, `tests/test_shipped_conformance.py`, `WORKLOG.md` |







| M12-W320 | M12 aggregates: Fleet change-unit grain view model and cross-detector rung tally. `change_units` groups open findings across repositories by vendor change (vendor_id, operation_id, change_kind, versions) with distinct repository and call-site counts and unified/weakest evidence rung, joined with checkpointer standing and checkpoint age. `detector_accountability` computes the cross-detector tally of open findings across all 5 known evidence rungs (`static`, `resolved`, `observed`, `unresolved`, `unattributed`), counted once per open finding. Both view models served via Starlette `/api/change-units` and `/api/detectors` | landed | `src/sync/dashboard/fleet.py`, `src/sync/dashboard/graph_views.py`, `src/sync/api/app.py`, `src/sync/api/__main__.py`, `tests/test_dashboard_fleet.py`, `tests/test_graph_views.py`, `tests/test_api_routes.py` |







| M12-W321 | Gate 2 blocker: Wire `GitHubForge.pull_request_outcome` to the corpus. `GraphStore.set_merge_outcome` now records the exact instant GitHub holds in `mergedAt` (rather than stamping `now()`), and `GraphStore.repo_id_for_finding` / `repo_ids_for_findings` resolves repository per finding through call sites. `sync.benchmark.reconcile.reconcile_pull_request_outcomes` queries pending pull requests, updates `migration_outcome` rows with merge decisions and human edit counts, unlocking the numerator for `sync.benchmark.axes.compute_axes` merge rate | landed | `src/sync/graph/store.py`, `src/sync/benchmark/reconcile.py`, `src/sync/benchmark/__init__.py`, `tests/test_reconcile_merge_outcomes.py` |







| M12-W322 | B136: `intake_attempt` table in `schema.sql` and `IntakeAttemptSink` store implementation. `GraphStore.record_intake_attempt` persists adapter inquiries idempotently under natural key `(vendor_id, attempted_at, from_version, to_version)` with closed 17-member reason code vocabulary; `GraphStore.intake_attempts` queries recent attempts with time-descending ordering | landed | `src/sync/graph/schema.sql`, `src/sync/graph/store.py`, `tests/test_intake_attempt_store.py` |







| M12-W323 | Corpus health view model and `/api/corpus/health` route. `sync.dashboard.fleet.corpus_health` aggregates quality axes from `migration_outcome` via `sync.benchmark.axes.compute_axes`, mapping each of the 5 quality axes (`merge_rate_by_change_kind`, `merge_rate_by_tier`, `routing_accuracy`, `tokens_per_merged_patch`, `wall_ms_per_merged_patch`) with distinct `status` ("measured" vs "unmeasured"), `has_samples`, `sample_count`, `value` (null vs measured float/breakdown), and `runs_contributed`. Wired to Starlette transport `/api/corpus/health` | landed | `src/sync/dashboard/fleet.py`, `src/sync/api/app.py`, `src/sync/api/__main__.py`, `tests/test_corpus_health_view.py`, `tests/test_api_routes.py` |







| M12-W324 | Wire `reconcile_pull_request_outcomes` to CLI commands `sync reconcile-pull-requests` and `sync benchmark --reconcile`, and baseline `GraphStore.intake_attempts` in `dead_links_baseline.txt`. Pull request reconciliation now has an end-to-end driver that updates `migration_outcome` rows with GitHub merge outcomes and human edit counts, closing beta Gate 2's last link. All dead-link lint checks pass | landed | `src/sync/cli.py`, `scripts/dead_links_baseline.txt`, `tests/test_reconcile_merge_outcomes.py` |







| M12-W325 | Provenance and sample counts across all 5 quality axes: `Axis` and `corpus_health` now carry `provenance` alongside `value` and `sample_count` (`n`), distinguishing `production`, `rehearsal`, `mixed`, and `unmeasured` runs. Verified arithmetic of all 5 quality axes (`merge_rate_by_change_kind`, `merge_rate_by_tier`, `routing_accuracy`, `tokens_per_merged_patch`, `wall_ms_per_merged_patch`) with extensive unit tests over direct synthetic rows. Proved that `is_rehearsal` rows in `migration_outcome` are explicitly distinguishable via table/model columns and filtered out of production readers, preventing rehearsal data from contaminating live corpus metrics | landed | `src/sync/benchmark/axes.py`, `src/sync/dashboard/fleet.py`, `tests/test_benchmark_axes.py`, `tests/test_corpus_health_view.py` |







| M0-W240 | The safety net stops making a token outage permanent. Two lanes hit their session limit at once with a two-hour reset ahead of them, and the twenty-minute sweep would have retried each of them six times -- Orca circuit-breaks a task after three consecutive dispatch failures, so the mechanism built to survive an outage would have permanently failed two healthy lanes about an hour into one that resolves itself. The sweep now reads the terminal's own tail for a budget notice and holds instead, because silence cannot distinguish a thinking agent from an exhausted one. The check sits ahead of the dry-run branch, so a preview reports the verdict a real run would reach, and the notice is ASCII-folded before printing because stdout is cp1252 here and a box-drawing glyph in the tail crashed the one path that exists for an outage | landed | `scripts/orchestration/resume_lanes.py` |







| M14-W260 | Make ledgers true: reconcile console plan statuses against the tree before build work starts | landed | `docs/superpowers/BACKLOG.md`, `docs/superpowers/plans/2026-08-08-console-mock-to-build.md`, `docs/superpowers/plans/2026-08-16-sync-m13-dynamic-visuals-and-telemetry.md`, `docs/superpowers/WORKLOG.md` |







| M14-W261 | Raw-utility guard over `web/src/features/` with a shrinking baseline; pytest detects new raw Tailwind utilities not in `console_raw_utilities_baseline.txt` and fails until pair count is reduced to zero | landed | `tests/test_console_raw_utilities.py`, `tests/console_raw_utilities_baseline.txt` |







| M14-W262 | Baseline mock-gap measurement across all nine console routes, seeded fixture against the running dev loop, compared to `docs/console-mock/screens/`; no code changed | landed | `docs/superpowers/reports/2026-08-17-console-mock-gaps.md` |







| M14-W263 | `DetailGrid`, the console's one two-column detail shape, factored out of five hand-spelled grids that had started to drift into two mirrored literals; adopted in `finding-page`, `pull-request-page`, `workflow-page` (rail start) and `vendor-page`, `binding-surface-page` (rail end) with no change to child order, rail side, or any of the pages' protected prose | landed | `web/src/layouts/detail-grid.tsx`, `web/src/layouts/detail-grid.test.tsx`, `web/src/features/findings/finding-page.tsx`, `web/src/features/pullrequests/pull-request-page.tsx`, `web/src/features/workflows/workflow-page.tsx`, `web/src/features/vendors/vendor-page.tsx`, `web/src/features/bindings/binding-surface-page.tsx` |







| M14-W264 | Fleet back on the shared chassis: `PageHeader` carries the route's question and its one primary action, `ControlBar` carries the scope and the `chipSurface`-styled repository filters, `FactTile` carries the health-score-policy paragraph. `proposedPatchTarget` replaces the hardcoded CTA link to an invented finding id with the newest run whose outcome is `opened`, absent entirely when none has; five raw Tailwind utilities retired from the guard baseline | landed | `web/src/features/fleet/proposed-patch.ts`, `web/src/features/fleet/proposed-patch.test.ts`, `web/src/features/fleet/fleet-page.tsx`, `tests/console_raw_utilities_baseline.txt` |







| M14-W265 | `CodebasesPanel` rewritten so every claim on a repository card comes from an answer scoped to that repository: `codebase-cards.ts`'s `cardFacts`/`matchesFilter` refuse an overview computed for a different `repo_id` and hold `openFindings` null (never zero) until the scoped answer arrives; `useRepoOverviews` issues one `/api/overview` query per repository at `useOverview`'s own key shape. Deleted the `["acme/payments-api"]` and `"Stripe"` fallbacks, the emerald/amber judgement badges, the unattributable "Remediation active" row (`RunRow` carries no `repo_id`), and the unsupported "Index status: verified" line; eleven raw-utility rows retired from the guard baseline | landed | `web/src/features/fleet/codebase-cards.ts`, `web/src/features/fleet/codebase-cards.test.ts`, `web/src/features/fleet/codebases-panel.tsx`, `web/src/features/fleet/codebases-panel.test.tsx`, `tests/console_raw_utilities_baseline.txt` |







| M14-W266 | Conformance check rather than rebuild: `a4a0fd4` (M4-W231, Settings as a destination) and `ab5514d` (M7-W230, the palette's nine destinations) landed this plan's Tasks 13 and 14 independently. Both hold every structural requirement -- `DESTINATIONS` is its own array, `GRAPH_LEVELS` stays at nine with `test_console_hierarchy.py` green untouched, subject-taking routes render as lookups carrying `reachedFrom` and the route pattern. Two rulings recorded in the plan instead of code changes: Task 13's absence panels were superseded by `GET /api/adapters` actually being built, which is a better answer to the same honesty requirement and keeps null distinct from zero; and the shipped `DESTINATIONS` name stands against the plan's `DESTINATION_ROUTES`, because renaming a landed export to match a plan is churn | landed | `docs/superpowers/plans/2026-08-17-console-mock-parity.md` |







| M5-W301 | Adapter conformance against configured vendors: Anthropic & Vercel staged SDK source support in GeneratedSpecAdapter with symbol resolution, sdk_generator dispatch, and test_shipped_conformance suite verification | landed | `src/sync/signals/registry.py`, `tests/test_shipped_conformance.py`, `tests/test_vendor_registry.py`, `WORKLOG.md` |







| M0-W241 | A lane must confirm its lane before its first landing, because a dispatch delivering a spec is not an agent having read it. Lane A was mid-task when its charter arrived, never acted on it, and spent twenty-four minutes rebuilding the change-unit aggregate Lane E had already landed as `M12-W320` -- two lanes, one implementation, discovered only when a coordinator sweep read a terminal. It also stalled asking whether the coordinator was genuine, which was correct caution and cost nothing; the duplication cost the half hour. The charter now asks for a one-time acknowledgement naming lane, paths and number block, and says how to verify a coordinator instruction in two commands rather than stall on it | landed | `docs/superpowers/orchestration/2026-08-17-lane-charters.md` |







| M0-W242 | The dead-link red is re-measured and has three causes with one owner each, not the one the earlier arbitration named: `pull_request_outcome` (the coordinator's own, `M10-W229`), `dispatch_webhook_event` (Lane A, M10 event ingress) and `ensure_image_built` (Lane A, B97). All three are the same shape -- a primitive landed without the consumer that calls it -- so the arbitration now names the rule rather than the instance: do not land a producer with no consumer, and if one must land early, baseline it in the same commit naming the item that removes the baseline. Three accumulated in an afternoon because each author judged their own piece complete, and the cost falls on the lanes gating around a red they did not cause | landed | `docs/superpowers/orchestration/2026-08-17-lane-charters.md` |







| M0-W243 | Three defects in the sweep, all found by running it against five live lanes and all of them false alarms in the dangerous direction. `--retry-of` is only valid against a settled dispatch, so passing it to three active ones reported three healthy lanes as failures; a dispatch Orca still considers running is not the sweep's to restart at all, because forcing it is how a merely-quiet worker gets circuit-broken. The budget markers missed `Individual quota reached`, so a real two-hour outage read as a stall. And the dry-run branch sat above the staleness check exactly as it had above the budget check, so a preview again took a different path from the run it previews -- now every verdict is reached identically and only the mutation is skipped | landed | `scripts/orchestration/resume_lanes.py` |







| M0-W244 | The durable safety net was inert and reported success while being it. `orchestration task-list` answers for the Run bound to the invoking terminal, and a Windows scheduled task is not an Orca terminal -- so every fire saw zero tasks, printed `no open lane tasks; nothing to resume` and exited zero, three times, while five lanes were open. Caught by reading the log rather than trusting that an armed task is a working one. The sweep now names its Run explicitly from a `_run` key recorded beside it, falls back to the newest Run and says it is guessing, and treats an unresolvable Run as a failure rather than as a quiet workspace | landed | `scripts/orchestration/resume_lanes.py`, `scripts/orchestration/lane_terminals.json` |







| M0-W245 | Two charter corrections forced by B151, the first of them mine to own. The trap note said a run failing in the hundreds is Postgres bouncing; `main` was then measured 60 tests red for a real reason with Postgres healthy throughout, so my own guidance would have sent every lane to the wrong conclusion. Environmental is now defined by the failure text -- `starting up`, `in recovery mode`, `connection failed` -- and anything else is a real regression wearing a large number. Second, a crashed xdist worker prints `F` against tests that never ran at `-n 4` too, so `-n 4` is a better default and not a cure, and a run without a summary line is not a result | landed | `docs/superpowers/orchestration/2026-08-17-lane-charters.md` |







| CI-W281 | B151 filed against Lane A: `main` is 60 tests red on `origin/main` at `acc0617` and it is not environmental — 23 `GraphRecursionError`, 3 `KeyError: 'report_reason'`, attributed to `12e416a`'s removal of `report_reason` from `RunState` and its attempt-counter rewrite. Two gate defects of Lane C's own recorded with it: a crashed xdist worker reads as mass failure at `-n 4`, and one test exceeds 600s | landed | `docs/superpowers/BACKLOG.md` |







| CI-W282 | B152: a crashed xdist worker printed `F` against tests that never ran, and three runs of one tree read as 30 failures, 60 failures and 1 failure. `scripts/gate_verdict.py` answers whether a run's verdict can be believed at all, separately from whether the suite passed; proven against the four real captures from today's gating | landed | `scripts/gate_verdict.py`, `tests/test_gate_verdict.py`, `docs/superpowers/BACKLOG.md` |







| M14-W267 | Raw-utility baseline driven to zero across the last eight features files: `py-0.5` to `py-field` (findings, signals, workflows evidence); bare `rounded`/`rounded-lg` to `rounded-control` or `rounded-surface` chosen by whether the element is a control/chip or a panel/card (fleet change-units table, pull-request evidence bundle, workflows evidence/run-outcome/superseded-generations/workflow-page); the three fleet run-outcome palette spellings (`text-emerald-400`/`text-amber-400`/`text-rose-400`) to the declared status tokens (`text-good-ink`/`text-warning-ink`/`text-critical-ink`), each still carrying its symbol and word. `rounded-full` on `node-sequence.tsx`'s circular status markers is a shape the radius scale cannot express, so the guard's own regex now excludes it instead of tolerating it via the baseline, with the docstring saying why | landed | `web/src/features/findings/finding-page.tsx`, `web/src/features/signals/signals-page.tsx`, `web/src/features/workflows/evidence.tsx`, `web/src/features/fleet/change-units-table.tsx`, `web/src/features/pullrequests/evidence-bundle.tsx`, `web/src/features/workflows/run-outcome.tsx`, `web/src/features/workflows/superseded-generations.tsx`, `web/src/features/workflows/workflow-page.tsx`, `tests/test_console_raw_utilities.py`, `tests/console_raw_utilities_baseline.txt` |







| M14-W268 | Vendor and Codebase say what contains them: the two routes of nine that rendered no breadcrumb now carry one. A vendor narrowed by a repository names that repository in its trail and an unnarrowed vendor does not, because inventing a crumb would claim a path the reader never took. `Crumb` takes `to`, not the `href` the plan's text guessed at | landed | `web/src/features/vendors/vendor-page.tsx`, `web/src/features/vendors/vendor-page.test.tsx`, `web/src/features/repositories/codebase-page.tsx`, `web/src/features/repositories/codebase-page.test.tsx` |







| M14-W269 | Task 9 refused on inspection rather than implemented: both charts it targets are stacked bars whose length carries magnitude and whose hue carries identity, so M12's invariant (colour may not carry a fact length or position already carries) has a false precondition here -- `corpus-chart.tsx` has a single unlabelled y-category, and de-hueing it would delete the only channel saying which disposition a segment is. The rung chart's apparent breach of the monochrome-rung rule was checked rather than assumed: that rule governs the rung as prose furniture, and the chart meets the colour-never-alone bar with a legend, axis labels, inline segment labels and `absentRungs` in words, verified in the option builder | landed | `docs/superpowers/plans/2026-08-17-console-mock-parity.md` |







| M0-W246 | Two honesty defects in how the sweep reports a budget outage. The banner was matched anywhere in the tail, so once a lane recovered its own scrollback would have held it for as long as the notice stayed in the buffer -- a stop condition with no end. It is now only believed within the last six lines, because a recovered agent pushes its banner up the scrollback and that movement is the proof. And the countdown inside the notice was captured when the agent stopped, not now, so a frozen `resets in 2h` read as live an hour later and overstated the outage by exactly the time already served; it is reported with how long ago it was captured | landed | `scripts/orchestration/resume_lanes.py` |







| M14-W270 | The activity timeline, derived from checkpoints and nothing else: `activityEntries` renders one entry per node that wrote `first_seen_at` plus one unstamped closing entry for the run outcome, refusing mock screen 07's CI/PR events and refusing to synthesise an outcome timestamp the payload never records. `omittedCount` counts nodes with no timestamp so their absence is stated rather than silently shortening the list. `primaryDetail` reuses `evidence.tsx`'s exported `FIELDS` order rather than building a second evidence vocabulary. `ActivityTimeline` renders through `MetricPanel` with the caption "Assembled at read time from the checkpointer. Nothing writes a timeline row." and no liveness claim. Not wired into `workflow-page.tsx` -- that is Task 12's | landed | `web/src/features/workflows/activity.ts`, `web/src/features/workflows/activity.test.ts`, `web/src/features/workflows/activity-timeline.tsx`, `web/src/features/workflows/evidence.tsx`, `docs/superpowers/WORKLOG.md` |







| M14-W271 | The raw-utility guard stops reading prose as code, and two follow-ups on the activity timeline. The guard scanned whole file text, so a docstring quoting a class name tripped it and the reader's fix was to reword the docstring -- `evidence-bundle.tsx` had to stop naming the class M7-W179 changed, which is the guard making a file's history less accurate. Comments are now stripped before the scan and that sentence is restored verbatim; narrowing to `className=` attributes was rejected instead, because a class string held in a variable (`change-units-table.tsx` builds one per run outcome) would have escaped, proven by injecting one and watching the guard still catch it. `primaryDetail` now passes over an evidence value that is present but empty rather than surfacing a blank line under a timestamp, and the omitted-nodes sentence reads "One node has" rather than "1 nodes have" | landed | `tests/test_console_raw_utilities.py`, `web/src/features/pullrequests/evidence-bundle.tsx`, `web/src/features/workflows/activity.ts`, `web/src/features/workflows/activity.test.ts`, `web/src/features/workflows/activity-timeline.tsx` |







| M0-W247 | A dispatch id is not a stable address for a lane and the coordinator had been caching them. It changes on every re-dispatch, so a high-priority broadcast about a 60-test regression was addressed to a dispatch the sweep had already replaced -- `ok=true`, no delivery, and the lane reporting `count: 0` while the coordinator believed it had been told. Resolve it with `dispatch-show` in the same breath as the send; the terminal handle is the durable identity. For a message that must arrive, `terminal send` reaches a busy agent as its next input rather than waiting for it to ask for mail | landed | `docs/superpowers/orchestration/2026-08-17-lane-charters.md` |







| M0-W248 | The budget hold gains an expiry, which is the half of automatic resumption that was missing. An exhausted agent produces no output, so its banner never scrolls out of the window the previous fix bounded -- the hold had no way to end, and the mechanism built to survive an outage would have made it permanent. The sweep now parses the agent's own stated window from the notice, and once that long has passed since it was printed, stops believing the banner and retries. Only the duration form is parsed; a wall-clock reset needs a timezone, and guessing one ends a hold early. Every hold now reports how much of its window is left | landed | `scripts/orchestration/resume_lanes.py` |







| CI-W283 | B152 reaches CI: all three jobs that run pytest capture their output and ask `gate_verdict.py` whether the run can be believed, on failure too. `set -o pipefail` so the capture cannot swallow the exit code the nightly fix restored | landed | `.github/workflows/ci.yml`, `tests/test_ci_gates_what_it_runs.py` |







| CI-W284 | B150's adversarial review, run late because the first reviewer died on a session limit. Its MAJOR: the nightly gate was escapable by `continue-on-error` on the step or the job, or a script ending `exit 0`, with all four assertions staying green. Closed, with the reviewer's three mutants as negative controls. B132's superseded prediction about the container tests struck through against what was measured | landed | `tests/test_ci_gates_what_it_runs.py`, `docs/superpowers/BACKLOG.md` |







| M14-W272 | Task 11: three honest dynamics on the node sequence. `sequence-dynamics.ts` derives which ink a node earns (`inkFor`, recessed only for the two never-visited standings), the newest timestamp any node has stamped (`latestEvidenceAt`), and which node's evidence opens without a click (`defaultDisclosed`, the last node the run actually reached). `node-sequence.tsx` wires all three: node name and purpose sentence take `text-ink-muted` when unreached, markers unchanged; every node's evidence sits behind a `button[aria-expanded]` disclosure, evidence being data rather than a protected sentence; and an unfinished, stamped run shows "since last evidence -- staleness, not liveness" beside its due node, ticking on `useNow(1000)` and surviving reduced motion by the `LoadingState` (M7-W218) precedent -- no pulse, no dot, anywhere. Also carries out the controller ruling on M13-W227's "Reasoning & Strategy" disclosure: that text is static and identical across every run of a node, so titling it as reasoning and nesting it inside the evidence block let it read as something the run recorded. Moved out of `NodeEvidence` entirely, retitled "How this node works", and rendered beside the purpose sentence instead of folded into `PURPOSE` -- the two answer different questions (what a node does vs. how it does it) and merging them would blur the always-visible one-sentence purpose into a two-register paragraph | landed | `web/src/features/workflows/sequence-dynamics.ts`, `web/src/features/workflows/sequence-dynamics.test.ts`, `web/src/features/workflows/node-sequence.tsx`, `web/src/features/workflows/node-sequence.test.tsx`, `web/src/features/workflows/evidence.tsx`, `web/src/features/workflows/evidence.test.tsx`, `web/src/features/workflows/workflow-page.tsx`, `docs/superpowers/WORKLOG.md` |







| M14-W273 | Coverage restored for the text W272 rehomed. W272 correctly deleted the test asserting a "Reasoning & Strategy" disclosure inside `NodeEvidence`, because that placement was retired on a ruling -- static per-node text framed as reasoning the run recorded. It left no test behind for the rehomed form, so the claim its docstring makes is now asserted instead: the mechanics disclosure is not contained by the evidence panel, and a node the file does not name renders no description rather than inventing one. Proven to bite by moving the text inside the panel and watching the containment assertion fail | landed | `web/src/features/workflows/node-sequence.test.tsx` |







| M14-W274 | Task 12: the workflow route recomposed into mock screen 07's two-pane shape. The eight-node `NodeSequence` -- opening entry, nodes, and the `RunOutcome` closing entry at whichever position `narrative-order.ts` places it, none of that touched -- moved out of the content column and into the rail, wrapped in a `MetricPanel` titled "Node by node" carrying the caption "Eight nodes, in the order the graph wires them. A standing is the checkpoint's own answer -- nothing here says a node is executing.". The content column now reads `FetchedAt`/`StaleBanner`, then the `ActivityTimeline` Task 10 built and left unwired, then `SupersededGenerations`. No sentence was deleted; the evidence-bundle link paragraph stayed put in the rail above the new panel | landed | `web/src/features/workflows/workflow-page.tsx`, `web/src/features/workflows/workflow-page.test.tsx`, `docs/superpowers/WORKLOG.md` |







| M5-W302 | Index tsc resolve_lock cache warming: skip lock once typescript npx cache is warm, eliminating test serialization and starvation across concurrent test runs and workers | landed | `src/sync/index/tsc.py`, `tests/test_tsc_npx_race.py`, `WORKLOG.md` |







| M12-W242 | The Fleet change-unit panel wired to real data. `M12-W320` landed `sync.dashboard.fleet.change_units` and its route, but `ChangeUnitsTable` still derived fake rows from `/api/runs` and `/api/overview` client-side -- `repoId`, `reposCount` and `rung` were hardcoded, the claim-the-data-cannot-support defect `console-surface.md` exists to catch. `fetchChangeUnits`/`useChangeUnits`/`ChangeUnitRow` read the real route now, and the `_NOT_YET_FETCHED_BY_CONSOLE` exemption for it is removed since the panel is what it was waiting on. **Numbered `M12-W321` before landing** -- collided with `M12-W321` above (Gate 2's `pull_request_outcome` wiring), landed on `origin/main` first; renumbered here into this lane's own reserved block rather than amending the already-existing local commit | landed | `web/src/api/client.ts`, `web/src/api/queries.ts`, `web/src/api/types.ts`, `web/src/features/fleet/change-units-table.tsx`, `tests/test_api_routes.py` |











| CI-W285 | CI-W283's own defect, caught by CI within a minute of landing: `if: always()` ran the verdict check in a job that had exited seven steps earlier, so it failed with `suite-test.log does not exist` — a second red naming a file rather than what broke. Guarded with `hashFiles`, keeping the missing-path refusal that is correct on its own terms | landed | `.github/workflows/ci.yml`, `tests/test_ci_gates_what_it_runs.py` |







| M14-W275 | Task 15: the closing measured walk, and the Gate 3 screen-pass evidence. Repeated Task 3's baseline method exactly (1440x900, `deviceScaleFactor: 1`, the same snippet) over the same nine routes plus `/settings`, against a freshly reseeded fixture. `typeRange` now clears the 3.4 bar on all ten routes -- Fleet's own miss (3.11) is resolved to 5.11 now that `FleetFacts` renders the shared 46px display step. `sideBySideRegions` clears the >=1 bar on all nine `GRAPH_LEVELS` routes; `/settings` measures 0, flagged as an open question rather than a failure since `routes.ts` declares Settings not a level. The workflow route's two-pane recomposition (W274) was confirmed live, not just from the ledger. Four gaps the baseline named are unchanged (Codebase and Binding surface still lack their tile row, Vendor's right panel is still flat, Signals' tri-column card row is still unadopted); Detectors' colour-coded rung bars are unchanged but Task 9's refusal is now recorded as resolving the baseline's suspicion rather than confirming it. Separately, walked all ten screens against Gate 3's question -- does anything assert a number nothing computed -- tracing every visible number to a named payload field or a documented derivation over an already-fetched value; all ten screens PASS, with one figure (Codebase's `CONTEXT SAVINGS`) noted as verified by pattern-consistency rather than a direct query and named for a future audit to close directly. BACKLOG.md's M14 row was out of this task's given deliverables and was not touched | landed | `docs/superpowers/reports/2026-08-17-console-mock-gaps.md`, `docs/superpowers/reports/2026-08-17-gate-3-screen-pass.md`, `docs/superpowers/WORKLOG.md` |







| M14-W276 | B145 filed from the Gate 3 pass, and the pass's one pattern-matched claim replaced with direct evidence: `context_savings` is computed (`graph_views.py:467`, `:585`) so it clears Gate 3's question, but it is a row count times a fixed per-read constant with no tokens ever counted, and the console states that only on the bounded-scan branch | landed | `docs/superpowers/BACKLOG.md`, `docs/superpowers/reports/2026-08-17-gate-3-screen-pass.md` |







| M0-W249 | Beta Gate 3 recorded as signed in the scope that defines it, with its evidence cited rather than its conclusion repeated. First of the four to close, and closed on a live reading of the running API against what each screen renders rather than on a review of the code | landed | `docs/superpowers/plans/2026-08-17-sync-to-beta-scope.md` |







| M5-W303 | B136 intake attempt record producer half: IntakeAttempt data model, closed vocabulary of 17 reason codes, IntakeAttemptSink port protocol, and execute_intake_attempt execution harness | landed | `src/sync/signals/intake_attempt.py`, `tests/test_intake_attempt.py`, `docs/superpowers/WORKLOG.md` |







| M10-W240 | B151 closes: `main` goes from 60 failed to 0. `StateGraph(RunState)` builds one channel per key the TypedDict declares, and a node returning an undeclared key is not an error -- it is a write nothing reads. `12e416a` removed `report_reason` and rewrote attempt accounting while `nodes.py` kept reading and writing `static_attempts`, `ci_attempts` and `report_reason`, so every increment vanished, the routing predicates always read the zero default, the retry budget never tripped (`GraphRecursionError`), and the graph never reached a stop condition. Fix restores all three where their own surviving comments already said they belonged. Also pins `test_remediation_graph.py`'s topology (`park`/`external_cause`, added by the same commit and never pinned) and baselines two finished-but-uncalled dead links (`ensure_image_built`, `dispatch_webhook_event`) with the reason rather than force-wiring a caller. Diagnosed and fixed by Lane A; cherry-picked and landed by the coordinator because the lane would not push without direct human confirmation it could authenticate, and five lanes were gating against the red meanwhile. Its commit subject still reads `M0-W241`, which collided with a coordinator row; this is the corrected number. **Two rows carried this item until `M0-W346` merged them** | landed | `src/sync/remediate/state.py`, `src/sync/remediate/nodes.py`, `tests/test_remediation_graph.py`, `scripts/dead_links_baseline.txt` |







| CI-W286 | B153: a job that failed downloading `setup-uv` with a 429 reports as `failure` having run one step, which reads identically to a failed suite — B112's misreading with a different cause. Signature and the distinguishing `gh api` check recorded; not fixed, because retrying is already what the runner does | landed | `docs/superpowers/BACKLOG.md` |







| CI-W287 | B154: the gate wall-clock measured before and after Lane D's `2cf2e62`. 1215s/1741s/3270s and a dead worker in every run, against **233s TRUSTWORTHY** after. Cause was starvation on the host-wide npx resolve lock, diagnosed from a crash traceback and handed to Lane D; the charter's `-n 4` advice treated the symptom and is worth re-measuring | landed | `docs/superpowers/BACKLOG.md` |







| M5-W304 | RequestCorrelator inventory completion and honest adapter correlation boundaries: StripeAdapter and TwilioAdapter verified as RequestCorrelators, and uncorrelatable_reason declared on GeneratedSpecAdapter and McpServerAdapter | landed | `src/sync/signals/generated/adapter.py`, `src/sync/signals/mcp_server/adapter.py`, `tests/test_shipped_conformance.py`, `docs/superpowers/WORKLOG.md` |







| CI-W288 | Lane C item 4: the threat model reconciled against the code that exists. Two of its reviewer answers claimed containment that does not exist and are now marked false; a whole defence layer that shipped (`SETTING_SOURCES = []`) was missing from it; eleven citations had drifted. B97 re-scoped rather than closed — the mechanism is proven and nothing routes a patch attempt through it, which the repository's own dead-link baseline already recorded | landed | `docs/superpowers/specs/2026-07-25-sync-threat-model.md`, `docs/superpowers/BACKLOG.md` |







| M14-W277 | Fleet reads the change-unit grain the payload computes: `change-units-table.tsx` synthesised its rows from `useOverview` and `useRuns`, deriving the same grouping `GET /api/change-units` (M12-W320, `sync.dashboard.fleet.change_units`) already computes -- two components answering one question the payload can answer once. Added `fetchChangeUnits`/`useChangeUnits` and the `ChangeUnitRow`/`ChangeUnitsPage` types, and rewrote the table to read the real endpoint, deleting the `deriveStanding`-over-`RunRow` synthesis and the `"acme/payments-api"`/`"Stripe"` fallbacks. `codebase-page.tsx` now passes `repoId` through so its table narrows the grouping itself rather than rendering the fleet's rows under one repository's name. `describeChangeUnitStanding` renders the payload's `standing` (`RunDisposition | "in_progress" | null`) through the console's one absence marker on `null` -- genuine absence, since the checkpointer read only runs when `SYNC_CHECKPOINTER_DSN` is configured -- and `describeChangeUnitRung` gives `_weaker_rung_summary`'s `"mixed"` its own honest sentence rather than falling into `describeRung`'s "not recognised" branch. The table is now Fleet's data centrepiece, placed above the repository cards; all three protected paragraphs at the foot of the screen are unchanged. Measured at 1440x900 against the seeded fixture: prose/(cells+figures) ratio 125.2 -> 25.0, data cells 4 -> 49, figures 7 -> 18 | landed | `web/src/api/client.ts`, `web/src/api/queries.ts`, `web/src/api/types.ts`, `web/src/features/fleet/change-units-table.tsx`, `web/src/features/fleet/change-units-table.test.ts`, `web/src/features/fleet/fleet-page.tsx`, `web/src/features/repositories/codebase-page.tsx`, `docs/superpowers/WORKLOG.md` |







| M0-W250 | The blanket permission to exclude `test_lint_dead_links` is rescinded, because it was the reason the rule against landing a producer with no consumer kept being broken. Granted when the red had three causes no working lane could fix, it outlived that: all three are closed, and every violation standing now was introduced this afternoon by the lane that still owns it. Telling five lanes to skip the one test that would have caught them made the arbitration unenforceable -- a rule nobody's gate checks is written twice and followed never. Lanes now run it, close what they introduced, and may still exclude a violation that is somebody else's provided they say whose | landed | `docs/superpowers/orchestration/2026-08-17-lane-charters.md` |







| M5-W305 | B136 scan path wiring: execute_intake_attempt wired into cli.py scan path with optional store sink passing, closing dead link and enabling intake attempt recording | landed | `src/sync/cli.py`, `docs/superpowers/WORKLOG.md` |







| M5-W306 | B7 acceptance verification for SIGNAL and INDEX stages: end-to-end verification of Stripe and Twilio change extraction, TypeScript and Python call site indexing, symbol resolution, and GraphStore finding creation | landed | `docs/superpowers/WORKLOG.md` |







| M14-W278 | The grid layout, closed on a measurement rather than the August complaint's scope. Re-ran Task 3/15's own snippet over all ten routes before touching anything: nine of ten already clear `sideBySideRegions >= 1` (Fleet 10->11 and Codebase 12->9 are both data-volume/scoping noise from W277, traced to `ChangeUnitRow`'s `StandingCell` row count -- not layout regressions, and neither was touched); `/settings` alone still measured 0, the same as Task 15's first reading of it. Ruled (per `.claude/rules/autonomous-development.md`, `/settings` being outside `GRAPH_LEVELS` bears on which hierarchy test governs it, not on whether it owes a region beside a region) to fix only that route: `settings-page.tsx` now wires `PageHeader`/`Merge policy`/`Adapters` onto `DetailGrid` (header spans both columns, `Merge policy` is the rail, `Adapters` keeps the wide column for its table) instead of three stacked `flex-col` divs -- no new grid literal, no sentence reworded, both refusal paragraphs and the Adapters intro guarded verbatim by a new test. `sideBySideRegions` on `/settings`: 0 -> 1. The other nine routes were left alone and reported with their number, per the brief's own warning against restyling a screen that already clears the bar | landed | `web/src/features/settings/settings-page.tsx`, `web/src/features/settings/settings-page.test.tsx`, `docs/superpowers/reports/2026-08-17-console-mock-gaps.md`, `docs/superpowers/WORKLOG.md` |







| M14-W279 | The drift guard's `/api/change-units` exemption deleted, because W277 retired it. `_NOT_YET_FETCHED_BY_CONSOLE` in `tests/test_api_routes.py` carries its own instruction -- remove the entry the day the panel lands and `client.ts` fetches the path -- and W277 was that day, so the guard was failing on `main` until this. One line, in Lane E's file, taken rather than escalated because the red was mine and the test named the fix; declared to the coordinator rather than done quietly | landed | `tests/test_api_routes.py` |







| M0-W251 | A lane may fix a red it caused in another lane's file, ratified rather than granted as a one-off: the failure message must name the exact fix, the edit must be unambiguous, and the lane must declare it and offer the reversal. Lane B's Fleet panel expired an entry in a set that documents its own expiry, turning a drift guard red on `main` at the moment it landed; escalating would have left `main` broken on its account while it waited, and a charter producing that outcome is wrong at that point. The red must be yours and the fix must be the one the failure states -- anything needing judgement about another lane's design is still an escalation | landed | `docs/superpowers/orchestration/2026-08-17-lane-charters.md` |







| CI-W289 | `scripts/beta_gates.py`: the four beta gates measured against the repository instead of asserted in chat, with `CANNOT TELL` as a first-class verdict. First run: Gate 1 NOT MET (4 real attempts, 0 green pull requests), Gate 2 CANNOT TELL (0 of 5 axes have samples), Gate 3 CANNOT TELL (the console changed after the sign-off was written), Gate 4 NOT MET (unbaselined dead links, and the sandbox still unwired) | landed | `scripts/beta_gates.py`, `tests/test_gate_beta_measurement.py` |







| M0-W252 | The lane boundary gets its own section after one lane crossed it three times in a day -- a duplicated aggregate, superseded panel wiring, and an edit to a file the owning lane was editing in the same minute. None was caught by the lane doing it or by review; each surfaced only because a coordinator read a terminal, and each cost three parties. Duplicated work is the most expensive failure here because from inside it looks like progress. Check the file against your path list before editing it, and note that a lane repeatedly outside its boundary is usually avoiding the harder item further down its own queue | landed | `docs/superpowers/orchestration/2026-08-17-lane-charters.md` |







| M0-W253 | The beta scope records what the gate meter measures rather than what the coordinator asserted, and the meter contradicted it immediately: 0 of 4 met, 2 cannot be told. Gate 3 was recorded here as signed and was stale within forty-four minutes -- the pass was signed at 11:10 and the console changed at 11:54. Gate 4's finding is sharper still: there are no unbaselined dead links because the sandbox primitives are baselined, so `B97` sits built and unwired and no patch run is contained while the gate reads green. The baseline mechanism this document sanctions is what concealed it | landed | `docs/superpowers/plans/2026-08-17-sync-to-beta-scope.md` |







| M14-W340 | The console becomes production-servable and is proven so locally, prepared rather than deployed per beta Ruling 1. `web/scripts/serve-console.mjs` serves the real `npm run build` output as static assets and proxies `/api` from the same origin, because the client fetches relative paths and `sync.api` declares no CORS -- split origins do not work and that is stated rather than discovered at deploy time. One shared credential in HTTP Basic gates every request including `/api`, fails closed on a missing, blank or under-length secret, and refuses a non-loopback bind without an explicit acknowledgement because base64 is not encryption. `scripts/shared-credential.ts` carries what one shared credential is NOT -- no identity, no revocation, no audit trail -- and its tests assert the two properties that would be invisible in a working console: an empty configured secret rejects everything rather than accepting everything, and a prefix of the secret is refused. Server-only code lives outside `src/` so the browser build never type-checks or bundles `node:crypto`; `vitest.config.ts` widened to keep its tests in the same gate | landed | `web/scripts/serve-console.mjs`, `web/scripts/shared-credential.ts`, `web/scripts/shared-credential.test.ts`, `web/vitest.config.ts`, `docs/superpowers/reports/2026-08-17-console-deployment-note.md` |







| M5-W307 | B7 REMEDIATE graph node and routing verification: zero-remote rehearsal and state machine execution across locate, prepare, patch, static_verify, replay, push_branch, await_ci, open_pr, park, report, external_cause, and abandon | landed | `docs/superpowers/WORKLOG.md` |







| M0-W254 | `B7`'s risk profile recorded as materially changed, because the reason it was frightening has been answered without spending anything. Its danger was that four of the pipeline's nodes postdated the last acceptance run, so authorising it risked discovering a months-old break while burning a real pull request and `xhigh` model time. `M5-W306` proved INDEX and SIGNAL clean; `M5-W307` drove all twelve remediation nodes and three compiled routing paths over the zero-remote fixture against a real corpus repository. The nodes work. `B7` still has not passed and only `B7` can pass it, but the decision is now an informed one rather than an experiment | landed | `docs/superpowers/plans/2026-08-17-sync-to-beta-scope.md` |







| CI-W290 | The beta meter runs without anyone remembering to run it: a `beta-gates` job on every push to `main` publishes the four verdicts to the run summary. It cannot fail the build — `--exit-zero`, not `continue-on-error`, so a NOT MET gate is a report and a crashed script is still a failure — and CANNOT TELL renders with its own mark and its own sentence | landed | `.github/workflows/ci.yml`, `scripts/beta_gates.py`, `tests/test_ci_gates_what_it_runs.py`, `tests/test_gate_beta_measurement.py` |







| M5-W308 | Gate 2 quality axes computation & rehearsal row isolation verification: verified sync.benchmark.axes computation across 5 axes and confirmed migration_outcome rehearsal row exclusion (is_rehearsal=True) | landed | `docs/superpowers/WORKLOG.md` |







| M0-W255 | Gate 2's two hidden questions separated and the dangerous one answered well: rehearsal rows cannot reach its metrics, because `is_rehearsal` is recorded and `GraphStore.migration_outcomes` filters `WHERE NOT is_rehearsal` -- confirmed in the source rather than taken from a report. Had they been indistinguishable, every axis would have been quotable as evidence it had not earned. All five axes compute correctly over a wide population. So Gate 2 is no longer *we do not know whether this works* but *this works and has no data yet*, and it correctly still reads CANNOT TELL, because a proven calculation over zero rows is still zero rows | landed | `docs/superpowers/plans/2026-08-17-sync-to-beta-scope.md` |







| M14-W341 | Gate 3 re-signed after W277/W278/W279/W340, a re-walk of what moved rather than ten screens again. The substantive question was W340's production runtime: static assets behind Basic with `/api` proxied is not the dev-proxy path the first pass was signed against, and absence-versus-zero survives a rebuild without automatically surviving a different fetch path. Measured rather than reasoned -- six endpoints fetched direct from the API and through the proxy and compared byte for byte, all identical, and the comparison is meaningful because `/api/change-units` carries 23 nulls including `standing`; 404 passes through as 404, so not-found is not collapsed into absence. Walked in Chrome on the built assets: the new STANDING column names the two kinds of nothing it cannot separate, the workflow captions and Settings' merge-policy refusal render intact, and the ticking evidence-age correctly does not render on a run whose outcome is `reported`, verified against the payload rather than assumed. Also answers the coordinator's question on the staleness meter: it is too crude, it watches all of `web/` so it will fire on test, token and tooling commits that cannot change a claim, and the one-line refinement is to narrow the watched set to `features/`, `components/` and `api/` excluding tests -- routed to Lane C rather than taken, since `scripts/` is its file | landed | `docs/superpowers/reports/2026-08-17-gate-3-resign.md` |







| M14-W342 | Two corrections to W341's own report, one of them mine. First: it said the staleness check watches all of `web/` and it watches `web/src` (`scripts/beta_gates.py:453`) -- I overstated, and a wrong fact in a report I signed is mine to fix rather than leave standing; the argument survives, since `web/src` still holds every `*.test.*`, `src/lib` and `src/vendor`, none of which can change what a screen claims. Second, measured after W341 landed: the meter still reports Gate 3 `CANNOT TELL` citing the 11:10 report, because `beta_gates.py:452` hardcodes the path of the FIRST report, so a re-sign written to a new file is invisible to it. That is a different defect from granularity and a worse one -- granularity makes the check noisy, a hardcoded path makes it unclearable, since a lane that does exactly what the check asks still gets `CANNOT TELL`. Recommended fix is one canonical Gate 3 report that accretes dated sections rather than a new file per re-sign; Lane C's call on Lane C's file, untouched here | landed | `docs/superpowers/reports/2026-08-17-gate-3-resign.md` |







| M14-W343 | The Gate 3 re-sign recorded in the file the meter actually reads. `beta_gates.py` dates a signature by the last commit touching `2026-08-17-gate-3-screen-pass.md`, so W341's re-sign written to a neighbouring file left the meter reading 11:10 and reporting `CANNOT TELL`. The note added here points at the re-sign evidence and states the mechanism, so the next lane is told to write into this file rather than beside it. Checked before writing rather than after: `web/src` has not changed since `6b68397` at 11:54:54, which is the tree W341 walked, so this signature covers the console as it stands rather than claiming coverage of later work | landed | `docs/superpowers/reports/2026-08-17-gate-3-screen-pass.md` |







| M14-W344 | Console beta stock-take, requested rather than volunteered: what is left for a design-partner beta that the scope document does not name. Five items, and only one I would refuse to ship without -- nobody has ever seen this console against an EMPTY graph. Every walk it has had ran on the seeded fixture (the Gate 3 report names `seed-console-*` twenty-eight times), and a partner's first five minutes are the opposite state: configured, nothing indexed, every table empty. On a console whose whole argument is that absence is not zero, a screen that says `0 findings` where the truth is `never indexed` fails on the exact axis the product is sold on -- and it has never been looked at. Also: a failed panel has no retry (`ErrorState` explains and offers nothing; the only affordance in the error surface is Dismiss), no screen states which deployment it is bound to, route changes do not move focus, and the abandoned-run workflow screen has unit coverage but has never been rendered. Two things argued AGAINST doing before beta: no restyling, since every measured bar is clear and no measurement asks for it, and not the second drawer, which has one consumer | landed | `docs/superpowers/reports/2026-08-17-console-beta-stock-take.md` |







| M14-W345 | Gate 3 signed under Lane C's new mechanism, which landed mid-iteration and replaced commit-time inference with an explicit `Signed:` line. The re-sign report carries it dated `2026-08-17T12:20:41-04:00`, the commit time of W341 -- the moment the verification was recorded rather than the moment the line was typed, because a signature should date the work and not the paperwork. The original screen-pass deliberately carries no such line: it is the superseded first signature, and the meter listing it as "not read" describes it correctly. Gate 3 now reads MET against the narrowed watch set Lane C adopted from W341's recommendation | landed | `docs/superpowers/reports/2026-08-17-gate-3-resign.md` |







| M14-W347 | Gate 3's signature extended to the empty graph, the state a design partner sees first and the one nobody had ever walked. Stood up as a SEPARATE schema-applied zero-row database rather than by truncating the shared one, since five lanes use it; 9 tables, 0 rows, verified before walking, dropped after. One real defect found and fixed under W346, and two screens confirmed already right with their words quoted as evidence: `/detectors` says "The API answered... That is an answer, not a failure", and Settings renders "Nothing received" rather than 0. Also disproves the hypothesis that a failed fetch and an empty graph are one defect wearing two hats -- with the API killed, Fleet renders "the API did not answer" in the figure slot with zero bare zeros, so the console already distinguishes them and the stock-take's item shrinks to affordance rather than honesty | landed | `docs/superpowers/reports/2026-08-17-gate-3-empty-state.md` |







| M14-W348 | The abandoned-run workflow screen rendered for the first time, and it is right -- no defect found and none manufactured. The outcome sits INSIDE the sequence immediately after `static_verify`, the last node the run reached, above the four that say "never ran" rather than "not yet"; the abandon reason renders in the closing bracket and again in the activity timeline, and `static_verify`'s evidence carries the real compiler diagnostic, so a reviewer sees why Sync gave up rather than being told that it did. Why nobody had rendered it IS the finding: `/api/workflows/{finding_id}` serves the NEWEST generation, and the seeded fixture pairs an abandoned generation 0 with an opened generation 1, so no URL produces the abandoned screen. Stood up by copying the seed into a throwaway database and deleting the opened generation's checkpoint, dropped after | landed | `docs/superpowers/reports/2026-08-17-abandoned-run-walk.md`, `docs/superpowers/BACKLOG.md` |







| M14-W349 | A failed panel can be retried rather than only explained. `ErrorState` gains an optional `onRetry`; absent, it renders no control, because a dead button that appears to retry is worse than none. Wired to each query's own `refetch` at twenty call sites, and proven end to end rather than in the suite alone: API killed, Try again appeared in a real failure, API restarted, clicked, the panel recovered with no page reload. The empty-state walk had already established the console SAYS which state it is in, so this was correctly scoped as affordance rather than honesty -- without it the only recourse was a full reload, which re-fetches every other panel and discards scroll position and filters | landed | `web/src/components/states.tsx`, `web/src/components/states.test.tsx`, and twenty feature files |







| M14-W350 | Gate 3 re-signed to cover W349, appended to the existing signature file rather than written to a fourth -- the one-accreting-report shape this lane recommended and Lane C's meter now supports. Signed rather than re-walked, with the reason checkable rather than asserted: the commit's diff over `web/src/features` contains only the `ErrorState` invocation gaining `onRetry`, proven by filtering for lines without that token and getting nothing, so the change adds a control and asserts no figure. The rendered result was observed on the built console in the same session | landed | `docs/superpowers/reports/2026-08-17-gate-3-empty-state.md` |







| M14-W351 | The console says whose data this is, on every screen. A partner reaching a hosted console sees repository names and had nothing telling them whether an unfamiliar one is their own deployment holding a repo they did not expect or somebody else's data -- a trust question rather than a cosmetic one on a single-tenant product, and one that stopped being hypothetical the moment the console could be served behind a shared credential. The sidebar footer now states what the console can HONESTLY know: every screen reads one deployment's graph and nothing is filtered per viewer, so an unrecognised repository is one this deployment was configured to watch. It deliberately does NOT name a deployment -- no route serves an identifier for one, and a label invented here would be the console asserting something nothing computed, in the furniture rather than in a figure. Proven to bite by deleting the filtering clause and watching the assertion fail | landed | `web/src/layouts/app-frame.tsx`, `web/src/layouts/app-frame.test.tsx` |







| M14-W352 | Focus follows the route, closing the last item of the console stock-take. `react-router` moves no focus, so a keyboard or screen-reader user who activated a destination stayed where they were -- and since this console's navigation hierarchy IS the API Dependency Graph, focus left behind makes the hierarchy itself unavailable, which `references/notes/roadmap-frontend-skills.md` argued and nothing had acted on. The content region takes focus rather than the page heading, because a heading belongs to the routed screen and one still loading has rendered none, which would leave focus nowhere on exactly the slowest navigations; `tabIndex={-1}` makes it a programmatic target without adding a tab stop. First paint is deliberately not a navigation. Tested through a real in-app navigation (the Observe rail link) rather than a contrived route swap, and proven to bite by deleting the focus call | landed | `web/src/layouts/app-frame.tsx`, `web/src/layouts/app-frame.test.tsx` |







| M14-W353 | Gate 3 re-signed for W351 and W352, and the re-signature is voluntary -- which is the finding. `CONSOLE_CLAIM_PATHS` watches `features`, `components` and `api` but NOT `web/src/layouts`, so W351's deployment sentence, which renders on every screen from the shell, did not move the meter and the gate read MET across a change it could not see. Same class of miss as the hardcoded report path, arriving through the other side of the same check, and it is mine: I proposed those three paths and did not think about the shell. Recommended to Lane C: add `web/src/layouts`, because a claim placed in the shell is the most widely seen claim in the product | landed | `docs/superpowers/reports/2026-08-17-gate-3-empty-state.md` |







| M14-W354 | The visual eval exists and has run: `web/scripts/visual-eval.mjs` measures the drawn mock and the built console with one probe and prints per-property deltas, and `capture-console.mjs` closes the stale-capture cause with nine routes at 1440x900 in a dated directory, subjects read off the API so a reseed cannot fill it with not-found screens. Zero dependencies -- both speak CDP over the WebSocket Node 22+ ships as a global -- and the trial verdict is measured rather than argued: the in-house script reached a real measurement in about ninety seconds against a target all four candidate extractors are built to crawl as a public site. FINDINGS: Fleet draws 4 side-by-side regions against the mock's 17 and carries 915 prose characters against 340, which is the owner's original complaint measured. Colour and radius match the mock EXACTLY, so what remains is composition rather than palette. THE HIERARCHY RULING IS WRONG FROM EVIDENCE: the plan says v2 supersedes v1, and v2 measures as a light theme with NO border-radius and a 1.45 type range -- three independent contradictions against a recorded dark-only ruling, DESIGN.md's two radius tokens, and the 3.4 bar -- while drawing 6 side-by-side regions to v1's 17. v1 is the appearance target; v2 supersedes only on vocabulary | landed | `web/scripts/visual-eval.mjs`, `web/scripts/capture-console.mjs`, `docs/superpowers/reports/2026-08-17-visual-eval-first-run.md`, `docs/superpowers/reports/screens/2026-08-17/` |







| M14-W355 | The eval walks all seven screens, and doing it found two measurement defects that REVERSE the first run's headline. First, the console under test was half broken: Chrome does not attach URL-embedded credentials to a page's own fetches, so three panels rendered their never-reached-a-server state and the eval counted error prose as console prose and failed panels as missing composition -- observe's side-by-side read 1 when it is 6, remediation's read 4 when it is 18. Fixed by sending Authorization through `Network.setExtraHTTPHeaders`. Second, `sideBySide` compares MARKUP TECHNIQUE rather than composition: the mock holds zero `<table>` elements and 33 `grid-template-columns`, so its every data row counts as a side-by-side placement while our semantic `<tr>` counts as nothing. Added `regionsBeside`, which counts panels beside panels with table rows excluded -- and on it the mock places 0-2 regions while the console places 0-4. FLEET NEEDED NO WORK AND NONE WAS DONE: `regionsBeside` 2 against the mock's 0, and of its 915 prose characters 580 are protected honesty sentences, leaving 335 discretionary against the mock's 340. Real remaining gaps, by measurement: codebase behind by 2 pairings, signals by 1 with the largest prose gap, observe by 1 | landed | `web/scripts/visual-eval.mjs`, `docs/superpowers/reports/2026-08-17-visual-eval-first-run.md` |







| M14-W356 | Plan written for the owner's instruction that the dev console show OUR OWN codebase and that our repairs be recorded through the systems we built, plus the codebase-and-testing taxonomy asked for alongside it. Grounded rather than aspirational: `runner/claude_sdk.py` calls `ClaudeAgentOptions`, a vendor surface `CLAUDE.md` records as having already broken this project twice, which is the honest dogfooding target. It states plainly what Sync CANNOT watch -- the API entrypoint `NameError` is a Python scoping bug, not vendor drift, and claiming it as a Sync catch would invent a capability. The recording half needs one link rather than a system: hand-made repairs get a `migration_outcome` row with a human-authored marker, since a corpus that cannot tell agent from human cannot answer what Sync does unattended; explicitly no second ledger. The taxonomy names four tiers -- systems codebase, per-vendor probes, the scored corpus, the synthetic fixture -- because tier 1 and tier 2 failures mean different things and today both read as "the corpus is red" | landed | `docs/superpowers/plans/2026-08-17-sync-watches-sync.md` |







| M14-W357 | The eval instrument was NOT REPRODUCIBLE and every number it produced before this is superseded, including my own "Fleet is at parity" conclusion. Two identical runs disagreed -- api-services read 4 regions then 0 -- because panels fetch independently of the document and the probe waited only for `main` to have text, so it measured whichever panels happened to have rendered. A still-loading panel has no heading and counted as no region; a failed panel wrote error prose that counted as console prose. Both return a plausible number rather than an error, which is the third defect in this work to survive on plausibility. Readiness now requires no panel loading and the probe REFUSES rather than reporting if any panel shows a fetch failure; two consecutive runs are byte-identical. Stable numbers strengthen the composition conclusion rather than weakening it -- the console is AHEAD of the drawing on fleet (12 regions against 0) and api-services (4 against 1), level on remediation and settings, behind by one on codebase, signals and observe -- and withdraw the prose parity claims, which need re-auditing per screen. Also added `prose-audit.mjs`, which classifies a screen's paragraphs as protected or discretionary and refuses on a failed panel | landed | `web/scripts/visual-eval.mjs`, `web/scripts/prose-audit.mjs`, `docs/superpowers/reports/2026-08-17-visual-eval-first-run.md` |







| M14-W358 | Fleet re-audited on the fixed instrument, and the first prose cut this work has justified. `prose-audit.mjs` carried the SAME unsettled-readiness defect the eval had and was fixed the same way first, so the audit does not repeat what it was written to catch. Settled Fleet is 1777 characters: 1327 protected (change-unit grain twice, staleness-not-liveness, absence-is-not-zero, three-attempts-one-finding, the fleet-versus-codebase scope sentence) and 450 discretionary against the mock's 340 -- over by 110, the first real gap to survive a correct measurement. Cut: `Git repository - Monitored by Sync` rendered on every card, 170 of those 450 characters, carrying no distinction and telling a reader nothing they do not know from being on Sync's own repository list. Verified by re-running rather than asserting -- 1777 to 1607, discretionary 450 to 280, now UNDER the mock's 340, with all four protected sentences confirmed still present in the same run | landed | `web/src/features/fleet/codebases-panel.tsx`, `web/src/features/fleet/codebases-panel.test.tsx`, `web/scripts/prose-audit.mjs` |







| M14-W359 | Screen-by-screen re-audit on the fixed instrument, which found a FOURTH defect of the same shape in the instrument itself: `prose-audit.mjs` refused on unreachable-style wordings and did not know a not-found panel, so it counted 302 characters of error prose as console prose on codebase. Fixed structurally rather than with another phrase -- every failed panel renders `ErrorState` and every one with a retry renders a `Try again` control, so the control is the marker, and both instruments now share it. Audited: `observe` is 3085 characters and roughly 80% protected -- rung-as-class-of-evidence, the refusal to compute a precision figure with no labelled corpus, scope-not-rendering, composition-not-quantity, and two never-measured statements -- with the discretionary remainder being the route question and figure labels, so NO CUT AVAILABLE. `codebase` cannot be audited at all, and why is worth more than the audit: both its telemetry routes 404 for a repository `/api/repositories` lists, filed as B147, which is absence-versus-zero violated one layer below the console | landed | `web/scripts/prose-audit.mjs`, `web/scripts/visual-eval.mjs`, `docs/superpowers/reports/2026-08-17-visual-eval-first-run.md`, `docs/superpowers/BACKLOG.md` |







| M14-W360 | Fetch audit across all seven screens, run ahead of the remaining prose audits because it changes how those are scored. Reports rather than fails, since over-fetching is a cost finding and a gate refusing on it would block correct work; no dependency added, because `Network.requestWillBeSent` over the same CDP-and-WebSocket transport the other two instruments use was already available. Findings: Fleet issues SIX `/api/overview` requests, one fleet-wide and one per repository, which is an N+1 that scales with the fleet -- and is not a bug, because the scoped call is what W265 added to stop every card showing the fleet-wide count; filed as B148 for Lane E, since the fix is a payload change. Fleet also fetches `/api/runs` twice with different limits, the coupling flagged as a Minor in W264's review and now measured. Every route pays two shell requests for the scope trail, which are read rather than wasted. No panel was found fetching a payload it does not read | landed | `web/scripts/fetch-audit.mjs`, `docs/superpowers/reports/2026-08-17-console-fetch-audit.md`, `docs/superpowers/BACKLOG.md` |







| M14-W361 | `docs/console-ui.md`: every console screen as it looks today, nine screenshots at 1440x900 from a production build behind the credential gate, rendering on GitHub from the repo. Written for the owner's request to see the UI from the git repo. `capture-console.mjs` was FIXED FIRST -- it still used URL-embedded credentials, which Chrome does not attach to a page's own fetches, so it would have photographed a console whose every panel had failed; a screenshot is the one artifact where that mistake is invisible to whoever opens it later. It now sends the header and waits for panels to settle rather than for the document to have text. The document says plainly that the rows are the seeded fixture rather than customer data, points at the plan to change that, and names what is deliberately absent from the set -- the empty state, the abandoned run, and the mock comparison -- with the report that covers each | landed | `docs/console-ui.md`, `web/scripts/capture-console.mjs`, `docs/superpowers/reports/screens/2026-08-17/` |







| M14-W362 | The landing page becomes the Overview and answers one question: which repository to open. Renamed in everything a reader sees -- it was titled "Repositories", labelled "Codebases" in the registry and sits at the `Fleet` level, three names for one screen -- while `GRAPH_LEVELS` keeps the specification's word, so `test_console_hierarchy.py` is untouched. The repository list is rows rather than five cards, which lets a reader compare down a column; the scoped-answer discipline is unchanged, one `/api/overview` per repository with `openFindings` null rather than zero until that repository answers. Removed: the page-level "Review proposed patch", which pointed at whichever run happened to be newest with an opened pull request and read as THE patch when nine change units are open, and the fleet-wide change-unit table and vendor distribution, both of which belong on the Codebase screen where they are scoped to one repository. Every protected sentence survives and is asserted by test, including the absence footnote whose referent -- "the repository list below" -- is why that list stays on this screen | landed | `web/src/features/fleet/fleet-page.tsx`, `web/src/features/fleet/fleet-page.test.tsx`, `web/src/features/fleet/codebases-panel.tsx` |







| M14-W363 | Three referents W362 falsified, and the two guards that let it through. The health-refusal sentence ends "the panel beside them names what none of these figures can tell you at all"; W362 collapsed a three-column band to `xl:grid-cols-2` holding ONE child, so both panels stacked and the clause described a layout that did not exist. `ScreenLimitsCard` likewise still said "the runs table above" and "the vendor panel above" after W362 removed the vendor panel from the screen. The prose was never touched by that commit, which is exactly why nobody noticed: `.claude/rules/console-surface.md` protects the sentence, and W362 falsified it from the outside by moving what it pointed at. Layout repaired to a genuine two-column band -- which also adds a side-by-side region on a screen the flatness report measures as one vertical stack -- and the two locational claims reworded to be true wherever the panel renders, neither shortened, neither keyed in the guard. Both guards that should have caught it could not fail: `fleet-page.test.tsx` asserted the sentence's TEXT survived and never its referent, and `test_console_honesty_sentences.py` searched every file under `web/src`, excluding `.test.ts` but NOT `.test.tsx` (25 such files), and counting modules no route mounts -- so a sentence surviving only in a test, or only in one of the five orphaned cards, passed a test named `..._is_still_on_screen`. It now walks the import graph from `main.tsx`: 113 modules of 177, zero test files, orphans excluded. Both new guards were shown red before being trusted | landed | `web/src/features/fleet/fleet-page.tsx`, `web/src/features/fleet/fleet-page.test.tsx`, `web/src/features/fleet/screen-limits.tsx`, `tests/test_console_honesty_sentences.py` |







| M14-W364 | Gate 3 re-signed at `4a5ef47` after freezing `web/src`, which is the actual fix for a gate that had been `CANNOT TELL` all afternoon. The signature has to be newer than the newest console change, and three landings at 14:36, 15:32 and 16:40 each reset that -- so the answer was never to re-sign faster but to stop changing the console first. Nine screens walked in Chrome at 1440x900 on the production build behind the credential gate, `dist/` rebuilt first because the bundle predated a 31-commit merge and walking a stale bundle would sign a console that is not on disk. PASS with two findings. B145 unchanged: `CONTEXT SAVINGS` is `total_findings * a constant` (`types.ts:110`) rendered flat on three screens -- not a blocker, on the 11:10 walk's own precedent, which traced it, filed it and passed. NEW: Codebase and Signals each show two failed panels claiming "The API does not hold that identifier" for a repository `/api/repositories` lists and whose own route renders -- `app.py:422-423` declare `/coverage` and `/observed` with `{repo_id}`, the default converter, which cannot match a `host/owner/name` id, while `:426-429` already use `{repo_id:path}`. A clean reproduction of B147 with the survey's corrected cause confirmed rather than inferred; the copy overclaim beside it is a console defect of mine, left unnumbered rather than inventing an id. Verified positively: the band W363 repaired renders side by side, tile x=305 and limits x=845, measured through CDP. The `Signed:` line was written bold first and silently not read -- `beta_gates.py:242` anchors on `^Signed:` | landed | `docs/superpowers/reports/2026-08-17-gate-3-w363-walk.md` |







| M14-W366 | Task 5 of the IA plan: one full-height sidebar, the top bar inside the content column. Measured at 1440x900 in Chrome -- sidebar `{x:0, y:0, 208x900}`, header `{x:208, y:0, 1217x48}`, nine destination rows from one screen, no horizontal overflow -- against mock v1's `nav {x:0, y:0, 246x900}` with its header at `x:246`, which is the same structure 38px wider. The rail is deleted and the two tiers are one list, which is a RETURN rather than a new idea: `M7-W160` built exactly this after the owner ruled against an icon rail beside a contextual panel, `M7-W171` re-introduced two tiers, and the owner ruled against it again. The load-bearing consequence the task text did not state: deleting the rail makes five of six areas unreachable unless the list holds them all, and `DESTINATIONS` is a separate registry from `ROUTES` sitting at no graph level, so Settings would have been dropped from navigation entirely while every routing test stayed green. Both are now asserted directly. Eleven rail tests retired -- hover labels, a collapse threshold, a pick surviving Back -- and what they guaranteed that still matters was rehomed into five stronger ones per `M14-W273`'s precedent, not deleted with them; the suite goes 358 to 352 for that reason. `ErrorSurface` moved inside the content column, recorded as a decision rather than a side effect: above the chassis it displaced the navigation too, and navigation should survive a panel's failure | landed | `web/src/layouts/app-frame.tsx`, `web/src/layouts/app-frame.test.tsx` |







| M14-W368 | Task 8: the sidebar expands and minimises without moving a row. Measured in Chrome at 1440x900 in BOTH states -- 240px expanded, 48px minimised, 900px tall in each, nine destination rows in each, `rowsThatMoved: []`. Not one row's vertical offset changed, which is the whole constraint: minimising changes density, not navigation. The vendored `collapsible="icon"` path is deliberately NOT adopted -- it carries `transition-[width]` and is exempt from `test_nothing_transitions_geometry_anywhere` BY PATH, so it would animate for a default reader while CI stayed green; `collapsible="none"` is kept and the two widths are owned in `layouts/`, argued in `DESIGN.md` first as `M14-W367`. What keeps the rows still is a reserved heading row: at the narrow width a group heading's TEXT goes `sr-only` and the row keeps its height, rather than the row being removed and dragging every icon beneath it upward. Three things the jsdom guard structurally cannot see, all found by measuring: level labels and destination labels would still have rendered text at 48px and wrapped, and the footer carries a PROTECTED sentence -- `sr-only` there is recorded as a decision, since the rule forbids collapsing one behind a disclosure, and the argument is that the default is expanded, the sentence stays in the accessibility tree, and prose wrapping to a dozen lines in a 48px column is how a qualification actually gets lost. Near-miss worth keeping: `transitionProperty` computes as `all` on that element and reads like an animation; `transitionDuration` is `0s`, so there is none. The property alone is not evidence | landed | `web/src/layouts/sidebar-collapse.ts`, `web/src/layouts/sidebar-collapse.test.ts`, `web/src/layouts/app-frame.tsx`, `web/src/layouts/app-frame.test.tsx` |







| CI-W291 | Gate 4's suite component reads the verdict CI already produced instead of running the suite again: `--suite-result` off `needs.serial.result`, with `skipped` and `cancelled` treated as absence rather than success. The nightly is deliberately NOT given `--run-suite` — its `coverage` job already runs and gates the whole suite, so a second run would be four minutes for a duplicate answer that can disagree with the first | landed | `.github/workflows/ci.yml`, `scripts/beta_gates.py` |







| M0-W256 | The registers say what is true today rather than what was true a fortnight ago. `BACKLOG.md`'s milestone table is rewritten against `git log` and the gate meter: M5 from ~35% to ~80%, M12 from ~10% to ~55%, M8 and M9 to done, M10 to ~85%, and M8-M11 split into four rows because they no longer share a state. A dated status section carries the four measured gate verdicts, the order work should be done in and why, and who owns which paths right now. `WORKLOG.md` gains a preamble saying it is a register rather than a report, and how to read 72 interleaved rows by lane prefix instead of in file order | landed | `docs/superpowers/BACKLOG.md`, `docs/superpowers/WORKLOG.md` |







| M0-W257 | Gate 3 recorded MET -- the first of four, cleared by measurement. Its two failed attempts are recorded with it because they are the lesson: a signature stale in forty-four minutes, then a gate made unclearable by one compiled-in report path, both found by the lane being blocked rather than by the coordinator. The scope also gains the one console gap that would block a design-partner beta, from the lane best placed to name it: every walk has run against the seeded fixture, while a partner's first five minutes are configured-and-empty, and nobody has looked at that state on a console whose whole argument is that absence is not zero | landed | `docs/superpowers/plans/2026-08-17-sync-to-beta-scope.md` |







| M0-W258 | The coordinator was wrong about Gate 4 and the scope now says so. I pressed one lane for several cycles to *wire the sandbox*, reading the meter's `reached from nowhere` as somebody having forgotten a call; the lane declined, cited this repository's own re-scope of `B97`, and was right. Two of the four remaining items block hard -- an Anthropic-only forward proxy that is undesigned, and the unanswered question of which credential the CLI needs, which is the owner's to settle. A gate saying what is missing does not say why, and the lane owning the file had the answer throughout | landed | `docs/superpowers/plans/2026-08-17-sync-to-beta-scope.md` |







| M0-W259 | The threat model says what is true about its own injection surface, as the reviewed change Lane C asked for rather than the unreviewed second rewrite it refused to make. Two spans replaced with its proposed wording after I verified the claims in the source myself: the fenced -span list now names the repository context section as an unfenced exception and calls it a defect rather than a decision, and the untrusted-bytes table now opens on an unauthenticated HTTP POST rather than on a vendor. The document ranked injection first and had never considered this path -- a gap in the spec, not only in the code | landed | `docs/superpowers/specs/2026-07-25-sync-threat-model.md` |







| CI-W292 | The Gate 3 staleness meter stops ignoring a real re-sign. It read one hardcoded report, so Lane B re-signing by landing a second document beside the first was invisible to it; it now reads every gate-3 report and takes the latest recorded `Signed:` date rather than a git timestamp, and the watched set narrows from all of `web/` to features, components and api excluding tests | landed | `scripts/beta_gates.py`, `tests/test_gate_beta_measurement.py` |







| CI-W293 | Gate 4's other half: the threat model read against the tree, 74 substantive claims classified — 68 hold, 2 false, 3 stale, 1 the code has moved past. The serious one is B165: a customer's `.sync/context.md` reaches the patch prompt unfenced while the preamble tells the agent that unfenced lines are its instructions, and an unauthenticated POST writes it. Filed B165-B168 against Lanes A, E and D; the spec itself deliberately not edited | landed | `docs/superpowers/reports/2026-08-17-threat-model-against-the-tree.md`, `docs/superpowers/BACKLOG.md` |







| M5-W309 | B97 patch agent container authentication contract & credential discovery research (B156): established exact SDK and CLI authentication precedence (ANTHROPIC_AUTH_TOKEN -> ANTHROPIC_API_KEY -> on-disk OAuth -> apiKeyHelper -> 3P providers -> failure) and documented the three sandbox authentication architectures | landed | `docs/superpowers/BACKLOG.md`, `docs/superpowers/WORKLOG.md` |







| M0-W260 | Ruling 7: B97's forward proxy and its credential are one piece of work. `B156` established the CLI's discovery order empirically and proved `build_container_env` passes none of it, so an isolated container fails before a patch begins and a proxy alone is insufficient -- which was assumed rather than known. Of the three container options, injecting a credential or mounting one hands a live secret to the agent the sandbox exists to distrust; a credential-injecting proxy keeps it outside. So the component that restricts egress is the component that supplies auth, and building them separately is the failure the ruling prevents. Which credential Sync authenticates with stays the owner's | landed | `docs/superpowers/plans/2026-08-17-sync-to-beta-scope.md` |







| M0-W261 | The empty-state gap is recorded as closed with what the walk actually found: one real defect, three zeros that were already honest and left alone, two screens quoted rather than reported as an absence of complaints, and one coordinator hypothesis disproved -- the failed fetch and the empty graph are not one defect, since Fleet renders *the API did not answer* in the figure slot with no bare zeros. The walk used a separate zero-row database rather than truncating the one five lanes were using | landed | `docs/superpowers/plans/2026-08-17-sync-to-beta-scope.md` |







| M0-W262 | Two Lane C scope items marked closed with their evidence, the edit being the coordinator's rather than the lane's since the scope is the coordinator's document. Both were already fixed and the plan had gone stale against them. One correction rides along: the sandbox test was never a contention flake as I had framed it -- `host.docker.internal` does not resolve on Linux, which `CI-W280` fixed, and it now passes 8 of 8 under `-n 4` in under thirty seconds | landed | `docs/superpowers/plans/2026-08-17-sync-to-beta-scope.md` |







| CI-W294 | The beta-gates job checked against real pushes rather than simulation: it runs, reads `needs.serial.result` (observed as `--suite-result "failure"`), leaves the build green on NOT MET, and Gate 3 came back MET once Lane B's `Signed:` line landed. The publication was the one part that could not be verified — GitHub's check-run API does not expose job summaries — so the job now reads its own summary back and fails if it is empty or missing a gate | landed | `.github/workflows/ci.yml`, `tests/test_ci_gates_what_it_runs.py` |







| CI-W295 | `gate_verdict` called every CI run untrustworthy. pytest prints its tally bare on a narrow terminal and wrapped in `=` on a runner, and every fixture was written from a local run — so the check reported "no summary line" against output carrying one, failed the `test` job on every push, and took the eight steps after it down with it | landed | `scripts/gate_verdict.py`, `tests/test_gate_verdict.py` |







| M5-W310 | B168 closed: `intake_attempt.detail` write-time sanitization (path scrubbing and 500-char bounding) and `IntakeAttempt` closed vocabulary validation; Lane D beta stock-take report | landed | `src/sync/signals/intake_attempt.py`, `tests/test_intake_attempt.py`, `docs/superpowers/reports/2026-08-17-signals-index-beta-stock-take.md`, `docs/superpowers/BACKLOG.md`, `docs/superpowers/WORKLOG.md` |







| CI-W296 | Lane C stock-take: what in CI, the gates, the sandbox tests and the developer loop is trusted without having been checked. Five findings ordered by what I would refuse to ship without, four things I argue against doing, and one place I expected a hole and found none. Filed B169 (cold clone unexercised), B170 (`-n auto` in CI against the charter's `-n 4`), B171 (two gates measured only by hand) | landed | `docs/superpowers/reports/2026-08-17-lane-c-stock-take.md`, `docs/superpowers/BACKLOG.md` |







| M0-W263 | The day-one coverage boundary recorded from Lane D's stock-take, plus the question it raises that crosses into the console. A partner wrapping the SDK in an internal module gets fewer static bindings, which is correct by design because the `observed` rung exists for it -- but that rung only produces bindings if telemetry is wired, so a partner with wrappers and no telemetry gets lower coverage from the same codebase, invisibly. Whether any screen separates *no call sites here* from *call sites behind an abstraction with no telemetry attached* is the absence-versus-zero rule applied to coverage | landed | `docs/superpowers/plans/2026-08-17-sync-to-beta-scope.md` |







| M0-W264 | A pattern named after two findings of the same shape: documented, asserted, never executed. The console's empty state was signed off across ten screens without anyone rendering the state a partner sees first, and `B169` finds twelve tests asserting the day-one setup is documented correctly while none runs anything from an empty checkout -- where a fresh worktree fails about fifty tests on gitignored artifacts alone. Both pass while proving nothing about the thing they are named after. `B169` is recorded as a beta blocker. Also confirmed by observation rather than by report: after `CI-W295`, the test job runs 22 of 22 steps again | landed | `docs/superpowers/plans/2026-08-17-sync-to-beta-scope.md` |







| M0-W265 | `B169` closed, and the answer refines the pattern rather than confirming it: the documentation was not wrong, it was correct and INCOMPLETE. `scripts/fetch_corpus_repositories.py` appeared in no document in the repository, so no assertion about the prose could have caught it and anyone following the setup exactly still met the failures. Fixed by making the instructions true rather than the test pass, with a contract test that EXECUTES both refusal paths and asserts the script appears before the suite command -- proved able to fail. A cold-clone CI job was declined on the grounds that fifteen minutes of wall clock gets disabled the first flaky week | landed | `docs/superpowers/plans/2026-08-17-sync-to-beta-scope.md` |







| M0-W266 | Why a fully unit-tested screen went unseen, recorded because it generalises: the workflow route serves the newest generation and the seeded fixture pairs an abandoned generation 0 with an opened generation 1, so no URL in the fixture produces the abandoned screen. Nobody skipped it; the data made it unreachable, and its tests kept passing. The screen itself renders correctly. Under it sits `B146`, filed not built: a superseded generation has no address, so for a finding that abandoned then retried the reason stays visible and the evidence beneath it is unreachable | landed | `docs/superpowers/plans/2026-08-17-sync-to-beta-scope.md` |







| M0-W267 | The `-n 4` guidance is retired, because it was charging every lane 108 seconds a run to prevent a crash that no longer happens. Lane C measured it once `CI-W295` made a dead worker visible on a runner: `-n auto` is 185s on Linux and 125s here with no worker lost, against 233s for `-n 4`, and the npx-lock starvation it existed to avoid was fixed in `2cf2e62`. The lane proposed the edit rather than making it, because the charter is the coordinator's file. A workaround that outlives its cause is a tax nobody notices paying | landed | `docs/superpowers/orchestration/2026-08-17-lane-charters.md` |







| M0-W268 | The reference material gets a hierarchy and the visual comparison gets an eval, because recreating the drawn console has been tedious and the reason is diagnosable: we compare a PNG to a running application, the dev captures are five weeks stale with nothing current to compare against, and the mock ships as ~100KB of renderable SOURCE that nobody has ever queried. Tier 1 is the demo and it is the only visual target; Tier 2 is Superlog and the competitor set, concepts only per `interface-originality.md`; Tier 3 is history. Research recorded: screenshot diffing answers the wrong question, design-token extractors answer this one, and a model handed a token set does arithmetic where one handed a PNG does interpretation | landed | `docs/superpowers/plans/2026-08-17-reference-hierarchy-and-visual-eval.md` |







| M0-W269 | Why the console is not getting visually better, audited against `git log` rather than guessed: fourteen console units landed today, seven were signing or re-signing Gate 3, and ZERO were visual fidelity. The lane executed well; it was asked the wrong question. Recorded with three coordinator fixes -- fidelity gets its own axis and sign-off separate from honesty, the demo is the bar and matching our own drawing is not an originality violation, and the dispatch mix alternates rather than filling a queue with correctness while expecting beauty. This project measured the same failure on 2026-08-06 and I re-created the conditions for it | landed | `docs/superpowers/plans/2026-08-17-reference-hierarchy-and-visual-eval.md` |







| M0-W270 | The hierarchy ruling corrected against evidence: I wrote *v2 supersedes v1* from filename order without opening either file, and the eval's first run refuted it three ways -- v2 is a light theme against a dark-only ruling, draws no radius against two declared tokens, and has a 1.45 type range against a console rebuilt for 3.4. Decisively, v2 draws 6 side-by-side regions to v1's 17, so following it would have made the console worse at the exact complaint the eval exists to measure. v1 is the appearance target; v2 supersedes on vocabulary only. Also recorded: the method works, the in-house script beat four extractors with zero dependencies, and Fleet's gap is composition rather than palette | landed | `docs/superpowers/plans/2026-08-17-reference-hierarchy-and-visual-eval.md` |







| M0-W271 | The eval plan gains the constraint that decides whether it can ever be a gate, from `CI-W300`: token-derived properties may gate, content counts may not. Colour and radius move only when a token changes, which is when a gate should fire; regions, prose and density move on every copy edit, and gating those makes it a snapshot test this repository already ruled gets deleted within a week. It runs in the `web` job rather than `beta-gates`, because `beta-gates` carries `--exit-zero` so a verdict cannot fail a build and an eval that gates needs the opposite | landed | `docs/superpowers/plans/2026-08-17-reference-hierarchy-and-visual-eval.md` |







| M0-W272 | `python -m sync.api` starts again -- the `B166` auth import sat inside `app_factory` while `main` called the same names, so the entrypoint died on `NameError` while `test_api_auth.py` passed throughout, because every test builds the app through `create_app` and none executes `main`. Taken by the coordinator after the owning lane wedged for over an hour on a one-line move while it blocked the owner's stated priority. The test that would have caught it is here too, and its FIRST version did not work: running `main` and asserting no `NameError` passed with the import removed, because `main` dies on the database first and never reaches the line. It now reads `LOAD_GLOBAL` off the bytecode, which is decidable without a database or a port, and it was proved red with the import removed and green with it restored | landed | `src/sync/api/__main__.py`, `tests/test_api_entrypoint_starts.py` |







| M0-W273 | The Fleet composition finding is withdrawn and the routing off it was wrong. Two measurement defects, both of which returned a plausible number rather than an error: the harness authenticated by URL credential, which Chrome does not attach to a page's own fetches, so three panels rendered their never-reached-a-server state and the eval scored error copy as console prose; and `sideBySide` counted markup technique, since the mock holds 0 `<table>` and 33 `grid-template-columns` and draws every table as grid rows, so each mock data row scored as a placement while our semantic `<tr>` scored nothing. 17-against-4 was almost entirely that. Lane B refused the layout pass I dispatched, replaced the metric with `regionsBeside`, and re-ran rather than asserting. Rule recorded: a visual metric is checked against a screen whose answer is already known before it may order work | landed | `docs/superpowers/plans/2026-08-17-reference-hierarchy-and-visual-eval.md` |







| M0-W274 | The coordinator was reading the same message three times and two others not at all. `orchestration check` returns the oldest *unacknowledged* batch and keeps returning it; the acknowledgement is `--ack <delivery_id>` on `check` itself, and there is no `orchestration ack` subcommand -- calling one fails `invalid_argument`, which reads as a bad argument rather than a missing verb. A Lane C escalation and `worker_done` sat behind an already-handled Lane B message while the owner's prompt counted 2 then 3 and `check` reported 1. Charter now carries the drain loop and the rule that a count mismatch is a defect in your own reading | landed | `docs/superpowers/orchestration/2026-08-17-lane-charters.md` |







| M0-W275 | Third reversal on the visual eval, and this one the lane found against itself: two identical runs disagreed, so nothing measured before it can order work. On the fixed instrument the composition finding gets stronger -- the console is *ahead* of the drawing on `fleet` (12 regions to 0) and `api-services` (4 to 1), level on two more, behind by exactly one pairing on three -- and the prose finding is withdrawn, Fleet's 915 characters having been read mid-load against a settled 1777. Standing consequence recorded: a visual metric must repeat before it may order work, and must refuse rather than estimate when its subject is not in a measurable state. Charter also now carries that `worker-done` is rejected once a dispatch is superseded, which silently cost two Lane B reports | landed | `docs/superpowers/plans/2026-08-17-reference-hierarchy-and-visual-eval.md`, `docs/superpowers/orchestration/2026-08-17-lane-charters.md` |







| M0-W276 | The safety net read an exhausted lane as a dead one for fifty-five minutes, and the interrupt sent to unwedge it ended the session. Lane E's quota notice landed mid-tool-call, so the agent's own chrome stayed drawn *underneath* the banner -- an in-flight tool line, a permissions footer, a prompt -- and pushed it out of the six-line window without a single byte of new output. `budget_held` now reads the whole tail when the terminal has been silent, and keeps the bound when it is producing: a tail that has not moved describes now, and output since a banner is still proof of recovery. First tests the script has ever had, all four tails taken from real terminals | landed | `scripts/orchestration/resume_lanes.py`, `tests/test_resume_lanes_budget.py` |







| M0-W278 | A worker may fast-forward `main`; it still may not merge into it. Lane A held a full day of gated work locally, correctly, because `CLAUDE.md` said a worker never pushes `main` and `autonomous-development.md` lists that among the human's three. The rule was written for one integration branch and one coordinator and does not describe five lanes with disjoint file ownership. A fast-forward of a branch already containing `origin/main` creates no commit, resolves no conflict and cannot lose work -- publication, not integration -- and `git merge-base --is-ancestor` is the proof rather than a belief. Reversible; recorded as the coordinator's | landed | `CLAUDE.md` |







| M0-W279 | The safety net was retrying a lane that was working, once per sweep. `worker-start` gives up after about a minute waiting for a busy TUI and marks the dispatch failed while the agent works straight through -- Lane C spent six minutes inside one `npm install` collecting a garbage retry dispatch on every pass. A bad record is now checked against the terminal before it is believed: the terminal is evidence, the record is a hypothesis. No terminal to check is still not evidence of health. Eight cases, and the same sweep now reads Lane C as working despite its record and Lane E as budget-held, which is both fixes confirmed on live data | landed | `scripts/orchestration/resume_lanes.py`, `tests/test_resume_lanes_verdict.py` |







| M0-W280 | There are two inboxes and I had been reading one. Bare `check` drains the Run FIFO; `check --terminal <handle> --all` reads the terminal's own mailbox, which held 52 non-heartbeat messages including a Lane C `worker_done` on `CI-W299`/`CI-W300` that never appeared in the FIFO and was never answered -- while the FIFO read empty. `--all` marks nothing read, so `read_at` cannot separate handled from unhandled; sort by `created_at` instead. Recorded with the matching failure in the other direction: Lane A said plainly that mail was not reaching it, was right, and a ruling that unblocked a day of its held work needed `terminal send` to arrive | landed | `docs/superpowers/orchestration/2026-08-17-lane-charters.md` |







| M0-W281 | Owner commissioned live browser feedback in the eval's scoring loop: console errors, failed requests and broken layout mark a remediation FAILED, revert, self-correct from what the browser said rather than from a re-reading of the diff. Specified with the two constraints that make it work -- score the **delta** and never the absolute, because B147 already 404s and an absolute rule marks every change FAILED; and these may gate where counts may not, since an error signal is binary and does not move when prose is edited, which is exactly the distinction `CI-W300` drew. Over-fetching reports rather than fails: a cost finding is not a correctness one | landed | `docs/superpowers/plans/2026-08-17-reference-hierarchy-and-visual-eval.md` |







| M0-W282 | The owner's directive arrived in full and three parts had been lost to truncation, one of them load-bearing. A persistent background session against `localhost:5173` rather than one opened per measurement; React **hydration errors and warning flags**, which an `error`-level filter drops precisely because React reports hydration as a warning; and the affirmative check -- **inspect the DOM and confirm the change actually appears** -- which no error-only rule can supply. A remediation that breaks nothing and also did not take is a silent no-op, and an absent error is not evidence of an applied change. Governing sentence recorded: do not rely solely on static analysis or unit tests | landed | `docs/superpowers/plans/2026-08-17-reference-hierarchy-and-visual-eval.md` |







| M0-W283 | The ancestor check earned its keep on its first real test. Lane A's branch has diverged -- `git merge-base --is-ancestor origin/main HEAD` fails, and `git diff --stat` against `main` reports 87 files and **5983 deletions**, because the branch predates most of today's landings. A push in that state would not have published its commits; it would have reverted four other lanes'. The cost of the stall is real and separate: **B165 is fixed on that branch and not on `main`**, fourteen commits deep, and it is the only live injection path in the tree. Lane A told to merge, re-gate, then land -- and to merge `origin/main` at the *start* of each iteration rather than the end, which is what let it go stale | landed | escalation, no code |







| M0-W284 | Caught a lane gating a merge in the wrong tree. Lane A ran the suite after `cd` to the *primary* worktree, which holds `main`, while its merge sat in `b97-patch-sandbox`. It would have passed, proved nothing about the branch, and read as success. Fifth defect of that shape today and I wrote one of them, so it is recorded as a trap rather than a fault. Charter now says gate from your own worktree and print `git rev-parse --show-toplevel` beside the result | landed | `docs/superpowers/orchestration/2026-08-17-lane-charters.md` |







| M0-W285 | A budget hold's remaining time was measured from the terminal's last-output timestamp, which is a proxy that fails in both directions. Lane D reported 23 minutes of silence while carrying a `Resets in 17m34s` banner printed seconds earlier, so the sweep compared a new window against an old clock, called the hold expired, retried into the same quota wall, and then reported the lane STALE -- the classification that invites an interrupt, which is what ended Lane E's session earlier the same day. The clock is now per-notice and persisted: a *changed* banner restarts it, because a fresh banner is proof the last retry already failed. Six cases, including a corrupt state file, since the net exists to run when nobody is watching | landed | `scripts/orchestration/resume_lanes.py`, `tests/test_resume_lanes_hold_clock.py`, `.gitignore` |







| M0-W286 | Caught Lane E rewriting a fix that landed two hours earlier. Its worktree had not merged since `6a9637d`, so it read its own stale `src/sync/api/__main__.py`, saw a genuinely absent import, and started writing it again -- and nothing in that file could have told it otherwise. Rejected the edit mid-prompt and routed it to merge first, then B147, B148 and its share of the decode-handler red. Charter trap added: a stale worktree makes you rebuild what already landed, and the rebuild looks like progress -- you are reading a real file, seeing a real absence, and fixing a real bug that is already fixed somewhere you did not look | landed | `docs/superpowers/orchestration/2026-08-17-lane-charters.md` |







| M0-W287 | A third channel that is in neither inbox. `terminal send` puts text in a lane's scrollback and never becomes a message, so Lane C asked which item a dispatch referred to -- naming its newest inbox message and correctly saying nothing followed it -- while the dispatch sat in its transcript. Third addressing failure today. Charter: use `terminal send` when a message must interrupt, then follow it with an `orchestration send` carrying the same content, so it exists somewhere a lane can look up | landed | `docs/superpowers/orchestration/2026-08-17-lane-charters.md` |







| M0-W288 | A backlog number collided for the first time since the blocks were allocated: two `B150` items, Lane C's CI-red one (fixed) and Lane B's *viewing the code means call sites*. Cause is not carelessness -- Lane B's block `B145-B149` was **full**, so the next number it took landed in Lane C's range, which is a defect in my allocation rather than in its counting. Lane B's item renumbered to `B173` with a note saying nothing about it changed, and its block extended to `B173-B182` alongside its second work-item block. `B97`'s two headings are an item plus a status section and are not a collision | landed | `docs/superpowers/BACKLOG.md`, `docs/superpowers/orchestration/2026-08-17-lane-charters.md` |







| CI-W297 | B169 fixed, and the instructions were wrong rather than unchecked: `scripts/fetch_corpus_repositories.py` was named in no document in this repository, so following the setup exactly still met the corpus failures. Both setup blocks now name it in order, and `tests/test_gate_setup_contract.py` keeps them true by executing both refusal paths and asserting the script each one names is documented before the suite | landed | `README.md`, `CONTRIBUTING.md`, `tests/test_gate_setup_contract.py` |







| CI-W298 | B170 measured in both environments now that `CI-W295` lets CI report a dead worker: `-n auto` is 185s on a runner and **125s** here, both TRUSTWORTHY with no worker lost, against 233s for `-n 4`. The workaround outlived its cause and charges every lane 108s a run; the charter guidance is the thing to retire, proposed rather than applied. B171 closed with it and was smaller than filed: the footer already refused absence-as-zero, and what was missing was that a structural `CANNOT TELL` reads the same forever | landed | `scripts/beta_gates.py`, `docs/superpowers/BACKLOG.md` |







| CI-W299 | Gate 3's watched set was invisible-by-default and hid a real change: three directory names as a proxy for the claim surface, missing `layouts/` which renders on every screen, so the gate read MET across `M14-W351`. Now names its exclusions instead — measured, the old list saw the console last change at 13:13:59 and the new one at 13:27:20. `lib/`, `vendor/`, `App.tsx` and `main.tsx` were missing for the same reason | landed | `scripts/beta_gates.py`, `tests/test_gate_beta_measurement.py` |







| CI-W300 | What the visual eval needs from CI to be a gate rather than a one-off, advisory only and nothing built: it belongs in `web` and not in `beta-gates`, whose `--exit-zero` contract is the opposite of a gate; three to five minutes; token-derived properties may fail a build and content counts may not, because gating a count is a snapshot test. Filed B172 | landed | `docs/superpowers/reports/2026-08-17-visual-eval-what-ci-needs.md` |







| CI-W301 | `scripts/dev_up.py`: one command that checks every precondition of the console dev loop and starts nothing until they all hold, because half a stack presents as a console bug. Executed by `tests/test_gate_dev_loop.py` rather than described. It reports the broken API entrypoint as Lane E's and offers no workaround, and found a **second** undefined name — `validate_bind_security` as well as `configured_api_password` | landed | `scripts/dev_up.py`, `tests/test_gate_dev_loop.py`, `CONTRIBUTING.md` |







| CI-W302 | The dev loop actually comes up, and running it found a defect `--check` never could: `npm` was spawned by bare name and on Windows that is `npm.CMD`, so the start path died with `WinError 2` from a launcher whose purpose is to turn missing preconditions into sentences. Now a resolved executable and a checked precondition. Verified end to end — API 200 serving 12 real findings, console 200 | landed | `scripts/dev_up.py`, `tests/test_gate_dev_loop.py` |







| CI-W303 | Running the launcher twice found two defects checking it could not. It started the console without confirming the API came up, and then the readiness poll was satisfied by a **stale API on the same port** — a check that proved 'something answers' while the process it started had died with `Errno 10048`. Port is now a precondition, and the console starts only after the API it started answers | landed | `scripts/dev_up.py`, `tests/test_gate_dev_loop.py` |







| CI-W304 | `main`'s decode-handler red closed by accounting for all four clauses, one judgement each: `store.py` decodes nothing (`fromisoformat` over a `str`), `reconcile.py` and `intake_attempt.py` are catch-alls where the read is elsewhere, and `auth.py::extract_credential` genuinely decodes an attacker-controlled `Authorization` header — accounted, wants narrowing, filed for Lane E rather than changed | landed | `tests/test_decode_handlers.py` |







| M5-W311 | Data half of unbindable wrapper and telemetry coverage distinction: implemented `unbound_import_paths` on `TypeScriptAdapter` and `PythonAdapter` (tracking files importing SDKs without static call sites), wired `unbound_imports` in `reachability.py` (attributing wrapper abstractions in `Reach.reason` rather than reporting false uncalled zeros), wired scan logging in `cli.py`, and defined telemetry attachment shape for Lane B / Lane E | landed | `src/sync/index/typescript.py`, `src/sync/index/python_lang.py`, `src/sync/signals/reachability.py`, `src/sync/cli.py`, `tests/test_typescript_index.py`, `tests/test_python_index.py`, `tests/test_reachability.py`, `tests/test_decode_handlers.py`, `docs/superpowers/WORKLOG.md` |







| M0-W289 | Third handoff today that existed only in a report. Lane D landed `M5-W311` -- `unbound_import_paths` on both adapters, threaded into `reachability.py`, so a wrapper attributes its reason instead of reporting a false uncalled zero -- and said it had *defined* `telemetry_attached_at` for Lanes E and B. It appears nowhere in `src/` or `docs/`. Lane E is solving the same problem one layer down in `B147` right now, so within the hour there would have been two answers to *how does the API say nothing was ever recorded*. Routed both ways and recorded as a trap: a cross-lane contract goes in `BACKLOG.md` with a number, naming what a consumer must render differently for `null` versus zero | landed | `docs/superpowers/orchestration/2026-08-17-lane-charters.md` |







| M0-W291 | Gate 3 was stuck partly because two of its own reports disagreed about how it is read. `screen-pass.md` claimed `beta_gates.py` dates a signature by the last commit touching that file and that it is therefore *the* signature; `resign.md` said the same file deliberately carries no `Signed:` line. The script settles it -- `signature_date` reads a `Signed:` line out of the document text across every `*gate-3*.md` and takes the latest, precisely because a whitespace edit is not a re-sign. False claim removed. **And my own framing was wrong**: I have twice called this one line away from moving. It is not. The latest signature is 13:28:32 and the console changed at 15:32:34, so the screens genuinely have not been walked since -- a re-sign is a walk, and editing the line without one is this gate's own failure mode performed on the gate | landed | `docs/superpowers/reports/2026-08-17-gate-3-screen-pass.md` |







| CI-W305 | B174 filed for Lane E: `extract_credential`'s `except Exception` cannot tell malformed base64 from well-formed base64 carrying non-UTF-8 bytes, on the most attacker-controlled read in the tree. Behaviour is correct and must not change; the entry carries the one-line narrowing and the census key that has to go with it | landed | `docs/superpowers/BACKLOG.md` |







| M5-W312 | B157 filed: formalised cross-lane contract for `telemetry_attached_at` on `repo_context` and API endpoints `/api/repositories` and `/api/codebases/:id`. Specified schema column (`Lane E`), ingest lifecycle (`Lane E` / `Lane D`), and console rendering contract (`Lane B`) requiring unattached `null` to render never-measured state and non-null timestamp with 0 spans to render measured-zero quiet state, unblocking `B147` and preserving the absence-versus-zero architectural rule | landed | `docs/superpowers/BACKLOG.md`, `docs/superpowers/WORKLOG.md` |







| M5-W313 | Ruling 4 / Gate 3 & Gate 2: implemented `CorrelatingGeneratedSpecAdapter` extending `GeneratedSpecAdapter` with runtime HTTP request correlation (`RequestCorrelator` protocol) over extracted SDK routes when SDK source is staged, wired in `registry.py`, added correlation conformance cases for staged generated vendors (Anthropic, Vercel) passing `check_request_correlator`, and proved that unstaged vendors (OpenAI, Cloudflare) explicitly declare `uncorrelatable_reason` | landed | `src/sync/signals/generated/adapter.py`, `src/sync/signals/registry.py`, `tests/test_generated_adapter.py`, `tests/test_shipped_conformance.py`, `docs/superpowers/WORKLOG.md` |







| CI-W306 | Gate 4 stops declining to answer whether `main` is green: it reads a durable verdict recording **when** and **against which commit**, and a record that does not describe `HEAD` is absence rather than evidence, naming both commits. Found while wiring it that `--run-suite` — the flag the gate's own message told everyone to pass — crashed as a script with `ModuleNotFoundError`, green under pytest only | landed | `scripts/beta_gates.py`, `tests/test_gate_beta_measurement.py` |







| M0-W293 | Found why Lane A held a day of gated work through three rulings: **a long `terminal send` arrives truncated**. It reported receiving *an ambiguous truncated message about main-landing authorization* and refused to act, which was right. Every send returned `ok: true` -- the sender sees success, the reader sees half a sentence. Fourth addressing failure today and the same shape as the other three. Re-sent as seven short lines. Charter: keep terminal sends to one or two sentences, or put the body in an `orchestration send` and use the terminal only to say mail is waiting | landed | `docs/superpowers/orchestration/2026-08-17-lane-charters.md` |







| M0-W294 | Progress documents brought up to date against `git log` rather than memory: 178 work items landed today across five lanes. **The order of work changed at the top** -- `CI-W308` found that routing accuracy is the one Gate 2 axis with no pull request in its predicates, so one tier-0 production run moves an axis today while four others wait on `B7`. Gate 4 now reports the suite (3984 passed, 4 skipped) instead of declining to look. Four stale per-milestone headers that contradicted the summary table were corrected -- M5 said ~35% where the table said ~85% | landed | `docs/superpowers/BACKLOG.md` |







| M0-W295 | Second block exhaustion in one day: Lane C ran out at `B174` and stopped to ask, having filed straight through `B150-B154`. Granted `B183-B192` and a second work-item block. Blocks are now extended in tens rather than fives, and a lane two numbers from the end asks before it needs one -- running out mid-unit costs an iteration and taking the next number anyway costs a renumber plus everything citing it, which is what `M0-W288` had to undo. Lane C is also at **97% context**; told to write a resumable handoff onto `main` ahead of finishing its unit, naming commits rather than intentions | landed | `docs/superpowers/orchestration/2026-08-17-lane-charters.md` |







| M0-W296 | First lane replaced for context exhaustion, and it went cleanly because the handoff was written at 97% rather than at 100%. Lane C landed `CI-W310` -- every unit named by commit, `B183` filed with what is *not* known as well as what is -- then a successor was started in a fresh terminal against it, the retired task marked `completed`, the lane map updated, and the old agent told it is retired so two lanes cannot take `B183`. One mechanism worth recording: `/clear` sent through `orca terminal send` is path-expanded by Git Bash into `C:/Program Files/Git/clear` and never reaches the TUI, so replacement needs a new worker rather than a cleared one | landed | `docs/superpowers/orchestration/2026-08-17-lane-charters.md`, `scripts/orchestration/lane_terminals.json` |







| M0-W297 | Board updated: **1 of 4 gates met, 1 cannot be told.** Gate 3 `MET` at 16:50:47 (`M14-W364`) -- the first gate to move today, and it took a freeze rather than more work, because the console-changed timestamp had climbed 14:36 to 15:32 to 16:40 while a lane tried to sign a console it was still changing. Recorded with the thing that makes it readable: **Gate 3 will flap and that is correct** -- it is a release gate, meaningful at the moment of release, and reading it as a steady-state health light would be the composite score this console refuses on the record | landed | `docs/superpowers/BACKLOG.md` |







| M0-W298 | Four lanes found idle in one sweep, and it was my doing. Step 7 of the loop said report by `worker_done` and the coordinator re-dispatches you. When `worker-done` started being rejected I told every lane to report by message instead and **never replaced the thing that re-armed them** -- so three finished cleanly and stopped, one of them literally *standing by for any newly scheduled cross-lane units*. From outside, a lane waiting for a dispatch that no longer comes looks exactly like a lane working. Step 7 now ends *then go straight to step 1 and take the next item yourself* | landed | `docs/superpowers/orchestration/2026-08-17-lane-charters.md` |







| M0-W299 | Swept every worktree for unlanded work, which is the failure this workspace keeps hitting. **Result is good: only one worktree carries anything, and it is worthless.** `repo-context` holds three docs commits from 2026-08-06 and diffs against `main` at **67,430 deletions across 524 files** -- it predates the console rebuild. Compared file by file rather than assumed: the plan is byte-identical, and the spec and `B116` entry differ only by being *older* than `main`'s, which records the two-branch reconciliation of 2026-08-16 that the copy predates. Nothing recoverable, nothing lost. Every lane's work is on `main` | landed | `docs/superpowers/BACKLOG.md` |







| M0-W300 | Caught two lanes inside `tests/test_patch_sandbox.py` at the same minute, on the same two failures. My collision: Lane C filed `B183` with the evidence and I dispatched it to Lane C's successor, while Lane A was already investigating those tests as part of `B97` -- and I told neither about the other. Arbitrated on which question each owns rather than on the file: **Lane C keeps *why the tests fail under contention*, a harness question it holds the timings for; Lane A keeps the sandbox and proxy themselves**, which is the Gate 4 blocker nobody else can do. Lane A told to hand over its twenty minutes of findings rather than discard them | landed | arbitration, no code |







| M0-W301 | Lane D reported an empty queue and named what it would take -- the first lane to do step 7's new half properly. Declined its offer to support Lane E on `B147`/`B148`, because two lanes in one file is the collision I arbitrated between A and C twenty minutes earlier. Assigned instead the thing upstream of the whole board: **Gate 2's routing-accuracy axis reads zero because nothing has ever been routed to tier 0**, and Lane A can run the cascade but has no tier-0 input to run it over. Producing that input is a signals question. Split stated so they cannot collide -- Lane D makes the finding exist, Lane A runs the cascade, neither touches the other's paths | landed | assignment, no code |







| M0-W302 | Gate 3 flipped back to `CANNOT TELL` twenty minutes after it was met, when `M14-W366` landed -- the flap I documented in `M0-W297`, arriving on schedule. Ruled the operational half rather than chasing it: **do not re-sign per landing.** Re-sign when console work pauses, at a milestone or when the board is about to be read. The alternative is the console lane walking screens instead of improving them, or freezing the console to hold a green meter, which is optimising the proxy -- the trap `M0-W269` names. Board back to 0 of 4 met, 2 cannot be told, and that is the honest reading | landed | `docs/superpowers/BACKLOG.md` |







| M0-W303 | Corrected a stale figure of mine that five lanes were planning against. The charter and the beta scope plan both called the gate *eight to fourteen minutes* and *the single largest tax on this workspace*; `CI-W363` measured **152-230s, median about 175s** across eight runs -- about four times off. `CI-W287` and the `-n 4` to `-n auto` switch had already paid it down and nobody updated the number. Struck in both documents with the measurement, including the arithmetic showing nothing is left to attack | landed | `docs/superpowers/orchestration/2026-08-17-lane-charters.md`, `docs/superpowers/plans/2026-08-17-sync-to-beta-scope.md` |







| M0-W304 | **The coordinator's mailbox has been dead since 19:53Z** -- newest non-heartbeat unchanged and total stuck at 54 for five hours, while Lane D's terminal shows `msg_662ab1d03c2b` going out and absent. Proven rather than suspected: `check` reports a dead inbox and an empty one identically, which is the day's recurring shape reaching the coordination layer itself. Sixth addressing failure. Charter now says read terminals -- every finding routed in those five hours came from a terminal read -- and tells lanes to address each other directly, because a hop through a broken mailbox is worse than no hop | landed | `docs/superpowers/orchestration/2026-08-17-lane-charters.md` |







| M0-W305 | Owner set a **Wednesday ship date** for a deployable product with the UI as highest priority. Reordered everything against it. The honest headline first: **Gates 1 and 2 cannot be met by Wednesday** -- both need a real pull request going green in somebody else's CI, which is elapsed time and an owner authorization, not schedulable work. That does not make the product unfinished; it ships with the meter reading `CANNOT TELL` on two axes and saying exactly why, which is the position this console exists to make legible. P0 is: `main` green, `B147`, the console IA, fresh-clone bring-up, and a named deployment target | landed | `docs/superpowers/plans/2026-08-18-ship-by-wednesday.md` |







| M0-W306 | Owner answered the three Wednesday decisions and they reorder the plan. Deployment is **local-only** -- nothing hosted, a clean clone coming up on one command *is* the deliverable. **`B7` is authorised against a scratch repository we own**, so the loop can be proven end to end tonight with no external CI in the path -- that is now the highest-value item in the workspace, ahead of the UI. The audience is an **investor**, which makes `CANNOT TELL` the pitch rather than an apology: every competitor shows a number, Sync shows a number, its provenance, and an explicit refusal where the evidence does not exist | landed | `docs/superpowers/plans/2026-08-18-ship-by-wednesday.md` |







| M0-W307 | Owner named the packaging target: installation must feel like `npx skills add superloglabs/skills --all` -- one command, from the repository, and it works. With hosting out, this *is* the deployment story. Recorded with the limit that keeps it honest: `npx` gives a Node entry point and **cannot conjure a Python toolchain**, so the promise is one command to type, one screen of output, and either the product is running or you know exactly what to install -- `dev_up.py` already refuses rather than dying, and the wrapper surfaces its messages rather than hiding them | landed | `docs/superpowers/plans/2026-08-18-ship-by-wednesday.md` |







| M0-W308 | The one command does **all setup, launches localhost, and indexes the codebase** -- the third step is the one nobody had scoped and it is the point. First-run is not *bring up a product with seed data*; it is **point Sync at a repository and watch it build that repository's dependency graph**. That is the answer to *is this real*, because a graph built from a repo the viewer chose proves the indexer works on code nobody tuned it for. Two consequences: INDEX must survive an arbitrary repository with a legible outcome rather than a traceback, and **seed data becomes a fallback** -- never show somebody else's data where theirs should be | landed | `docs/superpowers/plans/2026-08-18-ship-by-wednesday.md` |







| M0-W309 | Owner clarified that the Superlog command is a **method, not a feature list**: the point is *no assembly required*, not that it happens to index. One command sets up everything the product needs -- toolchain and shims, database and schema, harnesses and skills, the console build, the running services, the index of the target codebase. **The test is not whether the command exists but whether anything is left for a person to figure out afterwards**; every remaining step is a defect in the command rather than a note for the README | landed | `docs/superpowers/plans/2026-08-18-ship-by-wednesday.md` |







| M0-W310 | Owner supplied a competitor's onboarding as **reference only**; restated it as a problem before designing ours, per `interface-originality.md`. The problem: getから *nothing* to *seeing your own data* without assembling anything. **Sync's answer differs from a telemetry product's and that difference is the strongest thing we have** -- their dashboard is empty until traces arrive, so onboarding must be instrumentation; Sync's first rung is `static`, read out of the code, so **point it at a repository and it shows real findings before anything is configured**. Value before configuration, then telemetry as a visible upgrade from `static` to `observed`, then a pull request when trust exists. Checkable claim for Wednesday: our local path is one command against the reference's five | landed | `docs/superpowers/plans/2026-08-18-ship-by-wednesday.md` |







| M0-W311 | Scoped agent automation settings against two more reference documents. Checked what exists first: **project context is already ours and better placed** -- `.sync/context.md` read from the customer's repository, versioned with the code it describes, fenced by `B165`, needing documentation rather than implementation. Genuinely missing is the policy: merge policy, merge method, base branch, per **repository**. **The `immediately` value is refused on the record** -- merging before any check runs contradicts *nothing reaches a pull request unverified* and is the black box Sync was built against; the screen says why rather than omitting it, because an absent option reads as an oversight and a refused one reads as a position. GitHub App OAuth is P2 and out: we use the `gh` CLI and have no hosted callback by choice | landed | `docs/superpowers/plans/2026-08-18-ship-by-wednesday.md` |







| M0-W312 | Third install reference (`npx @deepseek-ai/dsh web`) -- the owner has pointed at the same shape three times, so the target is now decided rather than qualified again: **`npx` -> Docker -> UI, with Docker as the single stated prerequisite.** Recorded once why the clean version is easy for a Node harness and not for us: everything they need ships in the package, while `npx` cannot ship a Python runtime or a database. Wrapping `dev_up.py` would need Python, `uv` and Postgres already present -- three prerequisites, each a place the demo dies. **The container is the artifact; `npx` is the doorbell.** New P0: the product has never been containerised | landed | `docs/superpowers/plans/2026-08-18-ship-by-wednesday.md` |







| M0-W313 | **Corrected my own quickstart design against the code.** I had written step 2 as *attach telemetry and watch bindings move from `static` to `observed`* -- but **Sync has no OTLP listener**. `sync ingest` folds a *captured* payload from a file or stdin, and `cli.py:1519` records that as deliberate. Honest step 2 is *export a payload, then ingest it*. Ruled: **do not build a listener this week** -- it is a port, a supervisor and an operational surface, built for a demo rather than a user; `static` is what the one command delivers and a captured payload is enough to show the rung *moving*. Also checked: `LICENSE` and the Apache-2.0 declaration already exist, no work | landed | `docs/superpowers/plans/2026-08-18-ship-by-wednesday.md` |







| M0-W314 | Owner reviewed the running console and gave ten items. **One is not styling: it replaces the hierarchy's root** -- a *workspace*, selected or created, connecting to one codebase, scoping everything beneath, with no fleet-wide *show all*. `console-hierarchy.md` makes that the specification's to decide, not a plan's, so it is written up as needing the owner's ruling into `specs/…:427-445` rather than absorbed. Reads as the existing intent taken further -- the spec already called Fleet *never a substitute* for the codebase level -- but the spec must say so. Sidebar reference read structurally, with the one carve-out an agent would reproduce first: **its status dots are refused by name**, so take the row structure and render outcome as a closed-vocabulary badge | landed | `docs/superpowers/plans/2026-08-18-owner-console-review.md` |







| M0-W315 | Owner refined item 1 and the refinement resolves it: **codebase selection lives in the sidebar or Settings, and the Overview must not list codebases.** Sharper than my framing -- I had said *delete the fleet root*, which left open what replaces it; **selection is chrome, not content**, and `interface-originality.md` already names *a scope switcher that says what contains what* as a convention of the form. Directly contradicts `M14-W372`, landed an hour earlier, which put the repository list first on the Overview: **the argument was right and the container was wrong** -- value-before-configuration means the *selected* codebase's findings precede any setup prompt, not that a directory of codebases leads the page | landed | `docs/superpowers/plans/2026-08-18-owner-console-review.md` |







| CI-W308 | Which quality axes wait on `B7`, as a written finding: four of five are denominated on a merged pull request and cannot move before it, but **routing accuracy needs no pull request at all** — it counts findings routed to tier 0, reads zero only because nothing has been routed there yet, and is the shortest path to moving a gate. Rehearsal rows cannot supply it: `migration_outcomes` filters them in SQL | landed | `docs/superpowers/reports/2026-08-17-which-quality-axes-wait-on-b7.md` |







| CI-W309 | B183 filed: B97's two positive controls fail under `-n auto` and pass 8 of 8 alone, with a nine-hour leaked `sync-patch-sandbox` container on the host. The first durable suite record says `passed: false` on their strength — accurate about its run, not a statement about `main`, which is the staleness Gate 4 exists to refuse | landed | `docs/superpowers/BACKLOG.md` |







| CI-W310 | Lane C handoff written where a successor can read it: every unit named by commit rather than intention, the three open items with what each needs, the six things a successor would otherwise rediscover, and the pattern that every defect this lane found in its own work came from executing rather than asserting | landed | `docs/superpowers/reports/2026-08-17-lane-c-handoff.md` |







| CI-W360 | `B183` closed, and it was none of the three candidates. The container connected in **0.022s** and sent continuously; the host-side `accept()` had already raised `TimeoutError`, because its 10s deadline started when the socket was **bound** and 11.359s of Docker setup ran next. **The defect is the anchor, not the load.** Name collision eliminated from source (`uuid4` names), the nine-hour leaked container eliminated by measurement (3989/3989 passed while it was up), `CI-W280`'s cause eliminated by evidence (`host.docker.internal` resolved). Before: 2 failed/3987 passed. After: **3990 passed, 0 failed** under `-n auto`. Filed `B184` | landed | `tests/test_patch_sandbox.py`, `docs/superpowers/reports/2026-08-17-b183-a-deadline-anchored-to-the-wrong-event.md` |







| CI-W361 | `B184` closed: the docker skip probe told an absent daemon from a silent one. A machine without Docker **refuses** immediately (`error during connect`); a daemon buried under load answers nothing until the budget expires -- and both used to become the same skip, so a loaded host could silently skip exactly the tests carrying B97's boundary claim. `probe_docker` now returns `DockerProbe(reason, timed_out)`; collection skips only for absence and raises for silence. Budget left at 30s deliberately -- 2552ms measured worst case, and widening without evidence is what the entry was filed to avoid | landed | `tests/conftest.py`, `tests/test_gate_is_bounded.py` |







| CI-W362 | The Postgres bounce measured, and it is none of the charter's three candidates: not a resource ceiling (`OOMKilled` false, no limit, `RestartCount` 0), not Docker Desktop (the leaked sandbox container ran straight through it), not the leaked-database volume. **Nor a stop-grace overrun** -- a scratch container with identical flags and 86 connections under write load stopped cleanly in **2427ms** against a 10s default, so `stop_grace_period` would have been decoration and was not added. Recovery is **2.74s**, not the three minutes the charter states. The real cost was `B185`: `CannotConnectNow` (57P03) is an `OperationalError` subclass, so a restart mid-collection read as "no Postgres" and ran the whole suite unisolated | landed | `tests/conftest.py`, `tests/test_gate_is_bounded.py`, `docs/superpowers/reports/2026-08-17-what-the-postgres-bounce-actually-is.md` |







| CI-W363 | Gate wall-clock measured across eight runs: **152-230s, median ~175s**, against the charter's "eight to fourteen minutes". The tax was real and `CI-W287` plus the `-n 4` -> `-n auto` switch already paid it. **No hotspot is left:** 12 workers x 167s is ~2000 CPU-seconds, the slowest single test is 35.64s, and the top 25 are a fifth of the total -- deleting the worst outright returns under 2% of wall clock, so the suite is throughput-bound and a further cut would be a rewrite rather than an optimisation. None of the slow tests sleeps; each drives a real container, child pytest, `tsc` or Postgres. Closes measured rather than optimised | landed | `docs/superpowers/reports/2026-08-17-the-gate-wall-clock-is-already-paid-down.md` |







| CI-W364 | `B172` re-measured against the tree rather than against its own filing: the original blocker is **gone** -- Lane B settled the extraction mechanism, `web/scripts/visual-eval.mjs` won and installs nothing -- and a different one is now load-bearing. **The eval cannot fail:** no `process.exit(1)`, no gate predicate, so wiring CI around it today would build a job that always passes, which is the shape test-discipline forbids. Second cost found: `serve-console.mjs` proxies `/api` to a live origin, so a CI run needs Postgres, the API and seed data before one property can be read. Both recorded with what Lane B must add | landed | `docs/superpowers/BACKLOG.md` |







| CI-W365 | The class behind `B183`/`B184`/`B185` audited for rather than waited for, and it found a fourth: `beta_gates.py::_resume_path_exists` returned `False` on `OSError`, so a file it could not open reported the resume path as **missing** and Gate 1 failed with "no resume path, so a review comment leaves the run parked forever" -- a claim about code it had not read, in a script that argues the opposite of itself 600 lines earlier for the database. Now returns `None` and Gate 1 says `CANNOT_TELL`. A guard test pins that it can still report absence, so the fix cannot become "never say no". Every other broad handler in `scripts/` and `tests/conftest.py` checked and found deliberate | landed | `scripts/beta_gates.py`, `tests/test_gate_beta_measurement.py` |







| CI-W366 | Coordinator reported `main` red on both B97 controls. **Could not reproduce:** 4002 passed / 0 failed at `388c822` from this lane's worktree, and their run collected 3999 against `main`'s 4006, i.e. seven tests behind. Found the mechanism that *would* produce it under load anyway and hardened against it: `probe_connect` maps a 15s `docker exec` timeout to `reachable=False`, which is right for "is this blocked" and fatal for a positive control asserting the opposite. `_probe_until_reachable` retries so a timeout cannot read as a definite negative, with a guard test pinning that something genuinely unreachable still fails. Filed `B186` for the `ProbeResult.timed_out` half, which is Lane A's file | landed | `tests/test_patch_sandbox.py`, `docs/superpowers/BACKLOG.md` |







| CI-W367 | **P0, the red `main`.** Reproduced on the fourth attempt (~1 run in 3) and the cause is a race in the test, not in the boundary. `received["bytes"]` is incremented by the drain thread, so sampling it the instant `docker rm -f` returns samples *how far that thread has got* -- and under twelve workers plus five sessions it is still counting bytes the container sent **before** teardown. The test then failed saying "the structural fix did not close the window", which is a false statement about B97's boundary. `_quiesced_byte_count` waits for the fixed point instead, and raises if the count never settles, which is the real leak. Two Docker-free tests pin it, both watched failing against the old sample | landed | `tests/test_patch_sandbox.py` |







| CI-W368 | **P0: the product is containerised.** `Dockerfile` (two stages: console build, then Python 3.12 + Node 22 + `uv` runtime), `docker-compose.demo.yml`, `docker/entrypoint.sh` and a `.dockerignore` that did not exist. One command brings up Postgres, applies the schema, starts the API, waits for it to answer, and serves the console on `127.0.0.1:4173` -- **verified running, not asserted**: console 200, `/api/repositories` 200. Docker is the only prerequisite. Five build failures and one runtime defect were found by executing it, including `B187`, where the console's credential made every API panel 401. **Known gap: the console comes up empty because nothing indexes the target repository** -- no such entry point exists | landed | `Dockerfile`, `docker-compose.demo.yml`, `docker/entrypoint.sh`, `.dockerignore` |







| CI-W369 | **The one-command install was broken on a fresh clone and worked in the worktree that built it.** `core.autocrlf` is `true` here, so a clone of `main` gets a CRLF `entrypoint.sh` and the container dies with ``env: 'bash\r': No such file or directory`` -- proven by cloning from GitHub into a clean directory and running it, not inferred. A narrow `.gitattributes` pins LF for `*.sh` and `Dockerfile` only. This is a deliberate, stated exception to `CLAUDE.md`'s no-`.gitattributes` rule, which is about silencing the CRLF warning; the warning is untouched and nothing else is covered | landed | `.gitattributes` |







| CI-W370 | Why the container comes up empty, scoped rather than guessed. There is **no `index` entry point** in the CLI; the composition exists only inside `run`. The blocker is not the wiring: indexing is per vendor, and `prepare_vendor` reaches the network **and shells out to `gh`** -- measured, failing with `gh: No commit found for the ref None (HTTP 404)`. A stranger's container has no `gh`, no credential and no staged spec. `load_vendor` is the offline twin but builds over artifacts something else staged. Filed `B188` with the three routes and what each trades, because the choice is not this lane's to make | landed | `docs/superpowers/BACKLOG.md` |







| CI-W371 | **The chain that ends in a stranger typing one command.** The four-surfaces audit recorded the container as never built and the `npx` doorbell as absent; the container landed in `CI-W368` and this closes the rest. Root `package.json` with a `bin`, and `bin/sync-up.mjs` -- which checks the one prerequisite and hands over to `docker compose`, reimplementing none of the entrypoint. **It tells a missing Docker from a stopped one**, because those read identically to a newcomer and want different answers. `tests/test_container_install.py` closes the audit's real finding, that nothing verified one command brings it up: ten fast structural tests locally, and a `container` CI job that actually runs the command and asserts the console answers, the API answers **through the proxy** (`B187`'s shape), and an unauthenticated request is refused. README carries the quickstart journey | landed | `package.json`, `bin/sync-up.mjs`, `tests/test_container_install.py`, `.github/workflows/ci.yml`, `README.md` |



| CI-W372 | **The third race in one assertion, and the first two were real.** `CI-W360` moved a deadline off the wrong anchor, `CI-W367` stopped it sampling a counter mid-flight, and it still failed about one run in three -- because "the count has not moved for 1.5s" is a *proxy* for "the drain thread has finished", and a starved thread satisfies the proxy while still holding buffered bytes. Every version measured the scheduler. Now asserted on **EOF**, which is a fact rather than an inference: a destroyed container has no process to hold a socket open, so the stream ends and the count is final by construction. Proven able to fail by suppressing the end-of-stream signal. The dead quiescence helper and its two tests are deleted rather than left | landed | `tests/test_patch_sandbox.py` |



| CI-W373 | **The table format for large record sets, on the binding surface** -- the screen the owner's own words name (*"our calls and endpoints that have hundreds of different records"*). Audited first rather than assumed: filtering and pagination already existed, **sort did not exist at all and neither did horizontal scroll**, and headers were plain text. Each header now states its column's type and is the control that sorts it; the table scrolls inside itself so nine columns never take the navigation with them. **The type vocabulary is ours** -- `provenance`, `path`, `version` -- because `uuid`/`jsonb`/`timestamptz` describe somebody else's storage and nobody reading this screen is editing a database. Absence sinks in both directions, because it is not a value | landed | `web/src/features/bindings/call-site-columns.ts`, `binding-surface-page.tsx` |



| CI-W374 | The finding screen takes the mock's **action placement**, extracted by opening `screens/06-finding.png` rather than reading prose about it. The mock draws one primary action on the header row and two stacked full-width controls in the rail; this screen had neither -- its destinations were links buried inside sentences. Ported as arrangement, not as label: the mock's button offers to review a patch unconditionally, and this one appears only when a run actually reached a pull request. **Every honesty sentence kept in full**, beneath its control rather than folded into it, per the ruling that the layout gets the room | landed | `web/src/features/findings/finding-page.tsx` |



| CI-W375 | The evidence bundle becomes **one panel of ruled rows** with each stage's time on the right, extracted from `screens/08-pull-request.png`. Supersedes M7-W180's frame for this file and settles its own ruling 4: a rule is not a box, so a stage carrying a block now draws exactly one frame instead of a card inside a labelled panel. **The mock's most prominent element on this screen was refused** -- its Approve / Request changes / Abandon bar encodes a capability Sync does not have, and the API is read-only by guarantee. `last_seen_at` is real and nullable, so a node without one draws the absence marker rather than a blank right edge | landed | `web/src/features/pullrequests/evidence-bundle.tsx` |



| CI-W376 | `M0-W329` applied to this lane's three screens **without cutting anything**, because `prose-audit.mjs` drives a *built* console and `npm run build` exits 2 on `main` from another lane's six `tsc` errors -- so the ruling's own prerequisite is blocked. Protected sentences established first from the architecture plan. The test catches one block cleanly: `BUNDLE_STAGES[].blurb`, five blurbs and 757 characters that are identical for a run that passed, abandoned or never started -- 38% of the lane's static prose in one constant. Proposed for Settings verbatim rather than moved, since that directory is another lane's and is the broken one | landed | `docs/superpowers/reports/2026-08-18-lane-c-static-prose-audit.md` |



| CI-W377 | **`B187` met a second time, in the local dev loop.** Found by actually running `dev_up.py`: the API came up and answered `401`, because `SYNC_CONSOLE_PASSWORD` in the environment makes `configured_api_password` demand it while `serve-console.mjs` strips `authorization` on purpose -- so the console renders and every panel is empty. The container hit this and fixed it the same way; this is the other half, and neither place could have caught the other, which is why it now has a test. Also cleared the raw-utility red **my own UI work caused**: `gap-1.5` and `text-xs` are now `gap-field` and `text-meta` | landed | `scripts/dev_up.py`, `tests/test_gate_dev_loop.py`, `binding-surface-page.tsx`, `finding-page.tsx` |



| CI-W378 | **Decision 32 makes the install command the first thirty seconds of the demo, and it could not build.** The image ran `npm run build` = `tsc -b && vite build`, so the console stage failed whenever any lane had an in-progress type error -- measured at **24 errors across six files** in two other lanes' directories, none reached by any screen the image serves. With five lanes in `web/`, a cleanly-typechecking `main` at the instant that command is typed is a coincidence, not a property. The image now runs `vite build`; **the typecheck is relocated, not dropped** -- CI's `web` job still runs `npm run build` and still gates every push. Verified: image builds, console 200, API 200 through the proxy, unauthenticated 401, and the console renders. Also recorded the mock's approval-bar conflict where the decisions doc asks for it | landed | `Dockerfile`, `docs/superpowers/plans/2026-08-18-owner-ui-decisions.md` |



| CI-W379 | `M0-W329` applied with a measurement rather than a count. `BUNDLE_STAGES[].blurb` failed the test outright -- five sentences reading identically for a run that passed, abandoned or never started. Measured on the **built** console: the screen carried **1,309** characters against the mock's 282-579, and these were **757** of them; it now measures **569**, inside the mock's range. **A deduplication, not a cut** -- `workflows/node-sequence.tsx` already describes every node, in different words for the same fact | landed | `web/src/features/pullrequests/evidence-bundle.tsx` |



| CI-W380 | **Eight dead links, all of which compiled.** `M14-W386` collapsed routes to one workspace-scoped region and this lane's three features built links without the prefix -- typechecked, tested, and resolving to "No screen at this address." Found by opening the screen: a prose re-measurement returned a 404 page, which is the exact trap `prose-audit.mjs` documents having been caught twice before. `repoId` threaded as a prop rather than re-read; `workspacePath` is one module, not one copy per file. The drawer's vendor link renders as **text** when `repo_id` is null, because an absent destination beats one that lies | landed | `workspace-path.ts`, `finding-page.tsx`, `pull-request-page.tsx`, `binding-drawer.tsx` |



| M0-W316 | Owner gave the positive definition and it **collapses a level**: the Overview is *this codebase's findings and everything pertaining to it*, so Overview and the spec's `Codebase` level become one screen and the `Fleet` root disappears into the scope switcher. Simpler than the recorded ladder, and simpler in the direction the spec was already arguing -- it said Fleet must never substitute for the codebase level, and this removes the possibility. **Creates a P0 dependency that is not Lane B's**: probed against the running API, `/api/findings` 404s at the top level and `M14-W365` records that every findings view requires a vendor -- so the screen just made central has no route that serves it. Lane E, beside `B147` | landed | `docs/superpowers/plans/2026-08-18-owner-console-review.md` |



| M0-W317 | Owner: Settings lists information rather than containing settings. True and known -- `M4-W231` landed it **read-only** because nothing behind it was writable. Structure taken from a reference (left sub-nav of groups, one card per setting with helper text left and control right, card-scoped save, destructive actions in their own card). What Sync actually has to put there: codebase select/add/remove, pull-request merge policy/method/base-branch with `immediately` refused on screen, adapter configuration. **One field must stay read-only where the reference does the opposite**: their project context is a dashboard textarea, ours is `.sync/context.md` in the customer's repository, and `sync/context/seed.py` says it is read and never written -- show it, say where it comes from, never edit it | landed | `docs/superpowers/plans/2026-08-18-owner-console-review.md` |



| M0-W318 | Consolidated the owner's UI direction from seven reference surfaces into per-page content decisions, and recorded the directive that **all of it lands before Wednesday**. Biggest item: the **solution workflow is where a human intervenes in work still in progress**, not a record of what an agent did -- so it gets Activity/Findings tabs, tool calls as cards, and a reply box that re-enters the run, which is `M10`'s resume-on-review-comment finally getting an interface. **Three refusals carried through and one is named in our own rule**: no confidence scalars (the reference's `9/10`), no health dot, no invented severity. Lane B's one-unit rule suspended until Wednesday in favour of parallel per-screen workflows | landed | `docs/superpowers/plans/2026-08-18-page-information-architecture.md` |



| M0-W319 | **I broke my own safety net by typing into a held terminal.** Queued Wednesday work into two budget-held lanes with the phrase *start here the moment your quota resets*; the scan reads newest-first for a line containing `resets` and returned **my sentence** as the notice. `reset_seconds` found no duration in it, so the hold had no deadline and could never expire -- the two lanes I was trying to help became the two the net would never resume. A tail contains whatever anybody typed into it, so a marker-free line matching one keyword is not evidence: the reset time may now only come from a line that **also** carries a budget marker | landed | `scripts/orchestration/resume_lanes.py` |



| M0-W320 | The sweep reported a working lane as **silent for 29783562 minutes** -- 56 years. Orca returns `lastOutputAt: null` for a terminal it hosts but does not manage, which both `agy` lanes are, and `live_terminals` coerced that with `or 0` into the epoch. **The absence-versus-zero collapse this product refuses everywhere else, reached through an `or 0` in our own tooling** -- and it would have re-dispatched a lane that was working. Absence is now preserved and the sweep says silence cannot be measured rather than inventing a number. Charter: read those two terminals by hand, because they are the least observable lanes and the most often stopped | landed | `scripts/orchestration/resume_lanes.py`, `tests/test_resume_lanes_verdict.py`, `docs/superpowers/orchestration/2026-08-17-lane-charters.md` |



| M0-W321 | A hold with no deadline never ends, and Lane A hit one while running `B7`. Claude Code prints `resets 8:20pm (America/New_York)`; `reset_seconds` read only durations and returned `None`, so `hold_expired` could never fire and the highest-value lane on the board would have been held indefinitely. **The zone is stated in the notice**, which is what makes the wall-clock form safe -- the old refusal was right about a bare `10:20am` and wrong about a stamped one. Parses both forms now, rolls to tomorrow when the time is already past rather than returning a negative hold, and still refuses an unknown zone and an unstamped clock rather than substituting the machine's own | landed | `scripts/orchestration/resume_lanes.py`, `tests/test_resume_lanes_wallclock.py` |



| M0-W327 | **Found the owner's dead sidebar buttons and they are deliberate.** `app-frame.tsx:97` -- when `destinationHref` returns `null`, the entry renders a `<span>` instead of a `<Link>`, so it looks like a button and does nothing. It returns `null` for any route needing a bound parameter, and **nine of twelve routes need one**; only `/`, `/detectors` and `/settings` are param-free. So most of the sidebar is inert most of the time. This contradicts the owner's own instruction -- *do not limit buttons based off where you are currently looking* -- and inert-but-visible is worse than absent, because it looks clickable. With the codebase as the independent variable the fix is available: bind `:repoId` from the selected codebase, and where nothing is selected route to the place that selects one | landed | diagnosis, no code |



| M0-W328 | **I have been reporting `B7` as running for six sweeps on no evidence.** Checked three ways today: `migration_outcome` holds the same four non-rehearsal attempts as this morning (tiers 2, 2, 1, -1, no tier 0); no remediation process is running; no scratch repository exists under the workspaces; `gh pr list` returns empty. **The only source for *it is running* was a lane's terminal saying so**, and I repeated it to the owner each sweep without measuring. That is the exact defect this workspace has found nine times in its instruments -- a claim that returns a plausible answer instead of an error -- committed by the coordinator in his own status reporting | landed | correction, no code |



| M0-W335 | **Both `agy` lanes are quota-dead for 130 hours** -- past Wednesday, so they are gone rather than paused. Replaced with Claude successors: Lane H takes the indexer, signals and the Overview; Lane I takes graph, dashboard, API, settings and vendors. **Lane I inherits the P0** -- the build has been broken on `main` in those files, blocking every lane's gate, and Lane A has been unable to push because of it. Two of its twenty errors are real bugs rather than typing nits: `.repositories` and `.last_intake_at` do not exist on their payload types and would have been `undefined` at runtime, silently. Third lane replacement today; the handoff cost is now routine because the worktrees carry the work | landed | `scripts/orchestration/lane_terminals.json` |



| M0-W338 | **My lane map was inverted and every message went to the wrong successor.** I issued `worker-start` for Lane I first and Lane H second, then wrote the map in H-then-I order -- assuming call order matched output order. So Lane H's scope instructions went to Lane I and vice versa for an hour. **Lane I caught it and reported rather than acting**, which is the only reason it cost nothing: it could have started editing another lane's files on my say-so. Corrected against `dispatch-show`, which is the authority. Also recorded: `CI-W378` is used twice on `main` -- Lane I renumbered to `CI-W379` in its report but the commit subject still says `W378` | landed | `scripts/orchestration/lane_terminals.json` |



| M0-W339 | **My own wall-clock fix held a free lane for 1436 minutes.** Lane A printed `resets 1:20am` and the sweep read it at **01:23** -- three minutes after the limit lifted -- and rolling a past time to tomorrow's occurrence produced a 24-hour hold. Session windows are hours, not days (Claude's five, Gemini's about two), so a rolled-forward window longer than any real one is an **expired** notice rather than a future reset. **The test that should have caught this asserted the defect**: it required 20:49 against a 20:20 reset to return 23h31m, written from the arithmetic rather than from what a CLI means when it prints one | landed | `scripts/orchestration/resume_lanes.py`, `tests/test_resume_lanes_wallclock.py` |



| M0-W340 | **The sweep gave different answers depending on which `python` ran it, and said nothing.** Windows ships no IANA database, so `zoneinfo` needs `tzdata`: the project env has 2026.3, the system interpreter has none. Under bare `python` every stamped reset returned `None` because my own handler caught `ZoneInfoNotFoundError` -- and a `None` window is a hold with no deadline, so Lanes C and H were held indefinitely on a reset **ten minutes away**. Now raises with the fix named rather than degrading. Charter: run it with `uv run python` | landed | `scripts/orchestration/resume_lanes.py`, `tests/test_resume_lanes_wallclock.py`, `docs/superpowers/orchestration/2026-08-17-lane-charters.md` |



| M0-W341 | Lane B found a trap in the component batch I commissioned: **`npx shadcn add` replaces a file rather than merging it.** Running it over the already-vendored `button.tsx` **silently deleted a recorded focus-ring decision**, caught only because the lane diffed afterwards. Twenty-two components were vendored before this batch, each potentially amended, so the nineteen-component add could have quietly reverted a day of local decisions. Charter: check whether the target exists before each add, diff and restore after, and name the pre-existing files in the commit -- **a vendored file is not upstream's alone once we have amended it** | landed | `docs/superpowers/orchestration/2026-08-17-lane-charters.md` |



| CI-W381 | **Vendor marks are fetched and shown, which reverses this card's own refusal on owner decision 6.** The refusal reasoned that Sync holds no image and no brand colour for a vendor, so an id was the honest answer; a test enforced it. **The half the decision keeps is kept literally -- nothing is redrawn**, and that test now asserts the narrower boundary (no inline `svg`, no drawn `path`) rather than being deleted. The id stays the identity: the mark is `alt=""` and never stands in for it, because Sync knows a string the graph keys on and not which company owns it. **The domain is derived rather than known** -- the endpoint is asked about `<id>.com` and allowed to answer no, and a wrong guess is harmless because it degrades to the same monogram a vendor with no mark gets; the alternative was an id-to-domain table, which is vendor-specific knowledge in a shared component. An id that cannot be a hostname never reaches the network at all. **Stated rather than buried: the request discloses which vendors a private codebase depends on**, and `withoutFetchedMarks` turns it off for a deployment that cannot accept that | landed | `web/src/features/vendors/vendor-mark.tsx`, `vendor-card.tsx`, `web/src/features/settings/adapter-table.tsx` |



| CI-W382 | **Dashboard 9, and the plan it implements names a tier that does not exist.** `2026-08-18-dashboards.md` writes adapter coverage as `coded / configured / generated`. Nothing emits `configured` -- `registry.py` constructs `coded`, `generated`, `mcp`, and `dashboard/adapters.py` adds `unregistered` -- and `vendor-card.tsx` already carries this exact drift as a documented hazard, because **a screen inventing a tier is the same defect as a screen inventing a number.** The settled authority order puts the payload above a plan, so the registry's vocabulary is what is counted and the conflict is recorded rather than silently resolved. `unregistered` is held apart from the bars, not charted beside them: it is the absence of coverage rather than a kind of it, the way dashboard 2 holds `unresolved` apart. **One colour across all tiers**, because on this console colour carries a change kind, a rung or a run outcome and a tier is none of the three -- four hues would read as a quality ordering nothing measured. A tier at nought is stated on screen as counted-and-empty, which is the one figure here where `0` is the honest answer. **Also: echarts is aliased to a stub under the test runner** -- it measures a canvas jsdom never lays out and then throws inside its own teardown, reported against whichever page happened to contain a chart; with nine dashboards coming this is factored once rather than nine times | landed | `web/src/features/settings/adapter-coverage-option.ts`, `adapter-coverage-chart.tsx`, `web/src/components/charts/echarts-jsdom-stub.tsx` |



| CI-W383 | The container CI job proves the demo **renders**, not merely that it answers. `200` is what a blank page returns too, and decision 32 makes this the first thirty seconds of Wednesday -- a console that serves an empty document would pass the old check and fail the room. Asserts the app root and the built bundle are in the served document, and that the API returns the shape a screen reads rather than any 200 | claimed | `.github/workflows/ci.yml` |



| CI-W384 | **Two of the thirty-two decisions cannot be built by anybody**, and the same missing capability blocks a third thing. Decision 21 wants a drawer that opens on the customer's code with the call site highlighted; decision 26 wants narrative, then **diff**, then evidence; the mock draws a patch panel with per-file hunks. **No route exposes source, a diff, or the patch** -- checked across all nineteen, and the workflow payload's evidence carries `branch`, `pr_url` and `replay_evidence` and nothing of the edit. Recorded as the fourth mock conflict where the decisions document asks for it | claimed | `docs/superpowers/plans/2026-08-18-owner-ui-decisions.md` |



| M14-W389 | RESERVED under the push-is-the-lock rule, before the work starts: the Solution Workflow screen. Activity node summaries that expand to their tool calls, and a Findings tab reading narrative then diff then evidence, with the provenance rung carried in the narrative where the reference set puts a confidence scalar. Owner decision 12 -- if only one screen is flawless on Wednesday it is this one | reserved | `web/src/features/workflows/**` |



| M14-W390 | **`M14-W384` names two changes, which is the collision the numbering rule was changed to stop.** Lane F's row at this number describes the Overview losing its repository list; my commit at `f061d2c7..f1ed6300` describes the sidebar no longer rendering a `<span>` where a link belongs. Both landed, neither is wrong, and the number is ambiguous forever -- recorded rather than renamed, because rewriting a pushed commit's subject to fix a register is a worse trade than a register that says what happened. Also filed here because they had no rows at all: `M14-W387` (`b783dfec..56e91c00`, the shadcn CLI replaces rather than merges and reached `button.tsx`, which nobody named, deleting a measured 1.40:1 and 2.03:1 contrast decision) and `M14-W388` (`fe50b835..f07c62cb`, eighteen shadcn components with a separate MIT NOTICE section, because the CLI yields canonical shadcn/ui rather than Supabase's `packages/ui` and listing it under commit `6ac0316` would name the wrong upstream) | landed | `docs/superpowers/WORKLOG.md` |



| M14-W384 | **The Overview listed every repository, and the owner ruled it off that screen twice.** `fleet-page.tsx:120` rendered `<CodebasesPanel />`, a directory of every codebase, on a screen whose question is what is true about the one workspace already chosen -- "which workspace am I in" is the scope switcher's question and it was being answered twice. **The panel is moved rather than deleted, and not rebuilt**: it fixed a real defect worth keeping, where the panel it replaced fetched the fleet-wide overview once and printed that `total_findings` under every card -- a false claim about every repository except the one the fleet-wide figure happened to match. It now renders inside Settings' Codebases group with its filter chips, where choosing and configuring a codebase is one question on one screen; the scoped-answer discipline in `codebases-panel.tsx` is untouched by the move. **A protected sentence had to move with it.** *Absence is not zero* pointed at "the repository list below" in two places -- the Overview footnote and `screen-limits.tsx` -- and the list is no longer below. Re-placing a referent is permitted where shortening the sentence is not, so both now name the codebase list in Settings; leaving them would have been a true sentence with a dead pointer, which is the quiet half of the same defect. The two fleet-page tests that asserted the list stays on this screen are replaced by tests asserting it is gone and that the re-pointed sentence is present, both watched failing first | landed | `web/src/features/fleet/fleet-page.tsx`, `web/src/features/fleet/screen-limits.tsx`, `web/src/features/settings/codebases-settings-panel.tsx` |



| M0-W342 | **My inverted map (`M0-W338`) put two lanes in one worktree, and the damage surfaced an hour after I thought I had closed it.** Lane H acted on a message addressed to Lane I naming `lane-e-graph`, so both were mid-edit in the same six Python files -- and the shared tree was red with 40 failures from Lane H's in-flight TDD while Lane I worked around it. **Lane I escalated rather than reverting**, and its handling is the model: stage only your own hunks as crafted blobs so the other lane's uncommitted work is untouched, then gate the resulting *commit* in a detached worktree where their dirty state is absent. Lane H moved out by patch rather than redoing the work. Sixth collision of the day and the first in Python | landed | arbitration, no code |



| M14-W387 | **The Overview's dependency graph had a canvas and no data behind it.** `DependencyCanvas` was built, tested and wired to no screen, because drawing one repository's graph meant `useBindingSurface` per vendor per operation -- a round trip per node -- and the console cannot know which operations to ask about until it has the graph that names them. Adds one scoped read: `GraphStore.call_sites_for_repository` and its count, `graph_views.repository_graph`, and `GET /api/repositories/{repo_id}/graph` under **both** path converters, because a repository id holds a slash and the default converter never matches one -- `B147` is that defect left in place on a neighbouring route, so the pair is written here rather than filed. Three distinctions are carried across the join and each is tested: every edge keeps the rung it came from and it is `static`, because a call site is what the static index found and a telemetry rung is never blended into it; `openFindingCount` stays `null` rather than becoming a zero, because this route never counted findings; and the row bound is declared, with `total_bindings` beside `truncated`, because a graph quietly missing edges misreports the exposure it exists to show | landed | `src/sync/graph/store.py`, `src/sync/dashboard/graph_views.py`, `src/sync/api/app.py`, `src/sync/api/__main__.py`, `web/src/features/index-graph/overview-graph-panel.tsx` |



| M0-W343 | Lane I escalated that `CI-W378`, `W379` and `W380` each name **two different changes**, and diagnosed the cause rather than renumbering: every lane computes *next number* by reading `WORKLOG` on `main`, and with five lanes landing hourly that read is stale before the write. It offered per-lane ranges or register-as-allocator and recommended the second. **Ruled its way, and its option (a) was not hypothetical -- pre-allocated blocks are what we already had and they failed twice by exhaustion.** New rule: append the row, push that one-line commit alone, then do the work. A second lane on the same number now loses at `git push` -- **the collision becomes a push conflict instead of two rows nobody notices** | landed | `docs/superpowers/orchestration/2026-08-17-lane-charters.md` |



| CI-W385 | **The vendor page's opening answer renders, and two route guards caught what shipping it half-done would have hidden.** The new route failed the pagination guard as *unclassified* and the console-parity guard as *declared but never fetched* -- both correct, and each a decision rather than a nit. Classified as an aggregate: one row per operation, bounded by the vendor's operation surface rather than by traffic (a thousand call sites are one row with a count of a thousand), and **a page of a distribution is a truncated picture that reads as a complete one.** `VendorExposureCard` is the consumer the second guard demanded -- a route with no consumer is a route nobody can prove works. Operation, call sites, repositories, **rung on every row**, and traffic *beside* the count rather than inside it. `observed` renders `null` as **never measured** rather than *not observed*, because nobody having looked is not a measurement of nothing. No percentage anywhere, asserted | landed | `web/src/features/vendors/vendor-exposure-card.tsx`, `tests/test_api_routes.py` |



| CI-W386 | The README quickstart carries the measured numbers instead of my own vague ones. I had written *"a few minutes... after that it is seconds"*; it is **282s cold and 22s warm**, and the build-ahead step that turns one into the other now sits where somebody following the page will see it rather than in a report they will not read | claimed | `README.md` |


| CI-W387 | **The dead-route gate earned its place within the hour**, catching a new `?repo_id=` link in `fleet/vendor-cards-grid.tsx` that arrived on a merge. Fixed rather than baselined -- the baseline records what was already broken, not new breakage -- and fixed by me because **my gate is what turned `main` red**, which is the charter's own exception for a red a lane caused where the failure names the exact fix. One line, declared, reversible | claimed | `web/src/features/fleet/vendor-cards-grid.tsx` |

| CI-W388 | Gate 3 walked fresh and signed on evidence, against a named sha. Also corrects the premise of the request: `2026-08-17-gate-3-screen-pass.md` carries no `Signed:` line **deliberately** -- it is the historical record and `M0-W291` already resolved that contradiction -- so adding one would reverse a coordinator ruling and stamp a date for a walk nobody did | claimed | `docs/superpowers/reports/2026-08-18-gate-3-walk.md` |
| M14-W392 | One charting library, and it is echarts. `recharts` arrived with the shadcn `chart.tsx` in `M14-W388` while the console's dashboards already ran on `echarts` -- four modules use it and it has a jsdom stub. Nothing but `chart.tsx` imported recharts, so `chart.tsx` is deleted and recharts dropped from `package.json`; a shadcn chart is an echarts decision first if it is ever wanted. **Recorded because the reservation for this row was wrong:** it was opened against a report that `main` was red on three of `M14-W388`'s components, and the build was never red -- the report came from a stale `node_modules`, which is the same class of mistake as reading a stale dev server. The peer dependencies were declared correctly. `resizable` and `sonner` were briefly deleted on that false premise and are restored; only the charting choice, which stands on its own merits, survived the correction | landed | `web/src/components/ui/chart.tsx`, `web/package.json`, `web/NOTICE` |



| M14-W391 | RESERVED before the work, per the push-is-the-lock rule: remove the page header from all twelve pages (owner decision 7 -- *"you don't need to have a header above each page as they already describe what they do"*). A cross-lane sweep, so it is Lane B's even though it touches every feature directory. Two things the header carries that must survive it: the breadcrumb trail, and each screen's question sentence where that sentence is one of the protected twenty-four | reserved | `web/src/layouts/page-header.tsx`, `web/src/features/**` |



| CI-W392 | **Dashboard 6, and the third error found in its own plan.** The plan said 6 needed API work; `/api/corpus/abandonment` already existed and `migration_outcome_abandon_reasons_by_kind` already grouped on the closed `AbandonReasonCode` vocabulary rather than on free text (B128). Only the chart was missing. **Corrected the plan rather than working around it** -- three rows now carry a dated correction, including dashboard 9's `configured` tier that nothing emits. Built as a self-contained card Lane B mounts on the Runs route (decision 30): component-versus-route, so neither lane learns the other's surface. **Three distinctions the chart cannot erase, each asserted in derivation and again in prose:** the bars are *attempts* and not findings, because one finding retried three times is three rows; **a null code is not `unclassified`** -- the latter is a reason a run actually reached, the former is history from before the column and cannot be backfilled, so folding them would manufacture routing evidence out of a schema migration; and a vocabulary member nobody hit was **counted and found empty**, said in a sentence rather than drawn as twelve mostly-blank bars. A code the payload carries that the console does not know is shown, never dropped -- which is also how the duplicated vocabulary is caught going stale. One colour, because a reason for giving up is not a severity. No percentage, asserted. Retires the `/api/corpus/abandonment` console-fetch exemption, which its own comment said should go the day its panel landed | landed | `web/src/features/runs/abandon-reasons-card.tsx`, `abandon-reasons-option.ts`, `docs/superpowers/plans/2026-08-18-dashboards.md` |



| M14-W393 | **Owner decision 2's Overview: fact tiles beside the dependency graph, findings below, no page header.** The tiles and the canvas both existed and neither was arranged as the decision draws it -- the graph had no screen at all until `W387` gave it a route. Puts `CodebaseFactsBand` and `OverviewGraphPanel` in one two-column band so the graph is above the fold on the first screen, which answer 2's consequence makes not optional, and drops `PageHeader` per answer 7's *no page headers*. **Recorded conflict, resolved the decision's way:** the mock draws a page header on this screen and answer 20 says the answer wins. The screen keeps its name in the breadcrumb and the sidebar rather than in an `h1` nobody needs twice. Every protected sentence stays and none is shortened, moved behind a disclosure, or put in a tooltip | landed | `web/src/features/fleet/fleet-page.tsx` |



| M0-W344 | **Reported a red build from a stale environment and told a lane its batch broke `main`.** Eleven errors, all unresolved imports in the newly-vendored `chart`, `resizable` and `sonner` -- but `recharts`, `sonner`, `next-themes` and `react-resizable-panels` are all declared in `package.json`. **My worktree's `node_modules` was stale**; `npm install` and the build is 0. Same class as reading a stale dev server this morning: an environment I had not updated, reported as a fact about the tree. One real finding survives -- `package.json` now carries **both** `echarts ^6.1.0` and `recharts ^3.8.0`, and two charting libraries is weight for no gain | landed | correction, no code |



| M0-W345 | Ruled that Lane H adopts five files a **retired** lane left uncommitted in its worktree. Lane H flagged them rather than committing another lane's work, which was right in principle -- but Lane F is quota-dead for 130 hours and nobody is behind the boundary. I read them: `totals-bar.tsx` is the totals line with a time-range selector and `vendor-cards-grid.tsx` the per-vendor cards, both modelled on `supabase-02` -- **they are decision 2 below the fold**, complementing rather than duplicating the fact-tiles-and-graph half `M14-W393` just landed. They are also the sole cause of seven local guard failures, so adopting them clears that too. Refusal attached: their reference carries per-service bars, and a count is fine where a composite is not | landed | arbitration, no code |



| M14-W394 | **Adopting Lane F's four orphaned Overview files, and refusing what two of them claimed.** Lane F is quota-dead 130 hours and nobody was left to claim 227 lines of exactly-wanted work; owner ruled adopt. Read for defects first, and the refusal check earned its keep. **Mounted after repair:** the totals line and the per-vendor cards, beneath the fact tiles and the graph, which is decision 2 below the fold. **Four claims deleted rather than restyled** -- the vendor card's bar was `openFindings / callSites` rendered as a filled track, which is a per-vendor composite figure and a *rate* besides, and its `Clean`/`Active` caption was a green dot written in words; the totals bar's time-range selector filtered nothing while implying every figure beside it was windowed, and call sites are current index state that no window applies to; `Active Runs` asserted the liveness nothing in this data can tell from a run parked on the customer's CI. **Both files defaulted an unanswered count to zero** (`?? 0`, `= 0`), which is the absence-versus-zero conflation the console exists to refuse -- now `number | null` rendering the absence marker. `total_findings_bound_reached` is honoured, so a floor is never printed as a population. **`index-finding-panels.tsx` is deleted rather than mounted:** it rendered `src/clients/{vendor}.ts` as an indexed file path that no payload carries, labelled a call-site count `Ops`, and presented three hard-coded directories as skips *the index recorded, with the reason it gave* -- nothing records those. That is a claim the data cannot support, which `CLAUDE.md` does not let a decision override | landed | `web/src/features/fleet/totals-bar.tsx`, `web/src/features/fleet/vendor-cards-grid.tsx`, `web/src/features/fleet/fleet-page.tsx` |



| CI-W395 | Dashboard 5 -- attempt outcomes by tier -- as a mountable card for Lane B's Runs route, sparse and saying so | claimed | `web/src/features/runs/` |



| M0-W346 | **The work-item register was 32 nested copies of itself -- 1,533,135 lines and 10.7MB, holding 9,686 rows for 335 work items.** It was 30KB on the 16th and doubled roughly every merge round through the night, because a conflict spanning the whole file was being resolved by keeping both sides whole. Rebuilt on `b4bea74d`, the last single-copy version, with the 41 rows added since carried forward in first-appearance order; **zero non-row lines existed in the corrupt file that were absent from the skeleton**, so nothing was lost and nothing was judged. Merged the one genuine duplicate (`M10-W240`) rather than picking a winner. 221KB, 886 lines, 335 unique ids. A memory would not have caught this -- `scripts/check_worklog.py` now fails the gate on a second `# Work items` heading or a repeated id | landed | `docs/superpowers/WORKLOG.md`, `scripts/check_worklog.py`, `tests/test_worklog_register.py` |



| M14-W396 | **`vendor_change_volume` was reached from nowhere, and the console was computing the same aggregate over one page.** The dead-link gate flagged the Python view as unwired; the more useful finding was underneath it. `extractVendorChangeVolume` recomputes volume, kinds and the monthly timeline in TypeScript from whatever page of `/api/vendors/{id}/changes` happened to be loaded, so a vendor's *total changes* was the current page's count wearing the vendor's name -- and one fact now had two implementations free to disagree. Wires the Python view to `GET /api/vendors/{vendor_id}/change-volume`, which reads `all_vendor_changes` and is therefore scoped to the vendor rather than to a page. The console fetch is exempted with a reason naming its consumer: the chart that should read it lives in `web/src/features/vendors/`, another lane's screen, so the endpoint lands here and the swap is handed over rather than reached across | landed | `src/sync/api/app.py`, `src/sync/api/__main__.py`, `tests/test_api_routes.py` |
| M0-W347 | **`orca orchestration check` without `--run` is a different mailbox, not a lighter one**, and reading the unscoped form cost most of a night. Mail addressed to `run:<run_id>` -- which is where a *rejected* `worker_done` goes -- never appears there. Re-dispatching Lane H revoked the capability its in-flight report was written against, so Orca rejected a report carrying three refusal violations it had caught in adopted code, and filed it where I was not looking while the unscoped check showed 73 heartbeats. Same root cause as Lane A's `consumer_fenced` terminal seen from the other side: scoped surfaces the fencing, unscoped returns empty, so a dead binding is indistinguishable from no mail. Also records that this row was added *after* its commit, breaking the push-is-the-lock rule I enforce on every lane | landed | `docs/superpowers/orchestration/2026-08-17-lane-charters.md` |
| M0-W348 | **`orca terminal send` types without submitting, and truncates a long paste at the start.** Both found while reaching Lane A, whose mailbox was fenced -- so the fallback channel failed at exactly the moment nothing else worked. Without `--enter` the text sits in the input box unsubmitted and reads, through `terminal read`, as delivered and ignored. A ~2,000-character brief then arrived with its first half gone, so the lane got the tree-hygiene footer and neither work assignment; it said the message was truncated rather than guessing at the missing text, which is the only reason this was caught. Re-sent as three short numbered messages, all intact | landed | `docs/superpowers/orchestration/2026-08-17-lane-charters.md` |
| M14-W398 | RESERVED before the work: the vendor change-volume chart computes its aggregate in TypeScript over whichever page happens to be loaded, so a vendor total is a count of the current page wearing the vendor's name -- wrong by an amount that changes when you paginate, which is the worst kind because it looks plausible on every screen and is never right. Swap it onto the vendor-scoped `GET /api/vendors/{vendor_id}/change-volume` and delete the client-side aggregation rather than leaving it beside the new call. Two refusals carried in with it from Lane H's read of the adopted code: a filled track at `openFindings / callSites` is a per-vendor composite AND a rate, and captioning it Clean or Active is a green dot and a liveness pulse written in words; and an unanswered count defaulted to zero is the absence-versus-zero conflation reached through a default rather than a render | reserved | `web/src/features/vendors/` |
| M14-W397 | **Dashboard 2 had no source: `bindings_by_rung` on `/api/overview`, which Lane I was blocked on.** `overview_summary` carried `binding_source` -- the single rung every open finding shares, or null when they disagree -- which answers a different question and cannot be stacked. Adds `open_findings_rung_counts`, one `GROUP BY` over the closed rung vocabulary, and a `bindings_by_rung` tally beside it. **Deliberately unbounded**, for the reason the vendor breakdown already is: a distribution derived from a bounded page is the distribution of whichever rows the ordering reached, not of the population, so it stays whole even when `total_findings_bound_reached` is true. **Every rung is present at nought**, because a rung missing from the object and a rung at zero are different claims and a stacked bar cannot tell them apart. The vocabulary is now derived from the `FindingRung` type as `FINDING_RUNGS` rather than hand-written: `detector_accountability` had already restated it inline, which is the second use and therefore the place to factor -- a third copy is where they drift. The flat-query guard moves from four to five, and its point is the bound rather than the number: each of the five is one aggregate whose cost does not move with how many findings are open | landed | `src/sync/core/models.py`, `src/sync/graph/store.py`, `src/sync/dashboard/graph_views.py`, `web/src/api/types.ts` |










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







| CI-W399 | **Dashboard 7, and the console could not read the distinction it exists for.** `observed_telemetry` has always returned `telemetry_attached_at` and `ObservedTelemetryResponse` omitted it, so an empty calls page under attached telemetry and one with no attachment at all rendered identically -- **a measured nought and nobody-having-looked collapsed into the same screen** (B157), which is the substitution this console refuses everywhere else. Field added against the payload, and the two states now render as different empty states. **An aggregate over one page is not a total**: `calls` paginates, so the card asks for the 500-row ceiling and then says on screen what it counted over and that the ranking can change when the rest arrives, rather than printing a page sum as the operation's volume. Errors sit *beside* calls as a count, never divided into them -- a failure rate averages two facts. **Every rung an operation's rows arrived at is carried, never collapsed to the strongest**: a span that correlated and one that did not are two observations. A one-day series prints its figure instead of drawing a line, because a slope needs two points and a flat line invented from one reads as stability. Propless but scoped -- it reads `repoId` from the router as `signals-page.tsx` does, since telemetry attaches per repository and a fleet-wide version of this question has no single answer | landed | `web/src/features/dashboards/observed-volume-card.tsx`, `observed-volume-option.ts`, `web/src/api/types.ts` |
| M14-W400 | RESERVED before the work: the fleet-wide show-all is still reachable, against the owner's mandatory ruling that every page corresponds to a workspace. 26 non-test branches keyed on `repoId === null` across 11 files render copy like *"Every repository the index has seen"*. The urgent part is not the copy: `detectors-page.tsx` reads its scope from a SEARCH PARAM while its route is `/repositories/:repoId/detectors`, so the page renders a fleet-wide claim while its own URL names a repository -- a screen contradicting its own address, on the product whose argument is that it tells the truth about what it checked. The route path param becomes the single source of scope; the null branches are deleted rather than defaulted. What must survive the deletion: absence is not zero and it is not show-all either -- removing a fleet-wide branch must not turn *we have not indexed this workspace* into a zero or an unexplained empty table | reserved | `web/src/features/`, `web/src/layouts/scope-switchers.tsx` |
| M0-W349 | Filed `B189`: the lane sweep prints a permanent `MANUAL` for a dispatch that can never be restarted. Lane I's `worker-start` timed out, the task settled as `failed`, and the terminal was re-dispatched under a new id -- so every sweep now warns about a lane that is working fine. **A monitoring alarm that is always on is the cannot-fail test pointed the other way**: it trains the reader to skim the column a real stall would appear in. Not fixed here because coding was not the coordinator's this sweep, and `worker-release` takes a dispatch id `dispatch-list` would not yield. Standing reading until it is: one MANUAL is noise, two is real **I first filed it as `B1`, an id taken long ago** -- the next-id arithmetic grepped for `^## B` against a file that uses `###`, so an empty match became 1. That is the duplicate-number defect the register guard exists to catch, walked into while filing a note about alarms nobody reads | filed | `docs/superpowers/BACKLOG.md` |
| M0-W350 | **The owner's mandatory no-show-all ruling is still open on eleven screens, and the show-all branch is reachable rather than dead.** Measured: 23 non-test branches keyed on `repoId === null` across 10 files -- `vendor-findings-table` 7, `binding-surface-page` 4, `vendor-page` 3, then `detectors-page`, `detector-accountability`, `vendor-changes-table` and `scope-switchers` at 2 each -- rendering copy like *every repository the index has seen*. **The reachability is the finding.** `detectors-page.tsx:71` takes scope from `searchParams.get(REPO_KEY)`, a query string, while the route is `/repositories/:repoId/detectors`. Navigate there without `?repo_id=` and the screen claims fleet scope **while its own URL names one repository** -- a screen contradicting its address, on the product whose argument is that it tells you what it checked. Ruled to Lane B as P0 ahead of everything it held: the path param becomes the single source of scope, the null branches are deleted rather than defaulted, and removing them must not turn never-indexed into a zero | dispatched | `web/src/features/**`, `web/src/layouts/scope-switchers.tsx` |
| CI-W401 | **Dashboard 1, and the misreading it is built to pre-empt: the dates are Sync's, not the vendors'.** `finding.created_at` is when a detector first recorded a claim, and a reader looking at dated bars of API findings assumes the publication timeline -- nothing in the graph carries one, because the nearest field is a detection date too. Said on the card rather than in a docstring. The series is meaningful **only because `insert_finding` is `ON CONFLICT DO NOTHING`**: an upsert that touched the row would restamp the table on every DETECT run and draw the last run instead of the history. **A gap is not a zero** -- nothing records that a detector ran, so an absent day may be no changes or no run, and the axis is categorical over days that have rows rather than continuous over a calendar that would invent them. Counts findings **as produced, including ones since closed**, because a series filtered to still-open shrinks its own past as patches land; `still_open` sits beside it. Bands take categorical slots, never a red-to-green ramp -- severity is an *ordered* vocabulary, which is what makes that the tempting mistake here -- and every band is legible from its legend and tooltip without colour. `by_rung` travels with the window. **Also cleared a red `main` that was not mine**: `M14-W396` wired the console fetch for change-volume and left its `_NOT_YET_FETCHED_BY_CONSOLE` entry behind, so the parity guard failed on `main` for every lane; the guard's own message prescribes deleting the entry and that is all that was touched | landed | `src/sync/dashboard/graph_views.py`, `src/sync/graph/store.py`, `src/sync/api/app.py`, `web/src/features/dashboards/findings-over-time-card.tsx` |
| CI-W402 | **The chart requirement made testable rather than read off the code.** `CI-W392` already met "every bar legible without its colour" -- one fill for every bar, the code on the category axis, the count in its own label -- but nothing held it. Now asserted three ways: every bar named on the axis, one shared fill so colour cannot quietly become load-bearing, and the plotted values are the real counts rather than any derived share. Proven able to fail by removing the shared fill | landed | `web/src/features/runs/abandon-reasons-option.test.ts` |
| CI-W403 | **The canvas payload could not express two of the three things the screen is for.** `repository_graph` drew `static` edges only -- correct about call sites, incomplete as a picture of what Sync knows. **The rest of the rung vocabulary now arrives as its own edges, never blended**: `observed_bindings` is one edge per (vendor, operation, rung), aggregated because `observed_call`'s grain is one row per unit of work and an unaggregated draw would put a thousand identical lines between two nodes. **Off-path is a place on the screen rather than an omission** -- an uncorrelated span names no operation so there is no node to draw it to, and `unattributed` is a value no binder emits and `BindingRung` excludes, so neither can be a rung and neither is nothing; both report as counts. **`indexed_at` is the one field allowed to be null and its null is ambiguous on purpose**: no call site row has ever existed here, which is either an index that never ran or one that ran and found no vendor call, and nothing records an index attempt -- so the payload refuses to pick and the screen says both. Retracted rows still count as indexed, because a repository whose calls have all gone was still indexed. The console type was extended in the same commit; **a payload the type cannot express is the `telemetry_attached_at` bug again** (`CI-W399`) | landed | `src/sync/dashboard/graph_views.py`, `src/sync/graph/store.py`, `web/src/api/types.ts` |
| CI-W389 | Gate 4's suite verdict can be recorded against `HEAD` at the cut, in one command, and **the record can no longer name a commit it did not test**. `head_commit()` was read *after* the four-minute run, so anything landing meanwhile produced a verdict attributed to a tree nobody measured -- the same failure the Gate 3 walk caught on itself, inside Gate 4's mechanism. `HEAD` is now pinned before the run and re-checked after, a dirty worktree is refused, and both refusals name what to do | claimed | `scripts/beta_gates.py` |
| M0-W351 | **I dispatched a screen the owner had already ruled against, and the lane refused it.** My indexing-canvas task cited the schema-visualiser reference and a vendor-first topology; **decision 8 names that shape and rejects it**, decision 19 makes the file tree the one-command install's payoff, and `M14-W386` had already deleted the vendor-first canvas on that ruling. Lane I escalated rather than complying -- second time tonight a lane caught me assigning work the record had settled, and both times reporting rather than obeying cost minutes instead of a rebuild. Ruled: build Lane I's reconciliation, `file -> operation -> vendor`, which keeps decision 8's *your codebase* framing and puts a rung on every edge rather than only the last. **The larger finding is underneath it**: the canvas is fed from open findings, so a screen about what the index saw draws what the detectors flagged -- a subset that shifts whenever a finding closes, redrawing itself when nothing about the codebase changed | ruled | `docs/superpowers/plans/2026-08-18-owner-ui-decisions.md` |
| M14-W405 | RESERVED before the work: delete the eleven dead `repoId === null` branches the bucket table in `2026-08-18-lane-b-handoff.md` classified as unreachable -- binding-surface-page 4, vendor-page 3, fleet-page 1, detector-accountability 1, vendor-changes-table 1, vendor-distribution 1. Unreachable because `M14-W400` typed their `repoId` as `string`, so the comparison is always false. **Left alone by the coordinator's ruling:** `VendorFindingsTable`'s six, because it has two callers with different scopes and the test is what a SCREEN renders rather than what a component could; `scope-switchers`' two, because chrome describing an unset switcher is where an unscoped state belongs; and `api/client.ts`, because the transport may be asked an unscoped question by something that is not a page. Nothing here may turn absence into zero: a deleted fleet-wide branch must not leave a screen silently empty where it used to say what it had checked | reserved | `web/src/features/` |
| M14-W404 | **Two finished cards mounted, and three empty states that had stopped being true.** Lane I shipped dashboards 1 and 7 as propless cards; a card nobody mounts is not shipped, so `FindingsOverTimeCard` goes on the Overview fleet-scoped and `ObservedVolumeCard` on Signals, where it reads `repoId` from the **path param** rather than the query string Lane B is removing. Each mount carries a test, because an unmounted card is invisible without one. **The larger half is what Lane I's payload change exposed on a screen I own.** `ObservedTelemetryResponse` gained `telemetry_attached_at`, and `codebase-page.tsx` collapsed measured-nought onto nobody-looked in *three* places, each saying so in prose: the calls empty state and the error-window empty state both said *this view cannot tell the two apart*, and the rung note said *nothing here says whether a traffic source was ever watching*. All three were honest when written and became false the moment the field landed -- a stated limit that no longer exists is worse than no statement, because a reader trusts it. Each now renders two states: absence of a measurement, or a measurement of nought, naming the attachment time in the second. The shapes empty state is deliberately left alone -- its ambiguity is about correlation, which this field does not resolve | landed | `web/src/features/fleet/fleet-page.tsx`, `web/src/features/signals/signals-page.tsx`, `web/src/features/repositories/codebase-page.tsx` |
| CI-W406 | **The rung was `undefined` on every edge of the screen whose whole premise is that every edge carries one -- the third instance of this bug class.** `repository_graph` emitted `rung` while `RepositoryGraphBinding` declared `binding_rung` and `file-tree-canvas.tsx` read `binding_rung`; **TypeScript could not catch it because the type was right and the payload was wrong**, and no test compared the two. `binding_rung` is the convention in thirteen other places, so the payload was the outlier. Now pinned by a test asserting the exact key set, proven able to fail by reintroducing the outlier. My own new `observed_bindings` carried the same mismatch and would have shipped it again. **Also: the canvas stops rendering one nothing for two facts.** Its own empty state used to admit the limit -- *a repository the index never ran against shows the same nothing as one that calls no vendor* -- which was honest about a payload that could not tell them apart. `indexed_at` (`CI-W403`) can, so *never recorded* (the canvas is not evidence about this codebase) is now a different screen from *indexed and found none* (a measurement about it). **Off-path renders in every state including the empty ones**, because a repository whose call sites were all retracted still holds uncorrelated spans and unattributed findings, and nought is printed rather than hidden so a reader never guesses whether it was checked | landed | `src/sync/dashboard/graph_views.py`, `web/src/features/index-graph/index-state.ts`, `off-path-note.tsx`, `index-graph-page.tsx` |
| CI-W390 | `2026-08-17-gate-3-screen-pass.md` stops reading as an omission. It carries no `Signed:` line **by design** -- `M0-W291` resolved that after two reports disagreed about the mechanism -- but Gate 3 listed it under *"not read, because they record no signature date"*, which is indistinguishable from a report somebody forgot to sign. A `Historical:` line declares the intent and the gate now reports the two apart: **unmeasured is legitimate, ambiguous is not** | claimed | `scripts/beta_gates.py`, `docs/superpowers/reports/2026-08-17-gate-3-screen-pass.md` |
| M0-W353 | **A check joined with `;` cannot stop anything**, broadcast to every lane after Lane B self-reported it. `check_worklog.py` caught the `M14-W404` duplicate and the push ran regardless, because the check and the push were chained with `;` instead of `&&`. Lane B's own sentence is the rule and it generalises past numbering: *a check whose result cannot stop the next command is decoration*. **This is the cannot-fail test moved one level out** -- the check was real and the command made its result unable to matter. Charter item rather than a lane note because five lanes gate against one `main`: a lane that can push red hands four others a red tree, and twice today the lane that found the breakage spent its first minutes proving it was not the author | landed | `docs/superpowers/orchestration/2026-08-17-lane-charters.md` |
| CI-W407 | **The indexing canvas gains its middle level, on the ruling that reconciled a dispatch with an owner decision rather than reverting either.** The dispatch asked for vendor -> operation -> call site; decision 8 names and rejects that shape (*'this is a different build from the schema-visualiser shape'*) and `M14-W386` had already deleted it. The ruling was to keep decision 8's framing -- the reader's own codebase -- and insert the level the dispatch was really after: **`src/api/billing.ts -> PostCharges -> stripe`**. **The point is the rung**: a file drawn straight to a vendor spans two bindings, so a rung on that hop named neither; with the operation on screen every edge carries the rung it was actually established at, which is the sentence this screen exists to make true. Two rungs on one hop stay two, ordered by the vocabulary rather than by arrival. **An operation is keyed by its vendor as well as its id**, because two vendors both publishing `Charge` would otherwise draw one node and route a repository's exposure to the wrong company. **A binding naming no operation is `unroutable`, not dropped** -- there is no node to route it through and inventing one would put a name on screen no payload carries, so the canvas says it is held and not drawn. The two-level derivation is **deleted rather than left beside its replacement**, its four tree-only assertions ported | landed | `web/src/features/index-graph/operation-graph.ts`, `file-tree-layout.ts`, `file-tree-canvas.tsx`, `file-tree-graph.ts` |
| CI-W391 | A contract check between the keys the API **emits** and the keys `types.ts` **declares**, failing in either direction. Three payload/type mismatches landed in one night (`CI-W379`, `CI-W399`, `CI-W406`) and `tsc` could not catch one of them: the TypeScript was correct every time and the *type* was what was wrong. Truth comes from a live response through `TestClient`, not a hand-written list, so no fourth place is created for the same fact to disagree with itself | claimed | `tests/test_api_type_contract.py` |
| M0-W354 | **Three payload/type mismatches in one night is a gap, not three bugs**, and `tsc` was correct every time -- the type described a payload the Python did not emit, so the compiler checked the console against beliefs that were themselves the defect. `CI-W379`: `.repositories` absent, so the repository selector was always empty and always showed a hard-coded value. `CI-W399`: `telemetry_attached_at` absent, so telemetry-attached and never-attached rendered as one screen. `CI-W406`: the payload emits `rung` while the type and the canvas read `binding_rung`, so **every edge of the screen built to show rungs carried `undefined`, silently**. Lane I reports its own `observed_bindings` from an hour earlier carried the identical mismatch, so the rate is not falling. Commissioned to Lane C as a gate: compare emitted keys against declared keys and fail on disagreement **in either direction**, because a field the payload sends that no type declares is how a console silently ignores data it was given. Told to derive expected keys from the response models rather than a hand-written list, or it becomes a fourth place for one fact to disagree with itself | dispatched | `scripts/`, `web/src/api/types.ts` |
| M14-W408 | **The strict-gate broadcast is unactionable while `main` is red, so this clears the features half of it.** Auditing my own chain first: I used `&&` between steps but piped the gating steps through `grep`/`head` to keep output short, and a pipeline's status is its *last* element's -- `false | grep x | head -3 && echo` prints, status 0. That is the same defect as `;` and harder to see, because it reads as a correct `&&` chain. My pushes were gated by my reading the output, not by the shell. Gating steps now run unpiped into a file, tailed only on failure. **Then the standard could not be met**: `uv run pytest tests/` failed 6 console guards on `origin/main`, none in my scope, so a strict chain blocked every lane rather than just me. Fixed 3 of the 6 across 15 files in `settings/`, `vendors/` and `dashboards/`: 61 raw spacing utilities to their tokens, driven off the test's own file/line output rather than by hand; `text-xs`/`text-sm`/`text-lg` to `text-meta`/`text-body`/`text-emphasis`; `text-[10px]` up to the 12px floor; two `transition-all` to `transition-colors`, which is what those buttons actually change; and one hover lift deleted, because a translate is a geometry claim. **12px had no token and that is deliberate** -- DESIGN.md allows four values and says a fifth is a recorded decision, not one added in passing -- so every `p-3`/`gap-3`/`px-3` resolved *down* to `row`: each sits inside a card already padded at `section`, and inner must stay tighter than outer, which is also what answer 7 asks. **Three failures deliberately left**, because each is a ruling rather than a typo: `ring-ring/50` and geometry transitions in seven vendored shadcn components under `components/ui/`, which is a vendoring-policy call, and hex literals in `runs/abandon-reasons-option.test.ts`, where whether a test fixture counts as an untracked colour is a rule question | landed | `web/src/features/settings/`, `web/src/features/vendors/`, `web/src/features/dashboards/` |
| M0-W355 | **`main` was red on six console design-token guards and nobody owned the files**, because Lane B reached 100% context and stopped. 4118 passed, 6 failed; ~40 sites spell a spacing value raw where a token already names it, concentrated in `features/settings/**` with one in `features/dashboards/`. **No successor could be placed without a worktree collision** -- both idle agents found are Antigravity CLIs sitting in `lane-e-graph` and `lane-d-signals`, the worktrees Lanes I and H already hold, and two agents in one worktree is what `M0-W342` cost. Retired Lane B instead and redistributed: **`features/settings/**` and `features/dashboards/**` to Lane I** with the red fix and the instruction that a site needing an unnamed value is a `DESIGN.md` change rather than a new token or a widened guard; **mounting dashboards 5 and 6, the unlocated filled track, and the one page of twelve that kept its header to Lane H**. Lane B's ledger: show-all 26 to 11, and the 11 remaining are the ones ruled to stay | landed | `docs/superpowers/orchestration/2026-08-18-lane-b-handoff.md` |
| CI-W409 | Red main: three of the five failing design-token guards are mine -- raw spacing across settings and dashboards, a 10px label under the 12px floor, and colour literals in a chart test | claimed | `web/src/features/` |
| M14-W410 | **B97, the last Gate 4 clause -- `ephemeral_container`, `copy_between_containers` and `ensure_image_built` were baselined as reached from nowhere, so the sandbox image was built and pre-warmed and nothing ever ran inside it.** `DockerSdkRunner` closes that with a two-container split: a proxy container holds the forward proxy and the credential, a sandboxed container runs the patch agent's own `driver.py` against the customer clone with only `ANTHROPIC_BASE_URL` in its environment -- the credential never reaches the sandboxed container. **The central claim was proven able to fail before it was trusted**: `test_docker_sdk_runner.py` asserts `SYNC_PROXY_CREDENTIAL` is absent from the sandboxed exec's env; adding it back in deliberately turned the test red, confirming the assertion means something. `driver.py` copies `ClaudeSdkRunner._drive`'s logic rather than importing it, so the sandboxed footprint does not pull in `sync.runner`'s wider re-exports. `run_proxy.py`'s `serve_until` is split out from `main()` so its test does not depend on OS `SIGTERM` delivery, which this Windows dev host does not provide the way the Linux container does. **Closes mitigations 1 (credential-free sandbox) and 3 (no network egress except the allowlisted upstream).** Still open: mitigation 5 (read-only root, wall-clock kill -- `ephemeral_container` grants neither), wiring `DockerSdkRunner` into `AgentRemediator`'s default, and a real end-to-end model call, which needs separate spend authorization. The qualified sentence in `CLAUDE.md` about executing customer code is not upgraded -- the sandbox executes the customer's toolchain, and that stays true as written | landed | `docker/patch-sandbox/`, `src/sync/runner/docker_sdk.py`, `src/sync/remediate/sandbox.py` |
| CI-W410 | Decision 36 applied to this lane's three screens: the **word** `loading` where the value goes, and no skeletons. A grey block shaped like a number is a shape the reader completes, and a console that refuses to let absence look like zero cannot let pending look like a populated layout. Six render sites, and a test that the **four states stay four** -- never-measured, measured zero, cannot-tell, not-yet-arrived -- since collapsing any two is the defect the rule names | claimed | `web/src/features/findings/pending.tsx`, `finding-page.tsx`, `binding-surface-page.tsx`, `pull-request-page.tsx` |
| M14-W411 | **Coordinator review of M14-W410 found `DockerSdkRunner` had zero non-test callers** (`grep -rn DockerSdkRunner src/` returned only the class definition) **and two of the three baselined symbols still had real entries** -- `copy_between_containers` and `ensure_image_built` were never actually reached, only `ephemeral_container` was. `AgentRemediator.__init__` now selects `DockerSdkRunner` behind an env flag (`SYNC_PATCH_SANDBOX`, off everywhere today, so construction is unchanged for every current deployment) through `runner_from_environment`, which refuses outright rather than guessing when `SYNC_PATCH_SANDBOX_CREDENTIAL` is unset -- which Anthropic credential a sandboxed run authenticates with is an owner decision (threat model Ruling 7) left open on the owner's own instruction, and `ClaudeSdkRunner`'s production path authenticates through an already-signed-in CLI rather than a portable credential string, so there is no existing value to fall back to. `ensure_image_built` is now the real image-tag source, overridable via `SYNC_PATCH_SANDBOX_IMAGE`. **`copy_between_containers` is deleted rather than kept unreached**: it was sketched for a risky/safe container pair -- a networked install phase destroyed and copied into a `network=none` safe phase -- that `DockerSdkRunner`'s actual design (two containers alive together on an isolated `--internal` network with a forward proxy) never needed, since the sandboxed container never holds an open route to lose in the first place. Its test is rewritten to keep the one property still load-bearing -- `ephemeral_container`'s teardown, not `disconnect_network`, is what closes an already-open socket -- proven against real Docker before and after the rewrite. **Also fixes a bug in Gate 4's own `_sandbox_wired`**, found while re-verifying it: a substring search over the whole baseline file misread a retirement comment naming a symbol as a live entry for it, now matched against actual baseline entries with a regression test proven red against the old logic first | landed | `src/sync/remediate/agent_patch.py`, `src/sync/runner/docker_sdk.py`, `src/sync/remediate/sandbox.py`, `scripts/beta_gates.py`, `tests/test_patch_sandbox.py`, `tests/test_agent_patch.py` |
| CI-W411 | **Decision 40 on the two tables of mine that stated no count at all.** The adapter inventory and the vendor operations table both rendered rows with no figure saying how many -- and 40's argument is that the count is not ornament, it is how a reader knows what they are looking at. **Neither table is paged**, so the honest count is not a page figure but *all of them*: the adapter inventory is bounded by what an operator configured, and the operations answer is one row per operation bounded by the vendor's operation surface. Both now say so in as many words, which tells a reader there is nothing behind the list -- a stronger claim than a page count and the one these routes can actually support | landed | `web/src/features/settings/adapter-table.tsx`, `web/src/features/vendors/vendor-exposure-card.tsx` |
| M14-W412 | **The twelfth page loses its header, and the exception closes with nothing rehoused.** Answer 7 removed page headers and Lane B converted eleven of twelve, holding `finding-page.tsx` back for a human read because it alone passed an `actions` slot. Read it: **the action was a duplicate.** "Review proposed patch" pointed at the same `workflow/pull-request` route, under the same `reachedPullRequest` condition, as the "Pull request" control already standing in the rail with its own caption. The title was `findingTitle(vendor, operation)` and the rail's fact list already labels Vendor and Operation as separate facts. So the header carried one duplicate, one restatement and a breadcrumb, and `vendor-page.tsx` -- a converted detail page -- passes no header at all and lets the rail carry the subject. This now matches it exactly. `trail`, `title`, `DEFAULT_QUESTION` and four imports went with it rather than being left dead, and `question` stays on the props interface while the component takes no parameters, which is the shape Lane B settled on the other eleven | landed | `web/src/features/findings/finding-page.tsx` |
| CI-W413 | **Incident, not a change: I put committed conflict markers on `main` and Lane H repaired them before I could.** My land loop resolved a WORKLOG conflict with `rebuild_worklog.py` and then ran `git add -A`. That branch was written for the only conflict I had ever seen in it; when `CI-W409` and `M14-W408` made the same design-token substitutions in the same six files, the rebuild fixed the register and **five more files went in with their markers intact** -- 157 tsc errors, nothing built. `M14-W411` landed the fix first and my identical repair became a no-op. **The `^UU` status check cannot see a marker that is already committed**, so the loop now greps the tree for a surviving marker after any resolution and refuses to stage if one is found. Recorded rather than dropped because it is the third time in one session that a step which could not fail was the defect -- checks piped through `tail`, a push read through `grep`, and now a resolver that resolved one file and waved five through. **Also mine and worth the same honesty: the retry arm of that loop ran `git reset --hard`, which discarded uncommitted work in the tree** -- `CI-W411` had to be rebuilt from scratch | landed | `docs/superpowers/WORKLOG.md` |
| M0-W359 | **The `^UU` guard I gave every lane cannot see a committed conflict marker**, and `main` carried six files of them until Lane H found `npm run build` dying with `PARSE_ERROR` at `settings-page.tsx:105`. Once markers are committed they are ordinary file content: `git status` shows no `UU`, `git merge` reports success, and the check I instituted after committing markers twice myself **passes clean**. Only the build or `grep -rnE '^(<<<<<<<|>>>>>>>|=======)$'` sees it; that grep is now broadcast into every lane's gate. **The collision underneath was mine**: every conflict was `M14-W408`'s token values against `CI-W409` fixing the identical violations, because I split the design-token work by directory *after* both lanes had started. **A boundary announced after the work begins describes a collision rather than preventing one** | landed | `docs/superpowers/orchestration/2026-08-17-lane-charters.md` |
| M14-W413 | **Decision 38's named defect was live in three places, and the cause was one fact spelled twice.** `lib/elapsed.ts` had `useNow` + `formatAge`, which re-render on an interval; `lib/format.ts` had `formatElapsed`, which reads the clock once at render and then holds still. Three screens I own rendered the static one, so a tab open since morning said *14 minutes ago* about something from four hours back -- the console stating a falsehood with total confidence, reached through a formatting helper rather than a claim anyone wrote. Adds `<RelativeTime>`: re-renders each minute off the existing `useNow`, renders absence for a null or unparseable value rather than guessing, and carries the exact timestamp in `title` **with its UTC offset**, because a bare local string cannot be checked against a log line by a reader in another zone. `change-units-table`, `runs-table` and `codebase-facts` now use it -- the last inside prose, as a component rather than an interpolated string, since that is precisely how the staleness got in. **`formatElapsed` is deleted, with its tests**, rather than left beside its replacement: two spellings of *how long ago* is the duplication that disagrees with itself, and here the disagreement was the defect | landed | `web/src/components/relative-time.tsx`, `web/src/lib/format.ts`, `web/src/features/fleet/` |
| CI-W414 | **Decision 58 across the four charts I own, and the first version of the guard could not fail.** Gridlines removed from all four; the legend is now conditional on the series count, which matters on dashboard 1 because its bands vary with the data and a window holding one severity was naming it in a legend. **The rule lives in one place** -- four suites each carrying their own copy is a rule that will disagree with itself -- alongside the sentinel token fixture, which is also now shared rather than copied. **The assertion I wrote first passed against all four charts while every one of them was still drawing gridlines**: it read `splitLine?.show ?? false`, and echarts defaults `show` to true, so a `splitLine` present and merely styled sailed through. Corrected to absent-or-explicitly-off, watched it go red against all four, then fixed the charts. Gridlines are **deleted rather than disabled**, because a disabled line is one word away from returning | landed | `web/src/components/charts/chart-test-support.ts`, four `*-option.ts` |
| CI-W415 | **Decision 61 on my three tables: an empty table keeps its headers.** A panel replacing the table tells a reader there is nothing; a table that keeps its headers tells them what a row *would* be, which is 61's actual argument -- *the shape of the data is legible before there is data*. `TableEmptyState` holds it once rather than three times. **The sentences moved at full length, which is decision 63's line**: an existing on-screen sentence may be restyled and may not be trimmed, collapsed behind a disclosure, or moved into a tooltip -- so the never-measured sentence, the retracted-call-site sentence and the configured-state sentence are asserted verbatim in their new home. **`action` is optional and deliberately so**: 61 asks for one next action and a table with no honest next step says nothing rather than offering a control that leads nowhere. **The adapter table's colSpan was wrong the moment I wrote it** -- 5 against 7 real columns -- so the guard asserts colSpan against the rendered header count rather than a literal, because those two drifting apart is silent: the sentence simply stops spanning and nothing else breaks | landed | `web/src/components/table-empty.tsx`, three tables |
| M14-W414 | **Decision 60's footer, and the dead dialog was a dead *pair*.** The footer count read `1-4 of 4` under a narrowed table, which is the bare row count decision 60 forbids -- the owner did not take filter chips, so this string is the only thing between a filtered table and being read as the whole set. `describeRange` takes an optional unfiltered total and renders `1-4 of 4 matched, 27 filtered out`. **Deviation recorded:** the decision's example is `showing 4 of 31`, which is single-page; on page two that would be false, so the range stays and the filtered clause travels with it. A filter excluding nothing says nothing, because `0 filtered out` is noise that hides the real case. Wired on `vendor-findings-table`, the one table holding both numbers -- `types.ts` already states `severity_total` is the unfiltered scope and disagrees with `total` whenever a filter is on, which is exactly the number wanted. **The dialog deletion was checked before it was made, and the brief was wrong:** `vendor/supabase/ui/dialog.tsx` had one importer, `vendor/supabase/ui/command.tsx`, reached by a relative `./dialog` that a full-path grep misses -- deleting it alone broke the build, which is how it was caught. `command.tsx` is itself imported by nothing (the live palette uses `components/ui/command`), so the pair is dead and both are deleted, with both `NOTICE` attributions, because an attribution naming an absent file is its own small false claim | landed | `web/src/lib/format.ts`, `web/src/components/page-controls.tsx`, `web/src/layouts/footer-bar.tsx`, `web/src/features/vendors/vendor-findings-table.tsx`, `web/NOTICE` |
| CI-W416 | **A committed conflict marker is ordinary file content, so every guard we had was watching the one signal that cannot appear.** `main` carried markers in six files; `git status` showed no `UU`, the merges that carried them into five lanes' trees reported success, and the `^UU` check every lane was running passed clean. Only content sees it. `tests/test_no_conflict_markers.py` scans every tracked file rather than a source subtree -- the six were TypeScript and `tsc` would eventually have said so, but a marker in `schema.sql` or a fixture breaks something quieter with no compiler watching. **Proven able to fail**: a planted marker in a tracked file turned it red on all three lines, including the divider. `=======` is reported only in a file already carrying `<<<<<<<` or `>>>>>>>`, because it is also how Markdown underlines a heading -- the miss that trade accepts is stated in the docstring. **A test rather than the grep I was asked to adopt, because a guard each lane must remember is present exactly as often as somebody remembers it at five in the morning.** Also raises the skip baseline to 16: `CI-W391` added a skip and did not raise the count in the same change, which is the omission that baseline exists to force -- it caught its author two work items later | claimed | `tests/test_no_conflict_markers.py`, `tests/test_lint_test_skips.py` |
| M14-W415 | **Decision 61, and the primitive for it was already built and wired to nothing.** `runs-table` and `change-units-table` swapped the entire table for a paragraph when the page came back empty, so the column headers vanished exactly when they are most useful -- a reader learns what a run or a change unit *is* from the columns, and the screen with no rows is the screen where that teaching has to happen. `TableEmptyRow` already existed in `data-table.tsx` with no caller but its own test, so this wires what was there rather than adding a second thing. Both tables now always render the header row and put the empty message in a spanning body row, keeping every word of the existing sentences -- nothing was shortened to fit a cell. `runs-table`'s disposition tally stays row-dependent, because it counts the rows and with none it would be counting nothing. **What is deliberately not built:** 61 also asks the empty state to state what was checked and name one next action; neither payload carries how many detectors ran or when, so writing that sentence would be inventing the fact it reports. That needs an API change and is recorded rather than faked | landed | `web/src/features/fleet/runs-table.tsx`, `web/src/features/fleet/change-units-table.tsx` |
| CI-W417 | **Decision 45's grain, declared before the column exists as the decision itself demands -- and stopped deliberately at the read-only guarantee.** `finding_dismissal` is one row per dismissal of one finding by one person at one time; **a column would overwrite and the console could then never show that somebody changed their mind**, which is the only thing keeping history buys. Un-dismissal writes a second row with a null reason and the latest wins, so *nobody has touched it* and *dismissed then restored* are the same current state with different histories -- and the history is where the difference lives. The vocabulary is closed and refused at the write, for `AbandonReasonCode`'s reason: a promise to learn from dismissals needs a schema that can answer the question. **`false_positive` is separable rather than pooled**, because it is the only honest source of detector accuracy. Dismissal is not deletion -- asserted, since the read surface can only filter what is still there. **The vocabulary sits in `sync.graph` and not `sync.core`**: core is the published plugin SDK and a vendor adapter has no use for a reviewer's reason. **No route**: decision 45 needs a write path and the API is read-only by guarantee, which is the same boundary that made the pull-request approval bar resolve the mock's way losing. Asked three times and unanswered, so I built the half the decision assigns me and left the half that is not mine to relax | landed | `src/sync/graph/schema.sql`, `src/sync/graph/store.py` |
| M0-W371 | **The whole fleet is quota-exhausted at once** -- Lane A resets 6:20am ET, Lanes C, H and I at 10am, all three set to continue automatically. Four lanes had been running since the previous evening and hit their windows within minutes of each other, which is what shared pacing produces. **No development happens between now and 10am**, and that is the honest state of the Wednesday ship date rather than a scheduling detail. What is queued for the resume: 51 owner UI decisions (33-83) recorded across rounds five to seventeen, including the motion system, the style contract and the component contract, all broadcast before the lanes went down. **Gate-blocking work is entirely Lane A's** -- `B7` for Gates 1 and 2, and `DockerSdkRunner`'s missing call site for Gate 4 -- so the 6:20am lane is the one that matters most | recorded | `docs/superpowers/plans/2026-08-18-owner-ui-decisions.md` |
| CI-W418 | **A comment claiming a guarantee the code did not deliver.** The call-site scroller said in as many words that the table scrolls inside itself rather than widening the page -- and it was a `w-full overflow-x-auto` with no `min-w-0`, so a scroll container inside a flex parent kept its min-content floor, nine columns pushed the parent wider, and the **page** scrolled while the div never did. Exactly the failure the comment above it described. `components/data-table.tsx`'s `TableFrame` carries the same reasoning and the same pair, which is how the omission was visible at all. **Decision 48 makes the behaviour binding**, and two findings go with it that are not mine to fix: `components/ui/table.tsx:9` gives every table in the console `relative w-full overflow-x-auto` with **no `min-w-0`**, and `TableFrame` -- built for precisely this and carrying both halves -- is **exported, tested and used by no screen**. So 48's *never the page body* clause is currently unmet everywhere except the one scroller below. No test: `.claude/rules/console-dev-loop.md` puts class names outside vitest's scope and rendered geometry in Chrome, and I am not asserting a measurement I did not take | claimed | `web/src/features/bindings/binding-surface-page.tsx` |
| CI-W419 | **Decision 76's bus, as a real one.** Confirmed by grep first that nothing existed to subscribe to -- no `LISTEN`/`NOTIFY`, no pub/sub, and INDEX emitting no progress at all -- so the honest options were a real bus or polling behind a push facade, and the owner selected the bus. **`NOTIFY` is transactional**, which is why the publish sits inside the writing statement rather than after it: a subscriber never hears about a row that rolled back. **One event per call site and the payload carries the node**, both owner-selected with their costs stated at the point of choosing -- finest grain, no refetch. **The write must never fail because the notification did**: `NOTIFY` raises over 8000 bytes, so an oversized event degrades to a thin signal naming its kind and scope and the console re-reads. **Filtering is the subscriber's** because a Postgres channel name is an identifier and a `repo_id` is not one, so scope stays in the route path where decision 49 puts it while the shared channel is an implementation detail. One `notifies()` generator for the stream's life -- a fresh one per read drops every notification that arrived between reads, which is precisely what an index burst is, and the per-call-site test caught it | landed | `src/sync/graph/store.py` |
| M14-W420 | **The new `finding_dismissal` foreign key made every index run silently delete the dismissals it exists to preserve.** `REFERENCES finding (id) ON DELETE CASCADE` looks right and is the opposite: `finding` is re-derived, so a scan truncates it -- which Postgres refuses outright while the FK stands (`cannot truncate a table referenced in a foreign key constraint`, five tests red on `main`), and which, had the truncate been changed to CASCADE instead, would have wiped every human decision on every index. Decision 45 is explicit that dismissal is *filtered, not deleted*; this made it deleted, on a timer, with no trace. No other durable table references `finding`, and now none does. Finding ids are stable across re-derivation -- `insert_finding` hashes (detector, call_site_id, vendor_change_id, claim) -- so the key still names the same finding after the row is rebuilt. **Found by building the same table independently and hitting the identical failure**, which is the argument for `test_scan_preserves_durable_rows` existing at all. My duplicate schema, store methods and tests are deleted in favour of the version already on `main`; two concerns about it are reported rather than silently patched -- it has no natural key and no conflict clause, which `CLAUDE.md` requires of every table, and its five reads are unwired and unbaselined | landed | `src/sync/graph/schema.sql` |
| M14-W419 | **The Runs page, and Lane I's two finished cards get a screen to stand on.** Decision 30 puts Runs on the sidebar; `AbandonReasonsCard` and `TierOutcomesCard` have been built, tested and mounted nowhere since Lane I landed them. **The conflict this resolves rather than hides:** both read `/api/corpus/abandonment`, which takes no `repo_id` -- `fleet.abandonment_by_change_kind(store)` is fleet-wide at the source -- while the workspace mandate scopes every page and forbids a show-all. The owner ruled to mount them with an explicit not-narrowed sentence, the pattern `vendor-changes-table` already uses, rather than hold two finished cards off the ship or quietly print fleet figures under one workspace's name. `/api/runs` is fleet-wide for the same reason, so the statement is one sentence about the whole screen rather than one per card. Runs sits second in the rail, after Overview. **`GRAPH_LEVELS` is untouched**: this aggregates over Solution Workflow the way detector attribution aggregates over Errors & Incidents, and `console-hierarchy.md` is explicit that an aggregate is not a rung -- so no specification amendment was owed | landed | `web/src/features/runs/runs-page.tsx`, `web/src/lib/routes.ts` |
| M14-W421 | **Two owner rulings, and the Python gate is green again.** The focus-ring and geometry guards now skip `components/ui/` as well as `vendor/supabase/`: `ring-ring/50` and `transition-all` are shadcn's own defaults, and a guard failing on somebody else's defaults reports a decision nobody here made. The keyframe guard already excluded that directory on the same argument, so the two prefixes are one `_VENDORED_PREFIXES` tuple with one helper rather than a third spelling. Three guards red on `main` for hours, now green, and nothing was widened for `features/`. Second: `finding_dismissal` gained the natural key and conflict clause `CLAUDE.md` requires -- `UNIQUE (finding_id, actor, created_at)` with `ON CONFLICT ... DO UPDATE`, and `record_dismissal` takes an optional `at` so a replayed write converges while two genuine clicks stay two rows. The key must not collapse a real change of mind, which is why this is rows and not a column | landed | `tests/test_console_design_tokens.py`, `src/sync/graph/schema.sql`, `src/sync/graph/store.py` |
| M14-W422 | **`index-graph-page.tsx` was built, tested, and unreachable** -- Lane B held exclusive ownership of `routes.ts` and was retired before registering it. Registered at `/repositories/:repoId/graph`, level `Codebase`, `nav: true`: `routes.test.tsx`'s own rule is that a route buildable from the workspace's `repoId` alone belongs in the rail, not behind a `reachedFrom` link, and this one needs nothing else. `overview-graph-panel.tsx` (mounted on the workspace-picker's own compact copy of the same canvas) gains a "View full graph" link to it. Verified against a real running console and a real seeded repository, not just the build: the route renders the populated file tree, and the link's `href` resolves to it -- screenshots taken, both dev servers stopped and the seeded fixture removed afterward. Also deleted an orphaned comment block in `dead_links_baseline.txt`: a three-way merge between my M14-W411 deletion and another lane's concurrent insert resurrected prose describing `DockerSdkRunner` as unwired, with no entry line beneath it any more to anchor it -- stale and false since M14-W411 landed | landed | `web/src/lib/routes.ts`, `web/src/features/index-graph/overview-graph-panel.tsx`, `web/src/features/index-graph/index-graph-page.tsx`, `scripts/dead_links_baseline.txt` |
| CI-W422 | **Both red design-token guards are green, and neither was widened.** Seven `focus-visible:ring-ring/50` sites rendered the focus ring at half strength -- a contrast figure nobody computed, against a token whose arithmetic is in `DESIGN.md` -- and decision 53 says the focus ring is always visible, so all seven render the token. The geometry guard is **narrowed on an owner ruling rather than exempted by path**: direct manipulation of a control is not a claim about system state, so a geometry transition is permitted where the element's own class string carries an interaction selector, and banned everywhere else. **The narrowing produced a finding rather than swallowing eight**: of eight violations, seven were triggers, links and a switch thumb that move because somebody touched them, and the survivor was `progress.tsx` translating an indicator by a measured value -- motion nobody caused, which is the liveness claim the guard exists to refuse. It was removed, not exempted. The guard's own self-test had to be replaced: its fixture read `hover:opacity-80`, which the ruling now exempts, so it had stopped proving the guard rejects anything. Three tests now pin the rule -- rejects motion nobody caused, permits motion the reader caused, still catches motion bound to a value -- and the real defect was re-introduced into `progress.tsx` and watched go red | claimed | `tests/test_console_design_tokens.py`, `web/src/components/ui/` |
| M14-W423 | **B7 ran end to end for real against a scratch repository (stroland02/sync-b7-scratch, v2200->v2345, isolated `sync_b7_scratch` DB) and moved Gate 1 from an empty corpus to a real, honest measurement.** No hang: the "mystery stalls" earlier this session were `run_oasdiff_breaking` genuinely computing a diff over large spec files, confirmed with a live `py-spy` stack trace rather than guessed at. 24 real findings surfaced, all one structural class -- a response field (`card_reference_id`, a tax `tax_rate`) 7-9 levels deep inside `anyOf` branches, matched at "operation only" because the call site's own `response_fields_read` never names it. The attempted finding abandoned after 3 real attempts: the model called `Agent` (subagent dispatch, not in `ALLOWED_TOOLS`) three times with empty input, `tool_gate` refused it correctly every time, and the model gave up rather than falling back to `Grep`/`Glob`, which were available and could have located the field. **`_SCOPE_RULES` named Read/Grep/Glob as the inspection tools but never said a subagent is not one of them** -- added one line saying so plainly, proven red first against `test_the_prompt_says_subagent_dispatch_is_unavailable_and_names_the_search_tools`. **The 3 real (non-rehearsal) `migration_outcome` rows are merged into the shared `sync` DB**, ruled by the owner after I escalated it as a shared-state call rather than deciding it myself: `truncate_signal_and_detect` (`store.py:590`) is confirmed live to `TRUNCATE vendor_change, finding` only -- B129 is fixed, migration_outcome is spared by name, and the merge is durable. Merged as-is (`is_rehearsal=false`, since these were not rehearsals) rather than inventing an unmarked demo-vs-customer column to chase the gate one way or the other -- Gate 1 counting them under its current, only real/not-real axis is the honest current-state answer, and the gap (no repo-provenance distinction in the corpus) is named rather than quietly closed | landed | `src/sync/remediate/agent_patch.py`, `tests/test_agent_patch.py` |
| CI-W423 | **Gate 4 could not record a suite verdict for any lane that had ever run the npx doorbell, and the reason was not the tree.** `.gitignore` covered `web/node_modules/` and not the root one -- but `CI-W371` added a root manifest for the doorbell, so `npm` installs there too. `beta_gates.worktree_dirty()` counts untracked paths, so the gate reported *the worktree had uncommitted changes, so the suite measured something no commit holds* and refused to record. **That refusal was correct and the check is not the bug** -- a verdict about a tree no commit holds is exactly the claim this gate exists to refuse, and it was right to withhold one. The defect is that the doorbell's own install directory was never ignored, so the condition fired on an artifact rather than on work. Mine from `CI-W371`, found by running the gate rather than by reading it | claimed | `.gitignore` |
| CI-W424 | **Decision 55's ring, which no guard could see and every component contradicted.** The decision is *ring always visible, tab order only* -- visible to a mouse and a keyboard alike -- and all 37 sites across 12 files in `components/ui/` spelled it `focus-visible:`, which shows it to one of them. That is the Radix and shadcn default arriving with the catalog and never adapted, and it is the opposite of what was decided. Substituted to `focus:`, and `focus-visible:` now appears nowhere in `web/src` outside the Supabase carve-out. **The guard is the point of the unit**: this was invisible to every existing check, so a test now scans for it and is proven able to fail. It deliberately scans `components/ui/` even though `_VENDORED_PREFIXES` excludes that directory from the other guards -- that exclusion exists so nobody must restyle a catalog as it is copied in, and it is not a licence for the catalog to disagree with a decision. **A variant redefinition was considered and refused**: Tailwind can remap `focus-visible` to `:focus` in one line, which is cheaper to revert, but it leaves every class string saying one thing and meaning another -- the exact divergence this console exists to argue against | claimed | `web/src/components/ui/`, `tests/test_console_design_tokens.py` |
| CI-W425 | **The SSE route that forwards the bus**, scoped by the path decision 49 puts it in. **Held open with no lifetime cap by owner selection, and the cost was stated when the choice was offered**: forgotten tabs each hold a listening connection and enough of them exhaust the pool the read API shares. What is not a cap and is done anyway is cleanup -- the generator closes when the client disconnects. **The heartbeat is a named event rather than an SSE comment**, also owner-selected, and it is emitted by the reader rather than the store because it is a fact about the stream being alive and not about the graph -- nothing in `sync.graph` should invent events. Without it a proxy closing an idle connection is indistinguishable from an index with nothing to say, and 76 requires a drop to be rendered, which needs a drop to be distinguishable from silence. **A stream is not a page** -- no total, no offset, ends when the client goes -- so `limit`/`offset` have nothing to mean and it is classified accordingly. **The console-parity receipt carries a trap for whoever removes it**: an SSE route is read by `EventSource` and never by `fetch`, so that guard will still not see it once the consumer lands, and the guard must learn `EventSource` at the same moment the entry goes or the entry becomes permanent for a route that is genuinely consumed | landed | `src/sync/api/app.py`, `src/sync/api/__main__.py` |
| CI-W426 | **`CI-W425` wired `subscribe_events` and the dead-link baseline still called it unreachable**, so the stale-entry half of that guard was red on `main` -- the half that exists because a baseline nobody prunes stops describing the tree and starts excusing it. Entry deleted. **Recorded because the unit around it was thrown away, and that is the part worth keeping:** the coordinator assigned `GET /api/events` to this lane and I built it -- route, an extracted async frame loop with the disconnect injected so it could be tested at all, ten tests, and a negative control proving the stream cannot stamp an emit time onto an event that carries no transition time. `CI-W425` landed the same route first, scoped by path per decision 49 rather than by query string, with an owner-selected named heartbeat where mine sent an SSE comment. **Theirs is better on both counts and it was already tested, so mine is deleted entirely rather than merged into it** -- two implementations of one transport is exactly the fact written twice that this repository has spent a week paying for. What the duplication actually cost was coordination, not code: the assignment and the build were concurrent | claimed | `scripts/dead_links_baseline.txt` |
| CI-W427 | **The patch route, claimed before it is built rather than at first push** -- `CI-W426` cost this lane a whole unit to a concurrent build, and the numbering rule already says the row is the allocation. `GET /api/repositories/{repo_id}/findings/{finding_id}/patch`. **A diff is Sync's own artifact and is not blocked; source is the customer's input and stays blocked** on the threat-model ruling in `M0-W365` -- decisions 21, 26 and 47 all ran into that line without naming it. `RunState.patch` already holds `Patch.diff`, so nothing new is stored. **Owner ruling: the diff and its target are served together**, so a reader cannot see a change without seeing the branch and repository it was pushed to -- a diff with no destination is the shape somebody misreads as already applied. Absence stays separated: a run that produced no patch says why, and a patch not yet pushed says that rather than showing a blank branch | claimed | `src/sync/api/`, `src/sync/dashboard/` |
| M14-W428 | **WITHDRAWN, and the withdrawal is the point.** Claimed `GET /api/events` before writing a line, per decision 76. Checking the tree immediately after publishing the claim found the route already built and landed by another lane -- `/api/repositories/{repo_id}/events`, repo-scoped, which is better than the fleet-wide path I had planned because the bus filters by `repo_id` anyway. **So nothing was built and nothing was wasted.** That is the fourth time in one night two lanes reached for the same unit, and the first time it cost one commit instead of a full duplicate build -- the three before it (`finding_dismissal`, the design-token split, `RunsPage`) each cost a complete unit that was then discarded. The practice works and it is cheap: claim the unit, push the row, then look | withdrawn | none |
| M14-W429 | **CLAIMING BEFORE BUILDING: `index_run`, the durable half of decision 41.** A toast may announce *Index finished, 1,204 call sites* but must never be the only place that fact exists -- it has to be readable on the Overview a minute later by somebody who missed it. Nothing records an index pass completing today: `call_site.indexed_at` says rows exist, which cannot tell a finished pass from one that died halfway, and decision 61's empty state needs the same fact to say *what was checked*. Owner ruled a table with its own grain. Checked free before claiming -- no `index_run`, no completion record, nothing in `schema.sql`. Grain will be one row per index pass per repository, declared before the columns per `CLAUDE.md` | claimed | `src/sync/graph/schema.sql`, `src/sync/graph/store.py` |
| CI-W430 | **The console consumes the stream, and the aliveness lives in the banner rather than the graph.** Owner-selected: decision 87 applied to the canvas deliberately, so the count ticks while the picture stays settled until the reader asks -- 78's watch-it-index moment kept without content moving under a reader's eyes. **Three stream states stay apart** -- live-and-quiet, live-and-arriving, dropped -- which is only possible because the server's heartbeat is a named event; a hook reporting *no events lately* for both would put the console back where the payload started. **A heartbeat never moves a domain count**, asserted, because counting it would invent work that did not happen. **The drop names the loss and refuses the cause**: nothing records whether an index run continues, so the banner says the connection ended and that this screen can no longer tell -- and makes no reconnect claim, since a retry loop against a dead server renders *reconnecting* forever about a server nobody has heard from. The count survives the drop rather than resetting, because what arrived genuinely arrived. **The parity guard now reads `EventSource` as well as `fetch`**, so the receipt from `CI-W425` is deleted rather than left to become permanent -- and the guard was proven to bite by repointing the hook's URL, which it caught in both directions | landed | `web/src/features/index-graph/use-repository-events.ts`, `index-stream-banner.tsx`, `tests/test_api_routes.py` |
| CI-W431 | **`finding.opened`, and a blocking bug in the bus I shipped one unit earlier.** The event fires on `cursor.rowcount` rather than on the call: `insert_finding` is `ON CONFLICT DO NOTHING`, so a converging DETECT re-run writes nothing, and an event tied to the call would announce findings nobody opened on every scheduled pass -- **a banner that cries wolf once is a banner people turn off**. Severity travels because 87's banner is a triage prompt and a reader deciding whether to interrupt themselves should not have to open the table to find out; the rung travels for the reason every artifact derived from a binding does. **The bug: `CI-W419`'s stream held one `notifies()` generator opened with no timeout, so `next()` blocked forever on a quiet channel and the heartbeat could never fire** -- the transport looked dead exactly when the system was idle, which is the state it most needed to report honestly. A test asserting `None` on silence is what found it, by hanging. The second shape, a fresh generator per call with `stop_after=1`, unblocked it and lost every notification after the first because closing a generator discards what it buffered -- and an index run is precisely a burst. The third and current shape is a notify handler filling a deque, which owns neither failure | landed | `src/sync/graph/store.py` |
| M14-W432 | **The Findings destination, which the product is about and the rail did not have.** Five nav routes existed -- Overview, Runs, API services, Vendors, Signals, Detectors -- and a finding was reachable only by drilling through one of them. An operator asking *what is broken in this workspace* had no screen that answered it. `/api/repositories/{repo_id}/findings` already existed, fully scoped and carrying severity, path, vendor, ordering and a severity breakdown; nothing in the console called it, because `useVendorFindings` requires a vendor. **Declared fenced-file edit: one fetcher added to `web/src/api/client.ts`.** Third in the rail, after Overview and Runs, per the owner's ruling. `GRAPH_LEVELS` untouched -- this sits at the specification's own `Finding` level rather than claiming a new one. **The table is extracted at the second use, not the third**: the vendor level and this one render the same six columns over the same `RiskRow`, and the four `bindingSurfaceHref` copies `M14-W436` had to chase are what the other timing looks like. The shared table reads **the row's own vendor** rather than a page-level one, which is more correct at both levels -- a workspace-wide list holds several vendors, so a page-level vendor would put every row's operation under whichever vendor the page was about. **One of my own guards could not fail and I caught it by breaking the page**: asserting `"org/one"` appeared anywhere passed on the breadcrumb even after the figure lost its scope entirely; it pins `findings in org/one` now. The empty state reads `indexed_at` to tell *nothing has indexed this workspace* from *the detectors ran and found nothing* | landed | `web/src/features/findings/findings-page.tsx`, `web/src/features/findings/findings-table.tsx`, `web/src/api/client.ts`, `web/src/lib/routes.ts` |
| CI-W433 | **Decision 47: the pull request screen leads with the diff, and the verification chain stays visible beneath it.** The screen opened with a run outcome and five evidence stages, and never showed the change itself -- a reviewer could read every verdict about a patch without seeing the patch. `CI-W427`'s route now serves it. **The constraint is the point and it is not a layout preference:** `tsc` passed and the customer's CI running sit on screen without a click, never behind a disclosure and never in a tooltip, because that chain is the whole difference between this and a bot that opens pull requests. A run parked on the customer's CI still says so rather than reading as passed. **Touches `web/src/api/client.ts`, which is fenced** -- one additive fetcher mirroring `fetchWorkflow`, because `getJson` is module-private and a second spelling of the request would be the fact written twice | claimed | `web/src/features/pullrequests/`, `web/src/api/` |
| CI-W434 | **The bus tested where it lies rather than where it works.** Every defect this transport has had was in the quiet path, and the tests only ever asserted on events that arrived -- so a stream that blocked forever on an idle channel looked identical to one that worked. Now asserted: a quiet channel returns `None` inside its timeout (**the test fails by hanging if the CI-W419 defect returns**), a late subscriber misses what preceded it because `NOTIFY` is not queued, a burst drains in order, two repositories indexing at once do not cross streams, and a closed connection raises rather than waiting forever. **The banner now says *since you opened this***, which is load-bearing rather than wording: a reader who opens mid-index sees only what arrived after connecting, and labelling it as the run's total would be the screen claiming it watched something it did not -- the settled graph below carries the whole answer. **Burst cost measured rather than assumed**: 200 per-call-site events written and drained well inside a 30s bound, asserting the shape is linear and unblocked rather than benchmarking a machine. If a real repository ever makes that unacceptable, the fix is a coalescing publisher and this test is what shows it changed | landed | `tests/test_graph_views.py`, `web/src/features/index-graph/index-stream-banner.tsx` |
| CI-W435 | **Beta readiness scoped against the tree, not the plan** -- every claim checked by reading the repository, and where the README and the tree disagreed that is recorded as a finding. **Three owner decisions taken as multiple choice so none of it is a guess**: B188 resolved as *bake a pinned spec AND ship `--repo`*, the largest of the four routes and the only one where a new user sees the full loop on first run; all three install paths stay in scope; the README splits. **The blocker stated plainly: a stranger's container cannot index anything** -- no `index` subcommand exists, indexing is per-vendor so it needs a staged spec, and `prepare_vendor` reaches the network and shells out to `gh` which a fresh container has neither of. **Found while scoping: the README claimed the `npx` wrapper *is not built yet* and it has been built** -- `bin/sync-up.mjs` exists and `package.json` declares the bin, so the page new users land on was wrong about the shortest path to running it. Corrected, and the genuinely unverified part named instead: whether the published command resolves outside this checkout | landed | `docs/superpowers/plans/2026-08-18-beta-readiness.md`, `README.md` |


| CI-W436 | **Four revisions to the stream, three of which reverse what I built** -- recorded as reversals rather than reconciled quietly. **The heartbeat is an SSE comment again, and my own objection decided it**: a typed `heartbeat` puts something on the wire corresponding to nothing that happened, which is the property decision 84 says an event should have. The hook stops listening for it and now has two states rather than three -- an idle index and a healthy one look the same, which is correct, because reporting a difference it cannot observe is the invention the comment avoids. **The canvas builds visibly again**: an earlier pass let decision 87 govern a surface it was not written for -- 87 protects a reader *reading* a table, and this is one you are *watching build*. The banner accompanies and never replaces, and each arrival re-reads the settled graph so the picture grows from the same source of truth every other screen uses rather than a second one assembled off the wire. **A drop now offers a re-read the reader triggers**, because swapping a live view for a static one unasked would hide that the screen stopped being live. **Dismissal events emit now** -- the write path is in flight rather than anticipated, so this is not the dead usage `lib/motion.ts` recorded -- and a restore is its own kind rather than a dismissal carrying a null reason, since a console told only that *something changed* would have to re-read to learn which | landed | `src/sync/api/app.py`, `web/src/features/index-graph/` |
| CI-W412 | **Red main, and I caused it**: my merge loop staged six conflict-marked files with `git add -A` after resolving only WORKLOG -- 157 tsc errors. Repaired, and the loop now refuses to stage while any marker survives | claimed | `web/src/features/` |
| M14-W436 | **P0: every finding and vendor link in the console pointed at a route that no longer exists.** `M14-W386` scoped all ten routes under `/repositories/:repoId/`; twelve non-test link sites still built the old unscoped `/findings/{id}` and `/vendors/{id}` paths, and `App.tsx` has a `path="*"` catch-all with no legacy redirect -- so each one rendered *No screen at this address*. The build was green throughout, and so were 771 console tests: a `<Link to>` is a string, and nothing typechecks a string against a route table. Ten sites had `repoId` as a prop or a route param and are mechanical. Two did not and are not in this unit -- `runs-table` and `proposed-patch` link from a run, and `RunRow` carries no repository because `migration_outcome` stores none, so the destination is genuinely underdetermined. **The guard is the deliverable**, not the twelve edits: a link whose first path segment is not a declared route root now fails a test rather than a reader's click. **The guard found nineteen, not twelve** -- a whole class of `/bindings/vendors/{id}/operations/{id}` links in four more files, and a `/detectors?repo_id=` that the manual grep missed. Seventeen fixed here. `bindingSurfaceHref` existed as **four private copies of one function in four files**, which is why the route move found none of them; they are one `lib/hrefs` module now, tested against `ROUTES` with react-router's own matcher, so the next route move breaks one test instead of leaving readers in a 404. Four test files were **asserting the dead addresses** and passing -- `workflow-page.test.tsx` mounted the whole screen at a pattern the app does not route. Two show-alls fell out on the way: `ChangeUnitsTable`'s optional `repoId` and the scope trail's unscoped `useOverview()` | landed | `web/src/lib/hrefs.ts`, `tests/test_console_links_resolve.py`, 17 link sites |
| CI-W437 | **The four beta gates measured rather than asserted: 0 of 4 met, 2 cannot be told from here.** Gate 1 NOT MET (3 attempts, **0 pull requests that went green** -- `B7` has never passed). Gate 2 CANNOT TELL (0 of 5 axes have samples; unmeasured is absence, not zero). Gate 3 CANNOT TELL because **the last signature is older than the console it describes** -- signed 03:15, console changed 10:16, so the screens need walking again. Gate 4 NOT MET on 13 failures against 4,206 passes. **And Gate 4's failures are mostly not what they look like**: run in isolation, `test_codebase_index` passes alone and `test_sandbox_host_copy` passes alone, while `test_rehearse_boundary` fails alone too -- so the suite holds **genuine failures and tests that pass individually and fail together** under one number, which is interference through shared state rather than broken product code. The gate cannot tell those apart and neither could anyone reading *13 failed*. **Separating them turns Gate 4 from a wall into a list**, and the interference is by far the cheaper half. None of it argues for moving the gate: it is honestly NOT MET either way | landed | `docs/superpowers/plans/2026-08-18-beta-readiness.md` |
| CI-W438 | **A failing suite is a wall until you know which failures are real, and nothing here could tell.** `gate_verdict.py` already answers whether a verdict can be *believed* -- a dead worker's marks are absences wearing a failure's glyph -- and that is a different question from whether a failure is *genuine*. Three runs of one tree gave 7 failures, then 2, then a worker collection mismatch, and every lane reading that has to re-derive by hand which ones matter. `scripts/isolate_failures.py` re-runs each reported failure **alone** and splits them: fails alone is real, passes alone is interference through shared state. That is not a convenience -- it is the same distinction this repository enforces everywhere else, that a thing which could not be measured must not be reported as a thing that was. It found the shape already: the indexer's `_load_or_create_vendor_adapter` reads a **CWD-relative** cache path and silently substitutes a fallback adapter on any exception, so interference there does not raise -- it returns a different answer | claimed | `scripts/isolate_failures.py` |
| CI-W439 | **The git page split, owner-selected: 720 lines to 199.** A landing page that gets somebody running in **all three ways** -- `npx`, a checkout with Docker, and from source -- because the owner ruled all three stay supported rather than one being primary. The argument, the mechanism and the architecture move to `docs/why-sync.md`, `how-it-works.md`, `architecture.md` and `developing.md`, **verbatim rather than rewritten**: the honesty discipline is the product position and it relocates rather than being summarised away. **Three in-page anchors broke in the move and were caught before landing** -- they pointed at sections that now live under `docs/`, and a markdown link resolving to nothing is the same defect as a dead link in `src/` except that the gate catching those does not read markdown. Every link was walked, including the fragments inside the moved files | landed | `README.md`, `docs/` |
| CI-W440 | **`npx @superloglabs/sync` does not resolve for anybody outside this checkout, and now it is measured rather than unverified.** The registry answers **404**, and `package.json` carries **`"private": true`**, which forbids publication outright -- so this is not a step nobody has taken, it is a step the manifest currently refuses. The README hedged correctly (*what has not been verified is the published path*) and a hedge is the right thing to write before measuring and the wrong thing to leave after. **The line above it was the actual defect**: *three ways in, and all three are supported*, with `npx` first. One of the three is unavailable to a stranger, and decision 96 makes that the demo's opening line. Corrected to say what is true, with what it would take to make it true. **Guarded rather than just fixed**: a test now fails if the manifest is unpublishable while the README presents the command as a working way in -- the two can only drift apart silently, and the README is the page a stranger lands on | landed | `README.md`, `tests/test_install_paths_are_honest.py`, `tests/test_lint_dead_routes.py` |
| CI-W441 | **The front door told visitors to run a competitor's npm scope.** `README.md:48` printed `npx @superloglabs/sync` as the install command, and **superlog is a competitor we study in `docs/superpowers/references`** -- not our organisation. It could only ever 404 or install somebody else's package, and it attributed this product to them in the one file every packaging tool reads. **The origin is the instructive part**: the owner named superlog's install *pattern* as the model, and the literal org name travelled with it -- `interface-originality.md`'s take-the-concept-never-the-rendering failure, arriving through a manifest instead of a screen, where no design review would ever look. The command is removed from the README rather than reworded; the manifest rename and any publish are the owner's. **Guarded so it cannot return**: a test derives competitor names from the references directory itself and fails if any appears in `package.json`'s name -- self-maintaining, because studying a new competitor extends it without anybody remembering to | landed | `README.md`, `tests/test_install_paths_are_honest.py` |
| CI-W442 | **Three of Gate 4's last four failures were one moved section.** `test_day_one_path.py` reads the documented first run and holds it against the argparse surface -- it looked for `## Quick start` in `README.md`, and `CI-W435` turned the README into the install page and moved the developer path to `docs/developing.md`. **The failure mode is the interesting part: `str.index` raised `ValueError` rather than failing an assertion**, so three tests reported a crash where the honest message was *this section moved* -- a guard that cannot say what is wrong with it is most of the way to a guard nobody reads. Retargeted at the file that now holds the content, keeping every assertion: the first run still has to invoke commands the CLI actually declares, still has to name `gh`, `claude` and `npm` because a run shells out to all three, and the console block still has to install before it starts and seed before the API reads. **Nothing was weakened to make them pass** -- the content already satisfied all three where it now lives, which is why this is a retarget and not a rewrite | claimed | `tests/test_day_one_path.py` |
| M14-W443 | **`sync index --repo <path>` exists: the console can hold a stranger's code.** The beta-readiness blocker above all others -- `/api/repositories` answered `{"repo_ids":[]}` and no screen was at fault. The composition sat inside `run` and was never exposed; `run --repo` takes a git remote and clones it, needing `gh` and a credential, while somebody meeting Sync has a directory and neither. **Offline, no vendor staged, no network, no credential.** A vendor that cannot be resolved locally is skipped and named -- safe only because `M14-W433` deleted the stand-in that used to answer with invented operation ids, which would otherwise have filled a first-run graph with call sites bound to operations no vendor has. The pass is recorded through `index_run` whether it finishes or dies, so the Overview can state when the index last ran. **A defect the unit tests could not see:** five passed against a store double while the real command died on `relation "index_run" does not exist` -- a double answers whether or not the table is there, and this is the first command a new deployment runs. `apply_schema` added, and a test against a real database added beside the doubles. Verified end to end: a plain checkout indexes to 1 call site with a staged cache, and to 0 with an honest reason without one. `index_codebase` comes off the dead-link baseline in the commit that wires it | landed | `src/sync/cli.py`, `tests/test_cli_index_command.py` |
| M14-W444 | **The last two dead links, and one of them was dead code.** `M14-W436` left two links exempted because a run carries no repository -- `migration_outcome` stores none. `proposedPatchTarget` turned out to have **no caller at all**: the page-level *Review proposed patch* action it served was removed and the module outlived it, kept alive by nothing but its own test. Deleted, per *delete rather than deprecate* -- it is the `retracted_at` pattern exactly, a dead path that still typechecks and still gets read. The remaining one resolves the way the owner ruled: the run row asks `/api/findings/{id}` which workspace its finding belongs to and navigates with the answer, rather than assuming the workspace in the address -- which would render a finding under a workspace that does not contain it. `FindingIdentity.repo_id` is nullable, so a finding whose call site names no repository has no destination and says so instead of guessing. **The lookup was never needed, and my reason for exempting it was wrong.** Another lane's `M14-W438` had already fixed the run link, with the better diagnosis: `sync.dashboard.fleet._run_row` has **always** carried `repo_id`, and `types.ts` merely omitted the field -- so the console was building links without a value it was being sent. I had reasoned from `migration_outcome` storing no `repo_id` to *a run cannot know its workspace* without opening the reader that builds the row; the schema fact was right and the conclusion did not follow. So this unit deletes the dead module, deletes the exemption mechanism entirely rather than the two entries, and records the lesson in the guard: a guard is the wrong place to store a belief about why something cannot be fixed. **The console now has zero exempted links**, proven by planting one and watching it fail | landed | `tests/test_console_links_resolve.py`, `web/src/features/fleet/proposed-patch.ts` (deleted) |
| CI-W445 | **Decision 97's real cost, built first and separately: the process lifecycle.** Embedded Postgres makes a database *ours to own* -- start, stop, and the orphan a crash leaves behind -- and the owner named the failure precisely: **a Postgres left running makes the SECOND run worse than the first**, which is the run that happens on stage. `bin/embedded-postgres.mjs` decides, as pure functions with the probes injected: a live server of the right version is **adopted and said to be adopted**, never restarted and never reported as started; a live server of a different version is not ours to adopt and is reaped by name; a record with no process behind it is a crash that never cleaned up, and the next run says so rather than silently succeeding. Cache likewise -- 55MB is fetched once and a reuse **announces itself**, because a second run that silently re-downloads and a second run that silently reuses look identical until somebody is on a hotel connection. **No download and no Postgres in the tests**: every branch is reachable with an injected probe, which is the only way this is testable before Wednesday | claimed | `bin/embedded-postgres.mjs`, `tests/test_embedded_postgres.py` |
| CI-W446 | **Decision 98's bootstrap, decided the same way as 97: about what is already there.** `uv` fetching a pinned 3.12 is the easy half; the half that breaks a second run is a `uv`, a Python or a virtualenv the machine already has. **A virtualenv is reused only when the lockfile that built it is the lockfile in the tree** -- digests compared, never mtimes, because `CLAUDE.md` records that 184 of 200 identical-byte rewrites left `st_mtime_ns` untouched and a check written that way mostly does not check. Reusing a venv built from a different lock silently runs unpinned dependencies, which is the failure that produces a bug nobody can reproduce. **An interpreter of the wrong version is rebuilt rather than adopted**, because a pinned 3.12 is a guarantee this project already relies on. And **using a `uv` the machine already has is not installing one** -- the message says which, for the same reason adopting a Postgres is not starting one. No network in the tests: every branch is an injected probe | claimed | `bin/python-bootstrap.mjs`, `tests/test_python_bootstrap.py` |
| CI-W447 | **`dev_up` walked you into the sentence it exists to prevent.** `API_PORT` honours `SYNC_API_PORT`; the readiness URL was hardcoded to 8787. So following the script's own advice -- its busy-port message reads *set SYNC_API_PORT to a free port* -- moved the API and left the probe behind, and **the same message says a busy port means a readiness check would answer from whatever is already there**. That is then exactly what happens: the probe hits the old port, another lane's API answers it, and the stack reports ready on the strength of somebody else's server. **Found because it blocked my own Gate 3 walk** -- another lane genuinely held 8787 and the documented workaround was the trap. Now derived from `API_PORT` as a function rather than a constant, because `API_PORT` is read at import time and a constant beside it would freeze whichever value happened to be set first. Proven able to fail by restoring the hardcode | landed | `scripts/dev_up.py`, `tests/test_gate_dev_loop.py` |
| M14-W448 | **CLAIMING BEFORE BUILDING: the pinned vendor specification, staged offline (beta item 2).** `M14-W443` shipped `sync index --repo` and running it proved the gap exactly: a plain checkout indexes to **0 call sites** because no vendor cache is staged, and the reason printed is honest but the console still holds nothing. Item 2 closes it. **Measured before claiming:** `_load_stripe` needs only `<cache>/symbols.json` -- I verified directly that a directory holding just the symbol map loads, and that the spec files are not required for the load path. So the bake is a symbol map plus a record of which tag it came from and when, not a copy of a 15MB specification. `scripts/stage_symbol_map.py` already builds the map and pins it by digest across four tags, so this reuses it rather than writing a second staging path. **SPLIT, so this cannot collide:** I take the offline staging script and the version/date record, which are `scripts/` and `src/sync/signals/`. **The one Dockerfile line that invokes it is Lane C's** if they hold the image -- say so and I will hand it over ready to call | claimed | `scripts/`, `src/sync/signals/` |
| CI-W449 | **`npx sync --check`: what this machine needs, before anything is fetched or started.** `CI-W445` and `CI-W446` decided both lifecycles and nothing called either, which by the standing rule means neither shipped. This is their caller, and it is a real answer rather than a wiring exercise: it runs the probes it can honestly run -- is `uv` here and new enough, does a virtualenv exist and was it built from *this* lockfile, is a Postgres already recorded -- and prints what a zero-prerequisite install would do about each. **Every line says *would*, because none of it is done**: the download, the process spawn and the port bind are unwritten, and a check that reported them as steps taken would be the overstatement these modules were built to avoid. **It is also the honest form of the Wednesday list at machine scale** -- decision 99 forbids reporting anything working that has not run on a clean machine, and this is the thing a stranger can run to find out what their own machine still lacks | claimed | `bin/sync-up.mjs`, `tests/test_container_install.py` |
| CI-W450 | **Gate 3 not walked, and that is the answer rather than a delay.** The precondition question timed out unanswered after 900s, so the tree was measured instead of guessed, using the gate's own path spec: **four console changes in eighty-two minutes and a longest quiet gap of twenty-three**, against a twenty-five-minute bar chosen before the measurement and proposed in writing beforehand. There was no window in which a walk could start and finish against one tree. **The report is marked `Historical:` and carries no `Signed:` line**, so it cannot be read as a signature and Gate 3 stays `CANNOT TELL` -- unmeasured is a legitimate verdict and signing a partial tree is the failure this gate exists to catch. Everything except stillness was ready and is left running for a re-dispatch: API on 8811 and console on 5173 without touching the lane holding 8787, no seed run because 67 call sites were already there, real data, Chrome up. The binding surface stays recorded as **not verified rather than assumed to pass** | landed | `docs/superpowers/reports/2026-08-18-gate-3-not-walked.md` |
| CI-W451 | **The commands are ours to type: `npx sync-up` and a pnpm surface, made publishable and honest.** The name question the README recorded as open is settled by the owner's ruling: no scope, our own word -- the package takes the bin's name, `sync-up`, verified free on the registry, so the command and the package are one word and `npx sync-up` is the whole instruction. `private: true` stops being a guard against publishing under a name that was not ours and becomes the only thing between the manifest and `npm publish`. Flipped. `scripts` gains the pnpm surface a checkout can honestly offer today: `start`/`down`/`check` hand to the doorbell, `dev` to `scripts/dev_up.py`, reimplementing nothing -- `start` rather than `up` because `pnpm up` is pnpm's `update` builtin and ran it, measured by the `pnpm-lock.yaml` it left behind. And the registry gap is refused rather than discovered: the published tarball carries the compose file but not the tree it builds from, so a registry install dies mid-`docker build` on a missing `src/` -- `sourceTreeDiagnosis` now says plainly that no prebuilt image is published yet and prints the clone that works, before Docker is even probed. `B190` names what retires the refusal | landed | `package.json`, `bin/sync-up.mjs`, `tests/test_container_install.py`, `docs/superpowers/BACKLOG.md` |
| CI-W452 | **The Docker refusal learns to hand over a command, not only a URL.** Measured on the first fresh-clone run: the doorbell said Docker was missing and left the reader to a browser. Now `dockerInstallCommand` names the platform's own installer -- `winget` on Windows, `brew --cask` on macOS, and on Linux the convenience script is printed rather than piped, because a doorbell does not execute remote code the reader has not seen. The missing-Docker diagnosis prints that command inline, and `--install-docker` (surfaced as `npm run install-docker`) runs it where running is honest, with elevation left to the OS prompt. Pure function, probes injected, same testing shape as the diagnosis beside it | landed | `bin/sync-up.mjs`, `package.json`, `tests/test_container_install.py` |
| CI-W453 | **`--no-admin`: the install path for a machine where elevation is not available, measured into existence.** The owner's machine has no admin rights, so Docker, WSL2 and every VM-backed container runtime are closed -- and the owner proved the alternative by hand: portable Postgres 16.4 binaries in `~/.sync-postgres`, a cluster on 5433, `uv sync`, seed, `dev_up.py`. This turns that afternoon into one command. The decision layer was already built and tested (`embedded-postgres.mjs`, `python-bootstrap.mjs`, Decisions 97-99); this is their action layer, Windows-first: adopt a serving cluster (including one this installer never recorded -- `unrecordedClusterVerdict`, the case Decision 97's four did not cover), start a stopped one, or download the pinned binaries, initdb, start, seed once, and hand over to `dev_up.py` reimplementing nothing. The Docker refusal now offers it, because the reader most likely to hit that refusal is exactly the reader without admin. `uv` fetch-if-absent stays unbuilt and says so; `B191` carries it with macOS/Linux | landed | `bin/sync-up.mjs`, `package.json`, `tests/test_container_install.py`, `docs/superpowers/BACKLOG.md` |
| CI-W454 | **The embedded cluster is held to the shipped database settings, because the first full suite on it failed eight ways and five were one bug.** `initdb` inherits the machine's timezone; the compose image runs UTC; so timestamptz views serialized `-05:00` renderings of instants that were correct, and four `test_graph_views` cases plus the reconcile timestamp test failed on string comparisons of equal moments. The suite also crawled on `DataFileImmediateSync` -- full durability on data both compose files deliberately trade for speed because a seed rebuilds it. `parityStatements()` pins timezone, `fsync` and `synchronous_commit`, applied idempotently on every `--no-admin` run, adopted or fresh. The other three failures were guards meeting a machine they had not met: the skip baseline collapsed into the shared `requires_node` marker its own docstring recorded as owed (count 20 -> 17, narrative moved with it), and the Docker positive control now skips naming the toolchain a no-admin Windows machine can never have. Confirmed by the full suite: 8 failed / 4261 passed before, **1 failed / 4268 passed / 36 skipped in 3:36 after**, and the one is `test_leaked_database_sweep` interference -- passes alone (20/20), fails under the parallel suite, the exact shape the beta plan already records | landed | `bin/sync-up.mjs`, `tests/` |
| CI-W455 | **The README comes down to one page, and nothing was deleted -- it was moved.** Beta item 5, on the owner's direction: the landing page runs it and links out. The duplicated second quickstart collapses into the first (its measured timings, the prebuild tip, the loopback posture and the comes-up-empty caveat each keep one line); the journey and the full M0 status with its three qualifications move verbatim into `docs/why-sync.md`, which the status section and Read further now point at. The install-honesty guard held throughout -- it caught the not-published phrase wrapping across a line break before the page shipped claiming less than it says | landed | `README.md`, `docs/why-sync.md` |
| CI-W456 | **The one command is printed as the goal, on the owner's ruling.** The README now leads its one-command section with the fenced `npx` block under a heading that says *the goal, and it does not work yet* -- the destination stated as a destination. The guard that used to forbid printing an unpublished command changes jobs rather than dying: it now enforces the pairing, failing if the command appears while the not-published claim stands and nothing in the same section says so in plain words. Proven able to fail by removing the heading's status clause and watching it go red before trusting it. Publishing retires both halves in one edit | landed | `README.md`, `tests/test_install_paths_are_honest.py` |
| CI-W457 | **The two reference surfaces that were built and never mounted reach their screens, with the API growing what honesty required.** `FilterRail` and `TriageTabs` (M14-W377) existed as components and no page rendered either. The rail lands on Runs -- and because its counts must describe what a selection would return rather than the page in view, `/api/runs` grows an `outcome` filter plus `unfiltered_total`, with `by_disposition` (already computed fleet-wide) finally consumed instead of the page-only tally whose caption claimed the payload could not answer it. The tabs land on Findings, where the severity narrowing was a URL parameter with no control: one tab per kind in the payload's own order, counted over the scope, empty states naming the detectors behind a measured zero, and the severity filter finally clearing the offset it invalidates. The sidebar's "read-only until the write path lands" note stops contradicting the settings screen that saves. Owner-directed build phase: no new tests this pass, compile-checked both sides | landed | `src/sync/dashboard/fleet.py`, `src/sync/api/`, `web/src/` |
| CI-W458 | **The symmetry pass: one page rhythm, paired cards at one height, a centred content column.** A full front-end sweep found the console split down the middle on page rhythm -- seven screens spaced their panels at the recorded 32px page gap and six at the 16px in-panel token, so panels sat twice as close on some screens as on others for no reason a reader could see. Normalised to the recorded gap everywhere. Paired grid cards stretched to one height (`items-start` dropped where it fought the pairing, `h-full`/`flex-1` threaded through `MetricPanel`, the two runs charts put on one chart height), because two panels in one row at two heights read as a mistake rather than as two answers. The routed screen now renders in a centred column capped at 1400px -- a page-layout number argued in `app-frame.tsx`, inert at the 1440x900 reference size -- so wide monitors stop showing every page hugging the sidebar. Two structural repairs rode along: the two newest pages had reintroduced the breadcrumb-under-the-bar repetition `M7-W195` removed from five others, trimmed the same way; and `ObservedTelemetryCard` moved out of a 342-line `codebase-page.tsx` into `features/telemetry/`, where its subject lives. One off-scale spacing value (`pt-3`) moved onto the token it duplicated. Owner-directed build phase: compile-checked, no new tests | landed | `web/src/` |
| CI-W459 | **`npx sync-up` is real: the package is published, and the two defects the first outside-the-checkout run found are fixed.** The registry 404 was the owner running the command the README promises; the name was unclaimed, so `sync-up@0.1.0` now resolves for a stranger. Verifying the tarball before publishing found both defects in front of exactly the reader the doorbell protects: the source-tree refusal handed over `npm run up`, a script `package.json` deliberately does not define (`pnpm up` is pnpm's `update` builtin -- the same file's own test forbids it), so the one command a registry reader is given died on `Missing script`; and the extractor was bare `tar` resolved from PATH, where a Git Bash environment puts GNU tar first, which parses a `C:\` archive path as a remote hostname (`Cannot connect to C: resolve failed`) and cannot read zip at all. The refusal now hands over `npm start`, held by a test that resolves every command the message prints against the scripts `package.json` defines; the extractor is System32's bsdtar named absolutely (`tarExecutable`), PATH only as fallback, which is also what un-blocked the first `--no-admin` install on this machine | landed | `bin/sync-up.mjs`, `tests/test_container_install.py` |
| CI-W460 | **Explanation on demand: the (i) hint, real buttons, and Settings gains the Pages guide.** Owner direction: the reader is here for their own data, so how-this-panel-works prose moves behind a hover and the long form moves into Settings. `InfoHint` is the primitive -- a focusable trigger so the keyboard path exists, tooltip content at body type -- and `MetricPanel`/`TelemetrySection` grew a `hint` slot beside their headings. Findings, Signals, Observed telemetry and the Overview chrome moved their captions across; sentence-embedded route links became outline buttons (Open Signals, Vendors attached, Signals for this repository). **The boundary held rather than bent: no protected honesty sentence, count scope, or absence-versus-zero distinction moved into a tooltip** -- the thrice-recorded ruling bars disclosures, so those stay in front of the data and the hints carry only exposition. Settings -> Pages is the new home for every screen's full account | landed | `web/src/` |
| CI-W461 | **The console knows which codebase it was installed beside, and Setup lives on the dashboard.** The install story is one command run inside a codebase, so a launched console should not talk about "repository" in the abstract: when the graph holds exactly one, the sidebar binds every destination through it -- a reader is never asked to choose among one, while several keep the picker because choosing among several is the operator's act -- and the chrome names the workspace in mono under the wordmark. The Overview gains a Setup card stating the workspace identity with three acts as buttons routed to the Settings groups that already own them: Connect to Git, Manage codebases, How these pages work. No invented connection status -- the card states identity and routes to configuration, because a second place to configure a thing is a place for two to disagree | landed | `web/src/layouts/app-frame.tsx`, `web/src/features/repositories/codebase-page.tsx` |
| CI-W462 | **The stopped-daemon refusal offers the no-admin route, because the first fresh-clone `npm start` dead-ended on it.** `CI-W453` put the offer in the Docker-missing branch on the rationale that the reader most likely to meet a Docker refusal is exactly the reader without admin -- and that rationale binds the stopped-daemon branch identically, where it was missing. On the no-admin machine the fresh clone hit that branch and was told to start a Desktop that elevation forbids, with no mention that the user-space route exists. Both refusals now name it, held by a parametrized executed test over every not-ok `dockerDiagnosis` verdict | landed | `bin/sync-up.mjs`, `tests/test_container_install.py` |
| CI-W463 | **Setup measures the full loop: six prerequisites probed, and the git remote becomes a stored fact.** The loop is index -> detect -> remediate -> verify -> pull request, and a fresh install had no screen saying which of its prerequisites stood. `/api/setup` probes them at request time -- codebase indexed, vendor specification staged (with its tag), `gh` present and authenticated, `claude` on PATH, git remote recorded, merge policy in force -- and each item answers `ready`, `missing` with the fix named, or `unanswered` when the probe itself failed, three states nothing sums, because a figure over them would average could-not-check onto checked-and-missing. `repo_settings` gains `remote_url` (schema with the idempotent ALTER for databases that predate it, model, store, writer, and the same path-refusal at the API that `sync run` makes at the CLI), editable inline on the new Settings -> Setup group, which leads the nav amending decision 17 -- setup precedes what setup enables. The dashboard's card routes to it. Probed live: five of six ready on this machine, the remote honestly missing | landed | `src/sync/`, `web/src/features/settings/` |
| CI-W464 | **Plain `npm start` routes instead of refusing, and the one command finishes its own setup.** Owner ruling 2026-08-18: everything is set from `npm start`, the person never runs a Docker chore. `startRoute` decides: a serving daemon keeps the container path, because the container is the artifact; an unusable Docker on a platform with the user-space route falls through to it automatically, carrying the Docker diagnosis so a reader who wanted the container knows what to start; only a platform with neither gets a refusal. `npm run down` on that route stops the embedded cluster and keeps its data. And the last assembly step a fresh clone still asked a person to do is gone: `consoleDependenciesVerdict` installs `web/node_modules` when absent, decided the same way as the venv and the cluster (spawned through a shell on Windows, where npm is a `.cmd` Node refuses without one). Proven live: plain start on the no-admin machine adopted the serving cluster and reached API 8787 and console 5173 with nothing left to figure out | landed | `bin/sync-up.mjs`, `tests/test_container_install.py` |
| CI-W465 | **The integration surface widens on evidence, and one repository stops being three.** Nine generated-tier vendors verified live on 2026-08-18 and added to `generated-vendors.yaml` -- modern-treasury, lithic, increase, finch, orb, groq, openlayer, browserbase (Stainless) and mistral (the second Speakeasy vendor) -- each with its manifest and pyproject fetched and committed as fixtures, Python-only bindings because a binding nobody checked is worse than none. Twilio is baked at last: 228 symbols across messaging v1, verify v2, conversations v1 and lookups v2 at a pinned `twilio-oai` commit, with the legacy v2010 collision recorded as `B193` rather than papered over. And the first dogfood run exposed identity drift -- `sync index` derived repo_id from the package name while `run` derived it from the remote, three identities for this one repository -- so `remote_repo_id` moved to `sync.index.codebase` and the checkout's own origin now decides, package and directory names falling back only where no forge-addressable origin exists. `B192` records the TS7/nested-tsconfig baseline abandon the run surfaced | landed | `generated-vendors.yaml`, `vendor-cache/twilio/`, `src/sync/index/codebase.py`, `src/sync/cli.py`, `tests/fixtures/` |
| CI-W467 | **The bring-up freshens the checkout, and the console dependencies follow the lockfile.** Owner ruling 2026-08-18: the build commands always build the most recent code. `updateVerdict` automates the one case automation cannot lose work in -- clean and only behind fast-forwards on its own -- and leaves the rest a person's: local changes are never pulled over, a divergence is named rather than resolved, an unreachable origin is stated and stepped past. Every branch prints its decision, because five dev servers once ran stale here and nothing said so. `consoleDependenciesVerdict` stops meaning merely present: it compares the web lockfile digest against the install record (never an mtime, per the rule this file already carries), so a pull that changes `package-lock.json` reinstalls on the next start, and the record catches up only after the install succeeds. Proven live: a scratch clone one commit behind fast-forwarded itself on plain start | landed | `bin/sync-up.mjs`, `tests/test_container_install.py` |
| CI-W468 | **B194 and B195 built: runs get a heartbeat, and adapters declare their staging as a schema.** The heartbeat is the reference read's best idea made ours: `run_heartbeat` (grain: one row per checkpoint thread) with three ends that are different facts -- `stopped_at` a clean exit, `expired_at` the sweep's recorded transition when heartbeats stop without one, neither a process alive as of its last tick. The runner ticks on a timer thread with its own connection, straight through `await_ci`, because the heartbeat measures the process rather than progress; the sweep is read-triggered because a local-first deployment owns no supervisor. `/api/runs` rows carry `liveness` (alive / expired / unmonitored, null on terminal) and the console renders the word as a chip -- the protected staleness paragraph amended to stay true rather than deleted, saying exactly how far the new signal reaches. B195: `sync.signals.staging` declares typed fields per adapter, `/api/adapters/{vendor}/staging` reads and writes them, and one schema-driven renderer draws every form -- Twilio's product list editable from Settings with no Twilio-specific component, the write answering `stale_symbols` when the list drifts from what the bake covered | landed | `src/sync/graph/`, `src/sync/signals/staging.py`, `src/sync/api/`, `src/sync/dashboard/fleet.py`, `src/sync/cli.py`, `web/src/` |
| CI-W469 | **B192 closed: the typecheck baseline survives TypeScript 7 and nested projects, proven on the repository that abandoned.** Two causes, both fixed at the invocation: `typescript@latest` had drifted to TS 7, whose CLI answers a missing project with help text the parser reads as a broken compiler -- pinned to `typescript@5`, because a major is a CLI contract and adopting a new one is a deliberate act; and the baseline pointed at a root with no `tsconfig.json` -- `_project_dir` now resolves the nearest project (root, then depth two, `node_modules` excluded, deterministic), the compiler nearest the project wins, `-p` names it explicitly, and a repository with no project is refused in a sentence. The resolve marker carries the pinned major so moving the pin re-resolves. Measured: `run_tsc(".")` resolves `web`, runs its own tsc, returns ok -- the first remediation blocker on this repository is gone. B121 closed by inspection alongside | landed | `src/sync/index/tsc.py`, `docs/superpowers/BACKLOG.md` |
| CI-W470 | **An adopted database is held to the shipped schema, because the cluster outlives every checkout.** The first fresh clone after `run_heartbeat` landed adopted the machine-wide cluster and met a database created before that table existed: every precondition green except `schema: 1 table(s) absent`, and the named fix was `seed_console.py` -- which would also write fixture rows into a database whose rows the doorbell had just promised to keep. `scripts/apply_schema.py` is the schema-only half: `GraphStore.apply_schema` converges tables and constraints and touches no rows, the doorbell runs it on every adoption beside the settings parity step, and `dev_up` names it as the fix for schema drift instead of the seeding script. Its test suite covers the drift, the no-op, and standalone execution -- the first live run died on a `sys.path` difference between pytest and `python scripts/...`, so that difference is now a test. Proven live: the shared cluster gained `run_heartbeat` with rows untouched | landed | `scripts/apply_schema.py`, `scripts/dev_up.py`, `bin/sync-up.mjs`, `tests/test_apply_schema.py` |
| CI-W471 | **Three owner directives land in the chassis and the Overview: the environment top-left, the account bottom-left, and Getting Started first.** The setup probe now names who the forge credential speaks as (`operator.forge_login`, parsed from the one `gh auth status` the checklist already runs -- one probe, two answers), and the chassis renders both identity facts: an Environment block under the wordmark saying `local dev - git: <login>` and linking to Connections, and the pinned bottom utility bar the sidebar brief named and nothing had built -- the account row bottom-left with Settings beside it, the mid-list Deployment group deleted rather than kept as a second route to one screen. The Overview now leads with Getting Started: the workspace identity, the six prerequisites with their probed state words and fix commands, the three doorway buttons -- and it stays when everything is ready, saying so in one line, because a region that vanishes on success teaches an operator the page is unpredictable | landed | `src/sync/dashboard/setup.py`, `web/src/layouts/app-frame.tsx`, `web/src/features/repositories/getting-started-card.tsx` |
| CI-W472 | **One Overview, parallel chassis lines, and the scope trail comes out.** The owner measured three defects in one look: the sidebar header stacked ad-hoc rows and its hairline stopped meeting the top bar's, the fleet screen and the codebase screen were both answering as Overview from two addresses, and the trail's "Repositories" and the sidebar's "Overview" landed on different pages. Fixed structurally: the wordmark row is exactly the top bar's 48px with the shared hairline so the chassis line is continuous; the environment block sits under it in its own bordered section, every line truncating rather than wrapping; the fleet screen redirects to the codebase overview while exactly one codebase exists (the chooser returns the moment a second does); the dependency-graph panel moves to the one Overview rather than becoming unreachable behind the skipped screen; and the scope trail is removed on the owner's direction, its replacement to be designed from the new workflows rather than patched | landed | `web/src/layouts/app-frame.tsx`, `web/src/features/fleet/fleet-page.tsx`, `web/src/features/repositories/codebase-page.tsx` |
| CI-W473 | **The technical census reaches the Overview, and the chassis takes the owner's two touch-ups.** Build-versus-buy recorded first (`references/notes/codebase-facts-tooling.md`): linguist, tokei, scc, pygount and cloc all skipped -- a dependency or a binary for work the index already pays for, cloc GPL-poisoned outright -- with onefetch's card composition taken as the one idea. `sync.index.facts` measures with its method stated per figure: `git ls-files` as the census, newline counts over bytes, the intake's own manifest parse so two screens cannot disagree, git's own history. Stored in `codebase_facts` (grain: one row per repository, converged) with the index pass, served at `/api/repositories/{id}/facts` where null is an answer and never a 404, rendered by `CodebaseFactsCard` -- measured live: 1,561 files, Python 138.8k lines, 2,172 commits, 3 contributors. Chassis: the account row stops pretending an account page exists (identity, not navigation -- the owner caught it landing on Settings), and every header block moves onto the 16px left edge the destination rows sit on, so the sidebar is one grid | landed | `src/sync/index/facts.py`, `src/sync/graph/`, `src/sync/api/`, `web/src/` |
| CI-W474 | **The cross gets its quadrants, and the graph button leaves the rail.** The owner's geometry, implemented literally: the sidebar border and the top bar border form a cross, the environment lives ABOVE the horizontal line inside the 48px top-left cell -- wordmark and the `local dev - git: <login>` link as two compact truncating lines, the workspace riding the cell's title because three lines do not fit in 48px and the Overview names it in full -- and the destination buttons start AT the line, so nothing above can ever shift them again. The dependency-graph rail button goes `nav: false` rather than deleted: the Overview draws the graph panel itself, so the rail entry was a second door to a screen one click away, and the route stays for the panel's own link and the palette | landed | `web/src/layouts/app-frame.tsx`, `web/src/lib/routes.ts` |
| CI-W475 | **The owner's naming scheme lands at the presentation layer: Logs, Metrics, Integrations, Connections.** Runs presents as Logs (one row per attempt is the pipeline's own log), Findings as Metrics (the measured state of the workspace), each with its own rail entry and page by the amended ruling; the vendors list presents as Integrations and the services list as Connections, with their questions reworded to match. **The layering is the fleet screen's own precedent, applied deliberately:** reader-facing labels rename freely, while `GRAPH_LEVELS` keeps the specification's words (`console-hierarchy.md` binds them to the spec's fenced block) and the storage and plugin vocabulary -- `vendor_id`, `VendorAdapter`, `finding` -- keeps the domain's, because renaming a third-party adapter surface and a schema is a breaking migration that gets its own decision, not a label pass. The Pages guide titles follow | landed | `web/src/lib/routes.ts`, `web/src/features/` |
| CI-W476 | **The chassis takes its logo, the cross fills its quadrants, and two pages the rail was missing get built.** A drawn `SyncMark` -- two arcs closing a loop between terminal nodes, ours per `interface-originality.md`, `currentColor` at every size -- replaces the wordmark-plus-"console" pair in the top-left cell, and the environment moves to the cross's top-right where the top bar owns it: workspace, `local dev`, and the forge credential as one truncating link into Connections, both sides reading one `useChassisIdentity` hook so they cannot disagree. The rail stops grouping by level and takes a declared `navOrder` -- Overview, Findings, Integrations, Connections, Logs, Metrics, Solutions, Signals, Detectors -- because the reading order is a product decision rather than an accident of registry position, and an entry without one sorts last rather than silently. Two new screens: **Metrics** (the charts, composed from cards that already carry their own scope statements) and **Solutions** (every run that reached the forge, reusing the `outcome=opened` filter built for Logs so the two lists cannot disagree, each row opening the run's workflow and its pull request). Both are aggregates, so `GRAPH_LEVELS` is untouched | landed | `web/src/layouts/app-frame.tsx`, `web/src/lib/routes.ts`, `web/src/features/dashboards/metrics-page.tsx`, `web/src/features/workflows/solutions-page.tsx` |
| CI-W477 | **The call-sites browser: the graph's raw material, browsable at last.** Every other screen shows what Sync concluded; nothing showed what it *read*, which the owner named as the biggest remaining gap. `GraphStore.call_sites_page` is the new read -- bounded page, vendor facet, path prefix, retracted rows excluded as everywhere -- with **the facet counted without its own filter applied**, the rule the rail states on screen and the reason an option list does not collapse to whatever is already selected. Served at `/api/repositories/{id}/call-sites`, filters passed through unvalidated so a stale bookmark gets an empty page rather than an error screen, instants rendered in the store so one spelling reaches every reader. The page pairs the FilterRail with a typed table -- file:line:col, symbol, integration, operation linking into the binding surface, and loop depth with the sentence that says what a depth means. **No rung column, stated as a fact rather than left absent:** a rung describes a binding and `call_site` carries none, so rendering one would invent an attribution the rung exists to prevent. Measured live: 165 call sites, 110 stripe, 43 anthropic, 12 openai | landed | `src/sync/graph/store.py`, `src/sync/api/`, `web/src/features/bindings/call-sites-page.tsx`, `web/src/lib/routes.ts` |
| CI-W478 | **The integration-changes feed, the IA consolidation behind it, and two graph fixes.** `vendor_changes_page` serves every change the graph holds -- 8,723 across four vendors here -- with vendor and severity facets each counted without its own filter applied, at `/api/integration-changes`, and the screen states two things the data requires: **a change is a fact about the vendor, not about this codebase** (it becomes one where a call site binds, which is a finding), and oasdiff-sourced rows are at-least-once rather than converged, per `CLAUDE.md`'s named exemption. **Ten rail entries became seven** on the owner's ruling: Overview, Metrics (Findings / Detectors / Trends), Call sites, Integrations (Integrations / Changes), Connections, Logs (Runs / Signals), Solutions -- grouped by what kind of data each screen holds, with `PageTabs` joining each group as real routes so every tab is shareable and the router mounts one screen rather than four. **The graph stops opening illegibly:** `readableViewport` frames a large tree at the scale where a row still reads (ten pixels, measured against the three this codebase's 165 sites produced when fitted), anchored top-left because a file tree is read downward, with the whole-tree fit one button away and the clipping stated on screen. Sidebar rows gain their top padding so the first button no longer meets the header hairline | landed | `src/sync/graph/store.py`, `src/sync/api/`, `web/src/` |
| CI-W479 | **The rail order takes the owner's amendment: Metrics and Call sites move below Connections.** Overview, Integrations, Connections, Metrics, Call sites, Logs, Solutions -- the integrations a codebase uses and what it is connected to now precede what has been measured about it, which is the reading order of somebody checking their setup before their findings. `navOrder` carried the change and the type's own docstring was amended with it, so the declared order and the rendered one cannot drift. Two comments displaced by the changes-feed insert were returned to the entries they describe | landed | `web/src/lib/routes.ts` |
| CI-W480 | **The graph rebuilt on how the field actually draws large codebases.** Surveyed first (`references/notes/codebase-graph-ui.md`): repo-visualizer, Sourcetrail, xyflow, Cytoscape and elkjs, with licenses stated -- Sourcetrail GPL and elkjs EPL are ideas-only, Cytoscape and d3 are dependencies for work already done, and what every one of them shares is the thing ours lacked. **Three fixes, each the field's own answer.** Zoom was capped at `fit / 4` -- a limit that *scaled with the problem*, so a large codebase could never reach a legible scale at all; it is now expressed in pixels per row, so "as far in as is useful" means the same on any codebase. The tree aggregates: past forty call sites it opens folded below the first level, each folded folder carrying the count it stands for and expanding on click, **with bindings re-attached to the nearest visible ancestor** -- folding changes the picture's resolution and never its claims, which is what separates it from hiding rows. And every control moved inside the card, floating over the canvas with the minimap opposite, on the owner's instruction and the convention every node canvas follows | landed | `web/src/features/index-graph/`, `docs/superpowers/references/notes/codebase-graph-ui.md` |
| CI-W481 | **API topology on the Overview, and the integrations catalogue in Settings -- both from what Sync already reads.** Surveyed the scanning field first (`references/notes/code-metrics-tooling.md`): lizard and radon are candidates whose numbers tree-sitter already reaches, ruff and eslint are the customer's own thresholds and not ours to read, bandit and semgrep are a second product wearing this one's chrome, and the OSV family is the strongest fit and the one that needs a ruling -- `B196`. **What shipped instead is not a compromise:** `api_topology` is four `GROUP BY`s over call sites the index already wrote -- surface width, concentration (the operations reached from most files), coupling (files calling more than one integration), and calls inside loops. Measured live: 165 sites, 45 operations, 109 files, `PostCharges` reached from 96, one quadratic call. **`loop_depth` is the complexity signal nobody else on that list holds** -- per call site, at the API boundary, labelled static evidence. No maintainability index, no security grade: each is a composite this console refuses. The catalogue lists all 15 registered integrations with three honest states -- watched, staged, available -- and **no connect button, because Sync holds no vendor credential and never calls a vendor**; each row says what it would actually take instead | landed | `src/sync/graph/store.py`, `src/sync/dashboard/catalog.py`, `src/sync/api/`, `web/src/` |
| CI-W482 | **d3 arrives where it wins, and nowhere else: the codebase map is force-directed, and colour gets a scale.** The console charts with ECharts and **keeps charting with ECharts** -- a stacked bar in raw d3 is hand-written axes, legends, tooltips and responsive behaviour a chart library already gives, and two charting stacks is one fact written twice. What d3 is uniquely right for is the bespoke layout nothing off the shelf draws: `d3-force` lays out files -> operations -> integrations, `d3-zoom` owns pan and zoom (wheel, pinch, double-click, all correct without hand-rolled pointer arithmetic), five modules rather than the library. **The simulation is settled before the first paint** -- `stop()` then a tick loop -- which makes the map deterministic (the same codebase draws the same map twice, so two visits are comparable) and means there is no arrival animation to gate under reduced motion. **On colour, `DESIGN.md` stays the authority and d3 becomes the mechanism:** the eight series slots were already CVD-scored across all eight orderings and contrast-measured, so replacing them with a stock scheme would trade validated work for a default. `lib/palette.ts` binds them to an ordinal scale with a sorted domain -- a vendor wears one colour on every screen and on every visit, a ninth folds to `other` rather than cycling -- and `contrastRatio` derives the arithmetic `DESIGN.md` states, so the table cannot drift from the tokens. Colour on the map carries integration identity and nothing else: a file belongs to no single vendor and stays ink, and the rung stays a word | landed | `web/src/features/index-graph/force-map.tsx`, `web/src/lib/palette.ts`, `web/package.json` |
| CI-W483 | **Both codebase views are d3 now, the zoom actually binds, and the full graph takes the page.** Three defects the owner found, each real. **Zoom did not work at all, and the cause is worth naming:** the effect that binds `d3-zoom` ran once on mount, when the component was still rendering its settling placeholder rather than the svg -- `svgRef.current` was null, the behaviour bound to nothing. An effect reaching for a ref must run when that ref is filled. It is keyed on the settled layout now, the opening frame is applied *through* the behaviour so d3's notion of the current transform matches the screen (set in state alone, the first wheel tick jumped back to identity), and the buttons drive `scaleBy` so wheel and button share one transform. **Scaling was wrong because the simulation has no bounds** -- forces balance wherever they balance, regularly outside a fixed viewBox -- so `fitTransform` measures what settled, pads for the labels that hang past a node's radius, and frames it. **The file tree is d3 too**: `d3-hierarchy`'s tidy layout replaces the hand-rolled fixed-indent stack, `nodeSize` rather than `size` so a deep repository grows instead of being squeezed into sub-pixel spacing, the same zoom and the same fold rule, and the same vendor colour scale as the map and the charts. The full-graph route fills the viewport, which is the reason that route exists | landed | `web/src/features/index-graph/` |
| CI-W484 | **The tree's level of detail is derived from the window, which is the owner's principle rather than a bigger fold.** What shipped before folded to a *fixed depth*, so a large codebase drew six nodes -- the "one tiny component" reported -- while a small one drew everything; neither filled the picture it was given, and a constant cannot, because the two inputs it ignores are the codebase's shape and the reader's window. Now the canvas measures the height it actually renders at through a `ResizeObserver` (the page-filling route and the 44rem card are different budgets, and a split screen is a third), `nodeBudget` turns that height into how many rows can be drawn and still read, and `autoFold` opens directories **by descending call-site weight** until the budget is spent. The ordering is the argument: the directories a reader wants open are the ones their code calls integrations from, and weight is where those are. A directory that would overrun the budget stays folded carrying its count -- summarised rather than hidden, one click from open -- and the fold becomes the reader's the moment they touch it, with *Fit to window* handing it back | landed | `web/src/features/index-graph/tree-map-d3.tsx` |
| CI-W485 | **The dashboard catalogue for every page, and the skeleton the owner ruled: strip, grid, table.** `2026-08-19-dashboards-every-page.md` goes through all eleven screens -- what each renders today, what it should render, and the source behind every proposal, so nothing on the list is speculative. **The licensing question was measured rather than assumed:** the owner supplied NextAdmin's repository, and it reports `license: null` with no LICENSE file, which under default copyright is all-rights-reserved -- public and readable is not licensed. Conventions transfer, code does not, and that is the standard the Supabase carve-out met (Apache-2.0, attributed in `web/NOTICE`) and this cannot. Built: `KpiStrip` over the existing `FactTile` -- three or four tiles because five leaves a widow on the second row, `auto-rows-fr` so a wrapping note cannot make one tile taller than its neighbours, and the rule that a tile may not restate its own table's footer at the same weight (`corpus-chart.tsx` records two figures deleted for exactly that). `RankedBars` is the shape six proposed dashboards share, in SVG rather than the chart engine because a bar row is three numbers and anything with an axis belongs in ECharts. Connections and Solutions -- the two pages with no visuals at all -- now open with their facts | landed | `docs/superpowers/plans/2026-08-19-dashboards-every-page.md`, `web/src/components/kpi-strip.tsx`, `web/src/components/ranked-bars.tsx` |
| CI-W486 | **Two maps on the Overview, each opening its own subject page -- and that is what un-crowds the Overview rather than a trim.** The owner's ruling: a codebase has two shapes worth seeing, what it *calls* and how it is *laid out*, and neither summarises the other, so both render side by side at one height and each opens full screen. **The analytics moved with them**: the topology figures follow the integration map to `/graph`, the technical census follows the file tree to the new `/file-tree`, and each page becomes a subject instead of the Overview becoming a scroll. The Overview keeps a KPI strip -- strip only, by the same ruling, with bindings-by-rung left on Detectors where it is built rather than drawn twice -- and its four tiles read queries the page already issues, deduped on the key, so the strip costs no request. One read feeds both previews for the same reason. Neither map page is in the rail: the Overview shows both and each is one click away, so a rail entry would be a third door | landed | `web/src/features/index-graph/map-previews.tsx`, `file-tree-page.tsx`, `web/src/features/repositories/overview-kpis.tsx`, `web/src/lib/routes.ts` |
| CI-W487 | **The Overview's header opened the page fourth, and one region on it was a second door.** `PageHeader` and the `ControlBar` rendered below Getting Started, the KPI strip and both maps, so everything above them was unlabelled and unscoped -- on the one screen a workspace opens on, and the only screen in the console where the header was not first. Moved to the top. `VendorsListLink` retired with it: it existed because the rail rendered Integrations as unlinkable text until an address bound `repoId`, and the rail now carries Integrations at `navOrder: 2` and this route binds it, so the button pointed two rows away in the persistent navigation. Its guard was retired with its subject rather than deleted quietly, with the stale condition recorded in the file. **`ChangeUnitsTable` and `ObservedTelemetryCard` were proposed for the same cut and kept:** the Overview is their only mount, so cutting them would delete their protected sentences from the console rather than move them -- they move when they have a destination | landed | `web/src/features/repositories/codebase-page.tsx`, `codebase-page.test.tsx` |
| CI-W488 | **The integration catalog, generated from the registry so it cannot lie, and the getting-started journey that ends in a closed loop.** Nango's documentation shape carried by Sync's truth standard, with the licensing ruling recorded first: Nango is ELv2, so the shape and third-party facts transfer and nothing is copied (`plans/2026-08-18-integration-catalog-and-getting-started.md`). `vendor-catalog.yaml` holds display facts, and packages only for vendors nothing watches yet; *supported* is derived from `registered_adapters()` at generation time and a registered vendor's packages come from the registry -- a fact written twice will disagree with itself, and the test enforces both. `scripts/build_integration_docs.py` writes 40 vendor pages (15 supported, 25 recognized incl. the owner-priority dev-tools slate), the index, and `docs/llms.txt`; `tests/test_integration_catalog.py` is the drift gate. `docs/getting-started.md` carries bring-up -> index -> vendor -> rehearse -> the credentialed loop -> what the meter cannot tell; README brought back to tonight's truth. Also strips the UTF-8 BOM CI-W481 committed into `src/sync/api/__main__.py`, which crashed the encoding lint for every lane | landed | `vendor-catalog.yaml`, `scripts/build_integration_docs.py`, `docs/integrations/catalog/`, `docs/getting-started.md`, `docs/llms.txt`, `tests/test_integration_catalog.py`, `README.md` |
| CI-W489 | **The Dev Tools sweep: 49 registry-verified vendors join the catalog, 4 promotion candidates staged, 27 drops named.** Seven workflow agents took the owner's Dev Tools list (76 names after normalization), and every shipped fact carries probe evidence: packages verified against npm/PyPI (first-party only -- community wrappers and squatted names were rejected with the maintainer named), generator manifests probed in official SDK repos via the GitHub API. The catalog now renders 89 vendors, 15 supported and 74 recognized. `vendor-promotions.yaml` stages the manifest hits for the owner's one-look review before any joins `generated-vendors.yaml` (owner ruling: promote behind review) -- two Stainless, one Speakeasy, and one Fern, which is evidence of a third generator kind worth an extractor of its own someday. The 27 drops are recorded with reasons rather than silently absent: enterprise appliances without SDKs, agent products whose packages are the agent rather than an API client, placeholders and impostors. `scripts/merge_vendor_sweep.py` is the fold; the catalog drift gate held throughout | landed | `vendor-catalog.yaml`, `vendor-promotions.yaml`, `scripts/merge_vendor_sweep.py`, `docs/integrations/catalog/` |
| CI-W490 | **The `speakeasy-python` extractor: the fourth symbol rule, read out of Speakeasy's Python emission.** Built against `mistralai/client-python` (read, not vendored -- the fixtures are handwritten minimal emissions, provenance recorded in the fixtures README). The shape: client, resources and nested sub-SDKs all extend `BaseSDK`, so the root is the class that mounts another candidate and is not itself mounted; mounts are class-body annotations (quoted forward references on the root, direct names in `_init_sdks` nests); and unlike Speakeasy TypeScript the route is back in the declaring file, keyword arguments of `_build_request`, with `*_async` siblings and a `#stream` fragment dropped in comparison only. Two rulings recorded in docstrings: async variants are their own symbols, because `create_async` is a chain a customer writes; the fragment never reaches the wire. Registered in `EXTRACTORS`, which un-pends the (speakeasy, python) pair `generated-vendors.yaml` already configures -- `test_configured_vendors` goes green, and the ragie promotion candidate becomes buildable. 23 new tests, red-first; 218 pass across the generated-signals files | landed | `src/sync/signals/generated/symbols_speakeasy_python.py`, `src/sync/signals/generated/adapter.py`, `tests/test_extracted_symbols_speakeasy_python.py`, `tests/fixtures/sdk_sources/mistral_python/` |
| CI-W491 | **The continuous watch loop, planned against the whole record rather than invented beside it.** The owner asked how Sync stays constantly current with connected APIs; three parallel researchers swept all 33 specs, 36 plans, BACKLOG, WORKLOG and the public docs before the plan stood. The finding: Sync is a complete reactor with no clock -- every loop stage exists and is tested, and nothing anywhere runs on a cadence; the public docs promise a watcher and document a reactor, and the adapter guide third parties receive never says `fetch_changes` repeats. The record already decided the mechanism -- the cheap-poll cascade is an architectural requirement, cadence is vendor-driven and never a fixed clock, streaming is refused, MCP alone requires a timer, the original signature was `fetch_changes(since)` -- so the plan adopts those as constraints: a `watch_subscription` table derived from graph bindings (intake's own watched/watchable vocabulary), a version cursor restoring `since`, one idempotent `sync watch --once` any clock can call, GitHub's already-written ingress wired as M10's missing half, and the feed as phase-two fan-out blocked on the two owner decisions named since July. Seven unanswered questions and five proposed backlog entries are recorded so they become decisions rather than surprises | landed | `docs/superpowers/plans/2026-08-18-continuous-watch-loop.md` |
| CI-W492 | **Finding dismissal reaches the console, read-only, and the parity guard that should have caught it being absent was reading one file.** Owner ruling 2026-08-19: the console renders dismissals and never posts one, so dismissing stays a command-line action. The Finding page gains a Standing row -- dismissed with its reason and actor, or open -- and `history_count` is rendered in **both** branches, because `dismissed: false` covers "never touched" and "dismissed then restored" alike and hiding the flip on the open branch flatters the system. The Findings page gains a tally over the reason vocabulary, which needed a route: `store.dismissal_reason_counts()` existed and nothing exposed it. It **states its fleet scope on screen** -- a dismissal records no `repo_id` and the findings table it would join against is rebuilt by every scan -- which is `abandonment_by_change_kind`'s precedent, not `RunsCard`'s. **The drift guard read `client.ts` alone**, so seven routes landed fetched-from-their-own-component and invisible to it; widened to every console source, which retired two stale exemptions and classified seven unclassified routes. Python suite 85 -> 101 on that file. Also repaired three gate failures that predate this: eight `runs_reader` doubles missing the `outcome` kwarg another session shipped, and four decode clauses from CI-W481 unaccounted for in `SUBSUMING` | landed | `src/sync/api/app.py`, `__main__.py`, `web/src/features/findings/dismissed-tally.tsx`, `finding-page.tsx`, `tests/test_api_routes.py`, `tests/test_decode_handlers.py` |
| CI-W493 | **The donut form, and the Overview's provenance mix — dashboard O2, which the plan filed as blocked on API work and which needed none.** `overview_summary` has emitted `bindings_by_rung` since dashboard 2 was specified and `types.ts` has declared it; nothing rendered it, which is the `retracted_at` shape exactly — it typechecks, it is maintained, and nobody can tell it is unused. **The owner ruled donuts for mixes and bars for rankings**, so the form is built once with the rules that keep a donut honest: the centre total is the sum of its own arcs rather than a second query, colour is fixed by sorted key so an arc keeps its colour when counts move, a ninth member folds into an arc that says how many it holds, and a fold of exactly one is not a fold. `MixDonutCard` makes the absence note a **required** prop — a caller with no answer to "what does a missing arc mean here" has a chart it should not draw. On the Overview the mix drops rungs at nought from the arcs and names them in prose instead, because an invisible arc still takes a legend row and reads as a member that failed to render. `unattributed` is drawn like any other rung: it is the count the honesty rule exists to make visible. **Proven able to fail** — the sort was flipped to by-value and the colour-stability guard went red | landed | `web/src/components/charts/mix-donut-option.ts`, `mix-donut-card.tsx`, `web/src/features/repositories/rung-mix-card.tsx` |
| CI-W494 | **The watch loop exists: subscriptions, cursor, one idempotent tick, and B94's first delivery destination.** Two agents built the halves test-first and the CLI is where they meet. `watch_subscription` (grain: one repo x vendor) seeds from graph bindings and never overwrites an operator's edits; `vendor_cursor` (grain: one vendor) advances in the same transaction as the scan rows, so an at-least-once tick that dies mid-scan rescans the same window onto the same natural keys. `sync watch --once` walks due subscriptions through the cheap-poll cascade -- the manifest-hash probe exposed from the machinery that owns it; coded/mcp vendors say honestly that no cheap probe exists yet -- scans moved windows through the same compositions `sync run` uses (deliberately without the truncate a timer would turn into B129), enforces the findings-per-tick cap with overflow queued visibly (spend is capped by count, printed as such, because no dollar figure exists anywhere in the tree), records would-remediate decisions under the owner's auto_pr_breaking default (safe = routed below the agent tier, an upper bound `nodes.py` proves), polls each repo's remote HEAD and names the sha INDEX never recorded rather than guessing, notifies, reconciles. `sync.forge.notify.IssueNotifier` opens one deduplicated GitHub issue per non-PR finding -- deterministic title from graph identity, exact-title match as the authority because GitHub search matches terms, in-batch memory because the search index is eventually consistent, a closed three-reason vocabulary, failures returned as outcomes never raised past a tick. Three new import contracts (watch is core-forbidden, model-SDK-forbidden, forge-forbidden), each shown red. 62 new tests; 245 green across the integrated suites | landed | `src/sync/watch/`, `src/sync/forge/notify.py`, `src/sync/graph/schema.sql`, `src/sync/graph/store.py`, `src/sync/signals/registry.py`, `src/sync/cli.py`, `pyproject.toml`, `tests/` |
| CI-W495 | **Integrations and Changes take their dashboards — I1, I3, G1, G3 — and G3 is the one entry that genuinely needed a new query.** `by_vendor` and `by_severity` are each single-column facets and neither answers "which integration publishes the breaking changes"; a reader could only get there by filtering to one vendor and reading the severity facet, once per vendor. `by_vendor_severity` is one `GROUP BY` over both columns, **both filters ignored** for the same reason each facet ignores its own — a cross-facet narrowed to the current selection shows the reader the slice they already chose. Bounded by vendors x a five-member vocabulary rather than by rows. **G3 renders as a stacked ranking rather than a donut**, because it is both a ranking and a mix and a dozen donuts cannot be compared; each row's width is a share of the largest publisher's total, so rows compare against each other rather than each summing to full width and drawing a vendor with one change the same size as one with three hundred. The newest-change tile **withholds under a narrowing** rather than answering quietly: the newest row of a filtered page is the newest *matching* change, which is not the claim the label makes. `fetchCatalogue` extracted at the second use, not the third | landed | `src/sync/graph/store.py`, `web/src/features/vendors/{integrations-kpis,findings-per-integration,changes-dashboards,catalogue}.tsx` |
| CI-W496 | **Connections, Findings and Detectors — and two catalogued dashboards refused rather than built.** N3 renders index freshness as dates rather than bars: every bar's length would be "time since the last index pass", one number repeated per row with a common cause, drawing a spread that is an artefact of when each service's first call site was written. No threshold and no colour, because there is no age at which an index becomes wrong and an invented one would be the traffic light. Services with **no** date sit apart from the dated rows rather than sorted to one end — never-indexed is not indexed-long-ago. **F2 is refused as a duplicate**: `TriageTabs` already carries the severity distribution with exact counts *and* is the control that narrows the table, so a donut beside it would be the same numbers a second way and the owner ruled severity once per page. **F3 is refused as a second home** — the same chart is built on Integrations, and a fact written twice disagrees with itself. So F1 earns its slot on what the tabs and table do not carry: detectors reporting, and last-indexed, which is what makes an empty table readable as clean rather than as unchecked. D2 is volume and says so — the loudest detector is not the most wrong, and the rung breakdown beneath is where that reading lives. `by_rung` declared on `DetectorAccountabilityResponse`, which the route has always sent and the type did not say | landed | `web/src/features/vendors/index-freshness.tsx`, `web/src/features/findings/findings-kpis.tsx`, `web/src/features/detectors/detectors-dashboards.tsx`, `web/src/api/types.ts` |
| CI-W497 | **Trends gains the first of the six time series, bucketed server-side as the owner ruled — and the second use of the daily-stack shape is factored rather than copied.** `changes_by_day_and_vendor` groups in SQL for the reason `findings_recorded_by_day_and_severity` does: the changes feed orders newest-first and pages, so a client-side fold would draw the most recent page and label it the history. `buildDayStackOption` now holds what makes either chart honest — no band for a member that never occurs, no zero filled in for a day the payload omits, no legend below two bands — and `buildFindingsOverTimeOption` delegates to it, 30 existing tests green through the refactor. **The two series sit side by side because neither says the useful thing alone**: the findings series is what Sync produced, the changes series is what the vendors published, and a day with changes and no findings is the product working rather than a gap. This chart carries one caveat no other does — a height over an `oasdiff` source is at-least-once rather than a measurement, which is the pipeline's single recorded idempotency exemption, said on screen rather than in a docstring. The route parity guard widened in W492 caught the new route arriving unfetched, which is what it was widened to do | landed | `src/sync/graph/store.py`, `src/sync/dashboard/graph_views.py`, `src/sync/api/app.py`, `web/src/components/charts/day-stack-option.ts`, `web/src/features/dashboards/changes-over-time-card.tsx` |
| CI-W498 | **Call sites, Runs and Signals — and Call sites had the richest unused aggregate in the console.** `/api/topology` has always computed call sites, files, operations, integrations and a loop-depth histogram over exactly the rows that table lists, and the page fetched none of it: the table showed the rows and never their shape. Mounted on the map page's query key, so it costs nothing where that page has been opened. **Depth zero is drawn rather than dropped** — it is the overwhelming majority on a real codebase, and without it the looped call sites read as the whole population, turning "3 of 812 sit in loops" into "3 sit in loops" with no denominator. R1 lives inside `RunsCard` because the runs query does; a strip beside it on the page would issue the same read twice. **Its fourth tile says *no outcome recorded*, never *in flight***: a run parked on the customer's CI and one whose process died are identical in this data, which is the same fact that keeps a status dot off this console — the refusal applies to the word as much as to the dot. No merge rate and no error rate anywhere in the three: each would be a ratio across grains that do not divide. S1's every tile distinguishes never-attached from attached-and-quiet, which is the distinction the telemetry rung exists to make and the one an empty page erases | landed | `web/src/features/bindings/call-sites-dashboards.tsx`, `web/src/features/runs/runs-kpis.tsx`, `web/src/features/signals/signals-kpis.tsx` |
| CI-W499 | **Three vendors promoted on the owner's approval, and the conformance census made whole.** Perplexity (Stainless), Retell AI (Stainless) and Ragie (Speakeasy -- the first vendor through the new `speakeasy-python` extractor) join `generated-vendors.yaml`, each manifest re-fetched at write time and each Python module name read out of the package's own PyPI README rather than assumed -- `perplexityai` imports `perplexity` and `retell-sdk` imports `retell`, divergences a guess would have gotten wrong. Their catalog entries drop the package lists the registry now owns, `vendor-promotions.yaml` shrinks to Eleven Labs (Fern needs its own extractor), and the catalog regenerates: 18 supported, 71 recognized. `test_shipped_conformance`, broken at collection since CI-W464 registered nine vendors without cases, gets the twelve missing `VENDOR_CASES` in the file's own prescribed pattern and the twelve `UNSTAGED_SDK_SOURCE` entries the census gates in both directions -- one of main's standing reds goes green rather than exempted. Also recorded: the owner's ruling that the watch clock becomes a product surface on the integrations page rather than a task armed on this machine | landed | `generated-vendors.yaml`, `vendor-catalog.yaml`, `vendor-promotions.yaml`, `docs/integrations/catalog/`, `tests/test_shipped_conformance.py`, `docs/superpowers/plans/2026-08-18-continuous-watch-loop.md` |
| CI-W500 | **The provenance wheel was a ring, and the fix is not cosmetic.** Against this repository's own graph the Overview donut drew **one closed arc**: 24 open findings, every one `static`, four rungs at nought — a ring at 100% is the same picture for 24 findings as for 24,000, and the four numbers it moved into a footnote are the ones a reader came for. Two things were confused. **A zero in this breakdown is a measurement**: `overview_summary` fills the dict from `FINDING_RUNGS` rather than from the rows it found, so `resolved: 0` means counted-and-found-none — the opposite of everywhere else on this console, where a missing key means nobody looked. Hiding measured zeros threw away real information to protect a rule that did not apply here. And **a one-member mix is not a mix**, so `MixDonutCard` now degrades below two members to a stated fact plus the full breakdown, which is strictly more information in less space. The panel lists every rung with count, share and meaning under either form. **The strip uniformity pass completes the owner's ruling**: Trends, Runs, the file tree and the integration map had no strip, and the Overview, Detectors and Runs strips opened halfway down their own pages — the Runs one was inside `RunsCard`, below a caveat paragraph and a filter rail. All thirteen screens now open with one; the Runs strip reads `limit: 1` because every figure it needs is computed before the outcome filter applies | landed | `web/src/components/charts/mix-donut-card.tsx`, `web/src/features/repositories/{rung-mix-card,topology-kpis,codebase-facts-kpis}.tsx`, `web/src/features/dashboards/trends-kpis.tsx`, `web/src/features/runs/runs-kpis-region.tsx` |
| CI-W501 | **The Corpus tab and the intake attempt record — two owner-ruled surfaces that existed server-side with nothing rendering them.** `/api/corpus/health` has shipped since `M12-W323` and its payload is the most console-shaped in the product: every axis carries `status`, `has_samples`, `sample_count`, `provenance` and its own `denominator_description`, so the absence-versus-zero distinction is computed rather than asserted. Against this deployment it reports **five axes, all unmeasured, zero samples** — and that is the screen working. A competing tool with this data shows a merge rate of 100% over one attempt; this one names five measurements, gives each the denominator it would need, and says none has a sample. **An unmeasured axis is never drawn as a failing one** and there is no score over the five, which is where one would be most tempting — the payload even offers `axes_measured_count` to build it from. **`intake_attempt` closes two limits `adapter_inventory` had written down as open**: `last_change_at` is not when an adapter was last asked, and there could be no decline reason because nothing recorded an attempt. Both sentences are **corrected rather than deleted**, because the reason still holds for the column they were about — `last_attempt_at` now sits beside `last_change_at` and a healthy quiet adapter has a recent first and an old second, which was previously indistinguishable from one nobody ran. A null still never means "never asked": the record began when the table did. **The parity guard needed its own fix** — widened past `client.ts` in W492 it began reading routes cited in prose as fetches, so comments are stripped before scanning, and it was re-proven able to catch a real drift afterwards | landed | `web/src/features/dashboards/corpus-page.tsx`, `src/sync/graph/store.py`, `src/sync/dashboard/adapters.py`, `web/src/features/settings/adapter-table.tsx` |
| CI-W502 | **The 2026-08-19 catalogue completes: L2, L3, T4, and the log scale the owner ruled for skewed sets.** `outcomes_by_day` and `attempts_by_tier` are two groupings of one table at one grain, so they ship as **one** endpoint — three routes would be three round trips for one answer, and the console places them as three panels because placement is a layout decision rather than a reason for three routes. **Both are counts and neither is a rate**: which tier produced an attempt is the routing question, how often a tier succeeds is `merge_rate_by_tier` on the Corpus tab computed over a denominator these counts do not have. Attempts are dated by `created_at` and never `pr_merged_at` — a series keyed on the merge date silently drops every attempt that never opened a pull request, which is most of them and the half a reader most needs. Rehearsals excluded, matching `migration_outcomes`. **`RankedBars` gains an announced log scale**: 8,576 warnings against 108 breaking is one pixel each on a linear axis, which is the same illegibility that made the provenance ring look unbuilt. Opt-in, `log1p` so a member measured at nought still draws, counts printed beside every bar under either scale, and **the announcement is the thing that makes it permissible** — a log axis a reader takes for linear is worse than no chart, because every comparison is wrong by a factor they cannot see. Proven able to fail: removing the word turns the guard red | landed | `src/sync/graph/store.py`, `src/sync/dashboard/fleet.py`, `src/sync/api/app.py`, `web/src/features/workflows/remediation-activity.tsx`, `web/src/components/ranked-bars.tsx` |
| CI-W503 | **Provenance is bars, and the two earlier attempts were both wrong about the form rather than the styling.** It shipped as a donut: 24 findings all `static`, four rungs at nought, so it drew one closed ring. The fix kept the donut and moved the zeros into prose, which replaced an unreadable chart with **no chart** — a heading, two paragraphs and five lines of text, which is what the owner reported second. **The mistake underneath both is that a donut cannot draw a zero**: share-of-whole gives an arc of nought no angle, so a measured-zero member is invisible or absent — and on this panel *four of five members are measured zeros*, which is the ordinary state of a statically-indexed codebase and the most informative thing the panel can say. A horizontal bar has a length of zero and still has a row, a label and a count. Rows are in **evidence order** rather than ranked, because a ladder that reorders as data moves is harder to read across visits. `RankedBars` gains `annotate` (a clause per row, for a set whose members are a vocabulary rather than names) and `share` (**opt-in**: a bar's length is already a share of the largest, so a printed share of the *total* is a second denominator on one row, right only where the members partition a nameable whole). A zero row draws no bar at all rather than the minimum sliver every other member gets — an empty track beside a printed 0 reads as counted-and-none where a stub reads as a small quantity. **Also verified every dashboard against live payloads**: topology, overview, changes and integrations all sum to their stated totals. One defect found — N3 listed three services at identical timestamps sorted "oldest first", implying a spread `max(indexed_at)` per vendor cannot show when one pass stamps every row; it now says they share one pass | landed | `web/src/features/repositories/rung-mix-card.tsx`, `web/src/components/ranked-bars.tsx`, `web/src/features/vendors/index-freshness.tsx` |
| CI-W504 | **`CLAUDE.md` rewritten on one principle, with the check to back it — the owner's call that the previous version was blocking development.** The diagnosis is measurable rather than a matter of taste: **42% of the Python in this repository is comments and 25% of the console**, because the file asked for an argument in the source rather than a check in the pipeline. The governing principle is now **encode a rule where it fails, not where it is read** — and the evidence for it is this repository's own history. The conventions that held were machine-enforced: `test_import_boundary.py`, the required `bindingNullLabel` prop, `insert_finding` refusing an unattributed rung, `lint_encoding.py`. The ones that quietly decayed were prose — **seven of the twenty-four protected console sentences cited files that no longer exist, and nothing noticed for two weeks**, because nothing tests prose. **Every operational fact survives verbatim** (`python` not `python3`, port 5433, no Docker, both encoding rules, the stash rule, the mtime rule, the three SDK containment facts, the B112 CI caveat); what goes is ceremony — the protected-sentence set, the technical-debt essay, the documentation culture that produced the ratio. `scripts/lint_comments.py` makes the comment budget real as a **ratchet against a recorded baseline** rather than a threshold that would fail every build today and be disabled by tomorrow; proven able to fail by padding a module with 400 comment lines. Previous version preserved on `backup/pre-claudemd-rewrite-2026-08-19` | landed | `CLAUDE.md`, `.claude/rules/console-surface.md`, `scripts/lint_comments.py`, `.comment-baseline.json` |
| CI-W505 | **The memory files restructured against Anthropic's published guidance, and the first hook in this repository.** Three findings from the docs applied. (1) **"For each line, ask: would removing this cause Claude to make mistakes? If not, cut it. Bloated CLAUDE.md files cause Claude to ignore your actual instructions."** The root file goes 298 -> **127 lines** and now holds only what is universal. (2) **Nested memory files load only when you touch that directory** — so `src/sync/CLAUDE.md` (78 lines: the encoding rules, pipeline discipline, model configuration, the admin-connection rule) and `web/CLAUDE.md` (76 lines: the honesty rules, the ⓘ ruling, the chart-form rules learned from the provenance ring, the test scope) cost nothing when editing the other stack. Total content is roughly unchanged; **per-turn cost falls by more than half**. (3) **"Hooks are deterministic; CLAUDE.md instructions are advisory. Use hooks for actions that must happen every time with zero exceptions."** `scripts/hook_check_edit.py` runs the encoding lint on every Python edit — the sharpest case in this repository, because every fixture is ASCII so **no test can ever catch a missing `encoding="utf-8"`**; it failed first in production twice. **The hook's first probe passed a real violation**: it compared a relative payload path against an absolute root, `relative_to` raised, and the exception was swallowed as "not our file" — the vacuous check `CLAUDE.md` warns about, caught only because it was tested against a deliberate violation rather than assumed | landed | `CLAUDE.md`, `src/sync/CLAUDE.md`, `web/CLAUDE.md`, `.claude/settings.json`, `scripts/hook_check_edit.py` |
| CI-W506 | **The rules pruned, and the screenshot fence encoded as a hook — always-loaded governance falls from 366 lines to 135.** Two rule files loaded on **every turn**, 149 lines against every task in the repository, and `interface-originality.md` was one of them for a stated reason: the 50 competitor screenshots can be opened from anywhere, so no `paths:` pattern could fence them. **`scripts/hook_guard_reads.py` is that fence, encoded where it fails** — a `PreToolUse` guard blocking the image files while letting the notes beside them through, because the notes are the adoptable half and fencing those would close off the research the directory exists for. With the fence deterministic the rule scopes to `web/**` and costs a Python session nothing. **`signal-stage.md` and `remediate-stage.md` were left alone**, and that is the finding worth recording: both are already dense and every line is operative — cutting them would have removed working guidance to hit a number, which is the failure mode of a pruning pass. Deduplicated everywhere the new nested `CLAUDE.md` files now carry a fact: the rules **point rather than repeat**, since a fact written twice disagrees with itself and that is this repository's most expensive form of debt. `console-surface.md` and `test-discipline.md` shrank most, because `web/CLAUDE.md` and `src/sync/CLAUDE.md` had absorbed their duplicated halves | landed | `.claude/rules/*.md`, `.claude/settings.json`, `scripts/hook_guard_reads.py` |
| CI-W507 | **The UI sweep: on-screen prose falls from 4,160 characters to 947, a 77% cut, with every claim still visible.** The owner's ⓘ ruling applied across twelve screens — the argument moves behind the hover, the claim stays on screen in the fewest honest words. Connections went from four paragraphs and no hint to none and one; Runs lost a five-line bordered scope paragraph and two trailing explanations; Detectors lost three paragraphs and a `ControlBar` that restated the scope a chip now carries. **`ScopeChip` replaces the fact written three times**: the corpus scope stood in full on Runs, Solutions and Corpus, which is the shape of fact that eventually disagrees with itself — `CORPUS_SCOPE` is now one exported node, two words on screen and one hover. **A test caught the sweep moving a claim rather than an argument**, which is the amendment working as designed: `repository-services-page.test.tsx` holds that the screen must say it cannot show each service's operations, and folding that into a hover turned it red — what a screen does *not* show is exactly the absence a non-hovering reader must see, so a four-word visible form was restored with the *why* left in the ⓘ. Empty states took the short form throughout: *not measured yet*, *no tier has run*, *nothing recorded yet*. Console suite back to the pre-existing 50 failures with nothing added | landed | `web/src/components/scope-chip.tsx`, `info-hint.tsx`, and twelve page components |
| CI-W508 | **Symmetry, measured and fixed at the primitive -- and the root cause was not the grids.** An audit over every page component found **64 multi-column grids and only 10 holding equal row heights**, which is the owner's longest-standing complaint expressed as a number. Twelve card grids gained `auto-rows-fr`. **But that alone would have changed nothing visible**, and that is the finding: `MetricPanel`, `KpiStrip` and `RankedBars` had no `h-full`, so a card sat at its content height inside a taller cell and two panels in one row still ended at different baselines -- the equal-height grid appearing to have done nothing. The fix is three characters in three primitives and applies everywhere those components are used rather than grid by grid. Equal-height grids now 22. **Spacing was audited and largely left alone**: 417 tokenised gaps against 42 raw, and the raw ones sit inside `components/ui/` primitives and layout chrome rather than in page rhythm -- churning vendored primitives to move a ratio is polish competing with the milestone. Page centring verified consistent: one `mx-auto max-w-[1400px]` container in the chassis, no per-page override. Also adds `volumeScale` and `divergingScale` for the D3 visuals, **with the ramp floor derived rather than chosen** -- a fixed 0.35 step shipped at 1.62:1 against the plotting surface, a ramp floor a reader cannot see, caught by `palette.test.ts` before it reached a screen | landed | `web/src/components/{metric-panel,kpi-strip,ranked-bars}.tsx`, `web/src/lib/palette.ts` |
| CI-W509 | **Two of the three D3 visuals, and the third refused as duplication.** The Sankey answers the one question no panel answered: every screen counts a *stage* -- findings here, runs there -- and none showed the **attrition between** them, so 24 findings with no attempts and 24 findings with 24 abandonments rendered identically. **The component refuses to draw a flow that does not conserve**, and Sync's own graph is why: 8,723 vendor changes produced 13 change units carrying 24 findings, which is three units on one set of bands -- a widening that would read as growth. `assertConserves` returns the offending node ids and the panel counts in findings only, stating the change fan-out as a figure beside the diagram rather than drawing it. The chord answers what `ApiTopologyCard` counts but cannot show: *between which* integrations coupling runs, which is what predicts a change's cost. Diagonal dropped, since an integration coupled with itself is its own file count and would squeeze every real pairing into the remainder; where a file touches three or more integrations its weight is spread evenly across the possible pairs, **stated as an assumption because the payload carries how many it touched and not which**. **The radial run timeline was not built**: `NodeSequence` already renders order, evidence *and* durations for the same nodes, so a third view would be the fact written twice this repository has spent a week fixing -- and the corpus holds no attempts to draw it from | landed | `web/src/components/charts/sankey-flow.tsx`, `web/src/features/workflows/remediation-flow.tsx`, `web/src/features/index-graph/coupling-chord.tsx` |
| CI-W510 | **The console test suite repaired: 50 failures across 7 files to 0, and 848 tests green.** It had not been a working gate for the whole session -- a real regression could have landed unnoticed. **34 of the 50 were one cause**: `useChassisIdentity` calls `useQuery` directly rather than through `@/api/queries`, so the module mock never reached it and every chassis render threw *No QueryClient set*. Seeded rather than merely provided -- an unseeded client leaves identity pending forever and half the file's assertions are about chrome that only renders once a workspace is known. **The rest were the amended rules working as designed**, and each was judged rather than silenced: `navRoutes` was defined twice and the test's copy never applied `navOrder`, so the owner's rail reordering made two definitions disagree -- the component now exports the one. The scope-trail guard asserted against `ScopeSwitchers`, which the owner removed and which is mounted nowhere. Four tests used Detectors as *a rail link to focus* after it became a Metrics tab. Two run fixtures omitted `by_disposition`, which the payload always sends. **`hrefs.test.ts` caught a real defect**: six routes I added had no builder and their callers hand-rolled strings, which is the four-copies drift that module exists to stop -- builders added rather than the guard relaxed. One test was **strengthened**: it ran one fixture and asserted the other branch's wording, so it now checks both sides of absence-versus-zero as its own name promised. **Proven still able to fail** by breaking `corpusHref` and watching two guards go red | landed | `web/src/layouts/app-frame.{tsx,test.tsx}`, `web/src/lib/hrefs.ts`, and six test files |
| CI-W511 | **The startup reports the pipeline as a workflow, the KPI strip becomes one instrument, and empty states stop just sitting there.** Owner direction, three parts. **`dev_up.py` gained four stage checks** -- SIGNAL, DETECT, OBSERVE, REMEDIATE -- each naming the command that advances it, so a first run leaves an operator knowing *where the data workflow stands* rather than that a server is up. Against this deployment it reports 8,723 changes and 25 findings green, and observed traffic and repair attempts missing with the `ingest` and `rehearse` invocations beside them, which is exactly the two systems the owner named. **The strip was drawing its frame twice**: `FactTile` carried a border and a background and `KpiStrip` wrapped each one in another, which is why four facts occupied a panel's height and read as loose cards. One surface with hairline dividers now, values on the figure step, `auto-rows-fr` kept so a wrapping note cannot shorten its neighbour. The Findings strip moved above the tabs, where the owner said the identity row belongs. **`EmptyState` and `NotAttachedState` gained an action and a command slot**: 27 components explained an absence and stopped, and the console cannot run these itself -- no route mutates the graph or triggers a run -- so what it honestly offers is the exact invocation, copyable, rather than a button that would have to pretend it did something | landed | `scripts/dev_up.py`, `web/src/components/{kpi-strip,fact-tile,states}.tsx`, `web/src/features/signals/not-attached-state.tsx` |
| CI-W512 | **Real OTLP from Sync's own vendor calls, and the model made configurable — the two halves of populating the observed rung honestly.** The rung was empty because the only payloads available were vendor fixtures describing calls that never happened here, and ingesting those would have made the console claim it observed traffic it did not. **Sync does make real vendor calls**: every agent run reaches `api.anthropic.com`, `anthropic` is a registered adapter, and Sync's own index finds 43 Anthropic call sites in this codebase -- so spans correlate to real bindings. `sync.obs.otlp_emit` measures the call rather than describing it: timing is taken around the block, a call that raised still writes a span (dropping it would make the rung quietly optimistic), and **the attribute set is method, host, route and status and nothing else** -- no prompt, no completion, no identifier, which is the threat-model boundary at the place it would be easiest to break. Opt-in by `SYNC_EMIT_OTLP`, because a library that wrote files because it was imported is a defect. **The model is the product's only spend** -- `ClaudeSdkRunner` is the patch agent and no other path calls a model -- and it was hardcoded. `SYNC_MODEL` overrides it, **read at call time rather than at import** so an override cannot depend on module ordering. Per-attempt token cost was already recorded and already reaches the console as the Corpus tab's `tokens_per_merged_patch` axis | landed | `src/sync/obs/otlp_emit.py`, `src/sync/runner/claude_sdk.py`, `src/sync/runner/__init__.py` |
| CI-W513 | **The model provider: frontier, cheaper frontier, or local — and a correction worth recording, because the owner was planning cost architecture on it.** The owner understood there to be two AI costs, a solution agent and a telemetry agent. **There is one.** `grep` over every model-SDK import in `src/` returns exactly one file: `sync/runner/claude_sdk.py`. The telemetry path calls no model at all -- `otlp_emit` records spans of calls that already happened, which is passive observation at zero model cost. So one module can honestly describe the whole spend surface, and `sync.runner.provider` is it. **A local model is a base URL, not a second code path**: Ollama, LM Studio and vLLM all speak a compatible API over a URL, so support is pointing the client elsewhere rather than writing another client -- and it reaches the SDK through `options.env` because the SDK spawns a CLI subprocess and has no field for it, which `sandbox.py` already documented. **A base URL with no model named is refused rather than defaulted**: sending `claude-opus-5` to a local runtime asks for a model it does not have, and that failure arrives opaque and mid-repair, so the error names the variable instead. Blank values fall back, because shell scripts export empty strings constantly and reading one as a configured endpoint fails as a connection error rather than a missing setting. Settings now reports which provider is in use, **forwarded from the resolver rather than restated** -- and a misconfiguration is reported, not raised, because a Settings screen that 500s on a bad variable is worse than one that names it. Zero is still available and unchanged: `StaticRunner` runs the pipeline with no model at all | landed | `src/sync/runner/provider.py`, `claude_sdk.py`, `src/sync/dashboard/setup.py`, `tests/test_model_provider.py` |
| CI-W514 | **Empty states across 21 files now name the command that fills them, the Call sites page gains Nango's drawer, and the rehearsal proved a thing worth knowing.** Thirty-eight empty states were audited and **commands added only where one genuinely populates the panel** -- a state that clears with a filter, or that reports a scope mismatch, already tells a reader what to do, and a command there would be noise pretending to be help. `index`, `scan`, `run`, `ingest`, `shapes` and `adapters` each land where they actually apply, repository-scoped where the panel knows one. **Call sites takes Nango's row-to-drawer convention** (`references/notes/nango-integration-architecture.md` §4) with the open row in the URL, because 15 recorded fields do not fit a scannable row and a reader handing a colleague a link should hand them the row they are looking at. The drawer explains the call from its **recorded shape** -- symbol, argument keys, response fields read, nesting -- and says plainly that source is not shown: `api/app.py` records that as a threat-model ruling, and for *what would a vendor change break here* the shape is the better answer anyway, because it is exactly the surface a change has to break. **The full rehearsal landed and populated one tile, which is correct**: it wrote three attempts, all `is_rehearsal`, and every activity and rate query filters those out by `migration_outcomes`' own rule -- so `sync rehearse` cannot populate Solutions or the Sankey and only a production run can. The abandonment was real and honest: *the remediator produced no change* | landed | `web/src/features/bindings/call-site-drawer.tsx`, `call-sites-page.tsx`, and 21 files |
| CI-W515 | **M15 planned: the reference integration, as a document rather than a build.** Eleven tasks across Supabase, Nango and Superlog, sequenced so each one's verification is possible when it runs -- tags, full-page tables and the inline panel first because the other eight render inside them, and the two-tier shell **last** because it touches every screen and doing it first would mean rebuilding each task inside a moving shell. **The plan carries a correction against its own predecessor**: `CI-W514` shipped the Call sites detail as a modal sheet citing Nango's row-to-drawer pattern, and Nango's note does say drawer -- but Supabase's note says *which* drawer, and the modal is the wrong one for a list a reader moves down. Their `UserPanel` is non-modal, resizable beside the list, with `history: push` so Back closes it. Recorded rather than quietly fixed, because the reasoning is the reusable part. **Three refusals carried forward**: no `ActiveDot` on a rail item (their lint result is a closed lifecycle, ours would collapse *could not check* onto *checked and passed*), no confidence scalar from Superlog's incident view, no virtualisation at 165 rows. Three open questions left for the owner rather than guessed: vendor trademarks, what a logs query would even be over given a read-only API, and the production run that is the only thing that can populate Solutions | planned | `docs/superpowers/plans/2026-08-19-m15-reference-integration.md` |
| CI-W516 | **The model is the user's, never the operator's — and the empty-state commands I shipped last item did not exist.** Owner ruling: Sync must not inherit whoever installed it. The provider's default was a frontier model on the vendor's endpoint, which meant a deployment configuring nothing would spend the installer's credential the first time a repair ran; nobody chose that. **Unconfigured is now the default and it is a state rather than an error** -- the console asks what is set up, so `resolve_provider` reports and `require_provider` refuses, and the runner uses the second. The key is read at call time and **never held**: `CLAUDE.md`'s rule is unqualified, so the config carries a boolean and the test asserts the key appears in neither `repr()` nor `describe()`. `SYNC_MODEL_API_KEY` rather than `ANTHROPIC_API_KEY` deliberately -- the latter is already set in most developer environments by unrelated tools, and reading it would be exactly the inheritance this prevents, arriving silently and looking like configuration. Settings gains a Model panel that **reports rather than performs**: a form accepting a key would have to put it somewhere, and every one of those places is somewhere it can leak. **The correction:** `CI-W514`'s empty states named `sync scan` and `sync adapters`, **neither of which is a verb this CLI has**, and `sync index` takes `--repo` not `--repo-id`. Twenty files fixed and every named command checked against `sync --help`. A command that does not exist is worse than none: it sends a reader to a shell to be told the verb is invalid. **A demo workspace is now populated** -- the `furever` corpus fixture is a real 144-file Next.js app that genuinely calls Stripe, indexed at 31 call sites across 15 files with 11 findings and 6 call sites inside loops | landed | `src/sync/runner/provider.py`, `claude_sdk.py`, `web/src/features/settings/model-settings-panel.tsx`, 20 empty-state files |
| CI-W517 | **Switching codebases did not work, and the cause was worse than stale data: there was no switcher.** The owner reported the UI not updating between codebases. `useChassisIdentity` reads the workspace from the route and falls back to the sole repository *only when there is exactly one* -- so the moment a second codebase was indexed that fallback stopped applying, and the only way to change workspace was to hand-edit the address bar. The badge beside it linked into Settings. **The data layer was already correct**: every keyed read carries `repoId`, so changing the route changes the key and the data follows -- nothing was reaching it. `WorkspaceSwitcher` sits on the environment badge, **outside the `Link` rather than inside it**, because a menu trigger nested in an anchor is a nested interactive element and the anchor swallows the press. **Switching keeps the screen**: the path is rebuilt through the registry's own matcher rather than a string replace, because every repository id is `host/owner/name` and naive substitution on the percent-encoded form breaks on all of them. **A screen addressed by a subject the new workspace lacks falls back to its Overview** -- a finding id belongs to one workspace, and carrying it across lands on a 404 that reads as a broken switcher rather than as a finding that is not there. Proven able to fail by removing that guard. The demo workspace is renamed from its git remote to `demo` on the owner's direction | landed | `web/src/layouts/workspace-switcher.tsx`, `app-frame.tsx` |
| CI-W518 | **M15 Task 1: table-first screens get the window, and the badge stops navigating away.** The chassis caps content at 1400px, which is right for a screen of panels and wrong for one whose subject is fifteen recorded fields per row. **Declared in the registry rather than achieved with negative margins**: a full-bleed hack fights the scrollbar and lands differently per browser, where a `wide` flag the frame reads is one rule in one place. Matched through `matchPath` rather than by prefix, so widening `/findings` does not widen the workflow detail nested under it -- the same trap `isActiveMenuItem` documents. **Column visibility carries four rules that stop a preference becoming a broken screen**: a column may declare itself unhideable (the provenance rung, by a rule older than this component) and the stored set cannot defeat that; the last visible column stays; choices are per table, because hiding `SDK version` on call sites is not a request about findings; and a stored id for a column a later release removed is dropped on read rather than resurrecting a column that is gone. Call sites now offers all nine, defaulting to the five a reader scans. **And the owner's bug:** the environment badge was a `Link` into Settings with the switcher beside it, so pressing the codebase name navigated away. The whole badge is the trigger now, with the panel offset back under it rather than off the window edge | landed | `web/src/components/column-visibility.tsx`, `web/src/lib/routes.ts`, `layouts/app-frame.tsx`, `layouts/workspace-switcher.tsx` |
| CI-W519 | **Settings detached the codebase, and the cause was a hardcoded id that no longer exists.** The owner reported opening Settings dropping the workspace and showing an older interface. Two faults, one screen. **`activeRepo` fell back to the literal `"stroland02/Sync"`** -- not a repository this deployment holds, because the real identity is `github.com/stroland02/Sync` derived from the git remote. So Settings opened on a workspace that does not exist, every panel below asked the API about nothing, and its own selector offered that invented id as the only option when the repository list was empty. **And `/settings` binds no `repoId` at all**, being a destination rather than a level, so the chassis read the route and found nothing: the badge blanked and every repository-scoped rail row became unlinkable text. The old single-repository fallback covered this until a second codebase was indexed, which is the same edge that hid the missing switcher. `active-workspace.ts` owns the rule now and is tested: **the address always wins**, because a remembered value overriding it would open a shared link on the recipient's own codebase; an unscoped screen inherits the last workspace; and a remembered workspace the graph no longer holds is discarded rather than named. Only what the address itself bound is remembered -- persisting the inherited value would let a fallback promote itself into a choice nobody made. Integrations and Solutions join the wide set on the owner's direction | landed | `web/src/layouts/active-workspace.ts`, `app-frame.tsx`, `features/settings/settings-page.tsx` |
| CI-W520 | **The filter rails did not filter, and the cause was two writes where one was needed.** The owner reported the changes rail not working. Everything tested in isolation passed: the rail renders selectable options, `facetGroup` builds them correctly, and the route filters correctly when called directly -- 12,075 changes down to 107 for `openai`. **The seam between them had no test, and that is where it broke.** Pressing an option called the facet setter and then `setOffset(0)`, and both call `setSearchParams`; React Router hands the functional form the *current* params rather than a queued value, so the second write's `prev` predated the first and the offset reset discarded the facet it was meant to accompany. The rail showed itself pressed and nothing was refetched -- a defect that looks like a styling problem. `useFilterParam` already did both in one write and was in use on Findings only; the three rails that hand-rolled the pair now use it. **Reproduced first**: a page-level test asserting the press reaches the query failed before the fix and passes after, and it covers the seam neither the rail's tests nor the route's tests could. The rails also stretch to the table's height and stick within it -- a rail beside a 12,075-row table that scrolls away is reachable only by scrolling back to the top | landed | `web/src/features/vendors/integration-changes-page.tsx`, `bindings/call-sites-page.tsx`, `fleet/runs-table.tsx`, `components/filter-rail.tsx` |
| CI-W521 | **M15 Task 2: the detail sits beside the list, not over it — the correction M15 was planned around.** `CI-W514` shipped the call-site detail as a modal `Sheet` citing Nango's row-to-drawer convention. Nango's note does say drawer; **Supabase's note says which drawer**, and the modal is the wrong one for a list: their `modality.mdx` puts dialogs on short focused tasks and sheets on longer forms, and their own list-detail is not modal at all. On 165 rows a modal means open, read, close, find your place, open the next -- beside them, the next row is one arrow key away. **The selection pushes history so Back closes the panel**, which `useFacetParam` did not do and which would have made Back skip the whole table; and it is a separate hook from `useFilterParam` because the two want opposite history behaviour -- narrowing is a refinement nobody expects Back to undo a step at a time, opening a detail is a place they expect Back to leave. **The arrow-key handler is bound at the document**, because the reader's focus is on the row they clicked and a handler on the panel fires only when they are not looking at the list -- and it **never takes a key from somebody typing**, which is the defect a reader meets while searching, proven by removing the guard and watching it fail. The ends do not wrap: a list that wraps sends a reader holding the key back to the top believing they are still descending | landed | `web/src/components/detail-layout.tsx`, `features/bindings/call-site-drawer.tsx`, `call-sites-page.tsx` |
| CI-W522 | **The rail tells the pipeline's story: five stage groups, and every stage has a door.** The owner's restructure, superseding three rulings of 2026-08-18. The sidebar groups by workflow stage -- Index, Signal, Observe, Detect, Remediate, the owner's own definitions recorded in `routes.ts` -- and the grouping is presentation: `GRAPH_LEVELS` is untouched and `test_console_hierarchy.py` still holds it. **Two stages had no door at all**: the telemetry page (now `Telemetry`, under Observe -- `Signals` as a label would collide with the SIGNAL heading two rows up) and Detectors (under Detect) were tabs buried in other pages' strips. **Three labels stopped lying or colliding**: `Metrics` opened the findings list and is `Findings` now; `Integrations`/`Connections` were near-synonyms and are `Vendors`/`Services`; `Logs` is `Runs`. The tab strips re-cut to match: Findings carries Trends, Solutions gains Corpus (remediation output belongs beside the runs that produced it), Vendors carries Changes. **The heading ruling is superseded, not ignored**: what killed level headings was thirteen over eleven rows duplicating the row beneath; five stage words over nine differently-named rows is guarded against exactly that -- `routes.test.tsx` forbids a row named after its stage and holds contiguity and pipeline order, both proven red. Heading rows stay in the DOM at rail width with text `sr-only`, so no icon moves across the reveal | landed | `web/src/lib/routes.ts`, `layouts/app-frame.tsx`, `components/page-tabs.tsx`, nine page files |
| CI-W523 | **M15 Task 3: one tag anatomy for every closed vocabulary, and severity stays monochrome on purpose.** Nango's note asks for a closed tag vocabulary as components rather than ad-hoc chips per screen; measured before building, severity was bare text on **six** screens, change kind on four, adapter tier on two, and `RungBadge` was the only one that was a component -- the same value rendered several ways, which is the silent drift `CLAUDE.md` calls the most expensive. Ten sites converted and the hand-rolled anatomy is down from eleven to five, the rest being one-off labels rather than vocabulary members. **Severity could have taken colour and does not**: `DESIGN.md` permits a badge to be coloured when it is a recorded value from a closed vocabulary legible without its colour, and severity qualifies -- but a ramp from `info` to `breaking` reads as a judgement about *this codebase*, and severity is the **vendor's own published label**. A change published as breaking breaks this codebase only where a call site binds to it, so colouring it would assert a risk ordering the graph has not computed: the traffic light this console refuses, arriving as a gradient rather than a dot. **No dictionary for change kinds**, deliberately -- `signal-stage.md` records that the authoritative list is whatever `oasdiff checks` emits for the pinned binary, never a hand-maintained copy, and two hundred descriptions here would be that copy | landed | `web/src/components/tag.tsx` and ten render sites |
| CI-W526 | **M15 Task 4: a facet takes a set, and the union is expressible for the first time.** The rails were single-select, so the narrowing a reviewer actually wants -- two integrations, or breaking *and* deprecation -- had no sequence of presses that reached it. Widened end to end: `call_sites_page` and `vendor_changes_page` take value lists against `= ANY`, the routes read repeated query parameters (`?vendor_id=a&vendor_id=b`, never comma-joined -- a separator that can occur inside a vendor identifier is a parser that is wrong on somebody's repository and wrong silently), and `useFilterListParam` writes the whole set and the offset reset in **one** `setSearchParams`, which `CI-W520` is the record of getting wrong. **The facet rule survived the widening and is the part that could have broken quietly**: a facet ignores its own filter and honours the others, so pressing two of forty integrations does not collapse the list to those two -- one predicate builder serves the page query and every facet query, because a second copy is how they would come to differ. Call sites gained **operation** and **loop depth** facets the payload never counted, and per-facet search appears above eight options, where **a chosen option always survives the term** -- otherwise typing hides an option that is narrowing the table and the only control that would clear it is the one that just vanished. **No rung facet, and that is the table's fact rather than an omission**: `call_site` has no rung column and `store.py` hard-codes `static`, so the facet would hold one value and assert the others exist. **Disposition stayed single-select**, rendered as a set of one -- the union would have to reach `fleet.runs` and the checkpointer beneath it, and a rail that let two be pressed while one reached the query would look identical and be wrong. Every guard proven red: the two-write defect, the replace-instead-of-union defect, and the scalar `query_params.get` that returns only the first repeated value | landed | `src/sync/graph/store.py`, `api/app.py`, `api/__main__.py`, `web/src/lib/use-filter-list-param.ts`, `components/filter-rail.tsx`, three page files |
| CI-W527 | **Overview, Telemetry and Detectors were still capped at 1400px.** Owner report, 2026-08-19. `M15` Task 1 introduced the `wide` flag and gave it to the seven table screens; these three are grids of panels and were left behind, so each reflowed into a single column with half the viewport empty beside it. The flag's own contract said *a table first*, which is why they were skipped -- it now says what it does: the cap is for a screen a reader **reads**, not one they **scan**, and a detail screen (a finding, a binding surface, a pull request) keeps it because a column of prose at 2560px is harder to read rather than easier. Fixed at the flag rather than in the three pages: a local negative-margin full-bleed fights the scrollbar, lands differently per browser, and the next screen solves it a fourth way. **Nothing guarded width before this** -- `isWideRoute` had no test at all, so the omission was invisible; there is one now, holding both directions, proven red by removing the Detectors flag | landed | `web/src/lib/routes.ts`, `lib/routes.test.tsx` |
| CI-W528 | **M15 Task 6: a finding gets a name two people can say to each other.** A finding is a 32-character hex id -- correct for a key, useless in a sentence, and the plan's problem statement is exactly that two people cannot discuss one. The name is `stripe-postcharges-4b1c9e`: the integration, the operation, and enough of the finding's own identity to tell it from its siblings on the same operation. **Derived, never stored** -- `insert_finding` computes a finding's id from its natural key on every scan and converges on the row it already wrote, so a name computed from that id inherits the same convergence for free and needs no column and no migration. **The random word pair the plan refused is the important half of the record**: it would not survive re-hashing, and a name that changes on re-scan is worse than an id because a reader who wrote it into a ticket now holds a reference to nothing. **Six hex digits of discriminator, not four**, and the arithmetic is why -- at four, a workspace of two thousand findings is better than even money to collide, and a collision is two findings a reader cannot tell apart by the name on screen; proven by shortening it and watching the workspace test go red. Derived in the **payload** rather than in the console, because the same finding is named by the CLI and by a pull-request body too, and a third copy of one derivation is where they start to differ. It lives in `sync.core` and imports nothing but `hashlib` and `re`, so a third party writing a vendor adapter can name a finding without acquiring a database driver. **The id stays the addressable thing** -- every URL and every join is unchanged; what this earns is the sentence. One inherited limit stated rather than hidden: a call site's id is derived from its position, so a finding whose call moves to another line is a different finding with a different name -- that is the id's own behaviour, and a name that survived the move would claim a continuity the graph does not record | landed | `src/sync/core/naming.py`, `dashboard/graph_views.py`, `web/src/features/findings/findings-table.tsx`, `api/types.ts` |
| CI-W529 | **The console shows the code: index-captured windows on every call-site surface, config-gated.** Owner re-ruling scoping the threat-model rule in `api/app.py`: bounded windows the index captured ARE served, on a deployment that has not set `SYNC_SERVE_SOURCE=false`; whole files stay unserved everywhere, and the capture-not-serve shape is forced by the graph itself -- no table stores a path back to a checkout, so index time is the only moment the source is in hand. `call_site` gains `snippet`/`snippet_start_line` (nullable, the only shape `apply_schema` can add), `_attach_snippets` captures nine lines around each site at index time, and the API states its policy on every payload: **`source_served` is always present so a reader can tell withheld from never-captured** -- two different nothings, and `absentSnippetReason` spells each. `CodeSnippet` renders the window numbered from its place in the file with the subject line marked in more than colour. Three surfaces: the call-sites drawer (whose source-is-not-shown prose is retired), the binding drawer, and the finding page's new **The call, in place** panel -- the your-code-beside-their-contract comparison, whose vendor pane is the recorded shape until B197 captures the SDK type slice. B198 files the owner's workflow live-view ask. Two stale type-contract baseline entries pruned in passing (`by_disposition`, `by_rung` -- both declared since) | landed | `src/sync/index/codebase.py`, `graph/schema.sql`, `store.py`, `api/app.py`, `web/src/components/code-snippet.tsx`, three drawer/page surfaces |
| CI-W530 | **M15 Task 9: a node with no evidence now says which nothing that is.** The task's verification has two halves and only one was met -- every node with recorded evidence already opened it, and a node without rendered **nothing at all**: `EvidenceDisclosure` returned `null` on an empty set, so a node that ran and recorded nothing looked exactly like one the reader had not expanded. Two different facts drawn as the same absence, which is the single thing this console exists not to do, sitting inside the screen that argues the case. Which nothing it is comes from the standing `sync.dashboard.queries` already classifies: `ran` means the node executed and produced none of what this screen shows, and the other four each had a sentence in `node-standing.ts` that **nothing rendered** -- `due_again` was the only one wired up, so a reader deciding whether a run was stuck never saw the sentence saying a run parked on the customer's CI and a run that has died look identical from a checkpoint. **The sentence does not name the fields it would have shown**: that list is `_EVIDENCE_KEYS` in the payload, and a second copy in the console is the fact written twice that disagrees with itself the first time a node's evidence changes. The `due` guard was written twice too -- the first version asserted wording the label beside the name already carried, so it passed without the sentence rendering at all; retightened onto the claim only the sentence makes, and red before green. **Nothing was captured for this** -- the checkpointer held all of it already, exactly as the plan said | landed | `web/src/features/workflows/node-sequence.tsx` |
| CI-W531 | **M15 Task 7: findings fan into the change that caused them, and the two totals reconcile.** Twenty-four findings are thirteen change units, and a flat list is the console asserting there are twenty-four problems by its shape -- one vendor change breaking eleven call sites is one decision. The unit now leads on Findings, each opening to the same `FindingsTable` the flat view renders, so one finding is one object however a reader arrived at it. **The correctness claim is arithmetic**: a grouped view whose parts do not add to the flat total reads as a rounding artefact rather than as a contradiction, so nobody investigates it. The severity therefore narrows findings **before** they are grouped -- a unit then reports the findings of that severity it holds and the sum still equals the flat total on every tab. Filtering units afterwards would leave each one counting findings the reader is not being shown; proven by moving the filter and watching the sum read 2 where 1 was right. `finding_count` is **stated by the payload, never counted from the array beside it** -- counting `findings.length` would report the page rather than the workspace, proven red the same way. Findings rather than call sites: one call broken in two ways is two findings and one site. **No extra query** -- the grouping already fetches each finding's call site, so the nested rows were in hand. The flat view stays one press away because *what must I deal with* and *where exactly* are two questions, and the three guards that asserted the flat table now open it explicitly rather than relying on a default that deliberately moved | landed | `src/sync/dashboard/fleet.py`, `api/app.py`, `web/src/features/findings/change-unit-groups.tsx`, `findings-page.tsx` |
| CI-W532 | **Owner instruction: the three reserved decisions are asked as multiple choice, and silence resolves to the recommendation.** `CLAUDE.md` already said *decide rather than ask*, and this does not weaken it -- it is a rule about **form**, not frequency. What it replaces is the open-ended "what would you like?", which hands the work of framing a decision back to the person with the least context loaded. Options, trade-offs, a recommendation first, enough context to rule in one read. **The safety is the important half**: no answer means proceed on the marked recommendation, recorded as a reversible ruling and surfaced in the next report -- because a question asked and then waited on is the three-hour milestone stall wearing a nicer interface. Two things silence is explicitly **not** consent for, and they are the pair a later commit cannot undo: an irreversible action outside the repository, and a credential or a spend. Stated honestly: this is prose in the file that says prose decays, and there is no failure site to encode it at -- it governs a conversation, not a call site | landed | `CLAUDE.md`, `.claude/rules/autonomous-development.md` |
| CI-W533 | **M15 Task 5: integrations get their own names, and the third-party logo fetch is deleted.** Owner ruling: the neutral generated mark. The interesting half was not the mark but what building it found -- `VendorMark` was constructing a `logo.clearbit.com` URL and rendering an `<img>` from it, **on by default**. Three things wrong, and only the first is about trademarks: it put third-party marks in the product each under its own unreviewed licence; it **called a third party from the operator's browser on every render of every vendor**, telling that endpoint which integrations a customer watches -- a fact about their codebase, which Sync's whole position is to hold as little of as it can; and it made the console's appearance depend on a network it does not control, so a mark that resolves at a desk and not in a locked-down deployment is a screen that looks broken there. Deleted rather than flagged off: a disabled fetch is one edit away from a live one. The mark is now a monogram on a slot from `SERIES_SLOTS`, the categorical palette `DESIGN.md` already argues and whose contrast is already proven -- **no new token** -- hashed from the id so a vendor keeps its colour wherever it appears, because a mark that changed colour between screens reads as two integrations. Colour here is identity, not judgement, and the letters carry it alone. Names come from a small registry, because title-casing gets `Stripe` right and `Openai`, `Github` and `Sendgrid` wrong -- on exactly the vendors most likely to be watched. **An unregistered vendor is the expected case, not an error**: the plugin story is that a third party writes an adapter without touching core, so it gets a derived name that never claims to be more than a guess | landed | `web/src/features/vendors/vendor-name.ts`, `vendor-mark.tsx`, three render sites |
| CI-W534 | **Two stale test fixtures were failing the gate for every session, and `tsc` had not been clean in days.** Neither is a defect in shipped code; both are a test left behind by a change that landed correctly. `tests/test_cli.py` imported `_repo_id` from `sync.cli`, which moved to `sync.index.codebase.remote_repo_id` on 2026-08-18 so that `run` and `sync index` derive one identity from one function -- the move was right and the test kept the old address, and because it was an **ImportError it failed at collection**, taking all 52 tests in the file with it rather than the two that used the name. `subject-catalogue.test.ts` predated `by_service` becoming required on `IndexCoverageResponse`, so four fixtures were missing it and the whole console typecheck was red. `by_service: []` rather than a populated value, because `attachedVendors` never reads it: a fixture should state what the function under test consumes and nothing more. **`npx tsc -b` is clean for the first time in this milestone**, and the console suite is 927 green. Worth naming for the next session: a bare `git worktree` has no `oasdiff` binary, no `node_modules` and no fetch caches, so a suite run there reports failures that are environment rather than signal -- 64 against the real tree's 28. Verify in a worktree; attribute failures against the tree that has the tooling | landed | `tests/test_cli.py`, `web/src/features/signals/subject-catalogue.test.ts` |
| CI-W550 | **The request button becomes a run, and the run becomes a real pull request.** `sync tickets` is the executor the console's POST was waiting for: it claims the oldest requested ticket atomically, loads the finding back out of the graph (`get_finding` -- a ticket names a finding across process boundaries, so the row has to become a `Finding` again), drives the same remediation graph `sync run` drives, and closes the ticket with the run's own terminal outcome. A retracted finding closes as `reported` rather than parking forever, the claim stamps a provisional thread corrected once the real coordinates exist (`stamp_ticket_thread`), and the wiring is proven by tests with the store real and the heavy edges faked, each shown red first. **Proven live**: ticket 11 on demo-v1's retired `claude-3-opus-20240229` became https://github.com/stroland02/demo-v1/pull/1 -- tier-0 swap, tsc, push, the demo repo's own CI green, PR opened, ticket closed `opened`. Seven failed runs bought it, each an honest abandonment naming a real demo-repo defect. **The landing also repairs what the CI-W547-549 rebuild left red**: two BOMs from `Out-File -Encoding utf8` restores were breaking every test that AST-parses the tree (the bulk of 234 failures -- 17 remain, all pre-dating this branch and failing identically on the primary tree); the `service_id` taxonomy is ported through models, schema and store so the indexers' own references resolve; `by_service`/`by_operation` are wired into the coverage payload the console's types already declared; and the eleven console-guard violations the ports carried are fixed at the contract -- geometry transitions dropped, 11px raised to the floor, `focus-visible:` respelled `focus:`, `py-0.5` becomes the token, dead `/settings?group=` links point at the route that exists, `stage-pages` moves to `lib/` so no feature imports the routes registry, chart fixtures return to sentinels, `palette.ts` gets its argued exemption *paid for* by a new parity test holding its eight slots byte-equal to `index.css`, the `_attach_snippets` decode handler gets its census driver, three subsuming clauses get their census entries, the skip baseline moves to 18 deliberately, and three orphan heartbeat store methods are deleted rather than baselined | landed | `src/sync/cli.py`, `graph/store.py`, `graph/schema.sql`, `core/models.py`, `dashboard/fleet.py`, `dashboard/graph_views.py`, `tests/test_tickets_executor.py`, `tests/test_remediation_tickets.py`, `tests/test_decode_handlers.py`, `scripts/dead_links_baseline.txt`, `web/src/lib/stage-pages.ts`, fourteen console files, `docs/superpowers/specs/2026-08-20-beta-mode-validation-and-training.md` |
| CI-W551 | **The patch agent stops seeing tools it may never use, and the suite goes fully green for the first time since the rebuild.** Two live runs on demo-v1 ended as "the remediator produced no change" because the agent reached for `Skill`, the gate refused it -- correctly -- and the attempt died on the refusal. An unlisted tool is not a blocked tool (`CLAUDE.md` records the fall-through), so `Skill` and `Task` join `WebSearch`/`WebFetch` in `DISALLOWED_TOOLS`, denied at the SDK where the model never sees them; a skill *inside* the patch lane stays a designed change against the threat model (a clone can ship hostile `.claude/skills/`), never a name quietly removed from the list. **The other seventeen are fakes and fixtures lagging the restored production layer**, each fixed at the test because the production side was right: the day-one fake gains `call_site_source`; the dependency-intake unbound-vendor set moves from four to sixteen deliberately (the generated-adapter fleet, and the assertion exists precisely so that drift moves a landing); the install-honesty guard derives `npx @stroland02/sync-up` from the manifest the way its sibling always did, and the README sheds a BOM; `test_patch_tool_gate`/`test_patch_tool_output` gain the connected-provider fixture `test_agent_patch` already carries (the runner refuses to run unconfigured, owner ruling 2026-08-19); `RunHeartbeat` is stubbed in the two cli suites whose DSN deliberately resolves to nothing -- existence-reporting is `test_run_heartbeat.py`'s subject; the index-command fake accepts `upsert_codebase_facts`; and the tsc-race fixture gains the `tsconfig.json` that `run_tsc` now refuses to typecheck without. 4,484 passed, 0 failed, `-n0`. No web files changed; the web gates from CI-W550's landing stand | landed | `src/sync/runner/claude_sdk.py`, `tests/test_agent_patch.py`, seven test files, `README.md` |
| CI-W552 | **The agent learns from the corpus before it patches.** The owner's beta-mode ruling (corpus retrieval into the solutions workflow) lands as a per-change lookup: `cli.corpus_lessons_reader(store)` narrows the two closed-vocabulary aggregates -- `migration_outcome_rollup_by_kind` and `migration_outcome_abandon_reasons_by_kind` -- to the finding's change kind and composes attempt counts, abandonment counts and the top reason codes into a bounded block the patch prompt carries under *What past attempts at this change kind learned*. Unfenced deliberately where every vendor sentence is fenced, because the text is Sync's own template over tiers and reason codes and never a quoted sentence; empty appends nothing, the byte-identity guarantee `repo_context` already makes, and the block sits ahead of the scope rules so the strongest instruction keeps the last word. `AgentRemediator` takes a `lessons_for` callable rather than a store, keeping the database driver on the caller's side of the runner seam; both `sync run` and `sync tickets` wire it. Read at call time, not snapshotted: a `--limit 0` run's tenth finding deserves what the first nine taught. **Proven against a live run the same hour**: S1 (a response property removed nineteen levels below the read) ran three agent attempts to an honest `patch_attempts_exhausted` no-change verdict, and the rows it wrote are exactly what the reader now hands the next agent meeting that kind. The run also surfaced the next graph change, filed in the beta spec: a clean no-change verdict should route to `reported` rather than costing two retries and booking a true negative as an abandonment | landed | `src/sync/cli.py`, `src/sync/remediate/agent_patch.py`, `tests/test_agent_patch.py`, `tests/test_tickets_executor.py`, `tests/test_cli.py`, beta spec |
| CI-W553 | **Clear the ground: the bundle carried two keyframes, and the document the guards parse was wrong in three places.** The console's contract says it runs zero animation at rest; `dist/assets/*.css` carried `@keyframes pulse` and `@keyframes spin`, measured on a fresh build rather than a stale one. Neither was visible to a guard: `_ANIMATION_FREE_ROOTS` lists five directories and `vendor` is not among them, so the vendored `Skeleton` was unscanned, and `components/ui/` is excluded by an owner ruling that predates the shadcn `Toaster` nobody ever imported. Both sources are now deleted rather than restyled -- `Toaster` had zero importers and was the only importer of `sonner` and `next-themes`, and the vendored `Skeleton` was reachable only from `SidebarMenuSkeleton`, which nothing rendered. **The new guard is scoped to what actually compiles**: only `animate-pulse|spin|ping|bounce` are core Tailwind; the forty-odd `animate-in`/`fade-in-0`/`zoom-in-95` strings across both catalogs come from `tailwindcss-animate`, which is not installed, so a second test holds it uninstalled -- that absence is the whole reason those strings are inert, and installing the plugin would turn them live in one commit. **Proven red first, and then proven red a second time by accident**: the guard named both files, and the NOTICE entry written to record the fix spelled the utility out and put the keyframe straight back into the bundle. Tailwind extracts candidates from every non-gitignored file in the project, not from `web/src` -- which is the same defect `components/skeleton.tsx` already documents for docstrings, and it means every existing text-scanning guard is narrower than the compiler it protects. **Three authority defects reconciled**: `console-surface.md` claimed state is a named step and never an alpha overlay, which `DESIGN.md` reversed with the substrate, and claimed three spacing tokens with two exceptions where the contract declares four with one -- the tests read `DESIGN.md`, so the rule file was wrong in both. `DESIGN.md` claimed `vendor/supabase/theme.css` carries a light block un-imported; it declares one selector and carries no light block, so a future owner instruction starts at `theme-contrast.mjs`. `PLOTTING_SURFACE` is now bound by test to the hex `DESIGN.md` publishes for `--color-card`, the way the eight series slots already are -- every mark-legibility proof in `palette.ts` is computed against it. `components/3d/` and its three unimported packages are deleted: the README deferred the spatial view to *a spatial fact entering the data*, and the owner's terminal-density direction settles it. `.claude/launch.json` lands on port 5199, never 5173, because `console-dev-loop.md` reserves the owner's console and a worker never serves it | landed | `tests/test_console_design_tokens.py`, `.claude/rules/console-surface.md`, `DESIGN.md`, `.claude/launch.json`, `web/NOTICE`, `web/package.json`, `web/src/vendor/supabase/ui/sidebar.tsx`, four deletions |
| CI-W554 | **Before the cull: the three things that would have been lost silently.** The guard triage classified all 108 console test functions against the owner's thin-core ruling and found that only 48 are substantive -- the other 60 are red-proofs and permit-proofs riding along. Three findings had to land before anything is deleted. **The traffic light was about to come back**: `test_console_raw_utilities.py` retires with the token-ceiling family, but one of its three alternations -- the stock Tailwind palette classes -- is the only mechanical thing standing between `web/src` and a raw judgement colour, and `test_no_colour_literal_outside_index_css` does not cover it because a palette class is neither a hex literal nor an `oklch()` call. Lifted into `test_no_raw_palette_colour_claims_a_judgement` in the file that survives, with its own red-proof; the refusal `web/CLAUDE.md` states three times is not a taste rule that retires with the aesthetic. **The two focus-ring guards contradicted each other**: `:1065` enforces the alpha floor but excluded `components/ui/`, while `:1807` scans that directory and bans the spelling shadcn ships. Under shadcn-as-substrate the floor stopped covering the directory every visible control lives in, so the vendored exclusion is dropped -- and it costs nothing, because the catalog's focus rings were hand-substituted to full strength already and the `/n` rings it does carry are `aria-invalid:` and decorative, which the pattern never matched. **Two tests asserted nothing.** `test_lint_dead_routes.py`'s baseline-expiry check iterates `sorted(KNOWN_DEAD)` where `KNOWN_DEAD` is `frozenset()`, so the comprehension yields `[]` and the assertion cannot fail; deleted rather than repaired, since the rule it encodes is moot with no entries and returns with them. The dialog permit-proof ended on a bare `violations = ...` call with the next line opening a comment block; it asserts now. **Two scanners were blind**: `DEAD` and `LINKS` both `rglob` the console tree with no vacuity assert, so moving `web/src` would have passed them on zero files. Both now fail loudly, and both were proven red against an empty tree rather than assumed | landed | `tests/test_console_design_tokens.py`, `tests/test_lint_dead_routes.py`, `tests/test_console_links_resolve.py` |
| CI-W555 | **Four scanners over one property become one registry, and it caught a third attempt at the same defect in its own docstring.** The owner's motion ruling is that motion is free and *unaccounted* motion is not, so the blanket bans fold into `lib/motion.ts`'s new `KEYFRAMES` registry -- the companion to `MOTION_USAGES`, held in both directions by `test_every_keyframe_that_can_reach_the_bundle_is_one_somebody_chose`. The four predecessors each watched one breadth of the same property (the `index.css` baseline, the raw-text scan, the core-utility denylist, the plugin-absence check) and the gaps between them are where `@keyframes pulse` lived for weeks. **The breadth that mattered was never the rule, it was the scan**: every predecessor read `web/src`, and Tailwind reads the whole project minus what git ignores, which is how a line in `web/NOTICE` explaining that a utility had been removed compiled it straight back in. The new scan is the project, suffix-unfiltered, raw text -- a markdown note is a candidate source exactly as a `.tsx` is. **Proven by the guard failing on its own author**: the registry's docstring named the pulse utility while explaining that naming it is what put it in the bundle twice, and the guard went red on `motion.ts:74` before the commit existed. Third occurrence, first one stopped. **The liveness-pulse refusal is now carried by a type rather than by a side effect**: `KeyframeTrigger` is `interaction | arrival` and the two absent members are the rule -- nothing animates at rest, nothing animates in proportion to a data value. That claim was previously held only as a consequence of the blanket ban being retired, and `web/CLAUDE.md` keeps it in the honesty bucket the owner ruled stays enforced. Twelve functions and eight helpers deleted, five added; the empty registry is the correct state and the fixtures prove it fires on a declaration, on a comment, on a file outside `src/`, and on the forty class names an animation plugin would bring to life in one install | landed | `web/src/lib/motion.ts`, `tests/test_console_design_tokens.py` |
| CI-W556 | **The cull: the aesthetic ceilings retire, and three guards that looked aesthetic were kept because they are not.** Twenty-eight guard functions deleted from `test_console_design_tokens.py` and `test_console_raw_utilities.py` removed entirely, under the owner's thin-core ruling: spacing-token duplication, the 12px type floor, the 600 weight ceiling, the row-height arithmetic, the two-ink-level cap, display-step ownership, the section-step register and the two route-metadata rules all encode the aesthetic that terminal density replaces. The type floor is the clearest reversal -- its own failure message reads *a table out of width takes fewer columns, never a smaller step*, which is the opposite of the direction now chosen. The weight ceiling was forced regardless: it scans `components/ui/` and stock shadcn ships `font-bold`, so it reddens the moment that catalog becomes the substrate. **The `question` guard needed no argument** -- the field it checks is being deleted, so it fails on the first commit of the new direction either way. **Three kept against the triage's letter, and the reasoning is the interesting half.** The geometry-transition family reads as a blanket motion ban and is not one: it permits `transition-colors` unconditionally and permits any transition inside a class string carrying an interaction selector, so what it actually forbids is *motion the reader did not cause* -- the liveness pulse, in the honesty bucket the owner ruled stays enforced. It also cannot be narrowed to the value-bound case, because the guard has no mechanical notion of value-binding: its progress-bar red-proof is the same `transition-all`-without-a-selector shape as its blanket proof, and the value-bound case is caught only as a subset. Dropping the blanket half would have released the progress bar with it. The framer-motion registry stays for coherence -- retiring it would leave framer usage unaccounted while keyframes are accounted one file away -- and the dialog-heading family stays because Radix leaves `DialogTitle` mounted while closed, which put an `h2` ahead of every page's own `h1`: a heading tree a screen reader walks, not a style. **Thirty-one helpers fell out over three cascade rounds**, including `_DISPLAY_STEP_OWNER`, `_cell_classes` and `_panel_title_classes` -- three of the anchors the triage flagged as going *blind rather than red* when a file is renamed, now gone rather than left pointing at files a redesign is about to move. The file is 1,347 lines from 1,936, and 50 tests from 78 | landed | `tests/test_console_design_tokens.py`, `tests/test_console_raw_utilities.py` and its baseline (deleted) |
| CI-W557 | **One skeleton, proved on one screen.** Twenty routed screens carried eight different opening structures -- `PageHeader` on one (and that one a local copy), `Breadcrumbs` on eight, `PageTabs` on six, `DetailGrid` on five, `ControlBar` on four, and three screens using none of the five -- so a reader re-learned the layout on every navigation. `layouts/screen-frame.tsx` lands the four bands: identity, controls, content, status. **They are a reading order across four elements rather than one parent**, because `app-frame.test.tsx` pins `banner.parentElement` to the element that also holds `main` and the sidebar has to stay outside that column -- so a screen cannot render its status inline and publishes through a portal into a `<footer>` beside `main`. The portal target is held in state behind a callback ref: refs attach bottom-up and `main`'s subtree commits before its later sibling, so a ref read during the frame's first render is null and the band never mounts. **All 36 pinned chassis contracts pass untouched**, which is the proof the bands belong where they were put. Status is a row of typed segments rather than one count, because four screens make a single number false -- `RunsPage` counts runs at workspace scope beside corpus attempts at deployment scope, `MetricsPage` has five independent fetches and no instant at which it is loaded. The vocabulary is closed and `none` carries a reason, because a blank band draws *nothing here pages* and *has not answered yet* as the same nothing. **The ratchet is the part that makes this finish**: `screen-skeleton.test.tsx` holds a MIGRATED and a PENDING list whose union must equal every declared address, so a route added later cannot dodge the skeleton by being absent from both, and PENDING can only shrink -- proven red by removing one address and watching it name the omission. `components/table-toolbar.tsx` is deleted: it had no importer outside its own test, and its three formatters move to `lib/record-window.ts` **with their nine assertions re-pointed rather than dropped** -- they are the only coverage `describeRecordWindow`'s branching has. Two defects found in passing and fixed: `globals` is unset in `vitest.config.ts` so nothing cleans up between renders, and the assertion that a band is *absent* is exactly the one that passes vacuously under accumulated DOM; and `DESIGN.md` carried the false vendored-light-block claim a **second** time, which CI-W553 fixed only once | landed | `web/src/layouts/screen-frame.tsx`, `status-band.tsx`, `app-frame.tsx`, `lib/record-window.ts`, `features/vendors/integration-changes-page.tsx`, `DESIGN.md`, three test files |
| CI-W558 | **Seven screens onto the skeleton, and the reviewer stage earned its place.** Batch one of the migration: Metrics, Corpus, Detectors, Runs, Solutions, Vendors and Overview adopt `ScreenFrame`, each by one agent owning one file, with the shared files -- the ratchet, the frame, `app-frame`, `routes.ts`, `DESIGN.md` -- held by the coordinator so nothing raced. Frame adoption only: content restructuring, panel deletions and copy rewrites were deferred and reported rather than done, so every diff stays reviewable. **The batch was green on the gate and still not commit-ready**, which is the finding. An adversarial reviewer over the assembled tree caught two honesty regressions the seven migrators missed. `trends-kpis.tsx` gated its *Days with activity* value on `changes` alone while computing the set from both series, so while findings was pending the tile printed a number from half the data under the same label the new band renders from all of it -- two figures disagreeing on one screen, which is the exact failure the band exists to prevent. The tile had been internally inconsistent since it was written; its own `figure` flag already required both queries. And `codebase-page.tsx` collapsed *coverage has not answered* onto *a counted zero*, then labelled the result with a scope string asserting the measurement happened. Both fixed here. **The ratchet could not see either promotion**: three agents independently reported that its union check is satisfied by moving a string between two arrays and never asks whether the screen renders the frame. A consumer count now backs it, and it lives in the Python guards rather than beside the ratchet because `web/src`'s tsconfig carries no node types -- a `node:fs` import there runs under vitest and **fails `npm run build`**, which is how it was found. Deferred, each with a screen named: the Runs window is stated twice until `runs-table`'s own footer moves, the Metrics band restates three KPI tiles until the strip retires, the Vendors controls bar is left half-emptied, and the Solutions caveats now sit above rather than below the table | landed | seven feature screens, `trends-kpis.tsx`, `layouts/screen-skeleton.test.tsx`, `tests/test_console_design_tokens.py` |
| CI-W559 | **Seven more screens, and five honesty regressions caught before they shipped.** Batch two: Findings, Finding, Services, Pull request, Workflow, Fleet and Binding surface adopt `ScreenFrame`, taking the console to fifteen of twenty-one. The migrators were handed batch one's two failure modes by name and still produced five more, every one of them green on the JavaScript gate. **`reply-box.tsx` kept a protected-class sentence describing a control the same diff deleted** -- *the control is shown rather than omitted* -- while its sibling `run-fact-rail.tsx` had the parallel sentence correctly rewritten, which is what proves it an oversight rather than a judgement; the docstring argued with itself nine lines apart, and the paragraph was `aria-describedby` on the textarea, so a screen reader announced a description of a button that no longer existed. This is `CLAUDE.md`'s opening failure exactly: *seven of twenty-four protected console sentences cited deleted files and nothing noticed for two weeks*. **Findings printed a whole-set claim over a narrowed table** -- *This is all 12 findings* beside a pager stating 75 were excluded -- in code whose own comment cites the decision it was breaking. **Fleet rendered a counted zero as an absence**, defect (B) run backwards: `Repositories indexed` answered zero and the band drew the absence marker, so a measurement that happened was drawn as one that did not. **Workflow's scope explained a gap incorrectly**, which is worse than not explaining it: `activityEntries` is stamped nodes plus a closing entry once the run has an outcome, so nodes-minus-omitted fails to reconcile on every terminal run, and the new test passed only because its fixture had `outcome: null`. **And the same sentence rendered twice**, byte-identical in the band and in `FetchedAt`'s idle reason. **The ratchet was not lying green -- it was red**, in the Python guard `CI-W558` added: fifteen screens import the frame against eight promoted addresses, and `assert 15 == 8` is what a consumer count is for. The reviewer reported the gate green having run only the honesty file. `fleet-facts.tsx` is the fix worth naming: its docstring has argued since 2026-08-17 that a zero over an empty index is absence rather than a measurement, the note said so, and the tile printed `0` anyway -- the status band six inches below is what finally made the disagreement visible. Three tiles now refuse the false zero and `Repositories indexed` keeps its real one. Two `fleet-facts` tests went red on that change and were right to: they asserted a findings count over `repo_ids: []`, which is data that cannot occur, so the fixtures were repaired rather than the rule weakened | landed | seven feature screens, `reply-box.tsx`, `run-fact-rail.tsx`, `fleet-facts.tsx` and its tests, `screen-skeleton.test.tsx` |
| CI-W560 | **The last five screens, and a canvas that stopped tracking the window.** Batch three: File tree, Dependency graph, Call sites, Telemetry and Settings adopt `ScreenFrame`, taking the console to twenty of twenty-one -- only `UnknownRoute` remains, blocked on `PageHeader`'s deletion. **The blocking find is one the migration existed to prevent, moved rather than removed.** Both canvases computed height as `100svh - 16rem`, where `16rem` was a guess at the opener; the graph replaced it with `min-h-[32rem] flex-1` and a docstring claiming the height now comes from the fill band. It does not: `app-frame.tsx:565` sets `items-start` on the `min-h-svh` column, so there is no spare height for a flex child to take, and with only a `32rem` floor the height fell through to the svg's own `1200x700` viewBox -- making the canvas a function of window **width** and never of window height, measured losing 46% at 1024x1200. Floored at `70svh` to match the sibling, and both files' comments rewritten, because each asserted something the measurement contradicts. The sibling's ledger entry was wrong in the other direction -- it recorded that a bare `flex-1` renders zero pixels, and it renders 645 -- so the reason was corrected while the choice stood. **A second contradiction the band made visible**: `codebase-facts-kpis.tsx:85` printed the note `git-tracked` unconditionally while the file tree's new status band said the same numbers came from a filesystem walk, on checkouts where `_tracked_files` fell back. Gated on the census that actually ran. Nothing in the suite could catch it -- `test_console_honesty_sentences.py` asserts fragments exist somewhere, never that two of them agree. **Owned rather than buried:** `scripts/lint_comments.py` exits 1 at 26.9% against a 26.2% baseline, and it has been red since `4c55fe4b` -- one of mine. `CLAUDE.md` calls it an enforced ratchet and nothing calls it, which is precisely the decay the guard triage filed it under. It gets its own commit, trimmed and then wired into the gate, rather than being bundled here. Also deferred and named: `/graph` ships a five-segment band across three states with **no test file at all**, the only screen in three batches to migrate without one | landed | five feature screens, `codebase-facts-kpis.tsx`, `screen-skeleton.test.tsx` |
| CI-W561 | **The comment ratchet goes green and gets a caller, and the graph screen gets tests that bite.** `scripts/lint_comments.py` had been red since `4c55fe4b` -- one of mine -- at 26.9% against a 26.2% baseline, and nothing noticed because `CLAUDE.md` calls it an enforced ratchet and **nothing called it**: not CI, not the suite, not the hook. Six files trimmed to the budget, cutting the category the file names explicitly -- *why a change is correct, which is talking to a reviewer and noise the moment the PR merges* -- which is most of what three batches of migration agents wrote about their own work. Console lands at **26.09%, below the baseline itself** rather than merely inside tolerance, and `.comment-baseline.json` is untouched: nobody moved the target to make the number go green. **Nothing load-bearing was traded for the ratio**, and that was verified rather than asserted -- every bug id and dated ruling counted before and after (`B149` 3->3, `B157` 4->4, `2026-08-19` 12->12), and the code was proved untouched byte-level by stripping comments from both the `HEAD` blob and the working tree and diffing the remainder: zero code lines and zero JSX text nodes changed across all six. One comment was corrected rather than cut -- `signals-page.tsx` claimed a breakpoint guarded against a single column when that breakpoint *produces* one. **`tests/test_comment_budget.py` is the part that matters**: the ratchet now has a caller, plus a second test proving the guard reads the exit code rather than merely running something, which is the exact shape `CI-W534` recorded the import-boundary guard failing in. **The first red-proof did not go red** -- 220 narration lines left it green -- so rather than assume the wiring worked, the threshold was computed (baseline plus 0.005 tolerance needs ~0.86% of the tree) and it was re-proved at 800 lines, where the script exits 1 and the test fails. **And the new `/graph` tests had two dead assertions**, found by mutating the source rather than the assertions: `queryByLabelText(FORCE_MAP_LABEL)` is null whether the page gates the map or the map mounts and draws nothing, because `force-map.tsx:317` returns early on an empty node set -- so deleting the drawn-state gate left all twenty green. Giving the fixtures bindings was the wrong repair (the state is derived from them); asserting the map's own empty-state prose is absent is the right one, and deleting the gate now fails both | landed | six console files, `tests/test_comment_budget.py`, `index-graph-page.test.tsx` |
| CI-W562 | **The identity band is mounted, and the adapter catalogue stops answering for a query that did not.** `ScopeTrail` returns to the chassis banner, three bands becoming four. It was pulled in 2026-08 because it and the sidebar were two navigation systems that could disagree about what *Overview* meant; it returns because every segment derives from `useLocation()`, so it restates the address rather than holding an opinion about it, and it renders before any query resolves -- a bar that waits on `/api/overview` to say where you are says nothing on the slowest navigation, which is when a reader needs it most. `EnvironmentBadge` moves to the right group beside the palette trigger. **All 36 pinned chassis contracts pass untouched**, which is what the skeleton spec predicted and the reason the band went in the existing banner rather than a new wrapper. **The second half is a shipping honesty defect**: `repository-vendors-page.tsx` built its adapter map from `data?.adapters ?? []`, so a catalogue that errored rendered the badge `none` on every row -- a positive claim that these vendors have no adapter, from a query that answered nothing -- and zeroed every tier count, which the `count === 0` rule then removed, so the whole facet vanished rather than saying why. Both now distinguish the catalogue not answering from a vendor genuinely having no adapter. **The test is the part that was missing**: the screen's suite mocked `useRepositoryCoverage` and let `useAdapters` run unmocked, so no case existed for the error path at all. Two were added and both proved red against the original -- the badge assertion first failed showing the `none` element, then, once fixed, failed again because `getByText` found one absence per row where the assertion expected one on the page. That second failure is the fix working, and the assertion was widened rather than the behaviour narrowed | landed | `layouts/app-frame.tsx`, `features/vendors/repository-vendors-page.tsx` and its tests |
| CI-W563 | **The identity band carries something: fifteen per-screen openers retire into the chassis.** With `ScopeTrail` mounted, ten screens were still rendering their own trail below it, so two elements stated position. Nine `Breadcrumbs` call sites were pure duplication -- each passed a single static label the registry already holds and `ScopeTrail` already derives -- and all nine are gone. The six `PageTabs` strips become one chassis-owned `ScreenTabs`, because the defect they carried is structural: **six screens each hardcoded a strip naming the *other* screens**, so a route rename had six edit sites and any one could be missed. Membership is now a fact about the registry, and `screen-tabs.test.tsx` holds every named address against `ROUTES` -- proven red by naming one route does not declare. **The match is on the address a screen IS, never one it starts with**: `/findings/:findingId` is a detail screen under Findings, and a prefix match would render the strip there with neither tab current. `components/page-tabs.tsx` is deleted, but not before the two things it carried moved across: its decision with a live alternative (links rather than the vendored `Tabs`, which owns selection state and renders every panel's subtree -- here mounting several data-fetching screens to show one), and `chipSurface`, which the first draft of `ScreenTabs` had replaced with classes invented on the spot. `layouts/breadcrumbs.tsx` stays: `ScopeTrail` uses it internally, so it is not dead, only no longer a screen's business | landed | `layouts/screen-tabs.tsx` and its test, `layouts/app-frame.tsx`, ten feature screens, `components/page-tabs.tsx` deleted |
| CI-W564 | **The palette groups by the same five headings as the rail, and stops needing the question.** Two changes with one prerequisite. `stageOf` covered fourteen of nineteen routes -- the five subject-taking ones (vendor, binding surface, finding, workflow, pull request) had no stage at all, because `workspacePages()` filters on the parameter list and none of them joins the Overview's pipeline. That was harmless while the palette grouped by graph level and fatal the moment it grouped by stage: `command-palette.test.tsx` asserts every declared route appears exactly once, so a route with no stage silently vanishes from the console's own map of itself. All five now carry one, and removing a single entry was proven to fail that assertion. **The palette regroups from nine graph levels to the rail's five stages**, so a reader who learns the rail's headings does not meet nine different ones the moment they press Cmd-K. Settings keeps its own group rather than being filed under a stage -- it is on no pipeline stage, and `Index` would assert a place in the run it does not have. **`question` leaves the palette row**: it never rendered there, it only fed the search string, and the field is retiring | landed | `lib/stage-pages.ts`, `layouts/command-palette.tsx` and its test |
| CI-W565 | **Three silences become three answers, and the file that pinned the defect now pins its repair.** `tools.py`'s `_change_for` caught `(KeyError, LookupError, ValueError)` and returned `None`, so a finding with no change recorded, one whose change the graph lost, and one whose row this build cannot parse all rendered `change_kind: null` beside `spec_diff: {}`. `tests/test_mcp_tool_declines.py` had **already recorded this**, in a test named `test_the_three_silences_are_one_answer_to_an_agent` whose docstring calls it *the finding this file exists to record* and the behaviour *pinned rather than endorsed*: an agent had no field to branch on, and `binding_source` describes how a binding was established rather than whether reading it succeeded. `_change_lookup` now returns the change and, when there is none, which nothing it is; the at-risk row carries `change_absent_because`. Only two of the three are actionable and those two were the ones being hidden. **The severity CHECK constraint was NOT added, and that is the point**: `schema.sql` argues against it across three measurements -- a CHECK on a column definition never reaches a database that already has the column, because `apply_schema` re-issues `ADD COLUMN IF NOT EXISTS` and Postgres skips the whole item, so it would land on every database created after the edit and none of the ones that predate it, *which is the only place a hand-written row can be*. **Absent and believed present is worse than absent.** The unreadable row is permitted by design; what was wrong was reporting it as absence. **Two existing tests caught two mistakes in the fix.** Adding the reason to the evidence payload broke `test_the_response_carries_the_three_fields_the_spec_names` -- `sync.core.Evidence` names three fields and its own docstring already refuses a fourth -- so evidence is unchanged and the distinction lives on the console's own row shape. And the first wording embedded the exception text, which quotes the row that failed validation: an assertion that `catastrophic` stays out of the payload caught an unvalidated vendor string being handed to an agent inside a field describing the failure | landed | `src/sync/mcp/tools.py`, `tests/test_mcp_tool_declines.py`, `tests/test_mcp_tools.py`, `tests/test_mcp_provenance.py` |
| CI-W566 | **Three compatibility reviewers adopted from `cursor/plugins`, and twenty SaaS connectors deliberately not.** That marketplace is structurally close to this harness -- its `skills/` are `SKILL.md` with frontmatter, the same format -- so the portable part ports cleanly. Twenty of its thirty-three entries are SaaS integrations (Salesforce, HubSpot, Zoom, Gmail), the same category the console's own plugin trim measured at roughly 15,000 tokens per session against a stack that is not here; none is adopted. What is adopted is `agent-compatibility`'s three read-only reviewers -- docs reliability, cold start, and whether a small change can be verified without the whole-tree loop -- because **docs-versus-reality drift is the defect class this repository keeps paying for**: a ratchet `CLAUDE.md` called enforced that nothing called, a false claim about a vendored light block made twice, a docstring describing a control the same commit deleted, and a component arguing a rule in prose since 2026-08-17 while the tile beside it broke that rule. One upstream line is uncanny in this tree -- *do not infer a startup failure from a lockfile, a bound port, or an existing repo-local process by itself* -- which is the zombie-socket trap `console-dev-loop.md` documents and a session hit the same day, where `netstat` and `pg_ctl status` both reported a Postgres that was dead. **What was changed rather than copied**: upstream opens by running a published Cursor CLI scanner and blends its deterministic score at seventy percent; that CLI is not installed here and would be a third-party dependency for a review that does not need one, so the step is dropped and each reviewer reads this repository's own surfaces, grounded in the measured local instances above. `readonly: true` becomes a tool list with no Edit or Write. MIT, so `.claude/agents/NOTICE` carries the licence, the pinned commit `461255613064`, and what was taken against what was changed -- the discipline `web/NOTICE` already sets. **`continual-learning` is refused on argument, not oversight**: it appends prose bullets to `AGENTS.md` on a cadence and excludes evidence metadata, which runs against *encode a rule where it fails, not where it is read* and against `CLAUDE.md`'s own warning that adding to it is the most expensive change available | landed | `.claude/agents/` -- three reviewers and a NOTICE |
| CI-W567 | **`AGENTS.md` pointed ten rules at a directory that does not exist, and the guard that found it was ported the same day.** A find-replace had turned every `.claude/rules/` citation into `.Codex/rules/` -- a path holding only `hooks.json` -- so every pointer from the shared agent-context file to a stage rule resolved to nothing. **A missing include reads as no rule rather than as an error**, which is why two weeks of sessions could pass without noticing: an agent reading `AGENTS.md` as its primary surface silently lost remediate-stage, signal-stage, graph-grain, console-hierarchy, console-surface, interface-originality, test-discipline, console-dev-loop and autonomous-development at once. The same substitution set the model to `claude-opus-5` spelled as Codex and renamed the Claude Agent SDK, while leaving `ClaudeAgentOptions` in the snippet below untouched -- which is what shows it was a replace over prose rather than a decision. All fourteen repaired, and every path the file now names was checked to resolve. **A third staleness in the same file**: it claimed two rules load on every turn, but `interface-originality.md` was scoped on 2026-08-19 and has carried `paths:` frontmatter since, because `hook_guard_reads.py` blocks the competitor screenshots deterministically and the rule no longer has to load everywhere to fence them. One rule loads that way, not two. **Found by the `docs-reliability-review` agent adopted in CI-W566**, whose whole subject is documented paths drifting from the tree -- on its first run, against the repository that ported it | landed | `AGENTS.md` |
| CI-W568 | **The corpus reader raised on the only input it exists to serve, and a test double hid it.** `corpus_lessons_reader` composes two aggregates, and they spell their tally differently: `migration_outcome_rollup_by_kind` emits `count(*) AS attempt_count`, while `migration_outcome_abandon_reasons_by_kind` emits `count(*) AS n` (`store.py:2928`). The reader used the first spelling against the second, so `lessons()` raised `KeyError: 'attempt_count'` the first time the agent tier was asked to patch a change kind with **any** prior abandonment -- which is precisely the case CI-W552 built the block for; a kind never attempted returns the empty string and never reaches the loop. Proven by calling the reader against a store double carrying `GraphStore`'s real column names and watching it raise, then again after the fix. **The failure was invisible twice over**: it surfaced as a `make_patch` exception folded into `feedback`/`abandon_reason`, so it read as a patch failure rather than a lookup bug; and `tests/test_tickets_executor.py`'s double returned `attempt_count`, the other rollup's spelling, so the suite asserted against a shape the store does not produce. The double is corrected to `n` and the reader red-proved against it -- reverting the reader now fails `test_the_corpus_teaches_the_agent_about_its_change_kind` rather than passing quietly. **Found while researching what a vendor knowledge base would retrieve**, which also corrected a premise worth recording: `vendor_change` is not a history table. `truncate_signal_and_detect` runs `TRUNCATE vendor_change, finding` at the head of every scan (`cli.py:1105`), so `raw` gives re-derivation within a run rather than durability across them -- and `migration_outcome` is the only append-only vendor-adjacent table, carrying no vendor payload. That is the gap any corpus has to close first | landed | `src/sync/cli.py`, `tests/test_tickets_executor.py` |
| CI-W569 | **The acquisition chain became runnable, and running it found two dead vendors.** `scripts/demo_signal_chain.py` walks Signal's real path for one vendor -- the `generated-vendors.yaml` row, the manifest fetch, `parse_manifest`, the specification fetch -- using the product's own parser rather than a re-implementation, and prints every URL. `--all` sweeps the registry. It exists because the chain was only describable in prose, and prose is what decays. Three things it measured that no test asserted: end-to-end coverage is **6 of 16** configured vendors, not sixteen; **openai's `.stats.yml` is 404** at `openai/openai-python`, so the most-called vendor in the corpus is watched by a stale row; and **mistral's manifest is genuine but names `registry.speakeasyapi.dev/...` references rather than URLs**, which `parse_manifest` collapses to `None` -- indistinguishable from Cloudflare, which publishes no spec at all. The last is a live instance of the honesty rule `schema.sql` states: absent and believed present is worse than absent | landed | `scripts/demo_signal_chain.py` |
| CI-W570 | **The decode census still described a method renamed out from under it.** `CI-W565` split `GraphSurface._change_for` into `_change_lookup` with two clauses where there had been one, and `SUBSUMING` kept the old key -- so `test_no_entry_in_the_subsuming_census_is_gone` and `test_no_subsuming_chain_in_src_is_unaccounted_for` had both been red since that commit, one for a census line describing nothing and one for a real `except ValueError` nothing accounted for. `UnicodeDecodeError` subclasses `ValueError`, which is why only the narrower half of the split appears: the missing-row half catches `KeyError` and `LookupError`, which subsume nothing. Both tests were watched red before the edit and green after | landed | `tests/test_decode_handlers.py` |
| CI-W572 | **The skeleton ratchet claimed twenty migrations and had verified none of them.** `screen-skeleton.test.tsx` partitioned addresses between `MIGRATED` and `PENDING` and never rendered one, so twenty entries were a claim rather than a finding -- the vacuously-green shape `.claude/agents/validation-review.md` already names twice. It now renders the real chassis and reads the `data-band` that `ScreenFrame` stamps, in both directions: a `MIGRATED` screen must show a content band and a `PENDING` one must not, which is what makes the first half provable rather than a query that matches anything. Its first honest run went red on `/graph`, and the cause was the guard's own environment rather than the page: jsdom ships no `EventSource`, `useRepositoryEvents` constructs one on mount, and the `ErrorBoundary` caught the `ReferenceError` -- so the fallback answered every assertion meant for the screen. Stubbed in `test-setup.ts` beside the three gaps already there. 20 migrations now proven, 1 pending proven pending | landed | `web/src/layouts/screen-skeleton.test.tsx`, `web/src/test-setup.ts` |
| CI-W573 | **Health on the row, test signals, and the improvement loop -- planned against what is already built.** Researched before designing, and the headline is how little is new: `observed_call` already carries `binding_rung`, `spans` and both timestamps, `observed_error_window` already carries `status_class` and `error_count`, so **the row strip needs no new capture at all** -- it is an aggregation read. `benchmark/axes.py` already scores `wall_ms`, `tokens` and `routing_accuracy`, which is speed, cost and accuracy pointed at the patch agent rather than at the integration. `runner/provider.py` already holds the owner-ratified read-never-held credential pattern that a live vendor call would extend. Two owner rulings taken: **both tiers, staged** (spec re-run first, credentialed call second) and **any key with a confirm** (sandbox-only offered and declined, so the confirm is specified un-defaultable and recorded). Three constraints named that the request did not: absent must never render as healthy; a Tier-2 run is an observation *Sync caused* and poisons every downstream denominator unless `observed_call` gains a source marker the way `observed_error_window` already has one; and `remediation_ticket.finding_id` is `NOT NULL`, so an improvement request cannot ride the findings table without corrupting the finding count | landed | `docs/superpowers/plans/2026-08-23-integration-health-and-the-improvement-loop.md` |
| CI-W574 | **One operation, two resolvers, two names.** `ExtractedOperation` gains `operation_id`, `service_id` and `languages`, all optional and all `None` for every rule that reads an SDK checkout -- a checkout states a route, not the specification's name for it. `operation_for_symbol` honours a stated id, honours a stated service, and refuses a symbol whose rule named languages this caller is not among; a rule that states nothing resolves for everyone exactly as before, so the four registered rules are unchanged. The half that made this a defect rather than an addition: `operation_for_request` kept synthesising `"GET /v1/charges"` and passing no service, so a specification-reading rule would file the static and observed rungs of one operation under two different `operation_id` values -- and `operation_id` is what a finding joins a vendor change against, so neither would ever meet the other. Caught by `test_both_entry_points_answer_one_operation_the_same_way`, watched red on the service mismatch before the fix. Suite 4,482 passed; the four failures are three missing `.cache/corpus` fixtures and one parallel-run database race, all green in isolation | landed | `src/sync/signals/generated/symbols.py`, `adapter.py`, `tests/test_generated_adapter.py`, `tests/test_extracted_symbols.py` |
| CI-W575 | **Mistral was filed under Cloudflare's reason, which is the opposite claim.** Cloudflare publishes an endpoint count and no location -- nothing exists to fetch, and the repair is a hand-written adapter. Mistral publishes three genuine locations behind its own Speakeasy token. `_parse_speakeasy` returned `None` for both, so the console told an operator to write an adapter for a vendor that already publishes a spec. `SpecSource` gains `spec_reference`, recorded only for the documented `registry.speakeasyapi.dev/` form -- narrowed after the first attempt swallowed `./openapi.yaml`, which is a local path naming nothing and must keep returning `None`. A fetchable URL anywhere in the manifest still wins over a reference anywhere else. `observability()` answers a fourth reason, `SPEC_UNREACHABLE`, and the three-ways test is now four. **The half that would have made this cosmetic:** `execute_intake_attempt` defaults `reason_code` unconditionally, so a verdict with no branch was persisted as `spec_url_unconfigured` and the distinction died at the database boundary -- asserted on the stored code, watched red. And `schema.sql` called the vocabulary `seventeen-member` with nothing holding it there (the only check was a `>= 15` floor): the count is now tied to the code by a test that went red on `17 == 18` the moment the member landed | landed | `src/sync/signals/generated/manifest.py`, `generated/adapter.py`, `signals/intake_attempt.py`, `graph/schema.sql`, three test files |
| CI-W576 | **What the two hand-written symbol rules emit, pinned before they move.** Track A moves `stripe.symbols` and `twilio.symbols` into the extraction-rule registry, and a move is only safe if it changes nothing -- which is a claim somebody has to be able to check. Three digests measured by execution: stripe without the SDK document `cf8641cc` (272 entries), stripe with it `808500e3` (272), twilio insights v1 `3aa3ba31` (17). The two stripe digests are asserted **unequal**, or the file would pass against a rule that ignored the SDK document entirely -- the one input whose loss would otherwise be silent. Field sets are pinned separately from digests because a digest cannot say whether a value changed or a field vanished, and the two rules legitimately differ: stripe derives `languages`, twilio does not. **Deliberately not the same artifact as `benchmark/corpus/symbol_map.yaml`**, which pins the committed `vendor-cache/stripe/symbols.json` -- baked before these builders gained `service_id`, four keys per entry against the builder's five, so holding the builder to the cache would demand the rebake this sequence must not do. Red-proved by renaming one field: three tests went red, the twilio pins correctly stayed green | landed | `tests/test_symbol_rule_characterization.py` |
| CI-W577 | **The extractor registry read one member of a three-member contract.** `EXTRACTORS` was a dict comprehension over `module.GENERATOR`, so a module missing `extract_symbols` or `report_extraction` registered successfully and failed much later inside `_extracted_symbols` -- where the traceback names the adapter rather than the rule that is actually incomplete. `register_extraction_rules` validates all three where a rule registers, and refuses two rules claiming one name rather than letting the later silently replace the earlier: nothing collides today, and Track A registers two more rules, where a copied module with an unchanged `GENERATOR` would delete a working rule with every test green. Held over the shipped registry as a property, so a fifth rule inherits the check by existing. **Two rulings against the adjudicated sequence, both recorded in the plan:** A4's package rename moves to the end -- measured at 73 files for no capability, and a package can only be named for what it holds once A12 and A13 have put six rules of two kinds in it. And A5 narrowed to the structural check alone: `INPUT` and `LANGUAGES` have no reader until a specification-reading rule registers, and `CLAUDE.md` calls an abstraction for an anticipated second caller debt with no asset behind it | landed | `src/sync/signals/generated/adapter.py`, `tests/test_extraction_report_contract.py` |
| CI-W578 | **The uniform tier could only resolve a symbol from an SDK checkout.** Both hand-written adapters resolve from a `symbols.json` their preparer wrote, so moving stripe or twilio onto the tier before it could read one would have been a silent downgrade -- every call site stops resolving and the run reports zero findings rather than an error. `GeneratedSpecAdapter` takes `symbol_map_path` and prefers it over the checkout rule where both are staged, because a rule that read a specification states the operation's own id and service and a checkout states neither. Two details the committed artifacts force: the file keys the fully-dotted chain while the adapter keys without the vendor root, so the root comes off on read or nothing ever matches; and every field but the route is read with `.get`, because the committed caches carry four keys per entry and no `service_id` -- baked before the builder emitted one, with their bytes pinned by `benchmark/corpus/symbol_map.yaml`, and rebaking them is what that pin forbids | landed | `src/sync/signals/generated/adapter.py`, `tests/test_generated_adapter.py` |
| CI-W579 | **Sixteen vendors declared which package a customer imports, and nothing read it.** Every configured row in `generated-vendors.yaml` carries `sdk_bindings`, `GeneratedVendor` holds them, and `vendor_sdk_bindings()` returned `_CODED_ADAPTERS` alone -- so sixteen vendors were watchable in principle and bound no call site in fact, which is a scan that reports zero rather than reporting a gap. The gap was *recorded*: `test_a_registered_vendor_that_declares_no_binding_is_visible_as_such` asserted `bound == {stripe, twilio}` and called itself the finding this task surfaces rather than fixes. Rewriting it was the red proof. Seven classification tests moved with it and are corrected rather than relaxed -- the WATCHABLE middle category is now proved by **withholding** a binding explicitly, because a test waiting for a shipped row to be missing one asserts a property of the configuration file rather than of the classifier. Two guards fired usefully: `test_no_configured_vendor_is_named_in_the_registry_itself` caught a vendor name in my own docstring, and regenerating the catalog exposed that `_registry_packages` filtered on `package` alone -- so every **Python distribution** had been dropped from every page silently, npm naming a lockfile entry `package` where PyPI names it `distribution`. Catalog regeneration went from 7 files to 18 | landed | `src/sync/signals/registry.py`, `scripts/build_integration_docs.py`, `tests/test_dependency_intake.py`, `tests/test_integration_catalog.py`, 18 catalog pages |
| CI-W580 | **A row may name its specification instead of discovering one.** Discovery through a generator manifest was the only way the tier could reach a specification, which made having a manifest the definition of having a spec -- and three vendors falsify that: stripe pins its document at a git tag, twilio publishes one per product, and openai deleted its `.stats.yml` outright. `GeneratedVendor` gains `spec`, `manifest` becomes optional, and **exactly one** is required: a row naming both leaves the winner to whichever branch is read first, and a row naming neither is a vendor that appears configured and is not. Both refusals are tested. A direct row fetches no manifest at all, asserted by monkeypatching `fetch_manifest` to raise -- the manifest read exists to ask where the specification is, and the row has already answered. The ref sits in the path, so two versions are two documents rather than the `ONE_DOCUMENT` trap that already silently disables two configured vendors. `SpecSource.generator` reads `direct` and is descriptive only: verified that the extraction rule is chosen by the staged `sdk_generator.txt` and never by that string, which is the silent-wrong-reader trap the design flagged | landed | `src/sync/signals/registry.py`, `tests/test_generated_registry.py` |
| CI-W581 | **OpenAI's row pointed at a 404 for eleven days with every gate green.** `openai/openai-python` deleted `.stats.yml` on 2026-08-12 in a commit titled *remove Stainless attribution and infrastructure* -- they left the generator, so no manifest convention this deployment reads applies to them any more and repointing within the manifest tier could not have fixed it. The row becomes `spec: api_reference/openapi.transformed.yml`, measured live and genuinely diffable rather than one document served twice: **2,868,834 bytes at v3.3.1 against 2,757,171 at v3.0.0**, 404 at v1.99.0 so the usable window starts after v2. **The class of defect is closed, not just the instance.** `generated-vendors.yaml` claimed every entry was confirmed by fetching it on a date and nothing enforced that sentence; every other gate reads committed fixtures and is structurally unable to notice a vendor deleting a file. `tests/test_vendor_configuration_reachable.py` HEADs every shipped row, under a new `network` marker deselected by default -- network but no model and no spend, so it is distinct from `e2e`. Run before the repoint it named openai and only openai; it carries its own can-this-fail test, because a reachability check that has only seen reachable things has proved nothing. Four guards learned the alternation, and the field check now asserts *no unknown field* and *exactly one of manifest and spec* rather than set equality, which would have demanded both | landed | `generated-vendors.yaml`, `tests/test_vendor_configuration_reachable.py`, `pyproject.toml`, three guard files |
| CI-W582 | **A vendor's specification may be several documents.** One vendor publishes sixty per version and a customer calls two of them; the tier held one `SpecSource` per version, so moving such a vendor onto it would diff the first document and stay silent about the other fifty-nine -- which reads exactly like a vendor that shipped no breaking change. `sources` now normalises to a tuple **at the constructor**, so all five existing call sites keep passing one and nothing below asks which shape it got. Three properties the fan-out has to hold and is tested on: `observability` checks **every** document and returns the first refusal rather than the first success, because half a diff presented as a whole one is the failure this product exists to prevent; the cheap hash trigger is asked **per document**, so an unmoved sibling is skipped without skipping the ones that moved; and `SpecSource.label` goes into the cache filename, because two documents in one version would otherwise share `{vendor}-{version}.json` and the second fetch would read the first back and diff a document against itself. Records carry `sync_source_document` so a reader knows which document produced each | landed | `src/sync/signals/generated/adapter.py`, `generated/manifest.py`, `tests/test_generated_observability.py` |
| CI-W583 | **A row declares which oasdiff kinds its vendor's releases make noise with.** Both hand-written adapters drop `response-property-enum-value-added`, duplicated deliberately -- twilio's comment says *the duplication is the signal; it is reported, not resolved here* -- because promoting it to core is shared state across packages and importing one adapter from another is the coupling the plugin boundary exists to prevent. A per-vendor row is the third option. **This runs against a measured decision and does not overturn it:** `2026-07-29-generated-vendor-noise.md` found that same kind is the *sole route* to the affected operations for the configured vendors -- for one openai window it was every record and every operation -- so filtering it would report a release as no change at all. That is an argument against one list applied to everyone, not against a vendor stating its own habits. The default is empty, every existing noise guard still runs against a declaring-nothing adapter, and `test_the_shipped_configuration_declares_no_noise_kinds` fails the moment any row declares one, so the decision gets made deliberately rather than by inspection. The noise file's own claim that *these tests fail the moment somebody adds a filter of any shape* is no longer literally true and now says what is | landed | `src/sync/signals/generated/adapter.py`, `signals/registry.py`, `generated-vendors.yaml`, `tests/test_generated_adapter_noise.py` |
| CI-W584 | **Eleven test files built `StripeAdapter` to resolve a symbol, and none of them was about Stripe.** They needed something that turns `stripe.charges.retrieve` into an operation and a request path back into the same one; the hand-written adapter was simply the only thing that could. Since `CI-W578` the uniform tier reads the same staged `symbols.json` those tests already write, and `CI-W574` made both entry points agree -- checked before moving anything, by constructing both adapters over one map and comparing three symbol lookups and two request correlations, all identical. A shared `symbol_resolver` helper in `conftest.py` keeps the next constructor change from being eleven edits. This splits A12: the deletion is the next commit, and it is small now that only the registry and the adapter's own tests name the class | landed | `tests/conftest.py` and eleven test files |
| CI-W585 | **The stripe symbol rule leaves the vendor package for the rules directory.** `sync.signals.stripe.symbols` becomes `sync.signals.generated.symbols_stripe_openapi`, repointed across 23 files. Nothing else changes, and that is the whole claim: `CI-W576`'s digests are the gate, and all three held byte-identical across the move -- which is what that commit was written a day earlier to make checkable. It is **not** registered in `EXTRACTORS` yet, deliberately: its contract is `build_symbol_map(spec, sdk_spec)` where a registered rule states `extract_symbols(source_root)`, so registering it now would fail `CI-W577`'s validator, correctly. Reconciling the two contracts is what the row needs and is the next commit. The package it left still holds `StripeAdapter`, which is what A12c deletes. Ruling recorded: A12 splits a second time, because relocate-and-prove and register-and-delete are different risks and one diff cannot show both | landed | 23 files |
| CI-W586 | **Stripe is a configuration row, and `StripeAdapter` is deleted.** The first vendor off a hand-written adapter. Everything the class knew is in the row: the specification at a git tag, the SDK document beside it, the symbol rule that reads both, the noise kind its module comment judged, and the bindings. `src/sync/signals/stripe/` is gone and `_BUILDERS` holds twilio alone. The `gh` subprocess went rather than generalised -- `raw.githubusercontent.com` serves `spec3.json` at 7,866,866 bytes unauthenticated. **The regression this nearly shipped:** `_stage_symbol_map` passed one argument where the retired preparer passed two, silently dropping the SDK document -- the difference is `subscriptions.cancel` resolving instead of `subscriptions.del`, and the rule digests cannot see it because they pin the rule, not the staging. `test_cli` caught it; the row now names `sdk_spec` and degrades to the HTTP-verb derivation when a tag publishes none, as before. Two further defects found by moving: `unbindable_reason` read only the checkout, so a vendor resolving perfectly from a staged map still declared itself unbindable; and a staged map rooted at another vendor would stage cleanly and resolve nothing, silently -- refused now. Three guards fired as designed: the noise ratchet, the decode census on my own catch-all, and `test_cli`. Two tests stopped proving anything and were repaired rather than relaxed -- the unresolvable-vendor pair patched only `prepare_vendor` while `load_vendor` now succeeds by design | landed | 30 files |
| CI-W587 | **A row may name several documents, and the twilio rule moves to the rules directory.** The groundwork A13 needs. `sync.signals.twilio.symbols` becomes `sync.signals.generated.symbols_twilio_oai` with `CI-W576`'s digests holding byte-identical again, and a row's `spec` may now be a list of `{path, domain, version}` rather than one path. The mount is declared rather than derived: a twilio chain is `<domain>.<version>.<resource>.<verb>` and neither half can be read off the path. Verified before designing for it that these documents are reachable the same way stripe's is -- `twilio/twilio-oai` at tag `2.3.0` serves `twilio_api_v2010.json` at 1,968,941 bytes unauthenticated -- so twilio is a multi-document direct-spec row rather than the pre-staged-directory shape its retired preparer assumed. `_spec_source` now returns a tuple **uniformly**, so nothing downstream asks which shape a row produced, and the cheap-trigger check fans across every document. One map across all of them, because a call site names a symbol and not a product -- the chain already carries the product | landed | `src/sync/signals/registry.py`, `generated/spec_rules.py`, `generated/symbols_twilio_oai.py`, `tests/test_generated_registry.py` |
| CI-W588 | **Twilio is a configuration row, and the registry names no vendor at all.** Track A's closing condition. `_BUILDERS` and `_CODED_ADAPTERS` are empty, `registered_adapters()` reports one kind, and all eighteen vendors are rows. The `coded` kind stays in the vocabulary: `_BUILDERS` is the extension point the module offers a third party, and empty is that offer standing open rather than dead code. **The capability that would otherwise have gone with the adapter:** `TwilioAdapter._spelled` rewrote a TypeScript `callSummaries` into the map's `call_summaries` key at *lookup* time, so deleting it would have lost TypeScript resolution for twilio silently. The rule now records both spellings with the language that writes each -- what stripe's rule already did, and what `CI-W574` taught the tier to filter on -- so `CI-W576`'s twilio digest was **re-pinned deliberately**, seventeen entries to twenty, with the old value and the reason recorded beside it. Verified before designing for it that `twilio/twilio-oai` serves each product at a tag unauthenticated, so the retired preparer's claim that 61 downloads were outside an adapter's business no longer decides anything. The closing condition is now a guard rather than a sentence: `test_the_registry_names_no_vendor_at_all` reads every registered id against the module source, on word boundaries -- a substring search reported `orb` inside *forbids*, and a guard that cries wolf gets loosened rather than read | landed | 18 files |
| CI-W589 | **`sync vendors probe` — finding a stale row stops requiring pytest.** `CI-W581` closed the class of defect with a network-marked test, and a test is the wrong shape for the person who needs the answer: it asks them to know a marker name and a deselect rule. The command resolves every configured row against its live source, HEAD rather than GET because the question is whether the row still points at something and a specification is megabytes, and names each document of a multi-document row separately -- naming the vendor alone would leave an operator opening four URLs by hand. Run live: **18 rows, 21 documents, 21 reachable, exit 0**. The fetch is injected, so all four tests run in the default suite and the command reaches the network only when a person runs it. Two guards fired on the new code and both were right to: the decode census on the probe's catch-all, and `test_feed_publish`'s no-network check -- which grepped **the whole of `cli.py`** for `urlopen`, so a command whose entire job is to reach the network tripped a guard about publishing. Scoped to `inspect.getsource(publish_feed)`, because a whole-file ban a legitimate command trips gets deleted rather than narrowed | landed | `src/sync/cli.py`, `tests/test_vendors_probe_command.py`, `tests/test_feed_publish.py`, `tests/test_decode_handlers.py` |
| CI-W590 | **The shared extraction report stops naming one rule.** A4, and it is not the package rename it was deferred as. The deferral was taken so the package could be named for what it finally holds -- and `generated` turns out to be false of none of it, so renaming 125 import references is the polish `CLAUDE.md` says competes with the milestone. What the deferral surfaced instead is a real defect the rename would have papered over: `ExtractionReport.render` read the module-level `GENERATOR` of the rule that happened to define it, so an extraction by any other rule would have told an operator that `stainless-python` read the SDK. Three rules each subclassed the report to substitute one string, each imported another rule's identity to `removeprefix` it, and all three docstrings said the same thing. The report now carries `rule`, stated by whoever produced it -- naming the producer is the entire point of the line. Three subclasses, three cross-rule imports and roughly forty lines of near-identical prose go with it. Ruling recorded in the plan's ledger | landed | four rule modules |
| CI-W591 | **The migration corpus becomes Precedent, and only it.** The word named three things in this tree and the owner renamed one: the proto-RAG. The other two are the frozen benchmark corpus under `benchmark/corpus/` and the fetched repositories in `.cache/corpus/`, which are test specimens and stay -- a blanket rename would have taken `benchmark/corpus/symbol_map.yaml`, the digest pin `CI-W576` rests on, with it. `sync.core.corpus` and `sync.remediate.corpus` become `precedent`; `corpus_salt`, `CorpusWriter`, `CorpusRecorder` and `CorpusWriterMissing` follow. **Two names deliberately did not move:** `SYNC_CORPUS_SALT` and `.sync-corpus-salt` are deployment surface -- an operator has the variable set and the file on disk, and that module's own argument is that the salt must be stable across runs or the store cannot be joined to itself. Renaming either re-salts every digest and orphans every row already written, silently: the rename would look finished and every aggregate would start from zero. `tests/test_precedent_salt_surface.py` exists so that cannot be caused by tidying. The decode census caught the moved module path, the same shape it caught in `CI-W570` | landed | 18 files; console rename follows |
| CI-W592 | **The console and the API follow the rename.** `/repositories/:repoId/corpus` becomes `/precedent`, the four `/api/corpus*` endpoints become `/api/precedent*`, and `CorpusPage`, `CorpusChart`, `CorpusSummary` and `corpusHref` follow. Done in one commit rather than split, because a `PrecedentPage` fetching `/api/corpus` is a fact written twice that already disagrees with itself -- the split state is worse than either end of it. Nothing outside this repository consumes those routes: the API is read-only and the console is deployed with it, which is the difference from `SYNC_CORPUS_SALT`, where the same reasoning went the other way in `CI-W591`. Gates: `tsc` 0, vitest 122 files / 1,041 tests, lint 0, pytest 4,502 | landed | 36 files |
| CI-W593 | **The patch agent is shown the operation, not just told its name.** B2. `build_patch_prompt` named the operation a finding was about and said nothing about its shape, so the agent was told `PostCharges` changed and left to infer what `PostCharges` looks like. **The default depth is measured, not chosen.** Against Stripe's real 7,866,866-byte document, `PostCharges` slices to 15,938 bytes at depth 0, 33,857 at depth 1 and 137,117 at depth 2 -- roughly 4k, 8k and 34k tokens -- and the full transitive closure is 790 schemas, the whole document wearing a smaller name. My first design had no depth bound at all and raised on the first real vendor I tried it against, which is why depth 1 is the default: it expands the request and response shapes, where a breaking change lives, and leaves room for the call site and diagnostics. A schema past the bound is **named rather than dropped** -- the agent must tell *there is more, called `Charge`* from *the vendor declares nothing here*. The slice carries the spec hash it was cut from, which is the whole of the owner's constraint: a claim we cannot check is one we do not make. A `$ref` leaving the document is recorded, never followed -- resolving one is a fetch from inside a prompt build. Two guards shaped this: the dead-link check refused the slicer until it was wired into the run, and the decode census demanded a driver rather than a subsuming catch | landed | `src/sync/remediate/spec_slice.py`, `agent_patch.py`, `cli.py`, four test files |
| CI-W594 | **The prompt says how each fact was established.** B3, and the owner's constraint applied to the prompt rather than to the store: we do not reference information we cannot check, and a fact whose provenance is unstated cannot be checked by whoever reads the patch afterwards. `Finding.binding_rung` records whether a call site was read out of source, resolved through a further step, or seen in runtime traffic -- and the prompt carried none of it, so an agent edited with the same confidence whether the binding was literal or inferred. Each rung is **glossed rather than named**: `resolved` is Sync's vocabulary and not English, and a token is not a reason to weigh a line differently. Never omitted either -- a prompt with no provenance line reads as a certain one, which is the strongest of the five claims and the least often true. **Placed outside the untrusted fence**, which the first draft got wrong: everything inside it is the repository's own text that `HARDENING` tells the agent not to read as instruction, and this line is Sync speaking *about* that text -- fencing it would have told the agent to distrust our own assessment. Guarded both ways | landed | `src/sync/remediate/agent_patch.py`, `tests/test_patch_prompt_evidence.py` |
| CI-W595 | **The prompt says where the vendor's claim came from.** B4, and the plan's rule for this track applied to the last unattributed thing in the prompt: unattributed prose is worse than none. `VendorChange.source` spans a structural diff computed from two documents the vendor published, the vendor's own changelog, an SDK release note, and prose scraped off a page -- and all four rendered identically. A scraped page can be restyled, mis-parsed or simply wrong, and none of that is visible in the sentence it produced. Each source is glossed so the difference is legible rather than encoded in a token, an unrecognised one is reported as unrecognised rather than borrowing another's description -- which would attach confidence the row never claimed -- and the line sits outside the untrusted fence, the placement `CI-W594` settled. With B2's spec hash and B3's binding rung, every claim in the patch prompt now states how it was reached | landed | `src/sync/remediate/agent_patch.py`, `tests/test_patch_prompt_change_source.py` |
| CI-W596 | **The last screen joins the skeleton, and `PENDING` is empty.** C1. `/repositories/:repoId/vendors/:vendorId` was the one address still outside `ScreenFrame`, and the owner ruled it gets no exemption. Its panel chips are what narrow the screen, so they become the **controls band** rather than a strip inside the content -- which is the thing `ScreenFrame` exists to keep in one place. Status is a `listing` naming the mounted record plus a `note` scoping it, and deliberately not a count: the counts belong to the cards, which each fetch their own, and a number this component has not got would be a figure it invented. **The migration was proved rather than claimed** -- moving the entry from `PENDING` to `MIGRATED` turned `CI-W572`'s render check red first, exactly the moment that guard was built for. `PENDING` stays as an empty list rather than being deleted: a route added later still has to be accounted for. Gates: tsc 0, vitest 122 files / 1,041 tests, lint 0, build 0 | landed | `web/src/features/vendors/vendor-page.tsx`, `web/src/layouts/screen-skeleton.test.tsx` |
| CI-W597 | **`RouteEntry.question` is deleted entirely.** C2, the owner's ruling. The field existed for nine routes, grew to twenty-two, and by the time every screen carried its own heading through `ScreenFrame` it had **one renderer left** -- the stage doors on the Overview. `routeQuestion`, the `DestinationEntry` copy, the thread through `App.tsx`'s `RoutedScreen` and the `question?: string` prop every screen accepted and none read all go with it. One thing that looked like a fifth consumer and was not: `workflow-grid`'s settings prerequisites also render through `DoorRow`, passing their own local `why` rather than a registry sentence -- so `DoorRow` keeps an optional `detail` and those rows are unchanged. `PageHeader` keeps its `question` prop: it always took a string and never looked one up, and its last caller passes a literal. The deletion is guarded rather than described -- `routes-no-question.test.ts` fails if the field returns, which it would the next time somebody wants a subtitle. Gates: tsc 0, vitest 122 files / 1,039 tests, lint 0, build 0, pytest 4,531 | landed | `web/src/lib/routes.ts`, `App.tsx`, `workflow-grid.tsx`, three tests |
| CI-W598 | **`PageHeader` is deleted; the fallback screen joins the skeleton.** C3. The component's own docstring carried its expiry: it was mounted on `UnknownRoute` as a worked example while the feature screens had not adopted the frame yet, and `CI-W596` put the last of the twenty-one on `ScreenFrame` -- which discharged the reason and left the chassis's own screen as the last thing rendering a component nothing else used. **`UnknownRoute` itself stays**, contrary to the plan's wording: it is the router's fallback *and* the early return twelve screens make when a route parameter is missing, so deleting it would have meant twelve screens inventing their own. It renders through `ScreenFrame` now, publishing `{kind: none}` with a reason -- an empty band would read as a count of zero, which is a measurement this screen has not taken. The first draft published the address in **both** the band and the body; that is one fact written twice, caught by a test that found two matching elements, and there is now a guard asserting exactly one. Gates: tsc 0, vitest 122 files / 1,040 tests, lint 0, build 0, pytest 4,532 | landed | `web/src/layouts/unknown-route.tsx`, `page-header.tsx` and its test deleted, three docstrings |
| CI-W599 | **No primitive is declared twice.** C4, narrowed to the part that is a defect. Two substrates shipped side by side and **four primitives existed in both** -- `Button`, `Card`, `Input`, `Table` -- which is two answers to what a button looks like, and the shadcn `Button` carries focus-ring work measured against the 3:1 non-text contrast floor that the vendored copy never had. 13 consumers repointed, the four duplicates deleted, and the vendored sidebar's own sibling imports repointed with them (single-quoted, which the first grep missed). **The rest of the vendored tree stays**: sidebar, sheet, scroll areas, dropdown, popover and the others have no shadcn counterpart here, and replacing a working primitive that nothing duplicates is the polish `CLAUDE.md` says competes with the milestone. Guarded by `one-substrate.test.ts`, which compares the two directories rather than listing names -- a fifth duplicate fails by existing. It uses `import.meta.glob` because the console's tsconfig ships no Node types, and widening every file's type surface so one test can read a directory is the wrong trade. Gates: tsc 0, vitest 123 files / 1,042 tests, lint 0, build 0 | landed | 18 files |
| CI-W600 | **The named type scale is enforced rather than intended.** C5, and measuring first turned it from a deletion into a guard. 144 tokens are declared and a naive count called 96 unreferenced -- wrong, because Tailwind v4 derives a utility from a token name, so `--color-brand-500` is used by `bg-brand-500`. Accounting for that leaves 33, and most of those are modifiers (`--text-body--line-height` attaches to `--text-body`). What is real: **no file the console authors uses a default-scale size**, all 18 `text-sm` hits are shadcn and vendored primitives that ship with it. So the twelve ramp steps stay -- the role names resolve onto them and deleting the unwritten ones would leave a ramp with holes and restyle every primitive -- and what lands is `lib/type-scale.test.ts`, which fails naming the file and the class. **The first form of that guard was vacuously green**: its character class was spelled with one backslash too few, so it matched a literal `s`, and planting a real `text-2xl` in a screen did not turn it red. Found by trying to break it, which is the only thing that finds it. Now red-proved twice -- once on a unit input, once on a real screen | landed | `web/src/lib/type-scale.test.ts`, `web/src/index.css` |
| CI-W601 | **Six ink names, two colours, now declared once each.** C6. Both halves the plan named were already satisfied -- `WorkflowPage`'s only `disabled` attributes are transient fetch states, and the dead submit control it meant was retired by the owner's ruling of 2026-08-21 (`reply-box.tsx` records it); `BindingSurfacePage` is on `ScreenFrame` with controls and status and takes no exemption. What the survey found instead is a real duplication: `--color-foreground-light`, `--color-muted-foreground` and `--color-ink-muted` held the same colour byte-identically, and so did `--color-foreground-lighter`, `--color-foreground-muted` and `--color-ink-secondary`. Both name sets stay -- `ink-` is the console's, the substrate's is what the primitives are authored in -- but the substrate names now read `var(--color-ink-*)` rather than carrying a second copy, so adjusting an ink moves everything. The guard lives in `test_console_design_tokens.py` beside the other token contracts, with the paired violation tests that file's own docstring requires: one for a second copy, one for an owner that has become an alias. **It got there after two false starts in vitest** -- `?raw` and `?inline` both resolve `index.css` to an empty string under Vite's pipeline, which failed loudly rather than vacuously and is why the check is where the repository already keeps text-over-`web/src` guards | landed | `web/src/index.css`, `tests/test_console_design_tokens.py` |
| CI-W602 | **The named spacing scale is enforced, and the step the console reaches past it for is measured.** C7, closing Track C. Across 245 files the console authors, 86 raw numeric spacing utilities remained. Thirteen were steps 1-4, which map exactly onto `field`, `row` and `section` -- migrated, and `gap-3` to `gap-row` tightens 0.75rem to 0.5rem, which is the terminal-density ruling doing its job rather than a regression. **The interesting residue is `gap-8`**: 38 sites in 26 files write 2rem as the gap between a screen's top-level blocks, and no named step holds it -- `section` is 1rem, `frame` is 2.5rem. The scale's own comment says *a fifth is a decision recorded in DESIGN.md, not a value added in passing*, and DESIGN.md is the owner's document, so the step is **named in the exemption with its count and its argument** rather than invented here. `-0` is exempt as a reset. The guard fails naming file and step, and carries its own violation pair | landed | `tests/test_console_design_tokens.py`, eight console files |
| CI-W603 | **A fresh worktree stops failing three tests for its environment.** D4, and the suite is fully green for the first time in this sequence: **4,538 passed, 0 failed**. `.cache/corpus/` is gitignored, so a worktree that has not run `scripts/fetch_corpus_repositories.py` had three rehearse tests fail with a `RuntimeError` that names the path and the fix -- a good message attached to the wrong failure mode. Red tests that are not defects is what trains a reader to skim a red suite, and the failure this closes is **the next real one being read as more of the same**; every gate report in this sequence has had to carry the sentence *three environment failures*. `require_corpus` skips, using the idiom five console tests already use for an absent `web/`. The production raise stays: a run reaching for a repository it has not fetched is a genuine failure. **Proved not to hide anything** -- the same three tests were run in the primary tree, which does have the corpus, and passed 7/7 rather than skipping | landed | `tests/conftest.py`, `tests/test_rehearse_fixture.py`, `tests/test_rehearse_boundary.py` |
| CI-W604 | **The landing gate stops contradicting the config it runs under.** D3, closing Track D. `CLAUDE.md` prescribed `uv run pytest tests/ -q -n0` while `pyproject.toml` sets `-n auto` and its own comment reserves `-n0` for *a focused run* -- so the rule overrode the project default with a flag the config describes as being for the opposite purpose. Measured on 4,538 tests, both green: **serial 1,108s (18m28s) against parallel 215s (3m27s)**, a 5.2x difference for an identical verdict; run as newly written, with nothing competing, 160s. Owner ruled: drop `-n0`. **Two of my own numbers were wrong and are corrected rather than quietly replaced** -- the plan claimed 23m54s against 3m56s from memory, and my in-flight extrapolation said 44 minutes because the suite's tail runs faster than its head. **And the flake was mine.** Nearly every gate report in this sequence said *plus the intermittent leaked-database race* as if it were environment noise. It is not: the test passes 20/20 alone, `conftest.py:609` sweeps every dead-pid database at session start, and every occurrence came from my running a timing measurement beside a gate. The suite has no flake | landed | `CLAUDE.md`, `pyproject.toml`, the plan |
| CI-W605 | **The beta-gate meter could not run: the Precedent rename missed it.** `CI-W591` renamed `corpus_health` to `precedent_health` in `sync.dashboard.fleet` and did not repoint `scripts/beta_gates.py`, so the readiness meter died on an `ImportError` at its first call. Nothing caught it: the dead-link guard scans `src/`, the suite has no test that runs the meter, and no gate report was taken between the rename and now. Found by running it. Repointed, and the measurement it gives is materially different from the week-old status recorded in `BACKLOG.md`: **Gate 1 is now MET** -- 25 real attempts, 2 with a pull request that went green -- against `NOT MET` on 2026-08-17. Gate 2 NOT MET (1 of 5 axes), Gates 3 and 4 CANNOT TELL | landed | `scripts/beta_gates.py` |
| CI-W606 | **The browser verification loop is enabled and proven, and its output stops landing in the tree.** Playwright MCP drives the running console: navigate, screenshot, accessibility snapshot, console log, network. Proven rather than asserted -- a live screenshot of `localhost:5173` against real data, from the merged tree. `chrome-devtools-mcp` is enabled in settings but its server disconnected mid-session, so its Lighthouse and trace tools are unreachable until `/mcp` reconnects them; Playwright covers everything the frontend loop needs meanwhile. `.playwright-mcp/` is now gitignored -- it writes screenshots and snapshots beside the tree it drives, and the first run left two untracked paths in the repository root | landed | `.gitignore` |
| CI-W607 | **The parity plan's ledger said nothing was done while 89 of its work items had shipped.** `2026-08-17-console-mock-parity.md` carries 74 checkboxes, every one unchecked, against **89 `M14-` items in `WORKLOG.md`** and its own artefacts running in the console -- `detail-grid`, `breadcrumbs`, `activity-timeline`, `/settings`. **The cost is measurable and was paid today**: asked to rebuild the console, I searched for prior work, read that file as untouched, and wrote a *new* redesign plan for something already planned there against the owner's own mock in `docs/console-mock/` -- twelve screens, a demo video and a design canvas I never opened. A day of chassis refactoring followed, and the owner's reaction was that the console looked unchanged. It did, and this ledger is why. Reconciled with a header that says what shipped and how to measure what remains, rather than back-filling 74 boxes nobody can verify retrospectively | landed | `docs/superpowers/plans/2026-08-17-console-mock-parity.md` |
| CI-W608 | **The frontend resources are audited, enabled, and written down.** The owner provided plugins, skills and repositories for this work and asked why they were not being used. **`ui-theme-designer` was off** -- named in this session's first message and never enabled, now on alongside `frontend-design`, `superdesign`, `playwright` and both LSPs. The audit separates advisory from **binding**: `web/CLAUDE.md` (no composite score, health figure or traffic light -- rejected three times on the record), `DESIGN.md` (every value arrives with its 5.05:1 arithmetic), and the four console rules overrule any plugin suggestion. It also records what is *not* useful so it is not re-litigated: the repo's own `sync-external-resources` skill says of its one design-system entry *do not read it for design advice, Sync has no frontend* -- true when written, stale now -- and the roadmap.sh track was closed at *worth zero minutes* on 2026-08-04. `chrome-devtools-mcp` is enabled but its server is disconnected; Playwright covers the loop and is proven against the running console | landed | `docs/superpowers/references/notes/2026-08-24-frontend-resources-audit.md`, `~/.claude/settings.json` |
| CI-W609 | **The mock is now named in the file that loads when a screen is open.** The governing principle in `CLAUDE.md` is *encode a rule where it fails, not where it is read*, and the rule that failed on 2026-08-24 was **open the owner's mock before changing a screen**. It existed only as a plan nobody found and a directory nobody opened, so a day of console work produced nineteen commits of which four changed anything visible. `web/CLAUDE.md` loads whenever a console file is open, so the pointer lives there: the still, the route, the resources audit, and the measurement that says why | landed | `web/CLAUDE.md` |
