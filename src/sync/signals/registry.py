"""Which adapter serves a vendor id, as data rather than as a name in the entry point.

`CLAUDE.md` states the boundary as a non-negotiable: vendor-specific knowledge lives in
adapters, and the moment core knows a vendor's name the plugin story is dead. A second adapter
existed to prove the interface generalises past Stripe -- and `cli.py` constructed
`StripeAdapter` by name in two places, so no run could reach the second one. What was
unreachable there was not a feature but the claim the project rests on.

What a vendor is handed, and why none of it belongs to one vendor
-----------------------------------------------------------------
`VendorContext` is three things: a directory this deployment stages artifacts in, and the two
version strings `VendorAdapter.fetch_changes` already takes. Nothing in it names a file layout.

That is the constraint worth defending, because the obvious way to re-hardcode is to give this
module a union of every adapter's parameters. `StripeAdapter` takes `spec_dir` and
`symbol_map_path`, one specification at a git tag; `TwilioAdapter` takes a directory per tag and
a list of the products to read out of it. A context carrying either shape would be the vendor
knowledge just removed from `cli.py`, moved one file over -- and the third vendor would add a
third field that two adapters ignore.

So the shapes stay behind the builders. Each builder receives the neutral context and is the one
place that knows what its vendor's artifacts look like.

Staging and loading are two entry points, not a flag
-----------------------------------------------------
`prepare_vendor` stages what a scan needs -- for Stripe that is two specification downloads and
a symbol map derived from them. `load_vendor` builds over what is already staged and reaches no
network, which is what `sync ingest` needs: it reads a cache a previous run produced, and a
fetch there would turn an offline command into an online one on a code path nobody would think
to look at.

An unknown vendor raises
------------------------
Naming what is available, and never falling back. A silent default is how "we support many
vendors" becomes "we support one and lie about it": every run would appear to work and every
finding would describe the wrong API. `sync.index.deps` already refuses to substitute one
package manager for another because a different manager resolves a different tree, and a
different vendor resolves a different API.

What is deliberately not here
-----------------------------
No entry-point discovery and no plugin scan. A third party's adapter is registered by adding a
line to `_BUILDERS`, which is one place and a readable diff. Discovery would be the right shape
once an adapter ships outside this repository and is guesswork until then.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from sync.core.protocols import VendorAdapter
from sync.signals.stripe.adapter import StripeAdapter, fetch_sdk_spec, fetch_spec
from sync.signals.stripe.symbols import build_symbol_map as build_stripe_symbols
from sync.signals.twilio.adapter import ProductDocument, TwilioAdapter
from sync.signals.twilio.symbols import build_symbol_map as build_twilio_symbols

# Where every vendor's symbol map is written, relative to the cache. One name across vendors
# because the map's shape is the same -- symbol to operation metadata -- whatever derived it,
# and `sync ingest` reads it back without knowing which vendor staged it.
SYMBOL_MAP_FILENAME = "symbols.json"

# Where a vendor whose specification is split per product declares which products this
# deployment reads. Named per vendor rather than shared, because a vendor that publishes one
# document has nothing to put in it.
TWILIO_PRODUCTS_FILENAME = "twilio-products.json"


@dataclass(frozen=True)
class VendorContext:
    """Everything a vendor's construction is given, and nothing any one of them needs alone."""

    cache_dir: Path
    from_version: str
    to_version: str


@dataclass(frozen=True)
class PreparedVendor:
    """A staged adapter, and the published documents the staging read.

    `documents` exists because the observed-drift detector compares what a vendor's traffic
    returns against what its specification declares, and only the staging step ever holds the
    parsed document. A vendor publishing one document yields one; a vendor publishing per
    product yields one per product; a vendor whose specification this deployment does not stage
    yields none, which reads downstream as "nothing is declared" rather than as an error.
    """

    adapter: VendorAdapter
    documents: tuple[dict[str, Any], ...]


def _twilio_products(context: VendorContext) -> tuple[ProductDocument, ...]:
    """The products this deployment reads, from the manifest it staged.

    Twilio publishes 61 documents per tag and which of them a customer depends on is a
    scheduling decision the adapter's own docstring declines to make. Nothing in the repository
    ships a default list, so an absent manifest raises naming the path rather than resolving to
    the empty list -- a vendor that silently reports no changes is the failure the product
    exists to catch, arriving from our own side.

    `domain` and `version` come from the manifest rather than from the filename because they are
    not reliably in it: `twilio_iam_organizations.json` carries no version segment, and a split
    on the last underscore would mount every operation in that product under a symbol nobody can
    write.
    """
    manifest = context.cache_dir / TWILIO_PRODUCTS_FILENAME
    if not manifest.exists():
        raise FileNotFoundError(
            f"no product manifest at {manifest}; twilio publishes one specification per product "
            f"and this deployment has not said which of them it reads"
        )
    return tuple(
        ProductDocument(
            filename=entry["filename"], domain=entry["domain"], version=entry["version"]
        )
        for entry in json.loads(manifest.read_text(encoding="utf-8"))
    )


def _load_stripe(context: VendorContext) -> VendorAdapter:
    return StripeAdapter(
        spec_dir=context.cache_dir,
        symbol_map_path=context.cache_dir / SYMBOL_MAP_FILENAME,
    )


def _load_twilio(context: VendorContext) -> VendorAdapter:
    symbol_map = context.cache_dir / SYMBOL_MAP_FILENAME
    return TwilioAdapter(
        spec_dir=context.cache_dir,
        symbol_map_path=symbol_map if symbol_map.exists() else None,
        documents=_twilio_products(context),
    )


def _prepare_stripe(context: VendorContext) -> PreparedVendor:
    """Download both pinned specifications and derive the symbol map from the newer one.

    The generator input names the SDK method for each operation, which is where the map's verbs
    come from when it is published. A tag that publishes none degrades to the HTTP-verb
    derivation rather than abandoning the run, so `sdk_spec` stays None instead of raising.
    """
    cache = context.cache_dir
    fetch_spec(context.from_version, cache / f"{context.from_version}.json")
    head_spec = fetch_spec(context.to_version, cache / f"{context.to_version}.json")

    sdk_spec_path = fetch_sdk_spec(context.to_version, cache / f"{context.to_version}.sdk.json")
    sdk_spec = json.loads(sdk_spec_path.read_text(encoding="utf-8")) if sdk_spec_path else None

    head = json.loads(head_spec.read_text(encoding="utf-8"))
    (cache / SYMBOL_MAP_FILENAME).write_text(
        json.dumps(build_stripe_symbols(head, sdk_spec)), encoding="utf-8"
    )
    return PreparedVendor(adapter=_load_stripe(context), documents=(head,))


def _prepare_twilio(context: VendorContext) -> PreparedVendor:
    """Derive one symbol map across every product this deployment reads.

    Nothing is downloaded. Stripe's specification is one file at a git tag and fetching it is
    three lines; the Twilio equivalent is 61 files per tag, which the adapter's docstring places
    outside an adapter's business. This reads a directory something else populated, and says so
    by failing on a document that is not there.

    One map rather than one per product, because a call site names a symbol and not a product:
    `twilio.<domain>.<version>.<chain>` already carries the product in the symbol itself.
    """
    documents = _twilio_products(context)
    head_dir = context.cache_dir / context.to_version

    symbols: dict[str, dict[str, str]] = {}
    parsed: list[dict[str, Any]] = []
    for document in documents:
        path = head_dir / document.filename
        if not path.exists():
            raise FileNotFoundError(f"specification not found: {path}")
        head = json.loads(path.read_text(encoding="utf-8"))
        parsed.append(head)
        symbols.update(build_twilio_symbols(head, document.domain, document.version))

    (context.cache_dir / SYMBOL_MAP_FILENAME).write_text(
        json.dumps(symbols), encoding="utf-8"
    )
    return PreparedVendor(adapter=_load_twilio(context), documents=tuple(parsed))


_BUILDERS: dict[str, tuple[Callable[[VendorContext], PreparedVendor],
                           Callable[[VendorContext], VendorAdapter]]] = {
    "stripe": (_prepare_stripe, _load_stripe),
    "twilio": (_prepare_twilio, _load_twilio),
}


def available_vendors() -> tuple[str, ...]:
    """Every registered vendor id, sorted. What the command line offers and what an unknown id
    is told about, both read from here so neither can drift from what is actually registered."""
    return tuple(sorted(_BUILDERS))


def _builders(vendor_id: str) -> tuple[Callable, Callable]:
    try:
        return _BUILDERS[vendor_id]
    except KeyError:
        raise KeyError(
            f"no adapter is registered for vendor '{vendor_id}'; "
            f"available: {', '.join(available_vendors())}"
        ) from None


def prepare_vendor(vendor_id: str, context: VendorContext) -> PreparedVendor:
    """Stage what a scan of this vendor needs, and build the adapter over it."""
    return _builders(vendor_id)[0](context)


def load_vendor(vendor_id: str, context: VendorContext) -> VendorAdapter:
    """Build the adapter over artifacts already staged, reaching no network.

    What `sync ingest` needs. It correlates spans against a cache a previous `sync run`
    produced, and a fetch on that path would make an offline command quietly online.
    """
    return _builders(vendor_id)[1](context)
