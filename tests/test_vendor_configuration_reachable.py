"""Does every configured row still point at something that exists?

Every other gate in this repository reads committed fixtures, which is right -- the suite must
answer offline -- and structurally blind to the one failure mode that matters most here: a vendor
deleting the file we watch. `generated-vendors.yaml` states that each entry was confirmed by
fetching it on a date, and nothing enforced that sentence.

It went stale exactly as you would expect. `openai/openai-python` removed `.stats.yml` on
2026-08-12 in a commit titled *remove Stainless attribution and infrastructure*, and the row for
the most-called vendor in the corpus pointed at a 404 for eleven days with every gate green.

Marked `network` and deselected by default. This is the check a person runs deliberately, and the
one that would have named the defect on the day it happened.
"""

from __future__ import annotations

import urllib.error
import urllib.request

import pytest

from sync.signals.registry import _RAW_CONTENT, _generated_vendors

pytestmark = pytest.mark.network

_AGENT = "sync-configuration-probe"


def _reachable(url: str) -> tuple[bool, str]:
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": _AGENT})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status == 200, str(response.status)
    except urllib.error.HTTPError as exc:
        return False, str(exc.code)
    except Exception as exc:  # noqa: BLE001 -- a probe reports, it does not raise
        return False, type(exc).__name__


def _configured_paths() -> list[tuple[str, str]]:
    return [
        (vendor_id, _RAW_CONTENT.format(repo=row.repo, ref="HEAD", path=row.manifest or row.spec))
        for vendor_id, row in sorted(_generated_vendors().items())
    ]


def test_every_configured_row_points_at_something_that_exists():
    unreachable = []
    for vendor_id, url in _configured_paths():
        ok, status = _reachable(url)
        if not ok:
            unreachable.append(f"{vendor_id}: {url} -> {status}")

    assert not unreachable, (
        "a configured row names a document its vendor no longer publishes. The row is stale, not "
        "the vendor unwatchable -- find where the specification moved to and repoint it:\n  "
        + "\n  ".join(unreachable)
    )


def test_the_probe_can_fail():
    """A reachability check that has only ever seen reachable things has proved nothing."""
    reachable, status = _reachable(
        "https://raw.githubusercontent.com/openai/openai-python/HEAD/.stats.yml"
    )

    assert reachable is False
    assert status == "404"
