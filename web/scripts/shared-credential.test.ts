/**
 * The gate's properties, asserted rather than assumed.
 *
 * Every case here is a security claim the deployment note makes on this module's behalf, so each
 * one is written to fail if the claim stops being true — particularly "fails closed", which is the
 * one whose absence would be invisible in a working console.
 */

import { describe, expect, it } from "vitest"

import {
  MINIMUM_CREDENTIAL_LENGTH,
  credentialMatches,
  offeredCredential,
  requireCredential,
} from "./shared-credential"

describe("credentialMatches", () => {
  it("accepts the configured credential", () => {
    expect(credentialMatches("a-long-enough-secret", "a-long-enough-secret")).toBe(true)
  })

  it("rejects a wrong credential of the same length", () => {
    expect(credentialMatches("a-long-enough-secreT", "a-long-enough-secret")).toBe(false)
  })

  it("rejects a prefix of the credential, which a truncating comparison would accept", () => {
    expect(credentialMatches("a-long-enough", "a-long-enough-secret")).toBe(false)
  })

  it("rejects an empty offer rather than treating it as a match", () => {
    expect(credentialMatches("", "a-long-enough-secret")).toBe(false)
  })

  it("rejects everything when the configured credential is empty, rather than accepting all", () => {
    // The startup check refuses this case outright; if it is ever reached anyway, an empty
    // configured secret must not become a gate that opens for any input at all.
    expect(credentialMatches("", "")).toBe(false)
    expect(credentialMatches("anything", "")).toBe(false)
  })
})

describe("requireCredential", () => {
  it("refuses to start when the variable is absent — the gate fails closed", () => {
    const result = requireCredential({})
    expect(result.ok).toBe(false)
    expect(result.ok === false && result.reason).toContain("SYNC_CONSOLE_PASSWORD")
  })

  it("refuses a blank or whitespace-only credential", () => {
    expect(requireCredential({ SYNC_CONSOLE_PASSWORD: "" }).ok).toBe(false)
    expect(requireCredential({ SYNC_CONSOLE_PASSWORD: "   " }).ok).toBe(false)
  })

  it("refuses a credential under the floor, naming the floor", () => {
    const result = requireCredential({ SYNC_CONSOLE_PASSWORD: "short" })
    expect(result.ok).toBe(false)
    expect(result.ok === false && result.reason).toContain(String(MINIMUM_CREDENTIAL_LENGTH))
  })

  it("accepts a credential at or over the floor", () => {
    const value = "x".repeat(MINIMUM_CREDENTIAL_LENGTH)
    const result = requireCredential({ SYNC_CONSOLE_PASSWORD: value })
    expect(result.ok).toBe(true)
    expect(result.ok === true && result.credential).toBe(value)
  })
})

describe("offeredCredential", () => {
  it("reads the password half of a Basic header and ignores the username", () => {
    const header = `Basic ${Buffer.from("ignored:the-secret").toString("base64")}`
    expect(offeredCredential(header)).toBe("the-secret")
  })

  it("keeps a password containing a colon intact", () => {
    const header = `Basic ${Buffer.from("user:a:b:c").toString("base64")}`
    expect(offeredCredential(header)).toBe("a:b:c")
  })

  it("returns null for a missing, non-Basic, or malformed header", () => {
    expect(offeredCredential(undefined)).toBeNull()
    expect(offeredCredential("Bearer something")).toBeNull()
    expect(offeredCredential("Basic")).toBeNull()
    expect(offeredCredential(`Basic ${Buffer.from("no-separator").toString("base64")}`)).toBeNull()
  })
})
