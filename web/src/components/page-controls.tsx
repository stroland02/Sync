/**
 * Paging over a list response.
 *
 * "Next" is driven by `next_offset` rather than by arithmetic on `total`: the transport
 * returns null on the last page precisely so a client cannot walk past the end.
 */

import { Button } from "@/components/ui/button"
import { describeRange } from "@/lib/format"

export function PageControls({
  offset,
  limit,
  shown,
  total,
  nextOffset,
  busy,
  onOffsetChange,
}: {
  offset: number
  limit: number
  shown: number
  total: number
  nextOffset: number | null
  busy: boolean
  onOffsetChange: (offset: number) => void
}) {
  return (
    <div className="flex items-center gap-3 text-body">
      <span className="text-ink-muted">{describeRange(offset, shown, total)}</span>
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
