"""What `ExtractionReport`'s numbers count, and what a decline reaches.

Two findings against a class three flavours share, closed together because both change what its
numbers mean.

**The denominator was counted in comparable keys rather than in specification operations.**
`2026-07-29-parameter-reduction-collisions.md` constructed the cost: two specification operations
behind one comparable key are one member of a set, so a vendor publishing three operations got a
denominator of two, and an SDK reaching two of them read 100%. Every number in that line was
internally consistent with every other, which is what made it unreadable as a warning.

**Every decline in these readers was silent.** `2026-07-29-typescript-symbol-reader.md`,
`2026-07-29-hand-written-symbol-maps.md` and `2026-07-29-python-flavour-and-literals.md` tabled
every declining branch across four readers and found one shape in each: a construct the rule met
and could not read costs a symbol or a whole subtree, and nothing downstream learns it happened.

`2026-07-29-extraction-report-contract.md` carries the design both closures rest on -- which
counts became two fields, why the retired name is not reused, and which declines are recorded
rather than all of them.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from sync.signals.generated import symbols, symbols_speakeasy, symbols_typescript
from sync.signals.generated.manifest import STAINLESS_MANIFEST, parse_manifest
from sync.signals.generated.symbols import read_spec_operations

FIXTURES = Path(__file__).parent / "fixtures" / "sdk_sources"
MANIFESTS = Path(__file__).parent / "fixtures" / "manifests"

ANTHROPIC_SPEC = FIXTURES / "anthropic_spec_operations.json"
VERCEL_SPEC = FIXTURES / "vercel_spec_operations.json"

PYTHON_SDK = FIXTURES / "anthropic_python"
TYPESCRIPT_SDK = FIXTURES / "anthropic_typescript"
SPEAKEASY_SDK = FIXTURES / "vercel_typescript"


# --- the denominator, and the collision it used to hide -------------------------------------


def test_two_specification_operations_behind_one_key_no_longer_deflate_the_denominator(tmp_path):
    """M3-W96's own constructed input, which reported 100% of an API it reaches two thirds of.

    Three operations, two of which reduce to `(GET, /v1/{}/members)` under the parameter
    reduction. The old field counted the reduced set and answered 2, so the line read
    `2 of 2 specification operations (100.0%)` -- consistent, and wrong about the API's size.

    The two counts are now separate facts. The specification declares three operations; the
    comparison can be made against two keys; and the gap between them is one operation whose
    coverage this comparison cannot attribute either way.
    """
    root = _sdk(tmp_path, "  members() { return this._client.get(path`/v1/${workspaceID}/members`, {}); }")
    spec = _spec(
        tmp_path,
        ("GET", "/v1/models"),
        ("GET", "/v1/{workspace_id}/members"),
        ("GET", "/v1/{organization_id}/members"),
    )

    report = symbols_typescript.report_extraction(root, read_spec_operations(spec))

    assert report.declared_operation_count == 3
    assert report.comparable_key_count == 2
    assert report.indistinct_operation_count == 1
    assert report.covered_count == 2


def test_the_collision_is_a_number_in_the_line_an_operator_reads(tmp_path):
    """The same input, through the one artifact that reaches an operator.

    A ratio of 100% is not wrong -- the extraction does reach both keys the comparison can be
    made against -- so what was needed was not a smaller ratio but the sentence beside it. The
    line now says what the ratio is a ratio of, and names the operation the reduction absorbed.
    """
    root = _sdk(tmp_path, "  members() { return this._client.get(path`/v1/${workspaceID}/members`, {}); }")
    spec = _spec(
        tmp_path,
        ("GET", "/v1/models"),
        ("GET", "/v1/{workspace_id}/members"),
        ("GET", "/v1/{organization_id}/members"),
    )

    line = symbols_typescript.report_extraction(root, read_spec_operations(spec)).render()

    assert "reaching 2 of 2 comparable routes (100.0%)" in line
    assert "the specification declares 3 operations, 1 of them not separately comparable" in line


def test_the_retired_name_is_gone_rather_than_carrying_a_new_meaning():
    """`spec_operation_count` answered "how many comparable keys" while claiming to answer "how
    many specification operations". Both replacements say which they are.

    The name is not reused for the corrected quantity. A field whose meaning changed under a name
    that did not would give every existing reader a different number with no error, where a name
    that is gone raises `AttributeError` at the first stale read.
    """
    report = symbols.report_extraction(PYTHON_SDK, read_spec_operations(ANTHROPIC_SPEC))

    assert not hasattr(report, "spec_operation_count")
    assert report.declared_operation_count == 131
    assert report.comparable_key_count == 121


def test_the_operation_count_is_the_number_this_sdks_own_manifest_publishes():
    """Two independently published artifacts agreeing, which is what the old count could not do.

    Stainless writes `configured_endpoints` into the manifest it commits, and the operation set
    of the specification that manifest names holds the same number. The old field answered 121 --
    the routes those 131 operations reduce to once the query marker is dropped -- so the one
    cross-check available on the denominator could not be made at all.

    Both flavours' manifests are read, because one specification generated both SDKs and a
    denominator that agreed with only one of them would mean the fixtures had drifted apart.
    """
    published = [
        parse_manifest(STAINLESS_MANIFEST, path.read_text(encoding="utf-8")).endpoint_count
        for path in (MANIFESTS / "anthropic.stats.yml", FIXTURES / "anthropic_typescript.stats.yml")
    ]

    for flavour, root in ((symbols, PYTHON_SDK), (symbols_typescript, TYPESCRIPT_SDK)):
        report = flavour.report_extraction(root, read_spec_operations(ANTHROPIC_SPEC))
        assert report.declared_operation_count == 131
        assert published == [131, 131]


def test_a_generator_publishing_no_endpoint_count_leaves_the_denominator_unchecked():
    """The other generator, and the reason the comparison is a test rather than a runtime check.

    A Speakeasy `workflow.yaml` declares its inputs and not its size, so `endpoint_count` is
    `None` for every vendor under it and there is no second artifact to agree with. The
    extraction still reports both counts; nothing compares them to a published figure, and
    nothing pretends to.
    """
    manifest = yaml.safe_load(
        (FIXTURES / "vercel_typescript.workflow.yaml").read_text(encoding="utf-8")
    )
    assert "configured_endpoints" not in manifest

    report = symbols_speakeasy.report_extraction(SPEAKEASY_SDK, read_spec_operations(VERCEL_SPEC))

    assert report.declared_operation_count == 359
    assert report.comparable_key_count == 359
    assert report.indistinct_operation_count == 0


def test_the_ratio_is_taken_against_the_keys_it_is_counted_in():
    """`covered_count` is a count of comparable routes, so the operation count cannot be its
    denominator without mixing two units.

    The temptation is the honest-looking one: 10 of 131 reads like coverage of the vendor's API,
    and 10 of 121 reads like coverage of a reduction nobody outside this module cares about. It
    would be a ratio of routes to operations, which is a number that gets smaller when the query
    marker is dropped on both sides and means nothing either way. The operation count travels
    beside the ratio instead.
    """
    report = symbols.report_extraction(PYTHON_SDK, read_spec_operations(ANTHROPIC_SPEC))

    assert report.covered_count == 10
    assert report.coverage_ratio == report.covered_count / report.comparable_key_count
    assert report.coverage_ratio != report.covered_count / report.declared_operation_count


def test_an_empty_specification_still_says_zero_of_zero(tmp_path):
    """M3-W97 established that an empty specification and a fully missed one both answer exactly
    `0.0`, and that the distinction survives only because `render()` puts the denominator beside
    it. A line carrying two denominators must keep that legible."""
    empty = _spec(tmp_path)

    report = symbols.report_extraction(PYTHON_SDK, read_spec_operations(empty))
    line = report.render()

    assert report.coverage_ratio == 0.0
    assert "reaching 0 of 0 comparable routes (0.0%)" in line
    assert "the specification declares 0 operations" in line


def test_all_three_flavours_render_a_line_carrying_both_counts():
    """The contract is shared, so a change to it is a change to three rules. Each names itself
    and each carries the same two denominators."""
    lines = {
        flavour.GENERATOR: flavour.report_extraction(root, read_spec_operations(spec)).render()
        for flavour, root, spec in (
            (symbols, PYTHON_SDK, ANTHROPIC_SPEC),
            (symbols_typescript, TYPESCRIPT_SDK, ANTHROPIC_SPEC),
            (symbols_speakeasy, SPEAKEASY_SDK, VERCEL_SPEC),
        )
    }

    assert set(lines) == {"stainless-python", "stainless-typescript", "speakeasy-typescript"}
    for generator, line in lines.items():
        assert line.startswith(f"{generator}:")
        assert "comparable routes" in line
        assert "the specification declares" in line


def test_the_golden_tool_schemas_did_not_move():
    """`severity` and `Finding` reach the MCP surface and those four schemas are frozen. Nothing
    here touches either, and this is the assertion rather than the claim."""
    from sync.mcp.registry import schemas_as_data

    golden = json.loads(
        (Path(__file__).parent / "golden" / "tool_schemas.json").read_text(encoding="utf-8")
    )

    assert schemas_as_data() == golden


# --- fixtures written by hand, because these shapes are not what a generator emits -----------


def _sdk(tmp_path: Path, *methods: str) -> Path:
    """Three files of the shape the Stainless TypeScript rule reads, with `models.list` readable.

    The same construction `tests/test_parameter_reduction.py` uses, and hand-written for the same
    reason: the routes these tests need are ones Stainless does not emit, so corrupting the
    committed tree into them would make the corruption the fixture. `models.list` is always
    readable, so an assertion about a second operation cannot pass because the whole SDK failed
    to parse.
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
