"""Stands in for `npx` in `tests/test_tsc_npx_race.py`, B101's regression test.

Real `npx --package=typescript@latest` checks whether the package already
exists under the shared, per-user npm cache and, if not, downloads and
extracts it before executing the compiler out of that directory -- and that
check-then-write is exactly where B101's race lives: two callers reaching a
cold cache at once can both see it empty and both act on that, with nothing
between them.

This script reproduces the same shape -- check a shared target, and if it is
missing, write it in two steps with a real pause between them, then read it
-- against a location the test controls (`FAKE_NPX_CACHE_DIR`), never the
real npx cache. The pause is what makes two concurrent callers reliably
interleave instead of only occasionally doing so; see the module docstring in
`test_tsc_npx_race.py` for what was tried against the real `npx` first and
why this substitute exists instead.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path


def main() -> int:
    cache_dir = Path(os.environ["FAKE_NPX_CACHE_DIR"])
    delay = float(os.environ.get("FAKE_NPX_RACE_DELAY_SECONDS", "2.0"))
    target = cache_dir / "typescript-latest.marker"

    if not target.exists():
        # Non-atomic and deliberately slow, the same shape a real package
        # extraction takes: the destination exists before it is usable.
        target.write_text("PARTIAL", encoding="utf-8")
        time.sleep(delay)
        target.write_text("READY", encoding="utf-8")

    content = target.read_text(encoding="utf-8")
    if content != "READY":
        sys.stderr.write(
            f"npm error code EBUSY: resource busy or locked, open '{target}'\n"
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
