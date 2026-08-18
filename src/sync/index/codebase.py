"""Indexing arbitrary codebases across multiple languages and registered vendors.

Provides a unified entrypoint for discovering all third-party API dependencies in an
arbitrary repository or local checkout, selecting the appropriate language indexers,
extracting all call sites, and recording them into the GraphStore.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

from sync.core import CallSite, RepoRef
from sync.index.literals import index_operation_literals
from sync.index.python_lang import PythonAdapter
from sync.index.typescript import TypeScriptAdapter
from sync.signals.intake import read_declared_dependencies
from sync.signals.deprecations import DEPRECATION_SOURCES
from sync.signals.registry import (
    VendorContext,
    load_vendor,
    prepare_vendor,
    vendor_sdk_bindings,
)

log = logging.getLogger(__name__)

def _package_to_vendor_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for vendor_id, per_lang in vendor_sdk_bindings().items():
        mapping[vendor_id.lower()] = vendor_id
        for _lang, info in per_lang.items():
            for key in ("package", "distribution", "module"):
                val = info.get(key, "")
                if val:
                    mapping[val.lower()] = vendor_id
    return mapping


@dataclass(frozen=True)
class CodebaseIndexReport:
    """The result of indexing an arbitrary codebase."""

    repo: RepoRef
    languages: tuple[str, ...]
    vendors: tuple[str, ...]
    call_sites: tuple[CallSite, ...]
    unbound_import_paths: tuple[str, ...] = ()
    unread_paths: tuple[str, ...] = ()


def _resolve_repo_ref(target: RepoRef | Path | str) -> RepoRef:
    """Convert a path or RepoRef into a normalized RepoRef with valid repo_id and head_sha."""
    if isinstance(target, RepoRef):
        return target
    path = Path(target).resolve()
    if not path.is_dir():
        raise ValueError(f"repository path '{path}' is not a directory")

    repo_id = path.name
    pkg_json = path / "package.json"
    if pkg_json.is_file():
        try:
            data = json.loads(pkg_json.read_text(encoding="utf-8-sig"))
            if isinstance(data, dict) and "name" in data and isinstance(data["name"], str):
                repo_id = data["name"]
        except Exception:
            pass

    head_sha = "0" * 40
    git_dir = path / ".git"
    if git_dir.exists():
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=path,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if result.returncode == 0 and result.stdout.strip():
                head_sha = result.stdout.strip()
        except Exception:
            pass

    return RepoRef(
        repo_id=repo_id,
        url=f"file://{path.as_posix()}",
        local_path=str(path),
        head_sha=head_sha,
    )


def discover_codebase_vendors(repo_path: Path) -> list[str]:
    """Identify registered vendor IDs declared in root and nested codebase manifests."""
    declared: list[Any] = []
    root_declared, _ = read_declared_dependencies(repo_path)
    declared.extend(root_declared)

    skip_dirs = {"node_modules", ".git", "dist", "build", ".next", ".cache", "coverage", ".turbo", ".output"}
    for manifest_name in ("package.json", "pyproject.toml", "requirements.txt"):
        for manifest_file in repo_path.rglob(manifest_name):
            if manifest_file.parent == repo_path:
                continue
            if any(part in skip_dirs for part in manifest_file.relative_to(repo_path).parts[:-1]):
                continue
            sub_declared, _ = read_declared_dependencies(manifest_file.parent)
            declared.extend(sub_declared)

    discovered: set[str] = set()
    pkg_map = _package_to_vendor_map()
    for dep in declared:
        name_lower = dep.name.lower()
        if name_lower in pkg_map:
            discovered.add(pkg_map[name_lower])
        elif dep.name in pkg_map:
            discovered.add(pkg_map[dep.name])

    return sorted(discovered)


from sync.core import OperationRef


class _FallbackIndexingAdapter:
    """Minimal indexing adapter when no staged specification cache exists."""

    def __init__(self, vendor_id: str) -> None:
        self.vendor_id = vendor_id
        bindings = vendor_sdk_bindings().get(vendor_id)
        if bindings:
            self.sdk_bindings = bindings
        else:
            self.sdk_bindings = {
                "typescript": {"package": vendor_id},
                "python": {"distribution": vendor_id, "module": vendor_id},
            }

    def operation_for_symbol(self, symbol: str, *, language: str | None = None) -> OperationRef | None:
        parts = symbol.split(".")
        if len(parts) >= 3:
            resource = parts[-2]
            action = parts[-1]
            method = "POST" if action in ("create", "post", "cancel", "refund", "update") else "GET"
            op_id = f"{action.capitalize()}{resource.capitalize()}"
            return OperationRef(operation_id=op_id, http_method=method, path=f"/v1/{resource}")
        return None


def _load_or_create_vendor_adapter(
    vendor_id: str,
    cache_dir: Path | None = None,
    from_version: str = "v2320",
    to_version: str = "v2330",
) -> Any | None:
    """Instantiate a VendorAdapter for indexing, from cache or fallback construction."""
    candidate_caches = (
        [cache_dir]
        if cache_dir is not None
        else [Path(".cache/specs"), Path(".cache"), Path(f".cache/specs/{vendor_id}")]
    )
    for candidate in candidate_caches:
        if candidate is not None and candidate.is_dir():
            context = VendorContext(
                cache_dir=candidate,
                from_version=from_version,
                to_version=to_version,
            )
            try:
                return load_vendor(vendor_id, context)
            except Exception:
                try:
                    prepared = prepare_vendor(vendor_id, context)
                    return prepared.adapter
                except Exception:
                    pass

    return _FallbackIndexingAdapter(vendor_id)


def index_codebase(
    target: RepoRef | Path | str,
    *,
    store: Any = None,
    cache_dir: Path | None = None,
    from_version: str = "v2320",
    to_version: str = "v2330",
) -> CodebaseIndexReport:
    """Index an arbitrary codebase across all declared languages and vendors.

    Discovers all vendor dependencies from manifests, matches them to language indexers,
    indexes call sites and wrapper imports, and optionally persists results into GraphStore.
    """
    repo = _resolve_repo_ref(target)
    repo_path = Path(repo.local_path)

    vendors = discover_codebase_vendors(repo_path)
    all_sites: list[CallSite] = []
    unbound_paths: set[str] = set()
    unread_paths: set[str] = set()
    languages_seen: set[str] = set()

    for vendor_id in vendors:
        vendor_adapter = _load_or_create_vendor_adapter(
            vendor_id, cache_dir, from_version, to_version
        )
        if vendor_adapter is None:
            continue

        for adapter_cls in (TypeScriptAdapter, PythonAdapter):
            adapter = adapter_cls(vendor_adapter)
            if adapter.matches(repo):
                languages_seen.add(adapter.language_id)
                sites = list(adapter.index(repo))
                all_sites.extend(sites)

                unbound = getattr(adapter, "unbound_import_paths", None)
                if unbound is not None:
                    unbound_paths.update(unbound(repo))

                unread = getattr(adapter, "unread_paths", None)
                if unread is not None:
                    unread_paths.update(unread(repo))

    ts_exts = {".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs"}
    skip_dirs = {"node_modules", ".git", "dist", "build", ".next", ".cache", "coverage", ".turbo", ".output"}
    for p in repo_path.rglob("*"):
        if not p.is_file() or any(part in skip_dirs for part in p.relative_to(repo_path).parts[:-1]):
            continue
        if p.name.endswith(".d.ts") or p.suffix.lower() not in ts_exts:
            continue
        relative = p.relative_to(repo_path).as_posix()
        try:
            source = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            unread_paths.add(relative)
            continue
        for dep_vendor in DEPRECATION_SOURCES:
            literal_sites = index_operation_literals(
                source,
                path=relative,
                repo_id=repo.repo_id,
                vendor_id=dep_vendor.vendor_id,
                sdk_version="unknown",
                prefixes=dep_vendor.prefixes,
            )
            all_sites.extend(literal_sites)

    # Deduplicate call sites by identity
    seen_identities: set[tuple[str, int, int, str, str]] = set()
    deduped_sites: list[CallSite] = []
    for cs in all_sites:
        ident = (cs.path, cs.line, cs.col, cs.symbol, cs.operation_id)
        if ident not in seen_identities:
            seen_identities.add(ident)
            deduped_sites.append(cs)

    if store is not None and hasattr(store, "replace_call_sites"):
        store.replace_call_sites(repo.repo_id, deduped_sites)

    return CodebaseIndexReport(
        repo=repo,
        languages=tuple(sorted(languages_seen)),
        vendors=tuple(sorted(vendors)),
        call_sites=tuple(deduped_sites),
        unbound_import_paths=tuple(sorted(unbound_paths)),
        unread_paths=tuple(sorted(unread_paths)),
    )
