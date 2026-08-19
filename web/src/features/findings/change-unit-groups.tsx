/**
 * Findings, led by the change that caused them.
 *
 * **M15 Task 7.** The plan's problem statement is arithmetic: *24 findings are really 13 change
 * units, and the console lists them flat, so a reader sees 24 problems where there are 13.* One
 * vendor change breaking eleven call sites is one decision to make, not eleven — and a flat list
 * is the console asserting otherwise by its shape.
 *
 * ## The two figures have to agree, and that is the whole correctness claim
 *
 * A grouped view whose parts do not add to the flat total is worse than no grouping: it reads as
 * a rounding artefact rather than as a contradiction, so nobody investigates it. The payload
 * therefore **narrows before it groups** — a severity tab filters findings and *then* buckets
 * them, so a unit reports the findings of that severity it holds and the sum still equals the
 * flat total for that tab. Filtering units after grouping would leave every unit counting
 * findings the reader is not being shown. `tests/test_dashboard_fleet.py` holds it, proven by
 * moving the filter and watching the sum go to 2 where 1 was right.
 *
 * ## Counts come from the payload, never from the array beside them
 *
 * `finding_count` is stated. Counting `findings.length` would report the rows this page happens
 * to hold, which is the same class of defect as a total summed over a paginated set — right until
 * the moment anything paginates, and silent afterwards.
 *
 * ## Closed by default
 *
 * Every unit expanded is the flat table with extra steps. A reader scanning this is choosing
 * which vendor change to deal with; the call sites matter once that choice is made.
 */

import { useState } from "react"
import { ChevronRight } from "lucide-react"

import type { BindingSource, ChangeUnitRow } from "@/api/types"
import {
  Table,
  TableBody,
  TableCell,
  TableEmptyRow,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/data-table"
import { ChangeKindTag, SeverityTag } from "@/components/tag"
import { RungBadge } from "@/components/provenance"
import { Absent } from "@/components/status"
import { FindingsTable } from "@/features/findings/findings-table"
import { vendorName } from "@/features/vendors/vendor-name"

/**
 * How many findings a set of units holds, from the payload's own counts.
 *
 * Exported because it is the derivation with a wrong answer on this surface: summing
 * `findings.length` instead would quietly describe the page rather than the workspace.
 */
export function findingsHeld(units: readonly ChangeUnitRow[]): number {
  return units.reduce((held, unit) => held + unit.finding_count, 0)
}

function Versions({ unit }: { unit: ChangeUnitRow }) {
  if (unit.from_version === null || unit.to_version === null) {
    // The pair is what a version span means; half of one is not a narrower answer.
    return <Absent>not recorded</Absent>
  }
  return (
    <span className="font-mono text-meta">
      {unit.from_version} &rarr; {unit.to_version}
    </span>
  )
}

function UnitRow({ repoId, unit }: { repoId: string; unit: ChangeUnitRow }) {
  const [open, setOpen] = useState(false)
  const noun = unit.finding_count === 1 ? "finding" : "findings"

  return (
    <>
      <TableRow>
        <TableCell>
          <button
            type="button"
            onClick={() => setOpen((was) => !was)}
            aria-expanded={open}
            className="flex items-center gap-field rounded-control px-field py-field text-meta text-ink transition-colors hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          >
            <ChevronRight
              aria-hidden="true"
              className={`size-3.5 shrink-0 transition-transform ${open ? "rotate-90" : ""}`}
            />
            <span className="tabular-nums">
              {unit.finding_count.toLocaleString()} {noun}
            </span>
          </button>
        </TableCell>
        <TableCell className="font-mono text-meta">
          <span className="text-ink">{vendorName(unit.vendor_id)}</span>
          {unit.operation_id === null ? (
            <Absent>no operation recorded</Absent>
          ) : (
            <span className="text-ink-muted"> / {unit.operation_id}</span>
          )}
        </TableCell>
        <TableCell>
          <ChangeKindTag kind={unit.change_kind} />
        </TableCell>
        <TableCell>
          <Versions unit={unit} />
        </TableCell>
        <TableCell>
          <SeverityTag severity={unit.severity} />
        </TableCell>
        <TableCell>
          {/* The weakest rung among the constituent findings — the unit is only as well
              attributed as its least-attributed member, and reporting the strongest would
              overstate what the graph knows about the rest. */}
          <RungBadge rung={unit.binding_rung as BindingSource} />
        </TableCell>
        <TableCell className="text-right tabular-nums text-meta text-ink-muted">
          {unit.call_site_count.toLocaleString()}
        </TableCell>
      </TableRow>
      {open && (
        <TableRow>
          <TableCell colSpan={7} className="bg-surface-subtle p-section">
            {/* The same table the flat view renders, so one finding is one object however a
                reader arrived at it. */}
            <FindingsTable repoId={repoId} rows={unit.findings} />
          </TableCell>
        </TableRow>
      )}
    </>
  )
}

export function ChangeUnitGroups({
  repoId,
  units,
  unitTotal,
}: {
  repoId: string
  units: readonly ChangeUnitRow[]
  /** How many units the narrowing holds, which is not how many are on this page. */
  unitTotal: number
}) {
  const held = findingsHeld(units)

  return (
    <div className="flex min-w-0 flex-col gap-row">
      <p data-testid="grouping-summary" className="max-w-prose text-meta text-ink-muted">
        {unitTotal.toLocaleString()} {unitTotal === 1 ? "change" : "changes"} to deal with,
        holding {held.toLocaleString()} open {held === 1 ? "finding" : "findings"}. One vendor
        change breaking several call sites is one decision, and this counts the decisions.
      </p>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Findings</TableHead>
            <TableHead>Integration / operation</TableHead>
            <TableHead>Change kind</TableHead>
            <TableHead>Versions</TableHead>
            <TableHead>Severity</TableHead>
            <TableHead>Rung</TableHead>
            <TableHead className="text-right">Call sites</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {units.length === 0 && (
            <TableEmptyRow colSpan={7}>
              <span className="text-ink">No open finding in this narrowing.</span> That is a
              measured answer where a pass has run and nothing at all where none has &mdash; the
              Overview&rsquo;s Getting started says which.
            </TableEmptyRow>
          )}
          {units.map((unit) => (
            <UnitRow key={unit.change_unit_id} repoId={repoId} unit={unit} />
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
