"""Materialise pinned corpus repositories as local rehearsal fixtures.

A rehearsal fixture is a real local git repository with exactly one commit and
zero remotes, ensuring no pipeline operation can ever push to a remote origin.
"""

import hashlib
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import yaml

from sync.core import RepoRef

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MANIFEST_PATH = _REPO_ROOT / "benchmark" / "corpus" / "repositories.yaml"
_CORPUS_ROOT = _REPO_ROOT / ".cache" / "corpus"


def _subprocess_env() -> dict[str, str]:
    return {**os.environ, "PYTHONIOENCODING": "utf-8"}


def _git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=_subprocess_env(),
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} in {cwd}: {result.stderr.strip()}")
    return result.stdout.strip()


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda p: p.relative_to(root).as_posix()):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(root).parts
        if any(part == ".git" for part in rel_parts):
            continue
        rel = path.relative_to(root).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _load_manifest_entry(name: str) -> dict[str, Any]:
    if not _MANIFEST_PATH.exists():
        raise RuntimeError(
            f"Corpus manifest missing at {_MANIFEST_PATH}. "
            "Run scripts/fetch_corpus_repositories.py first."
        )
    content = _MANIFEST_PATH.read_text(encoding="utf-8")
    entries: list[dict[str, Any]] = yaml.safe_load(content) or []
    for entry in entries:
        if entry.get("name") == name:
            return entry
    raise RuntimeError(
        f"Corpus repository '{name}' is missing from {_MANIFEST_PATH}. "
        "Run scripts/fetch_corpus_repositories.py first."
    )


def _remove_readonly(func: Any, path: str, excinfo: Any) -> None:
    import stat

    os.chmod(path, stat.S_IWRITE)
    func(path)


def _safe_rmtree(path: Path) -> None:
    if not path.exists():
        return
    shutil.rmtree(path, onexc=_remove_readonly)


def prepare_fixture(name: str = "furever", *, root: Path = Path(".cache/rehearse")) -> RepoRef:
    """Materialise a named corpus repository into a local zero-remote git repository.

    The fixture is initialized with exactly one commit containing the pinned tree
    and has no remotes configured. Subsequent calls on an untouched fixture
    converge idempotently without creating additional commits.
    """
    entry = _load_manifest_entry(name)
    repo_slug = entry["repo"]
    pinned_digest = entry.get("tree_digest")

    source_dir = _CORPUS_ROOT / name
    if not source_dir.exists():
        raise RuntimeError(
            f"Corpus repository '{name}' is missing at {source_dir}. "
            "Run scripts/fetch_corpus_repositories.py first."
        )

    dest = (root / name).resolve()

    if (dest / ".git").exists():
        current_digest = _tree_digest(dest)
        if pinned_digest and current_digest == pinned_digest:
            head = _git(["rev-parse", "HEAD"], dest)
            remotes = _git(["remote"], dest)
            if not remotes:
                repo_id = f"github.com/{repo_slug}"
                return RepoRef(
                    repo_id=repo_id,
                    url=f"https://github.com/{repo_slug}",
                    local_path=str(dest),
                    head_sha=head,
                )

    if dest.exists():
        _safe_rmtree(dest)

    shutil.copytree(source_dir, dest)

    if pinned_digest:
        actual_digest = _tree_digest(dest)
        if actual_digest != pinned_digest:
            raise RuntimeError(
                f"Tree digest mismatch for '{name}': expected {pinned_digest}, got {actual_digest}"
            )

    _git(["init", "-q", "."], dest)
    _git(
        ["-c", "user.name=Sync Rehearse", "-c", "user.email=sync@sync.invalid", "add", "-A"],
        dest,
    )
    _git(
        [
            "-c",
            "user.name=Sync Rehearse",
            "-c",
            "user.email=sync@sync.invalid",
            "commit",
            "-q",
            "-m",
            "Initial commit for rehearsal fixture",
        ],
        dest,
    )

    head_sha = _git(["rev-parse", "HEAD"], dest)
    repo_id = f"github.com/{repo_slug}"

    return RepoRef(
        repo_id=repo_id,
        url=f"https://github.com/{repo_slug}",
        local_path=str(dest),
        head_sha=head_sha,
    )
