"""A tool's `inputSchema` read as a flat table of arguments, or refused.

MCP says `inputSchema` is "a JSON Schema object" and says nothing more. In practice servers
emit `{"type": "object", "properties": {...}, "required": [...]}`, which reads flat -- but
nothing in the protocol obliges them to, and the moment a schema composes with `allOf`,
`anyOf`, `oneOf`, `not` or `$ref`, the properties a caller must pass are no longer at the top
level. Reading the top level anyway finds nothing and reports nothing, which is
indistinguishable from a tool that did not change.

So this refuses instead, and the caller turns the refusal into a row. What can and cannot be
read is the honest limit of the whole adapter:

- **Presence and required-ness: read.** A property in `properties`, a name in `required`.
- **Accepted types: read, when the subschema names them.** `type` as a string or a list.
- **Everything else about a value: not read.** A tightened `enum`, a new `pattern`, a lowered
  `maximum`, `additionalProperties` flipping under a nested object -- each of these narrows
  what the server accepts and none of them is compared here. Deciding in general whether one
  JSON Schema accepts less than another is schema subsumption, which is not a diff.
- **Nested objects: not read.** Only the top level of `properties` is compared, so a required
  field appearing inside an object-typed argument is invisible.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Keywords whose presence means the properties are not where a flat read looks. `$ref` is
# included even though it is not strictly a composition keyword: it moves the schema
# elsewhere, which has the same consequence for a reader that does not resolve it.
_COMPOSITION = ("allOf", "anyOf", "oneOf", "not", "$ref")


@dataclass(frozen=True)
class Argument:
    """One argument a tool accepts.

    `types` is `None` rather than empty when the subschema names no type or composes one.
    Empty would read as "accepts nothing", and the difference decides whether a type
    comparison happens at all.
    """

    name: str
    types: frozenset[str] | None
    required: bool


@dataclass(frozen=True)
class ArgumentTable:
    """A tool's arguments, and what the server does with one it does not recognise.

    `rejects_unknown` is `additionalProperties: false`, and it is the difference between a
    caller getting a validation error it can see and a caller having an argument silently
    dropped. JSON Schema's default is to permit additional properties, so absence means the
    argument is accepted and ignored.
    """

    arguments: dict[str, Argument]
    rejects_unknown: bool


def read_arguments(input_schema: dict[str, Any]) -> ArgumentTable | None:
    """The tool's arguments, or `None` when a flat read would be a lie."""
    if any(keyword in input_schema for keyword in _COMPOSITION):
        return None

    properties = input_schema.get("properties", {})
    if not isinstance(properties, dict):
        return None

    declared = input_schema.get("required", [])
    required = set(declared) if isinstance(declared, list) else set()

    arguments: dict[str, Argument] = {}
    for name, subschema in properties.items():
        if not isinstance(subschema, dict):
            return None
        arguments[name] = Argument(
            name=name,
            types=_accepted_types(subschema),
            required=name in required,
        )

    return ArgumentTable(arguments=arguments, rejects_unknown=input_schema.get("additionalProperties") is False)


def _accepted_types(subschema: dict[str, Any]) -> frozenset[str] | None:
    if any(keyword in subschema for keyword in _COMPOSITION):
        return None
    declared = subschema.get("type")
    if isinstance(declared, str):
        return frozenset({declared})
    if isinstance(declared, list) and all(isinstance(member, str) for member in declared):
        return frozenset(declared)
    return None
