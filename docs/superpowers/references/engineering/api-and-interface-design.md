# API and interface design, versioning, and compatibility

Reference audit, 2026-08-04. Every claim below is labelled **VERIFIED** (I opened the file this
session and quote a line number), **REPORTED** (a secondary source in the repository asserts it and
I did not independently confirm the behaviour), or **INFERENCE** (my reasoning from what I read).

Clone root, written below as `engrefs/`:
`C:/Users/strol/AppData/Local/Temp/claude/C--Users-strol-orca-Sync-Sync/b4674d1e-f115-48c1-ab2c-dab217d86019/scratchpad/engrefs`

Sync paths are given in full from the worktree root
`C:/Users/strol/orca/Sync/Sync/.claude/worktrees/sync-m4-dashboard/`.

**Coverage.** I examined the interface surface of seven repositories: `codegraph`,
`codebase-memory-mcp`, `code-review-graph`, `claude-cookbooks` (the `cma-mcp` server only),
`Understand-Anything`, `open-code-review`, and `PageIndex`. I examined `superpowers` only for its
version-propagation machinery, which is the one part of it that bears on this dimension, and I did
not audit its skill-frontmatter contract. I did not examine `skills` at all beyond confirming it
ships a single release workflow and no schema validation; treat it as unread for this dimension.
On the Sync side I read `src/sync/mcp/tools.py`, `src/sync/mcp/registry.py`, `src/sync/mcp/server.py`,
`src/sync/api/app.py`, `web/src/api/types.ts`, and `web/src/api/client.ts` in full, and grepped
`tests/` for the contract tests that hold them together.

---

## 1. What this dimension covers, and why it matters here

An interface is the part of a system you cannot refactor unilaterally. Everything behind it is
yours; everything in front of it belongs to someone whose code you cannot see. This dimension asks
four questions of each surface: how is it *defined* (prose, code, or a machine-readable schema), how
is it *versioned*, what a consumer *experiences* when it changes, and whether anything *mechanically
prevents* an accidental change — a golden file, a schema validator, a contract test.

For Sync this is unusually load-bearing, for three reasons that compound.

The first is thematic. Sync's product claim is that it catches breaking API changes in other
people's dependencies. A Sync release that silently breaks its own consumers is not merely a bug; it
is a refutation. `src/sync/mcp/tools.py:8-10` already says this out loud — it rejects a generic
query tool because "publishing the graph schema as the interface would make every internal change a
breaking change -- for a product whose whole claim is catching breaking changes."

The second is that Sync now has **two consumers of one contract, in two languages**. The MCP server
at `src/sync/mcp/server.py` and the Starlette app at `src/sync/api/app.py` both delegate to the same
`GraphSurface` object, so the *logic* is shared. But the payload shapes that come out of
`GraphSurface._envelope` (`src/sync/mcp/tools.py:354-386`) are plain `dict[str, Any]`, and the React
console's view of those shapes is a hand-written TypeScript file whose own docstring admits the
provenance: `web/src/api/types.ts:2` reads *"The shapes `src/sync/api/app.py` returns, written from
the Python responses."* Written from. Not generated from, not validated against.

The third is that the tool set is **frozen by specification**. `src/sync/mcp/registry.py:6-9` says
the design spec "freezes the tool set on first publish: the set may grow and arguments may be added,
but nothing may be removed or renamed," and `tests/golden/tool_schemas.json` is the executable form
of that promise. A freeze is a compatibility commitment, and a commitment you have not tested is a
hope.

---

## 2. The design space, grouped by approach

### 2a. How the tool surface is defined: data, decorators, or derived

There are three distinct answers in the reference set, and they trade the same thing against each
other — whether the published schema is a thing you can diff.

**Static data, hand-written, diffable.** Sync (`src/sync/mcp/registry.py:41-137`) declares four
`ToolSpec` frozen dataclasses in a module-level tuple, and
`schemas_as_data()` (`registry.py:144-149`) renders them to the exact JSON a client receives.
`codegraph` does the same thing in TypeScript: `engrefs/codegraph/src/mcp/tools.ts:547-757` is a
literal `ToolDefinition[]` array of eight tools. `codebase-memory-mcp` does it in C — a `TOOLS[]`
table of struct literals whose `input_schema` fields are JSON string constants, rendered by
`mcp_add_tool_def` at `engrefs/codebase-memory-mcp/src/mcp/mcp.c:725-745`. All three can be pinned
by a golden file, and Sync and codebase-memory-mcp both are. **VERIFIED** for all three.

**Derived from signatures.** `code-review-graph` uses FastMCP:
`engrefs/code-review-graph/code_review_graph/main.py:89` constructs `FastMCP(...)` and there are
**30** `@mcp.tool()` decorators in that one file (counted this session). The schema for each tool is
produced by the framework from Python type hints and the Google-style docstring — see
`main.py:99-149` for `build_or_update_graph_tool`, where seven parameters and their defaults become
the input schema and the `Args:` block becomes the per-argument descriptions. **VERIFIED.** This is
the cheapest thing to write and the hardest thing to freeze: `registry.py`'s own comment
(`src/sync/mcp/registry.py:8-9`) names exactly this trade — "a golden file can diff data, and cannot
diff a decorator's behaviour." Renaming a Python parameter in code-review-graph is a published
breaking change with no test standing in the way. **INFERENCE**, but a direct one.

**Declared once in a validator library, reused by every transport.** The Anthropic cookbook's
`cma-mcp` is the cleanest instance and the most directly applicable to Sync's situation.
`engrefs/claude-cookbooks/managed_agents/cma-mcp/src/tools.ts:10` exports a single
`registerTools(server)` function — its docstring says *"Shared by stdio + HTTP entrypoints"* — whose
arguments are zod schemas (`tools.ts:17-19`, `min(1).max(200)` and `.describe(...)`). The stdio
entry point (`src/server.ts:8`) and the Streamable-HTTP entry point (`src/server-http.ts:22`) each
construct an `McpServer` and call that same function. **VERIFIED.** One declaration produces three
artifacts: the JSON Schema in `tools/list`, the runtime argument validator, and the TypeScript type
of the handler's parameter. Sync's `registry.py` produces only the first of those three.

### 2b. Versioning: nobody versions the payload, everybody versions the protocol

This is the most striking finding in the set, and it is an absence.

**Not one reference repository publishes a versioned schema for what its tools return.**
`codebase-memory-mcp` comes closest and then declines: `mcp.c:732` attaches an `outputSchema` to
every advertised tool, and `mcp.c:673` defines it as
`{"type":"object","additionalProperties":true}` — one shared constant, identical for all fourteen
tools, asserting nothing beyond "the result is an object." **VERIFIED.** Its purpose is visible at
`mcp.c:303-310`: because the spec requires `structuredContent` to conform to a declared
`outputSchema`, the code wraps even plain-text and error results in `{"text": ...}` or
`{"error": ...}` so the trivial schema is never violated. This is compliance plumbing, not a
contract.

What *is* versioned everywhere is the database schema behind the API — `code-review-graph`'s
`migrations.py:16` `get_schema_version`, `codegraph`'s `src/db/migrations.ts:12`
`CURRENT_SCHEMA_VERSION = 8` — and the MCP protocol revision. That second one produces a real
divergence worth naming:

- `codebase-memory-mcp` **negotiates**. `src/mcp/mcp.c:1195-1204` lists four supported revisions
  newest-first (`2025-11-25`, `2025-06-18`, `2025-03-26`, `2024-11-05`), and
  `cbm_mcp_initialize_response_for_profile` at `mcp.c:1235-1255` reads the client's requested
  `protocolVersion` out of the initialize params and echoes it back when it is one of the four,
  falling back to the newest otherwise. The comment states the rule: *"if client requests a version
  we support, echo it back; otherwise respond with our latest."* **VERIFIED.**
- `codegraph` **pins deliberately low**. `src/mcp/session.ts:58` sets
  `PROTOCOL_VERSION = '2024-11-05'` — the oldest revision — while
  `src/mcp/tools.ts:468-479` advertises `annotations`, a field introduced in `2025-03-26`, with an
  explicit justification: *"The field is purely additive — a client that predates annotations
  ignores it — so codegraph advertises these even though `initialize` still negotiates the
  2024-11-05 protocol version."* **VERIFIED.** That is a coherent compatibility strategy: floor the
  negotiated version, layer additive fields on top.
- **Sync does neither.** `src/sync/mcp/server.py:51` sets `PROTOCOL_VERSION = "2025-06-18"` and
  `server.py:141-155` answers `initialize` with that constant without ever reading
  `params["protocolVersion"]`. **VERIFIED** by reading the whole handler. The module docstring at
  `server.py:50-51` says the version is *"Reported back at initialize so a client can refuse a
  server it cannot speak to, rather than discovering the mismatch per call"* — which describes
  negotiation, and the code does not do it.

Package versioning is likewise uniform and unremarkable: `codegraph/src/mcp/version.ts` resolves the
version from `package.json` once at load and falls back to the sentinel `"0.0.0-unknown"` so a
version mismatch fails safe rather than accidentally matching (**VERIFIED**, `version.ts:35`).
`superpowers` solves the "one version, seven files" problem with a declared manifest —
`engrefs/superpowers/.version-bump.json` lists seven `(path, field)` pairs, and
`scripts/bump-version.sh` writes them all, then greps the whole repository for stragglers with a
declared exclude list (`bump-version.sh:94-162`, and the bump command runs `cmd_audit` afterwards at
line 191-193). **VERIFIED.** That is the cheapest possible codegen: not generating the copies, but
mechanically proving no undeclared copy exists.

### 2c. The one repository that publishes a real schema, and what it cost

`Understand-Anything` publishes `docs/benchmarks/large-repo-report-1.0.0.schema.json` — a JSON Schema
2020-12 with a stable `$id` URL pointing at the raw GitHub path, `additionalProperties: false`, a 19-
entry `required` list, and two self-describing constants inside every instance: `schemaUrl` pinned by
`"const"` to the `$id`, and `"schemaVersion": { "const": "1.0.0" }` (**VERIFIED**, lines 2-31). The
version is in the filename, in the `$id`, and in the payload. A consumer holding a report can tell
which contract it was written against without asking anyone.

It is backed by a real contract test:
`engrefs/Understand-Anything/tests/benchmark/test_large_repo_report_schema.test.mjs:1-27` compiles
the schema with Ajv 2020 (`allErrors: true`) and defines both `expectValid` and `expectInvalid`
helpers, then builds a canonical valid instance and mutates it. **VERIFIED.** This is the only
place in the reference set where a payload shape is mechanically defended.

The cost is honest and worth naming: it is a *benchmark report*, not an API. It is written once per
run by one producer and read by scripts. Applying the same machinery to five HTTP routes and four
MCP tools is a larger job, and `additionalProperties: false` means every additive field is a schema
edit. **INFERENCE.**

### 2d. Pagination and the response-too-large problem

Every serious MCP server here has been burned by context size, and their fixes fall into three
layers.

**Bounding the input.** `codegraph` caps free-form strings at 10 000 characters and paths at 4 096
(`src/mcp/tools.ts:66-83`), with the reason stated: *"without this an attacker could ship a 100MB
string and force a full FTS5 scan / OOM the server"* (`tools.ts:71-75`). It is regression-tested:
`__tests__/integration/mcp-input-limits.test.ts` asserts oversize `query`, `symbol` and
`projectPath` all come back `isError: true` with a `/maximum length/i` message. **VERIFIED.**
**Sync validates no string length anywhere on the MCP path** — `whats_at_risk` takes `path`,
`vendor` and `severity` as unbounded strings (`src/sync/mcp/tools.py:89-96`) and `dispatch` passes
them straight through (`registry.py:152-162`). **VERIFIED by absence.**

**Bounding the output, with a measured ceiling.** This is codegraph's best work.
`src/mcp/tools.ts:203-296` returns a tiered `ExploreOutputBudget` keyed on project file count, and
the comment at `tools.ts:204-214` explains the number: the budget *"MUST stay under the agent's
INLINE tool-result cap (~25K chars). Above that, the host externalizes the result to a file the
agent then Reads back — re-introducing a read AND the cache-write cost — which is exactly what a 35K
vscode explore did in the n=4 README A/B. So even large repos cap at ~24K."* **REPORTED** as to the
A/B measurement; **VERIFIED** that the code implements it. The design consequence they draw is the
important one: a larger index buys you *more calls* (`getExploreBudget`, `tools.ts:145-151`), never
a bigger single response. `codebase-memory-mcp` reaches the same conclusion from the other side —
`src/mcp/mcp.c:5065-5077` records that `get_architecture`'s old default rendered every aspect
including the full file tree, *"~94KB (~23K tokens) on a mid-size repo, a context bomb for the LLM
consumers,"* and the default is now a three-aspect summary with the full set behind an explicit
argument. **VERIFIED.**

**Truncation that announces itself.** codebase-memory-mcp never truncates silently. It carries
`total` + `has_more` on offset-paged tools (`mcp.c:2971`, `3014`, `3456`), `truncated: true` plus a
raise-the-limit hint on traces (`mcp.c:6621`, `6658`), and a `truncated` boolean beside every capped
list even in coverage output (`mcp.c:3927-3945`, `7023`). Its server `instructions` string, returned
at initialize (`mcp.c:1206-1216`), ends with the sentence *"Check has_more or nextCursor and
paginate when present."* **VERIFIED.**

**Cursors that refuse to lie.** The single best pagination design in the set is
`trace_cursor_decode` at `engrefs/codebase-memory-mcp/src/mcp/mcp.c:6087-6122`. The cursor is an
opaque token `c1.<leg>.<generation>.<qhash>.<hop>.<node_id>` (encoder at `mcp.c:6082-6085`) carrying
two guards. `qhash` is an FNV-1a hash of every traversal-defining argument
(`trace_params_hash`, `mcp.c:6064-6080`) — replay a cursor with a changed argument and you get
`"cursor_params_mismatch: this cursor was issued for different arguments — pass the cursor back with
ALL other arguments identical"`. `generation` is the index generation — reindex between pages and
you get `"stale_cursor: the project was reindexed since this cursor was issued — re-run the original
query without 'cursor' (node identities changed)"`. The comment above the hash states the principle:
*"A cursor replayed with different params must fail loudly, never silently mis-skip."* **VERIFIED.**

Sync paginates with a bare integer. `GraphSurface._page` (`src/sync/mcp/tools.py:331-352`) slices
`rows[offset:offset+limit]` and returns `next_offset`, computed from an in-memory list rebuilt by
`self._graph.open_findings()` on every call. **VERIFIED.** A DETECT run landing between an agent's
first and second page shifts every row; the agent silently skips or double-counts findings, and
nothing in the payload can tell it that happened. **INFERENCE**, and I consider it the most likely
real-world defect in Sync's current surface after the type-drift problem.

### 2e. Behavioural declarations: annotations and instructions

Both mature MCP servers declare per-tool behaviour that clients gate on, and Sync declares none.

`codegraph` defines a shared `READ_ONLY_ANNOTATIONS` constant
(`src/mcp/tools.ts:531-536`: `readOnlyHint: true, destructiveHint: false, idempotentHint: true,
openWorldHint: false`) and attaches it to all eight tools. The motivating comment
(`tools.ts:520-530`) is concrete: *"Cursor's Ask mode ... rejects any MCP tool lacking
`readOnlyHint: true`"* — without the annotation, read-only tools were blocked in that client.
`__tests__/mcp-tool-annotations.test.ts` then pins the contract through **every** transform that can
produce a `tools/list` response — the master array, `getStaticTools()`, the live `getTools()` which
rewrites a description via spread, and `withRequiredProjectPath()` which clones the schema — because
*"a drop in any of those would silently re-block the tools in Ask mode"* (test docstring, lines
9-15). **VERIFIED.** That is a compatibility test written against the *failure mode*, not the code.

`codebase-memory-mcp` does the same in a per-tool table (`mcp.c:700-745`), and its defaults are the
safe ones: a tool missing from `TOOL_ANNOTATIONS` gets `readOnlyHint: false`, `destructiveHint:
true`, `openWorldHint: true` (`mcp.c:737-740`). **VERIFIED.** Both servers also return an
`instructions` string at initialize (`mcp.c:1282`; `codegraph/src/mcp/proxy.ts:312`).

Sync's `ToolSpec` (`src/sync/mcp/registry.py:33-38`) has four fields — `name`, `description`,
`input_schema`, `handler` — and `schemas_as_data()` emits three of them. No `annotations`, no
`title`, no `outputSchema`, and `server.py`'s initialize result (`server.py:142-155`) carries no
`instructions`. **VERIFIED.** This is a live compatibility gap, not a theoretical one: three of
Sync's four tools are strictly read-only and the fourth is documented as never writing to the
repository (`server.py:21-23`), which is exactly the claim `readOnlyHint` exists to make, and there
is a client in the wild that refuses tools which do not make it.

### 2f. Sync's actual two-consumer problem, and what each reference would cost to copy

The problem, precisely. `GraphSurface` returns `dict[str, Any]`. The HTTP transport passes those
dicts to `JSONResponse` unchanged (`src/sync/api/app.py:104`, `142`) or hand-composes a new dict
(`app.py:89-97`, `126-134`). The console declares eleven interfaces describing those payloads in
`web/src/api/types.ts` and casts into them without checking: `getJson<T>` at
`web/src/api/client.ts:57` is `return (await response.json()) as T`. **VERIFIED.** A `TypeScript`
cast is a compile-time assertion about a runtime value the compiler has never seen. Rename
`change_kind` to `kind` in `tools.py` and: the Python tests pass, `tsc -b` passes, oxlint passes, and
the console renders `undefined` in a column.

What holds them together today is two regex assertions in Python that reach across the language
boundary. `tests/test_api_routes.py:419-424` asserts `web/src/api/client.ts` still declares a
`DEFAULT_LIMIT`, and `tests/test_dashboard_queries.py:401-403` asserts a *comment* in
`web/src/api/types.ts` still states the workflow node order. **VERIFIED.** Both are real and both
are honest about being stopgaps — but between them they defend one integer and one English sentence,
and not a single field name or type.

Four answers exist in the reference set, in increasing order of cost:

1. **Runtime validation at the consumer boundary, no shared artifact.** Nobody in the set does this
   for API responses. `Understand-Anything` uses zod for internal domain enums
   (`understand-anything-plugin/packages/core/src/schema.ts:1-15`, a 38-value `EdgeTypeSchema`) but
   not on a network boundary. **VERIFIED by absence.** Cost: one zod schema per response type,
   written in TypeScript, still hand-transcribed — it converts a silent wrong render into a loud
   parse error, which is strictly better, but it does not stop drift.
2. **One transport-agnostic declaration reused by both entry points.** `cma-mcp` (`src/tools.ts:10`
   shared by `server.ts:8` and `server-http.ts:22`). Cost: near zero, and Sync already has the
   equivalent for *logic* — both transports call one `GraphSurface`. It does not solve the
   cross-language half, because the shared declaration is TypeScript on both sides there.
3. **A published, versioned JSON Schema plus a validating contract test.**
   `Understand-Anything`'s `large-repo-report-1.0.0.schema.json` + the Ajv test. Cost: a schema per
   response type, kept honest by validating real payloads in CI on both sides. This is the only
   option in the set that a *third party* could also consume, which matters for an open-core product
   whose plugin story is a stated goal.
4. **A generated artifact.** Nobody in the set generates types across a language boundary. I
   grepped every `package.json`, `pyproject.toml` and `requirements.txt` in all nine clones for
   `openapi`, `json-schema-to-typescript`, `quicktype`, `datamodel-code-generator`, `typia` and
   `io-ts`, and the only hits were prose in design documents. **VERIFIED by absence.** The closest
   working mechanism anywhere here is `superpowers`' `.version-bump.json` + audit grep — declare the
   copies, write them from one source, then prove no undeclared copy exists.

---

## 3. What Sync should adopt

Ordered by value per unit of work. Each names the file that proves the pattern works and the exact
Sync file it lands in.

**A. Declare `outputSchema` on each tool, generate the TypeScript from it, and let one artifact serve
both consumers.** This is the answer to the highest-value question in the dimension, and it is worth
noting that no reference implements it well — `codebase-memory-mcp/src/mcp/mcp.c:673` shows the
degenerate version (`additionalProperties: true`, identical for every tool), which is what you get if
you add the field without meaning it. The pattern that *is* proven is
`Understand-Anything/docs/benchmarks/large-repo-report-1.0.0.schema.json` (self-describing
`schemaVersion` const, `additionalProperties: false`, stable `$id`) validated by
`tests/benchmark/test_large_repo_report_schema.test.mjs`. In Sync: define the four response shapes
as Pydantic v2 models in a new `src/sync/mcp/responses.py`; have `GraphSurface._envelope`
(`src/sync/mcp/tools.py:354`) and `_page` (`tools.py:331`) construct them; add an `output_schema`
field to `ToolSpec` (`src/sync/mcp/registry.py:33-38`) fed by `model_json_schema()`; emit it from
`schemas_as_data()` (`registry.py:144`) so `tests/golden/tool_schemas.json` starts pinning the output
half as well as the input half. Then generate `web/src/api/types.ts` from the same JSON Schema and
delete the hand-written file, or — if generation is too much machinery for one console — keep the
file and add a CI step that validates it against the schema, in the spirit of
`superpowers/scripts/bump-version.sh:94-162`. Note that Sync already emits `structuredContent` on
every tool result (`src/sync/mcp/server.py:233`) with no `outputSchema` declared, which is the half
of the 2025-06-18 contract that costs you nothing and gives the client nothing.

**B. Negotiate the protocol version instead of asserting it.** Proven by
`codebase-memory-mcp/src/mcp/mcp.c:1195-1255` — a newest-first list plus echo-if-supported. Lands in
`src/sync/mcp/server.py:141-155`, which currently ignores `params` entirely: turn
`PROTOCOL_VERSION` into a tuple, read `params.get("protocolVersion")`, echo it when it matches, fall
back to element zero. Two of Sync's `initialize` fields are already conditional-free constants;
this is the one that must not be.

**C. Annotate every tool read-only, and test the annotation survives every path that builds
`tools/list`.** Proven by `codegraph/src/mcp/tools.ts:531-536` and defended by
`codegraph/__tests__/mcp-tool-annotations.test.ts`, whose docstring names the real client that
blocks unannotated tools. Lands as a fifth field on `ToolSpec` (`src/sync/mcp/registry.py:33-38`)
plus a `READ_ONLY` constant; Sync has one path to `tools/list` rather than codegraph's three, so the
test is smaller. `sync_propose_patch` is the interesting case — it is `readOnlyHint: false`,
`destructiveHint: false`, `idempotentHint: false`, `openWorldHint: false`, because it runs a
pipeline and writes nothing (`src/sync/mcp/tools.py:216-231`), and saying so precisely is more useful
to a client than either extreme.

**D. Make the pagination cursor refuse a stale replay.** Proven by
`codebase-memory-mcp/src/mcp/mcp.c:6064-6122`. Lands in `GraphSurface._page`
(`src/sync/mcp/tools.py:331-352`): replace the integer `next_offset` with an opaque token carrying
the offset, a hash of the filter arguments, and a graph generation stamp — the DETECT run id, or a
`max(indexed_at)` the store can already produce. On mismatch return a teaching error rather than a
page. Sync's `_page` currently has no way to know a page came from a different graph than the one
before it, and `whats_at_risk` re-reads `open_findings()` on every call. Sync's `_MAX_LIMIT = 500`
cap exists only on the HTTP transport (`src/sync/api/app.py:37`); the MCP path honours whatever it is
handed.

**E. Bound free-form string inputs, and regression-test the bound.** Proven by
`codegraph/src/mcp/tools.ts:66-83` and `__tests__/integration/mcp-input-limits.test.ts`. Lands in
`dispatch` (`src/sync/mcp/registry.py:152-162`) or in the argument-validation step the transport
already has a place for — `server.py:222-224` already converts a `TypeError` from a bad argument into
a retryable tool error, which is the right shape for a length refusal too.

**F. Report freshness as a claim, not a timestamp.** `code-review-graph`'s `_graph` envelope
(`code_review_graph/tools/_common.py:108-120`) carries `built_at_sha`, the live `head_sha`, and a
derived `head_matches_build` boolean. **VERIFIED.** Sync's `_envelope` reports `indexed_at` and
`feed_fetched_at` as ISO timestamps and leaves the agent to decide whether that is fresh
(`src/sync/mcp/tools.py:361-366`). A boolean answers the question the agent is actually asking. Two
qualifications: `graph_provenance` in that file swallows every exception and returns `None`, so its
provenance can vanish silently — do not copy that part — and Sync's timestamps-not-durations
reasoning at `tools.py:361-363` is correct and should stay; `head_matches_build` is an addition, not
a replacement.

---

## 4. Where Sync is already ahead, and where a reference would be a step backwards

**Sync's provenance envelope is structural; every reference's is optional.** Every payload
`GraphSurface` returns goes through `_envelope` (`src/sync/mcp/tools.py:354-386`), so `indexed_at`,
`feed_fetched_at`, `binding_source` and `context_savings` cannot be forgotten by a new tool.
`code-review-graph` wraps opt-in at each call site (`with_provenance(...)` in
`main.py:139-146`), and `_common.py:122-123` catches bare `Exception` and returns `None` — a
provenance envelope that disappears when the metadata read fails is worse than one that is always
absent, because a consumer learns to expect it. `codegraph` and `codebase-memory-mcp` carry
freshness as *prose banners* prepended to text output (`codegraph/src/mcp/tools.ts:444-451`
`formatDegradedBanner`; the staleness banner at `tools.ts:398`), which an agent must read rather than
branch on. Sync's per-row `binding_source` (`tools.py:132-135`) and the `_shared_rung` rule that
returns `None` when a page mixes rungs (`tools.py:389-398`) have no analogue anywhere in the set.
**VERIFIED.** Do not trade this for anything.

**Four tools beats thirty.** `code-review-graph` advertises 30 tools from one module
(`main.py`, counted this session); `codebase-memory-mcp` advertises 14 (`mcp.h:4`) and has had to
build three *tool profiles* — `ALL`, `ANALYSIS`, `SCOUT` (`mcp.h:106-112`) — with three separate
instruction strings (`mcp.c:1206-1233`) to keep the surface manageable per client. `codegraph`
ships 8 and gates them behind a `CODEGRAPH_MCP_TOOLS` allowlist env var
(`src/mcp/tools.ts:796-799`). Every one of those is machinery for a problem Sync does not have. A
frozen four-tool surface is the compatibility strategy; adopting a profile system would be paying
maintenance for optionality nobody asked for. **INFERENCE**, well supported.

**Sync's "never return file contents" rule is stronger than any reference's, and it is the reason
the response-budget machinery is unnecessary here.** codegraph's entire tiered
`ExploreOutputBudget` (`tools.ts:203-296`, five tiers, eleven knobs, with `ITER3` comments recording
a reverted experiment at `tools.ts:217-221`) exists because `codegraph_node` and `codegraph_explore`
return *verbatim source* — `codegraph_node`'s description explicitly positions it as a Read
replacement (`tools.ts:651`). Sync returns bindings (`src/sync/mcp/tools.py:14-16`), and a binding
row is a few hundred bytes. Copying the budget machinery would be importing a solution to a problem
Sync designed away. What is worth importing is the *number* — the ~25K-char inline tool-result
ceiling above which a host externalizes the result (`tools.ts:204-209`) — as a ceiling Sync's default
`limit` of 50 (`tools.py:33`) should be checked against, not as a tiering system.

**Sync writing its own JSON-RPC framing was the right call and should not be revisited.**
`server.py:8-14` justifies it by dependency hygiene: the `mcp` package is present only transitively
via `claude-agent-sdk` and could vanish in a bump. That reasoning is sound and is reinforced by what
`cma-mcp` costs — it takes `@modelcontextprotocol/sdk` plus `zod` plus Bun as a runtime
(`engrefs/claude-cookbooks/managed_agents/cma-mcp/package.json`), and `codebase-memory-mcp` wrote its
own in C rather than depend on anything. **VERIFIED.** The adoption in §3A does not require the SDK:
Pydantic is already a Sync dependency and `model_json_schema()` produces the JSON Schema without any
MCP library involved.

**A step backwards worth naming explicitly: derived-from-signature schemas.** `code-review-graph`'s
FastMCP decorators are pleasant to write and would delete most of `registry.py`. They would also
delete `tests/golden/tool_schemas.json`'s ability to mean anything, because the golden file's value
is that a renamed argument is a failing test rather than a silent published breaking change. Given
that `registry.py:6-9` records a *specification-level freeze* on the tool set, this trade is not
close. **INFERENCE.**

**And one where Sync is behind in a way that looks like being ahead.** `web/src/api/types.ts` is
better *documentation* than any type file in the reference set — `types.ts:101-112` explains why
`FindingIdentity.binding_source` and the envelope's `binding_source` are two fields with two meanings
and must not be merged; `types.ts:141-155` explains why `running` is carried in `WorkflowOutcome`.
That quality is exactly what makes the drift dangerous: a reader trusts it, and nothing keeps it
true. The most useful thing that file could gain is not more prose but a build step that fails when
it stops matching `tools.py`.

---

## 5. Open questions only the owner can settle

1. **Is the console a consumer or an implementation detail?** If the React app is the only HTTP
   client Sync will ever have, generating types is over-engineering and a runtime validator on
   `getJson` (`web/src/api/client.ts:57`) plus a CI diff is enough. If a customer will ever write
   against `/api/*`, then `/api/*` is a published API and needs a version in its path or its payload
   — and the frozen-tool-set discipline in `registry.py:6-9` should extend to it. Nothing in the
   repository states which of these is intended, and the two answers have very different costs.

2. **Do the MCP surface and the HTTP surface share one contract or two?** They currently share
   `GraphSurface` and diverge at the edges: `/api/overview` composes a payload by hand
   (`app.py:89-97`) and is the one route that omits `context_savings` — which
   `web/src/api/types.ts:34-39` has already had to encode as an optional field. Every such
   divergence is a place a generated type must special-case. Is `/api/overview` a missing
   `GraphSurface` method, or is the HTTP surface allowed its own shapes?

3. **What is the compatibility promise on `binding_source`?** `FindingRung` currently admits five
   values (`web/src/api/types.ts:16-21`). Adding a sixth is a breaking change for any consumer that
   exhaustively switches on it, and the console does. Is the rung vocabulary frozen like the tool
   set, is it explicitly open with a documented fallback branch, or does adding a rung require a
   version bump? `.claude/rules/graph-grain.md` governs the column; nothing governs the wire value.

4. **Should `next_offset` become an opaque cursor now or when it bites?** The stale-page defect is
   real (§2d) but is currently invisible — a single-user local deployment where DETECT runs between
   pages is rare. The cursor costs a generation stamp the graph must expose and a teaching error the
   console must render. Fixing it after M4 means a wire-format change to a field the console already
   consumes.

5. **What does `sync_propose_patch` promise across versions?** It is the one tool that returns
   source (`tools.py:222-227`) and the one whose `outcome` vocabulary (`propose.UNAVAILABLE` and the
   values `run_to_static_verify` writes) is not pinned by the golden file, since the golden file
   holds inputs only. If a new outcome value ships, does a client that has not been updated fail
   loudly or fall through silently? That question is not answerable from the current code.
