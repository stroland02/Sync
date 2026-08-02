"""Which call the mutation attaches to when two of them start at one position.

`_call_at` takes an exact start match, which is right, and then breaks a tie by preferring a call
that passes an object argument and, failing that, **the longest one**. On a chained call the
longest one is the outer call -- `client.coupons.list(...)` and
`client.coupons.list(...).auto_paging_iter()` start at the same line and column, and the pager is
the longer of the two. So the field the vendor removed from the *operation* is written into the
*pager's* argument list, and the label still says the site is affected.

That is a mislabel, and a mislabel is the one defect class this instrument cannot absorb.
`sync.benchmark.mutate`'s own docstring says the label is exact only while the mutation is the sole
source of the dependency; here the mutation is the source of a dependency on a different call.
Removing the `created` parameter from `GET /v1/coupons` cannot break `auto_paging_iter(created=…)`,
so `affected=True` is a break the tree does not carry, and a binder that declines is scored as
having missed it.

**These tests pin the defect rather than endorse it.** Each asserts what the generator does today
so the claim in `docs/superpowers/reports/2026-07-30-the-corpus-scores-one-kind.md` cannot rot into
folklore, and each will fail the day `_call_at` learns to prefer the call the indexer recorded --
which is the point. Whoever makes that change replaces these assertions deliberately, and the
frozen corpus is regenerated in the same commit, because changing which call is mutated changes
every pair's tree.

Why it is latent rather than live: no committed specification names an operation whose call sites
chain. It becomes live the moment one does, and the operations it would arrive through are named in
that report -- `virtual-lab`'s five list operations, every one of them written
`client.X.list(params={...}).auto_paging_iter()`.
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

TS_CALL = "stripe.charges.list"
TS_CHAINED = f"const rows = await {TS_CALL}({{ limit: 3 }}).autoPagingToArray({{ limit: 5 }});\n"
TS_PLAIN = f"const rows = await {TS_CALL}({{ limit: 3 }});\n"


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


def test_a_chained_python_call_takes_the_field_into_the_pager_not_the_operation() -> None:
    """The keyword lands on `auto_paging_iter`, and the label says the site is affected anyway.

    Parsed as well as compared, because a mutation that is not Python would be a different defect
    wearing the same assertion -- tree-sitter's error recovery would let it through.
    """
    pair, _ = _pair(PY_CHAINED, "src/a.py", PY_CALL)
    mutated = pair.sources["src/a.py"]

    assert mutated == (
        f'coupons = [c for c in {PY_CALL}(params={{"limit": 100}})'
        f".auto_paging_iter({FIELD}={MUTATION_LITERAL})]\n"
    )
    assert f'{PY_CALL}(params={{"limit": 100}}, {FIELD}=' not in mutated
    assert pair.unreachable == ()
    assert [(label.call_site_id, label.affected) for label in pair.labels] == [("cs1", True)]
    ast.parse(mutated)


def test_a_chained_typescript_call_takes_the_property_into_the_pager_not_the_operation() -> None:
    """The same in TypeScript, and the object-argument preference does not save it.

    That preference picks the inner call only while the outer one passes no object literal. A
    pager taking its own options -- which is how `autoPagingToArray` is written -- puts both calls
    on equal footing and the length tie-break decides.
    """
    pair, _ = _pair(TS_CHAINED, "src/a.ts", TS_CALL)
    mutated = pair.sources["src/a.ts"]

    assert mutated == (
        f"const rows = await {TS_CALL}({{ limit: 3 }})"
        f".autoPagingToArray({{ {FIELD}: {MUTATION_LITERAL}, limit: 5 }});\n"
    )
    assert f"{TS_CALL}({{ {FIELD}:" not in mutated
    assert pair.unreachable == ()
    assert [(label.call_site_id, label.affected) for label in pair.labels] == [("cs1", True)]


@pytest.mark.parametrize(
    "path,source,call",
    [("src/a.py", PY_PLAIN, PY_CALL), ("src/a.ts", TS_PLAIN, TS_CALL)],
    ids=["python", "typescript"],
)
def test_the_same_call_unchained_is_mutated_where_the_change_lands(path, source, call) -> None:
    """The control, and it is what makes the two above a statement about chaining.

    Same source, same position, same change, with the trailing call removed: the field goes into
    the operation's own argument list. So nothing about the parameter kind or the shape of these
    calls is the cause -- the second call starting at the same position is.
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
def test_the_audit_half_cannot_catch_the_misattachment(path, source, call) -> None:
    """`depends_on_change` agrees, which is why nothing has caught this.

    The audit half exists so a label can be checked against what the tree says rather than against
    what the generator recorded, and it is the one guard that could have flagged a mislabel. It
    cannot flag this one: it resolves the position through the same `_call_at`, so it asks about
    the pager too and truthfully answers that the pager carries the field.

    A cross-check strong enough to catch this has to resolve the position the way the indexer does,
    and `mutate.py` deliberately imports nothing from `sync.index` -- so the fix belongs in
    `_call_at`'s tie-break rather than in a second opinion here.
    """
    pair, site = _pair(source, path, call)

    assert depends_on_change(pair.sources, _change(), site) is True
