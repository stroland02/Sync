"""The same map, read out of Stainless's TypeScript emission.

`symbols.py` covers `stainless-python` and its author established why that is a boundary rather
than an omission: the two Stainless flavours do not emit the same thing. Python writes the path
as a positional literal or `path_template(...)`; TypeScript writes it as a tagged template. A
rule claiming to cover both would be guessing about the one it had not seen.

This flavour matters more than the one already built. TypeScript is the mature indexer here, and
a customer calling Anthropic or OpenAI from TypeScript is the likelier case -- today their call
sites are matched, the client is found, and every symbol resolves to nothing.

Fixtures
--------
`sdk_sources/anthropic_typescript/` is verbatim source from
`anthropics/anthropic-sdk-typescript` at tag **sdk-v0.115.0**, fetched through the GitHub contents
API on 2026-07-29. Seven files under `src/`: `client.ts`, `resources/models.ts`,
`resources/completions.ts`, `resources/messages/messages.ts`, `resources/messages/batches.ts`,
`resources/beta/beta.ts` and `resources/beta/models.ts`.

The last two are there for one reason. `resources/models.ts` and `resources/beta/models.ts` both
export a class named `Models`, and `beta.ts` mounts the second while `client.ts` mounts the first.
A rule keying classes by bare name conflates them and files beta routes under the top-level mount;
`test_two_classes_sharing_a_name_are_told_apart_by_their_module` is what holds that apart.

The specification fixture is **reused** from the Python flavour, and the reuse is evidenced rather
than assumed: this SDK's own `.stats.yml` publishes `openapi_spec_hash: d2deb0fef6a15bf53cc6c53f07973a54`,
which is byte-identical to the Python SDK's, and fetching both specifications and comparing their
operation sets gave the same 131 operations. Two flavours generated from one specification.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sync.signals.generated.symbols import read_spec_operations
from sync.signals.generated.symbols_typescript import (
    GENERATOR,
    UnrecognisedSdkShape,
    extract_symbols,
    report_extraction,
)

FIXTURES = Path(__file__).parent / "fixtures" / "sdk_sources"
SDK = FIXTURES / "anthropic_typescript"
SPEC_OPERATIONS = FIXTURES / "anthropic_spec_operations.json"


def _extracted() -> dict[str, object]:
    return {operation.symbol: operation for operation in extract_symbols(SDK)}


# --- what the source says --------------------------------------------------------------


def test_the_generator_and_language_supported_are_named():
    """A generator alone does not name an extraction rule. The unit is generator times language,
    which is the finding the Python flavour's author left on the record."""
    assert GENERATOR == "stainless-typescript"


def test_a_plain_string_path_is_read_from_the_call_that_sends_it():
    """`this._client.getAPIList('/v1/models', Page<ModelInfo>, ...)`. The verb is the client
    method and the path is the string beside it -- neither is derived from the resource name,
    which is what would make this generation rather than extraction."""
    models = _extracted()["models.list"]

    assert models.http_method == "GET"
    assert models.path == "/v1/models"


def test_a_tagged_template_path_is_read_from_its_literal_parts():
    """`this._client.get(path`/v1/models/${modelID}`, options)` -- the shape that made this a
    second module rather than a branch in the first.

    The route is the template's literal parts with each interpolation standing where it stood.
    The interpolated expression is a local parameter name and says nothing about the route, so
    it is not read; what is recorded is that a segment is a parameter.
    """
    retrieve = _extracted()["models.retrieve"]

    assert retrieve.http_method == "GET"
    assert retrieve.path == "/v1/models/{modelID}"


def test_a_nested_resource_carries_its_whole_chain():
    """`client.messages.batches.create`, read from the property initialisers that mount it."""
    extracted = _extracted()

    assert extracted["messages.batches.create"].path == "/v1/messages/batches"
    assert extracted["messages.batches.create"].http_method == "POST"
    assert extracted["messages.batches.delete"].http_method == "DELETE"


def test_two_classes_sharing_a_name_are_told_apart_by_their_module():
    """`resources/models.ts` and `resources/beta/models.ts` both export `Models`.

    Python's flavour keys classes by bare name and gets away with it on the sample it reads.
    TypeScript cannot: the root mounts `API.Models` and `Beta` mounts `ModelsAPI.Models`, and
    conflating them files beta's routes under the top-level mount -- a wrong answer that
    resolves, which is the failure mode this whole approach exists to avoid. The import alias
    is what disambiguates, so a mount is resolved through the importing file's own alias map.
    """
    extracted = _extracted()

    assert extracted["models.retrieve"].path == "/v1/models/{modelID}"
    assert extracted["beta.models.retrieve"].path == "/v1/models/{modelID}?beta=true"
    assert extracted["models.retrieve"].path != extracted["beta.models.retrieve"].path


def test_the_deprecated_and_type_only_declarations_do_not_become_operations():
    """A resource file is mostly interfaces and type aliases. Only a method that actually calls
    the client is an operation, and counting anything else would inflate coverage against a
    denominator that counts each operation once."""
    symbols = set(_extracted())

    assert symbols
    assert not [symbol for symbol in symbols if symbol.endswith(".constructor")]
    assert all(symbol.count(".") >= 1 for symbol in symbols)


# --- coverage against a named denominator ------------------------------------------------


def test_coverage_is_reported_against_the_specifications_operation_count():
    """Both numbers, because a ratio hides which one moved.

    The denominator is the specification this SDK's own manifest names -- 131 published
    operations, 121 distinct routes once the `?beta=true` marker is dropped for comparison.
    The numerator is what the committed fixture holds: seven files out of the SDK's full set,
    so this is a floor rather than the SDK's coverage. The un-truncated figure, measured against
    a full checkout of the same tag, is in the task report.
    """
    published = json.loads(SPEC_OPERATIONS.read_text(encoding="utf-8"))
    report = report_extraction(SDK, read_spec_operations(SPEC_OPERATIONS))

    assert len(published) == 131
    assert report.spec_operation_count == 121
    assert report.extracted_count > 0
    assert 0 < report.covered_count <= report.spec_operation_count
    assert report.spec_operation_count > report.covered_count


def test_the_rendered_line_names_the_generator_and_carries_the_denominator():
    """"Extracted 180 operations" says nothing. The Stripe map's 105 of 414 means something only
    because the second number travels with it."""
    rendered = report_extraction(SDK, read_spec_operations(SPEC_OPERATIONS)).render()

    assert GENERATOR in rendered
    assert "of 121 specification operations" in rendered


# --- the cross-check ----------------------------------------------------------------------


def test_an_operation_the_specification_does_not_declare_is_reported(tmp_path):
    """A deliberately corrupted source is caught by the cross-check rather than by a reviewer.

    The extractor still reads the altered route -- it is doing its job, the source really does
    say that -- and the cross-check is what refuses it. Reported rather than dropped, because a
    silently discarded operation is indistinguishable from a vendor that genuinely does not
    offer it.
    """
    corrupted = _corrupt(tmp_path, "resources/models.ts", "'/v1/models'", "'/v1/model_registry'")

    report = report_extraction(corrupted, read_spec_operations(SPEC_OPERATIONS))

    assert [operation.path for operation in report.unknown_to_spec] == ["/v1/model_registry"]


def test_the_cross_check_is_not_vacuous(tmp_path):
    """A check that never fires is decoration; one that always fires is worse. The uncorrupted
    fixture must report nothing, and a second, different corruption must still fire."""
    clean = report_extraction(SDK, read_spec_operations(SPEC_OPERATIONS))
    assert clean.unknown_to_spec == ()

    corrupted = _corrupt(
        tmp_path, "resources/messages/batches.ts", "'/v1/messages/batches'", "'/v1/batches'"
    )

    assert report_extraction(corrupted, read_spec_operations(SPEC_OPERATIONS)).unknown_to_spec != ()


def test_a_parameter_named_differently_from_the_specification_is_not_a_disagreement():
    """The SDK writes `${modelID}` and the specification writes `{model_id}`. They are the same
    route spelled by two generators from one document.

    A cross-check that fires on that trains a reader to ignore it, which is worse than no
    cross-check -- so a parameter segment is normalised to a placeholder on both sides before
    comparing, and the extracted path keeps the SDK's own spelling.
    """
    report = report_extraction(SDK, read_spec_operations(SPEC_OPERATIONS))
    retrieve = {operation.symbol: operation for operation in report.operations}["models.retrieve"]

    assert retrieve.path == "/v1/models/{modelID}"
    assert retrieve not in report.unknown_to_spec


# --- both raise sites, one test each -------------------------------------------------------


def test_source_with_no_resource_class_fails_rather_than_returning_a_partial_map(tmp_path):
    """First raise site: nothing derives `APIResource`, so there is no resource to read.

    The Python flavour's equivalent is "no class derives the client base". The points differ
    because the emissions differ -- TypeScript's client extends a generated base whose name is
    the vendor's, so the resource base is the fixed anchor and the client is found by what it
    mounts.
    """
    (tmp_path / "thing.ts").write_text("export class Thing {}\n", encoding="utf-8")

    with pytest.raises(UnrecognisedSdkShape) as raised:
        extract_symbols(tmp_path)

    assert GENERATOR in str(raised.value)
    assert "APIResource" in str(raised.value)


def test_resources_with_nothing_mounting_them_fails_too(tmp_path):
    """Second raise site: resources exist and no class mounts any of them, so nothing is
    reachable and every symbol would be unrooted.

    "Half the shape is not the shape" -- a rule that returned the resources it found would
    produce an empty map, and an empty map reported as success is the partial-map failure this
    whole approach exists to avoid.
    """
    (tmp_path / "models.ts").write_text(
        "export class Models extends APIResource {\n"
        "  list() {\n"
        "    return this._client.get('/v1/models', {});\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )

    with pytest.raises(UnrecognisedSdkShape) as raised:
        extract_symbols(tmp_path)

    assert GENERATOR in str(raised.value)


# --- the Python flavour is unaffected -------------------------------------------------------


def test_a_typescript_sdk_handed_to_the_python_extractor_still_fails_loudly():
    """The boundary, asserted from the other side. Neither rule may half-succeed on the other's
    input -- that is the guessing the split exists to prevent."""
    from sync.signals.generated import symbols as python_flavour

    with pytest.raises(python_flavour.UnrecognisedSdkShape):
        python_flavour.extract_symbols(SDK)


def test_the_python_flavour_still_reads_its_own_sdk():
    """Its own fixture, through its own rule, unchanged by this module existing."""
    from sync.signals.generated import symbols as python_flavour

    report = python_flavour.report_extraction(
        FIXTURES / "anthropic_python", read_spec_operations(SPEC_OPERATIONS)
    )

    assert report.extracted_count == 11
    assert report.covered_count == 10
    assert report.unknown_to_spec == ()


# --- resolution through the adapter -----------------------------------------------------------


def test_the_adapter_resolves_a_typescript_symbol():
    from sync.signals.generated.adapter import GeneratedSpecAdapter

    adapter = GeneratedSpecAdapter(
        vendor_id="anthropic", sources={}, fetch=_never_fetch, cache_dir=FIXTURES,
        sdk_source=SDK, sdk_source_generator=GENERATOR,
    )
    reference = adapter.operation_for_symbol("anthropic.models.list", language="typescript")

    assert reference is not None
    assert reference.http_method == "get"
    assert reference.path == "/v1/models"


def test_a_symbol_the_sdk_does_not_contain_resolves_to_nothing():
    """A wrong lookup stays a miss rather than becoming a wrong hit."""
    from sync.signals.generated.adapter import GeneratedSpecAdapter

    adapter = GeneratedSpecAdapter(
        vendor_id="anthropic", sources={}, fetch=_never_fetch, cache_dir=FIXTURES,
        sdk_source=SDK, sdk_source_generator=GENERATOR,
    )

    assert adapter.operation_for_symbol("anthropic.charges.create", language="typescript") is None
    assert adapter.operation_for_symbol("anthropic.models", language="typescript") is None


def test_the_adapter_still_defaults_to_the_python_flavour():
    """The existing caller passes no generator and must keep the behaviour it had."""
    from sync.signals.generated.adapter import GeneratedSpecAdapter

    adapter = GeneratedSpecAdapter(
        vendor_id="anthropic", sources={}, fetch=_never_fetch, cache_dir=FIXTURES,
        sdk_source=FIXTURES / "anthropic_python",
    )

    reference = adapter.operation_for_symbol("anthropic.models.list", language="python")
    assert reference is not None and reference.path == "/v1/models"


def _never_fetch(url: str) -> str:
    raise AssertionError("symbol extraction must not reach a network")


def _corrupt(tmp_path: Path, relative: str, old: str, new: str) -> Path:
    import shutil

    destination = tmp_path / "sdk"
    shutil.copytree(SDK, destination)
    target = destination / relative
    text = target.read_text(encoding="utf-8")
    assert old in text, f"{relative} does not contain {old}, so this corruption proves nothing"
    target.write_text(text.replace(old, new), encoding="utf-8")
    return destination
