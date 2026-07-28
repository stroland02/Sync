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

# The generator input for Stripe's own SDKs, published beside the specification
# at the same tags. Its `x-stableId` names the SDK method for an operation, which
# is what `build_symbol_map` reads instead of guessing one from the HTTP verb.
SDK_SPEC_PATH_IN_REPO = "openapi/spec3.sdk.json"

# A new value in a response enum breaks only an exhaustive switch, and it is
# four fifths of what oasdiff reports on a Stripe release -- 86,368 of 107,396
# records between v2320 and v2330. Carrying that volume through the graph to
# produce findings nobody asked for is the wrong default. It lives here rather
# than in core because it is a judgement about one vendor's release habits,
# not a fact about API changes.
NOISE_KINDS = frozenset({"response-property-enum-value-added"})


def fetch_spec(tag: str, dest: Path, path_in_repo: str = SPEC_PATH_IN_REPO) -> Path:
    """Download a document at a given tag of stripe/openapi.

    Tags are sequential (`v2345`). Uses the authenticated `gh` CLI so it works
    without a separate token. Requests the raw file bytes via the
    `application/vnd.github.raw` Accept header rather than the default JSON
    envelope: spec3.json is larger than the 1 MB limit GitHub enforces on the
    base64-encoded `.content` field, so the envelope form fails outright for
    this file. Bytes are written unchanged — no `text=True` round trip — so a
    Windows console's non-UTF-8 default encoding can't corrupt the spec's
    non-ASCII characters.

    A tag names an immutable commit, so a populated `dest` is already
    byte-identical to what a fresh fetch would produce and is returned as-is
    without invoking `gh`. A zero-byte `dest` is not treated as cached: that
    is what an interrupted or failed previous write leaves behind, and
    reusing it would hand a truncated spec to oasdiff.
    """
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            "gh", "api", f"repos/{SPEC_REPO}/contents/{path_in_repo}?ref={tag}",
            "--header", "Accept: application/vnd.github.raw",
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"failed to fetch stripe spec at {tag}: {result.stderr.decode(errors='replace').strip()}")
    dest.write_bytes(result.stdout)
    return dest


def fetch_sdk_spec(tag: str, dest: Path) -> Path | None:
    """Download `openapi/spec3.sdk.json`, or return None if the tag has none.

    The document is an enhancement to the symbol map rather than a requirement
    for it: a tag predating `x-stableId` degrades to the HTTP-verb derivation, so
    a failed fetch is a supported outcome and must not end the run. That swallows
    every `gh` failure and not only a 404, which is affordable because the
    specification itself is fetched first and still raises — a real outage
    surfaces there rather than being mistaken for an absent document here.

    It is 10 MB, larger than the specification it accompanies, so it relies on
    the same cache-by-destination that `fetch_spec` already applies.
    """
    try:
        return fetch_spec(tag, dest, SDK_SPEC_PATH_IN_REPO)
    except RuntimeError:
        return None


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
        records = [r for r in run_oasdiff_breaking(base, revision) if r.get("id") not in NOISE_KINDS]
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
