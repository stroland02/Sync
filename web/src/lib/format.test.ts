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

import { describeRange, describeRung, pathAfter } from "@/lib/format"
import type { BindingSource } from "@/api/types"

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

describe("describeRange with a filter active", () => {
  it("says a bare range when nothing is filtered out", () => {
    expect(describeRange(0, 50, 200)).toBe("1–50 of 200")
  })

  it("never lets a filtered count read as the whole set", () => {
    // Decision 60: the footer is the only thing standing between a filtered table and being read
    // as everything, because the owner did not take filter chips. A bare "1-4 of 4" under a
    // narrowed table is the claim this refuses.
    expect(describeRange(0, 4, 4, 31)).toBe("1–4 of 4 matched, 27 filtered out")
  })

  it("keeps the range across pages rather than collapsing to the shown count", () => {
    // The decision's own example is single-page. On page two "showing 50 of 200" would be false;
    // the range is what stays true, and the filtered clause travels with it.
    expect(describeRange(50, 50, 120, 900)).toBe("51–100 of 120 matched, 780 filtered out")
  })

  it("says nothing about filtering when the filter excluded nothing", () => {
    // A filter matching everything is not a filter the reader needs warning about, and
    // "0 filtered out" is noise that makes the real case easier to miss.
    expect(describeRange(0, 31, 31, 31)).toBe("1–31 of 31")
  })

  it("still says none when a filter matched nothing", () => {
    expect(describeRange(0, 0, 0, 31)).toBe("none of 31, all 31 filtered out")
  })
})
