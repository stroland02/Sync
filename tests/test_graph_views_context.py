import os

import pytest

from sync.core.models import RepoContext
from sync.dashboard import graph_views
from sync.graph.store import GraphStore

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")


@pytest.fixture()
def store():
    s = GraphStore(DSN)
    s.apply_schema()
    s.truncate_all()
    return s


def test_a_repository_with_no_context_echoes_its_scope_and_an_empty_body(store):
    """A payload that names the scope it was computed in cannot be rendered under the wrong
    heading in silence -- the convention every repository-scoped view in this module keeps."""
    view = graph_views.repo_context(store, "github.com/acme/storefront")
    assert view["repo_id"] == "github.com/acme/storefront"
    assert view["body"] == ""
    assert view["source"] is None
    assert view["updated_at"] is None


def test_a_stored_context_renders_with_its_source(store):
    """`source` is rendered because the precedence rule surprises anyone who meets the body
    without it: a seeded row is overwritten on the next index and an operator row is not."""
    store.upsert_repo_context(
        RepoContext(
            repo_id="github.com/acme/storefront",
            body="Package manager is pnpm.",
            source="seeded-file",
        )
    )
    view = graph_views.repo_context(store, "github.com/acme/storefront")
    assert view["body"] == "Package manager is pnpm."
    assert view["source"] == "seeded-file"
    assert isinstance(view["updated_at"], str)


def test_the_view_returns_primitives_rather_than_a_live_model(store):
    store.upsert_repo_context(
        RepoContext(repo_id="r", body="b", source="operator")
    )
    view = graph_views.repo_context(store, "r")
    assert isinstance(view, dict)
    assert not isinstance(view["updated_at"], object.__class__) or isinstance(view["updated_at"], str)
    assert all(isinstance(v, (str, type(None))) for v in view.values())
