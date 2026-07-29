"""Python implementation of the LanguageAdapter protocol.

The second implementation of a protocol that had one, which is the only way to find out whether
`LanguageAdapter` is a boundary or a description of `typescript.py`. `index` and `matches` port
cleanly. `prepare` and `static_verify` do not, and the honest versions of those are weaker than
their TypeScript counterparts rather than differently shaped. Where that is true this module says
so and returns the weaker answer, because a gate that reports success it did not earn is worse
than no gate.

Resolution follows the TypeScript passes: find the identifiers bound to the SDK, find attribute
chains rooted at one of them ending in a call, then capture the keyword arguments passed and the
fields read off the result.

Three places Python differs, all of them findings about the protocol rather than about the
grammar:

**The module is a client.** `import stripe` then `stripe.charges.create(...)` binds no variable.
The TypeScript rule -- an identifier assigned from `new Imported(...)` -- has nothing to match,
and ported verbatim it indexes nothing in a repository written that way. Here an imported module
alias is a client root in its own right.

**A response is read by subscript as often as by attribute.** `typescript.py` deliberately stops
a chain at a subscript, because in TypeScript it is nearly always an array index. In Python
`result["status"]` is idiomatic on a dict-like Stripe response, so a string-literal subscript
continues the path and an index does not.

**There is no manifest.** `pyproject.toml` and `requirements.txt` both declare dependencies and
both are current practice, so both are read.

One thing this module deliberately does not do: `stripe.Charge.create(...)`, the older SDK's
resource-class idiom, resolves to no operation. The symbol map is derived from Stripe's own
generator input and names `stripe.charges.create`; binding the two needs an alias table that is
knowledge about one vendor's Python SDK, and that belongs in `sync.signals.stripe`, not here.
The call is left unindexed rather than guessed at.
"""

from __future__ import annotations

import ast
import hashlib
import tomllib
from pathlib import Path
from typing import Iterable

import tree_sitter_python as tspython
from tree_sitter import Language, Node, Parser

from sync.core import CallSite, Patch, RepoRef, VendorAdapter, VerifyResult

_PY_LANGUAGE = Language(tspython.language())
_SDK_PACKAGE = "stripe"
_FUNCTION_TYPES = {"function_definition", "lambda"}
# Where a project may declare that it depends on the SDK. Both are current practice, and reading
# only one reports half the ecosystem as not using it.
_MANIFESTS = ("pyproject.toml", "requirements.txt")
# Files naming a typechecker this adapter does not run. Their presence changes what
# `static_verify` can honestly say, not what it returns.
_MYPY_CONFIG_FILES = ("mypy.ini", ".mypy.ini", "setup.cfg")
_VERSION_DELIMITERS = "=<>!~ ;[#"


def _parser() -> Parser:
    return Parser(_PY_LANGUAGE)


def _text(node: Node, source: bytes) -> str:
    """The source a node covers.

    Sliced from bytes, never from a decoded string. tree-sitter reports byte offsets and Python
    slices strings by character, so on a file holding any non-ASCII text a character slice reads
    from the wrong offset and every symbol, argument and field after it comes out wrong together.
    `sync/route/templates.py` carries a fix for the same confusion, and every other fixture in
    this repository is ASCII, which is what let it go unnoticed there.
    """
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _walk(node: Node):
    yield node
    for child in node.children:
        yield from _walk(child)


def _path(segments: Iterable[str]) -> str:
    return ".".join(segments)


class PythonAdapter:
    language_id = "python"

    def __init__(self, vendor_adapter: VendorAdapter) -> None:
        self._vendor = vendor_adapter

    # --- manifests ----------------------------------------------------------------

    def _requirement_lines(self, repo: RepoRef) -> list[str]:
        """Every dependency this project declares, as the raw requirement strings.

        A customer's manifest is untrusted input, so an unreadable one answers "declares
        nothing" rather than raising: the caller already has a path for a repository that does
        not demonstrably depend on the SDK, and a `TOMLDecodeError` out of `run()` is a
        traceback where that answer belongs.
        """
        root = Path(repo.local_path)
        requirements: list[str] = []

        pyproject = root / "pyproject.toml"
        if pyproject.exists():
            try:
                data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            except (tomllib.TOMLDecodeError, UnicodeDecodeError):
                data = {}
            project = data.get("project")
            if isinstance(project, dict):
                declared = project.get("dependencies")
                if isinstance(declared, list):
                    requirements += [item for item in declared if isinstance(item, str)]

        text_manifest = root / "requirements.txt"
        if text_manifest.exists():
            for line in text_manifest.read_text(encoding="utf-8").splitlines():
                stripped = line.split("#", 1)[0].strip()
                if stripped and not stripped.startswith("-"):
                    requirements.append(stripped)

        return requirements

    def _requirement_name(self, requirement: str) -> str:
        name = requirement
        for delimiter in _VERSION_DELIMITERS:
            name = name.split(delimiter, 1)[0]
        return name.strip().lower().replace("_", "-")

    def matches(self, repo: RepoRef) -> bool:
        return any(self._requirement_name(item) == _SDK_PACKAGE for item in self._requirement_lines(repo))

    def _sdk_version(self, repo: RepoRef) -> str:
        """The version the manifest pins, as written.

        Only the digits are taken. A Python requirement carries a specifier set richer than
        npm's caret -- `>=12.0,<13` and `~=12.0` both appear -- and resolving one to the version
        actually installed needs the environment, which `prepare` deliberately does not build.
        What is recorded is what the project declared, which is what the manifest can support.
        """
        for requirement in self._requirement_lines(repo):
            if self._requirement_name(requirement) != _SDK_PACKAGE:
                continue
            remainder = requirement[len(self._requirement_name(requirement)) :]
            version = remainder.lstrip("=<>!~ ").split(",")[0].strip()
            return version or "unknown"
        return "unknown"

    def _source_files(self, repo: RepoRef) -> list[Path]:
        root = Path(repo.local_path)
        skip = {".venv", "venv", "site-packages", "__pycache__", ".tox", "build", "dist"}
        return [p for p in root.rglob("*.py") if not skip & set(p.parts)]

    # --- clients ------------------------------------------------------------------

    def _client_identifiers(self, repo: RepoRef) -> set[str]:
        """Names that stand for the SDK anywhere in the repository.

        Two idioms, and only the second has a TypeScript analogue. `import stripe` makes the
        module itself the client, so the alias it binds is a root with no construction to find.
        `from stripe import StripeClient` followed by `client = StripeClient(...)` is the
        familiar shape, and is matched the way `typescript.py` matches `new Imported(...)`.

        Names accumulate across the repository rather than per file, which is what lets a client
        built in one module resolve at its call sites in another. It inherits the same limitation
        as the TypeScript version: the match is by name, so a client re-exported under a
        different name is missed, and closing that needs type inference tree-sitter does not
        give us.
        """
        names: set[str] = set()
        parser = _parser()

        for file_path in self._source_files(repo):
            source = file_path.read_bytes()
            tree = parser.parse(source)
            imported: set[str] = set()

            for node in _walk(tree.root_node):
                if node.type == "import_statement":
                    for child in node.named_children:
                        if child.type == "dotted_name" and _text(child, source) == _SDK_PACKAGE:
                            names.add(_SDK_PACKAGE)
                        elif child.type == "aliased_import":
                            original = child.child_by_field_name("name")
                            alias = child.child_by_field_name("alias")
                            if original is not None and alias is not None:
                                if _text(original, source) == _SDK_PACKAGE:
                                    names.add(_text(alias, source))
                elif node.type == "import_from_statement":
                    module = node.child_by_field_name("module_name")
                    if module is None or _text(module, source).split(".")[0] != _SDK_PACKAGE:
                        continue
                    for child in node.named_children:
                        if child is module:
                            continue
                        if child.type == "dotted_name":
                            imported.add(_text(child, source))
                        elif child.type == "aliased_import":
                            alias = child.child_by_field_name("alias")
                            if alias is not None:
                                imported.add(_text(alias, source))

            for node in _walk(tree.root_node):
                if node.type != "assignment":
                    continue
                left = node.child_by_field_name("left")
                right = node.child_by_field_name("right")
                if left is None or right is None or left.type != "identifier":
                    continue
                if right.type != "call":
                    continue
                function = right.child_by_field_name("function")
                if function is not None and _text(function, source) in imported:
                    names.add(_text(left, source))

        return names

    def _attribute_chain(self, node: Node, source: bytes) -> list[str] | None:
        """Flatten `a.b.c` into ['a', 'b', 'c']; return None for anything else."""
        parts: list[str] = []
        current = node
        while current.type == "attribute":
            attribute = current.child_by_field_name("attribute")
            if attribute is None:
                return None
            parts.append(_text(attribute, source))
            current = current.child_by_field_name("object")
            if current is None:
                return None
        if current.type != "identifier":
            return None
        parts.append(_text(current, source))
        return list(reversed(parts))

    # --- arguments ----------------------------------------------------------------

    def _dictionary_paths(self, node: Node, source: bytes, prefix: tuple[str, ...] = ()) -> set[str]:
        """Dotted paths for every key a dict literal declares, at any depth.

        Each key is recorded before descending, which leaves every prefix of a nested path in
        the result -- the shape the detector's comparison assumes, since it asks whether a call
        site's path leads into a change's and needs `metadata` recorded alongside
        `metadata.internal_id`.

        Only string-literal keys are taken. A computed key names no field anyone can compare
        against, and recording the expression that produced it would put customer source into a
        column that holds field names.
        """
        paths: set[str] = set()
        for pair in node.named_children:
            if pair.type != "pair":
                continue
            key = pair.child_by_field_name("key")
            if key is None or key.type != "string":
                continue
            here = (*prefix, _text(key, source).strip("'\"" ))
            paths.add(_path(here))
            value = pair.child_by_field_name("value")
            if value is not None and value.type == "dictionary":
                paths.update(self._dictionary_paths(value, source, here))
        return paths

    def _argument_keys(self, call_node: Node, source: bytes) -> list[str]:
        """The request fields this call names.

        Keyword arguments are Python's form of the object literal `typescript.py` reads, so they
        are the primary source; a dict literal passed positionally is the same thing written the
        other way and is read identically. A `**kwargs` spread names nothing statically and is
        skipped rather than guessed at.
        """
        arguments = call_node.child_by_field_name("arguments")
        if arguments is None:
            return []

        keys: set[str] = set()
        for child in arguments.named_children:
            if child.type == "keyword_argument":
                name = child.child_by_field_name("name")
                if name is None:
                    continue
                here = (_text(name, source),)
                keys.add(_path(here))
                value = child.child_by_field_name("value")
                if value is not None and value.type == "dictionary":
                    keys.update(self._dictionary_paths(value, source, here))
            elif child.type == "dictionary":
                keys.update(self._dictionary_paths(child, source))
        return sorted(keys)

    # --- response fields ----------------------------------------------------------

    def _enclosing_scope(self, node: Node, root: Node) -> Node:
        """The nearest function or lambda ancestor, falling back to the module.

        Same reason as TypeScript: two unrelated calls sharing a generic result name in
        different functions must not merge into one dependency set.
        """
        current = node.parent
        while current is not None:
            if current.type in _FUNCTION_TYPES:
                return current
            current = current.parent
        return root

    def _read_path(self, node: Node, source: bytes, result_name: str) -> str | None:
        """The field path a read expression addresses, or None if it addresses something else.

        Attribute access and string-literal subscripts both continue a path, because a Stripe
        response in Python is dict-like and `result["status"]` is as idiomatic as
        `result.status`. A non-literal subscript ends it: `result["data"][0]` is an index, it
        names no field, and continuing through it would invent a path segment.
        """
        segments: list[str] = []
        current = node

        while True:
            if current.type == "attribute":
                attribute = current.child_by_field_name("attribute")
                if attribute is None:
                    return None
                segments.append(_text(attribute, source))
                current = current.child_by_field_name("object")
            elif current.type == "subscript":
                index = current.child_by_field_name("subscript")
                if index is None or index.type != "string":
                    return None
                segments.append(_text(index, source).strip("'\""))
                current = current.child_by_field_name("value")
            else:
                break
            if current is None:
                return None

        if current.type != "identifier" or _text(current, source) != result_name or not segments:
            return None
        return _path(reversed(segments))

    def _response_fields(self, call_node: Node, source: bytes, root: Node) -> list[str]:
        """Field paths read off the call's result.

        Finds the name the call is assigned to, then collects every read rooted at it inside the
        call's enclosing function. Prefixes land in the result on their own, because
        `result["a"]["b"]` contains `result["a"]` as a node the walk reaches independently --
        which is the same property `typescript.py` relies on and the same one the detector's
        comparison assumes.

        Tuple unpacking has no analogue to TypeScript's destructuring here: Python unpacks
        positionally, so it names no vendor field and there is nothing to record.
        """
        assignment = call_node
        while assignment is not None and assignment.type != "assignment":
            assignment = assignment.parent
        if assignment is None:
            return []
        left = assignment.child_by_field_name("left")
        if left is None or left.type != "identifier":
            return []

        result_name = _text(left, source)
        scope = self._enclosing_scope(call_node, root)

        fields: set[str] = set()
        for node in _walk(scope):
            if node.type not in ("attribute", "subscript"):
                continue
            path = self._read_path(node, source, result_name)
            if path is not None:
                fields.add(path)
        return sorted(fields)

    # --- the protocol -------------------------------------------------------------

    def index(self, repo: RepoRef) -> Iterable[CallSite]:
        clients = self._client_identifiers(repo)
        if not clients:
            return
        sdk_version = self._sdk_version(repo)
        root_path = Path(repo.local_path)
        parser = _parser()

        for file_path in self._source_files(repo):
            source = file_path.read_bytes()
            tree = parser.parse(source)
            relative = file_path.relative_to(root_path).as_posix()

            for node in _walk(tree.root_node):
                if node.type != "call":
                    continue
                function_node = node.child_by_field_name("function")
                if function_node is None or function_node.type != "attribute":
                    continue
                chain = self._attribute_chain(function_node, source)
                if chain is None or len(chain) < 3 or chain[0] not in clients:
                    continue

                symbol = f"{_SDK_PACKAGE}.{'.'.join(chain[1:])}"
                operation = self._vendor.operation_for_symbol(symbol, language=self.language_id)
                if operation is None:
                    continue

                args_keys = self._argument_keys(node, source)
                response_fields = self._response_fields(node, source, tree.root_node)
                content_hash = hashlib.sha256(
                    f"{symbol}|{','.join(args_keys)}|{','.join(response_fields)}".encode()
                ).hexdigest()[:32]

                yield CallSite(
                    repo_id=repo.repo_id,
                    path=relative,
                    line=node.start_point[0] + 1,
                    # A byte column, matching `typescript.py`. The unit is not stated anywhere in
                    # `sync.core`, and the two adapters agreeing on the wrong-ish one is better
                    # than them disagreeing -- see the module notes in the task report.
                    col=node.start_point[1],
                    vendor_id=self._vendor.vendor_id,
                    operation_id=operation.operation_id,
                    symbol=symbol,
                    args_keys=args_keys,
                    response_fields_read=response_fields,
                    sdk_version=sdk_version,
                    content_hash=content_hash,
                )

    def discard_contaminated_dependencies(self, repo: RepoRef) -> bool:
        """Never anything to discard, because `prepare` installs nothing.

        The TypeScript adapter can be handed back a clone whose `node_modules` a patch
        agent doctored, and has to drop it. This adapter never writes an installed tree
        into the clone at all, so there is none to be contaminated.
        """
        return False

    def prepare(self, repo: RepoRef) -> None:
        """Nothing, deliberately.

        TypeScript installs the customer's dependencies because `tsc` cannot resolve an import
        without them, and the install pays for itself by making the gate behind it work. Python
        has no such gate here, so the equivalent would buy nothing -- and it would cost a great
        deal: `pip install` executes arbitrary `setup.py` from every source distribution in the
        dependency tree, and pip has no `--ignore-scripts`. CLAUDE.md's position is that Sync
        runs the customer's toolchain and never their application code, and an install that
        executes third-party build scripts to feed a typechecker that will not run is the wrong
        side of that line.

        A no-op is the honest implementation, not a stub waiting to be filled in. If a later
        milestone runs mypy, this is where the environment for it would be built -- inside a
        virtual environment, which is a decision that needs the sandbox story the threat model
        gates on.
        """
        return None

    def _syntax_errors(self, repo: RepoRef) -> list[str]:
        """Files that do not parse, by path.

        `ast.parse` rather than the tree-sitter grammar: tree-sitter recovers from a syntax
        error and reports a tree, which is what makes it right for indexing a half-written file
        and wrong for answering whether the file is valid Python. The interpreter's own parser
        is the authority on that.
        """
        root = Path(repo.local_path)
        broken: list[str] = []
        for file_path in self._source_files(repo):
            try:
                ast.parse(file_path.read_text(encoding="utf-8"))
            except SyntaxError as exc:
                broken.append(f"{file_path.relative_to(root).as_posix()}: {exc.msg}")
            except UnicodeDecodeError as exc:
                broken.append(f"{file_path.relative_to(root).as_posix()}: {exc}")
        return broken

    def _configured_typechecker(self, repo: RepoRef) -> str | None:
        """The name of a typechecker this project configures, if it configures one."""
        root = Path(repo.local_path)
        pyproject = root / "pyproject.toml"
        if pyproject.exists():
            try:
                data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            except (tomllib.TOMLDecodeError, UnicodeDecodeError):
                data = {}
            tools = data.get("tool")
            if isinstance(tools, dict):
                for name in ("mypy", "pyright", "pyre"):
                    if name in tools:
                        return name
        for candidate in _MYPY_CONFIG_FILES:
            if (root / candidate).exists():
                return "mypy"
        return None

    def static_verify(self, repo: RepoRef, patch: Patch) -> VerifyResult:
        """Fail closed. This adapter cannot verify a Python patch, and says so.

        The verification promise is that nothing reaches a pull request unverified, and it rests
        on `tsc` being present in every TypeScript project. Python has no equivalent. mypy is
        optional, frequently unconfigured, and routinely failing on code that ships happily --
        so a project's silence about typechecking says nothing about whether a patch is safe.

        Three answers were available and two of them are wrong. Returning ok=True would let an
        unverified patch through on the strength of a gate that never ran, which breaks the
        promise outright. Passing on a syntax check alone would be the same thing wearing a
        gate's clothes: a renamed field parses perfectly, and that is precisely the class of
        change this system exists to make. So it returns ok=False, and every Python finding
        abandons here.

        That is a real limitation of extending to this language rather than a placeholder. What
        it costs is exactly the value of the indexing above: call sites, findings and the
        parameter-deprecation join all work in Python, and the remediation half does not.

        The syntax check still runs, because it is the one gate Python does have everywhere and
        a patch that broke the file should be reported as having broken the file -- not as
        Python merely lacking a typechecker, which reads as nothing to see.
        """
        broken = self._syntax_errors(repo)
        if broken:
            return VerifyResult(
                ok=False,
                diagnostics="python syntax error, so the patch cannot be correct:\n" + "\n".join(broken),
            )

        configured = self._configured_typechecker(repo)
        if configured is not None:
            return VerifyResult(
                ok=False,
                diagnostics=(
                    f"this project configures {configured}, and this adapter does not run it. "
                    "The patch parses; nothing has typechecked it, so it is not verified."
                ),
            )
        return VerifyResult(
            ok=False,
            diagnostics=(
                "no typechecker is configured, and Python has no equivalent of tsc present in "
                "every project. The patch parses; nothing has verified it further."
            ),
        )
