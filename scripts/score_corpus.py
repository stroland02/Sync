"""Score every pair in the frozen corpus and report one binding number over the set.

`sync benchmark --score-pair` scores exactly one pair. A single pair is an anecdote:
`2026-07-27-sync-benchmark-gates.md` requires a sample size beside every axis, and a sample size
of one is a number that cannot be read. This runs the committed set in `benchmark/corpus/pairs/`
and pools the result.

A harness rather than a pipeline stage, which is why it is here and not under `src/`. Nothing in
a remediation run scores anything.

Pooled, not averaged
--------------------
Findings and labels meet on the pair of call site and vendor change, and call site ids are per
repository, so the corpus number is computed over the union of every pair's findings and labels.
Averaging per-pair precisions would weight a one-site pair the same as a six-site one and report
a mean of ratios as though it were a ratio.

Every pair the harness refuses is counted and named
---------------------------------------------------
`score.py` raises `DisplacedLabel` and `UnbrokenLabel` rather than scoring a pair it cannot score
honestly, and `mutate.py` raises `UnsupportedChangeKind` rather than returning an unmutated tree.
Those refusals are the feature. A runner that caught them and moved on would turn a biased sample
into an unqualified number, so each is mapped to a named reason, counted, and printed beside the
score rather than in a file nobody opens.

An unrecognised failure is not mapped at all and is re-raised. A reason nobody wrote down must
not be reported under one somebody did.

No threshold
------------
Nothing here compares a number against a floor. `2026-07-27-sync-benchmark-gates.md` is
unambiguous that a gate at an invented number either fires constantly and gets disabled or never
fires and gives false assurance. This records; it does not judge.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from pydantic import BaseModel

from sync.benchmark.axes import Axis
from sync.benchmark.binding import (
    BindingAccuracy,
    BindingLabel,
    EmittedFinding,
    compute_binding_accuracy,
)
from sync.benchmark.mutate import UnsupportedChangeKind
from sync.benchmark.score import SYNTHETIC_REFERENCE, DisplacedLabel, UnbrokenLabel

SPECS = Path("benchmark/corpus/pairs")

# Ordered, because `DisplacedLabel`, `UnbrokenLabel` and `UnsupportedChangeKind` are all
# `ValueError` subclasses and the specific ones have to be tried first. `KeyError` is a malformed
# specification rather than a corpus property, and it is named separately for that reason.
_REASONS: tuple[tuple[type[BaseException], str], ...] = (
    (DisplacedLabel, "displaced-label"),
    (UnbrokenLabel, "unbroken-label"),
    (UnsupportedChangeKind, "unsupported-change-kind"),
    (KeyError, "malformed-specification"),
    (LookupError, "no-call-site-on-the-changed-operation"),
    (ValueError, "generator-refused"),
)


def reason_for(error: BaseException) -> str | None:
    """The named reason a pair was excluded, or None for a failure nobody classified.

    None rather than a catch-all bucket. An exclusion count is only worth reading if every entry
    in it says something specific, and folding an unexpected crash into "generator-refused" would
    report a broken harness as a property of the corpus.
    """
    for kind, reason in _REASONS:
        if isinstance(error, kind):
            return reason
    return None


class PairResult(BaseModel):
    """One specification's outcome: scored with its rows, or excluded with a named reason."""

    name: str
    scored: bool
    reason: str | None = None
    detail: str | None = None
    findings: list[EmittedFinding] = []
    labels: list[BindingLabel] = []
    affected_sites: int = 0
    unaffected_sites: int = 0
    unreachable_targets: tuple[str, ...] = ()
    falsifiable_negatives: tuple[str, ...] = ()
    skipped_files: tuple[str, ...] = ()


class CorpusScore(BaseModel):
    """The corpus number, and everything needed to refuse to over-read it."""

    pairs_total: int
    pairs_scored: int
    excluded_by_reason: dict[str, int]
    excluded_pairs: list[PairResult]
    accuracy: BindingAccuracy
    affected_sites: int
    unaffected_sites: int
    unreachable_targets: list[str]
    falsifiable_negatives: list[str]
    """The negatives the detector could have fired on, pooled across the set.

    Empty is the finding rather than the absence of one. Precision is the share of judged
    findings that were genuine, and with no candidate for its false-positive term the rate is
    fixed by how the corpus was built -- so it reads 1.0 through any binder regression that only
    affects same-operation discrimination.
    """
    skipped_files: list[str]
    """Checkout paths no pair could read as source, pooled across the set and deduplicated.

    Deduplicated because a repository appears in several specifications and its binaries are the
    same binaries each time; the per-pair counts in `pairs` are what says how many each scoring
    run walked past. Most entries are images and fonts and nothing is lost by skipping them. An
    entry that looks like source is a file in a legacy encoding, which is a call site this score
    does not cover and cannot be told apart from a binary without guessing.
    """
    scored_pairs: list[str]
    pairs: list[PairResult]
    """Every pair's own numbers, kept rather than summed away.

    A corpus total hides a pair that contributed no positives at all, and a pair whose every
    target was unreachable is exactly that: scored, counted, and carrying no information about
    the binder. Reading the total without this cannot tell twelve pairs of one site each from two
    pairs of six.
    """

    @property
    def precision(self) -> Axis:
        return self.accuracy.precision

    @property
    def recall(self) -> Axis:
        return self.accuracy.recall


def aggregate(results: Sequence[PairResult]) -> CorpusScore:
    """Pool every scored pair into one accuracy and count every excluded one by reason.

    Pure: results in, a score out. The exclusions are carried rather than filtered away, because
    the count of what could not be scored is part of what the number means.
    """
    scored = [result for result in results if result.scored]
    excluded = [result for result in results if not result.scored]

    findings: list[EmittedFinding] = []
    labels: list[BindingLabel] = []
    unreachable: list[str] = []
    falsifiable: list[str] = []
    skipped: set[str] = set()
    for result in scored:
        findings.extend(result.findings)
        labels.extend(result.labels)
        # Qualified by the pair, because a call site id is unique within a repository and these
        # are pooled across four of them.
        unreachable.extend(f"{result.name}::{target}" for target in result.unreachable_targets)
        falsifiable.extend(f"{result.name}::{site}" for site in result.falsifiable_negatives)
        # A set rather than a list, and unqualified: several specifications name one repository,
        # so qualifying by pair would list its images once per specification and read as though
        # the corpus skipped them that many times.
        skipped.update(result.skipped_files)

    by_reason: dict[str, int] = {}
    for result in excluded:
        by_reason[result.reason or "unclassified"] = by_reason.get(result.reason or "unclassified", 0) + 1

    return CorpusScore(
        pairs_total=len(results),
        pairs_scored=len(scored),
        excluded_by_reason=by_reason,
        excluded_pairs=excluded,
        accuracy=compute_binding_accuracy(findings, labels),
        affected_sites=sum(result.affected_sites for result in scored),
        unaffected_sites=sum(result.unaffected_sites for result in scored),
        unreachable_targets=sorted(unreachable),
        falsifiable_negatives=sorted(falsifiable),
        skipped_files=sorted(skipped),
        scored_pairs=[result.name for result in scored],
        pairs=list(results),
    )


def _axis(label: str, axis: Axis) -> str:
    value = "unmeasured" if axis.value is None else f"{axis.value:.4f}"
    return f"  {label:<22}{value:<12} n={axis.n}"


def render(score: CorpusScore, reference: str | None) -> str:
    """The corpus score as text, with its sample sizes, its exclusions and its reference.

    Refuses without a reference for the reason `render_report` does: a precision with nothing
    saying what the labels were derived from is a number claiming to describe the binder when it
    partly describes the corpus.
    """
    if reference is None:
        raise ValueError(
            "a corpus score was rendered with no reference describing what its labels were "
            "derived from and what that biases; pass one"
        )

    lines = [
        "Sync benchmark -- binding accuracy over the frozen corpus",
        "Recorded, not gated: no number here is compared against a threshold.",
        "",
        f"  pairs specified       {score.pairs_total}",
        f"  pairs scored          {score.pairs_scored}",
        _axis("binding precision", score.precision),
        _axis("binding recall", score.recall),
        f"  call sites affected   {score.affected_sites}",
        f"  call sites unaffected {score.unaffected_sites}",
        f"  unlabelled findings   {score.accuracy.unlabelled_findings}",
        # Beside precision rather than under it, because the two are read together or the rate is
        # read as a property of the binder when it is partly a property of the corpus.
        f"  falsifiable negatives  {len(score.falsifiable_negatives)}",
        # Distinct paths, not a sum over pairs: one repository's images are the same images in
        # every specification naming it. A skip nobody counts is how a corpus stops describing
        # the repository it names, which is the failure the exclusion counts above also guard.
        f"  paths not read        {len(score.skipped_files)}",
        "",
        # Per pair, because a pair whose every target was unreachable is scored, counted and
        # carries no information about the binder -- and the corpus total cannot show that.
        f"  {'scored pair':<58}{'affected':>9}{'unaffected':>12}{'findings':>10}"
        f"{'unreachable':>13}{'unread':>8}",
    ]
    for result in score.pairs:
        if not result.scored:
            continue
        lines.append(
            f"  {result.name:<58}{result.affected_sites:>9}{result.unaffected_sites:>12}"
            f"{len(result.findings):>10}{len(result.unreachable_targets):>13}"
            f"{len(result.skipped_files):>8}"
        )

    lines.append("")
    if not score.falsifiable_negatives:
        lines.extend([
            "Binding precision above is not a measurement. This corpus holds no negative the "
            "detector could have fired on --",
            "every unaffected call site is on another operation, which no detector examines, or "
            "carries no field list for the",
            "match to test. The false-positive term has no candidates rather than few, so a "
            "directional floor on this axis would",
            "gate a constant and could never fire.",
            "",
        ])
    if score.excluded_pairs:
        lines.append("Excluded pairs, by reason:")
        for reason, count in sorted(score.excluded_by_reason.items()):
            lines.append(f"  {reason}: {count}")
        for result in score.excluded_pairs:
            lines.append(f"  {result.name}: {result.reason} -- {result.detail}")
    else:
        lines.append("Excluded pairs: none.")

    if score.unreachable_targets:
        lines.append("")
        lines.append("Targets the mutation could not attach to, labelled unaffected:")
        lines.extend(f"  {target}" for target in score.unreachable_targets)

    if score.skipped_files:
        lines.append("")
        lines.append("Checkout paths not read as source, because they do not decode as UTF-8:")
        # Listed and not merely counted. Every one of these is either a binary, which no indexer
        # wanted, or a source file in a legacy encoding, which is a call site this score does not
        # cover -- and nothing can tell the two apart without guessing, so the names are what a
        # reader has to work from.
        lines.extend(f"  {path}" for path in score.skipped_files)

    lines.extend(["", "Reference:", *(f"  {line}" for line in reference.splitlines()), ""])
    return "\n".join(lines)


def score_specs(paths: Sequence[Path], score_dsn: str) -> list[PairResult]:
    """Run each specification through the shipped scorer, in the order given.

    Imported from `sync.cli` rather than reimplemented. `_score_corpus` is the definition of the
    specification format -- which fields are required and what each means -- and a second copy
    here would let the corpus and the command that reads one pair drift apart silently.
    """
    from sync.cli import _score_corpus

    results = []
    for path in paths:
        name = path.stem
        try:
            scored = _score_corpus(path, score_dsn)
        except Exception as error:
            reason = reason_for(error)
            if reason is None:
                raise
            results.append(PairResult(name=name, scored=False, reason=reason, detail=str(error)))
            continue
        results.append(PairResult(
            name=name, scored=True, findings=scored.findings, labels=scored.labels,
            affected_sites=scored.affected_sites, unaffected_sites=scored.unaffected_sites,
            unreachable_targets=scored.unreachable_targets,
            falsifiable_negatives=scored.falsifiable_negatives,
            skipped_files=scored.skipped_files,
        ))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--score-dsn", dest="score_dsn", required=True,
        help="a database of its own for scoring, which is truncated per pair; it must not name "
             "the database any corpus of migration outcomes lives in",
    )
    parser.add_argument("--specs", default=str(SPECS), help="directory of corpus specifications")
    parser.add_argument("--json", dest="json_out", default=None, help="also write the score here")
    args = parser.parse_args()

    # Sorted, so two runs over one set score in one order and a comparison of the two is a
    # comparison of the pipeline rather than of the filesystem's enumeration.
    paths = sorted(Path(args.specs).glob("*.yaml"))
    if not paths:
        print(f"no corpus specifications under {args.specs}", file=sys.stderr)
        return 2

    score = aggregate(score_specs(paths, args.score_dsn))
    print(render(score, reference=SYNTHETIC_REFERENCE), end="")

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(score.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
