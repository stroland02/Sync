"""Which call the mutation attaches to when two of them start at one position.

`_call_at` takes an exact start match, and on a chained call that match is ambiguous: a call and
its receiver begin at the same line and column, so `client.coupons.list(...)` and
`client.coupons.list(...).auto_paging_iter()` both answer to the position the indexer recorded.
It used to break the tie by preferring a call passing an object argument and, failing that, the
longest one -- which is the outer call. So the field the vendor removed from the *operation* was
written into the *pager's* argument list while the label still said the site was affected.

**The rule that replaced the tie-break is the indexer's own shape, not a preference for the
shorter call.** `sync.index.python_lang.index` records a call only when its callee flattens
through `_attribute_chain` to a dotted run of plain identifiers, and
`sync.index.typescript.index` requires the same of `_member_chain`. A chained call's callee has
another call as its object, so neither walk terminates on an identifier and **the outer call is
never indexed at all**. A position the indexer recorded therefore cannot denote it.

That is why the direction generalises rather than fitting these examples. Two calls share a start
position only when one is the other's receiver -- an argument begins after the opening
parenthesis, so nothing in an argument list can start where the call does -- and a callee that
flattens to identifiers contains no call. So at most one call at any position satisfies the rule,
and where none does, the position is one no indexer could have produced.

These tests assert on the mutated source and on the labels rather than on which node `_call_at`
returned, because a test that the shorter node was picked proves nothing about where the field
was written.
"""

from __future__ import annotations

import ast

import pytest

from sync.benchmark.mutate import MUTATION_LITERAL, depends_on_change, generate_pair
from sync.core import CallSite, VendorChange

FIELD = "created"

PY_CALL = "client.coupons.list"
PY_CHAINED = f'coupons = [c for c in {PY_CALL}(params={{"limit": 100}}).auto_paging_iter()]\n'
PY_PLAIN = f'coupons = {PY_CALL}(params={{"limit": 100}})\n'

# The shape `virtual-lab` actually writes, which is where the nine chained call sites in the
# pinned checkouts are: a two-segment client root, and the pager's result handed to `list`. The
# outer `list(` starts at its own column, so the position still names two calls and not three.
PY_CORPUS_CALL = "self.client.customers.list"
PY_CORPUS = (
    f'customers = list({PY_CORPUS_CALL}(params={{"limit": 100}}).auto_paging_iter())\n'
)

TS_CALL = "stripe.charges.list"
TS_CHAINED = f"const rows = await {TS_CALL}({{ limit: 3 }}).autoPagingToArray({{ limit: 5 }});\n"
TS_PLAIN = f"const rows = await {TS_CALL}({{ limit: 3 }});\n"
# Three calls at one position rather than two, so the rule is shown to reach the innermost and
# not merely to have stopped taking the outermost.
TS_THRICE = (
    f"const ids = await {TS_CALL}({{ limit: 3 }}).autoPagingToArray({{ limit: 5 }})"
    ".map((charge) => charge.id);\n"
)


def _change() -> VendorChange:
    """A parameter removal on the operation the *inner* call names."""
    return VendorChange(
        id="vc-1", vendor_id="stripe", from_version="v2320", to_version="v2330",
        kind="request-parameter-removed", operation_id="GetCoupons", path_ptr="/v1/coupons",
        severity="breaking", source="oasdiff",
        raw={"id": "request-parameter-removed",
             "text": f"deleted the `{FIELD}` request parameter"},
    )


def _site(source: str, path: str, needle: str) -> CallSite:
    """Addressed by the position of the inner call, which is the position the indexer records:
    a chained call and its receiver start at the same line and column."""
    index = source.index(needle)
    return CallSite(
        id="cs1", repo_id="fixture", path=path,
        line=source.count("\n", 0, index) + 1,
        col=index - (source.rfind("\n", 0, index) + 1),
        vendor_id="stripe", operation_id="GetCoupons", symbol=needle,
        sdk_version="18.0.0", content_hash="h",
    )


def _pair(source: str, path: str, needle: str):
    site = _site(source, path, needle)
    return generate_pair({path: source}, _change(), [site], targets=["cs1"]), site


def test_a_chained_python_call_takes_the_field_into_the_operation_not_the_pager() -> None:
    """The keyword lands on `list`, which is the call the indexer recorded.

    Parsed as well as compared, because a mutation that is not Python would be a different defect
    wearing the same assertion -- tree-sitter's error recovery would let it through.
    """
    pair, _ = _pair(PY_CHAINED, "src/a.py", PY_CALL)
    mutated = pair.sources["src/a.py"]

    assert mutated == (
        f'coupons = [c for c in {PY_CALL}(params={{"limit": 100}}, {FIELD}={MUTATION_LITERAL})'
        ".auto_paging_iter()]\n"
    )
    assert f".auto_paging_iter({FIELD}=" not in mutated
    assert pair.unreachable == ()
    assert [(label.call_site_id, label.affected) for label in pair.labels] == [("cs1", True)]
    ast.parse(mutated)


def test_the_corpus_chained_shape_takes_the_field_into_the_operation() -> None:
    """The same, on the shape the pinned Python checkout is written in.

    A two-segment client root and the pager's result handed to `list`, which is what nine of
    `virtual-lab`'s twenty-one indexed call sites look like. Distinct from the case above because
    the enclosing `list(` proves the rule selects on the callee's shape rather than on being the
    innermost call in the statement.
    """
    pair, _ = _pair(PY_CORPUS, "src/a.py", PY_CORPUS_CALL)
    mutated = pair.sources["src/a.py"]

    assert mutated == (
        f'customers = list({PY_CORPUS_CALL}(params={{"limit": 100}}, {FIELD}={MUTATION_LITERAL})'
        ".auto_paging_iter())\n"
    )
    assert f".auto_paging_iter({FIELD}=" not in mutated
    assert [(label.call_site_id, label.affected) for label in pair.labels] == [("cs1", True)]
    ast.parse(mutated)


def test_a_chained_typescript_call_takes_the_property_into_the_operation_not_the_pager() -> None:
    """The same in TypeScript, where both calls pass an object literal.

    The old tie-break's first key could not discriminate here -- a pager taking its own options is
    how `autoPagingToArray` is written, so both calls satisfied it and length decided. The callee
    shape separates them where the object argument never could.
    """
    pair, _ = _pair(TS_CHAINED, "src/a.ts", TS_CALL)
    mutated = pair.sources["src/a.ts"]

    assert mutated == (
        f"const rows = await {TS_CALL}({{ {FIELD}: {MUTATION_LITERAL}, limit: 3 }})"
        ".autoPagingToArray({ limit: 5 });\n"
    )
    assert f".autoPagingToArray({{ {FIELD}:" not in mutated
    assert pair.unreachable == ()
    assert [(label.call_site_id, label.affected) for label in pair.labels] == [("cs1", True)]


def test_three_calls_at_one_position_still_attach_to_the_operation() -> None:
    """Innermost, not second-longest.

    A two-call chain cannot tell "prefer the receiver" from "prefer the shorter", and a rule that
    only stepped in one link would leave a longer chain mutating the wrong call.
    """
    pair, _ = _pair(TS_THRICE, "src/a.ts", TS_CALL)
    mutated = pair.sources["src/a.ts"]

    assert mutated == (
        f"const ids = await {TS_CALL}({{ {FIELD}: {MUTATION_LITERAL}, limit: 3 }})"
        ".autoPagingToArray({ limit: 5 }).map((charge) => charge.id);\n"
    )
    assert f".autoPagingToArray({{ {FIELD}:" not in mutated
    assert pair.unreachable == ()


@pytest.mark.parametrize(
    "path,source,call",
    [("src/a.py", PY_PLAIN, PY_CALL), ("src/a.ts", TS_PLAIN, TS_CALL)],
    ids=["python", "typescript"],
)
def test_the_same_call_unchained_is_mutated_where_the_change_lands(path, source, call) -> None:
    """The control, and it is what makes the cases above a statement about chaining.

    Same source, same position, same change, with the trailing call removed. It asserted the same
    text before the tie-break was replaced and asserts it after, which is the evidence the rule
    did not buy the chained case at the ordinary one's expense.
    """
    pair, _ = _pair(source, path, call)
    mutated = pair.sources[path]

    if path.endswith(".py"):
        assert mutated == f'coupons = {call}(params={{"limit": 100}}, {FIELD}={MUTATION_LITERAL})\n'
    else:
        assert mutated == (
            f"const rows = await {call}({{ {FIELD}: {MUTATION_LITERAL}, limit: 3 }});\n"
        )
    assert pair.unreachable == ()


@pytest.mark.parametrize(
    "path,source,call",
    [("src/a.py", PY_CHAINED, PY_CALL), ("src/a.ts", TS_CHAINED, TS_CALL)],
    ids=["python", "typescript"],
)
def test_the_audit_half_agrees_once_the_mutation_has_landed(path, source, call) -> None:
    """`depends_on_change` reads the mutated tree and finds the dependency on the operation.

    It agreed before this change too, and that agreement was worthless: it resolved the position
    through the same `_call_at`, so it asked about the pager and truthfully answered that the
    pager carried the field. Both halves were wrong about the same call. They are now right about
    the same call, which is not the same thing as the guard having been fixed -- the two tests
    below are what make it a check rather than a mirror.
    """
    pair, site = _pair(source, path, call)

    assert depends_on_change(pair.sources, _change(), site) is True


@pytest.mark.parametrize(
    "path,source",
    [
        ("src/a.py",
         f'coupons = [c for c in {PY_CALL}(params={{"limit": 100}})'
         f".auto_paging_iter({FIELD}='x')]\n"),
        ("src/a.ts",
         f"const rows = await {TS_CALL}({{ limit: 3 }})"
         f".autoPagingToArray({{ {FIELD}: 'x', limit: 5 }});\n"),
    ],
    ids=["python", "typescript"],
)
def test_a_field_the_pager_carries_is_not_the_call_sites_own_dependency(path, source) -> None:
    """A dependency belonging to the pager is not one the vendor's change can break.

    Removing `created` from `GET /v1/coupons` cannot break `auto_paging_iter(created=...)`. The
    audit half used to answer True here, because the position resolved to the pager; answering
    False is the audit half becoming a check on the label instead of a restatement of it.
    """
    needle = PY_CALL if path.endswith(".py") else TS_CALL
    assert depends_on_change({path: source}, _change(), _site(source, path, needle)) is False


@pytest.mark.parametrize(
    "path,source",
    [
        ("src/a.py",
         f'coupons = [c for c in {PY_CALL}(params={{"limit": 100}}, {FIELD}=1)'
         ".auto_paging_iter()]\n"),
        ("src/a.ts",
         f"const rows = await {TS_CALL}({{ {FIELD}: 1, limit: 3 }})"
         ".autoPagingToArray({ limit: 5 });\n"),
    ],
    ids=["python", "typescript"],
)
def test_a_site_already_passing_the_field_on_the_operation_is_refused(path, source) -> None:
    """The exactness guard reaches a chained site now, and refusing is the whole of its job.

    `generate_pair`'s refusal exists because a label is only derived from the mutation while the
    mutation is the sole source of the dependency. Resolving to the pager made the guard blind on
    every chained site: it asked whether `auto_paging_iter` passed `created`, found it did not,
    and built a pair whose target already carried the change. That pair labels a site affected on
    evidence the generator did not write.
    """
    site = _site(source, path, PY_CALL if path.endswith(".py") else TS_CALL)
    with pytest.raises(ValueError, match="already depends"):
        generate_pair({path: source}, _change(), [site], targets=["cs1"])
