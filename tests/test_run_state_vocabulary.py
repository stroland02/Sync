"""Every write into an outcome key resolves to a word that key's type declares, or fails.

`Outcome` and `PreviewOutcome` are `Literal`s and nothing in this repository typechecks:
`pyproject.toml` configures no mypy and no pyright, and CI runs `lint_encoding.py`,
`lint-imports`, `lint_dead_links.py` and pytest. A `Literal` is therefore a claim no tool
checks, which is how `RunState["outcome"]` came to be declared as four words while
`sync.mcp.propose` wrote five different ones into it.

What the scan can see is a write whose key is a literal string where it sits: a subscript
assignment plain or annotated, an entry in a dict literal a node returns, a `setdefault`, and
an argument to a helper that performs the subscript itself. What it cannot see is a key
computed at run time or a whole dict merged in under a name, and no census can enumerate
those -- the sentence above is bounded by that and by nothing else.

Inside those forms, silence is not an answer. A write that resolves to no word at all fails
naming its position, so the next reader either extends `_resolve` or records the case in
`UNRESOLVED` with the reason it must stay invisible. That half is the whole point: the first
version of this file returned the empty set for anything it could not follow and unioned the
results, so a *removed* word went red while an *added* one reached by a keyword argument, a
parameter, a dict lookup, an f-string, a method call or a `setdefault` was invisible. A gate
that reports clean over a vocabulary which has already grown is worse than no gate.

Shaped after `tests/test_corpus_writer.py`'s terminal-status scan, which holds the corpus
vocabulary the same way and for the same reason, and after `tests/test_decode_handlers.py`
for the census: a named entry per case rather than a count, keyed so that an edit above a
write does not invalidate a decision nobody revisited, and two checks holding it -- one that
fails when an unaccounted-for case appears, one that fails when an entry describes nothing.

The members are read with `typing.get_args` rather than copied, so a word added to one
`Literal` cannot leave this asserting the old set. Maintained the same way as the corpus scan:
a failure here is a vocabulary that grew, so add the word to the `Literal` and this follows.
Widening an assertion instead retires the check.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterator, NamedTuple, get_args

from sync.mcp.propose import PreviewOutcome
from sync.remediate.state import Outcome

SRC = Path(__file__).resolve().parents[1] / "src" / "sync"
REMEDIATE = SRC / "remediate"
MCP = SRC / "mcp"

# The pipeline's key alone in `sync.remediate`; both names in `sync.mcp`, where
# `preview_outcome` rides the state the driver returns and `outcome` is the published
# response. Every check below that reads `src/` reads exactly these two pairs.
SURVEYED: tuple[tuple[Path, frozenset[str]], ...] = (
    (REMEDIATE, frozenset({"outcome"})),
    (MCP, frozenset({"outcome", "preview_outcome"})),
)


def _parse(package: Path) -> dict[Path, ast.Module]:
    return {path: ast.parse(path.read_text(encoding="utf-8")) for path in sorted(package.rglob("*.py"))}


def _subscript_key(node: ast.AST) -> str | None:
    if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
        return node.slice.value
    return None


def _scopes(tree: ast.Module) -> dict[int, str]:
    """The dotted `def`/`class` trail enclosing every node, keyed by `id`.

    Descended rather than read off a parent pointer, which `ast` nodes do not carry. The ids
    are only valid while the caller still holds the tree they came from.
    """
    trails: dict[int, str] = {}

    def descend(node: ast.AST, trail: tuple[str, ...]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                descend(child, trail + (child.name,))
            else:
                trails[id(child)] = ".".join(trail) or "<module>"
                descend(child, trail)

    descend(tree, ())
    return trails


def _constants(trees: dict[Path, ast.Module]) -> dict[tuple[str, str], str]:
    """Module-level `NAME = "literal"`, keyed by the module that defines it.

    One flat namespace per package would let two modules defining the same name with
    different values resolve to whichever sorts last, which makes the word this reports a
    property of a filename. A bare name means the definition in its own module; the
    qualified `module.NAME` spelling is what crosses modules, and it is the form `tools.py`
    uses to write `propose.UNAVAILABLE` into the response.
    """
    found: dict[tuple[str, str], str] = {}
    for path, tree in trees.items():
        for node in tree.body:
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Constant):
                continue
            if not isinstance(node.value.value, str):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    found[(path.stem, target.id)] = node.value.value
    return found


def _resolve(node: ast.AST, module: str, constants: dict[tuple[str, str], str]) -> set[str]:
    """The words an expression can evaluate to, or nothing where the source cannot say.

    Unresolvable is empty rather than guessed. `state["preview_outcome"]` copied into a
    response dict names no word, and inventing one there would put a value in the vocabulary
    that no line of source chose.
    """
    if isinstance(node, ast.Constant):
        return {node.value} if isinstance(node.value, str) else set()
    if isinstance(node, ast.Name):
        value = constants.get((module, node.id))
        return {value} if value is not None else set()
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        value = constants.get((node.value.id, node.attr))
        return {value} if value is not None else set()
    if isinstance(node, ast.IfExp):
        return _resolve(node.body, module, constants) | _resolve(node.orelse, module, constants)
    return set()


class _Writer(NamedTuple):
    """A helper that performs the subscript, and where in a call to it the word travels.

    `bound` is whether the first parameter is `self` or `cls`, which a call through the
    instance supplies rather than passing: `self._finish(state, PROPOSED)` puts the word one
    position earlier than the signature does.
    """

    index: int
    parameter: str
    key: str
    bound: bool


def _writers(
    trees: dict[Path, ast.Module], keys: set[str]
) -> tuple[dict[tuple[str, str], _Writer], dict[int, tuple[str, str]]]:
    """Functions that assign one of their own parameters to one of `keys`, and those writes.

    Without this hop the scan sees `_finish(state, PROPOSED)` and one assignment of an
    unresolvable name, and reports an empty vocabulary for a module that writes five words.
    The assignment inside the helper is returned alongside so the survey can skip it: it is
    accounted for at every call site, and demanding that it resolve on its own would fail a
    gate on the one write the registry exists to follow.

    Keyed by the module that defines the function, because a package is not one namespace: a
    second `_finish` elsewhere in `sync/mcp/` writes nothing, and feeding its argument into
    the vocabulary fails the gate naming a word no outcome key ever held.
    """
    found: dict[tuple[str, str], _Writer] = {}
    bodies: dict[int, tuple[str, str]] = {}
    for path, tree in trees.items():
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            params = [arg.arg for arg in node.args.args]
            bound = bool(params) and params[0] in {"self", "cls"}
            for sub in ast.walk(node):
                if not isinstance(sub, ast.Assign) or not isinstance(sub.value, ast.Name):
                    continue
                if sub.value.id not in params:
                    continue
                for target in sub.targets:
                    key = _subscript_key(target)
                    if key in keys:
                        found[(path.stem, node.name)] = _Writer(
                            params.index(sub.value.id), sub.value.id, key, bound
                        )
                        bodies[id(sub)] = (path.stem, node.name)
    return found, bodies


class _Write(NamedTuple):
    """One place a word reaches an outcome key, and the words it can be.

    `words` empty means the resolver could not follow this write to any word. That is a
    failure rather than a silence: an added word reached by a form the scan cannot resolve
    would otherwise leave the vocabulary assertion green.
    """

    path: str
    scope: str
    key: str
    line: int
    words: frozenset[str]

    @property
    def census_key(self) -> str:
        # Deliberately carries no line. A comment added above a write moves it, and a census
        # entry that an unrelated edit invalidates is one somebody eventually silences --
        # measured on `tests/test_decode_handlers.py`, whose keys were positional until B63.
        return f"{self.path}::{self.scope}::{self.key}"

    @property
    def position(self) -> str:
        return f"{self.path}:{self.line}"


def _called_writer(
    node: ast.Call, module: str, writers: dict[tuple[str, str], _Writer]
) -> tuple[tuple[str, str], _Writer] | None:
    """The writer a call names, however the call spells it.

    `self._finish(...)` and `propose._finish(...)` reach the same function a bare
    `_finish(...)` does. `self` and `cls` mean this module; any other qualifier names the
    module that defines it, which is how `_constants` reads `propose.UNAVAILABLE`.
    """
    if isinstance(node.func, ast.Name):
        name = (module, node.func.id)
    elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
        owner = module if node.func.value.id in {"self", "cls"} else node.func.value.id
        name = (owner, node.func.attr)
    else:
        return None
    writer = writers.get(name)
    return None if writer is None else (name, writer)


def _unpacked_keys(target: ast.AST, keys: set[str]) -> Iterator[str]:
    """Keys written by a subscript sitting inside a tuple or list target.

    `a, state["outcome"] = ...` writes the key from an element of the right-hand side, which
    this resolver does not take apart. Reported so it fails rather than passing unseen.
    """
    if isinstance(target, (ast.Tuple, ast.List)):
        for element in target.elts:
            key = _subscript_key(element)
            if key in keys:
                yield key
            yield from _unpacked_keys(element, keys)


def _writes(package: Path, keys: set[str]) -> list[_Write]:
    """Every write into one of `keys` this package makes, resolved as far as the source says."""
    trees = _parse(package)
    constants = _constants(trees)
    writers, bodies = _writers(trees, keys)

    found: list[_Write] = []
    # A registered writer's own `state[key] = parameter` is accounted for at its call sites, so
    # it is held here and emitted only if nothing ever calls it -- a helper nobody calls carries
    # no word, and dropping it outright would be the silence this file exists to remove.
    deferred: dict[tuple[str, str], list[_Write]] = {}
    called: set[tuple[str, str]] = set()

    for path, tree in trees.items():
        module = path.stem
        relative = f"{package.name}/{path.relative_to(package).as_posix()}"
        scopes = _scopes(tree)

        def record(
            node: ast.AST,
            key: str,
            words: set[str],
            anchor: ast.AST | None = None,
            writer: tuple[str, str] | None = None,
        ) -> None:
            # The scope comes from the statement and the line from whatever a reader would
            # look at -- for a dict that is the entry, not the brace several lines above it.
            line = (anchor or node).lineno
            write = _Write(relative, scopes[id(node)], key, line, frozenset(words))
            if writer is None:
                found.append(write)
            else:
                deferred.setdefault(writer, []).append(write)

        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                owner = bodies.get(id(node))
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                # An augmented assignment builds its value out of the old one, which this
                # resolver holds nothing of, so it resolves to no word and says so.
                value = None if isinstance(node, ast.AugAssign) else node.value
                for target in targets:
                    key = _subscript_key(target)
                    if key in keys:
                        words = _resolve(value, module, constants) if value is not None else set()
                        record(node, key, words, writer=owner)
                    for unpacked in _unpacked_keys(target, keys):
                        record(node, unpacked, set())
            elif isinstance(node, ast.Dict):
                for key_node, value in zip(node.keys, node.values):
                    if isinstance(key_node, ast.Constant) and key_node.value in keys:
                        record(
                            node, key_node.value, _resolve(value, module, constants), key_node
                        )
            elif isinstance(node, ast.Call):
                named = _called_writer(node, module, writers)
                if named is not None:
                    name, writer = named
                    called.add(name)
                    record(
                        node, writer.key,
                        _resolve_argument(node, writer, module, constants),
                    )
                    continue
                setdefault = _setdefault_key(node, keys)
                if setdefault is not None:
                    words = _resolve(node.args[1], module, constants) if len(node.args) > 1 else set()
                    record(node, setdefault, words)

    for name, writes in deferred.items():
        if name not in called:
            found.extend(writes)
    return found


def _resolve_argument(
    node: ast.Call, writer: _Writer, module: str, constants: dict[tuple[str, str], str]
) -> set[str]:
    """The word a call hands its writer, positionally or by keyword.

    Both spellings, because they are the same call: `_finish(state, TIMED_OUT)` and
    `_finish(state, outcome=TIMED_OUT)` write the same key with the same word, and a scan
    that resolved only the first reported the second as no write at all.
    """
    index = writer.index
    if writer.bound and isinstance(node.func, ast.Attribute):
        index -= 1
    if 0 <= index < len(node.args):
        return _resolve(node.args[index], module, constants)
    for keyword in node.keywords:
        if keyword.arg == writer.parameter:
            return _resolve(keyword.value, module, constants)
    return set()


def _setdefault_key(node: ast.Call, keys: set[str]) -> str | None:
    """The key a `state.setdefault("outcome", ...)` writes, if it writes one of `keys`."""
    if not isinstance(node.func, ast.Attribute) or node.func.attr != "setdefault":
        return None
    if not node.args or not isinstance(node.args[0], ast.Constant):
        return None
    return node.args[0].value if node.args[0].value in keys else None


def _words_written_to(package: Path, keys: set[str]) -> set[str]:
    """Every word this package writes into one of `keys`."""
    found: set[str] = set()
    for write in _writes(package, keys):
        found |= write.words
    return found


def _subscript_writes(package: Path, key: str) -> list[str]:
    """`file:line` for every `something[key] = ...` in the package, annotated or not.

    Kept apart from a dict literal deliberately. Inside `sync.mcp` a `{"outcome": ...}` is
    the published MCP response, whose vocabulary is the preview's; a `state["outcome"] = ...`
    is a write into `RunState`, whose declared type holds none of those words.

    `AnnAssign` is here because `state["outcome"]: Outcome = "abandoned"` is the same write
    with a type on it, and reading only `Assign` let that spelling through.
    """
    found: list[str] = []
    for path, tree in _parse(package).items():
        relative = f"{package.name}/{path.relative_to(package).as_posix()}"
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any(_subscript_key(target) == key for target in targets):
                    found.append(f"{relative}:{node.lineno}")
    return sorted(found)


def _unresolvable() -> list[_Write]:
    """Every write in `src/` the resolver could not follow to a single word."""
    return [
        write
        for package, keys in SURVEYED
        for write in _writes(package, set(keys))
        if not write.words
    ]


# Writes that resolve to no word and are accepted that way, as of 2026-08-05. Keyed by file,
# enclosing scope and the key written -- none of which an edit above the write moves.
#
# This is a list and never a count. A count absorbs both a repair and a new blind spot in
# silence; a named entry has to be deleted by whoever removes the write. Adding a line is a
# decision rather than a formality: it says somebody looked at the write and concluded no word
# can be attributed to it here, which is different from the resolver not having been taught the
# form yet. That second case is a resolver to extend, not a line to add.

# The word was chosen elsewhere and is counted where it was chosen. `propose.run_to_static_verify`
# writes `state["preview_outcome"]` from its own vocabulary and this copies that value forward
# into the published response, so resolving it would need the value of a key at run time --
# and inventing a word here would put one in the vocabulary that no line of source chose.
_COPIED_FORWARD = ("mcp/tools.py::GraphSurface.propose_patch::outcome",)

UNRESOLVED: tuple[str, ...] = _COPIED_FORWARD


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


def test_no_write_into_an_outcome_key_resolves_to_nothing():
    """The half the first version of this file lacked.

    `_resolve` answers with the empty set for anything it cannot follow and the vocabulary
    assertions union the results, so a *removed* word goes red and an *added* one reached by a
    form the scan cannot follow is invisible. Measured: a sixth word reached by
    `_finish(state, outcome=TIMED_OUT)` -- the keyword spelling of the very helper the scan
    registers -- left all three assertions green.
    """
    unaccounted = sorted(
        f"{write.census_key} at {write.position}"
        for write in _unresolvable()
        if write.census_key not in UNRESOLVED
    )

    assert not unaccounted, (
        "these writes reach an outcome key and resolve to no word, so nothing above can tell "
        "whether the word they carry is in the vocabulary:\n  " + "\n  ".join(unaccounted) + "\n"
        "Teach `_resolve` the form if the source says which word arrives. If it genuinely "
        "cannot -- the value is only known at run time -- add the key to UNRESOLVED under a "
        "comment saying why, so the next reader inherits the decision rather than the question."
    )


def test_no_entry_in_the_unresolved_census_is_gone():
    """The census only shrinks, and a line leaves in the commit that resolves its write."""
    stale = sorted(set(UNRESOLVED) - {write.census_key for write in _unresolvable()})

    assert not stale, (
        "UNRESOLVED names writes that either resolve now or are no longer in src/:\n  "
        + "\n  ".join(stale) + "\n"
        "Delete the line. A census entry that describes nothing is one nobody can check."
    )


def _colliding(writes: list[_Write]) -> dict[str, list[str]]:
    """Census keys naming more than one write, each with the positions that share it."""
    found: dict[str, list[_Write]] = {}
    for write in writes:
        found.setdefault(write.census_key, []).append(write)
    return {
        key: [write.position for write in sorted(sharing, key=lambda w: w.line)]
        for key, sharing in found.items()
        if len(sharing) > 1
    }


def test_no_two_unresolvable_writes_share_a_census_key():
    """The cost of a key that carries no line, refused loudly rather than absorbed.

    `run_to_static_verify` alone holds six writes to one key in one scope, so this is not a
    theoretical pairing -- it is what the census looks like the moment two of them stop
    resolving. One entry would then excuse both, and the second would be invisible again.
    """
    collisions = _colliding(_unresolvable())

    assert not collisions, "these writes cannot be told apart by census key:\n  " + "\n  ".join(
        f"{key} at {', '.join(positions)}" for key, positions in collisions.items()
    )


def _synthetic(root: Path, source: str) -> Path:
    """A one-module package this test wrote, under a name its positions can carry.

    Named rather than `tmp_path` itself, because a position is reported relative to the
    package and a pytest temporary directory would put a per-run name in every assertion.
    """
    package = root / "drifted"
    package.mkdir()
    (package / "driver.py").write_text(source, encoding="utf-8")
    return package


def test_a_write_the_resolver_cannot_follow_is_reported_with_its_position(tmp_path):
    """What the check over `src/` proves is detectable, proven on a package this test wrote.

    Each of these is a form measured silent before: a parameter, a dict lookup, an f-string,
    a `setdefault`, a tuple unpack and an annotated assignment. None of them resolves, and the
    point is that each is reported rather than skipped.
    """
    package = _synthetic(
        tmp_path,
        "def from_parameter(state, word):\n"
        '    state["outcome"] = word\n'
        "def from_lookup(state, table):\n"
        '    state["outcome"] = table["key"]\n'
        "def from_format(state, stage):\n"
        '    state["outcome"] = f"failed_at_{stage}"\n'
        "def from_setdefault(state, word):\n"
        '    state.setdefault("outcome", word)\n'
        "def from_unpack(state, pair):\n"
        '    state["outcome"], rest = pair\n'
        "def from_annotation(state, word):\n"
        '    state["outcome"]: str = word\n',
    )

    unresolved = sorted(
        (write.line, write.census_key)
        for write in _writes(package, {"outcome"})
        if not write.words
    )

    assert unresolved == [
        (2, "drifted/driver.py::from_parameter::outcome"),
        (4, "drifted/driver.py::from_lookup::outcome"),
        (6, "drifted/driver.py::from_format::outcome"),
        (8, "drifted/driver.py::from_setdefault::outcome"),
        (10, "drifted/driver.py::from_unpack::outcome"),
        (12, "drifted/driver.py::from_annotation::outcome"),
    ]


def test_two_unresolvable_writes_one_key_cannot_tell_apart_are_refused_naming_both(tmp_path):
    """There is no such pair in `src/`; this is what happens on the day somebody writes one."""
    package = _synthetic(
        tmp_path,
        "def run(state, first, second):\n"
        '    state["outcome"] = first\n'
        '    state["outcome"] = second\n',
    )

    collisions = _colliding([w for w in _writes(package, {"outcome"}) if not w.words])

    assert collisions == {
        "drifted/driver.py::run::outcome": ["drifted/driver.py:2", "drifted/driver.py:3"]
    }


def test_a_word_reaching_a_writer_by_keyword_is_the_same_write_as_by_position(tmp_path):
    """The measured counterexample, held so the resolver cannot quietly stop following it.

    `_finish(state, outcome=TIMED_OUT)` is the spelling that put a sixth word on every
    finishing preview while all three assertions stayed green.
    """
    package = _synthetic(
        tmp_path,
        'TIMED_OUT = "timed_out"\n'
        "def _finish(state, outcome):\n"
        '    state["preview_outcome"] = outcome\n'
        "def run(state):\n"
        "    return _finish(state, outcome=TIMED_OUT)\n",
    )

    assert _words_written_to(package, {"preview_outcome"}) == {"timed_out"}
    assert [w for w in _writes(package, {"preview_outcome"}) if not w.words] == []


def test_a_method_call_reaches_the_writer_a_bare_call_would(tmp_path):
    """`self._finish(...)` was registered and never matched: the call branch read `ast.Name`
    funcs alone, so every write through a method was no write at all."""
    package = _synthetic(
        tmp_path,
        'TIMED_OUT = "timed_out"\n'
        "class Driver:\n"
        "    def _finish(self, state, outcome):\n"
        '        state["preview_outcome"] = outcome\n'
        "    def run(self, state):\n"
        "        return self._finish(state, TIMED_OUT)\n",
    )

    assert _words_written_to(package, {"preview_outcome"}) == {"timed_out"}


def test_a_writer_nothing_calls_still_reports_the_write_in_its_body(tmp_path):
    """The hole the writer registry would otherwise open.

    A helper's own `state[key] = parameter` is skipped because its call sites carry the word.
    A helper nobody calls has no call sites, so skipping it would delete the only write in the
    package -- an empty vocabulary reported as if the package wrote nothing.
    """
    package = _synthetic(
        tmp_path,
        "def _finish(state, outcome):\n"
        '    state["preview_outcome"] = outcome\n',
    )

    assert [w.census_key for w in _writes(package, {"preview_outcome"}) if not w.words] == [
        "drifted/driver.py::_finish::preview_outcome"
    ]


def test_an_annotated_subscript_write_is_a_subscript_write(tmp_path):
    """`state["outcome"]: Outcome = "abandoned"` inside `sync.mcp` passed the third assertion
    while writing the pipeline's key, because only `ast.Assign` was read."""
    package = _synthetic(
        tmp_path,
        "def run(state):\n"
        '    state["outcome"]: str = "abandoned"\n',
    )

    assert _subscript_writes(package, "outcome") == ["drifted/driver.py:2"]


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


def test_a_writer_is_a_writer_only_inside_the_module_that_defines_it(tmp_path):
    """A name is registered per module, because the package is not one namespace.

    `_finish` here writes the preview key; the `_finish` next to it is a different function
    that writes nothing. Resolving writers by bare name across the package feeds the second
    one's argument into the vocabulary and fails the gate naming a word no outcome key ever
    held -- a false red, which costs a gate the same trust a false green does.
    """
    (tmp_path / "preview.py").write_text(
        'PROPOSED = "proposed"\n'
        "def _finish(state, outcome):\n"
        '    state["preview_outcome"] = outcome\n'
        "def run(state):\n"
        "    return _finish(state, PROPOSED)\n",
        encoding="utf-8",
    )
    (tmp_path / "reporting.py").write_text(
        "def _finish(state, note):\n"
        "    return note\n"
        "def log(state):\n"
        '    return _finish(state, "not-an-outcome")\n',
        encoding="utf-8",
    )

    assert _words_written_to(tmp_path, {"outcome", "preview_outcome"}) == {"proposed"}


def test_a_constant_resolves_only_where_it_is_defined_or_where_it_is_qualified(tmp_path):
    """Two modules, one constant name, two values -- and a bare use means the local one.

    Keyed flat, the two collide and whichever module sorts last decides, so the word the
    gate reports depends on a filename. The qualified spelling still crosses modules, which
    is the form `tools.py` uses to write `propose.UNAVAILABLE` into the response.
    """
    (tmp_path / "alpha.py").write_text(
        'WORD = "proposed"\n'
        "def a(state):\n"
        '    state["preview_outcome"] = WORD\n',
        encoding="utf-8",
    )
    (tmp_path / "zulu.py").write_text(
        "import alpha\n"
        'WORD = "not-an-outcome"\n'
        "def z(state):\n"
        '    return {"outcome": alpha.WORD}\n',
        encoding="utf-8",
    )

    assert _words_written_to(tmp_path, {"outcome", "preview_outcome"}) == {"proposed"}
