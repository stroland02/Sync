"""Tier 0: a patch produced with no model call.

The routing matrix names four tiers and, until now, nothing sat below the agent. This is the
first remediator that satisfies the `Remediator` protocol without spending a token: the vendor
names the replacement, `ast-grep` performs the edit, and `difflib` renders it.

`strategy="codemod"` is not decoration. `migration_outcome` splits merge rate by strategy and
tier precisely so the claim that mechanical changes land more often can be checked rather than
asserted.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from sync.core import Finding, RepoRef, VendorChange
from sync.remediate.literal_swap import LiteralSwapRemediator
from sync.signals.deprecations import ModelDeprecation, to_vendor_changes

SOURCE = """\
import Anthropic from '@anthropic-ai/sdk';

const client = new Anthropic();

export async function summarise(text: string) {
  return client.messages.create({
    model: "claude-3-7-sonnet-20250219",
    max_tokens: 1024,
  });
}
"""

RETIRED = ModelDeprecation(
    vendor_id="anthropic", model_id="claude-3-7-sonnet-20250219", state="retired",
    replacement="claude-opus-4-8", retirement_date=date(2026, 2, 19),
    deprecated_date=None, not_before=None,
)

NO_REPLACEMENT = ModelDeprecation(
    vendor_id="anthropic", model_id="claude-opus-4-20250514", state="retired",
    replacement=None, retirement_date=date(2026, 6, 15), deprecated_date=None, not_before=None,
)


def _change(row: ModelDeprecation = RETIRED) -> VendorChange:
    return to_vendor_changes([row], "2026-07-01", "2026-07-28")[0]


def _finding() -> Finding:
    return Finding(
        detector="deprecation", call_site_id="cs-1", vendor_change_id="vc-1",
        severity="breaking", rationale="retired model in use",
    )


@pytest.fixture()
def repo(tmp_path: Path) -> RepoRef:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "summarise.ts").write_text(SOURCE, encoding="utf-8")
    return RepoRef(repo_id="repo-1", url="https://example.invalid/r", local_path=str(tmp_path), head_sha="abc123")


def _site(path: str = "src/summarise.ts", operation_id: str = "claude-3-7-sonnet-20250219"):
    from sync.core import CallSite

    return CallSite(
        repo_id="repo-1", path=path, line=7, col=11, vendor_id="anthropic",
        operation_id=operation_id, symbol="model", sdk_version="0.70.0", content_hash="h",
    )


# --- can_handle: the gate that keeps the agent's work away from the codemod ---------


def test_it_handles_a_deprecation_with_a_replacement():
    assert LiteralSwapRemediator().can_handle(_finding(), _change()) is True


def test_it_declines_a_deprecation_with_no_replacement():
    """No target, no mechanical edit. Declining sends this to the agent, which is the correct
    fallback -- inventing a successor would ship a confident patch to a model nobody named."""
    assert LiteralSwapRemediator().can_handle(_finding(), _change(NO_REPLACEMENT)) is False


def test_it_declines_a_change_that_is_not_a_deprecation():
    spec_change = VendorChange(
        vendor_id="stripe", from_version="a", to_version="b", kind="response-property-removed",
        operation_id="PostCharges", path_ptr="/v1/charges", severity="breaking",
        source="oasdiff", raw={},
    )
    assert LiteralSwapRemediator().can_handle(_finding(), spec_change) is False


# --- propose ----------------------------------------------------------------------


def test_the_patch_is_a_codemod_not_an_agent_run(repo: RepoRef):
    patch = LiteralSwapRemediator().propose(_finding(), _change(), _site(), repo)
    assert patch.strategy == "codemod"


def test_the_diff_replaces_the_model_and_nothing_else(repo: RepoRef):
    patch = LiteralSwapRemediator().propose(_finding(), _change(), _site(), repo)

    added = [l for l in patch.diff.splitlines() if l.startswith("+") and not l.startswith("+++")]
    removed = [l for l in patch.diff.splitlines() if l.startswith("-") and not l.startswith("---")]

    assert len(added) == 1 and len(removed) == 1
    assert "claude-opus-4-8" in added[0]
    assert "claude-3-7-sonnet-20250219" in removed[0]


def test_the_diff_names_the_file_it_applies_to(repo: RepoRef):
    patch = LiteralSwapRemediator().propose(_finding(), _change(), _site(), repo)
    assert "src/summarise.ts" in patch.diff


def test_the_rationale_carries_the_deadline_a_reviewer_needs(repo: RepoRef):
    """The pull request body is where this feature earns trust. A reviewer approving a
    machine-written change wants the vendor's own reason and date, not "updated model"."""
    patch = LiteralSwapRemediator().propose(_finding(), _change(), _site(), repo)

    assert "claude-3-7-sonnet-20250219" in patch.rationale
    assert "claude-opus-4-8" in patch.rationale
    assert "2026-02-19" in patch.rationale
    assert "retired" in patch.rationale.lower()


def test_a_file_already_migrated_produces_an_empty_diff(repo: RepoRef):
    """Empty means "nothing to do", and the graph already routes an empty diff to abandon.

    Returning a patch that changes nothing would push a branch with no commit and open an
    empty pull request.
    """
    target = Path(repo.local_path) / "src" / "summarise.ts"
    target.write_text(SOURCE.replace("claude-3-7-sonnet-20250219", "claude-opus-4-8"), encoding="utf-8")

    patch = LiteralSwapRemediator().propose(_finding(), _change(), _site(), repo)
    assert patch.diff == ""


def test_a_missing_file_produces_an_empty_diff_rather_than_raising(repo: RepoRef):
    """The index can outlive the file. A deleted path is a stale binding, not a crash."""
    patch = LiteralSwapRemediator().propose(_finding(), _change(), _site(path="src/gone.ts"), repo)
    assert patch.diff == ""


def test_an_unsupported_extension_is_declined(repo: RepoRef):
    (Path(repo.local_path) / "src" / "config.yaml").write_text('model: "claude-3-7-sonnet-20250219"\n', encoding="utf-8")
    patch = LiteralSwapRemediator().propose(_finding(), _change(), _site(path="src/config.yaml"), repo)
    assert patch.diff == ""


def test_the_patch_is_idempotent(repo: RepoRef):
    """Applying the produced diff and re-proposing must yield nothing. The remediation graph
    retries, and a codemod that keeps finding work would loop until the attempt budget runs
    out."""
    remediator = LiteralSwapRemediator()
    target = Path(repo.local_path) / "src" / "summarise.ts"

    first = remediator.propose(_finding(), _change(), _site(), repo)
    assert first.diff

    target.write_text(SOURCE.replace("claude-3-7-sonnet-20250219", "claude-opus-4-8"), encoding="utf-8")
    assert remediator.propose(_finding(), _change(), _site(), repo).diff == ""


def test_it_satisfies_the_remediator_protocol():
    from sync.core.protocols import Remediator

    assert isinstance(LiteralSwapRemediator(), Remediator)


def test_the_edit_reaches_the_clone_and_not_only_the_diff(repo: RepoRef):
    """Nothing in the pipeline applies `patch.diff`.

    `nodes.make_patch` stores the `Patch`, `static_verify` typechecks the working tree, and
    `push_branch` stages it with `git add -u`. A remediator that renders a diff without
    writing it produces a branch with no commit, having reported success.
    """
    LiteralSwapRemediator().propose(_finding(), _change(), _site(), repo)

    on_disk = (Path(repo.local_path) / "src" / "summarise.ts").read_text(encoding="utf-8")
    assert "claude-opus-4-8" in on_disk
    assert "claude-3-7-sonnet-20250219" not in on_disk
