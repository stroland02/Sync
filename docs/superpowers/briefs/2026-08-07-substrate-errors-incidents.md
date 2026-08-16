# Errors & Incidents on the substrate — the mapping table, and the rulings it forced

Task 6 of `docs/superpowers/plans/2026-08-06-console-supabase-substrate.md`, fifth level. Work item
M7-W177.

Errors & Incidents is `/detectors` — which detector raised how many open findings, at which rungs,
with what claims and severities. It is the sixth level ported, after Fleet (M7-W172), Codebase
(M7-W173), API Services (M7-W174), Signals (M7-W175) and the Binding surface (M7-W176).
`docs/superpowers/briefs/2026-08-07-substrate-fleet.md` is the parent document and its eleven
rulings bind wherever they generalise; Codebase adds nine, API Services seven, Signals thirteen and
the Binding surface thirteen. This file records only what is new here, or what this level decided
differently, and says which.

`.claude/rules/console-hierarchy.md` is worth restating before the table, because it changes how one
row below reads: **this screen is not a level.** The specification files detector attribution as an
aggregate *over* Errors & Incidents (`:445`), in the same relation the vendor roll-up has to API
Services, and `lib/routes.ts` carries the `Errors & Incidents` level on the route rather than
inventing one. So the screen has no child to link down to and no sibling to switch between, and two
of the rulings below are consequences of that rather than of the substrate.

Two things make this port different from the five before it.

**It is the level the M7 plan names as the faceted explorer**, alongside Signals — *"a facet
sidebar with counts per value — `Edge Function 0` rendered, not suppressed — a volume histogram
aligned over the result set, and a dense monospace table beneath"*. Ruling 3 is where that landed,
and it landed as a rendering rather than as a control, for a reason that is about this level's API
rather than about the direction.

**It is the first ported level whose evidence is a chart rather than a table.** The rung-composition
chart's derivation is untouchable in this work item by construction — `rung-series.ts` is the data
seam and `rung-composition-option.ts` is the chart derivation, both with their own tests — so what
this port has to give is placement: the chart becomes a metric panel's evidence, beneath the figure
it decomposes.

The table below was built by reading all three files line by line, not from memory. Every rendered
string, every count, every state branch is a row.

## The mapping table

### `detectors-page.tsx` — the page shell

| Field rendered today | Substrate slot |
|---|---|
| breadcrumb trail "Fleet" → "Detectors", or "Fleet" → repository id → "Detectors" | `PageHeader` trail, `Breadcrumbs` unchanged, both branches unchanged |
| `h1` "Detectors" at `--text-page` | `PageHeader` title at the display step — ruling 1 |
| — (the route's own question is not rendered today) | `PageHeader` question, read from `ROUTES` through `routeQuestion` — ruling 1 |
| — (no scope statement in the furniture register today) | `ControlBar` left slot: `SCOPE` over the repository id, or over "Every repository the index has seen." — ruling 2 |
| — (no primary action today) | **no `ControlBar` action** — ruling 2 |
| paragraph: "Every detector's open findings, broken down by the rung of evidence behind its claims. The rung breakdown is the substance: a detector whose findings rest entirely on `static` evidence is making a different kind of claim from one correlating watched traffic, and an operator weighing a false positive needs that difference before weighing anything else." | intro band, left column, unchanged |
| paragraph: "This is not a leaderboard and carries no precision or accuracy figure: detectors are not competing, and a ratio computed from open findings alone, with no labelled corpus behind it, would measure nothing." | intro band, right column, unchanged (protected: the refusal to score) |
| paragraph: "A row here exists only for a detector that has raised an open finding -- the graph keeps no registry of which detectors are installed, only the findings they have written. A detector currently raising nothing does not appear, and that absence is indistinguishable from a detector that does not exist." | moves down to the detector catalogue's own caption, where the rows it is about are — one noun changes, ruling 6 |
| fleet branch: "This is a fleet-wide aggregate, not a repository's own answer: nothing selected a repository on the way here, so a detector's tally below counts its open findings across every repository the index has seen at once. Open this screen from a repository to narrow it to that codebase." | intro band, right column, unchanged |
| repository branch: "Every figure below counts open findings in {repoId} and in no other repository. A detector with no row here may still be raising findings elsewhere in the fleet — this screen cannot tell you that, because it did not ask." | intro band, right column, unchanged |
| `<DetectorAccountability repoId>` | unchanged as a mount |

### `detector-accountability.tsx` — the query, the states and the totals

| Field rendered today | Substrate slot |
|---|---|
| `LoadingState`("detector accountability") | unchanged, outside everything |
| `ErrorState`(error, "detector accountability") | unchanged, outside everything |
| empty headline, fleet: "No open finding is attributed to any detector." | `EmptyState`, unchanged |
| empty headline, scoped: "No open finding in {repoId} is attributed to any detector." | `EmptyState`, unchanged |
| empty detail: "The API answered, and the graph holds no open findings in this scope right now. That is an answer, not a failure -- nothing indexed here is currently flagged by any detector." | `EmptyState`, unchanged |
| the loose total line — `total_open_findings` at `--text-figure`, then "open finding(s) across N detector(s)." | **`MetricPanel` metric**: the same number at the same register, with the same words as its unit, inside the panel whose chart decomposes it — ruling 4 |

### `RungComposition` — the panel the chart is evidence for

| Field rendered today | Substrate slot |
|---|---|
| `CardTitle` "What these claims rest on" | `MetricPanel` label `WHAT THESE CLAIMS REST ON`, furniture register |
| — (no headline figure today) | `MetricPanel` metric, from the line above — ruling 4 |
| description "Every open finding in this scope, split by the rung of evidence behind it, one bar per detector. The same counts are in each detector's own `By rung` table below; this is the one view where they can be compared across detectors without arithmetic." | `MetricPanel` caption, unchanged |
| `Suspense fallback={null}` around the lazy chart | unchanged — the cards below are the same numbers, already on screen |
| the stacked bar itself | unchanged, in the panel body beneath the figure — no derivation touched, ruling 8 |
| its legend | unchanged — echarts `roundRect` plus the rung word, which is already dot-with-word |
| paragraph: "Every bar is the same length because it is a composition, not a quantity… drawing that as length would render the smaller ones as a sliver indistinguishable from nothing." | panel body, beneath the chart, unchanged |
| paragraph: "The rung is a class of evidence, not a position on a good-to-bad scale, so no colour here grades anything… it is making a different kind of claim, which is the thing an operator weighing a false positive needs first." | panel body, unchanged |
| — (nothing on screen counts a rung across every detector at once) | **the rung tally**, one row per declared rung with its count over the whole scope, a rung with none rendered as `0` rather than suppressed — ruling 3 |
| paragraph, on `absentRungs`: "Nothing in this scope rests on …. Those rungs keep their place in the legend and draw no segment — an absence, which is not the same fact as a rung this console does not have." | panel body, beneath the tally it now also explains, unchanged in wording |
| paragraph, on `unrecognisedRungs`: "One series counts findings whose rung this console does not recognise: …. They are counted rather than dropped, so the bars still sum to each detector's own total — the provenance vocabulary has grown since this view was written." | panel body, unchanged in wording |

### `DetectorCard` — one card per detector

| Field rendered today | Substrate slot |
|---|---|
| `Card` from `components/ui/card` | vendored `Card`, so the plane, the radius and the hairline are the substrate's |
| `CardTitle` the detector name, mono at `--text-emphasis` | an `h3` written here rather than the vendored `CardTitle`, keeping mono at `--text-emphasis` — ruling 9 |
| description: the count in `font-semibold tabular-nums`, then "open finding(s) currently attributed to this detector." | unchanged, still weight rather than a size step — ruling 5 |
| the comment arguing that weight carries the count on a repeating card | unchanged — it states a constraint the code cannot show |
| `TallyTable` "By rung", with `describeRung` as the cell's `title` | `components/data-table` anatomy, heading at `h4` — rulings 9 and 10 |
| `TallyTable` "By claim" | `data-table` anatomy |
| `TallyTable` "By severity" | `data-table` anatomy |
| per tally: column Value, mono, `orAbsent` on the empty key, with the comment that an empty string is a real key | `data-table` column, unchanged |
| per tally: column Findings, mono | `data-table` column, unchanged |
| the three tallies side by side at `sm:grid-cols-3` | unchanged — ruling 7 |
| paragraph, once per card: "No route filters findings by detector yet. Every open finding, by vendor, is on [the fleet screen \| this repository's own screen] instead." | **rendered once**, in the catalogue's caption above the cards — ruling 6 |
| the comment arguing why the link is not scoped to the row | unchanged, moved with the sentence |
| — | **no `⋮` overflow menu** — a detector card has no action at all, ruling 11 |

### `rung-composition-chart.tsx`

| Field rendered today | Substrate slot |
|---|---|
| `EChart` with `buildRungCompositionOption` | unchanged, not opened — ruling 8 |
| `ariaLabel` "Open findings by evidence rung, per detector: {summary}" | unchanged |
| `style.height` from `chartHeight(detectors.length)` | unchanged |
| the docstring's argument for a full-width bar, and its refusal of a score | unchanged, verbatim |

## The rulings

Eleven arrangements had no slot the five earlier levels had already settled. Their fifty-three
rulings are not restated: the metric value at `--text-figure`, the panel name in the furniture
register carrying its own `h2`, the accepted collapse of `variant="grouping"`, `--card-padding-x`,
the kept `components/skeleton.tsx`, the untouched `fact-tile.tsx` and `fact-list.tsx`, and
`data-table`'s `px-row`/`break-words` correction all apply here unchanged.

**1. The chassis arrives with this port, because this level never had it.** `/detectors` opened on a
bare `h1` at `--text-page` under a breadcrumb, with the route's own question — *"Which detector is
producing my false positives?"* — sitting unread in `lib/routes.ts`. That is the state Codebase and
Signals were both in, and Signals' ruling 1 applies verbatim: each level takes the chassis as it is
recomposed, `layouts/` is consumed and not edited.

The question earns its place here more than on most levels, because it is the only sentence on the
screen that says who the screen is *for*. Everything else says what the screen counts.

**2. A `ControlBar` carrying the scope, and no action in it.** This is where this level differs from
Signals, which refused the bar outright (its ruling 2), and the difference is that **this level's
scope is bimodal and Signals' was not**. A repository's Signals screen is always about that
repository; `/detectors` answers for the fleet or for one codebase depending on a query parameter,
and the two answers are different numbers under the same heading. A scope stated in the furniture
register, scanned before the figures are read, is what stops that being a silent difference.

The paragraph that qualifies the scope stays where it is and is not replaced by the bar. Signals'
ruling 4 settled that shape: the chip is scanned, the sentence carries the *why*, both read the same
source so they cannot disagree, and collapsing the sentence into the label would be exactly the
collapse-into-a-glyph the console refuses. Here both read `repo_id` from one search parameter.

**The action slot stays empty**, and the candidate was real: the link to the fleet's or the
repository's own findings. It is refused because that link travels with a qualification — *"No route
filters findings by detector yet"* — and a button in the action slot cannot carry it. A destination
offered as a primary action implies the screen is handing you the next step; this one is telling you
the step you want does not exist yet and naming the nearest thing. That belongs in a sentence, and
ruling 6 is where it went.

**3. The faceted-explorer direction lands as a rendered tally, not as a control, and the reason is
this level's API rather than the direction.** This is the ruling the level exists to make.

The direction is that a facet renders counts per value and renders a zero-count value rather than
suppressing it, and that the narrowing goes to the API rather than to the rows on screen.
`components/filters.tsx` already holds both properties and both are untouched here. What this level
does not have is anything for a chip to narrow: `GET /api/detectors` takes exactly one parameter,
`repo_id`, and `sync.dashboard.graph_views.detector_accountability` reads
`open_findings_page(repo_id=…)`. There is no rung parameter, no claim parameter and no severity
parameter, so a rung chip on this screen would have to filter the rows already rendered — which is
precisely the property the direction pins as *"already true — do not regress it"*. Building the
control would break the rule the control was asked for in order to keep.

**A repository facet is refused on the counts rather than on the narrowing.** `repo_id` *is* an API
narrowing, so a repository chip is mechanically possible, and `GET /api/repositories` would supply
the values. It would supply no counts: no payload in this console carries open findings per
repository, and a facet without counts is a dropdown wearing a facet's clothes — the counts are the
whole reason `filters.tsx` chose chips over a select, and its own docstring says so. Faking them by
issuing one `/api/detectors` request per repository is a fan-out this level has no route for.

So what the direction asks for is delivered as the thing it is actually protecting: **counts per
value, with a zero rendered rather than suppressed.** The rung tally is one row per declared rung
with its count across every detector in scope, and on the current seed two of the five —
`unresolved` and `unattributed` — stand at `0` and are rendered. That is `Edge Function 0`, arrived
at from this console's own data.

It is also not decoration, and this is the part worth stating plainly: **the chart cannot answer the
question its own docstring opens with.** `rung-composition-chart.tsx` asks *"how much of everything
the console currently claims rests on a static read alone?"* — and every bar it draws is normalised
to that detector's own total, so the answer is nowhere on the bar. The per-rung totals across the
scope are that answer, they are already computed in `rung-series.ts` (`RungSeries.total`, tested
there), and until this port nothing rendered them. The tally closes a question the level had been
asking and not answering.

**4. The panel carries a figure, and the direction's escape hatch is declined on the facts.** The
brief for this work item anticipated that a rung tally is not one number and offered the Binding
surface's precedent — a panel may carry no figure where no figure is honest. It is not needed here.

`total_open_findings` is a field of the payload, it is exactly the set the chart partitions, and
**the screen already spends `--text-figure` on it today**, in a loose paragraph above the chart with
no evidence attached. So the figure register neither gains nor loses a consumer: the number moves
from a sentence floating above a card into the header of the card whose chart decomposes it, which
is the arrangement `metric-panel.tsx` was written for. Its unit keeps the existing words — "open
findings across N detectors" — so nothing is dropped either.

What *would* have been dishonest is a figure over the tally: "five rungs" is a fact about the
console's vocabulary, not about the graph. That figure is not rendered.

**5. A detector card keeps its count in the sentence, and Signals' ruling 6 does not reach.** Signals
ruled that in a catalogue the card carries the figure and the group states the total in words,
because a figure that is the sum of the figures directly beneath it is one fact at two weights.
Here the ruling goes the other way, and the two are consistent once the difference is named: on
Signals **no total was at the figure register anywhere on that screen**, so the register was free
for the cards. Here the total is at that register, with the evidence for it directly underneath, and
Fleet's ruling 2 governs — the count that stays is the one an operator reaches first.

The card's own recorded argument points the same way and predates both: *"this card repeats once per
detector, so a stat-tile figure here would cost a row on every one of them."* On the current seed
that is four cards; on a customer graph it is however many detectors have fired.

**6. Three sentences move down to the rows they are about, and one noun changes.** Both were
per-screen prose that describes per-card rows.

The registry sentence — *"A row here exists only for a detector that has raised an open finding…"* —
was the third paragraph of a four-paragraph intro, above a chart, two panels away from the rows it
qualifies. It becomes the detector catalogue's own caption. **"A row here" becomes "A card here"**,
because the rows became cards two ports ago in this substrate migration and a sentence describing a
screen that no longer exists is the drift the protected-sentence rule exists to stop, arrived at
from the other direction. Signals' ruling 3 made exactly this trade for the word "panel"; the claim
is untouched and the length is the same.

The unscoped-link sentence — *"No route filters findings by detector yet. Every open finding, by
vendor, is on … instead."* — was rendered **once per detector card**, which is one fact written as
many times as the graph has detectors. It is now rendered once, in the same caption, above the cards
it is about. The comment arguing why the link is deliberately not scoped to the row travels with it.

This is a de-duplication rather than a shortening, and the distinction matters because
`.claude/rules/console-surface.md` forbids the second. Every word survives; only the number of
copies falls.

**7. The detector cards stay stacked full width, and the three tallies stay side by side inside
one.** The M7 direction's catalogue shape is a grid, and API Services' ruling 2 is why it does not
apply to this card: a card here holds three tables abreast at `sm:grid-cols-3`, and putting two such
cards side by side gives each tally a sixth of the screen. The seeded `vendor-change` card carries
nine claim rows whose values are the graph's own strings — a two-column tally at a sixth of 1440px
wraps every one of them.

The screen's one horizontal placement is therefore the intro band, which pairs what the screen
measures against what it cannot. Before this port the level had none.

**8. `rung-composition-option.ts` is not opened, and the legend is already what the direction asks
for.** The direction is a dot-with-word legend. echarts is configured with `icon: "roundRect"`,
`itemWidth: 10`, `itemHeight: 10` and the rung's own name as the series name — a mark beside a word,
which is the same reading Fleet's mapping table made of the corpus chart's legend. Nothing to
change, and the file's test stays untouched, which is the untouchable this work item was given.

The one thing the chart's placement does change is what sits above it: a figure at
`--text-figure` in the panel header rather than a floating paragraph. `chartHeight` and the option
builder do not know about either.

**9. The heading levels move, and they move because the panel became an `h2`.** `MetricPanel` writes
its own `h2`, so the chart panel is now one. A detector card is beneath the catalogue's own `h2`
heading and is written as an `h3` here rather than taken from the vendored `CardTitle`, which is a
mono uppercase 12px `h3` — the wrong register for a detector's name, which is an identifier read
rather than a label scanned. `subject-catalogue.tsx` set this precedent for the same reason two
ports ago. The three tally headings drop from `h3` to `h4`, so a tally is contained by its card
rather than a sibling of it.

`--text-emphasis` on the detector name is deliberate and Fleet's ruling 11 is why it is worth
stating: a panel name is now lighter than emphasis text inside the panel, and a card whose subject is
a mono identifier is exactly the case that rule described. The name is read; the panel above it is
scanned.

**10. `describeRung` reaches the screen through the cell's `title`, exactly as it did before.** The
rung tooltip on the "By rung" tally is the only place on this level where the rung vocabulary's own
words are rendered, and moving the table to `components/data-table` does not touch it —
`TableCell` forwards every prop. Stated because a port that silently dropped it would leave the
level's central claim unexplained, and nothing would have gone red.

**11. No `⋮` overflow menu, and this level is the clearest case yet.** Every earlier level's answer
was that a row has exactly one action — the link it already is. Here a detector card has **none**: no
route filters findings by detector, which is the very thing ruling 6's sentence says. A menu on a
card with no action is furniture claiming a choice that provably does not exist.

**A note on `abandon_reason`, which this level does not render.** The work item's direction carries
the standing rule that abandoned attempts are data and nothing about them moves behind a disclosure.
No file in `features/detectors/` reads that field — it belongs to the runs table and the workflow —
so the rule binds here only in its general form, and it is honoured: all three tallies on every card
stay expanded, nothing is collapsed behind a toggle, and the two conditional paragraphs on absent
and unrecognised rungs render in place rather than in a tooltip. This port adds no disclosure
anywhere.

**A note on `components/filters.tsx`, which this port does not restyle.** The work item permits it.
It is declined for two reasons, either sufficient. This level renders none of it — the module's three
components are consumed by the Binding surface and the vendor level, both already ported and both
measured with it as it stands — so restyling it here changes two other levels and this one not at
all. And the `Button` it imports is `@/components/ui/button`, the same local component
`states.tsx`, `page-controls.tsx`, `ordering.tsx` and `error-surface.tsx` all import; moving one of
five puts two button treatments on every screen that renders a filter beside a pagination control.
That is a shared-layer decision with its own measurement, not a rider on a level's port. The
behaviour the direction pins — a zero-count option rendered, the narrowing sent to the API — is
untouched, and `filters.test.tsx` is unmodified.

## What ruling 6 cost, and the correction the walk found

**Written here rather than folded into ruling 6, because the first version of this port shipped the
defect and the walk is what caught it.** The registry sentence â€” *"A card here exists only for a
detector that has raised an open findingâ€¦ that absence is indistinguishable from a detector that
does not exist"* â€” moved out of the page intro and into the catalogue's caption. The catalogue does
not render when no detector has anything, so on a `repo_id` naming a repository the graph holds no
open findings for, the sentence disappeared entirely.

**That is the branch it matters most on.** "No detector raised anything" and "no detector is
installed" are the two readings the sentence exists to keep apart, and an empty screen is precisely
where a reader has to be told they cannot be told apart. Walked against the old screen on
`/detectors?repo_id=nope`, the old rendered it and the new did not.

It is now a component â€” `RegistryNote` â€” rendered on both branches: beneath the catalogue's heading
when there are cards, beneath the empty state when there are none. One copy in source, one copy on
screen in either case. The general shape is worth carrying to the three levels still unported: **a
sentence moved from a page intro into a region inherits that region's render condition**, and the
intro's condition was "always".

## What it measured

Chrome, `/detectors` â€” the fleet-wide route, which is the richest this level has: four detectors,
10,007 open findings, three of the five declared rungs carrying findings and two carrying none. The
old screen was served from a scratch worktree at `d4332e9` on port 5186 and the new one on 5187,
both proxied to the same API on 8787, so the two readings are of one seed.

| | 1440x900 before | 1440x900 after | 1280x800 before | 1280x800 after |
|---|---|---|---|---|
| type range | 2.33:1 | **3.83:1** | 2.33:1 | **3.83:1** |
| type steps | 12 / 13 / 15 / 22 / 28 | 12 / 13 / 15 / 18 / 28 / **46** | as 1440 | as 1440 |
| largest step | 28px (the total) | 46px (the `h1`) | 28px | 46px |
| side-by-side placements | 4 | **5** | 4 | 5 |
| column heading | sentence-case, 40.0px | uppercase, 40.0px | sentence-case, 40.0px | uppercase, 40.0px |
| body row | 36.0 / 36.5px | 36.5 / 37.0px | 36.0 / 36.5px | 36.5 / 37.0 / **57.0**px |
| widest table against its container | 344 of 344 | 1063 of 1063 | 291 of 291 | 903 of 903 |
| clipped by a sideways scroll | 0px | 0px | 0px | 0px |
| document height | 2746px | 3014px | 2746px | 3034px |

`DESIGN.md`'s bar is 3.4:1 and the display step is what clears it, exactly as on the four levels
that gained `PageHeader` before this one. The four placements the old screen already had are the
four cards' `sm:grid-cols-3` tally grids; the fifth is the intro band, which is the first time this
screen puts anything beside anything else at the page level.

The row grew by half a pixel to one pixel, which is the rule the vendored `TableRow` draws under
itself and the same delta the four ported levels before this one measured.

**One row is 20px taller at 1280 and it is the honest cost of the shared anatomy.** It is
`response-field-type-changed` in the `vendor-change` card's `By claim` tally, and nothing else on
the screen wraps at either width. The cause is measured rather than guessed: the furniture register
is wider per glyph than sentence case, so `FINDINGS` sets a 125px second column where `Findings` set
a narrower one, leaving 165px for the value in a 290px table â€” a few pixels short of what that
string needs. Signals' *What it measured* recorded the same mechanism on the twelve-column telemetry
table.

Recorded rather than fixed, on that level's reasoning. The alternatives are dropping a column, which
is a completeness loss, or hand-spelling a narrower register in this one feature, which is the drift
`components/data-table.tsx` exists to prevent. Nothing is hidden by it â€” the row is taller, not
clipped â€” and the rung tally, which is the table the graph-grain rule actually cares about here,
sits in 1063px at 1440 and 903px at 1280 with nothing behind a scroll at either.

The document is 268px taller at 1440. That is the header band, the control bar, the rung tally and
the catalogue heading, all of which are content this screen did not have.

## The completeness walk

Every field the old screen asserted, asserted by the new one, read off both screens against the same
seed rather than off the diff. Three states were walked: `/detectors` unfiltered,
`/detectors?repo_id=seed-console-repo-a` (the richest scoped route â€” two detectors, three findings,
three rungs absent), and `/detectors?repo_id=nope` (the empty state, and the branch that found the
correction above).

Carried unchanged, string for string: both breadcrumb trails; the `h1`; all four intro paragraphs in
both scope branches, including the mono repository id inside the scoped one; the panel's title and
its full description; both standing paragraphs under the chart; the absent-rung paragraph, with its
`or` before the last item, in both its two-rung and three-rung forms; every detector name; every
count sentence, with its singular and plural forms; all three tallies on every card, in the same
order, with the same values, the same sort and the same `describeRung` tooltip on the rung tally's
cells; the unscoped-link sentence with both of its link destinations; the empty state's headline in
both branches and its detail in full; the registry sentence on every branch that rendered it before.

Changed in rendering and not in content: every column heading is uppercase and open-tracked; every
count is written with thousands separators â€” `10,002` rather than `10002` â€” which the chart's own
axis labels and tooltip have always done; the panel title moves to the furniture register; the
total's trailing full stop goes, because it is now a metric's unit rather than a sentence, which is
how every other `MetricPanel` on the console spells one.

Reworded, one noun: "A row here exists only for a detectorâ€¦" is now "A card hereâ€¦", per ruling 6.

Gained: the route's own question at the display step; a `SCOPE` statement in the furniture register;
the total at the figure register inside the panel whose chart decomposes it, rather than floating
above it; a `By detector` heading over the cards; and the rung tally â€” `static 3,336`,
`resolved 3,334`, `observed 3,337`, `unresolved 0`, `unattributed 0`, summing to the 10,007 the
panel's own figure carries â€” with its scope sentence beneath it.

Lost: nothing.

Verified separately, because each is a branch the fleet route does not reach:

- **The scoped route** renders the three-segment breadcrumb, the repository id in the scope slot in
  mono, the repository branch of the intro paragraph, and the repository link rather than the fleet
  link in the catalogue caption.
- **A scope with three absent rungs** (`seed-console-repo-a`) renders `observed`, `unresolved` and
  `unattributed` at `0` in the tally and names all three in the absence paragraph.
- **The empty state** renders the headline, the detail, and the registry sentence beneath it, and
  renders no panel, no chart, no tally and no catalogue heading.

The document outline reads `h1` â†’ `h2` panel â†’ `h3` tally â†’ `h2` catalogue â†’ `h3` card â†’ `h4` tally,
with no level skipped, which is ruling 9 checked on the running screen rather than in the source.

## The protected sentences

**None of the seventeen fragments `tests/test_console_honesty_sentences.py` holds lives in
`features/detectors/`, before this port or after it.** Grepped per fragment across `web/src` in both
states; the per-fragment file counts are identical either side, and zero in this feature both times.
The whole file, 17 parametrised cases, is green, as are `tests/test_console_hierarchy.py` and
`tests/test_console_design_tokens.py` â€” 85 cases between the three.

That is a fact about where those sentences sit rather than about this screen's honesty, and it is
worth saying plainly rather than reporting as a clean bill. The claims this level makes â€” that it is
not a leaderboard, that a detector with no findings is indistinguishable from one that does not
exist, that a rung is a class of evidence and not a grade â€” are unpinned by that guard, and were
carried by the walk instead. Two of them are why ruling 3 refused to build a control and ruling 5
refused to move a figure.
