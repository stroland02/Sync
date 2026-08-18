"""No tracked file may carry a conflict marker, because once committed a marker is just content.

**Measured 2026-08-18.** `main` carried committed conflict markers in six files. `npm run build`
died with `PARSE_ERROR` at `settings-page.tsx:105` on a literal `<<<<<<< HEAD`, the console did not
parse, and no lane could gate against `main` until it was repaired at `b8e5212b`.

**The mechanism is the part worth writing down.** A marker that has been *committed* is no longer a
conflict — it is ordinary file content. `git status` shows no `UU`. `git merge` reports success. A
gate step checking for `^UU`, which is the guard every lane here had been running, passes clean and
cannot see this failure at all. Each lane then merged the markers into its own tree through a merge
that was genuinely conflict-free, and inherited a build that could not parse.

So the check has to read file *content* rather than merge *state*, and it has to be a test rather
than a habit: a grep each lane is asked to remember is a guard that is present exactly as often as
somebody remembers it at five in the morning, which is when this landed.

It scans every tracked file rather than a source subtree. The six files were TypeScript and the
compiler would eventually have said so, but a marker in `schema.sql`, a fixture, or a rule file
breaks something quieter and no compiler is watching.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Built by repetition rather than written out, so this file does not report itself. A test that
# trips its own check has to be exempted, and an exemption is the thing most likely to be widened
# later by somebody who does not know why it exists.
OURS = "<" * 7
THEIRS = ">" * 7
BASE = "|" * 7
DIVIDER = "=" * 7


def conflicted_lines(text: str) -> list[tuple[int, str]]:
    """Return the 1-indexed lines of `text` that are conflict markers.

    `<<<<<<<`, `>>>>>>>` and the diff3 `|||||||` are unambiguous: no language in this repository
    gives a line beginning with seven of those characters any other meaning.

    `=======` is deliberately **not** unambiguous — it is also how Markdown and reStructuredText
    underline a heading — so it is reported only in a file already known to be conflicted. The
    trade is stated rather than hidden: a file carrying a lone divider and nothing else is missed.
    That cannot arise from a merge, only from a hand-edit that removed two markers and left one.
    """
    lines = text.splitlines()
    unambiguous = [
        (number, line)
        for number, line in enumerate(lines, start=1)
        if line.startswith((OURS, THEIRS, BASE))
    ]
    if not unambiguous:
        return []
    dividers = [
        (number, line)
        for number, line in enumerate(lines, start=1)
        if line.rstrip() == DIVIDER
    ]
    return sorted(unambiguous + dividers)


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],  # subprocess-encoding: allow - git emits utf-8 paths
        cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", check=True,
    )
    return [REPO_ROOT / name for name in result.stdout.split("\0") if name]


def test_a_planted_marker_is_found(tmp_path: Path) -> None:
    """The negative control. Without this, the gate below passes by finding nothing anywhere."""
    planted = tmp_path / "planted.tsx"
    planted.write_text(
        f"const a = 1\n{OURS} HEAD\nconst b = 2\n{DIVIDER}\nconst b = 3\n{THEIRS} origin/main\n",
        encoding="utf-8",
    )

    found = conflicted_lines(planted.read_text(encoding="utf-8"))

    assert [number for number, _ in found] == [2, 4, 6]


def test_a_heading_underline_is_not_a_conflict() -> None:
    """Markdown underlines a heading the same way a merge divides a hunk."""
    assert conflicted_lines("Toolchain\n=======\n\nsome prose\n") == []


def test_no_tracked_file_carries_a_conflict_marker() -> None:
    violations: list[str] = []
    for path in tracked_files():
        try:
            text = path.read_bytes().decode("utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            # Binary, or a path recorded in the index that this worktree does not hold.
            continue
        for number, line in conflicted_lines(text):
            violations.append(f"{path.relative_to(REPO_ROOT).as_posix()}:{number}: {line[:60]}")

    assert not violations, (
        "a committed conflict marker is ordinary file content -- `git status` shows no `UU` and "
        "the merge that carried it reported success, so nothing but a content scan sees it:\n  "
        + "\n  ".join(violations)
    )
