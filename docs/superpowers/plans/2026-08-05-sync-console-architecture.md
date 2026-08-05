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
| 9 | The layered bipartite diagram | ~1.5 days | **Loses.** See below. |

**What loses, explicitly:**

- **The layered bipartite SVG diagram (Task 9), even though its deferral condition is met.**
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
