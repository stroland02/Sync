"""Findings that need two facts about one call site.

Every other detector matches one thing. This one fires only where a call site both passes a
deprecated parameter and targets the vendor whose parameter it is -- which is only expressible
because the literal indexer records the model and its sibling argument keys in one row.

The deliberate imprecision is the model scope. The vendor writes "Claude Opus 4.7 and later",
and deciding whether `claude-opus-5` falls inside that needs a version ordering across model
families that no vendor publishes machine-readably. The detector reports the scope rather than
evaluating it, and the severity says so.
"""

from __future__ import annotations

from sync.core import CallSite
from sync.core.protocols import Detector
from sync.detect.parameter_deprecation import ParameterDeprecationDetector
from sync.signals.deprecations import ParameterDeprecation

TEMPERATURE = ParameterDeprecation(
    vendor_id="anthropic",
    parameter="temperature",
    status="Deprecated (Claude Opus 4.7 and later)",
    behavior="Returns a 400 error when set to a non-default value.",
    applies_from="Claude Opus 4.7 and later",
)

BUDGET = ParameterDeprecation(
    vendor_id="anthropic",
    parameter="budget_tokens",
    status="Deprecated",
    behavior="Returns a 400 error.",
    applies_from=None,
    replacement="max_tokens",
)


def _site(*, args, model="claude-opus-5", vendor="anthropic", site_id="cs-1", path="src/a.ts"):
    return CallSite(
        id=site_id, repo_id="r", path=path, line=7, col=4, vendor_id=vendor,
        operation_id=model, symbol="model", args_keys=list(args),
        sdk_version="0.70.0", content_hash="h",
    )


def _scan(sites, deprecations=(TEMPERATURE,)):
    return list(ParameterDeprecationDetector(list(deprecations), list(sites)).scan())


# --- the two facts ----------------------------------------------------------------


def test_a_site_passing_the_parameter_produces_a_finding():
    findings = _scan([_site(args=["model", "temperature", "max_tokens"])])
    assert len(findings) == 1


def test_a_site_not_passing_the_parameter_produces_nothing():
    assert _scan([_site(args=["model", "max_tokens"])]) == []


def test_a_site_belonging_to_another_vendor_is_ignored():
    """The parameter name is not unique. `temperature` is a legitimate argument to plenty of
    APIs, and matching on the name alone would fire on every one of them."""
    assert _scan([_site(args=["model", "temperature"], vendor="openai")]) == []


def test_both_facts_are_required():
    sites = [
        _site(args=["model", "temperature"], vendor="openai", site_id="a"),
        _site(args=["model", "max_tokens"], site_id="b"),
        _site(args=["model", "temperature"], site_id="c"),
    ]
    assert [f.call_site_id for f in _scan(sites)] == ["c"]


# --- what the finding says --------------------------------------------------------


def test_the_rationale_names_the_parameter_the_model_and_the_scope():
    """A reviewer needs all three to decide, because the detector deliberately does not."""
    finding = _scan([_site(args=["model", "temperature"])])[0]

    assert "temperature" in finding.rationale
    assert "claude-opus-5" in finding.rationale
    assert "Claude Opus 4.7 and later" in finding.rationale


def test_the_vendor_wording_is_quoted_not_paraphrased():
    """"Returns a 400 error when set to a non-default value" is the vendor's authority, and it
    is the only authority here -- a paraphrase spends it."""
    finding = _scan([_site(args=["model", "temperature"])])[0]
    assert "400" in finding.rationale


def test_the_rationale_says_a_type_checker_cannot_catch_it():
    """The reason this finding exists at all. Without it a reviewer reasonably asks why the
    compiler did not flag the argument."""
    finding = _scan([_site(args=["model", "temperature"])])[0]
    assert "type-check" in finding.rationale or "type checker" in finding.rationale


def test_an_unevaluated_scope_is_reported_as_deprecation_not_breaking():
    """Severity carries the confidence. The detector cannot tell whether this model is inside
    the scope, so claiming `breaking` would spend trust it has not earned."""
    finding = _scan([_site(args=["model", "temperature"])])[0]
    assert finding.severity == "deprecation"


def test_the_remedy_is_stated():
    findings = _scan(
        [_site(args=["model", "temperature", "budget_tokens"])],
        deprecations=(TEMPERATURE, BUDGET),
    )
    by_param = {f.rationale.split("`")[1]: f for f in findings}

    assert "omit" in by_param["temperature"].rationale.lower()
    assert "max_tokens" in by_param["budget_tokens"].rationale


# --- edges ------------------------------------------------------------------------


def test_a_site_with_no_id_cannot_be_referenced_and_is_skipped():
    """A `Finding` points at a call site by id. Inventing one would produce a finding nothing
    downstream could resolve."""
    assert _scan([_site(args=["model", "temperature"], site_id=None)]) == []


def test_one_site_passing_two_deprecated_parameters_yields_two_findings():
    """One row per problem. A finding naming two parameters is one a reviewer must split by
    hand before acting."""
    findings = _scan(
        [_site(args=["model", "temperature", "budget_tokens"])],
        deprecations=(TEMPERATURE, BUDGET),
    )
    assert len(findings) == 2


def test_no_deprecations_means_no_findings():
    assert _scan([_site(args=["model", "temperature"])], deprecations=()) == []


def test_it_satisfies_the_detector_protocol():
    assert isinstance(ParameterDeprecationDetector([], []), Detector)


def test_scanning_twice_gives_the_same_answer():
    """Idempotence, held to the same standard as every other stage."""
    detector = ParameterDeprecationDetector([TEMPERATURE], [_site(args=["model", "temperature"])])
    first = [f.rationale for f in detector.scan()]
    assert [f.rationale for f in detector.scan()] == first
