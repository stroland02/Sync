"""Whether the codebase's calls are known to be safe, known to be at risk, or unexamined.

**Owner question, 2026-08-19: "why do severity tables not have a safe category, and why do we not
show safe APIs?"** The answer to the first half is that severity is the *vendor's* published label
on a change -- `oasdiff` emits no "safe", and a finding exists only where a call site binds to a
change, so those tables are lists of problems by construction. Inventing a `safe` severity would
put a judgement about this codebase inside a column that otherwise carries only the vendor's words.

The second half is a real gap and this is the answer to it. The console showed what was broken and
nothing else, so an operation this codebase calls and that is *fine* appeared nowhere -- and a
reader could not tell **"we checked this and nothing binds"** from **"we never checked this"**.
That is exactly the distinction `web/CLAUDE.md` says matters most, violated by omission.

**What makes `clean` honest is `intake_attempt`.** Its own grain comment says it exists to keep
*never-asked* apart from *nothing-new*, which is precisely what this needs: a vendor with no
successful intake has not been examined, and calling its operations clean would be the console
inventing an all-clear it never earned. `declined` and `failed` are not evidence either -- a
decline means the adapter would not answer and a failure means it could not.
"""

from datetime import datetime, timezone

import pytest

from sync.core import CallSite, Finding, VendorChange
from sync.graph.store import GraphStore
from sync.signals.intake_attempt import IntakeAttempt

DSN = "postgresql://sync:sync@localhost:5433/sync"


@pytest.fixture()
def store():
    s = GraphStore(DSN)
    s.apply_schema()
    s.truncate_all()
    return s


def _site(**kw) -> CallSite:
    base = dict(
        repo_id="r1",
        path="src/billing.ts",
        line=42,
        col=8,
        vendor_id="stripe",
        operation_id="PostCharges",
        symbol="stripe.charges.create",
        args_keys=["amount"],
        response_fields_read=["status"],
        sdk_version="18.0.0",
        content_hash="hash-1",
    )
    base.update(kw)
    return CallSite(**base)


def _finding(call_site_id: str, **kw) -> Finding:
    base = dict(
        detector="vendor-change",
        claim="request-parameter-removed",
        call_site_id=call_site_id,
        severity="breaking",
        rationale="the call passes a parameter the vendor removed",
        binding_rung="static",
    )
    base.update(kw)
    return Finding(**base)


def _checked(store, vendor_id: str, outcome: str = "success") -> None:
    store.record_intake_attempt(
        IntakeAttempt(
            vendor_id=vendor_id,
            attempted_at=datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc),
            outcome=outcome,
            changes_count=0,
            reason_code=None if outcome == "success" else "up_to_date",
        )
    )


def test_an_operation_with_an_open_finding_is_at_risk(store):
    site = store.upsert_call_site(_site())
    store.insert_finding(_finding(site))
    _checked(store, "stripe")

    page = store.call_sites_page("r1")

    assert page["items"][0]["binding_status"] == "at_risk"


def test_an_examined_operation_with_no_finding_is_clean(store):
    """The answer the owner asked for: the call is fine, and the console now says so.

    Not "no findings" rendered as a blank cell -- a measured absence stated as one.
    """
    store.upsert_call_site(_site())
    _checked(store, "stripe")

    page = store.call_sites_page("r1")

    assert page["items"][0]["binding_status"] == "clean"


def test_an_operation_whose_vendor_was_never_examined_is_not_clean(store):
    """The distinction the whole feature rests on, and the one that could quietly break.

    With no successful intake, the graph has never compared this vendor's spec to anything.
    Reporting `clean` here would be an all-clear the console never earned -- and it is the exact
    shape of claim this product exists to refuse, arriving as reassurance rather than as a score.
    """
    store.upsert_call_site(_site())

    page = store.call_sites_page("r1")

    assert page["items"][0]["binding_status"] == "unchecked"


@pytest.mark.parametrize("outcome", ["declined", "failed"])
def test_an_attempt_that_did_not_examine_the_spec_does_not_make_a_call_clean(store, outcome):
    """`declined` means the adapter would not answer; `failed` means it could not.

    Neither read the vendor's specification, so neither is evidence about the call. Counting any
    attempt rather than a successful one would turn a week of 403s into an all-clear, which is
    the failure `intake_attempt` was built to make visible in the first place.
    """
    store.upsert_call_site(_site())
    _checked(store, "stripe", outcome=outcome)

    page = store.call_sites_page("r1")

    assert page["items"][0]["binding_status"] == "unchecked"


def test_one_vendors_examination_says_nothing_about_another(store):
    store.upsert_call_site(_site(vendor_id="stripe", path="src/a.ts"))
    store.upsert_call_site(_site(vendor_id="twilio", path="src/b.ts"))
    _checked(store, "stripe")

    by_path = {row["path"]: row["binding_status"] for row in store.call_sites_page("r1")["items"]}

    assert by_path == {"src/a.ts": "clean", "src/b.ts": "unchecked"}


def test_a_finding_on_one_operation_does_not_put_another_at_risk(store):
    """At risk is per operation, not per vendor.

    A vendor with one broken call and forty working ones is the ordinary case, and reporting all
    forty-one as at risk would make the status useless exactly where it is most needed.
    """
    broken = store.upsert_call_site(_site(operation_id="PostCharges", path="src/a.ts"))
    store.upsert_call_site(_site(operation_id="GetBalance", path="src/b.ts"))
    store.insert_finding(_finding(broken))
    _checked(store, "stripe")

    by_path = {row["path"]: row["binding_status"] for row in store.call_sites_page("r1")["items"]}

    assert by_path == {"src/a.ts": "at_risk", "src/b.ts": "clean"}


def test_the_status_counts_exactly_what_every_other_open_findings_read_counts(store):
    """Consistency with the figures beside it, which decided the dismissal question.

    `record_dismissal` writes a row and never a column, and `_open_findings_predicate` -- the
    clause seven reads share -- asks only `finding.status = 'open'`. So a dismissed finding is
    still an open finding to every count in this store.

    This status matches that deliberately. Teaching one query about dismissals and not the other
    seven would put "clean" beside a table listing the finding, and a reader cannot be expected to
    know which of the two was using the newer rule. If dismissal should exclude a finding from
    open counts, that is one change to `_open_findings_predicate` and this follows it for free.
    """
    site = store.upsert_call_site(_site())
    finding_id = store.insert_finding(_finding(site))
    _checked(store, "stripe")
    store.record_dismissal(finding_id, reason="intentional", actor="tester")

    page = store.call_sites_page("r1")

    assert page["items"][0]["binding_status"] == "at_risk"
    assert store.open_findings_at_risk_count(repo_id="r1") == 1


def test_the_facet_counts_every_status_the_page_holds(store):
    """The rail needs counts, and they are counted over the same rows the table admits."""
    broken = store.upsert_call_site(_site(operation_id="PostCharges", path="src/a.ts"))
    store.upsert_call_site(_site(operation_id="GetBalance", path="src/b.ts"))
    store.upsert_call_site(_site(vendor_id="twilio", operation_id="GetCalls", path="src/c.ts"))
    store.insert_finding(_finding(broken))
    _checked(store, "stripe")

    counts = store.call_sites_page("r1")["by_binding_status"]

    assert counts == {"at_risk": 1, "clean": 1, "unchecked": 1}


def test_a_status_absent_from_the_page_is_absent_rather_than_nought(store):
    """The grouping returns groups that exist -- the rule every other facet here follows.

    A render site must not fill a missing key with a zero: `unchecked: 0` claims the question was
    asked of every call and answered, which is a different fact from no call being unchecked.
    """
    store.upsert_call_site(_site())
    _checked(store, "stripe")

    counts = store.call_sites_page("r1")["by_binding_status"]

    assert counts == {"clean": 1}
    assert "at_risk" not in counts


def test_narrowing_to_clean_returns_only_the_calls_that_are(store):
    """The owner's actual request: *show me the safe APIs*, as a set they can walk."""
    broken = store.upsert_call_site(_site(operation_id="PostCharges", path="src/a.ts"))
    store.upsert_call_site(_site(operation_id="GetBalance", path="src/b.ts"))
    store.insert_finding(_finding(broken))
    _checked(store, "stripe")

    page = store.call_sites_page("r1", binding_statuses=["clean"])

    assert page["total"] == 1
    assert page["items"][0]["path"] == "src/b.ts"


def test_the_status_facet_ignores_its_own_filter(store):
    """The rail's standing rule, which multi-select made load-bearing.

    A facet narrowed by its own selection collapses to what is already pressed, and the option
    that would clear it is the one that vanishes.
    """
    broken = store.upsert_call_site(_site(operation_id="PostCharges", path="src/a.ts"))
    store.upsert_call_site(_site(operation_id="GetBalance", path="src/b.ts"))
    store.insert_finding(_finding(broken))
    _checked(store, "stripe")

    page = store.call_sites_page("r1", binding_statuses=["clean"])

    assert page["by_binding_status"] == {"at_risk": 1, "clean": 1}
