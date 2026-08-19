"""The same map, read out of Speakeasy's **Python** emission.

The fourth rule, and the second for this generator. `generated-vendors.yaml` configures `mistral`
against `mistralai/client-python` with a Python binding, so today Mistral is a vendor whose
specification is diffable, whose package the indexer matches -- and every symbol resolves to
nothing for want of this module. `test_configured_vendors.py` is the gate that reported it.

What Speakeasy writes down in Python, and where it differs from both neighbours
-------------------------------------------------------------------------------
The route is back in the file that declares the method. Speakeasy's TypeScript emission splits an
operation across two modules joined by an import; its Python emission states both halves as
keyword arguments of one call inside the method body:

    req = self._build_request(
        method="POST",
        path="/v1/embeddings",
        ...
    )

The async variant is `create_async` calling `self._build_request_async` with the same pair. So no
module boundary is crossed to read one operation -- the Stainless-Python situation -- but the
class arrangement is Speakeasy's: the client (`Mistral`), every resource and every nested
sub-SDK extend `BaseSDK` alike, so the base identifies a candidate and cannot pick the root. The
root is the class that mounts another candidate and is not itself mounted, exactly as in
`symbols_speakeasy.py`.

A mount is a bare class-body annotation. The root writes forward references and loads lazily
(`chat: "Chat"` beside a `_sub_sdk_map`); a nested sub-SDK writes the class name directly and
assigns in `_init_sdks` (`conversations: Conversations`). The annotation is the one statement
both shapes share, and the attribute name -- what a customer writes -- is the annotation's
target, not the class or the file: the `models` attribute names class `Models` declared in
`models_.py`.

Fixtures
--------
`sdk_sources/mistral_python/` is **handwritten**, not vendored: a minimal emission in the shape
read from `mistralai/client-python` (`src/mistralai/client/`, default branch, 2026-08-18 --
`sdk.py`, `embeddings.py`, `models_.py`, `chat.py`, `beta.py`, `conversations.py`). Every
construct it states -- the `_sub_sdk_map` lazy root, the `_init_sdks` nested mount, the
`#stream` marker, the `models`/`Models`/`models_.py` naming split -- was observed there; none of
their code is copied. Seven mounts are declared and `ocr.py` is deliberately not staged, so a
mount naming a class this checkout does not declare has a case holding it.

`mistral_python_spec_operations.json` is handwritten to match: the seven routes the fixture
states plus `POST /v1/ocr`, which no staged symbol reaches -- the unreached channel's case.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sync.signals.generated.symbols import read_spec_operations
from sync.signals.generated.symbols_speakeasy_python import (
    GENERATOR,
    UnrecognisedSdkShape,
    extract_symbols,
    report_extraction,
)

FIXTURES = Path(__file__).parent / "fixtures" / "sdk_sources"
SDK = FIXTURES / "mistral_python"
SPEC_OPERATIONS = FIXTURES / "mistral_python_spec_operations.json"


def _by_symbol() -> dict[str, tuple[str, str]]:
    return {
        operation.symbol: (operation.http_method, operation.path)
        for operation in extract_symbols(SDK)[0]
    }


def test_the_generator_and_language_supported_are_named():
    """A rule covers a generator times a language, and says which."""
    assert GENERATOR == "speakeasy-python"


def test_the_route_is_read_from_the_builder_call_in_the_method_itself():
    """The half of the TypeScript flavour's difficulty this emission does not have.

    `Embeddings.create` states its own verb and path, as keyword arguments of the one
    `self._build_request(...)` call in its body -- no delegation, no second module. What stays
    Speakeasy's is everything around it: the class arrangement, and the root found by mounting
    rather than by base class.
    """
    assert _by_symbol()["embeddings.create"] == ("POST", "/v1/embeddings")


def test_the_verb_comes_from_the_builder_and_not_from_the_method_name():
    """`retrieve` and `delete` address one route under two verbs, so no rule reading either name
    can produce both -- the verb is the `method=` keyword of the builder call, where it is
    written."""
    extracted = _by_symbol()

    assert extracted["models.retrieve"] == ("GET", "/v1/models/{model_id}")
    assert extracted["models.delete"] == ("DELETE", "/v1/models/{model_id}")
    assert extracted["models.list"] == ("GET", "/v1/models")


def test_the_async_variant_is_its_own_symbol():
    """The decision Stainless never had to make, recorded here because it is reversible.

    Stainless emits its async client as a separate class (`AsyncAnthropic`) whose chains repeat
    the sync ones, so excluding those classes loses no symbol a customer writes. Speakeasy
    Python emits the async variant as a sibling method on the same class -- `create_async` is a
    different chain, and a customer's `mistral.embeddings.create_async(...)` is a real call site.
    Excluding it would resolve that call site to nothing, which is the false negative this whole
    approach exists to avoid. Two symbols on one route cannot inflate coverage either: coverage
    is counted in distinct comparable routes on the specification's side.
    """
    extracted = _by_symbol()

    assert extracted["embeddings.create_async"] == ("POST", "/v1/embeddings")
    assert extracted["embeddings.create_async"] == extracted["embeddings.create"]
    assert extracted["models.delete_async"] == ("DELETE", "/v1/models/{model_id}")


def test_a_nested_sub_sdk_carries_its_whole_chain():
    """`mistral.beta.conversations.start` -- the chain is the mount annotations walked from the
    root, and the nested mount is written as a direct class name where the root writes a quoted
    forward reference. Both are one shape to this rule: a bare class-body annotation."""
    extracted = _by_symbol()

    assert extracted["beta.conversations.start"] == ("POST", "/v1/conversations")
    assert extracted["beta.conversations.append"] == (
        "POST", "/v1/conversations/{conversation_id}"
    )


def test_the_mount_name_is_the_attribute_and_not_the_class_or_the_file():
    """The `models` attribute names class `Models`, declared in `models_.py` -- three different
    spellings of one resource, and the symbol carries the one a customer writes."""
    extracted = _by_symbol()

    assert "models.list" in extracted
    assert not any(symbol.startswith("Models") for symbol in extracted)
    assert not any(symbol.startswith("models_") for symbol in extracted)


def test_a_mount_naming_a_class_this_checkout_does_not_hold_is_not_an_edge():
    """`sdk.py` mounts five sub-SDKs and `ocr.py` is deliberately not staged.

    The other four must resolve, `ocr` must produce no symbols and no error, and the loss must be
    recorded rather than silent -- a smaller map with no explanation is indistinguishable from a
    smaller SDK.
    """
    operations, unreadable = extract_symbols(SDK)
    mounted = {operation.symbol.split(".")[0] for operation in operations}

    assert mounted == {"chat", "embeddings", "models", "beta"}
    assert len(unreadable) == 1
    assert "Ocr" in unreadable[0] and "does not declare" in unreadable[0]


def test_two_operations_sharing_a_route_under_different_verbs_stay_distinct():
    extracted = _by_symbol()

    assert extracted["models.retrieve"][1] == extracted["models.delete"][1]
    assert extracted["models.retrieve"][0] == "GET"
    assert extracted["models.delete"][0] == "DELETE"


def test_the_stream_marker_stays_in_the_path_and_is_dropped_by_the_comparison():
    """Speakeasy distinguishes the streaming operation over one route with a `#stream` fragment
    -- `/v1/chat/completions#stream`, stated in `chat.py` of the emission this rule reads. A
    fragment never reaches the wire, and the specification declares the route without it, so a
    comparison keeping it would report every streaming operation as unknown to the spec -- a
    cross-check firing on a difference in how two artifacts spell the same thing, which trains a
    reader to ignore it.

    Only the comparison is normalised, the same split `_route` makes for the query marker: the
    extracted path keeps the SDK's own spelling.
    """
    extracted = _by_symbol()

    assert extracted["chat.stream"] == ("POST", "/v1/chat/completions#stream")
    assert extracted["chat.complete"] == ("POST", "/v1/chat/completions")

    report = report_extraction(SDK, read_spec_operations(SPEC_OPERATIONS))
    assert report.unknown_to_spec == ()


def test_the_sixteen_stated_operations_are_all_reached():
    """The denominator this fixture can be held to: four resources' methods, sync and async."""
    assert len(_by_symbol()) == 16


def test_coverage_is_reported_against_the_specifications_operation_count():
    """Sixteen symbols reach seven of the eight declared routes: `chat.complete` and
    `chat.stream` share one, every operation has its async twin, and `POST /v1/ocr` is declared
    by the specification and reached by nothing because `ocr.py` is not staged -- the unreached
    channel carrying exactly the loss the unreadable channel explains."""
    spec = read_spec_operations(SPEC_OPERATIONS)
    report = report_extraction(SDK, spec)

    assert report.extracted_count == 16
    assert report.declared_operation_count == 8
    assert report.comparable_key_count == 8
    assert report.covered_count == 7
    assert report.unreached == (("POST", "/v1/ocr"),)
    assert 0 < report.coverage_ratio < 1


def test_the_rendered_line_names_this_rule_and_carries_the_denominator():
    report = report_extraction(SDK, read_spec_operations(SPEC_OPERATIONS))
    line = report.render()

    assert line.startswith(f"{GENERATOR}:")
    assert "stainless" not in line
    assert f"of {report.comparable_key_count} comparable routes" in line
    assert f"declares {report.declared_operation_count} operations" in line


def test_the_cross_check_is_not_vacuous(tmp_path):
    """Prove the check can fire, by corrupting the source rather than the specification."""
    corrupted = tmp_path / "sdk"
    _copy_tree(SDK, corrupted)
    target = corrupted / "embeddings.py"
    target.write_text(
        target.read_text(encoding="utf-8").replace(
            '"/v1/embeddings"', '"/v1/embedding_service"'
        ),
        encoding="utf-8",
    )

    report = report_extraction(corrupted, read_spec_operations(SPEC_OPERATIONS))

    assert sorted(operation.symbol for operation in report.unknown_to_spec) == [
        "embeddings.create", "embeddings.create_async"
    ]
    assert report_extraction(SDK, read_spec_operations(SPEC_OPERATIONS)).unknown_to_spec == ()


def test_a_route_the_rule_cannot_read_is_recorded_and_the_rest_still_extracts(tmp_path):
    """A builder call whose path is not a literal is a loss, not a silent shrink and not an
    abort: the record names the method, and every readable operation is still extracted."""
    corrupted = tmp_path / "sdk"
    _copy_tree(SDK, corrupted)
    target = corrupted / "embeddings.py"
    target.write_text(
        target.read_text(encoding="utf-8").replace(
            'path="/v1/embeddings",', "path=dynamic_route,"
        ),
        encoding="utf-8",
    )

    operations, unreadable = extract_symbols(corrupted)
    symbols = {operation.symbol for operation in operations}

    assert "embeddings.create" not in symbols
    assert "embeddings.create_async" not in symbols
    assert "chat.complete" in symbols
    assert any("_build_request" in record and "create" in record for record in unreadable)


def test_source_with_no_candidate_class_fails_rather_than_returning_a_partial_map(tmp_path):
    """First raise site: nothing extends the base this rule anchors on."""
    empty = tmp_path / "sdk"
    empty.mkdir()
    (empty / "nothing.py").write_text("class Thing:\n    pass\n", encoding="utf-8")

    with pytest.raises(UnrecognisedSdkShape, match=GENERATOR):
        extract_symbols(empty)


def test_candidates_with_nothing_mounting_another_fails_too(tmp_path):
    """Second raise site: candidates exist and none mounts another, so nothing is rooted.

    A resource file staged alone is exactly that source -- `Embeddings` extends the base,
    declares operations, and no client mounts it, so every symbol would be unrooted.
    """
    orphans = tmp_path / "sdk"
    orphans.mkdir()
    (orphans / "embeddings.py").write_text(
        (SDK / "embeddings.py").read_text(encoding="utf-8"), encoding="utf-8"
    )

    with pytest.raises(UnrecognisedSdkShape, match="mounts"):
        extract_symbols(orphans)


def test_a_rooted_client_reaching_no_readable_route_fails_too(tmp_path):
    """Third raise site: classes and mounts are present and no route could be read, so the
    checkout parses cleanly, roots cleanly and would yield an empty map -- the partial-map
    failure with a coverage number attached."""
    unreadable_routes = tmp_path / "sdk"
    _copy_tree(SDK, unreadable_routes)
    for path in unreadable_routes.glob("*.py"):
        path.write_text(
            path.read_text(encoding="utf-8")
            .replace('method="POST",', "method=verb,")
            .replace('method="GET",', "method=verb,")
            .replace('method="DELETE",', "method=verb,"),
            encoding="utf-8",
        )

    with pytest.raises(UnrecognisedSdkShape, match="no operation"):
        extract_symbols(unreadable_routes)


def test_a_speakeasy_python_sdk_handed_to_any_other_rule_still_fails_loudly():
    """Naming the wrong rule is not a silent failure, in either direction."""
    from sync.signals.generated import symbols as stainless_python
    from sync.signals.generated import symbols_speakeasy as speakeasy_typescript
    from sync.signals.generated import symbols_typescript as stainless_typescript

    with pytest.raises(stainless_python.UnrecognisedSdkShape):
        stainless_python.extract_symbols(SDK)
    with pytest.raises(stainless_typescript.UnrecognisedSdkShape):
        stainless_typescript.extract_symbols(SDK)
    with pytest.raises(speakeasy_typescript.UnrecognisedSdkShape):
        speakeasy_typescript.extract_symbols(SDK)


def test_the_other_rules_sdks_handed_to_this_one_fail_loudly_too():
    """The mirror: a Stainless Python checkout carries no class deriving `BaseSDK`, and the
    Speakeasy TypeScript checkout carries no Python source at all."""
    with pytest.raises(UnrecognisedSdkShape, match=GENERATOR):
        extract_symbols(FIXTURES / "anthropic_python")
    with pytest.raises(UnrecognisedSdkShape, match=GENERATOR):
        extract_symbols(FIXTURES / "vercel_typescript")


def test_the_other_three_rules_still_read_their_own_sdks():
    """The three finished rules are untouched by this one, and this is what says so."""
    from sync.signals.generated import symbols as stainless_python
    from sync.signals.generated import symbols_speakeasy as speakeasy_typescript
    from sync.signals.generated import symbols_typescript as stainless_typescript

    assert stainless_python.extract_symbols(FIXTURES / "anthropic_python")[0]
    assert stainless_typescript.extract_symbols(FIXTURES / "anthropic_typescript")[0]
    assert speakeasy_typescript.extract_symbols(FIXTURES / "vercel_typescript")[0]


def test_the_adapter_resolves_a_speakeasy_python_symbol(tmp_path):
    from sync.signals.generated.adapter import GeneratedSpecAdapter

    adapter = GeneratedSpecAdapter(
        vendor_id="mistral",
        sources={},
        fetch=lambda url: "",
        cache_dir=tmp_path,
        sdk_source=SDK,
        sdk_spec_operations=SPEC_OPERATIONS,
        sdk_source_generator=GENERATOR,
    )

    found = adapter.operation_for_symbol("mistral.chat.complete", language="python")

    assert found is not None
    assert (found.http_method, found.path) == ("post", "/v1/chat/completions")


def test_a_symbol_the_sdk_does_not_contain_resolves_to_nothing(tmp_path):
    from sync.signals.generated.adapter import GeneratedSpecAdapter

    adapter = GeneratedSpecAdapter(
        vendor_id="mistral",
        sources={},
        fetch=lambda url: "",
        cache_dir=tmp_path,
        sdk_source=SDK,
        sdk_source_generator=GENERATOR,
    )

    assert adapter.operation_for_symbol("mistral.chat.notAMethod") is None
    assert adapter.operation_for_symbol("mistral.ocr.process") is None


def test_the_extractor_registry_offers_this_rule_by_name():
    from sync.signals.generated.adapter import EXTRACTORS

    assert EXTRACTORS[GENERATOR].GENERATOR == GENERATOR
    assert sorted(EXTRACTORS) == [
        "speakeasy-python", "speakeasy-typescript", "stainless-python", "stainless-typescript"
    ]


def _copy_tree(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for path in source.rglob("*"):
        target = destination / path.relative_to(source)
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
