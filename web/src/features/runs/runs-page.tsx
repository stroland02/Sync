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

import { PageTabs, logsTabs } from "@/components/page-tabs"
import { AbandonReasonsCard } from "@/features/runs/abandon-reasons-card"
import { TierOutcomesCard } from "@/features/runs/tier-outcomes-card"
import { RunsCard } from "@/features/fleet/runs-table"
import { Breadcrumbs } from "@/layouts/breadcrumbs"
import { UnknownRoute } from "@/layouts/unknown-route"

const QUESTION =
  "What the remediation pipeline attempted, what it abandoned, and which change kinds it does not handle mechanically."

export function RunsPage() {
  const { repoId } = useParams<{ repoId: string }>()
  if (repoId === undefined) return <UnknownRoute />

  return (
    <section className="flex flex-col gap-8">
      <div className="flex flex-col gap-field">
        {/* Level name only: the scope trail in the top bar already draws the repository, and
            M7-W195 trimmed exactly this repetition from five other routes — the page keeps the
            segments the bar does not reach, which here is one. */}
        <Breadcrumbs trail={[{ label: "Logs" }]} />
        <PageTabs label="Logs" tabs={logsTabs(repoId)} />
        <p className="text-meta text-muted-foreground">{QUESTION}</p>
      </div>

      {/* The scope statement leads, because a reader who meets a count first has already formed a
          belief about it by the time a caveat arrives. It is one sentence about the whole screen
          rather than one per card: all three read the same two fleet-wide routes, and three copies
          of one fact is the disagreement `CLAUDE.md` names as the most expensive kind of debt. */}
      <p className="text-body text-muted-foreground max-w-3xl leading-relaxed border-l border-line pl-field">
        Every figure on this page is across all workspaces and is{" "}
        <span className="text-foreground">not narrowed to this workspace</span>. The corpus table{" "}
        <span className="font-mono">migration_outcome</span> stores no repository, deliberately —
        that is what makes it safe to aggregate across customers — so there is no column to filter
        on and no narrower answer being withheld. Everything above this line is scoped to the
        workspace in the breadcrumb; nothing below it is.
      </p>

      <RunsCard />

      <div className="grid gap-8 xl:grid-cols-2">
        <AbandonReasonsCard />
        <TierOutcomesCard />
      </div>

      <div className="flex flex-col gap-row text-meta text-muted-foreground max-w-5xl leading-relaxed pt-section border-t border-border">
        <p>
          One row here is one attempt, not one finding. A finding retried three times writes three
          attempts on this page and counts once toward the corpus grain, so a total here is larger
          than the finding count on every other screen and neither figure is wrong.
        </p>
        <p>
          An abandoned attempt is data rather than a failure to hide: the reason code is queryable,
          and abandonment by change kind is how routing learns which changes are not mechanically
          safe to attempt at all.
        </p>
      </div>
    </section>
  )
}
