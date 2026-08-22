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
import type { RunRow } from "@/api/types"
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
import { RemediationFlow } from "@/features/workflows/remediation-flow"
import { MetricPanel } from "@/components/metric-panel"
import { Absent } from "@/components/status"
import { ErrorState, LoadingState } from "@/components/states"
import { RelativeTime } from "@/components/relative-time"
import { Breadcrumbs } from "@/layouts/breadcrumbs"
import { ScreenFrame } from "@/layouts/screen-frame"
import type { StatusSegment } from "@/layouts/status-band"
import { UnknownRoute } from "@/layouts/unknown-route"
import { PageTabs, solutionsTabs } from "@/components/page-tabs"
import { useTickets } from "@/api/queries"
import { TicketFunnel } from "@/features/tickets/ticket-funnel"
import { describeRecordWindow } from "@/lib/record-window"
import { useOffsetParam } from "@/lib/use-offset-param"

/**
 * Which finding a solution is for: the sayable name, with the id under it.
 *
 * The column led with a 32-character hex id, which is the one thing about a finding nobody can
 * read, say or hold in their head — and this is the screen where a reviewer picks which of
 * several solutions to open. `finding_name` (`CI-W528`) exists precisely for that sentence, and
 * this table was still rendering the key instead.
 *
 * **The id stays on screen, in the smaller register.** It is what a URL, a `gh` command and a
 * grep are built from, so removing it would trade one unreadable column for one uncopyable one.
 * The name is the subject; the id is the reference.
 *
 * `null` is a run whose finding the graph no longer holds — a scan rebuilt `finding` and this
 * one was patched or retracted. The id is then all there is, and it says so rather than leaving
 * a blank where a name goes.
 */
function SolutionSubject({ run }: { run: RunRow }) {
  return (
    <div className="flex min-w-0 flex-col gap-field">
      {run.finding_name === null ? (
        <span className="text-body">
          <Absent>no longer in the graph</Absent>
        </span>
      ) : (
        <span className="font-mono text-body text-ink">{run.finding_name}</span>
      )}
      <span className="font-mono text-meta break-all text-ink-muted">{run.finding_id}</span>
    </div>
  )
}

export function SolutionsPage() {
  const { repoId } = useParams<{ repoId: string }>()
  const [offset, setOffset] = useOffsetParam("solutions_offset")
  const query = useRuns({ limit: DEFAULT_LIMIT, offset, outcome: "opened" })

  if (repoId === undefined) return <UnknownRoute />

  // Built for every query state: a band that appears only on success renders "not asked yet"
  // and "asked and empty" as the same nothing. The two caveats moved out of the panel's caption
  // rather than being copied into the band — one sentence rendered twice is a fact that can
  // disagree with itself.
  const status: StatusSegment[] = query.isSuccess
    ? [
        {
          kind: "records",
          label: "Solutions",
          text: describeRecordWindow(
            offset,
            query.data.items.length,
            { count: query.data.total, boundReached: false },
            "solution",
            "solutions"
          ),
          paging: {
            offset,
            limit: DEFAULT_LIMIT,
            shown: query.data.items.length,
            total: query.data.total,
            nextOffset: query.data.next_offset,
            busy: query.isFetching,
            onOffsetChange: setOffset,
          },
        },
        { kind: "note", text: "Every remediation that reached the forge, newest first." },
        {
          kind: "note",
          text:
            "One row per attempt: a finding whose retry also opened counts twice, and neither " +
            "row is wrong.",
        },
      ]
    : [
        {
          kind: "none",
          why: query.isError
            ? "the opened pull requests did not answer"
            : "asking for the opened pull requests",
        },
      ]

  return (
    <ScreenFrame status={status}>
    <section className="flex flex-col gap-8">
      <Breadcrumbs trail={[{ label: "Solutions" }]} />
      <SolutionsFunnelRegion repoId={repoId} />
      <PageTabs label="Solutions" tabs={solutionsTabs(repoId)} />

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
      {/* The flow leads the corpus panels: it is the only view showing attrition *between*
          stages, and the two beneath break the attempts down once you have seen where they sit. */}
      <RemediationFlow repoId={repoId} />

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
                    <TableCell>
                      <SolutionSubject run={run} />
                    </TableCell>
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
        </MetricPanel>
      )}
    </section>
    </ScreenFrame>
  )
}


/**
 * The funnel's own read, kept out of the page body so a tickets route that does not answer
 * costs the diagram and not the solutions table beneath, which reads a different route.
 */
function SolutionsFunnelRegion({ repoId }: { repoId: string }) {
  const query = useTickets(repoId, null, { refetchIntervalMs: 15_000 })
  if (!query.isSuccess) return null
  return <TicketFunnel tickets={query.data.tickets} />
}
