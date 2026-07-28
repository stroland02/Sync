"""Vendor discovery via the manifests SDK generators commit."""

from sync.signals.generated.manifest import (
    SPEAKEASY_MANIFEST,
    STAINLESS_MANIFEST,
    SpecSource,
    parse_manifest,
)

__all__ = [
    "SPEAKEASY_MANIFEST",
    "STAINLESS_MANIFEST",
    "SpecSource",
    "parse_manifest",
]
