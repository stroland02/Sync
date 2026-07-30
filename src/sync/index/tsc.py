"""Running the TypeScript compiler, and reading what it said.

The gate rejects a patch on the diagnostics the patch introduced, which means
the compiler's output has to be compared against the same tree before the patch
rather than simply counted. `introduced_diagnostics` is that comparison and
`Diagnostic.identity` is the decision it rests on.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from sync.core import VerifyResult

_TSC_TIMEOUT_SECONDS = 300

# `path(line,col): error TSxxxx: message`, the format `tsc` writes when its
# output is not a terminal. The position group is optional because a handful of
# configuration errors -- TS18003 for an empty project, TS5083 for an unreadable
# tsconfig -- are reported against no file at all.
_DIAGNOSTIC = re.compile(
    r"^(?:(?P<file>.+?)\((?P<line>\d+),(?P<column>\d+)\): )?"
    r"error (?P<code>TS\d+): (?P<message>.*)$"
)


@dataclass(frozen=True)
class Diagnostic:
    file: str
    line: int
    column: int
    code: str
    message: str

    @property
    def identity(self) -> tuple[str, str, str]:
        """What makes two diagnostics from two runs the same diagnostic.

        Position is deliberately absent. A patch that adds or removes lines
        moves every diagnostic below it, so an identity carrying line and column
        reports each moved pre-existing error as introduced and each original as
        fixed -- and the gate then rejects a patch for errors it did not write,
        which is the failure this whole comparison exists to end.

        The message stays in, because it is what separates fifteen TS2307s in
        one file naming fifteen different modules. Dropping position costs the
        ability to tell two byte-identical errors apart, which is why the
        comparison counts occurrences instead of taking a set difference.
        """
        return (self.file, self.code, self.message)

    def render(self) -> str:
        position = f"({self.line},{self.column})" if self.file else ""
        return f"{self.file}{position}{': ' if self.file else ''}error {self.code}: {self.message}"


def parse_diagnostics(output: str) -> list[Diagnostic]:
    """Every diagnostic in a `tsc` run's output, in the order it printed them.

    Lines that are not diagnostics yield nothing, which is what lets a caller
    tell a compiler that reported errors from one that failed to run: a timeout,
    a crashed compiler and a failed `npx` download all arrive as a non-zero exit
    carrying prose, and an empty parse of a non-zero exit means the run cannot
    be compared against anything.
    """
    found = []
    for raw in output.splitlines():
        match = _DIAGNOSTIC.match(raw.strip())
        if match is None:
            continue
        file = match["file"] or ""
        found.append(
            Diagnostic(
                file=file,
                line=int(match["line"] or 0),
                column=int(match["column"] or 0),
                code=match["code"],
                message=match["message"],
            )
        )
    return found


def introduced_diagnostics(
    baseline: list[Diagnostic], patched: list[Diagnostic]
) -> list[Diagnostic]:
    """The diagnostics in `patched` that `baseline` does not already account for.

    A multiset difference rather than a set difference: two call sites in one
    file can fail identically, so a patch that adds a third has added one the
    baseline does not cover, and a set would lose it. Each returned diagnostic
    is the one the patched run printed, so it carries the position the next
    patch attempt needs even though the matching ignored it.
    """
    unclaimed = Counter(diagnostic.identity for diagnostic in baseline)
    introduced = []
    for diagnostic in patched:
        if unclaimed[diagnostic.identity]:
            unclaimed[diagnostic.identity] -= 1
        else:
            introduced.append(diagnostic)
    return introduced


def run_tsc(repo_path: Path, timeout: float = _TSC_TIMEOUT_SECONDS) -> VerifyResult:
    """Typecheck a project with `tsc --noEmit`.

    Uses the project's own TypeScript when one is installed, and falls back to
    a pinned npx download otherwise. `npx` is resolved through shutil.which
    because on Windows it is `npx.cmd`, which subprocess will not find by bare name.

    Deliberate: preferring `node_modules/.bin/tsc` means executing the compiler
    binary the project's own lockfile resolved, from whatever registry its
    `.npmrc` names, rather than the version pinned here. Before dependencies
    were installed (see `sync.index.deps`) this branch was unreachable on a
    fresh clone and the pinned npx path always ran; now it is the common case.
    The tradeoff is accepted anyway: a version mismatch between the pinned
    compiler and the one the project was built against produces diagnostics
    that do not describe anything the patch can act on.

    `timeout` defaults to `_TSC_TIMEOUT_SECONDS` and is a parameter only so a
    test can force a real `subprocess.TimeoutExpired` without waiting five
    minutes; callers verifying a patch should not override it.
    """
    repo_path = Path(repo_path)
    local_tsc = repo_path / "node_modules" / ".bin" / ("tsc.cmd" if _on_windows() else "tsc")

    if local_tsc.exists():
        # `--pretty false` is not cosmetic. `parse_diagnostics` matches tsc's plain form,
        # `file(line,column): error TSxxxx:`, and left to itself tsc prints the pretty form
        # wrapped in ANSI colour, which matches nothing. `typescript.py` reads a non-zero
        # exit that parses to zero diagnostics as a compiler that could not run, so ordinary
        # type errors surfaced as a broken toolchain and raised.
        command = [str(local_tsc), "--noEmit", "--pretty", "false"]
    else:
        npx = shutil.which("npx")
        if npx is None:
            raise FileNotFoundError("npx not found on PATH")
        # `--package=` (not a positional `typescript@latest`) is required here:
        # this npm's npx resolves a positional package followed by a same-named
        # bin by re-appending the bin name as an argument, which turns into a
        # stray `tsc` positional file argument and makes tsc ignore tsconfig.json.
        command = [
            npx, "--yes", "--silent", "--package=typescript@latest",
            "tsc", "--noEmit", "--pretty", "false",
        ]

    try:
        # `errors="replace"` because this output is a diagnostic, and because the compiler that
        # produces it is the customer's own -- whatever version their lockfile resolved, from
        # whatever registry their `.npmrc` names. Task 6 shipped this call without it and one
        # accented identifier in a typechecked project crashed the verification gate instead of
        # failing it: the decode error lands on a reader thread, `stdout` comes back `None`, and
        # the concatenation below raises `TypeError` somewhere unrelated. `parse_diagnostics`
        # matches on `file(line,column): error TSxxxx:`, which is ASCII, so a replacement
        # character can only ever land inside a message a human reads.
        result = subprocess.run(
            command,
            cwd=repo_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return VerifyResult(ok=False, diagnostics=f"typecheck timed out after {timeout}s")
    if result.returncode == 0:
        return VerifyResult(ok=True)
    return VerifyResult(ok=False, diagnostics=(result.stdout + result.stderr).strip())


def _on_windows() -> bool:
    return os.name == "nt"
