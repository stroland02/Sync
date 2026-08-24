"""One adapter for every vendor whose SDK is generated.

`docs/superpowers/specs/2026-07-27-sync-adapter-targets.md` argues coverage is the market
requirement and hand-written adapters are the wrong way to buy it. A generator commits a manifest
naming the specification it worked from, for its own reasons, so no vendor has to cooperate and
no agreement can be withdrawn. `manifest.py` already reads those files; this is what consumes
them.

The most important test here is `test_an_unmoved_hash_downloads_nothing`, which is the entire
economic argument: polling a text file in a public repository costs nothing, and only vendors
whose hash actually moved pay for a spec fetch and an oasdiff run. It is asserted with a counter
rather than by reading the code, because the property is about what did not happen.

No test touches the network. The fetch is injected, and what it returns is a committed fixture.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

import pytest

from sync.core import VendorAdapter
from sync.signals.generated import STAINLESS_MANIFEST, SpecSource, parse_manifest
from sync.signals.generated.adapter import (
    CorrelatingGeneratedSpecAdapter,
    GeneratedSpecAdapter,
)
from sync.signals.generated.symbols import ExtractedOperation

FIXTURES = Path(__file__).parent / "fixtures"
SPECS = FIXTURES / "specs"

MIRROR_BASE = "https://storage.googleapis.com/stainless-sdk-openapi-specs/acme/base.json"
MIRROR_HEAD = "https://storage.googleapis.com/stainless-sdk-openapi-specs/acme/head.json"
VENDOR_HEAD = "https://api.acme.test/openapi.json"

BASE_SPEC = (SPECS / "charges_base.json").read_text(encoding="utf-8")
HEAD_SPEC = (SPECS / "charges_revision.json").read_text(encoding="utf-8")


class _CountingFetch:
    """Stands in for the network, and counts. Every URL it is asked for is recorded, which is
    how the download-avoidance property is asserted rather than assumed."""

    def __init__(self, bodies: dict[str, str] | None = None, failing: set[str] | None = None):
        self.bodies = bodies if bodies is not None else {MIRROR_BASE: BASE_SPEC, MIRROR_HEAD: HEAD_SPEC}
        self.failing = failing or set()
        self.calls: list[str] = []

    def __call__(self, url: str) -> str:
        self.calls.append(url)
        if url in self.failing:
            raise RuntimeError(f"the spec host refused: {url}")
        return self.bodies[url]


def _stainless(url: str | None, spec_hash: str | None, endpoints: int = 42) -> SpecSource:
    """A `SpecSource` built by the real parser, so these tests exercise the chain the run does."""
    lines = [f"configured_endpoints: {endpoints}"]
    if url is not None:
        lines.append(f"openapi_spec_url: {url}")
    if spec_hash is not None:
        lines.append(f"openapi_spec_hash: {spec_hash}")
    source = parse_manifest(STAINLESS_MANIFEST, "\n".join(lines) + "\n")
    assert source is not None
    return source


def _adapter(tmp_path, sources, fetch=None, vendor_spec_urls=None) -> GeneratedSpecAdapter:
    return GeneratedSpecAdapter(
        vendor_id="acme",
        sources=sources,
        fetch=fetch if fetch is not None else _CountingFetch(),
        cache_dir=tmp_path / "specs",
        vendor_spec_urls=vendor_spec_urls,
    )


def _moved(spec_hash_from="h-old", spec_hash_to="h-new"):
    return {
        "v1": _stainless(MIRROR_BASE, spec_hash_from),
        "v2": _stainless(MIRROR_HEAD, spec_hash_to),
    }


# --- the protocol -----------------------------------------------------------------


def test_adapter_satisfies_the_vendor_adapter_protocol(tmp_path):
    assert isinstance(_adapter(tmp_path, _moved()), VendorAdapter)


def test_the_vendor_id_is_the_one_it_was_built_for(tmp_path):
    assert _adapter(tmp_path, _moved()).vendor_id == "acme"


def test_operation_for_symbol_answers_nothing(tmp_path):
    """This adapter knows a specification, not an SDK's symbol scheme -- which is exactly the
    vendor-specific knowledge it exists to avoid needing. Inventing a naming convention here
    would put back the per-vendor guesswork the whole approach removes."""
    assert _adapter(tmp_path, _moved()).operation_for_symbol("acme.charges.create") is None


# --- the cheap trigger, which is the point ----------------------------------------


def test_an_unmoved_hash_downloads_nothing(tmp_path):
    """The economic argument, asserted. Polling a manifest in a public repository is free;
    a spec fetch and an oasdiff run are not. A vendor whose hash has not moved must cost
    nothing at all, and the counter is what proves the download did not happen -- reading the
    code cannot.
    """
    fetch = _CountingFetch()
    sources = {"v1": _stainless(MIRROR_BASE, "same-hash"), "v2": _stainless(MIRROR_HEAD, "same-hash")}

    changes = list(_adapter(tmp_path, sources, fetch=fetch).fetch_changes("v1", "v2"))

    assert fetch.calls == []
    assert changes == []


def test_a_moved_hash_pays_for_both_sides_and_diffs_them(tmp_path):
    """The other half of the trade: when the hash did move, the fetch and the diff are exactly
    what the manifest bought the right to skip everywhere else."""
    fetch = _CountingFetch()

    changes = list(_adapter(tmp_path, _moved(), fetch=fetch).fetch_changes("v1", "v2"))

    assert sorted(fetch.calls) == sorted([MIRROR_BASE, MIRROR_HEAD])
    assert changes, "a fixture pair with hand-labelled breaking changes produced none"


@pytest.mark.parametrize(
    "from_hash, to_hash",
    [(None, "h-new"), ("h-old", None), (None, None)],
    ids=["missing-before", "missing-after", "missing-both"],
)
def test_a_hash_missing_on_either_side_is_treated_as_changed(tmp_path, from_hash, to_hash):
    """Unknown reads as changed. Reporting "no change" from missing evidence would silently skip
    a vendor forever, and nothing would ever surface it -- the expensive failure precisely
    because it is invisible. Paying for a fetch that finds nothing is the cheap one."""
    fetch = _CountingFetch()
    sources = {"v1": _stainless(MIRROR_BASE, from_hash), "v2": _stainless(MIRROR_HEAD, to_hash)}

    list(_adapter(tmp_path, sources, fetch=fetch).fetch_changes("v1", "v2"))

    assert len(fetch.calls) == 2


# --- vendors this approach does not reach -----------------------------------------


def test_a_manifest_with_no_spec_url_yields_no_changes(tmp_path, caplog):
    """Cloudflare and Orb publish `configured_endpoints` and nothing else. That vendor still
    needs a hand-written adapter, and saying so is the honest answer -- it is not an error, and
    it must not be a silent zero either, so it is logged."""
    fetch = _CountingFetch()
    sources = {"v1": _stainless(None, "h-old"), "v2": _stainless(None, "h-new")}

    with caplog.at_level(logging.INFO, logger="sync.signals.generated.adapter"):
        changes = list(_adapter(tmp_path, sources, fetch=fetch).fetch_changes("v1", "v2"))

    assert changes == []
    assert fetch.calls == []
    assert caplog.records != []


def test_a_version_with_no_manifest_at_all_yields_no_changes(tmp_path, caplog):
    """Nothing was parsed for that commit, so there is nothing to compare against and no URL to
    fetch. Guessing the other side's URL would diff a spec against itself and report a clean
    bill of health nobody measured."""
    fetch = _CountingFetch()
    sources = {"v1": _stainless(MIRROR_BASE, "h-old")}

    with caplog.at_level(logging.INFO, logger="sync.signals.generated.adapter"):
        changes = list(_adapter(tmp_path, sources, fetch=fetch).fetch_changes("v1", "v2"))

    assert changes == []
    assert fetch.calls == []


def test_a_non_fetchable_vendor_does_not_raise(tmp_path):
    """A vendor outside this adapter's reach is a coverage gap, not a fault. Raising would make
    one such vendor abort a scan across every other."""
    sources = {"v1": _stainless(None, "h-old"), "v2": _stainless(None, "h-new")}

    assert list(_adapter(tmp_path, sources).fetch_changes("v1", "v2")) == []


# --- which artifact the diff was taken from ---------------------------------------


def test_the_vendor_published_spec_is_preferred_over_the_generator_mirror(tmp_path):
    """`openapi_spec_url` points at the generator's storage rather than the vendor's own host.
    That is a fine change hint and a weaker artifact, so where the vendor publishes a spec it
    wins."""
    fetch = _CountingFetch(bodies={MIRROR_BASE: BASE_SPEC, VENDOR_HEAD: HEAD_SPEC})

    changes = list(
        _adapter(tmp_path, _moved(), fetch=fetch, vendor_spec_urls={"v2": VENDOR_HEAD}).fetch_changes("v1", "v2")
    )

    assert VENDOR_HEAD in fetch.calls
    assert MIRROR_HEAD not in fetch.calls
    assert changes
    # Only one side came from the vendor, and a comparison is worth the weaker of its two ends.
    assert {c.raw["sync_spec_provenance"] for c in changes} == {"generator-mirror"}


def test_a_diff_taken_from_a_mirror_records_that_it_was(tmp_path):
    """A diff taken from a generator's copy is weaker evidence than one taken from the vendor,
    and a reviewer cannot weigh it without being told which they are holding."""
    changes = list(_adapter(tmp_path, _moved()).fetch_changes("v1", "v2"))

    assert {c.raw["sync_spec_provenance"] for c in changes} == {"generator-mirror"}


def test_a_diff_taken_from_the_vendor_records_that_too(tmp_path):
    fetch = _CountingFetch(bodies={VENDOR_HEAD: HEAD_SPEC, "https://api.acme.test/base.json": BASE_SPEC})
    urls = {"v1": "https://api.acme.test/base.json", "v2": VENDOR_HEAD}

    changes = list(_adapter(tmp_path, _moved(), fetch=fetch, vendor_spec_urls=urls).fetch_changes("v1", "v2"))

    assert {c.raw["sync_spec_provenance"] for c in changes} == {"vendor"}


def test_the_oasdiff_record_survives_underneath_the_provenance_key(tmp_path):
    """`raw` is what lets a better extractor re-derive against stored history instead of
    re-fetching every spec pair, so provenance is added beside the record rather than replacing
    any part of it."""
    change = list(_adapter(tmp_path, _moved()).fetch_changes("v1", "v2"))[0]

    assert change.raw["id"] == change.kind
    assert "text" in change.raw


def test_rows_carry_the_vendor_and_the_versions_they_were_asked_for(tmp_path):
    change = list(_adapter(tmp_path, _moved()).fetch_changes("v1", "v2"))[0]

    assert change.vendor_id == "acme"
    assert (change.from_version, change.to_version) == ("v1", "v2")


# --- fetching, caching, and failing -----------------------------------------------


def test_a_second_run_refetches_nothing(tmp_path):
    """A version names an immutable artifact, so a spec already on disk is what a fresh fetch
    would return. This is the same argument the Stripe adapter makes about a tag."""
    fetch = _CountingFetch()
    adapter = _adapter(tmp_path, _moved(), fetch=fetch)

    list(adapter.fetch_changes("v1", "v2"))
    calls_after_first = len(fetch.calls)
    list(adapter.fetch_changes("v1", "v2"))

    assert calls_after_first == 2
    assert len(fetch.calls) == 2


def test_an_empty_cached_file_is_not_treated_as_cached(tmp_path):
    """Zero bytes is what an interrupted or failed write leaves behind. Reading it as a cached
    spec hands oasdiff an empty file and calls whatever it says a diff."""
    fetch = _CountingFetch()
    cache = tmp_path / "specs"
    cache.mkdir(parents=True)
    (cache / "acme-v1.json").write_text("", encoding="utf-8")

    list(_adapter(tmp_path, _moved(), fetch=fetch).fetch_changes("v1", "v2"))

    assert len(fetch.calls) == 2


def test_a_cached_spec_means_a_failing_host_is_never_consulted(tmp_path):
    """The deprecation adapter falls back to a stale cache when a fetch fails, because its cache
    expires under a fixed URL. This one's cannot go stale -- a version names an immutable
    artifact -- so the same outage is survived one step earlier, by not fetching at all. Asserted
    as "the failing host was never called", which is the property that actually holds; a fallback
    inside the failure path would be unreachable code dressed as caution.
    """
    adapter = _adapter(tmp_path, _moved(), fetch=_CountingFetch())
    list(adapter.fetch_changes("v1", "v2"))

    failing = _CountingFetch(failing={MIRROR_BASE, MIRROR_HEAD})
    revived = GeneratedSpecAdapter(
        vendor_id="acme", sources=_moved(), fetch=failing, cache_dir=tmp_path / "specs",
    )

    assert list(revived.fetch_changes("v1", "v2"))
    assert failing.calls == []


def test_a_failed_fetch_with_nothing_cached_raises_rather_than_reporting_no_changes(tmp_path):
    """An outage that reads as "this vendor changed nothing" is the failure this whole adapter
    is meant to catch, arriving from our own side."""
    fetch = _CountingFetch(failing={MIRROR_BASE, MIRROR_HEAD})

    with pytest.raises(RuntimeError):
        list(_adapter(tmp_path, _moved(), fetch=fetch).fetch_changes("v1", "v2"))


def test_correlating_generated_spec_adapter_resolves_operation_for_request(tmp_path: Path):
    sdk_dest = tmp_path / "sdk_source"
    shutil.copytree(FIXTURES / "sdk_sources" / "anthropic_python", sdk_dest, dirs_exist_ok=True)
    adapter = CorrelatingGeneratedSpecAdapter(
        vendor_id="anthropic",
        sources={},
        fetch=_CountingFetch({}),
        cache_dir=tmp_path / "cache",
        sdk_source=sdk_dest,
    )
    assert adapter.uncorrelatable_reason is None

    # Instance route with placeholder
    op = adapter.operation_for_request("GET", "/v1/models/claude-3-5-sonnet-20241022")
    assert op is not None
    assert op.http_method == "get"
    assert op.path == "/v1/models/{model_id}"
    assert op.operation_id == "GET /v1/models/{model_id}"

    # Collection route
    op_list = adapter.operation_for_request("POST", "/v1/messages")
    assert op_list is not None
    assert op_list.http_method == "post"
    assert op_list.path == "/v1/messages"

    # Unknown route returns None
    assert adapter.operation_for_request("DELETE", "/v1/unknown/resource") is None


def test_unsupported_unstaged_generated_adapter_declares_uncorrelatable_reason(tmp_path: Path):
    adapter = GeneratedSpecAdapter(
        vendor_id="openai",
        sources={},
        fetch=_CountingFetch({}),
        cache_dir=tmp_path / "cache",
        sdk_source=None,
    )
    assert adapter.uncorrelatable_reason is not None
    assert "no staged SDK source" in adapter.uncorrelatable_reason
    assert not hasattr(adapter, "operation_for_request")


def test_both_entry_points_answer_one_operation_the_same_way(tmp_path: Path):
    """`operation_id` is what a finding joins a vendor change against, so the two resolvers
    have to agree on it or one operation occupies two keys.

    A rule that read the specification states the vendor's own id; a rule that read a checkout
    states none and the route is synthesised. The divergence this catches is one-sided: the
    symbol path was taught to honour a stated id while the correlator kept synthesising, which
    would file the static and observed rungs of one operation under different names and join
    neither to the other.
    """
    adapter = CorrelatingGeneratedSpecAdapter(
        vendor_id="acme",
        sources={},
        fetch=_CountingFetch({}),
        cache_dir=tmp_path / "cache",
    )
    stated = ExtractedOperation(
        symbol="charges.retrieve",
        http_method="GET",
        path="/v1/charges/{charge}",
        operation_id="GetChargesCharge",
        service_id="Charges",
    )
    adapter._extracted_symbols = lambda: {"charges.retrieve": stated}

    by_symbol = adapter.operation_for_symbol("acme.charges.retrieve")
    by_request = adapter.operation_for_request("GET", "/v1/charges/ch_123")

    assert by_symbol is not None and by_request is not None
    assert by_symbol == by_request
    assert by_request.operation_id == "GetChargesCharge"
    assert by_request.service_id == "Charges"


def test_a_staged_symbol_map_resolves_without_any_checkout(tmp_path: Path):
    """The uniform tier could only resolve a symbol from a staged SDK *checkout*.

    Both hand-written adapters resolve from a staged `symbols.json` that their preparer wrote, so
    until the tier can read one, moving stripe or twilio onto it would be a silent downgrade --
    every call site stops resolving and the run reports zero findings rather than an error.
    """
    staged = tmp_path / "symbols.json"
    staged.write_text(
        (Path("vendor-cache") / "stripe" / "symbols.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    adapter = GeneratedSpecAdapter(
        vendor_id="stripe",
        sources={},
        fetch=_CountingFetch({}),
        cache_dir=tmp_path / "cache",
        symbol_map_path=staged,
    )

    op = adapter.operation_for_symbol("stripe.charges.retrieve")

    assert op is not None
    assert op.operation_id == "GetChargesCharge"
    assert op.http_method == "get"
    assert op.path == "/v1/charges/{charge}"


def test_a_staged_map_missing_a_field_loads_rather_than_raising(tmp_path: Path):
    """The committed caches carry four keys per entry and no `service_id`.

    They were baked before the builder emitted one, `benchmark/corpus/symbol_map.yaml` pins their
    bytes, and rebaking them inside this sequence is the thing the pin forbids -- so the reader
    must treat every field but the route as optional.
    """
    staged = tmp_path / "symbols.json"
    staged.write_text(
        '{"acme.things.list": {"operation_id": "ListThings", '
        '"http_method": "get", "path": "/v1/things"}}',
        encoding="utf-8",
    )
    adapter = GeneratedSpecAdapter(
        vendor_id="acme",
        sources={},
        fetch=_CountingFetch({}),
        cache_dir=tmp_path / "cache",
        symbol_map_path=staged,
    )

    op = adapter.operation_for_symbol("acme.things.list")

    assert op is not None and op.operation_id == "ListThings"
    assert op.service_id is None


def test_a_staged_map_is_preferred_over_a_checkout_rule(tmp_path: Path):
    """Both staged at once is a real configuration -- stripe stages a map and could stage a
    checkout -- and the map is the richer answer, so it wins rather than racing."""
    sdk_dest = tmp_path / "sdk_source"
    shutil.copytree(FIXTURES / "sdk_sources" / "anthropic_python", sdk_dest, dirs_exist_ok=True)
    staged = tmp_path / "symbols.json"
    staged.write_text(
        '{"anthropic.messages.create": {"operation_id": "MessagesCreate", '
        '"http_method": "post", "path": "/v1/messages", "service_id": "Messages"}}',
        encoding="utf-8",
    )
    adapter = GeneratedSpecAdapter(
        vendor_id="anthropic",
        sources={},
        fetch=_CountingFetch({}),
        cache_dir=tmp_path / "cache",
        sdk_source=sdk_dest,
        symbol_map_path=staged,
    )

    op = adapter.operation_for_symbol("anthropic.messages.create")

    assert op is not None
    assert op.operation_id == "MessagesCreate"
    assert op.service_id == "Messages"

