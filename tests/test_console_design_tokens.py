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
    """The page-layout pixel values DESIGN.md permits spelled raw, because no token names them.

    **One, as of M7-W160.** It was two: the 24px page frame and the 32px between-panel gap, both
    unnamed on the same grounds. The frame is now `--spacing-frame` at 40px, which moves it out of
    this set and *into* the banned list -- `p-10` in a feature screen now duplicates a token under a
    different name, which is exactly what this guard is for. That is the second half of the
    correction M7-W160 made: the frame was `px-6` spelled inline, so nothing could read it and no
    guard could check the ratio the design contract was arguing about.

    The sentence this reads moved with the M7-W170 substrate swap: it used to record the gap
    *moving* to 32px and now records it *staying* there, because the substrate did not touch the
    spacing scale. The pattern matches the standing form rather than the one-off announcement, so
    the next slice that leaves the gap alone does not have to keep a sentence in the past tense to
    keep this guard fed.
    """
    # Line-wrapped in the source file, so whitespace is normalised before matching rather than
    # anchoring to one physical line.
    flat = re.sub(r"\s+", " ", _design_md_text())
    gap = re.search(r"between-panel gap stays \*\*(\d+)px\*\*", flat)
    assert gap, "DESIGN.md no longer names the between-panel gap as a sanctioned raw value"
    return {int(gap.group(1))}


# -- the contract and the declaration cannot disagree without a test naming which one moved -----
#
# `DESIGN.md` publishes a value for every token; `index.css` declares them. Until M7-W170 nothing
# held the two vocabularies together, and a substrate swap is exactly the shape of change that
# breaks that quietly: a token renamed in one file and not the other leaves a published contrast
# figure describing a colour nothing resolves, or a value on screen no document argued for. Both
# directions fail here, by name.
#
# **Every theme family, not just colour.** `.claude/rules/console-surface.md` puts a new type step,
# a third elevation level and a fourth spacing value in the same category as a new colour -- each is
# a decision argued in `DESIGN.md`, never a value added elsewhere -- so scoping this to `--color-*`
# left twelve type steps declared and argued nowhere, which is the gap this covers.

_THEME_FAMILY = r"--(?:background-color|border-color|color|text|spacing|radius|shadow|font)-[\w-]+"
_THEME_DECLARATION = re.compile(r"^\s*(" + _THEME_FAMILY + r")\s*:", re.MULTILINE)
_CONTRACT_TOKEN = re.compile(r"`(" + _THEME_FAMILY + r")`")

# Tailwind spells a type step's line height, weight and tracking as `--text-page--line-height` and
# friends -- properties *of* a step rather than steps of their own, and already published as the
# columns of the row that names the step. Only the step itself is a token this guard holds.
_STEP_MODIFIER = re.compile(r".--")

_STOCK_KEY_SECTION = re.compile(
    r"^## Stock Tailwind keys this contract leaves alone$(.*?)(?=^## |\Z)",
    re.MULTILINE | re.DOTALL,
)
# The *first cell* of a row in that section's table, not any token the section mentions. Reading
# the whole section swept `--radius-control` and `--text-meta` into the exemption because the "why
# it stands" column names them -- which would have let a rename of either hide behind a paragraph
# that was only explaining something else.
_STOCK_KEY_ROW = re.compile(r"^\| `(" + _THEME_FAMILY + r")` \|", re.MULTILINE)


def _index_css_text() -> str:
    path = _WEB_SRC / "index.css"
    assert path.is_file(), f"{path} is gone -- the token declarations moved and this guard is blind"
    return path.read_text(encoding="utf-8")


def _declared_theme_tokens(text: str | None = None) -> set[str]:
    """Every theme custom property `index.css` declares, across all eight families.

    Anchored to the start of a line so a `var(--color-line)` sitting inside another token's value
    is not counted as a declaration of it -- `--shadow-flat` and the `@layer base` block both
    reference tokens they do not declare.
    """
    found = {
        name
        for name in _THEME_DECLARATION.findall(_index_css_text() if text is None else text)
        if not _STEP_MODIFIER.search(name[2:])
    }
    assert found, "no theme declaration found in index.css -- the parser or the file moved"
    return found


def _stock_tailwind_keys(text: str | None = None) -> set[str]:
    """The keys DESIGN.md names precisely to record that it leaves them at Tailwind's default.

    Read out of the document rather than hardcoded here, for the reason every threshold in this
    file is: an exemption that lives in the test is an exemption nobody reviewing the contract can
    see. Deleting the section fails loudly instead of quietly widening what may go undeclared.
    """
    section = _STOCK_KEY_SECTION.search(_design_md_text() if text is None else text)
    assert section, (
        "DESIGN.md no longer carries the stock-Tailwind-keys section. It is where a key named but "
        "deliberately not declared is argued; without it this guard cannot tell one from an "
        "undeclared token"
    )
    keys = set(_STOCK_KEY_ROW.findall(section.group(1)))
    assert keys, "the stock-Tailwind-keys section carries no table row naming a key"
    return keys


def _contracted_theme_tokens(text: str | None = None) -> set[str]:
    """Every theme token name DESIGN.md spells inside backticks, minus the stock-key exemptions."""
    found = {
        name
        for name in _CONTRACT_TOKEN.findall(_design_md_text() if text is None else text)
        if not _STEP_MODIFIER.search(name[2:])
    }
    assert found, "DESIGN.md names no theme token -- the contract or the parser moved"
    return found


def test_every_token_the_contract_names_is_declared():
    _require_web_src()
    missing = sorted(_contracted_theme_tokens() - _declared_theme_tokens() - _stock_tailwind_keys())
    assert not missing, (
        "DESIGN.md publishes a value for these tokens and index.css declares none of them, so the "
        "value describes something nothing on screen resolves. Declare the token, argue it in the "
        "stock-Tailwind-keys section, or stop naming it:\n" + "\n".join(missing)
    )


def test_every_token_declared_is_named_in_the_contract():
    _require_web_src()
    undocumented = sorted(_declared_theme_tokens() - _contracted_theme_tokens())
    assert not undocumented, (
        "index.css declares these and DESIGN.md argues for none of them. A colour, a type step, a "
        "spacing value or an elevation level that no document names is a value nobody chose and "
        "nobody measured -- give it a row in the table its job belongs to, with the "
        "arithmetic:\n" + "\n".join(undocumented)
    )


def test_the_vocabulary_guard_sees_a_token_declared_but_never_argued() -> None:
    declared = _declared_theme_tokens(
        "--color-ink: oklch(0.95 0 0);\n  --color-smuggled: #ff0000;\n  --text-fake: 99px;\n"
    )
    contracted = _contracted_theme_tokens("The ink is `--color-ink`.\n")

    assert sorted(declared - contracted) == ["--color-smuggled", "--text-fake"]


def test_the_vocabulary_guard_sees_a_token_argued_but_never_declared() -> None:
    declared = _declared_theme_tokens("--color-ink: oklch(0.95 0 0);\n")
    contracted = _contracted_theme_tokens("`--color-ink` and `--spacing-imaginary` are steps.\n")

    assert sorted(contracted - declared) == ["--spacing-imaginary"]


def test_the_vocabulary_guard_ignores_a_reference_inside_another_tokens_value() -> None:
    # `--shadow-flat: 0 0 0 1px var(--color-line)` mentions a token it does not declare. Counting
    # that as a declaration would make the guard pass on a file that declared nothing at all.
    declared = _declared_theme_tokens(
        "--color-line: oklch(0.95 0 0 / 7%);\n  --shadow-flat: 0 0 0 1px var(--color-nonexistent);\n"
    )

    assert declared == {"--color-line", "--shadow-flat"}


def test_the_vocabulary_guard_treats_a_line_height_as_part_of_its_step() -> None:
    # A step's line height, weight and tracking are the columns of the row that names it. Holding
    # them as tokens of their own would demand `--text-page--letter-spacing` appear in backticks,
    # which is a table cell, not a name anything spells.
    declared = _declared_theme_tokens(
        "--text-page: 1.375rem;\n  --text-page--line-height: 2rem;\n"
        "  --text-page--font-weight: 600;\n"
    )

    assert declared == {"--text-page"}


def test_the_stock_key_exemption_is_read_out_of_the_contract() -> None:
    keys = _stock_tailwind_keys(
        "## Stock Tailwind keys this contract leaves alone\n\n"
        "| `--text-xs` | 0.75rem | it is the floor |\n\n"
        "## Deliberately absent\n\n`--color-not-an-exemption` lives here.\n"
    )

    assert keys == {"--text-xs"}


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


def test_the_spacing_guard_permits_the_sanctioned_between_panel_gap(tmp_path: Path) -> None:
    # `gap-8` (32px) is the one page-layout value DESIGN.md still leaves unnamed; a banned set that
    # has already excluded it must not flag it.
    (tmp_path / "page.tsx").write_text('<div className="gap-8" />\n', encoding="utf-8")

    violations = _spacing_violations(tmp_path, _banned_spacing_pixel_values())

    assert not violations


def test_the_spacing_guard_now_flags_the_frame_spelled_raw(tmp_path: Path) -> None:
    # The frame stopped being an exception when it became `--spacing-frame`, so `p-10` in a feature
    # screen is a token duplicated under a different name -- the case this guard exists for, and one
    # it could not see while the frame was an unnamed 24px.
    (tmp_path / "page.tsx").write_text('<div className="p-10" />\n', encoding="utf-8")

    violations = _spacing_violations(tmp_path, _banned_spacing_pixel_values())

    assert violations and "--spacing-frame" in violations[0]


# -- assertion 2: no keyframes or animation shorthand outside a loading indicator --------------

# `(?!\s*false)` exempts the one spelling that serves this guard rather than breaking it.
# `echarts` animates on entry unless an option says otherwise, so `animation: false` is how a
# chart in `features/` obeys "nothing decorative running at rest" -- and without the exemption
# this guard banned the only line that could turn it off, which is why `corpus-chart.tsx` has
# never carried one. Nothing else is exempt: a duration, a variable, or any other value is a
# chart asking for motion and is still a violation.
_KEYFRAME_OR_ANIMATION = re.compile(
    r"@keyframes\b|\banimate-[\w-]+\b|\banimation\s*:(?!\s*false)"
)


def _keyframe_violations(root: Path, exclude_prefix: str | None = None) -> list[str]:
    violations = []
    for path in _iter_source_files(root):
        # `exclude_prefix` is relative to `root`, not to `_WEB_SRC` -- a caller scanning one
        # subdirectory (the keyframe guard below, one root at a time) and a caller scanning all
        # of `_WEB_SRC` (the geometry and text-size guards) both pass a prefix meaningful against
        # the `root` they themselves passed in.
        if exclude_prefix is not None and path.relative_to(root).as_posix().startswith(exclude_prefix):
            continue
        text = _read_stripped(path)
        for match in _KEYFRAME_OR_ANIMATION.finditer(text):
            violations.append(f"{path}:{_line_at(text, match.start())}: {match.group(0)!r}")
    return violations


# `components/ui/` is where a sanctioned spinner would live -- it is the shadcn catalog, and the
# references' one permitted keyframe is a loading indicator. Everything above it is ours.
_ANIMATION_FREE_ROOTS = ("features", "layouts", "components", "api", "lib")
# Only `components/` has a vendored subdirectory to exclude; the prefix is relative to that
# root's own `_WEB_SRC / name`, so it reads "ui/" here rather than "components/ui/".
_ANIMATION_EXCLUDE_PREFIX = {"components": "ui/"}

# The two vendored catalogs, as prefixes relative to `web/src`. `vendor/supabase/` is the carve-out
# in `.claude/rules/interface-originality.md`; `components/ui/` is the shadcn catalog the keyframe
# guard above already excludes by the same argument -- restyling a vendored file is out of scope
# for the task that copies it in, and a guard that fails on somebody else's defaults reports a
# decision nobody here made. Owner ruling, 2026-08-18, on three guards red on `main`.
#
# One tuple rather than a prefix repeated per guard: a fact written twice disagrees with itself,
# and the disagreement here would be a guard quietly covering less than its neighbour.
_VENDORED_PREFIXES = ("vendor/supabase/", "components/ui/")


def _is_vendored(path: Path, root: Path) -> bool:
    relative = path.relative_to(root).as_posix()
    return any(relative.startswith(prefix) for prefix in _VENDORED_PREFIXES)



def test_no_keyframes_or_animation_shorthand_outside_the_component_catalog():
    _require_web_src()
    # Checked per directory, not on a combined file count: one renamed directory must not hide
    # behind another still having files, or this guard is starved over exactly the half nobody
    # noticed moved.
    violations = []
    for name in _ANIMATION_FREE_ROOTS:
        root = _WEB_SRC / name
        _require_examined(_iter_source_files(root), root)
        # `components/ui/` is the catalog and is vendored; it is excluded by path rather than
        # by leaving `components/` unscanned, which is what let `components/` go unchecked
        # until M4.5-W143 -- the two framer-motion call sites the motion audit ruled on both
        # live there, one directory above the exclusion.
        violations += _keyframe_violations(root, exclude_prefix=_ANIMATION_EXCLUDE_PREFIX.get(name))
    assert not violations, (
        "every keyframe measured across four references is an overlay entering or leaving, or "
        "something loading -- a loading indicator belongs in components/ui/, never in a feature "
        "screen, a layout, or a component this project wrote:\n" + "\n".join(violations)
    )


def test_the_keyframe_guard_rejects_an_animate_utility_in_a_feature_screen(tmp_path: Path) -> None:
    (tmp_path / "fleet-page.tsx").write_text(
        '<div className="animate-pulse" />\n', encoding="utf-8"
    )

    violations = _keyframe_violations(tmp_path)

    assert violations and "animate-pulse" in violations[0]


def test_the_keyframe_guard_permits_switching_an_animation_off(tmp_path: Path) -> None:
    # `animation: false` is a chart declining the entry transition `echarts` would otherwise
    # give it. Banning it would mean a feature screen could not turn motion off, which inverts
    # what this guard is for.
    (tmp_path / "rung-composition-option.ts").write_text(
        "const option = { animation: false, series: [] }\n", encoding="utf-8"
    )

    violations = _keyframe_violations(tmp_path)

    assert not violations


def test_the_keyframe_guard_still_rejects_an_animation_that_is_switched_on(tmp_path: Path) -> None:
    # The other half, and the one that keeps the exemption honest: only the literal `false` is
    # waved through, so a chart asking for motion by any other spelling is still caught.
    (tmp_path / "chart.ts").write_text(
        "const a = { animation: true }\nconst b = { animation: 300 }\n", encoding="utf-8"
    )

    violations = _keyframe_violations(tmp_path)

    assert len(violations) == 2


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


def _geometry_transition_violations(root: Path, *, skip_vendored: bool = False) -> list[str]:
    violations = []
    for path in _iter_source_files(root):
        if skip_vendored and _is_vendored(path, root):
            continue
        text = _read_stripped(path)
        for match in _GEOMETRY_TRANSITION.finditer(text):
            violations.append(f"{path}:{_line_at(text, match.start())}: {match.group(0)!r}")
    return violations


def test_nothing_transitions_geometry_anywhere():
    _require_web_src()
    _require_examined(_iter_source_files(_WEB_SRC), _WEB_SRC)
    # Both vendored catalogs are excluded by path -- see `_VENDORED_PREFIXES`. Restyling a
    # vendored file is out of scope for the task that copies it in.
    violations = _geometry_transition_violations(_WEB_SRC, skip_vendored=True)
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
        # A test may name the constant. The defect this guard exists to stop is a *component*
        # rendering a hard-coded glyph instead of going through `<Formatted>` — a second appearance
        # a reader could see. A test importing `ABSENT` to assert the one appearance is checking
        # that rule rather than breaking it, and importing it is strictly better than a test
        # hard-coding the glyph, which is what forbidding the import pushes people toward.
        #
        # This is deliberately NOT the shape of exemption `M14-W363` removed from the honesty-sentence
        # guard. There, excluding tests let a sentence deleted from the product pass because it
        # survived in a test file — the exclusion hid a real defect. Here the guard still reads every
        # non-test source file, and no test can put a second glyph in front of a reader.
        if ".test." in path.name:
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
        "@theme static { --color-brand: oklch(0.76 0.15 159); }\n", encoding="utf-8"
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


# `text-[…]` is the only spelling that reaches a size off the ramp: the seven named role steps and
# the substrate's own `text-xs` … `text-9xl` all resolve to declared values. A bracket carrying anything but a length
# is a different utility (`text-[color-mix(…)]`, `text-[--var]`) and is not this guard's business.
_ARBITRARY_TEXT_SIZE = re.compile(r"(?<![\w-])text-\[(\d*\.?\d+)(px|rem)\]")


def _undersized_text_violations(
    root: Path, floor_px: float, exclude_prefix: str | None = None
) -> list[str]:
    violations = []
    for path in _iter_source_files(root, suffixes=(".ts", ".tsx", ".css")):
        if exclude_prefix is not None and path.relative_to(root).as_posix().startswith(exclude_prefix):
            continue
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
    # See the identical exclusion in test_nothing_transitions_geometry_anywhere: vendored,
    # not restyled here.
    violations = _undersized_text_violations(
        _WEB_SRC, _text_size_floor_px(), exclude_prefix="vendor/supabase/"
    )
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
# `ring-ring/50` composited the previous brand hue to `rgb(84, 101, 139)` over the card, measuring
# 3.08:1 against a 3:1 floor -- cleared by 0.08, while `DESIGN.md` published 8.69. A ring colour is
# a token, not a wash: it is declared once, argued in that file, and rendered at the strength it
# was argued at.
#
# The M7-W170 substrate swap made this guard matter more rather than less. Upstream declares
# `--ring` as the brand at 55% alpha, so the wash this catches at a call site is the shape the
# vendored catalog would otherwise have arrived carrying; `DESIGN.md` names the full-strength
# declaration as a deviation and publishes both figures.
#
# Scoped to the focus ring rather than to every `ring-*/n`: the `aria-invalid:` rings on the same
# elements are washed the same way and are the same class of defect, but they are also spelled
# against `destructive`, which is not a token `DESIGN.md` declares at all. That is a bigger
# question than this guard, and B108 carries it.

# `\]?` catches the `has-[…:focus-visible]:ring-…` form `input-group.tsx` uses, where the ring
# is applied to a wrapper by a descendant's focus rather than by the element's own.
_RING_WITH_ALPHA = re.compile(r"(?<![\w-])focus(?:-visible)?\]?:ring-([a-z-]+)/(\d{1,3})(?![\w-])")


def _ring_alpha_violations(root: Path, *, skip_vendored: bool = False) -> list[str]:
    violations = []
    for path in _iter_source_files(root):
        if skip_vendored and _is_vendored(path, root):
            continue
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
    # `ring-ring/50` is shadcn's own default and arrives with the catalog; excluded by path for
    # the same reason the geometry guard excludes it.
    violations = _ring_alpha_violations(_WEB_SRC, skip_vendored=True)
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
# -- assertion 8: the table's rows measure what DESIGN.md says they measure ----------------------
#
# `DESIGN.md`'s Row height section states two heights as arithmetic over values it declares
# elsewhere in the same file -- a header at `row-lg`, a body row at `row-md` derived from
# `--text-body`'s line box plus `--spacing-row` top and bottom. Both sentences were false for as
# long as they existed: `table.tsx` spelled `py-2.5`, so a header measured 36px against a declared
# 40 and a single-line body row measured 40px against a declared 36 -- inverted, not merely off.
# Measured in Chrome at 1440x900 across seven tables on the Fleet screen before and after
# M4.5-W142: header 36.5 -> 40.0, single-line body row 40.5 -> 36.0.
#
# This guard is the arithmetic itself rather than a string match, because a string match would
# pass on any spelling somebody liked. It resolves the classes `table.tsx` actually sets against
# the type, spacing and row-height tables in `DESIGN.md` and asserts they multiply out to the
# declared height, so it reddens if either side moves alone.


def _type_line_heights() -> dict[str, int]:
    """`--text-*` step -> line-height px, from DESIGN.md's Type table."""
    steps = {
        name: int(lh)
        for name, lh in re.findall(r"\| `--text-(\w+)` \| \d+px \| (\d+)px \|", _design_md_text())
    }
    assert steps, "DESIGN.md's Type table no longer matches this regex -- update it here too"
    return steps


def _row_heights() -> dict[str, int]:
    """`row-*` step -> px, from DESIGN.md's Row height table."""
    steps = {
        name: int(px)
        for name, px in re.findall(r"\| `row-(\w+)` \| (\d+)px \(`h-\d+`\) \|", _design_md_text())
    }
    assert steps, "DESIGN.md's Row height table no longer matches this regex -- update it here too"
    return steps


def _table_primitive_text() -> str:
    path = _WEB_SRC / "components" / "ui" / "table.tsx"
    assert path.is_file(), f"{path} is gone -- the table primitive moved and this guard is blind"
    return _read_stripped(path)


def _cell_classes(slot: str, text: str | None = None) -> str:
    """The Tailwind class string `table.tsx` sets on one `data-slot`.

    Anchored on the slot rather than on the function name so a rename of `TableHead` does not
    silently starve this guard: the slot is what the rest of the tree selects on. `text` is the
    source to read, defaulting to the real primitive -- the tests below pass the class string
    that was there before this change so the arithmetic is proven to reject it.
    """
    if text is None:
        text = _table_primitive_text()
    match = re.search(
        r'data-slot="' + re.escape(slot) + r'"\s*\n\s*className=\{cn\(\s*\n?\s*"([^"]+)"',
        text,
    )
    assert match, f'table.tsx no longer sets a cn("...") class string on data-slot="{slot}"'
    return match.group(1)


def _vertical_padding_px(classes: str, spacing: dict[str, int]) -> int:
    """The rendered `py-*` in px, whether it is spelled as a token or as a raw Tailwind step."""
    match = re.search(r"(?<![\w-])py-([\w.]+)(?![\w-])", classes)
    assert match, f"no `py-*` in {classes[:60]!r} -- the padding moved and this guard is blind"
    value = match.group(1)
    if value in spacing:
        return spacing[value]
    return int(float(value) * 4)


def _declared_height_px(classes: str) -> int | None:
    match = re.search(r"(?<![\w-])h-(\d+)(?![\w.-])", classes)
    return int(match.group(1)) * 4 if match else None


def _text_step(classes: str, steps: dict[str, int]) -> str:
    found = [name for name in steps if re.search(r"(?<![\w-])text-" + name + r"(?![\w-])", classes)]
    assert len(found) == 1, f"expected exactly one `--text-*` step in {classes[:60]!r}, got {found}"
    return found[0]


def _body_row_height_px(classes: str) -> int:
    spacing, steps = _spacing_tokens(), _type_line_heights()
    return steps[_text_step(classes, steps)] + 2 * _vertical_padding_px(classes, spacing)


def test_a_body_row_measures_the_row_height_design_md_derives_for_it():
    _require_web_src()
    classes = _cell_classes("table-cell")
    rendered = _body_row_height_px(classes)
    declared = _row_heights()["md"]

    assert rendered == declared, (
        f"a single-line table cell renders {rendered}px against the {declared}px DESIGN.md "
        f"declares for `row-md`. Either the cell's padding or that table is wrong, and the "
        f"contract says the height is chosen first and the padding derived from it"
    )


def test_a_header_row_declares_the_row_height_design_md_assigns_it():
    _require_web_src()
    declared_by_class = _declared_height_px(_cell_classes("table-head"))
    declared_by_contract = _row_heights()["lg"]

    assert declared_by_class == declared_by_contract, (
        f"the header cell declares {declared_by_class}px against the {declared_by_contract}px "
        f"DESIGN.md assigns `row-lg`, whose own row names `TableHead` as where it is already "
        f"rendered. Padding alone cannot reach it -- 12px of `--text-meta` on a 16px line box "
        f"plus the 8px row token is 32px -- so the height is set and the padding derived"
    )


# The two class strings below are verbatim what `table.tsx` carried before M4.5-W142, so these are
# the guards refusing the real defect rather than a fixture invented to be refusable.
_OLD_CELL = 'data-slot="table-cell"\n      className={cn(\n        "px-row py-2.5 text-body align-middle",\n'
_OLD_HEAD = 'data-slot="table-head"\n      className={cn(\n        "px-row py-2.5 text-meta font-medium",\n'


def test_the_row_height_arithmetic_rejects_the_fractional_padding_that_was_there() -> None:
    # 10px of padding on `--text-body`'s 20px line box is 40 -- `row-lg`'s number, in `row-md`'s
    # slot, which is the inversion the measurement found.
    assert _body_row_height_px(_cell_classes("table-cell", _OLD_CELL)) == 40
    assert _row_heights()["md"] == 36


def test_the_header_guard_rejects_a_header_that_sets_no_height() -> None:
    # Without `h-10` the header's height is whatever its padding happens to make it, which is how
    # it came to render 36px while the contract assigned it 40.
    assert _declared_height_px(_cell_classes("table-head", _OLD_HEAD)) is None
    assert _row_heights()["lg"] == 40


# -- assertion 9: two working ink levels for text, and the third is not a text class ------------
#
# Section 8 of `2026-08-05-sync-console-architecture.md` measures two ink levels plus one accent
# and never three. The console holds it with `--color-ink` and `--color-ink-muted`;
# `--color-ink-secondary` has exactly one consumer, `corpus-chart.tsx`'s legend `textStyle`, which
# renders into a canvas and is not a DOM ink level at all. Two call sites reached for it as a
# class and made a third -- `run-outcome.tsx` on the two screens carrying the densest evidence,
# and `filters.tsx` on the active-filter strip, where it also made the value *dimmer* than the
# ink-muted label naming it. Both measured 3 levels before M4.5-W142 and 2 after.
#
# The ban is on the class, not on the token: a chart resolving `--color-ink-secondary` through
# `getComputedStyle` is the sanctioned consumer and must keep working.

_INK_SECONDARY_CLASS = re.compile(r"(?<![\w-])(?:text|decoration|placeholder|caret)-ink-secondary(?![\w-])")


def _third_ink_violations(root: Path) -> list[str]:
    violations = []
    for path in _iter_source_files(root, suffixes=(".ts", ".tsx")):
        text = _read_stripped(path)
        for match in _INK_SECONDARY_CLASS.finditer(text):
            violations.append(f"{path}:{_line_at(text, match.start())}: {match.group(0)!r}")
    return violations


def test_no_component_paints_dom_text_with_the_third_ink_level():
    _require_web_src()
    _require_examined(_iter_source_files(_WEB_SRC), _WEB_SRC)
    violations = _third_ink_violations(_WEB_SRC)
    assert not violations, (
        "the console's two working ink levels are `ink` and `ink-muted`; `ink-secondary` is the "
        "chart legend's step and reaching for it as a text class puts a third grey on screen "
        "where a reader cannot tell recessive prose from a deliberate second voice. Recessive "
        "prose takes `text-ink-muted`, a value takes `text-ink`:\n" + "\n".join(violations)
    )


def test_the_third_ink_guard_rejects_a_text_class(tmp_path: Path) -> None:
    (tmp_path / "run-outcome.tsx").write_text(
        '<div className="text-body text-ink-secondary">{children}</div>\n', encoding="utf-8"
    )

    violations = _third_ink_violations(tmp_path)

    assert violations and "text-ink-secondary" in violations[0]


def test_the_third_ink_guard_permits_the_chart_resolving_the_token(tmp_path: Path) -> None:
    # `echart.tsx` maps a token name to a chart option and `corpus-chart.tsx` spends it on legend
    # text inside a canvas. Neither is a DOM ink level and neither may be swept up here.
    (tmp_path / "echart.tsx").write_text(
        'const TOKEN_PROPERTIES = { inkSecondary: "--color-ink-secondary" }\n'
        "const legend = { textStyle: { color: tokens.inkSecondary } }\n",
        encoding="utf-8",
    )

    violations = _third_ink_violations(tmp_path)

    assert not violations


# -- assertion 10: framer-motion has a registry, and the registry and the tree agree -------------
#
# `DESIGN.md`'s Motion section and `lib/motion.ts`'s own docstring both already said that motion
# outside the declared usages is forbidden. Neither could stop a fourth `import { motion } from
# "framer-motion"` arriving, because prose does not fail a build. M4.5-W143 turned the list into an
# array in `lib/motion.ts` and this reads it, so the fact has one copy and a violation has a line
# number.
#
# **Both directions matter.** An unlisted importer is the obvious failure. A stale entry is the one
# that bites later: M4.5-W143 deleted the paginator's `layout` animation after measuring that it had
# never once run, and an entry left behind would have been a standing permission for the next person
# to animate a paginator, with a comment claiming somebody had thought about it.

_FRAMER_IMPORT = re.compile(r"""from\s+["']framer-motion["']""")


def _motion_registry() -> list[str]:
    """The module paths `web/src/lib/motion.ts` declares as permitted framer-motion importers."""
    path = _WEB_SRC / "lib" / "motion.ts"
    assert path.is_file(), f"{path} is gone -- the console's motion registry moved and this is blind"
    text = _read_stripped(path)
    match = re.search(r"export const MOTION_USAGES = \[(.*?)\] as const", text, re.DOTALL)
    assert match, "lib/motion.ts no longer declares `MOTION_USAGES` as an array literal"
    entries = re.findall(r'"([^"]+)"', match.group(1))
    assert entries, "MOTION_USAGES is empty; a registry with nothing in it cannot be checked"
    return entries


def _framer_importers() -> list[str]:
    """Every module under `web/src` that imports framer-motion, as a `web/src`-relative path.

    `lib/motion.ts` is excluded rather than listed: it is the registry, and a registry naming
    itself is a rule that permits its own existence and says nothing.
    """
    importers = []
    for path in _iter_source_files(_WEB_SRC):
        if path.name.endswith(".test.ts") or path.name.endswith(".test.tsx"):
            continue
        relative = path.relative_to(_WEB_SRC).as_posix()
        if relative == "lib/motion.ts":
            continue
        if _FRAMER_IMPORT.search(_read_stripped(path)):
            importers.append(relative)
    return sorted(importers)


def test_every_framer_motion_importer_is_a_declared_motion_usage():
    _require_web_src()
    _require_examined(_iter_source_files(_WEB_SRC), _WEB_SRC)
    undeclared = sorted(set(_framer_importers()) - set(_motion_registry()))
    assert not undeclared, (
        "these modules import framer-motion and `lib/motion.ts` does not declare them. Motion "
        "claims a time, so it is permitted where the data holds one and the operator meets the "
        "surface occasionally rather than on every pointer move -- add the state change to "
        "MOTION_USAGES in those terms, or take the animation out:\n" + "\n".join(undeclared)
    )


def test_every_declared_motion_usage_still_animates_something():
    _require_web_src()
    importers = set(_framer_importers())
    stale = [entry for entry in _motion_registry() if entry not in importers]
    assert not stale, (
        "`lib/motion.ts` declares these usages and none of them imports framer-motion any more. A "
        "stale entry is a standing permission to animate, carrying a comment that claims somebody "
        "argued for it -- delete the entry with the animation:\n" + "\n".join(stale)
    )


def test_every_declared_motion_usage_names_a_file_that_exists():
    _require_web_src()
    missing = [entry for entry in _motion_registry() if not (_WEB_SRC / entry).is_file()]
    assert not missing, (
        "MOTION_USAGES names files that are not there; a renamed module leaves a permission "
        "pointing at nothing:\n" + "\n".join(missing)
    )


def test_the_registry_guard_rejects_an_undeclared_importer(tmp_path: Path) -> None:
    # The scanning functions read the real tree by design -- they are guards over one known
    # registry, not a reusable scan -- so this exercises the set arithmetic they end in, which is
    # where an undeclared importer is actually caught.
    registry = {"components/error-surface.tsx"}
    importers = {"components/error-surface.tsx", "features/fleet/corpus-chart.tsx"}

    assert sorted(importers - registry) == ["features/fleet/corpus-chart.tsx"]


def test_the_registry_guard_rejects_a_stale_entry() -> None:
    registry = ["components/error-surface.tsx", "components/page-controls.tsx"]
    importers = {"components/error-surface.tsx"}

    assert [e for e in registry if e not in importers] == ["components/page-controls.tsx"]


# -- assertion 11: the display step has exactly one consumer, and it is the page header ----------
#
# The first guard in this file that fails for a *presence* reason rather than an absence one.
# `docs/superpowers/reports/2026-08-06-why-the-console-came-out-flat.md`, cause 5: every guard in
# this file fails when a screen adds something, and no test anywhere fails when a screen is flat --
# "the only automated feedback in the system pushes in one direction, and it is the direction that
# was already the problem."
#
# This is the narrow half of that correction, and the narrow half is the one that can be held today.
# The report asks for a guard that fails when a route renders nothing at the display tier; that
# needs the nine feature screens to adopt `PageHeader`, and M7-W160 deliberately changes nothing in
# `features/`. What is holdable now is the invariant that makes the wider guard possible later:
# **the step exists, and exactly one component spends it.** Two consumers is two focal points, which
# is none, and it is the failure this would drift into first -- a screen reaching for `text-display`
# on its own headline figure because it looked flat.

_DISPLAY_STEP_OWNER = "layouts/page-header.tsx"
_DISPLAY_CLASS = re.compile(r"(?<![\w-])text-display(?![\w-])")


def _display_step_consumers() -> list[str]:
    consumers = []
    for path in _iter_source_files(_WEB_SRC):
        if path.name.endswith((".test.ts", ".test.tsx")):
            continue
        text = _read_stripped(path)
        if _DISPLAY_CLASS.search(text):
            consumers.append(path.relative_to(_WEB_SRC).as_posix())
    return sorted(consumers)


def test_the_display_step_is_declared_so_a_page_title_has_somewhere_to_land():
    # Read out of the contract rather than asserted as 48: DESIGN.md's Type table is the authority
    # and this fails loudly if the step is removed, instead of the class silently resolving to
    # nothing the way an unlisted `text-*` utility does.
    steps = _type_line_heights()
    assert "display" in steps, (
        "DESIGN.md's Type table no longer declares `--text-display`. It was added by M7-W160 so a "
        "page title has a step of its own; without it every route's widest text is whichever "
        "stat-tile figure happens to be on screen, which is what the flat-console report measured."
    )


def test_exactly_one_component_spends_the_display_step():
    _require_web_src()
    _require_examined(_iter_source_files(_WEB_SRC), _WEB_SRC)
    consumers = _display_step_consumers()
    assert consumers == [_DISPLAY_STEP_OWNER], (
        "`text-display` is the page title's step and `layouts/page-header.tsx` is the only place it "
        "belongs. A second consumer is a second focal point on one screen, which is none -- and the "
        "likeliest way it arrives is a screen that looks flat reaching for the biggest step it can "
        f"find rather than composing.\nFound: {consumers}"
    )


def test_the_display_step_guard_rejects_a_second_consumer(tmp_path: Path) -> None:
    (tmp_path / "fleet-page.tsx").write_text(
        '<span className="text-display">1,000+</span>\n', encoding="utf-8"
    )
    (tmp_path / "page-header.tsx").write_text(
        '<h1 className="text-display">{title}</h1>\n', encoding="utf-8"
    )

    found = sorted(
        path.name
        for path in _iter_source_files(tmp_path)
        if _DISPLAY_CLASS.search(_read_stripped(path))
    )

    assert found == ["fleet-page.tsx", "page-header.tsx"]


# -- assertion 12: every route carries the sentence the page header renders ----------------------
#
# `RouteEntry.question` has existed since the registry did, one per route, written for a page header
# that did not exist -- so nine sentences sat unrendered while every screen opened with a bare `h1`.
# `PageHeader` renders it now, which makes an empty one a blank line under a display-size title
# rather than a field nobody reads.
#
# `reachedFrom` is the other half and the sidebar depends on it: a destination it cannot link renders
# that sentence instead of a dead label. The two fields have to disagree in exactly one direction --
# a route with parameters needs one, a route without must not claim one -- and asserting the
# biconditional is what stops a new route being added with neither.

_ROUTE_BLOCK = re.compile(r"\{\s*path: \"([^\"]+)\",(.*?)\n  \}", re.DOTALL)


def _route_fields() -> list[tuple[str, str]]:
    text = _read_stripped(_WEB_SRC / "lib" / "routes.ts")
    body = text[text.index("export const ROUTES") :]
    blocks = _ROUTE_BLOCK.findall(body)
    assert blocks, "lib/routes.ts no longer matches this parser -- update it here too"
    return blocks


def test_every_route_carries_the_question_its_page_header_renders():
    _require_web_src()
    missing = []
    for path, block in _route_fields():
        match = re.search(r'question:\s*\n?\s*"([^"]*)"', block)
        if match is None or len(match.group(1).strip()) < 20:
            missing.append(path)
    assert not missing, (
        "these routes declare no usable `question`, and `layouts/page-header.tsx` renders it as the "
        "one sentence saying what the screen is for -- an empty one is a blank line under a "
        f"display-size title:\n{missing}"
    )


def test_a_route_names_where_its_subject_comes_from_exactly_when_it_needs_one():
    _require_web_src()
    wrong = []
    for path, block in _route_fields():
        needs_subject = re.search(r"params: \[\s*\"", block) is not None
        names_source = re.search(r'reachedFrom:\s*"[^"]+"', block) is not None
        if needs_subject != names_source:
            wrong.append(
                f"{path}: params={'yes' if needs_subject else 'no'}, "
                f"reachedFrom={'yes' if names_source else 'no'}"
            )
    assert not wrong, (
        "`reachedFrom` has to be a sentence exactly when `params` is non-empty. The sidebar renders "
        "it beside a destination it cannot link, so a route with parameters and no sentence is a "
        "dead label -- which is how seven of eleven routes were once unreachable -- and a route "
        f"without parameters claiming one is a sentence nothing shows:\n" + "\n".join(wrong)
    )


# -- assertion 13: the compiler reads comments, so this guard reads them too ----------------------
#
# Every other guard in this file scans `_read_stripped` text, which blanks comments first, and that
# is right: this codebase's own docstrings describe the patterns being banned, so scanning raw text
# would flag the explanation along with the violation.
#
# **Tailwind does not have that luxury and neither does this.** Its scanner extracts class-name
# candidates from raw file text with no idea which of it is code. M7-W160 wrote a docstring in
# `components/skeleton.tsx` explaining why a skeleton does *not* pulse, named the utility while doing
# so, and put `@keyframes pulse` in `dist/assets/*.css` -- measured there before the wording changed.
# The existing keyframe guard could not see it, by construction.
#
# So this one scans raw source for the utility *prefix*, over the same roots, and it is deliberately
# narrower than its stripped sibling: only `animate-`, because that is the prefix that compiles a
# keyframe. A comment may say "no motion" all it likes; it may not spell a utility that emits one.

_RAW_ANIMATE_UTILITY = re.compile(r"(?<![\w-])animate-[\w-]+")


def _raw_animate_violations(root: Path) -> list[str]:
    violations = []
    for path in _iter_source_files(root, suffixes=(".ts", ".tsx", ".css")):
        if path.name.endswith((".test.ts", ".test.tsx")):
            continue
        text = path.read_text(encoding="utf-8")
        for match in _RAW_ANIMATE_UTILITY.finditer(text):
            violations.append(f"{path}:{_line_at(text, match.start())}: {match.group(0)!r}")
    return violations


def test_no_animate_utility_reaches_the_compiler_even_from_a_comment():
    _require_web_src()
    violations = []
    for name in _ANIMATION_FREE_ROOTS:
        root = _WEB_SRC / name
        _require_examined(_iter_source_files(root), root)
        for entry in _raw_animate_violations(root):
            if "/components/ui/" in entry.replace("\\", "/"):
                continue
            violations.append(entry)
    assert not violations, (
        "Tailwind's scanner reads raw text and cannot tell a comment from a class attribute, so "
        "naming an `animate-*` utility anywhere in these files compiles its keyframe into the "
        "bundle -- including in a docstring explaining that the console has no animation, which is "
        "how this was found. Describe the utility without spelling it:\n" + "\n".join(violations)
    )


def test_the_raw_animate_guard_sees_a_utility_named_only_in_a_comment(tmp_path: Path) -> None:
    # The exact shape the real defect took: no class attribute anywhere, one mention in prose, and a
    # keyframe in the output. `_read_stripped` blanks this line, which is why the stripped guard
    # reports clean on it.
    (tmp_path / "skeleton.tsx").write_text(
        "/** It does not pulse: animate-pulse would need a keyframe. */\n"
        'export const Skeleton = () => <span className="h-4 rounded-control" />\n',
        encoding="utf-8",
    )

    assert _keyframe_violations(tmp_path) == []
    assert _raw_animate_violations(tmp_path), "the raw guard missed what the stripped one cannot see"


# -- assertion 14: the section step reaches the panel heading -------------------------------------
#
# The mirror of assertion 11, failing for the opposite reason. That guard caps the display step at
# one consumer, because two focal points on a screen is none. This one requires the *section* step
# to be spent at all, because a step declared and never reached is a ramp with a hole in the middle
# of it.
#
# `docs/superpowers/reports/2026-08-07-console-fidelity-gaps.md` measured the rendered census across
# seven routes -- 46 / 28 / 18 / 15 / 13 / 12 -- and found 18px on exactly one heading in the whole
# application, with almost every other `h2` and `h3` at 12px uppercase furniture. That is the same
# size a table column header renders at, so a panel's name and the name of a column inside it were
# one register, and every route read as a single display-size title over an undifferentiated field.
#
# The guard is anchored on `components/metric-panel.tsx` rather than on a count across `features/`,
# because the panel is the component every level's sections are actually built from -- one class
# there is roughly forty renderings on nine routes, and a count would pass just as happily on forty
# screens each hand-spelling their own heading. A screen that composes a section some other way is
# deliberately not covered here.

_SECTION_CLASS = re.compile(r"(?<![\w-])text-section(?![\w-])")
_FURNITURE_CLASS = re.compile(r"(?<![\w-])(?:furniture|text-meta)(?![\w-])")


def _panel_title_classes(text: str | None = None) -> str:
    """The class string `components/metric-panel.tsx` sets on the panel's own title.

    Anchored on the heading element rather than on the module's text, so this is an assertion
    about the register that heading renders in and not about the word `text-section` appearing
    somewhere in the file.
    """
    if text is None:
        path = _WEB_SRC / "components" / "metric-panel.tsx"
        assert path.is_file(), f"{path} is gone -- the panel moved and this guard is blind"
        text = _read_stripped(path)
    match = re.search(r"<h2\s+className=\"([^\"]+)\"", text)
    assert match, "metric-panel.tsx no longer sets a literal class string on its <h2> title"
    return match.group(1)


def test_the_section_step_is_declared_so_a_panel_heading_has_somewhere_to_land():
    # Read out of the contract for the same reason the display step's own declaration test is:
    # DESIGN.md's Type table is the authority, and an undeclared `text-section` resolves to
    # nothing at all rather than failing.
    steps = _type_line_heights()
    assert "section" in steps, (
        "DESIGN.md's Type table no longer declares `--text-section`. It is the step between the "
        "furniture register and the page title, and without it a panel heading has nowhere to "
        "land but back on the 12px label register it shares with a table column header."
    )


def test_the_panel_heading_spends_the_section_step():
    _require_web_src()
    classes = _panel_title_classes()

    assert _SECTION_CLASS.search(classes), (
        "`components/metric-panel.tsx`'s `h2` is the console's section heading, on every level "
        "that has one. It takes `text-section`; the furniture register belongs to what a reader "
        f"scans rather than enters -- a `dt`, a column header, a rail label.\nFound: {classes!r}"
    )
    assert not _FURNITURE_CLASS.search(classes), (
        "the panel heading carries both the section step and the furniture register. `.furniture` "
        "is uppercase and open-tracked and `--text-section` is a heading role with its own "
        f"tracking; the two together are one element in two registers.\nFound: {classes!r}"
    )


# Verbatim what `metric-panel.tsx` carried before M7-W188, so the two halves below are this guard
# refusing the real defect rather than a fixture invented to be refusable.
_OLD_PANEL_TITLE = '<h2 className="furniture text-meta text-ink-muted">{label}</h2>'


def test_the_panel_heading_guard_rejects_the_furniture_register_that_was_there() -> None:
    classes = _panel_title_classes(_OLD_PANEL_TITLE)

    assert not _SECTION_CLASS.search(classes)
    assert _FURNITURE_CLASS.search(classes)


def test_the_panel_heading_guard_rejects_a_heading_wearing_both_registers() -> None:
    # The likelier regression than a straight revert: somebody adds the step and leaves the
    # uppercase treatment beside it, which renders 18px small-caps -- neither register, and a
    # substring check for `text-section` alone would wave it through.
    classes = _panel_title_classes('<h2 className="furniture text-section">{label}</h2>')

    assert _SECTION_CLASS.search(classes)
    assert _FURNITURE_CLASS.search(classes)


# -- B120: feature pages must not import the routes registry (routes.ts import cycle) ---

_ROUTES_IMPORT_PATTERN = re.compile(
    r"""import\s+(?:\{[^}]*\}|\*\s+as\s+\w+|\w+)\s+from\s+["'](?:@/lib/routes(?:\.ts)?|\.\./.*lib/routes)["']"""
)


def _scan_routes_imports(root: Path) -> list[str]:
    violations = []
    for path in _iter_source_files(root):
        text = _read_stripped(path)
        for match in _ROUTES_IMPORT_PATTERN.finditer(text):
            line = _line_at(text, match.start())
            violations.append(f"{path.name}:{line}: {match.group(0)}")
    return violations


def test_no_feature_page_imports_routes_registry():
    _require_web_src()
    features_dir = _WEB_SRC / "features"
    files = _iter_source_files(features_dir)
    _require_examined(files, features_dir)
    violations = _scan_routes_imports(features_dir)
    assert not violations, (
        "features/ must not import from lib/routes: routes.ts already imports each feature page to "
        "build its element, and an import in reverse closes a module-init cycle (B120). "
        "Pass route props (like `question`) down from App.tsx instead.\nViolations:\n"
        + "\n".join(f"  - {v}" for v in violations)
    )


def test_routes_import_guard_rejects_feature_import(tmp_path: Path):
    bad_feature = tmp_path / "bad-page.tsx"
    bad_feature.write_text('import { ROUTES } from "@/lib/routes"\nexport function Bad() {}', encoding="utf-8")
    violations = _scan_routes_imports(tmp_path)
    assert violations

