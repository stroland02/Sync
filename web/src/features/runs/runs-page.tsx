/**
 * Runs: what the remediation pipeline attempted, one row per attempt, as a locked stream.
 *
 * Owner decision 30 gives Runs its own destination rather than a panel on the Overview. It
 * aggregates over Solution Workflow and is therefore **not a new level** —
 * `.claude/rules/console-hierarchy.md` permits a screen that aggregates over a level without
 * claiming to be one, the way detector attribution sits at `Errors & Incidents`. `GRAPH_LEVELS`
 * is untouched and no specification amendment was needed.
 *
 * ## The composition, and what it replaced
 *
 * Two bands and a drawer. Identity and controls at the top, the stream filling everything below
 * it, the run record over the stream on selection. Nothing scrolls as a page: `layout="locked"`
 * hands `main`'s scrollbar to this screen and the stream's own table container is the only one on
 * it. What this replaced was one column a reader scrolled — a KPI region, a filter rail beside a
 * metric panel, a caption, a footer, a fetch line, a paragraph of legend, and two chart cards below
 * all of it — where the rows the screen is named for started halfway down.
 *
 * The two corpus charts moved to Corpus (`precedent-page.tsx`), which is not locked and is where
 * they can be tall. The legend paragraph moved into the record pane's ⓘ, and the rail became five
 * chips in the controls band.
 *
 * ## The scope, corrected
 *
 * This screen does not narrow to the workspace, and the reason is a choice rather than a schema
 * limit — the sentence this file used to carry got that wrong. `/api/runs` **does** accept
 * `repo_id` (`sync.dashboard.fleet.runs`, B149) and `app.py` reads it. What it cannot do is narrow
 * honestly: `repo_id` is null on any run whose finding the graph no longer holds, because the
 * checkpointer outlives `finding`, which every scan rebuilds. A narrowed page would silently drop
 * exactly the runs whose finding was patched or retracted — absence rendered as nothing, on the
 * screen least able to afford it. So the chip says *all workspaces* and the ⓘ says why.
 *
 * `/api/precedent/abandonment` genuinely takes no scope parameter, and that half of the old
 * paragraph left with the cards it described.
 *
 * ## One attempt is one attempt
 *
 * `CLAUDE.md`'s grain rule bites hardest here, because this is the only screen whose rows *are*
 * attempts. A finding retried three times is three rows on this page and one finding on every
 * other, and a reader comparing the two without being told would reasonably conclude one of them
 * is broken. The claim sits in the controls band; the argument is one hover away.
 */

import { Link, useParams } from "react-router"

import { DEFAULT_LIMIT } from "@/api/client"
import { hasLiveRun, useRuns } from "@/api/queries"
import {
  DetailLayout,
  useSelectionKeys,
  useSelectionParam,
} from "@/components/detail-layout"
import { FetchedAt } from "@/components/fetched-at"
import { FacetChips } from "@/components/filters"
import { InfoHint } from "@/components/info-hint"
import { ScopeChip } from "@/components/scope-chip"
import { ErrorState, LoadingState } from "@/components/states"
import { RunRecordDetail } from "@/features/runs/run-record-detail"
import { DISPOSITION_OPTIONS } from "@/features/runs/run-row"
import { RunsKpis } from "@/features/runs/runs-kpis"
import { RunsStream } from "@/features/runs/runs-stream"
import { ControlBar } from "@/layouts/control-bar"
import { ScreenFrame } from "@/layouts/screen-frame"
import type { StatusSegment } from "@/layouts/status-band"
import { UnknownRoute } from "@/layouts/unknown-route"
import { describeRecordWindow } from "@/lib/record-window"
import { useFilterParam } from "@/lib/use-filter-param"
import { useOffsetParam } from "@/lib/use-offset-param"

// One line, and it stays one line. Measured at 1366x768: every wrapped line up here is a row of
// the stream down there, and the grain claim in the controls band already says one row is one
// attempt -- a subtitle repeating it would be the second failure mode the brief names by name.
const QUESTION = "Every attempt the pipeline has checkpointed, newest first."

export function RunsPage() {
  const { repoId } = useParams<{ repoId: string }>()
  const [offset, setOffset] = useOffsetParam("runs_offset")
  // `useFilterParam` rather than a facet hook plus a separate `setOffset`, and the difference is a
  // real defect rather than tidiness: both hooks call `setSearchParams`, and React Router hands the
  // functional form the *current* params rather than a queued value -- so two writes in one handler
  // give the second a `prev` that predates the first, and the offset reset discarded the chip it
  // was meant to accompany. The chip looked pressed and nothing was refetched, which is the owner's
  // report of 2026-08-19. One write does both.
  const [outcome, setOutcome] = useFilterParam("runs_outcome", ["runs_offset"])
  // The open run lives in the URL and is written as a history push, so Back closes the drawer
  // rather than leaving the screen.
  const [openRun, setOpenRun] = useSelectionParam("runs_open")
  // One query for the whole screen. The strip used to issue a second `useRuns({limit: 1})` so it
  // could sit above the card that owned the real one; the figures are identical either way,
  // because `by_disposition` and `unfiltered_total` are computed before the outcome filter and
  // across every run rather than the page.
  const query = useRuns({ limit: DEFAULT_LIMIT, offset, outcome })

  const items = query.data?.items ?? []
  const selectedRun = items.find((run) => run.thread_id === openRun) ?? null
  // Arrow keys walk the stream with the drawer open, which is the affordance a row-to-drawer
  // table exists for.
  useSelectionKeys(
    items.map((run) => run.thread_id),
    openRun,
    setOpenRun,
  )

  if (repoId === undefined) return <UnknownRoute />

  // Built for every query state rather than for success alone: a band that appears only once an
  // answer arrives renders "not asked yet" and "asked and empty" as the same nothing.
  const status: StatusSegment[] = query.isSuccess
    ? [
        {
          kind: "records",
          label: "Runs",
          text: describeRecordWindow(
            offset,
            query.data.items.length,
            { count: query.data.total, boundReached: false },
            outcome === null ? "run" : "run carrying this disposition",
            outcome === null ? "runs" : "runs carrying this disposition",
          ),
          // The pager lives here rather than under the stream: a footer inside the content band
          // would be a second thing competing for the fixed height the stream is filling.
          paging: {
            offset,
            limit: DEFAULT_LIMIT,
            shown: query.data.items.length,
            total: query.data.total,
            unfilteredTotal: outcome === null ? undefined : query.data.unfiltered_total,
            nextOffset: query.data.next_offset,
            busy: query.isFetching,
            onOffsetChange: setOffset,
          },
        },
        // Without this the band is a fleet-wide count under one workspace's breadcrumb, which is
        // the `codebases-panel` defect this screen's scope statement exists to refuse.
        { kind: "note", text: "Counted across every workspace, not this one." },
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
        // The honest half of the reference's pause control: it says when the last successful fetch
        // returned and, when nothing is polling, why -- which distinguishes a poll that finished
        // from one that stalled, and a pause button does not.
        <FetchedAt
          at={query.dataUpdatedAt}
          polling={hasLiveRun(query.data)}
          idleReason="Every run here has reached an outcome, so nothing is being polled."
        />
      }
    >
      <FacetChips
        legend="Disposition"
        allLabel="Every run"
        selected={outcome}
        onSelect={setOutcome}
        options={DISPOSITION_OPTIONS.map((option) => ({
          value: option.value,
          count: query.data.by_disposition[option.bucket] ?? 0,
        }))}
        // The claim in the fewest honest words -- "counted before this filter" is one of the five
        // the prose ruling names outright -- with the argument in the ⓘ below. It was two
        // sentences, which wrapped to three lines at 1366x768 and starved the stream of two rows.
        countScope="Counted before this narrowing, over every run."
      />
      {/* Its own line rather than beside the chips. Sharing one line looked fine at 1920 and
          starved the chips to 266px at 1366, wrapping five of them into four rows: `flex-1` gives
          the fieldset whatever is left after this row's intrinsic width, and this row is wide. */}
      <div className="flex min-w-0 basis-full flex-wrap items-center gap-row">
        <ScopeChip scope="all workspaces">
          The runs route can be narrowed to a repository and this screen chooses not to be.{" "}
          <code className="font-mono">repo_id</code> is null on any run whose finding the graph no
          longer holds — the checkpointer outlives <code className="font-mono">finding</code>, which
          each scan rebuilds — so narrowing would silently drop exactly the runs whose finding was
          patched or retracted. Once the payload can report how many runs a narrowing excluded for
          want of a repository, this becomes a workspace view.
        </ScopeChip>
        {/* A claim, not an argument: one row is one attempt, and a finding retried three times is
            three rows here and one finding everywhere else. */}
        <span className="text-meta text-ink-muted">
          one row is one attempt, and counts once as a finding
        </span>
        <InfoHint label="About the run grain">
          One row is one <em>attempt</em>, not one finding: a finding retried across generations
          writes a new checkpoint thread each generation, and each generation is its own row here.
          So a total on this screen is larger than the finding count on every other screen and
          neither is wrong. An abandoned attempt is data rather than a failure to hide — the reason
          code is queryable, and abandonment by change kind is how routing learns which changes are
          not mechanically safe to attempt — which is what the Corpus link beside this reads.{" "}
          <strong>The chip counts and the record count answer different questions.</strong> Each
          chip is counted over every run this deployment holds, because the payload computes the
          roll-up before the narrowing applies — so a chip says what pressing it would return. The
          record count in the status band describes the narrowed set the pager is walking.
        </InfoHint>
        {/* The path to the two charts this screen used to render below its table. `ScreenTabs`
            would carry it and is mounted nowhere today (reported with this change), and a move
            that leaves its destination unreachable is not a move -- it is a deletion with extra
            steps. This link is what makes the move honest until the strip is mounted. */}
        <Link
          to={`/repositories/${encodeURIComponent(repoId)}/precedent`}
          className="text-meta underline underline-offset-2"
        >
          Abandonment by change kind, on Corpus
        </Link>
      </div>
    </ControlBar>
  ) : undefined

  return (
    <ScreenFrame layout="locked" controls={controls} status={status} subtitle={QUESTION}>
      {query.isPending && <LoadingState what="the runs" />}
      {query.isError && (
        <ErrorState
          error={query.error}
          what="the runs"
          onRetry={() => void query.refetch()}
        />
      )}

      {/* Dashboard R1. The strip portals itself into the top bar's second row; nothing is drawn
          for it here. */}
      {query.isSuccess && <RunsKpis page={query.data} />}

      {query.isSuccess && (
        <DetailLayout
          docked
          title="Run record"
          subtitle={selectedRun === null ? undefined : selectedRun.thread_id}
          onClose={() => setOpenRun(null)}
          detail={
            selectedRun !== null ? (
              <RunRecordDetail run={selectedRun} />
            ) : openRun === null ? null : (
              // Never silently closed: dropping a selection the URL still carries makes the
              // address and the screen disagree, and a bookmarked run is the case that does it.
              <p className="text-body text-ink-muted">
                That run is not on this page. The address names thread{" "}
                <span className="font-mono break-all">{openRun}</span>; the page in view starts at
                offset {offset}. Clear the selection or page back to it.
              </p>
            )
          }
          list={
            <RunsStream
              page={query.data}
              selected={openRun}
              onSelect={setOpenRun}
              narrowed={outcome !== null}
            />
          }
        />
      )}
    </ScreenFrame>
  )
}
