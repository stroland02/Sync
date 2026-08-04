#!/usr/bin/env python
"""Fail the build on a public symbol that nothing in the scanned tree reaches.

Four times in this repository a complete, well-tested component shipped with no caller
anywhere in `src/`: `GraphStore.set_merge_outcome`, `sync.route.matrix.route()`,
`DeprecationAdapter`, and `ingest_payload`. Every one had passing tests the whole time, and
every one was found weeks later by a human running `grep`. The tests were not weak. **Being
tested and being reachable are different properties, and only the first was ever checked.**

This is the same shape of defect as a missing `encoding="utf-8"`, and it gets the same shape
of answer: a static check over call sites rather than over executions, because the thing that
is wrong is a property of the source and no execution exhibits it.

The rule
--------
A public symbol defined in the scanned tree is reported when **no reference to it exists
anywhere in that tree, outside its own package's `__init__.py`.**

Three choices in that sentence carry the whole design.

**Tests are not scanned, so a test reference is not a reference.** A symbol only a test
reaches is precisely what this lint exists to find. CI passes `src` and nothing else.

**A package `__init__.py` re-export is packaging, not use.** Counting it would make every
`__all__` entry in the repository look reachable, which is the single change that would
reduce this lint to decoration.

**A reference from the defining module *does* count.** This is a deliberate narrowing of the
obvious rule, and it is what keeps the output readable. A dead cluster -- a function nothing
calls, the result type it returns, the helper it uses -- is reported once, at the entry point
that nothing reaches, instead of once per member. The cost is that a symbol used only by
other dead code in its own module is not reported on its own; repairing the entry point is
what surfaces it, and repairing the entry point is the work anyway.

What this deliberately does not look at
---------------------------------------
A lint that reports every legitimately uncalled public symbol is noise, is switched off
inside a week, and takes with it the attention that would have gone to a real finding. Each
exemption below is a place the next dead link can hide, which is the point of writing them
down.

- **`sync.core`.** `CLAUDE.md` makes it the surface a third-party adapter author depends on,
  and that author is not in this tree. A `sync.core` symbol with no internal caller is the
  design working. This is the largest blind spot and it is accepted knowingly.
- **`Protocol` classes and every method name declared on one.** A protocol is satisfied by
  shape, so no caller ever names `propose` or `fetch_changes` on a concrete class. Exempting
  the *name* means a dead implementation of a protocol method is invisible; the class that
  holds it is still reported when nothing constructs it, which is the failure that matters.
- **Exception classes.** A `raise` at the definition site is a legitimate sole use, and
  nothing is obliged to catch by type.
- **Console entry points named in `pyproject.toml`'s `[project.scripts]`.** A generated shim
  invokes these by name, and no Python caller exists by construction.
- **Names starting with `_`.** Not public. An unused private is a different and much cheaper
  defect, and one a reader of the module can see.

What counts as a reference
--------------------------
Any `Name`, attribute, import alias, or **string constant** matching the symbol's bare name.
Strings are counted on purpose: registration by string name, `getattr`, and plugin discovery
are real patterns, and a lint that reported something a string reaches would be wrong in the
direction that gets it disabled.

Matching is by bare name and is never resolved. Two symbols sharing a name share a verdict,
so one live `ingest` keeps every other `ingest` alive. That is the conservative direction --
over-counting references means under-reporting dead links -- and it is the correct bias for a
check whose failure mode is noise.

Known limits, so nobody rediscovers them: a recursive function references itself and stays
live; a name reached only through a computed string (an f-string, `prefix + name`) is
invisible; and nested definitions inside a function body are not collected.

Bare-name matching has cost a real repair once, which is worth recording because the shape
recurs. `src/sync/api/app.py` defined its route handlers as local coroutines named after graph
entities -- `vendor_detail`, `finding_detail` -- and the `ast.Name` load that passes each one to
`Route` counted as a reference to the unrelated module-level `sync.dashboard.queries.vendor_detail`
and `finding_detail`. Both were removed from the baseline on the belief that the transport had
wired them; nothing had. The masking is silent in the direction this lint is meant to protect,
and it does not heal on its own, because naming a handler after the entity it serves is a
convention rather than a slip. The handlers carry a leading underscore now. When a baseline entry
disappears, confirm the caller with an import rather than with a name.

The opt-out
-----------
For what the rule above cannot know, put a marker on the definition line:

    def kept_for_the_sdk() -> None:  # lint-dead-links: allow - external SDK callers only

The reason is required. An opt-out with nothing after `allow` is itself reported, because an
opt-out that says nothing is how a lint degrades into decoration.

Usage:
    python scripts/lint_dead_links.py src
    python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
import tomllib
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

# Packages whose public symbols are a published surface. A caller outside this repository is
# the intended consumer, so silence here is the design rather than a defect.
DEFAULT_PUBLIC_PACKAGES = ("sync.core",)

# `# lint-dead-links: allow <reason>` on the definition line. The reason is not optional.
_MARKER = re.compile(r"#\s*lint-dead-links:\s*allow\b(?P<rest>.*)$")

# Punctuation a reason may be introduced with. Only ASCII is stripped; a dash outside it
# simply stays part of the reason, which changes nothing -- the check is that a reason is
# there at all.
_REASON_LEAD = " 	:-"

# A class deriving from one of these, or from a locally defined class that does, is an
# exception. Matched on the base's bare name, which is all the AST offers without imports.
_EXCEPTION_SUFFIXES = ("Error", "Exception")


@dataclass(frozen=True)
class Violation:
    filename: str
    line: int
    qualname: str
    message: str


@dataclass(frozen=True)
class Definition:
    name: str
    qualname: str
    path: Path
    line: int
    kind: str


def _python_files(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    return sorted(p for p in target.rglob("*.py") if ".venv" not in p.parts)


def _package_root(path: Path) -> Path:
    """The directory above the outermost package `path` belongs to.

    Walking up while `__init__.py` is present is what makes the dotted module name
    independent of where the tree is checked out, so `sync.core` matches identically in
    `src/` and in a fixture.
    """
    directory = path.parent
    while (directory / "__init__.py").exists() and directory.parent != directory:
        directory = directory.parent
    return directory


def _module_name(path: Path) -> str:
    relative = path.relative_to(_package_root(path))
    parts = list(relative.parts[:-1])
    if relative.stem != "__init__":
        parts.append(relative.stem)
    return ".".join(parts)


def _in_public_package(path: Path, public_packages: tuple[str, ...]) -> bool:
    module = _module_name(path)
    return any(module == pkg or module.startswith(pkg + ".") for pkg in public_packages)


def _base_names(node: ast.ClassDef) -> list[str]:
    names = []
    for base in node.bases:
        if isinstance(base, ast.Name):
            names.append(base.id)
        elif isinstance(base, ast.Attribute):
            names.append(base.attr)
    return names


def _is_protocol(node: ast.ClassDef) -> bool:
    return "Protocol" in _base_names(node)


def _marker_reason(line_text: str) -> str | None:
    """The opt-out's reason, or `None` when the line carries no marker.

    An empty string means the marker is present and says nothing, which the caller reports
    rather than honours.
    """
    match = _MARKER.search(line_text)
    if match is None:
        return None
    return match.group("rest").strip(_REASON_LEAD).strip()


def _entry_points(targets: list[Path]) -> set[str]:
    """Function names a console script invokes, read from the nearest `pyproject.toml`.

    The search walks up from each scanned path and stops at the first file found, so a
    fixture tree carrying its own `pyproject.toml` is judged by that one.
    """
    found: set[str] = set()
    for target in targets:
        directory = target if target.is_dir() else target.parent
        while True:
            candidate = directory / "pyproject.toml"
            if candidate.exists():
                data = tomllib.loads(candidate.read_text(encoding="utf-8"))
                scripts = data.get("project", {}).get("scripts", {})
                for value in scripts.values():
                    _, _, function = str(value).partition(":")
                    if function:
                        found.add(function.split(".")[-1])
                break
            if directory.parent == directory:
                break
            directory = directory.parent
    return found


def _collect(path: Path, source: str) -> tuple[list[Definition], set[str], set[str], dict[str, str | None]]:
    """Definitions in one module, plus the names it exempts and the markers it carries."""
    tree = ast.parse(source, filename=str(path))
    lines = source.splitlines()
    definitions: list[Definition] = []
    protocol_names: set[str] = set()
    exception_names: set[str] = set()
    markers: dict[str, str | None] = {}

    def record(node: ast.stmt, qualname: str, kind: str) -> None:
        """One definition, and the opt-out marker on its own line if it carries one.

        The marker is read from the `def` or `class` line rather than from anywhere in the
        block: a decorator's line is not the definition, and a marker further down would sit
        too far from what it excuses to be read as excusing it.
        """
        index = node.lineno - 1
        if 0 <= index < len(lines):
            reason = _marker_reason(lines[index])
            if reason is not None:
                markers[qualname] = reason
        definitions.append(Definition(getattr(node, "name"), qualname, path, node.lineno, kind))

    # Two passes over the class definitions: the exception set has to be closed over local
    # subclassing before any class is judged, or `class X(CannotPatch)` reads as ordinary.
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    for node in classes:
        if any(base.endswith(_EXCEPTION_SUFFIXES) for base in _base_names(node)):
            exception_names.add(node.name)
    changed = True
    while changed:
        changed = False
        for node in classes:
            if node.name in exception_names:
                continue
            if any(base in exception_names for base in _base_names(node)):
                exception_names.add(node.name)
                changed = True

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                record(node, node.name, "function")
        elif isinstance(node, ast.ClassDef):
            if _is_protocol(node):
                protocol_names.add(node.name)
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        protocol_names.add(sub.name)
                continue
            if not node.name.startswith("_"):
                record(node, node.name, "class")
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and not sub.name.startswith("_"):
                    record(sub, f"{node.name}.{sub.name}", "method")

    return definitions, protocol_names, exception_names, markers


def _references(path: Path, source: str) -> set[str]:
    """Every bare name this module mentions, however it mentions it."""
    tree = ast.parse(source, filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            names.add(node.value)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add(alias.name.split(".")[-1])
                if alias.asname:
                    names.add(alias.asname)
    return names


def scan_paths(
    targets: list[Path],
    public_packages: tuple[str, ...] = DEFAULT_PUBLIC_PACKAGES,
    entry_points: set[str] | None = None,
) -> list[Violation]:
    """Every public symbol under `targets` that nothing under `targets` reaches."""
    files: list[Path] = []
    for target in targets:
        if target.exists():
            files.extend(_python_files(target))

    sources = {path: path.read_text(encoding="utf-8") for path in files}

    definitions: list[Definition] = []
    exempt_names: set[str] = set()
    markers: dict[tuple[Path, str], str] = {}
    for path, source in sources.items():
        found, protocols, exceptions, module_markers = _collect(path, source)
        definitions.extend(found)
        exempt_names |= protocols | exceptions
        for qualname, reason in module_markers.items():
            markers[(path, qualname)] = reason

    referenced_in: dict[str, set[Path]] = defaultdict(set)
    for path, source in sources.items():
        for name in _references(path, source):
            referenced_in[name].add(path)

    if entry_points is None:
        entry_points = _entry_points(targets)

    violations: list[Violation] = []
    for definition in definitions:
        marker = markers.get((definition.path, definition.qualname))
        if marker is not None:
            if marker:
                continue
            violations.append(
                Violation(
                    filename=str(definition.path),
                    line=definition.line,
                    qualname=definition.qualname,
                    message=(
                        f"{definition.qualname} ({definition.kind}) opts out with no reason; "
                        "an opt-out that says nothing is decoration, so name what reaches it"
                    ),
                )
            )
            continue

        if definition.name in exempt_names or definition.name in entry_points:
            continue
        if _in_public_package(definition.path, public_packages):
            continue

        package_init = definition.path.parent / "__init__.py"
        reachers = referenced_in.get(definition.name, set()) - {package_init}
        if reachers:
            continue

        violations.append(
            Violation(
                filename=str(definition.path),
                line=definition.line,
                qualname=definition.qualname,
                message=(
                    f"{definition.qualname} ({definition.kind}) is reached from nowhere in the "
                    "scanned tree; a component only a test calls is not wired in"
                ),
            )
        )

    return sorted(violations, key=lambda v: (v.filename, v.line))


def load_baseline(path: Path) -> set[str]:
    """The accepted violations, one `<path>:<qualname>` per line.

    A list rather than a count, deliberately. A threshold absorbs both a fix and a new
    defect in silence; a named entry has to be deleted by whoever fixes it.
    """
    if not path.exists():
        return set()
    entries = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            entries.add(stripped)
    return entries


def baseline_key(violation: Violation, root: Path) -> str:
    try:
        relative = Path(violation.filename).resolve().relative_to(root.resolve())
    except ValueError:
        relative = Path(violation.filename)
    return f"{relative.as_posix()}:{violation.qualname}"


def partition(
    violations: list[Violation], baseline: set[str], root: Path
) -> tuple[list[Violation], list[str]]:
    """What is new, and which baseline entries no longer describe anything.

    The second half is what makes the list shrink rather than rot: a repaired symbol fails
    the gate until its line is removed, in the commit that repaired it.
    """
    keys = {baseline_key(v, root) for v in violations}
    new = [v for v in violations if baseline_key(v, root) not in baseline]
    stale = sorted(baseline - keys)
    return new, stale


def main() -> int:
    parser = argparse.ArgumentParser(description="Report public symbols nothing reaches.")
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--baseline", type=Path, default=None,
                        help="file of accepted `<path>:<qualname>` violations")
    parser.add_argument("--root", type=Path, default=Path.cwd(),
                        help="directory baseline paths are relative to")
    parser.add_argument("--public-package", action="append", default=None,
                        help="package whose symbols are a published surface (repeatable)")
    parser.add_argument("--entry-point", action="append", default=None,
                        help="function a console script invokes by name (repeatable)")
    args = parser.parse_args()

    # A gate pointed at nothing reports success. CI names `src`, and a renamed directory
    # would narrow the scan in silence -- the shape of the import-boundary check that once
    # exited 0 without parsing its own argument.
    missing = [p for p in args.paths if not p.exists()]
    if missing:
        for path in missing:
            print(f"{path}: no such file or directory")
        return 2

    public = tuple(args.public_package) if args.public_package else DEFAULT_PUBLIC_PACKAGES
    entry_points = _entry_points(args.paths) | set(args.entry_point or ())

    found = scan_paths(args.paths, public_packages=public, entry_points=entry_points)
    baseline = load_baseline(args.baseline) if args.baseline else set()
    new, stale = partition(found, baseline, args.root)

    for violation in new:
        print(f"{violation.filename}:{violation.line}: {violation.message}")
    for entry in stale:
        print(f"{args.baseline}: {entry} no longer violates; delete this line")

    if new:
        print(f"\n{len(new)} public symbol(s) nothing reaches, or opting out without a reason.")
    if stale:
        print(f"\n{len(stale)} baseline entry(ies) that no longer describe anything.")

    return 1 if new or stale else 0


if __name__ == "__main__":
    sys.exit(main())
