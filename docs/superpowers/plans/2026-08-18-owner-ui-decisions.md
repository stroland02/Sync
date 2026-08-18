# Owner UI decisions, 2026-08-18 — twelve answers, and what each one settles

Asked as multiple choice so nothing here is a coordinator's guess. **Each answer below is the owner's
selection; the consequence beneath it is mine and is reversible.**

## Structure

**1. First run shows the full console with empty states.** Sidebar and every page visible before a
workspace exists, each saying what it would show. *Consequence:* every screen needs a real
no-workspace state — this is not a gate on the app, it is a state of it.

**2. The Overview leads with fact tiles beside the dependency graph.** Last indexed, call sites,
vendors, bindings by rung, open findings; graph to the right. Findings below. *Consequence:* the
graph panel is above the fold on the first screen, so it is not optional.

**3. The workflow reply box is free text that resumes the run**, exactly as the reference draws it.
*Consequence:* it needs `M10`'s resume-on-review-comment wired, not just rendered.

**4. Long lists are dense tables with a detail drawer.** Click a row, the drawer opens, you keep your
place. *Consequence:* one table component and one drawer, shared across findings, call sites,
bindings, runs.

## Visual

**5. Colour is rich — vocabularies, accents, and data visualisation.** *Consequence, and this is the
one to hold carefully:* a chart may use a multi-hue series for **findings by kind** because those are
categories. **It may not use a red-to-green ramp**, because that reintroduces the good-versus-bad
axis this console refuses. Categorical palettes yes; sequential-severity palettes no.

**6. Vendor logos are shown, fetched.** Small, for identification. *Consequence:* this reverses a
lane's refusal, which was reasoned but is now overruled by the owner. Fetch from a well-known
endpoint, degrade to a monogram when there is none, never redraw a mark.

**7. Density is dense — more on screen.** Tight rows, small type, minimal padding, no page headers.
*Consequence:* `DESIGN.md`'s spacing tokens tighten, and every change carries its contrast arithmetic
against the 5.05:1 floor as usual.

**8. The indexing canvas draws the file tree with edges out to vendors.** *Consequence:* it is framed
as *your codebase*, not as Sync's model of it — `src/api/billing.ts ──▶ stripe`. This is a different
build from the schema-visualiser shape and closer to what a reader already understands.

## Navigation and content

**9. The sidebar lists workspaces, and the current one expands to show its pages.** Orca's nested
disclosure. *Consequence:* this is compatible with `M0-W332` — there is still one set of pages, they
just live under the workspace that owns them. **Workspace creation is a `+` in that rail.**

**10. About covers the glossary and how the pipeline works** — index, signal, detect, remediate,
verify; what each stage reads and writes. *Consequence:* bounded. Not the gates, not the refusals,
not the quickstart.

**11. Empty states show the shape the screen would take** — a greyed skeleton with the reason
overlaid. *Consequence:* this is the strongest possible form of absence-versus-zero, because the
reader sees what is missing rather than being told. **The reason text stays exact:** *telemetry never
attached* is not *no data*.

**12. If only one screen is flawless on Wednesday, it is the solution workflow.** *Consequence:* Lane
B's ordering is confirmed — routes and sidebar first because they block everything, then the
workflow, and the workflow gets whatever time is left rather than being traded away.

## What did not change

The three refusals stand: no confidence scalar on the workflow, no health tile on the Overview, no
status dots in the rail. Answer 5 makes colour richer and answer 6 overturns a lane's judgement, but
neither touches what the console is allowed to claim.

## Round two — eight more, 2026-08-18

**13. The dependency graph draws everything, with pan, zoom and a minimap.** *Consequence:* it needs
a real canvas with viewport culling, not a static SVG. This is the largest single build on the list
and it sits above the fold on the first screen, so it is not deferrable.

**14. The Activity tab shows node summaries that expand to their tool calls.** One line per graph
node with its outcome; click to open the detail beneath. *Consequence:* scannable first, complete on
demand — and the expansion is where the evidence lives.

**15. Findings group by kind, breaking first**, under a triage header carrying each count. *That is
the advisor shape*, applied to the thing this product exists to surface.

**16. Creating a workspace accepts a local path or a git URL.** *Consequence:* Sync clones when given
a URL — which is the demo case, pointing it at something public on the spot.

**17. Settings uses a left sub-nav, one group at a time.** Codebases, Pull requests, Adapters,
Connection, About.

**18. Signals leads with attached integrations grouped by role** — vendor, signal source, human
surface — which is what the screen is already built around, so this confirms rather than changes it.

**19. Indexing finishes on the canvas**, not the Overview. *Consequence, and it raises the canvas's
priority again:* the file tree with its vendor edges is the payoff screen for the one-command
install. **The `is this real` moment lands here.**

**20. Where the mock conflicts with any of these answers, the answer wins.**

## The authority order, now settled end to end

`M0-W325` raised the mock to primary for everything it draws. **Answer 20 puts these decisions above
it.** So, highest first:

1. **The owner's decisions in this document.**
2. **The specification** for the hierarchy (`console-hierarchy.md`), and `CLAUDE.md` for what may be
   claimed. *Neither is overridden by anything above.*
3. **The mock**, for layout — grid tracks, gaps, adjacency, composition.
4. **Everything else.**

**Recorded conflicts to resolve the mock's way losing:** it draws a Fleet root (answer: workspace-
scoped) and page headers (answer: removed). A lane finding a new conflict records it here rather than
resolving it silently.

**Fourth conflict, recorded by Lane C, `CI-W384` — nothing exposes the customer's code or the
patch, and it blocks two decisions rather than a drawing.**

This one is not the mock losing. It is three things wanting one capability that does not exist:

- **Decision 21** — *a finding's drawer opens on the code, call site highlighted*.
- **Decision 26** — *the Findings tab reads narrative, then **diff**, then evidence*.
- The mock's `08-pull-request` **"The patch"** panel, with per-file hunks and line numbers.

**Checked against all nineteen routes rather than assumed.** None serves source, a diff, or the
patch. `GET /api/workflows/{finding_id}` is the closest and its nodes carry `branch`, `pr_url`,
`ci_url`, `replay_evidence`, `routing_row` and `tier` — every fact *about* the edit and no part of
the edit itself. `sync.dashboard.queries` reads `pr_url` and `pr_number` out of the checkpoint, and
`evidence-bundle.tsx` already says so on screen.

**So this is an API item before it is a console item, and no lane can start the console half.**
Lane B cannot build the drawer, and this lane cannot build the patch panel; both would be inventing
a payload. It is recorded here rather than attempted because the decisions are the highest
authority and two of them are, today, unbuildable.

**What it needs, stated so whoever picks it up is not designing from scratch:** a route that returns
the patch for a finding — the unified diff the run produced, or the file and the hunk — and, for
decision 21, the source lines around a call site with the line marked. Both exist in the graph and
the checkpointer; neither reaches the transport. **Care is owed on one point:** the console's
read-only guarantee is enforced by `test_no_route_reaches_past_the_read_surface`, and serving
customer source is still a read, but it widens what a console session can see from *facts about a
repository* to *the repository*. That is a deliberate decision rather than a detail.

**Third conflict, recorded by Lane C, `CI-W378` — the pull request screen's approval bar.**
`screens/08-pull-request.png` draws a full-width bar under the header offering **Abandon**,
**Request changes** and **Approve**, with the sentence that approval is a standing instruction and
Sync merges the moment CI reports green. It is the most prominent element on that screen.

**Sync cannot honour any of the three.** The API is read-only by guarantee, enforced by
`tests/test_api_routes.py::test_no_route_reaches_past_the_read_surface`. Three buttons that do
nothing is the smaller problem; the sentence beside them claims Sync merges on a standing
instruction, which is a capability claim the product does not have.

**Resolved the mock's way losing**, on authority 2 rather than 3: `CLAUDE.md` governs what may be
claimed, and `.claude/rules/interface-originality.md` refuses "any claim their screen makes that our
data cannot support" regardless of how good the reference is. The evidence bundle's layout was ported
(`CI-W375`); the bar was not built.

**What would retire this conflict:** a write surface. Decisions 23-24 select *tier 0 runs free, agent
tiers ask first*, which needs a control that starts a run — so the console is getting an action
surface, and when it exists this bar is buildable and should be revisited. Until then the refusal
stands and it is a product fact rather than an omission.

## Round three — eight more, and one revises a round-two answer

**21. A finding's drawer opens on the code, call site highlighted.** *Consequence:* the drawer needs
real source with the line marked — what a developer wants first is their own code, not our account of
it.

**22. The install command is `npx`, from the repo.** *Consequence:* confirms `M0-W312`'s target and
kills the alternatives. Docker stays the one prerequisite; `npx` is the doorbell.

**23-24. Auto-remediation: tier 0 runs free, agent tiers ask first — and this supersedes the
round-two answer.** Round two selected *run everything, stop before the PR*; the follow-up on spend
selected *tier 0 free, ask before agent tiers*. **The later answer governs**, and it is the better
one: codemods cost nothing and demonstrate the loop, while agent runs are a spend the owner approves
in one click knowing the count.

> `✓ 4 fixed by codemod (no model cost)` · `11 findings need an agent run — [Run all] [Run selected]`

**25. A stale index re-indexes automatically on open**, with progress and findings appearing as it
completes. *Consequence:* the console never shows findings against code that has moved without
saying so — but it costs time on every open, so the progress state must be good.

**26. The Findings tab reads narrative, then diff, then evidence.** *Consequence:* this mirrors the
reference incident view's summary → root cause → code order, **and the narrative is where the rung
goes instead of a confidence score.**

**27. One command palette holds everything** — workspaces, pages, vendors, findings, call sites.
*Consequence:* the palette becomes the primary find surface, so its index must cover data and not
only routes.

**28. Notifications are a toast plus a persistent sidebar count.** *Consequence:* the count is a
number, not a dot — which keeps it on the right side of the no-status-dot rule.

## Standing constraint on all of the above

**Nothing here relaxes the three refusals.** Auto-run makes more runs; it does not make a confidence
score. A sidebar count is a count; it is not a health indicator. The narrative carries the rung.

## Round four — four more, and two are structural rather than visual

**29. The Vendor page leads with your exposure, then their change history.** Operations you call with
site counts and rungs first; their version and deprecation timeline below as the reason findings
appeared. *Consequence:* the page answers *what does this vendor cost me* before *what has this
vendor done*.

**30. Runs gets its own page in the sidebar**, filterable by outcome and tier, alongside the
per-finding path. *Consequence:* a new route, so it is Lane B's — and it is the natural home for the
abandon-reason distribution from the dashboard plan.

**31. A workspace may hold several repositories — and this is a data-model change, not a UI one.**

**This amends `M0-W332`, which said a workspace is backed by a codebase.** It is backed by *one or
more*. The console today scopes through `call_site.repo_id`, which reaches exactly one repository;
a workspace spanning three needs an entity above that, and every scoped query becomes *the
repositories in this workspace* rather than *this repository*.

**Ship the one-repository case first and build the model to hold N.** The URLs, the schema and the
scoped queries take a workspace identifier now, even while every workspace contains exactly one
repository — because retrofitting a level above a scope is the migration this project least wants in
its last two days. *Owner asked for several; this delivers several without betting Wednesday on it.*

**32. The demo opens by typing the install command.** `npx sync-console`, cold start, point it at a
repository, watch the canvas draw. *Consequence, and it reorders the board:* **Lane C's `npx` → Docker
chain is now the literal first thirty seconds of Wednesday.** It stops being packaging and becomes the
opening argument — if that command does not work, nothing after it is seen.

---

## Ledger: the indexing canvas keeps decision 8's framing and gains the operation level

**Ruled 2026-08-18 by the coordinator, on Lane I's escalation, and reversible.**

**What happened.** I dispatched the indexing canvas citing
`references/direction/supabase-05-schema-visualizer.png` and a vendor to operation to call site
topology. Lane I refused to build it and escalated, because **decision 8 does not merely prefer the
file tree -- it names that shape and rejects it**: *"This is a different build from the
schema-visualiser shape and closer to what a reader already understands."* Decision 19 makes the file
tree the payoff screen for the one-command install, and `M14-W386` had already deleted
`dependency-canvas.tsx` on exactly that ruling.

**Decided.** Build `file -> operation -> vendor` -- `src/api/billing.ts -> PostCharges -> stripe`.

**Decided against**, and this is the part worth keeping: rebuilding the vendor-first canvas. It would
have reverted `M14-W386` and decisions 8 and 19 on a coordinator's dispatch, which is not an
authority that outranks an owner decision.

**Why the reconciliation is better than what I asked for.** The screen stays the reader's own
codebase rather than Sync's model of it, which is decision 8's whole point. Adding the operation
level puts a rung on **every** edge; the two-level `file -> vendor` shape could only carry one at the
end. My constraint was that every edge carries its rung, and Lane I's shape satisfies it more
completely than mine did.

**Not a conflict, on inspection.** Colour on the rung: `DESIGN.md:114` keeps it monochrome but
allows *"a single-hue ordinal ramp with no good end, never the status hues"*. That and the dispatch's
"colour may encode the rung" are the same requirement, with the word always present so the label
survives without colour.

**The finding underneath, which is larger than the topology question.** The canvas is fed by
`use-repository-risk-rows.ts`, composed from **open findings**. A screen whose job is to show what
the *index* saw is drawing what the *detectors* flagged -- a subset that moves every time a finding
closes. **It would quietly redraw itself when nothing about the codebase had changed.** Lane I is
building the route that lists every indexed call site regardless of finding status; the `SCOPE_NOTE`
stays until that is true and is deleted then, not left beside the fixed thing.


---

## Round five: decisions 33-36, owner-selected 2026-08-18

**33. First run shows a numbered checklist of what happens next, not live indexing and not the real
layout.** Four steps — installed, connect GitHub, choose a codebase, run the first index — with
`Nothing has been indexed yet.` beneath. **Rejected: the self-drawing canvas**, which would have been
the prettier demo and is the wrong first screen, because a person who has just run one command needs
to know what to do rather than watch something happen. **Rejected: the real layout with every tile
reading "not yet indexed"**, which is honest and gives a newcomer no route forward.

**Consequence for the install story.** Decision 19 makes the file tree the payoff for the
one-command install; **33 places a step before it**. The payoff still lands, after step 4, and the
canvas is what step 4 produces rather than what step 1 shows.

**34. A row opens a drawer over the table, with `Open full page` inside it.** The table stays behind
and scroll position survives — which is the whole reason, because these lists are hundreds of rows
and losing your place in one is the cost that makes people stop clicking. `interface-originality.md`
already lists *a detail that opens in a drawer instead of navigating away* among the conventions of
the form. **Rejected: expand-in-place**, too cramped for evidence; **rejected: navigate-away as the
default**, kept as the escape hatch inside the drawer.

**35. One accent hue for interaction, and no tinted surfaces.** The accent takes links, focus rings,
primary buttons and the active nav rail. The two closed vocabularies keep their own colour — change
kind, and the rung's single-hue ordinal ramp. **Cards, panels and headers stay grey.** So "bland" is
answered by giving colour a *job* rather than by spreading it: every coloured thing on screen is
either something you can act on or a value from a named vocabulary, and nothing is coloured for
decoration.

**36. Loading renders the word `loading…` where the value goes. No skeletons.** Chosen over
skeletons, which are the industry default. **The reason is this product's reason:** a grey block in
the shape of a number is a shape the reader completes, and a screen that refuses to let absence look
like zero cannot then let *pending* look like a populated layout. The word is never mistaken for a
value. **Rejected: keeping stale data dimmed**, which shows a figure that is no longer known to be
true.

**This is a fourth state, and it must not collapse into the other three.** Never-measured, measured
zero, cannot-tell, and now *not-yet-arrived* are four different facts and each renders as itself.

## Round six: decisions 37-40, owner-selected 2026-08-18

**37. The reply box re-enters the live run.** The agent takes the reply as a turn and keeps working;
the transcript shows `agent picked this up — running`. **Rejected: posting to the pull request**,
which would have reused `M10`'s resume-on-review-comment path and kept one channel — rejected because
it routes a console action through GitHub and back, and the reviewer is already here. **Rejected:
queue-for-next-attempt.**

**The consequence, and it is not optional to answer.** Re-entering a *live* run says nothing about a
run that has finished or abandoned, and those are the runs a reviewer most wants to argue with. **The
control does not disappear** — decision 2's rule stands: *state the refusal, do not omit the
control*. A finished run shows the box disabled with the reason, and `Retry` beside it. Queuing
guidance for the next attempt is not built; the box says so rather than pretending.

**38. Relative time, with the exact timestamp on hover and in the `title` attribute.** `14 minutes
ago`, `3 hours ago`, `Aug 16`.

**The consequence, and this one is a defect if ignored.** A relative string is computed against *now*
and a console tab is left open for hours. **A component that formats once and never recomputes will
say `14 minutes ago` at nine in the morning about something from four.** That is the console stating
a falsehood with total confidence, which is the failure this product exists to replace, arrived at
through a formatting helper. Relative times **re-render on an interval**, or they are not relative.
The absolute value carries its offset and is the thing in the `title`, so a copy-paste or a
screenshot-with-tooltip is unambiguous.

**39. One page-level banner when the API is unreachable, and the panels below render `—`.** Not
per-panel messages, not stale figures kept on screen. **The banner's sentence is the load-bearing
part: *nothing on this page is current*.** A dash under a label is the fourth state again — not
zero, not never-measured, not loading — and the banner is what names it, so the banner is not
decoration and may not be dismissed while the condition holds.

**40. Dense tables, 50 rows per page, with the footer record count.** Monospace where the cell is an
identifier. **Rejected: infinite scroll**, which drops the footer count — and the count is not
ornament here: `1,204 rows` is how a reader knows the page they are looking at is a page.
`interface-originality.md` lists *a footer bar owning pagination and the record count* among the
conventions of the form, and this is why.
