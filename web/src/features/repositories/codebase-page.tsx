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
 * Three view models, three questions, and none of them confirms another.
 *
 * `overview_summary` scoped to this repository answers "what is currently wrong here" — the
 * question the design document says a user actually arrives with. `index_coverage` answers
 * "how much of this codebase has Sync read" from `call_site` alone. `observed_telemetry`
 * answers "what traffic did Sync see" from three tables that carry no bearing on what the
 * static index found — a call site can exist with no traffic observed, and traffic can arrive
 * that correlates to no known call site. Three cards rather than one keeps those boundaries
 * visible instead of implying any of them confirms the others, and there is deliberately no
 * figure combining them: a scalar over "what is broken", "what we read" and "what we watched"
 * would collapse three different kinds of not-knowing onto one axis.
 *
 * Every figure on this screen and on every screen below it is scoped to `repoId`. The three
 * routes it reads take the repository — `/api/overview`, `/api/repositories/{repo}/coverage`
 * and `/api/repositories/{repo}/observed` — and each answer names the scope it was computed
 * in, so picking a different repository changes every number here rather than some of them.
 *
 * ## Ported onto the chassis and the vendored substrate by M7-W173
 *
 * `docs/superpowers/briefs/2026-08-07-substrate-codebase.md` is the mapping table this port was
 * gated on, and it is what to read before porting a level, not this docstring.
 *
 * **The chassis arrives here in the same work item as the substrate, because this level never had
 * it.** Fleet took the chassis in M7-W163 and the substrate in M7-W172; Codebase had neither, and
 * rendered a bare 22px heading over three stacked full-width panels while the route's own question
 * sat unread in `lib/routes.ts`. So `PageHeader` now carries that question at the display step,
 * a `ControlBar` states the scope and holds one action, and the two panels the question is
 * actually about sit beside one another.
 *
 * **Neither of this level's outbound links moved into the control bar.** Fleet lifted its
 * detector-attribution link out of a card description and into the action slot; here the detectors
 * link and the Signals link each complete a sentence that argues for them, and a qualification with
 * its link taken out is a qualification shortened. The action slot takes the Signals screen as a
 * plain navigation instead — the one thing an operator does next that is not a row on this page.
 *
 * **No fact rail, and that is ruling 9 of the brief rather than an omission.** `IndexCoverageCard`
 * is mounted by the Signals level too, so hoisting its call-site figure into a Codebase-only rail
 * would either delete that figure from Signals or render it twice here.
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

import { Link, useParams } from "react-router"

import { Button } from "@/components/ui/button"
import { ChangeUnitsTable } from "@/features/fleet/change-units-table"
import { MapPreviews } from "@/features/index-graph/map-previews"
import { OverviewKpis } from "@/features/repositories/overview-kpis"
import { RungMixCard } from "@/features/repositories/rung-mix-card"
import { GettingStartedCard } from "@/features/repositories/getting-started-card"
import { useRepositoryGraph } from "@/api/queries"
import { IndexCoverageCard } from "@/features/repositories/index-coverage-card"
import { OpenFindingsCard } from "@/features/repositories/open-findings-card"
import { ObservedTelemetryCard } from "@/features/telemetry/observed-telemetry-card"
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
          command={`uv run sync index --repo-id ${repoId}`}
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
      {/* The strip opens the body on every page (owner ruling), this one included -- it sat
          below Getting Started, which made the Overview the one screen whose facts did not lead. */}
      <OverviewKpis repoId={repoId} />
      {/* Getting started follows: the workspace identity and the full loop's probed
          prerequisites, which are instructions rather than measurements. */}
      <GettingStartedCard repoId={repoId} />
      {/* Both maps, side by side, each opening its own full view. A codebase has two shapes
          worth seeing — what it calls, and how it is laid out — and neither summarises the
          other. Their analytics moved with them: topology to the integration map's page, the
          technical census to the file tree's, which is what keeps this screen scannable. */}
      <MapsRegion repoId={repoId} />
      {/* The two halves of the route's own question, beside one another */}
      <div className="grid auto-rows-fr gap-8 xl:grid-cols-2">
        <OpenFindingsCard repoId={repoId} />
        <IndexCoverageCard repoId={repoId} />
      </div>
      {/* Dashboard O2. The rung mix is the console's own argument drawn once rather than
          asserted a column at a time, and the payload has carried the facet since dashboard 2
          was specified without anything rendering it. */}
      <RungMixCard repoId={repoId} />
      <ChangeUnitsTable repoId={repoId} />
      <ObservedTelemetryCard repoId={repoId} />
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
