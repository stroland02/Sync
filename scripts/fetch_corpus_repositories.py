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

Why the tree is pruned, and what that costs
-------------------------------------------
`sync.cli._score_corpus` reads every file under the checkout with `read_text(encoding="utf-8")`,
so one PNG anywhere in the tree ends the run. Three of the four repositories carry images; the
Stripe Connect demo carries 63 files that are not UTF-8. So the materialised tree holds only the
files that decode as UTF-8, and the count of what was dropped is printed rather than hidden.

Nothing an indexer reads is lost by that: `package.json`, `tsconfig.json` and every `.ts` file
are text. It is still a transformation of the vendor's tree and it is recorded as one -- the
alternative was to edit `_score_corpus`, which another task owns.

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


def materialise(source: Path, destination: Path) -> tuple[int, int]:
    """Copy the text of `source` into `destination`, and say how much was dropped.

    Returns (files written, files dropped). A file is dropped only because it does not decode as
    UTF-8, which is the one thing `_score_corpus` cannot read.
    """
    if destination.exists():
        shutil.rmtree(destination)

    written = dropped = 0
    for path in sorted(source.rglob("*")):
        if not path.is_file() or SKIP_DIRECTORIES & set(path.parts):
            continue
        try:
            text = path.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            dropped += 1
            continue
        target = destination / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Bytes rather than text, so a checkout carrying CRLF stays byte-identical to what was
        # fetched. Writing through `write_text` would rewrite line endings on this platform and
        # move the tree digest without any file having changed.
        target.write_bytes(text.encode("utf-8"))
        written += 1
    return written, dropped


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
        written, dropped = materialise(source, destination)
        digest = tree_digest(destination)

        expected = entry.get("tree_digest")
        state = "unpinned" if expected is None else ("ok" if expected == digest else "MISMATCH")
        if state == "MISMATCH":
            failures.append(f"{name}: manifest pins {expected}, materialised {digest}")

        print(f"{name:<16} {commit[:12]} {written:>4} files, {dropped:>3} dropped "
              f"({'not utf-8' if dropped else 'all text'})  {digest}  {state}")

    for failure in failures:
        print(f"refused: {failure}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
