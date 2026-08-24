"""The symbol map is read out of the SDK's own source, not proposed.

`docs/superpowers/specs/2026-07-29-sync-adaptive-vendor-substrate.md` step 4, and the section
arguing why extraction beats generation: an audit found that coverage cannot refute a
plausible-but-wrong mapping, and the fix is not a better metric but to stop generating the
mapping at all. A generated SDK states the HTTP method and path in the source that makes the
call, so the mapping is read from the artifact that will actually send the request -- and that
artifact cannot be wrong about what it sends, because it is the thing that sends it.

This does not overturn `GeneratedSpecAdapter.operation_for_symbol`'s reasoning. That docstring
refuses to *invent* a convention, and it is right: a guessed convention fails silently, because
an unresolvable symbol yields no finding and nobody learns the guess was wrong. Nothing here
guesses. Every pair below is a string literal lifted out of committed source.

Fixtures
--------
`sdk_sources/anthropic_python/` is verbatim source from `anthropics/anthropic-sdk-python` at tag
**v0.120.2**, fetched through the GitHub contents API on 2026-07-29 -- five files: `_client.py`, `resources/models.py`,
`resources/completions.py`, `resources/messages/messages.py` and
`resources/messages/batches.py`. The `beta/` tree is left out -- it carries 120 of the
specification's 131 operations -- and the consequence for the coverage number is stated in
`test_coverage_is_reported_against_the_specifications_operation_count` rather than hidden.

`anthropic_spec_operations.json` is the operation set of the specification that SDK's own
manifest names -- `openapi_spec_url` in `tests/fixtures/manifests/anthropic.stats.yml` -- fetched
the same day and reduced to method and path. It holds 131 operations, which is exactly the
`configured_endpoints: 131` the manifest declares, so the denominator is corroborated by two
independently published artifacts rather than asserted here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sync.signals.generated.symbols import (
    GENERATOR,
    ExtractedOperation,
    UnrecognisedSdkShape,
    _route,
    extract_symbols,
    read_spec_operations,
    report_extraction,
)

FIXTURES = Path(__file__).parent / "fixtures" / "sdk_sources"
SDK = FIXTURES / "anthropic_python"
SPEC_OPERATIONS = FIXTURES / "anthropic_spec_operations.json"


def _extracted() -> dict[str, ExtractedOperation]:
    return {operation.symbol: operation for operation in extract_symbols(SDK)[0]}


# --- what the source says --------------------------------------------------------------


def test_the_generator_supported_is_named():
    """One generator, said out loud. An extractor that tried to serve every SDK shape would be
    guessing about the ones it had not seen, which is the failure this replaces."""
    assert GENERATOR == "stainless-python"


def test_a_plain_path_literal_is_read_from_the_call_that_sends_it():
    """`self._get_api_list("/v1/models", ...)` in `resources/models.py`. The verb is the method
    Stainless emits and the path is the string beside it; neither is derived from the resource
    name, which is what would make this generation rather than extraction."""
    models = _extracted()["models.list"]

    assert models.http_method == "GET"
    assert models.path == "/v1/models"


def test_a_templated_path_is_read_from_its_literal_argument():
    """`self._get(path_template("/v1/models/{model_id}", model_id=model_id), ...)`. The template
    helper's first argument is the path as written; the keyword arguments are the interpolation
    and say nothing about the route."""
    retrieve = _extracted()["models.retrieve"]

    assert retrieve.http_method == "GET"
    assert retrieve.path == "/v1/models/{model_id}"


def test_a_nested_resource_carries_its_whole_chain():
    """`client.messages.batches.create`. The chain is read from the `cached_property` wiring in
    `_client.py` and `resources/messages/batches.py`, not assembled from file paths -- a
    generator is free to mount a resource under a name its directory does not carry."""
    extracted = _extracted()

    assert extracted["messages.batches.create"].path == "/v1/messages/batches"
    assert extracted["messages.batches.create"].http_method == "POST"
    assert extracted["messages.batches.cancel"].path == "/v1/messages/batches/{message_batch_id}/cancel"


def test_every_verb_stainless_emits_is_recognised():
    """`_delete` is the one a fixture holding only reads would miss, and a verb silently skipped
    is an operation that resolves to nothing while looking like a vendor with fewer endpoints."""
    extracted = _extracted()

    assert extracted["messages.batches.delete"].http_method == "DELETE"
    assert extracted["completions.create"].http_method == "POST"
    assert {operation.http_method for operation in extracted.values()} >= {"GET", "POST", "DELETE"}


def test_the_async_and_wrapper_classes_do_not_produce_a_second_map():
    """Stainless emits `AsyncModels`, `ModelsWithRawResponse` and `ModelsWithStreamingResponse`
    beside every resource. They are the same operations reached differently, and counting them
    would inflate coverage against a denominator that counts each operation once."""
    symbols = set(_extracted())

    assert not [symbol for symbol in symbols if "async" in symbol.lower()]
    assert not [symbol for symbol in symbols if "raw_response" in symbol or "with_" in symbol]
    assert len(symbols) == len(set(symbols))


# --- the closing condition: measured coverage against a named denominator ---------------


def test_coverage_is_reported_against_the_specifications_operation_count():
    """The spec's own history is the warning: the Stripe map covers 105 of 414 paths, and that
    number means something only because the denominator travels with it.

    The specification publishes **131** operations, which is exactly the `configured_endpoints`
    the manifest declares -- two independently published artifacts agreeing on the denominator.
    Of those, **121** are distinct routes once the `?beta=true` marker is dropped, and 121 is
    what an extracted route can be matched against. Both numbers are asserted, because they
    measure different things and quoting one as the other is how a denominator stops meaning
    anything. Until M3-W100 the report carried only the second and called it the first.

    The numerator is what this committed fixture contains: the non-beta resource modules. The
    `beta/` tree is not committed, and it carries most of the specification, so this is a floor
    on the SDK's true coverage rather than a measurement of it -- the un-truncated figure is in
    the task report. Both numbers rather than a ratio, because a ratio hides which one moved.

    Eleven symbols reach ten operations, and the gap is not a defect: `messages.create` and
    `messages.parse` both send `POST /v1/messages`. Coverage is counted on the specification's
    side for exactly that reason -- counting extracted symbols would report more coverage than
    there are operations to cover, and against a smaller SDK could exceed the denominator.
    """
    published = json.loads(SPEC_OPERATIONS.read_text(encoding="utf-8"))
    report = report_extraction(SDK, read_spec_operations(SPEC_OPERATIONS))

    assert len(published) == 131
    assert report.declared_operation_count == 131
    assert report.comparable_key_count == 121
    assert report.extracted_count == 11
    assert report.covered_count == 10
    assert 0 < report.coverage_ratio < 1


def test_the_denominator_is_the_specification_and_not_the_extraction():
    """A coverage figure whose denominator is what was extracted always reads 100%, which is the
    shape of measurement the audit found could not refute a wrong mapping."""
    report = report_extraction(SDK, read_spec_operations(SPEC_OPERATIONS))

    assert report.comparable_key_count > report.extracted_count


# --- the cross-check, which is what makes the result refutable --------------------------


def test_an_operation_the_specification_does_not_declare_is_reported(tmp_path):
    """The closing condition's other half: a deliberately corrupted SDK source is caught by the
    cross-check rather than by a reviewer.

    One path literal is altered to a route the specification does not contain. The extractor
    still reads it -- it is doing its job, the source really does say that -- and the cross-check
    is what refuses it. Reported rather than dropped, because a silently discarded operation is
    indistinguishable from a vendor that genuinely does not offer it.
    """
    corrupted = tmp_path / "sdk"
    _copy_sdk(corrupted)
    models = corrupted / "resources" / "models.py"
    models.write_text(
        models.read_text(encoding="utf-8").replace('"/v1/models"', '"/v1/model_registry"'),
        encoding="utf-8",
    )

    report = report_extraction(corrupted, read_spec_operations(SPEC_OPERATIONS))

    clean = report_extraction(SDK, read_spec_operations(SPEC_OPERATIONS))

    assert [operation.path for operation in report.unknown_to_spec] == ["/v1/model_registry"]
    assert report.covered_count == clean.covered_count - 1


def test_the_cross_check_is_not_vacuous(tmp_path):
    """A check that never fires is decoration. The uncorrupted fixture must report nothing, or
    the assertion above would pass against an extractor that flagged everything."""
    clean = report_extraction(SDK, read_spec_operations(SPEC_OPERATIONS))
    assert clean.unknown_to_spec == ()

    corrupted = tmp_path / "sdk"
    _copy_sdk(corrupted)
    batches = corrupted / "resources" / "messages" / "batches.py"
    batches.write_text(
        batches.read_text(encoding="utf-8").replace('"/v1/messages/batches"', '"/v1/batches"'),
        encoding="utf-8",
    )

    assert report_extraction(corrupted, read_spec_operations(SPEC_OPERATIONS)).unknown_to_spec != ()


def test_a_beta_query_marker_is_not_mistaken_for_a_different_route():
    """This specification writes 120 of its 131 operations with a `?beta=true` suffix, and the
    SDK writes the path without one. Reading the suffix as part of the route would report every
    beta operation as unknown to the spec -- a cross-check that fires on a difference in how two
    artifacts spell the same thing is worse than none, because it trains a reader to ignore it.

    The marker survives the read and is dropped by the comparison, which is where M3-W100 moved
    it. Dropping it at the read is what made the published operation count unrecoverable: the
    ten routes listed both with and without the marker arrived as ten members instead of twenty,
    and the report's denominator was 121 for a specification declaring 131.
    """
    operations = read_spec_operations(SPEC_OPERATIONS)

    published = json.loads(SPEC_OPERATIONS.read_text(encoding="utf-8"))
    assert sum(1 for entry in published if "?beta=true" in entry["path"]) == 120

    assert ("GET", "/v1/models") in operations
    assert ("GET", "/v1/models?beta=true") in operations
    assert len({_route(method, path) for method, path in operations}) == 121

    report = report_extraction(SDK, read_spec_operations(SPEC_OPERATIONS))
    assert report.unknown_to_spec == ()


# --- an unrecognised shape fails loudly -------------------------------------------------


def test_source_with_no_recognisable_client_fails_rather_than_returning_a_partial_map(tmp_path):
    """A partial map is indistinguishable from a vendor whose operations genuinely cannot be
    seen, and it is worse than an error because it produces a coverage number that looks like a
    measurement."""
    (tmp_path / "thing.py").write_text("class Thing:\n    pass\n", encoding="utf-8")

    with pytest.raises(UnrecognisedSdkShape) as raised:
        extract_symbols(tmp_path)

    assert GENERATOR in str(raised.value)


def test_a_client_with_no_resources_fails_too(tmp_path):
    """Half the shape is not the shape. A client class whose resources this rule cannot see
    yields an empty map, and an empty map reported as success is the silent failure the
    generated adapter's docstring warns about."""
    (tmp_path / "_client.py").write_text(
        "class Acme(SyncAPIClient):\n    pass\n", encoding="utf-8"
    )

    with pytest.raises(UnrecognisedSdkShape):
        extract_symbols(tmp_path)


# --- resolution through the adapter -----------------------------------------------------


def test_the_adapter_resolves_an_extracted_symbol():
    """The whole point: a configured vendor with no hand-written map answers a call site."""
    from sync.signals.generated.adapter import GeneratedSpecAdapter

    adapter = GeneratedSpecAdapter(
        vendor_id="anthropic", sources={}, fetch=_never_fetch, cache_dir=FIXTURES,
        sdk_source=SDK,
    )
    reference = adapter.operation_for_symbol("anthropic.models.list", language="python")

    assert reference is not None
    assert reference.http_method == "get"
    assert reference.path == "/v1/models"


def test_a_symbol_the_sdk_does_not_contain_resolves_to_nothing():
    """A wrong lookup stays a miss rather than becoming a wrong hit. The extractor knows what the
    source says and nothing else, so a symbol absent from it has no answer to give."""
    from sync.signals.generated.adapter import GeneratedSpecAdapter

    adapter = GeneratedSpecAdapter(
        vendor_id="anthropic", sources={}, fetch=_never_fetch, cache_dir=FIXTURES,
        sdk_source=SDK,
    )

    assert adapter.operation_for_symbol("anthropic.charges.create", language="python") is None
    assert adapter.operation_for_symbol("anthropic.models", language="python") is None


def test_an_adapter_with_no_sdk_source_still_answers_none():
    """The behaviour the existing docstring describes, kept exactly. A vendor whose SDK source
    this deployment has not staged resolves nothing rather than guessing, which is what that
    docstring refuses and this change does not overturn."""
    from sync.signals.generated.adapter import GeneratedSpecAdapter

    adapter = GeneratedSpecAdapter(
        vendor_id="anthropic", sources={}, fetch=_never_fetch, cache_dir=FIXTURES
    )

    assert adapter.operation_for_symbol("anthropic.models.list", language="python") is None


def test_the_hand_written_stripe_map_is_unaffected():
    """A vendor resolving from a map somebody built must answer exactly as it did.

    It used to be pinned against `StripeAdapter`; `CI-W586` retired that adapter and the
    property moved to the tier, which is now the only thing that reads a staged map.
    """
    from conftest import symbol_resolver
    from sync.signals.generated.symbols_stripe_openapi import build_symbol_map

    spec = {"paths": {"/v1/charges": {"post": {"operationId": "PostCharges"}}}}
    map_path = FIXTURES / "stripe-map-unused.json"
    try:
        map_path.write_text(json.dumps(build_symbol_map(spec)), encoding="utf-8")
        adapter = symbol_resolver(map_path)
        reference = adapter.operation_for_symbol("stripe.charges.create", language="typescript")
    finally:
        map_path.unlink(missing_ok=True)

    assert reference is not None
    assert reference.operation_id == "PostCharges"


def _never_fetch(url: str) -> str:
    raise AssertionError("symbol extraction must not reach a network")


def _copy_sdk(destination: Path) -> None:
    import shutil

    shutil.copytree(SDK, destination)


def test_the_adapter_cross_checks_when_a_specification_is_staged(caplog):
    """The check has to run where the map is built, not only where a test calls it.

    `scripts/lint_dead_links.py` caught this: `report_extraction` was reached from nothing in
    `src/`, which is the shape of defect this build has spent weeks removing -- a component only
    a test calls is not wired in, and a cross-check nobody runs protects nothing.
    """
    import logging

    from sync.signals.generated.adapter import GeneratedSpecAdapter

    adapter = GeneratedSpecAdapter(
        vendor_id="anthropic", sources={}, fetch=_never_fetch, cache_dir=FIXTURES,
        sdk_source=SDK, sdk_spec_operations=SPEC_OPERATIONS,
    )
    with caplog.at_level(logging.INFO, logger="sync.signals.generated.adapter"):
        adapter.operation_for_symbol("anthropic.models.list", language="python")

    logged = " ".join(record.getMessage() for record in caplog.records)
    assert "11 symbols extracted" in logged, logged
    assert "10 of 121 comparable routes" in logged, logged
    assert "the specification declares 131 operations" in logged, logged
    assert GENERATOR in logged


def test_an_operation_unknown_to_the_specification_is_logged_and_still_resolves(tmp_path, caplog):
    """Logged, not dropped. The SDK is what runs, so a route it states is one the customer's
    process will send whatever the specification says -- discarding it would make a misread
    source indistinguishable from a vendor that genuinely lacks the route, which is the
    distinction the check exists to draw."""
    import logging

    from sync.signals.generated.adapter import GeneratedSpecAdapter

    corrupted = tmp_path / "sdk"
    _copy_sdk(corrupted)
    models = corrupted / "resources" / "models.py"
    models.write_text(
        models.read_text(encoding="utf-8").replace('"/v1/models"', '"/v1/model_registry"'),
        encoding="utf-8",
    )

    adapter = GeneratedSpecAdapter(
        vendor_id="anthropic", sources={}, fetch=_never_fetch, cache_dir=FIXTURES,
        sdk_source=corrupted, sdk_spec_operations=SPEC_OPERATIONS,
    )
    with caplog.at_level(logging.WARNING, logger="sync.signals.generated.adapter"):
        reference = adapter.operation_for_symbol("anthropic.models.list", language="python")

    assert "/v1/model_registry" in " ".join(r.getMessage() for r in caplog.records)
    assert reference is not None and reference.path == "/v1/model_registry"


def test_an_operation_carrying_its_own_id_is_not_given_a_synthesised_one():
    """A rule that read the specification knows the vendor's name for an operation.

    Synthesising `"GET /v1/charges"` over it would discard a stated fact for a derived one, and
    the derived one does not match what a spec diff reports the change against.
    """
    op = ExtractedOperation(
        symbol="charges.create", http_method="POST", path="/v1/charges",
        operation_id="PostCharges",
    )

    assert op.operation_id == "PostCharges"


def test_an_operation_stating_no_id_still_synthesises_the_route():
    # Every checkout-reading rule is this case, and it must not change.
    op = ExtractedOperation(symbol="charges.create", http_method="POST", path="/v1/charges")

    assert op.operation_id is None
    assert op.service_id is None
    assert op.languages is None
