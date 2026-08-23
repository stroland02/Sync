"""What a tool's silence means, and whether an agent can tell one silence from another.

Five of the six unexecuted statements in `sync.mcp` were declines and only one of them was a
refusal: `resources.read` says `unknown_resource` out loud, and the graph tools say nothing at
all. This file covers the two declines in `_change_for` and pins what an agent observes of each.

Everything here is driven through `serve` with scripted frames. A tool result is what an agent
acts on, and the question this file exists to answer -- can the agent tell "no change" from "I
could not read the change" -- is a question about the frame, not about the return value.

`RowBackedGraph` builds its models the way `GraphStore` does rather than looking them up in a
dict, because the sharp case is not a missing row. It is a row that exists and does not
validate: `VendorChange(**row)` raises `pydantic.ValidationError`, which is a `ValueError`, and
`_change_for` catches `ValueError`.
"""

from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sync.core import CallSite, Finding, VendorChange
from sync.mcp.server import serve
from sync.mcp.tools import GraphSurface

ROWS = json.loads(
    (Path(__file__).parent / "fixtures" / "graph" / "vendor_change_rows.json").read_text(
        encoding="utf-8"
    )
)

INDEXED = datetime(2026, 7, 28, 6, 0, tzinfo=timezone.utc)


def _row(name: str) -> dict:
    """One fixture row in the shape psycopg hands `GraphStore`, timestamp included."""
    row = {key: value for key, value in ROWS[name].items()}
    row["detected_at"] = datetime.fromisoformat(row["detected_at"])
    return row


def _site(site_id: str = "cs1") -> CallSite:
    return CallSite(
        id=site_id, repo_id="r", path="src/pay.ts", line=12, col=4, vendor_id="stripe",
        operation_id="PostCharges", symbol="stripe.charges.create",
        args_keys=["amount"], response_fields_read=["status"],
        sdk_version="18.0.0", content_hash="h", indexed_at=INDEXED,
    )


def _finding(
    finding_id: str, change_id: str | None, detector: str = "vendor-change",
    binding_rung: str = "static",
) -> Finding:
    return Finding(
        id=finding_id, detector=detector, claim="response-field", call_site_id="cs1",
        vendor_change_id=change_id, severity="breaking", rationale="status was removed",
        binding_rung=binding_rung,
    )


class RowBackedGraph:
    """A `GraphReader` that reads rows and builds models exactly as `GraphStore` does.

    `GraphStore.get_vendor_change` is two statements -- `raise KeyError` when the row is absent,
    `VendorChange(**row)` when it is not -- and both are reproduced here. A dict of prebuilt
    models cannot reach the second one, which is where the interesting failure lives.
    """

    def __init__(self, findings: list[Finding], rows: dict[str, dict]) -> None:
        self._findings = findings
        self._rows = rows

    def open_findings(self) -> list[Finding]:
        return list(self._findings)

    def get_call_site(self, call_site_id: str) -> CallSite:
        return _site(call_site_id)

    def get_vendor_change(self, change_id: str) -> VendorChange:
        row = self._rows.get(change_id)
        if row is None:
            raise KeyError(f"no vendor change {change_id}")
        return VendorChange(**row)

    def all_vendor_changes(self, vendor_id: str) -> list[VendorChange]:
        return []


def _call(graph: RowBackedGraph, tool: str, arguments: dict | None = None) -> dict:
    """One `tools/call` over the transport, and the structured payload it returned."""
    frame = {
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": tool, "arguments": arguments or {}},
    }
    stdout = io.StringIO()
    serve(GraphSurface(graph), stdin=io.StringIO(json.dumps(frame) + "\n"), stdout=stdout)
    (response,) = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
    return response


def _rows_of(response: dict) -> list[dict]:
    assert response["result"]["isError"] is False, response
    return response["result"]["structuredContent"]["items"]


# --- the fixture has to keep meaning what it says ------------------------------------


def test_the_off_literal_row_is_one_the_model_refuses_and_the_schema_accepts():
    """The fixture's whole value rests on this, so it is asserted rather than assumed.

    `vendor_change.severity` is `TEXT NOT NULL` with no CHECK constraint and `Severity` is a
    five-member Literal, so this row is one Postgres stores and the model will not build. If
    `Severity` ever widens, this goes red and says the fixture stopped exercising the path it
    was written for -- rather than the path quietly ceasing to be covered.
    """
    with pytest.raises(ValueError):
        VendorChange(**_row("off-literal-severity"))

    assert VendorChange(**_row("readable")).severity == "breaking"


# --- the three silences ---------------------------------------------------------------


def test_a_finding_that_names_no_vendor_change_is_still_a_row():
    """`tools.py:291`. Two of the five detectors read telemetry and raise findings with no
    vendor change at all, which `Finding`'s docstring records. Such a finding is a real answer
    and must not be dropped from `sync_whats_at_risk` for lacking a field it never had.
    """
    graph = RowBackedGraph([_finding("f-telemetry", None, detector="observed-drift")], {})

    (row,) = _rows_of(_call(graph, "sync_whats_at_risk"))

    assert row["finding_id"] == "f-telemetry"
    assert row["change_kind"] is None


def test_a_vendor_change_the_graph_cannot_find_leaves_the_finding_standing():
    """`tools.py:294-295`, entered by `KeyError` -- the decline at the reader's boundary.

    One unreadable change must not deny an agent the finding, which is the argument `_site_for`
    makes for the same catch. What the agent is not told is that anything went wrong.
    """
    graph = RowBackedGraph([_finding("f-dangling", "vc-vanished")], {})

    (row,) = _rows_of(_call(graph, "sync_whats_at_risk"))

    assert row["finding_id"] == "f-dangling"
    assert row["change_kind"] is None


def test_a_vendor_change_row_that_does_not_validate_says_it_is_unreadable():
    """The decline *inside* the reader, now named rather than silent.

    The row is present, `severity` is a value the model does not accept, and
    `VendorChange(**row)` raises `pydantic.ValidationError` -- a `ValueError`. It is still not a
    tool error and `change_kind` is still null, because there is no kind to report. What changed
    is that the row now says WHY: a stored-and-unreadable change is a defect somebody can act on,
    and it used to arrive as the same silence as a finding with no change at all.

    The offending value stays out of the payload. It is untrusted content from a row that failed
    validation, and echoing it would put it in front of an agent as though it were a kind.
    """
    graph = RowBackedGraph(
        [_finding("f-unparseable", "vc-off-literal-severity")],
        {"vc-off-literal-severity": _row("off-literal-severity")},
    )

    response = _call(graph, "sync_whats_at_risk")
    (row,) = _rows_of(response)

    assert row["finding_id"] == "f-unparseable"
    assert row["change_kind"] is None
    assert "cannot read it back" in row["change_absent_because"]
    assert "catastrophic" not in json.dumps(response)


def test_the_three_silences_are_three_answers_to_an_agent():
    """The finding this file existed to record, and its repair.

    A finding with no vendor change, a finding whose change the graph lost, and a finding whose
    change the graph holds and cannot parse used to produce the SAME row apart from its
    identifier -- so an agent had no field to branch on, and the envelope added none, because
    `binding_source` describes how a binding was established and not whether reading it
    succeeded.

    They are three different facts and only two are actionable: a lost row and an unreadable one
    are defects, and no-change-recorded is an answer. `change_absent_because` is the field to
    branch on, and this asserts the three differ rather than asserting their exact wording --
    the distinction is the contract, the sentences are not.
    """
    absent = RowBackedGraph([_finding("f", None)], {})
    missing = RowBackedGraph([_finding("f", "vc-vanished")], {})
    unparseable = RowBackedGraph(
        [_finding("f", "vc-off-literal-severity")],
        {"vc-off-literal-severity": _row("off-literal-severity")},
    )

    reasons = [
        _rows_of(_call(graph, "sync_whats_at_risk"))[0]["change_absent_because"]
        for graph in (absent, missing, unparseable)
    ]

    assert all(reason for reason in reasons), reasons
    assert len(set(reasons)) == 3, reasons


def test_an_unreadable_change_is_not_reported_as_a_tool_error():
    """The other half of the same fact. `_call` turns any escaping exception into a result
    carrying `isError`, so a narrower catch would have a channel to speak on -- and today
    nothing travels down it. Every one of the three answers is a success frame.
    """
    for graph in (
        RowBackedGraph([_finding("f", None)], {}),
        RowBackedGraph([_finding("f", "vc-vanished")], {}),
        RowBackedGraph(
            [_finding("f", "vc-off-literal-severity")],
            {"vc-off-literal-severity": _row("off-literal-severity")},
        ),
    ):
        result = _call(graph, "sync_whats_at_risk")["result"]
        assert result["isError"] is False
        assert "error" not in result


# --- a second thing the surface flattened, and no longer does -------------------------


@pytest.mark.parametrize("rung", ["static", "resolved", "observed", "unresolved"])
def test_the_rung_is_the_one_flattening_in_this_file_that_was_repaired(rung: str):
    """The counterpart to the three silences above, and the contrast is the point.

    This test pinned the loss first: `binding_rung` had become an enforced column and the surface
    still answered `binding_source: "static"` for all four rungs, so a claim resting on a
    span-to-operation correlation reached an agent as a syntactic match. M3-W109 repaired it, and
    that turned this test red on purpose, which is what it was written to do.

    What separates it from the declines this file exists to record is that the rung had a value to
    carry. "No change" and "the change would not parse" are two facts with one shape and no field
    to tell them apart, so repairing them means inventing a channel. The rung was already in the
    row; only the response dropped it. `tests/test_mcp_provenance.py` holds the full behaviour and
    `docs/superpowers/reports/2026-07-30-provenance-on-the-tool-surface.md` the argument.
    """
    graph = RowBackedGraph(
        [_finding("f", "vc-readable", detector="observed-drift", binding_rung=rung)],
        {"vc-readable": _row("readable")},
    )

    payload = _call(graph, "sync_whats_at_risk")["result"]["structuredContent"]

    assert payload["items"][0]["binding_source"] == rung
    assert payload["binding_source"] == rung


# --- the same swallow, on the evidence a reviewer reads --------------------------------


def test_evidence_reports_an_empty_spec_diff_for_a_change_it_could_not_read():
    """`_evidence_for` calls `_change_for` too, and its `spec_diff` is the raw vendor record a
    reviewer judges the patch by. An unreadable change makes that `{}`, which reads as "the
    spec diff was empty" rather than "the spec diff could not be read" -- the same conflation
    one layer further in, where the consumer is a human rather than an agent.
    """
    graph = RowBackedGraph(
        [_finding("f-unparseable", "vc-off-literal-severity")],
        {"vc-off-literal-severity": _row("off-literal-severity")},
    )

    payload = _call(graph, "sync_propose_patch", {"finding_id": "f-unparseable"})["result"][
        "structuredContent"
    ]

    assert payload["outcome"] == "unavailable"
    assert payload["evidence"]["spec_diff"] == {}
    assert payload["evidence"]["call_sites"] == ["src/pay.ts:12"]


def test_a_readable_change_puts_the_raw_vendor_record_in_the_evidence():
    """The control for the test above, and what makes its `{}` a loss rather than a shape.

    `CLAUDE.md` requires the raw vendor record be kept, and this is where it is spent. The two
    tests together say the difference between a change that read and one that did not is
    visible in the evidence and invisible in the row.
    """
    graph = RowBackedGraph(
        [_finding("f-ok", "vc-readable")], {"vc-readable": _row("readable")}
    )

    payload = _call(graph, "sync_propose_patch", {"finding_id": "f-ok"})["result"][
        "structuredContent"
    ]

    assert payload["evidence"]["spec_diff"] == ROWS["readable"]["raw"]
