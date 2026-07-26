# Sync — The Graph Surface

**Date:** 2026-07-25
**Status:** Approved design. Implementation follows M0.
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

One resource: `sync://feed/{vendor}`, the normalized change feed.

Each tool answers a question an agent actually has. A generic query tool was rejected: agents compose arbitrary
query languages poorly, and publishing the graph schema as the interface would make every internal change a
breaking change — for a product whose entire claim is that it catches breaking changes.

### Provenance is part of every response

Every response carries `indexed_at`, `feed_fetched_at`, and `binding_source`. The first two are ISO-8601
timestamps of when the index was last built and the feed last fetched — timestamps rather than durations, so a
cached response cannot report a freshness that has since expired. `binding_source` is `static` when the
symbol-to-operation mapping was derived from a vendor's conventions and `observed` when it was read off
telemetry.

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
| `sync_explain_call_site` | Yes, `binding_source: static` | Yes, `observed` where telemetry covers it |
| `sync_whats_changed` | Yes, from the public feed | Yes |
| `sync_propose_patch` | No | Yes |
| Store | SQLite | Postgres |

The free tier is genuinely useful and the paid tier is strictly better in a way local software cannot
replicate, because the difference is production telemetry rather than a feature flag.

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
- **Provenance assertions.** A response built from a deliberately stale index must report that staleness, and a
  response with no telemetry must report `binding_source: static`. Both are the kind of field that silently
  defaults to something plausible and is never noticed again.
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

## Scope boundary

The public change feed is consumed by this design and not specified by it. Its schema, hosting, integrity, and
data license need their own document. Flagged explicitly so it is not smuggled in half-designed: an unsigned
feed that drives code changes is a supply-chain surface, and it deserves the same scrutiny as the threat model
gives the verification sandbox.

## Open questions

- Whether `sync_whats_at_risk` with no arguments should scan the whole repository or refuse without a path.
  Whole-repository is friendlier and is also how an agent burns its context window on a large codebase.
- Whether the hosted tier speaks stdio via a local proxy or HTTP directly, which is an authentication question
  more than a transport one.
- Whether the feed resource belongs on the same server as the private graph at all, given one is public data
  and the other is a customer's dependency map.
