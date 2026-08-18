# What each page portrays: information architecture from the reference set

**Owner direction, 2026-08-18, consolidated from a sequence of messages sent across a session
limit.** Seven reference surfaces were supplied with a note on each about what to take. This document
turns them into per-page content decisions.

**Governing rule, and it is not decoration.** `.claude/rules/interface-originality.md` permits the
*conventions of the form* — a grid of fact tiles, a filter rail, a table with typed columns, a node
canvas, a tabbed triage header. It refuses the rendering, the copy, the iconography, and **any claim
their screen makes that our data cannot support**. That last clause does real work below, three
times, and the rule names one of them by hand: *"Superlog's incident view is the best thing in the
reference set and it carries `Root cause confidence: 9`. Take its structure, refuse its scalar."*

---

## 1. The Solution Workflow — the most important screen, and the most under-built

**Owner:** *"we need to make some serious improvements to the solution workflow … this is where the
human interaction actually takes place with the coding agents to either review or improve or change
the final product of what they're working on."*

**That sentence changes what the screen is for.** It is not a record of what an agent did. It is the
place a human intervenes in work that is still in progress.

**Structure taken from the reference incident view:**

- **A persistent left rail** carrying the run's identity and its facts as a label/value list — the
  finding, the vendor, the repository, the tier the cascade routed to, the strategy, when it started,
  how long it has run, what it is waiting on. Facts on the left stay visible while the main pane
  scrolls.
- **Two tabs over one run: `Activity` and `Findings`.** Activity is the turn-by-turn transcript with
  tool calls rendered as structured cards rather than raw text. Findings is the settled output —
  summary, root cause, the diff, the evidence.
- **Tool calls as cards with the tool name shown** (`report_findings` in theirs). Ours has a closed
  set of nodes; each should render as itself rather than as a wall of JSON.
- **Code with `file:line` anchors and syntax highlighting**, and a `show more` for long spans.
- **A reply box at the bottom of Activity**, and this is the whole point of the screen: *"reply to
  the investigation — request PR changes, explain the issue, add context."* **A human turn that
  re-enters the run.** `M10` already built resume-on-review-comment; this is its interface.
- **Actions in the left rail**: copy the agent prompt, give feedback, restart the run.

**Three refusals, and the first is named in our own rule.**

1. **No confidence scalars.** Theirs carries `Estimated impact — confidence 9/10` and `Root cause —
   confidence 9/10`. **We render the provenance rung instead**, which says what class of evidence
   stands behind the claim rather than inventing a number for how sure a model feels. This is the
   single most tempting thing in the reference set and it is refused on the record.
2. **No `Investigation: complete` with a dot.** Run outcome is a recorded value from a closed
   vocabulary, legible without colour.
3. **No invented severity.** Theirs shows `SEV-3`. Ours shows the change kind the detector emitted —
   breaking, deprecation, warning — because that is what we actually have.

---

## 2. The Overview — a dashboard for one codebase

Already ruled in `2026-08-18-owner-console-review.md`: the Overview *is* the selected codebase. This
is what goes on it, taking the reference project overview's arrangement.

**Top band — identity and a fact grid.** The codebase name, its origin URL with a copy control, and a
grid of small labelled tiles. Theirs: status, compute, github, recent branch, last migration, last
backup. **Ours, from data we hold:** last indexed, call sites, vendors detected, bindings by rung,
open findings, last run.

**Refused: their `STATUS — Healthy` tile with the green dot cluster.** That is a composite health
figure and it is rejected on the record three times over. The tiles state facts; none of them
averages the others.

**A large visual panel beside the fact grid.** Theirs renders a region topology. **Ours renders the
dependency graph** — vendors as nodes, call sites clustered beneath them, edges carrying the rung.
This is the screen's centrepiece because it is the thing no competitor can draw: *your code's actual
API surface*.

**Below the fold — a totals line and per-vendor cards.** Theirs: *193 Total Requests / 72.5% Success
Rate* with a time-range selector, then a card per service with a bar chart and warning/error counts.
**Ours:** total findings and their split by kind, a time range, then a card per vendor with its
finding counts. Bar charts are permitted here — a count over time is a real measurement, unlike a
composite.

---

## 3. Large record sets — the table format

**Owner:** *"I love how the editor shows a table format like you're in an Excel sheet … for calls and
endpoints that are hundreds of different records."*

**Take:** typed column headers (name plus its type), row selection, a filter field above, sort
controls per column, pagination with an explicit record count in the footer, horizontal scroll inside
the table rather than on the page.

**Where it applies:** call sites, bindings, findings, runs, pull requests — every screen currently
rendering a list that will be hundreds of rows on a real repository. **This is also the fix for
Fleet's N+1** (`B148`): a table that pages does not fetch every repository at once.

---

## 4. Indexing — the node canvas

**Owner:** *"this page would be a great example of our code indexing … show the indexing in a visual
way, a really cool immersive grid so it can be visually understood."*

**Take from the schema visualiser:** a pannable dotted canvas, entities as cards listing their fields
with types, edges drawn between related entities, a minimap, an auto-layout control.

**Ours renders the API dependency graph, not a database schema.** Vendor → operation → call site,
with each edge carrying the rung it was established at. **This is the visual that explains what Sync
is** in one screen, and it is the natural landing for the "watch it index your repository" moment the
one-command install creates.

---

## 5. Triage over large sets — the tabbed count header

**Owner:** *"a professional way to implement triage organization when dealing with large data sets …
signals, endpoints, traces, logs."*

**Take from the advisor screen:** tabs across the top, each carrying its own count (`Errors 0`,
`Warnings 8`, `Info 3`), a filter control, refresh and export, and a genuinely empty state that says
what was checked rather than sitting blank.

**Ours:** findings by kind, signals by source, abandoned runs by reason code. The counts are already
computed. **The empty state must say which detectors ran** — an empty findings list after a real scan
is a different fact from one before any scan, and this console exists to keep those apart.

---

## 6. Vendors and API services — detected, with identity

**Owner:** *"automatically detect what vendor or service it is so we can create a professional page
that shows the company logo and their information and all the metrics."*

**Take from the integrations screen:** a card grid, a featured band for the vendors we have first-
class adapters for, category and type filters, and a badge on each card showing its state.

**Ours already detects the vendor — that is what the indexer does.** The card shows the vendor, its
adapter tier (`coded`, `configured`, `generated`), what we know about its spec freshness, and the
finding count. **Badge vocabulary is closed and legible without colour**; `INSTALLED` becomes
`adapter: coded`.

**One caution.** Vendor logos are third-party marks. Use them for identification, at small size,
without implying endorsement — and never redraw them.

---

## 7. Logs and traces — the filter rail

**Take from the logs screen:** a left filter rail with time range, type and level each showing counts
beside them; a timeline histogram above the table; dense monospace rows; a detail drawer on a row.

**Ours:** the runs and signals views, where volume will be real. **The counts beside each filter are
the valuable part** — they tell you what you would get before you click.

---

## 8. The sidebar expands on hover

**Owner:** *"Supabase's sidebar only expands when you're hovering over it and then automatically
minimizes once you drag off."*

Take it. It reconciles the two things the owner asked for that otherwise conflict: **a compact rail
that does not consume width, and full labels when you need them.** It also removes the pinned/
unpinned decision the collapse button currently forces. Keep the explicit collapse control for people
who want it pinned open; hover-expand is the default behaviour, not a replacement for it.

---

## 9. Subtle colour, without a traffic light

**Owner:** *"subtle coloring in simple features so it's not too distracting but it gives the UI enough
style to look modern and advanced."*

**What colour is permitted to mean here:** a change kind (breaking / deprecation / warning), a rung, a
run outcome. All are closed vocabularies with a legible label; the colour is a second channel, never
the only one.

**What it may not mean:** health, confidence, or "good/bad" in aggregate. The moment a colour
averages two facts it has become the traffic light this product refuses.

Every value stays inside `DESIGN.md`'s dark-only palette and its 5.05:1 contrast floor, and any new
token carries the arithmetic that proves it. **Themes remain post-Wednesday.**

---

## All of it lands before Wednesday — owner directive, and what that requires

**The owner's instruction is that every item above is implemented before Wednesday.** Taken as
given. What follows is not a negotiation of the scope; it is what has to change about how the work is
run for the scope to be reachable.

- **The console is one lane and that is now the binding constraint.** Nine surfaces cannot land
  sequentially in two days. **Lane B runs parallel agent workflows per screen**, the mechanism it
  already used for `console-p0-ia-sweep`, rather than one reviewable unit at a time. The charter's
  one-unit rule is suspended for the console lane until Wednesday and restored after.
- **Lanes free up and move to the console.** Lane C after the container; Lane A after `B7`. The
  lane-owns-files rule still holds — they take console work only under an explicit split the
  coordinator records, because four collisions today all came from two lanes in one area.
- **The API dependencies are the thing that can silently sink this.** The Overview needs findings
  scoped to a repository; `B147` blocks a screen entirely. **Lane E is budget-held until it returns,
  and those two are its only P0s.**
- **Every screen ships with real data or says why it has none.** An empty screen is the failure mode
  that matters on Wednesday, and it is worse than an unstyled one.

**The one thing I will not do quietly is trade honesty for coverage.** The three refusals in this
document — confidence scalars, health dots, invented severity — are not polish that can be dropped
under time pressure. They are the product's argument, and an investor asking *is this real* is
exactly the reader who would notice a number nothing computed.

## Sequencing

1. **Solution workflow** — highest value, most under-built, and it is the screen the whole product
   argument rests on.
2. **Overview as the codebase dashboard** — already ruled; needs the scoped findings route from
   Lane E.
3. **Table format** wherever a list will be hundreds of rows.
4. **Sidebar hover-expand** plus the chrome items from the console review.
5. **Triage headers and filter rails** on signals and runs.
6. **The graph canvas** — highest ceiling, largest build; after the rest is honest.
