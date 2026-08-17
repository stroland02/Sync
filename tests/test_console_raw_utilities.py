"""Raw Tailwind utilities inside ``web/src/features`` — a shrinking baseline.

``DESIGN.md`` records the decision: four spacing tokens, two radius tokens, seven
type steps, and colour only through tokens. A raw utility inside ``features/``
duplicates one of them under a different name, or asserts a judgement colour the
surface rules forbid. The baseline file holds the violations that existed when the
guard landed; it only ever shrinks. A pair not in the baseline fails immediately.

``rounded-full`` is exempt for the same reason ``gap-8`` is: a circle is a shape,
not a point on the radius scale, and neither ``rounded-control`` nor
``rounded-surface`` can express one. ``node-sequence.tsx``'s status markers are
circular by design, so the raw spelling there is not a token gap to close.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_FEATURES = _REPO_ROOT / "web" / "src" / "features"
_BASELINE = Path(__file__).resolve().parent / "console_raw_utilities_baseline.txt"

# Each alternative is a raw spelling with a token answer. ``gap-8`` is exempt by
# DESIGN.md's own text; icon ``size-*`` is geometry, not spacing, and is not hunted.
# ``rounded-full`` is exempt the same way: a circle is a shape the radius scale does
# not express, so it is left out of the alternation entirely rather than matched and
# tolerated.
_RAW = re.compile(
    r"(?<![-\w:])("
    r"text-(?:xs|sm|base|lg|xl|2xl|3xl|4xl)"          # type steps exist for these
    r"|rounded(?:-(?:sm|md|lg|xl|2xl))?(?![-\w])"  # radius-control / radius-surface
    r"|(?:p|px|py|m|mx|my|gap)-(?:0\.5|1|1\.5|2|2\.5|3|4|5|6)(?![-\w.])"
    r"|(?:bg|text|border)-(?:emerald|amber|red|green|blue|yellow|orange|rose|sky|"
    r"slate|zinc|gray|stone|neutral)-\d{2,3}(?:/\d{1,3})?"
    r")"
)


# Comments are not code, and the first form of this guard did not know the difference. It scanned
# whole file text, so a docstring *quoting* a class name tripped it -- and the fix a reader reaches
# for is to reword the docstring, which is what happened: `evidence-bundle.tsx`'s account of what
# M7-W179 changed had to stop naming the class it changed. A guard whose first measured effect is
# making a file's history less accurate is a broken guard.
#
# Comments are stripped rather than the scan being narrowed to `className=` attributes, which was
# the other candidate and is worse: a class string held in a variable -- `change-units-table.tsx`
# builds one per run outcome as a `tone` field -- never appears inside a class attribute, so that
# narrowing would have stopped hunting exactly the colours this guard exists to catch.
_COMMENT = re.compile(r"/\*.*?\*/|//[^\n]*", re.DOTALL)


def _code_only(text: str) -> str:
    return _COMMENT.sub(" ", text)


def _current_pairs() -> set[str]:
    pairs: set[str] = set()
    for path in sorted(_FEATURES.rglob("*.tsx")):
        text = path.read_text(encoding="utf-8")
        for match in _RAW.finditer(_code_only(text)):
            rel = path.relative_to(_REPO_ROOT / "web").as_posix()
            pairs.add(f"{rel}\t{match.group(1)}")
    return pairs


def test_features_add_no_raw_utilities() -> None:
    assert _FEATURES.is_dir(), "features directory moved; update the guard"
    baseline = set(
        line
        for line in _BASELINE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    new = _current_pairs() - baseline
    assert not new, (
        "Raw Tailwind utilities not in the baseline (use the token; "
        "DESIGN.md is the authority):\n" + "\n".join(sorted(new))
    )
