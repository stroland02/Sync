"""Binding precision and recall, attributed to the rung that produced the binding.

`docs/superpowers/specs/2026-07-27-sync-benchmark-gates.md` calls these the two axes that
matter most -- a false finding spends reviewer trust, and a missed break is the failure the
product exists to prevent -- and then explains why neither could be computed: the migration
corpus records what Sync *did*, not what was *correct*. Precision and recall need a labelled
reference and there is not one.

That blocks the score. It does not block the arithmetic, which is the same distinction the
spec draws for the three axes `axes.py` already computes against a corpus holding no rows.
Nothing here is wired into CI and no constant here is a pass mark, because the spec's rule is
that a gate at an invented number either fires constantly and gets disabled or never fires and
provides false assurance.

Labels are an argument, not a lookup
------------------------------------
Nothing in this module reads a file, queries the database, or knows what a label is made of.
`axes.py` reads the corpus because its axes are about what Sync did; these are about what was
correct, and correctness arrives from outside. It also arrives from somewhere still undecided:
`2026-07-28-sync-ground-truth-count.md` establishes that the obvious source -- migration
commits mined from GitHub -- is viable on sample size and unproven on label quality, since the
findable cohort is overwhelmingly zero-star repositories whose commit messages suggest a
coding agent rather than an engineer wrote them. A scorer that had a label source compiled into
it would have to be rewritten the day that question is settled.

The split is the primary output
-------------------------------
`CLAUDE.md` and `2026-07-27-sync-pipeline-discipline.md` both bind this: every binding carries
the rung it came from, and so does every artifact derived from it, because a false positive
that cannot be attributed to a rung cannot be fixed. An aggregate precision of 0.7 is a real
number and the wrong one to act on. Precision of 0.95 on `observed` bindings beside 0.4 on
`static` ones says where the binder is guessing.

So the per-rung counts are what this stores, and the aggregates are properties derived from
them. A caller wanting only the aggregate sums; a caller handed only an aggregate cannot
recover the split, and neither can a serialised result that carried the aggregate instead. The
derivation is over integers rather than over the per-rung rates, so an aggregate can never
disagree with the split it came from.

Precision and recall key their split on different things, deliberately
----------------------------------------------------------------------
**Precision splits on the rung the finding carries.** The question is which binder produced
this claim, and the finding is the claim.

**Recall splits on the rung the label names.** The question is which binder should have
produced a claim and did not -- and a miss has no finding, so it has no rung of its own. The
label is the only thing that can say where the evidence for that call site lived. A label that
does not say lands under `unresolved`, which `sync.core` already names as the absence of a
binding rather than a rung of one, for the same reason: silently dropping it would hide how
good the correlation is.

Collapsing the two into one keying would attribute a found call site to the binder that found
it and its missed sibling to a different one, which distorts both rates and only under
disagreement -- the shape of wrongness this repository treats as worse than an error.

What is counted, and what has no term
-------------------------------------
- A finding matching a label that says *affected* is a true positive, and it marks that call
  site reached.
- A finding matching a label that says *not affected* is a false positive.
- A finding with no label at all is **excluded and counted**, never dropped. Silent exclusion
  turns a biased sample into an unqualified number.
- A label that says *affected* with no finding is a **false negative**, which is precisely what
  recall exists to count. Reading it as an exclusion instead yields a recall of 1.0 on any
  input whatsoever.
- A label that says *not affected* with no finding is a true negative and appears nowhere.
  Neither rate has a term for it, and it is the overwhelming majority of any real repository:
  in a denominator it would make both numbers fall as the customer's codebase grew.

Two findings for one call site cost precision twice and recall once. That is in the
definitions -- precision is over findings emitted and a reviewer reads both of them, recall is
over call sites genuinely affected and that one was reached -- not a choice made here.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Sequence

from pydantic import BaseModel

from sync.benchmark.axes import Axis
from sync.core import BindingRung


class EmittedFinding(BaseModel):
    """One finding a run emitted, reduced to what scoring it needs.

    Not `sync.core.Finding`, and no longer because that type carries no rung -- since B65 it
    does. What keeps this one is the mined corpus: a row scored there was produced by a pipeline
    run that no longer exists, so there is no `Finding` to read and nothing to attribute it from
    except the corpus record itself. Reducing to the pair plus the rung is what lets the scorer
    take both, and `BindingRung` rather than `FindingRung` is deliberate -- a row being scored
    must name a rung a binder actually emitted, where `unattributed` is a fact about history.
    """

    call_site_id: str
    vendor_change_id: str
    binding_rung: BindingRung


class BindingLabel(BaseModel):
    """The correct answer for one call site against one vendor change.

    `rung` is where the evidence for this dependency lived, and it is read only for a pair that
    is `affected` -- it is what lets a miss be attributed to a binder, since a miss has no
    finding to carry a rung of its own. A pair that is not affected has no binding to
    establish, which is what the default says.
    """

    call_site_id: str
    vendor_change_id: str
    affected: bool
    rung: BindingRung = "unresolved"


class RungPrecision(BaseModel):
    """What one rung's findings were worth, and how many could not be judged.

    `unlabelled` sits beside the rate rather than inside it. It is not a wrong finding and not
    a right one; it is a finding the label set says nothing about, and the rate it is missing
    from is the one number that would otherwise imply it had been covered.
    """

    precision: Axis
    true_positives: int
    false_positives: int
    unlabelled: int


class RungRecall(BaseModel):
    """What one rung's genuinely affected call sites produced.

    `false_negatives` is a count of misses, not of exclusions. The distinction is the whole
    reason both axes are computed rather than one.
    """

    recall: Axis
    true_positives: int
    false_negatives: int


class BindingAccuracy(BaseModel):
    """Both axes, per rung, with the aggregates derived rather than stored.

    The two dictionaries are keyed by different questions and are named for them; see the
    module docstring. Neither is padded with rungs the input never mentioned, so an absent key
    means no binding at that rung rather than a rung that scored zero.
    """

    precision_by_rung: dict[BindingRung, RungPrecision]
    recall_by_rung: dict[BindingRung, RungRecall]

    @property
    def precision(self) -> Axis:
        """Of every finding that could be judged, the share that was genuine."""
        genuine = sum(rung.true_positives for rung in self.precision_by_rung.values())
        wrong = sum(rung.false_positives for rung in self.precision_by_rung.values())
        return Axis.over(genuine, genuine + wrong)

    @property
    def recall(self) -> Axis:
        """Of every call site genuinely affected, the share that produced a finding."""
        found = sum(rung.true_positives for rung in self.recall_by_rung.values())
        missed = sum(rung.false_negatives for rung in self.recall_by_rung.values())
        return Axis.over(found, found + missed)

    @property
    def unlabelled_findings(self) -> int:
        """Findings excluded from precision because nothing labels them."""
        return sum(rung.unlabelled for rung in self.precision_by_rung.values())


def _labels_by_pair(labels: Sequence[BindingLabel]) -> dict[tuple[str, str], BindingLabel]:
    """One label per (call site, vendor change), refusing a second.

    Labels are the one input arriving from outside the pipeline, so they are a boundary. A
    repeated pair inflates recall's denominator once per repetition and a contradictory one
    makes the score depend on which label was read last; neither is visible in the number that
    comes out, which is what makes this worth raising over rather than resolving.
    """
    by_pair: dict[tuple[str, str], BindingLabel] = {}
    for label in labels:
        key = (label.call_site_id, label.vendor_change_id)
        if key in by_pair:
            raise ValueError(
                f"two labels for call site {label.call_site_id} against change "
                f"{label.vendor_change_id}; a label set with a repeated pair scores neither"
            )
        by_pair[key] = label
    return by_pair


def compute_binding_accuracy(
    findings: Sequence[EmittedFinding], labels: Sequence[BindingLabel]
) -> BindingAccuracy:
    """Score a run's findings against a labelled reference.

    Pure: findings in, labels in, counts out. A finding and a label meet on the pair of call
    site and vendor change, because a call site can depend on one changed operation and not
    another -- matching on the call site alone would judge a finding by the answer to a
    different question and be right only by coincidence.
    """
    by_pair = _labels_by_pair(labels)

    # [true positives, false positives, unlabelled] per rung the findings claim.
    emitted: dict[BindingRung, list[int]] = defaultdict(lambda: [0, 0, 0])
    reached: set[tuple[str, str]] = set()
    for finding in findings:
        key = (finding.call_site_id, finding.vendor_change_id)
        counts = emitted[finding.binding_rung]
        label = by_pair.get(key)
        if label is None:
            counts[2] += 1
        elif label.affected:
            counts[0] += 1
            reached.add(key)
        else:
            counts[1] += 1

    # [true positives, false negatives] per rung the labels name. A pair labelled unaffected
    # is not in either half: recall asks what share of the affected ones were found.
    affected: dict[BindingRung, list[int]] = defaultdict(lambda: [0, 0])
    for key, label in by_pair.items():
        if not label.affected:
            continue
        affected[label.rung][0 if key in reached else 1] += 1

    return BindingAccuracy(
        precision_by_rung={
            rung: RungPrecision(
                precision=Axis.over(genuine, genuine + wrong),
                true_positives=genuine,
                false_positives=wrong,
                unlabelled=unlabelled,
            )
            for rung, (genuine, wrong, unlabelled) in emitted.items()
        },
        recall_by_rung={
            rung: RungRecall(
                recall=Axis.over(found, found + missed),
                true_positives=found,
                false_negatives=missed,
            )
            for rung, (found, missed) in affected.items()
        },
    )
