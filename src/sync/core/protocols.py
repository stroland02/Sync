"""The four plugin protocols. A third-party adapter implements one of these."""

from __future__ import annotations

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

    def operation_for_symbol(self, symbol: str) -> OperationRef | None: ...


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
class Remediator(Protocol):
    """Turns a finding into a proposed patch."""

    strategy: str

    def can_handle(self, finding: Finding, change: VendorChange) -> bool: ...

    def propose(
        self, finding: Finding, change: VendorChange, site: CallSite, repo: RepoRef, diagnostics: str = ""
    ) -> Patch: ...
