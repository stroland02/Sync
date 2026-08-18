"""Hold an adopted database to the shipped schema, and touch nothing else.

The embedded cluster outlives any checkout, so a clone that pulled today's `main` can adopt a
database created before today's tables existed. Seeding is the wrong fix for that -- an adopted
database's rows are somebody's data, and the doorbell has just promised to keep them -- so this
is the schema-only half of `seed_console.py`: `GraphStore.apply_schema` converges tables and
constraints (`CREATE TABLE IF NOT EXISTS` throughout, per its own docstring) and writes no rows.

The doorbell runs this on every no-admin adoption, the same way it holds the cluster to the
shipped settings: idempotently, saying what it decided.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Standalone execution -- `python scripts/apply_schema.py`, the way the doorbell calls it --
# does not put the repo root on sys.path the way pytest's pythonpath does, and the shared
# DSN guard lives in a sibling script rather than being copied here.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.seed_console import _require_dev_dsn  # noqa: E402
from sync.graph.store import DEFAULT_DSN, GraphStore  # noqa: E402


def converge(dsn: str) -> str:
    store = GraphStore(dsn=dsn)
    missing = store.missing_tables()
    store.apply_schema()
    if missing:
        return f"Added {len(missing)} missing table(s): {', '.join(missing)}. Rows were not touched."
    return "The schema is already current. Nothing was changed."


def main() -> None:
    dsn = os.environ.get("SYNC_GRAPH_DSN", DEFAULT_DSN)
    _require_dev_dsn(dsn, "SYNC_GRAPH_DSN")
    print(converge(dsn))


if __name__ == "__main__":
    main()
