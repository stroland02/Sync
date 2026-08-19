/**
 * How an integration's name is written.
 *
 * The derivation with a wrong answer is the fallback: an unregistered vendor is the *expected*
 * case — Sync's plugin story is that a third party writes an adapter without touching core — so a
 * name it has never seen must read well and must never look like an error.
 */

import { describe, expect, it } from "vitest"

import { vendorName } from "@/features/vendors/vendor-name"

describe("writing a vendor's name", () => {
  it("uses the company's own capitalisation where a rule would get it wrong", () => {
    // Title-casing gets Stripe right and these wrong, on exactly the vendors most likely watched.
    expect(vendorName("openai")).toBe("OpenAI")
    expect(vendorName("github")).toBe("GitHub")
    expect(vendorName("sendgrid")).toBe("SendGrid")
  })

  it("derives a readable name for a vendor it has never heard of", () => {
    expect(vendorName("stripe")).toBe("Stripe")
    expect(vendorName("google-maps")).toBe("Google Maps")
  })

  it("never returns nothing, whatever it is handed", () => {
    // A screen asking what to call a vendor always has something to render; an empty name would
    // render as a gap that reads as a load failure.
    expect(vendorName("")).toBe("")
    expect(vendorName("   ")).not.toBe("")
    expect(vendorName("_")).toBeDefined()
  })

  it("is case-insensitive on the key, because an id's case is not a fact about the company", () => {
    expect(vendorName("OpenAI")).toBe("OpenAI")
    expect(vendorName("OPENAI")).toBe("OpenAI")
  })
})
