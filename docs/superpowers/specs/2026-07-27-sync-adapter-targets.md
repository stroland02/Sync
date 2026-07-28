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

This is the part that matters more than any individual row below, and it was found by reading
`.stats.yml` in `anthropics/anthropic-sdk-python`.

Stainless-generated SDKs commit a file that names the spec they were generated from:

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
A `StainlessAdapter` that reads `.stats.yml`, follows `openapi_spec_url`, and hands the result
to the existing oasdiff pipeline is **one adapter that covers every Stainless customer**, not one
per vendor. Anthropic acquired Stainless in May 2026, and OpenAI and Google both depended on it,
so the covered surface is large and growing.

Two caveats recorded rather than smoothed over. The hash is absent from several `.stats.yml`
files (Cloudflare, Orb), so the cheap trigger is not universal and the adapter must fall back to
fetching. And `openapi_spec_url` points at Stainless-hosted storage rather than the vendor, which
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

**Supabase, Clerk, WorkOS, Resend, PostHog, Vercel, Algolia.** All actively maintained, all
plausibly consumed by the startup segment. Every one was checked only for repository liveness,
not for a published spec. They are candidates, not targets, and are recorded here so the next
pass starts from a list rather than from memory.

## Sequencing

| When | What |
|---|---|
| M0 | Stripe. Done. |
| M1 | MCP, on measured drift. Unchanged by this document. |
| M1.5 | **The `StainlessAdapter`.** One adapter, many vendors. This is the highest coverage-per-unit-effort item on the entire roadmap and it should not wait for M3's adapter SDK. |
| M2 | OpenAI and Anthropic, which the Stainless adapter largely delivers. Sentry arrives anyway as a signal source. |
| M3 | GitHub and Twilio, hand-written against vendor-published specs, as the reference adapters the public SDK is documented with. |
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
