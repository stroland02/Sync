"""Vendor deprecation tables — the findings that carry a deadline."""

from sync.signals.deprecations.adapter import (
    ANTHROPIC,
    CLOUDFLARE,
    DEPRECATION_SOURCES,
    OPENAI,
    DeprecationAdapter,
    DeprecationSource,
    http_fetch,
    model_deprecation_sources,
    parameter_deprecation_sources,
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
    "DEPRECATION_SOURCES",
    "OPENAI",
    "DeprecationAdapter",
    "DeprecationSource",
    "ModelDeprecation",
    "ParameterDeprecation",
    "http_fetch",
    "model_deprecation_sources",
    "parse_deprecation_table",
    "parameter_deprecation_sources",
    "parameters_to_vendor_changes",
    "parse_parameter_deprecations",
    "to_vendor_changes",
    "urgency",
]
