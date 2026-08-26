/**
 * One integration in full, as a locked viewport of four panes.
 *
 * **Rebuilt 2026-08-26 against `docs/stitch_sync_developer_console/.../integration_performance_explorer/`.**
 * The screen it replaces was a `DetailGrid` fact rail over one exposure table with three records
 * stacked into tabs beneath it — a single scrolling column, which is the shape the owner's *"eight
 * of twenty-one screens still render `flow`"* audit names. The reference's composition is a wide
 * subject pane, a narrow rail of two smaller panes beside it, and a dense table filling the width
 * below; that is what this is, with each pane scrolling its own body and the page scrolling not at
 * all.
 *
 * **What the reference asks for and this refuses.** Its header carries a `Healthy` pill, its strip
 * carries throughput, average latency, a success rate and a dollar figure for cost saved, and its
 * endpoint list carries a coloured latency dot per row. Every one of those is either the composite
 * this console has rejected three times or a figure no stage measures, and `web/CLAUDE.md` outranks
 * the reference. What survived is its *composition* — mark, subject line, record chips, an
 * instrument strip, and the pane geometry — filled with what the graph actually holds. Its two
 * write actions (`Pause Sync`, `Force Sync`) are refused for a second reason: the API is read-only.
 *
 * **This screen goes deeper than the deck's drawer rather than repeating it.**
 * `vendor-inspector.tsx` names the products, the feeds and the last intake attempt from answers the
 * deck already holds. This one fetches the vendor's own payloads: every operation with its rung and
 * whether traffic confirmed it, the changes feed with the detail of any row, the findings open here
 * with their three narrowings, the attempt tally by outcome, and what the vendor has published.
 *
 * **The scope split is the screen's load-bearing fact and it is on screen, not in a tooltip.** Call
 * sites, operations and findings are counted in this repository; changes and everything about the
 * adapter are counted over the vendor, in every repository. The subject line says so and the status
 * band repeats it for whichever record is open.
 */

import { useParams } from "react-router"

import { useVendorChangeVolume, useVendorFindings, useVendorOperations } from "@/api/queries"
import { InfoHint } from "@/components/info-hint"
import { KpiStrip } from "@/components/kpi-strip"
import { Absent } from "@/components/status"
import { Pending } from "@/features/findings/pending"
import { VendorIntakePane } from "@/features/vendors/vendor-intake-pane"
import { VendorMark } from "@/features/vendors/vendor-mark"
import { vendorName } from "@/features/vendors/vendor-name"
import { VendorOperationsPane } from "@/features/vendors/vendor-operations-pane"
import { VendorPublishingPane } from "@/features/vendors/vendor-publishing-pane"
import { RECORDS, recordFrom, trafficSummary } from "@/features/vendors/vendor-record"
import { VendorRecordPane } from "@/features/vendors/vendor-record-pane"
import { ScreenFrame } from "@/layouts/screen-frame"
import type { StatusSegment } from "@/layouts/status-band"
import { UnknownRoute } from "@/layouts/unknown-route"
import { useFilterParam } from "@/lib/use-filter-param"

export interface VendorPageProps {
  readonly question?: string
}

// One line at `max-w-prose`, and measured rather than guessed: at 1366×768 the locked column has
// 577px for four panes, and a subtitle that wraps to two spends 20 of them on a second clause.
const QUESTION = "One integration in full: what this codebase calls, and what came of it."

export function VendorPage() {
  // **The route is the scope**, and it used to be a query string: this read
  // `searchParams.get("repo_id")` while the route carries `:repoId`, so an address naming a
  // workspace could still render a fleet-wide claim -- the screen contradicting its own URL.
  const { vendorId, repoId } = useParams<{ vendorId: string; repoId: string }>()
  if (vendorId === undefined || repoId === undefined) return <UnknownRoute />
  return <VendorRecord vendorId={vendorId} repoId={repoId} />
}

function VendorRecord({ vendorId, repoId }: { vendorId: string; repoId: string }) {
  const [recordParam, setRecord] = useFilterParam("record")
  const record = recordFrom(recordParam)

  const operations = useVendorOperations(vendorId, repoId)
  const volume = useVendorChangeVolume(vendorId)
  // Asked without any of the record's narrowings and with the smallest page the transport will
  // serve: this tile reports what the vendor has open in this scope *before* a filter, which is
  // exactly `severity_total`, and a key that carried the filters would let the figure move when a
  // chip was pressed.
  const findings = useVendorFindings(vendorId, { limit: 1, offset: 0, repoId })

  const summary =
    operations.data === undefined
      ? null
      : trafficSummary(operations.data.operations, operations.data.telemetry_attached_at)

  const callSites =
    operations.data === undefined
      ? null
      : operations.data.operations.reduce((total, operation) => total + operation.call_site_count, 0)

  const active = RECORDS.find((entry) => entry.id === record)!
  const status: StatusSegment[] = [
    { kind: "listing", label: "Record", text: active.label },
    { kind: "note", text: active.scope(vendorId, repoId) },
  ]

  return (
    <ScreenFrame layout="locked" status={status} title={vendorName(vendorId)} subtitle={QUESTION}>
      {/* Portals into the chassis stats bar, so it costs the locked column no height. */}
      <KpiStrip
        items={[
          {
            label: "Call sites here",
            value: figure(operations, callSites),
            note: `Static evidence — call sites the last index pass found in ${repoId} binding this vendor. Not calls, and not traffic.`,
          },
          {
            // A denominator on screen rather than a percentage, and no figure at all when any
            // operation went unmeasured: "1 of 5" over a set where only four were looked at is a
            // claim about five, and a reader cannot see which four.
            label: "Traffic confirmed",
            value:
              summary === null ? (
                queryMarker(operations)
              ) : summary.kind === "counted" ? (
                `${summary.confirmed.toLocaleString()} of ${summary.total.toLocaleString()} ops`
              ) : summary.kind === "never-measured" ? (
                <Absent>never measured</Absent>
              ) : (
                <Absent>no operations</Absent>
              ),
            note:
              summary === null || summary.kind === "counted"
                ? "Operations a span named, against every operation this codebase calls on the vendor. Observed evidence, reported beside the static count and never blended into it."
                : summary.why,
          },
          {
            label: "Open findings here",
            value: figure(findings, findings.data?.severity_total ?? null),
            note: `Open findings against this vendor in ${repoId}, counted before any narrowing on this screen.`,
          },
          {
            label: "Vendor change rows",
            value: figure(volume, volume.data?.total_changes ?? null),
            note: "Every change row Sync holds for this vendor, in every repository. Recorded at least once rather than exactly once, so this is a count of rows the feed produced and not a measurement of how often the vendor changed something.",
          },
        ]}
      />

      <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-section">
        {/* The subject line: the key every URL and join uses, and the scope split the four panes
            below disagree about on purpose. `shrink-0` because the grid under it claims `flex-1`
            and a header without it is compressed rather than keeping its own height. */}
        <div
          data-testid="vendor-identity"
          className="flex shrink-0 flex-wrap items-center gap-section rounded-surface border border-line bg-card px-section py-row text-meta"
        >
          <span className="flex min-w-0 items-center gap-row">
            <VendorMark vendorId={vendorId} />
            <code className="font-mono break-all text-ink select-all">{vendorId}</code>
          </span>
          <span className="flex min-w-0 items-center gap-field text-ink-muted">
            Call sites, operations and findings counted in{" "}
            <code className="font-mono break-all text-ink">{repoId}</code> · changes and the adapter
            counted over the vendor, in every repository
            <InfoHint label="About the two scopes on this screen">
              A vendor publishes a change once, to everyone, so its changes feed and its adapter
              record are the same whichever repository you reached them from. What this codebase
              calls, and what is open against it, are facts about this repository alone. The two are
              never added together, and every figure on this screen belongs to one of them.
            </InfoHint>
          </span>
        </div>

        {/* Three tracks stacked below `xl`, two columns at it: the subject pane and the record take
            the slack, the rail is fixed at the 22rem this console already uses for one. The rows are
            declared rather than left implicit — an implicit row is sized by its content before the
            `fr` rows divide what is left, which is what collapsed two panes to 131px and 87px on
            another screen. */}
        <div className="grid min-h-0 min-w-0 flex-1 grid-rows-[minmax(0,2fr)_minmax(0,3fr)_minmax(0,3fr)] gap-section xl:grid-cols-[minmax(0,1fr)_22rem] xl:grid-rows-[minmax(0,2fr)_minmax(0,3fr)]">
          <VendorOperationsPane
            vendorId={vendorId}
            repoId={repoId}
            data={operations.data}
            isPending={operations.isPending}
            error={operations.isError ? operations.error : null}
            onRetry={() => void operations.refetch()}
          />

          {/* The rail spans both rows at `xl` and stacks into its own two panes below it. One grid
              item either way, which is what keeps the base layout at three rows rather than four. */}
          <div className="grid min-h-0 min-w-0 grid-rows-[minmax(0,3fr)_minmax(0,2fr)] gap-section xl:row-span-2">
            <VendorIntakePane vendorId={vendorId} />
            <VendorPublishingPane vendorId={vendorId} />
          </div>

          <VendorRecordPane
            vendorId={vendorId}
            repoId={repoId}
            record={record}
            onRecord={(next) => setRecord(next === "changes" ? null : next)}
          />
        </div>
      </div>
    </ScreenFrame>
  )
}

/** A read still in flight, or one that failed — never a nought standing in for either. */
function queryMarker(query: { isPending: boolean }) {
  return query.isPending ? <Pending /> : <Absent>not answered</Absent>
}

/** A counted figure, or which nothing stands in its place. */
function figure(query: { isPending: boolean }, value: number | null) {
  if (value === null) return queryMarker(query)
  return value.toLocaleString()
}
