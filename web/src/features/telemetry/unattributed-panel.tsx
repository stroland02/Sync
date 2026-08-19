/**
 * The gap the telemetry cannot see past: traffic nothing could attribute to an operation.
 *
 * Its own panel by the owner's ruling (2026-08-19) because the gap is itself a live signal —
 * an unresolved row is a request that reached a vendor without the graph being able to say
 * which operation, so every measurement above it silently excludes this traffic. Pooling these
 * rows into the rollup would average a correlation gap into a measurement; hiding them would
 * render the gap as coverage.
 *
 * An empty panel renders nothing: no unresolved row is the good state, and a card announcing
 * the absence of a gap would be a claim about traffic that may simply not have been watched.
 */

import type { TrafficRollupRow } from "@/api/types"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/data-table"
import { InfoHint } from "@/components/info-hint"
import { MetricPanel } from "@/components/metric-panel"
import { formatTimestamp } from "@/lib/format"

export function UnattributedPanel({ unattributed }: { unattributed: TrafficRollupRow[] }) {
  if (unattributed.length === 0) return null

  return (
    <MetricPanel
      label="Unattributed traffic"
      hint={
        <InfoHint label="About unattributed traffic">
          Requests the collector saw but nothing could correlate to a vendor operation — either
          the adapter for that vendor has no request map, or the URL matched nothing it knows.
          These rows keep no path at all (the observation boundary discards anything that could
          identify a customer), so fixing the correlation later means re-ingesting, not
          reinterpreting. Settings → Adapters says what each adapter can correlate.
        </InfoHint>
      }
      caption="Traffic recorded at the unresolved rung — excluded from every measurement above, because a correlation gap is not a measurement."
    >
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Method · host</TableHead>
            <TableHead>Vendor</TableHead>
            <TableHead>Requests</TableHead>
            <TableHead>Last seen</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {unattributed.map((row) => (
            <TableRow key={`${row.vendor_id}:${row.server_address}:${row.http_method}`}>
              <TableCell className="font-mono text-meta">
                {row.http_method.toUpperCase()} {row.server_address}
              </TableCell>
              <TableCell className="font-mono">{row.vendor_id}</TableCell>
              <TableCell className="font-mono">{row.requests.toLocaleString()}</TableCell>
              <TableCell className="text-meta text-ink-muted">
                {formatTimestamp(row.last_seen)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </MetricPanel>
  )
}
