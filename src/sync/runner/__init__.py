"""Everything that knows a model SDK exists.

`sync.remediate` decides what a patch has to be and reads what the clone ended up holding.
This package drives a model to do the editing in between, and it is the only package in the
tree allowed to import a model SDK -- an import-linter contract in `pyproject.toml` says so,
and it was watched failing on all three of the imports that used to sit on the other side.

The point is not layering. It is that the remediation pipeline can be exercised without a
key: `StaticRunner` satisfies the same protocol and reaches no network, so a test can drive
`locate -> patch -> verify` and assert on what the graph does with a patch.

`sync.runner` imports nothing from `sync.remediate`. The gate that narrows what the patch
agent may ask a tool to do is remediation's policy, so `ClaudeSdkRunner` takes it as an
argument rather than reaching for it -- which is also what keeps an ungated runner impossible
to build by forgetting one.
"""

from sync.runner.claude_sdk import ALLOWED_TOOLS, DISALLOWED_TOOLS, MODEL, ClaudeSdkRunner
from sync.runner.static import StaticRunner

__all__ = ["ALLOWED_TOOLS", "DISALLOWED_TOOLS", "MODEL", "ClaudeSdkRunner", "StaticRunner"]
