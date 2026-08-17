"""The conformance kit, run against the implementations this repository actually ships.

`tests/test_adapter_conformance.py` proves the kit's rules work. It proves them against
`_Correct()`, `WrongType()`, `Raises()` and their siblings -- classes written to be checked. None
of that says anything about `StripeAdapter`, which is what a customer's run loads.

That distinction is the whole point of the kit. `CLAUDE.md` makes the plugin story the product: a
third party writing an adapter depends on `sync.core` alone, and the kit is what tells them they
are wrong before the pipeline does. A kit whose own project never points it at its own
implementations is a kit nobody has evidence works on real code.

**Every list here is derived, never restated.** A test naming `["stripe", "twilio"]` passes
forever after somebody registers a third adapter that conforms to nothing, which is the defect
this file exists to close arriving one level up. So the vendors come from
`registry.available_vendors()`, the languages from `cli.language_adapters()`, the detectors and
the remediators from the functions that assemble them for a run, and the correlators from asking
each built vendor adapter whether it is one. Registering an implementation is what puts it in
scope here; nothing else is.

What a registered implementation with no case does
--------------------------------------------------
It fails. Loudly, naming itself, in a test that did not exist before it was registered.

Several checks need inputs the kit cannot invent -- `check_vendor_adapter` needs a symbol the
adapter is expected to resolve, `check_request_correlator` needs a request and the identifier
inside it, `check_detector` needs a graph its detector finds something in. Those are per-vendor
and per-detector facts, and they live beside the tests as a mapping keyed by whatever the
registry keys the implementation by.

A mapping is the obvious answer and it carries the obvious hazard: the moment a vendor is
registered without an entry, a mapping consulted with `.get` skips it silently and the file goes
on reporting success about a set that no longer includes it. So the mapping is never consulted
with `.get`. The parametrisation is over the *registry*, and a case looked up and not found
raises -- a registered adapter that is quietly not checked is precisely the defect being closed.
The mirror is asserted too: a case naming something no longer registered fails rather than
sitting here exempting whatever gets registered under that name next.
"""

from __future__ import annotations

import json
import math
import os
import shutil
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable

import pytest

from sync.cli import _detector_suite, build_remediator, language_adapters
from sync.core import (
    CallSite,
    Finding,
    ObservedCall,
    ObservedShape,
    RepoRef,
    VendorChange,
)
from sync.core.conformance import (
    ConformanceFailure,
    check_detector,
    check_language_adapter,
    check_remediator,
    check_request_correlator,
    check_vendor_adapter,
)
from sync.core.protocols import RequestCorrelator
from sync.detect.efficiency import LOOP_THRESHOLD, EfficiencyDetector
from sync.detect.observed_drift import MIN_SAMPLES as DRIFT_MIN_SAMPLES
from sync.detect.observed_drift import DeclaredField, ObservedDriftDetector
from sync.detect.parameter_deprecation import (
    LinkedDeprecation,
    ParameterDeprecationDetector,
)
from sync.detect.status_rate import (
    ERROR_RATE_THRESHOLD,
    MIN_STATUSED_CALLS,
    StatusRateDetector,
)
from sync.detect.vendor_change import VendorChangeDetector
from sync.graph.store import GraphStore
from sync.signals.deprecations import (
    ModelDeprecation,
    ParameterDeprecation,
    parameters_to_vendor_changes,
    to_vendor_changes,
)
from sync.signals.registry import (
    SYMBOL_MAP_FILENAME,
    TWILIO_PRODUCTS_FILENAME,
    VendorContext,
    available_vendors,
    load_vendor,
)
from sync.signals.stripe.symbols import build_symbol_map as build_stripe_symbols
from sync.signals.twilio.symbols import build_symbol_map as build_twilio_symbols

FIXTURES = Path(__file__).parent / "fixtures"

# --- VendorAdapter ------------------------------------------------------------------


@dataclass(frozen=True)
class VendorCase:
    """The per-vendor facts the kit cannot invent, for one registered vendor.

    `stage` writes into the cache directory `load_vendor` is pointed at, which is the same
    directory `sync run` stages into -- so the adapter under test is built by the registry's own
    loader over artifacts in the layout the loader expects, rather than by a constructor call
    that could drift from how a run builds it.

    `known_symbol` is a symbol the adapter is expected to be asked about. `correlation` is the
    `(method, path)` and the live identifier inside it that `check_request_correlator` needs, and
    is None for a vendor whose adapter does not correlate requests -- which is checked rather
    than assumed, below.
    """

    stage: Callable[[Path], None]
    known_symbol: str
    correlation: tuple[tuple[str, str], str] | None = None


def _stage_nothing(cache_dir: Path) -> None:
    """A configured vendor is served by `GeneratedSpecAdapter`, which `load_vendor` builds over
    an empty cache by design: `sources={}` and no `sdk_source`, because that loader promises to
    reach no network. Staging anything here would be testing an adapter no run constructs."""


def _stage_stripe(cache_dir: Path) -> None:
    shutil.copy(FIXTURES / "specs" / "stripe_v2330_shape.json", cache_dir)
    specification = json.loads(
        (FIXTURES / "specs" / "stripe_v2330_shape.json").read_text(encoding="utf-8")
    )
    (cache_dir / SYMBOL_MAP_FILENAME).write_text(
        json.dumps(build_stripe_symbols(specification)), encoding="utf-8"
    )


def _stage_twilio(cache_dir: Path) -> None:
    shape = json.loads(
        (FIXTURES / "twilio" / "insights_v1_shape.json").read_text(encoding="utf-8")
    )
    (cache_dir / "insights_v1.json").write_text(json.dumps(shape), encoding="utf-8")
    (cache_dir / TWILIO_PRODUCTS_FILENAME).write_text(
        json.dumps([{"filename": "insights_v1.json", "domain": "insights", "version": "v1"}]),
        encoding="utf-8",
    )
    (cache_dir / SYMBOL_MAP_FILENAME).write_text(
        json.dumps(build_twilio_symbols(shape, domain="insights", version="v1")),
        encoding="utf-8",
    )


def _stage_anthropic(cache_dir: Path) -> None:
    sdk_dest = cache_dir / "sdk_source"
    shutil.copytree(FIXTURES / "sdk_sources" / "anthropic_python", sdk_dest, dirs_exist_ok=True)


def _stage_vercel(cache_dir: Path) -> None:
    sdk_dest = cache_dir / "sdk_source"
    shutil.copytree(FIXTURES / "sdk_sources" / "vercel_typescript", sdk_dest, dirs_exist_ok=True)
    (cache_dir / "sdk_generator.txt").write_text("speakeasy-typescript", encoding="utf-8")


# Keyed the way `sync.signals.registry` keys a vendor, and consulted by a lookup that raises
# rather than by `.get`. A vendor registered without an entry here fails the parametrised test
# below naming itself; it is never skipped, because a registered adapter that is quietly not
# checked is the defect this file exists to close.
#
# The remaining configured vendors share `_stage_nothing` and a plausible customer symbol. Their
# adapter answers `operation_for_symbol` with None for every symbol, because `load_vendor`
# builds it with no staged SDK source -- see `test_which_registered_vendors_actually_resolve`,
# which records that rather than leaving it to be inferred from a check that passed.
VENDOR_CASES: dict[str, VendorCase] = {
    "stripe": VendorCase(
        stage=_stage_stripe,
        known_symbol="stripe.charges.retrieve",
        correlation=(("GET", "/v1/charges/ch_3MtwBwLkdIwHu7ix28a3tqPa"), "ch_3MtwBwLkdIwHu7ix28a3tqPa"),
    ),
    "twilio": VendorCase(
        stage=_stage_twilio,
        known_symbol="twilio.insights.v1.calls.fetch",
        correlation=(("GET", "/v1/Voice/CA1234567890abcdef1234567890abcdef"), "CA1234567890abcdef1234567890abcdef"),
    ),
    "anthropic": VendorCase(stage=_stage_anthropic, known_symbol="anthropic.messages.create"),
    "openai": VendorCase(stage=_stage_nothing, known_symbol="openai.responses.create"),
    "cloudflare": VendorCase(stage=_stage_nothing, known_symbol="cloudflare.zones.list"),
    "vercel": VendorCase(stage=_stage_vercel, known_symbol="vercel.aliases.getAlias"),
}


def _vendor_case(vendor_id: str) -> VendorCase:
    if vendor_id not in VENDOR_CASES:
        raise AssertionError(
            f"'{vendor_id}' is registered in sync.signals.registry and no conformance case "
            f"names it, so the adapter a customer's run loads for it is never checked against "
            f"the kit. Add an entry to VENDOR_CASES in {__file__}"
        )
    return VENDOR_CASES[vendor_id]


def _built(vendor_id: str, cache_dir: Path):
    """The adapter a run loads for this vendor, over a cache staged the way a run stages one."""
    case = _vendor_case(vendor_id)
    cache_dir.mkdir(parents=True, exist_ok=True)
    case.stage(cache_dir)
    return load_vendor(
        vendor_id, VendorContext(cache_dir=cache_dir, from_version="v1", to_version="v2")
    )


# Vendors whose SDK source **this suite** never stages, so the kit's requirement that the known
# symbol resolves cannot be met here.
#
# Read the reason precisely, because the shorter version of it is alarming and wrong. These
# adapters are not unable to resolve symbols. `registry._load_generated` builds
# `GeneratedSpecAdapter` with `sources={}` -- an empty cache, deliberately, because that loader
# promises to reach no network and builds from the manifest alone. Symbol resolution needs the
# SDK source, and nothing here stages one, so `operation_for_symbol` is being asked a question it
# was never given the material to answer. The extraction that would answer it is proved
# separately, against committed SDK checkouts, in `test_extracted_symbols.py`,
# `test_extracted_symbols_typescript.py` and `test_extracted_symbols_speakeasy.py`.
#
# What retires an entry: a fixture in this suite that stages that vendor's SDK source into the
# cache `load_vendor` is pointed at, after which the adapter resolves and the vendor moves into
# the checked set. `test_the_unstaged_set_is_exactly_the_set_that_resolves_nothing` fails in both
# directions until then, so this cannot outlive the gap or quietly grow to cover a real defect.
#
# That question -- whether a generated vendor resolves in a real run -- is answered, and the
# answer is no, on both paths. The two loaders differ in what they hold and not in this: neither
# `_prepare_generated` (`registry.py:319`) nor `_load_generated` (`registry.py:362`) passes
# `sdk_source`, so the map is never built for either, and a `sync run` declines every symbol
# exactly as this suite does. An earlier version of this note said the shape a customer meets was
# the other one; it is the same one, and the correction is the point. B131 is the entry.
#
# What that costs the product is reported rather than absorbed: the adapter declares
# `unbindable_reason`, `cli._binding_lines` prints it before the finding count, and
# `test_a_registered_vendor_that_binds_nothing_declares_why` below holds the two sides in step.
# Reporting the gap is not closing it -- closing it needs a staged checkout.
UNSTAGED_SDK_SOURCE = {"cloudflare", "openai"}

_UNRESOLVED_RULE = "the adapter did not resolve the symbol the kit was given."


@pytest.mark.parametrize("vendor_id", available_vendors())
def test_every_registered_vendor_adapter_passes_the_kit(vendor_id: str, tmp_path):
    adapter = _built(vendor_id, tmp_path)
    known_symbol = _vendor_case(vendor_id).known_symbol

    if vendor_id in UNSTAGED_SDK_SOURCE:
        # Asserted on the rule's own wording rather than on the exception type. Every rule in the
        # kit raises `ConformanceFailure`, so `pytest.raises` alone would let this entry absorb
        # some later, unrelated failure of the same type and go on reporting it as the known gap.
        with pytest.raises(ConformanceFailure) as raised:
            check_vendor_adapter(adapter, known_symbol=known_symbol)
        assert _UNRESOLVED_RULE in str(raised.value), (
            f"'{vendor_id}' is exempted for having no SDK source staged, and the kit refused it "
            f"for a different reason: {raised.value}"
        )
        return

    check_vendor_adapter(adapter, known_symbol=known_symbol)


def test_no_vendor_case_names_something_that_is_not_registered():
    """The mirror, and the half that is easy to leave out.

    A case outliving its vendor is a line that exempts nothing today and quietly supplies a
    fixture to whatever is registered under that name tomorrow.
    """
    registered = set(available_vendors())

    for vendor_id in sorted(VENDOR_CASES):
        assert vendor_id in registered, (
            f"VENDOR_CASES names '{vendor_id}' and sync.signals.registry registers "
            f"{sorted(registered)}; delete the entry"
        )


def test_the_unstaged_set_is_exactly_the_set_that_resolves_nothing(tmp_path):
    """The staleness gate on `UNSTAGED_SDK_SOURCE`, and it has to fail in both directions.

    An exemption that starts covering something it does not describe is the failure mode a list
    exists to be immune to, and it arrives from either side. A vendor in the set that starts
    resolving -- because somebody staged its SDK source -- leaves a line exempting a vendor that
    no longer needs exempting, and the next vendor added to the set inherits the silence. A
    vendor *outside* the set that stops resolving is the direction that matters more: that is a
    real regression in an adapter this repository ships, and without this assertion it would
    surface as its parametrisation failing with a message about the case rather than about the
    adapter.

    So the set is asserted as an equality against what the adapters actually answer, rather than
    each half being spot-checked. This replaces an earlier assertion here that pinned the
    resolving set to the literal `{"stripe", "twilio"}`: the two would have had to be kept in
    step by hand, and one of them would eventually have been the only one updated.
    """
    resolving = {
        vendor_id
        for vendor_id in available_vendors()
        if _built(vendor_id, tmp_path / vendor_id).operation_for_symbol(
            _vendor_case(vendor_id).known_symbol, language=None
        )
        is not None
    }

    assert resolving == set(available_vendors()) - UNSTAGED_SDK_SOURCE, (
        f"{sorted(resolving)} resolve their known symbol and UNSTAGED_SDK_SOURCE says "
        f"{sorted(set(available_vendors()) - UNSTAGED_SDK_SOURCE)} should. A vendor that started "
        f"resolving means its SDK source is now staged and its entry should be deleted; a vendor "
        f"that stopped is a regression in an adapter this repository ships"
    )


def test_a_registered_vendor_that_binds_nothing_declares_why(tmp_path):
    """Every registered adapter that resolves no symbol says so, and no other one claims to.

    The half of the gap above that a caller can act on. `test_the_unstaged_set_...` establishes
    which adapters resolve nothing; this establishes that each of them *reports* it, so a run
    can tell "we looked and found no call sites" from "nothing here could have been looked at".
    Without it those two are one output -- no call sites, no findings, exit 0 -- and the second
    reads as the first, which is a clean bill of health the data does not support.

    Both directions, and derived on both sides. An adapter that resolves and declares a reason
    anyway would qualify a real measurement and teach a reader to skip the qualification; an
    adapter that resolves nothing and declares nothing is the silent zero this closes. Neither
    side is a list of vendor ids, so a vendor registered tomorrow is checked on the commit that
    registers it.
    """
    for vendor_id in available_vendors():
        adapter = _built(vendor_id, tmp_path / vendor_id)
        resolves = adapter.operation_for_symbol(
            _vendor_case(vendor_id).known_symbol, language=None
        ) is not None
        declared = getattr(adapter, "unbindable_reason", None)

        assert (declared is None) == resolves, (
            f"'{vendor_id}' resolves its known symbol: {resolves}, and declares "
            f"unbindable_reason: {declared!r}. An adapter that binds nothing has to say why, or "
            f"a run reports the same zero for a repository that calls the vendor and one that "
            f"does not; an adapter that binds must stay silent, or the qualification appears "
            f"over a real measurement"
        )


# --- RequestCorrelator ---------------------------------------------------------------


def _correlators() -> list[str]:
    """Which registered vendors ship a correlator, asked of the adapters rather than listed.

    Derived by `isinstance` against the protocol, so a second vendor that implements
    `operation_for_request` is checked by the test below on the commit that adds it -- and one
    that stops implementing it stops being claimed here.
    """
    import tempfile

    found = []
    for vendor_id in available_vendors():
        with tempfile.TemporaryDirectory() as cache:
            if isinstance(_built(vendor_id, Path(cache)), RequestCorrelator):
                found.append(vendor_id)
    return found


CORRELATORS = _correlators()


@pytest.mark.parametrize("vendor_id", CORRELATORS)
def test_every_shipped_correlator_passes_the_kit(vendor_id: str, tmp_path):
    """The one check with no gate downstream of it.

    Everywhere else in the kit a broken guarantee produces a wrong answer something later
    refuses. A path that arrives carrying a customer's identifier is written to `observed_call`,
    joined into findings and rendered into a pull request on a repository Sync does not own.
    """
    case = _vendor_case(vendor_id)
    assert case.correlation is not None, (
        f"'{vendor_id}' implements RequestCorrelator and its VENDOR_CASES entry names no "
        f"request to correlate, so the only check standing between a customer's identifier and "
        f"a public pull request is never run against it"
    )
    known_request, identifier = case.correlation

    check_request_correlator(
        _built(vendor_id, tmp_path), known_request=known_request, identifier=identifier
    )


def test_a_vendor_that_does_not_correlate_declares_no_correlation_case():
    """The mirror. A correlation case on a vendor whose adapter is not a correlator is a fixture
    nothing runs, and it reads as coverage that does not exist."""
    for vendor_id, case in sorted(VENDOR_CASES.items()):
        if case.correlation is not None:
            assert vendor_id in CORRELATORS, (
                f"VENDOR_CASES['{vendor_id}'] names a request to correlate and that adapter is "
                f"not a RequestCorrelator; the case is never used"
            )


# --- Remediator ----------------------------------------------------------------------

# One call carrying a retired model and both deprecated parameters, which is what lets the three
# deprecation codemods share a clone.
#
# `max_tokens` is deliberately absent. `ParameterRenameRemediator` renames `budget_tokens` onto
# it and declines when the target key is already present, because JavaScript resolves a duplicate
# key to the last one silently -- so a source declaring both makes that tier return an empty diff,
# which `check_remediator` reads as a decline and passes. That is exactly the vacuous pass
# `test_the_case_each_remediator_was_given_is_one_it_actually_patches` exists to refuse, and it is
# how this comment came to be written.
_DEPRECATED_MODEL_SOURCE = """\
import Anthropic from '@anthropic-ai/sdk';

const client = new Anthropic();

export async function summarise(text: string) {
  return client.messages.create({
    model: "claude-3-7-sonnet-20250219",
    temperature: 0.7,
    budget_tokens: 16,
  });
}
"""


def _typescript_clone(root: Path) -> RepoRef:
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "src" / "summarise.ts").write_text(_DEPRECATED_MODEL_SOURCE, encoding="utf-8")
    return RepoRef(
        repo_id="r", url="https://example.invalid/r", local_path=str(root), head_sha="s"
    )


def _model_site(operation_id: str = "claude-3-7-sonnet-20250219") -> CallSite:
    return CallSite(
        id="cs-1", repo_id="r", path="src/summarise.ts", line=7, col=11, vendor_id="anthropic",
        operation_id=operation_id, symbol="model",
        args_keys=["model", "temperature", "budget_tokens"],
        sdk_version="0.70.0", content_hash="h",
    )


def _model_finding(severity: str = "breaking") -> Finding:
    return Finding(
        detector="deprecation", claim="parameter:model", call_site_id="cs-1",
        vendor_change_id="vc-1", severity=severity, rationale="the case handed to the kit",
    )


def _literal_swap_case(root: Path) -> RemediationCase:
    change = to_vendor_changes(
        [ModelDeprecation(
            vendor_id="anthropic", model_id="claude-3-7-sonnet-20250219", state="retired",
            replacement="claude-opus-4-8", retirement_date=date(2026, 2, 19),
            deprecated_date=None, not_before=None,
        )],
        "2026-07-01", "2026-07-28",
    )[0]
    return RemediationCase(_model_finding(), change, _model_site(), _typescript_clone(root))


def _parameter_case(row: ParameterDeprecation, root: Path) -> RemediationCase:
    change = parameters_to_vendor_changes([row], "2026-07-01", "2026-07-28")[0]
    return RemediationCase(
        _model_finding("deprecation"), change, _model_site("claude-3-7-sonnet-20250219"),
        _typescript_clone(root),
    )


def _omit_case(root: Path) -> RemediationCase:
    return _parameter_case(
        ParameterDeprecation(
            vendor_id="anthropic", parameter="temperature",
            status="Deprecated (Claude Opus 4.7 and later)",
            behavior="Returns a 400 error when set to a non-default value.",
            applies_from="Claude Opus 4.7 and later",
        ),
        root,
    )


def _rename_case(root: Path) -> RemediationCase:
    return _parameter_case(
        ParameterDeprecation(
            vendor_id="anthropic", parameter="budget_tokens", status="Deprecated",
            behavior="Returns a 400 error.", replacement="max_tokens",
        ),
        root,
    )


def _property_omit_case(root: Path) -> RemediationCase:
    shutil.copytree(FIXTURES / "ts" / "two_payment_intents", root, dirs_exist_ok=True)
    change = VendorChange(
        vendor_id="stripe", from_version="v2300", to_version="v2345",
        kind="request-property-removed", operation_id="PostPaymentIntents",
        path_ptr="/v1/payment_intents", severity="breaking", source="oasdiff",
        raw={"id": "request-property-removed",
             "text": "removed the request property `receipt_email`"},
    )
    site = CallSite(
        id="cs-1", repo_id="r", path="app/api/setup_accounts/route.ts", line=11, col=23,
        vendor_id="stripe", operation_id="PostPaymentIntents",
        symbol="stripe.paymentIntents.create",
        args_keys=["amount", "currency", "customer", "receipt_email"],
        response_fields_read=["id"], sdk_version="22.4.0-beta.1", content_hash="h",
    )
    repo = RepoRef(
        repo_id="r", url="https://example.invalid/r", local_path=str(root), head_sha="abc123"
    )
    return RemediationCase(_model_finding(), change, site, repo)


# A case per remediator, keyed by class name, and a case each one actually handles.
#
# One shared case would be worse than none. Each codemod's `can_handle` keys on a different
# `change.kind`, so a single case is declined by three of the four -- and the kit's rule for a
# decline is that the clone was left alone, which a remediator that never ran satisfies
# perfectly. Three of four tiers would pass without their `propose` writing a line, which is the
# vacuous pass this whole file exists to stop reporting as coverage.
REMEDIATOR_CASES: dict[str, Callable[[Path], "RemediationCase"]] = {
    "LiteralSwapRemediator": _literal_swap_case,
    "ParameterOmitRemediator": _omit_case,
    "ParameterRenameRemediator": _rename_case,
    "PropertyOmitRemediator": _property_omit_case,
    # The composite the graph is actually handed. Checked over the case its first tier claims,
    # so the patch it returns is one a tier really wrote.
    "TieredRemediator": _literal_swap_case,
}

# Shipped, registered in the cascade, and not checkable from a test in this suite.
#
# `AgentRemediator.propose` runs the Agent SDK against a model, and `CLAUDE.md` states that no
# test calls a model API. There is no fixture that changes this: the rule the kit checks -- that
# a patch is what is on disk rather than what the diff says -- is a property of what the agent
# writes, and observing it means running the agent.
#
# Named rather than counted, for the reason `scripts/dead_links_baseline.txt` gives, and held to
# the registry in both directions by the two tests below: an entry that no longer names a
# registered remediator fails, and a registered remediator that is in neither this set nor
# `REMEDIATOR_CASES` fails. A silent skip here would be the defect this file closes, wearing the
# costume of a decision somebody made.
UNCHECKABLE_REMEDIATORS = {"AgentRemediator"}


@dataclass(frozen=True)
class RemediationCase:
    """A finding, a change, a call site and a clone the remediator is expected to edit."""

    finding: Finding
    change: VendorChange
    site: CallSite
    repo: RepoRef


def _shipped_remediators() -> dict[str, object]:
    """Every remediator the cascade a run is handed contains, by class name.

    Read out of `cli.build_remediator()` rather than listed, because that function is what
    decides which tiers exist. `TerminalTier` is unwrapped: it is a positional wrapper with no
    guarantees of its own, and the remediator inside it is the one whose `propose` writes to a
    customer's clone.
    """
    cascade = build_remediator()
    found: dict[str, object] = {type(cascade).__name__: cascade}
    for tier in cascade._remediators:
        inner = getattr(tier, "_remediator", tier)
        found[type(inner).__name__] = inner
    return found


SHIPPED_REMEDIATORS = _shipped_remediators()

CHECKABLE_REMEDIATORS = sorted(set(SHIPPED_REMEDIATORS) - UNCHECKABLE_REMEDIATORS)


@pytest.mark.parametrize("name", CHECKABLE_REMEDIATORS)
def test_every_shipped_remediator_passes_the_kit(name: str, tmp_path):
    if name not in REMEDIATOR_CASES:
        raise AssertionError(
            f"{name} is a tier in cli.build_remediator() and no conformance case names it, so "
            f"the remediator a run hands a customer's clone to is never checked against the "
            f"kit. Add an entry to REMEDIATOR_CASES in {__file__}"
        )
    case = REMEDIATOR_CASES[name](tmp_path)

    check_remediator(
        SHIPPED_REMEDIATORS[name], case.finding, case.change, case.site, case.repo
    )


def test_every_remediator_case_and_exemption_still_names_a_shipped_tier():
    """Both directions, because an exemption outliving what it exempted is a line that quietly
    exempts whatever gets registered under that name next."""
    shipped = set(SHIPPED_REMEDIATORS)

    for name in sorted(set(REMEDIATOR_CASES) | UNCHECKABLE_REMEDIATORS):
        assert name in shipped, (
            f"{name} is named here and cli.build_remediator() assembles {sorted(shipped)}; "
            f"delete the entry"
        )


def test_each_remediator_agrees_with_can_handle_about_the_case_it_was_given(tmp_path):
    """What is left here after the kit learned to refuse a case it was not exercised by.

    This test used to assert two things: that the remediator claims the case, and that `propose`
    returns a patch rather than an empty diff. The second is now `check_remediator`'s own
    precondition -- "the case handed to the kit must be one this remediator patches" -- so
    `test_every_shipped_remediator_passes_the_kit` above catches it one layer down, for every
    author rather than only for this repository. Asserting it twice would leave two statements of
    one rule free to drift, and the weaker one is the one that would survive.

    The `can_handle` half stays, because the kit genuinely cannot see it: nothing in
    `check_remediator` consults `can_handle`, and `nodes.make_patch` calls `propose` directly
    without it. So a tier that patches a change it publicly declines is a real inconsistency
    between what routing is told and what the tier does, and this is the only place it is checked.
    """
    for name in CHECKABLE_REMEDIATORS:
        case = REMEDIATOR_CASES[name](tmp_path / name)

        assert SHIPPED_REMEDIATORS[name].can_handle(case.finding, case.change), (
            f"{name} declines the case REMEDIATOR_CASES gives it and then patches it, so routing "
            f"is told this tier does not serve a change it does in fact serve"
        )


# --- LanguageAdapter -------------------------------------------------------------------


@dataclass(frozen=True)
class LanguageCase:
    """A committed checkout the adapter is expected to own, index, prepare and verify.

    `installed_dependency` is the repository-relative path to a file `prepare` installed, and it
    is what turns on the doctored-dependency rule. None for a language that installs nothing --
    the kit skips that rule rather than passing it, which is the honest reading for `PythonAdapter`,
    whose `prepare` deliberately does nothing at all.
    """

    repo: RepoRef
    installed_dependency: str | None


def _committed(root: Path, git) -> None:
    """A checkout, not a directory.

    `TypeScriptAdapter.prepare` measures a typecheck baseline and refuses a tree with uncommitted
    changes in it, because a modification present at baseline is subtracted from the verification
    that exists to catch it. Every clone the pipeline verifies came from `git clone`, so a bare
    directory is not a case the pipeline can reach.
    """
    git(["init", "-q", "-b", "main"], root)
    git(["add", "."], root)
    git(["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base"], root)


def _typescript_case(root: Path, git) -> LanguageCase:
    shutil.copytree(FIXTURES / "ts" / "simple", root, dirs_exist_ok=True)
    (root / "tsconfig.json").write_text(
        '{"compilerOptions": {"strict": true, "noEmit": true, "target": "ES2022",'
        ' "module": "ESNext", "moduleResolution": "bundler", "skipLibCheck": true},'
        ' "include": ["src"]}',
        encoding="utf-8",
    )
    (root / ".gitignore").write_text("node_modules\n", encoding="utf-8")

    # An install, without running one. `deps.install_dependencies` is a no-op for a tree whose
    # `node_modules` is already populated, so writing the tree here gives `prepare` a real
    # installed dependency to record and the kit a real one to doctor -- without a network fetch
    # in a suite that must not need one, and without the minutes an `npm install` costs.
    (root / "node_modules" / "stripe").mkdir(parents=True)
    (root / "node_modules" / "stripe" / "package.json").write_text(
        '{"name": "stripe", "version": "18.0.0", "types": "index.d.ts"}', encoding="utf-8"
    )
    (root / "node_modules" / "stripe" / "index.d.ts").write_text(
        "declare class Stripe { charges: { create(args: object): Promise<{ id: string;"
        " status: string }> } }\nexport default Stripe;\n",
        encoding="utf-8",
    )
    _committed(root, git)
    return LanguageCase(
        repo=RepoRef(
            repo_id="ts", url="https://example.invalid/ts", local_path=str(root),
            head_sha="0" * 40,
        ),
        installed_dependency="node_modules/stripe/index.d.ts",
    )


def _python_case(root: Path, git) -> LanguageCase:
    shutil.copytree(FIXTURES / "py" / "simple", root, dirs_exist_ok=True)
    _committed(root, git)
    return LanguageCase(
        repo=RepoRef(
            repo_id="py", url="https://example.invalid/py", local_path=str(root),
            head_sha="0" * 40,
        ),
        installed_dependency=None,
    )


# Keyed by `language_id`, which is what `cli.select_language_adapter` selects on and what every
# migration outcome records. Consulted by a lookup that raises: a third indexer registered in
# `cli.language_adapters` without a case here fails the test below naming itself.
LANGUAGE_CASES: dict[str, Callable[[Path, object], LanguageCase]] = {
    "typescript": _typescript_case,
    "python": _python_case,
}


def _language_vendor(cache_dir: Path):
    """A vendor adapter that resolves the symbols these fixtures call.

    Both indexers read `sdk_bindings` off whatever they are handed and ask it to resolve every
    symbol they find, so a language adapter checked against a vendor that binds nothing matches
    no repository and indexes no call site -- and the kit reports that as the case being wrong,
    correctly, but the adapter would never have been exercised.
    """
    return _built("stripe", cache_dir)


SHIPPED_LANGUAGES = {adapter.language_id: adapter for adapter in language_adapters()}


@pytest.mark.parametrize("language_id", sorted(SHIPPED_LANGUAGES))
def test_every_shipped_language_adapter_passes_the_kit(language_id: str, tmp_path, git):
    if language_id not in LANGUAGE_CASES:
        raise AssertionError(
            f"'{language_id}' is registered in cli.language_adapters() and no conformance case "
            f"names it, so the indexer a customer's repository is handed to is never checked "
            f"against the kit. Add an entry to LANGUAGE_CASES in {__file__}"
        )
    case = LANGUAGE_CASES[language_id](tmp_path / "clone", git)
    adapter = SHIPPED_LANGUAGES[language_id](
        vendor_adapter=_language_vendor(tmp_path / "cache")
    )

    check_language_adapter(
        adapter, case.repo, installed_dependency=case.installed_dependency
    )


def test_no_language_case_names_something_that_is_not_registered():
    for language_id in sorted(LANGUAGE_CASES):
        assert language_id in SHIPPED_LANGUAGES, (
            f"LANGUAGE_CASES names '{language_id}' and cli.language_adapters() registers "
            f"{sorted(SHIPPED_LANGUAGES)}; delete the entry"
        )


# --- Detector --------------------------------------------------------------------------

_SEEN = datetime(2026, 7, 20, 9, 0, tzinfo=timezone.utc)

_DEPRECATED_PARAMETER = ParameterDeprecation(
    vendor_id="anthropic", parameter="temperature",
    status="Deprecated (Claude Opus 4.7 and later)",
    behavior="Returns a 400 error when set to a non-default value.",
    applies_from="Claude Opus 4.7 and later",
)


def _stored_site(store, **over) -> str:
    fields = dict(
        repo_id="r", path="src/billing.ts", line=12, col=4, vendor_id="stripe",
        operation_id="GetCharges", symbol="stripe.charges.list", args_keys=["limit"],
        response_fields_read=["data"], sdk_version="18.0.0", content_hash="h",
    )
    fields.update(over)
    return store.upsert_call_site(CallSite(**fields))


def _observed_call(store, spans: dict, **over) -> None:
    fields = dict(
        repo_id="r", vendor_id="stripe", operation_id="GetCharges", binding_rung="observed",
        server_address="api.stripe.com", http_method="get", trace_id="t1",
        url_template="/v1/charges", spans=spans, first_seen=_SEEN, last_seen=_SEEN,
    )
    fields.update(over)
    store.record_observed_call(ObservedCall(**fields))


def _vendor_change_case(store):
    """A change on an operation the indexed code calls, reading the field that was removed."""
    _stored_site(
        store, operation_id="PostCharges", symbol="stripe.charges.create",
        args_keys=["amount"], response_fields_read=["id", "status"],
    )
    store.upsert_vendor_change(
        VendorChange(
            vendor_id="stripe", from_version="v1", to_version="v2",
            kind="response-property-removed", operation_id="PostCharges",
            path_ptr="/paths/x/status", severity="breaking", source="oasdiff",
            raw={"id": "response-property-removed", "field": "status"},
        )
    )
    return VendorChangeDetector(store)


def _parameter_deprecation_case(store):
    """Two facts about one call site: it passes the deprecated parameter and it is this vendor's.

    The only detector here that reads no graph at all -- it is handed its inputs by the caller
    that assembled them, so the store this case is given goes unused.
    """
    site = CallSite(
        id="cs-1", repo_id="r", path="src/a.ts", line=7, col=4, vendor_id="anthropic",
        operation_id="claude-opus-5", symbol="model",
        args_keys=["model", "temperature"], sdk_version="0.70.0", content_hash="h",
    )
    linked = [LinkedDeprecation(deprecation=_DEPRECATED_PARAMETER, vendor_change_id="vc-1")]
    return ParameterDeprecationDetector(linked, [site])


def _observed_drift_case(store):
    """A field observed as a type the specification does not declare."""
    _stored_site(
        store, operation_id="PostCharges", symbol="stripe.charges.create",
        args_keys=["amount"], response_fields_read=["data.status"],
    )
    store.record_observed_shape(
        ObservedShape(
            vendor_id="stripe", operation_id="PostCharges", field_path="/data/status",
            json_type="number", source="error-payload", sample_count=DRIFT_MIN_SAMPLES,
            first_seen=_SEEN, last_seen=_SEEN,
        )
    )
    return ObservedDriftDetector(
        store,
        {"PostCharges": [DeclaredField(
            field_path="/data/status", json_types=frozenset({"string"}), required=True,
            nullable=False,
        )]},
        "stripe",
    )


def _status_rate_case(store):
    """An error rate on the threshold, over enough calls to clear the sample floor."""
    _stored_site(store)
    errors = math.ceil(MIN_STATUSED_CALLS * ERROR_RATE_THRESHOLD)
    statuses = [500] * errors + [200] * (MIN_STATUSED_CALLS - errors)
    _observed_call(
        store,
        {
            f"s{index}": {"target": f"target{index}", "status": status, "resend": 0}
            for index, status in enumerate(statuses)
        },
    )
    return StatusRateDetector(store=store, repo_id="r", vendor_id="stripe")


def _efficiency_case(store):
    """One operation called enough times inside one trace to read as a loop."""
    _stored_site(store)
    _observed_call(
        store,
        {
            f"span{index}": {"target": f"target{index}", "status": 200, "resend": 0}
            for index in range(LOOP_THRESHOLD)
        },
    )
    return EfficiencyDetector(store=store, repo_id="r", vendor_id="stripe")


# A case per detector, keyed by class name. Each one seeds an input that reaches that
# detector's own thresholds, which is not optional here: `check_detector` refuses a scan that
# emits nothing, and it refuses it because probing this kit against the real detectors once had
# `StatusRateDetector` pass every rule on a fixture a hundred and twenty calls short of its
# floor. A shared fixture would reproduce exactly that.
DETECTOR_CASES: dict[str, Callable[[object], object]] = {
    "VendorChangeDetector": _vendor_change_case,
    "ParameterDeprecationDetector": _parameter_deprecation_case,
    "ObservedDriftDetector": _observed_drift_case,
    "StatusRateDetector": _status_rate_case,
    "EfficiencyDetector": _efficiency_case,
}


def _shipped_detectors() -> dict[str, type]:
    """Every detector class a scan runs, read out of the table that assembles the scan.

    `_detector_suite` is the difference between a detector existing and a detector running, and
    it is the only place that difference is decided. Constructed over `None` because these
    constructors record what they were handed and query nothing until `scan`, which keeps the
    enumeration available at collection time without a database.
    """
    suite = _detector_suite(
        None, spec_documents=[], call_sites=[], deprecations=[],
        vendor_id="stripe", repo_id="r", deprecation_vendors=("anthropic",),
    )
    return {type(detector).__name__: type(detector) for _, detector in suite}


SHIPPED_DETECTORS = _shipped_detectors()


@pytest.fixture()
def detector_store():
    store = GraphStore(os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync"))
    store.apply_schema()
    store.truncate_all()
    return store


@pytest.mark.parametrize("name", sorted(SHIPPED_DETECTORS))
def test_every_shipped_detector_passes_the_kit(name: str, detector_store):
    if name not in DETECTOR_CASES:
        raise AssertionError(
            f"{name} is in cli._detector_suite() and no conformance case names it, so a "
            f"detector every scan runs is never checked against the kit. Add an entry to "
            f"DETECTOR_CASES in {__file__}"
        )

    check_detector(DETECTOR_CASES[name](detector_store))


def test_no_detector_case_names_something_the_suite_does_not_run():
    for name in sorted(DETECTOR_CASES):
        assert name in SHIPPED_DETECTORS, (
            f"DETECTOR_CASES names {name} and cli._detector_suite() runs "
            f"{sorted(SHIPPED_DETECTORS)}; delete the entry"
        )
