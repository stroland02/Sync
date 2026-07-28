#!/usr/bin/env python
"""Fail the build on a text call that does not name its encoding.

On Windows every one of these defaults to the locale codepage -- cp1252 on the
development machine -- so a single non-ASCII byte corrupts or raises, and only on that
platform. Every fixture in this repository is ASCII, which means the test suite can
never catch it: the failure arrives first against real vendor data or a real customer
repository.

`subprocess` is the worst of them. A decode error there is raised on the reader thread
and never propagates: the call returns with `stdout` set to `None`, and the next line
that concatenates it raises `TypeError` somewhere unrelated.

Usage:
    python scripts/lint_encoding.py src scripts tests
"""

from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass
from pathlib import Path

# Calls that open a text stream. `read_bytes`/`write_bytes` are deliberately absent:
# bytes are not decoded, so naming an encoding there would be meaningless.
_TEXT_IO_NAMES = frozenset({"open", "read_text", "write_text"})

# Kwargs that switch a subprocess call from bytes to decoded text.
_TEXT_MODE_KWARGS = frozenset({"text", "universal_newlines"})


@dataclass(frozen=True)
class Violation:
    filename: str
    line: int
    message: str


def _kwarg(node: ast.Call, name: str) -> ast.expr | None:
    for keyword in node.keywords:
        if keyword.arg == name:
            return keyword.value
    return None

def _called_name(node: ast.Call) -> str | None:
    """The bare function name, whether called directly or as an attribute."""
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _is_binary_open(node: ast.Call) -> bool:
    """Whether an `open` call is in binary mode, where an encoding is invalid.

    A mode that is not a literal cannot be judged, so it is treated as text -- the
    conservative direction. A caller passing a computed mode can still satisfy the lint
    by naming the encoding, which is the right thing to do when the mode is unknown.
    """
    mode = node.args[1] if len(node.args) > 1 else _kwarg(node, "mode")
    if isinstance(mode, ast.Constant) and isinstance(mode.value, str):
        return "b" in mode.value
    return False


def _wants_text(node: ast.Call) -> bool:
    """Whether a subprocess-style call asked for decoded output."""
    for name in _TEXT_MODE_KWARGS:
        value = _kwarg(node, name)
        if isinstance(value, ast.Constant) and value.value is True:
            return True
    return False


def check_source(source: str, filename: str) -> list[Violation]:
    """Every text call in `source` that does not name an encoding."""
    tree = ast.parse(source, filename=filename)
    found: list[Violation] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _kwarg(node, "encoding") is not None:
            continue

        name = _called_name(node)
        if name in _TEXT_IO_NAMES:
            if name == "open" and _is_binary_open(node):
                continue
            found.append(
                Violation(
                    filename=filename,
                    line=node.lineno,
                    message=f"{name}() without encoding=; on Windows this defaults to cp1252",
                )
            )
        elif _wants_text(node):
            found.append(
                Violation(
                    filename=filename,
                    line=node.lineno,
                    message=(
                        f"{name or 'call'}() decodes output without encoding=; a decode error "
                        "here is swallowed and surfaces as stdout=None"
                    ),
                )
            )

    return found


def _python_files(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    return sorted(p for p in target.rglob("*.py") if ".venv" not in p.parts)


def scan_paths(targets: list[Path]) -> list[Violation]:
    """Every violation under `targets`. A path that does not exist is skipped here and
    rejected by `main`, which is the only caller that gates anything."""
    found: list[Violation] = []
    for target in targets:
        if not target.exists():
            continue
        for path in _python_files(target):
            found.extend(check_source(path.read_text(encoding="utf-8"), str(path)))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()

    # A gate pointed at nothing reports success, which is the failure mode this whole
    # script exists to prevent elsewhere: CI names `src scripts tests`, and a renamed
    # directory would narrow the scan in silence.
    missing = [p for p in args.paths if not p.exists()]
    if missing:
        for path in missing:
            print(f"{path}: no such file or directory")
        return 2

    found = scan_paths(args.paths)
    for violation in found:
        print(f"{violation.filename}:{violation.line}: {violation.message}")

    if found:
        print(f"\n{len(found)} call(s) without an explicit encoding.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
