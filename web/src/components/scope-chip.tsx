/**
 * What a figure was counted over, as a chip beside the panel's title.
 *
 * **Owner ruling, 2026-08-19.** Scope used to be a bordered paragraph — Runs carried five lines
 * saying its figures are fleet-wide rather than this workspace's, and Solutions and Corpus repeated
 * it. Load-bearing prose, visually heavy, and repeated three times, which is the shape of fact that
 * eventually disagrees with itself.
 *
 * The chip is the claim in two words; the ⓘ carries why. That is the amended rule exactly: a
 * reader who never hovers still sees *all workspaces* and does not mistake it for their own.
 *
 * **Monochrome, and a word rather than a colour.** Scope is not a status — a fleet-wide figure is
 * not worse than a scoped one, it is a different question — so this takes the chip anatomy
 * `RungBadge` spells and none of the four reserved status hues.
 */

import type { ReactNode } from "react"

import { InfoHint } from "@/components/info-hint"

export function ScopeChip({
  scope,
  children,
}: {
  /** Two or three words. "all workspaces", "this workspace", "before filtering". */
  scope: string
  /** Why the scope is what it is, and what it would take to narrow it. */
  children: ReactNode
}) {
  return (
    <span className="inline-flex shrink-0 items-center gap-field">
      <span className="furniture rounded-control border border-line px-field py-field text-meta text-ink-muted">
        {scope}
      </span>
      <InfoHint label={`About the ${scope} scope`}>{children}</InfoHint>
    </span>
  )
}

/**
 * The one written in three places, so it cannot drift into three versions.
 *
 * `migration_outcome` stores no `repo_id` — the schema decision that makes the corpus safe to
 * aggregate across customers — so there is no column to filter on and no narrower answer being
 * withheld. Every panel reading that table says the same thing by importing this.
 */
export const CORPUS_SCOPE = (
  <>
    Counted across every workspace, not this one. The corpus table stores no repository —
    deliberately, because that is what makes it safe to aggregate across customers — so there is no
    column to narrow on and no narrower answer being withheld from you.
  </>
)
