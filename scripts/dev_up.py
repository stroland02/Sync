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

**It does not route around a broken entrypoint.** `python -m sync.api` currently raises
`NameError` and that is Lane E's to fix; a launcher that quietly used `uvicorn --factory` instead
would hide a defect on `main` behind a convenience, which is how a repository accumulates knowledge
that only lives in one person's head.
"""

from __future__ import annotations

import argparse
import inspect
import os
import re
import shutil
import subprocess
import sys
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

    print("\nstarting the API and the console dev server; stop them with Ctrl-C")
    api = subprocess.Popen([sys.executable, "-m", "sync.api"], cwd=REPO_ROOT)
    try:
        subprocess.run(
            [npm_executable(), "run", "dev", "--prefix", "web"], cwd=REPO_ROOT, check=False
        )
    finally:
        api.terminate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
