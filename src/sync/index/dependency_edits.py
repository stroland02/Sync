"""Catch a patch that edited an installed dependency instead of the source.

`sync.index.shipped_tree` reduces the clone to what a push would carry, and
keeps `node_modules` because the customer's CI installs its own. That exception
is the hole: an agent holding `Bash` and `Edit` can add the property it needs to
a declaration inside the package, the compiler resolves it and is satisfied, and
`git add -u` stages none of it. The branch then carries the source edit alone
and the customer's CI typechecks it against the package their lockfile installs.

Typechecking a second, pristine checkout closes this, and the cost is the
reason it was not: a checkout plus a second dependency install on every
verification, up to three per finding, against an install measured in minutes.
It also re-verifies everything in order to establish one thing -- that the patch
touched a path the branch will not carry -- which is answerable on its own.

**Git cannot answer it.** `git diff` reports tracked modifications, and nothing
under a gitignored `node_modules` is tracked, so a guard reading the patch's
diff would never fire. `git status --ignored` reports the directory, collapsed
to one entry and present on every run whether or not anything inside it was
touched, so a guard reading that would fire every time. Neither distinguishes
"held aside for the compile" from "the agent edited it". The filesystem does:
every file under a dependency directory was written by the install, so one
whose mtime is later than the install is one something else wrote.

That comparison is a stat per file, taken from the directory listing itself, and
it is paid only by a tree that has dependencies installed. It does not read
file contents and it does not run the compiler twice.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Iterator

# Enough for an operator to see the shape of what happened. An agent that ran an
# install rather than making an edit changes every file in the tree, and a
# diagnostic listing them is not one anybody reads.
_REPORTED = 5


def _walkable(repo_path: Path) -> str:
    """The clone's path spelled so Windows will list all of it.

    A dependency's own dependencies nest without bound, and `node_modules` is
    where a clone crosses the 260-character limit that the Win32 path APIs
    apply by default: `resolve`'s committed test fixtures do it on their own,
    and `os.scandir` then raises `FileNotFoundError` on a directory that is
    plainly there. Lifting the limit system-wide is a privilege this project
    cannot assume, the same constraint that rules out symlinks -- the
    extended-length prefix needs none.

    A drive-letter path only. `\\\\?\\` takes a fully-qualified name and a UNC
    share is spelled differently under it; a clone on one is left as it is
    rather than mangled.
    """
    absolute = os.path.abspath(repo_path)
    if os.name != "nt" or absolute.startswith("\\\\"):
        return absolute
    return absolute if absolute.startswith("\\\\?\\") else "\\\\?\\" + absolute


def _dependency_files(root: str, dependency_dirs: frozenset[str]) -> Iterator[os.DirEntry]:
    """Every file inside an installed dependency directory, at any depth.

    Descends the whole clone rather than only its root `node_modules`, because a
    workspace keeps its own beside its package. Nothing outside one is stat'd:
    a source file is tracked, so a modification to it is staged, committed and
    reviewed like any other.

    Symlinks are never followed. pnpm lays out `node_modules` as a tree of links
    into `node_modules/.pnpm`, so the files themselves are reached through that
    directory once rather than through every link that names them.
    """
    stack: list[tuple[str, bool]] = [(root, False)]
    while stack:
        directory, inside = stack.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                if entry.is_dir(follow_symlinks=False):
                    if entry.name == ".git":
                        continue
                    stack.append((entry.path, inside or entry.name in dependency_dirs))
                elif inside:
                    yield entry


def _tracked_dependency_files(repo_path: Path, dependency_dirs: frozenset[str]) -> set[str]:
    """Repository-relative paths under a dependency directory that git tracks.

    A repository that commits its `node_modules` ships an edit inside one the
    same way it ships any other tracked modification, and failing it would be
    wrong. The index is read whole and filtered here rather than through a
    pathspec, so a workspace's nested directory is found as well as the root's.
    """
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return {
        path
        for path in result.stdout.split("\0")
        if path and dependency_dirs.intersection(path.split("/"))
    }


def unshippable_dependency_edits(
    repo_path: Path, dependency_dirs: frozenset[str], installed_at_ns: int
) -> list[str]:
    """Paths under a dependency directory written after `installed_at_ns`.

    The index is consulted only once something has changed, which for an
    ordinary patch is never.
    """
    repo_path = Path(repo_path)
    root = _walkable(repo_path)
    changed = sorted(
        entry.path[len(root) + 1 :].replace(os.sep, "/")
        for entry in _dependency_files(root, dependency_dirs)
        if entry.stat(follow_symlinks=False).st_mtime_ns > installed_at_ns
    )
    if not changed:
        return []
    tracked = _tracked_dependency_files(repo_path, dependency_dirs)
    return [path for path in changed if path not in tracked]


def describe(edits: list[str]) -> str:
    """What the operator reading `abandon_reason` gets, and all they get.

    It has to name a path and say what happens to it, because "verification
    failed" against a compiler that reported nothing is the one message this
    situation cannot be diagnosed from.
    """
    shown = ", ".join(edits[:_REPORTED])
    rest = f" and {len(edits) - _REPORTED} other paths" if len(edits) > _REPORTED else ""
    return (
        f"the patch modified {shown}{rest} inside an installed dependency, which will not be "
        f"committed: `push_branch` stages with `git add -u` and nothing there is tracked. The "
        f"branch would carry the rest of the patch on its own, and the customer's CI would "
        f"typecheck it against the package their lockfile installs -- so this typecheck "
        f"describes no tree anyone will build."
    )
