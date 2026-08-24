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


# -- assertion 2: no keyframes or animation shorthand outside a loading indicator --------------





_VENDORED_PREFIXES = ("vendor/supabase/", "components/ui/")


def _is_vendored(path: Path, root: Path) -> bool:
    relative = path.relative_to(root).as_posix()
    return any(relative.startswith(prefix) for prefix in _VENDORED_PREFIXES)



# -- assertion 3: nothing transitions geometry anywhere (opacity is not geometry) ---------------

_GEOMETRY_TRANSITION = re.compile(
    r"(?<![\w-])(?:transition-all|transition-transform|transition-shadow|transition)(?![\w=-])"
)


# Selectors that make a class string's motion a response to the reader's own hand rather than a
# claim about the system. **Owner ruling, 2026-08-18:** direct manipulation of a control is not a
# statement about state, so interaction feedback is permitted and motion implying liveness stays
# banned. A switch whose thumb does not slide reads as broken; a progress bar that animates its
# fill is a claim, and the difference is whether the reader caused it.
_INTERACTION_SELECTORS = (
    "hover:", "focus:", "focus-visible:", "focus-within:", "active:", "disabled:",
    "data-checked:", "data-unchecked:", "data-disabled:", "data-[state=",
    "group-data-open", "group-data-popup-open", "peer-checked",
)


def _enclosing_class_string(text: str, position: int) -> str:
    """The double-quoted literal `position` sits inside, which is the element's own class string.

    Class strings in this codebase carry no escaped quotes, so the nearest quote on each side
    bounds the literal. A match outside any literal yields the empty string and is not exempt.
    """
    start = text.rfind('"', 0, position)
    end = text.find('"', position)
    if start == -1 or end == -1:
        return ""
    return text[start + 1 : end]


def _geometry_transition_violations(root: Path, *, skip_vendored: bool = False) -> list[str]:
    violations = []
    for path in _iter_source_files(root):
        if skip_vendored and _is_vendored(path, root):
            continue
        text = _read_stripped(path)
        for match in _GEOMETRY_TRANSITION.finditer(text):
            classes = _enclosing_class_string(text, match.start())
            if any(selector in classes for selector in _INTERACTION_SELECTORS):
                continue
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
    # No interaction selector, so nothing about this element's motion is the reader's doing.
    # The fixture read `hover:opacity-80`, which the owner's ruling now exempts -- so it had
    # stopped proving the guard rejects anything and is replaced rather than deleted.
    (tmp_path / "banner.tsx").write_text(
        '<div className="w-full transition-all" />\n', encoding="utf-8"
    )

    violations = _geometry_transition_violations(tmp_path)

    assert violations and "transition-all" in violations[0]


def test_the_geometry_guard_permits_motion_the_reader_caused(tmp_path: Path) -> None:
    """Owner ruling, 2026-08-18: direct manipulation of a control is not a claim about state.

    A switch whose thumb does not slide reads as broken, and the thumb slides because
    somebody flipped it. This is the narrowing that ruling authorises, and nothing wider.
    """
    (tmp_path / "switch.tsx").write_text(
        '<span className="transition-transform data-checked:translate-x-4" />\n'
        '<button className="transition-all hover:bg-muted focus-visible:ring-ring" />\n',
        encoding="utf-8",
    )

    violations = _geometry_transition_violations(tmp_path)

    assert not violations


def test_the_geometry_guard_still_catches_motion_bound_to_a_value(tmp_path: Path) -> None:
    """The half of the ruling that is a refusal, and the reason the narrowing is safe.

    This is `components/ui/progress.tsx` as it stood: an indicator translated by a measured
    value, animating whenever that value moves. Nobody touched it -- so it is the console
    asserting something, which is the motion that stays banned. It was the one violation of
    eight left standing when the exemption landed, and it was removed rather than exempted.
    """
    (tmp_path / "progress.tsx").write_text(
        '<div className="size-full flex-1 bg-primary transition-all" />\n', encoding="utf-8"
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


# The one sanctioned home for a colour value outside index.css. `lib/palette.ts` computes with
# its colours -- relative luminance, contrast ratios, Lab ramps -- and a CSS variable is a string
# JavaScript cannot do arithmetic on. The exemption is paid for by
# `test_palette_series_slots_match_the_stylesheet` below, which holds the one set of values both
# files state (the eight series slots) equal, so the exemption cannot quietly become a fork.
_COLOUR_LITERAL_EXEMPT = ("palette.ts", "palette.test.ts")


def _colour_literal_violations(root: Path) -> list[str]:
    violations = []
    for path in _iter_source_files(root, suffixes=(".ts", ".tsx", ".css")):
        if path.name == "index.css":
            continue
        if path.parent.name == "lib" and path.name in _COLOUR_LITERAL_EXEMPT:
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


def test_palette_series_slots_match_the_stylesheet():
    """The price of `lib/palette.ts`'s exemption: the eight series slots it states are the
    stylesheet's own, byte for byte, so the two files cannot drift into naming one colour twice.
    """
    _require_web_src()
    palette = (_WEB_SRC / "lib" / "palette.ts").read_text(encoding="utf-8")
    stylesheet = (_WEB_SRC / "index.css").read_text(encoding="utf-8")

    block = re.search(r"SERIES_SLOTS = \[(.*?)\]", palette, re.DOTALL)
    assert block, "SERIES_SLOTS not found in palette.ts"
    stated = re.findall(r'"(#[0-9a-fA-F]{6})"', block.group(1))
    assert len(stated) == 8

    for index, value in enumerate(stated, start=1):
        declared = re.search(rf"--color-series-{index}:\s*([^;]+);", stylesheet)
        assert declared, f"--color-series-{index} not declared in index.css"
        assert declared.group(1).strip().lower() == value.lower(), (
            f"--color-series-{index} is {declared.group(1).strip()} in index.css but "
            f"{value} in palette.ts; one of them moved without the other"
        )


def test_the_colour_literal_guard_rejects_a_hardcoded_hex(tmp_path: Path) -> None:
    (tmp_path / "precedent-chart.tsx").write_text(
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


# -- assertion 7: no font weight above the ramp's heaviest step ----------------------------------


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
    # The vendored exclusion is dropped: `components/ui/` is the primitive substrate now, so a
    # floor that skips it skips the directory every visible control lives in. It costs nothing
    # today -- the catalog's focus rings were hand-substituted to full strength already, and the
    # `/n` rings it does carry are `aria-invalid:` and decorative, which this pattern never matched.
    violations = _ring_alpha_violations(_WEB_SRC, skip_vendored=False)
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

    assert not _dialog_heading_violations(tmp_path)


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


# -- assertion 9: two working ink levels for text, and the third is not a text class ------------
#
# Section 8 of `2026-08-05-sync-console-architecture.md` measures two ink levels plus one accent
# and never three. The console holds it with `--color-ink` and `--color-ink-muted`;
# `--color-ink-secondary` has exactly one consumer, `precedent-chart.tsx`'s legend `textStyle`, which
# renders into a canvas and is not a DOM ink level at all. Two call sites reached for it as a
# class and made a third -- `run-outcome.tsx` on the two screens carrying the densest evidence,
# and `filters.tsx` on the active-filter strip, where it also made the value *dimmer* than the
# ink-muted label naming it. Both measured 3 levels before M4.5-W142 and 2 after.
#
# The ban is on the class, not on the token: a chart resolving `--color-ink-secondary` through
# `getComputedStyle` is the sanctioned consumer and must keep working.

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
    importers = {"components/error-surface.tsx", "features/fleet/precedent-chart.tsx"}

    assert sorted(importers - registry) == ["features/fleet/precedent-chart.tsx"]


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

# -- decision 55: the ring is visible to a mouse and a keyboard alike --------------------------

_FOCUS_VISIBLE = "focus-visible:"


def _keyboard_only_ring_violations(root: Path) -> list[str]:
    """Sites spelling the focus ring as keyboard-only.

    Scanned across `components/ui/` deliberately, even though `_VENDORED_PREFIXES` excludes it
    from the guards above. That exclusion exists so nobody is asked to restyle a catalog as it
    is copied in; it is not a statement that the catalog may disagree with a decision, and
    most of what a reader sees is those components.

    `vendor/supabase/` stays out under the carve-out in `interface-originality.md`.
    """
    violations = []
    for path in _iter_source_files(root):
        if path.relative_to(root).as_posix().startswith("vendor/supabase/"):
            continue
        text = _read_stripped(path)
        index = text.find(_FOCUS_VISIBLE)
        while index != -1:
            violations.append(f"{path}:{_line_at(text, index)}")
            index = text.find(_FOCUS_VISIBLE, index + 1)
    return violations


def test_the_focus_ring_is_not_keyboard_only():
    """Owner decision 55: ring always visible, tab order only.

    `focus-visible:` is the Radix and shadcn default and it is the opposite of what was
    decided -- it shows the ring to a keyboard and hides it from a mouse. The decision was
    recorded with the note that Radix defaults that way precisely because a ring left after a
    click reads as noise, and that reversing it is cheap if it turns out loud in use. Cheap
    means one substitution over one directory, which is why this is a guard and not a habit.
    """
    _require_web_src()
    violations = _keyboard_only_ring_violations(_WEB_SRC)
    assert not violations, (
        "decision 55 chose a focus ring visible to a mouse and a keyboard alike, and "
        "`focus-visible:` shows it to one of them -- spell it `focus:`:\n  "
        + "\n  ".join(violations)
    )


def test_the_keyboard_only_ring_guard_can_fail(tmp_path: Path) -> None:
    (tmp_path / "control.tsx").write_text(
        '<button className="focus-visible:ring-ring" />\n', encoding="utf-8"
    )

    assert _keyboard_only_ring_violations(tmp_path)



_ANIMATION_PLUGINS = ("tailwindcss-animate", "tw-animate-css")




def test_plotting_surface_matches_the_card_token():
    """The price of `lib/palette.ts`'s third exemption. `PLOTTING_SURFACE` is a hand transcription
    of `--color-card`, and every mark-legibility proof in that file is computed against it, so a
    move of the card token with no matching edit here measures a surface no longer on screen.
    """
    _require_web_src()
    palette = (_WEB_SRC / "lib" / "palette.ts").read_text(encoding="utf-8")
    design = _DESIGN_MD.read_text(encoding="utf-8")

    stated = re.search(r'PLOTTING_SURFACE = "(#[0-9a-fA-F]{6})"', palette)
    assert stated, "PLOTTING_SURFACE not found in palette.ts"

    row = re.search(r"`--color-card`[^|]*\|[^|]*\|\s*`(#[0-9a-fA-F]{6})`\s*\|", design)
    assert row, "DESIGN.md publishes no hex for --color-card"

    assert stated.group(1).lower() == row.group(1).lower(), (
        f"PLOTTING_SURFACE is {stated.group(1)} in palette.ts but DESIGN.md publishes "
        f"{row.group(1)} for --color-card; one of them moved without the other"
    )


_JUDGEMENT_COLOUR = re.compile(
    r"(?<![-\w:])(?:bg|text|border)-(?:emerald|amber|red|green|blue|yellow|orange|rose|sky|"
    r"slate|zinc|gray|stone|neutral)-\d{2,3}(?:/\d{1,3})?(?![-\w])"
)


def _judgement_colour_violations(root: Path) -> list[str]:
    violations: list[str] = []
    for path in _iter_source_files(root):
        if _is_vendored(path, root):
            continue
        # Comments blanked, not the scan narrowed to `className=`: a tone string built in a
        # variable never appears inside a class attribute, and those are the colours this exists
        # to catch. The retired guard recorded both halves of that decision.
        text = _read_stripped(path)
        for match in _JUDGEMENT_COLOUR.finditer(text):
            violations.append(f"{path}:{_line_at(text, match.start())}: {match.group(0)!r}")
    return violations


def test_no_raw_palette_colour_claims_a_judgement():
    """A stock Tailwind palette class is a verdict nobody declared and nobody measured.

    `red-500` on a row is the traffic light `web/CLAUDE.md` refuses three times over, arriving as a
    utility rather than as a component. Status ships from the four declared roles, with an icon and
    a word beside it; identity ships from the series slots.
    """
    _require_web_src()
    _require_examined(_iter_source_files(_WEB_SRC), _WEB_SRC)
    violations = _judgement_colour_violations(_WEB_SRC)
    assert not violations, (
        "a raw palette colour asserts a judgement the graph has not computed -- spend a status "
        "token and ship the icon and the word with it, or a series slot if what you mean is "
        "identity:\n" + "\n".join(violations)
    )


def test_the_judgement_colour_guard_rejects_a_traffic_light(tmp_path: Path) -> None:
    (tmp_path / "findings-table.tsx").write_text(
        'const tone = severe ? "text-red-500" : "text-emerald-400"\n', encoding="utf-8"
    )

    violations = _judgement_colour_violations(tmp_path)

    assert len(violations) == 2, violations


def test_the_judgement_colour_guard_permits_a_declared_status_token(tmp_path: Path) -> None:
    (tmp_path / "status.tsx").write_text(
        '<span className="text-status-critical bg-surface-subtle border-line" />\n', encoding="utf-8"
    )

    assert not _judgement_colour_violations(tmp_path)


# -- assertion N: every keyframe that can reach the bundle is one somebody chose -----------------
#
# This folds four guards that each watched one breadth of the same defect: the `index.css` keyframe
# baseline, the raw-text `animate-*` scan, the core-utility denylist, and the plugin-absence check.
# Four scanners over one property left gaps between them, and the bundle carried `@keyframes pulse`
# through one of those gaps for weeks.
#
# The breadth that matters is `_tailwind_scanned_files`. Every predecessor read `web/src`, and
# Tailwind reads the whole project minus what git ignores -- which is how a line in `web/NOTICE`
# explaining that a utility had been removed compiled it straight back in, measured in the commit
# that removed it.
_KEYFRAME_DECL = re.compile(r"@keyframes\s+([A-Za-z][\w-]*)")

# Core Tailwind ships these four and nothing else. Everything in the `animate-in` / `fade-in-0` /
# `zoom-in-95` family belongs to `tailwindcss-animate`, which is why it is inert here and why the
# plugin's absence is part of the assertion rather than a separate rule.
_CORE_ANIMATE = re.compile(r"\banimate-(pulse|spin|ping|bounce)\b")
_ANY_ANIMATE = re.compile(r"\banimate-([a-z0-9][\w-]*)\b")

_ANIMATION_PLUGINS = ("tailwindcss-animate", "tw-animate-css")

_TAILWIND_IGNORED_DIRS = {"node_modules", "dist", "dist-ssr", ".git", "coverage"}


def _tailwind_scanned_files(web_root: Path) -> list[Path]:
    """Every file Tailwind's source detection reads: the project minus what git ignores.

    Deliberately not `web/src` and deliberately not filtered by suffix -- the scanner is a text
    extractor, so a markdown note and a JSON manifest are candidate sources exactly as a `.tsx` is.
    """
    found: list[Path] = []
    for path in sorted(web_root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in _TAILWIND_IGNORED_DIRS for part in path.relative_to(web_root).parts):
            continue
        found.append(path)
    return found


def _registered_keyframes(web_src: Path) -> set[str]:
    text = (web_src / "lib" / "motion.ts").read_text(encoding="utf-8")
    block = re.search(r"KEYFRAMES[^=]*=\s*\[(.*?)\]", text, re.DOTALL)
    assert block, "KEYFRAMES not found in lib/motion.ts -- this guard is blind"
    return set(re.findall(r'name:\s*"([\w-]+)"', block.group(1)))


def _animation_plugin_installed(web_root: Path) -> list[str]:
    manifest = (web_root / "package.json").read_text(encoding="utf-8")
    return [name for name in _ANIMATION_PLUGINS if f'"{name}"' in manifest]


def _unchosen_keyframes(web_root: Path, web_src: Path) -> list[str]:
    registered = _registered_keyframes(web_src)
    plugin = _animation_plugin_installed(web_root)
    unchosen: list[str] = []

    for path in _tailwind_scanned_files(web_root):
        try:
            # Raw text, never comment-stripped: the compiler reads comments, and that is not a
            # theoretical point -- it is how the keyframe reached the bundle both times.
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        for match in _KEYFRAME_DECL.finditer(text):
            if match.group(1) not in registered:
                unchosen.append(f"{path}:{_line_at(text, match.start())}: @keyframes {match.group(1)}")

        # A plugin turns the whole `animate-*` surface live at once, so the pattern widens with it.
        pattern = _ANY_ANIMATE if plugin else _CORE_ANIMATE
        for match in pattern.finditer(text):
            if match.group(1) not in registered:
                unchosen.append(f"{path}:{_line_at(text, match.start())}: {match.group(0)!r}")

    return unchosen


def test_every_keyframe_that_can_reach_the_bundle_is_one_somebody_chose():
    """Motion is not forbidden. Unaccounted motion is.

    `lib/motion.ts`'s `KEYFRAMES` is the registry; this holds it against the three sources that can
    put a keyframe in `dist` -- a declaration in `index.css`, a core Tailwind utility spelled
    anywhere the scanner reads, and the wider family an animation plugin would bring to life.
    """
    _require_web_src()
    web_root = _WEB_SRC.parent
    scanned = _tailwind_scanned_files(web_root)
    assert scanned, f"scanned no files under {web_root} -- the console tree moved and this is blind"

    unchosen = _unchosen_keyframes(web_root, _WEB_SRC)
    assert not unchosen, (
        "a keyframe can reach the built stylesheet without an entry in lib/motion.ts's KEYFRAMES "
        "-- register it with the trigger that runs it, or delete the utility. Nothing animates at "
        "rest and nothing animates in proportion to a data value, so if neither `interaction` nor "
        "`arrival` describes it, it does not get an entry:\n" + "\n".join(unchosen)
    )


def test_every_registered_keyframe_declares_a_permitted_trigger():
    """The liveness-pulse refusal, and after the blanket motion bans retire it is the only thing
    holding it. A trigger outside the closed vocabulary is a shape moving with nobody touching it.
    """
    _require_web_src()
    text = (_WEB_SRC / "lib" / "motion.ts").read_text(encoding="utf-8")
    block = re.search(r"KEYFRAMES[^=]*=\s*\[(.*?)\]", text, re.DOTALL)
    assert block, "KEYFRAMES not found in lib/motion.ts -- this guard is blind"

    entries = re.findall(r'name:\s*"([\w-]+)"[^}]*?trigger:\s*"([\w-]+)"', block.group(1))
    assert len(entries) == len(re.findall(r'name:\s*"[\w-]+"', block.group(1))), (
        "a KEYFRAMES entry names a keyframe without declaring what runs it"
    )
    bad = [f"{name} -> {trigger}" for name, trigger in entries if trigger not in {"interaction", "arrival"}]
    assert not bad, (
        "a keyframe may be run by an interaction or by something arriving, and by nothing else -- "
        "motion at rest is a liveness pulse and motion proportional to a value claims the value is "
        f"arriving now: {bad}"
    )


def test_the_keyframe_registry_catches_a_declaration_nobody_registered(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "lib").mkdir()
    (tmp_path / "src" / "lib" / "motion.ts").write_text("export const KEYFRAMES = [\n]\n", encoding="utf-8")
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "src" / "index.css").write_text("@keyframes pulse { to { opacity: 1 } }\n", encoding="utf-8")

    violations = _unchosen_keyframes(tmp_path, tmp_path / "src")

    assert violations and "@keyframes pulse" in violations[0]


def test_the_keyframe_registry_reads_through_a_comment_and_past_web_src(tmp_path: Path) -> None:
    """The two gaps the four predecessors left, proven closed together."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "lib").mkdir()
    (tmp_path / "src" / "lib" / "motion.ts").write_text("export const KEYFRAMES = [\n]\n", encoding="utf-8")
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    # A prose file outside src/, naming the utility in order to explain its removal.
    (tmp_path / "NOTICE").write_text("its animate-spin compiled a keyframe into the bundle\n", encoding="utf-8")

    violations = _unchosen_keyframes(tmp_path, tmp_path / "src")

    assert violations and "animate-spin" in violations[0] and "NOTICE" in violations[0]


def test_the_keyframe_registry_permits_a_registered_keyframe(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "lib").mkdir()
    (tmp_path / "src" / "lib" / "motion.ts").write_text(
        'export const KEYFRAMES = [\n  { name: "spin", trigger: "interaction", why: "x" },\n]\n',
        encoding="utf-8",
    )
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "src" / "spinner.tsx").write_text('<i className="animate-spin" />\n', encoding="utf-8")

    assert not _unchosen_keyframes(tmp_path, tmp_path / "src")


def test_the_keyframe_registry_widens_when_an_animation_plugin_is_installed(tmp_path: Path) -> None:
    """`animate-in` is inert only because nothing compiles it. Installing the plugin makes roughly
    forty class names across both vendored catalogs live in a single commit."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "lib").mkdir()
    (tmp_path / "src" / "lib" / "motion.ts").write_text("export const KEYFRAMES = [\n]\n", encoding="utf-8")
    (tmp_path / "src" / "popover.tsx").write_text('<div className="animate-in fade-in-0" />\n', encoding="utf-8")

    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    assert not _unchosen_keyframes(tmp_path, tmp_path / "src"), "inert without the plugin"

    (tmp_path / "package.json").write_text('{"dependencies": {"tailwindcss-animate": "^1"}}', encoding="utf-8")
    violations = _unchosen_keyframes(tmp_path, tmp_path / "src")
    assert violations and "animate-in" in violations[0], "live once the plugin is installed"


def _migrated_addresses() -> list[str]:
    text = (_WEB_SRC / "layouts" / "screen-skeleton.test.tsx").read_text(encoding="utf-8")
    block = re.search(r"const MIGRATED = \[(.*?)\]", text, re.DOTALL)
    assert block, "MIGRATED not found in screen-skeleton.test.tsx -- this guard is blind"
    return re.findall(r'"([^"]+)"', block.group(1))


def _screen_frame_consumers(features: Path) -> list[Path]:
    return [
        path
        for path in _iter_source_files(features, suffixes=(".tsx",))
        if ".test." not in path.name and "layouts/screen-frame" in path.read_text(encoding="utf-8")
    ]


def test_every_migrated_address_has_a_real_screen_frame_consumer():
    """The ratchet's union check is satisfied by moving a string between two arrays, and never asks
    whether the screen renders the frame -- so a promotion could be pure bookkeeping.

    It lives here rather than beside the ratchet because the app's tsconfig carries no node types:
    a `node:fs` import inside `web/src` runs under vitest and fails `npm run build`.
    """
    _require_web_src()
    migrated = _migrated_addresses()
    consumers = _screen_frame_consumers(_WEB_SRC / "features")
    assert len(consumers) == len(migrated), (
        f"{len(migrated)} addresses are marked migrated but {len(consumers)} feature screens "
        "import layouts/screen-frame -- a promotion the tree does not back. Screens importing it:"
        + "".join(sorted("\n  " + path.name for path in consumers))
    )


def test_the_consumer_guard_counts_only_screens_that_import_the_frame(tmp_path: Path) -> None:
    features = tmp_path / "features"
    features.mkdir()
    (features / "migrated-page.tsx").write_text(
        'import { ScreenFrame } from "@/layouts/screen-frame"\n', encoding="utf-8"
    )
    (features / "pending-page.tsx").write_text("export function Pending() {}\n", encoding="utf-8")
    (features / "migrated-page.test.tsx").write_text(
        'import "@/layouts/screen-frame"\n', encoding="utf-8"
    )

    consumers = _screen_frame_consumers(features)

    # The unmigrated screen is not counted, and neither is the test file beside the migrated one --
    # a promotion backed only by a test import is the bookkeeping this guard exists to refuse.
    assert [path.name for path in consumers] == ["migrated-page.tsx"]


# --- one ink, one declaration ------------------------------------------------------


#: Each group is one ink. The first name owns the value; the rest read it through `var()`.
#:
#: The `ink-` names are the console's own and the substrate's are what the vendored and shadcn
#: primitives are authored in, so both sets stay -- re-authoring a working primitive to change a
#: class name is polish. What must not stay is one colour spelled twice: six names carried two
#: values byte-identically, and a value written twice disagrees with itself the first time
#: somebody adjusts one copy.
_INK_GROUPS = (
    ("--color-ink-muted", ("--color-foreground-light", "--color-muted-foreground")),
    ("--color-ink-secondary", ("--color-foreground-lighter", "--color-foreground-muted")),
)


def _declaration_of(css: str, token: str) -> str | None:
    matched = re.search(re.escape(token) + r":\s*([^;]+);", css)
    return matched.group(1).strip() if matched else None


def _ink_violations(css: str) -> list[str]:
    """Every ink token declaring a colour where it should read one, and every owner that has
    stopped holding a colour of its own."""
    found: list[str] = []
    for owner, aliases in _INK_GROUPS:
        owned = _declaration_of(css, owner)
        if owned is None:
            found.append(owner + " is not declared")
        elif not owned.startswith("oklch("):
            found.append(owner + " holds " + owned + ", not a colour of its own")
        for alias in aliases:
            value = _declaration_of(css, alias)
            if value is None:
                found.append(alias + " is not declared")
            elif value != "var(" + owner + ")":
                found.append(alias + " holds " + value + " rather than var(" + owner + ")")
    return found


def test_each_ink_is_declared_once_and_read_everywhere_else():
    _require_web_src()

    assert _ink_violations((_WEB_SRC / "index.css").read_text(encoding="utf-8")) == []


def test_the_ink_guard_sees_a_second_copy_of_a_colour() -> None:
    """The state this replaced: two names, one colour, spelled out twice."""
    css = "\n".join([
        ":root {",
        "  --color-ink-muted: oklch(0.798 0.00275 159);",
        "  --color-foreground-light: oklch(0.798 0.00275 159);",
        "  --color-muted-foreground: var(--color-ink-muted);",
        "  --color-ink-secondary: oklch(0.684 0.00275 159);",
        "  --color-foreground-lighter: var(--color-ink-secondary);",
        "  --color-foreground-muted: var(--color-ink-secondary);",
        "}",
    ])

    violations = _ink_violations(css)

    assert len(violations) == 1
    assert "--color-foreground-light" in violations[0]


def test_the_ink_guard_sees_an_owner_that_has_become_an_alias() -> None:
    """An alias chain reads as tidy and moves the value somewhere this guard is not looking."""
    css = "\n".join([
        ":root {",
        "  --color-ink-muted: var(--color-foreground-light);",
        "  --color-foreground-light: oklch(0.798 0.00275 159);",
        "  --color-muted-foreground: var(--color-ink-muted);",
        "  --color-ink-secondary: oklch(0.684 0.00275 159);",
        "  --color-foreground-lighter: var(--color-ink-secondary);",
        "  --color-foreground-muted: var(--color-ink-secondary);",
        "}",
    ])

    assert any("not a colour of its own" in line for line in _ink_violations(css))


# --- spacing: the named steps, and the one the console reaches past them for --------


#: Raw numeric spacing utilities a screen may still write, and why each is not a density
#: decision. Everything else in the console's own files goes through `field`, `row`, `section`
#: or `frame`.
_SPACING_EXEMPT = {
    "0": "a reset -- `p-0` and `mt-0` remove a primitive's own padding rather than choosing any",
    "8": (
        "2rem, the gap between a screen's top-level blocks. 38 sites in 26 files write it and no "
        "named step holds it: `section` is 1rem and `frame` is 2.5rem. The scale's own comment "
        "says a fifth step is a decision recorded in DESIGN.md rather than a value added in "
        "passing, and DESIGN.md is the owner's document -- so this is measured and named here, "
        "and stays a raw number until that decision is taken."
    ),
}

_SPACING_UTILITY = re.compile(
    r"\b(?:gap|gap-x|gap-y|p|px|py|pt|pb|pl|pr|m|mt|mb|ml|mr|space-x|space-y)-(\d+)\b"
)


def _raw_spacing_steps(source: str) -> set[str]:
    """Numeric spacing steps a file writes, ignoring the exempt ones."""
    return {step for step in _SPACING_UTILITY.findall(source) if step not in _SPACING_EXEMPT}


def test_the_console_writes_no_unnamed_spacing_step():
    _require_web_src()

    offenders: list[str] = []
    for path in sorted(_WEB_SRC.rglob("*.tsx")):
        posix = path.as_posix()
        # The primitives ship with the substrate's own utilities and are not ours to re-author.
        if "/ui/" in posix or "/vendor/" in posix:
            continue
        for step in sorted(_raw_spacing_steps(path.read_text(encoding="utf-8"))):
            offenders.append(f"{path.relative_to(_WEB_SRC).as_posix()}: -{step}")

    assert offenders == [], (
        "a screen reached past the named spacing scale. Use `field`, `row`, `section` or "
        "`frame`, or record a new step in DESIGN.md first:\n  " + "\n  ".join(offenders)
    )


def test_the_spacing_guard_sees_a_step_outside_the_scale() -> None:
    assert _raw_spacing_steps('<div className="flex gap-5">') == {"5"}


def test_the_spacing_guard_passes_the_exempt_steps() -> None:
    """`-0` is a reset and `-8` is measured above; neither is a density choice made in passing."""
    assert _raw_spacing_steps('<div className="mt-0 gap-8 p-0">') == set()
