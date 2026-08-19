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

import { useParams } from "react-router"

import { PageTabs, metricsTabs } from "@/components/page-tabs"

import { UnknownRoute } from "@/layouts/unknown-route"

import { DetectorAccountability } from "@/features/detectors/detector-accountability"
import { DetectorsDashboards } from "@/features/detectors/detectors-dashboards"
import { ControlBar } from "@/layouts/control-bar"


export interface DetectorsPageProps {
  readonly question?: string
}

export function DetectorsPage() {
  // **The route is the scope, and it used to be a query string.** This read
  // `searchParams.get("repo_id")` while the route is `/repositories/:repoId/detectors`, so an
  // address that named a repository could still render "Every repository the index has seen" --
  // the screen contradicting its own URL, on a console whose whole argument is that it tells you
  // the truth about what it checked. There is one source of scope now and the router owns it.
  const { repoId } = useParams<{ repoId: string }>()
  if (repoId === undefined) return <UnknownRoute />

  return (
    <section className="flex flex-col gap-8">
      <PageTabs label="Metrics" tabs={metricsTabs(repoId)} />
      <div className="flex flex-col gap-section">
        <ControlBar>
          <div className="flex min-w-0 flex-col gap-field">
            <span className="furniture text-meta text-ink-muted">Scope</span>
            {/* No widen control and no fleet-wide reading. The owner's ruling is that every page
                corresponds to a workspace, so "every repository" is not a mode this screen has --
                switching workspace is the switcher's job, in chrome. */}
            <span className="font-mono text-body break-words">{repoId}</span>
          </div>
        </ControlBar>
      </div>

      {/* Dashboards D1 and D2. This screen carried one chart and a table; the strip says how much
          was attributed and to how many detectors, and the ranking says which detector is loudest
          -- which the rung chart beneath deliberately does not answer. */}
      <DetectorsDashboards repoId={repoId} />

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
          <p className="max-w-prose text-body text-muted-foreground">
            Every figure below counts open findings in{" "}
            <span className="font-mono">{repoId}</span> and in no other workspace. A detector with
            no row here may still be raising findings in another workspace — this screen cannot
            tell you that, because it did not ask.
          </p>
        </div>
      </div>

      <DetectorAccountability repoId={repoId} />
    </section>
  )
}
