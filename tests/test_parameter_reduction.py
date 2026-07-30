"""What the parameter reduction absorbs, and what it would absorb that it must not.

Both TypeScript flavours reduce every brace-delimited span of a route to a bare `{}` before
comparing an SDK's routes against the specification's -- `_PARAMETER.sub("{}", route)`, defined
identically in `symbols_typescript.py` and `symbols_speakeasy.py`. That absorbs the difference
between `${modelID}` and `{model_id}`, which is one route spelled by two generators from one
document and is exactly what the reduction exists for.

`2026-07-29-typescript-symbol-reader.md` left it as the module's one residual wrong-binding path:

    One residual wrong-binding path exists -- an SDK interpolating a non-parameter where the spec
    writes one -- but that is the documented `_PARAMETER` reduction shared with Speakeasy, not this
    reading.

This file is what happens when that is constructed rather than reasoned about, and the answer
narrows the claim. The reduction is not on the binding path at all: `operation_for_symbol` returns
the SDK's route verbatim and never calls `_comparable`, so a collision cannot resolve a call site
to another operation. What a collision reaches is the **cross-check** -- the thing
`symbols.py` calls "what makes the result refutable" -- and the coverage denominator counted
through it. Both fail silently, and `2026-07-29-parameter-reduction-collisions.md` carries the
measurement and the argument.

Three things are held here, and they are different kinds of claim:

- **The reduction is injective over every real specification available**, so the collision is a
  latent shape rather than a live defect. That is a measurement, pinned per vendor, and it goes red
  the day a pinned document stops having that property.
- **What a collision does today, asserted** -- because it is silent, and a silent behaviour nobody
  has written down is one the next reader has to rediscover.
- **The Speakeasy flavour's reduction is inert in outcome**, which its own `_PARAMETER` comment
  claims from a measurement taken once against one checkout. Pinned so the day that generator's
  spelling stops agreeing with the document it generated from is a red test.
"""

from __future__ import annotations

import collections
import json
import re
from pathlib import Path

import pytest

from sync.signals.generated import symbols_speakeasy, symbols_typescript
from sync.signals.generated.symbols import _route, read_spec_operations

FIXTURES = Path(__file__).parent / "fixtures" / "sdk_sources"
ANTHROPIC_SPEC = FIXTURES / "anthropic_spec_operations.json"
VERCEL_SPEC = FIXTURES / "vercel_spec_operations.json"
VERCEL_SDK = FIXTURES / "vercel_typescript"

# Not committed -- 7.8 MB apiece, fetched by `scripts/fetch_measurement_inputs.py` and gitignored
# for the reason that script's docstring gives. The tests reading them skip when they are absent,
# because a checkout that has not fetched them is the ordinary case and must not go red for it.
STRIPE_SPECS = tuple(Path(".cache/specs") / f"{tag}.json" for tag in ("v2320", "v2330"))

_HTTP_METHODS = frozenset(
    {"get", "post", "put", "patch", "delete", "head", "options", "trace"}
)


def _spec_entries(path: Path) -> list[tuple[str, str]]:
    """The `(method, path)` pairs a committed operation-set fixture lists, with duplicates kept.

    `read_spec_operations` returns a set, which is what the cross-check wants and is the wrong
    input for counting a collision: the multiplicity is the thing being measured.
    """
    return [
        (entry["method"], entry["path"])
        for entry in json.loads(path.read_text(encoding="utf-8"))
    ]


def _openapi_entries(path: Path) -> list[tuple[str, str]]:
    """The same pairs, read out of a whole OpenAPI document."""
    document = json.loads(path.read_text(encoding="utf-8"))
    return [
        (method, route)
        for route, item in document["paths"].items()
        for method in item
        if method.lower() in _HTTP_METHODS
    ]


def _collisions(
    entries: list[tuple[str, str]], comparable
) -> dict[tuple[str, str], set[tuple[str, str]]]:
    """Every comparable key with more than one distinct route behind it.

    Distinct *after* `_route`, so the query marker this project already drops on both sides is not
    counted as a collision -- that reduction is deliberate, measured, and not what this is about.
    What is left is exactly what the parameter reduction merged.
    """
    behind: dict[tuple[str, str], set[tuple[str, str]]] = collections.defaultdict(set)
    for method, route in entries:
        behind[comparable(method, route)].add(_route(method, route))
    return {key: routes for key, routes in behind.items() if len(routes) > 1}


# --- the reduction is one rule written twice ------------------------------------------------


def test_both_flavours_reduce_a_parameter_the_same_way():
    """Two copies of one regex, and a measurement taken through either applies to both.

    They are deliberately not extracted -- the duplication is the signal, as both module
    docstrings argue -- but a copy that drifts silently would mean a collision count measured on
    one flavour saying nothing about the other, and `2026-07-29-typescript-symbol-reader.md`
    already records that fixing the reduction is a two-module change for this reason.
    """
    assert symbols_typescript._PARAMETER.pattern == symbols_speakeasy._PARAMETER.pattern
    assert symbols_typescript._comparable("get", "/v1/models/{model_id}") == (
        symbols_speakeasy._comparable("get", "/v1/models/{model_id}")
    )


# --- injectivity over every real specification available -----------------------------------


def test_the_reduction_collides_no_anthropic_operation():
    """131 published operations, 121 distinct routes once the `?beta=true` marker is dropped, and
    121 still after every parameter name is reduced to a placeholder.

    The second number and the third being equal is the claim: the parameter reduction merges
    nothing in this document. The ten operations lost between the first and the second are the
    query marker's, and each is a `?beta=true` twin of a route already listed -- `_route`'s own
    documented reduction, not this one.
    """
    entries = _spec_entries(ANTHROPIC_SPEC)
    routed = {_route(method, route) for method, route in entries}
    reduced = {symbols_typescript._comparable(method, route) for method, route in entries}

    assert len(entries) == 131
    assert len(routed) == 121
    assert len(reduced) == 121
    assert _collisions(entries, symbols_typescript._comparable) == {}


def test_the_reduction_collides_no_vercel_operation():
    """359 operations, and the reduction merges none of them either.

    Unlike the Anthropic document this one carries no query markers at all, so all three counts
    agree and the reduction is the only thing that could have moved the number.
    """
    entries = _spec_entries(VERCEL_SPEC)
    routed = {_route(method, route) for method, route in entries}
    reduced = {symbols_speakeasy._comparable(method, route) for method, route in entries}

    assert len(entries) == 359
    assert len(routed) == 359
    assert len(reduced) == 359
    assert _collisions(entries, symbols_speakeasy._comparable) == {}


@pytest.mark.parametrize("spec", STRIPE_SPECS, ids=lambda path: path.stem)
def test_the_reduction_collides_no_stripe_operation(spec: Path):
    """The same measurement over a document an order of magnitude larger, and a vendor neither
    flavour reads.

    Stripe has a hand-written adapter, so its SDK never reaches this reduction. It is here because
    the claim being tested is about the reduction against a *specification*, and 587 operations
    over 414 paths is the largest real document this repository pins. A rule that is injective over
    490 operations and not over 587 would be a rule holding by luck.
    """
    if not spec.exists():
        pytest.skip(f"{spec} is gitignored; run scripts/fetch_measurement_inputs.py to include it")

    entries = _openapi_entries(spec)

    assert len(entries) == 587
    assert _collisions(entries, symbols_typescript._comparable) == {}


def test_the_collision_measurement_can_fail():
    """The three tests above assert an absence, and an absence is where a measurement rots.

    A reduction that merged two paths differing only in the *number* of parameters would collide
    these two, and the counting above must see it. Without this, `_collisions` returning `{}`
    unconditionally would satisfy every assertion in this section.
    """
    entries = [("GET", "/v1/{a}/x"), ("GET", "/v1/{a}/{b}/x")]
    greedy = lambda method, route: (method.upper(), re.sub(r"\{.*\}", "{}", route))  # noqa: E731

    assert _collisions(entries, symbols_typescript._comparable) == {}
    assert _collisions(entries, greedy) == {
        ("GET", "/v1/{}/x"): {("GET", "/v1/{a}/x"), ("GET", "/v1/{a}/{b}/x")}
    }


# --- what a collision does today, constructed rather than reasoned about --------------------


def test_two_specification_operations_behind_one_key_deflate_the_denominator(tmp_path):
    """The collision constructed, and the reader neither picks one nor declines: it never sees it.

    `report_extraction` builds `declared` as a **set** of comparable keys, so two specification
    operations reducing to one key are one member. Nothing chooses between them and nothing reports
    that a choice was available -- the denominator is simply one smaller than the number of
    operations the vendor published, and the coverage ratio is taken against it.

    That makes the visible harm a wrong *measurement* rather than a wrong binding. An SDK reaching
    both readable operations here reports 100% of an API it reaches two thirds of, and every number
    in the line is internally consistent, which is what makes it unreadable as a warning.
    """
    root = _sdk(tmp_path, "  members() { return this._client.get(path`/v1/${workspaceID}/members`, {}); }")
    spec = _spec(
        tmp_path,
        ("GET", "/v1/models"),
        ("GET", "/v1/{workspace_id}/members"),
        ("GET", "/v1/{organization_id}/members"),
    )

    report = symbols_typescript.report_extraction(root, read_spec_operations(spec))

    assert len(_spec_entries(spec)) == 3
    assert report.spec_operation_count == 2
    assert report.covered_count == 2
    assert report.coverage_ratio == 1.0
    assert "reaching 2 of 2 specification operations (100.0%)" in report.render()


def test_a_collision_is_reported_nowhere(tmp_path):
    """And the other half: no decline, no warning, no field.

    `ExtractionReport` carries `operations`, `spec_operation_count`, `unknown_to_spec` and
    `covered_count`, and a collision moves only the two counts. `unknown_to_spec` is the one loud
    channel this module has where a specification is staged, and a collision cannot reach it --
    the SDK's route *did* match a declared key, so there is nothing for it to report.

    This is why the deliverable for this task is a measurement rather than a repair: the condition
    is silent, so what protects against it is a test over the real documents, not a branch that
    fires on input nobody has.
    """
    root = _sdk(tmp_path, "  members() { return this._client.get(path`/v1/${workspaceID}/members`, {}); }")
    spec = _spec(
        tmp_path,
        ("GET", "/v1/models"),
        ("GET", "/v1/{workspace_id}/members"),
        ("GET", "/v1/{organization_id}/members"),
    )

    report = symbols_typescript.report_extraction(root, read_spec_operations(spec))

    assert report.unknown_to_spec == ()
    assert not hasattr(report, "declined")


# --- the residual path the earlier report named, and what it actually costs -----------------


def test_the_intended_absorption_and_the_residual_path_are_one_shape():
    """Why this is not repairable in `_comparable`, stated as the two inputs rather than argued.

    `${modelID}` against the specification's `{model_id}` is the difference the reduction exists to
    absorb. `${this.channel}` against `{api_version}` is an SDK interpolating a value that is not a
    path parameter into a position where the specification writes one -- the residual path
    `2026-07-29-typescript-symbol-reader.md` named. Both are a brace span in the same position, and
    they reduce to the same key.

    Separating them means deciding which brace spans hold parameter names, which is a rule about a
    vendor's SDK conventions and belongs in an adapter rather than in a reduction two generators
    share. So the reduction cannot be narrowed here without guessing, and the residual path is a
    documented cost rather than a defect with a fix in this module.
    """
    intended = symbols_typescript._comparable("get", "/v1/models/{modelID}")
    residual = symbols_typescript._comparable("get", "/v1/models/{this.channel}")
    declared = symbols_typescript._comparable("GET", "/v1/models/{model_id}")

    assert intended == declared
    assert residual == declared


def test_an_sdk_interpolating_a_non_parameter_is_affirmed_by_the_cross_check(tmp_path):
    """The residual path constructed. `${this.channel}` is a segment chosen at runtime, not a path
    parameter, and the reduction makes it equal to the specification's `{api_version}`.

    What that costs is the cross-check's verdict on this route, and the verdict is the wrong one:
    the specification declares no route the SDK sends, and `unknown_to_spec` says it declares one.
    `symbols.py` calls the cross-check "what makes the result refutable", and this is the input on
    which it stops refuting -- silently, because affirmation is the quiet answer.
    """
    root = _sdk(tmp_path, "  pinned() { return this._client.get(path`/v1/${this.channel}/models`, {}); }")
    spec = _spec(tmp_path, ("GET", "/v1/models"), ("GET", "/v1/{api_version}/models"))

    report = symbols_typescript.report_extraction(root, read_spec_operations(spec))

    assert {operation.symbol: operation.path for operation in report.operations} == {
        "models.list": "/v1/models",
        "models.pinned": "/v1/{this.channel}/models",
    }
    assert report.unknown_to_spec == ()
    assert report.covered_count == 2


def test_the_same_route_is_reported_when_the_specification_parameterises_nothing(tmp_path):
    """The control, and it is what makes the test above mean something.

    The identical SDK against a specification that writes no parameter in that position reports the
    route. So the affirmation is produced by the reduction meeting a parameterised specification
    route, not by `/v1/{this.channel}/models` being a route the cross-check finds unremarkable.
    """
    root = _sdk(tmp_path, "  pinned() { return this._client.get(path`/v1/${this.channel}/models`, {}); }")
    spec = _spec(tmp_path, ("GET", "/v1/models"))

    report = symbols_typescript.report_extraction(root, read_spec_operations(spec))

    assert [operation.symbol for operation in report.unknown_to_spec] == ["models.pinned"]


def test_the_reduction_is_not_on_the_path_a_call_site_resolves_through(tmp_path):
    """And the reason none of this is a wrong binding, asserted at the place a binding is made.

    `operation_for_symbol` builds its `OperationRef` from `ExtractedOperation.path`, which is the
    SDK's route verbatim -- the reduction is applied only inside `report_extraction`, to decide
    membership of a set. So the colliding key never reaches a `call_site` row: the symbol resolves
    to what the SDK sends, which is what the whole extraction argument rests on.

    This is what narrows the earlier report's claim. A collision costs a measurement and a
    cross-check verdict; it cannot attach a vendor change to a call site that does not call it.
    """
    from sync.signals.generated.adapter import GeneratedSpecAdapter

    root = _sdk(tmp_path, "  pinned() { return this._client.get(path`/v1/${this.channel}/models`, {}); }")
    spec = _spec(tmp_path, ("GET", "/v1/models"), ("GET", "/v1/{api_version}/models"))
    adapter = GeneratedSpecAdapter(
        vendor_id="anthropic", sources={}, fetch=_never_fetch, cache_dir=tmp_path,
        sdk_source=root, sdk_spec_operations=spec,
        sdk_source_generator=symbols_typescript.GENERATOR,
    )

    reference = adapter.operation_for_symbol("anthropic.models.pinned", language="typescript")

    assert reference is not None
    assert reference.path == "/v1/{this.channel}/models"
    assert reference.operation_id == "GET /v1/{this.channel}/models"


# --- the absorption the reduction exists for still works ------------------------------------


def test_a_parameter_spelled_differently_on_each_side_still_covers_its_operation():
    """The other direction, and the guard against over-correcting this.

    `symbols_typescript`'s reason for existing is that Stainless writes `${modelID}` where the
    specification writes `{model_id}`. Five of this fixture's twelve symbols carry a parameter and
    they reach four distinct comparable keys, and every one of those keys must be counted as covered
    -- a reduction narrowed until it declined a colliding key would decline all four, and the
    cross-check would report the SDK disagreeing with the document it was generated from on a third
    of its symbols.
    """
    spec = read_spec_operations(ANTHROPIC_SPEC)
    report = symbols_typescript.report_extraction(FIXTURES / "anthropic_typescript", spec)
    parameterised = [
        operation for operation in report.operations if "{" in operation.path
    ]
    keys = {
        symbols_typescript._comparable(operation.http_method, operation.path)
        for operation in parameterised
    }

    assert len(parameterised) == 5
    assert len(keys) == 4
    assert keys <= {symbols_typescript._comparable(method, route) for method, route in spec}
    assert report.unknown_to_spec == ()
    assert report.covered_count == 10


# --- the Speakeasy flavour's reduction is inert, and stays measured ------------------------


def test_the_speakeasy_reduction_changes_no_verdict(monkeypatch):
    """`_PARAMETER`'s comment in `symbols_speakeasy.py` claims this from a measurement taken once
    against one checkout of one SDK, and nothing held it.

    Inert means inert *in outcome*, not unused: the reduction rewrites eight of this SDK's fifteen
    routes and 258 of the specification's 359. What makes it inert is that Speakeasy writes the
    document's own parameter names through unchanged, so reducing both sides moves no route into or
    out of the declared set. Disabling it therefore has to produce the same four numbers, and the
    day this generator's spelling stops agreeing with the document it generated from is the day this
    goes red -- which is the condition the comment keeps it for.
    """
    spec = read_spec_operations(VERCEL_SPEC)
    with_reduction = symbols_speakeasy.report_extraction(VERCEL_SDK, spec)

    monkeypatch.setattr(symbols_speakeasy, "_PARAMETER", re.compile(r"(?!)"))
    without_reduction = symbols_speakeasy.report_extraction(VERCEL_SDK, spec)

    assert without_reduction.spec_operation_count == with_reduction.spec_operation_count == 359
    assert without_reduction.covered_count == with_reduction.covered_count == 15
    assert without_reduction.unknown_to_spec == with_reduction.unknown_to_spec == ()
    assert without_reduction.operations == with_reduction.operations


def test_the_speakeasy_reduction_is_inert_rather_than_unreached():
    """The non-vacuity of the test above, and the thing that makes it a measurement.

    A reduction that matched nothing would satisfy every assertion there while proving nothing. It
    fires on most of both artifacts, and the verdicts still agree, which is the claim.
    """
    operations = symbols_speakeasy.extract_symbols(VERCEL_SDK)
    rewritten = [
        operation
        for operation in operations
        if symbols_speakeasy._comparable(operation.http_method, operation.path)
        != _route(operation.http_method, operation.path)
    ]
    declared = _spec_entries(VERCEL_SPEC)
    rewritten_declared = [
        (method, route)
        for method, route in declared
        if symbols_speakeasy._comparable(method, route) != _route(method, route)
    ]

    assert len(rewritten) == 8
    assert len(rewritten_declared) == 258


def test_the_overlay_the_speakeasy_reduction_is_kept_for_is_declared_by_this_vendor():
    """Whether the condition the reduction is kept for is a real one for this generator.

    It is. `vercel/sdk`'s own workflow applies an overlay to the specification before generating, so
    the document this cross-check reads is not the document the SDK was generated from, and an
    overlay renaming a path parameter would put every affected route on the wrong side of the
    comparison. The mechanism is declared here rather than imagined for the generator.

    What the overlay actually does is not readable from what is committed -- only `workflow.yaml` is,
    and its filename is the only thing that says "title". The evidence that it renames no path
    parameter is the agreement itself, held by the test above: all fifteen routes resolve to routes
    the fetched document declares. So the case is reachable in mechanism and unexercised in effect.
    """
    import yaml

    manifest = yaml.safe_load(
        (FIXTURES / "vercel_typescript.workflow.yaml").read_text(encoding="utf-8")
    )
    overlays = [
        entry["location"]
        for source in manifest["sources"].values()
        for entry in source.get("overlays", ())
    ]

    assert overlays == ["overlay-title.yaml"]


def _never_fetch(url: str) -> str:
    raise AssertionError("symbol extraction must not reach a network")


def _sdk(tmp_path: Path, *methods: str) -> Path:
    """Three files of the shape the Stainless TypeScript rule reads, with `models.list` readable.

    Hand-written rather than cut from the committed Anthropic tree, because the routes these tests
    need are ones Stainless does not emit -- corrupting the fixture into them would make the
    corruption the fixture. `models.list` is always readable so that an assertion about a second
    operation cannot pass because the whole SDK failed to parse.
    """
    root = tmp_path / "sdk"
    files = {
        "client.ts": (
            "import * as API from './resources/index';\n"
            "\n"
            "export class Anthropic extends BaseAnthropic {\n"
            "  models: API.Models = new API.Models(this);\n"
            "}\n"
        ),
        "resources/index.ts": "export { Models } from './models';\n",
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


def _spec(tmp_path: Path, *operations: tuple[str, str]) -> Path:
    """An operation-set file of the shape `read_spec_operations` reads."""
    destination = tmp_path / "spec_operations.json"
    destination.write_text(
        json.dumps([{"method": method, "path": route} for method, route in operations]),
        encoding="utf-8",
    )
    return destination
