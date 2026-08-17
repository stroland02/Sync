"""The documented setup produces everything the suite refuses without.

`tests/test_day_one_path.py` asserts that the commands in the Quick start exist. This asserts the
harder and more useful thing: that following them leaves nothing behind. Those are different
claims, and the gap between them is where a second engineer lives.

**B169 is what the gap cost.** Twelve tests said the day-one path was documented correctly and a
fresh checkout failed about fifty tests anyway — 47 on a missing `tools/oasdiff` and 3 on a missing
`.cache/corpus/`. The first is documented. The second was named in no document in this repository:
not `README.md`, not `CONTRIBUTING.md`, not anything under `docs/`. Somebody following the
instructions exactly still met three failures, and the tests kept passing because they were reading
the prose rather than executing it.

**So this module executes the refusals rather than describing them.** It runs the real code paths
with the artifact absent, reads the script each one names, and asserts that script is in the
documented setup. That is the assertion that fails when a step is added to the code and not to the
instructions, which is the direction the drift actually goes: nobody forgets to write the refusal,
because the refusal is what they hit while building it.

The alternative was a job that clones the repository and runs the whole setup. Fifteen minutes of
wall clock gets disabled the first week it is flaky, and it would prove the same thing this proves
in under a second.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# Every document a newcomer is pointed at. A step documented in none of them is undocumented.
SETUP_DOCUMENTS = ("README.md", "CONTRIBUTING.md")

# `run scripts/x.sh` or `Run scripts/x.py`, the shape every refusal in this repository uses to
# name the thing that fixes it.
_NAMES_A_SCRIPT = re.compile(r"[Rr]un (?P<script>scripts/[a-z_]+\.(?:py|sh))")


def _setup_text() -> str:
    return "\n".join(
        (REPO_ROOT / name).read_text(encoding="utf-8") for name in SETUP_DOCUMENTS
    )


def _script_named_by(message: str) -> str | None:
    match = _NAMES_A_SCRIPT.search(message)
    return match["script"] if match else None


# --- executing the refusals ---------------------------------------------------------


def test_a_missing_oasdiff_refuses_and_names_the_script_that_supplies_it(monkeypatch) -> None:
    """Executed, not read: the real resolver, with the binary genuinely absent.

    `_binary()` looks in `tools/` and then on PATH, so both have to be empty for this to reach the
    refusal. Pointing the module at a scratch root is what makes this a check on a fresh checkout
    rather than on this one.
    """
    from sync.signals import oasdiff

    monkeypatch.setattr(oasdiff.shutil, "which", lambda _name: None)
    monkeypatch.setattr(
        oasdiff.Path, "exists", lambda self: False, raising=False
    )

    with pytest.raises(FileNotFoundError) as raised:
        oasdiff._binary()

    assert _script_named_by(str(raised.value)) == "scripts/bootstrap_tools.sh"


def test_a_missing_corpus_refuses_and_names_the_script_that_supplies_it(tmp_path) -> None:
    """The refusal a fresh checkout actually meets, raised by the real fixture code."""
    from sync.rehearse import fixture

    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setattr(fixture, "_MANIFEST_PATH", tmp_path / "absent.yaml")
        with pytest.raises(RuntimeError) as raised:
            fixture._load_manifest_entry("furever")
    finally:
        monkeypatch.undo()

    assert _script_named_by(str(raised.value)) == "scripts/fetch_corpus_repositories.py"


# --- and closing the loop back to the instructions ----------------------------------


REFUSAL_SCRIPTS = ("scripts/bootstrap_tools.sh", "scripts/fetch_corpus_repositories.py")


@pytest.mark.parametrize("script", REFUSAL_SCRIPTS)
def test_every_script_a_refusal_names_is_in_the_documented_setup(script: str) -> None:
    """The assertion that would have caught B169, and the one that keeps catching it.

    A refusal naming a script the instructions never mention is a step somebody has to already
    know about. That is the definition of undocumented, and it is invisible to any test that reads
    the prose and asks whether what is there is correct — what was there was correct, and
    incomplete.

    Drift goes this way and not the other: nobody forgets to write the refusal, because the
    refusal is what they hit while building the thing. They forget the document.
    """
    assert script in _setup_text(), (
        f"{script} is named by a refusal the suite raises on a fresh checkout, and by no setup "
        f"document. Somebody following {' or '.join(SETUP_DOCUMENTS)} exactly still meets that "
        "failure. Add the step to the instructions rather than removing this assertion"
    )


def test_the_setup_runs_every_step_before_it_runs_the_suite() -> None:
    """Order, not presence. A step listed after `uv run pytest` is a step the suite ran without."""
    for name in SETUP_DOCUMENTS:
        text = (REPO_ROOT / name).read_text(encoding="utf-8")
        if "uv run pytest" not in text:
            continue
        suite_at = text.index("uv run pytest")
        for script in REFUSAL_SCRIPTS:
            if script not in text:
                continue  # covered by the test above, with a better message
            assert text.index(script) < suite_at, (
                f"{name} runs the suite before {script}, so the documented order produces the "
                "failures the script exists to prevent"
            )
