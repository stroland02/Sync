from pathlib import Path

import pytest

from sync.index import shipped_tree as shipped_tree_module
from sync.index.shipped_tree import shipped_tree, unshipped_paths


@pytest.fixture()
def repo(tmp_path: Path, git) -> Path:
    """A clone holding one of everything `git status` can report."""
    repo = tmp_path / "clone"
    (repo / "src").mkdir(parents=True)
    (repo / ".gitignore").write_text("node_modules\nbuild\n*.log\n", encoding="utf-8")
    (repo / "src" / "tracked.ts").write_text("export const a = 1;\n", encoding="utf-8")

    git(["init", "-q", "-b", "main"], repo)
    git(["add", "."], repo)
    git(["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base"], repo)

    (repo / "src" / "tracked.ts").write_text("export const a = 2;\n", encoding="utf-8")
    (repo / "src" / "untracked.ts").write_text("export const b = 3;\n", encoding="utf-8")
    (repo / "agent.log").write_text("noise\n", encoding="utf-8")
    (repo / "build").mkdir()
    (repo / "build" / "out.js").write_text("1\n", encoding="utf-8")
    (repo / "node_modules" / "pkg").mkdir(parents=True)
    (repo / "node_modules" / "pkg" / "index.d.ts").write_text("export {};\n", encoding="utf-8")
    return repo


def test_unshipped_paths_names_untracked_and_ignored_content(repo: Path):
    assert set(unshipped_paths(repo)) == {"agent.log", "build/", "node_modules/", "src/untracked.ts"}


def test_kept_directories_are_not_reported(repo: Path):
    assert "node_modules/" not in unshipped_paths(repo, keep=frozenset({"node_modules"}))


def test_a_tracked_modification_is_shipped_and_so_is_never_reported(repo: Path):
    """`git add -u` stages it, so it is part of the artifact under test."""
    assert "src/tracked.ts" not in unshipped_paths(repo)


def test_a_new_file_the_agent_staged_itself_is_shipped(repo: Path, git):
    """The agent has `Bash`, so it can `git add` a file it created.

    `push_branch` commits the index it finds, so that file reaches the branch
    and has to be verified with it. Provenance is not the rule here -- what git
    would commit is.
    """
    git(["add", "src/untracked.ts"], repo)

    assert "src/untracked.ts" not in unshipped_paths(repo)


def test_unshipped_content_is_absent_inside_the_block_and_back_after(repo: Path):
    keep = frozenset({"node_modules"})

    with shipped_tree(repo, keep=keep):
        assert not (repo / "src" / "untracked.ts").exists()
        assert not (repo / "build").exists()
        assert not (repo / "agent.log").exists()
        assert (repo / "node_modules" / "pkg" / "index.d.ts").exists()
        assert (repo / "src" / "tracked.ts").read_text(encoding="utf-8") == "export const a = 2;\n"

    assert (repo / "src" / "untracked.ts").read_text(encoding="utf-8") == "export const b = 3;\n"
    assert (repo / "build" / "out.js").read_text(encoding="utf-8") == "1\n"
    assert (repo / "agent.log").exists()


def test_content_is_restored_when_the_block_raises(repo: Path):
    """A failed typecheck is the normal case; a crashed one must not cost the
    agent its working tree either."""
    with pytest.raises(ZeroDivisionError):
        with shipped_tree(repo, keep=frozenset({"node_modules"})):
            1 / 0

    assert (repo / "src" / "untracked.ts").exists()
    assert (repo / "build" / "out.js").exists()


def test_nothing_is_moved_when_the_tree_is_already_what_ships(repo: Path, git):
    """The holding directory is a sibling of the clone, so a run that creates
    one when it had nothing to move leaves litter next to a customer's checkout."""
    git(["clean", "-qfdx"], repo)

    before = set(repo.parent.iterdir())
    with shipped_tree(repo):
        pass

    assert set(repo.parent.iterdir()) == before


def test_an_artifact_the_block_regenerates_does_not_defeat_the_restore(repo: Path):
    """The collision that ended the M0 acceptance run.

    `tsc --noEmit` writes `tsconfig.tsbuildinfo` for an `incremental` project
    and `.gitignore` keeps it out of the repository, so the gate holds it aside
    and the compiler then writes a new one at the path it was held aside from.
    The run abandoned a finding on the `FileExistsError` that followed, for a
    reason unrelated to whether the patch was correct.

    Windows is where the rename refuses. POSIX overwrites silently and reaches
    the verdict this asserts by accident, so this is red on the platform the
    pipeline runs on and pins the chosen verdict on both.
    """
    with shipped_tree(repo, keep=frozenset({"node_modules"})):
        (repo / "agent.log").write_text("written while the gate measured\n", encoding="utf-8")

    assert (repo / "agent.log").read_text(encoding="utf-8") == "noise\n"


def test_a_directory_the_block_recreates_does_not_defeat_the_restore(repo: Path):
    """The same collision in the form that refuses on every platform.

    `os.rename` replaces a file and never a populated directory, so a compiler
    that writes its output directory again while the gate is measuring fails
    the restore on POSIX as well as on Windows.
    """
    with shipped_tree(repo, keep=frozenset({"node_modules"})):
        (repo / "build").mkdir()
        (repo / "build" / "fresh.js").write_text("2\n", encoding="utf-8")

    assert (repo / "build" / "out.js").read_text(encoding="utf-8") == "1\n"
    assert not (repo / "build" / "fresh.js").exists()


def test_every_other_path_is_restored_when_one_of_them_cannot_be(repo: Path, monkeypatch):
    """A half-restored clone poisons every later finding in the same run, which
    is a larger fault than the one path that could not be moved back.

    There is no portable way to hold a real lock on a file, so the refusal is
    injected at the seam that would meet one. The held copies stay where they
    are when this happens: after a failed restore they are the only copies left.
    """
    real_clear = shipped_tree_module._clear

    def refuse(path: Path) -> None:
        if path.name == "agent.log":
            raise OSError("locked by another process")
        real_clear(path)

    monkeypatch.setattr(shipped_tree_module, "_clear", refuse)

    with pytest.raises(RuntimeError, match="agent.log"):
        with shipped_tree(repo, keep=frozenset({"node_modules"})):
            (repo / "agent.log").write_text("written while the gate measured\n", encoding="utf-8")

    assert (repo / "src" / "untracked.ts").read_text(encoding="utf-8") == "export const b = 3;\n"
    assert (repo / "build" / "out.js").read_text(encoding="utf-8") == "1\n"

    held = list(repo.parent.glob(".sync-unshipped-*"))
    assert len(held) == 1
    assert (held[0] / "agent.log").read_text(encoding="utf-8") == "noise\n"
