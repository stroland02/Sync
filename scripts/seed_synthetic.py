"""A synthetic corpus that exercises every vocabulary the console renders.

`seed_console.py` writes a small honest fixture -- six call sites, two vendors -- and is owned by
another session. This is the development corpus beside it: wide rather than realistic, built so a
screen can be checked against every state it claims to handle without waiting for a real
repository to happen to contain one.

**What it covers, and why each matters to a screen**

- **Every protocol kind the taxonomy names.** `web/src/features/vendors/api-service-taxonomy.ts`
  declares twelve -- `rest-sdk` through `baas` -- and each is written in *its own shape* rather
  than under its own name: a webhook call site is a handler reading event fields, a queue's is a
  producer and a consumer, a GraphQL operation names the fields it selects, a gRPC one names a
  fully-qualified method. A corpus where twelve kinds all looked like a REST call would let a
  screen that renders only REST calls look finished.
- **A vendor is not a protocol.** `github` appears at three kinds, `stripe`, `twilio` and
  `supabase` at two. Any screen keyed on vendor alone has to survive one vendor holding several
  wire shapes, and no corpus with one kind per vendor can show that.
- **A spread of vendors a developer recognises**, using the ids `generated-vendors.yaml` already
  declares where one exists -- `stripe`, `openai`, `anthropic`, `mistral`, `groq`, `twilio`,
  `cloudflare`, `browserbase` -- and plain lowercase ids where none does. Vendors with graph rows
  and no registered adapter land in the catalogue's `unregistered` tier, which is a real state
  with its own badge and nothing else in the fixtures reaches it.
- **Every binding rung** (`static`, `resolved`, `observed`, `unresolved`) and the finding-only
  `unattributed`. The rung column, the rung mix chart and the health strip all branch on these.
- **Every severity** in `SEVERITY_ORDER`, including the ones a real corpus rarely holds, so the
  severity tabs are never checked against a set where two of five are absent.
- **Every `ChangeSource`**, because what produced a change is a property of the protocol rather
  than of the vendor: an OpenAPI surface is diffed, a model provider publishes a deprecation
  table, a schema registry ships with an SDK release, a GraphQL schema moves in a changelog.
- **One detector per protocol kind**, so the detector accountability screen has more than one card
  and each card's rung mix differs.
- **All three binding statuses.** `at_risk` needs an open finding, `clean` needs a vendor asked
  successfully and no open finding, `unchecked` needs neither -- so the corpus carries call sites
  no finding names and intake attempts that succeeded, declined and failed. Every call site
  carrying a finding would leave two of the three states undrawable.
- **Telemetry present, telemetry absent, and errors without telemetry.** These are three different
  nothings and the console is required to say which -- a corpus with only the first cannot prove it.
- **The awkward shapes**: a path long enough to wrap, a unicode path, a call site two loops deep, a
  call with no SDK behind it, an observation on a transport with no HTTP method, an uncorrelated
  observation, an operation nothing binds, a vendor with intake and no call site anywhere. Every
  one of these has broken a screen at some point.

Three removal keys, because three of these tables have no repo id: a repo id prefixed `synthetic`,
a detector prefixed `synthetic-`, `raw->>'synthetic'` on a vendor change and `source` on an intake
attempt. `--remove` takes exactly what `write` put in and leaves both the real graph and
`seed-console`'s fixture untouched. Writing twice converges on one corpus rather than two.

    uv run python scripts/seed_synthetic.py            # write it
    uv run python scripts/seed_synthetic.py --remove   # take it away
    uv run python scripts/seed_synthetic.py --scale 500  # a repository big enough to page
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sync.core import CallSite, Finding, ObservedCall, ObservedErrorWindow, VendorChange
from sync.graph.store import DEFAULT_DSN, GraphStore
from sync.signals.intake_attempt import IntakeAttempt

#: Every repository this writes. The prefix is the removal key.
PREFIX = "synthetic"

WIDE = f"{PREFIX}/every-state"
EMPTY = f"{PREFIX}/never-indexed"
SCALE = f"{PREFIX}/at-scale"

NOW = datetime.now(timezone.utc)

#: `intake_attempt`'s natural key is the vendor and the instant, so an attempt stamped `NOW` writes
#: a fresh row on every run where every other write in this script converges on the one it already
#: made. Floored to the hour: re-running inside one converges, and a later run records a vendor
#: genuinely asked again.
ASKED_AT = NOW.replace(minute=0, second=0, microsecond=0)

RUNGS = ["static", "resolved", "observed", "unresolved"]
SEVERITIES = ["breaking", "warning", "deprecation", "addition", "info"]

#: `open` three times, then the two closed states. A corpus of only `open` cannot show that a
#: screen renders the closed ones.
STATUSES = ("open", "open", "open", "patched", "abandoned")


@dataclass(frozen=True)
class Shape:
    """One call site, written the way a service of its kind is actually called."""

    path: str
    symbol: str
    operation_id: str
    args_keys: tuple[str, ...]
    #: What the call site reads back. Never empty: a change's pointer is built from one of these,
    #: so a shape reading nothing would collapse five vendor changes onto one id.
    reads: tuple[str, ...]
    snippet: str | None = None
    loop_depth: int = 0


@dataclass(frozen=True)
class Surface:
    """One vendor at one kind of the taxonomy."""

    kind: str
    vendor: str
    #: The vendor's own API product. `None` is *not grouped yet* and never "outside every service".
    service: str | None
    #: Empty where there is genuinely no SDK -- raw HTTP against an OpenAPI document. The console
    #: renders that through its absence marker, which is the honest reading and a path worth
    #: exercising from something other than a forgotten field.
    sdk_version: str
    from_version: str
    to_version: str
    ptr_root: str
    #: An operation of this vendor the codebase does not call, so intake holds a change nothing
    #: binds. Most real changes reach nothing, and a corpus where every change had a finding would
    #: make the binding step look free.
    unbound_operation: str
    shapes: tuple[Shape, ...]


#: What a diff of each protocol can report, one kind per severity in `SEVERITIES` order. This is a
#: property of the wire shape rather than of the vendor -- an OpenAPI diff cannot report a retired
#: model and a schema registry cannot report a deprecated endpoint.
CHANGE_KINDS: dict[str, tuple[str, ...]] = {
    "rest-sdk": (
        "response-body-property-removed",
        "optional-response-property-removed",
        "endpoint-deprecated",
        "response-body-property-added",
        "endpoint-summary-changed",
    ),
    "rest-openapi": (
        "api-path-removed",
        "response-property-type-changed",
        "api-deprecated",
        "new-optional-request-parameter",
        "api-operation-id-changed",
    ),
    "llm": (
        "model-retired",
        "model-alias-repointed",
        "model-deprecated",
        "model-published",
        "model-context-window-changed",
    ),
    "mcp": (
        "tool-removed",
        "tool-input-property-became-required",
        "tool-superseded",
        "tool-added",
        "tool-description-changed",
    ),
    "graphql": (
        "field-removed",
        "field-type-changed",
        "field-deprecated",
        "field-added",
        "field-description-changed",
    ),
    "grpc": (
        "message-field-removed",
        "field-cardinality-changed",
        "rpc-deprecated",
        "rpc-added",
        "proto-comment-changed",
    ),
    "webhooks": (
        "event-payload-property-removed",
        "event-payload-property-nullable",
        "event-type-deprecated",
        "event-type-added",
        "delivery-header-added",
    ),
    "streaming": (
        "channel-message-property-removed",
        "message-property-type-changed",
        "channel-deprecated",
        "channel-message-property-added",
        "heartbeat-interval-changed",
    ),
    "queues": (
        "subject-incompatible-field-removed",
        "field-default-removed",
        "topic-deprecated",
        "optional-field-added",
        "compatibility-mode-changed",
    ),
    "soap": (
        "wsdl-operation-removed",
        "element-min-occurs-raised",
        "wsdl-version-sunset",
        "wsdl-operation-added",
        "wsdl-documentation-changed",
    ),
    "auth": (
        "claim-removed",
        "claim-value-format-changed",
        "scope-deprecated",
        "claim-added",
        "discovery-metadata-added",
    ),
    "baas": (
        "column-dropped",
        "column-became-not-null",
        "table-deprecated",
        "column-added",
        "row-level-security-policy-annotated",
    ),
}

#: Which pipeline saw the change. All four members of `ChangeSource` are used, each where it is the
#: one that could genuinely have produced the row.
CHANGE_SOURCES: dict[str, str] = {
    "rest-sdk": "oasdiff",
    "rest-openapi": "oasdiff",
    "llm": "vendor-deprecation-table",
    "mcp": "sdk-release",
    "graphql": "changelog",
    "grpc": "sdk-release",
    "webhooks": "changelog",
    "streaming": "changelog",
    "queues": "changelog",
    "soap": "changelog",
    "auth": "vendor-deprecation-table",
    "baas": "changelog",
}

#: The shapes that have broken a screen before, each attached to the surface it plausibly belongs
#: to. Each is a real defect class, not decoration: a path long enough to wrap a column, a
#: non-latin path, a call two loops deep, a path short enough to collapse a column's minimum width.
AWKWARD: dict[tuple[str, str], Shape] = {
    ("webhooks", "stripe"): Shape(
        path="app/api/billing/subscriptions/webhooks/handlers/payment_intent_succeeded/route.ts",
        symbol="handleSubscriptionPaymentIntentSucceededWebhookDelivery",
        operation_id="event:payment_intent.succeeded",
        args_keys=("payload", "signature", "endpointSecret"),
        reads=("data.object.id", "data.object.latest_charge", "livemode"),
    ),
    ("rest-sdk", "twilio"): Shape(
        path="app/api/日本語/route.ts",
        symbol="twilio.messages.createLocalised",
        operation_id="CreateMessage",
        args_keys=("to", "from", "body"),
        reads=("sid", "status"),
    ),
    ("rest-openapi", "sendgrid"): Shape(
        path="lib/batch/sweep.ts",
        symbol="fetch:POST /v3/mail/batch",
        operation_id="POST /v3/mail/batch",
        args_keys=("personalizations", "from", "template_id"),
        reads=("batch_id",),
        loop_depth=2,
    ),
    ("llm", "openai"): Shape(
        path="app/api/a/route.ts",
        symbol="openai.chat.completions.createTerse",
        operation_id="createChatCompletion",
        args_keys=("model", "messages"),
        reads=("choices",),
    ),
}

#: Call sites no detector has raised anything about, keyed like `AWKWARD` and deliberately kept
#: out of the finding loop. `GraphStore.BINDING_STATUSES` has three members and every call site
#: carrying an open finding reads `at_risk`, so without these the console's other two states --
#: `clean` and `unchecked` -- have nothing in the corpus to draw.
QUIET: dict[tuple[str, str], Shape] = {
    ("rest-sdk", "stripe"): Shape(
        path="lib/billing/balance.ts",
        symbol="stripe.balanceTransactions.list",
        operation_id="GetBalanceTransactions",
        args_keys=("limit", "type", "created"),
        reads=("data", "has_more"),
    ),
    ("baas", "supabase"): Shape(
        path="web/src/data/feature-flags.ts",
        symbol="supabase.from(feature_flags).select",
        operation_id="select:public.feature_flags",
        args_keys=("table", "columns"),
        reads=("key", "enabled"),
    ),
    ("streaming", "slack"): Shape(
        path="services/chatops/app-mention.ts",
        symbol="socketModeClient.on(app_mention)",
        operation_id="channel:app_mention",
        args_keys=("event", "ack"),
        reads=("event.user", "event.text"),
    ),
    ("soap", "fedex"): Shape(
        path="services/shipping/fedex_addresses.py",
        symbol="AddressValidationServiceClient.addressValidation",
        operation_id="addressValidation",
        args_keys=("AddressesToValidate",),
        reads=("AddressResults.EffectiveAddress.PostalCode",),
    ),
}

#: What this deployment's adapters last answered when asked. Both closed vocabularies the Settings
#: adapters screen renders are here -- the three outcomes, and a reason code from
#: `CLOSED_REASON_CODES` on the two that decline or fail.
#:
#: It is also what separates `clean` from `unchecked`: a call site with no open finding reads
#: `clean` only where its vendor has a successful attempt on record, and `unchecked` otherwise.
#: Those are two different claims and a corpus that recorded no attempt could only make one.
INTAKE: tuple[tuple[str, str, str | None, int], ...] = (
    ("stripe", "success", None, 6),
    ("supabase", "success", None, 6),
    ("openai", "success", None, 6),
    ("slack", "declined", "up_to_date", 0),
    ("fedex", "failed", "spec_unreachable", 0),
)

#: The removal key for the rows above. `intake_attempt` is keyed by vendor and carries no repo id,
#: so deleting by vendor would take a real attempt for the same vendor with it.
INTAKE_SOURCE = "seed_synthetic"

SURFACES: tuple[Surface, ...] = (
    # --- rest-sdk: HTTPS + JSON through the vendor's published SDK ---------------------------
    Surface(
        kind="rest-sdk",
        vendor="stripe",
        service="Payment Intents",
        sdk_version="18.4.0",
        from_version="2026-06-30.basil",
        to_version="2026-08-27.acacia",
        ptr_root="/paths/~1v1~1payment_intents/post/responses/200/schema/properties",
        unbound_operation="GetDisputes",
        shapes=(
            Shape(
                path="app/api/checkout/route.ts",
                symbol="stripe.paymentIntents.create",
                operation_id="PostPaymentIntents",
                args_keys=("amount", "currency", "customer", "automatic_payment_methods"),
                reads=("id", "status", "client_secret"),
                snippet=(
                    "const intent = await stripe.paymentIntents.create({\n"
                    '  amount, currency: "eur", customer,\n'
                    "  automatic_payment_methods: { enabled: true },\n"
                    "})"
                ),
            ),
            Shape(
                path="lib/billing/invoices.ts",
                symbol="stripe.invoices.list",
                operation_id="GetInvoices",
                args_keys=("customer", "limit", "starting_after"),
                reads=("data", "has_more"),
                loop_depth=1,
            ),
        ),
    ),
    Surface(
        kind="rest-sdk",
        vendor="twilio",
        service="Programmable Messaging",
        sdk_version="5.4.1",
        from_version="2010-04-01.r18",
        to_version="2010-04-01.r22",
        ptr_root="/paths/~1Accounts~1{Sid}~1Messages.json/post/responses/201/schema/properties",
        unbound_operation="CreateVerificationCheck",
        shapes=(
            Shape(
                path="services/notify/sms.ts",
                symbol="twilio.messages.create",
                operation_id="CreateMessage",
                args_keys=("to", "from", "body", "statusCallback"),
                reads=("sid", "status", "error_code"),
                snippet=(
                    "const message = await twilio.messages.create({\n"
                    "  to, from: process.env.TWILIO_NUMBER, body,\n"
                    "  statusCallback: `${origin}/api/webhooks/twilio`,\n"
                    "})"
                ),
            ),
            Shape(
                path="services/notify/lookup.ts",
                symbol="twilio.lookups.v2.phoneNumbers.fetch",
                operation_id="FetchPhoneNumber",
                args_keys=("phoneNumber", "fields"),
                reads=("valid", "line_type_intelligence"),
            ),
        ),
    ),
    Surface(
        kind="rest-sdk",
        vendor="github",
        service="Pull Requests",
        sdk_version="22.0.0",
        from_version="2022-11-28",
        to_version="2026-08-01",
        ptr_root="/paths/~1repos~1{owner}~1{repo}~1pulls/post/responses/201/schema/properties",
        unbound_operation="ReposCreateDeployment",
        shapes=(
            Shape(
                path="tools/release/open_pull_request.py",
                symbol="github.rest.pulls.create",
                operation_id="PullsCreate",
                args_keys=("owner", "repo", "head", "base", "title"),
                reads=("number", "html_url", "mergeable_state"),
                snippet=(
                    "pr = github.rest.pulls.create(\n"
                    '    owner=owner, repo=repo, head=branch, base="main", title=title\n'
                    ")"
                ),
            ),
            Shape(
                path="tools/release/list_checks.py",
                symbol="github.rest.checks.list_for_ref",
                operation_id="ChecksListForRef",
                args_keys=("owner", "repo", "ref", "per_page"),
                reads=("check_runs", "total_count"),
                loop_depth=1,
            ),
        ),
    ),
    # --- rest-openapi: raw HTTP against an OpenAPI-described surface, no SDK -----------------
    Surface(
        kind="rest-openapi",
        vendor="sendgrid",
        service="Mail Send v3",
        sdk_version="",
        from_version="3.0.0",
        to_version="3.1.0",
        ptr_root="/paths/~1v3~1mail~1send/post/requestBody/schema/properties",
        unbound_operation="POST /v3/marketing/contacts",
        shapes=(
            Shape(
                path="lib/http/sendgrid.ts",
                symbol="fetch:POST /v3/mail/send",
                operation_id="POST /v3/mail/send",
                args_keys=("personalizations", "from", "subject", "content"),
                reads=("x-message-id", "status"),
                snippet=(
                    'const res = await fetch("https://api.sendgrid.com/v3/mail/send", {\n'
                    '  method: "POST",\n'
                    "  headers: { authorization: `Bearer ${key}` },\n"
                    "  body: JSON.stringify({ personalizations, from, subject, content }),\n"
                    "})"
                ),
            ),
        ),
    ),
    Surface(
        kind="rest-openapi",
        vendor="fastly",
        service="Purge",
        sdk_version="",
        from_version="2026-04-11",
        to_version="2026-08-14",
        ptr_root="/paths/~1service~1{service_id}~1purge~1{key}/post/responses/200/schema",
        unbound_operation="GET /service/{service_id}/version",
        shapes=(
            Shape(
                path="lib/http/fastly.ts",
                symbol="fetch:POST /service/{service_id}/purge/{key}",
                operation_id="POST /service/{service_id}/purge/{key}",
                args_keys=("service_id", "key", "fastly-soft-purge"),
                reads=("status", "id"),
                snippet=(
                    "await fetch(`https://api.fastly.com/service/${serviceId}/purge/${key}`, {\n"
                    '  method: "POST",\n'
                    '  headers: { "fastly-key": apiKey, "fastly-soft-purge": "1" },\n'
                    "})"
                ),
            ),
            Shape(
                path="lib/http/fastly-stats.ts",
                symbol="fetch:GET /stats/service/{service_id}",
                operation_id="GET /stats/service/{service_id}",
                args_keys=("service_id", "from", "to", "by"),
                reads=("data", "meta.to"),
                loop_depth=1,
            ),
        ),
    ),
    Surface(
        kind="rest-openapi",
        vendor="cloudflare",
        service="DNS Records",
        sdk_version="",
        from_version="4.0.0",
        to_version="4.3.0",
        ptr_root="/paths/~1zones~1{zone_id}~1dns_records/post/responses/200/schema/result",
        unbound_operation="GET /zones/{zone_id}/settings",
        shapes=(
            Shape(
                path="infra/dns/records.py",
                symbol="httpx:POST /zones/{zone_id}/dns_records",
                operation_id="POST /zones/{zone_id}/dns_records",
                args_keys=("zone_id", "type", "name", "content", "proxied"),
                reads=("result.id", "result.proxiable", "success"),
                snippet=(
                    "response = httpx.post(\n"
                    '    f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records",\n'
                    '    json={"type": "CNAME", "name": name, "content": target},\n'
                    ")"
                ),
            ),
        ),
    ),
    # --- llm: the model identifier is the versioned surface ----------------------------------
    Surface(
        kind="llm",
        vendor="openai",
        service="Chat Completions",
        sdk_version="1.51.0",
        from_version="v3.0.0",
        to_version="v3.3.1",
        ptr_root="/models",
        unbound_operation="createModeration",
        shapes=(
            Shape(
                path="services/agent/plan.py",
                symbol="openai.chat.completions.create",
                operation_id="createChatCompletion",
                args_keys=("model", "messages", "temperature", "response_format"),
                reads=("choices.0.message.content", "usage.total_tokens"),
                snippet=(
                    "completion = openai.chat.completions.create(\n"
                    '    model="gpt-4o-2024-08-06",\n'
                    "    messages=messages,\n"
                    '    response_format={"type": "json_schema"},\n'
                    ")"
                ),
            ),
            Shape(
                path="services/search/embed.py",
                symbol="openai.embeddings.create",
                operation_id="createEmbedding",
                args_keys=("model", "input", "dimensions"),
                reads=("data.0.embedding", "usage.prompt_tokens"),
                loop_depth=1,
            ),
        ),
    ),
    Surface(
        kind="llm",
        vendor="anthropic",
        service="Messages",
        sdk_version="0.39.0",
        from_version="2023-06-01",
        to_version="2026-08-01",
        ptr_root="/models",
        unbound_operation="countMessageTokens",
        shapes=(
            Shape(
                path="services/agent/review.py",
                symbol="anthropic.messages.create",
                operation_id="createMessage",
                args_keys=("model", "max_tokens", "system", "messages", "tools"),
                reads=("content.0.text", "stop_reason", "usage.output_tokens"),
                snippet=(
                    "message = anthropic.messages.create(\n"
                    '    model="claude-sonnet-4-5",\n'
                    "    max_tokens=4096,\n"
                    "    tools=REVIEW_TOOLS,\n"
                    '    messages=[{"role": "user", "content": diff}],\n'
                    ")"
                ),
            ),
            Shape(
                path="services/agent/summarise.ts",
                symbol="anthropic.messages.stream",
                operation_id="createMessageStreaming",
                args_keys=("model", "max_tokens", "messages"),
                reads=("delta.text", "message.usage.input_tokens"),
                loop_depth=1,
            ),
        ),
    ),
    Surface(
        kind="llm",
        vendor="mistral",
        service="Chat",
        sdk_version="1.2.3",
        from_version="0.0.2",
        to_version="0.1.0",
        ptr_root="/models",
        unbound_operation="createFimCompletion",
        shapes=(
            Shape(
                path="services/classify/route.py",
                symbol="mistral.chat.complete",
                operation_id="chatCompletionV1",
                args_keys=("model", "messages", "safe_prompt"),
                reads=("choices.0.message.content", "usage.completion_tokens"),
                snippet=(
                    "result = mistral.chat.complete(\n"
                    '    model="mistral-small-latest", messages=messages, safe_prompt=True\n'
                    ")"
                ),
            ),
        ),
    ),
    Surface(
        kind="llm",
        vendor="groq",
        service="Chat Completions",
        sdk_version="0.11.0",
        from_version="0.4.0",
        to_version="0.9.0",
        ptr_root="/models",
        unbound_operation="createTranscription",
        shapes=(
            Shape(
                path="services/classify/fast_path.py",
                symbol="groq.chat.completions.create",
                operation_id="createChatCompletion",
                args_keys=("model", "messages", "max_tokens"),
                reads=("choices.0.message.content", "x_groq.usage.queue_time"),
                snippet=(
                    "completion = groq.chat.completions.create(\n"
                    '    model="llama-3.3-70b-versatile", messages=messages, max_tokens=512\n'
                    ")"
                ),
            ),
        ),
    ),
    # --- mcp: tool schemas over stdio or HTTP -------------------------------------------------
    Surface(
        kind="mcp",
        vendor="browserbase",
        service="Browserbase MCP",
        sdk_version="1.4.0",
        from_version="1.2.0",
        to_version="1.4.0",
        ptr_root="/tools",
        unbound_operation="tools/call:browserbase_screenshot",
        shapes=(
            Shape(
                path="agents/tools/browser.ts",
                symbol="mcpClient.callTool(browserbase_navigate)",
                operation_id="tools/call:browserbase_navigate",
                args_keys=("name", "arguments.url", "arguments.waitUntil"),
                reads=("content.0.text", "isError"),
                snippet=(
                    "const result = await mcpClient.callTool({\n"
                    '  name: "browserbase_navigate",\n'
                    '  arguments: { url, waitUntil: "networkidle" },\n'
                    "})"
                ),
            ),
            Shape(
                path="agents/tools/registry.ts",
                symbol="mcpClient.listTools",
                operation_id="tools/list",
                args_keys=("cursor",),
                reads=("tools", "nextCursor"),
                loop_depth=1,
            ),
        ),
    ),
    Surface(
        kind="mcp",
        vendor="sentry",
        service="Sentry MCP",
        sdk_version="0.8.0",
        from_version="0.6.0",
        to_version="0.8.0",
        ptr_root="/tools",
        unbound_operation="tools/call:update_issue",
        shapes=(
            Shape(
                path="agents/tools/incidents.ts",
                symbol="mcpClient.callTool(find_errors)",
                operation_id="tools/call:find_errors",
                args_keys=("name", "arguments.organizationSlug", "arguments.query"),
                reads=("content.0.text", "structuredContent.issues"),
                snippet=(
                    "const errors = await mcpClient.callTool({\n"
                    '  name: "find_errors",\n'
                    '  arguments: { organizationSlug, query: "is:unresolved" },\n'
                    "})"
                ),
            ),
        ),
    ),
    Surface(
        kind="mcp",
        vendor="notion",
        service="Notion MCP",
        sdk_version="1.9.0",
        from_version="1.7.0",
        to_version="1.9.0",
        ptr_root="/tools",
        unbound_operation="tools/call:create-comment",
        shapes=(
            Shape(
                path="agents/tools/notes.py",
                symbol="mcp_client.call_tool(search)",
                operation_id="tools/call:search",
                args_keys=("name", "arguments.query", "arguments.filter"),
                reads=("content", "structuredContent.results"),
                snippet=(
                    "result = await mcp_client.call_tool(\n"
                    '    "search", {"query": query, "filter": {"value": "page"}}\n'
                    ")"
                ),
            ),
        ),
    ),
    # --- graphql: the query names exactly the fields it reads ---------------------------------
    Surface(
        kind="graphql",
        vendor="github",
        service="GitHub GraphQL",
        sdk_version="7.1.0",
        from_version="2026-04-01",
        to_version="2026-10-01",
        ptr_root="/schema/Repository/fields",
        unbound_operation="query:OrganizationMembers",
        shapes=(
            Shape(
                path="tools/insights/queries/repository_issues.graphql",
                symbol="graphql(RepositoryIssues)",
                operation_id="query:RepositoryIssues",
                args_keys=("owner", "name", "first", "after"),
                reads=(
                    "repository.issues.nodes.title",
                    "repository.issues.nodes.author.login",
                    "repository.issues.pageInfo.endCursor",
                ),
                snippet=(
                    "query RepositoryIssues($owner: String!, $name: String!, $after: String) {\n"
                    "  repository(owner: $owner, name: $name) {\n"
                    "    issues(first: 100, after: $after) {\n"
                    "      nodes { title author { login } }\n"
                    "      pageInfo { endCursor hasNextPage }\n"
                    "    }\n"
                    "  }\n"
                    "}"
                ),
                loop_depth=1,
            ),
            Shape(
                path="tools/insights/queries/pull_request_reviews.graphql",
                symbol="graphql(PullRequestReviews)",
                operation_id="query:PullRequestReviews",
                args_keys=("owner", "name", "number"),
                reads=(
                    "repository.pullRequest.reviews.nodes.state",
                    "repository.pullRequest.reviewDecision",
                ),
            ),
        ),
    ),
    Surface(
        kind="graphql",
        vendor="shopify",
        service="Shopify Admin",
        sdk_version="2026-07",
        from_version="2026-04",
        to_version="2026-07",
        ptr_root="/schema/Order/fields",
        unbound_operation="mutation:fulfillmentCreateV2",
        shapes=(
            Shape(
                path="services/orders/queries/orders.graphql",
                symbol="shopify.graphql(OrdersPage)",
                operation_id="query:OrdersPage",
                args_keys=("first", "after", "query"),
                reads=(
                    "orders.nodes.totalPriceSet.shopMoney.amount",
                    "orders.nodes.displayFinancialStatus",
                    "orders.pageInfo.endCursor",
                ),
                snippet=(
                    "query OrdersPage($after: String) {\n"
                    '  orders(first: 50, after: $after, query: "financial_status:paid") {\n'
                    "    nodes { displayFinancialStatus totalPriceSet { shopMoney { amount } } }\n"
                    "    pageInfo { endCursor hasNextPage }\n"
                    "  }\n"
                    "}"
                ),
                loop_depth=1,
            ),
            Shape(
                path="services/orders/mutations/draft_order.graphql",
                symbol="shopify.graphql(DraftOrderCreate)",
                operation_id="mutation:draftOrderCreate",
                args_keys=("input.lineItems", "input.customerId"),
                reads=("draftOrderCreate.draftOrder.id", "draftOrderCreate.userErrors.message"),
            ),
        ),
    ),
    Surface(
        kind="graphql",
        vendor="contentful",
        # Nothing has mapped this vendor's operations onto its API products, which is *not grouped
        # yet* and must not render as a vendor selling one API.
        service=None,
        sdk_version="11.2.0",
        from_version="2026-02-19",
        to_version="2026-07-30",
        ptr_root="/schema/ArticleCollection/fields",
        unbound_operation="query:AssetCollection",
        shapes=(
            Shape(
                path="web/lib/cms/articles.graphql",
                symbol="contentful.graphql(ArticleCollection)",
                operation_id="query:ArticleCollection",
                args_keys=("limit", "skip", "preview"),
                reads=(
                    "articleCollection.items.slug",
                    "articleCollection.items.hero.url",
                    "articleCollection.total",
                ),
                snippet=(
                    "query ArticleCollection($limit: Int!, $skip: Int!) {\n"
                    "  articleCollection(limit: $limit, skip: $skip) {\n"
                    "    total\n"
                    "    items { slug hero { url } }\n"
                    "  }\n"
                    "}"
                ),
            ),
        ),
    ),
    # --- grpc: generated stubs against a .proto contract --------------------------------------
    Surface(
        kind="grpc",
        vendor="google-cloud",
        service="Cloud Spanner",
        sdk_version="3.49.0",
        from_version="v1.62.0",
        to_version="v1.68.0",
        ptr_root="/google.spanner.v1.ExecuteSqlRequest/fields",
        unbound_operation="google.spanner.v1.Spanner/BatchWrite",
        shapes=(
            Shape(
                path="services/reporting/spanner_client.py",
                symbol="spanner_v1.SpannerStub.ExecuteStreamingSql",
                operation_id="google.spanner.v1.Spanner/ExecuteStreamingSql",
                args_keys=("session", "sql", "params", "query_options"),
                reads=("metadata.row_type.fields", "values", "resume_token"),
                snippet=(
                    "for partial in stub.ExecuteStreamingSql(\n"
                    "    ExecuteSqlRequest(session=session, sql=SQL, params=params)\n"
                    "):\n"
                    "    rows.extend(partial.values)"
                ),
                loop_depth=1,
            ),
            Shape(
                path="services/reporting/pubsub_admin.py",
                symbol="pubsub_v1.PublisherStub.CreateTopic",
                operation_id="google.pubsub.v1.Publisher/CreateTopic",
                args_keys=("name", "labels", "message_retention_duration"),
                reads=("name", "message_storage_policy.allowed_persistence_regions"),
            ),
        ),
    ),
    Surface(
        kind="grpc",
        vendor="temporal",
        service="Workflow Service",
        sdk_version="1.9.0",
        from_version="v1.24.0",
        to_version="v1.27.0",
        ptr_root="/temporal.api.workflowservice.v1.StartWorkflowExecutionRequest/fields",
        unbound_operation="temporal.api.workflowservice.v1.WorkflowService/ResetWorkflowExecution",
        shapes=(
            Shape(
                path="services/orchestrator/client.go",
                symbol="workflowservice.WorkflowServiceClient.StartWorkflowExecution",
                operation_id=(
                    "temporal.api.workflowservice.v1.WorkflowService/StartWorkflowExecution"
                ),
                args_keys=("namespace", "workflow_id", "task_queue", "workflow_execution_timeout"),
                reads=("run_id", "started"),
                snippet=(
                    "resp, err := client.StartWorkflowExecution(ctx,\n"
                    "    &workflowservice.StartWorkflowExecutionRequest{\n"
                    "        Namespace: ns, WorkflowId: id, TaskQueue: queue,\n"
                    "    })"
                ),
            ),
        ),
    ),
    # --- webhooks: the vendor calls you, and the handler reads event fields -------------------
    Surface(
        kind="webhooks",
        vendor="stripe",
        service="Events",
        sdk_version="18.4.0",
        from_version="2026-06-30.basil",
        to_version="2026-08-27.acacia",
        ptr_root="/events/invoice.payment_failed/data/object",
        unbound_operation="event:charge.dispute.created",
        shapes=(
            Shape(
                path="app/api/webhooks/stripe/route.ts",
                symbol="handleStripeEvent",
                operation_id="event:invoice.payment_failed",
                args_keys=("payload", "signature", "endpointSecret"),
                reads=(
                    "type",
                    "data.object.customer",
                    "data.object.attempt_count",
                    "data.object.next_payment_attempt",
                ),
                snippet=(
                    "const event = stripe.webhooks.constructEvent(payload, signature, secret)\n"
                    'if (event.type === "invoice.payment_failed") {\n'
                    "  await dunning.schedule(event.data.object.customer,\n"
                    "    event.data.object.next_payment_attempt)\n"
                    "}"
                ),
            ),
        ),
    ),
    Surface(
        kind="webhooks",
        vendor="github",
        service="Webhook Events",
        sdk_version="7.1.0",
        from_version="2022-11-28",
        to_version="2026-08-01",
        ptr_root="/events/pull_request/payload",
        unbound_operation="event:workflow_run",
        shapes=(
            Shape(
                path="app/api/webhooks/github/route.ts",
                symbol="handleGithubPullRequestDelivery",
                operation_id="event:pull_request",
                args_keys=("x-github-event", "x-hub-signature-256", "x-github-delivery"),
                reads=(
                    "action",
                    "pull_request.merged",
                    "pull_request.head.sha",
                    "repository.full_name",
                ),
                snippet=(
                    'if (event === "pull_request" && body.action === "closed") {\n'
                    "  if (body.pull_request.merged) {\n"
                    "    await recordMerge(body.repository.full_name, body.pull_request.head.sha)\n"
                    "  }\n"
                    "}"
                ),
            ),
            Shape(
                path="app/api/webhooks/github/route.ts",
                symbol="handleGithubCheckSuiteDelivery",
                operation_id="event:check_suite",
                args_keys=("x-github-event", "x-hub-signature-256"),
                reads=("check_suite.conclusion", "check_suite.head_branch"),
            ),
        ),
    ),
    Surface(
        kind="webhooks",
        vendor="twilio",
        service="Status Callbacks",
        sdk_version="5.4.1",
        from_version="2010-04-01.r18",
        to_version="2010-04-01.r22",
        ptr_root="/callbacks/message-status/form",
        unbound_operation="callback:voice-status",
        shapes=(
            Shape(
                path="app/api/webhooks/twilio/route.ts",
                symbol="handleTwilioStatusCallback",
                operation_id="callback:message-status",
                args_keys=("x-twilio-signature",),
                reads=("MessageStatus", "MessageSid", "ErrorCode", "To"),
                snippet=(
                    "const form = await request.formData()\n"
                    'await deliveries.record(form.get("MessageSid"),\n'
                    '  form.get("MessageStatus"), form.get("ErrorCode"))'
                ),
            ),
        ),
    ),
    # --- streaming: WebSocket, SSE, or a long-poll cursor -------------------------------------
    Surface(
        kind="streaming",
        vendor="slack",
        service="Socket Mode",
        sdk_version="7.0.4",
        from_version="2026-03-11",
        to_version="2026-08-06",
        ptr_root="/events/message/payload",
        unbound_operation="channel:reaction_added",
        shapes=(
            Shape(
                path="services/chatops/socket.ts",
                symbol="socketModeClient.on(message)",
                operation_id="channel:message",
                args_keys=("event", "ack"),
                reads=("event.text", "event.channel", "event.thread_ts", "event.bot_id"),
                snippet=(
                    'socketModeClient.on("message", async ({ event, ack }) => {\n'
                    "  await ack()\n"
                    "  if (!event.bot_id) await route(event.channel, event.text)\n"
                    "})"
                ),
            ),
        ),
    ),
    Surface(
        kind="streaming",
        vendor="supabase",
        service="Realtime",
        sdk_version="2.45.0",
        from_version="2.39.0",
        to_version="2.45.0",
        ptr_root="/channels/postgres_changes/payload",
        unbound_operation="channel:broadcast",
        shapes=(
            Shape(
                path="web/src/live/orders-channel.ts",
                symbol="supabase.channel(public:orders).on(postgres_changes)",
                operation_id="channel:postgres_changes",
                args_keys=("event", "schema", "table", "filter"),
                reads=("eventType", "new.id", "new.status", "old.status"),
                snippet=(
                    'supabase.channel("public:orders")\n'
                    '  .on("postgres_changes",\n'
                    '      { event: "UPDATE", schema: "public", table: "orders" },\n'
                    "      ({ eventType, new: row }) => apply(eventType, row.id, row.status))\n"
                    "  .subscribe()"
                ),
            ),
        ),
    ),
    Surface(
        kind="streaming",
        vendor="pusher",
        service=None,
        sdk_version="8.4.0",
        from_version="7.6.0",
        to_version="8.4.0",
        ptr_root="/channels/presence-room/events",
        unbound_operation="channel:client-typing",
        shapes=(
            Shape(
                path="web/src/live/presence.ts",
                symbol="pusher.subscribe(presence-room).bind(member_added)",
                operation_id="channel:pusher:member_added",
                args_keys=("channelName", "eventName"),
                reads=("id", "info.name", "info.avatar_url"),
                snippet=(
                    "const channel = pusher.subscribe(`presence-room-${roomId}`)\n"
                    'channel.bind("pusher:member_added", (member) =>\n'
                    "  roster.add(member.id, member.info.name))"
                ),
            ),
        ),
    ),
    # --- queues: producers and consumers against a registry contract --------------------------
    Surface(
        kind="queues",
        vendor="kafka",
        service="orders.v2",
        sdk_version="2.2.4",
        from_version="orders.v2-value:6",
        to_version="orders.v2-value:7",
        ptr_root="/subjects/orders.v2-value/versions/7/fields",
        unbound_operation="consume:shipments.v1",
        shapes=(
            Shape(
                path="services/orders/producer.py",
                symbol="AvroProducer.produce(orders.v2)",
                operation_id="produce:orders.v2",
                args_keys=("topic", "key", "value", "headers"),
                reads=("partition", "offset"),
                snippet=(
                    "producer.produce(\n"
                    '    topic="orders.v2", key=order.id, value=ORDER_SCHEMA.encode(order),\n'
                    '    headers={"schema-version": "7"},\n'
                    ")"
                ),
            ),
            Shape(
                path="services/fulfilment/consumer.py",
                symbol="AvroConsumer.poll(orders.v2)",
                operation_id="consume:orders.v2",
                args_keys=("topics", "group_id", "auto_offset_reset"),
                reads=("order_id", "total_cents", "currency", "promised_at"),
                loop_depth=1,
            ),
        ),
    ),
    Surface(
        kind="queues",
        vendor="aws-sqs",
        service="invoices.fifo",
        sdk_version="3.658.0",
        from_version="2012-11-05.r4",
        to_version="2012-11-05.r6",
        ptr_root="/queues/invoices.fifo/message/body",
        unbound_operation="receive:invoices-dead-letter",
        shapes=(
            Shape(
                path="services/billing/queue.ts",
                symbol="sqs.send(SendMessageCommand)",
                operation_id="send:invoices.fifo",
                args_keys=("QueueUrl", "MessageBody", "MessageGroupId", "MessageDeduplicationId"),
                reads=("MessageId", "SequenceNumber"),
                snippet=(
                    "await sqs.send(new SendMessageCommand({\n"
                    "  QueueUrl, MessageBody: JSON.stringify(invoice),\n"
                    "  MessageGroupId: invoice.accountId,\n"
                    "}))"
                ),
            ),
            Shape(
                path="services/billing/worker.ts",
                symbol="sqs.send(ReceiveMessageCommand)",
                operation_id="receive:invoices.fifo",
                args_keys=("QueueUrl", "MaxNumberOfMessages", "WaitTimeSeconds"),
                reads=(
                    "Messages.Body.invoice_id",
                    "Messages.Body.amount_due",
                    "Messages.ReceiptHandle",
                ),
                loop_depth=1,
            ),
        ),
    ),
    Surface(
        kind="queues",
        vendor="google-pubsub",
        service="events-ingest",
        sdk_version="4.7.0",
        from_version="v1.9.0",
        to_version="v1.11.0",
        ptr_root="/topics/events-ingest/schema/fields",
        unbound_operation="publish:events-audit",
        shapes=(
            Shape(
                path="services/ingest/publisher.py",
                symbol="publisher.publish(events-ingest)",
                operation_id="publish:events-ingest",
                args_keys=("topic", "data", "ordering_key", "attributes"),
                reads=("message_id", "ordering_key"),
                snippet=(
                    "future = publisher.publish(\n"
                    "    topic_path, data=payload.encode(), ordering_key=tenant_id\n"
                    ")"
                ),
            ),
            Shape(
                path="services/ingest/subscriber.py",
                symbol="subscriber.subscribe(events-ingest-sub)",
                operation_id="subscribe:events-ingest-sub",
                args_keys=("subscription", "callback", "flow_control"),
                reads=("data.event_name", "data.occurred_at", "attributes.tenant"),
                loop_depth=1,
            ),
        ),
    ),
    # --- soap: HTTP + XML behind a WSDL --------------------------------------------------------
    Surface(
        kind="soap",
        vendor="fedex",
        service="Rate Service",
        sdk_version="v28",
        from_version="v26",
        to_version="v28",
        ptr_root="/definitions/RateReply/RateReplyDetails",
        unbound_operation="cancelPendingShipment",
        shapes=(
            Shape(
                path="services/shipping/fedex_client.py",
                symbol="RateServiceClient.getRates",
                operation_id="getRates",
                args_keys=("WebAuthenticationDetail", "ClientDetail", "RequestedShipment"),
                reads=(
                    "RateReplyDetails.ServiceType",
                    "RateReplyDetails.RatedShipmentDetails.ShipmentRateDetail.TotalNetCharge",
                ),
                snippet=(
                    "reply = client.service.getRates(\n"
                    "    WebAuthenticationDetail=auth, ClientDetail=detail,\n"
                    "    RequestedShipment=shipment,\n"
                    ")"
                ),
            ),
            Shape(
                path="services/shipping/fedex_tracking.py",
                symbol="TrackServiceClient.track",
                operation_id="track",
                args_keys=("SelectionDetails", "TransactionDetail"),
                reads=("CompletedTrackDetails.TrackDetails.StatusDetail.Code",),
            ),
        ),
    ),
    Surface(
        kind="soap",
        vendor="authorize-net",
        service=None,
        sdk_version="2.0.2",
        from_version="1.0",
        to_version="1.1",
        ptr_root="/definitions/createTransactionResponse/transactionResponse",
        unbound_operation="getTransactionDetails",
        shapes=(
            Shape(
                path="services/payments/authorize_net_client.py",
                symbol="AuthorizeNetClient.createTransactionRequest",
                operation_id="createTransactionRequest",
                args_keys=("merchantAuthentication", "transactionRequest", "refId"),
                reads=(
                    "transactionResponse.responseCode",
                    "transactionResponse.transId",
                    "transactionResponse.avsResultCode",
                ),
                snippet=(
                    "response = client.service.createTransactionRequest(\n"
                    "    merchantAuthentication=auth, transactionRequest=request\n"
                    ")"
                ),
            ),
        ),
    ),
    # --- auth: OAuth / OIDC flows and the claims a codebase reads ------------------------------
    Surface(
        kind="auth",
        vendor="auth0",
        service="Management API",
        sdk_version="4.17.0",
        from_version="2026-05-01",
        to_version="2026-08-15",
        ptr_root="/id_token/claims",
        unbound_operation="PatchUsersById",
        shapes=(
            Shape(
                path="services/identity/session.ts",
                symbol="auth0.verifyIdToken",
                operation_id="GetUserInfo",
                args_keys=("audience", "scope", "issuer"),
                reads=("sub", "email_verified", "https://sync.dev/roles"),
                snippet=(
                    "const claims = await auth0.verifyIdToken(idToken, {\n"
                    "  audience: process.env.AUTH0_AUDIENCE,\n"
                    "})\n"
                    'return { userId: claims.sub, roles: claims["https://sync.dev/roles"] }'
                ),
            ),
            Shape(
                path="services/identity/provisioning.ts",
                symbol="auth0.users.getAll",
                operation_id="GetUsers",
                args_keys=("q", "page", "per_page", "include_totals"),
                reads=("users.user_id", "users.identities.connection", "total"),
                loop_depth=1,
            ),
        ),
    ),
    Surface(
        kind="auth",
        vendor="okta",
        service="Okta Identity Engine",
        sdk_version="7.0.1",
        from_version="2026-04-24",
        to_version="2026-08-12",
        ptr_root="/access_token/claims",
        unbound_operation="ListGroupRules",
        shapes=(
            Shape(
                path="services/identity/okta_scim.py",
                symbol="okta.user_api.list_users",
                operation_id="ListUsers",
                args_keys=("search", "limit", "after"),
                reads=("profile.login", "profile.department", "status"),
                snippet=(
                    "users, resp, err = await okta.user_api.list_users(\n"
                    '    query_params={"search": \'status eq "ACTIVE"\', "limit": 200}\n'
                    ")"
                ),
                loop_depth=1,
            ),
        ),
    ),
    Surface(
        kind="auth",
        vendor="clerk",
        service="Backend API",
        sdk_version="1.6.0",
        from_version="2026-06-01",
        to_version="2026-08-20",
        ptr_root="/session_token/claims",
        unbound_operation="CreateOrganizationInvitation",
        shapes=(
            Shape(
                path="web/src/auth/require-session.ts",
                symbol="clerkClient.verifyToken",
                operation_id="VerifySessionToken",
                args_keys=("token", "authorizedParties"),
                reads=("sub", "org_id", "org_role", "sid"),
                snippet=(
                    "const payload = await clerkClient.verifyToken(token, {\n"
                    "  authorizedParties: [origin],\n"
                    "})\n"
                    "return { userId: payload.sub, orgRole: payload.org_role }"
                ),
            ),
        ),
    ),
    # --- baas: generated, schema-derived endpoints over the customer's own tables -------------
    Surface(
        kind="baas",
        vendor="supabase",
        service="PostgREST",
        sdk_version="2.45.0",
        from_version="2026-06-04",
        to_version="2026-08-21",
        ptr_root="/public/profiles/columns",
        unbound_operation="select:public.audit_log",
        shapes=(
            Shape(
                path="web/src/data/profiles.ts",
                symbol="supabase.from(profiles).select",
                operation_id="select:public.profiles",
                args_keys=("table", "columns", "eq.id"),
                reads=("id", "full_name", "avatar_url", "updated_at"),
                snippet=(
                    "const { data, error } = await supabase\n"
                    '  .from("profiles")\n'
                    '  .select("id, full_name, avatar_url, updated_at")\n'
                    '  .eq("id", session.user.id)\n'
                    "  .single()"
                ),
            ),
            Shape(
                path="web/src/data/orders.ts",
                symbol="supabase.from(orders).upsert",
                operation_id="upsert:public.orders",
                args_keys=("table", "values", "onConflict"),
                reads=("id", "status"),
            ),
        ),
    ),
    Surface(
        kind="baas",
        vendor="firebase",
        service="Cloud Firestore",
        sdk_version="11.1.0",
        from_version="10.12.0",
        to_version="11.1.0",
        ptr_root="/collections/sessions/fields",
        unbound_operation="query:analytics_events",
        shapes=(
            Shape(
                path="web/src/data/sessions.ts",
                symbol="firestore.getDocs(sessions)",
                operation_id="query:sessions",
                args_keys=("collection", "where.userId", "orderBy", "limit"),
                reads=("docs.id", "docs.data.lastSeenAt", "docs.data.deviceLabel"),
                snippet=(
                    "const snapshot = await getDocs(query(\n"
                    '  collection(db, "sessions"),\n'
                    '  where("userId", "==", uid),\n'
                    '  orderBy("lastSeenAt", "desc"), limit(20),\n'
                    "))"
                ),
            ),
        ),
    ),
    Surface(
        kind="baas",
        vendor="airtable",
        service="Web API",
        sdk_version="0.12.2",
        from_version="2026-03-01",
        to_version="2026-08-05",
        ptr_root="/bases/appSyncOps/tables/Vendors/fields",
        unbound_operation="list:Contacts",
        shapes=(
            Shape(
                path="tools/ops/airtable_sync.py",
                symbol="airtable.table(Vendors).all",
                operation_id="list:Vendors",
                args_keys=("baseId", "tableName", "view", "pageSize"),
                reads=("fields.Name", "fields.Tier", "fields.Owner", "createdTime"),
                snippet=(
                    "records = airtable.table(BASE_ID, \"Vendors\").all(\n"
                    '    view="Watched", page_size=100\n'
                    ")"
                ),
                loop_depth=1,
            ),
        ),
    ),
)

#: Vendors whose intake has delivered and whose call sites are nowhere -- the state a codebase is
#: in before it adopts an integration. A vendor row with changes and zero call sites has broken a
#: screen that divided by the call-site count.
UNCALLED: tuple[tuple[str, str, str, str, str], ...] = (
    ("plaid", "rest-sdk", "2020-09-14.r7", "2020-09-14.r9", "ItemPublicTokenExchange"),
    ("datadog", "rest-openapi", "v1.2026-05", "v1.2026-08", "POST /api/v2/logs"),
)

#: Telemetry, attached to a few surfaces and deliberately not to the rest. Absence here is what
#: makes *no telemetry attached* a state the console can be checked against.
#:
#: `(vendor, operation, rung, server, method, url_template, spans)`. An empty method is honest on a
#: transport that has none -- Kafka has a broker, not a verb -- and the console renders it through
#: the absence marker rather than as a blank.
TELEMETRY: tuple[tuple[str, str, str, str, str, str, int], ...] = (
    (
        "stripe", "PostPaymentIntents", "observed",
        "api.stripe.com", "post", "/v1/payment_intents", 4,
    ),
    (
        "openai", "createChatCompletion", "observed",
        "api.openai.com", "post", "/v1/chat/completions", 9,
    ),
    (
        "anthropic", "createMessage", "observed",
        "api.anthropic.com", "post", "/v1/messages", 3,
    ),
    (
        "github", "query:RepositoryIssues", "resolved",
        "api.github.com", "post", "/graphql", 6,
    ),
    (
        "supabase", "select:public.profiles", "observed",
        "db.synthetic.supabase.co", "get", "/rest/v1/profiles", 12,
    ),
    (
        "auth0", "GetUserInfo", "observed",
        "synthetic.eu.auth0.com", "get", "/userinfo", 2,
    ),
    (
        "kafka", "produce:orders.v2", "observed",
        "pkc-4yyd6.eu-central-1.aws.confluent.cloud:9092", "", "", 31,
    ),
    # Nothing correlated this request to an operation. `unresolved` with an empty operation id is
    # the honest pairing, and the unattributed-traffic panel exists to render exactly this.
    (
        "fastly", "", "unresolved",
        "api.fastly.com", "post", "", 5,
    ),
)

#: Error windows. Two shapes, and the difference is the point: a window over a vendor telemetry
#: also covers, and a window over one it does not -- a numerator whose denominator is nowhere.
ERROR_WINDOWS: tuple[tuple[str, str, str, str, str, int, int], ...] = (
    ("stripe", "PostPaymentIntents", "observed", "error-tracker-group", "4xx", 23, 4),
    ("sendgrid", "POST /v3/mail/send", "unresolved", "error-tracker-group", "5xx", 17, 3),
    # No status class: an exception raised reading a field off a successful response carries none,
    # which is a third answer rather than a missing one.
    ("okta", "ListUsers", "unresolved", "error-tracker-group", "", 6, 1),
)


SURFACE_BY_KEY: dict[tuple[str, str], Surface] = {(s.kind, s.vendor): s for s in SURFACES}


def _shapes_for(surface: Surface) -> tuple[Shape, ...]:
    """A surface's own shapes, plus the awkward one that belongs to it."""
    extra = AWKWARD.get((surface.kind, surface.vendor))
    return surface.shapes if extra is None else surface.shapes + (extra,)


def _call_site(repo: str, index: int, surface: Surface, shape: Shape) -> CallSite:
    return CallSite(
        repo_id=repo,
        path=shape.path,
        # Position is part of a call site's identity, so two shapes sharing a path -- the GitHub
        # webhook route handles two events in one file -- need distinct lines or they collapse
        # onto one row.
        line=12 + index * 7,
        col=2 + index % 9,
        vendor_id=surface.vendor,
        operation_id=shape.operation_id,
        service_id=surface.service,
        symbol=shape.symbol,
        args_keys=list(shape.args_keys),
        response_fields_read=list(shape.reads),
        sdk_version=surface.sdk_version,
        content_hash=f"synthetic{index:032d}"[:32],
        loop_depth=shape.loop_depth,
        # A snippet on some rows and not others: the code pane must say which nothing it is.
        snippet=shape.snippet,
        snippet_start_line=None if shape.snippet is None else max(1, 10 + index * 7),
        indexed_at=NOW - timedelta(hours=index),
    )


def _changes_for(surface: Surface, shapes: tuple[Shape, ...]) -> list[VendorChange]:
    """One change per severity, then one this codebase does not call.

    The bound five walk the surface's own change kinds and point at a field one of its call sites
    genuinely reads, which is what makes the finding they produce mean something on screen.
    """
    kinds = CHANGE_KINDS[surface.kind]
    source = CHANGE_SOURCES[surface.kind]
    changes = []
    for s_i, severity in enumerate(SEVERITIES):
        shape = shapes[s_i % len(shapes)]
        changes.append(
            VendorChange(
                vendor_id=surface.vendor,
                from_version=surface.from_version,
                to_version=surface.to_version,
                kind=kinds[s_i],
                operation_id=shape.operation_id,
                path_ptr=f"{surface.ptr_root}/{shape.reads[s_i % len(shape.reads)]}",
                severity=severity,
                source=source,
                raw={"synthetic": True, "surface": surface.kind},
                detected_at=NOW - timedelta(hours=s_i + 1),
            )
        )
    changes.append(
        VendorChange(
            vendor_id=surface.vendor,
            from_version=surface.from_version,
            to_version=surface.to_version,
            kind=kinds[3],
            operation_id=surface.unbound_operation,
            path_ptr=f"{surface.ptr_root}/unbound",
            severity="addition",
            source=source,
            raw={"synthetic": True, "surface": surface.kind, "binds": None},
            detected_at=NOW - timedelta(hours=7),
        )
    )
    return changes


def write(store: GraphStore, scale: int) -> str:
    lines = []

    # --- the wide repository: every protocol kind, in the shape that kind is actually called ---
    plan: list[tuple[Surface, Shape]] = [
        (surface, shape) for surface in SURFACES for shape in _shapes_for(surface)
    ]
    site_ids: dict[tuple[str, str], str] = {}
    for index, (surface, shape) in enumerate(plan):
        site_ids[(surface.vendor, shape.operation_id)] = store.upsert_call_site(
            _call_site(WIDE, index, surface, shape)
        )
    kinds = {surface.kind for surface in SURFACES}
    vendors = {surface.vendor for surface in SURFACES}
    lines.append(
        f"{len(plan)} call sites in {WIDE} across {len(vendors)} vendors "
        f"and {len(kinds)} protocol kinds"
    )

    # --- a change per severity per surface, plus one per surface that binds nothing ---
    changes = 0
    unbound = 0
    findings = 0
    f_i = 0
    for surface in SURFACES:
        shapes = _shapes_for(surface)
        for c_i, change in enumerate(_changes_for(surface, shapes)):
            change_id = store.upsert_vendor_change(change)
            changes += 1
            if c_i >= len(SEVERITIES):
                unbound += 1
                continue
            # Four rungs, not five. `insert_finding` refuses `unattributed` outright: it is
            # reserved for rows written before the column existed, and a corpus that manufactured
            # one would be asserting a history this database does not have. The console still has
            # to render it -- real rows carry it -- so that state is checked against the real
            # graph, not from here.
            store.insert_finding(
                Finding(
                    detector=f"synthetic-{surface.kind}",
                    claim=f"{change.kind}:{change.path_ptr}",
                    binding_rung=RUNGS[f_i % len(RUNGS)],
                    # The site the change actually reaches. Pairing a Stripe change with an OpenAI
                    # call site would put an incoherent row in front of every screen that renders
                    # both sides of a finding.
                    call_site_id=site_ids[
                        (surface.vendor, shapes[c_i % len(shapes)].operation_id)
                    ],
                    vendor_change_id=change_id,
                    severity=change.severity,
                    rationale=(
                        f"{surface.vendor} moved {surface.from_version} to "
                        f"{surface.to_version}; this {surface.kind} call site reads what moved."
                    ),
                    status=STATUSES[f_i % len(STATUSES)],
                    created_at=NOW - timedelta(hours=f_i),
                )
            )
            findings += 1
            f_i += 1
    lines.append(
        f"{changes} vendor changes across {len(SEVERITIES)} severities and "
        f"{len(set(CHANGE_SOURCES.values()))} sources"
    )
    lines.append(f"{unbound} of those name an operation nothing in this codebase binds")
    lines.append(
        f"{findings} findings across {len(RUNGS)} rungs, {len(SEVERITIES)} severities and "
        f"{len(kinds)} detectors"
    )

    # --- call sites no finding names, so `clean` and `unchecked` have rows to draw ---
    for q_i, (key, shape) in enumerate(QUIET.items()):
        store.upsert_call_site(_call_site(WIDE, len(plan) + q_i, SURFACE_BY_KEY[key], shape))
    for vendor, outcome, reason, count in INTAKE:
        store.record_intake_attempt(
            IntakeAttempt(
                vendor_id=vendor,
                attempted_at=ASKED_AT,
                outcome=outcome,
                reason_code=reason,
                detail=None if reason is None else f"synthetic {reason}",
                changes_count=count,
                source=INTAKE_SOURCE,
                duration_ms=180.0 + count,
            )
        )
    successes = sum(1 for row in INTAKE if row[1] == "success")
    lines.append(
        f"{len(QUIET)} more call sites there carrying no finding, and {len(INTAKE)} intake "
        f"attempts ({successes} successful), so all three binding statuses draw"
    )

    # --- vendors with intake and no call site anywhere ---
    uncalled_changes = 0
    for vendor, kind, from_version, to_version, operation in UNCALLED:
        for s_i, severity in enumerate(SEVERITIES[:3]):
            store.upsert_vendor_change(
                VendorChange(
                    vendor_id=vendor,
                    from_version=from_version,
                    to_version=to_version,
                    kind=CHANGE_KINDS[kind][s_i],
                    operation_id=operation,
                    path_ptr=f"/{vendor}/{operation}/{s_i}",
                    severity=severity,
                    source=CHANGE_SOURCES[kind],
                    raw={"synthetic": True, "surface": kind},
                    detected_at=NOW - timedelta(hours=s_i + 2),
                )
            )
            uncalled_changes += 1
    lines.append(
        f"{uncalled_changes} changes for {len(UNCALLED)} vendors with no call site anywhere"
    )

    # --- telemetry on some vendors only: attached, absent, and errors-without-calls ---
    for o_i, (vendor, operation, rung, server, method, template, spans) in enumerate(TELEMETRY):
        store.record_observed_call(
            ObservedCall(
                repo_id=WIDE,
                vendor_id=vendor,
                operation_id=operation,
                binding_rung=rung,
                server_address=server,
                http_method=method,
                trace_id=f"synthetic-trace-{o_i}",
                url_template=template,
                spans={
                    f"s{o_i}-{n}": {
                        "target": f"d{n % 3}",
                        "status": 429 if n and n % 7 == 0 else 200,
                        "resend": n % 2,
                    }
                    for n in range(spans)
                },
                first_seen=NOW - timedelta(hours=6),
                last_seen=NOW - timedelta(minutes=5 + o_i),
            )
        )
    lines.append(
        f"{len(TELEMETRY)} observed calls on {len({row[0] for row in TELEMETRY})} of "
        f"{len(vendors)} vendors, one of them uncorrelated"
    )

    for vendor, operation, rung, source, status_class, errors, issues in ERROR_WINDOWS:
        store.record_observed_error_window(
            ObservedErrorWindow(
                repo_id=WIDE,
                vendor_id=vendor,
                operation_id=operation,
                binding_rung=rung,
                source=source,
                status_class=status_class,
                # The window bounds are in this row's grain, so `NOW` here wrote a second window
                # on every run rather than converging on the one already recorded. Anchored to
                # `ASKED_AT` for the reason stated there.
                window_start=ASKED_AT - timedelta(hours=2),
                window_end=ASKED_AT - timedelta(hours=1),
                error_count=errors,
                issue_count=issues,
            )
        )
    observed_vendors = {row[0] for row in TELEMETRY}
    windows_without_calls = sum(1 for row in ERROR_WINDOWS if row[0] not in observed_vendors)
    lines.append(
        f"{len(ERROR_WINDOWS)} error windows, {windows_without_calls} with no calls behind them"
    )

    # --- a repository that exists and holds nothing: the never-indexed empty state ---
    store.upsert_call_site(_call_site(EMPTY, 0, SURFACES[0], SURFACES[0].shapes[0]))
    lines.append(f"1 call site in {EMPTY}, so an almost-empty repository has a screen")

    # --- the paging repository ---
    if scale:
        for i in range(scale):
            surface, shape = plan[i % len(plan)]
            store.upsert_call_site(
                _call_site(
                    SCALE,
                    i,
                    surface,
                    Shape(
                        path=f"packages/generated/{i // 100:03d}/{shape.path}",
                        symbol=shape.symbol,
                        operation_id=shape.operation_id,
                        args_keys=shape.args_keys,
                        reads=shape.reads,
                        snippet=shape.snippet,
                        loop_depth=shape.loop_depth,
                    ),
                )
            )
        lines.append(f"{scale} call sites in {SCALE}, enough to page")

    return "\n".join(f"  {line}" for line in lines)


def remove(store: GraphStore) -> str:
    """Take back exactly what `write` put in, and nothing a real pass produced.

    `finding` has no `repo_id`, which the first version of this function did not know: it deleted
    by one and raised `UndefinedColumn`, so `--remove` never completed and the corpus could only
    grow. Findings are reached through their call site instead, before the site they reference.
    """
    removed = 0
    with store._connect().cursor() as cur:  # noqa: SLF001 - dev script, one connection
        for repo in (WIDE, EMPTY, SCALE):
            cur.execute(
                "DELETE FROM finding WHERE call_site_id IN "
                "(SELECT id FROM call_site WHERE repo_id = %s)",
                (repo,),
            )
            for table in ("observed_call", "observed_error_window", "call_site"):
                cur.execute(f"DELETE FROM {table} WHERE repo_id = %s", (repo,))
            removed += 1

        # A vendor change carries no repo id, so nothing above can reach one. Every change this
        # script writes is stamped `raw->>'synthetic'`, which is the only key that takes exactly
        # these back out and leaves a real intake row for the same vendor standing.
        cur.execute("DELETE FROM finding WHERE detector LIKE %s", ("synthetic-%",))
        cur.execute("DELETE FROM vendor_change WHERE raw->>'synthetic' = 'true'")
        changes = cur.rowcount
        cur.execute("DELETE FROM intake_attempt WHERE source = %s", (INTAKE_SOURCE,))
        attempts = cur.rowcount
    return (
        f"  removed {removed} synthetic repositories, {changes} synthetic vendor changes "
        f"and {attempts} synthetic intake attempts"
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--remove", action="store_true", help="delete the synthetic rows")
    parser.add_argument("--scale", type=int, default=0, help="also write N call sites to page")
    parser.add_argument("--dsn", default=DEFAULT_DSN)
    args = parser.parse_args(argv[1:])

    store = GraphStore(args.dsn)
    store.apply_schema()

    print(f"{'removing' if args.remove else 'writing'} synthetic rows in {args.dsn}")
    print(remove(store) if args.remove else write(store, args.scale))
    if not args.remove:
        print("  run with --remove to take exactly these away")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
