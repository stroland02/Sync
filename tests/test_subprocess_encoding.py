"""Whether every `subprocess.run` in `src/` states a defence against the child's encoding.

`encoding="utf-8"` says how to decode the bytes, not which bytes arrive. Measured on this
machine, a Python child with no `PYTHONIOENCODING` writes cp1252: the child emitted
`b'caf\\xe9 \\x97\\r\\n'` for `café —`, the parent's reader thread raised
`UnicodeDecodeError`, and `subprocess.run` returned **exit code 0 with `stdout` set to `None`**.
That is the whole defect. It does not raise where the call is written, so no `try` catches it and
no exit code reports it; the next line that concatenates `stdout` raises `TypeError` somewhere
unrelated. `test_the_old_form_loses_stdout_on_a_child_that_chooses_its_own_encoding` holds that
measurement, and it is the reason this file exists rather than a style preference.

Why this cannot be a coverage question, or a runtime one
-------------------------------------------------------
The failing path is a property of the source. No test in this repository executes it: every
fixture here is ASCII, so every one of these calls decodes cleanly forever and the suite is
silent. The failure arrives first against a real customer repository or real vendor data, which
is the same argument `scripts/lint_encoding.py` and `scripts/lint_dead_links.py` make. So the
check is static, over call sites, like theirs.

The inventory is read out of `src/` by AST rather than listed here, following
`tests/test_decode_handlers.py`: a `subprocess.run` added tomorrow is in scope without anyone
remembering to register it.

What the check requires, and why not one literal spelling
--------------------------------------------------------
`CLAUDE.md` names `PYTHONIOENCODING=utf-8` in the child's environment as the remedy. A check
demanding that literal would be wrong here, and wrong in the expensive direction:
**not one of the fifteen calls in `src/` spawns a Python process.** They spawn `git`, `oasdiff`,
`gh`, `node`, and the `npm`/`pnpm`/`yarn` shims. `PYTHONIOENCODING` is read by none of them, so
demanding it would fire on every call site and be satisfied by setting a variable no child looks
at -- a check that passes while proving nothing, which is worse than no check.

Requiring `errors="replace"` everywhere is wrong in the other direction. It is lossy:
`café —` comes back as `caf� �`, with the accent and the dash collapsed to the
same character. Where the output is **data** that is a silent corruption, and this repository has
already shipped it once -- `tests/test_decode_handlers.py::_drive_literal_call_sites` records
`_literal_call_sites` reading customer sources that way until B57, where a mangled `operation_id`
became a call site joined against a model nothing retires. `CLAUDE.md` scopes `errors="replace"`
to output that is "diagnostic rather than data" for exactly that reason, and a checker cannot tell
those two apart.

So the check requires that a **choice has been made**, and accepts any of four routes:

1. **The call does not decode.** No `text=`, `encoding=`, `errors=` or `universal_newlines=`;
   bytes cannot raise. `sync.signals.stripe.adapter` fetches a spec this way on purpose.
2. **`errors=` is passed.** The decode cannot raise, so the reader-thread failure is gone. The
   cost is mojibake, which is why this is the right route for diagnostics and the wrong one for
   data. `sync.verify.replay` already takes it.
3. **`env=` is passed and names `PYTHONIOENCODING`.** The only route that keeps the output
   faithful, and the only one available when the output is data and the child is Python.
4. **An exemption marker on the call, carrying a reason.** For a child that cannot emit
   non-UTF-8, which is a fact about the child that no static check can know:

       result = subprocess.run(  # subprocess-encoding: allow - git normalises paths to utf-8

   The reason is required. A marker with nothing after `allow` is reported as a violation, copying
   `scripts/lint_dead_links.py`: an opt-out that says nothing is how a check decays into
   decoration. Route 4 is for a measured fact, not for "not yet looked at" -- that is what the
   baseline is for.

Two mechanisms, deliberately not one
------------------------------------
An **exemption** lives beside the call and is permanent: somebody established that this child
cannot emit non-UTF-8 and wrote down how they know. The **baseline** at
`scripts/subprocess_encoding_baseline.txt` is debt: a call nobody has judged yet, in a file this
task could not edit. It may only shrink, and an entry that stops describing a violation fails the
gate until it is deleted, so a fix removes its line in the same commit. Every entry names the task
that retires it.

The baseline key is `<path>:<enclosing qualname>`, not `<path>:<line>`. `test_decode_handlers.py`
pays a real price for a positional key -- it re-anchored seven keys in one afternoon over comment
blocks -- and says there is no stable identity to key on instead. For a `subprocess.run` there is
one: the function that holds it. An edit above the call does not move the key. Two calls in one
function are disambiguated by `#<n>` in line order, which is positional again but only within a
single function body.

Known limits, so nobody rediscovers them
----------------------------------------
`PYTHONIOENCODING` is looked for as a string constant inside the `env=` expression itself. A call
that builds its environment in a helper satisfies route 3 by argument and not by inspection, and
needs route 2 or route 4 instead. Tightness is deliberate: routes 1-3 *grant* satisfaction, so a
loose reading here produces a false pass, and a false pass is the outcome this file cannot afford.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
BASELINE = ROOT / "scripts" / "subprocess_encoding_baseline.txt"

# Every `subprocess` entry point that can hand back decoded text. Only `run` appears in `src/`
# today; the others are here so one added tomorrow is in scope, which is the same reason the
# inventory is read from the source rather than listed.
_SPAWNERS = frozenset({"run", "Popen", "check_output"})

# Kwargs whose presence means the call decodes. `encoding=` and `errors=` are on this list
# because either one puts `subprocess` into text mode on its own, with no `text=True` in sight.
_DECODING_KWARGS = frozenset({"text", "universal_newlines", "encoding", "errors"})

# `# subprocess-encoding: allow <reason>`, the spelling `lint_dead_links.py` established.
_MARKER = re.compile(r"#\s*subprocess-encoding:\s*allow\b(?P<rest>.*)$")

# Punctuation a reason may be introduced with. ASCII only; anything else stays part of the
# reason, which changes nothing -- the check is that a reason is there at all.
_REASON_LEAD = " \t:-"


@dataclass(frozen=True)
class SubprocessCall:
    """One spawning call in the scanned tree, and what it says about the child's encoding."""

    path: str
    line: int
    qualname: str
    ordinal: int
    decodes: bool
    passes_errors: bool
    names_pythonioencoding: bool
    exemption: str | None

    @property
    def key(self) -> str:
        suffix = f"#{self.ordinal}" if self.ordinal else ""
        return f"{self.path}:{self.qualname}{suffix}"

    @property
    def satisfied(self) -> bool:
        if not self.decodes:
            return True
        if self.passes_errors or self.names_pythonioencoding:
            return True
        return bool(self.exemption)

    @property
    def complaint(self) -> str:
        if self.exemption == "":
            return (
                "exempts itself with no reason; name what you established about the child, "
                "because an opt-out that says nothing is decoration"
            )
        return (
            "decodes the child's output with no defence against the child choosing its own "
            "encoding; pass errors=, or PYTHONIOENCODING in env=, or exempt it with a reason "
            "(# subprocess-encoding: allow - <why this child cannot emit non-utf-8>)"
        )


def _called_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _is_spawner(node: ast.Call) -> bool:
    """Whether this call spawns a child through `subprocess`.

    Attribute form only -- `subprocess.run(...)`. A bare `run(...)` is not assumed to be this
    one: `run` is an ordinary name, and treating every call of it as a spawner would demand an
    encoding defence from unrelated code.
    """
    func = node.func
    if not isinstance(func, ast.Attribute) or func.attr not in _SPAWNERS:
        return False
    value = func.value
    if isinstance(value, ast.Name):
        return value.id == "subprocess"
    if isinstance(value, ast.Attribute):
        return value.attr == "subprocess"
    return False


def _kwarg(node: ast.Call, name: str) -> ast.expr | None:
    for keyword in node.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def _decodes(node: ast.Call) -> bool:
    """Whether the call hands back `str` rather than `bytes`.

    A `text=` or `universal_newlines=` that is not a literal cannot be judged and is read as
    text -- the conservative direction, the same one `lint_encoding.py._is_binary_open` takes.
    A caller passing a computed flag can still satisfy this check, by any of the four routes.
    """
    for name in ("encoding", "errors"):
        if _kwarg(node, name) is not None:
            return True
    for name in ("text", "universal_newlines"):
        value = _kwarg(node, name)
        if value is None:
            continue
        if isinstance(value, ast.Constant):
            if value.value:
                return True
        else:
            return True
    return False


def _names_pythonioencoding(node: ast.Call) -> bool:
    """Whether the `env=` expression itself mentions `PYTHONIOENCODING`."""
    env = _kwarg(node, "env")
    if env is None:
        return False
    return any(
        isinstance(sub, ast.Constant)
        and isinstance(sub.value, str)
        and sub.value == "PYTHONIOENCODING"
        for sub in ast.walk(env)
    )


def _exemption(node: ast.Call, lines: list[str]) -> str | None:
    """The marker's reason, `""` for a marker that gives none, `None` for no marker.

    Read from any line the call itself spans. A `subprocess.run` runs to a dozen lines here and
    the readable place for the marker is beside the argument that provoked it, so restricting it
    to the opening line -- which is what `lint_dead_links.py` does for a one-line `def` -- would
    push it somewhere nobody looks.
    """
    first = node.lineno - 1
    last = (node.end_lineno or node.lineno) - 1
    for index in range(first, min(last + 1, len(lines))):
        match = _MARKER.search(lines[index])
        if match is not None:
            return match.group("rest").strip(_REASON_LEAD).strip()
    return None


def subprocess_calls(source: str, filename: str) -> list[SubprocessCall]:
    """Every spawning call in one module, each keyed by the function that holds it."""
    tree = ast.parse(source, filename=filename)
    lines = source.splitlines()
    found: list[SubprocessCall] = []
    seen: dict[str, int] = {}

    def visit(node: ast.AST, scope: tuple[str, ...]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                visit(child, scope + (child.name,))
                continue
            if isinstance(child, ast.Call) and _is_spawner(child):
                qualname = ".".join(scope) or "<module>"
                ordinal = seen.get(qualname, 0)
                seen[qualname] = ordinal + 1
                found.append(
                    SubprocessCall(
                        path=filename,
                        line=child.lineno,
                        qualname=qualname,
                        ordinal=ordinal,
                        decodes=_decodes(child),
                        passes_errors=_kwarg(child, "errors") is not None,
                        names_pythonioencoding=_names_pythonioencoding(child),
                        exemption=_exemption(child, lines),
                    )
                )
            visit(child, scope)

    visit(tree, ())
    return sorted(found, key=lambda call: call.line)


def scan_tree(src: Path = SRC) -> list[SubprocessCall]:
    """The whole inventory, relative to `src/`."""
    found: list[SubprocessCall] = []
    for path in sorted(src.rglob("*.py")):
        relative = path.relative_to(src).as_posix()
        found.extend(subprocess_calls(path.read_text(encoding="utf-8"), relative))
    return found


def load_baseline(path: Path = BASELINE) -> set[str]:
    if not path.exists():
        return set()
    return {
        stripped
        for line in path.read_text(encoding="utf-8").splitlines()
        if (stripped := line.strip()) and not stripped.startswith("#")
    }


# --- the rule itself, measured rather than asserted -------------------------------
#
# Without these the check above is a style rule. With them it has a reproduced defect behind it.

# Built from escapes, not typed literally: every source file in this repository is ASCII, and a
# committed non-ASCII byte is a thing git and every editor round-trip through a heuristic.
NON_ASCII = "café —"
CHILD = "import sys; sys.stdout.write({!r} + chr(10))".format(NON_ASCII)


def _child_env(**overrides: str) -> dict[str, str]:
    """A child environment with `PYTHONIOENCODING` removed unless an override puts it back.

    The suite is run with `PYTHONIOENCODING=utf-8` exported, which a child inherits. Left in
    place it would remedy the very defect these tests exist to reproduce, and they would pass
    for the wrong reason -- the false-verdict shape this whole file is about.
    """
    import os

    env = {name: value for name, value in os.environ.items() if name != "PYTHONIOENCODING"}
    env.update(overrides)
    return env


def test_a_python_child_writes_the_locale_codepage_and_not_utf_8() -> None:
    """The premise. Read as bytes, so nothing about the parent's decoding is involved."""
    result = subprocess.run(
        [sys.executable, "-c", CHILD], capture_output=True, env=_child_env()
    )
    assert result.returncode == 0
    assert result.stdout.rstrip(b"\r\n") != NON_ASCII.encode("utf-8"), (
        "this child emitted utf-8, so the defect below cannot be reproduced on this machine "
        "and the rule needs re-measuring rather than trusting"
    )
    with pytest.raises(UnicodeDecodeError):
        result.stdout.decode("utf-8")


def test_the_old_form_loses_stdout_on_a_child_that_chooses_its_own_encoding() -> None:
    """`text=True, encoding="utf-8"` and nothing else: exit 0, no exception, `stdout` is `None`.

    The `UnicodeDecodeError` is raised on `subprocess`'s reader thread. `threading.excepthook`
    is installed to capture it, which is also what proves *where* it was raised -- the claim is
    not merely that output went missing but that the failure happened somewhere no caller can
    catch it. Without the hook it would print a traceback into the suite's output and the test
    would assert only on the symptom.
    """
    raised: list[BaseException] = []
    original = threading.excepthook
    threading.excepthook = lambda args: raised.append(args.exc_value)
    try:
        result = subprocess.run(
            [sys.executable, "-c", CHILD],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=_child_env(),
        )
    finally:
        threading.excepthook = original

    assert result.returncode == 0, "the child succeeded; nothing about it failed"
    assert result.stdout is None, (
        f"expected stdout=None from a swallowed decode error, got {result.stdout!r}"
    )
    assert [type(exc) for exc in raised] == [UnicodeDecodeError], (
        f"expected one UnicodeDecodeError on a reader thread, got {raised!r}"
    )


def test_pythonioencoding_in_the_child_env_is_what_makes_that_call_correct() -> None:
    """Route 3, and the only route that keeps the output faithful."""
    result = subprocess.run(
        [sys.executable, "-c", CHILD],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=_child_env(PYTHONIOENCODING="utf-8"),
    )
    assert result.stdout is not None and result.stdout.rstrip("\r\n") == NON_ASCII


def test_errors_replace_survives_the_decode_but_does_not_preserve_the_bytes() -> None:
    """Route 2, and why the check does not demand it everywhere.

    Both non-ASCII characters come back as the same replacement character. For a diagnostic that
    is the right trade. For a path, an `operationId`, or an author's name it is a wrong answer
    that no exception marks, which is the failure B57 records.
    """
    result = subprocess.run(
        [sys.executable, "-c", CHILD],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_child_env(),
    )
    assert result.stdout is not None, "errors= must stop the reader thread from raising"
    assert result.stdout.rstrip("\r\n") != NON_ASCII
    assert result.stdout.count("�") == 2, (
        f"expected both characters replaced, got {result.stdout!r}"
    )


# --- the check is not vacuous ------------------------------------------------------

_UNDEFENDED = """
import subprocess

def build():
    return subprocess.run(["git", "log"], capture_output=True, text=True, encoding="utf-8")
"""

_BYTES = """
import subprocess

def build():
    return subprocess.run(["git", "log"], capture_output=True)
"""

_ERRORS = """
import subprocess

def build():
    return subprocess.run(
        ["git", "log"], capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
"""

_ENV = """
import subprocess

def build():
    return subprocess.run(
        ["python", "-c", "print(1)"], capture_output=True, text=True, encoding="utf-8",
        env={"PYTHONIOENCODING": "utf-8"},
    )
"""

_EXEMPT = """
import subprocess

def build():
    return subprocess.run(  # subprocess-encoding: allow - git normalises paths to utf-8
        ["git", "ls-files", "-z"], capture_output=True, text=True, encoding="utf-8",
    )
"""

_EXEMPT_WITHOUT_REASON = """
import subprocess

def build():
    return subprocess.run(  # subprocess-encoding: allow
        ["git", "ls-files", "-z"], capture_output=True, text=True, encoding="utf-8",
    )
"""

_ENCODING_ONLY = """
import subprocess

def build():
    return subprocess.run(["git", "log"], capture_output=True, encoding="utf-8")
"""

_TWO_IN_ONE_FUNCTION = """
import subprocess

def build():
    subprocess.run(["git", "a"], capture_output=True, text=True, encoding="utf-8")
    subprocess.run(["git", "b"], capture_output=True, text=True, encoding="utf-8")
"""


@pytest.mark.parametrize(
    "label, source, satisfied",
    [
        ("undefended", _UNDEFENDED, False),
        ("bytes", _BYTES, True),
        ("errors=", _ERRORS, True),
        ("PYTHONIOENCODING in env=", _ENV, True),
        ("exemption with a reason", _EXEMPT, True),
        ("exemption without a reason", _EXEMPT_WITHOUT_REASON, False),
        # `encoding=` alone puts subprocess into text mode. A check keyed on `text=True` would
        # call this one bytes and let the defect straight through.
        ("encoding= with no text=", _ENCODING_ONLY, False),
    ],
)
def test_the_check_answers_each_route_correctly(label: str, source: str, satisfied: bool) -> None:
    compile(source, f"<{label}>", "exec")
    found = subprocess_calls(source, f"<{label}>")
    assert len(found) == 1, f"{label}: expected one call, found {len(found)}"
    assert found[0].satisfied is satisfied, f"{label}: read as satisfied={found[0].satisfied}"


def test_two_calls_in_one_function_get_distinct_keys() -> None:
    """Otherwise one baseline entry would silently stand in for both."""
    found = subprocess_calls(_TWO_IN_ONE_FUNCTION, "m.py")
    assert [call.key for call in found] == ["m.py:build", "m.py:build#1"]


def test_a_key_does_not_move_when_a_line_is_added_above_the_call() -> None:
    """The whole reason the key is the enclosing function rather than the line number."""
    before = subprocess_calls(_UNDEFENDED, "m.py")
    shifted = _UNDEFENDED.replace("def build():", "# a new comment\ndef build():")
    after = subprocess_calls(shifted, "m.py")
    assert [c.key for c in before] == [c.key for c in after]
    assert before[0].line != after[0].line


def test_a_bare_run_is_not_read_as_a_subprocess_spawner() -> None:
    """`run` is an ordinary name. Demanding an encoding defence from every call of it is noise."""
    assert subprocess_calls("run(['git'], text=True)\n", "m.py") == []


# --- the gate ---------------------------------------------------------------------


def test_the_inventory_finds_every_call_a_textual_scan_finds() -> None:
    """A scan that silently matches nothing reports success.

    `lint_encoding.py` and `lint_dead_links.py` both carry this guard because the
    import-boundary check once exited 0 without parsing its own argument. Here the way to match
    nothing is an AST walk that misses a call -- one nested in a `with`, a comprehension, or a
    lambda -- and the symptom would be a green gate.
    """
    assert SRC.is_dir(), f"{SRC} is missing; this gate would otherwise scan nothing and pass"
    textual = sum(
        path.read_text(encoding="utf-8").count("subprocess.run(")
        for path in SRC.rglob("*.py")
    )
    assert textual > 0, "no subprocess.run in src/ at all; the pattern must have moved"
    assert len(scan_tree()) == textual, (
        f"the AST walk found {len(scan_tree())} calls where the text finds {textual}"
    )


def test_every_decoding_subprocess_call_states_a_defence() -> None:
    baseline = load_baseline()
    new = [call for call in scan_tree() if not call.satisfied and call.key not in baseline]
    assert not new, "\n  " + "\n  ".join(
        f"{call.path}:{call.line} ({call.key}) {call.complaint}" for call in new
    )


def test_no_baseline_entry_has_stopped_describing_a_violation() -> None:
    """What makes the baseline shrink rather than rot.

    A repaired call fails this until its line is deleted, in the commit that repaired it.
    """
    violating = {call.key for call in scan_tree() if not call.satisfied}
    stale = sorted(load_baseline() - violating)
    assert not stale, (
        f"these entries in {BASELINE.name} no longer describe a violation; delete them in the "
        "commit that fixed them:\n  " + "\n  ".join(stale)
    )


def test_every_baseline_entry_names_the_task_that_retires_it() -> None:
    """A baseline is debt, and debt with no owner is a permanent exemption in disguise.

    An exemption is the mechanism for something nobody will ever fix, and it lives in `src/`
    beside the call with its reason. A line here says instead that somebody is going to look.
    """
    if not BASELINE.exists():
        return
    text = BASELINE.read_text(encoding="utf-8")
    unowned = []
    for line in text.splitlines():
        entry = line.strip()
        if not entry or entry.startswith("#"):
            continue
        preceding = text.split(line)[0]
        block = preceding.rsplit("\n\n", 1)[-1]
        if not re.search(r"\bM\d+-W\d+\b", block):
            unowned.append(entry)
    assert not unowned, (
        "these baseline entries name no retiring task in the comment block above them:\n  "
        + "\n  ".join(unowned)
    )
