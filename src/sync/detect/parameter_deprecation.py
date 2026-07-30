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

import logging
from dataclasses import dataclass
from typing import Iterable, Sequence

from sync.core import CallSite, Finding
from sync.signals.deprecations import ParameterDeprecation

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class LinkedDeprecation:
    """One parameter deprecation beside the id of the `VendorChange` it became.

    The pair exists because a `Finding` has to name both ends of the join it represents, and
    only the caller can supply the second: `parameters_to_vendor_changes` builds the row and
    the store assigns its id, both of which happen before this detector is constructed.

    Recomputing the id here instead was the tempting shortcut and would have been the bug. The
    store derives it by hashing seven fields of the change, so a copy of that derivation living
    here would be a second implementation of a private key -- correct until the store's hash
    changed, and then silently naming rows that do not exist.
    """

    deprecation: ParameterDeprecation
    vendor_change_id: str


class ParameterDeprecationDetector:
    """Call sites passing a request parameter their vendor no longer honours."""

    detector_id = "parameter-deprecation"

    def __init__(
        self,
        deprecations: Sequence[LinkedDeprecation],
        call_sites: Sequence[CallSite],
    ) -> None:
        self._deprecations = list(deprecations)
        self._call_sites = list(call_sites)
        self.declined: list[str] = []
        """Findings this scan did not raise, each naming its subject and its cause.

        Counted rather than merely skipped. A row this pipeline discards in silence is the
        defect that keeps being found by hand here, and a number is what makes it answerable
        later without re-reading a run's output.

        One decline reaches it here -- a deprecation with no `VendorChange` id established for
        it. The name is the general one because `cli._scan` prints this channel by name for
        every detector that carries it, and a per-detector name table in that file would put
        knowledge of each detector's vocabulary in the one place that must not hold it.
        """

    def scan(self) -> Iterable[Finding]:
        """Every finding, as a list rather than a generator.

        Eager because `declined` is only true once the scan has run, and a generator nobody
        finished consuming would leave the count describing part of the work.
        """
        self.declined = []
        findings: list[Finding] = []

        for site in self._call_sites:
            # A `Finding` addresses its call site by id. Inventing one would produce a finding
            # nothing downstream could resolve back to a location.
            if site.id is None:
                continue

            passed = set(site.args_keys)
            for link in self._deprecations:
                deprecation = link.deprecation
                if deprecation.vendor_id != site.vendor_id:
                    continue
                if deprecation.parameter not in passed:
                    continue
                # The same rule, for the other identifier. `make_locate` resolves
                # `vendor_change_id` and abandons the run when it cannot, so a finding
                # carrying none is a finding that dies -- and one carrying a plausible id
                # rather than an established one is worse, because it survives and produces a
                # patch against a change nobody matched it to.
                if not link.vendor_change_id:
                    self._drop(deprecation, site)
                    continue

                findings.append(
                    Finding(
                        detector=self.detector_id,
                        # The rung names the binding whose wrongness would make this finding
                        # wrong. This detector reads only the static index, so a wrong static
                        # binding is the only thing that could make the claim wrong.
                        binding_rung="static",
                        # The parameter, because that is what the claim is about: this site
                        # passes `model` and the vendor stopped honouring it. Two deprecated
                        # parameters on one call site already resolve to two vendor changes --
                        # `parameters_to_vendor_changes` puts the parameter in `operation_id`,
                        # so the ids differ -- so this does not carry identity on its own. It
                        # says which claim the row is without a join, which is worth having.
                        claim=f"parameter:{deprecation.parameter}",
                        call_site_id=site.id,
                        vendor_change_id=link.vendor_change_id,
                        # Severity carries the confidence. The scope was not evaluated, so
                        # claiming `breaking` would spend trust this finding has not earned.
                        severity="deprecation",
                        rationale=self._rationale(deprecation, site),
                    )
                )

        return findings

    def _drop(self, deprecation: ParameterDeprecation, site: CallSite) -> None:
        reason = (
            f"`{deprecation.parameter}` is passed at {site.path}:{site.line} and no vendor "
            f"change was established for it, so no finding was raised"
        )
        self.declined.append(reason)
        log.warning("parameter-deprecation: %s", reason)

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
