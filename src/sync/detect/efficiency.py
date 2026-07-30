"""Findings about what the customer's own code costs, read from observed traffic.

Every other detector here asks whether something is going to break. This one asks what is
being spent, which makes it the first detector whose output a buyer might quote at a renewal,
and therefore the first whose wrongness is expensive in a way a false positive normally is not.
Two decisions follow from that and both are refusals; they are documented here rather than in
a commit message because they are the load-bearing part of the module.

There is no dollar figure
-------------------------
The design document says these findings carry a dollar estimate and calls it the easiest value
to defend at renewal. That is true of the *finding*, not of this repository's ability to
compute it today. A saving is a call count multiplied by a price per call, and no table here
holds a price: not `observed_call`, not `call_site`, not `vendor_change`. Vendor pricing is
real-world data that varies by plan and by negotiated contract, and none of it is stored.

So the rationale states the call volume, which is a fact the table can source, and states no
money at all. Multiplying by a plausible-looking constant would produce a number that looks
defensible and is not, and an inflated saving quoted in a renewal conversation is worse than no
number -- it is a number the buyer can puncture, which costs the trust every other finding
depends on. `sync.benchmark.axes` already refuses the same way for the same reason: it excludes
`cache_read_input_tokens` from a cost total rather than "inventing a price ratio this module has
no business asserting."

There is no page-size finding
-----------------------------
The design document names four findings and this module emits three. A default page size is
visible only in a request's query string. The only column that ever held one is the salted
`target` digest, which is one-way by construction and deliberately so, and `url_template` holds
the vendor's published path template with no query string at all. The information was destroyed
at the observation boundary, on purpose, by the privacy rule.

The available proxy -- many distinct targets in one trace looking like a pagination walk -- is
indistinguishable from a loop over a list of ids, which is the finding above and has a
different fix. A detector that fired on that would be guessing while sounding certain, so it
does not fire. Making this finding real needs a stored page-size *parameter value*, which is a
schema change and a privacy argument, not a detector change.

What the thresholds are worth
-----------------------------
They are policy floors, not calibrations, and nothing in this repository can currently make
them anything better. `vendor_change` refuses to pick a depth cut-off because there is no
labelled data to calibrate one against, and that objection applies here in full:
`observed_drift` could answer it with a distribution-free argument because its question is
about sample size, and "is this a loop" is not that kind of question.

So each threshold is a constructor argument, each default is chosen to sit well clear of
traffic a reviewer would call deliberate, and every rationale quotes the observed count so the
finding can be judged without trusting the threshold that surfaced it. What would replace them
is a corpus of real traces with labelled outcomes -- which findings a customer acted on -- and
that corpus does not exist yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from sync.core import Finding, ObservedCall
from sync.graph.store import GraphStore


@dataclass(frozen=True)
class _Claim:
    """One efficiency claim a single unit of work supports.

    `kind` reaches `Finding.claim` and joins the graph's identity for the row, so it is a fixed
    vocabulary and never carries a number. `magnitude` is the number the claim was made on, and
    exists only so `scan` can choose which trace to quote when several make the same claim.
    """

    kind: str
    magnitude: int
    rationale: str

LOOP_THRESHOLD = 10
"""Calls to one operation within one unit of work, at or above which this reads as iteration.

Ten rather than three or four because the claim being made is "no one wrote this out by hand".
A request legitimately calling one operation several times -- a create followed by a read, a
handful of look-ups -- is ordinary, and the first findings this system ships should be ones
nobody argues with. The cost is real and is the intended trade: a loop of five is invisible,
and precision over recall is this repository's committed direction."""

REPEAT_THRESHOLD = 2
"""Repeats of one target within one unit of work, at or above which a cache is worth proposing.

Not one. A single repeat is explained by a read-after-write, or by a retry the span did not
record as a resend, and both are correct code. Two or more repeats of the same request in one
unit of work is harder to account for innocently."""

RESEND_THRESHOLD = 3
"""`http.request.resend_count` on a single call, at or above which retrying has become a storm.

`resend_count` is zero on a first attempt, so this is the fourth attempt at one request. The
honest limit of this number: what counts as exhausting a retry policy is set by each SDK's
default and those differ by vendor, and nothing in the graph records which policy was in force.
The rationale therefore quotes the observed count rather than claiming a policy was exceeded."""


def _successful_targets(spans: Mapping[str, Mapping[str, Any]]) -> list[str]:
    """The targets of calls that came back below 400.

    Repeats are counted over these rather than over every span, which is where this parts
    company with `ObservedCall.repeated_calls`. That property counts every duplicate digest,
    which is right for the property and wrong for this finding: a 500 the caller re-issued is a
    retry, and proposing a cache for it would be advice to cache an error.

    A span with no status is included. It is a request that got no response rather than one that
    failed, and dropping it would silently shrink the denominator of a finding about volume.
    """
    return [
        str(facts.get("target"))
        for facts in spans.values()
        if not (isinstance(facts.get("status"), int) and facts["status"] >= 400)
    ]


class EfficiencyDetector:
    """Loops, absent caches and retry storms, read one unit of work at a time."""

    detector_id = "efficiency"

    def __init__(
        self,
        store: GraphStore,
        repo_id: str,
        vendor_id: str = "stripe",
        loop_threshold: int = LOOP_THRESHOLD,
        repeat_threshold: int = REPEAT_THRESHOLD,
        resend_threshold: int = RESEND_THRESHOLD,
    ) -> None:
        self._store = store
        self._repo_id = repo_id
        self._vendor_id = vendor_id
        self._loop_threshold = loop_threshold
        self._repeat_threshold = repeat_threshold
        self._resend_threshold = resend_threshold
        self.declined: list[str] = []
        """Cost claims this scan computed and did not raise, each naming its subject and cause.

        One decline reaches it: a claim whose operation nothing indexed resolves to. It is the
        quietest skip in the package -- there is no statement for coverage to have missed,
        because an empty `reachable` list just does not enter the loop below.

        A row belonging to another vendor is deliberately not here. That decline is correct
        scoping and loses nothing, and counting it would put a number on every run that says
        the repository calls more than one API.
        """

    def scan(self) -> Iterable[Finding]:
        """One finding per claim per call site, quoting the worst unit of work that made it.

        The reduction over traces is not an optimisation. A trace is unbounded -- a busy
        repository writes one `observed_call` row per request -- and every request looping over
        one call site supports the same claim, so emitting a finding each would put a row in
        front of a reviewer for every request the customer served. That is the same argument
        the shared-cost note below makes about call sites, applied to the axis where the
        numbers are far larger: N findings would assert N savings that do not exist.

        Which trace gets quoted is decided rather than left to arrive: the largest magnitude,
        with the trace id breaking ties so two scans of an unchanged graph choose the same one.
        The worst unit of work is also the one worth showing.

        A list rather than a generator, because `declined` is only true once the scan has run
        and a generator nobody finished consuming would leave the count describing part of the
        work.
        """
        self.declined = []
        findings: list[Finding] = []
        strongest: dict[tuple[str, str], tuple[ObservedCall, _Claim]] = {}

        for call in self._store.observed_calls(self._repo_id):
            if call.vendor_id != self._vendor_id:
                continue

            # An early-out to skip a query, not a correctness guard, and the distinction is
            # worth stating because it looks like one. Both indexers drop a call site whose
            # symbol did not resolve, so no `call_site` row carries an empty `operation_id`,
            # so the lookup below already returns nothing for an uncorrelated observation.
            # Removing this line changes no finding -- mutation testing confirmed that -- and
            # `uncorrelated` is the count `IngestReport` calls the one worth watching, so the
            # query it avoids is not a rare one.
            if not call.operation_id:
                continue

            for claim in self._claims(call):
                key = (call.operation_id, claim.kind)
                held = strongest.get(key)
                if held is None or (claim.magnitude, call.trace_id) > (
                    held[1].magnitude, held[0].trace_id
                ):
                    strongest[key] = (call, claim)

        for (operation_id, _), (call, claim) in sorted(strongest.items()):
            sites = self._store.call_sites_for_operation(
                self._vendor_id, operation_id, repo_id=self._repo_id
            )
            reachable = [site for site in sites if site.id is not None]
            if not reachable:
                self.declined.append(
                    f"{operation_id}: a {claim.kind} claim over {claim.magnitude} in trace "
                    f"{call.trace_id} resolves to no indexed call site, so it has no location "
                    f"to report"
                )
                continue

            shared_note = (
                f", shared across {len(reachable)} call sites" if len(reachable) > 1 else ""
            )
            for site in reachable:
                findings.append(Finding(
                    detector=self.detector_id,
                    # The correlator's rung, not `static`. A perfect static binding still
                    # yields a wrong claim if this span was correlated to the wrong operation,
                    # so that correlation is the binding whose wrongness would make the finding
                    # wrong -- and `observed_call` already records its rung. Carried through
                    # including when it is `unresolved`, which is what lets the benchmark see a
                    # correlator's false positives at all.
                    binding_rung=call.binding_rung,
                    # The kind of claim and never its wording. The rationale beside it carries
                    # a live call count, so a discriminator derived from it would change
                    # between runs and write a new row on each one instead of converging.
                    claim=claim.kind,
                    call_site_id=site.id,
                    # `Severity` has no cost axis and `info` is the honest fit. An
                    # efficiency finding has not broken anything, and reporting one as
                    # breaking would let a saving compete in triage with a call site that
                    # no longer compiles.
                    severity="info",
                    # The cost is stated as shared because it was incurred once. Every
                    # other detector's findings are repair instructions -- each call site
                    # is independently broken and independently fixable, so N sites are N
                    # pieces of work. This one is a cost claim, and N findings would
                    # assert N savings that do not exist. The row count stays one per
                    # site, so the shape matches every other detector; what the reviewer
                    # gets is a rationale that cannot be totalled into a number three
                    # times the truth.
                    rationale=(
                        f"{claim.rationale} ({site.path}:{site.line}"
                        f"{shared_note})"
                    ),
                ))

        return findings

    def _claims(self, call: ObservedCall) -> list[_Claim]:
        """Every efficiency claim this one unit of work supports.

        A single row can support more than one -- a loop whose calls also repeat is both a loop
        and an absent cache, with different fixes -- so they are not mutually exclusive and none
        short-circuits the others.

        Each carries the magnitude the claim was made on, because `scan` has to choose between
        two traces making the same claim and the larger number is the one worth quoting.
        """
        claims: list[_Claim] = []
        where = f"{call.operation_id} at {call.server_address}"
        unit = f"one unit of work (trace {call.trace_id})"

        if call.call_count >= self._loop_threshold:
            claims.append(_Claim(
                kind="loop",
                magnitude=call.call_count,
                rationale=(
                    f"{call.call_count} calls to {where} within {unit}, which reads as a loop "
                    f"rather than a written-out sequence. Volume is stated rather than a cost: "
                    f"no price per call is recorded anywhere in the graph."
                ),
            ))

        targets = _successful_targets(call.spans)
        repeats = len(targets) - len(set(targets))
        if repeats >= self._repeat_threshold:
            claims.append(_Claim(
                kind="uncached-repeat",
                magnitude=repeats,
                rationale=(
                    f"the same request to {where} was made {repeats + 1} times within {unit}, so "
                    f"{repeats} of those calls returned something the caller already had -- a cache "
                    f"would remove them. Counted over calls that succeeded, because re-issuing a "
                    f"failed call is a retry rather than an absent cache."
                ),
            ))

        if call.max_resend_count >= self._resend_threshold:
            claims.append(_Claim(
                kind="retry-storm",
                magnitude=call.max_resend_count,
                rationale=(
                    f"a single call to {where} was resent {call.max_resend_count} times within "
                    f"{unit}, which is a retry storm rather than a transient. The worst single "
                    f"call, not the total: each span already counts its own resends. Whether this "
                    f"exhausted the SDK's retry policy is not recorded, so the count is quoted "
                    f"rather than a policy being claimed."
                ),
            ))

        return claims
