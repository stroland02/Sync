"""Vendor deprecation tables — the findings that carry a deadline."""

from sync.signals.deprecations.catalogue import (
    ModelDeprecation,
    parse_deprecation_table,
    to_vendor_changes,
    urgency,
)

__all__ = [
    "ModelDeprecation",
    "parse_deprecation_table",
    "to_vendor_changes",
    "urgency",
]
