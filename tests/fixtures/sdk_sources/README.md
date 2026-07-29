# Committed SDK source

The regression fixture the substrate spec asks for: *"an extraction rule is a per-generator
artifact that can rot when a generator changes its emitted shape -- so a rule needs its own
regression fixture pinned to a real SDK version."*

## `anthropic_python/`

Verbatim source from `anthropics/anthropic-sdk-python` at tag **v0.120.2**, fetched through the
GitHub contents API on 2026-07-29 with `Accept: application/vnd.github.raw`. Five files, each at
its path under `src/anthropic/`:

| file | bytes |
|---|---|
| `_client.py` | 45,747 |
| `resources/models.py` | 12,483 |
| `resources/completions.py` | 36,220 |
| `resources/messages/messages.py` | 141,248 |
| `resources/messages/batches.py` | 30,376 |

Nothing is edited. The `beta/` tree is **not** committed: it carries 113 of the SDK's operations
and would roughly triple the fixture. The consequence is that coverage measured against this
fixture is a floor rather than the SDK's real figure, which is why the task report carries the
un-truncated number measured against a full checkout of the same tag.

## `anthropic_typescript/`

Verbatim source from `anthropics/anthropic-sdk-typescript` at tag **sdk-v0.115.0**, commit
`3b45cd3b69c956ac63384fdb09ce1d8109f3fa80`. Eight files, each at its path under `src/`:

| file | bytes |
|---|---|
| `client.ts` | 75,291 |
| `resources/index.ts` | 6,654 |
| `resources/models.ts` | 6,439 |
| `resources/completions.ts` | 7,215 |
| `resources/messages/messages.ts` | 106,441 |
| `resources/messages/batches.ts` | 13,119 |
| `resources/beta/beta.ts` | 63,247 |
| `resources/beta/models.ts` | 7,221 |

Nothing is edited. As with the Python tree, most of `beta/` is left out and coverage measured
against this fixture is a floor rather than the SDK's real figure; the un-truncated number is in
the task report.

Three of these files are here for a reason beyond being reachable.

`resources/models.ts` and `resources/beta/models.ts` both export a class named `Models`. The root
mounts the first and `Beta` mounts the second, so a rule keying classes by bare name files beta's
routes under the top-level mount — a wrong answer that resolves.

`resources/index.ts` declares no class at all. Every one of the client's own mounts is written
`new API.Completions(this)`, where `API` is that barrel, so without it nothing is rooted and the
extractor raises. It is the file that makes the fixture a working SDK rather than a set of
orphans.

## `anthropic_spec_operations.json`

The operation set of the specification that SDK's own manifest names. The URL is
`openapi_spec_url` in `tests/fixtures/manifests/anthropic.stats.yml`; the document was fetched on
2026-07-29 and reduced to method and path, because the specification itself is 1.8 MB and nothing
here reads anything else from it.

It holds **131** operations, which is exactly the `configured_endpoints: 131` that manifest
declares -- two independently published artifacts agreeing on the denominator rather than a
number asserted by a test. 120 of the 131 carry a `?beta=true` marker, leaving **121** distinct
routes once the marker is dropped for comparison.

One file serves both SDKs. `anthropic_typescript.stats.yml` is the TypeScript SDK's own manifest
at `sdk-v0.115.0`, and it publishes the same `openapi_spec_hash` and the same
`configured_endpoints` as the Python SDK's — the two SDKs saying they came from one specification,
rather than this README asserting it. `test_both_flavours_were_generated_from_the_same_specification`
holds it, so bumping either SDK to a tag generated from a different document goes red before a
coverage number starts being measured against the wrong denominator.
