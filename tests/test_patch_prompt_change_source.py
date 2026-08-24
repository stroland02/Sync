"""Where the vendor's claim came from, said rather than assumed.

B4. `VendorChange.source` is a closed vocabulary -- a structural diff of two specifications, the
vendor's own changelog, an SDK release note, a scraped deprecation table -- and the prompt said
nothing about it. A rationale derived from `oasdiff` is a fact computed from two documents; one
derived from `vendor-deprecation-table` is the vendor's prose, scraped and reformatted. They are
very different evidence and they rendered identically.

The plan states the rule for this track: unattributed prose is worse than none.
"""

from __future__ import annotations

import pytest

from sync.remediate.agent_patch import build_patch_prompt
from tests.test_agent_patch import CHANGE, FINDING, SITE


def _prompt(source: str) -> str:
    return build_patch_prompt(FINDING, CHANGE.model_copy(update={"source": source}), SITE)


@pytest.mark.parametrize(
    "source", ["oasdiff", "changelog", "sdk-release", "vendor-deprecation-table"]
)
def test_every_source_in_the_vocabulary_reaches_the_prompt(source):
    assert source in _prompt(source)


def test_a_computed_diff_and_scraped_prose_do_not_read_alike():
    """The whole point. If they render the same the source is decoration."""
    assert _prompt("oasdiff") != _prompt("vendor-deprecation-table")


def test_a_structural_diff_is_described_as_computed():
    """`oasdiff` is the strongest source here: two documents the vendor published, compared by a
    pinned binary. The agent should know the claim is derived rather than quoted."""
    rendered = _prompt("oasdiff").lower()

    assert "compar" in rendered or "diff" in rendered
    assert "specification" in rendered


def test_scraped_prose_is_described_as_the_vendor_s_own_words():
    """The weakest source, and the one most worth flagging: a page can be restyled, mis-parsed,
    or simply wrong, and none of that is visible in the sentence it produced."""
    rendered = _prompt("vendor-deprecation-table").lower()

    assert "prose" in rendered or "own words" in rendered or "published" in rendered


def test_an_unrecognised_source_is_reported_rather_than_glossed_as_something():
    """A source outside the vocabulary must not silently pick up another one's description --
    that would attach confidence the row never claimed."""
    rendered = _prompt("something-new")

    assert "something-new" in rendered
    assert "unrecognised" in rendered.lower()


def test_the_source_line_is_not_inside_the_untrusted_fence():
    """Sync's statement about the vendor's text, not the vendor's text -- the same placement
    `CI-W594` settled for the binding rung."""
    rendered = _prompt("changelog")
    fenced = rendered.split("<untrusted-vendor-text>")[1].split("</untrusted-vendor-text>")[0]

    assert "Where this came from" not in fenced
    assert "Where this came from" in rendered
