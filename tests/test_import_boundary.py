"""`sync.core` must import nothing from any sibling package.

This is not a style rule. A third party writing a Twilio adapter depends on
`sync.core` alone; if core reaches into `sync.graph`, that adapter drags in
Postgres.
"""

import os
import shutil
import subprocess
from pathlib import Path

# `python -m importlinter.cli lint` does not work: importlinter/cli.py defines
# its click commands but has no `if __name__ == "__main__":` guard, so running
# the module does nothing and exits 0 whether or not a contract is violated.
# The documented entry point is the `lint-imports` console script instead.
REPO_ROOT = Path(__file__).resolve().parent.parent


def test_core_imports_no_sibling_package():
    lint_imports = shutil.which("lint-imports")
    assert lint_imports is not None, "lint-imports console script not found on PATH"

    # PYTHONIOENCODING is not optional here. import-linter renders through rich, whose
    # Windows console path encodes with the locale codepage -- cp1252 on this machine -- and
    # the spinner it prints is an emoji. Without this the child dies with a UnicodeEncodeError
    # before it evaluates a single contract, and a dead child looks exactly like a broken one.
    result = subprocess.run(
        [lint_imports],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
    )
    output = result.stdout + result.stderr

    # Checked before the exit code, so the two failure modes report differently. A crashed
    # linter and a violated contract both exit non-zero, and a test that cannot tell them
    # apart would let a real breach hide behind an environment fault.
    assert "Contracts:" in output, (
        "lint-imports produced no contract report, so the boundary was never checked:\n" + output
    )
    assert result.returncode == 0, output


# --- the consequence the rule exists for, which the rule alone does not keep --------------


STDLIB_AND_SELF = {
    "__future__", "abc", "ast", "collections", "contextlib", "dataclasses", "datetime",
    "enum", "functools", "hashlib", "importlib", "inspect", "itertools", "json", "os",
    "pathlib", "re", "sys", "tempfile", "textwrap", "types", "typing", "urllib", "uuid",
    "sync",
}


def _third_party_imports_of(package: Path) -> set[str]:
    """Every distribution `package` imports, by top-level name."""
    import ast as ast_module

    found: set[str] = set()
    for source in package.rglob("*.py"):
        tree = ast_module.parse(source.read_text(encoding="utf-8"))
        for node in ast_module.walk(tree):
            if isinstance(node, ast_module.Import):
                found.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast_module.ImportFrom) and node.module and node.level == 0:
                found.add(node.module.split(".")[0])
    return found - STDLIB_AND_SELF


def test_core_needs_one_third_party_package():
    """The dependency claim CONTRIBUTING.md makes to adapter authors, pinned.

    `test_core_imports_no_sibling_package` above keeps core from reaching into a sibling. That
    is necessary and it is not the promise: the promise is that an adapter "does not inherit
    Postgres, LangGraph, or anything else in this repository's dependency tree", and a direct
    `import psycopg` in core would satisfy the sibling rule while breaking it completely.

    Pinned at one rather than counted loosely because the number is the whole argument. `sync`
    declares twelve runtime dependencies; core needs one. That gap is what makes packaging core
    separately worth doing, and it closes silently -- one convenient import at a time, each
    individually defensible -- unless something fails when it moves.

    Widen this deliberately or not at all. A second entry here is a decision about what a third
    party must install to write an adapter, and it should be argued in a commit message rather
    than discovered later by someone wondering why the split got harder.
    """
    core = REPO_ROOT / "src" / "sync" / "core"

    assert _third_party_imports_of(core) == {"pydantic"}
