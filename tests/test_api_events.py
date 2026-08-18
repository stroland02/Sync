"""`GET /api/events`, and the two things it must never do.

Decision 76 put the console on a stream with no polling fallback. That makes the honesty of a
frame load-bearing in a way a request/response route's is not: a screen that polls re-reads the
truth every few seconds and self-corrects, and a screen driven by a stream believes what it was
told until it is told otherwise.
"""

from __future__ import annotations

import asyncio
import json

from tests.test_api_routes import FETCHED, FakeGraph, _build_app
from starlette.testclient import TestClient

from sync.api.events import (
    event_frames,
    keepalive_frame,
    sse_frame,
)
from sync.mcp.tools import GraphSurface


def test_a_frame_carries_the_events_kind_on_its_own_line():
    """A client subscribes to `run.stage` without parsing every payload it is sent."""
    frame = sse_frame({"kind": "run.stage", "repo_id": "r1"})

    assert frame.startswith("event: run.stage\n")
    assert frame.endswith("\n\n")


def test_a_frame_carries_the_whole_event_because_the_payload_is_fat_by_decision():
    frame = sse_frame(
        {"kind": "call_site.indexed", "repo_id": "r1", "path": "src/billing.ts"}
    )

    data = json.loads(frame.split("data: ", 1)[1].strip())
    assert data["path"] == "src/billing.ts"


def test_an_event_without_a_transition_time_is_forwarded_without_one():
    """The emit time is knowable and wrong, which makes it the most tempting wrong answer.

    Every animation binds to when the transition happened. Stamping `now()` here would make the
    motion system state something false with total confidence -- and it would look right.
    """
    event = {"kind": "call_site.indexed", "repo_id": "r1"}

    frame = sse_frame(event)

    data = json.loads(frame.split("data: ", 1)[1].strip())
    assert "occurred_at" not in data


def test_a_transition_time_the_event_carries_is_forwarded_intact():
    event = {"kind": "run.stage", "repo_id": "r1", "occurred_at": "2026-08-18T09:00:00+00:00"}

    data = json.loads(sse_frame(event).split("data: ", 1)[1].strip())

    assert data["occurred_at"] == "2026-08-18T09:00:00+00:00"


def test_a_quiet_stream_says_so_rather_than_saying_nothing():
    """Silence and death are identical on a socket, and the console must tell them apart."""
    assert keepalive_frame().startswith(":")
    assert keepalive_frame().endswith("\n\n")


class _FakeStream:
    def __init__(self, events):
        self._events = list(events)

    def next(self, timeout: float):
        return self._events.pop(0) if self._events else None


class _FakeEvents:
    """Stands in for `GraphStore`, which satisfies this shape already."""

    def __init__(self, events=()):
        self._events = events
        self.asked_for = None

    def subscribe_events(self, repo_id: str):
        from contextlib import contextmanager

        self.asked_for = repo_id

        @contextmanager
        def _cm():
            yield _FakeStream(self._events)

        return _cm()


def _client(events_reader=None) -> TestClient:
    surface = GraphSurface(FakeGraph(), feed_fetched_at=FETCHED)
    return TestClient(_build_app(surface=surface, events_reader=events_reader))


def test_the_stream_refuses_an_unscoped_request():
    """Every page is scoped to a workspace, and an unscoped stream would leak another one's."""
    response = _client(events_reader=_FakeEvents()).get("/api/events")

    assert response.status_code == 400


def test_a_deployment_without_an_event_source_says_so_rather_than_streaming_nothing():
    """An empty stream and an absent one look identical, and only one is worth waiting on."""
    response = _client(events_reader=None).get("/api/events?repo_id=r1")

    assert response.status_code == 503
    assert "stream" in response.json()["error"].lower()


def _drive(source, repo_id, *, disconnect_after):
    """Run the stream, reporting disconnected once it has been asked `disconnect_after` times."""
    asked = []

    async def is_disconnected():
        asked.append(1)
        return len(asked) > disconnect_after

    async def drive():
        return [
            frame
            async for frame in event_frames(
                source, repo_id, is_disconnected=is_disconnected, wait_seconds=0.01
            )
        ]

    return asyncio.run(drive())


def test_the_stream_yields_a_frame_for_each_event_and_says_so_when_quiet():
    source = _FakeEvents(events=[{"kind": "run.stage", "repo_id": "r1"}])

    frames = _drive(source, "r1", disconnect_after=2)

    assert frames[0].startswith("event: run.stage")
    # The source is dry, and dry is quiet rather than finished -- the stream says so.
    assert frames[1] == keepalive_frame()


def test_the_stream_ends_when_the_reader_goes_away():
    """Checked before each wait, not after each event.

    The next event may never come, and a stream nobody is reading should not outlive them
    by a quiet quarter of a minute holding a database connection open.
    """
    frames = _drive(_FakeEvents(), "r1", disconnect_after=0)

    assert frames == []


def test_the_stream_subscribes_to_the_repository_it_was_asked_for():
    """Scope is the route's, and the subscription honours it rather than opening the fleet."""
    source = _FakeEvents()

    _drive(source, "r1", disconnect_after=1)

    assert source.asked_for == "r1"
