"""Sentry issue counts reduced to a failure count per operation per window.

`shapes.py` reads the same source and asks a different question. It parses a recorded response
body and yields a shape, which is what the drift detector compares against a published
specification; nothing in this repository asked Sentry how *often* an operation failed, so the
join M5 exists to make -- errors rising, against a deploy, against a vendor change -- had no
numerator to start from.

What an issue is, and what that costs
-------------------------------------
Sentry groups events by fingerprint and reports a count per group. So one issue is many errors
and one operation is usually several issues: two different call paths raising the same `402` are
two groups, and pooling them is the whole point -- a per-issue row would answer "which of your
error groups is largest" rather than "did this operation start failing". `issue_count` is kept
beside the total because it is the difference between one broken call path and a vendor refusing
everything, and it cannot be recovered from the total afterwards.

The status class comes from the group's representative event, and is attributed to the whole
group's count. Sentry groups by fingerprint, so the events in one group are alike and that is
usually right; it is not guaranteed, and there is no per-event breakdown in an issues export to
make it exact.

Only the window's own counts
----------------------------
An issue carries lifetime totals as well as `count`, and only `count` is read. `userCount`,
`firstSeen` and `lastSeen` describe the group rather than the period queried, and a window
assembled from them would shrink to whatever happened to fail -- so an hour with two errors and
an hour with two thousand would both read as a busy minute. The bounds come from the caller,
which is the only party that knows what period it asked for.

Values
------
None leave this module. An issue is richer than an event payload and worse to hold: the title is
an exception message, the culprit is a path and a symbol out of the customer's own repository,
and `metadata.value` is whatever their code interpolated into the error. What survives is a
count, a status class and an operation the vendor's own adapter resolved. The log lines carry
Sentry's surrogate id and nothing the customer wrote, because a log file is a column with worse
access control.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Mapping, Sequence

from sync.core import ObservedErrorWindow
from sync.graph.store import GraphStore

log = logging.getLogger(__name__)

ERROR_TRACKER_GROUP_SOURCE = "error-tracker-group"
"""How a count reached the graph, as `observed_error_window.source` records it.

The mechanism and not the product, which is how `observed_shape.source` names its values --
Sentry and Datadog both write 'error-payload' there. The sampling story is what the column
separates: a count an error tracker's own grouping produced and a count derived from spans are
different samples of the same failures, and two sources disagreeing about one operation is
information about the correlator that merging them would erase.

That argument runs the other way too, which is why this is not named for Sentry. A count
Datadog grouped is the same sampling story as a count Sentry grouped, and under a per-product
value the same failures seen through two trackers would be two rows for one operation, class
and window -- which any consumer summing rows would double-count.
"""

# The rung every row here carries. A recorded request URL matched against the vendor's published
# path template is watched traffic, which is the same binding `observed_call` makes from a span
# and fails the same way. There is deliberately no 'unresolved' counterpart: a Sentry project is
# the customer's entire error stream rather than a pre-filtered one, so recording what nothing
# correlates would make this table a copy of their error volume filed under no operation.
BINDING_RUNG = "observed"


@dataclass(frozen=True)
class WindowIngest:
    """What one export did to the window it was queried over.

    Two numbers and not one. A re-query that wrote nothing and removed three rows reports
    identically to an export holding nothing this vendor owns if only the writes are counted, and
    of the two it is the deletion that cannot be undone -- an error tracker's retention is finite
    and this table cannot be backfilled.
    """

    written: int
    removed: int


class UnreadableExport(Exception):
    """Every record the export held was dropped as malformed, so the window is not replaced.

    An empty pooling is otherwise a replacement: a period the tracker now reports as clean has
    to bring the previous counts down. This is the one reading of an empty pooling that is not
    evidence about the vendor's operations -- rename a field an issue is built from and every
    record drops out, and clearing the slice would report the reader having stopped working as
    an hour in which nothing failed, with the counts gone and no way back because this table
    cannot be backfilled.

    An export holding records this reader understood and does not own is not this. Those were
    read; that a customer's Sentry project is mostly their own bugs is the ordinary case, and a
    condition that fired on "nothing pooled" would refuse every hour of one.
    """

    def __init__(self, held: int) -> None:
        super().__init__(f"no record in an export of {held} was readable as an issue")
        self.held = held


class SentryErrorReader:
    """Folds an issues export into `observed_error_window`.

    Takes a resolver rather than knowing any URL convention, for the reason `SentryShapeReader`
    does: turning a request into an operation is a fact about one vendor's paths, and that
    knowledge belongs to that vendor's adapter.
    """

    def __init__(
        self,
        store: GraphStore,
        repo_id: str,
        vendor_id: str,
        resolve_operation: Callable[[str, str], str | None],
    ) -> None:
        self._store = store
        self._repo_id = repo_id
        self._vendor_id = vendor_id
        self._resolve_operation = resolve_operation

    def ingest(
        self, issues: Sequence[Any], window_start: datetime, window_end: datetime
    ) -> WindowIngest:
        """Record the counts in one export. Returns what it did to the window.

        A record that is not what it claims to be yields nothing and raises nothing: this reads
        data a third party produced, and one malformed group must not cost the rest of a window.
        It is logged rather than swallowed, because a source that quietly stopped working looks
        exactly like a week with no errors.

        One window's slice for this source is replaced whole rather than upserted key by key. An
        export re-queried after Sentry merged or deleted a group reaches fewer keys, and a key
        nothing writes is a key nothing corrects -- the stale row keeps asserting a level the
        tracker no longer reports while the errors it counted are counted again under the group
        they were merged into. The writes and the removal share one transaction so no reader ever
        sees a window that is half-replaced.

        Raises `UnreadableExport` when every record held was dropped as malformed, which is the
        one empty pooling that says nothing about the vendor's operations.
        """
        pooled: dict[tuple[str, str], list[int]] = {}
        dropped = 0
        for issue in issues:
            request = self._request(issue)
            if request is None:
                dropped += 1
                continue

            method, url, event = request
            operation_id = self._resolve_operation(method, url)
            if operation_id is None:
                # Not a defect and the ordinary case: most of a customer's error stream is their
                # own code and other people's APIs. Deliberately not counted as a drop -- this
                # record was read, and that is what tells a quiet window from a broken reader.
                log.debug("sentry issue %s resolves to no operation", self._issue_id(issue))
                continue

            count = _count(issue.get("count"))
            if count is None:
                log.warning("sentry issue %s carries no readable count", self._issue_id(issue))
                dropped += 1
                continue

            totals = pooled.setdefault((operation_id, _status_class(event)), [0, 0])
            totals[0] += count
            totals[1] += 1

        if dropped and dropped == len(issues):
            log.warning(
                "every one of %d record(s) in this export was dropped as malformed; "
                "the window is left as it was",
                dropped,
            )
            raise UnreadableExport(dropped)

        with self._store.transaction():
            for (operation_id, status_class), (errors, groups) in pooled.items():
                self._store.record_observed_error_window(ObservedErrorWindow(
                    repo_id=self._repo_id,
                    vendor_id=self._vendor_id,
                    operation_id=operation_id,
                    binding_rung=BINDING_RUNG,
                    source=ERROR_TRACKER_GROUP_SOURCE,
                    status_class=status_class,
                    window_start=window_start,
                    window_end=window_end,
                    error_count=errors,
                    issue_count=groups,
                ))
            removed = self._store.remove_observed_error_windows_outside(
                self._repo_id,
                self._vendor_id,
                ERROR_TRACKER_GROUP_SOURCE,
                window_start,
                window_end,
                pooled.keys(),
            )
        return WindowIngest(written=len(pooled), removed=removed)

    def _request(self, issue: Any) -> tuple[str, str, Mapping[str, Any]] | None:
        """The method, url and representative event, or `None` with a reason logged.

        Structural only, and that is what makes it the readability test. Whether this vendor owns
        the operation is a fact about the customer's traffic rather than about the export, so it
        is decided by the caller and not here -- a record that gets this far was read, whoever it
        turns out to belong to.
        """
        if not isinstance(issue, Mapping):
            log.warning("sentry issue is %s, not a mapping", type(issue).__name__)
            return None

        event = issue.get("latestEvent")
        request = event.get("request") if isinstance(event, Mapping) else None
        if not isinstance(request, Mapping):
            log.warning(
                "sentry issue %s carries no representative event to read a request from",
                self._issue_id(issue),
            )
            return None

        method, url = request.get("method"), request.get("url")
        if not isinstance(method, str) or not isinstance(url, str):
            log.warning(
                "sentry issue %s has no usable request method or url", self._issue_id(issue)
            )
            return None

        return method, url, event

    def _issue_id(self, issue: Mapping[str, Any]) -> str:
        """Sentry's own surrogate for the group, which is the only handle on a dropped record.

        Not the `shortId`, which a customer names their project after, and not the title.
        """
        issue_id = issue.get("id")
        return issue_id if isinstance(issue_id, str) else "<no id>"


def _count(raw: Any) -> int | None:
    """How many errors the group held, from either shape Sentry serialises it in.

    The issues endpoint returns `count` as a string and the same field arrives as an integer
    through other exports. A reader taking only one of the two would drop half a real export and
    the surviving rows would look like a quiet week.

    A negative is refused rather than clamped: there is no reading of a negative error count, and
    zeroing it would file a group that cannot be believed under a number that can be.

    `isdecimal` and not `isdigit`: superscripts and other numeric-but-not-positional characters
    satisfy `isdigit` and `int` rejects them, so that guard admits strings the conversion behind
    it raises on -- and the exception would escape the whole ingest, costing every record after
    it in the export.
    """
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw if raw >= 0 else None
    if isinstance(raw, str) and raw.isdecimal():
        return int(raw)
    return None


def _status_class(event: Mapping[str, Any]) -> str:
    """The hundreds bucket of the response the representative event recorded.

    Empty when it recorded none, which is a third answer rather than a missing one. A `TypeError`
    reading a field off a successful response is exactly the failure a removed response property
    causes, and it carries no status at all -- dropping those would discard the evidence, and
    folding them into `5xx` would invent a status the vendor never sent.
    """
    contexts = event.get("contexts")
    response = contexts.get("response") if isinstance(contexts, Mapping) else None
    status = response.get("status_code") if isinstance(response, Mapping) else None
    if not isinstance(status, int) or not 100 <= status <= 599:
        return ""
    return f"{status // 100}xx"
