# Direction notes

One entry per example the owner supplies. Each records **what is structurally right about it** and
**what we already store that would go in that slot** — because a layout copied without that mapping
is a layout we cannot fill.

---

## 1. Superlog — incident detail (2026-08-06)

The owner's words: *"this is exactly the type of professionalism I was looking for in terms of the
structure of the user interface, and we don't have anything close to this."*

### What the screen is made of

1. **A persistent left sidebar**, roughly 210px, grouped with small caps labels — `Workspace`
   (Overview, Incidents, Errors, Alerts) and `Observe` (Explore, Dashboards) — the active item
   carrying a filled surface, a collapse control at the top beside the wordmark, and `Settings`
   pinned at the bottom edge.
2. **A top bar** carrying a breadcrumb (`Workspace / Incidents`) on the left and account furniture
   on the right — theme toggle, organization switcher, avatar.
3. **A second trail row** below it: `Incidents › <the incident's title>` with a close control at the
   far right. The detail is an addressable destination that remembers where it was opened from.
4. **A two-column detail.** A fixed left rail about 360px wide: a short id (`#honey-jackal`), the
   title at display size with tight leading, a paragraph of summary prose, then a **definition list
   of nine facts** — Priority, Status, Service, Environment, First detection, Last detection,
   Duration, Linked errors, Investigation — then three actions stacked at the bottom.
5. **Tabs in the content column** (`Activity` / `Findings`).
6. **Labelled content rows** — a narrow label column (`Proposed title`, `Root cause`) against a wide
   body that mixes prose, inline code chips and full code blocks. Each code block carries a
   **language label in its own header strip** (`TEXT`, `PYTHON`) and is syntax-highlighted.
7. **A composer pinned at the bottom** of the content column: *"Reply to the investigation — request
   PR changes, explain the issue, add context…"*, with a Send button and a `Shift Enter` hint.

### Why it reads as professional, stated as properties rather than as praise

- **The eye has one place to land.** The title is the only display-sized text on screen; everything
  else is body or smaller. Our console's type range is 2.0–2.67:1 and nothing dominates.
- **Facts are a list, not a paragraph.** Nine of them, label left, value right, one line each,
  scannable without reading. We render most of these as prose or as table columns.
- **The frame is doing work.** The sidebar holds the left edge, the content column is inset from it,
  and the rail and body are separated by a real gutter rather than a border.
- **Depth is used once.** Code blocks sit on a raised surface with their own label strip; nothing
  else on the screen is raised.
- **The trail is visible.** Two levels of breadcrumb mean you always know which entity you are
  inside and what contains it.

### What we already store that goes in each slot

This is the part that matters, and it is favourable: **we hold more than they render.**

| Their slot | Our data |
|---|---|
| Incident | `Finding` — with a rung, which their incident has no equivalent of |
| Priority / Status | `severity`, run outcome from the checkpointer |
| Service / Environment | vendor, operation, repository |
| First / Last detection | `indexed_at`, `first_seen` on observed calls |
| Linked errors | observed error windows, call sites, binding surface |
| Root cause + code | the vendor change, the call site, the patch diff, the `tsc` verdict |
| **Activity trail** | the remediation graph's checkpointed node sequence — `locate → patch → static verify → push → await CI → open PR`, **including the attempts that were abandoned and why** |
| Findings tab | the detectors that fired and the rung each rested on |

Their activity log is the closest thing on screen to what this product is *for*, and ours is
strictly richer: theirs shows what an agent did, ours shows what it did, what it could not verify,
and what it gave up on with a reason. We render it as a plain vertical list.

### The one thing that is not just presentation

**The composer implies a write path.** Every route we serve is a GET, held by a behavioural test, and
an operator cannot start a run, retry one, or reply to anything. That is a product decision with an
authorization story attached, not a component. It belongs in the plan as its own item and must not
be smuggled in as a text box.

### A premise this screenshot falsifies

`DESIGN.md`'s Space section refuses a wider frame ratio because *"the nav rail and header already
hold the composition's edge."* **There is no rail.** `layouts/site-nav.tsx` renders a horizontal
strip with `border-b`, and `app-shell.tsx` puts the whole page in a 24px gutter under it. The
argument that kept our frame at 3.0 against a 4.7–7.2 bar rests on a component that does not exist.

---

## 2. Superlog — the activity trail's content model (2026-08-06)

The owner supplied the feed's full text alongside the screenshot. This is the more valuable half:
the first example showed the *frame*, this shows **what goes in it**.

### The entry types, in the order they interleave

1. **Signal entries.** A kind chip (`trace` or `log`), the exception class or level, an event count
   (`8 events`), the message, and a relative time. Repeated for each distinct signal.
2. **An occurrence histogram** — *"Occurrences · last 14 days"*, one row per day with a count,
   showing zero every day here. **Zero is rendered, not suppressed**, which is the same discipline
   this console already holds and is worth noting as agreement rather than as something to adopt.
3. **State transitions**, as their own entries: *Investigation queued* · *Investigation started
   across 1 candidate repos* · *New issue joined the incident* · *Incident resolved by the
   investigating agent*.
4. **A collapsed agent run**: *"Started investigation — Show investigation · 8 steps"*. The steps
   exist, are counted, and are behind a disclosure.
5. **The agent's own narration**, labelled `Investigation agent`, in the first person, with numbered
   observations.
6. **A tool call rendered as a titled, structured block** — `report_findings` — with named fields:
   Summary, Proposed title, Root cause (prose, inline code, and two syntax-highlighted blocks with
   file and line references), Estimated impact, Severity.
7. **A second tool call** — `resolve_incident` — with Reasoning, Evidence, and a per-issue outcome
   array: `reason`, `status`, `issueId`, `evidence`, one object per issue closed.

### What we already hold for each

| Theirs | Ours |
|---|---|
| `trace` / `log` signal entries | observed calls, observed shapes, error windows — with `binding_rung` on each |
| Occurrence histogram | `observed_error_window` counts over time |
| *New issue joined the incident* | findings grouping under one `vendor_change` |
| *Investigation started across 1 candidate repos* | the run's repository scope |
| The 8 collapsed steps | **the checkpointed remediation graph** — `locate → prepare → patch → static verify → replay → push → await CI → open PR` |
| Agent narration | the patch agent's own recorded reasoning |
| `report_findings` block | the `Finding`, its vendor change, its call site, its rung |
| Root cause with file:line and code | the call site, the diff, the `tsc` verdict |
| `resolve_incident` per-issue outcomes | `migration_outcome` rows — disposition, `abandon_reason`, `terminal_status`, the routing row |

**We hold every slot, and two they do not have**: the provenance rung on each signal, and the
attempts that were abandoned with the reason they were abandoned. We render this as a plain vertical
list.

### The one thing to refuse, and it is prominent

Their block carries **`Root cause confidence: 9`** and **`Impact confidence: 9`**. That is the
composite score this project has refused four times, and the refusal does not move because a
reference we admire does it. A 9 has no referent: it does not say what was checked, what could not
be, or which of those two produced the number — and `CLAUDE.md`'s argument is precisely that a
scalar collapses *we could not check* onto the same axis as *we checked and it passed*.

**The honest version of that field is the one we already have.** The rung says which class of
evidence a claim rests on — `static`, `resolved`, `observed` — and it is attributable, so a false
positive can be traced to the binder that produced it. Where their screen puts a number, ours puts
the rung and the evidence behind it.

So: take the **structure** — a named, structured findings block with its evidence beside it, a
resolution block with a per-item outcome and reason, a collapsed step count that expands. Refuse the
**scalar**. That is the whole of what "concepts, not appearance" means here.

### What this makes obvious about our own screens

The workflow screen renders the node sequence as a list of nodes. Theirs renders a *narrative*: what
happened, then what the agent concluded, then the structured artifact it produced, then the
resolution with per-item evidence. Same data, different reading order — and the reading order is
what makes one feel like an investigation and the other like a status table.

---

## 3. Supabase — project overview (2026-08-06)

The owner's third example. Where Superlog showed a **detail**, this shows an **index**: the screen
you land on, whose job is to say what this thing is and what state it is in.

### What the screen is made of

1. **Entity switchers in the top bar, as the breadcrumb.** Organization (`stroland02's Org`, with a
   `FREE` plan chip) / project / branch (`main`, with a `PRODUCTION` chip), each carrying its own
   up-down switcher control. The trail is not a set of links to click back through — **each level is
   a control that changes scope in place.**
2. **A left sidebar** of about 180px, every item icon-plus-label, grouped by blank space rather than
   by headings: build tools, then stores, then observe, then settings pinned last. The active item
   is a filled surface with white text.
3. **A keyboard-shortcut strip** directly under the nav: *"Go to Project Overview  `G` then `H`"*.
   The shortcut is discoverable on the screen it applies to rather than hidden in a palette.
4. **A display-size page title** — the only text at that size — then the project's URL beside a
   split Copy control.
5. **A grid of six fact tiles.** Each is a bordered, rounded icon square about 56px, then a
   **small-caps letterspaced label** (`STATUS`, `COMPUTE`, `GITHUB`, `RECENT BRANCH`,
   `LAST MIGRATION`, `LAST BACKUP`), then the value at body size. Two of them carry a chip instead
   of text (`NANO`).
6. **A spatial panel** on the right: a dotted-grid canvas holding one infrastructure card — Primary
   Database, region with flag, instance class, and a metric row underneath (`CPU 0%` · `Disk 0%` ·
   `RAM 0%` · `0/60 conns`). Two small controls sit at its top-right corner.
7. **A metrics strip** across the bottom: a headline stat pair (`13 Total Requests`, `53.8% Success
   Rate`) with a **time-range selector** (`Last 60 minutes`) at the right, then a horizontally
   scrolling rail of service cards — each with a count, a `WARNINGS` / `ERRORS` legend with coloured
   dots, a sparkline of bars, and the window's start and end timestamps. A pager arrow overlays the
   rail's right edge.

### The properties worth taking

- **Absence is written out.** *"No branches"*, *"No backups"*, *"Waiting for project…"* — never a
  dash, never an empty tile. This is the discipline this console already holds, arriving from a
  reference rather than from our own rules, which is the strongest form of confirmation available.
- **A skeleton, not a spinner.** `LAST MIGRATION` renders a grey bar the width its value will be.
  The console has no skeleton anywhere; every pending state is a sentence.
- **The label register is separate from the value register.** Small caps, letterspaced, muted, at
  the smallest step — so a label never competes with what it labels. Our `text-meta` exists but is
  not used as a distinct register this way.
- **A fact is a tile, not a row.** Icon, label, value, in a grid. We render the same facts as table
  rows and prose paragraphs.
- **Status colour ships with a word.** The legend reads `● WARNINGS  ● ERRORS`; the dot never
  travels alone. That is our rule, independently arrived at.
- **A time range is a control.** Every count on the strip is scoped by it, and it says which window
  it is in. Nothing in our console is time-scoped or says what window it covers.

### What we would put in each slot

| Their slot | Ours |
|---|---|
| Org / project / branch switchers | fleet / repository / vendor — the levels the specification already defines |
| The six fact tiles | last indexed, index coverage, open findings, watched vendors, last run, corpus attempts |
| `LAST MIGRATION` skeleton | any figure still being fetched |
| The infrastructure card with live metrics | **nothing yet** — see below |
| Service cards with sparklines | per-detector or per-vendor finding counts over a window |
| `Last 60 minutes` | a window over `observed_error_window`, which is stored per window already |

### The one that does not transfer, and why it is worth saying

The dotted canvas with a database node is a **topology** view: one entity, its location, its live
resource use. We have no live resource metrics and no infrastructure to draw — and
`2026-08-05-sync-console-architecture.md` Task 11 already ruled against a layered bipartite diagram
of call sites against operations, with the argument at `:1364-1372`. That ruling stands; a canvas
with one card on it is not the counter-example that reopens it.

What *is* transferable from that panel is subtler: **the screen gives its most spatial fact its own
region rather than a row in a table.** For us the equivalent is the binding surface — call sites
joined to operations — and the question that reopens Task 11 is whether the table is measured
failing at scale, not whether a competitor drew a picture.

---

## 4. Supabase — the same overview, populated, with a world map (2026-08-06)

The same screen as entry 3 with data in it and the sidebar collapsed to icons. Three things the
empty state did not show:

- **The sidebar collapses to a 40px icon rail** and the page reflows into the space. The navigation
  is not a fixed cost.
- **The spatial panel is a world map**, dimmed almost to the background, with one bright dot for the
  active region and faint dots for the others. It is a *locator*, not a chart: it answers "where is
  this" at a glance and carries no axis, legend or number.
- **Sparklines are dense and small** — a week of bars in a 300px card, green for success and red for
  errors, with only the window's start and end labelled. No axis, no gridline, no tooltip visible.

The map is the clearest example so far of a property this console has none of: **a region whose job
is orientation rather than measurement.** What ours would hold there is a question the plan has to
answer, not a picture to copy — and Task 11's ruling against a bipartite diagram still stands, so
the honest candidates are the ones that locate rather than diagram.

---

## Measurement: the console at 1890px, taken 2026-08-06 against the running tree

The owner asked why the console does not use the screen. Measured in Chrome at a 1890px viewport on
`/` rather than reasoned about:

| | |
|---|---|
| Viewport | 1890 |
| `documentElement.scrollWidth` / `clientWidth` | 1875 / 1875 — **no horizontal overflow** |
| `body`, `#root`, `main` | 1875 each — **no width cap anywhere** |
| Content region inside the 24px gutter | 1827 |
| Cards | 1827 — full width |
| Tables | 1795 — full width |
| **Paragraphs** | **491** |

**So the app does fill the window, and the screen still looks empty.** Both are true, and the second
is the real finding: `max-w-prose` caps every paragraph at 491px and leaves roughly **1330px of
nothing to its right**, while the table beneath it spends a **1290px column on a vendor name**.

The layout is one column, stacked vertically, at every width. There is no composition — no rail, no
regions, nothing placed beside anything else. A single column that is technically full-width reads
as emptier than a narrower page that is arranged, which is exactly what the three reference examples
demonstrate: Superlog puts a 360px fact rail beside its content, Supabase puts a spatial panel
beside its tiles.

That is the defect. Not a cap — an absence of arrangement.

---

## 5. Supabase — seven screens, and the system underneath them (2026-08-06)

Table Editor, SQL Editor, Schema Visualizer, Functions, Extensions, Indexes, Settings. Seven screens
is enough to stop describing screens and describe **the system that generates them** — which is what
this console needs, because our problem is not one bad page.

### The chassis, present on all seven

1. **Two-tier navigation.** A 40px **icon rail** for the product's top-level areas, plus a ~215px
   **contextual sidebar** for the area you are in. The sidebar carries the area's name as a heading
   at its top (`Database`, `Table Editor`, `SQL Editor`) and groups its items under **small-caps
   letterspaced labels** — `DATABASE MANAGEMENT`, `ACCESS CONTROL`, `CONFIGURATION`, `PLATFORM`.
   The rail never changes; the sidebar is the level you are inside.
2. **A page header of exactly two lines**: a display-size title and a one-sentence subtitle saying
   what the page is for — *"Manage what extensions are installed in your database"*, *"Improve query
   performance against your database"*, *"Connections, security, and network configuration"*.
3. **A control bar directly beneath it**: scope selectors and a search on the left, secondary
   actions in the middle, **one green primary action on the right**. Never two greens.
4. **Tables with uppercase letterspaced column headers**, the identifying column as a link, a `⋮`
   overflow at the row's end, and the type printed beside the column name where a type exists
   (`id uuid`, `metadata jsonb`, `embedding vector`).
5. **Chips for enumerated values** — `FREE`, `PRODUCTION`, `NANO`, `SHARED`, `NEW`, `Invoker`. A
   closed vocabulary renders as a chip; an open one renders as text.
6. **Keyboard hints inline, on the surface they belong to** — `Ctrl K`, `G then D`, `Ctrl ⏎`,
   `Hit CTRL+SHIFT+K to generate query`.

### Four patterns we have no equivalent of

- **An empty section is a card with an explanation and the way out.** *"No shared queries — share
  queries with your team by right-clicking on the query."* Ours are single sentences; theirs tell
  you what would fill the space and how.
- **A detail opens in a right drawer and the page dims behind it.** The Indexes screen shows the
  index's `CREATE UNIQUE INDEX …` as syntax-highlighted SQL in a panel with `Cancel` at the bottom,
  without leaving the list. We navigate away for every detail.
- **A settings screen is one card per setting**: title, a prose explanation of what it does and what
  it costs, the control at the right, and the card's own `Cancel`/`Save`. Not a form.
- **A footer bar on a data view** carrying pagination, page size, the record count, and a
  Data/Definition toggle. Our pagination sits inside the card with no fixed home.

### The schema visualizer, and what it does to Task 11

The Database screen renders a **node-link diagram**: three table nodes, each a card with a header
and one row per column, orthogonal connectors between foreign keys, a minimap, `Auto layout`, and
`Copy as SQL`. It is the best thing in these seven screens and it is genuinely useful.

`2026-08-05-sync-console-architecture.md` Task 11 ruled against a layered bipartite diagram of call
sites against operations. **This is a real counter-example and it should be weighed rather than
waved away** — but the ruling stands, and the reason is cardinality, not principle. Their diagram
draws three tables and about fifteen columns. Ours would draw thousands of call sites against
hundreds of operations, and the plan's argument at `:1364-1372` is exactly that a diagram at that
cardinality becomes a hairball that answers nothing a table cannot.

What transfers is narrower and real: **a node card whose header is the entity and whose rows are its
fields, with the relationship drawn rather than described.** At *one* binding — one call site, one
operation, one vendor change, the rungs between them — that is a picture worth having, and it is not
the fleet-wide diagram Task 11 refused.

### Where this leaves the plan

Every one of the four properties above, plus the chassis, is buildable against data we already hold.
None of it needs a write path except the settings pattern, which needs one and therefore waits.
