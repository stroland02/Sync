"""The HTTP transport for the operator console: thin Starlette routes over `GraphSurface`.

Every route is one call into the surface and one JSON return. The rules under test are the
plan's, and each exists because breaking it costs the console its read-only guarantee: the
route returns the surface's payload unaltered, pagination parameters pass through and are
bounded, an unknown identifier is a 404 with a JSON body, and no route mutates -- proved by
driving every route against a surface that records what it was asked, so the constraint is
tested by behaviour rather than by grepping the source for the shape a mutation might take.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NamedTuple

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from sync.api.__main__ import DEFAULT_PORT, _reload_enabled, app_factory
from sync.api.app import _MAX_LIMIT, _SCAN_LIMIT, create_app
from sync.core import CallSite, Finding, VendorChange
from sync.dashboard.queries import _FINISHED
from sync.mcp.tools import DEFAULT_LIMIT, GraphSurface

INDEXED = datetime(2026, 7, 28, 6, 0, tzinfo=timezone.utc)
FETCHED = datetime(2026, 7, 28, 7, 0, tzinfo=timezone.utc)


def _site(
    site_id,
    path="src/pay.ts",
    line=12,
    op="PostCharges",
    vendor="stripe",
    indexed_at=INDEXED,
):
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


def _finding(finding_id, site_id, change_id, severity="breaking", rung="static"):
    return Finding(
        id=finding_id, detector="vendor-change", claim="response-field",
        call_site_id=site_id, vendor_change_id=change_id, severity=severity,
        rationale="status was removed", binding_rung=rung,
    )


class FakeGraph:
    """The narrow read surface the routes' surface needs."""

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


def _web_source(relative: str) -> str:
    """A file out of `web/`, or a skip when the console is not checked out here."""
    path = Path(__file__).resolve().parent.parent / "web" / relative
    if not path.is_file():
        pytest.skip(f"web/{relative} is absent; this checkout carries no console")
    return path.read_text(encoding="utf-8")


def _fake_runs_reader(*, limit: int, offset: int) -> dict[str, Any]:
    return {"items": [], "total": 0, "next_offset": None}


def _fake_corpus_reader() -> dict[str, Any]:
    return {
        "attempts": 0,
        "distinct_findings": 0,
        "by_terminal_status": {},
        "by_strategy": {},
        "by_tier": {},
    }


def _fake_repositories_reader() -> dict[str, Any]:
    return {"repo_ids": []}


_EMPTY_PAGE = {"items": [], "total": 0, "next_offset": None}


def _fake_binding_reader(
    vendor_id: str,
    operation_id: str,
    *,
    repo_id=None,
    binding_rung=None,
    call_sites_limit=DEFAULT_LIMIT,
    call_sites_offset=0,
    changes_limit=DEFAULT_LIMIT,
    changes_offset=0,
) -> dict[str, Any]:
    return {
        "vendor_id": vendor_id, "operation_id": operation_id, "repo_id": repo_id,
        "call_sites": dict(_EMPTY_PAGE), "changes": dict(_EMPTY_PAGE),
    }


def _fake_coverage_reader(repo_id: str) -> dict[str, Any]:
    return {"repo_id": repo_id, "by_vendor": {}, "total_call_sites": 0}


def _fake_observed_reader(
    repo_id: str,
    *,
    calls_limit=DEFAULT_LIMIT,
    calls_offset=0,
    shapes_limit=DEFAULT_LIMIT,
    shapes_offset=0,
    error_windows_limit=DEFAULT_LIMIT,
    error_windows_offset=0,
) -> dict[str, Any]:
    return {
        "repo_id": repo_id,
        "calls": dict(_EMPTY_PAGE),
        "shapes": dict(_EMPTY_PAGE),
        "error_windows": dict(_EMPTY_PAGE),
    }


def _fake_detector_reader() -> dict[str, Any]:
    return {"detectors": [], "total_open_findings": 0}


def _fake_severity_reader() -> dict[str, Any]:
    return {"by_severity": {}, "total": 0}


def _fake_overview_reader() -> dict[str, Any]:
    return {
        "vendors": [],
        "total_findings": 0,
        "total_findings_bound": 1000,
        "total_findings_bound_reached": False,
        "indexed_at": None,
        "feed_fetched_at": None,
        "binding_source": None,
        "context_savings": 0,
    }


def _build_app(
    *,
    surface: GraphSurface,
    workflow_reader=lambda finding_id: None,
    runs_reader=_fake_runs_reader,
    corpus_reader=_fake_corpus_reader,
    repositories_reader=_fake_repositories_reader,
    binding_reader=_fake_binding_reader,
    coverage_reader=_fake_coverage_reader,
    observed_reader=_fake_observed_reader,
    detector_reader=_fake_detector_reader,
    severity_reader=_fake_severity_reader,
    overview_reader=_fake_overview_reader,
) -> Starlette:
    """`create_app` with every reader defaulted to a fake, so a test naming one override is
    not forced to restate the other nine.

    `create_app` keeps every reader required -- a deployment that forgets one should fail
    at start-up rather than serve a route that breaks on first use. That signature stays as
    written; this helper exists only so the test file does not repeat the full argument list
    at every call site.
    """
    return create_app(
        surface=surface,
        workflow_reader=workflow_reader,
        runs_reader=runs_reader,
        corpus_reader=corpus_reader,
        repositories_reader=repositories_reader,
        binding_reader=binding_reader,
        coverage_reader=coverage_reader,
        observed_reader=observed_reader,
        detector_reader=detector_reader,
        severity_reader=severity_reader,
        overview_reader=overview_reader,
    )


def _client(**graph_kw) -> TestClient:
    graph = FakeGraph(**graph_kw)
    surface = GraphSurface(graph, feed_fetched_at=FETCHED)
    app = _build_app(surface=surface)
    return TestClient(app)


# -- overview -------------------------------------------------------------------
#
# `/api/overview` no longer reaches `GraphSurface.whats_at_risk` at all -- `sync.mcp.tools` is
# frozen and `whats_at_risk` always walks every open finding doing one `get_call_site` round trip
# per row, so no `limit` bounds the scan underneath it. `sync.dashboard.graph_views.overview_summary`
# answers the same question straight from `GraphStore` in real SQL instead (its own docstring and
# `tests/test_graph_views.py` carry the bounded-count and unbounded-distribution behaviour); these
# tests hold only the route's half of the contract -- it forwards its `overview_reader` verbatim,
# merges in `severity_counts` from its own separate reader, and reaches each reader exactly once.


def test_overview_returns_the_overview_readers_payload():
    payload = {
        "vendors": [{"vendor_id": "stripe", "open_finding_count": 2}],
        "total_findings": 2,
        "total_findings_bound": 1000,
        "total_findings_bound_reached": False,
        "indexed_at": "2026-07-28T06:00:00+00:00",
        "feed_fetched_at": None,
        "binding_source": "static",
        "context_savings": 800,
    }
    app = _build_app(
        surface=GraphSurface(FakeGraph(), feed_fetched_at=FETCHED), overview_reader=lambda: payload
    )
    client = TestClient(app)

    response = client.get("/api/overview")

    assert response.status_code == 200
    body = response.json()
    for key, value in payload.items():
        assert body[key] == value, key


def test_overview_reports_the_bound_and_whether_it_was_reached():
    payload = {
        **_fake_overview_reader(),
        "total_findings": 1000,
        "total_findings_bound": 1000,
        "total_findings_bound_reached": True,
    }
    app = _build_app(
        surface=GraphSurface(FakeGraph(), feed_fetched_at=FETCHED), overview_reader=lambda: payload
    )
    client = TestClient(app)

    body = client.get("/api/overview").json()

    assert body["total_findings"] == 1000
    assert body["total_findings_bound"] == 1000
    assert body["total_findings_bound_reached"] is True


def test_overview_includes_the_severity_counts_from_its_own_reader():
    payload = {"by_severity": {"breaking": 3, "warning": 1}, "total": 4}
    app = _build_app(
        surface=GraphSurface(FakeGraph(), feed_fetched_at=FETCHED), severity_reader=lambda: payload
    )
    client = TestClient(app)

    body = client.get("/api/overview").json()

    assert body["severity_counts"] == {"breaking": 3, "warning": 1}


def test_overview_reaches_its_severity_reader_exactly_once_with_no_arguments():
    calls: list[None] = []

    def severity_reader():
        calls.append(None)
        return _fake_severity_reader()

    app = _build_app(
        surface=GraphSurface(FakeGraph(), feed_fetched_at=FETCHED), severity_reader=severity_reader
    )
    client = TestClient(app)

    client.get("/api/overview")

    assert calls == [None]


def test_overview_reaches_its_overview_reader_exactly_once_with_no_arguments():
    calls: list[None] = []

    def overview_reader():
        calls.append(None)
        return _fake_overview_reader()

    app = _build_app(
        surface=GraphSurface(FakeGraph(), feed_fetched_at=FETCHED), overview_reader=overview_reader
    )
    client = TestClient(app)

    client.get("/api/overview")

    assert calls == [None]


def test_overview_never_reaches_the_frozen_surface():
    # The behavioural half of the same claim `overview_summary`'s docstring makes: this route
    # must not fall back to `whats_at_risk` for anything, including on an overview reader that
    # returns an empty payload -- a surface reached here at all is the scan defect regressing.
    surface = RecordingSurface(GraphSurface(FakeGraph(), feed_fetched_at=FETCHED))
    app = _build_app(surface=surface)
    client = TestClient(app)

    client.get("/api/overview")

    assert surface.method_names() == set()


# -- vendor detail --------------------------------------------------------------


def test_vendor_route_calls_whats_at_risk_filtered_by_vendor():
    stripe_site = _site("s1", vendor="stripe")
    shopify_site = _site("s2", vendor="shopify", op="GetOrders")
    change_stripe = _change("c1", vendor="stripe")
    change_shopify = _change("c2", vendor="shopify", op="GetOrders")
    client = _client(
        findings=[_finding("f1", "s1", "c1"), _finding("f2", "s2", "c2")],
        sites=[stripe_site, shopify_site],
        changes=[change_stripe, change_shopify],
    )

    body = client.get("/api/vendors/stripe").json()

    assert body["total"] == 1
    assert body["items"][0]["vendor"] == "stripe"
    assert body["items"][0]["finding_id"] == "f1"


def test_vendor_route_passes_pagination_through():
    findings, sites, changes = [], [], []
    change = _change("c1", vendor="stripe")
    changes.append(change)
    for i in range(5):
        site = _site(f"s{i}", vendor="stripe", path=f"src/a{i}.ts", line=i + 1)
        sites.append(site)
        findings.append(_finding(f"f{i}", f"s{i}", "c1"))
    client = _client(findings=findings, sites=sites, changes=changes)

    body = client.get("/api/vendors/stripe?limit=2&offset=1").json()

    assert body["total"] == 5
    assert len(body["items"]) == 2
    assert body["next_offset"] == 3


def test_vendor_route_passes_the_severity_filter_through_to_the_frozen_surface():
    # `whats_at_risk` has accepted `severity` since it was written (`tools.py:89-95`); no route
    # ever passed it. This is what exposes it -- one query parameter, no change to `tools.py`.
    breaking_site = _site("s1", vendor="stripe")
    warning_site = _site("s2", vendor="stripe", path="src/other.ts", line=44)
    change = _change("c1", vendor="stripe")
    client = _client(
        findings=[
            _finding("f1", "s1", "c1", severity="breaking"),
            _finding("f2", "s2", "c1", severity="warning"),
        ],
        sites=[breaking_site, warning_site],
        changes=[change],
    )

    body = client.get("/api/vendors/stripe?severity=breaking").json()

    assert body["total"] == 1
    assert body["items"][0]["finding_id"] == "f1"


def test_vendor_route_passes_the_path_filter_through_to_the_frozen_surface():
    billing_site = _site("s1", vendor="stripe", path="src/billing/pay.ts")
    other_site = _site("s2", vendor="stripe", path="src/other/pay.ts")
    change = _change("c1", vendor="stripe")
    client = _client(
        findings=[_finding("f1", "s1", "c1"), _finding("f2", "s2", "c1")],
        sites=[billing_site, other_site],
        changes=[change],
    )

    body = client.get("/api/vendors/stripe?path=src/billing").json()

    assert body["total"] == 1
    assert body["items"][0]["finding_id"] == "f1"


def test_vendor_route_severity_and_path_default_to_no_filter_when_absent():
    site_a = _site("s1", vendor="stripe")
    site_b = _site("s2", vendor="stripe", path="src/other.ts", line=44)
    change = _change("c1", vendor="stripe")
    client = _client(
        findings=[_finding("f1", "s1", "c1"), _finding("f2", "s2", "c1")],
        sites=[site_a, site_b],
        changes=[change],
    )

    body = client.get("/api/vendors/stripe").json()

    assert body["total"] == 2


def test_vendor_route_a_negative_offset_is_floored_not_turned_into_a_negative_slice():
    # `_int_param` returns whatever an out-of-range value parses to, and `offset` was never
    # clamped the way `limit` is (`app.py:88` clamps limit; offset went straight to the surface).
    # A negative offset is a slice bound in the surface's own Python-side pagination, not a page.
    client, surface, *_ = _recording_client()

    client.get("/api/vendors/stripe?offset=-5")

    offsets = [kwargs["offset"] for _, kwargs in surface.calls if "offset" in kwargs]
    assert offsets == [0]


def test_vendor_changes_route_a_negative_offset_is_floored():
    client, surface, *_ = _recording_client()

    client.get("/api/vendors/stripe/changes?offset=-5")

    offsets = [kwargs["offset"] for _, kwargs in surface.calls if "offset" in kwargs]
    assert offsets == [0]


def test_runs_route_a_negative_offset_is_floored():
    reader, calls = _recording_runs_reader()
    app = _build_app(surface=GraphSurface(FakeGraph(), feed_fetched_at=FETCHED), runs_reader=reader)
    client = TestClient(app)

    client.get("/api/runs?offset=-3")

    assert calls == [{"limit": DEFAULT_LIMIT, "offset": 0}]


def test_vendor_route_returns_empty_page_for_unknown_vendor():
    # `whats_at_risk` returns an empty page for a vendor with no findings; the route
    # matches that shape rather than 404, because the surface itself says that "nothing
    # matches" is an answer, not a failure.
    client = _client()

    response = client.get("/api/vendors/nobody")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["items"] == []


# -- finding detail --------------------------------------------------------------


def test_finding_route_returns_explain_call_site_plus_change():
    site = _site("s1")
    change = _change("c1")
    client = _client(
        findings=[_finding("f1", "s1", "c1")],
        sites=[site],
        changes=[change],
    )

    response = client.get("/api/findings/f1")

    assert response.status_code == 200
    body = response.json()
    # explain_call_site's payload passes through
    assert body["symbol"] == "stripe.charges.create"
    assert body["operation"] == "PostCharges"
    assert body["vendor"] == "stripe"
    # the change shows shallow, matching the surface's rule
    assert body["known_changes"][0]["change_id"] == "c1"


def test_finding_route_carries_the_findings_own_rung_beside_the_pages():
    # Two detectors bind one call site by different rungs, so the envelope's rung is null --
    # it describes the whole answer and the answer rests on no single binding. The rung of
    # the finding the URL names is a column on its row, and the two routes must not return
    # the same payload for two findings that were bound differently.
    site = _site("s1")
    change = _change("c1")
    client = _client(
        findings=[
            _finding("f1", "s1", "c1", rung="static"),
            _finding("f2", "s1", "c1", rung="observed"),
        ],
        sites=[site],
        changes=[change],
    )

    static = client.get("/api/findings/f1").json()
    observed = client.get("/api/findings/f2").json()

    assert static["binding_source"] is None
    assert observed["binding_source"] is None
    assert static["finding"] == {"finding_id": "f1", "binding_source": "static"}
    assert observed["finding"] == {"finding_id": "f2", "binding_source": "observed"}


def test_finding_route_returns_404_json_for_unknown_finding():
    client = _client()

    response = client.get("/api/findings/does-not-exist")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert "error" in body


# -- vendor changes --------------------------------------------------------------


def test_vendor_changes_route_calls_whats_changed():
    change_a = _change("c1", vendor="stripe", op="PostCharges")
    change_b = _change("c2", vendor="stripe", op="GetBalance", kind="response-property-removed")
    client = _client(changes=[change_a, change_b])

    body = client.get("/api/vendors/stripe/changes").json()

    assert body["total"] == 2
    ops = {row["operation"] for row in body["items"]}
    assert ops == {"PostCharges", "GetBalance"}


def test_vendor_changes_pagination_passes_through():
    changes = [
        _change(f"c{i}", vendor="stripe", op=f"Op{i}") for i in range(4)
    ]
    client = _client(changes=changes)

    body = client.get("/api/vendors/stripe/changes?limit=1&offset=2").json()

    assert body["total"] == 4
    assert len(body["items"]) == 1
    assert body["next_offset"] == 3


# -- workflows -------------------------------------------------------------------


def test_workflow_route_returns_reader_payload_unaltered():
    payload = {
        "nodes": [{"name": "locate", "status": "done", "evidence": {"tier": "static"}}],
        "outcome": None,
        "abandon_reason": None,
    }
    surface = GraphSurface(FakeGraph(), feed_fetched_at=FETCHED)
    app = _build_app(surface=surface, workflow_reader=lambda finding_id: payload)
    client = TestClient(app)

    response = client.get("/api/workflows/f1")

    assert response.status_code == 200
    assert response.json() == payload


def test_workflow_route_returns_404_when_reader_yields_none():
    surface = GraphSurface(FakeGraph(), feed_fetched_at=FETCHED)
    app = _build_app(surface=surface, workflow_reader=lambda finding_id: None)
    client = TestClient(app)

    response = client.get("/api/workflows/unknown")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert "error" in body


# -- fleet roll-ups: runs, corpus, repositories ---------------------------------


def test_runs_route_returns_the_readers_payload_unaltered():
    payload = {
        "items": [{"thread_id": "f1:0", "finding_id": "f1", "outcome": "opened"}],
        "total": 1,
        "next_offset": None,
    }
    app = _build_app(
        surface=GraphSurface(FakeGraph(), feed_fetched_at=FETCHED),
        runs_reader=lambda *, limit, offset: payload,
    )
    client = TestClient(app)

    response = client.get("/api/runs")

    assert response.status_code == 200
    assert response.json() == payload


def test_corpus_route_returns_the_readers_payload_unaltered():
    payload = {
        "attempts": 3,
        "distinct_findings": 2,
        "by_terminal_status": {"opened": 2, "abandoned": 1},
        "by_strategy": {"patch": 3},
        "by_tier": {"low": 3},
    }
    app = _build_app(
        surface=GraphSurface(FakeGraph(), feed_fetched_at=FETCHED),
        corpus_reader=lambda: payload,
    )
    client = TestClient(app)

    response = client.get("/api/corpus")

    assert response.status_code == 200
    assert response.json() == payload


def test_repositories_route_returns_the_readers_payload_unaltered():
    payload = {"repo_ids": ["r1", "r2"]}
    app = _build_app(
        surface=GraphSurface(FakeGraph(), feed_fetched_at=FETCHED),
        repositories_reader=lambda: payload,
    )
    client = TestClient(app)

    response = client.get("/api/repositories")

    assert response.status_code == 200
    assert response.json() == payload


def _recording_runs_reader():
    calls: list[dict[str, int]] = []

    def reader(*, limit: int, offset: int) -> dict[str, Any]:
        calls.append({"limit": limit, "offset": offset})
        return {"items": [], "total": 0, "next_offset": None}

    return reader, calls


def test_runs_route_passes_limit_and_offset_to_its_reader():
    reader, calls = _recording_runs_reader()
    app = _build_app(surface=GraphSurface(FakeGraph(), feed_fetched_at=FETCHED), runs_reader=reader)
    client = TestClient(app)

    client.get("/api/runs?limit=7&offset=3")

    assert calls == [{"limit": 7, "offset": 3}]


def test_runs_route_limit_above_the_ceiling_is_clamped():
    reader, calls = _recording_runs_reader()
    app = _build_app(surface=GraphSurface(FakeGraph(), feed_fetched_at=FETCHED), runs_reader=reader)
    client = TestClient(app)

    client.get(f"/api/runs?limit={_MAX_LIMIT * 1000}")

    assert calls == [{"limit": _MAX_LIMIT, "offset": 0}]


def test_runs_route_a_limit_under_the_ceiling_passes_through_untouched():
    reader, calls = _recording_runs_reader()
    app = _build_app(surface=GraphSurface(FakeGraph(), feed_fetched_at=FETCHED), runs_reader=reader)
    client = TestClient(app)

    client.get("/api/runs?limit=9")

    assert calls == [{"limit": 9, "offset": 0}]


def test_runs_route_a_negative_limit_is_floored():
    reader, calls = _recording_runs_reader()
    app = _build_app(surface=GraphSurface(FakeGraph(), feed_fetched_at=FETCHED), runs_reader=reader)
    client = TestClient(app)

    client.get("/api/runs?limit=-1")

    assert calls == [{"limit": 1, "offset": 0}]


def test_runs_route_a_zero_limit_is_floored():
    reader, calls = _recording_runs_reader()
    app = _build_app(surface=GraphSurface(FakeGraph(), feed_fetched_at=FETCHED), runs_reader=reader)
    client = TestClient(app)

    client.get("/api/runs?limit=0")

    assert calls == [{"limit": 1, "offset": 0}]


def test_corpus_route_reaches_its_reader_exactly_once_with_no_arguments():
    calls: list[None] = []

    def corpus_reader():
        calls.append(None)
        return _fake_corpus_reader()

    app = _build_app(surface=GraphSurface(FakeGraph(), feed_fetched_at=FETCHED), corpus_reader=corpus_reader)
    client = TestClient(app)

    client.get("/api/corpus")

    assert calls == [None]


def test_repositories_route_reaches_its_reader_exactly_once_with_no_arguments():
    calls: list[None] = []

    def repositories_reader():
        calls.append(None)
        return _fake_repositories_reader()

    app = _build_app(
        surface=GraphSurface(FakeGraph(), feed_fetched_at=FETCHED),
        repositories_reader=repositories_reader,
    )
    client = TestClient(app)

    client.get("/api/repositories")

    assert calls == [None]


# -- the graph views: bindings, coverage, observed telemetry, detectors --------


def test_binding_route_returns_the_readers_payload_unaltered():
    payload = {
        "vendor_id": "stripe", "operation_id": "PostCharges", "repo_id": None,
        "call_sites": [{"path": "src/pay.ts", "binding_rung": "static"}], "changes": [],
    }
    app = _build_app(
        surface=GraphSurface(FakeGraph(), feed_fetched_at=FETCHED),
        binding_reader=lambda vendor_id, operation_id, *, repo_id=None, **_: payload,
    )
    client = TestClient(app)

    response = client.get("/api/vendors/stripe/operations/PostCharges/bindings")

    assert response.status_code == 200
    assert response.json() == payload


def test_binding_route_passes_the_path_segments_and_the_repo_id_query_param():
    calls: list[tuple[str, str, str | None]] = []

    def reader(vendor_id: str, operation_id: str, *, repo_id=None, **_):
        calls.append((vendor_id, operation_id, repo_id))
        return _fake_binding_reader(vendor_id, operation_id, repo_id=repo_id)

    app = _build_app(surface=GraphSurface(FakeGraph(), feed_fetched_at=FETCHED), binding_reader=reader)
    client = TestClient(app)

    client.get("/api/vendors/stripe/operations/PostCharges/bindings?repo_id=r1")

    assert calls == [("stripe", "PostCharges", "r1")]


def test_binding_route_repo_id_defaults_to_none_when_the_query_param_is_absent():
    calls: list[tuple[str, str, str | None]] = []

    def reader(vendor_id: str, operation_id: str, *, repo_id=None, **_):
        calls.append((vendor_id, operation_id, repo_id))
        return _fake_binding_reader(vendor_id, operation_id, repo_id=repo_id)

    app = _build_app(surface=GraphSurface(FakeGraph(), feed_fetched_at=FETCHED), binding_reader=reader)
    client = TestClient(app)

    client.get("/api/vendors/stripe/operations/PostCharges/bindings")

    assert calls == [("stripe", "PostCharges", None)]


def test_binding_route_passes_binding_rung_and_defaults_it_to_none():
    calls: list[str | None] = []

    def reader(vendor_id: str, operation_id: str, *, binding_rung=None, **_):
        calls.append(binding_rung)
        return _fake_binding_reader(vendor_id, operation_id)

    app = _build_app(surface=GraphSurface(FakeGraph(), feed_fetched_at=FETCHED), binding_reader=reader)
    client = TestClient(app)

    client.get("/api/vendors/stripe/operations/PostCharges/bindings?binding_rung=observed")
    client.get("/api/vendors/stripe/operations/PostCharges/bindings")

    assert calls == ["observed", None]


def test_binding_route_call_sites_and_changes_paginate_independently():
    calls: list[dict[str, int]] = []

    def reader(vendor_id: str, operation_id: str, **kwargs):
        calls.append(
            {
                "call_sites_limit": kwargs["call_sites_limit"],
                "call_sites_offset": kwargs["call_sites_offset"],
                "changes_limit": kwargs["changes_limit"],
                "changes_offset": kwargs["changes_offset"],
            }
        )
        return _fake_binding_reader(vendor_id, operation_id)

    app = _build_app(surface=GraphSurface(FakeGraph(), feed_fetched_at=FETCHED), binding_reader=reader)
    client = TestClient(app)

    client.get(
        "/api/vendors/stripe/operations/PostCharges/bindings"
        "?call_sites_limit=3&call_sites_offset=6&changes_limit=9&changes_offset=12"
    )

    assert calls == [
        {"call_sites_limit": 3, "call_sites_offset": 6, "changes_limit": 9, "changes_offset": 12}
    ]


def test_binding_route_pagination_defaults_and_clamps_match_the_other_routes():
    calls: list[dict[str, int]] = []

    def reader(vendor_id: str, operation_id: str, **kwargs):
        calls.append(
            {"call_sites_limit": kwargs["call_sites_limit"], "call_sites_offset": kwargs["call_sites_offset"]}
        )
        return _fake_binding_reader(vendor_id, operation_id)

    app = _build_app(surface=GraphSurface(FakeGraph(), feed_fetched_at=FETCHED), binding_reader=reader)
    client = TestClient(app)

    client.get(f"/api/vendors/stripe/operations/PostCharges/bindings?call_sites_limit={_MAX_LIMIT * 1000}&call_sites_offset=-5")

    assert calls == [{"call_sites_limit": _MAX_LIMIT, "call_sites_offset": 0}]


def test_coverage_route_returns_the_readers_payload_unaltered():
    payload = {"repo_id": "r1", "by_vendor": {"stripe": 3}, "total_call_sites": 3}
    app = _build_app(
        surface=GraphSurface(FakeGraph(), feed_fetched_at=FETCHED),
        coverage_reader=lambda repo_id: payload,
    )
    client = TestClient(app)

    response = client.get("/api/repositories/r1/coverage")

    assert response.status_code == 200
    assert response.json() == payload


def test_coverage_route_passes_the_path_repo_id_to_its_reader():
    calls: list[str] = []

    def reader(repo_id: str):
        calls.append(repo_id)
        return _fake_coverage_reader(repo_id)

    app = _build_app(surface=GraphSurface(FakeGraph(), feed_fetched_at=FETCHED), coverage_reader=reader)
    client = TestClient(app)

    client.get("/api/repositories/r1/coverage")

    assert calls == ["r1"]


def test_observed_route_returns_the_readers_payload_unaltered():
    payload = {"repo_id": "r1", "calls": dict(_EMPTY_PAGE), "shapes": dict(_EMPTY_PAGE), "error_windows": dict(_EMPTY_PAGE)}
    app = _build_app(
        surface=GraphSurface(FakeGraph(), feed_fetched_at=FETCHED),
        observed_reader=lambda repo_id, **_: payload,
    )
    client = TestClient(app)

    response = client.get("/api/repositories/r1/observed")

    assert response.status_code == 200
    assert response.json() == payload


def test_observed_route_passes_the_path_repo_id_to_its_reader():
    calls: list[str] = []

    def reader(repo_id: str, **_):
        calls.append(repo_id)
        return _fake_observed_reader(repo_id)

    app = _build_app(surface=GraphSurface(FakeGraph(), feed_fetched_at=FETCHED), observed_reader=reader)
    client = TestClient(app)

    client.get("/api/repositories/r1/observed")

    assert calls == ["r1"]


def test_observed_route_paginates_calls_shapes_and_error_windows_independently():
    calls: list[dict[str, int]] = []

    def reader(repo_id: str, **kwargs):
        calls.append(kwargs)
        return _fake_observed_reader(repo_id)

    app = _build_app(surface=GraphSurface(FakeGraph(), feed_fetched_at=FETCHED), observed_reader=reader)
    client = TestClient(app)

    client.get(
        "/api/repositories/r1/observed"
        "?calls_limit=1&calls_offset=2&shapes_limit=3&shapes_offset=4"
        "&error_windows_limit=5&error_windows_offset=6"
    )

    assert calls == [
        {
            "calls_limit": 1, "calls_offset": 2,
            "shapes_limit": 3, "shapes_offset": 4,
            "error_windows_limit": 5, "error_windows_offset": 6,
        }
    ]


def test_observed_route_pagination_defaults_when_absent():
    calls: list[dict[str, int]] = []

    def reader(repo_id: str, **kwargs):
        calls.append(kwargs)
        return _fake_observed_reader(repo_id)

    app = _build_app(surface=GraphSurface(FakeGraph(), feed_fetched_at=FETCHED), observed_reader=reader)
    client = TestClient(app)

    client.get("/api/repositories/r1/observed")

    assert calls == [
        {
            "calls_limit": DEFAULT_LIMIT, "calls_offset": 0,
            "shapes_limit": DEFAULT_LIMIT, "shapes_offset": 0,
            "error_windows_limit": DEFAULT_LIMIT, "error_windows_offset": 0,
        }
    ]


def test_detectors_route_returns_the_readers_payload_unaltered():
    payload = {
        "detectors": [{"detector": "vendor-change", "total": 2, "by_rung": {"static": 2}}],
        "total_open_findings": 2,
    }
    app = _build_app(
        surface=GraphSurface(FakeGraph(), feed_fetched_at=FETCHED),
        detector_reader=lambda: payload,
    )
    client = TestClient(app)

    response = client.get("/api/detectors")

    assert response.status_code == 200
    assert response.json() == payload


def test_detectors_route_reaches_its_reader_exactly_once_with_no_arguments():
    calls: list[None] = []

    def detector_reader():
        calls.append(None)
        return _fake_detector_reader()

    app = _build_app(
        surface=GraphSurface(FakeGraph(), feed_fetched_at=FETCHED), detector_reader=detector_reader
    )
    client = TestClient(app)

    client.get("/api/detectors")

    assert calls == [None]


# -- the read-only constraint, as a test rather than a promise ------------------

# The three surface methods a read-only console is allowed to reach. `propose_patch` is
# absent deliberately: it clones the customer's repository, installs its dependencies and
# runs `tsc`, all of which the plan forbids a console route from doing.
_READ_ONLY_METHODS = frozenset({"whats_at_risk", "explain_call_site", "whats_changed"})


class RecordingSurface:
    """A `GraphSurface` that remembers what the routes asked it.

    Reads are delegated so the routes see real payloads. `propose_patch` is the one method
    the transport may not reach, so it raises instead of running: a route that called it
    would otherwise pass every assertion here and still start a remediation run.
    """

    def __init__(self, inner: GraphSurface) -> None:
        self._inner = inner
        self.calls: list[tuple[str, dict]] = []

    def __getattr__(self, name: str):
        attribute = getattr(self._inner, name)

        def recorded(*args, **kwargs):
            self.calls.append((name, kwargs))
            return attribute(*args, **kwargs)

        return recorded

    def propose_patch(self, *args, **kwargs):
        self.calls.append(("propose_patch", kwargs))
        raise AssertionError("a read-only transport must never propose a patch")

    def method_names(self) -> set[str]:
        return {name for name, _ in self.calls}


class _RecordingClient(NamedTuple):
    """What one `_recording_client()` call hands back to a test.

    Still unpacks positionally (`client, surface, *_ = ...`) for the call sites that only
    want the first two fields, and now supports named access (`.workflow_reads`) for any
    that want more.
    """

    client: TestClient
    surface: "RecordingSurface"
    workflow_reads: list[str]
    runs_reads: list[dict[str, int]]
    corpus_reads: list[None]
    repositories_reads: list[None]
    binding_reads: list[tuple[str, str, str | None]]
    coverage_reads: list[str]
    observed_reads: list[str]
    detector_reads: list[None]
    severity_reads: list[None]
    overview_reads: list[None]


def _recording_client(**graph_kw) -> _RecordingClient:
    surface = RecordingSurface(GraphSurface(FakeGraph(**graph_kw), feed_fetched_at=FETCHED))
    workflow_reads: list[str] = []
    runs_reads: list[dict[str, int]] = []
    corpus_reads: list[None] = []
    repositories_reads: list[None] = []
    binding_reads: list[tuple[str, str, str | None]] = []
    coverage_reads: list[str] = []
    observed_reads: list[str] = []
    detector_reads: list[None] = []
    severity_reads: list[None] = []
    overview_reads: list[None] = []

    def workflow_reader(finding_id: str):
        workflow_reads.append(finding_id)
        return {"nodes": [], "outcome": None, "abandon_reason": None}

    def runs_reader(*, limit: int, offset: int):
        runs_reads.append({"limit": limit, "offset": offset})
        return {"items": [], "total": 0, "next_offset": None}

    def corpus_reader():
        corpus_reads.append(None)
        return _fake_corpus_reader()

    def repositories_reader():
        repositories_reads.append(None)
        return _fake_repositories_reader()

    def binding_reader(vendor_id: str, operation_id: str, *, repo_id=None, **_):
        binding_reads.append((vendor_id, operation_id, repo_id))
        return _fake_binding_reader(vendor_id, operation_id, repo_id=repo_id)

    def coverage_reader(repo_id: str):
        coverage_reads.append(repo_id)
        return _fake_coverage_reader(repo_id)

    def observed_reader(repo_id: str, **_):
        observed_reads.append(repo_id)
        return _fake_observed_reader(repo_id)

    def detector_reader():
        detector_reads.append(None)
        return _fake_detector_reader()

    def severity_reader():
        severity_reads.append(None)
        return _fake_severity_reader()

    def overview_reader():
        overview_reads.append(None)
        return _fake_overview_reader()

    app = create_app(
        surface=surface,
        workflow_reader=workflow_reader,
        runs_reader=runs_reader,
        corpus_reader=corpus_reader,
        repositories_reader=repositories_reader,
        binding_reader=binding_reader,
        coverage_reader=coverage_reader,
        observed_reader=observed_reader,
        detector_reader=detector_reader,
        severity_reader=severity_reader,
        overview_reader=overview_reader,
    )
    return _RecordingClient(
        TestClient(app), surface, workflow_reads, runs_reads, corpus_reads, repositories_reads,
        binding_reads, coverage_reads, observed_reads, detector_reads, severity_reads, overview_reads,
    )


def test_no_route_reaches_past_the_read_surface():
    # Every route, driven against a surface that records the method behind each call. The
    # constraint is "reads only", and the only way to hold it is to watch what the routes
    # do -- a route reaching `propose_patch` names no SQL and imports nothing, and clones
    # the customer's repository all the same.
    site = _site("s1")
    change = _change("c1")
    (
        client, surface, workflow_reads, runs_reads, corpus_reads, repositories_reads,
        binding_reads, coverage_reads, observed_reads, detector_reads, severity_reads, overview_reads,
    ) = _recording_client(findings=[_finding("f1", "s1", "c1")], sites=[site], changes=[change])

    assert client.get("/api/overview").status_code == 200
    assert client.get("/api/vendors/stripe").status_code == 200
    assert client.get("/api/vendors/stripe/changes").status_code == 200
    assert client.get("/api/findings/f1").status_code == 200
    assert client.get("/api/workflows/f1").status_code == 200
    assert client.get("/api/runs").status_code == 200
    assert client.get("/api/corpus").status_code == 200
    assert client.get("/api/repositories").status_code == 200
    assert client.get("/api/vendors/stripe/operations/PostCharges/bindings").status_code == 200
    assert client.get("/api/repositories/r1/coverage").status_code == 200
    assert client.get("/api/repositories/r1/observed").status_code == 200
    assert client.get("/api/detectors").status_code == 200

    unexpected = surface.method_names() - _READ_ONLY_METHODS
    assert not unexpected, f"routes reached beyond the read surface: {sorted(unexpected)}"
    assert workflow_reads == ["f1"]
    # Each fleet or graph-view reader was reached by exactly the one request naming its own
    # route -- if any route had reached another's reader instead of (or in addition to) its
    # own, one of these counts would read 0 or 2 rather than 1.
    assert len(runs_reads) == 1, "the runs route must reach its own reader exactly once"
    assert len(corpus_reads) == 1, "the corpus route must reach its own reader exactly once"
    assert len(repositories_reads) == 1, "the repositories route must reach its own reader exactly once"
    assert len(binding_reads) == 1, "the bindings route must reach its own reader exactly once"
    assert len(coverage_reads) == 1, "the coverage route must reach its own reader exactly once"
    assert len(observed_reads) == 1, "the observed route must reach its own reader exactly once"
    assert len(detector_reads) == 1, "the detectors route must reach its own reader exactly once"
    assert len(severity_reads) == 1, "the overview route must reach the severity reader exactly once"
    assert len(overview_reads) == 1, "the overview route must reach the overview reader exactly once"


def test_a_404_route_reaches_past_nothing_either():
    # The unhappy paths get the same treatment: a route that fell back to a heavier call
    # when its cheap read came up empty would pass the test above and fail the constraint.
    client, surface, *_ = _recording_client()

    assert client.get("/api/findings/nope").status_code == 404
    assert client.get("/api/vendors/nobody").status_code == 200

    assert not surface.method_names() - _READ_ONLY_METHODS


# -- pagination is bounded ------------------------------------------------------


def test_limit_above_the_ceiling_is_clamped():
    client, surface, *_ = _recording_client()

    client.get(f"/api/vendors/stripe?limit={_MAX_LIMIT * 1000}")
    client.get(f"/api/vendors/stripe/changes?limit={_MAX_LIMIT * 1000}")

    limits = [kwargs["limit"] for _, kwargs in surface.calls if "limit" in kwargs]
    assert limits == [_MAX_LIMIT, _MAX_LIMIT]


def test_a_limit_under_the_ceiling_passes_through_untouched():
    client, surface, *_ = _recording_client()

    client.get("/api/vendors/stripe?limit=7")

    assert [kwargs["limit"] for _, kwargs in surface.calls if "limit" in kwargs] == [7]


def test_a_negative_limit_is_floored_not_turned_into_a_negative_slice():
    # `rows[offset : offset + limit]` in the surface turns a negative limit into a negative
    # slice stop, which trims from the end instead of returning nothing. The ceiling alone
    # does not stop this -- a floor does.
    client, surface, *_ = _recording_client()

    client.get("/api/vendors/stripe?limit=-1")

    assert [kwargs["limit"] for _, kwargs in surface.calls if "limit" in kwargs] == [1]


def test_a_zero_limit_is_floored_so_the_cursor_terminates():
    # `next_offset` only reaches `None` once a window is non-empty; a limit of zero never
    # consumes a row, so the cursor the console would page with never advances.
    client, surface, *_ = _recording_client()

    client.get("/api/vendors/stripe?limit=0")

    assert [kwargs["limit"] for _, kwargs in surface.calls if "limit" in kwargs] == [1]


# -- the console's mirrored constants -------------------------------------------


def test_the_consoles_default_page_size_matches_the_surfaces():
    # `web/src/api/client.ts` restates `DEFAULT_LIMIT` because the console cannot import
    # Python. Nothing else holds the two together: `web/` has no CI gate, so this is the
    # only place a drift can be noticed.
    source = _web_source("src/api/client.ts")
    match = re.search(r"export const DEFAULT_LIMIT\s*=\s*(\d+)", source)
    assert match is not None, "web/src/api/client.ts no longer declares DEFAULT_LIMIT"
    assert int(match.group(1)) == DEFAULT_LIMIT


def test_the_consoles_proxy_target_matches_the_apis_default_port():
    # `web/vite.config.ts` proxies `/api` to a hardcoded host:port because the dev server
    # cannot import Python. Nothing else holds the two together: a port changed on one side
    # and not the other turns every console request into a proxy error, silently.
    source = _web_source("vite.config.ts")
    match = re.search(r'target:\s*"http://127\.0\.0\.1:(\d+)"', source)
    assert match is not None, "web/vite.config.ts no longer proxies /api to a fixed port"
    assert int(match.group(1)) == DEFAULT_PORT


def test_the_consoles_run_disposition_matches_the_finished_outcomes():
    # `web/src/api/types.ts` restates `_FINISHED` as `RunDisposition` because the console
    # cannot import Python. Nothing else holds the two together: a value added to one side
    # and not the other lets a real outcome reach the console as a type the compiler never
    # checked, which is exactly the run-state Critical this class of test exists to pin.
    source = _web_source("src/api/types.ts")
    match = re.search(r"export type RunDisposition\s*=([^\n]+)", source)
    assert match is not None, "web/src/api/types.ts no longer declares RunDisposition"
    members = set(re.findall(r'"([^"]+)"', match.group(1)))
    assert members == set(_FINISHED)


def test_the_consoles_theme_block_declares_static_so_every_token_reaches_the_build():
    # `web/src/index.css` declares tokens such as `--color-series-*` and `--color-brand`
    # that are read only dynamically -- through `getComputedStyle` in `echart.tsx`, or not
    # yet read by anything -- and never appear as a Tailwind utility class name anywhere in
    # `web/src`. Tailwind v4's on-demand `@theme` block omits a variable that no generated
    # utility references, so a bare `@theme {` silently drops that token's light-mode value
    # from the compiled CSS while its `.dark` counterpart survives untouched, because the
    # `.dark` rule is plain CSS outside `@theme` and is never subject to the same pruning.
    # `static` is Tailwind's documented escape hatch and has to cover the whole block; this
    # checks the source declaration rather than `web/dist`, which is gitignored and absent
    # from a fresh checkout, so a check against it would either skip everywhere or need a
    # build step run first -- fragile in exactly the way this file's other checks are not.
    source = _web_source("src/index.css")
    assert "@theme static {" in source, (
        "index.css declares `@theme` without `static`; any theme token read only "
        "dynamically, or not yet read by anything, silently drops its light-mode value "
        "from the compiled CSS the moment nothing generates a utility class for it"
    )


def _normalized(path: str) -> str:
    """A route path with its one parameterisation collapsed to `{param}`.

    Starlette spells a parameter `{vendor_id}`; `client.ts` spells the same slot
    `${encodeURIComponent(vendorId)}`. Collapsing both to one token is what lets a path from
    either side compare equal to its counterpart.
    """
    path = re.sub(r"\$\{[^}]*\}", "{param}", path)
    return re.sub(r"\{[^}]*\}", "{param}", path)


def test_the_consoles_fetched_paths_match_the_apps_declared_routes():
    # `web/src/api/client.ts` writes the eight paths as string and template literals because
    # the console cannot import Python, and `create_app` declares them by hand at the bottom
    # of this module. Nothing else holds the two lists together: a path renamed on one side
    # and not the other is a 404 in the browser, and `web/` has no test runner and no CI gate
    # that would catch it before a human loads the page.
    app = _build_app(surface=GraphSurface(FakeGraph(), feed_fetched_at=FETCHED))
    app_paths = {_normalized(route.path) for route in app.routes}

    source = _web_source("src/api/client.ts")
    fetched_literals = re.findall(r'[`"](/api[^`"]*)[`"]', source)
    console_paths = {_normalized(literal) for literal in fetched_literals}

    missing_from_console = app_paths - console_paths
    missing_from_app = console_paths - app_paths
    assert not missing_from_console and not missing_from_app, (
        f"routes create_app declares that client.ts never fetches: {sorted(missing_from_console)}; "
        f"paths client.ts fetches that create_app never declares: {sorted(missing_from_app)}"
    )


# -- dev-only reload mode --------------------------------------------------------
#
# uvicorn's `reload=True` re-imports and re-calls a factory in a subprocess rather than
# reusing an app object, so `main()` and the reload path must build the app the same way or
# the two silently diverge. `app_factory` is that one construction route; these tests pin
# the property that would catch a drift (the route table) and the environment contract that
# keeps reload off by default.


def test_app_factory_builds_the_same_routes_as_create_app(monkeypatch):
    # `GraphStore` opens its connection lazily on first use (sync/graph/store.py), so building
    # the app from a DSN that is never queried is safe here -- this test only compares the
    # route table, which is fixed by `create_app` regardless of what the readers do.
    monkeypatch.setenv("SYNC_GRAPH_DSN", "postgresql://sync:sync@localhost:5433/sync")
    monkeypatch.delenv("SYNC_CHECKPOINTER_DSN", raising=False)
    monkeypatch.delenv("SYNC_API_RELOAD", raising=False)

    factory_app = app_factory()
    reference_app = _build_app(surface=GraphSurface(FakeGraph(), feed_fetched_at=FETCHED))

    factory_routes = {(route.path, frozenset(route.methods)) for route in factory_app.routes}
    reference_routes = {(route.path, frozenset(route.methods)) for route in reference_app.routes}
    assert factory_routes == reference_routes


def test_reload_defaults_to_off(monkeypatch):
    monkeypatch.delenv("SYNC_API_RELOAD", raising=False)

    assert _reload_enabled() is False


def test_reload_turns_on_when_the_environment_asks_for_it(monkeypatch):
    monkeypatch.setenv("SYNC_API_RELOAD", "true")

    assert _reload_enabled() is True


def test_reload_unrecognised_value_raises_rather_than_silently_enabling(monkeypatch):
    # sync/obs/log.py established the ruling for an unparseable value at this same kind of
    # boundary: raise, rather than fall back to a default the caller never asked for and
    # would not see. An unrecognised value here must not be treated as truthy just because a
    # production deployment did not intend to set it at all.
    monkeypatch.setenv("SYNC_API_RELOAD", "yes")

    with pytest.raises(ValueError):
        _reload_enabled()
