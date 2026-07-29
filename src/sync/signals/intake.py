"""Which of a repository's declared dependencies Sync can actually watch.

Step 2 of the sequence in `docs/superpowers/specs/2026-07-29-sync-adaptive-vendor-substrate.md`.
A run answers one question today -- does this repository depend on the vendor I was told to look
at -- and says nothing about the rest of the manifest, so a customer pointing Sync at their
codebase cannot find out what it covers and neither can we.

The middle category is the point
--------------------------------
Three answers, and *watchable but unconfigured* is the work queue. It is the set of dependencies
a tier could serve for the cost of a configuration entry, and it is invisible until something
reports it. It also has to say **what** is missing, because the two reasons are different jobs:

- `MISSING_SDK_BINDING` -- a registered vendor whose adapter does not declare which package a
  customer imports. Its specification is diffable and its call sites cannot be bound, so a scan
  produces zero findings. Fixed by adding `sdk_bindings` to that tier.
- `MISSING_REGISTRY_ENTRY` -- no vendor is registered, and the package's SDK repository commits
  a generator manifest, which is the evidence `generated-vendors.yaml` is built on. Fixed by a
  line in that file.

The join is the SDK repository, never the name
----------------------------------------------
A package is connected to a registered vendor by the repository its SDK is generated from, which
both sides state: the evidence names the repository a package's SDK lives in, and a configured
vendor names the repository its manifest is read from. Nothing matches on a name resembling a
vendor id. `@vercel/sdk` is why -- it is generated from `vercel/sdk`, which vendor `vercel`
configures, and its name resembles nothing. Matching on names would miss it and would also bind
a package coincidentally sharing a vendor's name to a vendor that has nothing to do with it.

The join is exact, so it is per-repository rather than per-vendor. `openai` on npm is generated
from `openai/openai-node` and vendor `openai` is configured against `openai/openai-python`; the
report says the npm package needs a registry entry, which is the true state of the configuration
even though the same vendor already appears in it. Naming the repository in the reason is what
makes that legible rather than confusing.

Watched means both halves, deliberately
---------------------------------------
A vendor the registry resolves is not enough. Four of the six registered vendors -- anthropic,
cloudflare, openai, vercel -- are served by `GeneratedSpecAdapter`, which declares no binding, so
they resolve and bind nothing. Calling them watched would be true against the sequence's wording
and false against what a reader takes from it, in a document that spec calls a sales asset. So
`WATCHED` requires a registered vendor *and* a declared binding for that ecosystem, and a vendor
with one but not the other lands in the middle with the missing half named.

Evidence, not hope
------------------
Nothing is called watchable without evidence a tier can serve it. `generated-vendors.yaml`
records that every entry there "was confirmed by fetching the path", and `mcp-servers.yaml`
configured nothing precisely because no equivalent confirmation existed -- "an entry nobody can
capture for would register a vendor that is offered on the command line and fails on first use."
The same standard binds here. A hopeful "watchable" is a promise the next run breaks.

That evidence is an argument rather than something this module gathers. `generator_manifests`
maps a package name onto the manifest confirmed to exist for it, and the caller does the
fetching -- the separation `sync.signals.generated.manifest` already keeps between parsing and
network, which is what lets the tests drive committed fixtures and reach nothing.

Reading the manifest
--------------------
Parsed here rather than reused from `sync.index`. Both indexers already read these files, but
each does it as a private method on an adapter that must be constructed with a vendor, and
returns a shape built for its own question -- a name-to-version map in one, raw requirement
strings in the other. Intake runs *before* a vendor is chosen; asking which vendors are relevant
at all is the question it exists to answer, so there is no vendor to construct an indexer with,
and importing one would pull tree-sitter into a path that only reads two text files. The
duplication is real and is named here rather than hidden: consolidating it is a change to
`sync.index`, which a live task owns.
"""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from sync.signals.registry import configured_generated_repos, vendor_sdk_bindings
from sync.signals.registry_tier.directory import RegistryEntry, versions_after

WATCHED = "watched"
WATCHABLE = "watchable"
NOT_WATCHABLE = "not-watchable"

MISSING_SDK_BINDING = "sdk-binding"
MISSING_REGISTRY_ENTRY = "registry-entry"
# A public OpenAPI directory knows this API and nothing here reads that directory for it. The
# third reason is separate from the second because the fix is: `MISSING_REGISTRY_ENTRY` is a line
# in `generated-vendors.yaml` naming a repository that commits a generator manifest, and this is
# a tier that reads a directory nobody at the vendor signed.
MISSING_REGISTRY_TIER = "registry-tier"

NPM = "npm"
PYPI = "pypi"

# Which language's binding an ecosystem's package name is declared under, and which field of it
# names the package. The two differ because the languages differ: an npm name is the manifest
# key and the import specifier at once, where Python declares a distribution and imports a
# module. `sync.index.python_lang` carries why.
_BINDING_FIELD = {NPM: ("typescript", "package"), PYPI: ("python", "distribution")}

_VERSION_DELIMITERS = "=<>!~ ;[#"


@dataclass(frozen=True)
class SdkRepository:
    """Confirmed evidence that one package's SDK is produced by a known generator.

    Gathered by a caller and passed in. Both fields were established by fetching: `repo` is where
    the package's SDK is generated, and `manifest` is the path found there. A value nobody
    confirmed is the thing this type exists to keep out.
    """

    repo: str
    manifest: str


@dataclass(frozen=True)
class Dependency:
    """One third-party package a repository declares, as its manifest declares it."""

    name: str
    version: str
    ecosystem: str


@dataclass(frozen=True)
class Assessment:
    """What Sync can do about one dependency, and what is missing when it cannot."""

    dependency: Dependency
    category: str
    reason: str
    vendor_id: str | None = None
    missing: str | None = None
    """Which configuration is absent, for a watchable dependency. None otherwise."""


@dataclass(frozen=True)
class IntakeReport:
    """The three-way split for one repository, plus what could not be read.

    `unreadable` is not an error channel. A manifest that does not parse is a fact a customer
    needs, because a repository whose manifest is unreadable is not a repository with no
    dependencies -- and reported as the latter it reads as a clean scan of an empty project.
    """

    assessments: tuple[Assessment, ...]
    unreadable: tuple[str, ...]

    def counts(self) -> dict[str, int]:
        counts = {WATCHED: 0, WATCHABLE: 0, NOT_WATCHABLE: 0}
        for item in self.assessments:
            counts[item.category] += 1
        return counts

    def to_json(self) -> str:
        """The artifact, for a reader outside this process.

        A structure rather than a rendering: the split is what carries meaning and the
        formatting is the caller's business.
        """
        return json.dumps(
            {
                "counts": self.counts(),
                "dependencies": [
                    {
                        "name": item.dependency.name,
                        "version": item.dependency.version,
                        "ecosystem": item.dependency.ecosystem,
                        "category": item.category,
                        "vendor_id": item.vendor_id,
                        "missing": item.missing,
                        "reason": item.reason,
                    }
                    for item in self.assessments
                ],
                "unreadable": list(self.unreadable),
            },
            indent=2,
        )


def read_sdk_repositories(path: Path) -> dict[str, SdkRepository]:
    """Confirmed package-to-repository evidence, from a file somebody probed and wrote down.

    The shape `generated-vendors.yaml` uses, for the same reason: a confirmation is worth having
    only if it is recorded where a reader can check it, and a fetch inside the classifier would
    make a report of what is on disk quietly online. Nothing here contacts a network -- the file
    *is* the record of the fetch.

    Every entry needs all three fields. A partial entry raises naming the path rather than being
    skipped, because a deployment that wrote evidence down and silently got none would report a
    smaller middle category and no fault.
    """
    entries = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if not isinstance(entries, list):
        raise ValueError(f"{path} does not hold a list of confirmed SDK repositories")

    try:
        return {
            entry["package"]: SdkRepository(repo=entry["repo"], manifest=entry["manifest"])
            for entry in entries
        }
    except (KeyError, TypeError) as exc:
        raise ValueError(
            f"{path}: every entry needs package, repo and manifest ({exc})"
        ) from None


def read_registry_apis(path: Path) -> dict[str, str]:
    """Confirmed package-to-directory-entry evidence, from a file somebody probed and wrote down.

    The same shape and the same discipline as `read_sdk_repositories`. The join is never a name
    resemblance: a directory `api_id` is a domain and a package name is not, `@vercel/sdk`
    resembles nothing it is generated from, and a package coincidentally sharing an API's name
    has nothing to do with it. Somebody has to have confirmed the pair, and this file is where
    that confirmation is recorded so a reader can check it.
    """
    entries = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if not isinstance(entries, list):
        raise ValueError(f"{path} does not hold a list of confirmed package-to-API entries")
    try:
        return {entry["package"]: entry["api"] for entry in entries}
    except (KeyError, TypeError) as exc:
        raise ValueError(f"{path}: every entry needs package and api ({exc})") from None


def _registry_index(
    entries: Sequence[RegistryEntry],
    apis: Mapping[str, str],
    moved_since: str | None,
) -> dict[str, RegistryEntry]:
    """Package name to the directory entry confirmed for it, filtered to what is still live.

    `moved_since` is optional and strict when given. A directory entry proves a machine-readable
    contract exists; an entry last touched in 2017 proves one existed once, which is a weaker
    claim. `versions_after` is what answers that from the one document the tier already holds,
    which is the whole economy of it -- one watermark, one fetch, and no specification
    downloaded to find out.
    """
    by_api = {entry.api_id: entry for entry in entries}
    if moved_since is not None:
        live = {entry.api_id for entry, _ in versions_after(list(entries), moved_since)}
        by_api = {api_id: entry for api_id, entry in by_api.items() if api_id in live}
    return {package: by_api[api_id] for package, api_id in apis.items() if api_id in by_api}


def _normalised(distribution: str) -> str:
    """A distribution name as PEP 503 compares it. Applied to both sides of a PyPI match."""
    return distribution.strip().lower().replace("_", "-")


def _requirement_name(requirement: str) -> str:
    name = requirement
    for delimiter in _VERSION_DELIMITERS:
        name = name.split(delimiter, 1)[0]
    return _normalised(name)


def _requirement_version(requirement: str) -> str:
    remainder = requirement[len(requirement.split(_VERSION_DELIMITERS[0])[0]) :]
    stripped = requirement[len(_requirement_name(requirement)) :].strip()
    return (stripped or remainder).strip() or "unspecified"


def _read_npm(root: Path, unreadable: list[str]) -> list[Dependency]:
    manifest = root / "package.json"
    if not manifest.exists():
        return []
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        unreadable.append(f"package.json could not be read: {exc}")
        return []
    if not isinstance(data, dict):
        unreadable.append("package.json does not hold an object")
        return []

    declared: dict[str, Any] = {
        **(data.get("dependencies") or {}),
        **(data.get("devDependencies") or {}),
    }
    return [
        Dependency(name=name, version=str(version), ecosystem=NPM)
        for name, version in declared.items()
        if isinstance(name, str)
    ]


def _read_pypi(root: Path, unreadable: list[str]) -> list[Dependency]:
    """Both manifests, because both are current practice and reading one reports half the
    ecosystem as declaring nothing."""
    requirements: list[str] = []

    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
            unreadable.append(f"pyproject.toml could not be read: {exc}")
            data = {}
        project = data.get("project")
        if isinstance(project, dict) and isinstance(project.get("dependencies"), list):
            requirements += [item for item in project["dependencies"] if isinstance(item, str)]

    text_manifest = root / "requirements.txt"
    if text_manifest.exists():
        try:
            lines = text_manifest.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError as exc:
            unreadable.append(f"requirements.txt could not be read: {exc}")
            lines = []
        for line in lines:
            stripped = line.split("#", 1)[0].strip()
            if stripped and not stripped.startswith("-"):
                requirements.append(stripped)

    return [
        Dependency(
            name=_requirement_name(item),
            version=_requirement_version(item),
            ecosystem=PYPI,
        )
        for item in requirements
    ]


def read_declared_dependencies(root: Path) -> tuple[tuple[Dependency, ...], tuple[str, ...]]:
    """Every third-party package a repository declares, and every manifest that would not parse.

    Pure: it reads files and returns a description. Nothing here decides watchability and
    nothing reaches a network.
    """
    unreadable: list[str] = []
    found = [*_read_npm(root, unreadable), *_read_pypi(root, unreadable)]
    return tuple(found), tuple(unreadable)


def _declared_packages(bindings: Mapping[str, Mapping[str, Mapping[str, str]]], ecosystem: str):
    """Package name to vendor id, for the vendors that declare one in this ecosystem."""
    language, field = _BINDING_FIELD[ecosystem]
    packages: dict[str, str] = {}
    for vendor_id, per_language in bindings.items():
        declared = per_language.get(language, {}).get(field)
        if isinstance(declared, str):
            key = _normalised(declared) if ecosystem == PYPI else declared
            packages[key] = vendor_id
    return packages


def _classify(
    dependency: Dependency,
    packages: Mapping[str, str],
    configured_repos: Mapping[str, str],
    generator_manifests: Mapping[str, SdkRepository],
    registry: Mapping[str, RegistryEntry],
) -> Assessment:
    key = _normalised(dependency.name) if dependency.ecosystem == PYPI else dependency.name

    vendor_id = packages.get(key)
    if vendor_id is not None:
        return Assessment(
            dependency=dependency,
            category=WATCHED,
            vendor_id=vendor_id,
            reason=f"vendor '{vendor_id}' is registered and declares this package",
        )

    evidence = generator_manifests.get(dependency.name) or generator_manifests.get(key)
    if evidence is None:
        # Checked after the generator tier and never before it. A package a generator serves has
        # a specification derived from the vendor's own repository, and a directory entry for the
        # same package is a mirror -- promoting on the weaker evidence first would report the
        # weaker reason for a dependency that has the stronger one.
        entry = registry.get(dependency.name) or registry.get(key)
        if entry is not None:
            return Assessment(
                dependency=dependency,
                category=WATCHABLE,
                missing=MISSING_REGISTRY_TIER,
                reason=(
                    f"a public OpenAPI directory lists {entry.api_id} "
                    f"(preferred {entry.preferred or 'unstated'}, {len(entry.versions)} version(s)), "
                    f"so a machine-readable contract is discoverable -- but the directory mirrors "
                    f"it rather than hosting it, so this is watchable and never a source a pull "
                    f"request rests on"
                ),
            )
        return Assessment(
            dependency=dependency,
            category=NOT_WATCHABLE,
            reason=(
                "no registered vendor declares this package, and its SDK repository was not "
                "confirmed to commit a generator manifest, so no tier has a specification to read"
            ),
        )

    configured = configured_repos.get(evidence.repo)
    if configured is not None:
        return Assessment(
            dependency=dependency,
            category=WATCHABLE,
            vendor_id=configured,
            missing=MISSING_SDK_BINDING,
            reason=(
                f"vendor '{configured}' is registered against {evidence.repo}, so its "
                f"specification is diffable, but nothing declares which package a customer "
                f"imports -- so no call site can be bound and a scan produces no findings"
            ),
        )

    return Assessment(
        dependency=dependency,
        category=WATCHABLE,
        missing=MISSING_REGISTRY_ENTRY,
        reason=(
            f"{evidence.repo} commits {evidence.manifest}, which the generated tier reads, so "
            f"this vendor is a line in generated-vendors.yaml rather than a module"
        ),
    )


def assess_repository(
    root: Path,
    generator_manifests: Mapping[str, SdkRepository] | None = None,
    bindings: Mapping[str, Mapping[str, Mapping[str, str]]] | None = None,
    configured_repos: Mapping[str, str] | None = None,
    registry_entries: Sequence[RegistryEntry] = (),
    registry_apis: Mapping[str, str] | None = None,
    registry_moved_since: str | None = None,
) -> IntakeReport:
    """The three-way split for one repository.

    Every input a decision rests on can be supplied, and each defaults to what this deployment
    actually has. That is what keeps the classification testable against committed fixtures and
    keeps the network out: `generator_manifests` is evidence somebody gathered, not something
    this function goes and looks up.
    """
    declared, unreadable = read_declared_dependencies(Path(root))
    resolved_bindings = vendor_sdk_bindings() if bindings is None else bindings
    resolved_repos = configured_generated_repos() if configured_repos is None else configured_repos
    evidence = generator_manifests or {}

    packages = {
        ecosystem: _declared_packages(resolved_bindings, ecosystem) for ecosystem in _BINDING_FIELD
    }
    registry = _registry_index(registry_entries, registry_apis or {}, registry_moved_since)
    assessments = tuple(
        _classify(dependency, packages[dependency.ecosystem], resolved_repos, evidence, registry)
        for dependency in declared
    )
    return IntakeReport(assessments=assessments, unreadable=unreadable)
