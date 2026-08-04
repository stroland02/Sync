# The Sync operator console

A read-only React front end over Sync's API Dependency Graph. It answers four questions, one
screen each: which vendors this codebase depends on, what is at risk for one of them, what one
finding binds to, and — the screen the rest exists to reach — what Sync actually did about a
finding, node by node, with the evidence each node of the remediation graph produced.

Nothing here writes. Every screen is a GET, and no route in the transport behind it mutates the
graph, starts a remediation run, or touches a customer repository.

## Running it

The console needs the Python API. Start that first, from the repository root:

```sh
uv run python -m sync.api
```

It reads `SYNC_GRAPH_DSN` for the graph and `SYNC_CHECKPOINTER_DSN` for the LangGraph
checkpointer, falling back to the graph DSN when the second is unset. It listens on **port
8787**, which is the port `vite.config.ts` proxies `/api` to; `SYNC_API_PORT` overrides it, and
changing one without the other turns every request into a proxy error.

Then, from this directory:

```sh
npm install
npm run dev
```

`npm run build` typechecks with `tsc -b` and then builds. It is expected to be silent — a
warning here is a defect, because `web/` has no CI gate of its own.

## Where things are

| | |
|---|---|
| The five routes and their payloads | `src/sync/api/app.py` |
| The workflow view's data | `src/sync/dashboard/queries.py` |
| Response types, mirroring both | `src/api/types.ts` |
| Fetching and errors | `src/api/client.ts`, `src/api/errors.ts` |
| One directory per screen | `src/features/` |

Three constants are restated here from Python because TypeScript cannot import it: the default
page size, the remediation graph's node order, and the evidence keys each node produces. Python
tests read these files and fail when the two sides drift — `tests/test_api_routes.py` and
`tests/test_dashboard_queries.py` hold them.
