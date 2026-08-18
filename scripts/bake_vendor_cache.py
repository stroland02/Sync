"""Bake a vendor's symbol map into the repository, so a first run resolves it offline.

Beta item 2. `sync index --repo` shipped and running it proved the gap exactly: a plain checkout
indexes to **0 call sites**, because no vendor cache is staged and the only path to one --
`prepare_vendor` -- shells out to `gh` and reaches the network. A first-run user has neither.

**Why the artifact is committed rather than fetched at image build.** `_load_stripe` reads
`<cache_dir>/symbols.json` and nothing else; measured directly rather than assumed, a directory
holding only the map loads. The pinned map is 272 symbols and one digest across four tags, so it
is small and stable. Committing it makes the *build* offline as well as the runtime, and no step
of the install path then needs a network or a token -- which is what "works on first run without
a network or a credential" actually requires.

**The snapshot ages, and that is stated rather than discovered.** `provenance.json` records the
tag, the digest, the symbol count and the instant it was baked. A cache with no provenance is a
claim about a vendor with no date on it, and a reader would have no way to tell whether a finding
reflects today's Stripe. The maintenance cost the owner accepted when choosing this route lives
there too, with a name rather than as folklore.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.symbol_map_pin import symbol_map_digest
from sync.signals.stripe.symbols import build_symbol_map

PROVENANCE = "provenance.json"
DEFAULT_INTO = Path("vendor-cache")


def read_provenance(vendor_dir: Path) -> dict[str, Any]:
    """What this cache holds and when it was taken."""
    return json.loads((vendor_dir / PROVENANCE).read_text(encoding="utf-8"))


def bake(
    spec: Mapping[str, Any],
    *,
    into: Path,
    vendor_id: str,
    tag: str,
    expect_digest: str | None,
) -> str:
    """Write `vendor_id`'s symbol map under `into`, or refuse and write nothing.

    The digest check happens before any write, so a refusal leaves whatever was already baked
    untouched -- the same argument `stage_symbol_map` makes about a shared cache, and it matters
    more here because the artifact is committed and a half-written one would be a bad commit
    rather than a bad run.

    `expect_digest=None` bakes whatever the specification yields, which is what taking a *new*
    pin looks like. Passing the pin is what every routine rebuild does.
    """
    mapping = build_symbol_map(dict(spec), None)
    digest = symbol_map_digest(mapping)
    if expect_digest is not None and digest != expect_digest:
        raise ValueError(
            f"{vendor_id} at {tag} builds a map at digest {digest[:12]} with {len(mapping)} "
            f"symbols; the pin records {expect_digest[:12]}. Re-pinning is a deliberate act with "
            f"a measurement attached, not a side effect of a rebuild."
        )

    vendor_dir = into / vendor_id
    vendor_dir.mkdir(parents=True, exist_ok=True)
    (vendor_dir / "symbols.json").write_text(json.dumps(mapping), encoding="utf-8")
    (vendor_dir / PROVENANCE).write_text(
        json.dumps(
            {
                "vendor_id": vendor_id,
                "tag": tag,
                "digest": digest,
                "symbols": len(mapping),
                "baked_at": datetime.now(timezone.utc).isoformat(),
                "note": (
                    "Baked from the vendor's specification at the tag above. This snapshot ages: "
                    "a finding derived from it reflects the vendor as of that tag, not today. "
                    "Re-baking is a maintained task, not an automatic one."
                ),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return digest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--spec", required=True, help="path to the vendor specification JSON")
    parser.add_argument("--vendor", default="stripe")
    parser.add_argument("--tag", required=True, help="the vendor tag the specification came from")
    parser.add_argument("--into", default=str(DEFAULT_INTO))
    parser.add_argument(
        "--expect-digest", default=None,
        help="refuse unless the built map matches this digest; omit only when taking a new pin",
    )
    args = parser.parse_args()

    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    try:
        digest = bake(
            spec,
            into=Path(args.into),
            vendor_id=args.vendor,
            tag=args.tag,
            expect_digest=args.expect_digest,
        )
    except (OSError, ValueError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2

    print(f"baked {args.vendor} at {args.tag} into {args.into}/{args.vendor} (digest {digest[:12]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
