/**
 * Solutions: every run that reached a pull request, and the door into each one's workflow —
 * the owner's page, named 2026-08-18: "shows the PR information and the solution workflow".
 *
 * The rows are `/api/runs` narrowed to `outcome=opened` — the disposition filter built for the
 * Logs rail, reused rather than a new route, so this list and the Logs screen cannot disagree
 * about what opened. One row per attempt holds here exactly as it does on Logs; a finding
 * whose retry also opened is two solutions, and the table's caption says so once.
 *
 * Each row links to the finding's Solution Workflow and its Pull Request screen — the deep
 * levels the specification already owns. This page aggregates over them and is not a new
 * level; `.claude/rules/console-hierarchy.md` is explicit that an aggregate is not a rung.
 */

import type { ReactNode } from "react"
import { Link, useParams } from "react-router"

import { DEFAULT_LIMIT } from "@/api/client"
import { useRuns, useTickets } from "@/api/queries"
import type { RunRow, RunsPage } from "@/api/types"
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
import { RankedBars, type RankedRow } from "@/components/ranked-bars"
import { ScopeChip } from "@/components/scope-chip"
import { Absent } from "@/components/status"
import { ErrorState, LoadingState } from "@/components/states"
import { RelativeTime } from "@/components/relative-time"
import { ScreenFrame } from "@/layouts/screen-frame"
import type { StatusSegment } from "@/layouts/status-band"
import { UnknownRoute } from "@/layouts/unknown-route"
import { TicketFunnel } from "@/features/tickets/ticket-funnel"
import { describeRecordWindow } from "@/lib/record-window"
import { useOffsetParam } from "@/lib/use-offset-param"

/**
 * Why the two run panels are fleet-wide, written once for both of them.
 *
 * Deliberately not `CORPUS_SCOPE`: that one says there is no column to narrow on, which is true
 * of `migration_outcome` and false here — `/api/runs` accepts a repository and narrowing it
 * would drop rows rather than withhold nothing.
 */
const RUNS_SCOPE = (
  <>
    Counted across every workspace, not this one. <code className="font-mono">/api/runs</code> is a
    fleet-wide route and this page asks it without a repository. It does accept one — but narrowing
    resolves the scope through the findings the graph still holds, which would silently drop every
    run whose finding has since been patched or retracted. Those are exactly the rows this table
    marks <em>no longer in the graph</em>, so the wider scope is what keeps them visible.
  </>
)

/** A panel title with the fleet scope beside it, written once for both run panels. */
function ScopeLabel({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex flex-wrap items-center gap-row">
      {children}
      <ScopeChip scope="all workspaces">{RUNS_SCOPE}</ScopeChip>
    </span>
  )
}

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

/**
 * What each recorded disposition means to a reader. The `"null"` key is the in-flight bucket —
 * `by_disposition` counts a run with no outcome under the string `"null"`, and rendering that
 * literally would put the word "null" in a chart where "still running" belongs.
 */
const DISPOSITION_LABEL = new Map<string, string>([
  ["opened", "opened a pull request"],
  ["abandoned", "abandoned"],
  ["reported", "reported, not patched"],
  ["parked", "parked"],
  ["null", "in flight, no outcome yet"],
])

/**
 * `by_disposition` as ranked rows, largest first. An unrecognised disposition keeps its own raw
 * value as its label rather than being dropped — a run the console does not have a word for is
 * still a run that happened.
 */
export function dispositionRows(byDisposition: Record<string, number>): RankedRow[] {
  return Object.entries(byDisposition)
    .map(([key, value]) => ({ key: DISPOSITION_LABEL.get(key) ?? key, value }))
    .sort((a, b) => b.value - a.value)
}

/**
 * What became of every run, including the ones the table above filters away.
 *
 * The rows are narrowed to `outcome=opened`, so what happened to the rest is a fact they
 * structurally cannot carry — and `by_disposition` is computed before that filter precisely so a
 * reader can see what each selection would return.
 */
function RunDispositionPanel({ page }: { page: RunsPage }) {
  const rows = dispositionRows(page.by_disposition)

  return (
    <MetricPanel
      frame="board"
      label={<ScopeLabel>Every run, by disposition</ScopeLabel>}
      caption={`What became of all ${page.unfiltered_total.toLocaleString()} run${page.unfiltered_total === 1 ? "" : "s"} the checkpointer holds, counted before the opened filter the table applies.`}
    >
      {rows.length === 0 ? (
        <span className="text-body">
          <Absent>the checkpointer holds no run at all</Absent>
        </span>
      ) : (
        <RankedBars
          label="By disposition"
          caption="Each bar's width is its share of the largest disposition, not of the total."
          rows={rows}
          unit="runs"
          colourByKey={false}
        />
      )}
      <p className="text-meta text-ink-muted">
        A disposition with no run is absent here rather than drawn at zero — the payload counts
        what occurred and does not enumerate the vocabulary.
      </p>
    </MetricPanel>
  )
}

export function SolutionsPage() {
  const { repoId } = useParams<{ repoId: string }>()
  const [offset, setOffset] = useOffsetParam("solutions_offset")
  const query = useRuns({ limit: DEFAULT_LIMIT, offset, outcome: "opened" })

  if (repoId === undefined) return <UnknownRoute />

  // Built for every query state: a band that appears only on success renders "not asked yet"
  // and "asked and empty" as the same nothing.
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
    <ScreenFrame status={status} subtitle="Every remediation that reached the forge, newest first.">
      {/* The page's facts before its rows (owner ruling 2026-08-19). `unfiltered_total` is the
          one a tile earns its slot with: the table below is narrowed to opened runs, so what
          that count is out of is a fact the rows cannot carry. */}
      {query.isSuccess && (
        <KpiStrip
          items={[
            {
              label: "Pull requests opened",
              value: query.data.total.toLocaleString(),
              note: "runs that reached the forge",
            },
            {
              label: "Distinct findings (this page)",
              value: new Set(query.data.items.map((run) => run.finding_id)).size,
              note: "a retried finding opens twice and counts twice",
            },
            {
              // A percentage whose denominator is only in a tooltip is a rate with no
              // denominator on screen; the count pair is honest without a hover.
              label: "Opened, of all runs",
              value: `${query.data.total.toLocaleString()} of ${query.data.unfiltered_total.toLocaleString()}`,
              note: "the checkpointer's whole run count, before the opened filter",
              figure: false,
            },
            {
              label: "Newest opened",
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

      <div className="grid min-w-0 gap-8 xl:grid-cols-3 xl:items-start">
        <div className="flex min-w-0 flex-col gap-8 xl:col-span-2">
          {/* The two query states render inside this card rather than above the board: a state
              that reflows the whole grid makes the loading screen a different layout from the
              loaded one. */}
          <MetricPanel
            frame="board"
            label={<ScopeLabel>Solutions</ScopeLabel>}
            caption="One row per attempt: a finding whose retry also opened counts twice, and neither row is wrong."
          >
            {query.isPending ? (
              <LoadingState what="the opened pull requests" />
            ) : query.isError ? (
              <ErrorState
                error={query.error}
                what="the opened pull requests"
                onRetry={() => void query.refetch()}
              />
            ) : (
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
                      checkpointer was asked and holds no run with the opened outcome —
                      remediation that abandons or is still in flight appears on Logs, not here.
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
            )}
          </MetricPanel>

          {/* Both Sankeys stay in the wide column: `SankeyFlow` scales its 720-unit viewBox to
              whatever container it is given, and at full frame width that is a 1.8x blow-up. */}
          <RemediationFlow repoId={repoId} frame="board" />
          <AttemptsOverTime frame="board" />
          <SolutionsFunnelRegion repoId={repoId} />
        </div>

        <aside className="flex min-w-0 flex-col gap-8">
          {query.isSuccess && <RunDispositionPanel page={query.data} />}
          <AttemptsByTier frame="board" />
        </aside>
      </div>
    </ScreenFrame>
  )
}

/**
 * The funnel's own read, kept out of the page body so a tickets route that does not answer
 * costs the diagram and not the solutions table beneath, which reads a different route.
 *
 * Three branches rather than one `return null`: a route still being asked, a route that failed
 * and a route that answered with no ticket are three different nothings, and this pane rendered
 * all three as the same blank.
 */
export function SolutionsFunnelRegion({ repoId }: { repoId: string }) {
  const query = useTickets(repoId, null, { refetchIntervalMs: 15_000 })

  if (query.isPending) return <LoadingState what="this workspace's remediation tickets" />
  if (query.isError) {
    return (
      <ErrorState
        error={query.error}
        what="this workspace's remediation tickets"
        onRetry={() => void query.refetch()}
      />
    )
  }
  if (query.data.tickets.length === 0) {
    return (
      <MetricPanel
        frame="board"
        label="Solutions funnel"
        caption="The tickets route was asked and holds none for this workspace, which is not the same as a workspace nothing has been asked about yet."
      >
        <span className="text-body">
          <Absent>no ticket has been raised in this workspace</Absent>
        </span>
      </MetricPanel>
    )
  }
  return <TicketFunnel tickets={query.data.tickets} />
}
