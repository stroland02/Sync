import os
from pathlib import Path

import pytest

from sync.index import deps


def _record_with_kwargs(monkeypatch) -> tuple[list[list[str]], list[dict]]:
    calls: list[list[str]] = []
    kwargs_seen: list[dict] = []

    def fake_run(args, **kwargs):
        calls.append(args)
        kwargs_seen.append(kwargs)
        class Result:
            returncode = 0
            stdout = ""
            stderr = ""
        return Result()

    monkeypatch.setattr(deps.subprocess, "run", fake_run)
    monkeypatch.setattr(deps.shutil, "which", lambda name: f"/usr/bin/{name}")
    return calls, kwargs_seen


def _record(monkeypatch) -> list[list[str]]:
    calls, _ = _record_with_kwargs(monkeypatch)
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
    tree may execute on our machine.

    The loop includes `None` for "no lockfile at all" so the fallback branch
    is actually constructed here too -- a loop over only the three lockfiles
    never builds `_FALLBACK`, so dropping `--ignore-scripts` from it would
    pass this test.
    """
    for lockfile in ("yarn.lock", "package-lock.json", "pnpm-lock.yaml", None):
        label = lockfile or "no_lockfile"
        work = tmp_path / label.replace(".", "_")
        work.mkdir()
        (work / "package.json").write_text("{}", encoding="utf-8")
        if lockfile is not None:
            (work / lockfile).write_text("", encoding="utf-8")
        calls = _record(monkeypatch)
        deps.install_dependencies(work)
        assert "--ignore-scripts" in calls[0], label


def test_a_populated_node_modules_is_not_reinstalled(tmp_path, monkeypatch):
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "yarn.lock").write_text("", encoding="utf-8")
    (tmp_path / "node_modules" / "react").mkdir(parents=True)
    calls = _record(monkeypatch)
    deps.install_dependencies(tmp_path)
    assert calls == []


def test_a_node_modules_left_by_an_aborted_install_is_reinstalled(tmp_path, monkeypatch):
    """`npm ci` deletes `node_modules` and repopulates it; if it is killed by
    the timeout partway through, the directory is left holding only npm's
    hidden bookkeeping file and a fraction of the real packages.
    `Path.glob('*')` matches dotfiles, so a guard built on it would treat that
    wreckage as a complete install and never repair it."""
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "package-lock.json").write_text("", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / ".package-lock.json").write_text("{}", encoding="utf-8")
    calls = _record(monkeypatch)
    deps.install_dependencies(tmp_path)
    assert calls != []


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


def test_a_hung_install_is_reported_as_a_runtime_error(tmp_path, monkeypatch):
    """subprocess.TimeoutExpired is not a RuntimeError. A caller written
    against the one documented failure type (the test above) must not be
    surprised by a second, uncaught exception class when the install hangs
    instead of exiting nonzero."""
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "package-lock.json").write_text("", encoding="utf-8")

    def hanging_run(args, **kwargs):
        raise deps.subprocess.TimeoutExpired(cmd=args, timeout=kwargs.get("timeout"))

    monkeypatch.setattr(deps.subprocess, "run", hanging_run)
    monkeypatch.setattr(deps.shutil, "which", lambda name: f"/usr/bin/{name}")
    with pytest.raises(RuntimeError, match="timed out"):
        deps.install_dependencies(tmp_path, timeout=5)


def test_the_configured_timeout_reaches_the_subprocess_call(tmp_path, monkeypatch):
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "yarn.lock").write_text("", encoding="utf-8")
    calls, kwargs = _record_with_kwargs(monkeypatch)
    deps.install_dependencies(tmp_path, timeout=42)
    assert kwargs[0]["timeout"] == 42


def test_yarn_install_disables_the_vendored_yarn_path_override(tmp_path, monkeypatch):
    """A committed `.yarnrc`/`.yarnrc.yml` setting `yarn-path`/`yarnPath` makes
    the `yarn` binary re-exec a vendored file under `.yarn/releases` with node,
    before any flag we pass is even parsed -- a normal, documented layout, not
    an adversarial one. `--ignore-scripts` cannot stop that; only the
    environment variable can."""
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "yarn.lock").write_text("", encoding="utf-8")
    calls, kwargs = _record_with_kwargs(monkeypatch)
    deps.install_dependencies(tmp_path)
    assert kwargs[0]["env"]["YARN_IGNORE_PATH"] == "1"
    # Extended, not replaced. Handing the child a bare one-key environment
    # strips PATH, so npm's shim cannot resolve node and every install fails
    # with a message about the install rather than about the environment.
    assert kwargs[0]["env"]["PATH"] == os.environ["PATH"]


def test_a_missing_manager_raises_rather_than_silently_falling_back(tmp_path, monkeypatch):
    """The wrong refactor here is `if executable is None: manager, args =
    _FALLBACK` -- that would silently install a pnpm-lock.yaml project with
    plain npm, which can resolve a different tree than the lockfile pins."""
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "pnpm-lock.yaml").write_text("", encoding="utf-8")
    calls = _record(monkeypatch)
    monkeypatch.setattr(deps.shutil, "which", lambda name: None if name == "pnpm" else f"/usr/bin/{name}")
    with pytest.raises(FileNotFoundError, match="pnpm"):
        deps.install_dependencies(tmp_path)
    assert calls == []
