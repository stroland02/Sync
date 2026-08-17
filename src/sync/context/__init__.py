"""Per-repository context: the file a customer may commit, and the prompt section it becomes.

This package knows a file format and a prompt section. It knows nothing about Postgres and
imports no sibling that does -- the same shape as `sync.telemetry`, which knows OTLP and HTTP
and no vendor. It returns data and persists nothing; every write goes through `GraphStore`, and
the caller holds both.
"""

from sync.context.prompt import render_section
from sync.context.seed import SEED_RELATIVE_PATH, read_seed

__all__ = ["SEED_RELATIVE_PATH", "read_seed", "render_section"]
