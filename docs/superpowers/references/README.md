# External references — what to open, and when

The project's owner supplied these references across July 2026 with one instruction attached: consult
them per milestone, when their specific question comes up, rather than reading all of them at the
start. Loading every reference at every milestone is the failure the instruction exists to prevent —
most are irrelevant to an API-binding engine most of the time, and a reference consulted at the wrong
moment is a distraction wearing the costume of diligence.

The eight notes in [`notes/`](notes/) are the audits that resolved those references against Sync's
actual code, each read from its primary source on 2026-08-04. This index exists to honour the
instruction: it is arranged by the work you are doing, so you arrive with a problem and leave with one
file to open. Nobody reads a reference list end to end.

Two conventions carried by every note and worth knowing before you open one. Each claim is labelled
**VERIFIED** (primary source read that session), **REPORTED** (a secondary source asserts it), or
**INFERENCE** (the auditor's reasoning), and each note ends with a "could not verify" section. Treat
those labels as load-bearing; several notes turn on the difference.

## Which reference answers your question

| When you are… | Read this, for this question |
|---|---|
| Running a console improvement tick and the tick's own four questions all answer yes | [`impeccable-interface-quality.md`](notes/impeccable-interface-quality.md) §3 — which named, checkable interface defect the tick should fix next, instead of "taste" |
| Deciding what sits on a Solution Workflow node and what goes behind a click | [`competitor-interfaces.md`](notes/competitor-interfaces.md) §2.6, §3.5 — what competing tools actually put on screen when they have to convince a human their claim is true |
| Laying out the Finding detail view | [`competitor-interfaces.md`](notes/competitor-interfaces.md) §2.5, §2.7 — what order the evidence goes in, and what a provenance block must itemise |
| Writing the text of a findings-table row | [`competitor-interfaces.md`](notes/competitor-interfaces.md) §2.4, §2.8 — why a row should carry a consequence sentence and a human-memorable name rather than a detector id |
| About to propose a canvas, a generated diagram, or a confidence number on a finding | [`competitor-interfaces.md`](notes/competitor-interfaces.md) §3.1–§3.3 — the three that were evaluated and rejected, with the cost of each |
| Building a graph view that must stay responsive as the graph grows | [`code-graph-and-memory.md`](notes/code-graph-and-memory.md) §2c, §2d — how a working React 19 + Vite + Tailwind v4 dashboard handles level expansion and edges that leave the current level |
| Rendering freshness or provenance where the honest answer may be "unknown" | [`code-graph-and-memory.md`](notes/code-graph-and-memory.md) §2a, §2b — why freshness anchors to a commit hash rather than a timestamp, and how to rank and explain an unknown |
| Considering whether anything justifies widening the frozen MCP surface | [`code-graph-and-memory.md`](notes/code-graph-and-memory.md) §2a, §2e and §3 — one additive change qualifies, one default needs measuring, and the rest is difference that is merely different |
| Writing or revising an MCP tool description | [`pageindex-retrieval.md`](notes/pageindex-retrieval.md) §2.3 — why server-side enforcement and prose guidance answer different questions |
| Sizing a paginated response | [`code-graph-and-memory.md`](notes/code-graph-and-memory.md) §2e — the inline tool-result ceiling that silently undoes pagination, and why a row count is not a byte budget |
| Making `/api/overview` or `/api/findings/{id}` faster | [`pageindex-retrieval.md`](notes/pageindex-retrieval.md) §3.5 — an incidental finding: what `_SCAN_LIMIT` actually bounds, and the N+1 underneath both routes |
| Fielding a proposal to put model reasoning between an operator's click and the record | [`pageindex-retrieval.md`](notes/pageindex-retrieval.md) §3.5, §4 — the reason not to spend a day on it, and the two changes that would help instead |
| Interpolating vendor prose, compiler output or CI logs into a model prompt | [`pageindex-retrieval.md`](notes/pageindex-retrieval.md) §2.1 — the delimiter-framing helper, including the one line most hand-rolled versions omit, and the adjacent mistake that corrupts data |
| Storing an identifier a model proposed | [`pageindex-retrieval.md`](notes/pageindex-retrieval.md) §2.2 — nullify what cannot be validated against the source, rather than clamping or trusting it |
| Deciding what a remediation sweep must record so failed attempts survive a crash | [`alibaba-open-code-review.md`](notes/alibaba-open-code-review.md) §3.1 — a sealed denominator and a terminal state derived only from coverage; also what happens today to findings 3 through 10 when finding 2 raises |
| Making `abandon_reason` queryable rather than a regex-over-prose exercise | [`alibaba-open-code-review.md`](notes/alibaba-open-code-review.md) §3.2, [`competitor-interfaces.md`](notes/competitor-interfaces.md) §2.2, [`system-design-and-scalability.md`](notes/system-design-and-scalability.md) §2 (Uber) — three independent precedents for a closed class beside the free text, and the operations an abandoned attempt needs beyond "list" |
| Persisting subprocess output — `tsc` stderr, CI logs, provider errors | [`alibaba-open-code-review.md`](notes/alibaba-open-code-review.md) §3.3, §4.6 — a redaction floor whose step ordering matters, and why the policy on top of it must be stricter here |
| Serving the read-only API on localhost | [`alibaba-open-code-review.md`](notes/alibaba-open-code-review.md) §3.5 — how a page the operator merely visits can read that API, and the middleware that stops it |
| Recording why DETECT considered a call site and rejected it | [`alibaba-open-code-review.md`](notes/alibaba-open-code-review.md) §3.4 — a typed exclusion reason and a preview that spends no tokens |
| Choosing the next frontend concept for the console, or proposing a fifth view | [`roadmap-frontend-skills.md`](notes/roadmap-frontend-skills.md) §2 — the ordered list, and why the React roadmap rather than the frontend one is the checklist |
| Noticing the console has no tests | [`roadmap-frontend-skills.md`](notes/roadmap-frontend-skills.md) §2 item 1 — what to install, and which product claim is currently unproven by anything |
| Consuming the Starlette API from `web/` | [`roadmap-frontend-skills.md`](notes/roadmap-frontend-skills.md) §2 item 5 — why a tool whose thesis is silent contract drift should not consume its own API on an unchecked assertion |
| Starting the design-system or dark-mode slice | [`roadmap-frontend-skills.md`](notes/roadmap-frontend-skills.md) §2 item 6 for the pre-flight checklist; [`impeccable-interface-quality.md`](notes/impeccable-interface-quality.md) §4 for what that design system must *not* reach for |
| Picking the next vendor to write an adapter for | [`public-apis-and-hosting.md`](notes/public-apis-and-hosting.md) §2.1 — the machine-readable vendor-to-canonical-spec index that answers the first question, and why its cached specs must never be diffed |
| Building the adapter coverage view | [`public-apis-and-hosting.md`](notes/public-apis-and-hosting.md) §2.2 — hand-written or generated, and the record shape that makes it generated |
| Deciding where to deploy M4 and what it costs | [`public-apis-and-hosting.md`](notes/public-apis-and-hosting.md) §2.3 — three costed configurations, the recommendation, and the price to re-check before ordering |
| Facing fan-out: one vendor change touching fifty call sites or fifty repositories | [`system-design-and-scalability.md`](notes/system-design-and-scalability.md) §2 (Spotify Fleet Management) — the closest public analogue to Sync's patch-verify-PR tail, and the cohort mechanism |
| Arguing about caching, sharding, queues, or a second service | [`system-design-and-scalability.md`](notes/system-design-and-scalability.md) §2 — one sentence that settles it, and the arithmetic behind why dead-lettering a nine-stage pipeline is a rule rather than a nicety |

## Where two notes disagree

Two audits reaching different conclusions is information, not noise. Both of these are open and should
be decided rather than smoothed over.

**Whether the console should render a node-link graph at all.**
[`code-graph-and-memory.md`](notes/code-graph-and-memory.md) §2c–§2d recommends a two-stage lazy
layout with a per-container cache and portal nodes for cross-level edges, argued from a dashboard
running M4's exact stack, and names `elkjs` as the first dependency to look at.
[`competitor-interfaces.md`](notes/competitor-interfaces.md) §3.1 and §3.3 reject a spatial canvas and
a generated diagram, on the grounds that a fixed eight-node sequence wants a list with per-node state
and that a list is more honest about retries. The scopes are not identical — the first argues about
the navigable hierarchy, the second about the Solution Workflow view — but they pull in opposite
directions on whether a layout engine enters `web/` at all, and
[`roadmap-frontend-skills.md`](notes/roadmap-frontend-skills.md) separately puts tests and error
boundaries ahead of any new dependency. Decide the workflow view and the hierarchy views separately;
do not let one answer carry the other.

**Whether a dark rendering exists to audit.** [`impeccable-interface-quality.md`](notes/impeccable-interface-quality.md)
§3 question 2 asks for contrast to clear 4.5:1 "in both the light and dark rendering".
[`roadmap-frontend-skills.md`](notes/roadmap-frontend-skills.md) §1 VERIFIED that `web/src/index.css`
pins the console to one palette because the dark values do not exist yet, and §2 item 6 defers dark
mode to the design-system slice. The tick's question presumes a surface the console does not have.
Until that slice lands, answer it for the light rendering only, and do not read the missing half as a
pass.

Worth recording alongside those: three notes converged independently on the same gap. A closed,
machine-readable class beside the free-text `abandon_reason` is recommended by
[`alibaba-open-code-review.md`](notes/alibaba-open-code-review.md) (from a run manifest's failure
enum), [`competitor-interfaces.md`](notes/competitor-interfaces.md) (from a shipping competitor's
reason codes), and [`system-design-and-scalability.md`](notes/system-design-and-scalability.md) (from
Uber's routing of failures by kind). Three unrelated sources arriving at one conclusion is the
strongest signal in this directory.

## What was evaluated and is not worth adopting

This section is the point of the audit as much as the adoptions are. A reference that turned out not
to apply is a real finding, and re-evaluating it costs the same as evaluating it did.

| Rejected | Reason | Note |
|---|---|---|
| `public-apis/public-apis` for vendor prioritisation | Five columns, none of them OpenAPI, versioning, changelog or last-verified; its validator checks formatting, not facts. Use the APIs.guru `x-origin` index instead | [`public-apis-and-hosting.md`](notes/public-apis-and-hosting.md) §3 |
| `trimstray/the-book-of-secret-knowledge` | Last pushed 2024-11-19; only its shell and systems chapters plausibly apply, and not to M4 at all | [`public-apis-and-hosting.md`](notes/public-apis-and-hosting.md) §3 |
| `ripienaar/free-for-dev` as a source of prices | Prose bullets with no schema, so no stated limit can be validated or dated. Index of who exists, nothing more. It also bans AI-authored contributions | [`public-apis-and-hosting.md`](notes/public-apis-and-hosting.md) §3 |
| Render, Supabase, and Oracle Always Free tiers | A 30-day database expiry, a one-week inactivity pause, and an idle-reclamation rule a batch pipeline is the textbook profile for | [`public-apis-and-hosting.md`](notes/public-apis-and-hosting.md) §3 |
| `iamgini/roadmap.sh` | A frozen 2019 snapshot of the website application, not the project. Worth zero minutes; the upstream frontend track is roughly ninety percent out of scope before you start | [`roadmap-frontend-skills.md`](notes/roadmap-frontend-skills.md) §1 |
| SSR, GraphQL, MUI, PWAs, web components, mobile and desktop targets, bundler alternatives | Each named with its concrete cost — a second token system, a cache to invalidate forever, a rendering server in a project that holds no secrets | [`roadmap-frontend-skills.md`](notes/roadmap-frontend-skills.md) §3 |
| `donnemartin/system-design-primer` as a whole | Interview apparatus, a DNS-to-NoSQL canon for load Sync does not have, MySQL-specific SQL tuning that is inert against Postgres, and a latency table three orders of magnitude below the dominant term. Three named sections survive | [`system-design-and-scalability.md`](notes/system-design-and-scalability.md) §3 |
| `awesome-scalability` as milestone reading | No entry on API versioning at scale, none on schema evolution, exactly one on large-scale codemod. Narrow reference, not M4-blocking, and budget for link rot | [`system-design-and-scalability.md`](notes/system-design-and-scalability.md) §3 |
| PageIndex's indexing half | Sampling validation plus retrying correction means a tree that does not converge over identical bytes, which would spend the project's one exemption from the idempotency rule on a capability replaceable by parsing YAML | [`pageindex-retrieval.md`](notes/pageindex-retrieval.md) §3.1–§3.2 |
| Its regex injection blocklist, its benchmark number, its "vectorless" framing | Trivially evaded while silently corrupting ordinary API prose; the benchmark belongs to a commercial product built on the repository; the framing argues against a vector store Sync never had | [`pageindex-retrieval.md`](notes/pageindex-retrieval.md) §2.1, §3.3–§3.4 |
| Basing the data pipeline on `alibaba/open-code-review` | Stated plainly because it was the commission's framing: it has no orchestrator, no state graph, no reducer, no database and no idempotency. What it perfected is the accounting over the pipeline, not the pipeline | [`alibaba-open-code-review.md`](notes/alibaba-open-code-review.md) §4.1 |
| Its JSONL store, its eight-way concurrency, its model-filters-its-own-output pass, its optional planning phase, its retry story | In order: loses SQL and idempotency; eight concurrent CI runs on a customer's repository; an agent that neither shortens the critical path nor improves a result; LOCATE is a data dependency, not enrichment; one retry on one error class is not a validated design | [`alibaba-open-code-review.md`](notes/alibaba-open-code-review.md) §4.2–§4.7 |
| A Cypher-style `query_graph` with a published schema | Makes `schema.sql` public API, so grain comments become a compatibility contract and the `migration_outcome` grain trap becomes everyone's to fall into and nobody's to fix | [`code-graph-and-memory.md`](notes/code-graph-and-memory.md) §3 |
| Collapsing the four MCP tools into one, returning verbatim source, float confidence on edges, community detection as navigation, 3D multi-repo layouts | Four different questions are not four slices of one; source hands back the tokens the graph exists to save; a float invites a threshold and a threshold is an unattributable filter; clustering makes the console's structure an algorithm's output, which can change between runs on unchanged input | [`code-graph-and-memory.md`](notes/code-graph-and-memory.md) §3 |
| 49 of Impeccable's 59 detector rules | Most describe defects of a marketing landing page and can only ever return zero here; four validate against a `DESIGN.md` this repository does not have, and adopting them would let a detector drive a deferred product decision; two fire correctly on any dense Tailwind table; its prose rules ban em dashes and would start a fight with house style across every document | [`impeccable-interface-quality.md`](notes/impeccable-interface-quality.md) §3 |
| A scalar confidence score, a spatial agent canvas, a per-run Mermaid sequence diagram, a copy-this-prompt-to-your-agent block, collapse-everything disclosure | A score competes with the rung and loses; a canvas is the wrong primitive for a fixed linear pipeline; the diagram would be of the customer's code, which Sync has no claim to; a prompt block advertises Sync as an advisor, which is the one thing it is deliberately not; seven clicks turns "we show our work" into a qualified claim | [`competitor-interfaces.md`](notes/competitor-interfaces.md) §3.1–§3.5 |

One further caution that belongs here rather than in a row.
[`code-graph-and-memory.md`](notes/code-graph-and-memory.md) §1 corrects the brief it was given: only
one of the four code-graph tools renders anything at all, and the directory that looked like a UI in
the second is terminal chrome. If a future brief names a reference as visual, confirm it before
budgeting time against that claim.

## Screenshots

[`screenshots/`](screenshots/) holds eighteen PNGs captured on 2026-08-04 by driving a real browser
against six shipping products — CodeRabbit, Greptile, Devin, Stage, Superlog and Pentagon. They are
the durable record behind the competitor survey: landing pages, and then the specific surfaces that
matter, including CodeRabbit's pre-merge checks table and its review-details provenance block,
Greptile's examples index and its PR confidence score, Devin's progress-steps documentation and its
confidence-score release note, Stage's PR prologue, Superlog's agent-run states, and Pentagon's agent
status rings.

[`competitor-interfaces.md`](notes/competitor-interfaces.md) is the note that interprets them, and
every claim in it cites the filename it rests on. Read the note first; open a screenshot when you want
to see the thing it describes rather than take its word. Two files carry caveats the note states
explicitly: `greptile-04-comments-outside-diff-and-unrendered-sequence-diagram.png` shows an empty
canvas because the diagram did not render for a signed-out viewer, which is itself the finding, and
none of these images shows a product's own authenticated dashboard, because the survey could not reach
one.
