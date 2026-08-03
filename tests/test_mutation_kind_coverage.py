"""Which change kinds the generator can actually invert, and which the corpus rule may omit.

`SUPPORTED_KINDS` is a declaration. Whether a kind in it produces a well-formed pair is a
measurement, and nothing measured it: three kinds are declared, seventeen committed specifications
name two of them, and the reason the third is omitted lives in a sentence in
`scripts/build_corpus_specs.py` and another in `benchmark/corpus/README.md` --

    The third supported kind, `request-parameter-removed`, mutates identically to the first and
    would add pairs without adding information.

-- with no test anywhere behind either. That sentence is what makes the omission honest rather
than an oversight, and it is exactly the kind of claim that rots: `_mutate` dispatches on
`change.kind in REQUEST_KINDS`, so the day somebody gives the two request kinds different branches
the stated reason becomes false and the corpus goes on omitting the kind for a reason that no
longer holds.

So the identity is asserted rather than restated, on the pair the generator produces -- its
sources, its labels and its unreachable set -- and never on which branch was taken. A test that
watched the dispatch would pass through a branch that produced a different tree.

Why the depth test is here rather than beside the score
-------------------------------------------------------
`sync.benchmark.score`'s docstring rests a load-bearing caveat on the corpus being flat: a false
positive needs a *partial* path match, "and against a flat change it cannot arise at all". The
generator is what makes the corpus flat, and it does so by discarding depth --
`generate_pair` writes `changed_field`, the deepest segment, as a top-level key. A specification
naming `metadata/charge` therefore mutates identically to one naming `charge`, while the detector
anchors its match at `metadata` and correctly declines. The pair scores a miss for a break the
tree does not carry in the shape the change describes, which is a mislabel of the class this
corpus has twice refused to certify.

That is a property of the mutation and not of the scorer, so it is pinned where the mutation is.
`docs/superpowers/reports/2026-07-30-the-corpus-scores-one-kind.md` carries the measurement and
what widening the generator would take.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
import yaml

from scripts.build_corpus_specs import KINDS
from sync.benchmark.mutate import (
    MUTATION_LITERAL,
    SUPPORTED_KINDS,
    depends_on_change,
    generate_pair,
)
from sync.core import CallSite, VendorChange
from sync.signals.oasdiff import changed_path

SPECS = Path(__file__).resolve().parents[1] / "benchmark" / "corpus" / "pairs"

CALL = "stripe.paymentIntents.create"
FIELD = "receipt_email"

# One input every supported kind can mutate: a call passing an object argument, whose result is
# bound to a plain name. The request kinds write into the argument and the response kind hangs a
# guard off the name, so a pair from any of the three is comparable against a pair from any other.
TS_SOURCE = f"const intent = await {CALL}({{ amount: 1 }});\n"
PY_SOURCE = f"intent = {CALL.replace('paymentIntents', 'payment_intents')}(amount=1)\n"
PY_CALL = CALL.replace("paymentIntents", "payment_intents")


def _change(kind: str, token: str = FIELD) -> VendorChange:
    """A change whose property path is whatever `token` backticks.

    `changed_path` splits that token on `/`, so `metadata/receipt_email` is a nested change and
    `receipt_email` is a flat one. The wording around the token follows the kind because that is
    how oasdiff writes each -- a parameter is "deleted", a property "removed" -- and neither
    `changed_path` nor anything downstream reads a word of it.
    """
    if kind == "request-parameter-removed":
        text = f"deleted the `{token}` request parameter"
    elif kind == "request-property-removed":
        text = f"removed the request property `{token}` from POST /v1/payment_intents"
    else:
        text = f"removed the optional property `{token}` from the response"
    return VendorChange(
        id="vc-1", vendor_id="stripe", from_version="v2320", to_version="v2330", kind=kind,
        operation_id="PostPaymentIntents", path_ptr="/v1/payment_intents", severity="breaking",
        source="oasdiff", raw={"id": kind, "text": text},
    )


def _site(sources: dict[str, str], path: str, needle: str) -> CallSite:
    """Addressed by position, computed from the source so an edit cannot strand a test."""
    source = sources[path]
    index = source.index(needle)
    return CallSite(
        id="cs1", repo_id="fixture", path=path,
        line=source.count("\n", 0, index) + 1,
        col=index - (source.rfind("\n", 0, index) + 1),
        vendor_id="stripe", operation_id="PostPaymentIntents", symbol=needle,
        sdk_version="18.0.0", content_hash="h",
    )


def _typescript_pair(kind: str, token: str = FIELD):
    sources = {"src/a.ts": TS_SOURCE}
    site = _site(sources, "src/a.ts", CALL)
    return generate_pair(sources, _change(kind, token), [site], targets=["cs1"]), site


def _python_pair(kind: str, token: str = FIELD):
    sources = {"src/a.py": PY_SOURCE}
    site = _site(sources, "src/a.py", PY_CALL)
    return generate_pair(sources, _change(kind, token), [site], targets=["cs1"]), site


# --- what the generator can invert, measured rather than declared -------------------


@pytest.mark.parametrize("kind", sorted(SUPPORTED_KINDS))
def test_every_declared_kind_inverts_into_a_tree_the_audit_half_reads_back(kind) -> None:
    """The measurement `SUPPORTED_KINDS` only claims.

    A kind added to the set without an inversion branch reaches `_mutate`, falls through to the
    response path, and produces whatever that path happens to do -- or nothing, in which case the
    target comes back unreachable, every label says unaffected, and the pair scores as a flawless
    run over an empty positive set. Both outcomes are silent, so the assertion is on the pair: the
    tree changed, the target is labelled affected, nothing was unreachable, and
    `depends_on_change` -- which reads the fact back out of the source rather than off the edit
    record -- agrees.
    """
    pair, site = _typescript_pair(kind)

    assert pair.sources["src/a.ts"] != TS_SOURCE
    assert pair.unreachable == ()
    assert [(label.call_site_id, label.affected) for label in pair.labels] == [("cs1", True)]
    assert depends_on_change(pair.sources, _change(kind), site) is True


@pytest.mark.parametrize("kind", sorted(k for k in SUPPORTED_KINDS if k.startswith("request-")))
def test_a_request_kind_writes_the_field_into_the_call_the_change_breaks(kind) -> None:
    """The shape of the edit, not merely that there was one.

    A request change is judged against what the call passes, so the inversion has to make the call
    pass the removed field. Asserted as the emitted text in both spellings the generator has --
    an object-literal entry in TypeScript, a keyword argument in Python -- because those are two
    branches of `_insert_property` and a kind reaching only one of them is a pair that breaks one
    language.
    """
    typescript, _ = _typescript_pair(kind)
    python, _ = _python_pair(kind)

    assert typescript.sources["src/a.ts"] == (
        f"const intent = await {CALL}({{ {FIELD}: {MUTATION_LITERAL}, amount: 1 }});\n"
    )
    assert python.sources["src/a.py"] == (
        f"intent = {PY_CALL}(amount=1, {FIELD}={MUTATION_LITERAL})\n"
    )
    # Parsed rather than only compared: tree-sitter's error recovery would let a mutation that is
    # not Python still be labelled affected.
    ast.parse(python.sources["src/a.py"])


@pytest.mark.parametrize("kind", sorted(k for k in SUPPORTED_KINDS if k.startswith("response-")))
def test_a_response_kind_makes_the_caller_read_the_field_off_the_result(kind) -> None:
    """The other side's shape. A response change is judged against what the call reads, so the
    inversion has to make something read the removed field off the bound result."""
    typescript, _ = _typescript_pair(kind)

    assert typescript.sources["src/a.ts"] == (
        f"const intent = await {CALL}({{ amount: 1 }});"
        f" if (intent.{FIELD} === undefined) throw new Error('{FIELD} missing');\n"
    )


# --- the identity the corpus rule's omission rests on -------------------------------


def test_the_two_request_kinds_produce_the_same_pair_in_both_languages() -> None:
    """`request-parameter-removed` and `request-property-removed`, over one input.

    This is the sentence `scripts/build_corpus_specs.py` states and the corpus acts on. Equality
    over the whole pair rather than over the source alone: a kind that wrote the same tree and
    labelled it differently would be a different pair, and the label is what a scorer reads.

    Both languages, because the two request spellings are separate branches and an identity that
    held in one of them would still leave the rule proposing pairs that differ.
    """
    parameter_ts, _ = _typescript_pair("request-parameter-removed")
    property_ts, _ = _typescript_pair("request-property-removed")
    parameter_py, _ = _python_pair("request-parameter-removed")
    property_py, _ = _python_pair("request-property-removed")

    assert parameter_ts.sources == property_ts.sources
    assert parameter_ts.labels == property_ts.labels
    assert parameter_ts.unreachable == property_ts.unreachable
    assert parameter_py.sources == property_py.sources
    assert parameter_py.labels == property_py.labels
    assert parameter_py.unreachable == property_py.unreachable


def test_the_selection_rule_omits_only_kinds_that_duplicate_one_it_keeps() -> None:
    """Why seventeen specifications name two kinds while the generator declares three.

    The corpus rule is allowed to omit a supported kind exactly when the pair it would produce is
    a pair the corpus already holds. Anything else omitted is coverage nobody decided to drop, so
    this fails naming the kind rather than leaving the gap to be noticed by reading two
    docstrings.

    Symmetrical in the other direction too: a kind `KINDS` proposes and the generator cannot
    invert would make every specification over it refuse as `unsupported-change-kind`.
    """
    assert set(KINDS) <= SUPPORTED_KINDS

    kept = {kind: _typescript_pair(kind)[0] for kind in KINDS}
    for kind in sorted(SUPPORTED_KINDS - set(KINDS)):
        pair, _ = _typescript_pair(kind)
        duplicates = [name for name, other in kept.items() if other == pair]
        assert duplicates, (
            f"{kind} is supported, is not proposed by the corpus selection rule, and produces a "
            f"pair no proposed kind produces -- so the corpus omits coverage rather than a "
            f"duplicate"
        )


def test_every_committed_specification_names_a_kind_the_rule_proposes() -> None:
    """A specification is not a test, and a typo in `change.kind` fails only when somebody runs
    the corpus by hand -- as `unsupported-change-kind`, one refused pair among seventeen, in a
    report nobody reads on a green run.

    Read from the committed files rather than from the filenames. The filename encodes the kind by
    convention and `change.kind` is the authority, so a specification renamed without its field
    being changed -- or the reverse -- is the drift this catches.
    """
    specs = sorted(SPECS.glob("*.yaml"))
    assert specs, f"no corpus specifications under {SPECS}"

    for path in specs:
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        kind = spec["change"]["kind"]
        assert kind in KINDS, f"{path.name} names {kind}, which the selection rule does not propose"
        assert path.stem.endswith(f"-{kind}"), (
            f"{path.name} is named for a kind its `change.kind` does not hold ({kind})"
        )


# --- the depth the generator discards ------------------------------------------------


@pytest.mark.parametrize(
    "token",
    [FIELD, f"metadata/{FIELD}", f"data/items/{FIELD}"],
    ids=["flat", "one-level", "two-levels"],
)
def test_a_nested_change_is_mutated_as_its_leaf_at_the_top_level(token) -> None:
    """The generator cannot express a nested change, and the corpus is flat because of it.

    `changed_path` keeps every segment and `changed_field` takes the last, which is what the
    mutation writes -- so three changes at three depths produce one tree. The label still says
    affected and `depends_on_change` still agrees, because both read the leaf; only the detector
    sees the difference, and it anchors its match at the outermost segment and correctly declines.

    Measured end to end while establishing this: `turbo-PostRefunds-request-property-removed` with
    its field changed from `charge` to `metadata/charge` scores recall 0.0 at n=1 with precision
    unmeasured -- a miss manufactured by the corpus, not made by the binder. That is why no
    committed specification names a nested field and why adding one is a generator change first.
    """
    pair, _ = _typescript_pair("request-property-removed", token)

    assert changed_path(_change("request-property-removed", token)) == token.split("/")
    assert pair.sources["src/a.ts"] == (
        f"const intent = await {CALL}({{ {FIELD}: {MUTATION_LITERAL}, amount: 1 }});\n"
    )
