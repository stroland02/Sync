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
 */

import { Link } from "react-router"

import type { RiskRow } from "@/api/types"
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
import { bindingSurfaceHref, findingHref } from "@/lib/hrefs"
import { orAbsent } from "@/lib/format"

export function FindingsTable({
  repoId,
  rows,
}: {
  repoId: string
  rows: readonly RiskRow[]
}) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Severity</TableHead>
          {/* Rung sits ahead of the call site so it stays on screen at 1280px without a sideways
              scroll: the call site is the widest cell in this table — a path from a customer
              repository — and no fixture here is long enough to prove that on its own. */}
          <TableHead>Rung</TableHead>
          <TableHead>Call site</TableHead>
          <TableHead>Symbol</TableHead>
          <TableHead>Operation</TableHead>
          <TableHead>Change kind</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={row.finding_id}>
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
                aria-label={`Finding ${row.finding_id} at ${row.file} line ${row.line}`}
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
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
