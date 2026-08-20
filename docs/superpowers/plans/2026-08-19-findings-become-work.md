# Findings become work — the second half of the pipeline loop

**Owner direction, 2026-08-19.** *"the second half of the System workflow … the user interactions to
see what the system has detected and found and moved, the user can then select create ticket which
triggers the solution workflow and PR gen. This is also automatic for the type of finding/detection
it is, which we need to see fully built out in the demo repo."*

The first half is built and visible: `PipelineStrip` draws Index → Signal → Observe → Detect →
Remediate, `WorkflowGrid` gives every stage its doors, and every stage but the last has a screen
that answers it. **Remediate is the stage with no way in.** A reader can see what Sync found and
cannot do anything about it, and the console cannot say what Sync *would* do about it either.

---

## 1. The two gaps, stated precisely

**Gap 1 — a finding does not say what will happen to it.** The routing matrix
(`sync/route/matrix.py`) already decides that: seven change kinds by eight actions assign a tier —
`NO_PATCH`, `CODEMOD`, `TEMPLATED`, `AGENT`. It is the existing authority for *automatic for the
type of finding it is*, and it is invisible until a run has already started, because `_decide_tier`
is private to `sync/remediate/nodes.py` and fires inside `locate`. A reader looking at 24 findings
cannot tell the one that will be fixed by a mechanical edit from the one no edit in their repository
can resolve.

**Gap 2 — nothing turns a finding into work.** There is no ticket, no queue, and no record that a
human accepted a finding. `FindingPage` offers "Open the solution workflow", which *reads* a run
that some command line already started. The console can watch the loop and cannot enter it.

---

## 2. The ruling this plan is built on

**A ticket is a durable intent record. It is not a run trigger.**

`.claude/rules/console-dev-loop.md` is explicit: *"No route mutates the graph, triggers a run, or
touches a customer repository."* A button that started a remediation run would break all three at
once — a run clones the customer's repository, spends model tokens, and ends at an open pull
request. Two of the three things `autonomous-development.md` reserves for the human are on that
path, and neither becomes acceptable because a button was pressed.

So the write is split from the act:

```
console  ──POST /api/findings/{id}/ticket──▶  remediation_ticket row   (one row, no clone, no spend)
                                                      │
worker   ──sync work ──────────────────────────────────┘  claims open tickets, runs the graph,
                                                          opens the pull request
```

The API writes one row and answers with what it wrote, exactly as `POST /api/findings/{id}/dismissal`
and `PUT /api/repositories/{id}/context` already do. **`GraphSurface` gains no write method**, so
`test_no_route_reaches_past_the_read_surface` stays green on its own terms rather than being
relaxed — that test watches which surface methods a route reaches, and a ticket writer is an
injected callable beside the dismissal writer, not a surface call.

**This is recorded as reversible.** It widens a rule with one owner-ruled exception to a rule with
two, and the widening is the ticket write alone. If the owner wants the console to stay strictly
read-only, the console's button becomes a copied `sync work --finding <id>` command line and every
other part of this plan stands unchanged.

**What is not reversible is deliberately not built here.** No route runs the graph, and `sync work`
is a command a human types. The demo shows tickets in every state and runs that were started from a
terminal.

---

## 3. Why the tier can be previewed honestly

`tiered.routing_facts(change, site, repo=None)` is already a pure function over two graph rows, and
its own docstring settles the honesty question:

> *`repo` is optional because `nodes.py` previews the route at `locate`, before a clone is
> necessarily in hand. Without it the literal fact stays unknown, so that preview can only ever name
> a tier at least as expensive as the one `propose` settles on — a refinement, never a
> contradiction.*

That is the whole licence. A console preview computed with no clone is an **upper bound**: the run
may settle cheaper, never dearer. Row 4 (`request-field-removed-literal`) is the only row that turns
on the checkout, so it is the only row a preview can miss, and missing it costs a `CODEMOD` that
shows as `AGENT` — the safe direction.

**The screen says so.** Per `web/CLAUDE.md`, the claim is visible in the fewest honest words —
*before the clone is read* — and the argument sits behind the ⓘ. Three further nothings stay apart
and none is rendered as another:

| What the payload holds | What the screen says |
|---|---|
| `(None, None)` — the catalogue has no jurisdiction | *outside the routing table* — a deprecation's kind is not an oasdiff rule id |
| no catalogue loaded at all | *the routing table was not loaded* |
| a tier and the row that assigned it | the tier, and the row's name |

`(None, None)` is **not** tier −1, and `nodes.py`'s docstring says so in as many words. Collapsing
them would switch off the deprecation signal on screen.

---

## 4. Tasks

### Task 1 — The tier moves to `sync.route`, and is previewed

`_decide_tier` is private to `nodes.py` and this is its second use, which is the repository's own
threshold for factoring. `routing_facts` and `_passed_as_literal` move out of
`sync/remediate/tiered.py` into `sync/route/` beside the table they feed — `RoutingFacts` is already
declared there — and `decide_tier(change, site, catalogue, repo=None)` becomes the one entry point.
`nodes.py` and `tiered.py` call it.

**One derivation, two callers, no copy.** The alternative — a second implementation in the dashboard
— is the fact written twice that disagrees the first time a row changes, and this table's whole
point is that the row that decided is recorded.

**Verify.** The run's tier is unchanged on every existing remediation test; the preview with
`repo=None` never names a tier cheaper than the same call with a clone.

### Task 2 — The disposition reaches the console

`sync.dashboard.graph_views` gains the finding's disposition and `finding_detail` carries it: tier,
routing row, and which of the three nothings applies. `types.ts` declares it, and the type-contract
test holds the two sides together.

**Build.** A `Disposition` panel on `FindingPage` — what Sync will do about this finding, the row
that decided, and whether it needs a human. A tier tag in the closed vocabulary `components/tag.tsx`
already owns, legible without its colour, on the findings table.

**Refused.** A tier column that sorts. Tier is an ordinal over cost, not over urgency, and a table
sorted by it reads as a priority order Sync did not assign.

### Task 3 — The ticket

`remediation_ticket`, modelled on `finding_dismissal` row for row: **no foreign key to `finding`**,
for the reason that table's comment already records — `finding` is re-derived and a cascade would
delete every ticket a human opened on every scan. Finding ids are stable across re-derivation, so
the key still names the same finding.

Columns: `finding_id`, `origin` (`human` / `automatic`, a closed vocabulary), `opened_by`,
`tier_at_open`, `routing_row_at_open`, `created_at`, and the natural key
`UNIQUE (finding_id, created_at)`.

**`tier_at_open` is stored rather than re-derived on read.** The routing table changes; a ticket
opened under the old table and re-read under the new one would report a decision nobody took. This
is the same reason `migration_outcome.routing_row` exists.

**Verify.** A scan that truncates and rebuilds `finding` leaves every ticket standing —
`tests/test_scan_preserves_durable_rows.py` is where that guard already lives and where this one
goes.

### Task 4 — The route and the screen

`POST /api/findings/{id}/ticket` and `GET /api/tickets`, both through injected callables. The
console gets a **Tickets** screen under Remediate, and `FindingPage` gets the action.

**The button never claims a pull request.** It says a ticket was opened and names what happens next,
because between the row and the pull request sits a worker a human starts. A control that said
"Open a pull request" would be the console asserting something it cannot cause.

### Task 5 — Automatic, by the type of the finding

A policy function over the disposition: which findings open a ticket without a human. The tier is
the discriminator the matrix already computes, so the policy is a small table over it and not a
second judgement.

- `NO_PATCH` — **never**. No edit in the consumer's repository resolves it; a ticket would be work
  nobody can do.
- `CODEMOD` — **automatic**. The table asserts a mechanical edit with the graph facts to back it.
- `TEMPLATED` — **automatic**. The shape of the change is known; only the value is not.
- `AGENT` and the fall-through — **a human decides.** The fall-through direction is the matrix's
  safety property and it stays one here: an unrecognised change costs a human's attention rather
  than a model run nobody asked for.
- outside the table's jurisdiction — **a human decides**, and for the stated reason: no tier was
  assigned, so there is nothing to be automatic about.

**Every automatic ticket records that it was automatic and which row made it so**, so a policy that
turns out wrong is a query rather than an excavation.

### Task 6 — The worker, and the demo

`sync work` claims open tickets and runs the existing graph. It is where the clone, the spend and
the pull request live, and it is a command a human types.

Seed the demo through `scripts/seed_console.py`'s own writers so the console shows: findings of each
tier, tickets opened both ways, a ticket claimed by a run, and a run that reached a pull request.

---

## 5. What this plan refuses

- **A run triggered by an HTTP request.** §2.
- **A tier re-derived on read.** Task 3.
- **A preview that does not say it is a bound.** §3.
- **`(None, None)` rendered as tier −1.** §3. Two different facts, one of which is "the table has no
  jurisdiction here".
- **A priority score over findings.** `web/CLAUDE.md`'s standing refusal; the tier is cost, and
  severity is already its own recorded column.

---

## 6. Ledger

| # | Decision | Against | Why |
|---|---|---|---|
| 1 | A ticket is a row; the run stays with `sync work` | A route that starts the graph | A run clones the customer's repository, spends tokens and ends at a pull request — two of the three reserved actions sit on that path |
| 2 | The tier derivation moves to `sync.route` | A second copy in the dashboard | Second use is this repository's factoring threshold, and the recorded row is the thing that must not disagree with itself |
| 3 | The preview is labelled a pre-clone bound | Presenting it as the decision | Row 4 reads the checkout; without it the preview can only be dearer, never cheaper, and a bound presented as a decision is a claim the payload cannot support |
| 4 | `tier_at_open` is stored | Re-deriving it when the ticket is read | The routing table changes, and a ticket must report the decision that was actually taken |
| 5 | `AGENT` and the fall-through need a human | Automating everything with a tier | The fall-through direction is the matrix's safety property; automating it spends model runs on changes nothing recognised |
| 6 | No foreign key from the ticket to the finding | The obvious constraint | `finding` is re-derived per scan; the cascade would delete every ticket, which is the defect `finding_dismissal`'s comment already records |
