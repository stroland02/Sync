"""What Sync can and cannot watch in a customer's manifest, as a three-way split.

`docs/superpowers/specs/2026-07-29-sync-adaptive-vendor-substrate.md` sequences this after
un-hardcoding the indexer and says why it is worth its own artifact: a run answers one question
today -- does this repository depend on the vendor I was told to look at -- and says nothing about
the rest of the manifest. The middle category is the point. *Watchable but unconfigured* is the
work queue, and it is invisible until something reports it.

The standard for the middle category is the one `generated-vendors.yaml` already sets for itself:
every entry there "was confirmed by fetching the path", and `mcp-servers.yaml` configured nothing
precisely because no such confirmation was available. So no dependency is called watchable here
without evidence a tier can serve it, and the evidence is committed rather than fetched --
`orb.stats.yml` was captured from `orbcorp/orb-node` the same way, and its shape is the shape
Cloudflare's has, which is a vendor configured on that evidence today.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from sync.signals.intake import (
    NOT_WATCHABLE,
    WATCHABLE,
    WATCHED,
    SdkRepository,
    assess_repository,
    read_declared_dependencies,
    read_registry_apis,
    read_sdk_repositories,
)
from sync.signals.registry import (
    available_vendors,
    configured_generated_repos,
    vendor_sdk_bindings,
)

FIXTURES = Path(__file__).parent / "fixtures" / "intake"

# Confirmed by fetching on 2026-07-29, the method `tests/fixtures/manifests/README.md` records:
# `orbcorp/orb-node` publishes `.stats.yml` and `plaid/plaid-node` publishes nothing. The
# response is committed at `orb.stats.yml`; `plaid` appears in no mapping because the absence is
# what makes it not watchable.
GENERATOR_EVIDENCE = {
    "orb-billing": SdkRepository(repo="orbcorp/orb-node", manifest=".stats.yml"),
    "@vercel/sdk": SdkRepository(repo="vercel/sdk", manifest=".speakeasy/workflow.yaml"),
    "openai": SdkRepository(repo="openai/openai-python", manifest=".stats.yml"),
}


def _report(fixture: str, **over):
    kwargs = {"generator_manifests": GENERATOR_EVIDENCE}
    kwargs.update(over)
    return assess_repository(FIXTURES / fixture, **kwargs)


def _by_name(report) -> dict[str, object]:
    return {item.dependency.name: item for item in report.assessments}


# Constructed here rather than committed, and written with `write_bytes`. A string holding an odd
# character is still valid UTF-8 once Python encodes it, so it would never reach the handler these
# tests aim at. The bytes are cp1252 for an accented identifier: valid in their own manifest
# syntax once decoded that way, and an invalid UTF-8 continuation byte -- so the *only* reason the
# read fails is the decode, not the parse. Committing them would put a file in the tree whose
# bytes are deliberately illegal, and any editor, formatter or agent that round-trips it as text
# repairs it silently; the test would then pass against a valid file, which is the manufactured
# confidence `CLAUDE.md` names. `tests/test_corpus_binary_files.py` constructs its bytes for the
# same reason.
NOT_UTF8_PACKAGE_JSON = b'{"dependencies": {"caf\xe9-sdk": "^1.0.0"}}'
NOT_UTF8_PYPROJECT = b'[project]\ndependencies = ["caf\xe9-sdk>=1.0.0"]\n'
NOT_UTF8_REQUIREMENTS = b"caf\xe9-sdk==1.0.0\n"


# --- the closing condition -----------------------------------------------------------


def test_five_declared_sdks_produce_a_three_way_split():
    """The spec's closing condition, with every landing justified rather than asserted.

    `stripe` and `twilio` are watched: both adapters declare an npm binding, so a call site in
    this repository reaches an operation. `@vercel/sdk` is generated from `vercel/sdk`, which
    `generated-vendors.yaml` configures as vendor `vercel`, so its specification is diffable and
    nothing declares which package a customer imports -- the missing configuration is the
    binding, and its scoped name is why the join is on the repository rather than on a name.
    `orb-billing` is generated from `orbcorp/orb-node`, which commits a Stainless manifest and
    which nothing configures, so the missing configuration is a line in that file. `plaid`
    publishes no manifest under either convention and no vendor declares it, so there is nothing
    for a tier to read.
    """
    report = _report("five_sdks")
    split = {name: item.category for name, item in _by_name(report).items()}

    assert split["stripe"] == WATCHED
    assert split["twilio"] == WATCHED
    assert split["@vercel/sdk"] == WATCHABLE
    assert split["orb-billing"] == WATCHABLE
    assert split["plaid"] == NOT_WATCHABLE

    assert report.counts() == {WATCHED: 2, WATCHABLE: 2, NOT_WATCHABLE: 3}


def test_a_watched_dependency_names_the_vendor_it_resolves_to():
    """A split that does not say which vendor is watching is not actionable, and it is the field
    that catches a dependency matched against the wrong adapter."""
    watched = _by_name(_report("five_sdks"))["stripe"]

    assert watched.vendor_id == "stripe"
    assert watched.dependency.version == "^18.0.0"
    assert watched.dependency.ecosystem == "npm"


# --- the middle category, which must be actionable rather than a label ---------------


def test_the_two_middle_reasons_are_told_apart():
    """The coordinator's requirement, and the difference decides what someone does next.

    A dependency missing an SDK binding is a change to an adapter; one missing a registry entry
    is a line in a configuration file. A reader who cannot tell them apart can act on neither.
    """
    items = _by_name(_report("five_sdks"))

    assert items["@vercel/sdk"].missing == "sdk-binding"
    assert items["orb-billing"].missing == "registry-entry"
    assert items["@vercel/sdk"].missing != items["orb-billing"].missing


def test_a_dependency_moves_between_watched_and_watchable_with_its_binding():
    """The pair that proves the middle category is real rather than a label.

    `@vercel/sdk` is the dependency both halves are establishable for: a configured registry
    entry against `vercel/sdk`, and a binding that could be declared and is not. Declare one and
    it is watched; withhold it and the same dependency in the same manifest lands in the middle
    with the missing thing named. That is precisely the state the four generated vendors are in
    today, reached here deliberately rather than by accident.
    """
    bound = _by_name(
        _report("five_sdks", bindings={"vercel": {"typescript": {"package": "@vercel/sdk"}}})
    )["@vercel/sdk"]
    assert bound.category == WATCHED
    assert bound.vendor_id == "vercel"

    unbound = _by_name(_report("five_sdks"))["@vercel/sdk"]
    assert unbound.category == WATCHABLE
    assert unbound.missing == "sdk-binding"
    assert unbound.vendor_id == "vercel"


def test_withholding_a_binding_from_a_vendor_with_no_registry_entry_leaves_nothing():
    """The other half, and it must not be softened into the middle.

    Stripe is watched only because its adapter declares the package; `stripe-node` is
    hand-written rather than generator-produced, so nothing else in this system could serve it.
    Withhold the binding and the honest answer is not watchable, not "watchable if someone
    configures something" -- there is no something to configure.
    """
    unbound = _by_name(_report("five_sdks", bindings={}))["stripe"]

    assert unbound.category == NOT_WATCHABLE
    assert unbound.missing is None


def test_configuring_a_generated_vendor_changes_what_is_missing(monkeypatch):
    """The same pair through the mechanism a deployment actually has.

    `generated-vendors.yaml` is the file the spec points at when it says adding a vendor costs a
    line and no module, so the report has to move when someone adds that line. It moves from
    "no registry entry" to "no SDK binding" rather than to watched, because a registry entry is
    half of what watching needs and this report must not imply otherwise.
    """
    monkeypatch.setenv(
        "SYNC_GENERATED_VENDORS", str(FIXTURES / "generated-vendors-empty.yaml")
    )
    assert _by_name(_report("five_sdks"))["orb-billing"].missing == "registry-entry"

    monkeypatch.setenv(
        "SYNC_GENERATED_VENDORS", str(FIXTURES / "generated-vendors-with-orb.yaml")
    )
    configured = _by_name(_report("five_sdks"))["orb-billing"]
    assert configured.category == WATCHABLE
    assert configured.missing == "sdk-binding"
    assert configured.vendor_id == "orb"


def test_nothing_is_called_watchable_without_evidence_a_tier_can_serve_it():
    """`plaid` is a real SDK and would be a plausible guess. It publishes no generator manifest
    under either convention, so calling it watchable would be a promise the next run breaks --
    and this report is described as a sales asset, which makes an overstatement worse than an
    omission. Withdrawing the Orb evidence must move Orb too, or the evidence is decorative."""
    items = _by_name(_report("five_sdks"))
    assert items["plaid"].category == NOT_WATCHABLE

    without_evidence = _by_name(_report("five_sdks", generator_manifests={}))
    assert without_evidence["orb-billing"].category == NOT_WATCHABLE


def test_an_ordinary_library_is_not_watchable_and_says_why():
    """The reason is not allowed to be empty. A split with a blank third column tells a customer
    nothing about why two thirds of their manifest is uncovered."""
    express = _by_name(_report("five_sdks"))["express"]

    assert express.category == NOT_WATCHABLE
    assert express.reason.strip() != ""
    assert express.missing is None


# --- manifests, including the ones that do not parse ---------------------------------


def test_a_python_manifest_is_read_as_its_own_ecosystem():
    """A distribution name is not an npm name, and a report that mixed them would match
    `stripe` on PyPI against an npm binding that says nothing about it.

    `openai` lands differently here than the npm package of the same name would: this one is
    generated from `openai/openai-python`, which vendor `openai` is configured against, so what
    is missing is the binding rather than the entry. That the same name answers differently per
    ecosystem is the join being exact rather than approximate.
    """
    items = _by_name(_report("python_app"))

    assert items["stripe"].category == WATCHED
    assert items["stripe"].dependency.ecosystem == "pypi"
    assert items["openai"].category == WATCHABLE
    assert items["openai"].missing == "sdk-binding"
    assert items["openai"].vendor_id == "openai"
    assert items["requests"].category == NOT_WATCHABLE


def test_a_manifest_that_does_not_parse_is_reported_rather_than_skipped():
    """A repository whose manifest is unreadable is not a repository with no dependencies, and
    the difference decides whether a customer believes they are covered. Silence here reads as
    a clean scan of an empty manifest."""
    report = _report("broken_manifest")

    assert report.assessments == ()
    assert report.unreadable != ()
    assert any("package.json" in problem for problem in report.unreadable)


def test_a_repository_with_no_manifest_is_not_an_error():
    """Distinct from the case above, and deliberately so. Nothing to read is a fact about the
    repository; something unreadable is a fault, and collapsing them would either raise on
    ordinary repositories or hide a real one."""
    report = _report("no_manifest")

    assert report.assessments == ()
    assert report.unreadable == ()


def test_a_package_json_that_is_valid_json_and_not_an_object_is_reported():
    """Distinct from the unparseable case, and it has to be. A top-level array parses cleanly, so
    nothing raises and nothing is declared -- reported as zero dependencies it is indistinguishable
    from a project that depends on nothing, which is the narrowing this report exists to remove."""
    report = _report("array_manifest")

    assert report.assessments == ()
    assert any("does not hold an object" in problem for problem in report.unreadable)


def test_package_json_bytes_that_are_not_utf8_are_a_fault_rather_than_a_crash(tmp_path):
    """The failure `CLAUDE.md` says no fixture in this repository can catch, caught deliberately.

    These bytes are valid JSON read as cp1252, so the decode is the only thing that fails. A
    customer repository with one accented package name would otherwise raise `UnicodeDecodeError`
    out of the whole report rather than naming the file it could not read.
    """
    (tmp_path / "package.json").write_bytes(NOT_UTF8_PACKAGE_JSON)

    dependencies, unreadable = read_declared_dependencies(tmp_path)

    assert dependencies == ()
    assert any("package.json could not be read" in problem for problem in unreadable)


def test_both_python_manifests_are_read_when_a_project_carries_both():
    """The module reads both deliberately, because both are current practice and a project may
    declare different things in each. Reading one reports half the ecosystem as declaring nothing,
    and the half that vanishes is silent -- there is no fault to notice."""
    items = _by_name(_report("python_both"))

    assert items["stripe"].category == WATCHED
    assert items["orb-billing"].category == WATCHABLE
    assert items["openai"].missing == "sdk-binding"
    assert items["requests"].category == NOT_WATCHABLE
    assert {"stripe", "orb-billing", "openai", "requests"} <= set(items)


def test_an_unparseable_pyproject_is_reported_and_the_other_manifest_is_still_read():
    """The two halves are independent, and collapsing them would lose one of them.

    A `pyproject.toml` that does not parse must not take `requirements.txt` down with it: the
    fault is recorded for the file that has one, and the packages the readable manifest declares
    still reach the report. Reporting nothing here would understate the repository twice over.
    """
    report = _report("python_half_broken")

    assert any("pyproject.toml could not be read" in problem for problem in report.unreadable)
    assert _by_name(report)["openai"].category == WATCHABLE


def test_a_non_string_in_the_dependency_array_is_dropped_and_the_rest_still_read():
    """TOML arrays are heterogeneous, so a requirement list can hold something that is not a
    requirement. The file parses, which is why this is not the unreadable case: only the entry is
    wrong, and `Dependency(name=12)` would put a number where every consumer expects a package.

    Pinned as the behaviour it is rather than endorsed. This is the one manifest malformation the
    module drops without recording, and the report accompanying this task argues that is a
    narrower contract than `unreadable` sets -- but it is consistent with the identical filter in
    the npm reader, so it is a design question rather than a defect.
    """
    dependencies, unreadable = read_declared_dependencies(FIXTURES / "python_mixed_array")

    assert [d.name for d in dependencies] == ["stripe"]
    assert unreadable == ()


def test_pyproject_bytes_that_are_not_utf8_are_a_fault_rather_than_a_crash(tmp_path):
    """Valid TOML read as cp1252, so the decode is the only thing that fails."""
    (tmp_path / "pyproject.toml").write_bytes(NOT_UTF8_PYPROJECT)

    dependencies, unreadable = read_declared_dependencies(tmp_path)

    assert dependencies == ()
    assert any("pyproject.toml could not be read" in problem for problem in unreadable)


def test_requirements_bytes_that_are_not_utf8_are_a_fault_rather_than_a_crash(tmp_path):
    """`requirements.txt` has no parser to fail, so the decode is the only failure it has -- and
    the arm that catches it is the one nothing else in this suite reaches."""
    (tmp_path / "requirements.txt").write_bytes(NOT_UTF8_REQUIREMENTS)

    dependencies, unreadable = read_declared_dependencies(tmp_path)

    assert dependencies == ()
    assert any("requirements.txt could not be read" in problem for problem in unreadable)


def test_every_manifest_fault_reaches_the_artifact_rather_than_being_counted_and_dropped(tmp_path):
    """`unreadable` is an accumulator, and a fault appended to it and dropped by the caller is
    exactly the silent narrowing it exists to prevent.

    All three manifests fail at once, which is what makes the point: `counts()` answers three
    zeroes, and three zeroes are what a repository depending on nothing answers too. The zeroes
    are only honest because the faults travel beside them in the same artifact, so this asserts
    the serialised form carries all three rather than trusting that the list was populated.
    """
    (tmp_path / "package.json").write_bytes(NOT_UTF8_PACKAGE_JSON)
    (tmp_path / "pyproject.toml").write_bytes(NOT_UTF8_PYPROJECT)
    (tmp_path / "requirements.txt").write_bytes(NOT_UTF8_REQUIREMENTS)

    report = assess_repository(tmp_path, generator_manifests=GENERATOR_EVIDENCE)

    assert report.counts() == {WATCHED: 0, WATCHABLE: 0, NOT_WATCHABLE: 0}

    payload = json.loads(report.to_json())
    assert payload["counts"] == {WATCHED: 0, WATCHABLE: 0, NOT_WATCHABLE: 0}
    assert len(payload["unreadable"]) == 3
    for manifest in ("package.json", "pyproject.toml", "requirements.txt"):
        assert any(manifest in problem for problem in payload["unreadable"])


def test_the_manifest_read_is_pure_and_returns_versions_as_declared():
    """Separated from classification the way `manifest.py` separates parsing from fetching, so
    the classifier can be driven by committed fixtures and reaches no network."""
    dependencies, unreadable = read_declared_dependencies(FIXTURES / "five_sdks")

    assert unreadable == ()
    assert {d.name: d.version for d in dependencies}["stripe"] == "^18.0.0"
    assert {d.ecosystem for d in dependencies} == {"npm"}


# --- the registry side ----------------------------------------------------------------


def test_every_coded_adapter_is_offered_a_binding_lookup():
    """Two tables that must agree, with something checking that they do.

    `_CODED_ADAPTERS` exists so this module can read a declared binding without constructing an
    adapter, and it is keyed the way `_BUILDERS` is. An adapter added to one and not the other
    would silently stop being matchable against a manifest.
    """
    from sync.signals import registry

    assert set(registry._CODED_ADAPTERS) == set(registry._BUILDERS)


def test_the_configured_repositories_are_keyed_for_the_join():
    """Keyed by repository, because that is the side a package's evidence can be matched on."""
    repos = configured_generated_repos()

    assert repos["vercel/sdk"] == "vercel"
    assert repos["openai/openai-python"] == "openai"
    assert "openai/openai-node" not in repos


def test_the_bindings_reported_are_the_ones_the_adapters_declare():
    bindings = vendor_sdk_bindings()

    assert bindings["stripe"]["typescript"]["package"] == "stripe"
    assert bindings["twilio"]["python"]["distribution"] == "twilio"


def test_a_registered_vendor_that_declares_no_binding_is_visible_as_such():
    """The finding this task surfaces rather than fixes: four of six registered vendors resolve
    through the registry and can bind no call site, so they can be watched in principle and not
    in fact. Asserted so the number cannot quietly drift in either direction unnoticed."""
    bound = set(vendor_sdk_bindings())
    registered = {vendor for vendor in available_vendors() if not vendor.startswith("mcp:")}

    assert bound == {"stripe", "twilio"}
    assert registered - bound == {"anthropic", "cloudflare", "openai", "vercel"}


def test_reading_a_manifest_reaches_no_network(monkeypatch):
    """The classifier takes evidence as an argument and gathers none. A fetch on this path would
    make a report of what is already on disk quietly online, which is the same rule
    `load_vendor` holds for `sync ingest`."""
    import urllib.request

    def explode(*args, **kwargs):
        raise AssertionError("dependency intake must not reach a network")

    monkeypatch.setattr(urllib.request, "urlopen", explode)
    monkeypatch.setattr(os, "system", explode)

    assert _report("five_sdks").assessments != ()


def test_the_report_serialises_for_an_operator(tmp_path):
    """It is described as a sales asset as much as an engineering one, so it has to leave the
    process. Asserted on the parsed structure rather than on a rendered string, because the
    shape is the artifact and the formatting is not."""
    payload = json.loads(_report("five_sdks").to_json())

    assert payload["counts"][WATCHED] == 2
    entries = {item["name"]: item for item in payload["dependencies"]}
    assert entries["orb-billing"]["category"] == WATCHABLE
    assert entries["orb-billing"]["missing"] == "registry-entry"
    assert entries["plaid"]["reason"] != ""


def test_confirmed_evidence_is_read_from_a_file_rather_than_fetched():
    """The file is the record of the fetch, the shape `generated-vendors.yaml` already uses.

    That is what lets the classifier stay pure: a confirmation is worth having only if a reader
    can check it, and a fetch inside the classifier would make a report of what is on disk
    quietly online.
    """
    evidence = read_sdk_repositories(FIXTURES / "sdk-repositories.yaml")

    assert evidence["orb-billing"] == SdkRepository(repo="orbcorp/orb-node", manifest=".stats.yml")
    assert evidence["@vercel/sdk"].repo == "vercel/sdk"


def test_an_evidence_entry_missing_a_field_raises_rather_than_being_skipped():
    """A deployment that wrote evidence down and silently got none would report a smaller middle
    category and no fault, which is the shape of failure this whole report exists to remove."""
    with pytest.raises(ValueError) as raised:
        read_sdk_repositories(FIXTURES / "sdk-repositories-partial.yaml")

    assert "package" in str(raised.value) or "manifest" in str(raised.value)


def test_evidence_that_is_not_a_list_raises_naming_the_file_and_the_shape():
    """A mapping keyed by package reads as reasonable evidence, so it has to be refused loudly.

    Both assertions are load-bearing and the second is the one that is easy to omit. Delete the
    shape guard and this still raises `ValueError` naming the same path -- iterating a mapping
    yields its keys, `"orb-billing"["package"]` is a `TypeError`, and the entry-level handler
    turns that into a `ValueError` about the entries. The two faults are different repairs: fix
    the container, or fix one line in it. A test that asserted only the type and the path would
    pass against a module that could no longer tell them apart.
    """
    with pytest.raises(ValueError) as raised:
        read_sdk_repositories(FIXTURES / "sdk-repositories-mapping.yaml")

    assert "sdk-repositories-mapping.yaml" in str(raised.value)
    assert "does not hold a list" in str(raised.value)


def test_confirmed_registry_evidence_is_read_from_a_file_rather_than_fetched():
    """The same discipline as `read_sdk_repositories`, for the directory tier. The join is never
    a name resemblance -- an `api_id` is a domain and a package name is not -- so the pair has to
    have been confirmed, and this file is where a reader can check that it was."""
    apis = read_registry_apis(FIXTURES / "registry-apis.yaml")

    assert apis == {"acme-sdk": "acme.com", "ancient-sdk": "ancient.com"}


def test_registry_evidence_that_is_not_a_list_raises_naming_the_file_and_the_shape():
    """The same pair of assertions, for the same reason as the generator tier above."""
    with pytest.raises(ValueError) as raised:
        read_registry_apis(FIXTURES / "registry-apis-mapping.yaml")

    assert "registry-apis-mapping.yaml" in str(raised.value)
    assert "does not hold a list" in str(raised.value)


def test_a_registry_evidence_entry_missing_a_field_raises_rather_than_being_skipped():
    """Skipping it would drop a package from the middle category and report no fault, which is
    the same failure `read_sdk_repositories` refuses for the generator tier."""
    with pytest.raises(ValueError) as raised:
        read_registry_apis(FIXTURES / "registry-apis-partial.yaml")

    assert "registry-apis-partial.yaml" in str(raised.value)
    assert "api" in str(raised.value)


def test_a_pypi_version_is_recorded_as_the_manifest_declares_it():
    """A specifier set is richer than npm's caret and resolving one needs an environment this
    never builds, so what is recorded is what the project declared."""
    dependencies, _ = read_declared_dependencies(FIXTURES / "python_app")

    assert {d.name: d.version for d in dependencies}["stripe"] == ">=12.0.0"
    assert {d.name: d.version for d in dependencies}["openai"] == "==1.51.0"


def test_a_dependency_table_that_is_not_an_object_is_a_fault_rather_than_a_crash():
    """The manifest is a customer's file, so every shape JSON permits arrives eventually.

    The top level is already checked and a bad one is reported. The two tables under it were
    not, and they are splatted into a dict -- so `"dependencies": ["stripe"]` left `TypeError:
    'list' object is not a mapping` to propagate out of `assess_repository` and out of `sync
    intake`, where a traceback is what a customer gets instead of a report. Worse, the same
    malformation had three outcomes: a top-level array was a fault, a truthy non-object crashed,
    and a falsy one (`"dependencies": []`) was silently zero dependencies -- the exact silent
    narrowing `IntakeReport.unreadable` exists to prevent.
    """
    dependencies, unreadable = read_declared_dependencies(FIXTURES / "npm_table_not_an_object")

    assert dependencies == ()
    assert any("dependencies" in problem for problem in unreadable)
