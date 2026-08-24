/**
 * One primitive substrate, asserted rather than intended.
 *
 * Owner ruling: shadcn is the single substrate, retired phased with the chassis. Two trees
 * shipped a `Button`, a `Card`, an `Input` and a `Table` at once, which is two answers to what a
 * button looks like -- and the shadcn one carries focus-ring work measured against the 3:1
 * non-text contrast floor that the vendored copy never had.
 *
 * A name in both places is the whole defect, so that is what this checks. The vendored tree keeps
 * the primitives shadcn does not offer -- the sidebar, the sheet, the scroll areas -- and those
 * are not duplicates.
 */

import { describe, expect, it } from "vitest"

// `import.meta.glob` rather than `readdirSync`: the console's tsconfig ships no Node types, and
// adding them so one test can read a directory would widen the type surface of every file in the
// tree for a check that Vite already answers at build time.
const SHADCN = import.meta.glob("./ui/*.tsx")
const VENDORED = import.meta.glob("../vendor/supabase/ui/*.tsx")

function primitives(modules: Record<string, unknown>): string[] {
  return Object.keys(modules)
    .map((path) => path.split("/").pop()!.replace(/\.tsx$/, ""))
    .sort()
}

describe("the primitive substrate", () => {
  it("declares no primitive in two places", () => {
    const shadcn = new Set(primitives(SHADCN))
    const duplicated = primitives(VENDORED).filter((name) => shadcn.has(name))

    expect(duplicated).toEqual([])
  })

  it("has something in both trees, so the check is not vacuous", () => {
    expect(primitives(SHADCN).length).toBeGreaterThan(0)
    expect(primitives(VENDORED).length).toBeGreaterThan(0)
  })
})
