#!/usr/bin/env bash
#
# Everything between `docker compose up` and a console on localhost.
#
# The bar this is written against: after the one command, there must be nothing left for a person
# to figure out. So every step that can be done is done here rather than described in a README --
# waiting for the database, applying the schema, starting the API, waiting for it to answer, and
# only then serving the console.
#
# `dev_up.py`'s rule is kept and it is the important one: **half a stack is worse than no stack.**
# A console pointed at an API that never came up presents as a console bug, and the person
# debugging it is debugging the wrong thing. So each step is waited for and a failure says which
# step failed rather than leaving a half-started stack behind.

set -euo pipefail

log() { printf '%s\n' "$*"; }
fail() { printf 'sync: %s\n' "$*" >&2; exit 1; }

: "${SYNC_GRAPH_DSN:?SYNC_GRAPH_DSN is not set; the compose file is supposed to set it}"
: "${SYNC_CONSOLE_PASSWORD:?SYNC_CONSOLE_PASSWORD is not set; the compose file is supposed to set it}"

export SYNC_API_HOST="${SYNC_API_HOST:-127.0.0.1}"
export SYNC_API_PORT="${SYNC_API_PORT:-8787}"
export SYNC_CONSOLE_HOST="${SYNC_CONSOLE_HOST:-0.0.0.0}"
export SYNC_CONSOLE_PORT="${SYNC_CONSOLE_PORT:-4173}"
export SYNC_API_ORIGIN="${SYNC_API_ORIGIN:-http://127.0.0.1:${SYNC_API_PORT}}"

# `SYNC_API_PASSWORD` is deliberately NOT set, and setting it was a real bug caught by running
# this rather than reading it: the console served 200 and every panel behind it got 401.
# `serve-console.mjs` strips `authorization` before proxying to `/api` on purpose -- the console's
# shared credential is not the API's, and the API is not supposed to check it. Giving the API a
# password therefore does not add a boundary, it removes the data from every screen, which is the
# "half a stack" failure this file exists to prevent.
#
# The API needs no credential here because it is not exposed: it binds loopback *inside* this
# container and the compose file publishes no port for it. The console's HTTP Basic gate is the
# boundary, and it is in front of both the console and the proxied API.

# The console binds off-loopback *inside the container* so Docker can publish it. That is not a
# hole: the compose file publishes to 127.0.0.1 on the host, so the surface is the same loopback
# one the guard is protecting, and the credential is set regardless.
export SYNC_CONSOLE_INSECURE="${SYNC_CONSOLE_INSECURE:-i-understand}"

log "sync: waiting for the database"
python - <<'PY'
import os, sys, time
import psycopg

dsn = os.environ["SYNC_GRAPH_DSN"]
deadline = time.monotonic() + 120
last = ""
while time.monotonic() < deadline:
    try:
        psycopg.connect(dsn, connect_timeout=5).close()
        sys.exit(0)
    except psycopg.OperationalError as exc:
        # Starting up and absent are different states and only one is worth waiting on -- but at
        # this point in a compose bring-up both are ordinary, because the database container may
        # not have accepted its first connection yet. The deadline is what makes it honest.
        last = str(exc).strip()
        time.sleep(1)
print(f"sync: the database never became reachable within 120s: {last}", file=sys.stderr)
sys.exit(1)
PY
log "sync: database is up"

log "sync: applying the schema"
python -c "
import os
from sync.graph.store import GraphStore
GraphStore(dsn=os.environ['SYNC_GRAPH_DSN']).apply_schema()
print('sync: schema applied')
"

log "sync: starting the API on ${SYNC_API_HOST}:${SYNC_API_PORT}"
# `SYNC_CONSOLE_PASSWORD` is unset for this process alone, and the reason is a real
# incompatibility that only appears when these two components run together -- which, until this
# image, they never had. `api.auth.configured_api_password` falls back to `SYNC_CONSOLE_PASSWORD`
# when `SYNC_API_PASSWORD` is absent, so merely having the console's credential in the
# environment makes the API demand it; and `serve-console.mjs` deliberately strips
# `authorization` before proxying, because the console's shared credential is not the API's. The
# two are individually reasonable and together they serve a console whose every panel is 401.
# Measured here: console 200, `/api/repositories` 401, which is a fully rendered console with no
# data in it.
env -u SYNC_CONSOLE_PASSWORD python -m sync.api &
api_pid=$!

# The API answering is the precondition for serving the console, so it is waited for rather than
# assumed. A dead API behind a live console is the failure this ordering exists to prevent.
python - <<'PY'
import os, sys, time, urllib.error, urllib.request

url = f"http://127.0.0.1:{os.environ['SYNC_API_PORT']}/api/repositories"
deadline = time.monotonic() + 90
last = ""
while time.monotonic() < deadline:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            if response.status < 500:
                sys.exit(0)
            last = f"HTTP {response.status}"
    except urllib.error.HTTPError as exc:
        # Any answer at all means the process is serving; 401 is an answer.
        if exc.code < 500:
            sys.exit(0)
        last = f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001 -- not up yet is the ordinary case here
        last = str(exc).strip()
    time.sleep(1)
print(f"sync: the API never answered within 90s: {last}", file=sys.stderr)
sys.exit(1)
PY

if ! kill -0 "$api_pid" 2>/dev/null; then
    fail "the API exited while starting; nothing is served rather than serving a console over a dead API"
fi
log "sync: API is answering"

log ""
log "sync: console on http://127.0.0.1:${SYNC_CONSOLE_PUBLISHED_PORT:-$SYNC_CONSOLE_PORT}"
log "sync: password ${SYNC_CONSOLE_PASSWORD}"
log ""

exec node web/scripts/serve-console.mjs
