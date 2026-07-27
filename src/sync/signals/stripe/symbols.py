"""Derives the SDK-symbol to OpenAPI-operation map from Stripe's own specification.

Stripe generates its TypeScript SDK from this specification, so the mapping is
mechanical rather than guessed. This logic is deliberately Stripe-specific and
belongs to the adapter — never to sync.core.
"""

from __future__ import annotations

import re
from typing import Any


def _camel(segment: str) -> str:
    head, *rest = segment.split("_")
    return head + "".join(part.capitalize() for part in rest)


def _method_name(http_method: str, is_instance: bool) -> str | None:
    match (http_method.lower(), is_instance):
        case ("post", False):
            return "create"
        case ("get", False):
            return "list"
        case ("get", True):
            return "retrieve"
        case ("post", True):
            return "update"
        case ("delete", True):
            return "del"
        case _:
            return None


def build_symbol_map(spec: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Map `stripe.<resource>.<method>` onto operation metadata."""
    mapping: dict[str, dict[str, str]] = {}

    for path, operations in spec.get("paths", {}).items():
        match = re.match(r"^/v1/([a-z_]+)(/\{[^}]+\})?/?$", path)
        if not match:
            continue
        resource_segment, instance_suffix = match.group(1), match.group(2)
        is_instance = instance_suffix is not None
        resource = _camel(resource_segment)

        for http_method, operation in operations.items():
            if not isinstance(operation, dict):
                continue
            method_name = _method_name(http_method, is_instance)
            if method_name is None:
                continue
            operation_id = operation.get("operationId")
            if not operation_id:
                continue
            mapping[f"stripe.{resource}.{method_name}"] = {
                "operation_id": operation_id,
                "http_method": http_method.lower(),
                "path": path,
            }

    return mapping
