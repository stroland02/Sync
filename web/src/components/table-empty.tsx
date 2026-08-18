/**
 * A table with no rows, which keeps its column headers (decision 61).
 *
 * **The headers staying is the whole point.** A panel that replaces the table tells a reader
 * there is nothing; a table that keeps its headers tells them what a row *would* be. "The shape
 * of the data is legible before there is data, so a reader learns what a finding is from a
 * screen that has none."
 *
 * **It states what was checked, not merely that there is nothing.** A read that happened and
 * returned no row is a measurement; a read that never happened is not, and the two must not
 * render alike. That distinction is the caller's to make, because only the caller knows which
 * one it is holding — this component gives it somewhere to say so at full length.
 *
 * **`action` is optional and must never be invented.** Decision 61 asks for one next action, and
 * a table with no honest next step says nothing rather than offering a control that leads
 * nowhere.
 *
 * Sentences arriving here are not shortened to fit the cell. Decision 63 draws that line
 * explicitly: an existing on-screen sentence may be restyled and may not be trimmed, collapsed
 * behind a disclosure, or moved into a tooltip.
 */

import type { ReactNode } from "react"

import { TableBody, TableCell, TableRow } from "@/components/data-table"

export interface TableEmptyStateProps {
  /** How many columns the header declares, so the sentence spans all of them. */
  columns: number
  headline: string
  /** What was checked and what was found. Full length: this is not a tooltip. */
  detail: ReactNode
  /** One next step, when an honest one exists. Omitted otherwise. */
  action?: ReactNode
}

export function TableEmptyState({ columns, headline, detail, action }: TableEmptyStateProps) {
  return (
    <TableBody>
      <TableRow>
        <TableCell colSpan={columns} className="py-section">
          <div className="flex max-w-prose flex-col gap-field">
            <p className="text-emphasis font-medium text-ink">{headline}</p>
            <p className="text-body text-ink-muted leading-relaxed">{detail}</p>
            {action !== undefined && <div className="pt-field">{action}</div>}
          </div>
        </TableCell>
      </TableRow>
    </TableBody>
  )
}
