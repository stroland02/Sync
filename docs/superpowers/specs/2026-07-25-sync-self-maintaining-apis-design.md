# Sync — Self-Maintaining API Integrations

**Date:** 2026-07-25
**Status:** Approved
**Scope of this document:** the whole product's design, with milestone M0 specified in enough detail to implement.

## Problem

Every codebase depends on APIs it does not control. Those APIs change. Fields disappear, endpoints are deprecated, defaults shift, and cheaper endpoints ship without announcement. The consuming team finds out when production breaks, if it finds out at all. One AWS org traced over 30% of its service downtime to external API and package changes nobody noticed.

The tooling that exists watches the wrong side of the wire. SmartBear/Swagger, Treblle, Levo, Optic, and Postman-Akita all detect drift on the API *you publish*, and they stop at an alert. That helps the provider. It does nothing for the thousands of teams whose calling code just broke, because a provider-side tool has no idea who consumes it, from which repository, in which language.

Nothing watches the APIs you *consume*, across vendors, and nothing repairs the calling code.

Dependabot solved this exact shape for package versions and never extended to API semantics. Dependabot does not tell npm it broke semver; it edits your `package.json` and opens a pull request. Sync does that for API surfaces.

**The analogy holds until it inverts, and the inversion is the whole argument.** The literature on breaking changes in package ecosystems reports a consistent and initially deflating result: only a small subset of theoretically-affected clients ever break — largely because most clients *deliberately avoid upgrades* ([Venturini et al., "I depended on you and you broke me"](https://arxiv.org/pdf/2301.04563)). A pinned version is a complete defence, so the population needing automated repair is smaller than the dependency graph suggests.

**None of that protection exists for a hosted API.** There is no version to pin, no upgrade to decline, and no lockfile that holds. The vendor deploys, and every consumer is on the new behaviour whether or not anyone chose it. The safety valve that shrinks the package-ecosystem problem is precisely the thing consumers of a web API do not have.

So the demand argument is not "this is like Dependabot but for APIs". It is that the mitigation which makes the package version of this problem tolerable is unavailable here, which is why the consuming team learns about the change from an incident rather than from a dependency bump.

Two consequences follow for what gets built. The gate has to be the customer's CI rather than a type checker, because a web API break compiles perfectly and fails in production. And a change must be discoverable from the *vendor's* published artifacts, because unlike a package there is no local copy of the new version to compare against — which is what makes specification discovery a first-class problem rather than a configuration detail.

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
| Verification gate | The customer's own CI verifies the patch | We never hold their secrets, and never run their application — see the qualifications below |
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

**The verb is no longer guessed — and fixing it moved coverage by nothing.** Stripe publishes `openapi/spec3.sdk.json` beside `spec3.json` at the same tags, and its `x-stableId` extension names the SDK method outright: `/v1/account` GET is `retrieve_connect_account`, `/v1/accounts` GET is `list_connect_accounts`. `build_symbol_map` now takes the verb from there where one exists and keeps the URL heuristic where none does, so the singleton verbs come from the vendor rather than from a rule we invented.

The measured effect is worth more than the fix. Against the real cached `v2330`: 179 symbols over 105 of 414 paths **before and after**, no operation newly resolved, and exactly one symbol corrected — `stripe.subscriptions.del` became `stripe.subscriptions.cancel`. That one matters, because `Subscriptions.ts` exposes no `del` at all, so the old map named a method that does not exist. Everything else the heuristic had already guessed right.

An estimate had circulated that widening the path pattern would take coverage from 105 to 241. The arithmetic is correct and the conclusion is not: widening produces symbols like `stripe.apps/secrets/delete.del`, which no call site can ever match. Coverage counted that way measures the generator, not the binding.

Two properties of this to preserve. The document is optional — `v1900`'s carries zero extensions of any kind, so the degradation path is exercised by real data rather than by a fixture, and a version without it must fall back rather than raise. And the original failure was a **safe miss, not a wrong answer**: `stripe.account.list` matched no real call site, so nothing looked it up and no finding was ever raised against the wrong operation. Any mapping strategy adopted later should keep that property — failing to resolve is recoverable, resolving incorrectly is not.

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

### Vendor onboarding

The previous section argues that adapters can be generated. This one answers the question underneath it: what does a new vendor actually cost, and what has to be built before that cost is low?

**The scaling unit is the artifact tier, not the vendor.** Looking at the Stripe adapter as built, almost nothing in it is about Stripe. `fetch_changes` is generic given two specification files on disk. `operation_for_symbol` is a dictionary lookup. Only two things are vendor-specific: where the specifications live, and how the symbol map was produced.

So a per-vendor adapter class is the wrong decomposition. What varies is the shape of the artifact a vendor publishes, and there are five shapes.

| Tier | Artifact | Vendors | Differ | Cost of a new vendor |
|---|---|---|---|---|
| 0 — self-describing | `tools/list`, JSON Schema 2020-12 per tool | any MCP server | ours, a JSON Schema diff | none; fully generated |
| 1 — versioned OpenAPI in git | tagged specification file | Stripe, Twilio, GitHub, Azure | `oasdiff` | configuration: repository, path, tag pattern |
| 2 — machine-readable, not OpenAPI | Discovery Document, `service-2.json` | Google, AWS | converter, then `oasdiff` | one converter per format, then tier 1 |
| 3 — GraphQL | SDL via introspection | Linear, GitHub v4, Shopify | `graphql-inspector` | a differ and a different symbol model |
| 4 — prose only | changelog | Notion, the long tail | LLM extraction | per-vendor, low trust, never authoritative |

Tier 1 collapses to a single `GitOpenApiAdapter` parameterised by coordinates. Stripe becomes a configuration row rather than a class, and Twilio and GitHub cost an afternoon each. That collapse is the difference between a plugin catalogue that scales and one that accumulates hand-written code proportional to the vendor count.

Three findings from surveying the tooling change what has to be built.

**Webhook payload changes are already covered.** `oasdiff` supports OpenAPI 3.1, including a webhooks diff that reports added, removed and modified webhooks and applies every operation-level check to the modified ones. A vendor changing a webhook body breaks consumers exactly as hard as changing a response body, and this was expected to require separate AsyncAPI tooling. It does not.

**MCP versions the protocol but not its tools.** Protocol versions are date strings negotiated at `initialize` and carried in an `MCP-Protocol-Version` header, and breaking protocol changes land roughly quarterly. Individual tool schemas carry no version at all. So a tier 0 adapter cannot ask a server what changed; it snapshots `tools/list` and diffs consecutive snapshots itself. This is not a limitation in practice — it needs no vendor cooperation, which is what makes tier 0 free — but it does mean Sync owns the snapshot store and the JSON Schema differ.

**GraphQL needs a different symbol model, not merely a different differ.** `graphql-inspector` supplies the classification, marking each change breaking, dangerous, or safe. The harder problem is that a GraphQL consumer's call site is a query document naming fields, not a method chain like `stripe.charges.create`. `operation_for_symbol` has no meaning there; the equivalent is matching changed field paths against the field sets of parsed query documents. That is real work in both the vendor adapter and the language adapter, and it is why GraphQL is a tier of its own rather than one more entry in tier 1.

#### The symbol map is the part that resists templating

Everything above concerns knowing what a vendor changed. Binding that to a call site remains the weak point: the M0 symbol map covers 105 of 414 Stripe paths, and maps singleton resources to the wrong verb. One derivation strategy will not carry a plugin catalogue.

**Measured against a second vendor, and the result inverts the assumption above.** A Twilio adapter was built specifically to test whether `VendorAdapter` is a plugin surface or a description of Stripe. The change half is a real surface. The symbol half was not, and the reason is worth stating exactly, because it was the opposite of what was expected.

Before Twilio, `operation_for_symbol` had exactly one implementation. Both other non-Stripe adapters return `None` from it on principled grounds — a model id is not an SDK symbol, and a generated-spec adapter deliberately does not know one vendor's naming scheme. Each is individually correct, and the aggregate effect was that the half of the protocol with a single implementation was also the half nobody had stress-tested. **A protocol with one implementation is a description of that implementation.**

Twilio states in its specification proper both of the things Stripe's machinery exists to recover. The verb is written into `operationId` as a closed vocabulary — `Fetch`, `List`, `Create`, `Update`, `Delete` covers all 155 operations across five product documents, with no exceptions and no fallback rule. Instance-versus-list is stated outright as `x-twilio.pathType`. Stripe publishes neither: `sync.signals.stripe.symbols._addresses_one_resource` exists to infer the second from response shape, and the first is fetched from a separate ten-megabyte `spec3.sdk.json`.

The number that settles it is pinned in Stripe's own committed test rather than asserted here: consulting `x-stableId` across 521 stable ids changes **exactly one symbol out of 179** — `del` to `cancel` on subscriptions — and reaches no operation the path pattern did not already reach. Ten megabytes per version, per fetch, for one corrected name.

So the general mechanism is *read what the vendor states about its own SDK*, and `x-stableId` is one vendor's unusually expensive instance of it. Building the abstraction around that instance is what produced a symbol half that only ever had one implementation.

Two things this does not license. Twilio is not simply better documented: its hint for the resource *name* is the sparse one — `mountName` covers 28 of 95 paths declaring operations, 29%, ranging from 9% in `twilio_video_v1` to 47% in `twilio_messaging_v1` — where Stripe's is dense. And a nearby field, `x-twilio.className`, would lift apparent coverage to 45% while being wrong on all ten paths where it disagrees with the last path segment, because it names the generated class rather than the attribute the client exposes. `twilio-python` sides with the path segment in all ten. A wrong symbol is worse than a missing one: a missing one leaves the call site visibly unresolved and countable, a wrong one binds it to an operation the customer never called. `tests/test_twilio_adapter.py` pins that deliberately.

**The gap is a language axis, not a vendor one.** `twilio-python`'s `call_summaries` and `twilio-node`'s `callSummaries` are the same operation, and `operation_for_symbol` cannot tell them apart. That signature change, and a product axis on `VendorChange`, are recorded and not yet made.

It should become a cascade, where each strategy records how it produced a mapping:

| Strategy | Source | Confidence |
|---|---|---|
| Convention | `operationId` plus the SDK's naming rules | low; wrong on every irregular resource |
| SDK typings | the vendor's shipped type declarations | high for existence, silent on the endpoint |
| Runtime observation | an OTel client span joined to the call site that produced it | highest; it is ground truth |
| Documentation | an LLM reading the vendor's reference | lowest; a last resort |

Runtime observation is the strategy that makes the rest optional. A client span carries `http.request.method` and `url.full`; the static index carries the symbol; correlating them yields the mapping empirically, for a vendor nobody has written an adapter for and for a bare `fetch()` with no SDK at all.

The cascade must record provenance rather than only the answer. A mapping observed at runtime outranks one derived from convention, and a low-confidence mapping degrades to an operation-match-only finding rather than being silently filtered — the same principle the detector already applies to a field it cannot resolve. A wrong mapping is recoverable because the verification gate catches it; a mapping that silently drops a real change is not.

#### What onboarding a vendor requires

For a tier 1 vendor, in full:

1. Specification coordinates: repository, path within it, and the tag pattern that identifies a version.
2. Two pinned versions checked in as fixtures, with a hand-labelled expected change set.
3. A symbol map, produced by the cascade above, with its provenance recorded.
4. A handful of small source files under `tests/fixtures/` exercising that vendor's client-construction idiom.

No forked application, and no network in any test. The one end-to-end acceptance run proves the pipeline once; it is a milestone gate rather than regression coverage, and running one per vendor is not affordable — each costs agent invocations plus a full CI wait. Per-vendor regression instead replays captured artifacts: a clone pinned at a commit, the specification pair, and the expected finding set, with the model call stubbed.

A real repository is needed again per *language*, not per vendor. Fixtures only catch idioms someone already thought of, which is exactly what the M0 acceptance target demonstrated by exposing a gap no fixture would have.

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
| The name collides with an adjacent tool | `oasdiff/sync` is a consumer-side monitor for upstream OpenAPI breaking changes, published under the same word and solving the near half of the same problem. It notifies and stops; it does not index the consumer codebase, locate call sites, patch, or open pull requests. The overlap validates the thesis and confirms the gap, but the name is cheap to change now and expensive after a public repository exists. Unresolved. |
| Tier 3 (GraphQL) is not one more adapter | A GraphQL call site is a query document, not a method chain, so `operation_for_symbol` has no meaning and field-path matching against parsed documents replaces it. Scoped as its own tier with work in both the vendor and language adapters, rather than assumed to fall out of the plugin protocol. |
| Symbol mapping has one derivation strategy and 25.4% coverage | Replaced by a provenance-recording cascade — convention, SDK typings, runtime observation, documentation — where a low-confidence mapping degrades to an operation-match-only finding rather than silently filtering a real change. |
| Agent SDK runs unsupervised against a repository clone | It operates on a throwaway clone, never the customer's working tree, and nothing it produces reaches a pull request without passing `tsc` and then the customer's CI. |

## Known limitations at M0

Everything here was measured against real data rather than reasoned about, and each is open. They are recorded because the sections above state the intent, and the intent is ahead of the code everywhere below.

**The gate cannot see inside `node_modules`, and no longer has to.** `static_verify` holds every untracked and every ignored path out of the clone before it compiles, so its verdict describes the branch `push_branch` creates rather than the tree the patch agent left behind. Installed dependencies are the one exception, because the customer's CI installs its own and a typecheck without them describes neither tree — so an agent that edits a type declaration inside `node_modules` satisfies a compiler the customer's CI will not.

Typechecking a second, pristine checkout was the recorded fix and was rejected on cost: a checkout and a dependency install per verification, three per finding at the current retry budget, which is the largest avoidable cost in the pipeline. It was also aimed at the wrong target. A second compile re-establishes everything in order to answer one question — did the patch touch a path the branch will not carry — and that question is answerable from the filesystem. Every file under an installed dependency was written by the install, so one whose mtime is later was written by something else. `sync.index.dependency_edits` makes that comparison before the compiler runs and fails the verification naming the path; measured at 0.09s over 8,800 files and 0.35s over 29,300, against an install measured in minutes. `sync.index.shipped_tree` carries the rest of the comparison.

**A patch that needs a new file ships one, and staging is the assertion that it needs it.** Widening to `git add -A` is what Task 10 rejected, because it commits whatever else the agent's tool calls left behind — a build directory, a log, a stray install — and separating a new source file the patch needs from that debris is not a question the pipeline can answer. It is put to the party that knows. The patch agent's scope rules now tell it to create the file and stage it by path with `git add <path>`, and never `git add -A` or `git add .` (`src/sync/remediate/agent_patch.py`, `_SCOPE_RULES`). Three things carry it from there without further change: git reports a staged addition as `A `, `_UNSHIPPED` in `src/sync/index/shipped_tree.py:79` is exactly `{"??", "!!"}`, so the gate compiles it; and `git add -u` updates the index where it already has an entry, so `push_branch` commits it. That set being exactly those two codes is now load-bearing rather than incidental — adding `"A "` to it would read as tightening and would silently push branches missing the module they import.

The case where the agent creates a file and stages nothing is now closed, and closed against the tree rather than against the diff. `_git_diff` runs `git diff HEAD` rather than `git diff`, so a patch whose whole content is a new module is not read as a remediator that changed nothing; and `propose` asks `git ls-files --others --exclude-standard` unconditionally, before it reads the diff at all, raising with the files and the remedy wherever any exist. Conditioning that question on an empty diff answered only half of it: an agent that edited a tracked call site *and* left the new module unstaged produced a non-empty diff, so the run proceeded and the gate failed on `TS2307: Cannot find module` — a compile error about an import, handed to an attempt whose actual mistake was not staging a file. The refusal is fed back to the next attempt rather than abandoning, and `push_branch` is untouched: `git add -u` still stages only tracked paths, so a patch that needs a new file still fails verification rather than pushing a branch without it. What remains open is what the boundary costs. `--exclude-standard` reads the repository's own ignore rules, which is the customer's declaration of what is disposable and the only such declaration available; where a project's rules do not cover what its toolchain writes, that byproduct is indistinguishable from a module the fix needs and it draws a refusal, spending one of three attempts. An extension allowlist would narrow that and is deliberately absent, because no measurement here supports one and a guessed list would be wrong silently on the first repository that disagreed.

**Sync executes the customer's toolchain, though not their application.** `run_tsc` prefers the clone's own `node_modules/.bin/tsc`, resolved through the customer's `.npmrc`, and the patch agent runs commands inside the clone. Dependency installs pass `--ignore-scripts`, so no `postinstall` or `prepare` script runs, and the customer's application is never started. The honest statement is that we run their compiler, not that we run nothing.

**The indexer and the detector now meet on nested changes, and the match is weak where the code is shallow.** This was previously recorded as the indexer and the detector meeting only on depth-1 changes, with three windows quoted as though they were three measurements. They were not: `.cache/specs` holds duplicate specifications — `v2300.json` and `v2320.json` are byte-identical, as are `v2330`/`v2340`/`v2345`, because Stripe tags every SDK release whether or not `spec3.json` moved — so `v2320→v2330` and `v2300→v2330` are one window, and the two figures came from counting different things (deduplicated rows in Postgres against raw records from `oasdiff`).

Measured on that one window, and stated as what re-runs rather than as what one run returned: **none of the filtered records is depth-1.** The shallowest is three segments, and the whole population reduces to four underlying schema changes — leaves `description`, `iin`, `issuer` and `stored_credential_usage` — re-reported once per distinct route to them under `error/payment_method/card/generated_from/…`. Every route is a walk of a cyclic schema graph, which is why there are so many of them and why nobody should quote how many: `2026-07-29-depth-measurement.md` re-ran this command nine times on hash-verified inputs and got nine different counts, from 29,768 records to 1,375,504. This paragraph previously carried two of those samples — 672,286 raw and 327,124 filtered — as though they described the window. They describe a run. The structural claims here are the ones that reproduced, on every run, and they are the ones the detector rests on.

Both sides now record and compare paths, anchored at the outermost segment. Against that window a call site reading `error` matches records where it previously matched none, and its ceiling is the whole filtered population; a call site reading only `id`, `status` and `amount` still matches nothing, which is the filter doing its job. Anchoring also closed a wrong-answer case the old rule had: `description` is one of the four leaves, so a call site reading the genuine top-level `charge.description` matched a change twenty levels below it under `error/payment_method/card`. The failure direction was never purely conservative. The counts these sentences carried are omitted rather than restated for the reason above — the comparison they illustrate does not depend on them, and a number that changes by a factor of thirty between runs is not evidence of anything it would be quoted for.

What remains open is the strength of the match, not its existence. Static syntax follows a member chain until a subscript or a `map` callback, so a call site's recorded path is typically one to three segments against a change twenty-five deep. Those emit as operation-match-only findings that name both ends rather than claiming the call site read the changed field. Narrowing them needs type resolution, not a threshold.

**The push lease now reads authorship, but only at the tip.** `push_branch` fetches the branch's remote tip, refuses outright when that commit's author is not `COMMIT_AUTHOR_EMAIL`, and otherwise names it in `--force-with-lease=<branch>:<sha>`. A reviewer who pushes a fixup onto Sync's branch between runs now abandons the finding with a reason naming them, rather than having their commit replaced. It reads the **author** rather than the committer deliberately: GitHub rewrites the committer on a squash and on any web-UI edit, and a rebase rewrites it too, so reading the committer would make Sync disown a branch it wrote every line of. Abandonment after a push now deletes the branch as well, refusing when there is an open pull request, when the tip is not Sync's, or when the tip moved after the check — the deletion carries the same lease.

The check covers every commit the push would discard, not merely the tip. The range is the remote branch's commits that the replacing commit does not carry forward — `<remote tip> ^HEAD` — and both halves earn their place. Without the range, a reviewer's fixup with any Sync-authored commit above it leaves a branch whose tip is Sync's and whose history is not, and a tip-shaped check reports it as Sync's to replace. Without `^HEAD`, a fixup that the push *carries forward* rather than destroys would be refused, abandoning findings over work that was never at risk. Deleting either half fails the suite.

What this still does not do is authenticate. `git commit --author` sets that field to anything, so anyone who can push to the branch can present as Sync; what stands against that is the lease plus the customer's own branch protection. The guard protects against clobbering human work by accident, which is the realistic failure, and it should not be described as more than that.

**A codemod cannot check its own work by re-parsing the result.** The obvious safety net for a deterministic edit is to parse the output and reject it if the tree contains an error, and against tree-sitter that net does not hold: removing an object property while leaving its separating comma behind produces `{ model: "x", , max_tokens: 16 }`, which is not valid TypeScript and which tree-sitter reports with **zero `ERROR` nodes, zero `MISSING` nodes, and `root_node.has_error` false** — the same verdict it gives the correct source. Measured directly against `tree_sitter_typescript`, and it holds for a leading comma and for two consecutive dangling commas as well. The broken result parses as cleanly as the correct one, so a validate-after-edit check passes it, including the cheap `has_error` form anyone would reach for first. It is why the edit primitives in `sync.route.templates` delete a property and its separating comma as one span instead of deleting the pair and repairing afterwards — the span is not a stylistic preference, it is the only part of the operation that is verifiable. The general form of the constraint: a codemod's correctness has to be established by construction, because the parser will not tell us we were wrong.

**A remediator that renders a diff without writing it reports success and ships nothing.** Nothing in the pipeline applies `patch.diff` — `make_patch` stores the `Patch`, `static_verify` typechecks the working tree, and `push_branch` stages it with `git add -u`. A codemod that computed the correct edit and returned it as a diff, without touching the clone, therefore produced a branch with an empty commit and a green verdict. This shipped in `literal_swap` and again in both parameter remediators, found the second time by one worker reading another's fix, and it is recorded here because the failure is invisible from the diff, which is correct in every case. The tests that hold it closed assert on the file's bytes rather than on the returned diff, and the decline path asserts `st_mtime_ns` is unchanged so that an unconditional write of identical bytes cannot pass.

### What the M0 acceptance run proved

The milestone's definition of done — one `sync run` invocation producing a pull request on a real repository whose checks pass, unattended — is met. Against a fork of `stripe/stripe-connect-furever-demo`, with a request property removed from a real pinned Stripe specification, one command produced [pull request #1](https://github.com/stroland02/stripe-connect-furever-demo/pull/1): two deletions in one file, removing the withdrawn `receipt_email` argument at both call sites that passed it, `tsc` green on the branch in 38 seconds. Nothing else in the file was touched.

Every stage is now exercised in a single invocation: specification fetch, `oasdiff`, noise filtering, symbol mapping, clone, dependency installation without lifecycle scripts, indexing, the graph store, detection, the patch agent, baseline-subtracted typechecking, branch push under Sync's own commit identity, the CI wait, and the pull request.

Two honest qualifications. The vendor change was constructed — a property removed from a real specification rather than one Stripe withdrew — because no window of Stripe's own history examined here contains a top-level breaking change this application would notice, which the limitation above on match strength explains. And the repository's own pre-existing `test` workflow fails on the pull request for a reason that predates Sync: it invokes a `yarn run validate-change` script absent from its `package.json`. The gate Sync verified against is the typecheck, and it passes.

## Verification

Test-driven throughout. A failing test precedes implementation in every case.

- **Contracts** — protocol conformance tests in `sync.core` that every adapter must pass, plus an import-linter test enforcing that `sync.core` imports no sibling package.
- **Stripe adapter** — two pinned specification versions committed as fixtures with a hand-labeled expected `VendorChange` set. Deterministic; no network access in tests.
- **TypeScript adapter** — small fixture repositories under `tests/fixtures/ts/`, each with known call sites and a golden `CallSite` set. Includes deliberately hard cases: aliased imports, a client wrapped in a helper function, destructured responses.
- **Detector** — a synthetic ADG and synthetic changes, asserting the exact finding set, including the true negatives.
- **Remediation graph** — node-level unit tests, plus a whole-graph test against a stubbed forge and a stubbed patch node, asserting retry bounds and abandonment behavior. No test makes a model call; the Agent SDK is exercised only in the end-to-end run.
- **End to end** — `sync run --vendor stripe --from <v1> --to <v2> --repo <fixture>` against a fork we control, asserting that a pull request appears and its checks pass.

M0 acceptance is one command producing one green pull request. Anything short of that is not M0 complete.
