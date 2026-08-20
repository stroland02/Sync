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
