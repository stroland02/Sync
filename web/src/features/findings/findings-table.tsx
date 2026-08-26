/**
 * One workspace's open findings, as rows.
 *
 * **Extracted at the second use, not the third.** The vendor level and the workspace level render
 * the same six columns over the same `RiskRow`, and `CLAUDE.md` puts the extraction here rather
 * than after the two copies have drifted. The four `bindingSurfaceHref` copies `M14-W436` had to
 * chase down are what the other timing looks like.
 *
 * **The vendor comes from the row, never from the page.** The vendor screen could pass its own
 * `vendorId` and be right every time; a workspace-wide list holds several vendors at once and would
 * put every row's operation under whichever vendor the page happened to be about. `RiskRow.vendor`
 * is per row, so reading it there is correct at both levels and cannot be wrong at either.
 *
 * The rung is a column, not a decoration and not hideable — `CLAUDE.md`'s rule that every artifact
 * derived from a binding carries the rung it came from. A finding that cannot be attributed to a
 * rung cannot be fixed.
 *
 * **The eight columns and their order did not move when selection arrived**, and that is the point
 * of the two optional props. Six surfaces render this table; only the workspace Findings screen has
 * an inspector, so `onSelect` gates a ninth column after Solution and nothing else changes. The
 * name `Link` stays either way: a row keeps its direct route to the finding whether or not the
 * screen it is on can also open a drawer over it.
 */

import { Link } from "react-router"

import type { RiskRow, Ticket } from "@/api/types"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/data-table"
import { SeverityTag } from "@/components/tag"
import { RungBadge } from "@/components/provenance"
import { Formatted } from "@/components/status"
import { Button } from "@/components/ui/button"
import { TicketCell } from "@/features/tickets/ticket-cell"
import { bindingSurfaceHref, findingHref } from "@/lib/hrefs"
import { orAbsent } from "@/lib/format"

export function FindingsTable({
  repoId,
  rows,
  tickets,
  selectedId,
  onSelect,
  stickyHeader,
}: {
  repoId: string
  rows: readonly RiskRow[]
  /**
   * The workspace's tickets, fetched once by the page and null while that read is in flight.
   * Undefined means the surface has no solutions workflow — the fleet and vendor tables — and
   * the column itself stays off, not merely empty.
   */
  tickets?: readonly Ticket[] | null
  /** Which row the inspector is showing, when the surface has one. */
  selectedId?: string | null
  /**
   * Publishes the pressed row's id. Its absence is what keeps the Inspect column off the four
   * surfaces with no inspector — the same `tickets !== undefined` precedent one prop over, and
   * the reason the vendor level and the inspector's own constituent list render today's table
   * unchanged.
   */
  onSelect?: (findingId: string) => void
  /**
   * Pins the head while the rows scroll. A fact about the *surface* rather than about the table:
   * only a locked screen has a bounded scroller for a head to stick inside, and the four flowing
   * consumers would get a head stuck to the page. Separate from `onSelect` on purpose — a screen
   * could reasonably want one without the other.
   */
  stickyHeader?: boolean
}) {
  return (
    <Table>
      <TableHeader sticky={stickyHeader}>
        <TableRow>
          {/* The name leads: M15 Task 6. A 32-character hex id is correct for a key and useless
              in a sentence, and a reader who wants to raise one of these with a colleague has to
              be able to say which. Derived in the payload so this table, the CLI and a pull-request
              body cannot disagree about what a finding is called. */}
          <TableHead>Finding</TableHead>
          <TableHead>Severity</TableHead>
          {/* Rung sits ahead of the call site so it stays on screen at 1280px without a sideways
              scroll: the call site is the widest cell in this table — a path from a customer
              repository — and no fixture here is long enough to prove that on its own. */}
          <TableHead>Rung</TableHead>
          <TableHead>Call site</TableHead>
          <TableHead>Symbol</TableHead>
          <TableHead>Operation</TableHead>
          <TableHead>Change kind</TableHead>
          {tickets !== undefined && <TableHead>Solution</TableHead>}
          {onSelect !== undefined && <TableHead className="text-right">Inspect</TableHead>}
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow
            key={row.finding_id}
            data-state={onSelect !== undefined && row.finding_id === selectedId ? "selected" : undefined}
            onClick={onSelect === undefined ? undefined : () => onSelect(row.finding_id)}
            className={onSelect === undefined ? undefined : "cursor-pointer"}
          >
            <TableCell className="font-mono text-meta">
              <Link
                to={findingHref(repoId, row.finding_id)}
                className="underline underline-offset-2"
                aria-label={`Finding ${row.name}, ${row.file} line ${row.line}`}
                onClick={(event) => event.stopPropagation()}
              >
                {row.name}
              </Link>
            </TableCell>
            <TableCell>
              <SeverityTag severity={row.severity} />
            </TableCell>
            <TableCell>
              <RungBadge rung={row.binding_source} />
            </TableCell>
            <TableCell className="font-mono">
              <Link
                to={findingHref(repoId, row.finding_id)}
                className="underline underline-offset-2"
                onClick={(event) => event.stopPropagation()}
              >
                {row.file}:{row.line}
              </Link>
            </TableCell>
            <TableCell className="font-mono">
              <Formatted value={orAbsent(row.symbol)} />
            </TableCell>
            <TableCell className="font-mono">
              {row.operation ? (
                <Link
                  to={bindingSurfaceHref(repoId, row.vendor, row.operation)}
                  className="underline underline-offset-2"
                  onClick={(event) => event.stopPropagation()}
                >
                  {row.operation}
                </Link>
              ) : (
                <Formatted value={orAbsent(row.operation)} />
              )}
            </TableCell>
            <TableCell>
              <Formatted value={orAbsent(row.change_kind)} />
            </TableCell>
            {tickets !== undefined && (
              <TableCell>
                <TicketCell repoId={repoId} findingId={row.finding_id} tickets={tickets} />
              </TableCell>
            )}
            {onSelect !== undefined && (
              <TableCell className="text-right">
                {/* The keyboard-reachable control. The row's `onClick` is a pointer convenience
                    and carries no affordance of its own. */}
                <Button
                  size="sm"
                  variant="outline"
                  aria-pressed={row.finding_id === selectedId}
                  onClick={(event) => {
                    event.stopPropagation()
                    onSelect(row.finding_id)
                  }}
                >
                  Inspect
                </Button>
              </TableCell>
            )}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
