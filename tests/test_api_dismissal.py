"""Decision 45's write path: dismissing a finding, and refusing to invent who did it.

Dismissal is the first thing this console writes that is a *judgement* rather than a setting. That
makes the attribution load-bearing in a way a context body's is not: `false_positive` is the only
honest source of detector accuracy, and a number nobody can trace to a person is not evidence.

The route therefore refuses a dismissal it cannot attribute. A console behind one shared password
cannot infer who is typing, so the caller says who, and filling the column with a constant would
satisfy the schema while destroying the only question it exists to answer.
"""

from __future__ import annotations

from starlette.testclient import TestClient

from sync.mcp.tools import GraphSurface
from tests.test_api_routes import FETCHED, FakeGraph, _build_app

VOCABULARY = "not_used_here, intentional, false_positive, wont_fix"


class _Dismissals:
    """A stand-in for the store, refusing the same reasons `record_dismissal` refuses."""

    def __init__(self) -> None:
        self.writes: list[tuple[str, str | None, str]] = []
        self.state = {"dismissed": False, "reason": None, "actor": None, "history_count": 0}

    def read(self, finding_id: str) -> dict:
        return self.state

    def write(self, finding_id: str, *, reason, actor: str) -> None:
        if reason is not None and reason not in {
            "not_used_here", "intentional", "false_positive", "wont_fix",
        }:
            raise ValueError(f"{reason!r} is not a dismissal reason. The vocabulary is closed -- {VOCABULARY}")
        self.writes.append((finding_id, reason, actor))
        self.state = {
            "dismissed": reason is not None,
            "reason": reason,
            "actor": actor,
            "history_count": len(self.writes),
        }


def _client(dismissals: _Dismissals) -> TestClient:
    surface = GraphSurface(FakeGraph(), feed_fetched_at=FETCHED)
    return TestClient(
        _build_app(
            surface=surface,
            dismissal_reader=dismissals.read,
            dismissal_writer=dismissals.write,
        )
    )


def test_a_dismissal_nobody_can_be_attributed_to_is_refused():
    """The column exists so a reader can ask who decided, and this console cannot infer it."""
    dismissals = _Dismissals()

    response = _client(dismissals).post(
        "/api/findings/f1/dismissal", json={"reason": "false_positive"}
    )

    assert response.status_code == 400
    assert "actor is required" in response.json()["error"]
    assert dismissals.writes == [], "nothing may be recorded when the actor is unknown"


def test_a_blank_actor_is_not_an_actor():
    """Whitespace satisfies "a string is present" and answers nobody's question."""
    dismissals = _Dismissals()

    response = _client(dismissals).post(
        "/api/findings/f1/dismissal", json={"reason": "intentional", "actor": "   "}
    )

    assert response.status_code == 400
    assert dismissals.writes == []


def test_a_reason_outside_the_closed_vocabulary_is_refused_by_name():
    """The transport does not restate the vocabulary; it forwards the refusal that owns it.

    A second copy of the closed set inside the API is the fact written twice, and it is the copy
    that would drift first -- so the route's job is to turn the store's refusal into a 400 with
    the store's own words in it.
    """
    dismissals = _Dismissals()

    response = _client(dismissals).post(
        "/api/findings/f1/dismissal", json={"reason": "seems fine", "actor": "sam"}
    )

    assert response.status_code == 400
    assert "vocabulary is closed" in response.json()["error"]
    assert "false_positive" in response.json()["error"], (
        "the refusal must name the vocabulary, or a caller cannot correct it"
    )


def test_dismissing_records_the_reason_and_the_person_and_returns_the_new_standing():
    dismissals = _Dismissals()

    response = _client(dismissals).post(
        "/api/findings/f1/dismissal", json={"reason": "false_positive", "actor": "sam"}
    )

    assert response.status_code == 200
    assert dismissals.writes == [("f1", "false_positive", "sam")]
    assert response.json()["dismissed"] is True
    assert response.json()["reason"] == "false_positive"


def test_restoring_is_a_second_row_rather_than_an_erasure():
    """A finding dismissed and restored has two rows, and the count is how the console shows it.

    Overwriting a column would leave the screen unable to say that somebody changed their mind,
    which is the whole reason decision 45 specifies a row per decision.
    """
    dismissals = _Dismissals()
    client = _client(dismissals)

    client.post("/api/findings/f1/dismissal", json={"reason": "wont_fix", "actor": "sam"})
    restored = client.post("/api/findings/f1/dismissal", json={"reason": None, "actor": "ash"})

    assert restored.json()["dismissed"] is False
    assert restored.json()["history_count"] == 2, "the flip is visible, not erased"
    assert [w[1] for w in dismissals.writes] == ["wont_fix", None]


def test_the_standing_is_readable_without_writing_anything():
    dismissals = _Dismissals()

    response = _client(dismissals).get("/api/findings/f1/dismissal")

    assert response.status_code == 200
    assert response.json()["dismissed"] is False
    assert dismissals.writes == []


def test_a_body_that_is_not_an_object_is_refused_rather_than_indexed():
    dismissals = _Dismissals()

    response = _client(dismissals).post("/api/findings/f1/dismissal", json=["false_positive"])

    assert response.status_code == 400
    assert dismissals.writes == []
