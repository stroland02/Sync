"""Resolve a WORKLOG.md conflict by carrying rows forward, never by keeping both sides.

The register is one table of unique ids. A conflict spanning it has exactly one correct
resolution -- the prose skeleton once, and every row from either side exactly once -- and the
resolution that comes to hand instead is "keep both", which is how one file became thirty-two
nested copies of itself (`M0-W346`). Ours is authoritative for prose; theirs contributes rows. **Neither side is trusted to be
clean**, because during the merge that matters every lane branch holds the corrupt file and `--ours`
defaults to it -- a resolver that trusted its skeleton would carry thirty-two copies straight
through the resolution meant to end them.

    uv run python scripts/rebuild_worklog.py --ours HEAD --theirs MERGE_HEAD
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

REGISTER = Path("docs/superpowers/WORKLOG.md")
ROW = re.compile(r"^\| ([A-Z0-9]+-W\d+) \|")


def read(ref: str) -> list[str]:
    out = subprocess.run(
        ["git", "show", f"{ref}:{REGISTER.as_posix()}"], capture_output=True, check=True
    )
    return out.stdout.decode("utf-8").splitlines()


HEADING = "# Work items"


def normalise(lines: list[str]) -> list[str]:
    """One document, one row per id -- whatever arrived.

    Prose is taken from the first copy and rows from all of them. Once a file is several copies
    deep, an appended row lands at the end of whichever copy the appending agent's editor reached,
    so truncating at the second heading silently drops it -- 32 of 335 rows, in the file this was
    written for.
    """
    headings = [i for i, line in enumerate(lines) if line.strip() == HEADING]
    body = lines[: headings[1]] if len(headings) > 1 else lines

    kept, seen = [], set()
    for line in body:
        if m := ROW.match(line):
            if m.group(1) in seen:
                continue
            seen.add(m.group(1))
        kept.append(line)

    buried = []
    for line in lines[len(body) :]:
        if (m := ROW.match(line)) and m.group(1) not in seen:
            seen.add(m.group(1))
            buried.append(line)
    if not buried:
        return kept
    last = max(i for i, line in enumerate(kept) if ROW.match(line))
    return kept[: last + 1] + buried + kept[last + 1 :]


def rebuild(ours: list[str], theirs: list[str]) -> list[str]:
    ours = normalise(ours)
    have = {m.group(1) for line in ours if (m := ROW.match(line))}
    carried = []
    for line in theirs:
        if (m := ROW.match(line)) and m.group(1) not in have:
            have.add(m.group(1))
            carried.append(line)
    last = max(i for i, line in enumerate(ours) if ROW.match(line))
    return ours[: last + 1] + carried + ours[last + 1 :]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ours", default="HEAD")
    parser.add_argument("--theirs", default="MERGE_HEAD")
    args = parser.parse_args()
    merged = rebuild(read(args.ours), read(args.theirs))
    REGISTER.write_text("\n".join(merged) + "\n", encoding="utf-8")
    rows = [m.group(1) for line in merged if (m := ROW.match(line))]
    print(f"{len(merged)} lines, {len(rows)} rows, {len(set(rows))} unique")


if __name__ == "__main__":
    main()
