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
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from sync.core import VerifyResult
from sync.index.npx_lock import LockTimeout, resolve_lock

_TSC_TIMEOUT_SECONDS = 300

# Fixed rather than per-run: the race this guards is host-wide -- any two
# `sync` processes resolving TypeScript through npx at once, not just two
# calls within one process -- so every caller on this host has to agree on
# the same lock path. `tempfile.gettempdir()` is per-user on every platform
# this runs on, matching the scope of the npx cache it protects.
_NPX_RESOLVE_LOCK_PATH = Path(tempfile.gettempdir()) / "sync-npx-typescript-resolve.lock"

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


# The major this gate is verified against, pinned rather than `latest` (B192). `latest` drifted
# to TypeScript 7, whose native CLI answers `--noEmit --pretty false` over a missing project with
# its help text -- a usage error the parser reads as a compiler that could not run, which
# abandoned the first real remediation on this repository at the baseline. A major is a CLI
# contract; adopting a new one is a deliberate act with a measurement attached, not a drift.
_TYPESCRIPT_SPEC = "typescript@5"


def _project_dir(repo_path: Path) -> Path | None:
    """The directory whose `tsconfig.json` this repository's typecheck should run against.

    The root when it has one; otherwise the nearest nested project, depth two at most, chosen
    deterministically -- this repository's own console lives at `web/tsconfig.json`, and a
    baseline pointed at the root abandoned the run (B192). `node_modules` is excluded because
    every dependency ships a tsconfig and none of them is the customer's project.
    """
    if (repo_path / "tsconfig.json").is_file():
        return repo_path
    nested = sorted(
        candidate.parent
        for pattern in ("*/tsconfig.json", "*/*/tsconfig.json")
        for candidate in repo_path.glob(pattern)
        if "node_modules" not in candidate.parts
    )
    return nested[0] if nested else None


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

    B101: two callers reaching the npx fallback at once against a cold,
    shared cache race on it -- one still writing the package while the other
    reads it. `_ensure_typescript_resolved` closes that under
    `npx_lock.resolve_lock` before the real compile command below ever runs,
    so by the time this function's own `subprocess.run` executes, the cache
    this call reads from is guaranteed warm.
    """
    repo_path = Path(repo_path)
    project = _project_dir(repo_path)
    if project is None:
        # An honest refusal rather than a compiler usage error: without a project there is no
        # baseline to establish, and "this repository declares no TypeScript project" is an
        # answer the caller can act on where TS7's help text was not (B192).
        return VerifyResult(
            ok=False,
            diagnostics="no tsconfig.json found at the repository root or up to two directories deep, "
            "so there is no TypeScript project to typecheck",
        )

    # The compiler nearest the project wins: a nested project's own `node_modules` first, the
    # repository root's second -- executing the binary the customer's lockfile resolved is the
    # standing decision, and a nested console's lockfile lives beside its tsconfig.
    tsc_name = "tsc.cmd" if _on_windows() else "tsc"
    local_candidates = [
        project / "node_modules" / ".bin" / tsc_name,
        repo_path / "node_modules" / ".bin" / tsc_name,
    ]
    local_tsc = next((candidate for candidate in local_candidates if candidate.exists()), None)

    try:
        if local_tsc is not None:
            # `--pretty false` is not cosmetic. `parse_diagnostics` matches tsc's plain form,
            # `file(line,column): error TSxxxx:`, and left to itself tsc prints the pretty form
            # wrapped in ANSI colour, which matches nothing. `typescript.py` reads a non-zero
            # exit that parses to zero diagnostics as a compiler that could not run, so ordinary
            # type errors surfaced as a broken toolchain and raised.
            command = [str(local_tsc), "--noEmit", "--pretty", "false", "-p", str(project)]
        else:
            npx = shutil.which("npx")
            if npx is None:
                raise FileNotFoundError("npx not found on PATH")
            _ensure_typescript_resolved(npx, timeout=timeout)
            # `--package=` (not a positional package spec) is required here:
            # this npm's npx resolves a positional package followed by a same-named
            # bin by re-appending the bin name as an argument, which turns into a
            # stray `tsc` positional file argument and makes tsc ignore tsconfig.json.
            command = [
                npx, "--yes", "--silent", f"--package={_TYPESCRIPT_SPEC}",
                "tsc", "--noEmit", "--pretty", "false", "-p", str(project),
            ]

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
    except (subprocess.TimeoutExpired, LockTimeout):
        return VerifyResult(ok=False, diagnostics=f"typecheck timed out after {timeout}s")
    if result.returncode == 0:
        return VerifyResult(ok=True)
    return VerifyResult(ok=False, diagnostics=(result.stdout + result.stderr).strip())


# Carries the pinned major, so moving the pin re-resolves rather than trusting a marker another
# major wrote.
_NPX_RESOLVE_MARKER = "sync-npx-typescript5-resolved.marker"


def _marker_path() -> Path:
    if "FAKE_NPX_CACHE_DIR" in os.environ:
        return Path(os.environ["FAKE_NPX_CACHE_DIR"]) / _NPX_RESOLVE_MARKER
    return Path(tempfile.gettempdir()) / _NPX_RESOLVE_MARKER


def _lock_path() -> Path:
    if "FAKE_NPX_CACHE_DIR" in os.environ:
        return Path(os.environ["FAKE_NPX_CACHE_DIR"]) / "sync-npx-typescript-resolve.lock"
    return _NPX_RESOLVE_LOCK_PATH


def _ensure_typescript_resolved(npx: str, timeout: float) -> None:
    """Force `npx --package=typescript@latest` to exist in the shared cache,
    under a lock, before any caller execs the compiler out of it. This is
    B101.

    `resolve_lock` makes at most one process on this host resolve the
    package at a time. The command run under it is a bare `tsc --version`,
    not the real `--noEmit` invocation -- forcing the resolve is all this
    step is for. Once warm, callers skip the lock entirely so parallel
    verifications never serialize or starve on it.
    """
    marker = _marker_path()
    if marker.exists():
        return

    with resolve_lock(_lock_path(), timeout=timeout):
        if marker.exists():
            return
        subprocess.run(
            [npx, "--yes", "--silent", f"--package={_TYPESCRIPT_SPEC}", "tsc", "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        try:
            marker.write_text("1", encoding="utf-8")
        except OSError:
            pass



def _on_windows() -> bool:
    return os.name == "nt"
