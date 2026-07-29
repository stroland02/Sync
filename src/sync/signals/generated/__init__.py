"""Vendor discovery via the manifests SDK generators commit."""

from sync.signals.generated.adapter import (
    DEFAULT_GENERATOR,
    EXTRACTORS,
    GENERATOR_MIRROR,
    PROVENANCE_KEY,
    VENDOR_PUBLISHED,
    GeneratedSpecAdapter,
    http_fetch,
)
from sync.signals.generated.manifest import (
    SPEAKEASY_MANIFEST,
    STAINLESS_MANIFEST,
    SpecSource,
    parse_manifest,
)

__all__ = [
    "DEFAULT_GENERATOR",
    "EXTRACTORS",
    "GENERATOR_MIRROR",
    "GeneratedSpecAdapter",
    "PROVENANCE_KEY",
    "SPEAKEASY_MANIFEST",
    "STAINLESS_MANIFEST",
    "SpecSource",
    "VENDOR_PUBLISHED",
    "http_fetch",
    "parse_manifest",
]
