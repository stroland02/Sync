/**
 * A call site's list-valued fields are the one place on this level where empty and absent meet.
 *
 * `args_keys` and `response_fields_read` are arrays, and an empty one is what the index records
 * when it read the call and found none — which the console draws as its absence marker rather than
 * as an empty cell, because an empty cell is indistinguishable from a column that failed to render.
 * Joining an empty array gives `""`, and `""` renders as nothing at all; that is the wrong answer
 * this guard exists to catch.
 */

import { describe, expect, it } from "vitest"

import { joinOrAbsent } from "@/features/bindings/call-site-fields"

describe("joinOrAbsent", () => {
  it("answers null for an empty list, so the caller renders the absence marker", () => {
    expect(joinOrAbsent([])).toBeNull()
  })

  it("joins what is there", () => {
    expect(joinOrAbsent(["customer", "amount", "currency"])).toBe("customer, amount, currency")
  })

  it("keeps a single value as itself rather than decorating it", () => {
    expect(joinOrAbsent(["customer"])).toBe("customer")
  })
})
