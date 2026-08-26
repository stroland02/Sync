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
    // Subject changed 2026-08-26, coverage did not. Runs used to be the example of a screen in no
    // group; the Runs rebuild sent its two corpus charts to Corpus and put Runs in the Solutions
    // group so a reader still has a path to them. Call sites is now the screen that stands alone,
    // and what is asserted is unchanged: a route in no group gets no strip rather than an empty one.
    expect(groupFor("/repositories/org%2Fone/call-sites", "org/one")).toBeNull()
  })

  it("puts Runs beside Solutions and Corpus, so the corpus charts stay reachable from the stream", () => {
    // The two charts Runs used to render below its table live on Corpus now — Runs is locked to
    // the viewport and a reader should not scroll a locked screen to reach them. A tab is the whole
    // path between the two, so its absence is a broken move rather than a missing decoration.
    const group = groupFor("/repositories/org%2Fone/runs", "org/one")
    expect(group?.label).toBe("Solutions")
    expect(group?.members.map((member) => member.label)).toEqual(["Solutions", "Runs", "Corpus"])
  })

  it("renders no strip where no workspace is bound", () => {
    expect(groupFor("/settings", null)).toBeNull()
  })

  it("encodes the workspace, so a slash in a repository name stays one segment", () => {
    const group = groupFor("/repositories/org%2Fone/vendors", "org/one")
    expect(group?.label).toBe("Vendors")
  })
})
