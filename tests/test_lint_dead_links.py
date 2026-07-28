"""The dead-link lint exists because no test can catch what it catches.

Four times a complete, well-tested component shipped with no caller anywhere in `src/`, and
every one of them was found weeks later by a human reading code. The tests were not weak.
Being tested and being reachable are different properties, and only the first was ever
checked. A lint runs over the reference graph rather than over executions, which is why it
sees what a passing suite cannot.

These tests hold the lint to the standard `CLAUDE.md` sets for anything CI gates by exit
code: prove it detects a real violation before trusting it to pass anything. That means
asserting on the exit code *and* on the output naming the symbol, in that order -- a
non-zero exit with unrelated output is a broken lint that looks like a working one.

The second half matters as much as the first. A lint that reports every legitimately
uncalled public symbol is noise, gets disabled inside a week, and takes the attention that
would have gone to a real finding with it. `test_clean_fixture_*` is what stops that.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts.lint_dead_links import Violation, scan_paths

REPO_ROOT = Path(__file__).resolve().parents[1]
LINT = REPO_ROOT / "scripts" / "lint_dead_links.py"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "dead_links"

DEAD = FIXTURES / "dead"
CLEAN = FIXTURES / "clean"
UNREASONED = FIXTURES / "unreasoned"


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(LINT), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def names(violations: list[Violation]) -> set[str]:
    return {v.qualname for v in violations}


# --- proof it can fail ------------------------------------------------------------


def test_reports_a_method_nothing_calls() -> None:
    """The `set_merge_outcome` shape: an update path with tests and no caller."""
    found = scan_paths([DEAD / "sync"])
    assert "GraphStore.set_merge_outcome" in names(found)


def test_cli_exits_non_zero_and_names_the_symbol() -> None:
    """Exit code first, then the output. A gate that exits non-zero for an unrelated
    reason is indistinguishable from a working one until the day it matters."""
    result = run_cli(str(DEAD / "sync"))
    assert result.returncode != 0, "CLI exited 0 on a known-bad tree; CI would stay green"
    assert "set_merge_outcome" in result.stdout


def test_a_symbol_with_a_caller_is_not_reported() -> None:
    """`GraphStore` and `record` are reached from another module in the same tree."""
    found = names(scan_paths([DEAD / "sync"]))
    assert "GraphStore" not in found
    assert "GraphStore.record" not in found


def test_a_package_re_export_is_not_a_use() -> None:
    """`sync/graph/__init__.py` imports `GraphStore` and that is packaging, not use.

    Counting it would make every `__all__` entry in the repository look reachable, which
    is the single change that would turn this lint into decoration.
    """
    found = scan_paths([DEAD / "sync"])
    assert all("__init__.py" not in v.filename for v in found)


def test_violation_names_file_and_line() -> None:
    found = [v for v in scan_paths([DEAD / "sync"]) if v.qualname.endswith("set_merge_outcome")]
    assert len(found) == 1
    assert found[0].filename.endswith("store.py")
    assert found[0].line == 13


# --- proof it is not noise --------------------------------------------------------


def test_clean_fixture_reports_nothing() -> None:
    """One of every legitimate case in one tree. If this ever reports, the lint is on its
    way to being switched off, so read the failure as a scoping defect rather than a find."""
    found = scan_paths([CLEAN / "sync"])
    assert not found, "\n".join(f"{v.filename}:{v.line}: {v.message}" for v in found)


def test_clean_fixture_exits_zero() -> None:
    result = run_cli(str(CLEAN / "sync"))
    assert result.returncode == 0, result.stdout + result.stderr


def test_clean_fixture_actually_contains_the_cases_it_claims_to() -> None:
    """A clean fixture that is clean because it is empty proves nothing.

    This is the guard on the guard: it fails if someone deletes a legitimate case from the
    fixture, which would let the exemption it exercises rot untested.
    """
    sources = {p.name for p in (CLEAN / "sync").rglob("*.py")}
    assert {"models.py", "protocols.py", "ingest.py", "agent.py", "errors.py",
            "registry.py", "legacy.py", "cli.py"} <= sources


# --- the opt-out ------------------------------------------------------------------


def test_opt_out_with_a_reason_is_honoured() -> None:
    found = names(scan_paths([CLEAN / "sync"]))
    assert "kept_for_the_sdk" not in found


def test_opt_out_without_a_reason_is_itself_a_violation() -> None:
    """An opt-out that says nothing is how a lint degrades into decoration."""
    found = scan_paths([UNREASONED / "sync"])
    assert names(found) == {"kept_for_the_sdk"}
    assert "reason" in found[0].message


def test_cli_exits_non_zero_on_an_unreasoned_opt_out() -> None:
    result = run_cli(str(UNREASONED / "sync"))
    assert result.returncode != 0
    assert "kept_for_the_sdk" in result.stdout


# --- the baseline -----------------------------------------------------------------


def test_a_baselined_violation_does_not_fail_the_gate(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.txt"
    baseline.write_text(
        "# known, accepted, and expected to shrink\n"
        "sync/graph/store.py:GraphStore.set_merge_outcome\n",
        encoding="utf-8",
    )
    result = run_cli(str(DEAD / "sync"), "--baseline", str(baseline), "--root", str(DEAD))
    assert result.returncode == 0, result.stdout + result.stderr


def test_a_baseline_entry_that_no_longer_violates_fails(tmp_path: Path) -> None:
    """The property that makes the list shrink rather than rot.

    A threshold absorbs a fix silently. A named entry that has been fixed must fail, so the
    line is deleted in the same commit that fixed it.
    """
    baseline = tmp_path / "baseline.txt"
    baseline.write_text(
        "sync/graph/store.py:GraphStore.set_merge_outcome\n"
        "sync/graph/store.py:GraphStore.record\n",
        encoding="utf-8",
    )
    result = run_cli(str(DEAD / "sync"), "--baseline", str(baseline), "--root", str(DEAD))
    assert result.returncode != 0
    assert "GraphStore.record" in result.stdout
    assert "no longer" in result.stdout


# --- the gate cannot be pointed at nothing ----------------------------------------


def test_refuses_a_path_that_does_not_exist(tmp_path: Path) -> None:
    """CI names `src`. A renamed directory must not narrow the scan in silence -- the same
    shape as the import-boundary check that once exited 0 without parsing its argument."""
    result = run_cli(str(tmp_path / "no-such-directory"))
    assert result.returncode != 0
    assert "no-such-directory" in result.stdout + result.stderr


# --- the repository itself ---------------------------------------------------------


def test_the_repository_matches_its_baseline() -> None:
    """`src/` against the checked-in list of accepted violations.

    This is the regression guard: a newly unreachable symbol fails here as well as in CI,
    and a repaired one fails until its baseline line is removed.
    """
    from scripts.lint_dead_links import load_baseline, partition

    found = scan_paths([REPO_ROOT / "src"])
    baseline = load_baseline(REPO_ROOT / "scripts" / "dead_links_baseline.txt")
    new, stale = partition(found, baseline, REPO_ROOT)
    assert not new, "unreachable and not baselined:\n" + "\n".join(
        f"{v.filename}:{v.line}: {v.message}" for v in new
    )
    assert not stale, "baseline entries that no longer violate; delete them:\n" + "\n".join(stale)
