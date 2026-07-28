"""The corpus that cannot be backfilled.

`docs/superpowers/specs/2026-07-25-sync-migration-corpus.md` declares this table, and four other
specs already speak as though it exists -- the routing matrix tells an implementer to write into
columns that were never created. Every finding processed before it exists is a row permanently
lost, which is the whole argument for building it before it pays.

The privacy rules are tested rather than commented, because they are what makes the corpus safe
to reason across customers: shapes never source, salted hashes never literal keys.
"""

from __future__ import annotations

import os

import pytest

from sync.core import CallSite, MigrationOutcome, Patch, VendorChange
from sync.core.corpus import hash_arg_keys, symbol_shape
from sync.graph.store import GraphStore

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")

SITE = CallSite(
    id="cs-1", repo_id="r", path="src/billing.ts", line=12, col=4, vendor_id="stripe",
    operation_id="PostCharges", symbol="stripe.charges.create",
    args_keys=["amount", "currency", "receipt_email"], response_fields_read=["status", "id"],
    sdk_version="18.0.0", content_hash="h",
)

CHANGE = VendorChange(
    id="vc-1", vendor_id="stripe", from_version="2026-05-01", to_version="2026-11-01",
    kind="request-property-removed", operation_id="PostCharges", path_ptr="/v1/charges",
    severity="breaking", source="oasdiff", raw={},
)


# --- the shape, which is what replaces the source ---------------------------------


def test_the_symbol_is_reduced_to_a_shape():
    """Two companies calling the same SDK method produce the same shape, which is the only
    reason a corpus aggregated across them says anything."""
    assert symbol_shape("stripe.charges.create") == "<client>.<resource>.<verb>"


def test_a_deeper_symbol_keeps_its_depth():
    assert symbol_shape("stripe.checkout.sessions.create") == "<client>.<resource>.<resource>.<verb>"


def test_a_bare_symbol_is_still_shaped():
    assert symbol_shape("fetch") == "<verb>"


def test_the_shape_contains_no_vendor_or_customer_identifier():
    """A shape carrying `charges` would leak which products a customer integrates, and a
    corpus of those is a customer list."""
    shaped = symbol_shape("stripe.charges.create")

    assert "stripe" not in shaped
    assert "charges" not in shaped
    assert "create" not in shaped


# --- salted hashes, never the literal keys ----------------------------------------


def test_argument_keys_are_hashed():
    hashes = hash_arg_keys(["amount", "currency"], salt="s1")

    assert len(hashes) == 2
    assert "amount" not in hashes and "currency" not in hashes


def test_the_same_key_and_salt_hash_alike_so_rows_can_be_compared():
    assert hash_arg_keys(["amount"], salt="s1") == hash_arg_keys(["amount"], salt="s1")


def test_a_different_salt_gives_a_different_hash():
    """Per-deployment salting is what stops a hash being a dictionary lookup. `amount` is a
    guessable key, and an unsalted digest of it is the key."""
    assert hash_arg_keys(["amount"], salt="s1") != hash_arg_keys(["amount"], salt="s2")


def test_hashing_is_order_stable():
    """Two call sites passing the same keys in a different order are the same shape, and rows
    that disagree on ordering cannot be grouped."""
    assert hash_arg_keys(["b", "a"], salt="s") == hash_arg_keys(["a", "b"], salt="s")


def test_an_empty_key_list_hashes_to_nothing_rather_than_to_a_constant():
    assert hash_arg_keys([], salt="s") == []


# --- the row ----------------------------------------------------------------------


def test_an_outcome_is_built_from_a_site_and_a_change():
    outcome = MigrationOutcome.from_attempt(
        finding_id="f-1", attempt_index=0, site=SITE, change=CHANGE,
        patch=Patch(diff="d", strategy="codemod", rationale="r"),
        tier=0, wall_ms=12, salt="s1",
    )

    assert outcome.change_kind == "request-property-removed"
    assert outcome.strategy == "codemod"
    assert outcome.tier == 0
    assert outcome.arg_arity == 3
    assert outcome.response_fields_touched_count == 2


def test_no_source_text_reaches_the_row():
    """Asserted against the row's own serialised form, so a future column cannot smuggle
    source in without failing here."""
    outcome = MigrationOutcome.from_attempt(
        finding_id="f-1", attempt_index=0, site=SITE, change=CHANGE,
        patch=Patch(diff="const x = secretValue;", strategy="agent", rationale="r"),
        tier=2, wall_ms=1, salt="s1",
    )
    serialised = outcome.model_dump_json()

    assert "secretValue" not in serialised
    assert "src/billing.ts" not in serialised, "a file path is customer structure, not shape"
    for key in SITE.args_keys:
        assert key not in serialised


def test_the_diff_is_never_stored():
    """`edit_script` is specified as abstract operations rather than a textual diff. A diff is
    source, and storing it would put customer code in a cross-customer table."""
    outcome = MigrationOutcome.from_attempt(
        finding_id="f-1", attempt_index=0, site=SITE, change=CHANGE,
        patch=Patch(diff="- old\n+ new", strategy="codemod", rationale="r"),
        tier=0, wall_ms=1, salt="s1",
    )
    assert "old" not in outcome.model_dump_json()


def test_the_grain_is_one_row_per_attempt():
    """One finding retried three times is three rows. A query counting findings by counting
    rows is wrong, and this says so out loud."""
    rows = [
        MigrationOutcome.from_attempt(
            finding_id="f-1", attempt_index=i, site=SITE, change=CHANGE,
            patch=Patch(diff="d", strategy="agent", rationale="r"), tier=2, wall_ms=1, salt="s",
        )
        for i in range(3)
    ]
    assert [r.attempt_index for r in rows] == [0, 1, 2]
    assert len({r.finding_id for r in rows}) == 1


# --- persistence ------------------------------------------------------------------


@pytest.fixture()
def store():
    s = GraphStore(DSN)
    s.apply_schema()
    s.truncate_all()
    return s


def _outcome(**over):
    fields = dict(
        finding_id="f-1", attempt_index=0, site=SITE, change=CHANGE,
        patch=Patch(diff="d", strategy="codemod", rationale="r"),
        tier=0, wall_ms=12, salt="s1",
    )
    fields.update(over)
    return MigrationOutcome.from_attempt(**fields)


def test_an_outcome_round_trips(store: GraphStore):
    store.record_migration_outcome(_outcome())
    rows = store.migration_outcomes()

    assert len(rows) == 1
    assert rows[0].change_kind == "request-property-removed"
    assert rows[0].arg_key_hashes == _outcome().arg_key_hashes


def test_every_attempt_is_kept(store: GraphStore):
    """Attempts are the negative class. A corpus of successes cannot compute precision and
    cannot evaluate any future router."""
    for i in range(3):
        store.record_migration_outcome(_outcome(attempt_index=i))

    assert len(store.migration_outcomes()) == 3


def test_recording_the_same_attempt_twice_does_not_duplicate(store: GraphStore):
    """Idempotence, held to the same standard as every other stage. The remediation graph
    retries, and a restarted run must converge rather than inflate the corpus."""
    store.record_migration_outcome(_outcome())
    store.record_migration_outcome(_outcome())

    assert len(store.migration_outcomes()) == 1


def test_the_merge_outcome_can_be_filled_in_later(store: GraphStore):
    """`pr_merged` arrives days later by webhook. A column that silently stays null destroys
    the only measurement that tests the product claim, so the update path exists from the
    start."""
    store.record_migration_outcome(_outcome())
    store.set_merge_outcome("f-1", 0, pr_number=42, pr_merged=True, human_edits_before_merge=1)

    row = store.migration_outcomes()[0]
    assert row.pr_number == 42
    assert row.pr_merged is True
    assert row.human_edits_before_merge == 1
