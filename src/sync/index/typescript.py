"""TypeScript implementation of the LanguageAdapter protocol.

Resolution happens in three passes over each file:
  1. find the identifier bound to the Stripe SDK (import, then construction)
  2. find member-chain calls rooted at that identifier
  3. for each call, capture the argument keys passed and the response fields read

tree-sitter gives us syntax, not types. Where a client is exported from another
module we resolve it by name across the repository rather than by type inference,
which is sufficient for the single-vendor M0 case and is where the Python type
resolver would be needed for a general solution.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable

import tree_sitter_typescript as tsts
from tree_sitter import Language, Node, Parser

from sync.core import CallSite, Patch, RepoRef, VendorAdapter, VerifyResult

_TS_LANGUAGE = Language(tsts.language_typescript())
_SDK_PACKAGE = "stripe"


def _parser() -> Parser:
    return Parser(_TS_LANGUAGE)


def _text(node: Node, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _walk(node: Node):
    yield node
    for child in node.children:
        yield from _walk(child)


class TypeScriptAdapter:
    language_id = "typescript"

    def __init__(self, vendor_adapter: VendorAdapter) -> None:
        self._vendor = vendor_adapter

    def matches(self, repo: RepoRef) -> bool:
        manifest = Path(repo.local_path) / "package.json"
        if not manifest.exists():
            return False
        data = json.loads(manifest.read_text(encoding="utf-8"))
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        return _SDK_PACKAGE in deps

    def _sdk_version(self, repo: RepoRef) -> str:
        manifest = json.loads((Path(repo.local_path) / "package.json").read_text(encoding="utf-8"))
        deps = {**manifest.get("dependencies", {}), **manifest.get("devDependencies", {})}
        return str(deps.get(_SDK_PACKAGE, "unknown")).lstrip("^~")

    def _source_files(self, repo: RepoRef) -> list[Path]:
        root = Path(repo.local_path)
        return [
            p
            for p in root.rglob("*.ts")
            if "node_modules" not in p.parts and not p.name.endswith(".d.ts")
        ]

    def _client_identifiers(self, repo: RepoRef) -> set[str]:
        """Identifiers bound to a Stripe client anywhere in the repository.

        Two sources: `new <ImportedName>(...)` assigned to a variable, and any
        name re-exported from a module that itself binds a client.
        """
        names: set[str] = set()
        parser = _parser()

        for file_path in self._source_files(repo):
            source = file_path.read_bytes()
            tree = parser.parse(source)
            imported: set[str] = set()

            for node in _walk(tree.root_node):
                if node.type == "import_statement":
                    if f"'{_SDK_PACKAGE}'" not in _text(node, source) and f'"{_SDK_PACKAGE}"' not in _text(node, source):
                        continue
                    for child in _walk(node):
                        if child.type == "identifier":
                            imported.add(_text(child, source))

            for node in _walk(tree.root_node):
                if node.type != "variable_declarator":
                    continue
                name_node = node.child_by_field_name("name")
                value_node = node.child_by_field_name("value")
                if name_node is None or value_node is None:
                    continue
                if value_node.type != "new_expression":
                    continue
                constructor = value_node.child_by_field_name("constructor")
                if constructor is not None and _text(constructor, source) in imported:
                    names.add(_text(name_node, source))

        return names

    def _member_chain(self, node: Node, source: bytes) -> list[str] | None:
        """Flatten `a.b.c` into ['a', 'b', 'c']; return None for anything else."""
        parts: list[str] = []
        current = node
        while current.type == "member_expression":
            prop = current.child_by_field_name("property")
            if prop is None:
                return None
            parts.append(_text(prop, source))
            current = current.child_by_field_name("object")
            if current is None:
                return None
        if current.type != "identifier":
            return None
        parts.append(_text(current, source))
        return list(reversed(parts))

    def _argument_keys(self, call_node: Node, source: bytes) -> list[str]:
        args = call_node.child_by_field_name("arguments")
        if args is None:
            return []
        keys: list[str] = []
        for node in _walk(args):
            if node.type in ("pair", "shorthand_property_identifier"):
                if node.type == "shorthand_property_identifier":
                    keys.append(_text(node, source))
                else:
                    key = node.child_by_field_name("key")
                    if key is not None:
                        keys.append(_text(key, source).strip("'\""))
        return sorted(set(keys))

    def _response_fields(self, call_node: Node, source: bytes, root: Node) -> list[str]:
        """Fields read off the call's result.

        Finds the variable the call is assigned to, then collects every property
        accessed on that variable elsewhere in the file.
        """
        declarator = call_node
        while declarator is not None and declarator.type != "variable_declarator":
            declarator = declarator.parent
        if declarator is None:
            return []
        name_node = declarator.child_by_field_name("name")
        if name_node is None or name_node.type != "identifier":
            return []
        result_name = _text(name_node, source)

        fields: set[str] = set()
        for node in _walk(root):
            if node.type != "member_expression":
                continue
            obj = node.child_by_field_name("object")
            prop = node.child_by_field_name("property")
            if obj is None or prop is None:
                continue
            if obj.type == "identifier" and _text(obj, source) == result_name:
                fields.add(_text(prop, source))
        return sorted(fields)

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
                if node.type != "call_expression":
                    continue
                function_node = node.child_by_field_name("function")
                if function_node is None or function_node.type != "member_expression":
                    continue
                chain = self._member_chain(function_node, source)
                if chain is None or len(chain) < 3 or chain[0] not in clients:
                    continue

                symbol = f"{_SDK_PACKAGE}.{'.'.join(chain[1:])}"
                operation = self._vendor.operation_for_symbol(symbol)
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
                    col=node.start_point[1],
                    vendor_id=self._vendor.vendor_id,
                    operation_id=operation.operation_id,
                    symbol=symbol,
                    args_keys=args_keys,
                    response_fields_read=response_fields,
                    sdk_version=sdk_version,
                    content_hash=content_hash,
                )

    def static_verify(self, repo: RepoRef, patch: Patch) -> VerifyResult:
        raise NotImplementedError("implemented in Task 6")
