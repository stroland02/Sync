"""Joins vendor changes against call sites and emits findings.

The filter that matters is the second one: a change to an operation the code
calls is only a finding if the code actually touches the thing that changed.
Without it, every Stripe release would fire on every call site.
"""

from __future__ import annotations

from sync.core import Finding, VendorChange
from sync.graph.store import GraphStore

_REQUEST_KINDS = {
    "request-parameter-removed",
    "request-parameter-became-required",
    "request-property-removed",
    "request-property-became-required",
}
_RESPONSE_KINDS = {
    "response-property-removed",
    "response-property-became-optional",
    "response-body-type-changed",
}


def _changed_field(change: VendorChange) -> str | None:
    """The field name a change refers to, when it refers to one."""
    for key in ("field", "property", "parameter", "name"):
        value = change.raw.get(key)
        if isinstance(value, str) and value:
            return value
    tail = change.path_ptr.rsplit("/", 1)[-1]
    return tail or None


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
                if change.kind in _RESPONSE_KINDS and field is not None:
                    if field not in site.response_fields_read:
                        continue
                elif change.kind in _REQUEST_KINDS and field is not None:
                    if field not in site.args_keys:
                        continue

                detail = f"`{field}`" if field else change.kind
                findings.append(
                    Finding(
                        detector=self.detector_id,
                        call_site_id=site.id or "",
                        vendor_change_id=change.id,
                        severity=change.severity,
                        rationale=(
                            f"{change.kind} on {change.operation_id}: {detail} "
                            f"affects {site.path}:{site.line}"
                        ),
                    )
                )

        return findings
