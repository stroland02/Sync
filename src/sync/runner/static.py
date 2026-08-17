"""A runner that reaches no model, so the pipeline can be exercised without a key.

This is what M8 exists for. Every test that drives `locate -> patch -> verify` used to reach
the model through a symbol it replaced inside the SDK's own namespace, which asserted on
another package's internals and could be handed to no caller outside a test.

`edit` stands for what the agent left in the clone, because the clone is how a runner reports
its work: `AgentRemediator.propose` reads the diff from git rather than from a return value.
`error` stands for a run that failed, which the caller must be able to reproduce without the
SDK's result vocabulary -- a test of the abandon path that could not fail a run would only
ever exercise the half of routing where nothing goes wrong.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable


class StaticRunner:
    """Records what it was asked to do, optionally edits the clone, optionally fails."""

    def __init__(
        self,
        edit: Callable[[Path], None] | None = None,
        error: str | None = None,
    ) -> None:
        self._edit = edit
        self._error = error
        self.calls: list[tuple[str, Path, str]] = []

    def run(self, prompt: str, repo_path: Path, identity: str) -> None:
        self.calls.append((prompt, repo_path, identity))
        # Edits land before the failure, which is the order the SDK runner produces: it raises
        # after the run is over, by which time whatever the agent wrote is already in the
        # clone. A runner that failed before editing could not express a run that did half
        # the work and then hit its turn limit.
        if self._edit is not None:
            self._edit(repo_path)
        if self._error is not None:
            raise RuntimeError(self._error)
