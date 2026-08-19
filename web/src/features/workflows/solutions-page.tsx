/**
 * Solutions: every run that reached a pull request, and the door into each one's workflow —
 * the owner's page, named 2026-08-18: "shows the PR information and the solution workflow".
 *
 * The rows are `/api/runs` narrowed to `outcome=opened` — the disposition filter built for the
 * Logs rail, reused rather than a new route, so this list and the Logs screen cannot disagree
 * about what opened. One row per attempt holds here exactly as it does on Logs; a finding
 * whose retry also opened is two solutions, and the footnote says so once.
 *
 * Each row links to the finding's Solution Workflow and its Pull Request screen — the deep
 * levels the specification already owns. This page aggregates over them and is not a new
 * level; `.claude/rules/console-hierarchy.md` is explicit that an aggregate is not a rung.
 */

import { Link, useParams } from "react-router"

import { DEFAULT_LIMIT } from "@/api/client"
import { useRuns } from "@/api/queries"
import {
  Table,
  TableBody,
  TableCell,
  TableEmptyRow,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/data-table"
import { KpiStrip } from "@/components/kpi-strip"
import { AttemptsByTier, AttemptsOverTime } from "@/features/workflows/remediation-activity"
import { MetricPanel } from "@/components/metric-panel"
import { Absent } from "@/components/status"
import { ErrorState, LoadingState } from "@/components/states"
import { RelativeTime } from "@/components/relative-time"
import { Breadcrumbs } from "@/layouts/breadcrumbs"
import { FooterBar } from "@/layouts/footer-bar"
import { UnknownRoute } from "@/layouts/unknown-route"
import { useOffsetParam } from "@/lib/use-offset-param"

export function SolutionsPage() {
  const { repoId } = useParams<{ repoId: string }>()
  const [offset, setOffset] = useOffsetParam("solutions_offset")
  const query = useRuns({ limit: DEFAULT_LIMIT, offset, outcome: "opened" })

  if (repoId === undefined) return <UnknownRoute />

  return (
    <section className="flex flex-col gap-8">
      <Breadcrumbs trail={[{ label: "Solutions" }]} />

      {query.isPending && <LoadingState what="the opened pull requests" />}
      {query.isError && (
        <ErrorState
          error={query.error}
          what="the opened pull requests"
          onRetry={() => void query.refetch()}
        />
      )}

      {/* The page's facts before its rows (owner ruling 2026-08-19). `unfiltered_total` is the
          one a tile earns its slot with: the table below is narrowed to opened runs, so the
          share it represents is a fact the rows cannot carry. */}
      {query.isSuccess && (
        <KpiStrip
          items={[
            {
              label: "Pull requests opened",
              value: query.data.total.toLocaleString(),
              note: "runs that reached the forge",
            },
            {
              label: "Distinct findings behind them",
              value: new Set(query.data.items.map((run) => run.finding_id)).size,
              note: "on this page — a retried finding opens twice",
            },
            {
              label: "Share of all runs",
              value: `${Math.round((query.data.total / Math.max(query.data.unfiltered_total, 1)) * 100)}%`,
              note: `${query.data.total} of ${query.data.unfiltered_total} the checkpointer holds`,
            },
            {
              label: "Newest",
              value:
                query.data.items.length === 0 ? (
                  <Absent>none opened yet</Absent>
                ) : (
                  <RelativeTime iso={query.data.items[0].last_checkpoint_at} />
                ),
              note: "last checkpoint on the newest opened run",
              figure: false,
            },
          ]}
        />
      )}

      {/* Dashboards L2 and L3. Outside the runs query's success branch on purpose: they read
          the corpus rather than the runs feed, so a runs failure is no reason to withhold how
          the pipeline got here. Both state their own fleet scope, since the corpus table stores
          no repository. */}
      <div className="grid auto-rows-fr gap-8 xl:grid-cols-2">
        <AttemptsOverTime />
        <AttemptsByTier />
      </div>

      {query.isSuccess && (
        <MetricPanel
          label="Solutions"
          metric={{
            value: query.data.total.toLocaleString(),
            unit: `run${query.data.total === 1 ? "" : "s"} that opened a pull request`,
          }}
          caption={
            <p className="max-w-prose">
              Every remediation that reached the forge, newest first. One row per attempt: a
              finding whose retry also opened counts twice, and neither row is wrong.
            </p>
          }
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Finding</TableHead>
                <TableHead>Opened</TableHead>
                <TableHead>Solution workflow</TableHead>
                <TableHead>Pull request</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {query.data.items.length === 0 && (
                <TableEmptyRow colSpan={4}>
                  <span className="text-ink">No run has opened a pull request yet.</span> The
                  checkpointer was asked and holds no run with the opened outcome — remediation
                  that abandons or is still in flight appears on Logs, not here.
                </TableEmptyRow>
              )}
              {query.data.items.map((run) => {
                const scoped = run.repo_id !== null
                const workflowHref = scoped
                  ? `/repositories/${encodeURIComponent(run.repo_id!)}/findings/${encodeURIComponent(run.finding_id)}/workflow`
                  : null
                return (
                  <TableRow key={run.thread_id}>
                    <TableCell className="font-mono">{run.finding_id}</TableCell>
                    <TableCell className="font-mono text-meta">
                      <RelativeTime iso={run.last_checkpoint_at} />
                    </TableCell>
                    <TableCell>
                      {workflowHref !== null ? (
                        <Link to={workflowHref} className="underline underline-offset-2">
                          the run, node by node
                        </Link>
                      ) : (
                        <span className="text-meta text-ink-muted">
                          not addressable — the checkpoint names no repository
                        </span>
                      )}
                    </TableCell>
                    <TableCell>
                      {workflowHref !== null ? (
                        <Link
                          to={`${workflowHref}/pull-request`}
                          className="underline underline-offset-2"
                        >
                          the diff and its branch
                        </Link>
                      ) : (
                        <span className="text-meta text-ink-muted">—</span>
                      )}
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
          <FooterBar
            offset={offset}
            limit={DEFAULT_LIMIT}
            shown={query.data.items.length}
            total={query.data.total}
            nextOffset={query.data.next_offset}
            busy={query.isFetching}
            onOffsetChange={setOffset}
          />
        </MetricPanel>
      )}
    </section>
  )
}
