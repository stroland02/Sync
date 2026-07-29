"""A generated pair, run through the pipeline that ships, and scored against its own label.

`mutate.py` produces a broken repository and the ground truth for it; `binding.py` turns
findings and labels into precision and recall. Both landed with nothing joining them, and
deliberately so -- a generator and a scorer built together would be one artifact agreeing with
itself. This is the join, and it is what makes binding precision and recall computable for the
first time on this project.

Where the label comes from, and why it cannot have asked the binder
-------------------------------------------------------------------
It comes from the edit. `generate_pair` writes the removed dependency into the call sites it was
told to break, and records exactly those as affected; every other site in the tree is a
negative. That derivation is a record of what the generator did, not a computation over the
result, and `mutate.py` imports nothing from `sync.index`, `sync.detect` or `sync.graph` -- a
test in `test_mutation_pairs.py` asserts that on the module's import closure rather than
trusting the sentence.

This module does not touch that. It forwards `pair.labels` to `compute_binding_accuracy`
unchanged and by identity; it constructs no `BindingLabel` and reads no field of one except to
count the classes and to check that the mutated index can still address them. A label derived
here from what the detector emitted would score the binder against its own opinion: both axes
would read 1.0 against any binder whatsoever, including a broken one, and the number would move
only when two components disagreed about something neither was right about.

The findings are the pipeline's, not this module's
--------------------------------------------------
`TypeScriptAdapter.index` and `VendorChangeDetector.scan` are what `cli.py` runs. Nothing here
constructs an `EmittedFinding` from anything but a `Finding` the detector emitted, because a
score over hand-built findings measures the harness.

Two pieces of production indexing are deliberately absent. `cli.py` also collects model-id
string literals, and its detector suite also runs the deprecation detectors; both join on
`CallSite.args_keys` literals rather than on `operation_id`, and a pair from `generate_pair`
carries no deprecation signal for them to fire on. Including them would add unlabelled findings
and no information.

Every binding here is `static`
------------------------------
The call sites come from reading source and nothing correlates telemetry against them, so
`static` is the only rung a finding in this harness can honestly carry. `resolved` and
`observed` are not absent because they scored badly; they are absent because this path does not
produce them, and an empty key in the split means exactly that.

What the number is not allowed to claim
---------------------------------------
`SYNTHETIC_REFERENCE` travels with every result and `report.py` refuses to render a binding
score without one. The reference is synthetic by choice rather than by oversight -- mining real
migrations was measured and rejected -- and the cost of that choice is realism, which has to
survive into the reporting or the number overstates itself.

One bias belongs here rather than in a specification, because it was found by building this and
is a property of the join rather than of either half: **precision over these pairs has almost no
way to fail.** `generate_pair` refuses a tree where an untargeted call site already carries the
changed dependency, and carrying it is the only thing the detector's field match fires on. So a
false positive requires a *partial* path match -- a site passing an outer segment of a nested
change -- and against a flat change it cannot arise at all. A precision of 1.0 over a flat pair
is close to a property of the corpus, and reading it as a property of the binder is the mistake
this paragraph exists to prevent.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from pydantic import BaseModel

from sync.benchmark.binding import (
    BindingAccuracy,
    BindingLabel,
    EmittedFinding,
    compute_binding_accuracy,
)
from sync.benchmark.mutate import MutationPair, depends_on_change, generate_pair
from sync.core import BindingRung, CallSite, RepoRef, VendorChange
from sync.detect.vendor_change import VendorChangeDetector
from sync.graph.store import GraphStore

# The rung a statically indexed call site's finding carries; see the module docstring.
INDEXED_RUNG: BindingRung = "static"

SYNTHETIC_REFERENCE = """\
The reference is synthetic. A vendor change was applied mechanically by `sync.benchmark.mutate`
to a real repository written against the old contract, and the label is the record of those
edits. Mining real migrations was measured and rejected -- 2026-07-29-sync-ground-truth-quality
read 117 candidate commits, found 58% carried a coding-agent trailer, and found none of the five
plausible ones to be a migration -- and this is the fallback that verdict named, at the cost of
realism.

What it biases, all of it towards the binder:
  - The break is mechanical and local: one property in one argument object, or one guard reading
    one response field. A real break lands in code that has drifted around the call for years,
    which is where a static reading is weakest.
  - The distribution is whatever this generator implements, in the proportions the caller asked
    for, and not the shape of any vendor's release history.
  - Precision has almost no way to fail. The generator refuses a tree where an untargeted call
    site already carries the changed dependency, and that is the only thing the detector's field
    match fires on, so a false positive needs a partial path match and cannot arise at all from
    a flat change.

A binder that scores well here has been shown to handle the mechanical case, and nothing more."""


class DisplacedLabel(ValueError):
    """A labelled call site the mutated index no longer holds.

    `upsert_call_site` puts `line` and `col` in a call site's identity, and says so: a site that
    merely shifts down the file becomes a new row rather than an update. A response-side mutation
    inserts lines, so every call below it in that file is a different id afterwards -- its label
    addresses a row that no longer exists, and the score would read as a miss beside an
    unlabelled finding with nothing saying the two were the same call.

    Raised rather than scored, because both halves of that are wrong and neither is visible in
    the number that comes out.
    """


class UnbrokenLabel(ValueError):
    """A label says a call site is affected and the mutated tree does not carry the dependency.

    `generate_pair` labels from the edits it made; `depends_on_change` reads the same fact back
    out of the source it produced. The two are independent derivations of one thing, so a
    disagreement is a bug in the generator or in the positions the index recorded -- never a
    result worth scoring. Unchecked it reads as a miss: recall falls, the binder is blamed, and
    the call site it was blamed for was never broken.

    This is not the binder being consulted. `depends_on_change` answers about one named call site
    against one field in one tree; it cannot say which call sites an operation change affects,
    which is the question the binder exists to answer and the one a label must never be derived
    from.
    """


class ScoredPair(BaseModel):
    """One pair's score, with everything needed to read it.

    The accuracy carries its own sample sizes, rung splits and unlabelled count. What is added
    here is the shape of the corpus behind them -- how many call sites were in each class, and
    which targets the mutation could not reach -- because a precision measured over a reference
    with no negatives is 1.0 for a reason that has nothing to do with the binder.
    """

    accuracy: BindingAccuracy
    reference: str
    # What the two axes were computed from, kept so the result can be rendered. `render_report`
    # takes findings and labels rather than an accuracy -- the same "rows, not a store" rule
    # `axes.py` follows -- so a result that carried only the arithmetic could be read and not
    # reported, and the caveat that has to travel with the number travels with this.
    findings: list[EmittedFinding]
    labels: list[BindingLabel]
    affected_sites: int
    unaffected_sites: int
    unreachable_targets: tuple[str, ...]


def materialise(sources: Mapping[str, str], root: Path) -> None:
    """Write a checkout to disk. The mapping is the whole tree, which is what
    `MutationPair.sources` promises: the indexer reads `package.json` to recognise the vendor at
    all, so a caller handed only the edited files indexes nothing."""
    for relative, text in sources.items():
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding="utf-8")


def index_sources(
    sources: Mapping[str, str], store: GraphStore, repo: RepoRef, adapter
) -> list[CallSite]:
    """Index a tree into `store` and return its call sites carrying the ids the store assigned.

    Truncates first. The detector reads every call site the graph holds, so a row left over from
    another tree is a call site nobody labelled -- it emits findings that land in the unlabelled
    bucket and quietly widens the exclusion count. `cli.py` truncates for the same reason.

    `repo.repo_id` is part of a call site's identity and `repo.local_path` is not, so the mutated
    tree may be written anywhere as long as it keeps the repository id the original was indexed
    under. A mismatch shows up as every label displaced rather than as a wrong score.
    """
    store.truncate_all()
    root = Path(repo.local_path)
    materialise(sources, root)

    sites = []
    for site in adapter.index(repo):
        site.id = store.upsert_call_site(site)
        sites.append(site)
    return sites


def score_pair(
    pair: MutationPair, change: VendorChange, store: GraphStore, repo: RepoRef, adapter
) -> ScoredPair:
    """Run the pipeline over the mutated tree and score what it emitted against the pair's label.

    `change` must already carry the id the store assigns it, because the labels address it by
    that id. A caller who skipped that produces labels keyed on the empty string against findings
    keyed on the real one: nothing matches, precision is null, recall is zero, and the binder
    looks broken because the harness was.
    """
    store.truncate_all()
    stored_id = store.upsert_vendor_change(change)
    if stored_id != change.id:
        raise ValueError(
            f"the pair's labels address this change by the id {change.id!r}, which is not the id "
            f"this store derives for it ({stored_id!r}); upsert the change before `generate_pair` "
            f"runs, or the labels address a change no finding carries"
        )

    root = Path(repo.local_path)
    materialise(pair.sources, root)
    indexed = {}
    for site in adapter.index(repo):
        indexed[store.upsert_call_site(site)] = site

    displaced = sorted({label.call_site_id for label in pair.labels} - set(indexed))
    if displaced:
        raise DisplacedLabel(
            f"{len(displaced)} labelled call site(s) are absent from the mutated index "
            f"({', '.join(displaced)}); a mutation that inserts lines shifts the calls below it "
            f"and `upsert_call_site` keys identity on position, so the label addresses a row the "
            f"mutated tree no longer has"
        )

    unbroken = sorted(
        label.call_site_id for label in pair.labels
        if label.affected and not depends_on_change(pair.sources, change, indexed[label.call_site_id])
    )
    if unbroken:
        raise UnbrokenLabel(
            f"{len(unbroken)} call site(s) are labelled affected and the mutated tree does not "
            f"carry the change at them ({', '.join(unbroken)}); the label and the source disagree, "
            f"and scoring it would charge the binder for a break that is not there"
        )

    findings = VendorChangeDetector(store, change.vendor_id).scan()
    emitted = [
        EmittedFinding(
            call_site_id=finding.call_site_id,
            vendor_change_id=finding.vendor_change_id or "",
            binding_rung=INDEXED_RUNG,
        )
        for finding in findings
    ]

    accuracy = compute_binding_accuracy(emitted, pair.labels)
    affected = sum(1 for label in pair.labels if label.affected)
    return ScoredPair(
        accuracy=accuracy,
        reference=SYNTHETIC_REFERENCE,
        findings=emitted,
        labels=list(pair.labels),
        affected_sites=affected,
        unaffected_sites=len(pair.labels) - affected,
        unreachable_targets=pair.unreachable,
    )


def score_change(
    sources: Mapping[str, str],
    change: VendorChange,
    sites: Sequence[CallSite],
    targets: Sequence[str],
    store: GraphStore,
    repo: RepoRef,
    adapter,
) -> ScoredPair:
    """Generate a pair for `change` and score it, which is the whole path in one call.

    `sites` are the call sites of the *unmutated* tree with the ids the store assigned, which
    `index_sources` returns; the mutation is positional, so it has to be computed against the
    tree the positions were read from. A change kind the generator cannot invert is refused here
    rather than scored -- an unmutated tree labels every site unaffected and produces no
    findings, which reads as a flawless run rather than as a generator that declined.
    """
    return score_pair(generate_pair(sources, change, sites, targets), change, store, repo, adapter)
