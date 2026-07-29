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

## `anthropic_spec_operations.json`

The operation set of the specification that SDK's own manifest names. The URL is
`openapi_spec_url` in `tests/fixtures/manifests/anthropic.stats.yml`; the document was fetched on
2026-07-29 and reduced to method and path, because the specification itself is 1.8 MB and nothing
here reads anything else from it.

It holds **131** operations, which is exactly the `configured_endpoints: 131` that manifest
declares -- two independently published artifacts agreeing on the denominator rather than a
number asserted by a test. 120 of the 131 carry a `?beta=true` marker, leaving **121** distinct
routes once the marker is dropped for comparison.
