"""Every internal link in the console points at a route the console declares.

## The defect this exists to catch, which shipped and stayed green

`M14-W386` moved all ten routes under `/repositories/:repoId/`. Twelve link sites went on building
the old unscoped `/findings/{id}` and `/vendors/{id}` paths, and `App.tsx` ends its table with
`<Route path="*" element={UnknownRoute}>` and carries no legacy redirect -- so every one of them
rendered *No screen at this address*. Clicking a finding anywhere in the console 404'd.

**Nothing caught it, and nothing could have.** `npm run build` was clean, 771 console tests passed,
`lint` reported no errors, and the Python guards were green: a `<Link to=...>` is a string, and no
compiler checks a string against a route table. The registry knows every path the application
serves and the source knows every path it asks for; until this file, the two were never compared.

## What is asserted, and why it is a first segment rather than a full match

A link's full path is usually a template -- `` `/repositories/${encodeURIComponent(repoId)}/runs` ``
-- and reconstructing the exact route pattern from an expression means evaluating TypeScript, which
is a different and much worse project. The **first path segment is nearly always literal**, and it
is the segment that carries the whole failure: `/findings/...` and `/vendors/...` are wrong at
character two, not at their parameters.

So the rule is: the first segment of every absolute internal link must be a first segment some
declared route actually has. That is cheap, has no false negatives for the class of defect that
occurred, and does not pretend to verify parameters it cannot see.

**A path built entirely from an expression is skipped rather than guessed at.** A link opening with
`${` has no literal first segment; asserting anything about it would be asserting about the variable
name. That is a stated limit of this guard, not an oversight -- `destinationHref` in
`layouts/app-frame.tsx` builds paths from the registry itself, which is the pattern that cannot
drift and the one more code should use.
"""

from __future__ import annotations

import re
from pathlib import Path

WEB_SRC = Path(__file__).resolve().parents[1] / "web" / "src"
ROUTES_TS = WEB_SRC / "lib" / "routes.ts"

# `path: "/repositories/:repoId/runs",` in the registry and the destinations table alike.
DECLARED_PATH = re.compile(r'^\s*path:\s*"(/[^"]*)"', re.MULTILINE)

# `to="/settings"` and `` to={`/repositories/${x}`} `` -- the two spellings react-router takes.
# `href` is deliberately not matched: an `href` in this console is an external link or a mailto,
# and an internal destination always goes through `Link`.
LINK = re.compile(r"""to=(?:"(/[^"]*)"|\{`(/[^`]*)`\})""")

# A path built into a variable and passed to `to` somewhere else -- `` const path = `/vendors/${id}` ``
# and `` return `/findings/${id}/workflow` ``. Two of the thirteen sites this guard first caught were
# spelled that way, so matching only the inline form would have left them live while reporting green.
ASSIGNED = re.compile(r"""(?:=|return)\s+(?:"(/[^"]*)"|`(/[^`]*)`)""")

# `/api/...` is a transport path, not a route. It is the one prefix that legitimately starts with a
# segment no route declares, and `api/client.ts` is where those belong.
TRANSPORT = "api"

# The two links that cannot be built from the data in hand, named individually so the exemption
# cannot quietly widen.
#
# Both link from a *run* to its finding, and `RunRow` carries no repository -- `migration_outcome`
# stores none, by the schema decision that makes the corpus safe to aggregate across customers. The
# destination is genuinely underdetermined: the run's finding may belong to a workspace other than
# the one the reader is in, so taking the workspace from the address would render a finding under a
# workspace that does not contain it.
#
# **What retires this:** the owner ruled these resolve by asking `/api/findings/{id}` which
# workspace the finding belongs to and navigating with the answer. When that lands, both entries
# come out of this set and the set goes with them. Until then these two links are known-broken
# rather than believed-working, which is the distinction the entry buys.
UNRESOLVABLE_UNTIL_LOOKUP = {
    ("features/fleet/proposed-patch.ts", 14),
    ("features/fleet/runs-table.tsx", 153),
}


def declared_roots() -> set[str]:
    """The first path segment of every route the application serves."""
    source = ROUTES_TS.read_text(encoding="utf-8")
    roots = set()
    for path in DECLARED_PATH.findall(source):
        segments = [s for s in path.split("/") if s]
        # `/` itself is a real destination -- the workspace picker.
        roots.add(segments[0] if segments else "")
    return roots


def source_files() -> list[Path]:
    """Every non-test module under `web/src`, vendored components included.

    Vendored Supabase code is in scope on purpose: it is ours once it is in this tree, and a
    vendored component that links somewhere is subject to this console's route table like any
    other. Test files are excluded because a test may legitimately render a component under a
    made-up address to prove what it does there.
    """
    return [
        p
        for p in sorted(WEB_SRC.rglob("*"))
        if p.suffix in {".ts", ".tsx"} and ".test." not in p.name
    ]


def test_every_internal_link_starts_at_a_declared_route_root() -> None:
    roots = declared_roots()
    assert roots, "parsed no routes out of routes.ts -- the guard would pass vacuously"

    violations: list[str] = []
    for path in source_files():
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            # A path named inside a comment is prose about a route, not a request for one. Every
            # module here cites addresses in its docstring, so matching them would bury the real
            # findings under dozens of mentions of `/findings/f-91ac`.
            stripped = line.lstrip()
            if stripped.startswith(("*", "//", "/*")):
                continue
            for quoted, templated in LINK.findall(line) + ASSIGNED.findall(line):
                target = quoted or templated
                # The query string is not part of the path, and leaving it attached makes the first
                # segment read as `detectors?repo_id=${...}` in the failure message.
                path_only = target.split("?", 1)[0]
                segments = [s for s in path_only.split("/") if s]
                if not segments:
                    continue  # `to="/"` -- the workspace picker.
                first = segments[0]
                if first.startswith("${"):
                    continue  # Built from the registry; see this module's docstring.
                if first == TRANSPORT:
                    continue
                if (path.relative_to(WEB_SRC).as_posix(), line_number) in UNRESOLVABLE_UNTIL_LOOKUP:
                    continue
                if first not in roots:
                    violations.append(
                        f"{path.relative_to(WEB_SRC)}:{line_number} links to {target!r}, "
                        f"whose first segment {first!r} is not a route root. "
                        f"Declared roots: {sorted(roots)}"
                    )

    assert not violations, (
        "a link to an undeclared route renders the 404 screen, and neither the compiler nor the "
        "test suite can see it -- a `to` is a string:\n" + "\n".join(violations)
    )
