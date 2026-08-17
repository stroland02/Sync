"""The quality axes, computed from the migration corpus.

`docs/superpowers/specs/2026-07-27-sync-benchmark-gates.md` names five axes and blocks gate
tier B on `migration_outcome` holding rows. It holds none today, because no real pipeline run
has produced one. That blocks the *gate* -- a pass/fail verdict in CI -- and not the
*computation*, so the computation exists now and is tested against synthetic rows. Nothing here
is wired into CI and no threshold appears, because the spec's rule is that a gate at an invented
number either fires constantly and gets disabled or never fires and provides false assurance.
Recording early is free and cannot be backfilled; gating early is a self-inflicted wound.

Every axis reports its sample size
----------------------------------
`Axis` is a value *and* an `n`, and an axis with no samples reports `value=None` rather than
`0.0`. "The merge rate is 0%" and "no attempts have been recorded" are different statements, and
a type that cannot tell them apart makes the difference unrecoverable by the time anyone reads
the number. Since the corpus is empty today, unmeasured is the normal answer and has to be the
one the type expresses best.

The grain, and what each axis divides by
----------------------------------------
A row is one *attempt*. A finding retried three times is three rows and one outcome, so no axis
may divide by row count where it means finding count. The denominators differ per axis and each
is chosen rather than inherited:

- **Merge rate** divides by pull requests *opened*, split by `change_kind` and by `tier`. An
  attempt abandoned before `push_branch` never reached a reviewer, and counting it as an unmerged
  pull request would report the pipeline's abandonment rate under the name of its merge rate. A
  finding opens at most one pull request, so this is also the count of findings that reached one.
  `pr_merged` being null means the webhook has not arrived rather than that the branch was
  rejected, so those are excluded from both halves.

- **Routing accuracy** divides by *findings* routed to tier 0, not by tier-0 attempts. Three
  failed tier-0 attempts on one finding are one routing decision that went wrong, and dividing by
  attempts would let a single stubborn finding outvote three that succeeded first time -- moving
  the axis when the retry budget changed rather than when routing did.

- **Cost per merged patch** divides by merged pull requests and sums over *every* attempt of
  those findings, including the ones that failed. A patch that merged on its third try cost all
  three, and charging only the winning attempt would report a margin the pipeline never
  achieved.

Costs are `input_tokens + output_tokens`. `cache_read_input_tokens` is deliberately excluded:
cache reads bill at a different rate, and folding them into one total invents a price ratio this
module has no business asserting.

What is not here
----------------
Binding precision and recall need a labelled reference the corpus cannot supply -- it records
what Sync did, not what was correct. The spec's first deliverable for that is a count rather than
a harness, so `Counts` reports the denominators precision will divide into and no precision
number is fabricated from them.

Nothing is derived from `arg_key_hashes`. That column is salted per deployment, so grouping on it
across customers returns one bucket per customer and looks exactly like an answer;
`sync.core.corpus` carries the full argument. The shape columns -- `change_kind`, `tier`,
`symbol_shape` -- are the ones that mean the same thing everywhere.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Sequence

from pydantic import BaseModel

from sync.core import MigrationOutcome

TIER_ZERO = 0


class Axis(BaseModel):
    """One measurement, the number of samples behind it, and its row provenance.

    `value` is `None` exactly when `n` is zero. A rate over no samples is not zero, and the two
    have to stay distinguishable through serialisation, which is why this is a null rather than a
    sentinel float.
    `provenance` describes the kind of rows contributing to the measurement: 'unmeasured' when
    n is zero, 'production' when all contributing attempts are live runs, 'rehearsal' when all
    are fixture rehearsals, or 'mixed' when both kinds contributed.
    """

    value: float | None
    n: int
    provenance: str = "unmeasured"

    @classmethod
    def over(
        cls,
        numerator: float,
        denominator: int,
        provenance: str = "unmeasured",
    ) -> "Axis":
        if denominator == 0:
            return cls(value=None, n=0, provenance="unmeasured")
        return cls(value=numerator / denominator, n=denominator, provenance=provenance)


class Counts(BaseModel):
    """The sizes every rate above was computed against, plus what precision will need.

    `attempts` and `findings` are both reported because they are the grain distinction: a caller
    reading one as the other is the mistake the corpus spec names, and it cannot be made silently
    when both are present.
    """

    attempts: int
    findings: int
    pull_requests_opened: int
    pull_requests_merged: int
    findings_abandoned: int
    production_attempts: int = 0
    rehearsal_attempts: int = 0


class BenchmarkAxes(BaseModel):
    """Every axis one run of the corpus supports, as data a caller can serialise and compare."""

    merge_rate_by_change_kind: dict[str, Axis]
    merge_rate_by_tier: dict[int, Axis]
    routing_accuracy: Axis
    tokens_per_merged_patch: Axis
    wall_ms_per_merged_patch: Axis
    counts: Counts


def _tokens(attempt: MigrationOutcome) -> int:
    return (attempt.input_tokens or 0) + (attempt.output_tokens or 0)


def _provenance(attempts: Iterable[MigrationOutcome]) -> str:
    """Determine the provenance category for a collection of attempts."""
    attempts_list = list(attempts)
    if not attempts_list:
        return "unmeasured"
    has_prod = any(not a.is_rehearsal for a in attempts_list)
    has_rehearsal = any(a.is_rehearsal for a in attempts_list)
    if has_prod and has_rehearsal:
        return "mixed"
    if has_rehearsal:
        return "rehearsal"
    return "production"


def _merge_rate_grouped(groups: dict[object, list[MigrationOutcome]]) -> dict:
    """Merge rate per group with provenance, from attempts of pull requests that opened."""
    result = {}
    for group, group_attempts in groups.items():
        merged_count = sum(1 for a in group_attempts if a.pr_merged)
        total_count = len(group_attempts)
        result[group] = Axis.over(
            merged_count,
            total_count,
            provenance=_provenance(group_attempts),
        )
    return result


def compute_axes(outcomes: Sequence[MigrationOutcome]) -> BenchmarkAxes:
    """The benchmark axes over a set of corpus rows.

    Takes rows rather than a store, so the arithmetic is testable without Postgres and the one
    reader that produces them -- `GraphStore.migration_outcomes` -- stays the caller's business.
    """
    by_finding: dict[str, list[MigrationOutcome]] = defaultdict(list)
    for attempt in outcomes:
        by_finding[attempt.finding_id].append(attempt)

    # A null `pr_merged` is a webhook that has not arrived, not a rejection. Counting it as
    # unmerged would make every recent run look worse than it was, and the number would improve
    # on its own with no change to the pipeline.
    decided = [a for a in outcomes if a.pr_number is not None and a.pr_merged is not None]

    merged_findings = {a.finding_id for a in decided if a.pr_merged}
    merged_attempts = [a for finding in merged_findings for a in by_finding[finding]]

    routed_to_tier_zero = {
        finding for finding, attempts in by_finding.items()
        if any(a.tier == TIER_ZERO for a in attempts)
    }
    held_at_tier_zero = {
        finding for finding in routed_to_tier_zero
        if not any(a.tier > TIER_ZERO for a in by_finding[finding])
        and any(a.tier == TIER_ZERO and a.static_verify_passed for a in by_finding[finding])
    }
    tier_zero_attempts = [a for f in routed_to_tier_zero for a in by_finding[f]]

    kind_groups: dict[object, list[MigrationOutcome]] = defaultdict(list)
    tier_groups: dict[object, list[MigrationOutcome]] = defaultdict(list)
    for a in decided:
        kind_groups[a.change_kind].append(a)
        tier_groups[a.tier].append(a)

    return BenchmarkAxes(
        merge_rate_by_change_kind=_merge_rate_grouped(kind_groups),
        merge_rate_by_tier=_merge_rate_grouped(tier_groups),
        routing_accuracy=Axis.over(
            len(held_at_tier_zero),
            len(routed_to_tier_zero),
            provenance=_provenance(tier_zero_attempts),
        ),
        tokens_per_merged_patch=Axis.over(
            sum(_tokens(a) for a in merged_attempts),
            len(merged_findings),
            provenance=_provenance(merged_attempts),
        ),
        wall_ms_per_merged_patch=Axis.over(
            sum(a.wall_ms for a in merged_attempts),
            len(merged_findings),
            provenance=_provenance(merged_attempts),
        ),
        counts=Counts(
            attempts=len(outcomes),
            findings=len(by_finding),
            pull_requests_opened=sum(1 for a in outcomes if a.pr_number is not None),
            pull_requests_merged=len(merged_findings),
            findings_abandoned=len(
                {a.finding_id for a in outcomes if a.terminal_status == "abandoned"}
            ),
            production_attempts=sum(1 for a in outcomes if not a.is_rehearsal),
            rehearsal_attempts=sum(1 for a in outcomes if a.is_rehearsal),
        ),
    )

