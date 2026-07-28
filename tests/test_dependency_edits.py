"""The path arithmetic under the dependency guard, without a compiler.

`test_tsc_verify.py` proves the gate rejects a patched declaration. These pin
what counts as one, which is where a guard of this shape fails quietly: too
narrow and it never fires, too wide and it fires on every run.
"""

import os
from pathlib import Path

from sync.index.dependency_edits import describe, mark_installed, unshippable_dependency_edits

DIRS = frozenset({"node_modules"})


def _tree(root: Path) -> None:
    (root / "src").mkdir(parents=True)
    (root / "node_modules" / "vendorsdk").mkdir(parents=True)
    (root / "packages" / "billing" / "node_modules" / "vendorsdk").mkdir(parents=True)
    (root / "src" / "a.ts").write_text("export const n = 1;\n", encoding="utf-8")
    (root / "node_modules" / "vendorsdk" / "index.d.ts").write_text("export type C = {};\n", encoding="utf-8")
    (root / "packages" / "billing" / "node_modules" / "vendorsdk" / "index.d.ts").write_text(
        "export type C = {};\n", encoding="utf-8"
    )


def _mark(root: Path) -> int:
    """A mark every file in the tree predates and the next write does not.

    The production primitive, deliberately: taking the tree's newest mtime is not
    enough on its own, because the write a test makes immediately afterwards can land
    on the same filesystem tick and compare equal rather than greater. That is a real
    1-in-12 flake, not a theoretical one.
    """
    return mark_installed(root)


def test_nothing_written_since_the_install_is_reported(tmp_path: Path, git):
    _tree(tmp_path)
    git(["init", "-q"], tmp_path)

    assert unshippable_dependency_edits(tmp_path, DIRS, _mark(tmp_path)) == []


def test_an_edit_inside_a_workspaces_own_dependencies_is_found(tmp_path: Path, git):
    """A monorepo installs per package as well as at the root, and pnpm does it
    even for a single one. A guard that only looked at the root `node_modules`
    would pass every patch in a repository shaped like that."""
    _tree(tmp_path)
    git(["init", "-q"], tmp_path)
    mark = _mark(tmp_path)

    edited = tmp_path / "packages" / "billing" / "node_modules" / "vendorsdk" / "index.d.ts"
    edited.write_text("export type C = { receipt_email: string };\n", encoding="utf-8")

    assert unshippable_dependency_edits(tmp_path, DIRS, mark) == [
        "packages/billing/node_modules/vendorsdk/index.d.ts"
    ]


def test_editing_the_source_is_not_a_dependency_edit(tmp_path: Path, git):
    """The whole point of the patch. Everything outside a dependency directory
    is tracked, staged by `git add -u`, and reviewed on the pull request."""
    _tree(tmp_path)
    git(["init", "-q"], tmp_path)
    mark = _mark(tmp_path)

    (tmp_path / "src" / "a.ts").write_text("export const n = 2;\n", encoding="utf-8")

    assert unshippable_dependency_edits(tmp_path, DIRS, mark) == []


def test_a_repository_that_commits_its_dependencies_ships_the_edit(tmp_path: Path, git):
    """`git add -u` stages a tracked modification wherever it lives.

    A repository that vendors `node_modules` commits an edit inside one like any
    other, so the branch carries it and the customer's CI sees what we
    typechecked. Failing that patch would abandon every finding on the
    repository for doing nothing wrong.
    """
    _tree(tmp_path)
    git(["init", "-q"], tmp_path)
    git(["add", "-A"], tmp_path)
    git(["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "vendored"], tmp_path)
    mark = _mark(tmp_path)

    edited = tmp_path / "node_modules" / "vendorsdk" / "index.d.ts"
    edited.write_text("export type C = { receipt_email: string };\n", encoding="utf-8")

    assert unshippable_dependency_edits(tmp_path, DIRS, mark) == []


def test_a_file_the_agent_added_to_a_vendored_dependency_still_does_not_ship(tmp_path: Path, git):
    """Tracked is the property that matters, not the directory it sits in:
    `git add -u` never stages a path git does not already know."""
    _tree(tmp_path)
    git(["init", "-q"], tmp_path)
    git(["add", "-A"], tmp_path)
    git(["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "vendored"], tmp_path)
    mark = _mark(tmp_path)

    (tmp_path / "node_modules" / "vendorsdk" / "extra.d.ts").write_text(
        "export type Extra = {};\n", encoding="utf-8"
    )

    assert unshippable_dependency_edits(tmp_path, DIRS, mark) == [
        "node_modules/vendorsdk/extra.d.ts"
    ]


def _extended(path: Path) -> str:
    """A path spelled so Windows will create it past 260 characters.

    The fixture has to reach further than the code under test, or the test would
    be asserting against a tree it could not build either.
    """
    absolute = os.path.abspath(path)
    return "\\\\?\\" + absolute if os.name == "nt" else absolute


def test_a_dependency_nested_past_the_windows_path_limit_is_still_walked(tmp_path: Path, git):
    """Reproduced from a real install: `@babel/.../resolve` commits test
    fixtures deep enough that `os.scandir` raises `FileNotFoundError` on a
    directory that is plainly there, and a dependency's own dependencies nest
    without bound. Crashing here abandons every finding on the repository
    rather than verifying one.
    """
    _tree(tmp_path)
    git(["init", "-q"], tmp_path)
    mark = _mark(tmp_path)

    deep = tmp_path / "node_modules" / "vendorsdk"
    while len(str(deep)) < 300:
        deep = deep / "nested"
    os.makedirs(_extended(deep), exist_ok=True)
    with open(_extended(deep / "index.d.ts"), "w", encoding="utf-8") as handle:
        handle.write("export type C = {};\n")

    assert unshippable_dependency_edits(tmp_path, DIRS, mark) == [
        (deep / "index.d.ts").relative_to(tmp_path).as_posix()
    ]


def test_the_diagnostic_names_a_path_and_stays_readable_when_there_are_many():
    """An agent that reinstalled rather than edited changes every file in the
    tree. The operator reading `abandon_reason` gets this text and nothing else,
    so it has to name paths without becoming a listing of them."""
    one = describe(["node_modules/vendorsdk/index.d.ts"])
    assert "node_modules/vendorsdk/index.d.ts" in one
    assert "will not be" in one

    many = describe([f"node_modules/p{index}/index.d.ts" for index in range(40)])
    assert "node_modules/p0/index.d.ts" in many
    assert "35 other paths" in many


def test_the_mark_is_late_enough_that_the_very_next_write_is_visible(tmp_path: Path) -> None:
    """The guard compares mtimes against a mark, and a filesystem's mtime resolution is
    coarser than the clock's: measured here at about 0.56ms, so a write within roughly
    1.5ms of `time.time_ns()` records an mtime that is not strictly greater than it.

    In a real run the agent works for minutes between the install and the check, so the
    gap is never that small. The mark must not depend on that being true — a guard that
    holds only because the thing it watches happens to be slow is a guard that stops
    holding the day something gets faster, silently, in the direction of missing edits.
    """
    installed_at = mark_installed(tmp_path)

    offender = tmp_path / "node_modules" / "pkg" / "index.d.ts"
    offender.parent.mkdir(parents=True)
    offender.write_text("export {};\n", encoding="utf-8")

    assert offender.stat().st_mtime_ns > installed_at, (
        "a write immediately after the mark was not distinguishable from it"
    )
