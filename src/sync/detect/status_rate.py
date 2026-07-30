"""Findings from the status codes vendor calls came back with.

`observed_call.spans` has carried a status per span since the table existed and no detector read
one, so an operation that started failing outright was the one break this system could see and
did not report. This module reads them.

What "a change in rate" can honestly mean here
----------------------------------------------
M2 asks for a change in 4xx or 5xx rate, and a change is between two periods. This table has no
window column and no rollup: the grain is one row per unit of work, and the only time it carries
is `first_seen` and `last_seen` per row. Two things follow, and the second is the larger.

A period can be *derived* -- rows sorted by `first_seen` are a time-ordered stream, and the
earliest and the latest requests held are two samples. What cannot be derived is a change
*point*. Nothing here searches for when a rate moved, so a split chosen at the midpoint of the
data would dilute a break that started late and manufacture one out of sampling noise when the
rate never moved at all.

And "held" is doing real work in that sentence. `cli.py` truncates `observed_call` at the start
of every `sync run`, so this table contains whatever `sync ingest` folded in since the last run,
not the history of the integration. "Earlier" therefore means earlier *within one ingested
window*, which for a single captured payload may be minutes. A detector that called that
"before" and "after" would be quoting a trend it does not have.

So the finding is not a change. It is a level -- an error rate at or above a floor over enough
requests to be a rate -- which is a fact this table can source outright. Whether the rate *rose*
is used exactly as `observed_drift` uses its own window comparison: as enrichment of severity on
a finding some other rule already raised, never as a reason to raise one. That module states the
principle and this one inherits it unchanged.

The change comparison, when it happens at all, is between the earliest requests held and the
latest requests held, and each side must clear the sample floor on its own with no row in
common. Traffic that cannot supply two independent floor-sized samples gets no change claim and
says so in its rationale. What would make this a real change detector is a windowed rollup of
statused spans per operation that survives a run -- an hourly or daily bucket with error and
total counts -- which is a schema change and is not made here.

The denominator is a request, not a row and not a trace
------------------------------------------------------
The thing that carries a status is a span, and one span is one request and one response. So the
rate is failed requests over requests that carried a status, pooled across every row in the
group.

The available wrong answer is rows: `observed_call` is keyed per trace, so "traces containing an
error, over traces" is one cheap query away and gives a different number. A row is not a call --
its own docstring says so -- and one trace of two hundred clean requests would weigh the same as
one trace of a single failure.

A request with no status leaves the fraction entirely, from the numerator and the denominator
both. `ObservedCall.error_count` already refuses to count one as an error, on the grounds that a
request that got no response is a real outcome and a separate question; a denominator that
included them would report every operation whose collector dropped responses as healthier than
it is. The count of them is quoted in the rationale instead, so a reviewer can discount a rate
computed over a shrunken sample.

The population is `(operation_id, server_address, http_method)` -- the row's natural key without
the trace. `server_address` is in that key because one operation reached through two hosts is
two integrations, a sandbox and a live key or two regions, and the schema says merging them
would average a test workload into a production bill. The same argument is sharper here: a
sandbox failing at forty per cent averaged into healthy production traffic produces a rate that
describes neither integration.

The sample floor
----------------
`MIN_STATUSED_CALLS` is a floor on the denominator, and it is what stops two calls with one
failure being reported as a fifty per cent error rate.

Unlike `efficiency`'s thresholds, this one has an argument rather than a policy. Ordinary
traffic to a healthy operation carries a background of failures that break nothing -- a card
declined, a 404 on a resource somebody deleted -- and the floor's job is to make that background
unable to reach the threshold by chance. At a background of two per cent, the chance that a
hundred requests show ten or more failures is roughly one in twenty thousand; at thirty requests
it is about one in forty, which across a few dozen operations is a false finding most scans.
That gap is why the floor is a hundred rather than the thirty `observed_drift` could justify:
its question is "has this been seen enough times to be a baseline", and this one is "could this
proportion have come from a harmless one".

The honest limit of that argument is the two per cent it assumes. An operation whose ordinary
failure rate is genuinely five per cent clears the threshold by chance about three times in a
hundred, and nothing here holds a per-operation baseline to calibrate against. The rationale
therefore quotes the counts and the codes rather than asserting the rate is abnormal.

`ERROR_RATE_THRESHOLD` gets no such argument and is a policy floor in `efficiency`'s sense: one
request in ten failing is well clear of traffic anybody would call healthy, and the counts are
quoted so the finding can be judged without trusting the number that surfaced it.

What a status code does not say
-------------------------------
It does not say whose fault it was, and this module never claims one. A 429 is a limit the
caller provoked, a 401 can be a rotated key or a revoked one, a 400 can be a client that started
sending a field the vendor removed, and a 500 can be a malformed request the vendor handled
badly. Splitting the rate into "theirs" and "ours" along the 4xx/5xx line would be an attribution
the table cannot support, so both are one rate, the observed codes are listed as evidence, and
the rationale states what came back rather than what caused it.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Mapping, Sequence

from sync.core import Finding, ObservedCall
from sync.graph.store import GraphStore

MIN_STATUSED_CALLS = 100
"""Requests carrying a status below which no rate is stated at all. See the module docstring."""

ERROR_RATE_THRESHOLD = 0.10
"""Fraction of statused requests returning 4xx or 5xx at or above which this is reported."""

CODES_IN_RATIONALE = 3
"""How many distinct status codes the rationale names, most frequent first.

A bound rather than a completeness: the codes are there to tell a rate limit from a rotated
credential, and a rationale that grew into a histogram would stop being read."""


@dataclass(frozen=True)
class _Tally:
    """What one set of rows observed, counted the only way the fraction is defensible."""

    errors: int
    statused: int
    unknown: int
    codes: Counter
    first_seen: datetime
    last_seen: datetime

    @property
    def rate(self) -> float:
        return self.errors / self.statused


def _tally(rows: Sequence[ObservedCall]) -> _Tally | None:
    """Fold rows into one count, or `None` when nothing in them carried a status.

    `None` rather than a zero-denominator tally: an operation whose every response was lost is
    not an operation with a zero per cent error rate, and returning one would make the caller
    responsible for remembering the difference.
    """
    errors = 0
    statused = 0
    unknown = 0
    codes: Counter = Counter()

    for row in rows:
        for facts in row.spans.values():
            status = facts.get("status")
            if not isinstance(status, int):
                unknown += 1
                continue
            statused += 1
            if status >= 400:
                errors += 1
                codes[status] += 1

    if statused == 0:
        return None

    return _Tally(
        errors=errors,
        statused=statused,
        unknown=unknown,
        codes=codes,
        first_seen=min(row.first_seen for row in rows),
        last_seen=max(row.last_seen for row in rows),
    )


def _statused(row: ObservedCall) -> int:
    return sum(1 for facts in row.spans.values() if isinstance(facts.get("status"), int))


def _leading_block(rows: Sequence[ObservedCall], floor: int) -> int | None:
    """How many rows from the front it takes to reach `floor` statused requests, or `None`.

    A count rather than a tally, because the caller needs to know whether the front block and
    the back block share a row before either is worth folding.
    """
    seen = 0
    for index, row in enumerate(rows):
        seen += _statused(row)
        if seen >= floor:
            return index + 1
    return None


class StatusRateDetector:
    """Operations returning 4xx or 5xx often enough, over enough requests, to be a rate."""

    detector_id = "status-rate"

    def __init__(
        self,
        store: GraphStore,
        repo_id: str,
        vendor_id: str = "stripe",
        min_statused_calls: int = MIN_STATUSED_CALLS,
        error_rate_threshold: float = ERROR_RATE_THRESHOLD,
    ) -> None:
        self._store = store
        self._repo_id = repo_id
        self._vendor_id = vendor_id
        self._floor = min_statused_calls
        self._threshold = error_rate_threshold

    def scan(self) -> Iterable[Finding]:
        for (operation_id, server_address, method), rows in self._populations().items():
            overall = _tally(rows)
            if overall is None or overall.statused < self._floor:
                continue
            if overall.rate < self._threshold:
                continue

            sites = self._store.call_sites_for_operation(
                self._vendor_id, operation_id, repo_id=self._repo_id
            )
            if not sites:
                continue

            earlier, later = self._periods(rows)
            rose = (
                earlier is not None
                and later is not None
                and earlier.rate < self._threshold <= later.rate
            )

            for site in sites:
                if site.id is None:
                    continue
                yield Finding(
                    detector=self.detector_id,
                    # The population, minus the operation the call site already determines. One
                    # operation failing on a sandbox host and on a live one is two integrations
                    # and two claims -- which is why `server_address` is in `observed_call`'s
                    # key, and the findings have to be kept apart on the same grounds. Bounded
                    # by how many hosts a vendor answers on.
                    claim=f"error-rate:{server_address}:{method}",
                    call_site_id=site.id,
                    # Breaking only when the rate rose between two independent samples. A level
                    # that has held since the earliest traffic stored is a standing condition,
                    # and reporting it as breaking would put it in triage beside a call site
                    # that stopped compiling.
                    severity="breaking" if rose else "info",
                    rationale=(
                        f"{self._observation(operation_id, server_address, method, overall)} "
                        f"{self._history(earlier, later, rose)} {self._caveat()} "
                        f"({site.path}:{site.line})"
                    ),
                )

    def _populations(self) -> Mapping[tuple[str, str, str], list[ObservedCall]]:
        """Rows grouped into the thing a rate is quoted about, ordered oldest first.

        An uncorrelated row is dropped: `operation_id` is empty when nothing matched the request
        to an operation, and a finding has no operation to name and no call site to address.

        That test is an early-out and not a correctness guard, the same way `efficiency`'s is,
        and it is worth saying because it looks like one. No `call_site` row carries an empty
        `operation_id` -- both indexers drop a site whose symbol did not resolve -- so the
        lookup already returns nothing for an uncorrelated group. Mutation testing confirms it:
        deleting this half of the condition leaves every test green. It stays because
        `uncorrelated` is the count `IngestReport` calls the one worth watching, so the query it
        skips is not a rare one.
        """
        groups: dict[tuple[str, str, str], list[ObservedCall]] = {}

        for call in self._store.observed_calls(self._repo_id):
            if call.vendor_id != self._vendor_id or not call.operation_id:
                continue
            key = (call.operation_id, call.server_address, call.http_method)
            groups.setdefault(key, []).append(call)

        for rows in groups.values():
            # `trace_id` breaks the tie so the periods below are the same on every scan. Rows
            # ingested from one batch commonly share a `first_seen` to the second.
            rows.sort(key=lambda row: (row.first_seen, row.trace_id))

        return dict(sorted(groups.items()))

    def _periods(
        self, rows: Sequence[ObservedCall]
    ) -> tuple[_Tally | None, _Tally | None]:
        """The earliest and latest samples large enough to be rates, if two exist.

        Each side must reach the floor on its own and they must share no row. Anything less is a
        rate compared against an impression, and this detector would rather say a level than a
        trend it cannot support. Rows between the two blocks belong to neither: they are the
        middle of the stream, and including them in either side would make the comparison depend
        on where the split fell rather than on what the two ends observed.
        """
        leading = _leading_block(rows, self._floor)
        trailing = _leading_block(list(reversed(rows)), self._floor)
        if leading is None or trailing is None:
            return None, None

        if leading > len(rows) - trailing:
            return None, None

        return _tally(rows[:leading]), _tally(rows[len(rows) - trailing:])

    def _observation(
        self, operation_id: str, server_address: str, method: str, tally: _Tally
    ) -> str:
        """What was seen, in the terms the denominator was actually computed over."""
        codes = ", ".join(
            f"{code} (x{count})" for code, count in tally.codes.most_common(CODES_IN_RATIONALE)
        )
        dropped = (
            f" A further {tally.unknown} request(s) carried no status and are counted as "
            f"neither, so the rate is over the requests that returned one."
            if tally.unknown
            else ""
        )
        return (
            f"{method.upper()} {operation_id} at {server_address} returned 4xx or 5xx on "
            f"{tally.errors} of {tally.statused} request(s) that carried a status "
            f"({tally.rate:.1%}), between {tally.first_seen:%Y-%m-%d} and "
            f"{tally.last_seen:%Y-%m-%d}. Most frequent: {codes}.{dropped}"
        )

    def _history(self, earlier: _Tally | None, later: _Tally | None, rose: bool) -> str:
        """Whether this level is a change, stated with what the claim rests on.

        The qualification about which traffic is held is attached to the claim that the rate
        rose rather than to the module, because that is the only sentence it weakens.
        """
        if earlier is None or later is None:
            return (
                "This is a level rather than a change: the traffic held does not contain two "
                "separated samples large enough to compare, so no earlier rate is stated."
            )

        comparison = (
            f"The earliest {earlier.statused} request(s) held show {earlier.rate:.1%} and the "
            f"latest {later.statused} show {later.rate:.1%}"
        )

        if not rose:
            return (
                f"{comparison}, which does not cross the threshold in that direction, so this "
                f"reads as a standing level rather than something that broke."
            )

        return (
            f"{comparison}, so the rate rose between the two samples this repository holds. "
            f"Those are the earliest and latest requests stored, not the earliest and latest "
            f"that happened -- a run empties this table -- and nothing here searches for when "
            f"the rate moved, so no start date is claimed."
        )

    def _caveat(self) -> str:
        """The attribution this detector refuses to make, stated where the reader will need it."""
        return (
            "A status code records what came back, not who caused it: a 429 is a limit the "
            "caller provoked, a 401 can be a rotated key, and a 500 can be a malformed request. "
            "The codes are quoted and no cause is assigned. This rests on observed traffic "
            "(rung 'observed'), not on anything the vendor published."
        )
