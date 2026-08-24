"""The symbol map, read out of **Speakeasy's** Python emission.

The fourth rule, and the second for this generator. `generated-vendors.yaml` configures `mistral`
against `mistralai/client-python` with a Python binding, and `tests/test_configured_vendors.py`
is what reported that no extraction rule covered the pair -- a vendor whose specification is
diffable and whose call sites can never be bound.

The route is back in the file that declares the method
-------------------------------------------------------
Speakeasy's TypeScript emission splits an operation across two modules joined by an import; its
Python emission states both halves as keyword arguments of one call inside the method body:

    # src/mistralai/client/embeddings.py
    req = self._build_request(
        method="POST",
        path="/v1/embeddings",
        ...
    )

So this rule never crosses a module boundary to read one operation -- the Stainless-Python
situation -- while everything around the operation stays Speakeasy's. The client (`Mistral`),
every resource and every nested sub-SDK extend `BaseSDK` alike, so as in `symbols_speakeasy.py`
the base identifies a candidate and cannot pick the root; the root is the class that mounts
another candidate and is not itself mounted.

A mount is a bare class-body annotation
----------------------------------------
The root writes forward references and constructs lazily -- `chat: "Chat"` beside a
`_sub_sdk_map` a `__getattr__` reads -- while a nested sub-SDK writes the class name directly
and assigns eagerly in `_init_sdks` (`conversations: Conversations`). The annotation is the one
statement both shapes make, so it is what this rule reads; the two construction mechanisms are
the generator's plumbing and neither adds a mount the annotations do not state. The mount name
is the annotated attribute -- what a customer writes -- and the class it names is free to live
in a file spelled otherwise: the `models` attribute names class `Models` in `models_.py`.

The async variant is its own symbol
------------------------------------
Stainless emits its async client as separate classes whose chains repeat the sync ones, and the
base-class rule excludes them without losing a symbol anybody writes. Speakeasy Python emits the
async variant as a sibling method on the same class -- `create_async` beside `create`, calling
`_build_request_async` with the same route -- so it is a different chain and a real call site,
and excluding it would resolve `mistral.embeddings.create_async(...)` to nothing. Both are
extracted. Coverage cannot inflate: it is counted in distinct comparable routes on the
specification's side.

Three raise sites, matching the flavour this generator already has
-------------------------------------------------------------------
Nothing extends `BaseSDK`, so there is no candidate class; or candidates exist and none mounts
another, so nothing is rooted; or classes and mounts are present and no route could be read, so
the checkout parses and roots cleanly and would yield an empty map -- the partial-map failure
with a coverage number attached to make it look like a measurement.

What is shared, and what stays duplicated
------------------------------------------
`ExtractedOperation`, `ExtractionReport`, `UnrecognisedSdkShape`, `_route`, `_base_names` and
`_annotation_name` are imported from the Python flavour rather than copied -- parsing Python with
`ast` is a language fact, not a generator fact, which is the same line `typescript_grammar` draws
for tree-sitter. `_PARAMETER` is imported from the TypeScript flavour because the overlay
condition it guards is a property of a Speakeasy workflow, not of the emitted language. The
breadth-first walk stays duplicated for the reason `symbols_speakeasy.py` records: a shared
walker parameterised over what a class is, what a mount is and where a route lives would be a
framework for a population of four, and the day two generators agree on all of those is the day
it means something.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from sync.signals.generated.symbols import (
    ExtractedOperation,
    ExtractionReport,
    UnrecognisedSdkShape,
    _annotation_name,
    _base_names,
    _route,
    _source_files,
)
from sync.signals.generated.symbols_speakeasy import _PARAMETER

GENERATOR = "speakeasy-python"

# Every class this rule considers extends it -- the client, each resource, and each nested
# sub-SDK. It identifies a candidate; it does not pick the root. See the module docstring.
_CLIENT_BASE = "BaseSDK"

# The builder every request goes through, in its sync and async spelling. The verb and route are
# its keyword arguments, and anchoring on the call rather than on any `method=`/`path=` pair
# keeps an unrelated keyword of either name from being read as a route's half.
_REQUEST_BUILDERS = {"_build_request", "_build_request_async"}
_METHOD_KEYWORD = "method"
_PATH_KEYWORD = "path"


def _comparable(http_method: str, path: str) -> tuple[str, str]:
    """A method and route reduced to what two artifacts can be compared on.

    `_route` drops the query marker on both sides, decided and measured on the Stainless Python
    flavour. The fragment drop is this emission's own condition: Speakeasy distinguishes a
    streaming operation over one route with a `#stream` marker (`/v1/chat/completions#stream` in
    `mistralai/client-python`), a fragment never reaches the wire, and the specification declares
    the route without it -- a comparison keeping it would report every streaming operation as
    unknown to the spec. The parameter reduction is imported from the TypeScript flavour because
    the overlay condition it guards belongs to a Speakeasy workflow rather than to a language.

    Only the comparison is normalised. `ExtractedOperation.path` keeps the SDK's own spelling,
    marker included, and is what a binding is built from.
    """
    method, route = _route(http_method, path)
    return method, _PARAMETER.sub("{}", route.split("#", 1)[0])


def _annotated_class(node: ast.expr) -> str | None:
    """The class a bare annotation names, in either spelling this emission uses.

    The root writes a quoted forward reference (`chat: "Chat"`) because it constructs lazily; a
    nested sub-SDK writes the name directly (`conversations: Conversations`). One statement, two
    spellings, and an annotation that is neither -- a subscript, a union -- names no class.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return _annotation_name(node)


def _string_of(node: ast.expr | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _operation_in(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[tuple[str, str] | None, str | None]:
    """The verb and path a method sends, and the builder it sends through if that could not be read.

    First rather than every one: this emission writes a single builder call per method. The
    second half of the pair is what separates a method this rule declined from a method that is
    not an operation -- a method calling no builder at all is neither, and answering
    `(None, None)` for it keeps the decline channel about losses rather than about every method.
    """
    unread: str | None = None
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        callee = node.func
        if not isinstance(callee, ast.Attribute) or callee.attr not in _REQUEST_BUILDERS:
            continue
        if not isinstance(callee.value, ast.Name) or callee.value.id != "self":
            continue
        keywords = {kw.arg: kw.value for kw in node.keywords if kw.arg is not None}
        verb = _string_of(keywords.get(_METHOD_KEYWORD))
        route = _string_of(keywords.get(_PATH_KEYWORD))
        if verb is not None and route is not None:
            return (verb, route), None
        unread = unread or callee.attr
    return None, unread


@dataclass
class _SubSdk:
    """One class, as the two things this rule reads out of it and what it could not read."""

    mounts: dict[str, str]
    operations: dict[str, tuple[str, str]]
    unreadable: list[str]


def _read_class(
    node: ast.ClassDef, candidate_classes: set[str], declared_classes: set[str], where: str
) -> _SubSdk:
    """What one class contributes, and what it states that this rule could not use.

    **A mount annotation naming a class this checkout declares but this rule does not read is not
    recorded** -- a candidate annotating its configuration type names something declared and
    ordinary. A name nothing here declares is the other case: the file was not staged, the
    sub-SDK is gone, and that is a loss the map's reader needs explained. The annotation is the
    only evidence, the same position the Stainless Python flavour is in with its return
    annotations; the TypeScript flavours have the module too and ask a sharper question.
    """
    mounts: dict[str, str] = {}
    operations: dict[str, tuple[str, str]] = {}
    unreadable: list[str] = []

    for member in node.body:
        if isinstance(member, ast.AnnAssign) and member.value is None:
            if not isinstance(member.target, ast.Name):
                continue
            mounted = _annotated_class(member.annotation)
            if mounted in candidate_classes:
                mounts[member.target.id] = mounted
            elif mounted is not None and mounted not in declared_classes:
                unreadable.append(
                    f"{GENERATOR}: {where}: {node.name}.{member.target.id} mounts {mounted!r}, "
                    f"which this checkout does not declare, so that sub-SDK and every operation "
                    f"under it is absent"
                )
            continue
        if not isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        found, unread_builder = _operation_in(member)
        if found is not None:
            operations[member.name] = found
        elif unread_builder is not None:
            unreadable.append(
                f"{GENERATOR}: {where}: {node.name}.{member.name} calls self.{unread_builder} "
                f"with no route this rule can read, so it contributes no symbol"
            )

    return _SubSdk(mounts=mounts, operations=operations, unreadable=unreadable)


def extract_symbols(source_root: Path) -> tuple[tuple[ExtractedOperation, ...], tuple[str, ...]]:
    """Every operation the SDK's source states, and every construct it states unreadably.

    The same pair the other three flavours return: what was read, then what could not be, present
    and empty on a clean read.

    Raises `UnrecognisedSdkShape` at the three points this emission can be absent: nothing
    extending `BaseSDK`, no candidate mounting another, or no route readable from any rooted
    class. Those refusals stand -- the channel is for a partial loss, and a checkout that parses
    and roots cleanly while yielding an empty map is the total one the third raise exists for.
    """
    root = Path(source_root)
    trees = {
        path: ast.parse(path.read_text(encoding="utf-8")) for path in _source_files(root)
    }

    classes: dict[str, ast.ClassDef] = {}
    where: dict[str, str] = {}
    declared_classes: set[str] = set()

    for path, tree in trees.items():
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            declared_classes.add(node.name)
            if _CLIENT_BASE in _base_names(node):
                classes[node.name] = node
                where[node.name] = path.relative_to(root).as_posix()

    if not classes:
        raise UnrecognisedSdkShape(
            f"{GENERATOR}: no class deriving {_CLIENT_BASE} under {source_root}, so this source "
            f"is not shaped the way this rule reads; extracting part of it would produce a map "
            f"indistinguishable from a vendor whose operations cannot be seen"
        )

    candidates = set(classes)
    read = {
        name: _read_class(node, candidates, declared_classes, where[name])
        for name, node in classes.items()
    }

    mounted = {target for sub_sdk in read.values() for target in sub_sdk.mounts.values()}
    # The root mounts another candidate and is nothing else's mount. Every class here extends the
    # same base, so being unmounted is the only thing distinguishing a client from a sub-SDK.
    # Sorted rather than first found, because file order is not a fact about the SDK.
    roots = sorted(name for name, sub_sdk in read.items() if sub_sdk.mounts and name not in mounted)
    if not roots:
        raise UnrecognisedSdkShape(
            f"{GENERATOR}: {len(classes)} classes derive {_CLIENT_BASE} under {source_root} and "
            f"none mounts another, so nothing is rooted and every symbol would be unrooted"
        )

    extracted: dict[str, ExtractedOperation] = {}
    # Recorded for the classes the walk actually reaches, and keyed so a sub-SDK mounted twice
    # records its losses once. A class nothing mounts contributes no symbol either, so a decline
    # from it would name a loss the map never stood to have.
    unreadable: dict[str, None] = {}
    # Breadth-first from each root, carrying the chain each mount was reached by. The visited set
    # is per path rather than global: a sub-SDK mounted twice is two symbols a customer can
    # write, and both resolve to the same operations.
    queue: list[tuple[str, tuple[str, ...], frozenset[str]]] = [
        (name, (), frozenset()) for name in roots
    ]
    while queue:
        name, chain, visited = queue.pop(0)
        sub_sdk = read[name]
        unreadable.update(dict.fromkeys(sub_sdk.unreadable))
        for method_name, (verb, path) in sub_sdk.operations.items():
            symbol = ".".join([*chain, method_name])
            extracted.setdefault(
                symbol, ExtractedOperation(symbol=symbol, http_method=verb, path=path)
            )
        for attribute, target in sub_sdk.mounts.items():
            if target not in visited:
                queue.append((target, (*chain, attribute), visited | {name}))

    if not extracted:
        raise UnrecognisedSdkShape(
            f"{GENERATOR}: {len(roots)} rooted clients under {source_root} reach no operation "
            f"whose route this rule can read; a checkout carrying the classes without readable "
            f"builder calls parses and roots cleanly and yields an empty map, which is a partial "
            f"map with a coverage number attached rather than a measurement"
        )

    return tuple(extracted[symbol] for symbol in sorted(extracted)), tuple(unreadable)


def report_extraction(
    source_root: Path, spec_operations: set[tuple[str, str]]
) -> ExtractionReport:
    """Extract, then check every route against the specification the SDK's manifest names.

    The same check the other three flavours run. The reduction adds the fragment drop
    `_comparable` explains, applied to both sides so a difference in how two artifacts spell one
    route cannot read as a disagreement about which routes exist.
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
