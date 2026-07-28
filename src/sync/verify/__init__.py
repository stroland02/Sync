"""Verification tiers that run before the customer's own CI.

`tsc` proves a patch compiles and CI proves the suite still passes, and the gap between them
is where most customers actually live: a green CI run proves little when no test exercises the
patched call. `docs/superpowers/specs/2026-07-26-sync-observed-contract-drift.md` specifies a
replay tier to close it, and `mock_response` is its first step.
"""

from sync.verify.mock_response import (
    FieldDecision,
    PLACEHOLDER_PREFIX,
    decide_field,
    synthesize_mock_response,
)

__all__ = [
    "FieldDecision",
    "PLACEHOLDER_PREFIX",
    "decide_field",
    "synthesize_mock_response",
]
