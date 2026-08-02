"""Rank the modules a coverage run left uncovered by what a wrong answer in each one costs.

A percentage ranking answers the wrong question. Sixty per cent of forty statements in a module
that prints a summary is a smaller problem than ninety-two per cent of three hundred on the patch
path, and both of the earlier coverage baselines had to say so in prose beside their tables
because nothing computed it. This computes it: **exposure is missed statements times the cost of
being wrong there**, and the cost is declared per package with the argument attached.

Why a script rather than a paragraph
------------------------------------
The weighting is the contestable part of the measurement, and prose hides it. Here it is one
table a reader can disagree with by editing a number and re-running, which is the difference
between a ranking somebody can check and a ranking somebody has to trust. The percentages
themselves come from `coverage.py` and nothing here recomputes them.

Nothing here is a gate. `2026-07-27-sync-benchmark-gates.md` binds -- *"do not invent a
threshold"* -- and an exposure figure is a ranking key, not a floor. It orders work; it does not
fail a build.

What it refuses
---------------
Every refusal below exists because the alternative is a table with no rows and exit 0. A coverage
report that measured nothing, a `--cov` argument naming the wrong package, and a report format
that changed under a version bump all arrive as *an absence*, and an absence read as "nothing to
harden" is the same defect as a test that passes without parsing its argument.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


class CoverageReportUnreadable(RuntimeError):
    """The JSON handed in is not a coverage report, or is one that measured nothing.

    Raised rather than returning an empty list. The two failures this separates -- a report that
    is not JSON, and a report whose `files` is empty -- both produce zero modules, and a caller
    that sees zero modules renders a table saying there is nothing to harden. That is a false
    statement about the tree, arrived at without reading it.
    """


class UnclassifiedModule(RuntimeError):
    """A module under a package with no declared cost tier.

    Refusing rather than defaulting. A package that did not exist when this table was written is
    likelier to be new pipeline than new reporting, so weighting it at the bottom would rank the
    newest and least-exercised code last -- and silently, since a default leaves no trace in the
    output. The fix is one row in `COST_TIERS` and the argument for it.
    """


@dataclass(frozen=True)
class CostTier:
    """One weight, the packages it covers, and why a wrong answer there costs what it does."""

    name: str
    weight: int
    packages: tuple[str, ...]
    reason: str


COST_TIERS: tuple[CostTier, ...] = (
    CostTier(
        name="patch",
        weight=4,
        packages=("sync/remediate/", "sync/route/", "sync/verify/"),
        reason=(
            "These choose, write and gate an edit to a customer's source. The worst case this "
            "project has is the one `CLAUDE.md` names -- a patch that parses cleanly and means "
            "something else -- and it is produced here or caught here. `verify/` is weighted with "
            "them rather than below them because it is the only thing between a wrong edit and a "
            "pull request: a decline it gets wrong is a patch nobody looked at again."
        ),
    ),
    CostTier(
        name="signal",
        weight=3,
        packages=("sync/index/", "sync/signals/", "sync/detect/", "sync/telemetry/"),
        reason=(
            "A silent decline here costs a binding, and a run missing a binding reports clean -- "
            "the vendor broke, the call site was never found, and nothing distinguishes that from "
            "a healthy repository. A decline that resolves *wrongly* is worse and rarer. Five "
            "committed decline reports over these packages all reach the same finding: the caller "
            "observes nothing at all."
        ),
    ),
    CostTier(
        name="record",
        weight=2,
        packages=("sync/core/", "sync/graph/", "sync/forge/", "sync/benchmark/"),
        reason=(
            "These carry what the earlier stages established and publish it. A defect corrupts "
            "the record rather than the customer's source, which is recoverable -- but not free: "
            "`benchmark/` produces the labels precision and recall are gated on, and "
            "`2026-07-29-sync-verification-regime.md` records recall reading 1.0000 against a "
            "corpus that shared the binder's blind spot."
        ),
    ),
    CostTier(
        name="report",
        weight=1,
        packages=("sync/cli.py", "sync/dashboard/", "sync/mcp/"),
        reason=(
            "A defect here costs a number on a screen or a malformed tool response, with an "
            "operator reading it. This is deliberately the low weight even though `cli.py` is "
            "where the pipeline is wired, because the wiring failure -- a component reachable "
            "from nothing -- is invisible to line coverage in either direction and is gated by "
            "`scripts/lint_dead_links.py` instead."
        ),
    ),
)
"""The whole contestable part of this ranking, in one place and with the arguments attached.

Ordered by weight so the table reads top-down. Membership is by path prefix rather than by module,
because a per-module table would go stale the day somebody splits a file -- and a package is the
granularity at which the cost argument is actually true.
"""


@dataclass(frozen=True)
class ModuleCoverage:
    """One file's row of a coverage report, with the path in the form a reader can grep for."""

    module: str
    statements: int
    missed: int
    missing_lines: tuple[int, ...]
    percent: float


@dataclass(frozen=True)
class RankedModule:
    coverage: ModuleCoverage
    tier: CostTier
    exposure: int


def _module_name(path: str) -> str:
    """`src\\sync\\index\\literals.py` as `sync/index/literals.py`.

    Coverage writes the separator the platform uses, so the same run recorded on Windows and in
    CI produces two spellings of one module. Normalising here rather than at every comparison
    keeps the tier prefixes writable in one form.
    """
    normalised = path.replace("\\", "/")
    prefix = "src/"
    return normalised[len(prefix):] if normalised.startswith(prefix) else normalised


def read_report(text: str) -> list[ModuleCoverage]:
    """Every file a `coverage.py` JSON report names, refusing anything that is not one.

    Fully covered modules are kept. They are the denominator, and dropping them here would make
    this disagree with `--cov-report=term-missing` about the same run.
    """
    try:
        report: Any = json.loads(text)
    except ValueError as exc:
        raise CoverageReportUnreadable(
            f"not a coverage.py JSON report: {exc}. `--cov-report=json:<path>` writes one; "
            f"`term-missing` writes a table this cannot read."
        ) from exc

    if not isinstance(report, dict) or "files" not in report:
        raise CoverageReportUnreadable(
            "the JSON names no `files`, so it is not a coverage.py report of format 3"
        )

    files = report["files"]
    if not files:
        raise CoverageReportUnreadable(
            "the coverage report names no files at all. A run that measured nothing and a "
            "`--cov` argument naming a package that was never imported both look like this, and "
            "neither means the tree has nothing left to harden."
        )

    modules = []
    for path, entry in files.items():
        summary = entry.get("summary") if isinstance(entry, dict) else None
        if not isinstance(summary, dict) or "num_statements" not in summary:
            raise CoverageReportUnreadable(
                f"{path} carries no `summary`; the report format is not the one this reads"
            )
        modules.append(
            ModuleCoverage(
                module=_module_name(path),
                statements=int(summary["num_statements"]),
                missed=int(summary["missing_lines"]),
                missing_lines=tuple(entry.get("missing_lines", ())),
                percent=float(summary["percent_covered"]),
            )
        )
    return modules


def tier_for(module: str) -> CostTier:
    """The cost tier a module sits in, by the package it belongs to."""
    for tier in COST_TIERS:
        if any(module == package or module.startswith(package) for package in tier.packages):
            return tier
    raise UnclassifiedModule(
        f"{module} is in no package COST_TIERS declares. Add it with the argument for its "
        f"weight rather than letting it default -- a weight nobody chose is not a measurement."
    )


def rank(modules: Iterable[ModuleCoverage]) -> list[RankedModule]:
    """The modules with something missed, heaviest exposure first.

    Ties break on the module name so two runs over one report render the same table -- a ranking
    whose order moves between renderings cannot be diffed, and the diff is how a reader sees what
    the last round of hardening changed.
    """
    ranked = [
        RankedModule(coverage=m, tier=tier_for(m.module), exposure=m.missed * tier_for(m.module).weight)
        for m in modules
        if m.missed
    ]
    return sorted(ranked, key=lambda r: (-r.exposure, r.coverage.module))


def render(ranked: Sequence[RankedModule]) -> str:
    """The ranked table, as the markdown a specification carries."""
    rows = [
        "| Module | Tier | Weight | Missed | Statements | Covered | Exposure |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for entry in ranked:
        rows.append(
            f"| `{entry.coverage.module}` | {entry.tier.name} | {entry.tier.weight} | "
            f"{entry.coverage.missed} | {entry.coverage.statements} | "
            f"{entry.coverage.percent:.0f}% | {entry.exposure} |"
        )
    return "\n".join(rows)


def render_tiers() -> str:
    """The weighting itself, so a table never travels without the argument behind it."""
    rows = ["| Tier | Weight | Packages | Why a wrong answer costs this much |", "|---|---:|---|---|"]
    for tier in COST_TIERS:
        packages = ", ".join(f"`{p}`" for p in tier.packages)
        rows.append(f"| {tier.name} | {tier.weight} | {packages} | {tier.reason} |")
    return "\n".join(rows)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("report", type=Path, help="a coverage.py JSON report")
    parser.add_argument("--tiers", action="store_true", help="print the weighting table too")
    args = parser.parse_args(argv)

    ranked = rank(read_report(args.report.read_text(encoding="utf-8")))
    if args.tiers:
        print(render_tiers())
        print()
    print(render(ranked))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
