# Sync — The Graph Surface

**Date:** 2026-07-25
**Status:** Approved design. Partly implemented: `src/sync/mcp/tools.py` provides `GraphSurface`
with the three read tools (`whats_at_risk`, `explain_call_site`, `whats_changed`).
`sync_propose_patch`, the `sync://feed/{vendor}` resource, `FeedCache`, and any server transport
are not built — the module is tool logic over a `GraphReader`, not a running MCP server.
**Scope:** How the API Dependency Graph is exposed to consumers, given that the binding rather than the repair
is what Sync sells.

## Context

`2026-07-25-sync-positioning-and-open-core.md` decided that Sync sells the binding between a codebase and the
third-party operations it depends on. That decision left a question it did not answer: if the binding is the
product, what does a customer actually touch? The design document describes a dashboard and a stream of pull
requests, both of which are surfaces for a product whose output is repair.

This specifies the surface for a product whose output is a binding.

Three facts from `2026-07-25-sync-competitive-position.md` and subsequent research set the frame:

- By mid-2026 the category converged on structured context layers — central services many agents query. MCP is
  the integration standard: 78% of enterprise AI teams run at least one MCP-backed agent in production, and
  monthly MCP server downloads grew from roughly 100,000 in November 2024 to 97 million by March 2026.
  Commercial context-provider MCP servers are an established business.
- Datadog's Software Catalog already auto-discovers third-party API dependencies from outbound requests and
  exposes them at `/api/v2/catalog/entity`. **Service-level dependency discovery is taken.** What no product
  offers is call-site granularity: `src/billing.ts:6` depends on `POST /v1/charges` and reads its `status`
  field.
- GitHub's dependency graph is package-level, default-branch only, capped at 150 manifests, unable to resolve
  variables in manifests, and has published empirical work on its inaccuracy. It is complementary rather than
  competitive.

Sync's differentiation must be stated at call-site resolution or a larger company answers the question first.

## Decisions

| Decision | Choice | Consequence |
|---|---|---|
| Primary consumer | Agents, over MCP | Agent platforms become consumers rather than competitors |
| Does Sync act | No. It returns a verified patch as data | Sync needs no repository write access from a caller |
| Deployment | Local first, hosted later | An adoptable product exists before the control plane does |
| Tool surface | Question-shaped tools, not a query language | The internal schema is never the interface |
| Local store | `GraphStore` protocol, SQLite locally | Local mode adds no dependency; `sqlite3` is in the standard library |

## Two things called MCP

These will be confused permanently unless the names are fixed now.

**The MCP adapter** — Sync watches *other* MCP servers for tool-schema drift. An inbound signal source, one
implementation of `VendorAdapter`. Specified by `2026-07-25-sync-mcp-drift-measurement.md`.

**The MCP server** — Sync exposes *itself* to agents. An outbound surface. This document.

They share the change taxonomy — `tool_removed`, `param_removed`, `param_added_required`, `param_tightened`
and their non-breaking counterparts — which is why building them adjacently costs less than building either
alone. Sync watching MCP servers while being one is also the cheapest available proof that the product works.

## The tool surface

Four tools. The set is frozen on first publish and may only grow, for reasons given under Stability.

```
sync_whats_at_risk(path?, vendor?, severity?)
  → [{file, line, symbol, operation, vendor, change_kind, severity, finding_id}]

sync_explain_call_site(file, line)
  → {symbol, operation, vendor, args_keys, response_fields_read,
     sdk_version, binding_source, known_changes[]}

sync_whats_changed(vendor, since?)
  → [{operation, change_kind, path_ptr, severity, from_version, to_version, published_at}]

sync_propose_patch(finding_id)
  → {diff, static_verify: {passed, diagnostics},
     evidence: {spec_diff, changelog, call_sites}}
```

One resource: `sync://feed/{vendor}`, the normalized change feed, served from the server's local cache. The feed
is *published* separately from this server and merely *consumed* by it — see Feed separation below, which is a
data-boundary decision rather than a packaging one.

Each tool answers a question an agent actually has. A generic query tool was rejected: agents compose arbitrary
query languages poorly, and publishing the graph schema as the interface would make every internal change a
breaking change — for a product whose entire claim is that it catches breaking changes.

### Provenance is part of every response

Every response carries `indexed_at`, `feed_fetched_at`, and `binding_source`. The first two are ISO-8601
timestamps of when the index was last built and the feed last fetched — timestamps rather than durations, so a
cached response cannot report a freshness that has since expired.

`binding_source` is a three-rung ladder. Each rung is strictly more trustworthy than the one below, costs more
to produce, and is reported honestly rather than smoothed over:

| Value | How the mapping was established | Cost |
|---|---|---|
| `static` | Tree-sitter syntax plus vendor naming conventions. Derived, not confirmed. | Milliseconds |
| `resolved` | The TypeScript compiler resolved the symbol to its declaration through aliases and wrappers. | Seconds to minutes, once per repository |
| `observed` | A client span carrying the call site's source location confirmed which endpoint it actually hits. | Requires production telemetry |

An agent weighs a patch differently depending on which rung produced the binding, and it can only do that if the
rung is in the payload. `observed` appears only in the hosted tier, because a laptop has no production traffic.

### Response shaping

Token efficiency in a graph server comes from what is returned, not from how the index was built. Published
comparisons of graph-backed exploration against file-by-file reading report roughly an order of magnitude fewer
tokens and about half the tool calls at comparable answer quality, and the savings come entirely from returning
structure instead of source.

Four rules, which are also the 2026 consensus on MCP tool design:

- **Never return file contents.** The binding is the answer. A tool that returns source has given back the
  tokens the graph exists to save.
- **Shallow by default, with drill-down references.** Return the call site and its operation; return the full
  change history only when asked for it by identifier.
- **Pagination is mandatory on every list-returning tool.** An unbounded result on a large repository silently
  consumes an agent's context before the model has processed anything.
- **Emit `context_savings` on every response** — an estimate of the tokens an equivalent file-exploration would
  have cost. It makes the product's value visible inside the payload, and it is the measurement behind the
  efficiency claim rather than an assertion of it.

Four tools also sits well inside the 10 to 15 tool ceiling above which agents measurably degrade at selection.

This is not diagnostics. An agent acting on a stale or derived binding writes a wrong patch, and it cannot
weigh that risk against an answer that hides it. Freshness is data.

It also makes the commercial boundary legible inside the payload: `observed` can only appear in the hosted
tier, because a laptop has no production spans.

### Stability

**Sync cannot ship a breaking tool change.** A product that catches vendor breaking changes and then renames
its own parameters is finished, and no explanation recovers it.

Therefore: the tool schema is versioned from first publish; parameters are never removed or renamed; new
capability arrives as new optional parameters or new tools; and a golden-file test fails the build on any
removal or rename. Sync's own drift detector watches Sync's own server.

## Architecture

```
tree-sitter index ─┐
                   ├──► GraphStore ──► tools ──► MCP client (any agent)
public change feed ┘                      │
                                          └─ sync_propose_patch ─► remediate ─► tsc ─► diff returned
```

Local mode requires no Postgres, no authentication, and no network beyond fetching the feed. That is the whole
distribution argument: a developer installs it in one command and gets an answer in the same minute.

`sync_propose_patch` runs the existing remediation pipeline as far as static verification and stops. No branch,
no push, no forge involvement. The customer's CI remains the merge gate — it simply runs later, on the calling
agent's own commit. The verification promise is unchanged and Sync holds nothing.

### Indexing: what fills the graph

Not part of this surface, but it determines what the surface can answer, so it is recorded here and scheduled
alongside.

Tree-sitter is a syntax-level parser and cannot resolve a symbol to its definition. The hard cases the design
document already lists — aliased imports, a client reached through a helper function, destructured responses —
are cross-file resolution failures, not symbol-map failures, and no further tree-sitter work resolves them. The
Language Server Protocol is the obvious remedy and the wrong one: it resolves a single position per request
with no batch API, which makes indexing a large TypeScript project slow.

The TypeScript Compiler API loads a whole project into one in-process compiler and returns AST, semantic
information, and module resolution with no RPC. That was too slow to consider until recently. TypeScript 7.0
went stable on 2026-07-08 with a Go-native compiler roughly ten times faster than its predecessor — VS Code's
400,000-line repository now typechecks in 8.74 seconds against 89 before.

The efficient shape is therefore two passes, using each tool for what it is good at:

```
tree-sitter    scan the repository for candidate member-chain call expressions   ~15 ms, ~5 MB
TS compiler    resolve only those candidates to their declarations               seconds, once per repository
content_hash   skip unchanged files on reindex                                   already in the schema
```

Published work puts standard resolution at roughly 80% of calls in well-structured codebases, with cross-module
references and dynamic dispatch needing fallbacks. Measured against the 25% path coverage the current
URL-convention derivation achieves, that is the larger of the two available wins, and it is independent of the
telemetry-observed binding that arrives in the same milestone.

Neither pass blocks an answer. The tree-sitter pass returns `binding_source: static` immediately; the compiler
pass runs in the background and upgrades affected rows to `resolved` when it finishes. Published figures put
that pass at 35 seconds for a 147,000-line project and 705 seconds for 1.23 million lines, which is acceptable
as background work and unacceptable on a request path — hence the split rather than a choice between them.

Storage follows the same shape as comparable systems that have been measured at this scale: SQLite in
write-ahead-logging mode, built in memory and written once rather than row by row. A published implementation
indexes the Linux kernel — 28 million lines, 75,000 files, producing 4.81 million nodes and 7.72 million edges
— in about three minutes with this arrangement, and answers graph queries in single-digit milliseconds. That is
the performance envelope to design against; incremental reindex of a few thousand files should complete in
seconds.

**This does not change M0.** The tree-sitter indexer is committed and M0 exists to prove the spine end to end.
This is an M1 refinement, scheduled with the telemetry correlator because both address the same weakness.

**LangChain has no role here.** Its code offering is `RecursiveCharacterTextSplitter.from_language()`, which
chunks source at class and function delimiters for embedding, and which documents brace-delimited languages as
a weakness. That is retrieval preprocessing; this is symbol resolution. The design document already confines
LangChain to changelog map/reduce and structured extraction and keeps it out of the patch loop. Keep it out of
the index loop for the same reason.

### Packages

| Package | Change |
|---|---|
| `sync.core` | Add the `GraphStore` protocol and the MCP tool result contracts. Typing only, no logic, no sibling imports. |
| `sync.graph` | Refactor the existing Postgres store behind `GraphStore`; add a SQLite implementation. |
| `sync.mcp` | New. The server, tool handlers, and feed cache. Depends on `core` and `graph`; additionally on `remediate`, but only for `sync_propose_patch`, so the three read tools can ship before the remediation graph exists. |

The `GraphStore` protocol is required rather than speculative: local-first cannot work without an embedded
store, and two divergent query implementations would be worse than one abstraction. It touches code the M0
branch owns, so it lands after M0 merges.

### A correction this design depends on

OpenTelemetry promoted the `code.*` attributes to stable in semantic conventions v1.33.0 and renamed them:
`code.filepath` became `code.file.path`, and `code.lineno` became `code.line.number`. The design document's
synthesized-adapter section still uses the pre-stable names.

`binding_source: observed` is computed by correlating spans on exactly these attributes, so the correlator must
read both spellings — emitters migrate on their own schedule, gated by `OTEL_SEMCONV_STABILITY_OPT_IN` with
`code` and `code/dup` values, which means both forms appear in real traffic for as long as the migration lasts.

## Tiers

| | Local, free | Hosted, paid |
|---|---|---|
| `sync_whats_at_risk` | Yes, static binding | Yes |
| `sync_explain_call_site` | Yes, `static` then `resolved` | Yes, `observed` where telemetry covers it |
| `sync_whats_changed` | Yes, from the public feed | Yes |
| `sync_propose_patch` | No | Yes |
| Store | SQLite | Postgres |

The free tier is genuinely useful and the paid tier is strictly better in a way local software cannot
replicate, because the difference is production telemetry rather than a feature flag.

## Transport and identity

The server speaks stdio in both tiers. In local mode it reads SQLite; in hosted mode the same process is a thin
client holding a token and calling Sync's API. The tool layer never learns which mode it is in, and the
transport is swappable behind that boundary.

This looks like a plumbing decision and is an identity decision. stdio inherits the machine's identity —
whatever token is on disk is who you are, with no callback, session, or per-request principal. HTTP must
establish identity per request, which is where organization membership, per-repository authorization, and audit
logs live. An enterprise asking "who queried which repository's dependency map, and when" can only be answered
over HTTP.

Sync does not need a per-user principal until it has organizations, which is M4. Until then stdio is both
sufficient and more widely supported by MCP clients than remote transports.

One consequence makes this more than a concession: **the tier difference is the presence of a token, not a
different installation.** A free user becomes a paying user without reinstalling anything or reconfiguring
their agent.

## Feed separation and data boundaries

The public change feed and the private dependency graph are published separately and queried together.

```
feed published   static, signed JSON over HTTPS behind a CDN. No authentication, own data license.
                          │  fetched and cached locally
                          ▼
graph server     holds the private index, consumes the cached feed, serves the join
```

Three reasons they must not share a process:

- **Trust asymmetry.** One is public data; the other is a customer's complete third-party dependency map — a
  high-value target on its own, independent of any source code. A single process holding both means one
  cross-tenant defect leaks the map. The threat model's posture is that there is nothing here worth stealing,
  and mixing these weakens that for no benefit.
- **Different scaling shapes.** The feed is byte-identical for every consumer and belongs on a CDN. The graph is
  per-customer. Serving both from one place gets the worst of each.
- **Distribution.** An unauthenticated feed is something a developer adds to their agent in seconds with no
  account. Requiring registration to see what a vendor changed removes the only funnel a solo project has.

The one argument for sharing is that `sync_whats_at_risk` *is* the join — a finding is a vendor change
intersected with a call site. That is answered by separating publication from query rather than by merging the
two: the graph server consumes the cached feed locally and computes the join there. In local mode the
customer's dependency map never leaves their machine, and the feed never needs to know that a particular
customer exists.

**The feed is a supply-chain surface and must be treated as one.** It drives code changes, so an attacker who
forges an entry gets a patch proposed against real code. Checksums are the minimum; signing is required before
the feed is load-bearing for anyone but us. The verification gate limits the damage — a forged change still has
to produce a patch that typechecks and passes CI — but it does not eliminate it, because a plausible malicious
patch can do both. This belongs in the feed's own specification and is recorded here so it cannot be forgotten
when that document is written.

## Error handling

Validate at the boundaries — MCP client input, the feed, subprocess output — and trust internal code.

- **An unknown call site returns `not_indexed` with the index age, never an empty result.** Silence reads as
  "no third-party dependency here," which is a wrong answer an agent will act on.
- **A feed fetch failure serves the cached feed and reports its age.** Never fail closed into a confident wrong
  answer.
- **An unmapped operation returns `null` rather than a guess**, preserving the safe-miss property the design
  document already establishes: failing to resolve is recoverable, resolving incorrectly is not.
- **`tsc` invocation** keeps the handling already learned on the M0 branch: explicit UTF-8 on subprocess output,
  and a timeout surfaced as a failed verification rather than an exception.

## Testing

Test-first, as everywhere in this repository.

- **Tool-schema golden file.** Any removed or renamed parameter fails the suite. This makes the stability rule
  executable rather than aspirational, and it is the same check Sync sells.
- **Fixture repository with known call sites**, asserting exact tool responses including the true negatives —
  a file with no third-party calls must return `not_indexed`, not an empty list.
- **Feed committed as a fixture.** No test touches the network.
- **Provenance assertions.** A response built from a deliberately stale index must report that staleness; a
  response with no compiler pass must report `binding_source: static` rather than `resolved`; and one with no
  telemetry must never report `observed`. These are exactly the fields that silently default to something
  plausible and are never noticed again — and a falsely confident `observed` would be worse than no field at
  all, because it is the rung an agent trusts most.
- **Response size bounds.** Assert that no tool returns file contents, that every list-returning tool paginates,
  and that a query against a large fixture repository stays under a fixed token ceiling. A token-efficiency
  claim with no test is a regression waiting to happen, and this one is load-bearing for the product's pitch.
- **Protocol conformance.** The server answers `tools/list` and `resources/list` correctly, because Sync of all
  products cannot ship a malformed MCP server.

## Milestone placement

This is M1, together with the MCP adapter, and the two share the change taxonomy.

The three read tools depend only on the indexer and the feed, so they can ship as soon as M0's indexer is
merged. `sync_propose_patch` depends on the remediation graph and therefore on M0 completing.

**What this reorders.** The dashboard described in the design document's M4 information architecture is
demoted. It remains the right eventual surface for humans, but it is no longer the first surface, and it is not
what proves the thesis. A solo operator building a dashboard before an agent-queryable graph would be building
the more expensive half first.

## Prior art, and a correction to the moat estimate

Two open-source projects build tree-sitter code graphs, store them in SQLite, and serve them over MCP:
`DeusData/codebase-memory-mcp` and `tirth8205/code-review-graph`. Their reported token reductions — roughly 10x
measured in the accompanying paper, with README figures ranging far higher — are the numbers quoted above.
Benchmarks published by a project about itself deserve the usual discount, and the paper's own honesty about a
circular recall metric is a point in its favour rather than against it.

The correction matters more than the corroboration. `codebase-memory-mcp` ships `HTTP_CALLS` edges and an
`ingest_traces` tool that validates those edges against runtime traces. That is the mechanism
`2026-07-25-sync-competitive-position.md` ranks as Sync's most defensible asset — correlating a static index
against runtime telemetry — and a working open-source implementation of it exists today. **The estimate of
9 to 18 engineer-months to replicate is wrong for the mechanism** and should not be repeated.

What survives is narrower and still unique. Those edges connect services to other services. Sync's connect a
call site to a **vendor operation**, joined against **vendor change data**, at field granularity. A
trace-validated internal call graph cannot tell anyone that Stripe removed a response field. The moat is the
join and the vendor-knowledge half, not the correlation technique.

The practical consequence is that Sync should treat graph construction as solved-adjacent work to be borrowed
from rather than invented, and spend its scarce solo effort on the half no one else has.

## Scope boundary

The public change feed is consumed by this design and not specified by it. Its schema, hosting, integrity, and
data license need their own document. Flagged explicitly so it is not smuggled in half-designed: an unsigned
feed that drives code changes is a supply-chain surface, and it deserves the same scrutiny as the threat model
gives the verification sandbox.

## Open questions

- Whether `sync_whats_at_risk` with no arguments should scan the whole repository or refuse without a path.
  Whole-repository is friendlier and is also how an agent burns its context window on a large codebase.

Transport and feed separation were open when this document was first written and are now decided above.
