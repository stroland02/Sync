/**
 * The API integration taxonomy: every kind of service interface the platform intends to watch.
 *
 * Owner direction, 2026-08-19: the Services page stops mirroring Vendors and instead shows the
 * breadth of integration surfaces — the vendor SDKs the index binds today are one class among
 * many. This is a **capability catalogue, not graph data**: each class carries a `status` saying
 * whether the pipeline watches it today or intends to, and the examples are named services of
 * that class, never claims that this workspace calls them. A class the graph actually binds
 * renders its live counts from the payload beside this; the catalogue itself asserts nothing a
 * detector measured.
 */

export type ApiClassStatus = "watched today" | "planned"

export interface ApiServiceClass {
  readonly id: string
  readonly name: string
  /** The wire shape a watcher has to understand. */
  readonly transport: string
  /** Services of this class a reader will recognise. Examples, never bindings. */
  readonly examples: readonly string[]
  /** What Sync watches — or would watch — for this class. */
  readonly watches: string
  readonly status: ApiClassStatus
}

export const API_SERVICE_CLASSES: readonly ApiServiceClass[] = [
  {
    id: "rest-sdk",
    name: "REST APIs via vendor SDKs",
    transport: "HTTPS + JSON, called through the vendor's published SDK",
    examples: ["Stripe", "Twilio", "GitHub"],
    watches: "SDK call sites bound to spec operations; spec diffs; observed traffic per operation",
    status: "watched today",
  },
  {
    id: "rest-openapi",
    name: "REST APIs via raw HTTP",
    transport: "HTTPS + JSON against an OpenAPI-described surface, no SDK in between",
    examples: ["internal microservices", "Fastly", "SendGrid v3"],
    watches: "URL-template call sites matched to the OpenAPI document; breaking-change diffs",
    status: "planned",
  },
  {
    id: "llm",
    name: "Model provider APIs",
    transport: "HTTPS + JSON with model identifiers as the versioned surface",
    examples: ["Anthropic", "OpenAI", "Mistral"],
    watches: "model-identifier literals in code against provider deprecation schedules",
    status: "watched today",
  },
  {
    id: "mcp",
    name: "MCP servers",
    transport: "Model Context Protocol over stdio or HTTP",
    examples: ["internal tool servers", "vendor MCP endpoints"],
    watches: "tool schemas captured per session; drift between captures",
    status: "watched today",
  },
  {
    id: "graphql",
    name: "GraphQL APIs",
    transport: "HTTPS + a typed schema; queries name exactly the fields they read",
    examples: ["GitHub GraphQL", "Shopify Admin", "Contentful"],
    watches: "query documents against schema deprecations — a removed field breaks the exact query",
    status: "planned",
  },
  {
    id: "grpc",
    name: "gRPC / protobuf services",
    transport: "HTTP/2 + protocol buffers, contract in .proto files",
    examples: ["Google Cloud APIs", "internal service meshes"],
    watches: "generated-stub call sites against .proto changes; wire-compatibility rules",
    status: "planned",
  },
  {
    id: "webhooks",
    name: "Inbound webhooks",
    transport: "the vendor calls you: HTTPS POST with a signed, versioned payload",
    examples: ["Stripe events", "GitHub webhooks", "Twilio status callbacks"],
    watches: "handler field reads against the vendor's event schema versions",
    status: "planned",
  },
  {
    id: "streaming",
    name: "Streaming & realtime APIs",
    transport: "WebSocket, server-sent events, or long-poll cursors",
    examples: ["Slack RTM", "market data feeds", "Supabase Realtime"],
    watches: "message-shape reads against published channel schemas",
    status: "planned",
  },
  {
    id: "queues",
    name: "Message queue contracts",
    transport: "AMQP, Kafka topics, or cloud queues with schema-registry payloads",
    examples: ["Kafka + Avro registry", "SQS", "Pub/Sub"],
    watches: "producer/consumer schemas against registry compatibility modes",
    status: "planned",
  },
  {
    id: "soap",
    name: "SOAP / XML services",
    transport: "HTTP + XML with a WSDL contract",
    examples: ["payment processors", "government and logistics gateways"],
    watches: "WSDL operation changes against generated client usage",
    status: "planned",
  },
  {
    id: "auth",
    name: "Identity & OAuth providers",
    transport: "OAuth 2.0 / OIDC flows plus provider-specific user APIs",
    examples: ["Auth0", "Okta", "Google Identity"],
    watches: "scope and claim usage against provider deprecation notices",
    status: "planned",
  },
  {
    id: "baas",
    name: "Backend-as-a-service data APIs",
    transport: "HTTPS + JSON over generated, schema-derived endpoints",
    examples: ["Supabase", "Firebase", "Airtable"],
    watches: "table/field reads against schema migrations the service publishes",
    status: "planned",
  },
] as const
