"""PreToolUse fence around the competitor screenshots.

`.claude/rules/interface-originality.md` says the interface is ours and that the 50 screenshots
under `docs/superpowers/references/screenshots/` are a research artifact, never a design target.
That rule used to load on **every turn** -- 86 lines against every task in the repository -- for one
reason: the directory can be opened from anywhere, so no `paths:` frontmatter could fence it.

This is that fence, encoded where it fails. With the read blocked deterministically, the rule scopes
to `web/**` like every other console rule and stops costing a Python session anything.

Blocks the image files only. The notes beside them are the adoptable half -- concepts, workflows,
negative findings -- and blocking those would fence off the research this directory exists for.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

FENCED = ("docs/superpowers/references/screenshots",)
IMAGES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif"}

MESSAGE = (
    "Blocked: this is a competitor screenshot, and the interface is ours.\n"
    "`.claude/rules/interface-originality.md` -- these 50 captures are a research artifact, not a "
    "design target. Concepts, workflows and negative findings transfer; a rendering does not.\n"
    "What you probably want instead: the notes beside them in references/notes/, which restate "
    "what is adoptable as a problem rather than as a picture. If a change cannot be justified "
    "without pointing at a competitor's screen, it has not been justified."
)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    raw = (payload.get("tool_input") or {}).get("file_path")
    if not raw:
        return 0

    # Compared with forward slashes so a Windows path matches the same fence.
    posix = Path(raw).as_posix().lower()
    if not any(fence in posix for fence in FENCED):
        return 0
    if Path(raw).suffix.lower() not in IMAGES:
        return 0

    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
