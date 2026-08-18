/**
 * Paging over a list response.
 *
 * "Next" is driven by `next_offset` rather than by arithmetic on `total`: the transport
 * returns null on the last page precisely so a client cannot walk past the end.
 *
 * **No motion here, and the reason is a measurement rather than a preference.** This was a
 * `motion.div` carrying framer-motion's `layout` prop, described as "the paged table container
 * settling into its new height after a page swap". Measured on 2026-08-06 at 1440×900 against
 * `--scale 10000`: it had never once run. Every screen that paginates returns a loading state while
 * `query.isPending`, and a page change is a new query key with no cached data, so the subtree
 * unmounts and a fresh one mounts — `layout` animates a node that persists across a layout change,
 * and this node does not persist. Sampled every 40ms across a swap that took the row count from 50
 * to 34: zero transforms, zero entries in `document.getAnimations()`, and the node held before the
 * click came back `isConnected: false` afterwards with a different element in its place.
 *
 * It would not have earned itself even if it had worked. Motion claims a time and an offset
 * changing holds none, and paging is one of the most frequent interactions on a long table — the
 * case `DESIGN.md`'s frequency gate names outright.
 */

import { Button } from "@/components/ui/button"
import { describeRange } from "@/lib/format"

export function PageControls({
  offset,
  limit,
  shown,
  total,
  unfilteredTotal,
  nextOffset,
  busy,
  onOffsetChange,
}: {
  offset: number
  limit: number
  shown: number
  total: number
  /** The same scope's count with no filter applied, when the caller knows it. */
  unfilteredTotal?: number
  nextOffset: number | null
  busy: boolean
  onOffsetChange: (offset: number) => void
}) {
  return (
    <div className="flex items-center gap-3 text-body">
      <span className="text-ink-muted">{describeRange(offset, shown, total, unfilteredTotal)}</span>
      <Button
        variant="outline"
        size="sm"
        disabled={busy || offset === 0}
        onClick={() => onOffsetChange(Math.max(0, offset - limit))}
      >
        Previous
      </Button>
      <Button
        variant="outline"
        size="sm"
        disabled={busy || nextOffset === null}
        onClick={() => nextOffset !== null && onOffsetChange(nextOffset)}
      >
        Next
      </Button>
    </div>
  )
}
