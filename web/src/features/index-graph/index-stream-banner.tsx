/**
 * What the stream is doing, above a canvas that does not move while you read it.
 *
 * **The graph behind this stays settled and the banner carries the aliveness.** Decision 87's
 * rule — content shifting under your eyes costs more than freshness buys — was applied to the
 * canvas deliberately, so decision 78's watch-it-index moment lives in a ticking count rather
 * than in a graph rearranging itself. `Show` is the reader choosing when the picture changes.
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
  /** Reveals what has arrived. Absent while nothing has. */
  readonly onShow?: () => void
}

export function IndexStreamBanner({ indexedCount, status, onShow }: IndexStreamBannerProps) {
  if (status === "dropped") {
    return (
      <p
        role="status"
        className="flex flex-col gap-field rounded-surface border border-line bg-surface p-row text-meta text-ink-muted"
      >
        <span className="text-ink">The live connection ended.</span>
        <span>
          This is what had arrived by then
          {indexedCount > 0 ? ` — ${indexedCount.toLocaleString()} call sites` : ""}. The index may
          still be running and this screen can no longer tell you.
        </span>
      </p>
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
      {onShow !== undefined && (
        <button
          type="button"
          onClick={onShow}
          className="rounded-control border border-line px-field text-meta text-ink underline-offset-2 hover:underline"
        >
          Show
        </button>
      )}
    </p>
  )
}
