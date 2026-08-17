import { describe, expect, it } from "vitest"

import { defaultDisclosed, inkFor, latestEvidenceAt } from "@/features/workflows/sequence-dynamics"

describe("inkFor", () => {
  it("recedes only the unreached standings", () => {
    expect(inkFor("not_reached_yet")).toBe("receded")
    expect(inkFor("never_reached")).toBe("receded")
    expect(inkFor("ran")).toBe("default")
    expect(inkFor("due")).toBe("default")
    expect(inkFor("due_again")).toBe("default")
  })
})

describe("latestEvidenceAt", () => {
  it("takes the newest of last_seen_at falling back to first_seen_at", () => {
    const nodes = [
      { last_seen_at: "2026-08-17T14:03:00Z", first_seen_at: "2026-08-17T14:02:00Z" },
      { last_seen_at: null, first_seen_at: "2026-08-17T14:05:00Z" },
    ]
    expect(latestEvidenceAt(nodes as never)).toBe("2026-08-17T14:05:00Z")
  })

  it("is null when nothing was stamped", () => {
    expect(latestEvidenceAt([{ evidence: {} }] as never)).toBeNull()
  })
})

describe("defaultDisclosed", () => {
  it("opens only the last reached node", () => {
    expect(defaultDisclosed(3, 3)).toBe(true)
    expect(defaultDisclosed(2, 3)).toBe(false)
  })
})
