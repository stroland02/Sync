"""Tier routing: which strategy is cheap enough, and safe enough, for a given change."""

from sync.route.disposition import (
    AUTOMATIC_CODES,
    Disposition,
    DispositionCode,
    decide_tier,
    disposition,
)
from sync.route.facts import routing_facts
from sync.route.matrix import (
    AGENT,
    CODEMOD,
    NO_PATCH,
    TEMPLATED,
    RoutingFacts,
    Tier,
    catalogue_index,
    route,
)
from sync.route.templates import apply_rules, model_literal_swap

__all__ = [
    "AGENT",
    "AUTOMATIC_CODES",
    "CODEMOD",
    "NO_PATCH",
    "TEMPLATED",
    "Disposition",
    "DispositionCode",
    "RoutingFacts",
    "Tier",
    "apply_rules",
    "catalogue_index",
    "decide_tier",
    "disposition",
    "model_literal_swap",
    "route",
    "routing_facts",
]
