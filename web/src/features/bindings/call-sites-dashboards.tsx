/**
 * Dashboards C1, C2 and C3: the Call sites page's opening facts, its per-integration ranking,
 * and where a vendor change would cost most.
 *
 * **This page had the richest unused aggregate in the console.** `/api/topology` computes call
 * sites, files, operations and integrations over exactly the rows this table lists, and the page
 * fetched none of it — the table has always shown the rows and never their shape. The read is
 * shared with the Integration map's page on one query key, so mounting it here costs nothing where
 * that page has been visited.
 *
 * ## Loop depth was drawn here and is not any more, owner ruling 2026-08-19
 *
 * C3 was a loop-depth histogram and C1's fourth tile was the same fact as a figure. Against a real
 * graph that is *162 not in a loop, 2 at depth one, 1 at depth two* — a chart whose only content
 * beyond the tile above it is a two-versus-one split, drawn at 162:2:1. It is the bar-chart form of
 * the defect `web/CLAUDE.md` records for the provenance donut: a form that cannot draw its own data.
 *
 * What replaced it is the concentration ranking, which is the question this page exists for: one
 * operation reached from many files is one vendor change to review and many places to patch.
 *
 * **`busiest_operations` is `LIMIT 8` in SQL** (`graph/store.py`), so this is the eight busiest and
 * not every operation, and the caption says so. A cap a reader cannot see reads as a complete set.
 */

import { useQuery } from "@tanstack/react-query"

import { fetchTopology } from "@/features/repositories/api-topology-card"
import { InfoHint } from "@/components/info-hint"
import { KpiStrip } from "@/components/kpi-strip"
import { LastIndexed } from "@/components/last-indexed"
import { MetricPanel } from "@/components/metric-panel"
import { RankedBars } from "@/components/ranked-bars"
import { ErrorState, LoadingState } from "@/components/states"

export function CallSitesDashboards({ repoId }: { repoId: string }) {
  const query = useQuery({
    // The Integration map's page key, so the two share one read.
    queryKey: ["api-topology", repoId],
    queryFn: ({ signal }) => fetchTopology(repoId, signal),
  })

  if (query.isPending) return <LoadingState what="the call-site totals" />
  if (query.isError) {
    return (
      <ErrorState
        error={query.error}
        what="the call-site totals"
        onRetry={() => void query.refetch()}
      />
    )
  }

  const { totals, by_vendor, busiest_operations } = query.data

  const perVendor = by_vendor
    .map((row) => ({ key: row.vendor_id, value: row.call_sites }))
    .sort((a, b) => b.value - a.value || a.key.localeCompare(b.key))

  // Already ordered by the route; the key carries the vendor because an operation id is only
  // unique within one, and two integrations naming an operation alike would share a bar.
  const busiest = busiest_operations.map((row) => ({
    key: `${row.vendor_id} · ${row.operation_id}`,
    value: row.call_sites,
  }))
  const filesPerOperation = new Map(
    busiest_operations.map((row) => [`${row.vendor_id} · ${row.operation_id}`, row.files]),
  )
  // The colour dimension: three integrations behind eight operations, so the hue says where the
  // concentration sits rather than repeating each bar's own length.
  const vendorPerOperation = new Map(
    busiest_operations.map((row) => [`${row.vendor_id} · ${row.operation_id}`, row.vendor_id]),
  )

  return (
    <>
      <KpiStrip
        items={[
          {
            label: "Call sites",
            value: totals.call_sites.toLocaleString(),
            note: "indexed in this workspace, before any narrowing",
          },
          {
            label: "Files calling out",
            value: totals.files.toLocaleString(),
            note: "hold at least one call site",
          },
          {
            label: "Operations reached",
            value: totals.operations.toLocaleString(),
            note: `across ${totals.vendors.toLocaleString()} integration${totals.vendors === 1 ? "" : "s"}`,
          },
          {
            label: "Last indexed",
            // Staleness, never liveness, and never-indexed is not a date this tile invents: a
            // repository with no finished pass says so rather than borrowing another's stamp.
            value: <LastIndexed repoId={repoId} />,
            note: "when this codebase's call sites were last read",
            figure: false,
          },
        ]}
      />

      <div className="grid auto-rows-fr gap-8 xl:grid-cols-2">
        <MetricPanel
          label="Call sites per integration"
          hint={
            <InfoHint label="About call sites per integration">
              Where this codebase calls out, grouped by integration. Counted over every indexed
              call site rather than the narrowed table, so the rail&rsquo;s selections do not
              change these bars. An integration with no bar has no current call site here.
            </InfoHint>
          }
        >
          {perVendor.length === 0 ? (
            <p className="max-w-prose text-body text-ink-muted">
              No integration has a call site in this workspace. That is the absence of an index
              pass rather than a codebase that calls nothing.
            </p>
          ) : (
            <RankedBars
              label="By integration"
              caption="Indexed call sites, grouped by integration. Each bar's width is its share of the largest, not of the total."
              rows={perVendor}
              unit="call sites"
            />
          )}
        </MetricPanel>

        <MetricPanel
          label="Most-called operations"
          hint={
            <InfoHint label="About most-called operations">
              Concentration is what makes a vendor change cheap or expensive: one operation reached
              from many files is one change to review and many places to patch. Counted over every
              indexed call site rather than the narrowed table, so the rail&rsquo;s selections do
              not change these bars. The route returns the eight busiest and no more and five are
              drawn, so an operation absent here is outside the top eight rather than uncalled.
              Colour is the integration the operation belongs to, which is the one thing the bar
              lengths do not carry.
            </InfoHint>
          }
          caption="Where a vendor change would cost most. Static evidence: this is what the code calls, not what ran."
        >
          {busiest.length === 0 ? (
            <p className="max-w-prose text-body text-ink-muted">
              No operation has a call site in this workspace. That is the absence of an index pass
              rather than a codebase that calls nothing.
            </p>
          ) : (
            <RankedBars
              label="By call sites"
              caption="The five busiest operations, not every operation. Each bar's width is its share of the busiest, not of the total."
              rows={busiest}
              unit="call sites"
              // Five, not eight: the route returns eight and the remainder is summarised in a line
              // rather than dropped, which reads in a quarter of the height eight rows took.
              max={5}
              scale="log"
              colourKey={(key) => vendorPerOperation.get(key) ?? key}
              detail={(key) => {
                const files = filesPerOperation.get(key)
                if (files === undefined) return ""
                return `${files.toLocaleString()} file${files === 1 ? "" : "s"}`
              }}
            />
          )}
        </MetricPanel>
      </div>
    </>
  )
}
