"""The console's navigation hierarchy is supposed to come from the specification, never from
a plan. Three plans built one anyway: a route table, a route registry, a persistent navigation
and a command palette, all against a six-level hierarchy nobody had checked against the design
document. Reconciled on 2026-08-05: three of eleven routes matched, four levels were invented,
two were reparented, and three specified levels had never been built.

`.claude/rules/console-hierarchy.md` states the rule. This module is the guard that holds it
when nobody reads the rule -- it parses the specification's authoritative hierarchy and
`GRAPH_LEVELS` out of `web/src/lib/routes.ts` and asserts they name the same levels, in the same
order. It deliberately does not assert which route sits at which level; that is a judgement with
a wrong answer and belongs to a reviewer, not a parser.

The specification carries two fenced hierarchy diagrams in the same section: the original,
kept deliberately unamended so its argument stays readable, and a dated amendment the section
itself labels authoritative. Parsing the wrong one would fail closed in the worst way -- green
while drifted -- so block selection fails loudly rather than guessing when the authoritative
marker is missing or ambiguous.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = (
    REPO_ROOT
    / "docs"
    / "superpowers"
    / "specs"
    / "2026-07-25-sync-self-maintaining-apis-design.md"
)
ROUTES_PATH = REPO_ROOT / "web" / "src" / "lib" / "routes.ts"

_SECTION_HEADING = re.compile(r"^####\s+Information architecture\s*$", re.MULTILINE)
_NEXT_MAJOR_HEADING = re.compile(r"^#{1,3}\s", re.MULTILINE)
_FENCE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
_AUTHORITATIVE_MARKER = re.compile(r"authoritative", re.IGNORECASE)
_ARROW = re.compile(r"(?:├──|└──)\s*(.*)$")  # "├──" / "└──"
_NAME_BOUNDARY = re.compile(r"\s{2,}|\(")

_GRAPH_LEVELS_BLOCK = re.compile(r"export const GRAPH_LEVELS = \[(.*?)\]\s*as const", re.DOTALL)
_ROUTES_BLOCK = re.compile(
    r"export const ROUTES: readonly RouteEntry\[\] = \[(.*?)\]\s*as const", re.DOTALL
)
_QUOTED = re.compile(r'"([^"]+)"')
_ROUTE_LEVEL = re.compile(r'level:\s*"([^"]+)"')


def _information_architecture_section(spec_text: str) -> str:
    heading = _SECTION_HEADING.search(spec_text)
    if heading is None:
        raise AssertionError(
            f"Could not find the '#### Information architecture' heading in {SPEC_PATH}. "
            "That section is where the console's hierarchy is defined; if it moved or was "
            "renamed, update this test's section selector -- do not skip the check."
        )
    end = _NEXT_MAJOR_HEADING.search(spec_text, heading.end())
    return spec_text[heading.end() : end.start() if end else len(spec_text)]


def _authoritative_block(spec_text: str) -> str:
    """Selects the one fenced hierarchy diagram whose immediately preceding paragraph marks
    it authoritative. The section holds two diagrams on purpose -- fail loudly rather than
    silently picking one if that marker is missing or found on more than one block, because a
    parser that quietly matches the wrong (or no) block is the exact failure this test exists
    to catch.
    """
    section = _information_architecture_section(spec_text)
    marked_blocks = []
    cursor = 0
    for match in _FENCE.finditer(section):
        preceding = section[cursor : match.start()]
        paragraphs = [p for p in re.split(r"\n\s*\n", preceding.strip()) if p.strip()]
        last_paragraph = paragraphs[-1] if paragraphs else ""
        if _AUTHORITATIVE_MARKER.search(last_paragraph):
            marked_blocks.append(match.group(1))
        cursor = match.end()

    if len(marked_blocks) != 1:
        raise AssertionError(
            f"Expected exactly one fenced hierarchy block in the 'Information architecture' "
            f"section of {SPEC_PATH} to be marked authoritative by the paragraph immediately "
            f"above it; found {len(marked_blocks)}. The section deliberately carries two "
            "blocks -- the original, unamended, and a dated amendment the section labels "
            "authoritative -- so this parser must be able to tell them apart. Fix the marker "
            "sentence in the specification, not this test."
        )
    return marked_blocks[0]


def _parse_levels(block_text: str) -> list[str]:
    """Reads an ASCII tree diagram's level names, in depth-first order. A line defines a level
    if it is the diagram's root (no tree-drawing prefix) or contains an arrow (`├──`/`└──`); a
    bare `│` continuation line is wrapped description text, not a new level. A level's name
    ends at the first two-or-more-space gap or opening parenthesis, whichever comes first --
    the gap separates the name from its trailing description, and multi-word names like
    "API Services" or "Errors & Incidents" keep their single internal spaces.
    """
    levels = []
    seen_root = False
    for line in block_text.splitlines():
        if not line.strip():
            continue
        arrow = _ARROW.search(line)
        if arrow:
            remainder = arrow.group(1)
        elif not seen_root:
            remainder = line.strip()
        else:
            continue
        seen_root = True
        name = _NAME_BOUNDARY.split(remainder, maxsplit=1)[0].strip()
        if name:
            levels.append(name)
    return levels


def _parse_graph_levels(routes_text: str) -> list[str]:
    match = _GRAPH_LEVELS_BLOCK.search(routes_text)
    if match is None:
        raise AssertionError(
            f"Could not find `export const GRAPH_LEVELS = [...] as const` in {ROUTES_PATH}."
        )
    return _QUOTED.findall(match.group(1))


def _parse_route_levels(routes_text: str) -> list[str]:
    match = _ROUTES_BLOCK.search(routes_text)
    if match is None:
        raise AssertionError(
            "Could not find `export const ROUTES: readonly RouteEntry[] = [...] as const` "
            f"in {ROUTES_PATH}."
        )
    return _ROUTE_LEVEL.findall(match.group(1))


def test_graph_levels_match_the_specifications_authoritative_hierarchy_in_order():
    spec_text = SPEC_PATH.read_text(encoding="utf-8")
    routes_text = ROUTES_PATH.read_text(encoding="utf-8")

    spec_levels = _parse_levels(_authoritative_block(spec_text))
    graph_levels = _parse_graph_levels(routes_text)

    assert spec_levels == graph_levels, (
        f"GRAPH_LEVELS in {ROUTES_PATH} is {graph_levels}, but the specification's "
        f"authoritative hierarchy in {SPEC_PATH} is {spec_levels}. These must name the same "
        "levels in the same order. Fix it with a route change if GRAPH_LEVELS drifted, or "
        "with a dated amendment to the specification's Information architecture section if "
        "the graph genuinely gained or lost a level -- never by changing this test."
    )


def test_every_route_level_is_a_declared_graph_level():
    routes_text = ROUTES_PATH.read_text(encoding="utf-8")

    graph_levels = set(_parse_graph_levels(routes_text))
    route_levels = _parse_route_levels(routes_text)

    unknown = sorted({level for level in route_levels if level not in graph_levels})
    assert not unknown, (
        f"ROUTES in {ROUTES_PATH} names level(s) {unknown} that GRAPH_LEVELS does not "
        f"declare. Checked against the specification at {SPEC_PATH}, not against routes.ts "
        "itself. Fix it by changing the route to an existing level, or by adding the level "
        "to GRAPH_LEVELS after arguing for it in a dated amendment to the specification -- "
        "never by changing this test."
    )


def test_block_selection_fails_loudly_when_no_block_is_marked_authoritative():
    spec_text = SPEC_PATH.read_text(encoding="utf-8").replace(
        "This block is the authoritative one", "This block reflects the current thinking"
    )

    with pytest.raises(AssertionError, match="authoritative"):
        _authoritative_block(spec_text)


def test_block_selection_fails_loudly_when_two_blocks_are_marked_authoritative():
    spec_text = SPEC_PATH.read_text(encoding="utf-8").replace(
        "The navigation hierarchy is the API Dependency Graph.",
        "This block is the authoritative one. The navigation hierarchy is the API "
        "Dependency Graph.",
    )

    with pytest.raises(AssertionError, match="authoritative"):
        _authoritative_block(spec_text)
