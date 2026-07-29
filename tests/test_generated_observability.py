"""A vendor Sync cannot look at must say so, rather than reporting that nothing changed.

`docs/superpowers/reports/2026-07-29-generated-vendor-noise.md` §5 found the failure while
measuring something else: a manifest naming a live, unversioned endpoint publishes the same
string in every commit, so both ends of a version pair resolve to one document, `oasdiff`
compares it against itself, and the vendor reports zero records however much it shipped. Zero
records is also what a healthy vendor reports, and telling those apart is the product.

`2026-07-29-vercel-observability.md` carries the measurement and the three options weighed.

**The condition under test is a property of the two locations, never of who published them.**
Speakeasy names a live endpoint for one vendor and a tagged registry reference for another;
Stainless rotates a URL per revision and would be in exactly this position the day it stopped.
So every case below is stated in terms of what the manifests resolve to, and the two generators
appear only to prove neither is the thing being detected.

No test here touches the network. The fetch is injected and the manifests are committed.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from sync.signals.generated import SPEAKEASY_MANIFEST, STAINLESS_MANIFEST, parse_manifest
from sync.signals.generated.adapter import (
    NO_MANIFEST,
    NO_SPECIFICATION,
    ONE_DOCUMENT,
    GeneratedSpecAdapter,
)

FIXTURES = Path(__file__).parent / "fixtures"
SPECS = FIXTURES / "specs"
MANIFESTS = FIXTURES / "manifests"

BASE_SPEC = (SPECS / "charges_base.json").read_text(encoding="utf-8")
HEAD_SPEC = (SPECS / "charges_revision.json").read_text(encoding="utf-8")

MIRROR_BASE = "https://storage.googleapis.com/stainless-sdk-openapi-specs/acme/base.json"
MIRROR_HEAD = "https://storage.googleapis.com/stainless-sdk-openapi-specs/acme/head.json"

# What `vercel/sdk` names, verbatim from the committed manifest. Measured 2026-07-29: the file is
# byte-identical at all 12 commits that touched `.speakeasy/workflow.lock` across six weeks, and
# two fetches of the URL three seconds apart returned the same 9,757,380 bytes.
LIVE_ENDPOINT = "https://openapi.vercel.sh/"


class _CountingFetch:
    """Stands in for the network, and counts. Whether a fetch happened is the assertion in half
    these cases, and only a counter can carry it -- reading the code cannot."""

    def __init__(self, bodies: dict[str, str] | None = None):
        self.bodies = bodies if bodies is not None else {
            MIRROR_BASE: BASE_SPEC, MIRROR_HEAD: HEAD_SPEC, LIVE_ENDPOINT: BASE_SPEC,
        }
        self.calls: list[str] = []

    def __call__(self, url: str) -> str:
        self.calls.append(url)
        return self.bodies[url]


def _stainless(url: str | None, spec_hash: str | None = None, endpoints: int = 42):
    """Built by the real parser, so these cases exercise the chain a run exercises."""
    lines = [f"configured_endpoints: {endpoints}"]
    if url is not None:
        lines.append(f"openapi_spec_url: {url}")
    if spec_hash is not None:
        lines.append(f"openapi_spec_hash: {spec_hash}")
    source = parse_manifest(STAINLESS_MANIFEST, "\n".join(lines) + "\n")
    assert source is not None
    return source


def _speakeasy(filename: str):
    source = parse_manifest(
        SPEAKEASY_MANIFEST, (MANIFESTS / filename).read_text(encoding="utf-8")
    )
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


# --- the core assertion -----------------------------------------------------------


def test_one_url_at_both_commits_is_unobservable_rather_than_zero_changes(tmp_path):
    """The defect, stated as the property it violates.

    Both manifests are the real `vercel/sdk` workflow, which is the same bytes at every commit
    measured. Reporting no changes here would be indistinguishable from a vendor that shipped
    nothing, which is the one distinction this product exists to draw.
    """
    sources = {"v1": _speakeasy("vercel.workflow.yaml"), "v2": _speakeasy("vercel.workflow.yaml")}

    verdict = _adapter(tmp_path, sources).observability("v1", "v2")

    assert verdict.observable is False
    assert verdict.reason == ONE_DOCUMENT


def test_a_caller_can_tell_unobservable_from_unchanged(tmp_path):
    """The distinguishing test the whole change exists to pass.

    Both pairs answer `fetch_changes` with an empty list. One of them looked and found nothing;
    the other could not look. A caller holding only the list cannot tell, and that is precisely
    the silent-vendor failure `_spec` refuses to accept from a fetch outage.
    """
    unobservable = _adapter(
        tmp_path,
        {"v1": _speakeasy("vercel.workflow.yaml"), "v2": _speakeasy("vercel.workflow.yaml")},
    )
    unchanged = _adapter(
        tmp_path,
        {"v1": _stainless(MIRROR_BASE, "same"), "v2": _stainless(MIRROR_HEAD, "same")},
    )

    assert list(unobservable.fetch_changes("v1", "v2")) == []
    assert list(unchanged.fetch_changes("v1", "v2")) == []

    assert unobservable.observability("v1", "v2").observable is False
    assert unchanged.observability("v1", "v2").observable is True


def test_an_unobservable_pair_fetches_nothing(tmp_path):
    """The cost half of the same defect. Two fetches of a ~9.7 MB document, moments apart, to
    diff it against itself and produce nothing -- paid on every scan. A pair that cannot be
    compared must not be downloaded."""
    fetch = _CountingFetch()
    sources = {"v1": _speakeasy("vercel.workflow.yaml"), "v2": _speakeasy("vercel.workflow.yaml")}

    changes = list(_adapter(tmp_path, sources, fetch=fetch).fetch_changes("v1", "v2"))

    assert changes == []
    assert fetch.calls == []


def test_an_unobservable_pair_is_logged_rather_than_raised(tmp_path, caplog):
    """A vendor outside reach is a coverage gap, not a fault: raising would make one such vendor
    abort a scan across every other. The log has to name the location, because the repair is to
    supply a versioned one."""
    sources = {"v1": _speakeasy("vercel.workflow.yaml"), "v2": _speakeasy("vercel.workflow.yaml")}

    with caplog.at_level(logging.INFO, logger="sync.signals.generated.adapter"):
        list(_adapter(tmp_path, sources).fetch_changes("v1", "v2"))

    assert LIVE_ENDPOINT in caplog.text


# --- without this, a change that refuses everything passes -------------------------


def test_two_distinct_versioned_speakeasy_documents_still_diff(tmp_path):
    """The guard against over-refusing. Speakeasy's `location` carries a versioned path as
    readily as a live one -- `mistralai/client-ts` names a tagged registry revision, read
    2026-07-29 -- so the generator is not what makes a pair unobservable."""
    fetch = _CountingFetch(bodies={
        "https://specs.acme.test/openapi/2026-06-18.json": BASE_SPEC,
        "https://specs.acme.test/openapi/2026-07-28.json": HEAD_SPEC,
    })
    sources = {
        "v1": _speakeasy("acme-versioned-v1.workflow.yaml"),
        "v2": _speakeasy("acme-versioned-v2.workflow.yaml"),
    }
    adapter = _adapter(tmp_path, sources, fetch=fetch)

    assert adapter.observability("v1", "v2").observable is True
    changes = list(adapter.fetch_changes("v1", "v2"))
    assert changes, "two distinct Speakeasy documents produced no rows"
    assert len(fetch.calls) == 2


def test_the_stainless_path_is_unaffected(tmp_path):
    """Both parsers feed one `SpecSource`, so a condition written for one reaches the other.
    A Stainless pair rotating its URL per revision is observable and diffs, exactly as before."""
    fetch = _CountingFetch()
    sources = {"v1": _stainless(MIRROR_BASE, "h-old"), "v2": _stainless(MIRROR_HEAD, "h-new")}
    adapter = _adapter(tmp_path, sources, fetch=fetch)

    assert adapter.observability("v1", "v2").observable is True
    assert list(adapter.fetch_changes("v1", "v2"))
    assert sorted(fetch.calls) == sorted([MIRROR_BASE, MIRROR_HEAD])


# --- the condition is the manifest's, never the generator's ------------------------


def test_a_stainless_manifest_naming_one_url_is_equally_unobservable(tmp_path):
    """The other half of the same claim, and the reason no vendor name and no generator name
    appears in the condition. A Stainless manifest whose `openapi_spec_url` stopped rotating is
    in the position Vercel is in, and must be reported the same way."""
    fetch = _CountingFetch()
    sources = {"v1": _stainless(MIRROR_BASE, "h-old"), "v2": _stainless(MIRROR_BASE, "h-new")}
    adapter = _adapter(tmp_path, sources, fetch=fetch)

    assert adapter.observability("v1", "v2").reason == ONE_DOCUMENT
    assert list(adapter.fetch_changes("v1", "v2")) == []
    assert fetch.calls == []


# --- the repair a deployment can make without a code change ------------------------


def test_a_versioned_vendor_url_makes_a_one_document_manifest_observable(tmp_path):
    """The condition is asked of what the run will actually fetch, not of what the manifest
    said, so a deployment supplying a versioned URL per version restores the vendor with no
    code change. Asking it of `spec_url` alone would refuse a pair that resolves perfectly."""
    urls = {"v1": "https://specs.acme.test/openapi/2026-06-18.json",
            "v2": "https://specs.acme.test/openapi/2026-07-28.json"}
    fetch = _CountingFetch(bodies={urls["v1"]: BASE_SPEC, urls["v2"]: HEAD_SPEC})
    sources = {"v1": _speakeasy("vercel.workflow.yaml"), "v2": _speakeasy("vercel.workflow.yaml")}

    adapter = _adapter(tmp_path, sources, fetch=fetch, vendor_spec_urls=urls)

    assert adapter.observability("v1", "v2").observable is True
    assert list(adapter.fetch_changes("v1", "v2"))


# --- whatever was done about spec_hash, the cheap trigger still decides -------------


def test_an_unmoved_hash_still_skips_the_diff(tmp_path):
    """The economic argument, re-asserted against the new gate. An agreeing hash is evidence the
    document did not move, so the pair was examined -- observable, and empty."""
    fetch = _CountingFetch()
    sources = {"v1": _stainless(MIRROR_BASE, "same"), "v2": _stainless(MIRROR_HEAD, "same")}
    adapter = _adapter(tmp_path, sources, fetch=fetch)

    assert adapter.observability("v1", "v2").observable is True
    assert list(adapter.fetch_changes("v1", "v2")) == []
    assert fetch.calls == []


def test_a_moved_hash_still_runs_the_diff(tmp_path):
    fetch = _CountingFetch()
    sources = {"v1": _stainless(MIRROR_BASE, "h-old"), "v2": _stainless(MIRROR_HEAD, "h-new")}

    assert list(_adapter(tmp_path, sources, fetch=fetch).fetch_changes("v1", "v2"))
    assert len(fetch.calls) == 2


def test_an_agreeing_hash_answers_even_when_one_url_serves_both(tmp_path):
    """Evidence beats the location. A hash agreeing on both sides says the specification did not
    move, which is an answer rather than a failure to look, so the pair is observable even
    though only one document backs it. Ordering the location check first would relabel a
    vendor Sync can genuinely answer for as one it cannot."""
    sources = {"v1": _stainless(MIRROR_BASE, "same"), "v2": _stainless(MIRROR_BASE, "same")}

    assert _adapter(tmp_path, sources).observability("v1", "v2").observable is True


# --- the reasons that already existed, now answerable the same way -----------------


def test_the_three_ways_of_not_looking_are_told_apart(tmp_path):
    """`fetch_changes` returned an empty list for three unrelated reasons and named none of them
    to a caller. They are different repairs -- configure the version, write a hand-written
    adapter, supply a versioned URL -- so one verdict that cannot distinguish them is no better
    than the silence it replaced."""
    no_manifest = _adapter(tmp_path, {"v1": _stainless(MIRROR_BASE, "h-old")})
    no_url = _adapter(tmp_path, {"v1": _stainless(None, "h-old"), "v2": _stainless(None, "h-new")})
    one_document = _adapter(
        tmp_path,
        {"v1": _speakeasy("vercel.workflow.yaml"), "v2": _speakeasy("vercel.workflow.yaml")},
    )

    assert no_manifest.observability("v1", "v2").reason == NO_MANIFEST
    assert no_url.observability("v1", "v2").reason == NO_SPECIFICATION
    assert one_document.observability("v1", "v2").reason == ONE_DOCUMENT


@pytest.mark.parametrize(
    "sources, reason, expected",
    [
        ({"v1": _stainless(MIRROR_BASE, "h-old")}, NO_MANIFEST, "v2"),
        ({"v1": _stainless(None), "v2": _stainless(None)}, NO_SPECIFICATION, "hand-written"),
        (
            {"v1": _stainless(MIRROR_BASE, "a"), "v2": _stainless(MIRROR_BASE, "b")},
            ONE_DOCUMENT,
            MIRROR_BASE,
        ),
    ],
    ids=[NO_MANIFEST, NO_SPECIFICATION, ONE_DOCUMENT],
)
def test_every_reason_carries_a_detail_a_reader_can_act_on(tmp_path, sources, reason, expected):
    """A reason code routes; a detail is what an operator reads. A verdict that is queryable and
    says nothing would have replaced silence with a shrug, so each detail owes its reader the
    specific thing to go and fix: which version failed to parse, that the repair is a
    hand-written adapter, or which location is serving both ends of the diff."""
    verdict = _adapter(tmp_path, sources).observability("v1", "v2")

    assert verdict.reason == reason
    assert expected in verdict.detail


# --- naming nothing is not naming one thing twice -----------------------------------


def test_naming_no_url_at_all_is_reported_as_its_own_failure(tmp_path):
    """Cloudflare's shape, and the reason the location comparison sits behind `is_fetchable`
    rather than in front of it. Two sources that both name nothing would compare equal, and
    reporting them as one document would name the wrong repair -- that vendor needs a
    hand-written adapter, not a versioned URL."""
    sources = {"v1": _stainless(None), "v2": _stainless(None)}

    assert _adapter(tmp_path, sources).observability("v1", "v2").reason == NO_SPECIFICATION
