/**
 * The repair record, aggregated: every `migration_outcome` row the graph holds.
 *
 * `attempts` and `distinct_findings` are two different facts and this screen still renders both,
 * in the two places each belongs. `sync.remediate.corpus` writes one row per attempt, so a finding
 * retried three times is three attempts and one finding — a screen that showed a single number for
 * both would be the grain defect `CLAUDE.md` names for this table.
 *
 * **Which is where, and why.** `attempts` is the fact rail's fourth tile at the top of this screen.
 * `distinct_findings` is this panel's own metric, because it is the figure the rail cannot carry
 * and because the sentence that relates the two sits directly beneath it. Rendering `attempts`
 * here as well is what M7-W163 ruled out: two renderings of one count is a fact written twice, and
 * the one that stays is the one an operator reaches first.
 */

import { lazy, Suspense } from "react"

import { useCorpus } from "@/api/queries"
import type { Tally } from "@/api/types"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/data-table"
import { MetricPanel } from "@/components/metric-panel"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"

// Lazy so echarts and echarts-for-react — the corpus chart's only heavy
// dependency — land in their own chunk instead of the console's initial
// bundle.
const CorpusChart = lazy(() =>
  import("@/features/fleet/corpus-chart").then((mod) => ({ default: mod.CorpusChart })),
)

function TallyTable({ heading, tally }: { heading: string; tally: Tally }) {
  const entries = Object.entries(tally).sort(([a], [b]) => a.localeCompare(b))
  return (
    <div className="flex flex-col gap-row">
      <h3 className="furniture text-meta text-ink-muted">{heading}</h3>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Value</TableHead>
            <TableHead>Attempts</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {entries.map(([value, count]) => (
            <TableRow key={value}>
              <TableCell className="font-mono">{value}</TableCell>
              <TableCell className="font-mono">{count}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

export function CorpusSummaryCard() {
  const query = useCorpus()

  return (
    <div className="flex flex-col gap-section">
      {query.isPending && <LoadingState what="the repair record" />}
      {query.isError && <ErrorState error={query.error} what="the repair record" onRetry={() => void query.refetch()} />}

      {query.isSuccess && (
        <MetricPanel
          label="Repair record"
          metric={{
            value: query.data.distinct_findings.toLocaleString(),
            unit:
              query.data.distinct_findings === 1
                ? "finding with a repair attempt"
                : "findings with a repair attempt",
          }}
          caption={
            <>
              <p className="max-w-prose">
                Every repair attempt the graph has recorded, one row of{" "}
                <code className="font-mono">migration_outcome</code> per attempt. A finding
                retried three times writes three attempts here and counts once toward
                findings.
              </p>
              <p className="max-w-prose">
                This one cannot be narrowed to a repository, and no screen below this level
                renders it: <code className="font-mono">migration_outcome</code> stores no
                repository at all — nothing in it identifies a customer, which is the decision
                that makes it safe to aggregate across them.
              </p>
            </>
          }
        >
          {query.data.attempts === 0 ? (
            <EmptyState
              headline="The graph holds no repair attempts."
              detail="The API answered, and migration_outcome has no rows. That is an answer, not a failure — nothing has reached a patch attempt on this database yet."
            />
          ) : (
            <>
              <Suspense fallback={null}>
                <CorpusChart data={query.data} />
              </Suspense>
              <div className="grid gap-section sm:grid-cols-3">
                <TallyTable heading="By disposition" tally={query.data.by_terminal_status} />
                <TallyTable heading="By strategy" tally={query.data.by_strategy} />
                <TallyTable heading="By tier" tally={query.data.by_tier} />
              </div>
            </>
          )}
        </MetricPanel>
      )}
    </div>
  )
}
