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

## The malformed fixtures are malformed on purpose

Everything below is deliberately wrong, and each one is wrong in a different way, because the
module answers them differently. Do not repair them.

| fixture | what is wrong | what it pins |
|---|---|---|
| `broken_manifest/` | truncated JSON | a manifest that will not parse is a reported fault |
| `array_manifest/` | valid JSON, top-level array | parses cleanly and declares nothing, which is not the same as depending on nothing |
| `npm_table_not_an_object/` | `"dependencies"` is an array | the table under the top level is checked too; this used to raise `TypeError` out of the whole report |
| `python_half_broken/` | unclosed `[project` header, valid `requirements.txt` beside it | one unreadable manifest does not take the other down with it |
| `python_mixed_array/` | valid TOML, a number and a boolean in the requirement array | the file parses, so only the entry is dropped |
| `python_both/` | nothing | both Python manifests are read, because reading one reports half the ecosystem as declaring nothing |
| `sdk-repositories-partial.yaml`, `registry-apis-partial.yaml` | an entry missing a field | evidence written down and silently not read is the failure this report exists to remove |
| `sdk-repositories-mapping.yaml`, `registry-apis-mapping.yaml` | a mapping where a list belongs | the container is named as the fault, rather than blaming the entries in it |

**No fixture here is anything other than UTF-8, and none should become one.** The three manifests
whose bytes are deliberately not UTF-8 are constructed in `tests/test_dependency_intake.py` and
written with `write_bytes`. A file in the tree whose bytes are illegal is repaired silently by
any editor, formatter or agent that round-trips it as text, and the test would then pass against
a valid file while appearing to cover the decode handler.
