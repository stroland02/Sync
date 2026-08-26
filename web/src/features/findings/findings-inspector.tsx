/**
 * What one selected row holds, in the drawer over the table.
 *
 * **A drawer, not a docked column** — owner ruling 2026-08-25, carried in the UI rebuild brief:
 * *a detail must never squeeze the table*. The rebuild spec for this screen asked for a permanent
 * 22rem right-hand pane; that pane was measured on the call-sites screen squeezing file paths to
 * one word per line, and the ruling that replaced it postdates the spec. So the table takes the
 * whole locked viewport and this slides over it through `DetailLayout docked`.
 *
 * **Two selected branches, each its own component, so their hooks stay unconditional.** A unit
 * renders entirely from the `ChangeUnitRow` the table already holds and asks for nothing; a finding
 * paints from its `RiskRow` immediately and *enriches* from two further reads. That ordering is the
 * point of splitting them: the row's own facts are on screen before any request is made and stay
 * there when one fails.
 *
 * **Three states of a value, never folded together.** `<Pending>` while an enrichment read is in
 * flight, `<Absent>the API did not answer</Absent>` when it failed, and `<Absent>this finding is
 * not open</Absent>` for a 404 — which is the API answering about the finding rather than about the
 * request, and rendering the first over the second is a false report of the failure a reader is
 * looking at. `finding-page.tsx` spells the same three and this follows it exactly.
 *
 * **No captured source window here.** A snippet is the full finding page's, and a code block in a
 * drawer over a locked viewport is the one element that would blow its height. The drawer ends with
 * the link to that page instead.
 */

import type { ReactNode } from "react"

import { NotFoundError } from "@/api/errors"
import { useFinding, useWorkflow } from "@/api/queries"
import type { BindingSource, ChangeUnitRow, RiskRow, Ticket } from "@/api/types"
import { type Fact, FactList } from "@/components/fact-list"
import { ChangeKindTag, OutcomeTag, SeverityTag } from "@/components/tag"
import { RungBadge } from "@/components/provenance"
import { RelativeTime } from "@/components/relative-time"
import { Absent, Formatted } from "@/components/status"
import { Button } from "@/components/ui/button"
import { FindingsTable } from "@/features/findings/findings-table"
import { Pending } from "@/features/findings/pending"
import { describeRemediation } from "@/features/findings/remediation"
import { remediationFact } from "@/features/findings/remediation-fact"
import type { FindingSelection } from "@/features/findings/finding-selection"
import { vendorName } from "@/features/vendors/vendor-name"
import { findingHref } from "@/lib/hrefs"
import { orAbsent } from "@/lib/format"
import { Link } from "react-router"

/**
 * How a change unit's run stands — three nothings, spelled apart.
 *
 * A recorded disposition is a badge. `"in_progress"` is the checkpointer holding a run whose
 * outcome has not been written, which is not an outcome. `null` is two indistinguishable things at
 * once — no run was ever attempted, or this deployment has no checkpointer to ask — and
 * `ChangeUnitRow`'s own docstring is explicit that the payload cannot tell them apart, so neither
 * may be claimed.
 */
function standingFact(unit: ChangeUnitRow) {
  if (unit.standing === null) {
    return <Absent>no run recorded for this change</Absent>
  }
  if (unit.standing === "in_progress") {
    return <span>in flight — no outcome written yet</span>
  }
  return <OutcomeTag outcome={unit.standing} />
}

/**
 * When the standing was *written*, which is staleness and never liveness.
 *
 * Rendered as its own fact rather than omitted when absent: a missing checkpoint time is a thing
 * the payload does not hold, and dropping the row would render it as a standing with no age.
 */
function checkpointFact(unit: ChangeUnitRow) {
  return unit.last_checkpoint_at === null ? (
    <Absent>no checkpoint time recorded</Absent>
  ) : (
    <RelativeTime iso={unit.last_checkpoint_at} />
  )
}

/** The versions a change spans. Half a span is not a narrower answer, so the pair is the value. */
function versionsFact(unit: ChangeUnitRow) {
  if (unit.from_version === null || unit.to_version === null) return <Absent>not recorded</Absent>
  return (
    <span className="font-mono text-meta">
      {unit.from_version} &rarr; {unit.to_version}
    </span>
  )
}

function UnitInspector({
  unit,
  repoId,
  tickets,
}: {
  unit: ChangeUnitRow
  repoId: string
  tickets: readonly Ticket[] | null
}) {
  const facts: Fact[] = [
    { label: "Change kind", value: <ChangeKindTag kind={unit.change_kind} /> },
    { label: "Versions", value: versionsFact(unit) },
    { label: "Severity", value: <SeverityTag severity={unit.severity} /> },
    {
      label: "Rung",
      // The weakest rung among the constituent findings — the unit is only as well attributed as
      // its least-attributed member, and reporting the strongest would overstate what the graph
      // knows about the rest.
      value: <RungBadge rung={unit.binding_rung as BindingSource} />,
    },
    { label: "Findings", value: unit.finding_count.toLocaleString() },
    { label: "Call sites", value: unit.call_site_count.toLocaleString() },
    { label: "Repositories", value: unit.repository_count.toLocaleString() },
    { label: "Standing", value: standingFact(unit) },
    { label: "Standing written", value: checkpointFact(unit) },
  ]

  return (
    <div className="flex min-w-0 flex-col gap-section">
      <FactList facts={facts} />

      <div className="flex min-w-0 flex-col gap-row">
        <h3 className="furniture text-meta text-ink-muted">The findings this change holds</h3>
        <FindingsTable repoId={repoId} rows={unit.findings} tickets={tickets} />
        {/* The nested rows are a bounded sample and a reader must not read them as the whole
            unit. The payload caps them because `limit` bounds units and nothing bounded these --
            eight units carried ten thousand rows and 4.3 MB before it did -- and `finding_count`
            is the population, computed independently. Silence here would make a truncated list
            look complete, which is the one thing a count that disagrees with the rows beneath it
            must never do. */}
        {unit.finding_count > unit.findings.length && (
          <p className="text-meta text-ink-muted">
            Showing {unit.findings.length.toLocaleString()} of{" "}
            {unit.finding_count.toLocaleString()} findings in this change. The rest are in the flat
            list, which pages.
          </p>
        )}
      </div>
    </div>
  )
}

function FindingInspector({ row }: { row: RiskRow }) {
  const detail = useFinding(row.finding_id)
  const workflow = useWorkflow(row.finding_id)

  // A 404 is the API answering that the graph holds no open finding under this id -- it may have
  // been patched since the list was read -- and it is a different sentence from a request that did
  // not arrive.
  const gone = detail.isError && detail.error instanceof NotFoundError
  const enriched = (value: ReactNode) => {
    if (detail.isPending) return <Pending />
    if (gone) return <Absent>this finding is not open</Absent>
    if (detail.isError) return <Absent>the API did not answer</Absent>
    return value
  }

  const remediation = describeRemediation({
    data: workflow.data,
    missing: workflow.isError && workflow.error instanceof NotFoundError,
    failed: workflow.isError,
  })

  const facts: Fact[] = [
    // The row's own facts, from the list the reader is looking at. On screen before any request
    // is made, and still on screen when one fails.
    { label: "Severity", value: <SeverityTag severity={row.severity} /> },
    { label: "Rung", value: <RungBadge rung={row.binding_source} /> },
    {
      label: "Call site",
      value: (
        <span className="font-mono text-meta break-all">
          {row.file}:{row.line}
        </span>
      ),
    },
    { label: "Symbol", value: <Formatted value={orAbsent(row.symbol)} /> },
    { label: "Operation", value: <Formatted value={orAbsent(row.operation)} /> },
    { label: "Change kind", value: <Formatted value={orAbsent(row.change_kind)} /> },
    { label: "Integration", value: vendorName(row.vendor) },
    // Enriched from the finding's own route.
    {
      label: "SDK version",
      value: enriched(
        detail.data?.sdk_version ? (
          <span className="font-mono text-meta">{detail.data.sdk_version}</span>
        ) : (
          <Absent>not recorded</Absent>
        ),
      ),
    },
    {
      label: "Argument keys",
      value: enriched(
        detail.data && detail.data.args_keys.length > 0 ? (
          <span className="font-mono text-meta break-words">
            {detail.data.args_keys.join(", ")}
          </span>
        ) : (
          <Absent>none recorded</Absent>
        ),
      ),
    },
    {
      label: "Response fields read",
      value: enriched(
        detail.data && detail.data.response_fields_read.length > 0 ? (
          <span className="font-mono text-meta break-words">
            {detail.data.response_fields_read.join(", ")}
          </span>
        ) : (
          <Absent>none recorded</Absent>
        ),
      ),
    },
    {
      label: "Known changes",
      value: enriched(detail.data ? detail.data.known_changes.length.toLocaleString() : null),
    },
    { label: "Remediation", value: remediationFact(remediation) },
  ]

  return <FactList facts={facts} />
}

/**
 * A key the current window does not hold.
 *
 * Neither *nothing selected* nor *the row is gone*, and the parameter is deliberately **not**
 * cleared: clearing it would tell a reader their link was wrong, which is one of the three
 * possibilities and the only one this page can rule out.
 */
function Unresolved({ selectionKey, rowsHeld }: { selectionKey: string; rowsHeld: number }) {
  return (
    <div className="flex flex-col gap-row text-body text-ink-muted">
      <p className="font-mono text-meta break-all text-ink">{selectionKey}</p>
      <p>
        This page holds {rowsHeld.toLocaleString()} {rowsHeld === 1 ? "row" : "rows"} and none of
        them is that one — the row may sit behind a severity chip, on another page, or the graph
        may hold no such row at all. Nothing here can tell those apart, so none is picked.
      </p>
    </div>
  )
}

export function FindingsInspector({
  selection,
  repoId,
  rowsHeld,
  tickets,
}: {
  selection: FindingSelection
  repoId: string
  /** How many rows this window holds, for the sentence a key it does not hold has to make. */
  rowsHeld: number
  /** The workspace's tickets, fetched once by the page. Null while that read is in flight. */
  tickets: readonly Ticket[] | null
}) {
  if (selection.kind === "none") return null
  if (selection.kind === "unresolved") {
    return <Unresolved selectionKey={selection.key} rowsHeld={rowsHeld} />
  }

  const findingId =
    selection.kind === "finding" ? selection.row.finding_id : selection.unit.finding_ids[0]

  return (
    <div className="flex min-w-0 flex-col gap-section">
      {selection.kind === "unit" ? (
        <UnitInspector unit={selection.unit} repoId={repoId} tickets={tickets} />
      ) : (
        <FindingInspector row={selection.row} />
      )}

      {/* A unit gets no link per constituent: the nested table's name cells already carry one
          each, and a column of identical buttons beside them would be the same route twice. */}
      {findingId !== undefined && (
        <Button asChild variant="outline" className="w-full">
          <Link to={findingHref(repoId, findingId)}>
            {selection.kind === "unit" ? "Open the first finding" : "Open the finding"}
          </Link>
        </Button>
      )}
    </div>
  )
}
