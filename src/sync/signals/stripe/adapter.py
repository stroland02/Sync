"""Stripe implementation of the VendorAdapter protocol."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Iterable

from sync.core import OperationRef, VendorChange
from sync.signals.oasdiff import run_oasdiff_breaking, to_vendor_changes

SPEC_REPO = "stripe/openapi"
SPEC_PATH_IN_REPO = "openapi/spec3.json"


def fetch_spec(tag: str, dest: Path) -> Path:
    """Download `openapi/spec3.json` at a given tag of stripe/openapi.

    Tags are sequential (`v2345`). Uses the authenticated `gh` CLI so it works
    without a separate token. Requests the raw file bytes via the
    `application/vnd.github.raw` Accept header rather than the default JSON
    envelope: spec3.json is larger than the 1 MB limit GitHub enforces on the
    base64-encoded `.content` field, so the envelope form fails outright for
    this file. Bytes are written unchanged — no `text=True` round trip — so a
    Windows console's non-UTF-8 default encoding can't corrupt the spec's
    non-ASCII characters. Called only by the end-to-end test and the CLI —
    never by a unit test.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            "gh", "api", f"repos/{SPEC_REPO}/contents/{SPEC_PATH_IN_REPO}?ref={tag}",
            "--header", "Accept: application/vnd.github.raw",
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"failed to fetch stripe spec at {tag}: {result.stderr.decode(errors='replace').strip()}")
    dest.write_bytes(result.stdout)
    return dest


class StripeAdapter:
    """Turns two pinned Stripe specification versions into VendorChange rows."""

    vendor_id = "stripe"

    def __init__(self, spec_dir: Path, symbol_map_path: Path) -> None:
        self._spec_dir = Path(spec_dir)
        self._symbols: dict[str, dict[str, str]] = json.loads(Path(symbol_map_path).read_text(encoding="utf-8"))

    def fetch_changes(self, from_version: str, to_version: str) -> Iterable[VendorChange]:
        base = self._spec_dir / f"{from_version}.json"
        revision = self._spec_dir / f"{to_version}.json"
        for path in (base, revision):
            if not path.exists():
                raise FileNotFoundError(f"specification not found: {path}")
        records = run_oasdiff_breaking(base, revision)
        return to_vendor_changes(records, self.vendor_id, from_version, to_version)

    def operation_for_symbol(self, symbol: str) -> OperationRef | None:
        entry = self._symbols.get(symbol)
        if entry is None:
            return None
        return OperationRef(
            operation_id=entry["operation_id"],
            http_method=entry["http_method"],
            path=entry["path"],
        )
