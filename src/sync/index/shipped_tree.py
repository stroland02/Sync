"""Reduce a clone to the content a push would carry, for the duration of a block.

The static gate exists to reject a patch before it costs a CI run, and that only
means something if the tree it measures is the tree that ships. `push_branch`
commits `git add -u` -- the index, plus tracked modifications -- so every
untracked and every ignored path in the clone is content the branch will not
have. The patch agent holds `Bash` and `Write` and is told to run `npx tsc
--noEmit` until it is clean, which it can do by creating exactly such a file.
That is not hypothetical: the M0 acceptance run passed its typecheck against a
`next-env.d.ts` the agent had generated, gitignored, and left untracked, and
the customer's CI then failed with the fifteen TS2307 errors a clean checkout
produces.

Moving those paths aside was chosen over the two alternatives:

- *Typecheck a second, pristine checkout.* Identical in what it measures, and
  it also catches an agent editing declarations inside `node_modules`, which
  this does not. It costs a checkout and a second dependency install on every
  verification -- up to three per finding, against an install measured in
  minutes -- which the latency specification treats as the pipeline's largest
  avoidable cost. Sharing one `node_modules` between the two trees would need a
  junction or a symlink, and symlink creation on the primary development
  machine needs privileges the project already cannot assume (see the corepack
  note in CLAUDE.md).
- *Fail the gate on finding untracked files the typecheck depends on.* "Depends
  on" is the hard part, and the diagnostic it can produce names Sync's own
  bookkeeping rather than the code. Measuring the shipped tree instead yields
  the compiler's real complaint, which is what the retry prompt needs.

`keep` is the exception this cannot avoid: the customer's CI installs
dependencies, so a typecheck run without them describes neither tree.
Everything under a kept directory stays, which is the hole the pristine
checkout would have closed.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

# git's porcelain v1 status codes for content no commit from this index carries.
_UNSHIPPED = frozenset({"??", "!!"})


def _status_entries(repo_path: Path) -> Iterator[tuple[str, str]]:
    """`(code, path)` for every entry `git status` reports.

    `--ignored` without `-uall` collapses whole ignored and untracked
    directories to a single entry, which is what makes this affordable on a
    tree holding an installed `node_modules`: git answers from the directory's
    ignore match without descending into its hundred thousand files.
    """
    result = subprocess.run(
        ["git", "status", "--porcelain", "--ignored", "-z"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    fields = result.stdout.split("\0")
    index = 0
    while index < len(fields):
        entry = fields[index]
        index += 1
        if not entry:
            continue
        code, path = entry[:2], entry[3:]
        # A rename or a copy is reported as two NUL-separated fields, the second
        # holding the original path. Consuming it here stops a path being read
        # as the next entry's status code.
        if "R" in code or "C" in code:
            index += 1
        yield code, path


def unshipped_paths(repo_path: Path, keep: frozenset[str] = frozenset()) -> list[str]:
    """Repository-relative paths present on disk that a push would not carry.

    Directory entries arrive from git with a trailing slash; `keep` names are
    compared without one so a caller writes `node_modules`, not `node_modules/`.
    """
    return [
        path
        for code, path in _status_entries(Path(repo_path))
        if code in _UNSHIPPED and path.rstrip("/") not in keep
    ]


@contextmanager
def shipped_tree(repo_path: Path, keep: frozenset[str] = frozenset()) -> Iterator[None]:
    """Hold `repo_path` at the content a push would carry, then put it back.

    Restoration is unconditional, because the clone is where the next patch
    attempt runs: an agent that cannot see its own previous work rewrites it.
    A failure to restore raises rather than being swallowed -- a half-restored
    clone is an environment fault, and the graph routes those to `abandon`
    instead of spending the retry budget against them.
    """
    repo_path = Path(repo_path)
    unshipped = unshipped_paths(repo_path, keep)
    if not unshipped:
        yield
        return

    # A sibling of the clone rather than a directory inside it: a tsconfig whose
    # `include` is a bare `**/*` glob would otherwise typecheck the very files
    # being held out of the way. Sibling also keeps the move on one volume,
    # which is what makes `Path.rename` sufficient.
    holding = Path(tempfile.mkdtemp(dir=repo_path.parent, prefix=".sync-unshipped-"))
    moved: list[tuple[Path, Path]] = []
    try:
        for relative in unshipped:
            source, destination = repo_path / relative, holding / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            source.rename(destination)
            moved.append((source, destination))
        yield
    finally:
        for source, destination in reversed(moved):
            source.parent.mkdir(parents=True, exist_ok=True)
            destination.rename(source)
        shutil.rmtree(holding, ignore_errors=True)
