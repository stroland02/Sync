"""Pin the symbol map the frozen corpus is scored against.

The corpus has two frozen inputs and pinned one. `repositories.yaml` pins every checkout by
commit and validates each against a `tree_digest`, and `fetch_corpus_repositories.py` refuses on
mismatch. The symbol map is the other input, and it was a cached artifact in gitignored space
that nothing recorded, nothing validated, and any `sync run` could overwrite: a different head
specification, or `sdk_spec` present rather than absent, changes what resolves and therefore what
the binder can find at all.

`2026-07-27-sync-benchmark-gates.md` is why that matters rather than being untidy -- an unfrozen
benchmark measures the benchmark. B39 took the map from 179 symbols to 272 and the corpus could
not see the change until the artifact was rebuilt by hand. The failure that matters runs the
other way: a score moves, or fails to move when it should have, with no commit and no digest
mismatch to explain it, and `gate_corpus.py` gates on those numbers.

Over the content, not over the bytes
------------------------------------
`tree_digest` hashes bytes because a checkout *is* its bytes: the indexer reads the files it was
handed, and two trees differing anywhere differ as input. A symbol map is a mapping, and its
meaning is which symbol resolves to which operation by which method and path. Indentation, key
order and separators are how a serialiser felt on the day. A digest over the bytes would move
every time the file was rewritten by a different writer and report a corpus change that is not
one, which is the failure the gate specification names one input over: a check that fires
constantly gets switched off.

So the digest is taken over a canonical rendering of the whole mapping -- every symbol, every key
of every entry, sorted. Every key rather than a hand-picked triple, because a digest over fields
somebody chose goes blind the day the builder emits a fourth.

Recording, not regenerating
---------------------------
Nothing here builds a map. Rebuilding it inside the scorer would trade an unpinned input for an
unpinned *build*: which specification version, whether the SDK document was present, which
release of the builder ran. Those would then vary silently instead, and none of them is visible
in a score. Recording what was used is the weaker-sounding answer and the checkable one.

The map stays out of version control for the reason `.cache/` is gitignored -- it is generated,
it is large, and committing it would make the repository the place a stale copy lives. Pinning it
and committing it are different answers and this is the first.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import yaml

PIN = Path("benchmark/corpus/symbol_map.yaml")
"""Where the corpus records the map it was scored against.

Beside `repositories.yaml`, which pins the other frozen input, and committed for the same reason:
a reader meets it beside the corpus it qualifies, and moving it is a diff somebody has to justify
rather than a cache that changed under them.
"""

_REQUIRED = ("digest", "symbols", "staged_at", "built_from")


class SymbolMapMismatch(RuntimeError):
    """The staged map is not the map this corpus records, or there is none.

    Raised rather than warned. A score taken over the wrong map is a real number over a
    resolution nobody recorded, and it is indistinguishable from a good one by the time it
    reaches `gate_corpus.py` -- which would then compare it against floors it has no relationship
    to and pass or fail for a reason that is not the pipeline's.
    """


class SymbolMapRewritten(SymbolMapMismatch):
    """The staged map changed while it was being verified, so the refusal is about the artifact.

    A subclass rather than a separate exception: this still refuses, and every caller that
    already stops on `SymbolMapMismatch` goes on stopping. A rewrite mid-verification means the
    map a score would have been taken over is not knowable, which is the same reason to refuse as
    a mismatch -- what differs is what the reader should do next. A mismatch says the pin and the
    artifact disagree and one of them has to be brought to the other. This says nothing was
    established: run it again in a quiet tree.

    The distinction exists because these two arrive as the same red and only one of them is a
    finding. `.cache/` is gitignored and `staged_at` is relative, so the artifact is shared with
    every other process in the worktree, and a check that cannot say which of the two it met gets
    silenced -- taking the frozen-input guarantee with it.
    """


def symbol_map_digest(mapping: Mapping[str, Mapping[str, Any]]) -> str:
    """One string naming what this map resolves, and nothing about how it was written.

    Sorted at both levels and rendered with fixed separators, so the digest is a property of the
    mapping. A map reserialised by another writer digests the same; a map where one symbol points
    somewhere else does not.
    """
    canonical = json.dumps(mapping, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def read_pin(path: Path = PIN) -> dict[str, Any]:
    """The recorded pin, refusing a partial one.

    A field missing here would default to something and the pin would check less than it says.
    `read_sdk_repositories` refuses a partial entry for the same reason: evidence that was
    written down incompletely is evidence somebody will read as complete.
    """
    pin = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    missing = [key for key in _REQUIRED if key not in pin]
    if missing:
        raise ValueError(f"{path}: the symbol map pin names no {', '.join(missing)}")
    return pin


def _refusal(path: Path, snapshot: bytes, message: str) -> SymbolMapMismatch:
    """One refusal, classified by whether the artifact is still the bytes that were read.

    Compared by content rather than by timestamp. `CLAUDE.md` is explicit about why: a filesystem
    records modification times far more coarsely than the clock, so a rewrite that lands inside a
    tick leaves `st_mtime_ns` untouched, and a check written that way mostly does not detect. The
    bytes are already in hand, so there is nothing to gain by asking a cheaper question badly.

    The mismatch text is carried through rather than replaced. Whichever of the two this turns out
    to be, the reader still gets the digests and counts that name it -- adding an explanation must
    not cost the explanation that was already there.
    """
    try:
        current: bytes | None = path.read_bytes()
    except OSError:
        current = None

    if current == snapshot:
        return SymbolMapMismatch(message)

    became = "it is gone" if current is None else f"it now holds {len(current)} bytes"
    return SymbolMapRewritten(
        f"{message}\n"
        f"-- and {path} changed while this ran: {len(snapshot)} bytes were read and {became}. "
        f"Nothing was established about the pin. `.cache/` is gitignored and shared with every "
        f"process in this worktree, so another run regenerating the map looks exactly like this; "
        f"re-run against a tree nothing else is working in before treating the pin as wrong."
    )


def verify_staged_map(path: Path, pin: Mapping[str, Any]) -> str:
    """The digest of the staged map, or a refusal naming both sides.

    Both halves are checked. The count is redundant against the digest by construction and is
    kept because it is what a human reads in a diff and what a report of a change quotes -- a pin
    whose two halves disagree is a pin somebody edited without re-deriving it.

    **Verified against one snapshot, read once.** The artifact lives in gitignored per-worktree
    space that any other process can write, so reading it twice can compare two different files
    and refuse over neither: the check this replaced read it once for the digest and again for the
    count. Everything below is decided from `snapshot`, which means a rewrite landing after that
    read cannot manufacture a refusal -- it is simply the next revision of an artifact this call
    has already finished with.

    A rewrite landing *before* it is a different matter, and is what `_refusal` is for. The digest
    is taken before any refusal is raised so that every one of them is classified the same way.
    What none of this can separate is a rewrite that completed before the read and stopped: that
    is indistinguishable from a stale artifact, because it *is* one, and the answer to both is to
    restage from `built_from`.
    """
    path = Path(path)
    try:
        snapshot = path.read_bytes()
    except FileNotFoundError:
        raise SymbolMapMismatch(
            f"no symbol map at {path}; the corpus records one at digest {pin['digest'][:12]} and "
            f"{pin['symbols']} symbols, built from {pin.get('built_from', 'an unrecorded source')}"
        ) from None

    try:
        # Decoded explicitly rather than handing bytes to `json.loads`, which would guess the
        # encoding from a BOM. A `UnicodeDecodeError` is a `ValueError`, so both halves of "this is
        # not a readable symbol map" are caught by the one clause below.
        staged = json.loads(snapshot.decode("utf-8"))
    except ValueError as exc:
        # A bare decode error reaches the scorer as a message naming neither the file nor what to
        # do about it: it catches ValueError, and that is what a JSONDecodeError is.
        raise _refusal(
            path, snapshot,
            f"{path} does not hold a symbol map: {exc}. Half a file is what a write that was "
            f"interrupted or is still running leaves behind, so this is more often a staging "
            f"problem than a different map. The corpus records one at digest {pin['digest'][:12]} "
            f"and {pin['symbols']} symbols, built from "
            f"{pin.get('built_from', 'an unrecorded source')}",
        ) from exc

    digest = symbol_map_digest(staged)
    if len(staged) != pin["symbols"]:
        raise _refusal(
            path, snapshot,
            f"{path} holds {len(staged)} symbol(s); the corpus records {pin['symbols']}",
        )
    if digest != pin["digest"]:
        raise _refusal(
            path, snapshot,
            f"{path} is not the symbol map this corpus was scored against: it digests to "
            f"{digest} and {PIN} records {pin['digest']}",
        )
    return digest
