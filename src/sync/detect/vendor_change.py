"""Joins vendor changes against call sites and emits findings.

The filter that matters is the second one: a change to an operation the code
calls is only a finding if the code actually touches the thing that changed.
Without it, every Stripe release would fire on every call site.

When the changed field can't be determined, or the change's kind doesn't say
whether it's request- or response-side, we emit anyway, on the operation
match alone, rather than filter it away. Failing to resolve is recoverable --
a reviewer spends a glance on an irrelevant finding, and the verification
gate catches anything that doesn't actually matter. Resolving incorrectly is
not: a breaking change we silently drop is the exact failure this detector
exists to prevent.
"""

from __future__ import annotations

import re

from sync.core import Finding, VendorChange
from sync.graph.store import GraphStore

_BACKTICKED = re.compile(r"`([^`]+)`")


def _changed_field(change: VendorChange) -> str | None:
    """The field name a change refers to, when it can be determined.

    Real oasdiff records never carry a `field`, `property`, `parameter`, or
    `name` key -- the lookups below cost nothing today and stand ready in
    case a future oasdiff version adds a structured one. The field name lives
    in the free-text `text` message instead, as the first backticked token
    (oasdiff backticks the field it names before any incidental value, such
    as a status code). There is deliberately no path-derived fallback: a path
    segment is never a field name, and returning one would be confident
    nonsense -- worse than admitting the field couldn't be determined.
    """
    for key in ("field", "property", "parameter", "name"):
        value = change.raw.get(key)
        if isinstance(value, str) and value:
            return value
    text = change.raw.get("text")
    if isinstance(text, str):
        match = _BACKTICKED.search(text)
        if match:
            return match.group(1)
    return None


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

            field = _changed_field(change)

            for site in sites:
                # oasdiff's ~500 change kinds all start with "request-" or
                # "response-"; that prefix is the actual invariant, not any
                # enumerated list of kinds we'd have to keep in sync with it.
                if field is not None and change.kind.startswith("request-"):
                    if field not in site.args_keys:
                        continue
                    detail = f"call site passes `{field}`"
                elif field is not None and change.kind.startswith("response-"):
                    if field not in site.response_fields_read:
                        continue
                    detail = f"call site reads `{field}`"
                elif field is None:
                    detail = "field could not be determined from the vendor change -- operation match only"
                else:
                    detail = f"kind `{change.kind}` is neither request- nor response-side -- operation match only"

                findings.append(
                    Finding(
                        detector=self.detector_id,
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
