"""The work-item register is one table of unique ids. This fails the gate when it stops being one.

`M0-W346` is why: `WORKLOG.md` reached 32 nested copies of itself, 10.7MB, because a merge conflict
spanning the whole file was resolved by keeping both sides. It doubles, so it is invisible for a day
and then enormous in an hour. `scripts/rebuild_worklog.py` is the resolution; this is the alarm.

    uv run python scripts/check_worklog.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REGISTER = Path(__file__).resolve().parents[1] / "docs" / "superpowers" / "WORKLOG.md"
HEADING = "# Work items"
ROW = re.compile(r"^\| ([A-Z0-9]+-W\d+) \|")


def faults(lines: list[str]) -> list[str]:
    found = []

    headings = [i + 1 for i, line in enumerate(lines) if line.strip() == HEADING]
    if len(headings) > 1:
        found.append(
            f"{len(headings)} `{HEADING}` headings, at lines {headings}. The register is one "
            f"document; a second heading is a copy concatenated on. Rebuild with "
            f"`uv run python scripts/rebuild_worklog.py`, never by keeping both sides."
        )

    seen: dict[str, list[int]] = {}
    for i, line in enumerate(lines):
        if m := ROW.match(line):
            seen.setdefault(m.group(1), []).append(i + 1)
    for item, at in sorted(seen.items()):
        if len(at) > 1:
            found.append(
                f"`{item}` claims {len(at)} rows, at lines {at}. One work item is one row; take "
                f"the next free number, or merge the rows if they are the same item."
            )

    return found


def main() -> int:
    found = faults(REGISTER.read_text(encoding="utf-8").splitlines())
    for fault in found:
        print(f"WORKLOG: {fault}", file=sys.stderr)
    if found:
        return 1
    print(f"WORKLOG: clean ({REGISTER.name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
