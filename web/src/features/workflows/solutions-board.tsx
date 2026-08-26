/**
 * The solutions board: every remediation run as a card, in the column of the stage it reached.
 *
 * **The columns are the payload's vocabulary, not the board's** — `DISPOSITIONS` plus the
 * transport's word for the bucket with no disposition yet, which is the closed set `run-row.ts`
 * offers as chips and which the first test in `solutions-page.test.tsx` holds these against. A
 * column with no run still renders with a zero, because an absent column claims the stage does not
 * exist while a zero says nothing has reached it.
 *
 * **A heading and its cards answer different questions.** A heading is `by_disposition`, counted
 * over every run the checkpointer holds before any narrowing; the cards are the ones inside the
 * page window. So a column reads `43` over three cards honestly, and the footer says which is which.
 */

import type { ComponentType, SVGProps } from "react"
import { Link } from "react-router"
import {
  CircleDashed,
  CirclePause,
  CircleSlash,
  GitPullRequest,
  Megaphone,
} from "lucide-react"

import type { RunRow } from "@/api/types"
import { InfoHint } from "@/components/info-hint"
import { PanelPane } from "@/components/pane"
import { RelativeTime } from "@/components/relative-time"
import { Absent } from "@/components/status"
import { Tag, OUTCOME_TONE, type TagTone } from "@/components/tag"
import { isRehearsal, recordLine } from "@/features/runs/run-row"

/** `by_disposition`'s key for a run whose newest checkpoint carries no disposition. JSON spells it. */
export const IN_FLIGHT_BUCKET = "null"

/** What `/api/runs?outcome=` accepts for that bucket — `sync.dashboard.fleet.IN_FLIGHT`. */
export const IN_FLIGHT_FILTER = "in-flight"

export interface BoardStage {
  /** What `/api/runs?outcome=` accepts, which is also what Runs reads out of `runs_outcome`. */
  readonly filter: string
  /** `by_disposition`'s key. */
  readonly bucket: string
  readonly label: string
  readonly icon: ComponentType<SVGProps<SVGSVGElement>>
  /** What a run in this column has done. The column's own claim, in one sentence. */
  readonly claim: string
}

/**
 * The stages, left to right by how far the run got — still going, stopped for a person, gave up
 * and said so, gave up, opened a pull request.
 *
 * The order is editorial and the membership is not: reordering these changes nothing a reader can
 * be wrong about, while adding or dropping one would claim the checkpointer records a stage it does
 * not. The test holds membership against `DISPOSITION_OPTIONS` and says nothing about order.
 */
export const BOARD_STAGES: readonly BoardStage[] = [
  {
    filter: IN_FLIGHT_FILTER,
    bucket: IN_FLIGHT_BUCKET,
    label: "In flight",
    icon: CircleDashed,
    claim:
      "The newest checkpoint carries no disposition, so the graph still owes this run a node. How old that checkpoint is says nothing about whether the run is alive — the record pane carries the heartbeat, which is the field that does.",
  },
  {
    filter: "parked",
    bucket: "parked",
    label: "Parked",
    icon: CirclePause,
    claim:
      "The run stopped and is waiting on a person. It did not finish, and nothing is coming back to it on its own — which is why it is a column of its own rather than folded into in flight.",
  },
  {
    filter: "reported",
    bucket: "reported",
    label: "Reported",
    icon: Megaphone,
    claim: "The run stopped short of a patch and filed what it found instead.",
  },
  {
    filter: "abandoned",
    bucket: "abandoned",
    label: "Abandoned",
    icon: CircleSlash,
    claim:
      "The run gave up. The reason it recorded is on the card and in full in the record — abandonment is data the router learns from, not a failure to hide.",
  },
  {
    filter: "opened",
    bucket: "opened",
    label: "Opened",
    icon: GitPullRequest,
    claim: "The run pushed a branch and opened a pull request. This is the loop closing.",
  },
]

export interface BoardColumn {
  readonly stage: BoardStage
  /** Every run the checkpointer holds in this stage — never narrowed to the page window. */
  readonly count: number
}

/**
 * The board's columns, and anything the payload counted that has no column.
 *
 * `unrecognised` should always be empty: `sync.dashboard.fleet.runs` folds an outcome outside
 * `DISPOSITIONS` into the in-flight bucket before it reaches the transport, so `by_disposition`
 * cannot carry a key this file has not heard of. It is returned rather than dropped because the
 * alternative is a board that silently loses runs the day that stops being true, and a count with
 * no column is exactly the absence this console refuses to render as nothing.
 */
export function boardColumns(byDisposition: Record<string, number>): {
  columns: BoardColumn[]
  unrecognised: { key: string; count: number }[]
} {
  const known = new Set(BOARD_STAGES.map((stage) => stage.bucket))
  return {
    columns: BOARD_STAGES.map((stage) => ({
      stage,
      count: byDisposition[stage.bucket] ?? 0,
    })),
    unrecognised: Object.entries(byDisposition)
      .filter(([key]) => !known.has(key))
      .map(([key, count]) => ({ key, count })),
  }
}

/**
 * The page's runs, keyed by the bucket each one belongs in, newest first inside each.
 *
 * `outcome` is null on an in-flight run and on a run carrying a value the transport did not
 * recognise; both are `by_disposition`'s `"null"`, so the cards and the heading over them count the
 * same set by the same rule.
 */
export function groupByDisposition(items: readonly RunRow[]): Record<string, RunRow[]> {
  const grouped: Record<string, RunRow[]> = {}
  for (const run of items) {
    const bucket = run.outcome ?? IN_FLIGHT_BUCKET
    ;(grouped[bucket] ??= []).push(run)
  }
  return grouped
}

/** The tone the console already assigns this disposition. Parked and in flight are not verdicts. */
function toneFor(bucket: string): TagTone {
  return OUTCOME_TONE[bucket] ?? "neutral"
}

/**
 * One run, as a card.
 *
 * No disposition badge: every card in a column carries the column's disposition by construction, so
 * a badge here would be a constant repeated down the column — the same argument that kept a
 * severity pill out of the table this board replaced. What varies per card is the subject, its age
 * and the one line the run recorded, and those are the four lines.
 */
function SolutionCard({
  run,
  open,
  onSelect,
}: {
  run: RunRow
  open: boolean
  onSelect: (threadId: string) => void
}) {
  const record = recordLine(run)

  return (
    <button
      type="button"
      onClick={() => onSelect(run.thread_id)}
      // Without this the accessible name is the whole card read out — four lines of id, age and
      // record line — which is the least useful form of every one of those facts.
      aria-label={`Open the run record for ${run.finding_name ?? run.finding_id}`}
      aria-pressed={open}
      data-state={open ? "selected" : undefined}
      // `primary` is DESIGN.md's "the current thing" accent, carrying no verdict — it says which
      // card is open, not whether the run went well. The transition is the reader's own pointer,
      // which is the narrowing the motion guard permits.
      className="flex w-full min-w-0 flex-col gap-field rounded-surface border border-line bg-secondary px-row py-row text-left transition-colors hover:border-line-strong data-[state=selected]:border-primary"
    >
      {run.finding_name === null ? (
        <span className="text-body">
          <Absent>no longer in the graph</Absent>
        </span>
      ) : (
        <span className="truncate font-mono text-body text-ink">{run.finding_name}</span>
      )}
      <span className="truncate font-mono text-meta text-ink-muted">{run.finding_id}</span>
      <span className="flex min-w-0 flex-wrap items-center gap-field font-mono text-meta text-ink-muted">
        <RelativeTime iso={run.last_checkpoint_at} />
        <span aria-hidden="true">·</span>
        {isRehearsal(run) ? "rehearsal" : "live"}
      </span>
      <span className="truncate font-mono text-meta text-ink-muted">
        {record.absent === undefined ? record.text : <Absent>{record.absent}</Absent>}
      </span>
    </button>
  )
}

/** The door to every run in this stage, on the screen that pages through them one disposition at a time. */
function AllOnRuns({ repoId, stage }: { repoId: string; stage: BoardStage }) {
  return (
    <Link
      to={`/repositories/${encodeURIComponent(repoId)}/runs?runs_outcome=${encodeURIComponent(stage.filter)}`}
      className="underline underline-offset-2"
    >
      all of them on Runs
    </Link>
  )
}

function BoardColumnPane({
  column,
  cards,
  repoId,
  windowSize,
  checkpointerIsEmpty,
  selected,
  onSelect,
}: {
  column: BoardColumn
  cards: readonly RunRow[]
  repoId: string
  /** How many runs the board's current window holds, across every column. */
  windowSize: number
  /** Whether the checkpointer holds no run at all — a different nothing from an empty stage. */
  checkpointerIsEmpty: boolean
  selected: string | null
  onSelect: (threadId: string) => void
}) {
  const { stage, count } = column

  return (
    <PanelPane
      // `basis-0` with a floor: the columns divide the board evenly while they fit and stop
      // shrinking at a width a card is still readable in, at which point the board scrolls
      // sideways rather than crushing five columns into unreadable slivers.
      className="min-w-[15rem] shrink-0 basis-0"
      label={stage.label}
      icon={stage.icon}
      hint={<InfoHint label={`About ${stage.label.toLowerCase()}`}>{stage.claim}</InfoHint>}
      actions={<Tag tone={toneFor(stage.bucket)}>{count.toLocaleString()}</Tag>}
      bodyClassName="flex flex-col gap-row p-row"
      footer={
        count === 0 ? (
          <span>nothing here</span>
        ) : cards.length === count ? (
          <span>all {count.toLocaleString()} here</span>
        ) : (
          <span className="min-w-0 truncate">
            {cards.length.toLocaleString()} of {count.toLocaleString()} ·{" "}
            <AllOnRuns repoId={repoId} stage={stage} />
          </span>
        )
      }
    >
      {cards.length === 0 ? (
        // Three different nothings, and a blank column renders all three the same way.
        <p className="text-meta text-ink-muted">
          {checkpointerIsEmpty ? (
            <Absent>nothing has ever checkpointed</Absent>
          ) : count === 0 ? (
            <>
              <Absent>no run has reached this stage</Absent> The checkpointer answered and holds
              none carrying this disposition.
            </>
          ) : (
            <>
              {count.toLocaleString()} run{count === 1 ? "" : "s"} in this stage, none of them in
              this window of {windowSize.toLocaleString()} —{" "}
              <AllOnRuns repoId={repoId} stage={stage} />.
            </>
          )}
        </p>
      ) : (
        cards.map((run) => (
          <SolutionCard
            key={run.thread_id}
            run={run}
            open={selected === run.thread_id}
            onSelect={onSelect}
          />
        ))
      )}
    </PanelPane>
  )
}

/**
 * The board itself: one column per stage, each scrolling its own cards.
 *
 * No query of its own. The page owns the one `useRuns` call and hands the window down, so the
 * columns, the status band and the strip can never describe different sets.
 */
export function SolutionBoard({
  columns,
  items,
  unfilteredTotal,
  repoId,
  selected,
  onSelect,
}: {
  columns: readonly BoardColumn[]
  /** The page window, newest first, across every disposition. */
  items: readonly RunRow[]
  /** Every run the checkpointer holds — which nothing an empty column is. */
  unfilteredTotal: number
  repoId: string
  selected: string | null
  onSelect: (threadId: string) => void
}) {
  const grouped = groupByDisposition(items)

  return (
    // The board owns its own sideways scroll rather than letting the page grow: a locked screen
    // hands `main`'s scrollbar to the screen, and a column set wider than the frame has to be
    // reachable without the whole chassis moving.
    // `gap-section`, not the 32px between-panel exception: these columns are one object rather
    // than panels that happen to sit together, and 32px of gutter costs 128px of board at 1366.
    <div className="flex min-h-0 min-w-0 flex-1 gap-section overflow-x-auto">
      {columns.map((column) => (
        <BoardColumnPane
          key={column.stage.bucket}
          column={column}
          cards={grouped[column.stage.bucket] ?? []}
          repoId={repoId}
          windowSize={items.length}
          checkpointerIsEmpty={unfilteredTotal === 0}
          selected={selected}
          onSelect={onSelect}
        />
      ))}
    </div>
  )
}
