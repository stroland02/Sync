"""PostToolUse gate on every edited file.

`CLAUDE.md`'s governing principle is to encode a rule where it fails. The encoding rule is the
sharpest case in this repository: every fixture here is ASCII, so **no test can catch a missing
`encoding="utf-8"`** -- it fails first against real vendor data, on Windows, in production. A lint
existed and ran only when somebody remembered. This runs on the edit.

Deliberately narrow. It checks the one file just written, reports to stderr with exit 2 so the
agent sees the message and can fix it immediately, and stays silent otherwise. A hook that reports
on unrelated files trains the agent to ignore it.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def edited_path() -> Path | None:
    """The file this hook fired for, or None when the payload names none."""
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return None
    raw = (payload.get("tool_input") or {}).get("file_path")
    if not raw:
        return None
    # Resolved, because the payload may carry a relative path and the containment check below
    # compares against an absolute root. Comparing the two raises, which this hook would have
    # swallowed as "not our file" -- it passed a real violation on its first probe.
    path = Path(raw).resolve()
    return path if path.is_file() else None


def main() -> int:
    path = edited_path()
    if path is None or path.suffix != ".py":
        return 0
    try:
        path.relative_to(ROOT)
    except ValueError:
        return 0

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "lint_encoding.py"), str(path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=ROOT,
    )
    if result.returncode == 0:
        return 0

    print(
        f"Encoding lint failed on {path.name}. Every fixture in this repository is ASCII, so no "
        f"test will catch this -- it fails first against real vendor data on Windows.\n"
        f"{(result.stdout or '') + (result.stderr or '')}",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
