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
import subprocess
import time
from pathlib import Path
from typing import Iterable

import tree_sitter_typescript as tsts
from tree_sitter import Language, Node, Parser

from sync.core import CallSite, Patch, RepoRef, VendorAdapter, VerifyResult

_TS_LANGUAGE = Language(tsts.language_typescript())
_SDK_PACKAGE = "stripe"
_FUNCTION_TYPES = {
    "function_declaration",
    "function_expression",
    "generator_function",
    "generator_function_declaration",
    "arrow_function",
    "method_definition",
}


def _parser() -> Parser:
    return Parser(_TS_LANGUAGE)


def _text(node: Node, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _walk(node: Node):
    yield node
    for child in node.children:
        yield from _walk(child)


def _path(segments: Iterable[str]) -> str:
    return ".".join(segments)


class TypeScriptAdapter:
    language_id = "typescript"

    def __init__(self, vendor_adapter: VendorAdapter) -> None:
        self._vendor = vendor_adapter
        # What each clone already failed before Sync touched it, keyed by clone
        # path. Held in memory rather than in the clone because nothing has to
        # read it after this process ends: `cli.RESUMABLE_NODES` resumes a run
        # only at `await_ci` or `open_pr`, and anything interrupted earlier
        # starts from `locate`, which reaches `prepare` again.
        self._baselines: dict[Path, list] = {}
        # When each clone's dependencies were last installed. Everything under
        # `node_modules` was written by that install, so a later mtime is
        # something else's work -- see `sync.index.dependency_edits`.
        self._installed_at: dict[Path, int] = {}

    def _declared_dependencies(self, repo: RepoRef) -> dict[str, object]:
        """The SDK versions `package.json` declares, or nothing it can be read from.

        A customer's manifest is untrusted input, so an unparseable one answers
        "no declared dependency" rather than raising: the caller already has a
        path for a repository that does not demonstrably depend on the SDK, and
        a `JSONDecodeError` out of `run()` is a traceback where that answer
        belongs.
        """
        manifest = Path(repo.local_path) / "package.json"
        if not manifest.exists():
            return {}
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        if not isinstance(data, dict):
            return {}
        return {**data.get("dependencies", {}), **data.get("devDependencies", {})}

    def matches(self, repo: RepoRef) -> bool:
        return _SDK_PACKAGE in self._declared_dependencies(repo)

    def _sdk_version(self, repo: RepoRef) -> str:
        deps = self._declared_dependencies(repo)
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

        The one rule: `new <ImportedName>(...)` assigned to a variable, where
        `<ImportedName>` was imported from the `stripe` package in that same
        file. Names accumulate into a single set across every file in the
        repository, rather than being scoped per file — that repo-wide set is
        what lets a client built in one module (`export const stripe = new
        Stripe(...)`) resolve at its call sites in another (`import { stripe }
        from './client'`): both files use the identifier `stripe`, so the
        second file's occurrences land in the set the first file populated.
        There is no separate re-export rule; it is this name-matching that
        does it.

        Because it is matching by name and not tracing the import, a
        *renamed* re-export is missed: `import { stripe as billingClient }
        from './client'` binds the name `billingClient`, which the file that
        declared the client never added to the set, so
        `billingClient.charges.create(...)` is silently not indexed. Closing
        that gap would need the type inference tree-sitter doesn't give us —
        accepted as a known limitation for single-vendor M0.
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

    def _object_paths(self, obj: Node, source: bytes, prefix: tuple[str, ...] = ()) -> set[str]:
        """Dotted paths for every key an object literal declares, at any depth.

        Recording each key before descending is what leaves every prefix of a
        nested path in the result, which is the shape the detector's comparison
        assumes: it checks whether a call site's path leads into a change's, and
        needs no second direction as long as `metadata` is recorded alongside
        `metadata.internal_id`.

        An object literal buried in a second, callback, argument is still out of
        reach — only the tree under the object handed in is walked.
        """
        paths: set[str] = set()
        for node in obj.named_children:
            if node.type == "shorthand_property_identifier":
                paths.add(_path([*prefix, _text(node, source)]))
            elif node.type == "pair":
                key = node.child_by_field_name("key")
                if key is None:
                    continue
                here = (*prefix, _text(key, source).strip("'\""))
                paths.add(_path(here))
                value = node.child_by_field_name("value")
                if value is not None and value.type == "object":
                    paths.update(self._object_paths(value, source, here))
        return paths

    def _argument_keys(self, call_node: Node, source: bytes) -> list[str]:
        """Keys of the call's first argument, when it is an object literal.

        Nested keys are recorded under their parent rather than dropped: vendor
        changes are overwhelmingly nested, so a request-side path that stopped
        at depth 1 could only ever meet a depth-1 change.
        """
        args = call_node.child_by_field_name("arguments")
        if args is None or not args.named_children:
            return []
        first_arg = args.named_children[0]
        if first_arg.type != "object":
            return []
        return sorted(self._object_paths(first_arg, source))

    def _destructured_fields(self, pattern: Node, source: bytes, prefix: tuple[str, ...] = ()) -> set[str]:
        """API field paths bound by a destructuring pattern.

        `{ id, status: chargeStatus }` reads `id` and `status` — the key is
        what the vendor returns; a renamed local binding is not. A nested
        pattern binds a nested path, so `{ card: { brand } }` reads
        `card.brand` and not `brand`.
        """
        fields: set[str] = set()
        for node in pattern.named_children:
            if node.type == "shorthand_property_identifier_pattern":
                fields.add(_path([*prefix, _text(node, source)]))
            elif node.type == "pair_pattern":
                key = node.child_by_field_name("key")
                if key is None:
                    continue
                here = (*prefix, _text(key, source).strip("'\""))
                fields.add(_path(here))
                value = node.child_by_field_name("value")
                if value is not None and value.type == "object_pattern":
                    fields.update(self._destructured_fields(value, source, here))
        return fields

    def _enclosing_scope(self, node: Node, root: Node) -> Node:
        """The nearest function, method, or arrow-function ancestor of `node`.

        Falls back to `root` for a module-level call, which has no such
        ancestor.
        """
        current = node.parent
        while current is not None:
            if current.type in _FUNCTION_TYPES:
                return current
            current = current.parent
        return root

    def _response_fields(self, call_node: Node, source: bytes, root: Node) -> list[str]:
        """Field paths read off the call's result.

        Finds the variable — or destructuring pattern — the call is assigned
        to. For a destructured result, the pattern itself names the fields
        read. For a plain variable, collects every member chain rooted at it,
        searching only the call's enclosing function: two unrelated calls
        that happen to share a generic result name (`result`, `data`) in
        different functions must not merge into one dependency set.

        The whole chain is recorded, not its first hop. `result.a.b` reads a
        path two deep, and a vendor change two deep can only be matched by a
        call site that says so. Its prefixes land in the result too, because
        `result.a` is a node of its own and the walk reaches it independently.

        A chain ends at anything that is not a plain property access — a
        subscript, a call, a `map` callback — so `result.data[0].customer`
        contributes `data` and stops. That is a shorter path, never a wrong
        one, and it stops exactly where oasdiff writes an `items` segment.
        """
        declarator = call_node
        while declarator is not None and declarator.type != "variable_declarator":
            declarator = declarator.parent
        if declarator is None:
            return []
        name_node = declarator.child_by_field_name("name")
        if name_node is None:
            return []

        if name_node.type == "object_pattern":
            return sorted(self._destructured_fields(name_node, source))
        if name_node.type != "identifier":
            return []
        result_name = _text(name_node, source)
        scope = self._enclosing_scope(call_node, root)

        fields: set[str] = set()
        for node in _walk(scope):
            if node.type != "member_expression":
                continue
            chain = self._member_chain(node, source)
            if chain is None or len(chain) < 2 or chain[0] != result_name:
                continue
            fields.add(_path(chain[1:]))
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

    def prepare(self, repo: RepoRef) -> None:
        """Make the checkout typecheckable before the patch agent works in it.

        The patch agent runs with `Bash` in hand and is instructed to run its
        own `npx tsc --noEmit` until it is clean. If `node_modules` is still
        empty when it starts, its own typecheck reports the same unresolved-
        import wall this task exists to eliminate, and the only command
        available to clear that is an install with no `--ignore-scripts`
        guarantee. Installing here, before the patch node, also takes the
        multi-minute install off the serial patch -> verify path: it depends
        on nothing the patch produces.

        It also records what the checkout already fails, which is the only
        moment that measurement can be taken: after the patch node runs there is
        no pre-patch tree left to measure. Doing it here costs one `tsc` on the
        serial path, ahead of an agent run measured in minutes, and it is
        measured once for the clone rather than once per finding -- `_reset_clone`
        returns that clone to the commit it was cloned at, so every finding
        after the first would measure the same tree again. A CI retry keeps the
        first measurement even though `push_branch` has moved HEAD, because
        every commit Sync adds to that branch passed this gate and so introduced
        nothing the baseline does not already hold.
        """
        from sync.index.dependency_edits import mark_installed
        from sync.index.deps import install_dependencies

        path = Path(repo.local_path).resolve()
        install_dependencies(path)
        # Marked unconditionally, and after the install rather than before it:
        # this node is the last thing to touch the clone before the patch agent
        # does, so everything under `node_modules` older than this instant is
        # the install's and everything newer is the agent's.
        self._installed_at[path] = mark_installed(path)
        if path not in self._baselines:
            self._baselines[path] = self._baseline(path)

    def _baseline(self, path: Path) -> list:
        """The diagnostics this checkout produces with no patch applied.

        Measured through `shipped_tree` for the same reason the verification is:
        a baseline taken against the working tree would carry whatever generated
        files happen to be sitting in the clone -- the last finding's
        `next-env.d.ts` survives `git clean -fd` -- and would then report every
        error the shipped tree really has as one the patch introduced.

        A compiler that failed to run is not a baseline of zero. A timeout, a
        crashed compiler and a failed `npx` download all arrive as a non-zero
        exit carrying prose and no diagnostics, and either reading of that is
        wrong: as an empty baseline every pre-existing error looks introduced,
        and as a clean one every introduced error looks pre-existing. It raises,
        which the graph treats as the environment fault it is and abandons on
        before spending an agent run.

        Nor is a tree that already carries a patch. `static_verify` subtracts
        this measurement from its own, so a modification present here is
        subtracted from the verification that was supposed to catch it: the gate
        approves the error it exists to reject, and reports nothing. The graph
        cannot reach that -- `prepare` runs before the patch node, against a
        fresh clone or one `_reset_clone` has put back -- which is exactly why
        it has to fail loudly rather than be assumed.
        """
        from sync.index.deps import DEPENDENCY_DIRS
        from sync.index.shipped_tree import shipped_tree
        from sync.index.tsc import parse_diagnostics, run_tsc

        modified = subprocess.run(
            ["git", "diff", "--name-only"], cwd=path,
            capture_output=True, text=True, encoding="utf-8", check=True,
        ).stdout.split()
        if modified:
            raise RuntimeError(
                f"cannot measure a typecheck baseline for {path}: uncommitted changes to "
                f"{', '.join(modified)} would be subtracted from the verification"
            )

        with shipped_tree(path, keep=DEPENDENCY_DIRS):
            result = run_tsc(path)
        if result.ok:
            return []
        found = parse_diagnostics(result.diagnostics)
        if not found:
            raise RuntimeError(
                f"could not establish a typecheck baseline for {path}: {result.diagnostics}"
            )
        return found

    def discard_contaminated_dependencies(self, repo: RepoRef) -> bool:
        """Drop this clone's installed dependencies if the last patch edited them.

        One clone serves every finding in a run, and the reset between findings keeps
        ignored files so the install survives -- which is what makes the second finding
        cheap and is also what carries a doctored declaration forward into it. The guard
        that abandoned the first finding does not clean up after itself: the forge cannot
        see the filesystem and the graph does not know what a dependency directory is.

        Called by the driver between findings rather than from `static_verify`, because a
        verification that is about to be retried still needs the tree it just measured.
        Returns whether anything was removed, which is the only signal an operator gets
        that the next finding will pay for a reinstall.

        Nothing is cleared here afterwards: `prepare` re-marks the install unconditionally
        on the next finding, and the recorded baseline still describes the tree a reinstall
        from the same lockfile produces.
        """
        from sync.index.dependency_edits import discard_dependencies
        from sync.index.deps import DEPENDENCY_DIRS

        path = Path(repo.local_path).resolve()
        return discard_dependencies(
            path, DEPENDENCY_DIRS, only_if_edited_after=self._installed_at.get(path)
        )

    def static_verify(self, repo: RepoRef, patch: Patch) -> VerifyResult:
        """Fail on the diagnostics the patch introduced, and on no others.

        The patch is expected to be applied to `repo.local_path` before this is
        called — the graph's `patch` node writes to the clone directly, so there
        is nothing to apply here.

        Two subtractions, and the gate is the composition of them. The agent's
        untracked and ignored files are held out of the way for the compile,
        because `push_branch` will not carry them and a verdict that depends on
        them describes no artifact anyone will review; `sync.index.shipped_tree`
        carries why that is done in place rather than against a second checkout.
        Then whatever the same tree already failed before the patch is
        subtracted, because the customer's CI generates what it needs before it
        typechecks and Sync does not -- without this the gate is stricter than
        the CI it approximates, and the M0 acceptance run abandoned a correct
        patch on fifteen unresolved image imports present in the base tree.

        Subtracting is not the same as tolerating. What reaches the next patch
        attempt is only what that attempt can act on, and an error the patch
        wrote fails the gate whether or not the tree around it was already
        broken.

        A verification with no baseline raises rather than guessing. Passing
        would approve a patch on no evidence, and rejecting everything would
        abandon every finding on a repository that does not typecheck clean —
        which is the population this exists for.

        The dependency check runs before the compiler and raises rather than
        returning a failed result, which are two decisions and not one.

        Before, because a patch that edited an installed declaration cannot be
        verified at all: the compiler would be resolving a file no checkout of
        the branch contains, so the tens of seconds it would spend produce a
        verdict about nothing. Raising, because the edit stays in the clone. It
        cannot be undone without reinstalling, `_reset_clone` runs `git clean`
        without `-x` and so leaves it, and a fresh patch agent is handed the
        diagnostics and no pristine copy to restore from. Every remaining
        attempt would meet the same doctored declaration, so spending them costs
        two agent runs to reach the same abandonment with a later timestamp --
        which is exactly what `route_after_static` reads `static_fatal` for.
        """
        from sync.index.dependency_edits import (
            describe,
            mark_installed,
            unshippable_dependency_edits,
        )
        from sync.index.deps import DEPENDENCY_DIRS, install_dependencies
        from sync.index.shipped_tree import shipped_tree
        from sync.index.tsc import introduced_diagnostics, parse_diagnostics, run_tsc

        path = Path(repo.local_path).resolve()
        baseline = self._baselines.get(path)
        if baseline is None:
            raise RuntimeError(f"no typecheck baseline for {path}; prepare did not run")

        # An install here rewrote every file under `node_modules`, so the mark
        # `prepare` took would read the whole tree as edited.
        if install_dependencies(path):
            self._installed_at[path] = mark_installed(path)

        edited = unshippable_dependency_edits(path, DEPENDENCY_DIRS, self._installed_at[path])
        if edited:
            raise RuntimeError(describe(edited))

        with shipped_tree(path, keep=DEPENDENCY_DIRS):
            result = run_tsc(path)
        if result.ok:
            return VerifyResult(ok=True)

        patched = parse_diagnostics(result.diagnostics)
        if not patched:
            # Nothing to subtract from. An uninterpretable run is a failed
            # verification, never an empty set of introduced errors.
            return VerifyResult(ok=False, diagnostics=result.diagnostics)

        introduced = introduced_diagnostics(baseline, patched)
        if not introduced:
            return VerifyResult(ok=True)
        return VerifyResult(
            ok=False, diagnostics="\n".join(diagnostic.render() for diagnostic in introduced)
        )
