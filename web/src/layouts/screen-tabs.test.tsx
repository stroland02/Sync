import { describe, expect, it } from "vitest"

import { SIBLING_GROUPS, groupFor } from "@/layouts/screen-tabs"
import { ROUTES } from "@/lib/routes"

describe("the sibling-screen groups", () => {
  it("names only addresses the registry declares", () => {
    // The defect this replaces: six screens each hardcoded a strip naming the OTHER screens, so a
    // renamed route left a dead tab behind on whichever of the six nobody edited.
    const declared = new Set(ROUTES.map((route) => route.path))
    const named = SIBLING_GROUPS.flatMap((group) => group.members.map((member) => member.path))

    expect(named.filter((path) => !declared.has(path))).toEqual([])
  })

  it("puts every named address in exactly one group", () => {
    const named = SIBLING_GROUPS.flatMap((group) => group.members.map((member) => member.path))
    expect(new Set(named).size).toBe(named.length)
  })

  it("matches the address a screen IS, never one it starts with", () => {
    // `/findings/:findingId` is a detail screen under Findings, not a third tab beside it. A
    // prefix match would render the strip there and mark neither tab current.
    expect(groupFor("/repositories/org%2Fone/findings", "org/one")?.label).toBe("Findings")
    expect(groupFor("/repositories/org%2Fone/findings/abc123", "org/one")).toBeNull()
  })

  it("renders no strip on a screen with no siblings", () => {
    expect(groupFor("/repositories/org%2Fone/runs", "org/one")).toBeNull()
  })

  it("renders no strip where no workspace is bound", () => {
    expect(groupFor("/settings", null)).toBeNull()
  })

  it("encodes the workspace, so a slash in a repository name stays one segment", () => {
    const group = groupFor("/repositories/org%2Fone/vendors", "org/one")
    expect(group?.label).toBe("Vendors")
  })
})
