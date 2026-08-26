/**
 * The fleet Overview: a viewport-locked bento of five panes over the whole deployment.
 *
 * **One question per screen.** This level asks what is true across every codebase Sync holds,
 * and everything that answered a different question has moved to where that question is asked.
 *
 * **What this rebuild deleted, and why each was dead rather than merely crowded.** Three regions
 * on this screen could not draw under any address the console produces. `REPO_SCOPED_PATHS` is
 * empty, so nothing here is ever reached with `?repo_id=` bound, and the sole-codebase install
 * redirects to that codebase's own Overview before this component renders — which left the
 * totals line and the vendor cards returning `null` on every load, and the dependency-graph
 * region rendering a paragraph explaining why it had nothing to draw. The maps belong to a
 * codebase and are drawn full size on the codebase Overview; the counts they carried are in the
 * instrument bar. The four-tile fact grid went the same way for a different reason: the chrome
 * publishes those four figures on every screen now, so a grid of them here was the same fact
 * rendered twice at two weights.
 *
 * **The codebase list is not here.** Ruled twice by the owner: a directory of every codebase
 * answers "which workspace am I in", which the trail's workspace switcher answers, and the panel
 * it replaced printed one fleet-wide `total_findings` under every card — a false claim about
 * every repository but the one that figure happened to match. The listing moved whole to
 * Settings' Codebases group.
 *
 * **No page-level action.** The retired header carried "Review proposed patch", pointing at
 * whichever run happened to be the newest with an opened pull request. With nine change units
 * open that reads as *the* patch, which is a claim about priority the data does not make.
 *
 * **What stays, and why it is not clutter.** The standing limits, the composite-health refusal
 * and the three footnotes are the qualifications that make every figure on this screen readable.
 * They may be restyled and re-placed but never shortened: the absence footnote's referent moved
 * to Settings when the listing did, and pointing it at a list this screen no longer holds would
 * be a true sentence with a dead pointer.
 */

import { Navigate } from "react-router"

import { useDetectors, useRepositories } from "@/api/queries"
import { PanelPane } from "@/components/pane"
import { FindingsOverTimeBody } from "@/features/dashboards/findings-over-time-card"
import { CodebaseFactsBand } from "@/features/fleet/codebase-facts"
import { FleetKpis } from "@/features/fleet/fleet-facts"
import { RungUpgradeBody } from "@/features/fleet/rung-upgrade-card"
import { ScreenLimitsList } from "@/features/fleet/screen-limits"
import { ScreenFrame } from "@/layouts/screen-frame"
import type { StatusSegment } from "@/layouts/status-band"
import { overviewHref } from "@/lib/hrefs"

/** Which absence a figure is in, beside the glyph — a read still in flight is not a failed one. */
function absentScope(failed: boolean): string {
  return failed ? "did not answer" : "still asking"
}

/**
 * What every figure says when the index holds no codebase at all.
 *
 * Not a counted zero. Nothing has been read, so no finding, run, detector or repair attempt could
 * have been produced — five noughts here would be a clean bill of health for code nobody has
 * opened, which is what `reports/2026-08-17-gate-3-empty-state.md` measured on an empty graph and
 * what `fleet-facts.tsx` already refuses in the open-findings note.
 */
const NOTHING_INDEXED = "no codebase indexed, so nothing has been searched"

/**
 * The refusal, kept at the weight of the figures it refuses to average.
 *
 * It sits in a pane of its own rather than folded into the limits beside it, because its own last
 * clause names that neighbour — "the panel beside them" has to be a panel beside it.
 */
const HEALTH_REFUSAL =
  "There is no composite health figure here on purpose. A scalar that averaged three gates would " +
  'collapse "we could not check" onto the same axis as "we checked and it passed", which is the ' +
  "failure this console exists to replace. Every figure on this screen instead names its own " +
  "scope, and the panel beside them names what none of these figures can tell you at all."

export function FleetPage() {
  // One Overview, not two (owner, 2026-08-18): with exactly one codebase in the graph this
  // screen and the codebase screen were both answering as "Overview" from two addresses, and
  // clicking between them read as two different pages. The sole-codebase install lands on the
  // codebase's own overview; this screen remains the chooser the moment a second repository
  // exists, because choosing among several is the operator's act.
  const repositories = useRepositories()
  const repoIds = repositories.data?.repo_ids ?? []
  if (repoIds.length === 1) {
    return <Navigate replace to={overviewHref(repoIds[0])} />
  }

  return <FleetScreen />
}

/**
 * The screen itself, split from the redirect guard so the band's reads are unconditional hooks —
 * the sole-codebase install must not issue them on its way to somewhere else.
 */
function FleetScreen() {
  // Two of the reads `FleetKpis` issues, at the same keys, so the band states a figure already
  // being fetched rather than opening a request of its own.
  const repositories = useRepositories()
  const detectors = useDetectors()

  const nothingIndexed = repositories.isSuccess && repositories.data.repo_ids.length === 0

  /**
   * One count, gated on both reads it rests on rather than on its own.
   *
   * Every figure here reads two answers: the count, and whether the index holds a codebase at
   * all — because that is what decides whether the count is a measurement or an absence. Gating
   * on the count alone would state a nought against an index nobody has confirmed exists.
   */
  function figure(
    label: string,
    text: string | null,
    failed: boolean,
    scope: string,
  ): StatusSegment {
    if (nothingIndexed) {
      return { kind: "figure", label, value: null, scope: NOTHING_INDEXED }
    }
    if (!repositories.isSuccess || text === null) {
      return {
        kind: "figure",
        label,
        value: null,
        scope: absentScope(repositories.isError || failed),
      }
    }
    return { kind: "figure", label, value: text, scope }
  }

  // The band carries what the instrument bar cannot: the fifth figure, which has no cell up
  // there, and the three qualifications. Nothing is stated in both places -- a fact written twice
  // will disagree with itself the first time one of the two is edited.
  const status: StatusSegment[] = [
    figure(
      "Detectors with open findings",
      detectors.isSuccess ? detectors.data.detectors.length.toLocaleString() : null,
      detectors.isError,
      "fleet-wide, and open findings are the only findings the graph reads",
    ),
    {
      kind: "note",
      text: "A checkpoint age is staleness, not liveness — it says how old the evidence is not whether the run is still going. A change unit collapses findings sharing a vendor change against one repository set; the call-site grain is intact underneath and reachable from every row.",
    },
    {
      kind: "note",
      text: "A repository the index never indexed has no row — absence is not zero: a repository configured but never indexed has no row in the codebase list in Settings, and the same absence as a repository nobody ever configured.",
    },
    {
      kind: "note",
      text: "A finding retried three times writes three attempts here and counts once toward the corpus grain.",
    },
  ]

  return (
    <ScreenFrame status={status} layout="locked">
      {/* Outside the grid, a sibling before it: inside the chassis this is a portal into the top
          bar and no in-place DOM, and outside one its fallback grid must land above the bento
          rather than being auto-placed into a cell. */}
      <FleetKpis />

      {/* Row A is what the deployment found and what that evidence rests on; row B is what this
          screen refuses to compute and what it cannot answer at all. The refusal and the limits
          are adjacent because the refusal's last clause names the panel beside it. */}
      <div className="bento-lock grid min-h-0 min-w-0 flex-1 grid-cols-1 gap-8 lg:grid-cols-12">
        <PanelPane
          className="lg:col-span-8"
          label="What Sync has found, over time"
          bodyClassName="p-section"
        >
          <FindingsOverTimeBody />
        </PanelPane>

        <PanelPane
          className="lg:col-span-4"
          label="What this evidence rests on"
          bodyClassName="p-section"
        >
          <RungUpgradeBody />
        </PanelPane>

        <PanelPane className="lg:col-span-5" label="This codebase" bodyClassName="p-section">
          <CodebaseFactsBand />
        </PanelPane>

        <PanelPane className="lg:col-span-3" label="Health score policy" bodyClassName="p-section">
          <p className="text-body text-ink-muted">{HEALTH_REFUSAL}</p>
        </PanelPane>

        <PanelPane
          className="lg:col-span-4"
          label="What this screen cannot tell you"
          bodyClassName="p-section"
        >
          <ScreenLimitsList />
        </PanelPane>
      </div>
    </ScreenFrame>
  )
}
