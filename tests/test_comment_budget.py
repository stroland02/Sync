"""The comment ratchet, wired to something that runs.

`CLAUDE.md` calls `scripts/lint_comments.py` an enforced ratchet, and until this file nothing
called it -- not CI, not the suite, not the PostToolUse hook. It went red during the console
migration of 2026-08-21 and stayed red across three commits with every other gate green, which is
the decay the governing principle is about: a rule enforced where it is read is enforced by whoever
remembers it.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT = _REPO_ROOT / "scripts" / "lint_comments.py"


def _run(script: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script)],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        # Explicit, because `text=True` alone decodes with the platform codec: on this Windows
        # runner that is cp1252, and the script's own output carries an em dash. A decode error
        # here is swallowed and arrives as `stdout=None`, which would read as a guard that ran
        # and said nothing. `scripts/lint_encoding.py` is what catches the omission.
        encoding="utf-8",
        check=False,
    )


def test_the_comment_ratio_has_not_got_worse():
    assert _SCRIPT.is_file(), f"{_SCRIPT} is gone -- this guard is blind"

    result = _run(_SCRIPT)

    assert result.returncode == 0, (
        "the comment budget ratcheted the wrong way. Cut narration, provenance, and arguments for "
        "why a change is correct -- a comment states a constraint the code cannot show, a defect "
        "it prevents, or a decision with a live alternative:\n" + result.stdout + result.stderr
    )


def test_this_guard_reads_the_exit_code_rather_than_merely_running_something(tmp_path: Path) -> None:
    """The failure mode `CI-W534` recorded: the import-boundary guard's first form exited 0 without
    parsing its argument, so it passed while testing nothing.
    """
    failing = tmp_path / "always_fails.py"
    failing.write_text("import sys\nsys.exit(1)\n", encoding="utf-8")

    assert _run(failing).returncode == 1, "a non-zero exit must reach this test, or it proves nothing"
