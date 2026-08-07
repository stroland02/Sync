# Signals on the substrate — the mapping table, and the rulings it forced

Task 6 of `docs/superpowers/plans/2026-08-06-console-supabase-substrate.md`, third level. Work item
M7-W175.

Signals is `/repositories/:repoId/observed` — what this repository has attached to its graph, under
the three roles the M5 integration layer defines, and what each of them reported. It is the fourth
level ported, after Fleet (M7-W172), Codebase (M7-W173) and API Services (M7-W174).
`docs/superpowers/briefs/2026-08-07-substrate-fleet.md` is the parent document and its eleven
rulings bind wherever they generalise; Codebase adds nine and API Services seven. This file records
only what is new here, or what this level decided differently, and says which.

This port carries two extra obligations the earlier three did not.

**It owns `web/src/features/telemetry/` as well.** The Codebase port deferred those three tables in
its ruling 6, and named this work item as the one that inherits them: they still spell the old table
anatomy, so a column heading inside the telemetry panel is sentence-case while every heading around
it is uppercase. That is closed here.

**It carries the M7 plan's Phase 3 direction for this level.** The plan holds that a catalogue —
one card per integration, grouped by the three roles, with a role that has nothing attached saying
so in the same grid — is a better rendering of Signals than three stacked panels. The rulings below
say where that landed in full, where it landed partly, and what it was refused for.

The table was built by reading all seven files line by line, not from memory. Every rendered string,
every count, every state branch is a row.

## The mapping table

### `features/signals/roles.ts`

Nothing here renders. It is the roster the page and the panels both read, and
`tests/test_console_signals_roles.py` pins it to the specification's M5 table — the role names, the
relationship sentences, and that a role the header calls attached names a path the API actually
serves. **No semantics in this file change in this port.** It gains no field and loses none; the
restyle happens entirely in the files that consume it.

| Field rendered today | Substrate slot |
|---|---|
| `role` — the role name, spelled as the M5 table spells it | read by the role group's `h2` and by the roster sentence, both unchanged in source |
| `relationship` — that row's *Relationship to the graph*, verbatim | read by the role group's caption, unchanged |
| `source` — the read-surface path an attached role's panel asks | now read by the attachment chip as well as by the roster sentence — ruling 4 |
| `absence` — why an unattached role has nothing to query | `NotAttachedState` detail, unchanged |

### `features/signals/signals-page.tsx` — the page shell

| Field rendered today | Substrate slot |
|---|---|
| `UnknownRoute` when the URL carries no `repoId` | unchanged, before anything else renders |
| breadcrumb trail "Fleet" → repository id → "Signals" | `PageHeader` trail, `Breadcrumbs` unchanged |
| `h1` repository id, mono, at `--text-page` | `PageHeader` title, mono, at the display step — ruling 1 |
| — (the route's own question is not rendered today) | `PageHeader` question, read from `ROUTES` through `routeQuestion` — ruling 1 |
| — (no scope statement in the furniture register today) | **no `ControlBar`** — ruling 2 |
| intro paragraph: "Every integration attached to this repository's graph, grouped by the role it plays. One panel per role below, and a panel is not evidence that an integration stands behind it." | page body, left column of the intro band — reworded from "panel" to "card" only where the noun names the new rendering, ruling 3 |
| roster sentence: "Roles with an integration attached to this deployment: {names}." | page body, right column of the intro band, unchanged, still built from `ATTACHED_ROLES` |
| "…a panel with no rows in it is a quiet integration rather than a missing one." | same paragraph, unchanged in substance (protected: *attached and quiet* versus *nothing attached*) |
| "Roles with none: {names}. A role with nothing attached was never asked, because there is no adapter, no configuration table and no row here to ask — which is a different fact from an attached integration that was asked and had nothing to report." | same paragraph, unchanged, still rendered on `UNATTACHED_ROLES.length > 0` |
| `RoleSection` heading — `h2` at `--text-section`, the role name | role group `h2`, still `--text-section` — ruling 5 |
| `RoleSection` caption — the relationship sentence | role group caption, unchanged |
| — (nothing on screen today says, at a glance, which roles are attached) | attachment chip beside each role's name — ruling 4 |
| vendor role's body: `IndexCoverageCard` | the vendor catalogue, one card per vendor — ruling 6 |
| signal-source role's body: `SignalSourcePanel` | unchanged as a mount; its own three panels are recomposed below |
| human-surface role's body: `NotAttachedState` | unchanged as a mount, restyled onto the vendored `Card` — ruling 7 |
| the three role sections stacked full width | unchanged; each role groups its own cards — ruling 8 |

### `features/signals/not-attached-state.tsx`

| Field rendered today | Substrate slot |
|---|---|
| the bordered container, `rounded border border-border p-section` | vendored `Card`, so the plane, the radius and the hairline are the substrate's — ruling 7 |
| headline "No integration of this role is attached." | `CardHeader`, at `text-emphasis`, unchanged wording |
| — (the state carries no chip today) | the absence chip, `NOT ATTACHED`, beside the headline — ruling 4 |
| the `detail` prop — the role's `absence` sentence | `CardContent`, unchanged wording, still `max-w-prose` |
| the docstring's fifth-kind-of-nothing argument, carrying "still asking" | unchanged, verbatim (protected fragment) |

### `features/signals/attached-vendors.tsx` — new in this port

The vendor role's catalogue. Every field below is a field the level renders today through
`features/repositories/index-coverage-card.tsx`; nothing here is invented, and ruling 6 is why the
rendering moved rather than the component.

| Field rendered today (in `index-coverage-card.tsx`) | Substrate slot |
|---|---|
| `LoadingState`("index coverage for {repoId}") | unchanged, outside the catalogue |
| `ErrorState`(error, "index coverage for {repoId}") | unchanged, outside the catalogue |
| figure `total_call_sites` with "call site(s) indexed" | the group's caption, in words rather than at the figure register — ruling 6 |
| caption "A vendor absent from the table is not zero — it is a question this view cannot answer: whether the indexer looked and found nothing, or nothing declares which package to look for." | catalogue caption, unchanged (protected: absence apart from zero) |
| caption's second half, on a vendor link carrying this repository's scope | catalogue caption, unchanged |
| empty state "The index holds no call site for {repoId}." with its "nobody ever configured" detail | `EmptyState`, unchanged, where the grid would be |
| column Vendor, mono, as a link carrying `?repo_id=` | catalogue card's identifying line: the vendor id, mono, as the same link |
| column Call sites, mono | catalogue card's figure, at `--text-figure`, with its unit beside it |
| column Last indexed, `Formatted`/`formatTimestamp` | catalogue card's `LAST INDEXED` fact, furniture label over a mono value |
| the stale-response comment on `last_indexed?.[vendorId]` | unchanged — it states a constraint the code cannot show |
| "'Last indexed' is the newest indexing timestamp among that vendor's call sites — staleness, not a promise the index is current." | beneath the grid, unchanged (protected: staleness apart from liveness) |

### `features/telemetry/signal-source-panel.tsx`

| Field rendered today | Substrate slot |
|---|---|
| `LoadingState`("observed telemetry for {repoId}") | unchanged, outside the panels |
| `ErrorState`(error, "observed telemetry for {repoId}") | unchanged, outside the panels |
| `CardTitle` "Observed calls" | `MetricPanel` label `OBSERVED CALLS`, furniture register |
| — (no headline figure today) | `MetricPanel` metric: `calls.total` at the figure register — ruling 9 |
| description "One row per unit of work's use of one vendor operation. A row proves the call ran at least once; it does not prove the operation it names is the operation that was actually called — that is what the rung says." | `MetricPanel` caption, unchanged |
| `NothingRecorded`("observed calls") — the three-meanings sentence | `EmptyState`, wording carried across — ruling 10 |
| `ObservedCallsTable` | Studio anatomy through `components/data-table` — ruling 11 |
| `PageControls` under the calls table | `FooterBar`, no `left` — Codebase ruling 7 |
| `CardTitle` "Response shapes" | `MetricPanel` label `RESPONSE SHAPES` |
| — (no headline figure today) | `MetricPanel` metric: `shapes.total` — ruling 9 |
| description "What the operations this repository's own traffic names have actually been seen to return, joined in through those operations rather than stored per repository — a shape is a fact about the vendor, not about who calls it." | `MetricPanel` caption, unchanged |
| `NothingRecorded`("response shapes") | `EmptyState`, wording carried across — ruling 10 |
| `ObservedShapesTable` | Studio anatomy — ruling 11 |
| `PageControls` under the shapes table | `FooterBar`, no `left` |
| `CardTitle` "Error windows" | `MetricPanel` label `ERROR WINDOWS` |
| — (no headline figure today) | `MetricPanel` metric: `error_windows.total` — ruling 9 |
| description "How many times one operation failed, over a window an error tracker recorded. A count here has no denominator and is not a rate — it says nothing on its own about whether traffic is getting worse, only how many failures one window held." | `MetricPanel` caption, unchanged (protected fragment: "has no denominator") |
| `NothingRecorded`("error windows") | `EmptyState`, wording carried across — ruling 10 |
| `ErrorWindowsTable` | Studio anatomy — ruling 11 |
| `PageControls` under the error-windows table | `FooterBar`, no `left` |
| the docstring's no-composite-figure-and-no-chart argument, carrying "has no denominator" | unchanged, verbatim (protected fragment) |
| the docstring's note that `source` names the mechanism and never a vendor | unchanged — it is the ground for ruling 12 |

### `features/telemetry/observed-calls-table.tsx`

| Field rendered today | Substrate slot |
|---|---|
| column Rung, `RungBadge` on `binding_rung` | `data-table` column, first — never hidden, never coloured |
| column Operation, `vendor_id · operation_id` or the bare vendor when unresolved | `data-table` column, mono |
| column Method, mono uppercase, `orAbsent` | `data-table` column |
| column Trace, mono at `--text-meta` | `data-table` column |
| column Server, `orAbsent` | `data-table` column, mono |
| column URL template, `orAbsent` | `data-table` column, mono |
| column Calls, `call_count` | `data-table` column, mono |
| column Distinct targets | `data-table` column, mono |
| column Repeated | `data-table` column, mono |
| column Max resend | `data-table` column, mono |
| column Errors, `error_count` | `data-table` column, mono |
| column Observed, `first_seen` → `last_seen` | `data-table` column, mono at `--text-meta` |
| the row key built from trace, vendor, operation and index | unchanged |
| the docstring on `"observed"` versus `"unresolved"`, and the rung carrying the distinction rather than a colour | unchanged |

### `features/telemetry/observed-shapes-table.tsx`

| Field rendered today | Substrate slot |
|---|---|
| column Operation, `vendor_id · operation_id` | `data-table` column, mono |
| column Field, `field_path` | `data-table` column, mono |
| column Type, `json_type` | `data-table` column, mono |
| column Nullable seen, "yes"/"no" | `data-table` column — ruling 13 |
| column Enum values, joined, or `Absent` when the list is empty | `data-table` column, mono |
| column Source, `orAbsent` | `data-table` column |
| column Samples, `sample_count` | `data-table` column, mono |
| column Observed, `first_seen` → `last_seen` | `data-table` column, mono at `--text-meta` |
| — (a shape row carries no `binding_rung`) | **no rung column** — ruling 12 |
| the docstring on a shape being a vendor-wide fact joined in through this repository's own calls | unchanged |

### `features/telemetry/error-windows-table.tsx`

| Field rendered today | Substrate slot |
|---|---|
| column Rung, `RungBadge` on `binding_rung` | `data-table` column, first — never hidden, never coloured |
| column Operation, `vendor_id · operation_id` | `data-table` column, mono |
| column Status class, `orAbsent` | `data-table` column, mono — ruling 13 |
| column Source, the mechanism | `data-table` column |
| column Window, `window_start` → `window_end` | `data-table` column, mono at `--text-meta` |
| column Errors, `error_count` | `data-table` column, mono |
| column Issues, `issue_count` | `data-table` column, mono |
| the docstring carrying "has no denominator" and "no colour, no threshold" | unchanged, verbatim (protected fragment) |

## The rulings

Thirteen arrangements had no slot the three earlier levels had already settled. Fleet's eleven,
Codebase's nine and API Services' seven are not restated — the metric value at `--text-figure`, the
panel name in the furniture register carrying its own `h2`, the accepted collapse of
`variant="grouping"`, `--card-padding-x`, the kept `components/skeleton.tsx`, the untouched
`fact-tile.tsx`, and `data-table`'s `px-row`/`break-words` correction all apply here unchanged. So
does the refusal of a `⋮` overflow menu: every row on this level has at most one action, and most
have none at all, because a telemetry row is evidence rather than a destination.

**1. The chassis arrives with this port, because this level never had it.** Signals rendered a bare
`h1` at `--text-page` under a breadcrumb, with the route's question — *"What vendor, signal source
and human surface does this repository have attached, and what has each reported?"* — sitting unread
in `lib/routes.ts`. That is exactly the state Codebase was in before M7-W173, and its ruling 1
applies verbatim: each level takes the chassis as it is recomposed. `layouts/` is consumed, not
edited.

The question is worth rendering here more than on most levels, because it is the only sentence on
the screen that names all three roles in one breath, and it does so without the page file spelling
any of them — `routeQuestion` reads it out of the registry.
`test_the_page_reads_each_role_name_from_the_roster_rather_than_repeating_it` forbids a role name
appearing literally in `signals-page.tsx`, and reading the registry satisfies that rule rather than
evading it: the registry sentence and the roster are both single copies, and neither is written in
the page.

**2. No `ControlBar`, on API Services' argument rather than an oversight.** The one thing a bar could
carry here is the scope, and the scope is already stated three times on this screen in better
form: by the breadcrumb trail, by the mono `h1` naming the repository, and by the intro paragraph's
"attached to this repository's graph". A fourth copy is the failure mode `CLAUDE.md` names as the
most expensive kind of debt, because the copies disagree silently.

The action slot has no honest candidate either. The vendor cards each link to that vendor's page
carrying this repository's scope; the breadcrumb is the way back up to the codebase; `/detectors`
takes a `repo_id` but is Codebase's own inline link, argued inside a sentence there. Codebase's
ruling 2 — a destination is named once — cuts against inventing a second naming here.

**3. "One panel per role" becomes "one card per role's integrations", and only where the noun names
the rendering.** The intro paragraph's second sentence said *"One panel per role below, and a panel
is not evidence that an integration stands behind it."* After this port the vendor role renders a
card per vendor rather than one panel, so the noun would be wrong. The claim is untouched — what the
sentence protects is that **drawing a container is not evidence an integration exists**, and it now
reads "one card per integration below, grouped by the role it plays, and a card is not evidence that
an integration stands behind it."

This is a rewording of an honesty sentence and therefore worth being explicit about. It is not a
shortening: the sentence is the same length, makes the same claim, and the claim now matches what is
actually on screen. The alternative — keeping the word "panel" over a grid of cards — would be a
sentence describing a screen that no longer exists, which is the drift the protected-sentence rule
exists to stop, arrived at from the other direction.

**4. Each role carries an attachment chip, and it is the absence channel rather than a status
light.** `.claude/rules/console-surface.md` permits exactly three closed vocabularies to be a badge
— run outcome, error state, and absence — and requires the badge be legible without its colour.
`ATTACHED` and `NOT ATTACHED` is the absence vocabulary, it has two members, it is derived from
`role.source !== null` in `roles.ts`, and it is drawn monochrome in the same recipe `RungBadge`
already uses: `furniture`, a hairline border, no fill, no hue.

**No dot and no pulse, and this is the level where that refusal has to be said out loud**, because
this is the screen a control plane would put a green dot on. A dot would claim a lifecycle state
this data does not hold. `ATTACHED` is a fact about configuration, permanently true for as long as
the adapter exists, and it says nothing whatever about whether the integration reported anything
recently — which is the claim a dot makes and cannot support here. A source that has not reported is
rendered as the sentence it already has: the empty state's three meanings, none of them picked.

The chip and the roster sentence are one derivation rendered twice, and that is not the duplication
`CLAUDE.md` forbids. They cannot disagree — both read `source` from the same constant — and they do
different jobs: the chip is scanned beside the role it belongs to, and the sentence carries the
*why*, which no chip can. Removing the sentence to keep only the chip would be exactly the
collapse-into-an-icon the rule forbids.

**5. A role heading stays at `--text-section` while the panels under it take the furniture
register.** Fleet's ruling 11 moved *panel names* to the furniture register, and every panel on this
screen follows it. A role group is one level above a panel — it contains panels — so leaving it at
`--text-section` is what keeps a visible step between "the role" and "what the role reported".
Putting the role name in the furniture register too would render a container and its contents at
one weight, which is the flatness the substrate ports exist to undo.

The outline is a separate decision and is unchanged: a role group is `h2`, and `MetricPanel` writes
`h2` as well, so the two sit on one outline level. That predates this port — `RoleSection` and
`IndexCoverageCard` already both emitted `h2` — and fixing it means changing `metric-panel.tsx`,
which every ported level renders through. Not this work item's file, and not worth touching for a
level that is not the only one affected.

**6. The vendor role becomes a catalogue built here, and this level stops mounting
`IndexCoverageCard`.** This is the ruling the Phase 3 direction forced, and the one with a real
cost, so both sides are written down.

The direction is that one card per integration, grouped by role, is a better rendering of this level
than stacked panels. For the vendor role the integrations are the vendors this repository's code
calls, and `index_coverage.by_vendor` is a complete, deployment-scoped answer — not a page — so a
card per vendor is a catalogue that can be drawn honestly. A three-column table of vendor rows is
not that.

`features/repositories/index-coverage-card.tsx` cannot be restyled into one: it is another level's
file, it is Codebase's own panel, and Codebase's ruling 9 turns on it carrying the call-site figure
for both screens. So the rendering moves and the component stays, which means one query has two
renderings — the thing that component's docstring was written to prevent.

Accepted, with the reasons the docstring's argument does not cover this case. The two renderings
share the payload type and the seam (`useRepositoryCoverage`), and neither computes anything: one
sorts `by_vendor` by name into rows, the other sorts it into cards. What could drift is wording, and
the wording that matters is the two protected sentences — "a vendor absent from the table is not
zero" and "staleness, not a promise the index is current" — which are reproduced here in full rather
than paraphrased. What was actually being protected was a *derivation* existing twice, and there is
no derivation here to duplicate.

Two consequences, both deliberate:

- **The `total_call_sites` figure does not appear at the figure register on this screen any more.**
  Each vendor card carries its own count at that register, and the group caption states the total in
  words. Fleet's ruling 2 is the reason: a figure that is the sum of the figures on the cards
  directly beneath it is one fact at two weights, and the one that stays is the one an operator
  reaches first — which, in a catalogue, is the card.
- **`index-coverage-card.tsx`'s docstring names Signals as a caller and no longer has one.** Its
  first paragraph is corrected in this commit, and nothing else in that file is touched — no class,
  no element, no export. Leaving a docstring that describes a mounting which does not exist is the
  silent-disagreement failure `CLAUDE.md` puts first among the five, and it costs two sentences to
  avoid. The untouchable is against restyling another level, not against keeping its prose true.

**7. `NotAttachedState` moves onto the vendored `Card` and keeps every word.** It drew its own
`rounded border border-border p-section` box, which is a second set of values for the plane the
substrate already declares. On the vendored `Card` it renders at the same depth, radius and hairline
as every other card on the screen — which is the point, because the argument the component exists to
make is that *nothing attached* belongs in the catalogue rather than beside it. A role with nothing
attached that is drawn as loose prose under three carded roles reads as an afterthought; drawn as a
card, it reads as an answer.

It is not `EmptyState` and must not become one, for the reason its own docstring gives and
`test_the_level_draws_an_unattached_role_with_the_state_written_for_it` holds: `EmptyState` means
the API answered and the answer was nothing. Nothing answered here, because nothing was asked.

**8. The three role groups stay stacked, and the grid is inside a role rather than across all
three.** The direction asks for the roles to be a grid; measured against what each role actually
holds, they cannot be columns of one. The vendor role's cards are small. The signal-source role's
three panels each carry a table of seven to twelve columns, and API Services' ruling 2 already
settled what happens to a six-column table at a third of the width. The human-surface role is one
card of prose.

So the grouping is delivered as it can be delivered honestly: each role is a titled group with its
own chip and its own caption, and inside the group its integrations are a grid — one card per vendor
for the vendor role, one card for the human-surface role at the same width so it sits in the same
rhythm as its peers rather than as a full-bleed block at the foot of the screen. The signal-source
role's three panels stay full width and stay stacked, and the reason is a measurement rather than a
preference.

The screen's horizontal placements are therefore: the intro band, which pairs the catalogue sentence
with the roster sentence; and the vendor grid, which is two or three cards abreast. Before this port
the level had none.

**9. Each telemetry panel carries its own total at the figure register.** Codebase's ruling 4 gave
its telemetry panel no metric, and the reason was that *one* panel held three totals with no shared
denominator. Here each source is its own panel, so each has exactly one total and that total is the
panel's own grain — which is the case `metric-panel.tsx` was written for.

The `FooterBar` range beneath the table asserts the same number, and API Services' ruling 4 already
settled that this is not the duplication Fleet's ruling 2 forbids: the range is a fact about the
page ("1–2 of 2"), the figure is the count the panel is about, and the two say different things the
moment a table has more than one page.

**The zero case takes no metric.** A panel with `0` at the figure register would render an absence as
a measured zero, which is the distinction this console draws four times over. When a total is zero
the metric is omitted and the empty state's three-meanings sentence is the whole answer.

**10. `NothingRecorded` becomes `EmptyState`, carrying its sentence verbatim.** The component was a
bare paragraph doing `EmptyState`'s job with better words, and the words are the part worth keeping:
*"That could mean the relevant code path has never run since telemetry started, that telemetry was
never wired up for this repository, or that this identifier does not name a repository the index has
seen at all — this payload answers the same way in all three cases, so nothing here picks one."*
That moves across unchanged as the detail, under a headline naming which of the three things is
missing.

One thing is lost and it is worth naming rather than discovering: `EmptyState` takes strings, so the
repository id inside the headline is no longer set in mono. That is the same trade the Codebase
level already made for the same three empty states, and the alternative is a second empty-state
component whose only difference is a `<span>`.

**11. `features/telemetry/`'s three tables take the Studio anatomy, closing Codebase's ruling 6.**
The import moves from `@/components/ui/table` to `@/components/data-table` and nothing else in any
of the three changes: same columns, same order, same formatters, same row keys. That is the whole
fix, and it is the whole reason the anatomy is one file. The visible consequence is that a column
heading inside the telemetry panel is now uppercase and open-tracked like every other heading in the
console — including on the Codebase screen, which mounts all three tables and gets the correction
without being edited.

**12. No rung column is invented for the shapes table, and no signal-source catalogue is derived
from `source`.** Two refusals with one root: the console renders what the row carries.

`ObservedShapeRow` has no `binding_rung`. The other two telemetry rows do, and both keep it in the
first column, monochrome and never hidden — the graph-grain rule as it applies to this level. A
shape is a vendor-wide fact joined in through the operations this repository's own calls name, so
the rung that would attach to it is the rung of a call somewhere else in the payload. Rendering one
would be attributing a row to a binding it does not hold.

The more tempting refusal is the second. The signal-source role's genuine integrations are the
mechanisms `source` names — `interceptor`, `error-payload`, `replay` — and a catalogue card per
mechanism would be the truest reading of the direction on this screen. It is refused on two grounds,
either of which is sufficient. `observed_call` carries no `source` at all, so a catalogue built from
shapes and error windows would silently imply the calls came from nowhere. And the rows on screen
are one page of each table, so a set of distinct sources derived from them is a fact about the page
rather than about the deployment — a claim of the shape this console exists to refuse. It becomes
available when the payload carries the source roll-up; until then the role's integrations are its
three panels, named for what they hold.

**13. A closed vocabulary is not automatically a chip.** `nullable_seen` renders "yes"/"no" and
`status_class` renders values like `5xx`; both are closed sets, and neither becomes a badge.
`console-surface.md` permits three vocabularies to carry a claim as a badge — run outcome, error
state, absence — and permits is not requires. A badge earns its weight by being scanned across rows;
inside a twelve-column and an eight-column table it would add a border and a fill to a cell whose
value is already one short mono token, and it would put two of the three permitted channels on
values that are neither a verdict nor a state transition. `status_class` in particular is a
classification of a response code, not the error state the rule means. Both stay as text.
