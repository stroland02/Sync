# Code graph and memory: four references audited against Sync's frozen surface

Audited 2026-08-04 against `src/sync/mcp/tools.py` and M4's console work. Every claim below is
labelled VERIFIED (primary source read this session), REPORTED (a secondary source asserts it), or
INFERENCE (my reasoning on top of the other two).

## 1. What these references actually are

All four are 2026-vintage tools that parse a repository with tree-sitter, persist the result as a
graph in SQLite, and serve it to a coding agent over MCP so the agent stops reading files one at a
time. Three of them (`codebase-memory-mcp`, `code-review-graph`, `codegraph`) are query surfaces
whose product is token reduction; only one (`Understand-Anything`) is genuinely a visual tool, and
its dashboard happens to be built on exactly M4's stack. They are large and current rather than
toys, which matters for how seriously to take their design choices.

Repository metadata, VERIFIED via `gh api repos/{owner}/{repo}` this session:

| Repository | Stars | Forks | Created | Last push | Language |
|---|---|---|---|---|---|
| `Egonex-AI/Understand-Anything` | 77,452 | 6,500 | 2026-03-15 | 2026-07-30 | TypeScript |
| `colbymchenry/codegraph` | 64,489 | 4,057 | 2026-01-18 | 2026-08-01 | C |
| `DeusData/codebase-memory-mcp` | 37,421 | 2,968 | 2026-02-24 | 2026-08-04 | C |
| `tirth8205/code-review-graph` | 28,427 | 2,637 | 2026-02-26 | 2026-08-02 | Python |

**Correction to the brief, and it is load-bearing.** The brief describes `codegraph` and
`Understand-Anything` as the two visual references. That is half right. `codegraph` has a
`src/ui/` directory, but VERIFIED by reading `src/ui/glyphs.ts` and listing `src/ui/`
(`color.ts`, `glyphs.ts`, `shimmer-progress.ts`, `shimmer-worker.ts`, `types.ts`) that directory is
terminal chrome — Unicode-versus-ASCII glyph selection for Windows consoles and a spinner. There is
no D3, no Cytoscape, no React Flow anywhere in the repository. `codegraph` renders nothing; it is a
pure MCP query surface. The visual comparison for M4 therefore rests on `Understand-Anything` alone,
plus a static D3 HTML export from `code-review-graph` (REPORTED, from its README: the `visualize`
command emits a "D3.js force-directed graph with search, community legend toggles, and degree-scaled
nodes"). I did not verify that export by reading its source.

**The strategic finding, stated first because it is the most important thing in this note.** None
of the four binds a call site to a *versioned third-party vendor operation*. Their graphs are
intra-codebase, or at widest intra-fleet. The closest any of them comes is
`codebase-memory-mcp`'s `HTTP_CALLS` edge, and REPORTED from its README that edge models internal
service-to-service communication — route-to-call-site matching across repositories indexed under one
store, described as "`CROSS_*` edges link nodes across multiple repos indexed under the same store".
There is no vendor spec, no OpenAPI diff, no notion of an operation that changed underneath you.
INFERENCE: this is direct evidence for Sync's stated position that the binding is the claim and the
graph is not. Four well-funded, heavily-starred projects built the graph layer in six months and
none of them built the binding, because the binding requires vendor adapters and spec diffing that
a general code-graph tool has no reason to own. The commoditisation the design doc predicted for
repair is now visibly happening to *graph construction* as well, and it still leaves the binding
alone. That is a reason to keep the vendor-adapter substrate as the moat, not a reason to worry.

## 2. What Sync should adopt

### 2a. Anchor freshness to a commit hash, not to a timestamp

VERIFIED by reading
`understand-anything-plugin/packages/dashboard/src/freshness.ts`. Their freshness result is a
four-state discriminated union: `fresh`, `dirty`, `stale`, `unknown`. The `stale` case carries
`graphCommitHash`, `headCommitHash`, `commitsBehind`, `commitsAhead`, a `changedFileCount`, the
changed file list, and a `relation` of `behind | ahead | diverged`. The `unknown` case carries a
closed `GraphFreshnessUnknownReason` enum: `missing-graph-commit`, `git-head-unavailable`,
`graph-commit-unavailable`, `git-command-timeout`, `freshness-request-failed`.

This is better than what Sync does, and the gap is real rather than cosmetic. Sync's envelope in
`GraphSurface._envelope` returns `indexed_at` and `feed_fetched_at` as ISO timestamps, and the
docstring argues correctly that a timestamp beats a computed duration because a duration expires
silently once an answer is cached. That argument is sound and this does not contradict it — but a
timestamp answers "when did we look", and the question a consumer actually has is "has the code
moved since". Those come apart badly in the case that matters most: an index built five minutes ago
against a commit that is now forty commits behind HEAD looks maximally fresh by timestamp and is
worthless. A commit-hash comparison answers the real question and cannot be fooled that way.

Where it lands: an additional field on the envelope in `src/sync/mcp/tools.py` alongside
`indexed_at` — not a replacement for it — and the corresponding surface in the M4 console. Note
this widens a frozen surface, so it has to clear the bar in section 3's terms; my read is that it
does, because it is additive, because no existing consumer breaks, and because the alternative is a
console that displays a freshness claim it cannot substantiate.

### 2b. Rank `unknown` explicitly, and give every unknown a sentence

VERIFIED by reading
`understand-anything-plugin/packages/dashboard/src/components/StalenessBanner.tsx`. It defines
`RISK_RANK: Record<status, number> = { fresh: 0, unknown: 1, dirty: 2, stale: 3 }` and an
`unknownSummary` map turning each reason code into prose — for example `missing-graph-commit`
becomes "does not include a Git commit hash to compare with HEAD", and `graph-commit-unavailable`
becomes "references a commit that is not available in this checkout".

Two things are worth stealing. First, `unknown` ranks *above* `fresh` but *below* `dirty` — an
un-checkable graph is treated as more alarming than a verified-current one and less alarming than a
known-drifted one, which is the honest ordering and not the lazy one. Second, every unknown reason
has a human sentence attached at the point of definition, so the UI can never render a bare enum
value at a user. This is the interface expression of the evidence discipline this project already
runs on internally: "could not verify" is a state with a reason, not an absence.

Where it lands: M4's console, wherever it displays provenance. Sync's envelope already emits
`binding_source: null` in two distinct situations — `whats_changed`, which rests on no binding at
all, and a mixed page where `_shared_rung` found disagreement. The console currently cannot tell
those apart, because both arrive as `null`. INFERENCE: that is the same defect `unknown` without a
reason has, and the same fix applies — either a reason code beside the null, or the console
inferring it from the tool that answered.

### 2c. Two-stage lazy layout with a per-container cache

VERIFIED by reading
`understand-anything-plugin/packages/dashboard/src/components/GraphView.tsx` (1,603 lines). Stage 1
lays out collapsed containers with ELK (`applyElkLayout`, `ELK_DEFAULT_LAYOUT_OPTIONS`), clamped to
`STAGE1_MAX_CONTAINER_WIDTH = 800` and `STAGE1_MAX_CONTAINER_HEIGHT = 600`. Stage 2 lays out the
*inside* of a container only when the user expands it, writes the result into a
`containerLayoutCache` in the Zustand store, and — per the comment at line 419 — "Stage 1 must not
relayout on expand". A `layoutStatus` of `"computing" | "ready"` is exposed so the view can say it
is working rather than jumping.

This is the visual analogue of the response rule Sync's tool docstring already states as "Shallow by
default. Return the call site and its operation; return a change in full only when asked for it by
identifier." `Understand-Anything` arrived at the same rule independently for the same reason —
laying out what nobody has asked to see is the rendering cost equivalent of the tokens Sync's rule
exists to save. INFERENCE, but a well-supported one: this is the strongest evidence in the audit
that Sync's shallow-by-default rule generalises from agents to humans, which is the exact claim M4
is making by serving one set of rules to both.

Where it lands: M4's console graph views, in the worktree's `web/`. The console's hierarchy
(Codebase → API Services → Errors & Incidents → Finding → Solution Workflow → Pull Request) is
already a containment hierarchy, so the mapping is direct: a level is a Stage 1 container, and its
contents get laid out on expand and cached.

### 2d. Portal nodes for edges that leave the current level

VERIFIED by reading `GraphView.tsx` — it imports `computePortals` and a `PortalNode` component,
registers `portal: PortalNode` in the React Flow node-type map, and at line 609 builds "Portal nodes
for connected external layers", producing `portalNodes: PortalFlowNode[]` and `portalEdges`.

When the view is scoped to one layer, an edge that leaves that layer does not get dropped and does
not get drawn to an off-screen node. It terminates in a visible stub that names the layer it goes
to. INFERENCE: this is the single most useful visual idea for M4, because M4's whole navigation
premise is that you are always looking at one level of the dependency graph. Without something like
this, every level of Sync's console silently lies about connectivity — a Finding whose call site
lives in a service you have filtered out simply appears unconnected. A portal node makes the edge
visible and clickable and makes the navigation hierarchy legible from inside any one level of it.

### 2e. Respect the inline tool-result ceiling when sizing a page

VERIFIED by reading `codegraph`'s `src/mcp/tools.ts`, the comment on `getExploreOutputBudget` at
lines 203–214. The constraint, in their words: a budget "MUST stay under the agent's INLINE
tool-result cap (~25K chars). Above that, the host externalizes the result to a file the agent then
Reads back — re-introducing a read AND the cache-write cost — which is exactly what a 35K vscode
explore did in the n=4 README A/B."

This is a hard operational fact about how agent hosts behave, and it is the kind of thing that is
invisible until it silently undoes the work. Sync paginates every list, which is the right rule, but
`DEFAULT_LIMIT = 50` in `src/sync/mcp/tools.py` is a row count and not a byte budget. VERIFIED by
reading `whats_at_risk`: each row carries `file`, `line`, `symbol`, `operation`, `vendor`,
`change_kind`, `severity`, `finding_id`, `binding_source`. INFERENCE: fifty of those rows on a
repository with long paths plausibly exceeds 25K characters, at which point the page gets
externalised to a file, the agent Reads it back, and the pagination rule has bought nothing — the
read it exists to prevent happens anyway. This does not change the frozen surface at all; it is a
check on the default, and worth measuring against a real page before assuming it is fine.

### 2f. Ship the console as a standalone read-only viewer

VERIFIED from the `understand-anything-viewer` README that it requires "Only Node.js (>= 18)" and
explicitly "no Claude Code, no LLM, no API key", and that "Everything is served read-only from local
disk, bound to 127.0.0.1, and gated behind a one-time access token". The package description calls
it a "Standalone read-only viewer for Understand-Anything knowledge graphs". REPORTED rather than
verified: that a graph is shared by handing over the analysed project directory containing
`knowledge-graph.json`.

Three things here are directly applicable to M4: the local-bind-plus-one-time-token auth model,
which is proportionate for a read-only console and avoids inventing a session system; separating a
viewer from the tool that produced the data, so someone can look at a remediation graph without
running Sync; and the general shape of a shareable artifact. INFERENCE: the third is the interesting
one commercially — "here is the remediation graph as it happened, look at it yourself" is the
product position M4 already claims, and it is far more persuasive as a link someone can open than
as a screenshot.

### 2g. Show the savings breakdown, not just the total

REPORTED from `code-review-graph`'s README, which prints:

```
Full context would be:     12,921 tokens
Graph context used:           762 tokens
Saved:                     12,159 tokens (~94%)
Breakdown: Functions 244 · Tests 191 · Risk 244 · Other 83
```

Sync already emits `context_savings` on every envelope, computed as
`len(window) * _TOKENS_PER_AVOIDED_READ` with `_TOKENS_PER_AVOIDED_READ = 400` — VERIFIED by
reading `tools.py`, where the comment is admirably honest that this is "a deliberate estimate rather
than a measurement, and it is stated as one". Convergent design, which is reassuring. The one thing
worth taking is the presentation: showing the counterfactual and the breakdown alongside the number
makes an estimate legible as an estimate, whereas a lone integer named `context_savings` invites
being read as a measurement. That is a console concern, not a surface change.

## 3. What to deliberately skip

**A Cypher-like `query_graph`, and `get_graph_schema` beside it.** VERIFIED that
`codebase-memory-mcp` exposes both — `query_graph` accepts read-only Cypher with `MATCH`, `WHERE`,
`WITH`, `UNWIND`, `UNION`, variable-length paths and aggregates, and `get_graph_schema` returns node
and edge counts with per-label property definitions, documented as the recommended first call.
Sync's design spec rejected exactly this and `tools.py` records why in its module docstring: "agents
compose arbitrary query languages poorly, and publishing the graph schema as the interface would
make every internal change a breaking change — for a product whose whole claim is catching breaking
changes." Seeing it built does not weaken that argument; it sharpens it. The concrete cost of
adopting it is that `schema.sql` becomes public API, so the grain comments that `CLAUDE.md` requires
before adding a column stop being an internal discipline and start being a compatibility contract,
and the `migration_outcome` grain trap — one row is one attempt, not one finding — becomes something
every external query author can fall into and Sync cannot fix. Skip it.

**Collapsing to a single tool.** VERIFIED by reading `codegraph`'s `src/mcp/tools.ts`: eight tools
are defined (`explore`, `node`, `search`, `callers`, `callees`, `impact`, `files`, `status`) but
`DEFAULT_MCP_TOOLS = new Set(['explore'])`, and the comment at lines 804–814 gives the reason —
"the single tool that reliably earns its place", every other tool is "a narrower slice of what
explore already does, and presence itself steers mis-picks, so they are no longer LISTED to agents."
This is a real finding backed by measurement and it deserves to be taken seriously rather than
waved off. It still does not transfer. Their eight tools genuinely were slices of one another;
`codegraph_callers` and `codegraph_callees` are the same traversal in two directions. Sync's four
are four different questions with four different inputs and four different answer shapes —
`whats_at_risk` takes filters and returns bindings, `explain_call_site` takes a file and a line,
`whats_changed` takes a vendor and returns changes with no binding at all, and `propose_patch` runs
a pipeline. Merging them produces a tool whose response shape depends on which arguments were
supplied, which is the thing that actually causes mis-picks. This is a difference that is merely
different, and the bar for changing a frozen surface is not met.

**Returning verbatim source.** VERIFIED that `codegraph_explore` returns "the relevant symbols'
verbatim source grouped by file" and instructs the agent to treat it as already read. This is the
exact inverse of Sync's first response rule. Their inversion is coherent for what they are — a
context-delivery tool whose product *is* the source — and incoherent for Sync, whose product is the
binding. The cost of adopting it is stated in `tools.py`: "A tool returning source has handed back
the tokens the graph exists to save." Note that Sync already carries the one deliberate exception,
`propose_patch` returning a diff, with an argument for why the diff *is* the answer there and why
that is not a licence to return the surrounding file. That exception is correctly drawn and does not
need widening.

**Float confidence scores on edges.** REPORTED from `code-review-graph`'s README: it carries
"three-tier confidence scoring (EXTRACTED/INFERRED/AMBIGUOUS) with float scores on edges". The
three-tier part is striking convergence with Sync's rung ladder and independently validates the
design — as does `codebase-memory-mcp`'s `USAGE` edge, REPORTED as covering the case where "an
identifier is used, but a unique callable target is not proven", which is precisely Sync's
`unresolved`. The float is the part to skip. Sync's rung is categorical, is an enforced column
rather than a join, and the write refuses an unattributed finding; a float invites a consumer to
pick a threshold, and a threshold is an unattributable filter — a finding dropped at 0.7 cannot be
traced to the binder that produced it, which is the whole property `.claude/rules/graph-grain.md`
exists to protect. Note also that `_shared_rung` in `tools.py` deliberately returns `None` rather
than the weakest rung when findings disagree, with the argument that understating a rung is still a
wrong answer. A float would have no equivalent honest-null and would average instead, which is worse
than both options.

**Community detection as the navigation structure.** VERIFIED that `Understand-Anything`'s dashboard
depends on `graphology-communities-louvain`; REPORTED that `code-review-graph` uses Leiden and that
`codebase-memory-mcp`'s `get_architecture` returns "languages, packages, entry points, routes,
hotspots, boundaries, layers, and clusters in a single call". These tools cluster because they do
not know what the codebase's structure means and have to discover it. Sync does know: the hierarchy
is Codebase → API Services → Errors & Incidents → Finding → Solution Workflow → Pull Request, it is
the product claim, and it is stable. The cost of adopting clustering is that the console's structure
becomes an algorithm's output, which means it can change between runs on unchanged input — a direct
collision with the idempotency rule in `CLAUDE.md`, and it would move the one part of the UI whose
job is to be the same shape every time.

**Multi-repo and 3D layouts.** REPORTED that `codebase-memory-mcp` offers "Multi-galaxy 3D UI
layout for cross-repo architecture visualization". Not verified, and not relevant: Sync's console
serves one codebase, and 3D graph layout costs implementation and interaction complexity to convey
strictly less than a good 2D layout with portals.

**Adopting the dynamic per-project tool description.** VERIFIED that `codegraph` rewrites its tool
description at registration to append "Budget: make at most N calls for this project (X files
indexed)", scaled by `getExploreBudget(stats.fileCount)`. This is a genuinely clever idea — steering
an agent through the description rather than the response — and I want to flag it as noted rather
than adopted. It sits awkwardly with a frozen surface: the description is arguably not part of the
freeze, but a description that varies by deployment makes the tool's behaviour non-reproducible
across installs, and Sync has no per-repository size signal that would drive it anyway. Revisit only
if there is evidence agents are over-calling the read tools.

## 4. Who should consult this, and what it answers

**M4, the operator console — primary consumer.** It answers: how does a graph view stay responsive
and honest at scale? Sections 2c (two-stage lazy layout with a container cache), 2d (portal nodes
for cross-level edges), 2b (ranking `unknown` and giving every unknown reason a sentence), and 2f
(local-bind plus one-time token, and a viewer separable from the producer) are all directly
implementable, and all are VERIFIED against `Understand-Anything`'s dashboard source. The stack
match is close enough to be worth stating plainly: VERIFIED from
`understand-anything-plugin/packages/dashboard/package.json` that it runs React 19, Vite 6,
Tailwind v4, `@xyflow/react` 12, `@dagrejs/dagre`, `elkjs`, `d3-force`, `graphology`, and `zustand`.
M4 is on Vite + React 19 + Tailwind v4, so their layout and interaction code is readable as a
working reference rather than as an analogy. `elkjs` in particular is the dependency to look at
first if M4 has not already chosen a layout engine.

**The owner of `src/sync/mcp/tools.py` — secondary consumer.** It answers: does anything out there
justify unfreezing the surface? One thing does, section 2a, and it is additive: freshness anchored
to a commit hash rather than a timestamp, because `indexed_at` cannot distinguish a recent index of
stale code from a recent index of current code. One thing needs measuring rather than deciding,
section 2e: whether a 50-row page stays under the ~25K-character inline tool-result ceiling, because
above it the host externalises the page and the agent reads it back, which silently defeats
pagination. Everything else in this audit is a difference that is merely different, and section 3
says so case by case with the cost of adopting it.

**M5 or whoever next touches the telemetry rung — worth a glance.** `codebase-memory-mcp`'s
`ingest_traces` (REPORTED: "Ingest runtime traces to validate `HTTP_CALLS` edges") uses runtime
telemetry to *validate statically-derived edges* rather than to create new ones. INFERENCE: that is
a narrower and more defensible use of telemetry than promoting a static binding to `observed`
wholesale, and if the correlator ever produces findings that are hard to attribute, "telemetry
confirms or refutes a static edge" is a fallback position with a working precedent behind it.

## Sources

- https://github.com/DeusData/codebase-memory-mcp — README, and `gh api` metadata
- https://github.com/tirth8205/code-review-graph — README, and `gh api` metadata
- https://github.com/colbymchenry/codegraph — README, `src/mcp/tools.ts`, `src/ui/glyphs.ts`,
  repository tree, and `gh api` metadata
- https://github.com/Egonex-AI/Understand-Anything — README, `packages/dashboard/package.json`,
  `packages/dashboard/src/freshness.ts`, `packages/dashboard/src/components/StalenessBanner.tsx`,
  `packages/dashboard/src/components/GraphView.tsx`,
  `packages/dashboard/src/components/NodeInfo.tsx`,
  `packages/dashboard/src/components/FilterPanel.tsx`, `packages/viewer/README.md`,
  and `gh api` metadata
- `src/sync/mcp/tools.py` — the frozen surface every judgement above is measured against
