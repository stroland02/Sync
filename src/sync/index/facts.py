"""Technical facts about a codebase, computed from what the index already reads.

The build-versus-buy verdict, recorded in `references/notes/codebase-facts-tooling.md`: the
open-source tools that answer these questions (linguist for languages, tokei/scc/pygount for
line counts, onefetch for the summary-card composition) are all a dependency or a binary for
work this repository already does -- the indexer walks the tree, the intake parses manifests,
and git answers its own history. What is taken from them is shape, not code: linguist's
extension-to-language mapping idea, and onefetch's composition of a repository card.

Everything here is a measurement with a stated method:

- **Files come from `git ls-files`** when the checkout has git -- the repository's own answer
  to "what is tracked", which excludes `node_modules` and build output exactly as the
  repository's `.gitignore` says to, rather than by a guess this module maintains. A checkout
  without git falls back to a walk that skips the conventional dirt, and the payload says
  which census ran.
- **Lines are newline counts over bytes**, never decoded -- an encoding can corrupt a count on
  exactly one platform, and `CLAUDE.md` carries the measurement. A file whose first 8KB holds
  a NUL byte is counted as binary and contributes files, not lines.
- **Git facts are git's own**: commit count, first and last commit instants, contributor
  count. A checkout without git reports them absent rather than zero.
- **The stack is the manifests' own declaration**, through `read_declared_dependencies` --
  the same parse the intake command uses, so the Overview and `sync intake` cannot disagree
  about what a repository declares.
"""

from __future__ import annotations

import os
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from sync.signals.intake import read_declared_dependencies

# Extension to language name, linguist's idea at the size this console needs: the common
# languages a watched codebase is made of, not a registry of every language on earth. An
# extension absent here lands in "other", counted rather than dropped.
_LANGUAGES: dict[str, str] = {
    ".py": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".mts": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".java": "Java",
    ".kt": "Kotlin",
    ".cs": "C#",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".hpp": "C++",
    ".php": "PHP",
    ".swift": "Swift",
    ".scala": "Scala",
    ".sql": "SQL",
    ".sh": "Shell",
    ".ps1": "PowerShell",
    ".css": "CSS",
    ".scss": "CSS",
    ".html": "HTML",
    ".md": "Markdown",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".json": "JSON",
    ".toml": "TOML",
}

# What a walk without git skips. `git ls-files` needs no such list -- the repository's own
# ignore rules are the authority -- so this exists only for the checkout that has no git.
_WALK_SKIPS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".cache"}

_TOOLCHAIN_MARKERS: tuple[tuple[str, str], ...] = (
    ("package-lock.json", "npm"),
    ("pnpm-lock.yaml", "pnpm"),
    ("yarn.lock", "yarn"),
    ("uv.lock", "uv"),
    ("poetry.lock", "poetry"),
    ("requirements.txt", "pip requirements"),
    ("Cargo.lock", "cargo"),
    ("go.sum", "go modules"),
    ("Dockerfile", "docker"),
    ("docker-compose.yml", "docker compose"),
    (".github/workflows", "GitHub Actions"),
    ("tsconfig.json", "TypeScript config"),
)


def _git(repo_path: Path, args: list[str]) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _tracked_files(repo_path: Path) -> tuple[list[Path], str]:
    listing = _git(repo_path, ["ls-files", "-z"]) if (repo_path / ".git").exists() else None
    if listing is not None:
        files = [repo_path / name for name in listing.split("\0") if name]
        return files, "git ls-files"

    found: list[Path] = []
    for root, dirs, names in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in _WALK_SKIPS]
        for name in names:
            found.append(Path(root) / name)
    return found, "filesystem walk"


def _count_lines(path: Path) -> int | None:
    """Newlines in the file's bytes, or None for a binary. Bytes, never decoded."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\0" in data[:8192]:
        return None
    return data.count(b"\n")


def compute_facts(repo_path: Path) -> dict[str, Any]:
    """Every technical fact this module can measure about one checkout, with its method named."""
    repo_path = Path(repo_path)
    files, census = _tracked_files(repo_path)

    file_counts: Counter[str] = Counter()
    line_counts: Counter[str] = Counter()
    binary_files = 0
    for path in files:
        language = _LANGUAGES.get(path.suffix.lower(), "other")
        file_counts[language] += 1
        lines = _count_lines(path)
        if lines is None:
            binary_files += 1
        else:
            line_counts[language] += lines

    languages = [
        {"name": name, "files": file_counts[name], "lines": line_counts.get(name, 0)}
        for name, _ in file_counts.most_common()
    ]

    commit_count_raw = _git(repo_path, ["rev-list", "--count", "HEAD"])
    first_commit = _git(repo_path, ["log", "--reverse", "--format=%cI", "--max-parents=0", "-1"])
    last_commit = _git(repo_path, ["log", "-1", "--format=%cI"])
    contributors_raw = _git(repo_path, ["shortlog", "-s", "HEAD"])

    dependencies, unreadable = read_declared_dependencies(repo_path)
    by_ecosystem: dict[str, list[str]] = {}
    for dependency in dependencies:
        by_ecosystem.setdefault(dependency.ecosystem, []).append(dependency.name)

    toolchain = [
        label for marker, label in _TOOLCHAIN_MARKERS if (repo_path / marker).exists()
    ]

    return {
        "census": census,
        "total_files": len(files),
        "binary_files": binary_files,
        "languages": languages,
        "git": {
            "commit_count": int(commit_count_raw.strip()) if commit_count_raw else None,
            "first_commit_at": (first_commit or "").strip() or None,
            "last_commit_at": (last_commit or "").strip() or None,
            "contributor_count": (
                len(contributors_raw.strip().splitlines()) if contributors_raw else None
            ),
        },
        "dependencies": {
            "by_ecosystem": {
                ecosystem: sorted(names) for ecosystem, names in sorted(by_ecosystem.items())
            },
            "unreadable_manifests": list(unreadable),
        },
        "toolchain": toolchain,
    }
