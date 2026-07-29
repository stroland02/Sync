# Committed generator manifests

Captured verbatim on 2026-07-28 from the SDK repositories `generated-vendors.yaml` configures,
by the same method `docs/superpowers/specs/2026-07-27-sync-adapter-targets.md` used to verify a
target: fetch the path and read what came back.

| fixture | repository | path |
|---|---|---|
| `anthropic.stats.yml` | `anthropics/anthropic-sdk-python` | `.stats.yml` |
| `openai.stats.yml` | `openai/openai-python` | `.stats.yml` |
| `cloudflare.stats.yml` | `cloudflare/cloudflare-python` | `.stats.yml` |
| `vercel.workflow.yaml` | `vercel/sdk` | `.speakeasy/workflow.yaml` |

Real rather than hand-written, because between them they are the four shapes the parser has to
tell apart and a hand-written set would only ever contain the shapes somebody thought of:

- **Anthropic and OpenAI** publish a URL *and* a hash, which is the cheap change trigger the
  whole approach rests on.
- **Cloudflare** publishes an endpoint count and nothing else. `SpecSource.is_fetchable` is
  False, and the adapter reports that rather than raising -- the vendor still needs a
  hand-written adapter and must not abort a scan across the others.
- **Vercel** is the other generator entirely, and its input is `https://openapi.vercel.sh/` --
  the vendor's own host rather than a generator mirror -- with an overlay applied.

These are snapshots and the live files move. Nothing here is compared against the network, so a
stale copy stays a valid fixture: what they pin is the *shape* each convention publishes.

## The versioned Speakeasy pair

`acme-versioned-v1.workflow.yaml` and `acme-versioned-v2.workflow.yaml` are the one pair here
that is **written rather than captured**, and the distinction matters enough to state.

They exist for M3-W85. `vercel.workflow.yaml` names a live endpoint and is byte-identical at
every commit, so both ends of a version pair resolve to one document -- and a fix that reported
every Speakeasy vendor as unobservable would pass every test the captured manifests can express.
These two supply the other side: a Speakeasy manifest whose `location` names a different document
per version, which must still be diffed.

**The shape is evidence-backed even though the bytes are not a capture.** Speakeasy's `location`
carries a versioned reference in the wild -- read 2026-07-29, `mistralai/client-ts` names
`registry.speakeasyapi.dev/mistral-dev/mistral-dev/mistral-openapi-azure:v2`, a tagged revision --
while `vercel/sdk`, `dubinc/dub-node` and `polarsource/polar-js` all name a live endpoint. So
whether a pair is observable is a property of the location the manifest names and not of the
generator that wrote it, which is the claim these two fixtures hold in place.

They are written rather than captured because no repository was found publishing a *versioned
absolute URL* in that field; the real versioned form is a registry reference, which
`_is_absolute_url` rejects and nothing downstream can fetch today.
`2026-07-29-vercel-observability.md` records that gap.
