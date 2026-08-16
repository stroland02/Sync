"""A computed key names a property, and reading the brackets as the name loses it.

`{ ['receipt_email']: 'x' }` declares the same key as `{ receipt_email: 'x' }`. Comparing the
key node's text against the property name sees `['receipt_email']`, which matches nothing, so
both position-scoped primitives answer "the property is not here" -- and `PropertyOmitRemediator`
turns that into "the code already agrees with the vendor". It does not: the property is present
and was not removed.

The repair is not a strip in the shared text accessor. The rewriter reads the same helper the
readers do, and unwrapping there would make `rename_parameter` replace `['budget_tokens']` with
a bare `max_tokens` -- a change to the key's *form*, in a diff whose only claimed purpose is a
rename, and `[max_tokens]` is a reference to a binding rather than a name. So the readers take a
name node's *text* and the rewriter takes its *span*, and one rule decides which node that is.

The second half is the decline. `{ [k]: 'x' }` names something only the running program knows.
That is the unknown a spread already carries -- the computed key may itself be the property under
discussion -- so it is declined rather than guessed, and every assertion below on a decline is
against a spelled-out literal rather than against `== source`, because the primitives return the
input object on a decline and `== source` is true whatever the code did.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from sync.core import CallSite, Finding, RepoRef, VendorChange
from sync.remediate.property_omit import PropertyOmitRemediator
from sync.remediate.tiered import CannotPatch
from sync.route.templates import (
    argument_is_literal_at,
    omit_argument_at,
    omit_parameter,
    omit_property_at,
    rename_parameter,
)

MODEL = "claude-opus-5"


def _omit_at(source: str, argument: str = "receipt_email") -> str | None:
    return omit_argument_at(
        source, argument, language="typescript", line=0, col=source.index("create"),
    )


def _is_literal(source: str, argument: str = "receipt_email") -> bool | None:
    return argument_is_literal_at(
        source, argument, language="typescript", line=0, col=source.index("create"),
    )


# --- the defect: a computed literal key is the key it names ------------------------


def test_a_single_quoted_computed_key_is_removed_like_any_other():
    source = "const r = create({ amount: 1, ['receipt_email']: 'x', currency: 'usd' });\n"
    assert _omit_at(source) == "const r = create({ amount: 1, currency: 'usd' });\n"


def test_a_double_quoted_computed_key_is_removed_like_any_other():
    source = 'const r = create({ amount: 1, ["receipt_email"]: "x" });\n'
    assert _omit_at(source) == "const r = create({ amount: 1 });\n"


def test_a_computed_key_with_nothing_interpolated_is_removed_like_any_other():
    """A template with no substitution is a literal spelled differently -- the rule this
    module already applies to a *value*, applied to the name of a key."""
    source = "const r = create({ amount: 1, [`receipt_email`]: 'x' });\n"
    assert _omit_at(source) == "const r = create({ amount: 1 });\n"


def test_whitespace_inside_the_brackets_does_not_hide_the_name():
    source = "const r = create({ amount: 1, [ 'receipt_email' ]: 'x' });\n"
    assert _omit_at(source) == "const r = create({ amount: 1 });\n"


def test_a_computed_literal_key_reads_as_passed_as_a_literal():
    """`RoutingFacts.field_passed_as_literal`. `False` here means "located, and not written
    out at the call site", which row 4 reads as a decline it can explain. The whole of what
    this call sends is written at the call site, so the honest answer is `True`."""
    assert _is_literal("const r = create({ ['receipt_email']: 'x@example.com' });\n") is True


def test_a_computed_key_holding_a_variable_value_is_not_a_literal():
    """The key is readable and the value is not. Deleting the pair would drop the only use
    of `userEmail` and leave the question of what it was for."""
    assert _is_literal("const r = create({ ['receipt_email']: userEmail });\n") is False


# --- the declines: a name the call site does not write ------------------------------


UNREADABLE_KEYS = [
    "[k]",
    "[FIELDS.receipt]",
    "[Symbol.iterator]",
    "[`${prefix}_email`]",
    "['receipt' + '_email']",
]


@pytest.mark.parametrize("key", UNREADABLE_KEYS)
def test_a_key_the_call_site_does_not_write_cannot_be_established(key: str):
    """`None`, not an edit and not "already correct".

    The computed key may itself be the property the vendor removed, so deleting the explicit
    pair would not establish that the request stops sending it -- the same unknown a spread
    carries, in a different shape. Removing the explicit pair anyway produces a patch that
    compiles, type-checks, and leaves the call sending the property it claims to have removed.
    """
    source = f"const r = create({{ {key}: 'x', receipt_email: 'y' }});\n"

    assert _omit_at(source) is None
    assert _is_literal(source) is None


def test_the_source_is_untouched_where_the_property_set_cannot_be_read():
    """`None` is the answer and the input is not edited on the way to it."""
    source = "const r = create({ [k]: 'x', receipt_email: 'y' });\n"
    _omit_at(source)

    assert source == "const r = create({ [k]: 'x', receipt_email: 'y' });\n"


def test_a_readable_computed_key_beside_an_unreadable_one_still_declines():
    """One unknown key makes the object's property set unknown. Editing the readable pair
    would be answering a question the object did not settle."""
    source = "const r = create({ ['receipt_email']: 'x', [k]: 'y' });\n"

    assert _omit_at(source) is None
    assert _is_literal(source) is None


def test_a_numeric_computed_key_is_not_read_as_a_name():
    """`{ [0]: 'x' }` declares `"0"`, which is knowable and is not a name a vendor field can
    collide with. It is not collected, and the object it sits in declines like any other whose
    keys this cannot enumerate as names."""
    source = "const r = create({ [0]: 'x', receipt_email: 'y' });\n"
    assert _omit_at(source) is None


# --- the rewriter: the split, and the form it preserves -----------------------------


def _rename(source: str, old: str = "budget_tokens", new: str = "max_tokens") -> str:
    return rename_parameter(source, old, new, language="typescript", within_object_naming=MODEL)


def test_a_computed_key_is_renamed_inside_its_brackets():
    """The bracket and the quote are the author's, and a rename is not entitled to either.
    Replacing the whole key node would write `max_tokens: 8`, and replacing the whole computed
    name without the quote would write `[max_tokens]: 8` -- a reference to a binding.
    """
    source = "create({ model: \"claude-opus-5\", ['budget_tokens']: 8 });\n"
    assert _rename(source) == "create({ model: \"claude-opus-5\", ['max_tokens']: 8 });\n"


def test_a_double_quoted_computed_key_keeps_its_brackets_and_its_quotes():
    source = 'create({ model: "claude-opus-5", ["budget_tokens"]: 8 });\n'
    assert _rename(source) == 'create({ model: "claude-opus-5", ["max_tokens"]: 8 });\n'


def test_a_computed_key_written_as_a_template_keeps_its_backticks():
    source = "create({ model: \"claude-opus-5\", [`budget_tokens`]: 8 });\n"
    assert _rename(source) == "create({ model: \"claude-opus-5\", [`max_tokens`]: 8 });\n"


def test_a_key_computed_from_a_binding_is_not_renamed():
    """`[budget_tokens]` is a *reference* to a binding that happens to be spelled like the
    parameter. Rewriting it renames a variable, which is not what a rename of an argument key
    was approved for, and the name it resolves to is not knowable here.
    """
    source = "create({ model: \"claude-opus-5\", [budget_tokens]: 8 });\n"
    assert _rename(source) == "create({ model: \"claude-opus-5\", [budget_tokens]: 8 });\n"


def test_a_computed_duplicate_written_as_a_template_is_still_a_duplicate():
    """A duplicate key does not fail -- JavaScript takes the last one -- so a guard that
    misses a form produces exactly the silent overwrite it exists to prevent. The guard and
    the key comparison read the same rule, so a form one sees is a form the other sees.
    """
    source = "create({ model: \"claude-opus-5\", [`max_tokens`]: 16, budget_tokens: 8 });\n"
    assert _rename(source) == (
        "create({ model: \"claude-opus-5\", [`max_tokens`]: 16, budget_tokens: 8 });\n"
    )


def test_a_computed_duplicate_written_with_quotes_is_still_a_duplicate():
    source = "create({ model: \"claude-opus-5\", ['max_tokens']: 16, budget_tokens: 8 });\n"
    assert _rename(source) == (
        "create({ model: \"claude-opus-5\", ['max_tokens']: 16, budget_tokens: 8 });\n"
    )


def test_the_rename_is_idempotent_on_a_computed_key():
    once = _rename("create({ model: \"claude-opus-5\", ['budget_tokens']: 8 });\n")
    assert _rename(once) == once


# --- the value-scoped primitives read the same rule ---------------------------------


def test_a_computed_parameter_is_omitted_from_the_object_naming_the_model():
    source = "create({ model: \"claude-opus-5\", ['temperature']: 0.5, top_p: 1 });\n"
    result = omit_parameter(
        source, "temperature", language="typescript", within_object_naming=MODEL
    )
    assert result == 'create({ model: "claude-opus-5", top_p: 1 });\n'


def test_the_position_scoped_property_omit_reads_a_computed_key_too():
    """`omit_property_at` counts lines from one and answers two ways where the remediator
    needs three, which is why `scripts/dead_links_baseline.txt` records it as unwired. It is
    held to the same reading of a key anyway -- the baseline entry is a statement about wiring
    rather than about correctness.
    """
    source = "const r = create({ amount: 1, ['receipt_email']: 'x' });\n"
    result = omit_property_at(
        source, "receipt_email", language="typescript", line=1, col=source.index("create"),
    )
    assert result == "const r = create({ amount: 1 });\n"


# --- what the pipeline does with it -------------------------------------------------

FIXTURE = Path(__file__).parent / "fixtures" / "ts" / "computed_key"
TARGET = "app/api/setup_accounts/route.ts"

# As the indexer reports them: 1-based line, 0-based column, on the call_expression node.
COMPUTED_LITERAL_CALL = (15, 23)
COMPUTED_BINDING_CALL = (25, 23)

CHANGE = VendorChange(
    vendor_id="stripe", from_version="v2300", to_version="v2345",
    kind="request-property-removed", operation_id="PostPaymentIntents",
    path_ptr="/v1/payment_intents", severity="breaking", source="oasdiff",
    raw={"id": "request-property-removed",
         "text": "removed the request property `receipt_email`"},
)


def _finding() -> Finding:
    return Finding(
        detector="vendor_change", claim="request-field", call_site_id="cs-1",
        vendor_change_id="vc-1", severity="breaking",
        rationale="PostPaymentIntents no longer accepts receipt_email",
    )


def _site(position: tuple[int, int] = COMPUTED_LITERAL_CALL) -> CallSite:
    line, col = position
    return CallSite(
        repo_id="repo-1", path=TARGET, line=line, col=col, vendor_id="stripe",
        operation_id="PostPaymentIntents", symbol="stripe.paymentIntents.create",
        args_keys=["amount", "currency", "customer", "receipt_email"],
        response_fields_read=["id"], sdk_version="22.4.0-beta.1", content_hash="h",
    )


@pytest.fixture()
def repo(tmp_path: Path) -> RepoRef:
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    return RepoRef(
        repo_id="repo-1", url="https://example.invalid/r",
        local_path=str(tmp_path), head_sha="abc123",
    )


def test_the_remediator_patches_the_computed_key_instead_of_reporting_agreement(repo: RepoRef):
    """The defect, at the surface that shipped it. An empty diff here means "the code already
    agrees with the vendor", and the call was still sending the property the vendor removed.
    """
    patch = PropertyOmitRemediator().propose(_finding(), CHANGE, _site(), repo)

    removed = [
        line for line in patch.diff.splitlines()
        if line.startswith("-") and not line.startswith("---")
    ]
    assert removed == ["-    ['receipt_email']: 'onboarding@example.com',"]


def test_the_edit_reaches_the_clone_and_leaves_the_other_call_byte_identical(repo: RepoRef):
    """Nothing downstream applies `patch.diff`; `push_branch` stages the working tree.

    The fixture's header comment spells the computed key out, so the surviving occurrence is
    also the check that this is located with a parser rather than with a search for brackets.
    """
    PropertyOmitRemediator().propose(_finding(), CHANGE, _site(), repo)

    on_disk = (
        (Path(repo.local_path) / TARGET).read_bytes().decode("utf-8").replace("\r\n", "\n")
    )
    assert "    ['receipt_email']: 'onboarding@example.com',\n" not in on_disk
    assert "    customer: customerId,\n  });\n" in on_disk
    assert "    [RECEIPT]: 'topup@example.com',\n" in on_disk
    assert "// the same key, so a reader that compares the bracketed text" in on_disk


def test_a_key_computed_from_a_binding_declines_to_the_agent(repo: RepoRef):
    """`RECEIPT` may be `'receipt_email'` and this cannot read it. Declining costs an agent
    run; the empty diff this used to return abandons the finding instead.
    """
    with pytest.raises(CannotPatch):
        PropertyOmitRemediator().propose(_finding(), CHANGE, _site(COMPUTED_BINDING_CALL), repo)


def test_the_declined_call_is_left_on_disk_exactly_as_it_was(repo: RepoRef):
    before = (Path(repo.local_path) / TARGET).read_bytes()

    with pytest.raises(CannotPatch):
        PropertyOmitRemediator().propose(_finding(), CHANGE, _site(COMPUTED_BINDING_CALL), repo)

    assert (Path(repo.local_path) / TARGET).read_bytes() == before
