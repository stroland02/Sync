/**
 * Two formatters whose wrong answers are both silent.
 *
 * `describeRung` translates a closed vocabulary the transport owns; the case that matters is the
 * one where the transport has grown a value this console has never heard of, because the wrong
 * behaviour there is a blank cell that reads as "no rung" instead of "a rung we cannot name".
 *
 * `formatElapsed` reads the clock, so its tests pin the clock. A duration test that depends on
 * when it runs is a test that fails on a slow machine and gets deleted for being flaky.
 */

import { afterEach, describe, expect, it, vi } from "vitest"

import { describeRung, formatElapsed, pathAfter } from "@/lib/format"
import type { BindingSource } from "@/api/types"

const NOW = new Date("2026-08-06T12:00:00.000Z")

function ago(ms: number): string {
  return new Date(NOW.getTime() - ms).toISOString()
}

afterEach(() => {
  vi.useRealTimers()
})

describe("describeRung", () => {
  it("names every member of the rung union", () => {
    const rungs: BindingSource[] = [
      "static",
      "resolved",
      "observed",
      "unresolved",
      "unattributed",
    ]
    for (const rung of rungs) {
      expect(describeRung(rung)).not.toBe("")
      expect(describeRung(rung)).not.toMatch(/does not recognise/)
    }
  })

  it("distinguishes the five rungs from each other", () => {
    // A translation that collapsed two rungs onto one sentence would pass an
    // each-one-is-non-empty test and still lose the distinction the rung exists to carry.
    const said = new Set(
      (["static", "resolved", "observed", "unresolved", "unattributed"] as BindingSource[]).map(
        describeRung
      )
    )
    expect(said.size).toBe(5)
  })

  it("says the vocabulary has changed for a rung it has never heard of", () => {
    // The transport is the owner of this vocabulary and it can grow one without the console.
    // The cast is the point of the test: this is the value the type says cannot arrive.
    const unknown = describeRung("correlated-by-a-detector-written-next-month" as BindingSource)
    expect(unknown).toMatch(/does not recognise/)
    expect(unknown).toMatch(/vocabulary has changed/)
  })
})

describe("formatElapsed", () => {
  it("returns null for an absent timestamp rather than a duration since the epoch", () => {
    expect(formatElapsed(null)).toBeNull()
    expect(formatElapsed(undefined)).toBeNull()
    expect(formatElapsed("")).toBeNull()
  })

  it("returns null for a string that is not a timestamp", () => {
    expect(formatElapsed("last Tuesday")).toBeNull()
  })

  it("reads zero elapsed as zero seconds", () => {
    vi.useFakeTimers()
    vi.setSystemTime(NOW)
    expect(formatElapsed(NOW.toISOString())).toBe("0s ago")
  })

  it("never reports a negative duration for a timestamp in the future", () => {
    // Clock skew between the customer's checkpointer and this browser is ordinary, and
    // "-3s ago" reads as a bug in the console rather than as a fact about two clocks.
    vi.useFakeTimers()
    vi.setSystemTime(NOW)
    expect(formatElapsed(new Date(NOW.getTime() + 90_000).toISOString())).toBe("0s ago")
  })

  it("climbs to the coarsest unit that stays readable", () => {
    vi.useFakeTimers()
    vi.setSystemTime(NOW)
    expect(formatElapsed(ago(45_000))).toBe("45s ago")
    expect(formatElapsed(ago(90_000))).toBe("2m ago")
    expect(formatElapsed(ago(3 * 3_600_000))).toBe("3h ago")
    expect(formatElapsed(ago(50 * 3_600_000))).toBe("2d ago")
  })

  it("crosses each unit boundary rather than reporting 60 of the smaller one", () => {
    vi.useFakeTimers()
    vi.setSystemTime(NOW)
    expect(formatElapsed(ago(60_000))).toBe("1m ago")
    expect(formatElapsed(ago(3_600_000))).toBe("1h ago")
    expect(formatElapsed(ago(24 * 3_600_000))).toBe("1d ago")
  })
})

describe("pathAfter", () => {
  it("returns what follows a shared directory, so the row carries what distinguishes it", () => {
    expect(pathAfter("packages/billing/charges/", "packages/billing/charges/create.ts")).toBe(
      "create.ts"
    )
  })

  it("returns the whole path when there is no shared directory to factor out", () => {
    expect(pathAfter("", "packages/billing/charges/create.ts")).toBe(
      "packages/billing/charges/create.ts"
    )
  })

  it("returns the whole path when the path does not start with the prefix", () => {
    // The payload computes the prefix over the same set it drew the rows from, so this cannot
    // happen from the API. It is here because the failure mode if it ever did is a mangled path
    // that reads as a real one — a reader would take `ing/charges/create.ts` for a file. Falling
    // back to the whole path is wrong-but-legible instead of wrong-and-plausible.
    expect(pathAfter("services/orders/", "packages/billing/charges/create.ts")).toBe(
      "packages/billing/charges/create.ts"
    )
  })

  it("keeps a path that is exactly the prefix legible rather than returning nothing", () => {
    // A directory cannot itself be a call site, so this is unreachable through the payload too.
    // An empty cell would be a row that names no file at all, which is worse than a repeated
    // prefix.
    expect(pathAfter("packages/billing/", "packages/billing/")).toBe("packages/billing/")
  })
})
