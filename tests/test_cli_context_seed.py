import os

import pytest

from sync.cli import seed_repo_context
from sync.context import SEED_RELATIVE_PATH
from sync.core import RepoRef
from sync.core.models import RepoContext
from sync.graph.store import GraphStore

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")


@pytest.fixture()
def store():
    s = GraphStore(DSN)
    s.apply_schema()
    s.truncate_all()
    return s


def _repo(tmp_path) -> RepoRef:
    return RepoRef(
        repo_id="github.com/acme/storefront",
        url="https://github.com/acme/storefront",
        local_path=str(tmp_path),
        head_sha="0" * 40,
    )


def _seed_file(tmp_path, text: str) -> None:
    target = tmp_path / SEED_RELATIVE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def test_no_file_writes_no_row(store, tmp_path):
    assert seed_repo_context(store, _repo(tmp_path)) is False
    assert store.repo_context("github.com/acme/storefront") is None


def test_a_file_writes_a_seeded_row(store, tmp_path):
    _seed_file(tmp_path, "Generated code lives under src/generated.")
    assert seed_repo_context(store, _repo(tmp_path)) is True
    found = store.repo_context("github.com/acme/storefront")
    assert found.body == "Generated code lives under src/generated."
    assert found.source == "seeded-file"


def test_seeding_overwrites_an_operator_edit(store, tmp_path):
    """The customer's committed file wins when the two disagree.

    An operator edit to a seeded row is overwritten on the next index, and that is the point:
    the file is the original and the row is a copy of it.
    """
    store.upsert_repo_context(
        RepoContext(
            repo_id="github.com/acme/storefront",
            body="an operator wrote this",
            source="operator",
        )
    )
    _seed_file(tmp_path, "the committed file says this")
    seed_repo_context(store, _repo(tmp_path))
    found = store.repo_context("github.com/acme/storefront")
    assert found.body == "the committed file says this"
    assert found.source == "seeded-file"


def test_no_file_leaves_an_operator_row_alone(store, tmp_path):
    """Absence of a file is not an instruction to erase what an operator wrote."""
    store.upsert_repo_context(
        RepoContext(
            repo_id="github.com/acme/storefront",
            body="an operator wrote this",
            source="operator",
        )
    )
    assert seed_repo_context(store, _repo(tmp_path)) is False
    assert store.repo_context("github.com/acme/storefront").body == "an operator wrote this"


def test_an_unreadable_file_writes_no_row_and_does_not_raise(store, tmp_path):
    target = tmp_path / SEED_RELATIVE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"broken \xff bytes")
    assert seed_repo_context(store, _repo(tmp_path)) is False
    assert store.repo_context("github.com/acme/storefront") is None
