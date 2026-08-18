"""Every route a screen links to must be one the router can serve.

**A path is a string, so nothing in the toolchain catches this.** `M14-W386` collapsed
`web/src/lib/routes.ts` from two regions to one, making every address workspace-scoped
(`/repositories/:repoId/...`). Links written against the old shape still compile, still pass every
component test, and resolve at runtime to *"No screen at this address."*

Measured the day the collapse landed: **eighteen dead links across four lanes** — eight in Lane C's
own features, ten elsewhere. Every one typechecked. `tsc` cannot help, `vitest` renders components
rather than resolving routes, and `oxlint` has no opinion about a template literal. This file is the
only thing between a route rename and a screen that answers nothing.

It is a lint rather than a router assertion on purpose. Asserting that every declared route renders
proves the registry is coherent; this asks the opposite and more useful question — whether anything
*links to* an address the registry does not declare.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_SRC = REPO_ROOT / "web" / "src"

# A `to=` destination written as a literal or a template literal. Anything computed by a function
# is out of scope: this catches the addresses spelled in a screen, which is where the rename bites.
_LINK = re.compile(r"""to=(?:\{`(/[^`]*)`\}|"(/[^"]*)")""")

# Addresses that are correct without a workspace. `/` is the shell's own root and `/settings`
# configures the system rather than describing one workspace's graph -- `routes.ts` declares it as
# a destination rather than a level for exactly that reason.
UNSCOPED_BY_DESIGN = {"/", "/settings"}

# Links that are dead today, each recorded with the lane that owns the file.
#
# **A baseline is not permission.** It exists so this gate can go green on the day it lands without
# a lane having to fix another lane's screens first, which is the same shape as the dead-symbol
# baseline. Each entry is a screen that currently sends a reader nowhere, and removing an entry is
# the fix rather than the paperwork.
KNOWN_DEAD: frozenset[str] = frozenset({
    "features/fleet/runs-table.tsx",
})


def unscoped_links(source: str) -> list[str]:
    """Every destination in `source` that is neither workspace-scoped nor unscoped by design."""
    found = []
    for literal, quoted in _LINK.findall(source):
        path = literal or quoted
        if path.startswith("/repositories/") or path in UNSCOPED_BY_DESIGN:
            continue
        found.append(path)
    return found


def test_a_workspace_scoped_link_is_accepted():
    assert unscoped_links('to={`/repositories/${id}/findings/${f}`}') == []


def test_the_two_addresses_that_are_correct_without_a_workspace_are_accepted():
    assert unscoped_links('to="/"') == []
    assert unscoped_links('to="/settings"') == []


def test_a_link_to_the_collapsed_region_is_caught():
    """The exact shape `M14-W386` orphaned, and the reason this file exists."""
    assert unscoped_links('to={`/findings/${encodeURIComponent(id)}`}') == ["/findings/${encodeURIComponent(id)}"]


def test_the_old_query_parameter_form_is_caught_too():
    """The collapse turned `?repo_id=` into a path segment. A link still passing it as a query is
    pointing at the previous scheme and lands on nothing."""
    assert unscoped_links('to={`/vendors/${v}?repo_id=${r}`}') != []


def test_no_screen_links_to_an_address_the_router_cannot_serve():
    """The gate itself, over every screen in the console.

    A file appears here when it links somewhere unscoped and is not in `KNOWN_DEAD`. Fix the link
    rather than widening the baseline: the baseline is a record of what was already broken when
    this landed, not a place to put new breakage.
    """
    offenders: dict[str, list[str]] = {}
    for path in sorted(WEB_SRC.rglob("*.tsx")) + sorted(WEB_SRC.rglob("*.ts")):
        if "vendor/supabase" in path.as_posix():
            continue
        relative = path.relative_to(WEB_SRC).as_posix()
        if relative in KNOWN_DEAD:
            continue
        dead = unscoped_links(path.read_text(encoding="utf-8"))
        if dead:
            offenders[relative] = dead

    assert not offenders, (
        "these screens link to addresses routes.ts does not declare, so a reader who clicks gets "
        '"No screen at this address." Every route is workspace-scoped as of M14-W386:\n'
        + "\n".join(f"  {name}: {', '.join(paths)}" for name, paths in offenders.items())
    )


def test_the_baseline_names_only_files_that_are_still_broken():
    """A baseline entry that has been fixed must be removed, or this gate quietly stops watching a
    file. The same argument the dead-symbol baseline makes about its own expiry."""
    stale = [
        name
        for name in sorted(KNOWN_DEAD)
        if not unscoped_links((WEB_SRC / name).read_text(encoding="utf-8"))
    ]

    assert not stale, (
        "these files no longer link anywhere dead, so their baseline entries are stale and must be "
        f"deleted -- otherwise the gate stops watching them: {stale}"
    )
