"""The symbol map, read out of Stainless's **TypeScript** emission.

A second module rather than a branch in `symbols.py`, because the two Stainless flavours do not
emit the same thing. Python writes the route as a positional literal or `path_template(...)`;
TypeScript writes it as a tagged template, mounts resources with class-property initialisers
instead of `cached_property`, and reaches its client through `this._client` rather than `self`.
Two of those are surface and one is not: the tagged template has to be reassembled from literal
parts, and a rule covering both would be guessing about whichever it had not seen.

Everything else follows `symbols.py`, deliberately. Same `ExtractedOperation`, same
`ExtractionReport`, same `read_spec_operations`, so `GeneratedSpecAdapter` can take either and a
report reads the same in a log line whichever produced it.

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

The client's own mounts arrive through a barrel
-----------------------------------------------
`client.ts` writes `new API.Completions(this)`, and `API` is `./resources/index` -- a module that
declares no class and re-exports every resource from the file that does. Resolving a mount only
against classes declared in the aliased module therefore finds nothing at all rooted, which is
not a partial reading of this SDK but a total one.

So `export { Completions } from './completions'` and `export * from './shared'` are parsed and
followed, transitively, exactly as the aliases are. This stays inside the rule: a re-export is a
declaration the source makes, not a convention inferred about where a class probably lives. A
name that no chain of re-exports reaches is left unresolved rather than guessed at, and the mount
holding it simply is not an edge.

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
from dataclasses import dataclass, field
from pathlib import Path

import tree_sitter_typescript as tsts
from tree_sitter import Language, Node, Parser

from sync.signals.generated.symbols import (
    GENERATOR as _PYTHON_GENERATOR,
)
from sync.signals.generated.symbols import (
    ExtractedOperation,
    ExtractionReport,
    UnrecognisedSdkShape,
    _route,
)

GENERATOR = "stainless-typescript"

_TS_LANGUAGE = Language(tsts.language_typescript())

_RESOURCE_BASE = "APIResource"

_CLIENT_PROPERTY = "this._client"

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

_ClassKey = tuple[str, str]
"""A class's identity: the module that declares it, and its name."""


@dataclass(frozen=True)
class TypeScriptExtractionReport(ExtractionReport):
    """The same report, carrying the name of the rule that actually produced it.

    Only the name differs, and it has to differ: `ExtractionReport.render` names the module-level
    generator of the flavour that defined it, so a TypeScript extraction rendered through it would
    tell an operator that `stainless-python` read the SDK -- and the whole point of naming the
    generator is that a reader learns which rule spoke. Every number the line carries is the same
    line the Python flavour renders, deliberately, and is composed by it rather than restated.
    """

    def render(self) -> str:
        return f"{GENERATOR}{super().render().removeprefix(_PYTHON_GENERATOR)}"


def _comparable(http_method: str, path: str) -> tuple[str, str]:
    """A method and route reduced to what two artifacts can be compared on.

    `_route` is imported rather than reimplemented: it drops the query marker, and that decision
    was made and measured on the Python flavour. What is added here is the parameter reduction,
    which that flavour does not need -- its SDK writes the specification's own parameter names,
    and this one does not.

    **This reduction bears on the comparison only, never on a binding.**
    `ExtractedOperation.path` keeps the SDK's own spelling and is what `operation_for_symbol`
    builds an `OperationRef` from, so two routes reducing to one key cannot resolve a call site to
    the other one. What a collision costs is the coverage denominator, counted through this, and
    the cross-check's verdict on a route -- both silently. It is measured injective over every
    specification this repository pins; `2026-07-29-parameter-reduction-collisions.md` carries the
    counts and `tests/test_parameter_reduction.py` fails the day one of them collides.
    """
    method, route = _route(http_method, path)
    return method, _PARAMETER.sub("{}", route)


def _text(node: Node, source: bytes) -> str:
    """A node's own bytes as text.

    Decoded strictly. A real SDK carries identifiers and comments in any language, and a lenient
    decode would turn one of them into a route or a class name that silently differs from what
    the file says.
    """
    return source[node.start_byte : node.end_byte].decode("utf-8")


def _walk(node: Node):
    yield node
    for child in node.children:
        yield from _walk(child)


def _module_key(path: Path, root: Path) -> str:
    """A file's identity, as a path relative to the checkout root without its extension."""
    return path.relative_to(root).with_suffix("").as_posix()


def _specifier_target(node: Node, source: bytes, path: Path, root: Path) -> str | None:
    """The module an `import`/`export ... from` clause names, when it names one in this checkout.

    Only relative specifiers are resolved. A specifier naming a package names nothing here, and
    following it would be reading a dependency rather than the SDK.
    """
    source_node = node.child_by_field_name("source")
    if source_node is None:
        return None
    specifier = _text(source_node, source).strip("'\"")
    if not _RELATIVE.match(specifier):
        return None
    try:
        return _module_key((path.parent / specifier).resolve(), root)
    except ValueError:
        return None


@dataclass
class _Class:
    """One class, as the three things this rule reads out of it."""

    mounts: dict[str, tuple[str, str]] = field(default_factory=dict)
    """Property name to the class it constructs, as (aliased module, class name) before
    re-exports are followed."""

    operations: dict[str, tuple[str, str]] = field(default_factory=dict)
    is_resource: bool = False


@dataclass
class _Module:
    """One file, as what it declares and what it forwards."""

    classes: dict[str, _Class] = field(default_factory=dict)
    aliases: dict[str, str] = field(default_factory=dict)
    """`import * as ModelsAPI from './models'` as alias to module key."""

    reexports: dict[str, str] = field(default_factory=dict)
    """`export { Models } from './models'` as exported name to the module it came from."""

    star_reexports: list[str] = field(default_factory=list)
    """`export * from './shared'`, as module keys, consulted in declaration order."""


def _extends(node: Node, source: bytes) -> set[str]:
    """The classes a declaration extends.

    The `extends` clause only. An `implements` clause names an interface, which cannot be the
    base this rule anchors on, and reading the whole heritage would let one be mistaken for it.
    """
    names: set[str] = set()
    for child in node.children:
        if child.type != "class_heritage":
            continue
        for inner in _walk(child):
            if inner.type != "extends_clause":
                continue
            for named in _walk(inner):
                if named.type in ("identifier", "property_identifier", "type_identifier"):
                    names.add(_text(named, source))
    return names


def _plain_route(node: Node, source: bytes) -> str | None:
    """A route written as a plain string literal.

    The fragment rather than the quoted text, so an empty string reads as absent rather than as a
    route. A literal carrying an escape is declined whole: this grammar splits a string at every
    escape, so reading the fragments around one returns a route the source does not state -- a
    literal whose second character is escaped reads as everything before it -- and a wrong route
    resolves a call site to an operation the customer never calls.
    """
    if node.type != "string":
        return None
    if any(child.type == "escape_sequence" for child in node.children):
        return None
    for child in node.children:
        if child.type == "string_fragment":
            return _text(child, source)
    return None


def _tagged_route(node: Node, source: bytes) -> str | None:
    """A route written as a tagged template.

    In this grammar a tagged template is a call whose `arguments` node *is* the template, which is
    why this reads that field rather than looking for a positional list. Only the `path` tag is
    read: an untagged template would mean reading any string built by interpolation, and most of
    those are not routes.

    A template carrying an escape is declined for the reason `_plain_route` states. Every
    substitution, by contrast, contributes a segment where it stood, so a route is never assembled
    with a hole in it however unreadable the expression inside one is.
    """
    if node.type != "call_expression":
        return None
    function = node.child_by_field_name("function")
    template = node.child_by_field_name("arguments")
    if function is None or template is None or template.type != "template_string":
        return None
    if _text(function, source) != _PATH_TAG:
        return None
    if any(child.type == "escape_sequence" for child in template.children):
        return None

    parts: list[str] = []
    for child in template.children:
        if child.type == "string_fragment":
            parts.append(_text(child, source))
        elif child.type == "template_substitution":
            expression = child.named_children
            parts.append("{" + (_text(expression[0], source) if expression else "param") + "}")
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
        if verb is None or _text(object_node, source) != _CLIENT_PROPERTY:
            continue

        arguments = node.child_by_field_name("arguments")
        if arguments is None or not arguments.named_children:
            continue
        first = arguments.named_children[0]
        route = _tagged_route(first, source) or _plain_route(first, source)
        if route is not None:
            return verb, route
    return None


def _mount_target(constructor: Node, source: bytes, module: str) -> tuple[str, str] | None:
    """Which class a mount points at, as (module named by the constructor, class name).

    `ModelsAPI.Models` keeps its alias here and is resolved to a declaring module later, because
    two files in this SDK export a class called `Models` and only the module tells them apart. A
    bare `Models` is named by the module that writes it.
    """
    if constructor.type == "identifier":
        return module, _text(constructor, source)
    if constructor.type == "member_expression":
        alias_node = constructor.child_by_field_name("object")
        class_node = constructor.child_by_field_name("property")
        if alias_node is None or class_node is None:
            return None
        return _text(alias_node, source), _text(class_node, source)
    return None


def _read_class(node: Node, source: bytes, module: str) -> _Class:
    read = _Class(is_resource=_RESOURCE_BASE in _extends(node, source))

    body = node.child_by_field_name("body")
    if body is None:
        return read

    for member in body.named_children:
        if member.type in ("public_field_definition", "field_definition"):
            name_node = member.child_by_field_name("name")
            value_node = member.child_by_field_name("value")
            if name_node is None or value_node is None or value_node.type != "new_expression":
                continue
            constructor = value_node.child_by_field_name("constructor")
            if constructor is None:
                continue
            target = _mount_target(constructor, source, module)
            if target is not None:
                read.mounts[_text(name_node, source)] = target
        elif member.type == "method_definition":
            name_node = member.child_by_field_name("name")
            if name_node is None:
                continue
            found = _operation_in(member, source)
            if found is not None:
                read.operations[_text(name_node, source)] = found

    return read


def _read_module(tree_root: Node, source: bytes, path: Path, root: Path) -> _Module:
    module = _module_key(path, root)
    read = _Module()

    for node in _walk(tree_root):
        if node.type == "import_statement":
            target = _specifier_target(node, source, path, root)
            if target is None:
                continue
            for child in _walk(node):
                if child.type != "namespace_import":
                    continue
                for name in child.children:
                    if name.type == "identifier":
                        read.aliases[_text(name, source)] = target
        elif node.type == "export_statement":
            target = _specifier_target(node, source, path, root)
            if target is None:
                continue
            clause = next((c for c in node.children if c.type == "export_clause"), None)
            if clause is None:
                read.star_reexports.append(target)
                continue
            for specifier in clause.named_children:
                if specifier.type != "export_specifier":
                    continue
                # `type Foo` forwards a type, and a mounted resource is a value. Skipping them
                # keeps a type sharing a class's name from shadowing the class.
                if any(child.type == "type" for child in specifier.children):
                    continue
                alias = specifier.child_by_field_name("alias")
                name = specifier.child_by_field_name("name")
                if name is None:
                    continue
                read.reexports[_text(alias or name, source)] = target
        elif node.type == "class_declaration":
            name_node = node.child_by_field_name("name")
            if name_node is None:
                continue
            read.classes[_text(name_node, source)] = _read_class(node, source, module)

    return read


def _declaring(
    module: str, name: str, modules: dict[str, _Module], seen: frozenset[str] = frozenset()
) -> _ClassKey | None:
    """The module that actually declares `name`, following re-exports from `module`.

    A barrel declares nothing and forwards everything, so a mount naming one has to be followed
    to the file that writes the class. `seen` guards the cycle two barrels re-exporting each
    other would otherwise make; a name no chain reaches returns `None` and its mount is not an
    edge, which is the same refusal the rest of this module makes -- an unresolved name is left
    unresolved rather than matched against a class of that name somewhere else.
    """
    read = modules.get(module)
    if read is None or module in seen:
        return None
    if name in read.classes:
        return module, name
    seen = seen | {module}
    forwarded = read.reexports.get(name)
    if forwarded is not None:
        return _declaring(forwarded, name, modules, seen)
    for star in read.star_reexports:
        found = _declaring(star, name, modules, seen)
        if found is not None:
            return found
    return None


def _resolved_mounts(
    module: str, read: _Class, modules: dict[str, _Module]
) -> dict[str, _ClassKey]:
    """Every mount this class makes, as the key of the class it actually reaches."""
    resolved: dict[str, _ClassKey] = {}
    aliases = modules[module].aliases
    for attribute, (named, class_name) in read.mounts.items():
        target = _declaring(aliases.get(named, named), class_name, modules)
        if target is not None:
            resolved[attribute] = target
    return resolved


def _source_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in Path(root).rglob("*.ts")
        if "node_modules" not in path.parts and not path.name.endswith(".d.ts")
    )


def extract_symbols(source_root: Path) -> tuple[ExtractedOperation, ...]:
    """Every operation the SDK's source states, keyed by the chain a customer writes.

    Raises `UnrecognisedSdkShape` when the source does not carry the shape this rule reads --
    nothing extending `APIResource`, or resources with nothing mounting any of them.
    """
    root = Path(source_root).resolve()
    parser = Parser(_TS_LANGUAGE)

    modules: dict[str, _Module] = {}
    for path in _source_files(root):
        source = path.read_bytes()
        tree = parser.parse(source)
        modules[_module_key(path, root)] = _read_module(tree.root_node, source, path, root)

    classes = {
        (module, name): read
        for module, parsed in modules.items()
        for name, read in parsed.classes.items()
    }
    resources = {key for key, read in classes.items() if read.is_resource}
    if not resources:
        raise UnrecognisedSdkShape(
            f"{GENERATOR}: no class extends {_RESOURCE_BASE} under {root}, so this source is not "
            f"shaped the way this rule reads; extracting part of it would produce a map "
            f"indistinguishable from a vendor whose operations cannot be seen"
        )

    mounts = {
        key: _resolved_mounts(key[0], read, modules) for key, read in classes.items()
    }
    # The client is the class that mounts resources and is not one. Sorted rather than first
    # found, because file order is not a fact about the SDK, and every such class is walked
    # rather than one chosen: this emission writes exactly one, and picking among several by a
    # rule nothing here has seen would be the guessing the split exists to avoid.
    roots = sorted(
        key
        for key, resolved in mounts.items()
        if key not in resources and any(target in resources for target in resolved.values())
    )
    if not roots:
        raise UnrecognisedSdkShape(
            f"{GENERATOR}: {len(resources)} classes extend {_RESOURCE_BASE} under {root} and no "
            f"class mounts any of them, so nothing is reachable and every symbol would be "
            f"unrooted"
        )

    extracted: dict[str, ExtractedOperation] = {}
    # Breadth-first from each root, carrying the chain each mount was reached by. The visited set
    # is per path rather than global: a resource mounted twice is two symbols a customer can
    # write, and both resolve to the same operations.
    queue: list[tuple[_ClassKey, tuple[str, ...], frozenset[_ClassKey]]] = [
        (key, (), frozenset()) for key in roots
    ]
    while queue:
        key, chain, visited = queue.pop(0)
        read = classes.get(key)
        if read is None:
            continue
        for method_name, (verb, route) in read.operations.items():
            symbol = ".".join([*chain, method_name])
            extracted.setdefault(
                symbol, ExtractedOperation(symbol=symbol, http_method=verb, path=route)
            )
        for attribute, target in mounts[key].items():
            if target not in visited:
                queue.append((target, (*chain, attribute), visited | {key}))

    return tuple(extracted[symbol] for symbol in sorted(extracted))


def report_extraction(
    source_root: Path, spec_operations: set[tuple[str, str]]
) -> ExtractionReport:
    """Extract, then check every route against the specification that names the SDK.

    The same check the Python flavour runs, over one further normalisation: a parameter segment
    is reduced to a placeholder on both sides, because this SDK writes `${modelID}` where the
    specification writes `{model_id}` and a cross-check firing on that trains a reader to ignore
    it. The extracted path keeps the SDK's own spelling.

    The denominator is counted after that reduction, so it is the number of distinct routes the
    comparison can actually be made against rather than the number of entries the specification
    happens to list.
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
    return TypeScriptExtractionReport(
        operations=operations,
        spec_operation_count=len(declared),
        unknown_to_spec=unknown,
        covered_count=len(reached),
    )
