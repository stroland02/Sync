"""Sentry error payloads reduced to response shapes.

The first link in the chain the drift detector needs. `ObservedShape` holds the reduction,
`GraphStore.record_observed_shape` holds the baseline, and `ObservedDriftDetector` compares that
baseline against the published specification -- but nothing was writing to it. This does, from a
source that costs the customer nothing: the payloads are already captured.

What that buys, and what it costs
---------------------------------
Error payloads need no SDK install, no interceptor and no new permission, which is why the spec
sequences this source first. They are also **biased toward failures**, and that bias does not
average out with volume. A `402` response carries the fields a declined charge carries; the
baseline assembled from a thousand of them describes what Stripe sends when something goes wrong,
not what it sends normally. Two consequences worth stating plainly rather than discovering later:
a field that only appears on success may never enter the baseline at all, and a field that only
appears on failure will look universal. `source` is part of `observed_shape`'s natural key
precisely so this sample can never be merged into one drawn from normal traffic, and the drift
detector's sample floor is doing real work here.

How array elements are addressed
--------------------------------
Every element of an array collapses to one path segment, `-`, so ten refunds produce one
`/refunds/data/-/status` rather than ten indexed pointers. Indexing would make array position
part of a field's identity: a response carrying three elements tomorrow would read as new fields
appearing, one carrying a single element would read as fields disappearing, and every array in
the API would look like drift on every observation. `-` is the one array token RFC 6901 defines,
so the pointer stays a valid pointer; the cost is that an object key spelled literally `-` is
indistinguishable from an element, which is accepted rather than solved.

Collapsing the index does not collapse the shapes. Elements that genuinely differ -- one refund
whose `reason` is a string, another whose `reason` is null -- stay two observations of one path,
because that difference is exactly what the detector reads.

One payload, one observation per shape
--------------------------------------
`sample_count` is evidence that a shape is established, and the detector's floor rests on it. A
single response carrying a fifty-element array would clear a floor of thirty on its own, so a
payload contributes at most one observation per distinct `(field_path, json_type)`. Frequency
comes from many payloads, which is the only place it means anything.

Values
------
None leave this module. Paths, types and nullability are recorded; the sole exception is an enum
member the vendor published, and that decision belongs to `ObservedShape.from_observation` rather
than being made again here. Callers that supply no published enums retain nothing, which is the
safe default.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Iterator, Mapping, Sequence

from sync.core import ObservedShape
from sync.graph.store import GraphStore

log = logging.getLogger(__name__)

ARRAY_ELEMENT = "-"
"""The segment standing for any element of an array. See the module docstring."""

SOURCE = "error-payload"


def _escape(key: str) -> str:
    """RFC 6901 escaping. `~` first, or escaping `/` would then escape its own tilde."""
    return key.replace("~", "~0").replace("/", "~1")


def walk(body: Any, pointer: str = "") -> Iterator[tuple[str, Any]]:
    """Every node of a decoded body, as (JSON Pointer, value).

    Containers are yielded as well as their leaves: a field the specification declares an object
    and traffic sends as an array is drift, and the detector can only see it if the container
    carries a type of its own. The root is not yielded -- no specification declares the document
    itself as a field, and an empty pointer is not a field path anyone can compare against.
    """
    if isinstance(body, dict):
        for key, child in body.items():
            child_pointer = f"{pointer}/{_escape(str(key))}"
            yield child_pointer, child
            yield from walk(child, child_pointer)
    elif isinstance(body, list):
        element_pointer = f"{pointer}/{ARRAY_ELEMENT}"
        for element in body:
            yield element_pointer, element
            yield from walk(element, element_pointer)


class SentryShapeReader:
    """Turns one Sentry event into `observed_shape` rows.

    The operation is resolved by a callable the caller supplies, not by this module: mapping a
    request URL onto an operation is a fact about one vendor's URL conventions, and vendor
    knowledge lives in that vendor's adapter. A request this module cannot attribute is dropped
    rather than guessed, because a baseline filed under the wrong operation produces findings
    against fields that operation never returns.
    """

    def __init__(
        self,
        store: GraphStore,
        vendor_id: str,
        resolve_operation: Callable[[str, str], str | None],
        spec_enums: Mapping[str, Mapping[str, Sequence[str]]] | None = None,
    ) -> None:
        self._store = store
        self._vendor_id = vendor_id
        self._resolve_operation = resolve_operation
        self._spec_enums = spec_enums or {}

    def ingest(self, event: Mapping[str, Any]) -> int:
        """Record the shapes in one event. Returns how many rows were written.

        A payload that is not what it claims to be yields nothing and raises nothing: this reads
        data a third party produced, and one malformed event must not stop the rest of a batch.
        It is logged rather than swallowed, because a source that quietly stopped working looks
        exactly like a vendor who changed nothing.
        """
        parsed = self._parse(event)
        if parsed is None:
            return 0

        operation_id, body, seen_at = parsed
        enums = self._spec_enums.get(operation_id, {})

        shapes: dict[tuple[str, str], ObservedShape] = {}
        for field_path, value in walk(body):
            shape = ObservedShape.from_observation(
                vendor_id=self._vendor_id,
                operation_id=operation_id,
                field_path=field_path,
                value=value,
                source=SOURCE,
                spec_enum_values=list(enums.get(field_path, ())),
            )
            shape.first_seen = seen_at
            shape.last_seen = seen_at
            # One payload counts once per distinct shape. The key is the table's own grain minus
            # the columns fixed for this event.
            shapes.setdefault((shape.field_path, shape.json_type), shape)

        for shape in shapes.values():
            self._store.record_observed_shape(shape)
        return len(shapes)

    def _parse(self, event: Mapping[str, Any]) -> tuple[str, Any, datetime] | None:
        """The three things an event has to yield, or `None` with a reason logged.

        Only the event's structure is reported. A rejected payload's contents are the thing this
        module exists to discard, and a log file is a column with worse access control.
        """
        if not isinstance(event, Mapping):
            log.warning("sentry event is %s, not a mapping", type(event).__name__)
            return None

        request = event.get("request")
        response = self._response_context(event)
        if not isinstance(request, Mapping) or response is None:
            log.warning(
                "sentry event %s carries no request/response pair to read",
                self._event_id(event),
            )
            return None

        method, url = request.get("method"), request.get("url")
        if not isinstance(method, str) or not isinstance(url, str):
            log.warning("sentry event %s has no usable request method or url", self._event_id(event))
            return None

        operation_id = self._resolve_operation(method, url)
        if operation_id is None:
            # Not a defect: most requests in a customer's Sentry project are not this vendor's.
            log.debug("sentry event %s resolves to no operation", self._event_id(event))
            return None

        body = response.get("data")
        if not isinstance(body, (dict, list)):
            log.warning(
                "sentry event %s carries a %s response body, which has no fields to record",
                self._event_id(event), type(body).__name__,
            )
            return None

        return operation_id, body, self._seen_at(event)

    def _response_context(self, event: Mapping[str, Any]) -> Mapping[str, Any] | None:
        """Sentry's response context, where an SDK that captured the body puts it."""
        contexts = event.get("contexts")
        if not isinstance(contexts, Mapping):
            return None
        response = contexts.get("response")
        return response if isinstance(response, Mapping) else None

    def _event_id(self, event: Mapping[str, Any]) -> str:
        event_id = event.get("event_id")
        return event_id if isinstance(event_id, str) else "<no event_id>"

    def _seen_at(self, event: Mapping[str, Any]) -> datetime:
        """When the response was seen, not when it was ingested.

        An error payload is forwarded long after the response arrived, and the drift detector
        decides severity by asking which shape was seen first. Stamping ingestion time would
        make every backfilled batch look like the newest behaviour the vendor has. A timestamp
        that cannot be read costs the payload nothing: it is metadata about the observation, not
        the observation.
        """
        raw = event.get("timestamp")
        if isinstance(raw, str):
            try:
                return datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                log.warning("sentry event %s has an unreadable timestamp", self._event_id(event))
        return datetime.now(timezone.utc)
