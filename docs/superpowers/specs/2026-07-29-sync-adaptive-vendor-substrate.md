# Sync — the adaptive vendor substrate

**Date:** 2026-07-29
**Status:** Draft for review
**Question it answers:** how does Sync support the long tail of third-party APIs without a human writing an adapter per vendor?

## The claim this document has to defend

Sync's moat is coverage. A live codebase calls dozens of third-party APIs; the design document
states plainly that we cannot write dozens of adapters ourselves, which is the entire argument
for open core. But "someone else will write them" is a hope, not a mechanism, and a plugin SDK
with ten adapters in it is a plugin SDK nobody adopts.

The mechanism has to be that **most vendors need no adapter at all**.

That is not a new idea here. `2026-07-27-sync-adapter-targets.md` already argues it, and one
sentence in the design document already states the principle: *the scaling unit is the artifact
tier, not the vendor*. What follows is that argument taken to its conclusion, checked against
what is actually built, and turned into a sequence.

## What is already true

Verified against the tree at `9247d41`, not recalled:

**Discovery from generator manifests is built.** `sync.signals.generated` reads Stainless's
`.stats.yml` and Speakeasy's `.speakeasy/workflow.yaml`, both of which name the specification the
SDK was generated from. The module docstring states the reason this is reliable and it is the
strongest sentence in the codebase on this subject: the generator writes the manifest *for its
own reasons* — reproducible regeneration — so **no vendor has to cooperate and no agreement can
be withdrawn.**

**Vendor routing is data, not code.** `sync.signals.registry` maps a vendor id to an adapter, and
its docstring records why: `cli.py` once constructed `StripeAdapter` by name in two places, so a
second adapter existed and could never be reached. What was unreachable was not a feature but the
claim the project rests on.

**The protocol has been tested against a genuinely different vendor.** Twilio proved
`VendorAdapter`'s change half is a real plugin surface and its symbol half was not — that half
had exactly one implementation, and a protocol with one implementation is a description of that
implementation.

**A conformance kit exists** so an outside author can find out they are wrong before the pipeline
tells them, badly.

## The bottleneck, closed 2026-07-29

This section described the system's highest-value defect. It has since been repaired, and the
paragraphs below record what the claim was and what measurement retired it, because a spec that
silently drops a limitation teaches nobody why it mattered.

**What was true when this was written.** `src/sync/index/typescript.py:29` read
`_SDK_PACKAGE = "stripe"`. The indexer resolved call sites for exactly one vendor: it checked
`package.json` for `stripe`, resolved identifiers bound to `new Stripe(...)`, and emitted symbols
shaped `stripe.<chain>`. The two halves of the system had generalised asymmetrically — SIGNAL
could discover a specification for any vendor a generator serves while INDEX could bind only
Stripe, so a vendor whose spec we diffed perfectly still produced zero findings. The sentence
this document used to carry was: "Twilio's adapter can map `twilio.insights.v1.calls.fetch` onto
an operation, and no indexer will ever hand it that symbol."

**What is true now.** The constant is gone. Both indexers take the package from the vendor
adapter — `sdk_bindings[language_id]` — and never from the module. A vendor whose package name,
import specifier and symbol root disagree declares all three; one whose names agree declares
none, which is what keeps the change additive.

The evidence is `tests/test_indexer_vendor_agnostic.py` and `tests/test_scoped_package_symbols.py`,
37 tests, green. They bind Twilio in **both** languages against real operations —
`twilio.insights.v1.callSummaries.list` resolves to `ListCallSummaries`, and the TypeScript and
Python fixtures agree the repository depends on Twilio — and they cover the two forms that were
never exercised while a bare word was the only package name: a scoped package
(`@anthropic-ai/sdk`, whose import specifier is not its symbol root) and a client built by calling
the package's own default export rather than by construction.

**The lesson this section exists to keep.** The defect was invisible from a green suite because
every indexer fixture was a Stripe fixture — the same shape as the scoped-package gap that
followed it, where the suite stayed green because no fixture declared a scoped package. A test
suite proves the cases it contains. When one vendor, one shape, or one spelling is the only thing
any fixture ever declares, the suite is measuring that instance and reporting it as the protocol.

## The architecture: four tiers, and vendors are configuration

Order by *how the specification is found*, not by who the vendor is. Each tier is one piece of
code serving every vendor in it.

| Tier | How the spec is found | Per-vendor cost | Status |
|---|---|---|---|
| **0 — Generator-discovered** | The SDK repository commits a manifest naming its spec | Zero. A vendor is a row. | Built |
| **1 — Registry-discovered** | A public directory of OpenAPI definitions | Zero | Built and wired into intake |
| **2 — Vendor-published** | Configured location, versioned by tag or filename | One configuration entry | Built (Stripe, Twilio) |
| **3 — Synthesised** | No specification exists; the contract is inferred | Real work, and honest about it | Partial |

Tier 1 was the gap worth taking next on the signal side, and it is now closed end to end.
`src/sync/signals/registry_tier/directory.py` provides `parse_directory` and `versions_after`,
which answer which APIs a public directory holds and when each last moved, and dependency intake
consumes both — `sync.signals.intake` imports `versions_after`, `sync.cli` imports
`parse_directory`. Their entries left `scripts/dead_links_baseline.txt` in the commit that wired
them, which is the mechanic those entries specified when they were written.

This tier is deliberately **not** a `VendorAdapter`, and that constraint survives the wiring. The
directory's `swaggerUrl` points at its own storage rather than the vendor's host, and a large
share of entries are Swagger 2.0 needing conversion, so a change derived from it is a third
derivation from the vendor's truth. It is good enough to tell a customer that a declared
dependency is watchable. It is not good enough to open a pull request against, and wiring it to
the remediation pipeline would be the defect rather than the fix.

[APIs.guru's
openapi-directory](https://github.com/APIs-guru/openapi-directory) is a machine-readable
directory of API definitions with a REST API over it, and
[Speakeasy maintains a fork](https://github.com/speakeasy-api/openapi-directory) of the same
data. One adapter that reads a registry covers every vendor in it, on exactly the same terms as
tier 0: no vendor cooperation, no agreement to withdraw.

**Checked against `api.apis.guru/v2/list.json` rather than assumed.** The three questions that
decide whether this tier is real:

*Is there a cheap change trigger?* Yes, and a better one than tier 0's. There is no hash or
checksum, but every version carries `added` and `updated` ISO timestamps, and the whole registry
is one document. So a single fetch of `list.json` yields every vendor's last-updated time, and a
specification is downloaded only when a timestamp moves. Tier 0 must poll one manifest per SDK
repository; tier 1 polls one file for the entire catalogue.

*What is a version?* Real and diffable. Each entry carries a `versions` map keyed by version
string, each with its own `swaggerUrl`, so two comparable artifacts exist and `fetch_changes` has
something to diff.

*Whose artifact is it?* **The registry's.** `swaggerUrl` points at
`api.apis.guru/v2/specs/...`, not at the vendor's host — this is a mirror, and the design
document already calls vendor-hosted strictly better. Worse, `openapiVer` is `"2.0"` on a large
share of entries, meaning Swagger 2.0 rather than OpenAPI 3, so `oasdiff` will need converted
input for those. A converted mirror is a **third** derivation from the vendor's truth, and the
threat model's rule bites hardest here: a signature proves origin, not correctness, and nobody at
the vendor signed this.

That last answer is what fixes the tier's role. Registry provenance is good enough to *discover*
that a vendor exists, has a machine-readable contract, and roughly when it last moved — which is
exactly what the intake report in step 2 needs. It is not obviously good enough to open an
unattended pull request against a customer's repository. The honest default is that a
registry-derived change carries its own rung and feeds intake, and that promoting one to a
pull-request source requires the vendor-hosted artifact the registry merely points at.

Tier 3 is where the runtime signal earns its place. `observed_call` already records what the
customer's code actually calls, and `observed_shape` records the shape of what came back. A
vendor with no published specification still has an *observed* contract, and drift against it is
already detectable — `ObservedDriftDetector` exists. The synthesised tier is not speculative; it
is the tier we accidentally built first.

## Making INDEX symmetric, which is the actual work

The indexer must do for the customer's dependency manifest what tier 0 does for a vendor's SDK
repository: **read it, and ask what is watchable.**

```
package.json / pyproject.toml
        │
        ▼
  every declared dependency          ← today: filtered to one hardcoded name
        │
        ▼
  which of these does a tier serve?  ← registry lookup, not a hardcoded name
        │
        ▼
  index call sites for each          ← today: one vendor's import and construction rules
```

Two things had to change, and only one of them was hard.

**The easy half — stop filtering to one package — is done.** `matches`, `_sdk_version` and
`_client_identifiers` took the package name as a constant; they now take it from the bindings
`sync.index.sdk_bindings` derives from the vendor adapters the instance holds. It was mechanical,
as this said it would be.

**The hard half: the shape of a call site is per-SDK, not per-vendor.** `stripe.charges.create`
and `twilio.insights.v1.calls.fetch` are both member chains rooted at a client, which is the
common case and generalises. But `openai.chat.completions.create` nests differently, some SDKs
expose free functions, and Python's `import stripe` binds a module rather than a variable — the
Python adapter's docstring already records that as a deliberate difference.

This is the same wall the design document names as the part that resists templating, and it is
where the honest answer is that one derivation strategy will not carry a catalogue.

## Where an agent belongs, and where it does not

The temptation is to have a model read an SDK and write an adapter. That inverts this project's
central discipline. Everything here is built on **nothing reaches a pull request unverified**, and
a generated adapter is a generated *guess* about a contract.

The rule that keeps it honest is the one already stated for symbol mapping: **failing to resolve
is recoverable, resolving incorrectly is not.** An unresolved symbol is visibly unresolved and
countable. A wrongly resolved one produces a pull request against code that never made the call,
and nobody learns it was wrong.

So an agent may **propose**, and only where a mechanical check can **refute**:

- **Proposing a symbol map from an SDK's own type definitions.** Refutable: every proposed symbol
  is checked against the specification's operation set, and the map's coverage is measured. The
  Twilio work established the measurement discipline — state the denominator, and reject a source
  that raises apparent coverage while being wrong.
- **Proposing which declared dependency is a watchable API client.** Refutable: the proposal is
  a package name, and either a tier resolves a spec for it or none does.
- **Proposing a client-construction rule for an unfamiliar SDK.** Refutable: run the proposed rule
  over the customer's repository and count resolved call sites. A rule that resolves nothing is
  rejected without a human reading it.

And where it does not belong: an agent must never author the *change* interpretation. `oasdiff`
is authoritative on what changed; the changelog only enriches. That constraint is in the risk
register and it should survive this document unchanged.

## What the market does, and what nobody does

Software composition analysis already solves half of this. [SCA
tools](https://www.mend.io/blog/best-software-composition-analysis-sca-tools-top-solutions/) scan
a codebase and enumerate every open-source dependency, known and unknown, and the mature ones add
[reachability analysis](https://cycode.com/blog/top-enterprise-sca-tools/) to distinguish a
dependency that is merely present from one whose vulnerable path is actually called. That is the
same question as "which of these dependencies is a *live* API client", and it is solved.

[API discovery tools](https://www.stackhawk.com/blog/best-api-discovery-tools/) solve the other
half from traffic, cataloguing internal, external and third-party APIs by observation.

**Neither joins the two to the vendor's own published contract.** SCA tells you that you depend on
`stripe@18`; it does not know Stripe removed a field. API discovery tells you that you call
`POST /v1/charges`; it does not know that endpoint's request schema changed last Tuesday. The
join — dependency graph, vendor artifact, runtime evidence, one remediation pipeline — is the
thing this project already has and the market does not.

The strategic conclusion: **do not build SCA.** Consume its shape. The reachability idea in
particular is worth stealing outright, because "declared but never called" is exactly the noise
that would otherwise flood a coverage-driven system.

## Sequence

Ordered by what unblocks the most, and each step is verifiable on its own.

**1. Un-hardcode the indexer. Done.** The SDK package is taken from the vendor rather than from a
module constant, through `sync.index.sdk_bindings`. Its closing condition is met:
`tests/test_multi_vendor_index.py:182` indexes `tests/fixtures/ts/twilio` and resolves
`twilio.messages.create` to the Twilio operation, and the same file pins what is still out of
reach — `client.insights.v1.calls(callSid).fetch()`, a chain broken by a call in its middle,
yields no site even though the symbol map holds the operation. Steps 2 to 5 below have not
started.

**2. Dependency intake.** Read the customer's manifest, ask the registry which declared
dependencies a tier can serve, and report the answer as a first-class artifact: watched, watchable
but unconfigured, and not watchable. That report is a sales asset as much as an engineering one.
*Closes when a repository declaring five third-party SDKs produces a correct three-way split.*

**3. Registry tier.** One adapter over a public OpenAPI directory. *Closes when a vendor nobody
configured produces a real `VendorChange` from two registry versions.*

**4. Extract symbol maps from the SDK, do not generate them.** A generated SDK states the HTTP
method and path in the source that makes the call, so the map is read rather than proposed — see
the section above. Cross-check the extracted map against the specification's operation set, and
confirm against `observed_call` where traffic exists. A model is used only where extraction finds
no pattern, and then only to locate one; its output is refutable by running the extractor it
implies. *Closes when a vendor with no hand-written map reaches measured coverage against a named
denominator, and a deliberately corrupted SDK source is caught by the spec cross-check rather than
by a reviewer.*

**5. Reachability.** Rank by call sites actually indexed, not by dependencies declared.

## The symbol map does not need a model, and that resolves the hole

The audit below found that coverage cannot refute a plausible-but-wrong mapping. The fix is not
a better metric. It is to stop generating the mapping in the first place.

**A generated SDK contains the mapping literally, in the source the customer executes.** Verified
against `stripe-node`'s `src/resources/Charges.ts`:

```typescript
list(params?: ChargeListParams, options?: RequestOptions): ApiListPromise<Charge> {
  return this._makeRequest('GET', '/v1/charges', params, options, {
    methodType: 'list',
  }) as any;
}
```

That is `stripe.charges.list → GET /v1/charges`, stated by the artifact that makes the call.
It is not an inference from URL shape, not a companion manifest, and not a model's proposal.

This matters because of what the artifact *is*. A specification describes what the vendor says
the API does. A model's proposal describes what the model believes. **The SDK source describes
what the customer's process will actually send, and it cannot be wrong about that, because it is
the thing that sends it.** Where the SDK and the specification disagree, the SDK is what runs.

The consequence for step 4 is that its ordering inverts:

1. **Extract** from the SDK's own source where the SDK is generated. Deterministic, auditable,
   re-runnable per SDK version, and free of model cost entirely.
2. **Cross-check** the extracted map against the specification's operation set. Two independently
   derived artifacts agreeing is real refutation; a symbol that resolves to an operation no spec
   declares is a defect in one of them and worth surfacing either way.
3. **Confirm against traffic** where it exists. `observed_call` records the operation and
   `url_template` of requests that actually happened, which is a third independent artifact and
   the only one derived from reality rather than from a document.
4. **Propose with a model only where extraction fails**, and then only to locate the calling
   pattern in an unfamiliar SDK's source — a proposal that is itself refutable, because an
   extractor built on it either resolves symbols against the spec or does not. Stated more
   sharply by the coordinator who took this step, and the sharper form is the rule:
   **finding no pattern is a report rather than a licence.** An extraction that finds nothing is
   a fact to record about that SDK, not permission to guess at it.

So the model's role shrinks from *authoring a contract* to *finding where a contract is written
down*, which is the difference between a guess nobody can check and a search whose result is
checkable by running it.

This aligns the two halves of the architecture: the vendors whose specs tier 0 discovers from a
generator manifest are, by construction, the vendors whose SDKs are generated. Same set. Both
facts fall out of the generator having written things down for its own reproducibility.

**But "free" was an overclaim, and checking three generators disproved it.** The mapping is
present in all three and stated differently in each:

| Generator and language | Example | HTTP verb | Path |
|---|---|---|---|
| Stripe's own, TypeScript | `stripe-node` | `_makeRequest('GET', …)` — first argument | `'/v1/charges'` — plain string, second argument |
| Stainless, **TypeScript** | `openai-node` | the method name itself: `this._client.get(…)` | `` path`/models/${model}` `` — tagged template |
| Stainless, **Python** | `openai-python` | which helper is called: `self._get` / `self._post` / … | first argument of that call: a plain literal, or `path_template(…)` |
| Speakeasy, TypeScript | `vercel/sdk` | `method: "POST"` — object property | `pathToFunc("/v11/projects")()` — helper call |

All three are mechanically extractable and none of them is extractable by the *same* rule. An
extractor written against `stripe-node` finds nothing in `openai-node`, because Stainless puts
the verb in the method name and the path inside a tagged template.

**The unit is generator × language, not generator.** That correction came from the worker
building the first extractor, against my table above, and it is the second time this claim has
had to be narrowed. Stainless emits Python and TypeScript differently — Python writes the path
as a positional literal or `path_template(…)`, TypeScript writes it as a tagged template — so a
rule claiming to cover both would be guessing about whichever flavour it had not seen. Adding
`stainless-typescript` to a working `stainless-python` extractor is a second module of comparable
size, not a branch inside the first.

So the cost does not vanish, and it scales with generator × language rather than with generator:
call it a handful of generators times the two or three languages that matter, against hundreds of
vendors. That is still the argument tier 0 makes for specifications and it is still strong — but
the honest multiplier is a small number times another small number, not one rule per generator,
and I have now overstated this twice.

Two consequences worth stating plainly. A hand-written SDK has no generator rule to write, and
falls back to measured coverage with a stated denominator like any tier 2 vendor. And an
extraction rule is a per-generator artifact that can rot when a generator changes its emitted
shape — so a rule needs its own regression fixture pinned to a real SDK version, exactly as the
vendor adapters pin specification fixtures.

Where it does not reach: a hand-written SDK, where extraction has no pattern to find. That is the
honest boundary, it is the same boundary tier 2 already has, and the answer there is the same as
it has always been — measure the coverage, state the denominator, and let the gap be countable
rather than filled with guesses.

The wider literature is worth knowing but does not change this. The generic problem of
[validating LLM-generated mappings](https://cloudsecurityalliance.org/blog/2026/07/02/validating-llm-generated-control-mappings-beyond-aggregate-accuracy)
is hard precisely because there is no ground truth to check against, and the usual mitigations —
[cross-validation between models](https://arxiv.org/pdf/2502.07036),
[differential testing](https://dl.acm.org/doi/10.1145/3735637) — are consensus mechanisms rather
than correctness ones. Our case is easier than the literature's and it would be a mistake to
adopt the literature's answer: **we have ground truth, so agreement between models is the wrong
tool.**

## Prior art, and what it means that so much of this is solved

Searched rather than assumed. Most of what this project does has been done — on packages.

**Provider-side breaking-change detection is mature and in production.** JAPICMP and REVAPI run
against Apache Commons, Spring, Gson and Neo4j; [ROSEAU](https://arxiv.org/pdf/2507.17369) does
fast source-based analysis; [AutoGuard](https://arxiv.org/pdf/2311.08175) analyses REST changes
statically without running the service and is wired into GitHub and GitLab CI to generate
changelogs and flag breaks on pull requests.

**Automated client migration is an active field.** One study mined
[461 correct migration rules from 1,179 pull requests](https://arxiv.org/pdf/2301.04563) across
four Python libraries. And [Agentic Generation of AST Transformation Rules
(2026)](https://arxiv.org/pdf/2606.24446) is close to this project's tier-0 codemod: agents
synthesise AST transformations for breaking updates, validated by executing tests. That is the
same containment discipline used here, arrived at independently, which is reassuring rather than
threatening — our remediation approach is not novel and does not need to be.

**What none of it does is the web API surface.** Every one of those works on packages, where the
contract is a signature in an artifact you compiled against and hold a copy of. Two differences
do real work:

- A package break is found by comparing two artifacts already on disk. A web API break is only
  findable if you know **where the vendor's specification lives**, which is the discovery problem
  this document exists for.
- A package break is caught by a compiler or a test. A web API break **compiles perfectly and
  fails in production**, which is why the gate has to be the customer's CI.

The open research direction those studies name — *automating change-impact analysis to improve
notification accuracy and trustworthiness* — is the ADG join. Somebody else's stated open problem
is this project's shipped mechanism, and that is the clearest evidence available that the join is
the defensible part rather than the pipeline around it.

## Checked against the documents that bind this

Not a formality. One of these found a hole in the proposal above.

**Latency architecture — "every proposed agent must shorten the critical path or improve a
result. An agent that does neither is latency and cost with extra steps."** Step 4 is the only
agent this document adds, and it passes on the second clause rather than the first: it improves
coverage, which is a result. It must also stay off the critical path, and it does — a symbol map
is built once per vendor version and read from disk on every run, which is precomputation in the
sense that document argues for. **This is a constraint on the implementation, not a description
of it:** an agent invoked per finding, or per run, would fail this rule outright and must be
rejected in review.

**Pipeline discipline.** Tiers 0 and 1 fetch artifacts, so the rules apply unchanged. Keep the
raw record — a discovered specification is stored as fetched, not only as interpreted, for the
same reason `VendorChange.raw` exists. Every binding carries its rung, and a binding derived from
a *discovered* spec is not the same evidence as one from a configured vendor; the rung has to say
which. And a signature proves origin, not correctness — which matters more here than anywhere
else, because tier 1 introduces artifacts nobody at the vendor published.

**Threat model — and this is the hole.** The document's containment argument is that the
verification gate stops an injected instruction, because a malicious edit still has to pass `tsc`
and the customer's CI and still lands as a reviewable diff. That argument does not cover a
poisoned *symbol map*. A wrong mapping does not produce a malformed patch; it produces a
perfectly valid patch applied to **the wrong call site**, which typechecks, passes CI, and reads
as correct.

So "refutable by coverage measurement" is insufficient as stated above. Coverage counts how many
symbols resolved, not whether they resolved *correctly*, and a plausible-but-wrong map scores
well. The Twilio work already demonstrated the failure mode in miniature: `x-twilio.className`
raised apparent coverage from 29% to 45% and was wrong on every path where it disagreed with the
path segment. That was caught by a human reading generated SDK source, not by a metric.

Two consequences, and they change step 4 rather than decorating it:

- A proposed mapping must be checked against **the SDK's own source or type definitions**, not
  only against the specification's operation set. Agreement between two independently derived
  artifacts is refutation; agreement with the thing that generated the proposal is not.
- Until that check exists, a proposed map is **evidence for a human**, not an input to the
  pipeline. Mapping provenance therefore belongs in the rung: `proposed` is a fourth rung, and a
  finding resting on one should say so on the pull request.

**Positioning and open core.** The free cross-vendor change feed described there is the clearest
beneficiary. A feed's value scales directly with how many vendors it covers, and tiers 0 and 1
are the only mechanisms here whose coverage does not scale with headcount. `sync.signals.feed`
already publishes and consumes it. This document is the supply side of that strategy.

**Cost.** Tiers 0 and 1 add no per-vendor engineering, and the change-detection cost is already
solved: a Stainless manifest carries `openapi_spec_hash`, so a poll reads a text file and the
specification is fetched only when the hash moves. That property should be a requirement of the
registry tier too, not a happy accident of the generator tier — a tier that must download every
specification to learn nothing changed does not belong in this architecture.

**Simplicity for users.** The user-visible surface of all of this is one artifact: a repository's
dependencies split into watched, watchable-but-unconfigured, and not watchable. Nobody configures
a vendor, and nobody learns what a tier is. If a tier ever becomes something a user has to know
about, the abstraction has failed.

## What this document does not claim

It does not claim the symbol map problem is solved. Step 4 is the only speculative item, it is
sequenced last deliberately, and the measurement discipline around it matters more than the
mechanism.

It does not claim tier 0 covers the market. It covers vendors served by two generators, which is
a real and growing set and not a majority.

And it does not claim the indexer change is small because it is mechanical. Making `matches`
take a parameter is mechanical; deciding what a call site *looks like* in an unfamiliar SDK is
the same hard problem in a new place, and the honest position is that tiers 0 to 2 buy time to
answer it with evidence rather than guesses.
