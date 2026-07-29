import subprocess
from pathlib import Path

import pytest

from sync.core import VendorChange
from sync.signals import oasdiff
from sync.signals.oasdiff import (
    changed_field,
    run_oasdiff_breaking,
    run_oasdiff_checks,
    to_vendor_changes,
)

FIXTURES = Path(__file__).parent / "fixtures" / "specs"


def test_breaking_changes_are_detected_regardless_of_exit_code():
    records = run_oasdiff_breaking(FIXTURES / "charges_base.json", FIXTURES / "charges_revision.json")
    assert records, "oasdiff reported no breaking changes for a fixture pair with two hand-labelled ones"


def test_identical_specs_produce_no_changes():
    records = run_oasdiff_breaking(FIXTURES / "charges_base.json", FIXTURES / "charges_base.json")
    assert records == []


def test_nonzero_exit_raises_instead_of_returning_empty_list(monkeypatch):
    """A crashed or killed oasdiff must not be mistaken for "no breaking changes".

    A process that dies before writing any JSON returns exit code 1 and empty
    stdout -- the same stdout a clean "no findings" run would never produce,
    since oasdiff always writes the literal `[]` for that case. Any non-zero
    exit has to raise so a killed process can't be read as a clean report.
    """

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args, returncode=1, stdout="", stderr="killed")

    monkeypatch.setattr(oasdiff.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError):
        run_oasdiff_breaking(FIXTURES / "charges_base.json", FIXTURES / "charges_revision.json")


def test_records_convert_to_vendor_changes_with_operation_and_severity():
    """Severity is what oasdiff graded the record, which for this fixture pair is `warning`.

    Both of its records -- `request-property-removed` and `response-optional-property-removed` --
    are `level: 2`, which `oasdiff checks` calls a warning. This assertion read `breaking` for as
    long as `to_vendor_changes` stamped that on everything, and it passed for the same reason the
    field carried no information.
    """
    records = run_oasdiff_breaking(FIXTURES / "charges_base.json", FIXTURES / "charges_revision.json")
    changes = to_vendor_changes(records, vendor_id="stripe", from_version="base", to_version="revision")
    assert all(c.vendor_id == "stripe" for c in changes)
    assert all(r["level"] == 2 for r in records)
    assert all(c.severity == "warning" for c in changes)
    assert all(c.source == "oasdiff" for c in changes)
    assert any(c.operation_id == "PostCharges" for c in changes)


def test_path_ptr_holds_the_url_path_not_a_json_pointer():
    """Pins what `path_ptr` actually contains, because two specs once said otherwise.

    `2026-07-26-sync-public-change-feed.md` illustrated `path_ptr` as `/data/status`, and
    `2026-07-26-sync-observed-contract-drift.md` built a one-join claim on that reading. Both
    were wrong: oasdiff reports `path` as the operation's URL, and that is what is stored. A
    join written against the pointer reading matches nothing, so the contradiction is worth a
    test rather than a comment -- prose drifts from code silently, an assertion does not.
    """
    records = run_oasdiff_breaking(FIXTURES / "charges_base.json", FIXTURES / "charges_revision.json")
    changes = to_vendor_changes(records, vendor_id="stripe", from_version="base", to_version="revision")

    assert changes, "fixture pair produced no changes; this test cannot check anything"
    for change in changes:
        assert change.path_ptr.startswith("/v1/"), (
            f"path_ptr held {change.path_ptr!r}; it is oasdiff's URL path, not a JSON Pointer"
        )


def test_kind_is_the_oasdiff_rule_id():
    """`VendorChange.kind` is `record["id"]`, one of the rules `oasdiff checks` enumerates.

    Anything switching on `kind` is switching on that enum, so it needs a default branch and
    a completeness check against the pinned binary -- never a hand-maintained copy of the list.
    """
    records = run_oasdiff_breaking(FIXTURES / "charges_base.json", FIXTURES / "charges_revision.json")
    changes = to_vendor_changes(records, vendor_id="stripe", from_version="base", to_version="revision")

    assert changes
    for change, record in zip(changes, records, strict=True):
        assert change.kind == record["id"]


def test_the_check_catalogue_carries_the_axes_routing_depends_on():
    """The routing matrix keys on oasdiff's metadata, not on its 506 identifiers.

    `2026-07-27-sync-routing-matrix.md` routes on (kind, action, direction) precisely because a
    hand-maintained table of every rule ID would rot on each oasdiff release. That trade only
    holds while the catalogue actually carries those axes, so this asserts the shape the design
    rests on. If a future oasdiff drops or renames one, the matrix is unimplementable and this
    test is where that is discovered.
    """
    catalogue = run_oasdiff_checks()

    assert len(catalogue) > 100, "catalogue implausibly small; oasdiff output shape likely changed"
    for entry in catalogue:
        assert {"id", "level", "direction", "kind", "action"} <= entry.keys()

    levels = {entry["level"] for entry in catalogue}
    assert "error" in levels and "warning" in levels

    # Tier -1 in the matrix is justified entirely by this category existing: lifecycle rules
    # describe how the vendor documented a deprecation, so no edit to consumer code resolves
    # them. If the category disappears, that row loses its reason to exist.
    assert any(entry["kind"] == "lifecycle" for entry in catalogue)


def test_breaking_output_is_not_limited_to_error_level():
    """`run_oasdiff_breaking` returns a mix of severities, which `to_vendor_changes` flattens.

    The fixture pair's two records are both classified `warning` by the catalogue, yet
    `to_vendor_changes` stamps every record `severity="breaking"`. Routing wants that
    distinction, so this pins the discrepancy rather than leaving it to be rediscovered:
    the day severity is carried through properly, this test is what says so.
    """
    catalogue = {entry["id"]: entry for entry in run_oasdiff_checks()}
    records = run_oasdiff_breaking(FIXTURES / "charges_base.json", FIXTURES / "charges_revision.json")

    assert records
    reported_levels = {catalogue[r["id"]]["level"] for r in records if r["id"] in catalogue}
    assert reported_levels, "no fixture record matched the catalogue; the id domain diverged"
    assert reported_levels != {"error"}, (
        "fixture records are all error-level; the claim that breaking output mixes severities "
        "no longer holds and the routing spec needs updating"
    )


def _leaf_change(text: str, kind: str = "response-optional-property-removed") -> VendorChange:
    return VendorChange(
        vendor_id="stripe", from_version="v2320", to_version="v2330",
        kind=kind, operation_id="PostCharges", path_ptr="/v1/charges",
        severity="breaking", source="oasdiff", raw={"text": text},
    )


def test_a_bare_field_name_is_returned_unchanged():
    assert changed_field(_leaf_change("removed the optional property `source`")) == "source"


def test_a_nested_property_path_resolves_to_its_leaf():
    change = _leaf_change(
        "removed the optional property "
        "`error/payment_method/card/generated_from/setup_attempt/payment_method_details`"
    )
    assert changed_field(change) == "payment_method_details"


def test_schema_composition_segments_are_not_mistaken_for_fields():
    change = _leaf_change(
        "removed the optional property "
        "`error/payment_method/card/generated_from/"
        "anyOf[subschema #1: payment_method_card_generated_card]/setup_attempt`"
    )
    assert changed_field(change) == "setup_attempt"


def test_a_path_whose_leaf_is_a_composition_segment_falls_back_to_the_last_real_name():
    change = _leaf_change(
        "removed the optional property `error/payment_method/anyOf[subschema #2: Foo]`"
    )
    assert changed_field(change) == "payment_method"


def test_a_token_with_no_resolvable_field_returns_none():
    assert changed_field(_leaf_change("removed the optional property `anyOf[subschema #1: Foo]`")) is None


def test_the_oneof_and_allof_siblings_are_skipped_like_anyof():
    """The reduction skips every composition oasdiff interposes, not just `anyOf`.

    `anyOf` is the one the Stripe corpus exercises, so a blacklist that enumerated only it
    would look correct against every fixture here while dropping `oneOf`/`allOf` paths on
    the first spec that composes with them.
    """
    for keyword in ("oneOf", "allOf"):
        change = _leaf_change(
            f"removed the optional property `error/payment_method/{keyword}[subschema #2: Foo]`"
        )
        assert changed_field(change) == "payment_method"


def test_a_leaf_that_is_not_a_composition_segment_resolves_to_itself():
    """A leaf is skipped only for naming a schema, never for looking unusual.

    The indexer records the name a call site destructures, verbatim and quotes stripped, so
    `3d_secure` is exactly what a match needs. Resolving the path to `payment_method` instead
    answers with a field the vendor did not change, and the removal is filtered out of
    existence rather than surfaced. Returning nothing would at least leave the finding matched
    on its operation.
    """
    change = _leaf_change("removed the optional property `error/payment_method/3d_secure`")
    assert changed_field(change) == "3d_secure"


def test_a_segment_carrying_a_newline_is_not_returned_as_a_field_name():
    """No `response_fields_read` entry can carry a newline, so returning one filters silently.

    `_BACKTICKED`'s character class admits newlines, so a multi-line message reaches here even
    though no single-line oasdiff message does today. An end anchor of `$` accepts the segment
    and hands back the newline attached to it.
    """
    assert changed_field(_leaf_change("removed the optional property `status\n`")) is None


def test_a_newline_leaf_does_not_fall_back_to_its_parent():
    """Only a composition segment defers to the segment above it.

    Falling back for any other reason answers with the parent's name, which is a different
    field the vendor did not change -- the same wrong-answer failure as resolving `3d_secure`
    to `payment_method`.
    """
    assert changed_field(_leaf_change("removed the optional property `error/status\n`")) is None


def test_unparseable_breaking_output_raises_instead_of_propagating_a_decode_error(monkeypatch):
    """A truncated or malformed payload is a vendor-boundary failure, reported as one.

    `RuntimeError` is the failure this module documents and the only one its callers are
    written against; a `JSONDecodeError` escaping from here reaches a graph node that handles
    neither. It must still raise -- a differ that parsed nothing is not a vendor that changed
    nothing.
    """

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args, returncode=0, stdout='[{"id": "x"', stderr="")

    monkeypatch.setattr(oasdiff.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="breaking"):
        run_oasdiff_breaking(FIXTURES / "charges_base.json", FIXTURES / "charges_revision.json")


def test_unparseable_checks_output_raises_instead_of_propagating_a_decode_error(monkeypatch):
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="not json at all", stderr="")

    monkeypatch.setattr(oasdiff.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="checks"):
        run_oasdiff_checks()
