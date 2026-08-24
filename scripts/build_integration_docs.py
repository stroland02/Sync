"""Generate the integration catalog from the registry, so it cannot lie about coverage.

`docs/integrations/catalog/` is Nango's documentation shape carried by Sync's truth standard:
every page is generated from `sync.signals.registry.registered_adapters()` -- the same call the
command line resolves vendors with -- joined against `vendor-catalog.yaml` for the facts a
registry does not hold (display names, categories, documentation hosts, and the package names of
vendors nothing watches yet). A page therefore cannot exist for an integration the product does
not serve, a served integration cannot be missing its page, and *supported* versus *recognized*
is derived rather than declared. `tests/test_integration_catalog.py` is the drift gate.

Run it after changing the registry, `generated-vendors.yaml`, or `vendor-catalog.yaml`:

    uv run python scripts/build_integration_docs.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import yaml  # noqa: E402

from sync.signals.registry import (  # noqa: E402
    registered_adapters,
    vendor_sdk_bindings,
)

CATALOG_DIR = "docs/integrations/catalog"

_KIND_WATCHED = {
    "coded": (
        "Sync stages this vendor's versioned OpenAPI specification and diffs two pinned "
        "versions with oasdiff. A hand-written adapter resolves the vendor's own symbol "
        "scheme, so a changed operation is matched to the SDK call your code actually makes.\n"
        "\n"
        "Source: [`src/sync/signals/{vendor_id}/`](../../../src/sync/signals/{vendor_id}/)"
    ),
    "generated": (
        "Sync reads the manifest this vendor's SDK generator commits to `{source}`, fetches "
        "the specification the manifest names when its hash moves, and diffs pinned versions "
        "with oasdiff. No agreement with the vendor is required and none can be withdrawn: "
        "the manifest is what the generator writes for its own reasons.\n"
        "\n"
        "Source: [`src/sync/signals/generated/`](../../../src/sync/signals/generated/), "
        "configured by one entry in [`generated-vendors.yaml`](../../../generated-vendors.yaml)"
    ),
    "mcp": (
        "Sync captures the watched MCP server's `tools/list` answer and diffs the capture "
        "structurally, so a renamed tool, a changed parameter, or a removed capability is a "
        "recorded change rather than a surprise at call time.\n"
        "\n"
        "Source: [`src/sync/signals/mcp_server/`](../../../src/sync/signals/mcp_server/)"
    ),
}

_NOT_WATCHED = (
    "## What Sync does not watch\n"
    "\n"
    "Stated because absence claimed as coverage is the failure this product replaces:\n"
    "\n"
    "- **Runtime behavior the specification does not carry.** A latency regression or a "
    "semantic change behind an unchanged schema is invisible to this adapter; attach "
    "telemetry to observe it, and Sync will keep the two kinds of evidence apart.\n"
    "- **Anything requiring this vendor's credentials.** Sync holds no customer secrets, so "
    "nothing here calls the vendor's API on your behalf.\n"
    "- **Versions outside the two you pin.** A diff is between the versions a run names; "
    "Sync does not interpolate what happened between them.\n"
)


def knowledge_base() -> list[dict]:
    return yaml.safe_load((REPO_ROOT / "vendor-catalog.yaml").read_text(encoding="utf-8"))


def _quickstart(vendor_id: str, display_name: str) -> str:
    return (
        "## Quickstart\n"
        "\n"
        "From nothing to this vendor's findings, on your own repository. The full journey, "
        "including what the remediation loop needs, is in "
        "[Getting started](../../getting-started.md).\n"
        "\n"
        "```bash\n"
        "npm start                                  # bring Sync up; it sets up everything\n"
        "uv run sync index --repo <your-remote>     # read your call sites into the graph\n"
        f"uv run sync run --vendor {vendor_id} \\\n"
        "    --from-version <pinned> --to-version <target> --repo <your-remote>\n"
        "```\n"
        "\n"
        f"The console then shows every call site bound to {display_name} operations, each "
        "finding with the provenance rung it arrived at.\n"
    )


def _packages_section(packages: dict | None) -> str:
    if not packages:
        return ""
    lines = ["## What your lockfile declares", ""]
    for ecosystem in sorted(packages):
        names = ", ".join(f"`{name}`" for name in packages[ecosystem])
        lines.append(f"- **{ecosystem}**: {names}")
    lines.append("")
    return "\n".join(lines)


def _registry_packages(vendor_id: str) -> dict | None:
    bindings = vendor_sdk_bindings().get(vendor_id)
    if not bindings:
        return None
    # `package` on npm, `distribution` on PyPI -- the two ecosystems name the thing a lockfile
    # lists differently, and reading only the first dropped every Python distribution silently.
    return {
        language: [binding["package"] if binding.get("package") else binding["distribution"]]
        for language, binding in bindings.items()
        if binding.get("package") or binding.get("distribution")
    }


def _supported_page(entry: dict, kind: str, source: str | None) -> str:
    vendor_id = entry["vendor_id"]
    display = entry["display_name"]
    watched = _KIND_WATCHED[kind].format(vendor_id=vendor_id, source=source or "")
    packages = _packages_section(_registry_packages(vendor_id))
    return (
        f"# {display}\n"
        "\n"
        f"> Status: **supported** -- a registered `{kind}` adapter serves `{vendor_id}`.\n"
        "\n"
        f"{_quickstart(vendor_id, display)}"
        "\n"
        "## What Sync watches\n"
        "\n"
        f"{watched}\n"
        "\n"
        f"{_NOT_WATCHED}"
        "\n"
        f"{packages}"
        f"Official documentation: [{entry['docs_url']}]({entry['docs_url']})\n"
    )


def _recognized_page(entry: dict) -> str:
    display = entry["display_name"]
    packages = _packages_section(entry.get("packages"))
    return (
        f"# {display}\n"
        "\n"
        "> Status: **recognized** -- Sync can name this dependency in your repository, and "
        "does not watch it yet. That is a statement of absence, not a lesser kind of "
        "coverage.\n"
        "\n"
        f"{packages}"
        "\n"
        "## Adding it\n"
        "\n"
        "If this vendor's SDK is built by a supported generator, watching it is one entry in "
        "[`generated-vendors.yaml`](../../../generated-vendors.yaml). Otherwise, a coded "
        "adapter depends on `sync.core` alone -- "
        "[Writing a vendor adapter](../../writing-a-vendor-adapter.md) is the guide, and Sync "
        "does not watch this vendor until one exists.\n"
        "\n"
        "## What Sync does not watch\n"
        "\n"
        "Everything, for this vendor, today. The entry above exists so the absence is named "
        "instead of silent.\n"
        "\n"
        f"Official documentation: [{entry['docs_url']}]({entry['docs_url']})\n"
    )


def _index(supported: list[tuple[dict, str]], recognized: list[dict]) -> str:
    lines = [
        "# Integration catalog",
        "",
        "Generated from the vendor registry by `scripts/build_integration_docs.py` -- the "
        "same call the command line resolves vendors with, so this table cannot claim an "
        "integration the product does not serve. *Supported* means a registered adapter "
        "watches the vendor today; *recognized* means Sync can name the dependency and says "
        "so, and watching it is described on its page.",
        "",
        "Missing a vendor entirely? [Writing a vendor adapter](../../writing-a-vendor-adapter.md) "
        "is the path, and an adapter depends on `sync.core` alone.",
        "",
        "## Supported",
        "",
        "| Vendor | Adapter kind | Categories |",
        "|---|---|---|",
    ]
    for entry, kind in supported:
        lines.append(
            f"| [{entry['display_name']}]({entry['vendor_id']}.md) | {kind} | "
            f"{', '.join(entry['categories'])} |"
        )
    lines += [
        "",
        "## Recognized",
        "",
        "| Vendor | Categories |",
        "|---|---|",
    ]
    for entry in recognized:
        lines.append(
            f"| [{entry['display_name']}]({entry['vendor_id']}.md) | "
            f"{', '.join(entry['categories'])} |"
        )
    lines.append("")
    return "\n".join(lines)


def _llms_txt(pages: list[str]) -> str:
    lines = [
        "# Sync documentation index",
        "#",
        "# One line per page, for agents and the future website build.",
        "",
        "docs/getting-started.md - from nothing to a closed loop on your own repository",
        "docs/how-it-works.md - the API Dependency Graph and the five pipeline stages",
        "docs/architecture.md - the system's shape and its boundaries",
        "docs/writing-a-vendor-adapter.md - add a vendor; adapters depend on sync.core alone",
        "docs/developing.md - prerequisites, install, and the quality gates",
    ]
    lines += [f"{page} - integration catalog page" for page in sorted(pages)]
    lines.append("")
    return "\n".join(lines)


def generate() -> list[tuple[str, str]]:
    """Every generated file as (repo-relative path, content), deterministic order."""
    entries = {entry["vendor_id"]: entry for entry in knowledge_base()}
    registered = {adapter.vendor_id: adapter for adapter in registered_adapters()}

    files: list[tuple[str, str]] = []
    supported: list[tuple[dict, str]] = []
    recognized: list[dict] = []

    for vendor_id in sorted(entries):
        entry = entries[vendor_id]
        adapter = registered.get(vendor_id)
        if adapter is not None:
            supported.append((entry, adapter.kind))
            page = _supported_page(entry, adapter.kind, adapter.source)
        else:
            recognized.append(entry)
            page = _recognized_page(entry)
        files.append((f"{CATALOG_DIR}/{vendor_id}.md", page))

    files.insert(0, (f"{CATALOG_DIR}/index.md", _index(supported, recognized)))
    files.append(("docs/llms.txt", _llms_txt([path for path, _ in files if path.endswith(".md")])))
    return files


def main() -> None:
    for rel_path, content in generate():
        target = REPO_ROOT / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        print(f"wrote {rel_path}")


if __name__ == "__main__":
    main()
