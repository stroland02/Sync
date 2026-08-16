# The Solution Workflow on the substrate — the mapping table, and the rulings it forced

Task 6 of `docs/superpowers/plans/2026-08-06-console-supabase-substrate.md`, seventh level. Work
item M7-W179.

The Solution Workflow level is `/findings/:findingId/workflow` — what Sync's remediation graph
actually did about one finding, node by node. It is the eighth level ported, after Fleet
(M7-W172), Codebase (M7-W173), API Services (M7-W174), Signals (M7-W175), the Binding surface
(M7-W176), Errors & Incidents (M7-W177) and the Finding (M7-W178).
`docs/superpowers/briefs/2026-08-07-substrate-fleet.md` is the parent document and its eleven
rulings bind wherever they generalise; the six levels since add sixty-four more, and the Finding's
thirteen are the detail-shaped precedent this level sits directly below. This file records only
what is new here, or what this level decided differently, and says which.

Three things make this port different from the seven before it.

**This is the level the product's argument lives on, so the direction for it is a content model
rather than a layout.** `references/direction/NOTES.md` entry 2 is the owner's reading of
Superlog's activity trail, and its closing paragraph is aimed at this file by name: *"The workflow
screen renders the node sequence as a list of nodes. Theirs renders a narrative: what happened,
then what the agent concluded, then the structured artifact it produced, then the resolution with
per-item evidence. Same data, different reading order — and the reading order is what makes one
feel like an investigation and the other like a status table."* The recomposition below is that
reading order.

**The run's outcome stops being a banner and becomes an entry in the sequence, at the point in the
run where it happened.** That is ruling 3, and it is the single change that does most of the work:
an abandoned run's reason now sits between the node that failed and the nodes that were never
reached, so the tail of never-reached entries has a visible cause above it rather than a panel
four screens up.

**Two of the direction's four asks are not in this payload, and neither is invented.** There is no
per-node elapsed time and no way to reach a superseded generation from this route. Rulings 6 and 7
are what those cost and where the fix is. This is the same shape as the Finding port's ruling 3
and it is becoming the standard shape of a port: the direction names a slot, the payload does not
hold it, and the answer is a ruling with a backlog entry rather than a field filled with something
adjacent.

The table below was built by reading `workflow-page.tsx`, `node-sequence.tsx`, `run-outcome.tsx`,
`evidence.tsx` and `node-standing.ts` line by line, not from memory. Every rendered string, every
count, every state branch is a row.

## The mapping table

### `WorkflowPage` — the identifier guard

| Field rendered today | Substrate slot |
|---|---|
| `UnknownRoute` when the URL carries no `findingId` | unchanged, before the query is made |

### `Workflow` — the page shell

| Field rendered today | Substrate slot |
|---|---|
| breadcrumb trail "Fleet" → the finding id → "Solution workflow" | `PageHeader` trail, `Breadcrumbs` unchanged, in the rail — ruling 1 |
| `h1` `{findingId} — solution workflow`, mono, at `--text-page` | `PageHeader` title, mono, at the **display step**, and the trailing " — solution workflow" is dropped: the breadcrumb's last crumb already says it and the registry's question says it again — ruling 2 |
| — (this level rendered no question; `ROUTES` has held one unrendered since the registry landed) | `PageHeader` question, `routeQuestion("/findings/:findingId/workflow")` — ruling 2 |
| `LoadingState`("the run for finding {findingId}") | unchanged, in the content column |
| `NotFoundState` "No remediation run for this finding." with its detail and `identifier` | unchanged, in the content column (protected: "not a failure of the console") |
| its "Check again" button | unchanged, beneath the state |
| `ErrorState`(error, "the run for finding {findingId}") | unchanged, in the content column |
| `StaleBanner` — "Could not refresh. Showing the run as of …" | unchanged in wording and behaviour, at the top of the content column — ruling 8 |
| its live branch — "the run is still live, so polling continues in the background…" | unchanged (protected in claim) |
| its terminal branch — "the run has reached a terminal outcome, so nothing is polling…" | unchanged (protected in claim) |
| its "Check again" / "Asking…" button on a terminal run | unchanged |
| the run line — `Run {thread_id}`, mono | fact rail, row 2 — ruling 1 |
| "— the most recent of N runs the checkpointer holds for this finding." with the fleet link | fact rail, row 3, wording unchanged — ruling 7 |
| — (nothing linked up to the finding except the breadcrumb) | fact rail, row 1: Finding, as a link — the direction's *"what arrived"*, ruling 4 |
| the pull-request link, worded off `outcome` | the rail's action stack, unchanged in destination and in both wordings — ruling 9 |
| its note, "— the five nodes below that answer whether this run earned a merge…" | same line; **"below" is dropped**, because the five nodes are no longer below it — ruling 9 |
| the closing paragraph, "Read from the checkpointer, which is a different database…" with the finding link | the narrative's opening entry, verbatim — ruling 4 |
| — (nothing said what a run is an answer to) | the opening entry's first sentence, **new**: "A finding arrived from the API Dependency Graph, and this run is what Sync did about it." — ruling 4 |
| — (nothing said the run carries no clock) | the same opening entry, **new**: "It carries no clock either: the checkpoints hold a timestamp and this route does not read it, so no entry below says when it ran or how long it took." — ruling 6 |

### The "The run, node by node" card

| Field rendered today | Substrate slot |
|---|---|
| title "The run, node by node" | **dissolved.** The narrative is the content column and needs no panel around it — ruling 5 |
| description "The remediation graph's own order, with the evidence each node produced." | the narrative's opening entry, **reworded for position**: prefixed "The entries below are", because the phrase was the subject of a card title that no longer exists and now has to name what it describes — the same class of correction as ruling 11 |
| description "A node marked due after it has already run is a retry the graph owes another visit, not a finished step — the loop is real and this view does not hide it." | the same opening entry, unchanged (protected in claim) |

### `node-sequence.tsx` — the entries

| Field rendered today | Substrate slot |
|---|---|
| `ol` of eight `li`, marker column and body | unchanged shape, now carrying two bracket entries as well — ruling 3 |
| the marker glyph per standing — `✓` / `▶` / `○` | unchanged, and `appearanceOf` is untouched |
| the connector rule between markers | unchanged, and now runs through the bracket entries too |
| `ChangeWash` on a status transition | unchanged, and `node-sequence.test.tsx` holds it |
| `h3` `{node.name}`, mono | unchanged |
| `STANDING_LABEL[node.standing]` beside it | unchanged — `node-standing.ts` is consumed, never re-derived |
| `PURPOSE[name]` beneath it | unchanged |
| `UNKNOWN_NODE` for a node this file does not know | unchanged (protected: "the remediation graph has changed since this view was written") |
| `STANDING_SENTENCE.due_again` on a retried node | unchanged |
| `NodeEvidence` at the foot of the entry | unchanged in placement — the evidence has always been inside its own entry — ruling 10 |
| — (no opening entry) | the opening entry, `◇`, "What arrived" — ruling 4 |
| — (no closing entry) | the closing entry, `◆`, at `closingEntryIndex(nodes)` — ruling 3 |

### `run-outcome.tsx`

| Field rendered today | Substrate slot |
|---|---|
| the bordered panel with an `h2` headline | the closing entry's body, headline at `h3`, no box of its own — ruling 3 |
| "This run is still in flight." / "No outcome has been written yet." | unchanged, in the closing entry |
| "Sync abandoned this run." | unchanged, in the closing entry, **positioned where the run stopped** |
| "An abandoned run is kept rather than hidden: the reason is what teaches routing which change kinds are not mechanically safe." | unchanged |
| the "Reason it was abandoned" label and the reason, mono | unchanged, inside the closing entry |
| its `<Absent>` "the run recorded no reason, which is itself a gap worth chasing" | unchanged |
| "This run opened a pull request." with its `tsc`-and-CI sentence | unchanged |
| "This run reported rather than patched." with its "not an abandonment" sentence | unchanged |
| the "Reason it reported" label and the reason, mono | unchanged |
| its `<Absent>` "the run reported without recording why" | unchanged |
| "This run ended in a way the console does not recognise." with the recorded value | unchanged (protected: the console admitting it is out of date) |
| `BelowThisPanel.inFlight` — "The sequence below is the last state…" | reworded: the entries are no longer below it — ruling 11 |
| `BelowThisPanel.abandoned` — "The attempt is still below in full…" | reworded, same claim, and it now says which entries are which — ruling 11 |
| `BelowThisPanel.opened` — "The pull request is under `open_pr`." | unchanged: "under" names a heading, not a position |
| `BelowThisPanel.unrecognised` — "The sequence below is still what the run produced." | reworded — ruling 11 |
| the `BelowThisPanel` contract itself, and the Pull Request level's four sentences | untouched — that level's file is not opened here |

### `evidence.tsx`

| Field rendered today | Substrate slot |
|---|---|
| the `dl` grid, two columns at `sm` | unchanged |
| `Row` — `dt` in the furniture register, `dd` beneath | unchanged |
| a field's `help` sentence | unchanged |
| `text` values, mono, through `Formatted`/`scalarOrAbsent` | unchanged |
| `Flag` — `PASS`/`FAIL` and the wording | unchanged in content, respelled onto the console's chip anatomy — ruling 12 |
| `Flag`'s non-boolean fallback | unchanged |
| `Block` — `pre`, scrolling, newlines kept | **a titled block with a label strip**, the vendored card anatomy — ruling 10 |
| `Block`'s `<Absent>` for null and for empty | unchanged |
| `ExternalLink` — http/https only, everything else as text | unchanged, and the `asHttpUrl` boundary check is untouched |
| unnamed keys, rendered generically at the end | unchanged |
| every entry of `FIELDS` — eight nodes, seventeen fields, their labels and their help | unchanged, string for string |

### `node-standing.ts`

| Field rendered today | Substrate slot |
|---|---|
| `STANDING_LABEL`, five entries | consumed, not re-derived, not edited |
| `STANDING_SENTENCE`, four entries | consumed, not re-derived, not edited |

### `narrative-order.ts` — new in this port

Nothing here renders. It is the derivation that places the closing entry, and it is tested before
it exists.

| What it answers | Where it lands |
|---|---|
| how many node entries precede the run's closing entry | `closingEntryIndex(nodes)` — ruling 3 |
| what "the run reached this node" means, given five standings | `ran`, `due` and `due_again` are reached; the two never-visited standings are not |
| where the closing entry goes when the run reached nothing | index 0 — before every entry, which is where a `reported` run's decision belongs |

## The rulings

Twelve arrangements had no slot the seven earlier levels had already settled. Their seventy-seven
rulings are not restated: the metric value at `--text-figure`, the accepted collapse of
`variant="grouping"`, `--card-padding-x`, the kept `components/skeleton.tsx`, the untouched
`fact-tile.tsx` and `fact-list.tsx`, the panel name in the furniture register, and the refusal of a
`⋮` overflow menu all apply here unchanged.

**1. The fact rail is a left column, and that is now the standing shape for every detail level.**
The Finding port placed its rail left and left the question open for the two detail levels behind
it. The controller settled it for this task: **details keep the fact rail left**, and the Pull
Request port follows it without re-arguing. The grid is
`lg:grid-cols-[minmax(0,22.5rem)_minmax(0,1fr)]` — the same 360px the direction's first example
names, the same one the Finding level resolved — with the rail carrying `PageHeader`, the facts and
the links, and the narrative in the content column beside it from the top of the page. It stacks to
one column below `lg`.

The reason it is the right shape here rather than merely the consistent one: the narrative is a
long, single-column read of nine to eleven entries. A band across the top would push the first
entry down by the height of a header plus a fact list, and the whole value of this screen is that a
reader can start reading at the top. Measured on the Finding level at 163px; the same arithmetic
applies.

**2. The title takes the display step, loses its suffix, and the question arrives from the
registry.** This level opened on `h1` reading `{findingId} — solution workflow` at `--text-page`,
and never rendered `RouteEntry.question`, which for this route has read *"What did Sync's
remediation graph do about this finding, node by node?"* since the registry landed.

The suffix goes because it is now said twice above the title and once below it: the breadcrumb's
last crumb is "Solution workflow", the sidebar's active item is "Solution workflow", and the
registry's question says what the screen is in a full sentence. A title is the subject, and the
subject is the finding. B116 counts this route off as one more of the nine.

**3. The outcome is an entry in the sequence, placed where the run stopped — and this is the
ruling the level exists to make.**

`RunOutcome` rendered above the eight nodes, in its own bordered panel, and its docstring argued
for that position: *"An abandoned run is not an error to tuck away in a corner … a reader who came
to find out why Sync gave up should not have to scroll the whole run to find out."* That argument
was correct against the alternative it was written against — the reason at the bottom of the page,
after eight nodes. It is not the only way to satisfy it.

Placing the outcome **at the point in the sequence where the run stopped** satisfies it better on
the case that matters. On the seeded abandoned run, static verification fails after three attempts;
the reason now sits directly beneath `static_verify`'s own evidence and directly above
`replay`, `push_branch`, `await_ci` and `open_pr`, each reading *"Never reached — the run ended
before the graph got here."* Four entries that were previously four statements of an unexplained
absence now have their cause one entry above them. The reader who came to find out why Sync gave up
finds it beside the node that gave up, which is a shorter path than the top of the page and a much
shorter one than the bottom.

`closingEntryIndex` is the derivation and it is one line of logic with four cases, so it is a
module with a test rather than an inline expression: the entry goes after the last node the run
reached, where reached means `ran`, `due` or `due_again`. A run that reached everything puts it
last, which is where an `opened` run's "This run opened a pull request." belongs. A `reported` run
reached only `locate`, so its decision sits second, above the seven nodes it explains. A payload
with a reached node after an unreached one — which nothing forbids — puts the entry after the last
thing that actually happened rather than before the first gap.

**What this does not do is hide anything.** The outcome is not behind a disclosure, is not
shortened, and is not in a tooltip. It is the same words in a different position, which is the
restyle `.claude/rules/console-surface.md` permits.

**4. The narrative opens with an entry that says what this screen can and cannot see.** The
direction's first slot is *"what arrived — the finding's signal context"*, and this route's payload
carries none of it: no vendor, no operation, no call site, no vendor change, no rung. What it can do
is point up, which the direction also says (*"link up to the Finding; the breadcrumb carries the
trail"*).

So the opening entry is a link and three honesty sentences, and every one of them was already on
this screen — the checkpointer-is-a-different-database paragraph moves up from the foot of the page,
and the two sentences from the dissolved card's description move in beside it. It reads as the
first thing that happened because it is: a finding arrived, and this is what the console knows
about it here.

The rail also carries the finding as its first fact, as a link. That is not the same claim written
twice: the rail is scanned for the identifier, and the entry is read for what the identifier's
screen holds that this one does not.

**5. The narrative is not inside a panel.** Every other level's content column is a stack of
`MetricPanel`s, and the sequence sat inside a `Card` with a title and a description. It does not any
more. A panel groups a figure with its evidence; the narrative is the whole content column, so a
frame around it draws a box around the page and the panel name would be a second title under the
`h1`. The description that panel carried is not lost — ruling 4 says where it went.

This is the first ported level whose content column holds no panel at all, and it is worth saying
why that is not an inconsistency: the panel is for a screen that answers several questions at once,
and this screen answers one.

**6. There is no clock on this route, and the screen now says so.** The direction asks for each
entry's elapsed time. `WorkflowNode` is `{name, status, standing, evidence}` — no timestamp, no
duration, nothing time-shaped. `WorkflowState` carries none either.
`sync.dashboard.queries.workflow_state` reads one checkpoint row and forwards its channel values;
the row's own `ts` is not forwarded, and a single checkpoint could not give a per-node duration if
it were.

Three substitutes were available and all three are refused. `query.dataUpdatedAt` is when the
console last fetched, which `StaleBanner` already renders and which says nothing about the run.
`RunRow.last_checkpoint_at` is on a different route and is staleness rather than duration — the
fleet screen's own protected sentence says why that distinction is not negotiable. Node order is
not elapsed time, and rendering it as though it were would be the invention this console exists to
refuse.

**B123** is the entry: forward the checkpoint `ts` per node, which the checkpointer holds one row
per hop of and which this route already opens a connection to.

**The sentence that ships has to say which thing has no clock, and the first draft did not.** It
read *"A checkpoint records what a node produced and not when it produced it"*, which is false: a
checkpoint row carries `ts`, and `sync.dashboard.fleet` ships that very field as
`last_checkpoint_at` on the runs route. Written that way the screen claimed the time was never
recorded, where the truth is that this route does not read it — *we could not check* rendered as
*there was nothing to check*, which is the one distinction `.claude/rules/console-surface.md`
exists to keep. It now reads: *"It carries no clock either: the checkpoints hold a timestamp and
this route does not read it, so no entry below says when it ran or how long it took."* One
sentence, and it names the gap as a gap in the read rather than in the data.

**7. A superseded generation cannot be reached from this route, and this level does not go looking
for it.** The direction asks for an abandoned generation to render in sequence, and for a
multi-generation run to summarise a generation to one line that expands in place. The seeded
finding `9f176dea…` is exactly that case: `generation_count` 2, an abandoned first attempt whose
reason is *"static verification failed after 3 attempts"*, and a second that opened a pull request.

`GET /api/workflows/{finding_id}` answers with the newest thread only — its own type's docstring
says so — so the abandoned generation's nodes, its reason and its standings are not on this payload.
The one route that holds them is `GET /api/runs`, and reaching for it here was considered and
refused on three grounds, each sufficient on its own:

- It is **fleet-wide and paged, with no finding filter**. On this seed it returns four rows and
  the answer looks perfect. On a fleet with a thousand runs, generation 0 of this finding is on
  page seventeen, and the level would render "no other generation" for a finding that has one —
  a claim that is wrong more often than it is right, arriving silently.
- `useRuns` takes **no `enabled` option**, and `api/queries.ts` is the data seam this task does
  not open. So the query cannot be gated on `generation_count > 1`: every reader of every workflow
  page would pay a fleet-wide paged request, and it polls at `WORKFLOW_POLL_MS` while any run in
  the fleet is live, to serve a minority case.
- Even at its best it would render a **summary row, not a generation** — outcome, reason and
  staleness, with no nodes and no evidence. The one-line-that-expands the direction describes has
  nothing to expand into.

**B124** is the entry, and it is small: give `workflow_state` a `generations` array of
`{thread_id, outcome, abandon_reason, generation}` from the query it already runs — the
`COUNT(DISTINCT thread_id)` subquery is over exactly those rows. That turns the rail's count into
a list and gives the collapse something true to hold.

What ships instead is the count and the pointer, both of which were already here and are kept
verbatim: *"the most recent of N runs the checkpointer holds for this finding"*, with the fleet
screen linked as where the others are. The Finding level's ruling 5 reached the same place from the
other side, and the two now agree.

**The consequence for the direction's collapse clause is that nothing on this level collapses.**
The current generation is never collapsed, and it is the only generation this route can see — so no
disclosure is added, no expansion state exists, and no search parameter is written. The URL stays
the address of the run and nothing else. The drawer's search-param precedent is not followed
because there is nothing to follow it with.

**8. `StaleBanner` stays where it is and keeps every word.** It is the honesty sentence pair this
level owns — that a failed refresh is the console's failure and not the run's, and that a terminal
run has no poll left to heal it — and neither the wording nor the retry behaviour is touched. It
moves from the top of a single column to the top of the content column, which is the same position
relative to what it qualifies.

The poll itself is untouched: `useWorkflow` still stops on a terminal outcome, still never starts
without data, and `WORKFLOW_POLL_MS` still appears in the in-flight sentence so the interval is a
stated number rather than a mystery.

**9. The pull-request link keeps both of its wordings and loses one word.** The link's text already
follows `outcome` — *"See the pull request's evidence bundle"* on an `opened` run and *"See the
evidence bundle for this run"* on every other — and the comment arguing why is kept, because the
alternative it rules out (a possessive on every run) is still the tempting mistake.

Its note said *"the five nodes below that answer whether this run earned a merge"*. The five nodes
are no longer below it; the link is in the rail and they are in the content column. "Below" is
struck and nothing else moves. This is the same class of correction the Finding port's ruling 7
made to `bindingNullLabel`: a clause naming a position, repointed when the position changed.

**10. A structured block gets a label strip, and this is the one thing taken from the reference's
appearance rather than its structure.** Both direction notes single it out — entry 1's *"Depth is
used once. Code blocks sit on a raised surface with their own label strip"*, and entry 2's
`report_findings` block *"rendered as a titled, structured block with named fields"*. `Block`
rendered a bare `pre` with a `dt` above it; it now renders the vendored `Card` with the field's own
label in the header strip and the `pre` in the body.

What is taken is a convention of the form — a code block that says what kind of thing it is — and
`.claude/rules/interface-originality.md`'s amendment lists exactly this class of thing as
learnable. What is not taken is syntax highlighting, which would be a second colour system on a
console with four reserved colours, and which would have to make a claim about a language the
payload does not name.

`evidence.tsx` is imported by `features/pullrequests/evidence-bundle.tsx`, so restyling `Block`
restyles the Pull Request level's compiler output and replay evidence too. That is the substrate
migration working as intended, exactly as `VendorFindingsTable` was on Fleet, and that level's own
port will find its blocks already correct.

**11. Three of `BelowThisPanel`'s four sentences say "below" and no longer can.** The interface
exists because the panel cannot know what is under it and a default would be a confident claim
about whichever screen forgot to pass one — its docstring records it being wrong exactly that way.
The Solution Workflow's four sentences are written in `workflow-page.tsx`, which is this level's
file, and three of them name a position that has moved.

Each is repointed and none is shortened. The `abandoned` sentence gains rather than loses: it used
to say the attempt was still below in full, and it now says which entries are the attempt and which
are the nodes the run never reached — which is information the old arrangement could not carry,
because there was no "where" for the outcome to be relative to. The Pull Request level's own four
sentences are untouched; that file is not opened.

**12. `Flag` takes the chip anatomy, and a `PASS` is still not a status colour.** It drew
`rounded border border-border`; the console's chip — `RungBadge`, and now the Finding level's
argument-key chips — draws `rounded-control border border-line`. Two class names, the same
correction Signals' ruling 7 and the Finding's ruling 9 made.

The comment above it stays and is the reason this is a chip and not a badge: *"A node's evidence
boolean is a fact this node recorded about itself — not a verdict on the run … `verify_ok: false`
is often the retry loop sending a patch back, working as designed."* `PASS` and `FAIL` are words
with a hairline around them and no hue, on a screen where the four reserved colours are spent only
on a genuine failure of the console.

## What it measured

Chrome, `/findings/9f176dea35907f95beb29553e574a037/workflow` — the richest seeded run and the one
the controller named. It is the only seeded finding with more than one generation
(`generation_count` 2), and the generation this route answers with is the one that ran all eight
nodes and opened a pull request, so it is also the run carrying the most evidence: a routing tier
and row, two prepare flags, an attempt count and strategy, a `tsc` verdict, a replay outcome with a
block of evidence, a branch, a CI URL with its attempt and result, and a pull request with its
number. The old screen was served from a scratch worktree at `ff556f8` on port 5196 and the new one
on 5197, both proxied to the same API on 8787, so the two readings are of one seed.

| | 1440x900 before | 1440x900 after | 1280x800 before | 1280x800 after |
|---|---|---|---|---|
| type range | 1.83:1 | **3.83:1** | 1.83:1 | **3.83:1** |
| type steps | 12 / 13 / 15 / 22 | 12 / 13 / 15 / **46** | unchanged | unchanged |
| side-by-side region placements | 0 | **1** | 0 | **1** |
| `h1` | 22px, 32px tall | 46px, 153px tall | 22px, 32px tall | 46px, 153px tall |
| first heading in `main`, from the page's top | 250px | **40px** | 250px | **40px** |
| last rendered pixel | 1908px | **1741px** | 1908px | **1809px** |
| rail / content column | — | 360px / 705px | — | 360px / 545px |
| horizontal overflow | none | none | none | none |

Three readings need their method stated.

**The first-heading row is the first `h2` or `h3` inside `main`.** On the old screen that is the
outcome banner's headline — "This run opened a pull request." — 250px down, under a breadcrumb, an
`h1` and a paragraph of run prose. On the new one it is "What arrived" at 40px, because the two
columns start level and the narrative no longer waits for a header to finish. That 210px is what
ruling 1's arrangement buys, and it is the same effect the Finding level measured at 163px.

**"Last rendered pixel" is the greatest `bottom` of any element inside `main`**, not
`document.scrollHeight`, which floors at the viewport height. The page is **167px shorter at 1440
and 99px shorter at 1280** while carrying three things it did not carry before — the route's own
question, a Finding row, and a Generations row — and while nothing was deleted. The narrower
content column is why the two figures differ: 545px wraps more prose than 705px.

**The 15px step stays, and this level is the first ported one where that is correct.** On the
Finding level `--text-emphasis` left with the card titles, because a panel name belongs in the
furniture register. Here it is on the narrative's own entry headings — "What arrived", "This run
opened a pull request." — which are read rather than scanned, and `DESIGN.md` assigns type by role.
So this route's ramp is 12 / 13 / 15 / 46 rather than 12 / 13 / 46, which is 3.83:1 against the 3.4
bar `reports/2026-08-06-why-the-console-came-out-flat.md` sets, and one more of the nine B116 counts
off.

**The `h1` takes three lines and 153px**, exactly as the Finding level's does and for the same
reason: a 32-character hex identifier at 46px in a 360px column has no break opportunity, and
`PageHeader`'s own `break-words` is what keeps it inside the rail. Nothing clips at either width and
the document has no horizontal scroll at either.

**One cost is real and is recorded rather than argued away.** The rail ends around 590px and the
narrative runs to 1741px, so a reader who scrolls past the first screen has an empty 360px column
beside them. That is the shape of a detail level whose content is long, it is the same trade the
Finding level took with a much shorter content column, and no fix is applied here: a sticky rail is
behaviour nothing asked for, and the alternative arrangement costs the 210px this port just bought.

## The completeness walk

Every field the old screen asserted, asserted by the new one, read off both screens against the same
seed rather than off the diff. Four states were walked, each on both ports:

- `/findings/9f176dea35907f95beb29553e574a037/workflow` — `opened`, two generations, all eight nodes
  ran, every evidence field the fixture holds.
- `/findings/b45fb667d653b9187fe0d05ffe20a7df/workflow` — `reported`, one generation, `locate` ran
  and the other seven never did. This is the walk that proves ruling 3: the closing entry lands
  second, directly under `locate`'s routing evidence and above seven entries reading "never ran".
- `/findings/443b1719164579873939aaaecfa2902d/workflow` — in flight, `static_verify` due, four nodes
  not reached yet. The closing entry lands fifth, under the due node, above the four that have not
  been reached.
- `/findings/does-not-exist/workflow` — the 404.

Carried unchanged, string for string: the breadcrumb trail and all three crumbs; the run's
`thread_id`; the "most recent of 2 runs the checkpointer holds for this finding" clause and the
fleet link inside it; all four `RunOutcome` headlines walked and their prose; both reason labels and
both reason values; every one of the eight node names, its standing label and its purpose sentence;
every evidence field of every node with its label, its value and its help sentence; the two `PASS`
flags and the `tsc` verdict flag with their full wordings; both external links; the pull-request
link in both of its outcome-dependent wordings; the not-found headline, its detail, its identifier
and its "Check again" button; and the checkpointer-is-a-different-database paragraph with "The
finding itself" still the link inside it.

Changed in rendering and not in content: the outcome moved from a bordered banner above the sequence
to an entry inside it at the point the run stopped; the card that contained the sequence dissolved
and its description became the opening entry; the run's `thread_id` and generation count moved from a
prose line into two labelled rail rows; multi-line evidence gained a label strip on the card plane;
and `PASS`/`FAIL` gained the console's chip radius and hairline.

Reworded, four sentences, each because it named a position that had moved and none shortened: three
of `BelowThisPanel`'s four, and the dissolved card's description, which was prefixed "The entries
below are" — it had been the predicate of a card title and needed a subject once the card was gone.

Gained, three sentences and two rows: the route's own question at the display step; a Finding row in
the rail, as a link; a Generations row that says `1` on a run that previously said nothing about
generations at all; the opening entry's first sentence, *"A finding arrived from the API Dependency
Graph, and this run is what Sync did about it."*; and the no-clock sentence, *"It carries no clock
either: the checkpoints hold a timestamp and this route does not read it, so no entry below says
when it ran or how long it took."*

Lost: three words and a title. The `h1`'s " — solution workflow" suffix (ruling 2, said three times
around it), the word "below" from the pull-request note (ruling 9, no longer true), and the card
title "The run, node by node" (ruling 5, the card it named is gone). No sentence was shortened, none
was collapsed behind a disclosure, and none moved into a tooltip.

**One thing changed because the walk found it.** The 404 rendered the rail's absence phrase as "the
checkpointer holds no run for this finding" on both the Run row and the Generations row, directly
above a panel whose headline is "No remediation run for this finding." — three near-copies of one
sentence in 200 vertical pixels. The rail's phrase is now the short form, "no run for this finding",
which matches the panel's headline and leaves the full explanation in the one place with room for
it. Each row still says which nothing it is, which is what the absence vocabulary requires. This is
the same defect the Finding port's walk found on its own 404, and it arrived the same way.

**One thing the seed cannot walk, and it is worth saying plainly.** No seeded finding's newest
generation is `abandoned` — the four seeded runs are one `reported`, one in flight, and the two
generations of `9f176dea…`, of which this route answers with the `opened` one. So the abandoned
branch of the closing entry was exercised by `node-sequence.test.tsx` and by `narrative-order.ts`'s
own cases rather than in Chrome. The `reported` run demonstrates the identical mechanism against the
same code path — a terminal outcome with a recorded reason, placed where the run stopped, above the
nodes it explains — which is why that finding is the one walked in detail above.

## The protected sentences

One of the seventeen fragments `tests/test_console_honesty_sentences.py` holds lives in the files
this port opened. Every fragment was grepped against `features/workflows/` before the port and
against the whole of `web/src` after it.

| Fragment | Before | After |
|---|---|---|
| `not a failure of the console` | `features/workflows/workflow-page.tsx`, and two files outside this feature | the same three files, the sentence unchanged |

The other sixteen were checked against `features/workflows/` before the port and none of them was
there, so none could be lost by it; all sixteen still have holders elsewhere. The whole file,
seventeen parametrised cases, is green.

The seventeen fragments are not the whole set. Three of the twenty-four catalogued sentences in
`plans/2026-08-05-sync-console-architecture.md:102-207` sit in these files, two of them under the
"the console admits when it is out of date with its own backend" heading, and each was grepped
individually after the port:

| Sentence | Holder |
|---|---|
| `the remediation graph has changed since this view was written` | `node-sequence.tsx`, unchanged |
| `has not caught up with` — the unrecognised outcome | `run-outcome.tsx`, unchanged |
| `not a failure of the console` — the 404 detail | `workflow-page.tsx`, unchanged |

And eight more sentences this level owns that are load-bearing without being catalogued. Each was
grepped after the port and each is unchanged: the standing sentence that refuses a liveness claim
(`not a claim that anything is running`, `node-standing.ts`); the retry sentence
(`the loop is real and this view does not hide it`); the two-databases sentence
(`no indexing timestamp and no binding rung`); both halves of the stale banner
(`the run is still live, so polling continues`, `nothing is polling in the background`); both
missing-reason absences (`which is itself a gap worth chasing`,
`the run reported without recording why`); and the abandonment sentence
(`teaches routing which change kinds are not mechanically safe`).
