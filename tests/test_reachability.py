"""Ranking a repository's third-party surface by what the indexer actually found.

Step 5 of `2026-07-29-sync-adaptive-vendor-substrate.md`, and the property that makes it worth
having: *"declared but never called" is exactly the noise that would otherwise flood a
coverage-driven system.*

What is asserted here is not that the order is pleasant. It is the four things that decide
whether the order is honest:

- a dependency nothing calls ranks below one that is called, which is the whole point;
- a dependency nothing could bind is never reported as one nothing calls, because those two
  zeroes mean opposite things and read identically;
- the static count and the observed count stay separable, since one is shape and the other is
  volume;
- equal rows come out in the same order every time, or nobody can diff two reports.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from sync.core import CallSite, ObservedCall
from sync.signals.intake import (
    MISSING_REGISTRY_ENTRY,
    MISSING_SDK_BINDING,
    NOT_WATCHABLE,
    NPM,
    PYPI,
    WATCHABLE,
    WATCHED,
    Assessment,
    Dependency,
    IntakeReport,
    assess_repository,
)
from sync.signals.reachability import (
    CALLED,
    UNBINDABLE,
    UNCALLED,
    call_site_counts,
    observed_call_counts,
    rank_reachability,
)

REACHABILITY_SOURCE = Path(__file__).parents[1] / "src" / "sync" / "signals" / "reachability.py"


def _assessment(
    name: str,
    category: str,
    vendor_id: str | None = None,
    missing: str | None = None,
    ecosystem: str = NPM,
) -> Assessment:
    return Assessment(
        dependency=Dependency(name=name, version="1.0.0", ecosystem=ecosystem),
        category=category,
        reason=f"{name} is {category}",
        vendor_id=vendor_id,
        missing=missing,
    )


def _report(*assessments: Assessment) -> IntakeReport:
    return IntakeReport(assessments=tuple(assessments), unreadable=())


def _names(ranking) -> list[str]:
    return [row.dependency.name for row in ranking.rows]


def _by_name(ranking):
    return {row.dependency.name: row for row in ranking.rows}


def _site(vendor_id: str, line: int) -> CallSite:
    return CallSite(
        repo_id="r1", path="src/billing.ts", line=line, col=0, vendor_id=vendor_id,
        operation_id="PostCharges", symbol=f"{vendor_id}.charges.create",
        sdk_version="1.0.0", content_hash=f"h{line}",
    )


def _observed(vendor_id: str, spans: int, trace: str) -> ObservedCall:
    return ObservedCall(
        repo_id="r1", vendor_id=vendor_id, operation_id="PostCharges", binding_rung="observed",
        server_address="api.example.invalid", http_method="POST", trace_id=trace,
        spans={f"s{index}": {"target": "t", "status": 200, "resend": 0} for index in range(spans)},
    )


# --- the point of the task ------------------------------------------------------------


def test_a_dependency_nothing_calls_ranks_below_one_that_is_called():
    """A manifest entry no line of code reaches is not exposure. Both are watched, both are
    bound, and only one of them is anywhere in the repository's actual surface."""
    report = _report(
        _assessment("twilio", WATCHED, vendor_id="twilio"),
        _assessment("stripe", WATCHED, vendor_id="stripe"),
    )

    ranking = rank_reachability(report, call_sites={"stripe": 3})

    assert _names(ranking) == ["stripe", "twilio"]
    assert _by_name(ranking)["stripe"].evidence == CALLED
    assert _by_name(ranking)["twilio"].evidence == UNCALLED


def test_more_call_sites_rank_above_fewer():
    report = _report(
        _assessment("twilio", WATCHED, vendor_id="twilio"),
        _assessment("stripe", WATCHED, vendor_id="stripe"),
    )

    ranking = rank_reachability(report, call_sites={"stripe": 2, "twilio": 9})

    assert _names(ranking) == ["twilio", "stripe"]


# --- unbindable is not unused ---------------------------------------------------------


def test_a_dependency_nothing_can_bind_is_not_reported_as_one_nothing_calls():
    """The test that stops the ranking lying.

    Both dependencies have no call sites and the reasons are opposite. `twilio` is watched: the
    indexer knew which package to look for, looked, and found nothing -- a measured zero. `openai`
    is served by an adapter that declares no binding, so nothing could be bound and no call site
    could exist however heavily the repository calls it. Rendered as the same zero, the second
    tells a reader the opposite of the truth.
    """
    report = _report(
        _assessment("twilio", WATCHED, vendor_id="twilio"),
        _assessment("openai", WATCHABLE, vendor_id="openai", missing=MISSING_SDK_BINDING),
    )

    ranking = rank_reachability(report, call_sites={})
    rows = _by_name(ranking)

    assert rows["openai"].evidence == UNBINDABLE
    assert rows["openai"].call_sites is None
    assert rows["twilio"].evidence == UNCALLED
    assert rows["twilio"].call_sites == 0
    assert _names(ranking) == ["openai", "twilio"]


def test_an_unbindable_dependency_a_tier_could_serve_outranks_one_no_tier_can():
    """`intake` already splits watchable from not-watchable and calls the middle one the work
    queue. Carrying that into the order is what keeps the ranking from flooding: a repository
    declaring forty npm packages has thirty-eight nothing can ever watch, and putting all of
    them above a watched vendor would bury the answer under the noise the spec names.
    """
    report = _report(
        _assessment("lodash", NOT_WATCHABLE),
        _assessment("@vercel/sdk", WATCHABLE, missing=MISSING_REGISTRY_ENTRY),
    )

    ranking = rank_reachability(report, call_sites={})

    assert _names(ranking) == ["@vercel/sdk", "lodash"]
    assert all(row.evidence == UNBINDABLE for row in ranking.rows)


def test_a_measured_zero_outranks_a_dependency_no_tier_can_serve():
    """Both are dead ends for different reasons, and the watched one is the one an operator can
    act on: it is configured, it was looked at, and the answer was nothing."""
    report = _report(
        _assessment("lodash", NOT_WATCHABLE),
        _assessment("twilio", WATCHED, vendor_id="twilio"),
    )

    ranking = rank_reachability(report, call_sites={})

    assert _names(ranking) == ["twilio", "lodash"]


# --- the two counts stay apart --------------------------------------------------------


def test_the_static_and_observed_counts_are_reported_separately():
    """`schema.sql` already argues this on `loop_depth`: static evidence is proof of shape and
    not of volume, and the two are not interchangeable. A single number nobody can decompose is
    the thing both specs refuse.
    """
    report = _report(_assessment("stripe", WATCHED, vendor_id="stripe"))

    ranking = rank_reachability(report, call_sites={"stripe": 2}, observed_calls={"stripe": 50})
    row = ranking.rows[0]

    assert row.call_sites == 2
    assert row.observed_calls == 50

    rendered = json.loads(ranking.to_json())["rows"][0]
    assert rendered["call_sites"] == 2
    assert rendered["observed_calls"] == 50


def test_a_vendor_with_no_telemetry_reports_no_observed_count_rather_than_zero():
    """Most repositories send Sync nothing. A zero there would say the vendor was watched and
    never called, which is the same conflation the evidence classes exist to prevent, one column
    over."""
    report = _report(_assessment("stripe", WATCHED, vendor_id="stripe"))

    row = rank_reachability(report, call_sites={"stripe": 2}).rows[0]

    assert row.call_sites == 2
    assert row.observed_calls is None


def test_observed_calls_sum_spans_rather_than_counting_rows():
    """`ObservedCall`'s grain is one row per trace, and its own docstring says a query counting
    vendor calls by counting rows undercounts exactly where the efficiency detector looks."""
    counts = observed_call_counts([
        _observed("stripe", spans=3, trace="t1"),
        _observed("stripe", spans=2, trace="t2"),
        _observed("twilio", spans=1, trace="t3"),
    ])

    assert counts == {"stripe": 5, "twilio": 1}


def test_call_sites_are_counted_per_vendor():
    counts = call_site_counts([_site("stripe", 3), _site("stripe", 9), _site("twilio", 4)])

    assert counts == {"stripe": 2, "twilio": 1}


# --- the empty answer, and the stable one ---------------------------------------------


def test_a_repository_with_no_dependencies_ranks_nothing():
    """An answer, not an error. A repository with no third-party call sites has nothing to
    prioritise and saying so is the correct output."""
    ranking = rank_reachability(_report())

    assert ranking.rows == ()
    assert ranking.counts() == {CALLED: 0, UNBINDABLE: 0, UNCALLED: 0}
    assert json.loads(ranking.to_json())["rows"] == []


def test_equal_rows_come_out_in_the_same_order_whatever_order_they_went_in():
    """A ranking that reorders equal rows between runs is one nobody can diff, and every row
    here ties on every count."""
    forward = [
        _assessment("alpha", NOT_WATCHABLE),
        _assessment("beta", NOT_WATCHABLE),
        _assessment("gamma", NOT_WATCHABLE),
    ]

    assert _names(rank_reachability(_report(*forward))) == ["alpha", "beta", "gamma"]
    assert _names(rank_reachability(_report(*reversed(forward)))) == ["alpha", "beta", "gamma"]


def test_a_package_named_the_same_in_two_ecosystems_still_orders_deterministically():
    """The name alone is not unique: `openai` is on npm and on PyPI, and a repository can
    declare both. The ecosystem is what completes the key."""
    report = _report(
        _assessment("openai", NOT_WATCHABLE, ecosystem=PYPI),
        _assessment("openai", NOT_WATCHABLE, ecosystem=NPM),
    )

    ranking = rank_reachability(report)

    assert [row.dependency.ecosystem for row in ranking.rows] == [NPM, PYPI]


# --- what a reader needs to disagree with the order -----------------------------------


def test_every_input_that_produced_the_order_survives_into_the_row():
    """Rank, not score. There is no weighted number to argue with, so the inputs have to be
    beside each row or the order is unfalsifiable."""
    report = _report(
        _assessment("openai", WATCHABLE, vendor_id="openai", missing=MISSING_SDK_BINDING)
    )

    rendered = json.loads(rank_reachability(_report(*report.assessments)).to_json())["rows"][0]

    assert rendered["category"] == WATCHABLE
    assert rendered["missing"] == MISSING_SDK_BINDING
    assert rendered["vendor_id"] == "openai"
    assert rendered["evidence"] == UNBINDABLE
    assert "openai is watchable" in rendered["reason"]


def test_no_row_carries_a_composite_score():
    """`CLAUDE.md` and the benchmark spec both refuse invented thresholds, and a weighted score
    is a threshold with extra steps -- it hides which input moved it. Asserted on the rendered
    keys, because that is the surface a reader would quote."""
    report = _report(_assessment("stripe", WATCHED, vendor_id="stripe"))

    rendered = json.loads(
        rank_reachability(report, call_sites={"stripe": 4}, observed_calls={"stripe": 8}).to_json()
    )["rows"][0]

    assert not any(key in rendered for key in ("score", "risk", "weight", "priority"))


def test_the_ranking_reads_no_database_and_no_index():
    """Pure, the way `intake.assess_repository` is. Both counts arrive as arguments, so the
    ordering is testable against fixtures with nothing running -- and a module that imported a
    store would make the report of what is on disk quietly require one.
    """
    tree = ast.parse(REACHABILITY_SOURCE.read_text(encoding="utf-8"))
    imported = {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    } | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }

    forbidden = [name for name in imported if name.startswith(("sync.graph", "sync.index"))]
    assert forbidden == []


# --- against a real manifest ----------------------------------------------------------


def test_a_real_manifest_ranks_the_called_vendor_first(tmp_path: Path):
    """End to end over `assess_repository`, so the ranking is exercised against the shape intake
    really produces rather than against hand-built assessments alone."""
    (tmp_path / "package.json").write_text(
        json.dumps({"dependencies": {"stripe": "^18.0.0", "lodash": "^4.0.0", "react": "^19.0.0"}}),
        encoding="utf-8",
    )
    report = assess_repository(tmp_path)

    ranking = rank_reachability(report, call_sites=call_site_counts([_site("stripe", 6)]))

    assert _names(ranking)[0] == "stripe"
    assert _by_name(ranking)["stripe"].evidence == CALLED
    assert _by_name(ranking)["stripe"].call_sites == 1
    assert {row.evidence for row in ranking.rows if row.dependency.name != "stripe"} == {UNBINDABLE}


def test_the_counts_add_up_to_the_rows():
    report = _report(
        _assessment("stripe", WATCHED, vendor_id="stripe"),
        _assessment("twilio", WATCHED, vendor_id="twilio"),
        _assessment("lodash", NOT_WATCHABLE),
    )

    ranking = rank_reachability(report, call_sites={"stripe": 1})

    assert ranking.counts() == {CALLED: 1, UNCALLED: 1, UNBINDABLE: 1}
    assert sum(ranking.counts().values()) == len(ranking.rows)
