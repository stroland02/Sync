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
 *
 * ## Ported onto the chassis and the vendored substrate by M7-W177
 *
 * `docs/superpowers/briefs/2026-08-07-substrate-errors-incidents.md` is the mapping table this
 * port was gated on. Read that before porting a level, not this docstring.
 *
 * **The chassis arrives here in the same work item as the substrate, because this level never
 * had it.** The screen opened on a bare 22px heading while the route's own question — the only
 * sentence anywhere that says who this screen is for rather than what it counts — sat unread in
 * `lib/routes.ts`.
 *
 * **A `ControlBar` carries the scope, where Signals refused one.** The difference is that this
 * level's scope is bimodal: `/detectors` answers for the fleet or for one codebase depending on a
 * query parameter, and the two answers are different numbers under the same heading. The
 * paragraph that qualifies the scope stays beside it — the bar is scanned, the sentence carries
 * the why, and both read the one search parameter so they cannot disagree.
 *
 * **The action slot stays empty.** The candidate was the link to the fleet's or the repository's
 * own findings, and it travels with a qualification a button cannot carry: no route filters
 * findings by detector yet, so that link is the nearest thing rather than the next step. It is a
 * sentence, above the cards, in `detector-accountability.tsx`.
 *
 * ## The bar gains its one control in M7-W195
 *
 * `docs/superpowers/briefs/2026-08-07-substrate-fidelity-task-4.md` is the inventory this came from.
 * The gap report measured zero controls in this bar, and the honest count of what this level can
 * narrow is one: `?repo_id`, which is the only parameter `GET /api/detectors` takes.
 *
 * **Half of that control is already one bar above and the other half was nowhere.** The top bar's
 * repository switcher writes `?repo_id` in place on this route — `/detectors` is in
 * `REPO_SCOPED_PATHS` — so a second picker here would be the same control drawn twice. What the
 * switcher has no entry for is leaving the scope: its list is repositories, and the fleet is not
 * one of them, so a scoped screen's only way back to the fleet-wide answer was the browser's Back
 * button. That is the control the bar carries, and only while a scope is set. Unscoped, the bar
 * carries its sentence, because the scope is already at its widest.
 */

import { useSearchParams } from "react-router"

import { Button } from "@/components/ui/button"
import { DetectorAccountability } from "@/features/detectors/detector-accountability"
import { Breadcrumbs } from "@/layouts/breadcrumbs"
import { ControlBar } from "@/layouts/control-bar"
import { PageHeader } from "@/layouts/page-header"
import { routeQuestion } from "@/lib/routes"
import { useClearFilters } from "@/lib/use-filter-param"

/** This screen's own entry in the registry, so `PageHeader` renders the registry's sentence. */
const ROUTE_PATH = "/detectors"

/** The scope key, the only parameter `GET /api/detectors` takes. */
const REPO_KEY = "repo_id"

export function DetectorsPage() {
  const [searchParams] = useSearchParams()
  const repoId = searchParams.get(REPO_KEY)
  // No offsets to reset: this route paginates nothing, so widening the scope changes which rows
  // exist without moving any window over them.
  const widen = useClearFilters([REPO_KEY])

  return (
    <section className="flex flex-col gap-8">
      <div className="flex flex-col gap-section">
        <PageHeader
          title="Detectors"
          question={routeQuestion(ROUTE_PATH)}
          // Fleet and the repository are the top bar's, derived from this same address. What is
          // left is the level this screen is, which the bar does not reach — its trail stops at
          // the vendor. M7-W195.
          trail={<Breadcrumbs trail={[{ label: "Detectors" }]} />}
        />
        <ControlBar>
          <div className="flex min-w-0 flex-col gap-field">
            <span className="furniture text-meta text-ink-muted">Scope</span>
            {repoId === null ? (
              <span className="text-body">Every repository the index has seen.</span>
            ) : (
              <div className="flex flex-wrap items-center gap-row">
                <span className="font-mono text-body break-words">{repoId}</span>
                <Button type="button" size="sm" variant="outline" onClick={widen}>
                  Widen to every repository
                </Button>
              </div>
            )}
          </div>
        </ControlBar>
      </div>

      {/* What the screen measures beside what it refuses to measure and what it cannot see. A
          reader who takes the rung breakdown as a ranking has misread the screen, and the column
          on the right is where that reading is closed off before the figures are reached. */}
      <div className="grid gap-8 lg:grid-cols-2">
        <p className="max-w-prose text-body text-muted-foreground">
          Every detector's open findings, broken down by the rung of evidence behind its
          claims. The rung breakdown is the substance: a detector whose findings rest
          entirely on <code className="font-mono">static</code> evidence is making a
          different kind of claim from one correlating watched traffic, and an operator
          weighing a false positive needs that difference before weighing anything else.
        </p>
        <div className="flex flex-col gap-field">
          <p className="max-w-prose text-body text-muted-foreground">
            This is not a leaderboard and carries no precision or accuracy figure: detectors
            are not competing, and a ratio computed from open findings alone, with no labelled
            corpus behind it, would measure nothing.
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
      </div>

      <DetectorAccountability repoId={repoId} />
    </section>
  )
}
