"""Run the operator-console HTTP transport with uvicorn.

`python -m sync.api` starts a local server bound to the graph store the environment names, so
the frontend has one process to talk to during development. The GraphStore and checkpointer
DSNs come from environment variables rather than argv because a deployment already has them,
and duplicating one for a flag would let the two drift apart silently.
"""

from __future__ import annotations

import os

import uvicorn

from sync.api.app import create_app
from sync.dashboard import fleet
from sync.dashboard.queries import workflow_state
from sync.graph.store import GraphStore
from sync.mcp.tools import GraphSurface
from sync.obs.log import configure as configure_logging

# The port `web/vite.config.ts` proxies `/api` to. Named rather than inlined so
# tests/test_api_routes.py can bind the two together instead of asking them to agree by hand.
DEFAULT_PORT = 8787

# INFO rather than the stdlib's WARNING default: the module loggers beneath this transport
# call `log.info`, and a quieter default would leave them exactly as unreachable as before
# this module existed.
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FORMAT = "text"


def main() -> None:
    configure_logging(
        level=os.environ.get("SYNC_LOG_LEVEL", DEFAULT_LOG_LEVEL),
        fmt=os.environ.get("SYNC_LOG_FORMAT", DEFAULT_LOG_FORMAT),
    )
    dsn = os.environ["SYNC_GRAPH_DSN"]
    checkpointer_dsn = os.environ.get("SYNC_CHECKPOINTER_DSN", dsn)
    store = GraphStore(dsn=dsn)
    surface = GraphSurface(store)

    def workflow_reader(finding_id: str):
        return workflow_state(checkpointer_dsn, finding_id)

    def runs_reader(*, limit: int, offset: int):
        return fleet.runs(checkpointer_dsn, limit=limit, offset=offset)

    def corpus_reader():
        return fleet.corpus_summary(store)

    def repositories_reader():
        return fleet.repositories(store)

    app = create_app(
        surface=surface,
        workflow_reader=workflow_reader,
        runs_reader=runs_reader,
        corpus_reader=corpus_reader,
        repositories_reader=repositories_reader,
    )
    host = os.environ.get("SYNC_API_HOST", "127.0.0.1")
    port = int(os.environ.get("SYNC_API_PORT", DEFAULT_PORT))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
