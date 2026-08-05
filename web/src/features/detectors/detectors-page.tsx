/**
 * Which detector said what, and on what evidence.
 *
 * The console renders findings today and never who raised one or what kind of claim it
 * was making. `CLAUDE.md` requires a false positive be attributable to a rung, and the
 * rung is a column on the finding rather than a join -- this screen is that rule made
 * visible one level up, across every detector rather than one finding at a time.
 *
 * Reads `sync.dashboard.graph_views.detector_accountability` through `GET /api/detectors`,
 * never `GraphSurface`: detector attribution is a fact about every open finding, not a
 * question about one repository an agent is already pointed at.
 */

import { DetectorAccountability } from "@/features/detectors/detector-accountability"
import { Breadcrumbs } from "@/layouts/breadcrumbs"

export function DetectorsPage() {
  return (
    <section className="flex flex-col gap-4">
      <Breadcrumbs trail={[{ label: "Detectors" }]} />
      <h1 className="text-page">Detectors</h1>
      <p className="text-body text-muted-foreground">
        Every detector's open findings, broken down by the rung of evidence behind its
        claims. The rung breakdown is the substance: a detector whose findings rest
        entirely on <code className="font-mono">static</code> evidence is making a
        different kind of claim from one correlating watched traffic, and an operator
        weighing a false positive needs that difference before weighing anything else.
      </p>
      <p className="text-body text-muted-foreground">
        This is not a leaderboard and carries no precision or accuracy figure: detectors
        are not competing, and a ratio computed from open findings alone, with no labelled
        corpus behind it, would measure nothing.
      </p>
      <p className="text-body text-muted-foreground">
        A row here exists only for a detector that has raised an open finding -- the graph
        keeps no registry of which detectors are installed, only the findings they have
        written. A detector currently raising nothing does not appear, and that absence is
        indistinguishable from a detector that does not exist.
      </p>
      <DetectorAccountability />
    </section>
  )
}
