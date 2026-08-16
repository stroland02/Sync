#!/usr/bin/env python
"""Fail the build on a test skip whose reason does not name what makes it unavoidable.

A skipped test reports as neither pass nor fail, so a skip with no real reason is the same
defect as a test that cannot fail: it manufactures confidence while asserting nothing.
`.claude/rules/test-discipline.md` states the doctrine; this makes it a gate rather than a
convention a reviewer has to remember to check.

Proven to work at `codebase-memory-mcp/scripts/check-no-test-skips.sh`: a skip is legitimate
only when its reason names a platform or a genuinely absent local toolchain -- something the
test cannot control, rather than something a developer found inconvenient. This walks `tests/`
recursively (a flat glob is the reference implementation's own bug, and it has missed nested
directories for as long as they have existed) and reads every `pytest.skip`, `pytest.mark.skip`
and `pytest.mark.skipif` call site.

Usage:
    python scripts/lint_test_skips.py tests
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# A skip earns its keep when the reason names the thing that actually stops the test: a
# platform/locale fact, a local toolchain, binary or fixture that a documented script
# supplies, or an environment variable that opts a costly or credentialed test in. "because"
# or "flaky" name neither, and that is exactly what this pattern is written to reject.
_PERMITTED_REASON = re.compile(
    r"\btools/|\bscripts/|\blocale\b|\bplatform\b|\bis absent\b|\bgitignored\b|"
    r"\bno staged\b|\bSYNC_[A-Z0-9_]+\b"
)

_SKIP_CALLS = {
    ("pytest", "skip"),
    ("pytest", "mark", "skip"),
    ("pytest", "mark", "skipif"),
}


@dataclass(frozen=True)
class SkipSite:
    filename: str
    line: int
    reason: str | None
    permitted: bool


@dataclass(frozen=True)
class Violation:
    filename: str
    line: int
    message: str


def _dotted(node: ast.expr) -> tuple[str, ...] | None:
    """The dotted attribute chain a call's callee spells, or `None` for anything else.

    Only a plain `a.b.c` chain resolves. An aliased import or a reassigned name reads as
    no match, which is the conservative direction: this must never claim a call it cannot
    actually identify.
    """
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return tuple(reversed(parts))
    return None


def _literal_text(node: ast.expr | None) -> str | None:
    """The reason's literal text, joining an f-string's constant segments.

    An interpolated segment (`{spec}`) contributes nothing here, which is fine: every
    permitted category is written as literal text surrounding the interpolated value,
    never inside it.
    """
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(
            value.value
            for value in node.values
            if isinstance(value, ast.Constant) and isinstance(value.value, str)
        )
    return None


def _reason_argument(node: ast.Call) -> ast.expr | None:
    for keyword in node.keywords:
        if keyword.arg == "reason":
            return keyword.value
    return node.args[0] if node.args else None


def find_skip_sites(source: str, filename: str) -> list[SkipSite]:
    """Every skip call in `source`, permitted or not.

    Returning the permitted ones too is what lets a caller pin the current tree's total as
    a baseline: a count that only changes when someone deliberately adds or resolves a
    skip, rather than one that drifts unnoticed.
    """
    tree = ast.parse(source, filename=filename)
    sites: list[SkipSite] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        dotted = _dotted(node.func)
        if dotted not in _SKIP_CALLS:
            continue
        reason = _literal_text(_reason_argument(node))
        permitted = reason is not None and _PERMITTED_REASON.search(reason) is not None
        sites.append(SkipSite(filename=filename, line=node.lineno, reason=reason, permitted=permitted))
    return sites


def check_source(source: str, filename: str) -> list[Violation]:
    violations: list[Violation] = []
    for site in find_skip_sites(source, filename):
        if site.permitted:
            continue
        named = f"'{site.reason}'" if site.reason is not None else "no literal reason"
        violations.append(
            Violation(
                filename=filename,
                line=site.line,
                message=(
                    f"skip with {named} does not name a platform or an absent local "
                    "toolchain; state what makes this unavoidable or delete the skip"
                ),
            )
        )
    return violations


def _test_files(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    return sorted(p for p in target.rglob("test_*.py") if ".venv" not in p.parts)


def scan_paths(targets: list[Path]) -> list[Violation]:
    """Every violation under `targets`. A path that does not exist is skipped here and
    rejected by `main`, which is the only caller that gates anything."""
    found: list[Violation] = []
    for target in targets:
        if not target.exists():
            continue
        for path in _test_files(target):
            found.extend(check_source(path.read_text(encoding="utf-8"), str(path)))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()

    # A gate pointed at nothing reports success, which is the failure mode this whole
    # script exists to prevent elsewhere: CI names `tests`, and a renamed directory would
    # narrow the scan in silence.
    missing = [p for p in args.paths if not p.exists()]
    if missing:
        for path in missing:
            print(f"{path}: no such file or directory")
        return 2

    found = scan_paths(args.paths)
    for violation in found:
        print(f"{violation.filename}:{violation.line}: {violation.message}")

    if found:
        print(f"\n{len(found)} skip(s) with no qualifying reason.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
