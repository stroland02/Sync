/**
 * The fleet: what Sync is doing right now, across every run it has ever started.
 *
 * Every other screen answers a question about one finding, one vendor, or one repository.
 * This one sits above that hierarchy and answers a question none of them can: it reads the
 * LangGraph checkpointer and the index through `sync.dashboard.fleet`, never `GraphSurface`,
 * because "every run" and "every attempt" are not questions the frozen per-finding surface
 * was built to answer.
 *
 * There is no composite health figure here on purpose. A scalar that averaged three gates
 * would collapse "we could not check" onto the same axis as "we checked and it passed",
 * which is the failure this console exists to replace.
 */

import { CorpusSummaryCard } from "@/features/fleet/corpus-summary"
import { RepositoriesCard } from "@/features/fleet/repositories-table"
import { RunsCard } from "@/features/fleet/runs-table"
import { Breadcrumbs } from "@/layouts/breadcrumbs"

export function FleetPage() {
  return (
    <section className="flex flex-col gap-4">
      <Breadcrumbs trail={[{ label: "Fleet" }]} />
      <h1 className="text-page">Fleet</h1>
      <p className="text-body text-muted-foreground">
        Every run the checkpointer holds, the repair record aggregated across all of them,
        and every repository the index has seen. Runs come from the LangGraph checkpointer;
        the repair record and the repository list come from the graph's own tables, read
        through a view model built for this screen rather than the frozen{" "}
        <code className="font-mono">GraphSurface</code> the rest of the console uses. None
        of the three carries an indexing timestamp or a binding rung — that provenance
        envelope belongs to <code className="font-mono">GraphSurface</code>'s per-finding
        answers, and inheriting it here would invent fields the transport never sends.
      </p>
      <RunsCard />
      <CorpusSummaryCard />
      <RepositoriesCard />
    </section>
  )
}
