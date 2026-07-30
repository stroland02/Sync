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

- *Typecheck a second, pristine checkout.* Identical in what it measures. It
  costs a checkout and a second dependency install on every verification -- up
  to three per finding, against an install measured in minutes -- which the
  latency specification treats as the pipeline's largest avoidable cost.
  Sharing one `node_modules` between the two trees would need a junction or a
  symlink, and symlink creation on the primary development machine needs
  privileges the project already cannot assume (see the corepack note in
  CLAUDE.md). The one thing it caught that this does not -- an agent editing a
  declaration inside `node_modules` -- turned out to be answerable without a
  compiler at all; `sync.index.dependency_edits` is that answer.
- *Fail the gate on finding untracked files the typecheck depends on.* "Depends
  on" is the hard part, and the diagnostic it can produce names Sync's own
  bookkeeping rather than the code. Measuring the shipped tree instead yields
  the compiler's real complaint, which is what the retry prompt needs.

`keep` is the exception this cannot avoid: the customer's CI installs
dependencies, so a typecheck run without them describes neither tree.
Everything under a kept directory stays, which is why `static_verify` asks
`sync.index.dependency_edits` whether anything under one was written after the
install before it compiles at all.

## When the block writes to a path this held aside

The gate runs a compiler, and a compiler produces build output that is
gitignored for the same reason it is held aside. `tsc --noEmit` writes
`tsconfig.tsbuildinfo` for an `incremental` project, so the measurement
regenerates a file the measurement had just moved out of the way. The M0
acceptance run abandoned a finding on the `FileExistsError` that follows,
naming a build artifact rather than anything about the patch.

**The held copy wins and the regenerated one is deleted.** The held copy is the
clone as the patch agent left it; the new one is a byproduct of a verification
whose whole result is a `VerifyResult` and which is about to be discarded. The
next patch attempt and every later finding in the run work in this clone, so
the state they inherit has to be the state that was there, not one the gate
wrote. Keeping the byproduct instead would also feed a later `tsc` an
incremental record describing a tree that only existed inside this block.

Restoring is therefore total in a second sense: one path that refuses to move
back does not abandon the rest. A clone missing half the agent's work poisons
every later finding, which is the larger fault -- so every held path is
attempted, the failures are collected, and the holding directory is left in
place when there are any, because after a failed restore the copies in it are
the only ones left.

One thing this does not do: a byproduct at a path that held nothing stays.
Reverting those as well would mean deleting paths this module never moved, on
the strength of a second `git status`. They are ignored by construction, so
they can reach no commit, and the next block holds them aside before the
compiler runs -- which is also why an incremental record never survives to be
read.
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
    # `-z` turns off git's octal quoting, so a path arrives as raw bytes. On Windows those come
    # from NTFS, which stores names as UTF-16 and which git converts to UTF-8, so the child
    # cannot put a byte here that `encoding="utf-8"` would fail on -- measured against a
    # repository holding an accented filename. `errors=` must not be the route: a path is data,
    # and a replacement character in one silently moves a file between shipped and unshipped.
    result = subprocess.run(  # subprocess-encoding: allow - git emits utf-8 paths; output is data
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


def _clear(path: Path) -> None:
    """Remove whatever the block left standing where a held copy has to return.

    `Path.rename` refuses on Windows and replaces silently on POSIX, so without
    this the same collision is an abandoned finding on one platform and quiet
    data loss on the other.
    """
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.is_symlink() or path.exists():
        path.unlink()


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
            original, held = repo_path / relative, holding / relative
            held.parent.mkdir(parents=True, exist_ok=True)
            original.rename(held)
            moved.append((original, held))
        yield
    finally:
        failures: list[str] = []
        for original, held in reversed(moved):
            try:
                original.parent.mkdir(parents=True, exist_ok=True)
                _clear(original)
                held.rename(original)
            except OSError as exc:
                failures.append(f"{original.relative_to(repo_path)} ({exc})")
        if failures:
            # Raised from `finally`, so this displaces whatever the block was
            # failing with. That ordering is deliberate: the block's failure
            # concerns one finding, while a clone left in a state nobody
            # described concerns every finding that runs after it. The original
            # is still on `__context__` for anyone reading the traceback.
            raise RuntimeError(
                f"could not restore {', '.join(failures)} into {repo_path}; "
                f"the only copies are in {holding}"
            )
        shutil.rmtree(holding, ignore_errors=True)
