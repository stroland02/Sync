"""Severity that carries what oasdiff said, rather than a constant that says nothing.

`2026-07-29-oasdiff-determinism.md` measured the defect: every one of 792,552 records was
`level: 2`, oasdiff's *warning*, and `to_vendor_changes` stamped `severity="breaking"` on all of
them. `2026-07-27-sync-routing-matrix.md` had already named it as a prerequisite it was
deliberately not doing -- *"an endpoint deleted without deprecation and an optional response
property removed arrive downstream indistinguishable"*.

The trap that document names is the reason for the first test here. The two oasdiff surfaces
encode `level` differently -- an integer in a `breaking` record, a string in the `checks`
catalogue -- and only the warning value had been cross-referenced. Nothing here assumes the
correspondence: it is read off the pinned binary, by joining a record to the catalogue on the
rule id, which is the only thing both surfaces agree about.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from sync.signals.oasdiff import (
    LEVEL_SEVERITY,
    UnknownOasdiffLevel,
    _binary,
    to_vendor_changes,
)

BINARY = Path(__file__).parents[1] / "tools" / "oasdiff.exe"
BINARY_POSIX = Path(__file__).parents[1] / "tools" / "oasdiff"

needs_binary = pytest.mark.skipif(
    not (BINARY.exists() or BINARY_POSIX.exists()),
    reason="needs tools/oasdiff; run scripts/bootstrap_tools.sh",
)

# Levels observed on a `breaking` record. `error` and `warning` are the two the command emits;
# `info` is reachable only through `changelog`, and is mapped because it is a level the type
# already expresses rather than because this surface produces it.
ERROR, WARNING, INFO = 3, 2, 1


def _record(rule_id: str, level: int) -> dict:
    return {
        "id": rule_id,
        "text": "removed the optional property `note` from the response",
        "level": level,
        "operationId": "getThing",
        "operation": "GET",
        "path": "/v1/thing",
    }


def _spec(paths: dict) -> dict:
    return {"openapi": "3.0.3", "info": {"title": "t", "version": "1"}, "paths": paths}


def _operation(properties: dict | None = None) -> dict:
    return {
        "get": {
            "operationId": "getThing",
            "responses": {
                "200": {
                    "description": "ok",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {"id": {"type": "string"}, **(properties or {})},
                            }
                        }
                    },
                }
            },
        }
    }


def _run(command: str, base: dict, revision: dict, tmp_path: Path) -> list[dict]:
    (tmp_path / "base.json").write_text(json.dumps(base), encoding="utf-8")
    (tmp_path / "revision.json").write_text(json.dumps(revision), encoding="utf-8")
    result = subprocess.run(
        [_binary(), command, str(tmp_path / "base.json"), str(tmp_path / "revision.json"),
         "--format", "json"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout) if result.stdout.strip() else []


def _catalogue() -> dict[str, dict]:
    result = subprocess.run(
        [_binary(), "checks", "--format", "json"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    return {entry["id"]: entry for entry in json.loads(result.stdout)}


# --- the encoding, read off the binary rather than assumed ------------------------------


@needs_binary
def test_the_two_surfaces_encode_level_differently_and_the_integers_cross_reference(tmp_path):
    """The trap the routing specification names, checked rather than taken on trust.

    A `breaking` record carries `level` as an integer and the `checks` catalogue carries it as a
    string. Nothing but the rule id is common to both, so the id is what the join runs on. Each
    of the three integers the mapping knows is established here from the binary's own answers --
    an inferred correspondence would agree with a mapping that inferred it the same wrong way.
    """
    catalogue = _catalogue()
    assert {type(entry["level"]).__name__ for entry in catalogue.values()} == {"str"}

    removed = _run("breaking", _spec({"/v1/thing": _operation()}), _spec({}), tmp_path)
    optional = _run(
        "breaking",
        _spec({"/v1/thing": _operation({"note": {"type": "string"}})}),
        _spec({"/v1/thing": _operation()}),
        tmp_path,
    )
    added = _run(
        "changelog",
        _spec({"/v1/thing": _operation()}),
        _spec({"/v1/thing": _operation({"note": {"type": "string"}})}),
        tmp_path,
    )

    observed = {}
    for record in [*removed, *optional, *added]:
        assert isinstance(record["level"], int), "a breaking record's level is an integer"
        observed[record["level"]] = catalogue[record["id"]]["level"]

    assert observed == {ERROR: "error", WARNING: "warning", INFO: "info"}


@needs_binary
def test_every_level_the_mapping_knows_is_one_the_catalogue_declares(tmp_path):
    """The mapping's domain is oasdiff's, not one invented here. A level in the table that the
    binary never emits would be a rule this repository made up about a tool it does not own."""
    declared = {entry["level"] for entry in _catalogue().values()}

    assert declared == {"error", "warning", "info"}
    assert len(LEVEL_SEVERITY) == len(declared)


# --- what a record becomes ---------------------------------------------------------------


def test_a_warning_level_record_does_not_become_breaking():
    """The defect. `oasdiff breaking` returns warning-level records, not only errors, and every
    record the determinism report measured was one -- so stamping them `breaking` made the field
    a constant and a triage queue ordered by it ordered by nothing."""
    changes = to_vendor_changes(
        [_record("response-optional-property-removed", WARNING)], "stripe", "v1", "v2"
    )

    assert [change.severity for change in changes] == ["warning"]


def test_an_error_level_record_does_become_breaking():
    """Without this, a mapping that answered `warning` for everything would pass the test above
    and be exactly as uninformative as the constant it replaced."""
    changes = to_vendor_changes(
        [_record("api-path-removed-without-deprecation", ERROR)], "stripe", "v1", "v2"
    )

    assert [change.severity for change in changes] == ["breaking"]


def test_two_records_oasdiff_graded_differently_arrive_distinguishable():
    """What the routing specification asked for, stated as the thing it asked for: an endpoint
    deleted without deprecation and an optional response property removed used to arrive
    indistinguishable, and one line was where the distinction was thrown away."""
    changes = to_vendor_changes(
        [
            _record("api-path-removed-without-deprecation", ERROR),
            _record("response-optional-property-removed", WARNING),
        ],
        "stripe", "v1", "v2",
    )

    assert [change.severity for change in changes] == ["breaking", "warning"]


def test_an_info_level_record_is_carried_as_info():
    """Reachable through `changelog` rather than `breaking`, and mapped because the type already
    expresses it. A level this module knew about and declined to map would be the same silent
    default the whole change exists to remove."""
    changes = to_vendor_changes([_record("endpoint-added", INFO)], "stripe", "v1", "v2")

    assert [change.severity for change in changes] == ["info"]


# --- what an unrecognised level does ------------------------------------------------------


def test_a_level_the_mapping_does_not_know_fails_loudly_naming_it():
    """A new oasdiff release adding a level is a finding about the tool, not a record to guess
    at. Defaulting it to `breaking` is precisely the failure being fixed, one release later and
    harder to see."""
    with pytest.raises(UnknownOasdiffLevel, match="4"):
        to_vendor_changes([_record("something-new", 4)], "stripe", "v1", "v2")


def test_a_record_with_no_level_fails_loudly():
    """Absence is not a level. A record whose grading cannot be read is a record whose severity
    cannot be established, and the safe answer is to refuse rather than to pick one."""
    record = _record("response-optional-property-removed", WARNING)
    del record["level"]

    with pytest.raises(UnknownOasdiffLevel):
        to_vendor_changes([record], "stripe", "v1", "v2")


def test_a_level_encoded_as_a_string_fails_loudly():
    """The two surfaces disagree on the type, so a record arriving with the catalogue's encoding
    means oasdiff changed the record surface. Coercing it would hide exactly that."""
    with pytest.raises(UnknownOasdiffLevel):
        to_vendor_changes(
            [_record("response-optional-property-removed", "warning")], "stripe", "v1", "v2"
        )


# --- the frozen contract -------------------------------------------------------------------


def test_the_tool_schemas_did_not_move():
    """`severity` reaches the MCP graph surface, whose four tool schemas are frozen. The golden
    file is the executable form of that freeze: this change widens what the field can hold and
    must not widen what the schema declares, which it does not, because the schema types it as a
    string and enumerates nothing.
    """
    from sync.mcp.registry import schemas_as_data

    golden = json.loads(
        (Path(__file__).parent / "golden" / "tool_schemas.json").read_text(encoding="utf-8")
    )

    assert schemas_as_data() == golden
