/**
 * The console's own screens use the named type scale, not Tailwind's default one.
 *
 * Owner ruling: terminal density. `index.css` declares a six-step scale named for what each step
 * is -- `meta`, `body`, `section`, `page`, `figure`, `display` -- against Tailwind's `text-sm`
 * through `text-9xl`, which name sizes rather than roles. Two scales in one tree means a screen
 * can be built in either, and the density ruling then holds for half the console.
 *
 * Measured when this landed: no file the console authors used a default-scale size. The vendored
 * and shadcn primitives do, and are exempt -- they ship with those classes, and re-authoring a
 * working primitive to change a class name is the polish that competes with the milestone.
 */

import { describe, expect, it } from "vitest"

const OURS = import.meta.glob("../{features,layouts,components}/**/*.tsx", {
  eager: true,
  query: "?raw",
  import: "default",
}) as Record<string, string>

/** Sizes that name a size. The scale that replaced them names a role instead. */
const DEFAULT_SCALE = [
  "text-xs",
  "text-sm",
  "text-base",
  "text-lg",
  "text-xl",
  "text-2xl",
  "text-3xl",
  "text-4xl",
  "text-5xl",
]

function offendersIn(path: string, source: string): string[] {
  return DEFAULT_SCALE.filter((size) =>
    // Word boundaries, built by concatenation. The first form spelled its character class with
    // one backslash too few, so it matched a literal `s` rather than whitespace -- and the guard
    // stayed green when a real `text-2xl` was planted in a screen to check it could fail.
    new RegExp("\\b" + size + "\\b").test(source)
  ).map((size) => path + ": " + size)
}

describe("the type scale", () => {
  it("is the named one everywhere the console authors a screen", () => {
    const offenders = Object.entries(OURS)
      // The primitives ship with Tailwind's own classes and are not ours to re-author.
      .filter(([path]) => !path.includes("/ui/") && !path.includes("/vendor/"))
      .flatMap(([path, source]) => offendersIn(path, source))

    expect(offenders).toEqual([])
  })

  it("reads some files, so the check is not vacuous", () => {
    expect(Object.keys(OURS).length).toBeGreaterThan(20)
  })

  it("can fail, which the first form of it could not", () => {
    // The regex is the part that was wrong, so the regex is what this exercises directly.
    expect(offendersIn("screen.tsx", '<h1 className="text-2xl text-ink">')).toEqual([
      "screen.tsx: text-2xl",
    ])
  })
})
