"""Data contracts shared by every Sync component.

This module imports nothing from any sibling package. That is the constraint
the plugin SDK rests on: a third party writing an adapter depends on
`sync.core` alone.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

Severity = Literal["breaking", "deprecation", "addition", "info"]
ChangeSource = Literal["oasdiff", "changelog", "sdk-release"]
PatchStrategy = Literal["codemod", "agent"]
FindingStatus = Literal["open", "patched", "abandoned"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


class RepoRef(BaseModel):
    """A specific checkout of a customer repository."""

    repo_id: str
    url: str
    local_path: str
    head_sha: str


class CallSite(BaseModel):
    """One place in the customer's code that calls a vendor API."""

    id: str | None = None
    repo_id: str
    path: str
    line: int
    col: int
    vendor_id: str
    operation_id: str
    symbol: str
    args_keys: list[str] = Field(default_factory=list)
    response_fields_read: list[str] = Field(default_factory=list)
    sdk_version: str
    content_hash: str
    indexed_at: datetime = Field(default_factory=_now)


class VendorChange(BaseModel):
    """One change a vendor made between two versions of its API."""

    id: str | None = None
    vendor_id: str
    from_version: str
    to_version: str
    kind: str
    operation_id: str
    path_ptr: str
    severity: Severity
    source: ChangeSource
    raw: dict[str, Any] = Field(default_factory=dict)
    detected_at: datetime = Field(default_factory=_now)


class Finding(BaseModel):
    """A vendor change intersected with a call site that it affects."""

    id: str | None = None
    detector: str
    call_site_id: str
    vendor_change_id: str | None = None
    severity: Severity
    rationale: str
    status: FindingStatus = "open"
    created_at: datetime = Field(default_factory=_now)


class Patch(BaseModel):
    """A proposed source change, not yet trusted."""

    diff: str
    strategy: PatchStrategy
    rationale: str


class VerifyResult(BaseModel):
    """The outcome of a verification step. `diagnostics` is fed back to the patcher."""

    ok: bool
    diagnostics: str = ""


class Evidence(BaseModel):
    """Everything a human reviewer needs to judge a pull request without trusting us."""

    spec_diff: dict[str, Any]
    changelog_entry: str
    call_sites: list[str]
    ci_run_url: str


class OperationRef(BaseModel):
    """An OpenAPI operation, addressed the way both a spec diff and a call site can find it."""

    operation_id: str
    http_method: str
    path: str
