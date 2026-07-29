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


def test_a_pypi_version_is_recorded_as_the_manifest_declares_it():
    """A specifier set is richer than npm's caret and resolving one needs an environment this
    never builds, so what is recorded is what the project declared."""
    dependencies, _ = read_declared_dependencies(FIXTURES / "python_app")

    assert {d.name: d.version for d in dependencies}["stripe"] == ">=12.0.0"
    assert {d.name: d.version for d in dependencies}["openai"] == "==1.51.0"
