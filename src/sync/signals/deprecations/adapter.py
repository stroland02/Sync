"""The deprecation signal as a `VendorAdapter` the pipeline can pull on its own.

The catalogue parses text; this decides where the text comes from. Both vendors serve clean
markdown when the documented `.md` suffix is appended to the documentation URL, which avoids
an HTML parser and the breakage that comes with one.

Failure handling is the part worth reading. A vendor page that cannot be fetched, or that
returns 200 and parses to nothing because it was restyled, must never produce an empty change
list: empty is indistinguishable from a healthy vendor with nothing deprecated, and it hides
an outage rather than reporting one. A stale cache is preferred to silence, and silence with
no cache raises.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable

from sync.core import OperationRef, VendorChange
from sync.signals.deprecations.catalogue import parse_deprecation_table, to_vendor_changes

Fetch = Callable[[str], str]

_DEFAULT_MAX_AGE = timedelta(hours=12)


@dataclass(frozen=True)
class DeprecationSource:
    """Where a vendor publishes its deprecations, and how its models are named."""

    vendor_id: str
    url: str
    prefixes: tuple[str, ...]
    """Literal prefixes the indexer looks for. A family missing here is never indexed, so the
    finding would exist and point at nothing."""


ANTHROPIC = DeprecationSource(
    vendor_id="anthropic",
    url="https://platform.claude.com/docs/en/about-claude/model-deprecations.md",
    prefixes=("claude-",),
)

OPENAI = DeprecationSource(
    vendor_id="openai",
    url="https://developers.openai.com/api/docs/deprecations.md",
    # Broader than one prefix because OpenAI's naming is not one family. Taken from the model
    # names their own page lists rather than guessed.
    # Checked against every model id their page actually names rather than guessed. `code-`,
    # `codex-` and `ft-` were absent until that check ran, which would have left 16 real
    # deprecated models unindexed -- the finding raised, and no call site to attach it to.
    prefixes=(
        "gpt-", "chatgpt-", "o1", "o3", "o4",
        "text-", "davinci", "babbage", "curie", "ada",
        "code-", "codex-", "ft-",
        "dall-e", "whisper", "tts-", "sora-", "omni-",
    ),
)


def http_fetch(url: str, timeout: float = 20.0) -> str:
    """A plain GET returning decoded text. The default `Fetch` for real runs.

    `urllib` rather than a dependency: this is one unauthenticated GET against public
    documentation, and the decode is explicit because the platform default is the locale
    codepage on Windows.

    Tests never call this -- they inject their own fetch -- which is what keeps the suite free
    of network access.
    """
    import urllib.request

    request = urllib.request.Request(url, headers={"User-Agent": "sync-deprecation-adapter"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed https URLs
        return response.read().decode("utf-8")


def _age(path: Path) -> timedelta:
    """How old a cached page is, never negative.

    A file written moments ago can carry an mtime marginally in the future -- filesystem
    timestamp granularity against the clock -- which makes a raw subtraction negative and a
    strict `age < max_age` comparison flip non-deterministically. Clamping at zero means a
    `max_age` of zero reliably means "always refetch" rather than "usually".
    """
    stamp = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return max(datetime.now(timezone.utc) - stamp, timedelta(0))


class DeprecationAdapter:
    """Turns a vendor's published deprecation page into `VendorChange` rows."""

    def __init__(
        self,
        source: DeprecationSource,
        fetch: Fetch,
        cache_path: Path | str,
        max_age: timedelta = _DEFAULT_MAX_AGE,
        today: date | None = None,
    ) -> None:
        self._source = source
        self._fetch = fetch
        self._cache = Path(cache_path)
        self._max_age = max_age
        self._today = today

    @property
    def vendor_id(self) -> str:
        return self._source.vendor_id

    @property
    def prefixes(self) -> tuple[str, ...]:
        """What the literal indexer should look for in customer source."""
        return self._source.prefixes

    def operation_for_symbol(self, symbol: str) -> OperationRef | None:
        """Always `None`: a model id is not an SDK symbol.

        Fabricating an `OperationRef` would mean inventing an HTTP method and path a model does
        not have. The binding for this signal comes from the literal indexer, which produces
        `operation_id` directly and needs no symbol map.
        """
        return None

    def fetch_changes(self, from_version: str, to_version: str) -> Iterable[VendorChange]:
        # Resolved once and used twice. The parse derives lifecycle state from a date and
        # `to_vendor_changes` measures urgency against one, so two reads of the clock could
        # produce a row that says `retired` and counts down to a future retirement.
        today = self._today or date.today()

        body, is_fresh = self._page()
        rows = parse_deprecation_table(self.vendor_id, body, today=today)

        if not rows:
            # A 200 that parses to nothing is the likeliest way this breaks -- a vendor
            # restyling their documentation. Zero rows is not evidence the deprecations were
            # withdrawn, so the cache is deliberately left as it was and an operator hears
            # about it. Caching first would compound the failure: the next run would find an
            # unparseable page cached and have nothing good to fall back on.
            raise RuntimeError(
                f"{self.vendor_id} page returned no deprecation rows; "
                f"the published format has probably changed ({self._source.url})"
            )

        if is_fresh:
            self._store(body)

        return to_vendor_changes(
            rows, from_version=from_version, to_version=to_version, today=today
        )

    def _page(self) -> tuple[str, bool]:
        """The page, and whether it came from the network rather than the cache.

        Nothing is written here. A page is only cached once it has been shown to parse, which
        is why the caller stores rather than this method.
        """
        if self._cache.exists() and _age(self._cache) < self._max_age:
            return self._cache.read_text(encoding="utf-8"), False

        try:
            return self._fetch(self._source.url), True
        except Exception as exc:
            # Yesterday's answer beats a confident empty one. Only a failure with nothing
            # cached has no honest answer, and that raises rather than reporting silence.
            if self._cache.exists():
                return self._cache.read_text(encoding="utf-8"), False
            raise RuntimeError(
                f"{self.vendor_id} deprecation page could not be retrieved and nothing is "
                f"cached ({self._source.url}): {exc}"
            ) from exc

    def _store(self, body: str) -> None:
        """Cache the page, but never let a caching failure lose a good fetch."""
        try:
            self._cache.parent.mkdir(parents=True, exist_ok=True)
            self._cache.write_text(body, encoding="utf-8")
        except OSError:
            pass
