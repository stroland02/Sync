"""The same map, read out of Speakeasy's TypeScript emission.

The third flavour, and the first from a different generator. `symbols.py` covers
`stainless-python` and `symbols_typescript.py` covers `stainless-typescript`; both authors
established the same boundary, that an extraction rule covers a generator *times* a language and
a rule claiming more would be guessing about the emission it had not seen. Speakeasy is the case
that boundary was drawn for. `symbols.py`'s own docstring predicted its shape -- "Speakeasy uses
an object property and a helper call" -- and reading the source confirms it exactly.

Why this vendor is not hypothetical: `generated-vendors.yaml` configures `vercel` against
`@vercel/sdk` on the strength of `manifest._parse_speakeasy`, so today Vercel is a vendor whose
specification is diffable, whose package the indexer matches and whose client it finds -- and
every symbol resolves to nothing for want of this module.

What Speakeasy writes down, and where it differs
------------------------------------------------
The difference that matters is that **the route is not in the file that declares the method**.
Both Stainless flavours put the verb and path inside the method body; Speakeasy puts a one-line
delegation there and writes the request in a standalone function module:

    // src/sdk/aliases.ts
    export class Aliases extends ClientSDK {
      async getAlias(request, options) {
        return unwrapAsync(aliasesGetAlias(this, request, options));
      }
    }

    // src/funcs/aliasesGetAlias.ts
    const path = pathToFunc("/v4/aliases/{idOrAlias}")(pathParams);
    const requestRes = client._createRequest(context, { method: "GET", path: path, ... });

So an operation is read across two modules joined by an import, the path comes from a helper
call and the verb from an object property. Neither Stainless flavour has to cross a module
boundary to state one operation, which is why this is a third rule rather than a third branch.

The client is not distinguished by its base class either. `Vercel`, all 41 resources **and**
`VercelCore` extend `ClientSDK` alike, so the base is what identifies a candidate and not what
picks the root. The root is the class that mounts others and is not mounted -- and `VercelCore`,
which is `export class VercelCore extends ClientSDK {}` and nothing more, falls out of that for
free rather than being named.

Fixtures
--------
`sdk_sources/vercel_typescript/` is verbatim source from `vercel/sdk` at tag **v1.28.12**, commit
`142fa1bd976e91e47468cee500342efe59162bde`. Twenty files: `core.ts`, four under `sdk/` and
fifteen under `funcs/`.

`sdk/sdk.ts` is committed whole, with all 41 of its mounts, while only three of the resource
classes it names are. That is deliberate and it is a test in itself: a mount naming a class this
checkout does not contain must simply not be an edge, rather than raising or resolving to
something else. As with both Stainless fixtures, coverage measured here is a floor and the
un-truncated figure against the full checkout is in the task report.

`core.ts` is here for one reason: `VercelCore` is the class that proves the root rule is
"mounts and is not mounted" rather than "extends `ClientSDK`". Drop it and the fixture stops
holding that apart.

`vercel_spec_operations.json` is the operation set of the specification `.speakeasy/workflow.yaml`
names -- `https://openapi.vercel.sh/`, fetched 2026-07-29 and reduced to method and path, because
the document is 9.8 MB and nothing here reads anything else from it. It holds **359** operations
against the SDK's 349 request modules, which is the two artifacts nearly agreeing rather than a
number this file asserts.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sync.signals.generated.symbols import read_spec_operations
from sync.signals.generated.symbols_speakeasy import (
    GENERATOR,
    UnrecognisedSdkShape,
    extract_symbols,
    report_extraction,
)

FIXTURES = Path(__file__).parent / "fixtures" / "sdk_sources"
SDK = FIXTURES / "vercel_typescript"
SPEC_OPERATIONS = FIXTURES / "vercel_spec_operations.json"


def _by_symbol() -> dict[str, tuple[str, str]]:
    return {
        operation.symbol: (operation.http_method, operation.path)
        for operation in extract_symbols(SDK)[0]
    }


def test_the_generator_and_language_supported_are_named():
    """A rule covers a generator times a language, and says which."""
    assert GENERATOR == "speakeasy-typescript"


def test_the_route_is_read_across_the_module_boundary_speakeasy_puts_it_behind():
    """The shape that makes this a third rule rather than a third branch.

    `Aliases.getAlias` contains no route at all -- it delegates to `aliasesGetAlias`, and the
    verb and path are written in that function's own module. Reading it means following the
    import the class file states, which neither Stainless flavour has to do.
    """
    assert _by_symbol()["aliases.getAlias"] == ("GET", "/v4/aliases/{idOrAlias}")


def test_the_verb_comes_from_the_request_object_and_not_from_the_method_name():
    """Read, do not infer, and this fixture holds two cases where inferring cannot work.

    `assignAlias` and `listDeploymentAliases` send POST and GET to **one route**, so no rule
    reading either name can produce both -- the verb has to come from the `method` property of
    the object handed to `_createRequest`, which is where it is written.

    `getWebhook` and `getWebhooks` differ by one character and address different routes. A
    convention turning a method name into a path would have to invent the `{id}` segment for one
    of them and not the other, which is generation wearing extraction's name.

    Written in this shape after the first draft of this test asserted `requestDelete` was a POST
    on the strength of its name. The extractor read DELETE out of the source and was right; the
    assumption was the thing under test and it lost.
    """
    extracted = _by_symbol()

    assert extracted["aliases.assignAlias"] == ("POST", "/v2/deployments/{id}/aliases")
    assert extracted["aliases.listDeploymentAliases"] == ("GET", "/v2/deployments/{id}/aliases")

    assert extracted["webhooks.getWebhook"] == ("GET", "/v1/webhooks/{id}")
    assert extracted["webhooks.getWebhooks"] == ("GET", "/v1/webhooks")

    assert extracted["user.requestDelete"] == ("DELETE", "/v1/user")
    assert extracted["aliases.patchUrlProtectionBypass"] == (
        "PATCH", "/aliases/{id}/protection-bypass"
    )


def test_every_mounted_resource_carries_its_mount_name_as_the_symbol_root():
    """`client.aliases.listAliases` is the chain a customer writes, and the mount name is the
    getter's name rather than the class's."""
    extracted = _by_symbol()

    assert extracted["aliases.listAliases"] == ("GET", "/v4/aliases")
    assert extracted["user.getAuthUser"] == ("GET", "/v2/user")
    assert extracted["webhooks.getWebhooks"] == ("GET", "/v1/webhooks")


def test_two_operations_sharing_a_route_under_different_verbs_stay_distinct():
    """`/v2/deployments/{id}/aliases` is both a GET and a POST, and they are two operations."""
    extracted = _by_symbol()

    assert extracted["aliases.listDeploymentAliases"][1] == extracted["aliases.assignAlias"][1]
    assert extracted["aliases.listDeploymentAliases"][0] == "GET"
    assert extracted["aliases.assignAlias"][0] == "POST"


def test_a_mount_naming_a_class_this_checkout_does_not_hold_is_simply_not_an_edge():
    """`sdk.ts` is committed whole and mounts 41 resources; three are here.

    The other 38 must produce no symbols and no error. An unresolved name left unresolved is the
    same refusal the rest of this rule makes -- the alternative is matching it against some class
    of that name elsewhere, which is a wrong answer that resolves.
    """
    mounted = {symbol.split(".")[0] for symbol in _by_symbol() if "." in symbol}

    assert mounted == {"aliases", "user", "webhooks"}


def test_the_bare_core_client_contributes_nothing():
    """`export class VercelCore extends ClientSDK {}` extends the same base as the real client.

    It mounts nothing and declares no operation, so a rule anchoring the root on the base class
    would have two roots and one of them empty. Nothing here names `VercelCore`; it falls out of
    the mounts-and-is-not-mounted rule.
    """
    assert not any(symbol.startswith("VercelCore") for symbol in _by_symbol())
    assert (SDK / "core.ts").read_text(encoding="utf-8").count("extends ClientSDK") == 1


def test_an_operation_the_client_declares_itself_has_no_mount_in_its_symbol():
    """The client is not only a mount point; it declares 11 operations of its own.

    `vercel.getStorageStoresById(...)` is written on the client directly, so its chain is empty
    and the symbol is the bare method name. A rule that only walked mounts would drop all 11 and
    report a coverage number three per cent short with nothing to say why.
    """
    assert _by_symbol()["getStorageStoresById"] == ("GET", "/storage/stores/{id}")


def test_the_fifteen_committed_request_modules_are_all_reached():
    """The denominator this fixture can be held to: one symbol per committed func module."""
    assert len(_by_symbol()) == 15


def test_the_specification_fixture_is_the_one_this_sdks_manifest_names():
    """The denominator's provenance, evidenced rather than asserted by a README.

    The SDK's own `.speakeasy/workflow.yaml` is committed beside it, and the URL this file's
    operation set was fetched from is the single input that manifest declares. Moving the fixture
    to a tag generated from a different document goes red here, before a coverage number starts
    being measured against the wrong denominator.

    The Anthropic pair can do better than this -- two manifests publishing one `openapi_spec_hash`
    -- because Stainless publishes a hash and an endpoint count. A Speakeasy workflow declares its
    inputs and not its size, so the strongest available check is that the URL still matches.
    """
    import yaml

    manifest = yaml.safe_load(
        (FIXTURES / "vercel_typescript.workflow.yaml").read_text(encoding="utf-8")
    )
    inputs = [
        entry["location"]
        for source in manifest["sources"].values()
        for entry in source["inputs"]
    ]

    assert inputs == ["https://openapi.vercel.sh/"]


def test_coverage_is_reported_against_the_specifications_operation_count():
    spec = read_spec_operations(SPEC_OPERATIONS)
    report = report_extraction(SDK, spec)

    assert report.extracted_count == 15
    assert report.declared_operation_count == len(spec)
    assert report.comparable_key_count == len(spec)
    assert report.covered_count <= report.comparable_key_count
    assert 0 < report.coverage_ratio < 1


def test_the_rendered_line_names_this_rule_and_carries_the_denominator():
    """A number without its denominator says nothing, and a line naming the wrong rule tells an
    operator the wrong module read the SDK."""
    report = report_extraction(SDK, read_spec_operations(SPEC_OPERATIONS))
    line = report.render()

    assert line.startswith(f"{GENERATOR}:")
    assert "stainless" not in line
    assert f"of {report.comparable_key_count} comparable routes" in line
    assert f"declares {report.declared_operation_count} operations" in line


def test_an_operation_the_specification_does_not_declare_is_reported(tmp_path):
    """Reported rather than dropped: a misread source and a vendor that genuinely lacks a route
    are different facts, and only one of them is a defect here."""
    thinned = tmp_path / "thinned.json"
    declared = [
        entry
        for entry in json.loads(SPEC_OPERATIONS.read_text(encoding="utf-8"))
        if entry["path"] != "/v4/aliases"
    ]
    thinned.write_text(json.dumps(declared), encoding="utf-8")

    report = report_extraction(SDK, read_spec_operations(thinned))

    assert [operation.symbol for operation in report.unknown_to_spec] == ["aliases.listAliases"]


def test_the_cross_check_is_not_vacuous(tmp_path):
    """Prove the check can fire, by corrupting the source rather than the specification.

    A route rewritten in the SDK is exactly what a generator changing its emission would look
    like, and a cross-check that could not see it would be decoration.
    """
    corrupted = tmp_path / "sdk"
    _copy_tree(SDK, corrupted)
    target = corrupted / "funcs" / "aliasesGetAlias.ts"
    target.write_text(
        target.read_text(encoding="utf-8").replace(
            '"/v4/aliases/{idOrAlias}"', '"/v4/aliases/{idOrAlias}/not-a-real-route"'
        ),
        encoding="utf-8",
    )

    report = report_extraction(corrupted, read_spec_operations(SPEC_OPERATIONS))

    assert [operation.symbol for operation in report.unknown_to_spec] == ["aliases.getAlias"]
    assert report_extraction(SDK, read_spec_operations(SPEC_OPERATIONS)).unknown_to_spec == ()


def test_source_with_no_client_class_fails_rather_than_returning_a_partial_map(tmp_path):
    """First raise site: nothing extends the base this rule anchors on, so there is no candidate
    class at all and every symbol would be missing."""
    empty = tmp_path / "sdk"
    empty.mkdir()
    (empty / "nothing.ts").write_text("export const x = 1;\n", encoding="utf-8")

    with pytest.raises(UnrecognisedSdkShape, match=GENERATOR):
        extract_symbols(empty)


def test_classes_with_nothing_mounting_them_fails_too(tmp_path):
    """Second raise site: candidates exist and none mounts another, so nothing is rooted.

    `core.ts` alone is exactly that source -- a class extending the base and mounting nothing.
    """
    orphans = tmp_path / "sdk"
    orphans.mkdir()
    (orphans / "core.ts").write_text(
        (SDK / "core.ts").read_text(encoding="utf-8"), encoding="utf-8"
    )

    with pytest.raises(UnrecognisedSdkShape, match="mounts"):
        extract_symbols(orphans)


def test_a_client_whose_request_modules_are_absent_fails_too(tmp_path):
    """Third raise site, and the one only this generator has.

    The route lives in another module, so a checkout carrying the classes and not the functions
    parses cleanly, roots cleanly, and yields a map with no operations in it. Half the shape is
    not the shape: an empty map reported as success is the partial-map failure with a coverage
    number attached.
    """
    classes_only = tmp_path / "sdk"
    _copy_tree(SDK, classes_only)
    for path in (classes_only / "funcs").glob("*.ts"):
        path.unlink()

    with pytest.raises(UnrecognisedSdkShape, match="no operation"):
        extract_symbols(classes_only)


def test_a_speakeasy_sdk_handed_to_either_stainless_rule_still_fails_loudly():
    """Naming the wrong rule is not a silent failure. Each raises on the other's source rather
    than returning the part of it that happens to parse."""
    from sync.signals.generated import symbols as stainless_python
    from sync.signals.generated import symbols_typescript as stainless_typescript

    with pytest.raises(stainless_python.UnrecognisedSdkShape):
        stainless_python.extract_symbols(SDK)
    with pytest.raises(stainless_typescript.UnrecognisedSdkShape):
        stainless_typescript.extract_symbols(SDK)


def test_both_stainless_flavours_still_read_their_own_sdks():
    """The two finished rules are untouched by this one, and this is what says so."""
    from sync.signals.generated import symbols as stainless_python
    from sync.signals.generated import symbols_typescript as stainless_typescript

    assert stainless_python.extract_symbols(FIXTURES / "anthropic_python")[0]
    assert stainless_typescript.extract_symbols(FIXTURES / "anthropic_typescript")[0]


def test_a_stainless_sdk_handed_to_this_rule_fails_loudly():
    """The mirror. A Stainless checkout carries no class extending `ClientSDK`."""
    with pytest.raises(UnrecognisedSdkShape, match=GENERATOR):
        extract_symbols(FIXTURES / "anthropic_typescript")


def test_the_adapter_resolves_a_speakeasy_symbol(tmp_path):
    from sync.signals.generated.adapter import GeneratedSpecAdapter

    adapter = GeneratedSpecAdapter(
        vendor_id="vercel",
        sources={},
        fetch=lambda url: "",
        cache_dir=tmp_path,
        sdk_source=SDK,
        sdk_spec_operations=SPEC_OPERATIONS,
        sdk_source_generator=GENERATOR,
    )

    found = adapter.operation_for_symbol("vercel.aliases.getAlias", language="typescript")

    assert found is not None
    assert (found.http_method, found.path) == ("get", "/v4/aliases/{idOrAlias}")


def test_a_symbol_the_sdk_does_not_contain_resolves_to_nothing(tmp_path):
    from sync.signals.generated.adapter import GeneratedSpecAdapter

    adapter = GeneratedSpecAdapter(
        vendor_id="vercel",
        sources={},
        fetch=lambda url: "",
        cache_dir=tmp_path,
        sdk_source=SDK,
        sdk_source_generator=GENERATOR,
    )

    assert adapter.operation_for_symbol("vercel.aliases.notAMethod") is None
    assert adapter.operation_for_symbol("vercel.projects.getProject") is None


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
