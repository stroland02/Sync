/**
 * Dashboard 9: adapter coverage by tier.
 *
 * `adapter-coverage-option.ts` carries what is counted and why the plan's vocabulary is not the
 * one used. This file is the frame around it, and the sentences under the chart are load-bearing:
 * they say what the figure is over and what it excludes, because a bar chart with no denominator
 * invites a reader to supply their own.
 */

import { useCallback, useMemo } from "react"

import type { AdapterRow } from "@/api/types"
import type { ChartTokens } from "@/components/charts/echart"
import { EChart } from "@/components/charts/echart"
import { EmptyState } from "@/components/states"
import {
  adapterCoverageByTier,
  buildAdapterCoverageOption,
} from "@/features/settings/adapter-coverage-option"

export function AdapterCoverageChart({ adapters }: { adapters: readonly AdapterRow[] }) {
  const coverage = useMemo(() => adapterCoverageByTier(adapters), [adapters])

  const build = useCallback(
    (tokens: ChartTokens) => buildAdapterCoverageOption(coverage, tokens),
    [coverage],
  )

  if (adapters.length === 0) {
    return (
      <EmptyState
        headline="No adapter is registered."
        detail="The inventory answered with an empty list, so there is nothing to count by tier. This is a read that found nothing, not a read that did not happen."
          command="uv run sync intake --vendor <vendor>"
      />
    )
  }

  return (
    <section className="flex flex-col gap-field rounded-surface border border-line bg-surface p-section">
      <div className="flex flex-col gap-field">
        <h3 className="text-emphasis font-medium text-ink">Coverage by tier</h3>
        <p className="text-meta text-ink-muted">
          How many vendors each kind of adapter serves, across this whole deployment.
        </p>
      </div>

      <div className="h-40 w-full">
        <EChart
          buildOption={build}
          ariaLabel="Number of vendors served, by adapter tier"
          style={{ height: "100%", width: "100%" }}
        />
      </div>

      <p className="text-meta text-ink-muted leading-relaxed">
        {coverage.totalServing} of {adapters.length} rows in the inventory are served by an
        adapter. A tier showing nought was counted and found empty, which is not the same as not
        having been counted.
        {coverage.unregistered > 0 && (
          <>
            {" "}
            The remaining {coverage.unregistered}{" "}
            {coverage.unregistered === 1 ? "row is" : "rows are"} unregistered — history the graph
            holds keyed by a vendor nothing serves any more. They are excluded from the bars above
            rather than drawn beside them, because they are the absence of coverage rather than a
            kind of it.
          </>
        )}
      </p>
    </section>
  )
}
