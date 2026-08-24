"""The symbol map, read out of a generated SDK's source rather than proposed.

`docs/superpowers/specs/2026-07-29-sync-adaptive-vendor-substrate.md` step 4, and the section
arguing why extraction beats generation. An audit found that coverage cannot refute a
plausible-but-wrong mapping, and the fix is not a better metric -- it is to stop generating the
mapping at all, because a generated SDK already contains it as data.

**The artifact is the argument.** A specification describes what a vendor says the API does; a
model's proposal describes what a model believes. The SDK's source describes what the customer's
process will actually send, and it cannot be wrong about that, because it is the thing that
sends it. Where the SDK and the specification disagree, the SDK is what runs.

This does not overturn `GeneratedSpecAdapter.operation_for_symbol`'s refusal. That docstring
declines to *invent* a convention, and it is right to: a guessed convention fails silently,
since an unresolvable symbol yields no finding and nobody learns the guess was wrong. Nothing
here is invented. Every pair this returns is a string literal lifted from source, and a shape
this rule does not recognise raises rather than answering partially.

One generator, named
--------------------
**Stainless, Python flavour**, and nothing else. The spec's own survey found the mapping stated
three different ways across three generators -- Stripe's own emits `_makeRequest('GET', …)`,
Stainless puts the verb in the method name and the path beside it, Speakeasy uses an object
property and a helper call -- so an extractor claiming to serve every SDK shape would be
guessing about the ones it has not seen. That is the failure this replaces, arriving one level
up. A second generator is a second module, not a branch in this one.

What Stainless writes down, and where
-------------------------------------
Three facts, all of them literal:

- A resource class derives `SyncAPIResource`; the client class derives `SyncAPIClient`.
- A resource is mounted by a `cached_property` whose return annotation names another resource
  class, so `client.messages.batches` is a chain of those edges rather than a path on disk. A
  generator is free to mount a resource under a name its directory does not carry, so the
  directory is not consulted.
- An operation is a method calling `self._get`, `self._post`, `self._put`, `self._patch`,
  `self._delete` or `self._get_api_list`. The verb is which of those it is; the path is the
  first argument, either a plain string or the first argument of `path_template(...)`.

`Async*`, `*WithRawResponse` and `*WithStreamingResponse` fall out for free: none of them
derives `SyncAPIResource`, so the base-class rule excludes them without naming them. They are
the same operations reached differently, and counting them would inflate coverage against a
denominator that counts each operation once.

Parsed with `ast` rather than tree-sitter. tree-sitter earns its place where a file may be
half-written and a tree is still wanted; a generated file parses or the fixture is wrong, and
the interpreter's own parser is exact about what a call's arguments are.

The cross-check is what makes the result refutable
--------------------------------------------------
Extraction alone is one artifact asserting something. `report_extraction` compares it against
the operation set of the specification the vendor's manifest names -- two independently derived
artifacts agreeing is real refutation. An extracted operation the specification does not declare
is reported rather than dropped: dropping it would make a misread source indistinguishable from
a vendor that genuinely does not offer that route.

Coverage travels with its denominator. "Extracted 180 operations" says nothing; the Stripe map's
105 of 414 means something only because the second number is there.

Two denominators, and a channel for what was not read
-----------------------------------------------------
**Two**, because a comparison reduces both sides and a reduction is not free. The number of
operations the specification declares is the API's size; the number of keys those reduce to is what
this comparison can resolve; and the gap is the operations it cannot separate. Reporting one as the
other was a real defect -- 121 keys called 131 operations -- and a ratio taken against the larger
number would divide routes by operations.

**And a channel**, because a construct this rule met and could not read used to lower a number and
say nothing else. A smaller map with no explanation is indistinguishable from a smaller SDK, which
is the false negative the whole approach exists to avoid. Only losses are recorded: a method that
sends no request and a wrapper class this rule excludes on purpose are declined on every run of
every SDK, and a channel carrying those is one nobody reads.
"""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path

GENERATOR = "stainless-python"

_CLIENT_BASE = "SyncAPIClient"
_RESOURCE_BASE = "SyncAPIResource"

# The request helpers Stainless emits, and the verb each one sends. `_get_api_list` is the
# paginated read; it is a GET like any other and is listed because its name does not say so.
_REQUEST_METHODS = {
    "_get": "GET",
    "_post": "POST",
    "_put": "PUT",
    "_patch": "PATCH",
    "_delete": "DELETE",
    "_get_api_list": "GET",
}

# The helper Stainless wraps an interpolated route in. Its first argument is the path as
# written; the keyword arguments are the interpolation and say nothing about the route.
_PATH_TEMPLATE = "path_template"

_MOUNT_DECORATOR = "cached_property"


class UnrecognisedSdkShape(Exception):
    """The source does not look like what this rule reads.

    Raised rather than returning what was found. A partial map is indistinguishable from a
    vendor whose operations genuinely cannot be seen, and it is worse than an error because it
    produces a coverage number that reads as a measurement.
    """


@dataclass(frozen=True)
class ExtractedOperation:
    """One call the SDK makes, as its own source states it.

    The last three fields are `None` for every rule that reads an SDK checkout, because a
    checkout states a route and not the specification's name for it. A rule reading the
    specification itself knows all three, and dropping them would make the richer input answer
    the poorer question.
    """

    symbol: str
    """The chain a customer writes, without the package root -- `messages.batches.create`."""

    http_method: str
    path: str

    operation_id: str | None = None
    """The specification's own name for this operation, where the rule read one.

    `None` means no name was stated, and the caller synthesises `"GET /v1/charges"` from the
    route. That synthesis is deliberate and stays -- inventing a plausible id would be the guess
    this module refuses -- but a rule that read a real id must not have it thrown away.
    """

    service_id: str | None = None
    """Which of a vendor's products this operation belongs to, where the vendor divides itself.

    Twilio publishes sixty documents and a customer calls two of them; Stripe publishes one.
    `None` means the vendor states no division, not that the division is unknown.
    """

    languages: tuple[str, ...] | None = None
    """The languages whose SDK spells this symbol this way, or `None` for all of them.

    A rule reading one checkout knows only that checkout's language and says nothing, which is
    `None`. A rule reading a specification can derive several spellings at once, and a symbol
    that resolves for TypeScript must not resolve a Python call site that never spells it.
    """


@dataclass(frozen=True)
class ExtractionReport:
    """What was extracted, what the specification says about it, and what could not be read.

    **`spec_operation_count` was retired rather than corrected.** It answered "how many distinct
    comparable keys did the specification yield" under a name claiming to answer "how many
    operations does the specification declare", and those are two facts that differ by however
    much the comparison's reduction absorbed -- 121 against 131 for the vendor this repository
    pins. Both are now named for what they count. Reusing the old name for the corrected
    quantity would have handed every existing reader a different number with no error, where a
    name that is gone raises at the first stale read.
    """

    rule: str
    """Which extraction rule produced this, in that rule's own name.

    Carried rather than read off a module constant. `render` used the `GENERATOR` of the rule
    that happened to define this class, so every other rule subclassed it to substitute its own
    name -- three subclasses whose docstrings all said the same thing, and three imports of one
    rule's identity by another. Naming the producer is the point of the line, so the producer
    states it.
    """

    operations: tuple[ExtractedOperation, ...]

    declared_operation_count: int
    """Operations the specification declares -- the API's size.

    Counted before any reduction, which is what distinguishes it from the field below. It is not
    a denominator for `covered_count`: that is counted in comparable routes, and dividing one by
    the other would mix two units into a number that moves when a reduction changes and means
    nothing either way.
    """

    comparable_key_count: int
    """Distinct keys those operations reduce to -- what this comparison can resolve.

    The denominator of `coverage_ratio`, and smaller than the count above by every operation the
    reduction could not keep apart: the query marker this project drops on both sides, and in the
    TypeScript flavours a parameter segment reduced to a placeholder. An operation absorbed that
    way is neither covered nor missed by this report; it is indistinguishable from the operation
    it shares a key with, and `indistinct_operation_count` is how many.
    """

    unknown_to_spec: tuple[ExtractedOperation, ...]

    unreached: tuple[tuple[str, str], ...]
    """Declared operations no extracted symbol reaches, spelled as the specification spells them.

    The other direction of the same cross-check `unknown_to_spec` reports, and the one that carries
    the false negative: a symbol the map lacks is a call site that binds to nothing, so a vendor
    change to that operation finds no call site and the scan reports clean. Its size is what a
    coverage ratio cannot state, because the ratio's denominator is comparable routes and this is
    the surface a vendor moves in operations.

    **Counted in declared operations, where `covered_count` refused to be, and the asymmetry is
    why.** A comparable key two declared operations sit behind cannot be attributed as covered:
    reaching it proves one of them is sent and says nothing about the other. The complement carries
    no such ambiguity -- the reduction only ever merges, so a key no symbol reaches is a key none
    of the operations behind it is sent through. Every entry here is certainly unreached, which
    makes this count exact where the reached one would be a range.

    Spelled as declared rather than reduced, so an operator can find the entry in the document and
    so the two Anthropic flavours -- which reduce differently -- state their losses in one
    vocabulary. Two readers agreeing about a loss is only checkable if their verdicts are
    comparable.
    """

    @property
    def extracted_count(self) -> int:
        return len(self.operations)

    covered_count: int
    """Distinct comparable routes the extraction reaches.

    Distinct, and counted on the specification's side rather than the extraction's. Two symbols
    can send the same request -- `messages.create` and `messages.parse` are both
    `POST /v1/messages` -- so counting extracted entries would report more coverage than there
    are routes to cover, and could exceed the denominator outright.
    """

    unreadable: tuple[str, ...]
    """A construct the source states and this rule could not read, one prose string each.

    `IntakeReport.unreadable`'s key and shape, for the reason recorded there and carried into
    `ReachabilityRanking` and `parse_directory` before this: a reader parsing several artifacts
    needs one rule, not one per artifact. Present and empty on a clean read, and required at
    construction rather than defaulted, so a flavour that records nothing cannot pass for one
    that found nothing.

    **Not every decline.** Every SDK declares methods that send no request and classes that are
    not resources, and every Stainless client mounts wrappers this rule excludes on purpose --
    eleven of them in the committed Anthropic tree. Those are declined on every run and are
    correct, so recording them would bury the few that mean an operation or a whole resource
    subtree is missing from the map. Two kinds are recorded: a mount whose target this rule
    cannot reach, and a request whose route it cannot read.
    """

    @property
    def indistinct_operation_count(self) -> int:
        """Declared operations the comparison cannot tell apart from another.

        Zero is the ordinary answer and is the claim that the two counts are the same fact for
        this vendor. Anything else is the number of operations whose coverage this report can
        state neither way -- reaching their shared key proves one of them is sent and says
        nothing about the rest.
        """
        return self.declared_operation_count - self.comparable_key_count

    @property
    def coverage_ratio(self) -> float:
        if self.comparable_key_count == 0:
            return 0.0
        return self.covered_count / self.comparable_key_count

    def render(self) -> str:
        """One line an operator can read, with every number's denominator attached to it.

        Five counts, because they answer different questions and none substitutes. The symbol
        count is what a call site can resolve against; the comparable-route count is what the
        cross-check can be made against and is the ratio's denominator; the declared-operation
        count is the vendor's API size, which is the only one of the three a vendor publishes
        independently; the number of declared operations no symbol reaches is the surface a vendor
        change can move without any call site being found; and the number of constructs this rule
        could not read is what says whether a small extraction is a small SDK or a rule meeting an
        emission it does not know.
        """
        return (
            f"{self.rule}: {self.extracted_count} symbols extracted, reaching "
            f"{self.covered_count} of {self.comparable_key_count} comparable routes "
            f"({self.coverage_ratio:.1%}); the specification declares "
            f"{self.declared_operation_count} operations"
            + (f", {self.indistinct_operation_count} of them not separately comparable"
               if self.indistinct_operation_count else "")
            + (f"; {len(self.unreached)} declared operations no symbol reaches"
               if self.unreached else "")
            + (f"; {len(self.unknown_to_spec)} extracted operations the specification does not "
               f"declare" if self.unknown_to_spec else "")
            + (f"; {len(self.unreadable)} constructs this rule could not read"
               if self.unreadable else "")
        )


def _decorated_with(node: ast.FunctionDef, name: str) -> bool:
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if isinstance(target, ast.Name) and target.id == name:
            return True
        if isinstance(target, ast.Attribute) and target.attr == name:
            return True
    return False


def _base_names(node: ast.ClassDef) -> set[str]:
    names = set()
    for base in node.bases:
        if isinstance(base, ast.Name):
            names.add(base.id)
        elif isinstance(base, ast.Attribute):
            names.add(base.attr)
    return names


def _annotation_name(node: ast.expr | None) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _path_literal(argument: ast.expr) -> str | None:
    """The route a request helper was handed, when it was handed one literally.

    A path built by anything other than a literal or `path_template` is not read. Reconstructing
    it would mean evaluating the source, and a route this cannot see is better reported missing
    than guessed -- a wrong route resolves a call site to an operation the customer never calls.
    """
    if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
        return argument.value
    if (
        isinstance(argument, ast.Call)
        and _annotation_name(argument.func) == _PATH_TEMPLATE
        and argument.args
        and isinstance(argument.args[0], ast.Constant)
        and isinstance(argument.args[0].value, str)
    ):
        return argument.args[0].value
    return None


def _operation_in(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[tuple[str, str] | None, str | None]:
    """The verb and path a method sends, and the helper it sends through if that could not be read.

    First rather than every one: Stainless emits a method with a single request, and an
    overloaded signature repeats the same call under each overload. Taking the first keeps one
    operation per method, which is the grain the specification counts in.

    The second half of the pair is what separates a method this rule declined from a method that
    is not an operation. A method calling no request helper at all is neither, and answering
    `(None, None)` for it is what keeps the decline channel about losses rather than about every
    method an SDK declares.
    """
    unread: str | None = None
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        callee = node.func
        if not isinstance(callee, ast.Attribute):
            continue
        verb = _REQUEST_METHODS.get(callee.attr)
        if verb is None or not isinstance(callee.value, ast.Name) or callee.value.id != "self":
            continue
        if not node.args:
            unread = unread or callee.attr
            continue
        path = _path_literal(node.args[0])
        if path is not None:
            return (verb, path), None
        unread = unread or callee.attr
    return None, unread


@dataclass
class _Resource:
    """One class, as the two things this rule reads out of it and what it could not read."""

    mounts: dict[str, str]
    operations: dict[str, tuple[str, str]]
    unreadable: list[str]


def _read_class(
    node: ast.ClassDef, resource_classes: set[str], declared_classes: set[str], where: str
) -> _Resource:
    """What one class contributes, and what it states that this rule could not use.

    **A mount naming a class this checkout declares is not recorded.** Every Stainless client
    mounts `*WithRawResponse` and `*WithStreamingResponse` through a `cached_property`, and the
    base-class rule excludes them without naming their spelling -- which is the point, and a
    channel recording them would report eleven expected losses per Anthropic extraction. A name
    nothing here declares is the other case: the file was not staged, the resource is gone, and
    that is one repair. The annotation is the only evidence this language offers, so this is the
    sharpest question available to it; the TypeScript flavours have the module too and ask a
    better one.
    """
    mounts: dict[str, str] = {}
    operations: dict[str, tuple[str, str]] = {}
    unreadable: list[str] = []

    for member in node.body:
        if not isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if isinstance(member, ast.FunctionDef) and _decorated_with(member, _MOUNT_DECORATOR):
            mounted = _annotation_name(member.returns)
            if mounted in resource_classes:
                mounts[member.name] = mounted
            elif mounted is None:
                unreadable.append(
                    f"{GENERATOR}: {where}: {node.name}.{member.name} is a {_MOUNT_DECORATOR} "
                    f"whose return annotation names no class this rule can read, so the resource "
                    f"it mounts and every operation under it is absent"
                )
            elif mounted not in declared_classes:
                unreadable.append(
                    f"{GENERATOR}: {where}: {node.name}.{member.name} mounts {mounted!r}, which "
                    f"this checkout does not declare, so that resource and every operation under "
                    f"it is absent"
                )
            continue
        found, unread_helper = _operation_in(member)
        if found is not None:
            operations[member.name] = found
        elif unread_helper is not None:
            unreadable.append(
                f"{GENERATOR}: {where}: {node.name}.{member.name} calls self.{unread_helper} with "
                f"no route this rule can read, so it contributes no symbol"
            )

    return _Resource(mounts=mounts, operations=operations, unreadable=unreadable)


def _source_files(root: Path) -> list[Path]:
    return sorted(path for path in Path(root).rglob("*.py") if "__pycache__" not in path.parts)


def extract_symbols(source_root: Path) -> tuple[tuple[ExtractedOperation, ...], tuple[str, ...]]:
    """Every operation the SDK's source states, and every construct it states unreadably.

    The pair `read_declared_dependencies` and `parse_directory` already return: what was read,
    then what could not be. The second half is present and empty on a clean read, because an
    absent channel does not distinguish a clean read from a reader that records nothing.

    Raises `UnrecognisedSdkShape` when the source does not carry the shape this rule reads --
    no client class, or a client with no resources reachable from it. That refusal stands: this
    channel is for a partial loss, and a total one is not something to report a count for.
    """
    root = Path(source_root)
    files = _source_files(root)
    trees = {path: ast.parse(path.read_text(encoding="utf-8")) for path in files}

    classes: dict[str, ast.ClassDef] = {}
    where: dict[str, str] = {}
    client_name: str | None = None
    resource_classes: set[str] = set()
    declared_classes: set[str] = set()

    for path, tree in trees.items():
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            declared_classes.add(node.name)
            bases = _base_names(node)
            if _RESOURCE_BASE in bases:
                resource_classes.add(node.name)
                classes[node.name] = node
                where[node.name] = path.relative_to(root).as_posix()
            elif _CLIENT_BASE in bases and client_name is None:
                client_name = node.name
                classes[node.name] = node
                where[node.name] = path.relative_to(root).as_posix()

    if client_name is None:
        raise UnrecognisedSdkShape(
            f"{GENERATOR}: no class deriving {_CLIENT_BASE} under {source_root}, so this source "
            f"is not shaped the way this rule reads; extracting part of it would produce a map "
            f"indistinguishable from a vendor whose operations cannot be seen"
        )
    if not resource_classes:
        raise UnrecognisedSdkShape(
            f"{GENERATOR}: {client_name} derives {_CLIENT_BASE} and no class derives "
            f"{_RESOURCE_BASE} under {source_root}, so no operation is reachable from it"
        )

    read = {
        name: _read_class(node, resource_classes, declared_classes, where[name])
        for name, node in classes.items()
    }

    extracted: dict[str, ExtractedOperation] = {}
    # Recorded for the classes the walk actually reaches, and keyed so a resource mounted twice
    # records its losses once. A class nothing mounts contributes no symbol either, so a decline
    # from it would name a loss the map never stood to have.
    unreadable: dict[str, None] = {}
    # Breadth-first from the client, carrying the chain each mount was reached by. `seen` is per
    # path rather than global: a resource mounted twice is two symbols a customer can write, and
    # both resolve to the same operations.
    queue: list[tuple[str, tuple[str, ...]]] = [(client_name, ())]
    while queue:
        class_name, chain = queue.pop(0)
        resource = read.get(class_name)
        if resource is None:
            continue
        unreadable.update(dict.fromkeys(resource.unreadable))
        for method_name, (verb, path) in resource.operations.items():
            symbol = ".".join([*chain, method_name])
            extracted.setdefault(
                symbol, ExtractedOperation(symbol=symbol, http_method=verb, path=path)
            )
        for attribute, mounted in resource.mounts.items():
            if mounted not in chain:
                queue.append((mounted, (*chain, attribute)))

    return tuple(extracted[symbol] for symbol in sorted(extracted)), tuple(unreadable)


def _route(http_method: str, path: str) -> tuple[str, str]:
    """A method and path reduced to what two artifacts can be compared on.

    The query marker is dropped from **both** sides, and doing it on one was a real defect caught
    by running the extractor over a full checkout rather than the committed subset: this vendor's
    specification writes 120 of its 131 operations with `?beta=true`, its SDK writes the same
    marker into the path literal, and stripping only the specification reported all 113 beta
    operations as unknown to it. A cross-check that fires on a difference in how two artifacts
    spell the same thing trains a reader to ignore it, which is worse than no cross-check.

    Only the comparison is normalised. `ExtractedOperation.path` keeps the route verbatim,
    because the marker is part of what the customer's process actually sends.
    """
    return http_method.upper(), path.split("?", 1)[0]


def read_spec_operations(path: Path) -> set[tuple[str, str]]:
    """The operations a specification declares, as it declares them.

    The verb's case is normalised and nothing else is. Reducing here is what made the operation
    count unrecoverable: `_route` merges a route with its `?beta=true` twin, so this vendor's 131
    published operations arrived as 121 members and the report's denominator counted keys while
    saying it counted operations. Each flavour applies its own reduction to both sides, which is
    where the reduction belongs -- the TypeScript flavours add a second one this file knows
    nothing about.
    """
    declared = json.loads(Path(path).read_text(encoding="utf-8"))
    return {(entry["method"].upper(), entry["path"]) for entry in declared}


def report_extraction(
    source_root: Path, spec_operations: set[tuple[str, str]]
) -> ExtractionReport:
    """Extract, then check every operation against the specification that names the SDK.

    The check is the point. Extraction alone is one artifact asserting something; two
    independently derived artifacts agreeing is refutation. An operation the specification does
    not declare is reported rather than dropped, because a misread source and a vendor that
    genuinely lacks a route are different facts and only one of them is a defect here.

    The disagreement runs both ways and both directions are reported. An operation the
    specification declares that no symbol reaches is where a vendor change finds no call site,
    which is the failure this whole approach exists to avoid, and it is the direction the coverage
    ratio states only as a percentage of a reduced denominator.
    """
    comparable = {_route(method, path) for method, path in spec_operations}
    operations, unreadable = extract_symbols(source_root)
    unknown = tuple(
        operation
        for operation in operations
        if _route(operation.http_method, operation.path) not in comparable
    )
    reached = {
        _route(operation.http_method, operation.path) for operation in operations
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
                if _route(*operation) not in reached
            )
        ),
        covered_count=len(reached),
        unreadable=unreadable,
    )
