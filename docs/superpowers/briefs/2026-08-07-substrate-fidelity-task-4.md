# Feeding the bars — what each screen already controls, and where the count actually lives

Task 4 of `docs/superpowers/plans/2026-08-07-console-fidelity-pass.md`. Work item M7-W195.

The gap report measures two things this brief is the inventory for.
`reports/2026-08-07-console-fidelity-gaps.md` Surface 3 row 3: on `/` and `/detectors` the control
bar holds zero controls — `main input` 0, `main select` 0, `main button` 0 — and on the vendor page
the real controls sit inside a card body at `y=469-585`, beneath a panel heading. Surface 4 row 5:
the footer bar is absent on the two longest pages in the console, 3380px and 3014px, which put their
record counts in `<h2>` text instead.

The rule that bounds every row below is the plan's own: **a control must narrow through the API or
the URL state that already exists.** A control that filters rows already fetched is refused —
`components/filters.tsx` opens with why, and it is the same defect the console has closed six times.
A screen with nothing honest to control renders the bar's sentence, and this brief names which
screens those are rather than leaving the next reader to re-derive it.

## The controls that exist today, and where they sit

| Screen | Control | What it narrows | Where it sits before | Where it sits after |
|---|---|---|---|---|
| `/` | "Every repository the index has seen." | nothing — a sentence | `ControlBar` children | unchanged |
| `/` | "Detector attribution" link | nothing — a navigation | `ControlBar` action | unchanged |
| `/` | runs pager | `?runs_offset`, through `GET /api/runs` | `RunsCard`, and only above the cardinality threshold | `FooterBar`, on both branches |
| `/detectors` | scope statement, or the repository id | nothing — a sentence | `ControlBar` children | unchanged |
| `/detectors` | *(none)* | — | — | **new:** widen to the fleet, when `?repo_id` is set |
| `/vendors/:vendorId` | severity chips | `?severity`, through `GET /api/vendors/{id}` | `VendorFindingsCard` body, under the panel header | page-level `ControlBar` |
| `/vendors/:vendorId` | call-site path prefix | `?path`, same route | same | page-level `ControlBar` |
| `/vendors/:vendorId` | ordering | `?order`, same route | same | page-level `ControlBar` |
| `/vendors/:vendorId` | active-filter summary and its clear | `?severity`, `?path`, `?findings_offset` | same | directly under the page-level bar |
| `/vendors/:vendorId` | findings pager | `?findings_offset` | `FooterBar` in the findings panel | unchanged |
| `/vendors/:vendorId` | changes pager | `?changes_offset` | `FooterBar` in the changes panel | unchanged |

## The record counts, and which heading they were hiding in

| Screen | Count | Where it sits before | Where it sits after |
|---|---|---|---|
| `/` | repositories indexed | the panel's own `h2` — `` `${n} repositories indexed` `` — *and* a cardinality sentence above the table | `FooterBar` `left`; the `h2` becomes the section's name |
| `/` | detectors with open findings | the same shape, in `detectors-summary.tsx` | `FooterBar` `left`; the `h2` becomes the section's name |
| `/` | vendors with open findings | cardinality sentence above the table | `FooterBar` `left` |
| `/` | runs | cardinality sentence above the table below the threshold, `FooterBar` `left` above it | `FooterBar` `left`, both branches |
| `/detectors` | detector cards in the catalogue | nowhere — only inside the panel figure's unit, "N open findings across M detectors" | `FooterBar` `left` under the catalogue |

The `h2` rows are the gap report's measurement stated exactly: a count rendered as a heading is a
count nothing under the table asserts, and `repositories-table.tsx` and `detectors-summary.tsx` were
rendering theirs twice — once in the heading and once in the cardinality sentence four lines below
it. One copy survives, and it is the one under the rows it counts.

## Rulings

**1. `FooterBar` gains an optional pager rather than a mandatory one, and this is the only change to
`layouts/`.** Every count above belongs to a set the API returns whole: `GET /api/repositories`,
`GET /api/detectors` and `GET /api/overview` take no offset at all, and `GET /api/runs` returns a
complete listing whenever the fixture is under the cardinality threshold. `runs-table.tsx` already
had the argument written down — *"`FooterBar` would render page controls for a set that fits on one
page, which is a choice nobody has"* — and paid for it by rendering no footer at all on that branch.
So the seven paging props become one optional group: supply them and the bar carries a pager, omit
them and it carries only what the count is counted over. A type predicate holds the group together,
so a caller cannot supply four of the seven.

**2. Fleet has nothing honest to narrow, and its bar keeps only its sentence.** `GET /api/overview`
accepts `repo_id`, so a scope control is technically available — and it is refused for the reason
M7-W163 recorded when the bar landed: Fleet is the fleet-wide level by construction, and the
per-repository answer is a different screen one level down rather than a narrowing of this one.
`GET /api/runs` takes `limit` and `offset` and nothing else, so there is no disposition filter to
offer either. **Fleet is the screen this task records as having no honest control.**

**3. `/detectors` gains one control, and it is the half the top bar cannot reach.** The scope key is
`?repo_id`, and the new top bar's repository switcher already writes it in place — `/detectors` is
in `REPO_SCOPED_PATHS`. What the switcher has no entry for is *clearing* it: its list is
repositories, and the fleet is not one of them. So a scoped `/detectors` had no way back to the
fleet-wide answer except the browser's Back button. The bar carries that one control, and only while
a scope is set; unscoped, the bar carries its sentence, because the scope is already at its widest
and the only control that could narrow it is one bar above. A second repository picker here would be
the same control drawn twice, which is what Part B of this work item exists to stop.

**4. The vendor page's controls move up, and they say what they narrow.** M7-W174 argued against a
page-level bar on this screen and the argument was about *scope*: the bar would restate a scope the
fact list and the paragraph beside it already carry. That still holds and the bar carries no scope.
What it carries is the three narrowings that were buried in a card body under a heading, a figure
and a caption — and because this page has two panels and these narrow only one of them, the bar
states which. The vendor-changes table is untouched by all three, which is a fact the screen already
argues in prose and now also renders where the controls are.

**5. The filter state is one hook read twice, never two derivations.** Moving the controls out of
`VendorFindingsCard` splits the URL state from the table it narrows: the bar sets `?severity`,
`?path` and `?order`, and the card's empty state needs the same values to say which kind of nothing
it is showing. `useVendorFindingFilters` is one definition both consume, so the two cannot disagree
about what is currently narrowing the table. The query is `useVendorFindings` under one key, so the
bar and the card share one fetch rather than issuing two.

**6. The `/detectors` catalogue footer states its ordering, and that is new information rather than
decoration.** `detector-accountability.tsx` has documented since it was written that order is
alphabetical and that nothing re-sorts by total, because *"sorting by count is what turns a roll-up
into a leaderboard"* — and the screen never said so. `describeCardinality` is passed the real
`shown`, which is every row, so the sentence reads "This is all N detectors" or "Showing N of N",
never the "Showing 10 of N" a default `shown` would have claimed over a catalogue that slices
nothing.

## The breadcrumb trim, which rides along in the same work item

Task 1's review, Important finding 1. The top bar landed in M7-W183 (`6eafb87`) and renders a scope
trail: a Fleet link, then a repository switcher, then a vendor switcher, each derived from the
address — `layouts/scope-switchers.tsx`. On five list routes the page's own breadcrumb then repeats
those same segments about 90px below it.

**The bar owns exactly three segments: Fleet, the repository, the vendor.** It stops there by
design — a finding's vendor is in the payload rather than in the address, so carrying the trail
deeper would mean the bar issuing a query per route. Everything deeper than a vendor is still the
page's own to state.

| Route | Trail before | Owned by the bar | Trail after |
|---|---|---|---|
| `/vendors/:vendorId` | Fleet → *repo* → *vendor* | all of it | none — `PageHeader` renders no trail |
| `/repositories/:repoId` | Fleet → *repo* | all of it | none |
| `/detectors` | Fleet → *repo* → "Detectors" | the first two | "Detectors" |
| `/repositories/:repoId/observed` | Fleet → *repo* → "Signals" | the first two | "Signals" |
| `/bindings/vendors/:vendorId/operations/:operationId` | Fleet → *vendor* → *operation* | the first two | the operation id |

Nothing else is trimmed, and the three surviving single-crumb trails are deliberate. On the Signals
and binding-surface routes the remaining crumb is not the page's title — those titles are the
repository id and `vendor / operation` — so the crumb is the level name and the bar does not reach
it. On `/detectors` the surviving crumb does repeat the `h1`, at 12px muted against 46px; that is
recorded here as an observation for the whole-branch review rather than trimmed, because trimming it
would be removing a segment the bar does not own, which is a wider change than the finding asked
for.

`layouts/scope-switchers.tsx`'s docstring claimed that `layouts/breadcrumbs.tsx` *"keeps the full
in-page path, including its own root"*. That stops being true here, so the paragraph is corrected in
the same commit — a docstring that describes the arrangement before the change is the most expensive
kind of stale comment, because it reads as an argument against the change.
