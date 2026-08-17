import { Link } from "react-router"

import { useChangeUnits } from "@/api/queries"
import type { ChangeUnitRow } from "@/api/types"
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

function deriveStanding(unit: ChangeUnitRow): { label: string; symbol: string; tone: string } {
  if (unit.standing === "opened") {
    return { label: "PR open — CI green", symbol: "✓", tone: "text-emerald-400" }
  }
  if (unit.standing === "abandoned") {
    return { label: "Abandoned", symbol: "✗", tone: "text-rose-400" }
  }
  if (unit.standing === "reported") {
    return { label: "Reported — no patch attempted", symbol: "—", tone: "text-muted-foreground" }
  }
  if (unit.standing === "in_progress") {
    return { label: "Remediation in progress", symbol: "!", tone: "text-amber-400" }
  }
  return { label: "No remediation run yet", symbol: "—", tone: "text-muted-foreground" }
}

export function ChangeUnitsTable() {
  const changeUnitsQuery = useChangeUnits({ limit: 50, offset: 0 })

  const rows = changeUnitsQuery.data?.items ?? []

  return (
    <div className="flex flex-col rounded-lg border border-border bg-card overflow-hidden">
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
          {changeUnitsQuery.isLoading ? (
            <TableEmptyRow colSpan={6}>Loading open change units...</TableEmptyRow>
          ) : rows.length === 0 ? (
            <TableEmptyRow colSpan={6}>
              No open change units in this scope. When a vendor change produces an open finding,
              it appears here grouped with every other finding it caused.
            </TableEmptyRow>
          ) : (
            rows.map((unit) => {
              const standing = deriveStanding(unit)
              const firstFindingId = unit.finding_ids[0]
              const versionRange =
                unit.from_version && unit.to_version
                  ? `${unit.from_version} → ${unit.to_version}`
                  : unit.change_kind

              return (
                <TableRow
                  key={unit.change_unit_id}
                  className="border-b border-border hover:bg-surface-subtle transition-colors"
                >
                  <TableCell className="py-row px-section">
                    <div className="flex flex-col gap-field">
                      <Link
                        to={
                          firstFindingId
                            ? `/findings/${encodeURIComponent(firstFindingId)}/workflow`
                            : "#"
                        }
                        className="font-semibold text-body text-foreground hover:underline"
                      >
                        <span>{unit.vendor_id}</span>{" "}
                        <span className="font-mono text-meta text-muted-foreground">
                          {unit.operation_id ?? "all operations"}
                        </span>
                      </Link>
                      <span className="text-meta text-muted-foreground">{versionRange}</span>
                    </div>
                  </TableCell>
                  <TableCell className="py-row px-section text-right font-mono text-body text-foreground">
                    {unit.repository_count}
                  </TableCell>
                  <TableCell className="py-row px-section text-right font-mono text-body text-foreground">
                    {unit.call_site_count}
                  </TableCell>
                  <TableCell className="py-row px-section">
                    <span className="font-mono text-meta text-muted-foreground bg-muted px-field py-field rounded border border-border">
                      {unit.binding_rung}
                    </span>
                  </TableCell>
                  <TableCell className="py-row px-section">
                    <div className="flex items-center gap-field text-meta">
                      <span className={`font-mono ${standing.tone}`}>{standing.symbol}</span>
                      <span className={standing.tone}>{standing.label}</span>
                    </div>
                  </TableCell>
                  <TableCell className="py-row px-section font-mono text-meta text-muted-foreground">
                    {unit.last_checkpoint_at ? formatElapsed(unit.last_checkpoint_at) : "—"}
                  </TableCell>
                </TableRow>
              )
            })
          )}
        </TableBody>
      </Table>

      <div className="flex items-center justify-between border-t border-border bg-surface-subtle px-section py-row text-meta text-muted-foreground font-mono">
        <span>
          {rows.length > 0 ? `1–${rows.length} of ${changeUnitsQuery.data?.total ?? rows.length}` : "0"} · Every open change unit in this scope
        </span>
      </div>
    </div>
  )
}
