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
an `li`. A card inside a hand-drawn frame is two frames claiming one grouping, and the level that
owns the outer one is this one. Ruling 3 removes it.

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
| — (nothing on this level left the console) | the rail's action stack: the pull request on GitHub, an external link — ruling 9 |
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
| each stage's bordered `li` (`rounded border border-border p-section`) | **removed.** The stage is the frame now — ruling 3 |
| stage title, `h3` at `--text-emphasis` | `MetricPanel` label, furniture register, `h2` — rulings 3 and 4 |
| stage blurb, five of them | `MetricPanel` caption, all five verbatim |
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

The stage becomes a `MetricPanel`: the vendored `Card`, the stage title in the header strip at the
furniture register, the blurb as the caption directly under it, and the evidence in the body. The
`li` keeps the list semantics and draws nothing.

Three things this buys beyond removing a frame. The stage title stops competing with the node
evidence's own `dt` labels, because both are now in the furniture register and the panel's is the
one with a rule under it. The five stages become the same object every other ported level's content
column is made of, so a reader moving from the Finding to the Workflow to here meets one panel
anatomy rather than three. And the blurb moves from a paragraph under a heading to a caption inside
the header, which is where `MetricPanel` puts the sentence that says what a panel's contents mean —
this is the same relocation the Fleet port made for six panels at once.

**4. One nesting survives, and it is the right one.** A stage that carries a block field renders a
card inside a card: the stage panel, and `BlockField`'s own titled block around the compiler output
or the replay evidence. That is deliberate rather than overlooked.

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
