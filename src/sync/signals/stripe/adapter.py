"""Stripe implementation of the VendorAdapter protocol."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Iterable

from sync.core import OperationRef, VendorChange
from sync.signals.oasdiff import run_oasdiff_breaking, to_vendor_changes

SPEC_REPO = "stripe/openapi"
SPEC_PATH_IN_REPO = "openapi/spec3.json"

# The generator input for Stripe's own SDKs, published beside the specification
# at the same tags. Its `x-stableId` names the SDK method for an operation, which
# is what `build_symbol_map` reads instead of guessing one from the HTTP verb.
SDK_SPEC_PATH_IN_REPO = "openapi/spec3.sdk.json"

# A new value in a response enum breaks only an exhaustive switch, and it is
# four fifths of what oasdiff reports on a Stripe release -- 86,368 of 107,396
# records between v2320 and v2330. Carrying that volume through the graph to
# produce findings nobody asked for is the wrong default. It lives here rather
# than in core because it is a judgement about one vendor's release habits,
# not a fact about API changes.
NOISE_KINDS = frozenset({"response-property-enum-value-added"})


def fetch_spec(tag: str, dest: Path, path_in_repo: str = SPEC_PATH_IN_REPO) -> Path:
    """Download a document at a given tag of stripe/openapi.

    Tags are sequential (`v2345`). Uses the authenticated `gh` CLI so it works
    without a separate token. Requests the raw file bytes via the
    `application/vnd.github.raw` Accept header rather than the default JSON
    envelope: spec3.json is larger than the 1 MB limit GitHub enforces on the
    base64-encoded `.content` field, so the envelope form fails outright for
    this file. Bytes are written unchanged — no `text=True` round trip — so a
    Windows console's non-UTF-8 default encoding can't corrupt the spec's
    non-ASCII characters.

    A tag names an immutable commit, so a populated `dest` is already
    byte-identical to what a fresh fetch would produce and is returned as-is
    without invoking `gh`. A zero-byte `dest` is not treated as cached: that
    is what an interrupted or failed previous write leaves behind, and
    reusing it would hand a truncated spec to oasdiff.
    """
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            "gh", "api", f"repos/{SPEC_REPO}/contents/{path_in_repo}?ref={tag}",
            "--header", "Accept: application/vnd.github.raw",
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"failed to fetch stripe spec at {tag}: {result.stderr.decode(errors='replace').strip()}")
    dest.write_bytes(result.stdout)
    return dest


def fetch_sdk_spec(tag: str, dest: Path) -> Path | None:
    """Download `openapi/spec3.sdk.json`, or return None if the tag has none.

    The document is an enhancement to the symbol map rather than a requirement
    for it: a tag predating `x-stableId` degrades to the HTTP-verb derivation, so
    a failed fetch is a supported outcome and must not end the run. That swallows
    every `gh` failure and not only a 404, which is affordable because the
    specification itself is fetched first and still raises — a real outage
    surfaces there rather than being mistaken for an absent document here.

    It is 10 MB, larger than the specification it accompanies, so it relies on
    the same cache-by-destination that `fetch_spec` already applies.
    """
    try:
        return fetch_spec(tag, dest, SDK_SPEC_PATH_IN_REPO)
    except RuntimeError:
        return None


def _segments(path: str) -> tuple[str, ...]:
    return tuple(path.strip("/").split("/")) if path.strip("/") else ()


def _build_routes(symbols: dict[str, dict[str, str]]) -> dict[tuple[str, int], list[tuple[tuple[str, ...], dict[str, str]]]]:
    """The symbol map, indexed for lookup by request rather than by symbol.

    Built from the symbol map and not from the specification, which bounds what correlation can
    ever resolve to exactly the set of operations the indexer can bind a call site to. That
    sounds like a limitation and is the opposite: an operation absent from the symbol map has no
    SDK method, so no call site in the customer's source is ever bound to it, so a span
    correlated to it would describe traffic that no indexed code produced. There would be
    nothing to remediate and nothing to attribute the finding to.

    Bucketed by (method, segment count) because a template segment matches exactly one segment,
    so a path of a different length can never match however it is spelled -- and Stripe's map
    is several hundred entries that would otherwise be walked per span.
    """
    routes: dict[tuple[str, int], list[tuple[tuple[str, ...], dict[str, str]]]] = {}
    for entry in symbols.values():
        template = _segments(entry["path"])
        routes.setdefault((entry["http_method"].lower(), len(template)), []).append((template, entry))
    return routes


def _matches(template: tuple[str, ...], request: tuple[str, ...]) -> bool:
    return all(
        (literal.startswith("{") and literal.endswith("}")) or literal == observed
        for literal, observed in zip(template, request)
    )


class StripeAdapter:
    """Turns two pinned Stripe specification versions into VendorChange rows."""

    vendor_id = "stripe"

    sdk_bindings = {
        "typescript": {"package": "stripe"},
        "python": {"distribution": "stripe", "module": "stripe"},
    }
    """Which package a customer imports to reach this vendor, per language.

    Read by `sync.index`, which until now held `_SDK_PACKAGE = "stripe"` as a module constant --
    so a vendor whose specification we could diff perfectly produced no findings, because
    nothing in the customer's code was ever bound to it. The name belongs here for the reason
    `CLAUDE.md` gives for every other vendor fact: the moment shared code knows a vendor's name,
    the plugin story is dead.

    Keyed by `LanguageAdapter.language_id`, and the value's shape belongs to the language
    adapter that reads it rather than to a schema stated here -- the same argument
    `sync.signals.registry` makes for keeping each vendor's construction behind its own builder.
    TypeScript needs one npm name, which is both the manifest key and the import specifier.
    Python needs two, because a distribution name and a module name are different strings in
    general even where this vendor spells them alike.

    It is deliberately not part of the `VendorAdapter` protocol. An adapter that declares none
    indexes nothing, which is the honest state of the four configured vendors and every watched
    MCP server: their specifications are discoverable and their call sites are not. Defaulting
    would bind another vendor's traffic to Stripe operations, and falling back to `vendor_id`
    is the same defect one layer down -- it is wrong for a scoped npm package and for an MCP
    server id, and it fails by resolving confidently rather than by declining.

    The per-language entry is a mapping rather than a fixed record so a later field lands here
    without a protocol change. That matters sooner than it looks: the substrate spec's harder
    half is that a call site's shape is per-SDK rather than per-vendor, and the three generators
    checked state the symbol-to-operation mapping three different ways -- stripe-node passes
    verb and path as plain arguments, Stainless puts the verb in the method name and the path in
    a tagged template, Speakeasy uses an object property and a helper call. A binding that
    assumed one of those would not carry the others, so nothing here assumes any of them; an
    extraction rule belongs beside the package name when the first adapter needs one.
    """

    def __init__(self, spec_dir: Path, symbol_map_path: Path) -> None:
        self._spec_dir = Path(spec_dir)
        self._symbols: dict[str, dict[str, str]] = json.loads(Path(symbol_map_path).read_text(encoding="utf-8"))
        self._routes = _build_routes(self._symbols)

    def fetch_changes(self, from_version: str, to_version: str) -> Iterable[VendorChange]:
        base = self._spec_dir / f"{from_version}.json"
        revision = self._spec_dir / f"{to_version}.json"
        for path in (base, revision):
            if not path.exists():
                raise FileNotFoundError(f"specification not found: {path}")
        records = [r for r in run_oasdiff_breaking(base, revision) if r.get("id") not in NOISE_KINDS]
        return to_vendor_changes(records, self.vendor_id, from_version, to_version)

    def operation_for_symbol(
        self, symbol: str, *, language: str | None = None
    ) -> OperationRef | None:
        entry = self._symbols.get(symbol)
        if entry is None:
            return None
        return OperationRef(
            operation_id=entry["operation_id"],
            http_method=entry["http_method"],
            path=entry["path"],
        )

    def operation_for_request(self, http_method: str, path: str) -> OperationRef | None:
        """The operation an observed request addressed, or None if nothing here can say.

        The inverse of `operation_for_symbol`, and the only thing that makes a span mean
        anything: a span carries a URL, the graph is keyed by operation.

        A literal template is preferred over one with a placeholder in the same position, so a
        path such as `/v1/charges/search` resolves to its own operation rather than being read
        as a charge whose id happens to be `search`. No Stripe release has yet produced that
        collision through `build_symbol_map`, whose pattern admits at most one placeholder
        segment -- the ordering is here because the day a literal sub-path does derive a symbol,
        the alternative is a confident binding to the wrong operation.

        None rather than a guess. A missing binding is visibly unresolved and can be counted; a
        wrong one produces a finding against code that never made the call.
        
        `language` is accepted and ignored: this map's keys are `stripe.<resource>.<method>`,
        and `stripe-node` and `stripe-python` agree on both segments for every operation the
        map holds. Twilio is where the two SDKs disagree and where the parameter earns its
        place; ignoring it here is a statement about Stripe rather than about the protocol.
        """
        request = _segments(path)
        candidates = self._routes.get((http_method.lower(), len(request)), ())
        if any(not segment for segment in request):
            return None

        matched = [entry for template, entry in candidates if _matches(template, request)]
        if not matched:
            return None
        entry = min(matched, key=lambda e: e["path"].count("{"))
        return OperationRef(
            operation_id=entry["operation_id"],
            http_method=entry["http_method"],
            path=entry["path"],
        )
