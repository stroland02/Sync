"""The plugin protocols. A third party implements one of these and never calls it."""

from typing import Protocol


class Remediator(Protocol):
    strategy: str

    def propose(self, finding: object) -> str: ...
