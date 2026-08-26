/**
 * One block of a finding-detail pane: its name at the section step, its argument behind the ⓘ.
 *
 * Both panes of the split render four to six of these, which is the second use — and the shape is
 * the 2026-08-19 prose ruling made structural: the heading is the claim and stays on screen, the
 * paragraph explaining why the distinction exists moves into the hint. A section whose *nothing*
 * needs naming says so in its body, in the fewest honest words, and never in the hint.
 */

import type { ReactNode } from "react"

import { InfoHint } from "@/components/info-hint"

export function DetailSection({
  heading,
  hintLabel,
  hint,
  children,
}: {
  heading: string
  /** The accessible name of the disclosure — "About the captured window". */
  hintLabel?: string
  hint?: ReactNode
  children: ReactNode
}) {
  return (
    <section className="flex min-w-0 flex-col gap-row">
      <div className="flex min-w-0 items-center gap-field">
        <h3 className="min-w-0 text-section">{heading}</h3>
        {hint !== undefined && hintLabel !== undefined && (
          <InfoHint label={hintLabel}>{hint}</InfoHint>
        )}
      </div>
      {children}
    </section>
  )
}
