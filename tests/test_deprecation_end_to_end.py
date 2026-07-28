"""Vendor table to applied patch, with no model call anywhere in the path.

Each stage is tested on its own elsewhere. This asserts they compose, because a pipeline whose
parts all pass and whose whole does not is the failure that survives a green suite.

The path exercised: SIGNAL reads the vendor's published table, INDEX finds the literals in
source, DETECT joins them on `operation_id`, PATCH emits `ast-grep` rules, and the rules apply
deterministically. Tier 0 in the routing matrix, start to finish, for free.
"""

from __future__ import annotations

from datetime import date

from sync.index.literals import index_operation_literals
from sync.route import apply_rules, model_literal_swap
from sync.signals.deprecations import parse_deprecation_table, to_vendor_changes, urgency

# Trimmed from the page published on 2026-07-28. Both tables, as they appear there.
VENDOR_PAGE = """\
| API model name             | Current state | Deprecated        | Tentative retirement date         |
| -------------------------- | ------------- | ----------------- | --------------------------------- |
| claude-opus-4-8            | Active        | N/A               | Not sooner than May 28, 2027      |
| claude-opus-4-1-20250805   | Deprecated    | June 5, 2026      | August 5, 2026                    |
| claude-3-7-sonnet-20250219 | Retired       | October 28, 2025  | February 19, 2026                 |

### 2026-06-05: Claude Opus 4.1 model

| Retirement date | Deprecated model           | Recommended replacement |
| --------------- | -------------------------- | ----------------------- |
| August 5, 2026  | `claude-opus-4-1-20250805` | `claude-opus-4-8`       |

### 2025-10-28: Claude Sonnet 3.7 model

| Retirement date   | Deprecated model             | Recommended replacement |
| ----------------- | ---------------------------- | ----------------------- |
| February 19, 2026 | `claude-3-7-sonnet-20250219` | `claude-opus-4-8`       |
"""

# Shaped like an integration a customer would actually have: two models in use, one of them
# already retired, one healthy, and a comment that must not be touched.
CUSTOMER_SOURCE = """\
import Anthropic from '@anthropic-ai/sdk';

const client = new Anthropic();

// Kept on the old model deliberately for now.
export async function summarise(text: string) {
  return client.messages.create({
    model: "claude-3-7-sonnet-20250219",
    max_tokens: 1024,
    messages: [{ role: 'user', content: text }],
  });
}

export async function classify(text: string) {
  return client.messages.create({
    model: 'claude-opus-4-1-20250805',
    max_tokens: 16,
    messages: [{ role: 'user', content: text }],
  });
}

export async function healthy(text: string) {
  return client.messages.create({
    model: "claude-opus-4-8",
    max_tokens: 16,
    messages: [{ role: 'user', content: text }],
  });
}
"""


def _pipeline(source: str, today: date):
    """SIGNAL, INDEX, DETECT, PATCH -- returning the patched source and the findings."""
    rows = parse_deprecation_table("anthropic", VENDOR_PAGE)
    changes = to_vendor_changes(rows, from_version="2026-07-01", to_version="2026-07-28")
    by_model = {row.model_id: row for row in rows}

    sites = index_operation_literals(
        source,
        path="src/summarise.ts",
        repo_id="repo-1",
        vendor_id="anthropic",
        sdk_version="0.70.0",
        prefixes=("claude-",),
    )
    indexed = {site.operation_id for site in sites}

    findings = []
    patched = source
    for change in changes:
        # The DETECT join, exactly as `call_sites_for_operation` performs it.
        if change.operation_id not in indexed:
            continue
        findings.append((change, urgency(by_model[change.operation_id], today)))
        patched = apply_rules(model_literal_swap(change, language="typescript"), patched, "typescript")

    return patched, findings, sites


def test_both_dying_models_are_found_and_the_healthy_one_is_not():
    _, findings, sites = _pipeline(CUSTOMER_SOURCE, today=date(2026, 7, 28))

    assert {c.operation_id for c, _ in findings} == {
        "claude-3-7-sonnet-20250219",
        "claude-opus-4-1-20250805",
    }
    # The healthy model is indexed -- it is a real call site -- but produces no finding.
    assert "claude-opus-4-8" in {s.operation_id for s in sites}


def test_the_patched_source_names_only_live_models():
    patched, _, _ = _pipeline(CUSTOMER_SOURCE, today=date(2026, 7, 28))

    assert "claude-3-7-sonnet-20250219" not in patched
    assert "claude-opus-4-1-20250805" not in patched
    assert patched.count("claude-opus-4-8") == 3


def test_quote_style_is_preserved_at_each_site():
    """One site used double quotes and the other single. A patch that normalises them adds
    review noise and may lose a fight with the customer's formatter in their own CI."""
    patched, _, _ = _pipeline(CUSTOMER_SOURCE, today=date(2026, 7, 28))

    assert 'model: "claude-opus-4-8"' in patched
    assert "model: 'claude-opus-4-8'" in patched


def test_nothing_outside_the_model_ids_moved():
    patched, _, _ = _pipeline(CUSTOMER_SOURCE, today=date(2026, 7, 28))

    assert "// Kept on the old model deliberately for now." in patched
    assert "max_tokens: 1024" in patched
    assert "role: 'user'" in patched
    assert patched.count("client.messages.create") == 3
    assert len(patched.splitlines()) == len(CUSTOMER_SOURCE.splitlines())


def test_the_findings_carry_a_deadline_and_one_is_already_an_outage():
    """The property no other signal in the system has. One model is 159 days past retirement
    -- the vendor states requests to it fail -- and the other has days left, which is the
    difference between an incident and a scheduled change."""
    _, findings, _ = _pipeline(CUSTOMER_SOURCE, today=date(2026, 7, 28))
    days = {c.operation_id: d for c, d in findings}

    assert days["claude-3-7-sonnet-20250219"] == -159
    assert days["claude-opus-4-1-20250805"] == 8


def test_severity_separates_the_outage_from_the_deadline():
    _, findings, _ = _pipeline(CUSTOMER_SOURCE, today=date(2026, 7, 28))
    severity = {c.operation_id: c.severity for c, _ in findings}

    assert severity["claude-3-7-sonnet-20250219"] == "breaking"
    assert severity["claude-opus-4-1-20250805"] == "deprecation"


def test_the_pipeline_is_idempotent():
    """Running it on its own output changes nothing. The remediation graph retries, so a
    non-idempotent patch is a corruption waiting for a slow CI run."""
    once, _, _ = _pipeline(CUSTOMER_SOURCE, today=date(2026, 7, 28))
    twice, findings, _ = _pipeline(once, today=date(2026, 7, 28))

    assert twice == once
    assert findings == []


def test_a_repository_with_no_dying_models_produces_no_patch():
    clean = 'const m = { model: "claude-opus-4-8" };'
    patched, findings, _ = _pipeline(clean, today=date(2026, 7, 28))

    assert patched == clean
    assert findings == []
