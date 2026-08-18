/**
 * The change unit: every open finding grouped by the vendor change and operation that caused
 * it, fleet-wide or scoped to one repository.
 *
 * `GET /api/change-units` computes this grouping once — `sync.dashboard.fleet.change_units` —
 * so this table renders it rather than deriving it a second way from `/api/overview` and
 * `/api/runs`, which is what it did before this table read the real endpoint. Two components
 * computing one grain independently is the exact defect `.claude/rules/console-dev-loop.md`
 * names: "a rule the payload can answer belongs in the payload... two components cannot
 * disagree about it."
 *
 * `repoId` is a real scope, not decoration: it reaches the endpoint as `repo_id` and narrows
 * the grouping itself, so a scoped page's `repository_count` and `call_site_count` describe
 * that repository alone rather than the fleet's.
 *
 * `standing` and `last_checkpoint_at` are `null` together on a genuinely unattempted change
 * unit, and that null is rendered through the console's one absence marker rather than a dash
 * or a fabricated "not started" — see `describeChangeUnitStanding` below. `last_checkpoint_at`,
 * once present, is staleness rather than liveness: no dot, no pulse, no colour claims a run is
 * still going. The fleet screen's own legend carries the protected sentence for why.
 */

import { Link } from "react-router"

import { DEFAULT_LIMIT } from "@/api/client"
import { useChangeUnits } from "@/api/queries"
import { BINDING_SOURCES, type BindingSource, type ChangeUnitRow } from "@/api/types"
import {
  Table,
  TableBody,
  TableCell,
  TableEmptyRow,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/data-table"
import { MetricPanel } from "@/components/metric-panel"
import { RelativeTime } from "@/components/relative-time"
import { ErrorState, LoadingState } from "@/components/states"
import { Absent, Formatted } from "@/components/status"
import { FooterBar } from "@/layouts/footer-bar"
import { describeRung, orAbsent } from "@/lib/format"
import { useOffsetParam } from "@/lib/use-offset-param"

export interface ChangeUnitStanding {
  label: string
  symbol: string
  tone: string
}

/**
 * How a change unit's `standing` renders — the one place a `null` from the payload turns into
 * a sentence, and the one function this file's honesty rests on.
 *
 * `null` returns `null` rather than a placeholder standing: it is genuine absence (no run has
 * ever been attempted for any finding this unit groups, or this deployment has no checkpointer
 * to ask), never a zero and never "not started" — the call site renders `<Absent>` for it and
 * says which nothing it is.
 *
 * `"in_progress"` is the one value `sync.dashboard.fleet.change_units` writes that is not one
 * of `RunDisposition`'s three terminal outcomes; it means the checkpointer holds a run for this
 * unit that has not yet reached `opened`, `abandoned` or `reported`.
 */
export function describeChangeUnitStanding(
  standing: ChangeUnitRow["standing"],
): ChangeUnitStanding | null {
  switch (standing) {
    case null:
      return null
    case "opened":
      return { label: "PR open — CI green", symbol: "✓", tone: "text-good-ink" }
    case "abandoned":
      return { label: "Abandoned", symbol: "✗", tone: "text-critical-ink" }
    case "reported":
      return { label: "Reported — no patch attempted", symbol: "—", tone: "text-muted-foreground" }
    case "in_progress":
      return { label: "In progress", symbol: "!", tone: "text-warning-ink" }
  }
}

const BINDING_SOURCE_SET = new Set<string>(BINDING_SOURCES)

/**
 * What a change unit's `binding_rung` claims, in prose — the rung column stays monochrome
 * either way, this is only the tooltip.
 *
 * `binding_rung` is a plain `string` because `_weaker_rung_summary` can answer `"mixed"`, a
 * real and deliberate value for a unit whose call sites disagree on rung. Routing it through
 * `describeRung` alone would land in that function's "this console does not recognise" branch,
 * which is the wrong claim — the console recognises this value exactly, and it is not a data
 * error.
 */
export function describeChangeUnitRung(rung: string): string {
  if (BINDING_SOURCE_SET.has(rung)) return describeRung(rung as BindingSource)
  if (rung === "mixed") {
    return "the call sites behind this change unit do not all agree on one rung"
  }
  return "a rung this console does not recognise — the provenance vocabulary has changed since this view was written"
}

function bindingSurfaceHref(vendorId: string, operationId: string, repoId?: string): string {
  const path = `/bindings/vendors/${encodeURIComponent(vendorId)}/operations/${encodeURIComponent(operationId)}`
  return repoId === undefined ? path : `${path}?repo_id=${encodeURIComponent(repoId)}`
}

function ChangeUnitRungBadge({ rung }: { rung: string }) {
  return (
    <span
      className="furniture rounded-control border border-line px-field py-field font-mono text-meta"
      title={describeChangeUnitRung(rung)}
    >
      {rung}
    </span>
  )
}

function StandingCell({ unit }: { unit: ChangeUnitRow }) {
  const standing = describeChangeUnitStanding(unit.standing)
  if (standing === null) {
    return (
      <Absent>
        no remediation run has ever been attempted for this change unit, or this deployment has
        no checkpointer to ask — the two look the same from here
      </Absent>
    )
  }
  return (
    <div className="flex items-center gap-field text-meta">
      <span className={`font-mono ${standing.tone}`}>{standing.symbol}</span>
      <span className={standing.tone}>{standing.label}</span>
    </div>
  )
}

function CheckpointCell({ unit }: { unit: ChangeUnitRow }) {
  if (unit.last_checkpoint_at === null) return <Absent>no checkpoint recorded</Absent>
  return <RelativeTime iso={unit.last_checkpoint_at} />
}

function ChangeUnitEmptyState({ repoId }: { repoId?: string }) {
  return (
    <>
      <span className="text-ink">
        {repoId === undefined
          ? "No open change units across the fleet."
          : `No open change units for ${repoId}.`}
      </span>{" "}
      The API answered with an empty page. A change unit appears here the moment a vendor change
      produces an open finding; nothing on this screen implies the underlying vendor change list is
      empty too.
    </>
  )
}

export function ChangeUnitsTable({ repoId }: { repoId?: string }) {
  const [offset, setOffset] = useOffsetParam("change_units_offset")
  const query = useChangeUnits({ repoId, limit: DEFAULT_LIMIT, offset })

  if (query.isPending) return <LoadingState what="change units" />
  if (query.isError) return <ErrorState error={query.error} what="change units" onRetry={() => void query.refetch()} />

  const page = query.data

  return (
    <MetricPanel
      label="Change units"
      metric={{
        value: page.total.toLocaleString(),
        unit: `open change unit${page.total === 1 ? "" : "s"}${
          repoId === undefined ? " across every repository the index has seen" : ` in ${repoId}`
        }`,
      }}
      caption={
        <p className="max-w-prose">
          Every open finding, grouped by the vendor change and operation that produced it. A
          change unit collapses findings sharing a vendor change against one repository set —
          the call-site grain is intact underneath and reachable from every row.
        </p>
      }
    >
      {/* Decision 61: the headers stay when there is nothing to list. A reader learns what a
          change unit IS from the columns, and that is most useful on the screen that has none. */}
      <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Vendor / operation</TableHead>
                <TableHead>Change kind</TableHead>
                <TableHead>Versions</TableHead>
                <TableHead>Severity</TableHead>
                <TableHead className="text-right">Repos</TableHead>
                <TableHead className="text-right">Call sites</TableHead>
                <TableHead>Rung</TableHead>
                <TableHead>Standing</TableHead>
                <TableHead>Checkpoint age</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {page.items.length === 0 && (
                <TableEmptyRow colSpan={9}>
                  <ChangeUnitEmptyState repoId={repoId} />
                </TableEmptyRow>
              )}
              {page.items.map((unit) => (
                <TableRow key={unit.change_unit_id}>
                  <TableCell className="font-mono">
                    {unit.operation_id === null ? (
                      <>
                        {unit.vendor_id} <Formatted value={orAbsent(unit.operation_id)} />
                      </>
                    ) : (
                      <Link
                        to={bindingSurfaceHref(unit.vendor_id, unit.operation_id, repoId)}
                        className="underline underline-offset-2"
                      >
                        {unit.vendor_id} {unit.operation_id}
                      </Link>
                    )}
                  </TableCell>
                  <TableCell>{unit.change_kind}</TableCell>
                  <TableCell className="font-mono">
                    <Formatted value={orAbsent(unit.from_version)} /> →{" "}
                    <Formatted value={orAbsent(unit.to_version)} />
                  </TableCell>
                  <TableCell>{unit.severity}</TableCell>
                  <TableCell className="text-right font-mono">
                    {unit.repository_count.toLocaleString()}
                  </TableCell>
                  <TableCell className="text-right font-mono">
                    {unit.call_site_count.toLocaleString()}
                  </TableCell>
                  <TableCell>
                    <ChangeUnitRungBadge rung={unit.binding_rung} />
                  </TableCell>
                  <TableCell>
                    <StandingCell unit={unit} />
                  </TableCell>
                  <TableCell className="font-mono text-meta">
                    <CheckpointCell unit={unit} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <FooterBar
            offset={offset}
            limit={DEFAULT_LIMIT}
            shown={page.items.length}
            total={page.total}
            nextOffset={page.next_offset}
            busy={query.isFetching}
            onOffsetChange={setOffset}
          />
      </>
    </MetricPanel>
  )
}
