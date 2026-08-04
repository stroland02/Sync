"""The HTTP transport for the operator console: thin Starlette routes over `GraphSurface`.

Every route is one call into the surface and one JSON return. The rules under test are the
plan's, and each exists because breaking it costs the console its read-only guarantee: the
route returns the surface's payload unaltered, pagination parameters pass through, an unknown
identifier is a 404 with a JSON body, and no route mutates -- proved by grepping the package
for INSERT/UPDATE/DELETE and for `sync.remediate` imports rather than by asking the reader to
trust the code.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import pytest
from starlette.testclient import TestClient

from sync.api import app as app_module
from sync.api.app import create_app
from sync.core import CallSite, Finding, VendorChange
from sync.mcp.tools import GraphSurface

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


def _client(**graph_kw) -> TestClient:
    graph = FakeGraph(**graph_kw)
    surface = GraphSurface(graph, feed_fetched_at=FETCHED)
    app = create_app(surface=surface, workflow_reader=lambda finding_id: None)
    return TestClient(app)


# -- overview -------------------------------------------------------------------


def test_overview_returns_vendors_and_counts_from_the_surface():
    site_a = _site("s1", vendor="stripe")
    site_b = _site("s2", vendor="stripe", path="src/other.ts", line=44)
    site_c = _site("s3", vendor="shopify", op="GetOrders")
    change_stripe = _change("c1", vendor="stripe")
    change_shopify = _change("c2", vendor="shopify", op="GetOrders")
    findings = [
        _finding("f1", "s1", "c1"),
        _finding("f2", "s2", "c1"),
        _finding("f3", "s3", "c2"),
    ]
    client = _client(
        findings=findings,
        sites=[site_a, site_b, site_c],
        changes=[change_stripe, change_shopify],
    )

    response = client.get("/api/overview")

    assert response.status_code == 200
    body = response.json()
    assert body["total_findings"] == 3
    vendors = {v["vendor_id"]: v for v in body["vendors"]}
    assert vendors["stripe"]["open_finding_count"] == 2
    assert vendors["shopify"]["open_finding_count"] == 1


def test_overview_carries_the_surfaces_envelope_fields_unaltered():
    site = _site("s1")
    change = _change("c1")
    client = _client(
        findings=[_finding("f1", "s1", "c1")],
        sites=[site],
        changes=[change],
    )

    body = client.get("/api/overview").json()

    assert body["feed_fetched_at"] == FETCHED.isoformat()


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


def test_finding_route_answers_for_a_finding_past_the_overview_scan_window():
    """The failure this route used to hide: it found a finding by paging `whats_at_risk` and
    stopping at `_SCAN_LIMIT`, so a graph holding more open findings than that answered 404 for
    a finding that exists -- silently, because 404 is also the honest answer for a closed one.

    The condition is the finding's position past the window, not the size of the graph, so it is
    built by shrinking the window rather than by inventing ten thousand rows.

    Read cold, the patch looks like live coverage of a ceiling on this route. It is not: it is
    what made the old code answer 404 here, and against the route as it stands it does nothing,
    because the route no longer reads `_SCAN_LIMIT` at all. That absence is what the test below
    asserts; this one is the historical failure kept executable.
    """
    change = _change("c1")
    sites = [_site(f"s{i}", path=f"src/a{i}.ts", line=i + 1) for i in range(3)]
    findings = [_finding(f"f{i}", f"s{i}", "c1") for i in range(3)]
    client = _client(findings=findings, sites=sites, changes=[change])

    with mock.patch.object(app_module, "_SCAN_LIMIT", 2):
        response = client.get("/api/findings/f2")

    assert response.status_code == 200
    assert response.json()["symbol"] == "stripe.charges.create"


def test_finding_route_does_not_page_whats_at_risk_to_find_one_finding():
    """A by-id question asked as a page read is the defect above waiting to come back, so the
    absence of the page read is asserted rather than left to the row count."""
    calls: list[str] = []

    class RecordingSurface(GraphSurface):
        def whats_at_risk(self, *args, **kwargs):
            calls.append("whats_at_risk")
            return super().whats_at_risk(*args, **kwargs)

    graph = FakeGraph(
        findings=[_finding("f1", "s1", "c1")], sites=[_site("s1")], changes=[_change("c1")]
    )
    surface = RecordingSurface(graph, feed_fetched_at=FETCHED)
    client = TestClient(create_app(surface=surface, workflow_reader=lambda finding_id: None))

    assert client.get("/api/findings/f1").status_code == 200
    assert calls == []


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
    app = create_app(surface=surface, workflow_reader=lambda finding_id: payload)
    client = TestClient(app)

    response = client.get("/api/workflows/f1")

    assert response.status_code == 200
    assert response.json() == payload


def test_workflow_route_returns_404_when_reader_yields_none():
    surface = GraphSurface(FakeGraph(), feed_fetched_at=FETCHED)
    app = create_app(surface=surface, workflow_reader=lambda finding_id: None)
    client = TestClient(app)

    response = client.get("/api/workflows/unknown")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert "error" in body


# -- the read-only constraint, as a test rather than a promise ------------------


def _api_package_files() -> list[Path]:
    package = Path(__file__).resolve().parent.parent / "src" / "sync" / "api"
    assert package.is_dir(), f"expected api package at {package}"
    return sorted(package.rglob("*.py"))


def test_api_package_holds_no_write_sql():
    # An enforced constraint rather than a docstring: the transport is read-only, so a route
    # that emitted a mutation would break the console's contract. Grepping the package for
    # verbs a mutation would use catches an accidental one before it ships.
    forbidden = re.compile(r"\b(INSERT|UPDATE|DELETE)\b", re.IGNORECASE)
    for path in _api_package_files():
        text = path.read_text(encoding="utf-8")
        # `updated` and similar English words are allowed; the regex is on the SQL verb, not
        # on the substring.
        matches = [m.group(0) for m in forbidden.finditer(text)]
        assert not matches, f"{path} names a mutation verb: {matches}"


def test_api_package_does_not_import_sync_remediate():
    forbidden = re.compile(r"\bfrom\s+sync\.remediate\b|\bimport\s+sync\.remediate\b")
    for path in _api_package_files():
        text = path.read_text(encoding="utf-8")
        assert not forbidden.search(text), f"{path} imports sync.remediate"
