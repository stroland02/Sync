"""Which rung a tool response claims, and whether it is the rung the graph recorded.

`CLAUDE.md`: every binding carries the rung it came from, and so does every artifact derived
from it. A tool response is one. `GraphStore.insert_finding` refuses a finding whose rung is
`unattributed`, so every finding written since that landed names a rung a binder actually
produced -- and until this file existed the surface answered `binding_source: "static"` for all
of them.

`docs/superpowers/reports/2026-07-30-mcp-tool-surface-declines.md` found that and pinned it
across four rungs without repairing it; `2026-07-30-provenance-on-the-tool-surface.md` carries
the repair and the shape argument. The short form of the shape: `sync_whats_at_risk` returns a
page, two findings on one page can rest on different binders, and no single envelope value is
right for both -- so the rung is a field on the row, and the envelope speaks only when the whole
answer agrees.

Driven through `serve` with scripted frames rather than by calling the surface, because a wrong
provenance is something an agent acts on and what an agent acts on is the frame.
"""

from __future__ import annotations

import io
import json
import os
from datetime import datetime, timezone

import pytest

from sync.core import CallSite, Finding, VendorChange
from sync.graph.store import GraphStore
from sync.mcp.server import serve
from sync.mcp.tools import GraphSurface

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")

INDEXED = datetime(2026, 7, 28, 6, 0, tzinfo=timezone.utc)
FETCHED = datetime(2026, 7, 28, 7, 0, tzinfo=timezone.utc)

STORED_RUNGS = ("static", "resolved", "observed", "unresolved", "unattributed")
"""Every value a tool can read out of `finding.binding_rung`, which is `FindingRung` exactly.

`BindingRung`'s four, which `insert_finding` accepts, plus `unattributed`, which it refuses on
the way in and which rows written before the column existed still carry on the way out.
"""

ENVELOPE_KEYS = {"indexed_at", "feed_fetched_at", "binding_source", "context_savings"}
PAGE_KEYS = ENVELOPE_KEYS | {"items", "total", "next_offset"}
RISK_ROW_KEYS = {
    "file", "line", "symbol", "operation", "vendor", "change_kind", "severity", "finding_id",
    "binding_source",
}
EXPLAIN_KEYS = ENVELOPE_KEYS | {
    "symbol", "operation", "vendor", "args_keys", "response_fields_read", "sdk_version",
    "known_changes",
}


def _site(site_id: str | None = "cs1", path: str = "src/pay.ts", line: int = 12) -> CallSite:
    return CallSite(
        id=site_id, repo_id="r", path=path, line=line, col=4, vendor_id="stripe",
        operation_id="PostCharges", symbol="stripe.charges.create",
        args_keys=["amount"], response_fields_read=["status"],
        sdk_version="18.0.0", content_hash="h", indexed_at=INDEXED,
    )


def _change(change_id: str = "vc1") -> VendorChange:
    return VendorChange(
        id=change_id, vendor_id="stripe", from_version="2026-05-01", to_version="2026-11-01",
        kind="response-property-removed", operation_id="PostCharges", path_ptr="/v1/charges",
        severity="breaking", source="oasdiff", raw={"text": "status removed"},
    )


def _finding(
    finding_id: str, rung: str, site_id: str = "cs1", detector: str = "vendor-change"
) -> Finding:
    return Finding(
        id=finding_id, detector=detector, claim="response-field", call_site_id=site_id,
        vendor_change_id="vc1", severity="breaking", rationale="status was removed",
        binding_rung=rung,
    )


class FakeGraph:
    """The narrow read surface the tools need, which `GraphStore` already satisfies."""

    def __init__(self, findings=(), sites=(_site(),), changes=(_change(),)) -> None:
        self._findings = list(findings)
        self._sites = {site.id: site for site in sites}
        self._changes = {change.id: change for change in changes}

    def open_findings(self) -> list[Finding]:
        return list(self._findings)

    def get_call_site(self, call_site_id: str) -> CallSite:
        return self._sites[call_site_id]

    def get_vendor_change(self, change_id: str) -> VendorChange:
        return self._changes[change_id]

    def all_vendor_changes(self, vendor_id: str) -> list[VendorChange]:
        return [c for c in self._changes.values() if c.vendor_id == vendor_id]


def _payload(graph, tool: str, arguments: dict | None = None) -> dict:
    """One `tools/call` over the transport, and the structured payload it answered with."""
    frame = {
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": tool, "arguments": arguments or {}},
    }
    stdout = io.StringIO()
    serve(
        GraphSurface(graph, feed_fetched_at=FETCHED),
        stdin=io.StringIO(json.dumps(frame) + "\n"),
        stdout=stdout,
    )
    (response,) = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
    assert response["result"]["isError"] is False, response
    return response["result"]["structuredContent"]


# --- a finding's provenance is the rung it was stored with -----------------------------


@pytest.mark.parametrize("rung", STORED_RUNGS)
def test_a_findings_surfaced_provenance_is_the_rung_it_was_stored_with(rung: str):
    """The repair, one test per value the column can hold.

    Two of the five detectors raise findings from telemetry rather than from a static read, so
    `static` is a live wrong answer for them and not merely a contract gap. Nothing is mapped or
    renamed on the way out: the row reports the stored value, because a rung the surface invented
    would be a binding claim nobody made.
    """
    graph = FakeGraph([_finding("f", rung)])

    (row,) = _payload(graph, "sync_whats_at_risk")["items"]

    assert row["binding_source"] == rung


@pytest.mark.parametrize("rung", STORED_RUNGS)
def test_the_envelope_carries_the_rung_when_every_finding_in_the_answer_agrees(rung: str):
    """A homogeneous answer has one honest envelope value, so it says it.

    The spec requires `binding_source` on every response and an agent that reads only the
    envelope is the common case. Withholding the value when it is unambiguous would push every
    caller down to the rows for no gain.
    """
    graph = FakeGraph([_finding("f1", rung), _finding("f2", rung)])

    assert _payload(graph, "sync_whats_at_risk")["binding_source"] == rung


def test_a_page_holding_two_rungs_reports_each_row_and_declines_the_envelope():
    """The test the shape decision rests on.

    One page, one finding from a static read and one from watched traffic -- the ordinary shape
    of a repository with telemetry configured. No single envelope value is true of both, so the
    envelope declines and each row answers for itself. Absent provenance is recoverable; wrong
    provenance is what an agent weighs a patch by.
    """
    graph = FakeGraph(
        [_finding("f-static", "static"), _finding("f-observed", "observed", detector="status-rate")]
    )

    payload = _payload(graph, "sync_whats_at_risk")

    assert [row["binding_source"] for row in payload["items"]] == ["static", "observed"]
    assert payload["binding_source"] is None


def test_an_empty_page_claims_no_binding_source():
    """No finding, no binding, nothing to be the source of. `static` here would describe a read
    that never happened."""
    payload = _payload(FakeGraph([]), "sync_whats_at_risk")

    assert payload["items"] == []
    assert payload["binding_source"] is None


def test_the_envelope_speaks_for_the_answer_and_not_for_the_window():
    """A rung the envelope reports has to be true of rows the response does not carry too.

    `indexed_at` is already computed over every matching finding rather than over the page, and
    the envelope's second provenance field follows it: page one of a mixed result declines even
    though the rows it happens to carry agree. The direction matters -- narrowing to the window
    would make the value depend on where an agent happened to page.
    """
    graph = FakeGraph(
        [_finding("f1", "static"), _finding("f2", "static"), _finding("f3", "observed")]
    )

    first = _payload(graph, "sync_whats_at_risk", {"limit": 2})

    assert [row["binding_source"] for row in first["items"]] == ["static", "static"]
    assert first["binding_source"] is None


# --- the other three tools -------------------------------------------------------------


@pytest.mark.parametrize("rung", STORED_RUNGS)
def test_explain_call_site_reports_the_rung_of_the_finding_that_named_the_line(rung: str):
    """`binding_source` is in this tool's own field list in the spec, and the call site itself
    carries no rung -- `CallSite` has no such column. The findings that name the line do."""
    graph = FakeGraph([_finding("f", rung)])

    payload = _payload(graph, "sync_explain_call_site", {"file": "src/pay.ts", "line": 12})

    assert payload["binding_source"] == rung


def test_explain_call_site_declines_when_two_findings_disagree_about_one_line():
    """Two detectors on one call site is ordinary -- a vendor change and a status-rate claim --
    and they rest on different binders. So this tool reads every finding that names the line
    rather than stopping at the first one, because the rung is a property of all of them and not
    of whichever the graph returned first."""
    graph = FakeGraph(
        [_finding("f-static", "static"), _finding("f-observed", "observed", detector="status-rate")]
    )

    payload = _payload(graph, "sync_explain_call_site", {"file": "src/pay.ts", "line": 12})

    assert payload["symbol"] == "stripe.charges.create"
    assert payload["binding_source"] is None


def test_whats_changed_reports_no_binding_source_because_it_reports_no_binding():
    """The field is present, and null, for the same reason `indexed_at` is.

    This tool answers from vendor changes and never reads a call site or a finding, so its
    payload holds no binding at all. `static` here claimed a mapping had been established for an
    answer in which no mapping appears.
    """
    payload = _payload(FakeGraph([_finding("f", "static")]), "sync_whats_changed",
                       {"vendor": "stripe"})

    assert payload["items"]
    assert "binding_source" in payload
    assert payload["binding_source"] is None


@pytest.mark.parametrize("rung", STORED_RUNGS)
def test_propose_patch_reports_the_rung_of_the_one_finding_it_answers_about(rung: str):
    """Where the envelope is the right place for the field, which is what makes the page the
    wrong one. This tool answers about exactly one finding, so the response rests on exactly one
    binding and the envelope can name it."""
    graph = FakeGraph([_finding("f", rung)])

    payload = _payload(graph, "sync_propose_patch", {"finding_id": "f"})

    assert payload["outcome"] == "unavailable"
    assert payload["binding_source"] == rung


def test_no_response_invents_a_rung_the_graph_did_not_record():
    """The property behind every test above: the published value is drawn from what the column
    can hold, or is absent. A fourth rung name minted on the surface would be a rung no binder
    emits and no query can attribute a false positive to."""
    graph = FakeGraph([_finding("f1", "observed"), _finding("f2", "unresolved")])
    allowed = {*STORED_RUNGS, None}

    page = _payload(graph, "sync_whats_at_risk")

    assert page["binding_source"] in allowed
    assert {row["binding_source"] for row in page["items"]} <= allowed


# --- history, read through the store that refuses to write it --------------------------


@pytest.fixture()
def store() -> GraphStore:
    s = GraphStore(DSN)
    s.apply_schema()
    s.truncate_all()
    return s


def test_a_row_written_before_the_column_existed_surfaces_as_unattributed(store: GraphStore):
    """`insert_finding` refuses `unattributed`, and rows that predate the column carry it.

    Reproduced the way history produced it: the row is written normally and then reset to the
    column's own `DEFAULT`, which is the value every pre-column row holds. `unattributed` is not
    a fourth rung and nothing here treats it as one -- it is published verbatim because it is a
    fact the graph records, and folding it into the same `null` that means "the rows disagree"
    would flatten two different states into one answer.
    """
    site_id = store.upsert_call_site(_site(site_id=None))
    finding_id = store.insert_finding(
        Finding(
            detector="vendor-change", claim="response-field", call_site_id=site_id,
            severity="breaking", rationale="status was removed", binding_rung="static",
        )
    )
    store._connect().execute(
        "UPDATE finding SET binding_rung = DEFAULT WHERE id = %s", (finding_id,)
    )

    (readable,) = store.open_findings()
    assert readable.binding_rung == "unattributed"

    (row,) = _payload(store, "sync_whats_at_risk")["items"]
    assert row["binding_source"] == "unattributed"


# --- the shape, because the freeze cannot see it ---------------------------------------


def test_the_response_shape_is_pinned_here_because_the_golden_file_cannot_see_it():
    """`tests/golden/tool_schemas.json` stores `name`, `description` and `inputSchema`, and
    there is no `outputSchema` -- so the published freeze covers the request half only. Adding
    `binding_source` to a row left that file byte-identical, and
    `test_every_response_carries_the_provenance_fields` asserts a subset, so it passed too. The
    one artifact that exists to make a contract change deliberate could not have caught this
    one, which is why the response shape is asserted by exact key set here.
    """
    graph = FakeGraph([_finding("f", "static")])

    page = _payload(graph, "sync_whats_at_risk")
    explain = _payload(graph, "sync_explain_call_site", {"file": "src/pay.ts", "line": 12})
    changed = _payload(graph, "sync_whats_changed", {"vendor": "stripe"})

    assert set(page) == PAGE_KEYS
    assert set(page["items"][0]) == RISK_ROW_KEYS
    assert set(explain) == EXPLAIN_KEYS
    assert set(changed) == PAGE_KEYS
    assert set(changed["items"][0]) == {
        "operation", "change_kind", "path_ptr", "severity", "from_version", "to_version",
        "published_at",
    }
