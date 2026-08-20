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
entry would then vouch for the other's handler. There is no such pair in `src/` -- as many
distinct keys as there are handlers -- and `test_no_two_decode_handlers_share_a_key` refuses
the day somebody writes one, naming both positions.

What none of this can see is a chain that catches a `UnicodeDecodeError` without naming one.
The inventory reads exception *names*, and `UnicodeDecodeError` is a `ValueError`, so
`except ValueError` catches a decode failure while being neither counted nor required to have
a driver.

**Two clauses in `src/` guard a read that way**, and both say so where they sit. `benchmark`'s
chain around `_score_corpus` is one; the specification's own read is guarded inside
`_score_corpus` where this file can see it, but a decode failure raised anywhere else under that
call lands in a handler nothing here knows about. `PythonAdapter._syntax_errors` is the other,
over `ast.parse` on a customer source file, and its own comment states the subsumption as the
reason it needs no clause of its own. Probed on UTF-16, on cp1252 in an identifier, a string and
a comment, and on a mis-declared coding line, `ast.parse` answers `SyntaxError` every time, so
that arm may be unreachable in practice -- but an instance that cannot fire is still an instance
this survey has to account for, and the earlier version of this paragraph claimed one instance
while the second sat in the tree.

Following the hierarchy instead was measured and declined, for what it would demand rather than
for its size. It would surface forty-three clauses. Thirteen sit over `int()`,
`datetime.fromisoformat`, a graph lookup by id, a PEM parse or a signature check -- nothing that
decodes -- so each would enter the inventory owing a driver that cannot be written, and a rule
whose obligation is unsatisfiable is a rule somebody eventually silences.

**The other twenty-eight are the real argument, and they are the majority rather than the
exception.** They are `except Exception` around a whole stage, where the contract is that no
failure of any kind escapes. A decode failure genuinely reaches several of them --
`static_verify` over a repository whose `pyproject.toml` is UTF-16 is a path
`_drive_configured_typechecker` already builds -- so a driver for one would pass. Passing would
say nothing. It would prove the catch-all catches, not that anything decided what undecodable
bytes mean; that decision is made inside the stage, at the read, by a handler this file already
sees.

`SUBSUMING` below names all forty-three, grouped by which of those three conclusions applies,
and two checks hold it: one fails when a clause appears that the census does not account for,
the other when an entry describes nothing. That is what the earlier version of this file lacked
-- it stated the limitation in prose and left nothing reading `src/`, which is how the second
guarded read went unseen. A count in prose is a second copy of something computed on every run,
and this file's own count went stale twice before anyone noticed.
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


SUBSUMING_BASES = frozenset({"UnicodeError", "ValueError", "Exception", "BaseException"})


def subsuming_handlers(src: Path = SRC) -> list[DecodeHandler]:
    """Every clause in the tree that catches a `UnicodeDecodeError` without naming one.

    The clause is the unit here where the chain is the unit above, because a chain may hold
    both and order decides which one a decode failure reaches. A clause naming
    `UnicodeDecodeError` ends the walk over its chain: every clause after it is unreachable for
    a decode failure, and every clause before it shadows it.
    """
    found: list[DecodeHandler] = []
    for file_path in sorted(src.rglob("*.py")):
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
        relative = file_path.relative_to(src).as_posix()
        scopes = _scopes(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Try) or not node.handlers:
                continue
            first = node.handlers[0].lineno
            last = max(handler.end_lineno or handler.lineno for handler in node.handlers)
            for handler in node.handlers:
                caught = _caught_names(handler.type)
                if "UnicodeDecodeError" in caught:
                    break
                if SUBSUMING_BASES.isdisjoint(caught):
                    continue
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


def _drive_webhook_review(_: Path) -> None:
    from sync.forge.webhook import WebhookFormatError, parse_review_event

    with pytest.raises(WebhookFormatError):
        parse_review_event(UTF16)


def _drive_webhook_review_comment(_: Path) -> None:
    from sync.forge.webhook import WebhookFormatError, parse_review_comment_event

    with pytest.raises(WebhookFormatError):
        parse_review_comment_event(UTF16)


def _drive_webhook_check_run(_: Path) -> None:
    from sync.forge.webhook import WebhookFormatError, parse_check_run_event

    with pytest.raises(WebhookFormatError):
        parse_check_run_event(UTF16)



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
    from sync.route.facts import routing_facts

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


def _drive_ingest_payload(root: Path) -> None:
    """The same bytes on the span half, where zero rows is a claim about a customer's traffic.

    An ingest that writes nothing is indistinguishable from a repository that does not call this
    vendor, from every query downstream of `observed_call`. The handler answers with exit 2
    before any store is opened, which is why the DSN below is never used.
    """
    from sync.cli import ingest

    payload = root / "spans.json"
    payload.write_bytes(UTF16)

    assert ingest(argparse.Namespace(
        vendor="stripe", repo_id="decode", payload=str(payload),
        dsn="postgresql://unused", cache=str(_tracker_cache(root)),
    )) == 2


def _drive_merge_outcome_commits(root: Path) -> None:
    """The commit list beside a delivery, in an encoding this does not read.

    `--commits` omitted leaves `human_edits_before_merge` null, so a file that could not be
    decoded must not answer with the same null: the delivery would be recorded and the
    measurement the operator asked for would be missing with nothing saying so. The handler
    answers with exit 2 before any store is opened, which is why the DSN below is never used.

    The secret is a file rather than the environment variable, because a driver that exported
    one would leave it set for every driver after it.
    """
    import secrets

    from sync.cli import merge_outcome

    secret_file = root / "webhook.secret"
    secret_file.write_text(secrets.token_hex(32), encoding="utf-8")
    payload = root / "delivery.json"
    payload.write_bytes(json.dumps({"action": "closed"}).encode("utf-8"))
    commits = root / "commits.json"
    commits.write_bytes(UTF16)

    assert merge_outcome(argparse.Namespace(
        payload=str(payload), signature="sha256=0", secret_file=str(secret_file),
        commits=str(commits), dsn="postgresql://unused",
    )) == 2


def _drive_intake_registry_directory(root: Path) -> None:
    """A public OpenAPI directory document in an encoding this does not read.

    The directory is what promotes a declared dependency from unwatchable to watchable, so a
    document read as holding no entries reports a smaller work queue than the deployment has --
    and this command's report is the one a customer is shown. Nothing is opened before the
    refusal, which is why the DSN below is never used.
    """
    from sync.cli import intake

    directory = root / "directory.json"
    directory.write_bytes(UTF16)

    assert intake(argparse.Namespace(
        repo=str(root), evidence=None, registry_directory=str(directory),
        registry_evidence=None, registry_moved_since=None, rank_by_repo_id=None,
        dsn="postgresql://unused",
    )) == 2


def _drive_score_corpus_spec(root: Path) -> None:
    """A corpus specification in an encoding this does not read.

    Reached through `_score_corpus` rather than through `benchmark`, because the read is the
    first thing it does and the command around it opens two databases before it gets there. The
    assertion is on the type as well as the message: `UnicodeDecodeError` is itself a
    `ValueError`, so a `pytest.raises(ValueError)` alone would pass with no handler present.
    """
    from sync.cli import _score_corpus

    spec = root / "corpus.yaml"
    spec.write_bytes(UTF16)

    with pytest.raises(ValueError, match="could not read") as raised:
        _score_corpus(spec, "postgresql://unused")
    assert type(raised.value) is ValueError
    assert "corpus.yaml" in str(raised.value)


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


def _drive_read_seed(root: Path) -> None:
    """A customer's `.sync/context.md` that is not UTF-8, which reads as no context at all.

    `read_seed` folds absent, empty, whitespace-only, unreadable and non-UTF-8 into one `None`
    -- an optional file's malformed content must never abandon a run -- so this drives the one
    case among those that actually decodes bytes.
    """
    from sync.context import SEED_RELATIVE_PATH, read_seed

    target = root / SEED_RELATIVE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(UTF16)

    assert read_seed(root) is None


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

def _drive_extract_credential(root: Path) -> None:
    import base64
    from sync.api.auth import extract_credential

    # Non-UTF-8 bytes in base64 triggers UnicodeDecodeError
    invalid_utf8 = base64.b64encode(b"user:\xff\xfe").decode("ascii")
    assert extract_credential(f"Basic {invalid_utf8}") is None

    # Malformed base64 triggers binascii.Error
    assert extract_credential("Basic not_valid_base64!!!") is None

    # Control: valid basic auth
    valid_token = base64.b64encode(b"user:secret-pass").decode("ascii")
    assert extract_credential(f"Basic {valid_token}") == "secret-pass"


def _drive_index_codebase(root: Path) -> None:
    from sync.index.codebase import index_codebase

    repo_dir = root / "repo"
    repo_dir.mkdir()
    (repo_dir / "package.json").write_text("{}", encoding="utf-8")
    bad_file = repo_dir / "bad.ts"
    bad_file.write_bytes(b"\xff\xfe\x00\x00")
    report = index_codebase(repo_dir)
    assert "bad.ts" in report.unread_paths


DRIVERS: dict[str, Callable[[Path], None]] = {
    "sync/api/auth.py::extract_credential::Error+UnicodeDecodeError": _drive_extract_credential,
    "sync/index/codebase.py::index_codebase::UnicodeDecodeError": _drive_index_codebase,
    "sync/benchmark/checkout.py::read_checkout::UnicodeDecodeError": _drive_checkout,
    "sync/index/python_lang.py::PythonAdapter._readable_sources::UnicodeDecodeError":
        _drive_python_sources,
    "sync/index/typescript.py::TypeScriptAdapter._readable_sources::UnicodeDecodeError":
        _drive_typescript_sources,
    "sync/forge/webhook.py::parse_check_run_event::JSONDecodeError+UnicodeDecodeError":
        _drive_webhook_check_run,
    "sync/forge/webhook.py::parse_pull_request_event::JSONDecodeError+UnicodeDecodeError":
        _drive_webhook,
    "sync/forge/webhook.py::parse_review_comment_event::JSONDecodeError+UnicodeDecodeError":
        _drive_webhook_review_comment,
    "sync/forge/webhook.py::parse_review_event::JSONDecodeError+UnicodeDecodeError":
        _drive_webhook_review,
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
    "sync/cli.py::ingest::JSONDecodeError+OSError+UnicodeDecodeError": _drive_ingest_payload,
    "sync/cli.py::merge_outcome::JSONDecodeError+OSError+UnicodeDecodeError":
        _drive_merge_outcome_commits,
    "sync/cli.py::intake::JSONDecodeError+OSError+UnicodeDecodeError":
        _drive_intake_registry_directory,
    "sync/context/seed.py::read_seed::OSError+UnicodeDecodeError+ValueError": _drive_read_seed,
    "sync/cli.py::_score_corpus::OSError+UnicodeDecodeError+YAMLError": _drive_score_corpus_spec,
    "sync/index/typescript.py::TypeScriptAdapter._read_manifest::"
    "JSONDecodeError+UnicodeDecodeError": _drive_ts_manifest,
    "sync/remediate/agent_patch.py::_git_diff::UnicodeDecodeError": _drive_git_diff,
    "sync/remediate/literal_swap.py::LiteralSwapRemediator.propose::OSError+UnicodeDecodeError":
        _drive_literal_swap,
    "sync/remediate/parameters.py::_ParameterRemediator.propose::OSError+UnicodeDecodeError":
        _drive_parameters,
    "sync/remediate/property_omit.py::PropertyOmitRemediator.propose::OSError+UnicodeDecodeError":
        _drive_property_omit,
    "sync/route/facts.py::_passed_as_literal::OSError+UnicodeDecodeError":
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


_SUBSUMING_HANDLER = '''
def read(path):
    try:
        return path.read_text(encoding="utf-8")
    except ValueError:
        return None
'''


def test_a_chain_naming_only_a_base_class_is_outside_this_inventory(tmp_path: Path) -> None:
    """What this file cannot answer, asserted rather than described.

    The handler below catches every decode failure that read produces and appears in no
    inventory, so nothing above requires a driver for it and nothing above reports it missing.
    Written as an assertion because a limitation recorded only in prose is one that goes stale
    the first time somebody changes the reading -- and this one is meant to fail on the day
    somebody teaches `_caught_names` the exception hierarchy, which is the day it stops being
    true.
    """
    assert issubclass(UnicodeDecodeError, ValueError)

    assert _inventory_over(tmp_path / "subsuming", _SUBSUMING_HANDLER) == []


# Every clause in `src/` that catches a `UnicodeDecodeError` without naming one, accepted as of
# 2026-08-04. Keyed exactly as `DRIVERS` is, and for the same reason: an edit above a clause must
# not invalidate a decision nobody revisited.
#
# This is a list and never a threshold. A count absorbs both a repair and a new blind spot in
# silence; a named entry has to be deleted by whoever removes the clause. The file only shrinks,
# and adding a line is a decision rather than a formality -- it says somebody looked at what the
# clause guards and concluded a decode failure either cannot reach it or would prove nothing by
# reaching it. The three comments below are the three conclusions available.

# Nothing under the `try` decodes anything, so a `UnicodeDecodeError` cannot arrive: `int()` and
# `datetime.fromisoformat` and `strptime` over a `str`, a graph lookup by id, a PEM parse and a
# signature check over bytes neither of them reads as text, a dataclass built from values
# `json.loads` already decoded, and a `relative_to` over paths. A driver here would have nothing
# to drive, and an obligation that cannot be satisfied is one somebody eventually silences.
_DECODES_NOTHING = (
    "sync/api/app.py::_int_param::ValueError",
    "sync/cli.py::_signing_key::TypeError+ValueError",
    "sync/cli.py::_window_bound::ValueError",
    "sync/mcp/tools.py::GraphSurface._change_for::KeyError+LookupError+ValueError",
    "sync/mcp/tools.py::GraphSurface._site_for::KeyError+LookupError+ValueError",
    # `datetime.fromisoformat` over a value an `isinstance(pr_merged_at, str)` above the `try`
    # has already established is a `str`. Nothing under the clause reads bytes, so a decode
    # failure cannot arrive -- the same shape as `_int_param` and `_window_bound` above.
    "sync/graph/store.py::GraphStore.set_merge_outcome::ValueError",
    # Two clauses in one method, guarding `flush` and `detach` on a wrapper whose buffer has
    # already gone. `ValueError: I/O operation on closed file` is a teardown race, not a decode:
    # this method exists to hand a borrowed buffer back rather than shut it, and it runs from the
    # collector as often as from a call. Nothing is read here at all.
    "sync/obs/log.py::_BorrowedTextIOWrapper.close::ValueError",
    # `shlex` raising on an unbalanced quote in a command string the hook already holds in
    # memory. Nothing is read and nothing is decoded here -- the bytes became a string before
    # the gate ever saw them.
    "sync/remediate/tool_gate.py::_bash_refusal::ValueError",
    # The only clause here that catches `Exception`, and it belongs in this group rather than
    # with the whole-stage catch-alls because nothing is swallowed: with no refusal recorded it
    # re-raises unchanged, so a decode failure out of the SDK still reaches its caller. What it
    # exists for is priority, not suppression -- a refusal the hook took the trouble to record
    # names the run and what was refused, and the SDK's replacement text names neither. Nothing
    # is read or decoded in the clause itself.
    "sync/runner/claude_sdk.py::ClaudeSdkRunner._drive::Exception",
    "sync/graph/store.py::GraphStore.set_merge_outcome::ValueError",
    "sync/runner/outcome_tools.py::OutcomeToolValidator._validate_citations::ValueError",
    "sync/signals/datadog/shapes.py::DatadogShapeReader._seen_at::ValueError",
    "sync/signals/deprecations/catalogue.py::_parse_date::ValueError",
    "sync/signals/feed/consumer.py::parse_feed::TypeError+ValueError",
    "sync/signals/feed/consumer.py::verify_feed::InvalidSignature+ValueError",
    "sync/signals/generated/symbols_speakeasy.py::_specifier_target::ValueError",
    "sync/signals/generated/symbols_typescript.py::_specifier_target::ValueError",
    "sync/signals/sentry/shapes.py::SentryShapeReader._seen_at::ValueError",
    "sync/telemetry/otlp.py::_as_int::ValueError",
)

# `except Exception` around a whole stage, where the contract is that no failure of any kind
# escapes. Several of these a decode failure genuinely can reach -- `static_verify` over a
# repository whose `pyproject.toml` is UTF-16 is a path `_drive_configured_typechecker` already
# builds -- and a driver for one would pass. Passing would say nothing: it would prove the
# catch-all catches, not that anything downstream decided what undecodable bytes mean. That
# decision is made inside the stage, at the read, by a handler this file can already see.
_WHOLE_STAGE_CATCH_ALL = (
    "sync/benchmark/reconcile.py::reconcile_pull_request_outcomes::Exception",
    "sync/cli.py::_decline_line::Exception",
    "sync/cli.py::_model_deprecations::Exception",
    "sync/cli.py::_parameter_deprecations::Exception",
    "sync/cli.py::_scan::Exception",
    # Wraps the whole index pass in `sync index` so a run that dies closes its `index_run`
    # row with a terminal state instead of leaving it open forever. Re-raises immediately
    # and decodes nothing itself; the reads that can meet undecodable bytes are inside
    # `index_codebase`, which names `UnicodeDecodeError` and records the path.
    "sync/cli.py::index_repository::Exception",
    # Wraps the whole index pass so a run that dies closes its `index_run` row with a
    # terminal state instead of leaving it open forever. It re-raises immediately and
    # decodes nothing itself -- the reads that can produce undecodable bytes are inside
    # the adapter and carry their own handlers.
    "sync/cli.py::run::Exception",
    "sync/core/conformance.py::_check_fetch_changes::Exception",
    "sync/core/conformance.py::_check_matches::Exception",
    "sync/core/conformance.py::_check_operation_for_symbol::Exception",
    "sync/core/conformance.py::_check_prepare_is_repeatable::Exception",
    "sync/core/conformance.py::_check_static_verify_refuses_a_doctored_dependency::Exception",
    "sync/core/conformance.py::_correlate::Exception",
    "sync/forge/github.py::GitHubForge.delete_branch::Exception",
    "sync/index/literals.py::index_operation_literals::Exception",
    "sync/index/codebase.py::_load_or_create_vendor_adapter::Exception",
    "sync/index/codebase.py::_resolve_repo_ref::Exception",
    "sync/index/python_lang.py::PythonAdapter._read_manifests::Exception",
    "sync/index/typescript.py::TypeScriptAdapter._read_manifest::Exception",
    "sync/mcp/server.py::_call::Exception",
    "sync/rehearse/driver.py::_scan::Exception",
    "sync/remediate/corpus.py::CorpusRecorder.__call__::Exception",
    "sync/remediate/nodes.py::_observed::Exception",
    "sync/remediate/nodes.py::make_abandon.abandon::Exception",
    "sync/remediate/nodes.py::make_await_ci.await_ci::Exception",
    "sync/remediate/nodes.py::make_external_cause.external_cause::Exception",
    "sync/remediate/nodes.py::make_locate.locate::Exception",
    "sync/remediate/nodes.py::make_open_pr.open_pr::Exception",
    "sync/remediate/nodes.py::make_patch.patch::Exception",
    "sync/remediate/nodes.py::make_prepare.prepare::Exception",
    "sync/remediate/nodes.py::make_push_branch.push_branch::Exception",
    "sync/remediate/nodes.py::make_replay.replay::Exception",
    "sync/remediate/nodes.py::make_static_verify.static_verify::Exception",
    "sync/remediate/tiered.py::TieredRemediator.propose::Exception",
    "sync/signals/deprecations/adapter.py::DeprecationAdapter._page::Exception",
    "sync/signals/generated/adapter.py::GeneratedSpecAdapter._spec::Exception",
    "sync/signals/intake_attempt.py::execute_intake_attempt::Exception",
    "sync/signals/registry.py::_spec_source::Exception",
    # Per row rather than per stage, and the argument is the same one. It wraps a single
    # `forge.pull_request_outcome` so that one unreachable pull request cannot abort a reconcile
    # over all of them. A decode failure genuinely can arrive -- that call reaches `gh api` and
    # reads its output -- but the read is inside the forge, and what undecodable bytes mean there
    # is decided by a handler at that read rather than by this `continue`. A driver here would
    # prove the loop survives a row, which nobody doubts.
    "sync/benchmark/reconcile.py::reconcile_pull_request_outcomes::Exception",
    # The clearest member of this group, and the only one that demonstrably makes the decision
    # rather than deferring it. `classify_intake_exception` names `UnicodeDecodeError` in the same
    # arm as `json.JSONDecodeError` and `yaml.YAMLError` and returns the coded reason
    # `spec_unparseable`, which is written to `intake_attempt.reason_code` from a closed
    # vocabulary. So undecodable vendor bytes do not vanish into a catch-all here: they are
    # recorded, aggregable, and distinguishable from a network error or a 404.
    "sync/signals/intake_attempt.py::execute_intake_attempt::Exception",
)

# A read sits under these two, so they are the blind spot rather than an instance of it being
# harmless. Both say so where they sit. The docstring above carries what is known about each.
_GUARDS_A_READ = (
    # `set_dismissal` catches ValueError twice and they are not the same clause, so the
    # decision is recorded for both here rather than left for the next reader to re-derive.
    #
    # The first guards `await request.json()`, which IS a read and CAN produce undecodable
    # bytes: a client may post anything, and `json.loads` decodes UTF-8 before it parses, so
    # invalid bytes arrive as `UnicodeDecodeError` -- a `ValueError` subclass. Subsuming it is
    # deliberate. A body that is not valid UTF-8 is a malformed body, and `body must be JSON`
    # is the true answer to both; a separate handler would say the same sentence in more words.
    # This is a system boundary, which is where CLAUDE.md says to validate.
    #
    # The second guards `dismissal_writer`, which decodes nothing -- `record_dismissal` raises
    # `ValueError` on a reason outside the closed vocabulary, from a string already in memory.
    # It needs no decode handler and could never produce one.
    "sync/api/app.py::create_app.set_dismissal::ValueError",
    # `set_staging` is the same two-clause shape as `set_dismissal` above and the reasoning
    # transfers exactly: the first guards `await request.json()`, a boundary read that can meet
    # bytes that are not UTF-8, and `body must be JSON` is the true answer to a malformed
    # encoding as much as to malformed syntax; the second guards `staging_writer`, which
    # validates a dict already in memory and reads nothing.
    "sync/api/app.py::create_app.set_staging::ValueError",
    "sync/api/app.py::create_app.set_repo_context::ValueError",
    "sync/api/app.py::create_app.set_settings::ValueError",
    # Two reads of `provenance.json` out of the vendor cache, each `json.loads` over a
    # `read_text(encoding="utf-8")`. Undecodable bytes ARE reachable -- the file is written by an
    # adapter staging run and a truncated or half-written one is exactly what this guards -- and
    # subsuming is deliberate in both. Neither caller is reporting on the file: `_staged` answers
    # "is this vendor staged, and at what tag" and `_vendor_cache_item` builds a setup-checklist
    # line. A provenance file that cannot be decoded and one that is not valid JSON are the same
    # answer to both questions, which is "staged, tag unknown" -- and that is what they return
    # rather than a failure, because an unreadable tag does not unstage an adapter.
    "sync/dashboard/catalog.py::_staged::OSError+ValueError",
    "sync/dashboard/setup.py::_vendor_cache_item::OSError+ValueError",
    "sync/cli.py::benchmark::KeyError+LookupError+ValueError",
    "sync/index/python_lang.py::PythonAdapter._syntax_errors::ValueError",
)

SUBSUMING: tuple[str, ...] = _DECODES_NOTHING + _WHOLE_STAGE_CATCH_ALL + _GUARDS_A_READ


def test_no_subsuming_chain_in_src_is_unaccounted_for() -> None:
    """The same limitation as above, asserted over `src/` instead of a module this test wrote.

    The check above proves the inventory misses a subsuming chain. It cannot notice one being
    added, because it never reads `src/` -- which is how the second entry in `SUBSUMING` sat in
    the tree with nothing saying so.
    """
    appeared = sorted(
        f"{handler.key} at {handler.position}"
        for handler in subsuming_handlers()
        if handler.key not in SUBSUMING
    )

    assert not appeared, (
        "these clauses catch a UnicodeDecodeError without naming one, and SUBSUMING does not "
        "account for them:\n  " + "\n  ".join(appeared) + "\n"
        "A new one is not a defect by itself. Decide whether the code it guards can produce "
        "undecodable bytes: if it can, the read wants its own `except UnicodeDecodeError` and a "
        "driver above; if it cannot, or if the clause is a whole-stage catch-all, it needs "
        "neither. Either way add the key to SUBSUMING under the comment saying which of those "
        "it is, so the next reader inherits the decision rather than the question."
    )


def test_no_entry_in_the_subsuming_census_is_gone() -> None:
    """The census only shrinks, and a line leaves in the commit that removes its clause."""
    stale = sorted(set(SUBSUMING) - {handler.key for handler in subsuming_handlers()})

    assert not stale, (
        "SUBSUMING names clauses that are no longer in src/:\n  " + "\n  ".join(stale) + "\n"
        "Delete the line. A census entry that describes nothing is one nobody can check."
    )


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
