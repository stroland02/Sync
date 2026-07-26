"""Install a JavaScript project's dependencies so typechecking means something.

`tsc --noEmit` against a tree with no `node_modules` reports an unresolved
import for every dependency -- 1,264 of them on the M0 acceptance repository --
which drowns any diagnostic the patch is responsible for.

Every command here passes `--ignore-scripts`. Sync does not execute customer
code, and a dependency's `postinstall` is customer code by any reading. Type
declarations resolve without it; lifecycle scripts are what we are refusing.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

_INSTALL_TIMEOUT_SECONDS = 600

# yarn v1 refuses to install when the project's `engines.node` does not match
# the interpreter it finds. We are resolving type declarations, not running the
# project, so the constraint does not apply to what we do with the tree.
_COMMANDS = {
    "yarn.lock": ("yarn", ["install", "--frozen-lockfile", "--ignore-scripts", "--ignore-engines"]),
    "package-lock.json": ("npm", ["ci", "--ignore-scripts"]),
    "pnpm-lock.yaml": ("pnpm", ["install", "--frozen-lockfile", "--ignore-scripts"]),
}
_FALLBACK = ("npm", ["install", "--ignore-scripts", "--no-audit", "--no-fund"])


def install_dependencies(repo_path: Path, timeout: float = _INSTALL_TIMEOUT_SECONDS) -> None:
    """Populate `node_modules` for a checked-out project.

    Does nothing for a tree with no `package.json`, or one whose `node_modules`
    is already populated -- the graph calls `static_verify` up to three times
    against the same clone, and paying for the install on each is pure latency.
    """
    repo_path = Path(repo_path)
    if not (repo_path / "package.json").exists():
        return
    if any((repo_path / "node_modules").glob("*")):
        return

    manager, args = _FALLBACK
    for lockfile, command in _COMMANDS.items():
        if (repo_path / lockfile).exists():
            manager, args = command
            break

    executable = shutil.which(manager)
    if executable is None:
        raise FileNotFoundError(f"{manager} not found on PATH")

    result = subprocess.run(
        [executable, *args],
        cwd=repo_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(f"{manager} install failed: {(result.stdout + result.stderr).strip()[-800:]}")
