"""The three surfaces that make seven finished components reachable from the command line.

Every component wired here was built correctly, tested, and left with no caller for a reason
recorded in `scripts/dead_links_baseline.txt`. Those reasons expired -- the two files each of
them was blocked on came free -- and this is the wiring the baseline entries said would retire
them.

What is asserted here is driven from the command rather than from the component. Calling
`rank_reachability` in a test proves nothing this is about; running `sync intake` and seeing a
ranking does. Each of the three sections below drives `main()` with an argv and reads what came
out of stdout, because that is the surface an operator has.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from sync.cli import main
from sync.core import CallSite, ObservedCall
from sync.graph.store import GraphStore

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")

# Declares one vendor Sync can bind, one it cannot, and one nothing knows about. All three are
# needed: without the second the ranking cannot show that unbindable outranks a measured zero,
# and without the third every row would be a vendor.
MANIFEST = {
    "dependencies": {
        "stripe": "^18.0.0",
        "twilio": "^5.0.0",
        "lodash": "^4.0.0",
    }
}


@pytest.fixture()
def store() -> GraphStore:
    s = GraphStore(DSN)
    s.apply_schema()
    s.truncate_all()
    return s


@pytest.fixture()
def checkout(tmp_path: Path) -> Path:
    (tmp_path / "package.json").write_text(json.dumps(MANIFEST), encoding="utf-8")
    return tmp_path


def _site(vendor_id: str, line: int) -> CallSite:
    return CallSite(
        repo_id="r1", path="src/billing.ts", line=line, col=0, vendor_id=vendor_id,
        operation_id="PostCharges", symbol=f"{vendor_id}.charges.create",
        sdk_version="1.0.0", content_hash=f"h{vendor_id}{line}",
    )


def _observed(vendor_id: str, spans: int, trace: str) -> ObservedCall:
    return ObservedCall(
        repo_id="r1", vendor_id=vendor_id, operation_id="PostCharges", binding_rung="observed",
        server_address="api.example.invalid", http_method="POST", trace_id=trace,
        spans={f"s{index}": {"target": "t", "status": 200, "resend": 0} for index in range(spans)},
    )


def _cli(monkeypatch, capsys, *argv: str) -> tuple[int, str]:
    monkeypatch.setattr(sys, "argv", ["sync", *argv])
    code = main()
    return code, capsys.readouterr().out


# --- the store reader ------------------------------------------------------------------


def test_a_vendor_with_no_call_sites_is_absent_from_the_count_rather_than_zero(store):
    """The absence rule the baseline entry spelled out.

    A zero asserts one of two facts the query cannot tell apart -- the indexer looked and found
    nothing, or it never looked -- and only the intake category resolves which. A reader that
    filled in zeros would have made that resolution itself, wrongly, in the one place that has
    no way to be right about it.
    """
    store.upsert_call_site(_site("stripe", 6))

    counts = store.call_site_counts("r1")

    assert counts == {"stripe": 1}
    assert "twilio" not in counts


def test_call_sites_are_counted_per_vendor_not_per_dependency(store):
    """One row is one indexed location. A vendor called from three places is three, which is the
    number ranking is about, and is not the one dependency the manifest declares."""
    for line in (6, 11, 20):
        store.upsert_call_site(_site("stripe", line))
    store.upsert_call_site(_site("twilio", 6))

    assert store.call_site_counts("r1") == {"stripe": 3, "twilio": 1}


def test_the_count_does_not_leak_another_repository(store):
    """Scoped to a repository for the reason `observed_calls` is: it is the unit a finding is
    raised against, and a count carrying another customer's call sites would rank the wrong
    code."""
    store.upsert_call_site(_site("stripe", 6))
    other = _site("stripe", 6).model_copy(update={"repo_id": "r2"})
    store.upsert_call_site(other)

    assert store.call_site_counts("r1") == {"stripe": 1}


def test_a_repository_nothing_indexed_counts_nothing(store):
    assert store.call_site_counts("never-indexed") == {}


# --- sync intake ranks -----------------------------------------------------------------


def test_intake_without_the_flag_still_reports_the_three_way_split(monkeypatch, capsys, checkout):
    """The ranking is an additional question, not a replacement. Coverage and priority are
    different reports and the command answers whichever was asked for."""
    code, out = _cli(monkeypatch, capsys, "intake", "--repo", str(checkout))

    assert code == 0
    payload = json.loads(out)
    assert set(payload["counts"]) == {"watched", "watchable", "not-watchable"}
    assert "rows" not in payload


def test_intake_ranks_a_called_dependency_above_one_nothing_calls(
    monkeypatch, capsys, checkout, store
):
    """The point of the ranking, driven from the command.

    `stripe` and `twilio` are both watched: both are registered and both declare an SDK binding,
    so the indexer knew which package to look for in each case. Only one of them appears in the
    code.
    """
    store.upsert_call_site(_site("stripe", 6))

    code, out = _cli(
        monkeypatch, capsys, "intake", "--repo", str(checkout),
        "--rank-by-repo-id", "r1", "--dsn", DSN,
    )

    assert code == 0
    rows = json.loads(out)["rows"]
    names = [row["name"] for row in rows]
    assert names.index("stripe") < names.index("twilio")
    by_name = {row["name"]: row for row in rows}
    assert by_name["stripe"]["evidence"] == "called"
    assert by_name["stripe"]["call_sites"] == 1
    assert by_name["twilio"]["evidence"] == "uncalled"
    assert by_name["twilio"]["call_sites"] == 0


def test_intake_never_reports_an_unbindable_dependency_as_one_nothing_calls(
    monkeypatch, capsys, checkout, store
):
    """The test that stops the wiring lying.

    `lodash` has no registered vendor at all, so no call site for it could ever exist however
    heavily the repository uses it -- absence of evidence. `twilio` is bound and was looked at
    and found absent -- a measured zero. Rendered as the same zero, the first tells a reader the
    opposite of the truth.
    """
    store.upsert_call_site(_site("stripe", 6))

    _, out = _cli(
        monkeypatch, capsys, "intake", "--repo", str(checkout),
        "--rank-by-repo-id", "r1", "--dsn", DSN,
    )

    by_name = {row["name"]: row for row in json.loads(out)["rows"]}
    assert by_name["lodash"]["evidence"] == "unbindable"
    assert by_name["lodash"]["call_sites"] is None
    assert by_name["twilio"]["evidence"] == "uncalled"
    assert by_name["twilio"]["call_sites"] == 0


def test_intake_reports_observed_calls_beside_the_static_count(
    monkeypatch, capsys, checkout, store
):
    """Two counts, never folded. One is shape and the other is volume, and a reader given their
    sum cannot decompose it."""
    store.upsert_call_site(_site("stripe", 6))
    store.record_observed_call(_observed("stripe", spans=4, trace="t1"))

    _, out = _cli(
        monkeypatch, capsys, "intake", "--repo", str(checkout),
        "--rank-by-repo-id", "r1", "--dsn", DSN,
    )

    stripe = next(row for row in json.loads(out)["rows"] if row["name"] == "stripe")
    assert stripe["call_sites"] == 1
    assert stripe["observed_calls"] == 4


def test_intake_ranking_carries_no_threshold_and_no_score(monkeypatch, capsys, checkout, store):
    """Rank, not score. Position in the list is the rank and every input that produced it is on
    the row, because a weighted number is a threshold with extra steps."""
    store.upsert_call_site(_site("stripe", 6))

    _, out = _cli(
        monkeypatch, capsys, "intake", "--repo", str(checkout),
        "--rank-by-repo-id", "r1", "--dsn", DSN,
    )

    for row in json.loads(out)["rows"]:
        assert not any(key in row for key in ("score", "risk", "weight", "priority", "threshold"))


# --- sync benchmark scores --------------------------------------------------------------


def test_benchmark_without_a_pair_reports_the_axes_it_always_did(monkeypatch, capsys):
    """Scoring is an addition. A corpus with no rows and no generated pair still renders every
    axis unmeasured over zero samples, which is the honest answer and the one a reviewer needs
    before there is data."""
    code, out = _cli(monkeypatch, capsys, "benchmark", "--dsn", DSN)

    assert code == 0
    assert "binding precision" in out
    assert "unmeasured" in out


SPEC_JSON = json.dumps({"openapi": "3.0.0", "info": {"title": "t", "version": "1"}, "paths": {}})

CORPUS_TS = """import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);

export async function chargeCustomer(amount: number) {
  const charge = await stripe.charges.create({ amount, currency: 'eur' });
  return charge.id;
}

export async function lookUpCharge(id: string) {
  const found = await stripe.charges.retrieve(id);
  return found.amount;
}
"""


@pytest.fixture()
def corpus(tmp_path: Path) -> Path:
    """A pair specification, and the checkout and cache it names.

    A file rather than eight flags, and for the reason `generated-vendors.yaml` is a file: the
    corpus a score was taken over is worth having only if it is recorded where a reader can
    check it. The cache holds what `load_vendor` reads offline -- the symbol map that lets the
    indexer resolve a call, and the two specification files the vendor is staged against.
    """
    import yaml

    checkout = tmp_path / "checkout"
    (checkout / "src").mkdir(parents=True)
    (checkout / "package.json").write_text(
        json.dumps({"dependencies": {"stripe": "^18.0.0"}}), encoding="utf-8"
    )
    (checkout / "src" / "billing.ts").write_text(CORPUS_TS, encoding="utf-8")

    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "symbols.json").write_text(
        json.dumps({
            "stripe.charges.create": {
                "operation_id": "PostCharges", "http_method": "post", "path": "/v1/charges"
            },
            "stripe.charges.retrieve": {
                "operation_id": "GetChargesCharge", "http_method": "get",
                "path": "/v1/charges/{charge}"
            },
        }),
        encoding="utf-8",
    )
    for version in ("2026-05-01", "2026-11-01"):
        (cache / f"{version}.json").write_text(SPEC_JSON, encoding="utf-8")

    spec = tmp_path / "corpus.yaml"
    spec.write_text(
        yaml.safe_dump({
            "repo": str(checkout),
            "vendor": "stripe",
            "cache": str(cache),
            "from_version": "2026-05-01",
            "to_version": "2026-11-01",
            "change": {
                "kind": "request-property-removed",
                "operation": "PostCharges",
                "field": "receipt_email",
            },
        }),
        encoding="utf-8",
    )
    return spec


@pytest.fixture()
def score_dsn() -> str:
    """A database of its own, because scoring truncates the graph it scores in.

    `score_pair` empties the store before indexing the mutated tree -- the detector reads every
    call site the graph holds, so a row from another tree is a finding nobody labelled. Pointed
    at the corpus database that would destroy the corpus the same command is reporting on.
    """
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict, make_conninfo

    parts = conninfo_to_dict(DSN)
    name = f"{parts['dbname']}_score"
    admin = make_conninfo(**{**parts, "dbname": "postgres"})
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    return make_conninfo(**{**parts, "dbname": name})


def test_benchmark_refuses_to_score_into_the_database_it_is_reporting_on(
    monkeypatch, capsys, corpus
):
    """Scoring truncates. Pointed at the corpus database it would delete the migration outcomes
    the same command just rendered, so the two databases have to be different and the refusal is
    what makes that impossible to get wrong once."""
    monkeypatch.setattr(sys, "argv", [
        "sync", "benchmark", "--dsn", DSN, "--score-pair", str(corpus), "--score-dsn", DSN,
    ])
    assert main() != 0
    assert "same database" in capsys.readouterr().err


def test_benchmark_scores_a_generated_pair_and_reports_both_axes_with_sample_sizes(
    monkeypatch, capsys, corpus, score_dsn
):
    """The two axes the benchmark specification calls the ones that matter most, computed over a
    pair this command generates and scores. Sample sizes because a rate without its denominator
    is the number that specification spends a section warning about.
    """
    code, out = _cli(monkeypatch, capsys, "benchmark", "--dsn", DSN,
                     "--score-pair", str(corpus), "--score-dsn", score_dsn)

    assert code == 0
    assert "binding precision" in out
    assert "binding recall" in out
    # `n=` beside each, and neither of them the unmeasured placeholder any more.
    precision = next(line for line in out.splitlines() if line.startswith("binding precision"))
    recall = next(line for line in out.splitlines() if line.startswith("binding recall"))
    assert "n=" in precision and "unmeasured" not in precision
    assert "n=" in recall and "unmeasured" not in recall


def test_benchmark_says_its_reference_is_synthetic_beside_the_score(
    monkeypatch, capsys, corpus, score_dsn
):
    """A benchmark whose bias is undocumented is worse than none. The reference is a mechanical
    mutation of a real repository, and the caveat has to travel to the page rather than live in
    a specification the reader of the number never opens."""
    _, out = _cli(monkeypatch, capsys, "benchmark", "--dsn", DSN,
                  "--score-pair", str(corpus), "--score-dsn", score_dsn)

    assert "synthetic" in out
    assert "About the binding reference" in out


def test_benchmark_compares_nothing_to_a_threshold(monkeypatch, capsys, corpus, score_dsn):
    """Tier C is explicit: do not invent a threshold. The exit code says the report was produced
    and not whether the numbers were good, and no pass mark appears anywhere on the page."""
    code, out = _cli(monkeypatch, capsys, "benchmark", "--dsn", DSN,
                     "--score-pair", str(corpus), "--score-dsn", score_dsn)

    assert code == 0
    # The word appears once, in the sentence denying one. What must not appear is a verdict.
    assert "nothing here is compared against a threshold" in out
    assert not any(word in out for word in ("PASS", "FAIL", "OK ", "REGRESSION"))


# --- sync intake consumes the registry directory -----------------------------------------

DIRECTORY = {
    "acme.com": {
        "preferred": "1.0",
        "versions": {
            "1.0": {
                "updated": "2026-07-01T00:00:00.000Z",
                "swaggerUrl": "https://api.apis.guru/v2/specs/acme.com/1.0/openapi.json",
                "openapiVer": "3.0",
            }
        },
    },
    "ancient.com": {
        "preferred": "0.1",
        "versions": {
            "0.1": {
                "updated": "2017-06-27T16:49:57.000Z",
                "swaggerUrl": "https://api.apis.guru/v2/specs/ancient.com/0.1/swagger.json",
                "openapiVer": "2.0",
            }
        },
    },
}


@pytest.fixture()
def registry_files(tmp_path: Path) -> tuple[Path, Path]:
    """A directory document and the confirmed package-to-entry evidence that joins it.

    The join is evidence and never a name resemblance, which is the rule intake already holds:
    `@vercel/sdk` is generated from `vercel/sdk` and resembles nothing, and a package
    coincidentally sharing an API's name has nothing to do with it. A directory `api_id` is a
    domain and a package name is not, so somebody has to have confirmed the pair.
    """
    import yaml

    directory = tmp_path / "list.json"
    directory.write_text(json.dumps(DIRECTORY), encoding="utf-8")

    evidence = tmp_path / "registry-apis.yaml"
    evidence.write_text(
        yaml.safe_dump([
            {"package": "acme-sdk", "api": "acme.com"},
            {"package": "ancient-sdk", "api": "ancient.com"},
        ]),
        encoding="utf-8",
    )
    return directory, evidence


@pytest.fixture()
def registry_checkout(tmp_path: Path) -> Path:
    root = tmp_path / "declares"
    root.mkdir()
    (root / "package.json").write_text(
        json.dumps({"dependencies": {"stripe": "^18.0.0", "acme-sdk": "^1.0.0"}}),
        encoding="utf-8",
    )
    return root


def _intake(monkeypatch, capsys, checkout: Path, *extra: str):
    code, out = _cli(monkeypatch, capsys, "intake", "--repo", str(checkout), *extra)
    assert code == 0
    return {row["name"]: row for row in json.loads(out)["dependencies"]}


def test_without_the_directory_a_package_no_tier_serves_is_not_watchable(
    monkeypatch, capsys, registry_checkout
):
    """The control. Whatever the directory changes, it has to change something -- a test that
    only asserts the promoted state cannot tell a working join from one that promotes
    everything."""
    rows = _intake(monkeypatch, capsys, registry_checkout)

    assert rows["acme-sdk"]["category"] == "not-watchable"


def test_a_registry_directory_entry_makes_a_dependency_watchable(
    monkeypatch, capsys, registry_checkout, registry_files
):
    """One document answers what exists across every vendor, which is what intake needs to tell
    a customer a declared dependency has a machine-readable contract somewhere."""
    directory, evidence = registry_files

    rows = _intake(
        monkeypatch, capsys, registry_checkout,
        "--registry-directory", str(directory), "--registry-evidence", str(evidence),
    )

    assert rows["acme-sdk"]["category"] == "watchable"
    assert rows["acme-sdk"]["missing"] == "registry-tier"
    assert "acme.com" in rows["acme-sdk"]["reason"]


def test_a_registry_directory_entry_alone_never_makes_a_dependency_watched(
    monkeypatch, capsys, registry_checkout, registry_files
):
    """The rule intake already established: watched needs a registered vendor *and* a declared
    SDK binding. A directory knowing an API exists is neither, and the artifact it points at is
    the directory's own mirror rather than the vendor's, so a change derived from it is a third
    derivation from the vendor's truth and must never look like one a pull request could rest on.
    """
    directory, evidence = registry_files

    rows = _intake(
        monkeypatch, capsys, registry_checkout,
        "--registry-directory", str(directory), "--registry-evidence", str(evidence),
    )

    assert rows["acme-sdk"]["category"] != "watched"
    assert rows["acme-sdk"]["vendor_id"] is None
    # And it cannot demote or duplicate a dependency a real vendor already serves.
    assert rows["stripe"]["category"] == "watched"
    assert rows["stripe"]["vendor_id"] == "stripe"


def test_a_directory_entry_that_has_not_moved_since_the_watermark_is_not_promoted(
    monkeypatch, capsys, tmp_path, registry_files
):
    """`versions_after` is the tier's whole economy: one watermark, one document, and what moved
    without downloading a specification. An entry last touched in 2017 proves a contract existed
    once, which is a weaker claim than one that moved last month, and an operator asking for the
    live ones gets the strict answer.
    """
    directory, evidence = registry_files
    root = tmp_path / "stale"
    root.mkdir()
    (root / "package.json").write_text(
        json.dumps({"dependencies": {"acme-sdk": "^1.0.0", "ancient-sdk": "^0.1.0"}}),
        encoding="utf-8",
    )

    rows = _intake(
        monkeypatch, capsys, root,
        "--registry-directory", str(directory), "--registry-evidence", str(evidence),
        "--registry-moved-since", "2026-01-01T00:00:00.000Z",
    )

    assert rows["acme-sdk"]["category"] == "watchable"
    assert rows["ancient-sdk"]["category"] == "not-watchable"


def test_a_package_merely_resembling_a_directory_entry_is_not_promoted(
    monkeypatch, capsys, tmp_path, registry_files
):
    """The join is confirmed evidence and never a resemblance.

    `ancient` looks exactly like the front of `ancient.com` and nobody confirmed the pair, so it
    stays not-watchable. Intake already holds this rule for the generator tier -- `@vercel/sdk`
    is generated from `vercel/sdk` and resembles nothing, and a package coincidentally sharing an
    API's name has nothing to do with it -- and a directory of thousands of domains is where a
    resemblance rule would do the most damage.
    """
    directory, evidence = registry_files
    root = tmp_path / "resembles"
    root.mkdir()
    (root / "package.json").write_text(
        json.dumps({"dependencies": {"ancient": "^1.0.0", "acme": "^1.0.0"}}), encoding="utf-8"
    )

    rows = _intake(
        monkeypatch, capsys, root,
        "--registry-directory", str(directory), "--registry-evidence", str(evidence),
    )

    assert rows["ancient"]["category"] == "not-watchable"
    assert rows["acme"]["category"] == "not-watchable"
