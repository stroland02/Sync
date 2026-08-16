# Brief - M4-W166, B117: `GraphStore` reconnects instead of handing back a dead connection

You are working in your own Orca workspace. **Start by rebasing:**
`git fetch origin && git checkout -B b117-store-reconnect origin/console-identity`. The base is
`console-identity`, which is the integration branch for every workstream right now.

## Stay out of `web/`

**A second session is rebuilding the entire console presentation layer on branch `console-identity`
in parallel with you.** Nothing in `web/`, `DESIGN.md`, `.claude/rules/console-*.md`,
`docs/superpowers/references/direction/`, or the M7 plan is yours. If your change makes you want to
edit a file under `web/`, stop and say so in your report instead - it means the fix has a
presentation consequence that has to be coordinated rather than merged.

Your territory is `src/sync/graph/`, `src/sync/api/`, and `tests/`.

## The defect

`sync.graph.store.GraphStore._connect` caches its connection and reconnects only when the cached
value is `None`:

```python
def _connect(self) -> psycopg.Connection:
    if self._conn is None:
        self._conn = psycopg.connect(self._dsn, row_factory=dict_row, autocommit=True)
    return self._conn
```

A connection that has been **closed** is not `None`. It is handed back forever, and every query on
that store raises `psycopg.OperationalError: the connection is closed`.

`sync.api.__main__.app_factory` builds one `GraphStore` per process and holds it for the process
lifetime. So a single dropped connection takes every console route down until somebody restarts the
process, and nothing anywhere signals which of those two things has happened.

**Measured 2026-08-06.** The operator console rendered unreachable errors on every panel while
Postgres was healthy and idle at 11 of 300 connections, and a `GraphStore` constructed fresh in the
same interpreter answered `repo_ids()` immediately. The API process had been running since 12:40 and
its connection had died at a moment nobody can name. `B117` in `docs/superpowers/BACKLOG.md` carries
this.

## Why this is not excluded by "do not handle conditions that cannot occur"

`CLAUDE.md` says not to add error handling for conditions that cannot occur, and to validate at
system boundaries. **The database is a system boundary and a connection dying is a condition that
occurs** - a server restart, a failover, an idle timeout, an operator restarting the container. This
is squarely inside the rule rather than an exception to it.

## What to build

Test first, and prove the test fails for the reason you expect before writing the fix.

- **The failing test comes first.** Construct a `GraphStore`, run a query, close the underlying
  connection out from under it, run the query again, and watch it raise. That is your RED. The
  fixture is the local Postgres on **port 5433**; `tests/` already has the conftest machinery for it,
  so follow what the existing store tests do rather than inventing a second way to get a database.
- **Then make `_connect` return a live connection.** psycopg exposes `Connection.closed`; a cached
  connection that reports closed is replaced. Keep it to that. **Do not introduce a pool** - one is
  not needed for the case that exists, and `CLAUDE.md`'s "build for the case that exists" applies:
  an unused pool is debt with no asset behind it.
- **Decide what happens to an in-flight transaction and say so.** `_connect` is called inside
  `with self._connect().transaction():` in at least one place. Reconnecting underneath a transaction
  silently would turn a failed write into a silent partial one, which is worse than the bug you are
  fixing. Work out whether that can happen on this code path; if it can, the honest answer may be to
  reconnect only outside a transaction and let the transactional path raise. **Whatever you choose,
  write the reason into the code as a comment stating the constraint** - not narrating the line.
- **A second test proves it reconnects rather than swallowing.** After the reconnect, the query
  returns real rows, and the store is usable for subsequent queries. A fix that catches the error and
  returns an empty result would pass a careless test and would be far worse than the defect: it would
  turn "the database is unreachable" into "there is nothing here", which is the exact confusion the
  five kinds of nothing exist to prevent.

## What must not change

- **`sync.core` imports nothing from any sibling package.** `tests/test_import_boundary.py` enforces
  it.
- **The API stays read-only.** `test_no_route_reaches_past_the_read_surface` holds it behaviourally.
- **Payload shapes do not change.** A second session's console reads these view models and its spec
  states that a port which finds itself editing the data seam has left its brief. The same applies in
  reverse: if this fix would change a field, it has left its brief.
- **`encoding="utf-8"` explicitly** on every `read_text`, `write_text`, `open`, and
  `subprocess.run(..., text=True)`, plus `PYTHONIOENCODING=utf-8` in a child's environment.

## Close the entry

Update `B117` in `docs/superpowers/BACKLOG.md` to closed, with what the fix was and what you decided
about the transactional path. If you find the transactional case is real and you scoped it out, that
is a new entry rather than a silent omission.

## Your gate

```sh
cd <your workspace> && uv run pytest tests/ -q -n0
```

Clean. `docker compose up -d` first if Postgres is not running - it is on **port 5433**, not 5432.
The baseline at `e57a3e7` is 3407 passed, 4 skipped.

You do not need to run the console or the web gates; you are not touching `web/`. If you want to
confirm the fix end to end, run your own API on a free port with `SYNC_API_PORT`, kill its database
connection, and watch the route recover. **5173 and 8789 belong to the owner - leave both alone**,
and stop any server you start, **killing its shell wrapper chain too** and not just the child (B118).

Conventional Commits, subject carrying `M4-W166`. Push your branch. **No pull request, nothing on
`main`.** Send `worker_done` when you finish.
