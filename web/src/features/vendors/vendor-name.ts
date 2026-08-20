/**
 * What an integration is called, as a person writes it.
 *
 * **M15 Task 5.** The graph keys vendors by id — `stripe`, `openai`, `google-maps` — because an id
 * is what an adapter declares and what a call site binds to. That is correct for a key and wrong on
 * screen: a console that renders `openai` is showing a reader the database's spelling of a company
 * whose name is OpenAI.
 *
 * ## Why a registry rather than a rule
 *
 * Title-casing an id gets `Stripe` right and `Openai`, `Github` and `Sendgrid` wrong — and it is
 * wrong precisely on the vendors most likely to be watched. Capitalisation is a fact about each
 * company rather than a pattern, so it is recorded per vendor and derived for everyone else.
 *
 * ## The fallback is the honest half
 *
 * An unregistered vendor is **not** an error and must not render as one. Sync's whole plugin story
 * is that a third party writes an adapter without touching core, so a vendor this file has never
 * heard of is the expected case, not the exception. It gets a derived name — hyphens to spaces,
 * each part capitalised — which is right often enough to read well and never claims to be more
 * than a guess. The id itself stays the thing every URL and join uses.
 *
 * **This holds no marks and fetches nothing.** `vendor-mark.tsx` draws a monogram from the id.
 */

/**
 * Capitalisation that a rule cannot derive, keyed by vendor id.
 *
 * Kept deliberately short. An entry earns its place by being a name a reader would notice was
 * wrong — every vendor whose own spelling is not what title-casing produces.
 */
const WRITTEN_AS: Record<string, string> = {
  openai: "OpenAI",
  github: "GitHub",
  gitlab: "GitLab",
  sendgrid: "SendGrid",
  paypal: "PayPal",
  postgresql: "PostgreSQL",
  mysql: "MySQL",
  mongodb: "MongoDB",
  dynamodb: "DynamoDB",
  hubspot: "HubSpot",
  quickbooks: "QuickBooks",
  docusign: "DocuSign",
  youtube: "YouTube",
  linkedin: "LinkedIn",
  whatsapp: "WhatsApp",
  typeform: "Typeform",
  netsuite: "NetSuite",
  bigquery: "BigQuery",
  clickhouse: "ClickHouse",
  elevenlabs: "ElevenLabs",
  huggingface: "Hugging Face",
  aws: "AWS",
  gcp: "GCP",
  npm: "npm",
}

/**
 * How to write one vendor's name.
 *
 * Registered vendors get their own spelling; everyone else gets a derived one. Never throws and
 * never returns empty: a screen asking what to call a vendor always gets something to render.
 */
export function vendorName(vendorId: string): string {
  const key = vendorId.trim().toLowerCase()
  if (key === "") return vendorId
  const written = WRITTEN_AS[key]
  if (written !== undefined) return written

  return key
    .split(/[^a-z0-9]+/)
    .filter((part) => part.length > 0)
    .map((part) => part[0].toUpperCase() + part.slice(1))
    .join(" ")
}
