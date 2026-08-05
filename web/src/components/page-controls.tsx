/**
 * Paging over a list response.
 *
 * "Next" is driven by `next_offset` rather than by arithmetic on `total`: the transport
 * returns null on the last page precisely so a client cannot walk past the end.
 */

import { motion } from "framer-motion"

import { Button } from "@/components/ui/button"
import { describeRange } from "@/lib/format"
import { EASE_STANDARD, HEIGHT_TRANSITION_DURATION, useReducedMotion } from "@/lib/motion"

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
  const reduceMotion = useReducedMotion()

  return (
    <motion.div
      layout={!reduceMotion}
      transition={{ duration: HEIGHT_TRANSITION_DURATION, ease: EASE_STANDARD }}
      className="flex items-center gap-3 text-body"
    >
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
    </motion.div>
  )
}
