# Dependency-intake fixtures

`orb.stats.yml` was captured verbatim on 2026-07-29 from `orbcorp/orb-node`, by the method
`tests/fixtures/manifests/README.md` records: fetch the path and read what came back. It carries
nothing but `configured_endpoints`, which is the same shape Cloudflare's has -- and Cloudflare is
a vendor `generated-vendors.yaml` configures on exactly that evidence, which is what makes the
shape sufficient rather than merely present.

Four repositories were probed on the same day for the manifests the generated tier reads:

| package | repository | manifest | result |
|---|---|---|---|
| `orb-billing` | `orbcorp/orb-node` | `.stats.yml` | present |
| `@vercel/sdk` | `vercel/sdk` | `.speakeasy/workflow.yaml` | present, and configured as vendor `vercel` |
| `plaid` | `plaid/plaid-node` | `.stats.yml` | **absent** |
| `openai` | `openai/openai-node` | `.stats.yml` | present, and *not* the repository vendor `openai` configures, which is `openai/openai-python` |

`plaid` is in the manifest because the absence is what a fixture has to carry. A dependency that
looks like an SDK and has no generator manifest is the case where a hopeful "watchable" would be
a promise the next run breaks.
