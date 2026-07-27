"""The encoding lint exists because no test can catch what it catches.

`CLAUDE.md` records the reason: every fixture in this repository is ASCII, so a missing
`encoding="utf-8"` never fails here. It fails first against real vendor data or a real
customer repository, on Windows, where the default is cp1252. A lint runs over call sites
rather than over executions, which is why it sees what the suite cannot.

These tests hold the lint to the standard the repository holds every other assertion to:
prove it detects a real violation before trusting it to pass anything.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.lint_encoding import check_source, scan_paths

REPO_ROOT = Path(__file__).resolve().parents[1]


def violations(source: str) -> list[str]:
    return [v.message for v in check_source(source, "sample.py")]


# --- calls that must be flagged -------------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        'open("f")',
        'open("f", "w")',
        'open("f", mode="w")',
        "path.read_text()",
        "path.write_text(body)",
        "Path(name).read_text()",
        'subprocess.run(cmd, text=True)',
        'subprocess.run(cmd, capture_output=True, text=True)',
        'subprocess.run(cmd, universal_newlines=True)',
    ],
)
def test_flags_missing_encoding(source: str) -> None:
    assert violations(source), f"expected a violation for: {source}"


# --- calls that must not be flagged ---------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        'open("f", encoding="utf-8")',
        'open("f", "w", encoding="utf-8")',
        'open("f", "rb")',
        'open("f", mode="wb")',
        'open("f", "r+b")',
        'path.read_text(encoding="utf-8")',
        'path.write_text(body, encoding="utf-8")',
        "path.read_bytes()",
        "path.write_bytes(blob)",
        'subprocess.run(cmd, text=True, encoding="utf-8")',
        "subprocess.run(cmd, capture_output=True)",
        "json.dumps(obj)",
    ],
)
def test_accepts_explicit_encoding_and_binary(source: str) -> None:
    assert not violations(source), f"unexpected violation for: {source}"


# --- the lint reports where, not just whether ------------------------------------


def test_violation_names_file_and_line() -> None:
    source = "x = 1\ny = open('f')\n"
    found = check_source(source, "sample.py")
    assert len(found) == 1
    assert found[0].filename == "sample.py"
    assert found[0].line == 2


# --- proof it can fail, per CLAUDE.md ---------------------------------------------


def test_lint_fails_on_a_real_file_with_encoding_removed(tmp_path: Path) -> None:
    """The check that makes the rest of this file trustworthy.

    A lint that has only ever been run against clean input has not been shown to detect
    anything. This takes a real call site, strips the argument, and asserts the lint
    catches it -- and that the CLI exits non-zero, which is what CI actually gates on.
    """
    offender = tmp_path / "offender.py"
    offender.write_text(
        "from pathlib import Path\n"
        "def load(p: Path) -> str:\n"
        "    return p.read_text()\n",
        encoding="utf-8",
    )

    assert scan_paths([offender]), "lint did not flag a known-bad file"

    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "lint_encoding.py"), str(offender)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode != 0, "CLI exited 0 on a known-bad file; CI would stay green"
    assert "read_text" in result.stdout


# --- regression guard over the tree itself ----------------------------------------


def test_repository_is_clean() -> None:
    targets = [REPO_ROOT / "src", REPO_ROOT / "scripts", REPO_ROOT / "tests"]
    found = scan_paths(targets)
    assert not found, "\n".join(f"{v.filename}:{v.line}: {v.message}" for v in found)
