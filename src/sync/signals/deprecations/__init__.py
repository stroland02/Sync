"""Vendor deprecation tables — the findings that carry a deadline."""

from sync.signals.deprecations.adapter import (
    ANTHROPIC,
    CLOUDFLARE,
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
from sync.signals.deprecations.parameters import (
    ParameterDeprecation,
    parameters_to_vendor_changes,
    parse_parameter_deprecations,
)

__all__ = [
    "ANTHROPIC",
    "CLOUDFLARE",
    "OPENAI",
    "DeprecationAdapter",
    "DeprecationSource",
    "ModelDeprecation",
    "ParameterDeprecation",
    "http_fetch",
    "parse_deprecation_table",
    "parameters_to_vendor_changes",
    "parse_parameter_deprecations",
    "to_vendor_changes",
    "urgency",
]
