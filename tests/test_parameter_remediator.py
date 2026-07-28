"""Tier 0 for parameters: a removal produced with no model call.

`LiteralSwapRemediator` handles the swap case. This handles the omit case, which needs the
model as well as the parameter -- removal is scoped to the object that names the model, so the
remediator reads `site.operation_id` rather than guessing which object to edit.

`rename` is declined rather than attempted. Renaming an object key is a different edit from
removing one, and a remediator that half-implements a remedy is worse than one that hands it to
something which can.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sync.core import CallSite, Finding, RepoRef
from sync.core.protocols import Remediator
from sync.remediate.parameter_omit import ParameterOmitRemediator
from sync.signals.deprecations import ParameterDeprecation, parameters_to_vendor_changes

SOURCE = """\
import Anthropic from '@anthropic-ai/sdk';

const client = new Anthropic();

export async function summarise(text: string) {
  return client.messages.create({
    model: "claude-opus-5",
    max_tokens: 1024,
    temperature: 0.7,
    metadata: { temperature: 'unrelated' },
  });
}
"""

OMIT = ParameterDeprecation(
    vendor_id="anthropic", parameter="temperature",
    status="Deprecated (Claude Opus 4.7 and later)",
    behavior="Returns a 400 error when set to a non-default value.",
    applies_from="Claude Opus 4.7 and later",
)

RENAME = ParameterDeprecation(
    vendor_id="anthropic", parameter="budget_tokens", status="Deprecated",
    behavior="Returns a 400 error.", replacement="max_tokens",
)


def _change(row: ParameterDeprecation = OMIT):
    return parameters_to_vendor_changes([row], "2026-07-01", "2026-07-28")[0]


def _finding():
    return Finding(detector="parameter-deprecation", call_site_id="cs-1",
                   severity="deprecation", rationale="passes a deprecated parameter")


def _site(path: str = "src/summarise.ts", model: str = "claude-opus-5"):
    return CallSite(
        id="cs-1", repo_id="r", path=path, line=7, col=4, vendor_id="anthropic",
        operation_id=model, symbol="model", args_keys=["model", "max_tokens", "temperature"],
        sdk_version="0.70.0", content_hash="h",
    )


@pytest.fixture()
def repo(tmp_path: Path) -> RepoRef:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "summarise.ts").write_text(SOURCE, encoding="utf-8")
    return RepoRef(repo_id="r", url="https://example.invalid/r", local_path=str(tmp_path), head_sha="s")


# --- the change carries what the remediator needs ---------------------------------


def test_a_parameter_deprecation_becomes_a_vendor_change():
    change = _change()

    assert change.kind == "deprecation/parameter"
    assert change.operation_id == "temperature"
    assert change.raw["remedy"] == "omit"
    assert change.raw["applies_from"] == "Claude Opus 4.7 and later"


def test_the_change_is_namespaced_away_from_oasdiff_ids():
    assert _change().kind.startswith("deprecation/")
    assert _change().source == "vendor-deprecation-table"


# --- can_handle -------------------------------------------------------------------


def test_it_handles_an_omit():
    assert ParameterOmitRemediator().can_handle(_finding(), _change()) is True


def test_it_declines_a_rename():
    """Renaming a key is a different edit from removing one. Half-implementing a remedy is
    worse than handing it to something that can do it properly."""
    assert ParameterOmitRemediator().can_handle(_finding(), _change(RENAME)) is False


def test_it_declines_a_model_deprecation():
    from sync.signals.deprecations import ModelDeprecation, to_vendor_changes
    from datetime import date

    model_change = to_vendor_changes(
        [ModelDeprecation(vendor_id="anthropic", model_id="m", state="retired",
                          replacement="n", retirement_date=date(2026, 8, 5),
                          deprecated_date=None, not_before=None)],
        "a", "b",
    )[0]
    assert ParameterOmitRemediator().can_handle(_finding(), model_change) is False


# --- propose ----------------------------------------------------------------------


def test_the_patch_is_a_codemod(repo: RepoRef):
    patch = ParameterOmitRemediator().propose(_finding(), _change(), _site(), repo)
    assert patch.strategy == "codemod"


def test_the_diff_removes_only_the_deprecated_argument(repo: RepoRef):
    patch = ParameterOmitRemediator().propose(_finding(), _change(), _site(), repo)

    removed = [l for l in patch.diff.splitlines() if l.startswith("-") and not l.startswith("---")]
    added = [l for l in patch.diff.splitlines() if l.startswith("+") and not l.startswith("+++")]

    assert len(removed) == 1
    assert "temperature: 0.7" in removed[0]
    assert added == []


def test_the_nested_object_is_not_touched(repo: RepoRef):
    """`metadata.temperature` is not this call's argument, and a diff that removed it would
    claim something the finding never said.

    Asserted on the removed lines rather than on the diff text: the nested line sits within
    the hunk's context, so it appears in the diff prefixed with a space. Checking for its
    absence outright would fail on a correct patch.
    """
    patch = ParameterOmitRemediator().propose(_finding(), _change(), _site(), repo)
    removed = [l for l in patch.diff.splitlines() if l.startswith("-") and not l.startswith("---")]

    assert not any("unrelated" in line for line in removed)


def test_the_rationale_carries_the_vendor_wording_and_the_scope(repo: RepoRef):
    patch = ParameterOmitRemediator().propose(_finding(), _change(), _site(), repo)

    assert "temperature" in patch.rationale
    assert "400" in patch.rationale
    assert "Claude Opus 4.7 and later" in patch.rationale
    assert "type-check" in patch.rationale


def test_a_call_site_on_another_model_produces_no_edit(repo: RepoRef):
    """Scope is read from the call site. A model the file does not name means the object this
    finding described is not there, and inventing a target would edit the wrong call."""
    patch = ParameterOmitRemediator().propose(_finding(), _change(), _site(model="gpt-4o"), repo)
    assert patch.diff == ""


def test_an_already_clean_file_produces_an_empty_diff(repo: RepoRef):
    target = Path(repo.local_path) / "src" / "summarise.ts"
    target.write_text(SOURCE.replace("    temperature: 0.7,\n", ""), encoding="utf-8")

    patch = ParameterOmitRemediator().propose(_finding(), _change(), _site(), repo)
    assert patch.diff == ""


def test_a_missing_file_produces_an_empty_diff(repo: RepoRef):
    patch = ParameterOmitRemediator().propose(_finding(), _change(), _site(path="src/gone.ts"), repo)
    assert patch.diff == ""


def test_an_unsupported_extension_is_declined(repo: RepoRef):
    (Path(repo.local_path) / "src" / "conf.yaml").write_text("temperature: 0.7\n", encoding="utf-8")
    patch = ParameterOmitRemediator().propose(_finding(), _change(), _site(path="src/conf.yaml"), repo)
    assert patch.diff == ""


def test_the_patch_is_idempotent(repo: RepoRef):
    remediator = ParameterOmitRemediator()
    target = Path(repo.local_path) / "src" / "summarise.ts"

    first = remediator.propose(_finding(), _change(), _site(), repo)
    assert first.diff

    target.write_text(SOURCE.replace("    temperature: 0.7,\n", ""), encoding="utf-8")
    assert remediator.propose(_finding(), _change(), _site(), repo).diff == ""


def test_it_satisfies_the_remediator_protocol():
    assert isinstance(ParameterOmitRemediator(), Remediator)
