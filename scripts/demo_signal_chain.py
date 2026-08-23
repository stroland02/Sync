"""Walk the Signal stage's acquisition chain for one vendor, out loud.

Every step is the product's own code path, not a re-implementation: the row comes from
`generated-vendors.yaml`, the manifest is parsed by `sync.signals.generated.manifest`, and the
only thing this script adds is printing what each step answered.

    uv run python scripts/demo_signal_chain.py            # anthropic
    uv run python scripts/demo_signal_chain.py openai
    uv run python scripts/demo_signal_chain.py --all      # every configured vendor, hashes only

Reads nothing but public documents and sends no credential.
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sync.signals.generated.manifest import parse_manifest  # noqa: E402

_ROOT = Path(__file__).resolve().parent.parent
_RAW = "https://raw.githubusercontent.com/{repo}/HEAD/{path}"
_AGENT = "sync-signal-demo"


def _get(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": _AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def _rows() -> list[dict]:
    document = yaml.safe_load((_ROOT / "generated-vendors.yaml").read_text(encoding="utf-8"))
    return document["vendors"] if isinstance(document, dict) else document


def _row(vendor_id: str) -> dict:
    for row in _rows():
        if row.get("vendor_id") == vendor_id:
            return row
    raise SystemExit(f"{vendor_id} is not in generated-vendors.yaml")


def walk(vendor_id: str, verbose: bool = True) -> None:
    row = _row(vendor_id)
    repo, manifest_path = row["repo"], row["manifest"]

    if verbose:
        print(f"\n{'=' * 78}\n{vendor_id}\n{'=' * 78}")
        print("\n1. THE ROW  (generated-vendors.yaml -- the only configuration)")
        print(f"     repo:     {repo}")
        print(f"     manifest: {manifest_path}")

    manifest_url = _RAW.format(repo=repo, path=manifest_path)
    if verbose:
        print("\n2. THE MANIFEST  (public file the vendor's own generator commits)")
        print(f"     GET {manifest_url}")

    try:
        text = _get(manifest_url)
    except Exception as exc:  # noqa: BLE001 -- a demo reports, it does not raise
        print(f"     could not read: {exc}")
        return

    source = parse_manifest(manifest_path, text)
    if source is None:
        print("     parsed to nothing -- this manifest names no specification")
        return

    if verbose:
        print(f"     -> generator: {source.generator}")
        print(f"     -> spec_hash: {source.spec_hash or '(none published)'}")

    if source.spec_url is None:
        print("\n3. THE SPECIFICATION")
        print("     none. The manifest is genuine and names no URL -- this is the")
        print("     NO_SPECIFICATION case, not a failure. Cloudflare and Orb both do it.")
        return

    if verbose:
        print("\n3. THE SPECIFICATION  (a static document, not an API call)")
        print(f"     GET {source.spec_url}")

    try:
        spec = _get(source.spec_url)
    except Exception as exc:  # noqa: BLE001
        print(f"     could not read: {exc}")
        return

    print(f"     -> {len(spec):,} bytes")
    # Parsed rather than counted by substring: the first form of this guessed at indentation and
    # printed "roughly 0 paths" for a two-megabyte document -- a wrong number where no number
    # would have been the honest answer.
    _VERBS = {"get", "post", "put", "patch", "delete", "head", "options"}
    try:
        declared = (yaml.safe_load(spec) or {}).get("paths") or {}
        operations = sum(
            1
            for item in declared.values()
            if isinstance(item, dict)
            for verb in item
            if verb.lower() in _VERBS
        )
        print(f"     -> {len(declared)} paths, {operations} operations")
    except Exception as exc:  # noqa: BLE001
        print(f"     -> could not parse to count paths: {exc}")
    print("\n4. WHAT HAPPENS NEXT")
    print("     oasdiff compares this document against the previously staged one and emits")
    print("     one record per structural change. Nothing above involved a model, and nothing")
    print("     above called the vendor's API -- only files they publish.")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if "--all" in sys.argv:
        print(f"{'vendor':<16} {'generator':<11} {'hash':<34} spec")
        print("-" * 96)
        for row in _rows():
            try:
                text = _get(_RAW.format(repo=row["repo"], path=row["manifest"]))
                source = parse_manifest(row["manifest"], text)
            except Exception:  # noqa: BLE001
                source = None
            if source is None:
                print(f"{row['vendor_id']:<16} {'-':<11} {'-':<34} unreadable")
                continue
            print(
                f"{row['vendor_id']:<16} {source.generator:<11} "
                f"{(source.spec_hash or '-'):<34} {'yes' if source.spec_url else 'NO URL'}"
            )
        return
    walk(args[0] if args else "anthropic")


if __name__ == "__main__":
    main()
