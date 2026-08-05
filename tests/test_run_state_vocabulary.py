"""Every word written into an outcome key is a member of the type that key declares.

`Outcome` and `PreviewOutcome` are `Literal`s and nothing in this repository typechecks:
`pyproject.toml` configures no mypy and no pyright, and CI runs `lint_encoding.py`,
`lint-imports`, `lint_dead_links.py` and pytest. A `Literal` is therefore a claim no tool
checks, which is how `RunState["outcome"]` came to be declared as four words while
`sync.mcp.propose` wrote five different ones into it.

Shaped after `tests/test_corpus_writer.py`'s terminal-status scan, which holds the corpus
vocabulary the same way and for the same reason. Maintained the same way too: a failure here
is a vocabulary that grew, so add the word to the `Literal` and this follows. Widening an
assertion instead retires the check.

The members are read with `typing.get_args` rather than copied, so a word added to one
`Literal` cannot leave this asserting the old set.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import get_args

from sync.mcp.propose import PreviewOutcome
from sync.remediate.state import Outcome

SRC = Path(__file__).resolve().parents[1] / "src" / "sync"
REMEDIATE = SRC / "remediate"
MCP = SRC / "mcp"


def _parse(package: Path) -> dict[Path, ast.Module]:
    return {path: ast.parse(path.read_text(encoding="utf-8")) for path in sorted(package.rglob("*.py"))}


def _subscript_key(node: ast.AST) -> str | None:
    if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
        return node.slice.value
    return None


def _constants(trees: dict[Path, ast.Module]) -> dict[str, str]:
    """Module-level `NAME = "literal"` across the package, under `NAME` and `module.NAME`.

    Both spellings, because a word is defined in one module and used from another:
    `tools.py` writes `propose.UNAVAILABLE` into the response, and a scan resolving bare
    names alone would report that word as never written.
    """
    found: dict[str, str] = {}
    for path, tree in trees.items():
        for node in tree.body:
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Constant):
                continue
            if not isinstance(node.value.value, str):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    found[target.id] = node.value.value
                    found[f"{path.stem}.{target.id}"] = node.value.value
    return found


def _resolve(node: ast.AST, constants: dict[str, str]) -> set[str]:
    """The words an expression can evaluate to, or nothing where the source cannot say.

    Unresolvable is empty rather than guessed. `state["preview_outcome"]` copied into a
    response dict names no word, and inventing one there would put a value in the vocabulary
    that no line of source chose.
    """
    if isinstance(node, ast.Constant):
        return {node.value} if isinstance(node.value, str) else set()
    if isinstance(node, ast.Name):
        value = constants.get(node.id)
        return {value} if value is not None else set()
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        value = constants.get(f"{node.value.id}.{node.attr}")
        return {value} if value is not None else set()
    if isinstance(node, ast.IfExp):
        return _resolve(node.body, constants) | _resolve(node.orelse, constants)
    return set()


def _writers(trees: dict[Path, ast.Module], keys: set[str]) -> dict[str, int]:
    """Functions that assign one of their own parameters to one of `keys`, by position.

    Without this hop the scan sees `_finish(state, PROPOSED)` and one assignment of an
    unresolvable name, and reports an empty vocabulary for a module that writes five words.
    """
    found: dict[str, int] = {}
    for tree in trees.values():
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            params = [arg.arg for arg in node.args.args]
            for sub in ast.walk(node):
                if not isinstance(sub, ast.Assign) or not isinstance(sub.value, ast.Name):
                    continue
                if sub.value.id not in params:
                    continue
                if any(_subscript_key(target) in keys for target in sub.targets):
                    found[node.name] = params.index(sub.value.id)
    return found


def _words_written_to(package: Path, keys: set[str]) -> set[str]:
    """Every word this package writes into one of `keys`.

    Three forms, which is all the source uses: a subscript assignment, a key in a dict
    literal a node returns, and an argument to a helper that performs the subscript itself.
    """
    trees = _parse(package)
    constants = _constants(trees)
    writers = _writers(trees, keys)

    found: set[str] = set()
    for tree in trees.values():
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                if any(_subscript_key(target) in keys for target in node.targets):
                    found |= _resolve(node.value, constants)
            elif isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if isinstance(key, ast.Constant) and key.value in keys:
                        found |= _resolve(value, constants)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                index = writers.get(node.func.id)
                if index is not None and index < len(node.args):
                    found |= _resolve(node.args[index], constants)
    return found


def _subscript_writes(package: Path, key: str) -> list[str]:
    """`file:line` for every `something[key] = ...` in the package.

    Kept apart from a dict literal deliberately. Inside `sync.mcp` a `{"outcome": ...}` is
    the published MCP response, whose vocabulary is the preview's; a `state["outcome"] = ...`
    is a write into `RunState`, whose declared type holds none of those words.
    """
    return [
        f"{path.name}:{node.lineno}"
        for path, tree in _parse(package).items()
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(_subscript_key(target) == key for target in node.targets)
    ]


def test_the_pipeline_writes_only_the_outcomes_it_declares():
    """`RunState["outcome"]: Outcome` is the single document saying what a run carries, and
    the operator console and the migration corpus are both keyed against it."""
    assert _words_written_to(REMEDIATE, {"outcome"}) == set(get_args(Outcome))


def test_the_preview_writes_only_the_outcomes_it_declares():
    """Both names carry the preview vocabulary inside `sync.mcp`: `preview_outcome` on the
    state the driver returns, and `outcome` on the published MCP response."""
    assert _words_written_to(MCP, {"outcome", "preview_outcome"}) == set(get_args(PreviewOutcome))


def test_the_preview_never_writes_the_pipeline_s_outcome_key():
    """A preview that stops before pushing has neither opened nor abandoned anything, so its
    words are its own. Writing them into `RunState["outcome"]` makes the declaration there
    false, and `sync.dashboard.queries` reads that key against a three-word finished set --
    any other word renders as a run still in flight."""
    assert _subscript_writes(MCP, "outcome") == []


def test_the_scan_would_notice_a_word_outside_the_vocabulary(tmp_path):
    """The three assertions above are worth having only if the scan can fail. Proven against
    a synthetic module rather than by editing `src/`, since the property under test belongs
    to the scan either way -- and each of the three forms appears once here, so a form the
    scan stopped resolving would show up as a missing word rather than as nothing at all.
    """
    module = tmp_path / "drifted.py"
    module.write_text(
        'TIMED_OUT = "timed_out"\n'
        "def _finish(state, outcome):\n"
        '    state["preview_outcome"] = outcome\n'
        "    return state\n"
        "def run(state):\n"
        "    return _finish(state, TIMED_OUT)\n"
        "def unavailable():\n"
        '    return {"outcome": "unavailable"}\n'
        "def blocked(state):\n"
        '    state["preview_outcome"] = "blocked"\n',
        encoding="utf-8",
    )

    assert _words_written_to(tmp_path, {"outcome", "preview_outcome"}) == {
        "timed_out", "unavailable", "blocked",
    }
