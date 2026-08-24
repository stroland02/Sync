"""The symbol map, read out of **Speakeasy's** TypeScript emission.

A third module rather than a branch in either Stainless flavour, and the first from a different
generator. `symbols.py` predicted this shape before anything read it -- "Speakeasy uses an object
property and a helper call" -- and reading `vercel/sdk` confirms it exactly. What that sentence
undersells is where those two things live.

The route is not in the file that declares the method
------------------------------------------------------
Both Stainless flavours write the verb and path inside the method body, so one file states one
operation. Speakeasy writes a one-line delegation in the class and puts the request in a
standalone function module:

    // src/sdk/aliases.ts
    export class Aliases extends ClientSDK {
      async getAlias(request, options) {
        return unwrapAsync(aliasesGetAlias(this, request, options));
      }
    }

    // src/funcs/aliasesGetAlias.ts
    const path = pathToFunc("/v4/aliases/{idOrAlias}")(pathParams);
    const requestRes = client._createRequest(context, { method: "GET", path: path, ... });

So an operation is assembled across two modules joined by an import the class file states, the
path is the first argument of a helper call and the verb is a property of the object handed to
`_createRequest`. Neither Stainless flavour crosses a module boundary to state one operation.
That is the difference that makes this a third rule, and it is also the reason this rule has a
raise site the other two do not need.

The base class is not the client, and is not the resource either
-----------------------------------------------------------------
`symbols.py` anchors the client on `SyncAPIClient` and resources on `SyncAPIResource`;
`symbols_typescript.py` anchors resources on `APIResource` and finds the client by what it does,
because there the client extends a vendor-named base. Speakeasy is a third arrangement again:
`Vercel`, all 41 of its resources **and** the bare `VercelCore` extend `ClientSDK` alike. The base
identifies a candidate and cannot pick the root.

The root is therefore the class that mounts another candidate and is not itself mounted. That is
strictly narrower than the TypeScript flavour's "mounts a resource and is not one", and it has to
be: here every class is the same kind of thing, so being unmounted is the only thing left that
distinguishes a client from a resource. `VercelCore` -- which is `export class VercelCore extends
ClientSDK {}` and nothing else -- falls out of it for free rather than being named, the same way
`Async*` falls out of the Python flavour's base-class rule.

A mount is a getter, not a property initialiser
------------------------------------------------
    private _aliases?: Aliases;
    get aliases(): Aliases {
      return (this._aliases ??= new Aliases(this._options));
    }

The mount name is the getter's, not the class's or the backing field's, because the getter is
what a customer writes. The `new` expression inside it names the class.

Three raise sites, and why those points
----------------------------------------
The same rule both Stainless flavours state -- half the shape is not the shape -- at the three
places this emission can be absent. Nothing extends `ClientSDK`, so there is no candidate class;
or candidates exist and none mounts another, so nothing is rooted; or -- and this one is
Speakeasy's alone -- classes and mounts are both present and no route could be read, because the
request modules the classes delegate to are not in the checkout. That third case parses cleanly,
roots cleanly and yields an empty map, which is the partial-map failure with a coverage number
attached to make it look like a measurement.

What the flavours share, and what stays duplicated
---------------------------------------------------
`ExtractedOperation`, `ExtractionReport`, `UnrecognisedSdkShape`, `_route` and
`read_spec_operations` are imported rather than copied, exactly as the TypeScript flavour imports
them -- that is reusing a decision already proven, not inventing an abstraction.

**The tree-sitter plumbing is now `typescript_grammar`, and that is a correction rather than a
second thought.** This module's original argument for copying it priced the four differences that
make this a third rule -- what a class is, what a mount is, how a class is identified, and whether
an operation is readable from one file -- and every one of those is a fact about a generator. What
tree-sitter does with an escape is not, and the copy is how one reader got that fixed and the other
did not: `_string_literal` arrived here as a verbatim copy of the pre-fix `_plain_route`, false
docstring sentence included, and the fix landed on the original nine hours later. So the split
holds where it was argued for and does not hold over the parser.

What is still **not** extracted, and for the original reason: the breadth-first walk from a root
composing a chain, and -- between this module and `symbols_typescript.py` -- `_module_key`,
`_specifier_target` and `_source_files`, which state where a checkout keeps its files rather than
what the parser makes of one. A shared walker parameterised over four generator differences is a
framework for a population of three, written when the third is newest. That duplication is still
the signal, and the day a fourth generator agrees with two of these on all four points is the day
it means something.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import tree_sitter_typescript as tsts
from tree_sitter import Language, Node, Parser

from sync.signals.generated import typescript_grammar as grammar
from sync.signals.generated.symbols import (
    ExtractedOperation,
    ExtractionReport,
    UnrecognisedSdkShape,
    _route,
)

GENERATOR = "speakeasy-typescript"

_TS_LANGUAGE = Language(tsts.language_typescript())

# Every class this rule considers extends it -- the client, each resource, and the bare core
# client. It identifies a candidate; it does not pick the root. See the module docstring.
_CLIENT_BASE = "ClientSDK"

# The helper Speakeasy wraps a route in. Its first argument is the path as written; the call it
# returns is applied to the encoded parameters and says nothing about the route.
_PATH_HELPER = "pathToFunc"

# The client method every request goes through, and the property of its object literal that
# carries the verb. Anchoring on the call rather than searching for any `method:` pair keeps an
# unrelated property of that name from being read as a route's verb.
_REQUEST_BUILDER = "_createRequest"
_METHOD_PROPERTY = "method"

_RELATIVE = re.compile(r"^\.{1,2}/")

# A route segment standing for a value the caller supplies, reduced to a bare placeholder before
# comparing.
#
# **Measured inert for this vendor and kept anyway.** Against the full `vercel/sdk` checkout at
# v1.28.12 the reduction changes nothing: 0 routes unknown to the specification with it and 0
# without, and the denominator is 359 either way. Speakeasy writes the specification's own
# parameter names through unchanged, where Stainless TypeScript rewrites `{model_id}` to
# `${modelID}` and needs this to compare at all.
#
# It stays because the condition it guards is one this generator really has rather than one
# imagined for it. A Speakeasy workflow may apply overlays to the specification before generating,
# and `vercel/sdk`'s applies one -- so the document the SDK was generated from is not the document
# this cross-check reads. That overlay only sets a title, which is why the names still agree; an
# overlay that renamed a path parameter would make every affected route read as unknown, and a
# cross-check firing on a spelling difference trains a reader to ignore it.
#
# The extracted path keeps the SDK's own spelling; only the comparison is normalised.
_PARAMETER = re.compile(r"\{[^}]*\}")

_ClassKey = tuple[str, str]
"""A class's identity: the module that declares it, and its name."""


def _comparable(http_method: str, path: str) -> tuple[str, str]:
    """A method and route reduced to what two artifacts can be compared on.

    `_route` is imported rather than reimplemented: it upper-cases the verb and drops the query
    marker, and that decision was made and measured on the Python flavour. The parameter reduction
    is the TypeScript flavour's addition and is inert for this generator -- measured, see
    `_PARAMETER`. It is kept for the overlay case that comment describes, not carried over on the
    assumption that what one flavour needed the next one needs.

    Inert in outcome rather than unreached: it rewrites eight of this SDK's fifteen readable routes
    and 258 of the specification's 359, and the verdicts agree anyway. As in the TypeScript
    flavour, the reduction bears on the comparison only -- `ExtractedOperation.path` keeps the
    SDK's spelling and is what a binding is built from, so a colliding key costs the denominator
    and the cross-check rather than resolving a call site elsewhere.
    """
    method, route = _route(http_method, path)
    return method, _PARAMETER.sub("{}", route)


def _module_key(path: Path, root: Path) -> str:
    """A file's identity, as a path relative to the checkout root without its extension."""
    return path.relative_to(root).with_suffix("").as_posix()


def _specifier_target(node: Node, source: bytes, path: Path, root: Path) -> str | None:
    """The module an `import ... from` clause names, when it names one in this checkout.

    Speakeasy writes its own imports with a `.js` extension against `.ts` files on disk -- the
    ESM convention -- so the suffix is dropped rather than matched. Only relative specifiers are
    resolved: one naming a package names nothing here, and following it would be reading a
    dependency rather than the SDK.
    """
    source_node = node.child_by_field_name("source")
    if source_node is None:
        return None
    specifier = grammar.node_text(source_node, source).strip("'\"")
    if not _RELATIVE.match(specifier):
        return None
    try:
        return _module_key((path.parent / specifier).resolve(), root)
    except ValueError:
        return None


@dataclass
class _Module:
    """One file, as the four things this rule reads out of it."""

    classes: dict[str, _Class] = field(default_factory=dict)

    imports: dict[str, str] = field(default_factory=dict)
    """`import { aliasesGetAlias } from "../funcs/aliasesGetAlias.js"` as local name to module."""

    route: tuple[str, str] | None = None
    """The verb and path this module builds a request for, when it builds one.

    A request module states exactly one -- measured across all 349 in `vercel/sdk` at v1.28.12,
    each carrying one `pathToFunc` and one `_createRequest`. A module stating none is every other
    file in the SDK and is simply not a request module.
    """


@dataclass
class _Class:
    """One class, as the three things this rule reads out of it."""

    mounts: dict[str, str] = field(default_factory=dict)
    """Getter name to the class name its `new` expression constructs."""

    delegations: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """Method name to every bare function it calls, in source order.

    Every one rather than the first, because the first is the wrapper: Speakeasy writes
    `return unwrapAsync(aliasesGetAlias(this, request, options))`, so the outermost call is
    `unwrapAsync` and the request module is the argument. Which of them is the request is not
    guessed from the name -- it is whichever the importing file resolves to a module that builds
    a request, and the source states both halves of that.
    """

    is_candidate: bool = False


def _helper_path(root: Node, source: bytes) -> str | None:
    """The route this module names, from the first `pathToFunc` call it makes.

    Only that helper is read. A route reconstructed from any string in the file would mean
    reading base URLs, header values and operation ids as though they were paths, and a wrong
    route resolves a call site to an operation the customer never calls.
    """
    for node in grammar.walk(root):
        if node.type != "call_expression":
            continue
        function = node.child_by_field_name("function")
        arguments = node.child_by_field_name("arguments")
        if function is None or arguments is None:
            continue
        if grammar.node_text(function, source) != _PATH_HELPER or not arguments.named_children:
            continue
        found = grammar.string_literal(arguments.named_children[0], source)
        if found:
            return found
    return None


def _builder_verb(root: Node, source: bytes) -> str | None:
    """The verb this module sends, from the object handed to `_createRequest`.

    Anchored on that call rather than on any `method:` pair in the file. Speakeasy writes
    `method` as a property of several unrelated objects, and reading whichever came first would
    make the verb depend on statement order.
    """
    for node in grammar.walk(root):
        if node.type != "call_expression":
            continue
        callee = node.child_by_field_name("function")
        arguments = node.child_by_field_name("arguments")
        if callee is None or arguments is None or callee.type != "member_expression":
            continue
        property_node = callee.child_by_field_name("property")
        if property_node is None or grammar.node_text(property_node, source) != _REQUEST_BUILDER:
            continue
        for argument in arguments.named_children:
            if argument.type != "object":
                continue
            for pair in argument.named_children:
                if pair.type != "pair":
                    continue
                key = pair.child_by_field_name("key")
                value = pair.child_by_field_name("value")
                if key is None or value is None:
                    continue
                if grammar.node_text(key, source).strip("'\"") != _METHOD_PROPERTY:
                    continue
                verb = grammar.string_literal(value, source)
                if verb:
                    return verb
    return None


def _mounted_class(getter: Node, source: bytes) -> str | None:
    """The class a getter constructs, when it constructs one.

    `return (this._aliases ??= new Aliases(this._options))` -- the `new` expression is what names
    the class, and the backing field is not read. A getter returning anything else is not a mount.
    """
    for node in grammar.walk(getter):
        if node.type != "new_expression":
            continue
        constructor = node.child_by_field_name("constructor")
        if constructor is not None and constructor.type == "identifier":
            return grammar.node_text(constructor, source)
    return None


def _delegated_calls(method: Node, source: bytes) -> tuple[str, ...]:
    """Every bare function a method calls, outermost first.

    A Speakeasy method body is one delegation inside a wrapper --
    `return unwrapAsync(aliasesGetAlias(this, request, options))` -- so taking only the first
    call would read `unwrapAsync` every time. Both are returned and the import map decides:
    `unwrapAsync` resolves to a module that builds no request, and the request module is the one
    that does. A call on an object is a method call rather than a delegation and is not read.
    """
    called: list[str] = []
    for node in grammar.walk(method):
        if node.type != "call_expression":
            continue
        function = node.child_by_field_name("function")
        if function is not None and function.type == "identifier":
            called.append(grammar.node_text(function, source))
    return tuple(called)


def _read_class(node: Node, source: bytes) -> _Class:
    read = _Class(is_candidate=_CLIENT_BASE in grammar.extends_names(node, source))

    body = node.child_by_field_name("body")
    if body is None:
        return read

    for member in body.named_children:
        if member.type != "method_definition":
            continue
        name_node = member.child_by_field_name("name")
        if name_node is None:
            continue
        name = grammar.node_text(name_node, source)
        if any(child.type == "get" for child in member.children):
            mounted = _mounted_class(member, source)
            if mounted is not None:
                read.mounts[name] = mounted
            continue
        delegated = _delegated_calls(member, source)
        if delegated:
            read.delegations[name] = delegated

    return read


def _read_module(tree_root: Node, source: bytes, path: Path, root: Path) -> _Module:
    read = _Module()

    for node in grammar.walk(tree_root):
        if node.type == "import_statement":
            target = _specifier_target(node, source, path, root)
            if target is None:
                continue
            for child in grammar.walk(node):
                if child.type != "import_specifier":
                    continue
                alias = child.child_by_field_name("alias")
                name = child.child_by_field_name("name")
                if name is not None:
                    read.imports[grammar.node_text(alias or name, source)] = target
        elif node.type == "class_declaration":
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                read.classes[grammar.node_text(name_node, source)] = _read_class(node, source)

    verb = _builder_verb(tree_root, source)
    route = _helper_path(tree_root, source)
    if verb is not None and route is not None:
        read.route = (verb, route)

    return read


def _source_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in Path(root).rglob("*.ts")
        if "node_modules" not in path.parts and not path.name.endswith(".d.ts")
    )


def extract_symbols(source_root: Path) -> tuple[tuple[ExtractedOperation, ...], tuple[str, ...]]:
    """Every operation the SDK's source states, and every construct it states unreadably.

    The same pair both Stainless flavours return: what was read, then what could not be, present
    and empty on a clean read.

    Raises `UnrecognisedSdkShape` at the three points this emission can be absent: nothing
    extending `ClientSDK`, no candidate mounting another, or no route readable from any module a
    mounted class delegates to. Those refusals stand -- the channel is for a partial loss, and a
    checkout carrying classes without their request modules is exactly the total one the third
    raise exists for.
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
    candidates = {key for key, read in classes.items() if read.is_candidate}
    if not candidates:
        raise UnrecognisedSdkShape(
            f"{GENERATOR}: no class extends {_CLIENT_BASE} under {root}, so this source is not "
            f"shaped the way this rule reads; extracting part of it would produce a map "
            f"indistinguishable from a vendor whose operations cannot be seen"
        )

    # A mount names a bare class, and Speakeasy imports it from the module that declares it, so
    # the importing file's own import map is what says which class is meant. A name no import
    # reaches is left unresolved rather than matched against a class of that name elsewhere --
    # the same refusal the rest of this module makes.
    # An unresolved mount is recorded only where the source named the module the class should be
    # in. Speakeasy imports every mounted class by name, so a mount whose name is in the import
    # map and whose target is not a candidate is a file this checkout does not carry; a `new`
    # naming something the file never imported states no module and is not a mount this rule
    # missed. The same distinction the TypeScript flavour draws, against a different import form.
    mounts: dict[_ClassKey, dict[str, _ClassKey]] = {}
    unresolved: dict[_ClassKey, list[str]] = {}
    for key, read in classes.items():
        module, name = key
        resolved: dict[str, _ClassKey] = {}
        missing: list[str] = []
        for attribute, class_name in read.mounts.items():
            imported = modules[module].imports.get(class_name)
            declaring = imported if imported is not None else module
            if (declaring, class_name) in candidates:
                resolved[attribute] = (declaring, class_name)
            elif imported is not None:
                missing.append(
                    f"{GENERATOR}: {module}: {name}.{attribute} mounts {class_name!r} from "
                    f"{imported!r}, which this checkout does not contain, so that resource and "
                    f"every operation under it is absent"
                )
        mounts[key] = resolved
        unresolved[key] = missing

    mounted = {target for resolved in mounts.values() for target in resolved.values()}
    # The root mounts another candidate and is nothing else's mount. Every class here extends the
    # same base, so being unmounted is the only thing distinguishing a client from a resource --
    # and it is what leaves the bare `VercelCore` out without naming it. Sorted rather than first
    # found, because file order is not a fact about the SDK.
    roots = sorted(key for key, resolved in mounts.items() if resolved and key not in mounted)
    if not roots:
        raise UnrecognisedSdkShape(
            f"{GENERATOR}: {len(candidates)} classes extend {_CLIENT_BASE} under {root} and none "
            f"mounts another, so nothing is rooted and every symbol would be unrooted"
        )

    extracted: dict[str, ExtractedOperation] = {}
    # Recorded for the classes the walk actually reaches, and keyed so a resource mounted twice
    # records its losses once. A class nothing mounts contributes no symbol either, so a decline
    # from it would name a loss the map never stood to have.
    unreadable: dict[str, None] = {}
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
        unreadable.update(dict.fromkeys(unresolved[key]))
        for method_name, delegated in read.delegations.items():
            found = next(
                (
                    modules[target].route
                    for name in delegated
                    if (target := modules[key[0]].imports.get(name)) in modules
                    and modules[target].route is not None
                ),
                None,
            )
            if found is None:
                # A method delegating only to functions this checkout imports from files it does
                # not carry is an operation lost to staging. One delegating to modules that are
                # all present and none of which builds a request is not an operation at all --
                # which is most methods of most classes -- and is not recorded.
                absent = sorted(
                    {
                        target
                        for name in delegated
                        if (target := modules[key[0]].imports.get(name)) is not None
                        and target not in modules
                    }
                )
                if absent:
                    joined = ", ".join(repr(target) for target in absent)
                    unreadable[
                        f"{GENERATOR}: {key[0]}: {key[1]}.{method_name} reaches no request module "
                        f"-- {joined} are not in this checkout -- so it contributes no symbol"
                    ] = None
                continue
            symbol = ".".join([*chain, method_name])
            extracted.setdefault(
                symbol, ExtractedOperation(symbol=symbol, http_method=found[0], path=found[1])
            )
        for attribute, target in mounts[key].items():
            if target not in visited:
                queue.append((target, (*chain, attribute), visited | {key}))

    if not extracted:
        raise UnrecognisedSdkShape(
            f"{GENERATOR}: {len(roots)} rooted clients under {root} reach no operation whose "
            f"route this rule can read; Speakeasy states the verb and path in the request module "
            f"a method delegates to, so a checkout carrying the classes without those modules "
            f"parses and roots cleanly and yields an empty map, which is a partial map with a "
            f"coverage number attached rather than a measurement"
        )

    return tuple(extracted[symbol] for symbol in sorted(extracted)), tuple(unreadable)


def report_extraction(
    source_root: Path, spec_operations: set[tuple[str, str]]
) -> ExtractionReport:
    """Extract, then check every route against the specification the SDK's manifest names.

    The same check both Stainless flavours run, over the same parameter reduction the TypeScript
    one adds. The ratio's denominator is counted after that reduction and the specification's
    operation count before it, and for `vercel/sdk` the two are the same 359 -- Speakeasy spells
    its parameters exactly as the document it generated from does, so nothing is absorbed. That
    equality is a fact about this vendor and not a property of the code; the day an overlay
    renames a parameter the two counts come apart and the line says by how much.
    """
    comparable = {_comparable(method, path) for method, path in spec_operations}
    operations, unreadable = extract_symbols(source_root)
    unknown = tuple(
        operation
        for operation in operations
        if _comparable(operation.http_method, operation.path) not in comparable
    )
    reached = {
        _comparable(operation.http_method, operation.path) for operation in operations
    } & comparable
    return ExtractionReport(
        rule=GENERATOR,
        operations=operations,
        declared_operation_count=len(spec_operations),
        comparable_key_count=len(comparable),
        unknown_to_spec=unknown,
        unreached=tuple(
            sorted(
                operation
                for operation in spec_operations
                if _comparable(*operation) not in reached
            )
        ),
        covered_count=len(reached),
        unreadable=unreadable,
    )
