"""The tier B axes, rendered for a human to read.

`2026-07-27-sync-benchmark-gates.md` settles what happens to these numbers before the movement
that counts as a regression is established: *"tier B axes are **recorded, not gated** -- written
to the corpus every run, reviewed by a human, and reported with their sample size."* Reviewing
requires a surface to review on, and `compute_axes` and `compute_binding_accuracy` had no caller
in `src/` at all -- the arithmetic existed and nothing could display it.

Nothing here compares a number to anything. That is the same rule the computation already
follows and it is not a gap: a gate at an invented threshold either fires constantly and gets
switched off, or never fires and provides false assurance. The report says so in its own header,
because a page of numbers with no verdict beside them invites the next reader to supply one.

Unmeasured is the normal answer, and it renders
-----------------------------------------------
The corpus holds no rows, so today every axis reports null over zero samples. That has to be a
legible report rather than an error or an empty string -- a reporting surface that only works
once data exists cannot be tested before the data exists, which is to say it is first exercised
on the day somebody is relying on it.

`Axis` distinguishes "no samples" from "zero", and the distinction survives to the page here
rather than being flattened at the last step. "The merge rate is 0%" and "no attempt has been
recorded" are different statements, and an empty corpus rendered the first way reports a
pipeline that fails everything.

The sample size travels with the number
---------------------------------------
Every axis is rendered with its own `n`, including the ones inside a split. The spec's reason is
worth repeating exactly: *"A merge rate over four pull requests is not a merge rate, and
presenting it as one is how a solo founder talks themselves into a wrong conclusion with nobody
in the room to object."*

The splits stay split. A merge rate over one easy change kind is not the pipeline's merge rate,
so `merge_rate_by_change_kind` and `merge_rate_by_tier` are rendered per group and no aggregate
of either is computed here -- one would be the number a reader quotes, and it is the number the
spec says means nothing.

Binding precision and recall are reported unmeasured rather than omitted. They need a labelled
reference the corpus cannot supply, and `2026-07-28-sync-ground-truth-count.md` leaves the label
source undecided, so the labels arrive as an argument. An axis left off the page because nobody
can compute it yet is an axis nobody remembers is missing.
"""

from __future__ import annotations

from typing import Sequence

from sync.benchmark.axes import Axis, BenchmarkAxes, compute_axes
from sync.benchmark.binding import (
    BindingAccuracy,
    BindingLabel,
    EmittedFinding,
    compute_binding_accuracy,
)
from sync.core import MigrationOutcome

# What an axis with no samples prints. A word rather than a dash or a blank: this is the normal
# answer today, and it has to survive being read quickly by somebody scanning a column.
UNMEASURED = "unmeasured"

_LABEL_WIDTH = 30
_VALUE_WIDTH = 12

# Axes whose value is a proportion, so three decimals is the honest precision. The cost axes are
# means of token counts and milliseconds, and rendering those to three decimals would claim an
# accuracy the corpus does not have.
_RATES = frozenset({
    "routing accuracy",
    "binding precision",
    "binding recall",
})


def axis_rows(axes: BenchmarkAxes, accuracy: BindingAccuracy) -> list[tuple[str, Axis]]:
    """Every scalar axis the report carries, in the order it prints them.

    The splits are absent on purpose -- they are dictionaries with one `Axis` per group and are
    rendered as groups. What is here is the set a reader would otherwise have to be told is
    complete, which is what lets a test assert that none of them lost its sample size rather
    than asserting it for the ones a hand-written list happened to name.
    """
    return [
        ("routing accuracy", axes.routing_accuracy),
        ("tokens per merged patch", axes.tokens_per_merged_patch),
        ("wall ms per merged patch", axes.wall_ms_per_merged_patch),
        ("binding precision", accuracy.precision),
        ("binding recall", accuracy.recall),
    ]


def _value(axis: Axis, rate: bool) -> str:
    if axis.value is None:
        return UNMEASURED
    return f"{axis.value:.3f}" if rate else f"{axis.value:,.0f}"


def _axis_line(label: str, axis: Axis, rate: bool = True, indent: str = "") -> str:
    width = _LABEL_WIDTH - len(indent)
    return f"{indent}{label:<{width}}{_value(axis, rate):>{_VALUE_WIDTH}}   n={axis.n}"


def _group(title: str, entries: dict[str, Axis]) -> list[str]:
    """One split, or a line saying the split has nothing in it.

    Every entry in a split is a proportion whatever its group is named, so these are rates
    without consulting `_RATES` -- that set names the scalar axes, where the label is the only
    thing that says which kind of number it is.

    An empty split prints its own absence rather than nothing at all. A heading followed by
    blank space reads as a rendering fault; a heading followed by "nothing recorded" reads as
    the corpus being empty, which is what it is.
    """
    if not entries:
        return [title, "  (nothing recorded)"]
    return [
        title,
        *[_axis_line(key, axis, indent="  ") for key, axis in sorted(entries.items())],
    ]


def _counts(axes: BenchmarkAxes, accuracy: BindingAccuracy) -> list[str]:
    """The denominators, named. `attempts` and `findings` are both here because they are the
    grain distinction -- one corpus row is one attempt, and a reader taking one for the other is
    the mistake the corpus spec names."""
    counts = axes.counts
    return [
        ("attempts", counts.attempts),
        ("findings", counts.findings),
        ("pull requests opened", counts.pull_requests_opened),
        ("pull requests merged", counts.pull_requests_merged),
        ("findings abandoned", counts.findings_abandoned),
        # Excluded from precision because nothing labels them. Reported beside the score rather
        # than dropped: silent exclusion turns a biased sample into an unqualified number.
        ("findings with no label", accuracy.unlabelled_findings),
    ]


def render_report(
    outcomes: Sequence[MigrationOutcome],
    findings: Sequence[EmittedFinding] = (),
    labels: Sequence[BindingLabel] = (),
) -> str:
    """The whole report as text.

    Takes rows rather than a store, for the reason `axes.py` gives: the arithmetic and now the
    rendering are both testable without Postgres, and the one reader that produces the rows
    stays the caller's business.

    `findings` and `labels` default to empty because no label source is decided yet, and that
    renders as two unmeasured axes rather than as two missing ones.
    """
    axes = compute_axes(outcomes)
    accuracy = compute_binding_accuracy(findings, labels)

    lines = [
        "Sync benchmark -- tier B quality axes",
        "Recorded, not gated: nothing here is compared against a threshold, and a number that "
        "moves is not a verdict.",
        "",
        *_group("Merge rate by change kind", axes.merge_rate_by_change_kind),
        "",
        *_group(
            "Merge rate by tier",
            {f"tier {tier}": axis for tier, axis in axes.merge_rate_by_tier.items()},
        ),
        "",
        *[
            _axis_line(label, axis, rate=label in _RATES)
            for label, axis in axis_rows(axes, accuracy)
        ],
        "",
        *_group("Binding precision by rung", {
            rung: rung_precision.precision
            for rung, rung_precision in accuracy.precision_by_rung.items()
        }),
        "",
        *_group("Binding recall by rung", {
            rung: rung_recall.recall for rung, rung_recall in accuracy.recall_by_rung.items()
        }),
        "",
        "Sample counts",
        *[f"  {label:<{_LABEL_WIDTH - 2}}{count}" for label, count in _counts(axes, accuracy)],
    ]
    return "\n".join(lines) + "\n"
