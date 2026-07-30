"""The conformance kit an outside adapter author runs against their own class.

`isinstance(adapter, VendorAdapter)` is a `runtime_checkable` Protocol check, and those verify
only that the method *names* exist. Signatures, return types and behaviour are all unchecked, so
an adapter that raises where it should return `None`, or hands back a string where an
`OperationRef` is required, passes today and fails inside the pipeline instead — where the
diagnostic names Sync's internals rather than the author's mistake.

These tests are about the kit, not about any one adapter. The adapters ship their own tests.
"""

from __future__ import annotations

import pytest

from pathlib import Path

from sync.core import (
    CallSite,
    Detector,
    Finding,
    LanguageAdapter,
    OperationRef,
    Patch,
    RepoRef,
    RequestCorrelator,
    VendorAdapter,
    VendorChange,
    VerifyResult,
)
from sync.core.models import UNATTRIBUTED
from sync.core.conformance import (
    ConformanceFailure,
    check_detector,
    check_language_adapter,
    check_remediator,
    check_request_correlator,
    check_vendor_adapter,
)


class _Correct:
    """The shape every invariant is stated against."""

    vendor_id = "example"

    def fetch_changes(self, from_version: str, to_version: str):
        return []

    def operation_for_symbol(self, symbol: str, *, language: str | None = None):
        if symbol == "example.charges.create":
            return OperationRef(operation_id="PostCharges", http_method="post", path="/v1/charges")
        return None


def test_a_correct_adapter_passes():
    check_vendor_adapter(_Correct(), known_symbol="example.charges.create")


@pytest.mark.parametrize("known_symbol", [None, ""])
def test_no_known_symbol_is_reported_against_the_case(known_symbol):
    """"You did not give me a symbol to check" is a different problem from "your adapter did not
    resolve the symbol you gave me", and an author who conflates them edits the wrong thing.

    This half is the case being wrong. Nothing about the adapter has been established either way,
    and the message has to say so -- an author told their adapter failed would go looking in the
    adapter for a defect that is in the call.
    """
    with pytest.raises(ConformanceFailure, match="must be given a symbol"):
        check_vendor_adapter(_Correct(), known_symbol=known_symbol)


def test_an_adapter_that_resolves_no_symbol_at_all_fails():
    """The other half, and the hole this closes.

    `operation_for_symbol` is the hinge of the whole system: it is what joins a specification diff
    to a call site. An adapter that resolves nothing produces no findings ever, and the kit used
    to certify it -- every rule above this one is about what the adapter does *not* do, and an
    adapter that does nothing satisfies all of them.
    """

    class ResolvesNothing(_Correct):
        def operation_for_symbol(self, symbol: str, *, language: str | None = None):
            return None

    assert isinstance(ResolvesNothing(), VendorAdapter), "isinstance must still pass, or this proves nothing"
    with pytest.raises(ConformanceFailure, match="did not resolve the symbol"):
        check_vendor_adapter(ResolvesNothing(), known_symbol="example.charges.create")


def test_an_adapter_that_raises_on_an_unknown_symbol_fails():
    """The invariant this repository states most often and writes down least visibly: an
    unresolvable symbol returns None rather than raising or guessing. An unresolved symbol is
    visibly unresolved and countable; a raised exception aborts an indexing run over one
    call site the adapter simply did not recognise.
    """

    class Raises(_Correct):
        def operation_for_symbol(self, symbol: str, *, language: str | None = None):
            raise KeyError(symbol)

    assert isinstance(Raises(), VendorAdapter), "isinstance must still pass, or this proves nothing"
    with pytest.raises(ConformanceFailure, match="unknown symbol"):
        check_vendor_adapter(Raises(), known_symbol="example.charges.create")


def test_an_adapter_that_returns_the_wrong_type_fails():
    """A string is not an OperationRef. The pipeline would fail on attribute access somewhere
    far from here, naming a field rather than the adapter.
    """

    class WrongType(_Correct):
        def operation_for_symbol(self, symbol: str, *, language: str | None = None):
            # Correct for the unknown symbol, so this isolates the return-type rule from the
            # returns-None-for-unknown rule that would otherwise fire first.
            return "PostCharges" if symbol == "example.charges.create" else None

    assert isinstance(WrongType(), VendorAdapter)
    with pytest.raises(ConformanceFailure, match="OperationRef"):
        check_vendor_adapter(WrongType(), known_symbol="example.charges.create")


def test_an_adapter_that_refuses_the_language_argument_fails():
    """The language axis landed as a keyword-only argument. An adapter whose two SDK languages
    agree may ignore it, but every adapter must accept it -- the indexer passes it always, so
    one that does not accept it raises TypeError on the first call site it sees.
    """

    class NoLanguage(_Correct):
        def operation_for_symbol(self, symbol: str):
            return None

    # Matched on the rule's own wording rather than the word "language": without this rule the
    # later call raises TypeError whose text also contains "language", so a loose regex passes
    # for the wrong reason and the mutation that deletes the rule survives.
    with pytest.raises(ConformanceFailure, match="must accept a keyword-only"):
        check_vendor_adapter(NoLanguage(), known_symbol="example.charges.create")


def test_an_adapter_without_a_vendor_id_fails():
    class Anonymous(_Correct):
        vendor_id = ""

    with pytest.raises(ConformanceFailure, match="vendor_id"):
        check_vendor_adapter(Anonymous(), known_symbol="example.charges.create")


def test_fetch_changes_must_be_iterable_rather_than_none():
    """Every stage here is required to be idempotent and re-runnable. A vendor with nothing to
    report returns an empty iterable; None is the shape that makes a caller crash on a for loop.
    """

    class ReturnsNone(_Correct):
        def fetch_changes(self, from_version: str, to_version: str):
            return None

    with pytest.raises(ConformanceFailure, match="iterable"):
        check_vendor_adapter(ReturnsNone(), known_symbol="example.charges.create")


# --- Remediator -------------------------------------------------------------------


class _CorrectRemediator:
    """Writes its edit to the clone, then describes it."""

    strategy = "codemod"

    def can_handle(self, finding, change) -> bool:
        return True

    def propose(self, finding, change, site, repo, diagnostics: str = ""):
        target = Path(repo.local_path) / site.path
        original = target.read_text(encoding="utf-8")
        updated = original.replace("amount", "value")
        if updated == original:
            return Patch(diff="", strategy=self.strategy, rationale="nothing to change")
        target.write_text(updated, encoding="utf-8")
        return Patch(diff="--- a\n+++ b\n", strategy=self.strategy, rationale="renamed")


def test_a_correct_remediator_passes(tmp_path):
    check_remediator(_CorrectRemediator(), *_remediation_case(tmp_path))


def test_a_remediator_that_declines_the_case_is_reported_against_the_case(tmp_path):
    """A decline is not a pass, and the second hole this closes.

    Every rule below is about what `propose` writes. A remediator that declines writes nothing,
    satisfies the decline branch, and the kit reports success having watched it do nothing at
    all. It was live: `ParameterRenameRemediator` passed on a patch it never produced, because
    the fixture clone already declared the key it renames onto and declining was correct.

    Reported against the *case*, not the remediator, and that is the whole resolution of the
    tension. Declining a change outside its strategy is what a tier is supposed to do, so the kit
    cannot call it a defect -- but it can say that nothing was measured, which is true and is what
    an author needs to hear. The fix is a case they hand it that their own remediator handles,
    and they can always produce one.
    """

    class DeclinesEverything(_CorrectRemediator):
        def propose(self, finding, change, site, repo, diagnostics: str = ""):
            return Patch(diff="", strategy=self.strategy, rationale="not my change kind")

    with pytest.raises(ConformanceFailure, match="must be one this remediator patches"):
        check_remediator(DeclinesEverything(), *_remediation_case(tmp_path))


def test_a_remediator_that_only_returns_a_diff_fails(tmp_path):
    """The defect this rule exists for, and it has shipped twice.

    Nothing downstream applies `patch.diff`. `make_patch` stores the `Patch`, `static_verify`
    typechecks the working tree, and `push_branch` stages with `git add -u`. So a remediator
    that computes the right edit and returns it without writing produces a branch with an
    empty commit and reports success — green verdict, empty pull request. It shipped in
    `literal_swap` and again in both parameter remediators, and was caught the second time
    only because one worker happened to read another's fix.
    """

    class DiffOnly(_CorrectRemediator):
        def propose(self, finding, change, site, repo, diagnostics: str = ""):
            return Patch(diff="--- a\n+++ b\n", strategy=self.strategy, rationale="renamed")

    with pytest.raises(ConformanceFailure, match="did not change the clone"):
        check_remediator(DiffOnly(), *_remediation_case(tmp_path))


def test_a_remediator_that_writes_while_declining_fails(tmp_path):
    """The mirror, and the one a naive fix introduces.

    An empty diff means the remediator declined. Writing anyway — even identical bytes —
    touches a file it decided not to edit, and a tool that does that near a working tree is
    one nobody trusts. `test_declining_writes_nothing` asserts `st_mtime_ns` for this reason.
    """

    class WritesWhileDeclining(_CorrectRemediator):
        def propose(self, finding, change, site, repo, diagnostics: str = ""):
            target = Path(repo.local_path) / site.path
            target.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
            return Patch(diff="", strategy=self.strategy, rationale="declined")

    with pytest.raises(ConformanceFailure, match="declined.*changed the clone|changed the clone"):
        check_remediator(WritesWhileDeclining(), *_remediation_case(tmp_path))


def test_a_remediator_whose_strategy_is_empty_fails(tmp_path):
    class Anonymous(_CorrectRemediator):
        strategy = ""

    with pytest.raises(ConformanceFailure, match="strategy"):
        check_remediator(Anonymous(), *_remediation_case(tmp_path))


def _remediation_case(tmp_path):
    """A finding, a change, a call site and a clone the remediator is expected to edit."""
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "billing.ts").write_text(
        "stripe.charges.create({ amount: 100 });\n", encoding="utf-8"
    )
    site = CallSite(
        repo_id="r", path="src/billing.ts", line=1, col=0, vendor_id="example",
        operation_id="PostCharges", symbol="example.charges.create",
        args_keys=["amount"], response_fields_read=[], sdk_version="1.0.0", content_hash="h",
    )
    change = VendorChange(
        vendor_id="example", from_version="v1", to_version="v2",
        kind="request-property-removed", operation_id="PostCharges", path_ptr="/amount",
        severity="breaking", source="oasdiff", raw={},
    )
    finding = Finding(
        id="f1", detector="vendor_change", claim="request-field", call_site_id="cs1",
        vendor_change_id="vc1",
        severity="breaking", rationale="amount removed",
    )
    repo = RepoRef(repo_id="r", url="u", local_path=str(tmp_path), head_sha="0" * 40)
    return finding, change, site, repo


# --- LanguageAdapter --------------------------------------------------------------

DEPENDENCY = "deps/example-sdk/types.d"


class _CorrectLanguage:
    """The shape every `LanguageAdapter` invariant is stated against.

    Small enough to read in one screen, and faithful in the three ways the rules are about: it
    records what the install wrote, it notices when a later edit contradicted that record, and
    it leaves alone the files it was never asked about.
    """

    language_id = "example"

    def __init__(self, dependency: str | None = None) -> None:
        self._dependency = dependency
        self._installed: dict[str, bytes] = {}

    def matches(self, repo) -> bool:
        return (Path(repo.local_path) / "example.manifest").exists()

    def index(self, repo):
        root = Path(repo.local_path)
        for source in sorted(root.rglob("*.ex")):
            yield CallSite(
                repo_id=repo.repo_id,
                path=source.relative_to(root).as_posix(),
                line=1, col=0, vendor_id="example", operation_id="PostCharges",
                symbol="example.charges.create", args_keys=["amount"], response_fields_read=[],
                sdk_version="1.0.0", content_hash="h",
            )

    def prepare(self, repo) -> None:
        if self._dependency is not None:
            self._installed[self._dependency] = (
                Path(repo.local_path) / self._dependency
            ).read_bytes()

    def discard_contaminated_dependencies(self, repo) -> bool:
        return False

    def static_verify(self, repo, patch) -> VerifyResult:
        for name, installed in self._installed.items():
            if (Path(repo.local_path) / name).read_bytes() != installed:
                return VerifyResult(ok=False, diagnostics=f"{name} was edited after the install")
        return VerifyResult(ok=True)


def test_a_correct_language_adapter_passes(tmp_path):
    check_language_adapter(
        _CorrectLanguage(dependency=DEPENDENCY),
        _language_case(tmp_path),
        installed_dependency=DEPENDENCY,
    )


def test_a_language_adapter_without_a_language_id_fails(tmp_path):
    class Anonymous(_CorrectLanguage):
        language_id = ""

    with pytest.raises(ConformanceFailure, match="language_id"):
        check_language_adapter(Anonymous(), _language_case(tmp_path))


def test_a_matcher_that_raises_on_an_unfamiliar_repository_fails(tmp_path):
    """Every registered adapter is asked about every repository, before any of them is chosen.

    One that raises on a tree it does not recognise takes down the selection loop, and the
    traceback names the adapter that was asked rather than the one that owns the repository.
    """

    class Explodes(_CorrectLanguage):
        def matches(self, repo) -> bool:
            manifest = Path(repo.local_path) / "example.manifest"
            return manifest.read_text(encoding="utf-8").startswith("example-sdk")

    assert isinstance(Explodes(), LanguageAdapter), "isinstance must still pass, or this proves nothing"
    with pytest.raises(ConformanceFailure, match="must answer for a repository it does not own"):
        check_language_adapter(Explodes(), _language_case(tmp_path))


def test_a_matcher_that_returns_a_truthy_non_bool_fails(tmp_path):
    """`matches` is dispatch. Returning the thing it matched on instead of a decision reads as
    True for every repository that has a path at all, so the adapter claims repositories in
    another language and the one that owns them never gets asked.
    """

    class ReturnsThePath(_CorrectLanguage):
        def matches(self, repo):
            return Path(repo.local_path) / "example.manifest"

    with pytest.raises(ConformanceFailure, match="must return a bool"):
        check_language_adapter(ReturnsThePath(), _language_case(tmp_path))


def test_a_matcher_that_disowns_the_supplied_repository_fails(tmp_path):
    """A precondition, not an adapter rule, and the message says so. Every check below is
    measured against this repository, so an adapter that does not claim it would pass the rest
    of the kit vacuously.
    """

    class ClaimsNothing(_CorrectLanguage):
        def matches(self, repo) -> bool:
            return False

    with pytest.raises(ConformanceFailure, match="must claim the repository the kit was handed"):
        check_language_adapter(ClaimsNothing(), _language_case(tmp_path))


def test_a_matcher_that_claims_every_repository_fails(tmp_path):
    """A matcher that claims a directory with nothing in it claims everything, and selection
    then depends on which adapter was registered first rather than on the repository.
    """

    class ClaimsEverything(_CorrectLanguage):
        def matches(self, repo) -> bool:
            return True

    with pytest.raises(ConformanceFailure, match="must not claim an empty directory"):
        check_language_adapter(ClaimsEverything(), _language_case(tmp_path))


def test_a_repository_with_no_call_sites_in_it_fails(tmp_path):
    """The lesson from the remediator kit, restated as a rule. A case that exercises nothing
    passes every rule about what `index` emits, and reports a floor it never measured.
    """

    class FindsNothing(_CorrectLanguage):
        def index(self, repo):
            return iter(())

    with pytest.raises(ConformanceFailure, match="at least one call site"):
        check_language_adapter(FindsNothing(), _language_case(tmp_path))


def test_an_index_that_yields_something_other_than_a_call_site_fails(tmp_path):
    class Tuples(_CorrectLanguage):
        def index(self, repo):
            yield ("src/billing.ex", 1)

    with pytest.raises(ConformanceFailure, match="must yield CallSite"):
        check_language_adapter(Tuples(), _language_case(tmp_path))


def test_an_index_that_files_a_site_under_another_repository_fails(tmp_path):
    """`repo_id` is half a call site's identity in the graph. A wrong one files the row under a
    repository nobody indexed, where no finding will ever reach it.
    """

    class WrongRepo(_CorrectLanguage):
        def index(self, repo):
            for site in super().index(repo):
                yield site.model_copy(update={"repo_id": "somebody-elses-repo"})

    with pytest.raises(ConformanceFailure, match="must carry the repo_id"):
        check_language_adapter(WrongRepo(), _language_case(tmp_path))


def test_an_index_that_returns_none_fails(tmp_path):
    class ReturnsNone(_CorrectLanguage):
        def index(self, repo):
            return None

    with pytest.raises(ConformanceFailure, match="index must return an iterable"):
        check_language_adapter(ReturnsNone(), _language_case(tmp_path))


def test_an_index_that_reports_an_absolute_path_fails(tmp_path):
    """`Path(repo.local_path) / site.path` is how every consumer opens the file. An absolute
    right-hand side discards the left one silently — pathlib's documented behaviour — so the
    remediator edits a file outside the clone, or the patch agent is handed a path the
    customer's CI does not have.
    """

    class Absolute(_CorrectLanguage):
        def index(self, repo):
            for site in super().index(repo):
                yield site.model_copy(update={"path": str(Path(repo.local_path) / site.path)})

    with pytest.raises(ConformanceFailure, match="repository-relative"):
        check_language_adapter(Absolute(), _language_case(tmp_path))


def test_an_index_that_reports_a_windows_separator_fails(tmp_path):
    """An adapter written on Windows that spells a path with backslashes passes every test its
    author runs and fails on the customer's CI, where the path names no file.
    """

    class Backslashes(_CorrectLanguage):
        def index(self, repo):
            for site in super().index(repo):
                yield site.model_copy(update={"path": site.path.replace("/", "\\")})

    with pytest.raises(ConformanceFailure, match="forward slashes"):
        check_language_adapter(Backslashes(), _language_case(tmp_path))


def test_an_index_that_reports_a_file_that_is_not_there_fails(tmp_path):
    class Invents(_CorrectLanguage):
        def index(self, repo):
            for site in super().index(repo):
                yield site.model_copy(update={"path": "src/does-not-exist.ex"})

    with pytest.raises(ConformanceFailure, match="must exist in the repository"):
        check_language_adapter(Invents(), _language_case(tmp_path))


def test_an_index_that_does_not_converge_fails(tmp_path):
    """INDEX is a pipeline stage and every stage here is idempotent: re-running it over an
    unchanged checkout converges on the same rows. One that does not leaves the graph carrying
    whichever run happened last, and no query can tell which.
    """

    class Drifts(_CorrectLanguage):
        def __init__(self, dependency=None) -> None:
            super().__init__(dependency)
            self._runs = 0

        def index(self, repo):
            self._runs += 1
            for site in super().index(repo):
                yield site.model_copy(update={"line": self._runs})

    with pytest.raises(ConformanceFailure, match="same call sites"):
        check_language_adapter(Drifts(), _language_case(tmp_path))


def test_a_prepare_that_cannot_run_twice_fails(tmp_path):
    """One clone serves every finding in a run, and the driver reaches `prepare` again for each
    of them. An adapter that only tolerates being prepared once abandons every finding after
    the first, on a repository where nothing is wrong.
    """

    class OnceOnly(_CorrectLanguage):
        def __init__(self, dependency=None) -> None:
            super().__init__(dependency)
            self._prepared = False

        def prepare(self, repo) -> None:
            if self._prepared:
                raise RuntimeError("already prepared")
            self._prepared = True

    with pytest.raises(ConformanceFailure, match="prepare must tolerate being called again"):
        check_language_adapter(OnceOnly(), _language_case(tmp_path))


def test_a_discard_that_always_claims_it_removed_something_fails(tmp_path):
    """The return value is the only signal an operator gets that the next finding will pay for
    a reinstall. One that always says yes costs an install per finding and tells nobody why.
    """

    class AlwaysTrue(_CorrectLanguage):
        def discard_contaminated_dependencies(self, repo) -> bool:
            return True

    with pytest.raises(ConformanceFailure, match="nothing was contaminated"):
        check_language_adapter(AlwaysTrue(), _language_case(tmp_path))


def test_a_discard_that_answers_with_something_other_than_a_bool_fails(tmp_path):
    class ReturnsThePaths(_CorrectLanguage):
        def discard_contaminated_dependencies(self, repo):
            return []

    with pytest.raises(ConformanceFailure, match="must return a bool"):
        check_language_adapter(ReturnsThePaths(), _language_case(tmp_path))


def test_an_installed_dependency_that_is_not_there_fails(tmp_path):
    """A precondition, and the one the remediator kit learned to state. If the path the author
    named does not exist, the doctoring below writes a file nothing reads and the rule passes
    without ever having been exercised.
    """

    with pytest.raises(ConformanceFailure, match="installed dependency must exist"):
        check_language_adapter(
            _CorrectLanguage(),
            _language_case(tmp_path),
            installed_dependency="deps/example-sdk/never-installed",
        )


def test_a_static_verify_that_returns_a_bare_bool_fails(tmp_path):
    """`if result.ok` on a bool raises AttributeError inside the graph, several nodes from here."""

    class ReturnsBool(_CorrectLanguage):
        def static_verify(self, repo, patch):
            return True

    with pytest.raises(ConformanceFailure, match="must return a VerifyResult"):
        check_language_adapter(ReturnsBool(), _language_case(tmp_path))


def test_a_failed_verification_with_no_diagnostics_fails(tmp_path):
    """`diagnostics` is the entire input to the next patch attempt. A failure carrying none
    spends an agent run to arrive back where it started, and the routing that reads the result
    cannot tell an unverifiable patch from a broken toolchain.
    """

    class Silent(_CorrectLanguage):
        def static_verify(self, repo, patch):
            return VerifyResult(ok=False)

    with pytest.raises(ConformanceFailure, match="diagnostics"):
        check_language_adapter(Silent(), _language_case(tmp_path))


def test_a_static_verify_that_loses_a_file_it_was_not_asked_about_fails(tmp_path):
    """Verification measures the tree a push would carry, which means holding the agent's
    untracked and ignored files out of the compile — and putting them back. One that does the
    first half destroys work the next attempt needed and reports a clean verdict while doing it.
    """

    class LosesFiles(_CorrectLanguage):
        def static_verify(self, repo, patch) -> VerifyResult:
            for stray in Path(repo.local_path).glob(".sync-conformance-*"):
                stray.unlink()
            return VerifyResult(ok=True)

    with pytest.raises(ConformanceFailure, match="must put back every file"):
        check_language_adapter(LosesFiles(), _language_case(tmp_path))


def test_a_static_verify_that_approves_a_doctored_dependency_fails(tmp_path):
    """An edit inside an installed dependency satisfies a gate the customer's CI will not: no
    checkout of the branch contains that file. Approving it produces a green verdict about a
    tree nobody will ever have.
    """

    class IgnoresDependencies(_CorrectLanguage):
        def static_verify(self, repo, patch) -> VerifyResult:
            return VerifyResult(ok=True)

    with pytest.raises(ConformanceFailure, match="installed dependency"):
        check_language_adapter(
            IgnoresDependencies(dependency=DEPENDENCY),
            _language_case(tmp_path),
            installed_dependency=DEPENDENCY,
        )


def _language_case(tmp_path):
    """A checkout the adapter is expected to match, index and verify.

    Written under a `clone` subdirectory rather than at `tmp_path` itself, so the kit's own
    scratch — the empty directory it asks `matches` about — cannot land inside it.
    """
    clone = tmp_path / "clone"
    (clone / "src").mkdir(parents=True, exist_ok=True)
    (clone / "example.manifest").write_text("example-sdk 1.0.0\n", encoding="utf-8")
    (clone / "src" / "billing.ex").write_text("charges.create(amount=100)\n", encoding="utf-8")
    (clone / "deps" / "example-sdk").mkdir(parents=True, exist_ok=True)
    (clone / DEPENDENCY).write_text("declare charges\n", encoding="utf-8")
    return RepoRef(repo_id="r", url="u", local_path=str(clone), head_sha="0" * 40)


# --- Detector ---------------------------------------------------------------------


class _CorrectDetector:
    """One finding per affected call site, and the same ones every time it is asked.

    The rung is `static` because this example reads a vendor change against the static index and
    nothing else is load-bearing -- a wrong static binding is what would make its claim wrong. It
    was absent until the kit gained a rule about it, which means the kit's own example of a
    conforming detector was emitting findings `GraphStore.insert_finding` would have refused.
    """

    detector_id = "example-detector"

    def scan(self):
        for call_site_id in ("cs1", "cs2"):
            yield Finding(
                detector=self.detector_id,
                claim="request-field",
                call_site_id=call_site_id,
                vendor_change_id="vc1",
                severity="breaking",
                rationale="amount was removed from the request body",
                binding_rung="static",
            )


def test_a_correct_detector_passes():
    check_detector(_CorrectDetector())


def test_a_detector_without_an_id_fails():
    class Anonymous(_CorrectDetector):
        detector_id = ""

    with pytest.raises(ConformanceFailure, match="detector_id"):
        check_detector(Anonymous())


def test_a_scan_that_returns_none_fails():
    class ReturnsNone(_CorrectDetector):
        def scan(self):
            return None

    assert isinstance(ReturnsNone(), Detector), "isinstance must still pass, or this proves nothing"
    with pytest.raises(ConformanceFailure, match="scan must return an iterable"):
        check_detector(ReturnsNone())


def test_a_detector_that_finds_nothing_fails():
    """The same precondition `index` has, and it caught the same mistake. Probing the real
    detectors with this kit, `StatusRateDetector` passed every rule while emitting nothing --
    a fixture that reached no threshold, reported as conformance.
    """

    class Silent(_CorrectDetector):
        def scan(self):
            return iter(())

    with pytest.raises(ConformanceFailure, match="at least one finding"):
        check_detector(Silent())


def test_a_detector_that_emits_something_other_than_a_finding_fails():
    class Dicts(_CorrectDetector):
        def scan(self):
            yield {"detector": self.detector_id, "call_site_id": "cs1"}

    with pytest.raises(ConformanceFailure, match="must yield Finding"):
        check_detector(Dicts())


def test_a_detector_that_signs_its_findings_with_another_name_fails():
    """`Finding.detector` is what attributes a false positive back to the code that raised it.
    A finding signed with a name no detector answers to cannot be attributed to anything.
    """

    class Mislabels(_CorrectDetector):
        def scan(self):
            for finding in super().scan():
                yield finding.model_copy(update={"detector": "something-else"})

    with pytest.raises(ConformanceFailure, match="detector_id of the detector that raised it"):
        check_detector(Mislabels())


def test_a_finding_with_no_call_site_fails():
    """A `Finding` addresses its call site by id and nothing else. One carrying none has no
    location to report, no file to patch and no row to reference.
    """

    class Unlocated(_CorrectDetector):
        def scan(self):
            for finding in super().scan():
                yield finding.model_copy(update={"call_site_id": ""})

    with pytest.raises(ConformanceFailure, match="call_site_id"):
        check_detector(Unlocated())


def test_a_detector_whose_findings_name_no_rung_fails():
    """The store refuses these at the first write, and the kit exists to say so before that.

    `GraphStore.insert_finding` raises on `unattributed`, so a detector certified without this rule
    is one the kit calls conforming and production rejects on its first finding -- the worst
    ordering there is for somebody working from the published SDK. `CLAUDE.md` requires the rung of
    every artifact derived from a binding, because a false positive that cannot be attributed to a
    rung cannot be fixed.
    """

    class Forgetful(_CorrectDetector):
        def scan(self):
            for finding in super().scan():
                yield finding.model_copy(update={"binding_rung": UNATTRIBUTED})

    assert isinstance(Forgetful(), Detector), "isinstance must still pass, or this proves nothing"
    with pytest.raises(ConformanceFailure, match="binding rung"):
        check_detector(Forgetful())


def test_one_finding_out_of_two_naming_no_rung_fails():
    """A rule that read only the first finding would certify this, and the store would not.

    A detector attributing most of its findings and forgetting on one path is likelier than one
    that never attributes at all -- the forgetful path is usually the branch with the fewest
    fixtures behind it. So the rule is over every finding, and this is what says so.
    """

    class ForgetsOnTheSecond(_CorrectDetector):
        def scan(self):
            first, second = super().scan()
            yield first
            yield second.model_copy(update={"binding_rung": UNATTRIBUTED})

    with pytest.raises(ConformanceFailure, match="binding rung"):
        check_detector(ForgetsOnTheSecond())


def test_two_findings_that_collide_on_the_graph_key_fails():
    """The graph keys a finding on `(detector, call_site_id, vendor_change_id, claim)` and
    inserts `ON CONFLICT DO NOTHING`. Two findings sharing that key are one row, and the second
    one is discarded without a warning — so a detector saying two things about one call site
    says whichever of them it happened to emit first.

    `claim` joined the key after this test was written, and the broken example gained it rather
    than losing the collision: both findings still carry `loop`, so they still share the whole
    key. A test that had let them differ would have stopped testing anything the moment the
    field arrived, which is the failure mode a widened key invites.
    """

    class TwoClaimsOneKey(_CorrectDetector):
        def scan(self):
            for rationale in ("called inside a loop", "the same call repeated 40 times"):
                yield Finding(
                    detector=self.detector_id,
                    claim="loop",
                    call_site_id="cs1",
                    severity="info",
                    rationale=rationale,
                    # Broken in one way only. The rung rule runs before this one, so a fixture
                    # that omitted it would be rejected for the wrong reason and this test would
                    # pass without exercising the key at all.
                    binding_rung="static",
                )

    with pytest.raises(ConformanceFailure, match="same natural key"):
        check_detector(TwoClaimsOneKey())


def test_a_second_scan_that_disagrees_with_the_first_fails():
    """DETECT is a pipeline stage and every stage here is idempotent. A detector whose answer
    depends on how many times it has been asked makes the graph a record of run ordering.
    """

    class Drifts(_CorrectDetector):
        def __init__(self) -> None:
            self._runs = 0

        def scan(self):
            self._runs += 1
            yield Finding(
                detector=self.detector_id,
                claim="request-field",
                call_site_id="cs1",
                vendor_change_id="vc1",
                severity="breaking",
                rationale=f"seen on scan {self._runs}",
                # As above: broken only in the way this test is about.
                binding_rung="static",
            )

    with pytest.raises(ConformanceFailure, match="same findings"):
        check_detector(Drifts())


# --- RequestCorrelator ------------------------------------------------------------


class _CorrectCorrelator:
    """The shape every correlator invariant is stated against.

    Small enough to read in one screen and shaped like the real thing: a table of published
    templates, matched by method and segment count, answering with the template rather than with
    the path it was asked about.
    """

    vendor_id = "example"

    _ROUTES = {
        ("get", 2): ("/v1/charges", "GetCharges"),
        ("post", 2): ("/v1/charges", "PostCharges"),
        ("get", 3): ("/v1/charges/{charge}", "GetChargesCharge"),
        ("post", 3): ("/v1/charges/{charge}", "PostChargesCharge"),
    }

    def operation_for_request(self, http_method: str, path: str):
        observed = tuple(path.strip("/").split("/")) if path.strip("/") else ()
        entry = self._ROUTES.get((http_method.lower(), len(observed)))
        if entry is None or any(not segment for segment in observed):
            return None
        template, operation_id = entry
        expected = tuple(template.strip("/").split("/"))
        if not all(lit.startswith("{") or lit == seen for lit, seen in zip(expected, observed)):
            return None
        return OperationRef(
            operation_id=operation_id, http_method=http_method.lower(), path=template
        )


_KNOWN_REQUEST = ("GET", "/v1/charges/ch_3PjkLm2eZvKYlo2C1cQrSt")
_IDENTIFIER = "ch_3PjkLm2eZvKYlo2C1cQrSt"


def _check_correlator(correlator):
    return check_request_correlator(
        correlator, known_request=_KNOWN_REQUEST, identifier=_IDENTIFIER
    )


def test_a_correct_correlator_passes():
    _check_correlator(_CorrectCorrelator())


def test_a_correlator_that_returns_the_request_path_fails():
    """The rule the kit exists for. `operation_for_request` is handed a real observed path with a
    live customer identifier in it, and substituting the vendor's published template is the
    boundary at which that identifier stops travelling. A correlator that hands back what it was
    given carries the identifier into `observed_call`, into every finding joined against it, and
    from there into the body of a pull request opened on a public repository.

    Nothing else in the system checks this. `isinstance` cannot, and the two guards in `sync.cli`
    that use it therefore verify a method name and nothing more.
    """

    class ReturnsTheRequestPath(_CorrectCorrelator):
        def operation_for_request(self, http_method: str, path: str):
            answer = super().operation_for_request(http_method, path)
            return None if answer is None else answer.model_copy(update={"path": path})

    assert isinstance(
        ReturnsTheRequestPath(), RequestCorrelator
    ), "isinstance must still pass, or this proves nothing"
    with pytest.raises(ConformanceFailure, match="carried the request's own identifier"):
        _check_correlator(ReturnsTheRequestPath())


def test_a_correlator_that_leaks_the_identifier_into_the_operation_id_fails():
    """The same leak through a different field. A rule that read only `.path` would certify this
    as conformant, and every string on the ref is stored and reported.
    """

    class LeaksIntoTheId(_CorrectCorrelator):
        def operation_for_request(self, http_method: str, path: str):
            answer = super().operation_for_request(http_method, path)
            if answer is None:
                return None
            last = path.rsplit("/", 1)[-1]
            return answer.model_copy(update={"operation_id": answer.operation_id + ":" + last})

    with pytest.raises(ConformanceFailure, match="carried the request's own identifier"):
        _check_correlator(LeaksIntoTheId())


def test_a_correlator_that_raises_on_an_unrecognised_path_fails():
    """A correlator is asked about every client span in a batch, most of which are for other
    hosts entirely. One that raises on a path it does not recognise takes down the ingest of the
    whole batch over a request it was never expected to know.
    """

    class Raises(_CorrectCorrelator):
        def operation_for_request(self, http_method: str, path: str):
            answer = super().operation_for_request(http_method, path)
            if answer is None:
                raise KeyError(path)
            return answer

    assert isinstance(Raises(), RequestCorrelator)
    with pytest.raises(ConformanceFailure, match="must answer for a request it cannot resolve"):
        _check_correlator(Raises())


def test_a_correlator_that_guesses_at_an_unrecognised_path_fails():
    """`None` rather than a guess, which is `operation_for_symbol`'s rule addressed by path. A
    missing binding is visibly unresolved and can be counted; a wrong one attributes real traffic
    to an operation nobody called, and the finding it produces points at code that never made the
    request.
    """

    class Guesses(_CorrectCorrelator):
        def operation_for_request(self, http_method: str, path: str):
            answer = super().operation_for_request(http_method, path)
            if answer is not None:
                return answer
            return OperationRef(
                operation_id="GetCharges", http_method=http_method.lower(), path="/v1/charges"
            )

    with pytest.raises(ConformanceFailure, match="must return None for an unrecognised request"):
        _check_correlator(Guesses())


def test_a_correlator_that_raises_on_an_empty_path_fails():
    """`sync.cli` hands this `urlsplit(url).path`, which is the empty string for a URL that has no
    path at all. That is a real span produced by a real exporter, and a correlator that raises on
    it stops the ingest rather than declining one request.
    """

    class RaisesOnEmpty(_CorrectCorrelator):
        def operation_for_request(self, http_method: str, path: str):
            if not path:
                raise ValueError("empty path")
            return super().operation_for_request(http_method, path)

    with pytest.raises(ConformanceFailure, match="must answer for a request it cannot resolve"):
        _check_correlator(RaisesOnEmpty())


def test_a_correlator_that_ignores_the_http_method_fails():
    """A span carries a method and a URL, and `/v1/charges` is two different operations. A
    correlator matching on the path alone merges a read with a write -- which is the distinction
    the efficiency detector's whole subject rests on -- and binds a DELETE to the operation that
    reads.
    """

    class IgnoresTheMethod(_CorrectCorrelator):
        def operation_for_request(self, http_method: str, path: str):
            return super().operation_for_request("get", path)

    assert isinstance(IgnoresTheMethod(), RequestCorrelator)
    with pytest.raises(ConformanceFailure, match="must be the method it was asked about"):
        _check_correlator(IgnoresTheMethod())


def test_a_correlator_that_returns_the_wrong_type_fails():
    """A dict is not an `OperationRef`. `sync.telemetry.ingest` reads `.operation_id` and `.path`
    off whatever arrives, so the wrong shape fails there naming a field rather than here naming
    the correlator.
    """

    class WrongType(_CorrectCorrelator):
        def operation_for_request(self, http_method: str, path: str):
            answer = super().operation_for_request(http_method, path)
            return None if answer is None else answer.model_dump()

    with pytest.raises(ConformanceFailure, match="must return an OperationRef or None"):
        _check_correlator(WrongType())


def test_a_correlator_without_a_vendor_id_fails():
    """`isinstance` verifies that the attribute is *there* and says nothing about what it holds.
    An empty one keys every `observed_call` row this correlator produces under nothing.
    """

    class Anonymous(_CorrectCorrelator):
        vendor_id = ""

    assert isinstance(Anonymous(), RequestCorrelator)
    with pytest.raises(ConformanceFailure, match="vendor_id"):
        _check_correlator(Anonymous())


def test_a_correlator_whose_vendor_id_is_not_a_string_fails():
    """The half of the attribute rule `runtime_checkable` genuinely cannot reach. Presence it does
    check, on Python 3.12; type it does not, so an integer here satisfies `isinstance` and then
    fails wherever the value is compared against a vendor id or written to a text column.
    """

    class Numeric(_CorrectCorrelator):
        vendor_id = 42

    assert isinstance(Numeric(), RequestCorrelator)
    with pytest.raises(ConformanceFailure, match="vendor_id"):
        _check_correlator(Numeric())


def test_a_correlator_that_answers_differently_the_second_time_fails():
    """Every stage here is idempotent, and a correlator sits inside one. One whose answer depends
    on how many times it has been asked makes `observed_call` a record of ingest ordering, and the
    same batch re-delivered -- which at-least-once OTLP delivery guarantees will happen -- folds
    into a different operation than it did the first time.
    """

    class Drifts(_CorrectCorrelator):
        def __init__(self) -> None:
            self._calls = 0

        def operation_for_request(self, http_method: str, path: str):
            self._calls += 1
            answer = super().operation_for_request(http_method, path)
            if answer is None:
                return None
            return answer.model_copy(
                update={"operation_id": answer.operation_id + str(self._calls)}
            )

    with pytest.raises(ConformanceFailure, match="must give the same answer"):
        _check_correlator(Drifts())


def test_an_identifier_that_is_not_in_the_request_is_reported_against_the_case():
    """A precondition failing is not the same as a rule passing. An identifier the request does
    not contain makes the privacy rule vacuous -- every correlator passes it, including one that
    returns the raw path -- so the kit says the case is wrong rather than saying the correlator is
    right.
    """
    with pytest.raises(ConformanceFailure, match="identifier must appear"):
        check_request_correlator(
            _CorrectCorrelator(), known_request=_KNOWN_REQUEST, identifier="ch_not_in_this_path"
        )


def test_a_known_request_that_does_not_resolve_is_reported_against_the_case():
    """The same discipline. If the request the author supplied correlates to nothing there is no
    returned template to inspect, and every rule that reads one is vacuous.
    """
    with pytest.raises(ConformanceFailure, match="must resolve to an operation"):
        check_request_correlator(
            _CorrectCorrelator(),
            known_request=("GET", "/v1/nothing_here/ch_3PjkLm2eZvKYlo2C1cQrSt"),
            identifier=_IDENTIFIER,
        )
