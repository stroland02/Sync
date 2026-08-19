"""The cheap end of the cheap-poll cascade: what a probe may cost before a scan is justified.

`2026-07-29-sync-adaptive-vendor-substrate.md:441` is the constraint: a tier that must download
every specification to learn nothing changed does not belong in this architecture. `ls-remote`
is one round trip that transfers a ref listing and no objects, which is why it serves both
probes here -- the SDK-repo probe that gates a generated vendor's manifest read, and the
repo-HEAD poll that stands in for M2's push webhook on a deployment a webhook cannot reach.
"""

from __future__ import annotations

import subprocess


def remote_head(remote: str) -> str | None:
    """The commit HEAD points at on a remote, or None when the remote cannot say.

    None rather than a raise, because one unreachable remote must not abort a tick across
    every other subscription -- the caller prints the absence and the next tick retries.
    """
    try:
        result = subprocess.run(
            ["git", "ls-remote", remote, "HEAD"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    first = result.stdout.split(None, 1)
    return first[0] if first else None
