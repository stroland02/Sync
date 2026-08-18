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

Four places Python differs, all of them findings about the protocol rather than about the
grammar:

**The module is a client.** `import stripe` then `stripe.charges.create(...)` binds no variable.
The TypeScript rule -- an identifier assigned from `new Imported(...)` -- has nothing to match,
and ported verbatim it indexes nothing in a repository written that way. Here an imported module
alias is a client root in its own right.

**One package name does not serve.** TypeScript's npm name is at once the manifest key, the
import specifier and the root of the symbol. Python separates them: a manifest declares a
*distribution* and source imports a *module*, and the two are different strings in general --
`google-cloud-storage` is imported as `google.cloud.storage`. Both vendors registered today
spell them alike, which is a fact about those vendors and not a rule, so the binding this
module reads carries both rather than one that happens to work twice. The distribution is
normalised the way a requirement is; the module is not, because an import is spelled exactly.

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
import logging
import tomllib
from pathlib import Path
from typing import Iterable, Iterator

import tree_sitter_python as tspython
from tree_sitter import Language, Node, Parser

from sync.core import CallSite, Patch, RepoRef, VendorAdapter, VerifyResult

log = logging.getLogger(__name__)

_PY_LANGUAGE = Language(tspython.language())
_FUNCTION_TYPES = {"function_definition", "lambda"}

# A comprehension is a scope for its `for` target and not for a walrus: PEP 572 binds an
# assignment expression in the scope *containing* the comprehension, which makes it the one
# Python binding that escapes the construct it is written in. `typescript.py` has exactly one of
# those too -- `var`, which hoists out of its block to the enclosing function.
_COMPREHENSION_TYPES = {
    "list_comprehension",
    "set_comprehension",
    "dictionary_comprehension",
    "generator_expression",
}

# Every node that opens a scope of its own, which is what a name can be rebound in without the
# rebinding reaching the code around it. Python has no block scope, so an `if`, `for`, `while`,
# `with` or `try` body is deliberately absent: a name bound in one of those belongs to the
# enclosing function and shadows nothing. `typescript.py` carries a wider list for the opposite
# reason.
_SCOPE_TYPES = _FUNCTION_TYPES | {"class_definition"} | _COMPREHENSION_TYPES

# Nodes that give a name a binding in the scope holding them, as the field carrying the target.
# `augmented_assignment` belongs here and is not a read: `charge += 1` makes `charge` local to
# the whole of the function containing it, so a read above the line raises `UnboundLocalError`.
_REBINDING_FIELDS = {
    "assignment": "left",
    "augmented_assignment": "left",
    "named_expression": "name",
    "for_statement": "left",
    "for_in_clause": "left",
    "as_pattern": "alias",
}

# Nodes whose name is bound in the scope that *holds* them rather than inside them. Both are
# also scopes, so the walk that looks for a rebinding reads the name and then stops.
_DECLARATION_FIELDS = {
    "function_definition": "name",
    "class_definition": "name",
}

# Patterns a binding target may be spelled as, and every one of them may nest. An `attribute`
# or `subscript` target is deliberately absent -- `self.charge = ...` and `rows["charge"] = ...`
# name something other than a local, so neither shadows one.
_PATTERN_TYPES = {
    "pattern_list",
    "tuple_pattern",
    "list_pattern",
    "list_splat_pattern",
    "dictionary_splat_pattern",
    "parameters",
    "lambda_parameters",
    "as_pattern_target",
}
# Where a project may declare that it depends on the SDK. Both are current practice, and reading
# only one reports half the ecosystem as not using it.
_MANIFESTS = ("pyproject.toml", "requirements.txt")
# Files naming a typechecker this adapter does not run. Their presence changes what
# `static_verify` can honestly say, not what it returns.
_MYPY_CONFIG_FILES = ("mypy.ini", ".mypy.ini", "setup.cfg")

# How a customer's manifest is decoded, and the one place in this module that is not plain
# `utf-8`. A byte-order mark is valid UTF-8, so it does not fail to decode -- it arrives as a
# `\ufeff` first character, and what happens next depends only on who reads it. `tomllib` calls it
# an invalid statement; `requirements.txt` is split into lines rather than parsed, so it silently
# becomes part of the first requirement's name and the whole repository reads as not depending on
# the SDK with nothing raised anywhere. `utf-8-sig` strips a leading mark and is otherwise
# identical, including still raising `UnicodeDecodeError` on bytes that are not UTF-8 at all --
# so the guards around these reads still do their work and a UTF-16 manifest is still refused
# rather than decoded into mojibake.
#
# Manifests only, and customer *source* is not read as text at all -- `_syntax_errors` hands
# `ast.parse` the bytes and lets the tokenizer decide, because a `.py` file may declare its own
# encoding and may begin with a mark, and both are the interpreter's business rather than this
# module's. A manifest cannot declare anything, which is why it needs an answer chosen here.
_MANIFEST_ENCODING = "utf-8-sig"
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

    Strict, which is what `signals.generated.symbols_typescript._text` has always been over a
    vendor's SDK. This copy read the customer's repository with `errors="replace"`, which is the
    same class of defect one line further on: a PEP 263 cp1252 module produced `args_keys` holding
    `meta.co<U+FFFD>t` and a `response_fields_read` of `st` for a field spelled with an
    a-circumflex. The first is a key nobody wrote and the second is a plausible field name on a
    call site that never read it.

    Reaching this with bytes that do not decode is a caller that skipped `_readable_sources`, so
    it raises rather than repairing.
    """
    return source[node.start_byte : node.end_byte].decode("utf-8")


def _walk(node: Node):
    yield node
    for child in node.children:
        yield from _walk(child)


def _path(segments: Iterable[str]) -> str:
    return ".".join(segments)


def _same(left: Node | None, right: Node | None) -> bool:
    """Whether two handles address one node. tree-sitter returns a fresh object per access, so
    identity is the span rather than the reference."""
    if left is None or right is None:
        return False
    return left.start_byte == right.start_byte and left.end_byte == right.end_byte


def _pattern_names(node: Node, source: bytes) -> Iterator[str]:
    """Every name a binding target introduces, through whatever pattern spells it.

    A parameter list, a tuple unpacking and a `*rest` all bind more than one name or bind one
    at a depth, and a target that names an attribute or a subscript binds none.
    """
    if node.type == "identifier":
        yield _text(node, source)
    elif node.type in ("default_parameter", "typed_default_parameter"):
        name = node.child_by_field_name("name")
        if name is not None:
            yield from _pattern_names(name, source)
    elif node.type == "typed_parameter":
        # The annotation is a sibling of the name rather than a field of it, so it has to be
        # stepped over by type -- `charge: Charge` would otherwise bind `Charge` as well.
        for child in node.named_children:
            if child.type != "type":
                yield from _pattern_names(child, source)
    elif node.type in _PATTERN_TYPES:
        for child in node.named_children:
            yield from _pattern_names(child, source)


def _escaping_walrus(node: Node, source: bytes, name: str) -> bool:
    """Whether `node` holds a `:=` binding `name` in the scope around the comprehension.

    `[(charge := row) for row in rows]` makes `charge` local to the function holding the
    comprehension, exactly as a plain assignment there would, so a read above the line raises
    `UnboundLocalError` and cannot be of an outer object. A `lambda` inside the comprehension is
    still a wall -- a walrus written in one binds there -- and it is the only scope a
    comprehension can contain, the rest being statements.
    """
    if node.type == "lambda":
        return False
    if node.type == "named_expression":
        target = node.child_by_field_name("name")
        if target is not None and _text(target, source) == name:
            return True
    return any(_escaping_walrus(child, source, name) for child in node.children)


def _holds_binding(node: Node, source: bytes, name: str) -> bool:
    """Whether `node` binds `name` in the scope holding it, at any depth short of a new scope.

    A nested scope is read for the name it declares and then not entered: what it binds inside
    itself is its own, which is the whole distinction this walk exists to make. A comprehension
    is entered for one thing only, because one Python binding written inside it is not its own.
    """
    declared = _DECLARATION_FIELDS.get(node.type)
    if declared is not None:
        target = node.child_by_field_name(declared)
        if target is not None and _text(target, source) == name:
            return True
    if node.type in _SCOPE_TYPES:
        return node.type in _COMPREHENSION_TYPES and _escaping_walrus(node, source, name)
    field = _REBINDING_FIELDS.get(node.type)
    if field is not None:
        target = node.child_by_field_name(field)
        if target is not None and name in _pattern_names(target, source):
            return True
    return any(_holds_binding(child, source, name) for child in node.children)


def _scope_body(scope: Node) -> Node:
    """The node whose children are the scope's own statements.

    A function and a class hold theirs in a `block`; a lambda and a comprehension hold theirs
    directly, so the scope node stands in for itself.
    """
    body = scope.child_by_field_name("body")
    return body if body is not None and body.type == "block" else scope


def _rebinds(scope: Node, source: bytes, name: str) -> bool:
    """Whether `scope` gives `name` a binding of its own.

    Its parameters first, because a parameter is the one binding a scope carries outside its
    body, then everything the body holds.
    """
    parameters = scope.child_by_field_name("parameters")
    if parameters is not None and name in _pattern_names(parameters, source):
        return True
    return any(
        _holds_binding(child, source, name) for child in _scope_body(scope).children
    )


def _unshadowed(scope: Node, source: bytes, name: str, call_node: Node) -> Iterator[Node]:
    """`scope` and everything under it where `name` still means what `scope` bound it to.

    A nested scope that rebinds the name is skipped whole rather than searched for the reads
    above the rebinding. Python binds a name for the entire scope that assigns it anywhere, so
    a read on the line above raises `UnboundLocalError` rather than reaching the outer object,
    and recording it would be a false field on a read that cannot be of this call's result.

    A scope containing the call is never skipped. The binding this walk follows is declared
    inside one of them, and a class body is the case that shows it: an indexed call in a class
    body is scoped to the module, so the class is nested inside the scope being walked and does
    bind the name -- its own.
    """
    yield scope
    for child in scope.children:
        if (
            child.type in _SCOPE_TYPES
            and not (
                child.start_byte <= call_node.start_byte
                and call_node.end_byte <= child.end_byte
            )
            and _rebinds(child, source, name)
        ):
            continue
        yield from _unshadowed(child, source, name, call_node)


# Expressions a call's result passes through while still being what a name receives, and there
# are exactly two. TypeScript's list also carries `as`, `satisfies`, a non-null assertion and a
# type assertion, none of which Python has.
#
# What Python has instead is deliberately absent. A `boolean_operator` (`create(...) or {}`) and
# a `conditional_expression` (`create(...) if flag else other`) each choose between two values
# and only one of them is the call's; a `list` or other collection literal binds a container
# rather than the response; an `argument_list` means another call received the result and its
# own return value is what the name gets.
_RESULT_WRAPPERS = {"await", "parenthesized_expression"}

# How many leading segments of a call chain may name the client. One for `client.charges.create`
# and two for `self.client.charges.create`; nothing here binds a deeper root, because the only
# two-segment form is `self.<attribute>` and a third segment would have to be an object this
# walk cannot follow to its own construction.
_MAX_CLIENT_SEGMENTS = 2

# Nodes that bind a value to a name, as the field holding the name and the field holding the
# value. Both are checked the same way -- the name receives this call only when the value field
# *is* this call -- which is what keeps `dict(create(...))` uncredited in either spelling.
#
# The walrus belongs here and not in `_RESULT_WRAPPERS`, and the distinction is the whole of this
# rule rather than a detail of it. A wrapper is something the result passes *through* on its way
# to a name somewhere further up; `named_expression` is where the name already is. Listed as a
# wrapper it would change nothing at all -- the walk would step over it, reach the
# `parenthesized_expression` and then the `if_statement` that PEP 572's motivating form puts
# above it, find no binder there and answer None. That was measured rather than reasoned about:
# adding it to the wrapper set leaves all four recall tests red exactly as they were.
_BINDING_FORMS = {
    "assignment": ("left", "right"),
    "named_expression": ("name", "value"),
}


def _normalised(distribution: str) -> str:
    """A distribution name as PEP 503 compares it.

    Applied to both sides so `Twilio`, `twilio` and a hypothetical `twi_lio` in a manifest all
    meet the name an adapter declared. Only the distribution is normalised; a module name is
    spelled exactly as it is imported.
    """
    return distribution.strip().lower().replace("_", "-")


class PythonAdapter:
    language_id = "python"

    unverifiable_reason = (
        "Python has no equivalent of tsc present in every project, so no patch to this "
        "repository can be verified and none is attempted"
    )
    """Why `static_verify` fails closed, stated where a router can read it before a run starts.

    The verdict was always knowable in advance and was previously discovered the expensive way:
    a finding reached `patch`, spent an agent run, failed verification, retried, spent another,
    and abandoned. `route_after_prepare` reads this and reports instead, which is the same
    mechanism tier -1 uses for a change no edit resolves.

    An adapter that does not declare this is taken to verify. That keeps every existing adapter
    unchanged and needs no widening of the `LanguageAdapter` protocol, which this module does
    not own -- and the default is the safe direction, because an adapter wrongly assumed to
    verify still meets a real gate at `static_verify`, while one wrongly assumed not to would
    silently stop repairing a language Sync can repair.
    """

    def __init__(self, vendor_adapter: VendorAdapter) -> None:
        self._vendor = vendor_adapter
        # What this vendor is declared as and what it is imported as. `getattr` rather than a
        # protocol member for the same reason `unverifiable_reason` is read that way: this
        # module does not own `VendorAdapter`, and an adapter declaring nothing keeps working.
        # Declaring nothing means no repository matches and no call site resolves, which is the
        # honest answer for a vendor whose specification is discoverable and whose SDK nothing
        # here can recognise -- and it is the answer a default would replace with a wrong one.
        binding = getattr(vendor_adapter, "sdk_bindings", {}).get(self.language_id, {})
        declared = binding.get("distribution")
        self._distribution: str | None = (
            _normalised(declared) if isinstance(declared, str) else None
        )
        self._module: str | None = binding.get("module")
        # What an emitted symbol is rooted at. Defaults to the module rather than to the
        # distribution, and that default is the reason this side never carried TypeScript's
        # defect: a distribution is not importable -- PEP 503 folds `_` to `-` in a requirement
        # and never in an `import` -- so rooting at it would put `slack-sdk` into a symbol,
        # which is exactly the failure being fixed on the other side. Defaulting here to the
        # package would have introduced the defect rather than removed it.
        #
        # A module name and a symbol root are still different strings in general, so the field
        # earns its place here too: a map keying on `slack` is unreachable from a module named
        # `slack_sdk` without it. A binding that declares this language and omits the root gets
        # the module, and does not acquire a guess from elsewhere.
        self._symbol_root: str | None = binding.get("symbol_root") or self._module
        # Which files this clone holds that are not UTF-8, so two passes over one of them report
        # it once. `_readable_sources` carries why they are skipped at all.
        self._undecodable: set[Path] = set()
        self._importing_paths: set[Path] = set()
        self._bound_paths: set[Path] = set()

    # --- manifests ----------------------------------------------------------------

    def _read_manifests(self, repo: RepoRef) -> tuple[list[str], list[str]]:
        """Every dependency this project declares, and every manifest that would not be read.

        A customer's manifest is untrusted input, so an unreadable one answers "declares
        nothing" rather than raising: the caller already has a path for a repository that does
        not demonstrably depend on the SDK, and a `TOMLDecodeError` out of `run()` is a
        traceback where that answer belongs.

        Unreadable has two spellings and both files can be either. A manifest that does not
        parse is the obvious one; a manifest that does not decode is the one found in the wild,
        because a `requirements.txt` beginning `ff fe` is a UTF-16 file and every text call here
        reads UTF-8. Neither is decoded leniently: `errors="replace"` would turn that file into
        requirement strings nothing in it declares, which is worse than the traceback it
        replaces.

        Which files failed is returned rather than swallowed, because a repository whose manifest
        does not decode is not a repository with no dependencies, and answered as the latter it
        costs adapter selection with nothing said. `decline_reason` is what says it, and
        `sync.signals.intake` keeps the same two channels for the same reason. One list rather
        than one reason, because either file can fail independently of the other.
        """
        root = Path(repo.local_path)
        requirements: list[str] = []
        unreadable: list[str] = []

        pyproject = root / "pyproject.toml"
        if pyproject.exists():
            try:
                data = tomllib.loads(pyproject.read_text(encoding=_MANIFEST_ENCODING))
            except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
                unreadable.append(f"pyproject.toml could not be read: {exc}")
                data = {}
            project = data.get("project")
            if isinstance(project, dict):
                declared = project.get("dependencies")
                if isinstance(declared, list):
                    requirements += [item for item in declared if isinstance(item, str)]

        text_manifest = root / "requirements.txt"
        if text_manifest.exists():
            try:
                declared_lines = text_manifest.read_text(encoding=_MANIFEST_ENCODING).splitlines()
            except UnicodeDecodeError as exc:
                unreadable.append(f"requirements.txt could not be read: {exc}")
                declared_lines = []
            for line in declared_lines:
                stripped = line.split("#", 1)[0].strip()
                if stripped and not stripped.startswith("-"):
                    requirements.append(stripped)

        return requirements, unreadable

    def _requirement_lines(self, repo: RepoRef) -> list[str]:
        return self._read_manifests(repo)[0]

    def _requirement_name(self, requirement: str) -> str:
        name = requirement
        for delimiter in _VERSION_DELIMITERS:
            name = name.split(delimiter, 1)[0]
        return _normalised(name)

    def matches(self, repo: RepoRef) -> bool:
        if self._distribution is None:
            return False
        return any(
            self._requirement_name(item) == self._distribution
            for item in self._requirement_lines(repo)
        )

    def decline_reason(self, repo: RepoRef) -> str:
        """Why this indexer did not claim the repository, in the terms whoever reads it can act
        on.

        The same four situations `TypeScriptAdapter.decline_reason` separates, and the
        distribution is named in the last of them: a Python requirement is compared under PEP
        503, so what was looked for is the folded spelling and not necessarily the one anybody
        wrote down.
        """
        if self._distribution is None:
            return (
                f"vendor '{self._vendor.vendor_id}' declares no {self.language_id} "
                f"distribution, so no manifest could match it -- the absent configuration is "
                f"sdk_bindings, not anything in this repository"
            )

        requirements, unreadable = self._read_manifests(repo)
        if unreadable:
            return f"{'; '.join(unreadable)}, so what this repository declares is unknown"
        if not requirements:
            return "no pyproject.toml or requirements.txt in this repository declares a dependency"
        count = len(requirements)
        return (
            f"pyproject.toml and requirements.txt declare {count} "
            f"{'requirement' if count == 1 else 'requirements'} between them and "
            f"'{self._distribution}' is not one of them"
        )

    def _sdk_version(self, repo: RepoRef) -> str:
        """The version the manifest pins, as written.

        Only the digits are taken. A Python requirement carries a specifier set richer than
        npm's caret -- `>=12.0,<13` and `~=12.0` both appear -- and resolving one to the version
        actually installed needs the environment, which `prepare` deliberately does not build.
        What is recorded is what the project declared, which is what the manifest can support.
        """
        for requirement in self._requirement_lines(repo):
            if self._requirement_name(requirement) != self._distribution:
                continue
            remainder = requirement[len(self._requirement_name(requirement)) :]
            version = remainder.lstrip("=<>!~ ").split(",")[0].strip()
            return version or "unknown"
        return "unknown"

    def _source_files(self, repo: RepoRef) -> list[Path]:
        root = Path(repo.local_path)
        skip = {".venv", "venv", "site-packages", "__pycache__", ".tox", "build", "dist", ".git", ".cache"}
        return [
            p for p in root.rglob("*.py")
            if p.is_file() and not (skip & set(p.relative_to(root).parts[:-1]))
        ]

    def _readable_sources(self, repo: RepoRef) -> Iterator[tuple[Path, bytes]]:
        """Every source file that is UTF-8, with its bytes, naming the ones that are not.

        The gate both indexing passes read through, so a file the client pass skipped cannot be
        walked by the call pass. tree-sitter takes bytes and reports byte offsets, so the bytes are
        what is yielded and the decode is checked rather than kept.

        Skipped rather than decoded leniently, which is `benchmark.read_checkout`'s rule applied
        where a customer's scan actually reads: "`errors="replace"` would hand the indexer a file
        full of replacement characters, which is still a file it will parse". PEP 263 makes this a
        real category rather than a theoretical one -- a module declaring `coding: cp1252` is a file
        the interpreter runs and this walk must not corrupt.

        `_syntax_errors` deliberately does not read through here. It answers a different question
        -- whether a patch to this repository can be verified -- and an undecodable file is a
        reason it cannot, so that pass keeps reading every path and keeps reporting the ones that
        do not decode. Filtering them out of both would let `static_verify` pass a repository over
        a file it never looked at.
        """
        root = Path(repo.local_path)
        for file_path in self._source_files(repo):
            source = file_path.read_bytes()
            try:
                source.decode("utf-8")
            except UnicodeDecodeError as exc:
                if file_path not in self._undecodable:
                    self._undecodable.add(file_path)
                    log.warning(
                        "%s is not valid UTF-8, so it is not indexed and its call sites are "
                        "absent from this scan (%s)",
                        file_path.relative_to(root).as_posix(), exc,
                    )
                continue
            yield file_path, source

    def unread_paths(self, repo: RepoRef) -> list[str]:
        """The source paths this scan skipped because they are not UTF-8, repository-relative.

        Read by `sync.cli` after `index`, and empty before it: `_readable_sources` records as the
        walk reaches each file, so asking first reports nothing on a scan that skipped plenty.

        This exists because the warning above is not a coverage figure. It names a file without
        saying how much of the repository was missed, which is the distinction B60 drew for the
        literal pass -- and this is the pass that skips most, since it walks every source file
        where that one walks `*.ts` alone.

        Not on the `LanguageAdapter` protocol, and read with `getattr` for the reason
        `unverifiable_reason` and `sdk_bindings` are: this is a boundary neither this module nor
        `sync.cli` owns, and a third party's adapter that reports nothing has to scan rather than
        crash.
        """
        root = Path(repo.local_path)
        return sorted(path.relative_to(root).as_posix() for path in self._undecodable)

    def unbound_import_paths(self, repo: RepoRef) -> list[str]:
        """Source paths that imported the vendor SDK module but produced no bound call sites.

        Repository-relative paths. Identifies wrapper files or re-exports where the vendor SDK
        is imported but call sites sit behind abstractions that the single-file static AST indexer
        cannot resolve.
        """
        root = Path(repo.local_path)
        return sorted(
            path.relative_to(root).as_posix()
            for path in (self._importing_paths - self._bound_paths)
        )

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
        if self._module is None:
            return names
        parser = _parser()

        for file_path, source in self._readable_sources(repo):
            tree = parser.parse(source)
            imported: set[str] = set()
            # Names bound to the vendor's module in this file, kept apart from `names` because
            # only these may stand to the left of a constructor. `names` also accumulates client
            # variables, and allowing one of those as the object would make every call on a
            # client a candidate constructor for another.
            modules: set[str] = set()

            for node in _walk(tree.root_node):
                if node.type == "import_statement":
                    for child in node.named_children:
                        if child.type == "dotted_name" and _text(child, source) == self._module:
                            self._importing_paths.add(file_path)
                            names.add(self._module)
                            modules.add(self._module)
                        elif child.type == "aliased_import":
                            original = child.child_by_field_name("name")
                            alias = child.child_by_field_name("alias")
                            if original is not None and alias is not None:
                                if _text(original, source) == self._module:
                                    self._importing_paths.add(file_path)
                                    names.add(_text(alias, source))
                                    modules.add(_text(alias, source))
                elif node.type == "import_from_statement":
                    module = node.child_by_field_name("module_name")
                    if module is None or _text(module, source).split(".")[0] != self._module:
                        continue
                    self._importing_paths.add(file_path)
                    for child in node.named_children:
                        if _same(child, module):
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
                if left is None or right is None or right.type != "call":
                    continue
                if not self._constructs_client(right, source, imported, modules):
                    continue
                bound = self._bound_name(left, source)
                if bound is not None:
                    names.add(bound)

        return names

    def _constructs_client(self, call: Node, source: bytes, imported: set[str],
                           modules: set[str]) -> bool:
        """Whether this call builds the vendor's client.

        Two spellings and the second is the one Stripe's own documentation uses.
        `StripeClient(...)` names something imported from the vendor's module, which is the form
        that already worked. `stripe.StripeClient(...)` reaches the same class through the module,
        and bound nothing -- one rule away, and worth eleven of the seventeen repositories the
        coverage measurement indexed.

        **The object is what is checked, never the attribute.** `notstripe.StripeClient(...)`
        spells the vendor's class name on somebody else's module, and matching the attribute
        would bind it: every call on that object would then be attributed to a vendor it never
        reached, which is a false attribution introduced at the binding step rather than at the
        field step and is worse there -- a wrongly bound call site produces findings against code
        that never called the vendor at all.
        """
        function = call.child_by_field_name("function")
        if function is None:
            return False
        if function.type == "identifier":
            return _text(function, source) in imported
        if function.type == "attribute":
            obj = function.child_by_field_name("object")
            return obj is not None and obj.type == "identifier" and _text(obj, source) in modules
        return False

    def _bound_name(self, left: Node, source: bytes) -> str | None:
        """The client root an assignment target introduces, dotted where it has to be.

        A plain name is one segment. `self.client = ...` is two, and it is recorded as the whole
        `self.client` rather than as `client`: the call sites that use it are written
        `self.client.charges.create(...)`, so the root has to match what the chain actually
        spells. Recording the attribute alone would also bind every unrelated `client.x.y()` in
        the repository, which is the loose rule this module must not acquire.

        Only `self`. An attribute of anything else -- `config.client = ...` -- names an object
        this walk cannot follow to its call sites, and a rule matching any attribute target would
        bind on the attribute name alone.
        """
        if left.type == "identifier":
            return _text(left, source)
        if left.type != "attribute":
            return None
        obj = left.child_by_field_name("object")
        attribute = left.child_by_field_name("attribute")
        if obj is None or attribute is None or obj.type != "identifier":
            return None
        if _text(obj, source) != "self":
            return None
        return f"self.{_text(attribute, source)}"

    def _after_client(self, chain: list[str], clients: set[str]) -> list[str] | None:
        """What a call chain says once its client root is taken off, or None if it has none.

        A root is one segment for `client.charges.create` and two for
        `self.client.charges.create`, so the match is over prefixes rather than over `chain[0]`.
        The longest is taken first: a repository binding both `client` and `self.client` must
        read the second as the client it is, not as the first followed by an attribute nobody
        named.

        At least two segments have to survive. One is a call on the client itself rather than on
        a resource -- `client.close()` names no operation -- and this is the same floor the
        single-segment root enforced as `len(chain) < 3`.
        """
        for size in range(min(len(chain) - 2, _MAX_CLIENT_SEGMENTS), 0, -1):
            if ".".join(chain[:size]) in clients:
                return chain[size:]
        return None

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

        The fallback answers for more than a module-level call. A class body holds no ancestor
        in `_FUNCTION_TYPES` either, so a call in one is scoped to the whole module rather than
        to the class -- which is why `_response_fields` has to know that a class body is a scope
        a name can be rebound in, and not only that a function is.
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

    def _result_target(self, call_node: Node) -> Node | None:
        """The name this call's result is bound to, or None if the name receives something else.

        One binding form, which is the whole difference from `typescript.py`. Python has no
        declaration-versus-assignment split -- `charge = ...` is an `assignment` and so is
        `charge: Charge = ...`, the annotation being a field on the same node -- so the shape
        that was blind there is the shape here, and it always worked.

        What did not work is the check that the call is what the name receives.
        `charge = dict(client.charges.create(...))` binds `dict`'s return value, and the fields
        read off it were credited to the Stripe call: a claim of dependency on response fields
        the vendor need not carry, which is the direction that costs a reviewer's trust rather
        than an incident.

        `augmented_assignment` is deliberately not matched. `charge += client.charges.create(...)`
        binds the concatenation and never the response, and it is a different node kind, so it
        answers None here by falling off the wrapper set rather than by a rule of its own.

        Two binding forms now, not one. `charge := client.charges.create(...)` binds the call's
        own result as surely as `=` does, and until B35 it recorded nothing -- so a response-side
        change could not be detected against any call site written that way, which is the missed
        break B33 fixed on the TypeScript side. The walrus is checked by the identical rule and
        not by a looser one: the name receives this call only when the walrus's `value` *is* this
        call, so `charge := dict(client.charges.create(...))` still answers None, for the same
        reason and at the same point in the walk as its `=` spelling.
        """
        current = call_node
        parent = current.parent
        while parent is not None:
            binding = _BINDING_FORMS.get(parent.type)
            if binding is not None:
                target, value = binding
                bound = parent.child_by_field_name(value)
                return parent.child_by_field_name(target) if _same(bound, current) else None
            if parent.type not in _RESULT_WRAPPERS:
                return None
            current, parent = parent, parent.parent
        return None

    def _response_fields(self, call_node: Node, source: bytes, root: Node) -> list[str]:
        """Field paths read off the call's result.

        Finds the name the call is assigned to, then collects every read rooted at it inside the
        call's enclosing function -- minus every nested scope that gives the same name a binding
        of its own, which reads something else through it. Prefixes land in the result on their
        own, because `result["a"]["b"]` contains `result["a"]` as a node the walk reaches
        independently -- which is the same property `typescript.py` relies on and the same one
        the detector's comparison assumes.

        A nested scope that only *reads* the name still contributes. That is the closure it is,
        and the field it reads is genuinely this call's; dropping it would trade a false field
        for a missed break, which is the more expensive of the two and the silent one.

        What no scope rule can reach is a rebinding in the scope the call is in --
        `charge = create(...)` followed later by `charge = retrieve(...)` at the same level.
        Which read belongs to which call is a question about order rather than about scope, and
        both calls still collect both reads.

        Tuple unpacking has no analogue to TypeScript's destructuring here: Python unpacks
        positionally, so it names no vendor field and there is nothing to record.
        """
        left = self._result_target(call_node)
        if left is None or left.type != "identifier":
            return []

        result_name = _text(left, source)
        scope = self._enclosing_scope(call_node, root)

        fields: set[str] = set()
        for node in _unshadowed(scope, source, result_name, call_node):
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

        for file_path, source in self._readable_sources(repo):
            tree = parser.parse(source)
            relative = file_path.relative_to(root_path).as_posix()

            for node in _walk(tree.root_node):
                if node.type != "call":
                    continue
                function_node = node.child_by_field_name("function")
                if function_node is None or function_node.type != "attribute":
                    continue
                chain = self._attribute_chain(function_node, source)
                if chain is None:
                    continue
                rest = self._after_client(chain, clients)
                if rest is None:
                    continue

                symbol = f"{self._symbol_root}.{'.'.join(rest)}"
                operation = self._vendor.operation_for_symbol(symbol, language=self.language_id)
                if operation is None:
                    continue

                args_keys = self._argument_keys(node, source)
                response_fields = self._response_fields(node, source, tree.root_node)
                content_hash = hashlib.sha256(
                    f"{symbol}|{','.join(args_keys)}|{','.join(response_fields)}".encode()
                ).hexdigest()[:32]

                self._bound_paths.add(file_path)
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

        **Bytes, and that is the whole of deferring to it.** Deciding a file's encoding is part
        of parsing Python, not something to settle first and hand over the result: the tokenizer
        strips a byte-order mark and honours a PEP 263 `coding:` declaration. Reading the file as
        text with an encoding chosen here bypassed exactly the part of the interpreter this gate
        claims to defer to, and it called two kinds of compilable file broken -- a `.py` beginning
        with a mark, as `invalid non-printable character U+FEFF`, and a file declaring `latin-1`
        and written in it, as a decode failure. Measured against `py_compile` over seven files:
        bytes agrees with it on all seven, a `utf-8` read disagrees on two.

        A file that genuinely cannot be read is still reported, which is the half that must not
        move: undeclared non-UTF-8 bytes and a UTF-16 file are both rejected by CPython and both
        are rejected here.
        """
        root = Path(repo.local_path)
        broken: list[str] = []
        for file_path in self._source_files(repo):
            relative = file_path.relative_to(root).as_posix()
            try:
                ast.parse(file_path.read_bytes())
            except SyntaxError as exc:
                broken.append(f"{relative}: {exc.msg}")
            except ValueError as exc:
                # Not every unparseable file is a `SyntaxError` once the source is bytes. A
                # UTF-16 file raises `ValueError: source code string cannot contain null bytes`
                # from before the tokenizer, and uncaught that leaves the gate as a traceback
                # rather than a verdict -- the failure `matches` had against the same file twice.
                # `UnicodeDecodeError` is a `ValueError` too, so nothing needs its own clause.
                broken.append(f"{relative}: {exc}")
        return broken

    def _configured_typechecker(self, repo: RepoRef) -> str | None:
        """The name of a typechecker this project configures, if it configures one."""
        root = Path(repo.local_path)
        pyproject = root / "pyproject.toml"
        if pyproject.exists():
            try:
                data = tomllib.loads(pyproject.read_text(encoding=_MANIFEST_ENCODING))
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
