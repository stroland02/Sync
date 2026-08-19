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

## `vercel_typescript/`

Verbatim source from `vercel/sdk` at tag **v1.28.12**, commit
`142fa1bd976e91e47468cee500342efe59162bde`, cloned on 2026-07-29. Twenty files, each at its path
under `src/`:

| file | bytes |
|---|---|
| `core.ts` | 460 |
| `sdk/sdk.ts` | 13,273 |
| `sdk/aliases.ts` | 4,176 |
| `sdk/user.ts` | 2,792 |
| `sdk/webhooks.ts` | 2,160 |
| `funcs/aliases*.ts` (6 files) | 32,048 |
| `funcs/user*.ts` (4 files) | 20,148 |
| `funcs/webhooks*.ts` (4 files) | 20,010 |
| `funcs/getStorageStoresById.ts` | 4,861 |

Nothing is edited. This is the **Speakeasy** generator rather than Stainless, and the first
fixture here that is not Stainless.

Three of these files are here for a reason beyond being reachable.

`sdk/sdk.ts` is committed **whole**, with all 41 of its mounts, while only three of the resource
classes it names are. A mount naming a class this checkout does not contain must simply not be an
edge — not raise, and not resolve to something else. Truncating `sdk.ts` would have removed the
only case that holds that.

`core.ts` is 460 bytes and declares `export class VercelCore extends ClientSDK {}` and nothing
else. Speakeasy gives the client, every resource **and** this class the same base, so the base
cannot pick the root; the root is the class that mounts another and is not itself mounted, and
`VercelCore` is what proves the rule is that rather than the base class.

`funcs/getStorageStoresById.ts` backs an operation the client declares on itself rather than on a
mounted resource — `vercel.getStorageStoresById(...)`, chain length zero. The client declares 11
such operations and a rule walking only mounts would drop all of them.

As with both Stainless trees, coverage measured against this fixture is a floor rather than the
SDK's real figure; the un-truncated number is in the task report.

## `mistral_python/`

**Handwritten, not vendored** — the one tree here that is. Seven files in the shape of
Speakeasy's Python emission, read from `mistralai/client-python` (`src/mistralai/client/`,
default branch) on 2026-08-18: the `_sub_sdk_map` lazy root with quoted forward-reference
mounts, the `_init_sdks` nested mount with a direct class-name annotation, the verb and path as
keyword arguments of `self._build_request(...)` / `_build_request_async(...)`, the `#stream`
fragment marker, and the `models` attribute naming class `Models` in `models_.py`. Every
construct was observed in that repository; none of its code is copied.

`ocr.py` is deliberately not staged while `sdk.py` mounts it, so a mount naming a class the
checkout does not declare has a case holding it — the same role `sdk/sdk.ts` plays for the
TypeScript flavour.

## `mistral_python_spec_operations.json`

Handwritten to match the tree above rather than fetched: the seven routes the fixture states
plus `POST /v1/ocr`, which no staged symbol reaches. Because both sides are handwritten, nothing
here evidences Mistral's real API — the pair exercises the rule, and a measurement against a
full checkout belongs to whoever stages one.

## `vercel_spec_operations.json`

The operation set of the specification `vercel/sdk`'s own manifest names. The URL is the single
`sources.vercel-OAS.inputs[0].location` in `vercel_typescript.workflow.yaml` —
`https://openapi.vercel.sh/`, the vendor's own host rather than a generator mirror. Fetched on
2026-07-29 and reduced to method and path, because the document is 9.8 MB and nothing here reads
anything else from it.

It holds **359** operations against the SDK's 349 request modules. Unlike the Anthropic pair there
is no published endpoint count to check that against — a Speakeasy `workflow.yaml` declares its
inputs and not its size — so what evidences the denominator here is the extraction itself: all 352
symbols the full checkout yields resolve to routes this document declares, and none is unknown to
it.

## `vercel_typescript.workflow.yaml`

`vercel/sdk`'s own `.speakeasy/workflow.yaml` at the same tag, committed so the spec URL above is
read from the SDK's manifest rather than asserted by this README.
`test_the_specification_fixture_is_the_one_this_sdks_manifest_names` holds it, so moving the
fixture to a tag generated from a different document goes red before a coverage number starts
being measured against the wrong denominator.

It reports one overlay, `overlay-title.yaml`. `GeneratedSpecAdapter` diffs a spec with overlays
anyway and says why; for this cross-check what matters is that a title overlay changes no route,
which is consistent with the 352 extracted routes all being declared.
