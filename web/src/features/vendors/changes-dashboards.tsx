/**
 * Dashboards G1 and G3: the Changes feed's opening facts, and severity per integration.
 *
 * Both read the facets the page already fetched — same query key, so neither costs a request.
 *
 * **Every figure here is unfiltered, and the strip says so.** The rail narrows the table; these
 * describe the whole record. That is `kpi-strip.tsx`'s rule about earning a slot — a tile
 * restating the narrowed table's footer would be the same number twice, and the useful thing a
 * tile can say is what the reader has filtered themselves away from.
 *
 * **The breaking share is a ratio with its denominator on screen, not a score.** `n of m` rather
 * than a percentage alone: a bare percentage is the figure a reader cannot check, and it is one
 * step from the composite this console refuses. It is also not a judgement about this codebase —
 * severity is the vendor's own as published, and whether a breaking change breaks anything here
 * depends on whether a call site binds to it, which is what a finding is.
 *
 * **G3 is a stacked ranking, not a donut.** The owner ruled donuts for mixes and bars for
 * rankings, and this is both: the vendors are ranked and each bar is a mix. A donut per vendor
 * would be a dozen donuts nobody can compare, so it stays in the bar family and the stack
 * carries the mix — one row per integration, ordered by how much each published.
 *
 * **The severity ranking is drawn on a log scale, announced.** Measured against this deployment:
 * 8,576 warnings, 108 breaking, 39 deprecation. Linear, the two a reader cares about are one
 * pixel each — the same illegibility that made the provenance ring look unbuilt, and the reason
 * the owner ruled log for skewed sets. The stacked per-integration rows below stay linear, because
 * a stack is a composition and a log stack does not sum to anything.
 */

import { InfoHint } from "@/components/info-hint"
import { KpiStrip } from "@/components/kpi-strip"
import { MetricPanel } from "@/components/metric-panel"
import { RankedBars } from "@/components/ranked-bars"
import { RelativeTime } from "@/components/relative-time"
import { Absent } from "@/components/status"
import { seriesScale } from "@/lib/palette"

export interface ChangesFacets {
  readonly by_vendor: Record<string, number>
  readonly by_severity: Record<string, number>
  readonly by_vendor_severity: Record<string, Record<string, number>>
  readonly unfiltered_total: number
  readonly newestDetectedAt: string | null
}

export function ChangesKpis({ facets }: { facets: ChangesFacets }) {
  const breaking = facets.by_severity.breaking ?? 0
  const publishing = Object.keys(facets.by_vendor).length

  return (
    <KpiStrip
      items={[
        {
          label: "Changes recorded",
          value: facets.unfiltered_total.toLocaleString(),
          note: "every change the graph holds",
        },
        {
          label: "Integrations publishing",
          value: publishing.toLocaleString(),
          note: "at least one change recorded",
        },
        {
          label: "Published as breaking",
          value:
            facets.unfiltered_total === 0 ? (
              <Absent>nothing recorded</Absent>
            ) : (
              `${breaking.toLocaleString()} of ${facets.unfiltered_total.toLocaleString()}`
            ),
          note: "the vendor's own severity, not a judgement about this codebase",
          figure: facets.unfiltered_total !== 0,
        },
        {
          label: "Newest change",
          value:
            facets.newestDetectedAt === null ? (
              <Absent>{facets.unfiltered_total === 0 ? "none recorded" : "not while narrowed"}</Absent>
            ) : (
              <RelativeTime iso={facets.newestDetectedAt} />
            ),
          // Two things at once, and both are said rather than assumed. The date is when Sync
          // noticed, never when the vendor shipped -- nothing in the graph carries a vendor
          // publication date and a reader supplies one unless told. And this tile is the one
          // figure here that cannot be computed under a narrowing: the newest row of a filtered
          // page is the newest *matching* change, which is a different claim from the one the
          // label makes, so it withholds rather than answering the wrong question quietly.
          note:
            facets.newestDetectedAt === null && facets.unfiltered_total > 0
              ? "computed from the newest row, which a narrowing changes — clear the rail to read it"
              : "when Sync detected it, not when the vendor published it",
          figure: false,
        },
      ]}
    />
  )
}

/**
 * One stacked row per integration, ordered by how much each published.
 *
 * SVG rather than the chart engine, which is `ranked-bars.tsx`'s own argument: a stacked row here
 * is a handful of rectangles whose widths are ratios, and pulling in a canvas, a resize observer
 * and a theme bridge for that geometry buys nothing. Anything that grows an axis goes to ECharts.
 */
/**
 * The whole record split by severity, ranked — G3's other half, and the one a reader triages by.
 *
 * Separate from the per-integration stack because the questions differ: this is *how much of what
 * the vendors publish is breaking*, the stack is *which vendor publishes it*. Log-scaled and said
 * so, since the set spans three orders of magnitude.
 */
export function SeverityMix({ facets }: { facets: ChangesFacets }) {
  const rows = Object.entries(facets.by_severity)
    .map(([key, value]) => ({ key, value }))
    .sort((a, b) => b.value - a.value || a.key.localeCompare(b.key))

  if (rows.length === 0) return null

  return (
    <RankedBars
      label="Severity as published"
      caption="Every change the graph holds, by the severity its vendor gave it — counted across the whole record rather than the narrowed table. Severity is the vendor's own: a change published as breaking breaks this codebase only where a call site binds to it."
      rows={rows}
      unit="changes"
      colourByKey={false}
      scale="log"
    />
  )
}

export function SeverityPerIntegration({ facets }: { facets: ChangesFacets }) {
  const rows = Object.entries(facets.by_vendor_severity)
    .map(([vendor, mix]) => ({
      vendor,
      mix,
      total: Object.values(mix).reduce((sum, n) => sum + n, 0),
    }))
    .sort((a, b) => b.total - a.total || a.vendor.localeCompare(b.vendor))

  // Every severity that occurs anywhere, so one severity is the same colour on every row.
  const severities = [...new Set(rows.flatMap((row) => Object.keys(row.mix)))].sort()
  const colour = seriesScale(severities)
  const widest = rows.reduce((max, row) => Math.max(max, row.total), 0)

  const hint = (
    <InfoHint label="About severity per integration">
      Every change each integration published, split by the severity the vendor gave it. Counted
      across the whole record rather than the narrowed table, so the rail&rsquo;s selections do
      not change these bars. A severity missing from an integration&rsquo;s bar was never
      published by it — absent from the grouping rather than counted at nought, and those are
      different claims. Severity is the vendor&rsquo;s own: a change published as breaking breaks
      this codebase only where a call site binds to it.
    </InfoHint>
  )

  if (rows.length === 0) {
    return (
      <MetricPanel
        label="Severity per integration"
        hint={hint}
        caption="No integration has published a change."
      >
        <p className="max-w-prose text-body text-ink-muted">
          Nothing to split. No adapter has delivered a change yet, so there is no severity mix for
          any integration — which is the absence of a measurement rather than a measured zero.
        </p>
      </MetricPanel>
    )
  }

  return (
    <MetricPanel
      label="Severity per integration"
      hint={hint}
      caption="Each row is one integration's whole published record. A row's full width is the largest publisher's total, so rows compare against each other rather than against themselves."
    >
      <div className="flex flex-col gap-row">
        <ul className="flex flex-wrap gap-section">
          {severities.map((severity) => (
            <li key={severity} className="flex items-center gap-field text-meta text-ink-muted">
              <span
                aria-hidden
                className="h-[0.6rem] w-[0.6rem] rounded-[2px]"
                style={{ background: colour(severity) }}
              />
              {severity}
            </li>
          ))}
        </ul>

        {rows.map((row) => (
          <div key={row.vendor} className="flex min-w-0 flex-col gap-field">
            <div className="flex items-baseline justify-between gap-row">
              <span className="min-w-0 truncate font-mono text-meta text-ink">{row.vendor}</span>
              <span className="text-meta tabular-nums text-ink-muted">
                {row.total.toLocaleString()}
              </span>
            </div>
            <div
              className="flex h-[0.5rem] w-full overflow-hidden rounded-[2px]"
              role="img"
              aria-label={`${row.vendor}: ${severities
                .filter((s) => row.mix[s] !== undefined)
                .map((s) => `${row.mix[s]} ${s}`)
                .join(", ")}`}
            >
              {severities
                .filter((severity) => row.mix[severity] !== undefined)
                .map((severity) => (
                  <span
                    key={severity}
                    style={{
                      // Share of the widest row, not of this row: every row summing to full
                      // width would draw a vendor with one change the same size as one with
                      // three hundred, which is the ranking claim silently deleted.
                      width: `${widest === 0 ? 0 : (row.mix[severity] / widest) * 100}%`,
                      background: colour(severity),
                    }}
                  />
                ))}
            </div>
          </div>
        ))}
      </div>
    </MetricPanel>
  )
}
