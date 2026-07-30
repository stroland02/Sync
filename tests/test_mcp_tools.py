"""The graph surface: the three read tools, answered from the graph.

`docs/superpowers/specs/2026-07-25-sync-graph-surface-design.md` freezes four tools.
`sync_propose_patch` needs the remediation pipeline and is deliberately absent here -- the spec
says the three read tools can ship before it, and `src/sync/remediate/` belongs to another
worker right now.

The rules under test are the spec's, and each exists because breaking it costs an agent
context: never return file contents, stay shallow, paginate every list, and report provenance
honestly rather than smoothing it over.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from sync.core import CallSite, Finding, VendorChange
from sync.mcp.tools import GraphSurface

INDEXED = datetime(2026, 7, 28, 6, 0, tzinfo=timezone.utc)
FETCHED = datetime(2026, 7, 28, 7, 0, tzinfo=timezone.utc)


def _site(site_id, path="src/pay.ts", line=12, op="PostCharges", vendor="stripe", indexed_at=INDEXED):
    return CallSite(
        id=site_id, repo_id="r", path=path, line=line, col=4, vendor_id=vendor,
        operation_id=op, symbol="stripe.charges.create",
        args_keys=["amount", "currency"], response_fields_read=["status"],
        sdk_version="18.0.0", content_hash="h", indexed_at=indexed_at,
    )


def _change(change_id, vendor="stripe", op="PostCharges", kind="response-property-removed"):
    return VendorChange(
        id=change_id, vendor_id=vendor, from_version="2026-05-01", to_version="2026-11-01",
        kind=kind, operation_id=op, path_ptr="/v1/charges", severity="breaking",
        source="oasdiff", raw={"text": "removed the optional property `status`"},
    )


def _finding(finding_id, site_id, change_id, severity="breaking"):
    return Finding(
        id=finding_id, detector="vendor-change", claim="response-field",
        call_site_id=site_id,
        vendor_change_id=change_id, severity=severity, rationale="status was removed",
    )


class FakeGraph:
    """The narrow read surface the tools need, which `GraphStore` already satisfies."""

    def __init__(self, findings=(), sites=(), changes=()):
        self._findings = list(findings)
        self._sites = {s.id: s for s in sites}
        self._changes = {c.id: c for c in changes}

    def open_findings(self):
        return list(self._findings)

    def get_call_site(self, call_site_id):
        return self._sites[call_site_id]

    def get_vendor_change(self, change_id):
        return self._changes[change_id]

    def all_vendor_changes(self, vendor_id):
        return [c for c in self._changes.values() if c.vendor_id == vendor_id]


def _surface(**kw):
    graph = FakeGraph(**kw)
    return GraphSurface(graph, feed_fetched_at=FETCHED)


def _default():
    return _surface(
        findings=[_finding("f1", "cs1", "vc1"), _finding("f2", "cs2", "vc1", severity="deprecation")],
        sites=[_site("cs1"), _site("cs2", path="src/other.ts", line=40)],
        changes=[_change("vc1")],
    )


# --- sync_whats_at_risk -----------------------------------------------------------


def test_it_lists_the_bindings_at_risk():
    result = _default().whats_at_risk()

    assert {row["file"] for row in result["items"]} == {"src/pay.ts", "src/other.ts"}
    assert result["items"][0]["operation"] == "PostCharges"


def test_it_filters_by_path_prefix():
    result = _default().whats_at_risk(path="src/pay.ts")
    assert [row["file"] for row in result["items"]] == ["src/pay.ts"]


def test_it_filters_by_vendor_and_severity():
    surface = _default()

    assert len(surface.whats_at_risk(vendor="stripe")["items"]) == 2
    assert surface.whats_at_risk(vendor="adyen")["items"] == []
    assert len(surface.whats_at_risk(severity="breaking")["items"]) == 1


def test_no_arguments_answers_rather_than_refusing():
    """The spec left this open. It answers, because the list is bounded by findings rather
    than by files, and a tool that refuses the question an agent starts with is not a tool.
    Pagination is what keeps the unbounded case safe."""
    assert _default().whats_at_risk()["items"]


def test_a_finding_whose_call_site_vanished_is_skipped_not_fatal():
    """The index outlives the tree it was built from. One dangling row must not deny an agent
    every other answer."""
    surface = _surface(
        findings=[_finding("f1", "gone", "vc1"), _finding("f2", "cs1", "vc1")],
        sites=[_site("cs1")],
        changes=[_change("vc1")],
    )
    assert [row["finding_id"] for row in surface.whats_at_risk()["items"]] == ["f2"]


# --- pagination, mandatory on every list ------------------------------------------


def test_lists_are_paginated():
    surface = _surface(
        findings=[_finding(f"f{i}", "cs1", "vc1") for i in range(10)],
        sites=[_site("cs1")], changes=[_change("vc1")],
    )
    page = surface.whats_at_risk(limit=3)

    assert len(page["items"]) == 3
    assert page["total"] == 10
    assert page["next_offset"] == 3


def test_the_last_page_reports_no_next_offset():
    """An agent needs to know it is done. A next offset that always exists is an infinite
    loop with extra steps."""
    surface = _surface(
        findings=[_finding(f"f{i}", "cs1", "vc1") for i in range(4)],
        sites=[_site("cs1")], changes=[_change("vc1")],
    )
    assert surface.whats_at_risk(limit=10)["next_offset"] is None


def test_an_offset_reads_further_in():
    surface = _surface(
        findings=[_finding(f"f{i}", "cs1", "vc1") for i in range(5)],
        sites=[_site("cs1")], changes=[_change("vc1")],
    )
    assert [r["finding_id"] for r in surface.whats_at_risk(limit=2, offset=2)["items"]] == ["f2", "f3"]


# --- sync_explain_call_site -------------------------------------------------------


def test_it_explains_a_call_site():
    result = _default().explain_call_site("src/pay.ts", 12)

    assert result["symbol"] == "stripe.charges.create"
    assert result["operation"] == "PostCharges"
    assert result["args_keys"] == ["amount", "currency"]
    assert result["sdk_version"] == "18.0.0"


def test_the_known_changes_are_shallow_references_not_full_records():
    """Shallow by default. Returning every change in full is how a tool hands back the tokens
    the graph exists to save."""
    changes = _default().explain_call_site("src/pay.ts", 12)["known_changes"]

    assert changes and set(changes[0]) == {"change_id", "kind", "severity"}


def test_an_unknown_call_site_returns_none_rather_than_raising():
    assert _default().explain_call_site("src/nowhere.ts", 1) is None


# --- sync_whats_changed -----------------------------------------------------------


def test_it_lists_what_a_vendor_changed():
    result = _default().whats_changed("stripe")

    assert result["items"][0]["operation"] == "PostCharges"
    assert result["items"][0]["change_kind"] == "response-property-removed"


def test_an_unknown_vendor_returns_an_empty_page_not_an_error():
    assert _default().whats_changed("adyen")["items"] == []


# --- provenance, on every response ------------------------------------------------


@pytest.mark.parametrize("call", ["risk", "explain", "changed"])
def test_every_response_carries_the_provenance_fields(call: str):
    surface = _default()
    result = {
        "risk": lambda: surface.whats_at_risk(),
        "explain": lambda: surface.explain_call_site("src/pay.ts", 12),
        "changed": lambda: surface.whats_changed("stripe"),
    }[call]()

    assert {"indexed_at", "feed_fetched_at", "binding_source", "context_savings"} <= result.keys()
    assert result["feed_fetched_at"] == FETCHED.isoformat()
    assert result["binding_source"] == "static"


@pytest.mark.parametrize("call", ["risk", "explain"])
def test_answers_drawn_from_the_index_report_when_it_was_built(call: str):
    surface = _default()
    result = {
        "risk": lambda: surface.whats_at_risk(),
        "explain": lambda: surface.explain_call_site("src/pay.ts", 12),
    }[call]()

    assert result["indexed_at"] == INDEXED.isoformat()


@pytest.mark.parametrize("order", [("new", "old"), ("old", "new")])
def test_a_page_reports_the_newest_index_time_it_drew_on(order):
    """`indexed_at` on a list is a claim about the page, so it is the newest of the sites the
    page was built from and not whichever was read last.

    Both orderings, because either "keep the first" or "keep the last" answers one of them
    correctly by accident. Understating a page's freshness sends an agent back to files the
    graph already knew about, which is the cost the whole surface exists to avoid.
    """
    older = datetime(2026, 7, 20, 6, 0, tzinfo=timezone.utc)
    newer = datetime(2026, 7, 27, 6, 0, tzinfo=timezone.utc)
    stamps = {"new": newer, "old": older}
    surface = _surface(
        findings=[_finding(f"f{n}", f"cs-{name}", "vc1") for n, name in enumerate(order)],
        sites=[_site(f"cs-{name}", indexed_at=stamps[name]) for name in order],
        changes=[_change("vc1")],
    )

    assert surface.whats_at_risk()["indexed_at"] == newer.isoformat()


def test_a_call_site_always_carries_an_index_time():
    """The premise the page timestamp rests on, asserted where the consequence lives.

    `CallSite.indexed_at` is a non-optional `datetime`, so the one caller that folds site
    timestamps together cannot be handed a null candidate and its null branch is unreachable.
    `docs/superpowers/reports/2026-07-30-mcp-tool-surface-declines.md` records that branch as
    redundant rather than removing it; this is what stops the premise from changing silently.
    Making `indexed_at` optional fails here, beside the code that would then need the branch.
    """
    with pytest.raises(ValueError):
        CallSite(
            id="cs1", repo_id="r", path="src/pay.ts", line=12, col=4, vendor_id="stripe",
            operation_id="PostCharges", symbol="stripe.charges.create",
            sdk_version="18.0.0", content_hash="h", indexed_at=None,
        )

    assert _site("cs1").indexed_at == INDEXED


def test_whats_changed_reports_no_index_time_because_it_reads_no_index():
    """The field is present, and null.

    `whats_changed` answers from vendor changes and never touches the call-site index, so an
    index timestamp would attach a freshness from one subsystem to an answer produced by
    another. Present-and-null says "this answer does not depend on the index"; a borrowed
    timestamp would quietly claim it does.
    """
    result = _default().whats_changed("stripe")

    assert "indexed_at" in result
    assert result["indexed_at"] is None


def test_provenance_is_a_timestamp_not_a_duration():
    """A duration computed at response time expires silently once the answer is cached; a
    timestamp cannot claim a freshness it no longer has."""
    assert "T" in _default().whats_at_risk()["indexed_at"]


def test_binding_source_is_never_claimed_higher_than_it_was_established():
    """`resolved` requires a compiler pass and `observed` requires production telemetry.
    Neither has run here, so reporting either would be a claim about trustworthiness that
    nothing supports."""
    assert _default().whats_at_risk()["binding_source"] == "static"


# --- the rules that make the surface worth having ---------------------------------


def test_no_response_returns_file_contents():
    """The binding is the answer. A tool that returns source has given back the tokens the
    graph exists to save."""
    surface = _default()
    for result in (surface.whats_at_risk(), surface.explain_call_site("src/pay.ts", 12),
                   surface.whats_changed("stripe")):
        assert "source" not in result
        assert "contents" not in result


def test_every_response_reports_context_savings():
    """The efficiency claim, measured inside the payload rather than asserted outside it."""
    result = _default().whats_at_risk()
    assert isinstance(result["context_savings"], int)
    assert result["context_savings"] > 0


def test_an_empty_result_claims_no_savings():
    """Zero findings saved nobody anything, and a tool that inflates its own value is one
    nobody can use to measure the product."""
    empty = _surface().whats_at_risk()
    assert empty["items"] == []
    assert empty["context_savings"] == 0


# --- the protocol is satisfied by the real store ----------------------------------


def test_the_real_graph_store_satisfies_the_reader_protocol():
    """`GraphReader` is structural so `GraphStore` need not import it, which means nothing
    enforces the match. This is that enforcement: a rename on either side fails here rather
    than at runtime against a live database.
    """
    import inspect

    from sync.graph.store import GraphStore
    from sync.mcp.tools import GraphReader

    for name in ("open_findings", "get_call_site", "get_vendor_change", "all_vendor_changes"):
        assert hasattr(GraphStore, name), f"GraphStore lost {name}, which the graph surface calls"

        expected = list(inspect.signature(getattr(GraphReader, name)).parameters)
        actual = list(inspect.signature(getattr(GraphStore, name)).parameters)
        assert expected == actual, f"{name} signature drifted: surface expects {expected}, store has {actual}"
