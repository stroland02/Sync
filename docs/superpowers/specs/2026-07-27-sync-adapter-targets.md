# Sync — Adapter Targets

**Date:** 2026-07-27
**Status:** The rubric is binding on adapter selection. The target table is verified for spec
availability and explicitly unverified for change frequency.
**Scope:** Which vendors Sync writes adapters for, in what order, and the discovery mechanism
that makes coverage cheaper than one adapter at a time.

## Popularity is the wrong criterion

The obvious way to pick targets is to rank APIs by how many codebases call them. That ranking
is worth having and it is not sufficient, because Sync cannot bind an API it cannot diff.

An adapter needs four things, and the first is a hard gate:

1. **A machine-readable specification, published and versioned.** oasdiff diffs two pinned
   spec versions. No spec means no SIGNAL stage, and every downstream stage is starved. This is
   pass/fail, not a score.
2. **A stable symbol-to-operation mapping.** RESOLVE and `operation_for_symbol` need to get from
   `stripe.charges.create` to `POST /v1/charges`. A generated SDK supplies this almost free; a
   hand-written one means hand-written mapping.
3. **Actual breaking-change frequency.** This determines findings volume, and it is the axis
   where the intuitive answer is wrong most often — see Stripe below.
4. **Consumption breadth.** How many codebases call it, which sets how much the binding is worth
   once it exists.

**Stripe scores perfectly on the first two and poorly on the third.** Since
`2024-09-30.acacia`, monthly Stripe releases carry no breaking changes and breaking changes are
confined to semiannual major releases. It remains the right M0 ground truth — pinned versions, a
machine-readable diff, an SDK generated from the spec — and it is close to the lowest-frequency
findings source in the market. A target list built on "who is most popular" would have stopped
there and starved.

## The discovery mechanism

This is the part that matters more than any individual row below. **A generated SDK names the
spec it was generated from, in a committed file, in a public repository.** That holds across
generators, which makes it a discovery mechanism rather than a vendor trick.

Two conventions are confirmed. Both point from an SDK repository — easy to find, because
developers already depend on it — to the authoritative spec.

**Speakeasy** writes `.speakeasy/workflow.yaml`, naming the source location directly:

```yaml
sources:
    vercel-OAS:
        inputs:
            - location: https://openapi.vercel.sh/
```

That is how Vercel's spec endpoint was found. Note it is **vendor-hosted**, which is strictly
better than the Stainless case below: it is the authoritative artifact, not a mirror.

**Stainless** writes `.stats.yml`:

```yaml
configured_endpoints: 131
openapi_spec_url: https://storage.googleapis.com/stainless-sdk-openapi-specs/anthropic/anthropic-<sha>.yml
openapi_spec_hash: d2deb0fef6a15bf53cc6c53f07973a54
config_hash: 44bd45774e5a06742c1fb8f0e20e7864
```

Verified present, with an endpoint count and in most cases a spec hash, across nine of eleven
repositories sampled on 2026-07-27:

| SDK | `configured_endpoints` | `openapi_spec_hash` |
|---|---|---|
| `openai/openai-python` | 278 | `e9576bced964246b7e685a5ad30afffa` |
| `openai/openai-node` | 277 | `e9576bced964246b7e685a5ad30afffa` |
| `anthropics/anthropic-sdk-python` | 131 | `d2deb0fef6a15bf53cc6c53f07973a54` |
| `anthropics/anthropic-sdk-typescript` | 131 | `d2deb0fef6a15bf53cc6c53f07973a54` |
| `cloudflare/cloudflare-python` | 2521 | *(absent)* |
| `cloudflare/cloudflare-typescript` | 2439 | *(absent)* |
| `lithic-com/lithic-python` | 213 | `93aea3855d2d1c390107d223762aa818` |
| `orbcorp/orb-python` | 144 | *(absent)* |
| `BrowserBase/sdk-python` | 38 | `71dfbc1021a33dd7fc9d82844965b1b3` |
| `browserbase/sdk-node` | 38 | `71dfbc1021a33dd7fc9d82844965b1b3` |

Three properties follow, and each is worth more than a hand-written adapter.

**The spec hash is identical across languages for the same vendor.** OpenAI's Python and Node
SDKs carry the same hash; so do Anthropic's and Browserbase's. One spec generates every binding,
so one change signal covers every language Sync ever supports for that vendor.

**A hash change is a change signal on its own.** Detecting that `openapi_spec_hash` moved between
two commits requires no download and no diff — it is a string comparison against a file in a
public repository. That is a near-free SIGNAL-stage trigger, and only the vendors whose hash
actually moved need the expensive spec fetch and oasdiff run.

**`configured_endpoints` is a free denominator.** The observed-contract-drift spec argues coverage
should be reported against operations the customer actually calls rather than spec paths. This
gives the honest spec-side denominator per vendor at zero cost, which is what the internal
engineering number should be measured against.

This is the synthesized-adapter machinery the competitive-position spec named as the real moat —
"the moat is the synthesis machinery that produces coverage without hand-authored adapters."
A `GeneratedSdkAdapter` that reads whichever manifest a repository carries, follows the spec
location it names, and hands the result to the existing oasdiff pipeline is **one adapter that
covers every vendor either generator serves**, not one per vendor. Anthropic acquired Stainless
in May 2026, and OpenAI and Google both depended on it; Speakeasy serves a separate and
overlapping population. Neither generator has to cooperate, because the manifest is already
committed to a public repository for its own reasons.

The generator is also the right unit of effort. Supporting a new *generator* is a day of work
that yields every vendor using it; supporting a new *vendor* under a known generator is a
configuration line. Adapter coverage stops scaling with vendor count and starts scaling with
generator count, and there are not many generators.

Two caveats recorded rather than smoothed over, the first corrected after running the parser
against live manifests. **Cloudflare's and Orb's `.stats.yml` contain only
`configured_endpoints`** — no hash *and no URL*. An earlier draft of this section said the hash
was missing and the adapter could fall back to fetching; that was wrong, because there is
nothing to fetch. Those vendors yield a coverage denominator and still need a hand-written
adapter, so cohort A is smaller than its row suggests. Measured on 2026-07-27: five of seven
sampled manifests are fetchable, four of seven carry the cheap hash trigger.

And `openapi_spec_url` points at Stainless-hosted storage rather than the vendor, which
is a third-party dependency in the SIGNAL path — acceptable for a change *hint*, not acceptable
as the authoritative artifact. Prefer a vendor-published spec where one exists; use this to know
*when* to look.

## Verified targets

Spec availability confirmed on 2026-07-27 by fetching the path shown. **Change frequency is not
verified for any row** — that is the measurement this list still needs, and it is the axis that
decides ordering.

| Vendor | Spec location | Size | Why it earns a slot |
|---|---|---|---|
| **Stripe** | `stripe/openapi` → `openapi/spec3.json` | 7.9 MB | M0 ground truth. Best-behaved spec in the market, lowest findings frequency. |
| **OpenAI** | `openai/openai-openapi` → `openapi.yaml` | 2.8 MB | 278 endpoints. Every startup consumes it; model deprecations break production. |
| **Anthropic** | via `.stats.yml` → Stainless storage | — | 131 endpoints. Same shape as OpenAI, same consumer base. |
| **GitHub** | `github/rest-api-description` → `descriptions/api.github.com/api.github.com.json` | 12.8 MB | Nearly universal in CI and tooling. Vendor-published and versioned per release. |
| **Cloudflare** | `cloudflare/api-schemas` → `openapi.json` | 23.0 MB | 2521 endpoints. The scale test: if the pipeline survives this, spec size is a solved problem. |
| **Twilio** | `twilio/twilio-oai` → `spec/yaml/twilio_api_v2010.yaml` | 1.5 MB | Long-lived, heavily consumed, spec split per product. |
| **Plaid** | `plaid/plaid-openapi` → `2020-09-14.yml` | 3.0 MB | Filename *is* the pinned version — the cleanest version-pair story on this list. |
| **Sentry** | `getsentry/sentry-api-schema` → `openapi-derefed.json` | 3.9 MB | Already an M2 signal source. Being a consumer of Sentry and a watcher of it compound. |

### The AI providers are the reordering argument

Stripe ships breaking changes twice a year. OpenAI and Anthropic ship model deprecations,
parameter changes, and response-shape additions continuously, every startup on the list consumes
at least one of them, and a deprecated model identifier is a production outage rather than a
type error.

That combination — high frequency, broad consumption, real blast radius, and a machine-readable
spec reachable through the mechanism above — makes the AI providers the strongest second-adapter
candidate on pure findings volume. This does **not** overturn the committed M1 ordering, which
put MCP second on measured drift plus four independent arguments. It records that when M1's
measured drift is compared against something, the AI providers are the comparison, and the
`.stats.yml` mechanism means adopting both costs barely more than adopting one.

## Not viable, and why

Saying what to skip prevents the list from being re-litigated every time someone names a
popular API.

**Slack.** `slackapi/slack-api-specs` was last pushed in September 2021. A five-year-old spec
repository is a fossil, not a contract. Slack's API is documented for humans; there is nothing
to diff.

**SendGrid.** `sendgrid/sendgrid-oai` does not exist. Twilio owns SendGrid and the spec story
did not survive the acquisition.

**AWS, GCP, Azure.** Enormous, and described in vendor-specific model formats rather than
OpenAPI. They are SDK-shaped rather than spec-shaped, and each would be its own adapter
architecture. Gate 1 fails in substance even though a machine-readable description exists.

**GraphQL APIs — Linear, and Shopify's newer surface.** A GraphQL schema is machine-readable and
versioned, so gate 1 arguably passes, but oasdiff cannot read it. Supporting them means a second
diff engine (`graphql-inspector` or equivalent) behind the same `VendorAdapter` protocol. That is
a real and defensible extension — the protocol was designed for it — and it is a milestone of its
own, not a row in this table.

## The startup cohort, resolved

The seven candidates left open by the first pass were checked on 2026-07-27. None is
Stainless-generated, which usefully bounds the claim above: the `.stats.yml` trigger covers the
AI and infrastructure vendors, not this segment.

| Vendor | Finding | Verdict |
|---|---|---|
| **Clerk** | `clerk/openapi-specs` → `bapi/2021-02-05.yml`, 612 KB. **The filename is the pinned version.** | **Target.** Cleanest version-pair story on the list alongside Plaid. |
| **Vercel** | Speakeasy-generated. `.speakeasy/workflow.yaml` names `https://openapi.vercel.sh/` — vendor-hosted and live. | **Target**, and the proof the generator mechanism is not Stainless-specific. |
| **Algolia** | `algolia/api-clients-automation` → `specs/search/spec.yml`, 14 KB. Split per product. | **Target**, same shape as Twilio — many small specs, pinned per product. |
| **Supabase** | A spec exists at `apps/docs/spec/api_v1_openapi.json`, 494 KB — inside a docs app. | **Weak.** A docs artifact is not a contract, and Supabase's data API is PostgREST-generated per project, so there is no single stable spec to diff. Skip unless the management API alone is the target. |
| **Resend** | No `.stats.yml`; no spec repository found at the probed paths. | **Unresolved.** One timeboxed probe, then decide. |
| **WorkOS** | No `.stats.yml`; `workos/workos-openapi` does not exist. | **Unresolved.** As above. |
| **PostHog** | No `.stats.yml`; no spec at the probed paths. | **Unresolved.** As above. |

"Unresolved" means paths were probed and none hit — not that no spec exists. The distinction
matters, because absence of evidence at three guessed URLs is not evidence of absence.

## Splitting the work

Adapter targets accumulate faster than adapters get written, and a list that grows without a
throughput rule becomes a backlog nobody believes. Two rules keep it honest.

**One cohort per milestone, and at most two vendors of a genuinely new adapter *shape* per
milestone.** Vendors sharing a shape cost far less than the second one suggests — Twilio and
Algolia are the same problem twice, and adding both is barely more than adding one. Two vendors
whose shapes differ is a real doubling. Count shapes, not vendors.

| Cohort | Shape | Vendors | When |
|---|---|---|---|
| **A** | Generator-discovered — no per-vendor adapter at all | OpenAI, Anthropic, Cloudflare, Vercel, Lithic, Orb, Browserbase | M1.5 |
| **B** | Vendor-published, version in the filename | Plaid, Clerk | M2 |
| **C** | Vendor-published, split per product | Twilio, Algolia | M3 |
| **D** | Large monolithic spec — the scale test | GitHub, Cloudflare | M3+ |
| **E** | Unresolved, timeboxed probe | Resend, WorkOS, PostHog | Whenever a milestone has slack |
| **F** | Needs a second diff engine | Linear, newer Shopify | Own milestone, or never |

**Cohort A is not a batch of seven adapters.** It is one adapter that reads a generator
manifest, and every vendor in it is configuration. That is why it sits earliest despite being
the largest row: its cost does not scale with its length.

### The intake checklist

So each vendor is addressed the same way rather than however whoever picks it up feels that
day. Six questions, answered in the pull request that adds the adapter:

1. Where is the spec, and is it **vendor-hosted** or a mirror?
2. How is a version **pinned** — filename, git tag, release, or content hash?
3. Is there a **cheap change trigger** — a hash or an ETag — that avoids downloading the spec to
   learn nothing changed?
4. What is the **symbol-to-operation mapping**, and is it generated or hand-written?
5. **Measured** breaking changes per unit time, over at least three consecutive version pairs.
   Not estimated. This is the axis that orders the list and the one most often skipped.
6. What does the adapter do when the spec **disappears or fails to parse** — and is that path
   tested? Slack and SendGrid are on this list as the reason.

Question 5 is the one that will get skipped under time pressure. It is also the only one whose
absence makes the whole list guesswork, so a pull request that answers the other five and not
that one is not finished.

## Sequencing

| When | What |
|---|---|
| M0 | Stripe. Done. |
| M1 | MCP, on measured drift. Unchanged by this document. |
| M1.5 | **The `GeneratedSdkAdapter`** (cohort A). One adapter reading generator manifests — Stainless `.stats.yml` and Speakeasy `.speakeasy/workflow.yaml` — covering every vendor either generator serves. Highest coverage-per-unit-effort item on the roadmap; it should not wait for M3's adapter SDK. |
| M2 | Cohort B — Plaid and Clerk, both pinned by filename. OpenAI and Anthropic arrive free from cohort A; Sentry arrives anyway as a signal source. |
| M3 | Cohort C — Twilio and Algolia, the same product-split shape twice. These are the reference adapters the public SDK is documented with. |
| Later | Cloudflare as the scale test. A second diff engine for GraphQL, if demand justifies it. |

## The measurement this list still needs

Every row above is verified for spec availability and unverified for change frequency, which is
the axis that actually orders the list. The MCP drift measurement in
`2026-07-25-sync-mcp-drift-measurement.md` is the template: snapshot each vendor's spec on a
schedule, run oasdiff between consecutive versions, count breaking changes per unit time.

Until that runs, ordering here rests on judgement rather than data, and this section is the
record that it does. The `.stats.yml` hash makes the measurement cheap for every Stainless
vendor — poll a text file, and fetch the spec only when the hash moves.

## Verification

- **Every spec URL in the table is fetchable and parses as OpenAPI**, asserted in a test that is
  skipped without network access rather than failing.
- **The Stainless mechanism is proven on a real pair of commits**: find a commit where
  `openapi_spec_hash` changed, assert the adapter detects it without downloading the spec.
- **Cloudflare's 23 MB spec is a fixture in the performance test**, because a pipeline that only
  ever sees Stripe's 7.9 MB has not been shown to handle the market.
- **A vendor whose spec disappears fails loudly**, not silently. The Slack and SendGrid rows are
  the reason: an adapter pointed at a dead spec repository must abandon with a clear reason, not
  return zero changes and read as "nothing broke."
