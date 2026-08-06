/**
 * Which detector said what, and on what evidence.
 *
 * The console renders findings today and never who raised one or what kind of claim it
 * was making. `CLAUDE.md` requires a false positive be attributable to a rung, and the
 * rung is a column on the finding rather than a join -- this screen is that rule made
 * visible one level up, across every detector rather than one finding at a time.
 *
 * Reads `sync.dashboard.graph_views.detector_accountability` through `GET /api/detectors`,
 * never `GraphSurface`: detector attribution is an aggregate over open findings, not a
 * question about one finding an agent is already pointed at.
 *
 * A `repo_id` in the query string narrows every figure on the screen to one repository, and
 * the heading and the sentences below say which scope is on screen. Both are real questions --
 * "which detector is producing my false positives" is asked of one codebase at least as often
 * as of the fleet — and the screen never answers one while appearing to answer the other.
 */

import { useSearchParams } from "react-router"

import { DetectorAccountability } from "@/features/detectors/detector-accountability"
import { Breadcrumbs } from "@/layouts/breadcrumbs"

export function DetectorsPage() {
  const [searchParams] = useSearchParams()
  const repoId = searchParams.get("repo_id")

  return (
    <section className="flex flex-col gap-8">
      <div className="flex flex-col gap-section">
        <Breadcrumbs
          trail={
            repoId === null
              ? [{ label: "Fleet", to: "/" }, { label: "Detectors" }]
              : [
                  { label: "Fleet", to: "/" },
                  { label: repoId, to: `/repositories/${encodeURIComponent(repoId)}` },
                  { label: "Detectors" },
                ]
          }
        />
        <h1 className="text-page">Detectors</h1>
        <p className="max-w-prose text-body text-muted-foreground">
          Every detector's open findings, broken down by the rung of evidence behind its
          claims. The rung breakdown is the substance: a detector whose findings rest
          entirely on <code className="font-mono">static</code> evidence is making a
          different kind of claim from one correlating watched traffic, and an operator
          weighing a false positive needs that difference before weighing anything else.
        </p>
        <p className="max-w-prose text-body text-muted-foreground">
          This is not a leaderboard and carries no precision or accuracy figure: detectors
          are not competing, and a ratio computed from open findings alone, with no labelled
          corpus behind it, would measure nothing.
        </p>
        <p className="max-w-prose text-body text-muted-foreground">
          A row here exists only for a detector that has raised an open finding -- the graph
          keeps no registry of which detectors are installed, only the findings they have
          written. A detector currently raising nothing does not appear, and that absence is
          indistinguishable from a detector that does not exist.
        </p>
        {repoId === null ? (
          <p className="max-w-prose text-body text-muted-foreground">
            This is a fleet-wide aggregate, not a repository's own answer: nothing selected a
            repository on the way here, so a detector's tally below counts its open findings
            across every repository the index has seen at once. Open this screen from a
            repository to narrow it to that codebase.
          </p>
        ) : (
          <p className="max-w-prose text-body text-muted-foreground">
            Every figure below counts open findings in{" "}
            <span className="font-mono">{repoId}</span> and in no other repository. A detector
            with no row here may still be raising findings elsewhere in the fleet — this screen
            cannot tell you that, because it did not ask.
          </p>
        )}
      </div>
      <DetectorAccountability repoId={repoId} />
    </section>
  )
}
