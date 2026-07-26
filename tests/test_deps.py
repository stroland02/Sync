from pathlib import Path

import pytest

from sync.index import deps


def _record(monkeypatch) -> list[list[str]]:
    calls: list[list[str]] = []

    def fake_run(args, **kwargs):
        calls.append(args)
        class Result:
            returncode = 0
            stdout = ""
            stderr = ""
        return Result()

    monkeypatch.setattr(deps.subprocess, "run", fake_run)
    monkeypatch.setattr(deps.shutil, "which", lambda name: f"/usr/bin/{name}")
    return calls


def test_a_yarn_lockfile_selects_yarn(tmp_path, monkeypatch):
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "yarn.lock").write_text("", encoding="utf-8")
    calls = _record(monkeypatch)
    deps.install_dependencies(tmp_path)
    assert calls[0][1:] == ["install", "--frozen-lockfile", "--ignore-scripts", "--ignore-engines"]


def test_an_npm_lockfile_selects_npm_ci(tmp_path, monkeypatch):
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "package-lock.json").write_text("", encoding="utf-8")
    calls = _record(monkeypatch)
    deps.install_dependencies(tmp_path)
    assert calls[0][1:] == ["ci", "--ignore-scripts"]


def test_a_pnpm_lockfile_selects_pnpm(tmp_path, monkeypatch):
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "pnpm-lock.yaml").write_text("", encoding="utf-8")
    calls = _record(monkeypatch)
    deps.install_dependencies(tmp_path)
    assert calls[0][1:] == ["install", "--frozen-lockfile", "--ignore-scripts"]


def test_no_lockfile_falls_back_to_a_plain_npm_install(tmp_path, monkeypatch):
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    calls = _record(monkeypatch)
    deps.install_dependencies(tmp_path)
    assert calls[0][1:] == ["install", "--ignore-scripts", "--no-audit", "--no-fund"]


def test_every_install_command_suppresses_lifecycle_scripts(tmp_path, monkeypatch):
    """The one property that must hold whichever manager is chosen: no
    postinstall, prepare, or prepublish script from the customer's dependency
    tree may execute on our machine."""
    for lockfile in ("yarn.lock", "package-lock.json", "pnpm-lock.yaml"):
        work = tmp_path / lockfile.replace(".", "_")
        work.mkdir()
        (work / "package.json").write_text("{}", encoding="utf-8")
        (work / lockfile).write_text("", encoding="utf-8")
        calls = _record(monkeypatch)
        deps.install_dependencies(work)
        assert "--ignore-scripts" in calls[0], lockfile


def test_a_populated_node_modules_is_not_reinstalled(tmp_path, monkeypatch):
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "yarn.lock").write_text("", encoding="utf-8")
    (tmp_path / "node_modules" / ".bin").mkdir(parents=True)
    calls = _record(monkeypatch)
    deps.install_dependencies(tmp_path)
    assert calls == []


def test_a_project_with_no_package_json_installs_nothing(tmp_path, monkeypatch):
    calls = _record(monkeypatch)
    deps.install_dependencies(tmp_path)
    assert calls == []


def test_a_failed_install_raises_rather_than_letting_tsc_report_nonsense(tmp_path, monkeypatch):
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "package-lock.json").write_text("", encoding="utf-8")

    def failing_run(args, **kwargs):
        class Result:
            returncode = 1
            stdout = ""
            stderr = "ENOENT: registry unreachable"
        return Result()

    monkeypatch.setattr(deps.subprocess, "run", failing_run)
    monkeypatch.setattr(deps.shutil, "which", lambda name: f"/usr/bin/{name}")
    with pytest.raises(RuntimeError, match="registry unreachable"):
        deps.install_dependencies(tmp_path)
