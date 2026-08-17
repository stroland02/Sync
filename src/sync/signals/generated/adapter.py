"""A `VendorAdapter` driven by a generated SDK's manifest rather than by hand-written knowledge.

`manifest.py` reads the file a generator commits; this turns what it read into `VendorChange`
rows. The point, argued in `docs/superpowers/specs/2026-07-27-sync-adapter-targets.md`, is that
coverage should scale with generator count rather than vendor count: supporting a generator costs
a day and yields every vendor using it, while supporting one more vendor under a known generator
costs a configuration line.

The cheap trigger is the economics
----------------------------------
A Stainless manifest publishes `openapi_spec_hash`. Comparing that string across two commits of
the SDK repository is free -- it is a text file in a public repository -- and it answers "did the
specification move" without downloading anything. Only a vendor whose hash actually moved pays
for two spec fetches and an oasdiff run. A vendor whose hash is unchanged costs nothing at all,
which is what makes polling many vendors affordable rather than an idea about polling many
vendors.

Unknown reads as changed, never as unchanged. A manifest with no hash on either side says nothing
about whether the spec moved, and answering "unchanged" there would silently skip that vendor
forever with nothing to surface it. Paying for a fetch that finds nothing is the cheap mistake.

What this adapter cannot reach
------------------------------
Several real manifests -- Cloudflare's and Orb's among them -- publish `configured_endpoints` and
no URL at all. `SpecSource.is_fetchable` reports that, and such a vendor yields no changes and is
logged rather than raising: it still needs a hand-written adapter, and it must not abort a scan
across every other vendor. It is not an error, and it is not silence either.

A second shape reaches the same wall from the other side. A manifest may name a live, unversioned
endpoint -- the location the generator resolved when it ran -- and a vendor serving its current
specification there publishes the same string in every commit. Both ends of a version pair then
fetch the same bytes, so the differ compares a document against itself and reports nothing however
much the vendor shipped. That is a coverage failure wearing the costume of a clean bill of health,
and `2026-07-29-vercel-observability.md` measured it: two fetches of one such endpoint three
seconds apart returned identical bytes and diffed to zero records.

Not looking is not the same as finding nothing
----------------------------------------------
Those two, plus a version whose manifest did not parse, are three ways of answering `fetch_changes`
with an empty list that mean "we could not look" -- and an unmoved hash is a fourth that means "we
looked and nothing moved". A caller holding only the list cannot tell them apart, which is exactly
the silent-vendor failure `_spec` refuses to accept from a fetch outage, arriving instead from the
shape of our own return value. `observability` is where that question is answered, and it carries a
reason because the three are three different repairs.

**The condition is a property of the locations, never of the vendor or the generator that wrote
them.** Speakeasy names a live endpoint for one vendor and a tagged registry revision for another;
a Stainless manifest whose `openapi_spec_url` stopped rotating would be in the same position and is
reported the same way. A vendor id in this path is the knowledge the plugin boundary exists to keep
out, and it would also be wrong -- the vendor is not what makes the pair unobservable.

Which artifact the diff was taken from
--------------------------------------
`openapi_spec_url` points at the generator's own storage rather than the vendor's host. That is
sound as a change *hint* and weaker as evidence, so a vendor-published URL is preferred where the
caller supplies one, and every row records which was used under `sync_spec_provenance`. The
oasdiff record underneath is untouched -- `raw` is what lets a better extractor re-derive against
stored history instead of re-fetching every spec pair.

A manifest reporting overlays is diffed anyway. The fetched spec is then not byte-identical to
what the generator consumed, but both sides of the diff get the same treatment, so a comparison
between two fetches stays sound; only comparing a spec against the SDK would not be.

Why no noise filter
-------------------
Both hand-written adapters drop `response-property-enum-value-added`, and this one drops nothing.
That asymmetry is measured rather than overlooked: `2026-07-29-generated-vendor-noise.md` ran the
pinned differ over the configured vendors' own specification pairs and found the kind carries their
findings rather than burying them. It is the sole route to 28 of 31 affected operations across one
OpenAI window and to all three across another, so a vendor filtering it would report a real release
as no change at all -- the silent-vendor failure `_spec` refuses to accept from a fetch outage,
arriving instead from our own filter. Volume does not argue for it either: the widest window
measured produced 424 records against Stripe's hundreds of thousands.

Anything proposing to filter here has to be measured against the vendor it would apply to, and
because one code path serves every configured vendor, a constant would apply one vendor's answer to
all of them. `tests/test_generated_adapter_noise.py` holds the decision.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Mapping

from sync.core import OperationRef, VendorChange
from sync.signals.generated import symbols as stainless_python
from sync.signals.generated import symbols_speakeasy as speakeasy_typescript
from sync.signals.generated import symbols_typescript as stainless_typescript
from sync.signals.generated.manifest import SpecSource
from sync.signals.generated.symbols import ExtractedOperation, read_spec_operations
from sync.signals.oasdiff import run_oasdiff_breaking, to_vendor_changes

log = logging.getLogger(__name__)

Fetch = Callable[[str], str]

EXTRACTORS = {
    module.GENERATOR: module
    for module in (stainless_python, stainless_typescript, speakeasy_typescript)
}
"""Which rule reads a staged SDK, by the generator and language that emitted it.

Keyed by generator *times language*, because that is the unit an extraction rule covers. Stainless
writes the route as a positional literal in Python and as a tagged template in TypeScript, so
"Stainless" names two rules rather than one, and a deployment says which of them its staged
checkout needs.
"""

DEFAULT_GENERATOR = stainless_python.GENERATOR
"""What a deployment that stages an SDK and names no generator gets.

The first flavour written, kept as the default so callers predating the second keep the behaviour
they had. Naming it wrongly is not a silent failure: each rule raises `UnrecognisedSdkShape` on
the other's source rather than returning the part of it that happens to parse.
"""

PROVENANCE_KEY = "sync_spec_provenance"
"""Where a row records which artifact it was diffed from. Namespaced because it sits beside
oasdiff's own record rather than in it."""

VENDOR_PUBLISHED = "vendor"
GENERATOR_MIRROR = "generator-mirror"

NO_MANIFEST = "no-manifest"
NO_SPECIFICATION = "no-specification"
ONE_DOCUMENT = "one-document"


@dataclass(frozen=True)
class Observability:
    """Whether a version pair can be compared at all, and what stopped it if not.

    `fetch_changes` answers with an empty list for four unrelated reasons, three of which mean
    "we could not look" and one of which means "we looked and nothing moved". A caller holding
    only the list cannot tell them apart -- which is the silent-vendor failure `_spec` refuses
    to accept from a fetch outage, arriving instead from the shape of our own return value.

    The three reasons are three different repairs, which is why the code is carried rather than
    a bare boolean: `NO_MANIFEST` wants a version that parses, `NO_SPECIFICATION` wants a
    hand-written adapter, and `ONE_DOCUMENT` wants a versioned location per version.
    """

    observable: bool
    reason: str | None = None
    detail: str = ""


OBSERVABLE = Observability(observable=True)


def bindings_for(
    vendor_id: str, declared: Mapping[str, Mapping[str, str]] | None
) -> dict[str, dict[str, str]]:
    """Which package a customer imports to reach this vendor, per language.

    A configured vendor whose bindings nobody wrote still gets a guess derived from its id, and
    a configured vendor who declared any binding gets exactly what was declared.

    **The fallback is defensible because a wrong derivation fails to resolve rather than
    resolving wrongly.** The manifest declares no package by the guessed name, the match returns
    false, and nothing binds. It cannot bind to the wrong vendor, because a symbol rooted at the
    wrong name is in no vendor's map. That is what keeps the coverage argument intact -- adding
    a vendor costs a configuration line -- without the guess being able to produce a confident
    wrong answer.

    **A vendor that declared bindings has spoken completely, and a declared mapping missing a
    language yields no binding for that language.** Topping one up would restore the guess one
    level above where it was removed, and the vendor with a `@scope/name` package is exactly the
    vendor for whom the guess is wrong. Anthropic is that case in one vendor: its PyPI
    distribution is `anthropic`, so a derivation resolves, and its npm package is
    `@anthropic-ai/sdk`, so the same derivation fails. A binding is per-language, and a default
    that is right for one language and wrong for the other cannot be rescued by being cleverer
    about deriving it.

    The per-language shape belongs to the language adapter that reads it rather than to a schema
    stated here, which is why this copies rather than validates -- see
    `StripeAdapter.sdk_bindings`. TypeScript needs one npm name, which is both the manifest key
    and the import specifier; Python needs two, because a distribution name and a module name
    are different strings in general.
    """
    if declared:
        return {language: dict(fields) for language, fields in declared.items()}
    return {
        "typescript": {"package": vendor_id},
        "python": {"distribution": vendor_id, "module": vendor_id},
    }


def http_fetch(url: str, timeout: float = 60.0) -> str:
    """A plain GET returning decoded text. The default `Fetch` for real runs.

    `urllib` rather than a dependency, and the decode is explicit because the platform default
    is the locale codepage on Windows and a specification is full of non-ASCII descriptions.

    Tests never call this -- they inject their own fetch -- which is what keeps the suite free of
    network access.
    """
    import urllib.request

    request = urllib.request.Request(url, headers={"User-Agent": "sync-generated-adapter"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - caller-supplied https URLs
        return response.read().decode("utf-8")


class GeneratedSpecAdapter:
    """Turns two commits of a generated SDK's manifest into the vendor changes between them."""

    def __init__(
        self,
        vendor_id: str,
        sources: Mapping[str, SpecSource],
        fetch: Fetch,
        cache_dir: Path | str,
        vendor_spec_urls: Mapping[str, str] | None = None,
        sdk_bindings: Mapping[str, Mapping[str, str]] | None = None,
        sdk_source: Path | str | None = None,
        sdk_spec_operations: Path | str | None = None,
        sdk_source_generator: str = DEFAULT_GENERATOR,
    ) -> None:
        self._vendor_id = vendor_id
        self._sources = sources
        self._fetch = fetch
        self._cache_dir = Path(cache_dir)
        self._vendor_spec_urls = vendor_spec_urls or {}
        self._sdk_bindings = bindings_for(vendor_id, sdk_bindings)
        # A checkout of this vendor's generated SDK, when the deployment has staged one. Absent
        # is the ordinary case and answers nothing rather than guessing -- see
        # `operation_for_symbol`.
        self._sdk_source = Path(sdk_source) if sdk_source else None
        # The specification's operation set, when this deployment staged one beside the source.
        # Its absence costs the cross-check, not the map: extraction still answers, and the
        # disagreement it would have surfaced simply is not looked for.
        self._sdk_spec_operations = Path(sdk_spec_operations) if sdk_spec_operations else None
        # Rejected here rather than on first lookup. A misconfigured deployment must fail while
        # someone is looking at it, not on the run where a symbol quietly stops resolving.
        if sdk_source_generator not in EXTRACTORS:
            raise ValueError(
                f"{vendor_id}: no extraction rule for {sdk_source_generator!r}; "
                f"this deployment can read {', '.join(sorted(EXTRACTORS))}"
            )
        self._extractor = EXTRACTORS[sdk_source_generator]
        self._symbols: dict[str, ExtractedOperation] | None = None

    @property
    def vendor_id(self) -> str:
        return self._vendor_id

    @property
    def sdk_bindings(self) -> dict[str, dict[str, str]]:
        """Read by `sync.index` through `getattr`, which is why this is not a protocol member.

        Until it existed the four vendors `generated-vendors.yaml` configures resolved through
        the registry and matched nothing in a customer's repository: their specifications were
        diffable and their call sites were not. `bindings_for` carries the rule that decides
        what this holds.

        It makes a repository *match* this vendor and makes the indexer look for its client. It
        does not make a call site resolve: `operation_for_symbol` answers `None` by design, and
        both indexers skip a call whose symbol resolves to nothing. A configured vendor still
        needs a symbol scheme from somewhere before it yields a finding, and that is the next
        gap rather than this one -- `unbindable_reason` is where it is declared, so a run that
        can bind nothing reports it instead of counting zero.
        """
        return self._sdk_bindings

    @property
    def unbindable_reason(self) -> str | None:
        """Why no call site in any repository can bind to this vendor, or `None` if one can.

        `operation_for_symbol` answering `None` is per symbol and is an ordinary answer -- a
        chain the SDK does not state resolves to nothing and should. This is the other quantity:
        whether *any* symbol could have resolved. Without a staged checkout the map is never
        built, so every call site declines, and a repository that calls this vendor produces the
        same output as one that has never heard of it. The caller reporting a count needs the
        difference, and holding only the count it cannot recover it.

        Derived from what this instance was given rather than from which vendor it serves. The
        four vendors `generated-vendors.yaml` configures are in this state today and none of them
        is named here or anywhere upstream; staging a checkout for one of them retires it for that
        one, with no edit to this property.

        Read through `getattr` at the boundary the way `sdk_bindings` and
        `LanguageAdapter.unverifiable_reason` are, so `VendorAdapter` does not widen and a third
        party's adapter written before this existed goes on running unqualified. Silence is the
        ordinary case in the same direction those take: an adapter that binds says nothing, and a
        gap is something an adapter asserts.
        """
        if self._sdk_source is not None:
            return None
        return (
            "no checkout of this vendor's generated SDK is staged, so no symbol map was built "
            "and every call site resolves to nothing"
        )

    @property
    def uncorrelatable_reason(self) -> str | None:
        """Why observed HTTP telemetry cannot correlate back to an operation for this vendor.

        `RequestCorrelator` requires an authoritative URL route template mapping. Generated
        adapters build route templates from SDK source checkouts when staged; without staged source,
        observed HTTP telemetry cannot be correlated.
        """
        return (
            f"vendor '{self._vendor_id}' is served by GeneratedSpecAdapter with no staged SDK "
            f"source, so no route map was built; observed HTTP telemetry cannot be correlated"
        )

    def operation_for_symbol(
        self, symbol: str, *, language: str | None = None
    ) -> OperationRef | None:
        """`None` unless this deployment staged the SDK's own source, and then what it says.

        The original refusal stands and is worth restating, because this does not overturn it:
        mapping `acme.charges.create` onto an operation by *inventing* a convention would put
        per-vendor knowledge back as a guess that fails silently -- an unresolvable symbol yields
        no finding, so nobody would learn the convention was wrong. Nothing here is invented.

        What changed is that the answer was available all along in an artifact nobody was
        reading. A generated SDK writes the HTTP method and path into the source that makes the
        call, so `sync.signals.generated.symbols` reads them out of it rather than proposing
        them -- and the source cannot be wrong about what it sends, because it is the thing that
        sends it. Where extraction finds a shape it does not recognise it raises rather than
        answering partially, so a resolved symbol is one the SDK really states.

        Without `sdk_source` the answer is still `None`, unchanged and for the original reason.
        A vendor whose SDK this deployment has not staged has nothing to read, and guessing is
        the thing being avoided rather than the thing being deferred.

        `language` is accepted and ignored. An extraction rule covers a generator *times* a
        language and is named as one string, `sdk_source_generator`, chosen where the checkout is
        staged. Selecting it from the caller's language instead would mean deciding that
        `typescript` implies Stainless, which is the kind of convention this module refuses.
        """
        symbols = self._extracted_symbols()
        if symbols is None:
            return None

        root = f"{self._vendor_id}."
        chain = symbol[len(root):] if symbol.startswith(root) else symbol
        found = symbols.get(chain)
        if found is None:
            return None
        return OperationRef(
            # No operationId: the SDK states a route, not the specification's name for it. The
            # route is what a change is matched on, and inventing an id would be the guess this
            # module refuses in the paragraph above.
            operation_id=f"{found.http_method} {found.path}",
            http_method=found.http_method.lower(),
            path=found.path,
        )

    def _extracted_symbols(self) -> dict[str, ExtractedOperation] | None:
        """The map, read once, cross-checked against the specification where one is staged.

        The cross-check runs here rather than in a reporting command, because here is where the
        map is built and here is the only moment the disagreement is knowable. Coverage is logged
        with its denominator attached -- "extracted 180 operations" says nothing, and the Stripe
        map's 105 of 414 means something only because the second number travels with it.

        An operation the specification does not declare is **logged, not dropped**. The SDK is
        what runs, so a route it states is a route the customer's process will send whatever the
        specification says; discarding it would make a misread source indistinguishable from a
        vendor that genuinely lacks that route, which is the distinction the check exists to
        draw. What the log gives an operator is the pair to go and reconcile.

        A construct the rule could not read is surfaced on **both** paths, because a decline is a
        property of the source rather than of whether a specification was staged, and without a
        specification there is no coverage line for it to travel in.
        """
        if self._sdk_source is None:
            return None
        if self._symbols is None:
            if self._sdk_spec_operations is not None:
                report = self._extractor.report_extraction(
                    self._sdk_source, read_spec_operations(self._sdk_spec_operations)
                )
                log.info("%s: %s", self._vendor_id, report.render())
                for operation in report.unknown_to_spec:
                    log.warning(
                        "%s: %s reads %s %s, which the specification does not declare",
                        self._vendor_id, operation.symbol, operation.http_method, operation.path,
                    )
                extracted, unreadable = report.operations, report.unreadable
            else:
                extracted, unreadable = self._extractor.extract_symbols(self._sdk_source)
            self._report_unreadable(unreadable)
            self._symbols = {operation.symbol: operation for operation in extracted}
        return self._symbols

    def _report_unreadable(self, unreadable: tuple[str, ...]) -> None:
        """The count once at warning, each record one level below it.

        A decline means the map is smaller than the SDK, which is the false negative this whole
        approach exists to avoid, so silence is wrong. Warning **per record** is also wrong: the
        committed `vercel/sdk` tree produces 48 on every extraction because it is a deliberately
        partial checkout, and a vendor emitting 48 warnings per scan is how a reader learns to
        filter this logger out. So the count is one warning an operator cannot miss and the
        records are `info`, where whoever goes looking will find them.

        That is deliberately the opposite balance from `unknown_to_spec`, which warns per entry.
        That channel reports two independently derived artifacts disagreeing -- evidence one of
        them is wrong, and each entry is its own reconciliation. This one reports a limit of our
        own rule against a checkout, where the count is the finding and the records are the
        detail.
        """
        if not unreadable:
            return
        log.warning(
            "%s: %d constructs the %s rule could not read",
            self._vendor_id, len(unreadable), self._extractor.GENERATOR,
        )
        for record in unreadable:
            log.info("%s: %s", self._vendor_id, record)

    def observability(self, from_version: str, to_version: str) -> Observability:
        """Whether this pair can be compared, asked before anything is downloaded.

        The order is the argument. A hash agreeing on both sides is positive evidence that the
        specification did not move, and evidence is an answer: that pair was examined and found
        unchanged, however few documents back it. Only once the cheap trigger has failed to
        settle the question does where the documents live start to matter.

        The location check is asked of what a run will actually fetch rather than of what the
        manifest said, so a deployment supplying a versioned URL per version restores a vendor
        its manifest cannot describe -- with no code change and no entry naming that vendor.
        """
        base = self._sources.get(from_version)
        head = self._sources.get(to_version)

        if base is None or head is None:
            missing = from_version if base is None else to_version
            return Observability(
                False, NO_MANIFEST,
                f"no manifest parsed for {missing}, so there is nothing to compare",
            )

        if not (base.is_fetchable and head.is_fetchable):
            # Cloudflare and Orb publish an endpoint count and no URL. That is a coverage gap
            # this approach does not close, and it is reported rather than discarded: the vendor
            # still needs a hand-written adapter and still contributes a coverage denominator.
            return Observability(
                False, NO_SPECIFICATION,
                f"manifest names no spec to fetch ({head.endpoint_count} endpoints configured); "
                f"this vendor needs a hand-written adapter",
            )

        if not head.changed_from(base):
            return OBSERVABLE

        base_url, _ = self._spec_url(from_version, base)
        head_url, _ = self._spec_url(to_version, head)
        if base_url == head_url:
            return Observability(
                False, ONE_DOCUMENT,
                f"both {from_version} and {to_version} resolve to {head_url}, so a diff would "
                f"compare that document against itself and report nothing whatever the vendor "
                f"shipped; supply a versioned specification URL per version to observe it",
            )

        return OBSERVABLE

    def fetch_changes(self, from_version: str, to_version: str) -> Iterable[VendorChange]:
        verdict = self.observability(from_version, to_version)
        if not verdict.observable:
            # Logged rather than raised, and never as an empty success. A vendor outside this
            # adapter's reach is a coverage gap and one such vendor must not abort a scan across
            # every other -- `observability` is where a caller asks which of them this was.
            log.info("%s: %s", self._vendor_id, verdict.detail)
            return []

        base = self._sources[from_version]
        head = self._sources[to_version]

        if not head.changed_from(base):
            # The whole economic argument. Two identical hashes mean the specification did not
            # move, and nothing is downloaded.
            log.debug("%s: spec hash unmoved between %s and %s", self._vendor_id, from_version, to_version)
            return []

        base_url, base_provenance = self._spec_url(from_version, base)
        head_url, head_provenance = self._spec_url(to_version, head)

        base_path = self._spec(from_version, base_url)
        head_path = self._spec(to_version, head_url)

        # Unfiltered, and the module docstring carries the measurement that says so. A kind list
        # here would be one vendor's release habits applied to every configured vendor.
        records = run_oasdiff_breaking(base_path, head_path)
        changes = to_vendor_changes(
            records, vendor_id=self._vendor_id, from_version=from_version, to_version=to_version
        )

        # The weaker of the two sides is what the diff is worth: a comparison against a mirror
        # is a mirror-grade comparison even if the other end came from the vendor.
        provenance = (
            VENDOR_PUBLISHED
            if base_provenance == head_provenance == VENDOR_PUBLISHED
            else GENERATOR_MIRROR
        )
        for change in changes:
            change.raw[PROVENANCE_KEY] = provenance
        return changes

    def _spec_url(self, version: str, source: SpecSource) -> tuple[str, str]:
        """The URL to fetch this version from, and what that artifact is worth.

        A vendor-published URL wins where the caller supplied one. `source.spec_url` is not None
        here -- `fetch_changes` has already established the source is fetchable.
        """
        vendor_url = self._vendor_spec_urls.get(version)
        if vendor_url is not None:
            return vendor_url, VENDOR_PUBLISHED
        assert source.spec_url is not None
        return source.spec_url, GENERATOR_MIRROR

    def _spec(self, version: str, url: str) -> Path:
        """A local copy of one version's specification.

        A version names an immutable artifact, so a populated cache file is already what a fresh
        fetch would return and is used without calling out. A zero-byte file is not treated as
        cached: that is what an interrupted or failed write leaves behind, and handing it to
        oasdiff would produce a diff against nothing and call the result a clean bill of health.

        A failed fetch raises. An outage that reads as "this vendor changed nothing" is the exact
        failure this adapter exists to catch, arriving from our own side, so it is never allowed
        to look like an empty result.

        There is deliberately no stale-cache fallback in the failure path, which is where this
        departs from `sync.signals.deprecations.adapter`. That cache expires -- a deprecation page
        changes under a fixed URL -- so it can be stale while a refetch is attempted, and falling
        back to yesterday's copy is a real choice. Here a version names an immutable artifact, so
        a cached copy is never stale and the check above has already returned it. A fetch is only
        ever attempted when nothing is cached, which leaves the fallback unreachable rather than
        cautious.
        """
        destination = self._cache_dir / f"{self._vendor_id}-{version}.json"
        if destination.exists() and destination.stat().st_size > 0:
            return destination

        try:
            body = self._fetch(url)
        except Exception as exc:
            raise RuntimeError(
                f"{self._vendor_id} specification for {version} could not be retrieved and "
                f"nothing usable is cached ({url}): {exc}"
            ) from exc

        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(body, encoding="utf-8")
        return destination


def _segments(path: str) -> tuple[str, ...]:
    return tuple(path.strip("/").split("/")) if path.strip("/") else ()


def _matches(template: tuple[str, ...], request: tuple[str, ...]) -> bool:
    return len(template) == len(request) and all(
        (literal.startswith("{") and literal.endswith("}")) or literal == observed
        for literal, observed in zip(template, request)
    )


def _build_routes(
    operations: Iterable[ExtractedOperation],
) -> dict[tuple[str, int], list[tuple[tuple[str, ...], ExtractedOperation]]]:
    routes: dict[tuple[str, int], list[tuple[tuple[str, ...], ExtractedOperation]]] = {}
    for op in operations:
        template = _segments(op.path)
        routes.setdefault((op.http_method.lower(), len(template)), []).append((template, op))
    return routes


class CorrelatingGeneratedSpecAdapter(GeneratedSpecAdapter):
    """A GeneratedSpecAdapter over a staged SDK source that implements RequestCorrelator.

    Extends `GeneratedSpecAdapter` with runtime HTTP request correlation, matching observed
    client spans against the route templates extracted directly from the staged SDK source.
    """

    def __init__(
        self,
        vendor_id: str,
        sources: Mapping[str, SpecSource],
        fetch: Fetch,
        cache_dir: Path | str,
        vendor_spec_urls: Mapping[str, str] | None = None,
        sdk_bindings: Mapping[str, Mapping[str, str]] | None = None,
        sdk_source: Path | str | None = None,
        sdk_spec_operations: Path | str | None = None,
        sdk_source_generator: str = DEFAULT_GENERATOR,
    ) -> None:
        super().__init__(
            vendor_id=vendor_id,
            sources=sources,
            fetch=fetch,
            cache_dir=cache_dir,
            vendor_spec_urls=vendor_spec_urls,
            sdk_bindings=sdk_bindings,
            sdk_source=sdk_source,
            sdk_spec_operations=sdk_spec_operations,
            sdk_source_generator=sdk_source_generator,
        )
        self._routes: dict[tuple[str, int], list[tuple[tuple[str, ...], ExtractedOperation]]] | None = None

    @property
    def uncorrelatable_reason(self) -> str | None:
        return None

    def operation_for_request(self, http_method: str, path: str) -> OperationRef | None:
        """The operation an observed request addressed, or None if nothing here can say."""
        symbols = self._extracted_symbols()
        if not symbols:
            return None
        if self._routes is None:
            self._routes = _build_routes(symbols.values())

        request = _segments(path)
        candidates = self._routes.get((http_method.lower(), len(request)), ())
        if any(not segment for segment in request):
            return None

        matched = [entry for template, entry in candidates if _matches(template, request)]
        if not matched:
            return None
        entry = min(matched, key=lambda e: e.path.count("{"))
        return OperationRef(
            operation_id=f"{entry.http_method} {entry.path}",
            http_method=entry.http_method.lower(),
            path=entry.path,
        )

