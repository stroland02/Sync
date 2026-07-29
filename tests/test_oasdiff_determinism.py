"""What oasdiff's nondeterminism does to the SIGNAL stage.

`docs/superpowers/reports/2026-07-29-oasdiff-determinism.md` has the measurement. The short of it:
running `oasdiff breaking` on two hash-verified specification files produces a different answer
every time, on both 1.26.0 and the 1.26.1 CI pins, and the variance reaches `vendor_change` rows
rather than stopping at a record count.

These tests hold the parts of that a future change could quietly alter. They do **not** assert
that oasdiff is unstable -- an assertion that fails the day somebody fixes the binary is a trap,
and two runs can agree by luck. What they pin instead is the shape of Sync's own exposure:

- Sync adds no nondeterminism of its own. `to_vendor_changes` is a pure function of the records
  it is handed, so every difference between two runs came from the binary.
- The amplification is the natural key. Two records that differ only in their free-text message
  are two rows, because `upsert_vendor_change` hashes `raw["text"]`. That is the mechanism by
  which a record-count wobble becomes a row-set wobble, and it is one line in another module.
- The noise filter removes the volume and none of the coverage loss. Ninety-three per cent of the
  records are `response-property-enum-value-added`, which `NOISE_KINDS` drops -- and every one of
  the 467 operation-level rows that appear in some runs and not others is the other kind, which it
  keeps.

The one test that actually runs the binary is opt-in behind `SYNC_OASDIFF_DETERMINISM=1`, because
it costs up to ninety seconds and its subject is a third-party executable. It asserts the property
that held across six runs and would matter if it stopped: repeated runs are **nested**. A run
finds a subset of what a larger run finds and never invents a row the larger run lacks, so the
failure mode is lost work rather than fabricated work. A future oasdiff that produced genuinely
divergent sets would be a worse problem than this one, and this is what would say so.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from sync.signals.oasdiff import to_vendor_changes
from sync.signals.stripe.adapter import NOISE_KINDS

SPECS = Path(".cache/specs")
BASE = SPECS / "v2320.json"
REVISION = SPECS / "v2330.json"
BINARY = Path("tools/oasdiff.exe")

# The two rule ids every record in six runs carried, and the only two this specification pair
# produces at all. Both are level 2 -- oasdiff's "warning", not its "error".
ENUM_ADDED = "response-property-enum-value-added"
OPTIONAL_REMOVED = "response-optional-property-removed"


def _record(rule_id: str, text: str, operation_id: str = "GetAccount", path: str = "/v1/account"):
    """One oasdiff record, in the shape the binary really emits.

    Eight keys, taken from a real record rather than invented: a record this rule does not
    recognise would make every assertion below a statement about a fixture.
    """
    return {
        "id": rule_id,
        "text": text,
        "level": 2,
        "operation": "GET",
        "operationId": operation_id,
        "path": path,
        "section": "paths",
        "fingerprint": "8f1be3049e33",
    }


def test_the_mapping_adds_no_nondeterminism_of_its_own():
    """Every difference between two SIGNAL runs came from the binary, not from this code.

    Worth pinning because it is what makes the finding actionable: if `to_vendor_changes` were
    itself order-dependent there would be two problems to separate, and there is one.
    """
    records = [
        _record(OPTIONAL_REMOVED, "removed the optional property `a/b/c`"),
        _record(ENUM_ADDED, "added the new enum value `x` to `d/e`"),
    ]

    first = to_vendor_changes(records, "stripe", "v1", "v2")
    second = to_vendor_changes(records, "stripe", "v1", "v2")

    assert [c.model_dump(exclude={"detected_at"}) for c in first] == [
        c.model_dump(exclude={"detected_at"}) for c in second
    ]


def test_two_records_differing_only_in_their_message_are_two_changes():
    """The amplification, at the point it happens.

    `upsert_vendor_change` hashes `raw["text"]` into the natural key, and the text is where
    oasdiff writes the recursive property path -- `error/payment_intent/customer/anyOf[subschema
    #2: Customer]/subscriptions/data/items/...`. So a run that expands one branch further than the
    last run does not produce a differently-worded version of the same row; it produces a new row.

    That is the whole reason a record-count wobble is not absorbed by the conflict clause.
    """
    deep = _record(OPTIONAL_REMOVED, "removed the optional property `a/b/c`")
    deeper = _record(OPTIONAL_REMOVED, "removed the optional property `a/b/c/d`")

    changes = to_vendor_changes([deep, deeper], "stripe", "v1", "v2")

    assert len(changes) == 2
    assert changes[0].kind == changes[1].kind
    assert changes[0].operation_id == changes[1].operation_id
    assert changes[0].path_ptr == changes[1].path_ptr
    assert changes[0].raw["text"] != changes[1].raw["text"], (
        "the message is the only field that differs, and it is in the natural key"
    )


def test_the_noise_filter_drops_the_volume_and_keeps_the_kind_that_loses_operations():
    """Where the practical exposure actually sits, and it is not where the raw counts suggest.

    `response-property-enum-value-added` is 738,972 of the 792,552 records measured across six
    runs and `NOISE_KINDS` drops it, so the Stripe and Twilio adapters never see 93% of the noise.
    Every one of the 467 operation-level rows that vary between runs is
    `response-optional-property-removed`, which the filter keeps -- so filtering removes the
    frightening number and none of the reproducibility problem.
    """
    assert ENUM_ADDED in NOISE_KINDS
    assert OPTIONAL_REMOVED not in NOISE_KINDS

    records = [
        _record(ENUM_ADDED, "added the new enum value `x`"),
        _record(OPTIONAL_REMOVED, "removed the optional property `a/b`"),
    ]
    kept = [r for r in records if r.get("id") not in NOISE_KINDS]

    assert [r["id"] for r in kept] == [OPTIONAL_REMOVED]


def test_every_record_becomes_a_breaking_change_whatever_oasdiff_called_it():
    """A separate defect this investigation found, pinned rather than fixed.

    All 792,552 records measured across six runs carry `level: 2`, which is oasdiff's *warning*.
    `to_vendor_changes` stamps `severity="breaking"` on every record unconditionally, so the
    severity on a `VendorChange` from this source is a constant rather than evidence.

    Asserted as it is rather than corrected: severity feeds triage, and changing what it means is
    a decision with a blast radius well outside this task. The report recommends it; this test is
    what makes the current behaviour deliberate instead of accidental, and what will fail when
    somebody acts on that recommendation.
    """
    records = [_record(ENUM_ADDED, "added the new enum value `x`")]
    assert records[0]["level"] == 2

    changes = to_vendor_changes(records, "stripe", "v1", "v2")

    assert [c.severity for c in changes] == ["breaking"]


@pytest.mark.skipif(
    os.environ.get("SYNC_OASDIFF_DETERMINISM") != "1",
    reason="runs the oasdiff binary twice over 15 MB of specification; set "
    "SYNC_OASDIFF_DETERMINISM=1 to include it",
)
@pytest.mark.skipif(
    not (BINARY.exists() and BASE.exists() and REVISION.exists()),
    reason="needs tools/oasdiff and the pinned specifications from "
    "scripts/fetch_measurement_inputs.py",
)
def test_repeated_runs_are_nested_rather_than_divergent():
    """The invariant that held across six runs, and the one whose loss would be worse.

    Two runs disagree -- that is measured and is not what this asserts, because two runs can also
    agree by luck and an assertion of instability fails the day the binary is fixed. What holds in
    every pair observed is that the smaller answer is contained in the larger: a run truncates the
    walk early and loses rows, and never reports a row a longer run did not find.

    That is what makes the failure mode "lost work" rather than "invented work", and it is what
    makes a union over runs a coherent mitigation. An oasdiff that started producing genuinely
    divergent sets would break both of those, and this is the test that would say so.
    """
    first = _operation_rows()
    second = _operation_rows()

    assert first <= second or second <= first, (
        f"neither run's rows contain the other's: {len(first - second)} only in the first, "
        f"{len(second - first)} only in the second"
    )


def _operation_rows() -> set[tuple[str, str, str]]:
    result = subprocess.run(
        [str(BINARY), "breaking", str(BASE), str(REVISION), "--format", "json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    return {
        (r.get("id", ""), r.get("path", ""), r.get("operationId") or "")
        for r in json.loads(result.stdout)
    }
