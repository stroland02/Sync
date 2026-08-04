"""Whether every decode handler in `src/` has ever been entered.

Four defects in one day were the same defect: a text read whose undecodable-bytes path either
crashed at adapter selection or, worse, answered a confident wrong number. The tool anyone
would reach for to find the fifth reports them as already tested.

`_read_npm` catches `JSONDecodeError` and `UnicodeDecodeError` on one line. A fixture entering
the JSON arm marks that line covered, so line coverage calls the decode arm tested when it has
never run. Measured on a two-function module: a co-caught handler entered only by
`JSONDecodeError` reports 100% covered, and `coverage --branch` finds zero branches in an
except chain -- an except chain is not a branch to coverage.py, so no coverage configuration
answers this question.

Splitting each co-caught clause in two does answer it. As two clauses the arms occupy two
lines and the unentered one reports as missing, measured the same way. It was rejected for
what it produces rather than for whether it works: a number inside a report nothing fails on,
bought with an edit at eight sites in `src/` -- several of which would have to duplicate a
handler body to be split -- and a convention every future handler's author has to remember.

What runs instead attributes by exception type rather than by line. `sys.monitoring`'s
`EXCEPTION_HANDLED` event carries the exception instance that was handled, so a handler
entered by a `JSONDecodeError` and the same handler entered by a `UnicodeDecodeError` are
told apart at one line. The inventory is read out of `src/` by AST rather than declared here,
so a decode handler added tomorrow is in scope without anyone remembering to list it, and one
no driver below reaches fails this file by name.

The drivers construct undecodable bytes in code rather than committing a fixture. Git decides
text from binary by heuristic and `CLAUDE.md` rules out a `.gitattributes` to overrule it, so
a committed non-UTF-8 file is one that anything round-tripping it as text silently repairs --
after which the test passes against a valid file while appearing to cover the handler.
`.encode("utf-16")` writes the byte-order mark, so these bytes begin `ff fe` exactly as the
repository that found this defect does.

`DRIVERS` is keyed by file, enclosing scope and caught exception names, none of which an edit
above a handler moves. Adding a comment to a module in `src/` leaves every key here alone. The
keys were positional until B63 and the cost of that was measured rather than argued: seven
re-anchored when one change added comment blocks above them, three more inside a single commit,
one twice within an hour, and not one of them a defect in `src/`. A check that fails for a
change that touched no behaviour is a check somebody eventually silences.

Both failures this file exists to produce survive the change. A handler no driver reaches still
fails by name, and a driver whose handler is gone still fails by key -- a renamed scope reads as
a handler that moved, which is a question worth answering rather than a position to bump.

What the positional key bought was uniqueness, and that is what this scheme has to earn: two
chains in one scope catching the same exceptions cannot be told apart by key, and one driver's
entry would then vouch for the other's handler. There is no such pair in `src/` -- eighteen
handlers, eighteen keys -- and `test_no_two_decode_handlers_share_a_key` refuses the day
somebody writes one, naming both positions.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import CodeType
from typing import Callable, Iterator

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"

UTF16 = "stripe==11.0.0\n".encode("utf-16")


@dataclass(frozen=True)
class DecodeHandler:
    """A `try` in `src/` whose handler chain can catch `UnicodeDecodeError`.

    The chain is the unit rather than the clause. `EXCEPTION_HANDLED` fires on the instruction
    that opens the chain, which belongs to the first clause whichever clause matched, so no
    clause can be told from its siblings by position. `first_line` and `last_line` span the
    whole chain for that reason; `clause_line` is the line a reader would look at and what a
    failure prints, and it is deliberately no part of `key`.
    """

    path: str
    scope: str
    clause_line: int
    first_line: int
    last_line: int
    caught: tuple[str, ...]

    @property
    def key(self) -> str:
        # Sorted, because the order a clause lists its exceptions in changes nothing about what
        # the chain catches, and a key that moved when somebody reordered them would be
        # positional again in a second spelling.
        return f"{self.path}::{self.scope}::{'+'.join(sorted(self.caught))}"

    @property
    def position(self) -> str:
        return f"{self.path}:{self.clause_line}"


def _caught_names(node: ast.expr | None) -> tuple[str, ...]:
    """The exception names a clause lists, however it spells them.

    A bare `except:` names nothing and is not a decode handler by this reading. It would catch
    a `UnicodeDecodeError`, but nothing in `src/` writes one and a rule that treated every bare
    handler as a decode handler would demand a driver for each.
    """
    if node is None:
        return ()
    parts = node.elts if isinstance(node, ast.Tuple) else [node]
    names = []
    for part in parts:
        if isinstance(part, ast.Name):
            names.append(part.id)
        elif isinstance(part, ast.Attribute):
            names.append(part.attr)
    return tuple(names)


def _scopes(tree: ast.Module) -> dict[int, str]:
    """The dotted `def`/`class` trail enclosing every node, keyed by `id`.

    Descended rather than read off a parent pointer, which `ast` nodes do not carry. The ids are
    only valid while the caller still holds the tree they came from.
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


def colliding_keys(inventory: list[DecodeHandler]) -> dict[str, list[str]]:
    """Keys naming more than one handler, each with the positions that share it."""
    found: dict[str, list[DecodeHandler]] = {}
    for handler in inventory:
        found.setdefault(handler.key, []).append(handler)
    return {
        key: [handler.position for handler in sorted(handlers, key=lambda h: h.clause_line)]
        for key, handlers in found.items()
        if len(handlers) > 1
    }


def decode_handlers(src: Path = SRC) -> list[DecodeHandler]:
    """Every decode handler in the tree, read from the source rather than declared."""
    found: list[DecodeHandler] = []
    for file_path in sorted(src.rglob("*.py")):
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
        relative = file_path.relative_to(src).as_posix()
        scopes = _scopes(tree)
        for node in ast.walk(tree):
            # `ast.Try` covers `try/finally`, which has no clauses at all.
            if not isinstance(node, ast.Try) or not node.handlers:
                continue
            decoding = [
                (handler, _caught_names(handler.type))
                for handler in node.handlers
                if "UnicodeDecodeError" in _caught_names(handler.type)
            ]
            if not decoding:
                continue
            first = node.handlers[0].lineno
            last = max(handler.end_lineno or handler.lineno for handler in node.handlers)
            for handler, caught in decoding:
                found.append(
                    DecodeHandler(relative, scopes[id(node)], handler.lineno, first, last, caught)
                )
    return found


_EXCEPTION_HANDLED = sys.monitoring.events.EXCEPTION_HANDLED


def _free_tool_id() -> int:
    """A monitoring slot nothing else holds.

    Claimed rather than fixed, because coverage.py takes one of the six when it runs on the
    `sysmon` core and a collision raises rather than degrading.
    """
    for tool_id in range(6):
        if sys.monitoring.get_tool(tool_id) is None:
            return tool_id
    raise RuntimeError("every sys.monitoring tool id is in use")


def _handled_at(code: CodeType, offset: int) -> int | None:
    """The source line control transferred to.

    The instruction `EXCEPTION_HANDLED` reports opens the handler block and carries no line of
    its own, so the anchor is the first instruction at or after it that does.
    """
    following: tuple[int, int] | None = None
    for start, _end, line in code.co_lines():
        if line is None:
            continue
        if start <= offset < _end:
            return line
        if start >= offset and (following is None or start < following[0]):
            following = (start, line)
    return following[1] if following else None


@contextmanager
def watching_decode_handlers() -> Iterator[set[tuple[str, int]]]:
    """Every `(file, line)` where a `UnicodeDecodeError` was handled while this is open."""
    entered: set[tuple[str, int]] = set()
    tool_id = _free_tool_id()

    def record(code: CodeType, offset: int, exc: BaseException) -> None:
        if isinstance(exc, UnicodeDecodeError):
            line = _handled_at(code, offset)
            if line is not None:
                entered.add((code.co_filename, line))

    sys.monitoring.use_tool_id(tool_id, "sync-decode-handlers")
    try:
        sys.monitoring.register_callback(tool_id, _EXCEPTION_HANDLED, record)
        sys.monitoring.set_events(tool_id, _EXCEPTION_HANDLED)
        yield entered
    finally:
        sys.monitoring.set_events(tool_id, 0)
        sys.monitoring.register_callback(tool_id, _EXCEPTION_HANDLED, None)
        sys.monitoring.free_tool_id(tool_id)


def keys_entered(
    observed: set[tuple[str, int]], inventory: list[DecodeHandler]
) -> set[str]:
    """The inventory keys the observations account for."""
    entered: set[str] = set()
    for filename, line in observed:
        observed_path = Path(filename).resolve()
        for handler in inventory:
            if observed_path != (SRC / handler.path).resolve():
                continue
            if handler.first_line <= line <= handler.last_line:
                entered.add(handler.key)
    return entered


# --- the drivers ------------------------------------------------------------------
#
# One per handler, each reaching it through the shallowest entry point a caller uses, and each
# asserting what the handler answers -- entering it is the question this file asks, but a
# handler that is entered and then reports the wrong thing is the defect that started this.

SPEC = {"paths": {"/v1/charges": {"post": {"operationId": "PostCharges"}}}}

PROPERTY_REMOVED = dict(
    vendor_id="stripe",
    from_version="v2300",
    to_version="v2345",
    kind="request-property-removed",
    operation_id="PostPaymentIntents",
    path_ptr="/v1/payment_intents",
    severity="breaking",
    source="oasdiff",
    raw={
        "id": "request-property-removed",
        "text": "removed the request property `receipt_email`",
    },
)


def _python_adapter(root: Path):
    from sync.index.python_lang import PythonAdapter
    from sync.signals.stripe.adapter import StripeAdapter
    from sync.signals.stripe.symbols import build_symbol_map

    map_path = root / "map.json"
    map_path.write_text(json.dumps(build_symbol_map(SPEC)), encoding="utf-8")
    vendor = StripeAdapter(
        spec_dir=Path(__file__).parent / "fixtures" / "specs", symbol_map_path=map_path
    )
    return PythonAdapter(vendor_adapter=vendor)


def _repo(root: Path):
    from sync.core import RepoRef

    return RepoRef(
        repo_id="decode", url="https://example.invalid/decode",
        local_path=str(root), head_sha="0" * 40,
    )


def _ts_site(path: str = "src/charge.ts"):
    from sync.core import CallSite

    return CallSite(
        id="cs-1", repo_id="decode", path=path, line=1, col=0, vendor_id="stripe",
        operation_id="PostPaymentIntents", symbol="stripe.paymentIntents.create",
        args_keys=["amount", "receipt_email"], sdk_version="22.4.0", content_hash="h",
    )


def _finding():
    from sync.core import Finding

    return Finding(
        detector="decode", claim="parameter:receipt_email", call_site_id="cs-1",
        severity="breaking", rationale="r",
    )


def _undecodable_ts(root: Path, path: str = "src/charge.ts") -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(UTF16)


def _drive_checkout(root: Path) -> None:
    from sync.benchmark.checkout import read_checkout

    (root / "billing.ts").write_bytes(UTF16)
    sources, skipped = read_checkout(root)
    assert sources == {} and skipped == ["billing.ts"]


def _drive_webhook(_: Path) -> None:
    from sync.forge.webhook import WebhookFormatError, parse_pull_request_event

    with pytest.raises(WebhookFormatError):
        parse_pull_request_event(UTF16)


def _drive_feed(_: Path) -> None:
    from sync.signals.feed.consumer import FeedFormatError, parse_feed

    with pytest.raises(FeedFormatError):
        parse_feed(UTF16)


def _drive_requirement_lines_pyproject(root: Path) -> None:
    (root / "pyproject.toml").write_bytes(UTF16)
    assert _python_adapter(root).matches(_repo(root)) is False


def _drive_requirement_lines_requirements(root: Path) -> None:
    (root / "requirements.txt").write_bytes(UTF16)
    # The UTF-16 bytes spell `stripe==11.0.0`, so a reader that decoded them leniently would
    # answer True here. The handler's answer is that the manifest declares nothing.
    assert _python_adapter(root).matches(_repo(root)) is False


def _drive_configured_typechecker(root: Path) -> None:
    from sync.core import Patch

    (root / "pyproject.toml").write_bytes(UTF16)
    result = _python_adapter(root).static_verify(
        _repo(root), Patch(diff="", strategy="codemod", rationale="r")
    )
    assert result.ok is False


def _drive_literal_swap(root: Path) -> None:
    from sync.core import VendorChange
    from sync.remediate.literal_swap import LiteralSwapRemediator

    _undecodable_ts(root)
    patch = LiteralSwapRemediator().propose(
        _finding(), VendorChange(**PROPERTY_REMOVED), _ts_site(), _repo(root)
    )
    assert patch.diff == ""


def _drive_parameters(root: Path) -> None:
    from sync.core import VendorChange
    from sync.remediate.parameters import ParameterOmitRemediator

    _undecodable_ts(root)
    patch = ParameterOmitRemediator().propose(
        _finding(), VendorChange(**PROPERTY_REMOVED), _ts_site(), _repo(root)
    )
    assert patch.diff == ""


def _drive_property_omit(root: Path) -> None:
    from sync.core import VendorChange
    from sync.remediate.property_omit import CannotPatch, PropertyOmitRemediator

    _undecodable_ts(root)
    with pytest.raises(CannotPatch, match="UnicodeDecodeError"):
        PropertyOmitRemediator().propose(
            _finding(), VendorChange(**PROPERTY_REMOVED), _ts_site(), _repo(root)
        )


def _drive_tiered_literal(root: Path) -> None:
    from sync.core import VendorChange
    from sync.remediate.tiered import routing_facts

    _undecodable_ts(root)
    facts = routing_facts(VendorChange(**PROPERTY_REMOVED), _ts_site(), _repo(root))
    # `None` rather than `False`: unreadable bytes are not evidence the argument was written
    # as a literal, and absent evidence must never read as permission.
    assert facts.field_passed_as_literal is None


def _drive_intake_npm(root: Path) -> None:
    from sync.signals.intake import read_declared_dependencies

    (root / "package.json").write_bytes(UTF16)
    declared, unreadable = read_declared_dependencies(root)
    assert declared == () and any("package.json" in item for item in unreadable)


def _drive_intake_pyproject(root: Path) -> None:
    from sync.signals.intake import read_declared_dependencies

    (root / "pyproject.toml").write_bytes(UTF16)
    declared, unreadable = read_declared_dependencies(root)
    assert declared == () and any("pyproject.toml" in item for item in unreadable)


def _drive_intake_requirements(root: Path) -> None:
    from sync.signals.intake import read_declared_dependencies

    (root / "requirements.txt").write_bytes(UTF16)
    declared, unreadable = read_declared_dependencies(root)
    assert declared == () and any("requirements.txt" in item for item in unreadable)


def _drive_literal_call_sites(root: Path) -> None:
    """A customer `.ts` file that is not UTF-8, which this stage skips and names.

    It read the same bytes with `errors="replace"` until B57. `operation_id` is the literal's
    value and the key a retirement joins on, so a mangled one is a call site against a model
    nothing retires -- and `.ts` is MPEG transport stream too, so a video in the tree parsed into
    a phantom call site.
    """
    from sync.cli import _literal_call_sites

    (root / "models.ts").write_bytes(UTF16)
    assert _literal_call_sites(_repo(root))[0] == []


def _tracker_cache(root: Path) -> Path:
    """A cache holding the symbol map both error-tracker commands refuse to run without."""
    from sync.signals.registry import SYMBOL_MAP_FILENAME
    from sync.signals.stripe.symbols import build_symbol_map

    cache = root / "cache"
    cache.mkdir(exist_ok=True)
    (cache / SYMBOL_MAP_FILENAME).write_text(
        json.dumps(build_symbol_map(SPEC)), encoding="utf-8"
    )
    return cache


def _drive_shapes_payload(root: Path) -> None:
    """A captured response in an encoding this does not read.

    What an operator receives from this command is a count of rows, so an unreadable payload
    reported as zero of them reads as a vendor that sent nothing. The handler answers with exit 2
    before any store is opened, which is why the DSN below is never used.
    """
    from sync.cli import shapes

    payload = root / "event.json"
    payload.write_bytes(UTF16)

    assert shapes(argparse.Namespace(
        vendor="stripe", format="sentry", payload=str(payload),
        dsn="postgresql://unused", cache=str(_tracker_cache(root)),
    )) == 2


def _drive_sentry_errors_payload(root: Path) -> None:
    """The same bytes on the count half, where the misreading is worse.

    Zero rows from this command is a window in which the vendor's operations did not fail, and
    an export nobody could decode reported that way is a quiet week that never happened.
    """
    from sync.cli import sentry_errors

    payload = root / "issues.json"
    payload.write_bytes(UTF16)

    assert sentry_errors(argparse.Namespace(
        vendor="stripe", repo_id="decode", payload=str(payload),
        since="2026-07-20T14:00:00+00:00", until="2026-07-20T15:00:00+00:00",
        dsn="postgresql://unused", cache=str(_tracker_cache(root)),
    )) == 2


def _drive_git_diff(root: Path) -> None:
    """A clone whose tracked source file is not UTF-8, which the patch path refuses.

    The one child in `src/` that genuinely hands back bytes that are not UTF-8: `git diff`
    copies file content onto the pipe verbatim. Read with `text=True, encoding="utf-8"` the
    decode happened on `subprocess`'s reader thread, where the `UnicodeDecodeError` is
    swallowed and `stdout` comes back `None`. This handler is what turns that into a refusal
    naming the file, so the driver has to reach it through real git rather than a stub.

    cp1252 rather than the UTF-16 the other drivers use: this is a source file somebody edits
    in a legacy encoding, and the byte git copies onto the pipe is a lone 0xe9.
    """
    import os
    import subprocess

    from sync.remediate.agent_patch import _git_diff

    def git(*args: str) -> None:
        subprocess.run(
            ["git", *args], cwd=root, capture_output=True, check=True,
            env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull},
        )

    git("init")
    (root / "billing.ts").write_bytes(b"export const legacy = 1;\n")
    git("add", "billing.ts")
    git("-c", "user.name=Seed", "-c", "user.email=seed@example.com", "commit", "-m", "seed")
    (root / "billing.ts").write_bytes(b'export const caf\xe9 = "montr\xe9al";\n')

    with pytest.raises(RuntimeError, match="billing.ts"):
        _git_diff(root, "finding=f-1 repo=r1")


def _drive_ts_manifest(root: Path) -> None:
    from sync.index.typescript import TypeScriptAdapter
    from sync.signals.stripe.adapter import StripeAdapter
    from sync.signals.stripe.symbols import build_symbol_map

    map_path = root / "map.json"
    map_path.write_text(json.dumps(build_symbol_map(SPEC)), encoding="utf-8")
    vendor = StripeAdapter(
        spec_dir=Path(__file__).parent / "fixtures" / "specs", symbol_map_path=map_path
    )
    adapter = TypeScriptAdapter(vendor_adapter=vendor)
    manifest = root / "package.json"

    # A real package.json in the wrong encoding, rather than arbitrary undecodable bytes: this
    # handler's whole job is to answer "no declared dependency" for a manifest it cannot read,
    # and a file that would parse once decoded is the case that distinguishes the decode arm
    # from the JSONDecodeError arm beside it.
    manifest.write_bytes(json.dumps({"dependencies": {"stripe": "^14.0.0"}}).encode("utf-16"))
    assert adapter.matches(_repo(root)) is False

    # Without this the assertion above passes whenever `matches` short-circuits before reading
    # anything, which is how a driver ends up naming a handler it never enters.
    manifest.write_text(json.dumps({"dependencies": {"stripe": "^14.0.0"}}), encoding="utf-8")
    assert adapter.matches(_repo(root)) is True


def _drive_python_sources(root: Path) -> None:
    """The indexer's own gate: a module it cannot decode contributes no call sites."""
    (root / "requirements.txt").write_text("stripe==11.0.0\n", encoding="utf-8")
    (root / "billing.py").write_bytes(
        "import stripe\n\n\ndef charge():\n    # café\n    return stripe.charges.create(amount=100, currency='eur')\n"
        .encode("cp1252")
    )
    adapter = _python_adapter(root)
    assert list(adapter.index(_repo(root))) == []

    # The control, and it is the half that matters: without it this driver passes for a repository
    # the adapter never indexed at all, which is exactly the reading it exists to rule out.
    (root / "billing.py").write_text(
        "import stripe\n\n\ndef charge():\n    return stripe.charges.create(amount=100, currency='eur')\n",
        encoding="utf-8",
    )
    assert [site.operation_id for site in adapter.index(_repo(root))] == ["PostCharges"]


def _drive_typescript_sources(root: Path) -> None:
    """The same gate on the other language, reached the same way."""
    from sync.index.typescript import TypeScriptAdapter
    from sync.signals.stripe.adapter import StripeAdapter
    from sync.signals.stripe.symbols import build_symbol_map

    map_path = root / "map.json"
    map_path.write_text(json.dumps(build_symbol_map(SPEC)), encoding="utf-8")
    adapter = TypeScriptAdapter(vendor_adapter=StripeAdapter(
        spec_dir=Path(__file__).parent / "fixtures" / "specs", symbol_map_path=map_path
    ))
    (root / "package.json").write_text(
        json.dumps({"dependencies": {"stripe": "^14.0.0"}}), encoding="utf-8"
    )
    source = root / "src"
    source.mkdir(exist_ok=True)
    ts = ("import Stripe from 'stripe';\n"
          "const stripe = new Stripe(process.env.KEY!);\n"
          "export const go = () => stripe.charges.create({ amount: 1 });\n")

    (source / "billing.ts").write_bytes(("// café\n" + ts).encode("cp1252"))
    assert list(adapter.index(_repo(root))) == []

    (source / "billing.ts").write_text(ts, encoding="utf-8")
    assert [site.operation_id for site in adapter.index(_repo(root))] == ["PostCharges"]


DRIVERS: dict[str, Callable[[Path], None]] = {
    "sync/benchmark/checkout.py::read_checkout::UnicodeDecodeError": _drive_checkout,
    "sync/index/python_lang.py::PythonAdapter._readable_sources::UnicodeDecodeError":
        _drive_python_sources,
    "sync/index/typescript.py::TypeScriptAdapter._readable_sources::UnicodeDecodeError":
        _drive_typescript_sources,
    "sync/forge/webhook.py::parse_pull_request_event::JSONDecodeError+UnicodeDecodeError":
        _drive_webhook,
    "sync/index/python_lang.py::PythonAdapter._read_manifests::TOMLDecodeError+UnicodeDecodeError":
        _drive_requirement_lines_pyproject,
    "sync/index/python_lang.py::PythonAdapter._read_manifests::UnicodeDecodeError":
        _drive_requirement_lines_requirements,
    "sync/index/python_lang.py::PythonAdapter._configured_typechecker::"
    "TOMLDecodeError+UnicodeDecodeError": _drive_configured_typechecker,
    "sync/cli.py::_literal_call_sites::UnicodeDecodeError": _drive_literal_call_sites,
    "sync/cli.py::shapes::JSONDecodeError+OSError+UnicodeDecodeError": _drive_shapes_payload,
    "sync/cli.py::sentry_errors::JSONDecodeError+OSError+UnicodeDecodeError":
        _drive_sentry_errors_payload,
    "sync/index/typescript.py::TypeScriptAdapter._read_manifest::"
    "JSONDecodeError+UnicodeDecodeError": _drive_ts_manifest,
    "sync/remediate/agent_patch.py::_git_diff::UnicodeDecodeError": _drive_git_diff,
    "sync/remediate/literal_swap.py::LiteralSwapRemediator.propose::OSError+UnicodeDecodeError":
        _drive_literal_swap,
    "sync/remediate/parameters.py::_ParameterRemediator.propose::OSError+UnicodeDecodeError":
        _drive_parameters,
    "sync/remediate/property_omit.py::PropertyOmitRemediator.propose::OSError+UnicodeDecodeError":
        _drive_property_omit,
    "sync/remediate/tiered.py::_passed_as_literal::OSError+UnicodeDecodeError":
        _drive_tiered_literal,
    "sync/signals/feed/consumer.py::parse_feed::JSONDecodeError+UnicodeDecodeError": _drive_feed,
    "sync/signals/intake.py::_read_npm::JSONDecodeError+UnicodeDecodeError": _drive_intake_npm,
    "sync/signals/intake.py::_read_pypi::TOMLDecodeError+UnicodeDecodeError":
        _drive_intake_pyproject,
    "sync/signals/intake.py::_read_pypi::UnicodeDecodeError": _drive_intake_requirements,
}


# --- the checks -------------------------------------------------------------------


@pytest.mark.parametrize("key", sorted(DRIVERS))
def test_driver_enters_the_handler_it_names(key: str, tmp_path: Path) -> None:
    """Each driver reaches the handler it is filed under, and no other proves it for it."""
    inventory = decode_handlers()
    with watching_decode_handlers() as observed:
        DRIVERS[key](tmp_path)

    entered = keys_entered(observed, inventory)
    assert key in entered, (
        f"{key} was not entered with a UnicodeDecodeError by its own driver; "
        f"the run entered {sorted(entered) or 'no handler at all'}"
    )


def test_every_decode_handler_has_been_entered(tmp_path: Path) -> None:
    inventory = decode_handlers()
    with watching_decode_handlers() as observed:
        # Numbered rather than named after the key. A scope key is long enough that one under a
        # pytest temporary directory reaches the Windows path limit inside the drivers that build
        # a git clone, and the number is only ever a directory nobody reads.
        for index, drive in enumerate(DRIVERS.values()):
            root = tmp_path / f"{index:02d}"
            root.mkdir(parents=True)
            drive(root)

    missing = sorted({handler.key for handler in inventory} - keys_entered(observed, inventory))
    assert not missing, (
        "no test has ever entered these decode handlers, so nothing is known about what "
        "they do with undecodable bytes:\n  " + "\n  ".join(missing)
    )


def test_no_driver_names_a_handler_that_is_gone() -> None:
    """A driver outliving its handler would keep proving something that no longer exists."""
    stale = sorted(set(DRIVERS) - {handler.key for handler in decode_handlers()})
    assert not stale, "these drivers name a handler that is no longer in src/:\n  " + "\n  ".join(stale)


def test_handler_spans_do_not_overlap() -> None:
    """Two chains sharing a span would let one driver's entry vouch for the other's handler."""
    by_file: dict[str, list[DecodeHandler]] = {}
    for handler in decode_handlers():
        by_file.setdefault(handler.path, []).append(handler)
    for path, handlers in by_file.items():
        spans = sorted({(h.first_line, h.last_line) for h in handlers})
        for (_, earlier_end), (later_start, _) in zip(spans, spans[1:]):
            assert later_start > earlier_end, f"{path}: two handler chains overlap"


def _inventory_over(root: Path, source: str) -> list[DecodeHandler]:
    """The inventory read out of a one-module tree this test wrote."""
    root.mkdir(parents=True)
    (root / "reader.py").write_text(source, encoding="utf-8")
    return decode_handlers(root)


_ONE_HANDLER = '''
def read(path):
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None
'''

_TWO_HANDLERS_IN_ONE_SCOPE = '''
def read(first, second):
    try:
        return first.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        pass
    try:
        return second.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        pass
'''


def test_a_key_survives_an_unrelated_edit_above_its_handler(tmp_path: Path) -> None:
    """The failure mode this keying scheme exists to remove.

    A comment added above a handler moves every line below it. Under a positional key that
    invalidates the driver registered for it, and the file then fails by position over a
    handler whose behaviour nobody touched.
    """
    before = _inventory_over(tmp_path / "before", _ONE_HANDLER)
    after = _inventory_over(
        tmp_path / "after", "# an edit this file has no business having an opinion about\n" * 3
        + _ONE_HANDLER
    )

    assert [handler.clause_line for handler in before] != [
        handler.clause_line for handler in after
    ]
    assert [handler.key for handler in before] == [handler.key for handler in after]


def test_two_handlers_the_key_cannot_tell_apart_are_refused_naming_both(tmp_path: Path) -> None:
    """The cost of a non-positional key, refused loudly rather than absorbed.

    Two chains in one scope catching the same exceptions share a key, and one driver's entry
    would then vouch for both. There is no such pair in `src/`; this is what happens on the day
    somebody writes one.
    """
    collisions = colliding_keys(_inventory_over(tmp_path / "collide", _TWO_HANDLERS_IN_ONE_SCOPE))

    assert list(collisions) == ["reader.py::read::UnicodeDecodeError"]
    assert collisions["reader.py::read::UnicodeDecodeError"] == ["reader.py:5", "reader.py:9"]


def test_no_two_decode_handlers_share_a_key() -> None:
    """What the check above proves is detectable, asserted over `src/`."""
    collisions = colliding_keys(decode_handlers())

    assert not collisions, "these handlers cannot be told apart by key:\n  " + "\n  ".join(
        f"{key} at {', '.join(positions)}" for key, positions in collisions.items()
    )


def test_the_check_reports_a_handler_only_a_sibling_arm_entered() -> None:
    """The property line coverage does not have, held here so it cannot quietly regress.

    Both calls enter the same co-caught chain and line coverage cannot tell them apart -- the
    first marks the line executed and the decode arm reports as tested. Attribution by
    exception type reports it as never entered, which is what this whole file rests on.
    """


    def co_caught(payload: bytes) -> str:
        try:
            json.loads(payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            return type(exc).__name__
        return "ok"

    with watching_decode_handlers() as observed:
        assert co_caught(b"{ not json") == "JSONDecodeError"
    assert observed == set()

    with watching_decode_handlers() as observed:
        assert co_caught(UTF16) == "UnicodeDecodeError"
    assert {line for _, line in observed} != set()
