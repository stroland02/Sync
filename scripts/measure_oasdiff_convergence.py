"""How many oasdiff runs before the union of what it finds stops growing.

`docs/superpowers/reports/2026-07-29-oasdiff-determinism.md` established that oasdiff returns a
different answer on every run over the same hash-verified bytes, that the difference reaches
`vendor_change` rows, and that the operation-level row sets are *nested* -- a run truncates its
walk early and loses findings rather than inventing them. That nesting is what makes a union over
repeated runs a coherent mitigation, and it named the one thing missing before that mitigation
could ship: the curve. How many runs before the union stops growing.

This measures it, at two levels, because they are different questions and only one of them was
answered before:

- **The natural key** -- `(vendor_id, from, to, kind, path_ptr, operation_id, raw["text"])`, which
  is what `GraphStore.upsert_vendor_change` hashes. This is the set of rows a run would actually
  write, and its union is what option (1) would have to converge for the *rows* to be stable.
- **The operation level** -- `(kind, path, operationId)`, dropping the free-text message. This is
  the set the determinism report measured as nested, and its union converging is what makes the
  *coverage* stable even if the row text does not.

Two runs may agree by chance and a single pair proves nothing either way, which is why this
accumulates rather than compares. What it prints is the curve: after each run, how large the union
is and how many rows that run contributed that no previous run had.

The number of runs is an argument and not a constant on purpose. Picking N and then justifying it
is the thing `2026-07-27-sync-benchmark-gates.md` forbids; the curve is what a defensible N would
have to be read off, and a curve that never flattens is a real answer that kills the mitigation
rather than embarrassing it.

    uv run python scripts/measure_oasdiff_convergence.py --runs 20

Inputs come from `scripts/fetch_measurement_inputs.py` and are verified by blob hash before use.
Nothing here fetches anything.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

CACHE = Path(".cache/specs")
BINARY = Path("tools/oasdiff.exe")

# The pair the determinism and depth reports both measured, with the blob hashes
# `scripts/fetch_measurement_inputs.py` pins. Verified rather than assumed: a curve measured over
# the wrong bytes is a curve about nothing.
BASE = ("v2320.json", "c5d6078dd0b1392623a0d0c7a579f828ccb3a1f3")
REVISION = ("v2330.json", "634a4b329a8e6f0d1dd13373d9f92458d0e6ee6d")


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def verified(name: str, expected: str) -> Path:
    path = CACHE / name
    if not path.exists():
        sys.exit(f"{path} is missing; run scripts/fetch_measurement_inputs.py first")
    found = git_blob_sha(path.read_bytes())
    if found != expected:
        sys.exit(f"{path} is blob {found}, expected {expected}")
    return path


def run_once(base: Path, revision: Path) -> tuple[list[dict], float]:
    """One `oasdiff breaking`, exactly as `run_oasdiff_breaking` invokes it.

    `encoding="utf-8"` is not decoration: without it a decode error on this boundary is raised on
    the reader thread, never propagates, and returns `stdout` as `None` -- so the failure would
    arrive as a `TypeError` somewhere unrelated rather than here.
    """
    started = time.monotonic()
    result = subprocess.run(
        [str(BINARY), "breaking", str(base), str(revision), "--format", "json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    elapsed = time.monotonic() - started
    if result.returncode != 0:
        sys.exit(f"oasdiff failed ({result.returncode}): {result.stderr.strip()[:400]}")
    return json.loads(result.stdout), elapsed


def natural_keys(records: list[dict]) -> set[tuple[str, ...]]:
    """What `upsert_vendor_change` would hash, minus the three constant fields."""
    return {
        (r.get("id", ""), r.get("path", ""), _operation_id(r), r.get("text", ""))
        for r in records
    }


def operation_keys(records: list[dict]) -> set[tuple[str, ...]]:
    """The same rows with the free-text message dropped."""
    return {(r.get("id", ""), r.get("path", ""), _operation_id(r)) for r in records}


def _operation_id(record: dict) -> str:
    return record.get("operationId") or (
        f"{record.get('operation', '')} {record.get('path', '')}".strip()
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--out", type=Path, default=None, help="write the curve as JSON")
    args = parser.parse_args()

    base = verified(*BASE)
    revision = verified(*REVISION)
    if not BINARY.exists():
        sys.exit(f"{BINARY} is missing")

    version = subprocess.run(
        [str(BINARY), "--version"], capture_output=True, text=True, encoding="utf-8"
    ).stdout.strip()
    print(f"{version}\n{base} -> {revision}\n")

    key_union: set[tuple[str, ...]] = set()
    op_union: set[tuple[str, ...]] = set()
    curve = []

    header = (
        f"{'run':>4} {'records':>9} {'rows':>9} {'union':>10} {'new':>9} "
        f"{'ops':>6} {'op union':>9} {'op new':>7} {'nested?':>8} {'secs':>6}"
    )
    print(header)
    print("-" * len(header))

    for index in range(1, args.runs + 1):
        records, elapsed = run_once(base, revision)
        keys = natural_keys(records)
        ops = operation_keys(records)

        new_keys = len(keys - key_union)
        new_ops = len(ops - op_union)
        # The claim option (1) rests on. A run that contributes an operation-level row no larger
        # run found would mean the sets are not nested, and the union would be accumulating noise
        # rather than converging on a fixed answer.
        nested = ops <= op_union or op_union <= ops if op_union else True

        key_union |= keys
        op_union |= ops
        curve.append(
            {
                "run": index,
                "records": len(records),
                "rows": len(keys),
                "key_union": len(key_union),
                "new_keys": new_keys,
                "ops": len(ops),
                "op_union": len(op_union),
                "new_ops": new_ops,
                "nested": nested,
                "seconds": round(elapsed, 1),
            }
        )
        print(
            f"{index:>4} {len(records):>9,} {len(keys):>9,} {len(key_union):>10,} {new_keys:>9,} "
            f"{len(ops):>6,} {len(op_union):>9,} {new_ops:>7,} {str(nested):>8} {elapsed:>6.1f}"
        )
        sys.stdout.flush()

    total = sum(entry["seconds"] for entry in curve)
    print(
        f"\n{args.runs} runs in {total:.0f}s ({total / args.runs:.1f}s mean). "
        f"natural-key union {len(key_union):,}; operation-level union {len(op_union):,}. "
        f"nesting held on every run: {all(entry['nested'] for entry in curve)}"
    )
    if args.out:
        args.out.write_text(
            json.dumps({"version": version, "curve": curve}, indent=1), encoding="utf-8"
        )
        print(f"curve written to {args.out}")


if __name__ == "__main__":
    main()
