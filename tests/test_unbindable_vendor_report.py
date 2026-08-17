"""A run whose vendor can bind no call site says so, rather than reporting a clean scan.

The defect this closes, measured 2026-08-16 against `sync.signals.registry`: `available_vendors()`
offers six vendors and four of them -- every vendor served by `GeneratedSpecAdapter` -- were
constructed with no `sdk_source`, on both the `prepare_vendor` and the `load_vendor` path. The
symbol map for those four is never built, so `operation_for_symbol` answers `None` for every
symbol and both indexers `continue` past every call. A repository that genuinely calls the SDK and
one that has never heard of the vendor produced the same output: no call sites, no findings,
exit 0.

That is the shape `select_language_adapter` already refuses in its own docstring -- "a run that
appears to work and establishes nothing" -- and the shape `CLAUDE.md` forbids the console to
render: a zero that is not a measurement, presented where a measurement would go.

**Why the two states are exercised with one adapter class rather than two.** A test that pointed
one vendor at a symbol map and another at nothing would be comparing two implementations, and the
thing under test is whether a run can tell "we looked and found none" from "we could not look".
`GeneratedSpecAdapter` is both states: staged against the committed `anthropic_python` checkout it
resolves symbols, and unstaged it resolves none. Same class, same vendor id, same run path, one
difference.

The control matters as much as the subject. A report that fires for every vendor is a heading the
next reader learns to skip -- `_coverage_lines` carries that reasoning -- and it would also erase
the distinction it exists to draw, since a qualification printed over a real zero says the real
zero is not a measurement either.

Nothing here reaches a network, a database or the Agent SDK. `_never_fetch` raises rather than
returning, so a specification fetch appearing on this path fails the test instead of being
tolerated by it.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from sync import cli
from sync.core import RepoRef
from sync.signals.generated.adapter import GeneratedSpecAdapter
from sync.signals.registry import PreparedVendor

FIXTURES = Path(__file__).parent / "fixtures" / "sdk_sources"
STAGED_SDK = FIXTURES / "anthropic_python"

# The symbol that separates the two states, taken from the committed checkout rather than
# invented: `anthropic_python` states `POST /v1/messages` for this chain, and
# `test_extracted_symbols.py` is what proves the extraction reads it.
KNOWN_SYMBOL = "anthropic.messages.create"


def _never_fetch(url: str) -> str:
    raise AssertionError(f"a run reached the network for {url}")


def _generated(cache: Path, sdk_source: Path | None) -> GeneratedSpecAdapter:
    """The adapter a configured vendor's run builds, with and without a staged checkout.

    `sources={}` because a version pair this deployment has no manifest for is what
    `observability` reports as `NO_MANIFEST`, and that path returns an empty change list without
    fetching. The subject here is the binding gap, not the diff.
    """
    return GeneratedSpecAdapter(
        vendor_id="anthropic",
        sources={},
        fetch=_never_fetch,
        cache_dir=cache,
        sdk_source=sdk_source,
    )


class _RecordingStore:
    """Enough `GraphStore` for `run()` to reach the report."""

    def apply_schema(self) -> None: ...

    def transaction(self):
        class _Nothing:
            def __enter__(self): return None
            def __exit__(self, *exc): return False

        return _Nothing()

    def truncate_all(self, keep=()) -> None: ...

    def replace_call_sites(self, repo_id, sites) -> list[str]:
        return [f"cs-{index}" for index, _ in enumerate(sites)]

    def upsert_vendor_change(self, change) -> str:
        return "vc-1"

    def insert_finding(self, finding) -> str:
        return "f-1"


class _StubLanguageAdapter:
    """Claims the repository and indexes nothing, which is what every repository looks like once
    `operation_for_symbol` has declined every symbol in it."""

    language_id = "typescript"

    def __init__(self, *args, **kwargs) -> None: ...

    def matches(self, repo) -> bool:
        return True

    def index(self, repo):
        return []


def _stub_run(monkeypatch, vendor) -> None:
    monkeypatch.setattr(cli, "GraphStore", lambda dsn: _RecordingStore())
    monkeypatch.setattr(cli, "TypeScriptAdapter", _StubLanguageAdapter)
    monkeypatch.setattr(
        cli, "prepare_vendor",
        lambda vendor_id, context: PreparedVendor(adapter=vendor, documents=()),
    )
    monkeypatch.setattr(cli, "_parameter_deprecations", lambda cache: [])
    monkeypatch.setattr(cli, "_model_deprecations", lambda *args, **kwargs: [])
    monkeypatch.setattr(cli, "_literal_call_sites", lambda repo: ([], []))
    monkeypatch.setattr(cli, "_scan", lambda detectors, store: [])
    monkeypatch.setattr(
        cli, "_clone",
        lambda url, dest: RepoRef(
            repo_id="repo", url=url, local_path=str(dest), head_sha="0" * 40
        ),
    )


def _run_args(tmp_path: Path) -> argparse.Namespace:
    return argparse.Namespace(
        vendor="anthropic", from_version="v1", to_version="v2",
        repo="https://example.invalid/r", dsn="postgresql://unused",
        cache=str(tmp_path / "cache"), limit=1, run_id=None,
    )


def _run(monkeypatch, capsys, tmp_path: Path, sdk_source: Path | None) -> str:
    vendor = _generated(tmp_path / "cache", sdk_source)
    _stub_run(monkeypatch, vendor)
    assert cli.run(_run_args(tmp_path)) == 0
    return capsys.readouterr().out


def test_a_vendor_that_binds_nothing_is_reported_rather_than_counted_as_zero(
    monkeypatch, capsys, tmp_path
):
    """The subject. The reason printed is the adapter's own, not a sentence this file wrote --
    a message composed at the boundary would be `cli.py` explaining a vendor's substrate, and
    the only thing that knows why a symbol map is absent is the adapter that failed to build it.
    """
    unstaged = _generated(tmp_path / "cache", None)

    out = _run(monkeypatch, capsys, tmp_path, sdk_source=None)

    assert unstaged.unbindable_reason is not None
    assert unstaged.unbindable_reason in out
    assert "anthropic" in out


def test_the_report_precedes_the_finding_count_it_qualifies(monkeypatch, capsys, tmp_path):
    """`_coverage_lines` is placed for this reason and states it: a reader who meets the number
    first has already drawn a conclusion from it. A qualification printed underneath arrives
    after the damage."""
    unstaged = _generated(tmp_path / "cache", None)

    out = _run(monkeypatch, capsys, tmp_path, sdk_source=None)

    assert out.index(unstaged.unbindable_reason) < out.index("finding(s)")


def test_a_vendor_that_binds_is_not_qualified(monkeypatch, capsys, tmp_path):
    """The control, and the half that makes the subject mean anything.

    This run reports the same zero as the one above -- the stub indexer finds no call sites --
    and it is a real zero: the vendor could have bound one. Printing the qualification here would
    say a measurement is not a measurement, and would put a heading on every run.
    """
    staged = _generated(tmp_path / "cache", STAGED_SDK)
    assert staged.operation_for_symbol(KNOWN_SYMBOL) is not None, (
        "the committed checkout no longer resolves the symbol this test contrasts against"
    )

    out = _run(monkeypatch, capsys, tmp_path, sdk_source=STAGED_SDK)

    assert staged.unbindable_reason is None
    # The count and nothing else. Asserted as the whole output rather than as the absence of a
    # phrase: a test that greps for the qualification's current wording stops catching it the
    # moment somebody rewords the qualification, which is the edit most likely to break this.
    assert out.strip() == "0 finding(s)"


def test_the_count_alone_cannot_tell_the_two_apart(monkeypatch, capsys, tmp_path):
    """Why the qualification has to exist at all, asserted rather than argued.

    Both runs print the identical count. If the count were the whole report, a repository calling
    the vendor and a repository that cannot be looked at would be one output.
    """
    unstaged_out = _run(monkeypatch, capsys, tmp_path / "unstaged", sdk_source=None)
    staged_out = _run(monkeypatch, capsys, tmp_path / "staged", sdk_source=STAGED_SDK)

    assert "0 finding(s)" in unstaged_out
    assert "0 finding(s)" in staged_out
    assert unstaged_out != staged_out


def test_an_adapter_that_declares_nothing_is_not_reported_as_unbindable(
    monkeypatch, capsys, tmp_path
):
    """`unbindable_reason` is optional the way `unverifiable_reason` and `sdk_bindings` are.

    `VendorAdapter` is a protocol this repository publishes for third parties, and an adapter
    written before this field existed must go on running unqualified rather than being described
    as unable to bind. The safe direction is the same one `unverifiable_reason` takes: silence
    means the ordinary case, and a gap is something an adapter has to assert.
    """
    class _Silent:
        vendor_id = "acme"

        def fetch_changes(self, from_version, to_version):
            return []

        def operation_for_symbol(self, symbol, *, language=None):
            return None

    _stub_run(monkeypatch, _Silent())
    assert cli.run(_run_args(tmp_path)) == 0

    assert capsys.readouterr().out.strip() == "0 finding(s)"
