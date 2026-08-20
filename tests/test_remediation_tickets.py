"""The ticket: one remediation request, converging rather than queueing duplicates.

The grain is one row per request -- a finding retried after an abandoned run is a new ticket --
and the partial unique index is the idempotence rule: at most one ticket per finding that is
not yet done, so an operator's double-click and the watch tick racing an operator land on one
row. `claim_next_ticket` moves a row out of 'requested' atomically so two runners cannot both
execute one request.
"""

from __future__ import annotations

import os

import pytest

from sync.core.models import CallSite, Finding, VendorChange
from sync.graph.store import GraphStore

DSN = os.environ.get('SYNC_DSN', 'postgresql://sync:sync@localhost:5433/sync')


@pytest.fixture()
def store() -> GraphStore:
    s = GraphStore(DSN)
    s.apply_schema()
    s.truncate_all()
    return s


def test_a_double_click_converges_on_the_open_ticket(store: GraphStore) -> None:
    first = store.create_ticket("f-1", "acme", source="operator")
    second = store.create_ticket("f-1", "acme", source="operator")

    assert first["id"] == second["id"]
    assert [t["id"] for t in store.tickets("acme")] == [first["id"]]


def test_the_lanes_are_recorded_and_a_wrong_one_is_refused(store: GraphStore) -> None:
    store.create_ticket("f-1", "acme", source="operator")
    store.create_ticket("f-2", "acme", source="watch")

    assert [t["finding_id"] for t in store.tickets("acme", source="watch")] == ["f-2"]
    with pytest.raises(ValueError, match="ticket source"):
        store.create_ticket("f-3", "acme", source="gremlin")


def test_a_settled_finding_can_be_ticketed_again(store: GraphStore) -> None:
    first = store.create_ticket("f-1", "acme", source="operator")
    claimed = store.claim_next_ticket("acme", thread_id="t-1")
    assert claimed is not None and claimed["id"] == first["id"]
    store.close_ticket(first["id"], outcome="abandoned", detail="tier refused")

    second = store.create_ticket("f-1", "acme", source="operator")

    assert second["id"] != first["id"]
    newest = store.ticket_for_finding("f-1")
    assert newest is not None and newest["status"] == "requested"


def test_claiming_moves_exactly_one_ticket_and_stamps_the_thread(store: GraphStore) -> None:
    store.create_ticket("f-1", "acme", source="operator")
    store.create_ticket("f-2", "acme", source="operator")

    claimed = store.claim_next_ticket("acme", thread_id="thread-9")

    assert claimed is not None
    assert claimed["finding_id"] == "f-1"
    assert claimed["status"] == "picked_up"
    assert claimed["thread_id"] == "thread-9"
    remaining = [t for t in store.tickets("acme") if t["status"] == "requested"]
    assert [t["finding_id"] for t in remaining] == ["f-2"]


def test_an_empty_queue_claims_nothing(store: GraphStore) -> None:
    assert store.claim_next_ticket("acme", thread_id="t-1") is None


def test_closing_records_the_runs_own_outcome(store: GraphStore) -> None:
    ticket = store.create_ticket("f-1", "acme", source="watch")
    store.claim_next_ticket("acme", thread_id="t-1")
    store.close_ticket(ticket["id"], outcome="opened", detail="https://github.com/x/y/pull/1")

    settled = store.ticket_for_finding("f-1")
    assert settled is not None
    assert settled["status"] == "done"
    assert settled["outcome"] == "opened"
    assert settled["detail"] == "https://github.com/x/y/pull/1"
    assert settled["done_at"] is not None


def test_a_second_lane_converges_without_stealing_the_ticket(store: GraphStore) -> None:
    # The watch tick racing an operator lands on the operator's open ticket -- and the ticket
    # keeps the lane that asked first, because the Detectors page splits by lane and a row that
    # silently switched sides would move a request between the manual and automatic stories.
    first = store.create_ticket("f-1", "acme", source="operator")
    second = store.create_ticket("f-1", "acme", source="watch")

    assert second["id"] == first["id"]
    assert second["source"] == "operator"


def test_a_stored_finding_becomes_the_model_the_graph_takes(store: GraphStore) -> None:
    # The executor's read: a ticket names a finding by id across process boundaries, so the
    # row has to come back as the same `Finding` the scan wrote, rung and provenance intact.
    site_id = store.upsert_call_site(
        CallSite(
            repo_id="acme", path="src/billing.ts", line=12, col=4, vendor_id="stripe",
            operation_id="PostCharges", symbol="stripe.charges.create", args_keys=["amount"],
            response_fields_read=["status"], sdk_version="18.0.0", content_hash="h-1",
        )
    )
    change_id = store.upsert_vendor_change(
        VendorChange(
            vendor_id="stripe", from_version="v2300", to_version="v2345",
            kind="response-property-removed", operation_id="PostCharges",
            path_ptr="/paths/x", severity="breaking", source="oasdiff",
        )
    )
    written = Finding(
        detector="vendor_change", claim="response-field", call_site_id=site_id,
        vendor_change_id=change_id, severity="breaking", rationale="status removed",
        binding_rung="static",
    )
    finding_id = store.insert_finding(written)

    loaded = store.get_finding(finding_id)

    assert loaded is not None
    assert loaded.id == finding_id
    assert loaded.detector == written.detector
    assert loaded.claim == written.claim
    assert loaded.call_site_id == site_id
    assert loaded.vendor_change_id == change_id
    assert loaded.severity == written.severity
    assert loaded.rationale == written.rationale
    assert loaded.binding_rung == "static"


def test_a_retracted_finding_loads_as_none(store: GraphStore) -> None:
    assert store.get_finding("no-such-finding") is None


def test_the_real_thread_replaces_the_provisional_one(store: GraphStore) -> None:
    # The claim happens before the finding is loaded, so it stamps a provisional thread; the
    # executor corrects it once the real coordinates exist, keeping the console's join intact.
    store.create_ticket("f-1", "acme", source="operator")
    claimed = store.claim_next_ticket("acme", thread_id="claimed")
    assert claimed is not None

    store.stamp_ticket_thread(claimed["id"], "f-1:abc123:1")

    settled = store.ticket_for_finding("f-1")
    assert settled is not None
    assert settled["thread_id"] == "f-1:abc123:1"
