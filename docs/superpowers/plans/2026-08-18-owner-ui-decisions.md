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

## Round thirteen: decisions 65-67

**65. The diff renders unified and syntax-highlighted.** One column, removals above additions, with
the file name and `3 files · +12 −9`. **Rejected: split view**, which needs width the dense layout
does not have, and **rejected: pinning the call site inside the diff** — the finding already names
the line and decision 66 makes that line clickable.

**66. Clicking a file path anywhere opens a source drawer with the line highlighted**, and an
`Open on GitHub ↗` escape hatch. **Rejected: linking straight out to GitHub**, and **rejected:
copying the path.**

**This is the first UI decision that changes what the backend must hold, and it needs a threat-model
answer before it is built.** To render `src/api/billing.ts:41` in a drawer, something must serve that
file's contents. Sync clones a customer repository to index it. **The question this decision forces
is whether that clone is retained after the run, and that is not a console question** —
`docs/superpowers/specs/2026-07-25-sync-threat-model.md` is where it belongs.

Three routes, and they are not equivalent:

- **Serve from a retained clone.** Simplest, and it means customer source sits at rest on Sync's disk
  between runs. That is a claim the threat model currently does not make.
- **Fetch on demand from the forge.** Nothing at rest, but it needs a credential with read access at
  view time, and `CLAUDE.md`'s *we never hold customer secrets* is unqualified.
- **Store only the lines the graph references**, with their context window, at index time. Bounded,
  attributable, and it is the only one of the three where what Sync holds is exactly what it has
  already told the customer it looked at.

**The third is the one that fits what this product says about itself**, and it is a coordinator
recommendation rather than a ruling — the owner decides, and it is a threat-model amendment either
way. **`Open on GitHub ↗` must exist regardless**, because it is the answer when the drawer cannot
show a file.

**67. Tool calls in the Activity transcript render as typed cards, expanded by default.** Each node
renders as itself — `locate`, `patch`, `verify`, `push` — with its duration and its own fields.
**Rejected: collapsed by default**, and **rejected: a plain chronological log.**

**Expanded-by-default is the honest choice and the expensive one.** Nothing about the run is behind a
click, which is the position this screen exists to take — but it also means a long run is a long
page, and a card with nothing to show must say so rather than rendering an empty expansion.

## Round fourteen: decisions 68-71

**68. The breadcrumb shows the full path and every segment is a link**, the last one plain text.
`checkout › API Services › stripe › PostCharges › Solution workflow`. **Rejected: collapsing the
middle**, and **rejected: a back link only.**

**69. A destructive action opens a dialog naming the consequence** — what is removed, with counts,
and what survives. **Rejected: type-the-name**, and **rejected: do-it-with-undo**, which would have
required a soft-delete column built for a control rather than for a fact.

**Those counts must be real, and this is the whole reason the dialog is the right one.** `Removes
1,204 call sites, 31 findings, 18 runs / Keeps 2 open pull requests` is a claim, and a dialog that
guesses is worse than one that does not offer the number. **A count the query cannot establish says
so; it never renders `0`.** A dialog that says *removes 0 findings* about a workspace whose findings
were never counted is the absence-into-zero failure at the one moment it is irreversible.

**70. A global search field lives in the rail**, searching call sites, findings, vendors, operations
and files across the workspace, with results grouped by type and counted.

**This does not merge with decision 43's command palette, and neither replaces the other.** The
palette navigates to *named things* and holds no actions. Rail search looks *inside* the workspace's
content. Building one and calling it the other would leave a reader unable to find a file path by
its middle segment, which is exactly what rail search is for. **Two components, one index, and the
counts beside each group are the valuable part — they say what you would get before you click.**

**71. A long identifier truncates from the start and keeps the filename and line.**
`…/internal/charge-handler.ts:41`.

**The failure mode this creates has to be handled rather than accepted.** Two different files with
the same basename truncate to the same string. So the **full path goes in the `title` attribute and
the accessible name** — as decisions 60 and 65 already require for hovered precision — and the source
drawer shows it whole. **Where two visible rows would truncate identically, the column widens rather
than lying**; identical-looking rows that are different records is a worse table than a wide one.

## Round fifteen: decisions 72-75, and one raised back to the owner

**72. Signals rows are vendors, expandable to their changes.** `stripe — 312 changes · 31 matched`,
expanding to the matched changes and the operation each touched. **Rejected: one row per vendor
change**, and **rejected: only changes that touched this workspace.**

**The unmatched count is the valuable half and must not be dropped.** `312 changes · 31 matched` says
Sync read three hundred and twelve things and can account for why two hundred and eighty-one of them
are not your problem. A screen showing only matches would look identical whether the other 281 were
checked or never fetched.

**73. RAISED BACK TO THE OWNER, NOT RECORDED AS SETTLED.** The selection was *stage plus a live
progress indicator*, `●○○ awaiting CI` with motion on running rows. **`CLAUDE.md:63` refuses a
liveness pulse by name, rejected on the record three times**, and gives this exact case as the
reason: *"nothing in our data tells a run parked on the customer's CI from one that has died."* An
animated indicator on `awaiting CI` asserts liveness the data cannot establish. **The owner may
overrule their own document — but it is their document, so it is raised rather than absorbed.**

**74. Settings gets four editable groups**: Codebases (add, remove, select), Pull request policy with
`immediately` still refused and the reason shown, the notification webhook naming its environment
variable without ever accepting the value, and — **added by the owner in this round — AI model
configuration.**

**Model settings are a new group and they inherit a constraint from `CLAUDE.md`.** The model, the
thinking mode and the effort are already fixed project-wide — `claude-opus-5`, adaptive, `xhigh` —
and the two SDK surfaces spell them differently and are not interchangeable. **The screen shows what
is configured and where it comes from; the API key is an environment variable and is never accepted
by a form**, exactly as the webhook endpoint is. **Detector enable/disable was not selected** and is
not built.

**75. The install command prints what it found, then the URL.** Files read, call sites, vendors,
findings, then `✓ http://localhost:5170`. **Rejected: the URL alone**, and **rejected: adding a
not-measured-yet block** — which would have put the console's honesty discipline into a terminal
before anybody has seen a screen.

### 73 settled by owner reaffirmation: motion and live progress are wanted

**The owner reaffirmed after the objection was raised**, and asked for live progress and motion
across the console. **That is the decision.** What follows is the distinction that lets it be built
without reintroducing the thing `CLAUDE.md:63` refuses, because the two are separable and the
separation makes the interface *more* alive rather than less:

- **Motion driven by a received event is honest.** A stage transition that actually arrived, a row
  that actually inserted, a count that actually changed — animating those is showing something true,
  and it is the kind of motion that makes a console feel connected to a running system.
- **Motion driven by a timer is the pulse that was refused.** A spinner on `awaiting CI` rotates
  identically whether CI is running or the run died forty minutes ago. It looks like information and
  is not.

**So the rule is: animation is bound to the event stream, never to a clock.** A run that has produced
no event within its own stage's expected window **stops animating and says how long it has been
silent**. That is strictly more informative than a perpetual spinner, and it is what a reviewer
actually needs to know.

`CLAUDE.md:63` is amended by the owner to this extent and no further: **motion reflecting a received
transition is permitted. A composite score, a health figure, a traffic light and a green dot standing
for aggregate wellness remain refused.**

## Round sixteen: decisions 76-79, the motion system

**76. Server-sent events push every transition.** `GET /api/events` as `text/event-stream`, carrying
`run.stage`, `finding.opened` and the rest. **Rejected: polling**, and **rejected: push with a
polling fallback.**

**This is backend work before it is motion work**, and it is the thing that makes the rest honest:
animation binds to a received event, so a row moves at the moment the transition actually happened.
**A dropped stream is a state the console must render**, not one it may hide — if the connection
fails there is no fallback by decision, so the screen says the stream is down and what it last saw.

**77. A changed value swaps to its new figure with the delta beside it**, `31 ↑+1`, fading after ten
seconds. **Rejected: counting up**, and this rejection is load-bearing — a rolling counter renders
`1,207` on its way to `1,216`, and **`1,207` is a number nothing ever measured.** For four hundred
milliseconds the console states a figure that was never true.

**78. The canvas streams nodes as files are read, then settles the layout when the index completes**,
about 600ms. Edges draw straight during the stream and relax at the end. **Rejected: a progress bar
followed by the finished graph**, which hides the moment worth watching.

**79. Maximum motion — staggered entrances, charts drawing in, panels springing, page cross-fades.**

**Two reconciliations, because 79 as previewed contradicts 77 and omits an accessibility default.**

1. **Numbers do not roll.** 79's preview lists rolling numbers among the maximum set; **decision 77
   is the specific ruling on a changing value and it governs.** Rich motion everywhere else, swap
   plus delta on figures. A lane building a rolling counter and citing 79 has misread the pair.
2. **`prefers-reduced-motion` is still respected in full.** It was named in the two options not
   chosen, and the chosen one did not say to drop it. **Honouring it is the platform default, not a
   reduction of the owner's choice** — recorded as an assumption the owner can reverse, and it is the
   difference between a premium interface and one that makes some people ill.

**One performance bound, stated now rather than discovered on stage.** Dense tables are 50 rows
(decision 40); a 30ms stagger across 50 rows is a page that takes a second and a half to finish
arriving. **The stagger caps at the first 12 rows and the remainder appear together** — the effect
is entirely in the first few anyway, and a demo that visibly crawls on real data is worse than one
that never staggered.

## Round seventeen: decisions 80-83, the framer-motion contract

**The mechanism already exists and this expands it rather than introducing it.** `framer-motion`
`12.43.0` is installed, `lib/motion.ts` drives it, and `test_nothing_transitions_geometry_anywhere`
bans **Tailwind's** `transition`/`transition-all`/`transition-transform`/`transition-shadow` while
**explicitly permitting framer's `transition={{ … }}` prop**. Opacity is not geometry;
`transition-colors` stays legal. **So a motion system is buildable without touching the guard, and
anything animating geometry through a Tailwind class is still a failure.**

**80. Every motion instance stays named in `DESIGN.md`'s Motion section**, as the three sanctioned
ones are today. **Rejected: named primitives with composed instances**, and **rejected: relaxing the
guard.**

**This is the strictest of the three and it is the one consistent with everything else here.** The
register is the same discipline as `abandon_reason` and the dismissal vocabulary: **a closed set,
auditable, where adding an entry is a deliberate act.** It also means motion cannot creep — a screen
that wants a new animation adds a line to the contract first, which is exactly how `--spacing-row`
and the colour tokens already work.

**81. Springs, stiff and damped** — `stiffness: 400, damping: 40, mass: 0.8`, settling in about
250ms with almost no overshoot, and reacting instantly when interrupted. **Rejected: expressive
springs with visible rebound**, and **rejected: fixed durations with a cubic-bezier.**

**Interruption is the reason this matters more than the numbers.** Rows arrive from a live event
stream, so a second event can land mid-animation. A duration-and-easing transition restarts or
jumps; a stiff spring absorbs it and keeps its velocity. **Motion bound to real events needs physics
that survive being interrupted by more real events.**

**82. Shared-element layout animation on the canvas only.** A node morphs into its detail via
`layoutId`; a table row opens a drawer that **slides in from the right with no morph**. **Rejected:
morphing table rows**, and **rejected: no shared layout at all.**

**The split is where the morph earns its cost.** On the canvas the morph *explains* something — the
detail is that node, in that position, in a graph you are looking at. In a table it is decoration,
and `layoutId` across a 50-row virtualised list is the easiest way to make framer thrash.

**83. Route changes are instant. No transition between screens at all.** **Rejected: cross-fade**,
and **rejected: a directional slide.**

**This is the sharpest decision in the set and it is not a reduction of decision 79.** Maximum
motion, and **zero of it spent on navigation** — because a route change is something *you* did and
already know about, while an arriving row, a changing value and a building graph are things *the
system* did that you would otherwise miss. **The entire motion budget goes to what changed rather
than to where you went**, which is the same argument as every other refusal in this document,
applied to milliseconds instead of pixels.

## Round eighteen: decisions 84-87 — and 79 is substantially superseded

**84. `lib/motion.ts`'s bar stands unchanged: motion is permitted where the data holds a time, and
on a surface the operator meets occasionally rather than crosses on every pointer move.** **Rejected:
splitting it into a strict class and a looser interaction class**, and **rejected: replacing it with
taste.**

**This is the decision that reshapes the whole motion round, so the supersession is written out
rather than left to be discovered.** Decision 79 was *maximum motion — staggered entrances, charts
drawing in, panels springing, page cross-fades*. Against decision 84:

| 79 promised | status now | why |
|---|---|---|
| staggered row entrance on page load | **withdrawn** | a page load is not a time the data holds |
| charts drawing in on mount | **withdrawn** | same; mount is not an event |
| panels springing on mount | **withdrawn** | same |
| page cross-fades | already withdrawn by 83 | navigation is something you did |
| numbers rolling | already withdrawn by 77 | renders a figure nothing measured |
| hover easing | **withdrawn** | crossed on every pointer move |

**What survives is not less alive — it is differently alive.** Every animation left in the console
points at something that actually happened: a stage transition arriving, a value changing, the canvas
building as files are read, the new-findings banner appearing. **Nothing moves because a page
rendered.** The console feels alive exactly when the system is doing something, and still when it is
not — which is information rather than decoration.

**The bar is also load-bearing evidence rather than a slogan:** `lib/motion.ts` records that its
third sanctioned usage was **measured and deleted** after it was found never to have run once.

**85. Overlays split along a real line: the panel is a framer `motion.div` on the spring; the scrim
is Radix `[data-state]` opacity in CSS.** **Rejected: framer for both via `forceMount`**, and
**rejected: CSS keyframes for both.**

**One honest note on 84 and 85 together.** A drawer opening is *not* a time the data holds, so it
fails the bar's first clause and passes its second. **It is granted deliberately as a named register
entry rather than by reinterpreting the bar** — which is precisely what decision 80's
name-every-instance register is for. The bar governs whether a motion earns an entry; the register is
the authority on what exists.

**86. A dismissed or filtered-out row is gone on the next render.** No exit animation. The toast says
what happened and why — `PostRefunds dismissed · not used here`. **Rejected: collapse-and-settle**,
and **rejected: fade-in-place.** Exit animation on a virtualised list is the easiest thing here to
make janky, and the row leaving is something *you* did.

**87. New rows arriving on the stream are held behind a banner — `↓ 2 new findings [Show]`.** The
table does not move while you read it; **the count is live even so.** **Rejected: inserting at the
top**, and **rejected: inserting only when scrolled to the top.**

**This is the log-tail problem answered in the reader's favour**, and it is the same instinct as
decision 34's drawer: content that shifts under your eyes while you are reading it costs more than
freshness buys. The banner is the arrival animation.

## Round nineteen: decisions 88-89, and two questions answered from the tree

**88. A run that cannot produce a safe patch abandons with a reason code and opens no pull request.**
The finding stays open, the reason is recorded and queryable, and the screen offers `Retry` and
`Open manually ↗`. **Rejected: a draft PR carrying an unverified diff**, and **rejected: an
unverified suggested diff shown inside the finding.**

**This is `CLAUDE.md`'s *nothing reaches a pull request unverified* held at the moment it costs
something.** Both rejected options are the same trade — put a diff in front of a human with a label
saying it does not compile — and both would have made the invariant conditional. The abandon reason
is not a failure to hide; `CLAUDE.md` already says **abandoned runs are data**, and they are where
routing learns which change kinds are not mechanically safe.

**89. Production is a self-hosted container on the customer's infrastructure** — their Postgres,
their tokens, running beside their CI. **Rejected: a hosted GitHub App**, and **rejected: self-host
now with hosted later as a stated plan.**

**This keeps the one unqualified invariant intact.** A hosted app means holding a GitHub App
installation token, which is a customer credential, and `CLAUDE.md`'s *we never hold customer
secrets* has no qualification on it. Self-hosting is not a smaller version of the hosted product —
**it is the deployment shape in which that sentence stays true.**

### Two owner questions, answered from the tree rather than re-asked

**"Was there anything planned for reading many codebases?"** — **Yes, and it is built.**
`LanguageAdapter` is a protocol at `core/protocols.py:12` with **two implementations already wired**:
`TypeScriptAdapter` and `PythonAdapter`, both returned by `cli.py:198`. `core/conformance.py:361`
checks an adapter against every guarantee the protocol states but cannot enforce, and the design spec
records why Python exists at all — *"to prove `LanguageAdapter` generalizes past TypeScript."*

**The real shape is therefore: indexing is polyglot, remediation is not.** The verification gate is
`tsc`, so Sync can *see* Python call sites and cannot *fix* them. That is a live distinction the
console does not yet render, and it is exactly the kind of gap that reads as zero findings.

**"How did we plan for adding different vendors?"** — **Also built, deliberately without a plugin
scan.** `signals/registry.py` holds `_CODED_ADAPTERS` (`stripe`, `twilio`) beside configured vendors
served by `GeneratedSpecAdapter` and `McpServerAdapter`, with `available_vendors()` returning both.
Its own docstring states the choice: *"No entry-point discovery and no plugin scan. A third party's
adapter is registered by adding a line to `_BUILDERS`... Discovery would be the right shape once an
adapter ships outside this repository and is guesswork until then."* That is *build for the case that
exists*, applied and written down.

**And it already reports its own gap honestly**: a configured vendor's *specifications* are
discoverable while its *call sites* are not, so it binds nothing — and `signals/intake` reports that
as missing configuration rather than hiding it behind a vendor that appears served.

## Round twenty: decisions 90-91, the adaptability answer, and one new requirement

**90. Findings are not ranked.** Kind and rung are the facts; time is the only ordering.
**Rejected: ranking by call-site count**, which is a real measurement and was still declined — and
**rejected: call sites weighted by rung**, which is a composite and refused by name. **The reader
ranks.** A breaking change at 40 observed call sites and one at 2 static sites are both on screen
with both numbers; the console does not decide which matters to this team.

**91. The pull request body carries the finding, the verification, and a collapsed `<details>` block**
holding every call site and why each changed. Summary and proof visible; the long tail one click
down. **Rejected: the full list inline**, and **rejected: one paragraph and a link** — the PR is what
most people will see of this product, and a reviewer who never opens the console should still be able
to check the work.

### "We need this to work with all languages and vendors — are there plans?" — yes, and they are further along than the question assumed

**Six plugin protocols already exist in `core/protocols.py`**: `LanguageAdapter`, `VendorAdapter`,
`RequestCorrelator`, `Detector`, `PatchRunner`, `Remediator`. The design spec calls the
`sync.core`-imports-nothing rule *"what makes the system genuinely pluggable rather than merely
pluggable-shaped"*, and `tests/test_import_boundary.py` enforces it.

**Vendors have a four-tier classification and a route out of per-vendor code**
(`specs/2026-07-27-sync-adapter-targets.md`, and the design spec's own table):

| tier | source | examples | mechanism |
|---|---|---|---|
| 1 — OpenAPI in git | spec file | Stripe, Twilio, GitHub | `oasdiff` |
| 2 — machine-readable, not OpenAPI | Discovery Document, `service-2.json` | Google, AWS | converter → tier 1 |
| 3 — GraphQL | SDL via introspection | Linear, GitHub v4, Shopify | `graphql-inspector` |
| 4 — prose only | changelog | Notion, the long tail | LLM extraction, **never authoritative** |

**The key line is that tier 1 collapses to one `GitOpenApiAdapter` parameterised by coordinates —
*"Stripe becomes a configuration row rather than a class, and Twilio and GitHub cost an afternoon
each."*** That is the adaptable system, already designed. `M3` publishes `sync.core` as the open
plugin SDK with adapter-authoring docs, and the open-core decision exists *because* coverage is the
moat: **no single team can write dozens of adapters, so the protocol has to be the product.**

**Languages are the same shape and already proven**: `LanguageAdapter` has TypeScript and Python
implementations both wired at `cli.py:198`, plus `core/conformance.py` checking an adapter against
every guarantee the protocol states but cannot enforce.

**92. NEW REQUIREMENT, owner: bring your own model, open or closed.** Sync must let a customer attach
their own model rather than only Anthropic's.

**What this touches, stated so it is planned rather than bolted on.** `CLAUDE.md` currently fixes the
model project-wide — `claude-opus-5`, adaptive thinking, `xhigh` effort — and records that the two
SDK surfaces spell those differently and are not interchangeable. A BYO-model path needs a **seventh
protocol**, beside the six that exist: the thing that runs an agent turn. `PatchRunner` is the
closest existing seam. **The Settings group from decision 74 becomes its interface**, and the same
rule applies as to the webhook — **the screen names the environment variable and never accepts the
key.** Self-hosting (decision 89) makes this straightforward, because the credential never leaves the
customer's infrastructure.

## Round twenty-one: decisions 93-96

**93. The `observed` rung comes from reading the customer's existing APM.** Datadog and Sentry
adapters already exist in `signals/`. **Sync installs nothing in their application** — it reads spans
they already collect. **Rejected: an OTLP receiver**, and **rejected: both.**

`RequestCorrelator` is the protocol that joins a span to a call site, and it is already one of the
six. The credential is an environment variable named on screen and never accepted by a form, as with
the webhook and the model key.

**94. A workspace is a package that calls a vendor, not a repository.** In a monorepo of twelve
packages where three call vendors, there are three workspaces. **Rejected: one workspace for the
whole repo**, and **rejected: packages as a filter axis.**

**This changes what a workspace *is*, and reconciles with decision 44 in one sentence: you add a
codebase, and Sync derives the workspaces from it.** `Add workspace` in the switcher means *point
Sync at a repository*; what appears afterwards is discovered by the index, not chosen. **A package
with no vendor calls is not an empty workspace — it is not a workspace**, and the difference matters
because an empty workspace would read as *nothing found here* rather than *nothing to watch here*.

**Consequence for routing**: workspace identity becomes repository plus package, so
`/repositories/:repoId` is no longer a sufficient scope key. That is a real change to `routes.ts` and
to every scoped API route.

**95. GitHub OAuth, with identity recorded.** **Rejected: no auth**, and **rejected: a single shared
token.**

**This is what fills the column decision 45 already specified.** That decision's grain says one row
is one dismissal *by one person* at one time; until now nothing could populate the person.
Self-hosted means the customer registers their own OAuth app, so the client secret lives in their
environment exactly like every other credential here.

**96. The Wednesday path is the whole loop: install → index → canvas → finding → workflow → pull
request.** **Rejected: leading with the graph alone**, and **rejected: opening cold on a finding.**

**This is the most demanding of the three and it makes the beta gates the demo rather than a
scoreboard beside it.** Step 6 is a pull request that a run actually opened — which is `B7`, which
has never produced a CI-green pull request, which is why Gates 1 and 2 read NOT MET and CANNOT TELL.
**The demo path and the gate list are now the same list.** Step 2 needs the event bus wired, which
is Gate 4's newest dead link. Nothing here is decorative.

## Round twenty-two: decisions 97-99 — the install needs no prerequisites

**Owner, 2026-08-18:** *"setup still doesn't work because command needs docker, we need to build the
setup so it doesn't need anything just like the references I provided."*

**Measured before scoping.** Docker carries exactly two things in `docker-compose.demo.yml`:
`postgres:16`, and the `sync` app image. And the schema is genuinely Postgres-shaped — **22
`timestamptz`, 8 GIN indexes, 6 `jsonb`, 4 `text[]` across 642 lines** — so a SQLite port is a
rewrite of the schema *and* every query, and it would break the one-database property. **SQLite was
ruled out on measurement, not preference.**

**97. Postgres comes from embedded binaries the installer fetches**, run as a subprocess on a free
port. **Rejected: PGlite**, the WASM build, despite needing no download — because it is
single-connection and drops some extensions, and *"it IS Postgres"* was worth 55MB. **Rejected:
keeping Docker.**

**What this makes ours to own, and it is the real cost:** a process lifecycle. Start, stop, and
**orphans** — a Postgres left running after a crash is the failure mode that makes the second run
worse than the first. Idempotence matters as much as the first run: a second `npx sync` must not
re-download 55MB.

**98. Python arrives by bootstrapping `uv`**, which fetches a pinned 3.12 and the dependencies.
**Rejected: a frozen per-platform binary**, which needs a three-platform build matrix before
Wednesday. **Rejected: requiring Python**, which is the Docker problem moved rather than solved.

**The repository already uses `uv`, so this is the same tool fetching itself** — not a new
dependency, and the pinned-Python guarantee is one the project already relies on.

**99. Both paths run in parallel and the owner gets a measured list on Wednesday morning** — what a
stranger can do, what still needs Docker, and what does not work yet. **Rejected: protecting only
the zero-prerequisite install**, and **rejected: protecting only the full demo loop.**

**This is the decision that binds hardest on reporting rather than on building.** It forbids the
comfortable Wednesday summary. Every line is measured or it is marked as not measured, and
**nothing is reported working that has not been run on a clean machine.** The `docker compose` path
stays supported throughout — it works today, and removing it while the replacement is unproven would
trade a working install for a hoped-for one.

**One dependency that decides whether any of this matters.** `sync index --repo` still does not
exist, so a zero-prerequisite install that comes up perfectly still shows an empty console. The
install work and the index command are one deliverable, not two.
