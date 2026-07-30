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
"""

from __future__ import annotations

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
    whole chain for that reason; `clause_line` is the line a reader would look at, and is what
    a driver names.
    """

    path: str
    clause_line: int
    first_line: int
    last_line: int
    caught: tuple[str, ...]

    @property
    def key(self) -> str:
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


def decode_handlers(src: Path = SRC) -> list[DecodeHandler]:
    """Every decode handler in the tree, read from the source rather than declared."""
    found: list[DecodeHandler] = []
    for file_path in sorted(src.rglob("*.py")):
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
        relative = file_path.relative_to(src).as_posix()
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
                found.append(DecodeHandler(relative, handler.lineno, first, last, caught))
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


def _drive_syntax_errors(root: Path) -> None:
    from sync.core import Patch

    (root / "billing.py").write_bytes(UTF16)
    result = _python_adapter(root).static_verify(
        _repo(root), Patch(diff="", strategy="codemod", rationale="r")
    )
    assert result.ok is False and "billing.py" in result.diagnostics


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


DRIVERS: dict[str, Callable[[Path], None]] = {
    "sync/benchmark/checkout.py:81": _drive_checkout,
    "sync/forge/webhook.py:97": _drive_webhook,
    "sync/index/python_lang.py:219": _drive_requirement_lines_pyproject,
    "sync/index/python_lang.py:231": _drive_requirement_lines_requirements,
    "sync/index/python_lang.py:704": _drive_syntax_errors,
    "sync/index/python_lang.py:715": _drive_configured_typechecker,
    "sync/index/typescript.py:201": _drive_ts_manifest,
    "sync/remediate/literal_swap.py:84": _drive_literal_swap,
    "sync/remediate/parameters.py:77": _drive_parameters,
    "sync/remediate/property_omit.py:93": _drive_property_omit,
    "sync/remediate/tiered.py:174": _drive_tiered_literal,
    "sync/signals/feed/consumer.py:72": _drive_feed,
    "sync/signals/intake.py:282": _drive_intake_npm,
    "sync/signals/intake.py:318": _drive_intake_pyproject,
    "sync/signals/intake.py:329": _drive_intake_requirements,
}


# --- the checks -------------------------------------------------------------------


@pytest.mark.parametrize("key", sorted(DRIVERS))
def test_driver_enters_the_handler_it_names(key: str, tmp_path: Path) -> None:
    """Each driver reaches the handler it is filed under, and no other proves it for it."""
    inventory = decode_handlers()
    with watching_decode_handlers() as observed:
        DRIVERS[key](tmp_path)

    assert key in keys_entered(observed, inventory), (
        f"{key} was not entered with a UnicodeDecodeError by its own driver"
    )


def test_every_decode_handler_has_been_entered(tmp_path: Path) -> None:
    inventory = decode_handlers()
    with watching_decode_handlers() as observed:
        for key, drive in DRIVERS.items():
            root = tmp_path / key.replace("/", "_").replace(":", "_")
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
