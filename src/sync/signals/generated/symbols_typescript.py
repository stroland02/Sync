"""The symbol map, read out of Stainless's **TypeScript** emission.

A second module rather than a branch in `symbols.py`, because the two Stainless flavours do not
emit the same thing. Python writes the route as a positional literal or `path_template(...)`;
TypeScript writes it as a tagged template, mounts resources with class-property initialisers
instead of `cached_property`, and reaches its client through `this._client` rather than `self`.
Two of those are surface and one is not: the tagged template has to be reassembled from literal
parts, and a rule covering both would be guessing about whichever it had not seen.

Everything else follows `symbols.py`, deliberately. Same `ExtractedOperation`, same
`ExtractionReport`, same `read_spec_operations`, so `GeneratedSpecAdapter` can take either and
`report_extraction` reads the same in a log line whichever produced it.

What Stainless writes down in TypeScript, and where
---------------------------------------------------
- A resource class extends `APIResource`. This is the fixed anchor, and it is the anchor for a
  reason the Python flavour does not share: there the client extends a named base
  (`SyncAPIClient`), while here it extends a **vendor-named** generated base -- `Anthropic
  extends BaseAnthropic`. So the client cannot be found by its base and is found by what it
  does: a class that mounts resources and is not itself one.
- A mount is a class property initialised with `new <Alias>.<Class>(...)`, so `client.beta.models`
  is a chain of those edges rather than a path on disk.
- An operation is a method calling `this._client.get` / `post` / `put` / `patch` / `delete` /
  `getAPIList`. The verb is which of those it is; the route is the first argument.

The route is the first argument in one of two forms, both literal:

- a plain string -- `this._client.getAPIList('/v1/models', ...)`;
- a tagged template -- ``this._client.get(path`/v1/models/${modelID}`, ...)``. The literal parts
  are the route and each interpolation stands where it stood. The interpolated expression is a
  local parameter name and says nothing about the route, so it is recorded as a parameter segment
  rather than read.

A class name is not an identity here
------------------------------------
`resources/models.ts` and `resources/beta/models.ts` both export `Models`. The Python flavour keys
classes by bare name and gets away with it on the sample it reads; this cannot, because the root
mounts `API.Models` and `Beta` mounts `ModelsAPI.Models`, and conflating them would file beta's
routes under the top-level mount. That is a wrong answer that *resolves*, which is the failure
this whole approach exists to avoid -- so a class is keyed by the module that declares it, and a
mount is resolved through the importing file's own `import * as X from './y'` alias map.

Two raise sites, and why those points
-------------------------------------
The same rule the Python flavour states -- half the shape is not the shape -- at the two places
this emission can be absent. Nothing extends `APIResource`, so there is no resource to read; or
resources exist and nothing mounts any of them, so nothing is reachable and every symbol would be
unrooted. Either way a partial map is indistinguishable from a vendor whose operations genuinely
cannot be seen, and is worse than an error because it yields a coverage number that reads as a
measurement.

What the two flavours share, and was deliberately not extracted
---------------------------------------------------------------
`ExtractedOperation`, `ExtractionReport`, `_route` and `read_spec_operations` are genuinely
common, and this module imports them rather than copying them -- that is sharing a decision
already proven on one flavour, not a new abstraction. What is *not* extracted is the traversal:
both walk breadth-first from a root composing a chain, and the two differ in what a class is, what
a mount is and how a class is identified. Lifting a shared walker across two shapes when the
second is the first non-Python case would be inventing the abstraction the split exists to avoid.
Both stand, and the duplication is the signal.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import tree_sitter_typescript as tsts
from tree_sitter import Language, Node, Parser

from sync.signals.generated.symbols import (
    ExtractedOperation,
    ExtractionReport,
    UnrecognisedSdkShape,
    _route,
)

GENERATOR = "stainless-typescript"

_TS_LANGUAGE = Language(tsts.language_typescript())

_RESOURCE_BASE = "APIResource"

# The client methods Stainless emits, and the verb each one sends. `getAPIList` is the paginated
# read; it is a GET like any other and is listed because its name does not say so.
_REQUEST_METHODS = {
    "get": "GET",
    "post": "POST",
    "put": "PUT",
    "patch": "PATCH",
    "delete": "DELETE",
    "getAPIList": "GET",
}

# The tag Stainless wraps an interpolated route in. Reading an untagged template would mean
# reading any string built by interpolation, most of which are not routes.
_PATH_TAG = "path"

_RELATIVE = re.compile(r"^\.{1,2}/")

# A route segment standing for a value the caller supplies. Reduced to a bare placeholder before
# comparing, because this SDK writes `${modelID}` where the specification writes `{model_id}` --
# one route spelled by two generators from one document. The extracted path keeps the SDK's
# spelling; only the comparison is normalised.
_PARAMETER = re.compile(r"\{[^}]*\}")


def _comparable(http_method: str, path: str) -> tuple[str, str]:
    """A method and route reduced to what two artifacts can be compared on.

    `_route` is imported rather than reimplemented: it drops the query marker, and that decision
    was made and measured on the Python flavour. What is added here is the parameter reduction,
    which that flavour does not need -- its SDK writes the specification's own parameter names,
    and this one does not.
    """
    method, route = _route(http_method, path)
    return method, _PARAMETER.sub("{}", route)


def _text(node: Node, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _walk(node: Node):
    yield node
    for child in node.children:
        yield from _walk(child)


def _module_key(path: Path, root: Path) -> str:
    """A file's identity, as a path relative to the checkout root without its extension."""
    return path.relative_to(root).with_suffix("").as_posix()


def _import_aliases(tree_root: Node, source: bytes, path: Path, root: Path) -> dict[str, str]:
    """`import * as ModelsAPI from './models'` as alias to module key.

    Only relative specifiers are resolved. A namespace import from a package names nothing in
    this checkout, and following it would be reading a dependency rather than the SDK.
    """
    aliases: dict[str, str] = {}
    for node in _walk(tree_root):
        if node.type != "import_statement":
            continue
        source_node = node.child_by_field_name("source")
        if source_node is None:
            continue
        specifier = _text(source_node, source).strip("'\"")
        if not _RELATIVE.match(specifier):
            continue
        target = (path.parent / specifier).resolve()
        try:
            key = _module_key(target, root)
        except ValueError:
            continue
        for child in _walk(node):
            if child.type == "namespace_import":
                for name in child.children:
                    if name.type == "identifier":
                        aliases[_text(name, source)] = key
    return aliases


def _extends(node: Node, source: bytes) -> set[str]:
    names: set[str] = set()
    for child in node.children:
        if child.type != "class_heritage":
            continue
        for inner in _walk(child):
            if inner.type in ("identifier", "property_identifier"):
                names.add(_text(inner, source))
    return names


def _plain_route(node: Node, source: bytes) -> str | None:
    """A route written as a plain string literal."""
    if node.type != "string":
        return None
    return _text(node, source).strip("'\"`") or None


def _tagged_route(node: Node, source: bytes) -> str | None:
    """A route written as a tagged template.

    In this grammar a tagged template is a call whose arguments node *is* the template, which is
    why this reads `arguments` rather than looking for a positional list. Only the `path` tag is
    read: an untagged template would mean reading any string built by interpolation, and most of
    those are not routes.
    """
    if node.type != "call_expression":
        return None
    function = node.child_by_field_name("function")
    template = node.child_by_field_name("arguments")
    if function is None or template is None or template.type != "template_string":
        return None
    if _text(function, source) != _PATH_TAG:
        return None

    parts: list[str] = []
    for child in template.children:
        if child.type == "string_fragment":
            parts.append(_text(child, source))
        elif child.type == "template_substitution":
            inner = [c for c in child.named_children]
            parts.append("{" + (_text(inner[0], source) if inner else "param") + "}")
    return "".join(parts) or None


def _operation_in(method: Node, source: bytes) -> tuple[str, str] | None:
    """The verb and route a method sends, from the first client call it makes.

    First rather than every one: Stainless emits one request per method, and taking the first
    keeps one operation per method -- the grain the specification counts in.
    """
    for node in _walk(method):
        if node.type != "call_expression":
            continue
        callee = node.child_by_field_name("function")
        if callee is None or callee.type != "member_expression":
            continue
        property_node = callee.child_by_field_name("property")
        object_node = callee.child_by_field_name("object")
        if property_node is None or object_node is None:
            continue
        verb = _REQUEST_METHODS.get(_text(property_node, source))
        if verb is None or _text(object_node, source) != "this._client":
            continue

        arguments = node.child_by_field_name("arguments")
        if arguments is None or not arguments.named_children:
            continue
        first = arguments.named_children[0]
        route = _tagged_route(first, source) or _plain_route(first, source)
        if route is not None:
            return verb, route
    return None


@dataclass
class _Resource:
    """One class, as the two things this rule reads out of it."""

    mounts: dict[str, tuple[str, str]]
    operations: dict[str, tuple[str, str]]
    is_resource: bool


def _read_class(
    node: Node, source: bytes, module: str, aliases: dict[str, str]
) -> _Resource:
    mounts: dict[str, tuple[str, str]] = {}
    operations: dict[str, tuple[str, str]] = {}

    body = node.child_by_field_name("body")
    if body is None:
        return _Resource(mounts={}, operations={}, is_resource=False)

    for member in body.named_children:
        if member.type in ("public_field_definition", "field_definition"):
            name_node = member.child_by_field_name("name")
            value_node = member.child_by_field_name("value")
            if name_node is None or value_node is None or value_node.type != "new_expression":
                continue
            constructor = value_node.child_by_field_name("constructor")
            if constructor is None:
                continue
            target = _mount_target(constructor, source, module, aliases)
            if target is not None:
                mounts[_text(name_node, source)] = target
        elif member.type == "method_definition":
            name_node = member.child_by_field_name("name")
            if name_node is None:
                continue
            found = _operation_in(member, source)
            if found is not None:
                operations[_text(name_node, source)] = found

    return _Resource(
        mounts=mounts,
        operations=operations,
        is_resource=_RESOURCE_BASE in _extends(node, source),
    )


def _mount_target(
    constructor: Node, source: bytes, module: str, aliases: dict[str, str]
) -> tuple[str, str] | None:
    """Which class a mount points at, as (module, class name).

    `ModelsAPI.Models` is resolved through the importing file's alias map, because two files in
    this SDK export a class called `Models` and only the module tells them apart. A bare
    `Models` is declared in the same module.
    """
    if constructor.type == "identifier":
        return module, _text(constructor, source)
    if constructor.type == "member_expression":
        alias_node = constructor.child_by_field_name("object")
        class_node = constructor.child_by_field_name("property")
        if alias_node is None or class_node is None:
            return None
        target_module = aliases.get(_text(alias_node, source))
        if target_module is None:
            return None
        return target_module, _text(class_node, source)
    return None


def _source_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in Path(root).rglob("*.ts")
        if "node_modules" not in path.parts and not path.name.endswith(".d.ts")
    )


def extract_symbols(source_root: Path) -> tuple[ExtractedOperation, ...]:
    """Every operation the SDK's source states, keyed by the chain a customer writes.

    Raises `UnrecognisedSdkShape` when the source does not carry the shape this rule reads.
    """
    root = Path(source_root).resolve()
    parser = Parser(_TS_LANGUAGE)

    classes: dict[tuple[str, str], _Resource] = {}
    for path in _source_files(root):
        source = path.read_bytes()
        tree = parser.parse(source)
        module = _module_key(path, root)
        aliases = _import_aliases(tree.root_node, source, path, root)
        for node in _walk(tree.root_node):
            if node.type != "class_declaration":
                continue
            name_node = node.child_by_field_name("name")
            if name_node is None:
                continue
            classes[(module, _text(name_node, source))] = _read_class(
                node, source, module, aliases
            )

    resources = {key for key, value in classes.items() if value.is_resource}
    if not resources:
        raise UnrecognisedSdkShape(
            f"{GENERATOR}: no class extends {_RESOURCE_BASE} under {root}, so this source is not "
            f"shaped the way this rule reads; extracting part of it would produce a map "
            f"indistinguishable from a vendor whose operations cannot be seen"
        )

    roots = [
        key
        for key, value in classes.items()
        if key not in resources and any(target in resources for target in value.mounts.values())
    ]
    if not roots:
        raise UnrecognisedSdkShape(
            f"{GENERATOR}: {len(resources)} classes extend {_RESOURCE_BASE} under {root} and no "
            f"class mounts any of them, so nothing is reachable and every symbol would be "
            f"unrooted"
        )

    extracted: dict[str, ExtractedOperation] = {}
    queue: list[tuple[tuple[str, str], tuple[str, ...]]] = [(roots[0], ())]
    while queue:
        key, chain = queue.pop(0)
        resource = classes.get(key)
        if resource is None:
            continue
        for method_name, (verb, route) in resource.operations.items():
            symbol = ".".join([*chain, method_name])
            extracted.setdefault(
                symbol, ExtractedOperation(symbol=symbol, http_method=verb, path=route)
            )
        for attribute, target in resource.mounts.items():
            if attribute not in chain:
                queue.append((target, (*chain, attribute)))

    return tuple(extracted[symbol] for symbol in sorted(extracted))


def report_extraction(
    source_root: Path, spec_operations: set[tuple[str, str]]
) -> ExtractionReport:
    """Extract, then check every route against the specification that names the SDK.

    The same check the Python flavour runs, over the same normalisation: a parameter segment is
    reduced to a placeholder on both sides, because this SDK writes `${modelID}` where the
    specification writes `{model_id}` and a cross-check firing on that trains a reader to ignore
    it. The extracted path keeps the SDK's own spelling.
    """
    declared = {_comparable(method, path) for method, path in spec_operations}
    operations = extract_symbols(source_root)
    unknown = tuple(
        operation
        for operation in operations
        if _comparable(operation.http_method, operation.path) not in declared
    )
    reached = {
        _comparable(operation.http_method, operation.path) for operation in operations
    } & declared
    return ExtractionReport(
        operations=operations,
        spec_operation_count=len(spec_operations),
        unknown_to_spec=unknown,
        covered_count=len(reached),
    )
