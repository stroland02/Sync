/**
 * Dashboards D1 and D2: the Detectors page's opening facts, and findings per detector.
 *
 * Both read `/api/detectors`, which the page already fetches — same query key, so neither costs
 * a request.
 *
 * **The ranking is a ranking and nothing more.** A detector at the top of this chart is the one
 * raising the most findings, which is not the same as the one producing the most false positives
 * and is emphatically not a quality order. The page's own prose says a detector resting entirely
 * on `static` evidence is making a weaker claim than one resting on `observed` — that reading
 * belongs to the rung breakdown, and this chart deliberately does not encode it. Colour is ink
 * rather than identity for the same reason: a hue over a bar length would be a second encoding
 * of the same number, and a hue meaning *quality* would be the score this console refuses.
 *
 * **A detector that raised nothing is absent from the payload, not present at nought.** The
 * aggregate groups the open findings it found, so a detector that ran clean produces no entry —
 * and the strip's "detectors reporting" tile therefore counts detectors *with findings*, which
 * is what its note says rather than what a reader would otherwise assume.
 */

import { useDetectors } from "@/api/queries"
import { InfoHint } from "@/components/info-hint"
import { KpiStrip } from "@/components/kpi-strip"
import { MetricPanel } from "@/components/metric-panel"
import { RankedBars } from "@/components/ranked-bars"
import { Absent } from "@/components/status"
import { ErrorState, LoadingState } from "@/components/states"

export function DetectorsDashboards({ repoId }: { repoId: string }) {
  const query = useDetectors(repoId)

  if (query.isPending) return <LoadingState what="detector attribution" />
  if (query.isError) {
    return (
      <ErrorState
        error={query.error}
        what="detector attribution"
        onRetry={() => void query.refetch()}
      />
    )
  }

  const { detectors, by_rung, total_open_findings } = query.data
  const rungsPresent = Object.entries(by_rung).filter(([, count]) => count > 0)
  const rows = detectors
    .map((row) => ({ key: row.detector, value: row.total }))
    .sort((a, b) => b.value - a.value || a.key.localeCompare(b.key))

  return (
    <>
      <KpiStrip
        items={[
          {
            label: "Detectors reporting",
            value: detectors.length.toLocaleString(),
            // Not "detectors that ran". The aggregate groups findings, so a detector that ran
            // and found nothing is absent rather than present at zero.
            note: "raised at least one open finding here",
          },
          {
            label: "Findings attributed",
            value: total_open_findings.toLocaleString(),
            note: "each counted once, across every detector",
          },
          {
            label: "Rungs present",
            value:
              rungsPresent.length === 0 ? (
                <Absent>nothing to attribute</Absent>
              ) : (
                `${rungsPresent.length} of ${Object.keys(by_rung).length}`
              ),
            note: "kinds of evidence behind these findings",
            figure: rungsPresent.length !== 0,
          },
        ]}
      />

      <MetricPanel
        label="Findings per detector"
        hint={
          <InfoHint label="About findings per detector">
            How many open findings each detector raised in this workspace. A ranking of volume and
            nothing more — the detector at the top is the loudest, which is not the same as the
            most wrong. Whether a detector&rsquo;s claims are well evidenced is the rung breakdown
            beneath, and this chart deliberately does not encode it. A detector that ran and found
            nothing is absent from this chart rather than drawn at nought, because the aggregate
            groups findings rather than detectors.
          </InfoHint>
        }
      >
        {rows.length === 0 ? (
          <p className="max-w-prose text-body text-ink-muted">
            No detector has raised an open finding in this workspace. Nothing to rank — and this
            chart cannot tell you whether that is because every detector ran clean or because none
            has run, since a detector with no findings does not appear in it either way.
          </p>
        ) : (
          <RankedBars
            label="By detector"
            caption="Open findings in this workspace, grouped by the detector that raised each. Each bar's width is its share of the largest, not of the total."
            rows={rows}
            unit="findings"
            colourByKey={false}
          />
        )}
      </MetricPanel>
    </>
  )
}
