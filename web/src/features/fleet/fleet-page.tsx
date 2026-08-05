/**
 * The fleet: what Sync is doing right now, across every run it has ever started, and what
 * an operator has to act on today.
 *
 * Five routes make this screen, each read through the view model built for its own grain
 * rather than the frozen `GraphSurface`: `GET /api/overview` for open findings by vendor
 * (the one source here that does carry the frozen surface's provenance envelope, since it
 * reads `GraphSurface.whats_at_risk` directly), `GET /api/runs` for the checkpointer,
 * `GET /api/corpus` for the repair record, `GET /api/repositories` for the index's repo_id
 * roll-up, and `GET /api/detectors` for open-finding attribution. The latter four read
 * `sync.dashboard.fleet` and `sync.dashboard.graph_views`, and none of them carries an
 * indexing timestamp or a binding rung envelope — inheriting one would invent a field the
 * transport never sends.
 *
 * There is no composite health figure here on purpose. A scalar that averaged three gates
 * would collapse "we could not check" onto the same axis as "we checked and it passed",
 * which is the failure this console exists to replace.
 */

import { CorpusSummaryCard } from "@/features/fleet/corpus-summary"
import { DetectorsSummaryCard } from "@/features/fleet/detectors-summary"
import { RepositoriesCard } from "@/features/fleet/repositories-table"
import { RunsCard } from "@/features/fleet/runs-table"
import { ScreenLimitsCard } from "@/features/fleet/screen-limits"
import { VendorDistributionCard } from "@/features/fleet/vendor-distribution"
import { Breadcrumbs } from "@/layouts/breadcrumbs"

export function FleetPage() {
  return (
    <section className="flex flex-col gap-6">
      <Breadcrumbs trail={[{ label: "Fleet" }]} />
      <div className="flex flex-col gap-3">
        <h1 className="text-page">Fleet</h1>
        <p className="text-body text-muted-foreground">
          There is no composite health figure here on purpose. A scalar that averaged three
          gates would collapse "we could not check" onto the same axis as "we checked and it
          passed", which is the failure this console exists to replace. Every figure below
          instead names its own scope, and the panel beneath them names what none of these
          figures can tell you at all.
        </p>
      </div>
      <VendorDistributionCard />
      <ScreenLimitsCard />
      <RunsCard />
      <CorpusSummaryCard />
      <RepositoriesCard />
      <DetectorsSummaryCard />
    </section>
  )
}
