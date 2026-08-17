import os
from datetime import datetime, timezone

import pytest

from sync.core.models import CONTEXT_SOURCES, RepoContext
from sync.graph.store import GraphStore

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")


@pytest.fixture()
def store():
    s = GraphStore(DSN)
    s.apply_schema()
    s.truncate_all()
    return s


def test_a_repository_with_no_context_reads_as_none(store):
    assert store.repo_context("github.com/acme/storefront") is None


def test_an_upserted_context_reads_back(store):
    store.upsert_repo_context(
        RepoContext(
            repo_id="github.com/acme/storefront",
            body="Package manager is pnpm.",
            source="operator",
        )
    )
    found = store.repo_context("github.com/acme/storefront")
    assert found is not None
    assert found.body == "Package manager is pnpm."
    assert found.source == "operator"
    assert found.updated_at is not None


def test_a_second_upsert_replaces_rather_than_duplicating(store):
    for body, source in (("first", "operator"), ("second", "seeded-file")):
        store.upsert_repo_context(
            RepoContext(repo_id="github.com/acme/storefront", body=body, source=source)
        )
    found = store.repo_context("github.com/acme/storefront")
    assert found.body == "second"
    assert found.source == "seeded-file"
    rows = store._connect().execute(
        "SELECT count(*) AS n FROM repo_context WHERE repo_id = %s",
        ["github.com/acme/storefront"],
    ).fetchone()
    assert rows["n"] == 1


def test_context_is_scoped_to_one_repository(store):
    store.upsert_repo_context(
        RepoContext(repo_id="github.com/acme/one", body="one", source="operator")
    )
    store.upsert_repo_context(
        RepoContext(repo_id="github.com/acme/two", body="two", source="operator")
    )
    assert store.repo_context("github.com/acme/one").body == "one"
    assert store.repo_context("github.com/acme/two").body == "two"


def test_the_declared_sources_are_the_two_this_ships_with():
    """A third source added without a decision is the failure this guards.

    `sync.graph.sources` keeps membership positive for the same reason: a mechanism added and
    left unclassified must be loud rather than silently inside a baseline. Adding `agent` here
    is a deliberate edit that fails this test first.
    """
    assert CONTEXT_SOURCES == frozenset({"seeded-file", "operator"})
