"""Pin the symbol map the frozen corpus is scored against.

The corpus has two frozen inputs and pinned one. `repositories.yaml` pins four checkouts by
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


def symbol_map_digest(mapping: Mapping[str, Mapping[str, Any]]) -> str:
    """One string naming what this map resolves, and nothing about how it was written.

    Sorted at both levels and rendered with fixed separators, so the digest is a property of the
    mapping. A map reserialised by another writer digests the same; a map where one symbol points
    somewhere else does not.
    """
    canonical = json.dumps(mapping, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def read_staged_map(path: Path) -> dict[str, dict[str, Any]]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


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


def verify_staged_map(path: Path, pin: Mapping[str, Any]) -> str:
    """The digest of the staged map, or a refusal naming both sides.

    Both halves are checked. The count is redundant against the digest by construction and is
    kept because it is what a human reads in a diff and what a report of a change quotes -- a pin
    whose two halves disagree is a pin somebody edited without re-deriving it.
    """
    path = Path(path)
    if not path.exists():
        raise SymbolMapMismatch(
            f"no symbol map at {path}; the corpus records one at digest {pin['digest'][:12]} and "
            f"{pin['symbols']} symbols, built from {pin.get('built_from', 'an unrecorded source')}"
        )

    staged = read_staged_map(path)
    digest = symbol_map_digest(staged)
    if len(staged) != pin["symbols"]:
        raise SymbolMapMismatch(
            f"{path} holds {len(staged)} symbol(s); the corpus records {pin['symbols']}"
        )
    if digest != pin["digest"]:
        raise SymbolMapMismatch(
            f"{path} is not the symbol map this corpus was scored against: it digests to "
            f"{digest} and {PIN} records {pin['digest']}"
        )
    return digest
