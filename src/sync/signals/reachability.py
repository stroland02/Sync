"""Ranking a repository's third-party surface by what the indexer actually found.

Step 5 of `docs/superpowers/specs/2026-07-29-sync-adaptive-vendor-substrate.md`, and the last in
its sequence. `intake` answers *what can Sync cover*, over the dependencies a manifest declares.
That is the right report for coverage and the wrong one for priority, because a dependency no
line of code calls is not exposure -- a repository declaring twelve SDKs and calling three has
three vendors' worth of risk and nine entries of noise. The spec puts it plainly: *"declared but
never called" is exactly the noise that would otherwise flood a coverage-driven system.*

This adds a dimension to intake's answer rather than replacing it. Every row keeps its category,
its missing configuration and its reason, because those are what a reader needs in order to
disagree with the order.

Zero is two facts and they are not interchangeable
--------------------------------------------------
A dependency Sync cannot bind produces no call sites for the same reason it produces no findings:
the binding is missing, not the usage. Reported as a zero it says *nothing calls this* where the
truth is *nobody looked*, and those read identically to a customer. So the ranking carries three
evidence classes and `UNBINDABLE` never renders as `UNCALLED`:

- `CALLED` -- bound, and the indexer found call sites.
- `UNBINDABLE` -- nothing could be bound, so the absence of call sites is absence of evidence.
  `call_sites` is `None` rather than `0`, because a rendered zero invites exactly the reading
  this class exists to prevent.
- `UNCALLED` -- bound, and the indexer found nothing. A real measured zero.

The order is over four bands, not three
---------------------------------------
Evidence class alone would put every unbindable dependency above every measured zero, on the
argument that unknown exposure outranks exposure established at zero. That argument is right
about *evidence* and wrong about *priority*, and following it floods the report with the noise
the spec named: a repository declaring forty npm packages has thirty-eight nothing can ever
watch, and all thirty-eight would sit above the watched vendor whose answer was zero.

So the unbindable band splits on the distinction `intake` already draws, and the four bands are
ordered by what an operator can do next:

1. `CALLED` -- measured exposure, most call sites first.
2. `UNBINDABLE` and `WATCHABLE` -- unknown exposure, and a configuration entry away from being
   measurable. This is intake's work queue, now prioritised rather than merely listed.
3. `UNCALLED` -- configured, looked at, nothing there.
4. `UNBINDABLE` and `NOT_WATCHABLE` -- unknown exposure and no tier that could serve it.

That is a judgement and it is stated rather than buried: an operator reading this list is asking
what to do next, and "unknown, and one line of configuration from being known" is more actionable
than "known to be zero", which is in turn more actionable than "unknown, and nothing can be done
about it today". A reader who disagrees has every input on the row and can sort it differently.

Rank, not score
---------------
There is no weighted number here. `CLAUDE.md` and the benchmark specification both refuse
invented thresholds, and a composite score is a threshold with extra steps: it hides which input
moved it and gets believed further than it deserves. An ordered list with its inputs visible
beside each row is more useful and harder to over-read.

Two counts, kept apart
----------------------
`schema.sql` already argues this on `loop_depth` -- static evidence is proof of shape and not of
volume, "which is why this is not interchangeable with a count from `observed_call`". A call site
is one indexed location, not one invocation: two call sites in a file that runs hourly and one in
a hot loop rank identically here and differently by volume. Where telemetry exists the observed
count sits beside the static one rather than being folded into it, so a reader can decompose the
order. `2026-07-26-sync-observed-contract-drift.md` prefers observed volume as the honest
denominator where it exists, and reporting both is how that preference survives contact with the
repositories that have no telemetry at all -- for which `observed_calls` is `None`, never `0`.

Purity, and where the counts come from
--------------------------------------
`rank_reachability` takes its inputs, the way `intake.assess_repository` does: it reads no
database and no file, and a test asserts that on its imports rather than trusting this sentence.
`call_site_counts` and `observed_call_counts` are aggregators over rows a caller already holds,
not queries -- which is what keeps the ordering testable against fixtures with nothing running.

Sourcing those rows for a whole repository is the one thing this cannot do from here, and there
are now two ways in depending on what the caller is holding. A caller that has just indexed --
`sync run` -- already holds `CallSite` rows and aggregates them here, reaching no database.
A caller that has not, `sync intake --rank-by-repo-id`, reads `GraphStore.call_site_counts`,
which is the same count expressed as one `GROUP BY` because rows for a whole repository are not
otherwise in hand.

Two expressions of one count is a real cost and it is the lesser one: the alternative was for
this module to open a connection, which would have made the ordering untestable without a
database and put a query in the one place that must stay pure. Both carry the same two contract
sentences -- one row is one call site rather than one dependency, and a vendor with no call
sites is absent rather than zero -- because a caller that believed either differently would
misread the ranking, and they are the sentences to keep in step if a third caller appears.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable, Mapping

from sync.signals.intake import WATCHABLE, WATCHED, Assessment, Dependency, IntakeReport

CALLED = "called"
UNBINDABLE = "unbindable"
UNCALLED = "uncalled"


@dataclass(frozen=True)
class Reach:
    """One dependency, what the indexer found for it, and why the number means what it means."""

    dependency: Dependency
    category: str
    evidence: str
    vendor_id: str | None
    missing: str | None
    reason: str

    call_sites: int | None
    """Indexed locations calling this vendor. `None` when nothing could be bound, which is not
    the same fact as `0` and must not be rendered as one."""

    observed_calls: int | None
    """Calls telemetry actually saw, or `None` where there is no telemetry for this vendor.
    Never folded into `call_sites`: one is shape, the other is volume."""


@dataclass(frozen=True)
class ReachabilityRanking:
    """An ordered list, with every input that produced the order visible beside each row."""

    rows: tuple[Reach, ...]

    unreadable: tuple[str, ...]
    """Manifests that would not parse, carried through from the report this ranks.

    Repeated here rather than left to the caller's stderr, which `cli.py` also writes: the JSON
    is what a caller redirects to a file, commits and diffs between runs, and a fault visible
    only in a terminal nobody kept did not survive the run. A ranking whose counts are zero
    because nothing could be read is otherwise indistinguishable from one over a repository that
    depends on nothing.

    `IntakeReport.unreadable`'s key and its shape, deliberately: a reader parsing both artifacts
    needs one rule for this fact rather than two. Empty rather than absent on a clean scan,
    because an absent key does not distinguish a repository whose manifests all read from an
    artifact produced by something that never recorded a fault. Required rather than defaulted
    for the same reason -- a ranking constructed without it would report a clean scan silently."""

    def counts(self) -> dict[str, int]:
        counts = {CALLED: 0, UNBINDABLE: 0, UNCALLED: 0}
        for row in self.rows:
            counts[row.evidence] += 1
        return counts

    def to_json(self) -> str:
        """The artifact, for a reader outside this process.

        Deliberately no aggregate of the two counts and no rank number. The position in the list
        is the rank, and a reader who wants a different order has the inputs to produce one.
        """
        return json.dumps(
            {
                "counts": self.counts(),
                "rows": [
                    {
                        "name": row.dependency.name,
                        "version": row.dependency.version,
                        "ecosystem": row.dependency.ecosystem,
                        "evidence": row.evidence,
                        "call_sites": row.call_sites,
                        "observed_calls": row.observed_calls,
                        "category": row.category,
                        "vendor_id": row.vendor_id,
                        "missing": row.missing,
                        "reason": row.reason,
                    }
                    for row in self.rows
                ],
                "unreadable": list(self.unreadable),
            },
            indent=2,
        )


def call_site_counts(sites: Iterable) -> dict[str, int]:
    """Indexed call sites per vendor, over rows the caller already has.

    **A row is one call site, not one dependency.** The count answers how many *places in the
    code* reach a vendor, which differs from how many dependencies exist whenever one vendor is
    called from several files -- the normal case, and exactly the case ranking is about.

    A vendor with no call sites is absent rather than present with a zero, because absence here
    has two causes this function cannot tell apart: the indexer looked and found nothing, or it
    never looked. Only the intake category separates them, and `rank_reachability` is where that
    resolution happens.
    """
    counts: dict[str, int] = {}
    for site in sites:
        counts[site.vendor_id] = counts.get(site.vendor_id, 0) + 1
    return counts


def observed_call_counts(calls: Iterable) -> dict[str, int]:
    """Observed calls per vendor, summing spans rather than counting rows.

    `ObservedCall`'s own docstring is why this exists rather than being a one-line comprehension
    at each caller: "A row is not a call: `spans` holds one entry per span and `call_count` is
    its size ... A query counting vendor calls by counting rows undercounts exactly where the
    efficiency detector is looking."
    """
    counts: dict[str, int] = {}
    for call in calls:
        counts[call.vendor_id] = counts.get(call.vendor_id, 0) + call.call_count
    return counts


def _evidence(assessment: Assessment, call_sites: Mapping[str, int]) -> tuple[str, int | None]:
    """Which of the three classes this dependency is in, and its static count if it has one.

    The intake category resolves the ambiguity a count cannot: a vendor absent from the counts
    was either looked at and not found, or never looked at, and only the category says which.
    `WATCHED` means a registered vendor *and* a declared binding for this ecosystem, so the
    indexer could bind it and an absence there is a measured zero. Anything else could not be
    bound, so an absence is an absence of evidence.
    """
    if assessment.category != WATCHED:
        return UNBINDABLE, None

    found = call_sites.get(assessment.vendor_id or "", 0)
    return (CALLED if found else UNCALLED), found


def _band(row: Reach) -> int:
    """Which of the four bands this row sits in; see the module docstring for the order."""
    if row.evidence == CALLED:
        return 0
    if row.evidence == UNCALLED:
        return 2
    return 1 if row.category == WATCHABLE else 3


def _order(row: Reach) -> tuple:
    """Band, then the two counts, then the dependency's own identity.

    Name and ecosystem are last and are what make the order total: a repository cannot declare
    the same package twice in one ecosystem, so no pair is ever left to the sort's input order.
    A ranking that reordered equal rows between runs is one nobody can diff.
    """
    return (
        _band(row),
        -(row.call_sites or 0),
        -(row.observed_calls or 0),
        row.dependency.name,
        row.dependency.ecosystem,
    )


def rank_reachability(
    report: IntakeReport,
    call_sites: Mapping[str, int] | None = None,
    observed_calls: Mapping[str, int] | None = None,
) -> ReachabilityRanking:
    """The repository's dependencies, ordered by what is known to reach a vendor.

    Both counts are keyed by vendor id, which is the only key the two sides share: a dependency
    is named by its package and a call site is keyed by the vendor that package reaches. A
    dependency intake could not attribute to a vendor has neither, and is `UNBINDABLE` for that
    reason rather than by a separate rule.

    An empty repository ranks nothing and returns an empty ranking. That is an answer, not an
    error: a repository with no third-party call sites has nothing to prioritise.
    """
    static = call_sites or {}
    observed = observed_calls or {}

    rows = [
        Reach(
            dependency=assessment.dependency,
            category=assessment.category,
            evidence=evidence,
            vendor_id=assessment.vendor_id,
            missing=assessment.missing,
            reason=assessment.reason,
            call_sites=found,
            observed_calls=observed.get(assessment.vendor_id or ""),
        )
        for assessment, (evidence, found) in (
            (assessment, _evidence(assessment, static)) for assessment in report.assessments
        )
    ]

    return ReachabilityRanking(
        rows=tuple(sorted(rows, key=_order)),
        unreadable=report.unreadable,
    )
