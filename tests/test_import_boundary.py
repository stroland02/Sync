"""`sync.core` must import nothing from any sibling package.

This is not a style rule. A third party writing a Twilio adapter depends on
`sync.core` alone; if core reaches into `sync.graph`, that adapter drags in
Postgres.
"""

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

    result = subprocess.run(
        [lint_imports],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr
