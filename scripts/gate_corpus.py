"""The first quality gate: a directional floor on what the frozen corpus recorded.

`2026-07-27-sync-benchmark-gates.md` names exactly one gate that is safe to add without the
tier C statistics work: a directional floor on a deterministic axis. Everything else it
specifies is either waiting on a corpus that does not exist yet or on research that did not
complete, and it is unambiguous about what happens to a gate at a number nobody measured --
*"a gate at an invented number either fires constantly and gets disabled, or never fires and
provides false assurance."*

So every floor here is the figure the corpus produced. None is rounded, and none carries a
tolerance. A tolerance would be an invented threshold wearing a safety margin's clothes: the
axes are deterministic, so any drop is a real change and there is nothing for slack to absorb.

Recording and judging are separate, which is why this is not in `score_corpus.py`
---------------------------------------------------------------------------------
That script's docstring says it records and does not judge, and that separation is the same one
the specification draws between the computation and the gate. This reads what it recorded and
compares. A score can therefore be taken without being gated -- which is what every recording in
`benchmark/corpus/recorded/` was -- and the gate can be run against a score taken minutes or
weeks earlier without re-running the pipeline.

Why the floors live here
------------------------
In a module, beside the number each one guards and beside the argument for guarding it. Not in
`.github/workflows/ci.yml`, where a floor is a string in a shell line that a reader meets without
the figure it came from, and where lowering one is a config tweak rather than a reviewable act.
Moving a floor here is a diff against a comment stating what the old figure was and what produced
it, which is the only form in which lowering a gate can be argued with.

What is floored, and what is deliberately not
---------------------------------------------
**Binding precision**, at the recorded 1.0000 over n=16. Deterministic given a fixed pipeline and
fixed inputs -- measured byte-identical across independent runs from clean databases -- so a drop
is a regression rather than sampling noise.

**Binding recall**, at the recorded 1.0000 over n=16. This one is a judgement and the argument
against it is real: recall moved twice on the day the corpus was frozen, once when a corpus fix
exposed a genuine binder defect and once when positives were deliberately traded for negatives.
A gate that fires on honest work gets disabled, and a disabled gate is worse than none.

It is floored anyway, for three reasons. Both of those moves were *corpus authoring*, and a
frozen corpus is authored rarely and on purpose; the freeze is what makes the objection
historical. When it does happen, the floor turns a silent movement into a commit that has to
restate the recorded figure beside the change that moved it -- which is the reviewable act this
module exists to force, not an obstacle to it. And recall is the axis whose failure the product
exists to prevent: a missed break is the thing Sync is for, so gating precision and leaving
recall open would gate the less important half. The cost is friction on a rare deliberate act,
paid to catch a binder that quietly stops finding what it used to.

**Falsifiable negatives**, at the recorded 4, and this one guards a gate rather than the binder.
Precision is the share of judged findings that were genuine; with no negative the detector could
have fired on, its false-positive term has no candidates and the rate is fixed by how the corpus
was built. That was the state before `hold_back` existed, and a precision floor over it would
have gated a constant -- the "never fires and provides false assurance" half of the failure the
specification warns about. If the count silently returns to zero, the precision floor above stops
gating anything while staying green. A floor on the count is what makes that arrive loudly.

**Pairs scored**, at the recorded 12, for the same reason one step up. Two pairs were excluded by
`displaced-label` before that defect was fixed, and an exclusion regression shrinks both axes'
denominators while leaving both values at 1.0000. The rates would stay green over a corpus that
had quietly stopped covering a third of itself.

**Nothing else.** The tier B axes -- merge rate, routing accuracy, cost per merged patch -- have a
denominator of zero, because the pipeline has never opened a pull request. A floor over a null is
a floor over nothing.

A null is a failure, not a pass
-------------------------------
`axes.py` reports a null rather than a zero for an axis with no samples, deliberately, and a
comparison against a null must not silently succeed. Here it fails and says which axis was
unmeasured. Skipping would be defensible for an axis whose corpus might legitimately be empty;
this corpus is committed and frozen, so an unmeasured axis means the scoring stopped covering it,
which is a regression this gate should be the thing that reports.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Run as `uv run python scripts/gate_corpus.py`, Python puts `scripts/` on the path and not the
# repository root, so the sibling module below is unimportable by the name the tests use. Adding
# the root rather than importing it as a bare sibling keeps one spelling for both callers.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.symbol_map_pin import PIN, read_pin

# Every figure below was produced by
#
#     uv run python scripts/score_corpus.py --score-dsn <a database of its own>
#
# over `benchmark/corpus/pairs` on 2026-07-29, and reproduced from a second clean database in the
# commit that added this file. `benchmark/corpus/recorded/2026-07-29-held-back-negatives.txt` is
# the recording. These are the corpus's own answers, not round numbers chosen near them.
#
#                         was            now
#   binding precision     1.0000 n=18    1.0000 n=27
#   binding recall        1.0000 n=18    1.0000 n=27
#   falsifiable negatives  5              6
#   pairs scored          13             17
#
# Restated on 2026-07-29 because the corpus grew, which is the only reason a floor may move
# upward without an argument attached. Four pairs were added, all response-side, all of them
# operations the corrected selection rule proposes and the pinned thirteen did not hold:
# `furever-GetAccountsAccount` (six positives and the sixth falsifiable negative),
# `turbo-GetPaymentIntentsIntent`, `fireship-server-DeleteSubscriptionsSubscriptionExposedId`
# and `virtual-lab-GetBalance`, one positive each. Every rate held at 1.0000 and the movement is
# exactly additive -- 18 + 9 positives, 5 + 1 negatives, 13 + 4 pairs -- so nothing here is a
# rate that changed, only three denominators that did.
#
# `benchmark/corpus/recorded/2026-07-29-the-rule-and-the-corpus-agree.txt` is the recording, and
# it is what says the thirteen were kept rather than replaced: three of the four additions are
# operations the rule would pick *instead of* pairs the corpus holds, and a pair that scores
# honestly is evidence whether or not today's rule would have chosen it.
#
# Lowering one is a claim that the pipeline got worse on purpose, and it belongs in the same
# commit as the change that made it worse, with the reason in the commit body. Two Python pairs
# were refused rather than landed earlier the same day, for exactly that reason: they would
# have forced this recall floor to 0.8889 to accommodate ground truth already proved wrong.
PRECISION_FLOOR = 1.0
RECALL_FLOOR = 1.0
FALSIFIABLE_NEGATIVES_FLOOR = 6
PAIRS_SCORED_FLOOR = 17


@dataclass(frozen=True)
class Failure:
    """One floor a score did not clear, in the words a reader needs to act on it."""

    axis: str
    detail: str

    def __str__(self) -> str:
        return f"{self.axis}: {self.detail}"


def _rate(accuracy: dict[str, Any], half: str) -> tuple[float | None, int]:
    """One rate and its sample size, derived the way `BindingAccuracy` derives them.

    Over the per-rung integers rather than over the per-rung rates, for the reason `binding.py`
    gives: an aggregate computed from rates can disagree with the split it came from, and one
    computed from counts cannot.
    """
    rungs = accuracy.get(f"{half}_by_rung", {})
    wrong_key = "false_positives" if half == "precision" else "false_negatives"
    genuine = sum(rung["true_positives"] for rung in rungs.values())
    wrong = sum(rung[wrong_key] for rung in rungs.values())
    total = genuine + wrong
    return (genuine / total if total else None), total


def check(score: dict[str, Any]) -> list[Failure]:
    """Every floor this score did not clear, in the order the floors are declared.

    Returns them all rather than the first. A run that reported one regression and stopped would
    hide the other three, and a reader deciding whether a change is worth its cost needs the
    whole movement rather than its alphabetically first component.
    """
    failures: list[Failure] = []
    accuracy = score.get("accuracy", {})

    for half, floor in (("precision", PRECISION_FLOOR), ("recall", RECALL_FLOOR)):
        value, samples = _rate(accuracy, half)
        if value is None:
            failures.append(Failure(
                f"binding {half}",
                f"unmeasured over {samples} samples, and a floor cannot be compared against a "
                f"null; the corpus is committed and frozen, so an axis with no samples means the "
                f"scoring stopped covering it",
            ))
        elif value < floor:
            failures.append(Failure(
                f"binding {half}",
                f"{value:.4f} over n={samples}, below the recorded floor of {floor:.4f}",
            ))

    negatives = len(score.get("falsifiable_negatives", []))
    if negatives < FALSIFIABLE_NEGATIVES_FLOOR:
        failures.append(Failure(
            "falsifiable negatives",
            f"{negatives}, below the recorded floor of {FALSIFIABLE_NEGATIVES_FLOOR}; with fewer "
            f"negatives the detector could have fired on, the precision floor above gates a "
            f"constant and stops being able to fire at all",
        ))

    # The corpus's second frozen input. `score_corpus.py` refuses to produce a number over a
    # map that does not match the pin, and this refuses to judge a number that does not say which
    # map produced it -- a score JSON is a file, and a file can arrive from a scorer that predates
    # the pin or from a hand edit. Every floor below is a figure measured against one specific
    # resolution, so judging a score taken against another is comparing two different corpora.
    recorded_map = score.get("symbol_map_digest") or ""
    pinned_map = read_pin(PIN)["digest"]
    if recorded_map != pinned_map:
        failures.append(Failure(
            "symbol map",
            f"the score names {recorded_map[:16] or 'no symbol map'} and this corpus is pinned to "
            f"{pinned_map[:16]}; the floors below were measured against the pinned one, so this "
            f"score is a number over a different corpus",
        ))

    scored = score.get("pairs_scored", 0)
    if scored < PAIRS_SCORED_FLOOR:
        failures.append(Failure(
            "pairs scored",
            f"{scored} of {score.get('pairs_total', '?')}, below the recorded floor of "
            f"{PAIRS_SCORED_FLOOR}; an excluded pair shrinks both denominators while leaving both "
            f"rates untouched",
        ))

    return failures


def render(score: dict[str, Any], failures: list[Failure]) -> str:
    """What was compared against what, whether or not anything failed.

    Printed on a pass as well as a failure. A gate that is silent when green is a gate nobody can
    tell apart from one that did not run, and this repository has shipped that mistake before.
    """
    precision, precision_n = _rate(score.get("accuracy", {}), "precision")
    recall, recall_n = _rate(score.get("accuracy", {}), "recall")
    unmeasured = "unmeasured"

    lines = [
        "Sync benchmark -- directional floors over the frozen corpus",
        "Every floor is the figure the corpus recorded. None is rounded and none has a tolerance:",
        "the axes are deterministic, so any drop is real and there is nothing for slack to absorb.",
        "",
        f"  {'axis':<24}{'measured':>12}{'floor':>10}",
        f"  {'binding precision':<24}"
        f"{(f'{precision:.4f}' if precision is not None else unmeasured):>12}"
        f"{PRECISION_FLOOR:>10.4f}   n={precision_n}",
        f"  {'binding recall':<24}"
        f"{(f'{recall:.4f}' if recall is not None else unmeasured):>12}"
        f"{RECALL_FLOOR:>10.4f}   n={recall_n}",
        f"  {'falsifiable negatives':<24}{len(score.get('falsifiable_negatives', [])):>12}"
        f"{FALSIFIABLE_NEGATIVES_FLOOR:>10}",
        f"  {'pairs scored':<24}{score.get('pairs_scored', 0):>12}{PAIRS_SCORED_FLOOR:>10}",
        f"  {'symbol map':<24}{(score.get('symbol_map_digest') or 'unrecorded')[:12]:>12}"
        f"{read_pin(PIN)['digest'][:12]:>10}",
        "",
    ]

    if not failures:
        lines.append("Every floor cleared.")
        return "\n".join(lines) + "\n"

    lines.append(f"{len(failures)} floor(s) not cleared:")
    lines += [f"  {failure}" for failure in failures]
    lines += [
        "",
        "A floor is lowered in the commit that makes the pipeline worse, with the reason in that",
        "commit's body -- never to make a red build green.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--score", required=True,
        help="the JSON `scripts/score_corpus.py --json` wrote; this judges a recording rather "
             "than taking one",
    )
    args = parser.parse_args()

    path = Path(args.score)
    if not path.exists():
        print(
            f"no score at {path}; run `scripts/score_corpus.py --json {path}` first. A missing "
            f"score is not a passing gate.",
            file=sys.stderr,
        )
        return 2

    score = json.loads(path.read_text(encoding="utf-8"))
    failures = check(score)
    print(render(score, failures), end="")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
