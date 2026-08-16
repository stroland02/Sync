# Sync backlog

The queue an autonomous tick pulls from. Ordered by what unblocks the most, not by
size. When a tick has nothing else to do, it takes the topmost unclaimed item, dispatches
a worker against it, and moves the item to **In flight** with the task id.

An item is only **Done** once it is on `main` with all three gates green
(`uv run pytest`, `uv run lint-imports` unredirected, `uv run python scripts/lint_encoding.py src tests`).

Every item states what is wrong, why it matters, and what evidence would close it. An
item that cannot say what evidence closes it is not ready to dispatch.

**Before assigning a new `B`-number, check every local branch, not only `main`'s copy of this
file.** `git log --all --oneline --grep="B<N>"` costs one command. Two development lines each
independently filed `B122` for unrelated work on 2026-08-16, caught only by inspection during a
merge two weeks later — the same class of collision `B116` was hand-picked to dodge once already,
documented below at that entry. A number chosen against `main` alone is chosen blind to whatever
another branch has already claimed.

**A worktree with no commits in the last week and an unmerged branch is a backlog item, not
invisible capacity.** Paused work does not surface itself: three branches (M3-W113, M3-W114,
M3-W115) sat finished-but-unreviewed for seventeen days before a session's unrelated cleanup sweep
found them via `orca worktree ps`. When a tick runs, check worktree age against this file's own
**In flight** and **Ready** sections and add what's missing — a stale worktree holding real work is
a fact this file should carry, the same way an abandoned run is data rather than a silent drop.

## Milestone status

Percentages are judgement over measured facts, not a burndown. Each says what it counted. The
milestone names come from
[the design document](specs/2026-07-25-sync-self-maintaining-apis-design.md); the mapping below is
by content, because items were never tagged with a milestone as they landed.

### Where development stands, 2026-08-07

Fifty commits landed on `main` today, from two sessions working the same tree. The shape of the day:

- **The console was rebuilt twice and the second one shipped.** A chassis built from scratch
  (`W157`–`W164`), then replaced on the owner's ruling by Supabase's `packages/ui` vendored at code
  level (`W165`–`W180`). All nine specification levels are on the substrate. The first pass is not
  waste: it produced the honesty-sentence gate every later port merges against, and the
  before-measurements the substrate is judged by.
- **The measured bars moved.** Type range **2.00–2.67 → 4.00** against a 3.4 bar on the levels
  ported so far; frame ratio **3.0 → 5.0** on ten of ten routes. Two things deliberately did not
  move and say so: six feature routes still sit at the old range pending the migration `B116` files,
  and the binding surface at 1280 is **one pixel** short of its row-height threshold, which `B115`
  keeps open because a one-pixel margin on one fixture is a coincidence rather than a fix.
- **CI got 26% faster and the metric that watches it got fixed.** `B111` closed: coverage to a
  nightly, the serial job off the pull-request path. Pull-request critical path **200s → 123s**,
  push **200s → 170s**. `B112` closed on per-run evidence. Then `CI-W190` fixed the alarm that
  change broke — a skipped job is also stepless, so `zero_step_jobs` would have climbed forever.
- **One production defect closed.** `B117`: `GraphStore` handed back a *closed* connection forever,
  so one dropped connection took every console route down until a restart.
- **Two milestones proposed, neither scheduled.** M8–M11 (the resolution loop) and M12 (dashboards).

**What is not true yet, stated plainly.** Nothing is hosted. The acceptance run has not executed in
1,073 commits. Three of five quality axes have never had a sample. The console is a local
development surface with no auth, no tenancy and no write path.

**Two things the owner named that are not yet scheduled**, from reviewing our own screens against
the reference set: the layout is one vertical stack where it should be a grid, and Fleet carries
more prose than data. Both are M12's, and M12 is proposed rather than started. Two further points
from the same review were already answered and are recorded in the M12 plan rather than re-derived —
the background has not been pure black since `W170`, and the type scale already carries 22px, 28px
and a 48px display step, so the defect there was assignment rather than absence.

| | Milestone | % | The one sentence that matters |
|---|---|---|---|
| **M0** | Walking skeleton, one real PR | **~90%** | Every component exists; **the proof is 1,073 commits stale** — measured 2026-08-07, not the "~200" this row claimed for a fortnight |
| **M1** | Runtime signals, efficiency detector | **~85%** | Built; the dollar estimate is deliberately unbuilt |
| **M2** | Production error detector | **~85%** | Built; never exercised against real telemetry |
| **M3** | Multi-vendor, MCP, plugin SDK | **~95%** | Packaging closed 2026-07-30; nothing structural left |
| **M4** | Hosted control plane (**the front end**) | **~50%** | Nine levels and the honesty discipline are built and scoped; nothing is hosted, and three of the milestone's four deliverables have no code |
| **M4.5** | The console is worth looking at | **~90%** | W141-W145 all landed and merged; the conformance gaps it existed to close are closed, and what remains of "worth looking at" moved into M7 |
| **M5** | Integration layer | **~35%** | Sentry feeds counts in now; still nothing correlates anything |
| **M6** | Show it, rather than describe it | **0%** | Needs a UI worth filming. That is M7's line now, not M4.5's, and M7 is close enough that this is becoming schedulable |
| **M7** | The console becomes a product | **~88%** | All nine levels are on the vendored Supabase substrate. Fidelity Tasks 1-3 of 6 are done; Phase 5 (the workflow as narrative, one binding drawn) and Phase 6 (the write path, which belongs to M4's hosted half) are unbuilt |
| **M8–M11** | The resolution loop | **0%** | Proposed 2026-08-06, nothing scheduled; Sync opens a pull request and stops watching it |
| **M12** | Dashboards that earn their screen | **0%** | Proposed 2026-08-07 from the owner's review of our screens against the references; full-stack, because the useful panels need aggregates `sync.dashboard` does not compute |

### M0 — Walking skeleton, one real pull request · ~90%

**Done.** Stripe adapter, TypeScript indexer, vendor-change detector, LangGraph remediation graph and
GitHub forge all ship. The verification path is the part that got hardened most: a push lease that
refuses a tip Sync did not author, refusal to discard any non-Sync commit rather than only one at the
tip, branch deletion on abandonment, a guard catching a patch that edited an installed dependency,
support for a patch that must create a file, dependency-tree discarding, checkpoint serialiser
registration, and the tier cascade.

**Remaining — one item, and it is a decision rather than a build.** `B7`, the acceptance run.
`tests/test_e2e_stripe.py` is `@pytest.mark.e2e` and deselected by `addopts`, so it has not executed
since **1,073 commits** landed underneath it — measured 2026-08-07 as
`git rev-list --count f21a1c0..origin/main`, where `f21a1c0` (2026-07-27) is the last commit to
touch the test. This row said "roughly two hundred" for a fortnight, which is the failure mode a
backlog is most prone to: a number written once and then read as current forever. It opens a real pull request against a real
repository and spends `xhigh` model time, so it needs the user's go-ahead. **It is also the only
thing that gives three of the five quality axes their first sample** — `migration_outcome` holds 3
rows and **0** carry a `pr_number`.

### M1 — Runtime signals and the efficiency detector · ~85%

**Done.** The span store (`observed_call`), OTLP ingest, correlation behind a `RequestCorrelator`
protocol, loop context on `call_site` as a depth rather than a flag, and the efficiency detector
itself — calls in a loop, absent caching, retry storms via `resend_count`. Efficiency findings state
that a cost is shared across call sites rather than counted once per site.

**Remaining.** The design document says these findings carry a dollar estimate. They do not, and
`detect/efficiency.py` says why in its own docstring: a saving is a call count times a price per
call, and no table here holds a price. That is a data-sourcing decision, not missing code, and
inventing a price would be worse than reporting none.

### M2 — Production error detector · ~85%

**Done.** `status_rate.py` reports a level rather than a bare rate; `observed_drift.py` catches a
response that no longer matches the indexed specification; `observed_shape` stores what was actually
seen. A Sentry source exists, which the design document calls the fastest route to this milestone.

**Remaining.** None of it has run against real telemetry, so the detectors are correct by
construction and unproven in the field. Same root as M0: no real run has happened.

### M3 — Multi-vendor, MCP, and the public plugin SDK · ~95%

**Done.** Twilio as the second adapter — the first real second implementation of
`operation_for_symbol`, which inverted an assumption the symbol map was built around. A Python
language adapter. An MCP vendor adapter. A generated-SDK adapter family with the Stripe symbol map
derived from `x-stableId` rather than URL shape. The conformance kit covering **all five protocols**
against nineteen shipped implementations, with each rule proved able to fail — it has caught itself
three times, most recently certifying its own reference detector.

And the last structural piece: **`sync-core` is now a second distribution.** An adapter author
installs six packages instead of eighty-one, with psycopg, LangGraph, mcp, the Claude Agent SDK and
the tree-sitter grammars all demonstrably absent. CLAUDE.md's first non-negotiable is now true at the
packaging level, not only the import level.

**Remaining.** Publishing `sync-core` anywhere is public and irreversible and is the user's call. The
wheel builds and installs; nobody has uploaded it.

### M4 — Hosted control plane · ~50% — **this is where the front end lives**

Reconciled against the tree on 2026-08-05. The previous entry said "0%, nothing started, no plan file
exists", which was true when written and has been false for about seventy commits.

**Done: the read surface, and it is substantial.** Eight screens on branch `m4-dashboard` —
fleet, codebase, vendor, finding, solution workflow, binding surface, observed telemetry, detector
accountability. Twelve GET routes over `sync.dashboard`, all covered by a behavioural read-only test
that has been proven able to fail. Three plan files, not none:
`2026-07-30-sync-m4-dashboard.md`, `2026-08-04-sync-m4-slice-2.md`,
`2026-08-05-sync-console-design-system.md`, plus a dogfooding plan and a run-state specification.

A design system landed with it: a validated palette in both modes, a six-step type scale, three
spacing tokens, two elevation levels, and `DESIGN.md` recording every decision with the validator's
output pasted in.

**The honesty discipline is the part that was expensive and is worth protecting.** Provenance renders
wherever a binding is shown, at two levels. A screen that cannot support a claim says so instead:
absence is distinguished from zero, staleness from liveness, "never measured" from "nothing here".
Six separate defects of the form *the console asserts something the data does not hold* were found
and closed, several by removing a field or a column rather than adding one.

**Not done, and the gap is bigger than the percentage suggests.**

- **Nothing is hosted.** No deployment, no auth, no user model; the API binds `127.0.0.1`. "Hosted
  control plane" is the milestone's name and that half is at zero.
- **No write path.** Every route is read-only by design and by test. An operator cannot start a run,
  retry one, or close a finding from the console.
- ~~**The navigation hierarchy is not the one the design document specifies.**~~ **Closed
  2026-08-06.** All three unbuilt levels are in — the repository entry point (M4-W130), Signals
  (M4-W127) and Pull Request (M4-W126) — every level below Codebase inherits repository scope, and
  the two figures that genuinely cannot be scoped say so on screen rather than inheriting one.
  `tests/test_console_hierarchy.py` now holds `GRAPH_LEVELS` against the specification's
  authoritative block, which is the part that stops it drifting again: the reconciliation was
  needed because three plans checked the console against itself.
- **The interface is one idiom, and that is now half true.** Measured 2026-08-05: 21 `<Card>`, 17
  `<Table>`, 1 chart across 5,781 lines, and 7 `onChange`, 3 `<Button>`, 2 `onClick`, 1 `<input>`
  in the whole frontend. M4-W135 gave the two tables that will actually be long a server-side
  filter each, with facets computed without the filter they set. What remains is sorting — which
  needs an `ORDER BY` the frozen surface does not offer, filed as B100 — and the rest of the
  affordance layer, which is M4.5-W141 rather than M4. See B90, whose opening counts were wrong
  when written and are corrected in place.

**The condition on the deferred *premium components* row is now met.** That row said: after the data
model is visible. It is — eight screens cover the graph end to end. It retires now, and the work it
gates is the next real front-end slice rather than another polish pass.

**What no longer blocks it.** The old entry said the blocker was data — every panel would read zero.
That is closed: `scripts/seed_console.py` populates every screen with call sites, findings across
three rungs, vendor changes, observed calls, shapes, error windows, migration attempts and multi-
generation runs, idempotently, with an exact `--remove`. `B7` is still worth running, but it is no
longer what stands between M4 and progress.

### M4.5 — The console is worth looking at · 0%

**Split out of M4 on 2026-08-06, deliberately.** The plan is
`docs/superpowers/plans/2026-08-06-m45-console-quality.md` and carries the argument; the short version
is three reasons. M4 is four deliverables of which three have no code, so an open-ended quality bar
inside it produces a milestone with no end. Its acceptance test is a different kind — an M4 task is
done when a screen exists and a test holds it, a quality task when a measurement clears a bar. And
this has already gone wrong once in this exact direction: nine consecutive ticks went to design-system
findings while two specified levels of the console did not exist.

A separate milestone with a written start condition is what makes "not yet" a fact about sequence
rather than a judgement somebody re-makes every tick. The condition is: the architecture plan's Tasks
4 through 7 landed, the 2026-08-06 review wave closed, and the conformance report published.

Six tasks, each closing on a measurement rather than an opinion — the baseline report, the affordance
layer, type and ink and space against rendered pixels, motion (one keyframe, nothing running at rest),
density with its 11px floor, and the one visual that earns itself. M6 sits behind this rather than
behind M4, because what gets photographed is this milestone's output.

### M5 — The integration layer · ~35%

**Done.** The signed public change feed with its consumer and cache, the vendor registry and its
tiering, the deprecations catalogue, and B71's Sentry error-count ingest.

**Correction to an earlier reading of this milestone.** Sentry and Datadog were previously counted
here as "sources" on the strength of their `shapes.py` readers, which parse a recorded response
shape that `cli._fold_sentry` folds into `observed_shape` for M2's `observed_drift`. That
contributed nothing to this milestone and counting it here overstated it. B71 is what made Sentry a
source of this milestone's data: `observed_error_window` holds per-operation failure counts, and
nothing before it did.

**Remaining.** Nothing models a deploy, and no detector reads the counts B71 lands — the reader is
baselined as reached from nowhere, deliberately. The correlation join itself is what the milestone
is actually for: joining a spike to a deploy to a vendor change to the call sites affected. That is
a build rather than a defect, which is why nothing here is queued.

### M6 — Show it, rather than describe it · 0%

Remotion videography of the product working. Needs a working UI to film, so it sits behind M4.

### M8–M11 — The resolution loop · 0%

**Proposed, not scheduled.** Plan:
[`plans/2026-08-06-sync-m8-m11-resolution-loop.md`](plans/2026-08-06-sync-m8-m11-resolution-loop.md).
Source study, with a `path:line` citation behind every claim:
[`references/notes/superlog-investigation-mechanism.md`](references/notes/superlog-investigation-mechanism.md).
Numbered from M8 because M7 is the console.

Four milestones, ordered by what unblocks the most. **M8** puts the model call behind a protocol so
the remediation pipeline can be tested without a key. **M9** gives a run more outcomes than "diff"
and "abandoned" — an external cause and a question for a human are both real answers today that
have to be spelled as failures. **M10** parks a run instead of ending it, so a pull request CI
rejects is Sync's problem rather than nobody's. **M11** groups findings sharing a vendor change
into one remediation, instead of eight findings producing eight pull requests against one
repository.

M8 → M9 → M10 is a dependency chain; M11 needs M9 and is otherwise independent.

**Sequenced behind M7.** All four are pipeline work and none of it is visible in the console. M8 is
the exception worth taking opportunistically: a refactor that makes the existing remediation suite
key-free and faster, and it pays for itself before anything below it is scheduled.

### Measurement, which cuts across all of them

Two of five quality axes are measured: **binding precision and recall, both 1.0000 at n=26** over a
frozen corpus of 17 pairs across 5 repositories, gated by four floors that have each been proved able
to fire. Merge rate, routing accuracy and cost per merged patch have **never had a sample**.

Most of the `Done` list below is this: the corpus, the binder defects it caught, the rung a finding
carries, and a long family of encoding defects that all shared one shape — a text read that answered
confidently instead of refusing.

---

## Ready

### B90 — The console is one idiom repeated eight times, and the resources to fix it are already installed

Measured on 2026-08-05 across `web/src`: **21 `<Card>`, 17 `<Table>`, 1 chart, 5,781 lines.** The
whole frontend contains 7 `onChange`, 3 `<Button>`, 2 `onClick` and 1 `<input>`. Three shadcn
primitives exist — `button`, `card`, `table`.

**Two of those counts were wrong when written, and the correction matters more than the numbers.**
`web/src/components/ui/` held eight primitives that day, not three — `command`, `dialog`, `input`,
`input-group` and `textarea` alongside the three named — and `layouts/command-palette.tsx` existed,
having landed in `0455810` the day before this entry was filed. So "no command palette anywhere"
was false at the moment it was measured. The thesis survives the correction: what those primitives
were doing was sitting vendored and unused, which is the entry's actual argument. But an entry that
counts wrong teaches the next reader to re-measure rather than to trust it, and this one had three
plans quoting it.

So the console is a read-only table renderer. That was the right first version, and it produced
eight screens, provenance rendered at two levels, and six false-claim defects found and closed.
**What is missing is not structure, it is interface.** There is no filtering, sorting, search,
drill-down, tab, dialog, skeleton, tooltip or command palette anywhere — on a console whose tables
will hold thousands of call sites from a real customer repository, where the fixture holds five.

**Correction, 2026-08-05.** This entry previously said the information architecture those eight
screens produced was "genuinely good", and `2026-08-05-sync-console-architecture.md` cited that
sentence back as established fact. It was not established; it was never checked. Reconciled against
`specs/2026-07-25-sync-self-maintaining-apis-design.md:392-411`, three of eleven routes match the
specified hierarchy, four levels are invented, two are reparented, and three specified levels were
never built. B92 through B96 carry the corrective work. Everything else measured in this entry
stands.

**The leverage here is that almost nothing needs installing.** `shadcn` is already in
`devDependencies` and `radix-ui` is already a dependency, and shadcn vendors component source into
the repository rather than adding a package. Dialog, tabs, command, tooltip, badge, skeleton,
separator, scroll-area, dropdown-menu and sheet cost **zero new dependencies**. `lucide-react`,
`framer-motion` and `echarts` are installed and barely used — one chart in eight screens, against a
`dataviz` skill that has been invoked exactly once.

The one thing genuinely not installed is a headless table library. Seventeen tables with no sorting
or filtering is the strongest argument for TanStack Table, and it is a real dependency decision that
should be argued rather than assumed — `docs/superpowers/references/engineering/dependencies-and-packaging.md`
is the note that governs it.

**Evidence that closes this:** a slice that picks the two or three screens where the absence actually
costs an operator something — the vendor findings table and the binding surface are the candidates,
because both will be long — and gives them the affordances the data demands, with each addition
argued from the operator rather than from the component catalogue. **Not a sweep that adds a
component to every screen.** `.claude/rules/interface-originality.md` still binds: the interface is
ours, and a component earns its place from the graph and the operator, never from a competitor's
screen or from being available.

#### Slice 1, 2026-08-06 — the two long tables can be narrowed

Both candidate screens now filter, and every filter is a SQL predicate with a denominator that moves
with it. The vendor findings table takes a severity and a call-site path prefix; the binding surface
takes a repository and a call-site path prefix. Each filter lives in the URL beside the offset it
clears, so a narrowed table survives browser Back and can be pasted to somebody else.

**The filters sit inside the repository scope rather than beside it.** B92's scope work landed
first, on `m4-dashboard`, and this slice was rebased onto it: `repo_id` is what every level below
Codebase inherits and is not one of the filters an operator sets here, so choosing a severity inside
a selected repository narrows *that repository* and "clear all filters" deliberately does not touch
it. All three narrowings reach `open_findings_at_risk` as predicates on one query, and the vendor
screen's severity facet is scoped by the repository and the vendor together — either alone is the
same false claim on one axis, and both are the class of defect that scoping exists to remove.

**Every addition is argued from the graph rather than from the catalogue.** Severity and path were
already parameters of `GraphSurface.whats_at_risk` and reachable from no URL the console builds;
B92 turned them into real SQL predicates on the way past. `repo_id` was already read by the binding
surface and settable only by arriving on a link. The only genuinely new predicate is `path_prefix`
on `call_sites_for_operation`, and it is `starts_with` rather than `LIKE` because `_` is a wildcard
in a `LIKE` pattern and ordinary in `src/my_module/` — a defect no fixture in this repository would
have caught. B92's `_open_findings_predicate` reached the same conclusion independently for the
findings join; `_call_site_predicate` is its sibling over `call_site` alone, and cites rather than
restates the argument.

**Two facets, both deliberately unnarrowed by the filters they set.** A severity breakdown scoped to
the repository and the vendor, and the repositories holding a call site on the operation. An option
list narrowed by its own filter collapses to whatever is already selected and leaves no way back, so
these count over the whole scope and each says on screen that it does — the numbers on the chips and
the range under the table answer two different questions.

**Three kinds of nothing per table, where there was one.** Genuinely empty, filtered to empty, and a
page position past the end of a narrowed set. Each names the repository scope it found nothing in,
because the scope and the filters are different reasons for an empty table and a reader who cannot
tell which is which cannot act on either. The second names what the filter excluded against what
that scope actually holds; the third says the window is empty rather than the table.

**No sorting, and that is the ruling rather than an omission.** A sort control over the rows on
screen sorts fifty of two and a half thousand and reports a total drawn from all of them — the
"a reader cannot tell what this view can see" defect this milestone has closed six times, shipped as
a feature. A correct sort is a server-side `ORDER BY`. Until B92 landed there was nowhere to put
one, because the vendor route read the frozen `whats_at_risk`; there is now, and **B100** below
carries what it costs and what it must not claim.

**TanStack Table: declined, with the argument.** `docs/superpowers/references/engineering/dependencies-and-packaging.md`
governs this and the reason it does not earn its place is the shape of the data, not the size of the
package. Every long table here is server-paginated over a set that reaches thousands of rows, and
TanStack's sorting, filtering and faceting are client-side over the rows handed to them — which is
one page. Wiring it to a server leaves only its column-definition and header-rendering layer, which
is what `components/ui/table.tsx` already does in 152 lines. The failure mode is worse than the cost:
a client-side filter over a server page silently produces a wrong answer that looks right, and this
milestone has spent six defects closing exactly that class. Revisit if a table appears whose whole
set is genuinely bounded and small.

**No skeleton, no tooltip, no dialog, no icon.** `LoadingState` names what is being waited for in
words, which is more honest than a shimmer claiming a shape the answer may not have. A tooltip is
where the surface rule forbids putting a qualification. `--color-graphics` is still unspent, so its
recorded retiring condition still stands.

**A follow-up this slice filed is already closed, by somebody else, for a different reason.** On
the pre-rebase base the vendor route answered in about six seconds at this scale, 5,483 ms of which
was `whats_at_risk` walking every open finding with one `get_call_site` round trip per row. This
slice filed that rather than smuggling the fix into an interface change; B92 then closed it
independently by moving the route to `graph_views.vendor_findings`, a real SQL `LIMIT` over a join,
because the frozen surface's rows carry no `repo_id`. The follow-up entry is deleted rather than
kept, per this file's own rule that a repaired entry is removed by whoever notices the repair.

**Measured at `--scale 10000`, 1440×900, on the rebased tree.** Binding surface, unfiltered: 650
DOM nodes, 192 ms first contentful paint, its payload in by 210 ms, 18,307 B. With a path prefix:
139 nodes and 1,452 B, 12–19 ms at the route. Vendor findings, filtered to one severity: 742 nodes,
208 ms first contentful paint, both its payloads in by 249 ms, 16,996 B. The route itself answers in
25–40 ms unfiltered, filtered, or scoped and filtered together — the three are indistinguishable,
because all three narrowings are predicates on one query.

The paired before figures are against the pre-rebase base and describe this slice's own cost:
binding surface 634 → 650 nodes, 188 → 192 ms, 18,215 → 18,307 B, which is the filter bar and the
repository facet. The vendor screen's pair is not reproducible, because B92 replaced the route
underneath it in the same interval.

**One earlier reading here was wrong and is corrected rather than quietly dropped.** The first
sample after seeding ten thousand rows showed the filtered vendor route at 6.2 s and the unfiltered
one at 31 ms, which reads as a filter that costs six seconds. It was not: every read underneath was
already fast when timed directly, and five repeats of the same request landed at 25–40 ms. The first
sample after a bulk insert is a measurement of the insert, not of the route. One sample is not a
measurement, and the rule this file already carries — measure, do not describe — has a second half
that is easy to skip: measure more than once.

### B94 — Signals is built; one of its three roles has nothing to attach

*One panel per attached integration, grouped by role: vendor, signal source, human surface*
(`:399-400`).

**Built 2026-08-06** (M4-W127, `3855fd4`/`b39dcde`/`87f0d7f`, merged `e4284ae`). The level renders
all three roles from a roster taken verbatim from the specification's M5 table, held by five Python
tests that read the TypeScript, and its header states which roles have an integration attached and
which do not. `not-attached-state.tsx` draws the distinction the level turns on: *attached and
quiet* is a fact about traffic, *nothing is attached* is a fact about configuration.

**What remains is genuinely blocked rather than undone.** The vendor role has the registry behind
it and the signal-source role has B71's Sentry ingest; the human-surface role has nothing in the
tree at all — no adapter, no configuration table, no row naming a delivery destination. Rendering
that blockage is finished work, not a placeholder, and a panel invented so the grid looks even
would be a false claim.

**Evidence that closes this:** a human-surface integration exists and its panel reads from it.
Realistic after M5's correlation join, not before.

### B111 — The test suite runs three times on every pull request

**Closed 2026-08-07 (CI-W167).** A pull request now runs the suite once. Coverage moved into a job
of its own on a nightly schedule (03:43 UTC) plus `workflow_dispatch`; the serial job left
`pull_request` and runs on every push to `main` plus `workflow_dispatch`. Neither check was
deleted, and the serial condition is an event rather than a path filter — every change reaches
`main` as a fast-forward push, and every such push runs the serial job, so nothing lands without a
serial run at its landing. What a pull request's green no longer says is "serial passed"; it says
the gate passed and serial runs at the landing, with `-n0` remaining the local gate every brief
mandates. The accepted risk: coverage's recorded point arrives nightly rather than per push, which
its baseline series (`specs/2026-07-29-sync-coverage-baseline.md`) tolerates because nothing gates
on it and nobody waits for it.

Before and after, medians from `reports/ci-profile-2026-08-06.md` (25 runs) and
`reports/ci-profile-2026-08-07.md` (6 `workflow_dispatch` runs of the new shape on
`ci-critical-path`, all four jobs, zero-step check clean):

| Shape | Before | After |
|---|---:|---:|
| Pull request (`test` vs `web`) | 200s | **123s** |
| Push to `main` (adds `serial`) | 200s | 170s |
| Compute per pull request | ~435s | ~165s |

Two findings from the same pass. The concurrency group now includes `github.event_name`: `schedule`
and a push to `main` share `refs/heads/main`, so without it the nightly landing beside a push would
cancel one of them, and a cancelled run reads as red — the B112 misreading. And caching is already
done: `uv sync` and the oasdiff install sit below the profiler's 3s display floor in every job, so
there was no dependency-caching win to take instead.

One caveat for the profile series: coverage is now its own job, so `test`-job medians before and
after this change measure different step sets, and a window spanning 2026-08-07 mixes them.

The original entry, kept as the record:

Measured 2026-08-06 over 25 runs by `scripts/profile_ci.py`
(`reports/ci-profile-2026-08-06.md`). Jobs run concurrently, so the critical path is the `test` job
at a median of **200s**, and inside it:

| Median | Job | Step |
|---:|---|---|
| 137s | `serial` | Tests, serial scheduler (`-n0`) |
| 80s | `test` | Coverage (recorded, not gated) |
| 60s | `test` | Tests (`-n auto`) |

**Roughly 280s of compute and 140s of the 200s critical path is the same suite, three times.**

Each run has a real reason and none of them is wrong. The gate is the gate. Coverage is a separate
invocation because a dotted `--cov` legitimately changes behaviour here
(`specs/2026-07-29-psycopg-error-identity.md`) and is ungated because
`specs/2026-07-27-sync-benchmark-gates.md` forbids inventing a threshold. The serial job exists
because `addopts` runs `-n auto` everywhere else and 186 errors appear only under `-n0`
(`reports/2026-07-30-n0-is-broken.md`).

**What none of those reasons requires is that all three run on every pull request.** Coverage is
recorded rather than gated, so a nightly schedule loses nothing a reviewer waits for; the serial
scheduler catches a class of defect that arrives with a conftest or fixture change rather than with
a screen, so it could be conditioned or scheduled. Both are decisions with a real risk attached —
a defect found nightly is found later — and that risk is the thing to argue, not to assume away.

**Closes when:** the critical path falls with the before-and-after medians from two profiles beside
it, and every check that stopped running per-pull-request is named along with where it runs instead.
A gate deleted rather than moved does not close this.

### B112 — Hosted runners stopped acquiring this repository's jobs, so CI's verdict means nothing - CLOSED

Observed 2026-08-06. Run `31124124263` on `81d6c96`: all three jobs recorded a start and an end
fifteen minutes apart, ran **zero steps**, and were cancelled. The annotation is
*"The job was not acquired by Runner of type hosted even after multiple attempts."* It began as one
job an hour earlier and became all three.

`gh run list` reports those runs as `failure`, which is the dangerous part: a coordinator reading
the conclusion sees a red build on its own branch and starts looking for a defect that does not
exist. The distinguishing check is cheap and is now in the tick —

```sh
gh api repos/stroland02/Sync/actions/runs/<id>/jobs --jq '.jobs[] | "\(.name) \(.conclusion) steps=\(.steps|length)"'
```

— zero steps means the job never started.

The cause is not visible from here. Exhausted Actions minutes on a personal account produces exactly
this signature; so does a service incident. `gh api users/<login>/settings/billing/actions` answers
it and needs the `user` scope, which this checkout's `gh` does not hold
(`gh auth refresh -h github.com -s user`).

**While this holds, the local gate is the authority** — `uv run pytest tests/ -q -n0`, plus
`npm run build`, `npm run lint` and `npm test` from `web/`. Say so rather than implying CI covered
something it never ran.

**Closes when:** a run completes with steps again, and the cause is recorded — because "it started
working" without a cause is a thing that will happen again with nobody knowing why it stopped.

### B7 — The M0 acceptance run has not executed since the pipeline changed underneath it

`tests/test_e2e_stripe.py::test_one_command_produces_one_green_pull_request` is the
milestone's definition of done and it is `@pytest.mark.e2e`, deselected by default, so
nothing in CI or in any worker's gates has exercised it. Since it last ran the pipeline
gained: the tier cascade, the property-omit codemod, a push guard over the discarded-commit
range, branch deletion on abandonment, checkpoint serialiser registration, the
dependency-edit guard, staged-new-file support, and dependency-tree discarding. Every one of
those sits on the acceptance path.

Re-checked cheaply on 2026-07-30 at `bc1afdb` and it is still not obviously broken: the test
collects, and the production graph compiles with the real `StripeAdapter`, `TypeScriptAdapter`,
`TieredRemediator`, `GitHubForge` and a store. It now exposes **ten** nodes rather than the eight
this entry used to claim — `locate`, `prepare`, `patch`, `static_verify`, `push_branch`,
`await_ci`, `replay`, `open_pr`, `report`, `abandon`. Four of those postdate the last acceptance
run, which is the point: the wiring survived, and that establishes nothing about behaviour.

`build_graph` also refuses a store that cannot record a migration outcome, naming the missing
`record_migration_outcome(outcome)` and calling it the single write every benchmark axis reads
from. So the corpus wiring is checked at construction rather than at the end of a run.

**Run it with `-n0`.** `addopts` now carries `-n auto`, which applies to the e2e test too.

**This one is not a worker's to run unattended.** It opens a pull request on a real GitHub
repository and spends `xhigh` model time on the patch agent. It needs a human to decide
when, which is why it is recorded here rather than dispatched.

**Closes when:** one `sync run` produces a CI-green pull request again, or the failure is
recorded with which change broke it.

### B97 — The patch agent can exfiltrate a customer's secrets and no gate looks

Ranked first in the threat model's injection section
(`specs/2026-07-25-sync-threat-model.md`) and it is the only item there that the layer built on
2026-08-06 does not touch at all.

The patch agent holds `Bash` inside a clone of a customer's application repository. Such a clone
routinely holds `.env`, `.npmrc`, fixture credentials and CI configuration. `WebSearch` and
`WebFetch` are in `DISALLOWED_TOOLS` and that is a real block, but `curl` is a program rather than
a tool and the agent was given a shell. Every gate Sync has — `tsc`, `shipped_tree`,
`dependency_edits`, the customer's own CI — is a predicate on the *artifact*. None is a predicate
on the *run*. An attack that wants to ship something has to beat them; an attack that wants to
take something never meets them.

This is mitigation 1 of that document, restated with the attack that motivates it: the clone,
the install, the patch and the typecheck run in an ephemeral container with no credential in its
environment or on its filesystem, and no network egress after dependencies are installed. It has
been specified since 2026-07-25 and is what stands between Sync and the CodeRabbit shape.

**One bounded step landed on 2026-08-06 and the rest of this entry stands.**
`src/sync/remediate/tool_gate.py` is a `PreToolUse` hook on the patch run: a tool outside the six a
patch needs is refused, a shell command outside `git add`, `git status` and `npx tsc` is refused,
a compound or substituted command is refused before its first word is read, a write under `.git/`
is refused, and every call is recorded against the finding it belongs to. `curl` no longer runs and
the attempt is no longer invisible.

That is a predicate on what the agent may *ask for*. It is not an operating-system boundary, it has
not been observed enforcing — the CLI's honouring of a `deny` decision is taken from the SDK's own
contract, since watching it needs a model call the test discipline forbids — and the clone still
holds the secrets while the process still has a network stack. The close condition below is
unchanged, and the gate should be read as the cheap layer above the sandbox rather than as a
substitute for it.

**Closes when:** a patch run cannot open a socket to a host Sync did not name, proven by a test
that watches the attempt fail rather than by a configuration file asserting it.

### B98 — Injection-pattern matching and further prompt hardening, deliberately deferred

Layers two and three of the reference implementation's shape
(`references/engineering/llm-engineering-practice.md`, §2.6). Layer one — the untrusted-text
boundary — shipped on 2026-08-06. These two did not, and the reasoning belongs here rather than
being rediscovered.

**The pattern list fails in both directions at once.** It fails open, because the realistic
payload against Sync is not "ignore previous instructions" but a calm, correctly spelled paragraph
of plausible migration guidance, which is what a real deprecation notice looks like. It fails
closed, because vendor deprecation prose legitimately says "disregard the previous guidance" and
"this supersedes the note above" — and a defence that refuses Stripe is an outage. It is not
worthless, but it is worth less than the two items around it, and it must never be built in a form
that can refuse a legitimate entry silently.

Further hardening is cheaper and also lower value: the preamble already states the boundary once,
and a second sentence saying it again is not a second layer.

**What would change this ranking:** the first observed injection attempt. The refusal path built
on 2026-08-06 records one in `abandon_reason`, so the evidence will exist before the decision has
to be made again.

**Closes when:** either is built with a test proving it refuses a constructed payload *and* a test
proving it passes a real vendor entry, or this entry is closed as declined with the sample of
recorded attempts that justified declining.

### B101 — Two typechecks on one host race on a shared npx cache, and the loser looks like a bad patch

`run_tsc` (`src/sync/index/tsc.py:141-152`) falls back to `npx --yes --package=typescript@latest`
whenever a clone has no TypeScript installed. That resolver writes into `~/.npm/_npx/<hash>`, which
is shared by every process on the host. Two callers reaching it at once against a cold cache means
one is still writing the package while the other execs `node .../typescript/lib/tsc.js`, and Linux
answers `ETXTBSY`.

Observed in CI on 2026-08-06 (run `31099640833`): `pytest -n auto` put several xdist workers into
the fallback simultaneously and
`test_a_finding_reaches_a_verified_patch_through_the_real_graph` failed with
`abandon_reason='RuntimeError: could not establish a typecheck baseline ... process.execve failed
with error code ETXTBSY'`. **The failure mode is the expensive part.** It does not read as a
machine problem; it reads as a patch that could not be verified, which is exactly the verdict the
gate exists to produce honestly. A reviewer meeting it on a real finding would look at the patch.

The CI step *Warm the TypeScript npx cache* resolves the package once, serially, before the suite,
so no worker meets a cold cache. That is a fix for this repository's test run and nothing else —
two Sync remediations running on one host hit the same race with no step in front of them, and the
`--cache` npx flag is per-invocation rather than per-host so it does not help either.

**Closes when:** the fallback resolves TypeScript through a path that is safe to enter concurrently
— a lock around the resolve, a pre-resolved install directory the run owns, or an install into the
clone before the compile — with a test that starts two typechecks against a cold cache at once and
watches the current form fail before the fix lands. A test that merely runs two sequentially proves
nothing.
### B77 — one unexplained red in a database-backed suite, and no capture of it

`tests/test_status_rate_detector.py` ended a full run `1 failed, 2897 passed, 4 skipped, 6 errors`,
every failure and error in that one file, during B74. The immediate rerun was clean and the file
alone then passed three times, `27 passed` each. Nothing on that branch touches `sync.detect`.

**The obvious explanation was checked and does not hold.** The hypothesis was a concurrent
`truncate_all()` across the several worktrees live against the shared Postgres on 5433. But
`tests/conftest.py` gives every run its own database, named from its pid and its xdist worker id, so
two suites in two worktrees do not share one. The cross-run drop that *could* produce this shape --
a sweep removing a database out from under a live worker -- is the defect
`leaked_database_names` was written to close, and its docstring names the exact symptom it produced,
`database "sync_test_28096_gw2" does not exist`. That path is guarded and pinned by a test.

So the cause is unknown, and the honest record is that: one red, four subsequent greens, and the
leading theory eliminated rather than confirmed.

**The part that is actionable is the process failure, not the flake.** The failure text was gone
before anyone read it, because the rerun overwrote it. A one-off red that nobody captured cannot be
diagnosed later and cannot be told apart from a real defect that happens to be intermittent, which
is the same reason this repository does not accept a green it did not watch.

**Closes when:** either the failure is reproduced and explained, or a harness change makes a red
run's output survive the next run — and the second is worth doing whether or not the first ever
happens.

### B78 — no way to run the pipeline end to end without opening a real pull request

The console has no live data. `migration_outcome` holds three rows and none carries a `pr_number`,
the checkpoint tables are empty, and every UI verification so far has been done by hand-inserting
checkpoint rows — which tests the renderer against rows a human invented rather than against rows
the graph wrote.

**Most of this already exists and is not reachable.** `tests/test_cli.py:693` defines
`_LocalForge(GitHubForge)`, which keeps the real `push_branch` so a real branch lands in a real
origin and replaces only the two steps needing GitHub: `await_ci` answers green and
`open_pull_request` fabricates a `PullRequest`. `tests/test_cli.py:456` builds the fixture origin.
And `build_graph` already takes both the store and the checkpointer as parameters, so pointing them
at Postgres on 5433 needs no monkeypatching at all.

What is missing is the entry point. That test reaches the shape through `monkeypatch` with
`GraphStore` stubbed and `PostgresSaver` swapped for an in-memory checkpointer, so the run is real
and the rows go nowhere. There is no `--fixture` or `--dry-run` on `cli.run` — no spelling of one
exists.

This is not B7. B7 is the acceptance run against a real repository, it opens a real pull request,
and it stays gated on the user. This is the opposite: everything except the two steps that talk to
GitHub, against a fixture repo, writing real rows.

**Closes when:** one command drives `locate` through `open_pr` against a fixture repository, writes
real checkpoint and `migration_outcome` rows to the configured database, opens nothing, and is
covered by a test that watches the rows arrive. Whether the fabricated pull-request number counts
up across runs is a question for whoever consumes it.

**Task 2 of the dogfooding plan has landed** — the merge above `cc35120`. `build_graph` now accepts
`forge=None` and omits `push_branch`, `await_ci` and `open_pr` from the compiled graph rather than
guarding them at runtime, and a verified patch with nowhere to push routes `replay → report` and
records `terminal_status="halted"`. Two facts that came out of it and are worth carrying:

- **Before it, `forge=None` did not crash — it abandoned.** `None.push_branch(...)` raised inside
  the node's own handler, which set `fatal` and routed to `abandon`. So anyone who ran forge-less
  got a plausible-looking `abandoned` run with a Python traceback fragment in `abandon_reason`.
- **`"halted"` is a fourth `terminal_status`**, alongside `retried`, `opened` and `abandoned`. The
  column is plain `TEXT` with no `CHECK`, and `benchmark.axes` branches on `"abandoned"` alone, so a
  halted row lands in `counts.attempts` and in `routing_accuracy` and is excluded from every merge
  rate. Additive, no migration. It touches the run-state vocabulary spec, which the console session
  owns.

What remains for B78 is the entry point itself — Task 3 and the tasks below it.

### B79 — a rehearsal row and a production row collide on the corpus natural key

`migration_outcome` is upserted on `(finding_id, attempt_index)` with `ON CONFLICT DO NOTHING`
(`store.py:546`). That clause is the idempotence guarantee the pipeline discipline requires and is
not the defect.

The defect is that a run has no identity in that key. A forge-less rehearsal writes
`(f, 1, halted, pr_number=NULL)`; if the same finding at the same attempt index is later run with a
forge against the same database, `open_pr`'s `(f, 1, opened, pr_number=1)` is dropped silently and
that pull request never enters `merge_rate` or `counts.pull_requests_opened`.

Pre-existing rather than introduced — before the Task 2 merge the same path wrote
`(f, 1, abandoned)` — but B78's whole point is to make rehearsal runs routine, which turns a
theoretical collision into an expected one. It bites only when a rehearsal and a production run
share a database and a finding id.

**Closes when:** either a rehearsal's rows are distinguishable from a production run's at the grain
the corpus declares, or `schema.sql` states as a comment why sharing a database between the two is
not supported and something refuses it. Deciding which is the work; do not change the conflict
clause.

### B76 — three small truths about how this CLI reads files, left over from B73

Recorded rather than folded into B73, because each is a decision and none is a typo.

- **A whitespace-only `--secret-file` still answers the both-sources message.** An operator who
  passed `--secret-file` is told to set the environment variable or pass `--secret-file`, which is
  advice they have already taken. Fails closed, so this is confusion rather than a security defect.
  It is the same confusion B73's third ground names, on the one case that commit did not reach.
- **`_signing_key`'s docstring says "a key that is present and unreadable answers `None` like an
  absent one".** It does not: the read sits outside the `try`, and only unparseable material answers
  `None`. This sentence is what B73's brief was built on and what the implementer had to correct, so
  it has already cost one round of work. Its own read is unguarded too, and an unreadable key file
  tracebacks out of `publish-feed` and `feed-public-key`.
- **`benchmark` catches `ValueError`, which subsumes `UnicodeDecodeError`.**
  `tests/test_decode_handlers.py` inventories handlers by the exception *names* a chain lists, so
  that one is invisible to the gate — neither counted nor required to have a driver. A handler
  spelled `ValueError` is a hole in that gate's coverage by construction, and the gate cannot see
  its own blind spot.

Two more reads still have no handler at all: `intake --registry-directory` and the `--score-pair`
specification.

**Closes when:** each of the three is either fixed or carries a comment saying why the current
answer is right, the two remaining reads refuse like their siblings, and the decode gate either
sees `ValueError`-spelled chains or says in its own text that it cannot.

### B115 — Four columns on the binding surface each miss a single line by a handful of pixels

Measured 2026-08-06 at 1440x900 with `--scale 10000`, after M4.5-W144 factored the shared directory
out of the path column.

The whole table now wants **1,154px** of content width and is granted **1,345px**, so every column
could sit on one line — and the row is still two, because auto table layout balances columns rather
than minimising height. Each of the four wrapping columns misses by a little, comparing content box
(granted minus 16px of padding) against what the value needs:

| column | content box | needs | short by |
|---|---|---|---|
| Call site | 291 | 296 | 5 |
| Repository | 135 | 148 | 13 |
| Indexed at | 135 | 148 | 13 |
| Argument keys | 192 | 214 | 22 |

**Closing this would take the row from 57px to about 37px** — `row-md` plus nothing — which is another
seven rows per viewport height on top of the four M4.5-W144 bought.

Why it is an entry rather than that commit: the only lever left is explicit column widths, and a
fixed width is a bet about customer data. `seed-console-scale` is 18 characters; a repository named
`acme-payments-platform-integration` is 34 and would wrap under any width chosen against this
fixture, while a `table-fixed` layout would clip rather than wrap and take `break-words` out of the
picture — which B109 established must not happen, because it is what keeps the rung column on screen
at 1280px.

**Closes when:** the row measures at or under `row-md` at `--scale 10000` **and** at a second fixture
whose repository ids and argument-key lists are visibly longer than this one's, with the heights at
both. A width that only holds for one seed is not a fix, it is a coincidence that will be read as
one.

**Amended 2026-08-06 by M7-W160, which made this worse and says so.** The chassis takes content width
from every screen — the frame grew 24 to 40px to clear the 4.7–7.2 ratio, and the sidebar takes the
rest — and this table had no width to give.

**Re-measured the same day after the sidebar was rebuilt as one component at two widths**, replacing
a 56px icon rail plus a 240px contextual panel. The rebuild changes every figure below, so the first
table is replaced rather than annotated. Measured on the binding surface at `--scale 10000`, reading
the content box inside the frame, at both viewports and both widths:

| | content | call site column | row |
|---|---|---|---|
| before M7-W160, 1440 | 1232px | 256px | 57px |
| 1440, collapsed *(the default here)* | 1297px | 281px | **57px** |
| 1440, expanded | 1137px | 231px | **77px** |
| 1280, collapsed *(the default here)* | 1137px | 231px | **77px** |
| 1280, expanded | 977px | 181px | **77px** |

Two things the shape of that table says that the previous one could not. Collapsed at 1440 the
console now has **65px more** content width than before M7-W160 rather than 57px less, because one
48px sidebar is narrower than the 56px rail it replaced — the chassis is no longer a net cost at the
viewport it is measured at. And 1440-expanded and 1280-collapsed land on the same 1137px, which is
the useful coincidence: the sidebar's two widths and the two viewports are one axis, not two.

**This measurement corrected the default rather than only describing it.** The sidebar auto-collapsed
below 1440, which expanded at exactly 1440 — the row-height row above says that costs 20px on every
row there. The threshold is now **1473px**, the narrowest viewport at which an expanded sidebar still
leaves 1170px of content: the frame, the sidebar and a scrollbar take 303px. Both viewports in the
table therefore load collapsed, which is why the parenthetical moved.

**The 1280 row height does not improve. It is 77px collapsed and 77px expanded**, unchanged from the
first pass, and stating that plainly was the point of re-measuring. The mechanism, found by holding
the sidebar collapsed and stepping the surface's width in 2px increments: the row drops from 77px to
57px at **1170px of content width** and nowhere else. 1440-collapsed clears it by 127px. Every other
configuration — including 1280 with the sidebar already shut, at 1137px — is below it, 1280-collapsed
by **33px**. So the collapse is worth 20px of row height at 1440 and worth nothing at 1280, and no
sidebar width reachable from here closes a 33px gap that a 48px sidebar has already spent.

That threshold is the number this entry was missing. It converts "four columns are short by 5 to 22px"
into a single testable figure, and it is what a fix has to clear.

**And there is a second one above it, which is the first evidence that the target height is reachable
at all.** At 1920 wide — the window the owner actually works in — the sidebar loads expanded and the
content box is 1617px, where the row measures **37px**. That is the figure this entry names as what
closing it would buy, arrived at by width alone with no column widths declared. So the shortfall is
confirmed to be exactly what it says it is — a few pixels per column, not a structural cost — and a
fix that reclaimed 33px at 1280 would be buying a known result rather than an estimated one.

This does not argue for a narrower frame: 40px is the smallest value clearing the ratio, and the
ratio is what
`docs/superpowers/reports/2026-08-06-why-the-console-came-out-flat.md` identifies as one of the two
refusals that kept the console flat. It argues that **this entry is now on the critical path for the
1280 case rather than an improvement to it.**

**Amended 2026-08-06 by M7-W164, which took 1280 from 33px short to one pixel short and did not
close it.** That item moved the binding surface onto the chassis and dropped the `Card` around both
of its tables. A card spends 32px on `CardContent`'s horizontal padding, and this is the one table in
the console where 32px changes a row's height.

The important correction is what the threshold is a property of. Every figure above reads the content
box inside the frame, which had the card's padding inside it — so "1170px of content" was really
"1138px of table". With the card gone, content width and table width are the same number, and the
threshold restates as **1,138px of table width**, re-measured by stepping the viewport in 1px
increments with the sidebar collapsed. Measured at `--scale 10000` on the same operation:

| | content | table | call site column | row |
|---|---|---|---|---|
| 1440, collapsed *(the default here)* | 1297px | 1297px | 292px *(was 281)* | **57px** |
| 1440, expanded | 1137px | 1137px | 241px *(was 231)* | **77px** |
| 1280, collapsed *(the default here)* | 1137px | 1137px | 241px *(was 231)* | **77px** |
| 1280, expanded | 977px | 977px | 191px *(was 181)* | **77px** |
| 1281, collapsed | 1138px | 1138px | 242px | **57px** |

**1280 is short by one pixel.** 1281 is not. That is measured rather than derived, and it is the most
this entry can say: a threshold cleared by a single pixel against one fixture is a coincidence, not a
property, which is exactly what the closing condition below already refuses to accept. **The
condition is unchanged and this entry stays open** — a second fixture with visibly longer repository
ids and argument-key lists is still what would settle it, and against that fixture a one-pixel margin
would evaporate.

The 1473px auto-collapse threshold above is now conservative rather than wrong: it was derived from
1170px of content, and 1138px of content is enough, which puts the true figure at 1441px. It is left
where it is deliberately. Moving it would expand the sidebar at 1441 on a one-pixel margin, and the
20px per row it costs when the margin is missed is worse than the label it buys.

### B105 — Four statements in `DESIGN.md`'s rendered-pixel section are contradicted by the rendered pixels

**Closed 2026-08-06 (M4-W149).** The ring renders at full strength — `focus-visible:ring-ring` on
`button`, `input`, `textarea` and `input-group` — so the published figure is now the token's own,
re-measured at **8.70** against the card and **9.50** against the page plane. 3.08 with no second
channel was judged unacceptable rather than documented: it cleared the non-text floor by 0.08, and
on the `outline` variant it is the only channel there is. The two outline-button rows now name their
backdrop, which is what was actually missing — 10.76/8.03 over the card, 12.08/8.68 over the page
plane. The `TableRow` row is rewritten as history. `test_no_focus_ring_is_washed_by_an_alpha_modifier`
holds the ring.

Two corrections to the finding below, from re-measuring at `f725efb`: **12.09 is reproducible** —
over `--color-surface-sunken` the resting pairing is 12.08, and the "11.6" recorded here was an
arithmetic slip rather than a property of the ramp. And `TableRow`'s hover fill is not simply gone:
it is now the named step `bg-surface-subtle` at full strength, gated behind `data-interactive="true"`,
which no caller passes — so no row hovers, and one that did would measure 13.79 rather than 14.80.

Same measurement as B104. This is the one section of the contract whose whole purpose is to be
checkable against a screen, and four of its claims do not survive being checked.

- **The focus ring: 8.69 claimed, 3.08 measured.** *Non-text, against the 3:1 floor* says the ring
  "clears it comfortably: 8.69, against `--color-surface`". The token does — 8.70. What renders is
  `focus-visible:ring-ring/50`, the brand hue at half strength, compositing to `rgb(84, 101, 139)`:
  **3.08:1** against the card, **3.12:1** against the page plane. It clears the non-text floor by
  0.08. It is also the only channel — `outline-style` is `none` and the border stays
  `--color-input` under focus — so 3.08 is the whole of what a keyboard user sees.
- **The outline button: 12.09 and 8.70 claimed, 10.76 and 8.03 measured.** In the gamma-encoded sRGB
  Chrome composites in, `oklab(0.578 0 0)` is `#7a7a7a`, so `input/30` over `--color-surface` is
  `0.3 × 122 + 0.7 × 23 = 53` and `#f0f0f0` on it measures **10.76**; `input/50` is 72 and measures
  **8.03**. No backdrop in the ramp reproduces 12.09 — over `--color-surface-sunken` the resting
  fill is 45 and the pairing is 11.6. Both still clear 5.05, so these are wrong numbers rather than
  unsafe colours.
- **`TableRow`'s hover fill is documented in the present tense and is gone.** The table keeps `ink`
  on `surface-subtle/50` at 14.80 "as the measurement of what the tree renders today". A real
  pointer on a row now leaves `background-color` at `rgba(0, 0, 0, 0)` with the row's own
  `transition-duration` at 0s — section 15.5's ruling, correctly built, and the document has not
  caught up.

Why this is not pedantry: the contract's own argument for the section is that "a pairing that passes
on declared tokens can fail on rendered colour once opacity, layering or a chart fill is involved."
A published 8.69 that renders 3.08 is that failure, in the section written to prevent it, and the
next reader has no way to tell which of the seven rows to trust.

**Closes when:** either the ring renders at full strength — `ring-ring`, at which point 8.70 becomes
true rather than restated — or the section carries the composed figures with the arithmetic beside
them, and the retired `TableRow` row is rewritten as history rather than as current. Whichever is
chosen, the four numbers are re-read off a running instance, not recomputed from tokens.

### B106 — Every route's heading list opens with the title of a dialog that is not open

**Closed 2026-08-06 (M4-W149).** `DialogHeader` moved inside `DialogContent` in `command.tsx`, so
Radix unmounts it with the rest of the closed dialog. Walked on the running console: the first
heading is the page's own `h1` and the 1px description paragraph is gone. The accessible name was
verified rather than assumed — with the palette open, `aria-labelledby` resolves to "Jump to a
destination" and the node it names is inside the content, which is the association Radix wants and
which the hoisted header did not have. `test_no_dialog_heading_sits_outside_its_dialog_content`
holds the structural cause; nothing here can walk a rendered document.

Same measurement. No route skips a heading level. But on all nine, the first heading in the document
is `h2 "Jump to a destination"` — the command palette's title — ahead of the page's own `h1`.

`command.tsx:49` puts `DialogHeader` **outside** `DialogContent`. Radix unmounts the content when
the dialog is closed; the `sr-only` header is not inside it, so the title and its description sit in
the document permanently. A screen reader's heading list therefore begins with a closed dialog, and
the description ("Search the console's declared routes.") is a permanent 37-character paragraph in a
1px-wide container that every prose measurement has to filter out.

The console's navigation hierarchy *is* the dependency graph, and the heading tree is the only
machine-readable assertion of which level of it you are looking at
(`loops/console-improvement-tick.md`, item 3). An `h2` from a closed overlay in front of the `h1` is
that assertion starting with something that is not a level.

**Closes when:** the palette's accessible name comes from inside `DialogContent`, or from an
`aria-label` rather than a heading, and a walk of every route finds `h1` first.

### B108 — The validation ring is washed the way the focus ring was, and it is spelled against a token that does not exist

Found while closing B105 (M4-W149), and left rather than swept into it because it is a different
question wearing the same shape.

`button.tsx`, `input.tsx`, `textarea.tsx` and `input-group.tsx` each carry
`aria-invalid:ring-destructive/20` and `dark:aria-invalid:ring-destructive/40`. Two problems, and the
second is the bigger one. The alpha is the same defect the focus ring had: a contrast figure nobody
computed, unreadable off the class name, and `test_no_focus_ring_is_washed_by_an_alpha_modifier` is
deliberately scoped to focus rings so it does not force this to be answered in the same commit.
`--color-destructive` is also not a token `DESIGN.md` declares — the contract's vocabulary is
`critical-ink` / `critical-surface` — so these classes are shadcn defaults referring to a colour this
project never argued for.

Nothing sets `aria-invalid` in the console today, so this renders nowhere and is not urgent. It is
also not free to leave: the first form that validates inherits an unmeasured ring in an undeclared
colour.

**Closes when:** the invalid state is expressed in declared tokens at a strength measured against the
3:1 non-text floor, `destructive` is either declared in `DESIGN.md` or gone from `web/src`, and the
ring guard's scope widens from focus rings to every `ring-*/n` with the narrowing comment deleted.

**Closed 2026-08-07 by observation, and how it was read wrong first matters more than the closure.**
Twelve consecutive runs from 02:27 to 13:51 UTC ran zero zero-step jobs, checked run by run. The
cause was never visible from here and is not now; it stopped.

`zero_step_jobs` in the profiler stayed flat at **14 across both profiles**, which read as the
failure persisting and nearly stopped a tick on its own. All 14 were the 2026-08-06 incident, still
inside a 30-run sliding window. **A cumulative count over a sliding window cannot tell a failure
that is continuing from one that has stopped** — only the per-run check can, and it is one `gh api`
call. The metric stays because a rising count is still the alarm; what changes is that it is a
prompt to check per-run, never a verdict.


### B113 — Two guards in the node-status wash are unreachable, and the audit could not safely delete them

Measured 2026-08-06 while auditing motion for M4.5-W143. `ChangeWash`
(`features/workflows/node-sequence.tsx`) carries two defensive guards and **neither can fire**:

- `mounted.current` short-circuits the first effect run. Removing it changes nothing, because
  `previous` is seeded with `useRef(status)`, so the comparison below it is already equal on the
  first run.
- `previous.current !== status` guards against an unchanged refetch. Removing it changes nothing
  either, because the effect's dependency array is `[status]` — it does not run at all unless the
  status changed.

Both breaks were applied to the real component and **all four tests in `node-sequence.test.tsx`
still passed**, which is how they were found. `CLAUDE.md` forbids handling conditions that cannot
occur, so this is debt by that rule's own terms.

**Why M4.5-W143 did not delete them.** The trigger is a live poll observing a status transition, and
that session could seed no live run against the graph to exercise it end to end. Simplifying the one
animation the console has left, on reasoning about React's effect and ref semantics rather than on a
run, is a worse trade than a redundancy that is written down — so the finding went into the test's
docstring, where the next reader meets it beside the code.

**Closes when:** either both guards are gone with a run that shows a real status transition still
washing exactly once and a mount still washing nothing, or a comment in `ChangeWash` names the
condition each one actually catches. What must not happen is the guards staying with no explanation,
because that is a comment claiming somebody argued for them.

### B114 — The one hover transition left is on the frequency gate's wrong side, and nobody has measured whether it matters

Measured 2026-08-06 at 1440×900 with a real pointer and `:hover` matching. Every interactive control
in the console carries `transition-colors` from `button.tsx`'s base class, rendering
**`transition-duration: 0.15s`** on 11 elements on the vendor findings screen, 7 on the binding
surface and 6 on Signals. The shape is right and is not in question — `transform: none`,
`scale: none`, `box-shadow: none`, `opacity` unchanged, only the fill alpha stepping `input/30` to
`input/50`.

Section 15.2 of `2026-08-05-sync-console-architecture.md` overturned the references' literal
`transition-duration: 0s` for a dense surface, and `DESIGN.md` replaced it with a frequency gate:
*a surface the operator crosses repeatedly takes no transition at all*. **The gate and the
implementation now disagree in one place.** `TableRow`'s hover was correctly given none because a row
is crossed on every pointer move. A paginator's Previous and Next are the most frequently *clicked*
controls on a long table, and they take 0.15s because they are the same `Button` as a dialog's
confirm.

This is one entry rather than a change because the fix is a design-system decision with a real trade:
either `Button` gains a variant whose transition is zero and the frequent call sites take it, or the
gate is refined to say that frequency is about crossing rather than clicking and the 0.15s is correct
everywhere. Both are arguable and neither is measured.

**Closes when:** the disagreement is resolved in `DESIGN.md`'s Motion section — with the rendered
`transition-duration` on a paginator and on a dialog control measured either side of whatever
changes, or with an argued statement that one value is right for both.

### B116 — The chassis exists and nine screens have not moved into it

M7-W160 replaced `layouts/` with a rail, a contextual sidebar, a page header, a control bar, a footer
bar, fact tiles, a fact list and a skeleton, and reversed the two `DESIGN.md` refusals that the flat
console rested on. **Nothing in `features/` changed, on purpose** — that constraint is what made the
frame reviewable apart from the pages — and the measurement says exactly what is left because of it.

Measured at 1440x900 across all nine routes plus the router's fallback, before and after:

| | before | after |
|---|---|---|
| frame ratio (frame ÷ `--spacing-row`) | 3.0 on nine of nine | **5.0 on ten of ten** |
| type range, the nine feature routes | 2.00–2.67 | **2.00–2.67, unchanged** |
| type range, the one route the chassis owns | 2.00 | **3.43** |
| widest text on six routes | a stat-tile figure | a stat-tile figure, unchanged |

The frame moved because it is now a token the chassis owns. **The type range did not move on any
feature route, and it cannot until those screens render `PageHeader`.** The display step is declared,
guarded to exactly one consumer, and mounted on `layouts/unknown-route.tsx` — the router's fallback,
the one screen the chassis owns — where it measures 48px and takes the range to 3.43:1 against that
route's 14px floor. Nine screens still open with a `text-page` `h1` and, on four of them, several
paragraphs of prose before any data.

So the remaining work is not more chassis. It is: give each screen a `PageHeader` carrying its own
`RouteEntry.question`, move its filters into `ControlBar` and its paging into `FooterBar`, and turn
the facts it renders as prose or table columns into `FactTile` and `FactList`.

**The guard that finishes this is written and cannot land yet.**
`reports/2026-08-06-why-the-console-came-out-flat.md`'s fifth correction asks for a test that fails
when a route renders nothing at the display tier. `test_exactly_one_component_spends_the_display_step`
holds the half that is true today; the other half needs all nine screens to have adopted the header,
so it goes red on nine routes if written now. It belongs in the commit that finishes the migration,
and writing it earlier would mean either nine skips or a guard nobody can keep green.

**Closes when:** every route renders something at the display tier, measured, and the type range
clears 3.4:1 on each of the nine — with the presence guard landing in the same commit.

**Two of the nine landed 2026-08-06 under M7-W164:** the Binding surface and the Vendor level, both
measured at 1440x900 and 1280x800 at **4.00:1**, with regions placed beside another going from one
to two on each. The presence guard still cannot land — it goes red on whatever remains — and the
count of routes it would fail is the only thing this entry needs updating for.

### B126 — every remediation run starts cold, and the facts it rediscovers do not change

**Renumbered from B122 on 2026-08-16, landing the console line.** Two items were both filed as
B122 on separate branches — this one and "the Finding level cannot name its own severity" below —
and merging them onto one `main` would have let the collision stand. B126 is the next free number.

**Designed and planned, deliberately not started.** The console is the current focus and this is
pipeline work; it sits at the bottom of Ready so a tick takes the console items first.

- Design: [`specs/2026-08-06-sync-repo-context-design.md`](specs/2026-08-06-sync-repo-context-design.md)
- Plan: [`plans/2026-08-06-sync-repo-context.md`](plans/2026-08-06-sync-repo-context.md), seven tasks

`build_patch_prompt` assembles the vendor change, the call site and the required edit, and nothing
else. So an agent rediscovers the same stable facts about a repository on every finding — which
package manager the lockfile names, which directories are generated, which conventions the codebase
keeps. The facts do not change between findings and the rediscovery is not free.

The design adds a `repo_context` table at one row per repository, a `sync.context` package that
touches no database, a section in the prompt's cacheable prefix, an operator write path on the
console API and the CLI, and an optional `.sync/context.md` a customer may commit and Sync never
writes back. Two constraints shaped it: `sync.mcp.tools` is frozen, so context reaches an agent as
a resource template and an `initialize`-time `instructions` field rather than a fifth tool; and
nothing is written into a customer's checkout, so the store holds a copy and the committed file
stays the original. Precedence follows from the second — when Sync and the customer disagree about
what is true of the customer's repository, the customer wins.

**Why it is worth doing rather than merely appealing.** `CLAUDE.md` requires every agent to shorten
the critical path or improve a result. The context section sits ahead of the diagnostics block, so
it is inside the prefix that stays byte-identical across retries of one finding: supplied facts are
facts not derived, and a retry re-reads them from cache rather than paying for them again.

**Independent corroboration.** Superlog probes a candidate repository's default branch for
`CLAUDE.md`, `AGENTS.md`, `.cursorrules` and `.github/copilot-instructions.md` before handing it to
an agent, so the agent follows the repository's conventions
(`references/notes/superlog-investigation-mechanism.md`, section 7). Same instinct, arrived at
independently — evidence for the seed-file half of this design rather than the operator-written
half.

**What it does not do, on purpose.** No agent writes context. That is memory rather than context
and is a separate item; `CONTEXT_SOURCES` ships with `seeded-file` and `operator` only, and the
plan asserts that so a third member is a deliberate edit rather than a quiet one.

**Evidence that closes this:** the seven tasks land with `uv run pytest` green,
`tests/golden/tool_schemas.json` unmodified, and `build_patch_prompt` proved byte-identical for a
repository with no context. The first two are assertions in the plan rather than review
judgements.

## In flight

**Rewritten 2026-08-07.** The section had gone stale in the way it warns against below: it described
Orca dispatch as undelivered, briefs as needing a file because messages truncate, and a toolchain
gap as affecting one worktree. Two of those are now wrong and the third is wrong in its detail.

### Actually in flight

- **`M7-W182`, the fidelity pass** — six tasks against the measured gaps, held by the console
  session in this worktree. Its working tree has `DESIGN.md`, `app-frame.tsx`, `command-palette.tsx`,
  `error-surface.tsx`, `error-log.ts`, `motion.ts` and two test files open, plus an untracked
  `scope-switchers.test.tsx` written before its component. **Do not gate `web/` against the working
  tree while this runs** — `tsc` will fail on a test whose subject does not exist yet, and that is
  correct RED rather than a defect. Gate a commit instead.
- **`CI-W167`, B111** — dispatched twice into `m4-idiom` and started neither time. Its brief rendered
  into the terminal and was never submitted. Needs a fresh terminal rather than a third nudge.

### What is no longer true

- **Orca dispatch works.** `worker-start --task <id> --worktree "id:<repo>::<path>" --agent claude`
  has delivered every item from `M7-W159` onward. The Agent-tool workaround this section described is
  retired. What does still bite: **a spec passed to the CLI must be ASCII** — em dashes arrive as
  cp1252 mojibake — and a long mid-turn `send` can still reach a worker truncated, which is how
  `M7-W160` was built to a superseded brief and had to be reworked.
- **`status.worker == "ready"` does not mean a worker finished.** A worker mid-edit reports exactly
  that with `terminal: running`. And a worker may finish without ever sending `worker_done`:
  `M7-W160` did, and a coordinator blocking on the mailbox would have waited forever. Read the
  terminal.
- **The oasdiff gap is not one worktree's.** The measurement below said only `sync-m4-dashboard`
  lacked `tools/`; that tree has it and three others do not. It is a property of **any fresh
  worktree**, because `tools/` is gitignored and `_binary()` resolves it relative to the worktree
  root. On 2026-08-07 it cost an hour in `superlog-reference`: 38 failures and 9 errors, identical
  under `-n auto` and `-n0`, which rules out the Postgres contention a coordinator reaches for first.
  Run `bash scripts/bootstrap_tools.sh` once per checkout and the suite returns its exact baseline.

### Two hazards that survive

- **Two sessions share `sync-m4-dashboard`.** Commits from the other session appear in the tree
  between a gate and a push, and one has already been carried to `origin` by a push that meant to
  carry only its own. Stage by explicit path, read `git log --oneline -5` before assuming the tree is
  yours, and never `git stash` in it.
- **`SYNC_API_RELOAD=true` bounces the owner's API on every save** another agent makes in the shared
  worktree. It killed 8789 once on 2026-08-07. The flag still earns its place — a long-lived API
  serving stale Python is the more expensive failure — but expect the blip.

Entries stay under **Ready** above with their full reasoning until they land, because the reasoning
is what a reviewer needs and duplicating it here would let the two copies drift. Whoever lands an
item clears its line here in the landing commit; whoever dispatches one adds it in the same breath.

## Done

- **B110** — the binding surface's rows are 57px, and no column stopped being a fact. Measured at
`--scale 10000`, before and after: row height **76.5px -> 56.5px** at both 1440x900 and 1280x800,
rows per viewport height **11 -> 15** at 900px and **10 -> 14** at 800px, and the table's total
content demand **1,712px -> 1,154px**. Landed on `m45-density` under M4.5-W144.

  **The entry was right that there is nothing opaque here and wrong about where the width goes.**
  All nine columns are distinct facts, and none was deleted. But the path column wanted 854px of the
  1,345px available and **65% of what it held was a directory identical on every one of the 2,500
  rows** — a fact about the *set*, being re-rendered once per row. So the fact moved to where it is
  true: `call_sites_common_directory` is computed in SQL over the filtered set, stated once in a
  sentence above the table, and each cell carries what follows it. `create-charges-handler-000000.ts:1:1`
  instead of a 104-character path, which is the filename and line a reader matches against their
  editor. Nothing is truncated and nothing is hidden: the whole path is the sentence plus the cell,
  both on screen, and `break-words` is untouched.

  Computed over the **set** and not the page, deliberately. A prefix folded client-side over fifty
  rows would make the same call site render differently on page one and page two — a column whose
  meaning depends on where the reader is standing. `min(path)`/`max(path)` under the page's own
  predicate is the whole scan, because the longest common prefix of a set is the longest common
  prefix of its lexicographic extremes, and it costs nothing measurable: 24-26ms at `--scale 10000`.
  Truncated at the last `/`, which is the correctness condition rather than a nicety — `create-a.ts`
  and `create-b.ts` share the characters `create-`, and stopping there names a directory that does
  not exist and leaves a remainder nobody can rejoin.

  **The honest half: on the first screenful this is a wash.** The sentence costs about 96px above the
  table, which is roughly what the first five rows save, so rows fully visible from the page top are
  **5 before and 5 after** at 1440x900 and **3 before and 3 after** at 1280x800. The win is in
  scrolling a long table — every screenful after the first holds four more rows, and the prefix is
  paid once against 2,500 rows — not in what an operator sees before they touch the wheel. B115
  carries the four columns that each miss a single line by between 5 and 22 pixels, which is what
  would take the row to 37px.

- **B100** — the long tables can be ordered, and every page says how it is ordered. A named
ordering reaches SQL as an `ORDER BY` ahead of the page's own `LIMIT`, so the page is the first page
of the ordered set rather than an ordering of the first page. Two orderings and no more:
`first-seen`, which is what this shipped with and is now *named* rather than merely happening, and
`severity`. Landed on `m45-affordance` under M4.5-W141.

  All three questions the entry said had to be settled rather than assumed:

  **What an operator orders by.** Severity, and the ranking is invented because nothing stores one
  — `Severity` is a `Literal` with no order anywhere in the graph. So `SEVERITY_ORDER` sits in
  `sync/core/models.py` beside the vocabulary it ranks, not in a view, and
  `tests/test_core_contracts.py` asserts the two cover each other exactly: a sixth severity fails a
  test instead of silently sorting to the end of a page somebody opened to see the worst first. The
  rank then **travels in the payload** rather than being restated in TypeScript, so the sentence on
  screen is derived from the ordering that ran. A severity outside the rank sorts last, not first —
  `array_position` yields NULL and NULLs sort last under `ASC`, which is the behaviour to want.

  **What a stable order costs at scale.** Nothing measurable. At `--scale 10000` over 2,500 matching
  findings: default **27–38ms**, severity-ordered **26–37ms**, and a deep page at offset 2400
  **35–43ms**. `finding.created_at, finding.id` is the tiebreak on *both* orderings, because two
  findings of one severity without a total order make `LIMIT`/`OFFSET` pages overlap and skip, and
  the row that falls between two pages is the one nobody sees.

  **What the control claims.** The ordering is stated in words on every page whether or not anybody
  chose one — *"Ordered as Sync found them — the oldest open finding first"* — which was the honest
  half of this entry: the table was never unordered, it just never said so. The applied ordering
  comes back in the envelope rather than being read from the URL, so a hand-edited `?order=` cannot
  leave the screen naming an arrangement the rows are not in, and changing the ordering clears the
  page offset because offset 250 in one ordering is fifty different findings in the other.

  **A dependency was not added.** B90's slice-1 worker declined TanStack Table with an argument and
  this did not overturn it. The argument holds and got stronger: the failure mode a table library
  invites is a client-side sort over the fifty rows already fetched, reported against a total drawn
  from all 2,500. What was needed was one `ORDER BY` and one sentence, and neither is what a headless
  table library is for.

- **B109** — the finding-id column is gone and the call site is the way into the finding. Measured
at 1440x900 with `--scale 10000`, before and after: a body row **76px → 56px**, rows above the fold
**11 → 16** at 900px and **14** at 800px, DOM nodes **733 → 689**, and the call-site column
**644px → 797px**. The API page is unchanged in cost — 17,081B → 17,174B, the +93B being the two new
envelope fields — because this is a rendering change and not a payload one. Landed on
`m45-affordance` under M4.5-W141.

  **The entry named the wrong column and the measurement caught it.** It said the finding id was the
  tallest thing in the row, at three wrapped lines in a 164px column. The call-site path beside it
  was wrapping to **four**, needing 837px in a 644px column. Both had to move, and only one of them
  could: the path is the row's identity in the operator's own terms and `break-words` on it is what
  keeps the rung column on screen at 1280px. So the id column — an opaque 32-character hash that a
  reader clicks rather than reads — gave its 164px to the path, and the click moved onto the path
  itself.

  The id stays reachable in full, which was the closing condition: it is the heading of the page the
  link opens, and it rides the link's accessible name so a screen reader announces which finding a
  path leads to. A sentence under the table says both, because a column that disappears without
  explanation reads as a column that was lost.

  **Two candidates the entry offered were measured and rejected.** A leading fragment of the id
  fails on data Sync does not control: the fixture's ids are `seed-console-scale-finding-000004`, so
  the first eight characters are identical on every row and the column would render `seed-con…`
  two and a half thousand times. `whitespace-nowrap` plus the table's own horizontal scroll keeps the
  id verbatim but buys the same 20px at the cost of a sideways scrollbar on the console's primary
  table, which is a worse trade than an opaque column being one click away.

  **What did not close, honestly.** The path still wraps to two lines: 797px against 837px of
  natural width, forty pixels short. Closing that last line means truncating a path, and B110 carries
  the same question for the binding surface where it is sharper.

- **B104** — the table's rows measure what the contract says they measure. `table.tsx` took
`py-row` on both cells and `h-10` on the header, so the padding is derived from a height chosen
from the scale rather than the other way round. Measured in Chrome at 1440x900 across seven tables
on the Fleet screen, before and after: a single-line body row **40.5px -> 36.0px** (`row-md`) and a
header row **36.5px -> 40.0px** (`row-lg`) — the two declared heights were in each other's slots,
which is worse than merely off and is why the guard is arithmetic rather than a string match.
`--scale 10000`, vendor findings table: header **52.5 -> 48.5px**, body rows **80 -> 76px**. 10px
left the rendered spacing census on every route that has a table. Landed on `m4-tokens` under
M4.5-W142 with `DESIGN.md`'s *Row height* correction and
`test_a_body_row_measures_the_row_height_design_md_derives_for_it`.

  **Two claims in this entry were wrong and the correction matters more than the fix.** It said
  "roughly a third of the viewport spent on padding nobody chose". Padding was 20px of an 80px row;
  the row is dominated by the Finding cell, whose 32-character id wraps to three lines at 56px in a
  164px column. And the 4px saving buys **no extra rows**: 900/80 and 900/76 both floor to 11 rows
  above the fold. The fix is right for the reason the contract gives — a declared number that does
  not render is a number the next reader trusts and should not — not for the density it was sold on.
  B109 carries where the rows actually go.

- **B107** — the third neutral ink is gone from DOM text. `run-outcome.tsx`'s panel body takes
`text-ink-muted` and `filters.tsx`'s active-filter value takes `text-ink`; the ink census on the
solution workflow and pull request screens went from **three neutral levels to two** (`ink` and
`ink-muted`, plus the brand accent where a link exists), measured at 1440x900. The floor was never
in tension: the panel prose measures **7.75:1** at `ink-muted` on `surface-sunken` against a 5.05
floor, up from `ink-secondary`'s 11.57 and still far above it. `--color-ink-secondary` keeps its one
real consumer — `corpus-chart.tsx`'s legend `textStyle`, painted inside a canvas — and `DESIGN.md`
now says that is its job rather than "prose that is not the headline value", which is the sentence
that invited two components to spend it on DOM text. The guard bans the class, not the token.
Landed on `m4-tokens` under M4.5-W142.

  One census artifact worth knowing before the next reading: the workflow screen also paints one
  element at `oklch(0.155 0 0)`, which is `surface-sunken` used as ink on an `ink`-filled node
  marker. That is the inverse of the same pair, not a third level.

- **B96** — the route registry is checked against the specification that defines its levels.
`tests/test_console_hierarchy.py` parses the authoritative fenced block and `GRAPH_LEVELS` and
asserts they name the same levels in the same order. Block selection fails loudly rather than
guessing: the section carries two fenced hierarchies on purpose, and pointing the parser at the
superseded one is how the guard was proven able to fail. Landed `07b498b` (M4-W126's sibling, Task
10 of the architecture plan).

- **B95** — the Pull Request level has its own address. `/findings/:findingId/workflow/pull-request`
renders the bundle in the remediation graph's own causal order, and the Solution Workflow links to
it. Landed `c808854`, `d0e316f` (M4-W126). What the review then found on that screen — a `current`
node rendered as "Running now." — is M4-W136, not a reason to keep this open.

- **B93** — observed telemetry sits under Signals, scoped by repository, and the level's header
names which roles have an integration attached. Landed `3855fd4`, `b39dcde`, `87f0d7f`, merged
`e4284ae` (M4-W127). The re-export shim that let the route move separately is deleted rather than
left behind.

- **B92** — the repository level is the Codebase level, reachable by clicking a repository row, and
`/bindings` and `/observed-telemetry` are gone. Its third clause is what took the work: picking a
different repository changes every figure below it, so `/api/overview`, `/api/detectors` and
`/api/vendors/{id}` gained an optional `repo_id`, and the vendor page moved onto
`graph_views.vendor_findings` rather than changing a signature `sync.mcp.tools` pins. Two figures
stay fleet-wide and say so on screen — vendor changes are a fact about the vendor, and
`migration_outcome` stores no `repo_id` at all. Landed `a628e77`, merged `e79fb5b` (M4-W130).

- **B91** — one component reads the observed payload, and the binding call-site table renders
`args_keys`, `response_fields_read` and `loop_depth` with a per-field ruling in its docstring.
Landed `e5235b2`, `da078bb`.

- **B99** — what the patch agent reads for itself is framed. `sync.remediate.tool_output` is a
`PostToolUse` hook applying the same three elements `untrusted.py` puts around the prompt to what
`Read`, `Grep`, `Glob` and the shell hand back, with the same refusal-on-marker discipline.

**This entry said no clean equivalent of the fence was available here, and that was wrong.** It
reasoned from the prompt layer: the bytes never pass through `build_patch_prompt`, therefore they
cannot be fenced, therefore only a sandbox and a budget are left. The premise holds and the
conclusion does not. `PostToolUseHookSpecificOutput.updatedToolOutput` is declared in the installed
SDK as "Replaces the tool output before it is sent to the model", the bundled CLI applies it before
the tool's own result mapper runs, and the hook is handed the very object it replaces. The fence
moved one layer out rather than being unavailable. The lesson worth keeping is that the entry
described a limit of the place it had been looking rather than a limit of the system, and said so
with enough confidence that nobody checked for eight days.

Three things it does not do, each in the threat model beside the rest: it does not make the agent
obey the frame, it has not been observed enforcing, and it changes what the model sees rather than
what the process did. One control was found and rejected rather than built — confining reads to
paths inside the clone, rejected because `pnpm`'s symlinked `node_modules` makes the strong form
unusable and the lexical form is walked past by a symlink committed into the repository, which is
the attacker in scope.
- **B74** — `/api/overview` counts once and carries the same envelope as every other route, at
`cdb9040`. Two defects reported from two directions: the console chat found the missing
`context_savings` by consuming the API against a live server, and the windowing contradiction turned
up while narrowing a comment during M4-P1. **The measurement that decided the design**: the window
never bounded any work. `whats_at_risk` builds a row for every open finding and only then slices, so
the ceiling bounded serialisation, which the overview discarded — counted over two thousand findings,
the old path made two thousand call-site reads and two thousand vendor-change reads, the aggregate
makes two thousand and none. Removing the window halved the reads. `context_savings` is 0 as a
measurement rather than a placeholder, because the constant is a file read avoided per binding
returned and an overview returns no binding; `binding_source` follows `whats_at_risk` over the same
loop iteration the counts come from. The console contract is additive — one new key, no rename, every
existing value identical below the old ceiling.

- **M4-P1** — the operator console's transport reads one finding by asking for it, at `e7a481c`.
It had been scanning as many as ten thousand rows out of `whats_at_risk` and walking the list in
Python, and past that ceiling it answered 404 for a finding that exists. `GraphSurface.finding_by_id`
returns the row the page carries for that finding and `None` in exactly the cases the page would not
list it; the row literal is now shared so the two cannot drift, and the reviewer established the
predicate cannot drift either. **The four published MCP tools are still four** — a surface method
becomes a tool only when somebody writes a `ToolSpec`, the golden schema blob is byte-identical, and
`dispatch` answers "unknown tool" for the new name. The proving test shrinks the ceiling rather than
building ten thousand rows, because what breaks the scan is a finding's position past the window and
not the size of the graph. **B75 closed with it** — see below.

- **B75** — the dead-links gate covers its two symbols again, at `e7a481c`. Both entries are back in
the baseline with a reason that states the correction rather than repeating the framing that was
wrong, all five transport handlers took a `_` prefix rather than only the two that collide today,
and `lint_dead_links.py`'s known-limits section carries the instance and the lesson: when a baseline
entry disappears, confirm the caller with an import rather than with a name. **What is still open is
not this** — whether those two dead functions should exist at all turns on whether the console binds
to `sync.dashboard`, which belongs to whoever owns the console. One fact for that decision is in
`.claude/COORDINATION.md`: `repository_overview` returns a per-vendor `call_site_count` the surface
route cannot produce, so a vendor with indexed call sites and no open findings is absent from
`/api/overview` entirely.

- **B73** — the last three operator-named file reads refuse rather than traceback, at `4ef5cce`. Two
took the established handler. The third, the webhook secret, deliberately did not: the question was
what the caller does with `None`, because if `None` had meant verification is skipped then swallowing
a read failure would have downgraded authentication over a file permission. It fails closed instead —
but the behaviour being replaced was not silence either. The unguarded read raised out of `main()` as
exit 1, and exit 1 in that command is the code reserved for a verdict about a delivery, so an
unreadable secret file was reporting as a forged one. **The reviewer confirmed what the silent
alternative would have cost**: with the read swallowed inside `_webhook_secret`, control falls
through to the environment variable and a delivery signed with the environment's secret verifies and
exits 0 against a credential the operator did not name. The test pins exactly that. One premise of
the brief was false and the implementer said so rather than building on it — the neighbouring
signing-key loader does not answer `None` for a key file it cannot read, only for an unparseable PEM,
and its docstring says otherwise. That docstring is part of B76.

- **B72** — `sync ingest` refuses an unreadable payload rather than tracebacking, at `eb33cd6`.
Three commands read an operator-named payload through one helper and only two of them said what
had gone wrong; the third raised, so a mistyped path or a capture truncated mid-write produced a
stack trace and no statement about whether anything had reached the graph. The handler is
duplicated across the three rather than shared, deliberately: each command's comment states what a
wrong reading would mean for that command's own numbers, and one shared message keeps the
behaviour while losing three reasons. Four tests, each watched failing first with the exact
exception it now prevents, across the file route and the piped one; one asserts no fragment of the
payload reaches stderr, because a captured OTLP export carries customer request data. **What
closing it turned up is B73**: three more unguarded reads, one of which is a secret file and needs
its own answer rather than the same handler.

- **B71** — Sentry now answers a question other than what a response body looked like. An ingest
folds an issues export into per-operation, per-window failure counts on `observed_error_window`,
which closes the half of M5 that `status_rate.py` could not: that detector reads `observed_call`
from OTLP spans, and a Sentry project is a source most teams already have. **The entry that queued
this called it an error rate and the table deliberately is not one.** An error tracker sees
failures and cannot say how many requests were made, so these counts are a numerator with no
denominator, and the schema comment, the model and the source constant each say so. The source is
named `error-tracker-group` rather than for the vendor, matching how `observed_shape.source` names
the mechanism — otherwise a later Datadog ingest of the same failures would land as a second row
for one window and anything summing rows would double-count.

Two unreviewed preservation commits, left by agents that hit session limits, went through a full
review and three fix rounds before landing. The review found one defect the tests could not have
caught: re-ingesting a window after a Sentry group was merged or deleted replaced the keys that
survived and left the vanished key's row standing, so summing that window counted those failures
twice — and the test meant to cover it dropped an issue whose key another issue also carried, so
it could only ever exercise the surviving-key path. A window ingest is now a replacement of that
window's slice for that source inside one transaction, which in turn required a refusal path: an
export nothing in which reads would otherwise delete real counts and report a quiet hour at exit 0.
The condition is that every record held was dropped as malformed rather than that nothing pooled,
because a record that reads structurally but resolves to no operation still counts as read — a
customer's Sentry project is mostly their own bugs, and refusing every hour on that basis would be
wrong.

`GraphStore.observed_error_windows` ships with no caller and is baselined in
`scripts/dead_links_baseline.txt`, deliberately: a detector written against the single fixture that
exists would be a detector tuned to that fixture. The correlation join this milestone is actually
for — a spike joined to a deploy joined to a vendor change joined to the call sites affected — is
still unqueued, and now has something to correlate against.

- **B69** — CLAUDE.md described a gap `aeecde4` had closed. Landed by the coordinator after four
failed dispatches. The stale sentence claimed `git add -u` never stages a new file, so a patch
needing one could not ship. Re-derived rather than taken from the earlier report: `_UNSHIPPED` is
`frozenset({"??", "!!"})` and a staged addition reports `A `, so `shipped_tree` never holds it
aside; and in a scratch repository `git add -u` followed by `git checkout -B` preserved a staged
new file, which the commit then carried. The gap did not vanish so much as change shape, and the
replacement says so: a created file ships only if the agent staged it, an unstaged one fails the
gate, and that staging is deliberately the only route because nothing can separate a module a fix
requires from a byproduct beside it. **The audit of the file's other claims found nothing else
stale** — all seven `ClaudeAgentOptions` fields present with no `output_config` and no
`max_tokens`, both named shas still describing what the text says, yarn genuinely absent while npm
and pnpm resolve, Postgres on 5433, and `python3` resolving to the WindowsApps shim. The HTTP 400
claim for `temperature`/`top_p`/`budget_tokens` was not checked: verifying it costs a model API
call.


- **B70** — the core wheel ships the licence it asserts, and a page worth landing on. Landed
`e249247`. `dist-info/licenses/LICENSE` is present, `METADATA` carries `License-File: LICENSE` and
`Description-Content-Type: text/markdown` with a rendering body, and the six-package install is
unchanged. **The worker declined my instruction not to check in a second copy of the licence, and
measured why:** PEP 639 forbids the parent-directory operator in a `license-files` glob and uv
rejects `../LICENSE` verbatim, so the text must sit under `src/` — which must be the core project
root for the reason B68 documented. A build-time copy is worse still: `src` is a workspace member,
so declaring `license-files` with the file absent makes `uv run` itself fail, and a fresh clone
could not run its own suite. My stated reason for the prohibition was divergence, and a byte-equality
test on every run closes it at zero build cost. Both claims mutation-tested here — diverging the copy
fails `test_the_two_licence_copies_cannot_drift_apart`, removing `license-files` fails
`test_the_built_core_wheel_carries_the_licence_and_a_description`.


- **B49** — the corpus is now a **superset** of what the rule proposes rather than equal to it. The
  four differences were classified before anything moved: one genuine addition
  (`virtual-lab-GetBalance`, filling a response slot nothing occupied) and **three substitutions** —
  and all four were added while none was replaced, so nothing measured was discarded.

  Floors all moved **up**: precision and recall **n=18 to n=27**, falsifiable negatives 5 to 6,
  pairs scored 13 to 17. Symbol map digest unmoved. Byte-identical across two clean databases.

  The rates held at 1.0000 over half again as many labelled positives, which is the part worth more
  than the count — a perfect rate at n=18 and a perfect rate at n=27 are different amounts of
  evidence for the same claim.

- **B48** — operation selection now follows the change's own side. An operation qualifies on
  `args_keys` for a request pair and `response_fields_read` for a response one, through a shared
  `_judged_by` that `hold_back` also calls.

  The diagnosis in one line: **selection was the only clause that never followed the side**, which
  is why response coverage had been a side effect of request coverage.

  The closing condition was met exactly — the rule proposes `GetProductsId` for `virtual-lab`, and
  the specification it writes is *identical in parsed payload* to the pair that had to be
  hand-written: same field `created`, same held-back position. Ten tests cover the symmetry in both
  directions, including that an object argument does **not** qualify an operation for a response
  pair, so it did not swap one blindness for another.

  No floor moved and `benchmark/corpus/` is byte-untouched, which was the constraint: the four
  differences it would propose for the TypeScript repositories were measured into a scratch
  directory and left there. See B49.

- **B47 — the corpus measures Python.** `virtual-lab-GetProductsId-response-property-removed`:
  two labelled positives, both found, no false finding, and one held-back site the detector could
  have fired on and did not.

  **Every floor moved up**, which is the only direction that needs no argument: precision and
  recall n=16 to **n=18**, falsifiable negatives 4 to **5**, pairs scored 12 to **13**, symbol map
  digest unmoved. Byte-identical across two clean databases.

  The question it was sent to answer was whether an honest pair could exist at all. Of 21 call
  sites, **five** bind a result directly — the other sixteen bind through
  `list(...auto_paging_iter())`, a comprehension, a `for` header, or nothing, and are correctly
  unreachable. Three of the five sit on one operation, which is what makes it a *pair* rather than
  merely a reachable site: two targets and one held back, so it contributes a falsifiable negative
  rather than only denominators.

  It also had to restate the gate's own tests, which asserted the old floors — the same lesson as
  the symbol-map re-pin: when a floor moves, everything that records it moves with it. See B48 for
  why the pair had to be written by hand.

- **B44** — a Python repository is pinned and **none of the pairs it would have produced were
  written**. `openbraininstitute/virtual-lab-api`, Apache-2.0, 563 files, digest validating. Twelve
  pair specs unchanged, all four floors clear, symbol map digest unmoved.

  It set out to give Python its first measurement and instead caught the corpus about to certify a
  number about itself. Its rule produced two pairs; both mutated
  `customers = list(client.customers.list().auto_paging_iter())` into an assertion on
  `customers.has_more`, which is an `AttributeError` on a list. Removing `has_more` from that
  response cannot break that code, so the binder was right to record nothing and right to emit
  nothing.

  **It refused to land them rather than lower `RECALL_FLOOR` from 1.0000 to 0.8889 to accommodate
  ground truth it had proved wrong** — the act the gate exists to prevent. Python precision and
  recall stay `null` over `n=0`: unmeasured, not zero. See B47.

- **B46** — the generator now requires the value to **be** the call rather than merely contain it,
  matching both binders. `customers = list(client.customers.list().auto_paging_iter())` no longer
  gets a response guard attached to a name that never held the response.

  **It fixed both languages, and said so up front rather than letting it be discovered.** The brief
  asked whether TypeScript had the same asymmetry; it did, in the same function — the walk climbed
  to the statement and took whatever declarator it held without asking what that declarator's value
  was, so `const customers = Array.from(client.customers.list(...))` carried the identical defect.
  Its argument for one commit: *two grammars, one rule, one mistake — separating them would have
  described the code's layout rather than the change.*

  **The twelve TypeScript pairs survive the stricter rule unchanged.** All four floors clear:
  precision 1.0000 n=16, recall 1.0000 n=16, falsifiable negatives 4, pairs scored 12. So the
  corpus was not carrying mislabelled TypeScript pairs — the defect existed and had not yet been
  exercised there.

  One line from its reasoning worth keeping: a generator that consulted the binder would be scoring
  the binder against its own opinion. The two must agree by construction and not by consultation.

- **B43** — the pair generator can build a Python pair, and the router still cannot codemod one.
  Landed with the corpus untouched: all four floors clear, symbol map digest matching.

  The design question was the task, and it was separated the right way. `language_for` stays in
  `sync.route.templates` answering the router's question — *can a codemod patch this file?* — and
  still returns `None` for `.py`. The generator got its own `_language_for` answering a different
  question — *can I parse and edit this to build a labelled pair?* — which returns `python`. One
  function answering both with one answer was the bug.

  **Both router guards are tested**, which was the closing condition:
  `test_the_router_still_reads_python_as_a_language_it_cannot_codemod` and
  `test_the_codemod_declines_a_python_call_site_by_name`. That regression would have been
  completely silent — a Python finding routed to a tier whose codemod matches nothing, abandoning
  as "the remediator produced no change".

  It also covered hazards it was warned about and one it was not: the response guard occupies no
  new line, so the displaced-label interaction cannot fire; a result nobody binds is `unreachable`
  rather than labelled; a call already passing the field is refused; and the mutated Python still
  parses.

  **Then it found a corrupting defect in its own landed work.** The keyword insertion mirrored the
  TypeScript literal insertion and placed the field first, which is `SyntaxError: positional
  argument follows keyword argument` in Python — and `create(customer_id)` is an ordinary shape the
  corpus candidate writes.

  Worse than a failed mutation, because it would not have failed: **tree-sitter recovers from a
  syntax error and returns a tree**, so the dependency would have been read back out of a file that
  is not Python and the pair labelled affected. A corrupt pair rather than a refused one — the one
  unrecoverable mistake this generator has, since ground truth is what every future score is
  measured against.

  Fixed by writing the break last, and the tests now `ast.parse` the mutated source rather than
  comparing strings, which is the only check that could have caught it. This is the same trap the
  design document already records from the other side: a codemod cannot verify its own work by
  re-parsing, because the parser will not tell you it is wrong.

- **B45** — an unreadable `requirements.txt` now answers "declares nothing" rather than taking the
  run down at adapter selection. Landed with the front-page work. The `pyproject.toml` branch had
  always honoured that promise; the `requirements.txt` branch two lines below read with a bare
  `utf-8` decode.

  Verified across four encodings, two of them outside the brief: UTF-16 `requirements.txt` returns
  `[]` where it used to raise, UTF-8 is unchanged, UTF-16 `pyproject.toml` still works, and a
  latin-1 manifest is also handled — so the fix generalises rather than special-casing the byte
  order mark that found it.

  Worth knowing about the trade: a manifest with one non-UTF-8 byte anywhere now declares
  *nothing*, so a repository with an accented comment loses adapter selection entirely. That is the
  contract the docstring states and the safe direction — a missing binding is recoverable, a wrong
  one spends reviewer trust — but it is a real cost and not a free fix.

- **B42** — the Python blocker moved from the binder to the generator. B38 and B39 are visible in
  the counts: one repository went from zero to five call sites through the `self`-attribute
  receiver, another gained two through the Python spellings the map had lacked.

  **It repeated the search rather than only the measurement**, and the reason is the sharpest thing
  in the report: B37 assembled its seventeen candidates by searching for the shape the *old* binder
  could index, so re-measuring only those would have asked the new binder a question shaped by the
  old one's limits. That found a repository none of the seventeen matched.

  It did not pin it, because `mutate.language_for` returns `None` for `.py` — and it did not fix
  that either, because teaching the generator Python and pinning the repository it unblocks in one
  change is one worker moving both the corpus and the thing measured. That constraint has held all
  day and it applied it without being told. See B43 and B44.

- **B40** — the once-in-eight failure has a name:
  `test_a_database_that_cannot_be_dropped_does_not_fail_the_run`, caught on run 5 of 14 and failing
  in its own setup with `database "sync_test_22000_gw2" does not exist`.

  **A race between two pytest runs, not between two tests.** The sweep is server-wide and drops
  every `sync_test_%` database whose embedded pid is dead; three tests deliberately create databases
  named for a dead pid, because that is the only thing the sweep will consent to drop. That is the
  bait every *other* run's `pytest_configure` eats. Reproduced deterministically — a second run's
  `--collect-only` is enough, because the sweep happens before any test executes.

  Alternatives falsified with evidence rather than dismissed: not connections (the server answers
  "does not exist" *after* a successful connect, where a limit says "too many clients already", and
  the peak-54-of-300 measurement stands), not order dependence inside a run (the sweep runs once in
  the controller before any test), not product code (everything involved is under `tests/`). Load
  widens the window — the red run took 354.96s against 108–122s for the four green ones.

  **Two workers converged on the identical fix independently**: name the bait for a live pid and
  inject a probe that calls it dead, so the `DROP` and the in-use refusal stay real while the
  database is invisible to other runs. The other coordinator's landed first as `bf3356a`, so only
  this one's capture harness and report were taken.

- **B41** — the corpus's second frozen input is pinned. `benchmark/corpus/symbol_map.yaml` records
  a digest beside `repositories.yaml`, the score carries the digest of the map that actually ran,
  and both the scorer and the gate refuse a mismatch. A deleted map now exits 2 naming the pin
  instead of a `FileNotFoundError` from inside the Stripe adapter.

  **The digest covers content, not bytes**, and that distinction was proven both ways rather than
  argued: reserialised with reversed key order and seven-space indent it digests identically; one
  symbol repointed is refused naming both digests. A checkout is its bytes because the indexer
  reads the files it was handed; a map is a mapping, and indentation is how a serialiser felt on
  the day.

  The scorer refuses **before scoring a single pair**, because that is where a wrong number would
  be created and it is indistinguishable from a good one by the time anything reads it.

  Re-pinned by the coordinator in the same act: the worker's pin named a 179-symbol artifact that
  predated B39 and no run could stage, so it refused on every current cache — correctly and
  uselessly. Rebuilt to 272, scored, floors measured unmoved, digest and recording landed together.
  Its own test `test_the_gate_clears_the_score_the_scorer_actually_records` caught the incomplete
  half of that re-pin, which is exactly what its docstring says it is for.

- **B39** — the Stripe symbol map now carries the spelling Python actually writes. 179 symbols to
  **272**, all 93 previously-unreachable operations addressable, `paymentIntents` and
  `payment_intents` both resolving, and every TypeScript resolution unchanged — corpus floors all
  cleared.

  **The spelling was never missing; it was being discarded.** `payment_intents` is the
  specification's own path segment from `/v1/payment_intents`, and `_camel` was converting it and
  throwing the original away. So snake_case is the source and camelCase the derivation — nothing
  was inverted and nothing transformed, which is exactly what the brief forbade.

  Checked against the vendor before code was written: `StripeClient.payment_intents` is declared in
  `stripe/_v1_services.py`, a file whose header reads "File generated from our OpenAPI spec", and 31
  of 34 multi-word segments match letter for letter.

- **B38** — Python binds the client shapes people actually write. `stripe.StripeClient(k)` and
  `self.client...` both resolve now; the bare imported name is unchanged. Landed `4656d92`.

  The guards are the valuable half, and each is **asserted not to bind** rather than left to
  discovery — `notstripe.StripeClient(k)` (the object is checked, never the attribute),
  `config.client = stripe.StripeClient(k)` (only `self`), and a client received as a parameter and
  stored on the instance (nothing statically says a parameter is a Stripe client, and binding it
  would count any attribute assigned from any parameter). All four verified independently here.

  A rule loose enough to match any `x.Something(...)` would have reintroduced false attribution at
  the binding step — the same defect this file was fixed for earlier today, one layer earlier. It
  did not.

- **B37** — no Python repository was pinned, and the negative result is worth more than the pin
  would have been. Seventeen candidates cloned and indexed against the real adapter and the real
  symbol map; the corpus is unchanged, no floor was restated, and the gate is green for the same
  reason it was this morning. What it found is B38 and B39.

  The sharpest line in its report is about today's own work: both Python fixes landed today concern
  what happens *after* a call site is bound, and every limitation it measured concerns whether one
  is bound at all. **A Python corpus existing today would not have exercised either fix** — sixteen
  of the seventeen repositories bind nothing, and the seventeenth binds one call of neither shape.

- **B36** — the first quality gate this project has. `scripts/gate_corpus.py` floors binding
  precision and recall at the recorded 1.0000 over n=16, and it **recomputes both rates from
  `true_positives` and `false_positives` rather than reading the stored value**, so a stale or
  edited number cannot satisfy it.

  It floored two things beyond the brief, both guarding the gate rather than the binder.
  `falsifiable_negatives` at 4: if that count silently returns to zero, precision's false-positive
  term has no candidates again and the precision floor stays green while gating nothing.
  `pairs_scored` at 12: an exclusion regression shrinks both denominators while leaving both rates
  at 1.0000, so the gate would pass over a corpus that had quietly stopped covering a third of
  itself.

  Verified by seeded regression rather than by report — precision to 0.8889, recall to 0.8889,
  negatives to 0, pairs to 8, each exits 1 naming the floor it broke; the clean tree exits 0; a
  missing score file exits 2 rather than passing.

  Recall was floored on an argued judgement, not by default: it moved twice on the day the corpus
  was frozen, both times through deliberate corpus authoring, and a frozen corpus is authored rarely
  and on purpose. Leaving it open would have gated the less important half, since a missed break is
  the failure the product exists to prevent.

- **B30** — a checkout's undecodable files are skipped and **named**, rather than one PNG ending
  the run. The fetcher's own pre-filter is gone, so the corpus scores the vendor's subtree instead
  of a locally transformed copy of it, and both components walk the tree through one shared
  function (`src/sync/benchmark/checkout.py`) so the digest cannot come to cover a set of files the
  score was not taken over.

  **The axes are unchanged, measured rather than argued.** With the tree pre-filtered (0 skipped)
  and with it verbatim (64 skipped): precision 1.0000 n=16, recall 1.0000 n=16, falsifiable
  negatives 4, 12 of 12 pairs — identical. That is the same-criterion prediction confirmed.

  Two `tree_digest` values moved and no pinned commit did. The manifest now records that the
  digest's *coverage* changed on a date and the commits did not, so a future mismatch is not
  misread as a vendor moving a commit.

  All 64 skipped paths are images, fonts or an icon — no legacy-encoded source file among them.
  That is a property of these four repositories rather than a guarantee, which is why they are
  **named and not counted**.

- **B35** — a walrus-bound result is now credited to the call that produced it. Landed with B34's
  work. Verified across `if` and `while`, with the wrapped form (`charge := dict(create(...))`)
  still recording nothing, so B34's fix is not reopened.

  **The brief was wrong and two workers caught it independently.** It said to add
  `named_expression` to the transparent-wrapper set. A wrapper is something a result passes
  *through* on its way to a name further up the tree; the walrus is where the name already is. As a
  wrapper the walk steps over it and climbs to whatever assignment encloses the `if` — a false
  attribution, which is exactly the defect B34 had just removed. B34's worker predicted this from
  the grammar; B35's worker measured it as a silent no-op before writing anything, with all four
  recall tests staying red.

  Also caught: B34's "recording more would be wrong" reasoning is disqualifying for a precision
  task and is the *point* of a recall one. A worker carrying that sentence across unexamined would
  have done nothing at all.

- **B34** — the Python binder no longer credits a call with fields read off whatever wrapped it.
  Landed `a11c3be`, with its report. Two false attributions removed, six correct cases
  byte-identical, and **nothing anywhere records more than it did** — the check that mattered on a
  precision task.

  The wrapper set is `await` and `parenthesized_expression`, and it was derived from
  `tree_sitter_python`'s grammar rather than translated from TypeScript's, because the worker that
  found the defect had verified behaviour and said explicitly it had not verified node names. Every
  rejected form carries its own reason: `boolean_operator` and `conditional_expression` choose
  between two values and only one is the call's; collection literals bind a container; `argument_list`
  *is* the defect. Annotated assignment needed nothing — it is the same node with the annotation as
  a field. See B35 for the one form it declined to add.

- **B33** — the binder now sees fields read off a result the code assigns rather than declares.
  Landed in `67db957`. Recall **0.8000 to 1.0000 at the unchanged n=20**, every response-side miss
  found, and precision held at 1.0000 while its sample grew 16 to 20 — the check that mattered,
  since recall bought by claiming unread fields would have been worse than the defect.

  It also found and fixed an **unbriefed precision bug** its own test caught:
  `const c = wrap(await stripe.charges.create(...))` was crediting `wrap`'s return value to the
  Stripe call. Widening the binding forms without that guard would have doubled false attribution
  rather than fixed anything. And it refused to write under `benchmark/corpus/recorded/` on the
  grounds that recording into the instrument's directory is editing the instrument — a stricter
  reading than the constraint it was given, and the right one.

- **B32** — a pair specification can hold a call site out of the mutation, so precision has
  something it could fail on. Landed in `67db957`. **Falsifiable negatives 0 to 4, and the binder
  declined all four**, which is the first evidence that axis has ever carried. Its own recording
  was taken against a corpus B29 had already replaced; the coordinator rebased and re-measured.

- **B29** — the response half of the corpus now measures something, and it immediately caught a
  production defect. Landed `4a00841`. Two causes, not the one diagnosed: `_result_binding` reading
  only `const`/`let` accounted for 4 of 11 unreachable targets, and the larger cause was the guard
  occupying three lines, which displaced every call below it. Appending the guard to the statement
  it follows removed the interaction rather than trading one failure for another — **zero**
  `displaced-label` exclusions afterwards, where the naive fix would have created more.

  12 pairs scored, none excluded. Precision 1.0000 n=16, **recall 0.8000 n=20** — down from 1.0000
  n=12, and not a regression: all twelve request-side positives are still found and all four misses
  are response-side. See B33.

  The worker declined to fix the defect it found, because the corpus is what measures the fix and
  it was changing the corpus. That judgement is the most valuable thing in the task.

- **B28** — the decision-table row a run routed on now reaches `migration_outcome`. Landed
  `47cca19`, written by the coordinator after its worker went silent with no edits across two
  ticks. The seam is the recorder, not `on_route`, which still has no caller: `_record` already
  receives the state the row lives on. Required rather than defaulted, and the mutation showed
  why — with a default, removing the writer left the jurisdiction test still passing because the
  default equalled what it asserted; required, the same mutation fails it.
- **B31** — diagnosed why binding precision cannot fail and built `falsifiable_negatives` to say
  so in the output. Landed `67ab335`. It corrected the coordinator's evidence: the rung on an
  unaffected label is a literal `mutate.py:190` writes, and `binding.py:223` never reads it, so
  counting it proved nothing. Real cause is `cli.py:1473`. Follow-up is **B32**.

- **B31** — diagnosed and closed; `falsifiable_negatives` reads 0 for all ten pairs and the
  cause is `cli.py:1473`. The follow-up is **B32**, deliberately a different number.
- **B27** — a specimen corpus is frozen and scored: 12 pairs across 4 repositories pinned by commit
  SHA, checkouts materialised into gitignored space, exclusions counted by reason. Landed
  `c6e18a0` after its worker died holding 1091 lines uncommitted; preserved as `4631c01` on the
  worker branch first, then verified and landed.

  **Determinism is measured, not assumed** — two runs byte-identical, which is what the only
  safely-addable tier C gate rested on and nobody had ever tested.

  Two caveats that must travel with the number. Both axes are computed over the **request side
  only**: every `response-property-removed` pair scored 0 affected and 0 findings, with 11 labels
  unreachable. And **precision 1.0 is a constant, not a measurement** — `cli.py:1473` targets
  every same-operation site, so no negative the detector could have fired on exists. Recall 1.0 at
  n=12 is real. See B31.

- **B26** — the conformance kit no longer certifies what it never exercised. `check_vendor_adapter`
  refused nothing when `known_symbol` was `None` or resolved to `None`; `check_remediator` read an
  empty diff as a decline, so a remediator claiming everything and writing nothing passed. Landed
  `f297e47`. The two refusals carry distinct messages, because "you gave me no symbol" and "your
  adapter did not resolve it" are different problems and an author who conflates them edits the
  wrong thing.

  The new rule fails four generated vendors, and the exemption's wording was the hard part. They
  are **not** unable to resolve: `_load_generated` (`registry.py:362`) passes `sources={}` because
  it promises to reach no network, while `_prepare_generated` (`registry.py:319`) passes
  `sources=sources` and is the path a real run takes. The kit is handed the offline one. Its
  staleness test fails in **both** directions — verified by mutation, dropping a vendor and adding
  one that resolves.

  The limit worth remembering: **this suite certifies an adapter shape no customer ever meets.**
  That closes with a staged fixture, not a bug fix.

- **B24** — nineteen shipped implementations are now asserted against the conformance kit, with
  every list derived from the registry rather than restated and a registered implementation that
  has no case failing **by name** rather than being skipped. Landed `52303b6`. No shipped
  implementation failed, and the worker did the more valuable thing: it asked why everything
  passed, and found **two checks that pass without exercising anything** — `check_vendor_adapter`
  certifies an adapter resolving no symbol when `known_symbol` is `None`, and `check_remediator`
  reads an empty diff as a decline. Both confirmed independently. B26 moves those fixes into the
  kit, where outside authors will actually meet them.

- **The flaky database failures were never flaky.** Measured with a sampler through one full
  suite: peak **105** concurrent connections, mean 67.6, against the postgres default ceiling of
  **100** — `-n auto` gives one xdist worker per core and several worktrees run suites at once.
  Over the ceiling the failure is a `psycopg.OperationalError` on connect, landing on whichever
  database-touching test was running, which is why it moved between runs and never reproduced
  under a soak. Both coordinators lost time to it. `fba1f6e` raises the ceiling to 300 and takes
  effect on the next `docker compose up -d`. **The container was recreated and the ceiling is now
  live at 300**, confirmed against the running server.

  Re-measured after the recreate, same machine, same suite:

  | | before | after |
  |---|---|---|
  | result | 1 failed, 13 errors | **1851 passed** |
  | wall clock | 187s | **103s** |
  | peak connections | 105 of 100 | 75 of 300 |
  | sampler connections refused | 16 of 322 | 0 |

  The halved runtime was not expected and is the part worth remembering: exhausting the ceiling
  was costing refused connections and retries throughout the run, not only the visible failures.
  A resource limit read as both a flaky test *and* a slow suite, and neither symptom pointed at it.

  Peak 75 against 300 leaves real headroom, but that was one suite alone. Nobody has yet measured
  the peak with two or three concurrent suites, which is the case that broke the old ceiling.

- **B23** — the conformance kit covers all five protocols. `check_request_correlator` guards a
  privacy boundary rather than a correctness one: an observed path carries a live customer
  identifier and what comes back must address the operation with the vendor's published template.
  Verified by isolating the rule — a correlator returning the raw path is rejected, one returning
  `/v1/charges/{charge}` is accepted. Landed `ec080ee`. Two corrections from that worker, both
  right: the `cli.py` guards are at 1032 and 1102, and they should NOT call the kit, because the
  check needs a resolving request and its identifier that the ingest entry point cannot know.
- **B22** — the shipped `generated-vendors.yaml` is now gated. Its stale-exemption test fired
  against a real event within the hour: `symbols_speakeasy.py` landed, the one pending entry
  stopped describing anything, and the test named both the pair and the remedy. `PENDING_EXTRACTORS`
  is now empty. Landed `e5ee571`.

- **B21** — an existing database now gains columns added after it was created. `apply_schema`
  derives each table's columns from `schema.sql` and issues `ADD COLUMN IF NOT EXISTS` for
  whatever is missing, rather than executing a create-only script. The ALTERs are derived rather
  than hand-maintained, because a hand-kept list reintroduces the original bug the first time
  someone adds a column and forgets the migration. Landed `8a5cd89`, on main at `245382f`.
  Mutation-tested two ways before landing: reverting `apply_schema` to its create-only form fails
  2 of the 6 new tests, and the small SQL parser's documented limit is real — a semicolon inside a
  string literal fails 5 tests loudly rather than mis-parsing in silence.

- The conformance kit now covers four of five protocols, with 29 rules each proved to fire.
  Landed via `fc7090f`. It found the finding-collision defect below.
- `Finding.claim` joins the natural key, so three detectors stop overwriting themselves.
  Landed `c88f240`. Reproducing first revealed a second, unnamed axis in efficiency that a
  key-only fix would have turned from silent loss into a flood of rows.
- The indexer takes the SDK package from the vendor adapter rather than a module constant,
  delivered by the other coordinator's workers; `symbol_root` followed after a scoped-package
  defect that no fixture could see.

- An MCP vendor adapter, M3's last unstarted item. Landed via `28b0772`.
- The status-rate detector, M2's missing half. Landed via `28b0772`. It reports a *level* rather
  than a change, because `cli.py` truncates `observed_call` every run so "earlier" means earlier
  within one ingested window — and said so rather than quoting a trend it does not have.
- A language axis on the binding path. Landed `19834b6`.
- Efficiency findings state that a cost is shared across call sites rather than counted once
  each. Landed `0f980da`.
- The plugin SDK conformance kit and authoring guide. Landed `bb425ba`. Running it against the
  real adapters disproved one of its own rules within a minute.
- The orchestration archive: 147 worker reports, escalations and decisions, exported before the
  terminals were cleaned up. Landed `aef675a`.

- A language axis on the binding path. Landed `19834b6`. Every Twilio map key is snake_case
  (`twilio-python`), so a TypeScript call site could never resolve and failed silently. A
  mismatched spelling now refuses rather than being rewritten into a match. Written by the
  coordinator after the dispatched worker never started.

- The efficiency detector, M1's second half. Landed via `cb0ee3e`. Three findings — calls in a
  loop, uncached repeats, retry storms — and deliberately **no dollar figure**: a call count is
  a fact, a cost needs a price per call no table here holds.
- Loop context on `call_site`. Landed `e8076be`. A depth rather than a flag, counting array
  callbacks alongside loop statements. Written by the coordinator after two dispatched attempts
  had their work destroyed in shared worktrees.

- The M1 span store: `observed_call`, OTLP ingest, and correlation behind a `RequestCorrelator`
  protocol. Landed `ecab0bd`. Grain is one row per trace — per unit of work — which is what lets
  a loop be told apart from ordinary traffic, and what makes ingest idempotent with no counter.
- A second vendor adapter (Twilio), the first real second implementation of
  `operation_for_symbol`. Landed `14394e4`. It inverted the assumption the symbol map was built
  around; the design document now records it.

- Run the suite in parallel, one database per worker. Landed `b590a5e`. Measured **2.18x** on
  an idle 12-core machine, not the 3.0x first reported — that baseline was taken while other
  workers were running. The load-bearing find was `conftest` returning early on a set
  `SYNC_DSN`, which put all twelve workers on one database and deadlocked them on `TRUNCATE`.
- Discard a dependency tree the previous finding doctored. Landed `0fd1623`. Written by the
  coordinator after three dispatches to a worker failed to start.

- Let a patch ship a file it had to create. Landed `aeecde4`, with the install-mark fix at
  `12f9dc9`. Staging is the agent's assertion that the patch needs the file; untracked
  debris stays excluded because neither `git add -u` nor `git diff HEAD` reads it.
- Catch a patch that edited an installed dependency instead of the source. Landed `a891f65`.
  The cheap path guard's reasoning held but its mechanism did not — git cannot answer the
  question either way — so it compares filesystem mtimes instead. Residual recorded as B6.
- Refuse a push that would discard any non-Sync commit, not merely one at the tip. Landed
  `7adeb08`. The worker found a case the brief missed: a stranger's commit the push carries
  forward is not at risk, so refusing it would abandon findings needlessly.

- Register `sync.core` types with LangGraph's checkpoint serialiser. Landed `05c11f5`.
  The warning is read-side only and nothing fell back to pickle — the brief was wrong about
  that and the worker corrected it. Future failure returns a raw dict silently.

- Derive the SDK verb from `spec3.sdk.json`'s `x-stableId` rather than the URL shape.
  Landed `b289a9e`. Coverage unmoved at 105 of 414; one symbol corrected.
- Refuse a push lease against a tip Sync did not author; delete the branch an abandoned
  finding leaves behind. Landed `38ec2c7` and wired at `9627f65`.
- Run the tier cascade and give it the change class the acceptance run hit.

- Take the `hold_back` `turbo` earns and refuse the one `furever` earns. Landed `10f925b`. The
  worker stopped at the decision gate rather than adopting both, which is what caught it: adopting
  both put precision at 0.9615 over n=26, and the single false positive was the newly held-back
  site itself. The label was false, not the binder — two assignments to one name in one scope, so
  the guard's field read is credited to both and the held-back site genuinely depends on the
  removed property. Both rates hold at 1.0000 over n=26, falsifiable negatives 6 to 7, pairs
  unchanged at 17, so the only floor that moved moved upward. Verified by scoring the corpus from a
  fresh database independently, and all four floors were mutation-probed: injecting one false
  positive, one negative short, two false negatives and one dropped pair each fired, naming its own
  axis, with the unmutated control clean. The unsound-selection half is B52.

- Tell whether a decode handler has ever been entered. Landed `e804fe6`. Reads the handler inventory
  out of `src/` by AST and attributes entry by *exception type* using `sys.monitoring`'s
  `EXCEPTION_HANDLED`, so a handler reached by `JSONDecodeError` and the same handler reached by
  `UnicodeDecodeError` are told apart on one line — the distinction line coverage cannot make, which
  is the whole reason the defect class stayed invisible. Measuring the pre-existing suite this way
  found **9 of 14 decode handlers in `src/` had never been entered**; all 14 behave correctly on
  undecodable bytes, so the defect was only that nobody could tell. Nothing in `src/` changed and no
  lint or coverage configuration was weakened. Verified by dropping the driver for a *co-caught*
  handler — the arm a line-coverage check would still call covered — and watching the gate name
  `sync/signals/intake.py:275` exactly; a bogus driver naming a handler not in `src/` also fired.
  Two leave-behinds became B53; the 35 unhandled text decodes still need per-site triage.

- Decline a non-UTF-8 `package.json` instead of crashing on it. Landed `bdabe9c`, with the driver
  it omitted at `83825f6`. The worker measured two crash shapes rather than one — a UTF-16 manifest
  and a cp1252 `author` field failing on byte `0xe9`, the legacy-encoding case CLAUDE.md predicts —
  and both decline after. It also found B52's red suite and proved the five failures predate its own
  change by stashing its files at clean `34789db`, which is why that commit did not land with it.

  **What it missed is the more useful record.** Its change widened a guard to catch
  `UnicodeDecodeError`, which adds a row to `test_decode_handlers.py`'s AST inventory, and it did not
  register a driver — so `test_every_decode_handler_has_been_entered` failed naming
  `sync/index/typescript.py:201`, one hour after that gate landed. The worker correctly attributed
  the five failures it found to another commit and did not notice a sixth was its own. Proving the
  five were not its fault is not the same as proving nothing was. The driver was written here and
  probed by reverting the fix: the driver's own test then raises `UnicodeDecodeError` at
  `typescript.py:200`, so it genuinely enters the arm rather than passing beside it.

  Left behind and now B54: a BOM'd manifest, which decodes fine and defeats four readers instead.

- Refuse a hold-back whose site shares a scope and a result name with a target. Landed `9812313`,
  with the five callers `hold_back`'s new required `root` broke fixed at `0dfd09f`. A fresh
  generation now leaves `furever-PostPaymentIntents-response` without the unsound hold_back, which
  was the deliverable, and the four figures are unchanged: precision 1.0000 n=26, recall 1.0000
  n=26, falsifiable negatives 7, pairs scored 17, `Every floor cleared.`

  Probed in both directions, because a clause that refuses everything is as wrong as one that
  refuses nothing. Disabling the refusal fails `test_a_site_sharing_a_scope_and_a_name_with_a_target_is_refused`;
  dropping the path out of the scope identity — so two files holding the same text compare equal —
  fails `test_sites_in_different_files_are_still_held_back`, which is the case the docstring argues
  for. Regenerating the whole set changes one other file, and only its hand-written commentary:
  zero non-comment lines, `hold_back` key intact.

  **The worker did not land this itself.** It went silent for 53 minutes across two messages, and
  something reset its tree onto a stale main and orphaned `34789db` — 300 insertions reachable from
  no branch. Caught within a minute and preserved as `unreviewed/b52-hold-back-scope`, then
  finished here. Two habits earned from that: stage by explicit path, and run
  `git log --oneline main..HEAD` before any `git reset --hard`.

- Read a customer's manifest as `utf-8-sig`, so a byte-order mark stops changing the answer. Landed
  `9352dbe`. **Seven sites, not the four the brief named** — the brief counted `sync/index/` and the
  worker found `sync/signals/intake.py` reads the same three files for the intake report, correctly
  widened the scope, and said why. The worst instance is the one it added: intake *reported* a
  dependency called `﻿stripe` with an empty `unreadable` beside it, answering a wrong fact
  rather than an absence.

  The claim worth checking was that `utf-8-sig` narrows rather than decodes leniently, since a
  lenient decode would have made every unreadable manifest "readable" and turned the whole family of
  defects into silent mojibake. Verified here: BOM'd manifests now resolve to `stripe`, and UTF-16
  still refuses with `unreadable` set, on both `package.json` and `requirements.txt`.

  Landing it conflicted in three files, all of them "keep both halves" rather than a real
  disagreement: the worker's base predated B53's widened `except`, so `typescript.py` wanted its
  `utf-8-sig` read *and* main's `UnicodeDecodeError` clause. Its report said B53's fix was missing
  from `origin/main`; that was its stale base showing, not origin — `bdabe9c` is in origin's
  ancestry and the clause is there at line 201.

- Let the tokenizer decide a source file's encoding. Landed `b3fe71b`. **The worker refused the fix
  the brief prescribed and was right to.** The brief said `utf-8-sig`; it passed the file's *bytes*
  to `ast.parse` instead, on the argument the method's own docstring already made — deciding a
  file's encoding is part of parsing Python, so choosing one at the read bypasses the very authority
  the gate defers to. `utf-8-sig` fixes a byte-order mark and still fails a file that declares
  `latin-1` under PEP 263; bytes fixes both. Measured against `py_compile` over seven files: bytes
  agrees on all seven, the old `utf-8` read disagreed on two.

  Verified here across six shapes — valid, BOM'd, declared latin-1, undeclared non-UTF-8, UTF-16,
  and a real syntax error — with the gate and `py_compile` agreeing on every one, and the gate still
  rejecting two, so it discriminates rather than passing everything. Reverting the read to `utf-8`
  fails three tests including the property test that compares the two file by file.

  It also removed a clause and its driver rather than re-anchoring them: once the source is bytes,
  `UnicodeDecodeError` is unreachable because it is a `ValueError` subclass and a UTF-16 file raises
  `ValueError: source code string cannot contain null bytes` before the tokenizer. Deleting a driver
  is the right move when the handler is genuinely gone; the assertion moved to
  `tests/test_python_index.py` rather than disappearing.

- Skip and name a `.ts` file that does not decode. Landed `2b2c29b`. The read used
  `errors="replace"` and fed the result to the literal indexer, where `operation_id` *is* the
  literal's value. **The phantom is the finding**: `.ts` is MPEG transport stream as well as
  TypeScript, so under leniency a binary file parsed into a call site. Reproduced here — a binary
  `.ts` carrying an embedded literal yielded `vendor=anthropic operation_id='claude-3-opus'
  path=video.ts`, and zero after the fix. My first probe found no phantom because random bytes
  happen to contain no vendor prefix; the anecdote needed a matching literal to show, which is
  worth remembering before dismissing one.

  The worker priced its own change rather than hiding it: a valid `.ts` in a legacy encoding holds
  literals leniency recovered and this no longer indexes, and telling that file from a binary
  cheaply is impossible. `read_checkout` had already argued the same and chosen the same way.

- Adapter selection stops blaming the repository for a binding we never declared. Landed `7290bc6`.
  The load-bearing finding was that the old message was **false**, not merely vague: four of six
  registered vendors are served by `GeneratedSpecAdapter` and declare no `sdk_bindings`, so a
  repository genuinely importing `@anthropic-ai/sdk` was told its own manifest was at fault.
  Verified both branches here — an undecodable manifest now says so and names the byte, a clean
  manifest says `declares 1 dependency and 'stripe' is not one of them`.

  It reached main the hard way. The worker wrote into the *other coordinator's* worktree and
  committed onto their branch, 86 commits behind main, re-fixing a defect B53 had already landed.
  Preserved as `unreviewed/b55-decline-reason`, then cherry-picked with five conflict hunks —
  every one resolved as "keep both halves", its reason-reporting over main's newer encodings — and
  five `DRIVERS` keys re-anchored from what the gate reported.

- Let Stripe's symbol map skip a malformed path item, as Twilio's already does. Landed `4c13681`.
  Stripe reached `.get` on whatever `paths` held, so one malformed entry cost the **entire** map —
  every call site for the vendor unresolved for one bad key — while Twilio skipped the path and
  built the rest. Verified across four shapes (null, list, string, number): the two now agree on
  all four, a well-formed document still yields its entries, and a mixed document keeps its good
  one. The pinned symbol-map digest is unchanged at `5f71dcd3bec1302c` and the corpus gate clears,
  which was the constraint that could have made this a much larger change.

  **The verdict was already in the repository.** `tests/test_symbol_map_declines.py` had recorded
  this exact drift and said the raise was the worse answer, because a path key names which document
  is bad and a type name does not. The worker inverted that test from asserting disagreement to
  asserting agreement, keeping it as a comparison because agreement is the property and the two
  halves can only drift again by one changing alone.

- The indexer read the customer's code more loosely than the vendor's. Landed `49a4a09`. Four copies
  of one node reader existed: the two over a vendor's SDK decoded strictly, the two over the
  customer's repository passed `errors="replace"`. **The measurement is the finding** — leniency
  recorded `response_fields_read` of `['st']` for a field spelled with an a-circumflex, truncated at
  the bad byte rather than marked, so the graph carried a dependency on a field that does not exist,
  which `ObservedDriftDetector` reads and `PropertyOmitRemediator` patches against.

  Landing it needed three corrections. It committed onto the other coordinator's branch 96 commits
  behind main (preserved as `unreviewed/b58-strict-node-decode`); it duplicated B57's `cli.py` fix,
  so main's landed version was kept with B58's two measured consequences grafted into the docstring;
  and it added two decode handlers without drivers, which the gate caught. Writing those drivers,
  the control caught the coordinator twice — first a driver with no manifest, so `index()` returned
  `[]` regardless of encoding and the assertion passed for the wrong reason, then a wrong call shape.
  Both are the exact failure every brief here warns about.

- Let a run say how much of the repository it could not read. Landed `a7c1057`. A run's entire
  report was `N finding(s)`, identical whether it read the whole repository or a third of it, so
  `0 finding(s)` over a tree of legacy-encoded sources was indistinguishable from one that
  genuinely calls nothing. The block prints **above** the finding count, because a reader who sees
  the number first has already drawn a conclusion from it, and prints nothing at all when
  everything was read — a heading that fires every run is one the next reader learns to skip.

  The worker took a tuple-return over an optional out-parameter despite nine mechanical call-site
  edits, on the grounds that an omittable channel leaves the coverage report something a caller can
  silently drop, which is the exact failure being closed. It also noted the benchmark harness has
  printed a counted block of unread paths since a PNG first ended a corpus run, so the run path was
  the half that had never caught up.

  Two things from its report did not hold on verification. It said the indexers still decode with
  `errors="replace"` — every occurrence left in those files is a docstring explaining the removal.
  And it reported two suite skips; only one reproduced here. The conclusion it drew was right for a
  different reason, and that reason is B61.

- Count the language indexers' skips in a run's coverage figure. Landed `116d1f6`. B60's figure
  counted only the literal pass over `*.ts`, while both indexers walk every source file and recorded
  their skips in `self._undecodable` where nothing read it. **Structurally blind, not merely
  partial:** over a Python tree with one PEP 263 cp1252 module the adapter had `['src/legacy.py']`,
  the literal pass had `[]`, and the run reported it could not read *zero* paths having skipped a
  module the interpreter runs fine.

  The two reports overlap on a TypeScript tree, so the worker unioned rather than summed them —
  "an over-count is its own wrong number, and the one a reader trusts for being larger". Read
  through `getattr` so the protocol is untouched; verified here that an adapter lacking the member
  returns `[]` and breaks nothing, that a clean repository still reports none, and that a latin-1
  module now appears. It also corrected two docstrings that earlier tasks had falsified.

- Key the decode-handler drivers by scope rather than by line. Landed `229a242`. The positional key
  cost five re-anchorings in one run, none of them a defect in `src/`, and the docstring justifying
  it claimed no stable identity existed — measured false: 18 handlers, 18 distinct
  `path::scope::caught` keys, zero collisions. Verified by the probe that matters: inserting a
  comment above a decode handler, the exact edit that broke keys five times, leaves all 25 tests
  green; removing a driver still fails and now names
  `sync/signals/intake.py::_read_npm::JSONDecodeError+UnicodeDecodeError`. The line survives in the
  failure message while leaving the key, which is the split that makes both properties hold.

  **Two agents worked this in one worktree and both errors were the coordinator's.** The original
  was stood down on the evidence that its assigned tree was clean; it had never been in that tree.
  The all-worktree scan is now the only liveness check worth running.

- Retract ghost call sites without destroying findings. Landed `bb93176`, second attempt. The
  first removed the ghost and the `ON DELETE CASCADE` removed the finding with it; this one holds
  both properties at once by **retracting rather than deleting**. `call_site` gains `retracted_at`,
  its grain comment now reads *one row per position a call site has ever been indexed at*, and
  `call_sites_for_operation` excludes retracted rows with deliberately no opt-in flag — "a detector
  asking this question is asking what to raise a finding against, and a position the code no longer
  occupies is not one."

  Verified through the detector-facing query rather than the raw table, which matters: a raw
  `SELECT` still shows two rows and reads like a failure. What a detector sees:

      initial              detector 1 site at [5] | raw 1 | findings 1
      after the line shift detector 1 site at [6] | raw 2 | findings 1
      re-index unchanged   detector 1 site at [6] | raw 2 | findings 1   converges

  Corpus unmoved — precision 1.0000 n=26, recall 1.0000 n=26, negatives 7, pairs 17, every floor
  cleared. Suite `2507 passed, 1 skipped`.

  The lesson worth keeping is about the gate rather than the fix: the first attempt looked correct
  and was caught only because the brief had named the cascade as the thing that would make the
  change worse than the defect, and the check was run rather than assumed.

- Make the symbol-map pin check legible under concurrency. Landed `966d703`. `verify_staged_map`
  now reads the artifact **once** and decides parse, count and digest from those bytes, so a rewrite
  landing after the read cannot manufacture a refusal at all. When a refusal *is* raised the file is
  re-read, and a changed file raises `SymbolMapRewritten` — a `SymbolMapMismatch` subclass, so
  `score_corpus.py` and every other existing caller go on stopping.

  **The old code was worse than the brief described.** It called `read_staged_map(staged)` twice,
  once for the digest and once for the count, so it could compare two different files and refuse
  over neither. The brief only proposed narrowing a window; the window was a two-read race.

  Measured rather than argued: a two-thread writer produced 4000 concurrent refusals, **3726
  attributed to the rewrite and 274 falling on the loud side** — so the classification is good but
  not total, and roughly seven percent of concurrent rewrites still read as a real mismatch. Named
  as uncovered in the report, along with the case nothing can separate: a rewrite that completed
  before the read is indistinguishable from a stale artifact, because it is one.

  Verified here that the case the check exists for still fails loudly — one symbol repointed, refused
  naming both digests. It also settles the two-skips question that has been drifting between
  sessions: the second skip is a worktree lacking `.cache/specs/v2320.json` and `tools/oasdiff`, not
  the pin test.

- Record the rung a finding's binding came from. Landed `7cb4e95`. `finding.binding_rung` is a
  column rather than a join, `NOT NULL DEFAULT 'unattributed'` so rows written before it existed
  answer honestly, and all five detectors attribute by the rule that **the rung names the binding
  whose wrongness would make the finding wrong** — `static` for vendor_change, parameter_deprecation
  and observed_drift, the correlation's own rung carried through for efficiency, and status_rate
  folding a population to the weaker of the only two values that table holds.

  The subtlety the worker caught unprompted: the rung is deliberately absent from `_stable_id`, so a
  correlator improving from `unresolved` to `observed` converges on the row it already wrote instead
  of double-counting. Two idempotence tests pin it.

  Corpus verified here rather than taken on trust — the worker could not run that gate, because its
  worktree lacks the staged spec and the pin *correctly refused* to score against the wrong map,
  which is B64's work doing its job one task later. From a tree that has it: 1.0000, 1.0000, 7, 17,
  every floor cleared. Suite `2548 passed, 1 skipped`.

  Two coordinator errors it corrected: my preservation commit still called the work "unreviewed, not
  gated" after that stopped being true, and its schema comment still described the required field I
  had already reversed. It amended both. The enforcement half of that reversal is B66.

- Refuse to persist a finding that names no rung. Landed `f2c8275`. `insert_finding` raises
  `ValueError` naming the detector when `binding_rung` is `unattributed`, before the insert, with
  the argument for the placement in its own docstring — the check is at the store because `Finding`
  is exported from `sync.core` and a required field there breaks every third-party detector.

  Verified here: it refuses, names the detector, and **leaves no row behind** — the worker's second
  mutation existed specifically to prove that a write-then-check implementation would be caught, and
  it is the only test that catches it. The fourteen tests it had to touch each state the rung their
  detector attributes (four `observed`, three `static`, the efficiency fixtures commented as taking
  the correlated case) rather than a blanket value.

  It also closed the question B65 was asked and never answered: `insert_finding` is the only route
  that can set a rung. Two `INSERT INTO finding` exist — the store, and one test deliberately
  omitting the column to prove history reads back — `set_finding_status` writes status alone, there
  is no `COPY` or `executemany`, `psycopg.connect` appears in `src/` only in `store.py`, and
  `sync.benchmark` never persists a finding at all. That last fact is also why the corpus figures
  cannot move, and both sides measured 1.0000, 1.0000, 7, 17.

  `CLAUDE.md`'s rung bullet now names the mechanism, including why the check is not on `Finding` —
  the worker left that file to the coordinator deliberately, which was right.

- The conformance kit refuses what the store would. Landed `850854f`. `check_detector` gains a
  fifth rule, `_check_findings_name_a_rung`, rejecting `unattributed` and never asserting *which*
  rung is right — that is the detector author's judgement, and the kit cannot know it.

  **The accepting half caught what the failing half could not: `_CorrectDetector`, the kit's own
  published example of conformance, set no rung.** The kit was shipping an example whose findings
  the store would refuse. That is the third time this kit has been found certifying something it
  should not — `check_vendor_adapter` once passed an adapter resolving no symbol, and
  `check_remediator` read an empty diff as a decline — and the first time the miss was in its own
  reference implementation.

  Three mutations, each caught by a different test: removing the rule reddens both new tests,
  truncating to `findings[:1]` is seen only by the two-finding test, and inverting the predicate is
  caught by the accepting one. Verified here independently: two real rungs conform, no rung is
  refused naming the detector.

  It declined to check membership in `BindingRung`, correctly — the field is typed, so `banana`
  raises `ValidationError` at construction and never reaches a scan, leaving `unattributed` as the
  only member that is not a binder's rung. CLAUDE.md forbids validating conditions that cannot
  occur, and it applied that rather than adding a rule that could never fire.

  Two things beyond the ask: two fixtures had to name a rung because the new rule runs before the
  rule they exercise, and `docs/writing-a-vendor-adapter.md` still called the finding key a triple
  after `claim` had joined it.

- Make `sync.core` installable without the runtime. Landed `cf6031d`. `sync-core` is now a second
  distribution — a workspace member that `sync` depends on at `==0.1.0` — so an adapter author
  installs pydantic and nothing else. Verified independently rather than from the report, in a
  clean virtualenv holding only the built wheel:

      annotated-types, pydantic, pydantic-core, sync-core, typing-extensions, typing-inspection
      psycopg absent · langgraph absent · tree_sitter absent · mcp absent
      claude_agent_sdk absent · ast_grep_py absent
      sync.core imports, conformance kit reachable

  **Six packages against the eighty-one a checkout installs.** CLAUDE.md's first non-negotiable is
  now true in fact rather than in aspiration: it was enforced at the import level by `lint-imports`
  and false at the packaging level, which is the level the promise was made at.

  The worker took the hardest of the three shapes offered and documented the awkward part rather
  than hiding it: `src/` is the distribution's project root because `uv_build` refuses a module root
  outside the project it builds, and a backend that accepts one produces a wheel plus an sdist with
  no source in it. That reason is what stops the next person tidying it.

  `uv sync` still exits 0 for this repository and the suite is `2643 passed, 1 skipped`, which were
  the controls that mattered — a split that quietly changes what a developer here gets is not a win.

  Two coordinator near-misses worth recording. Diffed against a moved `main` the commit showed 506
  deletions including a whole test file; against its real base it is 449 insertions and zero
  deletions. And the first cherry-pick took only `HEAD`, which was the docs commit, missing the
  feature entirely — the six-file diff is what caught it.

### B117 - GraphStore never reconnects, so one dropped connection 500s every route until a restart - CLOSED

`sync.graph.store.GraphStore._connect` caches the connection and reconnects only when it is `None`:

```python
def _connect(self) -> psycopg.Connection:
    if self._conn is None:
        self._conn = psycopg.connect(self._dsn, row_factory=dict_row, autocommit=True)
    return self._conn
```

A connection that has been *closed* is not `None`, so it is handed back forever and every query
raises `psycopg.OperationalError: the connection is closed`. `sync.api.__main__.app_factory` builds
one store per process and holds it for the process lifetime, which means a single dropped connection
takes the whole console API down until somebody notices and restarts it.

Measured 2026-08-06: the console rendered a screenful of unreachable errors while Postgres was
healthy and idle at 11 of 300 connections, and a `GraphStore` constructed fresh in the same
interpreter answered `repo_ids()` immediately. The API had been up since 12:40 and its connection had
died at some point nobody can name, which is the point - nothing anywhere signals it.

The fix is a liveness check on the cached connection (`self._conn.closed`) and a reconnect, not a
pool. It is a boundary: the database is outside this process and a connection dying is a condition
that occurs, so `CLAUDE.md`'s "do not handle conditions that cannot occur" does not exempt it.

Closed by M4-W166. `_connect` replaces a connection reporting `closed` -- which covers `broken`
too, because psycopg marks a broken connection closed -- and the reconnect is guarded by a
transaction-depth counter so it never happens under an open `transaction()` block. The
transactional case is real, not scoped out: `transaction()` is the only way a block opens, so the
store tracks depth itself, and inside a block a dead connection is handed back and the next
statement raises `OperationalError` rather than committing later writes on a fresh autocommit
connection while the block's transaction dies with the old one. A block that *starts* on a dead
connection gets a live one, because `transaction()` resolves the connection before raising the
depth. Both behaviours are pinned in `tests/test_graph_store.py`: the reconnect test asserts the
query answers with the real rows written before the drop -- reconnect, not an empty result
swallowing the outage -- and the transaction test asserts the raise and that nothing from the
failed block committed.

### B118 - Killing a server's child leaves the wrapper holding the port, and the PID is dead

Stopping a dev server or API by killing the `python.exe`/`node.exe` that appears in the process list
leaves the shell wrapper that launched it alive, and the wrapper still owns the inherited listening
socket. The port then reports as `LISTENING` under a PID that no longer exists, `taskkill` answers
`ERROR: The process "26488" not found`, and nothing can bind it.

Measured 2026-08-06 on 8787: `Get-NetTCPConnection -LocalPort 8787` named three different dead PIDs
across successive calls, six orphaned `bash.exe` wrappers from 12:40 and 21:02 were still alive, and
killing all six did not release the socket - the last holder was a dead uvicorn reloader whose handle
Windows had not reclaimed. 8788 and 8790 were in the same state from earlier runs.

Two consequences, and the second is the expensive one. Operationally: **kill the wrapper chain, not
the child** - walk `ParentProcessId` up through `bash`/`sh` and stop those too. Diagnostically: a
process that cannot bind logs `Application startup complete` *before* the bind error, so a log tail
that stops at that line looks like a healthy server and is not. That is how an hour went into
debugging a `GraphStore` on a process that had never been listening, while every probe was answered
by a zombie from eight hours earlier.

`SYNC_API_ORIGIN` (M4-W151) is what makes this recoverable without a reboot: the API moves to a free
port and the console's proxy follows it.

### B119 - Two components are named `ControlBar`, and both are imported as `ControlBar` - CLOSED

`components/filters.tsx` has exported one since the filter module was written; `layouts/control-bar.tsx`
is the chassis's, added by M7-W160. They are not variants of one component. The filter one takes
`children` only and exists to group narrowing controls; the layout one adds the single `action` slot on
the right and is the page-level bar the chassis grammar names. Three files import a `ControlBar` today
and the name tells a reader nothing about which they got.

Found while composing the Fleet screen (M7-W163), which needs the layout one. `features/fleet/fleet-page.tsx`
imports it as `ControlBar as PageControlBar` rather than renaming anything, because both of the filter
one's callers - `features/bindings/binding-surface-page.tsx` and `features/vendors/vendor-findings-table.tsx` -
belonged to a second worker's branch running in parallel, and a rename would have collided.

**The one that should survive is `layouts/control-bar.tsx`**, and the argument is in that file's own
docstring: it is the same component with the slot the other never had, and its reason for not being
called `FilterBar` ("an ordering narrows nothing and a filter does") applies to both. So the filter
one's remaining job is the *contents* of a bar rather than the bar, which means the fix is to rename it
for what it holds - `FilterGroup` - and have all three callers use one `ControlBar`.

**Closes when:** one `ControlBar` exists in the tree, no file aliases it on import, and the three
callers are on the layout one. Cheap, and it must happen while only three callers exist - `CLAUDE.md`'s
debt section is explicit that a fact written twice will disagree with itself, and a name is a fact.

**Closed 2026-08-07 by M7-W164, and the entry is kept because how it closed is the useful part.** The
filter one was deleted rather than renamed: it carried no narrowing behaviour of its own - that lives in
`FacetChips` and `PrefixFilter`, which stay - so there was nothing for a `FilterGroup` to be. One
`ControlBar` exists, no file aliases it, and all three callers are on the layout one. **M7-W164 never saw
this entry**: it branched before M7-W163 pushed, so it reported there was no backlog item to close and was
right about its own tree. Two workers in parallel on one collision found the same answer independently,
which is the outcome the disjoint-directory rule is supposed to produce.

### B120 - A feature page cannot read `lib/routes.ts`, because `routes.ts` imports every feature page

`PageHeader` requires the route's `question`, and `lib/routes.ts` is where that sentence is written -
deliberately, so a screen and the command palette cannot disagree about it. But `routes.ts` imports each
page to build its `element`, so a page importing `ROUTES` closes a cycle: at module-initialisation time
`ROUTES` is still `undefined`, and a top-level `ROUTES.find(...)` throws
`Cannot read properties of undefined (reading 'find')`.

Measured in M7-W163: **`npm run build` does not catch it.** The cycle is legal ESM and typechecks
cleanly; it surfaced as three vitest suites failing to import - `app-frame.test.tsx`,
`page-header.test.tsx` and `routes.test.tsx` - none of which is about the fleet screen. A repository
without the frontend runner that landed in M4-W153 would have shipped this.

The workaround in place is to dereference at render instead of at module scope, which is safe because
both modules have finished initialising by then. It is a workaround: it leaves a cycle in the module
graph, and the next Phase 4 page will meet the same edge and may not recognise it.

**The fix belongs to whoever owns `App.tsx`**, which already maps over `ROUTES` to build its routes:
pass `question={route.question}` into the screen. Then no page reaches back into the registry, the cycle
is gone, and `page-header.tsx`'s own stated preference - "Passed rather than looked up, so a screen
rendered outside the router cannot fail to have one" - holds for the question as well as the title.

**Closes when:** no file under `features/` imports `ROUTES`, and a page rendered outside the router
still gets its question. Worth a guard in `test_console_design_tokens.py` afterwards, since the failure
is invisible to the compiler.

### B121 - The Fleet screen's fact rail costs six table rows above the fold

M7-W163 put a page header at the 48px display step, a control bar, and a four-tile fact rail at the top
of the Fleet screen. Measured at `--scale 10000`, before and after, with the sidebar at its default for
each viewport:

| | first table starts | table rows above the fold |
|---|---|---|
| 1440x900, before | 578px | 7 |
| 1440x900, after | 802px | 1 |
| 1280x800, before | 578px | 5 |
| 1280x800, after | 802px | 0 |

The trade is deliberate and the type range and side-by-side numbers are what the item was judged on -
2.67 to 4.00 and one placement to four. It is filed rather than accepted silently because **zero rows
above the fold on the operator's landing screen is a real cost**, and the document is 90-130px *shorter*
overall, so this is density moved to the top of the page rather than added to it.

Two things already paid for part of it and are worth not repeating: the scope sentence in the control bar
was cut to one line because its longer form was already in `VendorDistributionCard`, and the duplicated
`text-figure` totals were removed from the vendor and runs card titles once the rail carried the same
numbers.

What is left is prose, and it is not this item's to cut: `VendorDistributionCard`'s description runs five
lines and its bounded-total caveat four more, which is 224px of the 224px the first table moved down.
Both are honest and both are on screen twice over - the caveat restates what the `1,000+` glyph and the
tile's own note already say.

**Closes when:** at 1440x900 the first table row is above the fold with the rail in place, without
shortening a protected sentence. The likely route is progressive disclosure on the panel descriptions,
which is Task 7 of `plans/2026-08-05-sync-console-architecture.md` and unstarted - so this entry is a
caller for that task rather than a new piece of work.

### B127 - The Finding level cannot name its own severity, repository or call site, because the route drops them

**Renumbered from B122 on 2026-08-07.** Two sessions share this register and both took 122; the entry
that merged first keeps the number, checked by reachability rather than recalled - `6f0d7a1` reached
`main` at 00:50 UTC through PR #2, this one was committed at 10:30. **`19c70d7` and any commit around
it carry `B122` in their text**, which is left alone: rewriting pushed history to correct a label is
worse than the label.

`GET /api/findings/{finding_id}` reads a `_risk_row` through `GraphSurface.finding_by_id` and forwards
exactly two of its fields - `finding_id` and `binding_source` - merged onto `explain_call_site`'s
payload. The row it read also carries `severity`, `file` and `line`, and `sync.api.app.finding_detail`
discards all three.

The consequence is that the console's Finding level, whose own transport docstring calls it "one
binding in full", cannot say where the binding is. M7-W178 built the level's fact rail against the
direction's list - severity, status, vendor, operation, repository, first/last seen, rung - and could
honestly fill four of the seven from the payload. The rest are refused rather than approximated, and
`briefs/2026-08-07-substrate-finding.md`'s ruling 3 records why each substitute is wrong: a vendor
change's severity is not the finding's severity, and `indexed_at` is when the index last read the call
site rather than when anything was first seen.

Three separate things are missing and they are not one fix:

- **Severity and the call site (`file`, `line`) are already in hand.** The route reads them and throws
  them away, so this half is three keys on a `JSONResponse` plus the fields on `FindingDetail` in
  `web/src/api/types.ts`.
- **The repository is not on `_risk_row` at all.** `CallSite.repo_id` exists on the graph, and
  `binding_surface` already returns it per call site, so the join exists; the finding read does not
  make it.
- **First and last seen have no column.** A finding has no `first_seen`, and inventing one from
  `indexed_at` would be the exact conflation the level refused. This part is a schema question with a
  grain to declare, not a payload change.

**Closes when:** the first two land - the Finding level renders the finding's own severity, its
repository and its call site path and line, read from the payload rather than derived - and ruling 3 of
that brief is amended to record which of its three refusals expired. The third stays open behind a
declared grain for a first-detection timestamp, or is retired with an argument for why the level does
not need one.

### B123 - The Solution Workflow has no clock, so no entry on it can say when or how long

`WorkflowNode` is `{name, status, standing, evidence}` and `WorkflowState` carries no timestamp
either. `sync.dashboard.queries.workflow_state` reads the newest checkpoint row of the newest thread
and forwards its channel values; the row's own `ts` is not forwarded, and one row could not give a
per-node duration if it were.

The consequence is that the screen the product's argument lives on cannot say when a node ran, how
long it took, or how long the run has been parked. `references/direction/NOTES.md` entry 2 asks for
elapsed time on every entry of the narrative, and M7-W179 rendered none of it -
`briefs/2026-08-07-substrate-workflow.md`'s ruling 6 refuses all three available substitutes:
`query.dataUpdatedAt` is when the console last fetched, `RunRow.last_checkpoint_at` is on a different
route and is staleness rather than duration, and node order is not time.

The fix is a read rather than a schema change. The checkpointer writes one row per hop, each with its
own `checkpoint_id` (a UUIDv6, so text order is creation order) and its own `ts`. A second query over
`checkpoints` for this thread, grouped by the node each checkpoint advanced, gives a first-seen and a
last-seen per node from rows the route's connection is already open against.

Two things to get right when it lands, and both are the reason this is filed rather than done in
passing:

- **A duration between two checkpoints is not the node's execution time.** It is the wall clock
  between two writes, which for `await_ci` is the customer's CI and for a dead run is unbounded. The
  label has to say which - the same distinction `last_checkpoint_at` already carries on the fleet
  screen, and the same one this console refuses to guess at.
- **A node with one checkpoint has no duration at all**, and rendering a zero would be the absence
  collapsed onto a measurement.

**Closes when:** each node entry on the Solution Workflow carries a timestamp read from the
checkpointer, labelled as what it is, with the no-clock sentence in the level's opening entry removed
in the same commit.

### B124 - A superseded remediation generation is not reachable from the run that superseded it

`GET /api/workflows/{finding_id}` answers with the newest thread only, which its own type docstring
states. A finding retried across generations therefore has `generation_count` threads on screen as a
number and one of them as content: the abandoned first attempt that taught routing something is
counted and not shown.

The seeded fixture is the case exactly - `9f176dea35907f95beb29553e574a037` carries two generations,
an abandoned first attempt reading *"static verification failed after 3 attempts"* and a second that
opened a pull request. **Abandoned runs are data** is one of `CLAUDE.md`'s four pipeline rules, and
the console currently renders the newest generation's abandonment beautifully and a superseded one not
at all.

`GET /api/runs` holds those rows and is not the answer: it is fleet-wide and paged with no finding
filter, so on any real fleet the other generations of one finding are several pages away, and
`useRuns` takes no `enabled` option - so every reader of every workflow page would pay a fleet-wide
polled request to serve a minority case. `briefs/2026-08-07-substrate-workflow.md`'s ruling 7 carries
the whole refusal.

The fix is small and sits in the query that already runs. `workflow_state`'s
`COUNT(DISTINCT thread_id)` subquery is over exactly the rows wanted; returning a `generations` array
of `{thread_id, generation, outcome, abandon_reason}` alongside the count costs one more scan of the
same threads.

**Closes when:** the Solution Workflow renders each superseded generation as its own entry, with its
`abandon_reason` where the run stopped - which is the direction's collapsed-generation slot, and the
one the level currently has nothing true to put in.

### B125 - The Pull Request level cannot name the repository its pull request was opened against

`sync.remediate.state.RemediationState` carries `repo: RepoRef` on every run, so the checkpoint the
console reads already holds the answer. `sync.dashboard.queries.workflow_state` forwards eleven
other channel values out of that same dict and not this one, so the one screen in the console whose
subject is a pull request against a customer's repository cannot say which repository that is.

The direction's rail for this level is *"number, branch, state, opened at, repository, and the
finding it answers"*. Number and branch are lifted out of node evidence, state is the outcome panel,
opened-at is B123 - the repository is the only ask with no route to it at all.

The substitute is available and is refused in `briefs/2026-08-07-substrate-pull-request.md`, ruling
7: `pr_url` reads `https://github.com/example/repo/pull/101` on the seed, and a repository name can
be cut out of it with two `split` calls. A forge URL is an address rather than a schema. The path
shape differs between forges, an enterprise host puts the owner elsewhere, and the console would be
manufacturing a field by pattern-matching a string the payload never labelled - right on GitHub and
silently wrong anywhere else, which is worse than an absent row because an absent row is a question
and a wrong one is an answer.

**Carried on the same entry, because the same file open fixes both:** `asHttpUrl` in
`features/workflows/evidence.tsx` and the boundary check inside
`features/pullrequests/bundle-facts.ts` are two copies of one rule - anything that is not `http:` or
`https:` renders as text rather than as an anchor, because a `javascript:` href is a script the
console would run on a forge's say-so. The second copy exists because the first is not exported and
M7-W180 did not open another level's directory to export it. Two copies of a security boundary is
the defect `CLAUDE.md` names as the most expensive kind: one of them will be fixed and the other
will not.

**Closes when:** `workflow_state` returns the run's repository alongside `thread_id`, the Pull
Request level renders it as a rail row linking to that repository's Codebase screen, and the URL
boundary check is one function in `lib/` that both features import.

### B126 - `abandon_reason` is free text, so the claim that abandonment is queryable is weaker than it reads

`docs/superpowers/specs/2026-07-27-sync-pipeline-discipline.md` states that abandoned runs are data
and that `abandon_reason` stays queryable, because *"abandoned attempts are where routing learns
which change kinds are not mechanically safe"*. `M12-W196` built the first query that reads them
back and found the field is **diagnostics prose, not a coded vocabulary**.

So the aggregate tallies whatever strings occurred. You can count two identical sentences; you
cannot group two spellings of one cause, and you cannot ask "how often did tier 2 abandon because
the compiler never recovered" without matching substrings. A vocabulary is exactly what the spec's
own argument needs and exactly what does not exist.

**This is the shape `.claude/rules/interface-originality.md` already names as adoptable** - *"a
reason for giving up should be a closed set of codes rather than free text, because free text cannot
be aggregated and a promise to learn from failures needs a schema that can answer the question."*
The shape transfers; the values are ours to derive from routing predicates rather than borrowed.

**What this is not.** It is not a case for deleting the prose. The sentence an operator reads is
what makes an abandonment reviewable, and `RunState.diagnostics` exists precisely because the
operator's one line and the next attempt's feedback are different audiences. The fix is a **coded
reason beside the prose**, not instead of it.

**Closes when:** a run writes a code from a closed set alongside its diagnostics, the set is
declared in one place, and the abandonment aggregate groups by the code. **Do not invent the
vocabulary from the outside** - derive it from the abandonment paths that actually exist in
`sync.remediate.nodes`, and record the ones observed but not yet coded rather than forcing them into
a bucket.

**Measured 2026-08-07 and worth stating before anyone plans against it:** the corpus holds **4**
`migration_outcome` rows across 3 `(change_kind, tier)` groups, with **one** abandonment. There is
no signal to learn from yet whatever the schema does, so this ranks behind getting attempts on the
board.

