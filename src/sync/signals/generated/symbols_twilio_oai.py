"""Derives the SDK-symbol to OpenAPI-operation map from Twilio's own specification.

Twilio generates its libraries from these documents, so the mapping is mechanical rather
than guessed -- but it is mechanical along different axes than Stripe's, and the two do not
share a line of logic. Stripe reads the resource from the URL and needs a second 10 MB
document to learn the verb. Twilio is the exact inverse: the verb is written into
`operationId` and the URL frequently does not name the resource at all.

Three sources, in this order, and each is stated by the vendor rather than inferred:

- `x-twilio.mountName` names the library's attribute when the URL would get it wrong.
  `/v1/Voice/{Sid}` is `client.insights.v1.calls`, and nothing about "Voice" says "calls".
- The last literal path segment supplies the name when no mount is stated, which is most of
  them: across five product documents at tag 2.6.9, `mountName` covers 28 of the 95 paths
  declaring operations -- 29%, ranging from 9% in `twilio_video_v1` to 47% in
  `twilio_messaging_v1`.
- `x-twilio.parent` chains a sub-resource under its owner, so `/v1/Voice/{CallSid}/Events`
  becomes `calls.events` rather than a top-level `events`.

Two fields that look like sources and are not. The response schema name refs the wire
resource rather than the mount: `/v1/Video/Rooms` refs `insights.v1.video_room_summary`
where the library says `rooms`. And `x-twilio.className` names the generated class rather
than the attribute -- reading it would lift stated coverage from 29% to 45% and be wrong on
every one of the ten paths where it disagrees with the path segment, which is the direction
that binds call sites to operations nobody called.

This logic is Twilio-specific and belongs to the adapter, never to sync.core.
"""

from __future__ import annotations

import re
from typing import Any

_PASCAL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_LEADING_WORD = re.compile(r"^[A-Z][a-z]+")
_PLACEHOLDER = re.compile(r"^\{.*\}$")


class SymbolCollision(Exception):
    """Two operations derived the same SDK symbol."""


# Every `operationId` across the five product documents sampled -- 155 operations -- begins
# with one of these five words, and each maps to the method of the same name in
# `twilio-python`. That is a closed vocabulary where Stripe's needed a table of six verbs,
# a comma-splitting rule and an HTTP fallback, because Twilio states the verb outright.
#
# A leading word absent from this table yields no symbol, which is the conservative
# direction: inventing a method name from an unverified word is how a call site binds to an
# operation nobody called.
_SDK_VERBS = {
    "Fetch": "fetch",
    "List": "list",
    "Create": "create",
    "Update": "update",
    "Delete": "delete",
}


def _snake(segment: str) -> str:
    """`InsightsDomains` -> `insights_domains`, `Rooms` -> `rooms`."""
    return _PASCAL_BOUNDARY.sub("_", segment).lower()


def _version_prefix(path: str) -> str:
    """The path's own first segment.

    `x-twilio.parent` is spelled without it -- the parent of `/v1/Voice/{CallSid}/Events` is
    given as `/Voice/{Sid}` -- so resolving a parent means putting it back. It is read from
    the path rather than from the `version` argument because the two are not the same string
    on every product: `twilio_api_v2010.json` serves its operations under `/2010-04-01/`
    while the library mounts them at `.api.v2010`.
    """
    segments = path.strip("/").split("/")
    return f"/{segments[0]}" if segments and segments[0] else ""


def _mount(path: str, body: dict[str, Any]) -> str | None:
    """The library attribute this path is exposed as.

    `None` when the path has no literal segment to fall back on, which is a path built
    entirely of placeholders. No such path exists in this product; answering `None` rather
    than an empty string keeps a future one out of the map instead of mounting it under the
    empty name.
    """
    extension = body.get("x-twilio")
    if isinstance(extension, dict):
        mount_name = extension.get("mountName")
        if isinstance(mount_name, str) and mount_name:
            return mount_name

    literals = [s for s in path.strip("/").split("/")[1:] if s and not _PLACEHOLDER.match(s)]
    return _snake(literals[-1]) if literals else None


def _chain(path: str, paths: dict[str, Any], seen: frozenset[str] = frozenset()) -> list[str] | None:
    """The full mount chain for a path, outermost first.

    Walks `x-twilio.parent` upward. A parent naming a path the document does not contain
    yields `None` rather than a chain missing its root: a sub-resource silently mounted at
    the top level resolves symbols nobody can write, and does it without any error.

    `seen` guards a parent cycle. No published document contains one; a cycle would
    otherwise recurse until the interpreter stopped it, which is a crash rather than a
    diagnosis.
    """
    body = paths.get(path)
    if not isinstance(body, dict) or path in seen:
        return None

    mount = _mount(path, body)
    if mount is None:
        return None

    extension = body.get("x-twilio")
    parent = extension.get("parent") if isinstance(extension, dict) else None
    if not isinstance(parent, str) or not parent:
        return [mount]

    ancestors = _chain(_version_prefix(path) + parent, paths, seen | {path})
    return None if ancestors is None else [*ancestors, mount]


def build_symbol_map(spec: dict[str, Any], domain: str, version: str) -> dict[str, dict[str, Any]]:
    """Map `twilio.<domain>.<version>.<mount chain>.<method>` onto operation metadata.

    `domain` and `version` are supplied by the caller rather than read from the document.
    Neither is recoverable from the content: the title is prose ("Twilio - Insights") and
    the URL version is a date on the oldest product. They come from the filename, which is
    configuration the adapter holds.

    A symbol claimed twice raises rather than overwriting, for the reason Stripe's map does:
    an overwritten operation is unreachable from every call site, so a breaking change
    against it can never raise a finding, and nothing reports that it was lost.
    """
    paths = spec.get("paths", {})
    mapping: dict[str, dict[str, str]] = {}

    for path, body in paths.items():
        if not isinstance(body, dict):
            continue
        chain = _chain(path, paths)
        if chain is None:
            continue

        for http_method, operation in body.items():
            if not isinstance(operation, dict):
                continue
            operation_id = operation.get("operationId")
            if not operation_id:
                continue
            # The product this operation belongs to, in Twilio's own words -- the same reading
            # `stripe/symbols.py` gives its document's `tags`.
            tags = operation.get("tags")
            service_id = tags[0] if isinstance(tags, list) and tags and isinstance(tags[0], str) else None
            leading = _LEADING_WORD.match(operation_id)
            method_name = _SDK_VERBS.get(leading.group(0)) if leading else None
            if method_name is None:
                continue

            # Both spellings, each carrying the language that writes it. `twilio-python` exposes
            # `call_summaries` and `twilio-node` exposes `callSummaries` -- the same operation
            # under two names, and only the mount chain differs between the SDKs.
            #
            # Recorded at build time rather than rewritten at lookup time, which is what the
            # retired adapter did. A rewrite is invisible to anything holding the map, so a
            # caller reading it could not tell the two spellings apart; and the tier that now
            # serves every vendor filters on `languages`, which is machinery stripe's rule
            # already used. `CI-W588` re-pinned the digest for this deliberately.
            base = ["twilio", domain, version]
            for spelling, languages in _spellings(chain, method_name).items():
                symbol = ".".join([*base, spelling])
                existing = mapping.get(symbol)
                if existing is not None:
                    raise SymbolCollision(
                        f"{symbol} derives from two operations: "
                        f"{existing['operation_id']} "
                        f"({existing['http_method'].upper()} {existing['path']}) "
                        f"and {operation_id} ({http_method.upper()} {path})"
                    )
                mapping[symbol] = {
                    "operation_id": operation_id,
                    "http_method": http_method.lower(),
                    "path": path,
                    "service_id": service_id,
                    "languages": languages,
                }

    return mapping


_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])([A-Z])")


def _spellings(chain: list[str], method_name: str) -> dict[str, list[str]]:
    """Each SDK's spelling of one chain, as spelling to the languages that write it.

    Only the mount chain differs between the two SDKs -- vendor, domain, version and method
    segments are identical -- so this varies the middle. Where the two agree there is one key
    serving both languages, because emitting it twice would be one entry wearing two names.
    """
    snake = ".".join([*chain, method_name])
    camel = ".".join([_camel(segment) for segment in chain] + [method_name])
    if snake == camel:
        return {snake: ["python", "typescript"]}
    return {snake: ["python"], camel: ["typescript"]}


def _camel(segment: str) -> str:
    head, *rest = segment.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in rest)
