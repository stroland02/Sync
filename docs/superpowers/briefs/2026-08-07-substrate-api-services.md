# API Services on the substrate — the mapping table, and the rulings it forced

Task 6 of `docs/superpowers/plans/2026-08-06-console-supabase-substrate.md`, second level. Work
item M7-W174.

API Services is `/vendors/:vendorId` — one vendor, what it changed, and what that change is doing
to the codebase. It is the third level ported, after Fleet (M7-W172) and Codebase (M7-W173).
`docs/superpowers/briefs/2026-08-07-substrate-fleet.md` is the parent document and its eleven
rulings bind wherever they generalise; `docs/superpowers/briefs/2026-08-07-substrate-codebase.md`
adds nine more. This file records only what is new here, or what this level decided differently,
and says which.

The table below was built by reading `vendor-page.tsx`, `vendor-findings-table.tsx` and
`vendor-changes-table.tsx` line by line, not from memory. Every rendered string, every count, every
state branch is a row.

## The mapping table

### `vendor-page.tsx` — the page shell

| Field rendered today | Substrate slot |
|---|---|
| `UnknownRoute` when the URL carries no `vendorId` | unchanged, before anything else renders |
| breadcrumb trail "Fleet" → vendor id, unscoped | `PageHeader` trail, `Breadcrumbs` unchanged |
| breadcrumb trail "Fleet" → repository id → vendor id, scoped | `PageHeader` trail, unchanged |
| `h1` vendor id, mono, at the display step | `PageHeader` title, unchanged — the header moves to full width, see ruling 1 |
| the route's own question, read from `ROUTES` | `PageHeader` question, unchanged |
| scope paragraph, unscoped: "Every open finding and every published change… open it from a repository to narrow the findings below." | page body, beside the fact list, unchanged in wording — ruling 1 |
| scope paragraph, scoped: "Open findings for {vendor} in {repo} alone. The vendor changes below are the exception and say so…" | page body, beside the fact list, unchanged in wording — ruling 1 |
| fact "Vendor" → the vendor id, mono | `FactList`, unchanged — ruling 3 |
| fact "Repository scope" → the repository id, or "Nothing selected one on the way here" | `FactList`, unchanged |
| fact "Findings counted over" → the repository id, or "Every repository the index has seen" | `FactList`, unchanged |
| fact "Changes counted over" → "The vendor, never a repository" | `FactList`, unchanged |
| `h2` "Errors and incidents" at `--text-section` | `MetricPanel` label, furniture register, still an `h2` — Fleet ruling 11 |
| the findings paragraph, both scope variants | `MetricPanel` caption, unchanged in wording |
| `h2` "Vendor changes" at `--text-section` | `MetricPanel` label, furniture register |
| the changes paragraph, both scope variants | `MetricPanel` caption, first paragraph, unchanged in wording |
| — (nothing on screen today says a count of vendor changes is not a measurement) | `MetricPanel` caption, second paragraph — ruling 5, and it is the reason this level needed a ruling at all |
| the two sections stacked full width, header and fact list paired at `lg` | header full width; prose and fact list paired at `xl`; both panels full width — rulings 1 and 2 |

### `vendor-findings-table.tsx`

| Field rendered today | Substrate slot |
|---|---|
| `LoadingState`("open findings for {vendor}") | unchanged, outside the panel |
| `ErrorState`(error, "open findings for {vendor}") | unchanged, outside the panel |
| — (this level renders no headline figure today) | `MetricPanel` metric: `severity_total` at the figure register — ruling 4 |
| — (the panel has no name of its own today; the page's `h2` named the section) | `MetricPanel` label `ERRORS AND INCIDENTS` |
| `ControlBar` holding the three narrowing controls | unchanged, inside the panel body — ruling 6 |
| `FacetChips` legend "Severity", `allLabel` "Every severity" | unchanged |
| `FacetChips` `countScope`: "Counted across all N open findings… these are the choices available, so they stay the same whichever one is selected." | unchanged |
| `PrefixFilter` legend "Call site path", placeholder `src/billing/` | unchanged |
| `PrefixFilter` note: "Matched as a prefix… never as a substring" | unchanged |
| `OrderChoice` legend "Order", the applied ordering and the severity order | unchanged |
| `ActiveFilters` "Narrowed by …" and "Clear all filters" | unchanged |
| empty state, page past the end: "This page is past the end of the N findings that match." | `EmptyState`, unchanged, in the panel body |
| empty state, filter matched nothing: "No open finding for {vendor} in {scope} matches this filter." | `EmptyState`, unchanged |
| empty state, nothing at all: "No open findings for {vendor} in {scope}." | `EmptyState`, unchanged |
| the comment on why Rung sits ahead of Call site, carrying "sideways scroll" | unchanged, verbatim (protected) |
| column Severity | `components/data-table`, Studio header register |
| column Rung, `RungBadge` | `data-table` column — never hidden, never coloured |
| column Call site, `file:line` as a link to the finding, with its `aria-label` | `data-table` identifying column, link, mono |
| column Symbol, `orAbsent` | `data-table` column, mono |
| column Operation, link into the binding surface or `orAbsent` | `data-table` column, mono |
| column Change kind, `orAbsent` | `data-table` column |
| "Each call site opens its finding. The finding's full id is the heading of that page…" | panel body, beneath the table, unchanged |
| `FooterBar` with the filtered-total caveat in `left` | unchanged — ruling 4 |
| `ProvenanceStrip` `bindingNullLabel` "none: there is no finding here to attribute" | unchanged (protected) |
| `ProvenanceStrip` `bindingNullLabel` "mixed: the findings on this page do not all rest on one rung" | unchanged (protected) |

### `vendor-changes-table.tsx`

| Field rendered today | Substrate slot |
|---|---|
| `LoadingState`("vendor changes for {vendor}") | unchanged, outside the panel |
| `ErrorState`(error, "vendor changes for {vendor}") | unchanged, outside the panel |
| — (no headline figure today, and deliberately none after) | **no `MetricPanel` metric** — ruling 5 |
| — (the panel has no name of its own today) | `MetricPanel` label `VENDOR CHANGES` |
| empty state "Nothing recorded for {vendor}." with its detail | `EmptyState`, unchanged, in the panel body |
| column Published, `formatTimestamp` inside a `<time>` | `data-table` column, mono at `--text-meta` |
| column Kind, `orAbsent` | `data-table` column |
| column Severity, `orAbsent` | `data-table` column |
| column Operation, link into the binding surface or `orAbsent` | `data-table` column, mono |
| column Path, `orAbsent` on the JSON pointer | `data-table` column, mono |
| column Versions, `from` → `to`, both `orAbsent` | `data-table` column, mono |
| `FooterBar`, no `left` | `FooterBar` with the at-least-once caveat still in the caption rather than here — ruling 5 |
| `ProvenanceStrip` `bindingNullLabel` "none: this answer is built from vendor changes and holds no binding" | unchanged |
| `ProvenanceStrip` `indexedNullLabel` "not applicable: nothing here was read out of the codebase" | unchanged |

## The rulings

Six arrangements had no slot the two earlier levels had already settled. Fleet's eleven and
Codebase's nine are not restated: the metric value at `--text-figure`, the panel name in the
furniture register carrying its own `h2`, the accepted collapse of `variant="grouping"`, the kept
`components/skeleton.tsx`, the untouched `fact-tile.tsx` and `fact-list.tsx`, and the refusal of a
`⋮` overflow menu all apply here unchanged. This level's rows have exactly one action each — a call
site opens its finding, an operation opens its binding surface — so the menu argument transfers
without amendment.

**1. This level takes no page-level `ControlBar`, and the chassis is complete without one.**
Codebase's ruling 1 says the chassis arrives with each level's port, and it is right that the
question be asked here. It was, and the answer is that the bar is already on this screen:
`VendorFindingsTable` has rendered a `ControlBar` holding severity, call-site path and ordering
since the filters landed. What a second, page-level bar could hold is the scope — and the scope is
already stated twice on this screen in better form, by the `FactList` beside the header and by the
paragraph beside that. A bar repeating "Repository scope" a third time is a fact written three
times, which is the failure mode `CLAUDE.md` names as the most expensive kind of debt because the
copies disagree silently.

The action slot is empty for a related reason rather than an oversight. The one candidate was
detector attribution, and `/detectors` takes a `repo_id` but not a vendor: an action offered from a
vendor's page that silently widened to every vendor would make a claim about scope the destination
does not honour. Fleet's own ruling for its action slot was that the link had to be one an operator
actually takes next; here there is no such link that keeps the scope the page is about.

What does change is placement. `PageHeader` moves out of a two-column grid and takes the full
width, which is where Fleet and Codebase both put it, and the scope paragraph pairs with the fact
list underneath — the same two-thirds-and-a-third arrangement Fleet uses for its rail and the
paragraph that qualifies it. The display step gets the whole measure instead of two thirds of it.

**2. Both panels stay full width, and this level pairs nothing.** Codebase paired its two narrow
panels and left its wide one alone. Here both panels are wide: the findings table is six columns
including a call-site path that a customer repository makes the widest cell on the screen, and the
changes table is six columns including a JSON pointer and a version pair. Halving either wraps
every row, and the findings table's own comment records that keeping the rung column on screen at
1280px was already a constraint at full width. The side-by-side placement this screen gains is the
prose beside the fact list, which is prose and a `dl` and reads well narrow.

**3. The "Vendor" row stays in the fact list, although the `h1` carries the same id.** Fleet's
ruling 2 — a count the rail already carries is never re-rendered at the figure register — is about
figures competing for one focal point, and it does not extend to this. The fact list makes a
two-axis statement: what this page is about, and what scope it is in. Removing one axis leaves
"Repository scope" as the scope of nothing named, and the argument the list exists to make is
exactly that the two axes are different — findings move with the repository and changes do not.

**4. The findings panel's metric is `severity_total`, not `total`.** The envelope carries both, and
they are different questions. `total` is the count the current filter matched and is already
asserted by the range in the footer bar; putting it at the figure register would render one count
twice and make the headline move every time a chip is clicked. `severity_total` is the count of
open findings for this vendor in this scope, before any narrowing — the panel's own grain, and the
figure this level has never rendered at all.

The footer bar's filtered-total caveat stays exactly as it is, and it now names a figure that is on
screen above it rather than one the reader has to take on trust. That the same number appears in
both places is not the duplication ruling 2 forbids: the figure states the grain, and the sentence
draws a contrast that only renders when a filter is on. Deleting the sentence would leave a
narrowed range with nothing saying what it was narrowed from.

**5. The vendor-changes panel carries no metric, because a count of those rows is not a
measurement — and the panel now says so.** This is the ruling this level exists to make.
`src/sync/graph/schema.sql:65-70` declares the grain of `vendor_change` and does not hedge: *"This
is the one source in the pipeline that does not converge… these rows are at-least-once and a count
of them is not a measurement."* `CLAUDE.md` carries the same exemption. Putting `page.total` at the
figure register would have been the console asserting, at its largest register, a number the
pipeline's own schema says is not one.

So the slot stays empty, and a second caption paragraph states in words what the empty slot cannot:
that the rows are recorded at least once rather than exactly once, and that the range under the
table is a fact about the page rather than about the vendor. The range itself stays — it is how a
reader knows which rows they are looking at and how to reach the rest — and the sentence is what
stops it being read as a total.

It goes in the caption rather than in the footer bar's `left` slot, which is where Codebase put its
comparable sentence, and the reason is Codebase's own ruling 7 read the other way round: `left`
does not render when the table is empty, and the branch that most needs this caveat is not the
empty one but every non-empty one. A caption renders on both.

**6. Each component owns its own panel, and both exports take the `Card` suffix.** `MetricPanel`
needs the figure and the caption, and the figure is in a payload the child component fetches — so
the panel is rendered where the query lives, which is what `OpenFindingsCard` and
`IndexCoverageCard` already do. `VendorFindingsTable` becomes `VendorFindingsCard` and
`VendorChangesTable` becomes `VendorChangesCard`, on the precedent of `features/fleet/runs-table.tsx`
exporting `RunsCard`: in this tree a file is named for what it holds and a component for what it
renders, and a component named `…Table` that renders a card is a name that lies.

The rename has a second benefit worth stating, because it was a real hazard. `VendorFindingsTable`
was two different components in two feature directories — this one, taking a vendor id, and
`features/fleet/vendor-distribution.tsx`'s, taking a list of vendors — and `open-findings-card.tsx`
imports the second. One name for two components is a mistake waiting for whoever edits both in one
session.
