"""The README may not offer an install path the manifest cannot deliver.

**Measured 2026-08-18.** `npx @superloglabs/sync` is the first of three ways in, and the README
called all three supported. The registry answers 404 for that name, and `package.json` carries
`"private": true` — which does not merely mean *nobody has published it yet*, it means `npm
publish` refuses. So the opening line of the Wednesday demo could not work for anybody who is not
already in this checkout, and the page a stranger lands on said it would.

The README had hedged honestly before that — *what has not been verified is the published path* —
and a hedge is the right thing to write before measuring and the wrong thing to leave after.

**This is a drift guard, not a spell-checker.** The manifest and the README are two files nobody
edits together: publishing the package, or renaming it, or flipping `private`, all change what the
first section of the README promises, and none of them touches the README. The failure is silent
in the direction that matters — the page keeps offering a command that stopped working, or keeps
apologising for one that now works.

Nothing here reaches the network. A test that asked the registry would be measuring somebody
else's uptime, and `.claude/rules/test-discipline.md` rules that out. What is checkable offline is
whether the repository's own two statements agree.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = REPO_ROOT / "package.json"
README = REPO_ROOT / "README.md"

# Phrases that STATE the command is unavailable. Any one discharges the obligation; the list
# exists so a rewrite is not forced to keep an exact sentence.
#
# **Every one of these is a claim rather than a condition, and that is the point.** The first
# version of this guard accepted `does not resolve` and passed against the sentence *if it does
# not resolve, use the checkout below* -- a hedge, which is what the README already said and
# what measuring was supposed to replace. A guard that accepts the hedge it was written to
# retire is a guard that cannot fail.
_SAYS_IT_IS_NOT_PUBLISHED = (
    "is not published",
    "has not been published",
    "is not on npm",
    "cannot be published",
)


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _readme() -> str:
    return README.read_text(encoding="utf-8")


def test_the_manifest_is_the_reason_the_command_cannot_work():
    """Pins the fact the guard below depends on, so a change to it is deliberate.

    If somebody publishes the package they must remove `private`, and this test failing is how
    they are told the README section is now wrong in the other direction.
    """
    assert _manifest()["private"] is True, (
        "package.json is no longer private, so the one-command form may now be publishable -- "
        "re-measure `npm view @superloglabs/sync` and update the README section, which currently "
        "tells a reader the command does not resolve"
    )


def test_an_unpublishable_command_is_not_printed_for_a_visitor_to_run(): 
    """A command that cannot resolve must not appear as a command.

    This began as *the README must say the command does not work*, which was too weak. The
    manifest names an npm scope this project does not own -- a competitor's -- so the printed
    command would either 404 or install somebody else's package, and a paragraph underneath
    explaining that does not help a reader who copied the first line of a code block.

    The README describes the one-command form and prints no command for it. That is the
    honest shape while there is nothing to run.
    """
    manifest = _manifest()
    if not manifest.get("private"):
        return

    assert f"npx {manifest['name']}" not in _readme(), (
        f"the README prints `npx {manifest['name']}` as something to run, and that package "
        "cannot be published from this manifest -- describe the one-command form without "
        "printing a command that resolves to nothing, or to somebody else"
    )

def test_the_readme_does_not_call_every_path_supported_while_one_is_unavailable():
    """The line that was actually wrong.

    *Three ways in, and all three are supported* is a stronger claim than any of the three
    sections beneath it, and it was the sentence a reader would take away.
    """
    if not _manifest().get("private"):
        return

    assert "all three are supported" not in _readme().lower(), (
        "one of the three ways in cannot be published, so calling all three supported is a claim "
        "the manifest contradicts"
    )


def test_the_bin_the_manifest_declares_exists():
    """`npx` runs a file. A manifest naming one that is not shipped fails at the worst moment."""
    manifest = _manifest()
    for command, relative in manifest["bin"].items():
        assert (REPO_ROOT / relative).is_file(), f"bin {command!r} points at a missing {relative}"
        shipped = {entry.rstrip("/") for entry in manifest["files"]}
        assert relative.split("/")[0] in shipped or relative in shipped, (
            f"bin {command!r} is at {relative}, which `files` does not ship -- the package would "
            "publish without the program it declares"
        )
