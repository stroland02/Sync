/**
 * Trends: every measured series this deployment holds, on one viewport-locked surface.
 *
 * **Rebuilt 2026-08-26 from a scrolling column of five cards into a locked bento of five panes.**
 * The old screen stacked What-Sync-found above What-the-vendors-published above What-Sync-tried,
 * and the argument those three make is a *comparison* — a day with many changes and no findings
 * is the product working rather than a gap. A comparison read one card at a time down a scrollbar
 * is not a comparison, which is what the flow layout cost. Row A now carries the three in causal
 * order left to right: what the vendors published, what Sync found in it, what Sync did about it.
 * Row B carries the two rankings under them — what traffic actually called, and what a human set
 * aside. Nothing on this screen is below a fold; each pane scrolls its own body.
 *
 * **Every form on this screen is derived from its payload** (`daily-series.ts`). Measured here on
 * 2026-08-26, all three series returned exactly one day and the changes payload stacked
 * thirty-four integrations onto it — a stacked column over one tick, under a legend taller than
 * the bar. `web/CLAUDE.md`'s chart law is the authority the reference loses to: bars for rankings
 * and for sets with meaningful zeros, a log scale only where the set spans orders of magnitude and
 * said so on the chart, and no percentage without its denominator. There is none here: every
 * figure on this screen is a count.
 *
 * **The status band is one segment per pane, because there is no instant at which this page is
 * loaded.** Five panes answer from four independent reads — the top-bar strip shares its two with
 * the two series beside it — so a single count would be true of one pane while the others were
 * still asking. Each segment carries its own absence and says in words which absence it is: still
 * asking, did not answer, or never measured are three facts and the glyph alone renders them as
 * one.
 */

import { useQuery } from "@tanstack/react-query"
import { Activity, Radio, Wrench } from "lucide-react"
import { useParams } from "react-router"

import { useFindingsOverTime, useRepositoryObserved } from "@/api/queries"
import { InfoHint } from "@/components/info-hint"
import { CORPUS_SCOPE, ScopeChip } from "@/components/scope-chip"
import { DailySeriesPane } from "@/features/dashboards/daily-series-pane"
import { fetchChangesOverTime } from "@/features/dashboards/daily-series"
import { DismissedPane } from "@/features/dashboards/dismissed-pane"
import { observedVolumeByOperation } from "@/features/dashboards/observed-volume-option"
import { CALLS_LIMIT, ObservedVolumePane } from "@/features/dashboards/observed-volume-pane"
import { TrendsKpis } from "@/features/dashboards/trends-kpis"
import { AttemptsByTier, fetchRemediationActivity } from "@/features/workflows/remediation-activity"
import { RemediationFlow } from "@/features/workflows/remediation-flow"
import { ScreenFrame } from "@/layouts/screen-frame"
import type { StatusSegment } from "@/layouts/status-band"
import { UnknownRoute } from "@/layouts/unknown-route"

/** Which absence a figure is in, beside the glyph — a read still in flight is not a failed one. */
function absentScope(failed: boolean): string {
  return failed ? "did not answer" : "still asking"
}

export function MetricsPage() {
  const { repoId } = useParams<{ repoId: string }>()

  // The panes' own keys, so the band reads the answers already on screen rather than opening
  // four more requests for them.
  const findings = useFindingsOverTime(null)
  const changes = useQuery({
    queryKey: ["integration-changes", "over-time"],
    queryFn: ({ signal }) => fetchChangesOverTime(signal),
  })
  const attempts = useQuery({
    queryKey: ["corpus-activity"],
    queryFn: ({ signal }) => fetchRemediationActivity(signal),
  })
  const observed = useRepositoryObserved(repoId ?? "", { callsLimit: CALLS_LIMIT })

  if (repoId === undefined) return <UnknownRoute />

  const activeDays =
    findings.isSuccess && changes.isSuccess
      ? new Set([
          ...findings.data.days.map((day) => day.day),
          ...changes.data.days.map((day) => day.day),
        ]).size
      : null

  const attemptDays = attempts.data?.days ?? []
  const attemptCount = attempts.isSuccess
    ? attemptDays.reduce(
        (total, day) => total + Object.values(day.counts).reduce((sum, n) => sum + n, 0),
        0,
      )
    : null

  const volume = observed.isSuccess ? observedVolumeByOperation(observed.data) : null

  const status: StatusSegment[] = [
    {
      kind: "figure",
      label: "Days with activity",
      value: activeDays === null ? null : activeDays.toLocaleString(),
      scope:
        activeDays === null
          ? absentScope(findings.isError || changes.isError)
          : "days either series recorded something, never the length of the window",
    },
    {
      kind: "figure",
      label: "Findings recorded",
      value: findings.isSuccess ? findings.data.total.toLocaleString() : null,
      scope: findings.isSuccess
        ? "fleet-wide, including findings since closed"
        : absentScope(findings.isError),
    },
    {
      kind: "figure",
      label: "Changes published",
      value: changes.isSuccess ? changes.data.total.toLocaleString() : null,
      scope: changes.isSuccess
        ? "fleet-wide, by the watched integrations"
        : absentScope(changes.isError),
    },
    {
      kind: "figure",
      label: "Repair attempts",
      value: attemptCount === null ? null : attemptCount.toLocaleString(),
      scope:
        attemptCount === null
          ? absentScope(attempts.isError)
          : "every workspace rather than this one — one row is one attempt, not one finding",
    },
    {
      kind: "figure",
      // Never-measured is an absence and says so in words (B157): a repository nothing has looked
      // at would otherwise carry the same bare glyph as one whose read is still in flight.
      label: "Observed-call rows",
      value: volume?.telemetryAttached ? volume.totalRows.toLocaleString() : null,
      scope: !volume
        ? absentScope(observed.isError)
        : volume.telemetryAttached
          ? repoId
          : `never measured — no telemetry attached to ${repoId}`,
    },
  ]

  // Every status any day reached, so one outcome is the same colour on every day it appears.
  const outcomes = [...new Set(attemptDays.flatMap((day) => Object.keys(day.counts)))].sort()

  return (
    <ScreenFrame
      status={status}
      layout="locked"
      subtitle="What the integrations published, what Sync found in it, and what Sync did about it — read left to right."
    >
      {/* Outside the grid and before it: inside the chassis this renders a portal into the top
          bar and no in-place DOM at all, and outside one its fallback strip must land above the
          bento rather than being auto-placed into a cell. */}
      <TrendsKpis />

      {/* `.bento-lock` gives the two rows their tracks at 1024x720 and above, and hands the grid
          its own scrollbar below that — a short window degrades to a stacked column rather than
          clipping panes the chassis has stopped scrolling. Row A takes the taller track: three
          charts need height, and the two rankings under them do not. */}
      <div className="bento-lock-3 grid min-h-0 min-w-0 flex-1 grid-cols-1 gap-8 lg:grid-cols-12">
        <DailySeriesPane
          className="lg:col-span-4"
          label="What the integrations published"
          icon={Radio}
          hint={
            <InfoHint label="About integration changes">
              Every change the watched integrations published, on the day Sync detected it.
              Fleet-wide rather than scoped to this workspace, because what a vendor publishes is a
              fact about the vendor. These are detection dates, never publication dates — the graph
              holds no publication date, and the distance between the two is however long a feed
              took to arrive. A height over an <code className="font-mono">oasdiff</code> source is
              at-least-once rather than a measurement: that tool returns a different answer on
              consecutive runs over identical bytes, which is this pipeline&rsquo;s one recorded
              exemption from converging.
            </InfoHint>
          }
          days={changes.data?.days ?? []}
          members={changes.data?.vendors ?? []}
          stackId="changes"
          unit="changes"
          memberNoun="integration"
          total={changes.data?.total ?? 0}
          // The one set on this screen whose members are integrations: a vendor's hue is its
          // identity on the map and in every chart, so it carries a dimension length cannot.
          colourByKey
          absence="no adapter has delivered a change yet, which is the absence of a record rather than a stretch of quiet vendors."
          claim="Fleet-wide · detection dates, never publication dates · a missing day is not a nought."
          note={
            <>
              A day with no bar is a day nothing was recorded, which may be a day no vendor
              published or a day nothing fetched — the graph does not record that an adapter ran,
              so it cannot tell you which.
            </>
          }
        />

        <DailySeriesPane
          className="lg:col-span-4"
          label="What Sync found in it"
          icon={Activity}
          hint={
            <InfoHint label="About findings over time">
              Findings by severity, on the day Sync recorded them. This is Sync&rsquo;s own
              timeline rather than the vendors&rsquo; — a finding sits on the day a detector raised
              the claim, not the day the API changed, and nothing in the graph carries a
              publication date to draw instead. The count is of findings as produced, including
              ones since patched or abandoned: a series filtered to what is still open would shrink
              its own past every time work landed, so the outstanding count sits beside it in the
              stats bar rather than replacing it.
            </InfoHint>
          }
          days={findings.data?.days ?? []}
          members={findings.data?.severities ?? []}
          stackId="findings"
          unit="findings"
          memberNoun="severity"
          total={findings.data?.total ?? 0}
          absence="the graph holds no finding at any severity. This is a read that found nothing rather than a read that did not happen."
          claim="Fleet-wide · Sync's own dates · counted as produced, including findings since closed."
          note={
            <>
              A day with no bar is a day nothing was recorded, never a day measured at nought:
              nothing here records that a detector ran, so an absent day may be one with no changes
              or one with no run, and those are different facts.
            </>
          }
        />

        <DailySeriesPane
          className="lg:col-span-4"
          label="What Sync did about it"
          icon={Wrench}
          hint={
            <InfoHint label="About repair attempts">
              Every repair the pipeline attempted, on the day it was recorded, by what the attempt
              reached. One unit is one <em>attempt</em>, not one finding — a finding retried three
              times contributes three, so a total here is larger than the finding count on every
              other screen and neither is wrong. Dated by when the attempt happened rather than by
              when a pull request merged, because a series keyed on the merge date would drop every
              attempt that never opened one, which is most of them. Rehearsals halt before the
              remote and are excluded. This is a count and never a success rate: how often a tier
              succeeds is the merge-rate axis on Corpus, computed over a denominator these counts
              do not have.
            </InfoHint>
          }
          days={attemptDays}
          members={outcomes}
          stackId="attempts"
          // Every band here means an outcome, so every band reads the reserved ramp rather than a
          // categorical slot. Slot order once painted `abandoned` in the good ink.
          outcomeRamp
          unit="attempts"
          memberNoun="outcome"
          total={attemptCount ?? 0}
          absence="no repair attempt has been recorded on any day. The corpus is young rather than empty of results."
          claim={
            <span className="flex flex-wrap items-center gap-row">
              <ScopeChip scope="all workspaces">{CORPUS_SCOPE}</ScopeChip>
              <span>One row is one attempt, not one finding · a count, never a rate.</span>
            </span>
          }
          note={
            <>
              Rehearsals halt before the remote and are excluded. How often a tier succeeds is the
              merge-rate axis on Corpus, computed over a denominator these counts do not have.
            </>
          }
        />

        <ObservedVolumePane className="lg:col-span-8" />
        <DismissedPane className="lg:col-span-4" />

        {/* Both arrived here when Solutions became a board, and the third row arrived with them:
            `.bento-lock` declares two tracks and `overflow: hidden`, so a third row would have been
            clipped rather than scrolled. The utilities above win over it -- Tailwind's `utilities`
            layer outranks `components`, which is the same precedence that left the viewport steps
            inert until CI-W647. `RemediationFlow` counts findings rather than runs, so it is the
            only panel that can show a finding nothing has ever attempted; Solutions links here for
            it by name, and a link to a panel that is not on the page is a promise this console
            would be breaking on screen. */}
        <div className="lg:col-span-7">
          <RemediationFlow repoId={repoId} />
        </div>
        <div className="lg:col-span-5">
          <AttemptsByTier />
        </div>
      </div>
    </ScreenFrame>
  )
}
