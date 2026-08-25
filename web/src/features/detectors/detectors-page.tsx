/**
 * Which detector said what, and on what evidence.
 *
 * Reads `sync.dashboard.graph_views.detector_accountability` through `GET /api/detectors`, whose
 * only parameter is `repo_id` — not `GraphSurface`, because attribution is an aggregate over open
 * findings rather than a question about one finding.
 */

import { AutomationPanel } from "@/features/tickets/automation-panel"
import { useParams } from "react-router"

import { useDetectors } from "@/api/queries"
import { InfoHint } from "@/components/info-hint"
import { ScopeChip } from "@/components/scope-chip"

import { ScreenFrame } from "@/layouts/screen-frame"
import type { StatusSegment } from "@/layouts/status-band"
import { UnknownRoute } from "@/layouts/unknown-route"

import { DetectorAccountability } from "@/features/detectors/detector-accountability"
import { RungMixCard } from "@/features/detectors/rung-mix-card"


export interface DetectorsPageProps {
  readonly question?: string
}

export function DetectorsPage() {
  // The route is the scope: this read `searchParams.get("repo_id")` while the route is
  // `/repositories/:repoId/detectors`, so an address naming a repository still rendered "Every
  // repository the index has seen".
  const { repoId } = useParams<{ repoId: string }>()
  // The same query key `DetectorAccountability` already holds, so the band costs no request.
  const attribution = useDetectors(repoId)
  if (repoId === undefined) return <UnknownRoute />

  // Labelled "attributed", never "open": `total_open_findings` here and `severity_total` on
  // Findings count one population. Built for every query state — a band rendered only on success
  // shows "not asked yet" and "asked and empty" as the same nothing.
  const status: StatusSegment[] = attribution.isSuccess
    ? [
        {
          kind: "listing",
          label: "attributed",
          text:
            attribution.data.detectors.length === 0
              ? `No open finding in ${repoId} is attributed to any detector.`
              : `${attribution.data.total_open_findings.toLocaleString()} open ${
                  attribution.data.total_open_findings === 1 ? "finding" : "findings"
                } in ${repoId}, attributed across ${attribution.data.detectors.length} ${
                  attribution.data.detectors.length === 1 ? "detector" : "detectors"
                }.`,
        },
      ]
    : [
        {
          kind: "none",
          why: attribution.isError
            ? "the detector attribution did not answer"
            : "asking for the detector attribution",
        },
      ]

  return (
    <ScreenFrame status={status}>
    <section className="flex flex-col gap-8">
      {/* The automatic lane leads (owner ruling): what the platform did without a human. */}
      <AutomationPanel repoId={repoId} />


      {/* The workspace-wide rung mix, moved off the Overview 2026-08-19. */}
      <RungMixCard repoId={repoId} />

      <div className="flex items-center gap-row">
        <h2 className="text-section">Detector attribution</h2>
        <ScopeChip scope="this workspace">
          Every figure counts open findings in <span className="font-mono">{repoId}</span> and in no
          other. A detector with no row here may still be raising findings elsewhere — this screen
          cannot tell you that, because it did not ask.
        </ScopeChip>
        <InfoHint label="About detector attribution">
          Every detector&rsquo;s open findings, broken down by the rung of evidence behind its
          claims. The rung breakdown is the substance: a detector whose findings rest entirely on{" "}
          <code className="font-mono">static</code> evidence is making a different kind of claim
          from one correlating watched traffic, and an operator weighing a false positive needs
          that difference first. This is not a leaderboard and carries no precision or accuracy
          figure — detectors are not competing, and a ratio computed from open findings alone, with
          no labelled corpus behind it, would measure nothing.
        </InfoHint>
      </div>

      <DetectorAccountability repoId={repoId} />
    </section>
    </ScreenFrame>
  )
}
