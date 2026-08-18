"""Adapter staging as a declared schema, so one renderer draws every vendor's form (B195).

The catalog lesson from the 2026-08-18 reference read: per-vendor configuration scales when
the adapter declares *what it needs* as typed fields and nothing anywhere hand-writes a form
for one vendor. Twilio's product manifest is the first such field -- which specification files
this deployment reads -- and the closing evidence for B195 is that the console edits it with
no Twilio-specific component.

What a field declaration carries is rendering knowledge, not API knowledge: a title, a
description, a shape. The vendor's URL conventions and operation schemes stay in its adapter,
where the plugin boundary keeps them.

Writes go through `write_staging` and only to fields declared writable. A write that changes
what the baked symbols were built from does not silently rebake -- rebaking reaches the
network -- so the answer carries `stale_symbols` naming what the bake covered, and the reader
is told rather than left to discover the mismatch.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

TWILIO_PRODUCTS_FILENAME = "twilio-products.json"

# One schema per vendor that has configurable staging. A vendor absent here has none, which
# the API reports as an empty schema rather than an error -- Stripe is fully baked and that is
# an answer, not a gap.
_SCHEMAS: dict[str, list[dict[str, Any]]] = {
    "twilio": [
        {
            "key": "products",
            "title": "Products",
            "description": (
                "Which of Twilio's per-product specifications this deployment reads. Each row "
                "names a file in the vendor's twilio-oai repository and the domain/version the "
                "symbol map roots its entries at. Changing this list changes what the next "
                "bake covers -- it does not rebake by itself."
            ),
            "type": "table",
            "writable": True,
            "columns": [
                {"key": "filename", "title": "Spec file", "example": "twilio_messaging_v1.json"},
                {"key": "domain", "title": "Domain", "example": "messaging"},
                {"key": "version", "title": "Version", "example": "v1"},
            ],
        }
    ],
}


def staging_schema(vendor_id: str) -> list[dict[str, Any]]:
    """The declared staging fields for one vendor. Empty is an answer: nothing to configure."""
    return _SCHEMAS.get(vendor_id, [])


def read_staging(vendor_id: str, cache_dir: Path) -> dict[str, Any]:
    """The current values behind each declared field, read from the staged cache."""
    values: dict[str, Any] = {}
    if vendor_id == "twilio":
        manifest = cache_dir / "twilio" / TWILIO_PRODUCTS_FILENAME
        if manifest.is_file():
            values["products"] = json.loads(manifest.read_text(encoding="utf-8"))
        else:
            values["products"] = []
    return values


def _validated_rows(field: dict[str, Any], value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise ValueError(f"{field['key']} must be a list of rows")
    columns = [column["key"] for column in field["columns"]]
    rows: list[dict[str, str]] = []
    for entry in value:
        if not isinstance(entry, dict):
            raise ValueError(f"every {field['key']} row must be an object")
        row: dict[str, str] = {}
        for column in columns:
            cell = entry.get(column)
            if not isinstance(cell, str) or not cell.strip():
                raise ValueError(f"every {field['key']} row needs a non-empty '{column}'")
            row[column] = cell.strip()
        rows.append(row)
    return rows


def write_staging(vendor_id: str, cache_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Write the writable fields the payload names, validated against the declared schema.

    Returns the fresh values plus `stale_symbols`: when the write changes what the baked
    symbol map was built from, the reader is told which products the bake covered instead of
    discovering the mismatch at the next index.
    """
    schema = {field["key"]: field for field in staging_schema(vendor_id)}
    stale: str | None = None

    for key, value in payload.items():
        field = schema.get(key)
        if field is None:
            raise ValueError(f"'{key}' is not a staging field {vendor_id} declares")
        if not field.get("writable"):
            raise ValueError(f"'{key}' is not writable")

        if vendor_id == "twilio" and key == "products":
            rows = _validated_rows(field, value)
            vendor_dir = cache_dir / "twilio"
            vendor_dir.mkdir(parents=True, exist_ok=True)
            (vendor_dir / TWILIO_PRODUCTS_FILENAME).write_text(
                json.dumps(rows, indent=2) + "\n", encoding="utf-8"
            )
            provenance_path = vendor_dir / "provenance.json"
            if provenance_path.is_file():
                baked = json.loads(provenance_path.read_text(encoding="utf-8")).get("products", [])
                if sorted(baked) != sorted(row["filename"] for row in rows):
                    stale = (
                        "the staged symbol map was baked from "
                        + ", ".join(baked)
                        + " — re-bake to match this product list"
                    )

    values = read_staging(vendor_id, cache_dir)
    return {"values": values, "stale_symbols": stale}
