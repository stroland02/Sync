"""Tests for the rehearsal driver.

Rehearsals drive the pipeline against zero-remote fixtures without ever constructing
or passing a Forge, ensuring remote mutations are impossible.
"""

import argparse
import inspect
from unittest.mock import MagicMock, patch

from sync.core import Finding, OperationRef, RepoRef, VendorChange
from sync.forge.github import GitHubForge
from sync.rehearse.driver import run_rehearsal


def test_run_rehearsal_accepts_no_forge_parameter():
    sig = inspect.signature(run_rehearsal)
    param_names = set(sig.parameters.keys())
    assert "forge" not in param_names, "run_rehearsal must not accept a forge parameter"

    for name, param in sig.parameters.items():
        assert param.annotation != GitHubForge, f"parameter {name} must not be annotated with Forge"


def test_rehearsal_prepare_depth_invokes_no_remediator(tmp_path):
    args = argparse.Namespace(
        depth="prepare",
        limit=1,
        vendor="stripe",
        from_version="v2320",
        to_version="v2330",
        fixture="furever",
        cache=str(tmp_path),
        run_id="rehearsal-test",
        dsn="postgresql://mock",
    )

    mock_repo = RepoRef(
        repo_id="github.com/stripe/stripe-connect-furever-demo",
        url="https://github.com/stripe/stripe-connect-furever-demo",
        local_path=str(tmp_path),
        head_sha="0123456789ab",
    )

    mock_finding = Finding(
        id="finding-1",
        detector="parameter-deprecation",
        claim="param-removed",
        call_site_id="site-1",
        vendor_change_id="change-1",
        binding_rung="static",
        severity="breaking",
        rationale="Test finding",
    )

    mock_graph = MagicMock()
    mock_graph.get_state.return_value = MagicMock(values={})
    mock_graph.invoke.return_value = {
        "outcome": "reported",
        "report_reason": "rehearsal depth 'prepare' halts before remediation",
    }

    with (
        patch("sync.rehearse.driver.prepare_fixture", return_value=mock_repo),
        patch("sync.rehearse.driver.prepare_vendor") as mock_prep_vendor,
        patch("sync.rehearse.driver.select_language_adapter") as mock_sel_adapter,
        patch("sync.rehearse.driver.GraphStore") as mock_store_cls,
        patch("sync.rehearse.driver.parameter_deprecation_sources", return_value=[]),
        patch("sync.rehearse.driver.model_deprecation_sources", return_value=[]),
        patch("sync.rehearse.driver._scan", return_value=[mock_finding]),
        patch("sync.rehearse.driver.PostgresSaver") as mock_saver_cls,
        patch("sync.rehearse.driver.build_graph", return_value=mock_graph) as mock_build_graph,
        patch("sync.rehearse.driver.build_remediator") as mock_build_remediator,
    ):
        mock_adapter = MagicMock()
        mock_adapter.index.return_value = []
        mock_adapter.unread_paths.return_value = []
        mock_adapter.discard_contaminated_dependencies.return_value = False
        mock_sel_adapter.return_value = mock_adapter

        mock_store = MagicMock()
        mock_store_cls.return_value.__enter__.return_value = mock_store
        mock_saver_cls.from_conn_string.return_value.__enter__.return_value = MagicMock()

        exit_code = run_rehearsal(args)

        assert exit_code == 0
        mock_build_remediator.assert_not_called()
        # Verify build_graph was called with forge=None and remediator=None
        _, kwargs = mock_build_graph.call_args
        assert kwargs.get("forge") is None
        assert kwargs.get("remediator") is None


def test_rehearsal_zero_findings_exits_cleanly(tmp_path, capsys):
    args = argparse.Namespace(
        depth="prepare",
        limit=1,
        vendor="stripe",
        from_version="v2320",
        to_version="v2330",
        fixture="furever",
        cache=str(tmp_path),
        run_id=None,
        dsn="postgresql://mock",
    )

    mock_repo = RepoRef(
        repo_id="github.com/stripe/stripe-connect-furever-demo",
        url="https://github.com/stripe/stripe-connect-furever-demo",
        local_path=str(tmp_path),
        head_sha="0123456789ab",
    )

    with (
        patch("sync.rehearse.driver.prepare_fixture", return_value=mock_repo),
        patch("sync.rehearse.driver.prepare_vendor"),
        patch("sync.rehearse.driver.select_language_adapter") as mock_sel_adapter,
        patch("sync.rehearse.driver.GraphStore") as mock_store_cls,
        patch("sync.rehearse.driver.parameter_deprecation_sources", return_value=[]),
        patch("sync.rehearse.driver.model_deprecation_sources", return_value=[]),
        patch("sync.rehearse.driver._scan", return_value=[]),
    ):
        mock_adapter = MagicMock()
        mock_adapter.index.return_value = []
        mock_adapter.unread_paths.return_value = []
        mock_sel_adapter.return_value = mock_adapter

        mock_store = MagicMock()
        mock_store_cls.return_value.__enter__.return_value = mock_store

        exit_code = run_rehearsal(args)

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "0 finding(s)" in captured.out
