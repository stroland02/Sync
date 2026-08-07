# The Binding surface on the substrate — the mapping table, and the rulings it forced

Task 6 of `docs/superpowers/plans/2026-08-06-console-supabase-substrate.md`, fourth level. Work
item M7-W176.

The Binding surface is `/bindings/vendors/:vendorId/operations/:operationId` — one vendor
operation, every call site the index binds to it, and what the vendor changed about it. It is the
fifth level ported, after Fleet (M7-W172), Codebase (M7-W173), API Services (M7-W174) and Signals
(M7-W175). `docs/superpowers/briefs/2026-08-07-substrate-fleet.md` is the parent document and its
eleven rulings bind wherever they generalise; Codebase adds nine, API Services seven and Signals
thirteen. This file records only what is new here, or what this level decided differently, and says
which.

Two things make this port different from the four before it.

**This level is the join, so it is the one screen where the substrate's card vocabulary is
expensive.** Every other level ported has put its regions inside the vendored `Card`. Here the
call-site table is the console's densest object — nine columns over a set that reaches 2,500 rows
in the scale fixture — and the horizontal room a card takes is measured below at twenty pixels of
row height, on every row. The port therefore spends the substrate somewhere else, and ruling 1 is
the measurement that decided it.

**The detail drawer arrives with this level**, per the substrate plan's Task 6 (*"Detail drawers
(vendored `sheet`, URL-addressable) arrive with the level that owns the detail — Finding and
Binding surface first"*) and the M7 plan's Phase 5 (*"One binding, drawn"*). It is the first URL
state on this console that is neither a filter nor a page position, and rulings 5 through 10 are
what that cost.

The table below was built by reading `binding-surface-page.tsx` line by line, not from memory.
Every rendered string, every count, every state branch is a row.

## The mapping table

### `binding-surface-page.tsx` — the page shell

| Field rendered today | Substrate slot |
|---|---|
| `UnknownRoute` when the URL carries no `vendorId` or `operationId` | unchanged, before anything else renders |
| breadcrumb trail "Fleet" → vendor id → operation id | `PageHeader` trail, `Breadcrumbs` unchanged |
| `h1` `{vendor} / {operation}`, mono, at the display step | `PageHeader` title, unchanged |
| the route's own question, read from `ROUTES` | `PageHeader` question, unchanged |
| the header and `FactList` paired at `lg` in one band | unchanged — API Services ruling 1 settled this arrangement and nothing here contradicts it |
| `LoadingState`("bindings for {vendor}/{operation}") | unchanged, outside both sections |
| `ErrorState`(error, "bindings for {vendor}/{operation}") | unchanged, outside both sections |
| the two sections stacked full width, no card around either | unchanged — ruling 1 |

### `operationFacts` — the fact list beside the header

| Field rendered today | Substrate slot |
|---|---|
| fact "Vendor" → the vendor id, mono | `FactList`, unchanged |
| fact "Operation" → the operation id, mono | `FactList`, unchanged |
| fact "Repository scope" → the repository id, or "Every repository the index has seen" | `FactList`, unchanged |
| fact "Call sites bound" → `boundCallSites`, the sum over the facet's own scope | `FactList`, unchanged |
| fact "Repositories" → `repositories.length` | `FactList`, unchanged |
| fact "Vendor changes" → `changes.total` | `FactList`, unchanged — and it does not become a figure, ruling 1 |
| fact "Binding rung" → `RungBadge` at `static`, hardcoded because the payload hardcodes it | `FactList`, unchanged |
| per counted fact: `Skeleton` while pending | unchanged — Fleet ruling 6 keeps `components/skeleton.tsx` |
| per counted fact: `<Absent>`("the API did not answer") on failure | unchanged |

### `ScopeNote`

| Field rendered today | Substrate slot |
|---|---|
| "The call-site table below is scoped to {repoId}." when a scope is set | page body, beside the fact list, unchanged |
| "The counts beside this are taken across every repository the index has seen… the choices available, not the rows on screen. The range under the table is the number that moves when a filter is set." | same paragraph, unchanged |

### `SharedDirectoryNote`

| Field rendered today | Substrate slot |
|---|---|
| the truthiness guard against a half-formed sentence, and its comment | unchanged — it states a constraint the code cannot show |
| "Every call site below is under {directory}, so the call-site column carries what follows it. The whole path is that prefix and the cell together — nothing here is shortened away." | above the table, unchanged in wording and position |
| the docstring's measurement of the path column, and why the note is not in `FooterBar`'s `left` | unchanged |

### `RungNote` — the page-level rung, in prose

| Field rendered today | Substrate slot |
|---|---|
| filtered-and-empty: "No call site carries a rung under this filter. That is a fact about the filter and not about the operation…" | beneath the table, unchanged |
| unfiltered-and-empty: "No call site carries a rung here, because none is bound to this operation…" | unchanged |
| the standing sentence: "Every call site below rests on the `static` rung… A stronger rung for this same operation — traffic Sync has actually observed calling it — is a separate kind of evidence on the repository's own coverage page, never blended into this row." | unchanged |
| the docstring's argument for prose over `ProvenanceStrip` | unchanged |

### `CallSitesEmptyState` — three kinds of nothing

| Field rendered today | Substrate slot |
|---|---|
| past-the-end: "This page is past the end of the N call sites that match." with its offset detail | `EmptyState`, unchanged |
| filter-matched-nothing: "No call site matches this filter." with the bound count and "what the filter excluded and not what the index is missing" | `EmptyState`, unchanged |
| nothing-bound, unscoped: "…Either nothing in any indexed repository calls this operation, or nothing indexed does — the index cannot tell the two apart." | `EmptyState`, unchanged (protected) |
| nothing-bound, scoped: "…Either nothing in this repository calls the operation, or this repository has not been indexed at all — the index cannot tell the two apart." | `EmptyState`, unchanged (protected) |

### The call-sites section

| Field rendered today | Substrate slot |
|---|---|
| `h2` "Call sites" at `--text-section` | unchanged, still `--text-section` — ruling 3 |
| "What in the codebase calls this operation, and how the system knows it does." | section caption, unchanged |
| `ControlBar` holding the two narrowing controls | unchanged |
| `FacetChips` legend "Repository", `allLabel` "Every repository", with per-option counts | unchanged |
| `FacetChips` `countScope`: "Counted over every call site the index holds on this operation, not over the table below…" | unchanged |
| `PrefixFilter` legend "Call site path", placeholder `src/billing/` | unchanged |
| `PrefixFilter` note: "Matched as a prefix… never as a substring. It narrows the call sites only: a vendor change has no position in your codebase…" | unchanged |
| `ActiveFilters` "Narrowed by …" and "Clear all filters" | unchanged |
| column Repository, mono | `components/data-table` column, mono — now second, ruling 4 |
| column Call site, `pathAfter(common, path)`:line:col, mono | `data-table` **identifying column**, now the control that opens the drawer — ruling 5 |
| column Symbol, `orAbsent` | `data-table` column, mono |
| column SDK version, `orAbsent` | `data-table` column, mono |
| column Argument keys, `joinOrAbsent` | `data-table` column, mono |
| column Response fields read, `joinOrAbsent` | `data-table` column, mono |
| column Loop depth, the integer | `data-table` column, mono |
| column Rung, `RungBadge` on `binding_rung` | `data-table` column, **first** — never hidden, never coloured, ruling 4 |
| column Indexed at, `formatTimestamp` | `data-table` column, mono at `--text-meta` |
| the row key built from repo, path, line and column | unchanged — and it is now also the drawer's key, ruling 6 |
| `FooterBar` with the never-had-one-versus-retracted sentence in `left` | unchanged (protected: "cannot tell the two apart") |

### The vendor-changes section

| Field rendered today | Substrate slot |
|---|---|
| `h2` "Vendor changes" at `--text-section` | unchanged, still `--text-section` — ruling 3 |
| "What the vendor changed about this operation, whether or not a call site above is affected. A vendor change is not a binding and carries no rung — it is evidence about the vendor, not about the codebase." | section caption, unchanged |
| empty state "The vendor has never changed this operation." with "that is an answer, not a failure" | `EmptyState`, unchanged |
| column Detected, `formatTimestamp` | `data-table` column, mono at `--text-meta` |
| column Kind | `data-table` column |
| column Severity | `data-table` column |
| column Path, `orAbsent` on the JSON pointer | `data-table` column, mono |
| column Versions, `from` → `to`, both `orAbsent` | `data-table` column, mono |
| `FooterBar`, no `left` | unchanged |
| — (nothing on screen says a count of these rows is not a measurement) | **still nothing at the figure register** — API Services ruling 5 applies unchanged, ruling 1 |

### `binding-selection.ts` — new in this port

Nothing here renders. It is the derivation the drawer's URL state rests on, and it is tested before
it exists.

| What it answers | Where it lands |
|---|---|
| the search parameter the drawer's open state is spelled with | `BINDING_KEY`, read and written through `useFilterParam` — ruling 5 |
| a call site's own key, as the URL spells it | `bindingKey(site)` — repository, path, line and column, the natural key the row key already uses — ruling 6 |
| whether the URL names a call site, and whether this page holds it | `selectBinding(key, sites)` → `none` / `resolved` / `unresolved` — ruling 7 |

### `binding-drawer.tsx` — new in this port

One binding, drawn. Every field below is a field the level already renders in a table cell; nothing
here is invented, and ruling 8 is why one binding may be drawn where a fleet of them may not.

| Field | Slot |
|---|---|
| the sheet itself, right side, over the dimmed list | vendored `sheet`, `side="right"`, overlay on — ruling 11 |
| `SheetTitle` — the call site's `path:line:col`, mono | drawer header |
| `SheetDescription` — what the drawing is, and that it is one binding rather than a diagram | drawer header — ruling 8 |
| the call-site card: repository, full path, line, column, symbol, SDK version, argument keys, response fields read, loop depth, indexed at | vendored `Card` over `FactList` — ruling 13 |
| the edge from the call site to the operation, carrying that row's own `binding_rung` and `describeRung`'s words | the edge between the first and second card — ruling 9 |
| the operation card: vendor id and operation id, both mono, the vendor as a link carrying the scope | vendored `Card` |
| the edge from the vendor change to the operation, carrying that there is no rung and why | the edge between the second and third card — ruling 9 |
| the change cards: kind, severity, versions, JSON pointer, detected at | vendored `Card` each |
| the change section's empty state, when the vendor has never changed this operation | `EmptyState`, the same sentence the table below already uses |
| the sentence naming what the drawer's changes are counted over, when the table is paged | beneath the change cards — ruling 10 |
| the unresolved state: the URL names a call site this page does not hold | its own panel, with what to do about it — ruling 7 |

## The rulings

Thirteen arrangements had no slot the four earlier levels had already settled. Their forty rulings
are not restated: the metric value at `--text-figure`, the accepted collapse of
`variant="grouping"`, `--card-padding-x`, the kept `components/skeleton.tsx`, the untouched
`fact-tile.tsx` and `fact-list.tsx`, `data-table`'s `px-row`/`break-words` correction, and the
refusal of a `⋮` overflow menu all apply here unchanged. On the last of those, this level's answer
is the same as every level before it and now has a drawer to test it against: a call-site row has
exactly one action — open its detail — and a menu whose only entry duplicates the row's own control
is furniture claiming a choice nobody has.

**1. Neither table goes inside a `MetricPanel`, and the reason is a measured cliff sixteen pixels
wide.** This is the ruling this level exists to make, and it is the first time the substrate has
been refused on a number rather than accommodated.

The vendored `Card` spells `px-(--card-padding-x)`, wired in Task 5 to `--spacing-section`, so a
panel costs its contents 32px of horizontal room. Measured in Chrome at 1440x900 against
`/bindings/vendors/seed-console-scale-stripe/operations/PostCharges`, the 2,500-row scale fixture,
with the container narrowed by hand and the rows re-read:

| Table width | Body row height |
|---|---|
| 1097px (today) | **56px** |
| 1081px (−16) | 76px |
| 1065px (−32, what a card costs) | 76px |
| 1049px (−48) | 76px |

Twenty pixels a row, 36% taller, on every row of a table that reaches 2,500. `B115` recorded the
same cliff before the substrate existed and the file's own docstring carries it; this re-measures
it on the ported anatomy and finds it sharper than recorded — the cliff is between 1081 and 1097,
so a card does not merely cost the rows, it clears the edge by 16px with nothing to spare.

The changes table is five columns and would fit in a card comfortably. It does not get one anyway,
and that is deliberate rather than an oversight: one ringed panel beside one bare table on a screen
that is **one subject** would draw a grouping claim across a boundary that is not there. The
docstring already says what separates the two regions — their headings, and the rule each footer
bar draws under itself — and that is still true after the port.

The consequence for the figure register is that this level renders no metric at all, and every
candidate was already refused for its own reason. `call_sites.total` is the count the current
filter matched and is asserted by the footer bar's range (API Services ruling 4). `boundCallSites`
is the facet's denominator and is in the fact list, where `ScopeNote` explains why it disagrees with
the range — moving it to the figure register would put the two numbers at different weights and
invite exactly the reading that sentence exists to prevent. `changes.total` is a count of
`vendor_change` rows, which the pipeline's own schema says is not a measurement (API Services
ruling 5).

**2. The substrate's card vocabulary lands in the drawer instead, and that is where it belongs on
this level anyway.** A drawer is not competing for a row's height: it opens over the list at half
the viewport, holds one binding, and has room the table does not. So the vendored `Card` is what the
drawing is composed from — one card per node, the edges between them — and the level gets the
substrate's plane, radius and hairline in the one place where paying 32px buys something.

Stated rather than left implicit because it is the answer to the obvious objection: this port does
not skip the substrate, it spends it where the measurement says it is affordable.

**3. Both section headings stay at `--text-section` rather than moving to the furniture register.**
Fleet's ruling 11 moved *panel names* to the furniture register, and every ported level has
followed it. It does not reach here, for the reason ruling 1 produced: with no card around either
region, the `h2` is the only thing separating them. Dropping it from 18px to 12px uppercase would
take the screen's one structural separator and make it lighter than the sentence beneath it, on a
screen that has no ring to fall back on.

Signals' ruling 5 is the same argument from the other side — a heading one level above its contents
keeps a step — and the two together give the shape: **the furniture register is a panel's name, not
a section's.** Where the substrate supplies the container, the name may go light; where it does not,
the name is the container.

**4. The rung moves to the first column.** It was eighth of nine. `vendor-findings-table.tsx`
carries the argument in the comment whose fragment `tests/test_console_honesty_sentences.py` pins
as "sideways scroll": the rung sits ahead of the call site because the call site is the widest cell
in the table and no fixture here is long enough to prove that on its own. Both telemetry tables
that carry a rung do the same. This table is nine columns and the widest of the three, so it is the
last one that should have been the exception.

Neither width clips today — measured at 1097 of 1097 at 1440 and 937 of 937 at 1280 — because the
cells wrap rather than overflow. That is the argument for moving it, not against: a column that is
safe only because nothing has yet been long enough is a column protected by the fixture rather than
by the layout.

**The identifying column is therefore second, and that is a departure from Studio's anatomy taken
on the console's own rule.** The plan's Step 2 says "identifying column as a link"; it does not say
where. `.claude/rules/console-surface.md` says the rung is never a hideable column, and a column
behind a sideways scroll is hidden in the only sense that matters.

**5. The drawer's open state is a search parameter on the existing route, and `useFilterParam` is
what writes it.** `lib/routes.ts` is not touched: `GRAPH_LEVELS` and the registry shape are pinned
by `tests/test_console_hierarchy.py` and `routes.test.tsx`, and a drawer is not a level. A path
segment would also make the drawer a destination the rail and the command palette would have to
have an opinion about, which is three files of consequence for a panel.

`useFilterParam(BINDING_KEY)` already has both properties the mechanism note's §4 names as the ones
worth taking from Studio's `UserPanel`. It writes through `setSearchParams`, which pushes rather
than replaces — so **Back closes the drawer** — and it spells the closed state as the parameter's
absence rather than as an empty value, so a screen with nothing selected has one canonical URL.
That is `clearOnDefault` reached by a different route, and reusing the existing seam rather than
adding a hook is what keeps the two from drifting.

**It passes no `resets`, and that distinguishes it from every other parameter on this screen.**
Opening a detail does not change which rows exist, so the page position measured against them is
still valid. The two filters reset the call-site offset because they change the set; this does not.

**6. The drawer's key is the call site's natural key, and it is compared rather than parsed.**
`BindingCallSite` carries no id — a call site is identified by repository, path, line and column,
which is exactly the row key the table already builds. `bindingKey` joins those four with a colon
and **nothing ever splits the result**: `selectBinding` computes the key for each row and compares
strings. A customer path may hold a colon, and a parser would resolve `a:b.ts:1:2` to the wrong row
or to none; a comparison cannot.

This is the shape `.claude/rules/console-dev-loop.md` calls a rule about the rendered view: a
viewport is not in the payload, and neither is which row a reader clicked. It is tested here, and
the colliding-path case is one of the tests.

**7. A URL naming a call site this page does not hold is its own state, and the drawer says so
rather than closing.** This is the fifth kind of nothing, and it is new — the four `states.tsx`
names are about what the API answered, and this one is about what the URL asked for.

A binding URL is shareable, which is most of why it is in the URL at all. The reader who opens one
may be at a different page position, or under a filter the sender did not have, or looking at a
repository scope that excludes the row. Silently rendering the list with no drawer would tell them
the link was wrong. Rendering an empty drawer would tell them the call site was gone. Both are
false, and the true answer is that **this page does not hold it** — so the drawer opens, names the
key it was given, and says that clearing the filters or returning to the first page is where to
look. Nothing here asks the API for the row: the payload is a page, and a second request keyed on a
URL fragment is a route this level does not have.

**8. The drawing is cards and edges, and Task 11's cardinality refusal is not reopened.** The M7
plan's Phase 5 asks for "one binding, drawn" and says in the same breath that the refusal of a
fleet-wide bipartite diagram stands. The two are consistent, and the reason is worth writing down
because a reader meeting the drawer will ask.

A diagram of thousands of call sites against an operation is refused because it cannot be read: the
cardinality statement `features/fleet/cardinality.tsx` already renders is the honest rendering of a
set that large. A drawing of **one** binding has cardinality one at every node, so nothing is
elided, nothing is sampled, and there is no threshold at which it stops being true. It is the
counter-example rather than the exception.

It is composed cards with the relationship stated in words between them — no canvas, no SVG
plotting, no graph library, and **no new dependency**. The vendored `Card` and a line of prose per
edge is the whole mechanism, which is also why it survives at any width the drawer takes.

**9. Each edge states its rung, and the change edge states that it has none.** The call site → the
operation is a binding, so that edge carries that row's own `binding_rung` through `RungBadge` and
`describeRung`, consumed from `components/provenance.tsx` and never re-derived. The vendor change →
the operation is not a binding, and the section caption on the screen behind the drawer already
says why: *"A vendor change is not a binding and carries no rung — it is evidence about the vendor,
not about the codebase."*

Leaving that second edge bare would be the cheaper option and it is wrong. An edge with a rung
beside an edge with nothing reads as a missing value; an edge that says it has no rung, and why,
reads as the distinction it is. This is the same rule `bindingNullLabel` enforces one level up —
null is a fact, and it differs per place.

**10. The drawer names the changes this page holds, and says so when the page is not the whole
set.** `changes` is an `ItemPage`, and the drawer draws from the items the current page carries.
When `changes.total` exceeds what is on that page, a count read off the drawer would be a fact about
the page wearing the clothes of a fact about the operation — the failure Signals' ruling 12 refused
a whole catalogue over. So the sentence beneath the change cards names both numbers when they
differ and says which is which, and says nothing when they agree.

**11. The sheet's entry transition is permitted, and nothing on this screen animates at rest.**
`test_no_keyframes_or_animation_shorthand_outside_the_component_catalog` scans `features/`,
`layouts/`, `components/` (less `components/ui/`), `api/` and `lib/`, and its own failure message
states the boundary: *"every keyframe measured across four references is an overlay entering or
leaving, or something loading."* A sheet sliding in is an overlay entering. The classes live in
`web/src/vendor/supabase/ui/sheet.tsx`, which that guard does not scan and which this port consumes
unedited; `features/bindings/` spells no `animate-*` class of its own, so the guard would catch it
if a later change tried to.

**12. The drawer is modal, and the inline panel Studio uses for the same job is refused here.** The
mechanism note's §4 reads two patterns and prefers the second: a resizable panel beside the list, so
the list stays readable and the reader keeps their scroll position. That preference does not
survive contact with ruling 1. A panel beside this table takes a third of its width permanently,
and the table falls off the 1097px cliff the moment it opens — the whole list re-wraps to 76px rows
behind a panel that exists to keep the list readable.

So the modal sheet is the pattern, with the URL discipline of the inline one. `SKILL.md`'s
precondition quoted in that note is satisfied on the same reading: a sheet is for when switching
pages would be disruptive and the reader needs to keep their context, which is precisely a reader
comparing one call site against the forty-nine around it.

**13. `FactList` is reused inside the drawer rather than a second key/value component.** Its own
docstring names the case — several facts about one subject, label left, value right, scannable
without reading — and its widest label was sized for *this* level's "Response fields read". A card
holding a `<dl>` is the arrangement it was built for, and building a second one for the drawer would
be the fact-written-twice defect in component form.
