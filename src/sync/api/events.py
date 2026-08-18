"""Server-sent event frames for `GET /api/events`.

Owner decision 76: the console learns what changed from a stream rather than by polling, and
**there is no polling fallback**. That makes two things this module refuses to do.

**It never invents a time.** Every animation in the console binds to the instant a transition
happened, so a frame that carries the moment it was *emitted* instead would make the whole motion
system state something false with total confidence. An event that arrives without a time is
forwarded without one, and the console renders that absence -- which is a worse-looking screen and
a true one.

**It says nothing while it is quiet.** A stream with no traffic and a stream that has died look
identical on the wire, so a quiet stream sends a comment frame. That is what lets the console tell
"nothing has happened" from "nothing is coming", which is the same distinction the screens make
between a measured zero and an absence.

Frame formatting is separated from the route because the route is a loop and this is the part with
an argument in it.
"""

from __future__ import annotations

import json

# The field an event uses for the instant the transition happened. Named once here because the
# rule that it is never synthesised is only enforceable if there is one place to look.
TRANSITION_TIME = "occurred_at"


def sse_frame(event: dict) -> str:
    """One event as an SSE frame, carrying the event's own kind.

    The kind rides the `event:` line so a client can subscribe to `run.stage` without parsing
    every payload it is sent. `data:` is the event verbatim -- decision 76 chose a fat payload,
    so the canvas draws from the stream rather than refetching once it hears something moved.
    """
    kind = event.get("kind", "message")
    data = json.dumps(event, separators=(",", ":"), sort_keys=True)
    return f"event: {kind}\ndata: {data}\n\n"


def keepalive_frame() -> str:
    """A comment frame, which SSE clients ignore and proxies read as traffic.

    Two jobs, and the second is the one that matters here: it stops an idle connection being
    closed by something in the middle, and it is the evidence that lets the console distinguish a
    quiet stream from a dead one without polling anything.
    """
    return ": quiet\n\n"


async def event_frames(source, repo_id, *, is_disconnected, wait_seconds):
    """The stream itself: frames for one repository until the reader goes away.

    **Async, and that is a leak rather than a style.** `stream.next` blocks, so a plain generator
    would be iterated in a threadpool where it cannot be cancelled -- a reader who closed their
    tab would leave a thread waiting on a subscription forever, one per reader. Awaiting the
    blocking call in a worker keeps this loop cancellable.

    The disconnect is checked before each wait rather than after each event, because the next
    event may never come and a stream nobody is reading should not outlive them by a quiet
    quarter of a minute.

    It lives here rather than inside the route so it can be tested. Driven through HTTP it cannot
    be: an event stream ends when the reader goes away and not when the source runs dry, so a test
    that drained it would never return, and one that closed the connection early hangs the client.
    `is_disconnected` is passed in for exactly that reason -- the route hands it the request's own.
    """
    from anyio import to_thread
    from functools import partial

    with source.subscribe_events(repo_id) as stream:
        while not await is_disconnected():
            event = await to_thread.run_sync(partial(stream.next, timeout=wait_seconds))
            # `None` is quiet rather than broken, and the two must not look alike on the wire:
            # a comment frame is what lets the console tell a stream with nothing to say from
            # one that has died.
            yield sse_frame(event) if event is not None else keepalive_frame()
