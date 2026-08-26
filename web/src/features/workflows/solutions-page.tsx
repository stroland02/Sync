/**
 * Solutions: every remediation the pipeline attempted, in the column of the stage it reached.
 *
 * **Owner ruling, 2026-08-26: this screen is a board.** It was a table — fourteen table references
 * and no columns — inside a scrolling column of four charts. What replaced it is a viewport-locked
 * board whose columns are the run disposition vocabulary the payload already carries, each headed
 * by its own count, each card opening the run's record in a drawer.
 *
 * **The four charts left and none of it is a deletion.** *Every run, by disposition* was
 * `by_disposition` as bars and the column headings are now that payload; *Solutions funnel* was the
 * same stages over tickets. Both were the board drawn twice. *Where remediation work stops* and
 * *Attempts by repair tier* moved to Trends, and the first of those had to survive rather than
 * merely move: its unit is findings, so it is the only panel that counts a finding **no run has
 * ever attempted** — which has no card here, because there is no run. The controls band links to it.
 *
 * One card is one attempt: a finding retried across generations is two cards here and one finding
 * on every other screen, which is why the strip counts distinct findings separately.
 */

import { Link, useParams } from "react-router"

import { DEFAULT_LIMIT } from "@/api/client"
import { hasLiveRun, useRuns } from "@/api/queries"
import {
  DetailLayout,
  useSelectionParam,
} from "@/components/detail-layout"
import { FetchedAt } from "@/components/fetched-at"
import { InfoHint } from "@/components/info-hint"
import { KpiStrip } from "@/components/kpi-strip"
import { RelativeTime } from "@/components/relative-time"
import { ScopeChip } from "@/components/scope-chip"
import { Absent } from "@/components/status"
import { ErrorState, LoadingState } from "@/components/states"
import { RunRecordDetail } from "@/features/runs/run-record-detail"
import { boardColumns, SolutionBoard } from "@/features/workflows/solutions-board"
import { ControlBar } from "@/layouts/control-bar"
import { ScreenFrame } from "@/layouts/screen-frame"
import type { StatusSegment } from "@/layouts/status-band"
import { UnknownRoute } from "@/layouts/unknown-route"
import { describeRecordWindow } from "@/lib/record-window"
import { useOffsetParam } from "@/lib/use-offset-param"

/**
 * Why the board is fleet-wide.
 *
 * Deliberately not `CORPUS_SCOPE`: that one says there is no column to narrow on, which is true of
 * `migration_outcome` and false here — `/api/runs` accepts a repository and narrowing it would drop
 * rows rather than withhold nothing.
 */
const RUNS_SCOPE = (
  <>
    Counted across every workspace, not this one. <code className="font-mono">/api/runs</code> is a
    fleet-wide route and this page asks it without a repository. It does accept one — but narrowing
    resolves the scope through the findings the graph still holds, which would silently drop every
    run whose finding has since been patched or retracted. Those are exactly the cards this board
    marks <em>no longer in the graph</em>, so the wider scope is what keeps them visible.
  </>
)

export function SolutionsPage() {
  const { repoId } = useParams<{ repoId: string }>()
  const [offset, setOffset] = useOffsetParam("solutions_offset")
  // The open run lives in the URL and is written as a history push, so Back closes the drawer
  // rather than leaving the screen.
  const [openRun, setOpenRun] = useSelectionParam("solutions_open")
  // One query, unnarrowed, for the whole board. The disposition is what the columns are, so asking
  // the route for one disposition at a time would be five requests that can disagree with each
  // other and with the roll-up their headings are counted from.
  const query = useRuns({ limit: DEFAULT_LIMIT, offset })

  const items = query.data?.items ?? []
  const selectedRun = items.find((run) => run.thread_id === openRun) ?? null
  const { columns, unrecognised } = boardColumns(query.data?.by_disposition ?? {})

  if (repoId === undefined) return <UnknownRoute />

  // Built for every query state: a band that appears only on success renders "not asked yet" and
  // "asked and empty" as the same nothing.
  const status: StatusSegment[] = query.isSuccess
    ? [
        {
          kind: "records",
          label: "Runs",
          text: describeRecordWindow(
            offset,
            items.length,
            { count: query.data.total, boundReached: false },
            "run",
            "runs",
          ),
          paging: {
            offset,
            limit: DEFAULT_LIMIT,
            shown: items.length,
            total: query.data.total,
            nextOffset: query.data.next_offset,
            busy: query.isFetching,
            onOffsetChange: setOffset,
          },
        },
        {
          kind: "note",
          text: "Counted across every workspace, not this one. A column heading counts every run in that stage; the cards under it are the ones in this window.",
        },
        // Should never appear: the transport folds an outcome outside the vocabulary into the
        // in-flight bucket. If it ever does, the runs behind it are visible as a count rather than
        // lost between columns nobody drew.
        ...(unrecognised.length === 0
          ? []
          : [
              {
                kind: "note" as const,
                text: `The payload counted ${unrecognised
                  .map((entry) => `${entry.count} run(s) as ${entry.key}`)
                  .join(", ")}, which this board has no column for.`,
              },
            ]),
      ]
    : [
        {
          kind: "none",
          why: query.isError ? "the runs did not answer" : "asking for the runs",
        },
      ]

  const controls = query.isSuccess ? (
    <ControlBar
      action={
        <FetchedAt
          at={query.dataUpdatedAt}
          polling={hasLiveRun(query.data)}
          idleReason="Every run in this window has reached a disposition, so nothing is being polled."
        />
      }
    >
      <ScopeChip scope="all workspaces">{RUNS_SCOPE}</ScopeChip>
      {/* The claim in the fewest honest words; the argument is one hover away. The second half is
          the gap the board itself creates and cannot draw: every card is a run, so a finding
          nothing has attempted appears in no column at all. */}
      <span className="text-meta text-ink-muted">
        one card is one attempt — a finding no run has attempted has no card here
      </span>
      <InfoHint label="About the board">
        The columns are the disposition vocabulary the checkpointer records —{" "}
        <span className="font-mono">opened</span>, <span className="font-mono">abandoned</span>,{" "}
        <span className="font-mono">reported</span>, <span className="font-mono">parked</span>, and
        the bucket for a run whose newest checkpoint carries none yet. A column with no run still
        renders with a zero: an absent column would claim the stage does not exist.{" "}
        <strong>The heading and the cards answer different questions.</strong> A heading counts
        every run the checkpointer holds in that stage, computed before any narrowing; the cards are
        the ones inside this page window, and the footer says which of the two you are looking at.
        One card is one <em>attempt</em>, so a finding retried across generations is two cards here
        and one finding on every other screen. A checkpoint age is staleness, never liveness —
        whether a run&rsquo;s process is still ticking is a recorded heartbeat, and it is in the run
        record a card opens.
      </InfoHint>
      {/* Where the panel that counted findings went. A move that leaves its destination
          unreachable is a deletion with extra steps. */}
      <Link
        to={`/repositories/${encodeURIComponent(repoId)}/metrics`}
        className="text-meta underline underline-offset-2"
      >
        Open findings nothing has attempted, on Trends
      </Link>
    </ControlBar>
  ) : undefined

  const prHref =
    selectedRun !== null && selectedRun.outcome === "opened" && selectedRun.repo_id !== null
      ? `/repositories/${encodeURIComponent(selectedRun.repo_id)}/findings/${encodeURIComponent(selectedRun.finding_id)}/workflow/pull-request`
      : null

  return (
    <ScreenFrame
      layout="locked"
      controls={controls}
      status={status}
      subtitle="Every remediation the pipeline attempted, in the column of the stage it reached."
    >
      {query.isPending && <LoadingState what="the remediation runs" />}
      {query.isError && (
        <ErrorState
          error={query.error}
          what="the remediation runs"
          onRetry={() => void query.refetch()}
        />
      )}

      {/* The strip portals itself into the top bar's second row; nothing is drawn for it here.
          None of the three restates a column heading: the first is the total the columns
          partition, and the other two are facts no single stage carries. */}
      {query.isSuccess && (
        <KpiStrip
          items={[
            {
              label: "Runs held",
              value: query.data.unfiltered_total.toLocaleString(),
              note: "every run the checkpointer holds, across every workspace — the total these columns divide",
            },
            {
              label: "Distinct findings (this window)",
              value: new Set(items.map((run) => run.finding_id)).size,
              note: "a finding retried across generations is more than one card and one finding",
            },
            {
              label: "Newest checkpoint",
              value:
                items.length === 0 ? (
                  <Absent>nothing checkpointed</Absent>
                ) : (
                  <RelativeTime iso={items[0].last_checkpoint_at} />
                ),
              note: "on the newest run in this window — staleness, not liveness",
              figure: false,
            },
          ]}
        />
      )}

      {query.isSuccess && (
        <DetailLayout
          docked
          title="Run record"
          subtitle={selectedRun === null ? undefined : selectedRun.thread_id}
          onClose={() => setOpenRun(null)}
          detail={
            selectedRun !== null ? (
              <div className="flex flex-col gap-section">
                {prHref !== null && (
                  <Link to={prHref} className="text-body underline underline-offset-2">
                    Open the pull request this run wrote — the diff and its branch
                  </Link>
                )}
                <RunRecordDetail run={selectedRun} />
              </div>
            ) : openRun === null ? null : (
              // Never silently closed: dropping a selection the URL still carries makes the
              // address and the screen disagree, and a bookmarked run is the case that does it.
              <p className="text-body text-ink-muted">
                That run is not in this window. The address names thread{" "}
                <span className="font-mono break-all">{openRun}</span>; the board is showing the
                page starting at offset {offset}. Clear the selection or page back to it.
              </p>
            )
          }
          list={
            <SolutionBoard
              columns={columns}
              items={items}
              unfilteredTotal={query.data.unfiltered_total}
              repoId={repoId}
              selected={openRun}
              onSelect={setOpenRun}
            />
          }
        />
      )}
    </ScreenFrame>
  )
}
