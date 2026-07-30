"""What a repository checkout is, for everything that reads one.

Two components walk a corpus checkout: `scripts/fetch_corpus_repositories.py` materialises the
pinned subtree, and `sync.cli._score_corpus` reads it into the mapping the indexer runs over. They
have to agree on which paths are part of the repository, and they used to agree by both being
written correctly rather than by sharing anything. That is the arrangement where a divergence is
silent: the tree digest would go on pinning one set of files while the score was taken over a
different one, and nothing in either component would notice.

So the walk lives here and both import it. It is stdlib only and imports nothing from `sync`, so
a setup script that reaches the network and a scorer that reaches Postgres can both hold it
without acquiring each other's dependencies.

Two separate questions, deliberately not one
--------------------------------------------
**Is this path part of the tree.** `.git` is the fetch's own bookkeeping and `node_modules` is an
install rather than source; neither is a judgement about a file's contents, and both are excluded
from the digest as well as from the score. Indexing an install would attribute the vendor's own
SDK to the customer who installed it.

**Is this path source.** Answered by whether it decodes, and answered only by the reader --
`read_checkout` skips what it cannot decode and names it. The fetcher deliberately does not ask:
it copies bytes, so the digest pins what the vendor published rather than what a filter left
behind.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

NOT_PART_OF_THE_TREE = frozenset({".git", "node_modules"})
"""Directory names no corpus checkout carries into either the digest or the score."""


def tree_files(root: Path) -> Iterator[Path]:
    """Every file under `root` that belongs to the repository, in sorted order.

    Sorted, because the tree digest is over this sequence and the score's source mapping is built
    from it: two machines that walked the same checkout have to produce the same string and the
    same insertion order, and a filesystem's own enumeration is not a promise.
    """
    # Keyed on the posix string, never on Path objects: Path comparison is case-insensitive
    # on Windows, so two platforms walk the same checkout in different orders wherever a
    # case-mixed pair exists -- and the digest and the score's insertion order both ride on
    # this sequence. Codepoint order is the one both platforms can agree on.
    for path in sorted(root.rglob("*"), key=lambda p: p.relative_to(root).as_posix()):
        if path.is_file() and not NOT_PART_OF_THE_TREE & set(path.parts):
            yield path


def read_checkout(root: Path) -> tuple[dict[str, str], list[str]]:
    """Every file the pipeline can read as source, and the paths of those it cannot.

    A repository with one PNG in it used to be unscoreable: the caller read every file with
    `read_text(encoding="utf-8")` and a single undecodable byte ended the run before a call site
    was indexed. That is a coverage limit rather than an inconvenience -- an image, a font, a
    compiled asset or a `.ico` describes most repositories, and the frozen corpus is four of them
    partly for this reason.

    Skipped rather than decoded leniently. `errors="replace"` would hand the indexer a file full
    of replacement characters, which is still a file it will parse, and whatever tree-sitter makes
    of a mangled PNG can only be phantom call sites. Nothing downstream of this mapping wants a
    binary's bytes, so the honest answer is that the file is not source.

    Still `read_text` rather than `read_bytes().decode`, because the two differ on newlines:
    `read_text` translates CRLF, and this mapping is what call site positions and content hashes
    are computed from. Decoding by hand would move the corpus score for a reason that has nothing
    to do with binaries.

    **The skipped paths are returned, not just counted, and they are not all binaries.** A source
    file in a legacy encoding -- cp1252 is this platform's default and the reason `CLAUDE.md`
    demands an explicit encoding everywhere -- raises the same `UnicodeDecodeError` a PNG does,
    and skipping it loses real call sites. Telling the two apart cheaply is not possible: any byte
    sequence valid in cp1252 is valid in cp1252, so a guess would be a guess. Naming the paths is
    the mitigation, and it is a real one for the case that matters -- a reader who sees
    `src/legacy.ts` in the list knows to look, where a reader handed only a count could not.
    """
    sources: dict[str, str] = {}
    skipped: list[str] = []
    for path in tree_files(root):
        relative = path.relative_to(root).as_posix()
        try:
            sources[relative] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            skipped.append(relative)
    return sources, skipped
