"""Tier 0 for the change class the M0 acceptance run actually hit.

`request-property-removed` against a call site that passes the property is the single most
common shape this detector emits, and the acceptance run spent roughly ten minutes of `xhigh`
model time deleting two lines of it. The edit is mechanical: one named key leaves one object
literal at a known file and line.

The fixture is the arrangement that matters. `stripe-connect-furever-demo` passes
`receipt_email` at two separate `stripe.paymentIntents.create` calls in one file, and the
finding names one of them. A remediator that removes both is wrong even though both are
affected, because the pull request tells a reviewer it covers one call site.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from sync.core import CallSite, Finding, RepoRef, VendorChange
from sync.remediate.property_omit import PropertyOmitRemediator
from sync.remediate.tiered import CannotPatch

FIXTURE = Path(__file__).parent / "fixtures" / "ts" / "two_payment_intents"
TARGET = "app/api/setup_accounts/route.ts"

# Both calls, as the indexer reports them: 1-based line, 0-based column, on the
# call_expression node.
FIRST_CALL = (11, 23)
SECOND_CALL = (21, 23)

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
        vendor_change_id="vc-1",
        severity="breaking", rationale="PostPaymentIntents no longer accepts receipt_email",
    )


def _site(position: tuple[int, int] = FIRST_CALL, path: str = TARGET) -> CallSite:
    line, col = position
    return CallSite(
        repo_id="repo-1", path=path, line=line, col=col, vendor_id="stripe",
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


def _source(repo: RepoRef) -> str:
    return (Path(repo.local_path) / TARGET).read_text(encoding="utf-8")


# --- can_handle: what the codemod claims, and what it hands to the agent -----------


def test_it_handles_a_request_property_removal():
    assert PropertyOmitRemediator().can_handle(_finding(), CHANGE) is True


def test_it_declines_a_response_side_removal():
    """Removing a read of a response field is not deleting a key from an argument. The
    replacement value has to come from somewhere, which is reasoning, not an edit."""
    response_side = CHANGE.model_copy(update={
        "kind": "response-property-removed",
        "raw": {"id": "response-property-removed",
                "text": "removed the optional property `status` from the response"},
    })
    assert PropertyOmitRemediator().can_handle(_finding(), response_side) is False


def test_it_declines_a_change_whose_field_cannot_be_named():
    """oasdiff records frequently name no field. Without one there is no key to delete,
    and guessing from the URL path would be confident nonsense."""
    unnamed = CHANGE.model_copy(update={"raw": {"id": "request-property-removed"}})
    assert PropertyOmitRemediator().can_handle(_finding(), unnamed) is False


# --- propose: the edit, and the call site it is confined to ------------------------


def test_the_patch_is_a_codemod_not_an_agent_run(repo: RepoRef):
    assert PropertyOmitRemediator().propose(_finding(), CHANGE, _site(), repo).strategy == "codemod"


def test_it_removes_the_property_from_the_located_call_only(repo: RepoRef):
    """The test this module exists for. A naive implementation removes both."""
    patch = PropertyOmitRemediator().propose(_finding(), CHANGE, _site(FIRST_CALL), repo)

    removed = [l for l in patch.diff.splitlines() if l.startswith("-") and not l.startswith("---")]
    assert len(removed) == 1
    assert "onboarding@example.com" in removed[0]
    assert "topup@example.com" not in patch.diff


def test_the_second_call_site_is_reachable_by_its_own_position(repo: RepoRef):
    patch = PropertyOmitRemediator().propose(_finding(), CHANGE, _site(SECOND_CALL), repo)

    removed = [l for l in patch.diff.splitlines() if l.startswith("-") and not l.startswith("---")]
    assert len(removed) == 1
    assert "topup@example.com" in removed[0]


def test_the_diff_adds_nothing(repo: RepoRef):
    """A removal that also adds a line has reformatted something it was not asked to."""
    patch = PropertyOmitRemediator().propose(_finding(), CHANGE, _site(), repo)
    added = [l for l in patch.diff.splitlines() if l.startswith("+") and not l.startswith("+++")]
    assert added == []


def test_the_diff_names_the_file_it_applies_to(repo: RepoRef):
    assert TARGET in PropertyOmitRemediator().propose(_finding(), CHANGE, _site(), repo).diff


def test_the_property_named_in_prose_survives(repo: RepoRef):
    """The comment and the string in the fixture both contain `receipt_email`. This is
    why the edit is located with a parser rather than a regular expression."""
    patch = PropertyOmitRemediator().propose(_finding(), CHANGE, _site(), repo)
    assert "prose" not in patch.diff


def test_the_rationale_names_the_property_and_the_call_site(repo: RepoRef):
    """The pull request body is where a machine-written change earns approval."""
    patch = PropertyOmitRemediator().propose(_finding(), CHANGE, _site(), repo)

    assert "receipt_email" in patch.rationale
    assert TARGET in patch.rationale
    assert "PostPaymentIntents" in patch.rationale


# --- declining: an empty diff, and what the tier does with one ---------------------


def test_a_call_site_that_does_not_pass_the_property_produces_no_patch(repo: RepoRef):
    absent = CHANGE.model_copy(update={
        "raw": {"id": "request-property-removed",
                "text": "removed the request property `statement_descriptor`"},
    })
    assert PropertyOmitRemediator().propose(_finding(), absent, _site(), repo).diff == ""


def test_a_position_naming_no_call_declines_rather_than_claiming_nothing_to_do(repo: RepoRef):
    """The graph records this call site as passing `receipt_email`, so "no edit here" is a
    disagreement between the index and the source, not an already-migrated file. An empty
    diff would abandon the finding; declining sends it to the agent.
    """
    with pytest.raises(CannotPatch):
        PropertyOmitRemediator().propose(_finding(), CHANGE, _site((3, 0)), repo)


def test_a_missing_file_declines_rather_than_crashing(repo: RepoRef):
    """The index can outlive the file. A deleted path is a stale binding -- not a crash,
    and not evidence the property is gone either."""
    site = _site(path="app/api/gone/route.ts")
    with pytest.raises(CannotPatch):
        PropertyOmitRemediator().propose(_finding(), CHANGE, site, repo)


def test_an_unsupported_extension_declines(repo: RepoRef):
    (Path(repo.local_path) / "config.yaml").write_text("receipt_email: x\n", encoding="utf-8")
    site = _site(path="config.yaml")
    with pytest.raises(CannotPatch):
        PropertyOmitRemediator().propose(_finding(), CHANGE, site, repo)


def test_a_spread_in_the_argument_object_declines(repo: RepoRef):
    """`...defaults` may itself supply the property, so deleting the explicit pair does not
    establish that the request stops sending it. The agent can read `defaults`."""
    target = Path(repo.local_path) / TARGET
    target.write_text(
        _source(repo).replace("    amount: 1000,", "    ...defaults,\n    amount: 1000,"),
        encoding="utf-8",
    )
    with pytest.raises(CannotPatch):
        PropertyOmitRemediator().propose(_finding(), CHANGE, _site(FIRST_CALL), repo)


def test_the_patch_is_idempotent(repo: RepoRef):
    """The graph retries. A codemod that keeps finding work would loop to the budget."""
    remediator = PropertyOmitRemediator()
    target = Path(repo.local_path) / TARGET

    first = remediator.propose(_finding(), CHANGE, _site(), repo)
    assert first.diff

    target.write_text(_source(repo).replace(
        "    receipt_email: 'onboarding@example.com',\n", ""), encoding="utf-8")
    assert remediator.propose(_finding(), CHANGE, _site(), repo).diff == ""


def test_it_satisfies_the_remediator_protocol():
    from sync.core.protocols import Remediator

    assert isinstance(PropertyOmitRemediator(), Remediator)


# --- the applied diff has to be the edit, not merely describe it -------------------


def test_the_edit_reaches_the_clone_and_not_only_the_diff(repo: RepoRef):
    """Nothing in the pipeline applies `patch.diff`.

    `nodes.make_patch` stores the `Patch`, `static_verify` typechecks the working tree,
    and `push_branch` stages it with `git add -u`. A remediator that renders a diff
    without writing it produces a branch with no commit, having reported success.
    """
    PropertyOmitRemediator().propose(_finding(), CHANGE, _site(), repo)

    on_disk = _source(repo)
    assert "onboarding@example.com" not in on_disk
    assert "topup@example.com" in on_disk


def test_the_rendered_diff_describes_the_edit_that_was_written(tmp_path: Path):
    """The diff is what a reviewer reads and what `migration_outcome` keeps; the working
    tree is what ships. They have to be the same change, so the diff is applied to a
    pristine copy and the result compared against the clone the remediator edited.
    """
    import subprocess

    clone = tmp_path / "clone"
    pristine = tmp_path / "pristine"
    shutil.copytree(FIXTURE, clone)
    shutil.copytree(FIXTURE, pristine)
    repo = RepoRef(
        repo_id="repo-1", url="https://example.invalid/r",
        local_path=str(clone), head_sha="abc123",
    )

    patch = PropertyOmitRemediator().propose(_finding(), CHANGE, _site(), repo)
    patch_file = tmp_path / "omit.patch"
    # Bytes, not `write_text`: on Windows that translates "\n" to "\r\n", and a patch
    # whose context lines carry a stray carriage return matches no LF source file.
    patch_file.write_bytes(patch.diff.encode("utf-8"))

    subprocess.run(["git", "init", "-q"], cwd=pristine, check=True)
    applied = subprocess.run(
        ["git", "apply", str(patch_file)],
        cwd=pristine, capture_output=True, text=True, encoding="utf-8",
    )
    assert applied.returncode == 0, applied.stderr
    assert (pristine / TARGET).read_text(encoding="utf-8") == (clone / TARGET).read_text(
        encoding="utf-8"
    )


# --- line endings, which no ASCII fixture and no assertion on text can catch -------


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_the_file_keeps_the_line_endings_it_had(tmp_path: Path, newline: str):
    """`Path.write_text` translates "\n" to `os.linesep` on Windows.

    Writing an LF source back there converts every line in the file to CRLF. The diff
    claims one line; `push_branch` stages with `git add -u` and commits all of them, and
    the pull request asks a reviewer to approve a whole-file rewrite. It reverses on a
    CRLF repository read through universal newlines. Only the bytes show it, which is
    why this asserts on them.
    """
    clone = tmp_path / "clone"
    shutil.copytree(FIXTURE, clone)
    target = clone / TARGET
    body = target.read_bytes().replace(b"\r\n", b"\n")
    target.write_bytes(body.replace(b"\n", newline.encode("ascii")))

    repo = RepoRef(
        repo_id="repo-1", url="https://example.invalid/r",
        local_path=str(clone), head_sha="abc123",
    )
    PropertyOmitRemediator().propose(_finding(), CHANGE, _site(), repo)

    written = target.read_bytes()
    assert newline.encode("ascii") in written
    if newline == "\n":
        assert b"\r\n" not in written, "an LF file was rewritten with CRLF endings"
    else:
        assert written.count(b"\n") == written.count(b"\r\n"), "a CRLF file gained bare LFs"
    assert b"onboarding@example.com" not in written
    assert b"topup@example.com" in written
