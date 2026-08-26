/**
 * The catalogue's left column: one row per detector that has raised an open finding here.
 *
 * **Two facts per row, and the third was refused.** A name and a count. The obvious third — a
 * strip encoding each detector's rung mix — would put five segments in one monochrome ink,
 * distinguishable only by their position in the strip, which is the "colour is never the only
 * channel" refusal wearing a greyscale disguise. The mix is a pane away and drawn full size, with
 * every rung named beside its own bar.
 *
 * **No length encodes volume across rows.** One detector holding four figures' worth of findings
 * beside one holding three draws the smaller as a sliver, and a sliver reads as *found nothing* —
 * the absence-is-not-zero failure arriving through an axis. The counts are printed instead.
 */

import { Radar } from "lucide-react"

import type { DetectorRow } from "@/api/types"
import { cn } from "@/lib/utils"

export function DetectorIndex({
  rows,
  selected,
  onSelect,
}: {
  rows: readonly DetectorRow[]
  selected: string | null
  onSelect: (detector: string | null) => void
}) {
  return (
    <ul className="flex min-w-0 flex-col">
      {rows.map((row) => {
        const active = row.detector === selected
        return (
          <li key={row.detector} className="min-w-0 border-b border-line last:border-b-0">
            <button
              type="button"
              aria-current={active ? "true" : undefined}
              onClick={() => onSelect(active ? null : row.detector)}
              className={cn(
                "flex w-full min-w-0 items-center gap-row px-row py-row text-left",
                "focus:outline-none focus:ring-1 focus:ring-ring",
                active ? "bg-surface-subtle text-ink" : "text-ink-muted hover:bg-surface-subtle",
              )}
            >
              <Radar
                aria-hidden="true"
                className={cn("size-4 shrink-0", active ? "text-ink" : "text-graphics")}
              />
              <span className="min-w-0 flex-1 truncate font-mono text-meta text-ink">
                {row.detector}
              </span>
              <span className="shrink-0 font-mono text-meta tabular-nums">
                {row.total.toLocaleString()}
              </span>
            </button>
          </li>
        )
      })}
    </ul>
  )
}
