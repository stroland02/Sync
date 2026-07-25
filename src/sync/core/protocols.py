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

    def static_verify(self, repo: RepoRef, patch: Patch) -> VerifyResult: ...


@runtime_checkable
class VendorAdapter(Protocol):
    """Turns a vendor's published artifacts into structured changes."""

    vendor_id: str

    def fetch_changes(self, from_version: str, to_version: str) -> Iterable[VendorChange]: ...

    def operation_for_symbol(self, symbol: str) -> OperationRef | None: ...


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
