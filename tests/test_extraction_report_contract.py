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


# --- the decline channel: what it records, and what it deliberately does not ----------------


def test_the_channel_is_the_second_half_of_the_pair_and_present_when_empty(tmp_path):
    """`IntakeReport.unreadable`'s shape, carried here rather than a fourth one invented.

    `read_declared_dependencies` returns `(declared, unreadable)` and `parse_directory` returns
    `(entries, faults)`; `extract_symbols` now returns `(operations, unreadable)`. A tuple of
    prose strings, second in the pair, present and empty on a clean read.
    """
    root = _python_sdk(
        tmp_path,
        """
        class Models(SyncAPIResource):
            def list(self):
                return self._get_api_list("/v1/models")

        class Acme(SyncAPIClient):
            @cached_property
            def models(self) -> Models:
                ...
        """,
    )

    operations, unreadable = symbols.extract_symbols(root)

    assert [operation.symbol for operation in operations] == ["models.list"]
    assert unreadable == ()


def test_a_mount_whose_annotation_names_no_class_this_rule_can_read_is_recorded(tmp_path):
    """`-> Optional[Messages]`. `_annotation_name` declines a subscript rather than mounting its
    base, which is right -- guessing would mount a resource under a chain the customer may not be
    able to write -- and until now the whole subtree simply vanished.

    The blast radius is what makes this worth a record: `messages.create` is absent from the map,
    every call site on it resolves to nothing, and no finding can be raised against it however
    breaking the vendor's change.
    """
    root = _python_sdk(
        tmp_path,
        """
        class Messages(SyncAPIResource):
            def create(self):
                return self._post("/v1/messages")

        class Acme(SyncAPIClient):
            @cached_property
            def messages(self) -> Optional[Messages]:
                ...
        """,
    )

    operations, unreadable = symbols.extract_symbols(root)

    assert operations == ()
    assert unreadable == (
        "stainless-python: _client.py: Acme.messages is a cached_property whose return "
        "annotation names no class this rule can read, so the resource it mounts and every "
        "operation under it is absent",
    )


def test_a_mount_naming_a_class_this_checkout_does_not_declare_is_recorded(tmp_path):
    """The annotation names a class and no file here declares one by that name. A different
    repair from the one above -- that one wants the rule taught a spelling, this one wants the
    file staged -- so it is a different message.

    `models` is readable beside it, so the extraction still roots and the assertion cannot pass
    because the whole SDK failed to parse.
    """
    root = _python_sdk(
        tmp_path,
        """
        class Models(SyncAPIResource):
            def list(self):
                return self._get_api_list("/v1/models")

        class Acme(SyncAPIClient):
            @cached_property
            def models(self) -> Models:
                ...

            @cached_property
            def messages(self) -> Messages:
                ...
        """,
    )

    operations, unreadable = symbols.extract_symbols(root)

    assert [operation.symbol for operation in operations] == ["models.list"]
    assert unreadable == (
        "stainless-python: _client.py: Acme.messages mounts 'Messages', which this checkout does "
        "not declare, so that resource and every operation under it is absent",
    )


def test_an_operation_whose_route_this_rule_cannot_read_is_recorded(tmp_path):
    """`self._post(**kwargs)` -- the verb stated, the route not.

    Declining is right and M3-W97 argued why: the route is the first positional argument and
    there is no second source, so recording the verb alone would put a symbol in the map with no
    route to match a vendor change against. What was missing is that the method contributing no
    symbol reached nobody, while the operation beside it kept the coverage number plausible.
    """
    root = _python_sdk(
        tmp_path,
        """
        class Messages(SyncAPIResource):
            def create(self, **kwargs):
                return self._post(**kwargs)

            def count_tokens(self):
                return self._post("/v1/messages/count_tokens")

        class Acme(SyncAPIClient):
            @cached_property
            def messages(self) -> Messages:
                ...
        """,
    )

    operations, unreadable = symbols.extract_symbols(root)

    assert [operation.symbol for operation in operations] == ["messages.count_tokens"]
    assert unreadable == (
        "stainless-python: _client.py: Messages.create calls self._post with no route this rule "
        "can read, so it contributes no symbol",
    )


def test_the_wrapper_mounts_every_stainless_client_writes_are_not_recorded(tmp_path):
    """The bound on what the channel holds, and it is what makes the channel worth reading.

    `Anthropic.with_raw_response -> AnthropicWithRawResponse` is a `cached_property` mounting a
    class that does not derive `SyncAPIResource`, so the mount is not an edge -- which is right
    and is the module docstring's own argument: the wrappers are the same operations reached
    differently and counting them would inflate coverage. The committed Anthropic tree writes
    **eleven** of them across its five files, so a channel recording every unresolved mount would
    put eleven expected entries in front of the one that matters.

    What separates them is asked of the source rather than of a naming convention: a wrapper is a
    class this checkout **declares**, and an unstaged resource is a name nothing here declares at
    all. Naming the wrapper suffixes instead would put a generator's spelling in the rule that
    the base-class check deliberately excludes them without needing.
    """
    root = _python_sdk(
        tmp_path,
        """
        class Messages(SyncAPIResource):
            def create(self):
                return self._post("/v1/messages")

            def _validate(self, payload):
                return bool(payload)

        class AsyncMessages(AsyncAPIResource):
            def create(self):
                return self._post("/v1/messages")

        class AcmeWithRawResponse:
            def __init__(self, client):
                self._client = client

        class Acme(SyncAPIClient):
            @cached_property
            def messages(self) -> Messages:
                ...

            @cached_property
            def with_raw_response(self) -> AcmeWithRawResponse:
                ...
        """,
    )

    operations, unreadable = symbols.extract_symbols(root)

    assert [operation.symbol for operation in operations] == ["messages.create"]
    assert unreadable == ()


def test_the_committed_anthropic_tree_records_its_two_real_losses():
    """Both kinds, on real vendor source, and neither was visible before.

    **The uncommitted `beta/` tree.** `Anthropic.beta` is annotated `-> Beta` and no file here
    declares that class, because the fixture leaves the tree out -- it carries 113 of the SDK's
    131 operations. The README states that in prose; nothing in the extraction said it.

    **`messages.batches.results`.** The vendor writes
    `self._get(path_template(batch.results_url, ...))`, so the route comes from a field of an
    earlier response and no literal states it. Declining is right -- there is no second source
    for a route -- but the specification *does* declare
    `GET /v1/messages/batches/{message_batch_id}/results`, so the map is missing a symbol for an
    operation both artifacts agree exists, and the coverage line read as a smaller SDK.
    """
    operations, unreadable = symbols.extract_symbols(PYTHON_SDK)

    assert len(operations) == 11
    assert unreadable == (
        "stainless-python: _client.py: Anthropic.beta mounts 'Beta', which this checkout does not "
        "declare, so that resource and every operation under it is absent",
        "stainless-python: resources/messages/batches.py: Batches.results calls self._get with no "
        "route this rule can read, so it contributes no symbol",
    )


def test_the_typescript_flavour_records_a_route_it_could_not_read(tmp_path):
    """`this._client.get()` -- a client call handed no arguments, which M3-W91 tabled at line 305
    and found silent. One symbol short, and the same rule the Python flavour applies."""
    root = _sdk(tmp_path, "  ping() { return this._client.get(); }")

    operations, unreadable = symbols_typescript.extract_symbols(root)

    assert [operation.symbol for operation in operations] == ["models.list"]
    assert unreadable == (
        "stainless-typescript: resources/models: Models.ping calls this._client.get with no "
        "route this rule can read, so it contributes no symbol",
    )


def test_the_typescript_flavour_records_a_mount_whose_module_is_not_here(tmp_path):
    """A mount reached through an alias naming a file this checkout does not contain, which is
    what the committed Anthropic tree does thirteen times under `Beta`.

    The mount is not an edge, which is right -- an unresolved name matched against a class of that
    name somewhere else is the wrong answer that resolves. What is new is a record naming the
    class and the module it was looked for in.

    `models` resolves beside it, so the extraction still roots: a mount decline that removed the
    last edge raises `UnrecognisedSdkShape` instead, and this channel is for the partial loss.
    """
    root = _sdk(
        tmp_path,
        client=(
            "import * as API from './resources/index';\n"
            "import * as BetaAPI from './resources/beta/beta';\n"
            "\n"
            "export class Anthropic extends BaseAnthropic {\n"
            "  models: API.Models = new API.Models(this);\n"
            "  beta: BetaAPI.Beta = new BetaAPI.Beta(this);\n"
            "}\n"
        ),
    )

    operations, unreadable = symbols_typescript.extract_symbols(root)

    assert [operation.symbol for operation in operations] == ["models.list"]
    assert unreadable == (
        "stainless-typescript: client: Anthropic.beta mounts 'Beta' through "
        "'resources/beta/beta', which declares no class of that name in this checkout, so that "
        "resource and every operation under it is absent",
    )


def test_the_typescript_flavour_records_the_beta_resources_the_fixture_omits():
    """The same two kinds on the committed tree, where `resources/beta/beta.ts` is present and
    the fourteen resources it mounts are not.

    `Batches.results` is here too, and that is the more interesting half: the Python and
    TypeScript SDKs lose the same operation for the same reason, one flavour reading
    `path_template(batch.results_url, ...)` and the other the tagged-template equivalent. Two
    independent rules agreeing about a loss is what makes it a fact about the vendor's SDK rather
    than about either reader.
    """
    operations, unreadable = symbols_typescript.extract_symbols(TYPESCRIPT_SDK)

    mounts = [record for record in unreadable if " mounts " in record]

    assert len(operations) == 12
    assert len(mounts) == 14
    assert len(unreadable) == 15
    assert (
        "stainless-typescript: resources/beta/beta: Beta.skills mounts 'Skills' through "
        "'resources/beta/skills/skills', which declares no class of that name in this checkout, "
        "so that resource and every operation under it is absent"
    ) in mounts
    assert (
        "stainless-typescript: resources/messages/batches: Batches.results calls "
        "this._client.get with no route this rule can read, so it contributes no symbol"
    ) in unreadable


def test_a_field_holding_something_this_sdk_does_not_declare_is_not_a_mount(tmp_path):
    """The other bound, and it is a real emission rather than a hypothetical.

    `client.ts` in the committed Anthropic tree writes
    `#requestAuthFlags = new WeakMap<...>()` -- a field initialised with `new`, holding a global,
    reached by exactly the code path a mount is. A channel recording every `new` it could not
    resolve to a class would report that on every extraction of every Stainless TypeScript SDK.

    What separates it from a missing resource is the module: an unstaged resource is looked for in
    a file this checkout does not contain, and `WeakMap` is looked for in a file it does contain
    and which declares no such class. TypeScript states the module at the mount, so this flavour
    asks the sharper question; the Python flavour has only a class name in an annotation and asks
    the weaker one.
    """
    root = _sdk(tmp_path, client_field="  private flags = new WeakMap();\n")

    operations, unreadable = symbols_typescript.extract_symbols(root)

    assert [operation.symbol for operation in operations] == ["models.list"]
    assert unreadable == ()


def test_the_speakeasy_flavour_records_what_the_truncated_fixture_leaves_out():
    """The committed `vercel/sdk` tree is deliberately partial: `sdk/sdk.ts` is whole with all 41
    of its mounts and eleven of its own delegations, while three of the resource classes and one
    of the eleven request modules are committed.

    Its README states that in prose -- "coverage measured against this fixture is a floor rather
    than the SDK's real figure" -- and until now nothing in the extraction said so. Both counts
    are pinned so the day the fixture grows or shrinks is a red test rather than a coverage
    number moving quietly.
    """
    operations, unreadable = symbols_speakeasy.extract_symbols(SPEAKEASY_SDK)

    mounts = [record for record in unreadable if " mounts " in record]
    delegations = [record for record in unreadable if "reaches no request module" in record]

    assert len(operations) == 15
    assert len(mounts) == 38
    assert len(delegations) == 10
    assert len(unreadable) == 48

    assert (
        "speakeasy-typescript: sdk/sdk: Vercel.deployments mounts 'Deployments' from "
        "'sdk/deployments', which this checkout does not contain, so that resource and every "
        "operation under it is absent"
    ) in mounts
    assert (
        "speakeasy-typescript: sdk/sdk: Vercel.createApiKeys reaches no request module -- "
        "'funcs/createApiKeys', 'types/fp' are not in this checkout -- so it contributes no symbol"
    ) in delegations


def test_the_count_travels_in_the_line_an_operator_reads(tmp_path):
    """A number nobody renders is a number nobody reads. The line already carried its
    denominators for the reason the module docstring gives, and the decline count belongs beside
    them: it is what says whether a small extraction is a small SDK or a rule meeting an emission
    it does not know.
    """
    root = _sdk(tmp_path, "  ping() { return this._client.get(); }")
    spec = _spec(tmp_path, ("GET", "/v1/models"))

    report = symbols_typescript.report_extraction(root, read_spec_operations(spec))

    assert len(report.unreadable) == 1
    assert "1 constructs this rule could not read" in report.render()


def test_a_speakeasy_getter_constructing_a_class_it_never_imported_is_not_a_mount(tmp_path):
    """The Speakeasy half of the discriminator, and a mutation is what said it was missing.

    `elif imported is not None:` guards the same distinction the TypeScript flavour draws for
    `new WeakMap()`: Speakeasy imports every mounted class by name, so an unresolved mount whose
    name is in the import map names a file this checkout does not carry, and a `new` naming
    something the file never imported states no module at all. `get parsed()` returning
    `new URL(...)` is that second case, and without it the guard was unfalsifiable -- replacing it
    with a bare `else` survived the whole suite.

    Written after the mutation survived rather than before, which is the ordering the brief asks
    for: suspect the mutation, then the test, then the code. The mutation is real -- it records a
    decline on this input and the original does not -- so the fault was the missing fixture.
    """
    root = _speakeasy_sdk(
        tmp_path,
        "  get parsed(): URL {\n    return new URL(this._baseURL);\n  }\n",
    )

    operations, unreadable = symbols_speakeasy.extract_symbols(root)

    assert [operation.symbol for operation in operations] == ["aliases.getAlias"]
    assert unreadable == ()


def test_a_clean_extraction_says_so_rather_than_saying_nothing(tmp_path):
    """Present and empty, and the line carries no clause at all.

    M3-W94's argument, which is why the field is required at construction: an absent key does not
    distinguish a clean read from a reader that never recorded a fault. A clause that appears only
    when there is something to say is the same argument one level down -- silence in the line is
    the claim, and it is only a claim because the field is always there to be checked.

    Neither committed vendor tree can carry this assertion: all three are partial checkouts and
    all three now say so, which is the point of the channel.
    """
    spec = _spec(tmp_path, ("GET", "/v1/models"))
    report = symbols_typescript.report_extraction(
        _sdk(tmp_path), read_spec_operations(spec)
    )

    assert report.unreadable == ()
    assert "could not read" not in report.render()
    assert report.covered_count == 1


def test_the_adapter_surfaces_a_decline_on_the_path_that_stages_no_specification(tmp_path, caplog):
    """The default path, which M3-W91 measured as logging nothing at all.

    Without a staged specification there is no coverage line and no cross-check, so a decline had
    nowhere to appear even in principle. `extract_symbols` returning the pair is what closes that
    half; the report closes the other.
    """
    import logging

    from sync.signals.generated.adapter import GeneratedSpecAdapter

    root = _python_sdk(
        tmp_path,
        """
        class Acme(SyncAPIClient):
            @cached_property
            def messages(self) -> Messages:
                ...

            @cached_property
            def models(self) -> Models:
                ...

        class Models(SyncAPIResource):
            def list(self):
                return self._get_api_list("/v1/models")
        """,
    )
    adapter = GeneratedSpecAdapter(
        vendor_id="acme", sources={}, fetch=_never_fetch, cache_dir=tmp_path, sdk_source=root,
    )

    with caplog.at_level(logging.DEBUG, logger="sync.signals.generated.adapter"):
        assert adapter.operation_for_symbol("acme.models.list") is not None

    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    detail = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]

    assert warnings == ["acme: 1 constructs the stainless-python rule could not read"]
    assert [record for record in detail if "Acme.messages mounts 'Messages'" in record]


def test_the_adapter_states_the_count_once_rather_than_warning_per_decline(tmp_path, caplog):
    """A decline that is expected and correct on every run is noise at warning level, and the
    truncated `vercel/sdk` fixture produces 48 of them on every extraction.

    So the count is one warning and the records are one level below it. That is the opposite
    balance from `unknown_to_spec`, which warns per entry -- and deliberately: that channel
    reports two artifacts disagreeing, where this one reports a limit of our own rule, and 48
    warnings per vendor per run is how a reader learns to filter the logger out.
    """
    import logging

    from sync.signals.generated.adapter import GeneratedSpecAdapter

    adapter = GeneratedSpecAdapter(
        vendor_id="vercel", sources={}, fetch=_never_fetch, cache_dir=tmp_path,
        sdk_source=SPEAKEASY_SDK, sdk_spec_operations=VERCEL_SPEC,
        sdk_source_generator="speakeasy-typescript",
    )

    with caplog.at_level(logging.DEBUG, logger="sync.signals.generated.adapter"):
        adapter.operation_for_symbol("vercel.aliases.listAliases")

    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    detail = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]

    assert warnings == ["vercel: 48 constructs the speakeasy-typescript rule could not read"]
    assert len(detail) == 49
    assert len([record for record in detail if "speakeasy-typescript: sdk/sdk:" in record]) == 48


# --- fixtures written by hand, because these shapes are not what a generator emits -----------


def _python_sdk(tmp_path: Path, source: str) -> Path:
    """One file of the shape the Stainless Python rule reads.

    The same construction `tests/test_python_flavour_and_literal_declines.py` uses, for the same
    reason: every construct here is one Stainless does not emit, so there is nothing in the
    committed Anthropic tree to replace.
    """
    from textwrap import dedent

    root = tmp_path / "sdk"
    root.mkdir()
    (root / "_client.py").write_text(dedent(source), encoding="utf-8")
    return root


def _speakeasy_sdk(tmp_path: Path, client_member: str = "") -> Path:
    """Four files of the shape the Speakeasy rule reads, with `aliases.getAlias` readable.

    Written by hand rather than cut from the committed `vercel/sdk` tree, because that tree is
    deliberately partial: every mount and most delegations in it already decline, so it cannot
    carry an assertion that a construct is *not* recorded. `aliases.getAlias` resolves so the
    extraction roots and reaches an operation either way.
    """
    root = tmp_path / "speakeasy"
    files = {
        "sdk/sdk.ts": (
            'import { Aliases } from "./aliases.js";\n'
            'import { ClientSDK } from "../lib/sdks.js";\n'
            "\n"
            "export class Vercel extends ClientSDK {\n"
            "  get aliases(): Aliases {\n"
            "    return (this._aliases ??= new Aliases(this._options));\n"
            "  }\n"
            + client_member
            + "}\n"
        ),
        "sdk/aliases.ts": (
            'import { aliasesGetAlias } from "../funcs/aliasesGetAlias.js";\n'
            'import { ClientSDK } from "../lib/sdks.js";\n'
            'import { unwrapAsync } from "../types/fp.js";\n'
            "\n"
            "export class Aliases extends ClientSDK {\n"
            "  async getAlias(request, options) {\n"
            "    return unwrapAsync(aliasesGetAlias(this, request, options));\n"
            "  }\n"
            "}\n"
        ),
        "funcs/aliasesGetAlias.ts": (
            "export async function aliasesGetAlias(client, request, options) {\n"
            '  const path = pathToFunc("/v4/aliases/{id}")(pathParams);\n'
            "  const requestRes = client._createRequest({\n"
            '    method: "GET",\n'
            "    path: path,\n"
            "  }, options);\n"
            "  return requestRes;\n"
            "}\n"
        ),
    }
    for relative, body in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    return root


def _never_fetch(url: str) -> str:
    raise AssertionError("symbol extraction must not reach a network")


def _sdk(
    tmp_path: Path, *methods: str, client: str | None = None, client_field: str = ""
) -> Path:
    """Three files of the shape the Stainless TypeScript rule reads, with `models.list` readable.

    The same construction `tests/test_parameter_reduction.py` uses, and hand-written for the same
    reason: the routes these tests need are ones Stainless does not emit, so corrupting the
    committed tree into them would make the corruption the fixture. `models.list` is always
    readable, so an assertion about a second operation cannot pass because the whole SDK failed
    to parse.
    """
    root = tmp_path / "sdk"
    files = {
        "client.ts": client or (
            "import * as API from './resources/index';\n"
            "\n"
            "export class Anthropic extends BaseAnthropic {\n"
            "  models: API.Models = new API.Models(this);\n"
            + client_field
            + "}\n"
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
