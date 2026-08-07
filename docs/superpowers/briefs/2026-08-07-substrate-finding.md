# The Finding on the substrate — the mapping table, and the rulings it forced

Task 6 of `docs/superpowers/plans/2026-08-06-console-supabase-substrate.md`, sixth level. Work
item M7-W178.

The Finding level is `/findings/:findingId` — one finding, the binding it rests on, and the vendor
changes that name it. It is the seventh level ported, after Fleet (M7-W172), Codebase (M7-W173),
API Services (M7-W174), Signals (M7-W175), the Binding surface (M7-W176) and Errors & Incidents
(M7-W177). `docs/superpowers/briefs/2026-08-07-substrate-fleet.md` is the parent document and its
eleven rulings bind wherever they generalise; the five levels since add fifty-three more. This file
records only what is new here, or what this level decided differently, and says which.

Two things make this port different from the six before it.

**This is the first detail-shaped level, so the fact rail arrives as a region rather than as a
band.** Every level ported so far is a list of something: a fleet of repositories, a vendor's
findings, an operation's call sites. Four of them put `FactList` beside the page header in one band
at the top and let the tables have the rest of the screen. A detail has one subject and no table
that needs the width, which is the arrangement the owner's first direction example is built around
(`references/direction/NOTES.md` entry 1: *"A fixed left rail about 360px wide … then a definition
list of nine facts … then three actions stacked at the bottom"*). Ruling 1 is what that costs and
where it stops.

**The payload does not carry four of the seven facts a rail would want, and this port renders none
of them.** That is the more important half of this document. `GET /api/findings/{finding_id}` is
`explain_call_site` plus two fields, and it holds no severity, no repository, no call-site path or
line, and no first-or-last-seen timestamp. The direction names all of those; the honest answer is a
ruling and a backlog entry rather than a slot filled with something adjacent. Ruling 3.

The table below was built by reading `finding-page.tsx` line by line, not from memory. Every
rendered string, every count, every state branch is a row.

## The mapping table

### `FindingPage` — the identifier guard

| Field rendered today | Substrate slot |
|---|---|
| `UnknownRoute` when the URL carries no `findingId` | unchanged, before the query is made |

### `FindingDetail` — the page shell

| Field rendered today | Substrate slot |
|---|---|
| breadcrumb trail "Fleet" → the vendor (only once the query succeeds) → the finding id | `PageHeader` trail, `Breadcrumbs` unchanged, still conditional on success |
| `h1` `{findingId}`, mono, at `--text-page` | `PageHeader` title, mono, now at the **display step** — ruling 2 |
| — (this level rendered no question; `ROUTES` has held one unrendered since the registry landed) | `PageHeader` question, `routeQuestion("/findings/:findingId")` — ruling 2 |
| `LoadingState`("finding {findingId}") | unchanged, in the content column |
| `NotFoundState` "That finding is not open." with its detail and `identifier` | unchanged, in the content column (protected: "not a failure of the console") |
| `ErrorState`(error, "finding {findingId}") | unchanged, in the content column |
| the three cards stacked full width | three panels stacked in the content column, right of the rail — ruling 1 |

### The links down — rendered outside the success branch, and still are

| Field rendered today | Substrate slot |
|---|---|
| `Link` "Solution workflow" → `/findings/{id}/workflow` | the rail's action stack, unchanged in destination and wording |
| the note beside it, "— what Sync did about this finding, node by node." | same line, unchanged |
| the comment arguing why this sits outside `query.isSuccess` — a patched or abandoned finding 404s here, and that is exactly the finding whose run is most worth reading | unchanged, and now load-bearing for a second link — ruling 12 |
| — (nothing linked to the Pull Request level, which has had a route since 2026-08-06) | `Link` "Pull request", rendered only when the newest run's `outcome` is `opened` — rulings 4 and 6 |

### The fact rail — new in this port

| Fact | Where it comes from |
|---|---|
| Vendor, as a link carrying no scope | `data.vendor` — moved out of the "Binding" card's `dl`, ruling 10 |
| Operation | `data.operation` through `orAbsent` |
| Symbol | `data.symbol` through `orAbsent` |
| SDK version | `data.sdk_version` through `orAbsent` |
| This finding's rung | `data.finding.binding_source` through `RungBadge` — never null at this level |
| Remediation | `describeRemediation` over `useWorkflow`'s state — rulings 4 and 5 |
| per fact: `Skeleton` while the query is in flight | `components/skeleton.tsx`, kept by Fleet ruling 6 |
| per fact: `<Absent>`("the API did not answer") on failure | unchanged from the four levels that already do this |

### `remediation.ts` — new in this port

Nothing here renders. It is the derivation the rail's Remediation fact and the Pull Request link
both read, and it is tested before it exists.

| What it answers | Where it lands |
|---|---|
| whether the checkpointer holds a run at all, versus the console not knowing yet | `RemediationState.kind` — `pending` / `none` / `unavailable` / `run` |
| how the newest run stands, in the checkpointer's own vocabulary | `outcome`, passed through rather than re-spelled |
| how many threads this finding has, so the rail never implies one | `generations`, and `retried` — ruling 5 |
| whether a pull request exists to link to | `reachedPullRequest`, read off `outcome` and never off the `open_pr` node — ruling 6 |

### The "Binding" card

| Field rendered today | Substrate slot |
|---|---|
| title "Binding" | **dissolved.** Its `dl` is the fact rail and its strip is the provenance panel — ruling 10 |
| description "What this call site calls, and how the system knows it does." | the rail's own caption, beneath the facts, unchanged in wording |
| `dl` row Vendor, mono, as a link | fact rail, row 1 |
| `dl` row Operation, `Formatted`/`orAbsent` | fact rail, row 2 |
| `dl` row Symbol, `Formatted`/`orAbsent` | fact rail, row 3 |
| `dl` row SDK version, `Formatted`/`orAbsent` | fact rail, row 4 |
| `dl` row "This finding's rung", `RungBadge` | fact rail, row 5 |
| `ProvenanceStrip` with its `bindingNullLabel` | its own panel, PROVENANCE — rulings 7 and 10 |

### The "What the call site touches" card

| Field rendered today | Substrate slot |
|---|---|
| title "What the call site touches" | `MetricPanel` label, furniture register, no figure — ruling 8 |
| description "The argument keys sent and the response fields read — the surface a change has to break for this finding to matter." | panel caption, unchanged |
| `FieldList` "Argument keys" — its `h3` in the furniture register | unchanged, inside the panel |
| its empty branch, `<Absent>`("none recorded") | unchanged |
| its chips, one per key | unchanged shape, respelled onto `RungBadge`'s chip anatomy — ruling 9 |
| `FieldList` "Response fields read", all four rows above | unchanged |

### The "Known changes" card

| Field rendered today | Substrate slot |
|---|---|
| title "Known changes" | `MetricPanel` label, furniture register, no figure — ruling 8 |
| description "Vendor changes naming this call site, shallow. The full record is fetched by identifier." | panel caption, unchanged |
| the empty branch, `<Absent>`("No vendor change names this call site. The finding was raised by something other than a spec diff.") | `EmptyState`, wording unchanged — ruling 13 |
| column Change, the `change_id`, mono | `components/data-table` column, mono |
| column Kind | `data-table` column |
| column Severity | `data-table` column — and this is the only place on the level a severity is honest, ruling 3 |
| the row key, `change.change_id` | unchanged |
| — (no row on this table has an action) | no `⋮` overflow menu — ruling 11 |

## The rulings

Thirteen arrangements had no slot the six earlier levels had already settled. Their sixty-four
rulings are not restated: the metric value at `--text-figure`, the accepted collapse of
`variant="grouping"`, `--card-padding-x`, the kept `components/skeleton.tsx`, the untouched
`fact-tile.tsx` and `fact-list.tsx`, `data-table`'s `px-row`/`break-words` correction, `describeRung`
reaching the screen through a `title`, and the refusal of a `⋮` overflow menu all apply here
unchanged.

**1. The fact rail is a left column rather than a band, and this is the first level to place it
that way.** Vendor, API Services and the Binding surface all spell
`lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]` — content left, facts right, one band at the top,
tables full width beneath. That arrangement exists because those levels are lists and a table wants
the whole frame. This level has one table, three rows wide in the fixture, and no set that grows.

So the grid inverts and extends: `lg:grid-cols-[minmax(0,22.5rem)_minmax(0,1fr)]`, rail left,
content right, and the rail holds the header rather than sitting beside it. 22.5rem is 360px, which
is the width the direction names.

**The consequence a reader should know is that this level's `PageHeader` is inside a 360px column**,
so the display-step title wraps where the other six levels' do not. A finding id is a 32-character
hex string with no break opportunity, and `PageHeader` already spells `break-words` for exactly this
— measured below at three lines and 148px of header, which is what buys the facts their position
directly under the title. The alternative was the title full width above both columns, which is the
band arrangement again with extra steps and puts 148px between the question and the facts that
answer it.

**It stays a single column below `lg`.** The rail is a column, not a sidebar: at 1023px it stacks
above the content and nothing is lost, because a definition list reads the same at either width.

**2. The title takes the display step, and the question arrives from the registry.** This level
opened on a bare `h1` at `--text-page` and never rendered `RouteEntry.question`, which for this
route has read *"What is this finding, and what binding does it rest on?"* since the registry
landed. B116 is the entry that counts this off; the Finding level is one more of the nine.

**3. Four facts the direction asks for are not in this payload, and none of them is invented.** This
is the ruling this level exists to make.

The direction's rail is *"severity, status, vendor, operation, repository, first/last seen, rung"*.
What `GET /api/findings/{finding_id}` actually returns is `symbol`, `operation`, `vendor`,
`args_keys`, `response_fields_read`, `sdk_version`, `known_changes`, the `Provenance` envelope, and
`{finding_id, binding_source}`. So:

- **Severity is not there.** `sync.api.app.finding_detail` reads a `_risk_row` through
  `finding_by_id` — which *does* carry `severity` — and forwards two of its fields. The severity on
  screen is therefore the severity of each *vendor change*, in the changes table, which is a
  different claim: a `breaking` change naming this call site is not the same statement as a
  `breaking` finding, and rendering the change's word in a rail slot labelled "Severity" would
  silently promote one to the other. On a finding with two known changes at different severities it
  would have to pick one.
- **The repository is not there**, and neither is the call site's path or line. The same `_risk_row`
  holds `file` and `line`; the route drops both. So this level, whose own docstring calls itself
  *"one binding in full"*, cannot name where the binding is. It could not before this port either —
  this is a standing gap the port names rather than a regression it introduces.
- **First and last seen are not there.** `indexed_at` is on the envelope and is rendered by
  `ProvenanceStrip`, where it already means "when the index last read this call site". It is not a
  first detection and must not be labelled as one.

`api/types.ts` is the data seam and this task does not open it, so the fix is a payload change
argued on its own. **B122** is the entry. What this port does instead is render the six facts the
payload does hold and let the changes table carry the only severity there is.

**4. "Status" is answerable, and it costs this level one query it has never made.** `useWorkflow` is
consumed here for the first time. Three things come out of it and each was otherwise unavailable:
the rail's Remediation fact, the fact that a finding has been retried, and whether there is a pull
request to link to.

The alternative — link to `/findings/{id}/workflow/pull-request` unconditionally — is what the
direction rules out with three words (*"if one exists"*), and it is right to: that page's own
not-found state is well written, but a link a console offers is a claim the console is making, and
offering "Pull request" on a finding that has never had a run is a claim that is wrong more often
than it is right.

The cost is honest and worth stating. It is a second request on page load, and `useWorkflow` polls
at `WORKFLOW_POLL_MS` while the run it describes is in flight — so this level now re-asks every five
seconds on a finding with a live run, which it did not before. Against that: the query key is
`["findings", id, "workflow"]`, exactly the key the Solution Workflow level reads, so the level
below this one now opens against a warm cache rather than a cold one. The reader who follows the
link is the reader who paid for the request.

**5. `useWorkflow` answers the newest generation only, so the rail may not say "the run".**
`WorkflowState`'s own docstring is explicit: *"this route always answers with the newest, so a
finding retried across generations has `generation_count` threads and this payload is only one of
them."* The seed proves it — `9f176dea…` carries `generation_count: 2`, an abandoned first attempt
and a second that opened a pull request.

A rail reading "abandoned" on that finding would be a false statement about the finding and a true
one about a superseded thread. So `describeRemediation` carries `generations` and `retried`, the
Remediation fact says *newest of N*, and the sentence beneath names the runs table as where the
others are — which is what the type's docstring already says (*"`sync.dashboard.fleet.runs` is the
query that lists every generation as its own row"*), rather than a link this route cannot serve.

**6. The pull request is read off the run's outcome, never off the `open_pr` node's evidence.**
`isRunTerminal`'s own comment carries the argument one field over: reading terminality off the nodes
*"would be wrong twice: `open_pr` reads `done` on a run that went on to be abandoned"*. A node's
evidence holding a `pr_url` is the same trap — it says a pull request was opened at some point on
some thread, not that the run this payload describes ended with one. `outcome === "opened"` is the
whole predicate and it is the only one this level uses.

**7. `bindingNullLabel` keeps its claim and repoints the one clause that names a position.** It read
*"mixed: more than one detector names this call site and they disagree on the rung — this finding's
own rung is above"*, which was true when the rung sat in a `dl` above the strip inside one card. It
now reads *"…this finding's own rung is in the facts beside this panel"*, because that is where the
rung is. Nothing else in the sentence moves.

It is not one of the twenty-four catalogued sentences and it is not one of
`tests/test_console_honesty_sentences.py`'s seventeen fragments — both of those hold `null is a
fact` in `components/provenance.tsx`, which is the rule that this label exists per route. Changing a
word that describes the screen's own geometry is the restyle the rule permits; the distinction it
carries (the envelope's rung goes null on disagreement, and this finding's own rung still says
something definite) is untouched.

**8. This level renders nothing at the figure register, and every candidate is refused for its own
reason.** The Binding surface reached the same place by a different route, and this is the second
level to do it.

- `known_changes.length` is a count of `vendor_change` rows. `CLAUDE.md`'s idempotency exemption
  names that source as at-least-once and says not to read a row count from it as a measurement;
  API Services ruling 5 refused the same figure one level up.
- `args_keys.length` and `response_fields_read.length` are counts of two lists the panel renders in
  full a few pixels below. A figure above its own members, where the members always fit, is a fact
  written twice at two weights.
- `context_savings` is a constant per avoided read rather than a measurement of this finding, and
  `ProvenanceStrip` already renders it in the register it belongs to.

Both content panels therefore pass no `metric`, which is the case `MetricPanel` made the prop
optional for.

**9. The `FieldList` chip is respelled onto `RungBadge`'s anatomy, and nothing else about it moves.**
It drew `rounded border border-border px-field py-0.5 font-mono text-meta`; the console's chip —
`RungBadge` — draws `rounded-control border border-line px-field py-0.5 font-mono text-meta`. Two
tokens differ and both are the substrate's: `--radius-control` is declared, `border-line` is the
hairline every other bordered thing on the ported levels now uses. This is the same class of
correction Signals' ruling 7 made and it changes two class names.

**A chip is not a badge claiming a status, and this is worth being explicit about** because the
console reserves colour for four tones and spends none of them here. An argument key is a recorded
string from the customer's own source. It gets weight and a hairline and no hue, exactly as the rung
does.

**10. The "Binding" card dissolves, and its two halves go to two different places.** Its `dl` is
what the fact rail is made of and its `ProvenanceStrip` is what the provenance panel holds; a card
containing neither has nothing left to be. Its description — *"What this call site calls, and how the
system knows it does."* — moves to the rail as the caption under the facts, which is the sentence's
own subject and where it now sits.

The strip gets its own panel rather than being appended to one of the other two, because it is the
only region on the level that is about the *answer* rather than about the finding: it carries the
envelope's rung, the index and feed timestamps, and the savings figure. Its caption is the two-rungs
sentence this level's docstring has always carried in prose — the per-finding rung is in the rail,
the envelope's is in the panel, and the caption is what tells a reader they are different questions
rather than a disagreement.

**11. No `⋮` overflow menu, and this level is the emptiest case of the seven.** Every earlier level
refused it because a row had exactly one action. A `known_changes` row has **zero**: a `change_id`
is not addressable in this console — the payload is shallow by design, and the full record is
fetched by identifier through a route the console does not serve. A menu here would have nothing to
put in it.

**12. The links stay outside `query.isSuccess`, and the pull-request link inherits that.** The
existing comment is the argument and it survives the port intact: a finding that has been patched or
abandoned is no longer open, so this page 404s for it — *and that is exactly the finding whose run
is most worth reading*. The workflow lives in the checkpointer, which does not care whether the
graph still holds the finding.

The consequence, which is new: **the Pull request link can render on a page whose finding query
404'd**, because the two queries are answered by two databases. That is correct rather than a leak.
The reader who arrives at a remediated finding's URL sees "That finding is not open." beside a live
link to the pull request that closed it, which is the most useful thing this screen can do for them.

**13. The empty branch becomes an `EmptyState` and keeps every word.** It was an `<Absent>` inside a
paragraph, which is the absence marker doing an empty state's job — `states.tsx`'s four kinds of
nothing exist for exactly this and the glyph belongs to a value that is missing rather than to an
answer that is empty. The headline is the first sentence and the detail is the second, both verbatim:
*"No vendor change names this call site."* / *"The finding was raised by something other than a spec
diff."*

## What it measured

Chrome, `/findings/9f176dea35907f95beb29553e574a037` — the richest seeded finding, and richest on
the axis this level is about. It is the only seeded finding with more than one remediation
generation: an abandoned first attempt and a second that opened a pull request, `generation_count`
2. It also carries one known change at `breaking` and rests on the `static` rung. The old screen was
served from a scratch worktree at `5a31798` on port 5194 and the new one on 5195, both proxied to
the same API on 8787, so the two readings are of one seed.

| | 1440x900 before | 1440x900 after | 1280x800 before | 1280x800 after |
|---|---|---|---|---|
| type range | 1.83:1 | **3.83:1** | 1.83:1 | **3.83:1** |
| type steps | 12 / 13 / 15 / 22 | 12 / 13 / **46** | unchanged | unchanged |
| side-by-side region placements | 0 | **1** | 0 | **1** |
| `h1` | 22px, 32px tall | 46px, 153px tall | 22px, 32px tall | 46px, 153px tall |
| first panel heading, from the page's top | 220px | **57px** | 220px | **57px** |
| last rendered pixel | 875px | **716px** | 875px | **757px** |
| column heading, changes table | 40.0px | 40.0px | 40.0px | 40.0px |
| body row, changes table | 36.5px | 36.5px | 36.5px | 36.5px |
| table against its container | 1065 of 1065 | 686 of 686 | 905 of 905 | 526 of 526 |
| horizontal overflow | none | none | none | none |

Two readings need their method stated, because both are easy to take wrongly.

**The first-panel-heading row is the first `h2` in `main`.** On the old screen that heading is
"Binding", 220px down, under a breadcrumb, an `h1`, a paragraph of link prose and a card's own
padding. On the new one it is "KNOWN CHANGES" 57px down — the grid's top edge plus the panel's own
header inset — because the two columns start level and the content no longer waits for the header
to finish. That 163px is what ruling 1's arrangement buys, and it is the reason a rail 360px wide
costs this level nothing vertically.

**"Last rendered pixel" is the greatest `bottom` of any element inside `main`**, not
`document.scrollHeight` — that value is floored at the viewport height and reads 900 and 800 on the
new screen, which says only that nothing scrolls. The honest number is 716px at 1440 and 757px at
1280 against 875px at both widths before, so the page is **159px and 118px shorter** while carrying
two facts it did not carry before.

**The rail does not push content under the fold at either width. It removes the fold.** The old
screen ran to 875px and scrolled at 1280x800; the new one ends at 757px and does not. Everything on
this level — six facts, both links, all three panels, the change row and the whole provenance strip
— is above the fold at 1280x800, which was not true before. So the measurement the direction asked
for has no cost to report on this level.

**The rail is 360px at both widths**, which is `minmax(0,22.5rem)` resolving exactly, and the content
column takes 720px at 1440 and 560px at 1280. The changes table draws in 686px and 526px of that and
fits both without a sideways scroll.

**The changes table's heights did not move, and that is the expected reading.** Every level before
this one gained a pixel per row moving to `components/data-table`. This one gained nothing, because
the old screen's `components/ui/table.tsx` already spelled `px-row py-row` — the arithmetic
`DESIGN.md` publishes, and the value M7-W174's correction brought the substrate back to. The visible
change is the register: `Change` / `Kind` / `Severity` are now uppercase and open-tracked.

**The type range moves because the display step arrives, and the 15px step leaves with the cards.**
`--text-emphasis` was on this screen only as the three `CardTitle`s; a panel name sits in the
furniture register now, so this route's ramp is 12 / 13 / 46 rather than 12 / 13 / 15 / 22. That is
3.83:1 against the 3.4 bar `reports/2026-08-06-why-the-console-came-out-flat.md` sets, and this route
is one more of the nine B116 counts off.

**The `h1` takes three lines and 153px**, which is ruling 1's stated cost. A 32-character hex
identifier at 46px in a 360px column has no break opportunity, and `PageHeader`'s own `break-words`
is what keeps it inside the rail instead of overflowing it. Nothing clips at either width and the
document has no horizontal scroll.

## The completeness walk

Every field the old screen asserted, asserted by the new one, read off both screens against the same
seed rather than off the diff. Four states were walked at 1280x800, each on both ports:

- `/findings/9f176dea35907f95beb29553e574a037` — one known change, two generations, a pull request.
- `/findings/443b1719164579873939aaaecfa2902d` — three argument keys, three response fields, the
  `resolved` rung, and a run still in flight.
- `/findings/9e44cb35095a641c02b48f93104a2e0b` — no known change, no argument keys, no response
  fields, and no run at all.
- `/findings/does-not-exist` — the 404.

Carried unchanged, string for string: the breadcrumb trail and its conditional vendor crumb; the
`h1`'s content; the Solution workflow link, its destination and its note; the not-found headline, its
detail and its identifier; all five binding facts with the same formatters, the same values and the
same rung badge; the "What this call site calls" sentence; both `FieldList` labels and every chip;
the "none recorded" absence on both; the "surface a change has to break" sentence; the "shallow /
fetched by identifier" sentence; the empty-changes wording in both of its sentences; the three column
headings and every cell; and all four fields of `ProvenanceStrip` with their values.

Changed in rendering and not in content: the three column headings are uppercase and open-tracked;
the three card titles are panel names in the furniture register; the five binding facts are a rail
rather than a four-column `dl`; the empty-changes branch is an `EmptyState` rather than an `<Absent>`
inside a paragraph; and the panels read known changes, then what the call site touches, then
provenance, where the cards ran binding, touches, changes.

Gained: the route's own question at the display step; a Remediation fact reading *"Opened a pull
request"* with *"The newest of 2 runs on this finding"* under it on the two-generation finding,
*"In flight — no outcome written yet"* on the running one, and the checkpointer's own absence on the
finding that has no run; and a Pull request link on the one finding that has one.

Lost: nothing.

**One thing changed because the walk found it**, and it is recorded here rather than quietly fixed.
The 404 state rendered the not-found sentence six times — once per rail fact and once in the panel —
because the rail's absence phrase was the panel's whole sentence. Six copies of one fact is the
defect `CLAUDE.md` names as the most expensive kind, so the rail's phrase is now the short form,
*"this finding is not open"*, which matches the panel's headline and leaves the full explanation in
the one place with room for it. Each row still says which nothing it is, which is what the absence
vocabulary requires.

## The protected sentences

One of the seventeen fragments `tests/test_console_honesty_sentences.py` holds lives in the file this
port opened. Every fragment was grepped against `features/findings/` before the port and against the
whole of `web/src` after it.

| Fragment | Before | After |
|---|---|---|
| `not a failure of the console` | `features/findings/finding-page.tsx`, and two files outside this feature | the same three files, the sentence unchanged |

The other sixteen were checked against `features/findings/` before the port and none of them was
there, so none could be lost by it; all sixteen still have holders elsewhere. `null is a fact` and
`deliberately not merged` were checked specifically, because ruling 7 edits a `bindingNullLabel`:
both live in `components/provenance.tsx`, which this port consumes and does not open. The whole
file, seventeen parametrised cases, is green.
