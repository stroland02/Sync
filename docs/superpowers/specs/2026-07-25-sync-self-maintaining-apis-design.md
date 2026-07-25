# Sync — Self-Maintaining API Integrations

**Date:** 2026-07-25
**Status:** Approved
**Scope of this document:** the whole product's design, with milestone M0 specified in enough detail to implement.

## Problem

Every codebase depends on APIs it does not control. Those APIs change. Fields disappear, endpoints are deprecated, defaults shift, and cheaper endpoints ship without announcement. The consuming team finds out when production breaks, if it finds out at all. One AWS org traced over 30% of its service downtime to external API and package changes nobody noticed.

The tooling that exists watches the wrong side of the wire. SmartBear/Swagger, Treblle, Levo, Optic, and Postman-Akita all detect drift on the API *you publish*, and they stop at an alert. That helps the provider. It does nothing for the thousands of teams whose calling code just broke, because a provider-side tool has no idea who consumes it, from which repository, in which language.

Nothing watches the APIs you *consume*, across vendors, and nothing repairs the calling code.

Dependabot solved this exact shape for package versions and never extended to API semantics. Dependabot does not tell npm it broke semver; it edits your `package.json` and opens a pull request. Sync does that for API surfaces.

## Why now

Remediation requires write access to a customer's codebase. Two years ago that was unsellable. Agentic coding tools — Claude Code, Devin, Greptile — established that developers and enterprises will grant codebase access to an external tool when the value is clear. The infrastructure for automated code change now exists. The missing layer is the one connecting API change to the code that calls it.

## Product

Sync indexes a customer's repositories and builds a graph of every third-party API call site. It watches vendor specifications and changelogs, and the customer's own production telemetry. When something breaks or degrades, it opens a pull request against the customer's repository — already verified green by the customer's own CI.

### Positioning

| | Provider-side drift tools | Sync |
|---|---|---|
| Whose code is watched | Theirs, one API | Yours, every vendor you call |
| Whose code changes | Nobody's | Yours |
| Trigger | Own spec versus own implementation | Vendor shipped, production erroring, calls wasteful |
| Output | Report, failed CI check | Verified pull request |
| Vendor cooperation | It *is* the vendor | None required |

One distinction is worth holding precisely, because the technologies look similar. Optic and Akita read **inbound** traffic to reconstruct the specification of the API *you serve*. Sync reads **outbound** client spans to learn which vendor endpoints *you depend on*. Same telemetry family, mirrored direction.

## Decisions

| Decision | Choice | Consequence |
|---|---|---|
| Market side | Consumer-side, neutral across vendors | Ships without a single vendor partnership |
| M0 wedge | Vendor-change detector, Stripe, TypeScript | Every input is public; demoable with no customer |
| Verification gate | The customer's own CI verifies the patch | We never execute customer code and never hold their secrets |
| Openness | Open core | Plugin SDK and adapters public; hosted runtime commercial |
| Orchestration | LangGraph 1.0, Python | Durable checkpointing across long CI waits |
| Patch harness | Claude Agent SDK, inside one LangGraph node | Inherits a hardened file-edit toolchain instead of rebuilding one |
| Repository | This repository, named `sync` | Empty before this work; clean identity and dependency tree |

Provider-side push — a vendor installing Sync to fan fixes out to its customers — is the two-sided end state. It stays deferred until a consumer-side install base makes a vendor's signature worth pursuing.

## Architecture

The unifying primitive is the **API Dependency Graph** (ADG), one per customer. Every detector is a query against it, and every detector emits the same `Finding` type into one shared remediation pipeline.

```
  EXTERNAL SIGNALS          ADG                    REMEDIATION
  vendor spec diff  ─┐   ┌──────────────┐        ┌───────────────┐
  vendor changelog  ─┼──►│ call sites   │        │ locate        │
  SDK releases      ─┘   │ endpoints    │        │ strategize    │
                         │ fields read  ├─Finding►│ patch         │
  RUNTIME SIGNALS        │ versions     │        │ static verify │
  OTel client spans ────►│ volumes      │        │ push branch   │
  error rates       ────►│ status mix   │        │ await CI      │
  call patterns     ────►│ latency      │        │ open PR       │
                         └──────────────┘        └───────────────┘
```

Three detectors share one spine:

- **Vendor change** — a new external fact intersected with call sites. Milestone M0.
- **Efficiency** — a runtime pattern intersected with call sites. Milestone M1.
- **Production error** — a runtime anomaly intersected with call sites. Milestone M2.

This is what makes Sync one product rather than three. The detectors differ only in which signal opens the query. Everything downstream — locate, patch, verify, open — is shared.

### Packages

All under `src/sync/`.

| Package | Responsibility | Depends on |
|---|---|---|
| `sync.core` | Contracts only: `Finding`, `CallSite`, `VendorChange`, `Patch`, `Evidence`, and the four plugin protocols. No logic. | nothing |
| `sync.graph` | ADG persistence and queries over Postgres. | `core` |
| `sync.index` | The `LanguageAdapter` protocol and the TypeScript adapter. Turns a repository into `CallSite` rows. | `core` |
| `sync.signals` | The `VendorAdapter` protocol and the Stripe adapter. Turns vendor artifacts into `VendorChange` rows. | `core` |
| `sync.detect` | The `Detector` protocol and `VendorChangeDetector`. Joins signals against the ADG and emits findings. | `core`, `graph` |
| `sync.remediate` | LangGraph graphs that turn a finding into a merge-ready pull request. Its `patch` node delegates to the Claude Agent SDK. | `core`, `graph`, `forge` |
| `sync.forge` | Git and GitHub App operations: branch, push, poll checks, open pull request. | `core` |
| `sync.cli` | Local driver. The only entry point at M0; there is no hosted control plane yet. | all |

`sync.core` imports nothing from any sibling package. This constraint is what makes the system genuinely pluggable rather than merely pluggable-shaped: a third party writing a Twilio adapter depends on `sync.core` alone. Enforce it with an import-linter test, not with discipline.

### Plugin protocols

```python
class LanguageAdapter(Protocol):
    def matches(self, repo: RepoRef) -> bool: ...
    def index(self, repo: RepoRef) -> Iterable[CallSite]: ...
    def static_verify(self, repo: RepoRef, patch: Patch) -> VerifyResult: ...

class VendorAdapter(Protocol):
    vendor_id: str
    def fetch_changes(self, since: Version) -> Iterable[VendorChange]: ...
    def operation_for_symbol(self, symbol: str) -> OperationRef | None: ...

class Detector(Protocol):
    def scan(self, graph: ADG) -> Iterable[Finding]: ...

class Remediator(Protocol):
    def can_handle(self, finding: Finding) -> bool: ...
    def propose(self, finding: Finding, repo: RepoRef) -> Patch: ...
```

`operation_for_symbol` is the hinge of the entire system. It maps a source-level call such as `stripe.charges.create` onto an OpenAPI operation such as `POST /v1/charges`. Without it, specification diffs and source code occupy unconnected universes and no detector can fire.

### Remediation graph

```
locate ──► strategize ──► patch ──► static_verify ──┐
                            ▲                        │ fail (retry ≤ 3)
                            └────────────────────────┘
                                     │ pass
                                     ▼
                              push_branch ──► await_ci ──► decide
                                                  ▲          │
                                       red, retry │          │ green
                                                  └──────────┤
                                                             ▼
                                                          open_pr
```

`await_ci` is the reason this is a LangGraph graph and not a loop. A CI run takes between three and thirty minutes, and a worker restart during that wait must not lose the run. LangGraph's Postgres checkpointer persists state at every node, so a restarted run resumes exactly where it stopped.

Retries are bounded. Three static-verification failures, or two CI failures, abandons the finding and records why. An agent that grinds indefinitely against a patch it cannot get right burns money and produces nothing.

### Two frameworks, two jobs

The graph above and the work inside its `patch` node are different problems, and one framework does not serve both well.

**LangGraph owns the spine.** Durable state, conditional edges, bounded retries, and a wait that survives a worker restart. Its measured orchestration overhead is roughly fourteen milliseconds per step, which is noise beside a CI run measured in minutes.

**The Claude Agent SDK owns the `patch` node.** Producing a patch means opening a repository, locating call sites, editing TypeScript, running `tsc`, reading the errors, and editing again. The Agent SDK ships that toolchain — file read, write, and edit, bash, glob, grep, subagents, permissions, context management — as a library. Rebuilding it inside LangGraph would consume the largest single block of M0 and produce a weaker version of something already hardened in production.

The node boundary keeps this clean: the Agent SDK runs entirely inside one LangGraph node, checkpointed like any other. It never sees the graph, and the graph never sees its internals. Because `sync.core` already defines a `Remediator` protocol, the Agent SDK is one implementation of that protocol rather than a dependency baked into the spine — a different patch strategy can be written against the same interface without touching the graph.

LangChain 1.0 stays in the stack for what it is genuinely good at: the changelog map/reduce chain and structured extraction, where multiple model backends and schema-validated output matter. It is deliberately not in the patch loop.

### Model configuration

`claude-opus-5` with adaptive thinking, at `xhigh` effort — the documented setting for coding and agentic work.

```python
{
    "model": "claude-opus-5",
    "thinking": {"type": "adaptive"},
    "output_config": {"effort": "xhigh"},
    "max_tokens": 64000,
}
```

Three constraints follow from that choice and are easy to get wrong. `temperature`, `top_p`, and `budget_tokens` are all removed on this model and return a 400 — steer with prompting instead. Thinking is on by default, and `max_tokens` caps thinking plus response text together, hence the generous ceiling. The prompt-cache minimum is 512 tokens, half of Opus 4.8, so the repository-context prefixes we send on every patch attempt cache cheaply.

### Patch strategy

Neither available approach is sufficient alone. Static codemods handle mechanical substitution reliably and fail on cross-file semantic change. LLM-authored patches invert that profile and fail in documented, non-obvious ways. `strategize` therefore chooses:

1. **Deterministic first.** When the `VendorChange` maps to a known transform — a renamed field, a moved parameter, a deprecated method with a direct successor — apply a codemod. Deterministic, reviewable, no model call.
2. **Agent fallback.** Otherwise the Claude Agent SDK runs against a clone of the repository, given the call site, the specification diff, and the changelog entry. It reads surrounding code and iterates against `tsc` output rather than emitting a patch blind on first attempt.
3. **Verification does not vary by path.** Neither patch source is trusted. `tsc --noEmit` runs first against the vendor's shipped `.d.ts`, because it is fast and catches a wrong field, wrong arity, or removed method before a single CI minute is spent. The customer's CI is the final word.

### Data model

Postgres.

```sql
call_site(id, repo_id, path, line, col, vendor_id, operation_id,
          symbol, args_keys[], response_fields_read[], sdk_version,
          content_hash, indexed_at)

vendor_change(id, vendor_id, from_version, to_version, kind,
              operation_id, path_ptr, severity, source, raw, detected_at)

finding(id, detector, call_site_id, vendor_change_id, severity,
        rationale, status, created_at)
```

`content_hash` on `call_site` makes reindexing incremental; unchanged files are skipped.

There is no vector store at M0. Every M0 query is a structured join. Introduce `pgvector` when a detector actually needs semantic recall, and not before.

## Milestones

### M0 — Walking skeleton, one real pull request

One vendor, one language, one detector, one repository. The scope is narrow on purpose: this milestone exists to prove the spine end to end, and every additional axis of variation delays that proof.

1. Repository scaffold, `sync.core` contracts, Postgres schema, CLI shell.
2. **Stripe adapter.** Fetch two pinned OpenAPI versions from `stripe/openapi`. Shell out to `oasdiff` for the machine-readable diff — it already classifies roughly 500 distinct change types as breaking or non-breaking, and reimplementing that would be waste. Parse the changelog with a LangChain map/reduce chain into structured `VendorChange` records, then reconcile both sources. Build the symbol-to-operation map from Stripe's own `.d.ts`; the SDK is generated from the specification, so the mapping is mechanical rather than guessed.
3. **TypeScript adapter.** Parse with tree-sitter-typescript. Resolve `stripe` imports and client construction, walk member chains to call sites, and capture both the argument keys passed and the response fields the code actually reads. `static_verify` shells out to `tsc --noEmit`.
4. **VendorChangeDetector.** Join `vendor_change` against `call_site` on `operation_id`, filtered by whether the code touches the affected field.
5. **Remediation graph.** Both patch paths, bounded retries, Postgres checkpointer. The `patch` node wraps a Claude Agent SDK run scoped to a repository clone.
6. **Forge.** GitHub App: create branch, push, poll check runs, open a pull request carrying an evidence bundle — the specification diff, the changelog entry, the affected call sites, and a link to the CI run.

**Complete when** a genuine breaking change between two pinned Stripe specification versions produces a CI-green pull request, start to finish, unattended.

The target repository is our own fork of a real open-source TypeScript project that uses the Stripe SDK. It must be a fork rather than a purpose-built toy, because unfamiliar real-world code is the only honest test of the indexer, and it must be a fork we control so that opening pull requests against it is ours to do.

#### Known limits of the M0 symbol map

Both limits below come from deriving `operation_for_symbol` out of Stripe's URL conventions. Both are measured against Stripe's real specification, not estimated, and both are properly solved by the telemetry-derived mapping described under Synthesized adapters rather than by patching the derivation.

**Coverage is 105 of 414 `/v1/` paths, about 25%.** The remainder are nested sub-resources such as `/v1/customers/{customer}/sources`, which the path pattern does not match. A call site on an unmatched operation produces no symbol mapping, so no finding can be raised against it.

**Singleton resources map to the wrong verb.** A `GET` with no path parameter is treated as a collection listing, which is right for `/v1/charges` and wrong for `/v1/account` and `/v1/balance`, whose real SDK methods are `retrieve` rather than `list`.

The second is a smaller problem than it appears, and the reason is worth stating because it generalises to every synthesized mapping: the failure is a **safe miss, not a wrong answer**. The generated key `stripe.account.list` matches no real call site, so nothing looks it up, and the genuine symbol `stripe.account.retrieve` resolves to `None`. A finding is never raised against the wrong operation. Any mapping heuristic we adopt later should preserve that property — failing to resolve is recoverable, resolving incorrectly is not.

### M1 — Runtime signals and the efficiency detector

An OTLP ingest endpoint consuming client spans on stable semantic conventions version 1.23.0 or later: `http.request.method`, `url.full`, `server.address`, `http.response.status_code`, `http.request.resend_count`. Correlate spans to call sites by operation and host.

Then the efficiency detector: vendor calls inside loops, default page sizes against large result sets, repeated identical calls with no caching, and retry storms visible through `resend_count`. These findings carry a dollar estimate, which is the easiest form of value to defend at renewal.

### M2 — Production error detector

Anomaly detection over the same span stream. A change in 4xx or 5xx rate on a single vendor operation, or a contract violation where a response no longer matches the indexed specification, becomes a finding. Root-cause context comes from the trace joined with the ADG.

### M3 — Multi-vendor, MCP, and the public plugin SDK

Stripe is the easiest vendor that exists: a public machine-readable specification, a dated changelog, date-versioned releases, and an SDK generated from that specification. Designing the adapter interface against Stripe alone would encode its tidiness as an assumption. So M3 deliberately targets harder cases before the interface is published and becomes permanent.

**A messier REST vendor** — one without a clean published specification, where changes must be recovered from a changelog and SDK releases rather than a spec diff. This is the case that tells us whether `operation_for_symbol` generalizes.

**An MCP server adapter.** MCP is becoming a first-class API surface, and its tool schemas drift like any other contract. It is also a structurally easier adapter than a REST vendor: an MCP server exposes its tool schemas on request, so there is no specification to locate, no changelog to parse, and no SDK symbol mapping to derive.

```
REST vendor:  fetch spec  ->  diff  ->  map SDK symbol to operation
MCP server:   connect     ->  tools/list  ->  diff schemas
```

Same `VendorAdapter` protocol, fewer unknowns. It is a strong candidate for the second adapter rather than a distant one.

**A Python language adapter**, to prove `LanguageAdapter` generalizes past TypeScript.

Then publish `sync.core` as the open plugin SDK with adapter-authoring documentation.

Coverage is the moat, and it is the reason for the open-core decision rather than a consequence of it. A live codebase calls dozens of third-party APIs. We cannot write dozens of adapters ourselves, so the interface has to be good enough that vendors and users write them. That is also why `sync.core` importing no sibling package is a hard rule rather than a stylistic preference.

### Synthesized adapters

Writing adapters by hand does not scale, and third parties writing them is only half an answer. The other half is generating them.

The word "adapter" covers two separable jobs, and conflating them is what makes hand-authoring look mandatory:

| | Answers | Source |
|---|---|---|
| **Codebase binding** | Which vendors does this repository call, and which call site maps to which endpoint? | Synthesizable from the index and telemetry |
| **Vendor knowledge** | What did that vendor change? | Must come from outside |

**Codebase binding is fully synthesizable.** Static parsing enumerates every SDK import and every literal hostname; OTel client spans report `server.address` and `url.full` for every outbound call. Together they produce a vendor inventory with no configuration.

The mapping matters more. In M0, `stripe.charges.create → POST /v1/charges` is *derived* from Stripe's naming conventions — the single most vendor-specific assumption in the system and the risk this document already flags. Telemetry replaces derivation with observation. When a client span carries the code location that produced it, the mapping is read off real traffic:

```
static index   src/billing.ts:6  ->  stripe.charges.create
OTel span      POST https://api.stripe.com/v1/charges
               code.filepath=src/billing.ts, code.lineno=6
                          |
                 correlate on call site
                          |
            symbol -> endpoint, observed rather than derived
```

This generalizes to a vendor nobody has written an adapter for, and to a bare `fetch()` with no SDK at all.

**Vendor knowledge cannot be synthesized from our own telemetry.** Traffic is a mirror: it shows what our customer's code does, never what a vendor is about to ship. Learning that a field was removed requires reading something the vendor published. Three things soften that:

- Changelog parsing is vendor-agnostic — prose to structured change is one LLM chain, reused across vendors.
- SDK releases are a universal signal. A type-signature diff between two published SDK versions indicates a breaking change without any specification.
- **Two of the three detectors need no vendor knowledge at all.** Efficiency and production-error run entirely off telemetry joined against the graph. A 4xx spike on an endpoint is self-describing.

The resulting coverage model: every vendor gets error and efficiency detection immediately; vendors that publish specifications or changelogs additionally get pre-emptive change detection.

MCP is the case where both halves are automatic. An MCP server returns its tool schemas on request, so vendor knowledge is a snapshot-and-diff rather than a research problem. A fully synthesized adapter, end to end.

**Why this is safe to attempt.** A synthesized mapping will sometimes be wrong, and a wrong mapping yields a wrong finding and a wrong patch. That patch then fails `tsc`, or fails CI, and is abandoned. The verification gate is what makes inference affordable: we can generate adapters aggressively precisely because nothing they produce reaches a human without a green build behind it.

**Sequencing.** This does not change M0, and should not. Stripe stays hand-written, because an adapter synthesizer cannot be built without a known-correct adapter to score it against. Stripe is the ground truth.

### M4 — Hosted control plane

Multi-tenant runtime, dashboard, organization onboarding, and per-repository policy: which vendors are watched, and which severities open a pull request automatically versus requiring review.

#### Information architecture

The navigation hierarchy is the API Dependency Graph. Every level of the interface is an entity the system already stores, which means the interface cannot drift from the domain — there are no invented screens and no dead ends.

```
Codebase (the selected repository)
   └── API Services              vendors the indexer found in this repository
         ├── Signals             one panel per attached integration, grouped by role:
         │                       vendor, signal source, human surface
         ├── Errors & Incidents  findings for this vendor, from any detector
         │      └── Finding
         │            └── Solution Workflow      the remediation run
         │                  └── Pull Request     with its evidence bundle
```

A user starts from a repository, not from a vendor list, because the question they actually have is "what is wrong with my code" rather than "what is Stripe doing". Vendors appear underneath because the indexer discovered them, so the list is never something anyone configures.

**The Solution Workflow view renders live graph state, not a progress bar.** Because the remediation graph checkpoints at every node, the interface can show `locate → strategize → patch → static verify → push → await CI → open PR` as it happens, with the evidence attached at each step: which call sites were located, what the patch changed, what `tsc` said, which CI run was watched. Failed attempts stay visible, along with the reason a finding was abandoned.

This is a deliberate product position rather than a debugging convenience. Comparable tools present a black box and a result, which asks a reviewer to trust the output on faith. Showing the state machine and its evidence is what earns the merge — the reviewer can see that the patch passed a real typecheck and a real CI run before it was ever offered to them.

### M5 — The integration layer

The product's name is its thesis: synchronize signal across the tools a team already uses, so that remediation has complete context rather than one channel's worth.

An integration is not one kind of thing. Three roles attach to the graph at different points, and treating them as one bucket is what makes this look unbuildable:

| Role | Examples | Relationship to the graph |
|---|---|---|
| **Vendor** | Stripe, Notion API, Linear API, Cloudflare API | A subject. Code calls it; it can break you. |
| **Signal source** | Sentry, Vercel, Railway, Render, GitHub Actions, CloudWatch | Feeds the graph. Reports that something broke, deployed, or changed. |
| **Human surface** | Slack, Linear issues, Notion, GitHub pull requests | Consumes. Where a finding is delivered and a human answers. |

Some vendors occupy two roles. Linear's API is something a customer's code may call, and Linear is also where a finding becomes a ticket. Those are unrelated integrations that happen to share a logo.

**Why correlation is worth the work.** Each signal alone is close to noise. A Sentry spike is a mystery, a Vercel deploy is routine, a Stripe changelog entry goes unread. Joined on the graph they are a root cause and a fix:

```
Vercel    deploy 4f2a shipped                     14:02
Sentry    TypeError on charge.status, 312 events  14:04
ADG       src/billing.ts:6 reads `status` off stripe.charges.create
Stripe    response-property-removed `status` in v2344
GitHub    4f2a bumped stripe 18.0.0 -> 19.0.0
                          |
          one finding, causally complete, with a patch attached
```

**Sentry is likely the fastest route to M2.** It has already solved grouping, deduplication, and stack-trace capture — the expensive parts of turning raw errors into a finding. A Sentry signal source may reach a working production-error detector well before a raw OTLP pipeline does, and the two are not exclusive.

**Two rules keep this from consuming the product.**

*Everything integrates through the graph, never tool to tool.* Point-to-point wiring across N tools is N² connections and is how this category of product collapses. Graph-mediated is N: each integration learns one schema, the graph's.

*Every integration must answer one question — what finding does it produce, or what patch does it improve?* If neither, it is a dashboard feature and does not belong here. What makes Sync worth paying for is that it changes code. Integrations are inputs to a remediation engine, not the product.

**Why coverage compounds rather than accumulates.** Each additional signal is another dimension the join can cut on, so the quality of a remediation rises faster than the count of integrations. One source establishes that an error occurred. Four establish which deploy introduced it, which vendor change the deploy carried, which call sites are affected, and who owns them — enough to propose a fix a senior engineer would recognise as correct rather than a mechanical substitution.

This is also why the graph-mediated rule is a competitive property and not only an engineering one. A product that wires tools to each other pairwise can surface each tool's data beside the others, but it cannot reason across them, because no component holds a model of how the customer's code actually uses any of it. Correlation composes only when every signal lands on a shared structure. The graph is that structure, and it is the part that is hard to copy.

## Risks

| Risk | Mitigation |
|---|---|
| Symbol-to-operation mapping does not generalize past Stripe | Prove it against a messier vendor at M3, before the SDK is public. The map is an adapter responsibility, never core. |
| One bad merge destroys trust | Nothing reaches a pull request without passing the customer's CI. Failed findings are reported, never guessed at. |
| Repositories without CI have no verification path | Explicitly out of scope at M0. Sandbox fallback is a separate decision deferred to M4, where its security surface can be designed properly rather than smuggled in. |
| Changelog parsing hallucinates a change | The `oasdiff` output is authoritative. The changelog enriches and prioritizes; it can never introduce a `VendorChange` on its own. |
| Codebase access is a hard sell | The open-core plugin SDK and a self-hostable core are the trust answer, which is why openness is settled now rather than later. |
| The patch node is Claude-only | Contained by design. It sits behind the `Remediator` protocol and inside a single LangGraph node, so an alternative implementation is a new class rather than a rewrite. Accepted deliberately: the alternative is hand-building a file-edit harness, which costs more than the coupling does. |
| Agent SDK runs unsupervised against a repository clone | It operates on a throwaway clone, never the customer's working tree, and nothing it produces reaches a pull request without passing `tsc` and then the customer's CI. |

## Verification

Test-driven throughout. A failing test precedes implementation in every case.

- **Contracts** — protocol conformance tests in `sync.core` that every adapter must pass, plus an import-linter test enforcing that `sync.core` imports no sibling package.
- **Stripe adapter** — two pinned specification versions committed as fixtures with a hand-labeled expected `VendorChange` set. Deterministic; no network access in tests.
- **TypeScript adapter** — small fixture repositories under `tests/fixtures/ts/`, each with known call sites and a golden `CallSite` set. Includes deliberately hard cases: aliased imports, a client wrapped in a helper function, destructured responses.
- **Detector** — a synthetic ADG and synthetic changes, asserting the exact finding set, including the true negatives.
- **Remediation graph** — node-level unit tests, plus a whole-graph test against a stubbed forge and a stubbed patch node, asserting retry bounds and abandonment behavior. No test makes a model call; the Agent SDK is exercised only in the end-to-end run.
- **End to end** — `sync run --vendor stripe --from <v1> --to <v2> --repo <fixture>` against a fork we control, asserting that a pull request appears and its checks pass.

M0 acceptance is one command producing one green pull request. Anything short of that is not M0 complete.
