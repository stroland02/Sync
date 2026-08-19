/**
 * Which workspace the chassis attaches to. The wrong answer here opens somebody else's codebase.
 */

import { describe, expect, it } from "vitest"

import { activeWorkspace } from "@/layouts/active-workspace"

const KNOWN = ["demo", "github.com/stroland02/Sync"]

describe("the active workspace", () => {
  it("takes the address over anything remembered", () => {
    // The rule that matters most: a shared link must open the codebase it names. A remembered
    // value winning here would open the recipient's own workspace instead, silently.
    expect(activeWorkspace("demo", "github.com/stroland02/Sync", KNOWN)).toBe("demo")
  })

  it("inherits the remembered workspace where the address names none", () => {
    // The owner's report: opening Settings blanked the badge and made every repository-scoped
    // rail row unlinkable, because `/settings` binds no repoId.
    expect(activeWorkspace(undefined, "demo", KNOWN)).toBe("demo")
  })

  it("discards a remembered workspace the graph no longer holds", () => {
    // A codebase can be removed between sessions. A badge naming one that is gone is a claim
    // nothing supports, and every scoped link built from it would 404.
    expect(activeWorkspace(undefined, "a-codebase-since-removed", KNOWN)).toBeNull()
  })

  it("falls back to the only codebase when there is exactly one", () => {
    expect(activeWorkspace(undefined, null, ["demo"])).toBe("demo")
  })

  it("attaches to nothing when several exist and none was chosen", () => {
    // Guessing here would make the first indexed repository quietly authoritative.
    expect(activeWorkspace(undefined, null, KNOWN)).toBeNull()
  })
})
