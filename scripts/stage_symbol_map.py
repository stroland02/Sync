"""Rebuild the symbol map the frozen corpus is scored against, and stage it where the scorer looks.

`benchmark/corpus/symbol_map.yaml` pins that map by a digest and records in prose how to rebuild
it: `build_symbol_map` over a Stripe specification staged in `.cache/specs/`, with no SDK
document. Prose is not a step a runner can execute, and the cost was exact -- CI fetched the
corpus, reached `scripts/score_corpus.py`, and was refused with `no symbol map at
.cache/specs/symbols.json`. The binding gate has never run on a runner, and the fetch failure
that came before it hid that for as long as it lasted.

The SDK document is deliberately not read
-----------------------------------------
`_prepare_stripe` passes one when the tag publishes it, and the pin was taken without one. Both
produce 272 symbols and the same digest, which the pin's own note records as measured. Passing
the argument anyway would make this script's output depend on whether a large optional file
happened to be staged, which is the class of thing the pin exists to stop.

Any pinned tag will do, and that is a property rather than a convenience
-----------------------------------------------------------------------
Measured across `v2200`, `v2300`, `v2330` and `v2345`: one digest, 272 symbols. The map is keyed
by SDK symbol and derived from path segments and `x-stableId`, both of which are stable across
these versions. `--spec` defaults to the head the corpus pairs are cut against; a caller naming
another is checked by the same pin, so a version that ever did move the map fails here rather
than scoring quietly.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sync.signals.stripe.symbols import build_symbol_map

# Run as `uv run python scripts/stage_symbol_map.py`, Python puts `scripts/` on the path and not
# the repository root, so the sibling module below is unimportable by the name the tests use.
# The same line for the same reason as in `scripts/score_corpus.py`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.symbol_map_pin import PIN, SymbolMapMismatch, read_pin, symbol_map_digest

SPEC = Path(".cache/specs/v2330.json")


def stage_symbol_map(spec: Path, into: Path, pin: Mapping[str, Any]) -> str:
    """Build the map from `spec` and write it to `into`, or refuse and write nothing.

    The check is before the write, and a refusal leaves whatever was already staged untouched.
    `.cache/` is per-worktree space several workers share, so a rebuild that truncated the file
    on its way to failing would break a run that was scoring correctly.
    """
    mapping = build_symbol_map(json.loads(spec.read_text(encoding="utf-8")), None)
    digest = symbol_map_digest(mapping)
    if digest != pin["digest"]:
        raise SymbolMapMismatch(
            f"{spec} builds a map at digest {digest[:12]} with {len(mapping)} symbols; the "
            f"corpus records {pin['digest'][:12]} with {pin['symbols']}. Re-pinning is a "
            f"deliberate act with a measurement attached -- see {PIN}."
        )

    into.parent.mkdir(parents=True, exist_ok=True)
    into.write_text(json.dumps(mapping), encoding="utf-8")
    return digest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--spec", default=str(SPEC), help="the specification to build from")
    parser.add_argument("--pin", default=str(PIN), help="the pin the built map must match")
    args = parser.parse_args()

    pin = read_pin(Path(args.pin))
    try:
        digest = stage_symbol_map(Path(args.spec), Path(pin["staged_at"]), pin)
    except (OSError, SymbolMapMismatch) as exc:
        print(f"refused: {exc}")
        return 2

    print(f"{pin['staged_at']}  {digest}  {pin['symbols']} symbols")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
