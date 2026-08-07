/**
 * Every failure count Sync's telemetry has recorded for one repository.
 *
 * `error_count` has no denominator here — it is a numerator, not a rate, `ObservedErrorWindow`'s
 * own grain note. This table renders it as-is: comparing one window against another is what
 * these rows support unaided, and computing a rate from them would need `observed_call`, a
 * different table drawn from a different sample, joined at a granularity nothing here attempts.
 * A shape drift is not an error and this table is not a verdict — no colour, no threshold.
 */

import type { ObservedErrorWindowRow } from "@/api/types"
import { RungBadge } from "@/components/provenance"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/data-table"
import { formatTimestamp, orAbsent } from "@/lib/format"
import { Formatted } from "@/components/status"

export function ErrorWindowsTable({ windows }: { windows: ObservedErrorWindowRow[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Rung</TableHead>
          <TableHead>Operation</TableHead>
          <TableHead>Status class</TableHead>
          <TableHead>Source</TableHead>
          <TableHead>Window</TableHead>
          <TableHead>Errors</TableHead>
          <TableHead>Issues</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {windows.map((window, index) => (
          <TableRow
            key={`${window.vendor_id}-${window.operation_id}-${window.source}-${window.status_class}-${index}`}
          >
            <TableCell>
              <RungBadge rung={window.binding_rung} />
            </TableCell>
            <TableCell className="font-mono">
              {window.vendor_id} · {window.operation_id}
            </TableCell>
            <TableCell className="font-mono">
              <Formatted value={orAbsent(window.status_class)} />
            </TableCell>
            <TableCell>{window.source}</TableCell>
            <TableCell className="font-mono text-meta">
              <Formatted value={formatTimestamp(window.window_start)} /> →{" "}
              <Formatted value={formatTimestamp(window.window_end)} />
            </TableCell>
            <TableCell className="font-mono">{window.error_count.toLocaleString()}</TableCell>
            <TableCell className="font-mono">{window.issue_count.toLocaleString()}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
