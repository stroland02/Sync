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
ChangeSource = Literal["oasdiff", "changelog", "sdk-release", "vendor-deprecation-table"]
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


class MigrationOutcome(BaseModel):
    """One repair attempt, recorded as shape rather than as source.

    The grain is one row per *attempt*, not per finding: a finding retried three times writes
    three rows, and `attempt_index` is what says so. A query counting findings by counting rows
    is wrong.

    Nothing here identifies a customer. The symbol is a shape, argument keys are salted
    digests, and neither the diff nor the file path is stored -- a path is customer structure
    even when the code is not included. That is what makes the table safe to aggregate, which
    is the only thing that makes it worth keeping.
    """

    id: int | None = None
    finding_id: str
    attempt_index: int

    # The vendor change. Public data; no privacy constraint applies to this block.
    vendor_id: str
    from_version: str
    to_version: str
    change_kind: str
    change_severity: Severity
    operation_id: str | None = None
    path_ptr: str | None = None

    # The call site, as shape only.
    language: str
    sdk_version: str | None = None
    symbol_shape: str
    arg_arity: int
    arg_key_hashes: list[str] = Field(default_factory=list)
    response_fields_touched_count: int

    # What was attempted.
    strategy: PatchStrategy
    tier: int
    edit_script: dict[str, Any] | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_input_tokens: int | None = None
    wall_ms: int

    # What happened.
    static_verify_passed: bool | None = None
    static_verify_error_class: str | None = None
    ci_result: str | None = None
    terminal_status: str | None = None
    abandon_reason: str | None = None

    # Outcome, arriving days later by webhook.
    pr_number: int | None = None
    pr_merged: bool | None = None
    pr_merged_at: datetime | None = None
    human_edits_before_merge: int | None = None

    created_at: datetime = Field(default_factory=_now)

    @classmethod
    def from_attempt(
        cls,
        finding_id: str,
        attempt_index: int,
        site: "CallSite",
        change: "VendorChange",
        patch: "Patch",
        tier: int,
        wall_ms: int,
        salt: str,
        language: str = "typescript",
        **outcome: Any,
    ) -> "MigrationOutcome":
        """Build a row from the objects an attempt already has.

        The reduction happens here rather than at the call sites that record outcomes, so there
        is one place where source could leak and it is the place that is tested.
        """
        from sync.core.corpus import hash_arg_keys, symbol_shape

        return cls(
            finding_id=finding_id,
            attempt_index=attempt_index,
            vendor_id=change.vendor_id,
            from_version=change.from_version,
            to_version=change.to_version,
            change_kind=change.kind,
            change_severity=change.severity,
            operation_id=change.operation_id,
            path_ptr=change.path_ptr,
            language=language,
            sdk_version=site.sdk_version,
            symbol_shape=symbol_shape(site.symbol),
            arg_arity=len(site.args_keys),
            arg_key_hashes=hash_arg_keys(site.args_keys, salt=salt),
            response_fields_touched_count=len(site.response_fields_read),
            strategy=patch.strategy,
            tier=tier,
            wall_ms=wall_ms,
            **outcome,
        )
