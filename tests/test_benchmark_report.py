"""The two call sites this task added, and what each of them makes reachable.

Both were on `scripts/dead_links_baseline.txt`: the benchmark axes computed and nothing could
display them, and the two parameter remediators were complete, tested, and absent from the
cascade `cli.build_remediator` composes -- so a finding either of them handles deterministically
reached the agent instead, which is the cost the tiering exists to avoid.

Every assertion below goes through the production surface. A test that constructed
`ParameterOmitRemediator` itself, or called `compute_axes` itself, would re-create exactly the
situation being fixed: the component works and nothing gets to it.
"""

from __future__ import annotations

import argparse
import sys
import os
from pathlib import Path

import pytest

import sync.cli as cli
from sync.benchmark import compute_axes, compute_binding_accuracy
from sync.benchmark.report import axis_rows, render_report
from sync.cli import build_remediator, main
from sync.core import CallSite, Finding, MigrationOutcome, RepoRef
from sync.graph.store import GraphStore
from sync.remediate.agent_patch import AgentRemediator
from sync.remediate.tiered import TierFailed
from sync.signals.deprecations import ParameterDeprecation, parameters_to_vendor_changes

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")


def _outcome(**overrides) -> MigrationOutcome:
    """One corpus row. The grain is an attempt, so a finding that retried three times is three
    of these -- every axis that divides by findings has to say so itself."""
    fields = dict(
        finding_id="f-1", attempt_index=1,
        vendor_id="stripe", from_version="v2320", to_version="v2330",
        change_kind="response-property-removed", change_severity="breaking",
        language="typescript", symbol_shape="stripe.charges.*", arg_arity=2,
        response_fields_touched_count=1,
        strategy="agent", tier=2, wall_ms=1000,
    )
    fields.update(overrides)
    return MigrationOutcome(**fields)


# --- the report -------------------------------------------------------------------


def test_the_report_renders_against_an_empty_corpus():
    """The corpus holds no rows today, so unmeasured is the normal answer and the reporting
    surface has to work before the data exists. One that only rendered once rows arrived could
    not be tested until the day it was needed, which is the day nobody wants to find a bug in
    it.
    """
    report = render_report([])

    assert report.strip()
    assert "routing accuracy" in report.lower()
    assert "n=0" in report


def test_an_axis_with_no_samples_is_unmeasured_and_never_zero():
    """"The merge rate is 0%" and "no attempts have been recorded" are different statements, and
    `Axis` keeps them apart with a null. Flattening that at the rendering step would undo the
    distinction at exactly the point a human reads it, and an empty corpus would report the
    pipeline as failing everything.
    """
    report = render_report([])

    assert "unmeasured" in report
    for zero in ("0.000", "0.0%", " 0 "):
        assert zero not in report, f"an unmeasured axis rendered as {zero!r}"


def test_every_axis_carries_the_sample_size_it_divided_by():
    """A merge rate over four pull requests is not a merge rate. The spec is emphatic that the
    sample size travels with the number, so this asserts it for every axis the report knows
    about rather than for the ones a hand-written list happened to name.
    """
    outcomes = [
        _outcome(finding_id="f-1", pr_number=1, pr_merged=True, tier=0, strategy="codemod"),
        _outcome(finding_id="f-2", pr_number=2, pr_merged=False),
    ]
    report = render_report(outcomes)
    rendered = {line.split("  ")[0].strip(): line for line in report.splitlines() if "n=" in line}

    for label, _ in axis_rows(compute_axes(outcomes), compute_binding_accuracy([], [])):
        assert label in rendered, f"{label} is not rendered on a line carrying its sample size"


def test_a_populated_corpus_reports_real_numbers_with_real_sample_sizes():
    """Two pull requests decided, one merged. The rate and the count are both asserted because
    either alone passes with the other wrong -- and reporting a rate without its denominator is
    the failure mode the spec names in as many words.
    """
    outcomes = [
        _outcome(finding_id="f-1", pr_number=1, pr_merged=True, tier=0, strategy="codemod",
                 static_verify_passed=True, input_tokens=100, output_tokens=50, wall_ms=2000),
        _outcome(finding_id="f-2", pr_number=2, pr_merged=False),
    ]

    report = render_report(outcomes)

    assert "0.500" in report
    assert "n=2" in report
    # Cost is per merged pull request and sums every attempt of those findings: one merged
    # finding, 150 tokens on its single attempt.
    assert "150" in report


def test_binding_accuracy_is_reported_with_the_findings_it_could_not_score():
    """Precision and recall need a labelled reference the corpus cannot supply, so both are
    unmeasured today -- but the exclusion count is part of the answer rather than a footnote.
    Silent exclusion turns a biased sample into an unqualified number, so a finding no label
    covers is counted where the score is read.
    """
    labelled = render_report([], findings=[_emitted("cs-1")], labels=[])

    assert "binding precision" in labelled.lower()
    assert "binding recall" in labelled.lower()
    # One finding emitted, no label to judge it by: excluded from precision and said so.
    assert "1" in _line_for(labelled, "no label")


def test_the_report_states_that_it_gates_nothing():
    """A number rendered beside no verdict is the whole tier B position: recorded, not gated,
    until the movement that counts as a regression is established. The line saying so is what
    stops the next reader adding a threshold to a report that looks like it wants one.
    """
    lowered = render_report([]).lower()

    assert "not gated" in lowered
    for verdict in ("pass", "fail", "threshold exceeded"):
        assert verdict not in lowered


def test_the_report_reaches_a_human_through_the_cli(capsys, monkeypatch):
    """The wiring. `compute_axes` and `compute_binding_accuracy` were finished and had no caller
    in `src/` at all, so "reviewed by a human" had no surface to happen on.
    """
    store = GraphStore(DSN)
    store.apply_schema()
    with store.transaction():
        store.truncate_all()

    # Through the parser rather than through a hand-built namespace. `benchmark` grew two flags
    # for scoring a generated pair, and a namespace assembled by hand goes stale on every one of
    # them -- which fails the wiring test for a reason that has nothing to do with the wiring.
    monkeypatch.setattr(sys, "argv", ["sync", "benchmark", "--dsn", DSN])
    assert main() == 0

    printed = capsys.readouterr().out
    assert "n=0" in printed
    assert "unmeasured" in printed


# --- the cascade ------------------------------------------------------------------

SOURCE = """\
import Anthropic from '@anthropic-ai/sdk';

const client = new Anthropic();

export async function summarise(text: string) {
  return client.messages.create({
    model: "claude-opus-5",
    max_tokens: 1024,
    temperature: 0.7,
    budget_tokens: 512,
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
    behavior="Returns a 400 error.", replacement="max_output_tokens",
)


@pytest.fixture()
def repo(tmp_path: Path) -> RepoRef:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "summarise.ts").write_text(SOURCE, encoding="utf-8")
    return RepoRef(
        repo_id="r", url="https://example.invalid/r", local_path=str(tmp_path), head_sha="s"
    )


@pytest.fixture(autouse=True)
def agent_is_a_failure(monkeypatch):
    """Reaching the agent is the defect, so it fails loudly rather than quietly costing a model
    call. Nothing in this suite may talk to a model API, and a cascade that fell through to the
    agent would otherwise try."""
    def refuse(self, prompt, repo_path, identity):
        raise AssertionError("a parameter deprecation reached the agent tier")

    monkeypatch.setattr(AgentRemediator, "_run_agent", refuse)


def _site(model: str = "claude-opus-5") -> CallSite:
    return CallSite(
        id="cs-1", repo_id="r", path="src/summarise.ts", line=7, col=4, vendor_id="anthropic",
        operation_id=model, symbol="model",
        args_keys=["model", "max_tokens", "temperature", "budget_tokens"],
        sdk_version="0.70.0", content_hash="h",
    )


def _finding() -> Finding:
    return Finding(detector="parameter-deprecation", claim="parameter:model",
                   call_site_id="cs-1",
                   severity="deprecation", rationale="passes a deprecated parameter")


def _emitted(call_site_id: str):
    from sync.benchmark import EmittedFinding

    return EmittedFinding(
        call_site_id=call_site_id, vendor_change_id="vc-1", binding_rung="static"
    )


def _line_for(report: str, needle: str) -> str:
    for line in report.splitlines():
        if needle in line.lower():
            return line
    raise AssertionError(f"no line mentioning {needle!r} in:\n{report}")


def test_the_composites_can_handle_says_nothing_about_which_tier_will_run():
    """A trap worth pinning, because it is the obvious way to write the test below and it
    cannot fail.

    `TieredRemediator.can_handle` is `any(...)` over its tiers and `TerminalTier` answers
    `True` for everything, so the composite claims every change whatever it is composed of --
    with both parameter tiers deleted, with all the codemods deleted. A reachability assertion
    written against it passes through the exact defect this task fixed, which is why the tests
    below go through `propose` and read the strategy of the patch that came back.
    """
    change = parameters_to_vendor_changes([OMIT], "2026-07-01", "2026-07-28")[0]
    unclaimed = change.model_copy(update={"kind": "response-write-only-property-enabled"})

    assert build_remediator().can_handle(_finding(), unclaimed)


@pytest.mark.parametrize(
    "row,gone,present",
    [(OMIT, "temperature: 0.7", "max_tokens"), (RENAME, "budget_tokens", "max_output_tokens")],
)
def test_a_parameter_deprecation_is_repaired_without_a_model_call(repo, row, gone, present):
    """The economic claim, asserted rather than assumed. A deterministic strategy has to be
    tried before the agent, and `TerminalTier` answers `can_handle` with `True` for everything
    -- so a remediator placed after it is never reached however correct it is.
    """
    change = parameters_to_vendor_changes([row], "2026-07-01", "2026-07-28")[0]

    patch = build_remediator().propose(_finding(), change, _site(), repo)

    assert patch.strategy == "codemod"
    assert gone not in Path(repo.local_path, "src", "summarise.ts").read_text(encoding="utf-8")
    assert present in patch.diff


def test_the_cascade_still_reaches_the_agent_for_a_change_no_codemod_handles(repo):
    """The counterweight. Adding tiers must not narrow what the pipeline repairs: a change none
    of the codemods claims still has to reach the agent, which is why the agent tier is terminal
    and never asked whether it can handle anything.
    """
    change = parameters_to_vendor_changes([OMIT], "2026-07-01", "2026-07-28")[0]
    unclaimed = change.model_copy(update={"kind": "response-write-only-property-enabled"})

    # `TierFailed` rather than the raw assertion: the cascade wraps a tier that ran and raised,
    # carrying which tier it was. That wrapper is what proves the agent was reached rather than
    # skipped, so it is asserted on instead of unwrapped.
    with pytest.raises(TierFailed, match="reached the agent tier") as raised:
        build_remediator().propose(_finding(), unclaimed, _site(), repo)

    assert raised.value.tier_strategy == "agent"
