"""Indexing arbitrary codebases across multiple languages and registered vendors.

Provides a unified entrypoint for discovering all third-party API dependencies in an
arbitrary repository or local checkout, selecting the appropriate language indexers,
extracting all call sites, and recording them into the GraphStore.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

from sync.core import CallSite, RepoRef
from sync.index.literals import index_operation_literals
from sync.index.python_lang import PythonAdapter
from sync.index.typescript import TypeScriptAdapter
from sync.signals.intake import read_declared_dependencies

_LOG = logging.getLogger(__name__)
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


_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")
_PORT = re.compile(r":\d+/")


def remote_repo_id(url: str) -> str:
    """A repository's identity, derived from its remote rather than its checkout.

    Call site ids hash `repo_id`, so this value decides whether two customers
    whose `src/billing.ts` both call `stripe.charges.create` occupy one row or
    two. Every spelling of one remote has to reduce to one string: scheme,
    trailing `.git`, scp-style `git@host:owner/name`, a port, an embedded
    credential. The credential in particular must not survive, because the
    result is written to every `call_site` row and hashed into the branch name
    the forge pushes.

    Path case is preserved. GitHub is case-insensitive there, but not every
    host is, and splitting one repository in two is a cheaper mistake than
    merging two distinct ones.

    Lives here rather than in `cli` because both derivation paths read it: `run`
    normalizes the remote it was given, and `_resolve_repo_ref` below normalizes
    the checkout's own origin — one function, or the two spellings of one
    repository drift apart, which was measured on 2026-08-18 as three identities
    for this repository in one graph.
    """
    remote = _SCHEME.sub("", url.strip().rstrip("/"))
    userinfo, at, rest = remote.partition("@")
    if at and "/" not in userinfo:
        remote = rest
    remote = _PORT.sub("/", remote, count=1)
    remote = remote.replace(":", "/", 1)
    host, _, path = remote.removesuffix(".git").partition("/")
    return f"{host.lower()}/{path}"


def _origin_url(path: Path) -> str | None:
    """The checkout's own origin remote, or None when it has none to speak of."""
    if not (path / ".git").exists():
        return None
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    url = result.stdout.strip()
    if result.returncode != 0 or not url:
        return None
    # A path-shaped origin (a local mirror) carries no forge identity; deriving one from it
    # would put a filesystem path into every call-site id.
    if "://" not in url and not re.match(r"^[^:@]+@[^/\\:@]+:", url):
        return None
    return url


def _resolve_repo_ref(target: RepoRef | Path | str) -> RepoRef:
    """Convert a path or RepoRef into a normalized RepoRef with valid repo_id and head_sha.

    **The origin decides the identity, when there is one.** `run --repo <remote>` derives
    `repo_id` from the remote, so a checkout of that same remote must derive the same string —
    otherwise one repository holds two identities in the graph depending on which door it came
    in through, and every screen scoped to one cannot see the other's rows. Measured 2026-08-18:
    this repository held three. The package name and the directory name remain the fallbacks
    for a checkout with no forge-addressable origin, which is exactly the first-run case
    `sync index` exists for.
    """
    if isinstance(target, RepoRef):
        return target
    path = Path(target).resolve()
    if not path.is_dir():
        raise ValueError(f"repository path '{path}' is not a directory")

    origin = _origin_url(path)
    if origin is not None:
        repo_id = remote_repo_id(origin)
    else:
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


def _cache_candidates(vendor_id: str, cache_dir: Path | None) -> list[Path]:
    """Where a staged specification cache for this vendor might be, most specific first.

    **The per-vendor subdirectory is a candidate in its own right**, and it is the layout every
    caller stages: `_load_stripe` reads `<cache_dir>/symbols.json`, so a map written to
    `<cache_dir>/<vendor>/symbols.json` is invisible unless the vendor directory is offered
    directly. The discovery branch already knew that; the explicit branch did not, so a cache
    staged on purpose was never found -- `load_vendor` raised `FileNotFoundError` and the next
    line fetched the specification over the network instead.

    **Absolute, because a relative path resolves against the process's working directory.** Which
    adapter loaded therefore depended on where the process happened to stand, which is the
    order-dependence that made a plain bug look environmental: on a machine or a run where the
    fetch succeeded the real adapter appeared, and where it timed out the fallback took over and
    invented operation ids.
    """
    if cache_dir is not None:
        return [(cache_dir / vendor_id).resolve(), cache_dir.resolve()]
    return [
        Path(f".cache/specs/{vendor_id}").resolve(),
        Path(".cache/specs").resolve(),
        Path(".cache").resolve(),
    ]


def _load_or_create_vendor_adapter(
    vendor_id: str,
    cache_dir: Path | None = None,
    from_version: str = "v2320",
    to_version: str = "v2330",
) -> Any | None:
    """The adapter for this vendor, or `None` when none can be resolved.

    **`None` rather than a stand-in.** This used to return a fallback that answered
    `operation_for_symbol` by deriving an operation id from the symbol's own words -- so a symbol
    the specification calls `PostCharges` came back as `CreateCharges`, an operation no vendor
    has. A finding built on that names something that does not exist, and the patch agent would
    open a pull request against it. That is worse than crashing, because it looks like an answer.

    Making the derived name correct was never the fix: the adapter had no specification to be
    correct against. `index_codebase` already skips a vendor whose adapter is `None`, so the
    honest outcome costs nothing -- no adapter, no call sites for that vendor, and the log says
    which vendor could not be resolved and why both routes to it failed.
    """
    failures: list[tuple[Path, Exception, Exception]] = []
    for candidate in _cache_candidates(vendor_id, cache_dir):
        if candidate is not None and candidate.is_dir():
            context = VendorContext(
                cache_dir=candidate,
                from_version=from_version,
                to_version=to_version,
            )
            try:
                return load_vendor(vendor_id, context)
            except Exception as load_failure:
                try:
                    prepared = prepare_vendor(vendor_id, context)
                    return prepared.adapter
                except Exception as prepare_failure:
                    failures.append((candidate, load_failure, prepare_failure))

    # Loud, because choosing the fallback is a decision rather than a detail: it answers
    # `operation_for_symbol` by inventing an operation id from the symbol's own words, so a
    # finding built on it can name an operation no vendor has. Two nested bare `except ...: pass`
    # used to make this silent, which is why a night of CI failures reported no reason at all.
    for candidate, load_failure, prepare_failure in failures:
        _LOG.warning(
            "no adapter loaded for %s from %s: load failed with %r, prepare failed with %r; "
            "so this vendor is skipped and contributes no call sites",
            vendor_id,
            candidate,
            load_failure,
            prepare_failure,
        )
    if not failures:
        _LOG.warning(
            "no staged cache found for %s in any of %s; this vendor is skipped and contributes "
            "no call sites",
            vendor_id,
            [str(c) for c in _cache_candidates(vendor_id, cache_dir)],
        )
    return None


# Lines each side of the call in a captured snippet. Bounded so the graph holds a window a
# drawer can render, never a file: the graph stores no path back to the checkout, so index
# time is the only moment the source is in hand (the same fact that keeps the API from ever
# reading a customer file at request time).
SNIPPET_CONTEXT_LINES = 4


def _attach_snippets(repo_path: Path, sites: list[CallSite]) -> list[CallSite]:
    """Each site with a bounded source window attached, in the order given.

    A file that cannot be re-read leaves its sites as they were rather than failing the pass:
    the snippet is evidence for a reader, not part of the binding, and an index run must not
    abandon a repository because one file went unreadable between the parse and this pass.
    """
    lines_by_path: dict[str, list[str] | None] = {}
    out: list[CallSite] = []
    for cs in sites:
        if cs.path not in lines_by_path:
            try:
                lines_by_path[cs.path] = (
                    (repo_path / cs.path).read_text(encoding="utf-8").splitlines()
                )
            except (OSError, UnicodeDecodeError, ValueError):
                lines_by_path[cs.path] = None
        lines = lines_by_path[cs.path]
        if lines is None or cs.line < 1 or cs.line > len(lines):
            out.append(cs)
            continue
        start = max(1, cs.line - SNIPPET_CONTEXT_LINES)
        end = min(len(lines), cs.line + SNIPPET_CONTEXT_LINES)
        out.append(
            cs.model_copy(
                update={
                    "snippet": "\n".join(lines[start - 1 : end]),
                    "snippet_start_line": start,
                }
            )
        )
    return out


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

    deduped_sites = _attach_snippets(repo_path, deduped_sites)

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
