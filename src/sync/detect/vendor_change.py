"""Joins vendor changes against call sites and emits findings.

The filter that matters is the second one: a change to an operation the code
calls is only a finding if the code actually touches the thing that changed.
Without it, every Stripe release would fire on every call site.

When the changed path can't be determined, or the change's kind doesn't say
whether it's request- or response-side, we emit anyway, on the operation
match alone, rather than filter it away. Failing to resolve is recoverable --
a reviewer spends a glance on an irrelevant finding, and the verification
gate catches anything that doesn't actually matter. Resolving incorrectly is
not: a breaking change we silently drop is the exact failure this detector
exists to prevent.

Why the comparison is path against path
---------------------------------------
Both sides record paths, and a call site matches when its path leads into the
change's. Two cheaper rules were measured against Stripe's real v2320 -> v2330
window and rejected. The record count that stood here has been withdrawn rather
than refreshed: oasdiff returns a different total on every run over the same
hash-verified bytes -- nine runs spanned 29,768 to 1,375,504 -- so any absolute
here was one run's number wearing the clothes of a measurement. Every shape
claim below reproduced across all nine runs and is stated as a proportion or a
structure for that reason.

Matching the change's *leaf* against a bare field name, which is what this
detector did before, cannot work at all: not one record in the window is
depth-1. The shallowest is three segments and the median is about twenty-five,
with leaves like `iin` and `stored_credential_usage` sitting under
`error/payment_method/card/generated_from/...`. No static indexer reaches that
depth, because the code doesn't: it writes `result.error` and stops.

Matching *any* segment of the change's path, leaving the indexer alone, fails
in the opposite direction. `card` and `payment_method_details` occur in all
records and `data` in all but a handful, so any call site reading `data`
-- which is nearly every call site consuming a Stripe list -- would match every
change in the window. That is an operation-match-only finding wearing a field
match's rationale, which is worse than an honest operation-match-only finding,
because it misreports why it fired.

Anchoring the comparison at the outermost segment is what keeps the filter a
filter. The window's changes hang off only 44 distinct top-level fields, and
`id`, `status`, `amount`, `currency`, `created`, `object` and `livemode` are
none of them -- so the call sites that read only those still correctly do not
match.

What the rule costs
-------------------
Segments may be skipped in the change's path but never in the call site's.
oasdiff writes a segment where an array is walked (`data/items/customer`) and
the call site's syntax writes nothing there, so a rule without skipping would
miss almost everything -- `items` appears in all but a handful of the window's
records.
Skipping also admits a call site whose path rejoins the change's further down
a different branch. That is a false positive, and it is the direction this
module has always chosen: a reviewer's glance, not a dropped breaking change.

A match that stops short of the changed field is real but weak -- reading
`result.customer` says nothing about whether the code reaches `iin` twelve
levels below. Those degrade to operation-match-only findings and say so, rather
than being filtered or being reported as if the call site read the field
itself. There is deliberately no confidence score and no depth cut-off: there
is still no labelled data to calibrate either against, and a threshold picked
without one would drop findings for a number nobody can defend.
"""

from __future__ import annotations

from sync.core import Finding
from sync.graph.store import GraphStore
from sync.signals.oasdiff import changed_path


def _leads_into(site_path: str, change_segments: list[str]) -> bool:
    """Whether a recorded call-site path leads into a change's path.

    Anchored at the outermost segment, then consuming the call site's segments
    in order. The change's path may skip -- it carries structural segments the
    call site's syntax has no way to write.
    """
    wanted = site_path.split(".")
    if change_segments[0] != wanted[0]:
        return False
    matched = 1
    for segment in change_segments[1:]:
        if matched < len(wanted) and segment == wanted[matched]:
            matched += 1
    return matched == len(wanted)


def _deepest_match(site_paths: list[str], change_segments: list[str]) -> str | None:
    """The longest recorded path that leads into the change, if any does.

    The longest one is what the rationale should quote: it is the most the
    index can show the call site actually touches.
    """
    matches = [p for p in site_paths if _leads_into(p, change_segments)]
    return max(matches, key=lambda p: len(p.split(".")), default=None)


class VendorChangeDetector:
    detector_id = "vendor_change"

    def __init__(self, store: GraphStore, vendor_id: str = "stripe") -> None:
        self._store = store
        self._vendor_id = vendor_id

    def scan(self) -> list[Finding]:
        findings: list[Finding] = []

        for change in self._store.all_vendor_changes(self._vendor_id):
            sites = self._store.call_sites_for_operation(self._vendor_id, change.operation_id)
            if not sites:
                continue

            path = changed_path(change)

            for site in sites:
                # oasdiff's ~500 change kinds all start with "request-" or
                # "response-"; that prefix is the actual invariant, not any
                # enumerated list of kinds we'd have to keep in sync with it.
                # `claim` names how strong the join was, which is the one thing about this
                # finding that varies and the first thing a reviewer wants: a matched request
                # field is a specific argument this site passes, a matched response field is a
                # specific field it reads, and an operation-only match says the change lands on
                # this operation and the field could not be placed. The vendor change already
                # keeps two findings about one site apart, so nothing here is load-bearing for
                # identity -- which is exactly why it would have been the place to put a
                # thoughtless constant and tell the next reader the field is optional in spirit.
                if path is not None and change.kind.startswith("request-"):
                    detail = self._detail(path, site.args_keys, "passes")
                    claim = "request-field"
                elif path is not None and change.kind.startswith("response-"):
                    detail = self._detail(path, site.response_fields_read, "reads")
                    claim = "response-field"
                elif path is None:
                    detail = "field could not be determined from the vendor change -- operation match only"
                    claim = "operation-only"
                else:
                    detail = f"kind `{change.kind}` is neither request- nor response-side -- operation match only"
                    claim = "operation-only"

                if detail is None:
                    continue

                findings.append(
                    Finding(
                        detector=self.detector_id,
                        claim=claim,
                        call_site_id=site.id,
                        vendor_change_id=change.id,
                        severity=change.severity,
                        rationale=(
                            f"{change.kind} on {change.operation_id}: {detail} "
                            f"({site.path}:{site.line})"
                        ),
                    )
                )

        return findings

    def _detail(self, path: list[str], site_paths: list[str], verb: str) -> str | None:
        """How this call site meets the change, or `None` if it doesn't meet it at all."""
        matched = _deepest_match(site_paths, path)
        if matched is None:
            return None
        if matched.split(".")[-1] == path[-1]:
            return f"call site {verb} `{matched}`"
        return (
            f"call site {verb} `{matched}`, which leads to the changed `{path[-1]}` "
            f"{len(path) - len(matched.split('.'))} level(s) below it -- operation match only"
        )
