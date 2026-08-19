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
 * **There is a decline reason now, and this paragraph used to say there could not be.** It read:
 * "nothing in Sync records an intake attempt, only its result", and a column blank on every row
 * would have read as "no adapter has ever declined" — a claim nothing measured. `intake_attempt`
 * records the attempt, so "Last asked" carries the date, the outcome and the reason, drawn from
 * the closed vocabulary `sync.signals.intake_attempt` owns. Closed rather than free text is what
 * makes it aggregatable at all; a promise to learn from failures needs a schema that can answer
 * the question.
 *
 * The null rule above still governs it, one step further out: a row with no attempt says **no
 * attempt recorded**, never "never asked". The record began when the table did, so its silence is
 * a limit of the record rather than a fact about the adapter.
 */

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/data-table"
import { TableEmptyState } from "@/components/table-empty"
import { Absent, Formatted } from "@/components/status"
import type { AdapterRow } from "@/api/types"
import { formatTimestamp } from "@/lib/format"
import { VendorMark } from "@/features/vendors/vendor-mark"

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


/**
 * When the adapter was last asked, and what came back.
 *
 * **This is the column `AdapterRow.last_change_at` says it is not.** Until `intake_attempt`
 * landed, an adapter running hourly and finding nothing and an adapter nobody had run looked
 * identical on this screen — both showed an old newest-change date and no other evidence.
 *
 * **A null is not "never asked".** The attempt record began when the table did, so no row means
 * this screen holds no record of an attempt: a limit of the record, not a fact about the adapter.
 * The wording says which, because the stronger sentence is the one a reader would supply.
 *
 * The outcome travels as a word, never a colour: `declined` is the ordinary state of an adapter
 * asked about a spec that has not moved, and rendering it in a status hue would make routine
 * quiet look like a fault.
 */
function LastAsked({ adapter }: { adapter: AdapterRow }) {
  if (adapter.last_attempt_at === null) {
    return <Absent>no attempt recorded</Absent>
  }
  return (
    <span className="flex flex-col gap-field">
      <Formatted value={formatTimestamp(adapter.last_attempt_at)} />
      <span className="text-meta text-muted-foreground">
        {adapter.last_attempt_outcome}
        {adapter.last_attempt_reason !== null && <> · {adapter.last_attempt_reason}</>}
      </span>
    </span>
  )
}

export function AdapterTable({ adapters }: { adapters: AdapterRow[] }) {
  return (
    <>
      <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Vendor</TableHead>
          <TableHead>Served by</TableHead>
          <TableHead>Reads</TableHead>
          <TableHead>Changes</TableHead>
          <TableHead>Operations</TableHead>
          <TableHead>Newest change</TableHead>
          {/* Two columns, two questions. "Newest change" is when the adapter last had something
              to say; "Last asked" is when it was last asked. A healthy, quiet adapter has a
              recent second and an old first, and until `intake_attempt` landed those were
              indistinguishable -- which is the limit this table's own note used to state. */}
          <TableHead>Last asked</TableHead>
          <TableHead>Intake sources</TableHead>
        </TableRow>
      </TableHeader>
      {adapters.length === 0 ? (
        <TableEmptyState
          columns={8}
          headline="No adapter is registered, and the graph holds no vendor history"
          detail={
            "Both halves of this table are empty, which is a configured state rather than a " +
            "failure: a deployment registers adapters in its vendor configuration, and a vendor " +
            "appears here from history only once a scan has written a change against it."
          }
        />
      ) : (
      <TableBody>
        {adapters.map((adapter) => (
          <TableRow key={adapter.vendor_id}>
            <TableCell className="font-mono">
              <span className="flex items-center gap-row">
                <VendorMark vendorId={adapter.vendor_id} />
                {adapter.vendor_id}
              </span>
            </TableCell>
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
                  <LastAsked adapter={adapter} />
                </TableCell>
                <TableCell className="font-mono text-meta">
                  {adapter.sources?.join(", ")}
                </TableCell>
              </>
            ) : (
              <>
                {/* Three delivery columns collapse into the note; "Last asked" keeps its own
                    cell, in its own column, because it is the one fact an adapter that has
                    never delivered can still have — and it is precisely the fact that tells a
                    reader whether the silence has been tested. */}
                <TableCell colSpan={3} className="text-meta text-muted-foreground">
                  {NEVER_DELIVERED_NOTE}
                </TableCell>
                <TableCell className="font-mono text-meta">
                  <LastAsked adapter={adapter} />
                </TableCell>
                <TableCell />
              </>
            )}
          </TableRow>
        ))}
      </TableBody>
      )}
      </Table>

      <p className="text-meta text-ink-muted leading-relaxed">
        Showing all {adapters.length.toLocaleString()}{" "}
        {adapters.length === 1 ? "adapter" : "adapters"} this deployment registers. Not a page: the
        inventory is bounded by what an operator configured plus what the graph holds history for,
        so there is nothing behind this list.
      </p>
    </>
  )
}
