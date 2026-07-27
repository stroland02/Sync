"""Static verification by typechecking with the TypeScript compiler."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from sync.core import VerifyResult

_TSC_TIMEOUT_SECONDS = 300


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
        command = [str(local_tsc), "--noEmit"]
    else:
        npx = shutil.which("npx")
        if npx is None:
            raise FileNotFoundError("npx not found on PATH")
        # `--package=` (not a positional `typescript@latest`) is required here:
        # this npm's npx resolves a positional package followed by a same-named
        # bin by re-appending the bin name as an argument, which turns into a
        # stray `tsc` positional file argument and makes tsc ignore tsconfig.json.
        command = [npx, "--yes", "--silent", "--package=typescript@latest", "tsc", "--noEmit"]

    try:
        result = subprocess.run(
            command,
            cwd=repo_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return VerifyResult(ok=False, diagnostics=f"typecheck timed out after {timeout}s")
    if result.returncode == 0:
        return VerifyResult(ok=True)
    return VerifyResult(ok=False, diagnostics=(result.stdout + result.stderr).strip())


def _on_windows() -> bool:
    return os.name == "nt"
