"""Materialise the frozen corpus checkouts, pinned by commit, into a gitignored directory.

`benchmark/corpus/README.md` argues which repositories and why. This is the setup step that
turns that manifest into trees on disk. It runs once; scoring afterwards reaches no network,
which is the offline contract `sync benchmark --score-pair` already keeps.

Pinned by commit, never by branch
---------------------------------
Each entry names a commit and the fetch asks for that commit by name, so a repository whose
default branch moves produces the same bytes here forever. A corpus pinned to a branch scores a
different input set each run, and a movement in the number would mean nothing --
`2026-07-27-sync-benchmark-gates.md` is explicit that this is what separates a benchmark from a
score.

The tree is the tree, and it used to not be
-------------------------------------------
This script once held back every file that did not decode as UTF-8, because `_score_corpus` read
the whole checkout with `read_text(encoding="utf-8")` and one PNG anywhere ended the run. Three
of the four repositories carry images; the Stripe Connect demo carries 63 files that are not
UTF-8. The count was printed rather than hidden, but the corpus was still scoring a tree that was
not the repository the manifest names.

`sync.cli._read_checkout` now skips what it cannot read as source and reports which paths those
were, so the pre-filter here has nothing left to do and is gone. The materialised tree is the
pinned subtree, minus only `.git` and `node_modules`, and the digest below pins what the vendor
published rather than what a filter left behind.

The tree digest is what makes "frozen" checkable
------------------------------------------------
A commit pins what the vendor published; the digest pins what this script produced from it. It
is a SHA-256 over every materialised path and the SHA-256 of its bytes, in sorted order, so two
machines that ran this can compare one string rather than two trees. A digest that does not match
the manifest fails the run, because a corpus that quietly re-materialised differently would move
the score with nothing saying why.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

MANIFEST = Path("benchmark/corpus/repositories.yaml")
ROOT = Path(".cache/corpus")
CHECKOUTS = ROOT / ".checkouts"

# Never materialised, whatever a repository holds. `.git` is the fetch's own bookkeeping and
# `node_modules` is an install rather than source; `_score_corpus` already skips both, and
# carrying them here would mean copying tens of thousands of files to drop them later.
SKIP_DIRECTORIES = frozenset({".git", "node_modules"})


class CorpusMismatch(RuntimeError):
    """A materialised tree is not the one the manifest pins."""


def _git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} in {cwd}: {result.stderr.strip()}")
    return result.stdout.strip()


def fetch_commit(repo: str, commit: str, into: Path) -> None:
    """Put exactly `commit` in `into`, fetching only what that commit needs.

    `git fetch <sha>` rather than a clone of the default branch: the commit is the pin, and a
    clone would succeed against a moved branch and leave the mismatch to be noticed later.
    """
    if (into / ".git").exists() and _git(["rev-parse", "HEAD"], into) == commit:
        return

    into.mkdir(parents=True, exist_ok=True)
    _git(["init", "-q", "."], into)
    if not _git(["remote"], into):
        _git(["remote", "add", "origin", f"https://github.com/{repo}.git"], into)
    _git(["fetch", "--quiet", "--depth", "1", "origin", commit], into)
    _git(["checkout", "-q", "FETCH_HEAD"], into)

    head = _git(["rev-parse", "HEAD"], into)
    if head != commit:
        raise CorpusMismatch(f"{repo}: asked for {commit} and got {head}")


def materialise(source: Path, destination: Path) -> int:
    """Copy `source` into `destination` verbatim, and say how many files that was.

    Bytes throughout, and nothing is decoded. A checkout carrying CRLF stays byte-identical to
    what was fetched, and a PNG stays a PNG -- `sync.cli._read_checkout` is what decides which
    paths are source, so this has no business holding an opinion about it. Two components deciding
    that is one too many, and the one that used to be here is what made the corpus score a tree
    that was not the repository the manifest names.

    Only `.git` and `node_modules` are held back, and neither is a judgement about content:
    `.git` is the fetch's own bookkeeping and `node_modules` is an install. Copying them would
    write tens of thousands of files to be ignored later and put an install inside the digest.
    """
    if destination.exists():
        shutil.rmtree(destination)

    written = 0
    for path in sorted(source.rglob("*")):
        if not path.is_file() or SKIP_DIRECTORIES & set(path.parts):
            continue
        target = destination / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
        written += 1
    return written


def tree_digest(root: Path) -> str:
    """One string naming the whole materialised tree.

    Over paths as well as contents, because two trees differing only in where a file sits are
    different inputs to an indexer that reads `package.json` from the root.
    """
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", default=str(MANIFEST))
    args = parser.parse_args()

    entries = yaml.safe_load(Path(args.manifest).read_text(encoding="utf-8"))
    failures = []

    for entry in entries:
        name, repo, commit = entry["name"], entry["repo"], entry["commit"]
        checkout = CHECKOUTS / name
        fetch_commit(repo, commit, checkout)

        source = checkout / entry.get("subpath", ".")
        destination = ROOT / name
        written = materialise(source, destination)
        digest = tree_digest(destination)

        expected = entry.get("tree_digest")
        state = "unpinned" if expected is None else ("ok" if expected == digest else "MISMATCH")
        if state == "MISMATCH":
            failures.append(f"{name}: manifest pins {expected}, materialised {digest}")

        print(f"{name:<16} {commit[:12]} {written:>4} files  {digest}  {state}")

    for failure in failures:
        print(f"refused: {failure}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
