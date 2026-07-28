"""Datadog error and trace payloads reduced to response shapes.

The second feeder for the shape store. `docs/superpowers/specs/2026-07-25-sync-competitive-position.md`
sequences Sentry and Datadog as the M2 signal sources and is explicit about the shape this must
take: Sync does not build OTLP ingestion. Competing with Datadog on telemetry infrastructure is a
losing position; joining what Datadog already holds against the API dependency graph is not. So
this **reads** a search response the customer's Datadog account already answers. It receives no
telemetry, opens no port, and speaks to no Datadog client -- the caller hands it a decoded
response and this turns it into rows.

What that buys, and what it costs
---------------------------------
Nothing new is instrumented: the logs and spans are already being collected and paid for. The
sample is also **biased toward failures**, and that bias does not average out with volume. A `402`
carries the fields a declined charge carries; a baseline assembled from a thousand of them
describes what a vendor sends when something goes wrong, not what it sends normally. A field that
only appears on success may never enter the baseline, and one that only appears on failure will
look universal.

The second source makes that worse in a way worth stating rather than discovering. `source` is
part of `observed_shape`'s natural key so a biased sample can never merge into an unbiased one --
but this writes `error-payload`, which is the value Sentry writes, so these rows merge with
Sentry's rather than sitting beside them. That is the correct key: both samples are drawn from
failures and neither corrects the other's bias. The consequence is that `sample_count` clearing
the drift detector's floor is not evidence of corroboration between independent sources. Two views
of the same failure population reach the floor faster without making the baseline any more
representative of normal traffic, and once merged the row cannot say which source contributed.

Where the response body is read from
------------------------------------
`http.method`, `http.url` and `http.status_code` are Datadog's standard HTTP attribute names, and
this reads them from the nested attribute object the search APIs return. A captured **response
body** is not a standard attribute -- Datadog does not collect one, so wherever it appears the
customer's own instrumentation put it there. `DEFAULT_BODY_ATTRIBUTE` is therefore a convention
rather than a specification, and `body_attribute` exists so a caller whose pipeline named it
something else does not have to fork this module.

Two known limitations, stated rather than guessed around. Attributes are read nested, as the
documented search responses return them; a pipeline that flattens them into literal dotted keys
yields no rows and logs why, which is a visible miss rather than a silent one. And a record whose
body was never captured is not a defect -- most Datadog records are not this vendor's traffic at
all -- so it is dropped at debug level.

Arrays, and why the rule is not this module's to make
-----------------------------------------------------
`walk` and `ARRAY_ELEMENT` are imported from `sync.signals.sentry.shapes` rather than
reimplemented. Two modules feeding one table have to agree on how an array element is addressed,
or the same field reads as drift depending on which source observed it -- and a copied rule agrees
only until someone edits one copy, with nothing failing when they do, because each module's own
tests would still pass. Importing makes the agreement structural. Sentry's rule is right: every
element collapses to `-`, the one array token RFC 6901 defines, so array position never becomes
part of a field's identity.

The import is a wart and it is worth naming. A third party writing a Datadog adapter should not
depend on the Sentry one; the pointer walk is shared machinery rather than vendor knowledge, and
it belongs somewhere both adapters can reach without knowing about each other. Moving it is an
edit to a package this task does not own, so it is recorded here instead of done.

Values
------
None leave this module. Paths, types and nullability are recorded; the sole exception is an enum
member the vendor published, and that decision belongs to `ObservedShape.from_observation` rather
than being made again here. Datadog's own envelope -- `service`, `host`, `tags`, the message --
identifies the customer's infrastructure rather than the vendor's contract and is never walked.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence

from sync.core import ObservedShape
from sync.graph.store import GraphStore
from sync.signals.sentry.shapes import ARRAY_ELEMENT, walk

log = logging.getLogger(__name__)

SOURCE = "error-payload"

DEFAULT_BODY_ATTRIBUTE = "http.response.body"
"""Where a captured response body is looked for. A convention -- see the module docstring."""

_METHOD_ATTRIBUTE = "http.method"
_URL_ATTRIBUTE = "http.url"


def _dig(attributes: Mapping[str, Any], path: str) -> Any:
    """A dotted Datadog attribute name, resolved through the nested objects it names."""
    node: Any = attributes
    for segment in path.split("."):
        if not isinstance(node, Mapping):
            return None
        node = node.get(segment)
    return node


class DatadogShapeReader:
    """Turns one Datadog search response into `observed_shape` rows.

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
        body_attribute: str = DEFAULT_BODY_ATTRIBUTE,
    ) -> None:
        self._store = store
        self._vendor_id = vendor_id
        self._resolve_operation = resolve_operation
        self._spec_enums = spec_enums or {}
        self._body_attribute = body_attribute

    def ingest(self, response: Mapping[str, Any]) -> int:
        """Record the shapes in one search response. Returns how many rows were written.

        Datadog answers a search with a page of records where Sentry forwards a single event, so
        a record that is not what it claims to be is skipped and the rest of the page is still
        read. Reading only as far as the first bad record would lose most of a batch, and that
        loss looks exactly like a vendor sending fewer fields.
        """
        return sum(self._ingest_record(record) for record in self._records(response))

    def _records(self, response: Mapping[str, Any]) -> list[Any]:
        if not isinstance(response, Mapping):
            log.warning("datadog response is %s, not a mapping", type(response).__name__)
            return []

        data = response.get("data")
        if not isinstance(data, list):
            log.warning(
                "datadog response carries a %s where a page of records belongs",
                type(data).__name__,
            )
            return []
        return data

    def _ingest_record(self, record: Any) -> int:
        parsed = self._parse(record)
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
            # One record counts once per distinct shape. The key is the table's own grain minus
            # the columns fixed for this record.
            shapes.setdefault((shape.field_path, shape.json_type), shape)

        for shape in shapes.values():
            self._store.record_observed_shape(shape)
        return len(shapes)

    def _parse(self, record: Any) -> tuple[str, Any, datetime] | None:
        """The three things a record has to yield, or `None` with a reason logged.

        Only the record's structure is reported. A rejected record's contents are the thing this
        module exists to discard, and a log file is a column with worse access control.
        """
        if not isinstance(record, Mapping):
            log.warning("datadog record is %s, not a mapping", type(record).__name__)
            return None

        envelope = record.get("attributes")
        attributes = envelope.get("attributes") if isinstance(envelope, Mapping) else None
        if not isinstance(attributes, Mapping):
            log.warning("datadog record %s carries no attribute object to read", self._record_id(record))
            return None

        method = _dig(attributes, _METHOD_ATTRIBUTE)
        url = _dig(attributes, _URL_ATTRIBUTE)
        if not isinstance(method, str) or not isinstance(url, str):
            log.warning(
                "datadog record %s has no usable %s or %s",
                self._record_id(record), _METHOD_ATTRIBUTE, _URL_ATTRIBUTE,
            )
            return None

        operation_id = self._resolve_operation(method, url)
        if operation_id is None:
            # Not a defect: most requests in a customer's Datadog account are not this vendor's.
            log.debug("datadog record %s resolves to no operation", self._record_id(record))
            return None

        body = _dig(attributes, self._body_attribute)
        if not isinstance(body, (dict, list)):
            log.warning(
                "datadog record %s carries a %s at %s, which has no fields to record",
                self._record_id(record), type(body).__name__, self._body_attribute,
            )
            return None

        return operation_id, body, self._seen_at(envelope, record)

    def _record_id(self, record: Mapping[str, Any]) -> str:
        record_id = record.get("id")
        return record_id if isinstance(record_id, str) else "<no id>"

    def _seen_at(self, envelope: Mapping[str, Any], record: Mapping[str, Any]) -> datetime:
        """When the response was seen, not when the search ran.

        A log is searched long after the response arrived, and the drift detector decides
        severity by asking which shape was seen first. Stamping ingestion time would make every
        backfilled page look like the newest behaviour the vendor has. A timestamp that cannot be
        read costs the record nothing: it is metadata about the observation, not the observation.
        """
        raw = envelope.get("timestamp")
        if isinstance(raw, str):
            try:
                return datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                log.warning("datadog record %s has an unreadable timestamp", self._record_id(record))
        return datetime.now(timezone.utc)
