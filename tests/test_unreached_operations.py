"""The operations a specification declares that no extracted symbol reaches.

M3-W104. The decline channel M3-W100 built found a loss no coverage number would have: the
Anthropic SDK sends `GET /v1/messages/batches/{message_batch_id}/results` through a route it reads
out of an earlier response -- `path_template(batch.results_url, ...)` in Python,
`this._client.get(batch.results_url, ...)` in TypeScript -- so neither reader can state the route
and neither produces a symbol for it. The specification declares the operation. **Both flavours
lose it, independently**, which is what makes it a fact about how the vendor builds the SDK rather
than a limit of either reader.

What that costs is not the coverage line. A call site writing `client.messages.batches.results(...)`
binds to nothing, so a vendor change to that operation finds no call site and the scan reports
clean. `2026-07-30-an-operation-no-symbol-reaches.md` carries the measurement and the argument for
counting the class rather than closing it.

The measurement is counted in the specification's own operations, and that direction is sound
where the reverse is not. `report_extraction` reduces both sides before comparing, so two declared
operations can sit behind one comparable key -- and M3-W100 refused to recount `covered_count` in
operations for exactly that reason: reaching a shared key proves one of the two is sent and says
nothing about the other. The complement carries no such ambiguity. If no symbol reaches the shared
key then no symbol sends any operation behind it, so every entry here is certainly unreached.
"""

from __future__ import annotations

import json
from pathlib import Path

from sync.signals.generated import symbols, symbols_speakeasy, symbols_typescript
from sync.signals.generated.adapter import GeneratedSpecAdapter
from sync.signals.generated.symbols import read_spec_operations

FIXTURES = Path(__file__).parent / "fixtures" / "sdk_sources"

ANTHROPIC_SPEC = FIXTURES / "anthropic_spec_operations.json"
VERCEL_SPEC = FIXTURES / "vercel_spec_operations.json"

PYTHON_SDK = FIXTURES / "anthropic_python"
TYPESCRIPT_SDK = FIXTURES / "anthropic_typescript"
SPEAKEASY_SDK = FIXTURES / "vercel_typescript"

ARTIFACTS = (
    (symbols, PYTHON_SDK, ANTHROPIC_SPEC),
    (symbols_typescript, TYPESCRIPT_SDK, ANTHROPIC_SPEC),
    (symbols_speakeasy, SPEAKEASY_SDK, VERCEL_SPEC),
)

# Measured, not rounded. `docs/superpowers/reports/2026-07-30-an-operation-no-symbol-reaches.md`
# carries the split by cause: for both Anthropic flavours 110 of the 112 are reachable only
# through the `beta/` tree the fixture omits and every one of them has a recorded mount decline
# behind it, leaving two spellings of one operation -- the batch results read -- as the whole of
# the class this task is about. All 344 of Vercel's are the truncation its README documents.
UNREACHED = {
    "stainless-python": 112,
    "stainless-typescript": 112,
    "speakeasy-typescript": 344,
}

BATCH_RESULTS = ("GET", "/v1/messages/batches/{message_batch_id}/results")


def _report(flavour, root: Path, spec: Path):
    return flavour.report_extraction(root, read_spec_operations(spec))


# --- the count, pinned so the class cannot grow unnoticed --------------------------------


def test_the_declared_operations_no_symbol_reaches_are_counted_per_artifact():
    """The number this task exists to establish, per pinned artifact.

    Pinned to what was measured rather than to a round number, so a reader regression, a fixture
    that stages less, or a vendor version declaring more operations moves it and goes red. The
    counts are large because all three fixtures are deliberately partial checkouts; what matters
    is that they are stable, and that the report says which of them are a reader limit.
    """
    counted = {
        flavour.GENERATOR: len(_report(flavour, root, spec).unreached)
        for flavour, root, spec in ARTIFACTS
    }

    assert counted == UNREACHED


def test_every_entry_is_an_operation_the_specification_declares_as_it_declares_it():
    """The unit, asserted rather than described.

    Counted in the specification's own operations and spelled the way it spells them, so an
    operator can look one up in the document. A reduced key would not be findable there, and the
    two Anthropic flavours reduce differently, so the identities would stop being comparable
    between the readers -- which is the one property this measurement exists to compare.

    Ordered, and that is a pipeline rule rather than a nicety. `spec_operations` is a set, so
    leaving the entries in iteration order makes them depend on string hashing -- randomised per
    process by default -- and two extractions over identical bytes would then produce different
    records. Convergence on the same input is required of every stage, and this is a record.
    """
    for flavour, root, spec in ARTIFACTS:
        declared = read_spec_operations(spec)
        report = _report(flavour, root, spec)

        assert set(report.unreached) <= declared, flavour.GENERATOR
        assert len(set(report.unreached)) == len(report.unreached), flavour.GENERATOR
        assert list(report.unreached) == sorted(report.unreached), flavour.GENERATOR


def test_an_unreached_key_makes_every_operation_behind_it_unreached():
    """Why the count can be stated in operations where `covered_count` refused to be.

    M3-W100 established that a comparable key two declared operations sit behind cannot be
    attributed: reaching it proves one of them is sent and says nothing about the other, so
    `covered_count` stays counted in keys. The complement is not symmetric. A key no symbol
    reaches means no symbol sends any operation behind it, so the count in operations is exact
    rather than a range -- and it is at least the count in keys, by however many operations the
    reduction absorbed.
    """
    for flavour, root, spec in ARTIFACTS:
        report = _report(flavour, root, spec)
        unreached_keys = report.comparable_key_count - report.covered_count

        assert len(report.unreached) >= unreached_keys, flavour.GENERATOR
        assert report.declared_operation_count - len(report.unreached) >= report.covered_count


def test_the_channel_is_present_and_empty_when_the_map_reaches_every_declared_operation(tmp_path):
    """Empty is a claim, not an absence.

    The same narrowing `unreadable` carries: a field that defaulted would let a flavour computing
    nothing pass for one that lost nothing. An SDK reaching everything its specification declares
    answers `()`, and the render line says nothing, so silence means full coverage rather than a
    number nobody computed.
    """
    root = _typescript_sdk(tmp_path)
    spec = _spec(tmp_path, ("GET", "/v1/models"))

    report = symbols_typescript.report_extraction(root, read_spec_operations(spec))

    assert report.unreached == ()
    assert report.covered_count == 1
    assert "no symbol reaches" not in report.render()


def test_the_count_travels_in_the_line_an_operator_reads():
    """A measurement nobody renders is the defect M3-W100 just closed, in a new field.

    The line already carries coverage in comparable routes and the API's size in operations. What
    it could not state is the gap between them in operations, which is the size of the surface a
    vendor change can move without Sync raising anything.
    """
    line = _report(symbols, PYTHON_SDK, ANTHROPIC_SPEC).render()

    assert "112 declared operations no symbol reaches" in line
    assert "reaching 10 of 121 comparable routes" in line
    assert "the specification declares 131 operations" in line


# --- the one operation in the class, and the agreement between the two readers -----------


def test_the_only_operation_outside_the_omitted_tree_that_no_symbol_reaches_is_the_batch_results_read():
    """The class, separated from the truncation it is buried in.

    This specification writes 120 of its 131 operations with a `?beta=true` marker, and the two
    Anthropic fixtures leave most of the `beta/` tree out on purpose -- 110 of the 112 entries are
    only reachable through it and each has a recorded mount decline behind it. Strip them and one
    operation is left in both readers: the batch results read, whose route the vendor takes from a
    field of an earlier response.

    Its `?beta=true` twin is unreached too, and that is the point of the previous test: the two
    spellings reduce to one comparable key, so a report counting keys would say one where the
    specification declares two.
    """
    for flavour, root in ((symbols, PYTHON_SDK), (symbols_typescript, TYPESCRIPT_SDK)):
        report = _report(flavour, root, ANTHROPIC_SPEC)
        plain = [operation for operation in report.unreached if "?beta=true" not in operation[1]]

        assert plain == [BATCH_RESULTS], flavour.GENERATOR
        assert (BATCH_RESULTS[0], f"{BATCH_RESULTS[1]}?beta=true") in report.unreached


def test_both_flavours_lose_the_batch_results_read_and_agree_that_they_do():
    """Two rules over two languages, and the fact they agree about.

    They lose it for the same reason stated two different ways -- Python writes
    `path_template(batch.results_url, ...)` and TypeScript writes `this._client.get(batch.results_url,
    ...)` -- and each declines it independently. A change closing one and not the other would make
    the two readers disagree about a property of the vendor's SDK, which is worse than the loss:
    a call site would resolve in one language and not the other, and nothing would say why.

    Asserted on the specification's own spelling rather than on either flavour's reduced key,
    because the two reductions differ and a comparison between them would be comparing the
    readers' internals rather than their verdicts.
    """
    verdicts = {}
    for flavour, root in ((symbols, PYTHON_SDK), (symbols_typescript, TYPESCRIPT_SDK)):
        report = _report(flavour, root, ANTHROPIC_SPEC)
        verdicts[flavour.GENERATOR] = {
            operation for operation in report.unreached if "?beta=true" not in operation[1]
        }

        assert "messages.batches.results" not in {
            operation.symbol for operation in report.operations
        }
        assert [
            record
            for record in report.unreadable
            if "Batches.results" in record and "no route this rule can read" in record
        ], flavour.GENERATOR

    assert verdicts["stainless-python"] == verdicts["stainless-typescript"] == {BATCH_RESULTS}


def test_the_speakeasy_flavour_loses_no_operation_to_a_route_no_literal_states():
    """The third artifact, and why its 344 are a different fact.

    Speakeasy states the route in the request module a method delegates to, and every one of the
    fifteen this checkout stages yields a symbol -- so nothing here is lost to a route the rule
    could not read. All 48 declines name something absent from the checkout instead, which is the
    truncation `tests/fixtures/sdk_sources/README.md` documents rather than a limit of the rule.

    That is what makes the response-URL pattern a two-artifact finding rather than a three-artifact
    one, and it is worth pinning: the day a Speakeasy vendor returns a route in a response, this
    goes red and the class has a second generator in it.

    `test_the_fifteen_committed_request_modules_are_all_reached` already asserts the symbol count
    against the literal 15. This ties it to the filesystem instead, which is the stronger form for
    this question: a sixteenth request module whose route the rule cannot read leaves the extraction
    at 15, so that assertion still passes and this one does not.
    """
    report = _report(symbols_speakeasy, SPEAKEASY_SDK, VERCEL_SPEC)
    staged = list((SPEAKEASY_SDK / "funcs").glob("*.ts"))

    assert report.extracted_count == len(staged) == 15
    assert len(report.unreadable) == 48
    for record in report.unreadable:
        assert "this checkout does not contain" in record or "not in this checkout" in record


def test_no_symbol_is_bound_to_the_declared_operation_from_its_name():
    """The decision this task took, made falsifiable.

    The specification declares `GET /v1/messages/batches/{message_batch_id}/results` and the SDK
    method is `messages.batches.results`, so a rule matching a method name against a declared
    path's trailing segment would bind them. It is not built, and the report argues why: over the
    three pinned artifacts that rule fires on four of the thirty-eight symbols whose route is
    known, which is two distinct operations of evidence, and a wrong binding here is invisible --
    the route came from the specification, so `unknown_to_spec` can never contradict it.

    So the symbol stays absent, and this is the assertion that a later drive-by has to argue with
    rather than quietly pass.
    """
    for flavour, root in ((symbols, PYTHON_SDK), (symbols_typescript, TYPESCRIPT_SDK)):
        adapter = GeneratedSpecAdapter(
            vendor_id="anthropic",
            sources={},
            fetch=_never_fetch,
            cache_dir=root.parent,
            sdk_source=root,
            sdk_spec_operations=ANTHROPIC_SPEC,
            sdk_source_generator=flavour.GENERATOR,
        )

        assert adapter.operation_for_symbol("anthropic.messages.batches.results") is None
        assert adapter.operation_for_symbol("anthropic.messages.batches.retrieve") is not None


# --- the control: nothing that bound before binds differently now ------------------------


def test_every_symbol_that_bound_before_still_binds_to_the_same_route():
    """Without this a change binding everything to everything passes every assertion above.

    The Python flavour's whole map, pinned by symbol and route. `messages.create` and
    `messages.parse` share a route deliberately -- two symbols, one request -- which is why the
    map is eleven entries reaching ten comparable routes.
    """
    extracted = {
        operation.symbol: (operation.http_method, operation.path)
        for operation in symbols.extract_symbols(PYTHON_SDK)[0]
    }

    assert extracted == {
        "completions.create": ("POST", "/v1/complete"),
        "messages.batches.cancel": ("POST", "/v1/messages/batches/{message_batch_id}/cancel"),
        "messages.batches.create": ("POST", "/v1/messages/batches"),
        "messages.batches.delete": ("DELETE", "/v1/messages/batches/{message_batch_id}"),
        "messages.batches.list": ("GET", "/v1/messages/batches"),
        "messages.batches.retrieve": ("GET", "/v1/messages/batches/{message_batch_id}"),
        "messages.count_tokens": ("POST", "/v1/messages/count_tokens"),
        "messages.create": ("POST", "/v1/messages"),
        "messages.parse": ("POST", "/v1/messages"),
        "models.list": ("GET", "/v1/models"),
        "models.retrieve": ("GET", "/v1/models/{model_id}"),
    }


def test_the_coverage_numbers_for_the_pinned_artifacts_did_not_move():
    """The three counts this change deliberately leaves alone, asserted together.

    A measurement of what is missing must not move what is reached. These are the numbers
    M3-W100 established and every one of them is unchanged; only the count of what no symbol
    reaches is new.
    """
    measured = {
        flavour.GENERATOR: (
            report.extracted_count,
            report.covered_count,
            report.comparable_key_count,
            report.declared_operation_count,
        )
        for flavour, root, spec in ARTIFACTS
        if (report := _report(flavour, root, spec))
    }

    assert measured == {
        "stainless-python": (11, 10, 121, 131),
        "stainless-typescript": (12, 10, 121, 131),
        "speakeasy-typescript": (15, 15, 359, 359),
    }


# --- fixtures written by hand, because these shapes are not what a generator emits -------


def _typescript_sdk(tmp_path: Path) -> Path:
    """Three files of the shape the Stainless TypeScript rule reads, reaching one route.

    The same construction `tests/test_extraction_report_contract.py` uses. Hand-written because
    the assertion needs an SDK that reaches everything its specification declares, and all three
    committed trees are partial checkouts by design.
    """
    root = tmp_path / "sdk"
    files = {
        "client.ts": (
            "import * as API from './resources/index';\n"
            "\n"
            "export class Anthropic extends BaseAnthropic {\n"
            "  models: API.Models = new API.Models(this);\n"
            "}\n"
        ),
        "resources/index.ts": "export { Models } from './models';\n",
        "resources/models.ts": (
            "import { APIResource } from '../core/resource';\n"
            "\n"
            "export class Models extends APIResource {\n"
            "  list() { return this._client.get('/v1/models', {}); }\n"
            "}\n"
        ),
    }
    for relative, body in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    return root


def _spec(tmp_path: Path, *operations: tuple[str, str]) -> Path:
    destination = tmp_path / "spec_operations.json"
    destination.write_text(
        json.dumps([{"method": method, "path": route} for method, route in operations]),
        encoding="utf-8",
    )
    return destination


def _never_fetch(url: str) -> str:
    raise AssertionError("symbol extraction must not reach a network")
