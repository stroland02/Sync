"""`docker/patch-sandbox/driver.py`, the in-container half of B97 Decision 1.

Loaded from its file path rather than imported as a package: it is not part of `sync` and never
will be, because it runs inside the sandbox with none of `sync`'s other modules available.
`tool_gate`/`tool_output`/`untrusted` are put on `sys.path` from their real location in
`src/sync/remediate/` rather than a duplicate copy under `docker/`, so this test exercises the
same files a real attempt copies into the container -- one source, never two that can disagree.

Mirrors `tests/test_agent_patch.py`'s own `ClaudeSdkRunner` tests as closely as the two runners'
shared logic allows, mocking `claude_agent_sdk.query` the same way and never touching a real
vendor or model API (`.claude/rules/test-discipline.md`).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from claude_agent_sdk import ResultMessage

_REPO_ROOT = Path(__file__).resolve().parents[1]
_REMEDIATE = _REPO_ROOT / "src" / "sync" / "remediate"
_DRIVER_PATH = _REPO_ROOT / "docker" / "patch-sandbox" / "driver.py"

if str(_REMEDIATE) not in sys.path:
    sys.path.insert(0, str(_REMEDIATE))


def _load_driver():
    spec = importlib.util.spec_from_file_location("docker_driver", _DRIVER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


driver = _load_driver()


def _ok_result(**overrides) -> ResultMessage:
    fields = dict(
        subtype="success", duration_ms=1, duration_api_ms=1, is_error=False, num_turns=1, session_id="s1"
    )
    fields.update(overrides)
    return ResultMessage(**fields)


def test_patch_hooks_matches_the_real_gate_and_output_fence():
    """The one-liner `agent_patch.patch_hooks` computes, reproduced rather than imported.

    Both sides call the same two functions (`tool_gate.hooks`, `tool_output.hooks`) on the same
    module objects -- `sys.path` above points both at the one real copy -- so this asserts the
    combination logic matches rather than re-testing the gate or the fence themselves.
    """
    from sync.remediate import agent_patch

    identity = "finding=f-1 repo=acme"
    host_refusals: list = []
    container_refusals: list = []

    host_hooks = agent_patch.patch_hooks(identity, host_refusals)
    container_hooks = driver.patch_hooks(identity, container_refusals)

    assert set(host_hooks.keys()) == set(container_hooks.keys())


def test_drive_configures_the_repo_cwd_and_the_pinned_model(monkeypatch, tmp_path):
    captured = {}

    async def fake_query(*, prompt, options):
        captured["prompt"] = prompt
        captured["options"] = options
        yield _ok_result()

    monkeypatch.setattr(driver, "query", fake_query)

    import asyncio
    asyncio.run(driver.drive("do the patch", tmp_path, "finding=f-42 repo=acme-billing"))

    options = captured["options"]
    assert captured["prompt"] == "do the patch"
    assert options.cwd == tmp_path
    assert options.model == driver.MODEL
    assert options.allowed_tools == driver.ALLOWED_TOOLS
    assert options.disallowed_tools == driver.DISALLOWED_TOOLS
    assert options.setting_sources == []


def test_drive_raises_when_the_sdk_reports_a_failed_run(monkeypatch, tmp_path):
    async def fake_query(*, prompt, options):
        yield _ok_result(is_error=True, subtype="error_max_turns")

    monkeypatch.setattr(driver, "query", fake_query)

    import asyncio
    with pytest.raises(RuntimeError, match="failed"):
        asyncio.run(driver.drive("do the patch", tmp_path, "finding=f-42 repo=acme-billing"))


def test_drive_raises_when_no_result_message_arrives(monkeypatch, tmp_path):
    async def fake_query(*, prompt, options):
        return
        yield  # pragma: no cover -- makes this an async generator with an empty stream

    monkeypatch.setattr(driver, "query", fake_query)

    import asyncio
    with pytest.raises(RuntimeError, match="no result message"):
        asyncio.run(driver.drive("do the patch", tmp_path, "finding=f-42 repo=acme-billing"))


def test_main_writes_a_result_file_the_host_can_read_back(monkeypatch, tmp_path):
    """The job/result protocol this driver's own docstring describes, proven end to end against
    `main()` rather than only against `drive()` -- the file I/O is real code with a real path to
    get wrong.
    """
    job_dir = tmp_path / ".sync-job"
    job_dir.mkdir()
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (job_dir / "job.json").write_text(
        json.dumps({"prompt": "do the patch", "identity": "finding=f-1 repo=acme", "repo_path": str(repo_path)}),
        encoding="utf-8",
    )
    monkeypatch.setattr(driver, "JOB_DIR", job_dir)
    monkeypatch.setattr(driver, "JOB_PATH", job_dir / "job.json")
    monkeypatch.setattr(driver, "RESULT_PATH", job_dir / "result.json")

    async def fake_query(*, prompt, options):
        yield _ok_result()

    monkeypatch.setattr(driver, "query", fake_query)

    exit_code = driver.main()

    assert exit_code == 0
    result = json.loads((job_dir / "result.json").read_text(encoding="utf-8"))
    assert result == {"ok": True, "error": None}


def test_main_reports_failure_in_the_result_file_rather_than_only_the_exit_code(monkeypatch, tmp_path):
    job_dir = tmp_path / ".sync-job"
    job_dir.mkdir()
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (job_dir / "job.json").write_text(
        json.dumps({"prompt": "do the patch", "identity": "finding=f-1 repo=acme", "repo_path": str(repo_path)}),
        encoding="utf-8",
    )
    monkeypatch.setattr(driver, "JOB_DIR", job_dir)
    monkeypatch.setattr(driver, "JOB_PATH", job_dir / "job.json")
    monkeypatch.setattr(driver, "RESULT_PATH", job_dir / "result.json")

    async def fake_query(*, prompt, options):
        yield _ok_result(is_error=True, subtype="error_max_turns")

    monkeypatch.setattr(driver, "query", fake_query)

    exit_code = driver.main()

    assert exit_code == 1
    result = json.loads((job_dir / "result.json").read_text(encoding="utf-8"))
    assert result["ok"] is False
    assert "failed" in result["error"]
