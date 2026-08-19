/**
 * Dashboard O2: this workspace's open findings by the rung that established each binding.
 *
 * **This is the console's own argument rendered as a chart.** `CLAUDE.md`: every binding carries
 * the rung it came from, and a false positive that cannot be attributed to a rung cannot be
 * fixed. The rung has been a column on every table since the beginning; this is the first screen
 * that shows the shape of the whole set at a glance — how much of what Sync claims rests on a
 * static guess, how much on a resolved import, how much on observed traffic.
 *
 * **The payload already carried it.** `overview_summary` has emitted `bindings_by_rung` since
 * dashboard 2 was specified, `types.ts` has declared it, and nothing rendered it — the plan
 * filed this entry as needing API work and it needed none. A field a payload carries and no
 * screen draws is the `retracted_at` shape `CLAUDE.md` names: it typechecks, it gets maintained,
 * and nobody can tell it is unused.
 *
 * **Every rung in the vocabulary is present even at nought, and that is the server's doing** —
 * `overview_summary` fills the dict from `FINDING_RUNGS` rather than from the rows it found. So
 * unlike every other mix on this console, a rung missing here really would be a bug rather than
 * an absence, and the note beneath says so. `unattributed` is a member of that vocabulary and is
 * drawn like any other: it is the count the honesty rule exists to make visible, and hiding it
 * would be the one edit that defeats the chart's purpose.
 */

import { useOverview } from "@/api/queries"
import { InfoHint } from "@/components/info-hint"
import { MixDonutCard } from "@/components/charts/mix-donut-card"
import { ErrorState, LoadingState } from "@/components/states"

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
  // Zero-valued rungs are dropped from the arcs and named in the note instead. An arc of nought
  // is invisible but still takes a legend row and a colour slot, which reads as a member that
  // failed to render rather than as a member measured at none.
  const slices = Object.entries(byRung)
    .filter(([, count]) => count > 0)
    .map(([key, value]) => ({ key, value }))
  const atZero = Object.entries(byRung)
    .filter(([, count]) => count === 0)
    .map(([key]) => key)

  return (
    <MixDonutCard
      label="Provenance"
      hint={
        <InfoHint label="About provenance">
          Every binding Sync makes carries the rung that established it — <code>static</code> from
          the shape of the call alone, <code>resolved</code> from following the import,{" "}
          <code>observed</code> from traffic Sync actually saw, and <code>unattributed</code> where
          nothing recorded one. This is the mix across every open finding in this workspace. It is
          deliberately not a quality score: a static binding is not wrong, it is differently
          evidenced, and the reason this is a mix rather than a figure is that collapsing four
          kinds of evidence onto one axis is the thing this console exists not to do.
        </InfoHint>
      }
      caption="Open findings in this workspace, by the rung that established the binding each rests on. The centre is the sum of the arcs."
      slices={slices}
      unit="findings"
      absentNote={
        atZero.length === 0
          ? "Every rung in the vocabulary is drawn. The server fills this breakdown from the closed rung list rather than from the rows it found, so a rung missing here would be a defect rather than an absence."
          : `Measured at none: ${atZero.join(", ")}. That is a zero rather than an absence — the server fills this breakdown from the closed rung list, so these were counted and found empty.`
      }
      emptyHeadline="No open finding to attribute."
      emptyDetail="A rung describes the binding a finding rests on, and this workspace has no open findings to describe. That is not a claim that nothing here is bound — it is the absence of anything to attribute."
    />
  )
}
