"""Reading a spec location out of a generated SDK's committed manifest.

An SDK generator leaves a manifest in the repository it generates, naming the specification
it worked from. It does that for its own reasons -- reproducible regeneration -- which is what
makes this reliable: no vendor has to cooperate, and no agreement can be withdrawn.

`docs/superpowers/specs/2026-07-27-sync-adapter-targets.md` has the argument. The short version
is that supporting a generator costs a day and yields every vendor using it, while supporting a
vendor under a known generator costs a configuration line. Coverage stops scaling with vendor
count and starts scaling with generator count, and there are few generators.

This module is pure. It parses text and returns a description; it never fetches. Network access
belongs to the caller, which keeps the parsing testable against committed fixtures and keeps
the no-network-in-tests rule intact.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml

STAINLESS_MANIFEST = ".stats.yml"
SPEAKEASY_MANIFEST = ".speakeasy/workflow.yaml"

# Hosts that serve a generator's mirror of a spec rather than the vendor's own copy. A mirror is
# fine for learning *when* something changed and is not the authoritative artifact.
_GENERATOR_HOSTS = (
    "storage.googleapis.com/stainless-sdk-openapi-specs",
    "registry.speakeasyapi.dev",
)

# The one scheme-less location shape that names a real artifact rather than a local file.
# Matched literally rather than by "has no scheme", because `./openapi.yaml` is also scheme-less
# and names nothing anyone but the generator's own working copy can resolve.
_SPEAKEASY_REGISTRY = "registry.speakeasyapi.dev/"


@dataclass(frozen=True)
class SpecSource:
    """Where a generated SDK's specification lives, and what can be learned cheaply."""

    generator: str
    """Which convention produced this -- 'stainless' or 'speakeasy'."""

    spec_url: str | None = None
    """An absolute URL, when the manifest names one.

    Several real manifests publish nothing but `configured_endpoints` -- Cloudflare and Orb
    both do -- so a source can be genuine and still not fetchable. A relative path is treated
    as absent, because nothing downstream can resolve it.
    """

    spec_reference: str | None = None
    """A location the manifest names that this build cannot retrieve, recorded rather than dropped.

    Speakeasy lets a source name a registry reference -- `registry.speakeasyapi.dev/org/ws/spec:v2`
    -- instead of a URL, and resolving one needs the vendor's own bearer token. Discarding it
    returned `None`, which put such a vendor in the bucket for a manifest naming no specification
    at all: the opposite claim. Set only when no input in the manifest named a fetchable URL.
    """

    spec_hash: str | None = None
    """Content hash of the spec, when the manifest publishes one. Absent for several vendors."""

    endpoint_count: int | None = None
    """Operations the SDK was generated against. A free spec-side denominator for coverage."""

    generator_hosted: bool = False
    """Whether `spec_url` points at a generator's mirror rather than the vendor's own host."""

    has_overlays: bool = False
    """Whether the generator applied overlays before generating.

    When true the fetched spec is not byte-identical to the generation input. Diffing two
    fetches is still sound -- both sides get the same treatment -- but comparing spec against
    SDK is not.
    """

    @property
    def is_fetchable(self) -> bool:
        """Whether there is a spec to retrieve at all.

        False for a manifest carrying only an endpoint count. Such a vendor still contributes
        a coverage denominator and still needs a hand-written adapter, so it is reported rather
        than discarded.
        """
        return self.spec_url is not None

    @property
    def has_cheap_change_trigger(self) -> bool:
        """Whether drift can be detected without downloading the spec."""
        return self.spec_hash is not None

    def changed_from(self, other: SpecSource) -> bool:
        """Whether the spec plausibly changed relative to `other`.

        Without a hash on both sides the honest answer is "unknown", and unknown is reported as
        changed. Reporting "unchanged" from missing evidence would silently skip a vendor
        forever, which is the expensive failure precisely because it is invisible.
        """
        if self.spec_hash is None or other.spec_hash is None:
            return True
        return self.spec_hash != other.spec_hash


def _load(text: str) -> Any:
    """Parsed YAML, or None for anything unusable.

    These files come from arbitrary public repositories. One vendor committing a broken
    manifest must not abort a scan across every other vendor, so a parse failure is a
    non-result rather than an exception.
    """
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError:
        return None


def _is_absolute_url(location: str) -> bool:
    return location.startswith(("http://", "https://"))


def _generator_hosted(url: str) -> bool:
    return any(host in url for host in _GENERATOR_HOSTS)


def _parse_stainless(document: dict[str, Any]) -> SpecSource | None:
    url = document.get("openapi_spec_url")
    if not isinstance(url, str) or not _is_absolute_url(url):
        url = None

    hash_value = document.get("openapi_spec_hash")
    endpoints = document.get("configured_endpoints")

    # A manifest naming neither a spec nor an endpoint count says nothing at all.
    if url is None and not isinstance(endpoints, int):
        return None

    return SpecSource(
        generator="stainless",
        spec_url=url,
        spec_hash=hash_value if isinstance(hash_value, str) else None,
        endpoint_count=endpoints if isinstance(endpoints, int) else None,
        generator_hosted=_generator_hosted(url) if url else False,
    )


def _parse_speakeasy(document: dict[str, Any]) -> SpecSource | None:
    sources = document.get("sources")
    if not isinstance(sources, dict):
        return None

    # A fetchable URL anywhere in the manifest wins over a reference anywhere else, so the
    # unresolvable case is only reported once every input has been rejected.
    unresolvable: tuple[str, bool] | None = None

    for source in sources.values():
        if not isinstance(source, dict):
            continue
        for entry in source.get("inputs") or ():
            location = entry.get("location") if isinstance(entry, dict) else None
            if not isinstance(location, str):
                continue
            if not _is_absolute_url(location):
                if unresolvable is None and location.startswith(_SPEAKEASY_REGISTRY):
                    unresolvable = (location, bool(source.get("overlays")))
                continue
            return SpecSource(
                generator="speakeasy",
                spec_url=location,
                generator_hosted=_generator_hosted(location),
                has_overlays=bool(source.get("overlays")),
            )

    if unresolvable is not None:
        location, overlays = unresolvable
        return SpecSource(
            generator="speakeasy",
            spec_reference=location,
            has_overlays=overlays,
        )
    return None


_PARSERS = {
    STAINLESS_MANIFEST: _parse_stainless,
    SPEAKEASY_MANIFEST: _parse_speakeasy,
}


def parse_manifest(name: str, text: str) -> SpecSource | None:
    """The spec source a manifest names, or None when it names none usable.

    `name` selects the convention, so content alone is never enough -- a `.stats.yml` body
    committed as `README.md` is not a manifest, and treating it as one would let any file in a
    repository steer a fetch.
    """
    parser = _PARSERS.get(name)
    if parser is None:
        return None

    document = _load(text)
    if not isinstance(document, dict):
        return None

    return parser(document)
