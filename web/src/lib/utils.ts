import { clsx, type ClassValue } from "clsx"
import { extendTailwindMerge } from "tailwind-merge"

/**
 * `tailwind-merge`'s default config only recognises Tailwind's stock t-shirt sizes
 * (`text-sm`, `text-lg`, …) as font-size utilities; anything else in a `text-*` position
 * falls through to its text-*colour* group, which accepts any name at all. Every custom
 * step on DESIGN.md's six-step type scale (`--text-meta` … `--text-figure`) is exactly
 * such a name, so plain `twMerge` mistook `text-emphasis` and `text-critical-ink` for two
 * values of the same property and silently dropped one — the status ink, in every call
 * site that also passed a size class through `className`. Listing the scale here is what
 * tells the merge they are different properties, not a preference.
 */
const twMerge = extendTailwindMerge({
  extend: {
    theme: {
      text: ["meta", "body", "emphasis", "section", "page", "figure"],
    },
  },
})

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
