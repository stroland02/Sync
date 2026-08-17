"""The one command that brings the console up, executed rather than described.

`CI-W297` established the discipline this file follows: an assertion about instructions is not an
assertion about the thing the instructions describe. Twelve tests said the day-one path was
documented correctly while a fresh checkout failed fifty tests, because every one of them read the
prose. So this executes `scripts/dev_up.py` and asserts on what it does.

The behaviour worth pinning is not that it starts things. It is that it **refuses to start
anything when a precondition is missing**. Half a stack is worse than no stack: a dev server
pointed at an API that never came up presents as a console bug, and the person debugging it is
debugging the wrong component — which is the shape of every expensive failure this repository found
today.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.dev_up import (
    MISSING,
    OK,
    Check,
    check_api_entrypoint,
    check_npm,
    npm_executable,
    render,
    undefined_names_in,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "dev_up.py"), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**dict(__import__("os").environ), "PYTHONIOENCODING": "utf-8"},
        timeout=180,
    )


# --- executed, not described ---------------------------------------------------------


def test_check_runs_and_reports_every_precondition() -> None:
    """The command exists, runs, and answers. Executed rather than asserted about."""
    result = _run("--check")

    for precondition in ("postgres", "schema", "seeded", "api entrypoint", "console dependencies"):
        assert precondition in result.stdout, f"{precondition} is not reported at all"


def test_a_missing_precondition_is_named_with_the_command_that_fixes_it() -> None:
    """Executed against a database that is genuinely not there.

    A check that says a thing is missing without saying how to get it has moved the search rather
    than ended it.
    """
    import os

    env = {**os.environ, "SYNC_GRAPH_DSN": "postgresql://nobody:nobody@127.0.0.1:59998/nothing"}
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "dev_up.py"), "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=180,
    )

    assert result.returncode != 0, "a missing precondition reported success"
    assert "MISSING" in result.stdout
    assert "docker compose up -d" in result.stdout, "the fix is not named"


def test_nothing_is_started_when_a_precondition_is_missing() -> None:
    """The rule the command exists for.

    `--check` starts nothing by construction, so this pins the other half: the default path refuses
    before it reaches the point of spawning anything, and says so in words rather than exiting
    silently.
    """
    import os

    env = {**os.environ, "SYNC_GRAPH_DSN": "postgresql://nobody:nobody@127.0.0.1:59998/nothing"}
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "dev_up.py")],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=180,
    )

    assert result.returncode != 0
    assert "nothing was started" in result.stdout
    assert "starting the API" not in result.stdout


# --- the entrypoint check, which must survive the defect being fixed -----------------


def _module_with(source: str, tmp_path: Path):
    """Written to a real file, because `inspect.getsource` cannot read an `exec`-ed module.

    The checker reads source, so a synthetic module has to have some.
    """
    import importlib.util

    path = tmp_path / "synthetic_entrypoint.py"
    path.write_text(source, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("synthetic_entrypoint", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["synthetic_entrypoint"] = module
    spec.loader.exec_module(module)
    return module


def test_undefined_names_finds_a_name_the_module_does_not_define(tmp_path) -> None:
    """Tested against a synthetic module rather than against the real defect.

    Asserting that `sync.api.__main__` is currently broken would be a test that Lane E's fix makes
    fail, which is a test that punishes the repair. What is pinned is that the checker works.
    """
    module = _module_with("def main():\n    return configured_api_password()\n", tmp_path)

    assert undefined_names_in(module.main) == ["configured_api_password"]


def test_undefined_names_is_silent_when_every_name_resolves(tmp_path) -> None:
    module = _module_with(
        "def helper():\n    return 1\n\ndef main():\n    return helper()\n", tmp_path
    )

    assert undefined_names_in(module.main) == []


def test_the_entrypoint_check_reports_lane_e_rather_than_working_around_it() -> None:
    """Whichever way it currently reads, it must never propose a workaround.

    `uvicorn --factory` starts the app despite the broken `main()`, and a launcher that quietly
    used it would hide a defect on `main` behind a convenience. If the entrypoint is broken this
    says so and names the owning lane; if it is fixed this passes unchanged.
    """
    check = check_api_entrypoint()

    assert check.status in (OK, MISSING)
    if check.status is MISSING or check.status == MISSING:
        assert "Lane E" in check.detail
        assert check.fix is None, "a workaround was offered for another lane's defect"
        assert "uvicorn" not in check.detail.lower()


# --- rendering -----------------------------------------------------------------------


def test_render_says_nothing_was_started_when_something_is_missing() -> None:
    text = render([Check("postgres", MISSING, "unreachable", "docker compose up -d")])

    assert "nothing was started" in text
    assert "docker compose up -d" in text


def test_render_is_quiet_when_everything_holds() -> None:
    text = render([Check("postgres", OK, "reachable")])

    assert "every precondition holds" in text
    assert "MISSING" not in text


# --- the start path, which --check never exercised -----------------------------------


def test_no_subprocess_call_spawns_a_bare_executable_name() -> None:
    """Found by running the command rather than by checking it, which is the point.

    `--check` was tested and passed; the start path was not, and it could not work at all here. On
    Windows npm is `npm.CMD`, and spawning it by bare name without a shell raises
    `FileNotFoundError: [WinError 2]` -- a traceback out of a launcher whose entire purpose is to
    turn a missing precondition into a sentence. `CLAUDE.md` already records this for the corepack
    shims: `shutil.which` resolves the form Windows can execute.

    Read from the syntax tree rather than the source text. The first version of this test searched
    for the literal `["npm"` and was tripped by the docstring above describing the defect -- a
    check fooled by prose about the thing it checks, which is a small instance of the same error
    this file exists to avoid.
    """
    import ast

    tree = ast.parse((REPO_ROOT / "scripts" / "dev_up.py").read_text(encoding="utf-8"))
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        target = node.args[0]
        if not isinstance(target, ast.List) or not target.elts:
            continue
        first = target.elts[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            if "/" not in first.value and "\\" not in first.value:
                offenders.append(first.value)

    assert not offenders, (
        f"spawned by bare name and unresolvable on Windows: {offenders}. "
        "Resolve through shutil.which so the .CMD form is used"
    )


def test_npm_missing_is_a_precondition_rather_than_a_crash(monkeypatch) -> None:
    """The launcher must report it, not die on it."""
    import scripts.dev_up as dev_up

    monkeypatch.setattr(dev_up.shutil, "which", lambda _name: None)
    check = dev_up.check_npm()

    assert check.status == MISSING
    assert check.fix, "a missing precondition with no fix has moved the search rather than ended it"


def test_npm_resolves_on_this_machine() -> None:
    """Executed against the real PATH: whatever it returns must be runnable."""
    resolved = npm_executable()

    assert resolved is not None
    assert Path(resolved).exists(), f"{resolved} was resolved and does not exist"
    assert check_npm().status == OK
