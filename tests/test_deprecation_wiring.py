"""Which signal each deprecation source carries, and the scan asking rather than assuming.

`DEPRECATION_SOURCES` was one tuple read by four call sites doing three different jobs, and its
comment -- "Both publish one page carrying both a model lifecycle table and a parameter table" --
was false in two directions at once. Cloudflare publishes model retirements and no parameter
table, so a scan could not read it without handing the parameter parser a page that has no
parameters; and the OpenAI page, measured here, carries no parameter table either. One tuple
could not express that, so the third vendor stayed importable, tested, and unreachable.

Every test drives `sync.cli` -- the production path -- rather than the declaration, because a
declaration nothing consults is the defect this file exists to close. What each call site asks
for is asserted as behaviour: which URLs a scan fetches, which prefixes reach the indexer, and
which vendors get a detector.

No test fetches anything. The three committed fixtures are the real pages, captured by hand on
2026-07-29 and recorded in `docs/superpowers/reports/2026-07-29-third-deprecation-vendor.md`.
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import pytest

import sync.cli as cli
from sync.cli import DEPRECATION_SOURCES, _literal_call_sites, _model_deprecations
from sync.core import RepoRef
from sync.signals.deprecations import (
    ANTHROPIC,
    CLOUDFLARE,
    OPENAI,
    DeprecationSource,
    parse_deprecation_table,
    parse_parameter_deprecations,
)

FIXTURES = Path(__file__).parent / "fixtures" / "deprecations"

# After Cloudflare's stated deprecation date of May 30, 2026, which is what makes its rows
# retired rather than deprecated. Pinned so these assertions do not change meaning with the clock.
TODAY = date(2026, 7, 29)

# The committed capture behind each shipped source, keyed by vendor id rather than by filename:
# the third vendor's page is named for the product it retires and matching on the id keeps this
# map readable as "one page per source".
PAGE_FILES = {
    "anthropic": "anthropic.md",
    "openai": "openai.md",
    "cloudflare": "cloudflare-workers-ai.md",
}


def _page(vendor_id: str) -> str:
    return (FIXTURES / PAGE_FILES[vendor_id]).read_text(encoding="utf-8")


class _Pages:
    """The three real pages, served by URL, recording what was asked for.

    Keyed on each source's own URL rather than on the vendor id appearing in it -- Anthropic
    publishes at `platform.claude.com`, which carries no such substring. A URL nobody registered
    raises, so a scan reaching for a page this test did not intend shows up here rather than as
    a silently empty parse.
    """

    def __init__(self) -> None:
        self.bodies = {source.url: _page(source.vendor_id) for source in (ANTHROPIC, OPENAI, CLOUDFLARE)}
        self.requested: list[str] = []

    def __call__(self, url: str, **kwargs) -> str:
        self.requested.append(url)
        if url not in self.bodies:
            raise AssertionError(f"nothing registered {url}")
        return self.bodies[url]


# --- what each page actually publishes, measured rather than assumed ---------------


@pytest.mark.parametrize("vendor_id", sorted(PAGE_FILES))
def test_every_shipped_page_publishes_model_deprecations(vendor_id: str):
    """The premise behind asking all three for retirements. Asserted per page so a source whose
    page stopped carrying them fails here rather than as a `RuntimeError` inside a scan."""
    assert parse_deprecation_table(vendor_id, _page(vendor_id), today=TODAY)


def test_only_the_anthropic_page_publishes_a_parameter_table():
    """The measurement the old comment got wrong, and it was wrong about OpenAI too.

    Anthropic's page carries an `## API parameter deprecations` section with a real table. The
    OpenAI page does not contain the word "parameter" anywhere, and neither does Cloudflare's --
    so this is what those vendors publish, not what the parser could not read. That distinction
    is the one the whole signal rests on, and it is why the answer is declared per source rather
    than derived by parsing and seeing what comes back.
    """
    publishing = {
        vendor_id for vendor_id in PAGE_FILES
        if parse_parameter_deprecations(vendor_id, _page(vendor_id))
    }

    assert publishing == {"anthropic"}


@pytest.mark.parametrize("vendor_id", ["openai", "cloudflare"])
def test_a_page_with_no_parameter_table_parses_to_nothing_rather_than_raising(vendor_id: str):
    """Running the parameter parser over a page that carries no parameter table is harmless.

    Established rather than assumed, because it decides how bad each of the two failure modes
    is. It returns the empty list: no raise, no partial row, nothing written. So the cost of
    scanning a page that cannot carry parameters is an operator-facing message misattributing
    lost findings to a vendor that had none to lose -- where the cost of leaving a source out of
    the model scan is eighteen retirements nobody ever sees. The modes are not symmetric, and
    the design follows the asymmetry.
    """
    assert parse_parameter_deprecations(vendor_id, _page(vendor_id)) == []


# --- the model half: every source that publishes retirements is read ---------------


def test_a_scan_reads_every_model_sources_page_including_the_third(tmp_path: Path):
    """The core assertion. `CLOUDFLARE` was defined, exported and tested, and no scan reached
    it, so eighteen Workers AI retirements were invisible while the vendor looked healthy."""
    pages = _Pages()

    changes = _model_deprecations(tmp_path, "v2320", "v2330", fetch=pages, today=TODAY)

    assert CLOUDFLARE.url in pages.requested, "no scan fetched the third vendor's page"
    retired = {change.operation_id for change in changes}
    assert any(model.startswith("@cf/") for model in retired)
    assert any(model.startswith("claude-") for model in retired)
    assert any(model.startswith("gpt-") for model in retired)


def test_the_model_scan_reads_no_page_that_publishes_no_retirements(tmp_path: Path):
    """The adapter raises on a page that parses to zero rows, and is right to: an empty answer
    is indistinguishable from a healthy vendor. Handing it a page that cannot carry retirements
    would print a vendor-unavailable message on every scan, training an operator to ignore the
    one message this signal has."""
    pages = _Pages()

    _model_deprecations(tmp_path, "v2320", "v2330", fetch=pages, today=TODAY)

    unreadable = [
        url for url in pages.requested
        if not parse_deprecation_table("x", pages.bodies[url], today=TODAY)
    ]
    assert unreadable == []


# --- the parameter half: only pages that carry a parameter table ------------------


def test_the_parameter_scan_fetches_only_pages_that_publish_a_parameter_table(tmp_path: Path):
    """Asked of the scan rather than of the declaration.

    A source whose page carries no parameter table must not reach this parser at all. The parse
    would be harmless, but the fetch failure path is not: it prints `parameter-deprecation:
    <vendor> page unavailable`, which claims a detector lost findings for a vendor that publishes
    none.
    """
    pages = _Pages()

    cli._parameter_deprecations(tmp_path, fetch=pages)

    assert set(pages.requested) == {ANTHROPIC.url}


def test_the_parameter_scan_still_reads_the_vendor_that_does_publish_one(tmp_path: Path):
    """The other direction, so the filter cannot be satisfied by scanning nothing."""
    rows = cli._parameter_deprecations(tmp_path, fetch=_Pages())

    assert {row.parameter for row in rows} >= {"temperature", "top_p", "top_k"}
    assert all(row.vendor_id == "anthropic" for row in rows)


# --- the literal indexer: every source's prefixes, whatever signal it carries -----

MODEL_LITERALS = """\
const a = await env.AI.run("@cf/meta/llama-3.1-8b-instruct", input);
const b = await env.AI.run("@hf/google/gemma-7b-it", input);
const c = await anthropic.messages.create({ model: "claude-opus-4-1-20250805" });
const d = await openai.responses.create({ model: "gpt-5-2025-08-07" });
"""


def test_the_literal_indexer_receives_every_sources_prefixes(tmp_path: Path):
    """This call site asks a different question from the other three, and is the one most
    easily folded into them: it indexes model ids in a customer's own code, which has nothing
    to do with which table the vendor publishes.

    Both of the third vendor's namespaces are asserted. Cloudflare re-hosts Hugging Face models
    under `@hf/`, and three of those are among the eighteen being retired -- a model id that is
    never indexed produces a finding with no call site to attach it to.
    """
    (tmp_path / "models.ts").write_text(MODEL_LITERALS, encoding="utf-8")
    repo = RepoRef(
        repo_id="acme/billing", url="https://example.invalid/r",
        local_path=str(tmp_path), head_sha="0" * 40,
    )

    indexed = {site.operation_id for site in _literal_call_sites(repo)[0]}

    assert "@cf/meta/llama-3.1-8b-instruct" in indexed
    assert "@hf/google/gemma-7b-it" in indexed
    assert "claude-opus-4-1-20250805" in indexed
    assert "gpt-5-2025-08-07" in indexed


# --- a .ts file this stage cannot read -----------------------------------------------

# `.ts` is MPEG transport stream as well as TypeScript, and nothing keeps one out of a customer's
# tree. A packet begins with the sync byte 0x47; the rest of these bytes are not UTF-8, and the
# payload spells a prefix the literal indexer matches on.
TRANSPORT_STREAM = (
    bytes([0x47, 0x40, 0x11, 0x10]) + b'"claude-3-' + bytes([0xE9, 0xFF, 0xFE]) + b'"'
    + bytes([0xFF] * 170)
)

# The same file a human would actually have: valid TypeScript in a legacy encoding, here an
# accented word in a comment on the line above the literal.
CP1252_SOURCE = (
    "// mod\xe8le par d\xe9faut\n"
    'const model = "claude-opus-4-1-20250805";\n'
).encode("cp1252")


def _repo_at(root: Path) -> RepoRef:
    return RepoRef(
        repo_id="acme/billing", url="https://example.invalid/r",
        local_path=str(root), head_sha="0" * 40,
    )


def test_a_ts_file_that_is_not_utf8_indexes_no_mangled_model_id(tmp_path: Path):
    """A replacement character in a matched literal is a model id the customer's code does not
    name.

    `operation_id` is the value of the literal and it is the join key the deprecation detector
    matches a retirement against, so a mangled one is a call site recorded against a model that
    does not exist -- and it is not inert: the value carries U+FFFD, and writing it to a cp1252
    stream raises `UnicodeEncodeError` somewhere with no idea where the character came from.
    """
    (tmp_path / "models.ts").write_bytes('const m = "claude-3-caf\xe9";\n'.encode("cp1252"))

    sites, unread = _literal_call_sites(_repo_at(tmp_path))

    assert [site.operation_id for site in sites if "�" in site.operation_id] == []
    assert sites == []
    assert unread == ["models.ts"]


def test_a_transport_stream_named_ts_produces_no_phantom_call_site(tmp_path: Path):
    """`read_checkout` refuses lenient decoding by name for exactly this: a mangled binary is
    still a file the indexer will parse, and whatever it makes of one can only be phantom call
    sites. This stage read the same bytes leniently and recorded one."""
    (tmp_path / "clip.ts").write_bytes(TRANSPORT_STREAM)

    assert _literal_call_sites(_repo_at(tmp_path)) == ([], ["clip.ts"])


def test_a_file_it_cannot_read_is_returned_rather_than_silently_skipped(tmp_path):
    """Skipping is only honest if it is visible, and visible to the caller rather than only to a
    log. A legacy-encoded `.ts` file holds real model literals this stage no longer indexes, and
    the cost of refusing to guess is that somebody has to be told which file to look at.

    Returned rather than printed since B60, for the reason `sync.benchmark.score` states about
    `skipped_files`: whoever read the tree is the only one who knows, and a warning per file said
    a file was missed without ever saying how much was.
    """
    (tmp_path / "legacy.ts").write_bytes(CP1252_SOURCE)

    sites, unread = _literal_call_sites(_repo_at(tmp_path))

    assert sites == []
    assert unread == ["legacy.ts"]


def test_one_unreadable_file_does_not_cost_the_readable_ones(tmp_path: Path):
    """The property `index_operation_literals` already keeps for a file that does not parse:
    customer repositories contain files this stage cannot use, and one of them must not empty the
    index."""
    (tmp_path / "legacy.ts").write_bytes(CP1252_SOURCE)
    (tmp_path / "models.ts").write_text(MODEL_LITERALS, encoding="utf-8")

    indexed = {site.operation_id for site in _literal_call_sites(_repo_at(tmp_path))[0]}

    assert "claude-opus-4-1-20250805" in indexed
    assert "gpt-5-2025-08-07" in indexed


# --- the run report: a detector for every vendor whose retirements were upserted ---


def test_the_run_builds_a_detector_for_every_vendor_it_fetched_retirements_for(monkeypatch, tmp_path):
    """`VendorChangeDetector` is scoped to one vendor, so a retirement upserted for a vendor with
    no detector is a row nothing will ever read -- the wiring looks done and produces nothing.

    The two sets are asserted against each other rather than against a literal list, so a fourth
    source added to the scan and missed in the report fails here without this test being edited.
    Driven through `run()`, because line 859 is the call site and a helper asserted on its own is
    the defect this whole file exists to close.
    """
    pages = _Pages()
    recorded: dict = {}
    real_suite = cli._detector_suite

    def recording(*args, **kwargs):
        recorded.update(kwargs)
        return real_suite(*args, **kwargs)

    _stub_run(monkeypatch, pages)
    monkeypatch.setattr(cli, "_detector_suite", recording)

    assert cli.run(_run_args(tmp_path)) == 0

    fetched = {
        change.vendor_id
        for change in _model_deprecations(tmp_path / "m", "v2320", "v2330", fetch=pages, today=TODAY)
    }
    assert "cloudflare" in fetched
    assert set(recorded["deprecation_vendors"]) == fetched


# --- a source carrying one signal is read by that scan and no other ----------------

PARAMETERS_ONLY = DeprecationSource(
    vendor_id="paramsonly",
    url="https://example.invalid/parameters.md",
    prefixes=("px-",),
    publishes_model_deprecations=False,
    publishes_parameter_deprecations=True,
)

PARAMETER_TABLE = """\
| Parameter  | Status     | Behavior             | Recommended replacement |
| ---------- | ---------- | -------------------- | ----------------------- |
| `stop_seq` | Deprecated | Returns a 400 error. | `stop_sequences`        |
"""


def test_a_source_publishing_only_parameters_reaches_only_the_parameter_scan(monkeypatch, tmp_path):
    """The other half of the declaration, which no shipped source exercises.

    All three vendors publish model retirements today, so `publishes_model_deprecations` is
    True everywhere and its False branch would otherwise be a field nothing reads -- the same
    "all N pages agree" coincidence that made two of the parser's rules facts about two pages.
    A synthetic source is what makes the flag load-bearing rather than decorative.

    It matters because the two parsers fail differently: handing this page to the model adapter
    would raise on zero rows and print a vendor-unavailable message on every scan.
    """
    from sync.signals.deprecations import adapter

    monkeypatch.setattr(adapter, "DEPRECATION_SOURCES", (*DEPRECATION_SOURCES, PARAMETERS_ONLY))
    pages = _Pages()
    pages.bodies[PARAMETERS_ONLY.url] = PARAMETER_TABLE

    _model_deprecations(tmp_path / "models", "v2320", "v2330", fetch=pages, today=TODAY)
    assert PARAMETERS_ONLY.url not in pages.requested, "a page with no retirements was fetched for them"

    rows = cli._parameter_deprecations(tmp_path / "params", fetch=pages)

    assert PARAMETERS_ONLY.url in pages.requested
    assert "stop_seq" in {row.parameter for row in rows}


def test_the_run_report_omits_a_vendor_that_publishes_no_retirements(monkeypatch, tmp_path):
    """The drift the shared accessor exists to prevent, made observable.

    Line 859 and `_model_deprecations` must name the same set. Today every shipped source
    publishes retirements, so reading the unfiltered list there is accidentally correct and a
    mutation removing the filter changes nothing -- the survival that sent this test here. A
    source carrying only parameters separates them: unfiltered, it gets a `VendorChangeDetector`
    scoped to a vendor with no retirement rows in the graph, which reports a healthy zero
    forever.
    """
    from sync.signals.deprecations import adapter

    pages = _Pages()
    pages.bodies[PARAMETERS_ONLY.url] = PARAMETER_TABLE
    registered = (*DEPRECATION_SOURCES, PARAMETERS_ONLY)
    # Both bindings, and the second one is why this test exists in this form. `cli.py` imports
    # the tuple by name, so it holds its own reference: patching only the adapter's global leaves
    # `cli.DEPRECATION_SOURCES` pointing at the shipped three, and a report reading that
    # unfiltered list would return exactly the set this test expects and look correct.
    monkeypatch.setattr(adapter, "DEPRECATION_SOURCES", registered)
    monkeypatch.setattr(cli, "DEPRECATION_SOURCES", registered)

    recorded: dict = {}
    real_suite = cli._detector_suite

    def recording(*args, **kwargs):
        recorded.update(kwargs)
        return real_suite(*args, **kwargs)

    _stub_run(monkeypatch, pages)
    monkeypatch.setattr(cli, "_detector_suite", recording)

    assert cli.run(_run_args(tmp_path)) == 0

    assert "paramsonly" not in recorded["deprecation_vendors"]
    assert set(recorded["deprecation_vendors"]) == {"anthropic", "openai", "cloudflare"}


# --- a fourth source added in one place and missed in another ----------------------


def test_every_source_the_deprecations_package_defines_is_registered_for_a_scan():
    """The defect, stated as an invariant.

    `CLOUDFLARE` was a module-level `DeprecationSource` that no scan read, which is exactly what
    a fourth vendor will be on the day somebody adds the constant and stops. There is one list,
    so a source cannot be added to one and missed in another -- but it can still be defined and
    never registered, and that is what this catches.
    """
    from sync.signals.deprecations import adapter

    defined = {
        value.vendor_id
        for value in vars(adapter).values()
        if isinstance(value, DeprecationSource)
    }

    assert defined, "no sources found; this check would pass over an empty set"
    assert defined == {source.vendor_id for source in DEPRECATION_SOURCES}


def test_no_source_is_registered_twice():
    """Every row this signal writes is keyed by vendor id, so a repeated source would parse one
    page twice and upsert one vendor's retirements under two identical keys."""
    ids = [source.vendor_id for source in DEPRECATION_SOURCES]
    assert len(ids) == len(set(ids))


# --- stubs for driving `run()` without Postgres, the network or the Agent SDK ------


class _RecordingStore:
    """Enough `GraphStore` for `run()` to reach the scan."""

    def __init__(self) -> None:
        self.changes: list = []

    def apply_schema(self) -> None: ...

    def transaction(self):
        class _Nothing:
            def __enter__(self): return None
            def __exit__(self, *exc): return False

        return _Nothing()

    def truncate_all(self, keep=()) -> None: ...

    def replace_call_sites(self, repo_id, sites) -> list[str]:
        return [f"cs-{index}" for index, _ in enumerate(sites)]

    def upsert_call_site(self, site) -> str:
        return "cs-1"

    def upsert_vendor_change(self, change) -> None:
        self.changes.append(change)

    def insert_finding(self, finding) -> str:
        return "f-1"


class _NoFindings:
    detector_id = "stub"

    def __init__(self, *args, **kwargs) -> None: ...

    def scan(self):
        return []


class _StubVendor:
    vendor_id = "stripe"

    def __init__(self, *args, **kwargs) -> None: ...

    def fetch_changes(self, from_version, to_version):
        return []


class _StubAdapter:
    def __init__(self, *args, **kwargs) -> None: ...

    def matches(self, repo) -> bool:
        return True

    def index(self, repo):
        return []


def _stub_run(monkeypatch, pages) -> None:
    """Everything `run()` reaches that is not the wiring under test.

    `http_fetch` is replaced rather than a `fetch` argument, because `_model_deprecations`
    resolves the module attribute at call time precisely so a test can do this; `run()` passes
    no fetch of its own.
    """
    from sync.signals.registry import PreparedVendor

    monkeypatch.setattr(cli, "GraphStore", lambda dsn: _RecordingStore())
    monkeypatch.setattr(cli, "VendorChangeDetector", _NoFindings)
    monkeypatch.setattr(cli, "ParameterDeprecationDetector", _NoFindings)
    monkeypatch.setattr(cli, "ObservedDriftDetector", _NoFindings)
    monkeypatch.setattr(
        cli, "prepare_vendor",
        lambda vendor_id, context: PreparedVendor(adapter=_StubVendor(), documents=()),
    )
    monkeypatch.setattr(cli, "TypeScriptAdapter", _StubAdapter)
    monkeypatch.setattr(cli, "http_fetch", pages)
    # Stubbed whole rather than through the fetch: this test is about which vendors reach the
    # detector suite, and the parameter half upserts changes of its own on the way there.
    monkeypatch.setattr(cli, "_parameter_deprecations", lambda cache: [])
    monkeypatch.setattr(cli, "_literal_call_sites", lambda repo: ([], []))
    monkeypatch.setattr(
        cli, "_clone",
        lambda url, dest: RepoRef(repo_id="repo", url=url, local_path=str(dest), head_sha="0" * 40),
    )


def _run_args(tmp_path) -> argparse.Namespace:
    return argparse.Namespace(
        vendor="stripe", from_version="v2320", to_version="v2330",
        repo="https://example.invalid/r", dsn="postgresql://unused",
        cache=str(tmp_path / "cache"), limit=1, run_id=None,
    )
