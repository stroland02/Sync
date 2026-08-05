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

from sync.api.__main__ import DEFAULT_PORT
from sync.api.app import _MAX_LIMIT, _SCAN_LIMIT, create_app
from sync.core import CallSite, Finding, VendorChange
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


def _build_app(
    *,
    surface: GraphSurface,
    workflow_reader=lambda finding_id: None,
    runs_reader=_fake_runs_reader,
    corpus_reader=_fake_corpus_reader,
    repositories_reader=_fake_repositories_reader,
) -> Starlette:
    """`create_app` with every reader defaulted to a fake, so a test naming one override is
    not forced to restate the other four.

    `create_app` keeps all five readers required -- a deployment that forgets one should fail
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
    )


def _client(**graph_kw) -> TestClient:
    graph = FakeGraph(**graph_kw)
    surface = GraphSurface(graph, feed_fetched_at=FETCHED)
    app = _build_app(surface=surface)
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


def test_overview_carries_the_envelopes_context_savings_not_a_hardcoded_number():
    # `overview` composes its payload by hand from `whats_at_risk`'s page; the page it reads
    # already carries a real `context_savings` from the envelope, and the route must forward
    # that value rather than drop it or invent one.
    site = _site("s1")
    change = _change("c1")
    findings = [_finding("f1", "s1", "c1")]
    surface = GraphSurface(FakeGraph(findings=findings, sites=[site], changes=[change]), feed_fetched_at=FETCHED)
    client = TestClient(_build_app(surface=surface))
    expected = surface.whats_at_risk(limit=_SCAN_LIMIT, offset=0)["context_savings"]

    body = client.get("/api/overview").json()

    assert body["context_savings"] == expected


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


def _recording_client(**graph_kw) -> _RecordingClient:
    surface = RecordingSurface(GraphSurface(FakeGraph(**graph_kw), feed_fetched_at=FETCHED))
    workflow_reads: list[str] = []
    runs_reads: list[dict[str, int]] = []
    corpus_reads: list[None] = []
    repositories_reads: list[None] = []

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

    app = create_app(
        surface=surface,
        workflow_reader=workflow_reader,
        runs_reader=runs_reader,
        corpus_reader=corpus_reader,
        repositories_reader=repositories_reader,
    )
    return _RecordingClient(
        TestClient(app), surface, workflow_reads, runs_reads, corpus_reads, repositories_reads
    )


def test_no_route_reaches_past_the_read_surface():
    # Every route, driven against a surface that records the method behind each call. The
    # constraint is "reads only", and the only way to hold it is to watch what the routes
    # do -- a route reaching `propose_patch` names no SQL and imports nothing, and clones
    # the customer's repository all the same.
    site = _site("s1")
    change = _change("c1")
    client, surface, workflow_reads, runs_reads, corpus_reads, repositories_reads = _recording_client(
        findings=[_finding("f1", "s1", "c1")], sites=[site], changes=[change]
    )

    assert client.get("/api/overview").status_code == 200
    assert client.get("/api/vendors/stripe").status_code == 200
    assert client.get("/api/vendors/stripe/changes").status_code == 200
    assert client.get("/api/findings/f1").status_code == 200
    assert client.get("/api/workflows/f1").status_code == 200
    assert client.get("/api/runs").status_code == 200
    assert client.get("/api/corpus").status_code == 200
    assert client.get("/api/repositories").status_code == 200

    unexpected = surface.method_names() - _READ_ONLY_METHODS
    assert not unexpected, f"routes reached beyond the read surface: {sorted(unexpected)}"
    assert workflow_reads == ["f1"]
    # Each fleet reader was reached by exactly the one request naming its own route -- if any
    # route had reached another's reader instead of (or in addition to) its own, one of these
    # counts would read 0 or 2 rather than 1.
    assert len(runs_reads) == 1, "the runs route must reach its own reader exactly once"
    assert len(corpus_reads) == 1, "the corpus route must reach its own reader exactly once"
    assert len(repositories_reads) == 1, "the repositories route must reach its own reader exactly once"


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
