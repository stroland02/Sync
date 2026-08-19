/**
 * Traffic by operation: the live-signals page's core table (owner ruling 2026-08-19).
 *
 * One row per operation the correlated traffic names, pooled across every unit of work held —
 * the grain `StatusRateDetector` measures over, so a row here and a finding it raises can never
 * disagree about the population. The error figure is a sentence with its denominator in it,
 * never a bare percentage, and a row with unstatused spans says how many left the sample.
 *
 * The operation links into the Binding surface: the row says what traffic did, that page says
 * what the code binds — the join a reader makes when a rate looks wrong.
 */

import { Link } from "react-router"

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
import { bindingSurfaceHref } from "@/lib/hrefs"
import { formatTimestamp } from "@/lib/format"
import { rateSentence } from "@/features/telemetry/traffic"

export function TrafficRollupTable({
  repoId,
  traffic,
}: {
  repoId: string
  traffic: TrafficRollupRow[]
}) {
  return (
    <MetricPanel
      label="Traffic by operation"
      hint={
        <InfoHint label="About traffic by operation">
          <p>
            What the Observe stage recorded, pooled per operation across every unit of work the
            graph currently holds. A request is a span that carried a status; spans without one
            leave the numerator and the denominator both and are counted in their own column, so
            a rate over a shrunken sample can be discounted rather than trusted.
          </p>
          <p>
            One operation reached through two hosts is two rows — a sandbox failing beside
            healthy production traffic must not average into one figure.
          </p>
        </InfoHint>
      }
      caption="Correlated traffic only; requests nothing could attribute are in the unattributed panel below."
    >
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Operation</TableHead>
            <TableHead>Method · host</TableHead>
            <TableHead>Requests</TableHead>
            <TableHead>Errors</TableHead>
            <TableHead>No status</TableHead>
            <TableHead>Targets</TableHead>
            <TableHead>Last seen</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {traffic.map((row) => (
            <TableRow key={`${row.vendor_id}:${row.operation_id}:${row.server_address}:${row.http_method}`}>
              <TableCell className="font-mono">
                <Link
                  to={bindingSurfaceHref(repoId, row.vendor_id, row.operation_id)}
                  className="underline underline-offset-2"
                >
                  {row.operation_id}
                </Link>
                <span className="text-meta text-ink-muted"> · {row.vendor_id}</span>
              </TableCell>
              <TableCell className="font-mono text-meta">
                {row.http_method.toUpperCase()} {row.server_address}
              </TableCell>
              <TableCell className="font-mono">{row.requests.toLocaleString()}</TableCell>
              <TableCell className="text-meta">{rateSentence(row.errors, row.requests)}</TableCell>
              <TableCell className="font-mono">{row.unstatused.toLocaleString()}</TableCell>
              <TableCell className="font-mono">{row.distinct_targets.toLocaleString()}</TableCell>
              <TableCell className="text-meta text-ink-muted">
                {formatTimestamp(row.last_seen)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <p className="text-meta text-ink-muted leading-relaxed">
        Showing all {traffic.length.toLocaleString()} observed{" "}
        {traffic.length === 1 ? "operation" : "operations"}. The set is bounded by what traffic
        named, not paginated — and it covers whatever has been folded in since the last pipeline
        run, which is this table&rsquo;s whole retention.
      </p>
    </MetricPanel>
  )
}
