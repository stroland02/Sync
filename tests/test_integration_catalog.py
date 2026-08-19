"""The integration catalog is generated from the registry, so it cannot lie about coverage.

The catalog's argument is Nango's shape with Sync's truth-standard: a per-vendor page with a
quickstart, what is watched, what is deliberately not watched, and where the code lives. The
shape is a documentation convention and is learnable; the content is generated from
`sync.signals.registry.registered_adapters()` -- the same call the command line resolves vendors
with -- so a page cannot exist for an integration the product does not serve, and a served
integration cannot be missing its page. `scripts/build_integration_docs.py` is the generator;
these tests are the drift gate, the same pattern the API/type contract uses.

Licensing fence, recorded where the work happens: Nango's repository is Elastic License 2.0
(measured 2026-08-18), so nothing in `vendor-catalog.yaml` or the generated pages is copied from
it. Entries are our own words over verifiable facts about third-party vendors.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from scripts.build_integration_docs import CATALOG_DIR, generate, knowledge_base
from sync.signals.registry import registered_adapters

REPO_ROOT = Path(__file__).resolve().parents[1]


def _fresh() -> dict[str, str]:
    return {path: content for path, content in generate()}


def test_the_committed_catalog_matches_a_fresh_generation():
    """Regenerate and diff. A hand-edited page or a registry change without a rebuild fails
    here rather than shipping a catalog that disagrees with the code."""
    for rel_path, content in _fresh().items():
        committed = REPO_ROOT / rel_path
        assert committed.exists(), f"{rel_path} is not committed; run the generator"
        assert committed.read_text(encoding="utf-8") == content, (
            f"{rel_path} drifted from the registry; run "
            "`uv run python scripts/build_integration_docs.py`"
        )


def test_every_registered_vendor_has_a_page_and_an_entry():
    fresh = _fresh()
    entries = {entry["vendor_id"] for entry in knowledge_base()}
    for adapter in registered_adapters():
        assert adapter.vendor_id in entries, (
            f"{adapter.vendor_id} is registered but has no vendor-catalog.yaml entry, so its "
            "page would carry an id where a product needs a name"
        )
        assert f"{CATALOG_DIR}/{adapter.vendor_id}.md" in fresh, (
            f"{adapter.vendor_id} is registered but the generator produced no page for it"
        )


def test_supported_status_is_derived_from_the_registry_never_declared():
    """Two lists that can disagree is the defect `registry.py` names. An entry may not claim
    support in data; the generator derives it, and a supported entry may not carry its own
    package list either -- the registry's `vendor_sdk_bindings` is the single source."""
    registered = {adapter.vendor_id for adapter in registered_adapters()}
    for entry in knowledge_base():
        assert "status" not in entry, (
            f"{entry['vendor_id']} declares a status; support is derived from the registry"
        )
        if entry["vendor_id"] in registered:
            assert "packages" not in entry, (
                f"{entry['vendor_id']} is registered, so its packages come from "
                "generated-vendors.yaml via the registry; a copy here will disagree with it"
            )
        else:
            assert entry.get("packages"), (
                f"{entry['vendor_id']} is recognized-only, so the catalog entry is the only "
                "place its packages can come from"
            )


def test_every_page_says_what_is_not_watched():
    """The honesty section is the product position; a catalog page that only advertises is the
    competitor's shape, not ours."""
    fresh = _fresh()
    pages = [p for p in fresh if p.startswith(f"{CATALOG_DIR}/") and not p.endswith("index.md")]
    assert pages, "the generator produced no vendor pages at all"
    for page in pages:
        assert "does not watch" in fresh[page], f"{page} has no not-watched section"


def test_the_llms_index_names_every_catalog_page():
    fresh = _fresh()
    index = fresh["docs/llms.txt"]
    for page in fresh:
        if page.startswith(f"{CATALOG_DIR}/"):
            assert page in index, f"{page} is missing from docs/llms.txt"


def test_the_knowledge_base_file_is_valid_and_unique():
    raw = yaml.safe_load((REPO_ROOT / "vendor-catalog.yaml").read_text(encoding="utf-8"))
    ids = [entry["vendor_id"] for entry in raw]
    assert len(ids) == len(set(ids)), "duplicate vendor_id in vendor-catalog.yaml"
    for entry in raw:
        for key in ("vendor_id", "display_name", "categories", "docs_url"):
            assert entry.get(key), f"{entry.get('vendor_id', '?')} is missing {key}"
        assert entry["docs_url"].startswith("https://"), (
            f"{entry['vendor_id']}: docs_url must be an https URL"
        )
