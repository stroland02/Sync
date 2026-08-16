"""Turning a context body into the prompt section that carries it.

Kept beside the seed reader rather than in `sync.remediate` so that the text an agent sees and
the file a customer writes are described in one package. Neither of them knows about Postgres.
"""

from __future__ import annotations

_HEADING = "What is true of this repository:"


def render_section(body: str) -> str:
    """The prompt section for one context body, or the empty string for no body.

    The empty string rather than an empty heading. A heading with nothing under it tells an
    agent that somebody looked and found nothing worth saying, which is a claim; no section at
    all is the absence of a claim, and it is also what keeps the prompt byte-identical to the
    one built before this feature existed.
    """
    stripped = body.strip()
    if not stripped:
        return ""
    return f"{_HEADING}\n{stripped}"
