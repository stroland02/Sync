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
# Which rung of evidence produced a binding. 'static' is read out of source, 'resolved' is
# static plus a resolution step, 'observed' is watched traffic. 'unresolved' is the absence of a
# binding, which is a state worth naming: an uncorrelated observation that claimed a rung would
# be a fabricated binding, and one silently dropped would hide how good the correlation is.
BindingRung = Literal["static", "resolved", "observed", "unresolved"]


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
    # How many loops enclose this call, counting array callbacks that iterate. Zero is a call
    # made once per unit of work; one is a page of results becoming one vendor call each; two
    # is quadratic. A depth rather than a flag, because a boolean cannot tell N from N*M, and
    # that difference is the whole reason the signal is worth recording. Static evidence only:
    # a loop that never runs still counts here, and a runtime count belongs in `observed_call`.
    loop_depth: int = 0
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
    """One detector's claim about one call site.

    That is the grain, and it is the grain because `claim` is in the graph's identity for the
    row. An earlier version of this docstring said "a vendor change intersected with a call
    site", which described the first detector written and never the two that read telemetry
    instead -- those raise findings with no vendor change at all.
    """

    id: str | None = None
    detector: str
    claim: str = Field(min_length=1)
    """Which of this detector's claims this is -- `loop`, `shape-drift:/data/status`.

    Part of the graph's identity for a finding, beside the detector, the call site and the
    vendor change. So it has to be stable across runs and distinct per claim, and stable rules
    out anything derived from the rationale: an efficiency rationale carries a live call count,
    and keying on that would make two scans of an unchanged graph write two rows where they
    should converge on one.

    Required, with no default, and rejected when empty. A detector that left it blank would
    emit findings the key cannot tell apart, and `insert_finding` discards those without an
    error -- which is exactly how three detectors came to lose findings silently and how it
    went unnoticed. An optional field would leave that door open and differ only in that the
    next person through it had a chance to notice.

    The length constraint is here rather than left to a reviewer because omitting the field and
    writing `claim=""` to satisfy a type checker produce the identical collision, and only the
    first is caught by making it required. This is the plugin boundary: a third-party detector
    is the caller, so this is validation at an edge rather than mistrust of internal code.

    A bounded axis the detector iterates belongs here, because each value is a separate claim a
    reviewer acts on: a response field path, a host. An unbounded one does not. A trace id is
    evidence for a claim rather than a claim, and putting it here would put a row in front of a
    reviewer for every request the customer served.
    """
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
    # Which decision-table row assigned that tier. `tier` says what ran; this says what said
    # it should, and routing accuracy is defined over the difference. `"unrouted"` is a value
    # rather than a null because the table having no jurisdiction is a fact about the finding,
    # and a null has to stay available to mean the column was never written -- the attempts
    # that predate it, and any write that loses it. Conflating those makes the column unable
    # to answer the one question it exists for.
    #
    # Required rather than defaulted, for the reason `Finding.claim` is: a default is what a
    # writer silently falls back to after someone forgets to set it, and the fallback here
    # would be indistinguishable from a real "the table had no jurisdiction". `str | None`
    # rather than `str` because a row read back out of the database may legitimately carry the
    # NULL that predates this column -- required governs whether a caller must supply it, not
    # whether the value can be absent.
    routing_row: str | None
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


class ClientSpan(BaseModel):
    """One outbound HTTP request the customer's application made to a vendor.

    A *client* span. A server span describes somebody calling the customer, carries identical
    HTTP attributes, and is a different product. The distinction is not recoverable downstream,
    so it is made where spans are read and never re-litigated.

    `url` is the one field here holding customer data -- a path carries resource identifiers, a
    query string carries parameters. It exists for the length of an ingest call and reaches no
    column: `ObservedCall.from_spans` reduces it to a salted digest, and the operation's own
    published template replaces it.

    It lives in core rather than in `sync.telemetry` because it is the contract between an
    ingest and the reduction, and OTLP is not the only thing that could ever produce one.
    """

    trace_id: str
    span_id: str
    http_method: str
    url: str
    server_address: str
    status_code: int | None = None
    resend_count: int = 0
    started_at: datetime

    @property
    def path(self) -> str:
        from urllib.parse import urlsplit

        return urlsplit(self.url).path


class ObservedCall(BaseModel):
    """What one unit of work did with one vendor operation.

    The grain is one row per `(repo_id, vendor_id, operation_id, server_address, http_method,
    trace_id)`. A row is not a call: `spans` holds one entry per span and `call_count` is its
    size, so three calls to one operation inside one request are one row of three. A query
    counting vendor calls by counting rows undercounts exactly where the efficiency detector is
    looking.

    The trace is in the grain because three of the four efficiency findings -- a call in a loop,
    a page walked at the default size, a repeated call with no cache -- ask how many times one
    unit of work called something. A windowed rollup cannot distinguish one request making two
    hundred calls from two hundred requests making one, and that distinction is the finding.

    Every aggregate is derived from `spans` rather than stored beside it. That is what makes
    ingest idempotent under at-least-once delivery: folding a span already in the map is a
    no-op, where a stored counter would have to be told not to add twice and would be wrong the
    first time somebody forgot.

    Nothing here identifies a customer. The request URL never survives: a correlated call keeps
    the vendor's published template, and every call keeps a salted digest of the URL whose only
    purpose is to say whether two calls went to the same place.
    """

    id: int | None = None
    repo_id: str
    vendor_id: str
    # Empty when nothing correlated the request, which pairs with binding_rung 'unresolved'.
    operation_id: str = ""
    binding_rung: BindingRung
    server_address: str
    http_method: str
    trace_id: str
    # The vendor's published path template. Never the request path.
    url_template: str = ""
    # span_id -> {"target": <salted digest>, "status": <int|null>, "resend": <int>}
    spans: dict[str, dict[str, Any]] = Field(default_factory=dict)
    first_seen: datetime = Field(default_factory=_now)
    last_seen: datetime = Field(default_factory=_now)

    @property
    def call_count(self) -> int:
        return len(self.spans)

    @property
    def distinct_targets(self) -> int:
        """How many different URLs the calls in this row went to.

        Cardinality of the salted digests. Distinguishes fetching three different charges, which
        is work, from fetching one charge three times, which is a missing cache -- without the
        row holding anything that says which charge.
        """
        return len({facts.get("target") for facts in self.spans.values()})

    @property
    def repeated_calls(self) -> int:
        """Calls that went somewhere an earlier call in the same unit of work already went."""
        return self.call_count - self.distinct_targets

    @property
    def max_resend_count(self) -> int:
        """The worst retry count on any one call here.

        The maximum rather than the sum: each span already counts its own resends, so adding
        them across spans answers no question anyone asks.
        """
        return max((facts.get("resend") or 0 for facts in self.spans.values()), default=0)

    @property
    def error_count(self) -> int:
        """Calls that came back 4xx or 5xx.

        A span with no status is not counted as an error and not counted as a success. It is a
        request that got no response, which is a real outcome and a separate question.
        """
        return sum(
            1 for facts in self.spans.values()
            if isinstance(facts.get("status"), int) and facts["status"] >= 400
        )

    @classmethod
    def from_spans(
        cls,
        repo_id: str,
        vendor_id: str,
        operation_id: str,
        url_template: str,
        spans: list["ClientSpan"],
        salt: str,
        binding_rung: BindingRung | None = None,
    ) -> "ObservedCall":
        """Reduce a trace's spans against one operation to what is safe to keep.

        The reduction happens here rather than at each ingest that observes traffic, so there is
        one place where a URL could leak into a column and it is the place that is tested.

        The digest covers the whole URL with query parameters sorted, not just the path. A
        different `limit` is a different call and the page-size finding is exactly that
        difference; sorting the parameters keeps two spellings of one request from looking like
        two calls. Salted per deployment because the URL space is enumerable -- an unsalted
        digest of `/v1/charges` is `/v1/charges` to anyone willing to hash a wordlist.

        `binding_rung` defaults to what `operation_id` implies, so the two cannot disagree.
        """
        from sync.core.corpus import hash_request_target

        first = min(spans, key=lambda s: s.started_at)
        last = max(spans, key=lambda s: s.started_at)

        return cls(
            repo_id=repo_id,
            vendor_id=vendor_id,
            operation_id=operation_id,
            binding_rung=binding_rung or ("observed" if operation_id else "unresolved"),
            server_address=first.server_address,
            http_method=first.http_method,
            trace_id=first.trace_id,
            url_template=url_template,
            spans={
                span.span_id: {
                    "target": hash_request_target(span.url, salt=salt),
                    "status": span.status_code,
                    "resend": span.resend_count,
                }
                for span in spans
            },
            first_seen=first.started_at,
            last_seen=last.started_at,
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
