"""Derives the SDK-symbol to OpenAPI-operation map from Stripe's own specification.

Stripe generates its TypeScript SDK from this specification, so the mapping is
mechanical rather than guessed. This logic is deliberately Stripe-specific and
belongs to the adapter — never to sync.core.
"""

from __future__ import annotations

import re
from typing import Any


class SymbolCollision(Exception):
    """Two operations derived the same SDK symbol."""


def _camel(segment: str) -> str:
    head, *rest = segment.split("_")
    return head + "".join(part.capitalize() for part in rest)


def _addresses_one_resource(operations: dict[str, Any]) -> bool:
    """Whether a path without an id segment still addresses a single resource.

    Stripe's list endpoints answer with the `data`/`has_more` envelope; a
    singleton such as `/v1/balance` answers with a bare `$ref` to the resource
    schema. The distinction is stated by the specification, so it needs no
    knowledge of which resources Stripe happens to treat as singletons.

    Only a positive `$ref` counts. Reading it the other way round — treating
    anything without a `data` property as a singleton — turns every path whose
    GET response this function cannot see into an instance path, which collides
    a collection's `retrieve` with its own instance's.
    """
    get = operations.get("get")
    if not isinstance(get, dict):
        return False
    schema = (
        get.get("responses", {})
        .get("200", {})
        .get("content", {})
        .get("application/json", {})
        .get("schema", {})
    )
    return "$ref" in schema


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
    """Map `stripe.<resource>.<method>` onto operation metadata.

    A symbol claimed twice raises rather than overwriting. Overwriting makes the
    losing operation unreachable from any call site, so a breaking change against
    it can never produce a finding — a failure invisible at every later stage.
    Raising is affordable because collisions are not a property of Stripe's
    specification: v1900, v2320 and v2330 each derive zero. One therefore means
    the derivation is wrong, and a map that silently holds the wrong answer is
    worse than one that refuses to build.
    """
    mapping: dict[str, dict[str, str]] = {}

    for path, operations in spec.get("paths", {}).items():
        match = re.match(r"^/v1/([a-z_]+)(/\{[^}]+\})?/?$", path)
        if not match:
            continue
        resource_segment, instance_suffix = match.group(1), match.group(2)
        is_instance = instance_suffix is not None or _addresses_one_resource(operations)
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
            symbol = f"stripe.{resource}.{method_name}"
            existing = mapping.get(symbol)
            if existing is not None:
                raise SymbolCollision(
                    f"{symbol} derives from two operations: "
                    f"{existing['operation_id']} ({existing['http_method'].upper()} {existing['path']}) "
                    f"and {operation_id} ({http_method.upper()} {path})"
                )
            mapping[symbol] = {
                "operation_id": operation_id,
                "http_method": http_method.lower(),
                "path": path,
            }

    return mapping
