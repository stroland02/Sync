/**
 * Dashboard O2: this workspace's open findings by the rung that established each binding.
 *
 * **This is the console's own argument rendered as a chart.** `CLAUDE.md`: every binding carries
 * the rung it came from, and a false positive that cannot be attributed to a rung cannot be
 * fixed. The rung has been a column on every table since the beginning; this is the first screen
 * that shows the shape of the whole set at a glance — how much of what Sync claims rests on a
 * static guess, how much on a resolved import, how much on observed traffic.
 *
 * ## Why this is bars, and why it took two tries to get there
 *
 * It shipped first as a donut. Against this repository's graph that is 24 findings, all `static`,
 * four rungs at nought — so it drew one closed ring with a one-entry legend. The second attempt
 * kept the donut and moved the zeros into a prose list beneath, which replaced an unreadable
 * chart with no chart at all: a heading, two paragraphs and five lines of text.
 *
 * **The mistake underneath both was the form.** A donut asserts share-of-whole, and share-of-whole
 * cannot draw a zero — an arc of nought has no angle, so a member measured at none is either
 * invisible or absent, and on this panel *four of five members are measured zeros*. That is not a
 * degenerate case to special-case; it is the ordinary state of a codebase Sync has only indexed
 * statically, and it is the single most informative thing the panel can say.
 *
 * A horizontal bar has a length of zero and still has a row, a label and a printed count. So the
 * whole vocabulary is always visible, a rung at nought reads as *measured and empty* rather than
 * as missing, and the same chart works unchanged when the mix is genuinely spread.
 *
 * **A zero here is a measurement, and this is nearly the only place on the console where that is
 * true.** `overview_summary` fills the dict from `FINDING_RUNGS` rather than from the rows it
 * found, so `resolved: 0` means counted-and-found-none — the opposite of the usual reading, where
 * a missing key means nobody looked. Drawing the zeros is therefore not a courtesy; it is the
 * accurate rendering.
 *
 * **`unattributed` is drawn like any other rung.** It is the count the honesty rule exists to
 * make visible, and hiding it would be the one edit that defeats the panel's purpose.
 */

import { useOverview } from "@/api/queries"
import { InfoHint } from "@/components/info-hint"
import { MetricPanel } from "@/components/metric-panel"
import { RankedBars } from "@/components/ranked-bars"
import { ErrorState, LoadingState } from "@/components/states"

/** What each rung means, in one clause, so the chart explains itself without the ⓘ. */
const RUNG_MEANING: Record<string, string> = {
  static: "from the shape of the call alone",
  resolved: "from following the import to its package",
  observed: "from traffic Sync actually saw",
  unresolved: "the import was followed and led nowhere",
  unattributed: "written before the rung column existed",
}

/** Strongest evidence first, which is the order a reader weighs them in. */
const RUNG_ORDER = ["observed", "resolved", "static", "unresolved", "unattributed"]

export function RungMixCard({ repoId }: { repoId: string }) {
  const query = useOverview(repoId)

  if (query.isPending) return <LoadingState what="the provenance mix" />
  if (query.isError) {
    return (
      <ErrorState
        error={query.error}
        what="the provenance mix"
        onRetry={() => void query.refetch()}
      />
    )
  }

  const byRung = query.data.bindings_by_rung
  const total = Object.values(byRung).reduce((sum, n) => sum + n, 0)

  // Every rung, including the ones at nought, in evidence order rather than by count. A ranking
  // would reorder the vocabulary as the data moved and make the chart harder to read across
  // visits; this axis is a fixed ladder and reads as one.
  const rows = RUNG_ORDER.filter((rung) => rung in byRung).map((rung) => ({
    key: rung,
    value: byRung[rung as keyof typeof byRung],
  }))

  const hint = (
    <InfoHint label="About provenance">
      Every binding Sync makes carries the rung that established it, and this is the mix across
      every open finding in this workspace. It is deliberately not a quality score: a static
      binding is not wrong, it is differently evidenced, and collapsing several kinds of evidence
      onto one axis is the thing this console exists not to do. A rung at nought here is a
      measured nought — the breakdown is filled from the rung vocabulary rather than from the rows
      found, so every rung was counted whether or not it occurred.
    </InfoHint>
  )

  if (total === 0) {
    return (
      <MetricPanel
        label="Provenance"
        hint={hint}
        caption="No open finding to attribute."
      >
        <p className="max-w-prose text-body text-ink-muted">
          A rung describes the binding a finding rests on, and this workspace has no open findings
          to describe. That is not a claim that nothing here is bound — it is the absence of
          anything to attribute.
        </p>
      </MetricPanel>
    )
  }

  return (
    <MetricPanel
      label="Provenance"
      hint={hint}
      metric={{ value: total.toLocaleString(), unit: "open findings attributed" }}
    >
      <RankedBars
        label="By rung of evidence"
        caption="Open findings by the rung that established the binding each rests on, strongest evidence first. A rung at nought was counted and found empty — this breakdown is filled from the rung vocabulary rather than from the rows found, so unlike almost every figure on this console a zero here is a measurement."
        rows={rows}
        unit="findings"
        colourByKey={false}
        annotate={(rung) => RUNG_MEANING[rung] ?? "an unlisted rung"}
        // The rungs partition every open finding exactly once, so a share of the total is a
        // claim this set supports -- which is not true of most rankings this component draws.
        share
      />
    </MetricPanel>
  )
}
