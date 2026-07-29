"""The conformance kit an outside adapter author runs against their own class.

`isinstance(adapter, VendorAdapter)` is a `runtime_checkable` Protocol check, and those verify
only that the method *names* exist. Signatures, return types and behaviour are all unchecked, so
an adapter that raises where it should return `None`, or hands back a string where an
`OperationRef` is required, passes today and fails inside the pipeline instead — where the
diagnostic names Sync's internals rather than the author's mistake.

These tests are about the kit, not about any one adapter. The adapters ship their own tests.
"""

from __future__ import annotations

import pytest

from sync.core import OperationRef, VendorAdapter
from sync.core.conformance import ConformanceFailure, check_vendor_adapter


class _Correct:
    """The shape every invariant is stated against."""

    vendor_id = "example"

    def fetch_changes(self, from_version: str, to_version: str):
        return []

    def operation_for_symbol(self, symbol: str, *, language: str | None = None):
        if symbol == "example.charges.create":
            return OperationRef(operation_id="PostCharges", http_method="post", path="/v1/charges")
        return None


def test_a_correct_adapter_passes():
    check_vendor_adapter(_Correct(), known_symbol="example.charges.create")


def test_an_adapter_that_raises_on_an_unknown_symbol_fails():
    """The invariant this repository states most often and writes down least visibly: an
    unresolvable symbol returns None rather than raising or guessing. An unresolved symbol is
    visibly unresolved and countable; a raised exception aborts an indexing run over one
    call site the adapter simply did not recognise.
    """

    class Raises(_Correct):
        def operation_for_symbol(self, symbol: str, *, language: str | None = None):
            raise KeyError(symbol)

    assert isinstance(Raises(), VendorAdapter), "isinstance must still pass, or this proves nothing"
    with pytest.raises(ConformanceFailure, match="unknown symbol"):
        check_vendor_adapter(Raises(), known_symbol="example.charges.create")


def test_an_adapter_that_returns_the_wrong_type_fails():
    """A string is not an OperationRef. The pipeline would fail on attribute access somewhere
    far from here, naming a field rather than the adapter.
    """

    class WrongType(_Correct):
        def operation_for_symbol(self, symbol: str, *, language: str | None = None):
            # Correct for the unknown symbol, so this isolates the return-type rule from the
            # returns-None-for-unknown rule that would otherwise fire first.
            return "PostCharges" if symbol == "example.charges.create" else None

    assert isinstance(WrongType(), VendorAdapter)
    with pytest.raises(ConformanceFailure, match="OperationRef"):
        check_vendor_adapter(WrongType(), known_symbol="example.charges.create")


def test_an_adapter_that_refuses_the_language_argument_fails():
    """The language axis landed as a keyword-only argument. An adapter whose two SDK languages
    agree may ignore it, but every adapter must accept it -- the indexer passes it always, so
    one that does not accept it raises TypeError on the first call site it sees.
    """

    class NoLanguage(_Correct):
        def operation_for_symbol(self, symbol: str):
            return None

    # Matched on the rule's own wording rather than the word "language": without this rule the
    # later call raises TypeError whose text also contains "language", so a loose regex passes
    # for the wrong reason and the mutation that deletes the rule survives.
    with pytest.raises(ConformanceFailure, match="must accept a keyword-only"):
        check_vendor_adapter(NoLanguage(), known_symbol="example.charges.create")


def test_an_adapter_without_a_vendor_id_fails():
    class Anonymous(_Correct):
        vendor_id = ""

    with pytest.raises(ConformanceFailure, match="vendor_id"):
        check_vendor_adapter(Anonymous(), known_symbol="example.charges.create")


def test_fetch_changes_must_be_iterable_rather_than_none():
    """Every stage here is required to be idempotent and re-runnable. A vendor with nothing to
    report returns an empty iterable; None is the shape that makes a caller crash on a for loop.
    """

    class ReturnsNone(_Correct):
        def fetch_changes(self, from_version: str, to_version: str):
            return None

    with pytest.raises(ConformanceFailure, match="iterable"):
        check_vendor_adapter(ReturnsNone(), known_symbol="example.charges.create")
