/**
 * The route registry declares no `question`.
 *
 * Owner ruling: the field is deleted entirely, and the palette shows label and path grouped by
 * workflow stage instead. It existed for nine routes, grew to twenty-two, and had exactly one
 * renderer left -- the door rows on the Overview -- by the time every screen carried its own
 * heading through `ScreenFrame`.
 *
 * Asserted rather than described, because a deleted field is one line away from coming back the
 * next time somebody wants a subtitle.
 */

import { describe, expect, it } from "vitest"

import { DESTINATIONS, ROUTES } from "@/lib/routes"

describe("the route registry after the question field", () => {
  it("declares no question on any route", () => {
    const carrying = [...ROUTES, ...DESTINATIONS]
      .filter((entry) => "question" in entry)
      .map((entry) => entry.path)

    expect(carrying).toEqual([])
  })

  it("still declares a label and a path for every entry, which is what replaced it", () => {
    for (const entry of [...ROUTES, ...DESTINATIONS]) {
      expect(entry.path.startsWith("/")).toBe(true)
      expect(entry.label.length).toBeGreaterThan(0)
    }
  })
})
