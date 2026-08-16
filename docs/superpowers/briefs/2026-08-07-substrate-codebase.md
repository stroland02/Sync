# Codebase on the substrate — the mapping table, and the rulings it forced

Task 6 of `docs/superpowers/plans/2026-08-06-console-supabase-substrate.md`, first level. Work item
M7-W173.

Codebase is `/repositories/:repoId` — the selected repository, and the root of everything beneath
it. It is the first level ported after Fleet, so it is the first test of whether Fleet's pattern
transfers rather than merely being what Fleet happened to do.
`docs/superpowers/briefs/2026-08-07-substrate-fleet.md` is the parent document and its eleven
rulings bind here wherever they generalise; this file records only what is new or what this level
decided differently, and says which.

The table below was built by reading `codebase-page.tsx`, `index-coverage-card.tsx` and
`open-findings-card.tsx` line by line, not from memory. Every rendered string, every count, every
state branch is a row.

## The mapping table

### `codebase-page.tsx` — the page shell

| Field rendered today | Substrate slot |
|---|---|
| breadcrumb trail "Fleet" → repository id | `PageHeader` trail, `Breadcrumbs` unchanged |
| `h1` repository id, mono, at `--text-page` | `PageHeader` title, mono, at the display step — see ruling 1 |
| — (the route's own question is not rendered today) | `PageHeader` question, read from `ROUTES` through `routeQuestion` — ruling 1 |
| — (no scope statement in the furniture register today) | `ControlBar` left slot, short form — ruling 2 |
| — (no primary action today) | `ControlBar` action: the Signals screen for this repository — ruling 2 |
| the three panels, stacked full width | two panels paired at `xl`, the telemetry panel full width — ruling 3 |

### `codebase-page.tsx` — `ObservedTelemetryCard`

| Field rendered today | Substrate slot |
|---|---|
| title "Observed telemetry" | `MetricPanel` label, furniture register. No metric — ruling 4 |
| description, "A row here is evidence a call site was exercised — it is not proof the binding correlating it to an operation is correct." | `MetricPanel` caption, unchanged |
| the same description's inline link "see it grouped with the other two roles, on the Signals screen" | caption, unchanged and still inline — ruling 2 |
| `LoadingState`("observed telemetry for {repoId}") | unchanged, outside the panel |
| `ErrorState`(error, "observed telemetry for {repoId}") | unchanged, outside the panel |
| heading "Calls" at `--text-section` | `h3` in the furniture register — ruling 5 |
| empty state "No call has been observed for this repository." with its detail | `EmptyState`, unchanged, in the panel body |
| `ObservedCallsTable` | unchanged — ruling 6 |
| `PageControls` under the calls table | `FooterBar`, no `left` — ruling 7 |
| `TelemetryRungNote`: "No call has ever been observed for this repository — silence, not a measured zero" | unchanged, beneath the table, all three branches |
| `TelemetryRungNote`: "Every observed call below rests on the {rung} rung." | unchanged, carries `RungBadge` |
| `TelemetryRungNote`: "Mixed: … The rung column on each row says which is which." | unchanged |
| heading "Shapes" | `h3`, furniture register — ruling 5 |
| the shapes paragraph, "a shape is a vendor-wide fact, not a per-repository one" | panel body, unchanged, above the table |
| empty state "No shape recorded for this repository's operations." with its detail | `EmptyState`, unchanged |
| `ObservedShapesTable` | unchanged — ruling 6 |
| `PageControls` under the shapes table | `FooterBar`, no `left` — ruling 7 |
| heading "Error windows" | `h3`, furniture register — ruling 5 |
| "Failure counts have no denominator in this table — a count is not a rate" | panel body, unchanged, above the table (protected) |
| empty state "No error window recorded for this repository." with its detail | `EmptyState`, unchanged (protected: "cannot tell the two apart") |
| `ErrorWindowsTable` | unchanged — ruling 6 |
| `PageControls` under the error-windows table | `FooterBar`, no `left` — ruling 7 |

### `open-findings-card.tsx`

| Field rendered today | Substrate slot |
|---|---|
| `LoadingState`("open findings in {repoId}") | unchanged, outside the panel |
| `ErrorState`(error, "open findings in {repoId}") | unchanged, outside the panel |
| title figure `describeBoundedTotal(total_findings, bound_reached)` at `--text-figure` | `MetricPanel` metric value — ruling 8 |
| title words "open finding(s) in this repository" | `MetricPanel` metric unit, singular/plural unchanged |
| — (the panel has no name of its own today; the figure is the title) | `MetricPanel` label `OPEN FINDINGS` — ruling 8 |
| description "Counted in {repoId} and in no other repository — every figure on this card moves when a different repository is selected." | caption, first paragraph, unchanged |
| the same description's inline link to `/detectors?repo_id=` | caption, unchanged and still inline — ruling 2 |
| `boundedTotalCaveat` paragraph when the count stopped early | caption, second paragraph, rendered on the same condition |
| empty state "No open finding against any vendor in {repoId}." with its detail | `EmptyState`, unchanged, in the panel body |
| cardinality statement over vendors | panel body, above the table |
| `VendorFindingsTable` | unchanged — it is already on the substrate, restyled by M7-W172 |
| `SeverityBreakdown` heading "By severity" | `h3`, furniture register — already there, unchanged |
| `SeverityBreakdown` columns Severity, Open findings | `components/data-table.tsx`, Studio header register |
| `ProvenanceStrip` with both `bindingNullLabel` variants | panel body, beneath the tables, unchanged (both protected) |

### `index-coverage-card.tsx`

| Field rendered today | Substrate slot |
|---|---|
| title "Index coverage" | `MetricPanel` label `INDEX COVERAGE`, furniture register |
| description "A vendor absent from the table is not zero — it is a question this view cannot answer" | caption, unchanged |
| the same description's second half, on a vendor link carrying this repository's scope | caption, unchanged |
| `LoadingState`("index coverage for {repoId}") | unchanged, outside the panel |
| `ErrorState`(error, "index coverage for {repoId}") | unchanged, outside the panel |
| empty state "The index holds no call site for {repoId}." with its detail | `EmptyState`, unchanged (protected: "nobody ever configured") |
| figure `total_call_sites` at `--text-figure` with "call site(s) indexed." | `MetricPanel` metric — ruling 9 |
| column Vendor, mono, as a link carrying `?repo_id=` | `data-table` identifying column, link |
| column Call sites, mono | `data-table` column, mono |
| column Last indexed, `Formatted`/`formatTimestamp` | `data-table` column, mono at `--text-meta` |
| the stale-response comment on `last_indexed?.[vendorId]` | unchanged — it states a constraint the code cannot show |
| "'Last indexed' is the newest indexing timestamp among that vendor's call sites — staleness, not a promise the index is current." | panel body, beneath the table, unchanged |

## The rulings

Nine fields or arrangements had no slot Fleet had already settled. Fleet's eleven rulings are not
restated here — the metric value at `--text-figure`, the panel title in the furniture register with
its own `h2`, the accepted collapse of `variant="grouping"`, `--card-padding-x`, the kept
`components/skeleton.tsx` and the untouched `fact-tile.tsx` all apply unchanged.

**1. The chassis arrives with this port, because this level never had it.** Fleet's mapping table
says "`PageHeader` title, unchanged" for every chassis row, because M7-W163 had already put Fleet on
the chassis before M7-W172 ported it to the substrate. Codebase had neither: it renders a bare `h1`
at `--text-page` under a breadcrumb, with the route's `question` sitting unread in `lib/routes.ts`.
The M7 plan's Phase 4 is explicit that each level takes the chassis as it is recomposed — "a fact
rail replacing the prose intro, a fact-tile grid replacing the definition lists, a control bar
replacing ad-hoc filter placement, a footer bar replacing in-card pagination" — so this port does
both jobs in one work item rather than leaving the level on a 22px heading until a second item that
is not in any plan. `layouts/` is consumed, not edited: `PageHeader`, `ControlBar`, `Breadcrumbs`
and `FooterBar` are imported exactly as Fleet imports them.

Measured consequence: the type range on this route goes from 2.33:1 to 4.0:1, against `DESIGN.md`'s
3.4 bar. The display step is what does it, and `PageHeader` is the only component permitted to spend
it.

**2. A destination is named once, and the `ControlBar` action is the one this level has that no
sentence already argues for.** Fleet moved its detector-attribution link out of a card description
and into the action slot. Two of this level's links cannot move the same way: the detectors link
sits inside "detector attribution for this repository alone is on the detectors screen", and the
Signals link sits inside a sentence about which level of the specification owns this traffic. Both
sentences make an argument that the link completes; lifting the link out would leave a sentence
shortened, which `.claude/rules/console-surface.md` forbids for a qualification and which is a bad
habit to acquire for one that is merely adjacent.

So both stay inline, and the action slot takes the Signals screen as a plain navigation — the one
thing an operator does next that is not a row on this page. The bar's left slot carries the short
form of the scope ("This repository alone."); the long form stays in the open-findings caption,
exactly as Fleet split the same sentence between its bar and its vendor panel.

**3. Two panels pair at `xl`, and the telemetry panel does not.** The screen was three full-width
panels stacked, which is the single-column shape
`reports/2026-08-06-why-the-console-came-out-flat.md` measures as the console's default failure.
Open findings and index coverage are both narrow — a two-column table and a three-column table — and
they answer the two halves of the route's own question, so they sit beside one another. The
telemetry panel holds three tables of eight to twelve columns each and stays full width; halving it
would wrap every row.

**4. The telemetry panel carries no metric, and that is ruling 2 of the Fleet brief rather than an
omission.** It holds three totals — calls, shapes, error windows — and no single figure is its
grain. Each total is already asserted on screen by its own `FooterBar` range ("1–2 of 2"), and a
figure invented to fill the slot would either pick one of the three arbitrarily or sum three counts
that do not share a denominator.

**5. A heading inside a panel moves to the furniture register.** "Calls", "Shapes" and "Error
windows" were `--text-section`; they are now uppercase, open-tracked `--text-meta` at the second ink
level, which is what `corpus-summary.tsx`'s three tally headings already do inside a Fleet panel and
what `SeverityBreakdown` on this screen already did. They stay `h3`: the panel's own `h2` contains
them, and Fleet's ruling 11 is that outline level and visual register are two decisions.

**6. `features/telemetry/`'s three tables are consumed unchanged, and they still spell the old table
anatomy.** `ObservedCallsTable`, `ObservedShapesTable` and `ErrorWindowsTable` live in the Signals
level's feature directory, are imported by that level's own `SignalSourcePanel`, and are not this
work item's files. Their column headings therefore stay at `components/ui/table`'s register while
this screen's other two tables take `components/data-table`'s. That is visible: within the telemetry
panel a column heading is sentence-case, and outside it a column heading is uppercase.

Accepted for the length of one work item rather than fixed here, because fixing it means editing
another level's directory before that level's own mapping table exists — which is precisely the gate
this document is. The Signals port is the next level in Task 6's order and inherits all three tables
as its own rows.

**7. `FooterBar` replaces `PageControls` under each of the three telemetry tables, with no `left`.**
The M7 plan asks for a footer bar in place of in-card pagination and this is the level that has
three of them. `left` is where a caller puts what the count is counted over; none of these three
tables has such a sentence, and the rung note that could have gone there renders in the zero case as
well, where there is no footer at all. Putting it in the footer would have deleted it from the one
branch that most needs it — the branch whose sentence is "silence, not a measured zero".

**8. The open-findings figure keeps its own panel and its own words.** `MetricPanel` splits a figure
from the words that say what it counts, and this card already had both in one `CardTitle`: the
bounded total at `--text-figure`, then "open findings in this repository". They map straight across —
value and unit — and the panel gains the name it never had. The bounded `+` glyph from
`describeBoundedTotal` is unchanged and its caveat paragraph still renders on the same condition, so
the glyph is still never the only channel.

**9. There is no fact rail on this level, and the reason is that `IndexCoverageCard` is shared.**
Fleet's rail exists because six panels on one screen each carried a headline count and an operator
had to read six panels to find four numbers. This level has three panels and three figures, one of
which — `total_call_sites` — is rendered by a component the Signals level also mounts.
Hoisting it into a Codebase-only rail would either delete that figure from the Signals screen or
render it twice on this one, and M7-W163's ruling against rendering a count twice is the whole
reason a rail is worth having. So each figure stays as its own panel's metric, which is the
arrangement `metric-panel.tsx` was written for, and this level's top of screen is the header, the
control bar, and the two panels the route's question is about.

Reversing it is small if the owner wants a rail here: the tiles would be open findings and call
sites, `IndexCoverageCard` would take a `metric={undefined}` prop for the Codebase caller only, and
the Signals caller would keep its own. That is a prop and a conditional, and it buys a rail at the
cost of one component rendering differently on two screens.
