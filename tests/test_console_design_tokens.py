"""Guards over `web/src` as text, holding `DESIGN.md`'s token contract and the console's
honesty discipline without a frontend test runner.

`CLAUDE.md`'s console section rules this deliberately: classification with a wrong answer lives
in Python where pytest can hold it, formatting and rendering stay in the console. Every check
here is a read over source text, the same shape `tests/test_api_routes.py` already uses to hold
`web/src/api/client.ts` and `types.ts` to `app.py`'s own contract.

Each guard is two tests: one against the real tree, and one that builds a small `tmp_path`
fixture carrying a deliberate violation and asserts the same scanning function reports it. A
test that has never failed has never been shown to test anything, and a manual "introduce it,
watch it go red, revert" pass leaves no trace for the next session to trust -- the `tmp_path`
half stays in the suite so the proof is repeated on every run rather than performed once.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_WEB_SRC = _REPO_ROOT / "web" / "src"
_DESIGN_MD = _REPO_ROOT / "DESIGN.md"


def _require_web_src() -> None:
    if not _WEB_SRC.is_dir():
        pytest.skip("web/src is absent; this checkout carries no console")


def _iter_source_files(root: Path, suffixes: tuple[str, ...] = (".ts", ".tsx")) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix in suffixes)


def _line_at(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
# `(?<!:)` excludes a `//` immediately after `:` -- a URL scheme (`"https://..."`,
# `"http://..."`) -- from starting a comment. Without it, a real violation sitting later on the
# same line as a URL string is blanked along with the "comment" this regex wrongly opens there:
# `test_the_stripper_does_not_swallow_code_after_a_url_style_double_slash` below proves it.
_LINE_COMMENT = re.compile(r"(?<!:)//[^\n]*")


def _read_stripped(path: Path) -> str:
    """A file's text with `/* */` and `//` comments blanked out, newlines kept.

    Every guard below reads Tailwind class strings and JS literals, not prose -- and this
    codebase's own doc comments describe the very patterns being banned or permitted (a hover
    fill's `transition`, a chart's `oklch(...)`, a token's `rgba()`) in sentences that are not
    code. Scanning raw text flags the sentence along with the violation; blanking comments first
    keeps line numbers intact (a block comment is replaced by an equal count of newlines) while
    removing the one source of false positives every assertion here would otherwise share.

    This is a regex over text, not a parser, so it does not know a string literal from a real
    comment -- `_LINE_COMMENT`'s `(?<!:)` closes the one such gap this file has needed in
    practice (a URL's `//` swallowing the rest of its line as a false comment); it is not a
    guarantee against every string that happens to contain `/*` or `//`.
    """
    text = path.read_text(encoding="utf-8")
    text = _BLOCK_COMMENT.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    return _LINE_COMMENT.sub("", text)


def _require_examined(files: list[Path], where: Path) -> None:
    """A guard that iterates zero files cannot tell "clean" from "looked in the wrong place" --
    `_iter_source_files` returns `[]` just as readily for a directory that no longer exists under
    this name as for one that genuinely holds no source file, and `assert not violations` cannot
    tell the two apart on its own. Call this before that assertion so a renamed or deleted
    directory fails here, by name, instead of reporting the guard it starved as clean.
    """
    assert files, f"examined 0 files under {where} -- does this directory still exist under this name?"


# -- reading the token contract out of DESIGN.md, rather than hardcoding its numbers here ------


def _design_md_text() -> str:
    if not _DESIGN_MD.is_file():
        pytest.skip("DESIGN.md is absent; this checkout carries no token contract")
    return _DESIGN_MD.read_text(encoding="utf-8")


def _spacing_tokens() -> dict[str, int]:
    text = _design_md_text()
    tokens = {name: int(px) for name, px in re.findall(r"\| `--spacing-(\w+)` \| (\d+)px \|", text)}
    assert tokens, "DESIGN.md's Space table no longer matches this regex -- update it here too"
    return tokens


def _sanctioned_spacing_exceptions() -> set[int]:
    # Line-wrapped in the source file, so whitespace is normalised before matching rather than
    # anchoring to one physical line.
    flat = re.sub(r"\s+", " ", _design_md_text())
    frame = re.search(r"frame stays at \*\*(\d+)px\*\*", flat)
    gap = re.search(r"gap moves to \*\*(\d+)px\*\*", flat)
    assert frame and gap, "DESIGN.md no longer names its two sanctioned spacing exceptions"
    return {int(frame.group(1)), int(gap.group(1))}


def _banned_spacing_pixel_values() -> dict[int, str]:
    exceptions = _sanctioned_spacing_exceptions()
    return {px: name for name, px in _spacing_tokens().items() if px not in exceptions}


# -- assertion 1: no raw spacing utility duplicating a token's own pixel value, in features/ ----

_SPACING_PREFIXES = (
    "gap-x", "gap-y", "gap", "space-x", "space-y",
    "px", "py", "pt", "pb", "pl", "pr", "p",
    "mx", "my", "mt", "mb", "ml", "mr", "m",
)
_RAW_SPACING = re.compile(r"(?<![\w-])(?:" + "|".join(_SPACING_PREFIXES) + r")-(\d+)(?![\w-])")


def _spacing_violations(root: Path, banned: dict[int, str]) -> list[str]:
    violations = []
    for path in _iter_source_files(root):
        text = _read_stripped(path)
        for match in _RAW_SPACING.finditer(text):
            px = int(match.group(1)) * 4
            token = banned.get(px)
            if token is None:
                continue
            violations.append(
                f"{path}:{_line_at(text, match.start())} spells {px}px raw as "
                f"`{match.group(0)}`; `--spacing-{token}` already names this value"
            )
    return violations


def test_no_raw_spacing_value_duplicates_a_design_token_inside_features():
    _require_web_src()
    root = _WEB_SRC / "features"
    _require_examined(_iter_source_files(root), root)
    violations = _spacing_violations(root, _banned_spacing_pixel_values())
    assert not violations, "\n".join(violations)


def test_the_spacing_guard_rejects_a_raw_duplicate_of_a_named_token(tmp_path: Path) -> None:
    (tmp_path / "widget.tsx").write_text('<div className="gap-2 flex" />\n', encoding="utf-8")

    violations = _spacing_violations(tmp_path, {8: "row"})

    assert violations and "gap-2" in violations[0]


def test_the_stripper_does_not_swallow_code_after_a_url_style_double_slash(tmp_path: Path) -> None:
    # `_LINE_COMMENT`'s naive `//[^\n]*`, before `(?<!:)` was added, treated the `//` inside
    # `"https://..."` as a comment start and blanked everything after it on the same line --
    # including `gap-2`, a real violation, sitting later on that exact line. That is a violation
    # escaping because the stripper mistook code for a comment, not because it read a real one.
    (tmp_path / "link.tsx").write_text(
        'const href = "https://example.com"; const bad = <div className="gap-2 flex" />\n',
        encoding="utf-8",
    )

    violations = _spacing_violations(tmp_path, {8: "row"})

    assert violations and "gap-2" in violations[0]


def test_require_examined_fails_loudly_on_a_directory_that_is_not_there(tmp_path: Path) -> None:
    # The other half of the same defect: a renamed or deleted directory makes `_iter_source_files`
    # return `[]`, which every guard above would otherwise read as "nothing to complain about"
    # rather than "never looked". `_require_examined` is what turns that silence into a failure.
    missing = tmp_path / "features"

    with pytest.raises(AssertionError, match="examined 0 files"):
        _require_examined(_iter_source_files(missing), missing)


def test_the_spacing_guard_permits_the_two_sanctioned_exceptions(tmp_path: Path) -> None:
    # `gap-8` (32px) and `px-6` (24px) are the page-frame and between-panel-gap exceptions
    # DESIGN.md names; a banned set that has already excluded them must not flag either.
    (tmp_path / "page.tsx").write_text('<div className="gap-8 px-6" />\n', encoding="utf-8")

    violations = _spacing_violations(tmp_path, _banned_spacing_pixel_values())

    assert not violations


# -- assertion 2: no keyframes or animation shorthand outside a loading indicator --------------

_KEYFRAME_OR_ANIMATION = re.compile(r"@keyframes\b|\banimate-[\w-]+\b|\banimation\s*:")


def _keyframe_violations(root: Path) -> list[str]:
    violations = []
    for path in _iter_source_files(root):
        text = _read_stripped(path)
        for match in _KEYFRAME_OR_ANIMATION.finditer(text):
            violations.append(f"{path}:{_line_at(text, match.start())}: {match.group(0)!r}")
    return violations


def test_no_keyframes_or_animation_shorthand_under_features_or_layouts():
    _require_web_src()
    features_root = _WEB_SRC / "features"
    layouts_root = _WEB_SRC / "layouts"
    # Checked separately, not on the combined file count: one renamed directory must not hide
    # behind the other still having files, or this guard is starved over exactly the half nobody
    # noticed moved.
    _require_examined(_iter_source_files(features_root), features_root)
    _require_examined(_iter_source_files(layouts_root), layouts_root)
    violations = _keyframe_violations(features_root) + _keyframe_violations(layouts_root)
    assert not violations, (
        "every keyframe measured across four references is an overlay entering or leaving, or "
        "something loading -- a loading indicator belongs in components/ui/, never in a feature "
        "screen or a layout:\n" + "\n".join(violations)
    )


def test_the_keyframe_guard_rejects_an_animate_utility_in_a_feature_screen(tmp_path: Path) -> None:
    (tmp_path / "fleet-page.tsx").write_text(
        '<div className="animate-pulse" />\n', encoding="utf-8"
    )

    violations = _keyframe_violations(tmp_path)

    assert violations and "animate-pulse" in violations[0]


def test_index_css_declares_no_keyframes_beyond_its_recorded_baseline():
    # The baseline is zero as of this guard landing: no `@keyframes` exists in `index.css`
    # today. A loading indicator's spinner keyframe, when it is built, is a deliberate change to
    # this number rather than something this count should wave through silently.
    _require_web_src()
    text = (_WEB_SRC / "index.css").read_text(encoding="utf-8")
    assert text.count("@keyframes") == 0, (
        "index.css now declares a @keyframes block; if this is the sanctioned loading "
        "indicator, raise the recorded baseline here deliberately rather than deleting the check"
    )


# -- assertion 3: nothing transitions geometry anywhere (opacity is not geometry) ---------------

_GEOMETRY_TRANSITION = re.compile(
    r"(?<![\w-])(?:transition-all|transition-transform|transition-shadow|transition)(?![\w=-])"
)


def _geometry_transition_violations(root: Path) -> list[str]:
    violations = []
    for path in _iter_source_files(root):
        text = _read_stripped(path)
        for match in _GEOMETRY_TRANSITION.finditer(text):
            violations.append(f"{path}:{_line_at(text, match.start())}: {match.group(0)!r}")
    return violations


def test_nothing_transitions_geometry_anywhere():
    _require_web_src()
    _require_examined(_iter_source_files(_WEB_SRC), _WEB_SRC)
    violations = _geometry_transition_violations(_WEB_SRC)
    assert not violations, (
        "a sanctioned fade is not a geometry change, so opacity is not banned here -- transform, "
        "translate, scale and box-shadow are what a claim about motion is made of, and "
        "`transition`/`transition-all` reach all of them. `transition-colors` (and other named "
        "properties outside this list) stay permitted:\n" + "\n".join(violations)
    )


def test_the_geometry_guard_rejects_transition_all(tmp_path: Path) -> None:
    (tmp_path / "control.tsx").write_text(
        '<button className="transition-all hover:opacity-80" />\n', encoding="utf-8"
    )

    violations = _geometry_transition_violations(tmp_path)

    assert violations and "transition-all" in violations[0]


def test_the_geometry_guard_permits_colour_transitions_and_the_framer_prop(tmp_path: Path) -> None:
    # `transition-colors` is the sanctioned Tailwind spelling; `transition={{ ... }}` is the
    # framer-motion prop `lib/motion.ts` drives for the three deliberate exceptions DESIGN.md's
    # Motion section names (ErrorSurface, the changed-under-poll wash, the paged table settling
    # into height) -- an unrelated mechanism this guard must not confuse with a Tailwind class.
    (tmp_path / "row.tsx").write_text(
        'const a = <tr className="transition-colors" />\n'
        "const b = <motion.div transition={{ duration: 0.2 }} />\n",
        encoding="utf-8",
    )

    violations = _geometry_transition_violations(tmp_path)

    assert not violations


# -- assertion 4: no row-level de-emphasis -------------------------------------------------------

_DEEMPHASIZABLE_TAGS = (
    "TableRow", "TableCell", "TableHead",
    "Card", "CardHeader", "CardContent", "CardFooter", "CardTitle",
    "tr", "td", "th",
)
_ROW_OPACITY = re.compile(
    r"<(?:" + "|".join(_DEEMPHASIZABLE_TAGS) + r")\b"
    r"(?:(?!<)[\s\S]){0,300}?"
    r"\bopacity-(?:\[[^\]]+\]|0|[1-9]\d?)\b"
)


def _row_deemphasis_violations(root: Path) -> list[str]:
    violations = []
    for path in _iter_source_files(root):
        text = _read_stripped(path)
        for match in _ROW_OPACITY.finditer(text):
            violations.append(f"{path}:{_line_at(text, match.start())}")
    return violations


def test_no_row_level_de_emphasis():
    _require_web_src()
    _require_examined(_iter_source_files(_WEB_SRC), _WEB_SRC)
    violations = _row_deemphasis_violations(_WEB_SRC)
    assert not violations, (
        "a whole row, cell or card rendered at reduced opacity is a verdict with no text beside "
        "it and no way for a reader to learn what produced it -- if a row matters less, the "
        "column that makes it so says so in words:\n" + "\n".join(violations)
    )


def test_the_row_deemphasis_guard_rejects_opacity_on_a_table_row(tmp_path: Path) -> None:
    (tmp_path / "runs-table.tsx").write_text(
        '<TableRow className="opacity-50">\n  <TableCell>abandoned</TableCell>\n</TableRow>\n',
        encoding="utf-8",
    )

    violations = _row_deemphasis_violations(tmp_path)

    assert violations


def test_the_row_deemphasis_guard_permits_a_disabled_controls_opacity(tmp_path: Path) -> None:
    # `disabled:opacity-50` on a button or input is not a row -- it is the existing, sanctioned
    # affordance for a control that cannot be activated, and it must not be swept up by a guard
    # aimed at rows, cells and cards.
    (tmp_path / "button.tsx").write_text(
        'const Button = () => <button className="disabled:opacity-50" />\n', encoding="utf-8"
    )

    violations = _row_deemphasis_violations(tmp_path)

    assert not violations


# -- assertion 5: the absence glyph is rendered in one place ------------------------------------
#
# `lib/format.ts` returns `string | null` and `<Formatted>` in `components/status.tsx` is the one
# place a null becomes ink, so absence is `--color-ink-muted` everywhere. A call site that reaches
# for the `ABSENT` constant itself paints the same glyph at whatever colour surrounds it -- which
# is what `binding-surface-page.tsx`'s own `joinOrAbsent` did, in full `--color-ink`, months after
# that module's docstring recorded the regression as closed. A docstring did not hold it; this does.

_ABSENT_CONSTANT = re.compile(r"(?<![\w-])ABSENT(?![\w-])")
# The two files that are allowed to name it: the one that declares it, and the one that renders it.
_ABSENT_OWNERS = ("format.ts", "status.tsx")


def _absence_glyph_violations(root: Path) -> list[str]:
    violations = []
    for path in _iter_source_files(root):
        if path.name in _ABSENT_OWNERS:
            continue
        text = _read_stripped(path)
        for match in _ABSENT_CONSTANT.finditer(text):
            violations.append(f"{path}:{_line_at(text, match.start())}")
    return violations


def test_only_the_formatter_and_its_renderer_name_the_absence_glyph():
    _require_web_src()
    _require_examined(_iter_source_files(_WEB_SRC), _WEB_SRC)
    violations = _absence_glyph_violations(_WEB_SRC)
    assert not violations, (
        "DESIGN.md: one glyph, one appearance. Return `string | null` from the formatter and "
        "render it through `<Formatted>`, which is the only thing that knows what colour an "
        "absence is:\n" + "\n".join(violations)
    )


def test_the_absence_guard_rejects_a_helper_returning_the_glyph_as_a_string(tmp_path: Path) -> None:
    (tmp_path / "surface-page.tsx").write_text(
        "function joinOrAbsent(values: string[]): string {\n"
        "  return values.length === 0 ? ABSENT : values.join(', ')\n"
        "}\n",
        encoding="utf-8",
    )

    violations = _absence_glyph_violations(tmp_path)

    assert violations


def test_the_absence_guard_permits_the_two_files_that_own_the_glyph(tmp_path: Path) -> None:
    (tmp_path / "format.ts").write_text('export const ABSENT = "—"\n', encoding="utf-8")
    (tmp_path / "status.tsx").write_text(
        'import { ABSENT } from "@/lib/format"\n', encoding="utf-8"
    )

    violations = _absence_glyph_violations(tmp_path)

    assert not violations


# -- assertion 6: no colour literal outside index.css --------------------------------------------

_HEX_LITERAL = re.compile(
    r"(?<![&\w])#[0-9a-fA-F]{8}\b|(?<![&\w])#[0-9a-fA-F]{6}\b|(?<![&\w])#[0-9a-fA-F]{3,4}\b"
)
_COLOUR_FUNCTIONS = ("rgb", "rgba", "hsl", "hsla", "oklch", "oklab", "lab", "lch")
_COLOUR_FUNCTION_CALL = re.compile(r"\b(?:" + "|".join(_COLOUR_FUNCTIONS) + r")\(")


def _colour_literal_violations(root: Path) -> list[str]:
    violations = []
    for path in _iter_source_files(root, suffixes=(".ts", ".tsx", ".css")):
        if path.name == "index.css":
            continue
        text = _read_stripped(path)
        for pattern in (_HEX_LITERAL, _COLOUR_FUNCTION_CALL):
            for match in pattern.finditer(text):
                violations.append(f"{path}:{_line_at(text, match.start())}: {match.group(0)!r}")
    return violations


def test_no_colour_literal_outside_index_css():
    _require_web_src()
    _require_examined(_iter_source_files(_WEB_SRC, suffixes=(".ts", ".tsx", ".css")), _WEB_SRC)
    violations = _colour_literal_violations(_WEB_SRC)
    assert not violations, (
        "every colour DESIGN.md governs lives in index.css as a named token; a literal anywhere "
        "else is invented and untracked -- give it a name in index.css and read it from there, "
        "the way components/charts/echart.tsx resolves every other chart colour through "
        "getComputedStyle rather than hardcoding one:\n" + "\n".join(violations)
    )


def test_the_colour_literal_guard_rejects_a_hardcoded_hex(tmp_path: Path) -> None:
    (tmp_path / "corpus-chart.tsx").write_text(
        'function ink() { return "#ffffff" }\n', encoding="utf-8"
    )

    violations = _colour_literal_violations(tmp_path)

    assert violations and "#ffffff" in violations[0]


def test_the_colour_literal_guard_ignores_index_css_and_an_html_entity(tmp_path: Path) -> None:
    (tmp_path / "index.css").write_text(
        "@theme static { --color-brand: oklch(0.775 0.113 265); }\n", encoding="utf-8"
    )
    (tmp_path / "codebase-page.tsx").write_text(
        "<code>GET /api/vendors/&#123;vendor_id&#125;</code>\n", encoding="utf-8"
    )

    violations = _colour_literal_violations(tmp_path)

    assert not violations


def test_the_colour_literal_guard_permits_colour_mix_composed_from_tokens(tmp_path: Path) -> None:
    # `color-mix(in oklch, var(--color-primary), var(--color-foreground) 15%)` composes two
    # already-declared tokens; it introduces no new colour and DESIGN.md's own Elevation section
    # relies on this exact mechanism for a button's hover fill. It must not be flagged.
    (tmp_path / "button.tsx").write_text(
        'const c = "bg-[color-mix(in_oklch,var(--color-primary),var(--color-foreground)_15%)]"\n',
        encoding="utf-8",
    )

    violations = _colour_literal_violations(tmp_path)

    assert not violations


# -- assertion 6: no arbitrary font size beneath the ramp's floor --------------------------------
#
# Both guards below landed with the 2026-08-06 conformance measurement
# (`docs/superpowers/reports/2026-08-06-console-conformance.md`), which read every visible
# element on all nine routes through `getComputedStyle` and found the rendered census already
# inside both limits: no size under 12px anywhere, and no weight above 600 anywhere. They exist
# to keep it that way, because both limits are the kind that regress under pressure rather than
# by mistake -- a crowded table wants a smaller step and a heading that will not stand out wants
# a heavier one, and each is one class away.


def _text_size_floor_px() -> float:
    """The floor from DESIGN.md's Type table, rather than a 12 written here.

    The row is the one the table itself marks as the floor; reading the number off that mark
    means a decision to move the floor moves this guard with it, and a decision to remove the
    mark fails here loudly instead of silently freezing an old number.
    """
    match = re.search(
        r"\|\s*`--text-\w+`\s*\|\s*(\d+)px\s*\|[^|]*\|[^|]*\|[^|]*\|[^|\n]*\*\*The floor\.\*\*",
        _design_md_text(),
    )
    assert match, "DESIGN.md's Type table no longer marks a step as **The floor.**"
    return float(match.group(1))


# `text-[…]` is the only spelling that reaches a size off the ramp: the six named utilities and
# Tailwind's stock steps all resolve to declared values. A bracket carrying anything but a length
# is a different utility (`text-[color-mix(…)]`, `text-[--var]`) and is not this guard's business.
_ARBITRARY_TEXT_SIZE = re.compile(r"(?<![\w-])text-\[(\d*\.?\d+)(px|rem)\]")


def _undersized_text_violations(root: Path, floor_px: float) -> list[str]:
    violations = []
    for path in _iter_source_files(root, suffixes=(".ts", ".tsx", ".css")):
        text = _read_stripped(path)
        for match in _ARBITRARY_TEXT_SIZE.finditer(text):
            px = float(match.group(1)) * (16 if match.group(2) == "rem" else 1)
            if px >= floor_px:
                continue
            violations.append(
                f"{path}:{_line_at(text, match.start())} renders {px:g}px as "
                f"`{match.group(0)}`, beneath DESIGN.md's {floor_px:g}px floor"
            )
    return violations


def test_nothing_renders_beneath_the_text_size_floor():
    _require_web_src()
    _require_examined(_iter_source_files(_WEB_SRC, suffixes=(".ts", ".tsx", ".css")), _WEB_SRC)
    violations = _undersized_text_violations(_WEB_SRC, _text_size_floor_px())
    assert not violations, (
        "12px is a floor, not the small end of a range, and being on DESIGN.md's ramp does not "
        "exempt a value from it -- a table that has run out of width takes fewer columns or a "
        "narrower one, never a smaller step:\n" + "\n".join(violations)
    )


def test_the_text_size_guard_rejects_a_ten_pixel_step(tmp_path: Path) -> None:
    (tmp_path / "crowded-table.tsx").write_text(
        '<td className="text-[10px] font-mono">{row.file}</td>\n', encoding="utf-8"
    )

    violations = _undersized_text_violations(tmp_path, 12)

    assert violations and "text-[10px]" in violations[0]


def test_the_text_size_guard_reads_a_rem_spelling_too(tmp_path: Path) -> None:
    # `text-[0.625rem]` is 10px under a 16px root and would otherwise walk straight past a guard
    # that only knew the `px` spelling.
    (tmp_path / "badge.tsx").write_text(
        '<span className="text-[0.625rem]">static</span>\n', encoding="utf-8"
    )

    violations = _undersized_text_violations(tmp_path, 12)

    assert violations and "10px" in violations[0]


def test_the_text_size_guard_permits_a_size_at_or_above_the_floor(tmp_path: Path) -> None:
    (tmp_path / "ok.tsx").write_text(
        '<p className="text-[12px]">at the floor</p>\n'
        '<p className="text-[1rem]">above it</p>\n'
        '<p className="text-[color-mix(in_oklch,var(--color-ink),transparent)]">not a size</p>\n',
        encoding="utf-8",
    )

    violations = _undersized_text_violations(tmp_path, 12)

    assert not violations


# -- assertion 7: no font weight above the ramp's heaviest step ----------------------------------


_TAILWIND_WEIGHTS = {
    "thin": 100, "extralight": 200, "light": 300, "normal": 400, "medium": 500,
    "semibold": 600, "bold": 700, "extrabold": 800, "black": 900,
}
_FONT_WEIGHT = re.compile(
    r"(?<![\w-])font-(?:(" + "|".join(_TAILWIND_WEIGHTS) + r")|\[(\d{3})\])(?![\w-])"
)


def _weight_ceiling() -> int:
    """The heaviest weight DESIGN.md's Type table declares.

    Section 8 of `2026-08-05-sync-console-architecture.md` measured two weights and no 600 on
    three landing pages; section 15.1 overturned that against a control plane and against this
    console's own 2.67:1 type range, where weight does work size cannot. So the ceiling belongs
    to the token contract, and this reads it from there rather than restating either number.
    """
    weights = [int(w) for w in re.findall(r"\| `--text-\w+` \|[^|]*\|[^|]*\| (\d{3}) \|", _design_md_text())]
    assert weights, "DESIGN.md's Type table no longer declares a numeric weight on any step"
    return max(weights)


def _heavy_weight_violations(root: Path, ceiling: int) -> list[str]:
    violations = []
    for path in _iter_source_files(root, suffixes=(".ts", ".tsx", ".css")):
        text = _read_stripped(path)
        for match in _FONT_WEIGHT.finditer(text):
            weight = _TAILWIND_WEIGHTS[match.group(1)] if match.group(1) else int(match.group(2))
            if weight <= ceiling:
                continue
            violations.append(
                f"{path}:{_line_at(text, match.start())} asks for weight {weight} as "
                f"`{match.group(0)}`; DESIGN.md's heaviest step is {ceiling}"
            )
    return violations


def test_no_font_weight_above_the_heaviest_declared_step():
    _require_web_src()
    _require_examined(_iter_source_files(_WEB_SRC, suffixes=(".ts", ".tsx", ".css")), _WEB_SRC)
    violations = _heavy_weight_violations(_WEB_SRC, _weight_ceiling())
    assert not violations, (
        "weight is a channel this console spends deliberately, and it has exactly three values "
        "to spend: 400, 500 and the 600 its four heading steps carry. A fourth is a heading role "
        "argued in DESIGN.md, not a class:\n" + "\n".join(violations)
    )


def test_the_weight_guard_rejects_font_bold(tmp_path: Path) -> None:
    (tmp_path / "headline.tsx").write_text(
        '<h1 className="text-page font-bold">Fleet</h1>\n', encoding="utf-8"
    )

    violations = _heavy_weight_violations(tmp_path, 600)

    assert violations and "700" in violations[0]


def test_the_weight_guard_rejects_a_bracketed_weight(tmp_path: Path) -> None:
    (tmp_path / "figure.tsx").write_text(
        '<span className="text-figure font-[800]">4,000</span>\n', encoding="utf-8"
    )

    violations = _heavy_weight_violations(tmp_path, 600)

    assert violations and "800" in violations[0]


def test_the_weight_guard_permits_the_three_weights_the_console_spends(tmp_path: Path) -> None:
    (tmp_path / "row.tsx").write_text(
        '<th className="font-medium">Rung</th>\n'
        '<h2 className="font-semibold">Errors and incidents</h2>\n'
        '<p className="font-normal">prose</p>\n',
        encoding="utf-8",
    )

    violations = _heavy_weight_violations(tmp_path, 600)

    assert not violations


# -- assertion 8: the focus ring ships at full strength ------------------------------------------
#
# The focus ring is the only signal a keyboard user gets on a control whose variant sets its own
# border colour, and an alpha modifier on it is invisible in the source and decisive on screen:
# `ring-ring/50` composites the brand hue to `rgb(84, 101, 139)` over the card, which measures
# 3.08:1 against 3:1 -- a floor cleared by 0.08 while `DESIGN.md` published 8.69. A ring colour is
# a token, not a wash: it is declared once, argued in that file, and rendered at the strength it
# was argued at.
#
# Scoped to the focus ring rather than to every `ring-*/n`: the `aria-invalid:` rings on the same
# elements are washed the same way and are the same class of defect, but they are also spelled
# against `destructive`, which is not a token `DESIGN.md` declares at all. That is a bigger
# question than this guard, and B108 carries it.

# `\]?` catches the `has-[…:focus-visible]:ring-…` form `input-group.tsx` uses, where the ring
# is applied to a wrapper by a descendant's focus rather than by the element's own.
_RING_WITH_ALPHA = re.compile(r"(?<![\w-])focus(?:-visible)?\]?:ring-([a-z-]+)/(\d{1,3})(?![\w-])")


def _ring_alpha_violations(root: Path) -> list[str]:
    violations = []
    for path in _iter_source_files(root):
        text = _read_stripped(path)
        for match in _RING_WITH_ALPHA.finditer(text):
            violations.append(
                f"{path}:{_line_at(text, match.start())} renders the focus ring as "
                f"`{match.group(0)}`; {match.group(2)}% of a colour is not the colour "
                "DESIGN.md's contrast figure was computed for"
            )
    return violations


def test_no_focus_ring_is_washed_by_an_alpha_modifier():
    _require_web_src()
    _require_examined(_iter_source_files(_WEB_SRC), _WEB_SRC)
    violations = _ring_alpha_violations(_WEB_SRC)
    assert not violations, (
        "a focus ring at partial strength is a contrast figure nobody computed and nobody can "
        "read off the class name -- render the token, and argue the token in DESIGN.md:\n"
        + "\n".join(violations)
    )


def test_the_ring_guard_rejects_a_half_strength_ring(tmp_path: Path) -> None:
    (tmp_path / "button.tsx").write_text(
        '<button className="focus-visible:ring-3 focus-visible:ring-ring/50" />\n',
        encoding="utf-8",
    )

    violations = _ring_alpha_violations(tmp_path)

    assert violations and "ring-ring/50" in violations[0]


def test_the_ring_guard_permits_a_full_strength_ring_and_a_ring_width(tmp_path: Path) -> None:
    # `ring-3` is a width, not a colour, and `ring-0` removes the ring entirely -- neither is a
    # colour washed by an alpha modifier, and a guard that swept them up would be deleted.
    (tmp_path / "input.tsx").write_text(
        '<input className="focus-visible:ring-3 focus-visible:ring-ring" />\n'
        '<span className="focus-visible:ring-0" />\n',
        encoding="utf-8",
    )

    violations = _ring_alpha_violations(tmp_path)

    assert not violations


# -- assertion 9: a dialog's heading lives inside the dialog -------------------------------------
#
# Radix unmounts `DialogContent` while the dialog is closed. A `DialogTitle` outside it is not
# unmounted, so it sits in the document permanently -- and on every route of this console the
# first heading in the document was `h2 "Jump to a destination"`, the command palette's title,
# ahead of the page's own `h1`. The heading tree is the only machine-readable assertion of which
# level of the dependency graph a reader is on, and it was asserting a closed overlay.
#
# This is a text guard over the JSX, not a walk of the rendered document: nothing in this
# repository can run React. It holds the structural cause rather than the rendered symptom, which
# is the part a future edit can reintroduce.

_DIALOG_CONTENT_OPEN = re.compile(r"<DialogContent\b")
_DIALOG_HEADING = re.compile(r"<(DialogHeader|DialogTitle|DialogDescription)\b")


def _dialog_heading_violations(root: Path) -> list[str]:
    violations = []
    for path in _iter_source_files(root):
        text = _read_stripped(path)
        opens = [m.start() for m in _DIALOG_CONTENT_OPEN.finditer(text)]
        if not opens:
            continue
        first_content = min(opens)
        for match in _DIALOG_HEADING.finditer(text):
            if match.start() < first_content:
                violations.append(
                    f"{path}:{_line_at(text, match.start())} renders <{match.group(1)}> before "
                    "<DialogContent>; Radix unmounts the content and leaves this in the document"
                )
    return violations


def test_no_dialog_heading_sits_outside_its_dialog_content():
    _require_web_src()
    _require_examined(_iter_source_files(_WEB_SRC), _WEB_SRC)
    violations = _dialog_heading_violations(_WEB_SRC)
    assert not violations, (
        "a heading that outlives its closed dialog is the first heading on every route, ahead "
        "of the page's own h1:\n" + "\n".join(violations)
    )


def test_the_dialog_heading_guard_rejects_a_header_hoisted_above_the_content(tmp_path: Path) -> None:
    (tmp_path / "command.tsx").write_text(
        "<Dialog>\n"
        '  <DialogHeader className="sr-only">\n'
        "    <DialogTitle>{title}</DialogTitle>\n"
        "  </DialogHeader>\n"
        "  <DialogContent>{children}</DialogContent>\n"
        "</Dialog>\n",
        encoding="utf-8",
    )

    violations = _dialog_heading_violations(tmp_path)

    assert violations and "DialogHeader" in violations[0]


def test_the_dialog_heading_guard_permits_a_header_inside_the_content(tmp_path: Path) -> None:
    (tmp_path / "command.tsx").write_text(
        "<Dialog>\n"
        "  <DialogContent>\n"
        '    <DialogHeader className="sr-only">\n'
        "      <DialogTitle>{title}</DialogTitle>\n"
        "    </DialogHeader>\n"
        "    {children}\n"
        "  </DialogContent>\n"
        "</Dialog>\n",
        encoding="utf-8",
    )

    violations = _dialog_heading_violations(tmp_path)

    assert not violations
