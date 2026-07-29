"""Scoring a generated pair with the pipeline that ships, and what the number means.

`2026-07-27-sync-benchmark-gates.md` calls binding precision and recall the two axes that
matter most, and neither has ever been computed: first no labelled reference existed, then
`2026-07-29-sync-ground-truth-quality.md` returned No on mining one, and since the labelled-pair
generator landed the only thing missing was something joining it to `compute_binding_accuracy`.

What these tests assert is not that the binder is good. It is that the number means what it
says:

- both ends of the range are reachable, so a scorer that always answers the same shape fails one
  of them;
- a false positive moves precision and leaves recall alone, and a miss does the opposite --
  `binding.py` warns these can be silently swapped, so they are asserted apart;
- the labels reach the scorer as the generator produced them, by identity, so no derivation can
  have consulted the binder in between;
- the corpus carries both classes, because a reference where every site is affected reports 1.0
  precision for want of anything to be wrong about.

Every finding scored here comes out of `TypeScriptAdapter` and `VendorChangeDetector`, the
indexer and detector `cli.py` runs. Nothing constructs an `EmittedFinding`; a score over
hand-built findings measures the test.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from sync.benchmark.binding import BindingLabel
from sync.benchmark.mutate import UnsupportedChangeKind, generate_pair
from sync.benchmark.score import (
    SYNTHETIC_REFERENCE,
    DisplacedLabel,
    index_sources,
    score_change,
    score_pair,
)
from sync.core import OperationRef, RepoRef, VendorChange
from sync.graph.store import GraphStore
from sync.index.typescript import TypeScriptAdapter

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")

FIXTURE = Path(__file__).parent / "fixtures" / "mutation"

_OPERATIONS = {
    "stripe.charges.create": ("PostCharges", "post", "/v1/charges"),
    "stripe.charges.retrieve": ("GetChargesCharge", "get", "/v1/charges/{charge}"),
}


class SymbolMap:
    """The vendor half of indexing, which in production is Stripe's own specification.

    Stubbed because a symbol map is data: `StripeAdapter` builds this same mapping out of a
    spec file, and pinning two entries here is the fixture equivalent of pinning a spec. The
    indexer that reads it and the detector that consumes its output are the real ones.
    """

    vendor_id = "stripe"
    sdk_bindings = {"typescript": {"package": "stripe"}}

    def fetch_changes(self, from_version: str, to_version: str):
        return []

    def operation_for_symbol(self, symbol: str, language: str = "typescript"):
        entry = _OPERATIONS.get(symbol)
        if entry is None:
            return None
        return OperationRef(operation_id=entry[0], http_method=entry[1], path=entry[2])


PACKAGE_JSON = '{"name": "scored", "private": true, "dependencies": {"stripe": "^18.0.0"}}\n'

# Two calls on the changed operation and one on another. The third is what makes precision
# measurable at all: a corpus with no unaffected call site has no negative class, and reports
# 1.0 because nothing could have been wrong rather than because nothing was.
PLAIN = """import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);

export async function chargeCustomer(amount: number) {
  const charge = await stripe.charges.create({ amount, currency: 'eur' });
  return charge.id;
}

export async function chargeSupplier(amount: number) {
  const payment = await stripe.charges.create({ amount, currency: 'usd' });
  return payment.id;
}

export async function lookUpCharge(id: string) {
  const found = await stripe.charges.retrieve(id);
  return found.amount;
}
"""

# Two calls on the changed operation sharing one line. A response guard appended to the first
# statement moves no line and still shifts the second call's column, which is the displacement
# that remains once the guard stops occupying lines of its own.
SAME_LINE = """import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);

export async function chargeBoth(amount: number) {
  const charge = await stripe.charges.create({ amount, currency: 'eur' }); const payment = await stripe.charges.create({ amount, currency: 'usd' });
  return [charge.id, payment.id];
}
"""

# The same repository where both calls on the changed operation pass `metadata`. Against a
# change nested under `metadata`, the detector matches on the outer segment and says so -- an
# operation-match-only finding. It is how a false positive arises without anything being
# stubbed: the site carries the outer segment and not the changed field.
BOTH_CARRY_OUTER = PLAIN.replace(
    "{ amount, currency: 'eur' }", "{ amount, currency: 'eur', metadata: { note: 'a' } }"
).replace(
    "{ amount, currency: 'usd' }", "{ amount, currency: 'usd', metadata: { note: 'b' } }"
)

# Only the first carries it, so a change nested under `metadata` is found at one target and
# missed at the other -- one true positive and one false negative, with no false positive.
ONE_CARRIES_OUTER = PLAIN.replace(
    "{ amount, currency: 'eur' }", "{ amount, currency: 'eur', metadata: { note: 'a' } }"
)


def _sources(billing: str) -> dict[str, str]:
    """A whole checkout, not only the edited file. `MutationPair.sources` promises the same
    thing, and the indexer needs `package.json` to recognise the vendor at all."""
    return {"package.json": PACKAGE_JSON, "src/billing.ts": billing}


def _fixture_sources() -> dict[str, str]:
    return {
        path.relative_to(FIXTURE).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(FIXTURE.rglob("*"))
        if path.is_file()
    }


def _change(text: str, kind: str = "request-property-removed") -> VendorChange:
    """A vendor change whose property path is whatever `text` backticks.

    `changed_path` reads that token and splits it on `/`, so `metadata/receipt_email` is a
    nested change and `receipt_email` is a flat one, while `changed_field` -- what the mutation
    writes -- is the last segment either way. That is the difference between a break the
    detector's path rule reaches and one it does not, and it is the vendor's difference rather
    than one invented here.
    """
    return VendorChange(
        vendor_id="stripe", from_version="2026-05-01", to_version="2026-11-01", kind=kind,
        operation_id="PostCharges", path_ptr="/v1/charges", severity="breaking", source="oasdiff",
        raw={"id": kind, "text": f"removed the request property `{text}` from POST /v1/charges"},
    )


@pytest.fixture()
def store() -> GraphStore:
    s = GraphStore(DSN)
    s.apply_schema()
    s.truncate_all()
    return s


@pytest.fixture()
def adapter() -> TypeScriptAdapter:
    return TypeScriptAdapter(vendor_adapter=SymbolMap())


def _repo(tmp_path: Path, name: str = "tree") -> RepoRef:
    return RepoRef(
        repo_id="scored", url="https://example.invalid/scored",
        local_path=str(tmp_path / name), head_sha="0" * 40,
    )


def _prepared(sources, change, store, adapter, repo):
    """Everything a caller does before scoring: index the tree, learn the ids, id the change.

    The labels address a call site and a vendor change by the ids the store assigns, so both
    have to exist before `generate_pair` runs. Returns the indexed sites in file order.
    """
    sites = index_sources(sources, store, repo, adapter)
    change.id = store.upsert_vendor_change(change)
    return sites


def _create_sites(sites):
    return [site for site in sites if site.operation_id == "PostCharges"]


# --- both ends of the range are reachable -------------------------------------------


def test_a_binder_that_finds_every_break_scores_one_on_both_axes(store, adapter, tmp_path):
    """The upper end. A flat change, mutated into one call site, found by the detector's own
    field match -- and no finding anywhere else, because nothing else carries the field."""
    repo = _repo(tmp_path)
    change = _change("receipt_email")
    sources = _sources(PLAIN)
    sites = _prepared(sources, change, store, adapter, repo)
    target = _create_sites(sites)[0]

    scored = score_change(sources, change, sites, [target.id], store, _repo(tmp_path, "m"), adapter)

    assert scored.accuracy.precision.value == 1.0
    assert scored.accuracy.recall.value == 1.0


def test_a_binder_that_finds_nothing_scores_zero_recall_and_null_precision(
    store, adapter, tmp_path
):
    """The lower end, and the distinction `Axis` exists for. Precision over no findings is not
    zero -- nothing was judged -- while recall over a break nobody found is a real 0.0.

    The change is nested under a segment no call site passes, which is the failure
    `vendor_change.py` documents at length: the shallowest breaking record in Stripe's own
    v2320 window is three segments deep and no static indexer reaches that far.
    """
    repo = _repo(tmp_path)
    change = _change("metadata/receipt_email")
    sources = _sources(PLAIN)
    sites = _prepared(sources, change, store, adapter, repo)
    target = _create_sites(sites)[0]

    scored = score_change(sources, change, sites, [target.id], store, _repo(tmp_path, "m"), adapter)

    assert scored.accuracy.recall.value == 0.0
    assert scored.accuracy.recall.n == 1
    assert scored.accuracy.precision.value is None
    assert scored.accuracy.precision.n == 0


# --- the two arithmetics, apart ------------------------------------------------------


def test_a_false_positive_lowers_precision_and_leaves_recall_alone(store, adapter, tmp_path):
    """One finding on the site the mutation broke, one on a site it did not.

    Both calls pass `metadata`, so both match a change nested under it; only one of them was
    mutated. Precision has to fall to one half and recall has to stay at 1.0, because the break
    that existed was reached.
    """
    repo = _repo(tmp_path)
    change = _change("metadata/receipt_email")
    sources = _sources(BOTH_CARRY_OUTER)
    sites = _prepared(sources, change, store, adapter, repo)
    target = _create_sites(sites)[0]

    scored = score_change(sources, change, sites, [target.id], store, _repo(tmp_path, "m"), adapter)

    assert scored.accuracy.precision.value == 0.5
    assert scored.accuracy.recall.value == 1.0


def test_a_miss_lowers_recall_and_leaves_precision_alone(store, adapter, tmp_path):
    """Two breaks, one reached. The site that carries `metadata` matches the nested change and
    the one that does not is invisible to it, so recall falls to one half while every finding
    emitted was genuine and precision stays at 1.0."""
    repo = _repo(tmp_path)
    change = _change("metadata/receipt_email")
    sources = _sources(ONE_CARRIES_OUTER)
    sites = _prepared(sources, change, store, adapter, repo)
    targets = [site.id for site in _create_sites(sites)]

    scored = score_change(sources, change, sites, targets, store, _repo(tmp_path, "m"), adapter)

    assert scored.accuracy.recall.value == 0.5
    assert scored.accuracy.precision.value == 1.0


# --- the label never consults the binder ---------------------------------------------


def test_the_labels_reach_the_scorer_exactly_as_the_generator_produced_them(
    store, adapter, tmp_path, monkeypatch
):
    """Identity, not equality. Equal labels could have been rebuilt from anything, including
    from what the binder found; the same list object cannot have been.

    This is the property the whole two-task split exists to protect. A label derived by asking
    Sync which call sites a change affects scores the binder against its own opinion, and
    reports 1.0 on both axes for any binder whatsoever.
    """
    import sync.benchmark.score as score_module

    seen: dict[str, object] = {}
    real = score_module.compute_binding_accuracy

    def capturing(findings, labels):
        seen["labels"] = labels
        seen["findings"] = findings
        return real(findings, labels)

    monkeypatch.setattr(score_module, "compute_binding_accuracy", capturing)

    repo = _repo(tmp_path)
    change = _change("receipt_email")
    sources = _sources(PLAIN)
    sites = _prepared(sources, change, store, adapter, repo)
    pair = generate_pair(sources, change, sites, [_create_sites(sites)[0].id])

    score_pair(pair, change, store, _repo(tmp_path, "m"), adapter)

    assert seen["labels"] is pair.labels
    assert all(isinstance(label, BindingLabel) for label in seen["labels"])


def test_the_scorer_builds_no_findings_of_its_own(store, adapter, tmp_path, monkeypatch):
    """Every scored finding came out of the detector, so silencing the detector empties the
    input. A scorer that synthesised even one would keep answering."""
    import sync.benchmark.score as score_module

    captured: dict[str, object] = {}
    real = score_module.compute_binding_accuracy

    def capturing(findings, labels):
        captured["findings"] = list(findings)
        return real(findings, labels)

    monkeypatch.setattr(score_module, "compute_binding_accuracy", capturing)
    monkeypatch.setattr(score_module.VendorChangeDetector, "scan", lambda self: [])

    repo = _repo(tmp_path)
    change = _change("receipt_email")
    sources = _sources(PLAIN)
    sites = _prepared(sources, change, store, adapter, repo)

    score_change(sources, change, sites, [_create_sites(sites)[0].id], store,
                 _repo(tmp_path, "m"), adapter)

    assert captured["findings"] == []


# --- the corpus and the exclusions ---------------------------------------------------


def test_the_scored_corpus_carries_both_classes(store, adapter, tmp_path):
    """Without an unaffected call site there is no negative class and precision is not a
    measurement. The count is reported rather than assumed, so a corpus that lost its negatives
    says so instead of scoring 1.0 for want of anything to be wrong about."""
    repo = _repo(tmp_path)
    change = _change("receipt_email")
    sources = _sources(PLAIN)
    sites = _prepared(sources, change, store, adapter, repo)

    scored = score_change(sources, change, sites, [_create_sites(sites)[0].id], store,
                          _repo(tmp_path, "m"), adapter)

    assert scored.affected_sites == 1
    assert scored.unaffected_sites == 2


def test_the_result_carries_its_sample_sizes_and_its_exclusions(store, adapter, tmp_path):
    """A precision with no denominator and no exclusion count is the number the benchmark
    specification spends a section warning about."""
    repo = _repo(tmp_path)
    change = _change("receipt_email")
    sources = _sources(PLAIN)
    sites = _prepared(sources, change, store, adapter, repo)

    scored = score_change(sources, change, sites, [_create_sites(sites)[0].id], store,
                          _repo(tmp_path, "m"), adapter)

    assert scored.accuracy.precision.n == 1
    assert scored.accuracy.recall.n == 1
    assert scored.accuracy.unlabelled_findings == 0
    assert len(scored.findings) == 1
    assert scored.unreachable_targets == ()
    assert set(scored.accuracy.precision_by_rung) == {"static"}
    assert set(scored.accuracy.recall_by_rung) == {"static"}


def test_a_target_the_mutation_could_not_reach_is_carried_into_the_result(
    store, adapter, tmp_path
):
    """`generate_pair` labels an unreachable target unaffected, which is honest and invisible.
    Carrying the name through is what stops a corpus quietly shrinking its own positive class.
    """
    repo = _repo(tmp_path)
    # Response-side: the third call binds no result, so a guard has nothing to read off.
    change = _change("receipt_email", kind="response-property-removed")
    sources = _sources(PLAIN + "\nexport async function fireAndForget(amount: number) {\n"
                               "  await stripe.charges.create({ amount, currency: 'gbp' });\n}\n")
    sites = _prepared(sources, change, store, adapter, repo)
    unbound = [site for site in _create_sites(sites) if site.line > 15]

    scored = score_change(sources, change, sites, [unbound[0].id], store,
                          _repo(tmp_path, "m"), adapter)

    assert scored.unreachable_targets == (unbound[0].id,)
    assert scored.affected_sites == 0


# --- refusals ------------------------------------------------------------------------


def test_a_change_kind_the_generator_cannot_invert_is_refused_by_name(store, adapter, tmp_path):
    """Refused rather than scored. An unmutated tree labels every site unaffected and produces
    no findings, which reads as a perfect run rather than as a generator that declined."""
    repo = _repo(tmp_path)
    change = _change("receipt_email", kind="response-property-enum-value-added")
    sources = _sources(PLAIN)
    sites = index_sources(sources, store, repo, adapter)

    with pytest.raises(UnsupportedChangeKind, match="response-property-enum-value-added"):
        score_change(sources, change, sites, [_create_sites(sites)[0].id], store,
                     _repo(tmp_path, "m"), adapter)


def test_a_label_the_mutation_displaced_is_refused_rather_than_scored_as_a_miss(
    store, adapter, tmp_path
):
    """The one place the generator and the graph disagree, found by joining them.

    `upsert_call_site` puts `line` and `col` in a call site's identity, so a call the mutation
    moves becomes a new row: its label addresses one that no longer exists, and the score would
    read as a miss beside an unlabelled finding with nothing saying the two were the same call.
    Refused, naming the ids.

    Displacement used to arrive by the line, because the response guard occupied three of them,
    and that is what refused two of the twelve frozen-corpus specifications outright. The guard
    is now appended to the statement it follows and moves no line -- so this asserts the refusal
    against what remains, which is the column. Two calls sharing a line still shift the second
    when the first is mutated, and the refusal has to survive its common case disappearing or it
    is no longer being tested at all.
    """
    repo = _repo(tmp_path)
    change = _change("receipt_email", kind="response-property-removed")
    sources = _sources(SAME_LINE)
    sites = _prepared(sources, change, store, adapter, repo)
    first = _create_sites(sites)[0]

    with pytest.raises(DisplacedLabel, match="shift"):
        score_change(sources, change, sites, [first.id], store, _repo(tmp_path, "m"), adapter)


def test_a_change_whose_id_is_not_the_stores_is_refused(store, adapter, tmp_path):
    """The labels address the change by id. A caller who never upserted it produces labels
    keyed on the empty string while every finding carries the real one, so nothing matches:
    precision null, recall zero, and a binder that looks broken because the harness was.
    """
    repo = _repo(tmp_path)
    change = _change("receipt_email")
    sites = index_sources(_sources(PLAIN), store, repo, adapter)
    pair = generate_pair(_sources(PLAIN), change, sites, [_create_sites(sites)[0].id])

    with pytest.raises(ValueError, match="id"):
        score_pair(pair, change, store, _repo(tmp_path, "m"), adapter)


# --- what the number is allowed to claim ---------------------------------------------


def test_the_result_states_that_its_reference_is_synthetic(store, adapter, tmp_path):
    """A benchmark whose bias is undocumented is worse than none, and this is the repository's
    own standard applied to its own first score. The caveat travels with the number rather than
    living in a specification the reader of the number never opens."""
    repo = _repo(tmp_path)
    change = _change("receipt_email")
    sources = _sources(PLAIN)
    sites = _prepared(sources, change, store, adapter, repo)

    scored = score_change(sources, change, sites, [_create_sites(sites)[0].id], store,
                          _repo(tmp_path, "m"), adapter)

    assert scored.reference == SYNTHETIC_REFERENCE
    assert "synthetic" in SYNTHETIC_REFERENCE
    assert "mechanical" in SYNTHETIC_REFERENCE


def test_the_first_score_over_the_committed_fixture_is_measured(store, adapter, tmp_path):
    """The number this task exists to produce, over the repository the generator's own tests
    mutate. Asserted as measured rather than as a value: a threshold is exactly what tier C
    forbids, and pinning the figure here would turn the first score into a gate by accident.
    """
    repo = _repo(tmp_path)
    change = _change("receipt_email")
    sources = _fixture_sources()
    sites = _prepared(sources, change, store, adapter, repo)
    target = [site for site in sites if site.path == "src/billing.ts"][0]

    scored = score_change(sources, change, sites, [target.id], store, _repo(tmp_path, "m"), adapter)

    assert scored.accuracy.precision.n > 0
    assert scored.accuracy.recall.n > 0
    assert scored.affected_sites and scored.unaffected_sites


# --- and what the page is allowed to claim -------------------------------------------


def test_the_report_refuses_a_binding_score_with_no_reference_described():
    """The repository's own standard, enforced where it can be rather than remembered.

    A precision rendered with nothing saying what produced the labels claims to describe the
    binder when it partly describes the corpus. The refusal is the point: a note somebody has to
    remember is not a control.
    """
    from sync.benchmark.report import render_report

    label = BindingLabel(call_site_id="cs-1", vendor_change_id="vc-1", affected=True)

    with pytest.raises(ValueError, match="reference"):
        render_report([], findings=[], labels=[label])


def test_the_report_prints_what_the_synthetic_reference_biases(store, adapter, tmp_path):
    """The caveat travels to the page, in the words the scorer produced, under the numbers it
    qualifies. Asserted on the rendered text rather than on the argument, because the argument
    being carried and the argument being printed are different failures."""
    from sync.benchmark.report import render_report

    repo = _repo(tmp_path)
    change = _change("receipt_email")
    sources = _sources(PLAIN)
    sites = _prepared(sources, change, store, adapter, repo)
    scored = score_change(sources, change, sites, [_create_sites(sites)[0].id], store,
                          _repo(tmp_path, "m"), adapter)

    page = render_report([], findings=[], labels=[], reference=scored.reference)

    assert "synthetic" in page
    assert "mechanical and local" in page
    assert "cost of\nrealism" in page or "realism" in page


def test_a_report_with_no_labels_still_renders_without_a_reference():
    """Unmeasured is the normal answer and must not need a caveat. A guard that fired on the
    empty case would make the report unrenderable until the day it has a score."""
    from sync.benchmark.report import render_report

    page = render_report([])

    assert "binding precision" in page
    assert "About the binding reference" not in page


def test_a_measured_score_reaches_the_page_with_its_caveat(store, adapter, tmp_path):
    """The whole point of carrying findings and labels on the result: a score that can be read
    and not reported is a score whose bias never travels. Both halves are asserted on one page,
    because the number appearing without the caveat is the failure being prevented."""
    from sync.benchmark.report import render_report

    repo = _repo(tmp_path)
    change = _change("receipt_email")
    sources = _sources(PLAIN)
    sites = _prepared(sources, change, store, adapter, repo)
    scored = score_change(sources, change, sites, [_create_sites(sites)[0].id], store,
                          _repo(tmp_path, "m"), adapter)

    page = render_report(
        [], findings=scored.findings, labels=scored.labels, reference=scored.reference
    )

    assert "binding precision                    1.000   n=1" in page
    assert "binding recall                       1.000   n=1" in page
    assert "About the binding reference" in page
    assert "Binding precision by rung" in page
    assert "  static" in page


def test_a_call_site_from_another_tree_cannot_leak_into_the_score(store, adapter, tmp_path):
    """The graph is truncated before the mutated tree is indexed, because the detector reads
    every call site the store holds and not only the ones this pair labelled.

    A row left from another repository carries the changed field, so it produces a finding that
    no label covers -- excluded and counted, which is correct handling of a sample that should
    never have been in the input. `cli.py` truncates for the same reason.
    """
    from sync.core import CallSite

    repo = _repo(tmp_path)
    change = _change("receipt_email")
    sources = _sources(PLAIN)
    sites = _prepared(sources, change, store, adapter, repo)

    # After the original tree is indexed, so what this exercises is the truncate `score_pair`
    # does and not the one `index_sources` did.
    store.upsert_call_site(CallSite(
        repo_id="somebody-else", path="src/other.ts", line=1, col=0, vendor_id="stripe",
        operation_id="PostCharges", symbol="stripe.charges.create",
        args_keys=["receipt_email"], sdk_version="18.0.0", content_hash="h",
    ))

    scored = score_change(sources, change, sites, [_create_sites(sites)[0].id], store,
                          _repo(tmp_path, "m"), adapter)

    assert scored.accuracy.unlabelled_findings == 0
    assert len(scored.findings) == 1


def test_a_label_the_mutated_tree_does_not_carry_is_refused(store, adapter, tmp_path):
    """The generator's own second opinion, read back before anything is scored.

    `generate_pair` labels from the edits it made and `depends_on_change` reads the same fact
    out of the source it produced, so a disagreement is a generator or indexer bug. Unchecked it
    reads as a miss: recall falls and the binder is blamed for a call site nobody broke. The
    tree here is the unmutated one under a mutated tree's labels, which is that disagreement in
    its simplest form.
    """
    from sync.benchmark.mutate import MutationPair
    from sync.benchmark.score import UnbrokenLabel

    repo = _repo(tmp_path)
    change = _change("receipt_email")
    sources = _sources(PLAIN)
    sites = _prepared(sources, change, store, adapter, repo)
    pair = generate_pair(sources, change, sites, [_create_sites(sites)[0].id])
    unedited = MutationPair(sources=sources, labels=pair.labels, unreachable=pair.unreachable)

    with pytest.raises(UnbrokenLabel, match="does not"):
        score_pair(unedited, change, store, _repo(tmp_path, "m"), adapter)
