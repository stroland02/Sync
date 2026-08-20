"""The Signals level says which of its three roles has an integration attached, and this holds
that claim against the two things that could make it false.

The level renders one panel per role -- vendor, signal source, human surface. Two of the three
have something behind them in this deployment and one has nothing at all, so a screen that draws
three panels and says nothing else reads as three integrations existing. The header therefore
names which roles have one attached and which do not, and it builds that sentence out of
`web/src/features/signals/roles.ts` rather than restating it, because a fact written twice
disagrees with itself.

Two ways that claim goes quietly wrong, and one test each:

- **The vocabulary drifts.** The roles and their relationship sentences belong to
  `2026-07-25-sync-self-maintaining-apis-design.md:455-459`, the M5 table. A paraphrase in the
  console is a second authority, and the same drift cost the hierarchy four invented levels
  before `test_console_hierarchy.py` existed.
- **A role claims an integration nothing serves.** `source` is what the header reads as
  "attached", so a path that no API route answers would put a role on the attached side of that
  sentence with nothing behind it -- which is the exact false claim the header was added to
  prevent.

The console has no test runner (`.claude/rules/console-dev-loop.md`), so this reads the
TypeScript from Python, the way `test_console_hierarchy.py` and `test_console_design_tokens.py`
already do.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = (
    REPO_ROOT
    / "docs"
    / "superpowers"
    / "specs"
    / "2026-07-25-sync-self-maintaining-apis-design.md"
)
ROLES_PATH = REPO_ROOT / "web" / "src" / "features" / "signals" / "roles.ts"
SIGNALS_PAGE_PATH = REPO_ROOT / "web" / "src" / "features" / "signals" / "signals-page.tsx"
API_APP_PATH = REPO_ROOT / "src" / "sync" / "api" / "app.py"

_M5_HEADING = re.compile(r"^###\s+M5\b.*$", re.MULTILINE)
_NEXT_MAJOR_HEADING = re.compile(r"^#{1,3}\s", re.MULTILINE)
_TABLE_HEADER = re.compile(r"^\|\s*Role\s*\|.*Relationship to the graph\s*\|$")
_BOLD = re.compile(r"^\*\*(.+)\*\*$")

_ROLES_ARRAY = re.compile(r"export const SIGNAL_ROLES[^=]*=\s*\[(.*?)\]\s*as const", re.DOTALL)
_IDENTIFIER = re.compile(r"[A-Z][A-Z0-9_]*")
_ROLE_FIELD = re.compile(r'\brole:\s*"([^"]*)"')
_RELATIONSHIP_FIELD = re.compile(r'\brelationship:\s*"([^"]*)"')
_SOURCE_FIELD = re.compile(r'\bsource:\s*(null|"[^"]*")')

_API_ROUTE = re.compile(r'Route\(\s*"([^"]+)"')


def _m5_section(spec_text: str) -> str:
    heading = _M5_HEADING.search(spec_text)
    if heading is None:
        raise AssertionError(
            f"Could not find the '### M5' heading in {SPEC_PATH}. That section defines the "
            "three integration roles the Signals level groups by; if it moved or was renamed, "
            "update this test's selector -- do not skip the check."
        )
    end = _NEXT_MAJOR_HEADING.search(spec_text, heading.end())
    return spec_text[heading.end() : end.start() if end else len(spec_text)]


def _specification_roles() -> list[tuple[str, str]]:
    """The M5 table's rows: the role, and its *Relationship to the graph* cell.

    Fails loudly rather than guessing if the section carries no such table or more than one,
    for the same reason `test_console_hierarchy.py` refuses to pick between two fenced blocks:
    a parser that silently matches the wrong table is green while drifted.
    """
    lines = _m5_section(SPEC_PATH.read_text(encoding="utf-8")).splitlines()
    headers = [i for i, line in enumerate(lines) if _TABLE_HEADER.match(line.strip())]
    if len(headers) != 1:
        raise AssertionError(
            f"Expected exactly one 'Role | Examples | Relationship to the graph' table in the "
            f"M5 section of {SPEC_PATH}, found {len(headers)}."
        )
    rows: list[tuple[str, str]] = []
    for line in lines[headers[0] + 1 :]:
        stripped = line.strip()
        if not stripped.startswith("|"):
            break
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        if len(cells) != 3:
            raise AssertionError(
                f"Malformed row in the M5 role table of {SPEC_PATH}: {stripped!r}"
            )
        bold = _BOLD.match(cells[0])
        rows.append((bold.group(1) if bold else cells[0], cells[2]))
    if not rows:
        raise AssertionError(f"The M5 role table in {SPEC_PATH} has no rows.")
    return rows


def _console_roles() -> list[tuple[str, str, str | None]]:
    """`SIGNAL_ROLES`, in declaration order: the role, its relationship sentence, its source."""
    text = ROLES_PATH.read_text(encoding="utf-8")
    array = _ROLES_ARRAY.search(text)
    if array is None:
        raise AssertionError(
            f"Could not find `export const SIGNAL_ROLES = [...] as const` in {ROLES_PATH}."
        )
    order = _IDENTIFIER.findall(array.group(1))
    if not order:
        raise AssertionError(
            f"`SIGNAL_ROLES` in {ROLES_PATH} lists no role constants. This test reads the "
            "array as the level's declared order; an array built some other way needs this "
            "parser updated rather than bypassed."
        )
    roles: list[tuple[str, str, str | None]] = []
    for name in order:
        declaration = re.search(
            rf"export const {name}\b.*?=\s*\{{(.*?)\n\}}", text, re.DOTALL
        )
        if declaration is None:
            raise AssertionError(
                f"`SIGNAL_ROLES` names {name}, but {ROLES_PATH} declares no such constant."
            )
        body = declaration.group(1)
        role = _ROLE_FIELD.search(body)
        relationship = _RELATIONSHIP_FIELD.search(body)
        source = _SOURCE_FIELD.search(body)
        if role is None or relationship is None or source is None:
            raise AssertionError(
                f"{name} in {ROLES_PATH} is missing `role`, `relationship` or `source`."
            )
        raw_source = source.group(1)
        roles.append(
            (role.group(1), relationship.group(1), None if raw_source == "null" else raw_source.strip('"'))
        )
    return roles


def test_the_console_names_the_three_roles_the_specification_defines_in_its_order() -> None:
    assert [role for role, _, _ in _console_roles()] == [
        role for role, _ in _specification_roles()
    ], (
        "The Signals level groups panels by the roles the design document's M5 table defines. "
        "A role the console invents, drops or reorders is the console becoming a second "
        "authority on the vocabulary -- amend the specification first."
    )


def test_every_role_carries_the_specifications_own_relationship_sentence() -> None:
    expected = dict(_specification_roles())
    for role, relationship, _ in _console_roles():
        assert relationship == expected[role], (
            f"The Signals level's sentence for {role!r} is not the M5 table's. A paraphrase "
            "reads fine and drifts silently; the table is the authority."
        )


def test_a_role_the_header_calls_attached_names_a_path_the_api_serves() -> None:
    served = set(_API_ROUTE.findall(API_APP_PATH.read_text(encoding="utf-8")))
    attached = [(role, source) for role, _, source in _console_roles() if source is not None]
    assert attached, (
        "No role declares a source, so the header would report the whole level unattached. "
        "That is a claim about this deployment, and it is false while the index and the "
        "observed-telemetry tables are still queryable."
    )
    for role, source in attached:
        assert source in served, (
            f"{role!r} declares {source!r}, which {API_APP_PATH} does not serve. The header "
            "reads a declared source as 'an integration is attached', so a path nothing "
            "answers puts a role on the attached side of that sentence with nothing behind it."
        )


def test_the_level_draws_an_unattached_role_with_the_state_written_for_it() -> None:
    page = SIGNALS_PAGE_PATH.read_text(encoding="utf-8")
    assert "NotAttachedState" in page, (
        "The Signals level renders a role with nothing attached, and `not-attached-state.tsx` "
        "is the component that says so."
    )
    assert "EmptyState" not in page, (
        "`EmptyState` documents itself as 'the API answered, and the answer was nothing'. "
        "Nothing answered for an unattached role, because nothing was asked -- rendering one "
        "as the other puts a role nobody configured on the same axis as a role that was "
        "checked and found idle."
    )


def test_the_page_reads_each_role_name_from_the_roster_rather_than_repeating_it() -> None:
    page = SIGNALS_PAGE_PATH.read_text(encoding="utf-8")
    for role, _ in _specification_roles():
        assert role not in page, (
            f"{role!r} appears literally in {SIGNALS_PAGE_PATH}. The header names which roles "
            "have an integration attached and which do not, and it builds that sentence from "
            "`SIGNAL_ROLES`; a role name written here as well is the same fact in two places, "
            "which is how the header and the panels come to disagree."
        )
