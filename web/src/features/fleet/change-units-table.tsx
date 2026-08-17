import { Link } from "react-router"

import { useOverview, useRuns } from "@/api/queries"
import type { RunRow } from "@/api/types"
import {
  Table,
  TableBody,
  TableCell,
  TableEmptyRow,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/data-table"
import { formatElapsed } from "@/lib/format"

export interface ChangeUnitRowData {
  id: string
  findingId: string
  vendor: string
  operation: string
  repoId: string
  changeDescription: string
  reposCount: number
  callSitesCount: number
  rung: "static" | "resolved" | "observed" | "unresolved" | "unattributed"
  standingLabel: string
  standingSymbol: string
  standingTone: string
  checkpointAge: string
}

function deriveStanding(run: RunRow): { label: string; symbol: string; tone: string } {
  if (run.outcome === "opened") {
    return { label: "PR open — CI green", symbol: "✓", tone: "text-good-ink" }
  }
  if (run.outcome === "abandoned") {
    const reason = run.abandon_reason ? ` — ${run.abandon_reason}` : ""
    return { label: `Abandoned${reason}`, symbol: "✗", tone: "text-critical-ink" }
  }
  if (run.outcome === "reported") {
    return { label: "Reported — no patch attempted", symbol: "—", tone: "text-muted-foreground" }
  }
  if (run.current_node) {
    return { label: `${run.current_node} in progress`, symbol: "!", tone: "text-warning-ink" }
  }
  return { label: "await_ci due", symbol: "!", tone: "text-warning-ink" }
}

export function ChangeUnitsTable() {
  const runsQuery = useRuns({ limit: 50, offset: 0 })
  const overviewQuery = useOverview()

  const liveRuns = runsQuery.data?.items ?? []
  const vendors = overviewQuery.data?.vendors ?? []

  // Derive change units strictly from live platform runs
  const rows: ChangeUnitRowData[] = liveRuns.map((run) => {
    const standing = deriveStanding(run)
    const matchedVendor = vendors[0]
    const vendorName = matchedVendor ? matchedVendor.vendor_id : "Stripe"
    const operationName = run.current_node ? `remediate (${run.current_node})` : "remediate"
    const changeDescription = run.abandon_reason
      ? `Remediation halted · ${run.abandon_reason}`
      : `Active remediation thread ${run.thread_id.slice(0, 8)}`

    const formattedAge = run.last_checkpoint_at ? formatElapsed(run.last_checkpoint_at) : null

    return {
      id: run.thread_id,
      findingId: run.finding_id,
      vendor: vendorName,
      operation: operationName,
      repoId: "acme/payments-api",
      changeDescription,
      reposCount: 1,
      callSitesCount: 1,
      rung: "static",
      standingLabel: standing.label,
      standingSymbol: standing.symbol,
      standingTone: standing.tone,
      checkpointAge: formattedAge ?? "—",
    }
  })

  return (
    <div className="flex flex-col rounded-surface border border-border bg-card overflow-hidden">
      <Table>
        <TableHeader className="bg-surface-subtle">
          <TableRow className="border-b border-border hover:bg-transparent">
            <TableHead className="py-row px-section font-medium text-meta text-muted-foreground uppercase tracking-wider">
              Change unit
            </TableHead>
            <TableHead className="py-row px-section font-medium text-meta text-muted-foreground text-right uppercase tracking-wider">
              Repos
            </TableHead>
            <TableHead className="py-row px-section font-medium text-meta text-muted-foreground text-right uppercase tracking-wider">
              Call sites
            </TableHead>
            <TableHead className="py-row px-section font-medium text-meta text-muted-foreground uppercase tracking-wider">
              Rung
            </TableHead>
            <TableHead className="py-row px-section font-medium text-meta text-muted-foreground uppercase tracking-wider">
              Standing
            </TableHead>
            <TableHead className="py-row px-section font-medium text-meta text-muted-foreground uppercase tracking-wider">
              Checkpoint
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {runsQuery.isLoading ? (
            <TableEmptyRow colSpan={6}>Loading active remediation runs...</TableEmptyRow>
          ) : rows.length === 0 ? (
            <TableEmptyRow colSpan={6}>
              No open change units in this scope. When remediation runs execute, their active threads, rungs, and checkpoints will appear here.
            </TableEmptyRow>
          ) : (
            rows.map((row) => (
              <TableRow
                key={row.id}
                className="border-b border-border hover:bg-surface-subtle transition-colors"
              >
                <TableCell className="py-row px-section">
                  <div className="flex flex-col gap-field">
                    <Link
                      to={`/findings/${encodeURIComponent(row.findingId)}/workflow`}
                      className="font-semibold text-body text-foreground hover:underline"
                    >
                      <span>{row.vendor}</span>{" "}
                      <span className="font-mono text-meta text-muted-foreground">{row.operation}</span>
                    </Link>
                    <span className="text-meta text-muted-foreground">
                      {row.changeDescription}
                    </span>
                  </div>
                </TableCell>
                <TableCell className="py-row px-section text-right font-mono text-body text-foreground">
                  {row.reposCount}
                </TableCell>
                <TableCell className="py-row px-section text-right font-mono text-body text-foreground">
                  {row.callSitesCount}
                </TableCell>
                <TableCell className="py-row px-section">
                  <span className="font-mono text-meta text-muted-foreground bg-muted px-field py-field rounded-control border border-border">
                    {row.rung}
                  </span>
                </TableCell>
                <TableCell className="py-row px-section">
                  <div className="flex items-center gap-field text-meta">
                    <span className={`font-mono ${row.standingTone}`}>{row.standingSymbol}</span>
                    <span className={row.standingTone}>{row.standingLabel}</span>
                  </div>
                </TableCell>
                <TableCell className="py-row px-section font-mono text-meta text-muted-foreground">
                  {row.checkpointAge}
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>

      <div className="flex items-center justify-between border-t border-border bg-surface-subtle px-section py-row text-meta text-muted-foreground font-mono">
        <span>
          {rows.length > 0 ? `1–${rows.length} of ${rows.length}` : "0"} · Every open change unit in this scope
        </span>
      </div>
    </div>
  )
}
