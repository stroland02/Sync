"""The README may not offer an install path the manifest cannot deliver.

**Re-anchored by `CI-W451`, 2026-08-18.** The first form of this guard pinned `private: true` as
the reason the one-command form could not work; the manifest is publishable now, under the bin's
own name, so `private` stopped being the fact that decides what the README may print. What
decides it now is a fact no offline test can read — whether `npm publish` has actually run — so
the guard pins the next best thing: **the README's two statements about the one-command form may
not disagree with each other.** While the page says the package is not published, it must not
print the command a visitor would copy, because that command 404s — or worse, resolves to
whatever a squatter registered under the name in the meantime. Publishing is a two-line README
edit, and this guard is what insists both lines change together.

**This is a drift guard, not a spell-checker.** The manifest and the README are two files nobody
edits together: publishing the package, or renaming it, all change what the first section of the
README promises, and none of them touches the README. The failure is silent in the direction that
matters — the page keeps offering a command that stopped working, or keeps apologising for one
that now works.

Nothing here reaches the network. A test that asked the registry would be measuring somebody
else's uptime, and `.claude/rules/test-discipline.md` rules that out. What is checkable offline is
whether the repository's own statements agree.
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


def _readme_says_it_is_not_published() -> bool:
    return any(phrase in _readme().lower() for phrase in _SAYS_IT_IS_NOT_PUBLISHED)


def test_the_readme_states_the_publication_fact_one_way_or_the_other():
    """The page must say whether the one-command form works, as a claim rather than a hedge.

    The guard below reads the README's own statement to decide what the page may print. A page
    that stopped stating the fact at all would make that guard pass vacuously while telling a
    visitor nothing -- the same defect as a check that cannot fail.
    """
    assert _readme_says_it_is_not_published() or "npx sync-up" in _readme(), (
        "the README neither says the package is unpublished nor prints the command -- state the "
        "fact one way or the other, because a visitor cannot measure the registry from a README"
    )


def test_an_unpublished_command_is_not_printed_for_a_visitor_to_run():
    """A command that cannot resolve must not appear as a command.

    This began as *the README must say the command does not work*, which was too weak: a
    paragraph underneath does not help a reader who copied the first line of a code block. An
    unpublished name is also a squattable one, so the printed command would either 404 or
    install whatever somebody else registered under it in the meantime.

    Publishing retires this by one edit: remove the not-published sentence, print the command,
    and both tests flip together.
    """
    if not _readme_says_it_is_not_published():
        return

    manifest = _manifest()
    assert f"npx {manifest['name']}" not in _readme(), (
        f"the README prints `npx {manifest['name']}` as something to run while also saying the "
        "package is not published -- one of the two statements is wrong, and a visitor acts on "
        "the code block"
    )


def test_the_readme_does_not_call_every_path_supported_while_one_is_unavailable():
    """The line that was actually wrong.

    *Three ways in, and all three are supported* is a stronger claim than any of the three
    sections beneath it, and it was the sentence a reader would take away.
    """
    if not _readme_says_it_is_not_published():
        return

    assert "all three are supported" not in _readme().lower(), (
        "one of the three ways in is not published, so calling all three supported is a claim "
        "the page itself contradicts two paragraphs later"
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
