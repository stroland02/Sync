"""Vendor deprecation tables — the findings that carry a deadline."""

from sync.signals.deprecations.adapter import (
    ANTHROPIC,
    OPENAI,
    DeprecationAdapter,
    DeprecationSource,
    http_fetch,
)
from sync.signals.deprecations.catalogue import (
    ModelDeprecation,
    parse_deprecation_table,
    to_vendor_changes,
    urgency,
)

__all__ = [
    "ANTHROPIC",
    "OPENAI",
    "DeprecationAdapter",
    "DeprecationSource",
    "ModelDeprecation",
    "http_fetch",
    "parse_deprecation_table",
    "to_vendor_changes",
    "urgency",
]
