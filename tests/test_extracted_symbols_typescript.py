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
`anthropics/anthropic-sdk-typescript` at tag **sdk-v0.115.0**, commit
`3b45cd3b69c956ac63384fdb09ce1d8109f3fa80`. Eight files under `src/`: `client.ts`,
`resources/index.ts`, `resources/models.ts`, `resources/completions.ts`,
`resources/messages/messages.ts`, `resources/messages/batches.ts`, `resources/beta/beta.ts` and
`resources/beta/models.ts`.

Three of them are there for a reason beyond being reachable.

`resources/models.ts` and `resources/beta/models.ts` both export a class named `Models`, and
`beta.ts` mounts the second while `client.ts` mounts the first. A rule keying classes by bare name
conflates them and files beta routes under the top-level mount;
`test_two_classes_sharing_a_name_are_told_apart_by_their_module` is what holds that apart.

`resources/index.ts` declares no class at all. It is the barrel every one of the client's own
mounts goes through -- `new API.Completions(this)` where `API` is that file -- so without it
nothing is rooted and the extractor raises rather than returning a partial map. That is the right
refusal and the wrong outcome, which is why the barrel is read;
`test_a_mount_through_a_re_export_barrel_is_followed` is what holds it.

The specification fixture is **reused** from the Python flavour, and the reuse is evidenced rather
than assumed. `anthropic_typescript.stats.yml` is this SDK's own manifest at the same tag, and it
publishes the same `openapi_spec_hash` and the same `configured_endpoints` as the Python SDK's --
two flavours generated from one specification, each saying so itself.
`test_both_flavours_were_generated_from_the_same_specification` is what holds that, so the
denominator this file measures against stops being an assumption the moment either SDK moves.

The two manifests name different `openapi_spec_url`s. That is Stainless storing one document under
two content-addressed uploads; the hash is what the manifest publishes as the specification's
identity and is what `SpecSource.changed_from` compares, so it is what this reads.
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
TYPESCRIPT_MANIFEST = FIXTURES / "anthropic_typescript.stats.yml"
PYTHON_MANIFEST = Path(__file__).parent / "fixtures" / "manifests" / "anthropic.stats.yml"


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


def test_a_mount_through_a_re_export_barrel_is_followed():
    """`client.ts` mounts `API.Completions`, and `API` is `./resources/index` -- a barrel that
    declares no class at all and re-exports `Completions` from `./completions`.

    Every one of the client's own mounts arrives this way, so a rule that resolves a mount only
    against classes declared in the aliased module finds nothing rooted and raises. The barrel is
    read the same way everything else here is read: `export { Completions } from './completions'`
    is a declaration in the source, so it is parsed rather than worked around.
    """
    extracted = _extracted()

    assert extracted["completions.create"].http_method == "POST"
    assert extracted["completions.create"].path == "/v1/complete"


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


def test_both_flavours_were_generated_from_the_same_specification():
    """Why one specification fixture is a sound denominator for two SDKs.

    Each manifest publishes its own `openapi_spec_hash`, and the two agree. That is the SDKs
    saying it rather than this test asserting it, and it is what makes the 131 operations a
    denominator for the TypeScript extraction as well as the Python one. If either SDK is bumped
    to a tag generated from a different specification, this goes red before any coverage number
    silently starts being measured against the wrong document.
    """
    from sync.signals.generated.manifest import STAINLESS_MANIFEST, parse_manifest

    typescript = parse_manifest(
        STAINLESS_MANIFEST, TYPESCRIPT_MANIFEST.read_text(encoding="utf-8")
    )
    python = parse_manifest(STAINLESS_MANIFEST, PYTHON_MANIFEST.read_text(encoding="utf-8"))

    assert typescript is not None and python is not None
    assert typescript.spec_hash == python.spec_hash
    assert typescript.endpoint_count == python.endpoint_count == 131


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
    because the second number travels with it.

    And it names *this* rule. The report type is shared with the Python flavour, whose `render`
    writes its own module's generator, so a line saying `stainless-python` over a TypeScript
    extraction is the failure this asserts against -- naming the generator is only worth doing if
    a reader learns which rule spoke.
    """
    from sync.signals.generated.symbols import GENERATOR as PYTHON_GENERATOR

    rendered = report_extraction(SDK, read_spec_operations(SPEC_OPERATIONS)).render()

    assert rendered.startswith(f"{GENERATOR}:")
    assert PYTHON_GENERATOR not in rendered
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


# --- every place the reader declines, and the map it leaves behind ---------------------------
#
# Each of these asserts on the whole symbol map rather than on an internal call. A decline is a
# `continue` or a `return None`, and what makes it right or wrong is which operations survive it:
# a reader that skips too much produces a smaller map, and a smaller map produces fewer findings,
# which is indistinguishable from a healthy vendor.


def test_the_hand_built_sdk_is_read_before_anything_is_declined(tmp_path):
    """The control every other test in this section rests on.

    Each of those adds one construct the reader declines and asserts the map is still exactly
    this. Without this test that assertion is satisfied just as well by an SDK nothing could be
    read from at all, which is the failure they exist to detect.
    """
    assert _map(_hand_built(tmp_path)) == _READABLE


def test_a_client_call_handed_no_arguments_yields_no_operation(tmp_path):
    """`this._client.get()` -- the verb is there and the route is not.

    Declining is right and there is nothing else available: the route is the first argument and
    this call has none. Recording the verb alone would put a symbol in the map with no route to
    match a vendor change against.
    """
    root = _hand_built(tmp_path, "  ping() { return this._client.get(); }")

    assert _map(root) == _READABLE


def test_an_empty_route_however_written_reads_as_absent_rather_than_as_a_route(tmp_path):
    """`''` and an empty tagged template both.

    A string node with no fragment and a template with no parts are the same fact -- the source
    states no route -- and both must read as absent. Reading either as the empty route would mount
    an operation at `""`, which normalises to a path no specification declares and matches
    whatever a later comparison decides an empty string is equal to.
    """
    root = _hand_built(
        tmp_path,
        "  ping() { return this._client.get('', {}); }",
        "  pong() { return this._client.get(path``, {}); }",
    )

    assert _map(root) == _READABLE


def test_a_route_built_by_a_call_this_rule_does_not_read_is_declined(tmp_path):
    """`this._client.get(buildPath(x), {})`.

    The first argument is a call, so it reaches the tagged-template reader, and its arguments are
    a positional list rather than a template. Declining is right: reconstructing what `buildPath`
    returns means evaluating the source, and a route this cannot see is better missing than
    guessed -- a guessed route resolves a call site to an operation the customer never calls.
    """
    root = _hand_built(tmp_path, "  ping() { return this._client.get(buildPath(x), {}); }")

    assert _map(root) == _READABLE


def test_a_tagged_template_under_another_tag_is_not_read_as_a_route(tmp_path):
    """``this._client.get(url`/v1/ping`, {})``.

    Only the `path` tag is read. Declining is right for the reason the module states: reading any
    tag would mean reading any string built by interpolation, and most of those are not routes.
    The cost is that a Stainless flavour renaming that helper reads as a vendor with no
    operations, which is why the tag is a named constant rather than a literal at the test site.
    """
    root = _hand_built(tmp_path, "  ping() { return this._client.get(url`/v1/ping`, {}); }")

    assert _map(root) == _READABLE


def test_a_mount_whose_constructor_is_not_a_name_is_not_an_edge(tmp_path):
    """`new (pick())(this)` -- a `new` expression whose constructor is an expression.

    Declining is right: which class that constructs is a runtime fact, and this rule reads what
    the source states. An edge invented here would file a resource's whole route set under a
    property no customer reaches by that name.
    """
    root = _hand_built(
        tmp_path,
        client=_CLIENT.replace("}\n", "  beta = new (pick())(this);\n}\n"),
    )

    assert _map(root) == _READABLE


def test_a_comment_inside_an_export_clause_does_not_stop_the_barrel_being_followed(tmp_path):
    """`export { /* the resource */ Models } from './models'`.

    A comment is a named child of the export clause, so the clause loop meets one and skips it.
    Declining that child is right -- it names nothing -- and what matters is that the specifier
    beside it is still read: skipping the whole clause would unroot every mount that goes through
    the barrel, which is every mount the client makes.
    """
    root = _hand_built(tmp_path, barrel="export { /* the resource */ Models } from './models';\n")

    assert _map(root) == _READABLE


def test_a_class_reached_only_through_a_star_re_export_is_followed(tmp_path):
    """`export * from './models'` with no named specifier for `Models` anywhere.

    The committed Anthropic barrel names every class it forwards, so its `export * from './shared'`
    is never the clause that resolves one. A barrel that forwards a resource only by star is the
    same declaration made a second way, and a rule that read one and not the other would report a
    vendor with no operations rather than a vendor whose barrel is written differently.
    """
    root = _hand_built(tmp_path, barrel="export * from './models';\n")

    assert _map(root) == _READABLE


def test_an_import_resolving_above_the_checkout_root_names_nothing_here(tmp_path):
    """`import * as Out from '../../elsewhere/thing'`, with a mount through that alias.

    Relative and resolvable, so it is not refused as a package specifier; it simply lands outside
    the tree being read. Declining is right -- a module outside the checkout is not this SDK, and
    following it would read whatever happens to sit beside the clone -- and the mount holding the
    unresolved alias is left out rather than matched against a class of that name somewhere else.
    """
    root = _hand_built(
        tmp_path,
        client=(
            "import * as Out from '../../elsewhere/thing';\n"
            + _CLIENT.replace("}\n", "  outside = new Out.Models(this);\n}\n")
        ),
    )

    assert _map(root) == _READABLE


def test_an_interpolation_this_rule_cannot_resolve_stands_where_it_stood(tmp_path):
    """The module's own stated hard case: a route reassembled from the literal parts of a template.

    An interpolation is never dropped and the literal parts are never simply joined. Every
    substitution contributes a segment in the position it held, whatever the expression inside it
    was, so the route this produces has the same number of segments the source wrote. A template
    read with a hole in it would be a *wrong* route -- `/v1/ping` where the source says
    `${this.baseURL}/v1/ping` -- and a wrong route binds a call site to an operation that exists.
    """
    root = _hand_built(
        tmp_path,
        "  ping() { return this._client.get(path`${this.baseURL}/v1/ping`, {}); }",
        "  two() { return this._client.get(path`/v1/models/${modelID}/x/${version}`, {}); }",
    )
    extracted = _map(root)

    assert extracted["models.ping"] == ("GET", "{this.baseURL}/v1/ping")
    assert extracted["models.two"] == ("GET", "/v1/models/{modelID}/x/{version}")


def test_a_route_carrying_an_unresolvable_interpolation_is_unknown_to_the_specification(tmp_path):
    """And what that costs, measured on the cross-check rather than argued.

    The extra segment survives the parameter reduction as an extra placeholder, so the route
    matches nothing the specification declares and is reported. That makes an interpolation this
    rule cannot resolve a **missing** binding that says so, not a wrong one -- the operation is in
    the map, it resolves to no vendor change, and the cross-check names it where a spec is staged.
    """
    root = _hand_built(
        tmp_path, "  ping() { return this._client.get(path`${this.baseURL}/v1/models`, {}); }"
    )

    report = report_extraction(root, read_spec_operations(SPEC_OPERATIONS))

    assert [operation.symbol for operation in report.unknown_to_spec] == ["models.ping"]


def test_a_route_literal_carrying_an_escape_is_declined_rather_than_truncated(tmp_path):
    """Neither reader interprets an escape, and neither may read the fragments around one.

    tree-sitter splits a literal at every escape, so a plain string yields two fragments and a
    template yields two parts with the escape between them. Taking the first fragment reads
    `/v1/a` for a source that says `/v1/aAb`, and joining a template's fragments reads `/v1/ab`
    for the same -- both are routes the source does not state, produced silently, and a wrong
    route is worse than a missing one because it resolves.
    """
    root = _hand_built(
        tmp_path,
        "  plain() { return this._client.get('/v1/a\\u0041b', {}); }",
        "  tagged() { return this._client.get(path`/v1/a\\u0041b/${x}`, {}); }",
    )

    assert _map(root) == _READABLE


def test_a_resource_this_grammar_does_not_call_a_class_declaration_is_never_reached(tmp_path):
    """`abstract class Beta extends APIResource` parses as `abstract_class_declaration`, and
    `export default class extends APIResource` as a class *expression*. Neither is the
    `class_declaration` this rule matches, so neither is read and no guarded branch is reached.

    Declining is defensible -- Stainless emits neither -- but the decline happens before any
    branch that could record it, and this is what it looks like from outside: an SDK that parses,
    roots, reports a coverage number and is missing a resource. Recorded here because the map is
    the only place it shows.
    """
    root = _hand_built(
        tmp_path,
        client=_CLIENT.replace("}\n", "  beta: API.Beta = new API.Beta(this);\n}\n"),
        barrel=_HAND_BUILT_BARREL + "export { Beta } from './beta';\n",
    )
    (root / "resources" / "beta.ts").write_text(
        "import { APIResource } from '../core/resource';\n"
        "\n"
        "export abstract class Beta extends APIResource {\n"
        "  list() { return this._client.get('/v1/beta', {}); }\n"
        "}\n",
        encoding="utf-8",
    )

    assert _map(root) == _READABLE


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


def test_the_adapter_cross_checks_a_typescript_map_and_names_this_rule_in_the_log(caplog):
    """The adapter's own reporting path, which is where an operator meets the coverage number.

    Worth asserting separately from `report_extraction`: the adapter is what selects a rule, and a
    line naming the wrong one is a wrong answer that reads as a measurement.
    """
    import logging

    from sync.signals.generated.adapter import GeneratedSpecAdapter

    adapter = GeneratedSpecAdapter(
        vendor_id="anthropic", sources={}, fetch=_never_fetch, cache_dir=FIXTURES,
        sdk_source=SDK, sdk_spec_operations=SPEC_OPERATIONS, sdk_source_generator=GENERATOR,
    )
    with caplog.at_level(logging.INFO, logger="sync.signals.generated.adapter"):
        assert adapter.operation_for_symbol("anthropic.models.list") is not None

    assert any(GENERATOR in record.getMessage() for record in caplog.records)


def test_a_generator_this_deployment_cannot_read_is_refused_where_it_is_configured():
    """Not on the run where a symbol quietly stops resolving.

    A rule is named by generator *times* language, so a name is a thing a deployment can get
    wrong. Getting it wrong must fail while someone is looking at the configuration.
    """
    from sync.signals.generated.adapter import GeneratedSpecAdapter

    with pytest.raises(ValueError) as raised:
        GeneratedSpecAdapter(
            vendor_id="anthropic", sources={}, fetch=_never_fetch, cache_dir=FIXTURES,
            sdk_source=SDK, sdk_source_generator="speakeasy-go",
        )

    assert "speakeasy-go" in str(raised.value)
    assert GENERATOR in str(raised.value)


def _never_fetch(url: str) -> str:
    raise AssertionError("symbol extraction must not reach a network")


_CLIENT = """\
import * as API from './resources/index';

export class Anthropic extends BaseAnthropic {
  models: API.Models = new API.Models(this);
}
"""

_HAND_BUILT_BARREL = "export { Models } from './models';\n"

_READABLE = {"models.list": ("GET", "/v1/models")}
"""The one operation the hand-built SDK always states, and the whole map when nothing else is."""


def _hand_built(
    tmp_path: Path,
    *methods: str,
    client: str = _CLIENT,
    barrel: str = _HAND_BUILT_BARREL,
) -> Path:
    """Three files of the shape this rule reads, with `models.list` always readable.

    Written by hand rather than cut from a vendor, because every construct these tests are about
    is one Stainless does not emit -- there is nothing in the committed Anthropic fixture to
    replace, and corrupting it into these shapes would make the corruption the fixture.

    `models.list` is here so the map has something in it either way: a decline test asserting
    only that a symbol is absent passes just as well when the whole SDK failed to parse.
    """
    root = tmp_path / "sdk"
    files = {
        "client.ts": client,
        "resources/index.ts": barrel,
        "resources/models.ts": (
            "import { APIResource } from '../core/resource';\n"
            "import { path } from '../internal/utils/path';\n"
            "\n"
            "export class Models extends APIResource {\n"
            + "\n".join(["  list() { return this._client.get('/v1/models', {}); }", *methods])
            + "\n}\n"
        ),
    }
    for relative, body in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    return root


def _map(root: Path) -> dict[str, tuple[str, str]]:
    return {
        operation.symbol: (operation.http_method, operation.path)
        for operation in extract_symbols(root)
    }


def _corrupt(tmp_path: Path, relative: str, old: str, new: str) -> Path:
    import shutil

    destination = tmp_path / "sdk"
    shutil.copytree(SDK, destination)
    target = destination / relative
    text = target.read_text(encoding="utf-8")
    assert old in text, f"{relative} does not contain {old}, so this corruption proves nothing"
    target.write_text(text.replace(old, new), encoding="utf-8")
    return destination
