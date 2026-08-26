/**
 * Findings: what is broken in this workspace, as one viewport-locked table with a drawer over it.
 *
 * **Rebuilt 2026-08-26 against `docs/stitch_sync_developer_console/.../self_healing_queue/`.** The
 * screen it replaces was a single scrolling column: a question sentence, a KPI strip, a fleet-wide
 * dismissal chart, a Radix tablist, a metric panel, and a table somewhere under all of it. The
 * reference is one dense card filling the frame with its head pinned and its footer pinned, and
 * that is what this is now. The page itself never scrolls; the rows do.
 *
 * ## Where each band went, and why the page draws almost none of it
 *
 * Identity is the chassis — banner, trail, the Findings/Trends strip — and the title and subtitle
 * come from `ScreenFrame`, so the page draws no heading of its own. The four KPI tiles portal into
 * the top bar through `KpiStrip`, so `FindingsKpis` stays mounted and contributes no flex child
 * here. Pagination and the record window belong to the status band. What is left for the page is
 * one controls row and one pane, which is the whole point of a locked layout.
 *
 * ## The severity strip and the grouping toggle are one control now
 *
 * Both were the same anatomy written twice — a strip of chips, one pressed. `ChipTabs` is that
 * control and `TriageTabs` is deleted: it owned a `Tabs` root that mounted one panel per severity
 * kind to render a single table, which is a lot of machinery for a search parameter. The four-way
 * empty derivation it carried is the half worth keeping and is now `TriageEmpty`, rendered above
 * the table rather than inside a tab panel.
 *
 * ## A drawer, not a docked column
 *
 * Owner ruling 2026-08-25, which postdates this screen's rebuild spec: **a detail must never
 * squeeze the table.** The spec asked for a permanent 22rem right-hand pane; that pane was measured
 * on the call-sites screen crushing file paths to one word per line. So the table takes the whole
 * width and the inspector slides over it, exactly as call sites does — and the selection lives in
 * the URL, so Back closes it and a row somebody wants a second opinion on is a link they can paste.
 *
 * ## The band counts two populations, not one
 *
 * The grouped view's rows are change units and the flat view's are findings, so a single count
 * under both would be true of one branch and a lie about the other. Each branch publishes its own
 * `records` segment naming its population, and the grouped one carries a note because the summary
 * pinned under that table sums findings over the changes listed rather than over the whole
 * narrowing. A third segment states the fleet-wide dismissal standing, because this table lists
 * open findings only and a finding somebody deliberately set aside would otherwise read as one
 * nobody has looked at.
 *
 * ## What the reference asks for and this refuses
 *
 * The spinning `autorenew` and pulsing `science` glyphs on its Agent Status chips are a liveness
 * pulse. The `opacity-75` strikethrough "resolved" row makes opacity a state channel. *Deploy
 * Agent* and the Production/Staging switch have nothing behind them — the API is read-only and
 * there is one deployment. *Search queue* is the command palette in the banner. And its Agent
 * Status phases are not in any payload we hold; `ChangeUnitRow.standing` is, and it becomes the
 * Standing column.
 */

import { useParams } from "react-router"

import { useChangeUnits, useDetectors, useTickets, useWorkspaceFindings } from "@/api/queries"
import type { FindingOrder, Ticket } from "@/api/types"
import { ChipTabs, type ChipOption } from "@/components/chip-tabs"
import { TableFrame } from "@/components/data-table"
import { DetailLayout, useSelectionKeys } from "@/components/detail-layout"
import { InfoHint } from "@/components/info-hint"
import { PanelPane } from "@/components/pane"
import { ErrorState, LoadingState } from "@/components/states"
import {
  TriageEmpty,
  triagePanelState,
  type TriageChecks,
  type TriageCount,
} from "@/components/triage"
import {
  ChangeUnitGroups,
  groupingSummary,
} from "@/features/findings/change-unit-groups"
import { dismissedNote, useDismissalTally } from "@/features/findings/dismissed-note"
import { INSPECT_KEY, selectRow } from "@/features/findings/finding-selection"
import { FindingsInspector } from "@/features/findings/findings-inspector"
import { FindingsKpis } from "@/features/findings/findings-kpis"
import { FindingsTable } from "@/features/findings/findings-table"
import { POLL_MS } from "@/features/tickets/ticket-action"
import { vendorName } from "@/features/vendors/vendor-name"
import { ScreenFrame } from "@/layouts/screen-frame"
import type { StatusSegment } from "@/layouts/status-band"
import { UnknownRoute } from "@/layouts/unknown-route"
import { describeRecordWindow } from "@/lib/record-window"
import { useFilterParam } from "@/lib/use-filter-param"
import { useOffsetParam } from "@/lib/use-offset-param"

const OFFSET_KEY = "findings_offset"
const DEFAULT_LIMIT = 25

/** The chip for the whole scope. Not a severity value, so it cannot collide with one. */
const ALL_TAB = "all"

const QUESTION = "Every open finding in this workspace, and what each one is bound to."

export function FindingsPage() {
  const { repoId } = useParams<{ repoId: string }>()
  const [offset, setOffset] = useOffsetParam(OFFSET_KEY)
  // The severity chip changes which rows exist, so the offset measured against the old set is
  // cleared in the same URL write -- and so is the selection, because a reader's own narrowing
  // must not strand them on a key this window no longer holds. Paging deliberately keeps the
  // selection: that is exactly where an unresolved key earns its keep.
  const [severity, setSeverity] = useFilterParam("severity", [OFFSET_KEY, INSPECT_KEY])
  const [order] = useFilterParam("order")
  // M15 Task 7: the change leads, because one vendor change breaking eleven call sites is one
  // decision rather than eleven, and a flat list is the console asserting otherwise by its shape.
  // The parameter spells only the departure from the default, so an unswitched screen's URL is
  // the URL it had before the toggle existed.
  const [view, setView] = useFilterParam("findings_view", [OFFSET_KEY, INSPECT_KEY])
  const grouped = view !== "flat"
  const [inspect, setInspect] = useFilterParam(INSPECT_KEY)

  const query = useWorkspaceFindings(repoId ?? "", {
    limit: DEFAULT_LIMIT,
    offset,
    severity: severity ?? undefined,
    order: (order ?? undefined) as FindingOrder | undefined,
  })
  // For `checks`: an empty narrowing must say which detectors stood behind the zero, and the
  // findings payload does not carry their names -- the detector roll-up does.
  const detectors = useDetectors(repoId)
  // Read here rather than inside the grouped branch so the band can count that branch's own
  // population; a hook cannot be conditional, so the flat view pays one read it then finds
  // already answered when the toggle is pressed.
  const units = useChangeUnits({ repoId, severity })
  // One read for every Solution cell on the screen and in the drawer. It was inside
  // `ChangeUnitGroups`, which meant the nested tables and the flat one asked separately.
  const ticketsQuery = useTickets(repoId ?? "", null, { refetchIntervalMs: POLL_MS })
  const dismissals = useDismissalTally()

  const unitRows = units.isSuccess ? units.data.items : []
  const findingRows = query.isSuccess ? query.data.items : []
  const selection = selectRow(inspect, grouped, unitRows, findingRows)
  const rowsHeld = grouped ? unitRows.length : findingRows.length
  // Arrow keys move the selection down the rows with the drawer open, which is the affordance a
  // list-and-detail pairing exists for.
  useSelectionKeys(
    grouped ? unitRows.map((unit) => unit.change_unit_id) : findingRows.map((row) => row.finding_id),
    inspect,
    setInspect,
  )

  if (repoId === undefined) return <UnknownRoute />

  const tickets = ticketsQuery.isSuccess ? ticketsQuery.data.tickets : null

  // The body renders only once both reads have settled, so the band is built from both: a
  // segment gated on fewer queries than the rows it describes prints a count for a table that
  // is not on screen.
  const settled = query.isSuccess && !detectors.isPending ? query.data : null

  let status: StatusSegment[]
  if (settled === null) {
    status = [
      {
        kind: "none",
        why: query.isError
          ? `the open findings in ${repoId} did not answer`
          : `asking for the open findings in ${repoId}`,
      },
    ]
  } else if (!grouped) {
    status = [
      {
        kind: "records",
        label:
          severity !== null
            ? `Open findings in ${repoId}, ${severity} only`
            : `Open findings in ${repoId}`,
        // Decision 60, on the screen it was written for. `describeRecordWindow` knows nothing of
        // the filter, so over a narrowed set that fits one page it says "This is all 12 findings"
        // -- beside a pager stating 75 were excluded. Under a filter the pager's own sentence is
        // the only honest one, so the window claim is withheld rather than qualified.
        text:
          severity !== null
            ? null
            : describeRecordWindow(
                offset,
                settled.items.length,
                { count: settled.total, boundReached: false },
                "finding",
                "findings",
              ),
        paging: {
          offset,
          limit: DEFAULT_LIMIT,
          shown: settled.items.length,
          total: settled.total,
          // Decision 60: with a filter on, `total` counts the narrowed set while `severity_total`
          // counts the scope, and a bare range under a narrowed table reads as the whole set.
          unfilteredTotal: severity !== null ? settled.severity_total : undefined,
          nextOffset: settled.next_offset,
          busy: query.isFetching,
          onOffsetChange: setOffset,
        },
      },
      dismissedNote(dismissals),
    ]
  } else if (units.isSuccess) {
    status = [
      {
        kind: "records",
        label: `Changes in ${repoId}`,
        text: describeRecordWindow(
          0,
          units.data.items.length,
          { count: units.data.total, boundReached: false },
          "change",
          "changes",
        ),
      },
      {
        kind: "note",
        text:
          "Counted in change units rather than findings: one vendor change breaking several call " +
          "sites is one row here. The findings figure under the table is summed over the changes " +
          "listed, not over every change in this narrowing.",
      },
      dismissedNote(dismissals),
    ]
  } else {
    status = [
      {
        kind: "none",
        why: units.isError
          ? `the changes open in ${repoId} did not answer`
          : `asking for the changes open in ${repoId}`,
      },
      dismissedNote(dismissals),
    ]
  }

  return (
    <ScreenFrame
      status={status}
      subtitle={QUESTION}
      layout="locked"
      controls={settled === null ? undefined : <Controls
        page={settled}
        severity={severity}
        onSeverity={setSeverity}
        grouped={grouped}
        onView={setView}
      />}
    >
      <section className="flex min-h-0 min-w-0 flex-1 flex-col">
        {/* Dashboard F1. Portals into the chassis stats bar, so it draws nothing in place and
            costs the locked column no height (owner ruling: a page draws no KPI row of its own). */}
        {query.isSuccess && (
          <FindingsKpis
            page={query.data}
            detectorNames={
              detectors.isSuccess ? detectors.data.detectors.map((row) => row.detector) : null
            }
          />
        )}

        {query.isPending || detectors.isPending ? (
          <LoadingState what={`open findings in ${repoId}`} />
        ) : query.isError ? (
          <ErrorState
            error={query.error}
            what={`open findings in ${repoId}`}
            onRetry={() => void query.refetch()}
          />
        ) : (
          <FindingsBody
            repoId={repoId}
            page={query.data}
            detectorNames={
              detectors.isSuccess ? detectors.data.detectors.map((row) => row.detector) : null
            }
            severity={severity}
            grouped={grouped}
            units={units}
            tickets={tickets}
            selection={selection}
            rowsHeld={rowsHeld}
            inspect={inspect}
            onInspect={setInspect}
          />
        )}
      </section>
    </ScreenFrame>
  )
}

/**
 * The severity strip and the grouping toggle, one row, both `ChipTabs`.
 *
 * The severity chips reach both views, because the grouping narrows before it buckets — a chip
 * that stopped applying when the view changed would look pressed over numbers true of something
 * else. The counts are computed without the severity narrowing, so a kind at zero keeps its chip
 * and that zero is a measured answer.
 */
function Controls({
  page,
  severity,
  onSeverity,
  grouped,
  onView,
}: {
  page: NonNullable<ReturnType<typeof useWorkspaceFindings>["data"]>
  severity: string | null
  onSeverity: (next: string | null) => void
  grouped: boolean
  onView: (next: string | null) => void
}) {
  return (
    <>
      <ChipTabs
        label="Findings by kind"
        options={severityChips(page)}
        activeId={severity ?? ALL_TAB}
        onSelect={(id) => onSeverity(id === ALL_TAB ? null : id)}
      />
      <InfoHint label="About open findings">
        Call sites that an open finding touches in this workspace, and in no other. The rung on each
        row says how the system knows the site is bound to the operation, and the ordering applied
        is the one the API says it applied rather than the one the address asked for. Each count
        beside a kind is over the whole workspace rather than over this page, and is computed
        without the narrowing it sets — so a kind at zero is a measured zero.
      </InfoHint>
      <div className="ml-auto">
        <ChipTabs
          label="Which question"
          options={[
            { id: "units", label: "By change" },
            { id: "flat", label: "Every finding" },
          ]}
          activeId={grouped ? "units" : "flat"}
          onSelect={(id) => onView(id === "units" ? null : id)}
        />
      </div>
    </>
  )
}

/**
 * The chip vocabulary: the payload's own `severity_order`, most severe first, with any kind the
 * counts hold beyond it appended rather than dropped — a row whose kind the chips omit is
 * unreachable by exactly the reader triaging it.
 */
function severityChips(
  page: NonNullable<ReturnType<typeof useWorkspaceFindings>["data"]>,
): ChipOption[] {
  const kinds = [
    ...page.severity_order,
    ...Object.keys(page.severity_counts).filter((kind) => !page.severity_order.includes(kind)),
  ]
  return [
    { id: ALL_TAB, label: "every kind", count: { kind: "counted", value: page.severity_total } },
    ...kinds.map(
      (kind): ChipOption => ({
        id: kind,
        label: kind,
        count: { kind: "counted", value: page.severity_counts[kind] ?? 0 },
      }),
    ),
  ]
}

function FindingsBody({
  repoId,
  page,
  detectorNames,
  severity,
  grouped,
  units,
  tickets,
  selection,
  rowsHeld,
  inspect,
  onInspect,
}: {
  repoId: string
  page: NonNullable<ReturnType<typeof useWorkspaceFindings>["data"]>
  /** The detector roll-up's names, or null when that route did not answer. */
  detectorNames: string[] | null
  severity: string | null
  grouped: boolean
  units: ReturnType<typeof useChangeUnits>
  /** The workspace's tickets, read once by the page. Null while that read is in flight. */
  tickets: readonly Ticket[] | null
  selection: ReturnType<typeof selectRow>
  rowsHeld: number
  inspect: string | null
  onInspect: (next: string | null) => void
}) {
  // Absence apart from zero, per narrowing rather than per page: an unindexed workspace has not
  // been checked at all, an indexed one names the detectors that stood behind its zeros. The
  // roll-up failing to answer is stated as its own fact -- claiming "checked" on its behalf would
  // put a sentence on screen nothing computed.
  const checks: TriageChecks =
    page.indexed_at === null
      ? {
          kind: "unchecked",
          why: `Nothing has indexed ${repoId}, so no detector has had anything to run against. A finding appears here once INDEX has walked this workspace.`,
        }
      : detectorNames === null
        ? {
            kind: "unchecked",
            why: `${repoId} was indexed, but the detector roll-up did not answer, so this screen cannot name what checked it.`,
          }
        : detectorNames.length === 0
          ? {
              kind: "unchecked",
              why: `${repoId} was indexed and the detector roll-up lists nothing for it — no detector has reported over this workspace yet.`,
            }
          : {
              kind: "checked",
              ran: [detectorNames[0], ...detectorNames.slice(1)],
              at: page.indexed_at,
            }

  // The active narrowing's own count, which is what the empty panel is about. Under a severity
  // chip that is the kind's count; under "every kind" it is the scope's.
  const activeCount: TriageCount = {
    kind: "counted",
    value: severity === null ? page.severity_total : (page.severity_counts[severity] ?? 0),
  }
  const activeLabel = severity ?? "every kind"

  const unitsPending = grouped && units.isPending
  const unitsFailed = grouped && units.isError
  // The four-way derivation, asked once. `TriageEmpty` returns null for `"records"`, so the state
  // is what decides whether a table renders at all rather than the element being truthy.
  const showsRecords = triagePanelState(activeCount, checks) === "records"

  return (
    <DetailLayout
      docked
      title={inspectorTitle(selection)}
      subtitle={inspectorSubtitle(selection)}
      onClose={() => onInspect(null)}
      detail={
        selection.kind === "none" ? null : (
          <FindingsInspector
            selection={selection}
            repoId={repoId}
            rowsHeld={rowsHeld}
            tickets={tickets}
          />
        )
      }
      list={
        <PanelPane
          scroll={false}
          label={grouped ? "Changes to deal with" : "Every open finding"}
          footer={
            grouped && units.isSuccess ? (
              <span data-testid="grouping-summary">
                {groupingSummary(units.data.items, units.data.total)}
              </span>
            ) : (
              <span>
                One row per finding. A change breaking several call sites appears once per site
                here, which is why the other view counts decisions instead.
              </span>
            )
          }
        >
          {unitsPending ? (
            <LoadingState what={`the changes open in ${repoId}`} />
          ) : unitsFailed ? (
            <ErrorState
              error={units.error}
              what={`the changes open in ${repoId}`}
              onRetry={() => void units.refetch()}
            />
          ) : !showsRecords ? (
            // `TriageEmpty` owns the empty state for both views, so neither table draws its own
            // empty row -- two would render one nothing twice.
            <div className="min-h-0 flex-1 overflow-auto p-section">
              <TriageEmpty
                noun="open findings"
                label={activeLabel}
                count={activeCount}
                checks={checks}
              />
            </div>
          ) : grouped && units.isSuccess ? (
            <ChangeUnitGroups
              units={units.data.items}
              selectedId={inspect}
              onSelect={(id) => onInspect(id === inspect ? null : id)}
            />
          ) : (
            // The frame is what makes the head stick: it moves the scroll onto the vendored table
            // container, which is the element a `sticky` thead has to sit inside. `ChangeUnitGroups`
            // carries its own; this table is shared with four flowing surfaces, so its surface
            // supplies one. Borderless because the pane already draws the border.
            <TableFrame fill className="rounded-none border-0">
              <FindingsTable
                repoId={repoId}
                rows={page.items}
                tickets={tickets}
                selectedId={inspect}
                onSelect={(id) => onInspect(id === inspect ? null : id)}
                stickyHeader
              />
            </TableFrame>
          )}
        </PanelPane>
      }
    />
  )
}

/** What the drawer calls the row it is showing. Never an id where a name exists. */
function inspectorTitle(selection: ReturnType<typeof selectRow>): string {
  if (selection.kind === "unit") {
    return `${vendorName(selection.unit.vendor_id)} / ${selection.unit.operation_id ?? "no operation recorded"}`
  }
  if (selection.kind === "finding") return selection.row.name
  if (selection.kind === "unresolved") return "Nothing on this page holds that key"
  return "Inspector"
}

function inspectorSubtitle(selection: ReturnType<typeof selectRow>): string | undefined {
  if (selection.kind === "unit") return selection.unit.change_unit_id
  if (selection.kind === "finding") {
    return `${selection.row.file}:${selection.row.line}`
  }
  return undefined
}
