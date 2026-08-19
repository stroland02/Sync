---
paths:
  - "web/**"
  - "src/sync/api/**"
  - "src/sync/dashboard/**"
  - "scripts/seed_console.py"
---

# Running the console

`web/CLAUDE.md` carries what the console must not claim. This is how to run one, and what its green
checks do not prove.

## The loop

```sh
SYNC_API_RELOAD=true uv run python -m sync.api   # 8787 — the port vite proxies /api to
uv run python scripts/seed_console.py            # --scale N for synthetic rows; --remove to undo
cd web && npm run dev                            # 5173
```

`SYNC_GRAPH_DSN` names the graph, `SYNC_CHECKPOINTER_DSN` the checkpointer, the second falling back
to the first. **`scripts/seed_console.py` is owned by another session** — use it, do not edit it.

## The trap this file exists for

**A long-lived API process serves whatever Python it started with, and nothing signals the drift.**
Vite hot-reloads, so the frontend is always current — which makes it worse: the screen is new, the
payload is old, and the pairing looks entirely plausible.

On 2026-08-05 that cost half an hour of a verification walk. The process predated the commits being
verified, so the agent would have certified the exact defect it was dispatched to catch.

`SYNC_API_RELOAD=true` closes it structurally. Without it, restart the API or confirm its start time
postdates the last Python commit before believing anything on screen.

## One console, one port, one branch

Set by the owner 2026-08-06, after an afternoon of looking at four consoles unable to tell which was
current. Five workspaces had servers up; Vite picks the next free port on restart, so their URLs
moved; one served a mid-build branch with no API and rendered ninety-two *"The API is unreachable"*
errors.

1. **There is one console the owner looks at: `http://localhost:5173`**, started from the
   coordinator's worktree with `--port 5173 --strictPort`, serving the integration branch. Nothing
   else is ever given to the owner as a URL.
2. **A worker never serves the owner.** A worker's branch is not a preview.
3. **A worker may run a server to verify its own work** — a free port, never mentioned, **stopped
   before reporting.** A server left listening is the defect this exists to stop.
4. **After every merge the coordinator restarts 5173** and says so. Until a merge lands, 5173
   serving the previous tree is correct — say that plainly rather than implying newer work is visible.
5. **One API on 8787.** When it is unavailable, move it with `SYNC_API_PORT` and point the console
   with `SYNC_API_ORIGIN`. **Never edit `vite.config.ts` to reach a port.**

## Stopping a server, and the zombie that answers for it

**Measured 2026-08-06, after an hour debugging the wrong process.** Killing the `python.exe` or
`node.exe` leaves the shell wrapper that launched it alive, still owning the inherited socket. The
port reports `LISTENING` under a PID that does not exist. Walk `ParentProcessId` up through
`bash`/`sh` and stop those too.

- **A process that cannot bind logs `Application startup complete` before the bind error.** A log
  tail stopping there looks like a healthy server. Confirm by asking the socket —
  `Get-NetTCPConnection -LocalPort <n> -State Listen` — never by reading the startup log.
- **Establish *which* process is answering before diagnosing what it is doing wrong.** Every probe
  in that hour was answered by a zombie API from eight hours earlier whose database connection had
  died and which never reconnects (B117).

## The automation browser is not the owner's

`superpowers-chrome` drives one persistent shared Chrome. Any agent that measures a screen resizes
**that window**, and the owner watching sees the console jump widths for no visible reason.

**Every `set_viewport` is paired with a `clear_viewport` before the task ends**, the way a server
started is a server stopped. It is a CDP override on a shared instance: it survives navigation, the
page closing, and the session. Nothing clears it but `clear_viewport`.

**Measured 2026-08-06, after most of a day of confusion.** An override left from the previous day
pinned the console to a fraction of the window in every screenshot the owner took. Two agents
measured `main` at full width and the owner's eyes said otherwise, repeatedly — both correct, same
page, different overrides. A viewport override does not look like a bug; it looks like a CSS defect,
and it will send the next session hunting a `max-width` that does not exist.

## The API stays read-only

No route mutates the graph, triggers a run, or touches a customer repository.
`test_no_route_reaches_past_the_read_surface` holds that behaviourally and extends to every new route.

**One exception, owner-ruled 2026-08-19:** `POST /api/findings/{id}/dismissal` exists and the console
**does not call it**. Dismissing is a command-line action; the console reads the record.

`src/sync/mcp/tools.py` is frozen. The console reads aggregates through `sync.dashboard`, per-finding
answers through `GraphSurface`, and the transport issues no SQL of its own.

## Verification, today

`npm run build` clean, `npm run lint` with no new error-level violations, `npm test` green, and a
stated human observation of the running screen. A scale claim ships with three numbers at
`--scale 10000`: time to first paint, DOM node count, payload size, before and after.
