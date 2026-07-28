"""`sync.core` must import nothing from any sibling package.

This is not a style rule. A third party writing a Twilio adapter depends on
`sync.core` alone; if core reaches into `sync.graph`, that adapter drags in
Postgres.
"""

import os
import shutil
import subprocess
from pathlib import Path

# `python -m importlinter.cli lint` does not work: importlinter/cli.py defines
# its click commands but has no `if __name__ == "__main__":` guard, so running
# the module does nothing and exits 0 whether or not a contract is violated.
# The documented entry point is the `lint-imports` console script instead.
REPO_ROOT = Path(__file__).resolve().parent.parent


def test_core_imports_no_sibling_package():
    lint_imports = shutil.which("lint-imports")
    assert lint_imports is not None, "lint-imports console script not found on PATH"

    # PYTHONIOENCODING is not optional here. import-linter renders through rich, whose
    # Windows console path encodes with the locale codepage -- cp1252 on this machine -- and
    # the spinner it prints is an emoji. Without this the child dies with a UnicodeEncodeError
    # before it evaluates a single contract, and a dead child looks exactly like a broken one.
    result = subprocess.run(
        [lint_imports],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
    )
    output = result.stdout + result.stderr

    # Checked before the exit code, so the two failure modes report differently. A crashed
    # linter and a violated contract both exit non-zero, and a test that cannot tell them
    # apart would let a real breach hide behind an environment fault.
    assert "Contracts:" in output, (
        "lint-imports produced no contract report, so the boundary was never checked:\n" + output
    )
    assert result.returncode == 0, output
