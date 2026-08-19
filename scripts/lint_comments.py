"""Comment ratio, as a ratchet.

`CLAUDE.md` sets a comment budget. This is the check that makes it real, because a budget stated
in prose is enforced by whoever remembers it -- which is the failure the rewrite of 2026-08-19
exists to stop.

**A ratchet, not a threshold.** The repository sits at 42% comments in Python and 25% in the
console. A hard limit would fail every build today and get disabled within a day. Instead the
current ratio is recorded in `.comment-baseline.json` and this fails only when a tree gets *worse*
-- so existing files are left alone, new code is written to the new standard, and the number falls
as files are touched. Lower the baseline whenever it drops; there is no ceremony to that.

Counting is deliberately crude, and crude is correct here: this measures a trend, not a file. A
docstring line and an inline comment count the same, blank lines count as neither, and no attempt
is made to tell a load-bearing constraint from narration -- that judgement is a reviewer's and
this tool does not pretend to have it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / ".comment-baseline.json"

# The tolerance exists so a small honest change -- one file with a genuinely long constraint --
# does not fail a build. It is not headroom to spend.
TOLERANCE = 0.005


def _python_ratio(paths: list[Path]) -> tuple[int, int]:
    code = comments = 0
    for path in paths:
        in_doc = False
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line:
                continue
            if in_doc:
                comments += 1
                if '"""' in line or "'''" in line:
                    in_doc = False
                continue
            if line.startswith("#"):
                comments += 1
                continue
            if line.startswith('"""') or line.startswith("'''"):
                comments += 1
                # A one-line docstring opens and closes on the same line.
                if line.count('"""') < 2 and line.count("'''") < 2:
                    in_doc = True
                continue
            code += 1
    return code, comments


def _ts_ratio(paths: list[Path]) -> tuple[int, int]:
    code = comments = 0
    for path in paths:
        in_block = False
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line:
                continue
            if in_block:
                comments += 1
                if "*/" in line:
                    in_block = False
                continue
            if line.startswith("/*") or line.startswith("{/*"):
                comments += 1
                if "*/" not in line:
                    in_block = True
                continue
            if line.startswith("//"):
                comments += 1
                continue
            code += 1
    return code, comments


def measure() -> dict[str, float]:
    python = sorted((ROOT / "src" / "sync").rglob("*.py"))
    console = [
        path
        for pattern in ("*.ts", "*.tsx")
        for path in sorted((ROOT / "web" / "src").rglob(pattern))
        if ".test." not in path.name
    ]
    ratios: dict[str, float] = {}
    for name, (code, comments) in (
        ("python", _python_ratio(python)),
        ("console", _ts_ratio(console)),
    ):
        total = code + comments
        ratios[name] = round(comments / total, 4) if total else 0.0
    return ratios


def main() -> int:
    current = measure()

    if "--write" in sys.argv or not BASELINE.is_file():
        BASELINE.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
        print(f"comment baseline written: {current}")
        return 0

    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    failures = []
    for tree, ratio in current.items():
        allowed = baseline.get(tree, 1.0) + TOLERANCE
        if ratio > allowed:
            failures.append(
                f"{tree}: {ratio:.1%} comments, above the baseline {baseline.get(tree, 0):.1%}. "
                f"CLAUDE.md's comment budget -- a comment states a constraint the code cannot "
                f"show, a defect it prevents, or a decision with a live alternative. Narration, "
                f"provenance and arguments for rules a test already enforces are the ones to cut."
            )
        elif ratio < baseline.get(tree, 1.0) - TOLERANCE:
            print(f"{tree}: {ratio:.1%}, below baseline {baseline[tree]:.1%} — run --write to lower it")

    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"comment ratios within baseline: {current}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
