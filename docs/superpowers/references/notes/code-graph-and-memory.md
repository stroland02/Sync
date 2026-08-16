# Code graph and memory: four references read at source, audited against Sync's frozen surface

Second pass, 2026-08-04. The first pass read READMEs, repository trees, and a handful of files. This
pass cloned all four repositories and read implementation. Where the two disagree, this note says so
and shows what was read.

Every claim is labelled VERIFIED (I read the primary source this session), REPORTED (a secondary
source asserts it and I did not confirm it in code), or INFERENCE (my reasoning on top of the other
two). Paths are relative to each repository's root.

Clones live under the session scratchpad at
`.../b4674d1e-f115-48c1-ab2c-dab217d86019/scratchpad/refs/`. They are shallow and will not survive
the session; the paths below are for re-cloning, not for reading again.

**Coverage, stated honestly.** These are large repositories and I did not read them whole.

- `codebase-memory-mcp` — read `src/store/store.c` schema and write paths, `src/mcp/mcp.c` tool
  definitions and dispatch, `src/pipeline/pipeline_incremental.c` classification, `src/pipeline/
  pass_route_nodes.c`, `src/traces/traces.c`, `src/ui/layout3d.c`, and the whole of `graph-ui/src`.
  Did **not** read: the Cypher engine (`src/cypher/`), the semantic/embedding passes, the daemon, or
  most of the 28 pipeline passes.
- `code-review-graph` — read `graph.py` schema and write paths, `context_savings.py` whole,
  `incremental.py` change detection, `visualization.py` mode selection and D3 loader. Did **not**
  read: `parser.py` (16,080 lines), the resolvers, embeddings, or the MCP tool bodies.
- `codegraph` — read `src/db/schema.sql` whole, `src/mcp/tools.ts` budget and provenance sections.
  Did **not** read: the extraction layer (6,767 lines), the resolution layer, or the Rust kernel.
- `Understand-Anything` — read the dashboard's layout utilities whole (`elk-layout.ts`,
  `force-layout.ts`, `containers.ts`, `edgeAggregation.ts`, both workers), `core/src/staleness.ts`,
  `core/src/persistence/index.ts`, `WarningBanner.tsx`, `viewer/bin/viewer.mjs`, and the Stage 1 /
  Stage 2 sections of `GraphView.tsx`. Did **not** read: the language extractors, the Figma plugin,
  or most of `GraphView.tsx`'s 1,603 lines.

---

## 1. What these references actually are

Four tools that turn a repository into a graph an agent or a person can query without reading files
one at a time. They are close enough in purpose to compare and different enough in construction that
the differences are informative.

Repository metadata, VERIFIED via `gh api repos/{owner}/{repo}` this session:

| Repository | Stars | Forks | Created | Last push | GitHub language |
|---|---|---|---|---|---|
| `Egonex-AI/Understand-Anything` | 77,457 | 6,499 | 2026-03-15 | 2026-07-30 | TypeScript |
| `colbymchenry/codegraph` | 64,494 | 4,058 | 2026-01-18 | 2026-08-01 | C |
| `DeusData/codebase-memory-mcp` | 37,430 | 2,968 | 2026-02-24 | 2026-08-04 | C |
| `tirth8205/code-review-graph` | 28,434 | 2,637 | 2026-02-26 | 2026-08-02 | Python |

The GitHub language column is misleading for `codegraph`: VERIFIED by counting files, the product is
349 TypeScript source files with a Rust kernel (`codegraph-kernel/Cargo.toml`); the "C" is vendored
tree-sitter grammars.

### The first pass got the shape of the field wrong in four places

**Correction 1: `codebase-memory-mcp` has a full graph UI, and it is on M4's stack.** The first pass
concluded that "only one (`Understand-Anything`) is genuinely a visual tool" and dismissed
`codebase-memory-mcp`'s 3D layout as REPORTED and irrelevant. VERIFIED wrong. `graph-ui/` is 5,213
lines of React across 24 components with its own Vitest suite. Its `package.json` declares React
19.0, Vite 6.4, Tailwind 4.1, and `three` ~0.183 with `@react-three/fiber` 9.5, `@react-three/drei`,
and `@react-three/postprocessing`. Three of those four version lines match M4's stack exactly. The
render is genuinely 3D — a star-field metaphor where node colour is a Hertzsprung-Russell spectral
class keyed to degree (`src/ui/layout3d.c:99-129`) — and its answer to scale is unlike the other
three, so it belongs in the comparison whatever one thinks of the aesthetic.

**Correction 2: `code-review-graph`'s three-tier confidence system is two tiers, and nothing reads
them.** The first pass took the README's "three-tier confidence scoring
(EXTRACTED/INFERRED/AMBIGUOUS) with float scores on edges" as REPORTED and called it "striking
convergence with Sync's rung ladder [that] independently validates the design". VERIFIED that the
convergence is with a feature that does not exist. `AMBIGUOUS` appears in `README.md:306`, in four
translated READMEs, in `CHANGELOG.md:625`, and in `docs/FAQ.md:48`. It appears in **no Python file
in the repository**. The only two values ever written are `EXTRACTED` (the column default,
`graph.py:103`) and `INFERRED` (set in `scoped_resolver.py:480,489` and `event_resolver.py:107`).

Worse for the "validates the design" reading: the float and the tier are never consumed. Grepping
`confidence` across `tools/query.py`, `search.py`, and `analysis.py` returns nothing; the only reads
are the row-to-dataclass hydration at `graph.py:2188` and the serializer at `graph.py:2236`. So the
attribution is written to every edge and read by no query. INFERENCE: this is precisely the failure
mode `.claude/rules/graph-grain.md` exists to prevent, observed in the wild. An attribution that is
not enforced at the write and not consumed at the read decays into a decorative column, and nobody
notices because nothing breaks.

**Correction 3: `codebase-memory-mcp`'s `ingest_traces` is a stub.** The first pass reported it as
"Ingest runtime traces to validate `HTTP_CALLS` edges" and recommended it to M5 as "a fallback
position with a working precedent behind it". VERIFIED that there is no precedent. The whole handler
is `src/mcp/mcp.c:10885-10915`; it counts the array and returns:

```c
    yyjson_mut_obj_add_str(doc, root, "status", "accepted");
    yyjson_mut_obj_add_int(doc, root, "traces_received", trace_count);
    yyjson_mut_obj_add_str(doc, root, "note",
                           "Runtime edge creation from traces not yet implemented");
```

The tool's own description in the registry (`mcp.c:664`) says "enhance the knowledge graph", not
"validate"; the validate framing came from the README. There *is* real OTLP span-parsing code in
`src/traces/traces.c` (142 lines: service name, HTTP path, duration, p99), but nothing calls it from
the tool path. Section 4 of this note withdraws the M5 recommendation.

**Correction 4: not all four are "tree-sitter into SQLite".** The first pass opened by asserting all
four "parse a repository with tree-sitter, persist the result as a graph in SQLite". VERIFIED false
for `Understand-Anything`: there is no SQLite dependency anywhere in the workspace, persistence is a
JSON file at `.ua/knowledge-graph.json` (`packages/core/src/persistence/index.ts:9`), and the graph
is a **hybrid of parsed structure and LLM-authored summary**. `packages/core/src/analyzer/
llm-analyzer.ts:18-41` builds a prompt asking a model to return `fileSummary`, `tags`, `complexity`,
`functionSummaries`, and `classSummaries` as JSON. `WarningBanner.tsx:20-23` tells the user, in
those words, that graph defects "are LLM generation errors — not a system bug". That difference
explains most of what makes their dashboard interesting, and it was invisible from the README.

### What survives the corrections, and it is the important part

**None of the four binds a call site to a versioned third-party vendor operation.** This held in the
first pass and holds harder now that I have read the closest thing to a counter-example.

That counter-example is `codebase-memory-mcp`'s `Route` node, and it deserves to be described
accurately because it is the nearest any of these gets to Sync's binding. VERIFIED from
`src/pipeline/pass_route_nodes.c:1-16`: after resolution, an `HTTP_CALLS` edge points at the library
function (`requests.get`) and carries the URL in its properties. This pass mints a synthetic `Route`
node with a deterministic qualified name (`__route__METHOD__/path`) and re-targets the edge onto it,
so a client call site and a server handler meet at one node:

```
 *   Service A: checkout() → HTTP_CALLS → Route("POST /api/orders")
 *   Service B: create_order() → HANDLES → Route("POST /api/orders")
```

The join is made possible by `cbm_route_canon_path` (`pass_route_nodes.c:59-`), which collapses
`:name`, `{name}`, `<name>`, and `${...}` all to a single `{}` token, discarding the parameter name
on purpose "so the same logical endpoint matches across services that name the path variable
differently".

That is a rendezvous between two pieces of the customer's own fleet. There is no vendor spec, no
OpenAPI diff, no version pair, no notion of an operation that changed underneath you. INFERENCE, and
the strategic point of this whole audit: four heavily-starred projects built graph construction to a
high standard inside six months and none of them built the binding, because the binding needs vendor
adapters and spec diffing that a general code-graph tool has no reason to own. Graph construction is
commoditising. The binding is not. That is a reason to keep the vendor-adapter substrate as the moat
rather than a reason to worry — and it is a reason to *steal* the route-canonicalisation trick,
because Sync has the identical problem one level up.

---

## 2. What Sync should adopt

### 2a. Anchor freshness to a commit hash, and refuse to guess when the anchor is unusable

VERIFIED at `Understand-Anything`'s `packages/core/src/staleness.ts:12-53`. The freshness result is
a four-arm discriminated union — `fresh`, `dirty`, `stale`, `unknown`. `stale` carries
`graphCommitHash`, `headCommitHash`, `commitsBehind`, `commitsAhead`, `changedFileCount`,
`changedFiles`, and a `relation` of `behind | ahead | diverged` computed from two
`git merge-base --is-ancestor` calls (`staleness.ts:288-320`). `unknown` carries a closed reason
enum: `missing-graph-commit`, `git-head-unavailable`, `graph-commit-unavailable`,
`git-command-timeout`, `freshness-request-failed`.

Two details the first pass did not have, and both matter more than the union shape:

First, the comparison is **pathspec-scoped**. `PROJECT_PATHSPEC` (`staleness.ts:70-77`) restricts
every `git` invocation to the project directory and explicitly excludes the graph's own output
directory. Without that, writing the graph makes the graph look stale.

Second — and this is the better idea, from a different repository — `code-review-graph` stores the
same anchor and gets the failure case right. VERIFIED at `incremental.py:644-667`:

```python
    stored = store.get_metadata("git_head_sha")
    if stored and _commit_object_exists(repo_root, stored):
        return stored
    return None
```

The docstring says why `None` rather than a fallback: `HEAD~1` "silently misses work that arrived
through a multi-commit pull, rebase, or branch switch", and a stored commit lost to a history
rewrite or a shallow clone must trigger a full rebuild rather than a diff against a wrong base.
`_commit_object_exists` is deliberately an object-existence check and not an ancestry check, because
a commit only reachable from an abandoned branch is still a valid diff base (`incremental.py:
622-628`).

Where it lands: an additive field on the envelope in `src/sync/mcp/tools.py` beside `indexed_at`,
plus the console surface in `web/`. The existing docstring argument in `GraphSurface._envelope` —
that a timestamp beats a computed duration because a duration expires silently once cached — is
sound and this does not contradict it. But `indexed_at` answers "when did we look" and the consumer's
real question is "has the code moved since". They come apart in the case that matters: an index
built five minutes ago against a commit now forty behind HEAD reads as maximally fresh and is
worthless. This widens a frozen surface, so it must clear section 3's bar; my read is that it does,
because it is additive, no existing consumer breaks, and the alternative is a console displaying a
freshness claim it cannot substantiate.

### 2b. Make "this view is wrong" a typed, rendered result — the best single idea in the audit

Entirely missed by the first pass. VERIFIED across four files.

`Understand-Anything` treats its own graph as untrusted input and its renderer as a thing that can
fail, and both produce the same typed value. `packages/core/src/schema.ts:485-488`:

```ts
export interface GraphIssue {
  level: "auto-corrected" | "dropped" | "fatal";
  category: string;
  ...
```

`validateGraph` (`schema.ts:563`) emits `auto-corrected` for coerced or defaulted fields and
`dropped` for invalid nodes. `repairElkInput` (`packages/dashboard/src/utils/elk-layout.ts:56-212`)
does the same for the layout engine's input across five repairs — missing dimensions, duplicate ids
per parent, orphan children, orphan edges, containment cycles — each producing a categorised issue
with a counted human message (`"Dropped 3 edge(s) referencing nonexistent nodes."`). `applyElkLayout`
(`elk-layout.ts:225-244`) catches an ELK throw and returns a `fatal` issue rather than propagating.
In `import.meta.env.DEV` the whole thing runs `strict: true` and throws instead
(`GraphView.tsx:849`), so a repair that is acceptable in production is a test failure in
development.

Then `WarningBanner.tsx` renders them, and the part worth stealing is the routing at lines 12-24: a
`fatal` issue produces "Some of these issues look like dashboard rendering bugs. Please file an
issue…", anything else produces "These are LLM generation errors — not a system bug. You can ask
your agent to fix these specific issues…". The console distinguishes *your data is malformed* from
*our renderer broke*, and gives a copy button that produces the right text for either.

Where it lands: M4's console, in `web/`. INFERENCE, strongly held: this is the interface expression
of `CLAUDE.md`'s "abandoned runs are data" applied to rendering. A console whose job is to show a
remediation graph as it happened must never quietly drop a node or an edge it could not place,
because the whole product claim is that the picture is what occurred. A `GraphIssue`-shaped value
threaded from data load through layout to a banner is cheap, and it is the difference between a view
that is honest at scale and one that is merely pretty.

### 2c. Compute layout from a stable identity so the same graph draws the same way twice

Two independent implementations, both deliberate, and neither noted by the first pass.

`Understand-Anything`, `packages/dashboard/src/utils/force-layout.ts:66-67`:

```ts
  // Leaving x/y unset lets d3-force use its deterministic phyllotaxis seed.
  // This keeps layouts stable for identical, ordered graph inputs.
```

`codebase-memory-mcp`, `src/ui/layout3d.c:693-700` — the ring angle comes from `fnv1a` of the
directory cluster key, the jitter seed from `fnv1a` of the node's qualified name, and the z from call
depth. No wall clock, no time-seeded RNG, no dependence on row insertion order:

```c
        uint32_t h = fnv1a(ck);
        float angle = ((float)(h & 0xFFFF) / 65535.0f) * 6.2832f;
        ...
        uint32_t seed = fnv1a(sn->qualified_name);
```

Where it lands: M4's graph views. INFERENCE: `CLAUDE.md`'s idempotency rule is written about
pipeline stages, but a console that redraws the same finding in a different arrangement on every
load is the same defect wearing a different hat — a reviewer cannot say "the shape changed" if the
shape changes for free. Seed every layout from node identity, never from array position or
`Math.random`.

### 2d. Two-stage layout needs a termination gate, and that is the hard part

The first pass had the two stages. It did not have the loop, which is the part that is easy to get
wrong.

VERIFIED in `GraphView.tsx:797-921`. Stage 1 lays out collapsed containers with ELK using a
`sqrt(childCount)` size *estimate*, clamped to `STAGE1_MAX_CONTAINER_WIDTH = 800` and
`STAGE1_MAX_CONTAINER_HEIGHT = 600` (`GraphView.tsx:522-535`). Stage 2 fires only on expand, lays
out that one container's children, and writes into a `containerLayoutCache` in the Zustand store.
The Stage 2 effect deliberately does not depend on `built`, with the comment at lines 799-801:
"Critically does NOT depend on `built` — expanding a container must not trigger Stage 1 relayout of
the surrounding atoms."

But Stage 2 discovers the container's *real* size, which may be nothing like the estimate Stage 1
routed edges around. So it feeds back — and the feedback needs a brake:

```ts
          const dw = Math.abs(actualSize.width - stage1Width) / stage1Width;
          const dh = Math.abs(actualSize.height - stage1Height) / stage1Height;
          const deviated = dw > 0.2 || dh > 0.2;
```

with the reason at lines 903-907: "Bumping unconditionally would loop: Stage 1 → Stage 2 → bump →
Stage 1 → … With the >20% gate, after the re-layout `containerSizeMemory` holds the actual size, so
the next Stage 2 sees a 0% deviation and the loop terminates." Note also line 822: the deviation is
measured against a `containerSizeMemory` snapshot captured *before* any write, because
`setContainerLayout` overwrites it.

Where it lands: M4's console graph views. The navigation hierarchy — Codebase → API Services →
Errors & Incidents → Finding → Solution Workflow → Pull Request — is already a containment
hierarchy, so a level maps directly onto a Stage 1 container. Take the memoised size and the
deviation gate along with the two stages; without them the console either relayouts the world on
every expand or oscillates.

Separately and independently useful: both expensive layouts run in a **Web Worker**
(`utils/layout.worker.ts` for dagre, `utils/force-layout.worker.ts` for d3-force). The client
(`force-layout-client.ts:29-32`) spawns a **fresh worker per graph revision** so a cancel can
`terminate()` a running synchronous simulation rather than queue behind it, checks `requestId` on
the response to reject a stale reply, and falls back to `createFallbackGrid` (a plain
`ceil(sqrt(n))` grid) only if worker startup fails. That is a small, complete pattern and M4 can
lift it nearly verbatim.

### 2e. Portal nodes for edges that leave the level — with one modification

VERIFIED. `computePortals` is defined in `packages/dashboard/src/utils/edgeAggregation.ts:77-106`
and consumed at `GraphView.tsx:610`. The value is small:

```ts
export interface PortalInfo {
  layerId: string;
  layerName: string;
  connectionCount: number;
}
```

When the view is scoped to one layer, an edge crossing out of it is neither dropped nor drawn to an
off-screen node; it terminates in a visible stub naming the destination layer and how many edges go
there. `findCrossLayerFileNodes` (`edgeAggregation.ts:113-135`) then answers "which of my nodes
cross to that layer", which is what a click on the portal needs.

**One thing to change on adoption.** `aggregateLayerEdges` (`edgeAggregation.ts:43-48`) canonicalises
the pair key so `A→B` and `B→A` merge into one undirected count. For a codebase-comprehension tool
that is a reasonable simplification. For Sync it is wrong: on a remediation graph the direction is
the claim — a Finding pointing *at* a call site and a call site pointing *at* a Finding are different
statements. Keep the portal, keep the count, keep direction.

INFERENCE: this remains the single most useful visual idea for M4, because M4's whole navigation
premise is that you are always inside one level. Without a portal, every level silently lies about
connectivity — a Finding whose call site lives in a filtered-out service simply looks unconnected.

### 2f. When a grouping is derived, record which strategy derived it

VERIFIED at `packages/dashboard/src/utils/containers.ts:7-12` and `91-139`. `deriveContainers` groups
by folder first and falls back to Louvain community detection **only when folder grouping
degenerates** — fewer than two buckets, or any single bucket holding more than
`MAX_CONCENTRATION = 0.7` of the nodes. And the container it returns says which happened:

```ts
export interface DerivedContainer {
  id: string;
  name: string;
  nodeIds: string[];
  strategy: "folder" | "community";
}
```

This meaningfully refines the first pass's blanket "skip community detection as navigation
structure". The correct rule is not "never cluster" — it is "prefer the authoritative structure,
cluster only where the authoritative structure fails to discriminate, and make the derived grouping
carry how it was derived". That is Sync's rung discipline applied to a UI grouping, and Sync has
the same shape of problem: findings can be grouped by service when the service attribution is good
and must be grouped by something else when it is not.

Where it lands: `web/`, on any view that groups findings. Sync's hierarchy is authoritative and
stable, so `strategy` will read `"folder"` almost always — which is exactly why the field is cheap
and why the one time it reads otherwise is worth seeing.

### 2g. Put "this is an estimate" in the payload, and leave a calibration path

`code-review-graph`'s savings reporting is better than Sync's, VERIFIED by reading
`code_review_graph/context_savings.py` end to end (318 lines).

Three things Sync does not do. First, the estimate flag is **in the response**, not in a comment —
`estimate_context_savings` returns `{"estimated": True, "saved_tokens": …, "saved_percent": …}`
(lines 78-82). Second, the baseline is measured rather than assumed: `estimate_file_tokens`
(lines 35-51) sums the *actual sizes* of the changed files, using `stat().st_size` rather than
reading them. Third, there is a calibration path — `verify_with_tiktoken` (lines 151-198) re-runs
the same comparison through a real tokenizer when `tiktoken` is installed and returns a separate
`verified_*` block, and the CLI panel prints it on its own line beside the estimate
(`format_context_savings_panel`, lines 280-288).

Sync computes `len(window) * _TOKENS_PER_AVOIDED_READ` with `_TOKENS_PER_AVOIDED_READ = 400`, and
the comment in `tools.py:37-38` is admirably honest that this is "a deliberate estimate rather than
a measurement, and it is stated as one". The problem is *where* it is stated. A consumer reading the
JSON sees an integer named `context_savings` and no signal that it is modelled. Renaming is a
surface change; adding a sibling boolean is additive and closes the gap.

Where it lands: `src/sync/mcp/tools.py` for the flag, `web/` for the presentation — the panel
showing counterfactual, actual, saved, and a per-category breakdown makes an estimate legible as an
estimate in a way a lone integer never will.

### 2h. Canonicalise the operation path before joining on it

VERIFIED at `codebase-memory-mcp`'s `src/pipeline/pass_route_nodes.c:47-58` and the loop that
follows. Every route-parameter syntax collapses to one `{}` token, and the parameter name is
discarded on purpose. The comment enumerates the frameworks: `:name` for Express, React-Router,
Rails; `{name}` for Axum, Spring, OpenAPI, ASP.NET; `<name>` including typed `<int:id>` for Flask
and Rocket; `${...}` for JS template interpolation captured into the path.

Where it lands: `sync.signals.*` adapters, not core — the vendor's URL conventions are the adapter's
business. INFERENCE: Sync has this problem one level up and harder. An OpenAPI spec writes
`/v1/customers/{customer}`; a TypeScript call site writes a template literal; the SDK writes a method
name. Any binder joining a call site to an operation is doing some version of this normalisation,
and the value of seeing it written out is the *list of syntaxes* and the decision to throw the
parameter name away. If Sync's binder does not already discard the parameter name, it will miss a
binding whenever a customer names the variable differently from the spec.

### 2i. Render provenance as the mechanism, not as an enum

VERIFIED in `codegraph`. Its `edges.provenance` column (`src/db/schema.sql:53`, indexed at line 187)
is effectively two-valued — `NULL` for a directly-resolved edge, `'heuristic'` for a synthesized one
(`src/resolution/callback-synthesizer.ts`, `src/resolution/c-fnptr-synthesizer.ts`). Unlike
`code-review-graph`'s tier, it is genuinely consumed: `src/context/index.ts:379`,
`src/mcp/tools.ts:1855`, `:2002`, `:2052`.

The interesting part is *how*. `synthEdgeNote` (`tools.ts:1848-1885`) turns the flag plus the edge's
metadata into a sentence naming the mechanism, with the intent stated in its docstring: "so a
synthesized hop reads as 'registered via onUpdate at App.tsx:3148', not a bare arrow." A callback
edge renders as ``callback — registered via `onUpdate` on .handler (dynamic dispatch)``; an event
edge names the event; a React re-render edge says `setState` re-runs `render()`.

Where it lands: `web/`. Sync's `binding_source` correctly reports *which rung*; it does not report
*what the binder saw*. `"observed"` is true and unhelpful to a human deciding whether to trust a
patch. INFERENCE: the console already has the material to do better — `_evidence_for` in `tools.py`
assembles `spec_diff`, `changelog`, and `call_sites` — so this is a presentation change in `web/`,
not a surface change. Render the rung as a clause: "observed — 412 requests to
`POST /v1/payment_intents` in the last 24h", not `observed`.

### 2j. Keep what the indexer could not do, as queryable data

VERIFIED across `codebase-memory-mcp`'s schema and tool surface, and it is the closest thing in this
audit to `CLAUDE.md`'s "abandoned runs are data".

`index_coverage` (`store.c:304-310`) holds one row per file the indexer could not fully cover, keyed
`(project, rel_path, kind)`, where `kind` is `parse_partial` (indexed, but the tree had ERROR or
MISSING regions — `detail` carries 1-based line ranges) or a skip phase (`read`, `extract`,
`oversized` — `detail` carries the reason). The schema comment says why it is a separate table:
"coverage is metadata about the graph, not part of it." `index_coverage_meta` (`store.c:314-323`)
holds one row per *completed persistence attempt*, kept separate from `projects` so "a missing row
unambiguously means coverage metadata is unavailable" — a grain distinction of exactly the kind
`CLAUDE.md` asks for before adding a column.

The misses are then exposed three ways: as a report on `index_status`, as a dedicated
`check_index_coverage` tool taking exact paths or bounded scopes, and — the nice one —
`query_graph(graph="missed")`, which serves the failures as their own navigable Project → Folder →
File graph (`mcp.c:445-478`). The dashboard renders that variant too
(`graph-ui/src/hooks/useGraphData.ts:39-41`, `MissedCallout.tsx`).

Every one of those descriptions ends with the same sentence in different words: "absence of a flag
is NOT a completeness guarantee". They say the signal is best-effort every single time they offer
it.

Where it lands: `web/` first — Sync already persists `abandon_reason`, and the pattern to copy is
making abandoned attempts a *navigable view* rather than a column someone has to know to query.
Second, the honesty formula: any completeness claim the console makes should carry the same
qualification, because the alternative is a reviewer inferring completeness from silence.

### 2k. Respect the inline tool-result ceiling when sizing a page

The first pass's claim here was right and I can now give it exact lines. VERIFIED at
`codegraph`'s `src/mcp/tools.ts:203-214`:

> the budget is a CEILING (relevance still gates WHAT is included), and it MUST stay under the
> agent's INLINE tool-result cap (~25K chars). Above that, the host externalizes the result to a file
> the agent then Reads back — re-introducing a read AND the cache-write cost — which is exactly what
> a 35K vscode explore did in the n=4 README A/B.

The budget is tiered by project size — `maxOutputChars` 13000 / 18000 / 24000 / 24000 across
`<150`, `<500`, `<5000`, `>=5000` files (lines 215-289) — and never exceeds 24K even for the largest
tier, with the reasoning at 269-272: "a bigger response just externalizes … More files indexed →
more CALLS via `getExploreBudget`, not a bigger single response." A stated invariant at line 213-214
keeps `maxCharsPerFile` monotonic across tiers.

Two enforcement details worth having. The absolute stop is
`Math.min(Math.round(budget.maxOutputChars * 1.5), 25000)` (line 3861) — necessary content may
overflow the soft budget, but nothing crosses 25K. And when it does truncate, it **cuts at a
file-section boundary**, not at the character limit (lines 3864-3873), because "a half-rendered
method just forces the Read this tool exists to prevent"; the trailing marker then names what was
dropped so nothing vanishes silently.

Where it lands: a measurement against `src/sync/mcp/tools.py`, not a change to it. Sync paginates
every list, which is the right rule, but `DEFAULT_LIMIT = 50` is a **row count, not a byte budget**.
A `whats_at_risk` row carries `file`, `line`, `symbol`, `operation`, `vendor`, `change_kind`,
`severity`, `finding_id`, `binding_source`. INFERENCE: fifty of those on a repository with long
paths plausibly clears 25K characters, at which point the host externalises the page, the agent
Reads it back, and pagination has bought nothing. This costs one afternoon to measure against a real
page and is worth doing before assuming the default is fine.

### 2l. If a viewer serves source, let the graph be the allowlist

VERIFIED at `Understand-Anything`'s `packages/viewer/bin/viewer.mjs:13-18`, which states the model
in four lines: binds to `127.0.0.1` only; every data endpoint requires a one-time `?token=` printed
at startup (`crypto.randomBytes(16)`, line 86); node file paths are relativised to the project; and
`/file-content.json` "only serves files listed in the graph, capped at 1 MB, never binary".

That third clause is the one to take. The access-control predicate is *membership in the graph*, not
a path prefix — which is both tighter than a prefix check and self-maintaining, because it is the
same set the UI is allowed to link to.

Related, and relevant if M4 ever ships a shareable artifact: `sanitiseFilePaths` in
`packages/core/src/persistence/index.ts:35-51` rewrites absolute paths to project-relative before
writing, with the reason stated plainly — "the developer's home directory, username, and company
directory layout are never written to knowledge-graph.json". A Sync remediation graph handed to a
prospect would leak the same three things by default.

One caveat on adopting the auth model: the token comparison at `viewer.mjs:332` is a plain `!==` on
strings, not a constant-time compare. On a loopback-bound server that is defensible. It stops being
defensible the moment anything binds to a routable address.

---

## 3. What to deliberately skip, and what adopting it would cost

**A Cypher-like `query_graph`, and `get_graph_schema` beside it.** VERIFIED that
`codebase-memory-mcp` exposes both (`mcp.c:445` and `mcp.c:533`), that `query_graph` takes arbitrary
read-only Cypher with a hard 100k-row ceiling and no offset support, and that `get_graph_schema`
returns node labels and edge types. Sync's design spec rejected exactly this and `tools.py:7-10`
records why: "agents compose arbitrary query languages poorly, and publishing the graph schema as
the interface would make every internal change a breaking change — for a product whose whole claim
is catching breaking changes."

Seeing it built sharpens the argument rather than weakening it, and reading the implementation
sharpens it further. The concrete cost of adopting it is that `schema.sql` becomes public API, so
the grain comments `CLAUDE.md` requires before adding a column stop being internal discipline and
become a compatibility contract — and the `migration_outcome` grain trap (one row is one *attempt*,
not one finding) becomes a mistake every external query author can make and Sync cannot fix.
`codebase-memory-mcp` demonstrates the cost concretely: `store.c:331-338` documents a
schema-compatibility probe that **fails the database open** for any DB created before the
`local_name_gen` edge discriminator, because "SQLite cannot ALTER a table-level UNIQUE constraint in
place". That is the price of a schema that other people's queries depend on. Skip it.

**Collapsing to a single tool.** VERIFIED: `codegraph` defines eight tools but
`DEFAULT_MCP_TOOLS = new Set(['explore'])` (`tools.ts:815`), with the reason at 804-814 — explore is
"the single tool that reliably earns its place", every other tool is "a narrower slice of what
explore already does, and presence itself steers mis-picks, so they are no longer LISTED to agents".
The others stay functional behind `CODEGRAPH_MCP_TOOLS`.

This is measured and deserves to be taken seriously rather than waved off. It still does not
transfer. Their eight genuinely were slices of one another — `callers` and `callees` are one
traversal in two directions. Sync's four are four questions with four different inputs and four
different answer shapes: `whats_at_risk` takes filters and returns bindings, `explain_call_site`
takes a file and a line, `whats_changed` takes a vendor and returns changes with no binding at all,
`propose_patch` runs a pipeline. Merging them produces a tool whose response shape depends on which
arguments were supplied, which is the thing that actually causes mis-picks. Merely different; the
bar for changing a frozen surface is not met.

**Returning verbatim source.** VERIFIED — `codegraph_explore` returns the relevant symbols' verbatim
source grouped by file and tells the agent to treat it as already read (the truncation marker at
`tools.ts:3873` says so explicitly). Coherent for them, because their product *is* the source;
incoherent for Sync, whose product is the binding. The cost is stated in `tools.py:14-16`: "A tool
returning source has handed back the tokens the graph exists to save." Sync already carries the one
deliberate exception — `propose_patch` returning a diff — with an argument for why the diff *is* the
answer there and why that does not license returning the surrounding file. Correctly drawn; do not
widen it.

**Float confidence scores on edges.** The first pass reached this verdict from the README; I reached
it from the code, and the code gives a stronger reason than the design argument did.

Sync's rung is categorical, is an enforced column rather than a join, and the write refuses an
unattributed finding. A float invites a consumer to pick a threshold, and a threshold is an
unattributable filter — a finding dropped at 0.7 cannot be traced to the binder that produced it,
which is the property `.claude/rules/graph-grain.md` exists to protect. Note also that `_shared_rung`
(`tools.py:389-398`) returns `None` rather than the weakest rung on disagreement, on the argument
that understating a rung is still a wrong answer; a float has no equivalent honest-null and would
average instead, which is worse than either option.

The new evidence is section 1's Correction 2: in the one repository that shipped the float, the
float is written on every edge and read by no query, and the third tier the README advertises does
not exist in the source. INFERENCE: that is what happens to an attribution nothing depends on. It is
also a warning about Sync's own future — the rung survives because `open_findings` returns real
values, the write refuses an unattributed finding, and three tools carry it in the response. Remove
any one of those three and Sync gets `confidence_tier`.

**Application-level dedup where a database constraint belongs.** VERIFIED at `code-review-graph`'s
`graph.py:265-297`. `upsert_edge` implements edge identity with a `SELECT` on
`(kind, source_qualified, target_qualified, file_path, line)` and then either an `UPDATE` or an
`INSERT`. The natural key exists in the author's head. It is not in the schema — the `edges` table
(`graph.py:94-105`) has only `id INTEGER PRIMARY KEY AUTOINCREMENT` and no `UNIQUE` — and there is
no index covering the five columns the check queries. INFERENCE: two consequences follow, and the
repository ships a daemon (`daemon.py`, 1,126 lines) and a parallel parse pool, so concurrency is
real. Two writers can both miss on the `SELECT` and both `INSERT`. And the check is a partially
covered index probe per edge on the write path.

`codegraph` hit the same class of bug and fixed it the right way, which makes the pair a clean
before-and-after. `src/db/schema.sql:165-174`:

```sql
-- Edge identity uniqueness. An edge IS uniquely (source, target, kind, line,
-- col); insertEdge uses `INSERT OR IGNORE`, but without something UNIQUE to
-- conflict on it behaved like a plain INSERT, so two passes emitting the same
-- edge produced byte-identical duplicate rows that inflated counts and flowed
-- into callers/impact (#1034). IFNULL folds the nullable line/col so
-- coordinate-less edges (synthesized / file-level) dedup too — SQLite treats
-- each NULL as distinct otherwise. Migration v6 dedups existing rows + adds
-- this on older databases.
CREATE UNIQUE INDEX IF NOT EXISTS idx_edges_identity
  ON edges(source, target, kind, IFNULL(line, -1), IFNULL(col, -1));
```

That is `CLAUDE.md`'s "every table gets a natural key and an explicit conflict clause" — and Sync's
own `efcc19d` — reproduced independently, with the failure mode named: silently inflated counts
flowing into downstream answers. The `IFNULL` detail is a real trap worth carrying over: in SQLite
every NULL is distinct in a UNIQUE index, so a nullable column in a natural key defeats the
constraint exactly on the synthesized rows most likely to be re-emitted.

**Detecting change by mtime and size without a content fallback.** VERIFIED at
`codebase-memory-mcp`'s `src/pipeline/pipeline_incremental.c:661-706`. `classify_files` compares
`stat_mtime_ns(&st) != h->mtime_ns || st.st_size != h->size` and nothing else. The `file_hashes`
table stores a `sha256` (`store.c:238`) and the code computes one carefully elsewhere —
`semantic_manifest_hash_file` (`pipeline_incremental.c:163-209`) even re-stats after reading and
retries once if size or mtime moved mid-read, failing closed on a second race — but that hash is
**not consulted by the classification**. INFERENCE: an edit that preserves byte count within one
filesystem mtime tick is classified unchanged and the graph goes silently stale for that file. This
is the sibling of the rule in Sync's `CLAUDE.md` about never detecting a write by comparing against
a live mtime; here the direction is reversed but the root cause is the same, which is trusting a
timestamp with coarser resolution than the events it is being asked to order.

`codegraph` again does it correctly: VERIFIED that its change decision is content-hash only —
`existingFile.contentHash === contentHash` at `src/extraction/index.ts:2274`, and again at 2635,
2719, 2764 — with `modified_at` stored in `files` but never used to decide. Follow `codegraph`.

**3D layout.** Now VERIFIED to exist rather than REPORTED, and still skip it. `codebase-memory-mcp`'s
`graph-ui` is real, competent work, and reading `src/lib/density.ts` tells you why the aesthetic is
expensive: the whole file exists to fight a failure mode the metaphor creates. Its opening comment
names it — "The white-blob-at-scale failure is dominated by EDGES: they blend additively and a
15k-node graph carries ~80k long lines crossing the center, so their glow stacks into an opaque
wash" — and the fix is scaling edge intensity by `sqrt(2500 / edgeCount)` so total glow stays flat,
plus a separate node-count fade, plus a channel-dominance glow boost because "bloom is
luminance-thresholded, and blue has a tiny luminance weight". Three compensations, all
well-reasoned, none of which would be needed in 2D. The cost of adopting 3D is that budget, spent to
convey strictly less than a good 2D layout with portals.

**A tool description that varies by deployment.** VERIFIED that `codegraph` appends
`"Explore budget: N calls for this project (X files indexed)"` to the response when
`budget.includeBudgetNote` is set (`tools.ts:3840-3845`), scaled by `getExploreBudget(fileCount)`
(lines 145-151, a five-step ladder from 1 call under 500 files to 5 above 25,000). Steering an agent
through the description rather than the response is genuinely clever. Noted rather than adopted: a
description that varies by install makes behaviour non-reproducible across deployments, and Sync has
no per-repository size signal that would drive it. Revisit only with evidence that agents over-call
the read tools.

---

## 4. Who should consult this, and what question it answers

**M4, the operator console — primary consumer.** Question: how does a graph view stay responsive and
honest at scale, and what does an overview-to-one-node interaction look like?

Directly implementable and all VERIFIED against source: 2b (typed repair issues rendered to the
user), 2d (two-stage lazy layout with a memoised size and a deviation gate, plus worker-per-revision
layout), 2e (portal nodes, made directional), 2c (deterministic layout seeds), 2f (record the
grouping strategy), 2i (render the rung as a mechanism sentence), 2j (abandoned attempts as a
navigable view), 2l (graph-as-allowlist and path sanitisation if a shareable viewer ships).

Two stack facts. `Understand-Anything`'s dashboard runs React 19, Vite 6, Tailwind v4,
`@xyflow/react` 12, `@dagrejs/dagre`, `elkjs`, `d3-force`, `graphology`, and `zustand` — VERIFIED
from `packages/dashboard/package.json`. M4 is on Vite + React 19 + Tailwind v4, so their layout and
interaction code reads as a working reference rather than an analogy, and `elkjs` is the first
dependency to look at if M4 has not chosen a layout engine. `codebase-memory-mcp`'s `graph-ui` runs
the same three plus three.js, which makes it a second readable reference even though its render
target is one M4 should not follow.

**The four answers to "the graph is too big to draw", side by side.** This is the comparison the
first pass could not make, and for M4 it is the most useful paragraph in the note.

1. *Containment.* `Understand-Anything` collapses to containers, lays out only what is expanded,
   caches per container, and puts a named portal stub on every edge leaving the level. Best match for
   Sync, because Sync's hierarchy is authoritative rather than discovered.
2. *Aggregate and drill down.* `code-review-graph` (`visualization.py:86-95`, `440-455`) checks
   **both** node and edge counts against `DEFAULT_MAX_FULL_NODES = 3000` and
   `DEFAULT_MAX_FULL_EDGES = 9000`, and above either threshold collapses to community or file
   super-nodes with double-click drill-down. The comment names the bug that forced the second
   threshold: issue #609, "2792 nodes / 17488 edges stalled because only nodes were checked." If M4
   ever caps a view, cap on both counts — the node count alone will not save it.
3. *Budget the fetch, not the render.* `codebase-memory-mcp` computes layout server-side in C and
   ships positioned nodes; the client asks for a node budget (default 5000, user-raisable in 5k steps
   — `graph-ui/src/hooks/useGraphData.ts:26-37`) and streams the response body with live byte
   progress (lines 58-85). Interesting mainly as the one architecture here that does not compute
   layout in the browser.
4. *Do not draw it.* `codegraph`. VERIFIED, confirming the first pass on this point: `src/ui/` is
   terminal chrome (`color.ts`, `glyphs.ts`, `shimmer-progress.ts`, `shimmer-worker.ts`,
   `types.ts`), the dependency list has no graph library, and `grep -rl` for d3/cytoscape/xyflow/
   sigma/three across every `package.json` in the repository returns nothing.

**Honest caveat on the drill-down question.** `codebase-memory-mcp`'s interaction is entirely
client-side over the already-loaded budget: `handleNodeClick` (`GraphTab.tsx:275-304`) selects the
node, walks the loaded edge list to build the set of direct neighbours, highlights them, and flies
the camera to their bounding box. There is no server round-trip for detail, and the function that
was meant to provide one is a stub — `fetchDetail` in `useGraphData.ts:112-127` carries
`/* TODO: detail level with center_node filtering */` and simply refetches the whole graph. So the
overview-to-node path in that repository is "load everything you can afford, then filter locally".
That is a legitimate design for a 5,000-node budget and it does not answer the question M4 actually
has, which is what to do when the interesting node is outside the budget.

**The owner of `src/sync/mcp/tools.py` — secondary consumer.** Question: does anything out there
justify unfreezing the surface?

Two things, both additive. Section 2a: freshness anchored to a commit hash, because `indexed_at`
cannot distinguish a recent index of stale code from a recent index of current code — and take
`code-review-graph`'s failure handling, which returns `None` and forces a rebuild rather than
diffing against a base it cannot verify. Section 2g: an `estimated` flag beside `context_savings`,
because the honesty currently lives in a comment the consumer never sees.

One thing needs measuring rather than deciding — section 2k, whether a 50-row page stays under the
~25K-character inline ceiling, because above it the host externalises the page and the agent reads it
back, silently defeating the pagination rule.

Everything else is a difference that is merely different, and section 3 says so case by case with
the cost.

**M5 or whoever next touches the telemetry rung — the first pass's recommendation is withdrawn.**
The first pass suggested `codebase-memory-mcp`'s `ingest_traces` as a precedent for using telemetry
to validate statically-derived edges rather than to create new ones. VERIFIED that no such precedent
exists: the handler is a stub (Correction 3 above). The *idea* may still be right, but it now has
nothing behind it and should be argued on its merits.

One small thing does survive from that repository and is worth ten minutes. `src/traces/traces.c:
96-111` shows which OTLP span attributes an HTTP path should be read from, in priority order:
`http.route` or `http.target` or `url.path` first, and only then a path extracted from `url.full`.
Preferring `http.route` matters because it is the *templated* route, which is what joins to a
canonicalised operation; deriving the path from `url.full` gives you the concrete instance and a
join that misses. If Sync's correlator reads spans, read them in that order.

---

## 5. What the source says that the documentation does not

This section is why the second pass happened. Everything here was invisible from a README.

**A feature can exist in five translated READMEs and in no source file.** `code-review-graph`
advertises `EXTRACTED / INFERRED / AMBIGUOUS` in `README.md:306`, in Hindi, Japanese, Korean, and
Simplified Chinese, and in `CHANGELOG.md:625` as a shipped schema migration. `AMBIGUOUS` occurs in
zero `.py` files. The float score beside it is written on every edge and read by no query surface.
The general lesson is not that this project is careless — it is that the *documented* existence of a
design idea says nothing about whether the implementation depends on it, and a note built from
READMEs will confidently report convergence with things that are not there. This one mattered
because the first pass used it to claim independent validation of Sync's rung ladder.

**The dedup bug in Sync's `efcc19d` has a public twin, with the failure mode written down.**
`codegraph`'s `schema.sql:165-174` records that `INSERT OR IGNORE` "behaved like a plain INSERT"
because nothing UNIQUE existed to conflict on, producing byte-identical duplicate edges that
"inflated counts and flowed into callers/impact (#1034)". The `IFNULL(line, -1)` fold is the part
nobody writes down: in SQLite each NULL is distinct in a UNIQUE index, so a nullable column in a
natural key silently exempts exactly the synthesized rows most likely to be re-emitted. No README
mentions any of this.

**Everyone who renders a graph reinvents layout determinism, and both write the reason as a
comment.** `Understand-Anything` leaves d3-force's x/y unset "so layouts stay stable for identical,
ordered graph inputs"; `codebase-memory-mcp` derives ring angle and jitter seed from FNV-1a hashes of
the cluster key and the qualified name. Two independent codebases, same conclusion, in comments
rather than docs. That convergence is much stronger evidence for M4 than either alone, and it is
only visible at source.

**The hard part of two-stage layout is terminating it.** Every description of lazy layout describes
the two stages. `GraphView.tsx:903-907` describes the loop they create — Stage 2 discovers a
container's true size, which invalidates the estimate Stage 1 routed edges around — and the >20%
deviation gate that stops it, plus the reason the gate converges (after one re-layout the memoised
size is the actual size, so the next deviation is 0%). The comment at line 822 about capturing
`containerSizeMemory` *before* any write is the kind of ordering detail that only exists because
someone hit it.

**Two of the four ship a stub or a TODO on a path their documentation presents as working.**
`ingest_traces` returns `"Runtime edge creation from traces not yet implemented"`
(`mcp.c:10906-10907`). `fetchDetail` in the same project's dashboard carries
`/* TODO: detail level with center_node filtering */` and refetches the entire graph
(`useGraphData.ts:112-127`). Both are reachable from a documented surface. INFERENCE: at this level
of polish and star count, the base rate of "documented but not implemented" is high enough that a
reference note which does not read the handler is not worth much.

**Coverage gaps are a first-class product surface, and the honesty formula is repeated verbatim.**
`codebase-memory-mcp` records what it could not index in two purpose-built tables with grain comments
explaining why each is separate from the graph, exposes them through three tools and a dedicated
graph variant, and ends every one of those descriptions with a version of "absence from these lists
is NOT a completeness guarantee". A tool that says what it could not do, every time it says what it
did, is a discipline Sync claims in `CLAUDE.md` and can copy at the interface.

**The customer's structure is preferred and the algorithm is the fallback, not the other way
round.** From outside, `Understand-Anything`'s Louvain dependency reads as "it clusters". From
`containers.ts:91-139` it reads as "it groups by folder, and only clusters when folder grouping
produces fewer than two buckets or one bucket over 70%" — and the container it returns declares
`strategy: "folder" | "community"` so downstream can tell which happened. That is a materially
different design from what the dependency list implies, and it is the design Sync should copy.

**The renderer treats its own input as untrusted and says so on screen.** `repairElkInput` performs
five named repairs and `validateGraph` a dozen more, each emitting a typed
`{ level, category, message }`; `WarningBanner` renders them sorted by severity and routes the user
to "fix your graph" or "file a bug on us" depending on whether anything is `fatal`; and in DEV the
repair layer throws instead of repairing. Nothing in the README suggests the dashboard has an
opinion about being lied to. For a console whose product claim is "this is what actually happened",
that opinion is the whole ballgame.

**A parameter name is a liability in a join key.** `pass_route_nodes.c:47-58` throws away route
parameter names on purpose so `:id`, `{customerId}`, and `<int:id>` all reduce to `{}`. Stated
nowhere outside that comment, and it is the closest thing in these four repositories to the problem
Sync's binder solves.

---

## Sources

Cloned and read this session at
`.../b4674d1e-f115-48c1-ab2c-dab217d86019/scratchpad/refs/`:

- https://github.com/DeusData/codebase-memory-mcp — `src/store/store.c`, `src/mcp/mcp.c`,
  `src/pipeline/pipeline_incremental.c`, `src/pipeline/pass_route_nodes.c`, `src/traces/traces.c`,
  `src/ui/layout3d.c`, `graph-ui/package.json`, `graph-ui/src/lib/density.ts`,
  `graph-ui/src/hooks/useGraphData.ts`, `graph-ui/src/components/GraphTab.tsx`
- https://github.com/tirth8205/code-review-graph — `code_review_graph/graph.py`,
  `context_savings.py`, `incremental.py`, `visualization.py`, `scoped_resolver.py`,
  `event_resolver.py`, plus `README.md` and `CHANGELOG.md` for the documentation-versus-source
  comparison
- https://github.com/colbymchenry/codegraph — `src/db/schema.sql`, `src/mcp/tools.ts`,
  `src/db/queries.ts`, `src/extraction/index.ts`, `src/resolution/callback-synthesizer.ts`,
  `src/ui/` listing, `package.json`
- https://github.com/Egonex-AI/Understand-Anything — `packages/core/src/staleness.ts`,
  `packages/core/src/persistence/index.ts`, `packages/core/src/schema.ts`,
  `packages/core/src/analyzer/llm-analyzer.ts`, `packages/dashboard/package.json`,
  `packages/dashboard/src/components/GraphView.tsx`,
  `packages/dashboard/src/components/WarningBanner.tsx`,
  `packages/dashboard/src/utils/{elk-layout,force-layout,force-layout-client,containers,edgeAggregation,layout.worker}.ts`,
  `packages/viewer/bin/viewer.mjs`
- Repository metadata via `gh api repos/{owner}/{repo}` on 2026-08-04
- `src/sync/mcp/tools.py` — the frozen surface every judgement above is measured against
