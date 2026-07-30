"""How the indexer decodes the customer's own source, and why it must decode it the way it
decodes a vendor's.

There are four copies of one three-line helper in this repository. The two over a vendor's SDK
source -- `signals.generated.symbols_typescript._text` and `symbols_speakeasy._text` -- slice
tree-sitter's byte offsets and decode strictly. The two over the customer's repository --
`index.typescript._text` and `index.python_lang._text` -- passed `errors="replace"`. Same helper,
same parser, opposite discipline, and the lenient half was the one pointed at somebody else's
code. All four are strict now; the four parametrised cases below are what holds them level.

`benchmark.read_checkout` already settled the argument for the corpus, and its wording is the
brief for this: "Skipped rather than decoded leniently. `errors="replace"` would hand the indexer
a file full of replacement characters, which is still a file it will parse." So a corpus score is
measured with undecodable files skipped and named, and a customer scan is run with them mangled
and silent. `PythonAdapter._syntax_errors` reads the same files strictly and names the ones that
fail, three hundred lines from the loop that did not.

What the leniency produced, measured on one cp1252 file per language before this changed:

    args_keys              ['amount', 'meta', 'meta.co<U+FFFD>t']
    response_fields_read   ['st']

The first is a phantom argument key, and `ParameterDeprecationDetector` joins on that column. The
second is worse, and is why this is not cosmetic: the source reads `charge.status` with an
a-circumflex in it, and what reached the graph is a claim that the call site depends on a response
field named `st`. Nothing downstream can tell that from a real field.
`2026-07-26-sync-review-integration.md` puts a false attribution above a missed finding in cost,
and this manufactured them out of an encoding.

The fixtures below are the exception `.claude/rules/test-discipline.md` allows: non-ASCII content
added specifically to exercise a decode path. Each is encoded with an explicit `.encode("cp1252")`
rather than written to disk as UTF-8, because the bytes are the whole subject.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from sync.cli import _literal_call_sites
from sync.core import OperationRef, RepoRef
from sync.index import python_lang, typescript
from sync.signals.generated import symbols_speakeasy, symbols_typescript


class _Vendor:
    """Resolves the one symbol every fixture below calls, in either language."""

    vendor_id = "stripe"
    sdk_bindings = {
        "typescript": {"package": "stripe"},
        "python": {"distribution": "stripe", "module": "stripe"},
    }

    def operation_for_symbol(self, symbol: str, *, language: str | None = None):
        if symbol.endswith("charges.create"):
            return OperationRef(operation_id="PostCharges", http_method="post", path="/v1/charges")
        return None

    def fetch_changes(self, from_version: str, to_version: str):
        return []


_TS_CLEAN = """import Stripe from 'stripe';
const stripe = new Stripe('k');
export async function a() {
  const charge = await stripe.charges.create({ amount: 1 });
  return charge.status;
}
"""

# Legal TypeScript and legal cp1252. The accented response field is what makes the case: decoded
# leniently its name comes back as `st`, which is not a mangled string a reader could spot but a
# different field the vendor may well publish.
_TS_LEGACY = """import Stripe from 'stripe';
const stripe = new Stripe('k');
export async function b() {
  const charge = await stripe.charges.create({ "coût": 1, amount: 2 });
  return charge.stâtus;
}
"""

_PY_CLEAN = '''import stripe

client = stripe.StripeClient("k")


def a():
    charge = client.charges.create(amount=1)
    return charge.status
'''

# Legal Python: PEP 263 lets a module declare its own encoding, which is how a cp1252 file is
# still a file the interpreter runs and the indexer must not corrupt.
_PY_LEGACY = '''# -*- coding: cp1252 -*-
import stripe

client = stripe.StripeClient("k")


def b():
    charge = client.charges.create(amount=2, meta={"coût": 1})
    return charge.stâtus
'''


def _typescript_repo(root: Path) -> RepoRef:
    (root / "package.json").write_text(
        '{"dependencies": {"stripe": "17.0.0"}}', encoding="utf-8"
    )
    source = root / "src"
    source.mkdir()
    (source / "clean.ts").write_text(_TS_CLEAN, encoding="utf-8")
    (source / "legacy.ts").write_bytes(_TS_LEGACY.encode("cp1252"))
    return RepoRef(
        repo_id="r1", url="https://example.invalid/r", local_path=str(root), head_sha="0" * 40
    )


def _python_repo(root: Path) -> RepoRef:
    (root / "pyproject.toml").write_text(
        '[project]\nname = "x"\ndependencies = ["stripe>=12.0"]\n', encoding="utf-8"
    )
    source = root / "src"
    source.mkdir()
    (source / "clean.py").write_text(_PY_CLEAN, encoding="utf-8")
    (source / "legacy.py").write_bytes(_PY_LEGACY.encode("cp1252"))
    return RepoRef(
        repo_id="r1", url="https://example.invalid/r", local_path=str(root), head_sha="0" * 40
    )


_LANGUAGES = [
    pytest.param(typescript.TypeScriptAdapter, _typescript_repo, "ts", id="typescript"),
    pytest.param(python_lang.PythonAdapter, _python_repo, "py", id="python"),
]


@pytest.mark.parametrize("adapter_type, build, suffix", _LANGUAGES)
def test_a_source_file_that_does_not_decode_contributes_nothing(
    tmp_path: Path, adapter_type: type, build, suffix: str
) -> None:
    """One repository, two files, and only the one that is UTF-8 reaches the graph.

    Asserted as the whole row set rather than as an absence of replacement characters, because
    the truncated `response_fields_read` is the case such a check would pass over: `st` carries no
    marker at all.
    """
    repo = build(tmp_path)
    adapter = adapter_type(vendor_adapter=_Vendor())

    sites = list(adapter.index(repo))

    assert [(s.path, s.args_keys, s.response_fields_read) for s in sites] == [
        (f"src/clean.{suffix}", ["amount"], ["status"]),
    ]


@pytest.mark.parametrize("adapter_type, build, suffix", _LANGUAGES)
def test_the_file_that_could_not_be_decoded_is_named(
    tmp_path: Path, adapter_type: type, build, suffix: str, caplog: pytest.LogCaptureFixture
) -> None:
    """Skipping is only defensible if the skip is legible.

    `read_checkout` returns the paths for this reason and states it: telling a legacy encoding
    apart from a binary cheaply is not possible, so naming the file is the mitigation -- "a reader
    who sees `src/legacy.ts` in the list knows to look, where a reader handed only a count could
    not." The warning reaches stderr through the default handler on a run that configures no
    logging, and `unread_paths` below is the return channel a warning is not: it says how much was
    missed, where this says only that something was.
    """
    repo = build(tmp_path)
    adapter = adapter_type(vendor_adapter=_Vendor())

    with caplog.at_level(logging.WARNING):
        list(adapter.index(repo))

    assert f"src/legacy.{suffix}" in caplog.text
    assert f"src/clean.{suffix}" not in caplog.text


@pytest.mark.parametrize("adapter_type, build, suffix", _LANGUAGES)
def test_the_paths_it_could_not_read_are_reported_to_the_run(
    tmp_path: Path, adapter_type: type, build, suffix: str
) -> None:
    """The record both adapters kept and nothing in `src/` read.

    Each already recorded every skipped file to dedupe its warning, so the figure a run needed
    existed and had no reader -- and the run's coverage report counted the literal pass, which
    walks `*.ts`, while this pass walks every source file. Over a Python repository that made the
    figure structurally blind: measured, a legacy-encoded module is skipped here and the literal
    pass reports nothing, so a run said it could not read zero paths having skipped a module the
    interpreter runs.

    Empty before `index` and filled after, which is the half that has to be asserted rather than
    assumed. `_readable_sources` records as the walk reaches each file, so a caller that asked
    first would report nothing on a scan that skipped plenty -- and would pass a test that only
    checked the value afterwards.
    """
    repo = build(tmp_path)
    adapter = adapter_type(vendor_adapter=_Vendor())

    assert adapter.unread_paths(repo) == []

    list(adapter.index(repo))

    assert adapter.unread_paths(repo) == [f"src/legacy.{suffix}"]


class _Slice:
    """A stand-in for a tree-sitter node, which is two byte offsets as far as `_text` is
    concerned."""

    def __init__(self, start: int, end: int) -> None:
        self.start_byte = start
        self.end_byte = end


@pytest.mark.parametrize(
    "reader",
    [
        pytest.param(typescript._text, id="index.typescript"),
        pytest.param(python_lang._text, id="index.python_lang"),
        pytest.param(symbols_typescript._text, id="signals.symbols_typescript"),
        pytest.param(symbols_speakeasy._text, id="signals.symbols_speakeasy"),
    ],
)
def test_every_copy_of_the_node_reader_decodes_the_same_way(reader) -> None:
    """The asymmetry, stated where it lives.

    Four copies of one helper, two over a vendor's SDK and two over a customer's repository. A
    reader that substitutes rather than raising cannot be told from one that read the file
    correctly, so the strict pair is the one both halves have to agree on -- and raising here is
    what holds the callers to filtering undecodable bytes out before this is reached.
    """
    with pytest.raises(UnicodeDecodeError):
        reader(_Slice(0, 3), b"a\xfbb")


def test_literal_indexing_skips_a_file_it_cannot_decode(tmp_path: Path) -> None:
    """The third reader of the customer's source, and the one that said `errors="replace"` outright.

    `_literal_call_sites` feeds the parameter-deprecation detector, whose rows carry a model id and
    the arguments passed beside it. Read leniently, the content hash is taken over a line the file
    does not contain and the sibling keys are whatever the substitution made of them.
    """
    (tmp_path / "clean.ts").write_text(
        'const r = await client.messages.create({ model: "claude-3-opus-20240229" });\n',
        encoding="utf-8",
    )
    (tmp_path / "legacy.ts").write_bytes(
        'const r = await client.messages.create({ model: "claude-3-sonnet-20240229", '
        '"coût": 1 });\n'.encode("cp1252")
    )
    repo = RepoRef(
        repo_id="r1", url="https://example.invalid/r",
        local_path=str(tmp_path), head_sha="0" * 40,
    )

    sites, unread = _literal_call_sites(repo)

    assert [s.path for s in sites] == ["clean.ts"]
    # Returned rather than logged since B60: the run counts these into its coverage report, and a
    # message printed here was a file named without the total it belonged to.
    assert unread == ["legacy.ts"]
