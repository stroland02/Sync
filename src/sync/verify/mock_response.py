"""A mock response body, built from the new specification and from what was actually seen.

Step 1 of the replay verification tier in
`docs/superpowers/specs/2026-07-26-sync-observed-contract-drift.md`. Steps 2 and 3 execute the
patched call path against this body in the credential-free sandbox and assert the code consumes
it; neither is here, and nothing in this module runs anything.

**Observation outranks the specification, and that is the entire point.** The spec's argument:

    A specification says what the vendor promised. Observed traffic says what the vendor did.
    When those diverge, something changed that nobody announced.

A mock built only from the specification tests the patch against the vendor's promise. A mock
that prefers observation tests it against reality, and reality is what breaks customers. The
precedence lives in one place -- `decide_field` -- which returns the winning source by name
rather than leaving a reader to infer it from the order of two `if` branches.

Three constraints on what may come out
--------------------------------------
**No value the specification does not name.** The shape store retains no free-form value:
paths, types, nullability and counts, plus enum members the vendor's published specification
names, which are public data. There is nothing in the store to leak, and this module must not
invent something that reads real either -- every string it emits is either a published enum
member or carries `PLACEHOLDER_PREFIX`. A mock carrying what looks like a customer identifier
is a bug even when the value was fabricated, because someone will paste it into an issue
believing it.

`spec_enum_values` is trusted for shape and never for provenance: a member is emitted only if
the schema in hand also names it. A row that somehow carried an unpublished string would
otherwise be laundered into the mock by this module.

**The sample floor is the detector's floor.** `MIN_SAMPLES` is imported from
`sync.detect.observed_drift` rather than restated, because two floors that can drift is the
defect the Datadog signal module avoided by importing Sentry's array rule instead of copying
it. A shape seen fewer times than that is not a baseline -- one upstream incident supplies the
whole sample -- so below the floor the specification wins.

**Array elements are addressed the way the store writes them.** `ARRAY_ELEMENT` comes from
`sync.signals.sentry.shapes` for the same reason: observed paths collapse every element to
`-`, the one array token RFC 6901 defines, and a synthesizer expecting indexed pointers would
match nothing. Importing the token is what keeps the two ends of that agreement together.

What this module deliberately does not do
-----------------------------------------
**It does not write to the shape store.** The spec notes that every replay run is also a store
writer with `source = 'replay'`, which is how the baseline accumulates before any customer
installs anything. That writer belongs to the execution step, not here: this function is pure
and has no run to record.

**It does not synthesize a field the specification never declared.** An observed path with no
declaration is drift, and `ObservedDriftDetector` already reports it. Inventing it here would
make the mock assert a shape the vendor never promised, and step 3 checks the code's
`response_fields_read` against the contract rather than against this module's guesses.

**Both imports reach modules that open database connections.** Neither is called, and
`test_the_synthesizer_touches_no_database_and_no_network` pins that rather than leaving it to
this paragraph. Taking the two constants by import is still the right trade: a copied floor or
a copied array token is a silent divergence, and a silent divergence is worse than an import.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Literal, Mapping, Sequence

from sync.core import ObservedShape
# `JsonType` is the store's own type vocabulary and is not re-exported by `sync.core`, so it
# comes from the module that declares it -- naming the same six strings here would be a second
# vocabulary that could drift from the column's.
from sync.core.models import JsonType
from sync.detect.observed_drift import MIN_SAMPLES
from sync.signals.sentry.shapes import ARRAY_ELEMENT

# Every synthetic string starts with this. It is not a format anyone can mistake for a vendor
# identifier, which is the only property it needs.
PLACEHOLDER_PREFIX = "<sync-mock"

DecisionSource = Literal["observed", "specification"]

# What an untyped or unrecognised schema yields. `None` rather than a placeholder: a schema
# that names no type has promised nothing, and inventing a string there would put a value in
# the mock that no specification supports.
_UNTYPED = None


@dataclass(frozen=True)
class FieldDecision:
    """What one field will be, and which of the two sources decided it.

    `source` exists so the precedence is legible at the call site and in a test, and so the
    evidence line for a pull request can say which fields the mock took from reality rather
    than from the vendor's promise.
    """

    json_type: JsonType | None
    nullable: bool
    enum_values: tuple[str, ...]
    source: DecisionSource


def _spec_type(schema: Mapping[str, Any]) -> tuple[JsonType | None, bool]:
    """The declared type and whether the declaration allows null.

    Both spellings are accepted because both are in the wild: OpenAPI 3.0 writes
    `nullable: true` beside a scalar type, JSON Schema and OpenAPI 3.1 write
    `type: ["string", "null"]`.
    """
    declared = schema.get("type")
    nullable = bool(schema.get("nullable", False))

    if isinstance(declared, list):
        names = [name for name in declared if name != "null"]
        nullable = nullable or "null" in declared
        declared = names[0] if names else "null"

    if declared == "integer":
        declared = "number"
    if declared == "null":
        return "null", True
    return declared, nullable


def _published_enum(schema: Mapping[str, Any]) -> tuple[str, ...]:
    """Enum members the schema in hand names, in its own order so output is deterministic."""
    declared = schema.get("enum")
    if not isinstance(declared, list):
        return ()
    return tuple(member for member in declared if isinstance(member, str))


def decide_field(
    pointer: str,
    schema: Mapping[str, Any],
    observed: Iterable[ObservedShape],
    min_samples: int = MIN_SAMPLES,
) -> FieldDecision:
    """What this field is, with observation outranking the specification.

    The one place the precedence is decided. Everything else in this module either walks the
    schema to find fields or turns a decision into a value.

    Only observations at or above the floor are considered, and below it the specification is
    returned untouched -- not blended with the thin observation, which would be the floor
    doing half its job.

    Where several established rows describe one path, they are not in conflict: the store's
    grain is one row per `(field_path, json_type, source)`, so a field seen as both a string
    and a null is two rows describing the same field. Nullability is the disjunction of them,
    and it outranks the dominant type when the value is built, because a null the vendor
    really sends is precisely what the patched code has to survive.
    """
    spec_type, spec_nullable = _spec_type(schema)
    spec_enum = _published_enum(schema)

    established = [
        shape
        for shape in observed
        if shape.field_path == pointer and shape.sample_count >= min_samples
    ]
    if not established:
        return FieldDecision(spec_type, spec_nullable, spec_enum, "specification")

    nullable = any(
        shape.nullable_seen or shape.json_type == "null" for shape in established
    )
    typed = [shape for shape in established if shape.json_type != "null"]
    dominant = max(typed or established, key=lambda shape: shape.sample_count)

    # Trusted for shape, never for provenance: a member the schema in hand does not name is
    # dropped rather than emitted, whatever the row claims about where it came from.
    seen_members = {
        member for shape in established for member in shape.spec_enum_values
    }
    enum_values = tuple(member for member in spec_enum if member in seen_members) or spec_enum

    return FieldDecision(dominant.json_type, nullable, enum_values, "observed")


def _value_for(
    pointer: str,
    schema: Mapping[str, Any],
    observed: Sequence[ObservedShape],
    min_samples: int,
) -> Any:
    decision = decide_field(pointer, schema, observed, min_samples)

    if decision.nullable:
        # The case the tier exists to catch, so the mock shows it rather than the happy shape.
        return None
    if decision.enum_values:
        return decision.enum_values[0]

    if decision.json_type == "object":
        return _object_for(pointer, schema, observed, min_samples)
    if decision.json_type == "array":
        return _array_for(pointer, schema, observed, min_samples)
    if decision.json_type == "string":
        return f"{PLACEHOLDER_PREFIX} {pointer or '/'}>"
    if decision.json_type == "number":
        return 0
    if decision.json_type == "boolean":
        return False
    if decision.json_type == "null":
        return None
    return _UNTYPED


def _object_for(
    pointer: str,
    schema: Mapping[str, Any],
    observed: Sequence[ObservedShape],
    min_samples: int,
) -> dict[str, Any]:
    """Every declared property, not only the required ones.

    An optional field the customer's code reads is exactly as capable of breaking it as a
    required one, and a mock that omitted it would test less while looking complete.
    """
    properties = schema.get("properties") or {}
    return {
        name: _value_for(f"{pointer}/{name}", child, observed, min_samples)
        for name, child in properties.items()
    }


def _array_for(
    pointer: str,
    schema: Mapping[str, Any],
    observed: Sequence[ObservedShape],
    min_samples: int,
) -> list[Any]:
    """One element, addressed at `<pointer>/-`.

    One rather than several because element count is not something either source establishes:
    the store collapses every element to one path precisely so that array length is not part
    of a field's identity. One element exercises the element's shape, which is all this can
    honestly claim to know.
    """
    items = schema.get("items")
    if not isinstance(items, Mapping):
        return []
    return [_value_for(f"{pointer}/{ARRAY_ELEMENT}", items, observed, min_samples)]


def synthesize_mock_response(
    schema: Mapping[str, Any],
    observed: Iterable[ObservedShape] = (),
    *,
    min_samples: int = MIN_SAMPLES,
) -> Any:
    """A mock response body for one operation, from its new schema and its observed baseline.

    Pure: the caller supplies both inputs, and neither is read from a database, a
    specification fetch or a file. Deterministic, so a replay that fails is reproducible and a
    difference between two runs means the inputs changed.

    `observed` may be empty, which is the ordinary case: the store cannot be backfilled, so
    most operations have no baseline yet and the mock is the specification's shape alone.
    """
    return _value_for("", schema, tuple(observed), min_samples)
