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


def _spellings(segment: str, method_name: str) -> dict[str, list[str]]:
    """Each SDK's name for one operation, as symbol to the languages that write it.

    **The snake_case spelling is read and the camelCase one is derived, not the other way
    round.** `segment` is the specification's own path segment -- `/v1/payment_intents` gives
    `payment_intents` -- and that string is verbatim what `stripe-python` exposes:
    `StripeClient.payment_intents` is declared in `stripe/_v1_services.py`, a file whose own
    header says it is generated from Stripe's OpenAPI specification. Checked against v2330
    rather than assumed: of the 34 multi-word segments this pattern reaches, 31 are accessor
    names in that file letter for letter. So this is the same kind of reading `x-stableId` gets
    for method names, not a rule invented about one vendor's punctuation.

    That direction is the whole point. Recovering `payment_intents` by un-camelling
    `paymentIntents` would be a guess that fails silently -- `_camel` is not injective, and
    `GeneratedSpecAdapter.operation_for_symbol` refuses exactly that class of transformation
    because an unresolvable symbol yields no finding and nobody learns the convention was
    wrong. Here nothing has to be inverted: the source spelling was in hand all along and the
    map was throwing it away.

    The three segments that are not top-level `stripe-python` accessors -- `external_accounts`,
    `link_account_sessions` and `linked_accounts` -- are nested under another resource in that
    SDK. They still get a Python key, because it names the operation the vendor's own path
    names and no Python program writes it either way; what they do not get is a claim that the
    accessor was verified, which is why they are listed here rather than silently included.

    One key when the two SDKs agree. `charges` is one word, so both write `stripe.charges.list`
    and emitting it twice would be one entry wearing two names; the languages list is what says
    the spelling is shared rather than TypeScript's alone.
    """
    python = f"stripe.{segment}.{method_name}"
    typescript = f"stripe.{_camel(segment)}.{method_name}"
    if python == typescript:
        return {python: ["python", "typescript"]}
    return {python: ["python"], typescript: ["typescript"]}


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


# A token of an `x-stableId`, mapped to the method stripe-node exposes for it.
# Sixty-five distinct leading tokens appear across v2330's 521 stable ids, but
# only eight of them sit on a path the pattern below can reach: these six, plus
# `unified` and `top_level`, which qualify a verb rather than being one --
# `unified_list_tax_ids` is `TaxIds.list`, `top_level_list_invoice_payments` is
# `InvoicePayments.list`. `delete` is the one entry that is not its own method
# name: JavaScript reserved the word, so `Customers.ts`, `TaxIds.ts`,
# `Coupons.ts`, `InvoiceItems.ts` and `Accounts.ts` all spell it `del`.
#
# A token absent from this table leaves the operation on the HTTP rule. That is
# the conservative direction: it repeats an answer the map already gave, where
# accepting an unchecked token would invent a method name from a word nobody
# verified against the SDK.
_SDK_VERBS = {
    "retrieve": "retrieve",
    "list": "list",
    "create": "create",
    "update": "update",
    "delete": "del",
    "cancel": "cancel",
}


def _verb_from_stable_id(stable_id: str) -> str | None:
    """The SDK method name Stripe records against an operation, if it names one.

    The verb is not always the leading token: `unified_list_tax_ids` and
    `top_level_retrieve_invoice_payment` qualify it first, so tokens are read in
    order and the first recognised one wins.

    `x-stableId` is also sometimes a comma-separated list rather than one id --
    eight operations carry one in v2330, `/v1/tokens` POST carrying six -- and
    only the first entry speaks for the operation. Every list in that release
    agrees on its leading verb, so the split changes no answer today; it is here
    because scanning across a comma lets an entry that names no verb borrow one
    from a sibling, and a verb borrowed from another operation is not a fallback,
    it is a wrong answer stated confidently.
    """
    first_entry, _, _ = stable_id.partition(",")
    for token in first_entry.split("_"):
        verb = _SDK_VERBS.get(token)
        if verb is not None:
            return verb
    return None


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


def build_symbol_map(
    spec: dict[str, Any], sdk_spec: dict[str, Any] | None = None
) -> dict[str, dict[str, str]]:
    """Map `stripe.<resource>.<method>` onto operation metadata.

    The method name comes from the vendor when `sdk_spec` is supplied. Stripe
    publishes `openapi/spec3.sdk.json` beside the specification at the same tags,
    and its `x-stableId` states the SDK method for an operation outright. That
    matters because the design document names this derivation as the piece most
    likely not to generalise: a rule we invented from HTTP verbs and path shape
    is a guess about one vendor's conventions, whereas a rule read out of the
    vendor's own generator input is not. `sdk_spec` is optional and absence is a
    supported input, not an error — Stripe added `x-stableId` somewhere around
    v2320, and v1900's sdk document carries none — so an operation the document
    does not cover keeps the HTTP-verb reading.

    A symbol claimed twice raises rather than overwriting. Overwriting makes the
    losing operation unreachable from any call site, so a breaking change against
    it can never produce a finding — a failure invisible at every later stage.
    Raising is affordable because collisions are not a property of Stripe's
    specification: v1900, v2320 and v2330 each derive zero. One therefore means
    the derivation is wrong, and a map that silently holds the wrong answer is
    worse than one that refuses to build.
    """
    mapping: dict[str, dict[str, str]] = {}
    sdk_paths = (sdk_spec or {}).get("paths", {})

    for path, operations in spec.get("paths", {}).items():
        match = re.match(r"^/v1/([a-z_]+)(/\{[^}]+\})?/?$", path)
        if not match:
            continue
        # A vendor document is a boundary, so the shape is checked rather than trusted.
        # `_addresses_one_resource` reaches `.get` on this immediately, so without the guard one
        # malformed path item cost the entire map with an `AttributeError` naming a builtin type
        # -- every call site for the vendor unresolved, for one bad key. Twilio's builder guards
        # the same layer, and `tests/test_symbol_map_declines.py` is where the two are held to
        # the same answer.
        if not isinstance(operations, dict):
            continue
        resource_segment, instance_suffix = match.group(1), match.group(2)
        is_instance = instance_suffix is not None or _addresses_one_resource(operations)
        resource = _camel(resource_segment)

        for http_method, operation in operations.items():
            if not isinstance(operation, dict):
                continue
            stable_id = sdk_paths.get(path, {}).get(http_method, {}).get("x-stableId")
            method_name = _verb_from_stable_id(stable_id) if stable_id else None
            if method_name is None:
                method_name = _method_name(http_method, is_instance)
            if method_name is None:
                continue
            operation_id = operation.get("operationId")
            if not operation_id:
                continue
            for symbol, languages in _spellings(resource_segment, method_name).items():
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
                    "languages": languages,
                }

    return mapping
