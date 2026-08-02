"""Which observation sources are responses the vendor sent, and which are Sync's own work.

`observed_shape.source` names the mechanism that produced a row. Two consumers read the table as
traffic -- `ObservedDriftDetector` and the baseline `sync.remediate.nodes` hands the mock builder
-- and that reading was correct only because both writers emit `error-payload`. The replay tier
builds `source='replay'` rows, which are the published specification restated through the
customer's code rather than anything a vendor sent, and
`docs/superpowers/reports/2026-07-30-replay-shapes-reach-the-store.md` measures what filing them
beside traffic costs.

These are mechanisms, not vendors: Sentry and Datadog both write `error-payload`. No adapter's
name appears here and none may, which is what keeps this out of the reach of `CLAUDE.md`'s rule
that vendor knowledge lives in adapters.

**Membership is positive.** A source added to `ObservationSource` and forgotten here is then
absent from every baseline rather than silently entering one -- and `ObservedDriftDetector` is
the detector most able to violate precision-over-recall, so the failure that costs recall is the
one to take. `test_every_declared_observation_source_is_classified` is what keeps the omission
loud rather than merely safe; the two sets are written out rather than derived from each other
so that test has something to check.
"""

from __future__ import annotations

TRAFFIC_SOURCES: frozenset[str] = frozenset({"error-payload", "interceptor"})
"""Rows built from a response the customer's code actually received."""

SYNTHETIC_SOURCES: frozenset[str] = frozenset({"replay"})
"""Rows built from a body Sync constructed. Evidence about a specification, not about a vendor."""
