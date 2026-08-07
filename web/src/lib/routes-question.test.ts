/**
 * A screen gets its `PageHeader` sentence from the registry, keyed by its own path.
 *
 * `RouteEntry.question` has been in `routes.ts` since the registry existed and rendered on nothing
 * until the chassis gave it a home. The failure this guards is not a missing sentence — it is the
 * *wrong* one: a lookup that keyed on anything but the path would hand a screen its neighbour's
 * question, and the two read plausibly enough that nobody would notice on either screen.
 *
 * Separate from `routes.test.tsx`, which is the reachability guard and is being edited by another
 * work item in parallel. A guard for a new export does not need to share a file with one.
 */

import { describe, expect, it } from "vitest"

import { ROUTES, routeQuestion } from "@/lib/routes"

describe("routeQuestion", () => {
  it("hands a route its own sentence rather than a neighbour's", () => {
    const vendor = ROUTES.find((route) => route.path === "/vendors/:vendorId")
    const fleet = ROUTES.find((route) => route.path === "/")
    expect(vendor).toBeDefined()
    expect(fleet).toBeDefined()
    expect(routeQuestion("/vendors/:vendorId")).toBe(vendor?.question)
    expect(routeQuestion("/vendors/:vendorId")).not.toBe(fleet?.question)
  })

  it("answers for every route the registry declares", () => {
    for (const route of ROUTES) {
      expect(routeQuestion(route.path)).toBe(route.question)
    }
  })

  it("throws on a path the registry does not declare, rather than rendering a header with none", () => {
    expect(() => routeQuestion("/bindings/vendors/:vendorId")).toThrow(
      "/bindings/vendors/:vendorId"
    )
  })
})
