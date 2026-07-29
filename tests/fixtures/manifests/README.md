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
