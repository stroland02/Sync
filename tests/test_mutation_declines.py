"""Every input the mutation engine declines to break, and what the pair says afterwards.

`sync.benchmark.mutate` is part of the instrument rather than of the product, and that changes
what a defect costs. A wrong answer in a detector loses a finding and the number falls. A wrong
answer here moves the *label*, and a moved label makes the benchmark agree with whatever the
binder happens to do -- which is the failure `2026-07-29-sync-verification-regime.md` records
having already happened once, when recall read 1.0000 against a corpus that shared the binder's
blind spot.

So each decline is asserted against the **resulting mutated source and the resulting label**,
never against an internal call. A decline that is right and a decline that is a mislabel look
identical from the inside; they differ only in what the pair says, which is the thing a scorer
reads.

Two of the statements exercised here are not declines at all -- they are the two rewrite branches
that insert into an *empty* container, which no corpus specification reaches because every site
the frozen corpus mutates already passes something. They are covered beside the declines because
a rewrite nobody has run is a label nobody has checked.
`docs/superpowers/reports/2026-07-29-mutation-engine-declines.md` carries the per-statement
argument, including the eight statements no input reaches and why.
"""

from __future__ import annotations

import ast

import pytest

from sync.benchmark.mutate import MUTATION_LITERAL, depends_on_change, generate_pair
from sync.core import CallSite, VendorChange

CALL = "client.customers.list"


def _change(kind: str = "response-property-removed", field: str | None = "has_more") -> VendorChange:
    """A change carrying the field in the place `changed_field` reads it from: the first
    backticked token of oasdiff's free text. `field=None` writes a record naming none, which is
    the only way a supported kind arrives with nothing to insert."""
    if field is None:
        text = "removed a request property from POST /v1/customers"
    elif kind in ("request-property-removed", "request-parameter-removed"):
        text = f"removed the request property `{field}` from GET /v1/customers"
    else:
        text = f"removed the optional property `{field}` from the response"
    return VendorChange(
        id="vc-1", vendor_id="stripe", from_version="2026-05-01", to_version="2026-11-01",
        kind=kind, operation_id="GetCustomers", path_ptr="/v1/customers", severity="breaking",
        source="oasdiff", raw={"id": kind, "text": text},
    )


def _site(sources: dict[str, str], path: str, site_id: str = "cs1", needle: str = CALL,
          offset: int = 0) -> CallSite:
    """Addressed by position, computed from the source so an edit cannot strand a test.

    `offset` shifts the recorded column away from the call, which is how a position that names no
    call is written without hand-counting one.
    """
    source = sources[path]
    index = source.index(needle) + offset
    return CallSite(
        id=site_id, repo_id="fixture", path=path,
        line=source.count("\n", 0, index) + 1,
        col=index - (source.rfind("\n", 0, index) + 1),
        vendor_id="stripe", operation_id="GetCustomers", symbol="stripe.customers.list",
        sdk_version="18.0.0", content_hash="h",
    )


def _labels(pair) -> dict[str, bool]:
    return {label.call_site_id: label.affected for label in pair.labels}


# --- the one refusal that stops a scored run ---------------------------------------


def test_a_supported_kind_naming_no_field_is_refused_rather_than_left_unmutated() -> None:
    """`mutate.py:210`. A kind the generator can invert, arriving with nothing to invert.

    Declining here would produce an unmutated tree whose every label says unaffected, and the
    detector's findings would then read as hallucinations rather than as a generator that had
    nothing to write. The refusal names the change so a corpus specification can be fixed.
    """
    sources = {"src/a.ts": f"const c = {CALL}({{ limit: 3 }});\n"}

    with pytest.raises(ValueError, match="vc-1 names no field"):
        generate_pair(sources, _change("request-property-removed", field=None),
                      [_site(sources, "src/a.ts")], targets=["cs1"])


def test_the_refusal_is_not_reachable_through_the_audit_half() -> None:
    """`mutate.py:281`, the same input one function over.

    `depends_on_change` answers a question about a tree rather than producing one, so it has no
    label to protect and returns False instead of raising. The two contracts are deliberately
    different and this pins the difference: a fieldless change breaks nothing, so nothing depends
    on it.
    """
    sources = {"src/a.ts": f"const c = {CALL}({{ limit: 3 }});\n"}
    site = _site(sources, "src/a.ts")

    assert depends_on_change(sources, _change("request-property-removed", field=None), site) is False


def test_the_audit_half_declines_a_file_this_generator_cannot_parse() -> None:
    """`mutate.py:281` by its other clause. A suffix `_MUTABLE_LANGUAGES` does not name has no
    grammar to read the dependency out of, and False is the honest answer: nothing was written
    into it."""
    sources = {"lib/client.rb": f"c = {CALL}()\n"}
    site = _site(sources, "lib/client.rb")

    assert depends_on_change(sources, _change(), site) is False


# --- declines that produce a pair, and are countable -------------------------------


def test_a_target_in_a_file_this_generator_cannot_parse_is_named_unreachable() -> None:
    """`mutate.py:239-240`. The decline the corpus meets, and the one a caller can count.

    `unreachable` is the only decline in this module that reaches an artifact:
    `score.py` carries it onto `ScoredPair.unreachable_targets` and `scripts/score_corpus.py`
    prints a per-pair column and then names every one. The label is unaffected, which is honest
    -- nothing broke that site -- and it is the label a binder correctly finding the site would
    be charged a false positive for, so it has to be countable rather than merely correct.
    """
    sources = {"lib/client.rb": f"c = {CALL}()\n"}
    pair = generate_pair(sources, _change(), [_site(sources, "lib/client.rb")], targets=["cs1"])

    assert pair.unreachable == ("cs1",)
    assert _labels(pair) == {"cs1": False}
    assert pair.sources == sources


def test_an_untargeted_site_in_an_unparseable_file_does_not_refuse_the_whole_tree() -> None:
    """`mutate.py:226`, the pre-scan's skip, and it guards a different thing from 239.

    Every site in the tree is checked for an existing dependency before anything is edited,
    because a site that already carries the field cannot be labelled from a mutation that did not
    make it. A file with no grammar cannot be asked, and the alternative to skipping it is
    refusing the pair -- which would mean one Ruby file anywhere in a real checkout costs the
    whole specification.

    The Ruby call passes a hash, and `{ limit: 3 }` is byte-identical in Ruby and TypeScript. So
    reading the file under any grammar at all -- rather than declining to read it -- finds `limit`
    declared and refuses the tree. That is what makes this a measurement of the skip rather than
    of a file the substituted grammar happens to answer the same way about.
    """
    sources = {
        "src/a.ts": f"const c = {CALL}({{ expand: ['data'] }});\n",
        "lib/client.rb": f"c = {CALL}({{ limit: 3 }})\n",
    }
    sites = [_site(sources, "src/a.ts", "cs-ts"), _site(sources, "lib/client.rb", "cs-rb")]

    pair = generate_pair(sources, _change("request-property-removed", "limit"), sites,
                         targets=["cs-ts"])

    assert pair.unreachable == ()
    assert _labels(pair) == {"cs-ts": True, "cs-rb": False}
    assert pair.sources["lib/client.rb"] == sources["lib/client.rb"]


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("src/a.ts", f"const c = wrapper({CALL}());\n"),
        ("src/a.py", f"c = wrapper({CALL}())\n"),
    ],
    ids=["typescript", "python"],
)
def test_a_recorded_position_naming_no_call_is_unreachable_in_both_languages(path, body) -> None:
    """`mutate.py:440`, and `291` and `321` which are the two callers reading its None.

    `_call_at` matches a call's start exactly and will not fall back to a merely-containing one,
    because guessing which call was meant would put the label on a site nobody chose. Both
    readers of that None decline rather than raise: the audit half answers False, and the
    mutation half answers None, which the caller records as a target it did not break.

    The position is deliberately one byte inside a real call, and that call is nested in another,
    so a fallback of any kind has two calls to choose from and both are wrong. A fixture holding
    no call at all would leave nothing for a fallback to find, and would pin the return value
    without pinning the exactness the docstring rests on.
    """
    sources = {path: body}
    site = _site(sources, path, offset=1)

    pair = generate_pair(sources, _change(), [site], targets=["cs1"])

    assert pair.unreachable == ("cs1",)
    assert _labels(pair) == {"cs1": False}
    assert pair.sources == sources
    assert depends_on_change(sources, _change(), site) is False


# --- declines because the result is not bound to a plain name ----------------------


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("src/a.ts", "const { data } = " + CALL + "();\n"),
        ("src/a.ts", "const [first] = " + CALL + "();\n"),
        ("src/a.ts", "order.page = " + CALL + "();\n"),
        ("src/a.py", "a, b = " + CALL + "()\n"),
        ("src/a.py", "order.page = " + CALL + "()\n"),
        ("src/a.py", "cache['k'] = " + CALL + "()\n"),
    ],
    ids=["ts-object-pattern", "ts-array-pattern", "ts-property", "py-tuple", "py-attribute",
         "py-subscript"],
)
def test_a_result_bound_to_something_other_than_a_name_is_unreachable(path, body) -> None:
    """`mutate.py:531` for TypeScript and `564` for Python.

    The guard the response mutation needs is `<name>.<field>`, so the binding has to hand the
    result to a plain identifier. A destructuring pattern binds the *fields*, and a property
    target binds something whose lifetime is the object's rather than the call's -- which is the
    reason `_TS_BINDING_FORMS` admits `assignment_expression` and then refuses this case, rather
    than not admitting it.

    Refusing is what keeps the label derivable. Writing `data.has_more` off a destructured name
    manufactures a labelled positive no correct binder can find, which is exactly the mislabel
    that forced recall to 0.8000 before it was fixed.
    """
    sources = {path: body}
    pair = generate_pair(sources, _change(), [_site(sources, path)], targets=["cs1"])

    assert pair.unreachable == ("cs1",)
    assert _labels(pair) == {"cs1": False}
    assert pair.sources == sources


@pytest.mark.parametrize(
    "body",
    [CALL + "() = 1;\n", "(" + CALL + "()) = 1;\n", CALL + "()! = 1;\n",
     CALL + "() as any = 1;\n"],
    ids=["bare", "parenthesised", "non-null", "as-expression"],
)
def test_a_typescript_call_written_as_an_assignment_target_is_unreachable(body) -> None:
    """`mutate.py:528`, the identity half of the TypeScript binding walk.

    Assigning to a call's result is something `tsc` rejects and tree-sitter parses, wrapping the
    call in a zero-width `non_null_expression` so that an `assignment_expression` becomes the
    call's grandparent through a kind `_RESULT_WRAPPERS` calls transparent. The wrapper check
    therefore does not stop it and the identity check does: the call is the assignment's `left`,
    not its `right`, so no name receives the result and there is nothing to hang a guard off.

    The parenthesised, non-null and `as` spellings are here because each reaches the same
    statement through a different wrapper, and a narrower `_RESULT_WRAPPERS` would silently move
    which of them lands on the identity check rather than on the wrapper check.
    """
    sources = {"src/a.ts": body}
    pair = generate_pair(sources, _change(), [_site(sources, "src/a.ts")], targets=["cs1"])

    assert pair.unreachable == ("cs1",)
    assert _labels(pair) == {"cs1": False}
    assert pair.sources == sources


# --- the two rewrites the corpus never reaches ------------------------------------


def test_an_empty_typescript_object_literal_takes_the_property_with_no_separator() -> None:
    """`mutate.py:346`. The leading-insertion branch for a literal that has no entry to lead.

    `{}` needs no comma and `{ limit: 3 }` does, and the two are one branch apart. Nothing in the
    frozen corpus passes an empty literal, so this rewrite has produced no scored label and its
    output is asserted here rather than inferred from the covered sibling.
    """
    sources = {"src/a.ts": f"const c = {CALL}({{}});\n"}
    change = _change("request-property-removed", "limit")
    site = _site(sources, "src/a.ts")

    pair = generate_pair(sources, change, [site], targets=["cs1"])

    assert pair.sources["src/a.ts"] == (
        f"const c = {CALL}({{ limit: {MUTATION_LITERAL} }});\n"
    )
    assert _labels(pair) == {"cs1": True}
    assert depends_on_change(pair.sources, change, site) is True


def test_an_empty_python_dictionary_takes_the_property_as_a_string_key() -> None:
    """`mutate.py:346` again, through the Python spelling of a mapping literal.

    One statement, two grammars, and the key is quoted in one and bare in the other -- which is
    why the same branch is asserted twice rather than parametrised over a language name.
    """
    sources = {"src/a.py": f"c = {CALL}({{}})\n"}
    change = _change("request-property-removed", "limit")
    site = _site(sources, "src/a.py")

    pair = generate_pair(sources, change, [site], targets=["cs1"])

    assert pair.sources["src/a.py"] == f'c = {CALL}({{ "limit": {MUTATION_LITERAL} }})\n'
    assert _labels(pair) == {"cs1": True}
    assert depends_on_change(pair.sources, change, site) is True
    ast.parse(pair.sources["src/a.py"])


def test_a_python_call_with_no_arguments_takes_the_keyword_with_no_separator() -> None:
    """`mutate.py:374`. The trailing-insertion branch for an argument list that is empty.

    `create()` needs no comma and `create(other)` does. The insertion is trailing rather than
    leading because Python forbids a positional argument after a keyword one, so this is the
    branch where the two spellings coincide and the comma reasoning the leading form avoids is
    paid for nothing. Parsed with `ast` rather than only compared, because tree-sitter's error
    recovery would let a mutation that is not Python still be labelled affected.
    """
    sources = {"src/a.py": f"c = {CALL}()\n"}
    change = _change("request-property-removed", "limit")
    site = _site(sources, "src/a.py")

    pair = generate_pair(sources, change, [site], targets=["cs1"])

    assert pair.sources["src/a.py"] == f"c = {CALL}(limit={MUTATION_LITERAL})\n"
    assert _labels(pair) == {"cs1": True}
    assert depends_on_change(pair.sources, change, site) is True
    ast.parse(pair.sources["src/a.py"])


# --- what the collision guard actually guards ------------------------------------


def test_a_site_already_naming_the_field_refuses_the_tree_rather_than_relabelling_it() -> None:
    """`MUTATION_LITERAL` colliding with real source is not what would go wrong.

    The label claims a dependency on a *field*, and the audit half reads the field name back out
    of the tree; the literal is never matched on by anything. So the collision that could move a
    label is a call site that already declares the field, and that is refused for the whole tree
    by name -- loudly, before any pair exists. A repository that happened to pass
    `'sync-benchmark'` as some other field's value changes no label at all, which this asserts in
    the same test so the two cannot be confused.
    """
    sources = {"src/a.ts": f"const c = {CALL}({{ limit: 3 }});\n"}
    change = _change("request-property-removed", "limit")

    with pytest.raises(ValueError, match="already depends on `limit`"):
        generate_pair(sources, change, [_site(sources, "src/a.ts")], targets=["cs1"])

    coincidence = {"src/a.ts": f"const c = {CALL}({{ expand: {MUTATION_LITERAL} }});\n"}
    site = _site(coincidence, "src/a.ts")
    pair = generate_pair(coincidence, change, [site], targets=["cs1"])

    assert _labels(pair) == {"cs1": True}
    assert depends_on_change(pair.sources, change, site) is True
