"""The outcome ramp is five distinguishable colours, and stays that way.

`DESIGN.md`'s "The outcome ramp" carries the argument; this holds the values to it. Two
properties, and the second is the one that matters.

**Every step clears the 5.05:1 contrast floor** on every surface, like any text-bearing ink.

**No two steps look alike.** This is what the file exists for. A chart band is a few hundred
pixels of flat fill, and two bands a reader cannot tell apart are worth nothing however correct
each is alone -- which is exactly how `CI-W619` shipped, two near-identical oranges for failures
and successes. The ruling's own first draft had `opened` and `retried` at **CIE76 dE 2.1**, the
same defect one screen over, and only measuring found it.
"""

from __future__ import annotations

import math
import re
from itertools import combinations
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_INDEX_CSS = _REPO_ROOT / "web" / "src" / "index.css"

#: Ordered by how well the attempt ended. The order is the ramp's meaning, not a preference.
_STEPS = ("opened", "retried", "in-flight", "reported", "abandoned")

#: The surfaces a band is drawn on.
_SURFACES = ("#131413", "#181a19", "#1e201f")

_CONTRAST_FLOOR = 5.05

#: Below this, two flat fills read as the same colour at chart scale.
_DIFFERENCE_FLOOR = 20.0


def _require_console() -> None:
    if not _INDEX_CSS.is_file():
        pytest.skip("web/src/index.css is absent; this checkout carries no console")


def _rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _linear(channel: float) -> float:
    channel /= 255
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def _luminance(value: str) -> float:
    r, g, b = (_linear(c) for c in _rgb(value))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a: str, b: str) -> float:
    la, lb = _luminance(a), _luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _lab(value: str) -> tuple[float, float, float]:
    r, g, b = (_linear(c) for c in _rgb(value))
    x = 0.4124 * r + 0.3576 * g + 0.1805 * b
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = 0.0193 * r + 0.1192 * g + 0.9505 * b

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    fx, fy, fz = f(x / 0.95047), f(y / 1.0), f(z / 1.08883)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def _difference(a: str, b: str) -> float:
    """CIE76. Coarser than CIEDE2000 and sufficient here -- the question is whether two large
    flat fills are the same colour, not whether two adjacent swatches match."""
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(_lab(a), _lab(b))))


def _declared() -> dict[str, str]:
    css = _INDEX_CSS.read_text(encoding="utf-8")
    found: dict[str, str] = {}
    for step in _STEPS:
        match = re.search(rf"--color-outcome-{step}:\s*(#[0-9a-fA-F]{{6}});", css)
        if match:
            found[step] = match.group(1)
    return found


def test_every_step_of_the_ramp_is_declared():
    _require_console()

    assert sorted(_declared()) == sorted(_STEPS)


def test_every_step_clears_the_contrast_floor_on_every_surface():
    _require_console()

    below = [
        f"{step} on {surface}: {_contrast(value, surface):.2f}"
        for step, value in _declared().items()
        for surface in _SURFACES
        if _contrast(value, surface) < _CONTRAST_FLOOR
    ]

    assert below == []


def test_no_two_steps_look_alike():
    _require_console()
    declared = _declared()

    too_close = [
        f"{a} vs {b}: dE {_difference(declared[a], declared[b]):.1f}"
        for a, b in combinations(_STEPS, 2)
        if _difference(declared[a], declared[b]) < _DIFFERENCE_FLOOR
    ]

    assert too_close == [], (
        "two outcome bands read as the same colour, which is the defect CI-W619 fixed one "
        "screen over:\n  " + "\n  ".join(too_close)
    )


def test_the_difference_guard_sees_the_ruling_first_draft() -> None:
    """The pair that made this file necessary: `opened` against the proposed `retried`."""
    assert _difference("#3ecf8e", "#45cd8e") < _DIFFERENCE_FLOOR


def test_the_difference_guard_passes_two_colours_a_reader_can_tell_apart() -> None:
    assert _difference("#3ecf8e", "#fa8880") > _DIFFERENCE_FLOOR
