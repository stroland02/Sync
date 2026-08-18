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

## Round seven: decisions 41-44, owner-selected 2026-08-18

**41. A toast in the bottom corner when a long-running action finishes**, carrying the result and a
link to it. **Rejected: a count on the sidebar row**, and **rejected: silence**.

**The constraint this puts on the toast, because a toast is transient and this product refuses
transient truth.** A toast may *announce* a fact but may never be the only place it exists. `Index
finished — 1,204 call sites` must be readable on the Overview a minute later without having caught
the toast. And a toast never reports something the screens cannot corroborate: no `all clear`, no
`healthy`, no completion claim for a run parked on the customer's CI.

**42. Findings default to newest first, flat, with kind as a column you can sort and filter.**

**This supersedes decision 15's grouping and is recorded as a reversal rather than reconciled
quietly.** Decision 15 read *"findings group by kind, breaking first, under a triage header carrying
each count."* The grouping is withdrawn; **the triage header with its counts is retained** as filter
chrome above the flat table, because the counts answer *what would I get if I clicked* and that is
the part decision 15 was actually buying. **The retention is a coordinator ruling and the owner can
reverse it**; the grouping's withdrawal is the owner's.

Any screen currently rendering the grouped shape changes. `M14`'s finding work was dispatched
against 15 and must be re-read against this.

**43. A command palette for navigation only.** Screens, workspaces, vendors, findings, files. **No
actions in it at all** — not even safe ones. So it cannot become the surface where somebody triggers
a run by typing three letters and pressing return.

**44. The workspace switcher carries the list, a filter field, `Add workspace`, and `Manage in
Settings`.** **Rejected: per-item last-indexed facts in the switcher** — the switcher is for changing
scope, and a stale-vs-live judgement belongs on the screen that can explain it. **Rejected: a bare
list**, which would have made adding a workspace reachable only through Settings.

This is decision 1's *selection is chrome, not content* carried to its component: the switcher is
where you change scope and start a workspace, Settings is where you manage what exists.

## Round eight: decisions 45-48, owner-selected 2026-08-18

**45. A finding can be dismissed with a reason from a closed vocabulary** — `not used here`,
`intentional`, `false positive`, `won't fix`. **Dismissed findings stay listed and are filtered out
by default.**

**This is the first decision in this set that is not a rendering change, and it must not be built as
one.** It needs a write path and a stored column, so:

- **`schema.sql` declares the grain before the column exists.** One row is one *dismissal of one
  finding by one person at one time*, not a property of the finding — a finding dismissed and later
  un-dismissed has two rows and the current state is the latest, because otherwise the console cannot
  show that somebody changed their mind.
- **Dismissal is not deletion.** The finding remains, filtered out. `interface-originality.md`'s
  rule that we take a vocabulary's *shape* and not its *values* applies: this vocabulary comes from
  Sync's own reviewers, and it is deliberately the same discipline as `abandon_reason` — a closed set
  because *a promise to learn from dismissals needs a schema that can answer the question*, and free
  text cannot be aggregated.
- **`false positive` feeds detector accuracy and nothing else does.** It is the only honest source of
  that number, and it is exactly what Gate 2's quality axes have no samples for today.

**46. The sidebar rests collapsed and expands on hover.** Icons at rest, full labels when reached
for. The explicit collapse control stays for pinning it open.

**47. The Pull Request screen leads with the diff**, with `3 files · +12 −9` and the check line
beneath it. **Rejected: leading with the verification chain**, and **rejected: leading with the
finding it answers.**

**The constraint that keeps this honest.** Leading with the diff is the reviewer's instinct and it is
right — but the verification chain is *why this product is different from a bot that opens pull
requests*, so it sits **visibly below the diff, not behind a disclosure and not in a tooltip**.
`tsc passed · customer CI: running` is on screen without a click. A run parked on the customer's CI
still says so rather than reading as passed.

**48. Below its threshold the sidebar collapses itself and the content keeps its width.** Tables keep
every column and scroll horizontally **inside their own container**, never the page body. **Rejected:
dropping columns by priority**, which decides for the reader which column mattered.

## Round nine: decisions 49-52, owner-selected 2026-08-18

**49. Every filter, sort and page lives in the URL now; named saved views come after Wednesday.**
`[Copy link]` on each table; back and refresh both work.

**The distinction that must not be lost, because `M14-W400` just spent a unit fixing its opposite.**
**Scope is the path. Filters are the query string.** `/w/checkout/findings` says which workspace;
`?kind=breaking&rung=observed` says which rows. A screen reading its *scope* from the query string is
the defect that let a page claim fleet scope while its URL named one repository. Filters in the
query string are correct and are not a reversal of that.

**50. `Export CSV` on every table now; a token-authenticated read API documented after.**

**The CSV header carries the filters and the counts** — workspace, filters applied, export time with
offset, and `4 of 31 rows`. A CSV that does not say what it excluded is a screenshot of a filter
somebody will later read as the whole set.

**51. A `Since the last index` panel** — call sites added and removed, and rungs that strengthened or
weakened, with the date of the first index. **Rejected: a pick-any-two comparison screen**, which is
the larger build.

**A first-ever index has no previous, and that is the fourth state again.** The panel says *this is
the first index* rather than rendering `+0 / −0`, which would read as *nothing changed* about a
codebase nothing had ever looked at.

**52. One outbound webhook, configured in Settings, on finding-opened and pull-request-opened.**
**Rejected: a digest email**, and **rejected: relying on the pull request to notify.**

**The conflict, and how it resolves.** `CLAUDE.md` says *we never hold customer secrets*, and that
one is unqualified. **A Slack incoming-webhook URL is a credential** — it grants post access to a
channel — so a Settings field that accepts and stores one would break the invariant, in the product's
own console, in a field labelled Endpoint.

**It resolves against a pattern already in the tree.** `sync.cli._webhook_secret` reads GitHub's
inbound secret from a named file or an environment variable and never stores it. The outbound
endpoint takes the same shape: **Settings names the environment variable, says whether it is set, and
offers `Send test` — it never accepts the value and never displays it.** This is the same answer
already given for `.sync/context.md`: *show it, say where it comes from, never write it.* The
screen states that difference rather than hiding it, because it is a better answer than the
reference's, not a missing feature.

## Round ten: decisions 53-56, the style contract. Owner-selected 2026-08-18

**Stated influences: Radix, shadcn/ui, and Vercel's Geist — dark-first, high-density, keyboard
accessible.** These are conventions of the form and `interface-originality.md` permits learning them
from anything. What follows are token values, and `DESIGN.md` is the contract: **every one of these
lands there with its arithmetic, or it does not land.**

**53. Surfaces separate by a 1px border and nothing else.** Panels and cards share the page
background; a divider is a rule, not a gap. **No shadow anywhere except true overlays** — drawer,
command palette, popover. **Rejected: raised backgrounds**, and **rejected: border plus a step.**

This is the flattest of the three and the densest, and it suits a console whose screens are mostly
tables and facts rather than objects.

**54. The system font stack, with monospace for identifiers.** No webfont, no build step, no network
cost. Monospace is reserved for things that are code or an id — file paths with line numbers,
operation names, run ids, vendor slugs. **Rejected: self-hosted Geist**, and **rejected: Inter with
JetBrains Mono.**

**Monospace is doing semantic work here, not decorative work.** If a value is monospace it is
something you could search for or paste; that rule is worth keeping when somebody is tempted to
monospace a number.

**55. The focus ring is always visible, and keyboard navigation is tab order only.** No arrow-key
grid behaviour inside tables.

**The consequence, and it is reversible.** Radix's default is `:focus-visible`, which hides the ring
from mouse users precisely because a ring left behind after a click reads as noise. Choosing
always-visible trades that for never being invisible to somebody who needs it. **If the rings feel
loud in use, the fix is `:focus-visible` and it is a one-token change** — recorded here so it is a
decision to revisit rather than a bug to report.

**56. 6px radius, 32px control height, 32px table rows** — shadcn's proportions. About 28 rows at
1080p. **Rejected: 4px/28px** as too tight, **rejected: 8px/36px** as too roomy.

**This binds decision 40.** Dense tables at 50 rows per page now means 32px rows, and
`--spacing-row` already names 8px — the guards that failed on `main` tonight exist to keep exactly
these values in one place. **No screen spells 32px raw.**

## Round eleven: decisions 57-60, components. Owner-selected 2026-08-18

**57. The table gets a sticky header, a sticky first column, and column sort whose state is in the
URL.** **Not selected: row multi-select with bulk actions**, and **not selected: filter chips.**

**Not selecting chips leaves a gap that must be closed elsewhere, because it is an honesty gap rather
than a convenience one.** Decision 49 puts filters in the URL; with no chips, a filtered table looks
exactly like an unfiltered one. **The footer count from decision 40 carries it: `showing 4 of 31 ·
27 filtered out`, and never a bare `4 rows` when a filter is active.** That is a coordinator ruling
and reversible — but *something* must say it, because a subset presented as a set is the failure this
console exists to prevent.

**Bulk dismissal not being selected also settles a question decision 45 raised**: dismissal is
one finding at a time, so every dismissal has a reason somebody actually chose.

**58. Charts get a quiet baseline and tick labels. No gridlines, no legend unless there are multiple
series.**

**59. Radix primitives, styled by us — which is already the architecture, so this decision changes
nothing and deletes something.** All three existing overlays already import `radix-ui` directly:
`components/ui/dialog.tsx`, and the vendored `dialog.tsx` and `sheet.tsx`. Nothing new to install.

**What it does settle: `web/src/vendor/supabase/ui/dialog.tsx` has zero importers.** Our own
`components/ui/dialog.tsx` has one, and the vendored `sheet.tsx` has one. **Delete the dead one** —
delete rather than deprecate, and two dialog implementations for one job is the fact-written-twice
defect wearing a component's clothes. The Supabase carve-out is unaffected: `sheet.tsx` stays,
attributed in `web/NOTICE`.

**60. Counts group with separators and abbreviate above ten thousand**, with the exact value on
hover — `892k`, hover `892,317`.

**Two consequences, and the first is the same shape as decision 38's.** **Hover does not exist on
touch, in a screenshot, or for a keyboard user who never points at it.** So the exact value goes in
the `title` attribute and in the accessible name, not only in a floating tooltip — and **`Export CSV`
never abbreviates**, because a CSV is the artifact somebody sums.

**Second: tabular figures still apply.** Whatever is shown, digits align in a column. A right-aligned
column of numbers that do not line up is harder to compare than one that does, and comparison is the
only reason to put them in a column.

## Round twelve: decisions 61-64, mined from references no plan had cited

**Fifteen of the reference images are cited in no plan or spec.** These four come from two of them,
opened for this round: `direction/supabase-10-auth-users-empty.png` and
`direction/supabase-18-query-performance-drawer.png`.

**61. An empty table keeps its column headers, states what was checked, and names one next action.**
`No findings — 4 detectors ran 14 minutes ago and none of them matched`, then `[Re-run detectors]`
and *attach telemetry to reach the observed rung*.

**Headers staying is the part worth naming.** The shape of the data is legible before there is data,
so a reader learns what a finding *is* from a screen that has none. And the next action teaches the
rung ladder at the moment somebody is looking at an empty screen and wondering whether the product
works.

**62. A slash-separated metrics strip above every large table** — `31 open / 4 breaking / 12
dismissed` — each term explaining itself on an info icon. **Rejected: rendering them as fact tiles**,
which costs vertical space on screens whose value is rows.

**63. A screen states how it was computed, behind an info icon on the screen's title.**

**The boundary this must not cross, and it is written into `CLAUDE.md` by hand.** That rule says of
the twenty-four protected sentences: *"Restyling one is allowed. Deleting one, shortening one,
collapsing one behind a disclosure, or moving one into a tooltip is not."*

**Decision 63 authorises a new provenance note and nothing else.** It does not license moving any
existing on-screen sentence into the icon. The twenty-four stay where they are, at full length, on
the screen. **If a lane finds itself moving an existing sentence into an info popover and citing
decision 63, it has misread it** — the test is whether the sentence was on the screen before this
decision. New note: popover. Existing sentence: stays.

**64. Where a figure has a share and a magnitude, write the magnitude and draw the share.** The
number in the cell is the count; proportion is bar length. **Rejected: writing both**, in either
order.

**This stays inside the standing refusal because of what the bar is over.** A bar showing one
vendor's share of a real total is a measurement rendered proportionally. It does not become a
composite unless it starts averaging two different facts — which is what `M14-W394` caught in the
adopted cards, where a filled track over `openFindings / callSites` was a rate wearing a bar's
clothes.
