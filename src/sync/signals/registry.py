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
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

import yaml

from sync.signals.generated.adapter import (
    DEFAULT_GENERATOR,
    CorrelatingGeneratedSpecAdapter,
    GeneratedSpecAdapter,
    http_fetch,
)
from sync.signals.generated.manifest import SpecSource, parse_manifest
from sync.signals.mcp_server.adapter import VENDOR_ID_PREFIX, McpServerAdapter
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

# Which vendors are served by reading a generator's manifest, as a committed file rather than as
# entries in this module. A vendor id appearing in shared code is the knowledge the plugin
# boundary exists to keep out, and a mechanism still needing a line here per vendor would have
# moved that knowledge rather than removed it.
GENERATED_VENDORS_FILE = Path(__file__).resolve().parents[3] / "generated-vendors.yaml"

# A deployment configuring its own set overrides the shipped one. The same shape `corpus_salt`
# uses, and for the same reason: the committed default is right for this repository and wrong to
# impose on a deployment that has its own vendors.
GENERATED_VENDORS_VARIABLE = "SYNC_GENERATED_VENDORS"

# Which MCP servers this deployment watches. Configuration for the same reason generated vendors
# are: MCP is a protocol rather than a vendor, so every server watched is a separate catalogue
# and a builder keyed `mcp` would have to name one particular server -- the vendor knowledge this
# module exists to keep out. A file lets a deployment declare as many as it watches and lets this
# module know none of their names.
MCP_SERVERS_FILE = Path(__file__).resolve().parents[3] / "mcp-servers.yaml"
MCP_SERVERS_VARIABLE = "SYNC_MCP_SERVERS"

# Where a watched server's captures live when an entry does not say. Under the cache because it
# is the directory a deployment already stages artifacts in, and per server id because two
# servers' captures share a filename -- `tools_list_<capture>.json` -- and would otherwise
# overwrite each other.
MCP_SNAPSHOT_DIRNAME = "mcp-snapshots"

# The two network calls the generated path makes, held as module attributes so a test can replace
# either without replacing the other. They are separate because the distinction is the economic
# claim: reading two manifests is meant to happen on every scan, and fetching two specifications
# is what an unmoved hash is supposed to avoid. One injection point could not tell them apart.
fetch_manifest = http_fetch
fetch_specification = http_fetch

_RAW_CONTENT = "https://raw.githubusercontent.com/{repo}/{ref}/{path}"

log = logging.getLogger(__name__)


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


@dataclass(frozen=True)
class GeneratedVendor:
    """One vendor served by reading the manifest its SDK generator commits.

    Three fields, and none of them is knowledge about the vendor's API: which repository the
    generated SDK lives in, and which convention's manifest to read out of it. Everything about
    the specification itself comes from the manifest, which is what makes adding a vendor under
    a supported generator a configuration entry rather than a module.
    """

    vendor_id: str
    repo: str
    manifest: str
    sdk_bindings: Mapping[str, Mapping[str, str]] = field(default_factory=dict)
    """Which package a customer imports to reach this vendor, per language.

    A packaging fact, not knowledge about the vendor's API, which is why it sits beside the
    other three. Optional: a vendor declaring none falls back to a guess derived from its id,
    and `sync.signals.generated.adapter.bindings_for` carries why that is safe and where it
    stops.
    """


def _generated_vendors() -> dict[str, GeneratedVendor]:
    """Every configured generated-SDK vendor, keyed by id.

    An absent file is no configured vendors, which is a legitimate deployment -- the two
    hand-written adapters still resolve. A file that is present and unreadable raises naming the
    path, because a deployment that configured vendors and silently got none would report a
    quiet scan across every one of them, and quiet is indistinguishable from healthy.
    """
    path = Path(os.environ.get(GENERATED_VENDORS_VARIABLE) or GENERATED_VENDORS_FILE)
    if not path.exists():
        return {}

    entries = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(entries, list):
        raise ValueError(f"{path} does not hold a list of generated-SDK vendors")

    try:
        configured = [
            GeneratedVendor(
                vendor_id=entry["vendor_id"], repo=entry["repo"], manifest=entry["manifest"],
                sdk_bindings=entry.get("sdk_bindings") or {},
            )
            for entry in entries
        ]
    except (KeyError, TypeError) as exc:
        raise ValueError(
            f"{path}: every entry needs vendor_id, repo and manifest ({exc})"
        ) from None
    return {vendor.vendor_id: vendor for vendor in configured}


@dataclass(frozen=True)
class WatchedServer:
    """One MCP server this deployment watches, and nothing about what it advertises.

    Two fields. `server_id` is the identity the operator declares, and `snapshot_dir` is where
    that server's captures are kept.

    **The id is declared, never derived.** Nothing about the server produces it -- not the URL,
    not the host, not the name the server gives itself in its own initialise response. That is
    what makes it survive the server moving: an endpoint change is not an identity change, and
    a vendor id derived from a URL would silently orphan every row written before the move.
    Two servers cannot collide into one id because a repeated id is refused rather than resolved.

    There is no endpoint here, and its absence is the honest state of this path rather than an
    oversight. Nothing in this repository captures a `tools/list` yet; the adapter reads captures
    something else took. A field naming where to reach a server would be configuration nothing
    reads, and the capture step that needs it will know what shape it wants.
    """

    server_id: str
    snapshot_dir: str | None = None


def _read_mcp_servers(path: Path) -> dict[str, WatchedServer]:
    """Every watched server a file declares, keyed by the vendor id it resolves to.

    Keyed by the prefixed id -- `mcp:<server_id>` -- because that is what `--vendor` selects and
    what every row is keyed by. The prefix comes from the adapter, so this module composes an id
    it never spells: `VENDOR_ID_PREFIX` is a fact about the protocol and lives with the code that
    knows the protocol.
    """
    entries = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if not isinstance(entries, list):
        raise ValueError(f"{path} does not hold a list of watched MCP servers")

    servers: dict[str, WatchedServer] = {}
    for entry in entries:
        try:
            declared = entry.get("snapshot_dir")
            server = WatchedServer(
                server_id=entry["server_id"],
                # Relative to the file that declared it, not to whatever directory the process
                # happens to be started in. A deployment keeps its captures beside its
                # configuration, and a path resolved against the working directory would mean
                # something different for `sync run` in a repository and for the same
                # configuration read by a scheduled job.
                snapshot_dir=str(path.parent / declared) if declared else None,
            )
        except (KeyError, TypeError) as exc:
            raise ValueError(f"{path}: every entry needs a server_id ({exc})") from None

        vendor_id = VENDOR_ID_PREFIX + server.server_id
        if vendor_id in servers:
            # Two catalogues writing one history, with the later entry silently winning. Every
            # row is keyed by vendor id, so nothing downstream could separate them again.
            raise ValueError(f"{path}: server_id '{server.server_id}' is declared twice")
        servers[vendor_id] = server
    return servers


def _mcp_servers() -> dict[str, WatchedServer]:
    """The configured servers, from the deployment's file or the shipped one.

    An absent file is zero watched servers, which is a legitimate deployment and is what the
    shipped file describes: watching a server means holding its captures, and nothing here takes
    them yet.
    """
    path = Path(os.environ.get(MCP_SERVERS_VARIABLE) or MCP_SERVERS_FILE)
    if not path.exists():
        return {}
    return _read_mcp_servers(path)


def _load_mcp_server(server: WatchedServer, context: VendorContext) -> VendorAdapter:
    """Build over captures already on disk. Nothing is fetched, here or in `prepare`.

    A watched server inverts what preparation means everywhere else. For a REST vendor, staging
    downloads the artifact a scan reads; here the artifact is a capture something else took, and
    it cannot be re-fetched at all -- a server answers for its present state and has no way to
    say what it advertised in June. So both entry points build the same adapter, and neither
    reaches a network.
    """
    snapshot_dir = (
        Path(server.snapshot_dir)
        if server.snapshot_dir
        else context.cache_dir / MCP_SNAPSHOT_DIRNAME / server.server_id
    )
    return McpServerAdapter(snapshot_dir=snapshot_dir, server_id=server.server_id)


def _prepare_mcp_server(server: WatchedServer, context: VendorContext) -> PreparedVendor:
    """No documents. `documents` carries a parsed specification for the drift detector, and a
    server publishes none -- what it advertises is a tool list, which is not the same artifact
    and is not what that detector compares against."""
    return PreparedVendor(adapter=_load_mcp_server(server, context), documents=())


def _spec_source(vendor: GeneratedVendor, ref: str) -> SpecSource:
    """What the vendor's manifest says about its specification at one commit of the SDK.

    Both failures raise naming the repository and the path, and neither resolves to a default.
    `parse_manifest` answering None is deliberate -- one vendor's broken manifest must not abort
    a scan across the others -- but this vendor was asked for by name, so None means it cannot be
    served, and the silent fallback is what `_builders` already refuses for an unknown id.

    A fetch failure is the same judgement from the other direction: an outage that read as "this
    vendor published nothing" is the exact failure the product exists to catch, arriving from our
    own side.
    """
    url = _RAW_CONTENT.format(repo=vendor.repo, ref=ref, path=vendor.manifest)
    try:
        body = fetch_manifest(url)
    except Exception as exc:
        raise RuntimeError(
            f"{vendor.repo} manifest {vendor.manifest} at {ref} could not be retrieved "
            f"({url}): {exc}"
        ) from exc

    source = parse_manifest(vendor.manifest, body)
    if source is None:
        raise ValueError(
            f"{vendor.repo} manifest {vendor.manifest} at {ref} names no usable specification "
            f"({url})"
        )
    return source


def _prepare_generated(vendor: GeneratedVendor, context: VendorContext) -> PreparedVendor:
    """Read both manifests and build over them. No specification is fetched here.

    That is the whole economic argument and it is easy to lose at exactly this point. A manifest
    is a text file in a public repository, so reading two of them is the cost of asking whether
    the specification moved; a specification is megabytes, and only a vendor whose hash actually
    moved should pay for two of those. Staging them here -- which is what `prepare_vendor` does
    for a hand-written vendor -- would pay that cost before anything consulted the hash, and
    every assertion about the hash would still pass, because the fetch would simply have happened
    earlier.

    `documents` is empty for the same reason. It carries the parsed specification for the drift
    detector, and holding one would mean having downloaded it.
    """
    sources = {
        context.from_version: _spec_source(vendor, context.from_version),
        context.to_version: _spec_source(vendor, context.to_version),
    }

    if not sources[context.to_version].has_cheap_change_trigger:
        # The one place this is knowable and worth saying. A configured vendor whose manifest
        # publishes no hash cannot be asked whether its specification moved, so `changed_from`
        # answers "changed" and every scan pays for two specification fetches -- correct, and
        # the opposite of the economics that justify configuring many vendors. Nothing
        # downstream can tell that from a vendor that genuinely changes every time.
        log.info(
            "%s: %s publishes no specification hash, so every scan pays for a fetch rather "
            "than a comparison",
            vendor.vendor_id, vendor.manifest,
        )

    sdk_source = context.cache_dir / "sdk_source"
    sdk_source_path = sdk_source if sdk_source.exists() else None
    generator_file = context.cache_dir / "sdk_generator.txt"
    generator = generator_file.read_text(encoding="utf-8").strip() if generator_file.exists() else DEFAULT_GENERATOR
    adapter_cls = CorrelatingGeneratedSpecAdapter if sdk_source_path is not None else GeneratedSpecAdapter

    return PreparedVendor(
        adapter=adapter_cls(
            vendor_id=vendor.vendor_id,
            sources=sources,
            fetch=fetch_specification,
            cache_dir=context.cache_dir,
            sdk_bindings=vendor.sdk_bindings,
            sdk_source=sdk_source_path,
            sdk_source_generator=generator,
        ),
        documents=(),
    )


def _load_generated(vendor: GeneratedVendor, context: VendorContext) -> GeneratedSpecAdapter:
    """The same adapter with nothing read, because `load_vendor` promises to reach no network.

    It answers `fetch_changes` with nothing and says so in the log, which is the adapter's own
    designed behaviour for a version it has no manifest for. When an SDK source checkout is staged,
    it returns `CorrelatingGeneratedSpecAdapter` which satisfies `RequestCorrelator` and correlates
    observed HTTP spans against extracted SDK routes.
    """
    sdk_source = context.cache_dir / "sdk_source"
    sdk_source_path = sdk_source if sdk_source.exists() else None
    generator_file = context.cache_dir / "sdk_generator.txt"
    generator = generator_file.read_text(encoding="utf-8").strip() if generator_file.exists() else DEFAULT_GENERATOR
    adapter_cls = CorrelatingGeneratedSpecAdapter if sdk_source_path is not None else GeneratedSpecAdapter

    return adapter_cls(
        vendor_id=vendor.vendor_id,
        sources={},
        fetch=fetch_specification,
        cache_dir=context.cache_dir,
        sdk_bindings=vendor.sdk_bindings,
        sdk_source=sdk_source_path,
        sdk_source_generator=generator,
    )




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

# The adapter class behind each coded vendor, so a caller can read what the adapter *declares*
# without constructing one. `sync.signals.intake` needs the SDK package a vendor is imported as
# in order to match it against a customer's manifest, and constructing an adapter to ask is the
# wrong shape twice over: it reads files a scan has not staged yet -- `_load_twilio` raises
# without a product manifest -- and it does IO to answer a question about configuration.
#
# Naming the classes is this module's job and nowhere else's; `sync/signals/__init__.py` states
# that as the rule. Keyed the same way `_BUILDERS` is, and
# `test_every_coded_adapter_is_offered_a_binding_lookup` holds the two in step -- an adapter
# added to one and not the other would silently stop being matchable against a manifest.
_CODED_ADAPTERS: dict[str, type] = {
    "stripe": StripeAdapter,
    "twilio": TwilioAdapter,
}


def vendor_sdk_bindings() -> dict[str, dict[str, dict[str, str]]]:
    """Which package each vendor is imported as, for the vendors whose adapter says.

    Only coded adapters appear. A configured vendor is served by `GeneratedSpecAdapter` or
    `McpServerAdapter`, and neither declares a binding: their specifications are discoverable
    and their call sites are not, so they resolve through this registry and can bind nothing.
    That is a real gap rather than an omission here, and `sync.signals.intake` reports it as
    the missing configuration it is instead of hiding it behind a vendor that appears served.
    """
    return {
        vendor_id: dict(getattr(adapter, "sdk_bindings", {}))
        for vendor_id, adapter in _CODED_ADAPTERS.items()
        if getattr(adapter, "sdk_bindings", None)
    }


def configured_generated_repos() -> dict[str, str]:
    """The SDK repository each configured generated vendor is registered against, by repo.

    Keyed by repository rather than by vendor id because that is the join a caller can make:
    `sync.signals.intake` holds confirmed evidence of which repository a package's SDK is
    generated from, and matching repository to repository needs neither side to guess that a
    package name resembles a vendor id. Scoped package names are why -- one can be generated from
    a configured repository while resembling nothing about the vendor -- and `intake.py` carries
    the worked example, because naming a configured vendor here is the knowledge this module is
    built to keep out.

    Exact, so it is per-repository rather than per-vendor. A deployment configured against one
    language's SDK does not answer for another's, which is the true state of the configuration
    rather than a limitation of the lookup.
    """
    return {vendor.repo: vendor.vendor_id for vendor in _generated_vendors().values()}


def available_vendors() -> tuple[str, ...]:
    """Every registered vendor id, sorted -- coded and configured alike.

    What the command line offers and what an unknown id is told about, both read from here so
    neither can drift from what is actually registered. Configuration is included because a
    configured vendor the parser refuses is registered and unreachable, which is the shape of
    defect this whole path exists to close.
    """
    return tuple(sorted({*_BUILDERS, *_generated_vendors(), *_mcp_servers()}))


@dataclass(frozen=True)
class RegisteredAdapter:
    """One registered vendor, as configuration rather than as a constructed adapter.

    Three fields, and the reason for each is that a reader wants to know what serves a vendor
    without paying for it. `kind` is which of the three routes registered it; `source` is the one
    thing about that route worth naming on a screen -- the repository a generated vendor's
    manifest is read from, the directory an MCP server's captures are kept in -- and is `None` for
    a coded adapter, whose source is this repository.

    Nothing here constructs an adapter or reads a staged artifact. `_load_twilio` raises without a
    product manifest, so a reader that built one to ask what it is would report a deployment as
    broken for the ordinary state of having not scanned yet.
    """

    vendor_id: str
    kind: str
    """`coded`, `generated` or `mcp`."""
    source: str | None


def registered_adapters() -> tuple[RegisteredAdapter, ...]:
    """Every registered vendor with what registered it, sorted by id.

    Sorted because the caller is a table and an unstable order is a diff on every render.

    Held against `available_vendors` by `test_every_registered_id_is_one_the_command_line_would_
    accept`: two lists of registered vendors that can disagree is the defect this module's
    `_CODED_ADAPTERS` comment already names, and here it would surface as a row for an adapter no
    run can select.
    """
    entries = [
        RegisteredAdapter(vendor_id=vendor_id, kind="coded", source=None) for vendor_id in _BUILDERS
    ]
    entries += [
        RegisteredAdapter(vendor_id=vendor.vendor_id, kind="generated", source=vendor.repo)
        for vendor in _generated_vendors().values()
    ]
    entries += [
        RegisteredAdapter(vendor_id=vendor_id, kind="mcp", source=server.snapshot_dir)
        for vendor_id, server in _mcp_servers().items()
    ]
    return tuple(sorted(entries, key=lambda entry: entry.vendor_id))


def _builders(vendor_id: str) -> tuple[Callable, Callable]:
    """The staging and loading pair for a vendor, coded first and configured second.

    Coded first so a configuration entry cannot shadow a hand-written adapter. A vendor with a
    hand-written adapter has it for a reason -- a symbol scheme the generated path deliberately
    declines to guess at -- and a configuration file quietly replacing it would swap a resolving
    adapter for one that answers `operation_for_symbol` with None every time, which produces no
    findings and reports no fault.
    """
    if vendor_id in _BUILDERS:
        return _BUILDERS[vendor_id]

    vendor = _generated_vendors().get(vendor_id)
    if vendor is not None:
        return (
            lambda context: _prepare_generated(vendor, context),
            lambda context: _load_generated(vendor, context),
        )

    server = _mcp_servers().get(vendor_id)
    if server is not None:
        return (
            lambda context: _prepare_mcp_server(server, context),
            lambda context: _load_mcp_server(server, context),
        )

    raise KeyError(
        f"no adapter is registered for vendor '{vendor_id}'; "
        f"available: {', '.join(available_vendors())}"
    )


def prepare_vendor(vendor_id: str, context: VendorContext) -> PreparedVendor:
    """Stage what a scan of this vendor needs, and build the adapter over it."""
    return _builders(vendor_id)[0](context)


def load_vendor(vendor_id: str, context: VendorContext) -> VendorAdapter:
    """Build the adapter over artifacts already staged, reaching no network.

    What `sync ingest` needs. It correlates spans against a cache a previous `sync run`
    produced, and a fetch on that path would make an offline command quietly online.
    """
    return _builders(vendor_id)[1](context)
