/**
 * Switching workspace keeps the screen, and knows when it cannot.
 *
 * The owner reported switching as broken; the cause was that no switcher existed, and the part
 * with a wrong answer is this: which address the reader lands on. Scope is
 * `console-dev-loop.md`'s — a derivation, tested here rather than reviewed.
 */

import { describe, expect, it } from "vitest"

import { switchedPath } from "@/layouts/workspace-switcher"

describe("switching workspace", () => {
  it("keeps the screen a reader is on", () => {
    // The whole point: someone comparing Call sites across two codebases should not be dropped
    // on the Overview and made to navigate back.
    expect(switchedPath("/repositories/demo/call-sites", "org/two")).toBe(
      "/repositories/org%2Ftwo/call-sites",
    )
  })

  it("encodes a repository id containing a slash, because every real one has one", () => {
    // `org/one` unescaped matches a different route or none, which is the defect `lib/hrefs.ts`
    // exists to stop — and a naive string replace on the encoded path reintroduces it here.
    expect(switchedPath("/repositories/demo", "github.com/stroland02/Sync")).toBe(
      "/repositories/github.com%2Fstroland02%2FSync",
    )
  })

  it("switches from a workspace whose own id contains slashes", () => {
    expect(
      switchedPath("/repositories/github.com%2Fstroland02%2FSync/findings", "demo"),
    ).toBe("/repositories/demo/findings")
  })

  it("falls back to the Overview for a screen addressed by a subject the new workspace lacks", () => {
    // A finding id belongs to one workspace. Carrying it across lands on a 404 that reads as a
    // broken switcher rather than as a finding that is not there.
    expect(
      switchedPath("/repositories/demo/findings/f-91ac", "org/two"),
    ).toBe("/repositories/org%2Ftwo")
  })

  it("falls back to the Overview from an address no route declares", () => {
    expect(switchedPath("/nowhere/at/all", "demo")).toBe("/repositories/demo")
  })
})
