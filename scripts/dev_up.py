"""Bring the console up against real data, or say precisely why it cannot.

The owner's words are that dev local has been *tediously difficult* to use for replicating the
references and the demos. Doing it by hand today means a seeded database, an API that starts, a dev
server, and knowing which of those is currently broken and what the workaround is — and the
workaround is knowledge one lane acquired an hour ago and nobody else has.

So this checks every precondition first and starts nothing until they all hold. **Half a stack is
worse than no stack**: a dev server pointed at an API that never came up looks like a console bug,
and the person debugging it is debugging the wrong thing. The failure that costs an afternoon is
not the missing precondition, it is the missing precondition that presents as something else.

`--check` reports without starting anything, which is what the test executes. Every failure names
the command that fixes it, because a check that says a thing is missing without saying how to get
it has moved the search rather than ended it.

**It does not route around a broken entrypoint.** When `python -m sync.api` was raising `NameError`
this reported it, named the owning lane and offered no fix command, rather than quietly using
`uvicorn --factory` — which starts the app and hides the defect behind a convenience, and is how a
repository accumulates knowledge that lives in one person's head. That entrypoint is fixed now and
the check went green without a change here, which is what building around a defect rather than into
it buys.

**Preconditions passing is not the same as the stack being up.** The API is started first and the
console only once it answers, because the realistic failure — a port already in use — happens after
every check has passed, and a console pointed at a dead API presents as a console bug.
"""

from __future__ import annotations

import argparse
import inspect
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]

OK = "ok"
MISSING = "missing"


@dataclass(frozen=True)
class Check:
    """One precondition, what it is for, and the command that satisfies it."""

    name: str
    status: str
    detail: str
    fix: str | None = None


CONNECT_TIMEOUT_SECONDS = 5
"""How long to wait before calling the database unreachable.

Short on purpose. psycopg's default is long enough that an absent database makes this command look
hung, and a launcher that hangs on a missing precondition has reproduced the problem it exists to
solve -- the person waiting cannot tell it from a slow start.
"""


def _default_dsn() -> str:
    from sync.graph.store import DEFAULT_DSN

    dsn = os.environ.get("SYNC_GRAPH_DSN", DEFAULT_DSN)
    if "connect_timeout" in dsn:
        return dsn
    return f"{dsn}{'&' if '?' in dsn else '?'}connect_timeout={CONNECT_TIMEOUT_SECONDS}"


def check_postgres() -> Check:
    from sync.graph.store import GraphStore

    dsn = _default_dsn()
    try:
        GraphStore(dsn=dsn).missing_tables()
    except Exception as exc:  # noqa: BLE001 -- any failure to reach it is the same answer
        return Check(
            "postgres",
            MISSING,
            f"cannot reach the graph database: {exc}",
            "docker compose up -d",
        )
    return Check("postgres", OK, f"reachable at {dsn.rsplit('@', 1)[-1]}")


def check_schema() -> Check:
    from sync.graph.store import GraphStore

    try:
        missing = GraphStore(dsn=_default_dsn()).missing_tables()
    except Exception as exc:  # noqa: BLE001
        return Check("schema", MISSING, f"cannot be read: {exc}", "docker compose up -d")
    if missing:
        return Check(
            "schema",
            MISSING,
            f"{len(missing)} table(s) absent, including {missing[0]}",
            "uv run python scripts/seed_console.py",
        )
    return Check("schema", OK, "every table the schema declares is present")


def check_seeded() -> Check:
    """Data, not just tables. A console against an empty database renders empty states correctly
    and teaches a reader nothing about whether a screen works."""
    from sync.graph.store import GraphStore

    try:
        store = GraphStore(dsn=_default_dsn())
        rows = store._connect().execute("SELECT count(*) AS n FROM call_site").fetchone()["n"]
    except Exception as exc:  # noqa: BLE001
        return Check("seeded", MISSING, f"cannot be counted: {exc}", "docker compose up -d")
    if not rows:
        return Check(
            "seeded",
            MISSING,
            "call_site is empty, so every screen renders its empty state",
            "uv run python scripts/seed_console.py",
        )
    return Check("seeded", OK, f"{rows} call site(s) present")


def undefined_names_in(function: Callable) -> list[str]:
    """Names a function calls that its own module does not define.

    A cheap static read rather than starting the process, because the failure this catches is a
    `NameError` raised only when the line runs — which for an entrypoint means after the terminal
    has already printed a startup banner, and reads as a crash rather than as a missing symbol.
    """
    module = sys.modules.get(function.__module__)
    if module is None:
        return []
    called = set(re.findall(r"\b([a-z_][a-z_0-9]{3,})\s*\(", inspect.getsource(function)))
    return sorted(
        name
        for name in called
        if not hasattr(module, name) and not hasattr(__builtins__, name)
    )


def check_api_entrypoint() -> Check:
    """`python -m sync.api`, as documented, and not a workaround for it."""
    try:
        from sync.api import __main__ as entrypoint
    except Exception as exc:  # noqa: BLE001
        return Check("api entrypoint", MISSING, f"will not import: {exc}", None)

    undefined = undefined_names_in(entrypoint.main)
    if undefined:
        return Check(
            "api entrypoint",
            MISSING,
            (
                f"`python -m sync.api` raises NameError: main() calls {', '.join(undefined)}, "
                "which src/sync/api/__main__.py does not define. That file is Lane E's and this "
                "launcher deliberately does not work around it"
            ),
            None,
        )
    return Check("api entrypoint", OK, "python -m sync.api resolves every name main() calls")


API_PORT = int(os.environ.get("SYNC_API_PORT", "8787"))


def port_is_free(port: int, host: str = "127.0.0.1") -> bool:
    import socket

    with socket.socket() as probe:
        try:
            probe.bind((host, port))
        except OSError:
            return False
    return True


def check_api_port(port: int = API_PORT) -> Check:
    """Whether the API's port is free, asked before anything is started.

    **This exists because the readiness poll could be satisfied by somebody else's server.**
    Measured: with a stale API still holding 8787, a newly started one failed to bind with
    `[Errno 10048] only one usage of each socket address` and exited, while the poll got `200` from
    the old process, called the API ready, and started the console against it. The check proved
    "something answers on this port", which is not the question anyone was asking.

    A precondition that passes for the wrong reason is worse than one that fails, and this one hid
    a dead API behind a live port — the half stack this command exists to refuse, wearing the
    costume of a working one.
    """
    if not port_is_free(port):
        return Check(
            "api port",
            MISSING,
            (
                f"something is already listening on {port}, so a new API cannot bind and a "
                "readiness check would answer from whatever is already there"
            ),
            "stop it, or set SYNC_API_PORT to a free port",
        )
    return Check("api port", OK, f"{port} is free")


def npm_executable() -> str | None:
    """`npm` as Windows can actually execute it.

    On this platform npm is `npm.cmd`, and `subprocess.run(["npm", ...])` without a shell raises
    `FileNotFoundError: [WinError 2]` -- a traceback rather than a precondition, from a launcher
    whose whole purpose is to turn missing preconditions into sentences. `shutil.which` resolves
    the `.CMD` form, which is the same fix `CLAUDE.md` already records for the corepack shims.
    """
    return shutil.which("npm")


def check_npm() -> Check:
    if npm_executable() is None:
        return Check(
            "npm",
            MISSING,
            "npm is not on PATH, so the console dev server cannot be started",
            "install Node.js, which supplies npm",
        )
    return Check("npm", OK, f"resolved to {npm_executable()}")


def check_console_dependencies() -> Check:
    if not (REPO_ROOT / "web" / "node_modules").is_dir():
        return Check(
            "console dependencies",
            MISSING,
            "web/node_modules is absent, so the dev server cannot start",
            "npm install --prefix web",
        )
    return Check("console dependencies", OK, "web/node_modules present")


CHECKS: tuple[Callable[[], Check], ...] = (
    check_postgres,
    check_schema,
    check_seeded,
    check_api_entrypoint,
    check_api_port,
    check_npm,
    check_console_dependencies,
)


def run_checks() -> list[Check]:
    """In dependency order, so the first failure is the one worth reading.

    Every check runs even after one fails. A reader who fixes the first thing and re-runs to find
    a second has paid twice for one answer, and this is a command whose whole purpose is to stop
    that.
    """
    return [check() for check in CHECKS]


def render(checks: Sequence[Check]) -> str:
    lines = []
    for check in checks:
        mark = "  ok " if check.status == OK else "MISSING"
        lines.append(f"{mark}  {check.name}: {check.detail}")
        if check.fix:
            lines.append(f"          fix: {check.fix}")
    missing = [c for c in checks if c.status != OK]
    lines.append("")
    if missing:
        lines.append(
            f"{len(missing)} precondition(s) missing, so nothing was started. "
            "A dev server against an API that never came up looks like a console bug."
        )
    else:
        lines.append("every precondition holds")
    return "\n".join(lines)


def api_url() -> str:
    """Where readiness is checked, derived from the port the API was told to bind.

    **This was hardcoded to 8787 while `API_PORT` honoured `SYNC_API_PORT`**, so following this
    script's own advice -- its busy-port message says *"set SYNC_API_PORT to a free port"* -- moved
    the API and left the probe behind. The same message says a busy port means *"a readiness check
    would answer from whatever is already there"*, which is exactly what then happened: the probe
    hit the old port, another lane's API answered it, and the stack reported ready on the strength
    of somebody else's server. Measured on a machine where another lane genuinely held 8787.

    A function rather than a module constant because `API_PORT` is read at import time, and a
    constant computed beside it would freeze the first value any test or caller happened to set.
    """
    return f"http://127.0.0.1:{API_PORT}/api/overview"
CONSOLE_URL = "http://localhost:5173"
"""`localhost` rather than `127.0.0.1`, and that is not cosmetic.

Vite binds IPv6-only here, so `127.0.0.1:5173` refuses the connection while `localhost:5173`
serves. A launcher whose purpose is removing tedium must not hand somebody the address that fails
— they read it as a broken dev server, which is the same wrong-component diagnosis this command
exists to prevent.
"""

API_READY_TIMEOUT_SECONDS = 30


def wait_for_api(process, url: str | None = None, timeout: float = API_READY_TIMEOUT_SECONDS):
    """Whether the API is actually serving, or why it is not.

    Preconditions passing says the API *can* start. It does not say it did, and the realistic
    failure — a port already in use because somebody has the loop running in another terminal —
    happens after every check has passed.
    """
    # Resolved here rather than in the signature: a default evaluated at import time would
    # freeze the port before any caller could set it.
    url = api_url() if url is None else url
    import urllib.error
    import urllib.request

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        code = process.poll()
        if code is not None:
            return False, f"exited with code {code} before it answered"
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                return True, f"answered {response.status} on {url}"
        except urllib.error.HTTPError as exc:
            # A 4xx or 5xx is still the server answering, which is what this asks.
            return True, f"answered {exc.code} on {url}"
        except Exception:  # noqa: BLE001 -- not up yet is the ordinary case
            time.sleep(0.5)
    return False, f"did not answer {url} within {timeout:.0f}s"


def _api_environment() -> dict[str, str]:
    """The API's environment, with the console's credential taken out of it.

    `B187`, met a second time and in a second place. `sync.api.auth.configured_api_password` falls
    back to `SYNC_CONSOLE_PASSWORD` when `SYNC_API_PASSWORD` is unset, so merely *having* the
    console's credential in the environment makes the API demand it -- while
    `web/scripts/serve-console.mjs` strips `authorization` before proxying, deliberately, because
    the console's shared credential is not the API's. The two are individually reasonable and
    together they serve a console whose every panel is 401.

    Measured here: with `SYNC_CONSOLE_PASSWORD` exported, `GET /api/repositories` answered 401 and
    the console rendered with nothing in it. The container hit exactly this and fixed it the same
    way; this is the local dev loop's half of the same defect, which is why it is worth fixing
    rather than working around at the shell.

    The API needs no credential here for the same reason it needs none in the container: it binds
    loopback and is not published. The console's own gate is the boundary, and it sits in front of
    both the console and the proxied API.
    """
    environment = dict(os.environ)
    environment.pop("SYNC_CONSOLE_PASSWORD", None)
    return environment


def start_loop(*, start_api=None, start_console=None, wait_ready=None) -> int:
    """Start the API, wait until it serves, and only then start the console.

    **The console is never started against an API that did not come up.** Checking preconditions
    catches that before anything runs; this catches it after, which is where the port-in-use case
    lives. A dev server pointed at a dead API presents as a console bug and sends whoever debugs it
    to the wrong component — the failure this command exists to remove, surviving one layer below
    where it was being refused.
    """
    start_api = start_api or (
        lambda: subprocess.Popen(
            [sys.executable, "-m", "sync.api"], cwd=REPO_ROOT, env=_api_environment()
        )
    )
    start_console = start_console or (
        lambda: subprocess.run(
            [npm_executable(), "run", "dev", "--prefix", "web"], cwd=REPO_ROOT, check=False
        )
    )
    wait_ready = wait_ready or wait_for_api

    print("\nstarting the API")
    api = start_api()
    ready, detail = wait_ready(api)
    if not ready:
        api.terminate()
        print(f"the API {detail}, so the console was not started.")
        print("a console against a dead API looks like a console bug; this would not be one.")
        return 1

    print(f"API {detail}")
    print(f"console will serve on {CONSOLE_URL}")
    print("stop both with Ctrl-C")
    try:
        start_console()
    finally:
        api.terminate()
    return 0


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="report the preconditions and start nothing",
    )
    args = parser.parse_args(list(argv[1:]))

    checks = run_checks()
    print(render(checks))
    if any(check.status != OK for check in checks):
        return 1
    if args.check:
        return 0

    return start_loop()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
