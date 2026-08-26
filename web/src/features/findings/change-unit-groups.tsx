/**
 * Findings, led by the change that caused them, as a viewport-locked selectable table.
 *
 * **M15 Task 7.** The plan's problem statement is arithmetic: *24 findings are really 13 change
 * units, and the console lists them flat, so a reader sees 24 problems where there are 13.* One
 * vendor change breaking eleven call sites is one decision to make, not eleven — and a flat list
 * is the console asserting otherwise by its shape.
 *
 * ## The expander is gone, and a unit opens in the drawer instead
 *
 * **Rebuilt 2026-08-26.** Each row used to carry a disclosure that pushed a nested findings table
 * into a `colSpan` row beneath it. In a locked viewport that is the wrong control twice: it makes
 * a row's height jump under the reader's pointer while they are scanning, and it puts a table
 * inside a table inside a pane that scrolls. A unit is now selected into the inspector, which is
 * where its constituents, its call-site and repository counts and the caveat about the nested
 * sample all live. `findings-inspector.tsx` carries them.
 *
 * ## The two figures have to agree, and that is the whole correctness claim
 *
 * A grouped view whose parts do not add to the flat total is worse than no grouping: it reads as
 * a rounding artefact rather than as a contradiction, so nobody investigates it. The payload
 * therefore **narrows before it groups** — a severity chip filters findings and *then* buckets
 * them, so a unit reports the findings of that severity it holds and the sum still equals the
 * flat total for that narrowing. Filtering units after grouping would leave every unit counting
 * findings the reader is not being shown. `tests/test_dashboard_fleet.py` holds it, proven by
 * moving the filter and watching the sum go to 2 where 1 was right.
 *
 * ## Counts come from the payload, never from the array beside them
 *
 * `finding_count` is stated. Counting `findings.length` would report the rows this page happens
 * to hold, which is the same class of defect as a total summed over a paginated set — right until
 * the moment anything paginates, and silent afterwards.
 *
 * ## Standing is the reference's Agent Status, landed on data we actually hold
 *
 * The Stitch still gives every row a phase — *Proposing Fix*, *Testing Sandbox*, *Analyzing
 * Traces* — with a spinning glyph beside it. Nothing in any payload here holds a phase, and
 * `WorkflowNodeStatus` is a different grain that only exists per finding on the workflow route, so
 * synthesising one is inventing a claim. What the grouped payload does carry, and nothing rendered
 * until now, is `standing` and `last_checkpoint_at`. Those are the honest counterpart: a recorded
 * disposition, a run in flight with no outcome written, or a null that means *no run was attempted
 * or this deployment has no checkpointer to ask* and cannot be narrowed further.
 */

import type { BindingSource, ChangeUnitRow } from "@/api/types"
import {
  Table,
  TableBody,
  TableCell,
  TableFrame,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/data-table"
import { ChangeKindTag, OutcomeTag, SeverityTag } from "@/components/tag"
import { RungBadge } from "@/components/provenance"
import { RelativeTime } from "@/components/relative-time"
import { Absent } from "@/components/status"
import { Button } from "@/components/ui/button"
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

/**
 * The sentence that reconciles the two figures a reader compares, pinned in the pane's footer.
 *
 * A string rather than JSX because it is the derivation, and the derivation is the half with a
 * wrong answer: the unit count comes from the narrowing and the finding count is summed from the
 * payload's own per-unit counts over the units on this page. Those are deliberately different
 * scopes, which is why the sentence says *holding* rather than *of*, and why the status band
 * carries its own note saying the findings figure is summed over the changes listed.
 */
export function groupingSummary(units: readonly ChangeUnitRow[], unitTotal: number): string {
  const held = findingsHeld(units)
  return (
    `${unitTotal.toLocaleString()} ${unitTotal === 1 ? "change" : "changes"} to deal with, ` +
    `holding ${held.toLocaleString()} open ${held === 1 ? "finding" : "findings"}. ` +
    "One vendor change breaking several call sites is one decision, and this counts the decisions."
  )
}

/**
 * The unit's run standing — three answers that must stay three.
 *
 * A recorded `RunDisposition` is a badge from a closed vocabulary. `"in_progress"` is a run the
 * checkpointer holds whose outcome has not been written, which is not an outcome. `null` is two
 * indistinguishable facts at once and `ChangeUnitRow`'s docstring says so: either no run was ever
 * attempted for any finding this unit groups, or this deployment has no checkpointer to ask.
 * Rendering it as "not started" would claim the second case never happens.
 */
function Standing({ unit }: { unit: ChangeUnitRow }) {
  if (unit.standing === null) return <Absent>no run recorded</Absent>
  return (
    // Inline rather than stacked. Measured 2026-08-26 in Chrome at 1366x768: two stacked cells put
    // the row at 59px and only three rows in the pane, against the reference's 44px. The qualifier
    // is a phrase beside the badge, not a second line under it.
    <span className="flex flex-wrap items-center gap-field text-meta">
      {unit.standing === "in_progress" ? (
        <span>in flight — no outcome yet</span>
      ) : (
        <OutcomeTag outcome={unit.standing} />
      )}
      {/* Staleness, never liveness: this is when the standing was *written*, and nothing in this
          row says whether the run behind it is still going or has died. */}
      <span className="text-ink-muted">
        {unit.last_checkpoint_at === null ? (
          <Absent>no checkpoint time</Absent>
        ) : (
          <>
            written <RelativeTime iso={unit.last_checkpoint_at} />
          </>
        )}
      </span>
    </span>
  )
}

function UnitRow({
  unit,
  selected,
  onSelect,
}: {
  unit: ChangeUnitRow
  selected: boolean
  onSelect: (id: string) => void
}) {
  const noun = unit.finding_count === 1 ? "finding" : "findings"

  return (
    <TableRow
      // `data-table.tsx` already styles this with `bg-surface-emphasis`, so selection is the
      // surface step rather than a colour claiming a judgement about the row.
      data-state={selected ? "selected" : undefined}
      onClick={() => onSelect(unit.change_unit_id)}
      className="cursor-pointer"
    >
      <TableCell className="tabular-nums text-meta">
        {unit.finding_count.toLocaleString()} {noun}
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
        {/* Versions folded under the kind rather than given a column of their own: the call-sites
            table already stacks a two-line leading cell inside one `py-row`, and the pair is a
            qualifier on the change rather than a fact a reader scans down, so it sits beside the
            kind rather than under it. The absence marker travels with the fold -- half a version
            span is not a narrower answer. */}
        <span className="flex flex-wrap items-center gap-field">
          <ChangeKindTag kind={unit.change_kind} />
          <span className="text-meta text-ink-muted">
            {unit.from_version === null || unit.to_version === null ? (
              <Absent>not recorded</Absent>
            ) : (
              <span className="font-mono">
                {unit.from_version} &rarr; {unit.to_version}
              </span>
            )}
          </span>
        </span>
      </TableCell>
      <TableCell>
        <SeverityTag severity={unit.severity} />
      </TableCell>
      <TableCell>
        {/* The weakest rung among the constituent findings — the unit is only as well attributed
            as its least-attributed member, and reporting the strongest would overstate what the
            graph knows about the rest. Not hideable. */}
        <RungBadge rung={unit.binding_rung as BindingSource} />
      </TableCell>
      <TableCell>
        <Standing unit={unit} />
      </TableCell>
      <TableCell className="text-right">
        {/* The keyboard-reachable control. The row's own `onClick` is a convenience for a pointer
            and carries no affordance of its own. */}
        <Button
          size="sm"
          variant="outline"
          aria-pressed={selected}
          onClick={(event) => {
            event.stopPropagation()
            onSelect(unit.change_unit_id)
          }}
        >
          Inspect
        </Button>
      </TableCell>
    </TableRow>
  )
}

export function ChangeUnitGroups({
  units,
  selectedId,
  onSelect,
}: {
  units: readonly ChangeUnitRow[]
  selectedId: string | null
  onSelect: (id: string) => void
}) {
  return (
    <TableFrame fill className="border-0 rounded-none">
      <Table>
        <TableHeader sticky>
          <TableRow>
            <TableHead>Findings</TableHead>
            <TableHead>Integration / operation</TableHead>
            <TableHead>Change kind</TableHead>
            <TableHead>Severity</TableHead>
            <TableHead>Rung</TableHead>
            <TableHead>Standing</TableHead>
            <TableHead className="text-right">Inspect</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {/* No empty row here. `TriageEmpty` above this table owns the empty state and says
              which nothing it is; two would render one nothing twice. */}
          {units.map((unit) => (
            <UnitRow
              key={unit.change_unit_id}
              unit={unit}
              selected={unit.change_unit_id === selectedId}
              onSelect={onSelect}
            />
          ))}
        </TableBody>
      </Table>
    </TableFrame>
  )
}
