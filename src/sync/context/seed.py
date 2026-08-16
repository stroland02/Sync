"""Reading the optional context file a customer may commit to their own repository.

`.sync/context.md` is the customer's, not Sync's. It is read and never written: a `seeded-file`
row in the graph is a copy and this file is the original, which is what makes re-indexing a
refresh rather than a conflict.

Every failure here returns None. A malformed optional file must not abandon a remediation run --
context improves a run and is not a precondition for one, and a feature whose broken input
stopped repairs would be riskier to adopt than to ignore.
"""

from __future__ import annotations

from pathlib import Path

from sync.core.models import CONTEXT_BODY_MAX

SEED_RELATIVE_PATH = Path(".sync") / "context.md"


def read_seed(local_path: str | Path) -> str | None:
    """The checkout's context file as text, or None when there is nothing usable to read.

    None covers absent, empty, whitespace-only, unreadable, not valid UTF-8, and over the cap.
    A caller cannot distinguish them and does not need to: every one of them means this
    repository supplied no context, and the log is where the difference belongs.

    Over the cap returns None rather than a truncation. Prose cut mid-sentence and handed to an
    agent that edits code reads as a complete statement and is not one.
    """
    target = Path(local_path) / SEED_RELATIVE_PATH
    try:
        raw = target.read_text(encoding="utf-8")
    except (OSError, ValueError, UnicodeDecodeError):
        # OSError covers absent, a directory in the file's place, and permissions.
        # UnicodeDecodeError is a subclass of ValueError; both are named so the intent survives
        # a reader who does not remember that.
        return None
    body = raw.strip()
    if not body or len(body) > CONTEXT_BODY_MAX:
        return None
    return body
