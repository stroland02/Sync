"""Unit tests for the CLI's testable seams: argument parsing and findings
selection. `run()` itself is wiring against Postgres, the network, and the
Agent SDK -- none of which a unit test may touch -- so these tests reach only
the argparse setup and the `_select` helper that `run()` calls into.
"""

import sys

import pytest

from sync.cli import _select, main


def test_no_arguments_exits_nonzero_instead_of_crashing(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["sync"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code != 0


def test_run_with_missing_required_arguments_exits_nonzero(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["sync", "run"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code != 0


def test_limit_zero_selects_every_finding():
    findings = ["a", "b", "c"]
    assert _select(findings, 0) == findings


def test_limit_one_selects_only_the_first_finding():
    findings = ["a", "b", "c"]
    assert _select(findings, 1) == ["a"]


def test_limit_larger_than_the_findings_selects_all_of_them():
    findings = ["a", "b"]
    assert _select(findings, 5) == ["a", "b"]
