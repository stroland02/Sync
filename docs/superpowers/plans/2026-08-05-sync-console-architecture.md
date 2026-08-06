# M4 Slice 4 — The console becomes a product

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.
>
> **Read before Task 1:** `.claude/rules/interface-originality.md`, `DESIGN.md`, and the *Global
> constraints* section below in full. The constraints are not preamble; several of them are
> sentences currently on screen that a builder can delete by accident.

**Goal:** Make the operator console immersive, legible and modern, while every claim on screen
stays exactly as defensible as it is today.

The owner looked at it and said they were "just kind of seeing a bunch of engineering
information". That judgement is correct and it is measurable. Across `web/src`: 21 `<Card>`, 17
`<Table>`, 1 chart, 5,781 lines, three shadcn primitives, 7 `onChange`, 3 `<Button>`, 2 `onClick`,
1 `<input>`. No filtering, sorting, search, drill-down, tab, dialog, skeleton or command palette
anywhere. Eight screens, one idiom, repeated.

**But the fix is not styling.** The measurements above describe a component gap. Three passes over
the tree found something larger underneath, and the whole shape of this plan follows from it:
**seven of the console's eleven routes cannot be reached by clicking.** The information
architecture is printed in the header as a caption and implemented nowhere. That is established in
the next section with the link graph, and it is the reason navigation ranks above the lead screen,
which ranks above the component catalogue.

---

## What was established before anything was designed

Four passes were required before a single decision. Each is recorded here because a task that
disagrees with one of them is wrong, and because a reviewer needs to be able to check the finding
rather than take the design on faith.

### 1. The operator's questions, and which screen answers each

What someone opens this console to find out, in the order they need to know it. The mapping is to
the console as it exists on `m4-dashboard` at `6f62eae`.

| # | The question at 9am | Screen that answers it | Reachable by clicking from `/`? |
|---|---|---|---|
| 1 | **Did anything break that I have to act on today?** | Nothing. `/codebase` gives open findings per vendor; no screen orders by severity, by age, or by "new since yesterday". | `/codebase` — **no** |
| 2 | **Is a run stuck right now?** | `/` runs table, partially — it shows time since the last checkpoint, but cannot sort or filter by it, and shows fifty rows of an unbounded set. | yes, and it degrades to *no* at scale |
| 3 | **Sync opened this pull request — should I merge it?** | `/findings/:id/workflow`. The flagship, and the best-answered question in the console. | **yes** |
| 4 | **Stripe shipped a breaking change — what does it hit?** | `/bindings/vendors/:vendorId/operations/:operationId`. Answers it precisely. | **no** |
| 5 | **Is this repository actually covered, and what does Sync not see in it?** | `/bindings/repositories/:repoId` and `/repositories/:repoId/observed`. | **no** (both) |
| 6 | **Which detector is producing my false positives?** | `/detectors`. | **no** |
| 7 | **Is Sync worth what it costs?** | `/` repair record, partially — attempts by disposition, strategy and tier, with no time axis and no merge rate. `BACKLOG.md:151-153` records that merge rate, routing accuracy and cost per merged patch have never had a sample. | yes, partially |

**The link graph, which is the evidence.** Following `<Link>` elements only, starting at `/`:

```
/  ──→ /findings/:id/workflow ──→ /findings/:id ──→ /vendors/:vendorId ──→ /findings/:id
```

Four routes. The remaining seven form a separate component:

```
/bindings ──→ /bindings/repositories/:repoId
         └──→ /detectors ──→ /codebase ──→ /vendors/:vendorId
/observed-telemetry ──→ /repositories/:repoId/observed
/bindings/vendors/:v/operations/:op        (linked from nothing)
```

`/bindings` is linked from nothing (`App.tsx:31`; the only inbound links are breadcrumbs on pages
you cannot get to). `/observed-telemetry` is linked from nothing. `/codebase` is reachable only
through `/detectors`, which is reachable only through `/bindings`. `/bindings/vendors/:v/
operations/:op` — the screen that answers question 4, the single most product-defining question
Sync exists to answer — has no inbound link anywhere in the tree.

The header renders `Fleet → Codebase → API Services → Errors & Incidents → Finding` as a paragraph
of static text (`layouts/app-shell.tsx:24-26`). It is a caption describing a navigation that does
not exist.

One more, smaller and in the same class: the fleet's repositories table renders `repo_id` as plain
text (`features/fleet/repositories-table.tsx:59`) while `/bindings/repositories/:repoId` exists and
takes exactly that value. The console holds a row and its destination on the same screen and does
not connect them.

**So, plainly: this console has a route table, not an information architecture.**

That needs stating carefully, because it is not a criticism of the thinking that produced it. The
*conceptual* architecture is good and `BACKLOG.md:169-171` is right to say so — eight screens map
the graph end to end, each screen's grain is stated, and the hierarchy is real. What does not exist
is the *implemented* architecture: no navigation, no entry points, no ordering by urgency, and an
index screen that leads with the machine's activity rather than with the operator's first question.
An information architecture is a set of paths a person can walk. A route table is a set of
addresses. This is the second one.

> **Correction, 2026-08-05, after Task 1 shipped.** The paragraph above is wrong in its most
> confident sentence. The conceptual architecture is *not* good, and neither this plan nor the two
> before it ever opened the document that defines it. The hierarchy every one of them treats as
> settled — `Fleet → Codebase → API Services → Errors & Incidents → Finding → Solution Workflow` —
> matches the design document's information architecture at three of its six levels. Establish 5
> below carries the reconciliation, route by route, and Task 9 carries the work. Nothing else in
> this plan is retracted: the reachability finding was real, and the navigation Task 1 built is the
> right mechanism pointed at a hierarchy nobody had checked.

The corollary decides the ranking: **adding filtering and sorting to a screen nobody can reach
improves nothing.** Navigation comes first.

### 2. Every load-bearing honesty sentence currently on screen

These are the product. They go into *Global constraints* below as a protected set, and they are
reproduced verbatim here because a builder cannot protect what they cannot see. **Restyling any of
these is allowed. Deleting one, shortening one, collapsing one behind a disclosure, or moving one
into a tooltip is not.**

**The refusal to score.** `features/fleet/fleet-page.tsx:10-12`:

> There is no composite health figure here on purpose. A scalar that averaged three gates would
> collapse "we could not check" onto the same axis as "we checked and it passed", which is the
> failure this console exists to replace.

**Staleness is not liveness.** `features/fleet/runs-table.tsx:114-123`:

> There is no heartbeat and no process registry — the only evidence a run exists is a checkpoint
> row, and "last checkpoint" is staleness, not liveness. A run parked at `await_ci` blocks inside
> that node while it waits on the customer's CI, and writes no checkpoint for as long as that
> takes, by design. A run parked at any other node with the same silence has probably died. Nothing
> in this data tells the two apart, so this screen does not guess: there is no dot and no colour
> here, because a wrong guess would be a confident wrong verdict.

**Grain, twice.** `features/fleet/runs-table.tsx:51-54`:

> One row per checkpoint thread, not one per finding — a finding retried across generations writes
> a new thread each generation, and each generation is its own row here.

`features/fleet/corpus-summary.tsx:71-75`:

> Every repair attempt the graph has recorded, one row of `migration_outcome` per attempt. A
> finding retried three times writes three attempts here and counts once toward findings.

**Absence is not zero.** `features/fleet/repositories-table.tsx:37-41`:

> Every repository the API Dependency Graph holds at least one call site from. A repository that
> was configured but never indexed has no row here — the same absence as one that was never
> configured at all, because the index cannot tell the two apart.

The same fact, said again at `features/bindings/bindings-page.tsx:90-91` and at
`features/bindings/repository-coverage-page.tsx:55`, which is the longest of them:

> This repository was never indexed, or it was indexed and nothing bound to a vendor was found.
> Those are the same answer here: the index has no configuration table, so a repository it has
> never seen a call site from is indistinguishable from one nobody ever configured.

**The two-meanings sentences.** Four of them, and they share a phrase on purpose.
`features/bindings/binding-surface-page.tsx:116` and `:117`; `:157-160`:

> Either this operation has never had a call site here, or it had one that was later retracted —
> this table cannot tell the two apart.

`features/bindings/repository-coverage-page.tsx:162` and `:258` carry the same construction for
observed traffic and for error windows.

**A count is not a rate.** `features/bindings/repository-coverage-page.tsx:252` and
`features/telemetry/observed-telemetry-page.tsx:118`:

> A count here has no denominator and is not a rate — it says nothing on its own

and the docstring that holds the reason, `features/telemetry/error-windows-table.tsx:4`.

**Provenance, at two levels.** `components/provenance.tsx:8-11`:

> Two levels, deliberately not merged. The per-row rung on a finding is the rung of that finding.
> The envelope's rung describes the whole page and goes null whenever the page rests on no single
> binding — which means something different on each route, so `bindingNullLabel` is required rather
> than defaulted.

`components/provenance.tsx:53` enforces it in the type — `bindingNullLabel` is a required prop
with the comment *"Required: null is a fact, and it differs per route."* Four call sites supply a
different sentence each: `vendor-findings-table.tsx:111-112`, `overview-page.tsx:92-93`,
`vendor-changes-table.tsx:103-104`, and the prose form at `binding-surface-page.tsx:59-66`. Every
one distinguishes **none** ("there is no finding here to attribute") from **mixed** ("the findings
on this page do not all rest on one rung"). That distinction is not a nicety; it is the difference
between an absent claim and a conflicting one.

**The rung stays monochrome.** `components/provenance.tsx:22-25`:

> The rung records how a binding was established (static / resolved / observed / …), not how much
> to trust it. Colouring it would restate the scalar confidence score this project rejected twice,
> so it takes the design system's weight and spacing and never its hue.

**Provenance rendered is not provenance visible.** `features/vendors/vendor-findings-table.tsx:52-55`
is a comment holding a layout constraint, and it is load-bearing:

> Rung sits ahead of the call site so it stays on screen at 1280px without a sideways scroll: the
> call site is the widest cell in this table — a path from a customer repository — and no fixture
> here is long enough to prove that on its own.

**Four kinds of nothing.** `components/states.tsx:3-6`:

> "No findings", "that finding is not open", "the API is not running" and "still asking" are four
> different answers. A spinner that never resolves and a silent empty table are both the console
> refusing to say which one it is.

**The console admits when it is out of date with its own backend.** Three places where a value
outside the known vocabulary renders a sentence rather than a blank or a guess:
`lib/format.ts:62` ("a rung this console does not recognise — the provenance vocabulary has changed
since this view was written"), `features/workflows/node-sequence.tsx:45`, and
`features/workflows/run-outcome.tsx:113`.

**Answers about the thing, not failures of the console.** `features/workflows/workflow-page.tsx:107`
is the fullest form, and the pattern repeats at `finding-page.tsx:102`,
`detector-accountability.tsx:128`, `overview-page.tsx:56`, `runs-table.tsx:60`,
`corpus-summary.tsx:81`, `repositories-table.tsx:47`, `binding-surface-page.tsx:177`.

### 3. What breaks at real scale

The fixture holds six call sites. A customer repository holds thousands, and the largest table in
this console is an aggregate across *every* indexed repository. `scripts/seed_console.py` is
gaining a `--scale N` flag as this plan is written, which turns everything below from an argument
into a measurement.

**Fourteen of the seventeen tables fetch their whole set. None of the seventeen can sort, filter or
search.** Seventeen is the count of `<Table>` sites; twenty-one render, because two `TallyTable`
components are each instantiated three times. The only user-driven narrowing anywhere in the tree is
`features/bindings/binding-lookup-form.tsx:43`, three text fields that navigate to a URL rather than
filter a rendered table. The three client-side `.sort()` calls in the tree are fixed alphabetical
orderings, not controls.

| Table | Source | Bound | At 10,000 rows |
|---|---|---|---|
| `binding-surface-page.tsx:121` call sites | `GET /api/bindings/vendors/{v}/operations/{op}` — **no limit, no offset** | none | ~2 MB of JSON parsed on the main thread; 10,000 `<tr>` × 6 `<td>` ≈ 70,000 DOM nodes; first paint in seconds; `Ctrl-F` returns hundreds of hits with no way to narrow. **This is the worst case in the console and it is also the screen that answers the product's defining question.** |
| `binding-surface-page.tsx:180` vendor changes | same request | none | a vendor with a long feed history renders every change ever ingested |
| `repository-coverage-page.tsx` × 4 tables | `GET /api/repositories/{repo}/coverage`, `/observed` | none | observed calls and observed shapes are per-operation-per-repository and unbounded; four unbounded tables stacked on one screen, all fetched before anything paints |
| `observed-telemetry-page.tsx` × 3 tables | `GET /api/repositories/{repo}/observed` | none | same payload, same problem, second implementation |
| `bindings-page.tsx`, `observed-telemetry-hub-page.tsx`, `fleet/repositories-table.tsx` | repository lists | none | bounded by repository count — tolerable now, and the first thing to break in a multi-tenant control plane |
| `overview-page.tsx`, `detector-accountability.tsx`, `corpus-summary.tsx` × 3 | aggregates | bounded by vendor / detector / enum cardinality | fine, and they should stay tables |
| `runs-table.tsx`, `vendor-findings-table.tsx`, `vendor-changes-table.tsx` | paginated, `PageControls`, offset in the URL | 50/page | the only three that hold — and **a stuck run at offset 900 is still invisible**, because paging is not finding |

Four consequences, and the last two were found by reading the Python rather than the console.

- **Pagination without sort or filter is not a scale answer.** It bounds the DOM and leaves the
  operator paging through 200 screens to answer "which run is stuck". The three tables that
  paginate are not solved; they are contained.
- **Client-side sort over a paginated set would be a false claim.** Sorting the fifty rows already
  fetched and labelling the column "Severity ↓" says *these are the highest-severity findings* and
  means *these are the highest-severity of an arbitrary page*. That is the exact defect class this
  milestone has closed six times. **Sort and filter over a paginated set are server-side or they do
  not exist.**
- **The pagination that exists is not pagination.** Every "paginated" route materialises the whole
  result set in Python and slices it: `rows[offset : offset + limit]` at `src/sync/mcp/tools.py:339`
  and `items[offset : offset + limit]` at `src/sync/dashboard/fleet.py:73`. **No `GraphStore` read
  method accepts a `limit` or an `offset`, and no SQL in the tree carries a `LIMIT`.** So the three
  tables that appear contained are bounded only in the DOM: the database still returns every row,
  Python still builds every model, and the payload is smaller only because the last step throws most
  of it away. At ten thousand findings, `GET /api/vendors/stripe?limit=50` reads ten thousand rows to
  return fifty. The fix in Task 3 is therefore deeper than adding route parameters — it reaches the
  store.
- **The lead screen's own source is the worst offender.** `/api/overview` fetches every open finding
  on purpose, by probing for the total and then re-reading with `limit=max(total, 1)`
  (`src/sync/api/app.py:130-131`), because grouping by vendor needs them all. That is the route
  Task 2's lead screen is built on. It is correct today and it does not survive a real customer.

Three smaller scale cliffs found in the same pass, each named so a task can close it:

- **`offset` is unclamped.** `_limit_param` clamps limit to `[1, 500]` (`app.py:88`), but `offset`
  goes through `_int_param` (`app.py:67-79`), which returns the default on a parse error and clamps
  nothing. A negative offset reaches the slice.
- **A finding becomes unfindable by id past ten thousand.** `GET /api/findings/{id}` has no index
  read behind it; it scans `whats_at_risk` up to `_SCAN_LIMIT = 10_000` (`app.py:59, 165`). The
  docstring at `app.py:160-164` states the limit honestly and says a deployment past it adds a by-id
  read to the surface. That deployment is the one this plan is preparing for.
- **`observed_telemetry` is N+1.** It reads every observed call for a repository, then issues one
  shape read per distinct `(vendor_id, operation_id)` pair (`graph_views.py:187-194`). A repository
  touching two hundred operations is two hundred and one queries per page load.

**What to do with `--scale N`.** It becomes the plan's measuring instrument rather than a
convenience, and three values are named so results are comparable across tasks:

- `--scale 6` — today's fixture. The regression baseline.
- `--scale 1000` — the point at which an unpaginated table is unpleasant. Every task that claims a
  scale property proves it here first.
- `--scale 10000` — the point at which it is broken. **A task that changes a table's scale
  behaviour records a before-and-after observation at `--scale 10000`: time to first paint, DOM
  node count from `document.querySelectorAll('*').length`, and payload size from the network
  panel.** Three numbers, written into the task's report. A claim of "now it scales" without them
  is not evidence, and `verification-before-completion` applies.

### 4. What the platform promised and never showed

Every deferral across the three console plans, with its stated retiring condition checked against
the tree today. **A deferral whose condition is met is ready work, not parked work.**

| Deferred | Stated condition | Checked today |
|---|---|---|
| **Premium components, bento grids** | "after the data model is visible" (`2026-07-30-sync-m4-dashboard.md:253`) | **MET.** `BACKLOG.md:118-120` rules it retired: eight screens cover the graph end to end. This plan is the work it gates. |
| **A layered bipartite SVG diagram** — which call sites one vendor change touches | "not in this slice because slice 2 has not yet shipped the fleet screen it would sit beside" (`2026-08-05-sync-console-design-system.md:366-369`) | **MET.** The fleet screen shipped. Ranked, and it is what loses — see *Ranking*. |
| **A frontend test runner** | "a console screen needs logic that cannot live in a view model" (`2026-08-04-sync-m4-slice-2.md:544`) | **MET, and it was already met before this plan.** Decision 6 below. |
| **`framer-motion` transitions** | "the layout has stopped moving" (`2026-08-04-sync-m4-slice-2.md:505`) | **MET and shipped** — `lib/motion.ts`, three sanctioned usages. Nothing owed. |
| **TanStack Table + `@tanstack/react-virtual`** | Named as the thing to try before MUI: "try this first, because it is strictly cheaper" (`2026-08-05-sync-console-design-system.md:420-423`) | **Pre-authorised and never tried.** Decision 4 below. |
| **The abandonment vocabulary in the console** | owner accepts the specification **and** `AbandonCode` plus `classify` land in `sync.remediate` (`2026-08-04-sync-m4-slice-2.md:545`) | **HALF met.** The owner accepted the specification (`2026-08-04-sync-m4-slice-2.md:592-596`). `grep -rn "AbandonCode\|def classify" src/sync/` returns nothing. Still correctly deferred; the console has nothing to render. |
| **MUI for an enterprise grid** | shadcn's `Table` plus TanStack headless "has been tried and recorded as failing — not predicted to fail" (`2026-08-05-sync-console-design-system.md:426-428`) | **Not met.** TanStack has not been tried. Task 4 is what makes this condition checkable for the first time. |
| **`@react-three/fiber` scenes** | "a spatial fact enters the data" (`2026-08-05-sync-console-design-system.md:371-373`) | **Not met.** Nothing on the roadmap produces a coordinate. |
| **`react-grid-layout` draggable widgets** | three conditions together: a per-operator preference store, more panels than one viewport, and an operator who has asked (`2026-08-05-sync-console-design-system.md:399-401`) | **Not met.** None of the three. |
| **SPA history fallback for deep links** | "something serves `web/dist`" (`2026-08-04-sync-m4-slice-2.md:543`) | **Not met.** Nothing serves it. |

**And one capability is built, frozen, and has never been called.** `whats_at_risk` accepts a
`path` filter and a `severity` filter (`src/sync/mcp/tools.py:89-95`). The transport passes
`vendor` and nothing else (`src/sync/api/app.py:151-156`). So **filtering findings by severity —
the single most valuable filter in the console, and the one the operator's first question needs —
already exists on the frozen surface and no route exposes it.** It costs one query parameter on an
existing route, not a change to `tools.py`. That reorders part of Task 3 and it is the cheapest
real capability in this plan.

Two further items are promised in the transport and shown nowhere, both from `B91`
(`BACKLOG.md:196-209`): `server_address` and `url_template` on observed calls, and `args_keys`,
`response_fields_read` and `loop_depth` on binding call sites are sent and rendered by no screen.
And two screens read `GET /api/repositories/{repo}/observed` and disagree about which fields they
show, with neither saying it is partial — the coverage page's calls table omits `Method` and
`Max resend`, the telemetry page's shapes table adds `Enum values`. That is the same *a reader
cannot tell what this view can see* class the milestone has closed six times, duplicated across two
implementations of one payload.

**Three things nothing in the tree can answer**, listed because a screen must not imply otherwise
and because two of them look like ordinary features:

- **A closed finding.** `open_findings` is the only findings read `GraphStore` offers, `finding` has
  no `closed_at`, and every findings-bearing route rests on it. "Findings closed this week" has no
  source, and neither does a burn-down.
- **Anything over time.** No route returns a bucketed series, a trend or a delta. The only
  date-shaped parameter in the transport is `since` on `/api/vendors/{id}/changes`, which is a
  lexical string comparison against an ISO timestamp (`tools.py:212`), not a parsed date.
- **A fleet-wide route narrowed to one repository.** `/api/overview`, `/api/detectors`,
  `/api/corpus` and `/api/runs` are fleet-wide and take no `repo_id`.

### 5. Added 2026-08-05 — the hierarchy, reconciled against the document that defines it

Everything above was established by reading the console. This was established by reading the
console *against the specification*, which is the pass that was never made — not by this plan, not
by `2026-08-04-sync-m4-slice-2.md`, and not by `2026-07-30-sync-m4-dashboard.md`. Between them
those three plans built a route registry, a persistent navigation and a command palette on a
hierarchy none of them checked, and the sixth level of that hierarchy is a word the design document
does not contain.

The authority is
`docs/superpowers/specs/2026-07-25-sync-self-maintaining-apis-design.md:392-411`, section *M4 —
Hosted control plane / Information architecture*. It states two rules and they are the test applied
throughout this section:

> Every level of the interface is an entity the system already stores, which means the interface
> cannot drift from the domain — there are no invented screens and no dead ends. (`:394`)

> A user starts from a repository, not from a vendor list, because the question they actually have
> is "what is wrong with my code" rather than "what is Stripe doing". (`:407`)

#### The reconciliation, route by route

All eleven routes in `web/src/lib/routes.ts`, against the seven levels the specification's
hierarchy declares at `:396-405`.

| Route (`routes.ts`) | Console label and declared level | Specification | Verdict |
|---|---|---|---|
| `/` (`:68-74`) | **Fleet**, level `Fleet` | no such level; the word appears **zero times** in the specification | **invented**, and it is the index route |
| `/codebase` (`:76-82`) | **Codebase**, level `Codebase` | `Codebase (the selected repository)` (`:397`) | **reparented** — the name survives, the grain does not. `/api/overview` groups open findings by vendor across every repository and takes no `repo_id` (`app.py:130-131`), so this is a fleet-wide vendor roll-up wearing the repository level's name |
| `/bindings/repositories/:repoId` (`:84-90`) | **Repository coverage**, level `Codebase` | `Codebase (the selected repository)` (`:397`) | **renamed** — this *is* the specified root. It takes exactly the parameter that level needs, and it is addressed as a child of `/bindings` |
| `/bindings` (`:92-98`) | **Bindings**, level `API Services` | no such level | **invented**. Its own child is the repository screen, and its content is a three-field lookup form (`binding-lookup-form.tsx:43`) — a repository selector that does not know it is one |
| `/vendors/:vendorId` (`:100-106`) | **Vendor**, level `API Services` | `API Services — vendors the indexer found in this repository` (`:398`) | **matches spec**, except that "in this repository" has no repository to be in |
| `/bindings/vendors/:vendorId/operations/:operationId` (`:108-114`) | **Binding surface**, level `API Services` | no such level | **invented**, and judged correct — see below |
| `/detectors` (`:116-122`) | **Detectors**, level `Errors & Incidents` | no such level; `detector` is named as an attribute at `:401` | **invented**, and judged correct as an aggregate rather than a level — see below |
| `/observed-telemetry` (`:124-130`) | **Observed telemetry**, level `Errors & Incidents` | no such level | **invented**. It is a repository picker, which exists only because the repository level does not |
| `/repositories/:repoId/observed` (`:132-139`) | **Observed telemetry**, level `Errors & Incidents` | `Signals … grouped by role: vendor, signal source, human surface` (`:399-400`) | **reparented** — a signal source's output, rendered where findings belong |
| `/findings/:findingId` (`:141-147`) | **Finding**, level `Finding` | `Finding` (`:402`) | **matches spec** |
| `/findings/:findingId/workflow` (`:149-155`) | **Solution workflow**, level `Solution Workflow` | `Solution Workflow — the remediation run` (`:403`) | **matches spec** |

And the three levels the specification declares that no route implements:

| Specification | Console | Verdict |
|---|---|---|
| `Codebase (the selected repository)` as the entry point (`:397`, `:407`) | nothing selects a repository anywhere | **missing** |
| `Signals — one panel per attached integration, grouped by role` (`:399-400`) | nothing | **missing** |
| `Pull Request — with its evidence bundle` (`:404`) | `pr_url`, one row in the workflow's evidence panel (`features/workflows/evidence.tsx:131`) | **missing as a level** — present as a link, absent as a destination with an address |

Three of eleven routes match. Two are the specification's own levels renamed or regrained. Four
are invented. Two are reparented. Three specified levels were never built.

#### The judgement on each invented level

The specification's test is literal — *is this level an entity the system already stores* — so it
is applied literally, and it does not return the same answer four times.

**`Fleet` is a legitimate surface that must not be the root.** Slice 2's decision 2 already
conceded the first half of the case against it: *"a fleet view is not a graph entity. There is no
node in the API Dependency Graph whose grain is 'every run'"*
(`2026-08-04-sync-m4-slice-2.md:48-50`). It then granted itself an exception for a directory and
the exception was spent on the index route. That is the drift.

But the question the screen answers — *what is this system doing right now, across everything* — is
real, an operator has it, and it is unanswerable from any single repository. The specification's own
M4 opens by promising a "multi-tenant runtime, dashboard, organization onboarding" (`:390`) and then
draws a hierarchy that starts inside one repository. Those two sentences cannot both be complete, so
here the document is what is stale, and it has been amended.

**That leaves the load-bearing sentence, and it must be answered directly rather than around.** *"A
user starts from a repository, not from a vendor list."* Read narrowly it forbids a vendor list at
the entry, and gives its own reason — the user's question is "what is wrong with my code", never
"what is Stripe doing". A fleet surface asks the first question across every codebase rather than
the second, so it does not violate the sentence's reason. Read broadly it names the first screen,
and Fleet violates it.

The narrow reading is the right one, **and it does not acquit the console**, because the sentence
protects something neither reading is about: the repository level is the *scope* every level
beneath it inherits. Take it out and nothing below has a scope. That is exactly what happened —
`/codebase`, `/detectors` and the corpus roll-up are all fleet-wide because there is no repository
to narrow them to, and the plan above records that gap as a data limitation
(*"a fleet-wide route narrowed to one repository"*) without noticing it is a hierarchy defect.

**Ruling: `Fleet` survives, at `/`, as an index into repositories — not as a replacement for one.**
The corrective work is to build the Codebase level, not to delete the fleet screen. Recorded under
`.claude/rules/autonomous-development.md` as a decision the owner can reverse; reversing it means
demoting `/` to `/fleet` and making the repository list the index, which is one entry in one array.

**`Binding surface` is legitimate and the specification is stale.** Every element it renders is
stored: `vendor_change`, `call_site`, and the `binding_rung` on each binding. It passes the test
outright. What the specification lacks is a path to it — its hierarchy reaches a vendor's
consequences only through Errors & Incidents, which presumes every consequence of a vendor change
is a finding. It is not. A change no detector has claimed still has a binding surface, and *"Stripe
shipped a breaking change — what does it hit?"* is this plan's operator question 4 and the single
most product-defining question the console answers. Amended into the specification as a level under
API Services.

**`Detectors` is legitimate, and it is an aggregate rather than a level.** A detector is not a
table. But `finding.detector` is `NOT NULL` and the table's grain is *one row per claim, per
detector, per call site* (`src/sync/graph/schema.sql:122-137`) — attribution is stored, deliberately,
for the same reason the rung is: *"a false positive that cannot be attributed to a rung cannot be
fixed"* (`CLAUDE.md`). Storing the attribution and never rendering the aggregate is holding the
evidence for the feedback loop and not showing it. `routes.ts:17-20` argues its placement at Errors
& Incidents by analogy with `/codebase` over API Services, and that reasoning is right — it is an
aggregate over the level, in the same relation `/codebase` has to `/vendors/:id`. Amended into the
specification on those terms. Its defect is scope, not existence: it is fleet-wide.

**`Observed telemetry` is a stored entity in the wrong place, and this one is drift.**
`observed_call`, `observed_shape` and `observed_error_window` are tables, so it passes the stored
test — and the specification already has a home for it that nobody looked up. *Signals — one panel
per attached integration, grouped by role: vendor, signal source, human surface* (`:399-400`), with
the three roles defined in the M5 table at `:455-459`. Observed telemetry is what a signal source
produced. Declaring it at `Errors & Incidents` puts a signal where a claim belongs, and the rung
discipline exists to keep those apart. **Reparent it under Signals, scoped by repository.** Note
what this does not close: Signals as specified is one panel *per attached integration*, and observed
telemetry is one panel of one role. Building it does not build the level.

**`Bindings` is not a level at all.** A binding is stored; `/bindings` does not render one. It
renders three text fields that navigate to a URL, and its child is the repository screen. It is the
repository selector, built sideways because the level that should have held it was missing. It
disappears into the Codebase level, and the lookup form goes with it.

#### The corrected hierarchy

Written as the specification writes it, with every surviving screen placed. Levels the
specification already had are unmarked; the three added by the 2026-08-05 amendment are marked
`[amended]`; what is not yet built is marked `[missing]`. Two nodes below are shown in place and are
**not levels** — observed telemetry is a panel of the Signals level, and detector attribution is an
aggregate over Errors & Incidents. Neither belongs in `GRAPH_LEVELS`, and the specification's own
authoritative block omits both for that reason.

```
Fleet  [amended]                    every repository the index has seen, and what the machine
   │                                has been doing across all of them; an index into the level
   │                                below, never a substitute for it
   └── Codebase (the selected repository)      what the index sees here, and what it does not
         └── API Services           vendors the indexer found in this repository
               ├── Signals  [missing]          one panel per attached integration, grouped by
               │     └── Observed telemetry    role: vendor, signal source, human surface
               ├── Binding surface  [amended]  the call sites one vendor operation binds, and
               │                               the rung each binding came from
               └── Errors & Incidents          findings for this vendor, from any detector
                     ├── Detector attribution  [amended]   which detector raised what, and on
                     │                                     what evidence — an aggregate over
                     │                                     this level, not a level beneath it
                     └── Finding
                           └── Solution Workflow     the remediation run
                                 └── Pull Request  [missing]   with its evidence bundle
```

Where each of the eleven lands:

| Today | Becomes |
|---|---|
| `/` Fleet | **Fleet.** Keeps `/`. Gains a repository list that links into the level below, which is the whole of what makes it an index rather than a replacement |
| `/bindings/repositories/:repoId` Repository coverage | **Codebase.** Promoted and re-addressed to `/repositories/:repoId`. This screen already exists and already takes the right parameter |
| `/codebase` | folds into Codebase, scoped by repository. Its fleet-wide vendor roll-up is what Fleet should carry |
| `/bindings` | **removed.** The lookup form moves onto Codebase |
| `/vendors/:vendorId` | **API Services**, scoped by repository |
| `/bindings/vendors/:v/operations/:op` | **Binding surface**, under API Services. Address unchanged |
| `/observed-telemetry` | **removed.** It is the repository selector under another name |
| `/repositories/:repoId/observed` | **Signals**, under API Services. The first of the three roles to have a panel |
| `/detectors` | **Errors & Incidents**, as an aggregate, scoped by repository |
| `/findings/:findingId` | **Finding.** Unchanged |
| `/findings/:findingId/workflow` | **Solution Workflow.** Unchanged |
| — | **Pull Request**, new: a destination with an address, carrying the evidence bundle that today is one `pr_url` row |

**What this costs, honestly.** Every fleet-wide route takes no `repo_id` (`app.py`), so scoping the
levels below Codebase is a transport change and not a routing change. That is why Task 9 is a day
rather than an afternoon, and why it is sequenced where it is.

---

## The architectural spine, before any file

Nine decisions. Each is argued from the operator, the graph and the product position. None of them
is justified by a component being available, and none by a competitor having it —
`.claude/rules/interface-originality.md` binds every one, and the test it states is applied
explicitly at the end of each.

### 1. Navigation is a first-class surface, and the route registry is its single source of truth

The console's routes *are* the API Dependency Graph — that decision holds and is right
(`App.tsx:1-6`, `2026-07-30-sync-m4-dashboard.md:40-50`). What was never built is the means of
walking it. Seven routes unreachable is not a polish defect; it is the console failing to deliver
four of its seven operator questions at all.

So the shell gains a persistent navigation region, and it is driven by data rather than by markup:
`web/src/lib/routes.ts` declares every destination once — path, label, the graph level it sits at,
and a one-line statement of the question it answers. `App.tsx` builds its `<Route>` elements from
that array, the navigation renders from it, and the command palette searches it. **A route that
exists and is not in the registry cannot be declared**, because the registry is what declares it.

That is the structural fix for the defect, and it is also what makes it stay fixed: reachability
becomes a property of one array rather than a habit maintained across thirteen files.

The navigation is always visible, not behind a menu button. A hidden navigation is how a console
arrives back at seven unreachable routes, one shortcut at a time.

### 2. The console leads with the operator's decision, and says which mode it is in

The index today is the fleet: every run the checkpointer holds, newest first, plus the repair
record and the repository roll-up. It answers *what has the machine been doing*. The operator's
first question is *what do I have to act on*, and those are different questions.

**At four findings and at four thousand these are not the same screen, and pretending otherwise is
where dashboards start lying.** With four findings, a count of four is worse than the four rows —
the reader has to click to learn what they already could have read. With four thousand, a list is a
log.

So the lead screen holds one component that switches on cardinality, **and states which mode it is
in**, because a screen that silently changes what it shows is the defect class this milestone has
closed six times:

- Below the threshold: every row, with the sentence *"this is all of them"*.
- At or above it: the count, the ordering rule, and the top N, with the sentence *"showing 10 of
  4,213, ordered by severity then age"*.

The threshold is a constant in one place with its reasoning in a comment, and it is a rule with a
wrong answer, which is why Decision 6 exists.

**What the lead screen may contain.** Figures the data genuinely holds, each with the sentence that
says what it excludes, at the same visual weight as the figure:

- Open findings and their distribution across vendors, from `GET /api/overview`.
- Runs and their dispositions **over the newest page only**, from `GET /api/runs` — and the figure
  says so, because the route paginates and a total across all runs is not in the payload.
- The repair record, from `GET /api/corpus`, carrying the grain sentence already at
  `corpus-summary.tsx:71-75`.
- Repositories the index has seen, from `GET /api/repositories`, carrying
  `repositories-table.tsx:37-41`.
- Detector attribution, from `GET /api/detectors`.

Every one of those routes exists today. The lead screen needs no transport change, which is what
makes it a parallel task.

**What the lead screen may not contain**, restated because a lead screen is exactly where somebody
reaches for it: no composite number, no score, no traffic light, no green dot, no liveness pulse,
no count-up. Rejected on the record three times, most recently at `fleet-page.tsx:10-12`, and the
reason has not changed.

**The one thing the lead screen genuinely cannot do today**, stated rather than faked: it cannot
order findings by severity across all vendors, because `GET /api/overview` returns per-vendor counts
and no route passes the `severity` filter the frozen surface already accepts
(`tools.py:89-95`). Task 3 exposes it. Until then the screen says the ordering is by vendor and open
count, which is what it actually is.

**And one thing the lead screen must not paper over.** `/api/overview` builds its answer by reading
*every* open finding (`app.py:130-131`). The lead screen is therefore the most expensive page in the
console at scale, and it is the one page an operator opens first. Task 2 ships against that route as
it is — the screen is not the place to fix a transport — but the screen's own report records the
measured load time at `--scale 10000`, so the cost is a number somebody has seen rather than a
surprise Task 3 discovers.

### 3. Disclosure may hide a value. It may never hide a qualification

Evidence is the product, and all the evidence at once is a dump. `evidence.tsx` is 319 lines
rendering every checkpoint key on one screen, several through `JSON.stringify`. That has to
collapse. But collapsing is exactly how an honest console becomes a dishonest one, so the rule is
stated as a mechanism rather than as an intention:

**A disclosure may hide a value the reader could look up. It may never hide the sentence that says
what the data cannot support.** If collapsing a section would take a qualification with it, the
qualification lifts out of the section and stays on the page.

Permanently visible, never behind a click, never in a tooltip alone:

1. **The per-row rung** on any row that carries one.
2. **The page-level rung and its null label**, including which of *none* and *mixed* it is.
3. **The absence marker.** `ABSENT` is a rendered fact, not an empty cell.
4. **Every "cannot tell the two apart" sentence**, and every "that is an answer, not a failure".
5. **Every denominator caption** — the error-count sentences, and the three abandonment classes
   that never reach `migration_outcome`.

And the converse, which is what makes a disclosure honest rather than merely tidy: **a collapsed
section states its own cardinality in its header.** "Evidence (11 keys)", not "Evidence".
"Observed calls (1,204)", not "Observed calls". A closed section whose label does not say how much
is behind it hides the fact that there is anything behind it.

This has to be a rule rather than a review habit, because **no detector will catch it**.
Impeccable's `content-hidden-at-rest` excludes any `display: none`, `hidden` or `aria-hidden`
subtree from its denominator entirely — a collapsed accordion, a closed disclosure and an inactive
tab panel are all removed rather than counted
(`docs/superpowers/references/notes/impeccable-interface-quality.md:267-277`). The tooling is
structurally blind here. The rule is the only guard.

### 4. What a table is in this console, decided once

Seventeen tables, none of which can sort or filter, on a console whose largest set is unbounded.
The dependency question is real and `docs/superpowers/references/engineering/dependencies-and-packaging.md`
governs it, so it is argued rather than assumed.

**First, what that note does and does not reach.** Its central concern is the extension seam: "If
writing a Twilio adapter means installing Postgres, LangGraph, tree-sitter and the Claude Agent
SDK, nobody writes one, and the open-core thesis is a licence file rather than a strategy"
(`:37-44`). `web/package.json` is `private: true`, ships in no wheel, and is not in `sync.core`'s
dependency tree or anybody's. **That argument does not reach the console's manifest at all.** What
does reach it are the note's general rules — enforce the lock, bound where a break is known, gate
dependency changes — and its standing point that a dependency's cost is the tree it drags and the
verification it needs, not the line in the manifest.

**Second, the operator argument, which is what actually decides it.** The scale finding above rules
out the naive answer: client-side sort over a paginated set is a false claim, so the honest sort is
server-side. That means the *sorting and filtering* a table library sells is not what this console
needs most. What it needs from a table library is three things a hand-rolled `<Table>` cannot give:

- **A column model.** Seventeen tables each hand-write their headers and their cells, so a column
  is defined in two places that can silently disagree, and an eighteenth screen writes an
  eighteenth copy. A declarative column definition is what makes a column's header, its cell, its
  width and its visibility one object.
- **Column visibility.** The Rung column problem (`vendor-findings-table.tsx:52-55`) was solved
  once, by hand, by reordering. That fix does not generalise past seven columns and it does not
  survive a customer with longer paths. Letting the reader hide columns is the general answer, and
  it is safe here only because of the constraint below.
- **Virtualisation**, for the sets that are legitimately fetched whole and large.

**Decision: adopt `@tanstack/react-table` and `@tanstack/react-virtual`, headless, with a stated
scope and one prohibition.**

- Both are headless: they render nothing. The markup stays shadcn's and `DESIGN.md` stays the only
  source of truth. No second design system enters the tree, which is the cost the MUI protocol
  exists to avoid (`2026-08-05-sync-console-design-system.md:409-418`).
- Same vendor as `@tanstack/react-query`, already a dependency (`web/package.json:12`).
- **The prohibition: client-side sorting or filtering over a paginated set is forbidden.** Where a
  set is paginated, the sort and the filter live in the view model and the route, and TanStack
  renders the answer the server gave. Where a set is fetched whole and bounded, client-side
  filtering is honest and is allowed.
- **Column visibility never hides a column carrying a qualification.** The rung column and the
  absence-bearing columns are not hideable. This is enforced in the column definition — a column
  declares `hideable: false` — not left to the reader's judgement.

This is also what finally makes the MUI protocol's trigger condition checkable: it requires shadcn
plus TanStack headless to have been *tried and recorded as failing*, and after Task 4 that
sentence can be evaluated for the first time.

### 5. The component layer: seven primitives earn their place, three do not

`shadcn` is a devDependency and vendors source into `web/src/components/ui/` rather than adding a
package; `radix-ui` and `lucide-react` are installed; `components.json` is configured
(`style: radix-nova`, `baseColor: neutral`, `cssVariables: true`). So ten primitives cost zero new
dependencies. **Zero cost is not an argument, and each one is decided on the operator's problem.**

**Earn their place:**

- **`command`** — eleven destinations, two keystrokes. The direct fix for the reachability defect,
  and the affordance an operator reaches for after the second day.
- **`dialog`** — the verbatim things the system recorded (compiler output, a raw vendor-change
  payload, an evidence blob) need a full-height reading surface. `evidence.tsx:231`'s
  `max-h-72 overflow-auto` is a compromise between reading it and not losing the page. Also
  required by `command`.
- **`badge`** — `RungBadge` (`provenance.tsx:27-36`) is a hand-rolled badge already. One primitive
  replaces it, and the monochrome constraint travels with the component rather than with a comment
  that the next screen will not read.
- **`tooltip`** — earns it **only under a constraint**: a tooltip may carry a *definition*, never a
  *fact*. What `resolved` means is a definition. Which rung this row is, is a fact and stays in the
  cell. Two `title=` attributes already do the definition job (`provenance.tsx:31,65`); a real
  tooltip is keyboard-reachable, touch-reachable and styled, which `title=` is not.
- **`tabs`** — earns it **only where the tab labels carry their own cardinality**.
  `repository-coverage-page.tsx` stacks four unbounded tables; four tabs is right, and four tabs
  labelled "Observed calls (1,204) / Shapes (18) / Error windows (0)" is honest, because a closed
  tab still says what is behind it — including that it is empty, which is a fact and not an
  absence. Without the counts, tabs are a way to hide three of four datasets from a reader who
  never clicks. The counts are the condition, not a nicety.
- **`separator`** — mechanical. `border-t border-border pt-3` is hand-written in at least three
  places (`provenance.tsx:60`, `runs-table.tsx:114`, and the coverage page). One primitive.
- **`dropdown-menu`** — scoped to one job: the column-visibility control from Decision 4. **Not**
  as a navigation menu; Decision 1 forbids a hidden nav.

**Do not earn their place, each rejected from the operator rather than from taste:**

- **`skeleton`** — `LoadingState` names what is being asked for (`states.tsx:48-55`), which is
  strictly more information than a grey rectangle imitating content that has not arrived. Already
  ruled once (`2026-08-05-sync-console-design-system.md:316-317`); named again here because "it is
  free and every modern app has one" is the argument that will be made.
- **`scroll-area`** — a styled scrollbar. The existing `overflow-auto` containers work, and a
  custom scrollbar is where *the reader could not see there was more* defects live. On a console
  whose position is that it does not hide evidence, replacing the platform's own affordance for
  "there is more below" with a painted one is a bad trade.
- **`sheet`** — a drawer holds secondary content while the primary content stays. This console's
  drill-downs are destinations, and the URL is load-bearing: *"Deep links are the point"*
  (`App.tsx:4-6`). A sheet has no URL, so a colleague cannot be sent to what you are looking at.
  Rejected from the product position, not from the catalogue.

**The rule governing the next one.** A primitive enters `components/ui/` when a named screen has a
problem it solves, the problem is stated as a sentence about the operator, and the component is
added through the shadcn CLI so the source is ours to constrain. A primitive does not enter because
it is available. **A primitive that hides a qualification does not enter at all.** And a standing
signal rather than a hard cap: `components/ui/` passing twelve files without every one of them
named by a screen is the moment to stop and re-read this section.

### 6. The frontend gets a test runner, because the deferral's own condition is met

Slice 2's decision 5 said classification belongs in Python, where the test runner is
(`2026-08-04-sync-m4-slice-2.md:89-99`), and deferred a frontend runner behind the condition *"a
console screen needs logic that cannot live in a view model"*.

**That condition was met before this plan, and the tree already contradicts the premise.**
`isRunTerminal` (`api/queries.ts:82-84`) and `hasLiveRun` (`api/queries.ts:116-118`) are
classification — is this run terminal, does this page hold a live run — they live in TypeScript,
and nothing tests them. Their docstrings say what they are guarding against ("reading it as
terminal stops the poll on a live run, which freezes the screen on a stale answer") and no test
holds that.

This plan adds more of the same kind, and it is a kind that cannot move: the cardinality threshold
in Decision 2, the disclosure-header count in Decision 3, and the palette's coverage of the route
registry are properties of the *rendered view*, not of the payload. Moving them into Python would
mean the transport computing presentation, which the "one contract, two consumers" decision
forbids — the frozen surface serves an agent, and an agent does not have a viewport.

**Ruling: add Vitest, `@testing-library/react` and `jsdom`. The deferral retires.**

The cost, stated rather than waved past. Three devDependencies in a `private: true` package that
ships nowhere — the packaging note's central concern does not reach it (Decision 4). One `test`
script, one CI job beside the existing `web` job. Roughly half a day to wire. **And a standing cost
that is the real one: the repository gains a second test discipline, and `CLAUDE.md`'s test-first
rule — write the failing test, run it, watch it fail for the reason you expect — now applies to
TypeScript on every task.** That is a permanent increase in per-task cost and it is the reason this
ranks fifth rather than first.

**Scope, so the runner does not become a component-snapshot habit.** It tests classification,
derivation and structural invariants: `isRunTerminal`, `hasLiveRun`, the cardinality threshold,
disclosure-header counts, `describeRung`'s exhaustiveness over the rung union, `formatElapsed`, and
**every route in the registry being reachable from the shell**. It does not assert class names, it
does not snapshot markup, and it does not replace the human observation for anything visual.

That last test earns its own sentence: **"every declared route is reachable" is the defect this
plan exists to fix, and it is mechanically checkable.** A plan that fixes reachability and does not
hold it fixed will watch it regress on screen nine. An honest alternative was considered — a Python
test parsing `App.tsx` and `routes.ts`, in the shape of the existing constant-mirror tests at
`tests/test_api_routes.py:440-460` — and it would work. It is not why the runner is added; the
classifiers are. But once the runner exists, this guard belongs beside them.

### 7. A ninth screen is expensive because three files are shared and mutable

Concretely, today, a new screen edits: `api/types.ts` (475 lines), `api/client.ts` (192),
`api/queries.ts` (201), `App.tsx`, and `layouts/app-shell.tsx`. Five files, three of them shared
and mutable, all five touched by every screen. Two agents building two screens collide in all
three of the shared ones — which is exactly the failure this plan's own parallel partition is
written to avoid, generalised.

**The fix: a feature owns its own transport.** `api/http.ts` keeps only the primitive — `getJson`,
the error classes, `DEFAULT_LIMIT`, `PageParams`, the `Page<T>` envelope. Each `features/<x>/`
gains an `api.ts` holding that feature's types, its fetch functions and its hooks. `App.tsx` and
the navigation both read `lib/routes.ts` from Decision 1.

After that, **a ninth screen touches one new directory and one entry in one array.** That is the
concrete answer to the owner's "easily improved", and it is measurable: count the files a new
screen's diff touches outside its own directory. Today five. After Task 6, one.

This is a mechanical split with no behaviour change, and it touches every feature directory — so it
**cannot** run in parallel with any task that edits a feature. It is serialised deliberately.

### 8. Immersive means checkable, and it is a consequence of hierarchy

"Immersive" for a marketing page means motion and depth. For an operator console read all day it
has to mean something a reviewer can walk up to and check. Three properties, each verifiable:

1. **The operator never leaves the graph to find the graph.** From any screen, the parent level is
   one interaction away via the breadcrumb, every sibling level via the navigation, and every child
   via a row link. Every declared route is reachable within two interactions from any other.
   *Check: walk it, from each of the eleven routes.*
2. **The screen fits its own question.** On a 1280×800 viewport the answer to the screen's headline
   question is above the fold with no horizontal scroll. The Rung-column fix was the first instance
   of this check; it becomes a per-screen one. *Check: load each screen at 1280×800 at `--scale
   1000` and look.*
3. **Nothing is chromatic that the data does not license.** `DESIGN.md`'s rule already: the run
   outcome, the error state, and absence. *Check: disable colour and confirm every screen still
   reads.*

**And the thing that produces the felt quality, said so it is not mistaken for a layer applied
afterwards.** `DESIGN.md` already carries it: *"What grows is the range — the page title, the
value-versus-label distinction — not the average."* Immersion here is the *absence of decisions the
reader has to make*: one absence glyph, one rung treatment, one table idiom, one place the
navigation lives, one meaning for every colour on screen. It is not the presence of effects. A
console that adds depth it has nothing to communicate with has spent its one channel on nothing.

Motion, depth and colour all assert, and `DESIGN.md` constrains all three already. **This plan adds
no new motion and no new elevation level.** Everything it adds is structural: where things are,
what is visible at once, and what a table can do.

### 9. Everything this plan adds must survive the honesty audit, and the audit is a step

Six defects of the form *the console asserts something the data does not hold* have been found and
closed, several by removing a field or a column rather than adding one. This plan adds navigation,
a lead screen, filters, disclosures and a column-visibility control — five new ways to make a
claim.

So each task carries an explicit audit step, and it asks one question of every new element: **what
does this assert, and does the data hold it?** A filter chip asserts a set is complete. A count in
a tab label asserts a total. A sort arrow asserts an ordering over a population. A collapsed
section asserts that what is hidden is less important. Each of those is checkable against the
payload, and each is a place this console has failed before.

---

## Global constraints

- `CLAUDE.md` is binding for all Python. Test-first with a proven RED; explicit
  `encoding="utf-8"` on every `read_text`/`write_text`/`open`/`subprocess.run(text=True)`;
  comments state constraints rather than narrating edits.
- **`DESIGN.md` is binding for every visual decision.** No new token, no new elevation level, no
  new spacing value, no seventh type step. Each of those is a decision argued in that file, not a
  value added here.
- **`.claude/rules/interface-originality.md` binds every screen.** Do not open anything under
  `docs/superpowers/references/screenshots/`. The test, applied per change: state the thing as a
  problem the operator has, without naming where it came from. If the justification needs the
  pointer, delete the pointer and make the argument from the graph and the operator — or drop the
  change.
- **The protected sentences.** Every sentence quoted in *Establish 2* above stays on screen, at
  full length, not behind a disclosure and not in a tooltip. Restyling is allowed. Any task that
  removes one is wrong even if the screen looks better. **Verification for every task in this plan
  includes re-reading its own diff for a deleted qualification.**
- **No composite health number, no score, no traffic light, no green dot, no liveness pulse, no
  count-up.** Rejected on the record three times. A lead screen and a design system are the two
  moments somebody reaches for one; this plan is both.
- **The provenance rung stays monochrome**, at both levels, and is never a hideable column.
- **The API stays read-only.** No route mutates the graph, triggers a run, or touches a customer
  repository. The behavioural read-only test (`tests/test_api_routes.py`) extends to every new
  route; a new route it does not cover is an untested hole in the guarantee.
- **`src/sync/mcp/tools.py` is frozen.** The console reads aggregate answers through
  `sync.dashboard`, per-finding answers through `GraphSurface`, and the transport issues no SQL.
- **Sort and filter over a paginated set are server-side or they do not exist** (Decision 4).
- **`scripts/seed_console.py` and `tests/test_seed_console.py` are owned by another session.** Do
  not edit either. Use `--scale N`; do not change it.
- **A scale claim ships with three numbers** at `--scale 10000`: time to first paint, DOM node
  count, payload size. Before and after.
- Web verification stays `npm run build` clean and `npm run lint` with no new error-level
  violations, plus stated human observation — until Task 5 lands, after which `npm test` joins it.

---

## File structure

```
web/src/lib/routes.ts                     new — the route registry: path, label, level, question
web/src/layouts/app-shell.tsx             the nav region replaces the static caption
web/src/layouts/site-nav.tsx              new — persistent navigation, rendered from the registry
web/src/layouts/command-palette.tsx       new — ⌘K over the registry
web/src/components/ui/{command,dialog,badge,tooltip,tabs,separator,dropdown-menu}.tsx
                                          new — vendored by the shadcn CLI, Task 0
web/src/App.tsx                           routes built from the registry

web/src/features/fleet/**                 the lead screen
web/src/features/repositories/**          the codebase screen, folded into the lead screen's answer

src/sync/dashboard/graph_views.py         pagination, filters, the severity roll-up
src/sync/dashboard/fleet.py               the disposition roll-up across all runs
src/sync/api/app.py                       new parameters on existing routes
src/sync/api/__main__.py                  wiring

web/src/components/data-table/**          new — the TanStack column model and the virtual body
web/src/api/http.ts                        new — the transport primitive, after the split
web/src/features/<x>/api.ts               new per feature — types, fetches, hooks
web/vitest.config.ts, web/src/**/*.test.ts new
```

---

## Task 0: Vendor the primitives — ten minutes, before dispatch

**Files:** `web/src/components/ui/{command,dialog,badge,tooltip,tabs,separator,dropdown-menu}.tsx`,
`web/package.json` if the CLI adds a peer.

This exists as its own task so that Tasks 1, 2 and 3 are genuinely parallel from minute zero rather
than blocked on one another's first commit. It is mechanical and it makes no design decision.

- [ ] **Step 1:** `npx shadcn@latest add command dialog badge tooltip tabs separator dropdown-menu`
  in `web/`. `components.json` is already configured, so the source lands in
  `web/src/components/ui/` under this project's own tokens.
- [ ] **Step 2:** Confirm no new runtime dependency was added beyond what `radix-ui` and
  `lucide-react` already provide. If the CLI adds one, stop and record it — a "zero new
  dependencies" claim that turns out false is exactly the kind of thing this repository catches
  rather than discovers later.
- [ ] **Step 3:** Re-theme each to `DESIGN.md`'s tokens where the CLI's output reaches for a
  Tailwind stock value. Radius resolves to `--radius-control` or `--radius-surface`; nothing
  renders below `--text-meta`.
- [ ] **Step 4:** `npm run build` clean. Commit.

**Verification a reviewer can run:** `git diff --stat web/package.json` shows no change to
`dependencies`. `grep -rn "text-\[10px\]\|rounded-xl\|rounded-lg" web/src/components/ui/` returns
nothing new.

---

## Task 1: Navigation, the route registry, and the command palette

**Files:** Create `web/src/lib/routes.ts`, `web/src/layouts/site-nav.tsx`,
`web/src/layouts/command-palette.tsx`. Modify `web/src/App.tsx`,
`web/src/layouts/app-shell.tsx`. **~1 day.**

**Exclusive.** Touches nothing under `web/src/features/`, nothing under `web/src/api/`, nothing
under `src/sync/`.

The console has eleven routes and four of them are reachable. This task is what turns the route
table into an information architecture, and it is ranked first because every other improvement
lands on a screen somebody has to be able to get to.

- [ ] **Step 1:** `lib/routes.ts` — one array, one entry per destination, each carrying `path`,
  `label`, `level` (its position in `Fleet → Codebase → API Services → Errors & Incidents →
  Finding → Solution Workflow`), and `question`: one sentence saying what an operator opens it to
  find out. The parameterised routes carry a `param` marker so the navigation can render them as
  destinations that need a subject rather than as dead links.
- [ ] **Step 2:** `App.tsx` builds its `<Route>` elements from the registry. A route that is not in
  the registry does not exist — that is the invariant, and it is what stops screen nine from being
  orphaned the way screens two through eight are.
- [ ] **Step 3:** `site-nav.tsx` — a persistent navigation region in the shell, rendered from the
  registry, grouped by `level`, with the current route marked using the brand hue, which
  `DESIGN.md` reserves for exactly this ("links, focus, and the current node"). Always visible; not
  behind a menu button (Decision 1).
- [ ] **Step 4:** Replace the static caption at `app-shell.tsx:24-26`. The hierarchy stops being a
  paragraph describing navigation and becomes the navigation. **The hierarchy sentence itself is
  not deleted** — it moves into the navigation as the grouping, so a reader still learns that the
  routes are the graph.
- [ ] **Step 5:** `command-palette.tsx` — ⌘K / Ctrl-K opens `Command` over the registry. **Scope:
  routes only in this version.** Entity search — finding a specific finding id or file path — needs
  a search route in the view model and a relevance rule with a wrong answer; it is a slice, not a
  step, and it is named in *What I am not proposing*.
- [ ] **Step 6:** Close the dead-row defect: the fleet's repositories table renders `repo_id` as
  plain text (`features/fleet/repositories-table.tsx:59`) beside a route that takes exactly that
  value. **This one line is the exception to the exclusive file set** — it is one `<Link>` in a file
  Task 2 also owns, so it moves to Task 2. Recorded here so it is not lost.
- [ ] **Step 7:** The honesty audit (Decision 9). The navigation asserts that these are the
  console's destinations. Confirm the registry holds every route `App.tsx` declares and no route it
  does not, and that a parameterised destination is not rendered as though it were clickable
  without a subject.
- [ ] **Step 8:** `npm run build` clean, `npm run lint` no new error-level violations. Commit.

**Verification a reviewer can run:** open `/`, and reach all eleven routes **using only the
keyboard and the mouse — never the address bar.** Record which ones took more than two
interactions. Then delete one entry from `routes.ts` and confirm the route disappears from both the
navigation and the palette *and* stops resolving, which is what proves the registry is the single
source rather than a second one. Restore it.

---

## Task 2: The lead screen — what the console says at four findings and at four thousand

**Files:** `web/src/features/fleet/**` (all files, including new ones),
`web/src/features/repositories/overview-page.tsx`. **~1.5 days.**

**Exclusive.** Reads existing hooks from `api/queries.ts` and **does not modify it**; every route
it needs already exists. Touches nothing under `layouts/`, `lib/`, `components/ui/`, or
`src/sync/`.

- [ ] **Step 1:** The cardinality switch (Decision 2), as one component used by every panel on the
  screen. Below the threshold it lists every row and says *"this is all of them"*. At or above it,
  it states the count, the ordering rule and the top N: *"showing 10 of 4,213, ordered by vendor
  and open count"*. The threshold is one constant in one place with its reasoning in a comment. **A
  test in Task 5 pins it; write the component so the rule is a pure function that a test can hold.**
- [ ] **Step 2:** Compose the lead screen from the five existing routes, each figure carrying the
  sentence that says what it excludes at the same weight as the figure. **The runs disposition
  figure states that its scope is the newest page**, because `GET /api/runs` paginates and no total
  by disposition exists in the payload. That sentence is not a hedge; it is the difference between
  a true statement and a false one.
- [ ] **Step 3:** The "what this screen cannot tell you" panel — the four standing limits, at the
  same visual weight as the figures, permanently visible: repositories never indexed are invisible
  and indistinguishable from ones never configured; three abandonment classes never reach
  `migration_outcome` so the repair record's denominator excludes the earliest failures; there is
  no heartbeat, so last-checkpoint is staleness and not liveness; severity ordering across vendors
  is not available until the view model computes it. **This panel is the product position rendered
  as a component, and it is not a footnote.**
- [ ] **Step 4:** Carry every protected sentence forward verbatim: `fleet-page.tsx:10-12`,
  `runs-table.tsx:51-54`, `runs-table.tsx:114-123`, `corpus-summary.tsx:71-75`,
  `repositories-table.tsx:37-41`, and every `EmptyState` detail on the screen. Diff the strings
  before and after; a reworded qualification is a changed claim.
- [ ] **Step 5:** Link the repository rows to `/bindings/repositories/:repoId` (Task 1's step 6,
  landed here because this file belongs to this task).
- [ ] **Step 6:** Fold `overview-page.tsx`'s answer into the lead screen's vendor distribution.
  `/codebase` stays a route and a destination — it holds the per-vendor detail the lead screen
  summarises — but it stops being the only place that answer lives.
- [ ] **Step 7:** The honesty audit. Every number on this screen: what is its denominator, what is
  its scope, and does a sentence beside it say so? A figure whose scope is a page and whose label
  implies a total is the defect this step exists to catch.
- [ ] **Step 8:** Measure and record the lead screen's load time at `--scale 10000`.
  `/api/overview` reads every open finding by design (`app.py:130-131`), so this screen is the most
  expensive page in the console and the first one an operator opens. **The number goes in the task's
  report whatever it is.** Do not fix it here — the screen is not the place to fix a transport, and
  Task 3 owns that file.
- [ ] **Step 9:** `npm run build` clean, `npm run lint` no new error-level violations. Commit.

**Verification a reviewer can run:** load `/` at `--scale 6` and confirm every panel lists its rows
and says so. Reseed at `--scale 10000` and confirm every panel switches to counting and says which
mode it is in and what the ordering is. Then read the screen with the question *"what would I
wrongly believe if I only read the big numbers?"* and confirm the answer is nothing — every figure
has its qualification beside it.

---

## Task 3: Scale, in the view model — pagination, filters, and the severity roll-up

**Files:** Modify `src/sync/graph/store.py`, `src/sync/dashboard/graph_views.py`,
`src/sync/dashboard/fleet.py`, `src/sync/api/app.py`, `src/sync/api/__main__.py`. Create/modify
`tests/test_graph_store.py`, `tests/test_dashboard_graph_views.py`,
`tests/test_dashboard_fleet.py`, `tests/test_api_routes.py`. **~2 days.**

**Exclusive.** Pure Python. Touches nothing under `web/`. Does not touch
`scripts/seed_console.py` or `tests/test_seed_console.py`, which another session owns. **Does not
touch `src/sync/mcp/tools.py`, which is frozen** — everything below is reachable without it.

Two things this task is, and the order matters. The obvious one is that fourteen routes return
whole sets. The one found by reading the Python is that **the three routes that look paginated are
not**: they materialise everything and slice in Python (`tools.py:339`, `fleet.py:73`), and no
`GraphStore` read takes a `limit`. So the work reaches the store, and adding a route parameter over
an unbounded read would be the same defect with a smaller payload.

- [ ] **Step 1:** Failing tests against the real Postgres on 5433, following
  `tests/test_dashboard_queries.py`'s fixture pattern. Required properties, each a way this can be
  wrong:
  - **`GraphStore` reads bound in SQL.** `call_sites_for_operation`, `all_vendor_changes`,
    `observed_calls`, `observed_error_windows` and `open_findings` gain `limit` and `offset` and a
    separate count, and the emitted SQL carries `LIMIT`. **Proven by asserting on rows read, not on
    rows returned** — a test that only checks the returned length passes against the Python slice
    that exists today and has therefore shown nothing.
  - `binding_surface` paginates its call sites and its changes **independently**, each with
    `items`, `total`, `next_offset`, and `next_offset` null on the last page.
  - `binding_surface` filters by `repo_id` and by `binding_rung`, and an empty filtered result is
    an empty page rather than an error.
  - The repository-observed views paginate their three sets independently, **and the shape read
    stops being N+1** (`graph_views.py:187-194` issues one query per distinct operation): one read
    over the operation set, asserted by counting queries rather than by timing.
  - `fleet.runs` gains a disposition roll-up across **every** run, not the current page, returned
    beside the page rather than inside it — so the lead screen's runs figure can stop qualifying
    its scope, and so the qualification is removed because the fact changed rather than because
    somebody found it inconvenient.
  - **A severity roll-up over open findings** returning a count per severity **and** the total, so
    the lead screen shows a distribution without inferring the total by summing. A sum over a
    filtered set is not a total, and asserting it is one is this milestone's recurring defect.
  - **Idempotency and grain hold:** re-running any of these over the same rows returns the same
    answer, and no count of findings is computed by counting `migration_outcome` rows.
  - **Every row still carries its rung.** A filter or a projection that drops the rung column is the
    failure `.claude/rules/graph-grain.md` exists to prevent.
- [ ] **Step 2:** RED for the right reasons — run them and read the failures before implementing.
  Several will pass against the Python slice; those are the tests that were written wrong, and
  fixing them before implementing is the point of this step.
- [ ] **Step 3:** Implement, store first and route last.
- [ ] **Step 4:** **Expose the severity filter that already exists.** `whats_at_risk` accepts
  `path` and `severity` (`tools.py:89-95`) and no route passes either. Add both as query parameters
  on `GET /api/vendors/{vendor_id}`. **No change to `tools.py`** — this is a capability that was
  built, frozen and never called, and it is the cheapest real thing in the plan.
- [ ] **Step 5:** **Clamp `offset`.** `_limit_param` clamps limit to `[1, 500]` (`app.py:88`);
  `offset` goes through `_int_param` (`app.py:67-79`) and is clamped nowhere, so a negative value
  reaches the slice. One floor, in the one place, beside the existing clamp.
- [ ] **Step 6:** Extend `RecordingSurface` in `tests/test_api_routes.py` so the behavioural
  read-only test covers every route with its new parameters. A parameter the recording test does
  not see is a hole in the guarantee, and this is the fourth time that test has had to grow.
- [ ] **Step 7:** The honesty audit. Each new filter asserts that the returned set is *every* row
  matching it. Confirm no join silently drops rows, and that a filter over a nullable column reports
  the null bucket by name rather than dropping it. Then confirm no new docstring claims a bound the
  SQL does not carry.
- [ ] **Step 8:** Gates: `uv run pytest tests/test_graph_store.py
  tests/test_dashboard_graph_views.py tests/test_dashboard_fleet.py tests/test_api_routes.py`,
  `uv run lint-imports`, `uv run python scripts/lint_encoding.py src scripts tests`,
  `uv run python scripts/lint_test_skips.py tests`. Commit.

**Verification a reviewer can run:** `uv run pytest tests/test_graph_store.py -q`. Then break the
bound deliberately — remove the `LIMIT` from one store read and let Python slice instead — and watch
the rows-read assertion go red while the rows-returned assertion stays green. **That divergence is
the whole point of this task**, and a test suite that does not show it has tested the old behaviour.
Then seed `--scale 10000` and `curl` the binding-surface route with and without `limit`, recording
both payload sizes and both response times.

**Not in this task, and named so nobody adds it quietly:** a by-id index read for
`GET /api/findings/{id}`, which today scans up to `_SCAN_LIMIT = 10_000` (`app.py:59, 165`). Its
docstring already states the limit and says a deployment past it adds a read to the surface — and
the surface is frozen, so that is a question for the owner rather than a step here. It is an open
question below.

---

## Task 4: The table layer

**Files:** Create `web/src/components/data-table/**`. Modify the consuming tables:
`features/bindings/binding-surface-page.tsx`, `features/bindings/repository-coverage-page.tsx`,
`features/telemetry/*`, `features/vendors/*`. Modify `web/package.json`. **~1 day. Consumes
Task 3.**

- [ ] **Step 1:** `npm i @tanstack/react-table @tanstack/react-virtual`. Record the installed
  versions and the bundle delta from `npm run build`'s output, before and after, in the commit
  body — the MUI protocol requires a measured bundle figure and this is the baseline it will be
  measured against.
- [ ] **Step 2:** `components/data-table/` — one column-model wrapper rendering through shadcn's
  existing `Table` primitives, so no markup and no token changes. A column declares its header, its
  cell, its alignment, and `hideable`. **`hideable: false` on the rung column and on every column
  carrying an absence marker**, enforced in the definition rather than in a reviewer's memory.
- [ ] **Step 3:** Virtualise the bodies of the sets that are fetched whole and bounded. **Do not
  virtualise a paginated set** — fifty rows do not need it, and a virtual container over a paged
  body adds a scroll position that fights the pager.
- [ ] **Step 4:** Wire Task 3's server-side filters into the tables that now have them, as visible
  filter controls — **severity on the vendor findings table first**, since it is the operator's
  first question and the capability has existed unused since `tools.py` was frozen. **A filter
  control states what it filtered to and how many it excluded** — "1,204 of 9,882 call sites,
  filtered to `resolved`" — because a filtered table that does not say it is filtered is a screen
  asserting that this is everything.
- [ ] **Step 5:** Column visibility through `dropdown-menu`, with the non-hideable columns absent
  from the menu rather than present and disabled. A disabled control invites the question; an
  absent one states the constraint.
- [ ] **Step 6:** The honesty audit. A sort arrow asserts an ordering over a population — confirm
  every sort in the tree is server-side over the full set, and that no column offers a sort the
  route does not implement.
- [ ] **Step 7:** Measure at `--scale 10000`: time to first paint, DOM node count, payload size,
  before and after. Write all six numbers into the commit body.
- [ ] **Step 8:** `npm run build` clean, `npm run lint` no new error-level violations. Commit.

**Verification a reviewer can run:** at `--scale 10000`, open the binding surface and confirm the
page paints in under two seconds and the DOM node count is bounded. Then hide the Rung column — and
confirm you cannot. Then set a filter and confirm the table says how many rows it excluded.

---

## Task 5: The frontend test runner, and the reachability guard

**Files:** Create `web/vitest.config.ts` and the test files. Modify `web/package.json`,
`.github/workflows/ci.yml`. **~half a day plus a standing cost.**

- [ ] **Step 1:** `npm i -D vitest @testing-library/react jsdom`. Add `"test": "vitest run"`.
- [ ] **Step 2:** Write the tests **failing first**, against the behaviour that already exists, and
  watch each one fail for the reason expected. `CLAUDE.md`'s rule now applies here: a test that has
  never failed has never been shown to test anything.
  - `isRunTerminal` over each outcome value including `running` and `null`.
  - `hasLiveRun` over an empty page, a page of terminal runs, and a mixed page.
  - The cardinality threshold: at, below and above.
  - The disclosure-header count, including zero — a section labelled "(0)" is a fact and must
    render rather than be suppressed.
  - `describeRung` over every member of the rung union plus an unknown value, which must produce
    the "vocabulary has changed" sentence rather than a blank.
  - `formatElapsed` over null, zero, and a value spanning units.
  - **Every route in `lib/routes.ts` is reachable from the shell**, and every route `App.tsx`
    declares is in the registry.
- [ ] **Step 3:** Prove the reachability test can fail: remove one entry from the registry's
  navigation grouping and watch it go red. Restore it.
- [ ] **Step 4:** Wire `npm test` into the existing `web` job in `.github/workflows/ci.yml`.
- [ ] **Step 5:** Record in `CLAUDE.md`'s test-discipline rule that TypeScript is now test-first
  too, with the scope from Decision 6 — classification and structural invariants, never class
  names, never snapshots.

**Verification a reviewer can run:** `npm test` green. Then delete a route from the navigation
grouping and watch the reachability test go red; restore it. A guard that has never rejected
anything has not been shown to guard.

---

## Task 6: The transport split, so a ninth screen is cheap

**Files:** Create `web/src/api/http.ts` and one `api.ts` per feature directory. Delete
`web/src/api/{client,queries,types}.ts`. Modify every feature's imports. **~half a day. Mechanical.
Must not run in parallel with Task 2, Task 4 or Task 7.**

- [ ] **Step 1:** `api/http.ts` keeps `getJson`, the error classes, `DEFAULT_LIMIT`, `PageParams`
  and the `Page<T>` envelope. Nothing feature-specific.
- [ ] **Step 2:** Move each feature's types, fetch functions and hooks into `features/<x>/api.ts`.
  Shared types that genuinely cross features — `Provenance`, `BindingSource`, `Tally` — stay in
  `api/types.ts`, which shrinks to the shared vocabulary. **Where a type is used by exactly one
  feature, it moves; where it is used by two, it stays. That is the rule, and it is checkable by
  grep rather than by judgement.**
- [ ] **Step 3:** No behaviour change. `npm run build` clean, `npm test` green, and every screen
  loads identically. This is the whole verification: a mechanical move that changes a behaviour has
  a bug in it.
- [ ] **Step 4:** Record the measurement that justifies the task: build a throwaway ninth screen on
  a scratch branch and count the files its diff touches outside its own directory. Before: five.
  After: one. Delete the branch; the number is the deliverable.

**Verification a reviewer can run:** `npm run build`, `npm test`, and walk all eleven routes. Then
`grep -c "" web/src/api/types.ts` and confirm it is a fraction of 475.

---

## Task 7: Progressive disclosure on the evidence-heavy screens

**Files:** Modify `web/src/features/workflows/evidence.tsx`,
`web/src/features/bindings/repository-coverage-page.tsx`,
`web/src/features/telemetry/observed-telemetry-page.tsx`. **~1 day.**

- [ ] **Step 1:** `evidence.tsx` — the verbatim blobs move into a `Dialog`, one per key, with the
  key's `help` sentence staying on the page. **Every qualification lifts out and stays visible**
  (Decision 3). The `<pre>` in the dialog gets the height it deserves.
- [ ] **Step 2:** `repository-coverage-page.tsx` — the four stacked tables become four `Tabs`,
  **each label carrying its own count**, including zero. A tab labelled "Error windows (0)" tells a
  reader something a hidden empty tab does not.
- [ ] **Step 3:** Every collapsed section states its cardinality in its header. Grep the diff for a
  disclosure whose label is a bare noun.
- [ ] **Step 4:** The honesty audit, and it is the sharpest one in the plan. Re-read the whole
  screen with everything collapsed and ask: **what claim can a reader now not see?** If the answer
  is anything other than "a value they can open", the disclosure is wrong.
- [ ] **Step 5:** `npm run build` clean, `npm test` green. Commit.

**Verification a reviewer can run:** load the workflow view with everything closed and confirm that
every sentence from *Establish 2* that applies to that screen is still on it. Then diff the visible
text before and after the change — the set of qualifications must be identical.

---

## Task 8: B91 — two screens read one payload and disagree

**Files:** Modify `web/src/features/telemetry/observed-calls-table.tsx`,
`web/src/features/bindings/repository-coverage-page.tsx`. **~hours.**

`observed-calls-table.tsx` renders `max_resend_count` and not `trace_id`; the embedded card in
`repository-coverage-page.tsx` renders `trace_id` and not `max_resend_count`, `http_method` or
`first_seen`. Neither says it is partial. And `server_address`, `url_template`, `args_keys`,
`response_fields_read` and `loop_depth` are sent by the transport and rendered nowhere.

- [ ] **Step 1:** One component reads that payload, used by both screens.
- [ ] **Step 2:** For each field the transport sends and no screen renders, decide and record: it
  is a screen gap or the payload should stop sending it. **Record the ruling per field**, in the
  component's docstring, where the next reader will find it.
- [ ] **Step 3:** `npm run build` clean, `npm test` green. Commit.

**Verification a reviewer can run:** open both screens and confirm they show the same fields, or
that each states which subset it shows and why.

---

## Task 9: The hierarchy the specification defines, built

**Added 2026-08-05, after Establish 5.** **Files:** Modify `web/src/lib/routes.ts`,
`web/src/App.tsx`, `web/src/layouts/site-nav.tsx`, `web/src/features/bindings/**`,
`web/src/features/telemetry/**`, `web/src/features/repositories/**`,
`web/src/features/fleet/**`. Modify `src/sync/dashboard/graph_views.py`,
`src/sync/dashboard/fleet.py`, `src/sync/api/app.py` for the repository scope. **~1 day.**

**Not exclusive, and it cannot run in parallel with Task 4, 6 or 7** — it moves screens those tasks
edit. It ranks ahead of all three, because a column model, a transport split and a disclosure pass
applied to a screen that is about to be reparented is that work done twice.

- [ ] **Step 1:** `GRAPH_LEVELS` becomes the specification's levels and nothing else, in the
  specification's order, each with the document line that defines it in a comment beside it. A level
  with no such line does not go in the array — it goes in the specification first, as a dated
  amendment with its argument, and only then here. That ordering is the rule, not a preference.
- [ ] **Step 2:** Promote the Codebase level. `/bindings/repositories/:repoId` becomes
  `/repositories/:repoId` and is labelled `Codebase`; the binding lookup form moves onto it;
  `/bindings` and `/observed-telemetry` are deleted from the registry. **Two routes disappearing is
  the deliverable, not a side effect** — both existed to work around the missing level.
- [ ] **Step 3:** Fleet becomes an index. Its repositories table links each row into
  `/repositories/:repoId`, which Task 2 step 5 already half-built. Fleet keeps `/` and keeps every
  protected sentence on it.
- [ ] **Step 4:** Reparent observed telemetry to `Signals` under API Services. **Do not build the
  rest of Signals** — one panel of one role is what the data supports, and the level's own header
  says which of the three roles has a panel and which two do not. A level that implies three
  integrations exist when one does is the same false-completeness defect in a new place.
- [ ] **Step 5:** Scope the levels below Codebase by repository. `/api/overview`, `/api/detectors`
  and `/api/corpus` take no `repo_id` (`app.py`), so this is a transport change: each gains an
  optional `repo_id`, and the screen states which scope it is in. **An unscoped answer rendered
  under a selected repository is a false claim about that repository**, which is this milestone's
  recurring defect wearing a new hat.
- [ ] **Step 6:** The Pull Request level. `pr_url` is one row in the workflow's evidence panel
  (`evidence.tsx:131`); the specification says a level with its evidence bundle (`:404`). Give it an
  address under the workflow and move the push, the `tsc` verdict and the CI run onto it as the
  bundle. Deep links are the point (`App.tsx:4-6`), and today a reviewer cannot send a colleague the
  pull request's evidence.
- [ ] **Step 7:** The honesty audit. Every level now asserts that it is scoped to the repository
  above it. Confirm each one is, and that any panel still reading a fleet-wide route says so beside
  its figure rather than inheriting a scope it does not have.
- [ ] **Step 8:** `npm run build` clean, `npm run lint` no new error-level violations, `npm test`
  green. Commit.

**Verification a reviewer can run:** open `/`, pick a repository, and confirm every figure on every
screen below it changes when you pick a different one. Then read `GRAPH_LEVELS` beside
`specs/2026-07-25-sync-self-maintaining-apis-design.md:429-443` and confirm they name the same
levels in the same order — `:392-411` is the section's original, unamended block and does not hold
`Fleet` or `Binding surface`, so a `GRAPH_LEVELS` compared against it would pass while missing both.
Then delete a level from the specification's block and watch the guard in Task 10 go red.

---

## Task 10: The guard that would have caught this

**Added 2026-08-05.** **Files:** Create `tests/test_console_hierarchy.py`. **~2 hours. Follows
Task 9.**

Establish 5 exists because three plans built an interface hierarchy and none of them opened the
document that defines one. `.claude/rules/console-hierarchy.md` is written and is the cheap half of
the fix; this is the half that fails a build.

**Python, not Vitest** — deliberately, and against Task 5's precedent. This assertion is over two
files' text, needs no DOM and no runner, and belongs in the suite CI already runs on every commit.
It is the same shape as the constant-mirror tests at `tests/test_api_routes.py:440-460`, and open
question 3 already sanctions the Python form.

What it asserts, exactly:

- [x] **Step 1:** Parse the authoritative fenced hierarchy block in
  `docs/superpowers/specs/2026-07-25-sync-self-maintaining-apis-design.md` — the one under
  *Amendment, 2026-08-05*, which the section marks as authoritative — into an ordered list of level
  names, reading indentation for depth. **The section holds two blocks on purpose**, the original
  kept unamended beside what changed, so the test selects by the amendment heading and fails loudly
  if it finds neither block or both unmarked. `encoding="utf-8"`, and the block contains `└──`, so
  this is a file where the encoding rule bites.
- [x] **Step 2:** Parse `GRAPH_LEVELS` out of `web/src/lib/routes.ts`.
- [x] **Step 3:** Assert the two sets are equal, and that the shared ordering matches. **The failure
  message names the offending level and both files**, and states the fix: either the route changes,
  or the specification gains a dated amendment — never the test.
- [x] **Step 4:** Assert every `level:` value in `ROUTES` is a member of `GRAPH_LEVELS`. TypeScript
  already enforces this; the assertion is here so that the *set* is checked against the
  specification rather than against itself, which is precisely the check that was missing.
- [x] **Step 5:** **Prove it can fail, twice** — once by adding a level to `GRAPH_LEVELS` that the
  specification does not have, once by removing a level from the specification's block. Watch both
  go red for the reason expected, restore. A guard that has never rejected anything has not been
  shown to guard, and the naive version of this test — comparing `routes.ts` to `routes.ts` — passes
  against today's drift and shows nothing.

**What it deliberately does not assert:** which route sits at which level. That is a judgement with
a wrong answer and it belongs in a plan and a review, not in a parser. The test holds the level
*vocabulary*, which is the thing that drifted silently.

**Landed 2026-08-06.** `tests/test_console_hierarchy.py`, four tests. Steps 1-4 landed as scoped
above, with two permanent regression tests added beyond the checklist: the block-selection failure
mode (neither block marked authoritative, or both marked) is asserted directly rather than left to
a one-off manual check, since a "fails loudly" contract that is only ever proven by hand tends to
stop being proven. Step 5's two required failures were reproduced, plus a third the checklist did
not ask for and the brief that dispatched this task did: pointing the block selector at the
original, unmarked block instead of the amended one, to confirm the test goes red against a
superseded diagram rather than passing it. All three mutations were applied to in-memory copies of
the file text, never to the committed spec or to `web/src/lib/routes.ts`, so the guard's own
fail-loudly behavior could be proven without touching the files it is a guard *for*.

---

## Ranking, and what loses

Value over cost, for a solo and self-funded project.

| # | Task | Cost | Why it ranks here |
|---|---|---|---|
| 0 | Vendor the primitives | 10 min | Not ranked. It exists so the top three are parallel from minute zero. |
| 1 | Navigation, registry, palette | ~1 day | Seven of eleven routes are unreachable. Four of the operator's seven questions are unanswerable *by clicking*. Every other improvement lands on a screen somebody must be able to get to. |
| 2 | The lead screen | ~1.5 days | The index answers the machine's question, not the operator's. It is what "immersive" means in practice, and it needs no transport change. |
| 3 | Scale in the store and the view model | ~2 days | Fourteen of seventeen tables fetch whole, **and the other three only appear not to** — they slice in Python over an unbounded read. Server-side because the client-side version would be a false claim, and store-side because the route-side version would be the same defect with a smaller payload. Also the task that exposes the severity filter the frozen surface has always had. |
| 4 | The table layer | ~1 day | Consumes Task 3. Also the first thing that makes the MUI protocol's trigger condition checkable. |
| 5 | Vitest and the reachability guard | ~½ day + standing cost | The deferral's condition is met. It ranks below the fixes because it holds them rather than makes them. |
| 6 | The transport split | ~½ day | Pure future value: a ninth screen goes from five shared files to one. Mechanical, and it cannot run in parallel with anything touching a feature. |
| 7 | Progressive disclosure | ~1 day | Real, and the riskiest task in the plan — it is the one that can lose a qualification by accident. Ranked below the structural work because disclosure over an unreachable screen is nothing. |
| 8 | B91 | hours | A known defect with a known fix. Cheap, and it is the sixth instance of a class this milestone keeps closing. |
| 9 | The hierarchy the specification defines | ~1 day | **Added 2026-08-05, and it ranks ahead of 4, 6 and 7 despite its number.** Four of eleven routes are invented, three specified levels were never built, and nothing below Codebase carries a repository scope. A column model, a transport split and a disclosure pass applied to a screen about to be reparented is that work done twice. |
| 10 | The guard that would have caught this | ~2 hours | Added 2026-08-05. Follows Task 9. Holds the fix rather than making it, which is where Task 5 ranks for the same reason. |
| 11 | The layered bipartite diagram | ~1.5 days | **Loses.** See below. *(Renumbered from 9 on 2026-08-05.)* |

**What loses, explicitly:**

- **The layered bipartite SVG diagram (rank 11; it was rank 9 before Task 9 and Task 10 were added
  on 2026-08-05), even though its deferral condition is met.**
  `binding-surface-page.tsx` already answers "which call sites does this vendor change touch", as a
  table, with the rung on every row. The `dataviz` skill's own rule sends more than about seven
  meaningful classes back to a table (`choosing-a-form.md:14`), and a customer repository's binding
  surface is thousands of call sites, not seven. So the diagram buys a second rendering of a
  question already answered, and costs an SVG layout engine, a new accessibility surface with no
  `Ctrl-F`, and a position for every node that the data does not hold. **Reopen it only if Task 4
  shows the table genuinely fails at scale** — which would be a measurement, not a preference.
- **Entity search in the command palette.** The palette navigates routes. Searching for a specific
  finding or file path needs a search route in the view model and a relevance rule with a wrong
  answer, which makes it a slice with its own tests, not a step in Task 1.
- **`skeleton`, `scroll-area` and `sheet`**, each rejected in Decision 5 from the operator rather
  than from taste.
- **Any write path.** Out of scope by the standing read-only constraint, and it needs an
  authorization story that does not exist. An operator still cannot start a run, retry one, or
  close a finding, and this plan does not change that.
- **Charts beyond the one that shipped.** `echarts` is installed and the corpus chart exists. The
  next honest chart candidate is the repair record over time, which needs a timestamp
  `corpus_summary` does not emit — a Python change nobody has asked for.
- **Motion, depth or colour additions of any kind.** `DESIGN.md` constrains all three and this plan
  adds nothing to any of them. Everything here is structural.

---

## What I am not proposing, and what decided it

- **A composite health number, a score, a traffic light, a green dot, or a liveness pulse.**
  Rejected three times on the record and rendered as a refusal on screen today
  (`fleet-page.tsx:10-12`, `runs-table.tsx:114-123`). A lead screen is the single most likely place
  for one to reappear, which is why Decision 2 forbids it by name rather than by inference.
- **Colouring the provenance rung.** `DESIGN.md` and `provenance.tsx:22-25`. If it ever takes
  colour it takes a single-hue ordinal ramp with no good end, never the status hues.
- **Client-side sorting or filtering over a paginated set.** It would assert an ordering over a
  population it does not have. Decision 4.
- **MUI, or any second design system.** The standing protocol's trigger condition requires shadcn
  plus TanStack headless to have been tried and *recorded as failing*. Task 4 is the trying. Until
  it produces a recorded failure, reaching for MUI would be answering a question nobody has asked.
- **3D anything.** Occlusion makes "here is every affected call site" unprovable, which is the one
  claim such a view would exist to make. The libraries stay installed by the owner's decision; that
  is not a use. `web/src/components/3d/README.md` carries the full argument.
- **A draggable dashboard.** Its three conditions are unmet and there is nowhere to persist a
  layout that survives the browser. A feature that quietly forgets is worse than a fixed layout.
- **The abandonment vocabulary in the console.** `AbandonCode` and `classify` have not landed in
  `sync.remediate` — verified by grep, not assumed. Building a renderer against a vocabulary that
  may still be amended is a day spent twice.
- **A write path, or authentication.** Both are slices with their own design. Pretending otherwise
  with a token check would be security theatre in the codebase whose whole claim is honesty.
- **An SPA history fallback.** Nothing serves `web/dist`, so the fix would configure a server that
  does not exist.
- **A `repository` table.** `GraphStore.apply_schema` cannot rename, retype, constrain or backfill,
  and a new entity table is a real migration. `SELECT DISTINCT repo_id` still gets most of the
  value, and the screens already state its limit.
- **Backfilling anything.** A guessed value and a measured one in the same column cannot be told
  apart afterwards.
- **Restyling ahead of the structure.** The console's problem is not that its cards are plain. It
  is that four of an operator's seven questions cannot be reached, one screen fetches ten thousand
  rows at once, and the index answers the wrong question. A polish pass over that is a nicer-looking
  version of the same complaint.

---

## The parallel partition

The top three tasks are built by three agents immediately, and their file sets are disjoint. Task 0
runs first — ten minutes, mechanical — so nobody waits on anybody's first commit.

| Task | Exclusive file set |
|---|---|
| **1 — Navigation** | `web/src/lib/routes.ts`, `web/src/layouts/site-nav.tsx`, `web/src/layouts/command-palette.tsx`, `web/src/layouts/app-shell.tsx`, `web/src/App.tsx` |
| **2 — Lead screen** | `web/src/features/fleet/**`, `web/src/features/repositories/**` |
| **3 — Scale** | `src/sync/graph/store.py`, `src/sync/dashboard/graph_views.py`, `src/sync/dashboard/fleet.py`, `src/sync/api/app.py`, `src/sync/api/__main__.py`, `tests/test_graph_store.py`, `tests/test_dashboard_graph_views.py`, `tests/test_dashboard_fleet.py`, `tests/test_api_routes.py` |

Three sets, three directories, no overlap. Task 1 does not enter `features/`; Task 2 does not enter
`layouts/`, `lib/` or `api/`; Task 3 does not enter `web/` at all. `components/ui/` belongs to Task
0 and is read-only afterwards. `scripts/seed_console.py` and `tests/test_seed_console.py` belong to
another session entirely and are off limits to all three.

One overlap was found and removed rather than tolerated: the repository-row link belongs
geographically to Task 1's concern and lives in a file Task 2 owns, so it moved to Task 2 (Task 1
step 6, Task 2 step 5). Two agents in one file is how a morning is lost, and a one-line exception
is still two agents in one file.

Tasks 4 through 8 are sequential after these three, and Task 6 in particular must not run in
parallel with anything that edits a feature directory.

---

## Verification

- **Python:** `uv run pytest`, `uv run lint-imports`,
  `uv run python scripts/lint_encoding.py src scripts tests`,
  `uv run python scripts/lint_test_skips.py tests`.
- **Web:** `npm run build` clean, `npm run lint` with no new error-level violations, and from Task
  5 onward `npm test` green.
- **Reachability, which is this plan's headline claim:** from `/`, reach all eleven routes using
  only the keyboard and the mouse. Recorded with how many interactions each took.
- **Scale, at `--scale 10000`:** time to first paint, DOM node count and payload size, before and
  after, for every table Task 4 touches.
- **The protected sentences survive:** diff the rendered text of every screen before and after the
  slice. The set of qualifications must be identical or larger, never smaller.
- **No new claim is unsupported:** every filter states what it excluded, every count states its
  denominator, every collapsed section states its cardinality, every figure states its scope.
- **Nothing is chromatic that the data does not license:** disable colour and confirm every screen
  reads.
- **A full walk of every route, in both themes, leaves the browser console empty.**
- **The read-only guarantee is proven able to fail** on the new parameters specifically: add a
  write to one handler, watch `test_no_route_reaches_past_the_read_surface` go red, revert.

### Where I could not verify

- **I did not run the console or query a database in this worktree.** Every claim about what a
  screen renders is read from its source at the line cited; every claim about scale is arithmetic
  over the rendered structure, not a measurement. Task 3 and Task 4 are where those become
  measurements, which is why both carry a numbers-in-the-commit requirement.
- **`--scale N` on `scripts/seed_console.py` is assumed to exist**, since another session was
  adding it as this was written. If its shape differs, the three named values are the requirement
  and the flag's spelling is not.
- **The bundle cost of `@tanstack/react-table` and `@tanstack/react-virtual`** is asserted as small
  from their headless design, not measured. Task 4 step 1 measures it, and a surprise there is a
  reason to stop rather than to proceed.
- **Whether `npx shadcn add` adds a runtime dependency** for any of the seven primitives. Task 0
  step 2 checks it rather than assuming, because a "zero new dependencies" claim is exactly the
  kind that is worth one command to confirm.

---

## Open questions

Under `.claude/rules/autonomous-development.md` none of these blocks execution, and each is
recorded here so an agent arriving cold reads a question rather than invents an answer.

1. **What is the cardinality threshold on the lead screen?** Decision 2 requires one; nothing in
   the data suggests a value. The implementing agent picks one, states its reasoning in a comment,
   and Task 5 pins it. **Ruling if nobody objects: twenty rows** — enough that a small deployment
   never sees a count, few enough that no panel becomes a log.
2. **Does `/codebase` survive as its own route** once the lead screen carries the vendor
   distribution, or does it fold in entirely? Task 2 step 6 keeps it, on the grounds that it holds
   per-vendor detail the summary does not. Revisit after it is on screen.
3. **Should the reachability guard be a Python test or a Vitest test?** It is specified as Vitest
   in Task 5 because the runner will exist by then. The Python form — parsing `App.tsx` and
   `routes.ts`, in the shape of `tests/test_api_routes.py:440-460` — is cheaper and needs no
   runner. If Task 5 slips, move the guard to Python rather than losing it.
4. **Is a search route in the view model worth a slice?** The command palette's route-only scope is
   defensible, and an operator who knows a finding id currently has to type a URL. The question is
   whether entity search is one route with a `LIKE` or a relevance problem, and that depends on
   whether it must span findings, call sites and vendor operations at once.
5. **Does `GraphSurface` gain a by-id finding read?** This is the one question here that is genuinely
   the owner's, because the surface is frozen. `GET /api/findings/{id}` scans `whats_at_risk` up to
   `_SCAN_LIMIT = 10_000` (`app.py:59, 165`) and its own docstring says a deployment past that limit
   adds a by-id read to the surface rather than raising the ceiling. Past ten thousand open findings
   a finding becomes unreachable by its own identifier, which is the identifier the runs table links
   with. The cost was never the method; it is that a frozen surface changed once changes again —
   the same reasoning that kept `repo_id` off `whats_at_risk`. Raising `_SCAN_LIMIT` is the wrong
   answer and is named here so nobody reaches for it.

---

# Amendment, 2026-08-05 — the surface, measured against a reference and against itself

The owner's verdict on the console as it stands is that it "still looks bad, unorganized and
confusing", and their target is a surface that feels like "a sophisticated, super advanced
spaceship, an F1 race car" — engaged and immersed, not "basic dashboards with information".

An interface reference was studied to answer *why a dense surface can feel engineered rather than
busy*. `.claude/rules/interface-originality.md` binds, so what follows carries **numbers and
mechanisms, never a layout, a palette, a component or a phrase**. Every recommendation below is
justified from the operator, the graph or the product position, and any that needed the reference to
survive was cut — the cuts are listed at the end.

Two things about the F1 framing, because they decide the shape of this amendment. An F1 cockpit is
**dense with instrumentation and every instrument is legible at speed**, which is the opposite of a
sparse dashboard and equally the opposite of a decorated one. And an F1 car has **no fake gauges**:
every dial reads a real sensor. The second of those is this console's honesty discipline restated in
somebody else's vocabulary, which is why the metaphor and the constraints agree rather than
conflict. Where they do not agree is named honestly in *The one real tension* below.

## 1. What was measured on the reference

Measured in a real browser at 1440×900 through `getComputedStyle` over all 2,700 elements, not read
from markup. Numbers, not impressions.

**Surface and colour.** One plane, `rgb(0,0,0)`. **Zero elements in the document declare a border.**
Depth is carried entirely by translucent white layers at five alpha steps — 0.02, 0.05, 0.1 (458
elements), 0.2, 0.3. Six distinct text colours exist and two are artifacts; the working set is white
(104 elements), white at 0.7 alpha (106), white at 0.5 (2), and a single accent used three times as
text and nine times as a fill. **Two ink levels and one accent, for a whole page.**

**Type.** Ten sizes present, six doing real work: 12px (50 elements), 14 (23), 16 (102), 20 (24), 24
(6), and a display tier at 40/48/56 (18 combined). Range ratio **56/12 = 4.67:1**.

**Weight does almost nothing.** Two values exist in the entire document: 400 (141 elements) and 500
(93). There is no 600 and no 700 anywhere. Hierarchy is carried by size, by ink level, and by
tracking — not by weight.

**Tracking is a mechanism, and its sign flips.** Every size at 13px and above carries a uniform
**−0.02em**: −1.12px at 56, −0.96 at 48, −0.8 at 40, −0.48 at 24, −0.4 at 20, −0.36 at 18, −0.32 at
16, −0.28 at 14. The 12px step instead carries **+0.1em** (1.2px), and every element on that step is
uppercase. So the smallest step is treated as a different job from the rest of the ramp rather than
as the bottom of it.

**Leading loosens as size falls.** 1.2 at display (67.2/56, 57.6/48), 1.3 at 40 and 16 (52, 20.8),
1.4 at 20, 14 and 12 (28, 19.6, 16.8), 1.6 at 18.

**Space, and the ratio that matters more than the values.** Base 4. Inside a component: 4, 8, 12,
16, 24 — with 24 dominant (140 padding declarations) and 16 next (65). Between blocks: 32, 40, 64.
Between sections: **80px, top and bottom, on every section**. Page frame: **160px** — the hero's top
padding, and also the side gutter, since the 1105px content column inside a 1425px viewport leaves
320 = 2 × 160. The three levels stand at **160 : 80 : 24, a ratio of 6.7 : 3.3 : 1**. Prose blocks
are held to 460–553px while the content column is 1105.

**Controls.** Buttons are 138 × 36 with `0 16px` padding and **radius 0**. Their label is the 12px
uppercase +0.1em step. Primary and secondary have identical geometry and type and differ **only by
fill**. Elsewhere, 81 elements are fully pilled and six large panels take a 40px radius.

**Motion, which is the most useful measurement of the lot.** The entire stylesheet declares **two
transitions — `color 0.15s` and `opacity 0.4s ease-out` — and one keyframe, a loading spinner.**
At rest, no element on the page has a running transition or animation. Scroll reveal is staged
through 59 elements held at inline `opacity: 0`, resolved by that single 400ms opacity transition;
458 elements carry inline transforms and 91 declare `will-change`.

And the finding that decides our motion budget, measured by hovering the primary call to action with
a real pointer and reading its computed style while `:hover` matched: **background unchanged,
transform `none`, opacity unchanged, `transition-duration: 0s`.** The entire hover affordance on the
page's primary action is `cursor: pointer`. The only hover rules in the stylesheet are the
framework's boilerplate link colours and a form-input clear button.

**Hierarchy in the first screenful**, by y-position: navigation at 49 (14px / 500 / white 0.7);
headline at 160 (56px / 500 / −0.02em / solid white); supporting sentence at 318 (20px / 400 / white
0.7); action at 416 (12px / uppercase / +0.1em / on the accent fill); reassurance row at 509 (14px /
white 0.7). The eye is directed by **a 2.8× size step from first to second, and by a drop to the
smallest step for the action** — the thing you are meant to click is the smallest text in the
composition and wins on fill and tracking instead.

## 2. The gap against our console, per item, with file and line

Measured on `m4-dashboard` at `94c274d`, which is well past this plan's original baseline: 7,262
lines, 20 `<Card>`, 18 `<Table>`, 8 `<Button>`, 8 `onClick`. Each candidate defect named in the
brief was checked rather than assumed, and one of them is rejected.

**CONFIRMED — everything renders at one visual weight, so nothing leads.** Across `features/`,
`layouts/` and `components/` there are 184 type-step declarations: `text-body` 79 and `text-meta` 65,
which is **78% of all rendered type sitting on the two smallest steps**. Above them: `text-emphasis`
14, `text-page` 8, `text-section` 3, and **`text-figure` exactly once in the whole console**. A
further 14 declarations are on Tailwind stock steps (`text-sm` 11, `text-xs` 2, `text-lg` 1) that
`DESIGN.md` says are not the scale. So the declared range of 12→32 (2.67:1) is not the experienced
range: most screens run 12→24, a ratio of **2.0:1**, which is exactly the failing threshold recorded
at `docs/superpowers/references/notes/impeccable-interface-quality.md:386`. The top of the ramp is
declared and not spent.

**CONFIRMED — cards are the default container rather than a grouping.** `features/fleet/fleet-page.tsx:42-47`
stacks six sibling `<Card>` components in one `flex flex-col gap-6`. Identical container, identical
`shadow-flat` ring, identical full width, one gap between them, no ordering by what the operator came
for. Twenty `<Card>` sites across the tree and thirteen of the files holding one wrap a single table
in it. Because every surface takes the same hairline ring, the ring — which `DESIGN.md` defines as
*the* elevation mechanism — encodes nothing.

**CONFIRMED — there is no rhythm, because the token layer is not governing.** `DESIGN.md` declares
three spacing tokens. Across `features/`, `layouts/` and `components/` those tokens are spelled **19
times** against **128 raw Tailwind spacing declarations**, and the two overlap on the same values:
`gap-1` (9 uses) and `gap-field` (6) are both 4px; `p-4` (4) and `p-section` (2) are both 16px;
`px-2` (6) and `px-row` (5) are both 8px. The tokens carry roughly **13%** of the spacing decisions
they exist to own, so a change to the rhythm cannot be made in one place — which is the only reason
to have them.

**CONFIRMED, and this is the sharpest number — the page has one spacing level where it needs three.**
Page gutter `px-6` = 24px (`layouts/app-shell.tsx:46`). Between-panel gap `gap-6` = 24px
(`features/fleet/fleet-page.tsx:30`). In-panel gap `gap-4` = 16px
(`features/fleet/screen-limits.tsx:52`). Field gap `gap-1` = 4px (`screen-limits.tsx:54`). So the
frame and the section gap are **the same value**, and the whole page runs at **24 : 24 : 16 : 4 —
a ratio of 1.5 : 1.5 : 1** between its outer three levels. The reference's equivalent three levels
stand at 6.7 : 3.3 : 1. Our largest spacing value is 1.5× our most common one. That is what "no
rhythm" means when it is measured.

**CONFIRMED — density is low while the data is dense.** `lg:grid-cols-4` appears **once** in
`features/` and `layouts/` combined. Every screen is a single column of full-width cards. At 1440px
a four-cell summary panel and a nine-column evidence table both occupy the same 1392px, and the lead
screen is six panels tall, so an operator answering "what do I act on today" scrolls past four
panels to reach one. `DESIGN.md`'s own currency argument — every unit of vertical space is a row that
fell off the viewport — is the argument against this, and nothing in the tree acts on it.

**CONFIRMED, smaller — the radius token is not true.** In `components/ui/` there are 10 Tailwind-stock
radius declarations (`rounded-lg` 5, `rounded-t-xl` 2, `rounded-b-xl` 2, `rounded-xl` 1) against 13
token ones. `Card`, the console's most-used container, renders `rounded-xl` = 12px at
`components/ui/card.tsx:16`, where `DESIGN.md` declares `--radius-surface` = 10px for exactly that
job and states that everything resolves to one of two values. Task 0's own verification grep was
written to catch this and the value is present.

**REJECTED — "nothing responds to the pointer, so the surface feels inert."** Not true as stated.
`components/ui/table.tsx:58` gives every row `transition-colors hover:bg-muted/50`, so the densest
and most-clicked surface in the console does respond. What is true is narrower and worth keeping:
there are 21 hover, focus and transition declarations in the tree and 15 of them are inside
`components/ui/`; across the eight feature screens exactly **one** is authored by hand
(`features/workflows/node-sequence.tsx`). The interaction the console has is inherited from its
primitives rather than designed, which is a different defect and a much cheaper one.

**And one thing the console already got right, recorded because the fix should generalise it rather
than replace it.** `layouts/site-nav.tsx:65` renders its graph-level labels as
`text-meta tracking-wide uppercase text-muted-foreground` — the same treatment of the smallest step
that the reference applies to every one of its 12px elements, arrived at here independently, from the
same problem. It exists in one file and nowhere else. Separately, the console's 112 `font-mono`
declarations are carrying a semantic distinction the reference has no equivalent of — mono means the
system recorded this verbatim — and that is a genuine advantage to protect, not a density problem.

## 3. The direction

Four moves. None adds a token, an elevation level, a spacing value or a seventh type step; each
spends something `DESIGN.md` has already declared and validated.

**Spend the type range instead of declaring it.** The console's hierarchy *is* the API Dependency
Graph, six levels deep, and an operator arriving on a screen must know which level they are on before
reading a word. Today 78% of type sits on two adjacent steps and the top step is used once, so the
graph's depth is invisible in the rendering of it. The fix is a usage rule, not a new value: **every
screen renders at least four of the six steps, and the figure step stops being ornamental** — a
count an operator acts on is a figure, and there are several on the lead screen currently rendered
as body text. This is justified from the graph: the levels are real, they are stored, and the type
ramp is the only channel that can show depth without asserting a judgement.

**Make tracking part of the step at the display end, and a class at the small end.** `DESIGN.md`
declares letter-spacing on two of six steps and nothing else, while `site-nav.tsx:65` reaches for it
by hand. `DESIGN.md`'s own test decides where each belongs: *if two agents building two screens could
reasonably choose differently and the difference would be visible, it is a token; if they could not,
it is a class.* Two agents setting a section heading could choose differently, so tracking travels
with `--text-section` and `--text-emphasis` as it already does with `--text-page` and `--text-figure`.
Two agents rendering a graph-level label would both reach for uppercase and open tracking, so the
furniture treatment is **one class**, defined once, replacing the ad-hoc pair in `site-nav.tsx`.
Justified from the operator: the 12px step carries what is scanned rather than read — level names,
column headers, rung labels, timestamps — and open tracking on short uppercase runs is legibility at
speed, which is the whole of what the F1 framing actually asks for.

**Let grouping ride the surface ramp we already validated, and give the ring back its job.** The dark
column already holds four surface steps — `surface-sunken` 0.155, `surface` 0.205, `surface-subtle`
0.255, `surface-emphasis` 0.305 — with every ink pairing on them computed and clearing the 5.05
floor by a wide margin (`ink` on surface 15.73, on subtle 13.79, on emphasis 11.75). That is enough
to separate a panel from the page and a header from a body without drawing a box around each of
twenty cards. So a surface's step, not its ring, says what kind of thing it is; the ring is kept for
a surface that must be told apart from a neighbour at the same step. This adds no elevation level —
`DESIGN.md` still has exactly two, and only `ErrorSurface` floats. The reference's demonstration that
2,700 elements can be organised with zero borders is what prompted checking whether ours were doing
work; the argument for the change is that ours measurably are not.

**Use the width, because vertical space is the currency and we are spending it on air.** Panels that
are *summaries* pair two-up at the viewport's width; panels that are *evidence tables* stay full
width, which `app-shell.tsx:23-28` already argues for correctly. On the lead screen this alone takes
six full-width panels to roughly three rows without hiding anything — density gained by layout rather
than by disclosure, which is the only kind this plan's Decision 3 permits without a qualification
audit. And separate the page frame from the between-panel gap so the two stop being the same number;
the goal is a distinguishable step between nesting levels, **not the reference's magnitudes**, which
would cost rows and which `DESIGN.md` explicitly refuses.

**One thing that must get louder rather than quieter, and it follows from the constraints rather than
from taste.** `features/fleet/screen-limits.tsx:42-63` renders the console's product position — what
this screen cannot tell you — in a `<Card>` identical to the five figure panels beside it, which
satisfies Task 2 step 3's requirement that it sit "at the same visual weight as the figures". That
requirement was written to stop it becoming a footnote. In a console whose figures are about to get
larger and whose panels are about to be ranked, *same weight* read literally makes it the quietest
thing on screen by contrast. The honest reading is **same tier**, and every task below re-verifies it
after the hierarchy moves. A denser console must be more legible about what it cannot prove, not
less, and this is the specific place that fails first.

## 4. Tasks

Ranked. Rank 11 stays the layered bipartite diagram, which still loses, so these begin at 12.

### Task 12: The system layer — the type range, tracking, and the surface ramp's grouping job

> **Steps 1, 2 and 3 are revised by section 11.** Step 3's stated premise is false; read section 11
> before writing anything into `DESIGN.md`.

**Files:** `DESIGN.md`, `web/src/index.css`. **~half a day.**

**Not parallel.** Both files are held by the session removing the light column for dark-mode-only.
This task starts after that lands and takes both files whole; there is no way to split them, and two
agents in `index.css` is a lost morning.

- [ ] **Step 1:** Add letter-spacing to `--text-section` and `--text-emphasis` on the pattern
  `--text-page` and `--text-figure` already set, and record both in `DESIGN.md`'s Type table with the
  reasoning. **No seventh step, no changed size, no changed weight.**
- [ ] **Step 2:** Define the furniture class once, in `@layer components` — the uppercase, open-tracked
  treatment of `--text-meta` that `site-nav.tsx:65` currently spells by hand. `DESIGN.md` gains a
  short section saying which of the smallest step's two jobs it covers and which it does not: a
  scanned label takes it, a timestamp does not.
- [ ] **Step 3:** State the surface ramp's grouping contract in `DESIGN.md` — which step a page, a
  panel, a panel header and a selected row take in dark mode, and that the ring is no longer applied
  to every surface by default. Cite the contrast figures already computed rather than recomputing
  them; none of these pairings is new.
- [ ] **Step 4:** Record the spacing ruling: the three tokens are the only spelling permitted inside
  `features/`, and the page-frame value stays unnamed on Tailwind's base scale as
  `DESIGN.md` already decided. **No fourth spacing token.**
- [ ] **Step 5:** The honesty audit. Nothing in this task may make colour, motion or depth carry a
  claim. Confirm the three channels licensed to assert — run outcome, error state, absence — are
  unchanged, and that the provenance rung is still monochrome.
- [ ] **Step 6:** `npm run build` clean. Commit.

**Verification a reviewer can run:** `grep -c "text-" web/src/index.css` still shows six steps.
Then re-read `DESIGN.md`'s "Deliberately absent" list and confirm every item is still absent. Then
set `--text-section`'s tracking to a deliberately wrong value, load a screen, see it, and revert —
a token nothing reads is a token that is not wired.

### Task 13: The primitives carry the grouping, and the radius token becomes true

> **Steps 1 and 3 are revised by section 11.** Step 3 in particular: the table keeps its header rule.

**Files:** `web/src/components/ui/card.tsx`, `web/src/components/ui/table.tsx`,
`web/src/components/provenance.tsx`. **~half a day. Follows Task 12.**

**Exclusive.** Touches nothing under `features/`, `layouts/` or `lib/`.

- [ ] **Step 1:** `Card` takes its surface step and its radius from the tokens: `rounded-xl` at
  `card.tsx:16` and the four `rounded-t-xl`/`rounded-b-xl` variants become `--radius-surface`. This
  is a 2px change and it is the difference between a token layer that governs and one that describes.
- [ ] **Step 2:** `Card` gains a variant expressing whether it is a grouping or a plain surface,
  carried by the surface step rather than by an added elevation level. **The default stops being
  ring-on-everything.**
- [ ] **Step 3:** `TableHeader` sits on `surface-subtle` so a dense table reads as header-then-body
  without a rule. **Leave `TableRow`'s `hover:bg-muted/50` and `transition-colors` at `table.tsx:58`
  exactly as they are** — that is the one interaction in the console that was already right.
- [ ] **Step 4:** `RungBadge` adopts the furniture class from Task 12 and **stays monochrome**. If
  this step ends with a hue anywhere near the rung, it is wrong.
- [ ] **Step 5:** The honesty audit. A surface step now distinguishes a grouping from a plain panel —
  confirm that distinction is structural and never a judgement, and that no reader could take a
  lighter surface for a better result.
- [ ] **Step 6:** `npm run build` clean, `npm run lint` no new error-level violations. Commit.

**Verification a reviewer can run:**
`grep -rnE "rounded-(lg|xl|t-xl|b-xl)" web/src/components/ui/` returns nothing. Then open any screen
with the theme's surface tokens temporarily collapsed to one value and confirm the page becomes
illegible as *grouping* while remaining legible as *text* — which proves the grouping is carried by
surface and not by the ring that is still there.

### Task 14: The lead screen uses its width and ranks its panels

> **Step 1 is revised by section 11**, which replaces "one step" with a measured target.

**Files:** `web/src/features/fleet/**`, `web/src/layouts/app-shell.tsx`. **~1 day. Follows Task 13.
Parallel with Task 15.**

- [ ] **Step 1:** Separate the page frame from the between-panel gap in `app-shell.tsx:46` so the two
  stop being 24px each. One step, not the reference's three.
- [ ] **Step 2:** Rank the six panels at `fleet-page.tsx:42-47` by the operator's first question and
  pair the summary panels two-up. Evidence tables keep the full width.
- [ ] **Step 3:** The figures an operator acts on take `--text-figure`, which is currently used once
  in the console. Every figure keeps the sentence naming its scope **at the same tier**, which after
  this change means a larger step than body, not the same one.
- [ ] **Step 4:** `ScreenLimitsCard` is re-checked against the new hierarchy and lifted to whatever
  tier keeps it level with the figures. **It is not moved below the fold, not collapsed, and not
  shortened.**
- [ ] **Step 5:** Every spacing declaration in these files uses a token spelling.
- [ ] **Step 6:** The honesty audit, and it is the one that matters most here. A ranked screen asserts
  that the top panel is the most important; confirm the ranking follows the operator's question and
  not the panel's size. A two-up pairing asserts the two are comparable; confirm they are. And diff
  the rendered text before and after — **the protected sentences at `fleet-page.tsx:15-17`,
  `runs-table.tsx`, `corpus-summary.tsx` and `repositories-table.tsx` must be present at full
  length**.
- [ ] **Step 7:** `npm run build` clean, `npm run lint` no new error-level violations. Commit.

**Verification a reviewer can run:** load `/` at 1440×900 and count how many panels are visible
before scrolling, before and after. Then read the screen asking *"what would I wrongly believe if I
only read the largest things?"* and confirm the answer is nothing. Then diff the visible text against
the previous commit; the set of qualifications must be identical or larger.

### Task 15: The remaining screens adopt the ranked hierarchy

> **Step 1 gains a companion constraint from section 11:** prose is never set to the column's full
> width, and that binds hardest on the protected sentences.

**Files:** `web/src/features/{bindings,telemetry,vendors,repositories,detectors,findings,workflows}/**`.
**~1 day. Follows Task 13. Parallel with Task 14.**

- [ ] **Step 1:** Each screen renders at least four of the six type steps, with its `h1` on
  `--text-page` and its scanned furniture on the Task 12 class.
- [ ] **Step 2:** Panels that are summaries pair or grid; panels that are evidence tables keep the
  full width.
- [ ] **Step 3:** Every spacing declaration in these files uses a token spelling. This is the bulk of
  the 128 raw declarations and it is mechanical.
- [ ] **Step 4:** The honesty audit, per screen: every "cannot tell the two apart" sentence, every
  denominator caption, every absence marker and every per-row rung is still on screen at full length
  and not behind a disclosure.
- [ ] **Step 5:** `npm run build` clean, `npm run lint` no new error-level violations. Commit.

**Verification a reviewer can run:** walk all routes at 1440×900 and confirm each one's headline
question is answered above the fold with no horizontal scroll — Decision 8's check, now applied per
screen. Then grep the diff for a removed sentence.

### Task 16: The guard that holds the token layer

> **Section 11 adds a fourth assertion**, guarding the motion finding. It is proved to fail like the
> other three.

**Files:** `tests/test_console_design_tokens.py`. **~2 hours. Follows Task 15.**

Python rather than Vitest, for Task 10's stated reason and under open question 3: this is an
assertion over source text, it needs no DOM and no runner, and Vitest does not exist in the tree yet
(`web/package.json` has no `test` script). Same shape as `tests/test_api_routes.py:440-460`.

- [ ] **Step 1:** Assert no file under `web/src/features/` spells a raw Tailwind spacing step where a
  `DESIGN.md` token holds the same value. The failure message names the file, the line and the token
  to use. `encoding="utf-8"` on every read.
- [ ] **Step 2:** Assert no file under `web/src/` declares a radius outside the two tokens, and none
  declares a type step outside the six.
- [ ] **Step 3:** Assert nothing renders below `--text-meta` — no `text-[10px]`, no `text-[11px]`,
  covering the standing temptation `DESIGN.md` names by hand.
- [ ] **Step 4:** **Prove it can fail, three times** — once per assertion. Introduce the violation,
  watch it go red for the reason expected, revert. A guard that has never rejected anything has not
  been shown to guard.
- [ ] **Step 5:** `uv run pytest tests/test_console_design_tokens.py`,
  `uv run python scripts/lint_encoding.py tests`. Commit.

**Verification a reviewer can run:** add `gap-4` to any file under `web/src/features/` and watch the
test name it and the token to replace it with. Revert.

### The parallel partition for these tasks

| Task | Exclusive file set | Runs |
|---|---|---|
| **12 — System layer** | `DESIGN.md`, `web/src/index.css` | after dark-mode-only lands; alone |
| **13 — Primitives** | `web/src/components/ui/card.tsx`, `web/src/components/ui/table.tsx`, `web/src/components/provenance.tsx` | after 12; alone |
| **14 — Lead screen** | `web/src/features/fleet/**`, `web/src/layouts/app-shell.tsx` | after 13; parallel with 15 |
| **15 — Remaining screens** | `web/src/features/{bindings,telemetry,vendors,repositories,detectors,findings,workflows}/**` | after 13; parallel with 14 |
| **16 — Token guard** | `tests/test_console_design_tokens.py` | after 15; alone |

Tasks 14 and 15 are disjoint by directory and are the only pair that runs concurrently. Tasks 12 and
13 are serialised because a token layer and the primitives reading it cannot be changed in parallel
without one of them being wrong for a commit.

## 5. What this amendment does not propose, and what decided it

The design-system plan's rejections stand and are **not reopened**: no 3D, no spatial canvas, no
draggable widgets, no composite score. Nothing below revisits them.

- **No score, health figure, traffic light, green dot or liveness pulse.** Rejected three times on
  the record and rendered as a refusal on screen at `fleet-page.tsx:15-17` and
  `runs-table.tsx:159-168` — that sentence has moved since *Establish 2* cited it at `:114-123`, and
  the citation here is the one checked against the tree at `94c274d`.
  A denser, more immersive console is the single most likely place for one to reappear, in the
  specific form of a "system status" indicator that a spaceship metaphor invites. There is no
  heartbeat in the data. There is no dot.
- **No new motion, and this is now a measurement rather than a preference.** The reference's entire
  stylesheet declares two transitions and its primary action does nothing at all on hover. Whatever
  produces the feel the owner is describing, it is demonstrably not motion. Decision 8 already said
  immersion is the absence of decisions the reader has to make; this is the evidence for it.
- **Not the reference's spacing magnitudes.** 80px between sections and a 160px page frame would cost
  rows on every screen, and `DESIGN.md` is explicit that whitespace is what is being spent. The
  **ratio between nesting levels** is the mechanism that transfers; the values are theirs and would be
  wrong here.
- **Not a single-plane, borderless surface.** It works on a marketing page with 24 elements per
  screenful. Our screens are evidence tables with hundreds of cells, and a table needs a header rule.
  We keep both channels and stop spending only one of them.
- **Not two font weights.** The reference reaches 4.67:1 of type range with only 400 and 500, which is
  elegant and is not available to us: our range is 2.67:1 by deliberate decision, since rows per
  screen is the currency, and at that range weight is doing necessary work that size cannot.
- **Not a backdrop blur, a translucent nav, or any decorative layer.** The reference carries a blurred
  nav and named decorative elements. Each is depth or motion asserting something the data does not
  hold, which `DESIGN.md`'s first rule forbids outright.
- **Not a radius of 0 on controls, and not pills.** Both are appearance with no argument from the
  operator behind them. `--radius-control` and `--radius-surface` already exist and Task 13's job is
  to make them true, not to change them.
- **Not a new accent colour or a second chromatic channel.** The reference runs on two ink levels and
  one accent. We already run on a nine-step neutral ramp with the brand hue reserved for links, focus
  and the current node, which is a stricter version of the same discipline arrived at independently.
- **No column of the honesty sentences is shortened, collapsed, moved into a tooltip or restyled into
  quietness.** The twenty-four protected sentences in *Establish 2* are restyled at most. Task 14 step
  6 and Task 15 step 4 both diff the rendered text, and a reworded qualification is a changed claim.

## 6. The one real tension, stated plainly

The F1 framing and this console's honesty discipline agree on three of four axes, and the agreement
is not a rhetorical convenience.

**Density agrees.** A cockpit shows everything at once; Decision 3 already forbids hiding a
qualification behind a click. Density and honesty pull the same direction here, which is unusual and
worth saying out loud.

**Legibility at speed agrees, and is the actual defect.** Every measurement in section 2 is a
legibility failure, not a decoration failure. 78% of type on two steps, one grid in the tree, a page
frame equal to a panel gap — an instrument panel where every dial is the same size is not dense, it
is unreadable.

**No fake gauges agrees exactly.** This is the console's whole position in somebody else's words.

**Immersion is where it conflicts, and the conflict is real.** The felt quality of a spaceship
interface, as the phrase is normally meant, comes from decoration that asserts activity — a sweep, a
pulse, a live readout, a counter that moves. Every one of those is a claim about time or liveness,
and this console has already ruled, three times and on screen, that it cannot make that claim:
`runs-table.tsx:159-168` refuses a liveness dot because nothing in the data distinguishes a run
parked on the customer's CI from one that has died. **So the animated, alive-looking register of the
metaphor is permanently unavailable here, and no amount of design will recover it.**

The honest resolution, and the reason this is a tension rather than a contradiction: the reference
was measured precisely to test whether that register is where the feeling comes from, and it is not.
A page with two transitions in its entire stylesheet and a primary button that does nothing on hover
reads as engineered because of typographic range, tracking discipline, a spacing ratio of nearly 7:1
across three nesting levels, and a colour system of two inks and one accent. **All four of those are
available to this console at zero cost to its honesty**, and all four are what section 3 proposes.

What the owner should know is the limit: this will make the console feel considered, deliberate and
fast to read. It will not make it feel *alive*, because being alive is a claim, and this product's
entire position is that it does not make claims it cannot support. That is the trade, it was decided
before this amendment, and it is the right one.

## 7. Added 2026-08-05 — two more references, and what three of them agree about

Sections 1 through 6 rest on one interface. One designer's page cannot tell you which of its
properties are principles and which are habits, so two more were measured by the same method and the
first was re-measured to check its own numbers. What follows names the three, reports both new
measurement sets, and then separates what all three do from what only one does.

`.claude/rules/interface-originality.md` binds here exactly as it binds above. Nothing below is a
layout, a component, a colour system or a phrase. Every recommendation is restated as a problem
from the operator, the graph or the product position, and where a finding survived only because a
reference did it, that is said out loud and the finding is demoted.

**The three, and how each was read.** Chrome at 1440×900, `getComputedStyle` across every element in
the document, plus a real pointer moved onto the primary call to action so `:hover` genuinely
matched. No markup was fetched or read for design content.

| | Reference A | Reference B | Reference C |
|---|---|---|---|
| Host | `early-list-690354.framer.app` | `newcomer-community-603717.framer.app` | `likely-discipline-565331.framer.app` |
| Elements | 2,708 | 1,311 | 2,103 |
| Text-bearing elements | 235 | 217 | 249 |
| Page surface | dark | dark | **light** |
| Studied in | section 1 | this section | this section |

Reference C is a light page. The owner has asked for dark mode only, so its colour values are not
transferable and are not proposed; its *structure* — how many ink levels, how they are separated, how
grouping is carried — is, and that is all that is taken from it.

### Reference B, measured

**Type.** Eight sizes present, seven doing real work: 14px (85 elements), 16 (82), 12 (11), 38 (10),
18 (9), 32 (9), 48 (8), 24 (3). Nine of the eleven 12px elements are browser defaults rather than
authored type — black ink, normal tracking, normal leading, one of them the default link blue — so
the authored ramp runs 14 to 48, a range of **3.43:1**. Counting the 12px step as present gives
4.0:1. Two-thirds of all rendered type sits on 14 and 16.

**Weight.** 400 on 164 elements, 500 on 52, and a single stray 700. **No 600 anywhere.**

**Tracking is two-tier, and the tier is chosen by role rather than by size.** Body copy takes
−0.02em: 14px at −0.28px, 16px at −0.32px. Everything acting as a heading takes **−0.04em**,
including 16px when it is a heading — 26 elements sit at 16px/500/−0.04em while 48 elements sit at
16px/400/−0.02em. Above that the −0.04em is uniform: 18 at −0.72px, 24 at −0.96, 32 at −1.28, 38 at
−1.52, 48 at −1.92. So the same size carries different tracking depending on the job it is doing.

**There is no uppercase anywhere in the document.** `text-transform` is `none` on all 217
text-bearing elements, and the smallest authored step carries negative tracking like every other.

**Leading is two-tier to match.** 1.5 on body (21px at 14, 24px at 16), 1.1 on everything heading and
above (19.8 at 18, 26.4 at 24, 35.2 at 32, 41.8 at 38, 52.8 at 48).

**Ink.** White at 0.8 alpha on 118 elements, solid white on 65, white at 0.7 on 5. On the inverted
panels, near-black on light. **Two working ink levels.** Backgrounds are opaque steps rather than
alpha layers: rgb(19,21,23) on 74 elements, rgb(35,35,38) on 22, over a page of rgb(8,10,9). Nine
further chromatic fills exist, each used once to four times — small chips, not a second channel.

**Lines.** **Zero elements declare a border.** But fourteen elements are 1–2px filled divs doing a
line's job: nine horizontal rules at 285×1 and 301×1 in rgb(35,35,38), and five 2×16 vertical
markers, one of them in an accent hue. The page is not ruleless. It draws rules without the `border`
property.

**Space.** Base 4. In-component padding: 20 (41 declarations), 32 (38), 24 (28), 8 (24), 12 (22), 16
(16), 18 (16), 4 (10). Gaps: 8 (90), 12 (72), 16 (58), 24 (44), 32 (24), 64 (22). Section vertical
padding is **72px, top and bottom, on seventeen sections**. The content column is 1080 inside a 1425
viewport, so the page frame is **173px** a side. The three levels stand at **173 : 72 : 24**, a ratio
of **7.2 : 3.0 : 1**. Prose is held to 285–480px while the column is 1080.

**Controls.** 124 × 33 with `8px 12px` padding and **radius 8**. Label 14px/500/−0.02em. Primary is a
white fill, secondary is rgb(35,35,38); **geometry, padding and type are identical and only the fill
differs**.

**Motion.** Two elements in the document carry a transition — `transform 0.1s` and
`opacity 0.4s ease-out`. The stylesheet declares two transition rules and both are the editor
framework's own furniture. **One keyframe exists, a loading spinner.** The document holds exactly one
Web Animation and it is paused at rest. Scroll reveal is 63 elements held at inline `opacity: 0` and
resolved by that single 400ms fade; 61 carry inline transforms and 88 declare `will-change`. A
smooth-scroll library is loaded.

**The primary action on hover, with the pointer really on it and `:hover` confirmed matching:**
background unchanged, `transform: none`, opacity unchanged, `transition-duration: 0s`. One thing does
change — a `0 0 0 2px` ring at white 0.5 appears, and it is genuinely a hover affordance rather than
a focus ring, because moving the pointer away returns it to zero alpha and zero spread. It arrives
instantly. **Nothing moves, scales or fades.**

**Hierarchy in the first screenful**, by y-position: navigation at 23 (14/400/white 0.8); eyebrow at
161 (14/400/white 0.8); headline at 206 (48/400/−0.04em/solid white); supporting sentence at 331
(16/400/−0.02em/white 0.8); actions at 427 (14/500, dark ink on a white fill). A **3.0× step** from
headline to supporting text, and the thing you are meant to click is again the smallest text in the
composition, winning on fill.

**Typeface.** One family across 200 of 217 text-bearing elements. No monospace anywhere.

### Reference C, measured

**Type, and this is where C is least disciplined.** Fourteen sizes present, twelve carrying five or
more elements: 15px (52), 12 (46), 14 (37), 16 (35), 13 (19), 20 (13), 32 (10), 54 (8), 11 (6), 26
(6), 44 (6), 18 (6), 48 (3), 64 (2). Range **64/11 = 5.82:1** — the widest of the three, reached with
twice as many steps as A. Ten of the 12px elements are browser defaults, as in B.

**Weight.** 400 on 232 elements, 500 on 17. **Two weights, and the second one is nearly unused.**

**Tracking is graduated by size, and tightens as size grows.** 15px body carries **none at all**
(`normal`). 11, 12, 13 and 14 carry −0.04em. 16 and 18 carry −0.02em. 20, 26 and 32 carry −0.03em.
44 carries −0.04em. 48, 54 and 64 carry **−0.05em**.

**There is no uppercase anywhere in this document either.** `text-transform` is `none` on all 249
text-bearing elements. Its eyebrow *reads* as capitals because the capitals are typed into the copy,
which is a worse way to get there — a screen reader spells out a word set that way, and a
`text-transform` does not.

**Leading.** 1.5 at 15px body, 1.4 at 12/13/16/18/20, 1.2 at 14/26/32, 1.09 at 44/48/54, 1.0 at 64.

**Ink.** rgb(82,82,82) on 121 elements, rgb(10,10,10) on 96, inverted rgb(250,250,250) on 8 and white
on 3. **Two working ink levels**, same as the other two, inverted for a light page.

**Lines.** Six elements declare a border, all of them `1px` on the top and left or top, bottom and
left of a 199×82 cell — a 3×2 grid, which is to say **the only borders on the page are on the one
thing that is a grid.** Separately, 576 elements are 1×4, 4×1, 1×8 or 8×1 filled divs at
rgba(10,10,10,0.2), a drawn tick lattice. Same construction as B and A: lines exist, drawn as fills.

**Space.** In-component padding: 24 (298 declarations — dominant by a wide margin), 4 (134), 12 (73),
16 (71), 32 (49), 8 (35). Gaps: 24 (172), 10 (144), 12 (108), 6 (88), 32 (64). Section vertical
padding is **64px** with a further 32px inside the column. The content column is 1200 inside 1425, so
the frame is **113px** a side. Three levels at **113 : 64 : 24**, a ratio of **4.7 : 2.7 : 1**. Prose
is held to a mode of 323px and a maximum of 588px inside a 1200px column.

**Controls.** 144 × 39 with `11px 16px` padding and **radius 0**. Label 14px/500/−0.029em. Primary is
a near-black fill, secondary a near-white one; **identical geometry and type, differing only by
fill** — the same construction as A and B, at a different radius.

**Motion.** Four elements carry a transition. The stylesheet declares three transition rules, of
which two are framework furniture and **one is authored: `color 0.3s` on a link preset**. One
keyframe exists, a loading spinner. Exactly one Web Animation runs at any moment: a 40ms width tween
on a 4px-tall div, which is a scroll-progress bar reading scroll position. Scroll reveal is 34
elements at inline `opacity: 0`. A smooth-scroll library is loaded.

**The primary action on hover, pointer really on it:** the fill goes from `rgb(10,10,10)` to
`rgba(10,10,10,0.7)`. `transform: none`, opacity unchanged, no shadow, **`transition-duration: 0s`**.
Re-read 500ms later, unchanged — the change is instant, not eased. **Nothing moves or scales.**

**Hierarchy in the first screenful**: navigation at 38 (14/400/−0.04em/secondary ink); eyebrow at 200
(11/400/−0.04em); headline at 233 (**64/400/−0.05em**/primary ink); supporting sentence at 373
(16/400/no tracking/secondary ink); actions at 454 (14/500 on fills). A **4.0× step** from headline
to supporting text.

**Typeface, and this is the finding section 1 could not have had.** Two families in near balance:
a sans on 123 text-bearing elements and a **monospace on 105**. The split is by role — monospace
carries navigation labels, button labels, eyebrows, section labels and small captions; the sans
carries body prose and the 64px headline. Monospace is used here as *furniture*, marking the scanned
register rather than the read one.

## 8. Where all three agree

Each row below was measured independently on three pages by three designers. That is the bar for
calling something a property of dense considered interfaces rather than one person's taste, and only
these rows clear it.

| Property | A | B | C | The invariant |
|---|---|---|---|---|
| Font weights | 400, 500 | 400, 500 | 400, 500 | **Two weights. No 600, no 700, in any of them.** |
| Working ink levels | white + white 0.7 | white + white 0.8 | 10,10,10 + 82,82,82 | **Two, plus one accent. Never three.** |
| Type range | 4.67:1 | 3.43:1 | 5.82:1 | **At least 3.4:1, display step at least 3× body.** |
| Display tracking | −0.02em | −0.04em | −0.05em | **Negative, and never looser than body.** |
| Leading | 1.2 display → 1.6 small | 1.1 → 1.5 | 1.0 → 1.5 | **Loosens as size falls. Display at or below 1.2.** |
| Spacing levels | 160 : 80 : 24 | 173 : 72 : 24 | 113 : 64 : 24 | **Three levels, each ≥2× the one below; frame 4.7–7.2× the in-component unit.** |
| In-component base | 4, dominant 24 | 4, dominant 20/24 | 4, dominant 24 | **Base 4, one dominant value.** |
| Prose measure | 460–553 in 1105 | 285–480 in 1080 | 267–588 in 1200 | **Prose never runs the column's width.** |
| Button pairs | identical, differ by fill | identical, differ by fill | identical, differ by fill | **Primary and secondary differ only in fill.** |
| Authored stylesheet transitions | 0 | 0 | 1 | **At most one in an entire page.** |
| `@keyframes` | 1 (spinner) | 1 (spinner) | 1 (spinner) | **One, and it is a spinner.** |
| Animations running at rest | 0 of 0 | 0 of 1 | 1 of 1, a 40ms scroll bar | **Nothing decorative is ever running.** |
| Primary action on hover | nothing changes | ring appears | fill alpha changes | **`transition-duration: 0s`, `transform: none`, no scale, no fade — in all three.** |
| Scroll reveal | inline `opacity: 0` + 0.4s | same, 63 elements | same, 34 elements | **One 400ms one-shot fade, and nothing else.** |
| Lines | 11 borders, 452 filled divs | 0 borders, 14 filled divs | 6 borders, 576 filled divs | **Rules exist and are drawn; the `border` property is not spent on containers.** |

Every one of those fourteen is available to this console at no cost to its honesty discipline, and
none of them requires a competitor's screen to justify: two ink levels because a table with three
is unreadable; two weights because weight is a channel we need for density; a display step because
the graph is six levels deep and depth has to be visible; three spacing levels because a page frame
that equals a panel gap tells the eye nothing; no motion because there is nothing in the data that
moves.

## 9. Where they diverge, which makes it taste

These are the properties on which the three references contradict each other. A property that three
careful designers resolve three different ways is not a principle, and we should decide it on our own
grounds or leave it alone.

- **Control radius.** 0 (A), 8 (B), 0 (C). Two of three at zero, and B is not the worse page for it.
  Ours stays `--radius-control`, decided by us, unchanged by this.
- **Whether the smallest step is uppercase.** A: 39 elements at 12px/+0.1em/uppercase. B and C:
  **zero uppercase elements in the entire document**, and both take negative tracking at their
  smallest step. This is the single largest divergence found and section 10 deals with it.
- **How tracking is assigned.** Uniform for all sizes (A), two-tier by role (B), graduated by size
  (C). All three tighten at the display end; nothing else about the model is shared.
- **How many type steps.** Six (A), seven (B), twelve (C). C is the least disciplined ramp and the
  widest range, and reads as considered anyway. **So the mechanism is range and consistent role
  assignment, not step count** — which matters, because our six steps are not the problem.
- **Monospace.** Absent in A and B; 46% of text in C, used as furniture. Ours is semantic. Different
  job, and section 10 says why we keep ours rather than drifting toward C's.
- **Section padding magnitude.** 80 / 72 / 64. Even among landing pages this is not a constant.
- **Whether a smooth-scroll library is loaded.** Not in A; in both B and C.
- **What the primary action does on hover.** Nothing (A), a ring (B), a fill alpha step (C). The
  *shape* of the answer is shared — instant, non-geometric — but the answer is not.

## 10. Where this contradicts section 1, and which measurement I trust

Four of section 1's findings needed revising. Three are refinements and one is wrong.

**Wrong: "Zero elements in the document declare a border."** Reference A was re-measured for this
amendment specifically because the claim was categorical, and it does not hold: **eleven elements
declare a border**, and **452 elements are 1–2px filled divs acting as lines** — 240 at 12×1 and 200
at 1×12 forming a tick lattice, six horizontal rules at 328×1, and six 2×72 vertical markers, three
of them in the accent hue. B has zero borders and fourteen line divs; C has six borders and 576 line
divs.

I trust the new measurement, and not because it is newer. It counts the same property the original
counted *and* the thing the original did not think to look for, so it can only add. The original
number was not miscounted; it was the wrong question, because a page that draws its rules as filled
divs answers "how many borders" with zero while being covered in lines.

This matters because a recommendation rests on it. Section 3 argued that the ring should stop being
applied to every surface, and cited "2,700 elements organised with zero borders" as the prompt for
checking whether ours do work. The prompt was false. **The recommendation survives on its own
evidence and needs restating on it**: our own measurement is that every surface takes the identical
hairline ring, which means the ring encodes nothing, and that is the argument. What the three
references actually demonstrate is narrower and more useful than "no borders" — **a line where
something is separated, a surface step where something is grouped, and neither applied by default.**
That rule survives translation to a table, where "no lines at all" would not.

**Refined: "Tracking flips to +0.1em and uppercase at 12px. The smallest step is a different job."**
Confirmed exactly on A — 39 elements at 12px, +0.100em, uppercase. Contradicted as a general
principle by both new references, which have **no uppercase at all** and take negative tracking on
their smallest steps.

I trust all three measurements; they are each internally consistent and there is nothing to
reconcile. The conclusion is that the uppercase micro-step is **one designer's habit**, and section 1
promoted it to a measured principle it is not. It should still be built, because there is a
Sync-side argument for it that does not point at anybody's screen — `site-nav.tsx:65` reached it
independently for graph-level labels, which are scanned rather than read, and open tracking on short
capitalised runs is legibility at speed. But it is now **our choice defended on our grounds**, not a
finding, and Task 12's brief has to say so. One thing C teaches here in the negative: it gets its
capitals by typing them into the copy, which a screen reader spells out letter by letter. If we do
this, it is `text-transform`, never the content.

**Refined: "Two CSS transitions in the entire stylesheet, and the primary CTA measured dead on
hover."** The stylesheet count holds for A and B, where every transition rule is framework furniture;
C has three, one of them authored. The CTA finding is exactly right for A and I reproduced it —
pointer on the element, `:hover` matching, background, transform, opacity and shadow all unchanged
and `transition-duration: 0s`. B and C both *do* change something on hover. Neither moves.

So the sentence "the primary action does nothing at all on hover" is true of one page, not of dense
interfaces. The correct statement is stronger and more useful: **all three give the primary action an
instant, non-geometric acknowledgement or none at all. None of the three moves, scales, or eases
anything.** `transition-duration` is `0s` on the primary action of all three pages.

**And the load-bearing conclusion is not weakened by this — it is confirmed three times.** Section 6
argued the felt quality does not come from motion. Three independent designers, three pages that read
as engineered, one spinner keyframe each, at most one authored transition in a whole stylesheet,
nothing decorative running at rest on any of them. If animation were where the quality came from, one
of the three would have used some. The standing prohibition on new motion still costs this console
nothing, and that now rests on three measurements rather than one.

**Refined: "our 112 `font-mono` declarations carry a distinction the reference has no equivalent
of."** True of A and B, both of which have no monospace at all. C is 46% monospace — but it uses it
as a *typeface for furniture*: navigation, buttons, eyebrows, captions. Ours means the system
recorded this verbatim. Both uses are legitimate and they are incompatible: adopt C's and our
semantic signal is destroyed, because mono would then be everywhere and mean nothing. **Keep ours,
and treat C as the demonstration of what breaks it.**

## 11. What this changes in Tasks 12 through 16

No task is renumbered, reordered, or removed. Each revision below is a change to a step's
justification or a step's target, and each names the step it changes.

**Task 12, Step 2 — the furniture class.** Build it, but not for the reason written. The reason
written cites a treatment two of three references do not use at all. Replace the justification with
the Sync-side one: `site-nav.tsx:65` arrived at uppercase and open tracking independently for
graph-level labels, the smallest step carries what is scanned rather than read, and legibility at
speed on short capitalised runs is the whole of what the F1 framing actually asks for. Add one
implementation constraint that C supplies in the negative: the class sets `text-transform:
uppercase`; **the capitals never go into the copy**, because a screen reader spells those out.
`DESIGN.md` records this as our decision, not as a measured convention.

**Task 12, Step 3 — the surface ramp's grouping contract.** The premise "a 2,700-element page is
organised with zero borders" is false and must not be written into `DESIGN.md`. The contract to state
is the one all three references actually follow: **a rule where something is separated, a surface step
where something is grouped, and neither applied by default.** The change to our tree is unchanged —
the ring stops being applied to every surface — but the reason is our own measurement that an
identical ring on every surface encodes nothing.

**Task 12, Step 1 — tracking on `--text-section` and `--text-emphasis`.** Unchanged in substance, with
the direction now confirmed three ways: tracking is negative at the display end in all three
references and never looser than body. Adding it to the two mid steps is consistent with that.

**Task 13, Step 1 — radius.** Unchanged. Note for whoever executes it that the references disagree
(0, 8, 0), so this is our call and `--radius-surface` at 10px stands on `DESIGN.md`'s argument alone.

**Task 13, Step 3 — `TableHeader` on `surface-subtle`.** Keep the surface step, and **keep the header
rule as well.** Section 3's aside that "a table needs a header rule" is now supported rather than
assumed: C's only six border declarations in 2,103 elements are on the one element that is a grid.
The step should not be read as licence to remove the rule in favour of the surface step; it is both,
and the rule is the thing that survives a dense table.

**Task 14, Step 1 — separating the page frame from the between-panel gap.** The target is now a
number rather than "one step". The triangulated invariant is **each spacing level at least 2× the one
below**, measured at 2.0 (A), 2.4 (B) and 1.8 (C) between frame and section, and 3.3, 3.0 and 2.7
between section and component. Our measured 24 : 24 : 16 fails the first at 1.0. Aim for the ratio at
our magnitudes, not theirs — at a 8px in-component unit in a table, 2× and 2× again is 16 and 32, and
that is affordable in rows. **The reference magnitudes are still refused, now on three measurements
instead of one.**

**Task 15, Step 1 — four of six type steps per screen.** Add a companion constraint the three
references agree on and our console has no rule for: **prose is never set to the column's full
width.** All three hold prose to between a quarter and a half of the content column. This binds
hardest on exactly the sentences this plan protects — the honesty qualifications are prose sitting
beside tables, and a qualification set 1,392px wide at 12px is a qualification nobody finishes
reading. Restyling for measure is explicitly permitted by the protection; shortening is not.

**Task 16 — the guard.** Add a fourth assertion, because the motion finding is now confirmed on three
independent pages and is the cheapest thing in this plan to regress. Assert that no file under
`web/src/features/` or `web/src/layouts/` declares a `transition-duration` above zero or an
`animation` shorthand, and that `web/src/index.css` declares no `@keyframes` beyond those already
present. The interaction the console has stays where it already is and was already right — inside
`components/ui/`, which the assertion excludes. Prove this one can fail like the other three.

**Unchanged and reaffirmed:** every item in section 5's rejection list, the twenty-four protected
sentences, and the standing prohibition on a score, a health figure, a traffic light, a green dot or
a liveness pulse. Reference C's own mock panel renders exactly the pattern we have rejected three
times — coloured status pills reading as completed, running and failed — which is a good illustration
of how naturally it appears when nobody has ruled it out, and changes nothing here.

## 12. The limit, and how much of this actually survives to a thousand rows

All three references are landing pages. Two dozen elements a screenful, one column, marketing copy,
no data. There is a sharper version of that limitation worth stating, because it was discovered while
measuring rather than assumed: **the only data-dense artifacts on any of the three pages are flat
PNGs.** B's workflow panel and C's table of runs are images. Neither is DOM and neither can be
measured. So none of these three pages contains a real dense surface at all, and every claim below
about what happens at a thousand rows is inference from marketing layout, not measurement of a
control surface.

With that said plainly, here is the honest split.

**Survives translation intact.** The weight discipline; two ink levels and one accent; negative
tracking at the display end; leading that loosens as size falls; primary and secondary controls
differing only by fill; prose capped well below the column width; and the whole motion finding. Every
one of these gets *easier* as density rises, not harder — a table of a thousand rows needs fewer ink
levels than a marketing page, not more, and it needs less motion, not more.

**Survives as a ratio, never as a magnitude.** The three spacing levels. Section padding of 64–80px
and a page frame of 113–173px would cost rows on every screen, and `DESIGN.md` is explicit that
whitespace is the currency being spent. Section 5 refused those magnitudes on one measurement; three
measurements refuse them the same way and additionally show the ratio itself is not a constant, which
means what transfers is only "each level distinguishably larger than the one below", and our own
floor decides how much larger.

**Survives as a role assignment, not as a scale.** The type range. A 56px or 64px display step is a
row and a half of table gone every time it appears. Our declared 2.67:1 is not the defect; section 2
measured the defect precisely — 78% of type on the two smallest steps and the figure step used once
in the whole console. Spending six declared steps at our magnitudes is the work. Reference C reaching
5.82:1 across twelve steps is a reminder that step count is not the mechanism.

**Does not survive.** The single-plane ruleless surface, which was never real in any of the three.
The uppercase micro-step as a measured principle, though it survives as our own decision. Monospace
as a furniture typeface. And the twelve-step ramp.

**What this means for the owner's question.** The parts of a premium landing page that come from
typographic range, tracking, spacing ratio, ink restraint and the refusal to animate transfer almost
completely, and they are the parts section 1 identified. The parts that come from air — 173px
margins, 900px hero sections, a 64px headline — do not transfer at all, and they are also the parts a
person most easily mistakes for the source of the quality. A control surface earns the same feeling
by spending its restraint on legibility at density rather than on space, which is the same
discipline pointed at a different constraint. That is the whole of what three references can tell us,
and the last unmeasured mile — whether it works at a thousand rows — is ours to find out on our own
screens.

## 13. Added 2026-08-05 — a published control plane, measured and read

Sections 1 through 12 rest on three landing pages, and section 12 states the limitation plainly:
none of the three contains a dense surface at all, because the only data-dense artifacts on any of
them are flat PNGs. Every claim about a thousand rows was inference.

Reference D is a different kind of evidence. It is a **published design system for a developer
control plane** — Vercel's Geist, at `vercel.com/geist` — which means two things the landing pages
could not offer. Its surfaces are real DOM at real density rather than screenshots, so they can be
measured. And its decisions are **documented with their reasoning**, which is the one form of
material `.claude/rules/interface-originality.md` permits without qualification: a stated argument
is a concept, and concepts transfer where layouts do not.

That rule binds here exactly as above. Nothing below is a layout, a component composition, a colour
system or a phrase. Where a Geist rule is quoted it is quoted as evidence of what a control plane
concluded, and the recommendation that follows is restated from our operator, our graph and our
product position. Where a finding survives only because Geist does it, that is said out loud and
the finding is cut.

**Method.** Chrome at 1440x900, `getComputedStyle` across every element in the document, the
system's own dark theme forced on so the measurement describes the surface we are building. A real
pointer moved onto controls so `:hover` genuinely matched, verified by reading `matches(':hover')`
before reading the style. Font metrics taken from canvas at 130px and normalised, so they are ratios
rather than rounded pixels. Pages measured: `introduction`, `colors`, `typography`, `materials`,
`table`, `button`, `badge`, `status-dot`, `gauge`, `entity`, `description`, `empty-state`, `note`.

**One thing could not be measured, and it is said rather than worked around.** `vercel.com/dashboard`
redirects to a login page. The running product is behind authentication, so every number below comes
from the published system and its live component surfaces, not from the operational dashboard. The
component surfaces are real DOM and are dense; the dashboard would have been better.

### 13.1 The token layer, read

467 custom properties resolve on `:root`. The structure, not the values, is the finding.

**Colour is indexed by job, and the same index does the same job in every hue.** Nine scales of ten
steps each — a neutral, its alpha twin, and seven chromatics. The documentation states what each
index is for, and it is identical across scales: **1 to 3 are component backgrounds (default, hover,
active); 4 to 6 are borders (default, hover, active); 7 and 8 are high-contrast backgrounds; 9 and
10 are text and icons.**

Three consequences follow, and all three are measurable in the ramp itself.

- **Only two of ten steps are text.** The "two ink levels" the three landing pages agreed on
  emergently is here a stated rule with a reason. Counted on a live component page in dark mode:
  208 text-bearing elements at the secondary ink, 27 at the primary, 4 strays, 2 inverted. **89% of
  all rendered text is the secondary level.** Primary ink is the exception, not the default.
- **Three of ten steps are borders.** A line is not an afterthought in a control plane; it gets as
  much of the ramp as text does. Measured on the table page: 23 elements at one border step and 18
  at the next.
- **The ramp is not monotonic, because it is not a ramp.** Lightness by index in dark mode runs 10,
  12, 16, 18, 27, 53, 56, 49, 63, 93 percent. **Step 8 is darker than steps 6 and 7.** A scale tuned
  to a job at each index will do that; a scale interpolated between two endpoints cannot. This is the
  clearest single piece of evidence that the index names a role.

**There are exactly two page backgrounds.** One default, one for the rare case where a subtle
differentiation is needed, and the documentation says to use the first in most instances. Everything
that looks like a third or fourth surface is a *component* background at rest, hover or active. So
the surface inventory of a control plane is **two levels of depth and three levels of state**, not
five levels of depth.

**One height scale governs controls, form fields, popover rows and menu rows alike:** 32, 36 and 40
pixels, named small, medium and large, with the form-field and popover-row tokens resolving to the
same three numbers. A control drops into a dense row without breaking the rhythm because there is
one rhythm.

**Elevation is a bundled preset whose name is its role.** Eight presets, each fixing radius, fill,
stroke and shadow together: four that sit on the page and four that float above it. The
documentation's rule is that you pick the preset from where the element sits in the layered
hierarchy, never by choosing a shadow; that you never stack two on one element, and a child needing
more elevation is lifted into its own; and that the choice is aligned with the element's z-index
band, which is itself tokenised in five named steps. Radius is a function of that role — 6px at the
resting levels, 12px at the raised and floating ones, 16px at full-screen — and separately a function
of control size, 6px on the two smaller controls and 8px on the largest.

**Lines are drawn as shadow rings, and it is a token.** The border preset is a 1px spread box-shadow
rather than a border property. This is the same construction the three landing pages reached (452,
14 and 576 thin filled divs respectively), arrived at here for a reason a control plane has and a
marketing page does not: **a ring costs no layout.** A border changes an element's box; in a table
where a selected row must not shift by a pixel relative to its neighbours, that matters. Our own
`shadow-flat` ring is the same mechanism, arrived at independently.

**Focus is one hue, and it is the link hue.** The focus ring is a double ring: two pixels of the
page colour, then two pixels of the accent. That construction exists so the ring reads against any
surface step underneath it. On a dense surface where focus can land on a row, a cell, a control
inside a cell, or a header button, a single-ring focus indicator disappears against roughly half of
them.

**Motion has tokens, and they are named by role rather than by duration:** an overlay duration, a
popover duration, one shared timing curve with a slight overshoot, and a default transition duration
of 0.15s. That a control plane tokenises motion at all is the first sign of the disagreement section
15 develops.

**Space is base 4**, with the scale 4, 8, 12, 16, 24, 32, 36, 40, 64, 96, 128, 192, 256 and named
aliases at 8, 12, 24, 32 and 40. **The page margin token is 24px.** That number is the whole of
section 15's spacing argument and it is worth reading twice.

### 13.2 Type, which is a matrix and not a ramp

This is the finding that most changes how we should read our own numbers.

Geist does not publish a type scale. It publishes **four roles, each with its own sizes, leading and
weight**, and a size may appear in more than one role with different treatment.

| Role | Sizes | Weight | Tracking | Job, as documented |
|---|---|---|---|---|
| **Heading** | 72, 64, 56, 48, 40, 32, 24, 20, 16, **14** | 600 | -0.06em at 40 and above, -0.04em at 24-32, -0.02em at 14-20 | introduce a page or a section |
| **Button** | 16, 14, 12 | 500 | normal | only inside components that render buttons |
| **Label** | 20, 18, 16, 14, 13, 12, plus mono at 14, 13, 12 | 400 | normal | single lines, ample leading, marries with icons |
| **Copy** | 24, 20, 18, 16, 14, 13, plus mono at 13 | 400 | normal | multiple lines, higher leading than Label |

Two modifiers, and nothing else: **Strong** raises 400 copy to 500 inside a line, and **Subtle**
lowers a 600 heading to 500 inside a line. Weight is therefore **not a hierarchy channel at all in
this system — it is a within-line emphasis modifier plus one constant per role.**

Measured leading, which shows the roles diverging: Heading runs 1.0 at 72, 56 and 64 up to 1.5 at 16;
Label runs 1.11 to 1.6 and takes 16px of leading at 13px; Copy takes 18px of leading at the same
13px. **The same size gets different leading depending on whether it is a row or a paragraph.**

The documented usage notes are worth more than the numbers:

- Copy at 24, 20 and 18 is marked **for marketing pages and hero areas**. The application register
  tops out at 16 for read text.
- Copy 14 is "the most commonly used text style"; Label 14 is "the most common text style of all".
- Copy 13 is "for secondary text and views where space is a premium".
- Label 12 is "for tertiary level text in busy views", and it is the step that carries capitals.
- Label 13 carries **tabular figures**, "used when conveying numbers for consistent spacing".
- Mono appears only at 14, 13 and 12, and is documented as pairing with a sans size one step larger.

**Measured on a live component page in dark mode**, the working band is narrow: of 231 text-bearing
elements, 183 at 14px, 22 at 16, 18 at a mono 13.7, 7 at 24, 4 at 12, 4 at 20, 2 at 13 and 1 at 40.
The nominal range is 40/12 = **3.33:1**, but **90% of all text sits inside 12-16px, a band of
1.33:1**. Weights present: 400 on 195, 500 on 34, **600 on 12**.

**Letter-spacing is `normal` on every application-register element measured.** Negative tracking
appears only on 600-weight headings, graduated in three tiers by size.

### 13.3 The dense surface, measured

Six live tables on one page, and every one of them identical.

| | Measured |
|---|---|
| Body row height | **40px**, on all six tables |
| Header cell height | **36px** |
| Body cell padding | **10px vertical, 8px horizontal** |
| Header cell padding | **0 vertical, 8px horizontal** |
| Rules between body rows | **none** |
| Rule under the header | **one, 1px, at the documented default-border step** |
| Body cell ink | secondary, on every cell |
| Body cell weight | 400, on every cell |
| Header cell ink | **the same secondary ink as the body** |
| Header cell weight | **500** |
| Striped variant | alternate rows take the **deeper** background step, not a lighter one |
| Row on hover, pointer really on it | background unchanged, `transform: none`, no shadow |

Three things in that table are worth stating as sentences.

**The header separates from the body by one weight step and one rule.** Not by ink, not by a surface
step, not by capitals. That is the cheapest possible separator and it survives a thousand rows,
because it costs no contrast budget and no vertical space.

**Nothing in a row carries emphasis.** Every cell is the same size, the same weight and the same ink.
Emphasis inside a row comes from what you put in the cell — a badge, a mono value, a control — never
from the row's own typography. A dense surface stays legible by **refusing to rank its own fields**
and letting the columns do it.

**The row height is the governing number and the padding is derived from it.** A 20px line box plus
10px above and below is 40px, which is the large step of the one height scale. The 10px is not on the
base-4 grid; the system breaks its own spacing scale in the table cell in order to hit the row
height. Pick the row from the control scale first, then solve for padding.

### 13.4 Motion, with a real pointer

Measured on a component page carrying 976 elements.

- **34 named `@keyframes` exist in the document.** Every one sorts into exactly three jobs: an
  overlay entering or leaving, something loading, or the marketing site's scroll reveal. **None is
  decorative on an application surface.**
- **77 elements carry a transition — 7.9% of the document.**
- **30 animations are running at rest, and every single one is the spinner's opacity keyframe**,
  belonging to the loading-state demonstrations on that page. Nothing else moves.
- **The primary control, pointer on it and `:hover` confirmed matching: fill changes from
  rgb(237,237,237) to rgb(204,204,204). `transform: none`. Opacity unchanged. No shadow. And
  `transition-duration: 0.15s`, eased on a standard curve.**

Three sizes of that control, at 32, 36 and 40px high, taking 14/500, 14/500 and 16/500 type, 6px,
6px and 8px radius, and 6px, 10px and 14px of horizontal padding. **Every variant differs from every
other by fill alone** — identical geometry, identical type. That is the fourth independent
measurement of the same construction.

### 13.5 Spacing at density, measured rather than tokenised

The rendered distribution inverts the landing pages completely.

| | Landing pages A/B/C | Geist, rendered |
|---|---|---|
| Dominant gap | 24px | **8px** (40 declarations), then 10 (20), 4 (12), 24 (6), 12 (6) |
| Dominant padding | 24px | **2px** (106), **6px** (91), **12px** (87), then 48 (14), 16 (9), 24 (7) |
| Page frame | 113-173px | **24px**, as a token |
| Frame : section : component | 4.7 to 7.2 : 2.7 to 3.3 : 1 | approximately **1 : 1 : 0.33** |

A control plane's page frame is the same value as its largest common gap. There is no 6.7:1.

---

## 14. Where Geist agrees with the three landing pages

Section 8 listed fourteen properties on which three designers agreed and called them invariants of
dense considered interfaces. A fourth measurement, this time of an actual control plane, holds seven
of them, refines three and breaks four. The agreements first.

| Property | A/B/C | Geist | Standing |
|---|---|---|---|
| Working ink levels | two, plus one accent | **two**, and stated as a rule with 89% on the secondary | **Confirmed, and now with a reason** |
| Ink default | primary is used sparingly | **89% of text is secondary ink** | **Confirmed, and sharper than we assumed** |
| Leading | loosens as size falls | 1.0 at the display end, 1.5 at 16px, 1.33 at 12px | **Confirmed** |
| Primary and secondary controls | identical geometry, differ only by fill | identical geometry and type, differ only by fill | **Confirmed four times** |
| Display tracking | negative, never looser than body | -0.02 to -0.06em, graduated, on headings | **Confirmed** |
| Nothing decorative runs at rest | 0, 0, and one 40ms scroll bar | 30 running animations, **all of them spinners** | **Confirmed, and this is the strongest form of it** |
| Geometry never moves on interaction | `transform: none` on all three | `transform: none`, no scale, no shadow | **Confirmed four times** |
| Lines are drawn without the border property | 452, 14 and 576 thin filled divs | a **tokenised 1px shadow ring**, and a stated reason | **Confirmed, and the reason is now known** |
| Prose never runs the column width | quarter to half the column | prose held to 862px inside a 1220px column, 71% | **Weakly confirmed; the constraint is looser in an app** |

The two that matter most are the last two and the sixth.

**"Nothing decorative is ever running" is now measured on a system that has every excuse to animate.**
Thirty animations were running at rest and every one was a loading indicator attached to a component
that was genuinely waiting. A control plane with 78 components, motion tokens, and a documented
overlay-animation model still runs nothing that is not reporting a real state. Section 6's conclusion
that the felt quality does not come from motion now rests on four measurements, one of them of
exactly our register.

**The ring construction now has an argument rather than a coincidence.** Section 10 concluded that
the useful rule was "a line where something is separated, a surface step where something is grouped,
neither applied by default", derived from what three pages did. Geist supplies the mechanism's
reason: a 1px shadow ring costs no layout, and on a surface where a row must not shift relative to its
neighbours when it gains a border, that is the whole point. Our `shadow-flat` is already this. The
defect section 2 found — every surface taking the identical ring, so the ring encodes nothing — is
unchanged and the fix is unchanged.

---

## 15. Where Geist disagrees, and which I trust for a dense surface

Four of section 8's fourteen invariants do not survive contact with a control plane. In every case
I trust the control plane, and in every case the reason is the same: the property was a consequence
of a page that is read once, and our screens are read all day.

### 15.1 Two weights, no 600 — broken, and we were already right

Section 8: "Two weights. No 600, no 700, in any of them." Measured on all three landing pages.

Geist: **600 on every heading at every size, down to and including 14px.** Weight 400 on 195
elements, 500 on 34, 600 on 12 in a single dark-mode census.

I trust Geist, and our own `DESIGN.md` already agrees — `--text-emphasis`, `--text-section`,
`--text-page` and `--text-figure` all carry 600 today. Section 5 refused "two font weights" on the
grounds that our range is 2.67:1 by decision and at that range weight does necessary work that size
cannot. That refusal was correct and is now confirmed by a system built for our register.

**And it goes further than a refusal.** Geist reaches a 14px heading — 600 weight, negative tracking,
20px line box, the same line box as a body row. A heading that costs no more vertical space than the
row beneath it is hierarchy for free, and it is the direct answer to "78% of our type is on two
steps". The problem was never that 78% of type sits at 12 and 14. The problem is that at 12 and 14 we
have **one treatment**, so a label, a value, a column header and a heading are indistinguishable.
Geist has four treatments in that band. We can afford at least three.

### 15.2 "At most one authored transition in an entire page" — broken, and the fourth guard must change

Section 8: "At most one in an entire page", from stylesheet counts of 0, 0 and 1. Section 10
strengthened the CTA finding to "instant, non-geometric acknowledgement or none at all, and
`transition-duration: 0s` on all three". Section 11 turned that into a new assertion for Task 16
banning any `transition-duration` above zero under `features/` and `layouts/`.

Geist: **77 transition-bearing elements out of 976, and the primary control eases its fill over
0.15s on a standard curve.** The change is still non-geometric — `transform: none`, no scale, no
opacity, no shadow — but it is not instant.

I trust Geist without hesitation, and the reason is a product difference rather than a taste
difference. A landing page has one call to action and the visitor clicks it once. **The button on
that Geist page was one of 47.** When a surface carries dozens of controls and the operator's pointer
crosses several on the way to the one they want, an instant fill change reads as flicker; a 150ms ease
reads as the surface tracking the pointer. The feedback is not decoration, it is disambiguation, and
only a dense surface generates the requirement.

**Section 11's fourth assertion for Task 16 is wrong as written and must not be built as written.**
Section 18 replaces it with two narrower assertions that all four references support.

### 15.3 The three-level spacing ratio — broken at the outer level, and this is the sharpest disagreement

Section 8: "Three levels, each at least 2x the one below; frame 4.7 to 7.2x the in-component unit."
Section 11 turned that into Task 14 Step 1's target.

Geist: **the page margin token is 24px, which is also the dominant named gap.** The rendered
distribution is dominated by 8px gaps and 2, 6 and 12px paddings. Frame-to-section is approximately
**1:1**, not 2:1 and certainly not 4.7:1.

I trust Geist, and the argument is one this plan already made in a different place. `DESIGN.md` says
vertical space is the currency and every unit of it is a row that fell off the viewport. Section 5
and section 12 both refused the landing pages' magnitudes on exactly that ground. What the fourth
measurement adds is that **the ratio does not survive either, at the outer level.**

The reason is structural rather than aesthetic. On a landing page the frame is the only thing
separating the content from the browser, so it has to do the work of saying "this is a composition".
On a console the frame is bounded by a persistent navigation rail and a header, which already say
that, and every pixel spent on the frame is taken from a nine-column evidence table. **A control
plane's frame does no hierarchical work, so it is set to the smallest value that keeps content off
the chrome.**

The step ratio is still real, but it lives one level down. Section 18 revises Task 14 Step 1
accordingly: hold the step between the three *inner* levels and stop requiring the frame to exceed
the between-panel gap.

### 15.4 "The smallest step is a different job" — resolved, in our favour, on a third reading

Section 1 measured Reference A's 12px step as uppercase with +0.1em tracking and promoted that to a
principle. Section 10 demoted it, because B and C have no uppercase anywhere at all, and reduced it to
our own decision defended on our own grounds.

Geist restores partial support with reasoning rather than habit. Its Label 12 is documented for
"tertiary level text in busy views" and it is the step that carries capitals. Two of four references
now use the treatment, and the one that documents it documents it **for the exact condition we have** —
tertiary text in a busy view. Its Label 13 additionally carries tabular figures for numeric comparison
across rows.

The status of Task 12 Step 2 is unchanged: build it, as our decision, justified from `site-nav.tsx:65`
arriving at it independently for graph-level labels. But it is no longer a lone habit, and the brief
can now say the role it serves is the one a control plane names.

### 15.5 One more disagreement, smaller, and it is about our own table

Section 2 recorded `TableRow`'s `hover:bg-muted/50` as "the one interaction in the console that was
already right", and Task 13 Step 3 instructs the executing agent to leave it exactly as it is.

**Geist's table row does not respond to hover at all.** Pointer on it, `:hover` matching, background
unchanged. Its *navigable* rows do respond, by moving to the other background step. The distinction
is that a row highlights when it is a target and stays quiet when it is data.

I trust Geist here, and the argument is ours: a highlight is an affordance, and an affordance that
leads nowhere is a lie the surface tells forty times a second as the pointer crosses the table.
Several of our tables are evidence, not navigation. Section 18 revises Task 13 Step 3 to keep the
hover where the row is genuinely navigable and remove it where it is not — and to move it off an
alpha overlay, because an alpha composites differently against each of our four surface steps and
therefore means four different things.

---

## 16. What transfers, in our own terms and our own tokens

Nine things. Each is stated as a problem we have, and each survives the rule's test: it can be
justified from the operator, the graph or the product position without pointing at anybody's screen.

**1. Our nine-step neutral ramp should say what each index is for, and the indices should not all be
about lightness.** The console's ramp is currently a lightness gradient with four steps named for
surfaces. The problem it fails to solve is ours and specific: a reviewer looking at an evidence table
cannot tell a panel from a header from a selected row from a hovered row, because all four are drawn
from the same continuum and none of them is *reserved*. Assigning jobs to indices — which are
surfaces, which are borders, which are text, which are state — makes the ramp answerable and makes a
misuse visible. **This is a documentation and allocation change, not a new value.**

**2. The extra surface steps belong to state, not to depth.** This is the single largest correction
to section 3. That section proposed letting grouping ride the four-step surface ramp so the ring
could stop being applied to everything. The direction is right and the allocation is wrong: two of
our four steps should carry depth — the page and a panel — and the remaining head-room should carry
**rest, hover and selected on a row**. Our own evidence supports this over the landing pages': we
have exactly one authored interaction in eight feature screens, and the reason is that we have no
vocabulary for state, so every agent invents an alpha overlay. Two depth levels is also what
`DESIGN.md` already declares.

**3. A table header separates by weight and one rule, and needs neither ink nor surface.** Task 13
Step 3 currently spends `surface-subtle` on the header. A weight step plus the rule we are already
keeping is cheaper, costs no contrast budget, and leaves `surface-subtle` free for point 2. Justified
from us: our tables run to hundreds of rows and the header is the one element that must survive being
sticky over any surface underneath it — a background makes that harder, a weight does not.

**4. A row's fields should not be individually ranked, and the row height should be picked before the
padding.** Our body step is 14px on a 20px line box, which is the same line box a control plane uses;
with 8px of row padding that is a 36px row, and 36px is a legible medium row. The transferable
mechanism is the ordering: **choose the row height from the same scale the controls use, then derive
the cell padding from it**, so a button dropped into a cell does not change the row. We have no
height scale today, which is why nothing lines up.

**5. Weight and leading, not size, are the affordable hierarchy channels inside the 12-16px band.**
This is the answer to the 2.0:1 measurement in section 2, and it is a better answer than the one
section 3 gave. Adding steps costs rows; a heading set at the body size in the heading weight costs
none. Our system already has the weight; it does not have the rule that says a screen must
distinguish scanned text from read text from headed text within the band.

**6. A single-line row and a paragraph at the same size should not share a line-height.** Measured:
a control plane gives its single-line label role 16px of leading at 13px and its multi-line copy role
18px at the same size. Our six steps carry one leading each, so a table cell and a qualification
paragraph are set identically. The qualification is the thing that suffers, and the qualifications
are what this plan protects.

**7. Tabular figures on every numeric column, and mono stays reserved.** The problem is ours and
concrete: a count of findings, a count of bindings and a row count only support comparison down a
column if their digits align. A control plane solves it two ways — tabular figures, or monospace —
and **the second one is closed to us**, because mono in this console means the system recorded this
value verbatim, and spending it on every number destroys the signal. So: tabular figures on numeric
columns, mono reserved for verbatim. Section 10 said C's furniture-mono is what breaks our rule;
this is the same hazard arriving from the numbers side, and the same answer.

**8. Absence needs a mark and a vocabulary, and there is more than one kind of nothing.** A control
plane renders a typographic mark where a value is unknown or not applicable and forbids substituting
an empty string, a null or an abbreviation — and separately ships six distinct empty states, for a
filter that matched nothing, a resource never created, work that has been cleared, a permission
denial, an informational blank, and a failed load. **Our data distinguishes more kinds of nothing
than theirs does**, because the provenance rung tells us whether a binding was never observed or
observed and empty, and that difference is the whole of the false-positive story. So we take the
discipline — every empty cell carries a mark, never a blank — and we go further than the convention,
because collapsing "not applicable" into "not observed" would erase a rung.

**9. A qualification is persistent by construction, and stacking three of them is an architecture
signal.** A control plane's rule for its inline-notice primitive is that it persists until the
underlying state changes, that it carries no dismiss control because the control competes with the
message, and that three of them stacked on one card means the page architecture is wrong rather than
the copy. The first two are Decision 3 restated by somebody else, which is worth recording. **The
third is uncomfortable and useful**: this plan protects twenty-four sentences, and if a screen ends
up stacking several of them, that is evidence the screen is answering too many questions, not
evidence the sentences are too long. Nothing here licenses shortening one.

### 16.1 The component inventory, and what we lack

A control plane ships 78 documented primitives. We have three that this plan counts — button, card,
table — inside a `components/ui/` directory of eight files. The gap is not 75 components; most of
that inventory is form controls and overlays we do not need yet. The honest short list is the
primitives our own data demands and our tree currently fakes:

| Missing | The problem it solves for us, stated without reference to anybody's system |
|---|---|
| **A definition list** | Finding detail and node detail are key/value metadata rendered as two-column tables inside cards. `<dl>` is the correct semantics, is denser, and lets a screen reader announce a pair as a pair. |
| **A qualification notice** | The twenty-four protected sentences are ad-hoc prose in ad-hoc containers. A primitive that is persistent by construction and has no dismiss path enforces the protection instead of leaving it to an audit every task has to repeat. |
| **An empty state with variants** | We have at least four kinds of nothing and render them identically. |
| **A verbatim value** | File paths, finding ids and node names are mono text with no copy affordance and no truncation strategy. |
| **A middle truncation** | A file path truncated at the end loses the filename, which is the part that identifies it. Our columns are fixed and our paths are long. |
| **A loading state that is not zero** | An indeterminate figure and a zero figure currently render the same, which is precisely the failure the absence channel exists to prevent. |

**Ruling, recorded here rather than acted on: this list does not become tasks in this plan.** Tasks 12
through 16 are being executed from by another session and the parallel partition depends on their file
sets. The inventory is a finding, it is written down so it is not rediscovered, and the two with the
strongest argument — the qualification notice and the verbatim value — should be the first work
proposed after Task 16 lands.

---

## 17. The font, and what it costs

Geist Sans and Geist Mono are OFL-licensed and installable, which makes this the one item here that
is a real adoption decision rather than a concept. It was measured rather than assumed, against the
stack `DESIGN.md` actually specifies today.

### 17.1 What was measured

Metrics taken from canvas at 130px and normalised to the em, so they are ratios.

| | Geist Sans | Geist Mono | Segoe UI (our sans) | Cascadia Code (our mono) | Consolas |
|---|---|---|---|---|---|
| x-height / em | **0.5308** | **0.5308** | 0.5000 | 0.5231 | 0.4923 |
| cap-height / em | 0.7154 | 0.7154 | 0.7000 | 0.7000 | 0.6385 |
| descender / em | **0.1538** | **0.1538** | 0.2308 | 0.2308 | 0.2000 |

Advance width, measured on `sync.index.dependency_edits` — 27 characters of the kind that actually
fill our cells:

| | at 13px | at 14px |
|---|---|---|
| Geist Sans | 174.10px | 187.49px |
| Segoe UI | 165.01px | 177.70px |
| Geist Mono | 210.60px | 226.80px |
| Cascadia Code | 205.66px | 221.48px |
| Consolas | 192.98px | 207.83px |

Digits `1234567890` at 13px: Geist Sans 74.67px, Segoe UI 70.08px.

Payload, as served: **Geist Sans variable woff2, full unicode range, 69,740 bytes. Geist Mono latin
subset, 23,108 bytes**, with five further subsets loaded only when their ranges are used. Roughly
**91 KB** for the pair with a full weight axis. A latin-only subset of the sans would be materially
smaller.

### 17.2 The three questions the brief asked, answered

**Does it improve legibility at 12-14px, where 78% of our type sits?** Yes, and the mechanism is
measurable rather than aesthetic. Geist Sans has a **6.2% larger x-height than Segoe UI** at the same
nominal size, and apparent size at small sizes is governed by x-height, not by the nominal number.

There is a cost hiding behind that, and it resolves in our favour. Geist Sans is **5.5% wider than
Segoe UI at the same nominal size**, and its digits are 6.6% wider — which on a nine-column table is
real column budget. But the comparison at equal *nominal* size is the wrong one. At 13px Geist Sans
has an x-height of 6.90px; at 14px Segoe UI has 7.00px. **So Geist at 13px is within 1.4% of Segoe's
apparent size at 14px, and its advance is 174.10px against 177.70px — 2.0% narrower.** Setting our
body step at 13px in Geist would be no less legible than 14px in Segoe, would be slightly narrower
per row, and would free a pixel of line box.

The descender is the second, quieter win. Geist's descender is **33% shallower** than Segoe UI's.
Descender depth is what forces a line box taller than the type needs; a shallower one is why a 20px
line box can hold 14px type without the risk of clipping that our current pair carries.

**Does a matched pair strengthen or blur the mono rule?** It strengthens it, and the measurement says
why. Geist Sans and Geist Mono are **metric-matched on the vertical axis to four decimal places** —
identical x-height, cap-height, ascender and descender. Our current pair is not: Segoe UI and Cascadia
Code differ by 4.6% in x-height, so a mono span inside a sans row today reads as *a different size*.

That is the blur, and it is in our current stack rather than in the matched pair. Size is the channel
our type ramp owns; a mono run that also shifts apparent size is competing with the hierarchy. A
matched pair removes size from the mono signal entirely and leaves it carried by letterform and by
advance rhythm — Geist Mono is 21% wider than Geist Sans for the same string, so a mono run is
unmistakable without being a different size. **Mono means the system recorded this verbatim, and it
should mean only that.**

One hazard, and it is worth writing into `DESIGN.md` if this is adopted: a matched, pleasant mono
invites exactly the drift section 10 identified in Reference C, where mono becomes a furniture
typeface for navigation and captions and consequently means nothing. The rule survives adoption only
if it is written down and guarded.

**What does it cost?** Honestly:

- **~91 KB of woff2** as served, less with a latin subset. Against a console that today ships zero
  font bytes and makes zero font requests.
- **A font-loading strategy, or a flash.** A variable font at 68 KB will not be there on first paint.
  The mitigation Vercel ships is a metric-adjusted local fallback face so the swap causes no reflow;
  that is a real, hand-written `@font-face` with `size-adjust`, `ascent-override` and
  `descent-override`, and getting the numbers wrong makes the swap worse than no fallback. It is an
  afternoon of work and it is not optional, because a reflowing table is worse than a plain one.
- **`DESIGN.md`'s current position becomes false and must be rewritten.** It states today that a
  webfont buys a network request, a flash of unstyled text and a licence question, for a console
  nobody outside the project has opened. Two thirds of that stands. The licence question does not —
  OFL settles it.

### 17.3 The ruling

**Adopt Geist Mono. Defer Geist Sans.** They are separable and they should be separated, because the
arguments for them are not equally strong.

The mono case is the strong one and it is nearly free. Our mono is load-bearing — it is a semantic
claim about provenance, not a style — and it is currently rendered in a face that sits at a different
optical size from the sans beside it, which weakens the one distinction we most need to read
correctly. Geist Mono's latin subset is **23 KB**, it is metric-matched to a sans we may or may not
adopt, its x-height is 7.8% larger than Consolas's, and it is the smaller half of the payload. A
flash on the mono spans alone is also the cheaper flash: mono is a minority of our text, and those
spans are values rather than prose, so a swap disturbs less.

The sans case is real but not urgent, and it should wait for a specific reason. The measured gain is
a body step that can drop from 14px to 13px at equal legibility and slightly narrower — which is
worth about one extra column of a wide table, or a pixel of line box per row. That is a genuine gain
and it is not worth 68 KB, a fallback-metrics exercise and a first-paint regression **until we have
measured a screen at a thousand rows and know whether we need that pixel.** Section 12 named that as
the last unmeasured mile. Adopt the sans when the mile is measured and it turns out we do.

**And one thing to take from the font work regardless of either decision: tabular figures.** They are
available in the system stack we already ship, they cost nothing, and transfer item 7 above is the
argument. Do that first.

---

## 18. What this changes in Tasks 12 through 16

No task is renumbered, reordered or removed, and the parallel partition is unchanged. Each revision
below names the step it changes and what replaces it.

**Task 12, Step 1 — tracking on `--text-section` and `--text-emphasis`.** Confirmed a fourth time and
now with target values. A control plane applies negative tracking **only to its heading role**, never
to a label, a button or body copy at any size, graduated by size: about -0.02em at 14-20px, -0.04em at
24-32px. Our steps map onto that directly — `--text-emphasis` at 16 and `--text-section` at 18 take
the shallower value, and `--text-page` at 24 and `--text-figure` at 32 already carry tracking that
should be checked against the deeper one. **Add the condition to `DESIGN.md`:** tracking travels with
these steps because they are heading roles; if `--text-emphasis` is ever used for in-row emphasis
rather than a panel title, that use takes the step without the tracking.

**Task 12, Step 2 — the furniture class.** Unchanged in substance, and the brief's justification gains
a fourth measurement. Section 11 correctly demoted the uppercase micro-step from a measured principle
to our own decision. It stays our decision, but the role it serves is now one a control plane names
explicitly: the smallest step carries **tertiary text in busy views**, which is what a graph-level
label, a column header and a rung label are. The implementation constraint from section 11 stands
without change — the class sets `text-transform`, and the capitals never go into the copy.

**Task 12, Step 3 — the surface ramp's grouping contract. This step changes most.** Section 11 already
struck its false premise. The contract to write is now more specific than "a rule where something is
separated, a surface step where something is grouped":

- **Two of the four surface steps carry depth** — the page, and a panel on it. That is all the depth
  a console needs, and it is what `DESIGN.md` already declares by having exactly two elevation levels.
- **The remaining head-room carries interaction state** — a row at rest, a row under the pointer, a
  row selected — and not a third and fourth level of nesting. This replaces section 3's proposal that
  grouping ride the whole ramp. The argument is ours: eight feature screens contain one authored
  interaction between them, because the system gives an agent no vocabulary for state and every agent
  invents an alpha overlay instead.
- **State steps are named surface values, never an alpha overlay.** An alpha composites differently
  against each depth step underneath it, so one declaration means several different things.
- **The ring is kept for a surface that must be told apart from a neighbour at the same step**, as
  already ruled, and it stops being applied by default.
- Record why the ring is a shadow rather than a border, in one sentence: a ring costs no layout, so a
  row that gains one does not shift relative to its neighbours.

**Task 12, Step 4 — the spacing ruling.** Unchanged: three tokens, no fourth, page frame unnamed on
Tailwind's base scale. Add one recorded decision that section 15.3 now supports: **the page frame is
set to the smallest value that keeps content off the chrome, and it is not required to exceed the
between-panel gap.** A control plane's frame does no hierarchical work because the nav rail and the
header already do it.

**Task 12 — one addition, and it is cheap.** Record a **row-height scale** in `DESIGN.md` alongside
the spacing tokens: three values that govern a control, a form field and a table row alike, so a
control dropped into a cell does not change the row. Our `--text-body` at 14/20 with `p-row` above and
below already produces a coherent row; the point is to name the height, derive the padding from it,
and stop deriving the row from the padding. **No fourth spacing token** — this is a height scale, and
it belongs with the control sizes rather than with the gaps.

**Task 13, Step 1 — radius.** Unchanged, and now with a fourth data point that does not disturb it. A
control plane makes radius a function of two things: elevation role (6, 12, 16) and control size (6 on
the two smaller controls, 8 on the largest). Our two-value rule is a deliberate simplification and it
stands on `DESIGN.md`'s own argument. Note the alternative in the brief so the next agent does not
rediscover it as a defect.

**Task 13, Step 3 — `TableHeader`. Revised, and it gets cheaper.** Section 11 already ruled that the
header rule stays. The measurement now shows the surface step is not needed to do the separating: a
control plane's table header sits on **no background at all**, uses **the same ink as the body**, and
separates by **weight 500 against 400 plus one 1px rule**. Make the weight step and the rule the
mechanism, and treat the surface step as optional. Two reasons, both ours: a sticky header over a
scrolled body is easier to keep legible without a background than with one, and freeing
`surface-subtle` is what pays for the state steps in Task 12 Step 3.

**Task 13, Step 3 — the second half, which section 11 did not touch.** The instruction to leave
`TableRow`'s `hover:bg-muted/50` "exactly as it is" is now revised. **Keep a hover response only where
the row is genuinely navigable, and remove it where the row is evidence.** A highlight is an
affordance; on a row that leads nowhere it is a promise the surface cannot keep, made forty times a
second as the pointer crosses the table. Where it is kept, move it from the alpha overlay to the named
state surface from Task 12 Step 3, and keep the transition — see Task 16 below, which no longer
forbids it.

**Task 14, Step 1 — separating the page frame from the between-panel gap. Retargeted.** Section 11 set
the target as "each spacing level at least 2x the one below", from 2.0, 2.4 and 1.8 measured on three
landing pages. A control plane measures approximately **1:1** at that level and 24px of frame in
total. The revised target: **hold the at-least-2x step between the three inner levels — between-panel,
in-panel, in-row — and drop the requirement that the frame exceed the between-panel gap.** At our
8px in-row unit that is 16 and 32, which is affordable in rows and is what section 11 already
computed. The frame is set for chrome clearance and nothing else. Our measured 24 : 24 : 16 : 4 still
fails, but it now fails at the inner levels, which is where fixing it is free.

**Task 14, Step 3 — the figures take `--text-figure`.** Unchanged, and one companion constraint is
added. `--text-figure` is for the figures an operator acts on and it is currently used once in the
whole console; spending it is still the work. But **hierarchy elsewhere on the screen is carried by
weight at the body size, not by reaching for a larger step**, because a larger step costs rows and a
weight step costs nothing. A control plane sets headings down to 14px at weight 600 on a 20px line
box — the same line box as its densest row. That is the mechanism that makes a dense screen legible
without making it taller.

**Task 14, Step 4 — `ScreenLimitsCard`.** Unchanged and reinforced. The rule a control plane states for
its persistent-notice primitive is that it survives until the underlying state changes and carries no
dismiss path. That is Decision 3 arrived at independently, and it is the argument for lifting this
card rather than quieting it.

**Task 15, Step 1 — four of six type steps per screen. Revised to a role rule.** The step count is the
wrong target and section 12 already suspected it — a reference reaching 5.82:1 across twelve steps
reads as considered, so the mechanism is role assignment rather than step count. Replace the target
with: **every screen distinguishes scanned text from read text from headed text, and may do it with
weight and leading at one size where a larger step would cost rows.** The companion constraint from
section 11 — prose is never set to the column's full width — stands unchanged and binds hardest on the
protected sentences.

**Task 15 — two additions to Step 4, the honesty audit.** Both are things our data supports and our
rendering currently does not.

- **Every empty cell carries a mark, never a blank, a null or an abbreviation** — and the mark
  distinguishes *not applicable* from *not observed*, because the provenance rung distinguishes them
  and collapsing the two erases a rung. This is stricter than the convention a control plane
  documents, deliberately, and the reason is our own.
- **Numeric columns take tabular figures.** Available in the stack we already ship, costs nothing, and
  it is the alternative to spending mono on numbers — which would destroy the verbatim signal.

**Task 16 — the guard. The fourth assertion from section 11 must not be built as written.** It bans
any `transition-duration` above zero under `features/` and `layouts/`, on the strength of three
landing-page measurements. A control plane carries 77 transition-bearing elements and eases its primary
control's fill over 0.15s, and section 15.2 gives the reason. Replace it with two assertions that all
four references support and that guard the thing actually worth guarding:

- [ ] **Assert no `@keyframes` and no `animation` shorthand anywhere under `web/src/features/` or
  `web/src/layouts/`, and none in `web/src/index.css` beyond those already present.** Every keyframe
  in every reference measured is an overlay entering or leaving, or something loading. This is the
  assertion that stops a liveness pulse, which is the specific regression section 5 names as most
  likely.
- [ ] **Assert no transition on `transform`, `translate`, `scale`, `opacity` or `box-shadow` anywhere
  under `web/src/`.** All four references move nothing on interaction: `transform: none` on every
  primary control measured. Colour and background-colour transitions are permitted, because a dense
  surface needs them to say which of forty controls the pointer owns.
- [ ] **Prove both can fail**, as the other three assertions must, and for the reason expected.

`components/ui/` is no longer excluded from the second assertion — geometry must not move anywhere.
It remains excluded from nothing else, since the first assertion already permits the spinner keyframe
that lives there.

**Unchanged and reaffirmed by a fourth measurement:** every item in section 5's rejection list, the
twenty-four protected sentences, and the standing prohibition on a score, a health figure, a traffic
light, a green dot or a liveness pulse. Section 19 explains why the fourth reference strengthens that
prohibition rather than testing it.

---

## 19. What a control plane teaches that a marketing page cannot

This study was commissioned because three landing pages could not answer a question about a thousand
rows. Six things came back that no marketing page could have supplied, and they are worth separating
from everything above because they are the return on the exercise.

**1. The prohibition on a score, a dot and a traffic light is not conservatism. It is what a mature
control plane's own rules require of our data.**

This is the most valuable finding and it was not the expected one. A control plane does ship a status
dot, a gauge and coloured badges — the very devices this console rejected three times. It also
documents the preconditions for each, and **our data fails them.**

- Its status dot is scoped to **one lifecycle with a closed enum**, and the documentation forbids
  repurposing it for any other kind of status. Its dot animates only while the system holds a
  non-terminal state, and the documentation says explicitly not to flash colour through transitional
  states on a polling tick — **only when the stored state changes.** `runs-table.tsx:159-168` refuses
  a liveness dot because nothing in our data distinguishes a run parked on the customer's CI from one
  that has died. That is precisely the stored-state transition the rule requires and we do not have.
  **The reference system's own rule forbids the dot for our data.**
- Its gauge requires **a 0-100 ratio against a fixed maximum where the comparison is the point**, and
  the documentation forbids inventing gauge-only thresholds — the numeric breakpoints must already
  exist elsewhere in the product. A composite health figure has no fixed maximum and no pre-existing
  breakpoints. `ScreenLimitsCard` exists because our denominators are the thing we cannot state.
  **The rule forbids the figure for our data.**
- Its badge, which is where colour does carry meaning, is keyed to **a value the system recorded** —
  a terminal outcome from a closed vocabulary matching the canonical API term — and the documentation
  requires the text to be readable without the colour, forbids adding a checkmark or an X, and says
  one badge per row, because two side by side means the row needs a second column.

That last one is the interesting boundary. **Sync already permits exactly what that permits.** Our
three licensed channels are run outcome, error state and absence, and all three are recorded values
from closed vocabularies. What we forbid is the *composite* and the *liveness claim*, and those are
the two the reference system also fences off behind preconditions. **We are not stricter than a mature
control plane. We have data that fails its tests, and we said so.** A marketing page could never have
produced that argument, because a marketing page has no state to render.

**2. A dense surface stays legible by refusing to rank its own fields.** Every cell in every measured
table is the same size, the same weight and the same ink. The temptation on a nine-column evidence
table is to make the important column louder; the measurement says a control plane does the opposite
and lets the column position and the cell's contents carry it. A screenful of twenty elements never
generates that problem, so no landing page can teach it.

**3. Hierarchy at density is bought with weight and leading, not with size.** A heading at 14px in the
heading weight on the same line box as the row beneath it costs zero rows. This is the direct answer
to the 2.0:1 experienced range measured in section 2, and it is a better answer than adding steps.
Landing pages solve hierarchy with a 3x size jump because they have the room; we do not, and neither
does a control plane.

**4. A control plane's frame does no work, and the spacing ratio the landing pages agreed on inverts.**
Frame at 24px, dominant gap at 8px, dominant paddings at 2, 6 and 12. Three references agreed on 4.7
to 7.2 : 1 and all three were measuring a composition that had to hold its own edge. A console's edge
is held by chrome. This one measurement saves a row on every panel on every screen.

**5. Interaction feedback is a density requirement, not decoration — and it is the only motion finding
that changed.** The landing pages measured `transition-duration: 0s` on their primary action and this
plan turned that into a prohibition. The reason it did not survive is countable: **that Geist page
carried 47 controls.** When the pointer crosses several controls to reach one, an instant fill change
is flicker and a 150ms ease is tracking. Everything else about the motion finding held — nothing
moves, nothing scales, nothing decorative runs, and the only thing animating at rest across a
976-element page was a spinner reporting a genuine wait. **The prohibition on motion was right about
what it forbade and wrong about the mechanism, and only a page with dozens of controls could show
that.**

**6. Absence is a first-class design problem with more than one answer, and a marketing page has no
absences.** Six documented empty states for six different reasons a list is empty; a required
typographic mark for a value that is unknown or not applicable, with substitutes explicitly banned; a
rule that an indeterminate figure must be labelled so it does not read as zero. This console has an
absence channel and an honesty discipline and had never seen another system treat nothing as a design
surface with its own vocabulary. **Ours has to be richer than theirs, because the provenance rung
distinguishes kinds of nothing that their model collapses** — and that is a place where the console's
core idea gives it something a general-purpose control plane does not have.

**And the limit, stated as plainly as section 12 stated its own.** This reference is a published
system and a set of component surfaces. Its dashboard is behind authentication and was not measured.
So the numbers above are of a documentation site built by the people who built the control plane,
using the control plane's own primitives at the control plane's own density — which is much closer to
our register than three landing pages, and is still not a screen holding a thousand rows. The last
mile remains ours, and it remains unmeasured until we render one.

---

## 20. Added 2026-08-06 — two dense applications, read as source

Sections 1 through 19 rest on four measured surfaces: three landing pages, whose only data-dense
artifacts were flat PNGs, and one published design system whose running dashboard is behind
authentication. Both limitations were stated plainly at the time. Section 12 said every claim about
a thousand rows was inference from marketing layout; section 19 said its numbers came from a
documentation site rather than an operational screen.

This study closes both gaps by a different method. Nothing here was measured in a browser. Two
open-source dense applications were **cloned and read as source**, which answers two questions no
rendered page can: how a dense surface is *built*, and what a mature team wrote down about *why*.

`.claude/rules/interface-originality.md` binds here as it binds above, and it is worth restating
what that rule permits, because reading source sits closer to its edge than measuring a page did.
Nothing below is a layout, a component composition, a colour system or a phrase. What is taken is
mechanism and stated reasoning — how a count is bounded, where pagination state lives, what
precondition a component's own documentation attaches to it. Every recommendation is restated as a
problem from our operator, our graph or our product position, and the two places where a finding
survived only because somebody else does it are named and demoted.

### 20.1 What was read, and how deeply

| | `getsentry/sentry` | `grafana/grafana` |
|---|---|---|
| Why it was chosen | the closest analog that exists — findings, triage, evidence, "why do we think this" | dense operational surfaces, and a table with a published rationale |
| Read | its issue stream end to end, its `components/core` design system, its written principles, and the server-side pagination it rests on | its table package end to end — the data grid, the hooks, the cells, the constants — plus its empty-state component and documentation |
| Depth | source, not skim: the stream's state machine, the paginator's SQL, four component primitives, three principle documents | source, not skim: the filter/sort/paginate hook pipeline, row-height derivation, three cell renderers |

`supabase/supabase`, `PostHog/posthog` and `tremorlabs/tremor` were not read. The brief said two read
properly beat five skimmed, and after Sentry's paginator turned up the answer to the performance
question in section 24, spending the remaining budget on breadth would have bought less than
reading that mechanism to the bottom. That is a choice and it is recorded as one.

Citations below are into the cloned trees. Sentry paths are relative to its repository root;
Grafana paths likewise.

---

## 21. The questions, answered

### 21.1 The table at ten thousand rows: virtualised or paginated

**Both applications do both, and the variable that decides is not the row count.** It is whether
the data is already in the client and whether the result set is bounded.

**Sentry paginates and does not virtualise its issue stream.** `static/app/views/issueList/overview.tsx:78`
sets `const MAX_ITEMS = 25;`, and that is the page. The list is rendered as plain rows —
`static/app/views/issueList/groupListBody.tsx:128-140` maps the ids straight into components with no
windowing anywhere in the path. Twenty-five DOM rows need no virtualiser.

**It virtualises exactly where the result set is unbounded.** `static/app/components/infiniteTable/infiniteTable.tsx:89-94`
uses `useVirtualizer` with `overscan: 5`, and the type of the thing it is windowing is the tell:
its `Body` takes a `UseInfiniteQueryResult` (`:84`). Virtualisation is coupled to infinite scroll,
not to size. Where the page is bounded, the bound is the answer; where the stream has no bound,
the window is.

**Grafana virtualises because its data is already client-side.** Its table renders through
`@grafana/react-data-grid` (`packages/grafana-ui/src/components/Table/TableNG/TableDataGrid.tsx:6`),
which windows rows and columns. A Grafana panel has already received its whole data frame from a
query; there is no server page to ask for. So it windows, and it *additionally* offers pagination
as a display option over the same in-memory rows.

**The rule this yields, stated for us.** The console's transport already returns pages —
`whats_at_risk` takes `limit` and `offset` and the graph surface has "paginate every list" as a
frozen rule. That puts every screen we have in Sentry's first case: bounded page, no virtualiser
needed. **Do not build a virtualiser.** It is the answer to a problem we have deliberately arranged
not to have, and it costs a measurement layer, a scroll-restoration bug class and a printing
regression. The one screen that could earn one is a future streaming log view, and there is none.

### 21.2 How sorting, filtering and a server-paginated fetch stay consistent

This was named as the thing we have not built and are about to. Both applications solve it, and
they solve it differently, for a reason that is visible in the code.

**Sentry: every state change except a page change discards the cursor.** The mechanism is one
expression. `static/app/views/issueList/overview.tsx:679-696` defines `transitionTo`, and its first
line is:

```
...omit(location.query, ['page', 'cursor']),
```

Every caller that changes a filter, a search, a sort or a stats period goes through it —
`onSearch` (`:699-706`), `onSortChange` (`:708-724`), `onSelectStatsPeriod` (`:740-748`) — and every
one of them therefore drops the cursor on the floor. The single caller that *keeps* it is
`onCursorChange` (`:723-739`), which passes the new cursor back in explicitly, and which additionally
resets to no cursor at all when the page index falls to zero or below (`:732-736`).

The invariant that expression encodes is worth naming, because it is the whole answer: **a cursor
is only meaningful relative to a fixed sort and a fixed filter.** A cursor is a position in an
ordering. Change the ordering or the population and the position denotes nothing, so it is not
carried forward — it is dropped, and the reader lands on page one of the new question.

**Grafana: an ordered pure pipeline, and the page is clamped rather than dropped.** Its hooks
compose in one direction — `useFilteredRows` (`packages/grafana-ui/src/components/Table/TableNG/hooks.ts:59`),
then `useSortedRows` (`:98`), then `usePaginatedRows` (`:163`) — each taking the previous stage's rows
as input. Consistency is structural: sorting cannot disagree with filtering because it can only see
what filtering returned. The page index is separate state, and when a filter shrinks the population
the page can point past the end, so there is an explicit guard at `:250-253` that resets to the last
valid page rather than to the first.

**Which we take, and why.** Sentry's, with Grafana's ordering as the internal discipline. Our
pagination offset is in the URL by deliberate decision, so a browser Back does not lose the
reader's place — that decision is confirmed by the more mature of the two systems and should not be
revisited. What it needs beside it is the discard rule, which we do not have written down anywhere:
**changing a filter, a severity, a path or a sort clears the offset; only a page control preserves
it.** Grafana's clamp is the right shape for a client-side table over a fixed frame and the wrong
shape for us, because our filter change is a new server query whose total we do not know until it
returns — clamping would require a round trip to learn what to clamp to.

### 21.3 Where filter, sort and pagination state lives

**Sentry puts all of it in the URL, and nothing else.** There is no store. `overview.tsx:144`
reads `useLocation()`, `:146` takes `useNavigate()`, and every state transition is a navigation
(`:693-696`). The cursor is read out of `location.query.cursor` at request-assembly time
(`:287-290`); the sort and the search live in the same object. `queryCount` is `useState`
(`:159`) — but it is *derived from the response*, not user intent, which is the line the codebase
draws: **intent goes in the URL, response metadata goes in component state.**

**Grafana puts none of it in the URL.** `useSortedRows` holds `sortColumns` in `useState`
(`hooks.ts:120`); `useFilteredRows` holds `filter` the same way (`:60`). That is correct for its
context and not for ours — a Grafana table is one panel among many on a dashboard whose own state
is the saved dashboard JSON, and a URL cannot hold twelve panels' sort orders without becoming
unreadable.

**How far a mature app takes it, which was the question asked.** Further than we do, and the
extra distance is the interesting part. Sentry's URL carries the *search query itself* — a full
structured query string — not merely a filter selection. And two details show the discipline is
deliberate rather than incidental: `getEndpointParams` omits `sort` from the URL when it equals the
default (`overview.tsx:267-269`), and `transitionTo` deletes a sort that is not valid for the
current query (`:685-690`). So the URL holds the *difference from default*, not the whole state.
That keeps a shared link short and, more usefully, means a default view has one canonical URL
rather than several that render identically.

### 21.4 Density mechanics

Read from Sentry's table primitive, `static/app/components/tables/simpleTable/index.tsx`.

| | Sentry, in source | Geist, measured (section 13.3) | Ours today |
|---|---|---|---|
| Header row height | `min-height: 40px` (`:109`) | 36px | 40px |
| Header ink | `content.secondary` (`:153`) — **the same as the body** | secondary, same as body | `text-foreground` |
| Header weight | `sans.medium` (`:151`) | 500 | `font-medium` |
| Header capitals | `text-transform: none`, set explicitly (`:111`) | none | none |
| Rule under header | `1px solid border.primary` (`:104`) | one, 1px | present |
| Rules between body rows | **`1px solid border.secondary` on all but the last** (`:126-129`) | **none** | none |
| Row emphasis | none — no cell is ranked | none | none |
| Cell padding | `lg xl` on every cell, header and body alike (`:89`) | 10/8 body, 0/8 header | 8px inline, 10px block, identical on both |

Four sentences are worth pulling out of that table.

**Both systems separate the header by weight and a rule, and neither spends ink on it.** Section 18
already revised Task 13 on exactly this and Task 13 landed it. It is now confirmed by a second
independent implementation, and the confirmation is stronger than the measurement was, because here
the ink token is *named* in source: the header cell explicitly selects `content.secondary`, the same
token the body uses. That is a choice, not a coincidence of rendering.

**Sentry rules between body rows and Geist does not.** This is a real disagreement between two
mature control planes and section 22.3 rules on it.

**The sorted column's header changes ink, and this is the best single idea in the file.**
`simpleTable/index.tsx:169-171`:

```
&[aria-sort] {
  color: ${p => p.theme.tokens.content.primary};
}
```

The one place primary ink is spent in the entire table is the column the table is currently ordered
by. Ink is not carrying importance, which would be a judgement; it is carrying **a fact the system
recorded about its own current state** — which ordering produced these rows in this sequence. That
passes our own test cleanly and section 23 adopts it.

**Column alignment is `subgrid`, not a `<table>` and not measurement.** The panel is one grid
(`:96`), and the header and every row declare `grid-template-columns: subgrid; grid-column: 1 / -1`
(`:112-114`, `:120-122`). Columns line up because they are the same grid tracks. This matters
beyond tidiness: it is what lets a row be an arbitrary component rather than a `<tr>`, which is the
precondition for ever windowing a list without the columns drifting.

### 21.5 Empty, loading and error, per surface

**Our console distinguishes four kinds of nothing and treats that as load-bearing. Sentry
distinguishes six, and pays a network round trip to tell two of them apart.**

The dispatcher is `static/app/views/issueList/noGroupsHandler/index.tsx`. Its branches:

- `:117-119` — still deciding which kind of empty this is: a loading indicator.
- `:121-123` — the decision itself failed: fall through to the generic empty rather than assert.
- `:125-133` — the project has never sent an event: an onboarding surface.
- `:166-173` — the default query returned nothing: nothing is wrong, everything is resolved.
- `:175-184` — the review queue is empty: a third message again.
- `:194` — a filtered query matched nothing.

The load-bearing detail is `:90-100`. To distinguish "never configured" from "configured and
currently clear", the component **issues a second HTTP request** to `/sent-first-event/`. It cannot
tell those two apart from the list response, and rather than guess it asks. That is the same
discipline our absence channel encodes, arrived at independently and paid for in latency.

**And it is where our core idea gives us something they do not have.** The provenance rung tells us
from the row itself whether a binding was never observed or observed and empty. Sentry needs a round
trip for the equivalent distinction because its data does not carry it. **We get for free what a
mature control plane pays for**, and that is worth writing down as a strength rather than treated as
mere compliance.

**Grafana types the same problem into the component signature.** Its `EmptyState` takes
`variant: 'call-to-action' | 'not-found' | 'completed'` as a **required** prop
(`packages/grafana-ui/src/components/EmptyState/EmptyState.tsx:34,46-54`), and its documentation
assigns each a cause: never created, filter matched nothing, all work cleared
(`EmptyState.mdx`, "When to use"). A required discriminated variant is the mechanism, and it is
better than a convention because an agent cannot render a generic empty by omission.

**The loading state is sized to the loaded state.** `groupListBody.tsx:63-83` renders exactly
`pageSize` skeleton rows. The page does not reflow when data arrives. Grafana does the analogous
thing for its scroll geometry by estimating an average row height over the first hundred rows
(`hooks.ts:188-199`).

**Error is a distinct branch with a retry, never an empty.** `groupListBody.tsx:113-115` returns
`<LoadingError onRetry={refetchGroups} />`. A failed read is never rendered as "nothing here" — with
the one honest exception at `noGroupsHandler/index.tsx:121-123`, where the request that failed was
the *disambiguating* one, and falling back to the less specific empty is the conservative answer.

### 21.6 The component inventory a control plane actually needs

Section 16.1 listed six primitives we lack, derived from Geist's 78. Reading two more inventories
changes that list in three places and confirms the rest.

**Confirmed and unchanged:** the empty state with variants (both systems ship one, Grafana with a
required variant prop), the qualification notice, the definition list, the verbatim value.

**Added, and it is cheap.** A **sortable header cell** that owns `aria-sort` — Sentry has
`static/app/components/tables/sortableHeaderCell.tsx` as a primitive rather than a per-table
concern, which is what makes the sorted-column ink rule enforceable in one place instead of eleven.
A **column-resize hook** is deliberately *not* added: `static/app/components/tables/useColumnResize.tsx`
exists there and we have no argument for it from our operator.

**Demoted: the middle truncation.** Section 16.1 argued for it because a file path truncated at the
end loses the filename. Neither application ships one. Sentry's cell instead sets
`overflow: hidden` and lets the cell clip (`simpleTable/index.tsx:89`); our own `TableCell` already
chose better, wrapping on `break-words` so nothing is lost at all. A truncation primitive solves a
problem we have already solved differently, and it should come off the list rather than sit on it
as a permanent unbuilt obligation.

**One primitive neither list had, and it is the one we most need.** Sentry's
`InteractionStateLayer` (`static/app/components/core/interactionStateLayer/interactionStateLayer.tsx`)
is a single absolutely-positioned overlay that owns **every** interaction state of whatever it sits
inside: rest at `opacity: 0` (`:62`), hover at 0.06 (`:68`), pressed at 0.09 (`:82`), and
`aria-selected`/`aria-expanded` at the same 0.09 (`:92-93`). It inherits `border-radius` and
`border` from its parent (`:52-53`) and its fill is `currentcolor` (`:58`). Section 22.2 takes this
up, because it contradicts a ruling we have already landed.

---

## 22. Where source contradicts the earlier studies, and which I trust

Six contradictions. In four cases source wins, in one our landed decision wins, and one is a genuine
standoff that we should decide on our own grounds.

### 22.1 Motion: the rule is a frequency test, not a duration

**Section 8 measured `transition-duration: 0s` on three landing pages and section 11 turned it into
a prohibition. Section 15.2 then reversed that on Geist's 0.15s ease and called the reason "a dense
surface has 47 controls". Both were reaching for a rule and neither found it.**

Sentry has it written down. `static/app/components/core/principles/motion/motion.mdx:39`:

> **Frequent interactions**, such as keyboard interactions and repetitive daily workflows, should
> avoid animation all together. Likewise, when the **speed** of an interaction is critical, motion
> should be applied carefully to maintain the perceived performance.

And the codebase obeys it where it matters most: `InteractionStateLayer` — the primitive that
handles hover on every row, every button and every menu item in the product — **declares no
transition at all.** The opacity step from 0 to 0.06 is instant. Meanwhile the same system publishes
a full motion token set with named durations of 120ms, 160ms and 240ms (`motion.mdx:100-102`) and
spends them on overlays, modals and toasts.

**I trust this over both earlier rulings, and it is strictly better than either.** The variable is
not the page's control count and not a magic duration. It is **how often the operator crosses this
thing**. A row hover on a nine-column evidence table is the most frequent interaction in the console
and takes no transition; a dialog opening is rare and may take one. That rule is decidable by
whoever is writing the component, which "0s everywhere" and "150ms because dense" both were not.

It also resolves the disagreement between Geist and Sentry rather than picking a side. Geist eases
the *fill of a button*; Sentry refuses to ease the *hover of a row*. Under the frequency test both
are right, and section 15.2's conclusion survives with a better reason than the one it was given.

### 22.2 The alpha overlay for interaction state: our ruling is too broad

**Section 18 and `DESIGN.md`'s *Surface ramp: depth and state* rule that state steps are named
surface values and never an alpha overlay, because an alpha composites differently against each
depth step and therefore means several things.**

Sentry does the opposite, deliberately, and its reason is not one we considered: the overlay's fill
is `currentcolor` (`interactionStateLayer.tsx:58`). It is not an alpha of a fixed grey. It is an
alpha of *whatever ink the element already carries*, so it is always a step toward the foreground,
on any surface, in any theme, at any nesting depth — one declaration, one meaning, no token per
combination. It inherits radius and border from its parent, so it fits a pill, a card corner and a
square cell without knowing which it is in.

**I trust our landed ruling for our tree, and the reason is that our defect was never the alpha.**
Section 2 found `hover:bg-muted/50` spelled inline in a primitive, and the surrounding problem was
that eight feature screens contained one authored interaction between them because nobody had a
state vocabulary to reach for. A named surface step fixes that with two enumerable values, because
after Task 12's reallocation we have exactly two depth steps for state to sit on — the composition
ambiguity that motivated the ban barely exists at two.

**But the ruling as written forbids more than it should, and should be narrowed rather than kept.**
What must stay banned is an *ad-hoc* alpha spelled at a call site. A single primitive owning all
four states, with a `currentcolor` fill, is a legitimate construction with a real advantage, and a
future agent reading `DESIGN.md` will find it forbidden with a reason that does not apply to what
they are doing. Section 26 revises the wording. This is the one place in this study where a landed
decision needs a correction rather than a confirmation.

### 22.3 Rules between body rows: a standoff, and we keep ours

Geist, measured: no rules between body rows (section 13.3). Sentry, in source: a rule between every
body row, at `border.secondary` — a **weaker token than the header's `border.primary`**
(`simpleTable/index.tsx:104` against `:126-129`).

Neither is a mistake. Sentry's rows carry a graph sparkline, an assignee avatar and a multi-line
title, so rows are tall and visually busy and a rule keeps them from bleeding into each other.
Geist's are single-line values at 40px.

**I trust neither for us and we should keep what we have**, which is Geist's shape — a header rule
and nothing between rows. The deciding fact is ours: our rows are single-line values at 36px, which
is Geist's case and not Sentry's. What transfers is the *graded* idea rather than the presence of
the rule: **when a rule is drawn between rows it must be weaker than the rule under the header**, so
the header still reads as the strongest horizontal division. If any of our tables ever grows a
multi-line row, that is the rule to apply, and it is now written down rather than rediscovered.

### 22.4 Row height derived from type, or type fitted into a row height

**Section 18 asked for a row-height scale on the argument that a control dropped into a cell must
not change the row, and Task 12 landed one — `DESIGN.md`'s *Row height*, three steps at 32/36/40,
with the row chosen first and the padding derived from it.**

Grafana does the opposite. `packages/grafana-ui/src/components/Table/TableNG/utils.ts:168` computes
the default row height as `CELL_PADDING * 2 + theme.typography.fontSize * theme.typography.body.lineHeight`
— padding plus type, exactly the derivation `web/src/components/ui/table.tsx:68-72` describes and
`DESIGN.md` replaced.

**But Grafana also publishes named steps beside that formula**, and they are the interesting part:
`utils.ts:159-167` returns **36 for small, 42 for medium, 48 for large**. So the derived value is the
fallback, and the named steps are what a user actually selects.

**I trust our landed decision, and a third independent 36 is why.** Geist's dense row is 40 with 36
as its middle control step; Grafana's small row is 36; our `row-md` is 36. Three systems, three
derivations, one number for a dense single-line row. That is about as much corroboration as this
kind of question admits. Grafana additionally supplies the failure mode our ordering avoids: because
its height is derived from content, it needs `MAX_CELL_HEIGHT: 48` (`TableNG/constants.ts:13`) and a
clamping apparatus inside the cell renderers to stop contents stretching with the row —
`Cells/BarGaugeCell.tsx:49-50` is one, with the comment "clamp the height of the gauge so it isn't
stretched for large rows". Deriving the row from the content means every cell renderer must then
defend itself against the row.

### 22.5 The "two ink levels" invariant needs a third category, and it is not text

Sections 8 and 14 concluded: two working ink levels plus one accent, never three. Sentry's token
documentation splits the same job three ways
(`static/app/components/core/principles/tokens/tokens.mdx`, "Categories"): `content` paints "text
and icons which need to stand out the most", and **`graphics` paints "icons and other graphical
elements which don't need to stand out as much as `content` tokens"**, with `border` a third
category again.

**I trust this as a refinement rather than a contradiction, and it is one we should adopt because we
have the bug it prevents.** The invariant holds for *text*: two levels, and one of them is the
default. What it got wrong is treating an icon as text. An icon at the secondary text ink is
optically louder than the text beside it, because it is a solid shape rather than a stroke pattern.
Naming a separate graphics level is how a system stops an agent reaching for the text token for a
chevron. This costs no new value in our ramp — it is an allocation and a sentence, which is exactly
what transfer item 1 in section 16 asked for and was not specific about.

### 22.6 What the landing pages could not have shown, and got backwards

Section 8 called "at most one authored transition in an entire page" an invariant of dense
considered interfaces, from stylesheet counts of 0, 0 and 1. Section 15.2 already broke it on
Geist's 77. Sentry publishes five easing curves and three durations as tokens and spends them
throughout.

The correction is complete and it is section 22.1's: the count was never the variable. Three landing
pages had near-zero transitions because a landing page has near-zero repeated interactions, which is
the *same rule* producing the opposite number. The invariant and its refutation are one principle
read at two densities — and this is precisely the class of error section 12 warned about when it
said every claim about a thousand rows was inference from marketing layout.

---

## 23. What transfers, in our own terms

Five things. Each is stated as a problem we have and each survives the rule's test — it can be
justified from the operator, the graph or the product position without pointing at anybody's screen.

**1. Bound every count in SQL, and let the bound reach the screen.** This is section 24 and it is
the largest item in this study.

**2. Changing what is asked clears where you are.** Our pagination offset is in the URL by
deliberate decision and that decision is confirmed. What is missing beside it is the discard rule:
an offset is a position in an ordering, so a change of filter, severity, path or sort must clear it.
Justified from the operator without reference to anyone: a reviewer who narrows to one vendor and
lands on page four of a three-page result has been handed an empty screen by the console's own
bookkeeping, and will read it as "no findings" — which is a **false absence**, on a console whose
entire position is that it distinguishes kinds of absence correctly. This is not a polish item; it
is an honesty defect waiting for its first filter.

**3. Ink marks which column produced this ordering.** Our tables sort, and a reader arriving at a
screenful of rows cannot see from the rows which column put them in that sequence. That is a fact
the system holds and does not render, which is the same defect class as an unattributed rung. One
step of ink on one header cell states it, spends no vertical space, and asserts nothing — the
ordering is recorded, not judged. This is the single cheapest thing in this study.

**4. A separate ink level for graphics, so an icon stops borrowing the text token.** Two text levels
stand. An icon is not text, and rendering it at the text ink makes it louder than the text it
accompanies. This is an allocation inside the nine-step ramp and a rule in `DESIGN.md`, not a value.

**5. Motion is decided by frequency.** The console's rule becomes: **a surface the operator crosses
repeatedly takes no transition; a surface they meet occasionally may take one.** This replaces both
"never" and "150ms because dense" with a test whoever writes the component can apply. It also
explains our own tree back to us — `TableRow`'s transition on navigable rows is the frequent case
and should go, while the theme control's press feedback is the rare case and stays.

---

## 24. The number that was the prize

Our fleet screen and vendor findings table measured **9–19s and 4.6s** at ten thousand call sites,
because `/api/overview` and `whats_at_risk` read every open finding. The binding surface, which got
real SQL bounds, measured **28ms**. The brief said that if source showed how a mature application
makes the first two behave like the third, that would be the most valuable thing to bring back.

It does, the mechanism is four files deep, and it fits this console better than it fits the
application it came from.

### 24.1 The mechanism

**The count is a `COUNT(*)` over a bounded subquery, never over the table.**
`src/sentry/api/paginator.py:30-48`:

```python
def count_hits(queryset: Any, max_hits: int) -> int:
    if not max_hits:
        return 0
    hits_query = queryset.values()[:max_hits].query
    hits_query.clear_select_clause()
    hits_query.add_fields(["id"])
    hits_query.clear_ordering(force=True, clear_default=True)
    ...
    count_sql = "SELECT COUNT(*) FROM (" + h_sql + ") as t"
```

Four separate economies in nine lines, and each is independently worth having. The result set is
**truncated with a LIMIT before it is counted**, so the database stops at `max_hits` however many
rows match. The select list is **stripped to the primary key**, so no column is materialised and no
`select_related` join runs. The **ordering is cleared**, which removes a sort the count does not
need. And it runs against a **read replica** (`:43`).

**The bound has a default and it is small.** `paginator.py:26`: `MAX_HITS_LIMIT = 1000`. Ten
thousand matching rows cost the same as one thousand.

**The bound travels to the client alongside the count.** `src/sentry/api/base.py:502-505` emits both
as response headers:

```python
if cursor_result.hits is not None:
    response["X-Hits"] = cursor_result.hits
if cursor_result.max_hits is not None:
    response["X-Max-Hits"] = cursor_result.max_hits
```

**And the interface renders the bound honestly rather than hiding it.**
`static/app/components/queryCount.tsx:18`:

```tsx
const countOrMax = defined(count) && defined(max) && count >= max ? `${max}+` : count;
```

The issue stream reads both headers (`overview.tsx:478-480`), stores them (`:159-160`), and passes
the bound down to that component (`:1016`).

**One more piece, and it is a guard rather than an optimisation.** `base.py:487-494` inspects every
`GET` response: if the body is a list, and the endpoint is not on an explicit allowlist, and the
response carries no pagination, it **raises**. The exception's own message (`paginator.py:56-58`)
says a list response must be paginated "as lack of pagination can break the product in the future
due to eventual growth". An unpaginated list endpoint is a bug that fails loudly rather than a
latency regression that shows up in a screenshot six months later.

### 24.2 What it means for `/api/overview`

`src/sync/api/app.py:150-156` is the defect in five lines. It probes for the total, then asks for
that many rows, then counts them by vendor **in a Python loop over materialised rows**:

```python
probe = surface.whats_at_risk(limit=1, offset=0)
page = surface.whats_at_risk(limit=max(probe["total"], 1), offset=0)
vendor_counts: dict[str, int] = {}
for row in page["items"]:
    vendor = row["vendor"]
    vendor_counts[vendor] = vendor_counts.get(vendor, 0) + 1
```

The comment above it is careful and correct about the thing it was written to solve — it bounds the
*call count* at two rather than looping `next_offset`. It is bounding the wrong axis. Two calls that
each materialise ten thousand rows is the 9–19 seconds.

Three changes follow, and they are the same three the binding surface already made to reach 28ms.

- **The vendor distribution is a `GROUP BY`.** "How many open findings per vendor" is one aggregate
  query returning one row per vendor. It is never a loop over findings, because the number of
  vendors does not grow with the number of findings and the number of findings does.
- **`total` is bounded and says so.** A count computed by materialising every row is precise and
  slow; a count that stops at a stated ceiling is a fact about where the system stopped looking.
  **The second is the more honest of the two on this console**, which is worth making explicit
  rather than treating the bound as a regrettable compromise. "10,000" rendered after nineteen
  seconds of scanning implies a completeness the operator has no way to check. "1,000+" states a
  limit the system actually enforced. That is the same register as every other sentence this plan
  protects, and it is why this mechanism fits here better than it fits Sentry.
- **The ceiling and the marker are one decision.** If the transport bounds a count it must return
  the bound, and if the interface receives a bound it must render the difference between "1,000" and
  "at least 1,000". A bounded count rendered as a bare number is a falsehood the transport
  introduced and the interface completed.

**Where the honesty discipline bites harder than Sentry's.** `severity_counts` on the same payload
is a distribution, and a distribution truncated at a global ceiling is **not** the distribution of
the population — it is the distribution of whichever thousand rows the ordering happened to reach. A
bounded total is honest; a bounded breakdown presented as a breakdown is not. So the roll-up is
computed as its own `GROUP BY` over the whole table, which is cheap for the same reason the vendor
distribution is, or it is not shown. It is never derived from a bounded page. `app.py:161-164`
already keeps these two as independently-computed reads for a related reason, and that decision
should be pointed at this one.

**The `_SCAN_LIMIT = 10_000` at `app.py:66` is this idea already present in our tree**, applied to
the wrong route. `finding_detail` fans through a page to find one finding by id and stops. The place
that needs a ceiling is the aggregate, not the lookup.

### 24.3 The ruling

**This is not a console task and it must not become one.** It is a change to `/api/overview`,
`whats_at_risk` and the severity roll-up — Python, SQL and the graph surface — and it is the
highest-value work this plan has identified since the amendment began. It is recorded here because
this is where the measurement was made and where the mechanism was found; **it should be proposed as
its own task after Task 16 lands**, ahead of the two primitives section 16.1 nominated.

The one piece of it that belongs to the console is the marker: whatever the transport decides, the
interface must render "at least N" distinctly from "N". That is an absence-channel question, it is
small, and section 26 puts it where it belongs.

---

## 25. What they do that we must not, with the precondition found in their source

Section 19 established that a mature control plane ships a status dot, a gauge and coloured badges
behind documented preconditions our data fails, and that we are therefore not stricter than the
field — we have data that fails its published tests and we said so. Reading two more implementations
strengthens that finding in a way measuring could not, because **source shows what happens to a
precondition when it meets a default.**

**The status dot's default is a repeating pulse.**
`static/app/components/core/statusIndicator/statusIndicator.mdx:18`: "By default, each dot renders
with a subtle muted background pulse behind it", and `:58`: "The background pulse repeats
continuously by default." The static form is opt-in, and the documentation states the condition for
it at `:79`:

> Reach for this when the indicator reflects a **known, persistent value** — such as a fixed `level`
> or `severity` from query parameters — rather than a change worth drawing attention to.

**Read as a precondition we fail, exactly as Geist's was, and it fails one step earlier.** A
continuously repeating pulse is a liveness claim — the strongest one an interface can make without
text. `runs-table.tsx:159-168` refuses a liveness dot because nothing in our data distinguishes a
run parked on the customer's CI from one that has died. Under this system's own framing, every
status we hold is a "known, persistent value" and therefore qualifies only for the static variant —
which is a dot carrying colour and nothing else, and our badge already carries the same recorded
value *as text*, legibly, without colour. So the precondition does not merely forbid the animated
dot: satisfying it strips the dot of everything the badge does not already do better.

**The gauge ships an invented threshold as its default.** Geist's documentation forbids inventing
gauge-only breakpoints — the numbers must already exist elsewhere in the product (section 19).
Grafana's table gauge cell, `packages/grafana-ui/src/components/Table/TableNG/Cells/BarGaugeCell.tsx:10-22`:

```ts
const defaultScale: ThresholdsConfig = {
  mode: ThresholdsMode.Absolute,
  steps: [
    { color: 'blue',  value: -Infinity },
    { color: 'green', value: 20 },
  ],
};
```

Blue below twenty, green at twenty and above, applied to **any** numeric column that has no
thresholds configured, with no argument anywhere for what twenty means. `:29-35` installs it
silently whenever the field lacks its own.

**This is the finding worth the most, because it refutes the standing counter-argument to our own
refusal, in someone else's source.** The objection to the prohibition on scores and traffic lights
is that it is over-cautious — that a responsible team would simply configure the thresholds
properly. Here is a responsible team, on a mature product, and the moment the device existed as a
cell type it acquired a default, and the default is a number with no meaning rendering as a colour
with two values. **The pattern does not degrade because someone was careless. It degrades because a
threshold-driven visual must render before anyone has supplied a threshold, and the only way to
render is to invent one.** Our data has no fixed maximum and no pre-existing breakpoints, so we
would be *starting* where Grafana's default ends.

**The coloured pill's colour is a hash of the string.**
`packages/grafana-ui/src/components/Table/TableNG/Cells/PillCell.tsx:87`:

```ts
return getColorByStringHash(colors, String(value));
```

Absent an explicit value mapping or a fixed colour, the pill's colour is a hash of the cell's text.
It carries **distinctness and nothing else** — two rows sharing a colour share a value, and that is
the whole of the information. It is not severity, not health, not outcome.

Two things follow. As a **concept it is defensible and we should say so**: a colour that means
"these are the same value" is a legitimate device, and it is not what our licensed channels do. As a
**pattern it is refused**, and the reason is that the reader cannot tell which kind of colour they
are looking at. On a console that already spends colour on run outcome, error state and absence,
adding a colour that means "distinct value" makes all four ambiguous — the reader would have to know
the column to know the encoding. `DESIGN.md` reserves the brand hue for links, focus and the current
node for the same reason, and this is that argument arriving from a different direction.

**The sparkline verdict was looked for and the finding is negative.** Grafana has
`TableNG/Cells/SparklineCell.tsx`, and it renders a series the panel's query returned — a real time
series with a real axis, drawn small. It is not a verdict. There is no cell in either codebase that
compresses a history into a direction or a judgement. The pattern the brief asked about does not
appear in either mature application, which is the strongest form of a negative finding: it is not
that we refuse something the field does; the field does not do it either.

**One thing to refuse that came from Sentry, and it is subtler than any of the above.**
`simpleTable/index.tsx:130-136` gives its row a `variant="faded"` that sets `opacity: 0.8` on every
cell. A whole row rendered quieter than its neighbours is a claim about that row — it says *this one
matters less* — carried by a channel with no text beside it and no way for the reader to learn what
produced it. That is precisely what the honesty discipline forbids, and it is far easier to add by
accident than a dot, because it looks like styling rather than like a verdict. **No row-level
de-emphasis.** If a row is less important, the column that makes it so is on screen and can say so
in words.

---

## 26. What this changes in Tasks 12 through 16

No task is renumbered, reordered or removed. Tasks 12 through 15 have landed (`b7ec856`, `2404850`,
`d516439`, `f1300d6`), so for those this section states **what should change next** rather than
rewriting a completed brief. Task 16 has not landed —
`tests/test_console_design_tokens.py` does not exist in the tree — so its brief is revised in place.

### After Task 12 — one correction and two additions to `DESIGN.md`

All three are documentation against an already-shipped token layer. None adds a value.

- **Correction.** *Surface ramp: depth and state* bans the alpha overlay outright. Narrow it to what
  the evidence supports: **an ad-hoc alpha spelled at a call site is banned; a single primitive
  owning all interaction states with a `currentcolor` fill is a legitimate alternative
  construction.** Record why we chose named steps anyway — two enumerable depth steps make the
  composition ambiguity the ban was written against nearly absent, and named values are greppable
  where an overlay is not. Section 22.2 carries the argument. Leave the shipped behaviour alone;
  this is a wording change so the next agent finds a reason that applies to what they are doing.
- **Addition — a graphics ink level.** Allocate an index of the existing nine-step ramp to icons and
  graphical elements, below the secondary text ink, and state the rule: an icon does not take a text
  token. No new value; an allocation and two sentences. Section 22.5.
- **Addition — the motion rule, as a frequency test.** `DESIGN.md` records: **a surface the operator
  crosses repeatedly takes no transition; a surface they meet occasionally may take one.** This
  replaces the standing "no new motion" framing with something decidable, and it is what Task 16's
  motion assertions should be read against. Section 22.1.

### After Task 13 — two changes to the table primitives, both small

- **The sorted column's header takes primary ink.** One selector on `TableHead`, keyed to
  `aria-sort`. It renders a recorded fact — which ordering produced this sequence — and asserts
  nothing. It also requires that `aria-sort` actually be set, which is the argument for lifting sort
  into a header-cell primitive rather than leaving it per table. Section 21.4.
- **Remove the transition from the navigable-row hover.** `web/src/components/ui/table.tsx:60`
  carries `data-[interactive=true]:transition-colors`. Under the frequency test a row hover is the
  most frequent interaction in the console and takes no transition. The hover itself stays where the
  row is navigable — that ruling is unchanged and was right.

### After Tasks 14 and 15 — one addition to the honesty audit, and one recorded rejection

**The addition is a new kind of nothing.** Section 24 will produce bounded counts. **The console
must render "at least N" distinctly from "N".** This is the absence channel gaining a fifth member:
not-applicable, not-observed, observed-and-empty, never-measured, and now **counted-to-a-limit**. It
is not a styling question — a bounded count rendered as a bare number is a false precision, which is
the exact failure the absence channel exists to prevent. Add it to the per-screen audit when the
transport change lands, not before.

**The rejection, recorded so it is not rediscovered.** Sentry rules between body rows and we should
not adopt it — our rows are single-line at 36px, which is the case where a header rule alone
suffices. What is worth writing into `DESIGN.md` is the conditional: **if a row ever becomes
multi-line, the rule between rows is weaker than the rule under the header.** Section 22.3.

**And one thing Tasks 14 and 15 should be re-audited for, because it is new.** Section 25's last
finding — no row-level de-emphasis. Neither task's audit looked for a whole row rendered at reduced
opacity, because nobody had seen one done deliberately before. Check the seven screens once.

### Task 16: the guard — revised in place

The brief stands as section 18 left it, with three changes to its assertion list and one addition.
Every assertion still has to be proved able to fail, as Step 4 requires.

- [ ] **Steps 1 through 3 — unchanged.** Spacing tokens, radius and type steps, nothing below
  `--text-meta`.
- [ ] **The first motion assertion — unchanged.** No `@keyframes` and no `animation` shorthand under
  `web/src/features/` or `web/src/layouts/`, and none in `web/src/index.css` beyond those already
  present. Four references and now two source trees agree that every keyframe in a control plane is
  an overlay entering or leaving, or something loading. Section 25 has strengthened its
  justification considerably: the reference system's status dot **pulses by default**, so the
  regression this guards against is not hypothetical — it is what happens when nobody rules it out.
- [ ] **The second motion assertion — narrowed.** Section 18 wrote it as "no transition on
  `transform`, `translate`, `scale`, `opacity` or `box-shadow` anywhere under `web/src/`". Keep the
  geometry half — nothing moves, confirmed on every reference measured and in both source trees.
  **Drop `opacity`**: the first assertion already covers the case that matters, and a legitimate
  loading state needs it. The frequency test from section 22.1 is the companion the guard cannot
  check and a reviewer must apply: a transition on a table row or a table cell is a defect
  regardless of which property it animates.
- [ ] **New assertion — no row-level de-emphasis.** Assert that no file under `web/src/` applies an
  opacity utility below 1 to a table row or its cells. Section 25's last finding is a claim about a
  row carried by a channel with no text beside it; it is trivially easy to add while believing it is
  styling; and it is the one honesty regression in this study that no existing guard would catch.
  Prove it fails.
- [ ] **Companion, and it is Python where it belongs.** Sentry's `MissingPaginationError`
  (`src/sentry/api/base.py:487-494`) raises when a `GET` returns a bare list with no pagination. We
  have "paginate every list" as a frozen rule of the graph surface and nothing that enforces it. A
  test over `src/sync/api/app.py`'s route table, asserting that every route returning a collection
  accepts `limit` and `offset`, is the same guard. It costs about an hour and belongs with the other
  Python assertions rather than in the frontend — which has no test runner by deliberate
  architectural decision, and this is a classification with a wrong answer.

### Unchanged and reaffirmed by two source trees

Every item in section 5's rejection list. The twenty-four protected sentences. The console stays
dark-only. And the standing prohibition on a score, a health figure, a traffic light, a green dot or
a liveness pulse — which section 25 has now supported from a second and a third independent
codebase, in a sharper form than section 19 could reach: **these devices do not fail only when the
data is unsuitable. They fail when a default has to exist**, and Grafana's blue-below-twenty is what
that failure looks like in production source.

### The limit of this study, stated as plainly as sections 12 and 19 stated theirs

Nothing here was rendered. These are two codebases read, not two products measured, and reading
tells you what a team decided rather than what the result feels like at nine columns and a thousand
rows. Two numbers in section 21.4 are declarations in source and were not confirmed against a
running page — Sentry's 40px header, and its cell padding, which is spelled as named tokens
(`padding="lg xl"`) whose resolved pixel values were not looked up, and which therefore should not
be compared against our 8/10 as though both were measurements. The last mile is still the last mile:
neither application was run, and this console has still never rendered a thousand rows. Section 24
is the one finding here that does not depend on that mile, because it is arithmetic about a query
plan rather than a judgement about a surface.
