"""The plugin protocols. A third-party adapter implements one of these."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Protocol, runtime_checkable

from sync.core.models import CallSite, Finding, OperationRef, Patch, RepoRef, VendorChange, VerifyResult


@runtime_checkable
class LanguageAdapter(Protocol):
    """Turns a repository into call sites, and verifies patches statically."""

    language_id: str

    def matches(self, repo: RepoRef) -> bool: ...

    def index(self, repo: RepoRef) -> Iterable[CallSite]: ...

    def prepare(self, repo: RepoRef) -> None: ...

    def static_verify(self, repo: RepoRef, patch: Patch) -> VerifyResult: ...

    def discard_contaminated_dependencies(self, repo: RepoRef) -> bool: ...


@runtime_checkable
class VendorAdapter(Protocol):
    """Turns a vendor's published artifacts into structured changes."""

    vendor_id: str

    def fetch_changes(self, from_version: str, to_version: str) -> Iterable[VendorChange]: ...

    def operation_for_symbol(
        self, symbol: str, *, language: str | None = None
    ) -> OperationRef | None: ...


@runtime_checkable
class RequestCorrelator(Protocol):
    """Turns an observed HTTP request back into the operation it addressed.

    Separate from `VendorAdapter` rather than a method on it, because the two are wanted at
    different times by different callers: the indexer needs `operation_for_symbol` and nothing
    else, and an adapter for a vendor whose traffic nobody instruments has no reason to
    implement this at all. Folding it into `VendorAdapter` would make every existing adapter
    fail a `runtime_checkable` test to add a capability none of them was asked for.

    The path is a URL path with real identifiers in it. What comes back addresses the operation
    with the vendor's own published template, which is public data -- that substitution is the
    boundary at which a customer's identifiers stop travelling.
    """

    vendor_id: str

    def operation_for_request(self, http_method: str, path: str) -> OperationRef | None: ...


@runtime_checkable
class Detector(Protocol):
    """Queries the graph and emits findings."""

    detector_id: str

    def scan(self) -> Iterable[Finding]: ...


@runtime_checkable
class PatchRunner(Protocol):
    """Drives a model against a clone until it stops.

    The narrowest thing that can be substituted. A runner is handed the prompt, the clone it
    may edit, and the identity every message it raises has to carry; it reports nothing back,
    because the clone is the report -- `AgentRemediator.propose` reads the diff from git
    rather than from a return value, so a runner that returned a patch would be describing
    work the tree either does or does not hold.

    Failure is a raised `RuntimeError` naming the identity. A runner owns the whole vocabulary
    of a failed run: the caller does not inspect the reason, and one that could not report a
    reason would move that handling back across the seam.

    One method, because one is the case that exists. M9's terminal outcomes and M10's parked
    runs each arrive with a real caller, and each widens this then.
    """

    def run(self, prompt: str, repo_path: Path, identity: str) -> None: ...


@runtime_checkable
class Remediator(Protocol):
    """Turns a finding into a proposed patch."""

    strategy: str

    def can_handle(self, finding: Finding, change: VendorChange) -> bool: ...

    def propose(
        self, finding: Finding, change: VendorChange, site: CallSite, repo: RepoRef, diagnostics: str = ""
    ) -> Patch: ...
