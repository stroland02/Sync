"""The integrations catalogue: every vendor this deployment can watch, and where each stands.

The reference read's first lesson (`references/notes/nango-integration-architecture.md`): a
catalogue-scale product lists every integration it supports whether or not the reader uses it,
so a reader learns what exists rather than discovering it in documentation. Sync's catalogue is
its adapter registry — coded adapters, the generated tier's YAML, and any watched MCP server —
which means adding an integration is still a configuration entry rather than a code change.

**Three states, and they are three different facts.** `watched` — this codebase calls it and the
index has bound a call site. `staged` — the specification is on disk, so a scan could bind one
today. `available` — registered and neither, which is the ordinary state of an integration a
codebase does not use. Nothing here reports a fourth state for "unsupported": a vendor absent
from the catalogue is absent, and the count of what is registered is the honest denominator.

**No connect button, and that is a product fact rather than a missing feature.** Sync watches an
API by reading its published specification and the customer's own code; it holds no credential
for a vendor and never calls one. What a reader does with this list is index a codebase that
uses one — which is why every row says what it would take rather than offering an OAuth flow
this product does not have.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sync.graph.store import GraphStore
from sync.signals.registry import registered_adapters, _generated_vendors


def _bindings_for(vendor_id: str) -> dict[str, Any]:
    """What a customer would import to reach this vendor, per language, as configured.

    Read from the generated tier's own declaration rather than guessed: a vendor that declared
    nothing yields nothing here, which is the same rule `bindings_for` applies when deciding
    whether a repository depends on a vendor at all.
    """
    entry = _generated_vendors().get(vendor_id)
    if entry is None or not entry.sdk_bindings:
        return {}
    return {
        language: {key: value for key, value in declared.items()}
        for language, declared in entry.sdk_bindings.items()
    }


def _staged(vendor_id: str, cache_dir: Path) -> dict[str, Any] | None:
    """The staged specification's own record, or None when nothing is staged for this vendor."""
    provenance = cache_dir / vendor_id / "provenance.json"
    if not provenance.is_file():
        symbols = cache_dir / vendor_id / "symbols.json"
        return {"tag": None, "symbols": None} if symbols.is_file() else None
    try:
        record = json.loads(provenance.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {"tag": None, "symbols": None}
    return {
        "tag": record.get("tag"),
        "symbols": record.get("symbols"),
        "baked_at": record.get("baked_at"),
    }


def integrations_catalogue(
    store: GraphStore, *, repo_id: str | None = None, cache_dir: str = "vendor-cache"
) -> dict:
    """Every registered integration, with what stands behind it and where it is in use."""
    cache = Path(cache_dir)
    delivered = store.vendor_intake_rollup()
    in_use: dict[str, int] = {}
    if repo_id is not None:
        in_use = store.api_topology(repo_id)["by_vendor"]
        in_use = {row["vendor_id"]: int(row["call_sites"]) for row in in_use}

    rows: list[dict[str, Any]] = []
    for entry in registered_adapters():
        staged = _staged(entry.vendor_id, cache)
        call_sites = in_use.get(entry.vendor_id, 0)
        rows.append(
            {
                "vendor_id": entry.vendor_id,
                "tier": entry.kind,
                "source": entry.source,
                "sdk_bindings": _bindings_for(entry.vendor_id),
                "staged": staged,
                "call_sites": call_sites,
                "changes_recorded": delivered.get(entry.vendor_id, {}).get("changes", 0),
                "state": "watched" if call_sites > 0 else ("staged" if staged else "available"),
            }
        )

    by_tier: dict[str, int] = {}
    by_state: dict[str, int] = {}
    for row in rows:
        by_tier[row["tier"]] = by_tier.get(row["tier"], 0) + 1
        by_state[row["state"]] = by_state.get(row["state"], 0) + 1

    return {
        "repo_id": repo_id,
        "integrations": rows,
        "by_tier": by_tier,
        "by_state": by_state,
        "total": len(rows),
    }
