"""The honesty sentences on screen are the product, and until now nothing held them.

`.claude/rules/console-surface.md` protects twenty-four sentences and says plainly how: *"Nothing
tests prose, the sentences sit in ad-hoc containers, and a screen gets shorter every time somebody
tidies it."* The mechanism was a reviewer re-reading their own diff. That was adequate while one
session edited one screen at a time. It is not adequate for M7, which rewrites roughly 7,900 lines
of presentation — a rebuild would delete the product's argument silently and nobody would notice
for weeks.

**This guard is deliberately not file-pinned.** It asserts a distinguishing fragment of each
sentence still appears *somewhere* under `web/src`. A sentence may move between files, be re-placed
in a new composition, or be restyled — all of which M7 requires. Deleting it, or shortening it past
the fragment, fails. That is exactly the boundary the rule draws: restyle yes, delete no.

The catalogue in `docs/superpowers/plans/2026-08-05-sync-console-architecture.md:102-207` is the
authority for *which* sentences these are. Its file citations are stale — four of the files it names
no longer exist, because the sentences moved when the hierarchy was reconciled — which is itself the
argument for asserting on content rather than on location.

**Fragments are chosen to survive reflow.** Each is short enough to sit on one source line at this
repository's wrap width, because a fragment spanning a line break matches nothing and would fail on
a reformat rather than on a deletion — a guard that fires on `prettier` is a guard somebody deletes.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

WEB_SRC = Path(__file__).resolve().parents[1] / "web" / "src"

# (fragment, what the sentence is for). The second element is the failure message: a worker who
# breaks this needs to know what they removed, not which string stopped matching.
PROTECTED: tuple[tuple[str, str], ...] = (
    (
        "we could not check",
        "the refusal to score — a scalar collapses 'we could not check' onto the same axis as "
        "'we checked and it passed'",
    ),
    (
        "staleness, not liveness",
        "a checkpoint row is the only evidence a run exists, so 'last checkpoint' is staleness "
        "and this screen does not guess which silence means death",
    ),
    (
        "per checkpoint thread",
        "the runs table's grain — one row per checkpoint thread, not one per finding",
    ),
    (
        "counts once toward",
        "the corpus grain — a finding retried three times is three attempts and one finding",
    ),
    (
        "never indexed has no row",
        "absence is not zero — a repository configured but never indexed is indistinguishable "
        "from one nobody configured",
    ),
    (
        "nobody ever configured",
        "the same absence said again, in its longest form, on the repository screen",
    ),
    (
        "cannot tell the two apart",
        "the two-meanings sentences — never had a call site versus had one that was retracted",
    ),
    (
        "has no denominator",
        "a count is not a rate",
    ),
    (
        "deliberately not merged",
        "provenance at two levels — the per-row rung and the envelope's rung are different facts",
    ),
    (
        "null is a fact",
        "`bindingNullLabel` is required rather than defaulted, because null differs per route",
    ),
    (
        "never its hue",
        "the rung stays monochrome — colouring it would restate the confidence score this project "
        "rejected",
    ),
    (
        "no finding here to attribute",
        "the envelope's null meaning *none*, which is not the same as *mixed*",
    ),
    (
        "do not all rest on one rung",
        "the envelope's null meaning *mixed*, which is not the same as *none*",
    ),
    (
        "sideways scroll",
        "provenance rendered is not provenance visible — the rung column's position is a layout "
        "constraint, not a preference",
    ),
    (
        "still asking",
        "the kinds of nothing — a spinner that never resolves and a silent empty table are both "
        "the console refusing to say which one it is",
    ),
    (
        "vocabulary has changed",
        "the console admits when it is out of date with its own backend rather than rendering a "
        "blank or guessing",
    ),
    (
        "not a failure of the console",
        "an empty answer is an answer about the thing, not a failure of the screen showing it",
    ),
)


_IMPORT = re.compile(r"""(?:from|import)\s+["']([^"']+)["']""")


def _resolve(spec: str, importer: Path) -> Path | None:
    """Resolve one import specifier to a file under `web/src`, or `None` for a package."""
    if spec.startswith("@/"):
        base = WEB_SRC / spec[2:]
    elif spec.startswith("."):
        base = (importer.parent / spec).resolve()
    else:
        return None
    for candidate in (
        base.with_suffix(".ts"),
        base.with_suffix(".tsx"),
        base / "index.ts",
        base / "index.tsx",
    ):
        if candidate.is_file():
            return candidate
    return base if base.is_file() else None


def _modules_reachable_from_entry() -> set[Path]:
    """Every module the running console actually pulls in, walked from `main.tsx`.

    The guard this replaces searched every `.ts`/`.tsx` under `web/src`, which made it unable to
    fail in the two ways that have actually happened. It excluded `.test.ts` but not `.test.tsx`,
    so a sentence surviving only in one of twenty-five test files passed; and it counted modules no
    route mounts, so a sentence in an orphaned component passed while rendering nowhere. A test
    named `..._is_still_on_screen` has to mean the screen.
    """
    entry = WEB_SRC / "main.tsx"
    assert entry.is_file(), f"console entry {entry} is missing; this guard cannot walk the app"

    seen: set[Path] = set()
    queue = [entry]
    while queue:
        module = queue.pop()
        if module in seen:
            continue
        seen.add(module)
        for spec in _IMPORT.findall(module.read_text(encoding="utf-8")):
            target = _resolve(spec, module)
            if target is not None and target not in seen:
                queue.append(target)
    return seen


@pytest.mark.skipif(not WEB_SRC.is_dir(), reason="web/src is absent; this checkout carries no console")
@pytest.mark.parametrize("fragment,purpose", PROTECTED, ids=[f for f, _ in PROTECTED])
def test_a_protected_honesty_sentence_is_still_on_screen(fragment: str, purpose: str) -> None:
    """Each protected sentence still appears somewhere under `web/src`.

    Not asserted against a file. A sentence that moves is fine and M7 requires it; a sentence that
    disappears is the product losing an argument it makes on screen.
    """
    sources = sorted(_modules_reachable_from_entry())
    assert sources, "no console source found to search"

    holders = [
        path.relative_to(WEB_SRC).as_posix()
        for path in sources
        if fragment in path.read_text(encoding="utf-8")
    ]

    assert holders, (
        f"the protected sentence carrying {fragment!r} is gone from web/src.\n"
        f"It says: {purpose}.\n"
        "`.claude/rules/console-surface.md` permits restyling one of these and forbids deleting, "
        "shortening, collapsing behind a disclosure, or moving into a tooltip. If the wording "
        "genuinely improved, update the fragment here in the same commit and say why; if it was "
        "tidied away, put it back."
    )
