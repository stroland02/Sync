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

from pathlib import Path

from sync.core import CallSite, Finding, OperationRef, Patch, RepoRef, VendorAdapter, VendorChange
from sync.core.conformance import ConformanceFailure, check_remediator, check_vendor_adapter


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


# --- Remediator -------------------------------------------------------------------


class _CorrectRemediator:
    """Writes its edit to the clone, then describes it."""

    strategy = "codemod"

    def can_handle(self, finding, change) -> bool:
        return True

    def propose(self, finding, change, site, repo, diagnostics: str = ""):
        target = Path(repo.local_path) / site.path
        original = target.read_text(encoding="utf-8")
        updated = original.replace("amount", "value")
        if updated == original:
            return Patch(diff="", strategy=self.strategy, rationale="nothing to change")
        target.write_text(updated, encoding="utf-8")
        return Patch(diff="--- a\n+++ b\n", strategy=self.strategy, rationale="renamed")


def test_a_correct_remediator_passes(tmp_path):
    check_remediator(_CorrectRemediator(), *_remediation_case(tmp_path))


def test_a_remediator_that_only_returns_a_diff_fails(tmp_path):
    """The defect this rule exists for, and it has shipped twice.

    Nothing downstream applies `patch.diff`. `make_patch` stores the `Patch`, `static_verify`
    typechecks the working tree, and `push_branch` stages with `git add -u`. So a remediator
    that computes the right edit and returns it without writing produces a branch with an
    empty commit and reports success — green verdict, empty pull request. It shipped in
    `literal_swap` and again in both parameter remediators, and was caught the second time
    only because one worker happened to read another's fix.
    """

    class DiffOnly(_CorrectRemediator):
        def propose(self, finding, change, site, repo, diagnostics: str = ""):
            return Patch(diff="--- a\n+++ b\n", strategy=self.strategy, rationale="renamed")

    with pytest.raises(ConformanceFailure, match="did not change the clone"):
        check_remediator(DiffOnly(), *_remediation_case(tmp_path))


def test_a_remediator_that_writes_while_declining_fails(tmp_path):
    """The mirror, and the one a naive fix introduces.

    An empty diff means the remediator declined. Writing anyway — even identical bytes —
    touches a file it decided not to edit, and a tool that does that near a working tree is
    one nobody trusts. `test_declining_writes_nothing` asserts `st_mtime_ns` for this reason.
    """

    class WritesWhileDeclining(_CorrectRemediator):
        def propose(self, finding, change, site, repo, diagnostics: str = ""):
            target = Path(repo.local_path) / site.path
            target.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
            return Patch(diff="", strategy=self.strategy, rationale="declined")

    with pytest.raises(ConformanceFailure, match="declined.*changed the clone|changed the clone"):
        check_remediator(WritesWhileDeclining(), *_remediation_case(tmp_path))


def test_a_remediator_whose_strategy_is_empty_fails(tmp_path):
    class Anonymous(_CorrectRemediator):
        strategy = ""

    with pytest.raises(ConformanceFailure, match="strategy"):
        check_remediator(Anonymous(), *_remediation_case(tmp_path))


def _remediation_case(tmp_path):
    """A finding, a change, a call site and a clone the remediator is expected to edit."""
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "billing.ts").write_text(
        "stripe.charges.create({ amount: 100 });\n", encoding="utf-8"
    )
    site = CallSite(
        repo_id="r", path="src/billing.ts", line=1, col=0, vendor_id="example",
        operation_id="PostCharges", symbol="example.charges.create",
        args_keys=["amount"], response_fields_read=[], sdk_version="1.0.0", content_hash="h",
    )
    change = VendorChange(
        vendor_id="example", from_version="v1", to_version="v2",
        kind="request-property-removed", operation_id="PostCharges", path_ptr="/amount",
        severity="breaking", source="oasdiff", raw={},
    )
    finding = Finding(
        id="f1", detector="vendor_change", call_site_id="cs1", vendor_change_id="vc1",
        severity="breaking", rationale="amount removed",
    )
    repo = RepoRef(repo_id="r", url="u", local_path=str(tmp_path), head_sha="0" * 40)
    return finding, change, site, repo
