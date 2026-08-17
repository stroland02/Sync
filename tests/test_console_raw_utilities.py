"""Raw Tailwind utilities inside ``web/src/features`` — a shrinking baseline.

``DESIGN.md`` records the decision: four spacing tokens, two radius tokens, seven
type steps, and colour only through tokens. A raw utility inside ``features/``
duplicates one of them under a different name, or asserts a judgement colour the
surface rules forbid. The baseline file holds the violations that existed when the
guard landed; it only ever shrinks. A pair not in the baseline fails immediately.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_FEATURES = _REPO_ROOT / "web" / "src" / "features"
_BASELINE = Path(__file__).resolve().parent / "console_raw_utilities_baseline.txt"

# Each alternative is a raw spelling with a token answer. ``gap-8`` is exempt by
# DESIGN.md's own text; icon ``size-*`` is geometry, not spacing, and is not hunted.
_RAW = re.compile(
    r"(?<![-\w:])("
    r"text-(?:xs|sm|base|lg|xl|2xl|3xl|4xl)"          # type steps exist for these
    r"|rounded(?:-(?:sm|md|lg|xl|2xl|full))?(?![-\w])"  # radius-control / radius-surface
    r"|(?:p|px|py|m|mx|my|gap)-(?:0\.5|1|1\.5|2|2\.5|3|4|5|6)(?![-\w.])"
    r"|(?:bg|text|border)-(?:emerald|amber|red|green|blue|yellow|orange|rose|sky|"
    r"slate|zinc|gray|stone|neutral)-\d{2,3}(?:/\d{1,3})?"
    r")"
)


def _current_pairs() -> set[str]:
    pairs: set[str] = set()
    for path in sorted(_FEATURES.rglob("*.tsx")):
        text = path.read_text(encoding="utf-8")
        for match in _RAW.finditer(text):
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
