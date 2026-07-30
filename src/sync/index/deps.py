"""Install a JavaScript project's dependencies so typechecking means something.

`tsc --noEmit` against a tree with no `node_modules` reports an unresolved
import for every dependency -- 1,264 of them on the M0 acceptance repository --
which drowns any diagnostic the patch is responsible for.

Every command here passes `--ignore-scripts`. Sync does not execute customer
code, and a dependency's `postinstall` is customer code by any reading. Type
declarations resolve without it; lifecycle scripts are what we are refusing.
"""

from __future__ import annotations

import os
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

# The only thing installing creates, and the only ignored content `static_verify`
# keeps while it measures the tree a push would carry. Every package manager here
# writes its own bookkeeping inside this directory rather than beside it.
DEPENDENCY_DIRS = frozenset({"node_modules"})


def _node_modules_populated(repo_path: Path) -> bool:
    """True only when `node_modules` holds a real package, not just npm's own
    bookkeeping.

    `npm ci` deletes `node_modules` and repopulates it; killed by the timeout
    partway through, it leaves the directory holding only a hidden file such
    as `.package-lock.json` and a fraction of the real packages.
    `Path.glob('*')` matches dotfiles, so a guard built on it would count that
    wreckage as a complete install and never repair it.
    """
    node_modules = repo_path / "node_modules"
    if not node_modules.is_dir():
        return False
    return any(not entry.name.startswith(".") for entry in node_modules.iterdir())


def install_dependencies(repo_path: Path, timeout: float = _INSTALL_TIMEOUT_SECONDS) -> bool:
    """Populate `node_modules` for a checked-out project. True if it ran one.

    Does nothing for a tree with no `package.json`, or one whose `node_modules`
    is already populated -- the graph calls `static_verify` up to three times
    against the same clone, and paying for the install on each is pure latency.

    The return value is what `sync.index.dependency_edits` compares mtimes
    against: an install that ran wrote every file under `node_modules` just now,
    and a caller holding an older mark would read all of them as edits.
    """
    repo_path = Path(repo_path)
    if not (repo_path / "package.json").exists():
        return False
    if _node_modules_populated(repo_path):
        return False

    manager, args = _FALLBACK
    for lockfile, command in _COMMANDS.items():
        if (repo_path / lockfile).exists():
            manager, args = command
            break

    executable = shutil.which(manager)
    if executable is None:
        raise FileNotFoundError(f"{manager} not found on PATH")

    # A committed `.yarnrc`/`.yarnrc.yml` can set `yarn-path`/`yarnPath`, which
    # makes the `yarn` binary re-exec a vendored file under `.yarn/releases`
    # with node before it parses a single flag we pass -- `--ignore-scripts`
    # cannot reach code substituted ahead of it. This is correct for both
    # Yarn major versions, so it is set unconditionally rather than only for
    # the yarn branch.
    env = {**os.environ, "YARN_IGNORE_PATH": "1"}

    try:
        # `errors="replace"` because the only reader of this output is the `RuntimeError` below.
        # The child is a `.CMD` shim over node here and measures as UTF-8, but it is whichever
        # manager the customer's lockfile named, run against whichever registry their `.npmrc`
        # names, and a decode failure would not raise where it happened: it lands on a reader
        # thread, `stdout` comes back `None`, and the concatenation below raises `TypeError`
        # instead of reporting the install that failed. A mangled character in a diagnostic
        # costs nothing by comparison.
        result = subprocess.run(
            [executable, *args],
            cwd=repo_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"{manager} install timed out after {timeout}s")
    if result.returncode != 0:
        raise RuntimeError(f"{manager} install failed: {(result.stdout + result.stderr).strip()[-800:]}")
    return True
