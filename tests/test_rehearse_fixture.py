"""Tests for rehearsal fixture preparation.

A rehearsal fixture is a local git repository materialised from the pinned corpus,
holding exactly one commit and zero remotes.
"""

import subprocess
from pathlib import Path

import pytest

from sync.core import RepoRef
from conftest import require_corpus
from sync.rehearse.fixture import prepare_fixture


def _git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return result.stdout.strip()


def test_prepare_fixture_produces_git_repo_with_zero_remotes_and_single_commit(tmp_path: Path):
    require_corpus("furever")
    repo = prepare_fixture("furever", root=tmp_path)

    assert isinstance(repo, RepoRef)
    assert repo.repo_id == "github.com/stripe/stripe-connect-furever-demo"
    assert "\\" not in repo.repo_id
    assert ":" not in repo.repo_id
    assert Path(repo.local_path).exists()
    assert (Path(repo.local_path) / ".git").exists()

    # Zero remotes - assert git remote -v is empty output
    remotes = _git(["remote", "-v"], cwd=Path(repo.local_path))
    assert remotes == "", f"expected zero remotes, got: {remotes}"

    # Exactly one commit
    log = _git(["log", "--oneline"], cwd=Path(repo.local_path))
    assert len(log.splitlines()) == 1
    assert repo.head_sha == _git(["rev-parse", "HEAD"], cwd=Path(repo.local_path))

    # Explicit author, not dependent on global git config
    author = _git(["log", "-1", "--format=%an <%ae>"], cwd=Path(repo.local_path))
    assert author == "Sync Rehearse <sync@sync.invalid>"


def test_prepare_fixture_is_idempotent_and_converges(tmp_path: Path):
    require_corpus("furever")
    repo1 = prepare_fixture("furever", root=tmp_path)
    repo2 = prepare_fixture("furever", root=tmp_path)

    assert repo1.head_sha == repo2.head_sha
    assert repo1.repo_id == repo2.repo_id
    assert repo1.local_path == repo2.local_path

    # Still exactly one commit
    log = _git(["log", "--oneline"], cwd=Path(repo1.local_path))
    assert len(log.splitlines()) == 1


def test_prepare_fixture_raises_on_missing_corpus(tmp_path: Path):
    with pytest.raises(RuntimeError, match="scripts/fetch_corpus_repositories.py"):
        prepare_fixture("nonexistent_fixture_name", root=tmp_path)
