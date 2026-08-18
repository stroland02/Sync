"""`_sandbox_wired` reads baseline *entries*, not the file's prose.

A substring search over the whole baseline text was the original shape, and it broke on its own
retirement note: the comment explaining that `ephemeral_container` had stopped violating still
names `ephemeral_container`, so the substring check read that explanation as the entry it was
describing the removal of. Reproduced here against a minimal baseline rather than the real one,
so the fixture cannot drift out from under the assertion as the real file grows.
"""

from __future__ import annotations

from pathlib import Path

from scripts.beta_gates import _sandbox_wired

_RETIRED_ENTRY_COMMENT_ONLY = """\
# `ephemeral_container` came out of this list once `docker_sdk.py` started calling it.
src/sync/remediate/sandbox.py:copy_between_containers
"""

_STILL_BASELINED = """\
src/sync/remediate/sandbox.py:copy_between_containers
src/sync/remediate/sandbox_image.py:ensure_image_built
"""

_NOTHING_BASELINED = """\
src/sync/graph/store.py:GraphStore.intake_attempts
"""


def test_a_retirement_comment_naming_the_symbol_does_not_read_as_a_live_entry(tmp_path: Path) -> None:
    baseline = tmp_path / "dead_links_baseline.txt"
    baseline.write_text(_RETIRED_ENTRY_COMMENT_ONLY, encoding="utf-8")

    ok, note = _sandbox_wired(baseline)

    assert "ephemeral_container" not in note, note


def test_a_symbol_still_carrying_a_real_entry_is_reported_unwired(tmp_path: Path) -> None:
    baseline = tmp_path / "dead_links_baseline.txt"
    baseline.write_text(_STILL_BASELINED, encoding="utf-8")

    ok, note = _sandbox_wired(baseline)

    assert ok is False
    assert "copy_between_containers" in note
    assert "ensure_image_built" in note


def test_no_sandbox_symbol_baselined_reads_wired(tmp_path: Path) -> None:
    baseline = tmp_path / "dead_links_baseline.txt"
    baseline.write_text(_NOTHING_BASELINED, encoding="utf-8")

    ok, note = _sandbox_wired(baseline)

    assert ok is True
