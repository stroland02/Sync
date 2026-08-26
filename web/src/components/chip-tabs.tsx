/**
 * A closed vocabulary as a strip of pressable chips, each optionally carrying its own count.
 *
 * **Written at the second use, which is one screen.** Findings narrows by severity and switches
 * between two groupings, and both were separate controls spelling the same anatomy — a bordered
 * chip climbing `chipSurface`'s rest / hover / selected ramp, one pressed at a time. The severity
 * strip was a `TriageTabs` tablist and the grouping toggle was a hand-rolled pair of buttons whose
 * classes had already drifted from it.
 *
 * **Buttons with `aria-pressed`, not a tablist.** A tablist promises panels, and the Radix `Tabs`
 * this replaces mounted one panel per value to render a single table. What these chips actually do
 * is write a search parameter; `aria-pressed` says that and nothing more.
 *
 * **What it refuses to render**, inherited verbatim from the component this replaces on the
 * Findings screen and still the reason it is worth having:
 *
 * - **No total across the chips.** Every count on screen is one the caller was given.
 * - **No colour on a chip or a count.** A hue on a severity chip grades the kind, and a colour
 *   that grades is the traffic light this console refuses. Selection is the surface step.
 * - **No zero standing in for an unanswered count.** `TriageCount` has no bare `number` to pass,
 *   so a view that never asked renders the absence marker with its reason attached.
 */

import { Absent } from "@/components/status"
import { chipSurface } from "@/lib/selectable-surface"
import type { TriageCount } from "@/components/triage"

export interface ChipOption {
  /** The vocabulary value itself — a severity kind, a grouping. */
  readonly id: string
  /** How that value is written for a reader. */
  readonly label: string
  /** Omitted where the control divides nothing countable, as the grouping toggle does. */
  readonly count?: TriageCount
}

/** The count as it sits on its chip: a figure, or the one absence marker with its reason. */
function ChipCount({ count }: { count: TriageCount }) {
  if (count.kind === "unanswered") {
    return (
      <span className="text-ink-muted">
        <Absent />
        <span className="sr-only"> count not answered: {count.why}</span>
      </span>
    )
  }
  return <span className="text-ink-muted tabular-nums">{count.value.toLocaleString()}</span>
}

export function ChipTabs({
  label,
  options,
  activeId,
  onSelect,
}: {
  /** What the chips divide, named for a screen reader — "Findings by kind". */
  label: string
  options: readonly ChipOption[]
  activeId: string
  onSelect: (id: string) => void
}) {
  return (
    <div role="group" aria-label={label} className="flex min-w-0 flex-wrap items-center gap-field">
      {options.map((option) => {
        const selected = option.id === activeId
        return (
          <button
            key={option.id}
            type="button"
            aria-pressed={selected}
            onClick={() => onSelect(option.id)}
            className={`flex shrink-0 items-center gap-field rounded-control border px-row py-field text-meta transition-colors ${chipSurface(selected)} ${
              selected ? "text-ink" : "text-ink-muted hover:text-ink"
            }`}
          >
            <span>{option.label}</span>
            {option.count !== undefined && <ChipCount count={option.count} />}
          </button>
        )
      })}
    </div>
  )
}
