/**
 * Every adapter this deployment registers, and what each has ever delivered.
 *
 * The console answers questions about vendors on nine screens and answers nothing about the
 * adapters behind them. A vendor Sync watches and finds nothing wrong with, and a vendor whose
 * adapter has never once been reached, render identically everywhere else — as a quiet row.
 *
 * **The one rule this file exists to hold: null is not zero.** `sync/dashboard/adapters.py`
 * answers `null` for an adapter the graph holds no `vendor_change` row for, and a number for one
 * it does. Zero is a measurement — Sync read the vendor's specification and had nothing to say.
 * Null is the absence of one. A cell that prints `0` for both is the failure this screen was built
 * to remove, and it is one `?? 0` away at all times, which is why the whole row switches on the
 * distinction rather than each cell defending itself.
 *
 * There is no decline column. The mock draws one — a catalogue that served an HTML error page —
 * and no field behind it exists: nothing in Sync records an intake attempt, only its result. A
 * column blank on every row would read as "no adapter has ever declined", which nothing measured.
 */

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/data-table"
import { EmptyState } from "@/components/states"
import { Formatted } from "@/components/status"
import type { AdapterRow } from "@/api/types"
import { formatTimestamp } from "@/lib/format"

/**
 * What a row says instead of a count.
 *
 * One sentence rather than a dash, because a dash in a numeric column reads as zero to anybody
 * scanning and the difference between those two readings is this screen's whole subject.
 */
export const NEVER_DELIVERED_NOTE = "Nothing received from this adapter yet"

/** What registered an adapter, in the operator's words rather than the registry's key. */
const KIND_NOTE: Record<AdapterRow["kind"], string> = {
  coded: "an adapter written in Sync",
  generated: "a manifest the vendor's SDK repository commits",
  mcp: "captures of a watched MCP server",
  unregistered: "history from an adapter this deployment no longer registers",
}

function hasDelivered(adapter: AdapterRow): boolean {
  return adapter.changes !== null
}

export function AdapterTable({ adapters }: { adapters: AdapterRow[] }) {
  if (adapters.length === 0) {
    return (
      <EmptyState
        headline="No adapter is registered, and the graph holds no vendor history"
        detail={
          "Both halves of this table are empty, which is a configured state rather than a " +
          "failure: a deployment registers adapters in its vendor configuration, and a vendor " +
          "appears here from history only once a scan has written a change against it."
        }
      />
    )
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Vendor</TableHead>
          <TableHead>Served by</TableHead>
          <TableHead>Reads</TableHead>
          <TableHead>Changes</TableHead>
          <TableHead>Operations</TableHead>
          <TableHead>Newest change</TableHead>
          <TableHead>Intake sources</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {adapters.map((adapter) => (
          <TableRow key={adapter.vendor_id}>
            <TableCell className="font-mono">{adapter.vendor_id}</TableCell>
            <TableCell>
              <span className="font-mono">{adapter.kind}</span>
              <div className="mt-field text-meta text-muted-foreground">
                {KIND_NOTE[adapter.kind]}
              </div>
            </TableCell>
            <TableCell className="font-mono text-meta">
              <Formatted value={adapter.source} />
            </TableCell>
            {hasDelivered(adapter) ? (
              <>
                <TableCell className="font-mono">{adapter.changes}</TableCell>
                <TableCell className="font-mono">{adapter.operations}</TableCell>
                <TableCell className="font-mono text-meta">
                  {/* Named for what it is. This is the newest row the graph holds, not the last
                      time the adapter was asked — an adapter polled hourly that has found nothing
                      new for a week reports last week, and no field here would say otherwise. */}
                  <Formatted value={formatTimestamp(adapter.last_change_at)} />
                </TableCell>
                <TableCell className="font-mono text-meta">
                  {adapter.sources?.join(", ")}
                </TableCell>
              </>
            ) : (
              <TableCell colSpan={4} className="text-meta text-muted-foreground">
                {NEVER_DELIVERED_NOTE}
              </TableCell>
            )}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
