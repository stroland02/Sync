"""A vendor added by configuration rather than by a module, through the generated-SDK path.

`src/sync/signals/generated/` was a complete, tested path with no caller, and what was
unreachable is the project's coverage argument: supporting a generator costs a day and yields
every vendor using it, while supporting one more vendor under a known generator costs a
configuration line.

So every assertion here goes through `sync.signals.registry` -- the seam a run selects through.
One that built `GeneratedSpecAdapter` itself would prove the adapter works, which was never in
doubt, and say nothing about whether anything reaches it.

Nothing here touches the network. The manifests are committed captures of the real files, and
both fetches -- the manifest and the specification it names -- are injected.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest
import yaml

from sync.signals import registry
from sync.signals.generated import GeneratedSpecAdapter, STAINLESS_MANIFEST, SPEAKEASY_MANIFEST
from sync.signals.registry import (
    VendorContext,
    available_vendors,
    load_vendor,
    prepare_vendor,
)
from sync.signals.twilio.adapter import TwilioAdapter

MANIFESTS = Path(__file__).parent / "fixtures" / "manifests"

CONFIG = [
    {"vendor_id": "anthropic", "repo": "anthropics/anthropic-sdk-python",
     "manifest": STAINLESS_MANIFEST},
    {"vendor_id": "cloudflare", "repo": "cloudflare/cloudflare-python",
     "manifest": STAINLESS_MANIFEST},
    {"vendor_id": "vercel", "repo": "vercel/sdk", "manifest": SPEAKEASY_MANIFEST},
]

# Two minimal specifications, differing by an operation the newer one dropped, so a run that
# does fetch has something oasdiff can read. Nothing here asserts on the changes themselves --
# `tests/test_generated_adapter.py` covers those -- only on whether a fetch happened at all.
BASE_SPEC = {
    "openapi": "3.0.0", "info": {"title": "t", "version": "1"},
    "paths": {"/things": {"get": {"operationId": "ListThings", "responses": {"200": {
        "description": "ok", "content": {"application/json": {"schema": {"type": "object"}}}}}}}},
}
HEAD_SPEC = {"openapi": "3.0.0", "info": {"title": "t", "version": "1"}, "paths": {}}


def _manifest(name: str) -> str:
    return (MANIFESTS / name).read_text(encoding="utf-8")


def _stainless(hash_value: str) -> str:
    """An Anthropic manifest with its hash replaced, for asking whether the hash moved.

    Derived from the committed capture rather than written from scratch, so a change to what
    Stainless publishes breaks this in the same place it breaks everything else.

    The URL moves with the hash because that is what Stainless does -- the real capture's URL
    ends in a content hash -- and because a stub that served one body for both versions could
    not tell a run fetching twice from one fetching the same thing twice.
    """
    document = yaml.safe_load(_manifest("anthropic.stats.yml"))
    document["openapi_spec_hash"] = hash_value
    document["openapi_spec_url"] = (
        f"https://storage.googleapis.com/stainless-sdk-openapi-specs/anthropic/{hash_value}.yml"
    )
    return yaml.safe_dump(document)


@pytest.fixture()
def configured(tmp_path, monkeypatch):
    """Point the registry at a configuration this test wrote, and return its cache directory."""
    config = tmp_path / "vendors.yaml"
    config.write_text(yaml.safe_dump(CONFIG), encoding="utf-8")
    monkeypatch.setenv(registry.GENERATED_VENDORS_VARIABLE, str(config))
    cache = tmp_path / "cache"
    cache.mkdir()
    return cache


def _context(cache: Path, from_version: str = "aaaaaaa", to_version: str = "bbbbbbb"):
    return VendorContext(cache_dir=cache, from_version=from_version, to_version=to_version)


class _Fetches:
    """A fetch that records what it was asked for, standing in for both network calls.

    Two of them are used per test rather than one: the manifest fetch is meant to happen and the
    specification fetch is the expensive one the hash exists to avoid. A single counter could not
    tell the two apart, which is the distinction the economic claim lives in.
    """

    def __init__(self, bodies: dict[str, str] | None = None, body: str | None = None) -> None:
        self.urls: list[str] = []
        self._bodies = bodies or {}
        self._body = body

    def __call__(self, url: str) -> str:
        self.urls.append(url)
        for fragment, body in self._bodies.items():
            if fragment in url:
                return body
        if self._body is None:
            raise AssertionError(f"nothing serves {url}")
        return self._body


def _serve(monkeypatch, manifests: _Fetches, specs: _Fetches) -> None:
    monkeypatch.setattr(registry, "fetch_manifest", manifests)
    monkeypatch.setattr(registry, "fetch_specification", specs)


# --- the vendor resolves ----------------------------------------------------------


def test_a_configured_generated_vendor_resolves_to_the_generated_adapter(configured, monkeypatch):
    """The coverage argument, reachable for the first time. `GeneratedSpecAdapter` was finished
    and tested with no caller anywhere in `src/`, so a vendor under a supported generator could
    not be scanned however correctly the adapter read its manifest.
    """
    manifests = _Fetches(body=_manifest("anthropic.stats.yml"))
    _serve(monkeypatch, manifests, _Fetches())

    prepared = prepare_vendor("anthropic", _context(configured))

    assert isinstance(prepared.adapter, GeneratedSpecAdapter)
    assert prepared.adapter.vendor_id == "anthropic"


def test_the_hand_written_adapters_still_resolve_to_themselves(tmp_path):
    """The regression that matters. A registry resolving everything to the generated adapter
    passes the test above, and this is the only thing that says which one it resolved to.
    """
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / registry.SYMBOL_MAP_FILENAME).write_text("{}", encoding="utf-8")
    (cache / registry.TWILIO_PRODUCTS_FILENAME).write_text(
        json.dumps([{"filename": "x.json", "domain": "d", "version": "v1"}]), encoding="utf-8"
    )

    # Stripe is a configuration row since `CI-W586`, so the discrimination this test exists for
    # now runs the other way: the one remaining coded vendor must not resolve to the tier.
    assert isinstance(load_vendor("stripe", _context(cache)), GeneratedSpecAdapter)
    assert isinstance(load_vendor("twilio", _context(cache)), TwilioAdapter)


def test_configuration_cannot_shadow_a_hand_written_adapter(tmp_path, monkeypatch):
    """Configuration widens what is registered; it must never replace what is coded.

    A vendor has a subpackage for a reason -- a symbol scheme the generated adapter deliberately
    declines to guess at, answering `operation_for_symbol` with None every time instead. Letting
    a configuration entry win would swap a resolving adapter for one that resolves nothing,
    which produces no findings and reports no fault: the run completes, every count is zero, and
    nothing says why.
    """
    config = tmp_path / "vendors.yaml"
    config.write_text(
        yaml.safe_dump([{"vendor_id": "twilio", "repo": "someone/twilio-sdk",
                         "manifest": STAINLESS_MANIFEST}]),
        encoding="utf-8",
    )
    monkeypatch.setenv(registry.GENERATED_VENDORS_VARIABLE, str(config))
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / registry.SYMBOL_MAP_FILENAME).write_text("{}", encoding="utf-8")
    (cache / registry.TWILIO_PRODUCTS_FILENAME).write_text(
        json.dumps([{"filename": "x.json", "domain": "d", "version": "v1"}]), encoding="utf-8"
    )

    assert isinstance(load_vendor("twilio", _context(cache)), TwilioAdapter)


def test_a_configured_vendor_is_offered_on_the_command_line(configured):
    """Selection is data, so what the parser offers has to come from the same place the builders
    do. A configured vendor the parser refuses is registered and unreachable, which is the shape
    of defect this whole sequence of tasks exists to close.
    """
    offered = available_vendors()

    for entry in CONFIG:
        assert entry["vendor_id"] in offered
    # The one remaining hand-written adapter is not displaced by configuration arriving.
    # Stripe left this set in `CI-W586`: it is a row now, so under a test configuration that
    # does not declare it, it is correctly absent rather than coded.
    assert "twilio" in offered


def test_no_configured_vendor_is_named_in_the_registry_itself():
    """The constraint the registry was built to hold. A vendor id appearing in shared code is
    the knowledge the plugin boundary exists to keep out, and a configuration mechanism that
    still needed a line per vendor in `registry.py` would have moved it rather than removed it.
    """
    source = Path(registry.__file__).read_text(encoding="utf-8")

    for entry in CONFIG:
        assert entry["vendor_id"] not in source


# --- the economics ----------------------------------------------------------------


def test_an_unchanged_spec_hash_fetches_no_specification(configured, monkeypatch):
    """The claim that makes polling many vendors affordable rather than an idea about polling
    many vendors. Two identical hashes mean the specification did not move, and the two
    manifests -- text files in a public repository -- are the whole cost of finding that out.

    Asserted on the specification fetch alone. Counting both together would pass for a path that
    fetched specifications and never read a manifest, which is the opposite arrangement.
    """
    manifests = _Fetches(body=_stainless("same-hash"))
    specs = _Fetches(body=json.dumps(BASE_SPEC))
    _serve(monkeypatch, manifests, specs)

    adapter = prepare_vendor("anthropic", _context(configured)).adapter
    changes = list(adapter.fetch_changes("aaaaaaa", "bbbbbbb"))

    assert specs.urls == []
    assert changes == []
    # The manifests were read, so this is not a path that answered by doing nothing at all.
    assert len(manifests.urls) == 2


def test_a_changed_spec_hash_does_fetch_the_specification(configured, monkeypatch):
    """The counterweight, and it is load-bearing: the test above is satisfied by any path that
    never fetches, including one that lost the ability to.
    """
    manifests = _Fetches(bodies={"aaaaaaa": _stainless("old"), "bbbbbbb": _stainless("new")})
    specs = _Fetches(bodies={"old": json.dumps(BASE_SPEC), "new": json.dumps(HEAD_SPEC)})
    _serve(monkeypatch, manifests, specs)

    adapter = prepare_vendor("anthropic", _context(configured)).adapter
    list(adapter.fetch_changes("aaaaaaa", "bbbbbbb"))

    # One per side, and each the URL its own manifest named -- a run fetching the same artifact
    # twice would satisfy a bare count and be comparing a specification against itself.
    assert len(specs.urls) == 2
    assert len(set(specs.urls)) == 2


def test_staging_a_generated_vendor_fetches_no_specification(configured, monkeypatch):
    """Where the economics would be lost without anyone noticing. `prepare_vendor` stages what a
    scan needs, and for a hand-written vendor that means downloading its specifications -- doing
    the same here would pay the cost the hash exists to avoid, before anything had consulted it,
    and every test above would still pass because the fetch would simply have happened earlier.
    """
    manifests = _Fetches(body=_stainless("same-hash"))
    specs = _Fetches(body=json.dumps(BASE_SPEC))
    _serve(monkeypatch, manifests, specs)

    prepare_vendor("anthropic", _context(configured))

    assert specs.urls == []


def test_a_vendor_with_no_hash_is_reported_as_costing_a_fetch_every_scan(configured, monkeypatch, caplog):
    """`has_cheap_change_trigger` is the only thing that separates a vendor Sync can poll for
    nothing from one it pays for on every scan, and staging is the one place both manifests are
    in hand to ask.

    Cloudflare publishes no hash, so `changed_from` answers "changed" -- correct, since unknown
    must never read as unchanged -- and the vendor costs two specification fetches forever.
    Nothing downstream can tell that from a vendor whose specification genuinely moves every
    time, which is what makes it worth saying here rather than leaving to a bill.
    """
    _serve(monkeypatch, _Fetches(body=_manifest("cloudflare.stats.yml")), _Fetches())

    with caplog.at_level("INFO", logger="sync.signals.registry"):
        prepare_vendor("cloudflare", _context(configured))

    assert "cloudflare" in caplog.text
    assert "hash" in caplog.text


def test_a_vendor_with_a_hash_is_not_reported_as_expensive(configured, monkeypatch, caplog):
    """The counterweight. A report emitted for every vendor is a report nobody reads, and it
    would make the cheap majority look like the expensive exception.
    """
    _serve(monkeypatch, _Fetches(body=_stainless("a-hash")), _Fetches())

    with caplog.at_level("INFO", logger="sync.signals.registry"):
        prepare_vendor("anthropic", _context(configured))

    assert "hash" not in caplog.text


def test_a_manifest_naming_no_specification_is_reported_rather_than_failing(configured, monkeypatch):
    """Cloudflare publishes an endpoint count and no URL at all. That is a coverage gap this
    approach does not close, and it is neither an error nor silence: the vendor still needs a
    hand-written adapter and must not abort a scan across every other vendor.
    """
    manifests = _Fetches(body=_manifest("cloudflare.stats.yml"))
    specs = _Fetches()
    _serve(monkeypatch, manifests, specs)

    adapter = prepare_vendor("cloudflare", _context(configured)).adapter

    assert list(adapter.fetch_changes("aaaaaaa", "bbbbbbb")) == []
    assert specs.urls == []


def test_the_other_generator_resolves_through_the_same_configuration(configured, monkeypatch):
    """Vercel is Speakeasy-generated, and the point of it being configured beside three Stainless
    vendors is that adopting a second generator changed the manifest name in a configuration
    entry and nothing else.
    """
    manifests = _Fetches(body=_manifest("vercel.workflow.yaml"))
    _serve(monkeypatch, manifests, _Fetches())

    prepared = prepare_vendor("vercel", _context(configured))

    assert isinstance(prepared.adapter, GeneratedSpecAdapter)
    assert manifests.urls and all(SPEAKEASY_MANIFEST in url for url in manifests.urls)


# --- the failure paths ------------------------------------------------------------


def test_a_malformed_manifest_fails_naming_the_path(configured, monkeypatch):
    """`parse_manifest` answers None for anything unusable, deliberately, so one vendor's broken
    manifest cannot abort a scan across the others. Here one vendor was asked for by name, so
    None means that vendor cannot be served -- and resolving it to a default would be the silent
    fallback `registry.py` already refuses for an unknown id.
    """
    _serve(monkeypatch, _Fetches(body="{{ not yaml"), _Fetches())

    with pytest.raises(ValueError) as raised:
        prepare_vendor("anthropic", _context(configured))

    assert "anthropics/anthropic-sdk-python" in str(raised.value)
    assert STAINLESS_MANIFEST in str(raised.value)


def test_a_manifest_that_cannot_be_fetched_fails_naming_the_path(configured, monkeypatch):
    """An outage that read as "this vendor published nothing" is the exact failure the product
    exists to catch, arriving from our own side.
    """
    def broken(url: str) -> str:
        raise OSError("network is down")

    monkeypatch.setattr(registry, "fetch_manifest", broken)

    with pytest.raises(RuntimeError) as raised:
        prepare_vendor("anthropic", _context(configured))

    assert "anthropics/anthropic-sdk-python" in str(raised.value)


def test_an_unknown_vendor_still_names_what_is_available(configured):
    """Configuration widens what is registered and must not weaken what happens off the end of
    it. Every configured vendor appears in the message, because a name absent from it looks
    exactly like a name that was never configured.
    """
    with pytest.raises(KeyError) as raised:
        prepare_vendor("sendgrid", _context(configured))

    message = str(raised.value)
    assert "sendgrid" in message
    for entry in CONFIG:
        assert entry["vendor_id"] in message


# --- what ships -------------------------------------------------------------------


def test_the_shipped_configuration_names_only_supported_generator_conventions():
    """A configuration entry pointing at a path no generator writes is a runtime failure wearing
    the costume of support: it registers, it is offered on the command line, and it fails on the
    first scan. The manifest name is the part a typo hides in, and it is checkable here without
    the network.
    """
    shipped = yaml.safe_load(registry.GENERATED_VENDORS_FILE.read_text(encoding="utf-8"))

    assert shipped, "the shipped configuration registers no vendor at all"
    for entry in shipped:
        if not entry.get("manifest"):
            # A row naming its specification names no convention; that it names exactly one of
            # the two is enforced by `_generated_vendors` and tested there.
            assert entry.get("spec")
            continue
        assert entry["manifest"] in {STAINLESS_MANIFEST, SPEAKEASY_MANIFEST}
        assert entry["repo"].count("/") == 1


def test_the_shipped_configuration_is_what_the_command_line_offers():
    """Read from the same place rather than restated, so a vendor added to the file needs no
    second edit anywhere -- which is the whole claim: a configuration entry, not a module.
    """
    shipped = yaml.safe_load(registry.GENERATED_VENDORS_FILE.read_text(encoding="utf-8"))

    assert {entry["vendor_id"] for entry in shipped} <= set(available_vendors())


# --- a row that names its specification rather than discovering one -----------------


def _direct_config(tmp_path, monkeypatch, **over):
    row = {"vendor_id": "acme", "repo": "acme/openapi", "spec": "openapi/spec3.json"}
    row.update(over)
    config = tmp_path / "vendors.yaml"
    config.write_text(yaml.safe_dump([row]), encoding="utf-8")
    monkeypatch.setenv(registry.GENERATED_VENDORS_VARIABLE, str(config))
    return config


def test_a_row_naming_a_spec_path_needs_no_manifest(tmp_path, monkeypatch):
    """Three vendors need this tier and none of them publishes a generator manifest we can use:
    stripe pins its specification at a git tag, twilio publishes one document per product, and
    openai deleted its `.stats.yml` outright. Discovery through a manifest is one way to reach a
    specification, not the definition of having one."""
    _direct_config(tmp_path, monkeypatch)

    vendors = registry._generated_vendors()

    assert vendors["acme"].spec == "openapi/spec3.json"
    assert vendors["acme"].manifest is None


def test_a_row_naming_both_a_manifest_and_a_spec_is_refused(tmp_path, monkeypatch):
    """The two are alternative answers to one question -- where is the specification -- and a row
    naming both leaves which one wins to whichever branch is read first."""
    _direct_config(tmp_path, monkeypatch, manifest=".stats.yml")

    with pytest.raises(ValueError) as raised:
        registry._generated_vendors()

    assert "acme" in str(raised.value)


def test_a_row_naming_neither_is_refused(tmp_path, monkeypatch):
    config = tmp_path / "vendors.yaml"
    config.write_text(
        yaml.safe_dump([{"vendor_id": "acme", "repo": "acme/openapi"}]), encoding="utf-8"
    )
    monkeypatch.setenv(registry.GENERATED_VENDORS_VARIABLE, str(config))

    with pytest.raises(ValueError):
        registry._generated_vendors()


def test_a_direct_row_resolves_a_versioned_url_per_version(tmp_path, monkeypatch):
    """The ref is in the path, so two versions are two documents rather than one document twice
    -- which is the `ONE_DOCUMENT` trap that already silently disables two configured vendors."""
    _direct_config(tmp_path, monkeypatch)
    vendor = registry._generated_vendors()["acme"]

    base = registry._spec_source(vendor, "v2320")
    head = registry._spec_source(vendor, "v2330")

    assert base.spec_url == "https://raw.githubusercontent.com/acme/openapi/v2320/openapi/spec3.json"
    assert head.spec_url != base.spec_url
    assert base.is_fetchable and head.is_fetchable


def test_a_direct_row_fetches_no_manifest_at_all(tmp_path, monkeypatch):
    """The manifest read is the cheap half of the economic argument. A row that names its
    specification has nothing to discover, so paying for a manifest fetch would be paying for an
    answer already written down."""
    _direct_config(tmp_path, monkeypatch)
    vendor = registry._generated_vendors()["acme"]

    def _never_fetched(url: str) -> str:
        raise AssertionError(f"a direct row fetched a manifest: {url}")

    monkeypatch.setattr(registry, "fetch_manifest", _never_fetched)

    assert registry._spec_source(vendor, "v2330").is_fetchable


# --- a row that names the rule which builds its symbol map -------------------------


def _symbols_config(tmp_path, monkeypatch, **over):
    row = {
        "vendor_id": "stripe",
        "repo": "acme/openapi",
        "spec": "openapi/spec3.json",
        "symbols": "stripe-openapi",
        "sdk_bindings": {"python": {"distribution": "acme", "module": "acme"}},
    }
    row.update(over)
    config = tmp_path / "vendors.yaml"
    config.write_text(yaml.safe_dump([row]), encoding="utf-8")
    monkeypatch.setenv(registry.GENERATED_VENDORS_VARIABLE, str(config))
    return config


def test_a_row_naming_a_symbol_rule_stages_the_map_it_builds(tmp_path, monkeypatch):
    """The last thing a hand-written adapter did that a row could not.

    Both retired adapters resolve symbols from a `symbols.json` their own preparer wrote. A row
    has to be able to say which rule writes it, or moving a vendor onto the tier resolves nothing
    and the run reports zero findings rather than an error.
    """
    _symbols_config(tmp_path, monkeypatch)
    spec = (Path("tests") / "fixtures" / "specs" / "stripe_v2330_shape.json").read_text(
        encoding="utf-8"
    )
    monkeypatch.setattr(registry, "fetch_specification", lambda url: spec)
    cache = tmp_path / "cache"
    cache.mkdir()

    prepared = registry.prepare_vendor("stripe", _context(cache, "v2320", "v2330"))

    assert (cache / registry.SYMBOL_MAP_FILENAME).exists()
    operation = prepared.adapter.operation_for_symbol("stripe.charges.retrieve")
    assert operation is not None and operation.operation_id == "GetChargesCharge"


def test_a_row_naming_a_symbol_rule_correlates_requests_without_a_checkout(tmp_path, monkeypatch):
    """A staged map is enough to correlate, so the correlating adapter is chosen for it.

    Until `CI-W586` that choice was made only by the presence of an SDK checkout, so a vendor
    resolving from a map answered `operation_for_request` not at all.
    """
    _symbols_config(tmp_path, monkeypatch)
    spec = (Path("tests") / "fixtures" / "specs" / "stripe_v2330_shape.json").read_text(
        encoding="utf-8"
    )
    monkeypatch.setattr(registry, "fetch_specification", lambda url: spec)
    cache = tmp_path / "cache"
    cache.mkdir()

    adapter = registry.prepare_vendor("stripe", _context(cache, "v2320", "v2330")).adapter

    operation = adapter.operation_for_request("GET", "/v1/charges/ch_1")
    assert operation is not None and operation.operation_id == "GetChargesCharge"


def test_a_row_naming_no_symbol_rule_fetches_no_specification(tmp_path, monkeypatch):
    """The economic argument, which this commit must not spend.

    A manifest is a text file and a specification is megabytes; only a vendor whose hash actually
    moved should pay for two of those. A row that names no rule has no map to build, so nothing
    is fetched during prepare -- exactly as before.
    """
    _direct_config(tmp_path, monkeypatch)

    def _never(url: str) -> str:
        raise AssertionError(f"prepare fetched a specification: {url}")

    monkeypatch.setattr(registry, "fetch_specification", _never)
    cache = tmp_path / "cache"
    cache.mkdir()

    registry.prepare_vendor("acme", _context(cache, "v2320", "v2330"))


def test_a_row_naming_an_unknown_symbol_rule_is_refused(tmp_path, monkeypatch):
    _symbols_config(tmp_path, monkeypatch, symbols="no-such-rule")

    with pytest.raises(ValueError) as raised:
        registry._generated_vendors()

    assert "no-such-rule" in str(raised.value)


def test_a_symbol_rule_rooted_at_another_vendor_is_refused(tmp_path, monkeypatch):
    """The silent shape this guards: a map whose every key misses stages successfully, the
    reader strips a root that is not there, and the run reports zero findings without an error."""
    _symbols_config(tmp_path, monkeypatch, vendor_id="notstripe")
    spec = (Path("tests") / "fixtures" / "specs" / "stripe_v2330_shape.json").read_text(
        encoding="utf-8"
    )
    monkeypatch.setattr(registry, "fetch_specification", lambda url: spec)
    cache = tmp_path / "cache"
    cache.mkdir()

    with pytest.raises(ValueError) as raised:
        registry.prepare_vendor("notstripe", _context(cache, "v2320", "v2330"))

    assert "resolve to nothing" in str(raised.value)

