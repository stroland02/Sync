/**
 * A URL the payload gave, or null.
 *
 * The value originates in the customer's repository by way of the forge, which makes it untrusted
 * input arriving at a boundary. Anything that is not http or https is not rendered as an anchor: a
 * `javascript:` href is a script the console would run on somebody else's say-so. Nothing here
 * constructs a URL the payload did not send.
 *
 * This boundary check is the single shared helper for B125, imported by both
 * `features/pullrequests/bundle-facts.ts` and `features/workflows/evidence.tsx`.
 */
export function asHttpUrl(value: unknown): string | null {
  if (typeof value !== "string" || value === "") return null
  let parsed: URL
  try {
    parsed = new URL(value)
  } catch {
    return null
  }
  return parsed.protocol === "http:" || parsed.protocol === "https:" ? value : null
}
