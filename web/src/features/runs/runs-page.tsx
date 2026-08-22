/**
 * Runs: what the remediation pipeline attempted, and what it gave up on.
 *
 * Owner decision 30 gives Runs its own destination rather than a panel on the Overview. It
 * aggregates over Solution Workflow and is therefore **not a new level** —
 * `.claude/rules/console-hierarchy.md` permits a screen that aggregates over a level without
 * claiming to be one, the way detector attribution sits at `Errors & Incidents`. `GRAPH_LEVELS`
 * is untouched and no specification amendment was needed.
 *
 * ## The one thing this screen cannot do, stated rather than hidden
 *
 * **Every figure here is fleet-wide, and none of it can be narrowed to a workspace.** That is a
 * schema fact and not a gap in the transport: `migration_outcome` stores no `repo_id` at all, by a
 * decision that is exactly what makes the corpus safe to aggregate across customers
 * (`src/sync/api/app.py:20-22`). `/api/runs` and `/api/corpus/abandonment` take no scope parameter
 * because there is no column to filter on.
 *
 * That collides with the workspace mandate, which scopes every page and forbids a show-all. The
 * owner ruled the collision the way the API had already ruled it — *"that figure states its fleet
 * scope on screen instead"* — so the statement below is load-bearing. Without it this is a
 * fleet-wide count sitting under one workspace's breadcrumb, which is `codebases-panel`'s defect
 * returning: one number printed under every card it did not describe.
 *
 * The alternative was holding two finished, tested cards off the ship until the corpus grew a
 * repository column. That trades a stated limit for an unstated absence, and an unstated absence
 * is the thing this console exists to refuse.
 *
 * ## One attempt is one attempt
 *
 * `CLAUDE.md`'s grain rule bites hardest here, because this is the only screen whose rows *are*
 * attempts. A finding retried three times is three rows on this page and one finding on every
 * other, and a reader comparing the two without being told would reasonably conclude one of them
 * is broken. The footnote says it once, plainly, at the grain where the confusion happens.
 *
 * ## No status colour, and no rate
 *
 * Abandonment is rendered as counts by change kind, which is what the corpus holds. A percentage
 * would be a rate against a denominator that moves for reasons unrelated to the numerator, and a
 * coloured band across it would be the traffic light `CLAUDE.md` refuses three times over. The
 * cards carry their own vocabulary — a recorded outcome from a closed set, legible without colour —
 * which is the badge the rules permit.
 */

import { useParams } from "react-router"

import { DEFAULT_LIMIT } from "@/api/client"
import { useAbandonment, useRuns } from "@/api/queries"
import { InfoHint } from "@/components/info-hint"
import { CORPUS_SCOPE, ScopeChip } from "@/components/scope-chip"
import { AbandonReasonsCard } from "@/features/runs/abandon-reasons-card"
import { TierOutcomesCard } from "@/features/runs/tier-outcomes-card"
import { RunsCard } from "@/features/fleet/runs-table"
import { RunsKpisRegion } from "@/features/runs/runs-kpis-region"
import { tierOutcomes } from "@/features/runs/tier-outcomes-option"
import { Breadcrumbs } from "@/layouts/breadcrumbs"
import { ScreenFrame } from "@/layouts/screen-frame"
import type { StatusSegment } from "@/layouts/status-band"
import { UnknownRoute } from "@/layouts/unknown-route"
import { describeRecordWindow } from "@/lib/record-window"
import { useFilterParam } from "@/lib/use-filter-param"
import { useOffsetParam } from "@/lib/use-offset-param"

const QUESTION =
  "What the remediation pipeline attempted, what it abandoned, and which change kinds it does not handle mechanically."

export function RunsPage() {
  const { repoId } = useParams<{ repoId: string }>()
  // The band's two figures are read at the query keys the table and the corpus cards already use,
  // off the URL parameters those cards read — so this is the cache entry rather than a second
  // request, and the band can never describe a page the table is not showing.
  const [offset] = useOffsetParam("runs_offset")
  const [outcome] = useFilterParam("runs_outcome")
  const runs = useRuns({ limit: DEFAULT_LIMIT, offset, outcome })
  const abandonment = useAbandonment()

  // Built for every query state rather than for success alone: a band that appears only once an
  // answer arrives renders "not asked yet" and "asked and empty" as the same nothing.
  const status: StatusSegment[] = [
    runs.isSuccess
      ? {
          kind: "records",
          label: "Runs",
          text: describeRecordWindow(
            offset,
            runs.data.items.length,
            { count: runs.data.total, boundReached: false },
            "run",
            "runs",
          ),
        }
      : { kind: "none", why: runs.isError ? "the runs did not answer" : "asking for the runs" },
    abandonment.isSuccess
      ? {
          kind: "figure",
          label: "Corpus attempts",
          value: tierOutcomes(abandonment.data).totalAttempts.toLocaleString(),
          scope: "all workspaces",
        }
      : {
          kind: "none",
          why: abandonment.isError ? "the corpus did not answer" : "asking the corpus",
        },
    // Without this the band is a fleet-wide count under one workspace's breadcrumb, which is the
    // `codebases-panel` defect this screen's scope statement exists to refuse.
    {
      kind: "note",
      text: "Both counts are across every workspace, not this one — neither read can be narrowed to a workspace.",
    },
  ]

  if (repoId === undefined) return <UnknownRoute />

  return (
    <ScreenFrame status={status}>
    <section className="flex flex-col gap-8">
      <div className="flex flex-col gap-field">
        {/* Level name only: the scope trail in the top bar already draws the repository, and
            M7-W195 trimmed exactly this repetition from five other routes — the page keeps the
            segments the bar does not reach, which here is one. */}
        <Breadcrumbs trail={[{ label: "Runs" }]} />
        <p className="text-meta text-muted-foreground">{QUESTION}</p>
      </div>

      {/* Dashboard R1, at the page's top with every other screen's strip. It sits ABOVE the
          scope statement and states its own scope in the tiles' notes instead -- the statement
          below is about the corpus panels, and a strip placed under it would read as covered by
          a caveat that is not about it. */}
      <RunsKpisRegion />

      <RunsCard />

      {/* The corpus half. Its scope is a chip on each panel rather than the bordered paragraph
          that used to stand above it -- the claim is two words, the argument is one hover, and it
          is written once in `CORPUS_SCOPE` rather than three times across three screens. */}
      <div className="flex items-center gap-row">
        <h2 className="text-section">The repair corpus</h2>
        {/* A claim, not an argument: one row is one attempt, and a finding retried three times
            is three rows here and one finding everywhere else. Short and visible; the why is
            in the ⓘ beside it. */}
        <span className="text-meta text-ink-muted">one row is one attempt, and counts once as a finding</span>
        <ScopeChip scope="all workspaces">{CORPUS_SCOPE}</ScopeChip>
        <InfoHint label="About the repair corpus">
          One row is one <em>attempt</em>, not one finding: a finding retried three times writes
          three attempts and counts once toward the corpus grain, so a total here is larger than
          the finding count on every other screen and neither is wrong. An abandoned attempt is
          data rather than a failure to hide — the reason code is queryable, and abandonment by
          change kind is how routing learns which changes are not mechanically safe to attempt.
        </InfoHint>
      </div>
      <div className="grid auto-rows-fr gap-8 xl:grid-cols-2">
        <AbandonReasonsCard />
        <TierOutcomesCard />
      </div>

    </section>
    </ScreenFrame>
  )
}
