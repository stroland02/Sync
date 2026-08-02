"""What `scripts/rank_coverage.py` must refuse, and what its ordering must mean.

**No test here asserts a coverage percentage.** The figure moves with every commit, so a test
pinning one is a tripwire that fires on unrelated work rather than a check on this script. What is
asserted is the parsing, the refusals, and the ordering -- the three things that would make a
ranked table wrong rather than merely stale.

The refusal tests exist because of a failure this repository has already shipped: the
import-boundary test's original form exited 0 without parsing its own argument, so it passed for
the wrong reason and would have kept passing through any violation. A report reader that answers
an empty list for an unreadable report has the same shape, and a ranking built on it prints a
table with nothing in it and no error.
"""

from __future__ import annotations

import json

import pytest

from scripts.rank_coverage import (
    CoverageReportUnreadable,
    UnclassifiedModule,
    rank,
    read_report,
    render,
    tier_for,
)


def _report(files: dict[str, tuple[int, int, list[int]]]) -> str:
    """A coverage.py JSON report holding exactly these files.

    Keyed by the Windows-separated paths coverage writes on this machine, because that is the
    form the script has to read and normalising it is one of the things under test.
    """
    return json.dumps(
        {
            "meta": {"format": 3, "version": "7.15.2"},
            "files": {
                path: {
                    "summary": {
                        "num_statements": statements,
                        "missing_lines": missed,
                        "percent_covered": 100.0 * (statements - missed) / statements,
                    },
                    "missing_lines": lines,
                }
                for path, (statements, missed, lines) in files.items()
            },
            "totals": {"num_statements": 0, "missing_lines": 0, "percent_covered": 0.0},
        }
    )


class TestReadingTheReport:
    def test_a_windows_separated_path_reads_as_a_module(self) -> None:
        modules = read_report(_report({"src\\sync\\index\\literals.py": (52, 1, [79])}))

        assert [m.module for m in modules] == ["sync/index/literals.py"]
        assert modules[0].statements == 52
        assert modules[0].missed == 1
        assert modules[0].missing_lines == (79,)

    def test_text_that_is_not_json_is_refused(self) -> None:
        with pytest.raises(CoverageReportUnreadable):
            read_report("Name    Stmts   Miss  Cover\n----\nTOTAL  7234  166  98%\n")

    def test_a_report_naming_no_files_is_refused_rather_than_read_as_empty(self) -> None:
        """The failure mode this whole file exists for.

        `{"files": {}}` is what a coverage run that measured nothing produces, and it is also what
        a wrong `--cov` argument produces. Answering `[]` makes the ranking print a table with no
        rows and exit 0, which reads as "nothing to harden".
        """
        with pytest.raises(CoverageReportUnreadable):
            read_report(json.dumps({"meta": {}, "files": {}, "totals": {}}))

    def test_a_report_with_no_files_key_at_all_is_refused(self) -> None:
        with pytest.raises(CoverageReportUnreadable):
            read_report(json.dumps({"meta": {}, "totals": {}}))

    def test_a_file_entry_carrying_no_summary_is_refused_and_names_the_file(self) -> None:
        broken = json.loads(_report({"src\\sync\\index\\literals.py": (52, 1, [79])}))
        del broken["files"]["src\\sync\\index\\literals.py"]["summary"]

        with pytest.raises(CoverageReportUnreadable, match=r"literals\.py"):
            read_report(json.dumps(broken))

    def test_a_fully_covered_module_is_kept_rather_than_filtered(self) -> None:
        """The denominator has to survive the read.

        A ranking that drops the zero rows cannot say how much of the tree is already accounted
        for, and `--cov-report=term-missing:skip-covered` already exists for readers who want the
        short form. Filtering here would make the two commands disagree about the same run.
        """
        modules = read_report(
            _report(
                {
                    "src\\sync\\graph\\store.py": (134, 0, []),
                    "src\\sync\\index\\literals.py": (52, 1, [79]),
                }
            )
        )

        assert {m.module for m in modules} == {"sync/graph/store.py", "sync/index/literals.py"}


class TestTheCostTiers:
    def test_the_patch_path_outweighs_the_signal_path_which_outweighs_reporting(self) -> None:
        assert (
            tier_for("sync/remediate/nodes.py").weight
            > tier_for("sync/index/python_lang.py").weight
            > tier_for("sync/cli.py").weight
        )

    def test_every_tier_states_why_it_weighs_what_it_does(self) -> None:
        """A weight with no argument beside it is a number somebody invented.

        The brief this ranking answers asks for the weighting to be stated so a reader can
        disagree with it, and a reader cannot disagree with a bare multiplier.
        """
        for module in ("sync/remediate/nodes.py", "sync/index/python_lang.py", "sync/cli.py"):
            assert tier_for(module).reason.strip()

    def test_a_module_in_no_declared_package_is_refused_rather_than_defaulted(self) -> None:
        """Silently weighting an unknown package at 1 is the failure this refuses.

        A package added later is likelier to be on the patch path than to be reporting -- that is
        where this build is going -- so the safe default is not the low one, and there is no safe
        default. Refusing names the file and costs one line in the tier table.
        """
        with pytest.raises(UnclassifiedModule, match=r"sync/quantum/entangle\.py"):
            tier_for("sync/quantum/entangle.py")


class TestTheRanking:
    def test_a_costlier_module_outranks_a_leakier_one(self) -> None:
        """The whole point of weighting, asserted as an ordering rather than as a number.

        Four missed statements in an edit primitive rank above nine in the command line, which
        percentage-ordering and gap-ordering both get backwards.
        """
        ranked = rank(
            read_report(
                _report(
                    {
                        "src\\sync\\cli.py": (500, 9, list(range(9))),
                        "src\\sync\\remediate\\nodes.py": (200, 4, [1, 2, 3, 4]),
                    }
                )
            )
        )

        assert [r.coverage.module for r in ranked] == ["sync/remediate/nodes.py", "sync/cli.py"]

    def test_exposure_is_the_missed_count_times_the_weight(self) -> None:
        ranked = rank(read_report(_report({"src\\sync\\remediate\\nodes.py": (200, 4, [1])})))

        assert ranked[0].exposure == 4 * tier_for("sync/remediate/nodes.py").weight

    def test_modules_with_nothing_missed_are_not_ranked(self) -> None:
        """They are read, so the denominator survives; they are not ranked, because a ranking of
        what to harden has nothing to say about a module with nothing uncovered."""
        ranked = rank(
            read_report(
                _report(
                    {
                        "src\\sync\\graph\\store.py": (134, 0, []),
                        "src\\sync\\index\\literals.py": (52, 1, [79]),
                    }
                )
            )
        )

        assert [r.coverage.module for r in ranked] == ["sync/index/literals.py"]

    def test_ties_break_on_the_module_name_so_two_runs_render_the_same_table(self) -> None:
        report = _report(
            {
                "src\\sync\\index\\typescript.py": (300, 2, [1, 2]),
                "src\\sync\\index\\literals.py": (52, 2, [1, 2]),
            }
        )

        first = [r.coverage.module for r in rank(read_report(report))]
        assert first == ["sync/index/literals.py", "sync/index/typescript.py"]


class TestRendering:
    def test_the_table_names_the_tier_beside_every_row(self) -> None:
        """A ranked row whose weight is not visible cannot be argued with, which is the same
        objection as an unstated weighting one level up."""
        table = render(
            rank(
                read_report(
                    _report(
                        {
                            "src\\sync\\remediate\\nodes.py": (200, 4, [1, 2, 3, 4]),
                            "src\\sync\\cli.py": (500, 9, list(range(9))),
                        }
                    )
                )
            )
        )

        assert "sync/remediate/nodes.py" in table
        assert tier_for("sync/remediate/nodes.py").name in table
        assert table.index("sync/remediate/nodes.py") < table.index("sync/cli.py")
