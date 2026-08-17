import pytest
from starlette.testclient import TestClient

from sync.core.models import CONTEXT_BODY_MAX
from sync.mcp.tools import GraphSurface

# `tests/test_api_app.py` does not exist in this checkout -- `tests/test_api_routes.py` is
# where the app-building helper actually lives, and `_build_app` already defaults every other
# reader to a fake, which is the same role the plan's `app_with` was meant to play.
from tests.test_api_routes import FakeGraph, _build_app


@pytest.fixture()
def written():
    return []


@pytest.fixture()
def client(written):
    stored = {"repo_id": "r", "body": "", "source": None, "updated_at": None}

    def context_reader(repo_id: str) -> dict:
        return {**stored, "repo_id": repo_id}

    def context_writer(repo_id: str, body: str) -> None:
        written.append((repo_id, body))

    app = _build_app(
        surface=GraphSurface(FakeGraph()),
        context_reader=context_reader,
        context_writer=context_writer,
    )
    return TestClient(app)


def test_get_returns_the_view(client):
    response = client.get("/api/repos/github.com%2Facme%2Fstorefront/context")
    assert response.status_code == 200
    assert response.json()["body"] == ""


def test_post_writes_and_returns_the_view(client, written):
    response = client.post(
        "/api/repos/r/context", json={"body": "Package manager is pnpm."}
    )
    assert response.status_code == 200
    assert written == [("r", "Package manager is pnpm.")]


def test_post_with_an_empty_body_is_400_and_writes_nothing(client, written):
    response = client.post("/api/repos/r/context", json={"body": "   "})
    assert response.status_code == 400
    assert written == []


def test_post_with_a_missing_body_key_is_400(client, written):
    assert client.post("/api/repos/r/context", json={}).status_code == 400
    assert written == []


def test_post_with_a_non_string_body_is_400(client, written):
    assert client.post("/api/repos/r/context", json={"body": 7}).status_code == 400
    assert written == []


def test_post_over_the_cap_is_400_naming_the_limit(client, written):
    response = client.post(
        "/api/repos/r/context", json={"body": "x" * (CONTEXT_BODY_MAX + 1)}
    )
    assert response.status_code == 400
    assert str(CONTEXT_BODY_MAX) in response.json()["error"]
    assert written == []


def test_post_exactly_at_the_cap_is_accepted(client, written):
    response = client.post(
        "/api/repos/r/context", json={"body": "x" * CONTEXT_BODY_MAX}
    )
    assert response.status_code == 200
    assert written == [("r", "x" * CONTEXT_BODY_MAX)]
