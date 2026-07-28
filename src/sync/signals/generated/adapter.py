"""A `VendorAdapter` driven by a generated SDK's manifest rather than by hand-written knowledge.

`manifest.py` reads the file a generator commits; this turns what it read into `VendorChange`
rows. The point, argued in `docs/superpowers/specs/2026-07-27-sync-adapter-targets.md`, is that
coverage should scale with generator count rather than vendor count: supporting a generator costs
a day and yields every vendor using it, while supporting one more vendor under a known generator
costs a configuration line.

The cheap trigger is the economics
----------------------------------
A Stainless manifest publishes `openapi_spec_hash`. Comparing that string across two commits of
the SDK repository is free -- it is a text file in a public repository -- and it answers "did the
specification move" without downloading anything. Only a vendor whose hash actually moved pays
for two spec fetches and an oasdiff run. A vendor whose hash is unchanged costs nothing at all,
which is what makes polling many vendors affordable rather than an idea about polling many
vendors.

Unknown reads as changed, never as unchanged. A manifest with no hash on either side says nothing
about whether the spec moved, and answering "unchanged" there would silently skip that vendor
forever with nothing to surface it. Paying for a fetch that finds nothing is the cheap mistake.

What this adapter cannot reach
------------------------------
Several real manifests -- Cloudflare's and Orb's among them -- publish `configured_endpoints` and
no URL at all. `SpecSource.is_fetchable` reports that, and such a vendor yields no changes and is
logged rather than raising: it still needs a hand-written adapter, and it must not abort a scan
across every other vendor. It is not an error, and it is not silence either.

Which artifact the diff was taken from
--------------------------------------
`openapi_spec_url` points at the generator's own storage rather than the vendor's host. That is
sound as a change *hint* and weaker as evidence, so a vendor-published URL is preferred where the
caller supplies one, and every row records which was used under `sync_spec_provenance`. The
oasdiff record underneath is untouched -- `raw` is what lets a better extractor re-derive against
stored history instead of re-fetching every spec pair.

A manifest reporting overlays is diffed anyway. The fetched spec is then not byte-identical to
what the generator consumed, but both sides of the diff get the same treatment, so a comparison
between two fetches stays sound; only comparing a spec against the SDK would not be.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Iterable, Mapping

from sync.core import OperationRef, VendorChange
from sync.signals.generated.manifest import SpecSource
from sync.signals.oasdiff import run_oasdiff_breaking, to_vendor_changes

log = logging.getLogger(__name__)

Fetch = Callable[[str], str]

PROVENANCE_KEY = "sync_spec_provenance"
"""Where a row records which artifact it was diffed from. Namespaced because it sits beside
oasdiff's own record rather than in it."""

VENDOR_PUBLISHED = "vendor"
GENERATOR_MIRROR = "generator-mirror"


def http_fetch(url: str, timeout: float = 60.0) -> str:
    """A plain GET returning decoded text. The default `Fetch` for real runs.

    `urllib` rather than a dependency, and the decode is explicit because the platform default
    is the locale codepage on Windows and a specification is full of non-ASCII descriptions.

    Tests never call this -- they inject their own fetch -- which is what keeps the suite free of
    network access.
    """
    import urllib.request

    request = urllib.request.Request(url, headers={"User-Agent": "sync-generated-adapter"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - caller-supplied https URLs
        return response.read().decode("utf-8")


class GeneratedSpecAdapter:
    """Turns two commits of a generated SDK's manifest into the vendor changes between them."""

    def __init__(
        self,
        vendor_id: str,
        sources: Mapping[str, SpecSource],
        fetch: Fetch,
        cache_dir: Path | str,
        vendor_spec_urls: Mapping[str, str] | None = None,
    ) -> None:
        self._vendor_id = vendor_id
        self._sources = sources
        self._fetch = fetch
        self._cache_dir = Path(cache_dir)
        self._vendor_spec_urls = vendor_spec_urls or {}

    @property
    def vendor_id(self) -> str:
        return self._vendor_id

    def operation_for_symbol(self, symbol: str) -> OperationRef | None:
        """Always `None`: this adapter knows a specification, not an SDK's symbol scheme.

        Mapping `acme.charges.create` onto an operation needs to know how one generator names
        methods for one vendor, which is exactly the per-vendor knowledge this adapter exists to
        do without. Inventing a convention would put it back, and would put it back as a guess
        that fails silently -- an unresolvable symbol yields no finding, so nobody would learn
        the convention was wrong.

        A vendor needing symbol resolution needs a hand-written adapter for that part. This one
        still supplies the changes.
        """
        return None

    def fetch_changes(self, from_version: str, to_version: str) -> Iterable[VendorChange]:
        base = self._sources.get(from_version)
        head = self._sources.get(to_version)

        if base is None or head is None:
            missing = from_version if base is None else to_version
            log.info(
                "%s: no manifest parsed for %s, so there is nothing to compare",
                self._vendor_id, missing,
            )
            return []

        if not (base.is_fetchable and head.is_fetchable):
            # Cloudflare and Orb publish an endpoint count and no URL. That is a coverage gap
            # this approach does not close, and it is reported rather than discarded: the vendor
            # still needs a hand-written adapter and still contributes a coverage denominator.
            log.info(
                "%s: manifest names no spec to fetch (%s endpoints configured); "
                "this vendor needs a hand-written adapter",
                self._vendor_id, head.endpoint_count,
            )
            return []

        if not head.changed_from(base):
            # The whole economic argument. Two identical hashes mean the specification did not
            # move, and nothing is downloaded.
            log.debug("%s: spec hash unmoved between %s and %s", self._vendor_id, from_version, to_version)
            return []

        base_url, base_provenance = self._spec_url(from_version, base)
        head_url, head_provenance = self._spec_url(to_version, head)

        base_path = self._spec(from_version, base_url)
        head_path = self._spec(to_version, head_url)

        records = run_oasdiff_breaking(base_path, head_path)
        changes = to_vendor_changes(
            records, vendor_id=self._vendor_id, from_version=from_version, to_version=to_version
        )

        # The weaker of the two sides is what the diff is worth: a comparison against a mirror
        # is a mirror-grade comparison even if the other end came from the vendor.
        provenance = (
            VENDOR_PUBLISHED
            if base_provenance == head_provenance == VENDOR_PUBLISHED
            else GENERATOR_MIRROR
        )
        for change in changes:
            change.raw[PROVENANCE_KEY] = provenance
        return changes

    def _spec_url(self, version: str, source: SpecSource) -> tuple[str, str]:
        """The URL to fetch this version from, and what that artifact is worth.

        A vendor-published URL wins where the caller supplied one. `source.spec_url` is not None
        here -- `fetch_changes` has already established the source is fetchable.
        """
        vendor_url = self._vendor_spec_urls.get(version)
        if vendor_url is not None:
            return vendor_url, VENDOR_PUBLISHED
        assert source.spec_url is not None
        return source.spec_url, GENERATOR_MIRROR

    def _spec(self, version: str, url: str) -> Path:
        """A local copy of one version's specification.

        A version names an immutable artifact, so a populated cache file is already what a fresh
        fetch would return and is used without calling out. A zero-byte file is not treated as
        cached: that is what an interrupted or failed write leaves behind, and handing it to
        oasdiff would produce a diff against nothing and call the result a clean bill of health.

        A failed fetch raises. An outage that reads as "this vendor changed nothing" is the exact
        failure this adapter exists to catch, arriving from our own side, so it is never allowed
        to look like an empty result.

        There is deliberately no stale-cache fallback in the failure path, which is where this
        departs from `sync.signals.deprecations.adapter`. That cache expires -- a deprecation page
        changes under a fixed URL -- so it can be stale while a refetch is attempted, and falling
        back to yesterday's copy is a real choice. Here a version names an immutable artifact, so
        a cached copy is never stale and the check above has already returned it. A fetch is only
        ever attempted when nothing is cached, which leaves the fallback unreachable rather than
        cautious.
        """
        destination = self._cache_dir / f"{self._vendor_id}-{version}.json"
        if destination.exists() and destination.stat().st_size > 0:
            return destination

        try:
            body = self._fetch(url)
        except Exception as exc:
            raise RuntimeError(
                f"{self._vendor_id} specification for {version} could not be retrieved and "
                f"nothing usable is cached ({url}): {exc}"
            ) from exc

        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(body, encoding="utf-8")
        return destination
