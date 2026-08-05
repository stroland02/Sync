"""The bottom of the logging stack: stdlib only, so every `sync.*` package can depend on it.

Nine modules under `sync.*` already call `logging.getLogger(__name__)`, and nothing in the
process ever installs a handler on the root logger -- Python's last-resort handler emits
`WARNING` and above to stderr with no timestamp and no logger name, so every `log.info` and
`log.debug` is discarded before it reaches anyone. `sync.obs.log.configure` is the one place
that changes.
"""

from sync.obs.log import configure

__all__ = ["configure"]
