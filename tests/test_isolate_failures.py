"""Splitting a failing suite into real failures and interference.

The classification is the whole of this tool, so it is tested with the subprocess injected out.
Whether `pytest` can be spawned is not the part that can be wrong; whether "passes alone" is
reported as a pass is.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from isolate_failures import INTERFERENCE, REAL, isolate, main, node_ids, render

OUTPUT = """
=========================== short test summary info ============================
FAILED tests/test_codebase_index.py::test_index_codebase_on_arbitrary_python_repo - assert False
FAILED tests/test_sandbox_attach_network.py::test_reaches_the_dual_homed_one - AssertionError
ERROR tests/test_broken.py::test_collects_badly
2 failed, 4219 passed, 4 skipped in 394.23s
"""


def test_every_failing_node_id_is_read_including_errors():
    """An ERROR is a failure the run reported, and dropping it would quietly shorten the list."""
    assert node_ids(OUTPUT) == [
        "tests/test_codebase_index.py::test_index_codebase_on_arbitrary_python_repo",
        "tests/test_sandbox_attach_network.py::test_reaches_the_dual_homed_one",
        "tests/test_broken.py::test_collects_badly",
    ]


def test_a_node_reported_twice_is_isolated_once():
    """A rerun plugin or a per-worker summary would otherwise have it counted twice."""
    doubled = OUTPUT + "FAILED tests/test_broken.py::test_collects_badly - again\n"

    assert node_ids(doubled).count("tests/test_broken.py::test_collects_badly") == 1


def test_a_test_that_passes_alone_is_interference_rather_than_a_failure():
    """The distinction the tool exists for. A summary line cannot make it and every lane was
    re-deriving it by hand."""
    results = isolate(["tests/a.py::x"], run=lambda node: (0, "1 passed"))

    assert results[0].verdict == INTERFERENCE
    assert "passes alone" in results[0].detail


def test_a_test_that_fails_alone_is_real():
    results = isolate(["tests/a.py::x"], run=lambda node: (1, "1 failed"))

    assert results[0].verdict == REAL


def test_a_node_id_that_cannot_be_collected_is_not_cleared():
    """Neither real nor interference, and the safe reading is the one that does not clear it.

    Calling a stale node id "interference" would remove it from the list on the strength of a
    test that never ran, which is the same fabrication as reading an empty table as a zero.
    """
    results = isolate(["tests/gone.py::x"], run=lambda node: (4, "no tests ran"))

    assert results[0].verdict == REAL
    assert "stale" in results[0].detail


def test_the_report_says_interference_is_not_automatically_harmless():
    """Shared state that changes an answer rather than raising is the case that matters.

    Reporting interference without that sentence invites the reading that these are noise to be
    ignored -- and the indexer's CWD-relative cache is interference that returns wrong data.
    """
    results = isolate(["tests/a.py::x"], run=lambda node: (0, "1 passed"))

    report = render(results)

    assert "not automatically harmless" in report
    assert "wrong data" in report


def test_being_given_nothing_is_not_an_all_clear(capsys):
    """`0 real failures` from an empty list would read as a measured all-clear on the tree."""
    code = main(["isolate_failures.py"])

    assert code == 2, "no input must not exit 0"
    assert "nothing is claimed" in capsys.readouterr().out
