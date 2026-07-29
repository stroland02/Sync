"""What an adapter must guarantee, expressed as something an author can run.

`isinstance(adapter, VendorAdapter)` is a `runtime_checkable` Protocol check, and the standard
library is explicit that those verify only the presence of method *names*. Signatures, return
types and behaviour are unchecked. So an adapter that raises where it must return `None`, or
returns a string where an `OperationRef` is required, satisfies `isinstance` and then fails
somewhere inside the pipeline, with a diagnostic naming Sync's internals rather than the
author's mistake.

That gap matters more here than it would elsewhere. The design document's argument for open
core is that a live codebase calls dozens of third-party APIs, we cannot write dozens of
adapters ourselves, and the interface therefore has to be good enough that vendors and users
write them. The interface is the product, and until now an outside author had no way to find
out whether theirs was correct.

The invariants below were harvested from the docstrings of the implementations in this
repository, where they were stated as prose an outside author would never see.

All five protocols have a kit. `RequestCorrelator` went without one longest, on the reading that
its guarantee is `operation_for_symbol`'s rule addressed by path instead of by symbol, and that
reading was wrong in the way that matters. Its rule about declining is the same rule; the rule
above it is not a correctness rule at all. `operation_for_request` is handed a real observed path
with a live customer identifier in it and must answer with the vendor's published template, and
that substitution is the only place a customer's identifiers stop travelling. Everywhere else in
this kit a broken guarantee produces a wrong answer some gate downstream refuses. There is no gate
downstream of this one.

Two things a kit of this shape cannot reach, said here rather than left to be discovered:

- **A precondition failing is not the same as a rule passing.** Several checks need a case from
  the author -- a symbol that resolves, a repository with call sites in it, a detector whose
  input reaches its thresholds. Each of those is checked and named, because a case that
  exercises nothing passes everything. That is not hypothetical: probing this kit against the
  five detectors here, `StatusRateDetector` passed every rule while emitting no findings at
  all, on a fixture a hundred and twenty calls short of its floor.
- **Behaviour that needs a language-specific artifact stays prose.** Whether `static_verify`
  subtracts a pre-existing baseline correctly needs a checkout that already fails to compile,
  committed in that state; the kit will not commit to somebody's repository and cannot author a
  compile error in a language it does not know. `_check_static_verify` says which of that
  method's three documented properties are checked and which is not.

**This module imports nothing outside `sync.core`,** because it ships with the SDK. A
conformance kit that needs `sync.graph` is not a kit, it is an integration test. The one place
that bites is `_check_findings_do_not_collide`, which is about a natural key `sync.graph`
owns: the triple is restated here rather than imported, and if the store's key ever changes
this is the second place to change.
"""

from __future__ import annotations

import inspect
import os
import tempfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from sync.core.models import CallSite, Finding, OperationRef, Patch, RepoRef, VerifyResult


class ConformanceFailure(AssertionError):
    """An adapter broke a documented guarantee.

    An `AssertionError` so a `pytest` run reports it as a failure rather than an error, and a
    distinct type so an author can catch it deliberately.
    """


def _fail(rule: str, detail: str) -> None:
    raise ConformanceFailure(f"{rule}\n  {detail}")


def check_vendor_adapter(adapter: Any, *, known_symbol: str) -> None:
    """Check `adapter` against every guarantee `VendorAdapter` states but cannot enforce.

    `known_symbol` is a symbol the adapter is expected to resolve — an author's own example,
    since the kit has no fixtures of its own and must run outside this repository.

    Raises `ConformanceFailure` naming the broken rule. Returns None when the adapter conforms.
    """
    _check_vendor_id(adapter)
    _check_operation_for_symbol(adapter, known_symbol)
    _check_fetch_changes(adapter)


def _check_vendor_id(adapter: Any) -> None:
    vendor_id = getattr(adapter, "vendor_id", None)
    if not isinstance(vendor_id, str) or not vendor_id:
        _fail(
            "vendor_id must be a non-empty string.",
            "It is the key every row this adapter produces is filed under, and a detector is "
            f"scoped to one vendor by it. Got {vendor_id!r}.",
        )


def _check_operation_for_symbol(adapter: Any, known_symbol: str) -> None:
    resolve = getattr(adapter, "operation_for_symbol", None)
    if resolve is None:
        _fail("operation_for_symbol must exist.", "It is how a call site becomes an operation.")

    parameters = inspect.signature(resolve).parameters
    if "language" not in parameters:
        _fail(
            "operation_for_symbol must accept a keyword-only `language` argument.",
            "The indexer passes it on every call, so an adapter that does not accept it raises "
            "TypeError on the first call site it sees. An adapter whose SDK languages spell "
            "symbols identically may ignore the value, but must accept the argument.",
        )

    try:
        unknown = resolve("this.symbol.does.not.exist", language=None)
    except Exception as exc:  # noqa: BLE001 - the point is that nothing may escape
        _fail(
            "operation_for_symbol must return None for an unknown symbol, not raise.",
            "An unresolved symbol is visibly unresolved and countable; an exception aborts an "
            f"indexing run over one call site the adapter did not recognise. Raised {exc!r}.",
        )
    if unknown is not None:
        _fail(
            "operation_for_symbol must return None for an unknown symbol, not a guess.",
            "A wrong operation produces a finding against code that never made the call, and "
            f"nobody learns it was wrong. Got {unknown!r}.",
        )

    resolved = resolve(known_symbol, language=None)
    if resolved is not None and not isinstance(resolved, OperationRef):
        _fail(
            "operation_for_symbol must return an OperationRef or None.",
            f"Got {type(resolved).__name__}. The pipeline reads attributes off this value, so a "
            "wrong type fails far from the adapter and names a field rather than the cause.",
        )


def _check_fetch_changes(adapter: Any) -> None:
    """`fetch_changes` may raise. What it may not do is return something a caller cannot loop over.

    An earlier version of this kit asserted that `fetch_changes` must not raise for a version
    pair it cannot serve, and running it against the real adapters proved that wrong within a
    minute. `StripeAdapter` raises `FileNotFoundError` when a pinned specification is absent,
    and it is right to: a missing specification is an environment failure, and answering it with
    an empty iterable would report that the vendor changed nothing when in fact nothing was
    looked at. That is a false negative in the one direction this system must not have.

    So the rule is narrower than it first appeared. If the call returns, the result has to be
    iterable, because every caller writes a for loop over it and `None` is the shape that
    crashes there.
    """
    fetch = getattr(adapter, "fetch_changes", None)
    if fetch is None:
        _fail("fetch_changes must exist.", "It is how a vendor's artifacts become changes.")

    try:
        changes = fetch("v1", "v1")
    except Exception:  # noqa: BLE001 - raising is permitted; see the docstring
        return

    try:
        iter(changes)
    except TypeError:
        _fail(
            "fetch_changes must return an iterable when it returns at all.",
            "Every caller writes `for change in ...`, and None is the shape that crashes that "
            f"loop. Got {type(changes).__name__}.",
        )


def check_remediator(
    remediator: Any,
    finding: Any,
    change: Any,
    site: Any,
    repo: Any,
) -> None:
    """Check `remediator` against the guarantees `Remediator` states but cannot enforce.

    The caller supplies a finding, a change, a call site and a repository whose working tree the
    remediator is expected to edit. The kit has no fixtures of its own and must run outside this
    repository, so the case comes from the author.

    Raises `ConformanceFailure` naming the broken rule. Returns None when the remediator conforms.
    """
    _check_strategy(remediator)
    _check_propose_touches_the_clone(remediator, finding, change, site, repo)


def _check_strategy(remediator: Any) -> None:
    strategy = getattr(remediator, "strategy", None)
    if not isinstance(strategy, str) or not strategy:
        _fail(
            "strategy must be a non-empty string.",
            "It is recorded on every attempt in the migration corpus, and routing reads it to "
            f"decide which tier produced a patch. Got {strategy!r}.",
        )


def _check_propose_touches_the_clone(
    remediator: Any, finding: Any, change: Any, site: Any, repo: Any
) -> None:
    """A patch is what is on disk, not what the diff says is on disk.

    This is the rule worth having a kit for. Nothing downstream applies `patch.diff`: the graph
    stores the `Patch`, static verification typechecks the working tree, and the push stages
    tracked modifications. So a remediator that computes the correct edit and returns it without
    writing produces a branch carrying an empty commit, and reports success while doing it. The
    verdict is green and the pull request is empty.

    It has shipped twice in this repository. It is invisible from the diff, which is correct in
    both cases, and it is invisible from a test that asserts on the returned value.

    The mirror matters too. An empty diff means the remediator declined, and a decline must leave
    the tree alone -- writing identical bytes still updates an mtime, and a tool that touches
    files it decided not to edit is one nobody trusts near a working tree.
    """
    target = Path(repo.local_path) / site.path
    if not target.exists():
        _fail(
            "the supplied call site must exist in the supplied repository.",
            f"{target} is not there, so this check cannot observe whether propose writes to it. "
            "Fix the case handed to the kit, not the remediator.",
        )

    before = target.read_bytes()

    # The decline case is detected by mtime, because a remediator that rewrites identical bytes
    # changes no content. But a filesystem records mtimes far more coarsely than the clock --
    # measured here at 184 of 200 identical-byte rewrites leaving `st_mtime_ns` untouched -- so
    # comparing against the file's current mtime detects a write only when it happens to cross a
    # tick boundary. That is a check which silently fails to fire, guarding a rule that has
    # already shipped broken twice.
    #
    # Backdating the baseline removes the timing entirely: any write, at any instant, moves the
    # mtime forward from a value no write could have produced. Metadata only; the content the
    # remediator is about to read is untouched.
    stat = target.stat()
    backdated = stat.st_mtime_ns - 10_000_000_000
    os.utime(target, ns=(stat.st_atime_ns, backdated))

    patch = remediator.propose(finding, change, site, repo)

    after = target.read_bytes()
    changed = after != before
    touched = target.stat().st_mtime_ns != backdated
    diff = getattr(patch, "diff", None)
    if not isinstance(diff, str):
        _fail(
            "propose must return a Patch whose diff is a string.",
            f"Got {type(diff).__name__} for the diff.",
        )

    if diff.strip() and not changed:
        _fail(
            "propose returned a diff but did not change the clone.",
            "Nothing downstream applies the diff: the tree is typechecked and the tracked "
            "modifications are staged, so this produces an empty commit and reports success. "
            "Write the edit to the file, then describe it.",
        )
    if not diff.strip() and (changed or touched):
        _fail(
            "propose declined and still changed the clone.",
            "An empty diff means no patch. Writing anyway -- even identical bytes -- updates an "
            "mtime and edits a file the remediator decided to leave alone.",
        )


# The file the kit leaves in the clone to find out whether verification puts back what it moved.
# Named rather than random so an interrupted run leaves something an author can recognise and
# delete, and dot-prefixed so a source scan does not pick it up as a file to index.
_UNTRACKED_MARKER = ".sync-conformance-untracked"

_NO_PATCH = Patch(
    diff="",
    strategy="codemod",
    rationale="the conformance kit verifying an unmodified checkout",
)


def check_language_adapter(
    adapter: Any,
    repo: Any,
    *,
    installed_dependency: str | None = None,
) -> None:
    """Check `adapter` against every guarantee `LanguageAdapter` states but cannot enforce.

    `repo` is a `RepoRef` for a checkout the adapter is expected to own and find call sites in
    -- an author's own example, since the kit has no fixtures of its own and must run outside
    this repository. It must be a clean checkout: `prepare` runs against it, and an adapter that
    measures a typecheck baseline is right to refuse a tree with uncommitted changes in it.

    `installed_dependency` is a repository-relative path to a file the adapter's `prepare`
    installed -- `node_modules/stripe/index.d.ts` and its equivalents. Supplying it is what turns
    on the dependency-edit rule; an adapter for a language that installs nothing has none to
    supply, and the rule is skipped rather than passed.

    This runs the author's real toolchain against their real checkout, so it is slow in the way
    an install and a compiler are slow. That is the point: the rules below are about what those
    tools were pointed at.

    Raises `ConformanceFailure` naming the broken rule. Returns None when the adapter conforms.
    """
    _check_language_id(adapter)
    _check_matches(adapter, repo)
    _check_index(adapter, repo)
    _check_prepare_is_repeatable(adapter, repo)
    _check_discard_reports_what_it_did(adapter, repo)
    _check_static_verify(adapter, repo)
    if installed_dependency is not None:
        _check_static_verify_refuses_a_doctored_dependency(adapter, repo, installed_dependency)


def _check_language_id(adapter: Any) -> None:
    language_id = getattr(adapter, "language_id", None)
    if not isinstance(language_id, str) or not language_id:
        _fail(
            "language_id must be a non-empty string.",
            "It selects the adapter for a repository, it is the axis `operation_for_symbol` is "
            "given so one vendor's two SDKs can spell a symbol differently, and it is recorded "
            f"as `language` on every migration outcome. Got {language_id!r}.",
        )


def _check_matches(adapter: Any, repo: Any) -> None:
    """`matches` is dispatch, and it is asked of every adapter before any of them is chosen."""
    claimed = adapter.matches(repo)
    if not isinstance(claimed, bool):
        _fail(
            "matches must return a bool.",
            "The caller writes `if adapter.matches(repo)`, so a manifest path or a match object "
            "returned instead of a decision is truthy for every repository that has one at all: "
            f"the adapter claims another language's repositories. Got {type(claimed).__name__}.",
        )
    if not claimed:
        _fail(
            "matches must claim the repository the kit was handed.",
            "Everything below is measured against it, and an adapter that does not own it would "
            "make every rule after this one vacuous. Either the matcher is wrong or the case "
            "handed to the kit is; the kit cannot tell which.",
        )

    with tempfile.TemporaryDirectory() as empty:
        stranger = RepoRef(
            repo_id="conformance-empty", url="", local_path=empty, head_sha="0" * 40
        )
        try:
            answer = adapter.matches(stranger)
        except Exception as exc:  # noqa: BLE001 - the point is that nothing may escape
            _fail(
                "matches must answer for a repository it does not own, not raise.",
                "Every registered adapter is asked about every repository, before any of them is "
                "chosen. One that raises on a tree with no manifest in it takes down the "
                f"selection loop, and the traceback names the wrong adapter. Raised {exc!r}.",
            )
        if answer:
            _fail(
                "matches must not claim an empty directory.",
                "There is nothing in it to index and no manifest to have read, so a claim here is "
                "a matcher that claims everything -- which makes selection depend on registration "
                "order rather than on what the repository contains.",
            )


def _check_index(adapter: Any, repo: Any) -> None:
    first = _indexed(adapter, repo)
    if not first:
        _fail(
            "the repository handed to the kit must contain at least one call site.",
            "Every rule about what `index` emits is vacuous against a repository it finds "
            "nothing in, and a kit that passes vacuously is worse than no kit. Fix the case "
            "handed to the kit, or the indexer -- the kit cannot tell which.",
        )

    root = Path(repo.local_path)
    for site in first:
        if not isinstance(site, CallSite):
            _fail(
                "index must yield CallSite objects.",
                f"Got {type(site).__name__}. Everything downstream reads typed attributes off "
                "these, so another shape fails at the first field somebody names.",
            )
        if PurePosixPath(site.path).is_absolute() or PureWindowsPath(site.path).is_absolute():
            _fail(
                "a call site's path must be repository-relative.",
                f"Got {site.path!r}. Every consumer opens it as `Path(repo.local_path) / path`, "
                "and pathlib discards the left-hand side when the right one is absolute -- "
                "silently, so the remediator edits a file outside the clone rather than failing.",
            )
        if "\\" in site.path:
            _fail(
                "a call site's path must be spelled with forward slashes.",
                f"Got {site.path!r}. It is stored, put in a pull request and opened by the "
                "customer's CI, which is not the machine the adapter was written on. A backslash "
                "path passes every test its author runs and names no file there.",
            )
        if not (root / site.path).exists():
            _fail(
                "a call site's path must exist in the repository it was indexed from.",
                f"{site.path!r} is not in {root}. A finding against it has no file to patch, and "
                "the failure arrives at the remediator rather than here.",
            )
        if site.repo_id != repo.repo_id:
            _fail(
                "a call site must carry the repo_id of the repository it was found in.",
                f"Got {site.repo_id!r} for {repo.repo_id!r}. It is half the call site's identity "
                "in the graph, so a wrong one files the row under a repository nobody indexed.",
            )

    if _site_keys(first) != _site_keys(_indexed(adapter, repo)):
        _fail(
            "two indexing passes over an unchanged checkout must produce the same call sites.",
            "INDEX is a pipeline stage and every stage here is idempotent: re-running it "
            "converges on the same rows. One that does not leaves the graph holding whichever "
            "run happened last, and no query can tell which run that was.",
        )


def _indexed(adapter: Any, repo: Any) -> list:
    produced = adapter.index(repo)
    try:
        iter(produced)
    except TypeError:
        _fail(
            "index must return an iterable of CallSite, never None.",
            "The caller writes `for site in adapter.index(repo)`, and None is the shape that "
            f"crashes that loop. Got {type(produced).__name__}.",
        )
    return list(produced)


def _site_keys(sites: list) -> list:
    """What makes two indexing passes the same, and nothing incidental.

    `id` and `indexed_at` are excluded: the graph derives the row id itself and stamps the
    timestamp, so neither is the adapter's contribution and a difference in either says nothing.
    Compared as a sorted collection rather than a sequence, because nothing downstream depends
    on the order call sites arrive in and pinning it would fail on a filesystem walk order.
    """
    return sorted(
        (
            site.repo_id, site.path, site.line, site.col, site.vendor_id, site.operation_id,
            site.symbol, tuple(site.args_keys), tuple(site.response_fields_read),
            site.sdk_version, site.content_hash, site.loop_depth,
        )
        for site in sites
    )


def _check_prepare_is_repeatable(adapter: Any, repo: Any) -> None:
    adapter.prepare(repo)
    try:
        adapter.prepare(repo)
    except Exception as exc:  # noqa: BLE001 - the point is that nothing may escape
        _fail(
            "prepare must tolerate being called again on the same checkout.",
            "One clone serves every finding in a run, and the driver reaches `prepare` again for "
            "each of them. An adapter that only survives being prepared once abandons every "
            f"finding after the first, on a repository where nothing is wrong. Raised {exc!r}.",
        )


def _check_discard_reports_what_it_did(adapter: Any, repo: Any) -> None:
    removed = adapter.discard_contaminated_dependencies(repo)
    if not isinstance(removed, bool):
        _fail(
            "discard_contaminated_dependencies must return a bool.",
            f"Got {type(removed).__name__}. The return value is read as a decision about whether "
            "the next finding pays for a reinstall.",
        )
    if removed:
        _fail(
            "discard_contaminated_dependencies claimed a removal when nothing was contaminated.",
            "Nothing has patched this checkout: `prepare` has just run and no remediator has "
            "touched it. Returning True here is a reinstall per finding, and the one signal an "
            "operator has that a dependency was doctored now fires for every run.",
        )


def _check_static_verify(adapter: Any, repo: Any) -> None:
    """The gate between a patch and a customer's repository, checked as far as a kit can reach.

    Three properties of `static_verify` are load-bearing, and only one of them is mechanically
    checkable without knowing the language:

    - It measures the tree a push would carry, holding the agent's untracked and ignored files
      out of the compile. The half of that a kit can check is the restore: a file the
      verification moved has to come back. Whether the *verdict* excluded it needs a source file
      that fails to compile, which is language-specific and which only the author can write.
    - It subtracts a pre-existing baseline, so errors the checkout already had do not fail a
      patch. Checking that needs a checkout that already fails to compile, committed in that
      state before `prepare` measures it. The kit will not commit to somebody's repository, and
      cannot author a compile error in a language it does not know. This one stays prose.
    - It refuses a patch that edited an installed dependency. That is checkable, and it is
      `_check_static_verify_refuses_a_doctored_dependency` -- but only when the author says
      where an installed dependency is, because the kit has no language-agnostic way to find one.

    What is checked here is the shape of the answer and the state of the tree afterwards.
    """
    marker = Path(repo.local_path) / _UNTRACKED_MARKER
    marker.write_text("left here by the conformance kit\n", encoding="utf-8")
    expected = marker.read_bytes()
    try:
        result = adapter.static_verify(repo, _NO_PATCH)

        if not isinstance(result, VerifyResult):
            _fail(
                "static_verify must return a VerifyResult.",
                f"Got {type(result).__name__}. The caller reads `.ok` and `.diagnostics` off it "
                "several nodes away, so a bool fails there as an AttributeError about a field "
                "rather than here as a statement about the adapter.",
            )
        if not result.ok and not result.diagnostics.strip():
            _fail(
                "a failed verification must carry diagnostics.",
                "The diagnostics string is the entire input to the next patch attempt. A failure "
                "carrying none spends an agent run to arrive back where it started, and routing "
                "cannot tell an unverifiable patch from a toolchain that did not run.",
            )
        if not marker.exists() or marker.read_bytes() != expected:
            _fail(
                "static_verify must put back every file it held out of the compile.",
                "Measuring the tree a push would carry means moving the agent's untracked and "
                "ignored files aside. Doing that without restoring them destroys work the next "
                "attempt needed, and reports a verdict while doing it.",
            )
    finally:
        marker.unlink(missing_ok=True)


def _check_static_verify_refuses_a_doctored_dependency(
    adapter: Any, repo: Any, installed_dependency: str
) -> None:
    """An edit inside an installed dependency satisfies a gate the customer's CI will not.

    No checkout of the branch contains that file: the install is theirs, and `git add -u` stages
    nothing under it. So a verification that compiles against the doctored copy delivers a green
    verdict about a tree that will never exist.

    Refusing by raising is as good as returning a failure and is what `TypeScriptAdapter` does,
    on the argument that the edit cannot be undone without a reinstall and every later attempt
    would meet the same doctored file. The rule is only that the answer is not `ok`.
    """
    target = Path(repo.local_path) / installed_dependency
    if not target.exists():
        _fail(
            "the supplied installed dependency must exist in the supplied repository.",
            f"{target} is not there after `prepare`, so this check cannot observe whether "
            "static_verify refuses an edit to it. Fix the case handed to the kit, not the "
            "adapter.",
        )

    original = target.read_bytes()
    stat = target.stat()
    try:
        target.write_bytes(original + b"\nedited by the conformance kit\n")
        # An edit under an installed tree is found by comparing mtimes against the install, and
        # a filesystem records mtimes far more coarsely than the clock -- a write landing inside
        # the same tick as the install leaves the timestamp equal to it, and "later than the
        # install" is then false for an edit that really happened. Moved forward explicitly, so
        # this check does not depend on which tick the write landed in.
        written = target.stat()
        os.utime(target, ns=(written.st_atime_ns, written.st_mtime_ns + 10_000_000_000))

        try:
            result = adapter.static_verify(repo, _NO_PATCH)
        except Exception:  # noqa: BLE001 - refusing by raising is permitted; see the docstring
            return
        if getattr(result, "ok", False):
            _fail(
                "static_verify approved a patch that edited an installed dependency.",
                f"{installed_dependency} was changed after the install and the verification "
                "passed anyway. The compiler was resolving a file no checkout of the branch "
                "contains, so the verdict describes a tree nobody will ever have.",
            )
    finally:
        target.write_bytes(original)
        os.utime(target, ns=(stat.st_atime_ns, stat.st_mtime_ns))


def check_detector(detector: Any) -> None:
    """Check `detector` against the guarantees `Detector` states but cannot enforce.

    The detector arrives already constructed, holding whatever graph or fixture it queries --
    the five in this repository take a store, a specification, a repository id and a set of
    thresholds between them, and no signature the kit could impose would fit all of them. What
    it must be handed is a detector whose input does not change while the kit runs, because two
    of the rules below are about asking the same question twice.

    Raises `ConformanceFailure` naming the broken rule. Returns None when the detector conforms.
    """
    _check_detector_id(detector)
    first = _scanned(detector)
    if not first:
        _fail(
            "the detector handed to the kit must find at least one finding.",
            "Every rule about what `scan` emits is vacuous against a scan that emits nothing, "
            "and a kit that passes vacuously is worse than no kit. Either the input this "
            "detector was constructed over reaches none of its thresholds, or the detector "
            "finds nothing it should -- the kit cannot tell which.",
        )
    _check_findings_are_usable(detector, first)
    _check_findings_do_not_collide(first)
    _check_scans_agree(first, _scanned(detector))


def _check_detector_id(detector: Any) -> None:
    detector_id = getattr(detector, "detector_id", None)
    if not isinstance(detector_id, str) or not detector_id:
        _fail(
            "detector_id must be a non-empty string.",
            "It is stamped on every finding and it is what attributes a false positive back to "
            f"the code that raised it. Got {detector_id!r}.",
        )


def _scanned(detector: Any) -> list:
    produced = detector.scan()
    try:
        iter(produced)
    except TypeError:
        _fail(
            "scan must return an iterable of Finding, never None.",
            "The caller writes `for finding in detector.scan()`, and None is the shape that "
            f"crashes that loop. Got {type(produced).__name__}.",
        )
    return list(produced)


def _check_findings_are_usable(detector: Any, findings: list) -> None:
    detector_id = detector.detector_id
    for finding in findings:
        if not isinstance(finding, Finding):
            _fail(
                "scan must yield Finding objects.",
                f"Got {type(finding).__name__}. One remediation pipeline consumes every "
                "detector's output, and it reads typed attributes off what arrives.",
            )
        if finding.detector != detector_id:
            _fail(
                "a finding must carry the detector_id of the detector that raised it.",
                f"Got {finding.detector!r} from a detector calling itself {detector_id!r}. That "
                "field is how a false positive is attributed back to the code that produced it, "
                "and a finding signed with a name nothing answers to cannot be attributed.",
            )
        if not isinstance(finding.call_site_id, str) or not finding.call_site_id:
            _fail(
                "a finding must name the call site it is about.",
                "A finding addresses its location by call_site_id and by nothing else, so one "
                f"carrying {finding.call_site_id!r} has no line to report and no file to patch. "
                "A detector that cannot establish the id should drop the finding and count it.",
            )


def _check_findings_do_not_collide(findings: list) -> None:
    """Two findings the graph cannot tell apart are one row, and nobody is told which one.

    A finding's identity is `(detector, call_site_id, vendor_change_id, claim)` and the insert
    is ON CONFLICT DO NOTHING. So a detector that says two different things about one call site
    under one change and one claim keeps whichever it emitted first: the second is dropped
    silently, at the store, after the detector has already decided both were worth raising.

    `claim` joined that key after this rule was written, and this rule followed it rather than
    being relaxed to admit the three detectors it was failing. The distinction matters: the
    rule still fires on two findings sharing the whole key, which is what its broken example
    now emits. A rule loosened to pass its own violators would be worse than the defect, since
    it would then certify the defect as conformant.

    Emitting the same finding twice is not that. Identical rows collapse to the identical row,
    which loses nothing, so only findings that *disagree* under one key are reported here.
    """
    seen: dict[tuple, Any] = {}
    for finding in findings:
        key = (
            finding.detector, finding.call_site_id, finding.vendor_change_id or "", finding.claim
        )
        earlier = seen.get(key)
        if earlier is None:
            seen[key] = finding
            continue
        if (earlier.severity, earlier.rationale, earlier.status) == (
            finding.severity, finding.rationale, finding.status
        ):
            continue
        _fail(
            "two findings from one scan share the same natural key.",
            "The graph identifies a finding by (detector, call_site_id, vendor_change_id, "
            f"claim) and inserts ON CONFLICT DO NOTHING, so only one of these is stored:\n    "
            f"{earlier.rationale}\n    {finding.rationale}\n  Both carry claim {finding.claim!r}. "
            "Give them claims that name the two different things they say, or say both things "
            "in one finding.",
        )


def _check_scans_agree(first: list, second: list) -> None:
    if _finding_keys(first) != _finding_keys(second):
        _fail(
            "two scans of an unchanged graph must produce the same findings.",
            "DETECT is a pipeline stage and every stage here is idempotent: re-running it over "
            "the same input converges on the same rows. A detector whose answer depends on how "
            "many times it has been asked makes the graph a record of run ordering.",
        )


def _finding_keys(findings: list) -> list:
    """What makes two scans the same, and nothing incidental.

    `id` and `created_at` are excluded: the graph derives the row id from the natural key and
    stamps the timestamp itself, so neither is the detector's contribution. Sorted, because
    nothing downstream depends on the order findings are emitted in.
    """
    return sorted(
        (
            finding.detector, finding.call_site_id, finding.vendor_change_id or "",
            finding.claim, finding.severity, finding.rationale, finding.status,
        )
        for finding in findings
    )


# What the kit asks a correlator about when it wants an answer of None. Synthesized rather than
# taken from the author, the same way `_check_operation_for_symbol` synthesizes its unknown
# symbol: the negative case is the kit's to state, and an author who supplied it could supply one
# their correlator happens to resolve. The empty path is not decoration -- `sync.cli` hands this
# `urlsplit(url).path`, which is the empty string for a URL carrying no path at all.
_UNRECOGNISED_REQUESTS = (
    ("GET", "/sync-conformance/no-such-resource/2f8b1c"),
    ("GET", ""),
    ("GET", "/"),
)

# The verbs the method rule is probed with. HEAD is deliberately absent: reading a HEAD request as
# addressing the GET operation is a defensible reading of RFC 9110, and probing it would make the
# kit reject a correlator over a judgement the protocol never made. The rule below still applies to
# a HEAD request an author hands in as their own case, and that is the one place a correlator could
# conform and disagree with it -- argue it there rather than discovering it as a failure.
_PROBE_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")


def check_request_correlator(
    correlator: Any,
    *,
    known_request: tuple[str, str],
    identifier: str,
) -> None:
    """Check `correlator` against every guarantee `RequestCorrelator` states but cannot enforce.

    `known_request` is an `(http_method, path)` pair the correlator is expected to resolve, and
    `identifier` is the substring of that path which is a live customer identifier -- the charge
    id in `/v1/charges/ch_3PjkLm2eZvKYlo2C1cQrSt`. Both come from the author, since the kit has no
    fixtures of its own and must run outside this repository, and the identifier cannot be derived
    from the path: which segment is an id and which is a resource name is vendor knowledge.

    This is the only check in the kit whose first rule is a privacy boundary rather than a
    correctness one, and the difference is worth stating. Everywhere else a broken guarantee
    produces a wrong answer, and the wrong answer is caught by a gate downstream -- a bad patch
    fails `tsc`, a bad finding is declined by a reviewer. There is no gate downstream of this one.
    A path that arrives carrying a customer's identifier is written to `observed_call`, joined into
    findings, and rendered into the body of a pull request opened on a repository Sync does not
    own. `CLAUDE.md` says we never hold customer secrets and does not qualify it; this is the check
    that makes that sentence true of the telemetry path.

    Raises `ConformanceFailure` naming the broken rule. Returns None when the correlator conforms.
    """
    _check_correlator_vendor_id(correlator)
    _check_unrecognised_requests_answer_none(correlator)
    resolved = _check_known_request_resolves(correlator, known_request, identifier)
    _check_the_identifier_does_not_survive(resolved, known_request, identifier)
    _check_the_method_is_the_one_asked_about(correlator, known_request, resolved)
    _check_correlation_is_deterministic(correlator, known_request, resolved)


def _check_correlator_vendor_id(correlator: Any) -> None:
    """`isinstance` reaches further here than it does for a method, and still not far enough.

    A `runtime_checkable` Protocol with a non-method member does check that the attribute is
    present -- measured on Python 3.12, an object without `vendor_id` fails `isinstance` against
    `RequestCorrelator`. What it does not check is what the attribute holds: `vendor_id = 42` and
    `vendor_id = ""` both satisfy it. So this rule is narrower than the one on `VendorAdapter` and
    is worth having for the half that remains.
    """
    vendor_id = getattr(correlator, "vendor_id", None)
    if not isinstance(vendor_id, str) or not vendor_id:
        _fail(
            "vendor_id must be a non-empty string.",
            "Every observed call this correlator resolves is filed under it, and it is what joins "
            "a span to the call sites indexed for the same vendor. `isinstance` verifies that the "
            f"attribute exists and nothing about its value. Got {vendor_id!r}.",
        )


def _correlate(correlator: Any, http_method: str, path: str, *, rule: str, why: str) -> Any:
    resolve = getattr(correlator, "operation_for_request", None)
    if resolve is None:
        _fail(
            "operation_for_request must exist.",
            "It is how a span becomes an operation, and it is the whole of this protocol.",
        )
    try:
        return resolve(http_method, path)
    except Exception as exc:  # noqa: BLE001 - the point is that nothing may escape
        _fail(rule, f"{why} Asked {http_method!r} {path!r} and it raised {exc!r}.")


def _check_unrecognised_requests_answer_none(correlator: Any) -> None:
    """None rather than a guess, and an answer rather than an exception.

    Both halves are the same rule seen from two sides, and both are about a correlator being asked
    about traffic it was never expected to know. One correlator is handed every client span in a
    batch, most of them addressed to other hosts entirely, so declining is the ordinary case rather
    than the exceptional one -- and an exception there abandons the whole batch over one request.

    A guess is the worse half. `sync.signals.stripe.adapter` states it exactly: a missing binding
    is visibly unresolved and can be counted; a wrong one produces a finding against code that
    never made the call, and nobody learns it was wrong. An observed binding carries the `observed`
    rung, which the graph surface reports as the most trustworthy of the three, so a guess here is
    laundered into the rung an agent weighs a patch by.
    """
    for http_method, path in _UNRECOGNISED_REQUESTS:
        answer = _correlate(
            correlator,
            http_method,
            path,
            rule="operation_for_request must answer for a request it cannot resolve, not raise.",
            why=(
                "One correlator is asked about every client span in a batch, and most of them "
                "address something else. An exception abandons the batch over a request this "
                "correlator was never expected to recognise."
            ),
        )
        if answer is not None:
            _fail(
                "operation_for_request must return None for an unrecognised request, not a guess.",
                f"Asked {http_method!r} {path!r} and got {answer!r}. A missing binding is visibly "
                "unresolved and can be counted; a wrong one attributes real traffic to an "
                "operation nobody called, and it arrives carrying the `observed` rung, which is "
                "the one an agent trusts most.",
            )


def _check_known_request_resolves(
    correlator: Any, known_request: tuple[str, str], identifier: str
) -> Any:
    """The precondition every rule below rests on, checked and named rather than assumed.

    A case that exercises nothing passes everything. An identifier the path does not contain makes
    the privacy rule vacuous -- a correlator returning the raw path would sail through it -- and a
    request that resolves to nothing leaves no template to inspect at all.
    """
    http_method, path = known_request
    if identifier not in path:
        _fail(
            "the identifier must appear in the request path the kit was handed.",
            f"{identifier!r} is not in {path!r}, so the rule that it does not survive the call is "
            "vacuous: every correlator passes it, including one that returns the path unchanged. "
            "Fix the case handed to the kit, not the correlator.",
        )

    resolved = _correlate(
        correlator,
        http_method,
        path,
        rule="operation_for_request must not raise for the request the kit was handed.",
        why="It is the case the author supplied as one this correlator resolves.",
    )
    if resolved is None:
        _fail(
            "the request handed to the kit must resolve to an operation.",
            f"{http_method!r} {path!r} correlates to nothing, so there is no template to inspect "
            "and every rule below this one is vacuous. Either the case is wrong or the correlator "
            "resolves nothing at all -- the kit cannot tell which.",
        )
    if not isinstance(resolved, OperationRef):
        _fail(
            "operation_for_request must return an OperationRef or None.",
            f"Got {type(resolved).__name__}. `sync.telemetry.ingest` reads `.operation_id` and "
            "`.path` off what arrives, several stages away, so another shape fails there as an "
            "attribute error about a field rather than here as a statement about the correlator.",
        )
    return resolved


def _check_the_identifier_does_not_survive(
    resolved: Any, known_request: tuple[str, str], identifier: str
) -> None:
    """The rule this check exists for.

    `RequestCorrelator`'s docstring puts it in one sentence: the path is a URL path with real
    identifiers in it, what comes back addresses the operation with the vendor's own published
    template, and that substitution is the boundary at which a customer's identifiers stop
    travelling. The template is public data -- it appears in the vendor's own specification. The
    request path is not.

    Every string on the ref is checked rather than `path` alone, because every string on it is
    stored and every one of them is rendered. A correlator that substitutes the template correctly
    and then appends the id to the operation id has moved the leak rather than closed it, and a
    rule reading one field would certify that as conformant.
    """
    _, path = known_request
    for field in sorted(type(resolved).model_fields):
        value = getattr(resolved, field, None)
        if isinstance(value, str) and identifier in value:
            _fail(
                "the operation returned carried the request's own identifier.",
                f"`{field}` came back as {value!r} for the request {path!r}. What comes back must "
                "address the operation with the vendor's published template, which is public "
                "data; the request path is a customer's. This value is written to `observed_call`, "
                "joined into findings, and rendered into the body of a pull request on a "
                "repository we do not own, and nothing downstream removes it.",
            )


def _check_the_method_is_the_one_asked_about(
    correlator: Any, known_request: tuple[str, str], resolved: Any
) -> None:
    """A correlator that matches on the path alone binds a write to the operation that reads.

    One path is several operations -- `/v1/charges` is a list and a create -- and the span carries
    the method that tells them apart. Merging them is not a small loss: the efficiency detector's
    entire subject is how many times one unit of work called an operation, and a read folded into
    a write is a call count against the wrong one.

    Checked as a property of the answer rather than as a probe for a defect, because the property
    is the simpler statement: if the correlator says this request addressed operation X, and X is
    declared under `post`, then a `GET` request did not address it. Probed across several verbs on
    the author's own path as well, since a correlator that ignores the method answers the known
    request correctly by luck whenever the author's own verb is the one it always returns.
    """
    asked, path = known_request
    if resolved.http_method.lower() != asked.lower():
        _fail(
            "the operation returned must be the method it was asked about.",
            f"Asked {asked!r} {path!r} and got an operation declared under "
            f"{resolved.http_method!r}. One path is several operations and the method is what "
            "separates them, so this binds a request to an operation the customer did not make.",
        )

    for probe in _PROBE_METHODS:
        if probe.lower() == asked.lower():
            continue
        answer = _correlate(
            correlator,
            probe,
            path,
            rule="operation_for_request must answer for a request it cannot resolve, not raise.",
            why="A method a path does not serve is declined, not raised on.",
        )
        if answer is None:
            continue
        if not isinstance(answer, OperationRef):
            _fail(
                "operation_for_request must return an OperationRef or None.",
                f"Got {type(answer).__name__} for {probe!r} {path!r}.",
            )
        if answer.http_method.lower() != probe.lower():
            _fail(
                "the operation returned must be the method it was asked about.",
                f"Asked {probe!r} {path!r} and got an operation declared under "
                f"{answer.http_method!r}. The method is not being consulted, so every span for "
                "this path folds into one operation whichever verb produced it.",
            )


def _check_correlation_is_deterministic(
    correlator: Any, known_request: tuple[str, str], resolved: Any
) -> None:
    """The same span, correlated twice, is the same call.

    OTLP delivery is at-least-once and a collector re-sends whatever is still buffered rather than
    the batch it sent before, so the same span really does arrive twice. `observed_call` is keyed
    partly on the operation, so a correlator whose answer moves writes the second delivery to a
    different row instead of folding into the first -- and every rate derived from that table
    becomes a function of how often the ingest ran.
    """
    http_method, path = known_request
    again = _correlate(
        correlator,
        http_method,
        path,
        rule="operation_for_request must not raise for the request the kit was handed.",
        why="It resolved once already, so the second call is the same question.",
    )
    if again != resolved:
        _fail(
            "two correlations of one request must give the same answer.",
            f"Got {resolved!r} then {again!r}. OTLP delivery is at-least-once, so the same span "
            "arrives more than once by design; a correlator whose answer depends on how many "
            "times it has been asked makes `observed_call` a record of ingest ordering.",
        )
