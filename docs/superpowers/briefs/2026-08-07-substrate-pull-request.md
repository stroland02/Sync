# The Pull Request on the substrate — the mapping table, and the rulings it forced

Task 6 of `docs/superpowers/plans/2026-08-06-console-supabase-substrate.md`, eighth level. Work
item M7-W180.

The Pull Request level is `/findings/:findingId/workflow/pull-request` — the evidence bundle behind
one remediation run, at an address a reviewer can send to a colleague. It is the ninth level ported
and the last, after Fleet (M7-W172), Codebase (M7-W173), API Services (M7-W174), Signals
(M7-W175), the Binding surface (M7-W176), Errors & Incidents (M7-W177), the Finding (M7-W178) and
the Solution Workflow (M7-W179). `docs/superpowers/briefs/2026-08-07-substrate-fleet.md` is the
parent document and its eleven rulings bind wherever they generalise; the seven levels since add
seventy-six more, and the Finding's thirteen and the Workflow's twelve are the detail-shaped
precedent this level sits beside. This file records only what is new here, or what this level
decided differently, and says which.

Three things make this port different from the eight before it.

**This screen is the product's core claim rendered.** *Nothing reaches a pull request unverified* is
the sentence `CLAUDE.md` puts under "Non-negotiables", and the evidence bundle is what makes it
checkable rather than asserted: the compiler's verdict, the replay's verdict, the branch, the
customer's own CI, and the pull request itself, in the order the graph produced them. Every ruling
below is measured against one question — does a reader still see each stage's verdict beside the
evidence that earned it, and is a stage that produced nothing still *stated* rather than skipped.

**It closes an interim defect the Workflow port ledgered rather than fixed.** M7-W179's ruling 10
gave a multi-line evidence value a label strip on the vendored card's plane, and said plainly that
`features/pullrequests/evidence-bundle.tsx` imports that file and would inherit it. It did — into a
stage that was already drawing its own hand-spelled `rounded border border-border p-section` around
an `li`. Two plain hairline rectangles at two different radii, with nothing to tell them apart, and
the level that owns the outer one is this one. Ruling 3 replaces it with a titled block; ruling 4
states plainly what that does and does not fix, because the count of nested boxes is unchanged and
saying otherwise would be the kind of claim this console exists to refuse.

**Three of the six facts a rail would want are not on this payload, and none is invented.** The
direction's rail for a pull request is *"number, branch, state, opened at, repository, and the
finding it answers"*. `GET /api/workflows/{finding_id}` carries the number and the branch inside
node evidence, carries the state as the outcome the panel already renders, and carries neither a
timestamp nor a repository. Rulings 6, 7 and 8 are what each of those costs and where the fix is.
This is the same shape the Finding port's ruling 3 and the Workflow port's rulings 6 and 7 took,
and it is now the standard shape of a port.

The table below was built by reading `pull-request-page.tsx` and `evidence-bundle.tsx` line by
line, not from memory. Every rendered string, every count, every state branch is a row.

## The mapping table

### `PullRequestPage` — the identifier guard

| Field rendered today | Substrate slot |
|---|---|
| `UnknownRoute` when the URL carries no `findingId` | unchanged, before the query is made |

### `PullRequest` — the page shell

| Field rendered today | Substrate slot |
|---|---|
| breadcrumb trail "Fleet" → the finding id → "Solution workflow" → "Pull request" | `PageHeader` trail, `Breadcrumbs` unchanged, in the rail — ruling 1 |
| `h1` `{findingId} — pull request`, mono, at `--text-page` | `PageHeader` title, mono, at the **display step**, and the trailing " — pull request" is dropped: the breadcrumb's last crumb says it and the registry's question says it again — ruling 2 |
| — (this level rendered no question; `ROUTES` has held one unrendered since the route landed) | `PageHeader` question, `routeQuestion("/findings/:findingId/workflow/pull-request")` — ruling 2 |
| `LoadingState`("the run for finding {findingId}") | unchanged, in the content column |
| `NotFoundState` "No remediation run for this finding, so there is no pull request." with its detail and `identifier` | unchanged, in the content column (protected: "not a failure of the console") |
| its "Check again" button | unchanged, beneath the state |
| `ErrorState`(error, "the run for finding {findingId}") | unchanged, in the content column |
| the run line — `Run {thread_id}`, mono | fact rail, row 4 — ruling 1 |
| "— the most recent of N runs the checkpointer holds for this finding. An earlier generation may have reached a pull request even where this one has not; the fleet screen lists every one." | fact rail, row 5, wording unchanged and still conditional on `generation_count > 1` |
| — (nothing linked up to the finding except the breadcrumb) | fact rail, row 1: Finding, as a link — ruling 1 |
| — (the pull request's number was only ever a row inside the last panel) | fact rail, row 2: Pull request, `#{pr_number}` — ruling 5 |
| — (the branch was only ever a row inside the third panel) | fact rail, row 3: Branch — ruling 5 |
| — (nothing on this level left the console) | the rail's action stack: "Open the pull request", an external link — ruling 9 |
| the closing paragraph, "Read from the checkpointer, the same source as the solution workflow, which shows all eight nodes; this page shows the five that carry the evidence a pull request rests on." | the rail's caption, beneath the facts, verbatim including the workflow link |
| `RunOutcome` with `BELOW`, above the bundle | unchanged: still a panel, still first in the content column — ruling 10 |
| `BELOW`'s four sentences | unchanged, all four, string for string — ruling 10 |
| `EvidenceBundle` | the content column, beneath the outcome panel |

### `evidence-bundle.tsx` — the bundle

| Field rendered today | Substrate slot |
|---|---|
| `Framing`'s `reported` sentence — "No pull request exists for this run. Routing decided no patch was warranted…" | unchanged, above the stages |
| `Framing`'s `abandoned` sentence | unchanged |
| `Framing`'s in-flight sentence — "Whether this run reaches a pull request is not yet decided…" | unchanged |
| `Framing`'s unrecognised-outcome sentence | unchanged |
| `Framing` rendering nothing on `opened`, and the comment arguing why | unchanged |
| `NothingAttempted` — the five node names and "a run that reports rather than patches ends before any of them runs" | unchanged, including all five `<code>` names |
| the `ol` of five stages, in the graph's own order | unchanged as an ordered list — ruling 12 |
| each stage's bordered `li` (`rounded border border-border p-section`) | **removed.** The `MetricPanel` is the frame, and the `li` draws nothing — ruling 3 |
| stage title, `h3` at `--text-emphasis` | `MetricPanel` label, furniture register, `h2` — rulings 3 and 4 |
| stage blurb, five of them | the panel body, first line, all five verbatim — ruling 3 |
| `STANDING_SENTENCE.due_again` on a retried stage | unchanged, inside the panel body |
| `NodeEvidence` for a stage that produced something | unchanged, inside the panel body — `features/workflows/evidence.tsx` is consumed, never opened |
| `EmptyStage`'s "The run carries no node under this name — the remediation graph has changed since this bundle was written." | unchanged (protected in claim) — ruling 11 |
| `EmptyStage`'s "This node ran and produced none of the fields this bundle names — see the run's outcome above for why." | unchanged, and "above" is still true — ruling 10 |
| `EmptyStage`'s `STANDING_SENTENCE[standing]` for the other three standings | unchanged |
| `BUNDLE_STAGES`, its five entries and its `BundleNodeName` type | unchanged |
| — (no row on this level is a table row) | no `⋮` overflow menu, and nothing to hang one on — ruling 12 |

### `bundle-facts.ts` — new in this port

Nothing here renders. It is the derivation the rail reads and the external link is gated on, and it
is tested before it exists.

| What it answers | Where it lands |
|---|---|
| the pull request's number, out of `open_pr`'s evidence | `bundleFacts(nodes).prNumber` — ruling 5 |
| the pull request's address, out of the same evidence, http and https only | `bundleFacts(nodes).prUrl` — rulings 5 and 9 |
| the branch, out of `push_branch`'s evidence | `bundleFacts(nodes).branch` — ruling 5 |
| which nothing a missing number is, in the rail's short form | `noPullRequestPhrase(outcome)` — ruling 5 |
| which nothing a missing branch is | `noBranchPhrase(outcome)` — ruling 5 |

## The rulings

Twelve arrangements had no slot the eight earlier levels had already settled. Their eighty-seven
rulings are not restated: the metric value at `--text-figure`, the accepted collapse of
`variant="grouping"`, `--card-padding-x`, the kept `components/skeleton.tsx`, the untouched
`fact-tile.tsx` and `fact-list.tsx`, and the panel name in the furniture register all apply here
unchanged.

**1. The fact rail is a left column, taken from the standing ruling rather than argued again.** The
Workflow port's ruling 1 records the controller settling it for every detail level: rail left,
`lg:grid-cols-[minmax(0,22.5rem)_minmax(0,1fr)]`, 360px, `PageHeader` inside the rail, content
column beside it from the top of the page, stacking to one column below `lg`. This level follows it
without re-opening it, which is the whole value of a standing ruling.

What the rail holds here is five facts and one link out. Three of them — the finding, the run and
the generation count — are the same three the Workflow level's rail carries, and the wording of the
generations sentence is this file's own rather than that one's, because this page's version says
something extra that is true only here: *"An earlier generation may have reached a pull request even
where this one has not."* That sentence is kept exactly as it was.

**2. The title takes the display step, loses its suffix, and the question arrives from the
registry.** This level opened on `h1` reading `{findingId} — pull request` at `--text-page`, and
never rendered `RouteEntry.question`, which for this route has read *"Did Sync open a pull request
for this finding, and what proof backs it?"* since the route landed.

The suffix goes for the reason the Workflow port's ruling 2 struck its own: it is said three times
around the title — the breadcrumb's last crumb is "Pull request", the sidebar's active item is
"Pull request", and the registry's question says what the screen is in a full sentence. A title is
the subject, and the subject is the finding. B116 counts this route off as the last of the nine.

**3. A stage is a titled block, and the hand-drawn frame around it goes. This is the ruling the
level exists to make.**

`BundleStages` drew each of the five as `<li className="rounded border border-border p-section">`
with an `h3` at `--text-emphasis` inside it. That was a reasonable local composition when it
shipped. It stopped being one on 2026-08-07, when M7-W179 gave a multi-line evidence value the
vendored card's plane and its own label strip: a `replay` stage carrying `replay_evidence`, or a
`static_verify` stage carrying `diagnostics`, then drew a card inside a hand-spelled border. Two
frames, one grouping, and the outer one is not even the substrate's — `border-border` at
`p-section` is a third rounding and a third padding beside the vendored card's own.

The stage becomes a `MetricPanel`: the vendored `Card`, the stage title alone in the header strip at
the furniture register, and the blurb, the retry sentence and the evidence in the body. The `li`
keeps the list semantics and draws nothing.

Two things this buys beyond removing a frame. The stage title stops competing with the node
evidence's own `dt` labels, because both are now in the furniture register and the panel's is the
one with a rule under it. And the five stages become the same object every other ported level's
content column is made of, so a reader moving from the Finding to the Workflow to here meets one
panel anatomy rather than three.

**The blurb stays in the body rather than becoming the panel's caption, and the reason is
arithmetic.** `MetricPanel`'s content is a `gap-section` column and `NodeEvidence` carries its own
`mt-section`, so a panel handed the blurb and the evidence as two siblings spends both and doubles
every gap inside a stage. The body is therefore one child, and the spacing inside a stage is
unchanged from before the port. `features/workflows/evidence.tsx` owns that margin and is another
level's file, so the fix is on this side of the boundary rather than in it.

**4. One nesting survives, the box count does not change, and the honest statement of what this
port fixes is narrower than "one frame instead of two."** A stage that carries a block field still
renders a box inside a box: the stage panel, and `BlockField`'s own titled block around the compiler
output or the replay evidence. Measured in Chrome on the seeded `opened` run, the number of bordered
elements with a bordered ancestor inside `main` is the same before and after.

What changed is that the two boxes stopped being the same box. Before, both were a plain hairline
rectangle at two different radii with nothing to tell them apart, and the screenshot reads as a
rectangle that accidentally acquired another rectangle. After, the outer one carries a label strip
with a rule under it — the panel anatomy every other ported level uses — and the inner one is
visibly an artifact sitting inside a named stage. Depth still claims a relationship, and now the
relationship is legible.

The two are not the same claim at two depths. The panel is *a stage of the run* — "What replay
found", with its verdict and its reason in the definition list. The block is *one verbatim artifact
the stage produced*, and the reason M7-W179 gave it a strip at all is that a reader recognises a
code block as a code block before reading a character of it. Flattening the block back to a bare
`pre` to avoid the nesting would undo that ruling from outside the file that made it; flattening the
stage instead would leave five verdicts running together in one column, which is the arrangement
this level's whole argument is against.

The Workflow screen reaches one depth on the same evidence because its narrative deliberately has no
panel around it (that level's ruling 5), and its entries are one reading rather than five findings.
Two screens, two shapes, one anatomy — which is what consistency means here.

**5. The rail's facts are lifted out of node evidence, so the lift is a module with a test.**
`pr_number`, `pr_url` and `branch` are not fields on `WorkflowState`. They are keys inside
`nodes[].evidence`, which is `Record<string, unknown>` — the transport does not promise a type, a
shape, or that the key is there at all. Reading three of them for a rail is a derivation with
several wrong answers available (a number that is an object, a URL that is not one, a node the
payload does not carry), so `bundle-facts.ts` is where it happens and `bundle-facts.test.ts` is
written first.

The two absence phrases live there too, for the reason both earlier detail ports had to learn the
hard way on their 404 walk: a rail row's absence must say *which* nothing it is, and must say it in
the short form. A pull request that is missing because routing decided against a patch, missing
because the run was abandoned before it got there, and missing because the run has not got there
yet are three different facts. The long form of each is already on screen, once, in the framing
sentence and the outcome panel; the rail carries the clause.

**6. There is no State row in the rail, and this is the second detail level to refuse one.** The
direction asks for it. `RunOutcome` renders it as the first thing in the content column, at `h2`,
with its reason and its `BELOW` sentence — and at `lg` that panel is level with the rail, so a
"State: opened" row would be the same fact twice, six inches apart, at two weights. Fleet's ruling 2
is the rule and the Workflow level's rail made the identical refusal.

**7. The repository is not on this payload, and it is not parsed out of the pull request's URL.**
The direction asks for it, `sync.remediate.state` carries `repo: RepoRef` as a channel value of
every run, and `workflow_state` forwards eleven other channel values and not that one. So the
checkpoint holds the answer and the route does not read it.

The tempting substitute is the one to name: `pr_url` on the seeded run is
`https://github.com/example/repo/pull/101`, and a repository name can be cut out of that with two
`split` calls. It is refused. That URL is a forge's address, not a schema — the path shape differs
between forges, an enterprise host puts the owner somewhere else, and the console would be
inventing a field by pattern-matching a string the payload never labelled. A repository name that is
right on GitHub and silently wrong on anything else is worse than an absent row, because an absent
row is a question and a wrong one is an answer. **B125** is the entry, and it is a one-line change to
a dict the query already builds.

**8. There is no clock here either, so no "opened at" row.** The direction asks for it and the
Workflow port already filed the gap: `workflow_state` reads one checkpoint row and does not forward
its `ts`, and a single checkpoint could not date the `open_pr` hop even if it did. **B123** is that
entry and it covers this level unchanged — the fix is per-node timestamps, and the moment they
exist the pull request has an opened-at.

The three substitutes are refused for the reasons that file states: `query.dataUpdatedAt` is when
the console fetched, `RunRow.last_checkpoint_at` is staleness rather than an event time and belongs
to a different route, and node order is not a clock. This level adds nothing to that argument; it
declines to invent a different answer to the same question, which is the point of a backlog entry
being shared.

**9. The link out is plain, is gated on a URL that survives the boundary check, and is not the
`open_pr` panel's row said twice.** This is the one level in the console with somewhere to go
outside it, and a reviewer's next action after reading the bundle is to open the pull request. The
link is in the rail's action stack, under the facts, worded as its destination and carrying no icon
— `lucide-react` is in the tree, and the icons already in use are `components/status.tsx`'s four
tone glyphs and the chassis's navigation set. Adding a glyph here would be a fifth vocabulary for
one link.

It reads *"Open the pull request — leaves the console for the forge it was opened on."* and names no
forge, for ruling 7's reason applied to a word rather than to a field: the payload says which URL,
not whose. GitHub is what the fixture happens to hold.

`bundleFacts` returns `prUrl` only for `http:` and `https:`, which is the same boundary check
`features/workflows/evidence.tsx`'s `asHttpUrl` applies to the same value. The check is duplicated
rather than shared, and that is worth stating plainly: `asHttpUrl` is not exported, and
`features/workflows/` is another level's directory that this task does not open. The two copies are
eleven lines and they are the kind of duplication `CLAUDE.md` warns about, so **the duplication is
recorded in B125 alongside the repository field** — one of them should be a `lib/` boundary helper
the next time either file is opened for another reason.

That the `open_pr` panel also renders `pr_url` is not the same claim written twice, by the same
argument the Workflow port's ruling 4 used for its Finding row: the rail is *scanned* for where to
go next, and the panel row is *read* as the artifact the run recorded, under a label that says so.
One of them is navigation and one is evidence.

**10. `RunOutcome` stays a panel here, and all four `BELOW` sentences survive intact.** The Workflow
port moved its own copy into the narrative and repointed three of its four sentences because they
named a position that had moved. Nothing moved here: the outcome is still the first thing in the
content column and the five stages are still under it, so "the five nodes below", "the last of the
five panels below" and "see the run's outcome above" are all still true. The interface's own
docstring is what makes that checkable — `BelowThisPanel` is required rather than defaulted
precisely so each screen states its own geometry, and this screen's geometry did not change.

`frame` defaults to `"panel"`, so this level passes nothing and gets the box. That default exists
because of this page.

**11. `EmptyStage` keeps its paragraphs and does not become an `EmptyState`.** The Finding port's
ruling 13 turned an `<Absent>` inside a paragraph into an `EmptyState`, and the obvious question
here is why the same move is not made for a stage that produced nothing.

Because they are different kinds of nothing. `EmptyState` takes a headline and a detail and is the
answer *an empty set* gets — "No vendor change names this call site." plus why. A stage with no
evidence is not an empty set; it is one of four distinct claims about a node, each already worded
once in `node-standing.ts` or in this file, and each a single sentence with no second sentence to
put under it. Splitting one of them into a headline and a detail would mean writing prose that does
not exist to fill a slot, and collapsing the four into one headline is the exact "nearly right
label" defect the component's own docstring was written to stop. They stay as they are, inside the
panel body, where the stage's own title already says which stage is silent.

**12. No `⋮` overflow menu, and this level has less to hang one on than any other.** Every earlier
level refused it because a row had one action or none. This level has no table and no rows: five
panels and a definition list. The vendored `dropdown-menu` is not imported here either.

The `ol` stays an `ol`. The graph's order is a fact about the run — `sync.dashboard.queries` returns
`WORKFLOW_NODES` order and this file renders five of them in it — so the list is ordered in the
markup as well as on screen, which is what a screen reader needs to hear.

## What it measured

Chrome, `/findings/9f176dea35907f95beb29553e574a037/workflow/pull-request` — the richest seeded pull
request, and the only run in the fixture that has one. It ran all eight nodes and opened
`https://github.com/example/repo/pull/101`, so it is the run carrying the most of what this level
exists to show: a `tsc` verdict, a replay outcome with its reason and a block of evidence, a branch,
a CI URL with its attempt and result, and the pull request with its number. It is also the only
seeded finding with more than one generation (`generation_count` 2). The old screen was served from
a scratch worktree at `cb55ddf` on port 5198 and the new one on 5199, both proxied to the same API
on 8787, so the two readings are of one seed.

| | 1440x900 before | 1440x900 after | 1280x800 before | 1280x800 after |
|---|---|---|---|---|
| type range | 1.83:1 | **3.83:1** | 1.83:1 | **3.83:1** |
| type steps | 12 / 13 / 15 / 22 | 12 / 13 / 15 / **46** | unchanged | unchanged |
| side-by-side region placements | 0 | **1** | 0 | **1** |
| `h1` | 22px, 32px tall | 46px, 153px tall | 22px, 32px tall | 46px, 153px tall |
| first heading in `main`, from the page's top | 266px | **57px** | 266px | **57px** |
| last rendered pixel | 1627px | **1431px** | 1627px | **1483px** |
| rail / content column | — | 360px / 705px | — | 360px / 545px |
| horizontal overflow | none | none | none | none |

Three readings need their method stated.

**The first-heading row is the first `h2` or `h3` inside `main`.** It is the same heading on both
screens — "This run opened a pull request." — which makes the comparison clean: 266px down on the
old one, under a breadcrumb, an `h1` and a paragraph of run prose, and 57px down on the new one
because the rail and the content column start level. That 209px is what ruling 1's arrangement buys,
and it is the same effect the Finding level measured at 163px and the Workflow level at 210px.

**"Last rendered pixel" is the greatest `bottom` of any element inside `main`**, not
`document.scrollHeight`, which floors at the viewport height. The page is **196px shorter at 1440 and
144px shorter at 1280** while carrying four things it did not carry before — the route's own
question, a Pull request row, a Branch row and a Finding row — and while nothing was deleted. The
narrower content column is why the two figures differ: 545px wraps more prose than 705px.

**The old screen measured identically at both widths**, because it was a single column already
capped at the prose measure, so nothing about it reflowed between 1440 and 1280. Every difference in
the table's last two columns belongs to the new arrangement.

**The `h1` takes three lines and 153px**, exactly as the Finding and Workflow levels do and for the
same reason: a 32-character hex identifier at 46px in a 360px column has no break opportunity, and
`PageHeader`'s own `break-words` is what keeps it inside the rail. Nothing clips at either width and
the document has no horizontal scroll at either.

**The 15px step stays.** `--text-emphasis` is on the outcome panel's headline, which is read rather
than scanned — the same reading the Workflow port made of its narrative entry headings. So this
route's ramp is 12 / 13 / 15 / 46, which is 3.83:1 against the 3.4 bar
`reports/2026-08-06-why-the-console-came-out-flat.md` sets. This is the ninth and last of the routes
B116 counts off.

**One cost is real and is recorded rather than argued away.** On the `opened` run the rail ends
around 800px and the content column runs to 1431px, so a reader who scrolls past the first screen has
an empty 360px column beside them. That is the shape of a detail level whose content is long, it is
the same trade both earlier detail levels took, and no fix is applied: a sticky rail is behaviour
nothing asked for.

## The completeness walk

Every field the old screen asserted, asserted by the new one, read off both screens against the same
seed rather than off the diff. Four states were walked, each on both ports:

- `/findings/9f176dea35907f95beb29553e574a037/workflow/pull-request` — `opened`, two generations, all
  five stages carrying evidence, one block field.
- `/findings/b45fb667d653b9187fe0d05ffe20a7df/workflow/pull-request` — `reported`, one generation,
  the framing sentence and `NothingAttempted` in place of the five stages.
- `/findings/443b1719164579873939aaaecfa2902d/workflow/pull-request` — in flight, `static_verify`
  due, four stages not reached yet, five empty stages each saying which nothing it is.
- `/findings/does-not-exist/workflow/pull-request` — the 404.

Carried unchanged, string for string: the breadcrumb trail and all four crumbs; the run's
`thread_id`; the generations clause including *"An earlier generation may have reached a pull request
even where this one has not"* and the fleet link inside it; all four `RunOutcome` headlines walked
and their prose; the reason label and the reason value on the `reported` run; all four `BELOW`
sentences; all four `Framing` sentences and the `opened` case rendering none; `NothingAttempted` with
its five node names in mono; every one of the five stage titles and blurbs; every evidence field of
every stage with its label, its value and its help sentence; the `tsc` verdict flag and both external
links; the "graph has changed since this bundle was written" sentence; the "see the run's outcome
above for why" sentence; all four `STANDING_SENTENCE` wordings on the in-flight run; the not-found
headline, its detail, its identifier and its "Check again" button; and the
checkpointer-is-the-same-source paragraph with "the solution workflow" still the link inside it.

Changed in rendering and not in content: the five stages are titled blocks on the card plane rather
than bordered list items with an emphasis heading, and their blurbs sit in the panel body under the
label strip; the run's `thread_id` and generation count moved from a prose line into two labelled
rail rows; and the checkpointer paragraph moved from the foot of the page to the rail, where it is
beside the facts it describes rather than under the evidence it does not.

Gained: the route's own question at the display step; a Finding row in the rail, as a link; a Pull
request row reading `#101`; a Branch row reading `sync/fix-post-charges-param`; a Generations row
that reads `1` on a run that previously said nothing about generations at all; and one external link,
"Open the pull request", the only link in the console that leaves it.

Lost: two words. The `h1`'s " — pull request" suffix, which ruling 2 strikes because it is said three
times around the title. No sentence was shortened, none was collapsed behind a disclosure, and none
moved into a tooltip.

**One thing changed because the walk found it.** The in-flight rail read *"— not opened yet — this
run is still in flight"*, which is the absence glyph's own em dash followed by a second em dash four
words later. Two dashes in a six-word clause reads as a fault in the value rather than as a sentence,
so both in-flight phrases were rewritten without one: *"the run has not opened one yet"* and *"the
run has not pushed anything yet"*. Each still names the state and still refuses finality, which is
what `bundle-facts.test.ts` asserts rather than the wording.

**One repetition is accepted rather than fixed, and it is worth naming.** On the 404 all four
query-answered rail rows read *"— no run for this finding"*, because that is the one fact and every
row has to say which nothing it is. It is already the short form — it matches the panel headline
below it word for word, which is the correction both earlier detail walks landed on — and shortening
it further would stop it saying which nothing it is. Four rows is more than the Workflow level's two,
and the alternative is a rail row with no answer in it, which is worse.

**One branch the seed cannot walk.** No seeded finding's newest generation is `abandoned` — the four
seeded runs are one `reported`, one in flight, and the two generations of `9f176dea…`, of which this
route answers with the `opened` one. So `RunOutcome`'s abandoned branch, `Framing`'s abandoned
sentence and `noPullRequestPhrase("abandoned")` were exercised by `bundle-facts.test.ts` rather than
in Chrome. The `reported` run demonstrates the identical mechanism against the same code path — a
terminal outcome with a recorded reason, the framing sentence that follows it, and a rail row saying
which nothing the pull request is.

## The protected sentences

One of the seventeen fragments `tests/test_console_honesty_sentences.py` holds lives in the files
this port opened. Every fragment was grepped against `features/pullrequests/` before the port and
against the whole of `web/src` after it.

| Fragment | Before | After |
|---|---|---|
| `not a failure of the console` | `features/pullrequests/pull-request-page.tsx`, and two files outside this feature | the same three files, the sentence unchanged |

The other sixteen were checked against `features/pullrequests/` before the port and none of them was
there, so none could be lost by it; all sixteen still have holders elsewhere. The whole file,
seventeen parametrised cases, is green.

The seventeen fragments are not the whole set. Eleven more sentences these two files own are
load-bearing without being catalogued, and each was grepped after the port and is unchanged: the
"remediation graph has changed since this bundle was written" admission; the "see the run's outcome
above for why" pointer that tells a node that ran and produced nothing apart from one that never ran;
all four `BELOW` sentences, which name this screen's geometry and are the reason `BelowThisPanel` is
required rather than defaulted; all four `Framing` sentences, which stop a `reported` run's page
being headed by a promise of a pull request; and `NothingAttempted`, which keeps the five node names
visible on the one run that reached none of them.
