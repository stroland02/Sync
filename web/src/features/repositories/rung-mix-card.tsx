/**
 * Dashboard O2: this workspace's open findings by the rung that established each binding.
 *
 * **This is the console's own argument rendered as a chart.** `CLAUDE.md`: every binding carries
 * the rung it came from, and a false positive that cannot be attributed to a rung cannot be
 * fixed. The rung has been a column on every table since the beginning; this is the first screen
 * that shows the shape of the whole set at a glance — how much of what Sync claims rests on a
 * static guess, how much on a resolved import, how much on observed traffic.
 *
 * ## What was wrong with the first version, and why the fix is not cosmetic
 *
 * It shipped as a donut with zero-valued rungs dropped from the arcs and named in a footnote.
 * Against this repository's own graph that is 24 findings, all `static`, and four rungs at
 * nought — so it drew **one closed ring** with a one-entry legend and moved four of the five
 * facts into small print. The owner reported it as looking unbuilt, and it was: a ring at 100%
 * is the same picture for 24 findings as for 24,000, and the four numbers it hid are the ones a
 * reader came for.
 *
 * Two things were confused, and separating them is the fix.
 *
 * - **A zero here is a measurement, not an absence.** `overview_summary` fills this dict from
 *   `FINDING_RUNGS` rather than from the rows it found, so `resolved: 0` means *Sync counted and
 *   found none*. That is the opposite of the situation everywhere else on this console, where a
 *   missing key means nobody looked — and it is exactly the distinction the four honesty rules
 *   exist to keep. Hiding measured zeros in a footnote threw away real information to protect a
 *   rule that did not apply.
 * - **A one-member mix is not a mix.** The donut is kept for the case it was built for and
 *   dropped below two members, where a sentence says more.
 *
 * So the panel now always renders every rung with its count and share, and the donut appears
 * above it only when there is a mix to draw.
 *
 * **`unattributed` is drawn like any other rung.** It is the count the honesty rule exists to
 * make visible, and hiding it would be the one edit that defeats the panel's purpose.
 */

import { useOverview } from "@/api/queries"
import { InfoHint } from "@/components/info-hint"
import { MixDonutCard } from "@/components/charts/mix-donut-card"
import { ErrorState, LoadingState } from "@/components/states"
import { seriesScale } from "@/lib/palette"

/** What each rung means, in one clause, so the panel explains itself without the ⓘ. */
const RUNG_MEANING: Record<string, string> = {
  static: "from the shape of the call alone",
  resolved: "from following the import to its package",
  observed: "from traffic Sync actually saw",
  unresolved: "the import was followed and led nowhere",
  unattributed: "written before the rung column existed",
}

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
  const slices = Object.entries(byRung)
    .filter(([, count]) => count > 0)
    .map(([key, value]) => ({ key, value }))
  // Sorted by key so a rung sits in the same row and wears the same colour on every visit, which
  // is the rule the donut's own arcs follow.
  const rows = Object.entries(byRung).sort(([a], [b]) => a.localeCompare(b))
  const colour = seriesScale(rows.map(([rung]) => rung))

  return (
    <MixDonutCard
      label="Provenance"
      hint={
        <InfoHint label="About provenance">
          Every binding Sync makes carries the rung that established it, and this is the mix
          across every open finding in this workspace. It is deliberately not a quality score: a
          static binding is not wrong, it is differently evidenced, and the reason this is a mix
          rather than a figure is that collapsing several kinds of evidence onto one axis is the
          thing this console exists not to do. A rung at nought here is a measured nought — the
          breakdown is filled from the rung vocabulary rather than from the rows found, so every
          rung was counted whether or not it occurred.
        </InfoHint>
      }
      caption="Open findings in this workspace, by the rung that established the binding each rests on."
      slices={slices}
      unit="findings"
      soleMemberNote={(rung, value) => (
        <>
          Every one of the {value.toLocaleString()} open findings here rests on a{" "}
          <span className="font-mono">{rung}</span> binding — {RUNG_MEANING[rung] ?? "an unlisted rung"}.
          No finding rests on any other rung, and the counts below are measured rather than
          missing.
        </>
      )}
      breakdown={
        total === 0 ? undefined : (
          <div className="flex flex-col gap-field">
            {rows.map(([rung, count]) => (
              <div key={rung} className="flex items-baseline gap-row">
                <span
                  aria-hidden
                  className="h-[0.6rem] w-[0.6rem] shrink-0 rounded-[2px]"
                  // A rung at nought keeps its slot and loses its fill: the row is still there,
                  // which is the point, and the empty swatch says it contributed nothing.
                  style={{
                    background: count > 0 ? colour(rung) : "transparent",
                    border: count > 0 ? undefined : "1px solid currentColor",
                  }}
                />
                <span className="w-[7rem] shrink-0 font-mono text-meta text-ink">{rung}</span>
                <span className="w-[4rem] shrink-0 text-right text-meta tabular-nums text-ink">
                  {count.toLocaleString()}
                </span>
                <span className="w-[3.5rem] shrink-0 text-right text-meta tabular-nums text-ink-muted">
                  {total === 0 ? "—" : `${Math.round((count / total) * 100)}%`}
                </span>
                <span className="min-w-0 text-meta text-ink-muted">
                  {RUNG_MEANING[rung] ?? "an unlisted rung"}
                </span>
              </div>
            ))}
          </div>
        )
      }
      absentNote={`Counted over all ${total.toLocaleString()} open findings. A rung at nought was counted and found empty, not skipped — this breakdown is filled from the rung vocabulary rather than from the rows found, so unlike almost every other figure on this console a zero here is a measurement.`}
      emptyHeadline="No open finding to attribute."
      emptyDetail="A rung describes the binding a finding rests on, and this workspace has no open findings to describe. That is not a claim that nothing here is bound — it is the absence of anything to attribute."
    />
  )
}
