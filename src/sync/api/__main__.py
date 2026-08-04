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
from sync.dashboard.queries import workflow_state
from sync.graph.store import GraphStore
from sync.mcp.tools import GraphSurface

# The port `web/vite.config.ts` proxies `/api` to. Named rather than inlined so
# tests/test_api_routes.py can bind the two together instead of asking them to agree by hand.
DEFAULT_PORT = 8787


def main() -> None:
    dsn = os.environ["SYNC_GRAPH_DSN"]
    checkpointer_dsn = os.environ.get("SYNC_CHECKPOINTER_DSN", dsn)
    store = GraphStore(dsn=dsn)
    surface = GraphSurface(store)

    def workflow_reader(finding_id: str):
        return workflow_state(checkpointer_dsn, finding_id)

    app = create_app(surface=surface, workflow_reader=workflow_reader)
    host = os.environ.get("SYNC_API_HOST", "127.0.0.1")
    port = int(os.environ.get("SYNC_API_PORT", DEFAULT_PORT))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
