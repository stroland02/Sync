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
JsonType = Literal["string", "number", "boolean", "object", "array", "null"]
ObservationSource = Literal["error-payload", "replay", "interceptor"]


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
    even when the code is not included.

    "Safe to aggregate" is not the same as "comparable in every column", and an earlier version
    of this docstring ran the two together. The shape columns carry no salt and mean the same
    thing for every customer; `arg_key_hashes` is salted per deployment and groups into one
    bucket per customer if aggregated across them. `sync.core.corpus` says which is which, and
    it is worth reading before writing a query against this table.
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


def _json_type_of(value: Any) -> JsonType:
    """The JSON type of a decoded value.

    `bool` is checked before `int` because it is a subclass of one in Python. Ordered the other
    way, every boolean is recorded as a number and the baseline disagrees with the specification
    about a type that never changed.

    An input JSON cannot produce is a fault at the observation boundary rather than a shape, so
    it raises -- and the message names the type only. Putting the value in an exception string
    is how discarded data reaches a log file.
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    raise ValueError(f"{type(value).__name__} is not a JSON type")


class ObservedShape(BaseModel):
    """What one field of one operation's response was actually seen to be.

    The grain is one row per `(vendor_id, operation_id, field_path, json_type, source)` tuple.
    `sample_count` is a counter on that row, not a row multiplier: observing a shape a second
    time increments it, because a table that appended instead would make every presence rate a
    function of how often the ingest ran rather than of what the vendor sent.

    Values are never recorded, only shape -- paths, types, nullability, counts. The one
    exception is an enum member the vendor's *published specification* names, which is public
    data. A string absent from the specification is a customer's data and is discarded at this
    boundary, which is the last point where it exists at all.

    It cannot be backfilled. Every response seen before this table existed is a baseline sample
    permanently lost.
    """

    id: int | None = None
    vendor_id: str
    operation_id: str
    # A JSON Pointer into the response body -- '/data/status'. Not the URL path: that is
    # `vendor_change.path_ptr`, which addresses the operation, not a field inside its response.
    field_path: str
    json_type: JsonType
    nullable_seen: bool = False
    # Only members the published specification names, and only those actually observed. The
    # column says what this operation has been seen to send, so it may not be invented from the
    # specification alone.
    spec_enum_values: list[str] = Field(default_factory=list)
    source: ObservationSource
    sample_count: int = 1
    first_seen: datetime = Field(default_factory=_now)
    last_seen: datetime = Field(default_factory=_now)

    @classmethod
    def from_observation(
        cls,
        vendor_id: str,
        operation_id: str,
        field_path: str,
        value: Any,
        source: ObservationSource,
        spec_enum_values: list[str] | None = None,
        sample_count: int = 1,
    ) -> "ObservedShape":
        """Reduce one observed field to what is safe to keep.

        The reduction happens here rather than at each caller that observes traffic, so there is
        one place where a value could leak and it is the place that is tested.

        `spec_enum_values` is the published enum for this field, supplied by the caller that
        holds the specification. Membership in it is the whole retention rule: not "short
        strings", not "strings that look like enums" -- published, or discarded. A non-string is
        never retained even when it matches a published member, because an amount of 4999 is an
        amount whether or not some specification's example also says 4999.
        """
        published = spec_enum_values or []
        retained = [value] if isinstance(value, str) and value in published else []

        return cls(
            vendor_id=vendor_id,
            operation_id=operation_id,
            field_path=field_path,
            json_type=_json_type_of(value),
            nullable_seen=value is None,
            spec_enum_values=retained,
            source=source,
            sample_count=sample_count,
        )
