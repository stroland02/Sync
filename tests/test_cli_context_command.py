import io
import os

import pytest

from sync.cli import main
from sync.core.models import RepoContext
from sync.graph.store import GraphStore

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")


@pytest.fixture()
def store():
    s = GraphStore(DSN)
    s.apply_schema()
    s.truncate_all()
    return s


def test_show_prints_nothing_and_exits_zero_when_there_is_no_context(store, capsys, monkeypatch):
    monkeypatch.setattr("sys.argv", ["sync", "context", "show", "--repo-id", "r", "--dsn", DSN])
    assert main() == 0
    assert capsys.readouterr().out.strip() == ""


def test_show_prints_the_body(store, capsys, monkeypatch):
    store.upsert_repo_context(RepoContext(repo_id="r", body="pnpm", source="operator"))
    monkeypatch.setattr("sys.argv", ["sync", "context", "show", "--repo-id", "r", "--dsn", DSN])
    assert main() == 0
    assert "pnpm" in capsys.readouterr().out


def test_set_from_a_file_writes_an_operator_row(store, tmp_path, monkeypatch):
    source_file = tmp_path / "ctx.md"
    source_file.write_text("Generated code lives under src/generated.", encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        ["sync", "context", "set", "--repo-id", "r", "--body", str(source_file), "--dsn", DSN],
    )
    assert main() == 0
    found = store.repo_context("r")
    assert found.body == "Generated code lives under src/generated."
    assert found.source == "operator"


def test_set_from_stdin_writes_an_operator_row(store, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("read from stdin"))
    monkeypatch.setattr(
        "sys.argv", ["sync", "context", "set", "--repo-id", "r", "--body", "-", "--dsn", DSN]
    )
    assert main() == 0
    assert store.repo_context("r").body == "read from stdin"


def test_set_over_the_cap_writes_nothing_and_exits_non_zero(store, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("x" * 8001))
    monkeypatch.setattr(
        "sys.argv", ["sync", "context", "set", "--repo-id", "r", "--body", "-", "--dsn", DSN]
    )
    assert main() != 0
    assert "8000" in capsys.readouterr().err
    assert store.repo_context("r") is None


def test_set_with_an_empty_body_writes_nothing_and_exits_non_zero(store, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("   \n "))
    monkeypatch.setattr(
        "sys.argv", ["sync", "context", "set", "--repo-id", "r", "--body", "-", "--dsn", DSN]
    )
    assert main() != 0
    assert store.repo_context("r") is None
