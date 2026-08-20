"""The keys the API emits, against the keys `web/src/api/types.ts` declares.

**Three of these landed in one night and `tsc` could not catch one of them**, because the
TypeScript was correct every time and the *type* was what was wrong. A compiler checks the console
against its own beliefs; the beliefs were the defect.

- `CI-W379` — `repositories` did not exist on the payload, so the repository selector was always
  empty and always showed a hard-coded value.
- `CI-W399` — `ObservedTelemetryResponse` omitted `telemetry_attached_at`, so an empty calls page
  *with* telemetry attached and one with *no* attachment rendered identically.
- `CI-W406` — the graph emits `rung`, the type declared `binding_rung`, and every edge on the
  indexing canvas carried `undefined` for the one field that screen exists to display.

**Both directions fail.** A field the payload sends that no type declares is as much a defect as
the reverse: it is how a console silently ignores data it was given, and nothing on screen says so.

**The truth is the running API.** These ask `app_factory` -- the same wiring `python -m sync.api`
runs -- over a real, empty graph, so the emitted side of the comparison is what a console actually
receives. A pinned key set would have been a fourth place for the same
fact to disagree with itself, which is the shape of the bug rather than a check on it.

**The first draft got this wrong and it is worth recording.** It read payloads through
`test_api_routes`' fakes and immediately "found" that `OverviewResponse` declares `bindings_by_rung`
and the payload never sends it. The real builder emits that key on `graph_views.py:591`; the *fake*
did not. A second draft called the view functions directly and "found" `severity_counts` missing --
which the *route* adds at `app.py:237` by composing a second reader. A check whose truth is a fake measures the fake, and
would have sent somebody hunting a bug that was not there -- while staying silent about whatever
the fake happens to emit correctly and production does not.

What this does not cover, stated rather than implied: only the shapes listed in `CONTRACTS`, only
their top level, and only fields a representative payload actually exercises. A route absent from
that list is unchecked, and an optional field the fake never populates cannot be verified here.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

TYPES_TS = TESTS.parent / "web" / "src" / "api" / "types.ts"

_INTERFACE = re.compile(
    r"^export interface (?P<name>\w+)(?:<[^>]*>)?"
    r"(?:\s+extends\s+(?P<bases>[^{]+))?\s*\{(?P<body>.*?)^\}",
    re.MULTILINE | re.DOTALL,
)
# A field at the interface's own level. Deeper indentation is a nested object literal and its keys
# are not this interface's keys; a comment line never matches because `*` and `/` are not word
# characters.
_FIELD = re.compile(r"^  (?P<name>\w+)(?P<optional>\??):", re.MULTILINE)


def _interfaces(source: str) -> dict[str, dict]:
    found = {}
    for match in _INTERFACE.finditer(source):
        bases = match.group("bases") or ""
        found[match.group("name")] = {
            "required": {f.group("name") for f in _FIELD.finditer(match.group("body"))
                         if not f.group("optional")},
            "optional": {f.group("name") for f in _FIELD.finditer(match.group("body"))
                         if f.group("optional")},
            # `Page<RiskRow>` contributes `Page`'s own fields; the parameter is the item type and
            # is checked separately as its own shape.
            "bases": [b.split("<")[0].strip() for b in bases.split(",") if b.strip()],
        }
    return found


def declared_fields(interfaces: dict[str, dict], name: str) -> tuple[set[str], set[str]]:
    """Every field `name` declares, its bases included. Returns `(required, optional)`."""
    entry = interfaces[name]
    required, optional = set(entry["required"]), set(entry["optional"])
    for base in entry["bases"]:
        if base in interfaces:
            base_required, base_optional = declared_fields(interfaces, base)
            required |= base_required
            optional |= base_optional
    return required, optional


def _types_source() -> str:
    if not TYPES_TS.is_file():
        pytest.skip("web/src/api/types.ts is absent; this checkout carries no console")
    return TYPES_TS.read_text(encoding="utf-8")


# --- the parser, pinned before it is trusted ----------------------------------------


def test_the_parser_reads_fields_and_marks_optionals():
    parsed = _interfaces(
        "export interface A {\n  one: string\n  two?: number\n}\n"
    )

    assert parsed["A"]["required"] == {"one"}
    assert parsed["A"]["optional"] == {"two"}


def test_the_parser_follows_extends():
    parsed = _interfaces(
        "export interface A {\n  one: string\n}\n"
        "export interface B extends A {\n  two: string\n}\n"
    )

    required, _ = declared_fields(parsed, "B")
    assert required == {"one", "two"}


def test_the_parser_ignores_keys_of_a_nested_object():
    """A nested literal's keys belong to it, not to the interface, and counting them would make
    this check fail on shapes that are perfectly correct."""
    parsed = _interfaces(
        "export interface A {\n  one: {\n    buried: string\n  }\n}\n"
    )

    assert parsed["A"]["required"] == {"one"}


def test_the_parser_finds_the_real_interfaces():
    """The guard against a regex that quietly matches nothing -- which would make every contract
    below pass by comparing an empty set to an empty set."""
    parsed = _interfaces(_types_source())

    assert "OverviewResponse" in parsed
    required, _ = declared_fields(parsed, "OverviewResponse")
    assert "repo_id" in required and "indexed_at" in required, (
        "OverviewResponse must carry its own fields and Provenance's, or extends is not resolving"
    )


# --- the contract itself -------------------------------------------------------------

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")


@pytest.fixture(scope="module")
def client():
    """The production wiring over a real, empty graph.

    `app_factory` is what `python -m sync.api` runs, so the keys this yields are the keys a console
    actually receives -- route composition included. That last part is not a detail: `/api/overview`
    merges two independently-computed readers and adds `severity_counts` at `app.py:237`, so a check
    that called `overview_summary` alone would report a field the route sends every time as missing.

    Empty is deliberate. Every key checked below sits in an unconditional dict literal, so the shape
    does not depend on rows -- and a key that only appears once data exists is one this check says
    plainly it does not cover.
    """
    os.environ.setdefault("SYNC_GRAPH_DSN", DSN)
    from starlette.testclient import TestClient

    from sync.api.__main__ import app_factory
    from sync.graph.store import GraphStore

    GraphStore(os.environ["SYNC_GRAPH_DSN"]).apply_schema()
    return TestClient(app_factory())


#: `(interface, route)`. The route is asked at the scope that carries every key: `/api/overview`
#: omits `repositories` when narrowed to one repository, and the fleet scope is the fuller shape.
CONTRACTS = [
    ("OverviewResponse", "/api/overview"),
    ("RunsPage", "/api/runs"),
    ("DetectorAccountabilityResponse", "/api/detectors"),
]

#: Keys the API sends today that `types.ts` does not declare, per interface.
#:
#: **A baseline is not permission.** It is here so this check can land green on the day it is
#: written without one lane editing another's types first, exactly as the dead-route lint carries
#: its own. Each entry is data the console is handed and silently ignores, and removing an entry is
#: the fix rather than the paperwork.
#:
#: `repositories` is the sharpest of the three: `CI-W379` was the console showing a hard-coded value
#: because the type said the field did not exist -- while `/api/overview` had been sending it all
#: along. The same field, found from the other side.
KNOWN_UNDECLARED: dict[str, set[str]] = {
    "OverviewResponse": {"repositories"},
}


@pytest.mark.parametrize("interface, route", CONTRACTS)
def test_the_payload_and_the_type_declare_the_same_keys(interface, route, client):
    """Either direction is a defect, and the message says which.

    A declared-but-absent field is what the console reads as `undefined` -- all three of the night's
    bugs. An emitted-but-undeclared field is data the console was given and silently ignores, which
    is quieter and no less wrong.
    """
    interfaces = _interfaces(_types_source())
    if interface not in interfaces:
        pytest.fail(f"web/src/api/types.ts declares no interface named {interface}")

    required, optional = declared_fields(interfaces, interface)
    response = client.get(route)
    assert response.status_code == 200, f"{route} answered {response.status_code}"
    emitted = set(response.json().keys())

    missing = required - emitted
    undeclared = emitted - required - optional - KNOWN_UNDECLARED.get(interface, set())

    assert not missing, (
        f"{interface} declares {sorted(missing)} and {route} never sends it, so the console "
        "reads undefined for those fields and no compiler will say so"
    )
    assert not undeclared, (
        f"{route} sends {sorted(undeclared)} and {interface} declares no such field, so the "
        "console is given data it silently ignores"
    )


@pytest.mark.parametrize("interface", sorted(KNOWN_UNDECLARED))
def test_the_baseline_names_only_keys_still_undeclared(interface):
    """A baselined key that has since been declared must leave the baseline.

    Otherwise the entry stays as a standing exemption for a field that is now fine, and the next
    genuine drift on that interface is waved through under it -- the same argument the dead-route
    lint makes about its own expiry.

    Parametrized over the baseline itself rather than over every contract, so there is no case with
    nothing to assert. A skip here would report as neither pass nor fail for a reason that is not a
    platform or an absent tool, which `.claude/rules/test-discipline.md` calls the same defect as a
    test that cannot fail.
    """
    baseline = KNOWN_UNDECLARED[interface]
    interfaces = _interfaces(_types_source())
    required, optional = declared_fields(interfaces, interface)

    settled = baseline & (required | optional)
    assert not settled, (
        f"{sorted(settled)} is declared on {interface} now, so its baseline entry is stale and "
        "must be deleted -- otherwise this check stops watching that key"
    )
