/**
 * Dashboards C1, C2 and C3: the Call sites page's opening facts, its per-integration ranking,
 * and the loop-depth distribution.
 *
 * **This page had the richest unused aggregate in the console.** `/api/topology` computes call
 * sites, files, operations, integrations and a loop-depth histogram over exactly the rows this
 * table lists, and the page fetched none of it — the table has always shown the rows and never
 * their shape. The read is shared with the Integration map's page on one query key, so mounting
 * it here costs nothing where that page has been visited.
 *
 * **Loop depth is the one figure here that is not a count of rows, and it is labelled as static
 * evidence.** A call inside a loop is a call the code *can* make many times; whether it does is
 * a runtime question this rung cannot answer, and a loop that never executes still counts. Depth
 * one is a page of results becoming one call each; depth two is quadratic. That is worth seeing
 * as a distribution rather than as a total, because one deeply nested call site matters more than
 * fifty shallow ones and a sum would hide it.
 *
 * **Depth zero is drawn.** It is the overwhelming majority on any real codebase, and dropping it
 * would make the looped ones look like the whole population — the chart would go from "3 of 812
 * sit in loops" to "3 sit in loops" with no denominator, which is the shape of figure this
 * console refuses.
 */

import { useQuery } from "@tanstack/react-query"

import { fetchTopology } from "@/features/repositories/api-topology-card"
import { InfoHint } from "@/components/info-hint"
import { KpiStrip } from "@/components/kpi-strip"
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

  const { totals, by_vendor, by_loop_depth } = query.data

  const perVendor = by_vendor
    .map((row) => ({ key: row.vendor_id, value: row.call_sites }))
    .sort((a, b) => b.value - a.value || a.key.localeCompare(b.key))

  const depths = Object.entries(by_loop_depth)
    .map(([depth, count]) => ({ depth: Number(depth), count }))
    .sort((a, b) => a.depth - b.depth)
  const looped = depths.filter((d) => d.depth > 0).reduce((sum, d) => sum + d.count, 0)

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
            label: "Inside a loop",
            value: `${looped.toLocaleString()} of ${totals.call_sites.toLocaleString()}`,
            // Static evidence, said in the tile rather than only in the chart below, because a
            // tile is read on its own and this one is the easiest on the page to misread.
            note: "what the code can repeat, not what ran",
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
          label="Loop depth"
          hint={
            <InfoHint label="About loop depth">
              How deeply each call site is nested inside loops, counted statically. A loop that
              never runs still counts here — this says what the code <em>can</em> repeat, never
              what it did. Depth one is a page of results becoming one call each; depth two is
              quadratic. Depth zero is drawn rather than dropped, because without it the looped
              call sites would appear to be the whole population.
            </InfoHint>
          }
          caption="Indexed call sites by nesting depth. Static evidence: this is the shape of the code, not a record of execution."
        >
          {depths.length === 0 ? (
            <p className="max-w-prose text-body text-ink-muted">
              No call site to measure. Nothing has been indexed in this workspace, so there is no
              nesting to report.
            </p>
          ) : (
            <RankedBars
              label="By nesting depth"
              caption="Each bar's width is its share of the most common depth. Depth zero is not inside a loop."
              rows={depths.map((d) => ({
                key: d.depth === 0 ? "not in a loop" : `depth ${d.depth}`,
                value: d.count,
              }))}
              unit="call sites"
              colourByKey={false}
            />
          )}
        </MetricPanel>
      </div>
    </>
  )
}
