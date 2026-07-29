"""The deprecation signal as a `VendorAdapter` the pipeline can pull on its own.

Until now the catalogue parsed text somebody handed it, so SIGNAL needed a human. This closes
that: a source names where the page lives, a fetch retrieves it, and a cache means a run that
finds nothing new costs one conditional request instead of a download.

The load-bearing behaviour is what happens when the fetch fails. Returning no changes would
read as "nothing is deprecated" -- indistinguishable from a healthy vendor, and wrong in the
direction that hides an outage. A stale cache is used instead, and a failure with no cache at
all raises rather than reporting silence.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from sync.core.protocols import VendorAdapter
from sync.signals.deprecations.adapter import (
    ANTHROPIC,
    CLOUDFLARE,
    OPENAI,
    DeprecationAdapter,
)

FIXTURES = Path(__file__).parent / "fixtures" / "deprecations"

PAGE = """\
| API model name | Current state | Deprecated   | Tentative retirement date |
| -------------- | ------------- | ------------ | ------------------------- |
| claude-opus-9  | Active        | N/A          | Not sooner than May 1, 2028 |
| claude-old-1   | Retired       | June 5, 2026 | August 5, 2026            |

### 2026-06-05: an announcement

| Retirement date | Deprecated model | Recommended replacement |
| --------------- | ---------------- | ----------------------- |
| August 5, 2026  | `claude-old-1`   | `claude-opus-9`         |
"""


class Fetcher:
    """Records calls so caching can be asserted rather than assumed."""

    def __init__(self, body: str = PAGE, fails: bool = False) -> None:
        self.body = body
        self.fails = fails
        self.calls = 0

    def __call__(self, url: str) -> str:
        self.calls += 1
        if self.fails:
            raise OSError("network is down")
        return self.body


def _adapter(fetch: Fetcher, cache: Path, **kw) -> DeprecationAdapter:
    return DeprecationAdapter(ANTHROPIC, fetch=fetch, cache_path=cache, today=date(2026, 7, 28), **kw)


# --- the protocol ----------------------------------------------------------------


def test_it_satisfies_the_vendor_adapter_protocol(tmp_path: Path):
    assert isinstance(_adapter(Fetcher(), tmp_path / "c.md"), VendorAdapter)


def test_the_vendor_id_comes_from_the_source(tmp_path: Path):
    assert _adapter(Fetcher(), tmp_path / "c.md").vendor_id == "anthropic"


def test_operation_for_symbol_is_always_none(tmp_path: Path):
    """A model id is not an SDK symbol, so no symbol resolves to one.

    Returning a fabricated `OperationRef` -- a method and path a model does not have -- would
    be confident nonsense. The binding for this signal comes from the literal indexer, which
    produces `operation_id` directly and needs no symbol map.
    """
    adapter = _adapter(Fetcher(), tmp_path / "c.md")
    assert adapter.operation_for_symbol("client.messages.create") is None
    assert adapter.operation_for_symbol("claude-old-1") is None


# --- fetching and parsing --------------------------------------------------------


def test_it_produces_changes_from_a_fetched_page(tmp_path: Path):
    changes = list(_adapter(Fetcher(), tmp_path / "c.md").fetch_changes("a", "b"))

    assert [c.operation_id for c in changes] == ["claude-old-1"]
    assert changes[0].raw["replacement"] == "claude-opus-9"
    assert changes[0].source == "vendor-deprecation-table"


def test_an_active_model_produces_no_change(tmp_path: Path):
    changes = list(_adapter(Fetcher(), tmp_path / "c.md").fetch_changes("a", "b"))
    assert "claude-opus-9" not in {c.operation_id for c in changes}


# --- caching ---------------------------------------------------------------------


def test_a_fresh_cache_is_used_without_fetching(tmp_path: Path):
    cache = tmp_path / "c.md"
    fetch = Fetcher()

    _adapter(fetch, cache).fetch_changes("a", "b")
    _adapter(fetch, cache).fetch_changes("a", "b")

    assert fetch.calls == 1, "the second run refetched a page it already had"


def test_a_stale_cache_is_refreshed(tmp_path: Path):
    cache = tmp_path / "c.md"
    cache.write_text(PAGE, encoding="utf-8")
    old = datetime.now(timezone.utc) - timedelta(days=30)
    import os

    os.utime(cache, (old.timestamp(), old.timestamp()))

    fetch = Fetcher()
    _adapter(fetch, cache, max_age=timedelta(hours=6)).fetch_changes("a", "b")

    assert fetch.calls == 1


def test_the_cache_is_written_so_the_next_run_is_free(tmp_path: Path):
    cache = tmp_path / "c.md"
    _adapter(Fetcher(), cache).fetch_changes("a", "b")

    assert cache.exists()
    assert "claude-old-1" in cache.read_text(encoding="utf-8")


# --- failure, which is where silence would be the bug -----------------------------


def test_a_failed_fetch_falls_back_to_a_stale_cache(tmp_path: Path):
    """Returning nothing would read as "nothing is deprecated".

    That is indistinguishable from a healthy vendor and wrong in the direction that hides an
    outage. Yesterday's answer is far better than a confident empty one.
    """
    cache = tmp_path / "c.md"
    cache.write_text(PAGE, encoding="utf-8")

    changes = list(_adapter(Fetcher(fails=True), cache, max_age=timedelta(0)).fetch_changes("a", "b"))
    assert [c.operation_id for c in changes] == ["claude-old-1"]


def test_a_failed_fetch_with_no_cache_raises(tmp_path: Path):
    """The one case with no honest answer. Raising reaches an operator; returning an empty
    list reaches nobody and looks like success."""
    with pytest.raises(RuntimeError, match="could not be retrieved"):
        _adapter(Fetcher(fails=True), tmp_path / "missing.md").fetch_changes("a", "b")


def test_a_page_that_parses_to_nothing_does_not_overwrite_a_good_cache(tmp_path: Path):
    """A vendor restyling their documentation is the likeliest way this breaks.

    Zero rows from a 200 response is not evidence the deprecations vanished, so the cached
    page stands and the run raises rather than reporting silence.
    """
    cache = tmp_path / "c.md"
    cache.write_text(PAGE, encoding="utf-8")

    with pytest.raises(RuntimeError, match="no deprecation rows"):
        _adapter(Fetcher(body="# Deprecations\n\nWe reorganised this page.\n"), cache,
                 max_age=timedelta(0)).fetch_changes("a", "b")

    assert "claude-old-1" in cache.read_text(encoding="utf-8"), "a good cache was replaced by an empty page"


# --- the shipped sources ---------------------------------------------------------


@pytest.mark.parametrize("source", [ANTHROPIC, CLOUDFLARE, OPENAI])
def test_the_shipped_sources_are_complete(source):
    assert source.vendor_id
    assert source.url.startswith("https://")
    assert source.url.endswith(".md"), "vendors serve markdown at the .md suffix; HTML needs a parser"
    assert source.prefixes, "the literal indexer needs prefixes to know what to look for"


def test_the_prefixes_cover_the_models_the_vendor_actually_names(tmp_path: Path):
    """A prefix list that misses a family means those literals are never indexed, so the
    finding exists and points at nothing."""
    changes = list(_adapter(Fetcher(), tmp_path / "c.md").fetch_changes("a", "b"))
    assert all(c.operation_id.startswith(ANTHROPIC.prefixes) for c in changes)


def test_a_third_vendor_needs_no_adapter_change(tmp_path: Path):
    """The structure held. A vendor publishing a shape neither of the first two used is still
    a `DeprecationSource` and a `DeprecationAdapter`, with nothing in this module aware of it.

    The page is the committed capture of the real one, read rather than fetched.
    """
    page = (FIXTURES / "cloudflare-workers-ai.md").read_text(encoding="utf-8")
    adapter = DeprecationAdapter(
        CLOUDFLARE,
        fetch=Fetcher(body=page),
        cache_path=tmp_path / "cf.md",
        today=date(2026, 7, 29),
    )

    changes = list(adapter.fetch_changes("a", "b"))

    assert adapter.vendor_id == "cloudflare"
    assert len(changes) == 18
    assert all(c.severity == "breaking" for c in changes)
    assert all(c.operation_id.startswith(CLOUDFLARE.prefixes) for c in changes)
