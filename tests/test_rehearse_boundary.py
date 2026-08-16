"""Structural boundary tests for rehearsals.

Rehearsals are structurally prevented from mutating remotes across four independent layers:
1. No push, await_ci, or open_pr node exists in the forge-less compiled graph.
2. The rehearsal driver takes no forge parameter and has no forge annotations.
3. sync.rehearse cannot import sync.forge (enforced by import-linter and AST scanning).
4. The fixture repository has zero remotes configured.
"""

import ast
import inspect
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

from langgraph.checkpoint.memory import InMemorySaver

from sync.rehearse.driver import run_rehearsal
from sync.rehearse.fixture import prepare_fixture
from sync.remediate.graph import build_graph


def test_forge_less_graph_has_no_push_nodes():
    store = MagicMock()
    adapter = MagicMock()
    remediator = MagicMock()
    checkpointer = InMemorySaver()

    graph = build_graph(
        store=store,
        adapter=adapter,
        remediator=remediator,
        forge=None,
        checkpointer=checkpointer,
    )

    nodes = set(graph.get_graph().nodes.keys())
    assert "push_branch" not in nodes, f"push_branch must not exist in forge-less graph: {nodes}"
    assert "await_ci" not in nodes, f"await_ci must not exist in forge-less graph: {nodes}"
    assert "open_pr" not in nodes, f"open_pr must not exist in forge-less graph: {nodes}"


def test_rehearsal_driver_signature_takes_no_forge():
    sig = inspect.signature(run_rehearsal)
    param_names = set(sig.parameters.keys())
    assert "forge" not in param_names, "run_rehearsal must not accept a forge parameter"

    for name, param in sig.parameters.items():
        annotation_str = str(param.annotation)
        assert "forge" not in annotation_str.lower(), (
            f"parameter '{name}' must not be annotated with Forge: {param.annotation}"
        )


def test_rehearse_package_does_not_import_forge():
    rehearse_dir = Path(__file__).resolve().parents[1] / "src" / "sync" / "rehearse"
    for py_file in rehearse_dir.glob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("sync.forge"), (
                        f"{py_file.name} directly imports forbidden module {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert not module.startswith("sync.forge"), (
                    f"{py_file.name} directly imports from forbidden module {module}"
                )


def test_rehearsal_fixture_has_zero_remotes(tmp_path: Path):
    repo = prepare_fixture("furever", root=tmp_path)
    result = subprocess.run(
        ["git", "remote", "-v"],
        cwd=Path(repo.local_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    assert result.stdout.strip() == "", f"expected zero remotes, got: {result.stdout.strip()}"
