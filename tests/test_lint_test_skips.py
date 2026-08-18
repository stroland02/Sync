"""The no-bare-skips lint exists because a skipped test reports as neither pass nor fail.

`.claude/rules/test-discipline.md` already states the doctrine this enforces: a test that
cannot fail is worse than no test, because it manufactures confidence. A skip with no stated
reason -- or a reason that does not actually name what makes the test unrunnable here -- is
the same defect wearing a different shape: it looks like coverage and asserts nothing.

Proven to work at `codebase-memory-mcp/scripts/check-no-test-skips.sh`, whose own doctrine is
that a skip is legitimate only when it names a platform or a genuinely absent local toolchain.
These tests hold this lint to the same standard the repository holds every other assertion to:
prove it detects a real violation before trusting it to pass anything.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.lint_test_skips import check_source, scan_paths

REPO_ROOT = Path(__file__).resolve().parents[1]


def violations(source: str) -> list[str]:
    return [v.message for v in check_source(source, "sample.py")]


# --- skips that must be flagged --------------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        'pytest.skip("because")',
        "pytest.skip()",
        'pytest.mark.skipif(True, reason="not today")',
        'pytest.mark.skip(reason="flaky")',
        "pytest.skip(compute_reason())",
    ],
)
def test_flags_a_skip_with_no_qualifying_reason(source: str) -> None:
    assert violations(source), f"expected a violation for: {source}"


# --- skips that must not be flagged ----------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        'pytest.skip("needs tools/oasdiff; run scripts/bootstrap_tools.sh")',
        'pytest.mark.skipif(not BINARY.exists(), reason="needs tools/oasdiff")',
        'pytest.skip(f"web/{relative} is absent; this checkout carries no console")',
        'pytest.skip(f"{spec} is gitignored; run scripts/fetch_measurement_inputs.py")',
        'pytest.skip("no staged symbol map at the pin; run the documented fetch first")',
        'pytest.skip("set SYNC_E2E_REPO to the fork created in Step 1")',
        'pytest.mark.skipif(locale_is_utf8, reason="this machine'"'"'s locale codepage is utf-8")',
    ],
)
def test_accepts_a_skip_that_names_what_stops_it(source: str) -> None:
    assert not violations(source), f"unexpected violation for: {source}"


# --- the lint reports where, not just whether -------------------------------------


def test_violation_names_file_and_line() -> None:
    source = "x = 1\npytest.skip('because')\n"
    found = check_source(source, "sample.py")
    assert len(found) == 1
    assert found[0].filename == "sample.py"
    assert found[0].line == 2


# --- proof it can fail, per CLAUDE.md ----------------------------------------------


def test_lint_fails_on_a_real_file_with_an_unqualified_skip(tmp_path: Path) -> None:
    """The check that makes the rest of this file trustworthy.

    A lint that has only ever been run against clean input has not been shown to detect
    anything. This writes a real offending test file and asserts both that `scan_paths`
    flags it and that the CLI exits non-zero, which is what CI actually gates on.
    """
    offender = tmp_path / "test_offender.py"
    offender.write_text(
        "import pytest\n"
        "\n"
        "def test_something() -> None:\n"
        "    pytest.skip('because')\n",
        encoding="utf-8",
    )

    assert scan_paths([offender]), "lint did not flag a known-bad file"

    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "lint_test_skips.py"), str(offender)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode != 0, "CLI exited 0 on a known-bad file; CI would stay green"
    assert "test_offender.py" in result.stdout


# --- regression guard over the tree itself ------------------------------------------


def test_repository_is_clean() -> None:
    found = scan_paths([REPO_ROOT / "tests"])
    assert not found, "\n".join(f"{v.filename}:{v.line}: {v.message}" for v in found)


def test_current_skip_sites_are_a_pinned_baseline() -> None:
    """Fifteen skip sites exist in this tree today, and every one is accepted on purpose.

    A count rather than a name-by-name list, because the point is not which fifteen -- it is
    that a sixteenth arriving silently is impossible: this test goes red until whoever
    added it either states a qualifying reason or takes the count up deliberately.

    Ten held before `tests/test_console_design_tokens.py`; that file added two, both naming
    an absent local checkout in the same words `test_api_routes.py`'s `_web_source` already
    uses for the identical condition ("this checkout carries no console").

    The thirteenth is `tests/test_console_honesty_sentences.py`, added by M7-W158 for the same
    condition. It arrived phrased differently ("the console is not checked out here"), which
    named the same absent checkout in words the lint's vocabulary does not carry, so both halves
    of this file were red on `console-identity`: the reason failed and the count was never taken
    up. Reworded to the phrasing the other three already use, and the count raised deliberately —
    which is exactly the pair of steps this baseline exists to force.

    The fourteenth is `tests/test_bootstrap_tools.py`, added by B130 with the platform mapping it
    covers. `scripts/` is written for bash, so on a machine without one the file has nothing to
    assert against rather than something failing — the same shape as the four console skips above,
    naming an absent tool instead of an absent checkout.

    The fifteenth is `tests/test_container_install.py`, added by `CI-W371`. It executes the `npx`
    doorbell's own JavaScript to prove that a missing Docker and a stopped Docker produce different
    messages, so it needs `node` — the same absent-toolchain shape as the fourteenth, and for the
    same reason: asserting that the two phrases merely *appear* in the file would pass on a source
    that never reaches the branch printing them.
    """
    from scripts.lint_test_skips import find_skip_sites

    sites = []
    for path in sorted((REPO_ROOT / "tests").rglob("test_*.py")):
        sites.extend(find_skip_sites(path.read_text(encoding="utf-8"), str(path)))

    assert len(sites) == 15, [f"{s.filename}:{s.line}" for s in sites]
    assert all(s.permitted for s in sites)


def test_lint_refuses_a_path_that_does_not_exist(tmp_path: Path) -> None:
    """A gate pointed at nothing must not report success.

    The same shape as the import-boundary check that once exited 0 without parsing its
    own argument: a renamed or mistyped directory must not silently narrow the scan while
    the gate stays green.
    """
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "lint_test_skips.py"),
         str(tmp_path / "no-such-directory")],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode != 0, "CLI exited 0 for a path that does not exist"
    assert "no-such-directory" in result.stdout + result.stderr
