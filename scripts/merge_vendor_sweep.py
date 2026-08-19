"""Fold a verified vendor sweep into the knowledge base, and stage promotions for review.

Input is the sweep workflow's result (a JSON file: {entries, promotions, dropped}), where every
package name carries probe evidence from the agent that verified it. This script trusts that
gate and does two mechanical things:

- appends each new entry to `vendor-catalog.yaml` in the file's established shape, skipping any
  vendor_id already present -- the file is the authority, a sweep never overwrites it;
- writes `vendor-promotions.yaml`, the staged review file the owner reads before any entry is
  promoted into `generated-vendors.yaml`. Nothing at runtime reads it; promotion stays a human
  decision (owner ruling, 2026-08-18).

Then run `uv run python scripts/build_integration_docs.py` and the catalog tests, which are the
real gate on what this wrote.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG = REPO_ROOT / "vendor-catalog.yaml"
PROMOTIONS = REPO_ROOT / "vendor-promotions.yaml"


def _entry_block(entry: dict) -> str:
    lines = [
        f"- vendor_id: {entry['vendor_id']}",
        f"  display_name: {entry['display_name']}",
        f"  categories: [{', '.join(entry['categories'])}]",
        f"  docs_url: {entry['docs_url']}",
        "  packages:",
    ]
    packages = entry.get("packages") or {}
    for ecosystem in sorted(packages):
        names = packages[ecosystem]
        if not names:
            continue
        rendered = ", ".join(f'"{n}"' if n.startswith("@") or "." in n else n for n in names)
        lines.append(f"    {ecosystem}: [{rendered}]")
    return "\n".join(lines) + "\n"


def main() -> None:
    results = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    existing = {e["vendor_id"] for e in yaml.safe_load(CATALOG.read_text(encoding="utf-8"))}

    added = []
    for entry in results["entries"]:
        if entry["vendor_id"] in existing:
            continue
        if not (entry.get("packages") or {}).get("npm") and not (entry.get("packages") or {}).get("pypi"):
            continue
        added.append(entry)

    if added:
        blocks = "\n".join(_entry_block(e) for e in sorted(added, key=lambda e: e["vendor_id"]))
        header = (
            "\n# --- swept 2026-08-18: every package below was registry-verified by the sweep "
            "workflow ---\n\n"
        )
        CATALOG.write_text(
            CATALOG.read_text(encoding="utf-8").rstrip("\n") + "\n" + header + blocks,
            encoding="utf-8",
        )

    promotions = results.get("promotions", [])
    header = (
        "# Staged promotions, awaiting the owner's review -- nothing at runtime reads this file.\n"
        "#\n"
        "# Each row records a registry-verified generator manifest found in a vendor's official\n"
        "# SDK repository. Promotion means writing the entry into `generated-vendors.yaml` by\n"
        "# hand, after looking: that file's own standard is that every entry was confirmed by\n"
        "# fetching the path, and this staging file carries exactly that evidence.\n"
    )
    PROMOTIONS.write_text(
        header + yaml.safe_dump(promotions, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    print(f"added {len(added)} entries, staged {len(promotions)} promotions")
    for drop in results.get("dropped", []):
        print(f"dropped: {drop['name']} -- {drop['reason']}")


if __name__ == "__main__":
    main()
