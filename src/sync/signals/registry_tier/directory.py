"""Reading a public OpenAPI directory, which says an API exists rather than what it changed.

Tier 0 discovers a specification from a generated SDK's own committed manifest. This is tier 1:
a public directory of OpenAPI definitions, where supporting the directory supports every vendor
in it at once. `docs/superpowers/specs/2026-07-29-sync-adaptive-vendor-substrate.md` carries the
argument; what follows is what was measured against `api.apis.guru/v2/list.json` rather than
assumed about it.

**The change trigger is better than tier 0's, and it is the reason this tier is affordable.**
There is no hash or checksum, but every version carries `added` and `updated` timestamps and the
whole catalogue is a single document. So one fetch answers what moved across every vendor, and a
specification is downloaded only when its timestamp advances. Tier 0 has to poll one manifest per
SDK repository; this polls one file for everything.

**What it cannot do is speak for the vendor, and that decides what the tier is for.** `swaggerUrl`
points at the directory's own storage rather than the vendor's host, so an entry is a mirror. A
large share of entries are `openapiVer` 2.0, meaning Swagger rather than OpenAPI 3, so `oasdiff`
needs converted input for those -- and a converted mirror is a third derivation from the vendor's
truth. The threat model's rule applies with more force here than anywhere else in the codebase: a
signature proves origin, not correctness, and nobody at the vendor signed this.

So this module discovers. It answers which APIs exist, which versions they have, and when each
last moved, which is what dependency intake needs to tell a customer that a declared dependency
is watchable. It deliberately does not produce `VendorChange` rows: promoting a registry-derived
change to something a pull request rests on requires the vendor-hosted artifact the directory
merely points at.

This module is pure. It parses a document and returns records; it never fetches. Network access
belongs to the caller, which keeps the parsing testable against a committed fixture and keeps the
no-network-in-tests rule intact -- the same division `sync.signals.generated.manifest` uses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Where the specification behind an entry actually came from. Only one value today, and it is
# spelled out rather than left implicit because the rung is the point: a binding derived from a
# mirror must never be indistinguishable from one derived from the vendor's published artifact.
RegistryProvenance = str
MIRROR: RegistryProvenance = "registry-mirror"


@dataclass(frozen=True)
class RegistryVersion:
    """One version of one API, as the directory describes it."""

    version: str
    updated: str
    spec_url: str
    # '2.0' is Swagger and needs converting before `oasdiff` will read it. Recorded here rather
    # than discovered at diff time, because a caller choosing what to download should know what
    # it is about to get.
    openapi_version: str
    provenance: RegistryProvenance = MIRROR


@dataclass(frozen=True)
class RegistryEntry:
    """One API in the directory, with every version it declares."""

    api_id: str
    preferred: str | None
    versions: dict[str, RegistryVersion]


def parse_directory(document: dict[str, Any]) -> list[RegistryEntry]:
    """Every usable entry in a directory document.

    A public directory is untrusted input and it is large. A malformed entry is skipped rather
    than raised on: one bad row must not cost the other thousands, and an entry with no versions
    has nothing to say about what changed, so skipping loses nothing that could have been used.
    """
    entries: list[RegistryEntry] = []
    for api_id, body in document.items():
        if not isinstance(body, dict):
            continue
        raw_versions = body.get("versions")
        if not isinstance(raw_versions, dict) or not raw_versions:
            continue

        versions: dict[str, RegistryVersion] = {}
        for version, detail in raw_versions.items():
            if not isinstance(detail, dict):
                continue
            spec_url = detail.get("swaggerUrl")
            updated = detail.get("updated") or detail.get("added")
            if not isinstance(spec_url, str) or not isinstance(updated, str):
                continue
            versions[version] = RegistryVersion(
                version=version,
                updated=updated,
                spec_url=spec_url,
                openapi_version=str(detail.get("openapiVer") or ""),
            )

        if not versions:
            continue
        preferred = body.get("preferred")
        entries.append(
            RegistryEntry(
                api_id=api_id,
                preferred=preferred if isinstance(preferred, str) else None,
                versions=versions,
            )
        )
    return entries


def versions_after(entries: list[RegistryEntry], watermark: str) -> list[tuple[RegistryEntry, str]]:
    """Every version whose `updated` is later than `watermark`, as (entry, version) pairs.

    This is the whole economy of the tier: the caller holds one watermark, fetches one document,
    and learns what moved without downloading a single specification.

    Compared as strings, which is correct rather than lazy for this data -- the directory writes
    ISO-8601 UTC with a fixed shape, and that sorts lexicographically. A `datetime` parse would
    add a failure mode (a malformed timestamp raising mid-scan) to buy nothing.
    """
    moved: list[tuple[RegistryEntry, str]] = []
    for entry in entries:
        for version, detail in entry.versions.items():
            if detail.updated > watermark:
                moved.append((entry, version))
    return moved
