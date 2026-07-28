"""Findings that need two facts about one call site.

Every other detector matches one thing. This one fires only where a call site both passes a
deprecated parameter and belongs to the vendor whose parameter it is, which is only expressible
because `sync.index.literals` records the model and its sibling argument keys in the same row.
Matching on the parameter name alone would fire on every API that happens to take a
`temperature`.

The deliberate imprecision is the model scope. Vendors write it as prose -- "Claude Opus 4.7 and
later" -- and deciding whether `claude-opus-5` falls inside that needs a version ordering across
model families that nobody publishes machine-readably. Inventing one would be a confident guess
in the one place this system refuses them, so the scope is reported and the severity says the
detector did not resolve it.
"""

from __future__ import annotations

from typing import Iterable, Sequence

from sync.core import CallSite, Finding
from sync.signals.deprecations import ParameterDeprecation


class ParameterDeprecationDetector:
    """Call sites passing a request parameter their vendor no longer honours."""

    detector_id = "parameter-deprecation"

    def __init__(
        self,
        deprecations: Sequence[ParameterDeprecation],
        call_sites: Sequence[CallSite],
    ) -> None:
        self._deprecations = list(deprecations)
        self._call_sites = list(call_sites)

    def scan(self) -> Iterable[Finding]:
        for site in self._call_sites:
            # A `Finding` addresses its call site by id. Inventing one would produce a finding
            # nothing downstream could resolve back to a location.
            if site.id is None:
                continue

            passed = set(site.args_keys)
            for deprecation in self._deprecations:
                if deprecation.vendor_id != site.vendor_id:
                    continue
                if deprecation.parameter not in passed:
                    continue

                yield Finding(
                    detector=self.detector_id,
                    call_site_id=site.id,
                    # Severity carries the confidence. The scope was not evaluated, so claiming
                    # `breaking` would spend trust this finding has not earned.
                    severity="deprecation",
                    rationale=self._rationale(deprecation, site),
                )

    def _rationale(self, deprecation: ParameterDeprecation, site: CallSite) -> str:
        """What a reviewer needs in order to make the call the detector deliberately did not."""
        scope = f" from {deprecation.applies_from}" if deprecation.applies_from else ""
        remedy = (
            f"Rename it to `{deprecation.replacement}`."
            if deprecation.replacement
            else "The vendor's guidance is to omit it rather than replace it."
        )

        return (
            f"`{deprecation.parameter}` is passed at {site.path}:{site.line} on model "
            f"`{site.operation_id}`, and {deprecation.vendor_id} deprecated it{scope}: "
            f"{deprecation.behavior.rstrip('.')}. {remedy} "
            "Deprecated parameters stay in the SDK request types, so this continues to "
            "type-check and fails at the vendor instead. Whether this model is inside the "
            "stated scope is not resolved here."
        )
