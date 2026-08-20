/**
 * Codebase: the selected repository, and the root of everything beneath it.
 *
 * `docs/superpowers/specs/2026-07-25-sync-self-maintaining-apis-design.md:397` names this
 * level "Codebase (the selected repository)" and the amended hierarchy (`:433`) keeps it —
 * this screen did not exist until the 2026-08-05 reconciliation found the console had no way
 * to select one, and everything below it (`/vendors/:id`, `/detectors`, the old `/codebase`)
 * was answering fleet-wide for exactly that reason. This is the fix: pick a repository here,
 * and drill down from it into the vendor rows below.
 *
 * ## The pipeline and its doors, owner ruling 2026-08-19
 *
 * This screen carried four tables — open findings, index coverage, change units, observed
 * telemetry — and every one of them was a truncated copy of a screen an operator could open in
 * full. Three were duplicates outright (Vendors and Findings carry the first, Services the second,
 * Telemetry the fourth); Change units moved to Integration changes and Provenance to Detectors,
 * because both were mounted nowhere else.
 *
 * What replaced them says what this screen is for: `PipelineStrip` draws the five
 * `WORKFLOW_STAGES` with one measured figure each, and `WorkflowGrid` lists every page a workspace
 * can reach under the stage it answers, with the question `lib/routes.ts` already declares for it.
 * The Overview is where a reader learns the shape of the loop and picks a door, not where every
 * screen is previewed.
 *
 * **There is still no figure combining the stages, and there is not going to be.** A scalar over
 * "what we read", "what we watched" and "what is broken" would collapse three different kinds of
 * not-knowing onto one axis. The strip refuses scale for the same reason: its stages count call
 * sites, integrations, calls and findings, and no width may assert a ratio between those.
 *
 * Every figure on this screen and on every screen below it is scoped to `repoId`, and each answer
 * names the scope it was computed in — so picking a different repository changes every number here
 * rather than some of them.
 *
 * ## Ported onto the chassis and the vendored substrate by M7-W173
 *
 * `docs/superpowers/briefs/2026-08-07-substrate-codebase.md` is the mapping table this port was
 * gated on, and it is what to read before porting a level, not this docstring.
 *
 * **The chassis arrives here in the same work item as the substrate, because this level never had
 * it.** Fleet took the chassis in M7-W163 and the substrate in M7-W172; Codebase had neither, and
 * rendered a bare 22px heading over three stacked full-width panels while the route's own question
 * sat unread in `lib/routes.ts`. So `PageHeader` now carries that question at the display step and
 * a `ControlBar` states the scope and holds one action.
 *
 * ## No runs panel and no repair record, until `B149` closes
 *
 * `RunsCard` and `CorpusSummaryCard` both name this screen as their destination and both are
 * unmounted anywhere in the console. Neither is mounted here, and the reason is the payload rather
 * than the layout: `RunRow` carries no `repo_id`, and `/api/corpus` accepts no repository
 * parameter, so either one placed under this heading would render every repository's rows beneath
 * one repository's name. That is the attribution `M14-W265` removed from the repository cards.
 * `codebase-page.test.tsx` holds the absence so a later tidy cannot restore it quietly.
 */

import { ApiSurfacePanel } from "@/features/repositories/api-surface-panel"
import { Link, useParams } from "react-router"

import { Button } from "@/components/ui/button"
import { MapPreviews } from "@/features/index-graph/map-previews"
import { PipelineStrip } from "@/features/repositories/pipeline-strip"
import { WorkflowGrid } from "@/features/repositories/workflow-grid"
import { GettingStartedCard } from "@/features/repositories/getting-started-card"
import { useRepositoryGraph, useRepositoryCoverage } from "@/api/queries"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { ControlBar } from "@/layouts/control-bar"
import { UnknownRoute } from "@/layouts/unknown-route"


/**
 * The two map previews, fed one read.
 *
 * One query for both: they draw the same bindings, and two components each issuing their own
 * would be two round trips for one answer -- React Query dedupes on the key, which is what
 * makes the pair free rather than double.
 */
function MapsRegion({ repoId }: { repoId: string }) {
  const query = useRepositoryGraph(repoId)
  if (query.isPending) return <LoadingState what="the codebase maps" />
  if (query.isError) {
    return (
      <ErrorState
        error={query.error}
        what="the codebase maps"
        onRetry={() => void query.refetch()}
      />
    )
  }
  if (query.data.total_bindings === 0) {
    return (
      <EmptyState
        headline="No call site has been indexed for this codebase."
        detail="Both maps draw indexed call sites, and there are none. A vendor call appears once INDEX has run against this repository and found one -- a repository the index never ran against shows the same nothing as one that calls no vendor, and neither is a claim that it calls none."
          command={`uv run sync index --repo ${repoId}`}
      />
    )
  }
  return <MapPreviews repoId={repoId} bindings={query.data.bindings} />
}

export interface CodebasePageProps {
  readonly question?: string
}

export function CodebasePage() {
  const { repoId } = useParams<{ repoId: string }>()
  if (repoId === undefined) return <UnknownRoute />

  return (
    <section className="flex flex-col gap-8">
      {/* The header opens the page, as it does on every other screen. It rendered fourth here —
          below Getting Started, the strip and both maps — which left everything above it
          unlabelled and unscoped on the one screen a workspace opens on. */}
      <PageHeaderRegion repoId={repoId} />
      {/* The pipeline opens the body: five stages, one measured figure each, every stage a door.
          It replaced the four-tile fact strip rather than sitting beneath it -- the strip's four
          numbers were this shape's first four cells, and one instrument beats two. */}
      <PipelineStrip repoId={repoId} />
      {/* Getting started follows: the workspace identity and the full loop's probed
          prerequisites, which are instructions rather than measurements. */}
      <GettingStartedCard repoId={repoId} />
      {/* Both maps, side by side, each opening its own full view. A codebase has two shapes
          worth seeing — what it calls, and how it is laid out — and neither summarises the
          other. Their analytics moved with them: topology to the integration map's page, the
          technical census to the file tree's, which is what keeps this screen scannable. */}
      <MapsRegion repoId={repoId} />
      {/* Good news as a number (W541, owner-picked from the scrapped build): how much of the
          API surface is verified clean, beside how much is at risk. */}
      <ApiSurfaceRegion repoId={repoId} />
      <WorkflowGrid repoId={repoId} />
    </section>
  )
}

function PageHeaderRegion({ repoId }: { repoId: string }) {
  return (
    <div className="flex flex-col gap-section">
      <ControlBar
        action={
          <Button asChild variant="outline" size="sm">
            <Link to={`/repositories/${encodeURIComponent(repoId)}/observed`}>
              Signals for this repository
            </Link>
          </Button>
        }
      >
        <div className="flex min-w-0 flex-col gap-field">
          <span className="furniture text-meta text-ink-muted">Scope</span>
          <span className="text-body">
            This repository alone. The codebase overview shows all repositories watched by Sync.
          </span>
        </div>
      </ControlBar>
    </div>
  )
}

/**
 * The API surface panel's own read: binding-status counts off the coverage payload, kept out
 * of the page body so a coverage failure costs this panel and not the maps beside it.
 */
function ApiSurfaceRegion({ repoId }: { repoId: string }) {
  const query = useRepositoryCoverage(repoId)
  if (!query.isSuccess || query.data.repo_id !== repoId) return null
  return <ApiSurfacePanel counts={query.data.by_binding_status ?? {}} />
}
