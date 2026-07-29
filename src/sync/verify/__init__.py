"""Verification tiers that run before the customer's own CI.

`tsc` proves a patch compiles and CI proves the suite still passes, and the gap between them
is where most customers actually live: a green CI run proves little when no test exercises the
patched call. `docs/superpowers/specs/2026-07-26-sync-observed-contract-drift.md` specifies a
replay tier to close it. `mock_response` is its first step -- a body built from the new
specification and from what was actually observed -- and `replay` is the other two: run the
patched call path against that body in a credential-free sandbox with no network, then check
that every field the code reads is still in the response.

The three compose in `replay_from_specification`, which is what a caller holding a schema and
a baseline reaches for. Nothing here writes to the shape store; `ReplayResult.shapes` carries
the `source='replay'` rows for whoever owns it.
"""

from sync.verify.mock_response import (
    FieldDecision,
    PLACEHOLDER_PREFIX,
    decide_field,
    synthesize_mock_response,
)
from sync.verify.replay import (
    REPLAY_SOURCE,
    SYNTHETIC_CREDENTIAL,
    ReplayResult,
    replay_call_path,
    replay_from_specification,
    replay_shapes,
    unsatisfied_fields,
)

__all__ = [
    "FieldDecision",
    "PLACEHOLDER_PREFIX",
    "REPLAY_SOURCE",
    "ReplayResult",
    "SYNTHETIC_CREDENTIAL",
    "decide_field",
    "replay_call_path",
    "replay_from_specification",
    "replay_shapes",
    "synthesize_mock_response",
    "unsatisfied_fields",
]
