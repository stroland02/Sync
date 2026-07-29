"""Labelled pairs by synthetic mutation, and the properties that make them a benchmark.

`docs/superpowers/specs/2026-07-29-sync-ground-truth-quality.md` closed the mining question with
a No -- 117 commits read, none of the five plausible ones a migration, and a pinned cohort that
does not migrate at all -- and named this as the fallback the benchmark specification had
already reserved: synthetic mutation of real repositories, at the cost of realism.

What is asserted here is not that a mutation looks like a migration. It is the three properties
a label has to have to be worth scoring against:

- it names exactly the call sites the mutation broke, in both directions;
- the sites it does not name survive byte-identical, which is the only thing that makes
  precision measurable at all;
- it is derived from the edit rather than from Sync, so a binder cannot pass by agreeing with
  itself.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from sync.benchmark.mutate import (
    SUPPORTED_KINDS,
    UnsupportedChangeKind,
    depends_on_change,
    generate_pair,
)
from sync.core import CallSite, VendorChange
from sync.route.templates import omit_argument_at

FIXTURE = Path(__file__).parent / "fixtures" / "mutation"
MUTATE_SOURCE = Path(__file__).parents[1] / "src" / "sync" / "benchmark" / "mutate.py"


def _sources() -> dict[str, str]:
    """The fixture repository, read the way a generator would read a real checkout."""
    return {
        path.relative_to(FIXTURE).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(FIXTURE.rglob("*.ts"))
    }


def _site(sources: dict[str, str], site_id: str, path: str, symbol: str, occurrence: int,
          operation_id: str) -> CallSite:
    """A call site addressed the way the indexer addresses one: path, line, column.

    Positions are computed from the fixture rather than written down, so a fixture edit cannot
    leave a test asserting against a call that has moved two lines.
    """
    source = sources[path]
    offset = -1
    for _ in range(occurrence + 1):
        offset = source.index(symbol + "(", offset + 1)
    line = source.count("\n", 0, offset) + 1
    column = offset - (source.rfind("\n", 0, offset) + 1)
    return CallSite(
        id=site_id, repo_id="fixture", path=path, line=line, col=column, vendor_id="stripe",
        operation_id=operation_id, symbol=symbol, sdk_version="18.0.0", content_hash="h",
    )


def _change(kind: str, field: str = "receipt_email") -> VendorChange:
    return VendorChange(
        id="vc-1", vendor_id="stripe", from_version="2026-05-01", to_version="2026-11-01",
        kind=kind, operation_id="PostCharges", path_ptr="/v1/charges", severity="breaking",
        source="oasdiff",
        raw={"id": kind, "text": f"removed the request property `{field}` from POST /v1/charges"},
    )


def _all_sites(sources: dict[str, str]) -> list[CallSite]:
    """Four call sites: two on the changed operation, one on another, one unbound result.

    The mix is the fixture's whole purpose. A generated repository where every site is affected
    cannot measure precision, because the negative class it would need does not exist.
    """
    return [
        _site(sources, "cs-billing-1", "src/billing.ts", "stripe.charges.create", 0, "PostCharges"),
        _site(sources, "cs-billing-2", "src/billing.ts", "stripe.charges.create", 1, "PostCharges"),
        _site(sources, "cs-refund-1", "src/refunds.ts", "stripe.charges.retrieve", 0,
              "GetChargesCharge"),
        _site(sources, "cs-refund-2", "src/refunds.ts", "stripe.charges.create", 0, "PostCharges"),
    ]


def _labels(pair) -> dict[str, bool]:
    return {label.call_site_id: label.affected for label in pair.labels}


# --- the label names exactly what was broken --------------------------------------


@pytest.mark.parametrize("kind", sorted(SUPPORTED_KINDS))
def test_the_label_names_every_site_the_mutation_broke_and_no_other(kind):
    """Both directions, because either alone is satisfied by a label that names everything.

    Forward: every site the label calls affected carries the changed field in the mutated
    source. Backward: no site the label calls unaffected does. A label failing the second
    direction reads as a scorer's false positive when the fault was in the benchmark.
    """
    sources = _sources()
    sites = _all_sites(sources)
    change = _change(kind)

    pair = generate_pair(sources, change, sites, targets=["cs-billing-1"])

    affected = _labels(pair)
    assert affected["cs-billing-1"] is True
    assert depends_on_change(pair.sources, change, sites[0]) is True
    for site in sites[1:]:
        assert affected[site.id] is False
        assert depends_on_change(pair.sources, change, site) is False


@pytest.mark.parametrize("kind", sorted(SUPPORTED_KINDS))
def test_a_site_that_was_not_targeted_survives_byte_identical(kind):
    """What makes precision measurable. A generator that edited every call in the file would
    leave no site a binder could be wrong about, and a precision of 1.0 over a corpus with no
    negative class is not a measurement."""
    sources = _sources()
    sites = _all_sites(sources)

    pair = generate_pair(sources, _change(kind), sites, targets=["cs-billing-1"])

    assert pair.sources["src/refunds.ts"] == sources["src/refunds.ts"]
    assert pair.sources["src/billing.ts"] != sources["src/billing.ts"]
    # The second call in the edited file is untouched: only the targeted call's own text moved.
    assert "chargeSupplier" in pair.sources["src/billing.ts"]
    assert sources["src/billing.ts"].split("export async function chargeSupplier")[1] == \
        pair.sources["src/billing.ts"].split("export async function chargeSupplier")[1]


@pytest.mark.parametrize("kind", sorted(SUPPORTED_KINDS))
def test_both_classes_are_present_in_one_generated_pair(kind):
    """Precision needs sites Sync flagged that were not affected; recall needs sites that were
    affected and not flagged. A pair carrying one class measures one axis and misreports the
    other as perfect."""
    pair = generate_pair(_sources(), _change(kind), _all_sites(_sources()), targets=["cs-billing-1"])
    affected = set(_labels(pair).values())

    assert affected == {True, False}


@pytest.mark.parametrize("kind", sorted(SUPPORTED_KINDS))
def test_an_affected_label_carries_the_rung_the_evidence_lived_at(kind):
    """A miss has no finding, so the label is the only thing that can attribute it to a binder.
    A synthetic mutation writes the dependency into the source, so the evidence is static."""
    pair = generate_pair(_sources(), _change(kind), _all_sites(_sources()), targets=["cs-billing-1"])
    by_id = {label.call_site_id: label for label in pair.labels}

    assert by_id["cs-billing-1"].rung == "static"
    assert by_id["cs-billing-2"].rung == "unresolved"


# --- determinism ------------------------------------------------------------------


@pytest.mark.parametrize("kind", sorted(SUPPORTED_KINDS))
def test_the_same_input_yields_byte_identical_output(kind):
    """An unfrozen benchmark measures the benchmark. Two runs over one input have to agree
    byte for byte, or a score moves for a reason that is not the pipeline."""
    first = generate_pair(_sources(), _change(kind), _all_sites(_sources()), targets=["cs-billing-1"])
    second = generate_pair(_sources(), _change(kind), _all_sites(_sources()), targets=["cs-billing-1"])

    assert first.sources == second.sources
    assert first.model_dump_json() == second.model_dump_json()


# --- the label is not Sync's opinion of itself ------------------------------------


def test_the_generator_never_imports_the_binder():
    """The structural form of the non-circularity rule, asserted rather than promised.

    A label computed by asking Sync which sites are affected is a test Sync passes by
    definition -- precision and recall would both read 1.0 against any binder at all, including
    a broken one. The module may read source, and may not ask the thing being measured.
    """
    tree = ast.parse(MUTATE_SOURCE.read_text(encoding="utf-8"))
    imported = {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    } | {
        alias.name
        for node in ast.walk(tree) if isinstance(node, ast.Import)
        for alias in node.names
    }

    # `sync.benchmark.binding` is deliberately not on this list: it defines the label's shape
    # and computes nothing about which call sites a change affects. What must not be reachable
    # is the machinery that decides that -- the indexer, the detector, and the graph they read.
    forbidden = [name for name in imported
                 if name.startswith(("sync.index", "sync.detect", "sync.graph"))]
    assert forbidden == []


def test_the_module_says_how_the_label_is_derived_and_what_it_costs():
    """Two claims this repository requires in writing rather than in a report: where the label
    comes from, and the bias the approach carries. A benchmark whose bias is undocumented is
    worse than none."""
    docstring = ast.get_docstring(ast.parse(MUTATE_SOURCE.read_text(encoding="utf-8"))) or ""

    assert "realism" in docstring.lower()
    assert "binder" in docstring.lower()


# --- refusals ---------------------------------------------------------------------


def test_a_change_kind_the_generator_cannot_invert_is_refused_by_name():
    """Producing an unmutated tree instead would score as a perfect miss for every binder --
    recall zero against a repository nothing broke -- and the fault would look like the
    pipeline's."""
    with pytest.raises(UnsupportedChangeKind) as raised:
        generate_pair(_sources(), _change("request-property-added"), _all_sites(_sources()),
                      targets=["cs-billing-1"])

    assert "request-property-added" in str(raised.value)


def test_a_site_that_already_depends_on_the_changed_field_is_refused():
    """The label is exact only because the mutation is the sole source of the dependency. A
    call site already passing the field would be genuinely affected without having been broken
    here, so labelling it from the edit record would be wrong -- and silently."""
    sources = _sources()
    sources["src/billing.ts"] = sources["src/billing.ts"].replace(
        "{ amount, currency: 'usd' }", "{ amount, currency: 'usd', receipt_email: 'a@b.c' }"
    )
    sites = _all_sites(sources)

    with pytest.raises(ValueError, match="cs-billing-2"):
        generate_pair(sources, _change("request-property-removed"), sites, targets=["cs-billing-1"])


def test_a_target_the_mutation_cannot_reach_is_reported_rather_than_labelled_affected():
    """`fireAndForget` never binds the response, so a response-side mutation has nothing to
    read the removed field off. Labelling it affected anyway would manufacture a false negative
    for every binder; the honest answer is that this site was not broken, and to say which."""
    sources = _sources()
    sites = _all_sites(sources)

    pair = generate_pair(sources, _change("response-property-removed", field="status"), sites,
                         targets=["cs-refund-2"])

    assert "cs-refund-2" in pair.unreachable
    assert _labels(pair)["cs-refund-2"] is False
    assert pair.sources["src/refunds.ts"] == sources["src/refunds.ts"]


def test_a_target_naming_a_call_site_that_is_not_in_the_tree_is_refused():
    """A target the generator cannot find is a mistake in the caller's input, and producing a
    pair regardless would put a label on a site nothing mutated."""
    with pytest.raises(ValueError, match="cs-nowhere"):
        generate_pair(_sources(), _change("request-property-removed"), _all_sites(_sources()),
                      targets=["cs-nowhere"])


# --- the mutation is the inverse of the repair ------------------------------------


def test_a_request_mutation_is_undone_exactly_by_the_repair_primitive():
    """The strongest statement of "a mutation is the inverse of a real change kind": the tier-0
    repair for a removed request property, run over the mutated source, returns the original
    byte for byte. Two mechanisms that disagree would mean the benchmark scores repairs against
    a break they do not describe."""
    sources = _sources()
    sites = _all_sites(sources)
    change = _change("request-property-removed")

    pair = generate_pair(sources, change, sites, targets=["cs-billing-1"])
    target = sites[0]
    # `line - 1` is `omit_argument_at`'s contract, not a fudge: it counts lines from zero
    # while `CallSite.line` counts from one, and `sync.remediate.property_omit` converts at the
    # same boundary. Its neighbour `omit_property_at` takes the 1-based form, which is worth
    # knowing before reusing either.
    repaired = omit_argument_at(
        pair.sources["src/billing.ts"], "receipt_email", "typescript", target.line - 1, target.col
    )

    assert repaired == sources["src/billing.ts"]


def test_the_mutated_tree_is_still_the_repository_it_started_as():
    """Every file comes back, mutated or not, including the ones the generator never parses. A
    generator returning only what it edited hands the caller a tree that no longer builds."""
    sources = _sources()
    pair = generate_pair(sources, _change("request-property-removed"), _all_sites(sources),
                         targets=["cs-billing-1"])

    assert set(pair.sources) == set(sources)
    assert json.loads((FIXTURE / "package.json").read_text(encoding="utf-8"))["name"]
