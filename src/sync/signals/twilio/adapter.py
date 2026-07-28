"""Twilio implementation of the VendorAdapter protocol.

Where this departs from `sync.signals.stripe.adapter`, it departs because the vendor is
shaped differently, and the differences are the point of this module existing.

A Twilio version is a tag, not a file
-------------------------------------
Twilio publishes 61 specification documents at each tag of `twilio/twilio-oai`, one per
product. Stripe publishes one. `VendorAdapter.fetch_changes(from_version, to_version)` takes
two version strings, and for Stripe each names a file; here each names a *directory*, and a
single call has to fan out across every document the caller registered. The protocol still
fits, but only because `from_version` was already opaque to it -- there is no place in the
signature to say which product a change belongs to, which is why the document lands in
`raw` instead.

Nothing here fetches
--------------------
`StripeAdapter` carries `fetch_spec`, because Stripe's specification is one file at a git
tag and downloading it is three lines. The Twilio equivalent is 61 files per tag and a
question about which of them a customer actually depends on, which is a scheduling decision
and not an adapter's business. This adapter reads a directory that something else populated.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from sync.core import OperationRef, VendorChange
from sync.signals.oasdiff import run_oasdiff_breaking, to_vendor_changes

PRODUCT_DOCUMENT_KEY = "sync_product_document"
"""Where a row records which of the vendor's 61 documents produced it.

`VendorChange` has no product axis and the graph keys on `(vendor_id, operation_id)`.
Across the five documents sampled, 155 operation ids collide zero times -- so this is not
repairing a live collision. It is what makes one diagnosable rather than silent, since
nothing Twilio publishes promises that ids are unique across products."""

# Verbatim from `sync.signals.stripe.adapter.NOISE_KINDS`, and the duplication is
# deliberate rather than overlooked. That constant is documented there as "a judgement
# about one vendor's release habits, not a fact about API changes". Measured against
# Twilio's 2.1.0 -> 2.3.0 release it is 76 of 83 records, 92%, against Stripe's roughly
# 80% -- so the judgement holds for a second vendor that shares no tooling with the first,
# and the constant is a fact about `oasdiff` output rather than about either vendor.
#
# It is copied instead of imported because one adapter importing another is the coupling
# the plugin boundary exists to prevent, and it is copied instead of promoted to
# `sync.core` because promoting shared state across packages is not a change one worker
# makes unilaterally. The duplication is the signal; it is reported, not resolved here.
NOISE_KINDS = frozenset({"response-property-enum-value-added"})


@dataclass(frozen=True)
class ProductDocument:
    """One of the vendor's specification documents, and where its operations are mounted.

    `domain` and `version` are configuration rather than derivation. The filename almost
    carries them -- `twilio_insights_v1.json` is `insights` plus `v1` -- but not reliably:
    `twilio_iam_organizations.json` has no version segment at all, so a split on the last
    underscore would name the version `organizations` and mount every operation in that
    product under a symbol nobody can write.
    """

    filename: str
    domain: str
    version: str


class TwilioAdapter:
    """Turns two pinned tags of Twilio's specification repository into VendorChange rows."""

    vendor_id = "twilio"

    def __init__(
        self,
        spec_dir: Path,
        symbol_map_path: Path | str | None,
        documents: Sequence[ProductDocument],
    ) -> None:
        self._spec_dir = Path(spec_dir)
        self._documents = tuple(documents)
        self._symbols: dict[str, dict[str, str]] = (
            json.loads(Path(symbol_map_path).read_text(encoding="utf-8")) if symbol_map_path else {}
        )

    def fetch_changes(self, from_version: str, to_version: str) -> Iterable[VendorChange]:
        """Every breaking change across every registered document, between two tags.

        A missing document raises rather than contributing nothing. An absent file that read
        as "this product changed nothing" is the exact failure the product exists to catch,
        arriving from our own side, and it would be indistinguishable from a quiet release.
        """
        changes: list[VendorChange] = []

        for document in self._documents:
            base = self._spec_dir / from_version / document.filename
            revision = self._spec_dir / to_version / document.filename
            for path in (base, revision):
                if not path.exists():
                    raise FileNotFoundError(f"specification not found: {path}")

            records = [r for r in run_oasdiff_breaking(base, revision) if r.get("id") not in NOISE_KINDS]
            produced = to_vendor_changes(records, self.vendor_id, from_version, to_version)
            for change in produced:
                change.raw[PRODUCT_DOCUMENT_KEY] = document.filename
            changes.extend(produced)

        return changes

    def operation_for_symbol(self, symbol: str) -> OperationRef | None:
        """The operation an SDK call site addressed, or None if the map cannot place it.

        None rather than a guess, for the reason the Stripe adapter gives: an unresolved
        symbol is visibly unresolved and can be counted, where a wrong one produces a
        finding against code that never made the call.
        """
        entry = self._symbols.get(symbol)
        if entry is None:
            return None
        return OperationRef(
            operation_id=entry["operation_id"],
            http_method=entry["http_method"],
            path=entry["path"],
        )
