/**
 * Dashboard I3: open findings per integration, ranked.
 *
 * **The table beneath answers "which integrations are here"; this answers "which one is costing
 * the most right now".** Those are different questions and the table cannot be read for the
 * second: it sorts by the reader's chosen column and pages, so the largest contributor is not
 * reliably on screen.
 *
 * **`vendors` is an unbounded `GROUP BY`, not a page.** `overview_summary`'s docstring is
 * explicit that the vendor breakdown is deliberately unbounded where the finding *total* is
 * bounded — a distribution derived from a truncated page is the distribution of whichever rows
 * the ordering reached. So this ranking describes the population, and it does not inherit the
 * total's ceiling.
 *
 * **An integration with no open findings is absent from the payload, not present at nought**, and
 * the note says so. The `GROUP BY` returns groups that exist; a vendor this codebase calls
 * cleanly produces no row, and drawing it at zero would claim it was measured and found clean
 * when the truth is that it did not appear.
 */

import { useOverview } from "@/api/queries"
import { InfoHint } from "@/components/info-hint"
import { MetricPanel } from "@/components/metric-panel"
import { RankedBars } from "@/components/ranked-bars"
import { ErrorState, LoadingState } from "@/components/states"

export function FindingsPerIntegration({ repoId }: { repoId: string }) {
  const query = useOverview(repoId)

  if (query.isPending) return <LoadingState what="open findings per integration" />
  if (query.isError) {
    return (
      <ErrorState
        error={query.error}
        what="open findings per integration"
        onRetry={() => void query.refetch()}
      />
    )
  }

  const rows = query.data.vendors
    .map((vendor) => ({ key: vendor.vendor_id, value: vendor.open_finding_count }))
    .sort((a, b) => b.value - a.value || a.key.localeCompare(b.key))

  const hint = (
    <InfoHint label="About findings per vendor">
      Open findings grouped by the integration each is bound to. Counted over every open finding
      in this workspace rather than over a page of them, so the ranking describes the whole set.
      An integration missing from this chart has no open finding — it is absent from the grouping
      rather than counted at nought, and those are different claims.
    </InfoHint>
  )

  if (rows.length === 0) {
    return (
      <MetricPanel
        label="Open findings per vendor"
        hint={hint}
        caption="No integration in this workspace has an open finding."
      >
        <p className="max-w-prose text-body text-ink-muted">
          Nothing to rank. Every integration this codebase calls is either clean or has never been
          scanned, and this chart cannot tell you which — it groups findings, so a vendor with
          none and a vendor nothing looked at are the same absence here.
        </p>
      </MetricPanel>
    )
  }

  return (
    <MetricPanel label="Open findings per vendor" hint={hint}>
      <RankedBars
        label="By vendor"
        caption="Open findings in this workspace, grouped by integration. Each bar's width is its share of the largest, not of the total."
        rows={rows}
        unit="findings"
      />
    </MetricPanel>
  )
}
