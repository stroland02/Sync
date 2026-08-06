/**
 * Every observed call Sync's telemetry has recorded for one repository.
 *
 * A row here proves a call site was exercised — the code ran, at least once, against this
 * vendor. It does not prove the binding correlating it to an operation is correct: that is
 * exactly what `binding_rung` says, `"observed"` for a correlation that ran or `"unresolved"`
 * for a request nothing could attribute. Neither reading is a verdict; `RungBadge` carries
 * the distinction rather than a colour, matching every other rung in this console.
 */

import type { ObservedCallRow } from "@/api/types"
import { RungBadge } from "@/components/provenance"
import { Formatted } from "@/components/status"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { formatTimestamp, orAbsent } from "@/lib/format"

function describeOperation(row: ObservedCallRow): string {
  return row.operation_id === "" ? row.vendor_id : `${row.vendor_id} · ${row.operation_id}`
}

export function ObservedCallsTable({ calls }: { calls: ObservedCallRow[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Rung</TableHead>
          <TableHead>Operation</TableHead>
          <TableHead>Method</TableHead>
          <TableHead>Trace</TableHead>
          <TableHead>Server</TableHead>
          <TableHead>URL template</TableHead>
          <TableHead>Calls</TableHead>
          <TableHead>Distinct targets</TableHead>
          <TableHead>Repeated</TableHead>
          <TableHead>Max resend</TableHead>
          <TableHead>Errors</TableHead>
          <TableHead>Observed</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {calls.map((call, index) => (
          <TableRow key={`${call.trace_id}-${call.vendor_id}-${call.operation_id}-${index}`}>
            <TableCell>
              <RungBadge rung={call.binding_rung} />
            </TableCell>
            <TableCell className="font-mono">{describeOperation(call)}</TableCell>
            <TableCell className="font-mono uppercase">
              <Formatted value={orAbsent(call.http_method)} />
            </TableCell>
            <TableCell className="font-mono text-meta">{call.trace_id}</TableCell>
            <TableCell className="font-mono">
              <Formatted value={orAbsent(call.server_address)} />
            </TableCell>
            <TableCell className="font-mono">
              <Formatted value={orAbsent(call.url_template)} />
            </TableCell>
            <TableCell className="font-mono">{call.call_count.toLocaleString()}</TableCell>
            <TableCell className="font-mono">
              {call.distinct_targets.toLocaleString()}
            </TableCell>
            <TableCell className="font-mono">{call.repeated_calls.toLocaleString()}</TableCell>
            <TableCell className="font-mono">
              {call.max_resend_count.toLocaleString()}
            </TableCell>
            <TableCell className="font-mono">{call.error_count.toLocaleString()}</TableCell>
            <TableCell className="font-mono text-meta">
              <Formatted value={formatTimestamp(call.first_seen)} /> →{" "}
              <Formatted value={formatTimestamp(call.last_seen)} />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
