/**
 * What the stream is doing, above a canvas that does not move while you read it.
 *
 * **The banner accompanies the canvas; it never replaces it.** Revised: an earlier pass had the
 * graph stay settled until the reader asked, which made decision 87 govern a surface 87 was not
 * written for. 87 protects a reader *reading* a table; decision 78's canvas is a surface you are
 * *watching build*, and freezing it removes the one moment the one-command install exists to
 * create. So the canvas builds visibly and this strip says what is arriving beside it.
 *
 * **A drop names the loss and refuses the cause.** Nothing in this graph records whether an index
 * run is still going, so the console cannot say whether the work continues — only that it can no
 * longer see it. Claiming otherwise would be the console asserting a liveness it does not observe,
 * which is the failure this product exists to replace.
 *
 * **The count says *since you opened this*, and that wording is load-bearing.** A `NOTIFY`
 * sent while nobody is listening is not queued, so a reader who opens this mid-index sees
 * only what arrives after connecting. Labelling it as the run's total would be the screen
 * claiming it watched something it did not. The settled graph below carries the whole answer;
 * this number is honest about being a window onto it.
 *
 * There is no reconnect claim here for the same reason: `EventSource` retries natively, and a
 * retry loop against a dead server would render "reconnecting" forever, which is a statement
 * about a server nobody has heard from.
 */

import type { StreamStatus } from "@/features/index-graph/use-repository-events"

export interface IndexStreamBannerProps {
  readonly indexedCount: number
  readonly status: StreamStatus
  /**
   * Fetches the settled graph after a drop. Optional because it must be an action the reader
   * takes: swapping a live view for a static one without being asked would hide that the screen
   * stopped being live.
   */
  readonly onReread?: () => void
}

export function IndexStreamBanner({ indexedCount, status, onReread }: IndexStreamBannerProps) {
  if (status === "dropped") {
    return (
      <div
        role="status"
        className="flex flex-col gap-field rounded-surface border border-line bg-surface p-row text-meta text-ink-muted"
      >
        <span className="text-ink">The live connection ended.</span>
        <span>
          This is what had arrived by then
          {indexedCount > 0 ? ` — ${indexedCount.toLocaleString()} call sites` : ""}. The index may
          still be running and this screen can no longer tell you.
        </span>
        {onReread !== undefined && (
          <span>
            <button
              type="button"
              onClick={onReread}
              className="rounded-control border border-line px-field text-meta text-ink underline-offset-2 hover:underline"
            >
              Load the settled graph
            </button>{" "}
            — a complete answer you asked for, rather than one swapped in behind the frozen
            picture.
          </span>
        )}
      </div>
    )
  }

  if (indexedCount === 0) return null

  return (
    <p
      role="status"
      className="flex flex-wrap items-center gap-row rounded-surface border border-line bg-surface p-row text-meta"
    >
      <span className="text-ink">
        ↓ {indexedCount.toLocaleString()} call{" "}
        {indexedCount === 1 ? "site" : "sites"} indexed since you opened this
      </span>

    </p>
  )
}
