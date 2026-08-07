/**
 * The drawer's open state is read out of the URL, and a URL is the one input this console does not
 * control. It arrives pasted from another operator, bookmarked from another page position, or typed
 * — so every branch below is a state a reader can actually reach, not a defensive one.
 *
 * Three answers, and collapsing any two of them tells a reader something false. Nothing selected is
 * the list. A key this page holds is the binding. A key this page does not hold is neither: the row
 * may exist behind a filter, on another page, or not at all, and the screen must say that rather
 * than render an empty drawer (which claims the call site is gone) or no drawer (which claims the
 * link was wrong).
 *
 * The colliding-path case is the one worth reading. A call site's key is four fields joined, and a
 * customer repository may hold a path with a colon in it. Anything that splits the key back apart
 * resolves such a key to the wrong row or to none — so the derivation compares and never parses,
 * and this file is where that is held.
 */

import { describe, expect, it } from "vitest"

import type { BindingCallSite } from "@/api/types"
import { bindingKey, selectBinding } from "@/features/bindings/binding-selection"

function site(overrides: Partial<BindingCallSite> = {}): BindingCallSite {
  return {
    repo_id: "repo-a",
    path: "src/billing/charge.ts",
    line: 42,
    col: 8,
    symbol: "stripe.charges.create",
    sdk_version: "14.0.0",
    args_keys: [],
    response_fields_read: [],
    loop_depth: 0,
    binding_rung: "static",
    indexed_at: "2026-08-06T19:35:30.483733+00:00",
    ...overrides,
  }
}

describe("bindingKey", () => {
  it("tells two call sites in one file apart by line and column", () => {
    const first = site({ line: 42, col: 8 })
    const second = site({ line: 42, col: 20 })
    expect(bindingKey(first)).not.toEqual(bindingKey(second))
  })

  it("tells the same path in two repositories apart", () => {
    expect(bindingKey(site({ repo_id: "repo-a" }))).not.toEqual(
      bindingKey(site({ repo_id: "repo-b" })),
    )
  })
})

describe("selectBinding", () => {
  it("selects nothing when the URL names nothing", () => {
    expect(selectBinding(null, [site()])).toEqual({ kind: "none" })
  })

  it("selects nothing when the parameter is present but empty", () => {
    expect(selectBinding("", [site()])).toEqual({ kind: "none" })
  })

  it("resolves a key this page holds to that call site", () => {
    const wanted = site({ path: "src/payments/create-charge.ts", line: 21, col: 6 })
    const selection = selectBinding(bindingKey(wanted), [site(), wanted])
    expect(selection.kind).toBe("resolved")
    expect(selection.kind === "resolved" && selection.site).toBe(wanted)
  })

  it("reports a key this page does not hold rather than falling back to the list", () => {
    const selection = selectBinding(bindingKey(site({ repo_id: "repo-z" })), [site()])
    expect(selection).toEqual({ kind: "unresolved", key: "repo-z:src/billing/charge.ts:42:8" })
  })

  it("reports a key this page does not hold rather than falling back to the first row", () => {
    const selection = selectBinding("nothing-shaped-like-a-key", [site()])
    expect(selection.kind).toBe("unresolved")
  })

  it("does not resolve a key by splitting it, so a path holding a colon cannot collide", () => {
    // Split on ":" and read the last two fields as line and column, and these two rows are
    // indistinguishable: both parse to repository `repo-a`, line 42, column 8.
    const decoy = site({ path: "src/a.ts:42:8/index.ts", line: 42, col: 8 })
    const real = site({ path: "src/a.ts", line: 42, col: 8 })
    expect(bindingKey(decoy)).not.toEqual(bindingKey(real))

    const selection = selectBinding(bindingKey(real), [decoy, real])
    expect(selection.kind === "resolved" && selection.site).toBe(real)
  })

  it("selects nothing when the page holds no call site at all", () => {
    expect(selectBinding(bindingKey(site()), [])).toEqual({
      kind: "unresolved",
      key: "repo-a:src/billing/charge.ts:42:8",
    })
  })
})
