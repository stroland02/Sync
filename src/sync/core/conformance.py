"""What an adapter must guarantee, expressed as something an author can run.

`isinstance(adapter, VendorAdapter)` is a `runtime_checkable` Protocol check, and the standard
library is explicit that those verify only the presence of method *names*. Signatures, return
types and behaviour are unchecked. So an adapter that raises where it must return `None`, or
returns a string where an `OperationRef` is required, satisfies `isinstance` and then fails
somewhere inside the pipeline, with a diagnostic naming Sync's internals rather than the
author's mistake.

That gap matters more here than it would elsewhere. The design document's argument for open
core is that a live codebase calls dozens of third-party APIs, we cannot write dozens of
adapters ourselves, and the interface therefore has to be good enough that vendors and users
write them. The interface is the product, and until now an outside author had no way to find
out whether theirs was correct.

The invariants below were harvested from the docstrings of the five adapters in this
repository, where they were stated as prose an outside author would never see.

**This module imports nothing outside `sync.core`,** because it ships with the SDK. A
conformance kit that needs `sync.graph` is not a kit, it is an integration test.
"""

from __future__ import annotations

import inspect
from typing import Any

from sync.core.models import OperationRef


class ConformanceFailure(AssertionError):
    """An adapter broke a documented guarantee.

    An `AssertionError` so a `pytest` run reports it as a failure rather than an error, and a
    distinct type so an author can catch it deliberately.
    """


def _fail(rule: str, detail: str) -> None:
    raise ConformanceFailure(f"{rule}\n  {detail}")


def check_vendor_adapter(adapter: Any, *, known_symbol: str) -> None:
    """Check `adapter` against every guarantee `VendorAdapter` states but cannot enforce.

    `known_symbol` is a symbol the adapter is expected to resolve — an author's own example,
    since the kit has no fixtures of its own and must run outside this repository.

    Raises `ConformanceFailure` naming the broken rule. Returns None when the adapter conforms.
    """
    _check_vendor_id(adapter)
    _check_operation_for_symbol(adapter, known_symbol)
    _check_fetch_changes(adapter)


def _check_vendor_id(adapter: Any) -> None:
    vendor_id = getattr(adapter, "vendor_id", None)
    if not isinstance(vendor_id, str) or not vendor_id:
        _fail(
            "vendor_id must be a non-empty string.",
            "It is the key every row this adapter produces is filed under, and a detector is "
            f"scoped to one vendor by it. Got {vendor_id!r}.",
        )


def _check_operation_for_symbol(adapter: Any, known_symbol: str) -> None:
    resolve = getattr(adapter, "operation_for_symbol", None)
    if resolve is None:
        _fail("operation_for_symbol must exist.", "It is how a call site becomes an operation.")

    parameters = inspect.signature(resolve).parameters
    if "language" not in parameters:
        _fail(
            "operation_for_symbol must accept a keyword-only `language` argument.",
            "The indexer passes it on every call, so an adapter that does not accept it raises "
            "TypeError on the first call site it sees. An adapter whose SDK languages spell "
            "symbols identically may ignore the value, but must accept the argument.",
        )

    try:
        unknown = resolve("this.symbol.does.not.exist", language=None)
    except Exception as exc:  # noqa: BLE001 - the point is that nothing may escape
        _fail(
            "operation_for_symbol must return None for an unknown symbol, not raise.",
            "An unresolved symbol is visibly unresolved and countable; an exception aborts an "
            f"indexing run over one call site the adapter did not recognise. Raised {exc!r}.",
        )
    if unknown is not None:
        _fail(
            "operation_for_symbol must return None for an unknown symbol, not a guess.",
            "A wrong operation produces a finding against code that never made the call, and "
            f"nobody learns it was wrong. Got {unknown!r}.",
        )

    resolved = resolve(known_symbol, language=None)
    if resolved is not None and not isinstance(resolved, OperationRef):
        _fail(
            "operation_for_symbol must return an OperationRef or None.",
            f"Got {type(resolved).__name__}. The pipeline reads attributes off this value, so a "
            "wrong type fails far from the adapter and names a field rather than the cause.",
        )


def _check_fetch_changes(adapter: Any) -> None:
    """`fetch_changes` may raise. What it may not do is return something a caller cannot loop over.

    An earlier version of this kit asserted that `fetch_changes` must not raise for a version
    pair it cannot serve, and running it against the real adapters proved that wrong within a
    minute. `StripeAdapter` raises `FileNotFoundError` when a pinned specification is absent,
    and it is right to: a missing specification is an environment failure, and answering it with
    an empty iterable would report that the vendor changed nothing when in fact nothing was
    looked at. That is a false negative in the one direction this system must not have.

    So the rule is narrower than it first appeared. If the call returns, the result has to be
    iterable, because every caller writes a for loop over it and `None` is the shape that
    crashes there.
    """
    fetch = getattr(adapter, "fetch_changes", None)
    if fetch is None:
        _fail("fetch_changes must exist.", "It is how a vendor's artifacts become changes.")

    try:
        changes = fetch("v1", "v1")
    except Exception:  # noqa: BLE001 - raising is permitted; see the docstring
        return

    try:
        iter(changes)
    except TypeError:
        _fail(
            "fetch_changes must return an iterable when it returns at all.",
            "Every caller writes `for change in ...`, and None is the shape that crashes that "
            f"loop. Got {type(changes).__name__}.",
        )


def check_remediator(
    remediator: Any,
    finding: Any,
    change: Any,
    site: Any,
    repo: Any,
) -> None:
    """Check `remediator` against the guarantees `Remediator` states but cannot enforce.

    The caller supplies a finding, a change, a call site and a repository whose working tree the
    remediator is expected to edit. The kit has no fixtures of its own and must run outside this
    repository, so the case comes from the author.

    Raises `ConformanceFailure` naming the broken rule. Returns None when the remediator conforms.
    """
    _check_strategy(remediator)
    _check_propose_touches_the_clone(remediator, finding, change, site, repo)


def _check_strategy(remediator: Any) -> None:
    strategy = getattr(remediator, "strategy", None)
    if not isinstance(strategy, str) or not strategy:
        _fail(
            "strategy must be a non-empty string.",
            "It is recorded on every attempt in the migration corpus, and routing reads it to "
            f"decide which tier produced a patch. Got {strategy!r}.",
        )


def _check_propose_touches_the_clone(
    remediator: Any, finding: Any, change: Any, site: Any, repo: Any
) -> None:
    """A patch is what is on disk, not what the diff says is on disk.

    This is the rule worth having a kit for. Nothing downstream applies `patch.diff`: the graph
    stores the `Patch`, static verification typechecks the working tree, and the push stages
    tracked modifications. So a remediator that computes the correct edit and returns it without
    writing produces a branch carrying an empty commit, and reports success while doing it. The
    verdict is green and the pull request is empty.

    It has shipped twice in this repository. It is invisible from the diff, which is correct in
    both cases, and it is invisible from a test that asserts on the returned value.

    The mirror matters too. An empty diff means the remediator declined, and a decline must leave
    the tree alone -- writing identical bytes still updates an mtime, and a tool that touches
    files it decided not to edit is one nobody trusts near a working tree.
    """
    from pathlib import Path as _Path

    target = _Path(repo.local_path) / site.path
    if not target.exists():
        _fail(
            "the supplied call site must exist in the supplied repository.",
            f"{target} is not there, so this check cannot observe whether propose writes to it. "
            "Fix the case handed to the kit, not the remediator.",
        )

    before = target.read_bytes()
    before_mtime = target.stat().st_mtime_ns

    patch = remediator.propose(finding, change, site, repo)

    after = target.read_bytes()
    changed = after != before
    touched = target.stat().st_mtime_ns != before_mtime
    diff = getattr(patch, "diff", None)
    if not isinstance(diff, str):
        _fail(
            "propose must return a Patch whose diff is a string.",
            f"Got {type(diff).__name__} for the diff.",
        )

    if diff.strip() and not changed:
        _fail(
            "propose returned a diff but did not change the clone.",
            "Nothing downstream applies the diff: the tree is typechecked and the tracked "
            "modifications are staged, so this produces an empty commit and reports success. "
            "Write the edit to the file, then describe it.",
        )
    if not diff.strip() and (changed or touched):
        _fail(
            "propose declined and still changed the clone.",
            "An empty diff means no patch. Writing anyway -- even identical bytes -- updates an "
            "mtime and edits a file the remediator decided to leave alone.",
        )
