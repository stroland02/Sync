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
