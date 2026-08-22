/**
 * The migration ratchet.
 *
 * Every address the console serves is either migrated onto `ScreenFrame` or explicitly pending.
 * The union must equal the declared set, so a route added later cannot dodge the skeleton by
 * being absent from both lists, and `PENDING` can only ever shrink.
 */

import { describe, expect, it } from "vitest"

import { DESTINATIONS, ROUTES } from "@/lib/routes"

/** Screens rendering through `ScreenFrame`. Move a path up as it migrates; never back. */
const MIGRATED = [
  "/repositories/:repoId/integration-changes",
  "/repositories/:repoId",
  "/repositories/:repoId/metrics",
  "/repositories/:repoId/corpus",
  "/repositories/:repoId/solutions",
  "/repositories/:repoId/runs",
  "/repositories/:repoId/vendors",
  "/repositories/:repoId/detectors",
]

const PENDING = [
  "/",
  "/settings",
  "/repositories/:repoId/file-tree",
  "/repositories/:repoId/call-sites",
  "/repositories/:repoId/graph",
  "/repositories/:repoId/findings",
  "/repositories/:repoId/services",
  "/repositories/:repoId/observed",
  "/repositories/:repoId/vendors/:vendorId",
  "/repositories/:repoId/bindings/vendors/:vendorId/operations/:operationId",
  "/repositories/:repoId/findings/:findingId",
  "/repositories/:repoId/findings/:findingId/workflow",
  "/repositories/:repoId/findings/:findingId/workflow/pull-request",
]

/** The index route is wired in `App.tsx` rather than the registry, so it is named here as "/". */
const INDEX_ROUTE = "/"

function declaredAddresses(): string[] {
  return [
    INDEX_ROUTE,
    ...ROUTES.map((route) => route.path),
    ...DESTINATIONS.map((destination) => destination.path),
  ]
}

describe("the skeleton migration ratchet", () => {
  it("accounts for every declared address exactly once", () => {
    const claimed = [...MIGRATED, ...PENDING].sort()
    const declared = declaredAddresses().sort()

    expect(claimed).toEqual(declared)
  })

  it("names no address twice", () => {
    const claimed = [...MIGRATED, ...PENDING]
    expect(new Set(claimed).size).toBe(claimed.length)
  })

  it("has migrated at least one screen, so the ratchet is not vacuous", () => {
    // Without this the lists could satisfy the union check with MIGRATED empty forever, and the
    // gate would report a migration that never started.
    expect(MIGRATED.length).toBeGreaterThan(0)
  })
})
