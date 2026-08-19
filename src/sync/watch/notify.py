"""Where the tick hands over findings that did not get a pull request.

Owner decision 4 (2026-08-18) makes notification GitHub-native: the verified pull request is
itself the notification for remediated changes, and non-PR findings open a GitHub issue on the
watched repository. The issue notifier is being built in `sync.forge`, which this package
deliberately does not import -- `tick()` takes a notifier as a callable, and this module is
only the default that stands in until one is injected.

The default is honest rather than empty: it records that the findings have nowhere to go yet
(B94 names the missing delivery destination), because a notification silently swallowed is
indistinguishable from a notification delivered.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from sync.core import Finding


@dataclass(frozen=True)
class Notified:
    """One finding the tick chose not to remediate, with what a notifier needs and the tick
    already knows: the decision's reason and the repository to notify on. A seam that carried
    bare findings forced the notifier to re-derive the reason, which is how two surfaces come
    to disagree about one decision."""

    finding: Finding
    reason: str
    repo_id: str


NotifyFindings = Callable[[Sequence[Notified], Callable[[str], None]], object]


def notify_findings(findings: Sequence[Notified], out: Callable[[str], None]) -> None:
    """The v1 seam: no destination exists, and the tick says so instead of pretending."""
    if not findings:
        return
    out(
        f"watch: notify: {len(findings)} finding(s) have no pull request; "
        "notification pending B94 destination (no notifier configured)"
    )
